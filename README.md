EmbyProject/
├── app/                        # 核心应用逻辑
│   ├── __init__.py             # 初始化模块
│   ├── api.py                  # 播放列表生成 API
│   ├── emby.py                 # Emby API 封装
│   ├── session.py              # 播放记录管理
│   ├── sync_data_to_database.py # 数据同步到数据库
│   ├── lrc.py                  # 歌词处理服务
│   ├── mitmproxy.py            # mitmproxy 拦截处理
│   └── adjust_lrc_time.py      # 歌词时间调整工具
├── config/                     # 配置文件
│   ├── __init__.py             # 配置初始化
│   ├── log_config.py           # 日志配置
│   ├── notififer .py           # Bark 通知
│   └── settings.py             # 项目配置（如 Redis、数据库等）
├── tests/                      # 测试代码
│   ├── __init__.py             # 测试初始化
│   ├── test_api.py             # 测试播放列表生成 API
│   ├── test_emby.py            # 测试 Emby API 封装
│   ├── test_session.py         # 测试播放记录管理
│   ├── test_sync_data.py       # 测试数据同步
│   ├── test_lrc.py             # 测试歌词处理
│   └── test_mitmproxy.py       # 测试 mitmproxy 拦截
├── logs/                       # 日志文件目录
│   └── (自动生成的日志文件)
├── requirements.txt            # Python 依赖包列表
├── .env                        # 环境变量配置文件
├── README.md                   # 项目说明文档
└── run.py                      # 项目启动入口

文件功能说明
app/
    api.py：
    提供 Flask API，用于生成播放列表（支持平均分发和加权分发）。
    依赖 TrackFilter、TrackGroupByGenre 和 TrackDistributor 类实现核心逻辑。
    emby.py：
    封装 Emby 的 API 调用，包括登录、获取曲目、创建播放列表等功能。
    session.py：
    监听 Emby 播放状态，记录播放进度到数据库。
    支持断线重连和播放记录的插入。
    sync_data_to_database.py：
    同步 Emby 的曲目数据到 PostgreSQL 数据库。
    包括曲目列表和详细信息的同步。
    lrc.py：
    提供歌词搜索、下载、解析和保存功能。
    支持通过网易云音乐 API 获取歌词。
    mitmproxy.py：
    使用 mitmproxy 拦截 Emby 的 HTTP 请求，处理曲目和风格类型请求。
    adjust_lrc_time.py：
    调整 .lrc 歌词文件的时间戳，支持批量处理。

config/
    log_config.py：
    配置日志记录，支持文件日志和 Bark 通知。
    settings.py：
    存储项目的全局配置，如 Redis、数据库连接信息等。

tests/
    包含针对各模块的单元测试，确保功能的正确性。

logs/
存储运行时生成的日志文件。