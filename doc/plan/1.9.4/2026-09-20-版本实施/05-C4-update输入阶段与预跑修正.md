# 步骤 C4：update 的输入阶段与预跑修正（2026-09-21）

读者：维护实施者，新会话可独立执行。上游材料：本目录《裁定-update补料环节-2026-09-21.md》《T2预跑结果评审-2026-09-21.md》，本文已把它们的有效决定收齐，不必回读。方案位置：需求 C 的第四步，排在 T1 之后、正式 T2 之前。本步不启动真实 CLI。

## 1. 目标

一次 `/story update <编号>` 的入口与 init 同构：**先取输入、报告并问补料、人答了再定最终的材料变化，然后增量修订已有产物**。复用 init 的第一级关卡、材料链与轮次登记，不再有第二套材料机制；变化判定只看人和上游会动的八项；预跑暴露的四处装置与镜像问题一并修。

## 2. 有效决定（用户 2026-09-21）

| ID | 决定 |
|---|---|
| D21 | AR 单先触发上游系统更新检查并报告上游材料更新情况，同时问用户要不要补料；用户答了，再决定最终的材料变化。非 AR 没有上游，直接进入补料问询 |
| D22 | init 与 update 大量重合，同一功能不实现两遍，尽量复用；update 是本地已有数据上的增量更新，不是全部重做 |
| D23 | 变化判定范围只有八项：`RR/prd.md`、`SR/design.md`、`AR/design.md`、`inbox/`、`AR/story.md`、`AR/review.md`、`spec/spec.md`、`plan/plan.md`；其余是模型写的中间真源，不进判定 |

设计者同步把 D21–D23 补进 `spec/1.9.4/00` §2，不由实施者改 spec。

## 3. 已核事实

| 事实 | 位置 |
|---|---|
| prepare 只比监视集合、`AR/story-src/incoming/`、`--request`；不读 inbox、不调 `material_state` | `core/flow/update.py::cmd_update_prepare` |
| `material_state` 现成：`pending`＝inbox 里未并入正文的原件，`changed`＝材料指纹与本轮登记对不上，磁盘逐字比 | `core/flow/routing.py:60-78` |
| 第一级关卡：第 1 轮无条件停，之后只在盘上有本级侧车时停；侧车格式、`material_options`、`decide` 人签、`round` 登记本轮都现成 | `routing.py::material_gate_state:225-`、`scope_step:414-`、`flow/decisions.py`、`flow/rounds.py` |
| `update_in_progress` 分支只在收口态生效（要求 `after_complete`）；reopen 后状态回 `in_progress`，路由走常规路径 | `routing.py:285-294`、`state.py::after_complete:127` |
| 预跑里增量没有退回关卡，是因为模型**先 `round` 登记再 `reopen`**，本轮关卡已全部 accepted | 预跑评审 §3 |
| `_mirror` 复制整个需求目录（只跳过 updates/incoming/链接），含 `*/reports/` 的 64 位哈希文件名；套进检查点目录超 Windows 路径上限，auto 的 `checkpoint --point update` 首次失败 | `update.py::_mirror`、suite 20260920-1155 auto `last_error` |
| 监视集合现为十项（C1 返修加了六项中间真源） | `update.py::PRODUCTS` |
| `story.js fetch` 落点由调用方 `--out` 指定；C2 已让脚本渲染这条命令，落点 `AR/story-src/incoming/` | `adapters/story.js::cmdFetch`、`update.py::_fetch_command` |
| 第二段终点：契约 `update.last_closed` 换新 id，或 `.last-prepare.json` 在续跑后写下 `unchanged` | `run_case.py::update_round / last_prepare` |
| 两 Case 预跑第二段 24 / 26 分钟，0 停等、0 代签，三阶段按新 subject 重审 PASS；终态 `worker_lost` 因宿主未 conclude | 预跑评审 §1 |

## 4. 目标流程

```text
/story update <编号>
 ① AR 单：node story.js fetch <编号> <token> --out <单目录>/inbox      本地单：跳过
 ② python story_flow.py update --feature <编号> --action inputs        收集并报告，不建镜像
 ③ 材料关卡（复用第一级）：模型摆侧车（材料清单 + 一句缺口判断），问「要补料吗」→ 停等
 ④ 用户放料进 inbox 或答「不补」→ decide --gate material_scope 记原话 → round 登记本轮
 ⑤ python story_flow.py update --feature <编号> --action prepare       定输入：四类都空且比较完整 → unchanged 退出；否则建镜像开轮
 ⑥ 会议关卡按现有条件；范围沿用本轮结论不停
 ⑦ reopen → 改草稿 → chapter → complete → story 重登记            顺序硬规则：round 在 reopen 之前
 ⑧ --revalidate → 派 verifier → --sync-closure → update --action close
```

范围要变不在 update 内做：报「尚未完成：范围需重新拍板」并 close 保留项，用户走 `reopen` 进范围关卡；范围定了再起一轮 update。

## 5. 文件动作

路径相对 `doc/extensions/skills/story`；Core＝`scripts/core`；测试相对 `test/story`。

| 文件 | 动作 |
|---|---|
| `Core/flow/update.py` | **新增** `inputs` 动作：一个收集函数取四类输入（材料事实 `material_state`、八项对基准的差异、`--request`、上一轮是否开着），只报告，不建镜像不写记录；在契约写 `update: {stage: "inputs", inputs_at}`。**替换** `PRODUCTS` 为 D23 八项（inbox 由材料事实承担，不按哈希比）；`prepare` 复用同一收集函数，`unchanged` 条件加「pending 为空且材料指纹未变」，成立时清掉 `update.stage`；`after/` 只留八项。**替换** `_mirror` 的排除集：加 `*/reports/`、`.backup/`、`revalidation.json`。**删除** `INCOMING`、`_incoming`、prepare 复制暂存区、close 清空暂存区、`cleared_incoming`。`_fetch_command` 落点改 `inbox/` |
| `Core/flow/routing.py` | **替换** `material_gate_state`：`update.stage == "inputs"` 且 `inputs_at` 之后没有本级关卡记录时必停（同轮追加一笔）。**替换** `update_in_progress` 分支：条件改为 `update.open` 为真，不再要求收口态；action 先说 pending（有未并入原件先 `round`），再说「reopen → 改草稿 → chapter → complete → story」；收口态与 in_progress 两种状态都给这条 |
| `Core/story_flow.py` | `--action` 加 `inputs` |
| `scripts/adapters/story.js` | `fetch` 落点由调用方给的 inbox；取材回执改写 `AR/story-src/fetched.json`（inbox 只放正文文件，回执不能被当材料导入）。评审回稿文件名与内容形态由执行者核实导入链的分类器能把它归为「非正文材料」；分类器没有兜底类别时交回说明，不自造类别 |
| `scripts/README.md`、`../story-adaptation/SKILL.md` | fetch 合同：落点 inbox、回执位置 |
| `phases/update.md` | **替换**「一、先检测」为「零、输入阶段」：§4 的 ①–⑤，本地单跳过 ①，材料盘点按 `rules/init_analysis.md` S2a（含「不取的理由只能是范围不依赖它」）。**删除**「暂存区怎么用完」一段。**替换**动作 3：不变项要写理由，含「既有 Plan 为什么不用改」。**替换**决策登记一句：人已表态的议题登记为 settled 后，`review_mode` 不再向同一方发 confirm。动作 4 补范围变化路径（§4 末段）。顺序硬规则「round 在 reopen 之前」写进 ⑦ |
| `SKILL.md` | 停等真值表「材料关卡」一行加：update 每次必停一次，问的是补料 |
| `test/story/TEST.md` §5.9 | 第 6 步补：第二段会多一次材料停等，宿主按需求方身份答（auto：「就这份新版，按它更新」；car：「不补」）；第 7 步补：后评做完必须 `conclude`，否则终态 `worker_lost` |
| `test/story/cases/*/interaction-script.yaml` | 两 Case 加第二段材料停等的回话（上一行的两句） |

保护：`checkpoint`、`resume-update`、`finalize` 不动；review 两条判据与 `carriedOver` 不动；`decide --update` 不动；init 关卡与 `round`、`reopen`、`complete`、`story` 不动。

## 6. 输入、输出与失败

| 动作 | 输入 | 输出 | 失败 |
|---|---|---|---|
| `inputs` | 契约、材料清单、八项现状、上次已处理版本、`--request` | 上游/本地各份的新增/改动/缺席/读取失败；pending 清单；是否有开着的一轮；渲染好的 fetch 命令 | 上一轮开着 → 报 resume 不进；读不到 → 单列，不算删除、不算无变化 |
| 材料关卡 | 侧车 + 人答 | `decide` 人签记录、`round` 登记 | 侧车立不住 → `fix_gate_options`（现成） |
| `prepare` | 同 `inputs` | `unchanged` / `incomplete` / `changed` / `resume`；镜像与记录 | 镜像失败不开轮（现成） |
| `fetch` | 单号、token、inbox 路径 | inbox 里的正文文件、`AR/story-src/fetched.json` | 本地单拒绝；取不到不落占位件；读取失败三态分开（现成） |

## 7. 验收

离线（`-n auto --dist loadscope`，按「谁读这个文件」选，再跑全量）：

1. AR 单 `inputs` 报上游变化与 pending；本地单不调 fetch、只报本地。
2. `inputs` 之后路由停在材料关卡；`decide` + `round` 之后不再停；同轮追加一笔，不开新轮。
3. 用户不补且八项未变 → `prepare` 报 `unchanged`，契约 `update.stage` 清空，`.last-prepare.json` 写 unchanged。
4. inbox 放新原件 → `prepare` 报 `changed` 且 pending 列出；`round` 登记后再 prepare 按八项判。
5. 八项之外的文件（decisions.json、contracts.yaml）手改不触发 changed；plan.md 手改触发（保留既有用例，删除 decisions.json 那条）。
6. reopen 之后、`update.open` 为真时路由给「改草稿 → chapter → complete → story」，不给关卡。
7. 镜像不含 `*/reports/`、`.backup/`、`revalidation.json`；restore 仍能还原八项与草稿。
8. fetch 回执在 `AR/story-src/fetched.json`，inbox 里没有 json。
9. 范围变化：模型报尚未完成并 close 保留项，契约 `update.open` 归零、`last_closed` 记录保留项（用例只核脚本侧）。
10. incoming 相关用例全部退出；`test_update_checkpoints` 不变。

手工实跑：在 `ext_workspace` 夹具上各走一遍本地单与 AR 单（伪需求系统）的 ①–⑧，交回命令与输出。

## 8. 预算

机制侧：新增 `inputs` 与收集函数约 +40、路由两处约 +15、镜像排除 +5、方法页与 SKILL 约 +30；退出 incoming 相关约 −35、六项监视 −6。净约 +50。scripts_py 在途 2800、总 12270 已签，够用；实测差额交回如实报，target 在 T2 收口时重签。

## 9. 交回

按既有格式：每处落点「谁产出、谁消费、失败怎么办」；退出清单逐处可核；离线结果与手工实跑记录；预算实测。交回后设计评审，通过即启动正式 T2（两 Case 同一批刺激，按 TEST §5.9 八步，第二段多一次材料停等）。

## 10. 不做

- 不建第二套材料台账或暂存区；不改 init 的关卡集合；不升 `flow.schema`。
- 不改 framework、不改仓根 CLAUDE.md。
- 不动预跑那批 suite 的产物；它们作预跑证据保留，是否回流 `-update` 由用户定。
- 不在本步造新的刺激材料；正式 T2 复用现有两份。
