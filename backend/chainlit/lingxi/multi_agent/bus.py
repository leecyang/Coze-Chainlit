"""Message Bus / Environment：进程内订阅-发布总线。

纯模块，不依赖 chainlit。Agent 通过 subscribe 声明自己关心的任务
topic；Router 只负责 publish 任务消息，由订阅关系决定谁能观察到。
独占型 topic（每日一练）只允许一个订阅者。
"""

from typing import Any, Dict, List

from .message import EXCLUSIVE_TOPICS, Message


class MessageBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Any]] = {}

    def subscribe(self, topic: str, agent: Any) -> None:
        subs = self._subscribers.setdefault(topic, [])
        if topic in EXCLUSIVE_TOPICS and subs:
            raise ValueError(
                f"独占型 topic '{topic}' 已有订阅者 "
                f"{getattr(subs[0], 'name', subs[0])}，拒绝重复订阅"
            )
        if agent not in subs:
            subs.append(agent)

    def subscribers_for(self, topic: str) -> List[Any]:
        return list(self._subscribers.get(topic, []))

    def publish(self, msg: Message) -> List[Any]:
        """发布消息，返回该 topic 的订阅者列表（由调用方驱动 observe/act）。"""
        subs = self.subscribers_for(msg.topic)
        names = [getattr(a, "name", str(a)) for a in subs]
        print(
            f"[Bus] publish topic={msg.topic} sender={msg.sender} "
            f"id={msg.message_id[:8]} subscribers={len(subs)} {names}"
        )
        return subs
