import requests
import json
import psycopg2
from datetime import datetime
from config.settings import EMBY_SERVER_URL, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, EMBY_API_KEY
from config.log_config import get_logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = get_logger("app.emby", "emby.log")


class Emby:
    def __init__(self, host=EMBY_SERVER_URL):
        self.host = host
        self.login_url = f"{host}/emby/Users/AuthenticateByName"
        self.UserId = None
        self.AccessToken = None

    def login(self, username="music", password="music"):
        """登录并获取 UserId 和 AccessToken"""
        headers = {
            "X-Emby-Client": "Emby Web",
            "X-Emby-Device-Name": "Chrome Windows",
            "X-Emby-Device-Id": "1609e44d-f7a5-4f9e-9b75-2328842391f0",
            "X-Emby-Client-Version": "4.7.14.0",
            "X-Emby-Language": "zh-cn"
        }
        data = {"Username": username, "Pw": password}
        try:
            response = requests.post(self.login_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            self.UserId = response.json().get("User", {}).get("Id")
            self.AccessToken = response.json().get("AccessToken")
            logger.info("登录成功")
            return self
        except requests.exceptions.RequestException as e:
            logger.error(f"登录失败: {e}")
            return None

    def _get_headers(self):
        """构造通用请求头"""
        if not self.AccessToken:
            raise ValueError("未登录，请先调用 login() 方法")
        return {"X-Emby-Token": self.AccessToken}

    def _get_user_id(self):
        """获取 UserId"""
        if not self.UserId:
            raise ValueError("未登录，请先调用 login() 方法")
        return self.UserId

    def Connect_To_EmbyDB(self):
        """连接 Emby 数据库"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                options="-c client_encoding=UTF8"
            )
            logger.info("成功连接到数据库")
            return conn
        except psycopg2.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def _get_session_with_retries(self):
        """创建带有重试机制的会话"""
        session = requests.Session()
        retries = Retry(
            total=5,  # 重试次数
            backoff_factor=1,  # 重试间隔时间的增长因子
            status_forcelist=[500, 502, 503, 504],  # 针对这些状态码进行重试
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def Get_Tracks(self):
        """获取所有歌曲列表"""
        url = f"{self.host}/Users/{self._get_user_id()}/Items"
        params = {
            "SortBy": "Random",
            "SortOrder": "Ascending",
            "IncludeItemTypes": "Audio",
            "Recursive": "true",
            "Fields": "SortName,MediaSources,AudioInfo,DateCreated,ProductionYear",
            "ImageTypeLimit": "1",
            "EnableImageTypes": "Backdrop",
            "StartIndex": "0",
        }
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()
            tracks_data = response.json()
            logger.info(f"获取歌曲成功，共 {tracks_data.get('TotalRecordCount', 0)} 首")
            return tracks_data
        except requests.exceptions.RequestException as e:
            logger.error(f"获取歌曲失败: {e}")
            return []

    def Get_Track_info(self, track_id):
        """获取单个歌曲信息"""
        url = f"{self.host}/Users/{self._get_user_id()}/Items/{track_id}"
        try:
            session = self._get_session_with_retries()
            response = session.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取歌曲信息失败: {e}")
            return None

    def make_item_played(self, item_id):
        """标记歌曲为已播放"""
        url = f"{self.host}/emby/Users/{self._get_user_id()}/PlayedItems/{item_id}"
        params = {"DatePlayed": datetime.now().strftime("%Y%m%d%H%M%S")}
        try:
            response = requests.post(url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()
            logger.info(f"成功标记歌曲 {item_id} 为已播放")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"标记歌曲为已播放失败: {e}")
            return None

    def make_item_unplayed(self, item_id):
        """标记歌曲为未播放"""
        url = f"{self.host}/emby/Users/{self._get_user_id()}/PlayedItems/{item_id}"
        try:
            response = requests.delete(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            logger.info(f"成功标记歌曲 {item_id} 为未播放")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"标记歌曲为未播放失败: {e}")
            return None

    def Sessions(self):
        """获取会话信息"""
        url = f"{self.host}/emby/Sessions"
        headers = self._get_headers()
        params = {"DeviceId": "sNmpJjgsnsL9O79Cv5iA2IwM"}
        try:
            session = self._get_session_with_retries()
            response = session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            play_state_data = response.json()
            return play_state_data
        except requests.exceptions.RequestException as e:
            logger.error(f"获取会话信息失败: {e}")
            return None