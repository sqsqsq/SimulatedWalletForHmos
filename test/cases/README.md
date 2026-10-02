# Case 编写规则

> 本目录是被测输入：改任何 Case 单独记一笔账。运行协议见 [../TEST.md](../TEST.md)，本文只写 Case 本身怎么写。

## 起手只用命令，诉求在关卡上说

- `prompt` 只写 `/story init <单号>`；配了第二段的，`update_request` 只写 `/story update <单号>`。
- 材料在哪、开过什么会、做到哪一步、要谁拍板，都不写进请求：取材、索要补料、发现冲突与交付选择正是要观测的行为。
  模型在流程里问，宿主在那一关按 `interaction-script.yaml` 的立场答；第二段的新稿与回稿由模型自己取得。
- 诉求不预塞：模型走到关卡时已在几十步之外，预塞测出来的是记忆衰减，与关卡交互无关。

判据在 `../tests/test_multi_scenario_cases.py` 与 `../tests/test_harness.py`。

## 终点归驱动器观测

- `run_case.py` 按 `end_at` 观测终点（`test/scripts/end_target.py`），**改终点只改这一行**，写法与回显字段见 TEST §4.1。
- 业务终点由宿主在交付关卡上选（送审、实现方案等），终点要与那条立场一致：选送审的写 `{kind: story, delivery: submitted}`，
  选实现方案的写 `{kind: phase, phase: plan}`。
- 不从 Story 起手的 Case，需求交付之后由驱动器指名下发下一步（`continuation_reply`，「现在执行施工单位 X 的 plan 阶段」）。

## 材料分三处，按真实体验投放

| 目录 | 是什么 | 什么时候到 |
|---|---|---|
| `<id>/system/` | 需求系统上挂着的单据（一个子目录一张单，含 `detail.json` 与正文 md） | 起跑时复制到系统临时目录（**workspace 之外**，模型 `ls` 看不见），被测侧只经环境变量知道它在哪 |
| `<id>/workspace/` | 起跑那一刻需求目录里就有的东西 | 起跑时 |
| `<id>/supplements/` | 人手上备着、**要来的**那几份 | `deliver: start` 起跑时；`deliver: on_request` 在模型第一次停在材料关卡时全部一次交出（TEST §3.2） |

补料条目可以带 `kind: meeting`，表示这份 docx 是会议的语音转写：静态检查据此不要求它内嵌图片。
这个键只给测试域用，投放时被测模型看到的仍只是一份 docx，归类由它自己判。
各话题该有的去向写在 Case 根下的对照答案里（如 `auto-topup/meeting-answer-key.md`），不放进三处材料目录。

**需求系统只承载 md，不承载图片**。图片只有一条路进来：人给的文档（docx）里内嵌，导入时抽出来。多留一条路，
「归档件里的图能不能打开」测的就不是真实链路了。

材料由**宿主**在回话时带出去：`reply --text "…" --deliver <文件名>`，文件先落进收件箱，那句话才排进队列（TEST §3.2）。
规划条目的 `deliver:` 只是告诉宿主「这一关该把哪份交出去」，它自己不投（`planned_deliver`）。起跑时收件箱里只有说明书；
提前把材料铺满，「它会不会发现材料不够」就永远测不到。

## `interaction-script.yaml`

- 写的是**需求方的立场**，不是台词；`text` 按立场写，宿主用自己的话说出来（TEST §3.2）。
- `expected_phase` 是那句话的阶段前提（`story` / `design_handoff` / 原生阶段 / `archived`，与 TEST §3.1 的阶段同一套，poll 里回显为 `planned_phase`），由宿主判断这话现在说出口通不通；
  `expected_kind` 是等待类型，与当前这一问对不上时 poll 不展示这一条。
- 一条只答一个关卡的一个问题；立场不替模型说出本该观测的识别，不提前泄露定源或处置。
- `expected_turn` / `expected_phase` 与实跑对不上时，先按本该说的话回，跑完再按实跑顺序校准（TEST §3.4）；不为对上脚本改话术。
