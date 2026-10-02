# Framework 3.1.0 协作：适用边界与最小接线请求

供用户转交，尚未发送。基线：3.1.0，source_commit 074a4c3c4a0591c8ed2162e2a0d048a1fdec081f；不推断远端今天是否已有修复。

## 1. 归因更正

无 Feature review 仍复用 active workflow 的代码审查 checker；review-rules 明确 Code Review 定位。本仓不再以补 Markdown 后缀解决 Story 审查，也不申请通用文档审查框架。

实跑的无关 JSON 引用绕行仍是不正确行为，交回“未触发”仍与记录不符；责任改为适配选型错误。无 Feature 不代表任意审查对象。代码审查自身是否另有文档/配置引用问题，不作为本版依赖。

缺专用质询 agent 或 helper 无脚本调用不证明宿主无法隔离执行。原生已有独立质询要求，须落实实际交接；不由作者自证，也不笼统宣称 Framework 无缺口。

## 2. FW-01：设计资产消费（必要）

已核 extension-loader 解析 skillAssetAbsPaths，profile-skill-assets 有 resolveSkillAssetPath；component-design-host-adaptation §7.1 指设计知识走 skill_assets，没有 before_component_design。当前正常设计指令未完整消费本扩展作者/质询资产。

请求复用现有入口：
- discovery 前读 component-design 的 extension_author_requirements。
- 派质询时交 extension_review_requirements、候选与必要知识。
- 无登记保持原生；登记不可读/解析失败报告缺口，不声称消费。
- 直接 component-design 与 Story 转入同路。
- 读取 Markdown 要求页，不新增任意脚本执行、provider 或 phase。

验收有/无登记、缺文件、直接/Story 入口，核实际执行体输入，不只核 manifest。上游交发布件/回归，本仓按 AGENTS §6 接入，不改 vendored 或设永久 Story 旁路。

## 3. FW-02：独立质询执行合同（必要）

复用原生 scope 派生、结果构造与校验，明确：
1. 主执行者用宿主已有隔离子代理，交当前候选/来源/required scopes/必要知识/扩展要求。
2. 质询者只读返回逐项结果；主执行者原样存蓝图质询过程目录。
3. 设计负责方处理问题再写 questioning，不以 provider 字符串代实际独立。
4. 候选与报告可回查，避免最终新增 questioning 与派审前全文摘要的循环比较。
5. 未完成或无能力如实缺口；不填 complete，不增固定返修次数、注册中心或调度器。
6. 字段与计算信息在动作前提供，正常设计不读 checker 报错猜合同。

验收真实调用/输入/原件及原生检查，构造报告仅证字段。无需新命名 API；实际执行入口、输入输出与留存位置须随发布件明确，不让实施者猜。

FW-01/FW-02 未接入限制直接设计/完整质询签收，不阻塞本仓独立 CLI、Story 审查、投影和更新修正。这是本报告的请求编号，区别于 2.0.0 spec 的四项接缝 A/B/C/D。

## 4. FW-03：物化保留用途（增强）

instance-skill-bridge 的“实例扩展 Skill：story”缺用途。建议保留源 SKILL 有效 description，沿原生所有权物化，不重建 Extension bridge。

不阻塞命令 Case，不包办车钥匙失败归因。核描述可见、转义和覆盖保护；自然语言选路另需行为证据，命令成功不代表自然语言发现通过。

## 5. 本仓责任

cmd 截断、误用代码审查、旧结论账本/旧夹具依赖、授权话术、投影/有效输入、Case 终点由本仓处理。Story 用现有宿主子代理和材料指纹，不申请通用文档审查平台。
