# 03 CLI 测试报告（知识贯通与评审件精简轮）

> 状态：**实跑进行中**（本文随实跑推进逐节填写；结论只覆盖已取证部分）
> 实施提交：`4412a78b` + `465aa7aa`　｜　对照基线：上一轮 suite `story-suite-20260824-091443`（提交 `6bf074a7`）
> 本轮 suite：第一次 `story-suite-20260824-121823`（**因 framework 缺陷中止**）；
> 正式 suite `story-suite-20260824-130828`，2 Case 并行，隔离 workspace，目标终点均为 **plan**

## 1. 离线验证（实跑前，已完成）

### 1.1 全套脚本

| 项 | 结果 |
|---|---|
| `node --check` 全部 `.mjs`（含 6 个新增模块） | 全通过 |
| `python -m unittest discover -s test/story/tests` | **128 项通过**（较上轮 +6，新增驱动器死锁回归） |
| `python -m unittest discover -s tools/cli/tests` | 16 项通过 |
| `python -m compileall -q tools/cli test/story/scripts` | 通过 |
| `run_multi_case.py plan --isolated-workspaces` | 通过 |

### 1.2 机制层负面断言（提交前固定扫描）

| 断言 | 结果 |
|---|---|
| 机制层（`knowledge/` 外）零域前缀字面 | 0 命中 |
| 机制层零测试 Case 单号／业务名 | 0 命中 |
| 机制层零架构层名字面 | 0 命中 |
| 「兼容性自检 / 两张表 / 编号速查」残留 | 仅剩解释性历史注释与向后兼容标记 |

### 1.3 构造产物门禁演练（证明门禁**拦得住**也**放得行**）

| 演练 | 输入 | 期望 | 实际 |
|---|---|---|---|
| P1 | 现有 AR90006 冻结（无 instance/roles/landing，anchor 自引用） | 逐条 BLOCKER | ✅ 10 条问题全部点名 |
| P2 | 补齐 instance + 4 角色 + landing，实体真实存在 | PASS | ✅ |
| P3 | 角色指向不存在的类 | BLOCKER | ✅「契约里找不到 NotExistOperates」 |
| P3b | landing 指向不存在的成员 | BLOCKER | ✅「SampleRepository 里没有成员 nosuch」 |
| P3c | anchor 指回知识决策章自己 | BLOCKER | ✅「那是声明本身，不是落点」 |
| P4 | 现有 AR90006 story-src（重复图片、DEC-005 settled+无上游依据） | build 失败并点名 | ✅ 两处行号 + DEC-005 |
| P5 | 现有 AR90004（附录域覆盖、长段） | 附录判据生效 | ✅ 附录按前缀判定通过；长段 WARN 4 段 |
| P6 | review 报告缺一条义务裁决 | BLOCKER | ✅ 点名 SEC-01 |
| P6b | 补上裁决行 | PASS | ✅ |
| P7 | ut 报告缺义务且无「不适用」 | BLOCKER | ✅ |
| P7b | 写「不适用于 UT + 理由」 | PASS | ✅（显式不适用可接受） |
| P8 | testing 报告缺行 | BLOCKER | ✅ |
| P8b | 写「待验证 + 阻塞原因」 | PASS | ✅ |
| P9 | 新增规约域 `ZZ` + manifest 登记 + 矩阵行，**不改任何 `.mjs`** | 全链自动生效 | ✅ 域清单/前缀/字典/附录覆盖判据均含 ZZ |
| P10 | 驱动器：4 种 verifier 命名、阶段预算、awaiting 间隔 | 单测通过 | ✅ |

**P9 是本轮适配能力的关键证据**：新增一个规约域后，编号字典、附录逐域覆盖、下游账本、
域前缀扫描四处同时生效，机制层零改动。

### 1.4 上一轮遗留缺陷的修复验证

| 缺陷 | 修复验证 |
|---|---|
| D1 驱动器只认单一 verifier 文件名（空转 27 轮） | `verifier_report()` 认 6 种命名；AR90004（`verifier-report.yaml`）现判为**已闭环** |
| D1' 阶段预算只求和当全局上限 | 循环按 `next_phase` 计数，超 `PHASE_TURNS` 即 `stop_reason=phase_turn_budget_exhausted` |
| D2 awaiting 跨唤醒响应 | poll 返回 `question` 原文 + `case_inputs_hint`；有等待时 `next_interval_sec` 强制 15 |

## 1.5 实跑中发现并修复的 framework 缺陷（第一次 suite 中止的原因）

第一次起跑 25 分钟后中止：两个 Case 都卡在 `framework_integrity` BLOCKER 上反复排查。
定位后发现是**一个已被解决过、又在 story.2.0 回退中被误删的缺陷**
（归档：`AIDefectHelpler/docs/archive/需求开发/framework缺陷-spec阶段无法闭环.md`）。

### 1.5.1 缺陷链

| 层 | 事实 |
|---|---|
| 根因 | `capability-resolution.ts` 的 `derive.requirement` 只认 goal 入参与 lite 轨 `change.md`，**不认 L2 完整流程的 RR/SR/AR** |
| 后果 | capability blocked → functional 轴强制 UNVERIFIED → summary INCOMPLETE → `check-receipt` 拒绝闭环，重跑多少次都一样 |
| 掩盖 | 上一轮实跑里被测模型**伪造了一个 `change.md`**（L1 产物）塞进 L2 需求目录骗过 provider（创建于 10:40，spec 中途），capability 因而显示 resolved——缺陷一直活着，只是被产物污染掩盖 |
| 叠加 | `RELEASE-MANIFEST` 声明的 `harness/trace/trace.schema.json`、`gap-notes.template.md` 自 2026-05-25（`744382be`）起就不在仓里；`harness/state/.gitkeep` 被测试的 workspace 复制丢弃 → `framework_integrity` 判 3 处漂移 |
| 复制缺陷 | `WORKSPACE_EXCLUDED_DIR_NAMES` 用**裸名** `"state"` 排除运行态目录，连带丢掉发布件声明的占位文件；裸名还会误伤任何叫 `state` 的产品源码目录 |

### 1.5.2 修复（提交 `c658a750`）

- **治本**（归档的建议一，而非原先应用的建议二 `on_missing: prune`）：`derive.requirement` 增补
  `AR/design.md` / `RR/prd.md` / `SR/design.md`。选建议一的理由是归档自己写的——
  `prune` 会让需求真缺失时**静默放行**，丢掉这条约束的保护价值。
- `framework.config.json` 恢复 `integrity.drift_allowlist` 四条 `{path, rationale, approved_by}`
  真人具名审批（走 framework 自身的合法热修通道，非自批）。
- 从 git `744382be^` 精确还原两个被误删的 framework 文件。
- workspace 复制改为**按路径**排除 `framework/harness/state` 并保留 `.gitkeep`。
- 新增 4 条回归测试，防止再次被回退误删而无人察觉。

### 1.5.3 验证（正反双向对照）

| 对照 | `capability_spec_requirement` | `readiness_signals` |
|---|---|---|
| 有 AR/RR/SR（正常 L2，且**已删除伪造的 change.md**） | **resolved** | **0 条** |
| 移走 AR/RR/SR（反向对照） | **blocked** | **`quality_axes_projection_mismatch`**（与归档记载逐字一致） |

反向对照同时证明两件事：确实是本次改动在起作用；且 `on_missing: fail` 的保护价值**保住了**。
`framework_integrity` 已从失败列表消失；`npx tsc --noEmit` 通过；132 项单测全绿。

## 2. 实跑事实

| Case | feature | 目标终点 | 实际到达 | 中止原因 |
|---|---|---|---|---|
| split-interactive | AR90006 | plan | **spec（产物齐备，形式闭环未完成）** | 被测 CLI 凭据 401 |
| pattern-image-review | AR90004 | plan | **spec（同上）** | 被测 CLI 凭据 401 |

**中止原因是外部凭据，不是被测扩展也不是 framework**：两 Case 在**同一秒**（14:02:14）以
`exit_code=1 / failure_kind=command_failed` 结束，事件流里的根因是

```
APIError 401 Incorrect API key provided（aliyun model-studio / dashscope）
```

被测 CLI 用的 provider 是 `bailian`（`~/.config/opencode/opencode.jsonc` →
`provider.bailian.options.apiKey`，另有 `~/.local/share/opencode/auth.json` 的 `alibaba-cn`），
其 key 是 `sk-ws-…` 形态的临时凭据，运行到 53 分钟时失效。**需人工更新凭据后才能重跑到 plan。**

各阶段闸门实况（两 Case 一致）：

| 阶段 | 执行 | 闸门 |
|---|---|---|
| story | completed | `post_check` pass、`merge_story_check` pass、`story_build_check` **fail** |
| spec | completed | `harness_spec` **pass**；formal closure `open`（receipt 未填完就断了） |
| plan | **not_reached** | `harness_plan` skipped |

`story_build_check: fail` 是**既有的源漂移检查正常工作**：模型在 build 之后又改了 `spec.md`，
装配指纹与源对不上。它会在下一轮 build 时自愈，被 401 打断来不及重跑，与本轮改动无关。

## 3. 判据结论（02-行为验证计划 逐条）

### 3.1 已取证（story / spec 段，两 Case 均验）

| 判据 | AR90006 | AR90004 | 判定 |
|---|---|---|---|
| B16 review 精简 | 无「怎么填」；编号对照 **15 行** | 无「怎么填」；编号对照 **21 行** | ✅ |
| B16' 对照表含义正确 | AC-1…AC-6、F1…F10 逐条给含义，文字取自 spec 原文 | 同 | ✅ |
| B16'' 无「无上游依据 + settled」 | 0 | 0 | ✅ |
| B17 附录单表 | 16 行条目级表；兼容性自检 0、编号速查 0 | 同 | ✅ |
| B18 图片唯一 | 引用 2 / 唯一 2 | 引用 1 / 唯一 1 | ✅ |
| B18' 无编号清单段 | 0 | 0 | ✅ |
| B19 决策引用 | 截断 0、叠字 0 | 截断 0、叠字 0 | ✅ |
| B23 spec §7 派生出口 | — | §7.5「应用域约束要求」11 条命中条目逐条一行 | ✅ |
| B27 派生不枚举（新增域零改码） | 离线 P9 已验 | — | ✅ |
| D1 凭证文件组 | — | 本轮 verifier 落名 `verifier-spec.md`，被正确识别 | ✅ |

### 3.2 未取证（plan 未到达）

B20 先冻结后设计、B21 模式角色投影、B22 义务落点实体、B24 下游三段式、B25 去重收敛、
B26 显式不适用——**本轮无实跑证据**。其中 B20–B22、B24、B26 已在离线构造产物演练
（P1–P8）中双向验证过门禁行为，但「模型会不会照做」仍需实跑。

## 4. 本轮发现的缺陷

| # | 级别 | 内容 |
|---|---|---|
| **F1** | 中（被测扩展） | **附录「编号」列粒度未被守住**：AR90004 写成域前缀 `SEC`/`DFX`/`DM`，没到条目粒度 `SEC-01`；AR90006 写对了。根因是 `appendixProblems` 的逐域覆盖判据**按前缀**判，前缀写对就放行。判据要收紧为「非整域行必须是 `<前缀>-<序号>`」 |
| **F2** | 低（被测扩展） | spec §7.1–7.4 与新增的 §7.5 部分重复（SEC-01/UX-01/DFX-01 两处各写一次）。模板已写「规约派生的一律进 §7.x」，模型未完全采纳 |
| **F3** | 中（测试基础设施） | **非 story 关卡的等待不被识别为 adaptive**：预置脚本只覆盖 story 的 3 个关卡，spec 阶段的关卡（术语映射表确认）走不到脚本，但 `interaction_state` 显示 `waiting`、`adaptive_reply_requests` 为空，宿主告警不触发——实测白等 3.4 分钟。已改用「按等待时长告警」绕过，根因待修 |
| **F4** | 中（测试基础设施） | **隔离通道不闭合**：被测模型可按绝对路径读到兄弟 Case 与历史 suite 的 workspace（同在 `%TEMP%/sw-story/` 下）。本次实读的是 framework 发布清单与 harness state，未触及其它 Case 的需求产物，但通道存在，违反 TEST.md §0.1 |
| **F5** | 高（环境，已修） | framework spec 闭环缺陷复活 + workspace 丢占位文件 —— 见 §1.5，已修复并提交 `c658a750` |
| **F6** | 外部（阻断） | 被测 CLI 的百炼 API key 失效导致两 Case 同秒中断，plan 未达 |

## 5. 与上一轮基线的量化对照

| 指标 | 上一轮（`0824-091443`） | 本轮（`0824-130828`） | 变化 |
|---|---|---|---|
| 附录结构 | 4 块（自检表 / 域级表 / 详情 / 速查），COMPAT 登记 2 次 | **1 张条目级表** | ✅ 去重 |
| review 编号对照 | **无**（交集恒空） | 15 / 21 行，含义取自原文 | ✅ 修复 |
| 图片重复 | AR90006 **1 处** | **0 处**（两 Case） | ✅ |
| 编号清单段 | AR90004 **3 段** | **0 段** | ✅ |
| 决策引用坏句 | 截断 + 叠字若干 | **0** | ✅ |
| 流程图 | 1 / 1 | 1 / 2 | ◐ |
| **有序列表** | **0 / 0** | **4 / 0** | ◐ AR90006 首次采用 |
| 厚度（story 正文 / spec） | 0.67 / 0.60 | 0.63 / 0.70 | ◐ 仍薄 |
| 长段（>200 字） | 1 / 4 | **7 / 10** | ❌ **变差** |
| 跨章重复长句 | 未观测 | AR90006 **2 处**（新 WARN 抓到） | 新观测项 |
| 到达阶段 | plan / spec（D1 死锁） | spec / spec（外部 401） | — |

**长段变差需要注意**：本轮两 Case 的长段数都上升（7 / 10）。一个可能的解释是附录改成
条目级单表后，正文里的「结论或落点」被写得更长；另一个是写作指引这一轮加了不少条目，
稀释了段落纪律那几条的权重。这一项下一轮要单独盯。

## 6. 结论与下一轮建议

**已确证有效**：评审件与附录的去冗余（B16/B17/B18/B19）四项在两个 Case 上全部达成，
且质量可查——review 的编号对照真的解释了 F/AC，附录真的收敛成一张条目级表，
图片重复与编号清单段这两类上一轮实测存在的问题本轮为零。spec §7 的派生出口也按预期产出。

**尚未证明**：知识三段式的核心（plan 冻结投影为契约实体、下游逐条留证）**本轮没有实跑证据**——
两 Case 都没到 plan。离线构造演练证明了门禁「拦得住、补齐即放行」，但模型行为未验。

**下一轮必须先做的三件事**：

1. **更新被测 CLI 的百炼凭据**（用户侧），否则跑不到 plan；
2. 修 F1（附录编号粒度判据）与 F3（非 story 关卡的等待识别）——两者都会直接影响下一轮取证质量；
3. 重跑两 Case 到 **plan**，补齐 B20–B22、B24–B26 的实跑证据。

长段回升（F 未编号，见 §5）与 AR90004 有序列表仍为 0，属「指引已写、模型未照做」，
按冻结需求 02-C2 不设形式配额，继续以 WARN 观测，不加硬门禁。
