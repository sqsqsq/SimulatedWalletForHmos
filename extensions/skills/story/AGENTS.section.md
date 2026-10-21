<!-- story-ext:begin -->
本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|update|adapt|stats|help> [需求编号]`——从材料导入到归档的完整链条由它承载。
- **动笔前先取本阶段的作者要求**：原则页 `doc/extensions/hooks/<阶段>/author.md`（spec / plan / coding / review / ut / testing 各一份）；spec 与 plan 阶段另跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>` / `node doc/extensions/hooks/plan/author.mjs --feature <名>` 取本次任务包。
- **使用记录的初始化输入**：一个需求取得需求材料之后、第一次正式分析之前，在它的需求目录写 `.usage-input.json`：`{"requirement": "<需求编号>", "name": "<需求名称；没有明确名称按功能写>", "version": "<业务版本>"}`，可加本会话可知的 `agent`、`model`（不知道写 null）。业务版本是需求明确的交付版本；没有就取工程的版本配置（如应用 versionName）；都没有写 null——需求文档的草稿或归档修订号、Framework 与 Extension 的版本都不是业务版本。四项只接收一次，之后切换会话或模型也不改；使用、结果与计时由正式命令和阶段检查自动记，不用另跑命令。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
<!-- story-ext:end -->
