# 内网升级清单：批次 4（扩展 1.3.0）→ 当前 HEAD（codex 宿主）

评审会话 2026-09-05 按 `git diff e2227f80..HEAD` 逐项核出。内网用 codex，不带 opencode 那 6 条。

## 0. 先做两件事，否则后面全白做

| # | 事 | 怎么核 |
|---|---|---|
| 1 | **内网 framework 先同步到 3.0.0 正式版 `85e266f`** | `framework/RELEASE-MANIFEST.json` 的 `source_commit` = `85e266f185fbaec92263377dc71f6c15512ea3db`。补丁清单带的是整文件（`harness-runner.ts`、`hooks-dispatcher.ts` 等），framework 版本不同就是把 3.0.0 的文件盖进旧版 |
| 2 | 本仓 manifest 已升 1.5.0（评审会话直接改，随本清单同一提交） | 1.4.0 之后机制行为又变了；adapt 判态现在同时看机制指纹，版本相同而机制不同会报「包未升版」停下 |

## 1. adapt 会自动带过去的（`/story adapt <内网根>`，按 SKILL §1–§7 走）

- **机制文件 52 处**：新增 5（`framework-patch.yaml`、`hooks/shared/knowledge-use.mjs`、`hooks/shared/reader-review-task.mjs`、`hooks/spec/author.mjs`、`skills/story/scripts/materials.py`）、删除 5（`paraphrase.mjs`、`verdict-set.mjs`、`story-verify.md`、`source-units.mjs`、`story-template.md`）、修改 42（SKILL、六份 rules、两份 phases、合同、七个脚本、六阶段 post_check 与 shared、六份 overlay、adapt 自身）。adapt 按 §2 表整目录同步，删除的会一并删。
- **framework 补丁 12 条**（`kind: extension_dependency`，codex 目标不带 6 条 opencode）：`harness/scripts/author-context.ts`（新文件）、`harness/hooks-dispatcher.ts`、`harness/harness-runner.ts`、`specs/lifecycle-hooks-schema.yaml`、`skills/reference/agent-behavioral-principles.md`、`skills/feature/spec/SKILL.md`、`skills/feature/device-testing/SKILL.md`、`docs/concepts/phase-terminology.md`、四份 spec/plan 模板。adapt 复制文件并往内网 `framework.config.json > integrity.drift_allowlist` 追加 12 条。
- **manifest**：`provides.hooks` 六阶段各多一个 `on_context_load` 事件（spec 两条：`author.md` + `author.mjs`）；`provides.knowledge` 由内网自己的清单合成，包不覆盖。
- **入口段** `skills/story/AGENTS.section.md`：作者要求改为经 `author-context.ts --phase <phase>` 取得。adapt 只写标记区之内。
- **`.gitignore`** 追加两行：`doc/extensions/.adapt-*/` 与 `doc/features/**/AR/story-src/drafts/`（adapt 第一步，`--scan` 给出、`--check` ⑦ 核）。

## 2. adapt 不管、要人做的

| # | 事 | 说明 |
|---|---|---|
| 1 | `framework.config.json` 除 allowlist 外**没有新键** | 本仓批次 4 → HEAD 只多了 allowlist 条目，不用加配置 |
| 2 | 内网知识文件不动 | 三类知识 frontmatter `kind:` 批次 4 已有；`knowledge-use.yaml` 是每个需求生成的，不是知识文件 |
| 4 | 入口 `.codex/skills/story/SKILL.md` | 批次 4 → HEAD 没变，不动 |
| 5 | 需求方回话规约 | 内网测试时人只回选项号或一句短语（`TEST.md §3.0`），补料先放文件再回话；这是测试方式，不进包 |

## 3. codex 上跑不到的地方（先知道，不是升级项）

- codex adapter **没有 verifier 发布器**（只有 claude / codeagent / opencode 有）。story 段到 spec 三份产物、harness PASS 都能跑；spec 闭环要 verifier PASS 那一步过不去，story 读者审查记「不适用」。内网测试终点定在「三份产物齐 + harness PASS + `check` 干净」，或换有发布器的宿主。
- plan 及之后五个阶段的知识义务门**未经批次 5 实跑证明**（登记在 `06-验收追踪矩阵`），内网若跑到 coding，撞到问题按原样记，不现场改。

## 4. 内网跑一单看什么（与五跑判据同）

作者是否在 `AR/story-src/drafts/` 的草稿上写并用 `chapter --from 草稿` 落盘；首次 `story-build check` 的 ⑫c / ⑩ / ⑨ 是否为零；登记时 `story-build project` 有没有被调用、附录 D 表与 `knowledge-use.yaml` 一致；流程章至少一张图；术语行不少于草稿打底行；日志里不出现读 `story-build.mjs` 源码。
