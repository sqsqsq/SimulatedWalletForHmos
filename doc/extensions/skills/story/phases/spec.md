# `/story` 链 · spec 阶段作业包

> 读者：从 `/story` 链进入 spec 阶段的作者。时机：S4 收口之后、动笔之前读一遍。扩展对所有 spec 的通用要求见
> [`hooks/spec/author.md`](../../../hooks/spec/author.md)；本页只补 `/story` 场景独有的：材料从哪来、
> 要出几份产物、阶段内顺序、§9.1 怎么取证。

## 一、上游输入必读

正文生成前必须读下面几份（存在时），并在 `spec/context-exploration.md` 的 `key_inputs_read` 里记录：

| 文件 | 是什么 |
|---|---|
| `doc/features/<feature>/AR/design.md` | 开发需求文档，本阶段主输入。「相关文档链接」表与「上游索引」章是回查 SR/RR 的定位索引 |
| `doc/features/<feature>/RR/prd.md` | 产品 PRD——业务场景全景与验收意图 |
| `doc/features/<feature>/SR/design.md` | SE 系统级设计——跨部件交互、云侧接口、系统级存储，是 §9.1 技术契约的取证源 |
| `doc/features/<feature>/AR/story-src/init-analysis.md` 第 ⑥ 节 | 读材料时已经形成的来源初筛：每块内容对本需求的作用、还要核实的疑点、不适用的依据 |

**来源初筛是 Spec 的起点，不是 Spec 的替身**：没变的判断直接沿用，写 Spec 时只补新结论、处理新冲突。
初筛里登记的作用与疑点不因 Spec 没写到就算处理完——成文与审查还会回来对照它和原文。

**「本 AR 范围与拆分说明」是 Scope 与功能清单的边界依据**：拆分表里归**兄弟 AR 或「待立项」**的那几份
**不属于本次**，不进功能清单与验收。它们涉及的模块登记 `out_of_scope_modules` 时，`rationale` 写
「归属 <兄弟 AR 编号>」而不是「本需求不做」。**「无拆分」不等于「本 AR 承载全部」**，同 SR 有兄弟 AR 时
后者是假的（三形态见 [`rules/ar_design_init.md`](../rules/ar_design_init.md) §3）。

## 二、本阶段产出三份文档

spec 阶段是**一次 pass 产出三份**，事实同源，不得只交 `spec.md` 就宣告闭环：

| 产物 | 作者 | 持有什么 | 读者 |
|---|---|---|---|
| `spec/spec.md` | AI | **代码要求** | AI 编码 / 出用例 / 门禁 |
| `AR/review.md` | 由 `AR/story-src/decisions.json` 渲染 + **人确认** | 每条决策的澄清叙述与人的填写位 | 评审者 |
| `AR/story.md` | AI（按章写、按章落盘） | 完整需求叙事 + 判断 + 附录规约判定 | 评审者（归档件·叙事主件） |

- `AR/review.md` **不手写**：你把每条决策登记进 `decisions.json`（什么算一条议题、澄清正文怎么分段，
  见 [`phases/story-write.md`](story-write.md) 的「决策登记」）；分层、编号与表态位由脚本生成。
  **表态位只能由评审人填**：填写位里的编号、勾选与文字你一个字都不写，推荐项也不替人预选——代填即 BLOCKER。
- **story 不是 spec 的排版件**：spec 的可标识事实、PRD 的业务语境、SE 的全局方案，以及无编号的
  数据与交付事实，都必须在 story 有完整落点；它还要补足判断、权衡、风险与规约判定。

### 阶段内顺序（story 在这里成文，不另起一步）

`spec.md` 与 `decisions.json` **定稿之后**、跑 harness **之前**，按下面走完。成文方法见
[`phases/story-write.md`](story-write.md)。

```
node .../story-build.mjs skeleton --feature <feature>  # ① 当前输入 + 写作设计空壳 + 十章骨架 + 十份章草稿
#                                 （流程、材料、来源、Spec 与决策登记一次预检完，全过才写盘）
#                              ①b 写整篇写作设计：AR/story-src/story-template.md 的阅读主线与每章骨架，
#                                 写完再跑一次 skeleton——它把骨架铺进草稿，给出第一章的写作动作
#                              ② 按章写：照骨架在草稿上写，经 `story-build chapter --from <草稿>` 原子落盘；
#                                 每次落盘都报还剩哪几章带着待写 marker
#                              ②b 回看：十章齐后 skeleton 给出回看清单，逐条撞两问、处置回真源
python .../story_flow.py story --feature <feature>   # ③ 登记（自带 project / number / build / check）
#                              ④ 跑 spec harness
#                              ⑤ 按 harness 末尾 NEXT: 行派 verifier
#                              ⑥ check-receipt → check --deliver 交付门
```

- **附录的接口、数据·配置·事件、改动边界、规约判定四节不用你写**：它们是 spec §9.1 与
  `knowledge-use.yaml` 的投影，要改投影出来的内容，改真源。登记之后 spec 改了，`story-build project`
  直接重投这几节，不必 reopen。
- **③ 登记在 story 写完之后**：判断在成文过程中还会长出来，先登记进 `decisions.json` 再登记成文，台账才完整。
  `story` 自己跑编号、渲染 review、全篇 `check`，**不必自己先 build**。登记之后作者写的部分冻结，
  要改先 `reopen`。
- **④ 之前必须走完 ①–③**：spec 门禁核的是「三份产物齐备」，`story_written` 未登记即 BLOCKER。

### 闭环

**⑤ 派不派只看 `NEXT:` 行**，不按宿主名分叉：它说要派就派一次；说本宿主没有审查员就直接进 ⑥。
请求与报告的路径都由 summary 的 `verifier_request`、`verifier_report` 给：不要自己拼 subject、不复用上一轮的文件名——
拿错了 `check-receipt` 判 `report_missing`，退回沿用历史 PASS，表面闭环、实际没审。
调用只带 request JSON；verifier 的回复由你**原样全文**写到 `summary.verifier_report` 指向的那份文件，
再完整跑一次 harness 采纳它（不用 `--sync-closure`：它对已闭环的阶段不改写）。读 summary 确认
`verifier_subject_id` 与报告终态块对得上、`readiness_signals` 里没有 `semantic_not_reverified`。
门禁核这份报告：格式不合或缺判据的回复每次运行都报、不计结论，重投同一份 request 拿完整回复；
同一审查对象只认第一份合规结论，之后换了内容的重投不算。

**报告回来之后怎么处置，全扩展只有这一张表**：

| 报告结论 | 你做什么 | 闭环方式 |
|---|---|---|
| 有阻断项 | 按阻断项返修：story 侧 `story_flow.py reopen` → 照它给的下一步走 → 改最早出错的那一处（Spec、决策登记、写作设计或章草稿）→ `chapter` → `story` 重新登记 | 完整 harness → 取新请求再派审 |
| PASS，改动只影响表达（措辞、格式、补说明、补可回查依据） | 改完跑 `harness-runner.ts --revalidate --feature <名>` | summary 记 `completed_with_prior_review` 与 `script_revalidated`；notes 写「按 <对象> 报告的建议修改，未独立重审」；交付门放行 |
| PASS，改动改变业务口径、范围、验收、契约实体 | 改完完整跑 harness | 取新请求再派审 |
| PASS，建议不在本阶段修 | 不改材料 | notes 逐条记建议与去处（下一阶段或评审） |

- 改动属于哪一类由你判断，写进 `<阶段>/notes.md`；门禁核报告里每条 WARN、FAIL 在 notes 里都有处置记录。
- 读者审查判 WARN 而没有阻断项时交付门放行，建议项进 notes；只有阻断项才拦。
- 审查之后改了知识判断或决策状态，notes 写新依据——只为消掉审查意见而改判断不算处置。
- 门禁反复报同一问题而你判断改不动时，停下向人说明缺什么、需要谁提供，不靠多跑几次过关。
- `/story update` 里改了业务的阶段，在 update-notes 写「业务改动的阶段：…」，`update --action close` 核它们有当前对象的报告。

**⑥ 回执不用你填**：它是 harness 的只读投影，`check-receipt` 自己先生成再校验；要写备注写 `<phase>/notes.md`。
**`check --deliver` 是交付门**：它把回执再跑一次，再核读者审查那一项的结论；本宿主没登记审查员时如实记一笔
「未经读者语义审查即交付」。通过之后按 SKILL 停等表问一次「归档送审 / 进入 plan」。

## 三、§9.1 技术契约怎么写

core spec 模板在 §8 之后预留了锚点「宿主扩展治理项」：写成「## 9. 宿主扩展治理项」，技术契约、规约约束要求、
设计模式候选登记是它的 9.1–9.3，附录是全文最后一章。模板见 [`templates/spec-sections.md`](../templates/spec-sections.md)。
9.1 技术契约下分 9.1.1 端云接口 / 9.1.2 数据存储 / 9.1.3 配置项 / 9.1.4 埋点 / 9.1.5 依赖变更。

**形式一律表格，不按条目数切换**：每个小节要么是一张表（表头固定、每行一个编号实体、
单元格 ≤30 字），要么是一行「不涉及：<现状扫描依据>」。不写散文段、不写嵌套 bullet、
不建空表，小节不得删。**9.1.4 埋点例外**：它是埋点设计的唯一完整说明，一个指标一个小节，用短段、表与列表写，
图放在它讲的业务章，这里用文字说明或链接过去；形状见模板。

写之前先读**两份**——「方法 + 数据」缺一不可：

| 读什么 | 给你什么 |
|---|---|
| [`reference/evidence-rules.md`](../reference/evidence-rules.md) | **怎么判**：各节取证规则、结论写法、取不到时怎么降级 |
| 激活清单里 `kind: facts` 的项目知识 | **这个工程有什么、叫什么、在哪**：照它写。它没登记的面才实扫仓；与仓不符时以仓为准，在产物里登记「项目知识矛盾」，**不改知识文件** |

**代码库现状**（仓内文件路径、检索零命中结论）是结论的一部分，作为表格的一列写进正文。
别拿平台常识替代它：某个 API 在别的工程常见，不等于本工程在用；项目知识里已核实为「没有」的能力，不要选进新设计。

**防重复**：写之前先查 spec 已有章节，同一件事只写一处。加密 / 脱敏 / 调用方校验归 §7.3；
性能阈值归 §7.1；谁先上线、阻塞谁，以及排期与跨方确认，归《决策与评审记录》。
§9.1 不重复这些；「9. 宿主扩展治理项」的锚点表指向它们在决策记录里的议题。埋点设计写在 9.1.4 一处，业务章引用它。

## 四、交付门之后

交付门通过后只问一次「归档送审 / 进入 plan」（本地单只有进 plan），按 SKILL 停等表记录人的选择。
`AR/review.md` 是首版，评审人在每条议题的人工区勾同意、需修改或暂缓，要改成什么写在修改意见里；
你不代填、不动人工区。评审人的表态回来之后，由 `/story update` 承接（系统需求经取材取回，本地单读工作区里的
review.md），不在交付门上开修订轮。还空着的议题在进 plan 时逐条列出。
