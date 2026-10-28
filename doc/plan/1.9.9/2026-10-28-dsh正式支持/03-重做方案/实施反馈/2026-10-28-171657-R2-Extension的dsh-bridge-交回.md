# R2 Extension 的 dsh bridge：交回

2026-10-28，维护执行者。依据：[重做方案](../00-实施方案.md) §3、§4 R2。前一步见同目录 R1 交回（提交 `e6b158c2`）。

## 改动（Extension 只动 bridges 层，本体零改动）

| 文件 | 改动 |
|---|---|
| `extensions/bridges/dsh-skill-story.md`（新增） | dsh 的 `/story` 入口：标准 skill 格式，与 `.agents` 那份同层深度、正文相同。dsh 按技能目录解析相对链接，指向 `doc/extensions/skills/...` |
| `extensions/manifest.yaml` | `provides.bridges` 增加 `.dsh/skills/story/SKILL.md` ← `bridges/dsh-skill-story.md`，版本仍是 1.9.9 |
| `test/tests/test_verifier_chain_in_workspace.py` | CHAIN 加入 `.dsh/skills/story/SKILL.md`；入口归属断言同时覆盖 `.agents` 与 `.dsh` |
| `test/tests/test_publish_to_demo.py`、`test_usage_stats.py`、`test_adapt_source_kinds.py` | 写死的入口数 6 改为 7 |
| `test/regression/mechanism-budget.yaml` | 用户 10-28 具名确认按实测上调：prompts_md 2513→2544（interim 2531→2544）、data 781→783、total 17042→17075，记录原值与理由 |
| demo 安装件 | 以 1.9.9 原号重装：`doc/extensions/manifest.yaml`、`doc/extensions/bridges/dsh-skill-story.md`、`.dsh/skills/story/SKILL.md` |

## 验证（`output/evidence/1.9.9-dsh-20261028/redo/`）

- 自检：`git diff 9c865bfb -- extensions` 只有 manifest 与新 bridge；
- 预算：endpoint G3899/X948，在 G3900 内；prompts_md +31、data +2（`r2-budget-report.md`）；
- 安装：dry-run 与安装各 143 项，completed 143、failed 0；demo 只多出上述安装件；
- `.dsh/skills/story/SKILL.md` 与 bridge 源逐字节相同；133 个文件与开发源同源；
- 失效形态 61 条：FAIL 0、PASS 53、委派 8；
- 受影响测试 66 条通过；提交后走正式入口跑 verifier chain，全量放到批末。

## 下一步

R3：文档。
