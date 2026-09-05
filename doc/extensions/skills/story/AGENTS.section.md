<!-- story-ext:begin -->
本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|review|adapt|help> [AR编号]`——从材料导入到归档的完整链条由它承载。
- **动笔前先取本阶段的作者要求**：原则页 `doc/extensions/hooks/<阶段>/author.md`（spec / plan / coding / review / ut / testing 各一份）；spec 阶段另跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>` 取本次任务包。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
<!-- story-ext:end -->
