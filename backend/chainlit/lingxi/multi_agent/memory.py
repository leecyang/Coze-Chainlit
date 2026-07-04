"""用户长期记忆（v1 极简版）。

纯模块，仅用标准库 sqlite3（同步），调用方用 asyncio.to_thread 包裹。
v1 只从 mistake_details 错题表提炼薄弱知识点；备考阶段/基础水平
暂无数据来源，返回"未知"，留作后续扩展点。
"""

import sqlite3
from typing import Any, Dict

_DEFAULT_MEMORY: Dict[str, Any] = {
    "备考阶段": "未知",
    "基础水平": "未知",
    "薄弱知识点": [],
}


def fetch_user_memory(db_path: str, username: str) -> Dict[str, Any]:
    memory = dict(_DEFAULT_MEMORY)
    memory["薄弱知识点"] = []
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            cursor = conn.execute(
                "SELECT question_text FROM mistake_details "
                "WHERE username = ? ORDER BY id DESC LIMIT 20",
                (username,),
            )
            seen = set()
            weak_points = []
            for (question_text,) in cursor:
                snippet = (question_text or "").strip().replace("\n", " ")[:40]
                if snippet and snippet not in seen:
                    seen.add(snippet)
                    weak_points.append(snippet)
                if len(weak_points) >= 5:
                    break
            memory["薄弱知识点"] = weak_points
        finally:
            conn.close()
    except Exception:
        # 表不存在 / DB 不可读时静默回退默认记忆
        pass
    return memory
