# 步骤 10 · 三类 Knowledge 消费与传递

## 目标

按 Facts、Constraints、Design patterns 的真实职责重建“看到 → 理解 → 应用 → 传递”，不再用名称回显、原文复述或逐行裁决
冒充知识应用。Demo 内容只作可适配样板。

## 生命周期

### Facts

从 Spec 起按 manifest 激活并作为目标仓事实使用；发现错误回 Knowledge 真源修正。事实不进入选型表，也不由 Plan 决定是否成立。

### Constraints

Spec 判断是否命中并形成当前需求的产品约束或明确不命中理由。Plan 为命中项确定设计落点、契约实体和验证方式，不能无理由取消。

### Design patterns

Spec 只登记候选和适用理由，不选型。Plan 根据方案上下文选择、拒绝或调整并冻结，允许全部不选，但每个候选有结论。

## 单一真源和投影

- manifest 只负责激活身份；机制从文件 frontmatter/正文派生类型和条目，不复制域清单；
- Spec 使用 `doc/features/<feature>/spec/knowledge-use.yaml` 作为结构化机器真源：记录 manifest digest、使用的 Facts、
  Constraints 的适用性/当前需求要求或不适用理由、Design patterns 的候选状态/理由；人读 Spec 摘要从它生成，不再手写第二版；
- Plan 的最终结果进入 `contracts.yaml` 的真实实体/义务；下游只读冻结结果，不回头重猜原始 Knowledge；
- Coding、Review、UT、Testing 对分派给自己的义务提供落实证据或明确不适用理由；
- Plan 若发现裁定会改变 Story 的产品行为、范围或验收，走 correction 返回 Spec，并同步 Story/Review。

`knowledge-use.yaml` 只由 Spec 写。Plan 对 pattern 候选的最终取舍和 Constraints 落点写入 `contracts.yaml`，不回写该文件；
发现 Spec 判断错误时走 correction。两份文件分别表达候选/需求判断与最终设计义务，不是同一结论的双写。

Spec 的“规约约束要求”和“设计模式候选登记”保留为人读章节，但改成由 `knowledge-use.yaml` 确定性生成的只读区：

- `hooks/spec/author.md` 与 `spec-sections.md` 删除让作者手填 §10/§11 表格的要求；作者只编辑 `knowledge-use.yaml`；
- 生成器从 YAML 同步渲染 §10/§11 及 Story 中需要的人读知识摘要；手改生成区由边界检查拒绝；
- `hooks/spec/post_check.mjs` 的旧三方 ID 核和 paraphrase 检查退场，替换为 manifest → YAML、YAML → 生成区、
  YAML → acceptance/Plan 输入、contracts → 下游分派的集合一致性；
- Spec 与 Story 的人读投影不反向成为判断真源。

## 验证分工

- 脚本：manifest 身份、类型、引用、候选集合、Plan 裁定集合、contracts 义务和下游分派集合一致；
- verifier：适用性理由是否结合需求、约束是否改变产品要求、模式取舍是否真实、落实证据是否回答义务；
- 行为测试：加入机制未知的中性 Knowledge，只改 manifest/知识正文即可贯穿全部环节。

## 允许范围

- `doc/extensions/knowledge/**` 的索引/样板契约说明，但不为测试改写业务答案；
- Spec/Plan 模板、六阶段 author/post_check/pre_verifier 与 shared knowledge/obligations helper；
- Knowledge、Plan pattern、contracts 单一真源和 verifier 协议测试；
- 相关失效形态的新发现者。

不改 Framework、Story 主叙事结构、金样、真实 Case 或产品代码。

## 正式路径退场项

- 逐行 Knowledge adjudication 与 verifier 行数配额；
- 原文相似度/paraphrase 作为理解或应用判断；
- Spec 与登记件、Plan Markdown 与 contracts 各写一份最终结论；
- Spec §10/§11 的手写作者义务与旧 `idSetProblems` 三方集合核；
- 下游重新扫描全部原始 Knowledge；
- 按域逐条写“不涉及”替代先判域/类型。

## 完成条件

- 三类 Knowledge 在提示、数据和下游行为中可区分；
- Spec 只为 patterns 提候选，Plan 才选型；Constraints 的命中与 Plan 落点职责不混用；
- 新增中性 Facts/Constraint/Pattern 无需修改通用脚本即可分别到达正确消费者；
- 删除、复述、错误裁定和静默下游跳过的反例均被正确责任层发现；
- 同一结论无双写，派生失败响亮报错；
- 修改 YAML 中一条 Constraint 为不命中后，重新生成会同步改变 Spec §10 和 Story 知识摘要；直接手改 §10 被判为编辑生成区；
- 全树搜索不存在继续要求作者手填 §10/§11 的指令，旧三方 ID 核无消费者；
- P6 与 Knowledge 相关失效形态已有新发现者；旧回归发现器保留至步骤 11。

## 预算（对照 `test/story/regression/mechanism-budget.yaml`）

| 类别 | 预计 | 归属 |
|---|---|---|
| hooks_mjs | **净减 ≥ 400**：`paraphrase.mjs` 整体退场，`pre_verifier.mjs` 逐行必答表与相似度排序退场，`knowledge.mjs` 的复述检查退场；新增 manifest → YAML → 生成区 → contracts → 下游分派的集合一致性检查 | 新增归 D2 §4「上下游 ID、义务集合、verifier subject 或报告身份不一致」「某项检查因前置缺失没有运行却表现成通过」 |
| prompts_md | 持平或小增：Spec/Plan 模板的手写 §10/§11 义务删除，`knowledge-use.yaml` 的作者说明新增 | — |
| data | 小增：`knowledge-use.yaml` 的合同形态 | — |
| semantic_proxy | pre_verifier 10、paraphrase 8、knowledge 1、post_check 6 归零；verifier-report 6 随引文核实退场归零 | — |

完成后把 `hooks_mjs`、`semantic_proxy` 的 ceiling 压到现值。预计超 ceiling 的情形：无。