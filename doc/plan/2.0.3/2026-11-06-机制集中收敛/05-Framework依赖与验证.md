# Framework依赖、原生接续与关闭证据

2026-11-07。固定合同ff111909/source879f1e8b；本地DSH不声明Goal能力。当前只修设计，未向外发送反馈、未改pin/patch/demo或产品。原05由bf7704bf和本轮before保存；本页区分上游缺陷、本地适配和正常实施验证。

## 1. 依赖与责任

| 事项 | 本轮判断 | 阻塞与下一结果 |
|---|---|---|
| F1 gap闭包 | 已证原生deriveClosure收gap而complete refs/schema不支持，仍属上游契约不一致 | Framework正式修复发布；只阻含该合法关联的CU闭合及依赖它的本版终点，不阻A04/A05；保真实未决阻断，不能删gap求绿 |
| F2人读渲染 | 上游改进建议，非Extension全部写作差距的解释 | 非前置，不造本地renderer；最终阅读效果不达仍列差距 |
| Q1设计authority/来源 | 仍需针对真实误拒表达核定；不把所有ref要求authoritative，不预判必须改source_kind | 设计者取得精确合法对象与消费者反例后定是否本地修或上游反馈；只有受影响来源闭合受阻，未知改动无预算。既有来源与转写职责可独立实施 |
| Q2独立设计接续 | 本轮已找到并隔离执行原生无run请求范围/Feature冻结/阶段输入链，不再等待上游新增interactive入口 | 设计选型关闭；真实DSH组合、作者产物、独审/闭环与observer终点仍待实施验证，不称Q2效果已通过 |
| Story只读运输 | 原生蓝图质询可通过公开知识扩展点使用；原生阶段verifier不收Story自由文本。本地DSH自足只读桥是实际适配 | 按06保现桥并收缩职责，不增加Framework Story资格/报告服务请求；实际宿主缺能力才诚实未审，不能伪称原生支持 |

只向Framework反馈“在原生正常入口仍有可复现职责缺口”的事项。F1可转交；F2是建议；Q1按对象核实；Q2的“没有interactive入口”旧归因撤回。未发送外部消息。

## 2. 已定的本版原生接续

本版承诺仍是用户已要求的CU Spec/Plan设计阶段，不签完整Feature实现。原生project-entry:32完整交付用attended或detached run；:34允许独立设计职责。attended属于会话交互，不是headless同义词；本版选择已有独立设计路径，不调整DSH Goal能力或后台范围。

对每个实际承接的CU，按原生分解/接受/readiness返回身份与路径。正式阶段前一次prepare-scope声明整个获准设计请求（同时要Spec/Plan时requested-phases spec,plan），由原生候选、phase_chain/obligations决定哪些阶段要执行，哪些有合法依据可复用。**不先冻结单Spec、再自行换范围为Plan；不人为强迫每CU全跑，也不删应做阶段。**

在消费工程framework/harness目录执行下列原生入口。FID是原生返回的canonical Feature身份；HOST为该消费根；REQ是已登记且当前有效的真实需求原文文件（需要时去引用片段），不是CU摘要或维护文档。

~~~powershell
npx ts-node scripts/goal-mode-entry.ts --project-root <HOST> --framework-root <HOST>/framework --feature <FID> --prepare-scope --completion-target request --requested-results '<本次获准设计结果>' --requested-phases spec,plan --requirement-file <REQ>

# 对原生phase_chain里应执行的P，依次执行；只请求单阶段则上面传真实单阶段。
npx ts-node scripts/prepare-blueprint-design.ts --feature <FID> --phase <P> --project-root <HOST> --framework-root <HOST>/framework
# 按原生Spec/Plan Skill完成本阶段Research/facts、正文及typed缺口。
npx ts-node harness-runner.ts --project-root <HOST> --phase <P> --feature <FID>
# 仅当summary实际签发request时调用原生阶段verifier；最终回复原样保存。
npx ts-node scripts/check-receipt.ts --project-root <HOST> --feature <FID> --phase <P>
npx ts-node harness-runner.ts --project-root <HOST> --sync-closure --feature <FID> --phase <P>
~~~

上列是接口顺序，不替换各Skill的完整作业书。初次正式harness由ensureFeatureExecutionScopeFrozen从合法候选写execution-scope.json，后续复用；prepare-scope不创建run、没有run-mode/next。阶段输入导出不承担冻结/完成；合法absent由本阶段作者补，invalid/冲突回设计owner。实际原生NEXT要求返回前阶段时必须处理，不能只按目录有文件前进。

Spec在真实阶段链中时，先完成Spec的当前summary/证据/receipt/closure，再Plan。已有完整验收导致原生只派Plan时，保其reused/obligation依据，不额外造Spec报告。无run的request-terminal不代表Feature完成，不能改写Feature完成状态或发布资格。

## 3. 真实完成与正常变化

原生阶段完成条件：脚本检查、policy所需trace/verifier、当前共同处置、最终绑定与receipt均按Skill满足，finalizePhaseClosure生成closed及phase evidence。路径全部取featurePhaseReportsDir等真实解析；不手造summary、receipt或freeze。每个实际CU要有相应阶段链及复用依据，不能用一个CU代整单。

现observe_target通过resolveEffectiveScopeSource同时支持Feature冻结和run，故scope=frozen并非强制Goal。end_target沿实际phase_chain/obligations及阶段freshness读取；C01核它消费真实request终点，必要修正仅限按现原生证据认复用/完成，不删frozen或以typed文件存在判成功。host_conclude仍只结束运行，不修改Case end_at。

冻结后作者在原生当前职责内补本阶段产物，先沿本阶段检查和既有修订规则；共同设计/请求范围实际改变则交原生owner核影响。无run不应用run专有scope revisions；若原生明确拒候选differs或要求Goal权威，保原失败/已有成果，交设计者按具体请求重新定合法设计路径；不加overwrite、手改冻结或默认改为attended。这是明确失败边界，不是让执行者自行选核心架构。

Story最后仍核basis/currentness；仅Story可用合法草稿，准入控制CU准备。后段真改共同设计，原生质询收尾→同步Story→同读者按影响复核→登记/check --deliver。无业务变化的确定性准备不自动再加一轮模型调用。

## 4. 本轮设计探针及证据限制

原件在output/evidence/2.0.3-native-plan/20261107/native-continuation.md §7—8、probe-commands.json及spec-required-commands.json。使用固定pin的现有隔离fixture，正式原生CLI确定性调用，无模型实跑、无产品改动：

- 验收已完整：prepare-scope实际派生[plan]，原生harness写Feature冻结，Plan导出和checker可达；失败为作者尚未完成sidecar/facts/知识上下文。
- 需补验收：合法来源夹具派生[spec,plan]；Spec正式checker准确指出缺作者产物。隔离构造合法Spec验收后，同一冻结范围下Plan输入和checker可达；Spec未closed时NEXT仍正确要求先收口Spec。构造产物不当真实作者/独审完成。
- 中途错误derive来源stamp被原生拒绝，原失败保留，改为真实需求来源后继续；未改冻结/Framework求绿。
- 该fixture物化宿主与本仓DSH测试模板不同，探针继续使用其已物化codex做确定性检查，不能签DSH运行。没有伪造verifier/trace/PASS/receipt；未验证最终closed组合或语义质量。

这些证据足以关闭“只能开Goal才能准备范围”的设计误解并确定命令链；不足以签B01交付或C02目标达成。实际DSH模板的正常作者/原生检查/独审闭环与observer链，是B01/C02必须补的实现和行为验证，不再挂为待上游新接口。

## 5. 组合验证与上游固定

授权实施后在一次性template安装开发源，按唯一framework-under-test.json固定release/source/patch。DSH实际物化、CLI/Preset接线和本地只读任务/原生阶段JSON两条真实消费者分开核；未改装配可复用证据，改pin/patch/模板必须assembly。demo仅正式接入/发布时更新。

F1正式修复需从原生完整生产入口验证合法gap关联，窄反例只作定位。Q1有确定结论后先同步接口/消费者和预算再实施，不能让执行者猜authority表达。最终C02锁同一组合，不把不同版本局部绿相加；依赖不影响的A04/A05/C01可在授权后独立推进。
