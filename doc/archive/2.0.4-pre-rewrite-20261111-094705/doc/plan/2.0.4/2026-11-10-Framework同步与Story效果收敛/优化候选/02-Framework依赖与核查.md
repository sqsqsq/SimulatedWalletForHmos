# Framework 依赖与核查

被测旧pin ff111909a20ffa6fb53683f15db7ca420b2ef1f0；目标900c508d5c800bb77f9adb8db395b2964ef111d3，framework tree 5a20d305386f781b2e8b9fdce5ff704c8160350c。源码取Git对象或本次隔离解出的同树，不以demo旧发布件替代。

## 1. 已核能力

- 原生设计目标直接带 acceptance.criteria / boundaries；没有 design_content.acceptance 新包装。原生承载must/knowledge_refs额外键，后者语义归Extension。
- blueprint-skill-projection.ts:294–353仅按显式设计目标选内容；依赖闭包不自动授予所有权。acceptance.schema.yaml允许额外键；artifact-content保留；SpecLoader/readFeature提供真实选中值。此前隔离探针已证knowledge_refs保留、合法补checkpoint不漂移、删除权威字段判漂移。
- app-component-blueprint-workflow.md及feature/spec/SKILL.md保Spec的合法深化；原生业务投影只有AC/BD锚点，精确验收在技术参考区，knowledge_refs仍须按canonical目标核，不能只给模型业务正文。
- blueprint-questioning.ts:100–146的parse/apply能保存回复并写回，但调用只在goal-phase-runtime及design-repair-unattended；直接S4没有公开CLI。当前保实际回复→作者登记→原生校验；未来上游公开命令具备完整输入/错误/对象绑定后才替换，不导入内部TS另包装。
- 原生质询复核要求当前业务正文整体通读，来源按原问题与影响核；当前正文未变且本轮读过不重复。不能误写为每次重做八问、读全工程，也不能删掉原生正文阅读。

## 2. 原 F1：旧引用障碍与真实阻断分别验

新版 change-unit-design-gate.ts 取消旧逐个gap显式认领，保全批必需设计义务及当前闭包未决检查。gap合法status只有 open_decision / blocker / not_applicable；**不存在 resolved**。needed_by命中当前slice的gap按当前合同必须是blocker，不可仅改标签过门。

A03固定测试：
1. 有真实依据的不适用gap用not_applicable、合法owner/unlock/provenance及非当前事项引用；保原flow的decisions_and_gaps关联，CU不把gap当交付目标；整批真实义务认领齐全时accept/readiness成立。
2. 同一实际关系换为真实当前blocker及当前needed_by：accept拒绝并保候选，不产生canonical CU、不进入阶段；核内含current_design_unresolved。
3. 当前真实问题已解决：按原生修订把已确设计/决定落地并保持历史证据；不是编造resolved。无当前依赖的远期open_decision不阻本期。
4. 删一项真实必需owner认领：报告closure_incomplete，不能靠手写整个闭包或删required求绿。

这些是离线原生合同场景，不更改Case业务。旧C02的F1失败不能由新版函数变化倒签通过。

## 3. FW-F2：Spec-only公开入口已复现的接续依赖

状态：**已从900c公开入口复现，尚未取得上游正式路径/修复；不是留给执行者调查的未知。** 本标识是Framework依赖编号，不是评价标准F2归档条目，也不代表本版新引入的回归。前次源级及纯函数证据保留：
- feature-track.ts:553–596、760–769同时派生设计/验收上下文；已存在权威验收可记satisfied_by，Plan施工映射缺失仍有design-context义务。
- execution-scope.ts:416–426在同provider已有required事实时不额外加请求marker；projectScopeSchedule按未满足义务排阶段。
- 本次直接调用新树resolveExecutionScope：request目标request、requested_phases=[spec]，验收上下文已满足、设计上下文未满足，结果phase_chain=[plan]、reused_phases=[]。这证明调度函数在该事实形状下的行为，不能替代真实CU解析/绑定/冻结的验证。
- 两次初试因探针夹具漏requires、source_refs/dependencies失败，均为探针错误；补完整最小输入后的第三次退出0。不作为产品失败记账。

203010评审进一步使用同一新树公开`check-change-unit --accept-candidates`、`--readiness`和`goal-mode-entry --prepare-scope`。旧夹具先被新版显式认领规则拒绝；为真实唯一CU补认领既有`decision:balance-refresh-policy`后，accept/readiness均退出0、ready=true、constructable。随后传真实需求文件、`completion-target=request`、`requested-results=spec.md`、`requested-phases=spec`，仍返回`phase_chain=[plan]`。原请求字段和真实生成候选均保留，未预写Plan映射、未改需求。没有运行后续harness或模型，故不冒称完整宿主组合已验证。原2.0.3的单阶段回归与B01复评已有同类记录。

证据根：`output/evidence/2.0.4-optimization-review/20261110-203010/`，最小反馈包为`candidate-with-policy-owner.json`、`native-request-public-owned.py`、`native-request-public-owned-result.json`、`owned-readiness.stdout`、`owned-scope-spec.stdout`，原拒绝另在`accept.stdout`。对应公开对象和source tree记录在该目录`objects.json`与复核报告；脚本保留全部参数，可在隔离项目复算。

责任与取得方式：设计者把该反馈包交Framework作者，要求明确Spec专项及显式人读结果在已有权威验收下的合法生产路径，或提供正式发布修复件。本轮只整理本地反馈，不发送外部消息。设计者核新入口/修复的请求、返回、写入范围、错误和关闭证据后更新固定组合及本页；执行者不自行选择内部TS、Goal或手写scope旁路。

影响范围：暂停A03的Spec-only成功接续、D02-auto的相应终点和整版效果通过；A01/A02、原F1正反、合法Plan链、B/C及D01非相关准备可按各自授权继续。car到Plan不因本依赖被整体暂停；两例均成立才可签整版。当前没有实施或CLI授权。

解除条件：在同一合法CU、权威AC、未写Plan映射及真实Spec-only请求上，经正式入口完成本次Spec职责和请求的人读结果；合法复用部分与实际产出分别核，原生阶段/receipt/observer一致，不先要求或执行未授权Plan。并回归Plan请求、真实当前blocker拒绝。若上游改树，按正式pin/补丁/物化重新固定组合及受影响验证，不拼多树结果。上游未解时保已知失败证据，不把观察到[plan]的诊断包装成正向成功验收。

## 4. DSH 工具面

这是测试装置配置，不是Framework缺少业务设计能力。当前实际DSH包：
- dsh-base/cordis.patch.yml:444–445注册id tool-goal；插件注册get_goal/create_goal/update_goal及其共同指导。
- dsh-headless patch没有另造Goal工具；沿同一基础profile组合。
- 原生配置补丁支持条目 '- id: tool-goal' 加 'disabled: true'。本轮使用--dump-config对headless、batch-build均得到disabled=true，未挂载插件、未运行模型。
- A02把这两行合并进现本地framework-verifier.patch.yml模板，不另建第二运行器或全局配置。现registry_snapshot同时装载新起与resume的overlay，主与子共享工具面均受该顶层插件开关作用；实际有效工具面还需最终组合/CLI留证，不仅看YAML。
- 禁工具不能单独证明不再headless_assumed；真实术语/范围等人答仍按原生交互与事件核。

## 5. 可以转交上游的事项

| 事项 | 类型 | 所需上游结果/本仓动作 |
|---|---|---|
| FW-F2 Spec-only公开链已复现 | 已知原生接续依赖；设计者负责核正式路径/修复 | 原请求与派生义务/结果语义一致；只锁相关Spec-only与auto终点，其他链不新增等待，不在本仓副本打补丁 |
| 直接S4质询写回公开接点 | 改进依赖，当前有可用承担者 | 可选提供原回复路径、对象身份、成功/失败输出及错误原件保全合同；不是本轮全版硬前置 |
| 当前真实blocker仍不能施工 | 原生正常能力边界 | 本仓先做应承担的工程设计/澄清；只有目标确需“带条件Plan”而现接口没有时再单独反馈需求 |
| 初始受管路线扩展输入 | 本版范围外 | 本轮坚持直接设计，不要求它解决后才能修Extension |

未发送外部消息，未改Framework发布件。正式换版仍走测试pin与本地定制流程；如为F2另换上游提交，重新固定同一组合并重跑受影响验证，不能拼不同树的通过结果。

