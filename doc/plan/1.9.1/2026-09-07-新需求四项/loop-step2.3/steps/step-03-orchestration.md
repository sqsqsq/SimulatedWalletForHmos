# `step-03-orchestration`：整篇编排的合同与函数（3a，不切作者入口）

> 2026-09-10 按 executor 实施前审视的提议、reviewer 裁决拆为两笔（见 `reviews/step-03-orchestration-review.md` seq 32 答复）。本步是 3a；入口切换与 v3 退出在 [step-03b-entry-switch](step-03b-entry-switch.md)。原步骤文件的「A：改 skeleton、v3 仍在」那条拆法作废：`skeleton` 是十份草稿的生产者，它一按 template 铺内容，作者拿到的就是新链，而 v3 指导区仍在同一批文件里刷新——正是 02 §6「不兼容两条正式写作链」要防的形态。

## 目标结果

02 分册里**新增的解析与装配**全部落地并有函数级/命令级证据，`skeleton` / `chapter` / `prepare` 与六份提示词一行不动，v3 仍是唯一正式写作链：

1. `story-build sources --stage after-spec`：保留未变的原始来源索引、加入 SPEC 单元、列出相对初筛新增/变更/失效的来源引用；template 不存在时创建十章 body 起点（`content`/`form` 留空待填、`basis` 由脚本填），selection 里有明确 `chapters` 的单元由脚本预填进对应章 `body.sources`，默认 keep 未归章的只进公共参考索引；已存在的 template 不整份重写，新增来源与待处理版本通过输出送达（02 §1、§2）。
2. `story-template.md` 合同的读写：一个 JSON 块；字段约定按 02 §2；「template 可读」与「template 可装配」两条谓词按 02 §5 表逐字段实现（可装配包含 `selection/index/basis 为当前版本`，覆盖语义不在内）。
3. 「有效取舍只按一条规则计算」的合并函数（02 §2 末段：`template.source_changes` > `selection.items` > 默认 keep；omit 与显式 sources 并存报合同冲突；replaced_by 禁自指与循环）。
4. structures 三种声明的生成与检查函数（02 §2.2：table 表头/分隔行/占位，diagram 围栏与类型首行，image 从 `source-index.images` 解析真实图片；检查复用章节合同已有的表头规范化、锚列与 named 包含匹配；title 为空作用整章，title 非空章内唯一命中，零/多命中报候选）。
5. 材料视图的装配函数按 02 §3.1 规则分配：只有一个编排项引用的全文进所属章、两个及以上引用的全文只进 shared 一份、其余只列索引行、未预分配可从完整来源目录补读；`chapterView`/`sharedView` 已在 step-02 导出，本步补分配逻辑与 related 目标章路径的解析（有草稿给草稿路径，没有给该章视图路径）。

**不做**：`skeleton`、`chapter`、`prepare` 的任何改动；`story-chapters.json` 删 `context_chapters`；六份提示词接线；总方案 §6 的退出项。这些全部归 3b。

## 前置与依赖

- 输入产物：step-02 的 `story-sources.mjs`、`sources --stage before-spec`、source-index / selection / `basis` 合同（`9b500d28`）。
- 真实依赖：step-02。
- 执行顺序：无。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md`、`test/story/AGENTS.md`、`test/story/TEST.md` §7、`99-执行者会话交接.md` §1/§5 | 共享已加载 | 同 step-01 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-Story写作流程重设计.md` §1、§3、§4、§7 | 共享已加载 | 角色边界、规模口径 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-02-整篇编排与成文.md` §1、§2（含 §2.1、§2.2）、§3.1、§5 谓词表 | 本步新增 | 本步全部合同 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-03-核对退出与验收.md` §2、§3 | 本步新增 | 最终 check 与 verifier 是 step-04 的活，本步产出的 template / 有效取舍形状要让它们能接 |
| `doc/extensions/skills/story/scripts/core/story-build.mjs` `cmdSources` 一带（step-02 新增）、:688–735（`specText`/`specSection`/`pipeTables`/`isPlaceholderRow`）、:1220（`table_anchor` 与表头规范化）、`chapterProblems` | 本步新增 | after-spec 挂在 `cmdSources`；Spec 可用性谓词只复用这四个函数；表头/锚列复用 |
| `doc/extensions/skills/story/scripts/core/story-sources.mjs` | 本步新增 | 新函数放这里；只解析与装配 |
| `doc/extensions/skills/story/contracts/story-chapters.json` :443（`form_note`：slots 与 named 包含匹配）、章 ID | 本步新增 | structures 定位复用；本步**不**删 `context_chapters` |
| `test/story/golden/story-template-金样-AR90006.md`、`…-说明.md`、`…-source-index.json`、`…-source-selection.json`、`test/story/fixtures/golden/AR90006-template/spec/` | 本步新增 | template 形状对照与 after-spec 的输入夹具（含 Spec 快照）；不注入被测作者 |
| `test/story/tests/test_source_index.py` | 本步新增 | 复用 `WorkspaceCase` 装配方式 |
| `test/story/regression/mechanism-budget.yaml`、`check_failure_modes.py`、`TEST.md` §7.2–7.3 | 条件：规模记录、改完注释后 | 同前 |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：`story-sources.mjs`（合并规则、structures 生成/检查、视图分配、related 路径解析）；`story-build.mjs` 的 `cmdSources` after-spec 分支与 template 读写/谓词；对应测试（可续写 `test_source_index.py` 或新建一份编排合同测试文件）。
- 排除：`skeleton` / `chapter` / `prepare`；提示词；合同删字段；退出项；knowledge 协议；`framework/`。
- 公共规则：四道门见 `TEST.md` §7；注释按 `AGENTS.md` §5.3。

## 关键决定

- 已确定：02 §2「编排调整规则」、§2 末段合并优先级、§2.2 structures 三种与定位规则、§3.1 分配规则、§5 六条谓词的字段级定义。
- 已确定（reviewer 裁决）：拆两笔的边界是「新增的合同与函数」对「入口切换与退出」；3a 落地时 `skeleton`/`chapter`/`prepare` 字节不变，v3 唯一。
- 已确定：本步 `sources --stage after-spec` 是一个存在但尚未被流程路由指向的命令（`status`/SKILL 仍走 v3），这是 3a→3b 之间明确的中间态，不发布、不跑效果比较；3b 收口时 03 §5「不存在新代码搭旧命令的中间态」必须成立。
- 设计任务：无。函数切分、测试文件名由 executor 定。

## 验收

「同类对象 ≥ 2」的反例先列进表再动手（executor 自己提的，采纳）。

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 金样夹具 + Spec 快照，跑 `sources --stage after-spec`（template 不存在） | SPEC 单元进索引且 `kind: derived`；十章 body 起点落盘、`basis` 由脚本填；selection 有 `chapters` 的单元已预填进对应章 `body.sources`；默认 keep 未归章的不在任何章的 sources 里；再次运行不整份重写（02 §7 条 1、3） | 新增用例 | 本步自动检查 |
| 初筛之后一个原始来源变了、Spec 也新加了一节 | after-spec 输出列出新增（SPEC）、变更（该源）与失效引用；来源变更仍走 step-02 的 basis 判据，不重编未变来源 | 新增用例 | 本步自动检查 |
| 有效取舍合并：同一单元 selection 标 omit、template `source_changes` 改 keep 并声明位置 → 采用；selection 标 keep、template 无条目 → 继承 selection 的 chapters；omit 与显式 sources 并存 → 报合同冲突；replaced_by 自指 / A→B→A | 前两种通过并给出正确归属；后两种被拒并报坐标 | 新增用例 | 本步自动检查 |
| **同一单元被两个编排项显式引用** vs 只被一个引用 vs 无人引用但初筛暂定归章 | 分别落 shared 全文（只一份）/ 所属章全文 / 索引行；分配函数输出可断言（02 §3.1） | 新增用例 | 本步自动检查 |
| structures：table 声明 → 生成表头与分隔行；diagram 三种 type → 围栏与类型首行；image → 从 `images` 解析真实路径；type 不在三种内 / columns 空 / image 不存在 → 报编排位置 | 生成物与报错可断言 | 新增用例 | 本步自动检查 |
| structures 定位：title 为空 → 整章任意子节命中即可；title 非空且**章内两处同名标题** → 报多命中与候选，不取第一个；零命中 → 报候选；另一章同形结构不算 | 检查函数返回可断言 | 新增用例 | 本步自动检查 |
| template 可读 / 可装配两条谓词 | 缺章、key 重复、related 目标不存在、content 有待填占位、basis 与当前不一致，各自落到正确谓词并报坐标 | 新增用例 | 本步自动检查 |
| related 目标章路径解析：**一个目标有草稿、一个没有** | 前者给草稿路径，后者明确缺失并给该章视图路径（02 §5） | 新增用例 | 本步自动检查 |
| 入口未切 | `skeleton` / `chapter` / `prepare` 三个函数与六份提示词 diff 为零；`test_writing_flow.py` 全绿不改 | `git diff` + 既有用例 | 本步自动检查 |
| 过拟合与规模 | 新代码零处 AR90006 专名与数字；`check_failure_modes` FAIL 0；`measure()` 前后值与逐函数增删；本步仍为净增，如实记 | `TEST.md` §7.2–7.3 | 本步自动检查 |
| 四道门 | 同 step-02 | `TEST.md` §7 | 本步自动检查 |

## 提交边界

- 纳入：`story-sources.mjs`、`story-build.mjs`、测试文件。
- 排除：他人未提交改动；golden 正本；`98` / 本目录。
- 完成条件：验收全过；送审说明按 02 §6 表以外的「函数 → 合同条款」分组列 diff；`approved_for_commit` 后提交，随后 `advance` 到 step-03b。

## 停止条件

- 实现 after-spec 或谓词时发现必须动 `skeleton`/`prepare` 才能验证 → 停下提问，不越界。
- 02 分册内部矛盾或与 step-02 合同冲突 → `executor_question`。
