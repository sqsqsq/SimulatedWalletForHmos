# 既有优化诉求守恒下的 Extension 正向重建方案（评审稿）

> 状态：待评审，尚未实施  
> 日期：2026-08-19  
> 当前实现基线：`aad670c`（临时本地归档1）  
> 兼容行为参照：`0c8ab1d`（`aad670c` 的父提交）  
> 本文范围：Story 输入与装配、完成态闭环、工程知识激活、Plan 机械门禁、自包含交付验证  
> 本文不修改 Extension、测试、配置、依赖或 Framework；评审通过前不进入实施

## 0. 结论先行

本问题不能靠回退解决，也不能在当前严格 selector、实例路径和脏工作区依赖上继续打补丁。

目标态必须同时满足三条基线：

```text
目标态 = C0 输入兼容下限 + C1 既有能力上限 + C2 正向治理增量
```

- **C0 输入兼容下限**：只纳入有父提交代码行为、父版回放或内网回执证明的真实材料维度；这些已证维度不能因为新合同收窄而失败。
- **C1 既有能力上限**：`aad670c` 已实现的 Human-First、决策闭环、图片与内容校验、工程知识跨阶段生效、`features_dir` 适配和 Story 生命周期能力不得回退。
- **C2 正向治理增量**：补上尚无父版成功证据的输入韧性、可恢复事务、共享完成检查、Manifest 单一激活真源、Plan 精确引用、自包含候选提交与正式实跑闭环。

因此：

1. `0c8ab1d` 只是**兼容行为基线**，不是代码回滚目标，也不是 Story 输出质量金标准。
2. `aad670c` 是**能力保留基线**，其中的严格 selector、非原子 scaffold、实例硬编码和未确认知识激活不是必须保留的能力。
3. 正向修复的核心是把“外部输入是什么样”与“最终 Story 应该是什么样”彻底解耦：脚本只盘点输入和校验输出，材料理解、事实取舍与自然归章由模型和语义审阅负责。
4. 工程知识是否生效只由 `manifest.yaml > provides.knowledge` 决定；目录存在、README 列表、ADAPTATION 登记和测试夹具都不能暗中激活知识。
5. 当前 `pattern-image-review` 实跑只可作为问题证据：运行中读取了 `test/story/EVOLUTION.md`，运行开始后才产生 `aad670c`；状态字段仍指向 Review，但实际最后动作已进入 Coding 并被强制终止，且没有 `report_data.json` 或完整评价回执。它不计入任何 Gate 的通过数量，也不能作为 clean commit 或无提示能力凭证。

## 1. 问题边界与前序成果关系

### 1.1 三轮既有优化均按“能力诉求已实施”处理

本文把以下三组设计与其落地能力作为守恒输入，不把它们误判为“尚未做”：

1. [`2026-08-18-story适配与设计模式重启`](../2026-08-18-story适配与设计模式重启)
2. [`2026-08-19-story人类表达与测试历史迁移`](../2026-08-19-story人类表达与测试历史迁移)
3. [`2026-08-19-story人读表达与工程知识生效`](../2026-08-19-story人读表达与工程知识生效)

其中“已实施”不等于“已经形成自包含、无污染、全链正式通过凭证”。这一区分只影响验收结论，不削弱既有能力的保留优先级。

### 1.2 本目录三份前文的分工

- [`00-实跑事实与问题记录.md`](00-实跑事实与问题记录.md)：保留原始运行事实。
- [`01-完整问题分析与正向优化方案.md`](01-完整问题分析与正向优化方案.md)：包含更宽的日志、VOC、Chart、CommFunc 等候选议题；这些议题本轮不实施。
- [`02-临时本地归档1过拟合审计与正向治理方案.md`](02-临时本地归档1过拟合审计与正向治理方案.md)：保留过拟合事实、实例泄漏和错误验证结论。
- **本文**：在不丢三轮既有优化诉求的前提下，给出可执行、可逐闸门验收的正向重建合同。

### 1.3 本轮明确排除

本轮不借重大问题修复之名扩展到以下内容：

- Logger、VOC、Chart、`05-SystemBase/CommFunc` 业务能力；
- 新的日志/可观测性类型系统；
- 产品架构、Catalog、Glossary 的业务改造；
- Framework 源码修改；
- 为单次实跑结果新增大批语义评分规则；
- 把当前未跟踪的 `libs/`、HAR、测试目录或本地 `ui_kit_target_dir` 当成默认运行前提。

### 1.4 修正落点

按“修正三问”判断：

| 问题 | 判断 | 落点 |
|---|---|---|
| 需求与既有验收诉求变了吗？ | 否 | 不重写三轮优化目标 |
| 设计、契约或机械门禁错了吗？ | 是 | 先修 Extension 合同、装配设计、知识激活与 Plan 机械边界 |
| 可以直接只改几行产品代码吗？ | 否 | 评审合同后再分片实施，并重验受影响的下游链路 |

### 1.5 证据分级

为避免把“用户确认曾正常”“代码具备降级分支”“某次正式运行 PASS”混成一件事，后续只使用以下分级：

| 等级 | 可支持的结论 | 当前事实 |
|---|---|---|
| E0 代码行为 | 某个分支客观存在 | `0c8ab1d` 在标题候选全部落空时回退整篇；`aad670c` 改为 missing/失败 |
| E1 离线正反例 | 机械合同在夹具上成立 | 当前有大量测试，但部分测试反向保护了 selector、UI Kit 和 Demo 假设 |
| E2 clean snapshot | 候选交付闭包自包含 | 当前临时提交不包含完整 `test/story`、CLI、HAR/依赖，尚未成立 |
| E3 正式行为 | 真实 CLI、读模型、无污染、四轴终态 PASS | 当前运行被污染、被强制终止、缺终态报告，尚未成立 |
| E4 内网兼容回放 | 原先正常的代表性材料在候选上仍正常 | 用户已确认父版正常，但具体 case/hash/回执仍需在 Gate 0 建账 |

父提交“整篇 fallback”能证明机制较宽容，但不能自动证明所有缺失、占位、DOCX 或多语言组合都曾成功。拿不出父版成功证据的输入维度统一归 C2 正向增量，不冒充 C0 回归。

## 2. 必须守恒的能力不变量

后续每个实施切片都必须声明影响了哪些不变量；任一不变量回退即不得进入下一闸门。

| ID | 必须保留的能力 | 可替换的错误机制 |
|---|---|---|
| INV-01 | 外部 RR/SR/AR/UX 材料可以缺失、占位、以任意 inbox 文件名导入，并可使用自由标题层级或纯文本 | 标题候选、正则、标题路径、primary 必须命中，或 runtime 扫全仓猜文件 |
| INV-02 | Story 保持 8 章正文 + 3 个附录、固定顶层顺序和稳定章节 ID | 章节与某份输入文件或某个 Mock 标题一一绑定 |
| INV-03 | H2 由装配器生成，作者按真实对象自然使用 H3/H4 | 用固定内部小标题证明“结构完整” |
| INV-04 | 保留 `reader_question`、`already_explained`、`boundary`、`expression_hint`、`review_focus` 的 Human-First 编辑职责 | 把这些职责误实现为输入 selector |
| INV-05 | 保留 `decisions.json` v2、`ids.json` v1、空集合 `none_reason`、每项决策在 Story 唯一投影 | 依赖具体业务 ID、Mock 决策名或关键词判定 |
| INV-06 | Review 保留决策全景、逐议题人工区、计划外意见和人工状态 | 构建失败时静默清空或重置人工区 |
| INV-07 | 保留段落、列表、表格、流程/状态/时序图、图片、引用块和最终图片安全校验 | 强迫所有来源图片进入 Story，或用数量代替相关性判断 |
| INV-08 | 非 Story 场景的 Spec 保持静默通过；Story 场景才启用专属完成门禁 | 对所有 Spec 无条件要求 Story/Review |
| INV-09 | 保留 `story init/import/scope/split/archive/restore/review/help` 和 `features_dir` 跨运行时适配 | 写死默认 `doc/features` 或某个实例模块目录 |
| INV-10 | 保留 `Spec 候选 → Plan 独立选型 → 主体设计/contracts 投影 → project_knowledge 冻结 → Coding/Review/UT/Testing 消费` | Spec/Plan 扫目录、token 任一命中、未确认 Demo 自动激活 |
| INV-11 | 保留动态约束、phase overlay、共享 hook、pre-verifier 和目标仓适配机制 | 假定每个仓库必有 SDK 模式、HAR 或 UI Kit 目标目录 |
| INV-12 | 保留 phase/worker/source transaction、不可变运行目录、正式非沙箱实跑语义 | 用脏工作区、预注入测试知识或不完整运行替代正式凭证 |
| INV-13 | `framework/` 继续只读 | 为解决实例 Extension 问题修改 vendored Framework |

## 3. 根因不是“校验太严格”，而是职责层错位

| 根因 | 当前错误 | 为什么内网会坏 | 正向职责边界 |
|---|---|---|---|
| R1 输入格式被当成能力合同 | 章节要求精确 heading/regex/path/primary | 真实材料结构变化就被判缺失，即使正文事实完整 | 外部材料只做物理盘点；模型语义读取并归章 |
| R2 脚本承担语义判断 | 标题、关键词、token-any-hit 被当成意义证明 | Mock 能绿，真实语义却假失败或假通过 | 脚本只验证路径、ID、集合、状态和可复算关系 |
| R3 Scaffold 非原子 | 先建目录、逐章写，最后才汇总失败 | 失败留下半初始化目录，后续命令误当合法工作区 | staging + 校验 + 最后发布 ready marker；失败保持旧状态 |
| R4 完成态过浅 | Spec Hook 只看 `story.md`、`review.md` 存在 | 空文件、旧文件、不同步文件可以越过门禁 | CLI 与 Hook 共用无副作用的严格完成检查 |
| R5 Story/Review 非一致发布 | Story 先落盘，Review 后失败 | 两份产物可能属于不同构建，人工区还可能丢失 | 内存预渲染、统一 `build_id`、可恢复事务提交点 |
| R6 知识有三套真源 | Manifest、目录扫描、ADAPTATION 各自决定可见性 | 未激活或未确认材料仍进入 Spec/Plan/下游 | Manifest 精确集合是唯一激活真源 |
| R7 Demo 被当成工程事实 | 两个模式处于未确认，却被 Manifest 激活并依赖本地 HAR | 离开当前脏工作区就不可复现 | 未确认只能做参考/夹具；激活项必须确认且自包含 |
| R8 Plan 机械合同实例化 | 强制 `ui_kit_target_dir`、目录首段、任意 token 命中 | 合法根目录文件失败，实例词碰撞却通过 | 安全项目相对路径 + 正式 ID 精确唯一解析 |
| R9 测试保护了实现细节 | 明确要求 H1 不命中、无关标题失败、至少两个 SDK 模式 | 测试证明的是 Demo 一致，不是通用能力 | 围绕输入变形、状态机和语义边界建立正反例 |
| R10 交付不是自包含候选 | `test/story`、`libs/`、配置与依赖留在脏工作区 | 临时提交在另一环境缺少验证链或运行依赖 | tracked-only clean snapshot 与正式 CLI 双重验收 |

关键代码证据快照：

- 父提交 `0c8ab1d:doc/extensions/skills/story/scripts/story-build.mjs:119-132,717-738`：标题落空回退整篇、单份缺失可跳过；它证明宽容分支存在，不证明所有组合成功。
- 当前 `doc/extensions/skills/story/scripts/story-build.mjs:160-185,923-982`：selector 落空为 missing，且 scaffold 在最终失败前已经逐文件写入。
- 当前 `doc/extensions/skills/story/scripts/story-build.mjs:1190-1240`：Review 人工区解析与 Story/Review 写入存在不一致风险。
- 当前 `doc/extensions/hooks/spec/post_check.mjs:564-573`：Story 场景只做最终文件存在性门禁。
- 当前 `doc/extensions/manifest.yaml:19` 与 `doc/extensions/ADAPTATION.md:148-149`：模式已列入激活集合，但适配仍未确认。
- 当前 `doc/extensions/hooks/spec/post_check.mjs:95`、`doc/extensions/hooks/plan/post_check.mjs:120-160,213-243`：消费者扫目录，Plan 同时存在 token-any、目录首段和 UI Kit 实例假设。
- 当前 `test/story/tests/test_story_build.py:209-249,335-340`、`test_plan_post_check.py:42-57`：测试保护了 selector 与固定 UI Kit 夹具，而不是输入变形能力。

## 4. 目标总架构

### 4.1 Story 链：输入宽容、输出严格

```text
外部材料（任意标题/层级/语言/缺失状态）
              │
              ▼
      纯机械 source inventory
  （路径、状态、hash、图片链接；无语义抽取）
              │
              ▼
        模型读取全部可用材料
   （理解事实、取舍、自然归入 11 个章节）
              │
              ▼
       v5 Human-First 编辑工作区
 （章节职责 + 作者正文 + decisions + ids）
              │
              ▼
    可恢复事务 build + 共享 completion
              │
              ▼
       同一 build_id 的 Story + Review
              │
              ▼
       独立语义 Verifier + 人工评审
```

核心原则：**Extension 对输出合同严格，对外部材料格式宽容。**

### 4.2 工程知识链：激活显式、选型独立

```text
Manifest provides.knowledge（唯一激活集）
              │
              ▼
       Spec：只登记候选，不选型
              │
              ▼
 Plan：结合真实仓库独立采用/拒绝，并投影主体设计
              │
              ▼
       project_knowledge 冻结精确引用
              │
              ▼
 Coding / Review / UT / Testing 只消费已冻结且仍激活的知识
```

目录存在、README 列出、ADAPTATION 有一行记录，都只能提供材料，不能改变激活集合。

## 5. Story 输入与章节合同 v5

### 5.1 新增物理来源合同 `story-sources.json`

建议新增：

`doc/extensions/skills/story/contracts/story-sources.json`

它只声明来源角色、物理位置和确定性枚举方式，不声明标题、表格、关键词或章节路由。例如：

```json
{
  "schema_version": 1,
  "numeric_provenance_roles": ["product_requirement", "system_design"],
  "sources": [
    { "source_id": "rr-prd", "role": "product_requirement", "kind": "file", "path": "RR/prd.md", "owner": "external", "required_at": [] },
    { "source_id": "sr-design", "role": "system_design", "kind": "file", "path": "SR/design.md", "owner": "external", "required_at": [] },
    { "source_id": "ar-scope", "role": "ar_scope", "kind": "file", "path": "AR/design.md", "owner": "story-flow", "required_at": [] },
    { "source_id": "ar-upstream", "role": "ar_upstream", "kind": "file", "path": "AR/upstream.md", "owner": "external", "required_at": [] },
    { "source_id": "ux-reference", "role": "ux_reference", "kind": "directory", "path": "ux-reference/", "recursive": false, "extensions": [".md", ".png", ".jpg", ".jpeg", ".webp", ".bmp"], "owner": "external", "required_at": [] },
    { "source_id": "spec", "role": "implementation_spec", "kind": "file", "path": "spec/spec.md", "owner": "spec", "required_at": ["build", "pre_archive_current", "archive_ready"] }
  ]
}
```

约束：

- 所有外部材料对 `scaffold` 都是可选的。
- `required_at` 只允许绑定生命周期阶段，不能绑定某个标题或章节。
- 来源角色用于帮助模型理解上下文，不是章节允许列表。
- 文件内容变化只改变 inventory，不改变章节合同。
- `source_id` 必须唯一；所有路径均为 feature 相对路径，禁止绝对路径、`..`、realpath 越界和符号链接逃逸。
- 目录来源必须显式声明是否递归、扩展名白名单和稳定排序；本轮保持现有 UX 顶层平铺、非递归语义，不由实现者顺手扩成递归扫描。
- UX 图片白名单与 importer 当前能力对齐为 PNG/JPG/JPEG/WEBP/BMP；SVG 若要成为直接导入来源，必须同步修改 importer、Framework 能力声明和正反例，不能只在 inventory 偷偷放行。Markdown 内已有的本地 SVG 链接仍按普通 local image 校验。
- “自由文件名”发生在 inbox/import 阶段：importer 接受外来文件名并归一到 canonical target；Story runtime 只读来源合同中的 canonical target，不扫描整个 feature 猜材料。

### 5.2 生成 `source-inventory.json`

落点：`<feature-dir>/AR/story-src/source-inventory.json`。

文件来源和目录来源分别记录；目录项还要包含逐文件稳定排序的 `entries[]` 和目录摘要。每个材料只记录：

- `source_id`、`role`、`kind`、feature 相对路径；
- 文件的 `missing | empty | placeholder | available`，目录的 `missing | empty | available`；
- 可用文件的字节数和 SHA-256；
- Markdown 图片的 `local | remote | data` 类型、原始目标；只有 local 才解析相对路径、存在状态和摘要；
- 整体确定性 `snapshot_sha256`。

边界：

- 不记录标题、表头、关键词、命中章节或抽取正文。
- `placeholder` 只认 `story_flow.py`/模板新生成的显式机器标记；禁止用“待补充”“TODO”等业务词猜测。Gate 1 必须同步修改这个唯一写入者。
- 旧占位模板只允许迁移器按完整旧模板识别一次。
- 缺失、空白、占位也进入摘要，使“缺失→新增”“占位→正文”能让旧构建失效。
- 读权限或摘要计算失败是 inventory 操作错误，命令在写目标前失败，不能伪装成 `missing`。
- 不写绝对路径、时间戳或机器相关目录，保证同一输入字节稳定。
- dot/temp 文件的排除规则必须在合同中明示；目录条目按规范化 POSIX 相对路径排序；符号链接默认拒绝。
- remote/data 图片只登记、不联网抓取，也不误报为本地文件缺失；最终 Story 继续按现有协议允许的图片类型分别校验。

### 5.3 `story-chapters.json` 升级到 v5

v5 只描述 Extension 拥有的输出编辑模型：

- 保留现有 11 个章节 ID、标题和顺序；
- 保留 Human-First 字段；
- 用“本章内容所有权/首次解释职责”替代 `primary source`；
- 删除每章 `inputs`、`heading`、`heading_regex`、`heading_path`、`whole`、`primary/supporting` 和必需来源命中；
- 将 Demo 高频措辞改为通用职责表达，避免把“能力占位、管理台放量、特定 SDK”等实例词固化到通用章节合同。
- 顶层继续保留当前 `spec_shape`，供 build 与 merge 共用；不得因删除 inputs 顺手丢掉 Spec 编号和可标识事实覆盖能力。

建议的章节条目形态：

```json
{
  "id": "05-experience-flow",
  "title": "体验、流程与状态设计",
  "reader_question": "读者在这里要解决什么问题",
  "already_explained": ["此前已解释、这里只引用的内容"],
  "boundary": "本章不重复解释什么",
  "expression_hint": "适合的自然表达方式",
  "review_focus": "人工评审重点"
}
```

首版不增加 `evidence_hints`。`reader_question`、内容所有权和全量 inventory 已足以指导写作；软路由字段很容易再次演化成 selector。若以后确有证据需要，只能作为不参与任何机械判定的独立提示变更。

### 5.4 输出检查与来源角色边界

- 数值溯源本轮保持现有真源边界：只有 `product_requirement`（RR）和 `system_design`（SR）可以证明上游数值；`implementation_spec` 不能自证。
- `ar_upstream` 是否将来成为数值真源必须另行评审并增加正反例，本轮不顺手扩大。
- Spec 编号、决定引用、图片安全和可标识事实覆盖继续由 v5 顶层 `spec_shape` 与共享 output-check 合同驱动。
- `context/facts.md > key_inputs_read` 的机械期望集合只由 inventory 中 `available` 且属于流程输入的 material 派生，覆盖 RR/SR/AR/upstream 和 UX，明确排除 `owner: spec`/`implementation_spec` 等本阶段输出，避免输出自读循环；它只核对 source ID/路径已声明读取，不推断模型是否真的理解。

### 5.5 生成区与作者区

每个章节文件必须显式区分所有权：

```markdown
<!-- story-generated-task:start schema=1 -->
...Extension 拥有的任务说明...
<!-- story-generated-task:end -->
<!-- story-author:start -->
...作者拥有的正文，允许包含普通 HTML 注释...
<!-- story-author:end -->
```

- Builder 只解析这两个边界，不再通过“删除全部 HTML 注释”猜作者正文。
- Scaffold 只能修改 generated 区；ready 工作区的 author 区逐字节保留。
- v4 迁移只按已知完整旧 header 前缀剥离；边界无法唯一识别时先备份并失败，不猜测。
- 作者区是否非空属于 build freshness；不进入 workspace 结构 marker 的摘要。

## 6. 原子 Scaffold 与迁移状态机

### 6.1 有效工作区必须有最后发布的 marker

新增 `<feature-dir>/AR/story-src/workspace.json`。它是**结构提交点**，只记录 workspace schema、`story-chapters`/`story-sources` 合同摘要、精确章节 ID/顺序、登记表 schema 和 scaffold-owned 路径。它不哈希作者正文或登记内容；正常编辑不能把 ready 工作区变成 corrupt。

`AR/story-src` 同时包含 `story_flow.py` 拥有的 `.positioning`、`.scope-options`、`.gate-options`、`.split-parts` 等侧车。Scaffold 只拥有合同列出的 chapters、registries、inventory、marker 和自身事务日志，禁止整体替换或清空 `AR/story-src`。

| 状态 | 判定 | 普通 `scaffold` 行为 |
|---|---|---|
| `absent/flow_only` | 没有编辑产物，或只有 Story 流程侧车 | 创建完整工作区 |
| `ready` | marker 与 scaffold-owned 结构、合同版本一致 | 保留作者正文，只事务性刷新 inventory |
| `stale` | marker 有效，但合同版本或章节集合已变化 | 不写，要求显式迁移 |
| `legacy` | 有章节/登记表但无 marker | 不写，要求显式迁移 |
| `partial/corrupt` | marker 与文件不一致，或有失败残留 | 不写，输出恢复说明 |
| `transaction_recovery` | 存在本脚本事务日志 | 只恢复本事务拥有的文件，不猜测人工内容 |

首次发布必须满足：

1. 在同一 feature 内的事务 staging 区生成完整章节任务书、`decisions.json`、`ids.json`、inventory 和 marker 草稿，只列出本命令拥有的文件。
2. 在 staging 中完成全部机械校验。
3. 通过逐文件备份、事务日志和可恢复 rename 发布全部生成件；不能假设文件系统提供多文件原子 rename。
4. `workspace.json` 最后发布，作为 ready 提交点。
5. 可捕获失败必须回滚到旧 ready 状态；进程崩溃可以留下明确的 transaction-recovery 状态，但该状态不可被接受，下次命令先恢复。

### 6.2 CLI 语义

- `scaffold`：首次创建，或对 ready 工作区无损刷新 inventory。
- `scaffold --migrate`：迁移 legacy/stale/partial 工作区，先备份并输出迁移报告。
- `scaffold --rebuild`：用户显式要求重建，先备份；作者正文只能按稳定章节 ID 恢复，未映射内容必须列入报告。
- 旧 `--force`：报废并给出明确替代命令，不再隐式覆盖人工正文。

### 6.3 v4/v2 迁移

- 当前 v4 的 11 章：保持章节 ID，替换生成头注，作者正文逐字保留；`decisions` v2、`ids` v1 不迁版本。
- 父版旧章节集合：脚本不能假装会语义合并；旧章节整体备份为迁移材料，由模型归入 v5，脚本只负责证明没有静默丢内容。
- 父版无版本登记表必须显式迁移：`open + proposal`、`settled + conclusion` 只有无歧义时才能转成 v2 `display_text`；字段缺失或互相冲突时不猜，原件与 hash 进入报告并返回 `semantic_rehome_required`。
- 父版 ids 补 `schema_version: 1`；空 decisions/ids 需要人工填写 `none_reason`，脚本不能替写业务理由。
- 当前严格 scaffold 留下的 partial：先备份；同 ID 且存在作者正文的章节恢复，缺章补任务书，未映射内容进入迁移报告。
- 迁移报告逐旧文件登记 hash、映射目标和 `mapped | unmapped | semantic_rehome_required`；结构迁移成功不等于语义归章完成。
- 已归档的历史 Story/Review 不批量重写。
- 新 build 全部成功前，不覆盖已有 Story/Review。

## 7. Build、Check 与阶段完成态

### 7.1 命令状态与归档生命周期必须分开

| 命令 | 成功只代表什么 | 不代表什么 |
|---|---|---|
| `scaffold` | 编辑工作区结构完整 | Story 已写完或语义合格 |
| `build` | 当前作者区、登记表、Spec 和 inventory 可确定性装配 | Human-First 质量通过 |
| `check --profile ...` | 对应生命周期 profile 的机械不变量成立 | 事实取舍和自然表达正确 |

Completion 至少支持三个 profile：

| Profile | 适用时点 | 当前性合同 |
|---|---|---|
| `pre_archive_current` | 写作、Spec 结束到归档前 | Story/Review 必须与当前 workspace、Spec、inventory 属于同一 build |
| `archive_ready` | 执行 archive 前 | 同上，并叠加归档自包含检查；draft 可按现有流程归档但必须显式记录提示 |
| `archived_snapshot` | 归档完成后 | 校验归档时的 pair、归档回执和人工区完整；后续 Spec/source 漂移只进入处置台账，不把历史 Story 判坏 |

归档凭据必须绑定实际上传字节，而不是上传后再 hash 可变工作区：

1. `archive_ready` 先生成唯一 `archive_attempt_id`，并在持久事务目录写入 immutable staged bundle、机器基线和 `prepared` attempt；重试必须复用同一 attempt ID。
2. 部署适配器按 attempt ID 幂等上传 Story/Review，逐附件记录状态。若远端不支持两附件原子提交，部分成功时只能补传缺件或执行已登记补偿，不能新建另一轮无关联上传。
3. 上传结果先持久化为唯一 receipt：`{schema_version, archive_attempt_id, state, build_id, story_sha256, review_full_sha256, review_machine_sha256, review_status_warning, staged_bundle_ref, backup_ref, remote_refs, artifact_statuses}`。`state` 至少区分 `prepared | uploading | uploaded_unbound | bound | compensation_required`。
4. `story_flow.py archived --receipt <exact-path>` 显式接收该 receipt，核对 feature/build/attempt 后事务性绑定归档状态；禁止扫描“最新 receipt”猜版本，也不另行对可变工作区取 hash。
5. 上传成功但本地绑定前崩溃时，以同一 attempt ID 查询/复用 remote refs，从 `uploaded_unbound` 继续；绑定完成后 receipt 进入 `bound`。`restore` 必须按该 archived receipt 的 `backup_ref` 恢复对应版本，不能取模糊的最新备份。
6. `archived_snapshot` 冻结 Story 全文、Review machine 区和 build ID；`review_full_sha256` 只证明初次上传内容，归档后人工区/status 合法变化不会让快照失效。

归档后普通 `build/rebuild` 必须拒绝。现行归档不可逆，本轮不凭空增加“新评审轮”命令；若未来需要多轮评审，必须另行定义 round schema、历史 receipt 和迁移协议。Plan/Coding 以最新 Spec 和正式契约为准，不因合法的 archived Story 与后续 Spec 漂移而阻塞。

### 7.2 Story/Review 可恢复事务构建

Build 必须：

1. 重新盘点 inventory，并记录开始时 Existing Review 的完整 hash。
2. 在内存或 staging 中完成章节、决策、编号、图片、可标识事实等现有确定性检查。
3. 完整预渲染 Story 和 Review，不提前落其中一份。
4. Existing Review 的人工区、计划外意见或状态无法安全解析时直接失败，绝不能生成空白区替代。
5. 已删除/改名的议题若仍有人工内容，失败并要求显式迁移。
6. 计算 canonical `build_id`，写入 Story/Review 机器标记和事务提交元数据。
7. 发布前复算 Existing Review hash；若人工并发编辑，放弃发布并保留其内容。
8. 用 staging、旧文件备份和事务日志发布；`build.json` 最后提交。崩溃可留下可识别、不可接受、可恢复的 transaction 状态，不能宣称文件系统天然支持多文件原子写。

`build_id` 的 preimage 固定为 UTF-8、LF、规范化 POSIX 相对路径、稳定字段顺序的 canonical JSON，并带协议版本。至少覆盖：

- `story-chapters` 与 `story-sources` 合同摘要；
- source inventory 摘要；
- 所有章节 author 区的逐字节摘要；
- decisions/ids 摘要；
- 最终 Spec 摘要；
- 去掉 build marker 后的渲染 Story；
- 去掉 build marker 和人工区后的 Review 机器区。

Preimage 明确排除：`build_id` 自身、事务 marker、时间戳、绝对路径、Review 人工填写、人工状态和确认信息，避免自引用及机器差异。

Review 状态仍必须绑定 build：

- draft Review 可以在保留人工内容的前提下重建；
- confirmed Review 若新 `build_id` 与其绑定的旧 ID 不同，build 在写前失败；归档前只能由人显式改回 draft 并确认旧结论失效，归档后则禁止 build；
- confirmed 状态下，每个议题必须恰好一个人工表态并有确认信息；不能只检查状态字符串合法。

### 7.3 共享 Completion Inspector

抽出一个无副作用、按 profile 返回结构化问题数组的唯一 completion inspector，供 CLI `check`、Spec Hook 和 archive-only 包装器复用，禁止通过 shell 拼接另一个 CLI，也禁止 `merge-story` 复制一套通用校验。

`pre_archive_current` 的机械检查至少包括：

- `workspace.json` 与 scaffold-owned 结构、合同版本一致；
- 章节集合与 v5 合同精确一致，无缺章、额外旧章；
- 每章显式 author 区去除首尾空白后非空，同时保留其中合法 HTML 注释；
- decisions v2、ids v1 结构合法；
- 磁盘 inventory 与实时盘点一致；
- Story/Review 非空、事务已提交，且使用相同、当前的 `build_id`；
- Story 可由当前章节 author 区、登记表、Spec 和 inventory 确定性重装配；这里不要求脚本重新从外部 RR/SR 做语义写作；
- Review 状态、build 绑定、机器区、人工区、回链和计划外意见边界完整；
- 所有登记决策均有唯一机器议题和 Story 回链；
- 最终 Story 的 local/remote/data 图片都必须有非空替代文本；local 额外要求目标存在且不越出 feature，remote/data 不联网抓取；
- Spec 编号、数值真源和现有确定性覆盖检查通过。

`archive_ready` 在此基础上叠加归档自包含；`archived_snapshot` 改为对归档时冻结的 hashes/回执复算，不与实时 Spec/source 强制相等。

机械检查明确不做：

- 判断某个标题是否像 Mock；
- 判断材料应该归入哪章；
- 判断某张来源图是否业务相关；
- 判断 Story 是否自然、取舍是否合理；
- 猜测无编号事实是否遗漏；
- 通过关键词判断模式或规约是否语义命中。

### 7.4 生命周期接入

- Spec `post_check` 仅在 `story-flow.json` 表明 Story 场景、且尚未归档时调用 `pre_archive_current`。
- 非 Story Spec 保持静默通过。
- Plan 入口不复算 archived Story 对最新 Spec 的当前性；如需核验，只验证 `archived_snapshot` 归档凭据，不重写 Story/Review。
- `merge-story` 只叠加 archive-only 自包含规则，并把状态缺失、人工区边界损坏等问题纳入失败集合。
- draft 在现有允许的 spec/archive 场景仍合法，但归档回执必须记录提示；confirmed 必须满足逐议题确认合同。
- `required_at` 只按当前 profile 执行；`archived_snapshot` 不重新应用 live source/Spec 的 required_at。
- “机械完成”“归档状态”“语义 PASS”在回执中分栏，禁止合并成一个笼统 PASS。

### 7.5 远端 Review 回稿的正向合并

真实需求系统可能剥离 HTML marker，adapter 不能先覆盖 canonical `AR/review.md` 再让 Builder 报坏。部署适配必须声明并通过一种 round-trip capability：

- `markdown_roundtrip_v1`：经真实系统往返后逐字保留 build/machine/human-zone markers；或
- `structured_feedback_v1`：远端只返回按稳定 decision ID 键控的表态、说明、状态、确认信息和计划外意见，由本地用 archived machine base 确定性合并。

原始回稿先落独立、不可变 receipt；只有 marker/ID、build 绑定、议题全集和人工区校验全部成功后，才事务性替换 canonical Review。两种 capability 都不成立时在部署前失败，并保留原始回稿供人工恢复，绝不能清空人工区或覆盖归档机器区。

## 8. 工程知识激活的唯一真源

### 8.1 三种状态必须分离

| 状态 | 所在位置 | 能否影响运行 |
|---|---|---|
| 参考材料 | adaptation/examples 或其它参考目录 | 否 |
| 已适配、未启用 | 已有目标仓证据，但未列入 Manifest | 否 |
| 已激活知识 | 已确认且精确列入 `provides.knowledge` | 是 |

硬合同：

- `active patterns = manifest.yaml > provides.knowledge` 中 `knowledge/design-patterns/*.md` 的精确集合，明确排除所有 `README.md`/catalog 文档。
- `active constraints = manifest.yaml > provides.knowledge` 中 `knowledge/constraints/*.md` 的精确集合，`README.md` 不属于 active domain。
- 所有可激活文档以 frontmatter `knowledge_kind: pattern | constraint_domain | project_fact` 闭合分类；component-profile、codebase-facts 属 `project_fact`。README/catalog 不可激活，也不进入 `provides.knowledge`。
- `knowledge_id = frontmatter name = 文件名 stem`，在对应类别内唯一。
- 激活项必须在 ADAPTATION 中为“已确认”。
- 未确认项不得进入 Manifest；已确认但未激活可以作为候选材料。
- ADAPTATION 的绑定表升级为通用 registry：每个 active `knowledge_ref` 精确登记 kind、confirmed 状态、事实证据 refs 和依赖 refs；pattern 可附加 SDK/案例字段，constraint domain 与 project fact 使用各自真实证据，不强迫伪造 SDK 信息。
- Patterns/Constraints README 只描述 schema/消费协议，不维护第二份激活清单；若保留展示型索引，必须由 Manifest 投影且 validator 对不一致 fail。
- 不再新增第二个 `enabled` 字段或平行状态文件。

### 8.2 统一解析器

新增 `doc/extensions/scripts/lib/active-knowledge.mjs`，由 Spec probe、Spec/Plan post-check、共享阶段 hook、动态 pre-verifier 和 `verify-adaptation` 共用。

它只负责：

- 从 hook payload 的 `projectRoot` 定位 Extension，使用唯一 YAML parser 解析 Manifest 的 canonical `provides.knowledge`；
- 按 `knowledge_kind` 返回 active patterns、constraint domains、project facts；未知 kind 或 catalog 被列入 Manifest 立即失败；
- 校验项目相对路径安全、文件存在、ID 唯一、frontmatter 与文件名一致；
- 在任何 prompt/overlay/Story 直接链接注入前，按 kind 校验 active 项在通用 ADAPTATION registry 中已确认，事实/依赖 refs 可解析且进入 delivery closure；
- 接受空 pattern 集合；
- Manifest/ADAPTATION/依赖解析错误一律 fail closed，不能被解释成合法空集；
- 阻止任何消费者自行扫描目录或直接从 README 激活知识。

现有 `pre_verifier.md` 是静态文本，不能直接执行 JS helper。实施时将它改成 Manifest 指向的动态 `.mjs`，由该脚本调用 helper 后输出 `promptFragments`；不保留一份静态代码路径自行解析 catalog。Framework 已支持 `.mjs` hook，本轮无需修改 `framework/`。

Standalone `/story init|scope|split|...` 也必须在读取工程事实前执行同一 resolver。删除 Story `SKILL.md`、rules 和 reference 对 component-profile/codebase-facts 的静态直链，只允许读取 resolver 返回的 active + confirmed `project_fact` refs；合法空集时明确进入“无 Extension project facts，按真实仓库研究”的降级路径，解析/确认错误则 fail closed。动态 Spec hook 不能替 standalone Story Skill 兜底。

### 8.3 三种 Plan 产物形态

1. **仓库没有激活模式**：Spec 不要求模式候选章节；Plan 保留总的“工程知识决策”和约束表，但完全省略模式子节；`pattern_applications: []`；所有模式 overlay 直接 SKIP。
2. **仓库有激活模式，但当前需求零命中**：Spec 仍按实际需求单元记录“无候选”；Plan 必须有逐单元模式处置表，数组为空；下游依据该设计结论 SKIP。
3. **仓库有激活模式且有采用项**：Plan 模式表、主体设计/contracts 投影和非空 `pattern_applications` 同时存在并集合一致。

第一种恢复父版内网可用的零模式基线；第二种保留本轮新增的“零命中也要经过设计判断”；第三种保留模式对主体设计和下游的真实投影。

### 8.4 当前两份未确认 Demo 的处理建议

推荐默认方案：

- 先从 Manifest 激活集合移除；
- 未确认参考移到 `doc/extensions/adaptation/examples/design-patterns/`；专用测试模式移到 `test/story/fixtures/`，不继续留在 runtime-looking `knowledge/design-patterns/`；
- 用自包含 fixture 验证“有模式”的全链行为；
- 目标仓完成真实 SDK/平台事实确认后，把确认文档和所需依赖作为同一候选提交原子加入 Manifest。

另一条合法路径是：把真实 HAR、依赖声明、目标仓证据和相应测试全部纳入 tracked 候选，再把这两份模式标为已确认并激活。不能继续让未跟踪 `libs/` 或本地 WalletMain 依赖替代交付证据。

这不是关闭设计模式能力，而是把“机制存在”与“当前仓库已有可信知识”分开。

### 8.5 异构知识协议

模式文档只强制通用字段：

- pattern ID；
- 适用单元；
- 适用/不适用条件；
- 解决的问题；
- 对主体设计与 contracts 的投影；
- 对实际消费阶段的实现、审查和验证义务。

所有 active 模式至少提供 Plan 选型、契约投影、Coding 实现指导和 Review 审查指导；UT/Testing 只在 `behavior_anchors` 非空且被分配到对应层时触发。SDK 行为、Builder/API、包名版本、代码骨架、UT/Testing 行为锚点均为条件字段。非 SDK 结构模式不得为了通过固定标题而伪造 SDK 章节，`behavior_anchors: []` 可以是合法设计结论。

## 9. Spec、Plan 与下游知识链

### 9.1 Spec 保持“候选，不选型”

- active pattern 集为空时，不注入模式候选模板，也不要求固定章节。
- active pattern 集非空时，只向模型提供精确激活路径。
- Spec 继续逐真实需求单元登记候选或无候选，不决定采用。
- 出现未激活 ID、重复 ID 或陈旧候选时机械失败；若 active set 已改变，先回 Spec（必要时先完成 adaptation）重跑候选，不允许 Plan/下游静默裁剪。
- 候选是否遗漏、适用性是否成立仍由语义 Verifier 判断。

### 9.2 Plan 保持独立设计顺序

Plan 顺序不回退：

1. 独立理解需求和代码事实；
2. 逐项处置 Spec 候选；
3. 先形成主体设计与 contracts，消费 Spec acceptance/use-cases，并只按 Framework 合同补足 Plan 被允许负责的缺项；
4. 再按 §8.3 三态写适用的模式子表与约束决策表；
5. 冻结 `project_knowledge`；
6. 下游只消费冻结结果。

模式关闭不关闭 constraints 链。

### 9.3 Plan 机械合同最小正向修复

- pattern/constraint catalog 改读 Manifest 精确集合，不扫描目录。
- Manifest 内部路径保持 Extension-relative `knowledge/...`；Plan/Contracts 中 `knowledge_ref` 统一写 POSIX 项目相对 `doc/extensions/knowledge/...`，helper 负责唯一转换，禁止两种形式混用。
- 删除对 `ui_kit_target_dir` 的无条件读取与存在性要求。
- 工程路径只机械检查：非空、项目根相对、无绝对路径、无 `..`、解析后不越根。
- 根目录文件和任意合法工程布局均可使用。
- 模块归属由 contracts 的显式模块字段和既有 architecture gate 判断，禁止从路径第一段推断。
- 本轮对所有实现路径只做规范化与安全/越根检查。现有 contracts 没有文件级 `path/action` 真源，因此 Plan Hook 不猜 add/modify，也不做存在性分支；新增/修改真实性在 Coding diff 与 scope/architecture gate 中核对。若以后需要前置机械判断，必须另行定义并评审最小 `{path, action}` 合同。
- `behavior_anchors`、`verification_anchors` 的每个值天然就是 acceptance/use-cases 的正式 `id` 引用，必须按解析后的 ID **精确且全局唯一**命中；禁止拆 token、正则猜测或任一片段命中。
- `contract_anchors`、`implementation_anchors` 若仍是自由文本，只检查结构非空或安全路径，并明确交给语义 Verifier；脚本不得宣称已经证明语义投影。
- active constraint 文档必须按固定表结构解析为全局唯一的 `{rule_id → domain_ref, owner}`；重复 rule ID、表结构歧义或正则散落命中一律 fail closed。Plan 决策表与 `constraint_obligations[].rule_ids` 均须精确命中，且 domain/owner 与 catalog 一致，禁止 Set 静默吞重复或跨域错挂。

本轮不额外引入一套大而全的 typed-reference DSL。若后续发现自由文本确需机械解析，应作为独立设计变更，而不是借当前故障夹带，也不与 `01` 中的可观测性合同绑定。

### 9.4 下游消费

所有模式 overlay 先执行同一个前置：

- active set 为空：SKIP；
- active set 非空、当前需求合法零命中：核对 Plan 结论后 SKIP；
- 有采用项：只消费 `pattern_applications[].knowledge_ref` 指向且仍处于 active set 的文档；
- 冻结的 `project_knowledge` 引用已退出 Manifest：FAIL 并回 Plan；若知识本应恢复，先过 adaptation 再重跑 Spec/Plan，禁止下游静默重选；
- 无行为锚点时，UT/Testing 可基于设计理由 SKIP，不伪造覆盖。

## 10. 实例知识与测试知识隔离

### 10.1 允许进入 Extension 运行时的内容

- 通用 Story 角色、状态机和输出合同；
- Manifest 激活的真实、已确认工程知识；
- 当前项目可追溯、已提交的代码与配置事实；
- 通用的 `features_dir` 和阶段消费机制。

### 10.2 只能留在 `test/story` 的内容

- AR90004、AR90006 等测试 ID；
- Mock 标题、Mock 模式名、预制 Story 文本；
- 脏工作区路径、临时 HAR、WalletMain/UI Kit 专用夹具；
- 实跑输出、测试历史、污染判定和评测报告。

### 10.3 规则文档回流

根 `AGENTS.md` 已经要求 Story 优化必须读取 `test/story/AGENTS.md`、`TEST.md` 和 `EVOLUTION.md`，本轮不再复制一套冗长反过拟合规则到根入口。

Gate 0 必须显式登记一项定向勘误：废止 `test/story/AGENTS.md` 中“每章声明输入源/形态”被解释成 selector/primary 机械门禁的旧实现，同时保留“最终 Story 对全部可用来源负责、语义审阅能核对来源”的产品目标。Gate 1 以 C0/C2 变形正例同步替换当前 selector 专用测试，避免实施期间两套合同互相阻塞。

除此以外，实施期间冻结 `TEST.md` 的产品语义标准、S/R rubric 和正式实跑定义；只更新受错误合同影响的单元/集成测试。新的长期红线只有在多类正反例和至少一轮无污染正式结果支持后，才回流 `test/story/AGENTS.md` 与 `EVOLUTION.md`。这样避免用一次失败继续制造另一组过拟合规则。

## 11. 验证设计：双基线、双环境、四结果轴

### 11.1 两条不可替代的基线

#### C0 兼容基线

Gate 0 先建立逐项基线账本，只有证据完整的维度才叫 C0：

```text
dimension
→ parent case/hash
→ parent command/result
→ evidence path/receipt
→ candidate oracle
```

当前已知只有两类线索：父代码在标题候选全部落空时存在整篇 fallback；用户确认临时提交前 Extension 在内网正常。它们足以证明“不能整体回退兼容性”，但不足以宣称所有缺失、占位、DOCX、多语言组合都曾在父版成功。

内网真实材料只记录匿名 case ID、材料角色、hash、结构维度、父版结果和候选结果，不把私有正文带回仓库。C0 的期望是“不破坏已证行为”，不是要求新旧 Story 字节相同。

以下作为 C2 正向韧性用例，除非 Gate 0 找到父版成功回执后再提升为 C0：

- H1-only、无 Markdown 标题和纯文本；
- 章节重排、标题重命名和多语言标题；
- 一份或多份外部材料缺失/空白/显式占位；
- 来源补齐后旧 build 失效；
- 任意 inbox 文件名经 importer 归一到 canonical target；
- UX 顶层二进制图片；
- remote/data 图片不联网且不误报；
- 正式 DOCX import 后进入 Story 流程。

#### C1 能力基线

逐项验证 INV-01 至 INV-13，包括 11 章 Human-First、决策投影、Review 人工区、图片、知识跨阶段、`features_dir`、归档生命周期和运行基础设施。

### 11.2 可复算验证映射

Gate 0 产出机器可读 `verification-map.yaml`。每个 INV、C0/C2 dimension 和 Gate 条件必须映射到：

```text
case_id
case_role: unit_contract | clean_snapshot | mechanical_formal | semantic_formal | c0_compat_replay | internal_compat_only
evidence_level: offline | clean | formal | internal
environment
required_gate
covers: [INV/C0/C2 IDs]
pass_predicate_ref
positive/negative fixture 或 property generator
精确 oracle
固定命令
证据路径
candidate tree hash
```

不可穷举词必须变成有限用例或确定性属性测试：

- 标题变形固定 transformation 集（H1/H2/H3 重命名、去标题、重排、Unicode/多语言），记录 generator 版本、seed 和样本数。
- 路径等价类至少覆盖根文件、嵌套路径、Unicode/空格；反例覆盖 POSIX 绝对路径、盘符、UNC、`../`、规范化越根和 symlink 越根。
- Scaffold/Build 建立 `failpoint-catalog.yaml`，枚举合同解析、每类 staging 写、备份、发布、marker/commit-point、回滚与恢复分支；测试逐 failpoint 执行，而不是声称“任何故障”。
- Human-First 不做关键词单测，必须映射现有 S1–S7/R1–R4 的独立语义回执和事实底册。

### 11.3 核心正反例矩阵

| 领域 | 正例 | 反例 |
|---|---|---|
| 输入兼容 | 固定变形集中的标题、H1-only、纯文本、缺失来源按各 case oracle 执行 | source ID 重复、路径越界、读取错误在写前失败 |
| Inventory | 缺失→新增使摘要变化，重建后通过 | 旧 Story 继续冒充当前来源快照 |
| Scaffold | 首次完整发布；ready 重跑生成区稳定；显式迁移有备份 | 任一已登记 failpoint 留下可被接受的 ready 半目录 |
| Build | 同一 build ID/提交点，人工区逐字保留，并发编辑被检测 | build ID 自引用；Review 损坏被清空；只更新 Story |
| Completion | 三种 lifecycle profile 分别满足其精确不变量 | archived snapshot 被实时 Spec 漂移误判，或空产物通过 |
| Human-First | 11 章、自然 H3/H4、决策唯一投影、图片合理 | 固定小标题堆砌、重复解释、事实清单冒充人读文档 |
| 非 Story Spec | 不创建 Story 也通过专属 Hook | Story 场景只有两个空文件却通过 |
| 知识零激活 | constraints 正常，模式链 SKIP | 验证器强制至少一个 SDK 模式 |
| 知识激活 | 一个已确认非 SDK 模式或自包含 SDK 模式全链生效 | 未确认模式、目录中未激活文件影响 Spec/Plan |
| Plan 路径 | 已登记的安全路径等价类通过 | 已登记的绝对/盘符/UNC/`..`/symlink 越根类通过 |
| Plan 引用 | 正式 ID 精确唯一命中 | 共享常见 token 即通过，或重复 ID 不报歧义 |
| 自包含 | 仅 tracked tree 即可运行全部离线测试 | 依赖当前脏工作区的 `libs/`、test 或本地配置 |

每个新机械检查至少配一个有效正例和一个无效反例；禁止只添加专门打当前案例的负例。每个正式语义 case 必须存在 `truth/facts/<case>.yaml`；缺事实底册的 `pattern-image-review` 不能成为最终语义验收 case。

### 11.4 Clean tracked snapshot 与交付指纹

Gate 0 同时建立唯一机器真源 `delivery-closure.yaml`，明确整个仓库 tracked tree、额外运行依赖和唯一允许的生成输出路径；由它解析出带精确文件/hash 的 `delivery-closure.lock.json`。Fingerprint、tracked 审计、正式运行前后污染检查只能读取这份 lock，不允许各脚本自行维护“相关文件”列表。

候选提交必须把本轮实际需要的 Extension、测试、用例、CLI、运行时配置和依赖全部纳入同一不可变 tree。然后：

1. 从该 commit/tree 创建独立 clean snapshot；不从当前工作区复制 untracked 文件。
2. 审计 Manifest 所列路径均已 tracked，文件依赖真实存在，`framework/` 未改变。
3. 从 closure lock 计算 `delivery_fingerprint`；其中 tracked 部分绑定整个 candidate tree，额外依赖逐文件绑定，且明确包含正式 CLI、`test/story`、评价脚本/事实底册、配置、包清单和实际运行依赖，不能继续只摘要 `doc/extensions`。
4. 审计产物和脚本没有指回脏工作区的绝对路径。
5. 在 snapshot 内运行 `verification-map.yaml` 指定的完整命令集，并确认受保护路径没有被测试污染。
6. 产出 `clean-snapshot.json`：HEAD、tree、delivery fingerprint、工具链、输入夹具摘要、命令和退出码。

Clean snapshot 只证明**自包含与可复现**，不替代正式行为实跑。

### 11.5 正式 CLI 与内网复验

正式行为仍按 `test/story/TEST.md`：在真实当前工作区、正式 CLI、真实读模型流程中执行，不用 sandbox/worktree 结果冒充。

要求：

- 主工作区 HEAD、tree 和 `delivery_fingerprint` 必须与 clean snapshot 完全一致；
- 主工作区除 `delivery-closure.yaml` 精确列出的运行输出目录外必须整体 clean；禁止运行前遗留、历史或其它 `run_id` 的输出成为输入。同一 `run_id` 内按 phase provenance 新生成、登记并冻结的产物允许成为后续阶段输入；正式运行前后复核来源链。这样既不放行污染，也不破坏合法分段续跑。
- 当前用户已有改动必须先通过用户认可的非破坏方式保全或纳入候选，禁止用 reset/删除来伪造干净状态；条件不成立就不启动正式运行；
- 不预注入 `test/story`、历史输出或答案；
- 不套外层 timeout、pipe 或擅自 force-kill；
- 至少包含一条真实 DOCX import 路径，不能只预置 Markdown/SVG；
- 分段运行并保留原始事件、phase/worker 状态与最终报告；报告和独立语义回执都绑定 HEAD/tree/delivery fingerprint；合并回执时再次复算；
- 检查模型是否读取测试域或旧输出，污染即单独标记；
- 回放 C0 的匿名内网兼容案例，并验证 C1 能力矩阵。

最终报告分四轴，不互相抵消：

1. 执行完成度；
2. 产物机械完整性；
3. 产品语义质量；
4. 证据可信度/污染状态。

每个 `required_gate: 9` case 必须在 verification map 中声明唯一 `pass_predicate_ref`。角色谓词固定如下：

```text
P-SEMANTIC-FORMAL:
  execution_status == finished
  mechanical_verdict == pass
  semantic_verdict == pass
  overall_verdict == pass
  pollution == false
  candidate tree / delivery fingerprint: pre == report == post
  report_data + independent semantic receipt structurally valid
  all rubric observations have evidence
  extra_findings has no substantive defect

P-MECHANICAL-FORMAL:
  execution_status == finished
  mechanical_verdict == pass
  semantic_verdict == not_applicable（有结构化原因，不能是 pending）
  overall_verdict == pass
  pollution == false
  candidate tree / delivery fingerprint: pre == report == post
  mechanical case receipt structurally valid

P-C0-COMPAT / P-INTERNAL-COMPAT:
  execution_status == finished
  exact compatibility oracle == pass
  pollution == false
  candidate tree / delivery fingerprint: pre == receipt == post
  parent evidence（C0）或 internal receipt（internal-only）可解析
```

`stopped`、`force_killed`、污染、指纹漂移和 predicate 所需 receipt 缺失对所有角色都是失败；pending 对所有 required 字段都是失败。`report_data.json` 和完整 rubric 只对 `P-SEMANTIC-FORMAL` 强制，不能拿其缺失去否定一个合同明确为机械/兼容的 case，也不能用机械 case 冒充语义 PASS。

Gate 9 不是“一条 case 通过即可”：

- required cases 等于 `verification-map.yaml` 中 `required_gate: 9` 的精确集合；任一缺失、pending、污染或失败，Gate 9 整体失败。
- 每个 `semantic_formal` case 都必须有 facts，并逐条满足 `P-SEMANTIC-FORMAL`。
- 每个 `mechanical_formal` case 必须满足 `P-MECHANICAL-FORMAL`。
- 每个 `c0_compat_replay` case 都必须满足账本中的父版/候选 oracle。
- 每个 C1 invariant 至少被一个 `evidence_level: formal` 的 required case 覆盖；其中 INV-02～INV-07 和 INV-10 必须至少有 `semantic_formal` 覆盖，其余可由明确的 `mechanical_formal` 覆盖，不能只靠离线单测。
- 私有内网 case 若只验证兼容性，标为 `internal_compat_only`，不得冒充完整语义 case。

## 12. 分片实施与硬闸门

评审通过后按以下顺序实施。一个切片只修一个最早责任层；核心实施期间冻结产品语义 rubric、正式测试定义和 Framework。

### Gate 0：守恒基线冻结

产物：

- INV-01～INV-13 的评审结论；
- C0 逐项基线账本；无父版成功证据的维度明确归 C2；
- `verification-map.yaml` 与初始 `failpoint-catalog.yaml`；
- `delivery-closure.yaml`（唯一 include/output policy）及候选提交应包含的 tracked/依赖闭包；
- 本轮排除项确认。
- selector/逐章输入绑定旧实现的定向勘误，不改产品语义 rubric。

通过条件：每项既有能力和输入维度都有唯一 case/oracle/evidence 落点；不存在“用户说正常”被擅自扩写成未证明的父版能力；父提交没有被当成代码回滚方案。

### Gate 1：Story v5 输入/输出合同

修改范围：

- `story-sources.json`；
- `story-chapters.json` v5；
- source inventory helper；
- `story_flow.py`/模板的显式 placeholder marker；
- generated/author 区边界、`spec_shape` 与 numeric provenance 合同；
- 相应合同测试。

通过条件：verification map 中固定的标题/文本/目录/图片/路径正反例全部符合 oracle；selector、primary、whole 在运行合同中为零；现有 11 章、`spec_shape`、数值真源和 Human-First 字段守恒。

### Gate 2：原子 Scaffold 与迁移

修改范围：结构型 workspace marker、scaffold-owned 文件清单、事务发布、`--migrate`/`--rebuild`、旧登记表迁移、迁移报告和故障注入测试。

通过条件：`failpoint-catalog.yaml` 中每个 mutation/recovery 点逐一通过；可捕获失败保持旧 ready，崩溃态可识别且不可接受；Flow 侧车和人工正文无静默丢失。

### Gate 3：成对 Build 与共享 Completion

修改范围：`story-build.mjs`、canonical build ID、事务提交点、completion inspector、Spec Hook、`merge-story.mjs`、`story.js` 部署适配数据契约、`story_flow.py` 归档 receipt、Review round-trip adapter、Skill 说明，以及三种 lifecycle profile 测试。

通过条件：空产物/不同 build ID/损坏人工区在当前 profile 失败；confirmed 旧状态不能冒充新 build；archive attempt 的准备、每附件上传、receipt 持久化、uploaded-unbound 续接、flow 绑定、补偿及按 `backup_ref` restore 均有 failpoint/幂等正反例；archived snapshot 不被后续 Spec 或人工 Review 区变化误伤；真实 adapter round-trip 正反例通过；合法 pair 通过事务提交点发布；非 Story Spec 不受影响。

### Gate 4：Manifest 单一激活与适配校验

修改范围：active-knowledge helper、knowledge frontmatter 分类、Manifest、通用 ADAPTATION registry、patterns/constraints README、verify-adaptation、动态共享 hook/`pre_verifier.mjs`、各阶段 overlay、Story `SKILL.md`/rules/reference 的 project-fact resolver，以及知识测试夹具。

通过条件：三种 Plan 产物形状均通过专属 case；README/catalog 不被误算 active；pattern/constraint/project-fact 分类闭合；inactive case 的 hook prompt、standalone Story 读取清单、catalog 和 project_knowledge 均无该 ID；active 未确认在注入前 fail；Manifest 解析错误不冒充空集；非 SDK 和自包含 SDK 模式均有正例；constraint rule ID 重复/跨域错挂失败，所有类别和所有 Story 入口都不绕过 Manifest。

### Gate 5：Plan 机械边界

修改范围：Plan probe/on-context/post-check、模式/约束 overlay 和对应测试。

通过条件：删除 UI Kit/目录首段假设；verification map 中所有路径等价类符合 oracle；正式 ID 精确全局唯一；token 假命中失败；canonical `knowledge_ref` 唯一；Spec 候选、Plan 处置与 `project_knowledge` 集合守恒。

### Gate 6：实例泄漏清理与文档同步

修改范围：Extension 规则、README、codebase facts、Story Skill 说明和测试域文档中受合同变化影响的事实。

通过条件：Extension 运行时不含 AR 测试 ID、Mock 标题、未提交 HAR 事实或 WalletMain/UI Kit 强制前提；`framework/` diff 为零。

### Gate 7：离线回归

通过条件：`verification-map.yaml` 列出的固定命令和完整 Story 离线套件全部 exit 0；每项新门禁有正反例；S/R rubric 未被修改来换绿。

### Gate 8：Clean snapshot

通过条件：同一最终 tree 在 tracked-only 环境全绿；closure lock 精确覆盖 Manifest、测试、CLI、事实底册、配置和依赖；生成可审计摘要；不借用当前工作区 untracked 内容。

### Gate 9：正式 CLI 与内网回放

通过条件：Gate 8 的同一最终 tree/delivery fingerprint 上，`required_gate: 9` 的精确 case 集全部满足 §11.5；C0 回放符合各自 oracle，每个 C1 invariant 有 formal 覆盖。只“形成报告”或只通过一条 case 不算通过。

每个 Gate 完成后先报告证据再进入下一 Gate；测试中的新发现记录到报告，不在同一次运行中边测边改以制造“全绿”。后续切片只要修改了某 Gate 的输入文件、依赖或 oracle，该 Gate 及所有受影响下游证据立即失效并重跑；Gate 7、8、9 必须绑定同一最终不可变 tree。

## 13. 完成定义

只有同时满足以下条件，才可以宣告本次重大问题正向闭环：

1. **兼容性**：C0 账本中的父提交可用维度和匿名内网案例逐项符合候选 oracle。
2. **能力守恒**：INV-01～INV-13 全部在 verification map 中有通过证据，无 Human-First、知识链或生命周期回退。
3. **原子性**：failpoint catalog 全部通过；scaffold/build 半状态不可接受且可恢复，不损坏 Flow 侧车或人工内容。
4. **完成态**：归档前只接受当前同 build pair；归档后只接受可复算的 archived snapshot，合法后续 Spec 漂移不反向破坏历史 Story。
5. **知识可信**：只有 Manifest 激活且已确认、自包含的知识能影响运行；零激活合法。
6. **Plan 通用性**：无实例目录、UI Kit、SDK 数量或 token 碰撞假设。
7. **自包含**：候选提交在 tracked-only snapshot 中可复现。
8. **正式证据**：真实 CLI、真实当前工作区满足 §11.5 全部 PASS 谓词，而不只是四轴字段存在。
9. **内网复验**：原先正常的代表性材料恢复通过，且新能力仍生效。
10. **边界合规**：Framework 未改，本轮排除议题未夹带。

## 14. 请评审的五个决策点

1. **双基线原则**：是否认可 `0c8ab1d` 只作为输入兼容下限、`aad670c` 作为能力保留下限，不采用整体回退。
2. **Story v5**：是否认可彻底删除 selector/primary 输入合同，改为 source inventory + 模型语义归章 + 输出严格校验，不保留双轨兼容；并按归档前当前态/归档后快照态分别验收。
3. **知识激活**：是否认可 Manifest 为唯一激活真源；当前两份未确认 Demo 默认退出 active set，待证据和依赖自包含后再原子激活。
4. **Plan 最小修复**：是否认可本轮只做精确正式 ID、安全项目相对路径和清晰的机械/语义分界，不夹带新的通用 typed-reference 或可观测性 DSL。
5. **验收顺序**：是否认可 Gate 0～9 共十个 Gate（一个基线 Gate + 九个实施/验收 Gate），任何前置未通过不得用后置结果冲抵，后续改动会使相关前序证据失效。

评审通过前，本文只是一份执行合同草案，不据此修改任何实现。
