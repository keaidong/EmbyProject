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
    logger.error("环境变量未正确配置，请检查 config/settings.py 或 .env 文件")
    raise ValueError("环境变量未正确配置")


class EmbyProxyHandler:
    def __init__(self):

        self.client_emby = emby.Emby().login()
        if not self.client_emby:
            logger.error("登录失败，程序退出")
            return
        
        self.db_conn = emby.Emby().Connect_To_EmbyDB()
        if not self.db_conn:
            logger.error("连接数据库失败，程序退出")
            return

    def _get_limit_from_query(self, query_dict):
        """
        从查询参数中获取 Limit 值
        """
        limit_str = query_dict.get("Limit", [None])[0]
        try:
            return int(limit_str) if limit_str else None
        except ValueError:
            logger.warning(f"无效的 Limit 参数值: {limit_str}")
            return None

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

                # 曲目类请求
                if 'Audio' in include_item_types:
                    if 'Random' in sort_by and limit in [50, 100]:
                        logger.info(f"拦截到【每日推荐】请求，Limit: {limit}")
                        self.process_items_request_average(flow, limit)
                    elif 'Random' in sort_by and limit == 500:
                        logger.info(f"拦截到【随便听听】请求，Limit: {limit}")
                        self.process_items_request_weight(flow, limit)
                    elif 'PlayCount' in sort_by and limit == 20:
                        logger.info(f"拦截到【最常播放】请求，Limit: {limit}")
                        self.process_items_request_top(flow, limit)
                    elif 'DatePlayed' in sort_by and limit == 20:
                        logger.info(f"拦截到【最近播放】请求，Limit: {limit}")
                        flow.request.url = flow.request.url.replace("SortOrder=Descending", "SortOrder=Ascending")
                        logger.info(f"拦截到【最近播放】请求，Limit: {limit} >>> 按播放日期升序")

                # 2. 专辑类
                if 'MusicAlbum' in include_item_types:
                    pass
                    
            # 处理风格类型请求
            elif flow.request.pretty_url.startswith(f"{EMBY_SERVER_URL}/Genres"):
                logger.info("拦截到 ¶ 风格类型⁋ 请求")
                self.process_genres_request(flow)

            # 处理封面请求（ID 替换）
            elif url_path.startswith("/Items/") and "Images/Primary" in url_path:
                if query_dict.get("tag", [None])[0] == "null":
                    logger.info("拦截到 ◩ 封面请求◪")
                    self.process_id_replacement(flow, url_path)
            
            elif flow.request.method == "POST" and url_path.endswith("/Sessions/Playing"):
                logger.info("拦截到 /Sessions/Playing 请求")
                try:
                    # 获取请求数据
                    request_data = json.loads(flow.request.text) if flow.request.text else {}
                    item_id = request_data.get("ItemId")
                    # 伪造成功响应，返回 200 但不含有效播放数据，使 Emby 忽略统计
                    flow.response = http.Response.make(
                        200,
                        b"{}",  # 返回空的JSON
                        {"Content-Type": "application/json"}
                    )
                    logger.info(f"拦截到 /Sessions/Playing 请求 >>> 已阻止曲目 {item_id} 标记为已播放")
                except Exception as e:
                    logger.error(f"处理失败: {e}")

            elif flow.request.method == "POST" and url_path.endswith("/Sessions/Playing/Stopped"):
                logger.info("拦截到 /Sessions/Playing/Stopped 请求")
                try:
                    # 获取请求数据
                    request_data = json.loads(flow.request.text) if flow.request.text else {}
                    item_id = request_data.get("ItemId")

                    if item_id:
                        self.client_emby.make_item_played(item_id)
                        logger.info(f"拦截到 /Sessions/Playing/Stopped 请求 >>> 曲目 {item_id} 标记为已播放且播放次数+1")
                    else:
                        logger.warning("请求中未找到 ItemId")

                except json.JSONDecodeError as e:
                    logger.error(f"解析请求数据失败: {e}")
                except Exception as e:
                    logger.error(f"处理失败: {e}")

        except ValueError as e:
            logger.error(f"值错误: {e}, 请求 URL: {flow.request.pretty_url}", exc_info=True)
        except Exception as e:
            logger.error(f"未知错误: {e}, 请求 URL: {flow.request.pretty_url}", exc_info=True)

    def process_items_request(self, flow: http.HTTPFlow, url: str, data: dict, log_message: str):
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code == 200:
                track_data = response.json()
                if not track_data or 'Items' not in track_data or len(track_data['Items']) == 0:
                    logger.warning(f"API返回的曲目数据无效或为空: 【{log_message}】")
                    return
                flow.response = self.create_response(track_data)
                logger.info(f"{log_message}")
            else:
                logger.error(f"API 请求失败，状态码: {response.status_code}, {log_message}")
        except Exception as e:
            logger.error(f"调用 API 时发生错误: {e}, {log_message}", exc_info=True)

    def process_items_request_average(self, flow: http.HTTPFlow, limit: int):
        self.process_items_request(flow, "http://192.168.2.40:5555/average", {'random_count': limit}, f"拦截到【每日推荐】请求，Limit: {limit} >>> 按曲目风格平均分配")

    def process_items_request_weight(self, flow: http.HTTPFlow, limit: int):
        self.process_items_request(flow, "http://192.168.2.40:5555/weight", {'random_count': limit}, f"拦截到【随便听听】请求，Limit: {limit} >>> 按曲目风格权重分配")

    def process_items_request_top(self, flow: http.HTTPFlow, limit: int):
        self.process_items_request(flow, "http://192.168.2.40:5555/top", {'top_count': limit}, f"拦截到【最常播放】请求，Limit: {limit} >>> 最常播放")

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
            logger.info(f"拦截到 ¶ 风格类型⁋ 请求 >>> 自定义 ¶ 风格类型⁋ 成功")

        except requests.exceptions.RequestException as e:
            logger.error(f"拦截到 ¶ 风格类型⁋ 请求 >>> 请求 ¶ 风格类型⁋ 数据失败: {e}")

    def process_id_replacement(self, flow: http.HTTPFlow, url_path: str):
        """
        处理 ID 替换逻辑
        """
        try:
            original_id = url_path.split('/')[2]
            new_id = self.get_new_id_from_database(original_id)
            if new_id:
                flow.request.url = flow.request.pretty_url.replace(original_id, new_id)
                logger.info(f"拦截到 ◩ 封面请求◪ >>> 专辑 {original_id} 封面已替换为 {new_id}")
            else:
                logger.warning(f"拦截到 ◩ 封面请求◪ >>> 未能从数据库中找到对应的替换 ID，保持原始 ID {original_id} 不变")

        except Exception as e:
            logger.error(f"处理 ID 替换时发生错误: {e}", exc_info=True)

    def get_new_id_from_database(self, album_id):
        """
        从数据库中查询替换后的 ID
        """
        try:
            if not album_id or album_id.lower() == "null":
                logger.warning(f"无效的 album_id: {album_id}，跳过查询")
                return None

            with self.db_conn as conn:
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