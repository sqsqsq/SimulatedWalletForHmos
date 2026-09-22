# `/story` 链 · spec 阶段作业包

> 读者：从 `/story` 链进入 spec 阶段的作者。时机：S4 收口之后、动笔之前读一遍。扩展对所有 spec 的通用要求见
> [`hooks/spec/author.md`](../../../hooks/spec/author.md)；本页只补 `/story` 场景独有的：材料从哪来、
> 要出几份产物、阶段内顺序、§9 怎么取证。

## 一、上游输入必读

正文生成前必须读下面几份（存在时），并在 `spec/context-exploration.md` 的 `key_inputs_read` 里记录：

| 文件 | 是什么 |
|---|---|
| `doc/features/<feature>/AR/design.md` | 开发需求文档，本阶段主输入。「相关文档链接」表与「上游索引」章是回查 SR/RR 的定位索引 |
| `doc/features/<feature>/RR/prd.md` | 产品 PRD——业务场景全景与验收意图 |
| `doc/features/<feature>/SR/design.md` | SE 系统级设计——跨部件交互、云侧接口、系统级存储，是 §9 技术契约的取证源 |
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
| `AR/story.md` | AI（按章写、按章落盘） | 完整需求叙事 + 判断 + 合规回显 | 评审者（归档件·叙事主件） |

- `AR/review.md` **不手写**：你把每条决策登记进 `decisions.json`（什么算一条议题、澄清正文怎么分段，
  见 [`phases/story-write.md`](story-write.md) 的「决策登记」）；分层、编号与表态位由脚本生成。
  **表态位只能由评审人填**：填写位里的编号、勾选与文字你一个字都不写，推荐项也不替人预选——代填即 BLOCKER。
- **story 不是 spec 的排版件**：spec 的可标识事实、PRD 的业务语境、SE 的全局方案，以及无编号的
  数据与交付事实，都必须在 story 有完整落点；它还要补足判断、权衡、风险与合规回显。

### 阶段内顺序（story 在这里成文，不另起一步）

`spec.md` 与 `decisions.json` **定稿之后**、跑 harness **之前**，按下面走完。成文方法见
[`phases/story-write.md`](story-write.md)。

```bash
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

- **附录的接口、数据·配置·事件、改动边界、规约判定四节不用你写**：它们是 spec §9 与
  `knowledge-use.yaml` 的投影，要改投影出来的内容，改真源。
- **③ 登记在 story 写完之后**：判断在成文过程中还会长出来，先登记进 `decisions.json` 再登记成文，台账才完整。
  `story` 自己跑编号、渲染 review、全篇 `check`，**不必自己先 build**。登记之后 story 冻结，
  评审回流只改 `spec.md`，不动 story（见 SKILL.md「检视」节）。
- **④ 之前必须走完 ①–③**：spec 门禁核的是「三份产物齐备」，`story_written` 未登记即 BLOCKER。
- **⑤ 派不派只看 `NEXT:` 行**，不按宿主名分叉：它说要派就派一次；说本宿主没有审查员就直接进 ⑥。
  **调用只带 request JSON**；verifier 的回复由你**原样全文**写到 `summary.verifier_report` 指向的那份文件。
  写好之后读 summary：这份报告**还没被采纳**时，再完整跑一次 ④ 的 harness 采纳它——这是 ⑤ 的收尾，不是回到 ④ 重走链（采纳的判据、为什么不能用 `--sync-closure` 见 [update.md](update.md)「与闭环、修正入口的关系」第 4 步）；
  已采纳就进 ⑥。报告有阻断项或材料又变了，按真实反馈与 `NEXT:` 处理，不拿历史 PASS 代替。
- **⑤ 之后闭环链不回头（硬规则）**：有阻断项才返修（见下「失败出口」）；没有阻断项就走 ⑥，把链走完。
  **闭环之后发现的真实问题**（verifier WARN 里有内容依据的也算）走 framework 的修正入口：
  `harness-runner.ts --correction-init` 按修正三问定责任层 → 改真源 →
  `harness-runner.ts --revalidate --feature <名>`——它只重跑脚本门禁。
  **这条路不重跑 spec 闭环链、不手动派 verifier**：每跑一次 harness 都换一份审查对象，
  每派一次就是整份再审，而这里改的是收口后冒出来的局部问题。
  story 侧的改动仍经 `reopen` → `chapter` → `story` 登记，同样不派 verifier。

  **另一条路是 `/story update`**，它与上面这条的区别不在「代码拦不拦」，在**谁发起、材料变了多少**：
  用户主动要求按新的材料与意见更新已有产物，改完的那几个阶段**要按新的审查对象审一次**——
  材料确实换了一批，沿用上一版的 PASS 说的是另一份产物。怎么派、怎么回写见
  [update.md](update.md)「与闭环、修正入口的关系」，本页不复述第二遍。
  纯表达类 WARN（措辞、标题偏好）交评审回流或下一轮，记进 `spec/notes.md` 只是登记，不算处置完成。
  交付门上人给的评审意见走 `/story update`，不算这里的修改。已经做了的正确修改不回滚。
- **⑥ 回执不用你填**：它是 harness 的只读投影，`check-receipt` 自己先生成再校验；要写备注写 `<phase>/notes.md`。
  只有 `check-receipt` 报 subject 失配时才重跑 harness（那之后 verifier 再来一次）。
  **`check --deliver` 是交付门**：它把回执再跑一次，再核读者审查那一项的**实际结论**——判的不是 PASS 就不交付，
  本宿主没登记审查员时如实记一笔「未经读者语义审查即交付」。通过之后按 SKILL 停等表停一次。

### 失败出口：verifier 报了阻断问题

`story_flow.py reopen` 撤销成文登记（唯一的回退出口）→ 照 reopen 给出的下一步走：范围与材料没变时是
`complete --from AR/story-src/design-draft.md` 重新收口，材料变了走盘点与关卡 → `story-build skeleton`
（只补缺席的章，story.md 一个字节不动）→ 改最早出错的那一处（Spec、决策登记、写作设计或章草稿）
→ `chapter --from <草稿>` → `story_flow.py story` 重新登记 → harness → verifier 再审。
材料变了、审查对象换代，这是正常返修，不是重复审。

## 三、§9 技术契约怎么写

core spec 模板缺少交付流程要求 spec 承载的接口契约 / 存储 / 配置 / 埋点 / 依赖，所以在
**§8 验收标准之后追加一章**，模板见 [`templates/spec-sections.md`](../templates/spec-sections.md)：
9.1 端云接口 / 9.2 数据存储 / 9.3 配置项 / 9.4 埋点 / 9.5 依赖变更。

**形式一律表格，不按条目数切换**：每个小节要么是一张表（表头固定、每行一个编号实体、
单元格 ≤30 字），要么是一行「不涉及：<现状扫描依据>」。不写散文段、不写嵌套 bullet、
不建空表，小节不得删。**9.4 埋点例外**：它是埋点设计的唯一完整说明，按流程用 H4、短段、表与列表写，
不放图与围栏（业务需要的图放它讲的业务章，这里用文字说明或链接过去），内容按项目知识；仓内路径只进「代码现状」列。

写之前先读**两份**——「方法 + 数据」缺一不可：

| 读什么 | 给你什么 |
|---|---|
| [`reference/evidence-rules.md`](../reference/evidence-rules.md) | **怎么判**：各节取证规则、结论写法、取不到时怎么降级 |
| 激活清单里 `kind: facts` 的项目知识 | **这个工程有什么、叫什么、在哪**：照它写。它没登记的面才实扫仓；与仓不符时以仓为准，在产物里登记「项目知识矛盾」，**不改知识文件** |

**代码库现状**（仓内文件路径、检索零命中结论）是结论的一部分，作为表格的一列写进正文。
别拿平台常识替代它：某个 API 在别的工程常见，不等于本工程在用；项目知识里已核实为「没有」的能力，不要选进新设计。

**防重复**：写之前先查 spec 已有章节，同一件事只写一处。加密 / 脱敏 / 调用方校验归 §7.3；
性能阈值归 §7.1；谁先上线、阻塞谁，以及管理台排期、打点归档、翻译回稿，归《决策与评审记录》。
§9 不重复这些，core 模板的「宿主扩展治理项」章只写一句索引。埋点设计写在 9.4 一处，业务章不另写一套。

## 四、交付门之后

`AR/review.md` 是首版草稿，请开发按其中议题逐条审核并写下意见；AI 不代填表态、不动人工区。
表态完成度看的是**每条议题的填写位里有人的表态**：方案选择填了编号或具体方案；审核结果勾了确认，
或勾了不同意并写了原因与调整结论。提示文字与空框不算；还空着的议题在进 plan 时逐条列出。
