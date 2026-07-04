"""Runtime settings helpers for the LingXi Chainlit app."""

import os
from pathlib import Path
from typing import Set


ACTIVE_CONFIG_KEYS: Set[str] = {
    "COZE_BOT_ID",
    "COZE_JWT_TOKEN",
    "COZE_JWT_EXPIRES_AT",
    "COZE_BASE_URL",
}


def resolve_db_path() -> str:
    """Resolve the SQLite path for Docker and local development."""
    explicit_path = os.getenv("LINGXI_DB_PATH")
    if explicit_path:
        return explicit_path
    if os.path.exists("/app/data"):
        return "/app/data/chainlit.db"

    backend_dir = Path(__file__).resolve().parents[2]
    backend_data_db = backend_dir / "data" / "chainlit.db"
    backend_data_dir = backend_dir / "data"
    if backend_data_db.exists():
        return str(backend_data_db)
    if backend_data_dir.exists():
        return str(backend_data_db)

    if os.path.exists("data/chainlit.db"):
        return "data/chainlit.db"
    if os.path.exists("data"):
        return "data/chainlit.db"
    return str(backend_data_db)
