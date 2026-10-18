# 包2：原生宿主扩展章的人读承接

## 定案

使用Framework现有模板锚点，作者根据权威内容组织说明，不新增Markdown投影器或改vendored模板。生成与否由原生required_outputs决定。

| 位置 | 内容 | 权威输入 |
|---|---|---|
| Spec／宿主扩展治理项／技术约定 | 本CU接口新增/复用/变更、代码现状、数据约束和依赖边界 | 蓝图contracts、源转写/映射和工程事实 |
| Spec／规约 | 本CU要求、业务落点、对应验收；不适用理由 | 蓝图决定、acceptance |
| Spec／设计模式 | 选择/拒绝/待定及理由、本CU承担范围 | 蓝图模式决定 |
| Spec／项目事实 | 复用什么、为何适用、缺什么 | 蓝图事实及实际工程来源 |
| Plan／宿主扩展／项目知识复用 | 具体复用入口、用途、替换边界 | 工程事实及本CU实现设计 |
| Plan／规约落实 | 要求、承担实体、验证责任 | contracts.must与验收 |
| Plan／设计模式 | 已定选型的角色、实体、协作；拒绝/未承担说明 | 蓝图决定、pattern_roles |
| Plan／埋点 | 按指标组织的点位、实际结果、编码与责任方法 | 蓝图event明细与上报知识下篇 |

同一事实用引用/摘要承接，不能整份蓝图表复制进每个CU；已在本篇其他节讲清的引用该位置并说明本章关系，不再重复大表。人读结果必须能直接回答本单位怎么落实，只有来源链接或验收一行不算完成。

## 实施位置

修改hooks/spec/author.md与hooks/plan/author.md：写前从当前knowledge-task及原生设计/产出取得上表内容，缺输入回实际责任，不从Story反推设计。knowledge-task的现有知识判断、实体/角色与事实段复用；缺具体源对象时在现有段补，不再包装统一模型。

spec/plan现有overlay分别核本单位来源忠实、理由、落点、验收与实体一致，复用已有知识判项，避免同一事实两条重复判据。post_check仅在本次确有对应Markdown时核锚点/必要子节存在、真实引用可解析；内容/适用性归独立审查。无适用内容明确理由，不造空表。

无spec.md/plan.md的合法原生复用路径：knowledge决定、acceptance桥、must/pattern_roles和当前作者/审查任务仍完整。明确“不产Markdown”，不为了展示强制改变required_outputs。

## 验收

用现有test_knowledge_task/test_cu_knowledge_chain/test_verifier_report_protocol及阶段post_check夹具，覆盖有/无Markdown、有适用/无适用、错误实体/缺验收、当前CU与兄弟CU。人读和机器件同源但不新增第二真源；改变蓝图决定后不能沿旧人读宣告同步。

金样在既有候选位置直接改目标Spec/Plan，核方法/角色与文件表自洽及工程真实可行；不建立金样contracts/acceptance现场。生产原生实体对齐由专项回归与实跑证明。
