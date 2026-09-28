# init 流程契约化 · 方案

> 问题与根因见 [00-问题分析.md](00-问题分析.md)。本文含：用户原始设想（逐字）、
> 客观审查结论、修正后的定稿设计、待用户裁决项。

## 一、原始设想（用户原话，2026-08-13）

> 3.1 为 story 构建一个契约文件，用来记录每一步的输入、输出、交互决策（人或AI）
>
> 3.2 第一步 story init 指令，完成 RR+SR+AR 的资料拉取与初步解读，这里是否考虑生成一个
> 临时文档，比如叫 AR/init-1.md，根据当前的信息，对需求做初步分析：需求概览、本部件视角
> 理解、本AR视角理解（如果原始AR/design.md有相关说明的话），本AR视角看，待实现的功能，
> 是否需要拆分（比如这个需求，需要在本部件内跨多个业务模块；超长业务流程；大颗粒特性
> 需要分层构建等），并可以提供具体的拆分建议
>
> 3.3 第二步 让用户选择：1）在 inbox/ 补充资料后，并继续（这个选项，并不是用户先选择，
> 而是用户先去 inbox/ 下放完资料，再选择。如果用户选择该选项，检查 inbox/ 下是否有文件，
> 没有重新提示用户，有就继续）。2）是否拆分需求，如选择此选项，下一步立即给出建议选项
> （具体拆分场景，并允许用户自己描述等）。3）直接进入 spec
>
> 3.4 第三步 1）如果用户选择了输入 inbox，则重新根据输入，参考第一步 生成一个临时文档，
> 比如叫 AR/init-2.md，重新进行需求初步分析 2) 提供选项是否拆分 AR 或直接进入 spec
>
> 3.5 第四步 全部前置输入、输出、决策已完成，开始生成 AR/design.md 并自动进入 spec

## 二、审查结论（客观）

**方向正确，可行，且不是新发明**——它就是框架 spec/plan 四重闭环（落盘产物 + 机械校验 +
人工确认 + 决策留痕）的微缩版，补上了 story init 作为全链路唯一无结构段的缺口：

| 设想要素 | 解决的问题 | 与框架机制的对应 |
|---|---|---|
| 契约文件（3.1） | P4 决策无落点、P6 无法机械校验、跳步不可拦 | trace.json / receipt |
| init 分析文档（3.2） | P4 报告即席化；决策依据可审计、可恢复 | 阶段交付件（如 spec.md 之于 spec.freeze） |
| 固定选择步骤（3.3） | P1 孤儿章节——补料成为**流程内选项**而非模型联想；inbox 非空校验是确定动作 | registry 编号确认点 |
| 循环重析（3.4） | 补料后的收敛语义 | 修正后重跑落点层门禁 |
| 决策齐备才生成+自动进 spec（3.5） | 交互收敛——进 spec 的授权就是第二步的选择本身，不再另停 | `spec.freeze` 冻结即授权 |

**优于此前设计的一点要点名**：旧流程是「先生成完整 design.md 草稿 → 关卡 → 拆分/补料则
重生成」。新流程把 draft-first 用在**对的产物**上——补料/拆分决策需要的是「分析 + 候选」，
不是完整提取件；旧流程在拆分场景下先生成的完整草稿必然报废。新流程 design.md 只生成一次、
生成时范围已定。

### 三处要修正（不影响方向）

1. **`init-1.md` / `init-2.md` 编号累积**。补料可以多批（材料分两次到），编号文件会长成
   init-3、init-4……哪份是现行版说不清，与「每个事实只有一个权威落点」冲突。
   修正：**单文件 `AR/init-analysis.md` 每轮重生成**（收敛语义与 inbox 不变量同构），
   轮次历史记在契约文件里，旧版进 `.backup/`——历史可查，现行唯一。
2. **分析文档与 design.md 的职责边界要划死**。分析文档的「需求概览/本部件理解/待实现
   功能」与 design.md 五段结构大面积重叠，不划界就是同一事实两个落点。
   修正：`init-analysis.md` 是**决策支撑件**（材料现状与缺口、复杂度信号、拆分候选、
   初步理解摘要），**非交付件**：/spec 不读它、归档不含它、生成 design.md 不以它为源
   （四源不变）。它的唯一读者是关卡上做决策的人（或代答的 AI）。
3. **第三步的选项要构成闭环**。3.4 写的是「拆分或直接进 spec」，少了「继续补料」——
   材料分批到达时流程会卡死。修正：每轮关卡选项恒为**同一组三选**（补料 / 拆分 / 进 spec），
   终止条件只有一个：选「进 spec」。

## 三、定稿设计

### 3.1 流程（四步一循环）

```text
S1  init（脚本）：拉取 RR/SR/AR 材料 + 建 inbox/
S2  初析（AI）：无条件列 inbox → 有未导入材料先导入（含 UX 图登记）→
    生成/重生成 AR/init-analysis.md → 写契约 round 记录
S3  关卡（人或 AI 按 transition_policy）：呈现 init-analysis 摘要，三选一——
      1=补充材料后继续   → 校验 inbox 有新文件（无则重新提示）→ 回 S2（round+1）
      2=拆分需求         → 子菜单：候选方案（含拆分依据/每份范围/推荐）+ 自述 → 记契约 → 回 S3
      3=进入 /spec       → 记契约，进 S4
S4  收口（AI）：按已定范围生成 AR/design.md（四源，一次成型）→ 契约 status=complete
    → 自动进入 /spec（授权即 S3 的选择 3，不再另停）
```

- S2 的「列 inbox」是流程固定动作（一条 ls，空则过），不再依赖模型联想——P1 根治点；
- S3 的停/走按既有「交互关卡语义」章的 `transition_policy` 分档执行（P2 修复保留）：
  `manual` 停等；授权态 AI 选推荐项并在契约里留 `by:"ai"` + 依据原话；
- 拆分范围文字的权威落点仍是 design.md §1.2（S4 写入）；spec 阶段照旧登记
  `decisions.json` settled 议题——契约只记「谁、何时、依据、选了哪项」元数据，不复制正文。

### 3.2 契约文件：`AR/story-flow.json`

```json
{
  "schema": 1,
  "feature": "AR90006",
  "status": "in_progress",
  "rounds": [
    {
      "round": 1,
      "imported": ["inbox 本轮导入的文件名（无则空数组）"],
      "analysis": "AR/init-analysis.md",
      "inputs": {"RR/prd.md": "sha256:…", "SR/design.md": "sha256:…",
                 "AR/design.md": "sha256:…", "AR/upstream.md": null},
      "decision": {
        "gate": "material_scope",
        "chosen": "supplement | split | proceed",
        "by": "human | ai",
        "policy": "manual | batch_authorized | goal_mode",
        "basis": "用户原话，或授权原话 + 推荐理由",
        "at": "ISO 时间"
      }
    }
  ],
  "split": {"decided": "none | split", "settled_round": 2,
            "scope_text": "定案的范围文字（decided=split 时必填）"},
  "design_generated_at": null
}
```

字段即审计：每轮读了什么（inputs 哈希）、导入了什么、谁在什么依据下选了什么。
`by:"ai"` 必须带 `policy` 与 `basis`——代答无依据即契约不完整。

`split.scope_text` 存的是 S3 定案的**范围文字本身**：S3 定案到 S4 写入 design.md §1.2
之间隔着一步，文字只留在对话里的话，会话一断定案就丢了。S4 从契约抄进 §1.2——
生成后 §1.2 是权威，契约转为历史记录（记录当时的输入），不构成双落点。

### 3.3 机械校验（三道，谁的活谁干）

| 校验点 | 执行方 | 判据 |
|---|---|---|
| 契约完整性 + 防跳步 | **只有一处：`hooks/spec/post_check.mjs`**（增 `storyFlowProblems`） | `AR/story-flow.json` 存在时校验：`status=complete`；每轮 decision 齐备（chosen ∈ 枚举）；`by:"ai"` 必带 policy+basis；complete 时末轮=proceed 且 design_generated_at 非空；`decided=split` 时 scope_text 非空。任一不满足 → BLOCKER「回 /story」。**文件不存在则不管**（未走 story 的 feature 不受影响） |
| 写入即时自查 | AI（SKILL「写入义务」规定，零新脚本） | 每次写/改契约后立即 `node -e "JSON.parse(require('fs').readFileSync('<路径>','utf-8'))"` 确认 JSON 合法——坏 JSON 若拖到 spec 闭环才被 post_check 发现，返工整个阶段 |
| 规约防漂移 | `test/story/tests/`（机械测试） | SKILL.md 流程链含 S1–S4；生成输入仍为四源且不含 inbox；关卡三选项与契约 chosen 枚举一致；post_check 正反例夹具（坏契约被拦 / 好契约放行 / 无契约不受影响） |

> 校验逻辑**不落 story 侧脚本**（曾考虑「新增轻量 check 或并入 import_sources」，与
> §3.5「不改数据层脚本」矛盾，弃）：判据只写一处，story 侧的即时性由 AI 自查补足。

### 3.4 SKILL.md 改动面

- 「初始化」章：路由改为 S1→S2→S3→S4 链条，每步一句话 + 指向对应章；
- 「导入上游材料」章：去掉「何时用」触发句式，改为 S2 的固定子步骤 + 关卡补料后的重入口；
- 新增「初析与流程契约」章：init-analysis.md 的五节结构（需求概览 / 本部件视角 /
  本 AR 视角 / 待实现功能清单 / 拆分评估与候选）+ story-flow.json 的写法与字段义务；
- 「材料与范围确认关卡」章：报告改为「呈现 init-analysis 摘要」，选项固定三选，
  选项行为由契约状态驱动；「已授权时怎么走」保留；
- 「生成design.md」章：输入保持四源（五源补丁已随 2026-08-12 20:05 快照回退，无需再改），
  补「不直接读 inbox」边界声明，触发条件改为「仅由 S4 进入」；
- 「产物定位」表：补 `AR/init-analysis.md`（决策支撑件，非交付件）与
  `AR/story-flow.json`（流程契约）两行。

### 3.5 本轮不做

- 不改 story.js / token.js / import_sources.py（数据层与转换器无缺陷；契约由 AI 写、
  脚本只校验——判断留 AI，执行归脚本）；
- 不动 harness 种子机制与只读位清理（已验证）；
- 不改框架（`framework/` 只读红线）。

## 四、裁决记录

| 项 | 裁决（用户，2026-08-13） | 结果 |
|---|---|---|
| 分析文档形态 | **单文件收敛** | `AR/init-analysis.md` 每轮重生成，轮次历史记契约，旧版进 `.backup/` |
| 防跳步钩子 | **要** | spec post_check 见 `story-flow.json` 存在且未 `complete` → BLOCKER；无契约文件的 feature 不受影响 |

本方案定稿，待用户授权后按 [04-总体执行计划.md](04-总体执行计划.md) 实施。
