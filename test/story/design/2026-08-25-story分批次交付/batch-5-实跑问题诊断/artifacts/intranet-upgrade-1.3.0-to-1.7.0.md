# 内网升级清单：批次 4（扩展 1.3.0）→ 当前 HEAD（扩展 1.6.0，codex 宿主）

2026-09-05 按 `git diff e2227f80..HEAD` 逐项核出。批次 6 步骤 1 之后**一条 framework 补丁都不带**：上游 `0143e21` 把扩展依赖的那几处全部合入或订正了。

## 0. 先做两件事，否则后面全白做

| # | 事 | 怎么核 |
|---|---|---|
| 1 | **内网 framework 先同步到 `0143e21`**（仍是 3.0.0） | `framework/RELEASE-MANIFEST.json` 的 `source_commit` 对得上。这一版把 verifier 报告的真源改回调用方写出的 MD、作者事件的语义订正为只进 verifier 上下文——扩展 1.6.0 是按它写的，装在更早的 framework 上，作者输入与读者审查两条链都对不上 |
| 2 | 本仓 manifest 已升 1.6.0 | 1.4.0 之后机制行为变过两轮；adapt 判态同时看机制指纹，版本相同而机制不同会报「包未升版」停下 |

## 1. adapt 会自动带过去的（`/story adapt <内网根>`，按 SKILL §1–§7 走）

- **机制文件 52 处**：新增 5（`framework-patch.yaml`、`hooks/shared/knowledge-use.mjs`、`hooks/shared/reader-review-task.mjs`、`hooks/spec/author.mjs`、`skills/story/scripts/materials.py`）、删除 5（`paraphrase.mjs`、`verdict-set.mjs`、`story-verify.md`、`source-units.mjs`、`story-template.md`）、修改 42（SKILL、六份 rules、两份 phases、合同、七个脚本、六阶段 post_check 与 shared、六份 overlay、adapt 自身）。adapt 按 §2 表整目录同步，删除的会一并删。
- **framework 补丁 0 条**：`framework-patch.yaml` 已从包里删除。上游 `0143e21` 合入或订正了扩展依赖的全部改动，adapt 对缺这份文件的语义就是「不依赖」，§2.5 整节跳过。内网 `framework.config.json > integrity.drift_allowlist` 里早先按本包追加的那 12 条已经失效，删不删由内网定。
- **manifest**：`provides.hooks` 六阶段只剩 `post_check` 与 `pre_verifier`——作者事件整体退场（登记在那里到不了动笔之前）；`provides.knowledge` 由内网自己的清单合成，包不覆盖。
- **入口段** `skills/story/AGENTS.section.md`：作者要求改为动笔前自己取——原则页 `doc/extensions/hooks/<阶段>/author.md`，spec 阶段另跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>`。adapt 只写标记区之内。
- **`.gitignore`** 追加两行：`doc/extensions/.adapt-*/` 与 `doc/features/**/AR/story-src/drafts/`（adapt 第一步，`--scan` 给出、`--check` ⑦ 核）。

## 2. adapt 不管、要人做的

| # | 事 | 说明 |
|---|---|---|
| 1 | `framework.config.json` 除 allowlist 外**没有新键** | 本仓批次 4 → HEAD 只多了 allowlist 条目，不用加配置 |
| 2 | 内网知识文件不动 | 三类知识 frontmatter `kind:` 批次 4 已有；`knowledge-use.yaml` 是每个需求生成的，不是知识文件 |
| 4 | 入口 `.codex/skills/story/SKILL.md` | 批次 4 → HEAD 没变，不动 |
| 5 | 需求方回话规约 | 内网测试时人只回选项号或一句短语（`TEST.md §3.0`），补料先放文件再回话；这是测试方式，不进包 |

## 3. codex 上跑不到的地方（先知道，不是升级项）

- codex adapter 上游已登记 `verifier_subagent: true`（2026-09-05），发布器那一环整体不存在了——报告由派 verifier 的那个 agent 原样写出。所以 spec 闭环在 codex 上是通的，读者审查这一项判得到。内网测试终点因此可以定在「spec 闭环 + `story-build check --deliver` 通过」。
- plan 及之后五个阶段的知识义务门**未经批次 5 实跑证明**（登记在 `06-验收追踪矩阵`），内网若跑到 coding，撞到问题按原样记，不现场改。

## 4. 内网跑一单看什么（与五跑判据同）

作者是否在 `AR/story-src/drafts/` 的草稿上写并用 `chapter --from 草稿` 落盘；首次 `story-build check` 的 ⑫c / ⑩ / ⑨ 是否为零；登记时 `story-build project` 有没有被调用、附录 D 表与 `knowledge-use.yaml` 一致；流程章至少一张图；术语行不少于草稿打底行；日志里不出现读 `story-build.mjs` 源码。
