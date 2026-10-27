# step-01-s4-fixes · 评审记录

> 本文件只追加，不改写。记录按事件序号或时间分节。步骤合同见 [../steps/step-01-s4-fixes.md](../steps/step-01-s4-fixes.md)；问题编号沿用 `../../reviews/25-Step2.3-01-S4提交实施评审.md` §4 的 R1–R3，不重编。

## 2026-09-10 发布（reviewer，init 前）

本步范围是 `804db2d3` 的三处返修，强制结果与复验方法如下。

| 编号 | 需求依据 | 真实错误及证据 | 强制结果 | 复验方法 |
|---|---|---|---|---|
| R1 | 01 分册 §1：中途失败重试同一命令；不把派生稿标成外部证据 | `story_flow.py:1389` 只认「候选一个字节没变」为重试；half_commit 后改一句提取稿再 `complete`，:1400 判「材料变了」并指路 `round`，`round` 开第 2 轮把候选 v1 登记成 AR 材料（reviews/25 §4 R1 有复现输出） | 留存件 `r<轮次>.md` 在且摘要等于登记的 AR 摘要即视为提交自己的写入，用新候选覆盖、`origin` 指向留存件；报错不再把该形态指向 `round`；新增反例用例 | 跑新用例：退出 0、`status == complete`、`origin == …/r1.md`、`r1.md` 仍是上游原话、`rounds` 不增；`test_retry_without_a_kept_source_refuses` 仍拒 |
| R2 | AGENTS §5.3 交付面只讲当前 | `import_sources.py:69` 注释理由「会被重生成的草稿」已不成立；`SKILL.md:3` description「init 生成 AR/design.md」与现行为不符 | 两处按当前事实改写（AR 类补料落 `upstream.md`，`design.md` 是上游输入件由 S4 提交覆盖；init 建工作区骨架） | 人读两处；`check_failure_modes.py` FAIL 0 |
| R3 | 总方案 §7 规模如实记录 | 98 §12 表 `story_flow.py` +147 / scripts_py 1723 / 总量 10110，按 `code_lines` 实测为 +152 / 1728 / 10115 | 98 §12 按改后 HEAD 重测改正 | reviewer 用 `test_mechanism_budget.measure()` 复算 |

事实更正（不需要动作）：AR 类收件箱材料不是「整个丢掉」，`import_sources.py:70` 落到 `AR/story-src/upstream.md`，该文件在 `SOURCE_DOCS` 与 ar_design_init 四源表里。

提交边界与四道门见步骤文件。金样 11 个未提交文件那条红与本步无关，待用户裁定。

## seq 4 · step_ready（reviewer）

执行者已加入，本步可以开始。范围与强制结果见上一节 R1–R3，合同见步骤文件。补一条事实：金样 11 个文件已入库（`d2d7a0eb`，`EXPECTED_CANONICAL_FILES` 已登记），离线全量现在应当全绿，验收不再豁免那一条。实施前先按协议做审视：有阻断疑问写在本文件末尾并交 `executor_question`；没有就记结论与假设，同一轮实施。

## seq 4 后 · 实施前审视（executor）

### 已加载路径 → 影响的实施/验收决定

| 路径 | 影响 |
|---|---|
| `steps/step-01-s4-fixes.md` 全文 | 范围＝R1–R3 一笔；`round` 不改；他人未提交改动一个不带 |
| `../../reviews/25-Step2.3-01-S4提交实施评审.md` §3–§6 | R1 的复现形态与最小改法、R2 两处文案、R3 三个数字；§5 的事实更正 |
| `../../steps/02.3-01-原材料与初筛.md` §1 | 提交顺序、留存件唯一、「重试同一条命令」——改法不得越出 |
| `story_flow.py`（`cmd_complete` / `prior_ar` / `resolve_candidate`） | R1 判据点在 `retry` 一行；`keep` 定义要上移到判据之前 |
| `import_sources.py` :55–75 | 确认 `DOC_TARGET["AR"] = AR/story-src/upstream.md`——只有注释理由过时，落点没错 |
| `SKILL.md` :1–10 | description 是 slash 跳板第一眼看到的话 |
| `AGENTS.md` §5.3 / §8 | 交付面注释只讲当前；改完自己先跑失效形态 |
| `test_s4_commit.py` | 新用例进 `InterruptedCommitsRetryTheSameCommand`，复用 `half_commit` / `write_draft` |
| （核实）`d2d7a0eb` 与 `test_golden_sample.py` | 金样 11 件已入库、用例 10 passed——本步验收按**全绿**判，不再豁免那一条 |

### 验收项 → 修改落点 → 验证方法 → 越界/疑问

| 验收项 | 修改落点 | 验证方法 | 越界/疑问 |
|---|---|---|---|
| half_commit 后改稿再 `complete`：退出 0、`origin == …/r1.md`、`r1.md` 仍是上游原话、`rounds` 不增、`AR/design.md` 等于新候选 | `cmd_complete` 的 `retry` 判据；`keep` / `keep_rel` 上移 | 新用例，先看它在改前红 | 无 |
| 只覆盖没留存仍拒绝 | 不改 | 既有 `test_retry_without_a_kept_source_refuses` | 无 |
| 既有 19 例全绿 | 不改 | `pytest test/story/tests/test_s4_commit.py -q` | 无 |
| 两处文字只讲当前 | `import_sources.py:69`、`SKILL.md:3` | 失效形态 70 条 FAIL 0；人读 | 无 |
| 四道门 | — | `TEST.md` §7 四条 | 无（金样已入库，按全绿判） |
| 规模如实 | `../../98-执行者给评审的反馈.md` §12 | `test_mechanism_budget.measure()` 重测 | 98 在 `.gitignore`，不入提交 |

### 结论：无阻断疑问

两条必要假设，写明以便评审推翻：

1. **R1 的判据只问「原输入还在不在」，不要求盘上是某个已知形态。** 断点可能落在
   `design_path.write_bytes` 写到一半——那时盘上既不是原输入也不是完整候选，是真实的第三态。
   要求「必须等于原输入或等于候选」会把唯一的恢复路径堵死。留存件在且摘要等于本轮登记的
   那一版，就证明上游原话已经保住；此后 `AR/design.md` 里是什么都是这条命令自己的中间产物。
2. **`prior_ar` 与五分支不动。** 新判据进入写入段后本来就落到「留存件已在」那一支
   （`origin = keep_rel`），再用新候选覆盖，正是 R1 要的结果。

## seq 7 后 · 送审（executor）

### R1 → 最终修改位置 → 验证及实际结果

**先复现再改**：新用例 `test_retry_after_an_edited_draft_succeeds` 在改前红，
报的正是评审给的那句——`材料在这一轮登记之后又变了：重跑 story_flow.py round …`。

最终修改在 `story_flow.py`：

- `keep` / `keep_rel` 的定义从写入段上移到判据之前，新增 `kept_is_prior`
  （留存件在、且摘要等于本轮登记的 AR 摘要）；
- `retry = design_bytes == cand_bytes or kept_is_prior`。判据从「候选一个字节没变」
  换成「原输入还在不在」，注释写明两个方向：断点可能落在覆盖写到一半、重跑前改稿是正常的；
  反过来只覆盖没留存时判不出重试，因为那份 AR 没有来历证据。
- 写入段里「留存件已在 → `origin = keep_rel`」那个 `elif` 随之**不可达**（`kept_is_prior`
  为真时 `retry` 必为真），删掉；`elif keep.is_file()` 此后单指「留存件在但与当前 AR 不同」
  的冲突，仍报「只有一份」。`prior_ar` 与其余四分支未动。`round` 未动。

验证（`pytest test/story/tests/test_s4_commit.py -q` → **21 passed**）：

| 用例 | 实际结果 |
|---|---|
| `test_retry_after_an_edited_draft_succeeds`（新） | 退出 0；`status == complete`；`origin == AR/story-src/sources/ar/r1.md`；`r1.md` 仍是上游原话；`AR/design.md` 等于改过的候选；`rounds` 不增 |
| `test_a_half_written_design_is_still_recoverable`（新） | 覆盖写到一半（截断）后重跑：退出 0、`origin` 同上、`design.md` 等于完整候选 |
| `test_retry_without_a_kept_source_refuses`（既有，反例） | 仍拒绝、报「来历说不清」、状态 `in_progress` |
| `test_a_conflicting_kept_source_refuses`（既有，反例） | 仍拒绝、报「只有一份」 |
| 其余 17 例 | 全绿 |

### R2 → 最终修改位置 → 验证

- `import_sources.py` 的 `DOC_TARGET["AR"]` 上方注释：改成当前事实——AR 类补料落
  `upstream.md`，因为 `AR/design.md` 是上游给进来的输入件、S4 提交提取稿时整份覆盖它，
  人工补录的本部件材料要有自己的落点才留得住，而它本身也是一份登记材料。
- `SKILL.md` frontmatter description：「init 拉取需求资料并生成 AR/design.md」→
  「init 拉取需求资料并建工作区骨架」。
- 验证：`check_failure_modes.py` **70 条 FAIL 0**；`grep` 确认这句 description
  在 `doc/` / `.claude/` / `CLAUDE.md` 里没有第二份副本（命中只在 `output/` 的历史跑记录，非交付面）。

### R3 → 最终修改位置 → 验证

`98-执行者给评审的反馈.md` §12 的规模表按改后 HEAD 重测（该文件在 `.gitignore`，不入提交）。
同时把该节「范围外，但撞见了」整段换成「一处我说错了」——`import_sources.py` 的 AR 落点
一直在 `upstream.md`，过时的是注释的理由不是落点（评审 §5）。

### 送审证据

四道门（工作区，改后）：

| 门 | 命令 | 结果 |
|---|---|---|
| 离线全量 | `pytest test/story/tests -n auto --dist loadscope -q` | **824 passed, 6 skipped**，0 failed |
| 失效形态 | `check_failure_modes.py` | **70 条 FAIL 0**，委派 11、PASS 59 |
| adapt | `adapt-scan.mjs --check --target .` | 退出 0，核对通过 |
| framework | `git status --porcelain framework/` | 0 行 |

金样那条豁免已不需要：`d2d7a0eb` 已入库、`test_golden_sample` 10 passed，我核过。

规模（`test_mechanism_budget.measure()`，基线 `0a177cf2`）：

| 类别 | 基线 | 现在 | 净 |
|---|---:|---:|---:|
| scripts_py | 1565 | 1727 | +162 |
| prompts_md | 1787 | 1797 | +10 |
| data / hooks_mjs / scripts_mjs | 752 / 3013 / 2825 | 未动 | 0 |
| **总量** | **9942** | **10114** | **+172** |
| 同范围完整字符量 | 499107 | 509393 | +10286 |

逐文件：`story_flow.py` 921 → 1072（+151，比 `804db2d3` 的 +152 少 1 行——
删掉的不可达分支抵掉了新增的 `kept_is_prior`）、`materials.py` +11、`ar_design_init.md` +10；
`import_sources.py`、`SKILL.md`、`init_analysis.md` 本次只动注释与一句 description，代码行 ±0。

### 提交边界与剩余限制

- 将纳入提交：`story_flow.py`、`test_s4_commit.py`、`import_sources.py`、`SKILL.md`。
- 不带：`AGENTS.md`、`TEST.md`、`mechanism-budget.yaml`、`test_mechanism_budget.py`、
  `run_multi_case.py`（工作区里他人或前轮的未提交改动）；`98` 与本目录在 `.gitignore`。
- 未运行：真实 CLI（按 `TEST.md` 由用户启动）。以上全部是结构与连接证据，
  不证明模型在真实需求上会走这条路。
- 本步问题反思：`804db2d3` 那一版的 `retry` 判据把「同一条命令的重试」理解成
  「输入一模一样地再跑一次」，而中断恢复的现实是**输入可以变、已保住的东西不能丢**。
  我当时为它写了用例，但用例复刻的是我自己的理解——`half_commit` 之后没有改稿。
  这一类缺口靠加用例补不上，得先问「这个判据在说什么、它凭什么这么说」。

## seq 10 · 评审与 closeout（reviewer）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| `pytest test/story/tests/test_s4_commit.py -q` | 21 passed | 一致 |
| 离线全量 `pytest test/story/tests -n auto --dist loadscope -q` | 824 passed / 6 skipped / 242 subtests，0 failed | 一致（金样入库后不再有豁免项） |
| `check_failure_modes.py` | 退出 0，FAIL 0，委派 11 | 一致 |
| `adapt-scan.mjs --check --target . --package .` | 退出 0 | 一致 |
| `git status --porcelain framework/` | 0 行 | 一致 |
| `test_mechanism_budget.measure()` | scripts_py 1727、总量 10114 | 一致；98 §12 已按此改正 |
| 突变核对：把 HEAD（`804db2d3`）的 `story_flow.py` 放进镜像目录跑两条新用例 | `test_retry_after_an_edited_draft_succeeds`、`test_a_half_written_design_is_still_recoverable` 均 FAILED；`test_retry_without_a_kept_source_refuses`、`test_a_conflicting_kept_source_refuses` 仍 passed | 新用例确实只被本次修改变绿；两条反例没有被放松 |

R1–R3 逐项：R1 改在 `retry = design_bytes == cand_bytes or kept_is_prior`，`keep`/`keep_rel` 上移，删掉随之不可达的 `elif`，`prior_ar` 与 `round` 未动——与 01 分册 §1 顺序一致，比评审给的最小改法还少一个分支。R2 两处文案只讲当前，读过。R3 数字对。executor 的两条假设（判据只问「原输入在不在」、五分支不动）成立，第二条新用例（覆盖写到一半）正是第一条假设的证据。

### closeout

- 最终设计：S4 提交的「重试」由「留存件在且摘要等于本轮登记的 AR 摘要」或「当前 AR 等于候选」任一成立判定；留存件证明原输入已保住后，`AR/design.md` 的任何内容都视为本命令的中间产物，用当前候选覆盖，`origin` 指向留存件。只覆盖没留存仍报「来历说不清」。
- 实际修改：`story_flow.py`（判据与注释，净 −1 行）、`test_s4_commit.py`（+2 例）、`import_sources.py:69–70` 注释、`SKILL.md:3` description；`98` §12 规模表与「一处我说错了」段（不入库）。
- 验证：见上表。
- 剩余限制：① 断点窗口内若上游又恰好改了 `AR/design.md`（留存之后、覆盖之前），重跑会用候选覆盖那次外部改动——原输入仍在留存件里，但新一版外部 AR 会丢；这是 01 分册明写「不承诺跨文件原子性」的范围，不在本步处理。② `scripts/adapters/story.js:303` 帮助文本仍写「生成 AR/design.md 空模板（…覆盖前须确认）」，后半句与 `ar_design_init.md` §4 第 4 条相反；对接层是本地模拟替身、不在本步清单，记给方案作者在 step-02 的提示词改动里顺手处理。③ 真实 CLI 未跑，行为待验。
- 本步问题反思：`804db2d3` 的判据把「重试」写成「输入一模一样地再跑」，用例又是照着同一理解写的，所以互相印证却漏了中断恢复的真实形态。评审时是靠推演恢复路径并实跑复现才发现的——这类判据以后在方案里就该写成「凭什么证据认定」而不是「什么状态算」。

**批准提交。** 纳入：`story_flow.py`、`test_s4_commit.py`、`import_sources.py`、`SKILL.md`；不带工作区里他人的改动。
