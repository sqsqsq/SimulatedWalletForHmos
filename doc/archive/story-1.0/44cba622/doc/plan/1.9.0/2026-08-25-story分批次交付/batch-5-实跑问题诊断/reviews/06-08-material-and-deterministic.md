# 步骤 6 + 8 · 材料真源与 Story/Review 确定性生成 · 独立评审（Claude，2026-09-03）

## 1. 结论

- 状态：**通过**（附两条裁定与两条 advisory；无需返修即可进入步骤 7）
- 审查基线：`00c46802`；审查对象：`da35bbb7`、`cb7b7797`（步骤 6）、`4e9a6d21`（步骤 8）三个提交的实际 diff
- 亲自复跑：story 586 条（含 P9 钉子已摘除）、cli 18、失效形态 73/73、全部 `.mjs` `node --check`、`compileall`；
  `story.js` / `review.js` / `token.js` 对 manifest 零引用（R2 成立）

评审依据是 2026-09-03 局部调整后的 `test/story/AGENTS.md`（§2 局部确定性能力只证真实 I/O 与消费者；§7.2 允许登记了所有者与退出步骤的迁移桥）。

## 2. 行为重建（从 diff）

**步骤 6**。新增 `scripts/materials.py`：唯一枚举四份正文 + `ux-reference/` + `assets/`，图片按内容归并、`paths` 列全部落点，
`digest` 只算权威材料不算收件箱；「已并入」不靠回执，靠把收件箱原件用 `import_sources.convert_sources` 重转后与正文比对。
`story_flow.py` 删掉自己那份材料哈希、`inputs` 表与导入回执读写，`round` 每次调用 `materials.refresh()` 按磁盘现状重算，
轮次条目只留 `materials: {path, digest}`；`pending_material` 改问清单。`flow-check.mjs` 轮次判据改为 `materials.digest`，
初析哈希不再划轮。`import_sources.py` 不再落 `.last-import.json`，转换逻辑抽成 `convert_sources()` 与判「已并入」共用。
修正提交 `cb7b7797`：`materials.json` 留在 `story-src/` 的清扫白名单里但不进 `STORY_SRC_FROZEN`（它是材料真源、随材料演化，
不是随稿冻结的台账；定稿那一刻的材料版本记在契约当轮 `materials.digest`）。

**步骤 8**。`story-build.mjs`：`requireStoryFirst()` 让 `build` 在 story 无章时拒绝渲染 review；图片身份改从 `materials.json`
读（`materialImages`），按内容认，归档副本区按字节核出是哪一张，来路不明的副本点名；材料清单节的集合由 `materialListTargets`
定（必列 = 清单里真在盘上的正文，可列 = 收件箱原件，其余即多列）；有清单时目录白名单粗判让位；新增 `⑫a 非占位`
（只判正文非空与 `{{…}}` 残留，无任何数量阈值）。`phases/spec.md` 成文顺序补入 ⑤ build（裁决之后、登记之前）。
`check_failure_modes.py` 在跑 story-build 前先跑一次 `round`，让依赖清单的判据真的执行。

## 3. 验收证据（逐条对完成条件）

| 完成条件 | 证据 | 结果 |
|---|---|---|
| 6·重复导入 digest 不变；任一字节改变即变 | `test_rerunning_without_change_is_idempotent`、`test_changing_one_image_is_a_new_round`、`test_a_text_only_supplement_still_starts_a_new_round` | PASS |
| 6·hash 只在唯一模块；对接层零引用；替身 js 取材后 `round` 仍生成 | `test_no_other_script_hashes_material_files`、`test_the_data_layer_never_hears_about_the_manifest`、`test_a_stand_in_data_layer_still_gets_a_manifest`；复审者 `rg` 零命中 | PASS |
| 6·回执删除；`story-flow.json` 无 `inputs`，只引 path/digest | diff：`RECEIPT`/`read_receipt`/`consume_receipt`/`material_inputs`/`material_fingerprint` 全部删除；`test_importing_leaves_no_receipt`、`test_the_contract_only_points_at_the_manifest` | PASS |
| 6·README 变化不动图片身份；图片无第二登记 | `test_a_readme_change_does_not_move_any_image_identity`；`materials.py` 是唯一登记，`story-build.mjs` 旧的「从 `![]()` 枚举登记」已删 | PASS |
| 6·同一 digest 下分析可修订并收口 | `test_revising_the_analysis_does_not_open_a_round`；`flow-check.mjs` 不再核 `analysis.sha256` | PASS |
| 6·flow 不镜像 Framework phase | `test_the_flow_never_mirrors_a_framework_phase` | PASS |
| 6·空材料 / 解析失败 / 变化 / 不变四态可区分 | `test_an_empty_feature_still_has_a_manifest`、`test_a_broken_classify_file_is_not_an_empty_inbox`、上两行 | PASS |
| 6·P5/P13 根因关闭；相关形态迁移 | P5：轮次只由 digest 划界，三处文本已同步（`SKILL.md`、`init_analysis.md`、脚本 docstring）；P13：图片登记唯一来源。**6 条形态的 checker 未改**，见 §4 裁定 2 | 部分（已登记） |
| 8·骨架稳定且无数量配额；一句合法内容通过 | `TestNonPlaceholderChecksOnlyTwoThings` 3 条；复审者通读 ⑫a 代码，无长度/条目常量 | PASS |
| 8·人写区重建字节稳定；机器区不可手维护 | `test_rebuilding_is_byte_stable`、`test_the_machine_zone_cannot_be_maintained_by_hand` | PASS |
| 8·Review 不可能在 Story 之前生成；新发现 decision 进入 Review | `test_build_refuses_before_the_story_is_written`、`test_build_runs_once_the_story_has_chapters`、`test_a_decision_found_while_writing_reaches_the_review` | PASS |
| 8·图片链接可达且不复制出新资产真源 | `TestImageIdentityComesFromTheManifest` 5 条；`materials.py` 不枚举归档副本目录，副本不进登记 | PASS |
| 8·金样与反例通过 | 全量 586 与 73/73 含金样测试 | PASS |
| 8·P1/P13/P16 确定性根因关闭 | P16：`requireStoryFirst` + 作业顺序；P13：同上；P1 的确定性部分（图片身份不再按文件名）关闭，语义部分归步骤 7 | PASS |

## 4. 裁定（评审者代方案维护者裁，记入方案）

1. **材料清单节「集合由清单定、语义由作者写」，接受，不算偏离 D8。** `steps/08` 第 3 条字面是「只从 manifest 生成」，
   金样每行含「内容贡献」这句语义，脚本不该写它。现实现把可机械的部分（有哪几份、链到哪）交给清单、漏列多列当场点名，
   语义留给作者——这正是 AGENTS §4.2 的分工。`steps/08` 与 D8 表「Story 确定性附录」一行改写为「材料清单：集合由 manifest 派生并核对，贡献说明由作者写」。
2. **步骤 6/8 名下 15 条失效形态的 checker 保留不改，接受为登记的迁移桥。** 旧发现者仍在守、新发现者（清单判据）已上线，
   符合 D10「新发现者先建、旧发现者后退场」。但 `06-验收追踪矩阵.md` 要求「调整主要步骤须同时改步骤文件、矩阵与
   `failure-modes.yaml`」，本轮三者都未动。**处置**：矩阵第 51、53 行各加一句「responsibility 改写与旧 checker 退场在步骤 9/11 执行」，
   `failure-modes.yaml` 不动（它记的是现行发现者，现行发现者确实没变）。

## 5. advisory

- **A1** `rules/init_analysis.md` 命令表仍写 `--by human|ai`，而 `ACTORS` 只剩 `human`（步骤 6 实施记录已登记）。这是 F8P 乙留下的文本与实现相斥，归步骤 11 的最终扫描，或步骤 9 触碰该文件时顺手改。
- **A2** `materials.py` 每次 `round` 与 `pending_material` 都重转一遍 docx。当前材料量级无感；步骤 7 的 large 夹具里顺带记一次 `round` 耗时，不另立指标。
- **A3** 8 先于 7 实施的代价如实登记（小节配额 `min_sections` 与 15 条 checker 保留到 7/9 之后）；05 §3 的进入条件应同步为「B 组按分组顺序，8 不再以 7 为前置」，否则文本与执行相斥。

## 6. 范围与回归

- 允许范围：步骤 6 改 `materials.py`（新增）、`story_flow.py`、`flow-check.mjs`、`import_sources.py`、`init_analysis.md`、`SKILL.md` 产物表，测试；
  步骤 8 改 `story-build.mjs`、`phases/spec.md`、`check_failure_modes.py`，测试。均在 `steps/06`、`steps/08` 允许范围内。
- 保护区差异：零（产品源码、金样、Case、Framework、Knowledge、post_check/pre_verifier、旧逐单元判据的退场状态均未动）。
- 未运行：真实 Story（两步都不要求）。

## 7. 后续

- 允许提交：三个提交已在库，无需追加。
- 下一步：**步骤 7**（verifier 资格门）。前置：用户对「跑成对 good/bad 模型实验」的授权口径要与步骤 2 暂缓一并定；
  资格门按 `cli_config_id` 逐配置出矩阵（`steps/07`）。
