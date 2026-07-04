"""Agent 基类与依赖注入容器。

本模块允许 import chainlit（读写 user_session），但绝不 import
app_impl——所有对宿主的依赖（CozeAPI 工厂、token、会话注册、
bot_id 解析、使用记录）都通过 AgentDeps 注入，避免循环导入。
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import chainlit as cl

from .message import Message

# session 键：{agent_name: coze_conversation_id}
# 值是纯字符串 dict → Chainlit 会经 thread metadata 自动持久化并在恢复时还原
SESSION_AGENT_CONVERSATIONS = "agent_conversations"
# session 键：{agent_name: {"pending_tool_action": {...}}}，同样可 JSON 序列化
SESSION_AGENT_STATE = "agent_state"


@dataclass
class AgentDeps:
    """由 app_impl 注入的宿主能力。"""

    coze_factory: Callable[[Optional[str], str], Any]          # (auth_token, bot_id) -> CozeAPI
    get_token: Callable[[str], Awaitable[Optional[str]]]       # username -> token
    register_conversation: Callable[[str, str], None]          # (conversation_id, username)
    get_bot_id: Callable[[str], str]                           # config key -> bot id（含回退）
    log_usage: Callable[[str, str, Optional[str]], None]       # (username, display_name, thread_id)


class BaseAgent:
    name: str = "Base_Agent"
    display_name: str = "基础智能体"
    bot_env_key: str = "COZE_BOT_ID"
    bot_id_override: str = ""
    subscribed_topics: Tuple[str, ...] = ()

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    # ---------- 订阅-竞价-执行 ----------

    def bid(self, msg: Message) -> float:
        """对任务消息给出置信度竞价（0~1，规则化，不调用 LLM）。"""
        return 0.0

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        """处理消息并把回复流式写入 cl_msg。

        Returns:
            {"content": str|None, "requires_action": dict|None}
        """
        raise NotImplementedError

    # ---------- Coze 客户端与会话 ----------

    async def _get_coze(self, username: str) -> Any:
        token = await self.deps.get_token(username)
        bot_id = (self.bot_id_override or "").strip() or self.deps.get_bot_id(self.bot_env_key)
        return self.deps.coze_factory(token, bot_id)

    async def _ensure_conversation(self, coze: Any, username: str) -> Optional[str]:
        """惰性创建本 Agent 的 Coze 会话，存入 session 并注册用户映射。"""
        conversations: Dict[str, str] = cl.user_session.get(SESSION_AGENT_CONVERSATIONS) or {}
        conversation_id = conversations.get(self.name)
        if conversation_id:
            return conversation_id

        conversation_id = await coze.create_conversation()
        if not conversation_id:
            return None
        conversations[self.name] = conversation_id
        cl.user_session.set(SESSION_AGENT_CONVERSATIONS, conversations)
        # 注册 conversation_id -> username 映射（Coze 工作流 HTTP 回调依赖）
        self.deps.register_conversation(conversation_id, username)
        bot_id = (self.bot_id_override or "").strip() or self.deps.get_bot_id(self.bot_env_key)
        print(f"[Agent:{self.name}] 创建会话 {conversation_id} (bot={bot_id})")
        return conversation_id

    # ---------- 每 Agent 独立状态（跨重连自动恢复） ----------

    def get_state(self) -> Dict[str, Any]:
        states: Dict[str, Dict[str, Any]] = cl.user_session.get(SESSION_AGENT_STATE) or {}
        return states.get(self.name) or {}

    def set_state(self, **updates: Any) -> None:
        states: Dict[str, Dict[str, Any]] = cl.user_session.get(SESSION_AGENT_STATE) or {}
        state = states.get(self.name) or {}
        state.update(updates)
        states[self.name] = state
        cl.user_session.set(SESSION_AGENT_STATE, states)
