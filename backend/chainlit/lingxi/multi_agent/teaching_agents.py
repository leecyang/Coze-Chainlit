"""三个教学型 Agent：新手小白 / 辩论对手 / 计网专家。

它们订阅同样的四个任务型 topic，只是回复风格不同（由各自独立的
Coze Bot 提示词决定）。bid() 是纯查表 + 难度修正，不调用 LLM——
先选择后生成，只有 Selector 选中的赢家才真正请求 Coze。
"""

from typing import Any, Dict

import chainlit as cl

from .base import BaseAgent
from .message import (
    DIFFICULTY_ADVANCED,
    DIFFICULTY_BASIC,
    Message,
    TEACHING_TOPICS,
    TOPIC_CONCEPT_EXPLAIN,
    TOPIC_EXAM_ANALYZE,
    TOPIC_QUESTION_SOLVE,
    TOPIC_STUDY_PLAN,
)

# 各 Agent 对各任务 topic 的基础置信度
BID_TABLE: Dict[str, Dict[str, float]] = {
    TOPIC_CONCEPT_EXPLAIN: {
        "Novice_Learner": 0.60, "Debate_Challenger": 0.50, "Network_Expert": 0.70,
    },
    TOPIC_EXAM_ANALYZE: {
        "Novice_Learner": 0.45, "Debate_Challenger": 0.55, "Network_Expert": 0.75,
    },
    TOPIC_QUESTION_SOLVE: {
        "Novice_Learner": 0.50, "Debate_Challenger": 0.70, "Network_Expert": 0.65,
    },
    TOPIC_STUDY_PLAN: {
        "Novice_Learner": 0.65, "Debate_Challenger": 0.40, "Network_Expert": 0.70,
    },
}


class TeachingAgent(BaseAgent):
    subscribed_topics = TEACHING_TOPICS

    def bid(self, msg: Message) -> float:
        base = BID_TABLE.get(msg.topic, {}).get(self.name, 0.0)
        difficulty = msg.payload.get("difficulty")
        return base + self._difficulty_bonus(difficulty)

    def _difficulty_bonus(self, difficulty: str) -> float:
        return 0.0

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        username = msg.payload.get("username", "unknown")
        coze = await self._get_coze(username)
        conversation_id = await self._ensure_conversation(coze, username)
        if not conversation_id:
            return {"content": None, "requires_action": None}

        extra_vars = {
            "task_topic": msg.topic,
            "difficulty": msg.payload.get("difficulty", "normal"),
        }
        context = msg.payload.get("context") or {}
        last_agent = context.get("last_agent")
        if last_agent and last_agent != self.name:
            recent_turns = context.get("recent_turns") or []
            if recent_turns:
                recent_context = "\n".join(str(item) for item in recent_turns[-2:])
                extra_vars["context"] = recent_context
                extra_vars["system_context"] = recent_context

        return await coze.chat_stream(
            conversation_id,
            username,
            msg.payload.get("user_message", ""),
            cl_msg,
            agent_name=self.display_name,
            extra_vars=extra_vars,
        )


class NoviceLearnerAgent(TeachingAgent):
    """费曼学习法：以"新手小白"身份反向提问，逼学习者讲清楚概念。"""

    name = "Novice_Learner"
    display_name = "新手小白"
    bot_env_key = "COZE_BOT_ID_NOVICE"

    def _difficulty_bonus(self, difficulty: str) -> float:
        return 0.10 if difficulty == DIFFICULTY_BASIC else 0.0


class DebateChallengerAgent(TeachingAgent):
    """辩论对手：用反例和刁钻问题挑战学习者的理解。"""

    name = "Debate_Challenger"
    display_name = "辩论对手"
    bot_env_key = "COZE_BOT_ID_DEBATE"

    def _difficulty_bonus(self, difficulty: str) -> float:
        return 0.05 if difficulty == DIFFICULTY_ADVANCED else 0.0


class NetworkExpertAgent(TeachingAgent):
    """计网专家：系统、规范、底层的专业讲解。"""

    name = "Network_Expert"
    display_name = "计网专家"
    bot_env_key = "COZE_BOT_ID_EXPERT"

    def _difficulty_bonus(self, difficulty: str) -> float:
        return 0.10 if difficulty == DIFFICULTY_ADVANCED else 0.0
