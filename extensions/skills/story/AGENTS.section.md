<!-- story-ext:begin -->
本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|update|adapt|stats|help> [需求编号]`——从材料导入到归档的完整链条由它承载。
- **动笔前先取本阶段的作者要求**：原则页 `doc/extensions/hooks/<阶段>/author.md`（spec / plan / coding / review / ut / testing 各一份）；spec 与 plan 阶段另跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>` / `node doc/extensions/hooks/plan/author.mjs --feature <名>` 取本次任务包。
- **使用记录的自报身份**：一个需求第一次跑 `/story init` 之前（直接跑 Framework 阶段的，在第一次阶段检查之前），在它的需求目录写 `.usage-input.json`：`{"agent": "<你所在的宿主>", "model": "<你的模型>"}`，不知道的写 null。只接收一次，之后切换会话或模型也不改；需求身份与起点由正式命令和阶段检查自动记。
- **阶段收尾与代码归档**：每个阶段原生闭环之后，先跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <需求编号> --finalize --phase <本阶段>`，返回 ok 才说明这一步已记进 `doc/usage.json`；然后再交付、问下一阶段或提交代码（提交带上 `doc/usage.json`，`doc/features/` 不入库）。停在哪个阶段就在那个阶段收尾。命令失败时按它报的原因处理（阶段还没闭环就先完成阶段，记录写不进就修好环境），再重跑同一条，成功前不说使用记录可以归档。Story 的交付门（`story-build check --deliver`）对 spec 自动做这一步。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
<!-- story-ext:end -->
