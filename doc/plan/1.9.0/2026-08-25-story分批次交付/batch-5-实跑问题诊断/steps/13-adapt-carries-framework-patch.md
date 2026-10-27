# 步骤 13 · adapt 带上扩展依赖的 framework 改动

**状态**：方案，待用户确认后实施。不与步骤 12 的 CLI 观测互相干扰——本步不改任何被观测的机制。

## 1. 为什么现在要做

内网已按批次 4 适配，现在要升到批次 5。批次 5 里有**两处改在 framework 上**，
而 `adapt` 现在明说不管 framework（SKILL §0：「framework 的补齐不归本命令管」）。
于是升级到内网之后，扩展会缺地基：

| 提交 | 改了什么 | 扩展的哪个能力依赖它 |
|---|---|---|
| `8a8d8a51` | `harness/scripts/author-context.ts`（新建）、`hooks-dispatcher.ts`、`harness-runner.ts`、`specs/lifecycle-hooks-schema.yaml`、四份 spec/plan 模板、`skills/feature/spec/SKILL.md`、`device-testing/SKILL.md`、`skills/reference/agent-behavioral-principles.md`、`docs/concepts/phase-terminology.md` | **作者任务包**：`on_context_load` 从 verifier 一侧接到作者一侧，`.mjs` 钩子才能返回 `promptFragments`。没有它，批次 5 的 `hooks/spec/author.mjs` 在目标工程根本不会被调用 |
| `4334ba5c` | `agents/opencode/adapter.yaml`、`templates/agents/verifier.md`、`templates/plugin/record-verifier-report.js`、`agents/adapter-schema.yaml`、`agents/README.md`、`harness/scripts/utils/verifier-plan.ts` | **opencode 的 verifier 发布器**：让 `required×interactive×opencode` 从 blocked 变 enabled |

第二处是**宿主专属**的：内网用 codex，带过去既没用也是噪声（用户 2026-09-05 明确不带）。
第一处是**扩展的运行依赖**：不带，扩展在内网就是残的。

还有一件不带就会红的事：目标工程的 `framework_integrity` 会把这些文件判成漂移。
本仓是靠 `framework.config.json > integrity.drift_allowlist` 的 21 条压住的
（3 条历史遗留 + 6 条 opencode + 12 条作者入口）。**带文件必须同时带 allowlist 条目**，
否则内网一跑就红在完整性上。

## 2. 判据写成数据，不是 adapter 名白名单

「不带 opencode 那 6 条」如果写成代码里的 adapter 名判断，下次换宿主又要改代码。
分类的真正依据是**这条补丁为谁而改**：

- **`extension_dependency`** —— 扩展跑不起来就缺它。**无条件带**；
- **`host_capability`** —— 某个宿主的能力补丁。**只在目标工程用同一宿主时才带**，
  宿主是谁由目标 `framework.config.json` 的已物化 adapter 决定，不由包写死。

同一套数据在本仓（opencode）与内网（codex）上给出不同结果，而规则只有一条。

## 3. 机制

### 3.1 包里声明：`<extension_dir>/framework-patch.yaml`

**独立文件，不进 manifest**：它是临时件——上游合入后整份删掉，独立文件删得干净，
也不必动 manifest 的合成规则。

```yaml
version: 1
note: |
  本扩展依赖的 framework 改动，尚未合入上游。每条都写清「扩展的哪个能力依赖它」。
  上游合入之后整份删除，同时删掉目标 framework.config.json 里对应的 drift_allowlist 条目。
patches:
  - path: harness/scripts/author-context.ts
    kind: extension_dependency
    why: 作者任务包的入口；扩展的 on_context_load 钩子靠它送达执行者
  - path: harness/hooks-dispatcher.ts
    kind: extension_dependency
    why: .mjs 钩子返回 promptFragments 的支持；author.mjs 靠它生效
  # …（12 条作者入口，逐条写 why）
  - path: agents/opencode/adapter.yaml
    kind: host_capability
    host: opencode
    why: opencode 的 verifier 发布器；required×interactive 由 blocked 变 enabled
  # …（6 条 opencode，逐条写 why 与 host）
```

`path` 相对 `framework/`。**`why` 不是可选的**：带一份 framework 文件到别人的工程里，
要说得出为什么非它不可。

### 3.2 adapt 怎么用它

| 步 | 动作 |
|---|---|
| §1 判态 | 不变 |
| §3 扫描 | `adapt-scan --scan` 增加一段 `framework_patch`：逐条列出「目标现有内容 == 包内容 / 不同 / 目标没有」，以及目标已物化的 adapter 名单（决定 `host_capability` 带不带） |
| §4 方案 | 第一段之后加一节 **framework 补丁**：要带哪几条、每条的 why、目标当前状态、以及「这是临时件，上游合入后删」的原话。`host_capability` 里 host 不匹配的**列出来但标明不带**——让人看见有这么一条、以及为什么不带 |
| §5 确认 | 不变（方案整体一次确认） |
| §6 写入 | 机制之前先写 framework 补丁：复制文件 → 往目标 `framework.config.json > integrity.drift_allowlist` 追加对应条目（`path` 同上，`rationale` 取 `why` + 「上游合入后失效须删」，`approved_by` 取确认人）。**已有同 path 条目就不重复追加** |
| §7 校验 | `adapt-scan --check` 增加：要带的每条在目标里存在且内容与包一致；每条在目标 allowlist 里有条目；不带的那些**没有**被带过去 |

### 3.3 目标工程原本就改过同一个文件怎么办

`--scan` 报「不同」时**不静默覆盖**，在方案里单列一条，写明「目标这份与包不同，
覆盖会丢掉目标的改动」，由人确认。与知识文件同一套纪律。

## 4. 退场

上游合入之后：删 `framework-patch.yaml` 整份 → 下一次 adapt 会在方案里报
「包不再要求任何 framework 补丁；目标 allowlist 里这 N 条已失效，建议删除」，
删不删由人定（那是目标工程的文件）。

## 5. 验收

- 离线：`framework-patch.yaml` 缺失时 adapt 照常工作（这一节整个跳过）；
  `kind` 未知值 → 报错不静默跳过；`host_capability` 在 host 匹配/不匹配两种目标上各一条夹具；
  写入后目标 allowlist 有对应条目、重复写入不产生第二条；`--check` 能报出「带了但 allowlist 没写」。
- 真实：对一份 codex 目标工程跑一次 `--scan`，方案里 12 条作者入口标「带」、6 条 opencode 标「不带（host 不匹配）」。
- 预算：`scripts_mjs` +60 以内（adapt-scan 的扫描与校验），`prompts_md` +40 以内（SKILL 的两节）。

## 6. 不做的事

- **不动 `framework/`**：本步只是把已有的改动**声明出来并带走**，不新增任何 framework 改动；
- 不给 codex 补 verifier 能力（用户 2026-09-05：内网测试有问题再说）；
- 不改 adapt 的判态、知识处置、manifest 合成——那些与本步无关。
