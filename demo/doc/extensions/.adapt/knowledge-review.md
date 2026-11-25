# demo 知识适配独立审查报告（2.0.6）

> 审查执行体：只读独立知识审查子代理（`conversation 67e41d6d-c14c-413d-8167-618d16e2136d`），不共享作者上下文。

### 总体结论
- **结构与旧版退出核对**：13 份知识均满足四格结构与 `adapt-scan --status` 摘要 `sha256:96c16ae47b3b04ef`；未发现旧版 1.9.7/2.0.0/2.0.1/2.0.5 退出写法残留（无 `knowledge-use.yaml`、`decision_id`、`AR/review.md`、`decisions.json`、`knowledge_application`、`knowledge_rule`、`knowledge_decision_id` 或将 `spec` 写成知识判断/埋点落点）。
- **发现的 4 项 `WARN`（无阻断级 `FAIL`）**：
  1. `knowledge/facts/component-profile.md`（`fact_use: WARN`）：§1 部件形态与 `Phone/src/main/module.json5`、`architecture.md` 一致，但 §1/§2 六类交互方未标注源码、配置或协议/负责人依据位置。
  2. `knowledge/facts/engineering-capabilities.md`（`fact_use: WARN`）：§1-§5、§7 与 `CommFunc`、`Phone`、`WalletMain`、`AccountManager` 及 `libs/framework-1.0.0.har` 一致，§6「资源」中公共颜色与组件实际在 `05-SystemBase/CommUI`。
  3. `knowledge/constraints/observability.md`（`granularity: WARN`）：当前保留 `OBS-02/03/05/06/07` 共 5 条，超过 `<= 3` 条合并建议。
  4. `knowledge/design-patterns/decision-tree.md`（`fact_use: WARN`）：`depends_on` 与 §4 SDK 行为事实核实准确，§9 反模式提及的存量开卡流程编排在当前 `WalletMain/src/` 中无对应实现。

```yaml
knowledge_review:
  digest: "sha256:96c16ae47b3b04ef"
  executor: "read-only independent knowledge reviewer subagent (conversation 67e41d6d-c14c-413d-8167-618d16e2136d)"
  files:
    - path: knowledge/facts/component-profile.md
      granularity: {verdict: PASS, evidence: "含部件申明（3要点）与交互方清单（6类外部交互方）两面，未逐个罗列内部模块职责，符合 knowledge-topics.md「部件画像」粒度。"}
      fact_use: {verdict: WARN, evidence: "手机侧独立app定位与 Phone/src/main/module.json5（type=entry, deviceTypes=[phone]）及 doc/architecture.md 一致，但正文未给出任何配置/协议/负责人依据位置（六类交互方在 demo 源码中尚无真实调用），建议按 protocol.md §四补注依据来源。"}
      duplication: {verdict: PASS, evidence: "聚焦部件外部边界与6类交互方，未重复 doc/architecture.md 与 doc/module-catalog.yaml 的内部五层及模块清单。"}
      coding_boundary: {verdict: PASS, evidence: "不含 coding-standards.md 中的编码、目录或命名规范。"}
    - path: knowledge/facts/engineering-capabilities.md
      granularity: {verdict: PASS, evidence: "按能力分7个索引面、每面1-3条用法要点，未展开内部实现原理。"}
      fact_use: {verdict: WARN, evidence: "已核 CommFunc/index.ets、Logger.ets(DOMAIN=0xD001000)、MaskUtil.ets(<=7/<=4原样返回)、NavPathContext.ets、Phone/module.json5、Phone/pages/index.ets(navDestinationMap)、WalletMain/module.json5(未引用route_map.json)、AccountConstants/AccountService、HomeConstants、libs/framework-1.0.0.har 及无受保护持久化实现，均与源码一致；但§6写「公共文案与颜色先用所属模块与 Phone 的 resources/base/element/」，实测 Phone 仅含5个壳层文案与4个壳层色值，公共颜色(comm_*)与组件(ActionListItem/SectionCard/Maison*)在 05-SystemBase/CommUI，且 WalletMain 不可依赖 Phone。建议§6更正为 CommUI 与所属模块（Phone 仅留 zh_CN/dark 说明）。"}
      duplication: {verdict: PASS, evidence: "未复制 module-catalog.yaml 的模块职责详情；§5 MaskUtil 边界集中在此处，由 security-privacy.md 引用。"}
      coding_boundary: {verdict: PASS, evidence: "§2 提及 data/repository/*Repository.ets 作能力索引，未搬运 coding-standards.md 的四层依赖规则、命名后缀或模板代码。"}
    - path: knowledge/facts/event-tracking.md
      granularity: {verdict: PASS, evidence: "正确采用 facts × halves 结构，上篇面向蓝图设计、下篇面向 plan/coding/review，职责与读者划分清晰；无 spec 旧落点。"}
      fact_use: {verdict: PASS, evidence: "逐条核对 CommFunc/src/main/ets/shared/ha/（WalletHAManager.ets、WalletHAEventID.ets、WalletFuncResult.ets、WalletHAReportBaseCBuilder.ets、WalletHAReportForChartCBuilder.ets、WalletHAReportForVOCBuilder.ets）及全仓 .ets 检索结果：Chart/VOC API、Wallet_COMMON 枚举、仅4个结果枚举、业务代码零调用均属实。"}
      duplication: {verdict: PASS, evidence: "SDK行为、字段取值与plan表头集中于本文件，与 observability.md 的基线义务分工明确、无内容重复。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 的通用编码规范。"}
    - path: knowledge/constraints/ux-consistency.md
      granularity: {verdict: PASS, evidence: "共1条（UX-01），符合<=3条与领域归纳要求。"}
      fact_use: {verdict: PASS, evidence: "约束、处置、模型/实机验法及探针（阻断：absent_regex）明确可执行；落法附注聚焦 RTL 镜像平台易错点与 setLanguage('ar') 实机验法。"}
      duplication: {verdict: PASS, evidence: "与其他知识文件无重复。"}
      coding_boundary: {verdict: PASS, evidence: "核对 coding-standards.md 全文无 RTL/Localized/TextAlign.Start/Canvas 规则，未把编码规范改写进知识。"}
    - path: knowledge/constraints/security-privacy.md
      granularity: {verdict: PASS, evidence: "合并为1条红线（SEC-01），在落法附注按业务处理、展示与观察性输出、跨重启存储、缺依据四面清晰界定，符合1.9.9演进要求与<=3条上限。"}
      fact_use: {verdict: PASS, evidence: "聚焦业务义务与边界，末行指向项目知识「敏感数据处理」一节（engineering-capabilities.md §5），未混入实现推导或硬编码脱敏代码细节。"}
      duplication: {verdict: PASS, evidence: "未重复 engineering-capabilities.md 中的 MaskUtil 截断细节；observability.md 仅引用本域。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 中的编码规范。"}
    - path: knowledge/constraints/dfx-baseline.md
      granularity: {verdict: PASS, evidence: "共2条（DFX-01 功耗高频调用、DFX-02 ROM 体积增量），符合<=3条及领域归类。"}
      fact_use: {verdict: PASS, evidence: "基线值表以<待补充：以本仓性能基线为准>如实登记空缺并禁臆造数值；DFX-02 附注按2.0.4要求区分新增预置资源与复用/运行时数据，量化写明真实来源与取得时机。"}
      duplication: {verdict: PASS, evidence: "DFX-02 管体积增量数值，与 resource-usage.md（管先复用后新增）互补不重复。"}
      coding_boundary: {verdict: PASS, evidence: "核对 coding-standards.md §8（ForEach/LazyForEach/visibility）无任何重叠。"}
    - path: knowledge/constraints/observability.md
      granularity: {verdict: WARN, evidence: "当前含 OBS-02/03/05/06/07 共5条条目，超出 knowledge-adaptation.md 质量判据与 knowledge-topics.md「可观测」（挑最核心、同类合并、<=3项）要求；建议将偏协议/编码登记的 OBS-05/06 与 OBS-03 合并，精简到<=3条。"}
      fact_use: {verdict: PASS, evidence: "已核探针正则与 CommFunc Logger.ets、WalletHAManager.ets（chartBuilder/vocBuilder/log*AndReport）及 WalletHAReportBaseCBuilder.ets（setWalletEventDesc）符号一致；开头指向项目上报知识。"}
      duplication: {verdict: PASS, evidence: "头部引用 security-privacy.md 与 event-tracking.md，OBS-02 与 event-tracking.md 的单渠道原则按1.9.7约定呼应，未搬运事件表或字段明细。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md §7 日志语法或通用编码规范。"}
    - path: knowledge/constraints/resource-usage.md
      granularity: {verdict: PASS, evidence: "共2条（RES-01 图片来源与10KB上限、RES-02 文案复用与新增），符合<=3条。"}
      fact_use: {verdict: PASS, evidence: "明确10KB为工程设定值、中文完全一致判定及依赖方向阻挡时的临时处理，并指引按项目知识查找具体资源路径。"}
      duplication: {verdict: PASS, evidence: "附注区分了与 deliverables.md（DLV-01 翻译闭环）的边界，与 DFX-02（ROM 体积量化）互补不重复。"}
      coding_boundary: {verdict: PASS, evidence: "未搬运 coding-standards.md §6 的 $r 语法、文件名与 SVG/snake_case 规定；RES-02 核对中文字面量服务于项目复用义务并附依赖方向例外。"}
    - path: knowledge/constraints/compatibility-checklist.md
      granularity: {verdict: PASS, evidence: "共2条（COMPAT-01 接口字段兼容、COMPAT-02 错误码不变更），符合<=3条。"}
      fact_use: {verdict: PASS, evidence: "处置问项明确，附注界定纯新增错误码亦命中且需给出兜底，区分 review/ut/testing 各自核对时机，无 spec/review.md 旧载体。"}
      duplication: {verdict: PASS, evidence: "附注将字符串翻译完整性指向 deliverables.md，未重复条目。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 中的编码规范。"}
    - path: knowledge/constraints/env-exceptions.md
      granularity: {verdict: PASS, evidence: "共2条（ENV-01 清除数据恢复、ENV-02 重复入口/深链防重入），符合<=3条，且通过「异常三分类」划清与需求常规异常的边界。"}
      fact_use: {verdict: PASS, evidence: "命中条件、处置与模型/实机验法具体可查。"}
      duplication: {verdict: PASS, evidence: "与其他知识文件无重复。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 中的编码规范。"}
    - path: knowledge/constraints/deliverables.md
      granularity: {verdict: PASS, evidence: "共2条（DLV-01 翻译字符串、DLV-02 对外文档归档），符合<=3条。"}
      fact_use: {verdict: PASS, evidence: "以<待补充：翻译提交流程><待补充：归档位置>如实标明流程缺口，明确「对外开放」不含端调云，DLV-02 正确标（评审动作）且无旧版 review.md/D编号。"}
      duplication: {verdict: PASS, evidence: "落法附注清晰界定与 resource-usage.md（RES-02）的衔接与不重复分工。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 中的编码规范。"}
    - path: knowledge/design-patterns/decision-tree.md
      granularity: {verdict: PASS, evidence: "采用 patterns × halves，roles 与 coordinator_role（构建与启动）合法；上下篇按蓝图选型与 plan/coding/review 落地拆分清晰。"}
      fact_use: {verdict: WARN, evidence: "depends_on（framework）已核 WalletMain/Phone oh-package.json5 属实，§4 SDK 行为事实已核 oh_modules/framework（DecisionTree.d.ets、StateMachine.d.ets、PageInteraction.d.ets）准确；但§9反模式写「本工程存量的开卡流程编排就是这种形态」，实查 demo/02-Feature/WalletMain/src 全部 .ets 文件仅含 AddCardEntryPage/CardPackPage 等页面与数据模型，仓内并无存量开卡流程编排实现，建议删除或更正该句。"}
      duplication: {verdict: PASS, evidence: "与 page-interaction.md 在组合交接处从各自视角互补描述，无重复。"}
      coding_boundary: {verdict: PASS, evidence: "核对 coding-standards.md §4.6（Page方法/独立类/导出函数三形态）未涉及 framework HAR 决策树模式，无越界重复。"}
    - path: knowledge/design-patterns/page-interaction.md
      granularity: {verdict: PASS, evidence: "采用 patterns × halves，roles（动作表/动作枚举/交互封装/上下文/页面组件）与 coordinator_role（交互封装）合法；上下篇分工清晰。"}
      fact_use: {verdict: PASS, evidence: "depends_on（framework）已核 WalletMain/Phone oh-package.json5 属实，§4 SDK 行为事实（PageOperator、doOperator、PageInteractionContext.operateSequence、DefaultPageInteractionContext、Interaction.nextNodes、PageInteractionBuilderV3）与 oh_modules/framework/PageInteraction.d.ets 一致；§9 存量页面回调写法符合 MineTabPage/CardPackPage 现状。"}
      duplication: {verdict: PASS, evidence: "与 decision-tree.md 无重复内容。"}
      coding_boundary: {verdict: PASS, evidence: "未包含 coding-standards.md 中的编码规范。"}
  blocking: []
  unreviewed: []
```
