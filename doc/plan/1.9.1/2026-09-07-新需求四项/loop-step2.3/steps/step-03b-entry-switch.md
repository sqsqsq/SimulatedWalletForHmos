# `step-03b-entry-switch`：作者入口切换与 v3 作者链退出（3b）

> 由 step-03 拆出（reviewer 2026-09-10 裁决，见 `reviews/step-03-orchestration-review.md` seq 32 答复）。3a 交付合同与函数，本步接线并退出旧链；落地那一刻只剩一条正式写作链。

## 目标结果

02 分册剩余部分落地：`skeleton` 改为消费索引 + template，成为唯一的正式视图写入口（章文件 / shared.md 按 3a 的分配函数）并按编排铺草稿标题与 structures 种子，已有草稿绝不重播种，编排改变后只列来源分配 / 采纳 / structures 三类差异；`chapter` 加原合同必要小节 + 已声明 structures 定位检查（复用 3a 函数），未声明的建议标题不拦；`prepare` 改为 NEXT/INPUT/RESULT 短输出、按 02 §5 状态表与六条谓词派生下一动作、`related` 解析到目标章草稿路径；`story_flow.py` 的 Spec 内接续与 complete 后动作文案（不起 Node）；02 §6 接线表六份文件逐行保留/改写/删除；`story-chapters.json` 删 `context_chapters` 字段与说明键；总方案 §6 列到「02」的旧职责全部退出（`guidanceRows` / `relatedChapters` / `guidanceSpan` / `putGuidance` / `stripGuidanceZone` / `quoteGuidance` / `prepareNext` / `prepareAfterWrite` / `wholePassOutput` / story-write 旧主干）。本步之后不存在两条正式写作链，也不存在「新代码搭旧命令」的中间态。

## 前置与依赖

- 输入产物：3a 的 after-spec、template 读写与谓词、合并函数、structures 生成/检查、视图分配、related 路径解析。
- 真实依赖：step-03（3a）。
- 执行顺序：无。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md`、`test/story/AGENTS.md`、`test/story/TEST.md` §7、`99-执行者会话交接.md` §1/§5 | 共享已加载 | 同 step-01 |
| `02.3-Story写作流程重设计.md` §6、§7 | 共享已加载 | 退出清单与时点；本步应出现净退出量 |
| `02.3-02-整篇编排与成文.md` §3、§4、§5、§6、§7 | 共享已加载（3a 已读） | 视图与草稿、chapter、prepare 输出与状态表、提示词接线表与必删清单、十条完成条件 |
| `02.3-03-核对退出与验收.md` §5、§6 | 本步新增 | 退出核对清单本步就要满足；确定性验收表的动态编排 / 输入输出分离 / 正常成文 / 输出与命令四行 |
| `story-build.mjs` :585（`guidanceInputs`）、:1119（`chapterProblems`）、:2414（`chapterDraft`）、:2468–2550（指导区）、:2729（`refreshGuidance`）、`cmdSkeleton`、`wholePassOutput`、`prepareNext`、`cmdPrepare`、`cmdChapter`（行号以当前 HEAD 为准） | 本步新增 | 替换点与退出点 |
| `flow-check.mjs` :367–461（`currentScope`） | 本步新增 | 保留；改由 prepare INPUT 给位置 |
| `story-chapters.json` :5（`context_chapters_note`）、:42–199（各章 `context_chapters`） | 本步新增 | 删字段与说明键 |
| `SKILL.md`、`phases/spec.md`、`phases/story-write.md`、`rules/ar_design_init.md`、`hooks/spec/author.mjs`、`author.md`、`story_flow.py` `spec_stage_step` / `SPEC_STAGE_ORDER` | 本步新增 | 02 §6 接线表逐行；`SPEC_STAGE_ORDER` 里「指导区 / 统稿」等 v3 说法随本步退出；`DERIVED_KEYS` 硬编码（02-N1）本步改为读合同 |
| `test/story/tests/test_writing_flow.py`、`test_author_task_package.py`、`test_author_context_entry*.py`（按实际文件名）、`test_source_index.py` | 本步新增 | 02 §7 末段点名复用的测试域 |
| `test/story/scripts/check_failure_modes.py` | 条件：退出核对时 | 建议把总方案 §6 的退出标识符加进 retired 清单，作为长期防回潮 |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：`story-build.mjs` 的 skeleton / prepare / chapter 与帮助文本；`story_flow.py` 的接续文案；`story-chapters.json`；02 §6 表的六份文件；退出清单里的函数与文本；对应测试。
- 排除：最终 `check` 新条件、verifier 输入重定、冻结名单扩展、`reopen`（step-04）；knowledge 协议；`framework/`。
- 公共规则：同前。

## 关键决定

- 已确定：02 §3.2 编排差异只报来源分配、采纳、structures 三类；02 §5 六条谓词与状态表；Python `status` 不起 Node；02 §6 不新增 `story-plan.md`；退出项以总方案 §6 为准；`chapterProblems`、`chapter --from`、`number/project/build`、图源/验收编号/规约适用/人工反馈保护一律保留。
- 已确定：最后一章提交成功时 stdout 首屏第一行是写后核对动作及路径（02 §6 末段）。
- 设计任务：无。

## 验收

02 §7 十条为全集（条 1、3 已在 3a 取得证据，本步复核接线后仍成立）；下面是必须有可运行反例的几条。

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 同一需求两套合理编排 | 都能 skeleton → chapter → 提交；固定章职责与原合同必要结构仍检查；不强迫所有章有 H4（02 §7 条 2） | 用例 | 本步自动检查 |
| 声明 `sequenceDiagram` 却交 flowchart；声明表缺「主责」列；图片放到另一节；未声明结构的建议标题在正文里改了名 | 前三种当前节提交被拒并报编排位置与候选；第四种不拦（02 §7 条 8） | 用例 | 本步自动检查 |
| **一次 template 修改同时影响两章**（换主落点 / 改 structures）后再 skeleton | 两章草稿一个字节不改；差异只列来源分配、采纳、structures 三类且两章都点名；未受影响章不出现（02 §7 条 4） | 用例 | 本步自动检查 |
| 作者在正文新增模板未列的小节 | chapter 提交通过（02 §3.2） | 用例 | 本步自动检查 |
| 最后一章提交成功时的 stdout | 首屏第一行是「读取当前 Story 与 template，执行写后核对」及路径；登记命令位置在后（02 §7 条 6） | 用例断言首屏 | 本步自动检查 |
| prepare 八种状态（02 §5 表） | 输出逐行一致；`related` **两个目标一个有草稿一个没有** → 前者草稿路径、后者明确缺失并给视图路径 | 用例覆盖八行 | 本步自动检查 |
| 已有草稿 + 现有 Story 已写而草稿缺失 | skeleton 不重播种；缺稿按现稿补回目标章（02 §3.2 恢复能力保留） | 既有用例 + 新增 | 本步自动检查 |
| 退出核对 | 总方案 §6 列到「02」的标识符在 `doc/extensions` 生产代码与提示词零命中；`story-chapters.json` 无 `context_chapters`；story-write 旧主干不在；`SPEC_STAGE_ORDER` 无 v3 说法；`DERIVED_KEYS` 改读合同 | grep + 人读；retired 清单可选 | 本步自动检查 |
| 规模 | `measure()` 前后值与逐函数增删；**本步必须出现净退出量**，并对照总方案 §7 说明 2.3 累计净变化 | `TEST.md` §7 | 本步自动检查 |
| 过拟合与四道门 | 同 step-02 | `TEST.md` §7、§7.2–7.3 | 本步自动检查 |

## 提交边界

- 纳入：上面「负责」的全部文件与测试。
- 排除：他人未提交改动；golden 正本；`98` / 本目录。
- 完成条件：02 §7 十条全部有证据；退出清单归零；`approved_for_commit` 后提交，随后 `advance` 到 step-04。

## 停止条件

- 必须保留两条写作链才能过测试时停下——那说明退出清单或替换归属有缺口，回方案。
- 与 3a 合同冲突时 `executor_question`；3a 函数需要改动的，在本步内改并在送审说明里点名，不回退 3a 的提交。
