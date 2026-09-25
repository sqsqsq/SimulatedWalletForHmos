# 知识协议演进记录

> 读者：执行 `/story adapt` 升级的维护模型。时机：`--apply` 末尾列出晚于目标 `knowledge_adapted_for` 的条目时，按条目改目标知识。

按扩展版本分节，每条写协议变了什么、目标仓要做什么。协议正文在 `skills/story/reference/knowledge/protocol.md`，改法在 `reference/knowledge-adaptation.md`；加载器只认当前协议。

## 1.9.7

- 每份知识的 frontmatter 必须写 `form`，且类型与形态只认四格（facts × facets、facts × halves、constraints × entries、patterns × halves）：逐份定格、补 `form`，只读检查按「类型 × 形态」计数核对。
- 多步推导的项目方法写成 facts × halves（上篇给设计侧、下篇给实现侧）：spec 登记用了上篇的，plan 任务包附它的下篇全文，所以下篇要能单独读懂。
- 方法型知识里的必须设计项写成具名列，每一行要给具体值；原来合并在一格里的字段拆开。
