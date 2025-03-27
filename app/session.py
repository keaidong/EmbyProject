import app.emby as emby
import pytz
import json
from datetime import datetime
from config.log_config import get_logger
import logging
from collections import defaultdict
import time
from functools import wraps
import psycopg2

# 创建独立的日志记录器
logger = get_logger("app.session", "session.log")

# 设置 requests 和 urllib3 的日志级别，仅在当前模块中生效
logger_requests = logging.getLogger("requests")
logger_requests.setLevel(logging.WARNING)
logger_requests.propagate = False

logger_urllib3 = logging.getLogger("urllib3")
logger_urllib3.setLevel(logging.WARNING)
logger_urllib3.propagate = False

def retry_on_exception(retries=3, delay=1):
    """失败自动重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"操作失败: {e}, 重试中...")
                    time.sleep(delay)
            logger.error("重试失败")
            return None
        return wrapper
    return decorator


class Session:
    """
    Emby 会话管理类，用于监听播放状态并记录到数据库。
    """
    def __init__(self):
        self.client_emby = emby.Emby().login()
        if not self.client_emby:
            logger.error("❌ 登录 Emby 失败，程序退出")
            return

        self.db_conn = emby.Emby().Connect_To_EmbyDB()
        if not self.db_conn:
            logger.error("❌ 连接 Emby 数据库失败，程序退出")
            return

        self.commit_interval = 1  # 每 1 条数据提交一次
        self.china_tz = pytz.timezone("Asia/Shanghai")

    def connect_db(self):
        return emby.Emby().Connect_To_EmbyDB()

    def check_db_connection(self):
        """检查数据库连接是否有效，否则重连"""
        try:
            cur = self.db_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"⚠️ 数据库连接失效，正在尝试重新连接: {e}")
            self.db_conn = self.connect_db()
            if not self.db_conn:
                logger.error("❌ 数据库重连失败，程序退出")
                return False
        return True

    @retry_on_exception(retries=3, delay=1)
    def insert_play_record(self, record):
        """插入播放记录"""
        if not self.check_db_connection():
            return False

        try:
            play_duration = record["last_position_ticks"] - record["start_position_ticks"]
            play_duration = max(play_duration, 0)  # 避免负数

            track_duration = record["track_duration"]
            if track_duration != 0:
                # 计算播放进度（百分比）
                play_process = (play_duration / track_duration) * 100
                if play_process >= 99:
                    play_process_str = "100%"
                else:
                    play_process_str = f"{play_process:.2f}%"

                # 结束播放时间
                play_end_time_utc = datetime.utcnow()
                play_end_time_china = play_end_time_utc.replace(tzinfo=pytz.utc).astimezone(self.china_tz)

                cur = self.db_conn.cursor()
                cur.execute(
                    """
                    INSERT INTO track_play_record (
                        id, name, path, genres, runtimeticks, 
                        start_play, stop_play, username, 
                        client, devicename, play_duration, play_process
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET play_duration = EXCLUDED.play_duration, 
                        stop_play = EXCLUDED.stop_play
                    """,
                    (
                        int(record["id"]),
                        record["name"],
                        record["path"],
                        record["genres"],
                        record["track_duration"] // 10000000,  # 纳秒转换为秒
                        record["start_play"],
                        play_end_time_china,
                        record["username"],
                        record["client"],
                        record["devicename"],
                        play_duration // 10000000,  # 纳秒转换为秒
                        play_process_str,
                    ),
                )
            logger.info(f"🎵 播放记录插入成功，曲目 ID: {record['id']}")
            return True
        except Exception as e:
            logger.error(f"❌ 插入播放记录失败: {e}", exc_info=True)
            self.db_conn.rollback()
            return False

    def get_session(self):
        """
        监听 Emby 播放状态。
        """
        track_play_record = defaultdict(dict)
        last_played_track_id = None
        count = 0

        while True:
            try:
                play_state_data = self.client_emby.Sessions()
                if not play_state_data:
                    time.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"⚠️ 获取 Emby 会话数据失败: {e}", exc_info=True)
                time.sleep(5)
                continue

            # 处理当前播放会话
            item = play_state_data[0]
            if item.get("NowPlayingItem") is None:
                continue

            now_playing = item["NowPlayingItem"]
            item_id = now_playing.get("Id", "")
            item_name = now_playing.get("Name", "")
            item_path = now_playing.get("Path", "")
            item_runtimeticks = now_playing.get("RunTimeTicks", 0)
            item_genres = json.dumps(now_playing.get("Genres", []))

            position_ticks = item.get("PlayState", {}).get("PositionTicks", 0)

            username = item.get("UserName", "")
            client = item.get("Client", "")
            device_name = item.get("DeviceName", "")

            timestamp_utc = datetime.utcnow()
            timestamp_china = timestamp_utc.replace(tzinfo=pytz.utc).astimezone(self.china_tz)

            if item_id != last_played_track_id:
                if last_played_track_id:
                    last_track = track_play_record[last_played_track_id]
                    play_duration = last_track["last_position_ticks"] - last_track["start_position_ticks"]
                    play_duration = max(play_duration, 0)

                    if play_duration > 0:
                        play_end_time_china = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(self.china_tz)
                        logger.info(
                            f"🎵 {last_track['name']} 结束播放: {play_end_time_china}, 播放时长: {play_duration // 10000000} 秒"
                        )

                        if self.insert_play_record(last_track):
                            count += 1
                            if count >= self.commit_interval:
                                self.db_conn.commit()
                                count = 0

                # 记录新歌曲的播放信息
                track_play_record[item_id] = {
                    "id": item_id,
                    "name": item_name,
                    "path": item_path,
                    "genres": item_genres,
                    "track_duration": item_runtimeticks,
                    "start_play": timestamp_china,
                    "last_position_ticks": position_ticks,
                    "start_position_ticks": position_ticks,
                    "username": username,
                    "client": client,
                    "devicename": device_name,
                }

                logger.info(f"▶️ {item_name} 开始播放: {timestamp_china}")
                last_played_track_id = item_id
            else:
                if position_ticks > track_play_record[item_id]["last_position_ticks"]:
                    track_play_record[item_id]["last_position_ticks"] = position_ticks

            time.sleep(1)

if __name__ == "__main__":
    session = Session()
    if session.client_emby and session.db_conn:
        session.get_session()
