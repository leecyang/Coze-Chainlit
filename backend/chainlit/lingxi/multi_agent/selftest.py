"""离线自测：不需要 chainlit 或网络。

运行：cd backend && python -m chainlit.lingxi.multi_agent.selftest
"""

import sys
import tempfile

from chainlit.lingxi.migrations import run_migrations

from .bus import MessageBus
from .message import (
    DIFFICULTY_ADVANCED,
    DIFFICULTY_BASIC,
    DIFFICULTY_NORMAL,
    TOPIC_CONCEPT_EXPLAIN,
    TOPIC_EXAM_ANALYZE,
    TOPIC_OFF_TOPIC,
    TOPIC_PRACTICE_ANSWER,
    TOPIC_PRACTICE_REQUEST,
    TOPIC_QUESTION_SOLVE,
    TOPIC_STUDY_PLAN,
    new_user_message,
)
from .normalizer import normalize
from .registry import RegistrySnapshot, load_registry
from .router import is_practice_exit, route
from .selector import select

FAILURES = []


def check(label: str, actual, expected) -> None:
    if actual == expected:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}: expected {expected!r}, got {actual!r}")
        FAILURES.append(label)


def route_topic(text: str) -> str:
    assert REGISTRY is not None
    return route(normalize(text), REGISTRY.route_config).topic


def route_difficulty(text: str) -> str:
    assert REGISTRY is not None
    return route(normalize(text), REGISTRY.route_config).difficulty


def test_router() -> None:
    print("[Router] topic 分类")
    # 五个前端启动器文案（app_impl.set_starters）——按钮改文案必须同步触发词
    check("启动器:每日一练", route_topic("开始每日一练"), TOPIC_PRACTICE_REQUEST)
    check("启动器:考试大纲", route_topic("请介绍一下计算机三级网络技术的考试大纲和主要内容"), TOPIC_EXAM_ANALYZE)
    check("启动器:备考建议", route_topic("给我一些计算机三级网络技术的备考建议和学习计划"), TOPIC_STUDY_PLAN)
    check("启动器:网络基础", route_topic("解释一下计算机网络的基本概念和OSI七层模型"), TOPIC_CONCEPT_EXPLAIN)
    check("启动器:IP地址", route_topic("详细讲解IP地址的分类、子网划分和CIDR表示法"), TOPIC_CONCEPT_EXPLAIN)

    # 练习触发（方案第三节示例）
    check("练习:每日一练", route_topic("每日一练"), TOPIC_PRACTICE_REQUEST)
    check("练习:开始今天的练习", route_topic("开始今天的练习"), TOPIC_PRACTICE_REQUEST)
    check("练习:来几道三级网络题", route_topic("来几道计算机三级网络题"), TOPIC_PRACTICE_REQUEST)
    check("练习:我要刷题", route_topic("我要刷题"), TOPIC_PRACTICE_REQUEST)
    check("练习:随机抽题练习", route_topic("随机抽题练习"), TOPIC_PRACTICE_REQUEST)
    check("练习:短消息刷题", route_topic("刷题"), TOPIC_PRACTICE_REQUEST)
    # 宽松触发护栏：关于练习的"提问"不是练习请求
    check("护栏:做题技巧提问", route_topic("选择题做题技巧有哪些"), TOPIC_CONCEPT_EXPLAIN)
    check("护栏:长句不触发", route_topic("我昨天做题的时候发现子网划分总是算错应该怎么办呢"), TOPIC_CONCEPT_EXPLAIN)
    assert REGISTRY is not None
    check("退出词识别", is_practice_exit(normalize("退出练习").compact, REGISTRY.route_config), True)
    check("非退出词", is_practice_exit(normalize("继续下一题").compact, REGISTRY.route_config), False)

    # concept.explain（方案示例）
    check("concept:三次握手", route_topic("TCP 三次握手是什么？"), TOPIC_CONCEPT_EXPLAIN)
    check("concept:RIP vs OSPF", route_topic("RIP 和 OSPF 有什么区别？"), TOPIC_CONCEPT_EXPLAIN)
    check("concept:ARP", route_topic("ARP 是干什么的？"), TOPIC_CONCEPT_EXPLAIN)
    check("concept:零命中默认", route_topic("随便聊聊呗"), TOPIC_CONCEPT_EXPLAIN)

    # exam.analyze（方案示例）
    check("exam:重点", route_topic("计算机三级网络技术哪些是重点？"), TOPIC_EXAM_ANALYZE)
    check("exam:子网怎么考", route_topic("子网划分考试怎么考？"), TOPIC_EXAM_ANALYZE)
    check("exam:丢分", route_topic("网络规划题容易在哪里丢分？"), TOPIC_EXAM_ANALYZE)

    # question.solve（方案示例）
    check("question:这道题", route_topic("这道题怎么做？"), TOPIC_QUESTION_SOLVE)
    check("question:为什么选A", route_topic("为什么这题选 A？"), TOPIC_QUESTION_SOLVE)
    check("question:子网计算", route_topic("这道子网计算题帮我解析一下。"), TOPIC_QUESTION_SOLVE)

    # study.plan（方案示例）
    check("plan:两周复习", route_topic("我还有两周考试怎么复习？"), TOPIC_STUDY_PLAN)
    check("plan:零基础备考", route_topic("零基础怎么备考三级网络？"), TOPIC_STUDY_PLAN)
    check("plan:冲刺计划", route_topic("帮我制定一个冲刺计划。"), TOPIC_STUDY_PLAN)

    # off_topic：黑名单命中且领域零命中才拒答
    check("off:天气", route_topic("今天天气怎么样"), TOPIC_OFF_TOPIC)
    check("off:笑话", route_topic("给我讲个笑话"), TOPIC_OFF_TOPIC)
    check("off:领域词不拒答", route_topic("网络游戏对带宽的要求高吗"), TOPIC_CONCEPT_EXPLAIN)
    check("off:白名单豁免黑名单", route_topic("原神这游戏的网络延迟为什么高"), TOPIC_CONCEPT_EXPLAIN)

    print("[Router] difficulty 识别")
    check("difficulty:通俗", route_difficulty("通俗地讲讲TCP拥塞控制"), DIFFICULTY_BASIC)
    check("difficulty:深入", route_difficulty("深入讲解OSPF的链路状态算法"), DIFFICULTY_ADVANCED)
    check("difficulty:默认", route_difficulty("什么是VLAN"), DIFFICULTY_NORMAL)


REGISTRY: RegistrySnapshot | None = None


def _msg(topic: str, last_agent=None, difficulty: str = "normal"):
    m = new_user_message("tester", "示例问题", {"last_agent": last_agent}, {})
    m.topic = topic
    m.payload["difficulty"] = difficulty
    return m


def _bids_for(topic: str, difficulty: str = "normal"):
    """从 DB registry seed 的订阅与 bid 表计算竞价。"""
    assert REGISTRY is not None
    bids = []
    for agent in REGISTRY.agents.values():
        subscription = agent.subscriptions.get(topic)
        if not subscription:
            continue
        score = subscription.base_bid
        if difficulty == "basic":
            score += subscription.basic_bonus
        elif difficulty == "advanced":
            score += subscription.advanced_bonus
        bids.append((agent.agent_id, score))
    return bids


def _priorities():
    assert REGISTRY is not None
    return {agent.agent_id: agent.priority for agent in REGISTRY.agents.values()}


def test_selector() -> None:
    print("[Selector] DB bid 与连续性")
    # auto 无历史：Expert 赢 concept/exam/plan，Debate 赢 question.solve
    for topic, expected in (
        (TOPIC_CONCEPT_EXPLAIN, "Network_Expert"),
        (TOPIC_EXAM_ANALYZE, "Network_Expert"),
        (TOPIC_STUDY_PLAN, "Network_Expert"),
        (TOPIC_QUESTION_SOLVE, "Debate_Challenger"),
    ):
        sel = select(_bids_for(topic), _msg(topic), _priorities())
        check(f"auto:{topic}", sel.agent_name, expected)

    # basic 难度翻转 study.plan 给 Novice（0.75 > 0.70）
    sel = select(_bids_for(TOPIC_STUDY_PLAN, "basic"), _msg(TOPIC_STUDY_PLAN, difficulty="basic"), _priorities())
    check("basic翻转study.plan", sel.agent_name, "Novice_Learner")

    # 连续性只在分差足够小时生效，不再有用户偏好风格加权
    sel = select(_bids_for(TOPIC_EXAM_ANALYZE), _msg(TOPIC_EXAM_ANALYZE, last_agent="Novice_Learner"), _priorities())
    check("连续性不强制:exam仍是Expert", sel.agent_name, "Network_Expert")
    sel = select(
        _bids_for(TOPIC_QUESTION_SOLVE),
        _msg(TOPIC_QUESTION_SOLVE, last_agent="Network_Expert"),
        _priorities(),
    )
    check("连续性可反超小分差", sel.agent_name, "Network_Expert")

    # 平手：上一轮 Agent > priority
    sel = select(
        [("Debate_Challenger", 0.5), ("Network_Expert", 0.5), ("Novice_Learner", 0.5)],
        _msg(TOPIC_CONCEPT_EXPLAIN, last_agent="Debate_Challenger"),
        _priorities(),
    )
    check("平手上一轮优先", sel.agent_name, "Debate_Challenger")
    sel = select(
        [("Debate_Challenger", 0.5), ("Network_Expert", 0.5), ("Novice_Learner", 0.5)],
        _msg(TOPIC_CONCEPT_EXPLAIN),
        _priorities(),
    )
    check("平手priority优先", sel.agent_name, "Network_Expert")


def test_registry() -> None:
    print("[Registry] migration seed")
    assert REGISTRY is not None
    check("默认Agent数量", set(REGISTRY.agents), {
        "Novice_Learner",
        "Debate_Challenger",
        "Network_Expert",
        "Daily_Practice_Agent",
    })
    check("每日一练类型", REGISTRY.agents["Daily_Practice_Agent"].agent_type, "coze_workflow")
    check("question.solve订阅数", len(_bids_for(TOPIC_QUESTION_SOLVE)), 3)


def test_bus() -> None:
    print("[Bus] 独占 topic")
    bus = MessageBus()

    class _Stub:
        def __init__(self, name):
            self.name = name

    bus.subscribe(TOPIC_PRACTICE_REQUEST, _Stub("practice"))
    try:
        bus.subscribe(TOPIC_PRACTICE_REQUEST, _Stub("intruder"))
        check("独占topic重复订阅抛错", "no-error", "ValueError")
    except ValueError:
        check("独占topic重复订阅抛错", "ValueError", "ValueError")
    # 非独占 topic 可多订阅
    bus.subscribe(TOPIC_CONCEPT_EXPLAIN, _Stub("a"))
    bus.subscribe(TOPIC_CONCEPT_EXPLAIN, _Stub("b"))
    check("教学topic多订阅", len(bus.subscribers_for(TOPIC_CONCEPT_EXPLAIN)), 2)
    check("练习answer暂无订阅", bus.subscribers_for(TOPIC_PRACTICE_ANSWER), [])


def test_normalizer() -> None:
    print("[Normalizer] 标准化")
    n = normalize("  ＴＣＰ　 是什么 ？ ")
    check("全角转半角+去空白", n.compact, "tcp是什么?")
    check("原文折叠空白", n.text, "ＴＣＰ 是什么 ？")


def main() -> int:
    global REGISTRY
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/chainlit.db"
        run_migrations(db_path)
        run_migrations(db_path)
        REGISTRY = load_registry(db_path)
        test_registry()
    test_normalizer()
    test_router()
    test_selector()
    test_bus()
    if FAILURES:
        print(f"\n{len(FAILURES)} 个用例失败: {FAILURES}")
        return 1
    print("\n全部用例通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
