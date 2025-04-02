import random
from collections import defaultdict
from app import emby
from config.log_config import get_logger
import logging

logger = get_logger("app.GenrePlaylistGenerator", "GenrePlaylistGenerator.log")

class GenrePlaylistGenerator:
    def __init__(self, total_tracks=8103, genres_count=42):
        try:
            self.client_emby = emby.Emby().login()
            if not self.client_emby:
                raise RuntimeError("登录 Emby 失败")

            self.db_conn = emby.Emby().Connect_To_EmbyDB()
            if not self.db_conn:
                raise RuntimeError("连接 Emby 数据库失败")

            self.total_tracks = total_tracks
            self.genres_count = genres_count

            # 从 Emby API 获取真实数据
            self.tracks_by_genre = self._generate_mock_data()
            self.initialized = True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            self.initialized = False

    def _generate_mock_data(self):
        try:
            # 获取所有曲目及其流派
            tracks_genres_data = self.client_emby.Get_Tracks_Genres().get("Items", [])
            if not tracks_genres_data:
                logger.warning("从 Emby 获取的曲目数据为空")
                return {}

            # 按流派组织曲目
            tracks_by_genre = defaultdict(list)
            for item in tracks_genres_data:
                if not item.get("Genres") or not item.get("MediaSources"):
                    logger.warning(f"曲目 {item.get('Id')} 缺少流派或媒体源，跳过")
                    continue
                for genre in item["Genres"]:
                    tracks_by_genre[genre].append({
                        "Id": item["Id"],
                        "Name": item["Name"]
                    })

            return tracks_by_genre
        except Exception as e:
            logger.error(f"生成曲目流派数据失败: {e}")
            return {}

    def generate_playlist(self, count=100):
        """生成播放列表，确保曲目数量与 count 一致"""
        if not self.initialized:
            logger.error("生成播放列表失败: 初始化未成功")
            return [], {}

        try:
            if count > self.total_tracks:
                raise ValueError("请求的曲目数超过曲库总量")

            # 平均分配部分
            base_per_genre = count // self.genres_count
            remaining = count % self.genres_count

            playlist = []
            allocation_stats = defaultdict(int)
            used_tracks = set()

            # 按流派循环分配
            for genre in self.tracks_by_genre:
                # 获取该流派所有可用曲目(未使用的)
                available_tracks = [
                    t for t in self.tracks_by_genre[genre]
                    if t["Id"] not in used_tracks
                ]

                # 计算该流派本次要分配的曲目数
                to_take = min(base_per_genre, len(available_tracks))

                # 随机选择曲目
                selected = random.sample(available_tracks, to_take)
                playlist.extend(selected)
                used_tracks.update(t["Id"] for t in selected)
                allocation_stats[genre] = to_take

            # 剩余曲目按权重分配
            if remaining > 0:
                genre_weights = {
                    genre: len([
                        t for t in self.tracks_by_genre[genre]
                        if t["Id"] not in used_tracks
                    ])
                    for genre in self.tracks_by_genre
                }
                total_weight = sum(genre_weights.values())

                if total_weight > 0:
                    for _ in range(remaining):
                        genre = random.choices(
                            list(genre_weights.keys()),
                            weights=list(genre_weights.values()),
                            k=1
                        )[0]

                        available = [
                            t for t in self.tracks_by_genre[genre]
                            if t["Id"] not in used_tracks
                        ]

                        if available:
                            track = random.choice(available)
                            playlist.append(track)
                            used_tracks.add(track["Id"])
                            allocation_stats[genre] += 1
                            genre_weights[genre] -= 1
                            total_weight -= 1

            # 如果仍然不足，补充曲目
            if len(playlist) < count:
                logger.warning(f"播放列表曲目不足，当前数量: {len(playlist)}，目标数量: {count}")
                all_available_tracks = [
                    t for genre_tracks in self.tracks_by_genre.values()
                    for t in genre_tracks
                    if t["Id"] not in used_tracks
                ]

                additional_needed = count - len(playlist)
                if len(all_available_tracks) >= additional_needed:
                    additional_tracks = random.sample(all_available_tracks, additional_needed)
                else:
                    additional_tracks = all_available_tracks  # 如果可用曲目不足，全部添加

                playlist.extend(additional_tracks)
                used_tracks.update(t["Id"] for t in additional_tracks)

            # 最终检查数量是否一致
            if len(playlist) > count:
                logger.warning(f"播放列表曲目数量超出目标数量，实际数量: {len(playlist)}，目标数量: {count}")
                playlist = playlist[:count]  # 截断多余的曲目

            if len(playlist) < count:
                logger.warning(f"播放列表曲目不足，实际数量: {len(playlist)}，目标数量: {count}")
                all_available_tracks = [
                    t for genre_tracks in self.tracks_by_genre.values()
                    for t in genre_tracks
                    if t["Id"] not in used_tracks
                ]
                additional_needed = count - len(playlist)
                additional_tracks = random.sample(all_available_tracks, min(len(all_available_tracks), additional_needed))
                playlist.extend(additional_tracks)

            # 最终返回结果
            return playlist, dict(allocation_stats)
        except ValueError as e:
            logger.error(f"生成播放列表失败: {e}")
            return [], {}
        except Exception as e:
            logger.error(f"生成播放列表过程中出现错误: {e}")
            return [], {}

    def get_genre_distribution(self):
        """获取原始流派分布统计"""
        if not self.tracks_by_genre:
            logger.warning("流派分布数据为空")
            return {}
        return {
            genre: len(tracks)
            for genre, tracks in self.tracks_by_genre.items()
        }


# 使用示例
if __name__ == "__main__":
    generator = GenrePlaylistGenerator()
    
    # 生成100首曲目的播放列表
    playlist, stats = generator.generate_playlist(500)
    
    print(f"生成的播放列表({len(playlist)}首):")
    print(playlist[:10], "...")  # 只打印前10首
    
    print("\n流派分配情况:")
    for genre, count in stats.items():
        print(f"{genre}: {count}首")
    
    # 查看原始流派分布
    original_dist = generator.get_genre_distribution()
    print("\n原始流派分布(前5个):")
    for i, (genre, count) in enumerate(original_dist.items()):
        if i >= 5:
            break
        print(f"{genre}: {count}首")