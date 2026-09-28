# `step-02-author-review-inputs`：作者输入与审查职责收敛

## 目标结果

02.4-02 分册落地：R09 编排协议只有 `story-sources.parseTemplate` 一份解析，作者侧与审查侧同判坏件；R21 四个可选字段（`structures` / `children` / `related` / `replaced_by`）的形状与省略条件写在 `renderTemplate` 起头文件头部，稳定读者问题（合同 `chapters[].questions`）在编排前有送达位置；R10 作者包不内联全部源图，逐图只给身份、主题、`文件:行范围`；R12 一张图一条任务，`items` / 单数 `path` 旧形态回退退场；R20 审查任务书不再维护第二套语义方法与结果 schema，独有的有效问题并入 overlay；R02 按人数选图与 R14 字数/项数/绝对一次的配额退出。**不改** structures 支持的图种集合、不恢复 form.note、不新增作者「已读」字段。

**本步实现已由执行者会话在 loop 建立前提交：`5203ca30`，交回 `../../steps/02.4-02-交回.md`。** 本步不重做实现：executor 加入后完成实施前审视（核交回与分册逐项对应、四道门在当前 HEAD 仍绿），直接以该提交送审。评审要求返修时另起提交，与 01 的 `f1f83c20` 同法；获批后 `step_completed --commit <最终提交>`。

## 前置与依赖

- 输入产物：01 之后的 HEAD（`sourceInventory` / `prepare` 九档 / `hasTicket` 已在）；`5203ca30` 的 diff 与交回。
- 真实依赖：无（与 01 无产物耦合）。
- 执行顺序：01 之后。
- 就绪程度：实现已提交，待评审。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`；行号按 HEAD `5203ca30`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md`、`test/story/AGENTS.md`、`test/story/TEST.md` §7、`test/story/plan/2026-09-07-新需求四项/99-执行者会话交接.md` §1/§5 | 共享已加载 | 角色边界、四道门、交付面通用性、编码/heredoc 坑 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.4-旧机制退场清理.md` §1/§4/§6/§7/§9 | 共享已加载 | 三条清理依据、执行者边界、规模口径、评审已并入 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.4-02-作者输入与审查职责收敛.md` 全文 | 本步新增 | 本步全部合同：§2 逐项边界与完成条件、§3.0 四字段表（形状须与 `story-sources.mjs` 一致）、§3.1–§3.4 分工、§4 验证 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.4-02-交回.md` | 本步新增 | 执行者声称做了什么、测试怎么迁、规模去向——评审逐项对 diff |
| `doc/extensions/skills/story/scripts/core/story-sources.mjs` `parseTemplate`、`flatSections` :382、`effectiveDispositions` :417、`placements`（已 export）、`relatedTargets` :526、`declarationProblems` :556、`DIAGRAM_TYPES`（已 export）、`templateReadable` :713 | 本步新增 | R09 唯一解析处；四字段的真实形状；图种集合的唯一来源 |
| `doc/extensions/skills/story/scripts/core/story-build.mjs` `readTemplate` :686、`templateSkeleton` :717、`renderTemplate` :747、`templateFieldGuide`、`afterSpec` :820、`assemblyInputs` :3076 | 本步新增 | 起头文件头部（R21 落点）；`assemblyInputs` 接住解析错误（交回记的基线缺陷修法）；after-spec INPUT 指向 questions |
| `doc/extensions/hooks/shared/reader-review-task.mjs` `sourceCatalogue` :46、`readerReviewTask` :94 | 本步新增 | 审查侧复用 `parseTemplate` + `placements`；坏编排写进 problems 而不是「没有位置」；六问与结果 schema 已退 |
| `doc/extensions/rules/spec-rules.overlay.yaml` `story_reader_review`（约 :52–:90） | 本步新增 | R20 的唯一规则源：六问并入、不按参与方数量要求图种 |
| `doc/extensions/hooks/spec/author.mjs` `imageSection` :158、`diagramSection` :225、`taskPackage` :314 | 本步新增 | R10/R12：逐图坐标、一图一任务、旧形态回退退场、坏清单报错 |
| `doc/extensions/skills/story/phases/story-write.md` 第二步 :71–:113、`## 怎么写一章` :211、`## 什么内容用什么形态` :269（图表 :310–:320）、`## 别写成长文` :370 | 本步新增 | R02/R14/R21 的作者面改动；erDiagram 那行须说明「不在 structures 声明集合」 |
| `doc/extensions/skills/story/contracts/story-chapters.json` `chapters[].questions` | 本步新增 | R21 的稳定读者目标真源，不复制到别处 |
| `test/story/tests/test_author_task_package.py`、`test_entry_switch.py`、`test_final_check.py`、`test_verifier_report_protocol.py`、`test_story_template.py` | 本步新增 | 迁移与新增用例；评审逐条问「守的是什么行为」 |
| `test/story/regression/mechanism-budget.yaml`、`test_mechanism_budget.measure()` | 条件：closeout 记规模 | 计数口径；只测量 |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：`story-sources.mjs`、`story-build.mjs`、`reader-review-task.mjs`、`author.mjs`、`spec-rules.overlay.yaml`、`phases/story-write.md`、五份测试。
- 排除：附录/图片判据（step-03）、知识与验收桥接（step-04）、R18 残料与 FEATURE 文档（step-05）；`DIAGRAM_TYPES` 集合本身；form.note。
- 公共规则：四道门见 `TEST.md` §7；注释与提示词按 `AGENTS.md` §5.3。

## 关键决定

- 已确定（分册 §3.0）：四字段全部保留，说明只在起头文件头部一处，用行内代码不加第二个 `json` 围栏，可选字段不预填。
- 已确定（分册 §3.3）：structures 的图只支持 `sequenceDiagram` / `flowchart` / `stateDiagram-v2`，作者示例统一 `stateDiagram-v2`，erDiagram 正文合法但不宣称受 structures 保护；集合由 `DIAGRAM_TYPES` 一处提供。
- 已确定（分册 §3.4）：overlay 是唯一审查方法源；任务书只装本次对象与读法。
- 设计任务：无。

## 验收

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 同一份坏围栏 / 坏 JSON 的 `story-template.md` | 作者侧（`assemblyInputs` / `prepare`）报「json 块解析不了」而不是类型错误；审查侧任务书写明「编排读不出来」而不是逐行「没有位置」 | 用例 `test_a_broken_plan_is_named_on_the_review_side_too` 及作者侧对应用例 | 本步自动检查 |
| 真实 `renderTemplate` 起头文件 | 四字段的形状/用途/省略条件在头部；恰好一个 `json` 围栏；`prepare` 能解析它；图种列表与 `DIAGRAM_TYPES` 同源且 erDiagram 不在生产说明里 | `test_the_starter_still_has_exactly_one_json_block` 等新增用例 | 本步自动检查 |
| 按头部说明真填一份含四字段的中性编排 | 解析 → 视图 → 局部检查全链通过；children 一层、related 指向存在项、replaced_by 不自指 | 交回列的端到端新增用例 | 本步自动检查 |
| materials 里一张图两个登记路径 / 坏清单 / `{"materials": [...]}` 真形态 | 只一条任务与命令，其余路径为别名；坏清单明确报错；三处夹具已改真形态 | `test_author_task_package.py` | 本步自动检查 |
| 作者包的上游图节 | 逐图身份、主题、`文件:行范围`，无围栏正文；`diagramsOf` 仍能精确定位 | 同上 | 本步自动检查 |
| 全仓搜「三个以上」「两个以内」「百字」「一百六十」「1–3 个短项」 | 交付面零命中；overlay 写明不按参与方数量要求图种 | grep + 人读 | 本步自动检查 |
| `sources --stage after-spec` 输出与 `story-write` 第二步 | 各有一句指向合同 `chapters[].questions` | 用例 + 人读 | 本步自动检查 |
| 四道门与规模 | 离线全量全绿；70 条形态 FAIL 0；adapt-scan 退出 0；framework 0 行；`measure()` 前后值与交回表一致 | `TEST.md` §7 | 本步自动检查 |

## 提交边界

- 纳入：`5203ca30`（已提交）；返修若有，另起提交。
- 排除：本目录文件；`test/story/AGENTS.md` 的用户未提交改动。
- 完成条件：验收全过；reviewer 写 closeout 并 `approved_for_commit`；executor `step_completed --commit <最终 hash>`。

## 停止条件

- 分册 §3.0 的字段形状与 `story-sources.mjs` 实际读法不一致时，先改分册再改实现，`executor_question` 交 reviewer。
- 发现要改 `DIAGRAM_TYPES` 集合或恢复 form.note 才能满足验收时停下。
