# LingXi Chat

LingXi Chat 是基于 Chainlit 2.11.1 定制的计算机网络学习应用。本仓库当前维护的是全栈版本，包含 React/Vite 前端和 Python Chainlit/FastAPI 后端。

## 功能特性

- 基于 Chainlit 的聊天界面，支持密码认证。
- 内置三种学习人格：`新手小白`、`辩论对手`、`计网专家`。
- 通过 Service Identity Token 对接 Coze Bot。
- 管理后台位于 `/admin`，用于管理用户、配置、会话、活跃统计和排行榜数据。
- 基于 SQLite 提供每日练习和作业分数 API。
- 支持 Docker Compose 部署，并持久化数据库数据。

## 项目结构

```text
.
├── backend/                 # Chainlit 后端源码和 LingXi API 实现
│   ├── app.py               # Chainlit 入口文件
│   ├── chainlit/            # 本地 Chainlit 源码树及 LingXi 定制内容
│   ├── init_db.py           # 幂等 SQLite 初始化与迁移脚本
│   ├── Dockerfile           # 生产镜像，会先构建前端资源
│   └── docker-compose.yml   # 从 backend 目录启动时使用的 compose 入口
├── frontend/                # React/Vite Chainlit 前端源码
│   ├── src/
│   ├── libs/react-client/
│   └── libs/copilot/
├── docker-compose.yml       # 根目录部署入口
├── .env.example             # 部署环境变量模板
└── .dockerignore            # Docker 构建上下文排除规则
```

后端运行时不依赖 PyPI 上的 `chainlit` 包，而是从本仓库的 `backend/chainlit/` 本地源码树启动。

## 本地开发

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_db.py
python -m chainlit run app.py --host 0.0.0.0 --port 8000
```

### 前端

```powershell
cd frontend
$env:CYPRESS_INSTALL_BINARY = "0"
corepack enable
corepack prepare pnpm@9.15.9 --activate
pnpm install
pnpm dev --host 0.0.0.0 --port 5173
```

Vite 开发服务器会将 `/api`、`/auth`、`/config`、`/project`、`/public`、`/user`、`/v1` 和 `/ws` 代理到 `http://127.0.0.1:8000`。

## Docker Compose 部署

1. 创建部署环境变量文件：

```bash
cp .env.example .env
```

2. 编辑 `.env`，至少设置以下变量：

```env
CHAINLIT_AUTH_SECRET=replace-with-a-long-random-secret
ADMIN_PASSWORD=replace-with-a-strong-password
```

3. 构建并启动服务：

```bash
docker compose up --build -d
docker compose logs -f lingxi-backend
```

默认情况下，服务暴露在 `http://localhost:8123`。

持久化 SQLite 数据存放在 `./backend/data`，并挂载到容器内的 `/app/backend/data`。Docker 环境中应用使用 `LINGXI_DB_PATH=/app/backend/data/chainlit.db`。

也可以使用辅助脚本部署：

```bash
chmod +x deploy.sh
./deploy.sh
```

## 配置项

| 变量 | 是否必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHAINLIT_AUTH_SECRET` | 是 | 无 | 用于 Chainlit 认证 Cookie 和 JWT 的密钥。 |
| `ADMIN_USERNAME` | 否 | `admin` | 启动时确保存在的管理员账号。 |
| `ADMIN_PASSWORD` | 是 | 无 | 启动时确保存在的管理员密码。 |
| `COZE_BASE_URL` | 否 | `https://api.coze.cn` | Coze API 基础地址。 |
| `COZE_BOT_ID` | 聊天功能需要 | 空 | Coze Bot ID。 |
| `COZE_JWT_TOKEN` | 聊天功能需要 | 空 | Coze Service Identity Token。 |
| `COZE_JWT_EXPIRES_AT` | 否 | 空 | 服务 Token 过期时间的 Unix 时间戳。 |
| `LINGXI_DB_PATH` | 否 | Docker Compose 会设置 | SQLite 数据库路径。 |

Coze 配置也可以由管理员在 `/admin` 中维护。运行时配置会保存在 SQLite 的 `app_config` 表中。

## 常用命令

```bash
# 构建生产镜像
docker compose build

# 后台启动
docker compose up -d

# 跟踪后端日志
docker compose logs -f lingxi-backend

# 停止容器
docker compose down

# 本地重建数据库表
cd backend && python init_db.py
```

## 协作与分支

仓库分支定位、fork 和 PR 提交流程请查看 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 推送前注意事项

- 不要提交 `.env`、`backend/.env`、SQLite 数据库、本地虚拟环境、`node_modules` 或构建产物。
- 不要把密钥写入 `docker-compose.yml`，部署配置请放在 `.env` 中。
- 根目录的 `docker-compose.yml` 是推荐的生产部署入口；`backend/docker-compose.yml` 仅保留用于从后端目录启动的兼容场景。
