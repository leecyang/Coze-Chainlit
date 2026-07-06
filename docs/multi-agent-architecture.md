# 灵犀（LingXi）多智能体架构设计文档

> 适用范围：`backend/chainlit/lingxi/multi_agent/` 及其宿主接入点 `backend/chainlit/lingxi/app_impl.py`，
> 管理端 UI：`frontend/src/lingxi/AdminPage.tsx`。
> 版本对应：`dev/v3-upgrade-beta` 分支，截至提交 `48c7255`（解决数据库锁竞争问题）。
>
> 本文档侧重**设计思路的完整叙事**（为什么这么设计、各模块如何协作、结合源码逐段讲解）。
> 如果只需要查字段表/接口 schema 速查，见同目录下的
> [`multi_agent/AGENT_SPECS.md`](../backend/chainlit/lingxi/multi_agent/AGENT_SPECS.md)。

## 目录

1. [设计目标与总体思路](#1-设计目标与总体思路)
2. [核心概念与数据流](#2-核心概念与数据流)
3. [模块地图](#3-模块地图)
4. [消息模型：Message 与 Topic](#4-消息模型message-与-topic)
5. [Router：任务分类与难度识别](#5-router任务分类与难度识别)
6. [Agent 抽象与依赖注入](#6-agent-抽象与依赖注入)
7. [MessageBus：订阅-发布总线](#7-messagebus订阅-发布总线)
8. [ResponseSelector：竞价与仲裁](#8-responseselector竞价与仲裁)
9. [MultiAgentPipeline：编排主流程](#9-multiagentpipeline编排主流程)
10. [Registry：数据库支撑的智能体注册表](#10-registry数据库支撑的智能体注册表)
11. [每日一练：独占型 Workflow Agent 与工具调用](#11-每日一练独占型-workflow-agent-与工具调用)
12. [宿主接入：与 Chainlit / Coze 的边界](#12-宿主接入与-chainlit--coze-的边界)
13. [管理端 UI：卡片墙与分步注册向导](#13-管理端-ui卡片墙与分步注册向导)
14. [跨 Agent 上下文与长期记忆](#14-跨-agent-上下文与长期记忆)
15. [并发与稳定性：数据库锁竞争修复](#15-并发与稳定性数据库锁竞争修复)
16. [离线自测](#16-离线自测)
17. [扩展指南：如何新增一个智能体](#17-扩展指南如何新增一个智能体)
18. [设计取舍与已知边界](#18-设计取舍与已知边界)

---

## 1. 设计目标与总体思路

灵犀是一个面向"计算机三级网络技术"备考场景的 Chainlit 聊天应用。v3 架构把原来"一个 Bot 打天下"的单体对话，重构成了一套**订阅-发布（pub/sub）式多智能体系统**。核心设计思路可以归纳为四点：

1. **任务与角色解耦**：路由层只判断"用户想做什么"（任务型 topic，如 `concept.explain`），不判断"该由谁回答"。谁来回答由订阅关系和竞价机制决定，这样新增/替换角色不需要改路由逻辑。
2. **纯逻辑核心 + 宿主适配层**：`multi_agent/` 包内的模块（`message.py`、`bus.py`、`router.py`、`selector.py`、`normalizer.py`、`registry.py`）**不 import chainlit**，也**不 import app_impl**，可以脱离 Web 框架单独运行和单元测试（见 [第 16 节](#16-离线自测)）。所有对宿主能力的依赖都通过 `AgentDeps` 依赖注入容器传入，避免循环导入，也让"底层协议 = Coze"这件事对路由/竞价逻辑完全透明。
3. **数据库驱动的注册表，而非硬编码 Agent 类**：智能体的身份、Bot 绑定、订阅的 topic、竞价参数全部存在 SQLite 的 `agent_definitions` / `agent_subscriptions` / `route_topics` / `route_keywords` 表中，管理员可以在 Web 管理页里可视化增删改，不需要改代码、重新部署。
4. **竞价制而非规则树**：每个智能体对一条任务消息给出一个 0~1 的置信度出价（`bid`），由 `ResponseSelector` 综合出价、连续性加分（避免来回切换人设）、优先级来裁决赢家。这比"if topic == X then agent = Y"的静态映射更容易表达"多个人设都能回答但风格不同"的场景（新手小白 / 辩论对手 / 计网专家）。

---

## 2. 核心概念与数据流

一条用户消息从进入系统到产生回复，完整流经以下阶段：

```
用户原始输入
  → MessageNormalizer 标准化（全角转半角、去空白、大小写归一）
  → 【续接优先】若练习工作流处于挂起态，直达 Daily_Practice_Agent
  → Router 判定任务型 topic + 难度（off_topic 走模板拒答，零 LLM 成本）
  → MessageBus.publish 任务消息（按订阅关系找到候选 Agent）
  → 独占型 topic：唯一订阅者直接执行
    教学型 topic：各订阅者 bid() 竞价
  → ResponseSelector 按 (竞价 + 连续性加分) 选出赢家
  → 赢家调用自己绑定的 Coze Bot，流式生成并写回 cl_msg
  → agent.response 消息重新发布到总线（供观测/未来扩展）
  → session 记账（last_agent / last_topic / recent_history）
```

对应的核心文件：

| 阶段 | 模块 |
|---|---|
| 标准化 | `multi_agent/normalizer.py` |
| 任务分类 | `multi_agent/router.py` |
| 消息封装 | `multi_agent/message.py` |
| 发布订阅 | `multi_agent/bus.py` |
| 竞价仲裁 | `multi_agent/selector.py` |
| Agent 基类 | `multi_agent/base.py` |
| 具体 Agent 实现 | `multi_agent/teaching_agents.py`、`multi_agent/practice_agent.py` |
| 注册表（DB 读写） | `multi_agent/registry.py` |
| 编排入口 | `multi_agent/pipeline.py` |
| 长期记忆 | `multi_agent/memory.py` |
| 离线自测 | `multi_agent/selftest.py` |
| 宿主接入 | `app_impl.py` |
| 管理 UI | `frontend/src/lingxi/AdminPage.tsx` |

---

## 3. 模块地图

```
backend/chainlit/lingxi/
├── app_impl.py                  # Chainlit 事件处理器、Coze HTTP 客户端、Admin REST API
├── migrations.py                # 版本化 SQL 迁移执行器
└── multi_agent/
    ├── __init__.py
    ├── base.py                  # BaseAgent 基类 + AgentDeps 依赖注入容器
    ├── message.py                # Message 数据结构 + Topic 常量
    ├── normalizer.py             # 输入标准化（纯函数）
    ├── router.py                 # 任务分类器（纯函数 + 关键词表）
    ├── bus.py                    # 订阅-发布总线
    ├── selector.py                # 竞价仲裁
    ├── registry.py                # DB-backed 注册表 CRUD
    ├── teaching_agents.py         # 教学型 Agent（Coze Bot 包装）
    ├── practice_agent.py          # 每日一练 Agent（Coze Workflow 包装）
    ├── memory.py                  # 用户长期记忆（错题提炼）
    ├── pipeline.py                 # MultiAgentPipeline：把以上串联成主流程
    └── selftest.py                 # 离线自测（不需要网络/chainlit）

backend/migrations/
├── 001_baseline.sql              # 基础表（用户、会话映射、配置等）
├── 002_multi_agent_registry.sql  # 注册表 schema：agent_definitions / agent_subscriptions / route_topics / route_keywords / route_settings
└── 003_seed_default_agents.sql   # 默认 4 个 Agent + 7 个 topic + 竞价表种子数据

frontend/src/lingxi/
├── AdminPage.tsx                  # 管理页：智能体卡片墙 + 分步注册向导 + 路由词表编辑
└── api.ts
```

**架构上的一个关键约束**（在 `base.py` 文档字符串里明确写出）：

> `multi_agent` 包内模块允许 `import chainlit`（读写 `user_session`），但绝不 `import app_impl`——所有对宿主的依赖都通过 `AgentDeps` 注入，避免循环导入。

这意味着依赖方向永远是单向的：`app_impl.py` → `multi_agent/*`，反过来则不允许，从物理上防止了"宿主细节渗透进编排核心"。

---

## 4. 消息模型：Message 与 Topic

所有在总线上流转的消息都统一封装为 `Message` 对象（[message.py](../backend/chainlit/lingxi/multi_agent/message.py)）：

```python
@dataclass
class Message:
    topic: str
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
```

`topic` 一律是**任务型主题**（`concept.explain`、`question.solve`……），而不是角色名——这是解耦路由与人设的关键设计。系统内置的任务 topic：

```python
TOPIC_USER_INPUT       = "user.input"
TOPIC_CONCEPT_EXPLAIN  = "concept.explain"   # 概念讲解
TOPIC_EXAM_ANALYZE     = "exam.analyze"      # 考点分析
TOPIC_QUESTION_SOLVE   = "question.solve"    # 解题答疑
TOPIC_STUDY_PLAN       = "study.plan"        # 备考规划
TOPIC_PRACTICE_REQUEST = "practice.request"  # 每日一练发起（独占）
TOPIC_PRACTICE_ANSWER  = "practice.answer"   # 每日一练续接（独占）
TOPIC_PRACTICE_REPORT  = "practice.report"   # 练习结果观测（预留扩展点）
TOPIC_AGENT_RESPONSE   = "agent.response"    # 赢家的回复重新发布，供观测
TOPIC_OFF_TOPIC        = "off_topic"         # 超纲拒答
```

`TEACHING_TOPICS` 是三个教学 Agent 共同订阅的任务集合；`EXCLUSIVE_TOPICS` 标记只允许单一订阅者的 topic（每日一练的请求/续接，防止工作流被多个 Agent 抢占）。

派生消息用 `derive()`，语义是"payload 浅拷贝 + 覆盖字段 + 重新生成 id/时间戳"：

```python
def derive(msg: Message, *, topic: str, sender: str, **payload_updates: Any) -> Message:
    payload = dict(msg.payload)
    payload.update(payload_updates)
    return Message(topic=topic, sender=sender, payload=payload)
```

`payload` 的约定结构（非强制 schema，写在 docstring 里）：

```python
{
    "username": str,
    "user_message": str,
    "context": {
        "recent_summary": str,     # 近几轮对话摘要
        "recent_turns": list[str], # 最近 2 轮，供跨 Agent 切换时注入 Coze
        "last_topic": str | None,
        "last_agent": str | None,
    },
    "memory": {
        "备考阶段": str,
        "基础水平": str,
        "薄弱知识点": list[str],
    },
    "difficulty": "basic" | "normal" | "advanced",
    "off_topic": bool,
}
```

---

## 5. Router：任务分类与难度识别

[router.py](../backend/chainlit/lingxi/multi_agent/router.py) 是一个**纯规则的分类器**，不调用 LLM，成本为零。它只回答"这是什么任务"，绝不指定人设。评估顺序（源码注释即设计文档）：

```
练习触发 → off_topic 门 → 教学 topic 打分 → 默认 concept.explain
```

### 5.1 练习触发：三级触发词 + 否定护栏

为了让"开始每日一练"这类固定文案 100% 命中，同时不误伤"选择题做题技巧有哪些"这种正常提问，触发判定分了三个强度：

```python
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
```

- **exact**：整句精确匹配（如"开始每日一练"，必须与前端启动器按钮文案完全同步，源码注释里专门标注了这个耦合点）。
- **contains**：任意位置包含即触发（如"每日一练"）。
- **loose**：短消息（`compact` 长度 ≤ 12）且不含疑问性标记（"怎么"、"如何"、"哪些"、"吗"……）才生效——这是为了让"刷题"这种短词触发练习，但"选择题做题技巧有哪些"这种长句 + 疑问词不被误判。

### 5.2 教学 topic 打分

四个教学 topic（`question.solve` / `exam.analyze` / `study.plan` / `concept.explain`）各自维护**强特征（2 分）/ 弱特征（1 分）/ 正则模式（2 分）**关键词表，逐一打分，最高分胜出：

```python
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
```

`question.solve` 还额外用正则匹配"选项行特征"（如"A."、"选B"这类真题原文）：

```python
_QUESTION_SOLVE_PATTERNS = (
    re.compile(r"[abcd][.、．)]"),
    re.compile(r"选[abcd]\b|选[abcd]$|选[abcd][^a-z]"),
)
```

打平手时的默认优先级（无注册表配置时）：`question.solve > exam.analyze > study.plan > concept.explain`；零命中默认落到 `concept.explain`。

### 5.3 off_topic 门：保守黑名单 + 领域白名单豁免

```python
blacklist_hits = [kw for kw in off_topic_blacklist if kw in compact]
if blacklist_hits and total_score == 0 and not domain_hits:
    return RouteResult(topic=TOPIC_OFF_TOPIC, difficulty=difficulty,
                        off_topic=True, matched=blacklist_hits)
```

只有"黑名单命中 **且** 教学关键词零命中 **且** 领域词零命中"三者同时成立才拒答。这样"网络游戏对带宽的要求高吗"（含"游戏"但也含领域词"带宽"）不会被误拒——源码注释特别指出"游戏"一词故意不放入黑名单。

### 5.4 难度识别

与 topic 分类并行，`_detect_difficulty()` 根据"通俗/简单点/零基础"vs"深入/详细/底层/进阶"关键词判断 `basic` / `advanced` / `normal`，结果写入 `payload["difficulty"]`，用于后续竞价加权（见 [第 8 节](#8-responseselector竞价与仲裁)）。

---

## 6. Agent 抽象与依赖注入

[base.py](../backend/chainlit/lingxi/multi_agent/base.py) 定义了两个核心类型：`AgentDeps`（宿主能力的依赖注入容器）与 `BaseAgent`（所有智能体的基类）。

```python
@dataclass
class AgentDeps:
    """由 app_impl 注入的宿主能力。"""
    coze_factory: Callable[[Optional[str], str], Any]      # (auth_token, bot_id) -> CozeAPI
    get_token: Callable[[str], Awaitable[Optional[str]]]    # username -> token
    register_conversation: Callable[[str, str], None]       # (conversation_id, username)
    get_bot_id: Callable[[str], str]                        # config key -> bot id（含回退）
    log_usage: Callable[[str, str, Optional[str]], None]    # (username, display_name, thread_id)


class BaseAgent:
    name: str = "Base_Agent"
    display_name: str = "基础智能体"
    bot_env_key: str = "COZE_BOT_ID"
    bot_id_override: str = ""
    subscribed_topics: Tuple[str, ...] = ()

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    def bid(self, msg: Message) -> float:
        """对任务消息给出置信度竞价（0~1，规则化，不调用 LLM）。"""
        return 0.0

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        """处理消息并把回复流式写入 cl_msg。
        Returns: {"content": str|None, "requires_action": dict|None}
        """
        raise NotImplementedError
```

这个契约体现了"订阅-竞价-执行"三段式：

1. **订阅**（`subscribed_topics`）：声明我关心哪些任务，供 Bus 建立路由表。
2. **竞价**（`bid`）：面对一条已发布的任务消息，给出我有多大把握能答好，纯规则打分，不调用 LLM——避免为了"决定谁来答"就先烧一次 LLM token。
3. **执行**（`act`）：真正调用 Coze Bot 生成内容，流式写回 `cl_msg`，返回统一结构 `{"content", "requires_action"}`（`requires_action` 用于工作流挂起，详见 [第 11 节](#11-每日一练独占型-workflow-agent-与工具调用)）。

`BaseAgent` 还提供了两个通用能力，供子类直接复用：

- **`_get_coze` / `_ensure_conversation`**：惰性创建并缓存每个 Agent 自己的 Coze 会话 ID（存进 `cl.user_session`），并通过 `deps.register_conversation` 登记 `conversation_id -> username` 映射（Coze 工作流的 HTTP 回调依赖这个映射解析用户身份）。
- **`get_state` / `set_state``**：每个 Agent 独立的 session 状态存取（`SESSION_AGENT_STATE = {agent_name: {...}}`），纯字符串/JSON 可序列化的 dict，Chainlit 会通过 thread metadata 自动持久化并在断线重连后还原。

---

## 7. MessageBus：订阅-发布总线

[bus.py](../backend/chainlit/lingxi/multi_agent/bus.py) 是一个进程内的订阅-发布总线，纯模块，不依赖 chainlit：

```python
class MessageBus:
    def __init__(self, exclusive_topics: Optional[Iterable[str]] = None) -> None:
        self._subscribers: Dict[str, List[Any]] = {}
        self.exclusive_topics = (
            frozenset(exclusive_topics) if exclusive_topics is not None else EXCLUSIVE_TOPICS
        )

    def subscribe(self, topic: str, agent: Any) -> None:
        subs = self._subscribers.setdefault(topic, [])
        if topic in self.exclusive_topics and subs:
            raise ValueError(
                f"独占型 topic '{topic}' 已有订阅者 "
                f"{getattr(subs[0], 'name', subs[0])}，拒绝重复订阅"
            )
        if agent not in subs:
            subs.append(agent)

    def publish(self, msg: Message) -> List[Any]:
        """发布消息，返回该 topic 的订阅者列表（由调用方驱动 observe/act）。"""
        subs = self.subscribers_for(msg.topic)
        ...
        return subs
```

关键设计点：

- **独占型 topic 的硬约束**：`practice.request` / `practice.answer` 默认独占（`EXCLUSIVE_TOPICS`），管理端也可以把自定义 topic 标记 `is_exclusive`。独占 topic 只允许一个订阅者，重复订阅在 `subscribe()` 时立即抛 `ValueError`——把"练习工作流不能被多个 Agent 干扰"这个业务约束下沉成了数据结构层面的强制。
- **Bus 只负责"发布 + 返回订阅者列表"，不驱动执行**：`publish()` 不调用任何 `act()`，执行逻辑完全交给调用方（`MultiAgentPipeline`）。这让 Bus 保持纯粹的路由职责，方便单测。
- **构建时的防御式降级**：`Pipeline` 在批量注册订阅时，如果某个 Agent 对独占 topic 的订阅冲突，只打印日志跳过该订阅，**不让整个消息管线构建失败**（见第 9 节 `_build_agent` 之后的循环）。

---

## 8. ResponseSelector：竞价与仲裁

[selector.py](../backend/chainlit/lingxi/multi_agent/selector.py) 实现"谁来回答"的仲裁逻辑：

```python
CONTINUITY_BONUS = 0.10  # 与上一轮实际输出的 Agent 相同时加分（减少乒乓切换）

def select(
    bids: List[Tuple[str, float]],
    msg: Message,
    priorities: Optional[Dict[str, int]] = None,
) -> Selection:
    last_agent = (msg.payload.get("context") or {}).get("last_agent")
    ...
    for name, bid in bids:
        continuity_bonus = CONTINUITY_BONUS if name == last_agent else 0.0
        total = bid + continuity_bonus
        ...
    best_score = max(s for _, s in scored)
    contenders = [name for name, s in scored if abs(s - best_score) < 1e-9]

    if len(contenders) > 1:
        # 平手：上一轮 Agent > 注册表优先级 > Agent ID 字典序。
        if last_agent in contenders:
            winner = last_agent
        else:
            winner = min(contenders, key=lambda n: (priorities.get(n, 100), n))
    else:
        winner = contenders[0]
    return Selection(agent_name=winner, score=best_score, breakdown=breakdown)
```

裁决规则分三层：

1. **总分 = 竞价 bid + 连续性加分**。连续性加分（+0.10）只在**分差足够小**时才能反超，不是强制粘滞——`selftest.py` 里有专门用例验证"连续性可反超小分差"但"连续性不强制"（`exam.analyze` 场景即便上一轮是 `Novice_Learner`，只要 `Network_Expert` 分数明显更高依然赢）。
2. **难度加权**：`bid()` 里的 `basic_bonus` / `advanced_bonus`（详见第 10 节竞价表）让同一 topic 在不同难度下把出价"翻转"，例如零基础用户的 `study.plan` 请求，`Novice_Learner` 因为 `basic_bonus` 更高反超 `Network_Expert`。
3. **平手仲裁**：先看上一轮 Agent 是否在候选中（保连续性），否则按注册表 `priority` 字段（越小越优先），最后按 Agent ID 字典序兜底，保证确定性（同样输入必然得到同样结果，便于测试和调试）。

---

## 9. MultiAgentPipeline：编排主流程

[pipeline.py](../backend/chainlit/lingxi/multi_agent/pipeline.py) 是整个系统的编排入口，把标准化、路由、总线、竞价、执行串联起来。

### 9.1 初始化：从 DB 加载注册表并建立订阅

```python
class MultiAgentPipeline:
    def __init__(self, deps: AgentDeps, db_path: str) -> None:
        self.deps = deps
        self.db_path = db_path
        self.snapshot = load_registry(db_path)
        self.route_config = self.snapshot.route_config
        self.exclusive_topics = frozenset(EXCLUSIVE_TOPICS) | {
            topic for topic, config in self.route_config.topics.items()
            if config.is_exclusive
        }
        self.bus = MessageBus(self.exclusive_topics)
        self.practice_agent = DailyPracticeAgent(
            deps, self.snapshot.agents.get("Daily_Practice_Agent"),
        )
        self.agents: Dict[str, BaseAgent] = {}

        for config in self.snapshot.agents.values():
            agent = self._build_agent(config)
            self.agents[agent.name] = agent
        for agent in self.agents.values():
            for topic in agent.subscribed_topics:
                try:
                    self.bus.subscribe(topic, agent)
                except ValueError as e:
                    print(f"[MultiAgent] 跳过订阅冲突 {agent.name} -> {topic}: {e}")

    def _build_agent(self, config: AgentConfig) -> BaseAgent:
        if config.agent_id == "Daily_Practice_Agent":
            return self.practice_agent
        return RegisteredCozeAgent(self.deps, config)
```

`Pipeline` 是**每次注册表变更后重建的单例**：管理端任何 CRUD 操作都会调用 `_invalidate_pipeline()`（见第 12 节），下次 `on_message` 触发 `_get_pipeline()` 时会用最新的 DB 快照重新构建整个 Agent 集合与订阅关系——这是"数据库即配置源"在运行时生效的关键机制。

### 9.2 主入口 `handle()`：续接优先 + 正常路由两条路径

```python
async def handle(self, username, raw_text, thread_id, cl_msg):
    inp = normalize(raw_text)

    # ---------- 续接优先：练习工作流挂起时，本条消息属于问答节点 ----------
    pending = self.practice_agent.get_state().get("pending_tool_action")
    if pending:
        if is_practice_exit(inp.compact, self.route_config):
            self.practice_agent.set_state(pending_tool_action=None)
            await self._stream_template(cl_msg, _PRACTICE_EXIT_REPLY)
            ...
            return
        ...
        msg = await self._build_message(username, inp.text)
        answer_msg = derive(msg, topic=TOPIC_PRACTICE_ANSWER, sender="router", pending_action=pending)
        self.practice_agent.set_state(pending_tool_action=None)
        self.bus.publish(answer_msg)
        await self._run_agent(self.practice_agent, answer_msg, cl_msg, thread_id, had_pending=True)
        return

    # ---------- 正常路由 ----------
    msg = await self._build_message(username, inp.text)
    result = route(inp, self.route_config)
    msg.payload["difficulty"] = result.difficulty
    msg.payload["off_topic"] = result.off_topic

    if result.off_topic:
        await self._stream_template(cl_msg, self.route_config.off_topic_reply or OFF_TOPIC_REPLY)
        ...
        return

    task_msg = derive(msg, topic=result.topic, sender="router")
    subscribers = self.bus.publish(task_msg)
    ...
    if task_msg.topic in self.exclusive_topics:
        winner = subscribers[0]  # 独占型 topic：唯一订阅者
    else:
        bids = [(agent.name, agent.bid(task_msg)) for agent in subscribers]
        priorities = {agent.name: int(getattr(agent, "priority", 100)) for agent in subscribers}
        selection = select(bids, task_msg, priorities)
        winner = self.agents[selection.agent_name]

    await self._run_agent(winner, task_msg, cl_msg, thread_id, had_pending=False)
```

设计要点：

- **续接优先级最高**：如果每日一练工作流处于 `requires_action` 挂起态，无论用户这条消息在语义上像什么，都优先当作"对挂起问题的回答"路由给练习 Agent（除非命中退出词）。这避免了 Router 的关键词匹配去"误解释"一个纯粹的答题输入（比如答案就是"A"，如果走正常路由可能被打成别的 topic）。
- **off_topic 走模板，不消耗 LLM**：命中拒答规则时直接流式输出模板文案，不调用任何 Agent、不记使用日志。
- **无订阅者时的分级兜底**：练习类 topic 无订阅者 → 提示"每日一练已停用"；其他独占 topic 无订阅者 → 保持独占语义拒绝回退；教学 topic 无人订阅 → 兜底把消息广播给除练习 Agent 外的全部 Agent 竞价，实在没有可用 Agent 才提示联系管理员。这层层递进的容错设计保证了管理端误操作（比如一次性停用所有教学 Agent）不会让整个应用崩溃，只会优雅降级成提示信息。

### 9.3 执行与记账 `_run_agent()`

```python
async def _run_agent(self, agent, msg, cl_msg, thread_id, had_pending):
    username = msg.payload.get("username", "unknown")
    await asyncio.to_thread(self.deps.log_usage, username, agent.display_name, thread_id)

    result = await agent.act(msg, cl_msg)
    content = result.get("content") if isinstance(result, dict) else result
    requires_action = result.get("requires_action") if isinstance(result, dict) else None

    if agent is self.practice_agent:
        self.practice_agent.set_state(pending_tool_action=requires_action or None)
        if requires_action:
            ...
        elif had_pending:
            report = derive(msg, topic=TOPIC_PRACTICE_REPORT, sender=agent.name,
                             report_summary=(content or "")[:200])
            self.bus.publish(report)
    elif requires_action:
        print(f"[Pipeline] 警告: {agent.name} 返回 requires_action，教学 Bot 不应挂载工作流，已忽略")

    ...
    self.bus.publish(derive(msg, topic=TOPIC_AGENT_RESPONSE, sender=agent.name,
                             response_preview=(content or "")[:120]))
    ...
    self._bookkeep(msg.payload.get("user_message", ""), msg.topic, agent.name, content or "")
```

- **挂起状态统一由 Pipeline 写回**：`practice_agent.set_state()` 只在这里被调用，`act()` 内部只读不写，职责单一。
- **`agent.response` 二次发布**：赢家的回复内容会作为新消息重新发布到总线，topic 是观测性质的 `agent.response`，目前没有订阅者消费，是留给未来扩展（比如审计、多 Agent 协作评审）的钩子。
- **教学 Agent 若误返回 `requires_action` 只打警告并忽略**：这是一个防御性设计，因为工作流挂起语义目前只属于每日一练。

### 9.4 上下文构建 `_build_message()` 与记账 `_bookkeep()`

```python
async def _build_message(self, username: str, text: str) -> Message:
    memory = await asyncio.to_thread(fetch_user_memory, self.db_path, username)
    history: List[str] = cl.user_session.get(SESSION_RECENT_HISTORY) or []
    context = {
        "recent_summary": "\n".join(history),
        "recent_turns": history[-2:],
        "last_topic": cl.user_session.get(SESSION_LAST_TOPIC),
        "last_agent": cl.user_session.get(SESSION_LAST_AGENT),
    }
    return new_user_message(username, text, context, memory)

def _bookkeep(self, user_text, topic, agent_name, reply) -> None:
    if agent_name:
        cl.user_session.set(SESSION_LAST_AGENT, agent_name)
    cl.user_session.set(SESSION_LAST_TOPIC, topic)
    history = cl.user_session.get(SESSION_RECENT_HISTORY) or []
    history.append(f"用户: {user_text[:60]} | {agent_name or 'system'}({topic}): {reply[:60]}")
    cl.user_session.set(SESSION_RECENT_HISTORY, history[-_RECENT_HISTORY_CAP:])
```

每轮对话都会把"用户说了什么 + 谁用什么 topic 回答了什么"压缩成一行摘要，滚动保留最近 6 轮（`_RECENT_HISTORY_CAP = 6`），存入 `cl.user_session`。这个滚动摘要供 `_build_message` 下一轮取用，也供 `RegisteredCozeAgent.act()` 在跨 Agent 切换时注入最近 2 轮上下文（见第 6.2 节）。

---

## 10. Registry：数据库支撑的智能体注册表

[registry.py](../backend/chainlit/lingxi/multi_agent/registry.py) 是纯 sqlite3 模块（同步 I/O，调用方用 `asyncio.to_thread` 包裹），负责把 4 张表读成强类型的 `RegistrySnapshot`，并提供管理端 CRUD。

### 10.1 数据库 Schema

来自迁移文件 [002_multi_agent_registry.sql](../backend/migrations/002_multi_agent_registry.sql)：

```sql
CREATE TABLE IF NOT EXISTS agent_definitions (
    "agent_id" TEXT PRIMARY KEY,
    "display_name" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "agent_type" TEXT NOT NULL DEFAULT 'coze_chat',      -- coze_chat | coze_workflow
    "bot_id" TEXT NOT NULL DEFAULT '',
    "enabled" INTEGER NOT NULL DEFAULT 1,
    "system_builtin" INTEGER NOT NULL DEFAULT 0,          -- 系统内置不可删除
    "locked" INTEGER NOT NULL DEFAULT 0,                  -- 锁定：仅 bot_id/enabled 可改
    "exclusive" INTEGER NOT NULL DEFAULT 0,
    "priority" INTEGER NOT NULL DEFAULT 100,              -- 平手仲裁用，越小越优先
    "context_policy" TEXT NOT NULL DEFAULT 'on_switch_recent_2',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK ("agent_type" IN ('coze_chat', 'coze_workflow')),
    CHECK ("context_policy" IN ('on_switch_recent_2', 'none'))
);

CREATE TABLE IF NOT EXISTS agent_subscriptions (
    "agent_id" TEXT NOT NULL,
    "topic" TEXT NOT NULL,
    "base_bid" REAL NOT NULL DEFAULT 0,
    "basic_bonus" REAL NOT NULL DEFAULT 0,
    "advanced_bonus" REAL NOT NULL DEFAULT 0,
    PRIMARY KEY ("agent_id", "topic"),
    FOREIGN KEY ("agent_id") REFERENCES agent_definitions("agent_id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS route_topics (
    "topic" TEXT PRIMARY KEY,
    "display_name" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "is_teaching" INTEGER NOT NULL DEFAULT 1,
    "is_exclusive" INTEGER NOT NULL DEFAULT 0,
    "route_priority" INTEGER NOT NULL DEFAULT 100,
    "enabled" INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS route_keywords (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "scope" TEXT NOT NULL,      -- topic | practice | global
    "topic" TEXT,
    "kind" TEXT NOT NULL,       -- strong | weak | pattern | exact | contains | loose | negative | exit | ...
    "keyword" TEXT NOT NULL,
    "enabled" INTEGER NOT NULL DEFAULT 1,
    "priority" INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS route_settings (
    "key" TEXT PRIMARY KEY,
    "value" TEXT NOT NULL DEFAULT ''
);
```

`agent_definitions` 与 `agent_subscriptions` 一对多，`route_topics` 定义可路由的任务型 topic，`route_keywords` 用 `(scope, topic, kind)` 三元组统一承载练习触发词、教学关键词、难度词、黑名单——即 Router 里所有硬编码常量在生产环境都有对应的可编辑数据行。

### 10.2 种子数据：默认 4 个 Agent

[003_seed_default_agents.sql](../backend/migrations/003_seed_default_agents.sql) 预置了三个教学人设 + 一个练习工作流 Agent：

```sql
INSERT OR IGNORE INTO agent_definitions
    (agent_id, display_name, description, agent_type, bot_id, enabled, system_builtin, locked, exclusive, priority, context_policy)
VALUES
    ('Novice_Learner',   '新手小白', '面向零基础用户，用费曼反问和类比帮助用户讲清楚。', 'coze_chat', ..., 1, 1, 0, 0, 20, 'on_switch_recent_2'),
    ('Debate_Challenger','辩论对手', '用反例、边界条件和陷阱题挑战学习者理解。',       'coze_chat', ..., 1, 1, 0, 0, 30, 'on_switch_recent_2'),
    ('Network_Expert',   '计网专家', '系统讲解、考试映射和规范推导。',                'coze_chat', ..., 1, 1, 0, 0, 10, 'on_switch_recent_2'),
    ('Daily_Practice_Agent', '每日一练', '系统锁定的每日一练 Coze Workflow Agent。',  'coze_workflow', ..., 1, 1, 1, 1, 1, 'none');
```

竞价表（`agent_subscriptions`）体现了三个人设的性格差异：

```sql
INSERT OR IGNORE INTO agent_subscriptions (agent_id, topic, base_bid, basic_bonus, advanced_bonus) VALUES
    ('Novice_Learner',    'concept.explain', 0.60, 0.10, 0.00),
    ('Novice_Learner',    'study.plan',      0.65, 0.10, 0.00),
    ('Debate_Challenger', 'question.solve',  0.70, 0.00, 0.05),
    ('Network_Expert',    'exam.analyze',    0.75, 0.00, 0.10),
    ('Network_Expert',    'question.solve',  0.65, 0.00, 0.10),
    ('Daily_Practice_Agent', 'practice.request', 1.00, 0.00, 0.00),
    ('Daily_Practice_Agent', 'practice.answer',  1.00, 0.00, 0.00);
```

可以看出："计网专家"在正常/进阶难度下对所有教学 topic 出价最高（专业可信度），"新手小白"靠 `basic_bonus` 在零基础场景反超，"辩论对手"则专精 `question.solve` 且随难度上升更自信（`advanced_bonus`）。每日一练固定出价 1.0——但因为是独占 topic，其实根本不走竞价环节，直接取唯一订阅者。

### 10.3 CRUD API 中的业务规则

`registry.py` 里几处强校验对应管理端体验中的"防呆"设计：

```python
def _validate_agent_id(agent_id: str) -> str:
    value = (agent_id or "").strip()
    if not _AGENT_ID_RE.match(value):   # ^[A-Za-z][A-Za-z0-9_]{1,63}$
        raise ValueError("Agent ID 只能使用英文字母开头的字母、数字和下划线，长度 2-64")
    return value
```

```python
def update_agent(db_path, agent_id, payload):
    ...
    if _bool(row["locked"]):
        # 锁定智能体（每日一练）只允许改 bot_id / enabled，其余字段保护
        conn.execute("UPDATE agent_definitions SET bot_id = ?, enabled = ? WHERE agent_id = ?", ...)
    else:
        # 合并式部分更新：未携带字段保留原值，避免卡片上的"快速启停"清空其余配置
        ...
```

```python
def save_agent_subscriptions(db_path, agent_id, subscriptions):
    ...
    if topic in exclusive_topics:
        holder = conn.execute(
            "SELECT agent_id FROM agent_subscriptions WHERE topic = ? AND agent_id != ? LIMIT 1",
            (topic, agent_id),
        ).fetchone()
        if holder:
            raise ValueError(f"独占 topic {topic} 已被 {holder['agent_id']} 订阅")
```

```python
def delete_agent(db_path, agent_id):
    ...
    if _bool(row["system_builtin"]) or _bool(row["locked"]):
        raise ValueError("系统内置智能体不能删除")
```

这些校验把"独占 topic 只能一个订阅者""系统内置 Agent 不可删/改名""部分更新不清空其它字段"这几条业务规则前移到了 DB 写入路径，与 `bus.py` 的运行时防御（订阅冲突跳过而非崩溃）形成两道保险：**注册表写入时就应该拒绝非法状态，Bus 构建时再兜底一次防止历史脏数据搞垮整个管线**。

---

## 11. 每日一练：独占型 Workflow Agent 与工具调用

系统里唯一暴露"工具调用"语义的场景是每日一练——它包装的是 Coze **Workflow**（而非普通 Bot Chat），工作流运行到"问答节点"时会通过 Coze API 返回 `requires_action`，等待用户的下一条输入作为节点的"工具输出"提交回去。

[practice_agent.py](../backend/chainlit/lingxi/multi_agent/practice_agent.py)：

```python
class DailyPracticeAgent(BaseAgent):
    name = "Daily_Practice_Agent"
    display_name = "每日一练"
    bot_env_key = "COZE_BOT_ID"
    subscribed_topics = (TOPIC_PRACTICE_REQUEST, TOPIC_PRACTICE_ANSWER)

    async def act(self, msg: Message, cl_msg: "cl.Message") -> Dict[str, Any]:
        ...
        if msg.topic == TOPIC_PRACTICE_ANSWER:
            return await self._continue_workflow(
                coze, conversation_id, username, user_message, cl_msg,
                msg.payload.get("pending_action") or {},
            )
        return await coze.chat_stream(conversation_id, username, user_message, cl_msg)

    async def _continue_workflow(self, coze, conversation_id, username, user_message, cl_msg, pending_action):
        pending_chat_id = pending_action.get("chat_id")
        pending_tool_calls = pending_action.get("tool_calls", [])
        first_tool_call = pending_tool_calls[0] if pending_tool_calls else {}
        tool_call_type = first_tool_call.get("type", "unknown")
        tool_call_id = first_tool_call.get("id", "")

        if not pending_chat_id:
            return await coze.chat_stream(conversation_id, username, user_message, cl_msg)

        if tool_call_type == "reply_message":
            # Coze 流式 API 已知问题：reply_message 的 tool_call_id 始终为空，
            # submit_tool_outputs 会报 code=4000。直接在同一会话发送用户回答，
            # Coze 会自动续接未完成的工作流。
            return await coze.chat_stream(pending_conv_id, username, user_message, cl_msg)

        if tool_call_id:
            tool_outputs = [{"tool_call_id": tc.get("id", ""), "output": str(user_message)}
                            for tc in pending_tool_calls]
            return await coze.submit_tool_outputs_stream(
                conversation_id=pending_conv_id, chat_id=pending_chat_id,
                tool_outputs=tool_outputs, msg=cl_msg,
            )

        return await coze.chat_stream(pending_conv_id, username, user_message, cl_msg)
```

工具调用/挂起协议由 `app_impl.py` 里的 `CozeAPI.chat_stream()` 与 `submit_tool_outputs_stream()` 实现（详见 [第 12 节](#12-宿主接入与-chainlit--coze-的边界)），对上层暴露统一的返回结构：

```python
{"content": str | None, "requires_action": dict | None}
```

`requires_action` 非空即代表工作流挂起（携带 `chat_id` / `tool_calls` / `conversation_id`），由 `Pipeline._run_agent()` 统一写入 `practice_agent` 的 session 状态（`pending_tool_action`），下一条用户消息进来时 `handle()` 的"续接优先"分支会读出这个挂起态并分派回 `_continue_workflow`。

这里能提炼出的通用模式是：**"工具调用"不是这套多智能体框架自己定义的抽象，而是下游 LLM 供应商（Coze）工作流协议的直接暴露**——`BaseAgent.act()` 的返回值签名专门为它开了口子（`requires_action`），但只有 `DailyPracticeAgent` 真正使用；教学类 Agent 如果误产生 `requires_action`，Pipeline 会打警告并丢弃（第 9.3 节），因为教学 Bot 被设计为不挂载工作流。

---

## 12. 宿主接入：与 Chainlit / Coze 的边界

`app_impl.py`（4660+ 行）承担了三类职责：Chainlit 事件回调、Coze HTTP 客户端封装、Admin REST API。与多智能体架构相关的接入点：

### 12.1 依赖注入的具体绑定

```python
_pipeline: Optional[MultiAgentPipeline] = None

def _get_pipeline() -> MultiAgentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MultiAgentPipeline(
            AgentDeps(
                coze_factory=CozeAPI,
                get_token=get_valid_token,
                register_conversation=_register_agent_conversation,
                get_bot_id=get_agent_bot_id,
                log_usage=log_persona_usage,
            ),
            DB_PATH,
        )
    return _pipeline

def _invalidate_pipeline() -> None:
    global _pipeline
    _pipeline = None
    print("[MultiAgent] Pipeline registry cache invalidated")
```

`_get_pipeline()` 用懒加载单例模式；`_invalidate_pipeline()` 在所有 Admin 智能体/路由词表 CRUD 端点末尾调用，下一次消息进来时会用最新 DB 状态重建整条管线（重新 `load_registry` + 重新订阅）。

`get_agent_bot_id()` 是"专属 Bot 未配置时的回退"逻辑，让新建 Agent 即便还没绑定 Coze Bot ID 也能先用主 Bot 跑起来：

```python
def get_agent_bot_id(key: str) -> str:
    value = (config_storage.get(key) or "").strip()
    if value:
        return value
    return (config_storage.get("COZE_BOT_ID") or "").strip()
```

### 12.2 `on_message` 事件里的接入

```python
@cl.on_message
async def on_message(message: cl.Message):
    ...
    # ========== 多智能体管线 ==========
    msg = cl.Message(content="")
    await msg.send()
    try:
        thread_id = cl.context.session.thread_id
    except Exception:
        thread_id = None
    await _get_pipeline().handle(username, message.content, thread_id, msg)
```

`on_message` 先处理管理员专属命令（`/register`、`/users`、`/model` 等），未命中任何命令才交给多智能体管线——命令系统与智能体路由是两条独立的分派路径。

`on_chat_resume` 里还包含了 v2→v3 的**会话迁移逻辑**：把旧版本单一 `conversation_id` 迁移到 `Daily_Practice_Agent` 名下，把旧版 `pending_tool_action` 迁移进新的 `agent_state` 结构，保证老会话在架构升级后依然能正确续接练习工作流。

### 12.3 CozeAPI：LLM/工作流的实际执行者

`CozeAPI`（`app_impl.py:805` 起）封装了 Coze 的 `/v3/chat`、`/v3/chat/submit_tool_outputs` 等接口。核心方法签名：

```python
class CozeAPI:
    async def create_conversation(self) -> Optional[str]: ...

    async def chat_stream(self, conversation_id, user_id, query, msg: cl.Message, **kwargs):
        """Returns: {"content": str, "requires_action": dict|None}"""
        payload = {
            "bot_id": self.bot_id,
            "user_id": user_id,
            "additional_messages": [{"role": "user", "content": query, "content_type": "text"}],
            "stream": True,
            "auto_save_history": True,
            "custom_variables": custom_vars,  # 含 username / agent_name / task_topic / difficulty
        }
        ...

    async def submit_tool_outputs_stream(self, *, conversation_id, chat_id, tool_outputs, msg): ...
```

`custom_variables` 里的 `agent_name` / `task_topic` / `difficulty` 是 `RegisteredCozeAgent.act()`（见第 6 节引用的 `extra_vars`）注入的任务上下文变量，让同一个 Coze Bot 的 Prompt 模板能感知"我现在扮演谁、在回答什么类型的任务、难度如何"，Coze 容忍 Prompt 中未声明的额外变量。

---

## 13. 管理端 UI：卡片墙与分步注册向导

`AdminPage.tsx`（[frontend/src/lingxi/AdminPage.tsx](../frontend/src/lingxi/AdminPage.tsx)，2500+ 行）是智能体注册表的可视化管理入口，对应最近提交 `管理页智能体改为卡片墙与分步注册向导`。

### 13.1 智能体卡片墙 `AgentCard`

每个 Agent 渲染成一张信息卡，展示类型图标（Bot / Workflow）、启停开关、系统内置/锁定/独占徽标、订阅的 topic 及竞价可视化进度条：

```tsx
function AgentCard({ agent, topics, onEdit, onToggle, onDelete }: {...}) {
  const TypeIcon = agent.agent_type === 'coze_workflow' ? Workflow : Bot;
  const subscriptions = agent.subscriptions || [];
  return (
    <Card className={agent.enabled ? undefined : 'opacity-70'}>
      <CardHeader>
        ...
        <Switch checked={agent.enabled} onCheckedChange={(checked) => onToggle(agent, checked)} />
      </CardHeader>
      <CardContent>
        <Badge variant="secondary">{agent.agent_type === 'coze_workflow' ? 'Coze Workflow' : 'Coze Bot'}</Badge>
        <Badge variant="secondary">优先级 {agent.priority}</Badge>
        {subscriptions.map((sub) => (
          <div key={sub.topic}>
            <span>{topicName(sub.topic)}</span>
            <span>{formatBid(sub.base_bid)}
              {Number(sub.basic_bonus)    ? ` · 基础+${formatBid(sub.basic_bonus)}` : ''}
              {Number(sub.advanced_bonus) ? ` · 进阶+${formatBid(sub.advanced_bonus)}` : ''}
            </span>
            <div className="h-1.5 ..." style={{ width: `${Math.min(100, Math.round(sub.base_bid * 100))}%` }} />
          </div>
        ))}
        <Button disabled={agent.system_builtin || agent.locked} onClick={() => onDelete(agent)}>删除</Button>
      </CardContent>
    </Card>
  );
}
```

卡片上的启停开关直接调 `PUT /api/admin/agents/{id}`，走的是 `registry.update_agent()` 的"部分更新保留其余字段"路径（第 10.3 节）——这也是为什么后端要专门做合并式更新：卡片上的"快速启停"只应该改 `enabled`，不能因为 payload 缺字段就把 `display_name`、`bot_id` 清空。

### 13.2 分步注册向导 `AgentWizardState`

新建/编辑 Agent 用一个多步向导，而非一次性大表单：

```tsx
type AgentWizardState = {
  mode: 'create' | 'edit';
  step: number;
  agent: AgentDefinition;
  subscriptions: Record<string, AgentSubscription>;
  error: string;
};
```

向导步骤条 `WizardStepper` 对应文案（"填写基础信息 → 绑定 Coze Bot → 订阅任务 topic 并设定竞价 → 核对提交"），把注册表的复杂度（Agent 基本信息 / Bot 绑定 / 每个 topic 的三个竞价参数）拆解成线性任务流，而不是一个巨大表单——直接对应 UI 里的说明文案：

```
按步骤完成智能体接入：填写基础信息，绑定 Coze Bot，订阅任务 topic 并设定竞价，最后核对提交。
```

`submitWizard()` 最终会依次调用创建/更新 Agent 的 REST 端点，再调用 `PUT /api/admin/agents/{id}/subscriptions` 保存订阅与竞价，两步操作对应后端两张表（`agent_definitions`、`agent_subscriptions`）的分离写入。

### 13.3 对应的 Admin REST API

```python
@app.get("/api/admin/agents")     # list_agents(DB_PATH)
@app.post("/api/admin/agents")    # create_agent(DB_PATH, body) + _invalidate_pipeline()
@app.put("/api/admin/agents/{agent_id}")               # update_agent(...)
@app.delete("/api/admin/agents/{agent_id}")            # delete_agent(...)
@app.put("/api/admin/agents/{agent_id}/subscriptions") # save_agent_subscriptions(...)
@app.get("/api/admin/topics")     # get_topics_payload(DB_PATH)：路由词表读取
@app.put("/api/admin/topics")     # save_topics_payload(DB_PATH, body)：路由词表编辑
```

每个写操作都会：校验 → 写库 → `log_admin_activity()` 审计日志 → `_invalidate_pipeline()` 使运行时管线失效。`/api/admin/topics` 对应管理员编辑 Router 关键词表的入口——这意味着运营人员可以在不改代码的情况下调整"什么样的消息算作 off_topic""哪些词触发练习"等规则。

---

## 14. 跨 Agent 上下文与长期记忆

### 14.1 短期上下文：切换 Agent 时注入最近 2 轮

`context_policy` 字段（`on_switch_recent_2` / `none`）控制 Agent 切换时是否向 Coze 注入最近对话摘要，逻辑在 [teaching_agents.py](../backend/chainlit/lingxi/multi_agent/teaching_agents.py) 的 `RegisteredCozeAgent.act()`：

```python
context = msg.payload.get("context") or {}
last_agent = context.get("last_agent")
if self.context_policy == "on_switch_recent_2" and last_agent and last_agent != self.name:
    recent_turns = context.get("recent_turns") or []
    if recent_turns:
        recent_context = "\n".join(str(item) for item in recent_turns[-2:])
        extra_vars["context"] = recent_context
        extra_vars["system_context"] = recent_context
```

只有在**发生了 Agent 切换**（`last_agent != self.name`）时才注入，同一个 Agent 连续对答不需要额外上下文（因为 Coze 会话本身已经有完整历史）。这解决的问题是：用户从"新手小白"切到"计网专家"时，专家 Bot 的 Coze 会话是全新/独立的（每个 Agent 有自己的 `conversation_id`），如果不手动注入最近几轮，专家会"失忆"，感觉不到对话的连续性。

### 14.2 长期记忆：从错题表提炼薄弱知识点

[memory.py](../backend/chainlit/lingxi/multi_agent/memory.py) 是极简的 v1 实现，纯同步 sqlite3（调用方 `asyncio.to_thread` 包裹）：

```python
_DEFAULT_MEMORY = {"备考阶段": "未知", "基础水平": "未知", "薄弱知识点": []}

def fetch_user_memory(db_path: str, username: str) -> Dict[str, Any]:
    memory = dict(_DEFAULT_MEMORY)
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.execute(
            "SELECT question_text FROM mistake_details WHERE username = ? ORDER BY id DESC LIMIT 20",
            (username,),
        )
        weak_points = [...]  # 去重取最近 5 条错题摘要
        memory["薄弱知识点"] = weak_points
    except Exception:
        pass  # 表不存在/DB 不可读时静默回退默认记忆
    return memory
```

"备考阶段"和"基础水平"目前恒为"未知"，源码注释明确标注为"留作后续扩展点"——这是一个诚实暴露当前局限、而非用假数据填充的设计选择。`memory` 会被塞进每条 `Message.payload["memory"]`，理论上可供 Agent 在 `act()` 里读取用于个性化，但当前 `RegisteredCozeAgent`/`DailyPracticeAgent` 均未使用它（只有 `context`/`extra_vars` 被消费），同样是预留的扩展点。

---

## 15. 并发与稳定性：数据库锁竞争修复

最新提交 `解决数据库锁竞争问题`（`48c7255`）修复了一个具体问题：`log_usage`（写 SQLite 使用日志）之前是同步阻塞调用，在高并发/事件循环内直接执行会与其他 SQLite 写操作竞争锁。修复方式是把它挪到线程池执行，不阻塞事件循环：

```python
# 之前：
self.deps.log_usage(username, agent.display_name, thread_id)

# 之后：
await asyncio.to_thread(
    self.deps.log_usage,
    username,
    agent.display_name,
    thread_id,
)
```

这与 `_build_message()` 里 `fetch_user_memory` 早已采用的 `asyncio.to_thread` 模式一致——**整个 `multi_agent` 包的原则是：所有同步 SQLite 调用一律通过 `asyncio.to_thread` 移出事件循环**，避免阻塞其他并发会话的消息处理，也降低 SQLite 文件锁的持有时间。`registry.py` 内部的 `_connect()` 用 `contextmanager` 包装 `sqlite3.connect(..., timeout=30)`，确保连接及时关闭、锁及时释放。

---

## 16. 离线自测

[selftest.py](../backend/chainlit/lingxi/multi_agent/selftest.py) 是不依赖网络或 Chainlit 运行时的自测脚本，验证了本文档描述的绝大多数行为契约：

```bash
cd backend && python -m chainlit.lingxi.multi_agent.selftest
```

测试覆盖点（节选）：

```python
def test_router() -> None:
    check("启动器:每日一练", route_topic("开始每日一练"), TOPIC_PRACTICE_REQUEST)
    check("护栏:做题技巧提问", route_topic("选择题做题技巧有哪些"), TOPIC_CONCEPT_EXPLAIN)
    check("off:领域词不拒答", route_topic("网络游戏对带宽的要求高吗"), TOPIC_CONCEPT_EXPLAIN)
    ...

def test_selector() -> None:
    # basic 难度翻转 study.plan 给 Novice（0.75 > 0.70）
    sel = select(_bids_for(TOPIC_STUDY_PLAN, "basic"), _msg(TOPIC_STUDY_PLAN, difficulty="basic"), _priorities())
    check("basic翻转study.plan", sel.agent_name, "Novice_Learner")
    # 连续性只在分差足够小时生效
    sel = select(_bids_for(TOPIC_EXAM_ANALYZE), _msg(TOPIC_EXAM_ANALYZE, last_agent="Novice_Learner"), _priorities())
    check("连续性不强制:exam仍是Expert", sel.agent_name, "Network_Expert")

def test_registry_crud(db_path: str) -> None:
    # 独占 topic 已有订阅者时，其他智能体不得再订阅
    try:
        save_agent_subscriptions(db_path, "Test_Agent", [{"topic": "practice.request", "base_bid": 1.0}])
        check("独占topic订阅冲突被拒", "no-error", "ValueError")
    except ValueError:
        check("独占topic订阅冲突被拒", "ValueError", "ValueError")

def test_bus() -> None:
    bus = MessageBus()
    bus.subscribe(TOPIC_PRACTICE_REQUEST, _Stub("practice"))
    try:
        bus.subscribe(TOPIC_PRACTICE_REQUEST, _Stub("intruder"))
        check("独占topic重复订阅抛错", "no-error", "ValueError")
    except ValueError:
        check("独占topic重复订阅抛错", "ValueError", "ValueError")
```

自测用真实迁移（`run_migrations`）在临时目录建库，用种子数据跑注册表加载、Router 分类、Selector 竞价、Bus 独占约束、Normalizer 标准化五大板块，`main()` 汇总失败用例并以非零退出码收尾，可直接接入 CI。

---

## 17. 扩展指南：如何新增一个智能体

结合以上设计，新增一个教学型智能体（无需改代码）的标准流程：

1. **管理页 → 智能体 → 新建**，走分步向导：
   - 第一步：填写 `agent_id`（英文字母开头，字母数字下划线）、中文显示名、描述、优先级、Agent 类型（`coze_chat`）、跨 Agent 上下文策略。
   - 第二步：绑定 Coze Bot ID（留空则回退到全局 `COZE_BOT_ID`）。
   - 第三步：勾选订阅的任务 topic（`concept.explain` / `exam.analyze` / `question.solve` / `study.plan`），为每个 topic 设置 `base_bid`、`basic_bonus`、`advanced_bonus`。
   - 第四步：核对提交。
2. 提交后端依次调用 `POST /api/admin/agents`（写 `agent_definitions`）→ `PUT /api/admin/agents/{id}/subscriptions`（写 `agent_subscriptions`），每次都触发 `_invalidate_pipeline()`。
3. 下一条用户消息进来时，`_get_pipeline()` 用最新 DB 快照重建 `MultiAgentPipeline`：`load_registry` 读出新 Agent → `_build_agent` 构造 `RegisteredCozeAgent` 实例（因为 `agent_id != "Daily_Practice_Agent"`）→ 按 `subscribed_topics` 逐一 `bus.subscribe`。
4. 新 Agent 从此参与对应 topic 的竞价：收到任务消息时 `bid()` 按 `AgentConfig.subscriptions[topic]` 查出 `base_bid` 并按难度加成，`ResponseSelector` 与其他订阅者一起裁决。

如果需要新增一个**独占型工作流**（例如"模拟考试"这种有状态多轮工作流）：

1. 在管理页"路由词表"里新增一个 `route_topics` 记录，`is_exclusive = true`。
2. 新建 Agent，`agent_type = coze_workflow`，绑定承载该工作流的 Coze Bot，订阅刚建的独占 topic。
3. 若该工作流也有"问答节点挂起"语义，需要参考 `practice_agent.py` 的 `_continue_workflow` 模式实现一个新的 `BaseAgent` 子类（而非复用 `RegisteredCozeAgent`），因为挂起续接的分派逻辑（`reply_message` vs `tool_call_id`）目前是硬编码在 `DailyPracticeAgent` 里的专用逻辑，还没有抽象成通用能力。

---

## 18. 设计取舍与已知边界

- **竞价是纯规则打分，不是 LLM 自评**：好处是零延迟、零 token 成本、行为完全可预测（可单测）；代价是新增 topic/Agent 时需要人工设定 `base_bid`/`bonus` 数值，调参更依赖经验而非自动学习。
- **"工具调用"绑定在 Coze 工作流协议上**：`requires_action` 挂起/续接逻辑目前只服务于每日一练这一个独占 workflow，尚未抽象成通用的"多轮工作流 Agent 基类"。如果未来有第二个有状态工作流，`practice_agent.py` 里的分派逻辑（`reply_message` / `tool_call_id` 两种续接方式）需要提炼成可复用的 mixin 或工具函数。
- **长期记忆是预留但未真正接入 Prompt 的字段**：`fetch_user_memory` 已经从错题表提炼薄弱知识点并塞进 `Message.payload["memory"]`，但目前没有 Agent 实际读取使用（`RegisteredCozeAgent.act()` 只用了 `context`，没用 `memory`）。这是一个明确的、代码里承认了的待办，而非疏漏。
- **注册表变更是"整体重建"而非增量更新**：任何一次 CRUD 都会让下次消息触发完整的 `load_registry` + 重新建总线，对于当前的智能体规模（个位数）性能完全没问题，但如果未来注册表规模显著增长，可能需要考虑增量订阅更新。
- **纯模块 / 宿主适配层分离是全篇最值得复用的模式**：`message.py`/`bus.py`/`router.py`/`selector.py`/`normalizer.py`/`registry.py` 均可脱离 Chainlit 独立运行和测试，这个边界（"绝不 import app_impl，所有宿主能力走 `AgentDeps` 注入"）是保证系统可维护、可测试、可替换底层 IM 框架（万一未来要迁移出 Chainlit）的核心保障，新增代码时应严格遵守。
