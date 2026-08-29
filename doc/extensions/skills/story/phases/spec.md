# `/story` 链 · spec 阶段作业包

> 从 `/story` 链进入 spec 阶段时读这一页。扩展对 spec 的通用要求见
> [`hooks/spec/author.md`](../../../hooks/spec/author.md)（那一页对所有 spec 都生效）；
> 本页只补 `/story` 场景独有的：材料从哪来、要出几份产物、§9 怎么取证。

## 一、上游输入必读

正文生成前必须读下面三份（存在时），并在 `spec/context-exploration.md` 的 `key_inputs_read` 里记录：

| 文件 | 是什么 |
|---|---|
| `doc/features/<feature>/AR/design.md` | 开发需求文档，本阶段主输入。「相关文档链接」表与「上游索引」章是回查 SR/RR 的定位索引 |
| `doc/features/<feature>/RR/prd.md` | 产品 PRD——业务场景全景与验收意图 |
| `doc/features/<feature>/SR/design.md` | SE 系统级设计——跨部件交互、云侧接口、系统级存储，是 §9 技术契约的取证源 |

**「本 AR 范围与拆分说明」是 Scope 与功能清单的边界依据**：该节含拆分表时，表里归**兄弟 AR
或「待立项」**的那几份**不属于本次**——它们的功能不进本 AR 的功能清单，也不进验收标准。
这些内容涉及的模块若要登记 `out_of_scope_modules`，`rationale` 写「归属 <兄弟 AR 编号>」而不是
「本需求不做」：前者有人接、后者没人接，对评审者是两个不同的信息。
三形态见 [`rules/ar_design_init.md`](../rules/ar_design_init.md) §3——**「无拆分」不等于「本 AR 承载全部」**，
同 SR 有兄弟 AR 时后者是假的。

## 二、本阶段产出三份文档

spec 阶段是**一次 pass 产出三份**，作者与读者各不相同，事实同源，不得只交 `spec.md` 就宣告闭环：

| 产物 | 作者 | 持有什么 | 读者 |
|---|---|---|---|
| `spec/spec.md` | AI | **代码要求** | AI 编码 / 出用例 / 门禁 |
| `AR/review.md` | AI 起草 + **人确认** | 自然语言问题、当前建议、可填写的审核结果 | 评审者 |
| `AR/story.md` | AI（**writer 子 agent**，见下方顺序） | 完整需求叙事 + 判断 + 合规回显 | 评审者（归档件·叙事主件） |

- `AR/review.md` **由 `AR/story-src/decisions.json` 渲染，不手写**：AI 只负责把开放点收齐并登记
  （问题、当前建议、依据、影响、来源、责任人），表态位由脚本生成、由评审人勾选。
  末尾状态行保持「**状态**：草稿（待开发确认）」——**不得代填「已确认」**。
  状态标「已确认」而问题没有审核结果即 BLOCKER。

**story 不是 spec 的排版件**：spec 的可标识事实、PRD 的业务语境、SE 的全局方案，以及无编号的
数据与交付事实，都必须在 story 有完整落点。story 可以整合、改序、改写，但不可以只保留编号、
删掉上下文，或把全局方案缩成一段摘要；它还要补足判断、权衡、风险与合规回显。

### 阶段内顺序（story 在这里成文，不另起一步）

`spec.md` 与 `decisions.json` **定稿之后**、跑 harness **之前**，按下面五步走完：

```bash
node doc/extensions/skills/story/scripts/story-build.mjs init --feature <feature>   # ① 枚举来源单元
#                                                    ② Task 起 writer  → phases/story-write.md
#                                                    ③ Task 起 verifier → phases/story-verify.md
python doc/extensions/skills/story/scripts/story_flow.py story --feature <feature>  # ④ 登记（自带 check）
#                                                    ⑤ 跑 spec harness
```

- **② 与 ③ 是两个独立子 agent，主 agent 不读材料、不写 story**。spec 走到这里时上下文已经
  几十万 token，story 是最后被挤出来的那一份——实测因此丢过表格非首列的事实与两张图。
  子 agent 拿到的是新鲜上下文，这才是它们独立的理由；与 story 写在哪个阶段无关。
- **③ 只在 `audit.json` 出现 `by: author` 记录时才需要**：机器定不了落点的单元只有模型能判。
- **④ 自带门禁**：先重跑 `story-build check`，通过才登记 `story_written`。**只登记一次**——
  story 定稿于评审时点，评审回流只改 `spec.md`，不动 story（见 SKILL.md「检视」节）。
- **⑤ 之前必须走完 ①–④**：spec 门禁核的是「三份产物齐备」，`story_written` 未登记即 BLOCKER。

## 三、§9 技术契约怎么写

core spec 模板缺少交付流程要求 spec 承载的接口契约 / 存储 / 配置 / 埋点 / 依赖，所以在
**§8 验收标准之后追加一章**，模板见 [`templates/spec-sections.md`](../templates/spec-sections.md)：
9.1 端云接口 / 9.2 数据存储 / 9.3 配置项 / 9.4 埋点 / 9.5 依赖变更。

**形式一律表格，不按条目数切换**：每个小节要么是一张表（表头固定、每行一个编号实体、
单元格 ≤30 字），要么是一行「不涉及：<现状扫描依据>」。不写散文段、不写嵌套 bullet、
不建空表，小节不得删。

写之前先读**两份**——「方法 + 数据」缺一不可：

| 读什么 | 给你什么 |
|---|---|
| [`reference/evidence-rules.md`](../reference/evidence-rules.md) | **怎么判**：各节取证规则、结论写法、取不到时怎么降级 |
| 激活清单里 `kind: facts` 的项目知识 | **这个工程有什么、叫什么、在哪**：照它写。它没登记的面才实扫仓；与仓不符时以仓为准，在产物里登记「项目知识矛盾」，**不改知识文件** |

**代码库现状**（仓内文件路径、检索零命中结论）是结论的一部分，作为表格的一列写进正文——
它是「事实 = 变更意图 × 代码库现状」的另一半。别拿平台常识替代它：某个 API 在别的工程常见，
不等于本工程在用；项目知识里已核实为「没有」的能力，不要选进新设计。

**防重复**：写之前先查 spec 已有章节，同一件事只写一处。加密 / 脱敏 / 调用方校验归 §7.3；
性能阈值归 §7.1；谁先上线、阻塞谁，以及管理台排期、打点归档、翻译回稿，归《决策与评审记录》。
§9 不重复这些，core 模板的「宿主扩展治理项」章只写一句索引。

## 四、闭环后的下一步

spec 闭环时三份产物都已在手，下一步**必须以「人工评审 → 归档」为首选链路**：`AR/review.md`
是首版草稿，请开发按其中议题逐条审核并填写表态（状态行保持「草稿（待开发确认）」直到人工完成）
→ `/story archive` 送审 `AR/story.md` 与 `AR/review.md`。
AI 不代填表态、不改状态行。「进入 plan」只能作为其后的选项列出，并注明「建议先完成评审与归档」。
