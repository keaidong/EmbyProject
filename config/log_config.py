import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config.notifier import NotificationHandler  # 引入 NotificationHandler

# 加载环境变量
load_dotenv()

def setup_logging(log_file_name, log_level=logging.INFO):
    """
    设置全局日志系统，确保日志目录存在。
    :param log_file_name: 默认日志文件名
    :param log_level: 日志级别，默认为 logging.INFO
    """
    LOG_DIR = os.getenv("LOG_DIR", "/home/hd/PythonProject/EmbyProject/logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, log_file_name)

    # 创建日志记录器
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # 创建文件处理器
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # 创建通知处理器
    bark_key = os.getenv("BARK_KEY")
    notification_handler = NotificationHandler(bark_key=bark_key)
    notification_handler.setLevel(logging.WARNING)
    notification_handler.setFormatter(formatter)

    # 清除重复的处理器
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(notification_handler)

def get_logger(module_name, log_file_name, log_level=logging.INFO):
    """
    为指定模块创建独立的日志记录器。
    :param module_name: 模块名称
    :param log_file_name: 日志文件名
    :param log_level: 日志级别
    :return: 配置好的日志记录器
    """
    LOG_DIR = os.getenv("LOG_DIR", "/home/hd/PythonProject/EmbyProject/logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, log_file_name)

    # 创建日志记录器
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)

    # 创建文件处理器
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # 创建通知处理器
    bark_key = os.getenv("BARK_KEY")
    notification_handler = NotificationHandler(bark_key=bark_key)
    notification_handler.setLevel(logging.WARNING)
    notification_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.handlers.clear()  # 确保不会重复添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(notification_handler)

    return logger