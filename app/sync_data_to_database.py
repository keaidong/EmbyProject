import psycopg2
from openai import max_retries
from app import emby
import json
from config.log_config import get_logger
import traceback
from tqdm import tqdm
from psycopg2.extras import execute_batch
from psycopg2 import sql
import time

# 创建独立的日志记录器
logger = get_logger("app.sync_data_to_database", "sync_data_to_database.log")

class SyncDataToDatabase:
    def __init__(self):
        self.client_emby = None
        self.db_conn = None
        self.track_list = []

        try:
            # 初始化Emby连接
            self._init_emby()
            # 初始化数据库连接
            self._init_db()
            # 预加载曲目数据
            self._load_track_list()
        except Exception as e:
            logger.error("初始化失败: %s", str(e))
            raise

    def _init_emby(self):
        """初始化Emby客户端连接"""
        try:
            self.client_emby = emby.Emby().login()
            if not self.client_emby:
                raise Exception("Emby API连接失败")
            logger.info("Emby连接成功")
        except Exception as e:
            logger.error("Emby初始化错误: %s", str(e))
            raise

    def _init_db(self):
        """初始化数据库连接"""
        try:
            self.db_conn = emby.Emby().Connect_To_EmbyDB()
            if not self.db_conn or self.db_conn.closed:
                raise Exception("数据库连接失败")
            logger.info("数据库连接成功")
        except psycopg2.Error as e:
            logger.error("数据库连接错误: %s", str(e))
            raise

    def _load_track_list(self):
        """加载曲目列表并验证数据"""
        try:
            response = self.client_emby.Get_Tracks()
            if not response or not isinstance(response, list):
                raise Exception("无效的API响应")

            self.track_list = response
            if not self.track_list:
                logger.warning("API返回空曲目列表")

            logger.info("获取到%d条曲目数据", len(self.track_list))
            # 验证ID有效性
            invalid_tracks = [t for t in self.track_list if not t.get('Id')]
            if invalid_tracks:
                logger.warning("发现%d条无效ID记录", len(invalid_tracks))
        except Exception as e:
            logger.error("数据加载失败: %s", str(e))
            raise

    def _prepare_track_data(self, track):
        """处理列表信息数据结构"""
        try:
            return (
                track.get('Name'),
                track.get('ServerId'),
                track.get('Id'),
                track.get('DateCreated'),
                track.get('Container'),
                track.get('SortName'),
                track.get('RunTimeTicks'),
                track.get('Size'),
                track.get('Bitrate'),
                track.get('ProductionYear'),
                track.get('IsFolder'),
                track.get('Type'),
                '{' + ','.join([f'"{artist}"' for artist in track.get('Artists', [])]) + '}',
                json.dumps(track.get('Composers', [])),
                track.get('Album'),
                track.get('AlbumId'),
                track.get('AlbumArtist'),
                json.dumps(track.get('ImageTags', {})),
                '{' + ','.join([f'"{tag}"' for tag in track.get('BackdropImageTags', [])]) + '}',
                track.get('MediaType'),
                json.dumps(track.get('MediaSources', []), ensure_ascii=False),
                json.dumps(track.get('UserData', []), ensure_ascii=False),
                json.dumps(track.get('ArtistItems', []), ensure_ascii=False),
                json.dumps(track.get('AlbumArtists', []), ensure_ascii=False)
            )
        except Exception as e:
            logger.error("列表数据处理失败: %s\n数据: %s", str(e), str(track)[:200])
            raise

    def _prepare_detail_data(self, track_id):
        """处理详情信息数据结构"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                detail = self.client_emby.Get_Track_info(track_id)
                if detail:
                    return (
                        detail.get('Album', ''),
                        detail.get('AlbumArtist', ''),
                        json.dumps(detail.get('AlbumArtists', []), ensure_ascii=False),
                        detail.get('AlbumId', ''),
                        json.dumps(detail.get('ArtistItems', []), ensure_ascii=False),
                        json.dumps(detail.get('Artists', []), ensure_ascii=False),
                        json.dumps(detail.get('BackdropImageTags', []), ensure_ascii=False),
                        detail.get('Bitrate', 0) or 0,
                        bool(detail.get('CanDelete', False)),
                        bool(detail.get('CanDownload', False)),
                        json.dumps(detail.get('Composers', []), ensure_ascii=False),
                        detail.get('Container', ''),
                        detail.get('DateCreated', ''),
                        detail.get('DisplayPreferencesId', ''),
                        detail.get('Etag', ''),
                        json.dumps(detail.get('ExternalUrls', []), ensure_ascii=False),
                        detail.get('FileName', ''),
                        detail.get('ForcedSortName', ''),
                        json.dumps(detail.get('GenreItems', []), ensure_ascii=False),
                        json.dumps(detail.get('Genres', []), ensure_ascii=False),
                        detail.get('Id', ''),
                        json.dumps(detail.get('ImageTags', {}), ensure_ascii=False),
                        bool(detail.get('IsFolder', False)),
                        json.dumps(detail.get('LockData', []), ensure_ascii=False),
                        json.dumps(detail.get('LockedFields', []), ensure_ascii=False),
                        json.dumps(detail.get('MediaSources', []), ensure_ascii=False),
                        json.dumps(detail.get('MediaStreams', []), ensure_ascii=False),
                        detail.get('MediaType', ''),
                        detail.get('Name', ''),
                        detail.get('ParentId', ''),
                        detail.get('Path', ''),
                        detail.get('PresentationUniqueKey', ''),
                        detail.get('PrimaryImageAspectRatio', 0.0) or 0.0,
                        detail.get('ProductionYear'),
                        json.dumps(detail.get('ProviderIds', {}), ensure_ascii=False),
                        json.dumps(detail.get('RemoteTrailers', []), ensure_ascii=False),
                        detail.get('RunTimeTicks', 0) or 0,
                        detail.get('ServerId', ''),
                        detail.get('Size', 0) or 0,
                        detail.get('SortName', ''),
                        bool(detail.get('SupportsSync', False)),
                        json.dumps(detail.get('TagItems', []), ensure_ascii=False),
                        json.dumps(detail.get('Taglines', []), ensure_ascii=False),
                        detail.get('Type', ''),
                        json.dumps(detail.get('UserData', {}), ensure_ascii=False)
                    )
                else:
                    logger.warning("未找到详情信息, ID: %s", track_id)
                    return None
            except Exception as e:
                logger.warning("尝试 %d/%d 获取详情失败: %s", attempt + 1, max_retries, str(e))
                time.sleep(1)  # 等待 1 秒后重试
        logger.error("获取详情失败超过最大重试次数, ID: %s", track_id)
        return None

    def _sync_table(self, table_name, query_template, data_generator):
        """通用同步逻辑"""
        try:
            with self.db_conn.cursor() as cursor:
                # 禁用自动提交以启用事务
                self.db_conn.autocommit = False

                # 批量插入数据
                execute_batch(cursor, query_template, data_generator(), page_size=500)
                logger.info("%s 数据插入完成", table_name)

                # 删除失效记录
                current_ids = [t['Id'] for t in self.track_list if t.get('Id')]
                delete_query = sql.SQL("DELETE FROM {} WHERE Id NOT IN %s").format(sql.Identifier(table_name))
                cursor.execute(delete_query, (tuple(current_ids),) if current_ids else (tuple(),))
                logger.info("已清理%d条失效记录", cursor.rowcount)

                # 提交事务
                self.db_conn.commit()
        except psycopg2.Error as e:
            self.db_conn.rollback()
            logger.error("数据库错误: %s\n%s", str(e), traceback.format_exc())
            raise
        finally:
            self.db_conn.autocommit = True

    def sync_track_list(self):
        """同步列表信息"""
        insert_query = """
            INSERT INTO track_list_info (
                Name, ServerId, Id, DateCreated, Container, SortName,
                RunTimeTicks, Size, Bitrate, ProductionYear, IsFolder, Type,
                Artists, Composers, Album, AlbumId, AlbumArtist, ImageTags,
                BackdropImageTags, MediaType, MediaSources, UserData,
                ArtistItems, AlbumArtists
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (Id) DO UPDATE SET
                Name=EXCLUDED.Name,
                ServerId=EXCLUDED.ServerId,
                DateCreated=EXCLUDED.DateCreated,
                Container=EXCLUDED.Container,
                SortName=EXCLUDED.SortName,
                RunTimeTicks=EXCLUDED.RunTimeTicks,
                Size=EXCLUDED.Size,
                Bitrate=EXCLUDED.Bitrate,
                ProductionYear=EXCLUDED.ProductionYear,
                IsFolder=EXCLUDED.IsFolder,
                Type=EXCLUDED.Type,
                Artists=EXCLUDED.Artists,
                Composers=EXCLUDED.Composers,
                Album=EXCLUDED.Album,
                AlbumId=EXCLUDED.AlbumId,
                AlbumArtist=EXCLUDED.AlbumArtist,
                ImageTags=EXCLUDED.ImageTags,
                BackdropImageTags=EXCLUDED.BackdropImageTags,
                MediaType=EXCLUDED.MediaType,
                MediaSources=EXCLUDED.MediaSources,
                UserData=EXCLUDED.UserData,
                ArtistItems=EXCLUDED.ArtistItems,
                AlbumArtists=EXCLUDED.AlbumArtists
        """

        def data_generator():
            with tqdm(self.track_list, desc="生成列表数据", unit="rec") as pbar:
                for track in pbar:
                    if not track.get('Id'):
                        logger.warning("跳过无效ID记录: %s", str(track)[:100])
                        continue
                    yield self._prepare_track_data(track)

        self._sync_table("track_list_info", insert_query, data_generator)

    def sync_track_details(self):
        """同步详细信息"""
        insert_query = """
                            INSERT INTO track_detail_info (
                                album, albumartist, albumartists, albumid, artistitems, artists, 
                                backdropimagetags, bitrate, candelete, candownload, composers, container,
                                datecreated, displaypreferencesid, etag, externalurls, filename, 
                                forcedsortname, genreitems, genres, id, imagetags, isfolder, lockdata, 
                                lockedfields, mediasources, mediastreams, mediatype, name, parentid, path, 
                                presentationuniquekey, primaryimageaspectratio, productionyear, providerids, 
                                remotetrailers, runtimeticks, serverid, size, sortname, supportssync, tagitems,
                                taglines, type, userdata
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                                      %s, %s, %s, %s, %s)
                            ON CONFLICT (Id) DO UPDATE 
                            SET Album = EXCLUDED.Album,
                                AlbumArtist = EXCLUDED.AlbumArtist,
                                AlbumArtists = EXCLUDED.AlbumArtists,
                                AlbumId = EXCLUDED.AlbumId,
                                ArtistItems = EXCLUDED.ArtistItems,
                                Artists = EXCLUDED.Artists,
                                BackdropImageTags = EXCLUDED.BackdropImageTags,
                                Bitrate = EXCLUDED.Bitrate,
                                CanDelete = EXCLUDED.CanDelete,
                                CanDownload = EXCLUDED.CanDownload,
                                Composers = EXCLUDED.Composers,
                                Container = EXCLUDED.Container,
                                DateCreated = EXCLUDED.DateCreated,
                                DisplayPreferencesId = EXCLUDED.DisplayPreferencesId,
                                Etag = EXCLUDED.Etag,
                                ExternalUrls = EXCLUDED.ExternalUrls,
                                FileName = EXCLUDED.FileName,
                                ForcedSortName = EXCLUDED.ForcedSortName,
                                GenreItems = EXCLUDED.GenreItems,
                                Genres = EXCLUDED.Genres,
                                ImageTags = EXCLUDED.ImageTags,
                                IsFolder = EXCLUDED.IsFolder,
                                LockData = EXCLUDED.LockData,
                                LockedFields = EXCLUDED.LockedFields,
                                MediaSources = EXCLUDED.MediaSources,
                                MediaStreams = EXCLUDED.MediaStreams,
                                MediaType = EXCLUDED.MediaType,
                                Name = EXCLUDED.Name,
                                ParentId = EXCLUDED.ParentId,
                                Path = EXCLUDED.Path,
                                PresentationUniqueKey = EXCLUDED.PresentationUniqueKey,
                                PrimaryImageAspectRatio = EXCLUDED.PrimaryImageAspectRatio,
                                ProductionYear = EXCLUDED.ProductionYear,
                                ProviderIds = EXCLUDED.ProviderIds,
                                RemoteTrailers = EXCLUDED.RemoteTrailers,
                                RunTimeTicks = EXCLUDED.RunTimeTicks,
                                ServerId = EXCLUDED.ServerId,
                                Size = EXCLUDED.Size,
                                SortName = EXCLUDED.SortName,
                                SupportsSync = EXCLUDED.SupportsSync,
                                TagItems = EXCLUDED.TagItems,
                                Taglines = EXCLUDED.Taglines,
                                Type = EXCLUDED.Type,
                                UserData = EXCLUDED.UserData;
                        """

        def data_generator():
            track_ids = [t['Id'] for t in self.track_list if t.get('Id')]
            with tqdm(track_ids, desc="生成详情数据", unit="rec") as pbar:
                for track_id in pbar:
                    try:
                        time.sleep(0.02)  # 每次请求之间暂停 0.1 秒，避免过载
                        yield self._prepare_detail_data(track_id)
                    except Exception as e:
                        logger.warning("跳过错误ID: %s 错误: %s", track_id, str(e))
                        continue

        self._sync_table("track_detail_info", insert_query, data_generator)


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
        logger.error("!!! 同步任务失败: %s\n%s", str(e), traceback.format_exc())
    finally:
        if syncer and syncer.db_conn:
            syncer.db_conn.close()
            logger.info("数据库连接已关闭")