import random
from collections import defaultdict
import pickle
import redis
import logging
from app import emby
from config.log_config import get_logger
from config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_CACHE_DURATION_TRACKS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

logger = get_logger("app.emby_playlist_utils", "emby_playlist_utils.log", log_level=logging.INFO)
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)

class EmbyTrackRepository:
    """负责从 Emby 获取曲目数据并缓存到 Redis"""
    def __init__(self):
        self.client_emby = emby.Emby().login()
        if not self.client_emby:
            raise RuntimeError("Emby 登录失败")
        self.db_conn = emby.Emby().Connect_To_EmbyDB()
        if not self.db_conn:
            raise RuntimeError("Emby 数据库连接失败")

    def get_tracks_and_details(self):
        cache_keys = ["track_list", "track_detail"]
        cached_data = redis_client.mget(cache_keys)
        if cached_data[0] and cached_data[1]:
            track_list = pickle.loads(cached_data[0])
            track_detail = pickle.loads(cached_data[1])
            logger.debug(f"从 Redis 加载曲目数据，track_list 长度: {len(track_list.get('Items', []))} || track_detail 长度: {len(track_detail)}")
        else:
            logger.warning("Redis 缓存未命中，重新从 Emby 获取数据")
            # 这里修正为统一 dict 格式
            tracks = self.client_emby.Get_Tracks()
            if not tracks:
                raise RuntimeError("从 Emby 获取的曲目数据为空")
            # 保证 track_list 是 dict 且有 Items
            track_list = {"Items": tracks, "TotalRecordCount": len(tracks)}
            redis_client.setex(cache_keys[0], REDIS_CACHE_DURATION_TRACKS, pickle.dumps(track_list))
            track_detail = {}
            for track in track_list.get('Items', []):
                track_id = track.get('Id')
                if track_id:
                    detail = self.client_emby.Get_Track_info(track_id)
                    if detail:
                        track_detail[track_id] = detail
            redis_client.setex(cache_keys[1], REDIS_CACHE_DURATION_TRACKS, pickle.dumps(track_detail))
        return track_list, track_detail

    def get_play_process(self):
        with self.db_conn as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, play_process FROM track_play_record")
            result = cursor.fetchall()
            return [{"id": row[0], "play_process": row[1]} for row in result] if result else []

class TrackFilter:
    """负责曲目筛选"""
    def __init__(self, track_list, track_detail, play_process_results):
        self.track_list = track_list
        self.track_detail = track_detail
        self.play_process_results = play_process_results

    def filter_tracks(self):
        play_ids = [str(r["id"]) for r in self.play_process_results]
        play_ids_50 = [str(r["id"]) for r in self.play_process_results if r["play_process"] < '50%']
        filtered = []
        for track in self.track_list.get('Items', []):
            if track.get('UserData', {}).get('IsFavorite', False):
                continue
            if track.get('UserData', {}).get('Played', False):
                continue
            if track['Id'] not in self.track_detail:
                continue
            if track['Id'] in play_ids_50:
                continue
            if track['Id'] in play_ids:
                if random.random() > 0.2:
                    continue
            filtered.append({
                "Id": track['Id'],
                "Genres": self.track_detail[track['Id']].get("Genres", [])
            })
        return filtered

    def get_top_tracks_by_playcount(self, top_count=20):
        tracks_with_playcount = [
            {
                "Id": track["Id"],
                "PlayCount": self.track_detail[track["Id"]].get("UserData", {}).get("PlayCount", 0)
            }
            for track in self.track_list.get("Items", [])
            if track["Id"] in self.track_detail
        ]
        sorted_tracks = sorted(tracks_with_playcount, key=lambda x: x["PlayCount"], reverse=True)
        return sorted_tracks[:top_count]

class TrackGrouper:
    """负责按风格分组"""
    def __init__(self, filtered_tracks):
        self.filtered_tracks = filtered_tracks

    def group_by_genre(self):
        genre_to_tracks = defaultdict(list)
        for track in self.filtered_tracks:
            for genre in track["Genres"]:
                genre_to_tracks[genre].append(track["Id"])
        return genre_to_tracks

class TrackDistributor:
    """负责分发算法"""
    def __init__(self, genre_to_tracks):
        self.genre_to_tracks = genre_to_tracks

    def average_distribute(self, random_count):
        genres = list(self.genre_to_tracks.keys())
        if not genres:
            raise ValueError("No tracks available to create the playlist.")
        base_count = random_count // len(genres)
        extra_count = random_count % len(genres)
        genre_to_count = {genre: base_count for genre in genres}
        for genre in random.sample(genres, extra_count):
            genre_to_count[genre] += 1
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
        remaining_count = random_count - len(distributed_tracks)
        if remaining_count > 0:
            remaining_tracks = [
                track for tracks in self.genre_to_tracks.values() for track in tracks if track not in selected_tracks
            ]
            additional_tracks = random.sample(remaining_tracks, min(remaining_count, len(remaining_tracks)))
            distributed_tracks.extend(additional_tracks)
        return distributed_tracks[:random_count]

    def weight_distribute(self, random_count):
        genres = list(self.genre_to_tracks.keys())
        if not genres:
            raise ValueError("No tracks available to create the playlist.")
        total_tracks = sum(len(self.genre_to_tracks[genre]) for genre in genres)
        genre_to_weight = {genre: len(self.genre_to_tracks[genre]) / total_tracks for genre in genres}
        genre_to_count = {genre: int(genre_to_weight[genre] * random_count) for genre in genres}
        total_allocated = sum(genre_to_count.values())
        adjustment = random_count - total_allocated
        if adjustment > 0:
            for genre in random.sample(genres, adjustment):
                genre_to_count[genre] += 1
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
        remaining_count = random_count - len(distributed_tracks)
        if remaining_count > 0:
            remaining_tracks = [
                track for tracks in self.genre_to_tracks.values() for track in tracks if track not in selected_tracks
            ]
            additional_tracks = random.sample(remaining_tracks, min(remaining_count, len(remaining_tracks)))
            distributed_tracks.extend(additional_tracks)
        return distributed_tracks[:random_count]

class PlaylistService:
    """统一入口，负责生成播放列表和响应"""
    def __init__(self):
        self.repo = EmbyTrackRepository()
        self.track_list, self.track_detail = self.repo.get_tracks_and_details()
        self.play_process_results = self.repo.get_play_process()
        self.filter = TrackFilter(self.track_list, self.track_detail, self.play_process_results)
        self.filtered_tracks = self.filter.filter_tracks()
        self.grouper = TrackGrouper(self.filtered_tracks)
        self.genre_to_tracks = self.grouper.group_by_genre()
        self.distributor = TrackDistributor(self.genre_to_tracks)

    def generate_playlist(self, count, mode="average"):
        if mode == "average":
            return self.distributor.average_distribute(count)
        elif mode == "weight":
            return self.distributor.weight_distribute(count)
        elif mode == "top":
            return self.filter.get_top_tracks_by_playcount(count)
        else:
            raise ValueError(f"未知分发模式: {mode}")

    def generate_response(self, count, mode="average"):
        playlist = self.generate_playlist(count, mode)
        if mode == "top":
            ids = [track["Id"] for track in playlist]
        else:
            ids = playlist
        items = [track for track in self.track_list.get('Items', []) if track['Id'] in ids]
        return {
            "Items": items,
            "TotalRecordCount": self.track_list.get('TotalRecordCount')
        }

# 对外暴露的主方法
def generate_responses_average(random_count=50):
    try:
        logger.info(f"生成 {random_count} 首曲目 (average 分发)")
        service = PlaylistService()
        resp = service.generate_response(random_count, mode="average")
        if len(resp.get('Items', [])) == random_count:
            return resp
        else:
            logger.warning(f"生成播放列表数量不一致")
            return {"status": "error", "message": f"生成播放列表数量{len(resp.get('Items', []))}与请求数量{random_count}不一致"}
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def generate_responses_weight(random_count=50):
    try:
        logger.info(f"生成 {random_count} 首曲目 (weight 分发)")
        service = PlaylistService()
        resp = service.generate_response(random_count, mode="weight")
        if len(resp.get('Items', [])) == random_count:
            return resp
        else:
            logger.warning(f"生成播放列表数量不一致")
            return {"status": "error", "message": f"生成播放列表数量{len(resp.get('Items', []))}与请求数量{random_count}不一致"}
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def generate_responses_top_playcount(top_count=20):
    try:
        logger.info(f"获取前 {top_count} 首曲目 (按 PlayCount 排序)")
        service = PlaylistService()
        resp = service.generate_response(top_count, mode="top")
        if len(resp.get('Items', [])) == top_count:
            return resp
        else:
            logger.warning(f"生成播放列表数量不一致")
            return {"status": "error", "message": f"生成播放列表数量{len(resp.get('Items', []))}与请求数量{top_count}不一致"}
    except Exception as e:
        logger.error(f"生成播放列表失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def update_cache():
    try:
        logger.debug("开始更新 Emby 缓存")
        repo = EmbyTrackRepository()
        repo.get_tracks_and_details()
        logger.debug("Emby 缓存更新完成")
    except Exception as e:
        logger.error(f"更新缓存时发生错误：{e}")

# 启动定时任务，每天凌晨1点执行
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=update_cache,
    trigger=CronTrigger(hour=1, minute=0),
    id='update_cache_job',
    name='每天凌晨1点更新Emby缓存',
    replace_existing=True
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# if __name__ == '__main__':
#     print("平均分发：")
#     print(generate_responses_average(10))
#     print("加权分发：")
#     print(generate_responses_weight(10))
#     print("Top播放量：")
#     print(generate_responses_top_playcount(5))