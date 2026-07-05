"""DB-backed agent registry and routing configuration."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class SubscriptionConfig:
    topic: str
    base_bid: float
    basic_bonus: float = 0.0
    advanced_bonus: float = 0.0


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    display_name: str
    description: str
    agent_type: str
    bot_id: str
    enabled: bool
    system_builtin: bool
    locked: bool
    exclusive: bool
    priority: int
    context_policy: str
    created_at: str = ""
    updated_at: str = ""
    subscriptions: Dict[str, SubscriptionConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteTopic:
    topic: str
    display_name: str
    description: str
    is_teaching: bool
    is_exclusive: bool
    route_priority: int
    enabled: bool


@dataclass(frozen=True)
class RouteConfig:
    topics: Dict[str, RouteTopic]
    topic_keywords: Dict[str, Dict[str, List[str]]]
    practice_exact: List[str]
    practice_contains: List[str]
    practice_loose: List[str]
    practice_negative: List[str]
    practice_exit: List[str]
    difficulty_basic: List[str]
    difficulty_advanced: List[str]
    off_topic_blacklist: List[str]
    domain_terms: List[str]
    loose_trigger_max_len: int = 12
    off_topic_reply: str = ""


@dataclass(frozen=True)
class RegistrySnapshot:
    agents: Dict[str, AgentConfig]
    route_config: RouteConfig
    version: str


_AGENT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")
_AGENT_TYPES = {"coze_chat", "coze_workflow"}
_CONTEXT_POLICIES = {"on_switch_recent_2", "none"}


@contextmanager
def _connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _bool(value: Any) -> bool:
    return bool(int(value or 0))


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_agent(row: sqlite3.Row, subscriptions: Dict[str, SubscriptionConfig]) -> AgentConfig:
    return AgentConfig(
        agent_id=row["agent_id"],
        display_name=row["display_name"],
        description=row["description"] or "",
        agent_type=row["agent_type"],
        bot_id=row["bot_id"] or "",
        enabled=_bool(row["enabled"]),
        system_builtin=_bool(row["system_builtin"]),
        locked=_bool(row["locked"]),
        exclusive=_bool(row["exclusive"]),
        priority=_int(row["priority"], 100),
        context_policy=row["context_policy"] or "on_switch_recent_2",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
        subscriptions=subscriptions,
    )


def _as_topic(row: sqlite3.Row) -> RouteTopic:
    return RouteTopic(
        topic=row["topic"],
        display_name=row["display_name"],
        description=row["description"] or "",
        is_teaching=_bool(row["is_teaching"]),
        is_exclusive=_bool(row["is_exclusive"]),
        route_priority=_int(row["route_priority"], 100),
        enabled=_bool(row["enabled"]),
    )


def _agent_to_dict(agent: AgentConfig) -> Dict[str, Any]:
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.display_name,
        "description": agent.description,
        "agent_type": agent.agent_type,
        "bot_id": agent.bot_id,
        "enabled": agent.enabled,
        "system_builtin": agent.system_builtin,
        "locked": agent.locked,
        "exclusive": agent.exclusive,
        "priority": agent.priority,
        "context_policy": agent.context_policy,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
        "subscription_count": len(agent.subscriptions),
        "subscriptions": [
            {
                "topic": sub.topic,
                "base_bid": sub.base_bid,
                "basic_bonus": sub.basic_bonus,
                "advanced_bonus": sub.advanced_bonus,
            }
            for sub in sorted(agent.subscriptions.values(), key=lambda item: item.topic)
        ],
    }


def _topic_to_dict(topic: RouteTopic) -> Dict[str, Any]:
    return {
        "topic": topic.topic,
        "display_name": topic.display_name,
        "description": topic.description,
        "is_teaching": topic.is_teaching,
        "is_exclusive": topic.is_exclusive,
        "route_priority": topic.route_priority,
        "enabled": topic.enabled,
    }


def _read_subscriptions(conn: sqlite3.Connection, enabled_topics: Optional[set[str]] = None) -> Dict[str, Dict[str, SubscriptionConfig]]:
    rows = conn.execute(
        """
        SELECT agent_id, topic, base_bid, basic_bonus, advanced_bonus
        FROM agent_subscriptions
        ORDER BY agent_id, topic
        """
    ).fetchall()
    by_agent: Dict[str, Dict[str, SubscriptionConfig]] = {}
    for row in rows:
        topic = row["topic"]
        if enabled_topics is not None and topic not in enabled_topics:
            continue
        by_agent.setdefault(row["agent_id"], {})[topic] = SubscriptionConfig(
            topic=topic,
            base_bid=_float(row["base_bid"]),
            basic_bonus=_float(row["basic_bonus"]),
            advanced_bonus=_float(row["advanced_bonus"]),
        )
    return by_agent


def _read_route_config(conn: sqlite3.Connection, only_enabled: bool = True) -> RouteConfig:
    topic_sql = """
        SELECT topic, display_name, description, is_teaching, is_exclusive, route_priority, enabled
        FROM route_topics
    """
    if only_enabled:
        topic_sql += " WHERE enabled = 1"
    topic_sql += " ORDER BY route_priority ASC, topic ASC"

    topics = {
        row["topic"]: _as_topic(row)
        for row in conn.execute(topic_sql).fetchall()
    }

    topic_keywords: Dict[str, Dict[str, List[str]]] = {
        topic: {"strong": [], "weak": [], "pattern": []}
        for topic in topics
    }
    practice = {"exact": [], "contains": [], "loose": [], "negative": [], "exit": []}
    global_words = {
        "difficulty_basic": [],
        "difficulty_advanced": [],
        "off_topic": [],
        "domain": [],
    }

    for row in conn.execute(
        """
        SELECT scope, topic, kind, keyword
        FROM route_keywords
        WHERE enabled = 1
        ORDER BY priority ASC, id ASC
        """
    ).fetchall():
        scope = row["scope"]
        topic = row["topic"]
        kind = row["kind"]
        keyword = row["keyword"]
        if scope == "topic" and topic in topic_keywords and kind in topic_keywords[topic]:
            topic_keywords[topic][kind].append(keyword)
        elif scope == "practice" and kind in practice:
            practice[kind].append(keyword)
        elif scope == "global" and kind in global_words:
            global_words[kind].append(keyword)

    settings = {
        row["key"]: row["value"]
        for row in conn.execute("SELECT key, value FROM route_settings").fetchall()
    }

    return RouteConfig(
        topics=topics,
        topic_keywords=topic_keywords,
        practice_exact=practice["exact"],
        practice_contains=practice["contains"],
        practice_loose=practice["loose"],
        practice_negative=practice["negative"],
        practice_exit=practice["exit"],
        difficulty_basic=global_words["difficulty_basic"],
        difficulty_advanced=global_words["difficulty_advanced"],
        off_topic_blacklist=global_words["off_topic"],
        domain_terms=global_words["domain"],
        loose_trigger_max_len=_int(settings.get("loose_trigger_max_len"), 12),
        # SQLite 字符串字面量不处理转义序列：种子迁移（以及管理端可能录入）
        # 的字面 \n 需要在加载时还原为真实换行，否则会原样输出给用户
        off_topic_reply=(settings.get("off_topic_reply") or "").replace("\\n", "\n"),
    )


def load_registry(db_path: str) -> RegistrySnapshot:
    with _connect(db_path) as conn:
        route_config = _read_route_config(conn, only_enabled=True)
        enabled_topics = set(route_config.topics)
        subscriptions = _read_subscriptions(conn, enabled_topics)
        agents = {
            row["agent_id"]: _as_agent(row, subscriptions.get(row["agent_id"], {}))
            for row in conn.execute(
                """
                SELECT agent_id, display_name, description, agent_type, bot_id, enabled,
                       system_builtin, locked, exclusive, priority, context_policy,
                       created_at, updated_at
                FROM agent_definitions
                WHERE enabled = 1
                ORDER BY priority ASC, agent_id ASC
                """
            ).fetchall()
        }
        stats = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM agent_definitions) AS agent_count,
                (SELECT COUNT(*) FROM agent_subscriptions) AS subscription_count,
                (SELECT COUNT(*) FROM route_topics) AS topic_count,
                (SELECT COUNT(*) FROM route_keywords WHERE enabled = 1) AS keyword_count,
                (SELECT COALESCE(MAX(updated_at), '') FROM agent_definitions) AS updated_at
            """
        ).fetchone()
    version = (
        f"{stats['agent_count']}:{stats['subscription_count']}:"
        f"{stats['topic_count']}:{stats['keyword_count']}:{stats['updated_at']}"
    )
    return RegistrySnapshot(agents=agents, route_config=route_config, version=version)


def list_agents(db_path: str) -> Dict[str, Any]:
    with _connect(db_path) as conn:
        topics = [
            _topic_to_dict(_as_topic(row))
            for row in conn.execute(
                """
                SELECT topic, display_name, description, is_teaching, is_exclusive, route_priority, enabled
                FROM route_topics
                ORDER BY route_priority ASC, topic ASC
                """
            ).fetchall()
        ]
        subscriptions = _read_subscriptions(conn)
        agents = [
            _agent_to_dict(_as_agent(row, subscriptions.get(row["agent_id"], {})))
            for row in conn.execute(
                """
                SELECT agent_id, display_name, description, agent_type, bot_id, enabled,
                       system_builtin, locked, exclusive, priority, context_policy,
                       created_at, updated_at
                FROM agent_definitions
                ORDER BY priority ASC, agent_id ASC
                """
            ).fetchall()
        ]
    return {"agents": agents, "topics": topics}


def get_topics_payload(db_path: str) -> Dict[str, Any]:
    with _connect(db_path) as conn:
        route_config = _read_route_config(conn, only_enabled=False)
        settings = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM route_settings").fetchall()
        }
    return {
        "topics": [
            _topic_to_dict(topic)
            for topic in sorted(route_config.topics.values(), key=lambda item: (item.route_priority, item.topic))
        ],
        "keywords": {
            "topic": route_config.topic_keywords,
            "practice": {
                "exact": route_config.practice_exact,
                "contains": route_config.practice_contains,
                "loose": route_config.practice_loose,
                "negative": route_config.practice_negative,
                "exit": route_config.practice_exit,
            },
            "global": {
                "difficulty_basic": route_config.difficulty_basic,
                "difficulty_advanced": route_config.difficulty_advanced,
                "off_topic": route_config.off_topic_blacklist,
                "domain": route_config.domain_terms,
            },
        },
        "settings": settings,
    }


def _validate_agent_id(agent_id: str) -> str:
    value = (agent_id or "").strip()
    if not _AGENT_ID_RE.match(value):
        raise ValueError("Agent ID 只能使用英文字母开头的字母、数字和下划线，长度 2-64")
    return value


def _validate_agent_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "display_name": (payload.get("display_name") or "").strip(),
        "description": (payload.get("description") or "").strip(),
        "agent_type": (payload.get("agent_type") or "coze_chat").strip(),
        "bot_id": (payload.get("bot_id") or "").strip(),
        "enabled": 1 if payload.get("enabled", True) else 0,
        "exclusive": 1 if payload.get("exclusive", False) else 0,
        "priority": _int(payload.get("priority"), 100),
        "context_policy": (payload.get("context_policy") or "on_switch_recent_2").strip(),
    }
    if not data["display_name"]:
        raise ValueError("请填写智能体中文名称")
    if data["agent_type"] not in _AGENT_TYPES:
        raise ValueError("智能体类型只能是 coze_chat 或 coze_workflow")
    if data["context_policy"] not in _CONTEXT_POLICIES:
        raise ValueError("跨 Agent 上下文策略无效")
    return data


def create_agent(db_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = _validate_agent_id(payload.get("agent_id", ""))
    data = _validate_agent_payload(payload)
    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO agent_definitions
                    (agent_id, display_name, description, agent_type, bot_id, enabled,
                     system_builtin, locked, exclusive, priority, context_policy)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
                """,
                (
                    agent_id,
                    data["display_name"],
                    data["description"],
                    data["agent_type"],
                    data["bot_id"],
                    data["enabled"],
                    data["exclusive"],
                    data["priority"],
                    data["context_policy"],
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Agent ID 已存在") from exc
    return list_agents(db_path)


def update_agent(db_path: str, agent_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = _validate_agent_id(agent_id)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT agent_id, display_name, description, agent_type, bot_id,
                   enabled, locked, exclusive, priority, context_policy
            FROM agent_definitions WHERE agent_id = ?
            """,
            (agent_id,),
        ).fetchone()
        if not row:
            raise ValueError("智能体不存在")
        # 合并式部分更新：载荷未携带的字段保留原值，
        # 避免局部 PUT（如卡片上的快速启停）清空既有配置
        merged = {
            "display_name": payload.get("display_name", row["display_name"]),
            "description": payload.get("description", row["description"]),
            "agent_type": payload.get("agent_type", row["agent_type"]),
            "bot_id": payload.get("bot_id", row["bot_id"]),
            "enabled": payload.get("enabled", _bool(row["enabled"])),
            "exclusive": payload.get("exclusive", _bool(row["exclusive"])),
            "priority": payload.get("priority", row["priority"]),
            "context_policy": payload.get("context_policy", row["context_policy"]),
        }
        data = _validate_agent_payload(merged)
        if _bool(row["locked"]):
            conn.execute(
                """
                UPDATE agent_definitions
                SET bot_id = ?, enabled = ?
                WHERE agent_id = ?
                """,
                (data["bot_id"], data["enabled"], agent_id),
            )
        else:
            conn.execute(
                """
                UPDATE agent_definitions
                SET display_name = ?, description = ?, agent_type = ?, bot_id = ?,
                    enabled = ?, exclusive = ?, priority = ?, context_policy = ?
                WHERE agent_id = ?
                """,
                (
                    data["display_name"],
                    data["description"],
                    data["agent_type"],
                    data["bot_id"],
                    data["enabled"],
                    data["exclusive"],
                    data["priority"],
                    data["context_policy"],
                    agent_id,
                ),
            )
        conn.commit()
    return list_agents(db_path)


def delete_agent(db_path: str, agent_id: str) -> Dict[str, Any]:
    agent_id = _validate_agent_id(agent_id)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT system_builtin, locked FROM agent_definitions WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if not row:
            raise ValueError("智能体不存在")
        if _bool(row["system_builtin"]) or _bool(row["locked"]):
            raise ValueError("系统内置智能体不能删除")
        conn.execute("DELETE FROM agent_definitions WHERE agent_id = ?", (agent_id,))
        conn.commit()
    return list_agents(db_path)


def save_agent_subscriptions(db_path: str, agent_id: str, subscriptions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    agent_id = _validate_agent_id(agent_id)
    rows = list(subscriptions or [])
    with _connect(db_path) as conn:
        agent = conn.execute(
            "SELECT agent_id, locked FROM agent_definitions WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if not agent:
            raise ValueError("智能体不存在")
        if _bool(agent["locked"]):
            raise ValueError("系统锁定智能体不能修改订阅")
        valid_topics = {
            row["topic"]
            for row in conn.execute("SELECT topic FROM route_topics").fetchall()
        }
        exclusive_topics = {
            row["topic"]
            for row in conn.execute("SELECT topic FROM route_topics WHERE is_exclusive = 1").fetchall()
        }
        conn.execute("DELETE FROM agent_subscriptions WHERE agent_id = ?", (agent_id,))
        for item in rows:
            topic = (item.get("topic") or "").strip()
            if topic not in valid_topics:
                raise ValueError(f"Topic 不存在: {topic}")
            # 独占 topic 只允许一个订阅者：否则管线重建时 bus.subscribe
            # 会抛错导致整个消息管线不可用
            if topic in exclusive_topics:
                holder = conn.execute(
                    "SELECT agent_id FROM agent_subscriptions WHERE topic = ? AND agent_id != ? LIMIT 1",
                    (topic, agent_id),
                ).fetchone()
                if holder:
                    raise ValueError(f"独占 topic {topic} 已被 {holder['agent_id']} 订阅")
            conn.execute(
                """
                INSERT INTO agent_subscriptions
                    (agent_id, topic, base_bid, basic_bonus, advanced_bonus)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    topic,
                    _float(item.get("base_bid")),
                    _float(item.get("basic_bonus")),
                    _float(item.get("advanced_bonus")),
                ),
            )
        conn.commit()
    return list_agents(db_path)


def _keywords_from(values: Any) -> List[str]:
    if isinstance(values, str):
        parts = re.split(r"[\n,，]+", values)
    elif isinstance(values, list):
        parts = values
    else:
        parts = []
    result: List[str] = []
    for item in parts:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result


def _insert_keywords(
    conn: sqlite3.Connection,
    scope: str,
    topic: Optional[str],
    kind: str,
    values: Any,
    priority: int,
) -> None:
    for keyword in _keywords_from(values):
        conn.execute(
            """
            INSERT OR IGNORE INTO route_keywords
                (scope, topic, kind, keyword, enabled, priority)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (scope, topic, kind, keyword, priority),
        )


def save_topics_payload(db_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    topics = payload.get("topics") or []
    keywords = payload.get("keywords") or {}
    settings = payload.get("settings") or {}

    with _connect(db_path) as conn:
        for item in topics:
            topic = (item.get("topic") or "").strip()
            if not topic:
                continue
            conn.execute(
                """
                INSERT INTO route_topics
                    (topic, display_name, description, is_teaching, is_exclusive, route_priority, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic) DO UPDATE SET
                    display_name = excluded.display_name,
                    description = excluded.description,
                    is_teaching = excluded.is_teaching,
                    is_exclusive = excluded.is_exclusive,
                    route_priority = excluded.route_priority,
                    enabled = excluded.enabled
                """,
                (
                    topic,
                    (item.get("display_name") or topic).strip(),
                    (item.get("description") or "").strip(),
                    1 if item.get("is_teaching", True) else 0,
                    1 if item.get("is_exclusive", False) else 0,
                    _int(item.get("route_priority"), 100),
                    1 if item.get("enabled", True) else 0,
                ),
            )

        conn.execute("DELETE FROM route_keywords WHERE scope IN ('topic', 'practice', 'global')")
        topic_keywords = keywords.get("topic") or {}
        for topic, groups in topic_keywords.items():
            _insert_keywords(conn, "topic", topic, "strong", groups.get("strong"), 10)
            _insert_keywords(conn, "topic", topic, "weak", groups.get("weak"), 20)
            _insert_keywords(conn, "topic", topic, "pattern", groups.get("pattern"), 30)

        practice = keywords.get("practice") or {}
        _insert_keywords(conn, "practice", None, "exact", practice.get("exact"), 10)
        _insert_keywords(conn, "practice", None, "contains", practice.get("contains"), 20)
        _insert_keywords(conn, "practice", None, "loose", practice.get("loose"), 30)
        _insert_keywords(conn, "practice", None, "negative", practice.get("negative"), 40)
        _insert_keywords(conn, "practice", None, "exit", practice.get("exit"), 50)

        global_words = keywords.get("global") or {}
        _insert_keywords(conn, "global", None, "difficulty_basic", global_words.get("difficulty_basic"), 10)
        _insert_keywords(conn, "global", None, "difficulty_advanced", global_words.get("difficulty_advanced"), 10)
        _insert_keywords(conn, "global", None, "off_topic", global_words.get("off_topic"), 20)
        _insert_keywords(conn, "global", None, "domain", global_words.get("domain"), 30)

        for key in ("loose_trigger_max_len", "off_topic_reply"):
            if key in settings:
                conn.execute(
                    """
                    INSERT INTO route_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, str(settings.get(key) or "")),
                )
        conn.commit()
    return get_topics_payload(db_path)
