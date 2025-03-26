import requests
import json
import psycopg2
from datetime import datetime
from config.settings import EMBY_SERVER_URL, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, EMBY_API_KEY
from config.log_config import get_logger

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
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取歌曲信息失败: {e}")
            return None

    def Set_Favorite(self, item_id):
        """收藏歌曲/专辑/歌手"""
        url = f"{self.host}/Users/{self._get_user_id()}/FavoriteItems/{item_id}"
        try:
            response = requests.post(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            logger.info(f"成功收藏项目: {item_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"收藏失败: {e}")

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

    def Get_Views(self):
        """获取视图列表并返回歌单视图 ID"""
        UserId, AccessToken = self.get_UserId_AccessToken()
        url = f"{self.host}/Users/{UserId}/Views"
        params = {"X-Emby-Token": AccessToken}
        response = requests.get(url, params=params)

        if response.status_code == 200:
            views_data = response.json()
            return views_data
        else:
            print(f"获取视图列表失败: {response.status_code} - {response.text}")
            return None

    def Get_Playlists(self):
        """获取歌单列表"""
        views_data = self.Get_Views()
        views_ids = [item['Id'] for item in views_data.get('Items',[]) if item['CollectionType'] == 'playlists']
        views_id = views_ids[0]

        UserId, AccessToken = self.get_UserId_AccessToken()
        url = f"{self.host}/Users/{UserId}/Items"
        params = {
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "ParentId": views_id,
            "Recursive": "true",
            "IncludeItemTypes": "Playlist",
            "Fields": "SortName,CanDelete,PrimaryImageAspectRatio",
            "EnableImageTypes": "Backdrop",
            "StartIndex": "0",
            "X-Emby-Token": AccessToken
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            return response.json().get("Items", [])
        else:
            print(f"获取歌单失败: {response.status_code} - {response.text}")
            return []

    def Create_Playlists(self, playlist_name):
        """创建歌单"""
        playlists = self.Get_Playlists()
        if any(pl.get("Name") == playlist_name for pl in playlists):
            print(f"歌单 '{playlist_name}' 已存在")
            return

        UserId, AccessToken = self.get_UserId_AccessToken()
        url = f"{self.host}/Playlists"
        headers = {"Content-Type": "application/json", "X-Emby-Token": AccessToken}
        data = {"Name": playlist_name, "Ids": "", "MediaType": "Audio"}
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            playlist_id = response.json().get("Id")
            print(f"成功创建歌单: {playlist_name} (ID: {playlist_id})")
            return playlist_id
        else:
            print(f"创建歌单失败: {response.status_code} - {response.text}")

    def Get_Tracks_Of_Playlist(self, playlist_id):
        """获取歌单中的歌曲"""
        UserId, AccessToken = self.get_UserId_AccessToken()
        url = f"{self.host}/Users/{UserId}/Items"
        params = {
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "Fields": "PrimaryImageAspectRatio,MediaSources,AudioInfo",
            "ImageTypeLimit": "1",
            "ParentId": playlist_id,
            "X-Emby-Token": AccessToken
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            return response.json().get("Items", [])
        else:
            print(f"获取歌单歌曲失败: {response.status_code} - {response.text}")
            return []

    def Add_Tracks_To_Playlist(self, playlist_id, track_ids):
        """
        添加歌曲到指定歌单
        :param playlist_id: 歌单 ID
        :param track_ids: 以逗号分隔的歌曲 ID 字符串
        """
        track_ids_list = track_ids.split(",")
        # 获取当前歌单中的歌曲
        tracks_of_playlist = self.Get_Tracks_Of_Playlist(playlist_id)
        existing_track_ids = {item["Id"] for item in tracks_of_playlist}

        # 过滤出需要添加的歌曲 ID
        track_ids_to_add = [track_id for track_id in track_ids_list if track_id not in existing_track_ids]

        if not track_ids_to_add:
            print("所有歌曲已在歌单中，无需添加。")
            return

        UserId, AccessToken = self.get_UserId_AccessToken()
        url = self.host + "/Playlists/" + playlist_id + "/Items"
        headers = {
            "Content-Type": "application/json",
            "X-Emby-Token": AccessToken
        }

        data = {
            "Ids": ",".join(track_ids_to_add),  # 将要添加的歌曲 ID 拼接为逗号分隔字符串
            "UserId": UserId,
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            return
        else:
            print(f"添加歌曲到歌单失败，HTTP 状态码: {response.status_code}，错误信息: {response.text}")

    def Del_Tracks_From_Playlist(self, playlist_id):
        """
        从指定歌单中移除所有歌曲
        :param playlist_id: 歌单 ID
        """
        # 获取当前歌单中的歌曲
        tracks_of_playlist = self.Get_Tracks_Of_Playlist(playlist_id)
        if not tracks_of_playlist:
            print("歌单中没有歌曲，无需移除。")
            return False

        # 提取所有歌曲 ID
        track_ids_to_remove = [item["PlaylistItemId"] for item in tracks_of_playlist]

        # 构造 API 请求
        UserId, AccessToken = self.get_UserId_AccessToken()
        url = f"{self.host}/Playlists/{playlist_id}/Items"
        headers = {
            "X-Emby-Token": AccessToken
        }
        params = {
            "entryIds": ",".join(track_ids_to_remove)  # 拼接歌曲 ID 列表为逗号分隔字符串
        }

        # 发起 DELETE 请求
        response = requests.delete(url, headers=headers, params=params)

        if response.status_code == 204:
            return True
        else:
            print(f"从歌单中移除歌曲失败，HTTP 状态码: {response.status_code}，错误信息: {response.text}")
            return False

    def Sessions(self):

        UserId, AccessToken = self.get_UserId_AccessToken()

        # 请求头，包含 API 密钥
        headers = {
            'accept': 'application/json',
            'X-Emby-Token': AccessToken,
        }

        params = {
            'DeviceId': 'sNmpJjgsnsL9O79Cv5iA2IwM',
        }

        response = requests.get(f'{self.host}/emby/Sessions', headers=headers, params=params)

        if response.status_code == 200:
            play_state_data = response.json()
            return play_state_data
        else:
            print(f"Failed to Get Session. Status code: {response.status_code}")

"""
if __name__ == "__main__":
    client_emby = Emby()
    client_emby.login()
    client_emby.Session()
"""