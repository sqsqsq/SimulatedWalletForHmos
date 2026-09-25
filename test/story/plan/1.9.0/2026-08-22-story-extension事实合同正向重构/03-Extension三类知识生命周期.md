# Extension 三类知识生命周期

## 激活分类

Manifest 将 `provides.knowledge` 明确分为 `project`、`constraints`、`patterns`。README 与目录存在本身不激活知识。

项目知识描述当前工程事实；约束描述适用条件和必须形成的要求；设计模式描述结构性候选及采用边界。三类知识不得继续靠路径或模型记忆区分。

## Spec 交接

Spec 生成 `spec/knowledge-application.yaml`，逐个处置所有激活知识项：

- 项目事实记录 evidence、impact 和 spec landing；
- 约束记录 applies/not_applies、理由、形成的要求和可选 `story_conclusion`；
- 模式记录 candidate/not_applicable、业务单元和触发信号，不在 Spec 决定实现库。

## Plan 冻结

Plan 生成 `plan/knowledge-freeze.yaml`，记录项目事实的设计落点、适用约束的契约/用例/验证落点、每个模式候选的 adopted/rejected 决定和下游义务。

工程当前不存在的能力不得当成已有能力；确需引入时标记为新能力并说明影响。没有现成 SDK 不等于模式不适用。模式采用决定不得推迟到 Coding。

Story 不直接读取原始 Knowledge，只消费 Spec 已形成且具有业务评审价值的 `story_conclusion`，并将其作为普通事实进入 `story-facts.yaml`。

