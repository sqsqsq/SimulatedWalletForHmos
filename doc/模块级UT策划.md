## AI 驱动的模块级端到端 UT 自动生成系统 — 计划书

### 一、问题定义与目标

| 维度 | 描述 |
|------|------|
| **痛点** | 鸿蒙应用功能复杂（多机型/多场景/多入口），人工自测遗漏率高，手写 UT 成本极高 |
| **目标** | 通过 AI 自动生成模块级端到端 UT，覆盖关键业务流程，兼具拦截能力与执行效率 |
| **核心理念** | 用 DAG（有向无环图）描述业务流程 → AI 理解流程 + 代码 → 自动生成含打桩的 UT → 运行验证 → 自动修正 |

---

### 二、整体架构（四层设计）

```
┌─────────────────────────────────────────────────────────┐
│                    Layer 4: Skill / MCP                  │
│   (Cursor Skill 或 MCP Server，对外暴露统一接口)         │
├─────────────────────────────────────────────────────────┤
│                    Layer 3: UT 生成引擎                   │
│   DAG解析 → 代码分析 → 打桩识别 → UT代码生成 → 修正循环  │
├─────────────────────────────────────────────────────────┤
│                    Layer 2: DAG 构建引擎                  │
│   静态分析 + 运行日志 → DAG 文件生成/校准                 │
├─────────────────────────────────────────────────────────┤
│                    Layer 1: 基础设施                      │
│   鸿蒙测试框架(Hypium) + 打桩库 + DAG Schema定义          │
└─────────────────────────────────────────────────────────┘
```

---

### 三、分阶段实施计划

#### 第一阶段：基础设施搭建（约 2-3 周）

**1.1 定义 DAG Schema 规范**

这是整个系统的核心数据结构。建议使用 JSON/YAML 格式：

```json
{
  "flow_id": "card_opening_flow",
  "flow_name": "开卡流程",
  "entry_point": {
    "module": "entry",
    "class": "CardOpenAbility",
    "method": "onCardOpenClicked"
  },
  "nodes": [
    {
      "id": "n1",
      "type": "code_execution",
      "description": "用户点击开卡入口",
      "source": { "file": "pages/CardPage.ets", "function": "onCardOpenClicked" },
      "next": ["n2"]
    },
    {
      "id": "n2",
      "type": "async_call",
      "description": "请求后台获取开卡参数",
      "source": { "file": "services/CardService.ets", "function": "fetchCardParams" },
      "stub_strategy": "mock_response",
      "mock_data_ref": "card_params_success.json",
      "next": ["n3"]
    },
    {
      "id": "n3",
      "type": "user_intervention",
      "description": "等待用户输入短信验证码",
      "intervention": {
        "ui_component": "SmsVerifyDialog",
        "input_field": "smsCodeInput",
        "simulated_value": "123456"
      },
      "next": ["n4"]
    },
    {
      "id": "n4",
      "type": "background_task",
      "description": "后台提交验证码并完成开卡",
      "source": { "file": "services/CardService.ets", "function": "submitVerification" },
      "stub_strategy": "mock_response",
      "next": ["n5"]
    },
    {
      "id": "n5",
      "type": "assertion",
      "description": "验证开卡成功状态",
      "assertions": [
        { "type": "state_check", "target": "CardViewModel.cardStatus", "expected": "ACTIVATED" }
      ]
    }
  ],
  "node_types_enum": ["code_execution", "async_call", "user_intervention", "background_task", "ui_navigation", "assertion", "conditional_branch"]
}
```

**关键节点类型定义：**

| 节点类型 | 说明 | AI 处理策略 |
|----------|------|-------------|
| `code_execution` | 普通代码执行 | 直接调用 |
| `async_call` | 异步调用（网络/IO） | 需要打桩 mock |
| `user_intervention` | 需用户操作 | 模拟 UI 输入 |
| `background_task` | 后台任务 | 模拟回调 |
| `ui_navigation` | 页面跳转 | 模拟路由 |
| `conditional_branch` | 条件分支 | 生成多条路径用例 |
| `assertion` | 断言检查点 | 生成 expect 语句 |

**1.2 搭建鸿蒙测试基座**

- 在工程中配置 `ohosTest` 模块，引入 `@ohos/hypium` 测试框架
- 建立打桩基础库（对 HarmonyOS 系统 API、网络请求、UI 交互的通用 mock 工具）
- 建立 UT 模板体系（模板文件供 AI 填充）

**1.3 交付物清单**

- `dag-schema.json` — DAG 规范定义文件
- `test-infra/` — 测试基础设施目录（mock 工具库、UT 模板）
- `docs/dag-spec.md` — DAG 规范文档

---

#### 第二阶段：DAG 构建引擎（约 3-4 周）

这是将"代码 + 运行日志"转化为 DAG 的引擎。

**2.1 静态分析模块**

```
源代码 (.ets/.ts)
    │
    ▼
┌─────────────────┐
│  AST 解析器      │  ← TypeScript Compiler API / SWC
│  (提取调用关系)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  调用图构建器     │  ← 从入口函数开始，递归解析调用链
│  (Call Graph)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  节点类型标注器   │  ← 规则引擎 + AI 辅助
│  (识别异步/UI等) │
└────────┬────────┘
         │
         ▼
    初版 DAG
```

**节点类型识别规则（规则引擎部分）：**

| 识别目标 | 识别方式 |
|----------|----------|
| 异步调用 | `async/await`、`Promise`、`http.createHttp()` 等模式 |
| 用户交互 | UI 组件的 `onClick`、`onChange`、`Dialog`、`TextInput` 等 |
| 后台任务 | `backgroundTaskManager`、`ServiceExtAbility`、`WorkScheduler` |
| 页面跳转 | `router.pushUrl`、`Navigation`、`NavDestination` |
| 条件分支 | `if/else`、`switch` 中影响流程走向的关键判断 |

**2.2 运行日志增强模块**

静态分析无法覆盖所有动态行为（如回调顺序、实际执行路径），因此需要运行日志来**校准**：

- **日志埋点方案**：在关键节点增加结构化日志（JSON 格式），记录 `{timestamp, module, function, event_type, params}`
- **日志解析器**：将运行日志解析为实际执行路径
- **DAG 校准器**：对比静态 DAG 与运行日志路径，修正节点顺序、补充遗漏节点

**2.3 AI 辅助精化**

对于规则引擎难以准确识别的场景，调用大模型进行判断：
- 输入：函数代码片段 + 上下文
- 输出：节点类型判定 + 置信度
- 低置信度节点标记为"需人工确认"

**2.4 交付物清单**

- `dag-builder/` — DAG 构建引擎
  - `static-analyzer/` — 静态分析模块
  - `log-parser/` — 日志解析模块
  - `dag-calibrator/` — DAG 校准模块
- CLI 工具：`dag-build --entry CardOpenFlow --log ./logs/card_open.log`

---

#### 第三阶段：UT 生成引擎（约 4-5 周，核心阶段）

**3.1 整体生成流程**

```
DAG 文件 + 工程源码
        │
        ▼
┌───────────────────┐
│  1. DAG 解析       │  读取 DAG，构建节点执行序列
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  2. 代码关联       │  将 DAG 节点映射到具体源码函数/类
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  3. 打桩策略决策   │  识别需 mock 的依赖，决定打桩方式
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  4. UT 代码生成    │  调用大模型，按模板生成完整 UT
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  5. 编译运行验证   │  执行 UT，收集结果
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  6. 错误修正循环   │  对比 DAG 预期 vs 实际结果，修正 UT
└────────┘──────────┘
     ↑        │
     └────────┘  (最多 N 轮)
```

**3.2 打桩策略矩阵**

| 场景 | 打桩方式 | 示例 |
|------|----------|------|
| 网络请求 | 替换 HTTP Client 为 Mock | `mockHttp.expect('/api/card').respond(200, mockData)` |
| 系统 API | 替换系统模块 | `mock(@ohos.telephonySms).onReceive(mockSmsCode)` |
| 用户 UI 输入 | 模拟组件事件 | `simulateInput(smsCodeInput, '123456')` |
| 定时器/延迟 | 使用 fake timer | `fakeTimers.advance(5000)` |
| 后台服务 | 直接调用回调 | `cardService.onBackgroundResult(mockResult)` |
| 页面跳转 | Mock Router | `mockRouter.verify('/pages/VerifyPage')` |
| 条件分支 | 控制输入变量 | 生成多条用例覆盖每个分支 |

**3.3 Prompt Engineering 策略**

给大模型的 Prompt 需要包含：

```
你是一个鸿蒙应用 UT 生成专家。

## 输入信息
1. DAG 文件: {dag_content}
2. 当前节点: {node_info}
3. 节点对应源码: {source_code}
4. 节点依赖的上下文代码: {context_code}
5. 已有的 mock 工具库 API: {mock_api_docs}
6. 测试框架: @ohos/hypium

## 任务
根据 DAG 流程描述和源码，为当前流程生成完整的端到端测试用例。

## 要求
1. 对 type=async_call 的节点，生成对应的 mock 打桩代码
2. 对 type=user_intervention 的节点，使用 simulated_value 模拟用户输入
3. 对 type=assertion 的节点，生成对应的 expect 断言
4. 确保按 DAG 节点顺序编排测试步骤
5. 生成的代码必须可编译通过
```

**3.4 自动修正循环**

```
运行 UT
  │
  ├─ 通过 → 完成 ✓
  │
  └─ 失败 → 收集错误信息
              │
              ├─ 编译错误 → 将错误信息 + 源码反馈给 AI 修正
              ├─ 运行时错误 → 分析堆栈，定位打桩缺失
              └─ 断言失败 → 对比 DAG 预期，调整断言或 mock 数据
              │
              └─ 重新生成 → 再次运行（最多 5 轮）
```

---

#### 第四阶段：Skill & MCP 封装（约 2-3 周）

**4.1 Cursor Skill 设计**

```
skills/
└── module-ut-generator/
    ├── SKILL.md              # Skill 入口描述文件
    ├── templates/
    │   ├── dag-schema.json   # DAG 规范模板
    │   ├── ut-template.ets   # UT 代码模板
    │   └── mock-template.ets # Mock 模板
    ├── prompts/
    │   ├── dag-generate.md   # DAG 生成 prompt
    │   ├── ut-generate.md    # UT 生成 prompt
    │   └── ut-fix.md         # UT 修正 prompt
    └── examples/
        ├── card-open-flow.dag.json
        └── card-open-flow.test.ets
```

**SKILL.md 核心触发词**：
- "生成模块级 UT"
- "根据 DAG 生成测试"
- "自动化端到端测试"

**Skill 工作流**：

```
用户触发 Skill
    │
    ▼
Step 1: 读取指定的 DAG 文件（或根据入口函数自动生成）
    │
    ▼
Step 2: 分析 DAG 中每个节点对应的源码
    │
    ▼
Step 3: 识别需打桩的节点，选择打桩策略
    │
    ▼
Step 4: 按 UT 模板 + Prompt 生成完整测试代码
    │
    ▼
Step 5: 写入 ohosTest 目录，执行编译检查
    │
    ▼
Step 6: 运行 UT，如有错误进入修正循环
    │
    ▼
Step 7: 输出最终结果报告
```

**4.2 MCP Server 设计（可选，面向更广泛的工具链集成）**

如果需要让其他 IDE 或 CI/CD 也能调用，可以开发 MCP Server：

| MCP Tool | 功能 | 输入 | 输出 |
|----------|------|------|------|
| `build_dag` | 从代码构建 DAG | 入口函数路径、日志文件(可选) | DAG JSON |
| `generate_ut` | 根据 DAG 生成 UT | DAG 文件路径、工程根目录 | UT 代码文件路径 |
| `run_ut` | 运行 UT 并收集结果 | UT 文件路径 | 运行结果 JSON |
| `fix_ut` | 自动修正失败的 UT | 错误信息、UT 文件、DAG | 修正后的 UT |
| `full_pipeline` | 一键全流程 | 入口函数 + 配置 | 最终报告 |

MCP Server 技术选型建议：Node.js/TypeScript 实现，通过 `@modelcontextprotocol/sdk` 接入。

---

### 四、关键技术挑战与应对策略

| 挑战 | 风险等级 | 应对策略 |
|------|----------|----------|
| DAG 准确度 | **高** | 静态分析 + 日志校准 + 人工确认三重保障；DAG 允许增量修正 |
| AI 生成代码编译通过率 | **高** | 提供详细上下文（mock API 文档、import 列表）；模板约束生成范围 |
| 鸿蒙特有 API 的 Mock | **中** | 预建常用系统 API 的 Mock 库（http、router、telephony 等） |
| 异步流程时序控制 | **中** | 使用 fake timer + Promise 链式控制执行顺序 |
| 多机型/多场景组合爆炸 | **中** | DAG 支持参数化节点，通过数据驱动生成多条用例 |
| 大模型幻觉导致错误代码 | **中** | 修正循环兜底；关键 mock 预置于工具库而非每次生成 |

---

### 五、推荐技术栈

| 组件 | 技术选择 | 理由 |
|------|----------|------|
| 静态分析 | TypeScript Compiler API 或 SWC | ArkTS 基于 TS，AST 兼容性好 |
| DAG 格式 | JSON + JSON Schema 校验 | 机器友好，易解析，可视化工具丰富 |
| 测试框架 | @ohos/hypium | 鸿蒙官方测试框架，与 DevEco 集成 |
| Mock 库 | 自建（基于 Proxy/装饰器模式） | 鸿蒙生态尚无成熟 mock 库 |
| MCP Server | Node.js + @modelcontextprotocol/sdk | Cursor 原生支持，社区活跃 |
| Skill | Cursor Skill (SKILL.md) | 无额外部署，直接在 IDE 中使用 |
| DAG 可视化 | Mermaid / D3.js | 便于人工审查 DAG 正确性 |

---

### 六、里程碑与时间线

```
Week 1-3:   ███████░░░░░░░░░  基础设施 (DAG Schema + 测试基座 + Mock 工具库)
Week 4-7:   ░░░████████░░░░░  DAG 构建引擎 (静态分析 + 日志解析 + 校准)
Week 8-12:  ░░░░░░░██████████  UT 生成引擎 (核心: 代码生成 + 修正循环)
Week 13-15: ░░░░░░░░░░░░░████  Skill/MCP 封装 + 文档 + 示例
```

**建议先用一条完整流程（如开卡流程）跑通全链路 MVP，再扩展到更多流程。**

---

### 七、MVP 最小可行路径（建议优先执行）

如果要快速验证可行性，建议用**最短路径**先走通：

1. **手写一个 DAG 文件**（开卡流程），不做自动生成
2. **手写 Mock 工具库**（仅覆盖开卡流程涉及的 3-5 个外部依赖）
3. **编写 Skill Prompt**，让 AI 根据 DAG + 源码 + Mock API 文档生成 UT
4. **验证生成的 UT 能否编译运行通过**
5. 根据 MVP 结果决定后续投入方向

这样可以在 **1-2 周内**验证核心假设："AI 能否根据 DAG 准确生成可运行的端到端 UT"。
