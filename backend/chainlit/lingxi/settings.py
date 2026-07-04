"""Runtime settings helpers for the LingXi Chainlit app."""

import os
from pathlib import Path
from typing import Set


ACTIVE_CONFIG_KEYS: Set[str] = {
    "COZE_BOT_ID",
    "COZE_BOT_ID_NOVICE",
    "COZE_BOT_ID_DEBATE",
    "COZE_BOT_ID_EXPERT",
    "COZE_JWT_TOKEN",
    "COZE_JWT_EXPIRES_AT",
    "COZE_BASE_URL",
}


def resolve_db_path() -> str:
    """Resolve the SQLite path for Docker and local development."""
    backend_dir = Path(__file__).resolve().parents[2]
    backend_data_db = backend_dir / "data" / "chainlit.db"

    explicit_path = os.getenv("LINGXI_DB_PATH")
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = backend_dir / path
        return str(path)

    docker_backend_db = Path("/app/backend/data/chainlit.db")
    docker_backend_dir = docker_backend_db.parent
    if docker_backend_db.exists() or docker_backend_dir.exists():
        return str(docker_backend_db)

    legacy_docker_db = Path("/app/data/chainlit.db")
    legacy_docker_dir = legacy_docker_db.parent
    if legacy_docker_db.exists() or legacy_docker_dir.exists():
        return str(legacy_docker_db)

    if backend_data_db.exists() or backend_data_db.parent.exists():
        return str(backend_data_db)

    legacy_chainlit_db = backend_dir / ".chainlit" / "chainlit.db"
    if legacy_chainlit_db.exists():
        return str(legacy_chainlit_db)

    return str(backend_data_db)
