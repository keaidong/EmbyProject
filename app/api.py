import random
from collections import defaultdict
from app import emby
import redis  # 引入 Redis 客户端库
import pickle
from flask import Flask, request, jsonify
from config.log_config import get_logger
from config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_CACHE_DURATION_TRACKS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# 创建独立的日志记录器
logger = get_logger("app.api", "api.log")

app_api = Flask(__name__)

# 配置 Redis 连接
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)

class TrackFilter:
    def __init__(self):
        self.client_emby = emby.Emby().login()
        if not self.client_emby:
            logger.error("登录失败，程序退出")
            return

        self.db_conn = emby.Emby().Connect_To_EmbyDB()
        if not self.db_conn:
            logger.error("连接数据库失败，程序退出")
            return

        self.track_list = []
        self.track_info = {}
        self.play_process_results = None

    def filter_tracks(self):
        try:
            cache_keys = ["track_list", "track_info"]
            cached_data = redis_client.mget(cache_keys)

            if cached_data[0] is not None and cached_data[1] is not None:
                self.track_list = pickle.loads(cached_data[0])
                self.track_info = pickle.loads(cached_data[1])
                logger.debug(f"读取到的 track_list 长度: {len(self.track_list)}，track_info 长度: {len(self.track_info)}")
            # 如果缓存未命中，从 Emby 获取数据
            else:
                self.track_list = self.client_emby.Get_Tracks()
                if self.track_list is None:
                    logger.error("未能从 Emby 获取曲目数据")
                    return []

                track_list_pickled = pickle.dumps(self.track_list)
                redis_client.setex(cache_keys[0], REDIS_CACHE_DURATION_TRACKS, track_list_pickled)

                self.track_info = {}
                for track in self.track_list.get('Items', []):
                    track_id = track.get('Id')
                    if track_id:
                        track_details = self.client_emby.Get_Track_info(track_id)
                        if track_details:
                            self.track_info[track_id] = track_details
                        else:
                            logger.warning(f"曲目 {track_id} 的详细信息未能获取到")
                    else:
                        logger.warning(f"曲目没有有效的 ID: {track}")

                track_info_pickled = pickle.dumps(self.track_info)
                redis_client.setex(cache_keys[1], REDIS_CACHE_DURATION_TRACKS, track_info_pickled)

            filtered_tracks = []
            for track in self.track_list.get('Items', []):
                if track.get('UserData', {}).get('IsFavorite', False):
                    continue

                play_process_results = self._get_play_process()
                play_process_results_ids_1 = [result["id"] for result in play_process_results]
                play_process_results_ids_2 = [result["id"] for result in play_process_results if result["play_process"] < '50%']

                track_id = track['Id']
                if track_id in play_process_results_ids_2:
                    continue
                if track_id in play_process_results_ids_1:
                    if random.random() > 0.2:
                        continue

                filtered_tracks.append({
                    "Id": track_id,
                    "Genres": self.track_info[track_id].get("Genres", [])
                })

            return filtered_tracks
        except Exception as e:
            logger.error(f"滤曲目过程中出现错误：{e}")
            return []

    def _get_play_process(self):
        # 如果未缓存播放进度查询结果，执行查询
        if  self.play_process_results is None:
            with self.db_conn as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, play_process FROM track_play_record")
                result = cursor.fetchall()
                self.play_process_results = [{"id": row[0], "play_process": row[1]} for row in result] if result else []

        return self.play_process_results

    def get_top_tracks_by_playcount(self, top_count=20):
        """
        根据 PlayCount 降序排列曲目，并获取前 top_count 首曲目
        """
        try:
            # 确保 track_list 和 track_info 已加载
            if not self.track_list or not self.track_info:
                self.filter_tracks()

            # 提取曲目并排序
            tracks_with_playcount = [
                {
                    "Id": track["Id"],
                    "PlayCount": self.track_info[track["Id"]].get("UserData", {}).get("PlayCount", 0)
                }
                for track in self.track_list.get("Items", [])
                if track["Id"] in self.track_info
            ]

            # 按 PlayCount 降序排列
            sorted_tracks = sorted(tracks_with_playcount, key=lambda x: x["PlayCount"], reverse=True)

            # 获取前 top_count 首曲目
            top_tracks = sorted_tracks[:top_count]
            logger.info(f"获取到的前 {top_count} 首曲目: {top_tracks}")
            return top_tracks

        except Exception as e:
            logger.error(f"根据 PlayCount 排序曲目时发生错误: {e}")
            return []

class TrackGroupByGenre():
    def __init__(self, filtered_tracks):
        self.filtered_tracks = filtered_tracks

    def group_tracks_by_genre(self):
        genre_to_tracks = defaultdict(list)
        for track in self.filtered_tracks:
            # 遍历每个曲目的所有风格
            for genre in track["Genres"]:
                genre_to_tracks[genre].append(track["Id"])  # 将曲目 ID 添加到对应风格的列表中
        return genre_to_tracks

class TrackDistributor:
    def __init__(self, genre_to_tracks):
        self.genre_to_tracks = genre_to_tracks

    def average_distribute(self, random_count):
        # 平均分发逻辑
        logger.debug(
            f"Starting average distribution. random_count: {random_count}, genre_to_tracks: {self.genre_to_tracks.keys()}")

        genres = list(self.genre_to_tracks.keys())
        if not genres:
            raise ValueError("No tracks available to create the playlist.")

        base_count = random_count // len(genres)
        extra_count = random_count % len(genres)

        logger.debug(f"Base count per genre: {base_count}, Extra count to distribute: {extra_count}")

        genre_to_count = {genre: base_count for genre in genres}
        for genre in random.sample(genres, extra_count):
            genre_to_count[genre] += 1

        logger.debug(f"Genre to count distribution: {genre_to_count}")

        distributed_tracks = []
        selected_tracks = set()  # 用于存储已选曲目的 ID，防止重复

        for genre, count in genre_to_count.items():
            genre_tracks = self.genre_to_tracks[genre]
            available_tracks = [track for track in genre_tracks if track not in selected_tracks]

            if len(available_tracks) <= count:
                distributed_tracks.extend(available_tracks)
            else:
                selected = random.sample(available_tracks, count)
                distributed_tracks.extend(selected)
                selected_tracks.update(selected)

        # 确保最终曲目数量为 random_count
        remaining_count = random_count - len(distributed_tracks)
        if remaining_count > 0:
            remaining_tracks = [
                track for tracks in self.genre_to_tracks.values() for track in tracks if track not in selected_tracks
            ]
            additional_tracks = random.sample(remaining_tracks, min(remaining_count, len(remaining_tracks)))
            distributed_tracks.extend(additional_tracks)

        logger.debug(f"Final track count: {len(distributed_tracks)}")
        return distributed_tracks[:random_count]  # 截取 random_count 长度，防止超出

    def weight_distribute(self, random_count):
        # 加权分发逻辑
        logger.debug(
            f"Starting weighted distribution. random_count: {random_count}, genre_to_tracks: {self.genre_to_tracks.keys()}")

        genres = list(self.genre_to_tracks.keys())
        if not genres:
            raise ValueError("No tracks available to create the playlist.")

        total_tracks = sum(len(self.genre_to_tracks[genre]) for genre in genres)
        genre_to_weight = {genre: len(self.genre_to_tracks[genre]) / total_tracks for genre in genres}

        logger.debug(f"Calculated genre weights: {genre_to_weight}")

        genre_to_count = {genre: int(genre_to_weight[genre] * random_count) for genre in genres}

        total_allocated = sum(genre_to_count.values())
        adjustment = random_count - total_allocated
        if adjustment > 0:
            for genre in random.sample(genres, adjustment):
                genre_to_count[genre] += 1

        logger.debug(f"Genre to count distribution after adjustment: {genre_to_count}")

        distributed_tracks = []
        selected_tracks = set()

        for genre, count in genre_to_count.items():
            genre_tracks = self.genre_to_tracks[genre]
            available_tracks = [track for track in genre_tracks if track not in selected_tracks]

            if len(available_tracks) <= count:
                distributed_tracks.extend(available_tracks)
            else:
                selected = random.sample(available_tracks, count)
                distributed_tracks.extend(selected)
                selected_tracks.update(selected)

        # 确保最终曲目数量为 random_count
        remaining_count = random_count - len(distributed_tracks)
        if remaining_count > 0:
            remaining_tracks = [
                track for tracks in self.genre_to_tracks.values() for track in tracks if track not in selected_tracks
            ]
            additional_tracks = random.sample(remaining_tracks, min(remaining_count, len(remaining_tracks)))
            distributed_tracks.extend(additional_tracks)

        logger.debug(f"Final track count: {len(distributed_tracks)}")
        return distributed_tracks[:random_count]  # 确保最终长度匹配

class GenerateEmbyPlaylist:
    def __init__(self):
        self.track_filter = TrackFilter()
        self.filtered_tracks = self.track_filter.filter_tracks()
        self.genre_group = TrackGroupByGenre(self.filtered_tracks)
        self.genre_to_tracks = self.genre_group.group_tracks_by_genre()
        self.track_distributor = TrackDistributor(self.genre_to_tracks)

    def generate_playlist(self, random_count, distribution_type):
        if distribution_type == "average":
            distributed_tracks = self.track_distributor.average_distribute(random_count)
        elif distribution_type == "weight":
            distributed_tracks = self.track_distributor.weight_distribute(random_count)
        elif distribution_type == "top":
            distributed_tracks = self.track_filter.get_top_tracks_by_playcount(random_count)
        else:
            distributed_tracks = []
        return distributed_tracks

class GenerateResponses:
    def __init__(self, random_count, distribution_type):
        # 创建 GenerateEmbyPlaylist 的实例
        self.generateembyplaylist = GenerateEmbyPlaylist()
        # 使用 generate_playlist 方法初始化 distributed_tracks
        self.distributed_tracks = self.generateembyplaylist.generate_playlist(random_count, distribution_type)

        # 创建 TrackFilter 的实例
        self.track_filter = TrackFilter()
        # 使用 filter_tracks 方法初始化 track_list
        self.track_filter.filter_tracks()
        # 直接访问 track_list
        self.track_list = self.track_filter.track_list

    def generate_responses(self):
        responses_data = {
            "Items": [track for track in self.track_list.get('Items') if track['Id'] in self.distributed_tracks],
            "TotalRecordCount": self.track_list.get('TotalRecordCount')
        }
        return responses_data

@app_api.route('/average', methods=['POST'])
def generate_responses_average():
    data = request.get_json()  # 获取 JSON 数据
    random_count = data.get('random_count', 50)  # 默认值 50

    logger.info(f"API 请求: 生成 {random_count} 首曲目 (average 分发)")
    responses_data = GenerateResponses(random_count, distribution_type="average").generate_responses()
    try:
        if len(responses_data.get('Items')) == random_count:
            return jsonify(responses_data)
        else:
            return jsonify({
                "status": "error",
                "message": f"生成播放列表数量{len(responses_data.get('Items'))}与请求数量{random_count}不一致"
            }), 500
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app_api.route('/weight', methods=['POST'])
def generate_responses_weight():
    data = request.get_json()  # 获取 JSON 数据
    random_count = data.get('random_count', 50)  # 默认值 50

    logger.info(f"API 请求: 生成 {random_count} 首曲目 (weight 分发)")
    responses_data = GenerateResponses(random_count, distribution_type="weight").generate_responses()
    try:
        if len(responses_data.get('Items')) == random_count:
            return jsonify(responses_data)
        else:
            return jsonify({
                "status": "error",
                "message": f"生成播放列表数量{len(responses_data.get('Items'))}与请求数量{random_count}不一致"
            }), 500
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app_api.route('/top', methods=['POST'])
def generate_responses_top_playcount():
    data = request.get_json()  # 获取 JSON 数据
    top_count = data.get('top_count', 20)  # 默认获取前 20 首曲目

    logger.info(f"API 请求: 获取前 {top_count} 首曲目 (按 PlayCount 排序)")
    try:
        playlist_generator = GenerateEmbyPlaylist()
        top_tracks = playlist_generator.generate_playlist(top_count, distribution_type="top")
        top_tracks_ids = [track["Id"] for track in top_tracks]
        if len(top_tracks_ids) == top_count:
            # 构造响应数据
            responses_data = {
                "Items": [track for track in playlist_generator.track_filter.track_list.get('Items') if track['Id'] in top_tracks_ids],
                "TotalRecordCount": playlist_generator.track_filter.track_list.get('TotalRecordCount', 0)  # 获取所有曲目的总数量
            }
            return jsonify(responses_data)
        else:
            return jsonify({
                "status": "error",
                "message": f"生成播放列表数量{len(top_tracks_ids)}与请求数量{top_count}不一致"
            }), 500
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def update_cache():
    """
    定时更新 Emby 缓存
    """
    try:
        logger.info("开始定时更新 Emby 缓存")
        track_filter = TrackFilter()
        track_filter.filter_tracks()  # 调用现有的缓存更新逻辑
        logger.info("Emby 缓存更新完成")
    except Exception as e:
        logger.error(f"定时更新缓存时发生错误：{e}")

# 初始化定时任务
scheduler = BackgroundScheduler()
scheduler.start()

# 每隔 12 小时执行一次更新缓存任务
scheduler.add_job(
    func=update_cache,
    trigger=IntervalTrigger(hours=12),
    id='update_cache_job',
    name='定时更新 Emby 缓存',
    replace_existing=True
)

# 确保在程序退出时关闭定时任务
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app_api.run(host='0.0.0.0', port=5555, debug=True)