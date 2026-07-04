"""ResponseSelector：根据置信度竞价与上下文连续性选出赢家。"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .message import Message

CONTINUITY_BONUS = 0.10  # 与上一轮实际输出的 Agent 相同时加分（减少乒乓切换）


@dataclass
class Selection:
    agent_name: str
    score: float
    breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)  # 供日志


def select(
    bids: List[Tuple[str, float]],
    msg: Message,
    priorities: Optional[Dict[str, int]] = None,
) -> Selection:
    """bids: [(agent_name, confidence)]，须非空。"""
    if not bids:
        raise ValueError("select() 需要至少一个竞价")

    last_agent = (msg.payload.get("context") or {}).get("last_agent")
    priorities = priorities or {}

    breakdown: Dict[str, Dict[str, float]] = {}
    scored: List[Tuple[str, float]] = []
    for name, bid in bids:
        continuity_bonus = CONTINUITY_BONUS if name == last_agent else 0.0
        total = bid + continuity_bonus
        breakdown[name] = {
            "bid": bid,
            "continuity_bonus": continuity_bonus,
            "total": total,
        }
        scored.append((name, total))

    best_score = max(s for _, s in scored)
    contenders = [name for name, s in scored if abs(s - best_score) < 1e-9]

    if len(contenders) > 1:
        # 平手：上一轮 Agent > 注册表优先级 > Agent ID 字典序。
        if last_agent in contenders:
            winner = last_agent
        else:
            winner = min(contenders, key=lambda n: (priorities.get(n, 100), n))
    else:
        winner = contenders[0]

    return Selection(agent_name=winner, score=best_score, breakdown=breakdown)
