# Step2.3-01 第一笔实施评审：S4 输入与输出分开

> 2026-09-10；评阅提交 `804db2d3`，对照 [01 分册](../steps/02.3-01-原材料与初筛.md) §1、§2、§7 与 [执行者反馈](../98-执行者给评审的反馈.md) §12。四道门本次亲自重跑；行号取自 `804db2d3`（工作区 `doc/extensions` 与之一致）；未改生产代码、未跑 CLI。角色按新 AGENTS §1.1：被评的是维护实施者的提交。

## 1. 结论

**实施评审通过，附三处返修与一处事实更正；行为待验。** 01 §1 的五步顺序、幂等重试、留存件唯一、空骨架不留存、派生稿不当原输入，在代码里都对得上；六处请评审确认的判断全部同意。四道门与自述一致，规模数字有 5 行出入（见 §2）。

三处返修里一处是失败路径上的真洞（§4 R1，已复现），两处是交付面措辞。事实更正是：执行者说 `import_sources.py` 把 AR 类收件箱材料「整个丢掉」，不成立（§5）。改完不必重开评审；来源索引（01 §3–§6）可以开工。

## 2. 四道门与规模（本次重跑）

| 门 | 本次结果 | 与自述 |
|---|---|---|
| 离线：`test_s4_commit.py` + `test_material_*` + `test_writing_flow.py` | 164 passed / 31 subtests | 一致（全量未重跑，自述 821 passed 可信） |
| 失效形态 `check_failure_modes.py` | 70 条 FAIL 0，委派 11，PASS 59 | 一致 |
| `adapt-scan --check --target . --package .` | 退出 0 | 一致 |
| `git status framework/` | 空 | 一致 |
| `test_golden_sample.py` 那条红 | 复现：`test_canonical_directory_has_no_unregistered_files` 1 failed / 9 passed | 一致，是工作区未提交的金样，与本笔无关 |

规模按 `test_mechanism_budget.code_lines` 逐文件对 `0a177cf2` → `804db2d3`：

| 文件 | 代码行 | 98 §12 自述 |
|---|---:|---:|
| `story_flow.py` | 921 → 1073（**+152**） | +147 |
| `materials.py` | 183 → 194（+11） | +11 |
| `ar_design_init.md` | 106 → 116（+10） | +10 |
| `init_analysis.md` / `SKILL.md` | 0 | 0 |
| scripts_py 现值 | **1728** | 1723 |
| 总量现值 | **10115** | 10110 |

差 5 行全在 `story_flow.py`。本轮预算不设上限、只靠如实记录，所以数字要对：98 §12 的表按 HEAD 重测改过来（§4 R3）。

## 3. 对照 01 §1：逐条与代码

| 01 §1 写的 | 代码 | 判断 |
|---|---|---|
| 模型写 `AR/story-src/design-draft.md`，不覆盖输入 | `DESIGN_DRAFT` :80；`scope_step` 在 :1073–1081 给的两步都指向它 | 对 |
| `complete --from <候选稿>` 先核范围与材料仍允许收口、候选存在可读及五段结构 | `resolve_candidate` :1260（需求根内、存在）；材料两问 :1379–1402；`scope_step` :1408；`candidate_problems` :1304（空/骨架/五段序号） | 对。顺序是材料 → 范围 → 结构，预检失败前无写入（用例 `PrecheckFailuresChangeNothing` 七条） |
| 留存原输入到 `sources/ar/r<轮次>.md`；当前 AR 等于已登记派生稿则沿用其原输入 | :1419–1441 五分支；`registered.get("origin")` :1431 | 对（用例 `test_a_new_round_inherits_the_first_rounds_origin`） |
| 更新 materials 与本轮基准，再记 design 摘要、原输入定位、`design_generated_at`、complete | `materials.refresh` :1448 → `current["materials"]` :1449 → `contract["design"]={sha256, origin}` :1461 → status :1463 | 对，complete 最后写 |
| 「留存→覆盖→刷新→complete」顺序，留存件已存在不得覆盖、须与原输入摘要一致 | :1433–1441；冲突报「只有一份」:1435 | 对（用例 `test_a_conflicting_kept_source_refuses`） |
| 中途失败报已完成动作与未收口，重试同一命令 | `done` 列表 :1417/:1442/:1446/:1450；异常统一报 :1451–1455 | 对 |
| 重试时只认「当前 AR 等于候选且留存与基准一致」为自己写入；来历说不清则停 | `retry` :1389；`prior_ar` :1324 认三种身份；否则 :1342 | **实现比方案宽**：多认「空骨架」与「已登记提取稿」两种。两种都有确定性证据、失败方向是停，我同意；但 01 §1 第 6 段要补上这两种，方案与实现不能两说（§6） |
| 旧的直接覆盖入口退出，SKILL / ar_design_init / next_step / 测试同时改 | 三份提示词 diff 齐；`next_step` 只剩材料新鲜度 :997–1018；无 `--from` 报错 :1263 | 对。交付面残留两处旧说法见 §4 R2 |

**「哪一笔差异算自己写的」这条判据比方案里写的强。** 01 §1 只说「其余来源仍按原材料检查」，实现给了可计算的形式：`materials.digest_with(live, rel, prior_sha)` :197 把 AR 换回登记版重算，等于基准即其余材料未动；非重试时再要求 `live.digest == base` :1400，堵住「AR 被外部改了而其余没动」这一支（用例 `test_an_edited_ar_before_commit_blocks_it`）。两条缺一不可，写法对。

## 4. 返修

### R1 失败路径：写到一半、提取稿又改过，会被推回 S3 并把半成品登记成材料（P2）

复现步骤（用 `test_s4_commit.S4Case` 的夹具）：留存与覆盖已完成、complete 未写成（`half_commit` 形态）→ 模型改了一句 `design-draft.md` → 跑 `complete`：

```
[complete] rc=1  材料在这一轮登记之后又变了：重跑 `story_flow.py round` 登记新一轮…
[round]    created=True  rounds 1 -> 2
[complete #2] rc=1  本轮范围尚未定下来，还不能收口：S2b 需求粒度分析…
```

原因：`retry = design_bytes == cand_bytes` :1389 只认「候选一个字节没变」；候选变了就走非重试判据，:1400 那条 `live.digest != base` 把自己上一次写下的覆盖判成材料变化，报错还指路 `round`。`round` 在 `in_progress` 下照常开第 2 轮，把 **候选 v1 当 AR 材料登记**；第 2 轮范围重定之后再 `complete`，:1419 的五分支里 v1 既不是骨架、`r2.md` 不在、`contract.design` 为空，落到 else :1437 把 **v1 写成 `r2.md` 原输入**——派生稿成了上游证据，正是 01 §1 点名要防的。

窗口窄（要在 :1441 与 :1448 之间断掉，且重试前改稿），但报错把人推进坑里，且后果是这一步要修的那类错。

**改法（最小）**：留存件已经证明原输入在，AR 的差异就该按自己写入处理，不看候选变没变。把 :1389 的判断改成「当前 AR 等于候选，**或** `r<轮次>.md` 在且其摘要等于 `prior_sha`」；后一支进入 :1419 后本来就会走 :1429（origin=keep）并在 :1443 用新候选覆盖。补一条用例：half_commit 后改稿再 complete，应成功、`origin` 为 `r1.md`、`r1.md` 内容仍是上游原话、不开新轮。不改 `round`。

### R2 交付面两处旧说法（P3）

- `import_sources.py:69` 注释「AR 类不落 design.md —— 那是会被重生成的草稿，材料写进去就丢了」。理由已不成立：`AR/design.md` 现在是被留存的上游输入件，提交时覆盖、原话留在 `sources/ar/`。按当前讲：AR 类补料落 `upstream.md`，因为 `design.md` 是上游给进来的输入件、由 S4 提交覆盖，人工补料另有落点。这条不在 01 §7 清单里，但它是本笔改动直接产生的必要清理，属于本笔。
- `SKILL.md:3` description「init 拉取需求资料并生成 AR/design.md」。init 落的是空骨架、提取稿由 S4 提交；这句是 slash 跳板上执行者第一眼看到的话。改成「init 拉取需求资料并建工作区骨架」或点明「空骨架」。`story.js:303` 写的「生成 AR/design.md 空模板」是准确的，不动。

### R3 98 §12 的规模表按 HEAD 重测（P3）

`story_flow.py` +152、scripts_py 1728、总量 10115（§2）。

## 5. 事实更正：AR 类收件箱材料没有被丢掉

98 §12「范围外，但撞见了」与反馈正文都说 `import_sources.py` 把 AR 类收件箱材料整个丢掉、人工放进收件箱的 AR 类材料没有正文落点。不成立：

- `import_sources.py:70` `DOC_TARGET["AR"] = AR/story-src/upstream.md`；
- `upstream.md` 在 `materials.py:41` 的 `SOURCE_DOCS` 里，是登记材料；
- `ar_design_init.md` 输入四源表第四行就是它。

所以不需要用户裁定「要不要把这条纳入范围」，只需要按 R2 改那行注释。执行者读到的是注释里过时的理由，没有核下一行的落点。

## 6. 给方案作者

- 01 §1 第 6 段的重试身份判据补上「init 空骨架」「契约已登记的提取稿」两种，与 `prior_ar` :1324 一致。
- 01 §7 改动清单加 `import_sources.py`（一行注释）。
- R1 的判据变化（留存件证明即视为自己写入）也回写到 01 §1 第 6 段。

## 7. 六处判断的回应

| # | 判断 | 回应 |
|---|---|---|
| 1 | `scope_step` 是拆分不是新判据 | 同意。`next_step` :1018 直接 `return scope_step(...)`，`cmd_complete` :1408 调同一个；关卡判据文本没有第二份 |
| 2 | 自己写的差异不靠猜 | 同意，且 §3 末段说明为何两条判据缺一不可 |
| 3 | 空骨架不留存 | 同意。骨架依赖 `read_ids` 读 `detail.json`，若它在 init 之后才变，比对失败会落到「来历说不清」而不是误存——方向安全，不改 |
| 4 | 重试身份三选一、证明不了就停 | 同意；见 §3 表末行与 §6 |
| 5 | 收口后换稿要 `reopen` | 同意。`story_written` 下即使候选相同也报 reopen 而非「已完成」（:1366–1373），对 |
| 6 | 五段只核序号、围栏内不算 | 同意。`numbers[:5]` 允许第六段起自由，正则 :1257 不会把 `## 1.1` 误认 |

## 8. 下一步

R1–R3 改完自核 §4 的用例即可，不重开评审；随后按 01 §3–§6 做来源索引。金样 11 个文件入不入库、要不要登记进 `EXPECTED_CANONICAL_FILES`，待用户裁定，与本笔无关。真实 CLI 按 TEST.md 由用户启动。
