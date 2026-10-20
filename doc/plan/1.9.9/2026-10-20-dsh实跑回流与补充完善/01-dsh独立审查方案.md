# S1：审查协作与能力合同

2026-10-20。依据00与第二轮独立评审；本步修原角色选择、输出生产和覆盖合同，不新增审查平台。先离线实施交审，真实模型证据按S4另行授权取得。

## 1. 专用角色通过现有入口交付

两Case都可见verifier，自动充值仍选通用subagent；这是实际选择偏离，不再只是工具名差异的假设。

在demo现有通用调用文字真源统一以下语义：

> 通过当前宿主已登记的专用verifier角色执行独立审查。宿主以task承载角色时，显式选择verifier；不能换成通用研究/开发subagent。阶段输入是当前request完整JSON正文，不附作者结论或额外格式指令；审查者读取prompt_path。父级原样保存回复，再按现有receipt流程核对。

| 文件/入口 | 动作与消费者 |
|---|---|
| `demo/framework/templates/AGENTS.md.template`、`skills/reference/agents-entry-detail.md`、`agents/shared/agent-bundle/templates/rules/framework-agent-execution.mdc` | 在原调用段替换“所有宿主都用Task”的解释；沿既有物化同步demo AGENTS/CLAUDE及已装规则，区外内容保留 |
| `demo/framework/harness/scripts/utils/verifier-evidence.ts`中的调用恢复文本及其它实际NEXT调用文字 | 同步同一语义，仅改指引文本，不改request/subject/验真/闭环算法；静态Task称谓不再冒充真实执行渠道 |
| `demo/framework/agents/dsh/`与`demo/.dsh/framework-verifier.patch.yml` | 保留原生spawn、one-shot、四工具白名单；阶段persona遵守任务的当前输出合同 |
| 根AGENTS §2/§6、TEST宿主说明 | 登记本地调用文字定制、物化目标、升级核对/退出条件。以后上游已提供同义能力时去掉本地差异，不整文件回退旧版 |

上游agent-maison不动，不加AGENTS.local，不关闭通用subagent，不给测试Case额外提示工具名。宿主名和角色决定属于现有适配层，不进Knowledge。`verifier_subagent=false`保持到受控资格证据交审；资格时仅在隔离工程启用。

## 2. 报告在生产端给出合法结构

根因有两处：读者审查要求details映射，实际回复多次为字符串；校验器把字符串变成空对象，再报“缺四键”，诱使父作者猜格式和改报告。

- `extensions/hooks/shared/reader-review-task.mjs`：在现有任务的输出部分直接给出最小YAML结构示意，`verification_result.checks[]`中本判据的`details`为映射，四个键为列表。示例只是结构，examined_inputs必须填本次实际路径，不得把示例空列表当已审。
- `extensions/rules/spec-rules.overlay.yaml`：输出要求与任务一致，PASS/WARN/FAIL都要本条结构明细；不要用“PASS不写论证”省略机器消费者必需的映射。
- DSH persona只说明“当前任务要求的结构明细不因通用精简规则省略”，不把Story四键硬写成Framework通用业务规则。
- `extensions/hooks/shared/verifier-report.mjs::readerReviewDetails/judgeReport`：分别报告YAML不可解析、details不是映射、缺键、字段不是列表及结论不自洽；一次列齐可判问题。不能把字符串当空对象，也不能新增解析旧字符串格式的兼容分支。

报告的业务结论由独立审查者给出。父作者负责落盘，不改措辞、不重排或补结构；无效报告保留原件并回原任务修正，不由作者代修。既有报告路径、schema和终态块不变。真实报告原样性在S4用原生会话与落盘件比较，不把提示当成机械保证，也不新增读取私人会话写业务报告的产品旁路。

## 3. 视觉能力与业务完整性分层

本轮Framework实际给出vision=false、semantic_layout/best_effort；Extension却把所有图片未读一律升级为整个Story FAIL。修正这一合同差异，不删除图片枚举，不伪称图已验。

### 3.1 单一事实与判定

`review-inputs.mjs::reviewInputs`同时供任务生产与报告校验消费。在这个现有返回对象中派生本次允许延期的视觉输入集合，不新增状态文件、模型自填开关或第二份能力探测。

允许延期须同时满足：

1. 按Framework真实生产者`fidelity-shared.ts::capabilitySnapshotPath/fidelityIntentSsotPath`定位：两份均在`<features_dir>/<feature>/spec/reports/`，由featureFilePath决定，不随reports_dir_pattern变化。Extension复用featureRoot读取；配置不可读时交付明确缺口、不得按默认旧件允许延期。两件合法、对应当前feature/spec，execution_identity与decision_id匹配。
2. Framework已裁定vision.verdict=false，effective_fidelity为semantic_layout，acceptance_strictness为best_effort；其它值、缺文件或冲突不自动降级。
3. 对象是材料清单按现有imagesIn登记的真实存在图片，非扩展名猜测；文件缺失、摘要失配仍是取材问题。

能力事实作为本次任务输入送达，变更须沿现有审查材料绑定重新核。不要把配置了某个工具、adapter.image_input一行或审查员自述当独立降级依据；外部视觉能力由Framework原有事实链反映，Extension不另猜可用provider。

### 3.2 结论与覆盖矩阵

| 当前事实 | 结论与恢复 |
|---|---|
| 文本缺件/可读而漏读/有视觉能力却漏图 | 原FAIL与补读路径保持 |
| 确认允许视觉延期，权威文字足以核业务，仅图面未核 | 图片仍逐项进unreviewed，理由指明能力事实；文本业务按内容审，零业务阻断时给WARN，明确图面未核，不能给视觉PASS |
| 关键业务事实只在图内、文字不能确定，或严格视觉要求 | 相关结果不完成，列具体待补事实/视觉能力，不能从图注造答案 |
| 已选SVG的visual_readability | 仍须真实渲染和查看；看不了则UNKNOWN/reading未完成，不能因文本WARN改为ready |

`inputCoverageProblems`仍要求每份输入在examined_inputs/unreviewed中有去向。仅当未核路径全部属于上述派生集合、文本与判项覆盖完整、无业务blocking_findings时，允许WARN；存在视觉延期时不得报本条PASS。未核的check-id、缺件、冲突和其它未读输入仍拒绝PASS/WARN。文字是否足以支撑业务由独立语义审查判断，脚本不靠字数、关键词或图数决定。

同步spec overlay的语义规则和`verifier-report.mjs`的结论自洽消费者；退出“一切unreviewed都阻断”的旧分支，保留遗漏防护。只消费既有Framework许可，不新增人签或降低严格视觉的要求。

## 4. 新旧交接与验收

| 新承担者 | 退出内容 | 保持/验收 |
|---|---|---|
| 现有原生角色调用指引 | 任意subagent可代verifier的解释 | 两工具同时可见时正常父级选专用；OpenCode原Task角色保持 |
| 原任务输出示意+精确类型反馈 | details字符串当空对象、作者补审查结论 | 本轮原生错误回复副本明确报类型；合法对象通过；已有报告shape测试保留 |
| 同一reviewInputs能力投影 | 图片未核一律等同业务缺件 | 以上四类矩阵、能力文件坏/过期、图片缺失、文本漏读、假报PASS正反例 |

离线通过只说明生产者/消费者合同闭合。新造报告桩不能称为独立语义通过。交回文件diff、本地物化一致性、正反例、预算实际G/X与真实资格未验项，按99的第一批集中交回；S1完整复核状态保持，无依赖的S2/S3已定工作可继续。

相关spec与TEST由本步同步当前合同，旧运行与历史报告不改。C1后续收敛同次命令解析职责，不改变本步视觉事实的生产者、目录与降级边界。改本地Framework发布内容需按AGENTS跑相关harness检查，不用只测Extension来证明未影响其他宿主；普通发布与完整Case不在本步授权内。
