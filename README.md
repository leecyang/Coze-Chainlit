# LingXi Chat

LingXi Chat is a customized Chainlit 2.11.1 application for computer network learning. The repository is split into a React/Vite frontend and a Python Chainlit/FastAPI backend.

## Features

- Chainlit chat UI with password authentication.
- Three learning personas: `新手小白`, `辩论对手`, `计网专家`.
- Coze Bot integration through Service Identity Token.
- Admin console at `/admin` for users, configuration, conversations, activity stats, and leaderboard data.
- Daily practice and assignment score APIs backed by SQLite.
- Docker Compose deployment with persistent database storage.

## Project Layout

```text
.
├── backend/                 # Chainlit backend source and LingXi API implementation
│   ├── app.py               # Chainlit entrypoint
│   ├── chainlit/            # Local Chainlit source tree plus LingXi customizations
│   ├── init_db.py           # Idempotent SQLite initialization and migrations
│   ├── Dockerfile           # Production image, builds frontend assets first
│   └── docker-compose.yml   # Backend-directory compose entrypoint
├── frontend/                # React/Vite Chainlit frontend source
│   ├── src/
│   ├── libs/react-client/
│   └── libs/copilot/
├── docker-compose.yml       # Root deployment entrypoint
├── .env.example             # Deployment environment template
└── .dockerignore            # Docker build context exclusions
```

The backend does not depend on the PyPI `chainlit` package at runtime. It starts from the local `backend/chainlit/` source tree.

## Local Development

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_db.py
python -m chainlit run app.py --host 0.0.0.0 --port 8000
```

### Frontend

```powershell
cd frontend
$env:CYPRESS_INSTALL_BINARY = "0"
corepack enable
corepack prepare pnpm@9.15.9 --activate
pnpm install
pnpm dev --host 0.0.0.0 --port 5173
```

The Vite dev server proxies `/api`, `/auth`, `/config`, `/project`, `/public`, `/user`, `/v1`, and `/ws` to `http://127.0.0.1:8000`.

## Docker Compose Deployment

1. Create deployment environment values:

```bash
cp .env.example .env
```

2. Edit `.env` and set at least:

```env
CHAINLIT_AUTH_SECRET=replace-with-a-long-random-secret
ADMIN_PASSWORD=replace-with-a-strong-password
```

3. Build and start:

```bash
docker compose up --build -d
docker compose logs -f lingxi-backend
```

The service is exposed at `http://localhost:8123` by default.

Persistent SQLite data is stored in `./backend/data` and mounted into the container at `/app/backend/data`. The application uses `LINGXI_DB_PATH=/app/backend/data/chainlit.db` in Docker.

You can also deploy with the helper script:

```bash
chmod +x deploy.sh
./deploy.sh
```

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CHAINLIT_AUTH_SECRET` | Yes | none | Secret used for Chainlit auth cookies and JWTs. |
| `ADMIN_USERNAME` | No | `admin` | Admin account ensured during startup. |
| `ADMIN_PASSWORD` | Yes | none | Admin password ensured during startup. |
| `COZE_BASE_URL` | No | `https://api.coze.cn` | Coze API base URL. |
| `COZE_BOT_ID` | For chat | empty | Coze Bot ID. |
| `COZE_JWT_TOKEN` | For chat | empty | Coze Service Identity Token. |
| `COZE_JWT_EXPIRES_AT` | No | empty | Unix timestamp for service token expiry. |
| `LINGXI_DB_PATH` | No | Docker compose sets it | SQLite database path. |

Coze settings can also be configured by an administrator from `/admin`. Runtime values are stored in the SQLite `app_config` table.

## Useful Commands

```bash
# Build the production image
docker compose build

# Start in the background
docker compose up -d

# Follow backend logs
docker compose logs -f lingxi-backend

# Stop containers
docker compose down

# Recreate database tables locally
cd backend && python init_db.py
```

## Notes Before Pushing

- Do not commit `.env`, `backend/.env`, SQLite databases, local virtual environments, `node_modules`, or build output.
- Keep secrets out of `docker-compose.yml`; use `.env` for deployment values.
- The root compose file is the preferred production entrypoint. `backend/docker-compose.yml` is kept for compatibility when running from the backend directory.
