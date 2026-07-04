"""ResponseSelector：根据置信度竞价、preferred_style 与上下文选出赢家。

纯模块，不依赖 chainlit。preferred_style 只是权重（加分项），
不是强制指定——这是与旧固定人设机制的本质区别。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .message import Message, STYLE_AUTO

# 偏好风格 → Agent 名的映射（Agent 名见 teaching_agents.py）
STYLE_TO_AGENT = {
    "novice": "Novice_Learner",
    "debate": "Debate_Challenger",
    "expert": "Network_Expert",
}

STYLE_BONUS = 0.25       # preferred_style 命中加分
CONTINUITY_BONUS = 0.10  # 与上一轮实际输出的 Agent 相同时加分（减少乒乓切换）

# 平手时的静态优先序（Expert 对应旧默认人设 计网专家）
_STATIC_ORDER = ("Network_Expert", "Novice_Learner", "Debate_Challenger")


@dataclass
class Selection:
    agent_name: str
    score: float
    breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)  # 供日志


def select(bids: List[Tuple[str, float]], msg: Message) -> Selection:
    """bids: [(agent_name, confidence)]，须非空。"""
    if not bids:
        raise ValueError("select() 需要至少一个竞价")

    preferred_style = msg.payload.get("preferred_style", STYLE_AUTO)
    preferred_agent = STYLE_TO_AGENT.get(preferred_style)
    last_agent = (msg.payload.get("context") or {}).get("last_agent")

    breakdown: Dict[str, Dict[str, float]] = {}
    scored: List[Tuple[str, float]] = []
    for name, bid in bids:
        style_bonus = STYLE_BONUS if name == preferred_agent else 0.0
        continuity_bonus = CONTINUITY_BONUS if name == last_agent else 0.0
        total = bid + style_bonus + continuity_bonus
        breakdown[name] = {
            "bid": bid,
            "style_bonus": style_bonus,
            "continuity_bonus": continuity_bonus,
            "total": total,
        }
        scored.append((name, total))

    best_score = max(s for _, s in scored)
    contenders = [name for name, s in scored if abs(s - best_score) < 1e-9]

    if len(contenders) > 1:
        # 平手：偏好命中 > 上一轮 Agent > 静态序
        if preferred_agent in contenders:
            winner = preferred_agent
        elif last_agent in contenders:
            winner = last_agent
        else:
            winner = min(
                contenders,
                key=lambda n: _STATIC_ORDER.index(n) if n in _STATIC_ORDER else 99,
            )
    else:
        winner = contenders[0]

    return Selection(agent_name=winner, score=best_score, breakdown=breakdown)
