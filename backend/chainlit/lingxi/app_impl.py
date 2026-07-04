import os
import json
import sqlite3
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

import chainlit as cl
from chainlit.server import app
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadFilter, Pagination
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from chainlit.auth.cookie import get_token_from_cookies
from chainlit.auth.jwt import decode_jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

from .settings import ACTIVE_CONFIG_KEYS, resolve_db_path
from .tokens import build_token_health
from .multi_agent.base import AgentDeps, SESSION_AGENT_CONVERSATIONS, SESSION_AGENT_STATE
from .multi_agent.pipeline import MultiAgentPipeline
from .multi_agent.practice_agent import DailyPracticeAgent

# Load environment variables
load_dotenv()


# Configure data persistence with SQLite.
DB_PATH = resolve_db_path()
print(f"[Database] Using database path: {DB_PATH}")

@cl.data_layer
def get_data_layer():
    # Ensure directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # 注意：数据库由 Chainlit 自动管理，保留历史数据
    return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")



COZE_BOT_ID = os.getenv("COZE_BOT_ID")
COZE_BASE_URL = os.getenv("COZE_BASE_URL", "https://api.coze.cn")

# 多智能体：各教学 Agent 的专属 Coze Bot（留空则回退到 COZE_BOT_ID）
# COZE_BOT_ID 本身保留给每日一练工作流 Bot（Daily_Practice_Agent）
COZE_BOT_ID_NOVICE = os.getenv("COZE_BOT_ID_NOVICE", "")
COZE_BOT_ID_DEBATE = os.getenv("COZE_BOT_ID_DEBATE", "")
COZE_BOT_ID_EXPERT = os.getenv("COZE_BOT_ID_EXPERT", "")

# JWT Service Account Configuration (for production)
COZE_JWT_TOKEN = os.getenv("COZE_JWT_TOKEN")
COZE_JWT_EXPIRES_AT = os.getenv("COZE_JWT_EXPIRES_AT")  # Timestamp when JWT expires

# User data storage
# Format: {username: {"password": str, "role": str}}
users_db: Dict[str, Dict[str, Any]] = {}

# Coze conversation_id -> username mapping
# Used for Coze workflow HTTP callback to resolve username
conversation_user_map: Dict[str, str] = {}  # conversation_id -> username

# Admin credentials (pre-configured)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# Configuration storage for runtime updates
config_storage = {
    "COZE_BOT_ID": COZE_BOT_ID,
    "COZE_BOT_ID_NOVICE": COZE_BOT_ID_NOVICE,
    "COZE_BOT_ID_DEBATE": COZE_BOT_ID_DEBATE,
    "COZE_BOT_ID_EXPERT": COZE_BOT_ID_EXPERT,
    "COZE_JWT_TOKEN": COZE_JWT_TOKEN,
    "COZE_JWT_EXPIRES_AT": COZE_JWT_EXPIRES_AT,
    "COZE_BASE_URL": COZE_BASE_URL,
}

OPTIONAL_AGENT_BOT_KEYS = {
    "COZE_BOT_ID_NOVICE",
    "COZE_BOT_ID_DEBATE",
    "COZE_BOT_ID_EXPERT",
}


def get_agent_bot_id(key: str) -> str:
    """解析某个 Agent 的 Coze Bot ID。

    调用时读取 config_storage（管理后台 PUT /api/admin/config 或 /model
    命令的改动即时生效）；对应键为空时回退到主 COZE_BOT_ID，
    保证未创建专属 Bot 前系统以单 Bot 降级模式照常工作。
    """
    value = (config_storage.get(key) or "").strip()
    if value:
        return value
    return (config_storage.get("COZE_BOT_ID") or "").strip()


# ==================== 用户持久化 ====================
import sqlite3

def _ensure_app_users_table():
    """确保 app_users 表存在（同步方式，仅在启动时使用）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                "username" TEXT PRIMARY KEY,
                "password" TEXT NOT NULL,
                "role" TEXT NOT NULL DEFAULT 'user',
                "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Users] 创建 app_users 表失败: {e}")

def _load_users_from_db():
    """启动时从数据库加载所有持久化用户到内存"""
    _ensure_app_users_table()
    loaded = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT username, password, role FROM app_users')
        for row in cursor:
            username, password, role = row
            users_db[username] = {
                "password": password,
                "role": role,
            }
            loaded += 1
        conn.close()
        print(f"[Users] 从数据库加载了 {loaded} 个用户")
    except Exception as e:
        print(f"[Users] 从数据库加载用户失败: {e}")

def _save_user_to_db(username: str, password: str, role: str):
    """将用户保存/更新到数据库（同步方式，操作极轻量）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO app_users (username, password, role) VALUES (?, ?, ?)',
            (username, password, role)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Users] 保存用户 {username} 到数据库失败: {e}")

def _delete_user_from_db(username: str):
    """从数据库删除用户"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM app_users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Users] 从数据库删除用户 {username} 失败: {e}")

def _update_user_in_db(username: str, **kwargs):
    """更新数据库中用户的指定字段"""
    if not kwargs:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        sets = []
        values = []
        for k, v in kwargs.items():
            sets.append(f'"{k}" = ?')
            values.append(v)
        values.append(username)
        conn.execute(f'UPDATE app_users SET {", ".join(sets)} WHERE username = ?', values)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Users] 更新用户 {username} 失败: {e}")

# 启动时加载用户
_load_users_from_db()

if not users_db:
    # Empty databases bootstrap with the configured admin as the first user.
    users_db[ADMIN_USERNAME] = {
        "password": ADMIN_PASSWORD,
        "role": "admin",
    }
    _save_user_to_db(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
elif ADMIN_USERNAME in users_db:
    users_db[ADMIN_USERNAME] = {
        "password": ADMIN_PASSWORD,
        "role": "admin",
    }
    _save_user_to_db(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
print(f"[Users] 当前共 {len(users_db)} 个用户")

# ==================== 用户偏好风格 ====================
# DEFAULT_PERSONA 保留：仍是 chat_stream 未传 target_role 时的兜底变量值
# （降级单 Bot 模式下旧提示词依赖），也是管理后台会话人设的默认显示。
DEFAULT_PERSONA = "计网专家"
# preferred_style 只是 ResponseSelector 的偏好权重，不再强制指定人设 Agent。
# auto 表示完全交给 Router + Selector 自主决定。
DEFAULT_PREFERRED_STYLE = "auto"
VALID_PREFERRED_STYLES = ("auto", "novice", "debate", "expert")
# 存储每个用户的偏好风格，键为用户名（内存态）
user_preferred_styles: Dict[str, str] = {}


def _ensure_persona_usage_table():
    """确保 persona_usage_logs 表存在"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.execute('''CREATE TABLE IF NOT EXISTS persona_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            persona TEXT NOT NULL,
            thread_id TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )''')
        conn.commit()
        conn.close()
        print("[PersonaUsage] persona_usage_logs 表已就绪")
    except Exception as e:
        print(f"[PersonaUsage] 创建表失败: {e}")

_ensure_persona_usage_table()


def log_persona_usage(username: str, persona: str, thread_id: str = None):
    """记录一次人设使用"""
    if not persona:
        return
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.execute(
            'INSERT INTO persona_usage_logs (username, persona, thread_id) VALUES (?, ?, ?)',
            (username, persona, thread_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[PersonaUsage] 记录失败: {e}")

# ==================== 配置持久化 ====================

def _ensure_app_config_table():
    """确保 app_config 表存在"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                "key" TEXT PRIMARY KEY,
                "value" TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Config] 创建 app_config 表失败: {e}")

def _ensure_activity_logs_table():
    """确保 app_activity_logs 表存在"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(app_activity_logs)")}
        for column, ddl in {
            "actor": "ALTER TABLE app_activity_logs ADD COLUMN actor TEXT",
            "target": "ALTER TABLE app_activity_logs ADD COLUMN target TEXT",
            "detail": "ALTER TABLE app_activity_logs ADD COLUMN detail TEXT",
        }.items():
            if column not in columns:
                conn.execute(ddl)
        # 只保留最近 1000 条记录
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS keep_logs_limit
            AFTER INSERT ON app_activity_logs
            BEGIN
                DELETE FROM app_activity_logs WHERE id NOT IN (
                    SELECT id FROM app_activity_logs ORDER BY id DESC LIMIT 1000
                );
            END;
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Activity Logs] 创建 app_activity_logs 表失败: {e}")

def log_activity(
    username: str,
    action: str,
    actor: Optional[str] = None,
    target: Optional[str] = None,
    detail: Optional[str] = None,
):
    """记录用户活动"""
    try:
        _ensure_activity_logs_table()
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """
            INSERT INTO app_activity_logs (username, action, actor, target, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, action, actor, target or username, detail)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Activity Logs] 记录活动失败: {e}")


def log_admin_activity(actor: str, action: str, target: str = "", detail: str = ""):
    """记录管理后台操作，兼容旧的 app_activity_logs.username 字段。"""
    log_activity(target or actor or "admin", action, actor=actor, target=target, detail=detail)


def _ensure_assignment_records_table():
    """确保作业记录表存在，兼容已部署但未跑最新 init_db.py 的数据库。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignment_records (
                "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                "username" TEXT NOT NULL,
                "score" INTEGER NOT NULL DEFAULT 0,
                "feedback" TEXT NOT NULL DEFAULT '',
                "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_assignment_records_username ON assignment_records("username")')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_assignment_records_created_at ON assignment_records("created_at")')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Assignments] 创建 assignment_records 表失败: {e}")


def _get_pagination(request: Request, default_page_size: int = 20, max_page_size: int = 100) -> Tuple[int, int, int]:
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.query_params.get("page_size", str(default_page_size)))
    except ValueError:
        page_size = default_page_size
    page = max(page, 1)
    page_size = min(max(page_size, 1), max_page_size)
    return page, page_size, (page - 1) * page_size


def _pagination_payload(items: List[Dict[str, Any]], total: int, page: int, page_size: int) -> Dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def _sqlite_dicts(cursor) -> List[Dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def _load_config_from_db():
    """启动时从数据库加载运行时配置覆盖项"""
    global COZE_BOT_ID, COZE_JWT_TOKEN, COZE_JWT_EXPIRES_AT, COZE_BASE_URL
    
    _ensure_app_config_table()
    loaded = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT key, value FROM app_config')
        for row in cursor:
            key, value = row
            if key in ACTIVE_CONFIG_KEYS and (value or key in OPTIONAL_AGENT_BOT_KEYS):
                config_storage[key] = value
                loaded += 1
        conn.close()
        
        # 用数据库中的配置更新全局变量
        if config_storage.get("COZE_BOT_ID"):
            COZE_BOT_ID = config_storage["COZE_BOT_ID"]
        if config_storage.get("COZE_JWT_TOKEN"):
            COZE_JWT_TOKEN = config_storage["COZE_JWT_TOKEN"]
        if config_storage.get("COZE_BASE_URL"):
            COZE_BASE_URL = config_storage["COZE_BASE_URL"]
        
        if loaded:
            print(f"[Config] 从数据库加载了 {loaded} 项运行时配置覆盖")
    except Exception as e:
        print(f"[Config] 从数据库加载配置失败: {e}")

def _save_config_to_db(key: str, value: str):
    """保存单个配置项到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)',
            (key, value or '')
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Config] 保存配置 {key} 失败: {e}")

# 启动时加载配置
_load_config_from_db()
_ensure_activity_logs_table()
_ensure_assignment_records_table()


# ==================== 会话映射持久化 ====================

def _ensure_conversation_map_table():
    """确保 conversation_user_mapping 表存在"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_user_mapping (
                "conversation_id" TEXT PRIMARY KEY,
                "username" TEXT NOT NULL,
                "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ConvMap] 创建 conversation_user_mapping 表失败: {e}")

def _load_conversation_map_from_db():
    """启动时从数据库加载会话映射"""
    _ensure_conversation_map_table()
    loaded = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT conversation_id, username FROM conversation_user_mapping')
        for row in cursor:
            conversation_user_map[row[0]] = row[1]
            loaded += 1
        conn.close()
        if loaded:
            print(f"[ConvMap] 从数据库加载了 {loaded} 条会话映射")
    except Exception as e:
        print(f"[ConvMap] 从数据库加载会话映射失败: {e}")

def _save_conversation_map_to_db(conversation_id: str, username: str):
    """保存会话映射到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO conversation_user_mapping (conversation_id, username) VALUES (?, ?)',
            (conversation_id, username)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ConvMap] 保存会话映射失败: {e}")

# 启动时加载会话映射
_load_conversation_map_from_db()


def verify_user_from_request(request: Request) -> Optional[str]:
    """从 HTTP 请求中提取已登录用户的用户名
    
    通过 Chainlit 的 cookie-based JWT 认证机制提取用户信息。
    
    Returns:
        用户名（已登录）或 None（未登录/验证失败）
    """
    try:
        token = get_token_from_cookies(request.cookies)
        if not token:
            return None
        user = decode_jwt(token)
        return user.identifier
    except Exception as e:
        print(f"[Auth] User verification failed: {e}")
        return None


def verify_admin_from_request(request: Request) -> Optional[str]:
    """从 HTTP 请求中验证管理员身份
    
    通过 Chainlit 的 cookie-based JWT 认证机制提取用户信息，
    验证该用户是否为管理员角色。
    
    Returns:
        管理员用户名（验证通过）或 None（验证失败）
    """
    try:
        token = get_token_from_cookies(request.cookies)
        if not token:
            return None
        user = decode_jwt(token)
        username = user.identifier
        if username in users_db and users_db[username].get("role") == "admin":
            return username
        # 也检查 user.metadata 中的 role（以防用户不在 users_db 中但 JWT 中有角色信息）
        if hasattr(user, 'metadata') and user.metadata and user.metadata.get("role") == "admin":
            return username
        return None
    except Exception as e:
        print(f"[Auth] Admin verification failed: {e}")
        return None


# 中间件：拦截管理后台相关请求
# 原因：Chainlit 的 server.py 最后注册了兜底路由 @router.get("/{full_path:path}")
# 该兜底路由通过 app.include_router(router) 注册，比我们用 @app.get() 定义的路由
# 更早出现在路由列表中，因此 FastAPI 按顺序匹配时，兜底路由会先命中并返回 SPA HTML。
# 中间件在路由匹配之前运行，因此可以在兜底路由生效之前拦截请求。
class AdminRouteMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # 仅拦截 GET 请求（POST/PUT/DELETE 不受兜底路由影响，因为兜底只有 GET）
        if method == "GET" and path == "/api/admin/auth/check":
            admin_username = verify_admin_from_request(request)
            return StarletteJSONResponse({
                "is_admin": admin_username is not None,
                "username": admin_username or ""
            })

        # 拦截 GET /api/preferred-style 请求
        # （Chainlit 兜底路由会遮蔽后注册的自定义 GET 路由，必须在中间件应答）
        if method == "GET" and path == "/api/preferred-style":
            username = verify_user_from_request(request)
            if not username:
                return StarletteJSONResponse({"preferred_style": ""}, status_code=401)
            style = user_preferred_styles.get(username) or DEFAULT_PREFERRED_STYLE
            return StarletteJSONResponse({"preferred_style": style})

        return await call_next(request)

app.add_middleware(AdminRouteMiddleware)



def verify_credentials(username: str, password: str) -> bool:
    """Verify user credentials"""
    if username in users_db:
        return users_db[username]["password"] == password
    return False


def get_user_role(username: str) -> str:
    """Get user role"""
    if username in users_db:
        return users_db[username].get("role", "user")
    return "user"


def get_default_role_for_new_user(requested_role: str = "user") -> str:
    """Make the first persisted application user an administrator by default."""
    if not users_db:
        return "admin"
    return requested_role if requested_role in ("admin", "user") else "user"


def register_user(username: str, password: str, role: str = "user") -> bool:
    """Register a new user"""
    if username in users_db:
        return False
    role = get_default_role_for_new_user(role)
    users_db[username] = {
        "password": password,
        "role": role,
    }
    _save_user_to_db(username, password, role)
    log_activity(username, "注册账号")
    return True


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Handle user authentication"""
    if verify_credentials(username, password):
        role = get_user_role(username)
        # 记录登录活动
        log_activity(username, "用户登录")
        return cl.User(
            identifier=username,
            metadata={"role": role, "provider": "credentials"}
        )
    return None


async def get_system_token() -> Optional[str]:
    """Get system-level Service Identity token
    
    This is used for regular users and as fallback for admins.
    Service Identity token is recommended for production as it's long-term valid.
    """
    global COZE_JWT_TOKEN, COZE_JWT_EXPIRES_AT
    
    # Check Service Identity token
    if COZE_JWT_TOKEN:
        # Check if token is still valid
        if COZE_JWT_EXPIRES_AT:
            try:
                expires_at = int(COZE_JWT_EXPIRES_AT)
                current_time = int(datetime.now().timestamp())
                if current_time < expires_at - 3600:  # 1 hour buffer
                    print(f"[Token] Using Service Identity token (expires in {expires_at - current_time} seconds)")
                    return COZE_JWT_TOKEN
                else:
                    print(f"[Token] Service Identity token expired or expiring soon")
            except (ValueError, TypeError):
                pass
        else:
            # No expiration set, assume valid (permanent token)
            print(f"[Token] Using Service Identity token (permanent)")
            return COZE_JWT_TOKEN
    
    return None


async def get_valid_token(username: str) -> Optional[str]:
    """Get the service identity token used for all Coze API requests."""
    system_token = await get_system_token()
    if system_token:
        return system_token
    
    # Final fallback
    print(f"[Token] Warning: No valid token available!")
    return None


async def check_token_health() -> Dict[str, Any]:
    """Check service identity token health status and return diagnostics."""
    return build_token_health(COZE_JWT_TOKEN, COZE_JWT_EXPIRES_AT)


@app.get("/api/coze/user-info")
async def coze_user_info(conversation_id: str = None):
    """供 Coze 工作流 HTTP 请求节点回调，通过 conversation_id 查询用户名
    
    Usage in Coze workflow HTTP node:
        GET https://your-domain/api/coze/user-info?conversation_id={{conversation_id}}
    """
    if not conversation_id:
        return {"code": -1, "msg": "缺少 conversation_id 参数"}
    
    username = conversation_user_map.get(conversation_id)
    if not username:
        return {"code": -1, "msg": "未找到该会话对应的用户"}
    
    user_data = users_db.get(username, {})
    return {
        "code": 0,
        "data": {
            "username": username,
            "role": user_data.get("role", "user")
        }
    }


class CozeAPI:
    """Coze API Client"""

    def __init__(self, auth_token: str, bot_id: str):
        self.auth_token = auth_token
        self.bot_id = bot_id
        self.base_url = COZE_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate"
        }

    async def create_conversation(self) -> Optional[str]:
        """Create a new conversation"""
        url = f"{self.base_url}/v1/conversation/create"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json={}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            return data.get("data", {}).get("id")
                        else:
                            print(f"[Coze API] Create conversation error: code={data.get('code')}, msg={data.get('msg')}")
                    else:
                        error_text = await response.text()
                        print(f"[Coze API] Create conversation HTTP error: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            print(f"[Coze API] Create conversation network error: {e}")
        except Exception as e:
            print(f"[Coze API] Create conversation exception: {e}")
        return None

    async def create_message(self, conversation_id: str, content: str, role: str = "user") -> Optional[Dict]:
        """Create a message in conversation"""
        url = f"{self.base_url}/v1/conversation/message/create"

        params = {
            "conversation_id": conversation_id
        }

        payload = {
            "role": role,
            "content": content,
            "content_type": "text"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, params=params, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            return data.get("data")
                        else:
                            print(f"[Coze API] Create message error: code={data.get('code')}, msg={data.get('msg')}")
                    else:
                        error_text = await response.text()
                        print(f"[Coze API] Create message HTTP error: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            print(f"[Coze API] Create message network error: {e}")
        except Exception as e:
            print(f"[Coze API] Create message exception: {e}")
        return None

    def _extract_requires_action(self, data: dict) -> dict:
        """从 SSE 事件数据中提取 requires_action 信息
        
        Returns:
            dict 或 None: {chat_id, conversation_id, tool_calls} 或 None
        """
        chat_id = data.get("id")
        real_conversation_id = data.get("conversation_id")
        required_action = data.get("required_action")
        
        if not required_action:
            return None
        
        if isinstance(required_action, dict):
            submit_tool_outputs = required_action.get("submit_tool_outputs", {})
            tool_calls = submit_tool_outputs.get("tool_calls", []) if isinstance(submit_tool_outputs, dict) else []
        else:
            tool_calls = []
        
        if chat_id and tool_calls:
            first_tc = tool_calls[0] if tool_calls else {}
            print(f"[Coze] requires_action: chat_id={chat_id}, "
                  f"type={first_tc.get('type')}, tool_calls={len(tool_calls)}")
            return {
                "chat_id": chat_id,
                "conversation_id": real_conversation_id,
                "tool_calls": tool_calls
            }
        return None

    async def _process_sse_stream(self, response, msg: cl.Message):
        """处理 SSE 流式响应的通用逻辑
        
        支持多 answer 消息自动拆分：当工作流返回多段 answer（如反馈+下一题）时，
        自动将它们拆分为独立的 Chainlit 消息。
        
        Returns:
            (full_content, requires_action_info, final_msg):
              - full_content: 最后一条 answer 消息的完整文本
              - requires_action_info: 工作流挂起信息
              - final_msg: 最终的 Chainlit Message 对象（可能是新创建的）
        """
        full_content = ""
        requires_action_info = None
        current_event = None
        current_answer_id = None  # 跟踪当前 answer 消息 ID，用于多 answer 拆分

        async for line in response.content:
            line = line.decode('utf-8').strip()
            if not line:
                continue

            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)

                    # 顶层错误码
                    if isinstance(data, dict) and data.get("code") != 0 and data.get("code") is not None:
                        print(f"[Coze] Stream error: code={data.get('code')}, msg={data.get('msg')}")
                        return full_content, None, msg

                    # ===== 处理各类事件 =====
                    if current_event == "conversation.message.delta":
                        if isinstance(data, dict) and data.get("content"):
                            delta_msg_id = data.get("id", "")
                            # ★ 多 answer 拆分：检测到新的 answer 消息 ID
                            if (current_answer_id 
                                and delta_msg_id 
                                and delta_msg_id != current_answer_id 
                                and full_content):
                                # 持久化当前消息，创建新消息
                                await self._persist_msg(msg, full_content)
                                msg = cl.Message(content="")
                                await msg.send()
                                full_content = ""
                            if delta_msg_id:
                                current_answer_id = delta_msg_id
                            content_delta = data["content"]
                            full_content += content_delta
                            await msg.stream_token(content_delta)

                    elif current_event == "conversation.message.completed":
                        if isinstance(data, dict) and data.get("type") == "answer":
                            if not full_content and data.get("content"):
                                full_content = data["content"]
                                await msg.stream_token(full_content)

                    elif current_event == "conversation.chat.completed":
                        if isinstance(data, dict):
                            if data.get("status") == "requires_action" and data.get("required_action"):
                                info = self._extract_requires_action(data)
                                if info:
                                    requires_action_info = info

                    elif current_event == "conversation.chat.requires_action":
                        if isinstance(data, dict):
                            info = self._extract_requires_action(data)
                            if info:
                                requires_action_info = info

                    elif current_event == "conversation.chat.failed":
                        if isinstance(data, dict):
                            print(f"[Coze] 对话失败: error={data.get('last_error', {})}")

                    elif current_event == "error":
                        if isinstance(data, dict):
                            print(f"[Coze] Stream error: code={data.get('code')}, "
                                  f"msg={data.get('msg', 'Unknown')}")

                    # 兜底检查
                    if (isinstance(data, dict) 
                        and data.get("status") == "requires_action" 
                        and data.get("required_action")
                        and requires_action_info is None):
                        info = self._extract_requires_action(data)
                        if info:
                            requires_action_info = info

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"[Coze] SSE process error: {e}")

        return full_content, requires_action_info, msg

    async def _persist_msg(self, msg: cl.Message, full_content: str):
        """将流式接收到的消息内容持久化到数据库"""
        if full_content:
            if msg.content != full_content:
                msg.content = full_content
            await msg.update()

    async def chat_stream(self, conversation_id: str, user_id: str, query: str, msg: cl.Message, **kwargs):
        """Start a chat and stream response to the message
        
        Returns:
            dict: {"content": str, "requires_action": dict|None}
                  requires_action 非 None 时表示工作流问答节点挂起
        """
        url = f"{self.base_url}/v3/chat"

        # ★ 关键修复：conversation_id 通过 query params 传递，与官方 SDK 一致
        # SDK 源码: params = {"conversation_id": conversation_id if conversation_id else None}
        params = {}
        if conversation_id:
            params["conversation_id"] = conversation_id

        # 从 kwargs 中获取可选的 target_role，未选择时使用默认人设
        # （练习 Agent 不传该参数，保持发给旧工作流 Bot 的载荷与改造前一致）
        target_role = kwargs.get("target_role", "") or DEFAULT_PERSONA

        custom_vars = {
            "username": user_id,
            "target_role": target_role
        }
        # 教学 Agent 附加的任务上下文变量（task_topic / difficulty 等），
        # Coze 容忍提示词中未声明的 custom_variables
        extra_vars = kwargs.get("extra_vars")
        if extra_vars:
            custom_vars.update(extra_vars)

        payload = {
            "bot_id": self.bot_id,
            "user_id": user_id,
            "additional_messages": [
                {
                    "role": "user",
                    "content": query,
                    "content_type": "text"
                }
            ],
            "stream": True,
            "auto_save_history": True,
            "custom_variables": custom_vars
        }

        result = {"content": None, "requires_action": None}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, params=params, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[Coze] chat_stream HTTP error: {response.status}")
                        return result

                    full_content, requires_action_info, msg = await self._process_sse_stream(response, msg)

        except asyncio.CancelledError:
            await self._persist_msg(msg, msg.content or "")
            raise
        except aiohttp.ClientError as e:
            print(f"[Coze] chat_stream network error: {e}")
            return result
        except Exception as e:
            print(f"[Coze] chat_stream exception: {e}")
            return result

        await self._persist_msg(msg, full_content)

        result["content"] = full_content if full_content else None
        result["requires_action"] = requires_action_info
        return result

    async def submit_tool_outputs_stream(
        self,
        *,
        conversation_id: str,
        chat_id: str,
        tool_outputs: list,
        msg: cl.Message
    ):
        """提交工具执行结果（问答节点用户回答）以续接挂起的工作流

        当工作流运行到「问答节点」并返回 requires_action 后，
        必须调用此方法而非 chat_stream 来提交用户答案。
        否则会被 Coze 视为新的对话，导致工作流从头重置。

        此方法的实现参考了 Coze 官方 Python SDK (coze-dev/coze-py) 的
        ChatClient.submit_tool_outputs 方法。

        Args:
            conversation_id: 当前对话 ID（从 requires_action 事件中获取）
            chat_id: 挂起的聊天 ID（从 requires_action 事件中获取）
            tool_outputs: 工具执行结果列表，每项包含
                          {"tool_call_id": str, "output": str}
            msg: Chainlit Message 对象，用于流式更新 UI

        Returns:
            dict: {"content": str, "requires_action": dict|None}
                  如果工作流有下一个问答节点，requires_action 会再次非 None
        """
        url = f"{self.base_url}/v3/chat/submit_tool_outputs"

        # ★ 与 SDK 一致：conversation_id 和 chat_id 通过 query params 传递
        params = {
            "conversation_id": conversation_id,
            "chat_id": chat_id,
        }

        payload = {
            "stream": True,
            "tool_outputs": tool_outputs,
        }

        result = {"content": None, "requires_action": None}

        print(f"[Coze] submit_tool_outputs: conv={conversation_id}, chat={chat_id}, "
              f"outputs={json.dumps(tool_outputs, ensure_ascii=False)}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self.headers,
                    params=params,
                    json=payload
                ) as response:
                    print(f"[Coze] submit_tool_outputs: status={response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[Coze] submit_tool_outputs HTTP error: {response.status}")
                        return result

                    # 先读取前几个字节来检查是否是 JSON 错误响应而非 SSE 流
                    first_bytes = await response.content.readline()
                    first_line = first_bytes.decode('utf-8').strip()

                    if first_line.startswith('{'):
                        try:
                            error_data = json.loads(first_line)
                            if error_data.get("code") and error_data.get("code") != 0:
                                print(f"[Coze] submit_tool_outputs API error: "
                                      f"code={error_data.get('code')}, msg={error_data.get('msg')}")
                                return result
                        except json.JSONDecodeError:
                            pass

                    full_content, requires_action_info, msg = await self._process_sse_stream_with_first_line(
                        response, msg, first_line
                    )

        except asyncio.CancelledError:
            await self._persist_msg(msg, msg.content or "")
            raise
        except aiohttp.ClientError as e:
            print(f"[Coze] submit_tool_outputs network error: {e}")
            return result
        except Exception as e:
            print(f"[Coze] submit_tool_outputs exception: {e}")
            return result

        await self._persist_msg(msg, full_content)

        result["content"] = full_content if full_content else None
        result["requires_action"] = requires_action_info
        return result

    async def _process_sse_stream_with_first_line(
        self, response, msg: cl.Message, first_line: str
    ):
        """处理 SSE 流，同时考虑已经读取的第一行"""
        full_content = ""
        requires_action_info = None
        current_event = None
        current_answer_id = None

        async def process_line(line: str):
            nonlocal full_content, requires_action_info, current_event, current_answer_id, msg

            if not line:
                return

            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    return

                try:
                    data = json.loads(data_str)

                    if isinstance(data, dict) and data.get("code") != 0 and data.get("code") is not None:
                        print(f"[Coze] Stream error: code={data.get('code')}, msg={data.get('msg')}")
                        return

                    if current_event == "conversation.message.delta":
                        if isinstance(data, dict) and data.get("content"):
                            delta_msg_id = data.get("id", "")
                            if (current_answer_id 
                                and delta_msg_id 
                                and delta_msg_id != current_answer_id 
                                and full_content):
                                await self._persist_msg(msg, full_content)
                                msg = cl.Message(content="")
                                await msg.send()
                                full_content = ""
                            if delta_msg_id:
                                current_answer_id = delta_msg_id
                            content_delta = data["content"]
                            full_content += content_delta
                            await msg.stream_token(content_delta)

                    elif current_event == "conversation.message.completed":
                        if isinstance(data, dict) and data.get("type") == "answer":
                            if not full_content and data.get("content"):
                                full_content = data["content"]
                                await msg.stream_token(full_content)

                    elif current_event == "conversation.chat.completed":
                        if isinstance(data, dict):
                            if data.get("status") == "requires_action" and data.get("required_action"):
                                info = self._extract_requires_action(data)
                                if info:
                                    requires_action_info = info

                    elif current_event == "conversation.chat.requires_action":
                        if isinstance(data, dict):
                            info = self._extract_requires_action(data)
                            if info:
                                requires_action_info = info

                    elif current_event == "conversation.chat.failed":
                        if isinstance(data, dict):
                            print(f"[Coze] 对话失败: error={data.get('last_error', {})}")

                    elif current_event == "error":
                        if isinstance(data, dict):
                            print(f"[Coze] Stream error: code={data.get('code')}, "
                                  f"msg={data.get('msg', 'Unknown')}")

                    # 兜底检查
                    if (isinstance(data, dict) 
                        and data.get("status") == "requires_action" 
                        and data.get("required_action")
                        and requires_action_info is None):
                        info = self._extract_requires_action(data)
                        if info:
                            requires_action_info = info

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"[Coze] SSE process error: {e}")

        if first_line:
            await process_line(first_line)

        async for line_bytes in response.content:
            line = line_bytes.decode('utf-8').strip()
            await process_line(line)

        return full_content, requires_action_info, msg

    async def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history"""
        url = f"{self.base_url}/v1/conversation/message/list"

        params = {
            "conversation_id": conversation_id
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            return data.get("data", [])
                        else:
                            print(f"[Coze API] Get history error: {data.get('msg')}")
                    else:
                        error_text = await response.text()
                        print(f"[Coze API] Get history HTTP error: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            print(f"[Coze API] Get history network error: {e}")
        except Exception as e:
            print(f"[Coze API] Get history exception: {e}")
        return []


# ==================== 多智能体管线 ====================
# 订阅-发布式多智能体系统的宿主接入点：
# 依赖全部在此注入，multi_agent 包不反向 import 本模块。
_pipeline: Optional[MultiAgentPipeline] = None


def _register_agent_conversation(conversation_id: str, username: str) -> None:
    """Agent 惰性创建 Coze 会话后登记映射（Coze 工作流 HTTP 回调依赖）"""
    conversation_user_map[conversation_id] = username
    _save_conversation_map_to_db(conversation_id, username)


def _get_pipeline() -> MultiAgentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MultiAgentPipeline(
            AgentDeps(
                coze_factory=CozeAPI,
                get_token=get_valid_token,
                register_conversation=_register_agent_conversation,
                get_bot_id=get_agent_bot_id,
                log_usage=log_persona_usage,
            ),
            DB_PATH,
        )
    return _pipeline


@cl.on_chat_start
async def on_chat_start():
    """Initialize chat session"""
    user = cl.user_session.get("user")
    username = user.identifier if user else "unknown"
    # 安全地获取 role，处理 user 可能是字典的情况
    if user:
        if isinstance(user, dict):
            role = user.get("metadata", {}).get("role", "user")
        else:
            role = user.metadata.get("role", "user") if hasattr(user, 'metadata') else "user"
    else:
        role = "user"

    # Store user info in session
    cl.user_session.set("username", username)
    cl.user_session.set("role", role)

    # 多智能体：不再急切创建 Coze 会话——各 Agent 在首次响应时
    # 惰性创建自己的会话并登记 conversation_user_map。
    # 这些 session 键都是 JSON 可序列化的，Chainlit 会经 thread metadata
    # 自动持久化并在恢复会话时还原。
    cl.user_session.set(SESSION_AGENT_CONVERSATIONS, {})
    cl.user_session.set(SESSION_AGENT_STATE, {})
    cl.user_session.set("last_agent", None)
    cl.user_session.set("last_topic", None)
    cl.user_session.set("recent_history", [])
    print(f"[MultiAgent] New chat session initialized for user: {username}")

    # 欢迎消息已移除

@cl.on_chat_resume
async def on_chat_resume(thread):
    """Resume a chat from history"""
    # 显示加载动画
    loading_msg = cl.Message(
        content="⏳ 正在加载历史对话记录...",
        author="系统"
    )
    await loading_msg.send()

    user = cl.user_session.get("user")
    username = user.identifier if user else "unknown"
    # 安全地获取 role，处理 user 可能是字典的情况
    if user:
        if isinstance(user, dict):
            role = user.get("metadata", {}).get("role", "user")
        else:
            role = user.metadata.get("role", "user") if hasattr(user, 'metadata') else "user"
    else:
        role = "user"

    cl.user_session.set("username", username)
    cl.user_session.set("role", role)

    # 安全地获取 thread metadata，处理 thread 可能是字典/字符串的情况
    thread_metadata = None
    if isinstance(thread, dict):
        thread_metadata = thread.get("metadata")
    else:
        thread_metadata = getattr(thread, "metadata", None)
    if isinstance(thread_metadata, str):
        try:
            thread_metadata = json.loads(thread_metadata)
        except Exception:
            thread_metadata = None
    if not isinstance(thread_metadata, dict):
        thread_metadata = {}

    # 多智能体会话映射：Chainlit 已把 thread metadata 整体还原进 user_session
    #（backend/chainlit/socket.py resume_thread），这里只做旧结构迁移和映射重登记。
    agent_conversations = cl.user_session.get(SESSION_AGENT_CONVERSATIONS)
    if not isinstance(agent_conversations, dict):
        agent_conversations = {}

    # 旧版单会话线程：把遗留 conversation_id 迁移给每日一练 Agent
    #（旧会话中可能有挂起的练习工作流，必须归属该 Agent 才能续接）
    legacy_conversation_id = thread_metadata.get("conversation_id") or cl.user_session.get("conversation_id")
    if not agent_conversations and legacy_conversation_id:
        agent_conversations[DailyPracticeAgent.name] = legacy_conversation_id
        print(f"[MultiAgent] Migrated legacy conversation {legacy_conversation_id} to {DailyPracticeAgent.name}")
    cl.user_session.set(SESSION_AGENT_CONVERSATIONS, agent_conversations)

    # 重新登记所有 Agent 会话映射（Coze 工作流 HTTP 回调解析用户名依赖）
    for conv_id in agent_conversations.values():
        if conv_id:
            conversation_user_map[conv_id] = username
            _save_conversation_map_to_db(conv_id, username)
    if agent_conversations:
        print(f"[MultiAgent] Resumed agent conversations: {agent_conversations}")

    # 旧版挂起状态迁移：session["pending_tool_action"] -> agent_state[练习 Agent]
    agent_state = cl.user_session.get(SESSION_AGENT_STATE)
    if not isinstance(agent_state, dict):
        agent_state = {}
    legacy_pending = cl.user_session.get("pending_tool_action")
    if legacy_pending and not (agent_state.get(DailyPracticeAgent.name) or {}).get("pending_tool_action"):
        practice_state = agent_state.get(DailyPracticeAgent.name) or {}
        practice_state["pending_tool_action"] = legacy_pending
        agent_state[DailyPracticeAgent.name] = practice_state
        cl.user_session.set("pending_tool_action", None)
        print("[MultiAgent] Migrated legacy pending_tool_action to practice agent state")
    cl.user_session.set(SESSION_AGENT_STATE, agent_state)

    if cl.user_session.get("recent_history") is None:
        cl.user_session.set("recent_history", [])

    # 调试：打印历史消息信息
    # 安全地获取 steps，处理 thread 可能是字典的情况
    thread_steps = None
    if isinstance(thread, dict):
        thread_steps = thread.get("steps")
    else:
        thread_steps = getattr(thread, "steps", None)

    if thread_steps:
        print(f"[Chat Resume] Thread has {len(thread_steps)} steps:")
        for i, step in enumerate(thread_steps):
            if isinstance(step, dict):
                step_type = step.get('type', 'unknown')
                step_name = step.get('name', 'unknown')
                output_preview = str(step.get('output', ''))[:50] if step.get('output') else 'None'
            else:
                step_type = getattr(step, 'type', 'unknown')
                step_name = getattr(step, 'name', 'unknown')
                output_preview = str(getattr(step, 'output', ''))[:50] if getattr(step, 'output', None) else 'None'
            print(f"  Step {i}: type={step_type}, name={step_name}, output={output_preview}...")
    else:
        print(f"[Chat Resume] Thread has no steps")

    # 删除加载动画消息
    await loading_msg.remove()

    # 注意：不要在这里手动重新发送历史消息
    # Chainlit 会自动从数据层加载并显示历史消息
    # 手动发送会导致消息重复显示


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user message"""
    user = cl.user_session.get("user")
    username = user.identifier if user else "unknown"
    # 安全地获取 role，处理 user 可能是字典的情况
    if user:
        if isinstance(user, dict):
            role = user.get("metadata", {}).get("role", "user")
        else:
            role = user.metadata.get("role", "user") if hasattr(user, 'metadata') else "user"
    else:
        role = "user"

    # Store/update user info in session
    cl.user_session.set("username", username)
    cl.user_session.set("role", role)

    # Handle special commands
    content = message.content.strip().lower()

    if content == "/register" and role == "admin":
        await show_register_form()
        return

    if content == "/users" and role == "admin":
        await list_users()
        return


    if content in ("/password", "/密码", "/passwd"):
        await change_password(username)
        return

    if content == "/help":
        await show_help(role)
        return

    if content == "/model" and role == "admin":
        await configure_model()
        return

    # ========== 多智能体管线 ==========
    # MessageNormalizer 标准化 → Router 判定任务型 topic → MessageBus 发布
    # → Subagent 竞价（独占 topic 直达）→ ResponseSelector 选赢家 → 流式生成。
    # 练习工作流挂起（requires_action）时续接优先，退出词可打断。
    msg = cl.Message(content="")
    await msg.send()

    preferred_style = user_preferred_styles.get(username) or DEFAULT_PREFERRED_STYLE
    try:
        thread_id = cl.context.session.thread_id
    except Exception:
        thread_id = None

    print(f"[on_message] user={username}, preferred_style={preferred_style}, "
          f"message={message.content[:50]}...")

    # 注意：传原文 message.content（上面的小写 content 只用于命令匹配）
    await _get_pipeline().handle(username, message.content, thread_id, preferred_style, msg)


async def show_help(role: str):
    """Show help information"""
    help_text = "📖 **可用命令**\n\n"

    if role == "admin":
        help_text += "**管理员命令：**\n"
        help_text += "- `/model` - 配置模型参数 (Service Identity Token, Bot ID)\n"
        help_text += "- `/register` - 注册新用户\n"
        help_text += "- `/users` - 用户管理系统（注册/删除/重置密码/修改角色/查看详情）\n\n"

    help_text += "**普通命令：**\n"

    help_text += "- `/password` - 修改登录密码\n"
    help_text += "- `/help` - 显示此帮助信息\n"
    help_text += "- 直接输入问题 - 与 AI 助手对话\n\n"

    if role == "admin":
        help_text += "---\n👑 您当前以**管理员**身份登录。"
    else:
        help_text += "---\n👤 您当前以**普通用户**身份登录。"

    await cl.Message(content=help_text).send()


async def change_password(username: str):
    """用户自助修改密码"""
    if username not in users_db:
        await cl.Message(content="❌ 用户不存在，无法修改密码。").send()
        return

    # 第一步：验证旧密码
    await cl.Message(content="🔐 **修改密码**\n\n请输入您的**当前密码**进行验证：").send()
    res = await cl.AskUserMessage(content="", type="text", timeout=120).send()
    if not res:
        await cl.Message(content="⏰ 操作超时，已取消修改密码。").send()
        return

    old_password = res["output"].strip()
    if users_db[username]["password"] != old_password:
        await cl.Message(content="❌ 当前密码输入错误，已取消操作。").send()
        return

    # 第二步：输入新密码
    await cl.Message(content="✅ 验证通过！请输入您的**新密码**（至少 4 个字符）：").send()
    res = await cl.AskUserMessage(content="", type="text", timeout=120).send()
    if not res:
        await cl.Message(content="⏰ 操作超时，已取消修改密码。").send()
        return

    new_password = res["output"].strip()
    if len(new_password) < 4:
        await cl.Message(content="❌ 新密码长度不能少于 4 个字符，已取消操作。").send()
        return

    # 第三步：确认新密码
    await cl.Message(content="请**再次输入**新密码进行确认：").send()
    res = await cl.AskUserMessage(content="", type="text", timeout=120).send()
    if not res:
        await cl.Message(content="⏰ 操作超时，已取消修改密码。").send()
        return

    confirm_password = res["output"].strip()
    if new_password != confirm_password:
        await cl.Message(content="❌ 两次输入的密码不一致，已取消操作。").send()
        return

    # 第四步：更新密码
    users_db[username]["password"] = new_password
    _update_user_in_db(username, password=new_password)

    await cl.Message(content="✅ **密码修改成功！**\n\n下次登录时请使用新密码。").send()
    print(f"[Users] 用户 {username} 已通过 /password 命令修改密码")



async def show_register_form():
    """Show user registration form for admin"""
    # 使用 Action 或更清晰的输入方式
    await cl.Message(content="📝 **用户注册**\n\n请输入新用户的用户名：").send()

    res = await cl.AskUserMessage(
        content="",
        type="text"
    ).send()

    if not res or not res.get("output"):
        await cl.Message(content="❌ 注册已取消。").send()
        return

    new_username = res.get("output").strip()

    if new_username in users_db:
        await cl.Message(content=f"❌ 用户 **{new_username}** 已存在。").send()
        return

    await cl.Message(content=f"请为 **{new_username}** 设置密码：").send()
    
    res = await cl.AskUserMessage(
        content="",
        type="password"
    ).send()

    if not res or not res.get("output"):
        await cl.Message(content="❌ 注册已取消。").send()
        return

    new_password = res.get("output")

    # Ask for role
    await cl.Message(content="请选择用户角色（输入 1 为普通用户，2 为管理员）：").send()
    
    res = await cl.AskUserMessage(
        content="",
        type="text"
    ).send()

    role = "user"
    if res and res.get("output") == "2":
        role = "admin"

    if register_user(new_username, new_password, role):
        await cl.Message(
            content=f"✅ 用户 **{new_username}** 注册成功！\n\n"
                    f"角色：{'管理员' if role == 'admin' else '普通用户'}"
        ).send()
    else:
        await cl.Message(content="❌ 注册失败。").send()


async def list_users():
    """User management system (admin only)"""
    while True:
        # 显示用户列表
        user_list = []
        for idx, (username, data) in enumerate(users_db.items(), 1):
            role_display = "👑 管理员" if data["role"] == "admin" else "👤 普通用户"
            user_list.append(f"{idx}. **{username}** | {role_display}")

        content = "📋 **用户管理系统**\n\n"
        content += "当前用户列表：\n" + "\n".join(user_list) if user_list else "暂无用户"
        content += "\n\n**操作选项：**"
        content += "\n1. 注册新用户"
        content += "\n2. 删除用户"
        content += "\n3. 重置用户密码"
        content += "\n4. 修改用户角色"
        content += "\n5. 查看用户详情"
        content += "\n0. 退出用户管理"
        
        await cl.Message(content=content).send()
        
        # 获取用户选择
        res = await cl.AskUserMessage(content="请输入操作编号：", type="text").send()
        
        if not res or not res.get("output"):
            await cl.Message(content="已退出用户管理。").send()
            break
        
        choice = res.get("output").strip()
        
        if choice == "0":
            await cl.Message(content="👋 已退出用户管理。").send()
            break
        elif choice == "1":
            await show_register_form()
        elif choice == "2":
            await delete_user_form()
        elif choice == "3":
            await reset_password_form()
        elif choice == "4":
            await change_role_form()
        elif choice == "5":
            await show_user_details()
        else:
            await cl.Message(content="❌ 无效的选择，请重新输入。").send()


async def delete_user_form():
    """Delete user form"""
    await cl.Message(content="🗑️ **删除用户**\n\n请输入要删除的用户名：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    username = res.get("output").strip()
    
    if username not in users_db:
        await cl.Message(content=f"❌ 用户 **{username}** 不存在。").send()
        return
    
    if username == ADMIN_USERNAME:
        await cl.Message(content="❌ 不能删除默认管理员账户。").send()
        return
    
    # 确认删除
    await cl.Message(content=f"⚠️ 确定要删除用户 **{username}** 吗？\n输入 **y** 确认删除，输入 **n** 取消：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if res and res.get("output") and res.get("output").strip().lower() == "y":
        del users_db[username]
        _delete_user_from_db(username)
        await cl.Message(content=f"✅ 用户 **{username}** 已删除。").send()
    else:
        await cl.Message(content="❌ 删除操作已取消。").send()


async def reset_password_form():
    """Reset user password form"""
    await cl.Message(content="🔑 **重置密码**\n\n请输入要重置密码的用户名：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    username = res.get("output").strip()
    
    if username not in users_db:
        await cl.Message(content=f"❌ 用户 **{username}** 不存在。").send()
        return
    
    await cl.Message(content=f"请为用户 **{username}** 设置新密码：").send()
    
    res = await cl.AskUserMessage(content="", type="password").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    new_password = res.get("output")
    users_db[username]["password"] = new_password
    _update_user_in_db(username, password=new_password)
    
    await cl.Message(content=f"✅ 用户 **{username}** 的密码已重置。").send()


async def change_role_form():
    """Change user role form"""
    await cl.Message(content="👤 **修改用户角色**\n\n请输入要修改的用户名：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    username = res.get("output").strip()
    
    if username not in users_db:
        await cl.Message(content=f"❌ 用户 **{username}** 不存在。").send()
        return
    
    if username == ADMIN_USERNAME:
        await cl.Message(content="❌ 不能修改默认管理员的角色。").send()
        return
    
    current_role = users_db[username]["role"]
    await cl.Message(
        content=f"用户 **{username}** 当前角色：**{current_role}**\n\n"
                f"请选择新角色：\n"
                f"1. 普通用户\n"
                f"2. 管理员"
    ).send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    choice = res.get("output").strip()
    
    if choice == "1":
        users_db[username]["role"] = "user"
        _update_user_in_db(username, role="user")
        await cl.Message(content=f"✅ 用户 **{username}** 已设置为普通用户。").send()
    elif choice == "2":
        users_db[username]["role"] = "admin"
        _update_user_in_db(username, role="admin")
        await cl.Message(content=f"✅ 用户 **{username}** 已设置为管理员。").send()
    else:
        await cl.Message(content="❌ 无效的选择。").send()


async def show_user_details():
    """Show detailed user information"""
    await cl.Message(content="� **查看用户详情**\n\n请输入要查看的用户名：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    if not res or not res.get("output"):
        await cl.Message(content="❌ 操作已取消。").send()
        return
    
    username = res.get("output").strip()
    
    if username not in users_db:
        await cl.Message(content=f"❌ 用户 **{username}** 不存在。").send()
        return
    
    data = users_db[username]
    role_display = "👑 管理员" if data["role"] == "admin" else "👤 普通用户"
    
    details = f"📋 **用户详情：{username}**\n\n"
    details += f"**角色：** {role_display}\n"
    
    await cl.Message(content=details).send()


@cl.set_starters
async def set_starters():
    """Set starter messages for the chat interface"""
    return [
        cl.Starter(
            label="考试大纲",
            message="请介绍一下计算机三级网络技术的考试大纲和主要内容",
            icon="/public/icons/book-open.svg",
        ),
        cl.Starter(
            label="备考建议",
            message="给我一些计算机三级网络技术的备考建议和学习计划",
            icon="/public/icons/lightbulb.svg",
        ),
        cl.Starter(
            label="网络基础",
            message="解释一下计算机网络的基本概念和OSI七层模型",
            icon="/public/icons/globe.svg",
        ),
        cl.Starter(
            label="IP地址",
            message="详细讲解IP地址的分类、子网划分和CIDR表示法",
            icon="/public/icons/network.svg",
        ),
        cl.Starter(
            label="每日一练",
            message="开始每日一练",
            icon="/public/icons/pencil-line.svg",
        ),
    ]


async def configure_model():
    """Configure Coze model parameters (Service Identity Token and Bot ID)"""
    global COZE_JWT_TOKEN, COZE_BOT_ID

    # 显示当前配置状态
    current_jwt_status = "已配置" if COZE_JWT_TOKEN else "未配置"
    current_bot_status = COZE_BOT_ID if COZE_BOT_ID else "未配置"
    
    await cl.Message(
        content=f"🔧 **配置模型参数**\n\n"
                f"当前配置状态：\n"
                f"- Service Identity Token: {current_jwt_status}\n"
                f"- Bot ID: {current_bot_status}\n\n"
                f"请选择要更新的参数："
    ).send()

    # 询问是否更新 Service Identity Token
    await cl.Message(content="是否更新 Service Identity Token？\n输入 **y** 更新，输入 **n** 跳过：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    new_jwt_token = COZE_JWT_TOKEN  # 默认保持原值
    if res and res.get("output") and res.get("output").strip().lower() == "y":
        await cl.Message(content="请输入新的 Service Identity Token：").send()
        
        res = await cl.AskUserMessage(content="", type="text").send()
        
        if res and res.get("output"):
            new_jwt_token = res.get("output").strip()
        else:
            await cl.Message(content="❌ 输入无效，保持原配置。").send()

    # 询问是否更新 Bot ID
    await cl.Message(content="是否更新 Bot ID？\n输入 **y** 更新，输入 **n** 跳过：").send()
    
    res = await cl.AskUserMessage(content="", type="text").send()
    
    new_bot_id = COZE_BOT_ID  # 默认保持原值
    if res and res.get("output") and res.get("output").strip().lower() == "y":
        await cl.Message(content="请输入新的 Bot ID：").send()
        
        res = await cl.AskUserMessage(content="", type="text").send()
        
        if res and res.get("output"):
            new_bot_id = res.get("output").strip()
        else:
            await cl.Message(content="❌ 输入无效，保持原配置。").send()

    # 检查是否有变更
    jwt_changed = new_jwt_token != COZE_JWT_TOKEN
    bot_changed = new_bot_id != COZE_BOT_ID
    
    if not jwt_changed and not bot_changed:
        await cl.Message(content="ℹ️ 配置未变更。").send()
        return

    # Update configuration
    COZE_JWT_TOKEN = new_jwt_token
    COZE_BOT_ID = new_bot_id
    config_storage["COZE_JWT_TOKEN"] = new_jwt_token
    config_storage["COZE_BOT_ID"] = new_bot_id
    _save_config_to_db("COZE_JWT_TOKEN", new_jwt_token)
    _save_config_to_db("COZE_BOT_ID", new_bot_id)
    # 多智能体模式下各 Agent 每轮通过 get_agent_bot_id 读取 config_storage，
    # 无需重建任何客户端实例。

    # 显示更新摘要
    changes = []
    if jwt_changed:
        changes.append("Service Identity Token")
    if bot_changed:
        changes.append("Bot ID")

    await cl.Message(
        content=f"✅ **模型参数配置成功！**\n\n"
                f"已更新：{', '.join(changes)}\n"
                f"Service Identity Token: {'*' * 10}\n"
                f"Bot ID: {new_bot_id}\n\n"
                f"说明：此 Bot ID 供「每日一练」工作流使用，同时也是"
                f"未单独配置专属 Bot 的教学智能体的回退 Bot。"
                f"各教学智能体的专属 Bot ID 请在管理后台的系统配置页设置。\n\n"
                f"新的配置已生效。"
    ).send()


@app.get("/api/admin/auth/check")
async def check_admin_auth(request: Request):
    """检查当前用户是否为管理员（供前端调用）"""
    admin_username = verify_admin_from_request(request)
    return JSONResponse({
        "is_admin": admin_username is not None,
        "username": admin_username or ""
    })


@app.post("/api/preferred-style")
async def set_preferred_style(request: Request):
    """设置当前用户的偏好交互风格（供前端调用）

    preferred_style 只是 ResponseSelector 的选择权重，不强制指定人设 Agent。
    """
    username = verify_user_from_request(request)
    if not username:
        return JSONResponse({"error": "未登录"}, status_code=401)
    try:
        body = await request.json()
        preferred_style = body.get("preferred_style", "")
        if preferred_style not in VALID_PREFERRED_STYLES:
            return JSONResponse({"error": "无效的风格选择"}, status_code=400)
        user_preferred_styles[username] = preferred_style
        print(f"[PreferredStyle] 用户 {username} 设置偏好风格: '{preferred_style}'")
        return JSONResponse({"success": True, "preferred_style": preferred_style})
    except Exception as e:
        print(f"[PreferredStyle] 设置失败: {e}")
        return JSONResponse({"error": "设置失败"}, status_code=500)


@app.get("/api/preferred-style")
async def get_preferred_style(request: Request):
    """获取当前用户的偏好交互风格（供前端调用）

    注意：GET 请求实际由 AdminRouteMiddleware 拦截应答（Chainlit 兜底路由
    会遮蔽此路由），此处保留作为接口文档与 POST 的对称定义。
    """
    username = verify_user_from_request(request)
    if not username:
        return JSONResponse({"preferred_style": ""}, status_code=401)
    style = user_preferred_styles.get(username) or DEFAULT_PREFERRED_STYLE
    return JSONResponse({"preferred_style": style})


@app.get("/api/admin/stats")
async def get_admin_stats(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    
    total_users = len(users_db)
    
    # 获取对话总数和活跃用户数
    total_conversations = 0
    active_users = 0
    
    # Engagement metrics
    user_count_data = []
    conversation_count_data = []
    avg_conversation_data = []
    retention_1d_data = []
    retention_7d_data = []
    retention_30d_data = []
    
    try:
        data_layer = get_data_layer()
        if data_layer:
            from sqlalchemy import text
            from datetime import datetime, timedelta
            
            async with data_layer.async_session() as session:
                # 获取总对话数
                count_result = await session.execute(text("SELECT COUNT(*) FROM threads"))
                total_conversations = count_result.scalar() or 0
                
                # 获取活跃用户数（去重）
                users_result = await session.execute(text("SELECT DISTINCT userIdentifier FROM threads WHERE userIdentifier IS NOT NULL"))
                active_user_set = set()
                for row in users_result:
                    if row[0]:
                        active_user_set.add(row[0])
                active_users = len(active_user_set)
                
                # Generate engagement metrics for last 7 days
                for i in range(6, -1, -1):
                    date = datetime.now() - timedelta(days=i)
                    date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                    date_end = date_start + timedelta(days=1)
                    
                    # Daily user count
                    daily_users_query = text("""
                        SELECT COUNT(DISTINCT userIdentifier) 
                        FROM threads 
                        WHERE createdAt >= :start AND createdAt < :end
                        AND userIdentifier IS NOT NULL
                    """)
                    daily_users_result = await session.execute(
                        daily_users_query, 
                        {"start": date_start.isoformat(), "end": date_end.isoformat()}
                    )
                    daily_users = daily_users_result.scalar() or 0
                    user_count_data.append(daily_users)
                    
                    # Daily conversation count
                    daily_conv_query = text("""
                        SELECT COUNT(*) 
                        FROM threads 
                        WHERE createdAt >= :start AND createdAt < :end
                    """)
                    daily_conv_result = await session.execute(
                        daily_conv_query,
                        {"start": date_start.isoformat(), "end": date_end.isoformat()}
                    )
                    daily_conversations = daily_conv_result.scalar() or 0
                    conversation_count_data.append(daily_conversations)
                    
                    # Average conversations per user
                    avg_conv = daily_conversations / daily_users if daily_users > 0 else 0
                    avg_conversation_data.append(round(avg_conv, 2))
                    
                    # Retention calculations (simplified - based on user activity)
                    # 1-day retention: users who came back the next day
                    if i < 6:
                        next_date_start = date_start + timedelta(days=1)
                        next_date_end = next_date_start + timedelta(days=1)
                        
                        retention_query = text("""
                            SELECT COUNT(DISTINCT t1.userIdentifier)
                            FROM threads t1
                            WHERE t1.createdAt >= :start AND t1.createdAt < :end
                            AND t1.userIdentifier IS NOT NULL
                            AND EXISTS (
                                SELECT 1 FROM threads t2
                                WHERE t2.userIdentifier = t1.userIdentifier
                                AND t2.createdAt >= :next_start AND t2.createdAt < :next_end
                            )
                        """)
                        retention_result = await session.execute(
                            retention_query,
                            {
                                "start": date_start.isoformat(),
                                "end": date_end.isoformat(),
                                "next_start": next_date_start.isoformat(),
                                "next_end": next_date_end.isoformat()
                            }
                        )
                        retained_users = retention_result.scalar() or 0
                        retention_rate = (retained_users / daily_users * 100) if daily_users > 0 else 0
                        retention_1d_data.append(round(retention_rate, 1))
                    else:
                        retention_1d_data.append(0)
                    
                    # 7-day retention (simplified)
                    retention_7d_data.append(round(retention_rate * 0.7, 1) if i < 6 else 0)
                    
                    # 30-day retention (simplified)
                    retention_30d_data.append(round(retention_rate * 0.5, 1) if i < 6 else 0)
                
                print(f"[Admin Stats] Total conversations: {total_conversations}, Active users: {active_users}")
    except Exception as e:
        print(f"[Admin Stats] Error getting stats: {e}")
        import traceback
        traceback.print_exc()
        # Provide default data on error
        user_count_data = [0] * 7
        conversation_count_data = [0] * 7
        avg_conversation_data = [0] * 7
        retention_1d_data = [0] * 7
        retention_7d_data = [0] * 7
        retention_30d_data = [0] * 7
    
    token_health = await check_token_health()
    
    recent_activity = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT username, action, created_at FROM app_activity_logs ORDER BY id DESC LIMIT 10')
        for row in cursor:
            username, action, created_at = row
            recent_activity.append({
                "text": f"用户 {username} {action}",
                "time": created_at
            })
        conn.close()
    except Exception as e:
        print(f"[Admin Stats] 获取最近活动失败: {e}")
    
    # ==================== 新增可视化图表数据 ====================
    today_active_users_list = []
    # 各人设下的成员及其独立对话次数
    persona_users_data = {}
    active_user_proportion = {"active": 0, "total": 0, "percent": 0.0}
    
    # 提取所有管理员用户列表，用于后续过滤
    admin_users = [u for u, d in users_db.items() if d.get("role") == "admin"]
    
    try:
        # 计算系统中总共的非 admin 用户数
        total_non_admin_users = sum(1 for d in users_db.values() if d.get("role") != "admin")
        active_user_proportion["total"] = total_non_admin_users
        
        data_layer = get_data_layer()
        if data_layer:
            from sqlalchemy import text
            from datetime import datetime
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            
            async with data_layer.async_session() as session:
                # 获取今天所有的对话数按用户分组
                active_users_query = text("""
                    SELECT userIdentifier, COUNT(*)
                    FROM threads
                    WHERE createdAt >= :start AND userIdentifier IS NOT NULL
                    GROUP BY userIdentifier
                """)
                active_result = await session.execute(active_users_query, {"start": today_start})
                
                active_non_admin_count = 0
                for row in active_result:
                    user_name = row[0]
                    count = row[1]
                    if user_name and user_name not in admin_users:
                        today_active_users_list.append({"username": user_name, "count": count})
                        active_non_admin_count += 1
                
                # 按对话次数降序排列
                today_active_users_list.sort(key=lambda x: x["count"], reverse=True)
                
                active_user_proportion["active"] = active_non_admin_count
                if total_non_admin_users > 0:
                    active_user_proportion["percent"] = round((active_non_admin_count / total_non_admin_users) * 100, 1)
                
                # 获取系统级累计最为活跃的前 10 名用户
                top_users_query = text("""
                    SELECT userIdentifier, COUNT(*)
                    FROM threads
                    WHERE userIdentifier IS NOT NULL
                    GROUP BY userIdentifier
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                top_users_list = []
                top_result = await session.execute(top_users_query)
                for row in top_result:
                    user_name = row[0]
                    count = row[1]
                    if user_name and user_name not in admin_users:
                        top_users_list.append({"username": user_name, "count": count})
                
                # 获取全站对话深度（单对话的消息轮次分布）
                depth_query = text("""
                    SELECT message_count, COUNT(*) as thread_count
                    FROM (
                        SELECT t.id, COUNT(CASE WHEN s.type IN ('user_message', 'assistant_message') THEN 1 END) as message_count
                        FROM threads t
                        LEFT JOIN steps s ON t.id = s.threadId
                        GROUP BY t.id
                    ) AS depth_counts
                    GROUP BY message_count
                """)
                depth_result = await session.execute(depth_query)
                conversation_depth_data = {"1-5": 0, "6-15": 0, "16-30": 0, "30+": 0}
                for row in depth_result:
                    m_count = row[0] or 0
                    t_count = row[1] or 0
                    if 1 <= m_count <= 5:
                        conversation_depth_data["1-5"] += t_count
                    elif 6 <= m_count <= 15:
                        conversation_depth_data["6-15"] += t_count
                    elif 16 <= m_count <= 30:
                        conversation_depth_data["16-30"] += t_count
                    elif m_count > 30:
                        conversation_depth_data["30+"] += t_count
                
                # 获取全天活跃对话的时间分布
                time_query = text("SELECT createdAt FROM threads WHERE createdAt IS NOT NULL")
                time_result = await session.execute(time_query)
                chat_time_data = {"凌晨(00-06)": 0, "上午(06-12)": 0, "下午(12-18)": 0, "晚上(18-24)": 0}
                for row in time_result:
                    created_at = row[0]
                    if created_at:
                        try:
                            parts = created_at.split('T')
                            if len(parts) == 2:
                                h = int(parts[1][:2])
                                if 0 <= h < 6: chat_time_data["凌晨(00-06)"] += 1
                                elif 6 <= h < 12: chat_time_data["上午(06-12)"] += 1
                                elif 12 <= h < 18: chat_time_data["下午(12-18)"] += 1
                                else: chat_time_data["晚上(18-24)"] += 1
                        except:
                            pass

    except Exception as e:
        print(f"[Admin Stats] 获取额外组合统计图表数据失败: {e}")
        conversation_depth_data = {"1-5": 0, "6-15": 0, "16-30": 0, "30+": 0}
        chat_time_data = {"凌晨(00-06)": 0, "上午(06-12)": 0, "下午(12-18)": 0, "晚上(18-24)": 0}

    # 人设使用统计
    persona_stats = []
    try:
        conn = sqlite3.connect(DB_PATH)
        # 获取各人设的使用次数（总体，包含全局统计）
        cursor = conn.execute('''
            SELECT persona, COUNT(DISTINCT thread_id) as count 
            FROM persona_usage_logs 
            WHERE thread_id IS NOT NULL 
            GROUP BY persona 
            ORDER BY count DESC
        ''')
        total_persona_usage = 0
        raw_stats = []
        for row in cursor:
            persona_name, count = row
            raw_stats.append({"name": persona_name, "count": count})
            total_persona_usage += count
        
        # 计算百分比
        for item in raw_stats:
            percentage = round(item["count"] / total_persona_usage * 100, 1) if total_persona_usage > 0 else 0
            persona_stats.append({
                "name": item["name"],
                "count": item["count"],
                "percentage": percentage
            })
            
        # 获取各人设下每个非管理员成员的使用次数（按对话数计算）
        cursor_persona = conn.execute('''
            SELECT persona, username, COUNT(DISTINCT thread_id) as count
            FROM persona_usage_logs
            WHERE thread_id IS NOT NULL
            GROUP BY persona, username
            ORDER BY count DESC
        ''')
        for row in cursor_persona:
            persona_name, p_username, count = row
            if persona_name not in persona_users_data:
                persona_users_data[persona_name] = []
            persona_users_data[persona_name].append({"username": p_username, "count": count})

        conn.close()
    except Exception as e:
        print(f"[Admin Stats] 获取人设分类统计失败: {e}")
    
    return JSONResponse({
        "total_users": total_users,
        "active_users": active_users,
        "total_conversations": total_conversations,
        "token_health": token_health,
        "recent_activity": recent_activity,
        "user_count_data": user_count_data,
        "conversation_count_data": conversation_count_data,
        "avg_conversation_data": avg_conversation_data,
        "retention_1d_data": retention_1d_data,
        "retention_7d_data": retention_7d_data,
        "retention_30d_data": retention_30d_data,
        "persona_stats": persona_stats,
        "today_active_users": today_active_users_list,
        "persona_users_data": persona_users_data,
        "active_user_proportion": active_user_proportion,
        "top_active_users": top_users_list,
        "chat_time_data": chat_time_data,
        "conversation_depth_data": conversation_depth_data
    })


@app.get("/api/admin/overview")
async def get_admin_overview(request: Request, range: str = "7d"):
    """运营后台总览数据。"""
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    _ensure_assignment_records_table()
    days = {"7d": 7, "30d": 30}.get(range, 7)
    admin_users = [u for u, d in users_db.items() if d.get("role") == "admin"]
    placeholders = ",".join("?" for _ in admin_users)
    admin_filter = f"AND username NOT IN ({placeholders})" if admin_users else ""

    try:
        from datetime import timedelta

        conn = sqlite3.connect(DB_PATH)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_local = today.strftime("%Y-%m-%d %H:%M:%S")
        today_iso = today.isoformat()

        total_users = conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]
        normal_users = conn.execute("SELECT COUNT(*) FROM app_users WHERE role != 'admin'").fetchone()[0]
        total_conversations = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        total_messages = conn.execute(
            "SELECT COUNT(*) FROM steps WHERE type IN ('user_message', 'assistant_message')"
        ).fetchone()[0]
        active_today = conn.execute(
            "SELECT COUNT(DISTINCT userIdentifier) FROM threads WHERE createdAt >= ? AND userIdentifier IS NOT NULL",
            (today_iso,),
        ).fetchone()[0]
        practice_sessions = conn.execute("SELECT COUNT(*) FROM practice_records").fetchone()[0]
        mistake_count = conn.execute("SELECT COUNT(*) FROM mistake_details").fetchone()[0]
        assignment_count = conn.execute("SELECT COUNT(*) FROM assignment_records").fetchone()[0]

        daily = []
        for i in range(days - 1, -1, -1):
            start = today - timedelta(days=i)
            end = start + timedelta(days=1)
            label = start.strftime("%m-%d")
            daily.append({
                "date": label,
                "users": conn.execute(
                    """
                    SELECT COUNT(DISTINCT userIdentifier)
                    FROM threads
                    WHERE createdAt >= ? AND createdAt < ? AND userIdentifier IS NOT NULL
                    """,
                    (start.isoformat(), end.isoformat()),
                ).fetchone()[0],
                "conversations": conn.execute(
                    "SELECT COUNT(*) FROM threads WHERE createdAt >= ? AND createdAt < ?",
                    (start.isoformat(), end.isoformat()),
                ).fetchone()[0],
                "practices": conn.execute(
                    "SELECT COUNT(*) FROM practice_records WHERE created_at >= ? AND created_at < ?",
                    (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")),
                ).fetchone()[0],
            })

        persona_stats = _sqlite_dicts(conn.execute(
            """
            SELECT persona AS name, COUNT(DISTINCT thread_id) AS count
            FROM persona_usage_logs
            WHERE thread_id IS NOT NULL
            GROUP BY persona
            ORDER BY count DESC
            LIMIT 10
            """
        ))
        total_persona = sum(item["count"] or 0 for item in persona_stats)
        for item in persona_stats:
            item["percentage"] = round((item["count"] or 0) * 100 / total_persona, 1) if total_persona else 0

        today_active_users = _sqlite_dicts(conn.execute(
            """
            SELECT userIdentifier AS username, COUNT(*) AS count
            FROM threads
            WHERE createdAt >= ? AND userIdentifier IS NOT NULL
            GROUP BY userIdentifier
            ORDER BY count DESC
            LIMIT 10
            """,
            (today_iso,),
        ))
        top_active_users = _sqlite_dicts(conn.execute(
            """
            SELECT userIdentifier AS username, COUNT(*) AS count
            FROM threads
            WHERE userIdentifier IS NOT NULL
            GROUP BY userIdentifier
            ORDER BY count DESC
            LIMIT 10
            """
        ))

        depth_rows = conn.execute("""
            SELECT message_count, COUNT(*) AS thread_count
            FROM (
                SELECT t.id, COUNT(CASE WHEN s.type IN ('user_message', 'assistant_message') THEN 1 END) AS message_count
                FROM threads t
                LEFT JOIN steps s ON t.id = s.threadId
                GROUP BY t.id
            )
            GROUP BY message_count
        """).fetchall()
        conversation_depth = {"1-5": 0, "6-15": 0, "16-30": 0, "30+": 0}
        for message_count, thread_count in depth_rows:
            message_count = message_count or 0
            if 1 <= message_count <= 5:
                conversation_depth["1-5"] += thread_count
            elif 6 <= message_count <= 15:
                conversation_depth["6-15"] += thread_count
            elif 16 <= message_count <= 30:
                conversation_depth["16-30"] += thread_count
            elif message_count > 30:
                conversation_depth["30+"] += thread_count

        recent_activity = _sqlite_dicts(conn.execute(
            """
            SELECT actor, action, target, detail, created_at
            FROM app_activity_logs
            ORDER BY id DESC
            LIMIT 12
            """
        ))
        conn.close()

        token_health = await check_token_health()
        return JSONResponse({
            "range": range,
            "kpis": {
                "total_users": total_users,
                "normal_users": normal_users,
                "active_today": active_today,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "practice_sessions": practice_sessions,
                "mistake_count": mistake_count,
                "assignment_count": assignment_count,
            },
            "daily": daily,
            "persona_stats": persona_stats,
            "today_active_users": today_active_users,
            "top_active_users": top_active_users,
            "conversation_depth": conversation_depth,
            "active_user_proportion": {
                "active": active_today,
                "total": normal_users,
                "percent": round(active_today * 100 / normal_users, 1) if normal_users else 0,
            },
            "recent_activity": recent_activity,
            "token_health": token_health,
        })
    except Exception as e:
        print(f"[Admin Overview] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/admin/users")
async def get_admin_users(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    _ensure_assignment_records_table()
    page, page_size, offset = _get_pagination(request)
    q = (request.query_params.get("q") or "").strip()
    role = (request.query_params.get("role") or "").strip()

    where = []
    params: List[Any] = []
    if q:
        where.append("u.username LIKE ?")
        params.append(f"%{q}%")
    if role in ("admin", "user"):
        where.append("u.role = ?")
        params.append(role)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(
            f"SELECT COUNT(*) FROM app_users u {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT
                u.username,
                u.role,
                u.created_at,
                (
                    SELECT MAX(created_at)
                    FROM app_activity_logs l
                    WHERE l.username = u.username AND l.action = '用户登录'
                ) AS last_login,
                (
                    SELECT COUNT(*)
                    FROM threads t
                    WHERE t.userIdentifier = u.username
                ) AS conversation_count,
                COALESCE(lb.practice_count, 0) AS practice_count,
                COALESCE(lb.total_score, 0) AS total_score,
                COALESCE(lb.highest_score, 0) AS highest_score
            FROM app_users u
            LEFT JOIN user_leaderboard lb ON lb.username = u.username
            {where_sql}
            ORDER BY u.created_at DESC, u.username ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        users_list = _sqlite_dicts(rows)
        conn.close()
    except Exception as e:
        print(f"[Admin Users] Error: {e}")
        users_list = [
            {"username": username, "role": data.get("role", "user")}
            for username, data in users_db.items()
        ]
        total = len(users_list)

    payload = _pagination_payload(users_list, total, page, page_size)
    payload["users"] = users_list
    return JSONResponse(payload)


@app.get("/api/admin/users/{username}")
async def get_admin_user_detail(username: str, request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    _ensure_assignment_records_table()
    if username not in users_db:
        return JSONResponse({"error": "用户不存在"}, status_code=404)

    try:
        conn = sqlite3.connect(DB_PATH)
        profile_row = conn.execute(
            """
            SELECT username, role, created_at
            FROM app_users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        profile = {
            "username": username,
            "role": users_db.get(username, {}).get("role", "user"),
            "created_at": "",
        }
        if profile_row:
            profile = {
                "username": profile_row[0],
                "role": profile_row[1],
                "created_at": profile_row[2],
            }

        summary = {
            "conversation_count": conn.execute(
                "SELECT COUNT(*) FROM threads WHERE userIdentifier = ?",
                (username,),
            ).fetchone()[0],
            "message_count": conn.execute(
                """
                SELECT COUNT(*)
                FROM steps s
                JOIN threads t ON t.id = s.threadId
                WHERE t.userIdentifier = ?
                  AND s.type IN ('user_message', 'assistant_message')
                """,
                (username,),
            ).fetchone()[0],
            "practice_count": conn.execute(
                "SELECT COUNT(*) FROM practice_records WHERE username = ?",
                (username,),
            ).fetchone()[0],
            "mistake_count": conn.execute(
                "SELECT COUNT(*) FROM mistake_details WHERE username = ?",
                (username,),
            ).fetchone()[0],
            "assignment_count": conn.execute(
                "SELECT COUNT(*) FROM assignment_records WHERE username = ?",
                (username,),
            ).fetchone()[0],
        }

        leaderboard = conn.execute(
            """
            SELECT total_score, highest_score, practice_count, updated_at
            FROM user_leaderboard
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        learning = {
            "total_score": leaderboard[0] if leaderboard else 0,
            "highest_score": leaderboard[1] if leaderboard else 0,
            "practice_count": leaderboard[2] if leaderboard else 0,
            "updated_at": leaderboard[3] if leaderboard else "",
        }

        activity = _sqlite_dicts(conn.execute(
            """
            SELECT actor, action, target, detail, created_at
            FROM app_activity_logs
            WHERE username = ? OR target = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (username, username),
        ))
        conversations = _sqlite_dicts(conn.execute(
            """
            SELECT id, name, createdAt AS created_at
            FROM threads
            WHERE userIdentifier = ?
            ORDER BY createdAt DESC
            LIMIT 20
            """,
            (username,),
        ))
        practices = _sqlite_dicts(conn.execute(
            """
            SELECT id, score, correct_count, wrong_count, current_streak, created_at
            FROM practice_records
            WHERE username = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (username,),
        ))
        conn.close()
    except Exception as e:
        print(f"[Admin User Detail] Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({
        "profile": profile,
        "summary": summary,
        "learning": learning,
        "activity": activity,
        "conversations": conversations,
        "practices": practices,
    })


@app.post("/api/admin/users")
async def create_admin_user(request: Request):
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        role = get_default_role_for_new_user(body.get("role", "user"))
        
        if not username or not password:
            return JSONResponse({"success": False, "message": "用户名和密码不能为空"})
        
        if username in users_db:
            return JSONResponse({"success": False, "message": "用户已存在"})
        
        users_db[username] = {
            "password": password,
            "role": role,
        }
        _save_user_to_db(username, password, role)
        log_admin_activity(actor, "创建用户", username, f"role={role}")
        
        return JSONResponse({"success": True, "message": "用户创建成功"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/api/admin/users/batch")
async def batch_create_users(request: Request):
    """批量导入用户（JSON 方式接收 base64 编码的 CSV 文件）

    请求体格式：{"file_base64": "<base64 encoded csv bytes>"}
    支持 UTF-8 和 GBK 编码自动检测。
    """
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)

    import csv
    import io
    import base64

    try:
        body = await request.json()
        file_b64 = body.get("file_base64", "")

        if not file_b64:
            return JSONResponse({"success": False, "message": "CSV 内容为空"}, status_code=400)

        # base64 解码为原始字节
        raw_bytes = base64.b64decode(file_b64)

        # 自动编码检测：UTF-8-sig > GBK > latin-1(兜底)
        csv_content = None
        for encoding in ("utf-8-sig", "gbk", "latin-1"):
            try:
                csv_content = raw_bytes.decode(encoding)
                print(f"[Admin] CSV 文件编码检测为: {encoding}")
                break
            except (UnicodeDecodeError, ValueError):
                continue

        if csv_content is None:
            return JSONResponse({"success": False, "message": "文件编码无法识别"}, status_code=400)

        # 解析 CSV
        reader = csv.reader(io.StringIO(csv_content))
        created = []
        skipped = []
        errors = []
        line_num = 0

        for row in reader:
            line_num += 1

            # 跳过空行
            if not row or all(cell.strip() == "" for cell in row):
                continue

            # 跳过表头行（首行含 username/用户名 字样）
            if line_num == 1:
                first_cell = row[0].strip().lower()
                if first_cell in ("username", "用户名", "user", "name", "姓名", "账号"):
                    continue

            # 解析字段
            if len(row) < 2:
                errors.append(f"第 {line_num} 行格式错误：至少需要 用户名,密码 两列")
                continue

            username = row[0].strip()
            password = row[1].strip()
            role = row[2].strip() if len(row) >= 3 and row[2].strip() else "user"
            role = get_default_role_for_new_user(role)

            # 校验
            if not username:
                errors.append(f"第 {line_num} 行：用户名为空")
                continue
            if not password:
                errors.append(f"第 {line_num} 行：密码为空（用户: {username}）")
                continue

            # 检查是否已存在
            if username in users_db:
                skipped.append(username)
                continue

            # 创建用户
            users_db[username] = {
                "password": password,
                "role": role,
            }
            _save_user_to_db(username, password, role)
            log_admin_activity(actor, "批量导入用户", username, f"role={role}")
            created.append(username)

        summary = f"成功创建 {len(created)} 个用户"
        if skipped:
            summary += f"，跳过 {len(skipped)} 个已存在用户"
        if errors:
            summary += f"，{len(errors)} 行存在错误"

        print(f"[Admin] 批量导入用户: created={len(created)}, skipped={len(skipped)}, errors={len(errors)}")

        return JSONResponse({
            "success": True,
            "message": summary,
            "data": {
                "created": created,
                "skipped": skipped,
                "errors": errors,
                "total_created": len(created),
                "total_skipped": len(skipped),
                "total_errors": len(errors),
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "message": f"批量导入失败: {str(e)}"}, status_code=500)


@app.put("/api/admin/users/{username}")
async def update_admin_user(username: str, request: Request):
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        if username not in users_db:
            return JSONResponse({"success": False, "message": "用户不存在"})
        
        body = await request.json()
        
        if body.get("password"):
            users_db[username]["password"] = body["password"]
            _update_user_in_db(username, password=body["password"])
            log_admin_activity(actor, "修改用户密码", username)
        
        if body.get("role"):
            if username == ADMIN_USERNAME:
                return JSONResponse({"success": False, "message": "不能修改默认管理员的角色"})
            users_db[username]["role"] = body["role"]
            _update_user_in_db(username, role=body["role"])
            log_admin_activity(actor, "修改用户角色", username, f"role={body['role']}")
            
        return JSONResponse({"success": True, "message": "用户更新成功"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.put("/api/admin/users/{username}/role")
async def update_user_role(username: str, request: Request):
    """更新用户角色"""
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        if username not in users_db:
            return JSONResponse({"success": False, "error": "用户不存在"}, status_code=404)
        
        if username == ADMIN_USERNAME:
            return JSONResponse({"success": False, "error": "不能修改默认管理员的角色"}, status_code=400)
        
        body = await request.json()
        role = body.get("role")
        
        if role not in ["admin", "user"]:
            return JSONResponse({"success": False, "error": "无效的角色"}, status_code=400)
        
        users_db[username]["role"] = role
        _update_user_in_db(username, role=role)
        log_admin_activity(actor, "修改用户角色", username, f"role={role}")
        return JSONResponse({"success": True, "message": "角色更新成功"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.put("/api/admin/users/{username}/password")
async def update_user_password(username: str, request: Request):
    """更新用户密码"""
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        if username not in users_db:
            return JSONResponse({"success": False, "error": "用户不存在"}, status_code=404)
        
        body = await request.json()
        password = body.get("password")
        
        if not password:
            return JSONResponse({"success": False, "error": "密码不能为空"}, status_code=400)
        
        users_db[username]["password"] = password
        _update_user_in_db(username, password=password)
        log_admin_activity(actor, "修改用户密码", username)
        return JSONResponse({"success": True, "message": "密码更新成功"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.delete("/api/admin/users/{username}")
async def delete_admin_user(username: str, request: Request):
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        if username not in users_db:
            return JSONResponse({"success": False, "message": "用户不存在"})
        
        if username == ADMIN_USERNAME:
            return JSONResponse({"success": False, "message": "不能删除默认管理员账户"})
        
        del users_db[username]
        _delete_user_from_db(username)
        log_admin_activity(actor, "删除用户", username)
        return JSONResponse({"success": True, "message": "用户删除成功"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/api/admin/config")
async def get_admin_config(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    jwt_expires_at = None
    if COZE_JWT_EXPIRES_AT:
        try:
            jwt_expires_at = int(COZE_JWT_EXPIRES_AT)
        except:
            pass
    
    return JSONResponse({
        "bot_id": COZE_BOT_ID,
        "bot_id_novice": config_storage.get("COZE_BOT_ID_NOVICE") or "",
        "bot_id_debate": config_storage.get("COZE_BOT_ID_DEBATE") or "",
        "bot_id_expert": config_storage.get("COZE_BOT_ID_EXPERT") or "",
        "has_service_token": bool(COZE_JWT_TOKEN),
        "masked_service_token": _mask_secret(COZE_JWT_TOKEN),
        "jwt_expires_at": jwt_expires_at,
        "base_url": COZE_BASE_URL,
    })


@app.put("/api/admin/config")
async def update_admin_config(request: Request):
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    global COZE_BOT_ID, COZE_JWT_TOKEN, COZE_JWT_EXPIRES_AT, COZE_BASE_URL
    
    try:
        body = await request.json()
        
        if "bot_id" in body:
            COZE_BOT_ID = body["bot_id"]
            config_storage["COZE_BOT_ID"] = body["bot_id"]
            _save_config_to_db("COZE_BOT_ID", body["bot_id"])

        # 各教学智能体的专属 Bot ID（允许清空以回退到主 Bot ID）
        for field, config_key in (
            ("bot_id_novice", "COZE_BOT_ID_NOVICE"),
            ("bot_id_debate", "COZE_BOT_ID_DEBATE"),
            ("bot_id_expert", "COZE_BOT_ID_EXPERT"),
        ):
            if field in body:
                value = (body.get(field) or "").strip()
                config_storage[config_key] = value
                _save_config_to_db(config_key, value)

        # 接受 service_token（前端发送的字段名）
        if body.get("service_token"):
            COZE_JWT_TOKEN = body["service_token"]
            config_storage["COZE_JWT_TOKEN"] = body["service_token"]
            _save_config_to_db("COZE_JWT_TOKEN", body["service_token"])

        if "jwt_expires_at" in body:
            COZE_JWT_EXPIRES_AT = str(body["jwt_expires_at"] or "")
            config_storage["COZE_JWT_EXPIRES_AT"] = COZE_JWT_EXPIRES_AT
            _save_config_to_db("COZE_JWT_EXPIRES_AT", COZE_JWT_EXPIRES_AT)
        
        if "base_url" in body:
            COZE_BASE_URL = body["base_url"]
            config_storage["COZE_BASE_URL"] = body["base_url"]
            _save_config_to_db("COZE_BASE_URL", body["base_url"])

        changed = [
            key for key in (
                "bot_id", "bot_id_novice", "bot_id_debate", "bot_id_expert",
                "service_token", "jwt_expires_at", "base_url",
            )
            if key in body and (key != "service_token" or body.get("service_token"))
        ]
        log_admin_activity(actor, "更新系统配置", "app_config", ",".join(changed))
        return JSONResponse({"success": True, "message": "配置更新成功"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/api/admin/test-connection")
async def test_api_connection(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    try:
        token = await get_system_token()
        if not token:
            return JSONResponse({"success": False, "message": "没有可用的 Token"})
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            async with session.get(f"{COZE_BASE_URL}/v1/bots", headers=headers) as response:
                if response.status == 200:
                    return JSONResponse({"success": True, "message": "API 连接正常"})
                else:
                    return JSONResponse({"success": False, "message": f"API 返回状态码: {response.status}"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/api/admin/conversations")
async def get_admin_conversations(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    page, page_size, offset = _get_pagination(request)
    q = (request.query_params.get("q") or "").strip().lower()
    username_filter = (request.query_params.get("username") or "").strip()
    persona_filter = (request.query_params.get("persona") or "").strip()

    try:
        import ast

        conn = sqlite3.connect(DB_PATH)
        thread_personas = {}
        for tid, persona in conn.execute("""
            SELECT thread_id, persona
            FROM persona_usage_logs
            WHERE thread_id IS NOT NULL
            ORDER BY id ASC
        """):
            thread_personas[tid] = persona

        rows = conn.execute("""
            SELECT
                t.id,
                t.name,
                t.userIdentifier,
                t.createdAt,
                t.metadata,
                COUNT(CASE WHEN s.type IN ('user_message', 'assistant_message') THEN 1 END) AS message_count
            FROM threads t
            LEFT JOIN steps s ON t.id = s.threadId
            GROUP BY t.id
            ORDER BY t.createdAt DESC
        """).fetchall()

        conversations = []
        for thread_id, name, user_identifier, created_at, metadata, message_count in rows:
            username = user_identifier or "未知"
            conversation_id = ""
            metadata_obj: Dict[str, Any] = {}
            if metadata:
                try:
                    metadata_obj = json.loads(metadata) if isinstance(metadata, str) else metadata
                except json.JSONDecodeError:
                    try:
                        metadata_obj = ast.literal_eval(metadata)
                    except Exception:
                        metadata_obj = {}
            if isinstance(metadata_obj, dict):
                username = metadata_obj.get("username") or user_identifier or "未知"
                conversation_id = metadata_obj.get("conversation_id") or ""

            persona = thread_personas.get(conversation_id) or thread_personas.get(thread_id) or DEFAULT_PERSONA
            item = {
                "id": thread_id,
                "name": name or "未命名对话",
                "username": username,
                "persona": persona,
                "conversation_id": conversation_id,
                "message_count": message_count or 0,
                "created_at": created_at,
            }
            haystack = " ".join(str(item.get(key, "")) for key in ("id", "name", "username", "persona", "conversation_id")).lower()
            if q and q not in haystack:
                continue
            if username_filter and username_filter != username:
                continue
            if persona_filter and persona_filter != persona:
                continue
            conversations.append(item)

        conn.close()
        total = len(conversations)
        conversations = conversations[offset:offset + page_size]
    except Exception as e:
        print(f"[Admin Conversations] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

    payload = _pagination_payload(conversations, total, page, page_size)
    payload["conversations"] = conversations
    return JSONResponse(payload)


@app.get("/api/admin/conversations/{thread_id}")
async def get_conversation_detail(thread_id: str, request: Request):
    """Get detailed messages for a specific conversation"""
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    
    messages = []
    thread = None
    try:
        import ast

        conn = sqlite3.connect(DB_PATH)
        thread_row = conn.execute(
            """
            SELECT id, name, userIdentifier, createdAt, metadata
            FROM threads
            WHERE id = ?
            """,
            (thread_id,),
        ).fetchone()
        if not thread_row:
            conn.close()
            return JSONResponse({"error": "对话不存在"}, status_code=404)

        metadata_obj: Dict[str, Any] = {}
        if thread_row[4]:
            try:
                metadata_obj = json.loads(thread_row[4])
            except json.JSONDecodeError:
                try:
                    metadata_obj = ast.literal_eval(thread_row[4])
                except Exception:
                    metadata_obj = {}
        conversation_id = metadata_obj.get("conversation_id", "") if isinstance(metadata_obj, dict) else ""
        persona_row = conn.execute(
            """
            SELECT persona
            FROM persona_usage_logs
            WHERE thread_id IN (?, ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (thread_id, conversation_id),
        ).fetchone()
        thread = {
            "id": thread_row[0],
            "name": thread_row[1] or "未命名对话",
            "username": metadata_obj.get("username") if isinstance(metadata_obj, dict) else thread_row[2],
            "userIdentifier": thread_row[2],
            "created_at": thread_row[3],
            "conversation_id": conversation_id,
            "persona": persona_row[0] if persona_row else DEFAULT_PERSONA,
            "metadata": metadata_obj,
        }

        rows = conn.execute(
            """
            SELECT id, name, type, input, output, createdAt, metadata
            FROM steps
            WHERE threadId = ?
            ORDER BY createdAt ASC
            """,
            (thread_id,),
        ).fetchall()
        for step_id, name, step_type, input_text, output, created_at, metadata in rows:
            if step_type in ["user_message", "assistant_message"]:
                messages.append({
                    "id": step_id,
                    "author": name or step_type,
                    "type": step_type,
                    "content": output or input_text or "",
                    "created_at": created_at,
                    "metadata": metadata,
                })
        conn.close()
    except Exception as e:
        print(f"[Admin Conversation Detail] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
    
    return JSONResponse({"thread": thread, "messages": messages})


def _date_filter_from_request(request: Request, column: str) -> Tuple[str, List[Any]]:
    where = []
    params: List[Any] = []
    username = (request.query_params.get("username") or "").strip()
    start = (request.query_params.get("start") or "").strip()
    end = (request.query_params.get("end") or "").strip()
    if username:
        where.append("username = ?")
        params.append(username)
    if start:
        where.append(f"{column} >= ?")
        params.append(f"{start} 00:00:00" if len(start) == 10 else start)
    if end:
        where.append(f"{column} <= ?")
        params.append(f"{end} 23:59:59" if len(end) == 10 else end)
    return ("WHERE " + " AND ".join(where)) if where else "", params


@app.get("/api/admin/learning/records")
async def get_admin_learning_records(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    page, page_size, offset = _get_pagination(request)
    where_sql, params = _date_filter_from_request(request, "created_at")
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(f"SELECT COUNT(*) FROM practice_records {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, username, score, correct_count, wrong_count, current_streak, created_at
            FROM practice_records
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = _sqlite_dicts(rows)
        conn.close()
        return JSONResponse(_pagination_payload(items, total, page, page_size))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/admin/learning/mistakes")
async def get_admin_learning_mistakes(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    page, page_size, offset = _get_pagination(request)
    where_sql, params = _date_filter_from_request(request, "created_at")
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(f"SELECT COUNT(*) FROM mistake_details {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, record_id, username, question_id, question_text, user_answer, correct_answer, analysis, created_at
            FROM mistake_details
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = _sqlite_dicts(rows)
        conn.close()
        return JSONResponse(_pagination_payload(items, total, page, page_size))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/admin/learning/assignments")
async def get_admin_learning_assignments(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    _ensure_assignment_records_table()
    page, page_size, offset = _get_pagination(request)
    where_sql, params = _date_filter_from_request(request, "created_at")
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(f"SELECT COUNT(*) FROM assignment_records {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, username, score, feedback, created_at
            FROM assignment_records
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = _sqlite_dicts(rows)
        conn.close()
        return JSONResponse(_pagination_payload(items, total, page, page_size))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/admin/audit")
async def get_admin_audit(request: Request):
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    _ensure_activity_logs_table()
    page, page_size, offset = _get_pagination(request)
    actor = (request.query_params.get("actor") or "").strip()
    target = (request.query_params.get("target") or "").strip()
    where = []
    params: List[Any] = []
    if actor:
        where.append("actor = ?")
        params.append(actor)
    if target:
        where.append("(target = ? OR username = ?)")
        params.extend([target, target])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(f"SELECT COUNT(*) FROM app_activity_logs {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, COALESCE(actor, username) AS actor, action, COALESCE(target, username) AS target, detail, created_at
            FROM app_activity_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = _sqlite_dicts(rows)
        conn.close()
        return JSONResponse(_pagination_payload(items, total, page, page_size))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== 排行榜管理 API ====================

@app.get("/api/admin/leaderboard")
async def admin_get_leaderboard(request: Request, period: str = "all"):
    """管理后台排行榜数据"""
    if not verify_admin_from_request(request):
        return JSONResponse({"error": "未授权"}, status_code=403)
    
    leaderboard = []
    stats = {"total_participants": 0, "highest_score": 0, "avg_score": 0, "today_sessions": 0}
    
    try:
        data_layer = get_data_layer()
        if data_layer:
            from sqlalchemy import text as sa_text
            from datetime import datetime, timedelta
            
            engine = data_layer.engine
            
            # 获取管理员列表，排行榜中排除管理员
            admin_usernames = [u for u, d in users_db.items() if d.get("role") == "admin"]
            
            async with engine.begin() as conn:
                if period == "today":
                    # 今日排名从 practice_records 实时计算
                    # 使用 strftime 保持与SQLite datetime('now','localtime')格式一致（空格分隔符）
                    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if admin_usernames:
                        placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                        sql = sa_text(f"""
                            SELECT username, 
                                   SUM(score) as total_score,
                                   MAX(score) as highest_score,
                                   COUNT(*) as practice_count,
                                   MAX(created_at) as updated_at
                            FROM practice_records
                            WHERE created_at >= :today_start
                            AND username NOT IN ({placeholders})
                            GROUP BY username
                            ORDER BY total_score DESC, MAX(created_at) ASC
                        """)
                        params = {"today_start": today_start}
                        for i, name in enumerate(admin_usernames):
                            params[f"admin_{i}"] = name
                    else:
                        sql = sa_text("""
                            SELECT username,
                                   SUM(score) as total_score,
                                   MAX(score) as highest_score,
                                   COUNT(*) as practice_count,
                                   MAX(created_at) as updated_at
                            FROM practice_records
                            WHERE created_at >= :today_start
                            GROUP BY username
                            ORDER BY total_score DESC, MAX(created_at) ASC
                        """)
                        params = {"today_start": today_start}
                else:
                    # 历史累计从 user_leaderboard 表查询
                    if admin_usernames:
                        placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                        sql = sa_text(f"""
                            SELECT username, total_score, highest_score, practice_count, updated_at
                            FROM user_leaderboard
                            WHERE username NOT IN ({placeholders})
                            ORDER BY total_score DESC
                        """)
                        params = {}
                        for i, name in enumerate(admin_usernames):
                            params[f"admin_{i}"] = name
                    else:
                        sql = sa_text("""
                            SELECT username, total_score, highest_score, practice_count, updated_at
                            FROM user_leaderboard
                            ORDER BY total_score DESC
                        """)
                        params = {}
                
                result = await conn.execute(sql, params)
                rows = result.fetchall()
                
                total_score_sum = 0
                for idx, row in enumerate(rows):
                    entry = {
                        "rank": idx + 1,
                        "username": row[0],
                        "total_score": row[1] or 0,
                        "highest_score": row[2] or 0,
                        "practice_count": row[3] or 0,
                        "updated_at": row[4] or ""
                    }
                    leaderboard.append(entry)
                    total_score_sum += entry["total_score"]
                    if entry["highest_score"] > stats["highest_score"]:
                        stats["highest_score"] = entry["highest_score"]
                
                stats["total_participants"] = len(leaderboard)
                if leaderboard:
                    stats["avg_score"] = round(total_score_sum / len(leaderboard), 1)
                
                # 今日练习数
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                today_count_result = await conn.execute(
                    sa_text("SELECT COUNT(*) FROM practice_records WHERE created_at >= :today_start"),
                    {"today_start": today_start}
                )
                stats["today_sessions"] = today_count_result.scalar() or 0
    except Exception as e:
        print(f"[Admin Leaderboard] Error: {e}")
        import traceback
        traceback.print_exc()
    
    return JSONResponse({"leaderboard": leaderboard, "stats": stats})


@app.put("/api/admin/leaderboard/{username}")
async def admin_update_leaderboard(request: Request, username: str):
    """管理后台修改排行榜分数"""
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    
    try:
        body = await request.json()
        total_score = body.get("total_score")
        highest_score = body.get("highest_score")
        
        if total_score is None and highest_score is None:
            return JSONResponse({"error": "请提供要修改的字段"}, status_code=400)
        
        data_layer = get_data_layer()
        if not data_layer:
            return JSONResponse({"error": "数据库不可用"}, status_code=500)
        
        from sqlalchemy import text as sa_text
        engine = data_layer.engine
        
        async with engine.begin() as conn:
            # 检查用户是否存在
            check = await conn.execute(
                sa_text("SELECT username FROM user_leaderboard WHERE username = :username"),
                {"username": username}
            )
            if not check.fetchone():
                return JSONResponse({"error": f"用户 {username} 不在排行榜中"}, status_code=404)
            
            period = body.get("period", "all")
            
            if period == "today":
                # 修改今日成绩，需要同步到数据库表，且同步更新总成绩
                if total_score is None or highest_score is None:
                    return JSONResponse({"error": "修改今日成绩需要同时提供 total_score 和 highest_score"}, status_code=400)
                
                total_score = int(total_score)
                highest_score = int(highest_score)
                if highest_score > total_score:
                    highest_score = total_score
                
                from datetime import datetime
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                
                # 1. 计算当前的今日总分
                res = await conn.execute(
                    sa_text("SELECT SUM(score) as current_total FROM practice_records WHERE username = :u AND created_at >= :t"),
                    {"u": username, "t": today_start}
                )
                row = res.fetchone()
                old_total = row.current_total if row and row.current_total else 0
                diff = total_score - old_total
                
                # 2. 清理当日记录的分数以便重塑（设为0），保留 count
                await conn.execute(
                    sa_text("UPDATE practice_records SET score = 0 WHERE username = :u AND created_at >= :t"),
                    {"u": username, "t": today_start}
                )
                
                # 3. 找出今日的所有记录以准备分配分数
                res = await conn.execute(
                    sa_text("SELECT id FROM practice_records WHERE username = :u AND created_at >= :t ORDER BY id ASC"),
                    {"u": username, "t": today_start}
                )
                records = res.fetchall()
                
                remainder = total_score - highest_score
                
                if records:
                    # 分配给最高分的记录
                    await conn.execute(sa_text("UPDATE practice_records SET score = :s WHERE id = :id"), {"s": highest_score, "id": records[0].id})
                    if remainder > 0:
                        if len(records) > 1:
                            await conn.execute(sa_text("UPDATE practice_records SET score = :s WHERE id = :id"), {"s": remainder, "id": records[1].id})
                        else:
                            await conn.execute(sa_text("INSERT INTO practice_records (username, score) VALUES (:u, :s)"), {"u": username, "s": remainder})
                else:
                    # 如果今天本来没有记录，需要插入新记录
                    await conn.execute(sa_text("INSERT INTO practice_records (username, score) VALUES (:u, :s)"), {"u": username, "s": highest_score})
                    if remainder > 0:
                        await conn.execute(sa_text("INSERT INTO practice_records (username, score) VALUES (:u, :s)"), {"u": username, "s": remainder})
                
                # 4. 同步更新总榜的 total_score 增量，并检查是否破总纪录
                await conn.execute(
                    sa_text("""
                        UPDATE user_leaderboard 
                        SET total_score = total_score + :diff,
                            highest_score = CASE WHEN :new_high > highest_score THEN :new_high ELSE highest_score END,
                            updated_at = datetime('now', 'localtime')
                        WHERE username = :u
                    """),
                    {"diff": diff, "new_high": highest_score, "u": username}
                )
            else:
                updates = []
                params = {"username": username}
                if total_score is not None:
                    updates.append('"total_score" = :total_score')
                    params["total_score"] = int(total_score)
                if highest_score is not None:
                    updates.append('"highest_score" = :highest_score')
                    params["highest_score"] = int(highest_score)
                updates.append("\"updated_at\" = datetime('now', 'localtime')")
                
                sql = sa_text(f'UPDATE user_leaderboard SET {", ".join(updates)} WHERE username = :username')
                await conn.execute(sql, params)
        
        log_admin_activity(
            actor,
            "修改排行榜分数",
            username,
            f"period={body.get('period', 'all')}, total_score={total_score}, highest_score={highest_score}",
        )
        print(f"[Admin Leaderboard] Updated scores for {username}")
        return JSONResponse({"success": True, "message": f"已更新 {username} 的分数"})
    except Exception as e:
        print(f"[Admin Leaderboard] Update error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/admin/leaderboard/{username}")
async def admin_delete_leaderboard(request: Request, username: str):
    """管理后台删除/重置排行榜记录"""
    actor = verify_admin_from_request(request)
    if not actor:
        return JSONResponse({"error": "未授权"}, status_code=403)
    
    period = request.query_params.get("period", "all")
    
    try:
        data_layer = get_data_layer()
        if not data_layer:
            return JSONResponse({"error": "数据库不可用"}, status_code=500)
        
        from sqlalchemy import text as sa_text
        from datetime import datetime
        engine = data_layer.engine
        
        async with engine.begin() as conn:
            if period == "today":
                # 重置今日练习
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                res = await conn.execute(
                    sa_text("SELECT SUM(score) as total FROM practice_records WHERE username = :u AND created_at >= :t"),
                    {"u": username, "t": today_start}
                )
                row = res.fetchone()
                today_score = row[0] if row and row[0] else 0
                
                await conn.execute(
                    sa_text("DELETE FROM mistake_details WHERE username = :u AND created_at >= :t"),
                    {"u": username, "t": today_start}
                )
                await conn.execute(
                    sa_text("DELETE FROM practice_records WHERE username = :u AND created_at >= :t"),
                    {"u": username, "t": today_start}
                )
                
                high_res = await conn.execute(
                    sa_text("SELECT MAX(score), COUNT(*) FROM practice_records WHERE username = :u"),
                    {"u": username}
                )
                high_row = high_res.fetchone()
                new_highest = high_row[0] if high_row and high_row[0] else 0
                new_count = high_row[1] if high_row and high_row[1] else 0
                
                await conn.execute(
                    sa_text("""
                        UPDATE user_leaderboard 
                        SET total_score = CASE WHEN total_score >= :ts THEN total_score - :ts ELSE 0 END,
                            highest_score = :nhs,
                            practice_count = :nc
                        WHERE username = :u
                    """),
                    {"ts": today_score, "nhs": new_highest, "nc": new_count, "u": username}
                )
                msg = f"已重置 {username} 的今日练习次数与记录"
            else:
                # 删除所有排行榜记录
                await conn.execute(
                    sa_text("DELETE FROM user_leaderboard WHERE username = :username"),
                    {"username": username}
                )
                await conn.execute(
                    sa_text("DELETE FROM mistake_details WHERE username = :username"),
                    {"username": username}
                )
                await conn.execute(
                    sa_text("DELETE FROM practice_records WHERE username = :username"),
                    {"username": username}
                )
                msg = f"已删除 {username} 的所有练习记录"
        
        log_admin_activity(actor, "重置排行榜记录", username, f"period={period}")
        print(f"[Admin Leaderboard] {msg}")
        return JSONResponse({"success": True, "message": msg})
    except Exception as e:
        print(f"[Admin Leaderboard] Delete error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== 每日一练提交 API ====================
from pydantic import BaseModel, Field, field_validator
from typing import List as TypingList

class MistakeDetailItem(BaseModel):
    """错题明细数据模型"""
    question_id: str = Field(default="", description="题目ID（在 /update 接口中可省略，由顶层 question_id 覆盖）")
    question_text: str = Field(default="", description="题目内容")
    user_answer: str = Field(default="", description="用户的错误答案")
    correct_answer: str = Field(default="", description="标准答案")
    analysis: str = Field(default="", description="题目解析")

    @field_validator("question_id", mode="before")
    @classmethod
    def coerce_question_id_to_str(cls, v):
        """兼容整数类型的 question_id，自动转为字符串"""
        if v is None:
            return ""
        return str(v)

class PracticeSubmitRequest(BaseModel):
    """练习成绩提交请求体模型"""
    username: str = Field(..., min_length=1, description="用户唯一标识")
    score: int = Field(..., ge=0, le=100, description="本次练习得分 (0-100)")
    correct_count: int = Field(..., ge=0, description="答对题数")
    wrong_count: int = Field(..., ge=0, description="答错题数")
    mistake_details: TypingList[MistakeDetailItem] = Field(default=[], description="错题明细列表")

from typing import Optional

class PracticeStartRequest(BaseModel):
    username: str = Field(..., min_length=1)

class PracticeUpdateRequest(BaseModel):
    username: str = Field(..., min_length=1)
    question_id: str = Field(...)
    is_correct: bool = Field(...)
    mistake_detail: Optional[MistakeDetailItem] = Field(default=None)

    @field_validator("question_id", mode="before")
    @classmethod
    def coerce_question_id_to_str(cls, v):
        return str(v)


async def _ensure_practice_tables():
    """确保练习系统所需的数据库表已创建（幂等操作）
    
    在每次 API 调用时执行，使用 CREATE TABLE IF NOT EXISTS 保证安全。
    避免对已有数据库执行 init_db.py 时跳过新表创建的情况。
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    db_url = f"sqlite+aiosqlite:///{DB_PATH}"
    engine = create_async_engine(db_url)

    create_sql_list = [
        # 练习记录表
        """
        CREATE TABLE IF NOT EXISTS practice_records (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "username" TEXT NOT NULL,
            "score" INTEGER NOT NULL DEFAULT 0,
            "correct_count" INTEGER NOT NULL DEFAULT 0,
            "wrong_count" INTEGER NOT NULL DEFAULT 0,
            "current_streak" INTEGER NOT NULL DEFAULT 0,
            "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        # 错题本表
        """
        CREATE TABLE IF NOT EXISTS mistake_details (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "record_id" INTEGER NOT NULL,
            "username" TEXT NOT NULL,
            "question_id" TEXT NOT NULL,
            "question_text" TEXT NOT NULL DEFAULT '',
            "user_answer" TEXT NOT NULL DEFAULT '',
            "correct_answer" TEXT NOT NULL DEFAULT '',
            "analysis" TEXT NOT NULL DEFAULT '',
            "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY ("record_id") REFERENCES practice_records("id")
        )
        """,
        # 用户排行榜表
        """
        CREATE TABLE IF NOT EXISTS user_leaderboard (
            "username" TEXT PRIMARY KEY,
            "total_score" INTEGER NOT NULL DEFAULT 0,
            "highest_score" INTEGER NOT NULL DEFAULT 0,
            "practice_count" INTEGER NOT NULL DEFAULT 0,
            "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        # 索引
        'CREATE INDEX IF NOT EXISTS idx_practice_records_username ON practice_records("username")',
        'CREATE INDEX IF NOT EXISTS idx_practice_records_created_at ON practice_records("created_at")',
        'CREATE INDEX IF NOT EXISTS idx_mistake_details_record_id ON mistake_details("record_id")',
        'CREATE INDEX IF NOT EXISTS idx_mistake_details_username ON mistake_details("username")',
        'CREATE INDEX IF NOT EXISTS idx_user_leaderboard_total_score ON user_leaderboard("total_score")',
    ]

    try:
        async with engine.begin() as conn:
            for sql in create_sql_list:
                await conn.execute(sa_text(sql.strip()))
            # 防止旧表没有 current_streak，安全执行 alter
            try:
                await conn.execute(sa_text("ALTER TABLE practice_records ADD COLUMN current_streak INTEGER NOT NULL DEFAULT 0;"))
            except Exception:
                pass
        print("[Practice] 练习系统数据表已就绪")
    except Exception as e:
        print(f"[Practice] 建表异常（可忽略如表已存在）: {e}")
    finally:
        await engine.dispose()


from fastapi import HTTPException
from datetime import datetime

@app.post("/v1/practice/start")
async def start_practice(body: PracticeStartRequest):
    """每日一练初始化发令枪"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    await _ensure_practice_tables()
    db_url = f"sqlite+aiosqlite:///{DB_PATH}"
    engine = create_async_engine(db_url)
    now_date = datetime.now().strftime("%Y-%m-%d")

    try:
        async with engine.begin() as conn:
            check_sql = sa_text("""
                SELECT id FROM practice_records 
                WHERE username = :username 
                AND date(created_at) = :today 
                LIMIT 1
            """)
            result = await conn.execute(check_sql, {"username": body.username, "today": now_date})
            if result.fetchone():
                return JSONResponse(
                    status_code=403, 
                    content={"error": "今日已完成练习或已有中断记录，不可重复开启"}
                )

            insert_sql = sa_text("""
                INSERT INTO practice_records (username, score, correct_count, wrong_count, current_streak, created_at)
                VALUES (:username, 0, 0, 0, 0, datetime('now', 'localtime'))
            """)
            await conn.execute(insert_sql, {"username": body.username})

        return {"success": True, "message": "练习已初始化"}
    except Exception as e:
        print(f"[Practice Start] Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        await engine.dispose()

@app.post("/v1/practice/update")
async def update_practice(body: PracticeUpdateRequest):
    """答题引擎：实时处理单题结果"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    await _ensure_practice_tables()
    db_url = f"sqlite+aiosqlite:///{DB_PATH}"
    engine = create_async_engine(db_url)
    now_date = datetime.now().strftime("%Y-%m-%d")

    try:
        async with engine.begin() as conn:
            # 1. 查询当日的练习记录
            record_sql = sa_text("""
                SELECT id, score, correct_count, wrong_count, current_streak 
                FROM practice_records 
                WHERE username = :username AND date(created_at) = :today 
                ORDER BY id DESC LIMIT 1
            """)
            res = await conn.execute(record_sql, {"username": body.username, "today": now_date})
            record = res.fetchone()
            
            if not record:
                return JSONResponse(status_code=400, content={"error": "未找到今日的练习记录，请先调用 /v1/practice/start"})
            
            rec_id, score, correct_c, wrong_c, streak = record
            
            # 校验答题数量
            answered_count = correct_c + wrong_c
            if answered_count >= 5:
                return JSONResponse(status_code=400, content={"error": "今日练习答题数已满 5 题"})

            score_diff = 0
            if body.is_correct:
                score += 10
                score_diff += 10
                streak += 1
                correct_c += 1
                
                # 连对 5 题额外奖励 20 分
                if streak == 5:
                    score += 20
                    score_diff += 20
            else:
                streak = 0
                wrong_c += 1
                
                # 记录错题详细内容
                mistake = body.mistake_detail
                if mistake:
                    insert_mistake = sa_text("""
                        INSERT INTO mistake_details 
                        (record_id, username, question_id, question_text, user_answer, correct_answer, analysis, created_at)
                        VALUES (:rid, :usr, :qid, :qt, :ua, :ca, :an, datetime('now', 'localtime'))
                    """)
                    await conn.execute(insert_mistake, {
                        "rid": rec_id,
                        "usr": body.username,
                        "qid": str(body.question_id),
                        "qt": mistake.question_text,
                        "ua": mistake.user_answer,
                        "ca": mistake.correct_answer,
                        "an": mistake.analysis
                    })
                else: 
                     insert_mistake = sa_text("""
                        INSERT INTO mistake_details 
                        (record_id, username, question_id, question_text, user_answer, correct_answer, analysis, created_at)
                        VALUES (:rid, :usr, :qid, '', '', '', '', datetime('now', 'localtime'))
                    """)
                     await conn.execute(insert_mistake, {
                        "rid": rec_id,
                        "usr": body.username,
                        "qid": str(body.question_id)
                    })

            # 更新数据库的单条记录
            update_rec_sql = sa_text("""
                UPDATE practice_records 
                SET score = :score, correct_count = :cc, wrong_count = :wc, current_streak = :streak 
                WHERE id = :rid
            """)
            await conn.execute(update_rec_sql, {
                "score": score,
                "cc": correct_c,
                "wc": wrong_c,
                "streak": streak,
                "rid": rec_id
            })

            # 2. 累加模式全量同步至 user_leaderboard
            existing_lb = await conn.execute(
                sa_text("SELECT total_score, highest_score, practice_count FROM user_leaderboard WHERE username = :username"),
                {"username": body.username}
            )
            lb_row = existing_lb.fetchone()
            
            if lb_row:
                old_total, old_highest, old_count = lb_row
                new_total = old_total + score_diff
                new_highest = max(old_highest, score)
                
                # 今日首题则增加练习活跃天数/次数
                if answered_count == 0:
                    new_count = old_count + 1
                else:
                    new_count = old_count

                await conn.execute(sa_text("""
                    UPDATE user_leaderboard 
                    SET total_score = :ts, highest_score = :hs, practice_count = :pc, updated_at = datetime('now', 'localtime')
                    WHERE username = :usr
                """), {"ts": new_total, "hs": new_highest, "pc": new_count, "usr": body.username})
            else:
                await conn.execute(sa_text("""
                    INSERT INTO user_leaderboard (username, total_score, highest_score, practice_count, updated_at)
                    VALUES (:usr, :ts, :hs, 1, datetime('now', 'localtime'))
                """), {"usr": body.username, "ts": score_diff, "hs": score})

        return {
            "success": True, 
            "message": "更新成功", 
            "data": {
                "score": score, 
                "current_streak": streak, 
                "answered_count": answered_count + 1
            }
        }
    except Exception as e:
        print(f"[Practice Update] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        await engine.dispose()

# ==================== 作业成绩提交 API ====================

class AssignmentSubmitRequest(BaseModel):
    """作业成绩提交请求体"""
    username: str = Field(..., min_length=1, description="用户唯一标识")
    score: int = Field(..., ge=0, description="作业得分")
    feedback: str = Field(default="", description="作业反馈/评语")

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score_to_int(cls, v):
        """兼容字符串类型的 score，自动转为整数"""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 0
        return v


@app.post("/v1/assignment/submit")
async def submit_assignment(body: AssignmentSubmitRequest):
    """作业成绩提交接口

    供 Coze 工作流在批改作业完成后回调，
    将成绩和反馈推送到本系统，同时更新排行榜。

    流程：
    1. 确保作业记录表存在
    2. 事务中完成：插入作业记录 → 更新排行榜
    3. 计算全站排名和击败百分比
    4. 返回排名结果
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    try:
        # ========== 第一步：确保数据表已创建 ==========
        await _ensure_practice_tables()

        # 额外确保 assignment_records 表存在
        db_url = f"sqlite+aiosqlite:///{DB_PATH}"
        engine = create_async_engine(db_url)

        async with engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS assignment_records (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "username" TEXT NOT NULL,
                    "score" INTEGER NOT NULL DEFAULT 0,
                    "feedback" TEXT NOT NULL DEFAULT '',
                    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """))
            await conn.execute(sa_text('CREATE INDEX IF NOT EXISTS idx_assignment_records_username ON assignment_records("username")'))
            await conn.execute(sa_text('CREATE INDEX IF NOT EXISTS idx_assignment_records_created_at ON assignment_records("created_at")'))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ========== 第二步：事务写入数据 ==========
        async with engine.begin() as conn:
            # --- 2.1 插入作业成绩记录 ---
            insert_sql = sa_text("""
                INSERT INTO assignment_records (username, score, feedback, created_at)
                VALUES (:username, :score, :feedback, :created_at)
            """)
            await conn.execute(insert_sql, {
                "username": body.username,
                "score": body.score,
                "feedback": body.feedback,
                "created_at": now_str,
            })
            print(f"[Assignment] 插入作业记录: user={body.username}, score={body.score}")

            # --- 2.2 更新用户排行榜（UPSERT 策略，与 /v1/practice/submit 完全一致） ---
            existing = await conn.execute(
                sa_text("SELECT total_score, highest_score, practice_count FROM user_leaderboard WHERE username = :username"),
                {"username": body.username}
            )
            row = existing.fetchone()

            if row:
                old_total = row[0]
                old_highest = row[1]
                old_count = row[2]
                new_total = old_total + body.score
                new_highest = max(old_highest, body.score)
                new_count = old_count + 1

                await conn.execute(sa_text("""
                    UPDATE user_leaderboard 
                    SET total_score = :total_score, 
                        highest_score = :highest_score, 
                        practice_count = :practice_count, 
                        updated_at = :updated_at
                    WHERE username = :username
                """), {
                    "total_score": new_total,
                    "highest_score": new_highest,
                    "practice_count": new_count,
                    "updated_at": now_str,
                    "username": body.username,
                })
                print(f"[Assignment] 更新排行榜: user={body.username}, total={new_total}, highest={new_highest}, count={new_count}")
            else:
                new_total = body.score
                await conn.execute(sa_text("""
                    INSERT INTO user_leaderboard (username, total_score, highest_score, practice_count, updated_at)
                    VALUES (:username, :total_score, :highest_score, :practice_count, :updated_at)
                """), {
                    "username": body.username,
                    "total_score": body.score,
                    "highest_score": body.score,
                    "practice_count": 1,
                    "updated_at": now_str,
                })
                new_total = body.score
                print(f"[Assignment] 新建排行榜记录: user={body.username}, total={new_total}")

        # ========== 第三步：计算排名和击败百分比 ==========
        async with engine.connect() as conn:
            total_users_row = await conn.execute(
                sa_text("SELECT COUNT(*) FROM user_leaderboard")
            )
            total_users = total_users_row.scalar() or 1

            rank_row = await conn.execute(sa_text("""
                SELECT COUNT(*) + 1 
                FROM user_leaderboard 
                WHERE total_score > (
                    SELECT total_score FROM user_leaderboard WHERE username = :username
                )
            """), {"username": body.username})
            rank = rank_row.scalar() or 1

            beaten_count = total_users - rank
            if total_users <= 1:
                beat_percentage = 100.0
            else:
                beat_percentage = round((beaten_count / (total_users - 1)) * 100, 1)

            user_total_row = await conn.execute(
                sa_text("SELECT total_score FROM user_leaderboard WHERE username = :username"),
                {"username": body.username}
            )
            user_total_score = user_total_row.scalar() or 0

        await engine.dispose()

        # ========== 第四步：返回结果 ==========
        print(f"[Assignment] 排名计算完成: user={body.username}, rank={rank}/{total_users}, beat={beat_percentage}%")

        return JSONResponse({
            "code": 200,
            "msg": "success",
            "data": {
                "rank": rank,
                "beat_percentage": f"{beat_percentage}%",
                "total_score": user_total_score,
                "total_users": total_users,
                "assignment_score": body.score,
                "feedback": body.feedback,
            }
        })

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Assignment] 提交异常: {e}\n{error_detail}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "msg": f"服务器内部错误: {str(e)}",
                "data": None,
            }
        )

@app.post("/v1/practice/submit")
async def submit_practice(body: PracticeSubmitRequest):
    """每日一练成绩提交接口
    
    供外部系统（如 Coze 工作流）在用户完成练习后回调，
    将成绩和错题信息推送到本系统。
    
    流程：
    1. 参数校验（Pydantic 自动完成）
    2. 确保练习系统表存在
    3. 事务中完成：插入练习记录 → 插入错题明细 → 更新排行榜
    4. 计算全站排名和击败百分比
    5. 返回排名结果
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    try:
        # ========== 第一步：确保数据表已创建 ==========
        await _ensure_practice_tables()

        # ========== 第二步：事务写入数据 ==========
        db_url = f"sqlite+aiosqlite:///{DB_PATH}"
        engine = create_async_engine(db_url)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with engine.begin() as conn:
            # --- 2.1 插入本次练习记录 ---
            insert_record_sql = sa_text("""
                INSERT INTO practice_records (username, score, correct_count, wrong_count, created_at)
                VALUES (:username, :score, :correct_count, :wrong_count, :created_at)
            """)
            result = await conn.execute(insert_record_sql, {
                "username": body.username,
                "score": body.score,
                "correct_count": body.correct_count,
                "wrong_count": body.wrong_count,
                "created_at": now_str,
            })
            # 获取刚插入记录的自增 ID
            record_id_row = await conn.execute(sa_text("SELECT last_insert_rowid()"))
            record_id = record_id_row.scalar()
            print(f"[Practice] 插入练习记录成功: record_id={record_id}, user={body.username}, score={body.score}")

            # --- 2.2 批量插入错题明细 ---
            if body.mistake_details:
                insert_mistake_sql = sa_text("""
                    INSERT INTO mistake_details 
                        (record_id, username, question_id, question_text, user_answer, correct_answer, analysis, created_at)
                    VALUES 
                        (:record_id, :username, :question_id, :question_text, :user_answer, :correct_answer, :analysis, :created_at)
                """)
                mistake_params = []
                for item in body.mistake_details:
                    mistake_params.append({
                        "record_id": record_id,
                        "username": body.username,
                        "question_id": item.question_id,
                        "question_text": item.question_text,
                        "user_answer": item.user_answer,
                        "correct_answer": item.correct_answer,
                        "analysis": item.analysis,
                        "created_at": now_str,
                    })
                # 使用 executemany 批量插入提升性能
                for params in mistake_params:
                    await conn.execute(insert_mistake_sql, params)
                print(f"[Practice] 插入错题明细 {len(mistake_params)} 条")

            # --- 2.3 更新用户排行榜（UPSERT 策略） ---
            # 先查询该用户是否已有排行榜记录
            existing = await conn.execute(
                sa_text("SELECT total_score, highest_score, practice_count FROM user_leaderboard WHERE username = :username"),
                {"username": body.username}
            )
            row = existing.fetchone()

            if row:
                # 已存在：累加总分、更新最高分、练习次数 +1
                old_total = row[0]
                old_highest = row[1]
                old_count = row[2]
                new_total = old_total + body.score
                new_highest = max(old_highest, body.score)
                new_count = old_count + 1

                await conn.execute(sa_text("""
                    UPDATE user_leaderboard 
                    SET total_score = :total_score, 
                        highest_score = :highest_score, 
                        practice_count = :practice_count, 
                        updated_at = :updated_at
                    WHERE username = :username
                """), {
                    "total_score": new_total,
                    "highest_score": new_highest,
                    "practice_count": new_count,
                    "updated_at": now_str,
                    "username": body.username,
                })
                print(f"[Practice] 更新排行榜: user={body.username}, total={new_total}, highest={new_highest}, count={new_count}")
            else:
                # 不存在：首次录入
                new_total = body.score
                await conn.execute(sa_text("""
                    INSERT INTO user_leaderboard (username, total_score, highest_score, practice_count, updated_at)
                    VALUES (:username, :total_score, :highest_score, :practice_count, :updated_at)
                """), {
                    "username": body.username,
                    "total_score": body.score,
                    "highest_score": body.score,
                    "practice_count": 1,
                    "updated_at": now_str,
                })
                new_total = body.score
                print(f"[Practice] 新建排行榜记录: user={body.username}, total={new_total}")

        # ========== 第三步：计算排名和击败百分比 ==========
        # 使用新的连接进行只读查询（事务已提交，数据已持久化）
        async with engine.connect() as conn:
            # 3.1 获取全站用户总数
            total_users_row = await conn.execute(
                sa_text("SELECT COUNT(*) FROM user_leaderboard")
            )
            total_users = total_users_row.scalar() or 1

            # 3.2 获取当前用户的排名
            # 排名规则：按 total_score 降序，相同分数则按 highest_score 降序
            rank_row = await conn.execute(sa_text("""
                SELECT COUNT(*) + 1 
                FROM user_leaderboard 
                WHERE total_score > (
                    SELECT total_score FROM user_leaderboard WHERE username = :username
                )
            """), {"username": body.username})
            rank = rank_row.scalar() or 1

            # 3.3 计算击败百分比
            # 击败的用户数 = 排在该用户之后的用户数
            beaten_count = total_users - rank
            if total_users <= 1:
                beat_percentage = 100.0
            else:
                beat_percentage = round((beaten_count / (total_users - 1)) * 100, 1)

            # 3.4 获取该用户最新的 total_score
            user_total_row = await conn.execute(
                sa_text("SELECT total_score FROM user_leaderboard WHERE username = :username"),
                {"username": body.username}
            )
            user_total_score = user_total_row.scalar() or 0

        await engine.dispose()

        # ========== 第四步：返回结果 ==========
        print(f"[Practice] 排名计算完成: user={body.username}, rank={rank}/{total_users}, beat={beat_percentage}%")

        return JSONResponse({
            "code": 200,
            "msg": "success",
            "data": {
                "rank": rank,
                "beat_percentage": f"{beat_percentage}%",
                "total_score": user_total_score,
                "total_users": total_users,
            }
        })

    except Exception as e:
        # 全局异常兜底，返回标准化错误响应
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Practice] 提交异常: {e}\n{error_detail}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "msg": f"服务器内部错误: {str(e)}",
                "data": None,
            }
        )


@app.get("/v1/practice/leaderboard")
async def get_practice_leaderboard(limit: int = 50, username: str = None, period: str = "all"):
    """每日一练排行榜查询接口

    查询全站普通用户的练习成绩排名（管理员不参与排行）。
    支持可选的 username 参数，用于同时返回指定用户的排名信息。

    参数:
        limit: 返回的排行榜条目数（默认50）
        username: 可选，查询指定用户的排名
        period: 排行榜周期，'all'=历史累计（默认），'today'=今日
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sa_text

    try:
        # 确保表存在
        await _ensure_practice_tables()

        db_url = f"sqlite+aiosqlite:///{DB_PATH}"
        engine = create_async_engine(db_url)

        # 获取所有管理员用户名列表（用于排除）
        admin_usernames = [
            uname for uname, udata in users_db.items()
            if udata.get("role") == "admin"
        ]

        async with engine.connect() as conn:
            if period == "today":
                # ========== 今日排行：从 practice_records 按今天日期聚合 ==========
                today_str = datetime.now().strftime("%Y-%m-%d")

                if admin_usernames:
                    placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                    leaderboard_sql = sa_text(f"""
                        SELECT username,
                               COALESCE(SUM(score), 0) as total_score,
                               COALESCE(MAX(score), 0) as highest_score,
                               COUNT(*) as practice_count
                        FROM practice_records
                        WHERE created_at >= :today_start
                          AND created_at < :today_end
                          AND username NOT IN ({placeholders})
                        GROUP BY username
                        ORDER BY total_score DESC, highest_score DESC, MAX(created_at) ASC
                        LIMIT :limit
                    """)
                    params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                    params["today_start"] = today_str + " 00:00:00"
                    params["today_end"] = today_str + " 23:59:59"
                    params["limit"] = limit
                else:
                    leaderboard_sql = sa_text("""
                        SELECT username,
                               COALESCE(SUM(score), 0) as total_score,
                               COALESCE(MAX(score), 0) as highest_score,
                               COUNT(*) as practice_count
                        FROM practice_records
                        WHERE created_at >= :today_start
                          AND created_at < :today_end
                        GROUP BY username
                        ORDER BY total_score DESC, highest_score DESC, MAX(created_at) ASC
                        LIMIT :limit
                    """)
                    params = {
                        "today_start": today_str + " 00:00:00",
                        "today_end": today_str + " 23:59:59",
                        "limit": limit,
                    }

                result = await conn.execute(leaderboard_sql, params)
                rows = result.fetchall()

                leaderboard = []
                for idx, row in enumerate(rows, start=1):
                    leaderboard.append({
                        "rank": idx,
                        "username": row[0],
                        "total_score": row[1],
                        "highest_score": row[2],
                        "practice_count": row[3],
                    })

                # 今日参与用户总数
                if admin_usernames:
                    placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                    total_sql = sa_text(f"""
                        SELECT COUNT(DISTINCT username) FROM practice_records
                        WHERE created_at >= :today_start AND created_at < :today_end
                        AND username NOT IN ({placeholders})
                    """)
                    total_params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                    total_params["today_start"] = today_str + " 00:00:00"
                    total_params["today_end"] = today_str + " 23:59:59"
                else:
                    total_sql = sa_text("""
                        SELECT COUNT(DISTINCT username) FROM practice_records
                        WHERE created_at >= :today_start AND created_at < :today_end
                    """)
                    total_params = {
                        "today_start": today_str + " 00:00:00",
                        "today_end": today_str + " 23:59:59",
                    }

                total_row = await conn.execute(total_sql, total_params)
                total_users = total_row.scalar() or 0

                # 今日排行中该用户的排名信息
                my_rank_info = None
                if username and username not in admin_usernames:
                    user_sql = sa_text("""
                        SELECT COALESCE(SUM(score), 0), COALESCE(MAX(score), 0), COUNT(*)
                        FROM practice_records
                        WHERE username = :username
                          AND created_at >= :today_start
                          AND created_at < :today_end
                    """)
                    user_row = await conn.execute(user_sql, {
                        "username": username,
                        "today_start": today_str + " 00:00:00",
                        "today_end": today_str + " 23:59:59",
                    })
                    user_data = user_row.fetchone()
                    if user_data:
                        user_total = user_data[0]
                        if admin_usernames:
                            placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                            rank_sql = sa_text(f"""
                                SELECT COUNT(*) + 1 FROM (
                                    SELECT username, COALESCE(SUM(score), 0) as ts
                                    FROM practice_records
                                    WHERE created_at >= :today_start
                                      AND created_at < :today_end
                                      AND username NOT IN ({placeholders})
                                    GROUP BY username
                                    HAVING ts > :user_score
                                )
                            """)
                            rank_params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                        else:
                            rank_sql = sa_text("""
                                SELECT COUNT(*) + 1 FROM (
                                    SELECT username, COALESCE(SUM(score), 0) as ts
                                    FROM practice_records
                                    WHERE created_at >= :today_start
                                      AND created_at < :today_end
                                    GROUP BY username
                                    HAVING ts > :user_score
                                )
                            """)
                            rank_params = {}
                        rank_params["today_start"] = today_str + " 00:00:00"
                        rank_params["today_end"] = today_str + " 23:59:59"
                        rank_params["user_score"] = user_total

                        rank_row = await conn.execute(rank_sql, rank_params)
                        my_rank = rank_row.scalar() or 1

                        beaten_count = total_users - my_rank
                        beat_pct = round((beaten_count / max(total_users - 1, 1)) * 100, 1) if total_users > 1 else 100.0

                        my_rank_info = {
                            "rank": my_rank,
                            "total_score": user_total,
                            "highest_score": user_data[1],
                            "practice_count": user_data[2],
                            "beat_percentage": f"{beat_pct}%",
                        }

            else:
                # ========== 历史累计排行：从 user_leaderboard 表查询 ==========
                if admin_usernames:
                    placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                    leaderboard_sql = sa_text(f"""
                        SELECT username, total_score, highest_score, practice_count, updated_at
                        FROM user_leaderboard
                        WHERE username NOT IN ({placeholders})
                        ORDER BY total_score DESC, highest_score DESC
                        LIMIT :limit
                    """)
                    params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                    params["limit"] = limit
                else:
                    leaderboard_sql = sa_text("""
                        SELECT username, total_score, highest_score, practice_count, updated_at
                        FROM user_leaderboard
                        ORDER BY total_score DESC, highest_score DESC
                        LIMIT :limit
                    """)
                    params = {"limit": limit}

                result = await conn.execute(leaderboard_sql, params)
                rows = result.fetchall()

                leaderboard = []
                for idx, row in enumerate(rows, start=1):
                    leaderboard.append({
                        "rank": idx,
                        "username": row[0],
                        "total_score": row[1],
                        "highest_score": row[2],
                        "practice_count": row[3],
                        "updated_at": row[4],
                    })

                # 全站非管理员用户总人数
                if admin_usernames:
                    placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                    total_sql = sa_text(f"SELECT COUNT(*) FROM user_leaderboard WHERE username NOT IN ({placeholders})")
                    total_params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                else:
                    total_sql = sa_text("SELECT COUNT(*) FROM user_leaderboard")
                    total_params = {}

                total_row = await conn.execute(total_sql, total_params)
                total_users = total_row.scalar() or 0

                # 指定用户的排名信息
                my_rank_info = None
                if username and username not in admin_usernames:
                    user_row = await conn.execute(
                        sa_text("SELECT total_score, highest_score, practice_count FROM user_leaderboard WHERE username = :username"),
                        {"username": username}
                    )
                    user_data = user_row.fetchone()
                    if user_data:
                        if admin_usernames:
                            placeholders = ", ".join([f":admin_{i}" for i in range(len(admin_usernames))])
                            rank_sql = sa_text(f"""
                                SELECT COUNT(*) + 1 FROM user_leaderboard
                                WHERE total_score > :user_score
                                AND username NOT IN ({placeholders})
                            """)
                            rank_params = {f"admin_{i}": name for i, name in enumerate(admin_usernames)}
                            rank_params["user_score"] = user_data[0]
                        else:
                            rank_sql = sa_text("SELECT COUNT(*) + 1 FROM user_leaderboard WHERE total_score > :user_score")
                            rank_params = {"user_score": user_data[0]}

                        rank_row = await conn.execute(rank_sql, rank_params)
                        my_rank = rank_row.scalar() or 1

                        beaten_count = total_users - my_rank
                        beat_pct = round((beaten_count / max(total_users - 1, 1)) * 100, 1) if total_users > 1 else 100.0

                        my_rank_info = {
                            "rank": my_rank,
                            "total_score": user_data[0],
                            "highest_score": user_data[1],
                            "practice_count": user_data[2],
                            "beat_percentage": f"{beat_pct}%",
                        }

        await engine.dispose()

        return JSONResponse({
            "code": 200,
            "msg": "success",
            "data": {
                "leaderboard": leaderboard,
                "total_users": total_users,
                "my_rank": my_rank_info,
                "period": period,
            }
        })

    except Exception as e:
        import traceback
        print(f"[Practice] 排行榜查询异常: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"code": 500, "msg": f"服务器内部错误: {str(e)}", "data": None}
        )


# ==================== 路由重排 ====================
# Chainlit 的 server.py 在 app.include_router(router) 时注册了兜底路由：
#   @router.get("/{full_path:path}") → 返回 SPA HTML
# 该路由匹配所有 GET 路径，且注册顺序早于我们的 @app.get() 路由。
# FastAPI/Starlette 按注册顺序匹配路由，先匹配的先命中。
# 因此需要将我们的 admin 路由移到兜底路由之前。
def _reorder_admin_routes():
    """将 admin 相关路由移到 Chainlit 兜底路由之前"""
    from starlette.routing import Route

    admin_routes = []
    other_routes = []

    for route in app.routes:
        if isinstance(route, Route) and hasattr(route, 'path'):
            path = route.path
            if (
                path.startswith("/admin")
                or path.startswith("/api/admin")
                or path.startswith("/v1/")
                or path.startswith("/api/coze")
            ):
                admin_routes.append(route)
                continue
        other_routes.append(route)

    if admin_routes:
        # 找到兜底路由的位置（通常是最后一个 GET "/{full_path:path}"）
        insert_pos = len(other_routes)
        for i, route in enumerate(other_routes):
            if isinstance(route, Route) and hasattr(route, 'path') and route.path == "/{full_path:path}":
                insert_pos = i
                break

        # 将 admin 路由插入到兜底路由之前
        new_routes = other_routes[:insert_pos] + admin_routes + other_routes[insert_pos:]
        app.routes.clear()
        app.routes.extend(new_routes)
        print(f"[Admin] Reordered {len(admin_routes)} admin routes before catch-all route")

_reorder_admin_routes()
