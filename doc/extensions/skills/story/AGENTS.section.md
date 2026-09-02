<!-- story-ext:begin -->
本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|review|adapt|help> [AR编号]`——从材料导入到归档的完整链条由它承载。
- **本扩展的阶段作者要求经 `on_context_load` 送达**：动笔前跑 `scripts/author-context.ts --phase <phase>` 即可取得（六个阶段共用同一条，见 Agent 行为规约约束 0），不必自己去翻文件。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
<!-- story-ext:end -->
