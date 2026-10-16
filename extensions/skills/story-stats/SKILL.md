---
name: story-stats
description: 本仓 Framework + Extension 使用情况统计（/story stats [--version <业务版本>]）：脚本对账并聚合 usage 与 Git，模型按模板成文，脚本核对后发布
---

# story-stats — 使用情况统计

用户输入 `/story stats` 或 `/story stats --version <业务版本>`（`未知` 查未知版本组）。这是维护能力，不是需求阶段：
不需要需求编号或系统 token，统计本身不新增需求或步骤，也不改业务产物。

## 步骤

1. **取统计事实**：在工程根跑
   `python doc/extensions/skills/story-stats/scripts/stats.py collect --project-root . [--version <业务版本>]`。
   - 输出 `{"ok": true, "analysis_id", "facts", "draft", "template"}`：记下这三个路径与 id。
   - `ok: false`：把 `error` 原话转告用户（坏记录、对账失败、不是 Git 仓等），不出报告，不拿旧报告充当本次结果。
2. **成文**：读 `facts` 与 `template`，按模板把报告写到 `draft` 指定的位置（只写这个文件）。
   - 报告头取 `facts.info`；正文按 `facts.sections` 逐节写标题，每节下面放该节列出的表，从 `facts.tables` 按 id 原样写成 Markdown 表，表头与每一格逐字照抄。
   - 文字只陈述表里已有的事实；不补算、不改数、不增加逐需求明细或模板之外的指标。
3. **发布**：跑 `python doc/extensions/skills/story-stats/scripts/stats.py publish --project-root . --analysis-id <id>`。
   - `ok: true` 时把 `report` 路径与两三句要点告诉用户。
   - 报「候选报告与 facts 不一致」：按列出的每一条改候选报告后再发布一次。
   - 报「已被新统计请求替代」：本次作废，按最新一次统计的结果办。

上一份已发布的报告在新报告发布前一直有效；输出在 `<需求目录根>/.usage-stats/` 下，是运行产物，不入库。
