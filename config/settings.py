import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_env_variable(key, default=None, required=False):
    """
    获取环境变量的值。如果变量未设置且为必需，则抛出异常。
    :param key: 环境变量的名称
    :param default: 默认值（如果未设置且非必需）
    :param required: 是否为必需变量
    :return: 环境变量的值
    """
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"环境变量 {key} 未设置，但它是必需的。")
    return value

# Emby 配置
EMBY_SERVER_URL = get_env_variable("EMBY_SERVER_URL", "http://localhost:8096", required=True)
EMBY_USER_ID = get_env_variable("EMBY_USER_ID", required=True)
EMBY_API_KEY = get_env_variable("EMBY_API_KEY", required=True)

# Redis 配置
REDIS_HOST = get_env_variable("REDIS_HOST", "localhost")
REDIS_PORT = int(get_env_variable("REDIS_PORT", 6379))
REDIS_DB = int(get_env_variable("REDIS_DB", 0))
REDIS_CACHE_DURATION_TRACKS = int(get_env_variable("CACHE_DURATION_TRACKS", 604800))  # 默认缓存 7 天

# 数据库配置
DB_NAME = get_env_variable("DB_NAME", "embydb_utf8")
DB_USER = get_env_variable("DB_USER", "embyuser")
DB_PASSWORD = get_env_variable("DB_PASSWORD", required=True)
DB_HOST = get_env_variable("DB_HOST", "localhost")
DB_PORT = int(get_env_variable("DB_PORT", 5432))

# 日志配置
LOG_DIR = get_env_variable("LOG_DIR", "/home/hd/PythonProject/EmbyProject/logs")

# Bark 通知配置
BARK_KEY = get_env_variable("BARK_KEY", "")

# Flask 配置
FLASK_API_HOST = get_env_variable("FLASK_API_HOST", "0.0.0.0")
FLASK_API_PORT = int(get_env_variable("FLASK_API_PORT", 5555))
FLASK_LRC_PORT = int(get_env_variable("FLASK_LRC_PORT", 51232))
FLASK_DEBUG = get_env_variable("FLASK_DEBUG", "False").lower() == "true"

# mitmproxy 配置
MITMPROXY_SCRIPT = get_env_variable("MITMPROXY_SCRIPT", "/home/hd/PythonProject/EmbyProject/app/mitmproxy.py")
MITMPROXY_PORT = int(get_env_variable("MITMPROXY_PORT", 8088))