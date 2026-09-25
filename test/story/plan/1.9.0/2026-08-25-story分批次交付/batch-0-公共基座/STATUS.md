# 批次 0 · 公共基座 · 进展跟踪

| 项 | 值 |
|---|---|
| 状态 | 已完成（回退验收 + 测试域恢复 + 台账设施 + 兼容矩阵） |
| 需求基线 | [../00-总方案.md §2](../00-总方案.md)、[../01-全批次需求记录.md G1](../01-全批次需求记录.md) |
| 交付物 | 本文件（回退验收登记）+ `test/story/regression/failure-modes.yaml` + `test/story/scripts/check_failure_modes.py` |
| 回写 | 批次 1 收口时一并入册 ../02 / ../03 |

## 1. 回退验收（`19977c98` = 1.0 基座）

> 坑 #24：回退门禁只查 `doc/extensions` 会看不见四宿主入口与 untracked，故四项分别取证。

### 1.1 tracked diff（产品侧回退范围）

```
git diff --stat 19977c98 HEAD -- doc/extensions .cac/commands/story.md .claude/commands/story.md \
  .codex/skills/story/SKILL.md .opencode/skill/story/SKILL.md
→ 输出为空
```

**结论**：`doc/extensions/` 与四宿主 story 入口的 tracked 内容与 1.0 逐字节一致。

### 1.2 untracked / ignored 清单

`git status --short --ignored -- doc test .cac .claude .codex .opencode`（2026-08-25）：

| 路径 | 性质 | 处置 |
|---|---|---|
| `.claude/settings.local.json` | 个人设置 | 保留（不属回退范围） |
| `.opencode/{.gitignore,node_modules/,package*.json}` | 宿主运行时 | 保留 |
| `doc/features/` | 历史产物（当前只有 DTS90006） | 保留（实施前基线） |
| `test/story/plan/`、`test/story/spec/` | 方案与冻结需求 | 保留（测试域，不回退） |
| `test/story/{scripts,tests}/__pycache__/` | 编译缓存 | 无害 |

**无遗留 untracked 的 2.x 产品件**（`doc/extensions` 下零 untracked）。

### 1.3 目标文件树

`git ls-tree -r --name-only HEAD -- doc/extensions | wc -l` → **43** 个文件，与 1.0 一致。
其中 **不存在** `knowledge/design-patterns/`、`hooks/shared/`、`hooks/{plan,coding,review,ut,testing}/`、
`rules/*.overlay.yaml` 之外的 2.x 新增件、`releases/`、`skills/story-adaptation/` —— 均为 2.x 引入，回退后正确消失。

### 1.4 四宿主入口内容

| 入口 | description 首句 |
|---|---|
| `.cac/commands/story.md` | 需求开发流程编排（story init / archive / restore / review / help） |
| `.claude/commands/story.md` | 需求开发流程编排（story init / archive / restore / review / help） |
| `.codex/skills/story/SKILL.md` | 需求开发流程编排——story init / archive / restore / … |
| `.opencode/skill/story/SKILL.md` | 需求开发流程编排——story init / archive / restore / … |

四份均为 1.0 形态（`/story adapt` 未出现，符合「adapt 归批次 3」）。

### 1.5 1.0 命令兼容用例

`node doc/extensions/skills/story/scripts/story.js help` → 输出五命令工作流程
（`init` / `/spec` / `archive` / `restore` / `review`），CLI 契约 `<init|archive|restore|review|help>` 可用。

## 2. 测试域恢复（用户裁定，2026-08-25）

回退误将 `test/story/**` 一并带回 1.0；按用户裁定从 `backup/story-2.x-20260825` 恢复。

| 文件 | 恢复内容 |
|---|---|
| `AGENTS.md` 62→114 行 | §2 维护不变量（01-G7 引用源）、§2.1 知识与机制引用边界、§2.2 知识编写要求、§1 领域心智模型、§4 维护红线 |
| `TEST.md` 169→194 行 | `awaiting_reply` 当轮回复纪律、阶段闭环凭证认一组 verifier 报告文件名、`stop_reason` 语义、清理残留不阻断 |
| `EVOLUTION.md` 132→181 行 | 2.x 演进记录与静态证据边界 |
| `scripts/run_case.py` +55 行、`scripts/run_multi_case.py` +48 行 | 驱动器死锁修复、清理残留保留现场重试 |
| `tests/test_driver_deadlock.py` +134 行 | 死锁修复回归测试（回退中被删） |
| `tests/test_multi_case_cli.py` +32 行 | 多 Case CLI 补充断言 |

校验：`git diff backup/story-2.x-20260825 -- test/story` 输出为空。提交 `84c052bb`。

## 3. 公共设施（G1 失效形态台账）

- `test/story/regression/failure-modes.yaml` —— 每形态一条，含正/反夹具、checker、status。
- `test/story/scripts/check_failure_modes.py` —— 全量回归入口，跑全部 `status != retired`。
- `test/story/fixtures/failure-modes/<id>/{bad,good}/` —— 夹具。
- `TEST.md` §7 离线验证清单已补台账、`node --check`、负面扫描三条。

状态语义：

| status | 含义 | 回归行为 |
|---|---|---|
| `fixed` | 已修复，永久回归 | 必跑，FAIL 即失败 |
| `pending_capability` | 目标能力尚未建（1.0 基座无此能力） | SKIP 并计数，不算失败 |
| `retired` | 经人工批准下架 | 不跑，须 `reason` + `approved_by` |

## 4. 测试域 × 1.0 基座兼容矩阵（Codex P1-4）

| 兼容项 | 结论 | 证据 |
|---|---|---|
| 当前 runner 能对 1.0 跑单测 | 通过 | Story 单测 132 passed |
| Tools CLI 检查 | 通过 | 16 passed |
| Python 编译 | 通过 | `compileall -q tools/cli test/story/scripts` |
| 只读 plan 演练（隔离 workspace 预检） | 见下方「演练记录」 | — |
| 台账区分「1.0 尚无该能力」与「目标能力回归」 | 通过 | `pending_capability` 状态位；批次 1 未交付前知识类形态全部 SKIP，不误报 |
| Case prompt 不调用 1.0 不存在的入口 | 通过 | 4 个 case.yaml 只用 `/story init`、`/spec`、`/story archive`、`/story review`，均在 1.0 CLI 契约内 |
| 阶段状态 / verifier 报告名 / 回灌协议可读 | 通过 | `phase_state.py` 读 `.current-phase.json` + 阶段产物；报告名认一组（TEST.md §5） |

**演练记录**：`run_multi_case.py plan --all --jobs 4 --isolated-workspaces` 输出完整 plan JSON
（4 个 Case、workspace 白名单策略、驱动间隔策略齐全），未启动真实 CLI。

## 5. 台账首轮回归发现的 1.0 基座机制缺陷（本批已修）

台账建立后首次对 `doc/extensions` 跑机制层回归，检出 4 类真实缺陷（均属 G7「机制层零硬编码」）：

| 形态 | 位置 | 缺陷 | 处置 |
|---|---|---|---|
| M01 | `lint-rules.mjs` 悬空引用 hint | 示例文案写真实域编号 | 改中性占位形态 |
| M02 | `merge-story.mjs` 术语分流注释 | 注释写测试 Case 单号（过拟合痕迹） | 改中性描述 |
| M03 | `merge-story.mjs` 术语分流**判定代码** | 平台能力层用层名字面判定（注释自称"SSOT 在架构 DSL"，实际写死） | 新增 `baseLayerIds()`：按 `can_depend_on` 为空派生底层，改为依赖方向判定 |
| M03 | `lint-rules.mjs` 路径模式注释 | 注释举例写死本工程层名 | 改中性表述 |
| M05 | `story-build.mjs` ×8、`hooks/spec/post_check.mjs` ×1 | 按 `'\n'` 切行，CRLF 文件静默零命中 | 判定型改 `/\r?\n/`；**改写型改捕获组 `/(\r?\n)/` 保留原行尾**——按 `/\r?\n/` 切开再 `join('\n')` 会把 CRLF 静默转 LF，`check` 的逐字重装配比对会假失败 |

修复后机制层回归 27/27 全绿。

### 历史样本观察档（不参与 PASS/FAIL）

对实施前基线跑产物类 checker，检出 9 处历史缺陷，证明 checker 有效：

| 形态 | 样本 | 检出 |
|---|---|---|
| P05 landing 为空 | AR90006 | 多条义务无承载实体 |
| P06 知识决策章位置 | DTS90006 / AR90006 | 决策章在设计章之后 / 根本没有该章 |
| P09 决策引用堆叠 | DTS90006 / AR90004 | 同段 2 次 / 3 次 |
| P10 图片重复引用 | AR90006 | 同一张图引用 2 次 |
| **P11 verifier 漏裁** | **AR90004 12/12（全未裁决）**、DTS90006 3/14、AR90006 4/10 | 2.1 的「扩展判据注入 ≠ 被执行」硬证据，直接印证 B1-13 全集裁决的必要性 |

## 6. 测试域 · 批次 2 开工前先修（2026-08-27 从批次 1 登记项移入）

| # | 缺陷 | 现象 | 处置要求 |
|---|---|---|---|
| T-1 | `review_feedback` 按关卡编号排队、不认阶段语义 | `run_multi_case.py` 生成 interaction_script 只声明 `expected_turn` + `expected_kind: story_gate`，评审意见被送到范围拆分第三级关卡（实跑 `-1310` turn=3） | **已修（2026-08-27）**：脚本步骤支持 `expected_phase` 与 `requires_archived`（读 `AR/story-flow.json` 归档态），对不上回落人工并给 `interaction_phase_mismatch` / `interaction_precondition_unmet`；`split-interactive` 的评审意见步骤已加前提；回归 3 条（`test_multi_case_cli.py::GatePreconditionTest`）；TEST.md §3 列出四类 reason |
| T-2 | 续话多行只送首行 | `reply` 路径多行文本截断，初始 prompt 多行能送达，差异在 resume 路径 | **未修**：根因未坐实前不动 `tools/cli`。现行规避在 TEST.md §0.2「回话必须是单段文本」——回话写成一段、用分号断句 |
| T-3 | interaction-script 只覆盖 story 关卡，spec 阶段的固定确认点全部漏空 | 本轮（`20260827-121825`）实测五个停等点：turn1 材料、turn2 范围、turn3 **承载**、turn4 **spec 术语表逐条确认**（框架红线 2）、turn5 **盲档降级确认**（`vision.blind_tier`）。脚本只有三条、且第 3 条是评审意见——turn3 被 T-1 的阶段前提正确拦下，turn4/5 是 `gate_mismatch`。每轮实跑要人工回三次，等待时间全花在这上面 | **实跑结束后补**：脚本扩到六条——材料 / 拆法 / 承载 / 术语确认 / 盲档接受 / 评审意见（末条保留 `expected_phase: spec` + `requires_archived`）。**术语与盲档两条要写成通用需求方措辞**（不点名字段与模块，反过拟合 M02）；三个 story 关卡与三个 spec 确认点的 `expected_phase` 分别写 `story` 与 `spec`，让串台在任何一侧都拦得住 |

## 7. 本仓专属修复（不随 Extension 交付）

`.claude/hooks/check-phase-completion.mjs`、`record-verifier-report.mjs`（framework claude adapter 模板的实例副本，各 29 行差异）+ 新增 `hook-session-evidence.mjs`：修「同仓开两个 Claude 会话时阶段状态归属串台」——归属改按本会话 transcript 里有没有跑过该 harness / 调过 verifier 判，不再按 grace 窗口猜；目录不存在不建。**用户裁定（2026-08-27）：只留本仓，adapt 不管、发布清单不含**；本仓 framework 升级时 `init.task_decision` 选「保留」。

## 8. 环境前置 · Maison UI kit（多次实跑失败的来源，与被测能力无关）

UI kit 不是需求编造的，也不是 story/extension 引入的，是 **framework hmos-app profile 的强制链**（framework 提交 `4e4f2b5e`，2026-07-18，「blind-visual-hardening」）：需求有页面 → spec 必须产 `ui-spec.yaml` → 盲模型（CLI 无视觉）每 P0 屏必须声明语义容器（`ui_kit_declaration_required`，「kit 是地板不是可选项」）→ coding 必须物化并使用 kit（`ui_kit_source_conformance`）。需求材料、story、extension、四个 Case 对它零提及。
2026-08-22 至 08-26 共 8 个 suite 撞此链：先是 `paths.ui_kit_target_dir` 未配置（halt），后是模板 `MaisonPrimaryButton.ets` 的 `enabled` 与 ArkUI 基类同名（模板此前从未在任何工程编译过）。两处均已补（配置 + 物化到 `05-SystemBase/CommUI/.../maison_ui_kit` + drift_allowlist 热修），TEST.md §2 列为起跑前检查。framework 无开关可关；只有模型具备读图能力时才跳过声明门禁。
**用户裁定（2026-08-27）：保持现状**——不再为它动 framework，也不提上游；后续实跑撞到 kit 门禁一律按环境前置处理，不计入被测能力。

## 9. 事件日志

- 2026-08-25 回退验收四项取证完成（§1），结论：产品侧已正确回退至 1.0。
- 2026-08-25 测试域从备份分支恢复并验证（§2），提交 `84c052bb`。
- 2026-08-25 台账（27 形态）+ 全量回归脚本 + 65 个正反夹具建立（§3）；夹具自检 27/27。
- 2026-08-25 首轮回归检出并修复 1.0 基座 4 类机制缺陷（§5）；回归全绿。
- 2026-08-25 兼容矩阵与只读 plan 演练通过（§4）。
