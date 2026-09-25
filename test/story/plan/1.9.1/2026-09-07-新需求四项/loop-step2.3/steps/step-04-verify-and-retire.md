# `step-04-verify-and-retire`：写后核对、审查接线、整体退出核对与确定性验收

## 目标结果

03 分册 §1–§6、§8、§9 落地：prepare 在全部章有正文时指向写后核对（读 Story + template + 来源/决策，四类关系）；`story-build check` 接入 03 §2 三组有限条件（来源版本仍在、template 结构与 structures 目标可核、原有保护继续）；verifier 输入按 03 §3 重定（Story 与 template 内联，selection 与来源目录只给路径/版本/单元表，字节分别记录）；`STORY_SRC_FROZEN` 扩到 selection / template / basis 并让 `reopen` 与 basis 刷新受同一守卫；03 §5 整体退出核对逐项归零；03 §6 确定性验收表全部有正反用例；03 §8 过拟合自查；03 §9 实施反馈写进 `98`。**03 §7 行为验收（三次同条件重复、场景泛化、成本记录）由用户按 TEST.md 启动，不在本步自动检查内**；最终报告如实标「实施评审通过，行为待验」。

## 前置与依赖

- 输入产物：step-03（3a）的 template 合同与函数、step-03b 的 skeleton / prepare / chapter 接线；step-02 的索引与 basis；现有 `hooks/shared/pre_verifier.mjs` :45–72（Story 内联段）、`reader-review-task.mjs`、`verifier-report.mjs`（`reviewVerdict`）。
- 真实依赖：step-03b。
- 执行顺序：无。
- 就绪程度：可实施。唯一待 Human 的事在收口时：`FINAL_REVIEW.md` 所在目录被 `.gitignore` 忽略，`complete-report --commit` 的提交方式请用户裁定（见 plan-review 未决 ②）。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md`、`test/story/AGENTS.md`、`test/story/TEST.md` §7、`99-执行者会话交接.md` §1/§5 | 共享已加载 | 同 step-01 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-03-核对退出与验收.md` 全文 | 本步新增 | 本步全部合同：§1 写后核对四类关系与三个落点；§2 最终 check 条件；§3 verifier 输入、次序、交付政策不变、冻结段；§4 失败恢复表；§5 退出核对清单；§6 确定性验收表；§8 自查；§9 交付结论 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-02-整篇编排与成文.md` §2.2、§5 | 共享已加载（step-03 已读） | 表头/图类型校验与谓词复用同一实现，不在最终 check 复制规则 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-Story写作流程重设计.md` §6、§7 | 共享已加载 | 退出清单最后一行（「仅以章标题列举得出读者审查通过的任务说明」→ 03 退出）；规模最终对照基线 9942 / 499107 / 515847 |
| `doc/extensions/hooks/shared/pre_verifier.mjs` :45–72、`reader-review-task.mjs`、`verifier-report.mjs` :206/:256 | 本步新增 | promptFragments 接入点；`reviewVerdict` 与 status 分开 |
| `doc/extensions/skills/story/scripts/core/story-build.mjs` `cmdCheck` :1254 起、`deliveryProblems` :2033–2039、`cmdPrepare` | 本步新增 | 最终 check 的接入位置；交付门条件保持用户已批准政策 |
| `doc/extensions/skills/story/scripts/core/story_flow.py` :81（`STORY_SRC_FROZEN`）、:1341（冻结指纹）、`cmd_reopen` :1084 起 | 本步新增 | 冻结名单扩展与 reopen 行为 |
| `doc/extensions/skills/story/rules/spec-rules.overlay.yaml`（`story_reader_review`）与 `phases/story-write.md` 写后核对段 | 本步新增 | 审查任务次序（先来源与范围、再对照 Story、再互补与图）；写后核对四类关系 |
| `test/story/golden/story-金样-AR90006.md`、`…-说明.md` §3、§4；`story-template-金样-…-说明.md` §5 | 条件：核 03 §7.2 对照口径、写实施反馈时 | 金样只作效果对照，不进 Case，不当判据 |
| `test/story/scripts/check_failure_modes.py`、`TEST.md` §7.2–7.3、§8.1 | 条件：自查与反馈时 | 过拟合扫描；证据还原表 |
| `test/story/regression/mechanism-budget.yaml` | 条件：收口时 | 最终规模对照；本步收口后由维护者移除 `null` 例外（不由 executor 改） |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：`story-build.mjs` 的 `check` 新条件与 prepare 写后核对分支；`story_flow.py` 冻结名单与 `reopen`；`hooks/shared/pre_verifier.mjs` / `reader-review-task.mjs` 的输入组装与字节记录；`spec-rules.overlay.yaml` 的审查任务次序；`phases/story-write.md` 写后核对段；退出清单最后一行；对应测试；`98` 的实施反馈（不入库）。
- 排除：交付政策（未登记审查员记提示放行）不改；`framework/`；knowledge 协议；03 §7 的真实运行。
- 公共规则：同前。

## 关键决定

- 已确定：03 §1 三个落点（业务根因回 Spec/decisions、编排不当回 template、表达改草稿），不新增 copyedit / 已读标记 / 台账。
- 已确定：03 §2 三组条件；表头/图类型校验复用 step-03 同一实现；不加字数、相似度、结论条数门槛。
- 已确定：03 §3 输入组成与内联边界（Story + template 内联；selection 与来源目录只给路径、版本、单元位置、有效取舍表；分别记录 UTF-8 字节与截断）；`reviewVerdict` 与 status 继续分开；交付政策保持现状。
- 已确定：03 §3 末段冻结规则（selection / template / basis 进 `STORY_SRC_FROZEN`；chapters 派生视图可重建不入冻结；reopen 解冻只修受影响内容；basis 刷新受同一守卫）。
- 设计任务：无。

## 验收

03 §6 十一行为全集；下面列必须有可运行反例的几行。

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 全部章有正文后跑 `prepare` | NEXT 第一行是写后核对动作，INPUT 列 Story、template、来源目录、decisions 路径；未生成草稿 | 用例 | 本步自动检查 |
| 登记前改动一个源文件（basis 不一致）跑 `check` | 报来源版本变化并指向 `sources --accept-source`，不放行 | 用例（03 §2 第一条） | 本步自动检查 |
| template 声明的 structures 目标在正文缺失 / 未声明的建议小节缺失 | 前者 check 报；后者不报 | 用例（03 §2 第二条） | 本步自动检查 |
| verifier request 组装 | request 含当前 Story 全文、template 全文、有效 selection、来源目录（含 omit / defer / 未分配的位置）；原文不内联；字节数分别写进记录 | 用例读 request 文件断言 | 本步自动检查 |
| 报告结构 PASS 而 `reviewVerdict` FAIL | 交付门不通过（沿用现状） | 既有用例仍绿 | 本步自动检查 |
| `story_written` 后改 selection / template / basis | 冻结守卫拒绝并给 reopen 出口；reopen 后可改且重登记更新同一组指纹 | 用例（03 §3 末段） | 本步自动检查 |
| 03 §5 退出核对 | 总方案 §6 全部退出项在 `doc/extensions` 零命中；无「新代码搭旧命令」中间态；提示词四段各只要求本阶段判断 | grep + 人读；若 step-03 已把标识符加进 retired 清单则由 `check_failure_modes` 兜底 | 本步自动检查 |
| 03 §8 过拟合自查 | 自查记录写进 `98`：规则是否依赖 AR90006、金样是否成答案、是否按关键词近似语义、是否固定模板强迫场景、新增指引有无消费者 | `TEST.md` §7.2–7.3 命令 + 逐条语境判断 | 本步自动检查 |
| 规模与四道门 | `measure()` 与完整字符量对照基线 9942 / 499107 / 515847；未下降时按总方案 §7 写专项审视（旧职责是否退出、是否叠加补丁）；四道门同前 | `TEST.md` §7 | 本步自动检查 |
| 03 §7 行为验收 | 三次同条件重复、两类场景、成本记录 | 用户按 `TEST.md` §1–§6 启动真实 CLI；结论写进 `../reviews/`，不在本 loop 内 | 后置检查：责任 Human；完成边界 = 用户确认稳定性与泛化证据 |

## 提交边界

- 纳入：上面「负责」的文件与测试。
- 排除：他人未提交改动；golden；`98` / 本目录；`mechanism-budget.yaml`（例外移除归维护者随评审结论办）。
- 完成条件：03 §6 十一行、§5 清单、§8 自查全部有证据；`approved_for_commit` 后提交；随后 `finish`。最终报告由 reviewer 生成，标「实施评审通过，行为待验」。

## 停止条件

- 需要改交付政策（未登记审查员的放行口径）才能过验收时停下——那是用户已批准的政策。
- 03 §6 某行无法在离线夹具里构造反例、只能靠真实运行时，如实标未验证并交 reviewer，不造假绿。
