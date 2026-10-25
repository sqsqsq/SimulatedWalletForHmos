# `step-01-s4-fixes`：S4 提交的三处返修

## 目标结果

`804db2d3`（S4 输入与输出分开）按 `../../reviews/25-Step2.3-01-S4提交实施评审.md` §4 关闭 R1–R3，一笔提交。本步不做来源索引（01 分册 §3–§6），不改方案文件（01 §1 第 6 段与 §7 清单的回写归方案作者）。

## 前置与依赖

- 输入产物：`804db2d3` 已在 HEAD；`../../reviews/25` §4 三条返修与 §5 事实更正；`../../98-执行者给评审的反馈.md` §12。
- 真实依赖：无。
- 执行顺序：无。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md` | 共享已加载（宿主） | 红线 9 framework 只读；提交由执行者做 |
| `test/story/AGENTS.md` §1、§5.3、§7.5、§8 | 共享已加载 | 角色叫法；交付面注释只讲当前；规模如实记录；完成前自检 |
| `test/story/TEST.md` §7、§7.9 | 共享已加载 | 四道门怎么跑；只跑有区分力的用例再全量 |
| `test/story/plan/2026-09-07-新需求四项/99-执行者会话交接.md` §1、§5 | 共享已加载 | 非沙箱授权、heredoc 吃反斜杠、`PYTHONIOENCODING=utf-8`、失效形态比单测严 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-01-原材料与初筛.md` §1 | 本步新增 | S4 提交顺序、重试身份、留存件唯一——R1 改法不能越出它 |
| `test/story/plan/2026-09-07-新需求四项/reviews/25-Step2.3-01-S4提交实施评审.md` §3–§5 | 本步新增 | R1 复现步骤与改法、R2 两处文案、R3 数字；§5 说明 AR 类补料的真实落点 |
| `doc/extensions/skills/story/scripts/core/story_flow.py` :1347–1468（`cmd_complete`）、:1324（`prior_ar`） | 本步新增 | R1 的判断点 :1389 与 :1399–1402 |
| `test/story/tests/test_s4_commit.py` | 本步新增 | 新用例放哪个类、夹具怎么用（`half_commit`、`write_draft`） |
| `doc/extensions/skills/story/scripts/core/import_sources.py` :55–75 | 本步新增 | R2 注释改成当前事实：AR 类补料落 `upstream.md`，`design.md` 是上游输入件、由 S4 提交覆盖 |
| `doc/extensions/skills/story/SKILL.md` :1–10 | 本步新增 | R2 description 里「生成 AR/design.md」改成建工作区骨架 |
| `test/story/regression/mechanism-budget.yaml` 文件头 | 条件：对计数口径有疑问时 | 代码行不含注释与空行；`.md` 只去空行 |
| `test/story/scripts/check_failure_modes.py` | 条件：改完注释与 description 后 | M02 交付面历史叙述扫描 |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：`story_flow.py` 的重试判据与相关报错文案；`test_s4_commit.py` 新增反例；`import_sources.py:69` 注释；`SKILL.md:3` description；`98-执行者给评审的反馈.md` §12 的规模表按实测改正（该文件在 `.gitignore`，不入提交）。
- 排除：来源索引与 `story-sources.mjs`；`round` 命令；方案文件；工作区里他人的未提交改动（`AGENTS.md`、`TEST.md`、`mechanism-budget.yaml`、`test_mechanism_budget.py`、`golden/*`、`run_multi_case.py`）——一个都不带进本笔。
- 公共规则：四道门与提交纪律见 `TEST.md` §7；本步差异只有上面两行。

## 关键决定

- 已确定（`../../reviews/25` §4 R1）：留存件 `sources/ar/r<轮次>.md` 在且摘要等于本轮登记的 AR 摘要，就证明原输入已保住，AR 的差异按提交自己写入处理，不再要求候选一个字节没变；进入后续分支后走 `origin = keep`，用新候选覆盖。`round` 不改。报错文案里不再把这种形态指向 `round`。
- 已确定（R2）：两处文案按当前事实写，不带「曾经 / 此前 / 会被重生成」一类历史参照。
- 设计任务：无。局部实现（判据写成一个 helper 还是就地条件、用例放哪个类）由 executor 定。

## 验收

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| S1–S3 走完，留存与覆盖已完成而 complete 未写（`half_commit` 形态），随后 `design-draft.md` 又改了一句，跑 `complete --from` | 退出 0；`contract.status == complete`；`result.origin == AR/story-src/sources/ar/r1.md`；`r1.md` 内容仍是上游原话；`rounds` 数不变；`AR/design.md` 等于改后的候选 | 新用例（建议放 `InterruptedCommitsRetryTheSameCommand`）；对照 `../../reviews/25` §4 R1 的复现脚本形态 | 本步自动检查 |
| 同上形态但留存件缺失（只覆盖没留存） | 仍拒绝，报「来历说不清」，状态 `in_progress` | 既有用例 `test_retry_without_a_kept_source_refuses` 仍绿 | 本步自动检查 |
| 既有 19 例 | 全绿 | `pytest test/story/tests/test_s4_commit.py -q` | 本步自动检查 |
| `import_sources.py:69` 与 `SKILL.md:3` 改后 | 失效形态 70 条 FAIL 0；两处文字只讲当前 | `PYTHONIOENCODING=utf-8 python -X utf8 test/story/scripts/check_failure_modes.py`；人读一遍 | 本步自动检查 |
| 四道门 | 离线全量除 `test_golden_sample` 那 1 条（未提交金样，用户待裁定）外全绿；`adapt-scan --check` 退出 0；`git status framework/` 空 | `TEST.md` §7 命令 | 本步自动检查 |
| 规模 | `test_mechanism_budget.measure()` 前后值写进送审说明；98 §12 表与实测一致（现值 scripts_py 1728 / 总量 10115，改后按实测） | 送审说明列数字 | 本步自动检查 |

## 提交边界

- 纳入：`story_flow.py`、`test_s4_commit.py`、`import_sources.py`、`SKILL.md`。
- 排除：上面「排除」里的全部工作区改动；`98`、本目录文件不入库。
- 完成条件：验收全过，reviewer `approved_for_commit` 后提交；提交说明按仓内惯例写清三处返修各改了什么。

## 停止条件

- R1 改法与 01 分册 §1 顺序冲突、或发现 `round` 也必须改才能闭合时，写 `executor_question` 交 reviewer，不自行扩范围。
- 金样入库、预算额度等用户保留事项不在本步内决定。
