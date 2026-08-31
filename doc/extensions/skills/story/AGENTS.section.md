本工程挂载了 story 实例扩展（`doc/extensions/`）：需求流程 + 三类知识 + 六阶段生命周期钩子。

- **需求流程入口**：`/story <init|archive|restore|review|adapt|help> [AR编号]`——从材料导入到归档的完整链条由它承载。
- **进入 spec / plan / coding / review / ut / testing 任一阶段、动笔之前**：若 `doc/extensions/hooks/<phase>/author.md` 存在，**先完整读它**。那一页写明本阶段要读哪几个扩展文件、产物里扩展要求的那几处长什么样、门禁会拦什么——写之前看，不必靠门禁报错反推。
- **门禁报错自带修法**：各阶段 harness 会跑 `doc/extensions/hooks/<phase>/post_check.mjs`，它报的每一条都给出「缺什么 / 写到哪 / 怎么写」，不需要读脚本源码。
