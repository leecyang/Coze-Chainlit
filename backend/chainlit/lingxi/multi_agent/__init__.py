"""类 MetaGPT 订阅-发布式多智能体包。

本文件只 re-export 纯模块符号（不触发 chainlit 导入），保证
`python -m chainlit.lingxi.multi_agent.selftest` 可离线运行。
需要 MultiAgentPipeline / AgentDeps 时请从子模块直接导入：

    from chainlit.lingxi.multi_agent.pipeline import MultiAgentPipeline
    from chainlit.lingxi.multi_agent.base import AgentDeps
"""

from .message import (  # noqa: F401
    EXCLUSIVE_TOPICS,
    Message,
    TEACHING_TOPICS,
    TOPIC_AGENT_RESPONSE,
    TOPIC_CONCEPT_EXPLAIN,
    TOPIC_EXAM_ANALYZE,
    TOPIC_OFF_TOPIC,
    TOPIC_PRACTICE_ANSWER,
    TOPIC_PRACTICE_REPORT,
    TOPIC_PRACTICE_REQUEST,
    TOPIC_QUESTION_SOLVE,
    TOPIC_STUDY_PLAN,
    TOPIC_USER_INPUT,
    derive,
    new_user_message,
)
