"""DB-registered Coze teaching agents."""

from typing import Any, Dict

import chainlit as cl

from .base import BaseAgent
from .message import DIFFICULTY_ADVANCED, DIFFICULTY_BASIC, Message
from .registry import AgentConfig


class RegisteredCozeAgent(BaseAgent):
    """Coze Bot Agent built from the DB registry.

    The runtime contract is intentionally based on agent_name. No legacy
    role/persona field is sent to Coze.
    """

    def __init__(self, deps, config: AgentConfig) -> None:
        super().__init__(deps)
        self.config = config
        self.name = config.agent_id
        self.display_name = config.display_name
        self.bot_id_override = config.bot_id
        self.priority = config.priority
        self.context_policy = config.context_policy
        self.subscribed_topics = tuple(config.subscriptions.keys())

    def bid(self, msg: Message) -> float:
        subscription = self.config.subscriptions.get(msg.topic)
        if not subscription:
            return 0.0
        difficulty = msg.payload.get("difficulty")
        bonus = 0.0
        if difficulty == DIFFICULTY_BASIC:
            bonus = subscription.basic_bonus
        elif difficulty == DIFFICULTY_ADVANCED:
            bonus = subscription.advanced_bonus
        return subscription.base_bid + bonus

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        username = msg.payload.get("username", "unknown")
        coze = await self._get_coze(username)
        conversation_id = await self._ensure_conversation(coze, username)
        if not conversation_id:
            return {"content": None, "requires_action": None}

        extra_vars = {
            "agent_name": self.display_name,
            "task_topic": msg.topic,
            "difficulty": msg.payload.get("difficulty", "normal"),
        }
        context = msg.payload.get("context") or {}
        last_agent = context.get("last_agent")
        if self.context_policy == "on_switch_recent_2" and last_agent and last_agent != self.name:
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
