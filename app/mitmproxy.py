import sys
import os

# 添加项目根目录到 sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mitmproxy import http
import json
import time
import requests
from urllib.parse import urlparse, parse_qs
import emby
from config.log_config import get_logger
from config.settings import EMBY_SERVER_URL, EMBY_USER_ID, EMBY_API_KEY

# 创建独立的日志记录器
logger = get_logger("app.mitmproxy", "mitmproxy.log")

# 检查配置项是否正确加载
if not EMBY_SERVER_URL or not EMBY_USER_ID or not EMBY_API_KEY:
    raise ValueError("环境变量未正确配置，请检查 config/settings.py 或 .env 文件")


class EmbyProxyHandler:
    def _get_limit_from_query(self, query_dict):
        """
        从查询参数中获取 Limit 值
        """
        limit_str = query_dict.get("Limit", [None])[0]
        return int(limit_str) if limit_str else None

    def handle_emby_request(self, flow: http.HTTPFlow):
        """
        根据请求 URL 调用对应的处理逻辑
        """
        try:
            url_path = urlparse(flow.request.pretty_url).path
            query_params = urlparse(flow.request.pretty_url).query
            query_dict = parse_qs(query_params)
            limit = self._get_limit_from_query(query_dict)

            # 处理曲目请求
            if flow.request.pretty_url.startswith(f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items"):
                include_item_types = query_dict.get('IncludeItemTypes', [])
                sort_by = query_dict.get('SortBy', [])

                # 1. 曲目类
                if 'Audio' in include_item_types :
                    # 1. 每日推荐
                    if 'Random' in sort_by and limit in [50, 100]:  # Limit 为 50、100调用平均分发接口
                        logger.info(f"拦截到每日推荐 {limit} 首请求")
                        self.process_items_request_average(flow, limit)
                    if 'Random' in sort_by and limit == 500:  # Limit 为500调用权重分发接口
                        logger.info(f"拦截到每日推荐 {limit} 首请求")
                        self.process_items_request_weight(flow, limit)                        
                    # 2. 最常播放
                    if 'PlayCount' in sort_by and limit == 20:  # 仅处理 Limit 为 20 的请求
                        logger.info(f"拦截到最常播放 {limit} 首请求")
                        self.process_items_request_top(flow, limit)
                    # 3. 最近播放   
                    if 'DatePlayed' in sort_by and limit == 20:  # 仅处理 Limit 为 20 的请求
                        logger.info(f"拦截到最近播放 {limit} 首请求")
                        pass              
                
                # 2. 专辑类
                if 'MusicAlbum' in include_item_types:
                    pass


            # 处理风格类型请求
            elif flow.request.pretty_url.startswith(f"{EMBY_SERVER_URL}/Genres"):
                logger.info("拦截到获取风格类型请求")
                self.process_genres_request(flow)

            # 处理封面请求（ID 替换）
            elif url_path.startswith("/Items/") and "Images/Primary" in url_path:
                if query_dict.get("tag", [None])[0] == "null":
                    logger.info("拦截到获取封面请求")
                    self.process_id_replacement(flow, url_path)

        except Exception as e:
            logger.error(f"请求处理失败: {e}, 请求 URL: {flow.request.pretty_url}", exc_info=True)

    def process_items_request_average(self, flow: http.HTTPFlow, limit: int):
        """
        处理曲目数据请求，并返回自定义的曲目列表
        """
        try:
            # 调用 /average 接口获取曲目数据
            url = f"http://192.168.2.40:5555/average"

            # 将数据转换为 JSON 格式
            data = {'random_count': limit}

            # 设置请求头为 application/json
            headers = {'Content-Type': 'application/json'}

            # 发送 POST 请求
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == 200:
                track_data = response.json()  # 返回曲目数据
                if not track_data or 'Items' not in track_data or len(track_data['Items']) == 0:
                    logger.warning("API返回的曲目数据无效或为空")
                    return
                # 设置自定义响应
                flow.response = self.create_response(track_data)
                logger.info(f"自定义随机生成 {limit} 首曲目成功")
            else:
                logger.error(f"API 请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"调用 API 时发生错误: {e}", exc_info=True)
            return None            

    def process_items_request_weight(self, flow: http.HTTPFlow, limit: int):
        """
        处理曲目数据请求，并返回自定义的曲目列表
        """
        try:
            # 调用 /average 接口获取曲目数据
            url = f"http://192.168.2.40:5555/weight"

            # 将数据转换为 JSON 格式
            data = {'random_count': limit}

            # 设置请求头为 application/json
            headers = {'Content-Type': 'application/json'}

            # 发送 POST 请求
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == 200:
                track_data = response.json()  # 返回曲目数据
                if not track_data or 'Items' not in track_data or len(track_data['Items']) == 0:
                    logger.warning("API返回的曲目数据无效或为空")
                    return
                # 设置自定义响应
                flow.response = self.create_response(track_data)
                logger.info(f"自定义随机生成 {limit} 首曲目成功")
            else:
                logger.error(f"API 请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"调用 API 时发生错误: {e}", exc_info=True)
            return None           

    def process_items_request_top(self, flow: http.HTTPFlow, limit: int):
        """
        处理曲目数据请求，并返回自定义的曲目列表
        """
        try:
            # 调用 /average 接口获取曲目数据
            url = f"http://192.168.2.40:5555/top"

            # 将数据转换为 JSON 格式
            data = {'random_count': limit}

            # 设置请求头为 application/json
            headers = {'Content-Type': 'application/json'}

            # 发送 POST 请求
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == 200:
                track_data = response.json()  # 返回曲目数据
                if not track_data or 'Items' not in track_data or len(track_data['Items']) == 0:
                    logger.warning("API返回的曲目数据无效或为空")
                    return
                # 设置自定义响应
                flow.response = self.create_response(track_data)
                logger.info(f"自定义随机生成 {limit} 首曲目成功")
            else:
                logger.error(f"API 请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"调用 API 时发生错误: {e}", exc_info=True)
            return None    

    def process_genres_request(self, flow: http.HTTPFlow):
        """
        处理风格类型请求，并返回自定义响应
        """
        try:
            headers = {'accept': 'application/json'}
            params = {
                'StartIndex': '0',
                'Recursive': 'true',
                'SortOrder': 'Ascending',
                'ParentId': '37197',
                'IncludeItemTypes': 'MusicAlbum',
                'SortBy': 'SortName',
                'UserId': EMBY_USER_ID,
                'api_key': EMBY_API_KEY,
            }

            response = requests.get(
                f"{EMBY_SERVER_URL}/emby/Genres",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            # 设置自定义响应
            flow.response = self.create_response(response.json())
            logger.info("返回自定义风格类型成功")

        except requests.exceptions.RequestException as e:
            logger.error(f"请求 Genres 数据失败: {e}")

    def process_id_replacement(self, flow: http.HTTPFlow, url_path: str):
        """
        处理 ID 替换逻辑
        """
        try:
            original_id = url_path.split('/')[2]
            new_id = self.get_new_id_from_database(original_id)
            if new_id:
                flow.request.url = flow.request.pretty_url.replace(original_id, new_id)
                logger.info(f"已将请求中的 albumid {original_id} 替换为 trackid {new_id}")
            else:
                logger.warning(f"未能从数据库中找到对应的替换 ID，保持原始 ID {original_id} 不变")

        except Exception as e:
            logger.error(f"处理 ID 替换时发生错误: {e}", exc_info=True)

    def get_new_id_from_database(self, album_id):
        """
        从数据库中查询替换后的 ID
        """
        try:
            # 过滤掉无效的 album_id
            if not album_id or album_id.lower() == "null":
                logger.warning(f"无效的 album_id: {album_id}，跳过查询")
                return None

            conn = emby.Emby().Connect_To_EmbyDB()
            with conn:
                cursor = conn.cursor()
                query = "SELECT id FROM track_list_info WHERE albumid = %s"
                cursor.execute(query, (album_id,))
                result = cursor.fetchone()
            return str(result[0]) if result else None
        except Exception as e:
            logger.error(f"查询数据库失败，album_id: {album_id}, 错误信息: {e}", exc_info=True)
            return None

    @staticmethod
    def create_response(data, content_type="application/json", status=200):
        """
        创建自定义 HTTP 响应
        """
        return http.Response.make(
            status,
            json.dumps(data) if isinstance(data, dict) else data,
            {"Content-Type": content_type}
        )


# 初始化处理器实例
handler = EmbyProxyHandler()

def request(flow: http.HTTPFlow):
    """
    mitmproxy 主函数，拦截 HTTP 请求并调用处理逻辑
    """
    handler.handle_emby_request(flow)