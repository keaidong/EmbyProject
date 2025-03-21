from app.session import Session
import logging

if __name__ == "__main__":
    try:
        logging.info("=== 启动 Emby 项目 ===")

        # 启动播放记录监听
        session = Session()
        if session.client_emby and session.db_conn:
            session.get_session()

    except Exception as e:
        logging.error(f"项目启动失败: {e}")