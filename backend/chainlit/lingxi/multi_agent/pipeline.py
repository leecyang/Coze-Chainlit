"""MultiAgentPipeline：把标准化、路由、总线、竞价、选择、执行串起来。

用户消息
  → MessageNormalizer 标准化
  → （续接优先）练习工作流挂起时直达 Daily_Practice_Agent
  → Router 判定任务型 topic（off_topic 模板拒答，零 LLM 成本）
  → MessageBus.publish 任务消息
  → 独占 topic 唯一订阅者直取；教学 topic 各订阅者 bid 竞价
  → ResponseSelector 按 preferred_style/置信度/上下文选赢家
  → 赢家调用自己的 Coze Bot 流式生成
  → agent.response 发布（观测）+ session 记账
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import chainlit as cl

from .base import AgentDeps, SESSION_AGENT_CONVERSATIONS, BaseAgent
from .bus import MessageBus
from .memory import fetch_user_memory
from .message import (
    Message,
    TOPIC_AGENT_RESPONSE,
    TOPIC_OFF_TOPIC,
    TOPIC_PRACTICE_ANSWER,
    TOPIC_PRACTICE_REPORT,
    TOPIC_PRACTICE_REQUEST,
    derive,
    new_user_message,
)
from .normalizer import normalize
from .practice_agent import DailyPracticeAgent
from .router import OFF_TOPIC_REPLY, is_practice_exit, route
from .selector import select
from .teaching_agents import (
    DebateChallengerAgent,
    NetworkExpertAgent,
    NoviceLearnerAgent,
)

# 与旧 on_message 一致的错误文案
_EMPTY_RESPONSE_ERROR = "抱歉，我没有收到有效的回复。请检查 Coze API Key 和 Bot ID 配置是否正确。"
_PRACTICE_EXIT_REPLY = "好的，已退出本次练习。你可以继续提问，或随时发送「开始每日一练」重新开始。"

_RECENT_HISTORY_CAP = 6
SESSION_RECENT_HISTORY = "recent_history"
SESSION_LAST_AGENT = "last_agent"
SESSION_LAST_TOPIC = "last_topic"


class MultiAgentPipeline:
    def __init__(self, deps: AgentDeps, db_path: str) -> None:
        self.deps = deps
        self.db_path = db_path
        self.bus = MessageBus()

        self.practice_agent = DailyPracticeAgent(deps)
        self.agents: Dict[str, BaseAgent] = {
            agent.name: agent
            for agent in (
                NoviceLearnerAgent(deps),
                DebateChallengerAgent(deps),
                NetworkExpertAgent(deps),
                self.practice_agent,
            )
        }
        for agent in self.agents.values():
            for topic in agent.subscribed_topics:
                self.bus.subscribe(topic, agent)

    # ==================== 主入口 ====================

    async def handle(
        self,
        username: str,
        raw_text: str,
        thread_id: Optional[str],
        preferred_style: str,
        cl_msg: "cl.Message",
    ) -> None:
        inp = normalize(raw_text)

        # ---------- 续接优先：练习工作流挂起时，本条消息属于问答节点 ----------
        pending = self.practice_agent.get_state().get("pending_tool_action")
        if pending:
            if is_practice_exit(inp.compact):
                # 用户显式退出：清挂起、模板确认，不再把"退出练习"当问题路由
                self.practice_agent.set_state(pending_tool_action=None)
                await self._stream_template(cl_msg, _PRACTICE_EXIT_REPLY)
                self._bookkeep(inp.text, TOPIC_PRACTICE_ANSWER, self.practice_agent.name, "已退出练习")
                return
            msg = await self._build_message(username, inp.text, preferred_style)
            answer_msg = derive(
                msg, topic=TOPIC_PRACTICE_ANSWER, sender="router", pending_action=pending,
            )
            # 与旧逻辑一致：分派前先清除挂起状态，新挂起由本轮结果决定
            self.practice_agent.set_state(pending_tool_action=None)
            self.bus.publish(answer_msg)
            await self._run_agent(self.practice_agent, answer_msg, cl_msg, thread_id, had_pending=True)
            return

        # ---------- 正常路由 ----------
        msg = await self._build_message(username, inp.text, preferred_style)
        result = route(inp)
        msg.payload["difficulty"] = result.difficulty
        msg.payload["off_topic"] = result.off_topic
        print(f"[Router] topic={result.topic} difficulty={result.difficulty} "
              f"matched={result.matched[:5]}")

        if result.off_topic:
            # 统一拒答模块：模板回复，不调用 LLM，不记使用日志
            await self._stream_template(cl_msg, OFF_TOPIC_REPLY)
            self._bookkeep(inp.text, TOPIC_OFF_TOPIC, None, "（超纲拒答）")
            return

        task_msg = derive(msg, topic=result.topic, sender="router")
        subscribers = self.bus.publish(task_msg)
        if not subscribers:
            # 理论上不可达（所有可路由 topic 都有订阅者），兜底走专家
            subscribers = [self.agents["Network_Expert"]]

        if task_msg.topic in (TOPIC_PRACTICE_REQUEST, TOPIC_PRACTICE_ANSWER):
            winner = subscribers[0]  # 独占型 topic：唯一订阅者
        else:
            bids: List[Tuple[str, float]] = [
                (agent.name, agent.bid(task_msg)) for agent in subscribers
            ]
            selection = select(bids, task_msg)
            winner = self.agents[selection.agent_name]
            print(f"[Selector] winner={selection.agent_name} "
                  f"score={selection.score:.2f} breakdown={selection.breakdown}")

        await self._run_agent(winner, task_msg, cl_msg, thread_id, had_pending=False)

    # ==================== 执行与记账 ====================

    async def _run_agent(
        self,
        agent: BaseAgent,
        msg: Message,
        cl_msg: "cl.Message",
        thread_id: Optional[str],
        had_pending: bool,
    ) -> None:
        username = msg.payload.get("username", "unknown")
        try:
            self.deps.log_usage(username, agent.display_name, thread_id)
        except Exception as e:
            print(f"[Pipeline] 记录使用日志失败: {e}")

        result = await agent.act(msg, cl_msg)
        content = result.get("content") if isinstance(result, dict) else result
        requires_action = result.get("requires_action") if isinstance(result, dict) else None

        # 挂起状态统一由 pipeline 写回（目前只有练习 Agent 会产生）
        if agent is self.practice_agent:
            self.practice_agent.set_state(pending_tool_action=requires_action or None)
            if requires_action:
                print(f"[Pipeline] 练习工作流挂起: chat_id={requires_action.get('chat_id')}")
            elif had_pending:
                # 工作流从挂起走到完成：发布 practice.report（v1 仅供观测/扩展）
                report = derive(
                    msg, topic=TOPIC_PRACTICE_REPORT, sender=agent.name,
                    report_summary=(content or "")[:200],
                )
                self.bus.publish(report)
        elif requires_action:
            print(f"[Pipeline] 警告: {agent.name} 返回 requires_action，教学 Bot 不应挂载工作流，已忽略")

        if not content:
            await cl_msg.stream_token(_EMPTY_RESPONSE_ERROR)
            cl_msg.content = _EMPTY_RESPONSE_ERROR
            await cl_msg.update()

        # agent.response：候选/最终回复上总线（观测与后续扩展）
        self.bus.publish(derive(
            msg, topic=TOPIC_AGENT_RESPONSE, sender=agent.name,
            response_preview=(content or "")[:120],
        ))

        # 把赢家的 Coze 会话镜像到旧 session 键，管理后台会话元数据展示依赖它
        conversations = cl.user_session.get(SESSION_AGENT_CONVERSATIONS) or {}
        if conversations.get(agent.name):
            cl.user_session.set("conversation_id", conversations[agent.name])

        self._bookkeep(msg.payload.get("user_message", ""), msg.topic, agent.name, content or "")

    async def _build_message(self, username: str, text: str, preferred_style: str) -> Message:
        memory = await asyncio.to_thread(fetch_user_memory, self.db_path, username)
        history: List[str] = cl.user_session.get(SESSION_RECENT_HISTORY) or []
        context = {
            "recent_summary": "\n".join(history),
            "recent_turns": history[-2:],
            "last_topic": cl.user_session.get(SESSION_LAST_TOPIC),
            "last_agent": cl.user_session.get(SESSION_LAST_AGENT),
        }
        return new_user_message(username, text, context, memory, preferred_style)

    def _bookkeep(self, user_text: str, topic: str, agent_name: Optional[str], reply: str) -> None:
        if agent_name:
            cl.user_session.set(SESSION_LAST_AGENT, agent_name)
        cl.user_session.set(SESSION_LAST_TOPIC, topic)
        history: List[str] = cl.user_session.get(SESSION_RECENT_HISTORY) or []
        snippet_user = user_text.replace("\n", " ")[:60]
        snippet_reply = (reply or "").replace("\n", " ")[:60]
        history.append(f"用户: {snippet_user} | {agent_name or 'system'}({topic}): {snippet_reply}")
        cl.user_session.set(SESSION_RECENT_HISTORY, history[-_RECENT_HISTORY_CAP:])

    @staticmethod
    async def _stream_template(cl_msg: "cl.Message", text: str) -> None:
        await cl_msg.stream_token(text)
        cl_msg.content = text
        await cl_msg.update()
