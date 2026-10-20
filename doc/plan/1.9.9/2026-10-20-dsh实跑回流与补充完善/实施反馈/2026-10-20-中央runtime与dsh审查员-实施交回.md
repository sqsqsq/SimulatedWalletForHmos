# DSH 补充包：中央 runtime 工具事件与 dsh 审查员本地定制 实施交回

2026-10-20，维护实施者。**已实施，等待评审。** 没有调用真实 DSH 模型。

依据：
- 用户 10-20 授权：「1 授权优化中央cli 2 不改framework，dsh的verifier适配按照opencode的方式，直接实现并在demo中归档」。
- 实施前确认：「不改framework」指不改上游 agent-maison，做法是 demo 本地定制 dsh adapter，与 opencode 的本地定制同一做法。
- [03](../03-测试装置与证据修正.md) §中央runtime；[01](../01-dsh独立审查方案.md) §1–§4。

**开工基线**：`de968bf4` 加上[上一份交回](2026-10-20-本仓可继续项-实施交回.md)的未提交改动。证据在 `output/story/1.9.9-dsh-verifier-20261020/`。

**与 01 的偏差（用户决定）**：01 原定 dsh adapter 由上游 Framework 交付、本仓不改 `demo/framework`。用户改为不动上游，在 demo 本地定制。01 §1 末段、§3「Framework最小文件动作」与「兼容基线与资格顺序」中关于上游交付的表述需设计者同步；本轮不改方案正文。

## 1. 中央 runtime：DSH 工具事件（不计 Extension G）

| 新承担者 | 原状 | 实际消费者 | 验证 |
|---|---|---|---|
| `adapters/providers.py::DshAdapter.parse`：`tool_call {callId,tool,input}` 产出公共 `tool`/`started`，带 tool_name 与 input；`tool_result {callId,status,result}` 产出同一 `tool_call_id` 的 `tool` 事件，状态原样透传（completed / error / …，缺省 `unknown`），result 作 tool_output（非字符串转 JSON 文本，缺失为空）。结果不带工具名，也不跨运行缓存 | 两类事件全部落到 BaseAdapter，events.jsonl 里没有工具事件 | 本仓 `measure_run.py`、`observe.py` 按 run 与 tool_call_id 读 | `test_dsh_tool_calls_pair_with_their_results`：夹具剪自 10-20 实跑，含两张图并发读取都失败、一次 subagent、一条被截断的读取，逐事件断言完整 `AdapterEvent`。`test_dsh_tool_results_keep_what_the_provider_said`：先到的结果独立成立、cancelled 原样、缺状态为 unknown、结构化结果、未知事件不产出工具事件 |
| `_tool_call_id` 认 `callId` | 只认 id / callID / call_id / tool_use_id | 同上 | 同上 |

中央 README 的 dsh 一节补了事件映射说明。

**发布与同步**：
- 中央测试 `pytest test/tools/cli test/test_sync.py` 82 passed。
- 在配置仓 `C:/Users/kangz` 只暂存这 4 个 cli-runtime 文件，提交 `ce5d1ff`，标签 `cli-runtime-v1.0.4`。未推送，未碰 Agent-Bot 的在途改动。
- `sync.py --to` 同步进本仓：替换 providers.py、README.md、test_adapters.py，新增 dsh_tools.jsonl，stamp 指向 `ce5d1ff`。随后 `--check` 为 CLEAN。
- 另两个业务仓（AIDefectHelpler、AIWalletKit）没有同步。

**重放**：用新 adapter 重放 `story-suite-20261020-dsh-01` 的 15 份 raw.jsonl，结果是 734 次调用、734 个结果（completed 683、error 51），没有对不上的结果（`dsh-tool-event-replay.txt`）。

**提交范围提示**：本轮 `tools/cli/**` 与 `test/tools/cli/**` 的改动是本任务的同步。「看评审」提交时这两处应纳入，不再按「另一任务的 CLI runtime 同步」排除。

## 2. dsh 审查员：demo 本地定制（不计 Extension G）

| 动作 | 文件 | 说明 |
|---|---|---|
| 新增 adapter | `demo/framework/agents/dsh/adapter.yaml` | 入口沿用 chrys 的共享 `.agents` bundle（AGENTS.md、`.agents/skills`、`.agents/rules`，与 generic/chrys 字节一致、可幂等共存）。加 opencode 同款 `commands.subagents`：target `.dsh`，template `templates/agents`，auto_overwrite。`image_input: none`。`verifier_subagent: false`：按 adapter-schema 的入册纪律，宿主实跑观测前不登记 true |
| 新增审查员模板 | `demo/framework/agents/dsh/templates/agents/framework-verifier.patch.yml` | 只 insert 一行，配置是 01 §2 的定案：id `maison-verifier`，`@deepseek-ai/dsh-tool-subagent`，provider spawn，toolName verifier，one-shot，不开后台，maxDepth 1，toolFilter 只放 read/glob/grep/read_image |
| persona | 同上 | 由 opencode `templates/agents/verifier.md` 正文生成：阶段审查各节逐字沿用，只改宿主措辞（Task prompt 改为调用参数 prompt，工具名改小写）。另加两节：「你收到什么」按阶段 request 与自足审查任务分派；「其它独立只读审查任务」只按任务指定格式返回，不加阶段终态块，看不了图写未审。生成器在 `output/scratch/dsh-verifier/build_template.py`，不随产品交付 |
| 交互渲染规则 | `demo/framework/agents/dsh/templates/rules/interaction-renderer.md` | 与 generic/chrys/opencode 同一份字节 |
| 选项登记 | `demo/framework/skills/reference/confirmation-registry.yaml` | `init.materialized_adapters` 加 dsh 选项。没有它 `buildAdapterCatalogOrThrow` 会抛错，framework-init 起不来。notes 的共享 bundle 一句加上 dsh |
| 物化 | `demo/.dsh/framework-verifier.patch.yml`、`demo/framework.config.json` | 物化件与模板逐字节相同；materialized_adapters 加 dsh |
| 规约登记 | `AGENTS.md` §2 | 本地定制由「两处」改为 opencode、dsh 两组，写明 dsh 的文件、物化位置、`--patch` 装载与入册条件 |

没有改 Framework 的任何逻辑或共享指引。共享规则、各阶段 SKILL、harness 的 NEXT 文本仍写「Task 触发 subagent_type: verifier」，dsh 宿主里对应的是名为 `verifier` 的工具。这样的映射模型能不能照做，要在资格实跑里看。

**Extension 侧**：dsh 走 `.agents/skills/story/SKILL.md`，这个入口已经由 manifest 的 bridges 登记过（generic/chrys 共用），所以没有新增入口，Extension 零改动。

**Framework 自己的核对**：
- `check-adapter-catalog-consistency.ts` PASS。
- `init-orchestrate --scope project` 的 adapter_catalog 列出 8 个 adapter，含 dsh；计划里有 `materialize-adapter:dsh`（`init-plan-after.json`）。
- 用 check-init 的 `loadAdapter('dsh')` 只读探针（`output/scratch/dsh-verifier/probe-adapter.ts`）：dsh 物化 15 个文件，`.dsh/framework-verifier.patch.yml` 为 verbatim、auto_overwrite，与 demo 现有文件逐字节相同。唯一不同的是 `.agents/skills/goal-mode/SKILL.md`，它在 HEAD 已有漂移，与本轮无关。

## 3. suite 调用配置快照（测试域）

| 新承担者 | 实际消费者 | 验证 |
|---|---|---|
| `cli_config_group.registry_snapshot`：配置组含 dsh 时，从中央 `clis.json` 派生只含 dsh 的快照，保留 defaults；每个档位的 args 与 resume_args 在 `--profile <名>` 之后插入 `--patch {cwd}/.dsh/framework-verifier.patch.yml`；中央注册表不动 | `run_multi_case.write_cli_registry` | `test_only_dsh_gets_the_layer_and_every_argv_keeps_its_order` |
| `run_multi_case.write_cli_registry`：`start` 装好模板后写 `<suite>/cli-registry.json`，路径记进 suite.json 的 `cli_registry`。模板缺配置层时，在任何 Case 起跑前退出 | `suite_environment` 经 `STORY_CLI_REGISTRY` 交给每个 Case | `TheSuiteWritesOneSnapshot` 三条：无 dsh 时不写也不设变量；缺配置层时停下且不留文件；有配置层时写出并交给 Case |
| `cli_config_group.registry_for` 与 `run_case` 的启动点：快照里有本 Case 的宿主就用快照，否则用中央注册表。stop/poll 不读注册表内容，保持原样 | `CliClient.start` 交给 worker 的 `--registry` | `test_start_and_resume_resolve_the_layer_in_each_case_workspace`：经真实 `CliClient.describe`，在两个工程（含带空格的路径）、启动与续跑下都解析成 `<该工程>/.dsh/framework-verifier.patch.yml`，且只出现一次。`test_the_case_runner_uses_the_snapshot_only_for_hosts_it_lists` |

工作区链测试新增：`.dsh/framework-verifier.patch.yml` 与 `.agents/skills/story/SKILL.md` 并入 CHAIN（demo 里有、没被 git 忽略、模板带上）。另新增 `test_the_dsh_verifier_is_a_read_only_spawn_with_the_same_protocol`：
- 物化件等于模板，adapter 的 subagents 声明正确，`verifier_subagent` 为 false；
- 配置逐字段精确匹配，多放一个 pwsh 就失败；
- persona 含当前 request 协议与终态块，阶段输出格式一节与 opencode 子代理逐字相同。

TEST.md 已同步：§2.1 的 dsh 快照、§5.1 改为 OpenCode / dsh、目录树补 `cli-registry.json`。现行 `test.yaml` 的配置组是 opencode / codex，所以平常起跑不生成快照。

## 4. 回归

| 命令 | 结果 |
|---|---|
| `pytest test/tests -n auto --dist loadscope` | 1860 passed、2 skipped、**9 errors**（`pytest-tests.txt`） |
| 9 个 error 的来源 | 全是 `test_verifier_chain_in_workspace` 的 setUpClass，被「demo 有未提交改动，不装配」守卫挡住，原因是 demo 本轮改动尚未提交。守卫本身是对的。在绕过守卫的本地脚本里同一类 9 条全过（`verifier-chain-uncommitted.txt`）。「看评审」提交后应在正常全量里通过 |
| `pytest test/tools/cli` | 74 passed |
| 中央 `pytest test/tools/cli test/test_sync.py` | 82 passed |
| compileall、validate_clis、`run_multi_case.py plan --all --jobs 2` | 退出 0 |
| 失效形态（绕过守卫新建模板） | 61 条 FAIL 0（`failure-modes.txt`） |
| `sync.py --check` | CLEAN |

**预算**：本轮没有改动 Extension，图文包账仍为上一份交回的 G818（R ≈ 104.9%）。中央 runtime、demo/framework 本地定制和测试域都不计 Extension G。

## 5. 未做与下一步

- **最小资格实跑**（01 §4 第 2 步）需要你授权：在隔离工程带 `--patch` 起 dsh。要核以下几点，确认后才把 `verifier_subagent` 改为 true：
  - 父子会话不同，子级是空上下文；
  - 写工具与 pwsh 实际不可用；
  - 子级读中性材料并交回带终态块的报告；
  - 错误关系的负例被报告发现；
  - 父 agent 在「Task subagent_type=verifier」的指引下能找到 `verifier` 工具。
- 起跑前检查（01 §4 第 3 步）要人工核以下几点，本轮没有加自动检查：
  - personal setup 实际选中 dsh（上次被测模型自己选了 generic）；
  - profile 里有 `dsh-subagent` 与 spawn 后端；
  - 没有同名工具冲突；
  - 当前模型没有图像输入，阅读图视觉项只能写未审。
- 本轮没碰 S2（usage）、删除失败根因、乱码边界、图文合同缺项。这些仍归设计者先取证定案。
