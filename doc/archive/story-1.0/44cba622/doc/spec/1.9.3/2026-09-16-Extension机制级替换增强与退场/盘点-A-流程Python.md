# 盘点 A · `skills/story/scripts/core` Python 侧 + `flow/*.mjs`（只读，2026-09-16，基线 9b4637fa）

盘点范围：`story_flow.py`、`import_sources.py`、`flow/{state,inputs,routing,decisions,rounds,submission,lifecycle,meetings}.py`、`materials/{importer,meeting,registry}.py`、`flow/check.mjs`、`flow/client.mjs`。
路径前缀 `core/`＝`doc/extensions/skills/story/scripts/core/`；测试前缀 `T/`＝`test/story/tests/`。只列事实与可疑点，不含修改建议。

## 0. CLI 子命令（9 个 mode，`core/story_flow.py:79-80`）

| 机制 | 做什么 | 谁生产 / 谁消费 | 确定性 / 依赖模型 | 现役证据 | 可疑点（事实） |
|---|---|---|---|---|---|
| `init` | 建工作区骨架：`inbox/README.md`、RR/SR 占位件、`AR/design.md` 空骨架 | 生产：`core/flow/inputs.py:418-464`；消费：人＋`submission.is_ar_skeleton`（`core/flow/submission.py:60-66`）、`known_identities`（同:89-104） | 确定性 | `T/test_requirement_system.py`（`"init", AR` 6 处）、`T/test_empty_knowledge_repo.py:117`、`T/test_flow_module_layout.py:159,174`、`T/test_image_registration.py:62` | 骨架字符串是 `AR/design.md` 唯一真源（`inputs.py:382-415`），同时被 `submission` 当「空判断」基准；骨架多一个空格即同时改变两处语义 |
| `round` | 按磁盘现状重算材料清单、划轮次、消费 positioning / scope_options 侧车 | 生产：`core/flow/rounds.py:18-118`；消费：`routing.next_step`、`check.mjs:118-208`、`story-build.mjs:125-131` | 确定性 | `T/test_material_rounds.py:57,376` 等 30+ 断言；`T/test_s4_commit.py`（7 处 `"round"`） | 同一条命令有三条互斥落点（新轮 102-118 / 幂等轮 61-73 / 收口后 85-100），三条各自写 `materials` 但只有后两条会写 `materials_changed_after_complete`（88），该字段零读者 |
| `decide` | 记一条关卡决策（含未生效的 rejected），退出码 0/2 | 生产：`core/flow/decisions.py:20-164`；消费：`routing.scope_step`、`meetings.presented/pending_asks`、`check.mjs:162-207` | 确定性（选项与依据由模型/人供给） | `T/test_author_task_package.py:98,111`、`T/test_image_registration.py:69,82`、`T/test_meeting_material.py:465-495`、`T/test_s4_commit.py` | `decisions.py:22-23` 的「--gate 须为…之一」不可达：`story_flow.py:83` 已用 argparse `choices=list(GATES)` 拦掉 |
| `status` | 只读位置 + 材料事实 + 会议话题枚举 + 侧车形状 | 生产：`core/flow/lifecycle.py:19-63`；消费：`flow/client.mjs:35-55` → `hooks/spec/author.mjs:45-73`、`core/story/sources.mjs:245-258` | 确定性 | `T/test_flow_status_client.py:81-161`、`T/test_material_rounds.py:357,532`、`T/test_multi_case_cli.py`、`T/test_cli_config_failover.py` | 输出 9 个字段中只有 `exists` / `material_state` / `action` / `sidecar` 有程序读者（`client.mjs:78-89`、`author.mjs:45-73`）；`schema`/`status`/`story_written_at`/`round`/`positioning`/`gates`/`split`/`design`/`archived`/`meetings` 只被提示页/人读 |
| `complete` | 备份上游 AR → 覆盖 `AR/design.md` → 刷新清单 → 记 `complete` | 生产：`core/flow/submission.py:115-253`；消费：`check.mjs:269-288`、`story-build.mjs:119` | 确定性 | `T/test_s4_commit.py` 全文件（约 35 个用例） | 重试判据 `retry`（`submission.py:178`）由三个条件或起来，其中 `refreshed_unsaved` 只能由「清单已刷新而契约未存」这一断点态产生（166-176），正常路径不可达 |
| `reopen` | 撤销收口（含撤销成文登记），留痕 `reopened[]` | 生产：`core/flow/rounds.py:121-162`；消费：无程序读者（`reopened` 零读者） | 确定性 | `T/test_material_rounds.py:313-462`（9 个用例） | `story_flow.py` 模块 docstring 的命令表（`story_flow.py:17-23`）没有列 `reopen`，也没有列 `story`，而 `mode` choices（:79-80）有 |
| `story` | 登记成文态：跑 `project`→`number`→`build`→`check` 四次 node，通过才写 `story_written` + 台账指纹 | 生产：`core/flow/lifecycle.py:66-158`；消费：`check.mjs:335-350`（`storyProduced`）、`core/story/context.mjs:177-181`（冻结判据） | 确定性（4 次 subprocess） | `T/test_material_rounds.py:462,471`、`T/test_harness.py`（5 处 `"story"`）、`T/test_spec_story_gate.py:64-75` | 一条命令里串 4 次 `story-build.mjs` 子进程（:110,116,127,135），任一非 0 即整体拒绝；失败文案把四步分别硬编码 |
| `archived` | 跑交付门 `check --deliver`，通过才写 `archived:{at}` | 生产：`core/flow/lifecycle.py:161-200`；消费：`state.after_complete`（`core/flow/state.py:119`）、`routing.py:42` | 确定性 | 无直测：`T/test_material_rounds.py:397` 直接手写 `data["archived"]={"at":…}`；`cases/auto-topup/interaction-script.yaml:44` 的 `expected_phase: archived` 是驱动器阶段名 | docstring（`lifecycle.py:164-167`）称「装配脚本据它判定 `AR/review.md` 已归人所有，此后只备份不重建」——JS 侧没有任何文件读 `contract.archived`（全仓只有 `check.mjs:71` 注释提到）；实际「不重建」是 `core/story/review.mjs:355,449-512` 的人工区逐字节保留，与 archived 无关 |
| `meeting-refresh` | 按 `corrections.json` 生成 `evidence.md` | 生产：`core/flow/meetings.py:213-235`；消费：无程序读者——`evidence.md` 只被 `meeting.evidence_stale`（`core/materials/meeting.py:204-210`）判陈旧，以及 `hooks/shared/reader-review-task.mjs:144` 当提示文字列出 | 确定性 | `T/test_meeting_material.py:337-390` | 产出物 `evidence.md` 零机器消费者：脚本生成它 → 脚本检查它是否过期 → 交给模型读。它不进材料清单（`meeting.material_items` 只登记 `original.docx`，`core/materials/meeting.py:351-363`） |

### `import_sources.py` 的 5 条入口（`core/import_sources.py:36-129`）

| 机制 | 做什么 | 谁生产 / 谁消费 | 确定性 | 现役证据 | 可疑点 |
|---|---|---|---|---|---|
| `--feature`（整批导入） | 转换落盘，全成功才写 | `core/materials/importer.py:641-712`；消费：`registry.collect_sources`（反算已并入） | 确定性 | `T/test_material_delivery.py`、`T/test_meeting_material.py:274-330`、`T/test_story_build.py` | 无回执，靠磁盘反推（设计声明见 `importer.py:18-19`） |
| `--preview` | 只读预览 docx 正文 + 图清单 | `importer.py:469-486`；消费：读会/归类的模型（`rules/inbox_import.md:51-58`） | 确定性 | 零测试（`grep preview T/*.py` 无命中） | 唯一一条完全没有测试的 CLI 分支 |
| `--register-ux` | 复制图到 `ux-reference/` 起语义名 + 写 caption + 刷清单 | `importer.py:608-638`；消费：`registry.collect_materials:169-190`、`hooks/spec/author.mjs:183-235`、`hooks/shared/reader-review-task.mjs:47-58` | 确定性 | `T/test_image_registration.py:119-161` | — |
| `--caption-image [--unused/--used]` | 三态写 `ux-reference/.captions.json` | `importer.py:538-605` + `registry.py:107-142`；消费同上 | 确定性 | `T/test_image_registration.py:236-302`、`T/test_material_rounds.py:213-258` | 侧车落在 `ux-reference/` 目录内但以点开头，靠 `registry.py:174` 的 `startswith(".")` 排除自己进清单——排除规则与落点选择耦合 |
| 归类件 `.classify.json` | AI 写、脚本执行 | `importer.read_classify:128-140`；消费 `validate:156-176`、`convert_sources:489-528`、`registry.collect_sources:238-303` | 模型判断 → 脚本执行 | 同上 | 值域三处声明且两处过期：`CLASSES` 六档（`importer.py:49`），而 `importer.py:3` 与 `:139` 写 `"RR|SR|AR|UX"`，`:168-169` 的报错也只列四类；`import_sources.py:13` 同样写四类；`rules/inbox_import.md:47` 写「四类」而下面表格列了六行 |

## 1. `story-flow.json` 契约字段：谁写 / 谁读

schema=3（`core/flow/state.py:24`，另一份字面量在 `flow/check.mjs:24`）。

| 字段 | 谁写 | 谁读 | 可疑点 |
|---|---|---|---|
| `schema` | `rounds.py:37` | `check.mjs:103`、`lifecycle.py:45`（回显） | 常量两处声明（`state.py:24` / `check.mjs:24`） |
| `status`（`in_progress`/`complete`/`story_written`） | `rounds.py:37`、`submission.py:239`、`lifecycle.py:144`、`rounds.py:141`（回退） | `state.after_complete:118`、`routing.py:278,297`、`check.mjs:84,269`、`story-build.mjs:119`、`context.mjs:179` | 值域在 Python 侧无枚举常量，四处字面量；JS 侧有 `FLOW_STATES`（`check.mjs:74`） |
| `rounds[]` | `rounds.py:111` | `state.round_gates:130`、`routing` 全篇、`check.mjs:111-208`、`story-build.mjs:125` | — |
| `rounds[].round` | `rounds.py:103` | `decisions.py:68,148`、`routing.settled_this_round:105`、`check.mjs:216,245` | — |
| `rounds[].imported[]` | `rounds.py:66,104` | 只有 `rounds.py:46` 自己读（算 `already`） | 只写不读（对外）：`rules/inbox_import.md:68` 把它当成可查的留痕，但无任何判据/渲染读它 |
| `rounds[].materials{path,digest}` | `rounds.py:32,50,87,230`(submission) | `routing.material_state:79`、`submission.py:145`、`check.mjs:125-131`、`story-build.mjs:125-131` | 轮次边界的唯一判据；`path` 字段只写不读（读者都硬编码 `AR/story-src/materials.json`） |
| `rounds[].positioning{scope_source,scope_text,sr_related_ars}` | `rounds.py:52`（来自 `inputs.read_positioning:76-121`） | `check.mjs:139-147,295-314`、`routing.py:427`、`lifecycle.py:48`（回显） | `scope_source` 只写不读：写入校验在 `inputs.py:92-98`，枚举在 `state.py:62`，无任何下游判据消费它 |
| `rounds[].scope_options[]` | `rounds.py:53`（来自 `inputs.read_scope_options:124-175`） | `decisions.py:78`、`inputs.chosen_dimension:178-188`、`check.mjs:149-154,183-194` | 第二级选项的唯一来源；`recommended` 字段无读者 |
| `rounds[].gates[]` | `decisions.py:130-141` | `state.last_gate:133`、`routing.scope_step:402,415,445`、`meetings._accepted:42`、`check.mjs:162-207`、`meetings.meeting_basis:115` | `by` 恒为 `"human"`（`decisions.py:132`），`check.mjs:202-206` 的「by 非 human」分支只能被手工编辑触发；`basis` 无程序读者（只进 `meeting_basis` 的摘要） |
| `split{decided,settled_round,scope_text,parts[]}` | `rounds.py:39`（初值）、`decisions.py:148-149` | `routing.settled_this_round:103-105`、`submission.py:200`、`check.mjs:215-266`、`rules/spec-rules.overlay.yaml:94,101` | `decided` 只有 `"none"`/`"split"` 两个取值，无「明确选了 carry_all」的记法——只能从 gates 反推（`check.mjs:276-279`）；`parts[].depends_on` 只在写入时查环（`inputs.py:339-354`），下游零读者 |
| `design{sha256}` | `submission.py:237` | 只有 `submission.known_identities:102` 与 `submission.py:216` 自己读 | 自用字段；docstring 自述「不是冻结比对基准」 |
| `design_generated_at` | `submission.py:238`、`rounds.py:41` | `check.mjs:285-287` | 唯一读者是一条「非空」检查 |
| `story_written_at` | `lifecycle.py:145`，`rounds.py:139` 撤销 | `lifecycle.py:47`（status 回显） | 无判据读者 |
| `story_src_digests{decisions.json,story-template.md}` | `lifecycle.py:154-156`（`STORY_SRC_FROZEN`，`state.py:39-42`） | `core/story/context.mjs:180` | 指纹算法两份实现：`state.ledger_digest:77-86` 与 `context.mjs` 的 `digestOf`（≈:199-203），注释自承必须逐字节同口径 |
| `archived{at}` | `lifecycle.py:197` | `state.after_complete:119`、`routing.py:42` | JS 侧零读者 |
| `materials_changed_after_complete{digest,at,note}` | `rounds.py:88-91` | 零读者 | `T/test_material_rounds.py:294` 是它唯一的消费者 |
| `reopened[]{at,from_status,from_round,story_registration_undone}` | `rounds.py:142-147` | 零读者 | `T/test_material_rounds.py:313` 断言留痕存在 |

只写不读汇总：`rounds[].imported`、`rounds[].materials.path`、`positioning.scope_source`、`materials_changed_after_complete`、`reopened`、`story_written_at`（除 status 回显）、`gates[].basis`、`split.parts[].depends_on`、`scope_options[].recommended`。

## 2. `routing.py` 的 `next` 全集与触发条件

`next_step`（`routing.py:262-336`）+ `meeting_step:339-365`、`scope_step:389-456`、`spec_stage_step:145-178`。共 19 个 `next` 值。

| `next` | 触发条件 | 可疑点 |
|---|---|---|
| `run_round` | 无契约或无轮次（:272）；材料指纹与本轮基准不符且未收口（:333） | 同一个值两条语义不同的来路 |
| `reopen_meeting` | `after_complete` 且盘上有未在第一级摆过的会议版本（:274-277） | 无测试 |
| `run_archived` | `status == "story_written"`（:278-296） | 归档之后仍然是这个值：`cmd_archived` 不改 `status`，流程无终态 |
| `import_materials` | `material_state.pending` 非空（`pending_import_step:82-94`，:308 与 :330 两处调用） | 无测试 |
| `refresh_round` | `status == complete`、有基准、`changed` 为真且 pending 为空（:310-316） | 无测试 |
| `spec_knowledge_use_init` / `spec_write` / `story_skeleton` / `story_chapters` / `register_story` | `status == complete` 且材料齐，按磁盘产物依次判（:154-178） | `story_skeleton`/`register_story` 无测试；四段文案各自拼接同一个 `SPEC_STAGE_ORDER`（:115-124），spec 阶段全部顺序硬编码在路由里 |
| `fix_meeting` | `meeting.inspect().problems` 非空（:347-348） | 无测试 |
| `refresh_meeting` | `inspect().stale` 非空（:349-353） | `T/test_meeting_material.py` |
| `read_meeting` | `inspect().missing` 非空（:354-358）或人表态后当前会议结果有缺口（`meeting_result_step:378-385`） | 一个 key 两种截然不同的作业 |
| `await_gate:meeting` | 有 `question` 且未签的话题（:360-364） | 见 §3 |
| `fix_gate_options` | 第一级侧车立不住且（无第一级记录或有未确认会议）（:406-408） | 触发面窄 |
| `await_gate:material_scope` | 第一轮无条件（:244 → :409-414）；或有未确认会议版本 `fresh`（:405,409）；或上一笔 rejected（:415-417） | 「rejected 重提」与「fresh 重停」两条都会重复停在同一级 |
| `run_analysis` | 本轮缺 positioning 或 scope_options（:427-436） | — |
| `await_gate:scope_decision` | 本轮无 `scope_decision` 记录（:439-442） | 只看「有没有记录」，不看 outcome |
| `await_gate:split_carrier` | 第二级选了非 carry_all 且本轮未定案（:445-446） | — |
| `generate_design` | 范围已定且 `design-draft.md` 不在（:449-453） | — |
| `run_complete` | 提取稿已在（:454-456） | — |

不可达 / 近似不可达：`frozen_inbox_note` 的「status==complete 且未归档」那一句（`routing.py:42-44`）不会从 `next_step` 的 complete 分支出现；`decisions.py:22-23` 的 gate 值域检查；`check.mjs:129-131`「与上一轮 digest 相同」。

## 3. 三级关卡 + meeting 关卡

`GATES = ("material_scope","scope_decision","split_carrier","meeting")`（`state.py:50`），JS 侧另写一份（`check.mjs:26`）。

| 机制 | 做什么 | 生产/消费 | 现役证据 | 可疑点 |
|---|---|---|---|---|
| 第一级值域 | `supplied`(request) / `confirm_scope` | 真源 `contracts/story-chapters.json → gates.material_scope.options`；读者 `inputs.material_options:30-39`（import 期读，:42）与 `check.mjs:39-58` | `T/test_spec_story_gate.py:88-142` | `inputs.py:42` 在 import 期读合同；合同坏掉时任何一次 `import flow.inputs` 直接抛 |
| 第一级停等判据 | 第 1 轮无条件停；第 2 轮起只在盘上有本级侧车时停 | `routing.material_gate_state:228-253` | `T/test_material_rounds.py` | 侧车校验在停等判据里顺带做，与 `decide` 的 `read_gate_options` 是同一函数两次调用 |
| 第一级补料校验 | `chosen ∈ MATERIAL_REQUEST_KEYS` 时核 pending/changed，不成立 → `rejected` + 退出码 2 | `decisions.py:119-127` | `T/test_s4_commit.py:536` | `rejected` 只此一处产生；`check.mjs:198-200`「rejected 必须有 reason」因此只对第一级有效 |
| 第二级 `scope_decision` | 选项只能来自契约 `scope_options` | `decisions.py:72-81`；`check.mjs:183-194` | `T/test_s4_commit.py` | 两侧各判一次「选项是不是现编的」 |
| 第三级 `split_carrier` | 选项由脚本从维度 `parts` 生成；定案时核「选的=记的」 | `inputs.split_carrier_options:191-202`、`decisions.py:100-116`；`check.mjs:215-266` | `T/test_s4_commit.py` | `--scope-text` 兜底（`decisions.py:103-108,147`）无测试、无文档 |
| 别级侧车拦截 | 第二/三级发现盘上侧车级别不符即拒 | `decisions.py:73-75,87-89` | — | 两段几乎逐字重复 |
| `meeting` 关卡 | 逐话题记人的裁决 | 选项来自 `meetings.topic_options:65-73`；消费 `meetings.pending_asks:57-62`、`meeting_basis:108-119`、`reader-review-task.mjs:140` | `T/test_meeting_material.py:452-495` | `state.py:49` 自述「不是第四级、不新增停等点」，但 routing 产出独立的 `await_gate:meeting`（:361）先于第一级，且第一级会因 `unconfirmed` 再停一次（:405-414、`decisions.py:52-58`） |
| 「摆过的选项必须留痕」 | `chosen ∈ options` | `decisions.py:94-97`；`check.mjs:169-174` | `T/test_meeting_material.py:465` | 成对判据 |

## 4. `materials/registry.py`：分类档、指纹与读者

| 机制 | 做什么 | 生产/消费 | 现役证据 | 可疑点 |
|---|---|---|---|---|
| 正文源集合 | 章节合同 `sources` 里 `derived != true` 的 | `registry.source_docs:59-66` ← `importer.contract_sources:69-77` | `T/test_contracts_single_source.py`、`T/test_material_rounds.py:200` | `spec/spec.md` 靠 `derived:true` 排除 |
| 目录源 | `ux-reference/`、`assets/` 逐文件登记 | `registry.SOURCE_DIRS:48`、`collect_materials:169-190` | `T/test_image_registration.py:135-161` | `ux-reference/README.md` 既是 UX 档落点（`importer.UX_DOC_TARGET:57`）又是材料：导入 UX 文档必然改材料版本 |
| 图片按内容归并 | 同 sha 多落点合成 `paths[]` | `collect_materials:178-188` | `T/test_image_registration.py:143` | 正文不归并，两套规则在同一函数里 |
| 会议条目 | 每版本一条，身份取 `original.docx` | `meeting.material_items:351-363` | `T/test_meeting_material.py:271-295` | 唯一 `kind` 不是 doc/image 的材料 |
| 材料版本 `digest` | `[kind, sha256, paths]` 摘要 | `compute_digest:200-208`；读者 `rounds.py:31`、`routing.material_state:79`、`submission.py:189`、`story-build.mjs:130` | `T/test_material_rounds.py:142-211` | caption/unused 故意不进摘要 |
| `digest_with` / `source_sha` | 换一份正文源 sha 再算版本 | `registry.py:211-230`；唯一消费者 `submission.py:163-190` | `T/test_s4_commit.py:216-250` | 为 S4 一个场景存在 |
| 「已并入」反算 | 重跑 inbox 转换与正文比对 | `collect_sources:238-303`；读者 `registry.pending:355-357` → `routing.material_state:78` | `T/test_material_rounds.py:503-531`、`T/test_material_delivery.py` | 每次 `build`（即每次 `status`/`round`/`decide`/`complete`）都重新解析 inbox 全部 docx（:275-278）；某份 `IMAGES` 档文档无图时 `convert_sources` 抛错 → 整个 `status` 失败 |
| 图片侧车 `.captions.json` | 按 sha 记 `caption` / `unused` | `registry.py:80-142` | `T/test_material_rounds.py:213-258` | 记全部图（含 `assets/`），落在 UX 目录里 |
| 清单读写 | `build`/`write`/`refresh`/`read` | `registry.py:306-352`；`read` 唯一消费者 `submission.py:147` | — | `read` 校验 `schema==1`，契约 schema 是 3：两套版本号 |

## 5. `importer.py` 的 docx→md 假设；`meeting.py` 现存解析

docx 转换假设（`importer.py:201-418`）：标题级别只认 `Heading|heading|标题 N` 三种样式名否则 `outlineLvl`；有序无序列表同渲 `- `；表格首行即表头、不处理合并单元格；图片只导出被引用的、同名不同源相互覆盖；未知结构白名单式，带文字或图的一律整份不导；落盘幂等按文件名排序拼接；覆盖备份 `.backup/<路径>-<秒>.md` 同一秒静默覆盖。

`meeting.py` 现存：版本目录与身份（:52-96）、原文行与摘要核对（:118-150）、逐行纠偏应用（:153-197）、引用范围校验（:224-237）、notes 结构自检（:240-348，明确不读 `finding` 判业务）、doc-refresh 引用核对（`flow/meetings.py:154-210` + `_plain_lines:122-142` + `_headed:145-151`）。

核实「固定发言正则已退出」：属实。遗留两处：`importer.py:504` 注释仍写「由 `cmd_import` 解析成发言结构」；`meeting.py:328-331` 对旧格式 `topics.json` 的残留检测无生产者，只有 `T/test_meeting_material.py:403` 在用。

## 6. `submission.py`：complete / 提取稿 / backup

候选定位 `resolve_candidate:25-40`；结构校验 `candidate_problems:69-86`（只看前五个序号，与 `rules/ar_design_init.md §3` 两处声明）；空骨架判定 `is_ar_skeleton:60-66`；「被覆盖的 AR 是谁」`known_identities:89-104`（LF/CRLF 手工枚举）；中断重试识别 `:163-178`（占约一半篇幅，正常一次成功不会走到）；材料未变核对 `:189-192`；范围已定前置 `:197-199`（与 `check.mjs:276-284` 判同一件事、形式不同）；备份 `:214-222`；写入顺序 `:212-242`。

## 7. `lifecycle.py`：story / archived 登记与指纹

`story` 前置 `:87-107`；四次 node `:108-142`；台账冻结指纹 `:153-156`（名单两处声明：`state.py:39-42` 与 `context.mjs:150-153`）；`archived` 前置与门禁 `:171-195`（无直测）；status 的会议枚举 `:41`。

## 8. `flow/check.mjs` 与 Python 侧的重复判据

| 判的同一件事 | Python 侧 | JS 侧 | 差别 |
|---|---|---|---|
| 契约 schema | `state.SCHEMA=3` | `FLOW_SCHEMA=3`（`check.mjs:24,103`） | 两份字面量 |
| 四个关卡名 | `state.GATES` | `FLOW_GATES`（`check.mjs:26,165`） | 两份字面量 |
| `carry_all` | `state.CARRY_ALL` | `FLOW_CARRY_ALL`（:60）+ 裸字面 `'carry_all'`（:152） | 三处 |
| 第一级值域 | `inputs.material_options` 读合同 | `materialChoices()` 读同一份合同 | 路径各算一次（`state.py:54` / `importer.py:60` / `check.mjs:40-41`） |
| `chosen ∈ options` | `decisions.py:94-97` | `check.mjs:169-174` | JS 只能被手工编辑触发 |
| `by == human` | `decisions.py:132` 写死 | `check.mjs:202-206` | 正常路径不可达 |
| `outcome`/`reason`/`at` | `decisions.py:118-135` | `check.mjs:195-201` | 同上 |
| positioning 三项 | `inputs.read_positioning:92-121` | `check.mjs:139-147` | 逐条同形 |
| scope_options 非空 + 含 carry_all | `inputs.read_scope_options:139-161` | `check.mjs:149-154` | 成对 |
| 第二级选项 ⊆ 分析选项 | `decisions.py:78-81` | `check.mjs:183-194` | 手段不同结论相同 |
| split carrier 恰一份 | `inputs.read_split_parts:322-326` | `check.mjs:254-266` | 成对 |
| `split.scope_text` 非空 | `submission.py:200-202` | `check.mjs:237-243` | 成对 |
| 「本轮范围已定」 | `submission.py:197-199` | `check.mjs:276-284` | 形式不同 |
| 「材料与本轮基准一致」 | `routing.material_state:61-79`（现算） | `story-build.mjs:125-131`（读落盘清单） | 输入不同；`sources.mjs:245-258` 又经 `client.mjs` 问 Python 拿第三份答案 |
| 「流程已收口」 | `state.after_complete:113-119` | `check.mjs:83-87` + `story-build.mjs:119` | 区间判、区间判、等值判 |
| 契约坏 JSON | `state.load:94-98` | `check.mjs:96-99,353-362` 两处读、两种 BOM 剥法 | — |

## 跨机制观察

A. 成对存在：契约常量、契约合法性（写入侧 vs 读取侧约 12 条不可达）、章节合同路径三处推导、台账指纹两份、「材料齐没齐」三入口两数据源、状态查询两条路径、spec 阶段顺序三处、推进授权声明两处。
B. 为测试/单一形态而存在：MEETING 全链只有一个 case 用；IMAGES 档无 case 用；S4 断点重试机制族；`--scope-text`；`topics.json` 迁移检测；`--preview` 零测试；`cmd_archived` 无直测。
C. 文档承诺/代码缺席：SKILL「新增停等点只有两处」vs 第四个 gate 与独立 next；`lifecycle.py` archived 承诺 vs JS 零读者；`importer.py:504` 过期；归类值域四类/六类；`story_flow.py` docstring 缺两命令；`SKILL.md:26` S5 终点 vs 契约无终态；侧车形状两处声明；`scripts/README.md` 约定表不全。
D. 零读者：见 §1 汇总；常量 `state.ANALYSIS`；产物 `evidence.md`（只有陈旧性检查与提示页）；分支 `routing.py:42-44`、`decisions.py:22-23`、`check.mjs:129-131,202-206,195-201`。
