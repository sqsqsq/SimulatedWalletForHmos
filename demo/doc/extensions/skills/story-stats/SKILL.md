---
name: story-stats
description: 本仓 Framework + Extension 使用情况统计（/story stats）：脚本从 doc/usage.json 与 Git 取出逐需求事实，你按模板把它写成报告
---

# story-stats — 使用情况统计

用户输入 `/story stats`。这是维护能力，不是需求阶段：不需要需求编号或系统 token，不新增需求或步骤，也不改业务产物。

## 步骤

1. **取事实**：在工程根跑 `python doc/extensions/skills/story-stats/scripts/stats.py collect --project-root .`。
   - `ok: true`：`facts` 是这次的事实文件，`report` 是报告要写到的位置，`template` 是报告模板。
   - `ok: false`：把 `error` 原话转告用户（坏记录、旧合同记录、不是 Git 仓、写不进去等），不出报告。
2. **写报告**：读 `facts` 与 `template`，按模板写到 `report`。每个数字都照抄 `facts`，不补算、不推断、不引入 facts 之外的数字；
   缺的如实写（`gaps` 里的文件未入库、无提交、身份未知，步骤行没有 `spent` 写耗时未知）。耗时按模板换成时:分:秒。
3. **告诉用户**：报告路径与两三句要点，要点只取报告里已有的内容。

事实只出自 `doc/usage.json` 与 Git 提交记录：不读需求目录，也不补记使用记录——少了某一步是记录端没收尾，如实报。
输出在系统临时目录下本次独有的 `story-stats-*` 目录，不写进工程。
