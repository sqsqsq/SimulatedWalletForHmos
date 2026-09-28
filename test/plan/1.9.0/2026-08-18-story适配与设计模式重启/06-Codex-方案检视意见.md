# Codex 对「story 适配与设计模式重启」的方案检视意见

> **审视者：Codex（OpenAI 的 GPT-5 系列编码代理）**
> **审视日期：2026-08-18**
> **审视对象：**本目录 `00`～`05` 六份方案
> **总判定：REVISE——需要重大修订，暂不建议按当前批次进入实施。**

## 0. 我是谁，以及这份意见怎么得出

我是 **Codex**，本次以本仓库主代理身份执行静态设计审查。我的职责不是替方案作者做
最终业务裁决，而是依据仓库 SSOT、当前实现和指定 SDK 源码，指出方案中已经能够证实的
矛盾、缺口与实施风险，并给出可落地的收敛路径。

本次检视完整对照了：

- 根 `AGENTS.md`，以及 `test/story/AGENTS.md`、`TEST.md`、`EVOLUTION.md`；
- `test/story/truth/达标判据.md`、`评测标准.md`、`rubric.yaml`；
- 当前 story 扩展的 SKILL、规则、脚本、hook、overlay、交付说明与测试；
- framework 的 plan/use-case/context-facts/harness 契约（只读）；
- `E:\Project\AIDefectHelpler\demo\sdk\Framework` 的导出与运行时源码（只读）。

本报告区分三类表述：

- **已验证事实**：当前文件或源码可直接证明；
- **影响判断**：由已验证事实推出的工程后果；
- **修订意见**：我建议方案作者采用的收敛方式。

## 1. 总体结论

方案的目标是合理的，以下方向值得保留：

1. 用真实 SDK/HAR 消除上一轮“载体不存在却盲测落码”的假洞；
2. 把设计模式拆成识别、分解、落位，而不是继续堆叠泛化知识正文；
3. 按功能单元、阶段做知识路由，避免全量投喂；
4. 用章节边界声明治理跨章重复，用确定性渲染治理决策引用噪声；
5. 把 `context-exploration.md` 漂移到 `context/facts.md` 识别为 P0 bug。

但当前版本还不是可交给实施者直接执行的方案。七项问题会造成错误交付、错误契约、
无法到达的路由或不可归因的评测，必须先修；另有五项重大缺口需要同步收口。

## 2. BLOCKER：实施前必须修正

### B1. `01` 把本地替身误判为“真实实现”，会把测试桩直接交付

**已验证事实**

- `01-story适配指南方案.md:37` 声称 `doc/extensions/` 可整包复用，且“仓内脚本即真实实现”。
- `doc/extensions/skills/story/scripts/story.js:2,31-37,44-46` 明确写着它是部署环境需要替换的
  数据对接层、本地只读 `test/story/mock-data/` 并模拟系统读写。
- `review.js:2-15` 同样明确是本地替身；`token.js:12-13` 返回占位 token。
- `test/story/DELIVERY.md:54-64` 明确禁止把这些脚本随分支直接送出，否则会覆盖部署侧可用实现。
- `test/story/AGENTS.md:189` 把“让文档迁就本地替身”列为已有实证的永久雷区。

**影响判断**

按现方案执行会得到一份“代码仓看似完整、实际上依赖测试数据且不连接真实需求系统”的交付。
删除 patch 机制可以是用户已定的交付方式变化，但不能顺手删除数据适配边界这个事实。

**必须修订**

按当前 SSOT，ADAPTATION 应明确采用以下唯一策略：

1. story 产品代码随仓交付，但 `story.js`、`review.js`、`token.js` 是**部署环境必换适配器**；
2. 适配清单改为显式 allowlist，不能写“整包复制再排除一个目录”；
3. 三个适配器分别列出 CLI/I/O、失败码、工作区不变量和契约测试；
4. 只有部署实现通过 `test_data_adapter_contract.py` 等契约验证后，才能称为适配完成；
5. 删除 DELIVERY/patch 机制时，把其中仍有效的适配边界迁入 ADAPTATION，不能一并抹掉。

### B2. 设计模式路由缺少“首跳”和稳定身份，plan 实际上不知道该读什么

**已验证事实**

- `03-遵从性路由机制方案.md:16-20` 已正确确认：plan/coding 的 authoring skill 不直接读取
  `doc/extensions`，lifecycle fragment 主要进入 verifier 的 `ai-prompt.md`。
- `framework/harness/harness-runner.ts:662-676,806-819,948-952` 也证明 fragment 的确定出口是
  AI 语义验证提示，而不是 plan 撰写模型的上下文。
- `03:43` 又把 `use-cases.yaml`/`contracts.yaml` 的字段投影本身当成模式登记；这些字段没有
  稳定 pattern ID，也不能解释“为什么选这个模式、应读哪份下篇”。
- `02-design-patterns重启方案.md:78-79` 新增的指路件和 overlay 仍只能可靠到达 verifier。

**影响判断**

当前链路从“plan 应选模式”开始，但没有任何上游产物告诉 plan 哪个功能单元出现了什么信号。
即使模型偶然选对，下游也无法从普通业务字段区分决策树、页面交互或两者叠加，SKIP/FAIL
判据同样缺少稳定依据。

**必须修订**

采用以下闭环，不新增独立台账：

1. **spec 只识别信号，不替 plan 选模式**：在现有 `context/facts.md` 的 Code Facts/本阶段事实中，
   按功能单元记录可观察信号、证据和候选知识路径；
2. **plan 作最终选型**：读取 facts 和 `design-patterns/README.md` 路由表，在 `plan.md` 增加
   “设计模式应用表”；
3. 应用表至少固定 `use_case/功能单元 ID`、`pattern_id`、`实例名`、`选型理由`、
   `知识文件`、`contracts/files/interfaces 锚点`；零命中和多模式叠加均显式表达；
4. **coding/review 只沿应用表消费**：coding 读取命中模式的落码部分，review 以同一表核对 diff；
5. overlay 检查“应用表与契约/代码是否一致”，不以猜测业务字段来反推是否选过模式。

这样首跳由必读的 `context/facts.md` 承担，模式身份由 `plan.md` 承担，下游不依赖不确定的 hook 注入。

### B3. 把决策树内部节点映射为 `state_model.phases`，污染业务 UT 契约

**已验证事实**

- `02-design-patterns重启方案.md:51-52,71` 计划把“节点枚举”投影到
  `use-cases.yaml.state_model.phases`，把树路径投影到业务分支阶段序列。
- `framework/skills/reference/plan-workflow-detail.md:40-51` 明确 `UseCase` 是文档级业务规约，
  代码形态由 coding 决定。
- `framework/profiles/hmos-app/skills/business-ut/templates/use-cases-schema.md:3-15,91-94`
  明确 `state_model.phases` 是供 UI 订阅和 UT 断言的**对外业务状态**。

**影响判断**

决策树实现节点并不天然是用户或 UI 可观察的业务状态。机械映射会让 business-ut 对内部实现
细节做断言，后续只要重构树结构就会被误判为业务行为变化。

**必须修订**

- `use-cases.yaml` 只记录真实可观察的业务状态、用户动作和分支；
- 决策树节点/动作枚举、builder/manager 类型和文件落点写入 `contracts.yaml` 的
  `files/interfaces` 及 plan 的模式应用表；
- 仅当某节点本来就是对外发布的业务状态时，才允许同时出现在 `state_model.phases`；
- overlay 应验证这种语义边界，不能要求每个模式节点在 use-case 中一一出现。

### B4. 把 design-pattern 全链评测塞进 `test/story`，越过了测试域 SSOT

**已验证事实**

- 根 `AGENTS.md:119-123` 把 story/spec 优化映射到 `test/story/`。
- `test/story/AGENTS.md:12-15` 又把该域目标限定为首版 `AR/story.md` 与 `AR/review.md` 的
  S1～S6/R1～R4 质量。
- `00-总体执行计划.md:37,52`、`02:91`、`03:67` 计划在 TEST.md 新增
  plan→coding→review 的设计模式全链案例。

**影响判断**

`run_case.py` 即使技术上能驱动后续阶段，也不等于测试域已经授权改变被测对象和达标判据。
直接混入会污染 story 的基线、评价口径和演进记录。

**必须修订**

- `test/story` 继续只评 story/spec 首份人类评审产物；
- design-pattern 建立独立测试域（建议 `test/design-patterns/`），自带 `AGENTS.md`、`TEST.md`、
  truth/fixtures，并定义 plan 投影、coding 落码、review 核查及模块编译的验收；
- 若坚持复用 `test/story`，必须先由用户明确批准扩域并同步修改该域 SSOT，不能在实施批次中暗改。

### B5. `05` 同批修改产品、判据、门禁和评价器，结果不可归因

**已验证事实**

- `00-总体执行计划.md:35` 把 S7、章节合同、渲染、rules、overlay、rubric v5、collect 放在同一批。
- `05-产物成文质量评审方案.md:49-119` 对应同时触及真值判据、作者约束、确定性产品脚本、
  运行时语义门禁、评价 rubric 与取材器。
- `test/story/AGENTS.md:195-203` 要求先定位最早责任层，并明确写着：
  “不得同时改判据、模板、门禁和 harness。”

**影响判断**

同一案例变好或变坏时，将无法判断是作者产品修正有效、评价标准被改宽/改严，还是采集方式改变。
这也让 S7 的 origin 失去独立性：被测物和裁判在同一轮一起变化。

**必须修订**

按缺陷和责任层拆开：

1. D1 跨章重复：只改章节边界合同/作者规则，用现有 rubric 复跑；
2. D2 决策引用：只改确定性渲染及其单测，用现有 rubric 复跑；
3. 连续多轮证据证明确有新判据缺口后，再单独修改 `达标判据.md` 与 rubric，并回填 EVOLUTION；
4. overlay/collector 只有在现有评价材料不足时另批增加，collector 只提供事实，不判语义；
5. 任一批都保留前一批基线，不能用“最后一起绿”代替因果验证。

### B6. 决策引用的新形态违反现有 S6/写作规则，且把关键行为留给实施者决定

**已验证事实**

- `05:88-90` 提议渲染为 ``relationalStore（待评审，DEC-002）``，同时写着“具体形态实施时定”。
- `truth/达标判据.md:61-64` 规定 story 不含议程，`待/需/须确认`、建议类措辞归 review。
- `rules/rules.md:30-33` 规定决策先登记，作者正文只写占位引用，不直接写结论。
- 当前 `story-build.mjs:493-503` 把引用展开为完整问题，确实会把表格单元格撑成议题句。

**影响判断**

D2 的根因判断成立，但拟议输出又把“待评审”议程写回 story；同时 open/settled、表格/散文、
重复引用的行为未定义，实施者仍需自行设计核心语义。

**必须修订**

锁定一个确定性、无议程措辞的渲染合同：

- 作者仍只写 `{{DEC-xxx}}`，不得绕过登记表手写结论；
- `status=settled` 渲染为 `conclusion（决策记录 DEC-xxx）`；
- `status=open` 渲染为 `proposal（开放决策 DEC-xxx）`；
- story 不出现“待评审/待确认/建议确认”等语气，完整问题、责任人和确认结果仍只在 review；
- 同一占位符每次按同一规则渲染，不做“首次/后续”这种依赖出现顺序的隐式状态；
- 同步把 `rules.md` 澄清为“作者不直接写，装配器可以从已登记字段投影”，并用 open/settled、
  表格/散文、重复引用四组单测锁定。

### B7. HAR 集成仍有关键决策空白，也没有可追溯的二进制身份

**已验证事实**

- `02:25` 把 HAR 收纳位置和消费方式留到“实施时按现状定”，`02:32` 只写“建议入库”。
- 当前工程没有 `.har` 或既有 `libs/` 约定；根 `build-profile.json5:28-48` 登记的模块中也没有
  SDK 模块。
- SDK `oh-package.json5:2-8` 声明 `framework@1.0.0`，但 author/license 为空。
- SDK `Index.ets:1-3` 的公开导出可以确认，但现方案没有固定来源提交、源码摘要或 HAR SHA-256。

**影响判断**

实施者仍需自行决定“放哪里、谁消费、是否提交、怎么更新”，且无法证明仓内二进制对应本次
审过的源码。空 license 也意味着不能由实施者擅自推断可复制/再分发边界。

**必须修订**

在实施前一次性锁定：

1. HAR 的确切仓内路径、文件名和首个消费模块；
2. 消费模块 `oh-package.json5` 的本地依赖写法及对应模块构建命令；
3. 源仓标识（提交或受控版本）、源码/HAR SHA-256、构建工具版本和可复现构建命令；
4. 二进制是否入库以及更新流程；
5. 代码所有者对内部复制/入库的确认。`license: ""` 不能被当成授权结论。

## 3. MAJOR：方案应同步收口

### M1. `04-P0` 对 facts 契约的事实判断错误

`04-story独立性方案.md:19` 声称 facts 没有 `key_inputs_read`，准备把读取记录塞进 Code Facts
或 `phase_delta`。但 `doc/features/AR90004/context/facts.md:7-15` 已实际使用该字段，
`framework/harness/scripts/utils/context-exploration.ts:31-40` 也明确按
`frontmatter.key_inputs_read` 消费。

修订方式应非常小：hook 和 overlay 直接改读/写 `context/facts.md` frontmatter 的
`key_inputs_read`，保持三份上游路径；不要发明 Code Facts 同义落点。该修复应作为独立 P0 批次。

### M2. P1/P2 都还不是 decision-complete

- `04:25` 在“Python 抽共享实现”与“保留双份”之间留给实施者选择；
- JS 侧拟建 `paths.mjs`，但 `story.js` 是 CommonJS，方案没有定义 CJS/ESM 互操作；
- `04:32-34` 只让 `merge-story.mjs` 读取 `spec_shape`，遗漏
  `story-build.mjs:416-438` 的同一 SPEC ID 正则，因此“story 侧唯一镜像”仍不成立。

建议 P1/P2 延后到功能修复稳定后再做。若继续实施，JS 侧应选定一个 CJS/ESM 都可消费的
单一模块并写互操作测试；Python 保留语言内实现但以跨语言 parity test 锁定语义。
`merge-story.mjs` 与 `story-build.mjs` 必须同时消费同一 `spec_shape`；独立评价器
`assert_story.py` 仍应独立实现判据，避免被测产品和裁判共享同一配置而共同漂移。

### M3. 删除 DELIVERY/两层规约的迁移清单不完整

当前仍存在以下活引用：

- `test/story/AGENTS.md:29`、`TEST.md:17,27`；
- `test_product_reader_purity.py:5`；
- `constraints-source/AGENTS.md`、`generate.py` 与多份 knowledge/style/generated 测试；
- `test_export_delivery_patch.py` 与导出脚本自身。

`01:90-92` 只列了部分删除项。修订方案应先给出“删除、迁移、改写、历史保留”四类清单，
再以 `rg` 零活引用（历史设计/EVOLUTION 可列白名单）验收。另外，`00:44` 引用了不存在的
`test/AGENTS.md`；仓内实际存在的是 `test/story/AGENTS.md`。

### M4. 设计模式知识必须区分“SDK 声明字段”与“运行时真正使用的字段”

源码核验结果：

- `DecisionTreeNode.nextNodes` 在 `DecisionTree.ets:10` 声明，但运行时 `23-38` 不读取它；
- `Interaction.nextNodes` 和 `operateSequence` 在 `PageInteraction.ets:3-15` 声明，运行时
  `29-38,51-52` 同样不读取；
- `BaseStateMachine.fireEvents` 会按 operator 返回值持续运行，直到返回 `undefined/null`
  （`StateMachine.ets:13-23`）。

因此知识文档不能声称 SDK 会校验 `nextNodes` 或自动维护 `operateSequence`。有真实用户等待点时，
当前 action 必须返回 `undefined`，后续用户动作再次调用 `doOperator`；否则状态机会连续跑完。
demo 中已有调用点也不能默认全部视为最佳实践，应建立“正例/反例/仅证明 API 可用”的分类表。

### M5. rubric 的 32 与 41 不是同一个计数口径

`rubric.yaml` v4 有 **32 个 observation points**，另有 9 个 S/R 顶层 criterion 节点，因而
全文共有 **41 个 `id` 节点**。`EVOLUTION.md:20` 的 41 与 05 所说的 32 可以同时成立；真正
过期的是 `评测标准.md:45` 的“28 条（v2）”。不要把三处无条件统一成一个数字，应明确写成：

> rubric v4：9 个 criterion、32 个 observation point、合计 41 个带 ID 节点。

## 4. 建议采用的收敛架构

### 4.1 模式应用链

```text
spec：识别功能单元的可观察信号
  ↓ 写入既有 context/facts.md（事实，不做最终选型）
plan：读取 facts + 路由表，形成带 pattern_id 的模式应用表
  ↓ 投影业务行为到 use-cases，投影代码结构到 contracts
coding：按应用表读取命中模式的落码部分并实现
  ↓
review：按同一应用表核对契约、diff 与模式不变量
```

三个真源的边界应固定为：

| 真源 | 只回答什么 |
|---|---|
| `context/facts.md` | 哪个功能单元出现了什么事实信号，证据在哪 |
| `plan.md` 模式应用表 | 选了哪个 pattern/实例，为什么，知识和契约锚点在哪 |
| `use-cases.yaml` / `contracts.yaml` | 可观察业务行为 / 具体代码文件接口，不重复登记选型理由 |

### 4.2 推荐重排批次

| 批次 | 唯一目标 | 验收重点 |
|---|---|---|
| 0 | 仅修 `key_inputs_read` P0 漂移 | 现有 story 测试与一例实跑行为不变 |
| 1 | ADAPTATION 与交付边界 | 替身不进入复用 allowlist；部署适配器契约清楚；活引用迁移完 |
| 2 | HAR 与两份模式知识 | 来源/摘要/消费模块锁定；模块编译；知识只陈述真实 API 行为 |
| 3 | facts→plan→coding/review 路由 | 稳定 pattern ID 与应用表；业务/实现契约不混层；独立测试域验证 |
| 4 | D1 跨章重复修复 | 只改边界合同/作者规则，用当前 rubric 对照基线 |
| 5 | D2 决策引用修复 | 只改渲染及单测，用当前 rubric 对照基线 |
| 6 | 评价体系演进 | 多轮证据成立后，单独升级 S7/rubric；overlay/collector 按需另批 |
| 7 | 可选 P1/P2 解耦 | CJS/ESM/Python 语义一致；两个产品脚本共用 spec shape |

## 5. 方案修订后的准入条件

只有以下问题都能在修订稿中直接找到唯一答案，才建议进入实施：

- 哪些文件随仓直接可用，哪些数据适配器必须由部署环境替换；
- HAR 的来源、摘要、路径、消费模块、依赖写法和构建命令；
- plan 在没有可靠 authoring hook 的前提下，如何首次获知模式候选；
- pattern ID 在哪里登记，coding/review 如何无歧义地找到对应知识；
- 哪些状态属于业务可观察状态，哪些只是决策树内部节点；
- design-pattern 全链评测属于哪个测试域；
- open/settled 决策引用在每种上下文中的确定渲染结果；
- 每个批次只改变哪个责任层，如何用未同步变化的评价标准判断效果。

## 6. 本次审视边界

- 本次只新增这份检视意见，没有修改 `00`～`05` 方案、产品代码或 `framework/`。
- 已做仓库与 SDK 源码静态核验；没有把“尚未实施的方案”宣称为已经通过编译或实跑。
- 报告中的行号对应 2026-08-18 当前工作区版本；后续方案改写后应重新核对。
