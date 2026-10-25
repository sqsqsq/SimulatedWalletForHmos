# 步骤 16 · 五跑后的修正：schema、固定形态落地、附录序号

**状态**：已实施（四提交 `f683fca9` / `84663536` / `b389f245` / `4a837c7a`），评审 `reviews/15` §14 判不通过——返修项与追加项全部归 **批次 6 `steps/02`**（原批次 5 步骤 17，2026-09-05 随 framework 对齐上游迁走），本文件只保留步骤 16 的范围。证据：`reviews/14` §5（schema）、`reviews/15` §13（产物）。
五跑首次起跑（`story-suite-20260905-145704`）story 段 3 次停等、作者在草稿上写、首次 check 1 处、读源码 0 次、流程章有图、附录机器投影齐——步骤 15 的方向已经对了。本步做四件事：S1 schema 缺陷；S2 按 `16-固定形态与自由形态设计.md` 把固定形态整套落地；S3 附录序号；S4 矛盾要在作者与审查两处被问到。

## 0. 三处缺陷

| 编号 | 现象 | 根因 | 归属 |
|---|---|---|---|
| S1 | verifier 15:42 交稿，opencode 插件判 request `invocation_request_unparseable`，报告只落 bedside；主模型从 15:42 起在 framework 里查因，卡住 | framework 3.0.0 正式版把 request `schema_version` 升到 1.1（`verifier-request.ts` 第 32 行；claude 钩子模板同步），步骤 14·1.2 重打 opencode 插件时只跟上 subject @2，`record-verifier-report.js` 第 55 行常量仍是 `"1.0"`，第 160 行按它整份拒收。字段集两边一致，只差这一个常量。物化件与测试夹具同为 1.0，所以 24 条全绿 | 步骤 14 遗漏；评审 reviews/14 §2 漏判 |
| S2 = R31 | story §3.3 多出「交接约定」一节，单列表四行填的是端云约定；本需求没有兄弟单据 | 合同 `03-scope.form.tables_when` 只给「特性分工」加了 `siblings` 条件，「交接约定」没条件；草稿渲染了单列锚表——槽位在，作者就会填 | 步骤 15 F1 |
| S3 = R32 | 附录五节标题没有 `A.`–`E.`（金样有，合同注明「必带（模板给形态）」） | 序号原来由退场的模板给；草稿不带、`number` 只铺数字序号 | 步骤 15 F1 |

## 1. 改法

### S1 · 插件 request schema 跟上 1.1

- `framework/agents/opencode/templates/plugin/record-verifier-report.js` 与 `.opencode/plugin/record-verifier-report.js`：`VERIFIER_REQUEST_SCHEMA_VERSION` 改 `"1.1"`；其余不动（字段集已与 claude 钩子一致）。
- `test/story/tests/test_opencode_verifier_publisher.py`：夹具 request 改 1.1；**加一条对账**——从 `framework/harness/scripts/utils/verifier-request.ts` 读 `VERIFIER_REQUEST_SCHEMA_VERSION` 现值，与插件模板、物化件的常量比，三处必须相等（读文件取值，不写死数字）。**再加一条真链路**：在 `test_verifier_chain_in_workspace.py` 里用 harness 真实生成的 request 喂插件的解析与发布，走到 canonical 落盘——两边夹具一致而真实链路不通，正是这次的形态。
- `artifacts/01-framework-opencode-verifier.patch` 从 `git diff main HEAD -- <6 个 opencode 文件>` 重生成；`01-upstream-handoff.md` 补一句 schema 1.1。
- `framework-patch.yaml` 18 条不变。

### S2 · 固定形态整套落地（真源 `16-固定形态与自由形态设计.md` §1–§3）

**story 合同与草稿**

- `story-chapters.json`：按设计 §2 逐章写 `form`——`prose`（段数与每段提示）、`ordered`、`list`（固定项名）、`labels`（5.x 三标签、9.3 三标签）、`diagram`、`image`、`tables`（全列，第一列即锚）；`when` 给 3.3/9.5（`siblings`）、4.3（`decisions`）；6.x 状态表**草稿渲染、不设条件、不核**（有没有图不等于要不要状态说明）；`sections` 档：4 章 `named` 必有节只列 4.1（4.2 / 4.4 真有才有，名字固定），7 章 `named` 7.1–7.2，9 章 `named` 9.1–9.4，5/6/8 章 `named` 只列固定节（5.1）。
- `skeleton` 草稿按形态渲染：段落提示行、`1. {{…}}`、`- {{固定项}}：{{…}}`、加粗标签行 + 占位、图复制、图引用串 + 承接占位、表头全列 + 一行占位；3.3/9.5 只在 `siblings` 成立时出现，标题渲染「与 {{兄弟}} 的交接约定」。
- `check ⑪`：`tables` 只核第一列；加「有序列表在」「标签在」「不该有的节不在」三种机械事实；叙述段与无序列表不核。
- `story-write.md`「什么内容用什么形态」按设计 §0 的六形态表收口，删与合同重复的行；「决策登记」不动。

**spec 三章**

- `post_check`：§9 每节表外出现段落或引用块 → 报「§9.x 表外有段落：约定进表格；实现取舍写 `spec/notes.md`，决策写决策件」（给去处，不只说删）；§10 命中行的落点**由作者显式声明类型，脚本按类型分别校验，不按「查不查得到」反推**（外部第九轮：按查找结果反推类型，接口名拼错也会滑成非实体落点，验真永远不会失败）。`knowledge-use.yaml` 每条命中项二选一：`contract: <§9 实体名>`（脚本验真：必须在 §9 五张表第一列，查不到就 FAIL）或 `impact: <实际影响对象>`（脚本只核非空，内容由读者审查判——只写「页面」「资源」这种泛称审查要点名）；两个都空或都填 → post_check 报。`render` 把两种落点投进同一列，前缀区分（`§9 · getAutoTopupPolicy` / `影响 · 签约页与管理页的布局参数`）。**不设字数门禁**——40 / 60 字只在 `author.md` 作写作提醒（外部评审第七轮：接口参数与失败处理可能合理超长，字数替代不了内容判断）。
- `knowledge-use.yaml` 骨架：`requirement` 改列表（`init` 生成 `- ` 占位，一条一句），`contract` 与 `impact` 命中时二选一（见上）；`render` 逐条成行（同编号多行）。**消费者一并改**：`knowledge-use.mjs`（`readUse` / `coverageProblems` / `renderZones`）、`story-build.mjs` `knowledgeUseVerdicts`（附录 D 的依据**完整保留全部条目**：同编号逐条成行，或同一格内分项；不得截取首条）、`hooks/spec/author.mjs` `acceptanceKeys`、`pre_verifier.mjs` 注入的判据文本；改完 grep `requirement` 零处按字符串读。`author.md`「知识判断怎么写」同步一句。

**替代关系**：合同 `form.note` 里的散文形态说明由结构化字段替代（note 只留一句主形态）；R31/R32 与「§9 长文」都由这一步关掉，不单独打补丁。

### S4 · 矛盾为什么能穿过作者与独立审查（外部第七轮，采纳）

五跑 story 把 PRD 自带的矛盾（旅程表「未实名引导去认证」vs AC-R1「未实名看不到入口」）原样传到了验收，流程图里实名回来的节点没有出边；作者没停、读者审查没报。补两处**问题**，不补判据：

- `story-write.md` 统稿六项加第七项：**同一条件在流程、功能、异常、验收里的说法一致**；材料自相矛盾时不选一边照抄，写进决策件（定得了的 `settled`，定不了的 `open` 交评审）。`copyedit.md` 相应七行，`check ⑫d` 的行数常量随之改。
- `reader-review-task.mjs`（读者审查任务书）加一问：「同一条件在各章的说法一致吗；图里每条路径有明确后续或合法终态吗；材料矛盾的地方作者定了口径吗；§10 非实体落点写的是实际影响对象吗」。这是 verifier 的语义判断，不进 check。
- **先核五跑证据，再说根因**（外部第八、九轮）：作者侧——`story-write.md` 已写「不确定、矛盾、错误的要人评估」，作者没把 PRD 旅程表与 AC-R1 的矛盾登记进决策件，规则在、没执行。verifier 侧——**规则已定义且已送达**：overlay `story_reader_review` 的 blocking 列表明写「前后矛盾」，五跑 `ai-prompt.md` 第 567 行原样送到 verifier；它没有报。所以对 verifier 不是「没被要求看」，是「要求在、没发现」，原因待证据——一个可核的猜想是任务书让它「按章过一遍读者问题」，矛盾却横跨 §5 与 §8 两章，逐章审看不到；本步加的那一问把「跨章比对」说成显式动作，是补强不是补职责。六跑若发现了，只能证明补强有效；没发现，再查它读了什么、怎么读的。

### S3 · 附录小节序号由 `number` 铺

- `number` 给附录章的小节按合同顺序铺 `A.`–`E.`（与章序、小节序同一处实现，同一条幂等规则：已有对的不动、错的改）；草稿与 `project` 投影都不带序号，标题比较照旧走规范化通道剥序号。
- `check ①` 不变（它按规范化后的名字比）。

### 顺带（不改机制）

- review.md 2.2.1「档位沿用产品给定值」是纯事实复述占了表态位。`story-write.md`「决策登记」的准入判据已经写着「材料直接给定、没有判断参与的纯事实复述不进」，本次不加文字、不加判据；六跑再看是否重现。

## 2. 提交

四个提交已落地（S1、S2a+S3、S2b、S4）。评审发现的返修（R33、R34、M02；R35 随批次 6 步骤 1 的插件退场而消失）与用户新要求（S5–S7）在批次 6 `steps/02`。

## 3. 六跑判据

五跑判据（`steps/15` §4、`reviews/15` §5/§11/§12）全部保留，另加：

| 项 | 判据 |
|---|---|
| verifier | 同一产物不重审（同 subject 不二次调用）；作者按审查意见修订后再审是正常返修，不算重复；插件发布 canonical（不是 bedside），PASS 后直接 check-receipt → archive |
| 一致性 | 未实名的说法在 §5/§6/§7/§8 一致；流程图无悬空节点；PRD 矛盾在决策件里有口径 |
| story §3 | 无兄弟单据时没有「交接约定」节 |
| 附录 | 五节标题 `A.`–`E.` |
| 槽位表 | 参与方、取舍、风险表列数 ≥ 合同列数（作者按草稿写，不是单列） |
| §9 交付 | 9.2 四项列表、9.3 三标签段（段落长短只作建议，不作通过条件） |
| spec | §9 表外零段落（在真实 spec 上不误报）；§10 每条要求独立可懂、必要条件齐、命中行落点齐 |
| 图 | SR 的 mermaid 在 spec 有标记对应；spec 每张 mermaid 在 story 各有一张且在讲它内容的那一节（管理交互那张落在讲管理的地方，周围文字是 story 自己写的）；10 张里该引的 5 张各在讲它的节里、图前有承接句、无图连图；不该引的 5 张一张不引且清单逐张写理由 |
| 标签 | 分支节与回退设计带固定标签（时机 / 方案 / 走向；回退动作 / 兼容性说明 / 可靠性说明） |
| 总时长 | 有闭环读数；五跑到 verifier 交稿 43 分钟，六跑以此为参照 |

六跑闭环后按 `TEST.md §10` 给三轴建议分（五跑先评：产物 88、知识 90），用户确认。

## 4. 预算

S1 ±0（一个常量）；S2 data +40（合同各章 form 结构化）、scripts_mjs +30（草稿六形态渲染、⑪ 三种机械事实）、hooks_mjs +40（post_check 三条、render 逐条成行）、prompts_md ±0；S3 scripts_mjs +15。总量 8732 → ≤ 8860，上限 8900。判据只加机械事实，无语义代理。

## 5. 不做的事

- 不改 framework 本体；不给 codex 补 verifier。
- 不为 review 2.2.1 加判据；不核行数、不核措辞、不核业务名；不给叙述章加表。
- 不动 T2–T5、F3、R17–R30 已落地的行为。
