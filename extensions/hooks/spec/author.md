# spec 阶段 · 扩展要求（写之前读这一页）

> 读者：spec 阶段的作者。时机：动笔前读一遍；这一次的数据（知识原文、本施工单位承接的判断、缺口）看知识任务
> （story-knowledge Skill，`--action spec`）。

## 你在写什么

spec 是这个施工单位的需求规格：补清本单位的行为、边界与验收。知识应用的判断已经在设计里——CU 在蓝图的知识应用决定，
非 CU 的维护 Feature 在它契约的 `knowledge_applications`。知识任务第 3 块列出本单位承接的那几条；spec 不重判，
把它们要求的行为与验证责任写进验收。判断站不住（不适用的依据回查不到事实、豁免缺理由）时交设计负责方修订，不在 spec 里改判。

## 验收怎么承接适用判断

本单位承接的每条适用判断（`outcome: applied`；处置以「（评审动作）」开头的不产生代码要求，不建验收），
`acceptance.yaml` 里至少一条 criteria 写出它要求的可观察行为与验证责任，并带上桥：

```yaml
criteria:
  - id: AC-012
    scenario: 处理完成后
    expected: 临时记录已清除，重新打开页面看不到上一次的内容
    knowledge_rule: RET-01
    knowledge_decision_id: knowledge-ret-01
```

- `knowledge_rule` 写判断里的单元，`knowledge_decision_id` 写那条判断的 `decision_id`：同编号的规约可能来自不同文件，下游按两项一起认。
- 一条 criteria 一个编号；同一规约在不同场景（正常、边界、异常恢复）各写一条。
- 验证责任与知识声明的执行体一致：要实机证据的规约，验收写得出实机上怎么判。
- 编号出现不等于承接：条件与结果说不清、只把规约换句话说一遍，都算没承接。

## 写字的几条

- **数值要标来源与测量对象**：阈值、时长、次数写明来自上游约束、本工程设定还是平台基线，条件与量的是什么一并写清；材料没给的数值不冠以上游约束。
- **承诺与工程现状不符**（能力没有、页面不存在、字段缺失）时，正文写明差距并交需求或设计负责方，不用模拟或降级悄悄顶替。
- **未决的保持未决**：仍开着的选择，正文只写确定的共同要求，依赖它的行为与验收写成条件，不替人选一边。
- 「验收标准」里一个编号第一次作行首的那一行是它的定义，行内的功能编号与 `acceptance.yaml` 的 `prd_function` 一致。
- 写完通读一遍，找错字、乱码与断句。

## 跑哪条命令

`cd framework/harness && npx ts-node harness-runner.ts --phase spec --feature <Feature id>`。派审、采纳与报告回来之后的处置见
[phase-closure.md](../../skills/story/reference/phase-closure.md)「闭环」。本单位有设计之外的新增工程事实要写时，取证与结论写法见
[`evidence-rules.md`](../../skills/story/reference/evidence-rules.md)。

## 门禁会拦什么

- 本单位承接的适用判断没有验收条目承接；桥接指回的不是本单位承接的适用判断；写了 `knowledge_rule` 没写 `knowledge_decision_id`，或写成列表。
- 设计里的知识判断本身有缺口（漏判、原文已变、落点失效）：交设计负责方。
- 「验收标准」里的编号在 `acceptance.yaml` 里没有，或关联功能两处不一致；一个编号在 criteria 与 boundaries 里说两件事。
- verifier 报告里没有本阶段判据的结论。
