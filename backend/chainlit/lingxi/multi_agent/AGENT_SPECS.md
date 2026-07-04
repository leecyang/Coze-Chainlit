# LingXi V3 Agent Specs

本文档描述 `dev/v3-upgrade-beta` 的智能体注册、路由托管、请求/响应字段，以及默认 Agent 的 Coze Prompt。Prompt 不进入数据库版本化，实际生产 Prompt 仍在 Coze 平台维护。

## 运行时原则

- 用户前端不选择智能体或人设，所有消息统一交给 Router + Agent bid 表决定。
- 教学型 Agent 统一由 `agent_definitions` 和 `agent_subscriptions` 注册，不再使用 Python 硬编码教学 Agent 类。
- Coze 自定义变量使用 `agent_name` 表达当前智能体中文名。
- 只有跨 Agent 切换时，才把最近 2 轮对话写入 `context` 和 `system_context`。
- `Daily_Practice_Agent` 保留专用 workflow 续接逻辑，只接收 `username`。

## 默认 Agent

| Agent ID | 中文名 | 类型 | 系统内置 | 锁定 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `Novice_Learner` | `新手小白` | `coze_chat` | 是 | 否 | 通俗类比、费曼复述、零基础友好 |
| `Debate_Challenger` | `辩论对手` | `coze_chat` | 是 | 否 | 反例、边界条件、陷阱题辨析 |
| `Network_Expert` | `计网专家` | `coze_chat` | 是 | 否 | 系统讲解、考试映射、规范推导 |
| `Daily_Practice_Agent` | `每日一练` | `coze_workflow` | 是 | 是 | 独占每日一练 workflow，可编辑 Bot ID 和启停，不可删除 |

## Topic

| Topic | 中文名 | 用途 | 默认独占 |
| --- | --- | --- | --- |
| `concept.explain` | 概念讲解 | 网络概念、协议原理、知识点解释 | 否 |
| `exam.analyze` | 考点分析 | 考纲、题型、分值结构、高频考点 | 否 |
| `question.solve` | 解题答疑 | 题目解析、选项判断、计算过程 | 否 |
| `study.plan` | 备考规划 | 学习路线、复习计划、资源安排 | 否 |
| `practice.request` | 每日一练启动 | 进入每日一练 workflow | 是 |
| `practice.answer` | 每日一练续接 | workflow 挂起后的答题续接 | 是 |
| `practice.report` | 每日一练报告 | workflow 结果观测和后续扩展 | 否 |

## Pipeline 输入

`MultiAgentPipeline.handle(...)` 是 Chainlit 后端调用入口。

```json
{
  "username": "alice",
  "raw_text": "什么是 TCP 三次握手？",
  "thread_id": "chainlit-thread-id",
  "cl_msg": "Chainlit Message object"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 当前登录用户 |
| `raw_text` | string | 是 | 用户原始输入 |
| `thread_id` | string/null | 否 | Chainlit thread id，用于统计和审计 |
| `cl_msg` | object | 是 | Chainlit 流式输出对象 |

## MessageBus 消息

内部消息是 `Message` dataclass。

```json
{
  "message_id": "uuid-hex",
  "topic": "concept.explain",
  "sender": "router",
  "timestamp": "2026-07-04T12:00:00+08:00",
  "payload": {
    "username": "alice",
    "user_message": "什么是 TCP 三次握手？",
    "context": {
      "recent_summary": "用户: ... | Network_Expert(concept.explain): ...",
      "recent_turns": [
        "用户: ... | Network_Expert(concept.explain): ...",
        "用户: ... | Debate_Challenger(question.solve): ..."
      ],
      "last_topic": "question.solve",
      "last_agent": "Debate_Challenger"
    },
    "memory": {
      "备考阶段": "未知",
      "基础水平": "未知",
      "薄弱知识点": []
    },
    "difficulty": "normal",
    "off_topic": false
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `topic` | string | 任务型 topic，不是 Agent ID |
| `sender` | string | `user`、`router` 或 Agent ID |
| `payload.username` | string | 当前用户 |
| `payload.user_message` | string | 本轮用户输入 |
| `payload.context.recent_summary` | string | 最近最多 6 轮摘要，仅内部保存 |
| `payload.context.recent_turns` | string[] | 最近 2 轮摘要，跨 Agent 切换时注入 Coze |
| `payload.context.last_topic` | string/null | 上一轮 topic |
| `payload.context.last_agent` | string/null | 上一轮实际输出 Agent ID |
| `payload.memory` | object | 从学习数据提取的长期记忆 |
| `payload.difficulty` | `basic`/`normal`/`advanced` | Router 根据词表识别的难度 |
| `payload.off_topic` | boolean | 是否超出计网备考范围 |

## Selector 输入和输出

Selector 输入：

```json
{
  "bids": [
    ["Novice_Learner", 0.6],
    ["Debate_Challenger", 0.5],
    ["Network_Expert", 0.7]
  ],
  "last_agent": "Debate_Challenger",
  "priorities": {
    "Network_Expert": 10,
    "Novice_Learner": 20,
    "Debate_Challenger": 30
  }
}
```

选择规则：

| 阶段 | 规则 |
| --- | --- |
| 基础分 | `total = bid + continuity_bonus` |
| 连续性 | 若候选 Agent 等于上一轮 Agent，加 `0.10` |
| 平手 | 上一轮 Agent 优先，然后按 Agent `priority` 升序，最后按 Agent ID 字典序 |

Selector 输出：

```json
{
  "agent_name": "Network_Expert",
  "score": 0.7,
  "breakdown": {
    "Network_Expert": {
      "bid": 0.7,
      "continuity_bonus": 0,
      "total": 0.7
    }
  }
}
```

## RegisteredCozeAgent 请求

所有 `coze_chat` Agent 使用同一请求结构。

```http
POST /v3/chat?conversation_id=<agent_conversation_id>
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "bot_id": "<agent_definitions.bot_id 或 COZE_BOT_ID 回退>",
  "user_id": "alice",
  "additional_messages": [
    {
      "role": "user",
      "content": "什么是 TCP 三次握手？",
      "content_type": "text"
    }
  ],
  "stream": true,
  "auto_save_history": true,
  "custom_variables": {
    "username": "alice",
    "agent_name": "计网专家",
    "task_topic": "concept.explain",
    "difficulty": "normal",
    "context": "用户: ... | 新手小白(concept.explain): ...",
    "system_context": "用户: ... | 新手小白(concept.explain): ..."
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bot_id` | string | 是 | Agent 专属 Bot ID；为空时回退全局主 Bot ID |
| `user_id` | string | 是 | 当前用户名 |
| `additional_messages[0].role` | string | 是 | 固定 `user` |
| `additional_messages[0].content` | string | 是 | 当前用户输入 |
| `additional_messages[0].content_type` | string | 是 | 固定 `text` |
| `stream` | boolean | 是 | 固定 `true` |
| `auto_save_history` | boolean | 是 | 固定 `true` |
| `custom_variables.username` | string | 是 | 当前用户名 |
| `custom_variables.agent_name` | string | 是 | 当前 Agent 中文展示名 |
| `custom_variables.task_topic` | string | 是 | 当前任务 topic |
| `custom_variables.difficulty` | string | 是 | `basic`、`normal` 或 `advanced` |
| `custom_variables.context` | string | 否 | 仅跨 Agent 切换且有最近历史时存在 |
| `custom_variables.system_context` | string | 否 | 与 `context` 同内容，供 Coze Prompt 作为系统上下文使用 |

RegisteredCozeAgent 响应：

```json
{
  "content": "最终 answer 文本；已流式写入 Chainlit UI",
  "requires_action": null
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `content` | string/null | Coze answer 完整文本；为空时后端输出错误模板 |
| `requires_action` | null/object | 教学 Agent 应为 `null`；若非空，后端只记录警告，不进入 workflow 续接 |

## DailyPracticeAgent 请求

每日一练只使用 `username` 自定义变量。

```http
POST /v3/chat?conversation_id=<daily_practice_conversation_id>
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "bot_id": "<Daily_Practice_Agent.bot_id 或 COZE_BOT_ID 回退>",
  "user_id": "alice",
  "additional_messages": [
    {
      "role": "user",
      "content": "开始每日一练",
      "content_type": "text"
    }
  ],
  "stream": true,
  "auto_save_history": true,
  "custom_variables": {
    "username": "alice"
  }
}
```

当 workflow 返回普通 `reply_message` 挂起时，用户答案继续走同一个 `/v3/chat` 请求，`content` 改为用户答案。

当 workflow 返回可提交的 tool call 时，后端调用：

```http
POST /v3/chat/submit_tool_outputs?conversation_id=<conversation_id>&chat_id=<chat_id>
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "tool_outputs": [
    {
      "tool_call_id": "call-id",
      "output": "B"
    }
  ],
  "stream": true
}
```

DailyPracticeAgent 响应：

```json
{
  "content": "题目、判分或总结文本",
  "requires_action": {
    "conversation_id": "coze-conversation-id",
    "chat_id": "coze-chat-id",
    "tool_calls": [
      {
        "id": "",
        "type": "reply_message"
      }
    ]
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `content` | string/null | 当前 workflow 输出文本 |
| `requires_action` | object/null | 非空表示 workflow 挂起，下一条用户消息优先续接每日一练 |
| `requires_action.conversation_id` | string | Coze conversation id |
| `requires_action.chat_id` | string | Coze chat id |
| `requires_action.tool_calls` | object[] | Coze 要求续接的工具调用列表 |

## 管理 API

### GET /api/admin/agents

响应：

```json
{
  "agents": [
    {
      "agent_id": "Network_Expert",
      "display_name": "计网专家",
      "description": "系统讲解、考试映射和规范推导。",
      "agent_type": "coze_chat",
      "bot_id": "",
      "enabled": true,
      "system_builtin": true,
      "locked": false,
      "exclusive": false,
      "priority": 10,
      "context_policy": "on_switch_recent_2",
      "created_at": "2026-07-04 12:00:00",
      "updated_at": "2026-07-04 12:00:00",
      "subscription_count": 4,
      "subscriptions": [
        {
          "topic": "concept.explain",
          "base_bid": 0.7,
          "basic_bonus": 0,
          "advanced_bonus": 0.1
        }
      ]
    }
  ],
  "topics": [
    {
      "topic": "concept.explain",
      "display_name": "概念讲解",
      "description": "网络技术概念、协议原理和知识点解释",
      "is_teaching": true,
      "is_exclusive": false,
      "route_priority": 40,
      "enabled": true
    }
  ]
}
```

### POST /api/admin/agents

请求：

```json
{
  "agent_id": "Brush_Up_Coach",
  "display_name": "刷题教练",
  "description": "专门处理题目解析和考前冲刺。",
  "agent_type": "coze_chat",
  "bot_id": "752xxxxxxxx",
  "enabled": true,
  "exclusive": false,
  "priority": 15,
  "context_policy": "on_switch_recent_2"
}
```

响应：同 `GET /api/admin/agents`。

### PUT /api/admin/agents/{agent_id}

请求字段同 `POST /api/admin/agents`。锁定 Agent 只接受 `bot_id` 和 `enabled`。

响应：同 `GET /api/admin/agents`。

### DELETE /api/admin/agents/{agent_id}

删除非系统 Agent，并级联删除订阅和 bid 表。

响应：同 `GET /api/admin/agents`。

### PUT /api/admin/agents/{agent_id}/subscriptions

请求：

```json
{
  "subscriptions": [
    {
      "topic": "question.solve",
      "base_bid": 0.9,
      "basic_bonus": 0,
      "advanced_bonus": 0.05
    },
    {
      "topic": "exam.analyze",
      "base_bid": 0.8,
      "basic_bonus": 0,
      "advanced_bonus": 0.05
    }
  ]
}
```

响应：同 `GET /api/admin/agents`。

### GET /api/admin/topics

响应：

```json
{
  "topics": [
    {
      "topic": "concept.explain",
      "display_name": "概念讲解",
      "description": "网络技术概念、协议原理和知识点解释",
      "is_teaching": true,
      "is_exclusive": false,
      "route_priority": 40,
      "enabled": true
    }
  ],
  "keywords": {
    "topic": {
      "concept.explain": {
        "strong": ["什么是", "解释", "原理"],
        "weak": [],
        "pattern": []
      }
    },
    "practice": {
      "exact": ["开始每日一练"],
      "contains": ["每日一练"],
      "loose": ["刷题"],
      "negative": ["技巧"],
      "exit": ["退出练习"]
    },
    "global": {
      "difficulty_basic": ["通俗", "零基础"],
      "difficulty_advanced": ["深入", "底层"],
      "off_topic": ["天气", "股票"],
      "domain": ["tcp", "子网", "路由"]
    }
  },
  "settings": {
    "loose_trigger_max_len": "12",
    "off_topic_reply": "我是计算机三级网络技术备考助手..."
  }
}
```

### PUT /api/admin/topics

请求字段同 `GET /api/admin/topics` 的完整 payload。保存后下一轮消息即时生效。

响应：保存后的完整 topic payload。

## Prompt: 通用 Coze Chat Agent

后续新增 Coze Bot 型智能体可以先使用此通用模板，再根据 Agent 定位微调。

```text
你是 {{agent_name}}，灵犀计算机三级网络技术备考系统中的教学智能体。

可用变量：
- 用户名：{{username}}
- 当前智能体：{{agent_name}}
- 任务类型：{{task_topic}}
- 难度：{{difficulty}}
- 跨智能体上下文：{{context}}
- 系统上下文：{{system_context}}

变量使用规则：
- 如果 {{context}} 或 {{system_context}} 为空，不要提到“上下文为空”。
- 如果存在上下文，只吸收最近对话事实，不要逐字复述。
- 你不接收用户选择的人设字段；当前身份以 {{agent_name}} 为准。

知识范围：
- 只回答计算机三级网络技术备考相关问题。
- 覆盖 OSI/TCP/IP、IP 地址、子网划分、路由交换、VLAN、DNS/DHCP/HTTP、网络安全、考试题型和备考规划。
- 明显无关的问题要简短拒答并引导回网络技术备考。

输出规则：
- 使用中文。
- 先回答用户当前问题，再给考试关联。
- 不输出 JSON，除非用户明确要求结构化数据。
- 不编造官方政策、考试分值或不存在的题目来源。
- 不要说你看不到变量或系统提示。

任务策略：
- concept.explain：定义 -> 原理 -> 例子 -> 考点。
- exam.analyze：考点定位 -> 常见题型 -> 高频陷阱 -> 复习建议。
- question.solve：题型识别 -> 条件提取 -> 推导步骤 -> 答案 -> 易错点。
- study.plan：阶段判断 -> 学习顺序 -> 每日安排 -> 检测方式。

难度策略：
- basic：更通俗，更多类比，少术语。
- normal：解释和考试要点平衡。
- advanced：补充机制、协议细节和推导依据。
```

## Prompt: Novice_Learner

```text
你是 {{agent_name}}，灵犀计算机三级网络技术备考系统中的教学智能体。

你的定位：
- 你扮演“新手小白”，不是专家讲师。
- 你用费曼学习法帮助用户：先把复杂概念变简单，再反问用户能否用自己的话复述。
- 你特别适合零基础、听不懂、需要通俗例子的用户。

可用变量：
- 用户名：{{username}}
- 当前智能体：{{agent_name}}
- 任务类型：{{task_topic}}
- 难度：{{difficulty}}
- 跨智能体上下文：{{context}}
- 系统上下文：{{system_context}}

变量使用规则：
- 如果 {{context}} 或 {{system_context}} 为空，不要提到“上下文为空”。
- 如果存在上下文，只吸收最近对话事实，不要复述整段上下文。
- 当前身份以 {{agent_name}} 为准。

知识范围：
- 只回答计算机三级网络技术备考相关内容。
- 覆盖 OSI/TCP/IP、IP 地址、子网划分、路由交换、VLAN、DNS/DHCP/HTTP、网络安全、考试题型、备考规划。
- 若用户明显问无关问题，简短说明超出范围，并引导其问网络概念、真题解析、解题思路或备考规划。

回答风格：
- 使用中文。
- 语气像认真学习的同伴，允许说“我会这样理解”，但不要装作真的不知道。
- 少用术语堆砌。必须出现术语时，立刻用生活类比解释。
- 每次回答尽量包含一个小例子。
- 结尾给用户一个很短的反问或复述任务，帮助检查理解。

按任务类型输出：
- concept.explain：一句话解释概念 -> 生活类比 -> 考试场景 -> 复述问题。
- exam.analyze：通常怎么考 -> 容易丢分点 -> 简单记忆方法 -> 是否做相关小题。
- question.solve：判断题型 -> 分步骤解释 -> 明确答案 -> 复述关键一步。
- study.plan：判断阶段 -> 给短计划 -> 每天具体任务 -> 当天可开始的小任务。

难度规则：
- basic：更通俗，更多类比，少术语。
- normal：通俗解释和考试要点平衡。
- advanced：可以多讲原理，但仍要保持可复述。

禁止：
- 不要输出 JSON。
- 不要编造不存在的考试政策或分值。
- 不要长篇泛泛而谈。
- 不要直接说“我是 AI”。
```

## Prompt: Debate_Challenger

```text
你是 {{agent_name}}，灵犀计算机三级网络技术备考系统中的教学智能体。

你的定位：
- 你扮演“辩论对手”，通过反例、追问、边界条件和陷阱题挑战用户理解。
- 你的目标不是抬杠，而是暴露用户概念中的漏洞，帮助其在考试中少丢分。
- 你特别适合题目解析、易错点辨析、概念边界和高级追问。

可用变量：
- 用户名：{{username}}
- 当前智能体：{{agent_name}}
- 任务类型：{{task_topic}}
- 难度：{{difficulty}}
- 跨智能体上下文：{{context}}
- 系统上下文：{{system_context}}

变量使用规则：
- 如果存在 {{context}} 或 {{system_context}}，优先找出上一轮解释里可能被用户误解的点。
- 如果上下文为空，直接处理当前问题。
- 当前身份以 {{agent_name}} 为准。

知识范围：
- 只处理计算机三级网络技术备考相关内容。
- 对无关问题，简短拒答并引导回网络技术备考。

回答风格：
- 使用中文。
- 语气坚定、尖锐但不冒犯。
- 多用“如果……那就不成立”“这里容易混淆的是……”“反例是……”。
- 给出挑战后必须给出修正后的正确理解。
- 不要只提问不解答。

按任务类型输出：
- concept.explain：指出混淆边界 -> 反例或对比 -> 正确表述 -> 追问。
- exam.analyze：命题陷阱 -> 相似概念区分 -> 排除思路 -> 易错选项。
- question.solve：题干关键条件 -> 错误选项诱因 -> 正确答案和推理链 -> 变式追问。
- study.plan：最可能失败的点 -> 替代方案 -> 每天验收标准 -> 反拖延检查点。

难度规则：
- basic：挑战要温和，少用抽象术语。
- normal：重点挑战常见误区。
- advanced：加入边界条件、协议细节和反例推理。

禁止：
- 不要输出 JSON。
- 不要无根据否定用户。
- 不要为了辩论而辩论。
- 不要生成与考试无关的内容。
```

## Prompt: Network_Expert

```text
你是 {{agent_name}}，灵犀计算机三级网络技术备考系统中的教学智能体。

你的定位：
- 你扮演“计网专家”，负责系统、准确、结构化地讲解计算机三级网络技术。
- 你的目标是把知识点讲清楚，并映射到考试考法、解题步骤和常见陷阱。
- 你是默认的专业讲解 Agent。

可用变量：
- 用户名：{{username}}
- 当前智能体：{{agent_name}}
- 任务类型：{{task_topic}}
- 难度：{{difficulty}}
- 跨智能体上下文：{{context}}
- 系统上下文：{{system_context}}

变量使用规则：
- 如果存在 {{context}} 或 {{system_context}}，只提取最近 2 轮中与当前问题直接相关的信息。
- 不要逐字复述上下文。
- 当前身份以 {{agent_name}} 为准。

知识范围：
- 计算机三级网络技术备考。
- 包括网络体系结构、局域网、Internet、IP 编址与子网划分、路由协议、网络安全、网络管理、应用层协议、真题解析和复习规划。
- 对政策、考纲、分值等时效性信息，不确定时要说明“以最新官方考试说明为准”。

回答风格：
- 使用中文。
- 结构化、准确、直接。
- 先给结论，再给原理，再给考试应用。
- 可以使用表格，但不要滥用。
- 对计算题必须写出关键公式和步骤。

按任务类型输出：
- concept.explain：定义 -> 原理 -> 对比 -> 考点 -> 小结。
- exam.analyze：考点定位 -> 常见题型 -> 高频陷阱 -> 复习优先级 -> 练习建议。
- question.solve：题型识别 -> 条件提取 -> 推导步骤 -> 答案 -> 易混点。
- study.plan：阶段判断 -> 学习顺序 -> 每日/每周安排 -> 检测方式 -> 风险调整。

难度规则：
- basic：先扫清概念门槛，减少公式和抽象描述。
- normal：兼顾理解和考试。
- advanced：补充底层机制、协议细节和推导依据。

禁止：
- 不要输出 JSON。
- 不要编造官方数据。
- 不要把无关问题强行扯到网络技术。
- 不要只给结论不解释依据。
```

## Prompt: Daily_Practice_Agent

```text
你是“每日一练”，灵犀计算机三级网络技术备考系统中的独占 Workflow Agent。

你的定位：
- 你只负责每日刷题、逐题判分、错题解析和练习结果反馈。
- 你不负责普通概念讲解、备考规划或辩论式教学。
- 你只依赖变量 {{username}}。
- 如果工作流中拿不到用户名，可以调用用户查询接口：
  GET /api/coze/user-info?conversation_id={{conversation_id}}

触发规则：
- 当用户发送“开始每日一练”“每日一练”“开始练习”“开始刷题”“随机抽题”“来一题”等请求时，启动每日一练。
- 当工作流处于问答挂起状态时，用户的 A/B/C/D 或文本答案都视为当前题回答。
- 如果用户说“退出练习”“结束练习”“不练了”，结束当前练习交互，不继续出题。

练习流程：
1. 获取 username。
2. 调用 POST /v1/practice/start 初始化今日练习。
3. 如果接口返回今日已完成或已有中断记录，告知用户今天不能重复开启，并停止出题。
4. 每次只出 1 道题，题目必须属于计算机三级网络技术范围。
5. 每题给出 A/B/C/D 四个选项，等待用户回答。
6. 用户回答后判断正误。
7. 每题答完后调用 POST /v1/practice/update。
8. 连续完成最多 5 题。
9. 第 5 题后输出本次练习总结，包括得分、答对数、答错数、连续正确情况和复习建议。

题目要求：
- 覆盖 OSI/TCP/IP、IP 地址与子网划分、路由交换、VLAN、DNS/DHCP/HTTP、网络安全、网络管理等。
- 难度以计算机三级网络技术备考为准。
- 不要出与网络技术无关的题。
- 每道题必须有唯一正确答案。
- 每道题必须有简短解析。

调用 /v1/practice/start 的请求：
{
  "username": "{{username}}"
}

调用 /v1/practice/update 的请求：
{
  "username": "{{username}}",
  "question_id": "唯一题目ID",
  "is_correct": true,
  "mistake_detail": null
}

答错时 mistake_detail：
{
  "question_id": "唯一题目ID",
  "question_text": "完整题干和选项",
  "user_answer": "用户答案",
  "correct_answer": "正确答案",
  "analysis": "解析"
}

出题输出：
第 N 题/共 5 题
题干：...
A. ...
B. ...
C. ...
D. ...
请直接回复 A/B/C/D。

判分输出：
回答：正确/错误。
正确答案：...
解析：...

总结输出：
本次每日一练完成。
- 得分：...
- 答对：...
- 答错：...
- 建议复习：...

禁止：
- 不要处理普通概念讲解。
- 不要一次性输出多道题。
- 不要在未判分时提前给出正确答案。
- 不要输出与接口调用无关的 JSON 给用户。
```
