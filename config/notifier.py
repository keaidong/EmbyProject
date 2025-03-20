import os
import logging
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Notifier:
    def __init__(self, bark_key=None):
        self.bark_key = bark_key or os.getenv("BARK_KEY")

    def send_bark_notification(self, title, content):
        """发送 Bark 通知"""
        if not self.bark_key:
            logging.error("未配置 Bark 的 app_key")
            return False

        url = f"http://192.168.2.40:8080/{self.bark_key}/"
        data = {"title": title, "body": content}
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                logging.info("Bark 通知发送成功")
                return True
            else:
                logging.error(f"Bark 通知发送失败: {response.text}")
                return False
        except Exception as e:
            logging.error(f"发送 Bark 通知失败: {e}")
            return False


class NotificationHandler(logging.Handler):
    """自定义日志处理器: 捕获 WARNING 和 ERROR 级别日志并发送通知"""

    def __init__(self, send_key=None, bark_key=None):
        super().__init__()
        self.notifier = Notifier(bark_key=bark_key)

    def emit(self, record):
        try:
            log_message = self.format(record)
            if record.levelno >= logging.ERROR:
                title = f"日志告警 - {record.levelname}"
                content = f"**日志级别:** {record.levelname}\n**位置:** {record.pathname}:{record.lineno}\n**消息:** {log_message}"

                # 发送 Bark 通知
                self.notifier.send_bark_notification(title, content)
        except Exception as e:
            logging.error(f"日志处理器异常: {e}")