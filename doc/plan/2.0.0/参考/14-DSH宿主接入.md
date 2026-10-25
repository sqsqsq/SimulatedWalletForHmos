# DSH接入、独审与模板同源

本版验证宿主由用户固定为DSH，沿用1.9.9。以下是实现设计，本轮未启动DSH。N无dsh adapter；B具有本地定制但模板/声明/实际workspace不同源，必须修正后再验。

## 1. 版本与所有权

只读本机 `E:\Tools\DSH\resources\app.asar` 的package及子代理实现，观察到0.2.1-rc.3/build `be72761ee1a6736ebcdf4f3739363b083ae53c98`。该值是调查时环境身份，实施和实跑时重新核实际安装，配置按0.2.1 Preset协议，不声称未来版本自动兼容。

B `doc/release/维护操作.md §2`已有三组本地定制：OpenCode adapter/审查模板；整个DSH adapter及confirmation registry选项；专用verifier调用文字。反合时同步该所有权与N接口，替换当前根AGENTS旧“两处opencode”说明。它们不随story-adaptation分发，不修改Framework逻辑或伪造发布manifest；上游出现同义能力时删除对应本地差异。

## 2. 逐文件接入

下表的定制原件以01§5指定的 `test/fixtures/framework-local/3.1.0-dsh.patch` 随版本控制保存，固定N输入由 `test/config/framework-under-test.json` 给出。公共create_workspace_template消费二者，不依赖前一份临时template；以后正式接入demo使用同一补丁内容，避免第二份定制真源。

| 文件/范围 | 最终动作与保留内容 |
|---|---|
| `framework/agents/dsh/adapter.yaml`（先template，正式接入再demo） | 从B承接路径约定：Skills/Rules在.agents，subagents在.dsh，portable交互；不声明goal_capability。解释Preset及异步完成，verifier_subagent设true供原生派审；依据是已有实际工具/空上下文及原运行证据，不是“本组合已经验收” |
| `agents/dsh/templates/agents/framework-verifier.patch.yml` | 采用B实际 `demo/.dsh/framework-verifier.patch.yml` 的0.2.1结构，替换B旧persona/toolFilter模板；不是直接复制B旧Framework模板 |
| Preset persona | 以N Claude verifier语义为底，改DSH小写工具名；合入B自足任务分流及局部明细优先。保留N物理Feature路径规则、合法产品FAIL诊断例外，不能照搬B“一律脚本FAIL拒审” |
| `agents/dsh/templates/rules/interaction-renderer.md` | B portable规则与N确认点逐项对应，共享规则可达不等于已自动注入 |
| `skills/reference/confirmation-registry.yaml` | 在N `init.materialized_adapters` options精确补DSH选项；与adapter-catalog磁盘成员双向join，不整文件回退B |
| `framework.config.json` | 在消费template的materialized_adapters纳入DSH，保持N配置/profile；原生framework-init物化。每Case再按其真实CLI选择active adapter |
| 物化及维护副本 | 修正模板→消费工程 `.dsh/framework-verifier.patch.yml`；正式demo接入时再同步根 `.dsh/`。每个时点以所用template为真源，不能拿根副本掩盖错误template |
| verifier调用文字 | N `templates/AGENTS.md.template`、`skills/reference/agents-entry-detail.md`、共享 `framework-agent-execution.mdc`、六阶段Skill、harness-runner/verifier-evidence提示、receipt模板/scaffold的静态invoked_via逐处承接B同义文字，保持N新增规则；不改执行分支 |
| 宿主物化产物 | 只由原生UPDATE生成，再核Extension段；不整文件复制旧3.0 AGENTS/CLAUDE或rules覆盖3.1 |

Preset保留四个实例：agent-preset-registry（default=standard）、空preset-standard、preset-maison-verifier、maison-verifier。审查Preset使用persona、tool-fs(write:false,edit:false)、tool-fs-search；专用工具 `provider:spawn, toolName:verifier, maxDepth:1, agentPreset:maison-verifier`。不恢复已退的backgroundMode/enableRunInBackground/persona/toolFilter工具字段。

源实际DSH专用spawn不继承父上下文；但全局headless工具对子级可见，Preset中的只读工具配置不是OS/工具权限隔离。保持角色只读约束，并用事件和产物核实际行为，不声称物理防写。额外强隔离非本Spec新增承诺，不为此建Extension旁路。

当前专用verifier不设置agentOptions，调用也不覆写provider/model。已核本机DSH子代理实现默认继承父provider/model；因此空上下文与同模型可以同时成立。Story视觉裁定按02§5读取这份实际执行配置的原生能力，不凭read_image工具存在推断有视觉；若调用者另选模型而无可对应身份则披露unknown，不扩建子代理能力管理或自动探测通道。

## 3. 三种审查同宿主、各守对象合同

| 审查 | 派发与返回 |
|---|---|
| 蓝图独立质询 | 作者预生成questioning核源任务文件，派发只交路径和读取顺序；子级先当前原生人读正文并答八问，再read任务/原件/canonical核源，不负责运行生成脚本；不继承父摘要；结果按原生questioning处理，不伪造Feature request/receipt |
| Story独审 | 用 `story-build review --action prepare` 生成的dispatch，首读Story后才读取现有task.md中的来源、人签、回看及返修诊断；同步改reading/readerReviewTask/dispatchFor及CLI prepare输出，不让首读载体内联作者结论。子级返回完整报告，父按完成通知原样写到新编号原件，check消费当前material_key；不得缩写/修报告 |
| CU Spec/Plan等原生阶段 | 运行harness后取summary.verifier_request完整JSON派专用verifier；pre_verifier与knowledge内容必须进入其prompt_path；最终回复原样写summary.verifier_report，再报告核对/check-receipt/closure |

DSH的 `verifier` 启动返回 `started subagent <childId>`，它不是审查报告。等待该child完成通知；期间不修改被审材料，不造轮询调度器。收到final answer后全文落盘，保留父子身份与实际回复原件。`host_verifier_role`在B只是静态invoked_via文字，不是N可调用API，不能据此写一个不存在的调度接口。

失效恢复：配置/实例错配在起跑前报错，修模板后重新物化；缺工具/未派审/子级失败/终稿缺失均记未审。报告形状坏交同一当前对象的隔离执行体返修，按对象合同写新原件；材料变化由原生或Story重算身份。completed_with_prior_review按原生含义披露，不等于当前稿已重审。

## 4. 测试装置修正

- `test/scripts/cli_config_group.py::registry_snapshot`保留启动和续跑均带 `--patch {cwd}/.dsh/framework-verifier.patch.yml`；不直接改中央CLI镜像拼参。
- `run_multi_case.py::seed_agent_adapter`显式project-root，使用原生check-personal-setup选择dsh；不能在framework/harness cwd误定位工程。
- `host_capabilities`当前硬读opencode，改按实际Case的cli/activeAdapter读取并保存；preflight、template、最终workspace三者身份核一致。读取失败报前置问题，不借别的宿主true代替。
- 保持 `dsh_session.mjs`、原生父子会话导出/摘要与不完整披露；原报告与最终回复校对用现有原生记录，不新建采集平台。
- `test_verifier_chain_in_workspace.py`删除模板错配豁免，补Preset结构、registry join、模板→物化→workspace同源、能力选择及N新增persona语义；现有CLI注册/参数快照用例覆盖启动和续跑。
- 本次DSH验收只选择dsh配置；B中备用opencode/codex配置可保留维护用途，但本轮runner配置不得自动切换它们后仍称DSH通过。DSH凭据/内容拒绝按现有重试和停止协议处理；换宿主需新的用户决定，不构成本版额外验收前置。

## 5. 旧证据与新验收

旧suite `story-suite-20261024-224427`的template DSH声明false，car-key实际workspace存在未提交false→true差异；真实派审事件可以证明该运行条件下的行为，不能证明正式源已同源启用。本轮保存原件，不回写旧报告和模板。

离线核配置/物化、选择、任务装配和失败恢复；获得对应里程碑运行授权后核：实际DSH版本/build/overlay、每Case activeAdapter、子级父上下文未继承、首条输入和读取顺序、蓝图八问、Story单独可读、CU实际知识/义务输入、final answer原样落盘及原生消费。只统计调用次数/不同provider_id/isolated_context声明不算独审有效。未见终稿、截断或缺原生事件明确证据不足，不能生成PASS。

本地定制/固定输入及公共装配在第一批02提交并独立核安装层；第二批当前开发源切换后沿同一入口验证首链，第三批验证剩余保持。DSH真实运行不再被目录编号定义成单独一批，权限与证据要求保持。
