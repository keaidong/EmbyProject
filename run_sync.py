from app.sync_data_to_database import SyncDataToDatabase
from config.log_config import get_logger


# 创建独立的日志记录器
logger = get_logger("run_sync", "run_sync.log")

if __name__ == "__main__":
    syncer = None
    try:
        logger.info("=== 开始数据同步任务 ===")
        syncer = SyncDataToDatabase()

        logger.info("开始同步列表信息...")
        syncer.sync_track_list()

        logger.info("开始同步详细信息...")
        syncer.sync_track_details()

        logger.info("=== 数据同步成功完成 ===")
    except Exception as e:
        logger.error("!!! 同步任务失败: %s", str(e), exc_info=True)
    finally:
        if syncer and syncer.db_conn:
            syncer.db_conn.close()
            logger.info("数据库连接已关闭")