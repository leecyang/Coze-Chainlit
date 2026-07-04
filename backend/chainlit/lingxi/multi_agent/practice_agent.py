"""Daily_Practice_Agent：每日一练独占型 Workflow Agent。

包装现有 Coze Bot（COZE_BOT_ID）里的每日一练工作流：
- practice.request：发起练习（触发 Bot 内工作流，可能以 requires_action 挂起）
- practice.answer：续接挂起的问答节点，分派逻辑与旧 on_message 完全一致：
    reply_message 类型      -> 同一会话 chat_stream（Coze 自动续接未完成工作流）
    有效 tool_call_id       -> submit_tool_outputs_stream
    缺 chat_id / 空 id      -> chat_stream 兜底

注意：act() 不传 agent_name 与 extra_vars，每日一练工作流只接收
chat_stream 注入的通用 username 变量。

挂起状态（pending_tool_action）的存取由 pipeline 统一管理：
续接时 pipeline 把旧 pending 放进 payload 并预先清除，act() 只读
payload；新的 requires_action 由 pipeline 写回本 Agent 状态。
"""

from typing import Any, Dict

import chainlit as cl

from .base import BaseAgent
from .message import Message, TOPIC_PRACTICE_ANSWER, TOPIC_PRACTICE_REQUEST
from .registry import AgentConfig


class DailyPracticeAgent(BaseAgent):
    name = "Daily_Practice_Agent"
    display_name = "每日一练"
    bot_env_key = "COZE_BOT_ID"  # 现有 Bot：每日一练工作流所在
    subscribed_topics = (TOPIC_PRACTICE_REQUEST, TOPIC_PRACTICE_ANSWER)

    def __init__(self, deps, config: AgentConfig | None = None) -> None:
        super().__init__(deps)
        if config:
            self.name = config.agent_id
            self.display_name = config.display_name
            self.bot_id_override = config.bot_id
            self.subscribed_topics = tuple(config.subscriptions.keys()) or self.subscribed_topics

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        username = msg.payload.get("username", "unknown")
        user_message = msg.payload.get("user_message", "")
        coze = await self._get_coze(username)
        conversation_id = await self._ensure_conversation(coze, username)
        if not conversation_id:
            return {"content": None, "requires_action": None}

        if msg.topic == TOPIC_PRACTICE_ANSWER:
            return await self._continue_workflow(
                coze, conversation_id, username, user_message, cl_msg,
                msg.payload.get("pending_action") or {},
            )
        return await coze.chat_stream(conversation_id, username, user_message, cl_msg)

    async def _continue_workflow(
        self,
        coze: Any,
        conversation_id: str,
        username: str,
        user_message: str,
        cl_msg: "cl.Message",
        pending_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        pending_chat_id = pending_action.get("chat_id")
        pending_tool_calls = pending_action.get("tool_calls", [])
        pending_conv_id = pending_action.get("conversation_id") or conversation_id

        first_tool_call = pending_tool_calls[0] if pending_tool_calls else {}
        tool_call_type = first_tool_call.get("type", "unknown")
        tool_call_id = first_tool_call.get("id", "")

        print(f"[Agent:{self.name}] 续接工作流: type={tool_call_type}, "
              f"chat_id={pending_chat_id}, tool_call_id='{tool_call_id}'")

        if not pending_chat_id:
            # chat_id 缺失，回退到普通对话
            return await coze.chat_stream(conversation_id, username, user_message, cl_msg)

        if tool_call_type == "reply_message":
            # Coze 流式 API 已知问题：reply_message 的 tool_call_id 始终为空，
            # submit_tool_outputs 会报 code=4000。直接在同一会话发送用户回答，
            # Coze 会自动续接未完成的工作流。
            return await coze.chat_stream(pending_conv_id, username, user_message, cl_msg)

        if tool_call_id:
            tool_outputs = [{
                "tool_call_id": tc.get("id", ""),
                "output": str(user_message),
            } for tc in pending_tool_calls]
            return await coze.submit_tool_outputs_stream(
                conversation_id=pending_conv_id,
                chat_id=pending_chat_id,
                tool_outputs=tool_outputs,
                msg=cl_msg,
            )

        # tool_call_id 为空的其他类型，回退 chat_stream
        return await coze.chat_stream(pending_conv_id, username, user_message, cl_msg)
