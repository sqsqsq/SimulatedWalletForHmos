# SimulatedWalletForHmos 维护契约

> 本仓维护 Story Extension。本文是项目级唯一维护契约，写给维护设计者与维护实施者；消费模型在 `demo/` 或隔离 workspace 里工作，
> 不读本文件、`doc/` 与 `test/`。角色定义、方法和交付要求按用户级 AGENTS，本文只写本项目特有的对象、事实、约束和入口。

## 0. 入口

| 目录 | 是什么 |
|---|---|
| `extensions/` | Story Extension 开发源（机制、知识样板、宿主入口 `bridges/`） |
| `demo/` | 完整消费工程：业务代码与业务文档、`framework/` 发布件、消费配置、宿主物化与已安装的 Extension（发布版） |
| `doc/` | 项目文档：`spec/` 需求与版本范围，`plan/` 方案、评审与交回，`release/` 按版本的发布说明（只写本版增量）与 AI 交付流程说明；`features/` 是 CLI 测试回流的需求产物（不入库） |
| `README.md` | 项目说明与使用指南，只写当前状态；维护者据此分发给使用者 |
| `test/` | 测试域：测试协议、脚本、Case、夹具、回归台账、金样、演进记录与本地需求系统 |
| `tools/cli/` | 实跑用的 CLI runtime |
| `output/` | 不入库：`output/story/` 放运行证据，`output/scratch/` 放临时脚本、临时工作区与 pytest 缓存 |

`extensions/` 是当前开发版；测试时它被装进从 demo 复制的一次性 template；demo 只在正式发布时更新，平时保持上一个发布版。

- 维护任务以用户本次给定的目标、需求、计划和状态为输入，在 `doc/spec/`、`doc/plan/` 中按该任务查找已有材料；对应不上时先补齐歧义。
  `doc/features/*` 是测试回流的运行产物，其下 `archive/` 按批次存历轮起跑前的归档；维护需求在 `doc/spec/`。
- `doc/spec/`、`doc/plan/`、`doc/release/` 随提交留下历史；运行证据（事件流、运行日志、截图、材料原件、压缩包）放 `output/story/` 并在过程件里按路径引用；
  临时脚本与临时工作区放 `output/scratch/<本次任务>/`。
- 运行、修改或评价测试按 [test/TEST.md](test/TEST.md)，命令、状态、证据与评分只在那里维护；测试命令从仓根执行。
- [test/EVOLUTION.md](test/EVOLUTION.md) 记录演进与规则来源，是追溯证据，不是当前实现依据。
- `demo/framework/` 是 AgentMaison 发布件，只读，变化只经 §6 进入 demo。本仓根不挂 Framework 的阶段钩子与写保护钩子，只读边界由维护者遵守。
- 新 checkout 先按下方「维护环境准备」恢复依赖。
- 维护范围只覆盖 interactive 运行模式；Framework 的 headless/goal 能力不在 Extension 的兼容、状态与测试范围内，用户明确提出时另立需求。

### 维护环境准备

依赖目录不入库，clone 之后按下面装齐（PowerShell，在仓根执行）：

```powershell
python -m pip install pytest pytest-xdist pyyaml                     # 维护脚本与测试
cd demo/framework/harness; npm install; cd ../../..                  # framework harness（门禁、渲染脚本）
cd demo/.opencode; npm install @opencode-ai/plugin@1.18.26; cd ../..  # opencode 插件；package.json 由 opencode 生成、不入库
$env:OHPM_EXE = "<DevEco>\tools\ohpm\bin\ohpm.bat"                    # 鸿蒙依赖用本机 DevEco 自带的 ohpm 与 node
$env:DEVECO_NODE = "<DevEco>\tools\node\node.exe"
demo/scripts/build-dependence.ps1                                     # 重建 demo 各模块的 oh_modules
```

`package-lock.json` 不入库，harness 的依赖会解析到各自版本范围内的最新补丁版。人手试用 `/story` 还要装本地需求系统，见 TEST §1.3。

## 1. 本项目的角色职责

| 角色 | 本项目负责 |
|---|---|
| 维护设计者 | 定位 Extension 的行为问题与最早失效点；为 Framework 协作、Extension 机制、knowledge、adaptation 和测试能力制定方案与验收标准；审查实现和真实执行证据 |
| 维护实施者 | 实现或修正上述对象；交付给消费模型的内容要求在使用前送达、任务边界清楚、完成条件可检查；运行方案确定的验证并提交证据 |

- 「维护者」是两者的合称。维护者直接检查被维护对象（Framework、Extension 生命周期能力、Skill、Hook、Knowledge、Adaptation、Harness、
  Verifier 和测试）的源码、配置、测试和产物，不用被维护系统自己的流程来证明它正确。§5 的方案制定者与 reviewer 指维护设计者。
- 实跑中宿主由本次任务指定的维护角色担任，代理需求方的边界见 TEST §0.3。
- 消费模型是用 Framework + Extension 在目标工程开发真实需求的模型，包括外网隔离 Case 的被测模型和内网仓的使用模型。它只依赖需求材料、
  目标仓事实与 Framework/Extension 上下文；交付内容不引导它读 `doc/`、`test/`、历史方案、失败用例或 checker 源码。它读 checker 是调查信号
  （TEST §6.1 第 3 项）：为定位工具内部错误可以读实现，据此改产物迎合隐藏判据的问题回维护层处理。verifier 是产品内部的独立审查能力。

## 2. 产品定位与所有权

Framework + Extension 是指导模型完成需求开发的 AI Agent 系统；提示词、知识、脚本、门禁、状态文件和报告是载体，评价对象是消费模型在
未知需求上的行为：

```text
输入事实 → 按时送达 → 正确理解 → 做出决策 → 产生产物 → 传给下游 → 失败恢复 → 留下证据
```

代码通过、字段出现、门禁全绿只证明载体的局部性质；消费模型在不接触维护材料的情况下以合理成本得到符合目标的结果，才是能力成立。
局部确定性 helper 证明它实际承担的输入、输出、失败语义和消费者即可；组合成用户可见行为时再沿行为链验收。

| 部分 | 负责 | 不负责 |
|---|---|---|
| Framework | 通用阶段、上下文装配、工具、宿主能力、verifier 调度、阶段闭环与公共扩展点 | 实例业务知识、Story 专属产物语义 |
| Extension 机制层 | 需求流程、作者任务、阶段扩展、知识路由、产物合同和确定性辅助能力 | 目标仓专名、测试答案、Framework 通用能力的影子实现 |
| Knowledge | 项目事实、规约和设计模式；内容由目标仓维护 | 阶段调度、消费方落点坐标、测试与维护历史 |
| Adaptation | 脚本按目录所有权安装/升级机制与入口、写已适配版本，不读写知识；首装由模型写部件定位知识，其余知识由模型按升级演进记录列出的知识主题（没有已适配版本时从基线起）逐题判适用，按方法页从目标仓自己的代码与需求出发写；演进记录的知识条目只写主题回答什么、到哪取证、怎样核 | 替目标仓改知识，灌入或照搬 Demo 知识的正文与结构，按业务改写通用机制 |
| 测试域 | 隔离输入、调度、观测、证据留存、离线回归与真实行为评价 | 替消费模型完成任务、把用例答案注入交付物 |

问题修在最早拥有该职责的位置；缺 Framework 能力时提出或补齐，不在 Extension 内复制旁路框架。

本仓特殊事实：

- `demo/framework/` 是 AgentMaison 3.0.0 的 vendored 副本（`demo/framework/RELEASE-MANIFEST.json`）。正式交付落在上游，经 framework-init UPDATE
  进入消费仓；本仓副本只在用户明确授权的单步验证中临时修改，交付时保留上游基线、可复现补丁和临时放行的失效条件。
- 本仓对 framework 有两处本地定制：`demo/framework/agents/opencode/adapter.yaml` 的 `verifier_subagent` 登记与
  `demo/framework/agents/opencode/templates/agents/verifier.md` 子代理模板（物化为 `demo/.opencode/agent/verifier.md`，根 `.opencode/agent/verifier.md`
  是维护装置的拷贝）。它们不含逻辑改动、不交上游，接入新发布件时按 §6 重新加回；不随 story-adaptation 进目标仓，进目标仓的只有 manifest
  `provides.bridges` 登记的入口。
- `demo/.opencode/` 同时是 CLI 测试装置（Case 工作区从 demo 复制）：外网实跑用 opencode，内网用 codex。

## 3. 不变量

回归台账（`test/regression/failure-modes.yaml` 的 clause）与评审按下列名字引用。

### 3.1 Agent-first

- **信息先于决策**：消费模型做决定之前，目标、事实、约束、可用能力和完成条件已进入它的实际上下文；文件在磁盘、manifest 有登记、
  hook 返回了文本都不等于送达。报错指出未满足的条件和回到正确路径的方法，首次交付的规则在报错之前送达。
- **模型与脚本按能力分工**：模型负责理解语义、判断适用性、处理冲突、取舍、组织叙事和评价内容是否讲清；脚本负责导入、转换、枚举、
  路径解析、结构校验、确定性渲染、状态记录和可复现比较；模型已选的表头、图语法、引用位置由脚本生成与检查。token、子串、字数、相似度和
  字段存在性只表达机械事实，语义审查由独立于作者上下文的 verifier 完成。新增确定性机制前说明它减少的重复劳动或失败、当前责任为何不能
  直接修正、将替换的旧实现。
- **提示词不是执行保证**：消费模型可能忽略、略写、误解、跳步或编造，系统级高风险行为按实际风险组合以下控制层：

  | 层 | 责任 |
  |---|---|
  | 提示词 / 作者任务包 | 在行动前交付完整目标、输入、步骤、输出合同和失败处置 |
  | 确定性脚本 | 冻结输入，控制步骤与状态，生成骨架，检查结构、引用、精确来源和证据完整性 |
  | 独立 verifier | 判断遗漏、略写、矛盾、编造、表达质量与知识是否真正应用 |
  | 隔离行为测试 | 验证未知消费模型、未知材料、时间成本和整套协作是否成立 |

  单层证明不了端到端；纯确定性子能力按其证据闭环，不强制过 verifier 或真实 CLI。作者提示与 checker 共享同一事实、结构和状态真源。
  确定性门一次报告完整问题，并列出因前置缺失未执行的检查。verifier 是纠偏安全网，作者机制以一次高质量完成主体为目标；运行机制不写死
  生成或返修次数。
- **区分约束层级**：已确认业务约束、工具协议与表达/组织建议分开。模板、编排与来源分配保存已有理解，不构成正文上限，允许消费模型补充
  有依据的关系、条件和合理分节；业务结论变化回相应真源，表达深化不增加审批或自证字段。

### 3.2 Extension 结构

- **按运行位置设计**：根 `extensions/` 只存放开发源；链接、命令和相对路径按安装到消费工程的 `doc/extensions/` 及宿主目标位置编写、验证。
  测试先装入隔离 template；正式发布更新 demo；对外 adapt 从 demo 中已安装的发布版执行。
- **两层一桥**：机制层是 `doc/extensions` 中 `knowledge/` 以外的 `skills/`、`hooks/`、`rules/*.overlay.yaml`、合同、`manifest.yaml`
  与宿主入口，基于 Framework 公共扩展点运行，对目标仓模块名、SDK、业务名、绝对路径和测试 Case 零强依赖；知识层是 `knowledge/` 的
  项目事实、规约和设计模式，本仓内容是可适配样板；Adaptation 按所有权接入目标仓，知识由目标维护。
- **机制层零测试特征**：机制层与注入件不含测试 Case 的单号、业务名或需求特征，判据是换一个业务域这段文字是否仍成立；示例用与
  Case 无关的中性题材，示例与适用条件分开；不按某个案例的原句、表行数、图节点或金样章节增加命中或豁免。过拟合自查覆盖新增、复用和
  移动的提示、注释、脚本、合同及实际生成内容，并检查是否提前穷尽了合法业务、强迫固定表达、忽略未预列的关系；只搜专名零命中不算完成。
  生成内容引用当前需求的业务名和数字是正常输入，核来源即可。机械回归见 TEST §5.5。
- **单一真源**：同一事实、状态、配置、编号含义、图片登记和决策只有一个权威来源，其他视图由它生成或解析；随工程变化的约定放数据合同
  或配置，脚本消费数据；域、条目、模式、角色集合从权威清单与正文派生，派生失败明确报错；业务名、契约名、ID 和编号只用于身份与追踪。
  Story/Review 的完整性围绕已确认范围内的业务事实、关系、流程、异常、验收与决策，由独立语义审查判断。
- **引用必须真实存在**：跨文件引用的条目、章号、钩子名和字段先确认在目标里存在；改契约文本时同步它的消费方。
- **显式不适用优于静默跳过**：下游无动作时给出不适用及理由；降级必须可观察并有明确适用条件，正常路径不依赖静默降级。
- **正向表达**：交付面、方案与知识直接写做什么、怎么做；提示给目标、输入、动作、完成条件和恢复方式；禁止性规则保留明确边界，
  退出项写进退出表。注释解释当前职责、理由与边界；维护历史、案例单号、测试业务名、模型名、suite、运行数字与轮次故事留在测试/演进域。
- **正向实现，不打补丁**：同一职责不新旧两套并存；导出即须有消费者；`暂时/临时/待迁移/TODO` 不跨轮次留存。extension 不兼容
  历史功能或数据格式：读到旧格式直接报错，指明在旧版本收口或从 init 重起；目标仓升级要做的事只写在 adapt 的升级演进记录里。

### 3.3 Knowledge

- **知识三类与边界**：

  | 类型 | 回答 | 内容要求 |
  |---|---|---|
  | 项目事实 | 目标仓有什么、在哪里、通常怎样使用 | 真实路径、类名、API、封装形态和工程惯例；不写阶段路由与维护规则 |
  | 规约 | 什么条件下必须做或禁止做什么 | 一条一个可独立判断的要求，写清命中条件、边界与例外；实现专名引用项目事实 |
  | 设计模式 | 什么情形适用、由哪些角色协作、怎样验证 | 适用与不适用条件、角色、骨架和验证清单；目标仓是否采用由具体需求决定 |

  同一知识只在一个面登记。`manifest.yaml > provides.knowledge` 是知识激活清单的唯一来源，只登记路径；每份知识用 frontmatter 的 `kind`、
  `form` 与 `applies_when` 描述自己，机制按它把知识交给当前阶段。框架只读清单列出的文件，派生为空即报错。机制只维护消费时机和产物出口。
- **知识不含维护信息，定位只写一处**：知识正文只写给消费模型——项目概念、事实、已定规范、项目方法的应用步骤、选择依据、参考例子与完成判断；
  阶段目标、何时读、结果写进哪份产物与命令归机制（作者页、模板、任务包）。归属按「什么变了它才变」判；读写规则在机制侧
  `skills/story/reference/knowledge/protocol.md`，适配方法在 `skills/story-adaptation/reference/knowledge-adaptation.md`。
- **知识链**：验收「看到 → 理解 → 应用 → 传递」。看到：当前阶段需要的知识实际进入正确执行体的输入，适用与否由该阶段读后判断；
  理解：执行体结合当前需求判断适用、不适用或冲突，以判断、产物变化和独立审查为证据；应用：适用知识改变本阶段的具体产物、设计或契约实体，
  有可指认的业务落点；传递：下游读取上游已形成的判断与义务，提供落实证据或明确不适用。项目事实从 Spec 起作为目标仓事实使用，发现错误回
  Knowledge 真源；规约由 Spec 判断命中并形成约束，Plan 决定落点与验证方式；设计模式由 Spec 提出候选，Plan 选择、拒绝或调整并冻结。
  知识判断在受其影响的设计之前形成。新增、删除或修改知识时，通用机制无需增加域名、编号、文件名或特例。
- **声明不是应用**：知识冻结须投影为契约实体并有可指认落点；回显名称、anchor 指回声明表自己都不算。
- **Demo 样板义务**：本仓维护者保证样板结构有效、类型边界正确，能演示和测试完整知识链；验证发现样板有真实问题时按实际所有权修复并加回归。
  真实目标仓负责把三类知识修正和扩展为自身事实。

## 4. 验收

- **设计闭合**：脚本只承担能确定计算的判断；提示词、脚本、verifier 和行为测试的责任明确，消费模型的忽略、略写、编造与跳步都有发现者和
  恢复路径；验收能区分正确与错误结果；换一个未知业务域机制仍成立且无需特例。
- **证据分层**：结构证据证明文件、合同、引用、状态和确定性脚本正确；独立语义审查分别核对对象绑定、报告结构和实际语义结论；隔离 CLI
  只在用户启动的里程碑运行，结果由用户按评分协议判；构造缺陷稿只用于确定性脚本自检与事后诊断。「已实施」、原生 gate、离线全绿和一次
  已知 Case 成功都不单独构成行为完成。
- **实际范围**：评价范围是本轮已确认目标加需要保持的原有能力——改进项是否变好、原有关键能力是否保持、有没有靠删事实、改范围或降低要求
  取得通过。测试评分与操作按 TEST §6。

## 5. 维护预算与分级复核

预算用于发现实现走偏、补丁叠加、被替代旧机制未退出和废弃内容残留，不限制功能的正向实现；不删正常功能、必要测试或说明来凑预算，
也不只改预算把问题变绿。阈值和判定原则只在本节维护。

**计量范围（唯一来源，用户裁定）**：只计 `extensions/` 中交付的实现与指令内容，排除 `knowledge/`、`skills/story/scripts/adapters/`
和安装器的升级演进记录 `skills/story-adaptation/reference/upgrade-changes.md`；安装器 `skills/story-adaptation/` 的其余部分计入。依赖、缓存和
适配现场等运行态不计；`test/`、`tools/` 的维护脚本、测试和文档不计，方案不另设预算域。有效行剥离注释/空行的算法由现有计量函数维护。

| 触点 | 必须带到当前工作中的内容 |
|---|---|
| 制定/修改方案 | 能力目标、新旧职责替换、退出范围；计量基线、预计新增量、旧机制退出清单与预计删除量、实施峰值与完成总量；先推演正常路径与异常，再估量 |
| 拆步实施/交接 | 引用本节；给本包新承担者、被替换旧内容及保留能力，写明每步对需求预算的预计增减 |
| 预算报告/超限 | 实际差额、所需复核动作与本节入口；先查实现与方案 |
| 评审/收口 | 核实际 diff 与消费者：有没有更简单完整的实现、旧内容是否真退、是否干扰正常功能 |

新增说明承担什么职责，删除说明由谁接替；移动、格式变化和重复记账不算净减；阶段分项只用于定位，不通过拆步骤重置预算。

**分级比例** `R = 本次累计实际新增实现量 / 初始批准的新增实现预算`。新增包括替换旧实现所写的新实现，旧机制删除量另核；各指标同口径分别计算，
方案指定主要判定指标。纯删除或预算为零时不算百分比；未预算的新实现先由 reviewer 核必要性、确定正预算与适用起点。

| 比例 | 必须采取的动作 | 推进条件 |
|---|---|---|
| R≤100% | 按方案实现并正常评审 | 仍做功能、质量与退场检查 |
| 100%＜R≤125% | 维护实施者自查重复实现、未退旧机制、范围扩大和方案漏算，记录差额与原因 | 可继续 |
| 125%＜R≤150% | 自查后交方案制定者或其指定 reviewer 确认，同时审实现与方案有无更简单完整的替代 | reviewer 具名确认后继续 |
| R＞150% | reviewer 整体反思实现与方案，形成保留/替换/预算调整建议 | 人工确认后继续，reviewer 不能代替 |

需确认时仍可做收敛性修正、删除、必要验证和准备评审材料；未确认前不扩大实现、不宣告完成、不进入下一实施包。确认记录写入该需求的方案、
评审或预算记录，注明范围、额度、理由与确认角色；初始预算与累计变化保留，连续小幅改签不能规避 150% 人工确认。完成时同时核功能质量、
实际新增、旧机制退出与最终总量：预算以内但旧实现未退出不能完成；超预算但必要合理的按上表权限调整。§3 的质量要求不能通过增加预算豁免。

**现有检查只覆盖一部分**：`test/regression/mechanism-budget.yaml` 与 `test/tests/test_mechanism_budget.py` 按上述范围检查分类总量、峰值与完成目标；
R 的分级计算与确认检查尚未接线，现有测试通过不代表分级复核已做，由 reviewer 按本节执行。接线现状与历史额度见台账文件头。

## 6. framework 接入

输入是 Maison 的已验证发布件（zip），版本与构建身份看其中 `framework/RELEASE-MANIFEST.json`。
`python test/scripts/check_framework_drift.py` 比较 main 与 demo 接入的版本：退出 0 相同，1 不同，2 读取失败。

1. demo 先干净：`git status --porcelain -- demo` 为空。
2. 把发布件解压到 demo 根，替换 `demo/framework/`；用 `git diff --stat -- demo/framework` 核改动面与发布件的 `MIGRATION.md` 相符。
3. 两处本地定制（§2）被发布件覆盖时，在新文件上重新加回定制内容，不整文件回退到旧版。
4. 在 demo 根按 [framework-init](demo/framework/skills/project/framework-init/SKILL.md) 做 UPDATE（S1–S4），物化清单按本轮实际选择。
5. 用 demo 已装版本的 manifest 判断 diff 里的入口是否属于 Extension；已登记入口或 AGENTS/CLAUDE 的 story-ext 扩展段被换成通用内容时，
   只把该文件恢复为已装版本的内容，不重装 Extension（方案 1.9.8 分册 03 §2.2）。
6. 装置同步：根 `.opencode/agent/verifier.md` 逐字节复制自 `demo/.opencode/agent/verifier.md`。
7. 验证：demo 下 `cd framework/harness && npm test`；`check_framework_drift.py` 结果与本次接入一致；按 [TEST §5](test/TEST.md) 跑与改动相关的离线回归。
8. 提交 demo，并在 [test/EVOLUTION.md](test/EVOLUTION.md) 登记发布件版本、source_commit、定制处理与验证结果。

失败时用 git 查看并还原 demo；framework 自身的缺陷报回上游。

## 7. Extension 安装与发布

同一个安装函数 `test/scripts/publish_to_demo.py` 服务两种目标，顺序固定：整体替换目标 `doc/extensions` → 按 manifest `provides.bridges`
的「目标位置 / 来源」对写宿主入口 → 更新 AGENTS.md / CLAUDE.md 的 story-ext 扩展段（区外不动）。

- **测试**：只装一次性 template，由 `run_multi_case.py` 按 TEST §1.2 装配，离线检查用的 template 按 TEST §5 现建。测试不写 demo；
  需求产物回流到维护仓 `doc/features/`。
- **版本号**：新版本第一次改动 `extensions/` 的提交就把 `manifest.yaml` 的 `version` 升到新版本号。
- **正式发布**：前置是用户已决定发布本版本、demo 干净。

  ```powershell
  python test/scripts/publish_to_demo.py --source extensions --target demo --dry-run   # 看计划
  python test/scripts/publish_to_demo.py --source extensions --target demo             # 退出 0 = 已安装
  ```

  验证 `git status -- demo` 的改动只在 `demo/doc/extensions/`、manifest 登记的入口和两份入口文件的扩展段，再核 demo 扩展与开发源同源（打印 `True`）：

  ```powershell
  python -c @"
  import sys
  from pathlib import Path
  sys.path.insert(0, 'test/scripts')
  import publish_to_demo as p
  src, dst = Path('extensions'), Path('demo/doc/extensions')
  files = p.enumerate_source(src)
  print(files == p.enumerate_source(dst) and all((src / f).read_bytes() == (dst / f).read_bytes() for f in files))
  "@
  ```

  然后跑 `python test/scripts/check_failure_modes.py`（缺省检查 demo）。发布提交带上 demo、`doc/release/<版本>.md` 与更新后的
  [README](README.md)，并在 EVOLUTION 登记。提交前核：本版增量里使用者可见的每项变化都已反映在 README 的当前描述里
  （命令、能力、产物、入口、安装），与发布版本一致；README 只写当前状态，版本变化只写在本版发布说明。
- **失败**：退出 2 是输入读取或 git 前置不成立，目标没写；退出 1 是写入中途失败，结果 JSON 列出实际完成项。用 git 查看并还原 demo，
  修好后从同一源重装。
- **对外升级**：其他仓的安装与升级用 demo 里已装的发布版 adapt（`demo/doc/extensions/skills/story-adaptation/`）。
