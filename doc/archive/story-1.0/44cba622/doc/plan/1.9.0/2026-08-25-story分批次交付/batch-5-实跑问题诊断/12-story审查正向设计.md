# 12 · story 审查的正向设计（评审者拟，2026-09-04，待用户确认后由执行会话实施）

用户要求：verifier 对 story 的适配不再来回打补丁，正向解决。本文先把失效链讲清，再从目标出发定最小机制，并写明每项替代了什么。

## 1. 目标

story 写完并登记之后，一个**独立、只读、带着材料**的审查者读完全篇，回答「关键事实缺了没有、编了没有、材料里的图用了没有、每章的读者问题答了没有」，
产出**两类结论**（阻断 / 建议），结果**与这一版 story 绑定**落盘，spec 闭环只认这份结果。审查者有没有区分力，从真实产物上用户找到的问题它报没报来看。

## 2. 二跑里它怎么坏的（事实，来自事件流与 opencode 会话库）

| # | 事实 | 后果 |
|---|---|---|
| F1 | verifier 拿到的 `ai-prompt.md`（117 KB）第五节「语义检查项（你的核心任务）」只列 framework 的 10 项；扩展 overlay 的三项（两条 knowledge、一条 `story_reader_review`）只出现在第三节的规则 yaml 原样转录里。framework 的规则是：overlay-only 项要由 profile 的 `verify-spec.overlay.md` 声明才进任务清单，扩展没有这份声明 | 三项都不是「任务」 |
| F2 | 扩展的 `pre_verifier.mjs` 只把 `knowledge_` 前缀的判据写进「输出要求」（`KNOWLEDGE_CHECK_PREFIX`），`story_reader_review` 被过滤掉 | verifier 第一次完全没做 story 审查（报告里零提及）。**这是步骤 10 小段 2+3 的实现缺陷，评审当时没看出来** |
| F3 | 扩展要求结果写成 markdown「以 id 为标记的块 + 两个小节」，而 verifier 按 framework 契约输出 YAML `checks[]` | 补做之后又缺小节，再 FAIL |
| F4 | 门禁 `storyReviewProblems` 读任意匹配文件名（含 `verifier-report.md`），不限插件发布的 JSON | 最后是主模型把 verifier 的文本转写成文件过的门 |
| F5 | 同一个 verifier 会话要做 12+ 项 spec 检查再通读 300 行 story 与三份材料 | 它读了 story、materials.json（登记三张图）、decisions，仍判「零阻断」——**三张图一张没进 story，它没报，用户报了** |
| F6 | 审查任务的问题清单（合同 `questions` + `chapter_dimensions`）没有一条问「材料登记的每张图，用了没有；没用，理由在哪」 | 图丢失这个两轮复发的形态，在任务定义里就没有对应的问题 |

合计：verifier 环节 20 分钟返工，且结果无区分力。F1–F4 是送达与格式问题，F5–F6 是任务定义问题；打补丁只能修前四条，正向要一起改。

## 3. 设计原则

- **单一任务**：story 审查是一件独立的事，不和 spec 的 12 项检查挤在一个会话里。
- **单一格式**：审查者只按 framework 的 YAML 契约输出，扩展不另立 markdown 形态。
- **单一真源**：门禁只读插件发布、带身份与指纹的 JSON；主模型写的任何文件不算证据。
- **单一入口**：审查者要看什么、按什么判、答什么问题，只在一份合同里（`story-chapters.json`），任务书从它生成。

## 4. 机制（方案 A，推荐）

### 4.1 触发与请求

`story_flow.py story` 登记成功后，生成 `AR/story-src/reader-review.request.json`：

```
kind: story_reader_review_request（新 kind）
subject_id: sha256(story.md 内容 + materials.digest + decisions.json 内容 + 合同版本)
inputs: story.md、materials.json（含每张图的路径与 caption）、decisions.json、spec.md、story-flow.json
task_path: AR/story-src/reader-review.task.md（由合同生成，见 4.2）
```

主 agent 用**同一个只读 verifier 子代理**跑它（task prompt = 这份 JSON，规则同 framework 的 verifier）。这一步写进 `phases/spec.md` 的阶段内顺序：登记 → 审查 → build review → harness。

### 4.2 任务书（从合同生成，不手写）

`story-build review-task` 从 `story-chapters.json` 渲染任务书：读者身份与输入清单；十章各自的读者问题；章级维度；**图片清单逐张列出（路径 + caption）并要求逐张回答「story 用了 / 未用及理由」**；
关键事实与编造两问；输出要求 = YAML `verification_result.checks[]` 里恰好一条 `story_reader_review`，`details` 下两个键 `blocking_findings` 与 `advisories`（都是列表，空列表是结论）。
任务书里**没有**逐条对账、裁决表、引文长度。

### 4.3 发布与绑定

插件（`record-verifier-report.js`，framework adapter，步骤 1 范围，作为上游补丁）按 `kind` 分派：`story_reader_review_request` 的终态发布为
`AR/story-src/reader-review.<subject>.json`（agent_id、subject、verdict、两个列表）。四方对账口径不变。

### 4.4 消费

- spec 的 `post_check`：`story_review_persisted` 只读 `reader-review.<subject>.json`，subject 必须等于**当前** story.md / materials / decisions 重算值；`blocking_findings` 非空即 BLOCKER。
- `story-build build`：review.md 机器区新增「读者审查」一节，从这份 JSON 渲染两类结论（人工区不动）。
- 台账：S01、C01 等 observed 形态的 `observed_by` 改指向这份 JSON 的对应键。

### 4.5 退场（每项写替代物）

| 退掉 | 被什么替代 |
|---|---|
| overlay 里的 `story_reader_review` 判据 | 独立请求 + 合同生成的任务书 |
| `verifier-report.mjs` 的 markdown 块解析（`STORY_REVIEW_ID` / `STORY_REVIEW_SECTIONS`） | 读 `reader-review.<subject>.json` |
| `pre_verifier.mjs` 的 `knowledge_` 前缀过滤 | 改为「overlay 里全部扩展判据」进输出要求（knowledge 两项仍走 spec verifier） |
| 门禁接受 `verifier-report.md` 等任意同名文件 | 只认插件 JSON |

## 5. 方案 B（最小改，不推荐）

留在 spec verifier 内：pre_verifier 把 `story_reader_review` 加进输出要求；格式改为 YAML checks 条目两键；门只读插件 JSON 的 `report_text`；任务问题加「图片逐张」。
能消掉 F1–F4、F6，消不掉 F5（一个会话 12+ 项 + 通读）。

## 6. 配套（用户 2026-09-04 的两条观察）

- **图片登记改脚本动作**：`import_sources.py register-ux <asset> --name <语义名> --caption "<这张图是什么>"` 复制到 `ux-reference/`、写 README 行、刷新 `materials.json`（image 条目带 `caption`）。
  作者任务包与 4.2 的任务书都从 `materials.json` 逐张列「路径 + caption」。替代：作者手拷 + 手写 README。
- **工作区按黑名单复制**：`run_multi_case.py` 改为复制仓库根全部内容，排除 `.git / output / test / tools / scratch / node_modules / oh_modules / 构建产物 / doc/features / harness state`；边界校验不变。

## 7. 验收

- 离线：请求生成、任务书渲染、插件按 kind 发布、门禁按 subject 消费，各一条测试；夹具只用金样与中性材料，不造缺陷稿。
- 真实：下一次 CLI，story 审查是独立会话；报告落 `reader-review.<subject>.json`；`blocking_findings` / `advisories` 两键在；**图片逐张有答复**。区分力仍从用户在真实产物上找到的问题它报没报看。
- 预算：hooks_mjs 约 +120（请求/消费）、scripts_py 约 +60（登记命令、请求生成）、prompts_md 持平（任务书由合同生成）、退场约 −80；插件改动不计入。

## 8. 归属

这是行为变更，不属步骤 11。建议作为**批次 5 的步骤 12**（回开步骤 1/7/8 的组合）在三轴评分之前做——否则评分的 verifier 轴没有对象。用户裁定。


## 9. 修订（2026-09-04）

方案 A 需要改 framework 的 verifier 协议（只认一种请求 kind）与三个 adapter 的发布器，属 framework 需求而非 bug；二跑里 resume 未发布是自由文本调用违反协议，不是插件缺陷。
本批采用**方案 B 的完整版**（见 13 号 D4）：送达、单一格式、只读插件 JSON、任务书含图片逐张问，全部在协议内完成，不改 framework 与 adapter。方案 A 作为对 framework 的需求登记，第三跑若证明单会话摊薄仍漏审再提。
