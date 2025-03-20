import os
import subprocess
from multiprocessing import Process
from config.log_config import get_logger
from app.session import Session
from app.api import app_api
from app.lrc import app_lrc
from config.settings import EMBY_SERVER_URL, FLASK_API_HOST, FLASK_API_PORT, FLASK_LRC_PORT, FLASK_DEBUG, MITMPROXY_SCRIPT, MITMPROXY_PORT

# 创建独立的日志记录器
logger = get_logger("run", "run.log")

def run_app_api():
    app_api.run(host=FLASK_API_HOST, port=FLASK_API_PORT, debug=FLASK_DEBUG)

def run_app_lrc():
    app_lrc.run(host=FLASK_API_HOST, port=FLASK_LRC_PORT, debug=FLASK_DEBUG)

def run_session_listener():
    session = Session()
    if session.client_emby and session.db_conn:
        session.get_session()

def run_mitmproxy():
    """
    启动 mitmdump 作为子进程
    """
    try:
        mitmproxy_command = [
            "mitmdump",
            "--mode", f"reverse:{EMBY_SERVER_URL}",
            "-p", str(MITMPROXY_PORT),
            "-s", MITMPROXY_SCRIPT
        ]
        logger.info(f"启动 mitmdump: {' '.join(mitmproxy_command)}")
        subprocess.run(mitmproxy_command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"mitmdump 启动失败: {e}")
    except FileNotFoundError:
        logger.error("未找到 mitmdump，请确保 mitmproxy 已正确安装")

if __name__ == "__main__":
    try:
        logger.info("=== 启动 Emby 项目 ===")

        # 启动播放记录监听进程
        session_process = Process(target=run_session_listener)
        session_process.start()

        # 启动 Flask API 服务进程
        api_process = Process(target=run_app_api)
        lrc_process = Process(target=run_app_lrc)

        # 启动 mitmdump 进程
        mitmproxy_process = Process(target=run_mitmproxy)
        mitmproxy_process.start()

        api_process.start()
        lrc_process.start()

        # 等待所有进程完成
        session_process.join()
        api_process.join()
        lrc_process.join()
        mitmproxy_process.join()

    except Exception as e:
        logger.error(f"项目启动失败: {e}")