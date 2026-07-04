"""统一消息结构与任务型 topic 常量。

本模块是纯模块：不依赖 chainlit，可被离线自测直接导入。
所有在总线上流转的消息统一封装为 Message 对象，topic 一律是
任务型主题（concept.explain / question.solve ...），而非角色名。
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict

# ==================== 任务型 Topic ====================
TOPIC_USER_INPUT = "user.input"
TOPIC_CONCEPT_EXPLAIN = "concept.explain"
TOPIC_EXAM_ANALYZE = "exam.analyze"
TOPIC_QUESTION_SOLVE = "question.solve"
TOPIC_STUDY_PLAN = "study.plan"
TOPIC_PRACTICE_REQUEST = "practice.request"
TOPIC_PRACTICE_ANSWER = "practice.answer"
TOPIC_PRACTICE_REPORT = "practice.report"
TOPIC_AGENT_RESPONSE = "agent.response"
TOPIC_OFF_TOPIC = "off_topic"

# 三个教学型 Agent 共同订阅的任务 topic
TEACHING_TOPICS = (
    TOPIC_CONCEPT_EXPLAIN,
    TOPIC_EXAM_ANALYZE,
    TOPIC_QUESTION_SOLVE,
    TOPIC_STUDY_PLAN,
)

# 独占型 topic：只允许一个订阅者（每日一练工作流不容多 Agent 干扰）
EXCLUSIVE_TOPICS = frozenset({TOPIC_PRACTICE_REQUEST, TOPIC_PRACTICE_ANSWER})

DIFFICULTY_BASIC = "basic"
DIFFICULTY_NORMAL = "normal"
DIFFICULTY_ADVANCED = "advanced"


@dataclass
class Message:
    """总线上的统一消息对象。

    payload 结构（约定，不强制校验）::

        {
            "username": str,
            "user_message": str,
            "context": {
                "recent_summary": str,   # 近几轮对话摘要（一行一轮）
                "recent_turns": list[str], # 最近 2 轮，跨 Agent 切换时注入 Coze
                "last_topic": str | None,
                "last_agent": str | None,
            },
            "memory": {
                "备考阶段": str,          # 基础/强化/冲刺/未知
                "基础水平": str,          # 薄弱/一般/较好/未知
                "薄弱知识点": list[str],
            },
            "difficulty": "basic" | "normal" | "advanced",
            "off_topic": bool,
        }
    """

    topic: str
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())


def new_user_message(
    username: str,
    user_message: str,
    context: Dict[str, Any],
    memory: Dict[str, Any],
) -> Message:
    """把一条用户原始输入封装为 user.input 消息。"""
    return Message(
        topic=TOPIC_USER_INPUT,
        sender="user",
        payload={
            "username": username,
            "user_message": user_message,
            "context": context or {},
            "memory": memory or {},
            "difficulty": DIFFICULTY_NORMAL,
            "off_topic": False,
        },
    )


def derive(msg: Message, *, topic: str, sender: str, **payload_updates: Any) -> Message:
    """从既有消息派生新消息：payload 浅拷贝并可覆盖字段，id/时间戳重新生成。"""
    payload = dict(msg.payload)
    payload.update(payload_updates)
    return Message(topic=topic, sender=sender, payload=payload)
