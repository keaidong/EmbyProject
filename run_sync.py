from app.sync_data_to_database import SyncDataToDatabase
from config.log_config import setup_logging
import logging

# 配置日志
setup_logging(log_file_name="/home/hd/PythonProject/EmbyProject/logs/sync_data_to_database.log", log_level=logging.INFO)

if __name__ == "__main__":
    syncer = None
    try:
        logging.info("=== 开始数据同步任务 ===")
        syncer = SyncDataToDatabase()

        logging.info("开始同步列表信息...")
        syncer.sync_track_list()

        logging.info("开始同步详细信息...")
        syncer.sync_track_details()

        logging.info("=== 数据同步成功完成 ===")
    except Exception as e:
        logging.error("!!! 同步任务失败: %s", str(e), exc_info=True)
    finally:
        if syncer and syncer.db_conn:
            syncer.db_conn.close()
            logging.info("数据库连接已关闭")