# 步骤 14 · main → story 同步（framework 升 3.0.0 正式版）

**状态**：方案，待用户确认后实施。

## 1. 现状

| | |
|---|---|
| main | `363c6e13`，framework `source_commit` = `85e266f`（v3.0.0，1098 文件）。本地已 `git fetch origin main:main` 同步到位 |
| story | `framework/` 停在 `7401f22`（3.0.0 候选，1093 文件） |
| 分叉 | main 领先 10 个提交，story 领先 221 个。升级前 main 领先 0，**这 10 个提交全是 framework 同步与 `.gitattributes` 行尾固定** |

> 目标版本是 `85e266f`，**不是** `51a37875`（后者是 `Br_release_3.0.0` 分支上更早的一个点，
> 曾用它编过一份发布包）。下面的补丁结论都在 `85e266f` 的真实树上验过。

## 2. 关键判断：`framework/` 不走三方合并

story 对 `framework/` 的改动**只有两笔提交、18 个文件**：

| 提交 | 文件数 | 内容 |
|---|---|---|
| `8a8d8a51` | 12 | 作者上下文入口（`author-context.ts` 等） |
| `4334ba5c` | 6 | opencode 的 verifier 发布器 |

其余 1000 多个文件，story 侧只是**旧版全量**，不是「改过」。让 git 去三方合并，
那 18 个文件会冲突，而手工解冲突的结果**无法逐字节验证**——解错一处，
表现是某个能力静默不生效。

所以：**`framework/` 整个目录取 main 侧，再把两份补丁重新打上**。
结果可精确表述为「3.0.0 正式版 + 18 处具名改动」，而且可验证（见 §5）。

两份补丁在 `85e266f` 的真实树上验过 `git apply --check`：

| 补丁 | 文件数 | 结果 |
|---|---|---|
| `artifacts/04-framework-author-context.patch` | 12 | **零冲突** |
| `artifacts/01-framework-opencode-verifier.patch` | 6 | **仅 `agents/adapter-schema.yaml` 打不上**；排除它之后其余 5 个零冲突 |

### 那一处冲突是什么

升级期间上游动过四个与我们重叠的文件（`agents/README.md`、`agents/adapter-schema.yaml`、
`harness/harness-runner.ts`、`skills/reference/agent-behavioral-principles.md`），
但只有 `adapter-schema.yaml` 的**改动位置**与我们撞上了：上游改写了 `publisher` 那一段的
description 措辞，补丁的上下文对不上。

**是文本冲突，不是语义冲突**——我们要做的事没变，仍是两点：

1. `verifier_capability.publisher` 的 `enum` 由 `["subagent_stop"]` 扩为
   `["subagent_stop", "task_tool_result"]`；
2. 该字段的 description 补一句 `task_tool_result` 的说明（宿主在子代理任务工具完成时把
   调用参数、子会话身份与终稿信封交给插件，插件据此发布；与 `subagent_stop` 的绑定材料同源，
   差别只在宿主把材料交出来的位置）。

在新版的措辞上手工加这两点即可，**不要**为它重做整份补丁——重做会把上游新写的
description 一并覆盖回旧措辞。

## 3. `framework.config.json` 要手工合

story 相对 main 在这份文件上只改了两处：`integrity.drift_allowlist` 的 **21 条**、
`ui_kit_target_dir` **1 项**。main 升级时若也动过它（版本号、新配置键），
两边的改动互不重叠，按块合并即可，**不要整份取一边**。

21 条 allowlist 的分类与去留：

| 组 | 条数 | 升级后 |
|---|---|---|
| 步骤 4（作者入口） | 12 | **保留**——补丁重新打上，仍是本地改动 |
| 步骤 1（opencode verifier） | 6 | **保留**——同上 |
| 历史遗留（`trace.schema.json`、`gap-notes.template.md`、`state/.gitkeep`） | 3 | **逐条复核**：新版 `RELEASE-MANIFEST` 可能已修正这几处，失效的要删（留着会掩盖真实漂移） |

## 4. 分三步执行，每步一个提交

拆开的理由：三件事的失败现场互不掩盖——地基换没换、opencode 那条链在不在、
作者入口通不通，各自可验、各自可回退。代价是中间态会红，所以每步都写明
**这一步之后什么该绿、什么还该红**；把预期中的红当事故，会白白回滚一次。

### 第 0 步 · 前置

```bash
python -m pytest test/story/tests -n auto --dist loadscope     # 608 绿
python test/story/scripts/check_failure_modes.py               # 70 条 FAIL 0
git status --short                                             # 干净
git tag pre-sync-3.0.0                                         # 出事回这里
```

### 步骤 1.1 · main 反合 story（只换地基）

```bash
git merge --no-commit --no-ff main
git checkout main -- framework/          # framework/ 全取 main，含抹掉我们那 18 处
# framework.config.json 按 §3 手工合；.gitignore 等根文件按常规解冲突
```

**这一步之后的预期**：

| 项 | 预期 | 说明 |
|---|---|---|
| `framework/` 内容 | == main 侧，逐字节 | 纯 3.0.0（`85e266f`），我们的改动一处不剩 |
| `author-context.ts` | **不存在** | 它是我们加的，被抹掉了 |
| 扩展离线全量 | **会红** | 至少作者入口相关的测试红；红几条、红在哪，**逐条记进提交信息**，作为 1.3 的验收对照 |
| `framework_integrity` | 只报 allowlist 内路径 | 此刻 18 条 allowlist 指向的文件已不漂移，条目变成「暂时无用但不错误」，**不要删** |

提交信息要写清：换到哪个 `source_commit`、红了哪些、为什么现在允许红。

### 步骤 1.2 · 重新应用 opencode 适配（6 处）

```bash
git apply --directory=framework --exclude='framework/agents/adapter-schema.yaml' \
          test/story/design/.../artifacts/01-framework-opencode-verifier.patch
# 再手工合 agents/adapter-schema.yaml 的那一处（§2 末：enum 加 task_tool_result + 一句描述）
```

**这一步之后的预期**：

| 项 | 预期 |
|---|---|
| `agents/opencode/adapter.yaml` | 含 `verifier_capability`，`publisher: task_tool_result` |
| `agents/adapter-schema.yaml` | `publisher.enum` 两个值；**上游新写的 description 保留**，只是多了一句 |
| `verifier-plan.ts` | `VERIFIER_CAPABILITY_PUBLISHERS` 两个值 |
| 能力解析 | `parseVerifierCapabilityDeclaration` 不报「未知值」——漏了手工合的话它会判非法，verifier 静默退回 `blocked` |
| 扩展离线全量 | **仍会红**（作者入口还没接回来），红的条目应当**只剩 1.1 记下的那些的子集** |

### 步骤 1.3 · 重新应用 author 适配（12 处）

```bash
git apply --directory=framework \
          test/story/design/.../artifacts/04-framework-author-context.patch
```

**这一步之后**：§5 的八项全部要过，扩展离线全量回到 **608 绿**。
1.1 记下的红条目应当**一条不剩**——还剩的话，那是 3.0.0 引入的新行为，不是补丁没打上，
按 §5 第 3 项处置。

**`--directory=framework` 是必须的**：两份补丁以 framework 仓根为路径基准（给上游用），
打进消费仓要补上 vendored 前缀。

## 5. 验证清单

按「地基 → 机制 → 能力」的顺序，每一层都要过：

| # | 验什么 | 怎么验 | 期望 |
|---|---|---|---|
| 1 | framework 完整性 | `harness-runner.ts --phase extensions` 或 `framework_integrity` | 只报 allowlist 内的路径；出现 allowlist 外的漂移 = 第 3 步打漏或打错 |
| 2 | 补丁真的生效 | `framework/harness/scripts/author-context.ts` 存在；`harness-runner.ts` 里 `emitLifecycle('on_context_load')` **零命中**；`hooks-dispatcher.ts` 含 `hookRef` | 三条全中 |
| 3 | 扩展离线全量 | `pytest test/story/tests -n auto --dist loadscope` | 608 绿。**红的要逐条看是不是 3.0.0 新引入的判据**，不要直接改断言 |
| 4 | 失效形态 | `check_failure_modes.py` | 70 条 FAIL 0、委派 15 |
| 5 | 扩展装配 | `adapt-scan.mjs --scan --check --target .` | 六项全过，含 framework 补丁那一项 |
| 6 | 作者入口真能跑 | `npx ts-node scripts/author-context.ts --phase spec --feature <任一>` | 退出 0 且打印出扩展片段，标识是仓内相对路径 |
| 7 | verifier 能力仍在册 | 看 `adapter-catalog` 解析结果 | `opencode` 的 `verifier_capability` 在，`publisher: task_tool_result` |
| 8 | 手工合的那一处生效 | `agents/adapter-schema.yaml` 的 `publisher.enum` 含两个值；`parseVerifierCapabilityDeclaration` 不报「未知值」 | 两条都成立——漏了第 3b 步的话，opencode 的能力声明会被判非法，verifier 静默退回 blocked |

**第 3 项是主要风险面**：3.0.0 正式版新增了 testing lane、Native evidence gate、
`--report-reconcile-only` 等，可能带来新的门禁或改过的判据形态。红了先判断是
「扩展该跟进」还是「新版行为变化」，前者改扩展，后者登记为观察项。

## 6. 不做的事

- **不跑 CLI**：同步是地基更换，验证靠离线全量与静态检查。跑 CLI 要等同步稳定后
  单独安排——否则一跑出问题分不清是同步引入的还是机制本身的；
- **不动 `framework-patch.yaml`**：那 18 条声明与本次同步无关，同步后仍然有效
  （上游未纳入，见 `artifacts/framework-proposal-author-context.md`）；
- **不趁机改扩展**：本步只换地基。扩展要跟进新版的地方，另开一步。

## 7. 回退

`git tag pre-sync-3.0.0` 已在第 0 步打好。合并未提交前 `git merge --abort`；
已提交则 `git reset --hard pre-sync-3.0.0`。**回退前先确认没有别的工作压在这次同步之上。**
