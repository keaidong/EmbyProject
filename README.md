# EmbyProject

## 项目简介
EmbyProject 是一个基于 Flask 和 Python 的项目，用于管理 Emby 播放记录、生成播放列表、处理歌词以及通过代理拦截和修改 Emby 的 HTTP 请求。

该项目支持以下功能：
- 监听 Emby 播放状态并记录到数据库。
- 提供 API 接口生成加权分发和平均分发的播放列表。
- 搜索、下载和解析歌词。
- 使用 `mitmproxy` 拦截 Emby 的 HTTP 请求并自定义响应。

---

## 功能模块
### **1. 播放记录管理**
- 监听 Emby 播放状态。
- 将播放记录存储到数据库中，支持后续分析和查询。

### **2. 播放列表生成**
- 提供 Flask API 接口，支持以下两种分发方式：
  - **加权分发**：根据用户偏好生成播放列表。
  - **平均分发**：随机生成播放列表。

### **3. 歌词处理**
- 搜索本地歌词文件。
- 支持歌词的模糊匹配和解析。

### **4. HTTP 请求拦截**
- 使用 `mitmproxy` 拦截 Emby 的 HTTP 请求。
- 自定义响应内容，例如修改曲目列表或封面信息。

---

## 安装步骤

### **1. 克隆项目**
```bash
git clone https://github.com/<your-username>/EmbyProject.git
cd EmbyProject
```

### **2. 创建虚拟环境并安装依赖**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### **3. 配置环境变量**
1. 复制 `.env.example` 文件为 `.env`：
   ```bash
   cp .env.example .env
   ```
2. 根据实际情况填写 `.env` 文件中的配置项，例如 Emby 服务器地址、数据库配置等。

### **4. 启动项目**
运行以下命令启动项目：
```bash
python run.py
```

---

## 环境变量配置
请在项目根目录下创建 `.env` 文件，并填写以下内容：

```properties
# Emby 服务器相关配置
EMBY_SERVER_URL=http://your-emby-server:8096
EMBY_USER_ID=your-emby-user-id
EMBY_API_KEY=your-emby-api-key

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 数据库配置
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=5432

# 日志配置
LOG_DIR=/path/to/logs

# Bark 通知配置
BARK_KEY=your-bark-key

# Flask 配置
FLASK_API_HOST=0.0.0.0
FLASK_API_PORT=5555
FLASK_LRC_PORT=51232
FLASK_DEBUG=False

# mitmproxy 配置
MITMPROXY_SCRIPT=/path/to/mitmproxy.py
MITMPROXY_PORT=8088
```

---

## 项目结构
```
EmbyProject/
├── app/                        # 核心应用逻辑
│   ├── api.py                  # 播放列表生成 API
│   ├── session.py              # Emby 会话管理
│   ├── lrc.py                  # 歌词处理逻辑
│   ├── sync_data_to_database.py # 数据同步逻辑
│   ├── emby.py                 # Emby 客户端封装
│   ├── mitmproxy.py            # HTTP 代理逻辑
├── config/                     # 配置模块
│   ├── log_config.py           # 日志配置
│   ├── notifier.py             # 通知功能封装
│   ├── settings.py             # 全局配置
├── tests/                      # 测试模块
│   ├── test_api.py             # API 测试
│   ├── test_session.py         # 会话管理测试
│   ├── test_emby.py            # Emby 客户端测试
├── logs/                       # 日志文件目录
├── .env                        # 环境变量配置
├── requirements.txt            # 项目依赖
├── README.md                   # 项目说明文档
└── run.py                      # 项目入口
```

---

## 常见问题

### **1. 如何生成播放列表？**
通过 Flask 提供的 API 接口，可以生成加权分发或平均分发的播放列表：
- **加权分发**：根据用户偏好生成播放列表。
- **平均分发**：随机生成播放列表。

### **2. 如何配置 mitmproxy？**
确保已安装 `mitmproxy`，并在 `.env` 文件中正确配置 `MITMPROXY_SCRIPT` 和 `MITMPROXY_PORT`。

### **3. 如何处理歌词？**
项目支持本地歌词搜索和模糊匹配，具体逻辑在 `app/lrc.py` 中实现。

---

## 许可证
此项目使用 [MIT License](LICENSE)。

