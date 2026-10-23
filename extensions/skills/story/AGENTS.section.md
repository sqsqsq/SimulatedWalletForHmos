<!-- story-ext:begin -->
本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|update|adapt|stats|help> [需求编号]`——从材料导入到归档的完整链条由它承载。
- **动笔前先取本阶段的作者要求**：原则页 `doc/extensions/hooks/<阶段>/author.md`（spec / plan / coding / review / ut / testing 各一份）；spec 与 plan 阶段另跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>` / `node doc/extensions/hooks/plan/author.mjs --feature <名>` 取本次任务包。
- **阶段起止与代码归档**：开始一个阶段的实际工作（读料、设计、改动）之前跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <需求编号> --begin --step <本阶段>`（Spec / Plan 取任务包时自动做；重跑保留最早的开始）；第一次开始前在需求目录写 `.usage-input.json`：`{"agent": "<宿主>", "model": "<模型>"}`，不知道的写 null，写了的项不再改。阶段原生闭环、本轮工作做完后跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <需求编号> --finalize --phase <本阶段>`，返回 ok 才算记进 `doc/usage.json`，再交付、问下一阶段或提交代码（带上 `doc/usage.json`，`doc/features/` 不入库）；失败按它报的原因处理后重跑同一条，成功前不说使用记录可以归档。Story 交付门对 spec 自动收尾。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
<!-- story-ext:end -->
