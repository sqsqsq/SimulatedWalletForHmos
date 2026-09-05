# 批次 6 · 零改动适配 · 进展跟踪

| 项 | 值 |
|---|---|
| 状态 | **步骤 1 已实施（四个提交），等评审；步骤 2 方案待用户确认** |
| 起点 | 上游 `0143e21`（`origin/main` `ea2365d1`）；本仓 story 分支 `framework/` = `85e266f` + 18 处 |
| 用户裁定 | framework 不改逻辑、只允许 opencode 登记两处且不交上游；`.opencode/` 只是本仓测试装置，内网用 codex；extension 支持批次 5 全部功能 |
| 方案文件 | [00-总览.md](00-总览.md)；`steps/01`、`steps/02` |

## 步骤状态

| 步骤 | 状态 | 评审报告 |
|---|---|---|
| 1 对齐上游与能力落回 | **已实施待评审**（55b24abb / 9c0a6148 / 18581b0a / 5e0230a1）。原稿问题：B1 读者审查两条路（codex 双审、post_check 里 framework 来源是死分支）、B2 verifier 定义只收 request JSON、B3 指纹未定义、B4 同步漏物化目录；§5/§6 预算矛盾；退场清单缺项 | [reviews/01-对齐上游与能力落回.md](reviews/01-对齐上游与能力落回.md) |
| 2 步骤 16 返修与追加（原批次 5 步骤 17） | 方案待确认；起点是步骤 1 落地后的实测预算 | — |

## 事件日志

- 2026-09-05 上游发布 `0143e21`：verifier 报告真源改回调用方写出的 MD，`verifier_capability` 矩阵换布尔 `verifier_subagent`（claude / codex / codeagent 登记，opencode 未登记），`on_context_load` 明确只进 verifier 上下文，行为规约加第 8 条。用户裁定 framework 0 改动、能力落回 extension。执行会话写 `steps/01`。
- 2026-09-05 评审 `steps/01`（reviews/01）：事实全部核对成立；设计三处必修——读者审查要一条路（推荐：扩展在 ⑤b 承载、`story_reader_review` 搬出 overlay、`pre_verifier` 不再注入、`verifier-report.mjs` 单来源）、任务书自足并沿用 framework 终态块、指纹定义为 story 正文 sha256；同步范围补物化目录（24 文件，`.claude/settings.json` 仍登记已删钩子）；§5「回落 8600」删；退场清单补内网升级件、overlay/任务书里的插件字句、五份受影响测试；披露装置上 framework verifier 不跑、知识轴待内网。
- 2026-09-05 批次 5 `steps/17` 迁为本批次 `steps/02`：R35 随插件退场删除，其余 R33 / R34 / M02 与 S5–S7 原样；六跑判据里「插件发布 canonical」换成读者审查报告三条；预算起点改为步骤 1 落地后实测。
- 2026-09-05 用户指定评审会话直接改步骤 1 方案。重写要点：读者审查一条路（overlay 的 `story_reader_review` 搬到 `reference/reader-review.md`，`pre_verifier` 不再注入，framework 的 verifier 只审 spec）；任务书自足（给定 `subject_id` = story 正文 sha256、只读要求、沿用 framework 终态块），派宿主只读子代理而非 `verifier`，装置的 `.opencode/agent/verifier.md` 加第二输入形态；`post_check` 单来源四条核对，缺报告即 FAIL；同步范围补物化目录（本仓钩子与 `85e266f` 模板逐字节相同，可直接取上游）；退场清单补五份测试、内网升级件、TEST.md 两节；预算 8856 → 约 8860；六跑披露知识轴待内网。§0、§1、§3.1 drift、§3.4 插件与补丁、§3.5 保留原稿。
- 2026-09-05 外部评审五条：① 失败恢复路径——机制已有（`story_flow.py reopen` 是唯一回退出口，撤销成文登记），方案只是没写，补上并把「只审一次」改为「指纹未变不重派」；② 指纹只算 story 正文——成立，改为复用登记时已写入 story-flow.json 的 materials.digest / decisions 指纹 / story_written_at，spec 不进（由 ⑫b 拦真会影响 story 的变化）；③ blocking 非空却 PASS——成立，改为 blocker_count 等于 blocking_findings 条数且 PASS 当且仅当零；④ 批次完成条件不能只凭六跑——成立，00-总览加四条条件与验证里程碑；⑤ 步骤 2 来源标记两种写法——成立，统一为「%% 图源 <文档> §<节> #<序>」指向直接上游、只有围栏首行算。预算改口径：8860+64≈8924 超 24 行，写成待实测与用户裁定。
- 2026-09-05 用户三条裁定：读者审查不在扩展里另建派发链（AGENTS §3）；opencode 参考 claude / codex 的方式登记，只登记不改逻辑；不交上游，story 分支支持即可。评审第二次重写 steps/01：drift 收到 2 文件长期放行；overlay / pre_verifier / 任务书不动；`verifier-report.mjs` 改读 `summary.verifier_report` 的 MD、从 post_check 挪到归档门（原位置在正常流程里永远 NOT_APPLICABLE）；overlay severity MAJOR→BLOCKER 与任务书对齐；⑦ 看 NEXT 行、⑧ 补 reopen 恢复路径；manifest 1.6.0；预算 8856→约 8840。reviews/01 加后记。
- 2026-09-05 外部第十二轮三条核实成立：① 归档顺序是 check → 上传 → 登记，本地单无归档——落盘核对改进 `story-build check`（未派 N/A、已派未落盘 FAIL、在则判），远程单在上传前拦、本地单在 ⑧ 闭环后跑 check 作交付门；framework 在 verifier 之后没有钩子点（post_verifier 在 harness 内触发）。② 上游 PASS 只进汇总表、明细只列非 PASS——扩展不设例外：PASS 汇总行证据非空即可，非 PASS 明细带两键。③ summary.json 在 `<phase>/reports/`，改口径。文档同步：总览完成条件改两文件差异；步骤 2 起点 8840、超约 4 行。
- 2026-09-05 外部第十三轮三条成立：① 落盘核对靠 summary 在不在推断阶段是错的——改为 `check`（恒 N/A）与 `check --deliver`（先 spawn framework `check-receipt`，退出 0 再核报告内容）两个入口同一实现，归档 ① 与本地单 ⑧ 都用 `--deliver`；② 交付门通过 = 回执通过且报告内容三条，FAIL 报告只算解析通过；③ 步骤 2 verifier 判据同步 PASS 新格式。用户裁定预算上限改为测算值 + 100：步骤 1 8940、步骤 2 起点 + 164，写进 mechanism-budget.yaml。

- 2026-09-05 执行会话实施步骤 1，四个提交。实施前核出方案五处要修，都按修正后的做法落地：
  ① `git checkout origin/main -- .cac` 会冲掉 `.cac/commands/story.md`（story 扩展入口），
  checkout 与验收路径收窄成 `.cac/agents .cac/hooks .cac/settings.json`；
  ② 上游 opencode `commands: null`，只加一行布尔的话子代理模板没有物化落点，
  adapter.yaml 同时补 `commands.subagents`（仍是两个文件，但「只加一行布尔」不成立，
  drift 理由如实写成「登记 + 子代理物化落点」）；
  ③ 五个 overlay 的注释都指着已退场的 `author-context.ts`，一并改写；
  ④ `--deliver` 在 verifier plan 为 `disabled` 的宿主上报告本就不存在，判 NOT_APPLICABLE 而非 FAIL；
  ⑤ `framework/agents/claude/templates/hooks/record-verifier-report.mjs` 上游已删、checkout 不会删它，
  §3.1 的 `git rm` 清单漏了这一件。
- 实施结果：framework 与物化目录同 `origin/main` 的差异恰好是登记那两个文件；离线全量 633 passed；
  失效形态 FAIL 0；`adapt-scan --check` 通过；预算 8909（上限 8940）。
  `resolveVerifierPlan` 实测：`verifier_subagent=true → enabled/policy_required`，
  缺省 → `disabled/adapter_has_no_reviewer`。
- 预算与方案 §6 的差异（已具名记进 `mechanism-budget.yaml`）：scripts_mjs 实际 +37（方案估 +12），
  多出来的是交付门的接线与三条失败路径；hooks_mjs 净 +7（方案估 −30），
  读者审查的报告读法换成汇总表解析后与旧的 JSON 解析等量，没有省下来。
  hooks_mjs 2741 仍高于 target 2700 共 41 行，挂账等收口裁定。
