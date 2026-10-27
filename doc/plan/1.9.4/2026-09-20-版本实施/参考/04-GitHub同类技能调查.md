# Story 表达需求：GitHub 同类技能调查

对象为 1.9.4 下的 S-EXP 需求，不是整个版本的设计。2026-09-20 补查，回应用户对上一轮调研不足及图型选择的反馈。本文区分实现事实、公开样例与待验证效果；不把新候选意见写成用户决定。

## 1. 查到的具体实现

| 来源 | 实际读到的实现/样例 | 对 Story 的启发及边界 |
|---|---|---|
| [HumanLayer show-me](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md) | 给出伪代码、调用树、组件树、文件树、Mermaid 和 diff 例子；复杂视觉采用集中 HTML | 以当前问题选择最小视图，变化用对照；其代码树不直接搬进面向业务评审的 Story |
| [rcosteira79 的 ELI5](https://gist.github.com/rcosteira79/3785ef546092f80aa5c25f97b7e1ad71) | 先说明问题和默认行为，用具体例子；系统解释先整体角色，再沿一次请求经过各部分，深入时只展开一部分 | 借鉴解释顺序与分层，不照抄对话字数上限和“其余等用户再问”：Story 必须在文内保留完整范围 |
| [DreambigOu ELI5](https://github.com/DreambigOu/ELI5/blob/main/skills/eli5/SKILL.md) | 按读者背景、词汇和关注点组织解释 | ELI5 有多个同名实现，不能只看这个仓就声称研究了用户所指版本 |
| [nicobailon visual-explainer](https://github.com/nicobailon/visual-explainer) / [实现](https://github.com/nicobailon/visual-explainer/blob/main/plugins/visual-explainer/SKILL.md) | HTML 作为成品；流程/时序等用 Mermaid，文字较多的结构用卡片，比较用表，时间线另组织；一图支撑一个明确结论 | 关键是说明布局与信息层级。HTML/交互不能未经归档验证直接换掉 Markdown 交付 |
| [architecture 模板](https://github.com/nicobailon/visual-explainer/blob/main/plugins/visual-explainer/templates/architecture.html) | 模板源码包含分层区域、局部卡片、横向步骤与并行分支 | 这是模板实现证据，不是已经观看实际页面、也不是从未知需求生成效果的证据 |
| [Eric Blue visual-explainer-skill](https://github.com/ericblue/visual-explainer-skill#example-gallery) | README 登记 DNS 白板、OAuth 多帧解释、Mermaid→信息图等输出，并提供部分原 Mermaid | 公开示例提示可以先角色、再过程、再完整关系；图像生成的维护成本与事实准确性不能据宣传判断 |

本轮找到了明确的 show-me 原仓，撤销此前“未定位所以只参考一般原则”的调查状态。未安装或运行任何上述技能，未上传本仓材料。

## 2. 实际效果证据的限制

已读取技能正文、模板源码、README 示例和原 Mermaid。尝试打开公开 PNG 时网页读取返回 Cache miss；尝试浏览器查看时运行环境初始化失败，未建立可截图会话。因此本轮**没有完成公开成品图片/HTML 的视觉核验**，不能宣称“实际看过效果”或“已经验证优于现有 Story”。

阅读模板不能替代渲染，作者声明不能替代来源保持核验。后续补成品观察只需读公开结果或用同一中性材料做受控示范，不因此增加既定两 Case 的真实测试数量，不把外部宣传性能写进预算。

## 3. 现有设计需要纠正的分类

当前菜单把语法类型、读者问题和页面排版放在同一层。应先说明读者需要看懂什么，再选合适载体；以下是维护设计者的候选调整，不是用户已批准的图型增删。

| 处理 | 候选表达 | 原因与实现关系 |
|---|---|---|
| 核心常用 | 业务流程、跨方时序、对象状态 | 直接支撑行为、责任与变化；沿用现有能力 |
| 需要补清适用方法 | 参与方与责任边界、数据流向、按责任分泳道、变更前后对照、方案差异、业务能力分解 | 当前泛称“关系图/表格”不够帮助作者选择；多数可用已有 flowchart/subgraph、列表和表格表达，不等于需要增加 Mermaid 语法 |
| 从常用推荐中降级 | 实现类图、数据库 ER、带评分的旅程、精确排期甘特、装饰性思维导图 | 不默认服务业务评审；只有真实内容需要才用。降级推荐不等于删除既有解析支持 |
| 分开处理 | 原型截图、状态对照、图形与短说明的组合 | 它们不是 Mermaid 图型；原型有真实来源才引用，不为丰富视觉虚构 UI |

diff 可用于 update 的变化说明；当前 Story 正文仍应清楚表达有效结论，不能长期把新旧规则并排混成现行要求。分层展开可借鉴 ELI5，但不能让读者必须继续聊天才能取得异常与验收。

## 4. 版本、需求与步骤

1.9.4 包含独立的表达、缺陷、update 需求，必要清理随实际职责交接，测试装置是共同支撑。用户已要求整体重写 design，当前实施顺序与需求边界以[版本设计总览](../00-整体设计与实施总览.md)为准；本调查不维护另一份步骤表。

S-EXP 的目标、实现与验收独立，不能以整个版本的预算/完成状态代替它。本文只保留外部实现事实、证据缺口及其对表达选择的启发，不把图型候选建议当用户决定或第二份生产合同。
