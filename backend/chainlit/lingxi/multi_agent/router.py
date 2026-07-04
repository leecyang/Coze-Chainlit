"""Router / Topic Classifier：规则+关键词判定任务型 topic 与难度。

纯模块，不依赖 chainlit。只判断"这是什么任务"，绝不指定某个人设
Agent——发布后由订阅关系和 ResponseSelector 决定谁来响应。

评估顺序：练习触发 → off_topic 门 → 教学 topic 打分 → 默认 concept.explain。
所有匹配都在 NormalizedInput.compact（小写、半角、无空白）上进行。
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .message import (
    DIFFICULTY_ADVANCED,
    DIFFICULTY_BASIC,
    DIFFICULTY_NORMAL,
    TOPIC_CONCEPT_EXPLAIN,
    TOPIC_EXAM_ANALYZE,
    TOPIC_OFF_TOPIC,
    TOPIC_PRACTICE_REQUEST,
    TOPIC_QUESTION_SOLVE,
    TOPIC_STUDY_PLAN,
)
from .normalizer import NormalizedInput
from .registry import RouteConfig

# ==================== 每日一练触发 ====================
# 整句精确匹配（compact 与之完全相等）。"开始每日一练"是前端启动器按钮文案，
# 见 app_impl.py 的 set_starters，改动按钮文案时必须同步这里。
PRACTICE_TRIGGERS_EXACT = (
    "开始每日一练",
    "每日一练",
    "开始练习",
    "开始今天的练习",
    "开始刷题",
    "随机抽题",
    "随机抽题练习",
    "来一题",
    "来道题",
    "我要刷题",
)
# 任意位置包含即触发
PRACTICE_TRIGGERS_CONTAINS = ("每日一练",)
# 宽松触发词：只在短消息（compact 长度 <= LOOSE_TRIGGER_MAX_LEN）且不含
# 疑问性标记时生效，防止"选择题做题技巧有哪些"这类教学提问被劫持进练习流程。
PRACTICE_TRIGGERS_LOOSE = (
    "刷题",
    "抽题",
    "做题",
    "练习题",
    "出题",
    "测验",
    "小测",
    "练一练",
    "来几道题",
    "来几道",
)
LOOSE_TRIGGER_MAX_LEN = 12
# 出现这些词说明用户在"问关于练习的问题"而不是"要开始练习"
_PRACTICE_NEGATIVE_MARKERS = ("技巧", "方法", "怎么", "如何", "什么", "为什么", "哪些", "吗")

# 练习挂起中允许打断工作流的退出词（由 pipeline 在续接前检查）
PRACTICE_EXIT_WORDS = ("退出练习", "结束练习", "不练了")

# ==================== 教学 topic 关键词表 ====================
# 强特征 2 分，弱特征 1 分；最高分的 topic 胜出。
_QUESTION_SOLVE_STRONG = (
    "这道题", "这题", "下面这道", "为什么选", "答案是什么", "选什么",
    "求解", "解析一下", "帮我算", "怎么做", "错在哪",
)
_QUESTION_SOLVE_WEAK = ("计算", "多少位", "多少个子网", "画出", "补全")
# 选项行特征："A."、"选B"这类真题文本
_QUESTION_SOLVE_PATTERNS = (
    re.compile(r"[abcd][.、．)]"),
    re.compile(r"选[abcd]\b|选[abcd]$|选[abcd][^a-z]"),
)

_EXAM_ANALYZE_STRONG = (
    "考点", "考纲", "大纲", "真题", "历年", "出题规律", "高频考",
    "题型", "分值", "及格", "通过率", "重点是", "哪些是重点", "丢分",
)
_EXAM_ANALYZE_WEAK = ("考试", "三级", "笔试", "上机", "占比", "考多少")

_STUDY_PLAN_STRONG = (
    "学习计划", "备考计划", "复习计划", "怎么备考", "怎么复习",
    "学习路线", "规划", "冲刺", "时间安排", "先学什么", "资源推荐",
)
_STUDY_PLAN_WEAK = ("零基础", "多久", "几周", "两周", "每天学", "顺序", "安排")

_CONCEPT_EXPLAIN_STRONG = (
    "什么是", "是什么", "解释", "讲讲", "讲解", "介绍一下", "区别",
    "定义", "原理", "概念", "为什么", "怎么理解", "干什么的",
)
# 领域名词：既是 concept 的弱特征，也是 off_topic 判定的领域白名单
DOMAIN_TERMS = (
    "osi", "tcp", "udp", "ip地址", "ip", "子网", "掩码", "cidr", "vlsm",
    "路由", "交换机", "集线器", "网桥", "vlan", "局域网", "广域网", "城域网",
    "以太网", "802", "wifi", "无线", "dns", "dhcp", "http", "https", "ftp",
    "smtp", "pop3", "telnet", "ssh", "nat", "acl", "vpn", "防火墙", "加密",
    "病毒", "木马", "入侵", "拓扑", "双绞线", "光纤", "同轴", "网络层",
    "传输层", "应用层", "物理层", "链路层", "七层", "五层", "三次握手",
    "四次挥手", "拥塞", "流量控制", "广播域", "冲突域", "网关", "网络",
    "服务器", "客户端", "带宽", "丢包", "延迟", "arp", "icmp", "rip",
    "ospf", "bgp", "组播", "端口",
)

# ==================== 难度关键词 ====================
_DIFFICULTY_BASIC_WORDS = (
    "通俗", "简单点", "简单些", "听不懂", "入门", "零基础", "小白",
    "讲得简单", "举个例子", "打个比方",
)
_DIFFICULTY_ADVANCED_WORDS = (
    "深入", "详细", "底层", "进阶", "高级", "原理层面", "源码", "深度", "全面",
)

# ==================== off_topic（保守黑名单） ====================
# 注意："游戏"一词不入黑名单——"网络游戏对带宽的要求"属于领域内问题。
OFF_TOPIC_BLACKLIST = (
    "天气", "股票", "基金", "彩票", "星座", "算命", "菜谱", "做饭",
    "减肥", "恋爱", "写首诗", "写一首诗", "写小说", "讲个笑话", "唱歌",
    "明星", "八卦", "旅游攻略", "王者荣耀", "原神", "电影推荐", "买什么车",
)

OFF_TOPIC_REPLY = (
    "我是计算机三级网络技术备考助手，这个问题超出了我的专业范围。\n\n"
    "你可以问我：\n"
    "- 网络概念讲解（如 TCP 三次握手、OSI 七层模型）\n"
    "- 真题与考点解析\n"
    "- 解题思路\n"
    "- 备考规划\n\n"
    "或者发送「开始每日一练」进行每日刷题。"
)


@dataclass
class RouteResult:
    topic: str
    difficulty: str = DIFFICULTY_NORMAL
    off_topic: bool = False
    matched: List[str] = field(default_factory=list)  # 命中的关键词，用于日志


def _score(compact: str, strong: tuple, weak: tuple, matched: List[str]) -> int:
    score = 0
    for kw in strong:
        if kw in compact:
            score += 2
            matched.append(kw)
    for kw in weak:
        if kw in compact:
            score += 1
            matched.append(kw)
    return score


def _detect_difficulty(compact: str, config: Optional[RouteConfig] = None) -> str:
    basic_words = config.difficulty_basic if config else _DIFFICULTY_BASIC_WORDS
    advanced_words = config.difficulty_advanced if config else _DIFFICULTY_ADVANCED_WORDS
    for kw in basic_words:
        if kw in compact:
            return DIFFICULTY_BASIC
    for kw in advanced_words:
        if kw in compact:
            return DIFFICULTY_ADVANCED
    return DIFFICULTY_NORMAL


def is_practice_trigger(compact: str, config: Optional[RouteConfig] = None) -> bool:
    exact = config.practice_exact if config else PRACTICE_TRIGGERS_EXACT
    contains = config.practice_contains if config else PRACTICE_TRIGGERS_CONTAINS
    loose = config.practice_loose if config else PRACTICE_TRIGGERS_LOOSE
    negative = config.practice_negative if config else _PRACTICE_NEGATIVE_MARKERS
    loose_max_len = config.loose_trigger_max_len if config else LOOSE_TRIGGER_MAX_LEN
    if compact in exact:
        return True
    if any(kw in compact for kw in contains):
        return True
    if len(compact) <= loose_max_len:
        if not any(neg in compact for neg in negative):
            if any(kw in compact for kw in loose):
                return True
    return False


def is_practice_exit(compact: str, config: Optional[RouteConfig] = None) -> bool:
    words = config.practice_exit if config else PRACTICE_EXIT_WORDS
    return any(kw in compact for kw in words)


def route(inp: NormalizedInput, config: Optional[RouteConfig] = None) -> RouteResult:
    compact = inp.compact
    difficulty = _detect_difficulty(compact, config)

    # 1) 练习触发（独占型 topic）
    if is_practice_trigger(compact, config):
        return RouteResult(
            topic=TOPIC_PRACTICE_REQUEST,
            difficulty=difficulty,
            matched=["practice_trigger"],
        )

    # 2) 教学 topic 打分
    if config:
        priority = [
            topic.topic
            for topic in sorted(config.topics.values(), key=lambda item: (item.route_priority, item.topic))
            if topic.is_teaching and topic.enabled
        ]
        if not priority:
            priority = [TOPIC_CONCEPT_EXPLAIN]
        matched = {topic: [] for topic in priority}
        scores = {topic: 0 for topic in priority}
        for topic in priority:
            groups = config.topic_keywords.get(topic) or {}
            strong = tuple(groups.get("strong") or [])
            weak_words = list(groups.get("weak") or [])
            if topic == TOPIC_CONCEPT_EXPLAIN:
                weak_words.extend(config.domain_terms)
            scores[topic] += _score(compact, strong, tuple(weak_words), matched[topic])
            for pattern_text in groups.get("pattern") or []:
                try:
                    if re.search(pattern_text, compact):
                        scores[topic] += 2
                        matched[topic].append(pattern_text)
                except re.error:
                    continue
        domain_terms = config.domain_terms
        off_topic_blacklist = config.off_topic_blacklist
    else:
        matched = {t: [] for t in (
            TOPIC_QUESTION_SOLVE, TOPIC_EXAM_ANALYZE, TOPIC_STUDY_PLAN, TOPIC_CONCEPT_EXPLAIN,
        )}
        scores = {
            TOPIC_QUESTION_SOLVE: _score(
                compact, _QUESTION_SOLVE_STRONG, _QUESTION_SOLVE_WEAK, matched[TOPIC_QUESTION_SOLVE]
            ),
            TOPIC_EXAM_ANALYZE: _score(
                compact, _EXAM_ANALYZE_STRONG, _EXAM_ANALYZE_WEAK, matched[TOPIC_EXAM_ANALYZE]
            ),
            TOPIC_STUDY_PLAN: _score(
                compact, _STUDY_PLAN_STRONG, _STUDY_PLAN_WEAK, matched[TOPIC_STUDY_PLAN]
            ),
            TOPIC_CONCEPT_EXPLAIN: _score(
                compact, _CONCEPT_EXPLAIN_STRONG, DOMAIN_TERMS, matched[TOPIC_CONCEPT_EXPLAIN]
            ),
        }
        for pattern in _QUESTION_SOLVE_PATTERNS:
            if pattern.search(compact):
                scores[TOPIC_QUESTION_SOLVE] += 2
                matched[TOPIC_QUESTION_SOLVE].append(pattern.pattern)
        priority = (
            TOPIC_QUESTION_SOLVE, TOPIC_EXAM_ANALYZE, TOPIC_STUDY_PLAN, TOPIC_CONCEPT_EXPLAIN,
        )
        domain_terms = DOMAIN_TERMS
        off_topic_blacklist = OFF_TOPIC_BLACKLIST

    domain_hits = any(kw in compact for kw in domain_terms)
    total_score = sum(scores.values())

    # 3) off_topic 门：黑名单命中且教学表+领域白名单零命中才拒答
    blacklist_hits = [kw for kw in off_topic_blacklist if kw in compact]
    if blacklist_hits and total_score == 0 and not domain_hits:
        return RouteResult(
            topic=TOPIC_OFF_TOPIC,
            difficulty=difficulty,
            off_topic=True,
            matched=blacklist_hits,
        )

    # 4) 最高分胜出；平手按 question.solve > exam.analyze > study.plan >
    #    concept.explain；零命中默认 concept.explain
    best = max(priority, key=lambda t: (scores[t], -priority.index(t)))
    if scores[best] == 0:
        best = TOPIC_CONCEPT_EXPLAIN if TOPIC_CONCEPT_EXPLAIN in scores else priority[0]
    return RouteResult(topic=best, difficulty=difficulty, matched=matched[best])
