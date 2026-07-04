# LingXi Chat Backend

项目根目录只保留两个源码目录：

- `frontend/`：基于 Chainlit 2.11.1 React 前端源码二开，包含聊天界面、登录页、人设选择、排行榜和管理后台。
- `backend/`：基于 Chainlit 2.11.1 Python 后端源码二开，包含 Chainlit 服务端、LingXi 业务 API、Coze 调用、数据库初始化和部署文件。

运行时不依赖 PyPI `chainlit` 包。后端通过当前目录下的 `chainlit/` 源码启动：

```powershell
cd backend
pip install -r requirements.txt
python init_db.py
python -m chainlit run app.py --host 0.0.0.0 --port 8000
```

前端通过源码启动：

```powershell
cd frontend
$env:CYPRESS_INSTALL_BINARY = "0"
pnpm install
pnpm run build
pnpm dev --host 0.0.0.0 --port 5173
```

本地开发时，前端 Vite 服务会把 `/api`、`/v1`、`/project`、`/auth`、`/ws` 等请求代理到 `http://127.0.0.1:8000`。

Docker 部署在 `backend/` 目录执行：

```bash
cd backend
docker compose up --build -d
```

数据库加载路径：

1. `LINGXI_DB_PATH` 环境变量。
2. `/app/data/chainlit.db`，兼容容器路径。
3. `data/chainlit.db`，当前后端目录的默认路径。
4. `.chainlit/chainlit.db`，兼容旧本地路径。

当前保留的主数据库位于 `backend/data/chainlit.db`。旧根目录 `chainlit.db` 已保留为 `backend/data/legacy-root-chainlit.db`，不会被默认加载。

Coze OAuth 已移除。应用只使用 `COZE_JWT_TOKEN` / Service Identity Token 调用 Coze，旧数据库中的 OAuth 配置键会被忽略。
