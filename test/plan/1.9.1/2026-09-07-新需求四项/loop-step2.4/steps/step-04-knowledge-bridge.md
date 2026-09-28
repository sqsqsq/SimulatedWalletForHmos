# `step-04-knowledge-bridge`：知识协议残留与验证桥接

## 目标结果

02.4-04 分册落地：R19 `knowledgeCriteria(acceptance, sections)` 返回 `{byRule, problems}`、`byRule` 为 `Map<rule, 条目[]>` 不覆盖（同时关闭 D01），Spec 调用者只传 `['criteria']`，UT/testing 消费数组全部条目；验收编号两端对齐（作者样例 `AC-K1` → `AC-1`，UT/testing 正则保持 `AC/BD-<数字>` 与 `G<数字>`，加从任务包样例到检查的正例）；R16 退出 `includes(数值+单位)` 判出处真假与「伪造出处」文案，保留来源类型结构检查；R06 / R17 / R22 / R23 四处指令改正；D02 空模式集合法、D03 候选/选择按 (unit, pattern) 保留多条。**不新增**逐数值台账、实体→验收业务字段、平行模式映射账本；不重写规约、模式算法或目标业务事实。

## 前置与依赖

- 输入产物：step-03 之后的 HEAD。
- 真实依赖：无。
- 执行顺序：step-03 之后。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根；行号按 HEAD `5203ca30`，实施前按符号重核。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| 共享入口（同 step-02） | 共享已加载 | 同上 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.4-04-知识协议残留与验证桥接.md` 全文 | 本步新增 | 本步全部合同；§3.1 共享读取的签名与策略、§3.2 编号对齐、§3.3 D02/D03、§3.4 数值出处、§3.5 四处指令 |
| `doc/extensions/hooks/shared/contracts.mjs` `readAcceptance` :155、`knowledgeCriteria` :175（含 :167–:174 那段「合并会放宽」注释，须随 R19 改） | 本步新增 | 共享提取的唯一入口 |
| `doc/extensions/hooks/spec/post_check.mjs` `NUMERIC_RE` :111、`UNIT_ALIASES` :114、`scanNumericSources` :124、`acceptanceCoverage` :263（含 :269「符合性附录由 writer 直接写」，归 step-05 R18 但同文件可顺手改） | 本步新增 | R16 与 R19 的 Spec 侧 |
| `doc/extensions/hooks/ut/post_check.mjs` `coveredAcceptanceIds` :25（正则 :32/:52）、义务循环 :70–:95（含 :92「改成 device」）；`doc/extensions/hooks/testing/post_check.mjs` :51 及同形循环 | 本步新增 | R19 下游消费者改成遍历数组；R06 修法说明；正则保持 |
| `doc/extensions/hooks/spec/author.mjs` :128（`AC-K1` 样例） | 本步新增 | 改 `AC-1` 并注明按已有编号顺延 |
| `doc/extensions/hooks/shared/knowledge-use.mjs` `coverageProblems` :173、`renderSkeleton` :544；`doc/extensions/hooks/plan/post_check.mjs` `specPatternHits` :128、`planPatternChoices` :152、消费处 :291–:292 | 本步新增 | D02 / D03 |
| `doc/extensions/hooks/ut/author.md` :43、`hooks/plan/author.md` :6、`knowledge/facts/README.md` :11、`knowledge/design-patterns/README.md` :59、`decision-tree.md` :42、`page-interaction.md` :40、`rules/spec-rules.overlay.yaml` :58–:59 | 本步新增 | R06 / R23 / R17 / R22 / R16 的文案落点 |
| `doc/extensions/hooks/coding/author.md` :15/:25 | 条件：R23 时 | 与 coding 侧「读已选模式实现篇」统一口径 |
| `test/story/tests/test_knowledge_use.py`、`test_plan_pattern_crosscheck.py`、`test_neutral_knowledge.py`、`test_empty_knowledge_repo.py`，以及 ut/testing/spec 钩子的现有用例 | 本步新增 | 迁移与新增 |

## 修改边界

- 负责：`contracts.mjs`、spec/ut/testing/plan 四个 post_check、`knowledge-use.mjs`、`author.mjs` 样例、七处文案、相关测试。
- 排除：Framework 验收协议；目标仓知识业务正文；内网仓适配；附录（step-03）；编排（step-02）。
- 公共规则：四道门见 `TEST.md` §7。

## 关键决定

- 已确定（分册 §3.1）：解析共享、策略分离；缺 `knowledge_rule` 的普通条目不算错误；该字段存在但非非空字符串给结构错误；同一验收 ID 重复告警可去重；不得挑最后一条、改 verify 或删验收消除错误。
- 已确定（分册 §3.2）：正式编号形态 `AC-<数字>` / `BD-<数字>` 及 `G<数字>`，不扩大到任意字母。
- 已确定（分册 §3.4）：结构检查只确认标注/定位，不证明出处真实；不降低已有规约阈值。
- 设计任务：无。

## 验收

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 同 rule 两条 AC（criteria）；同 rule 一条在 criteria 一条在 boundaries | UT/testing 两条都核、缺一条各报；Spec 只认 criteria 那条 | 新增用例（D01 的纯函数复现转为回归） | 本步自动检查 |
| 坏 YAML / `knowledge_rule` 写成列表或留空 / 普通业务 AC 无该字段 | 前两者结构错误一致报出；后者不报 | 新增用例 | 本步自动检查 |
| 作者按任务包样例写的 AC ID 出现在 UT/testing 证据里 | `coveredAcceptanceIds` 找得到；旧 `AC-3` / `AC-G2` 形态仍识别 | 从真实任务包样例取 ID 的正例 + 既有回归 | 本步自动检查 |
| Spec 写「30 min（上游约束：SR §3）」而上游写「30 分钟」 / 上游确无该数 | 不再报「伪造出处」；缺来源类型标注仍报 | 新增用例 | 本步自动检查 |
| 无在册模式 + `patterns: []` / 有模式未判断 / 同单元两候选 / 采用一拒绝一 / 两模式组合 | 分别：合法、提示、两条都保留、各有结论、组合可表达 | 新增用例（D02/D03） | 本步自动检查 |
| 七处文案 | UT 环境缺不自动改 device；plan 作者不再被禁读实现篇；事实库不禁止有依据新建；三处 `project_knowledge` 落点改为 files/interfaces 与 files.pattern/role；overlay 不再说「找不到即 FAIL（伪造出处）」 | 人读 + `check_failure_modes` | 本步自动检查 |
| 四道门与规模 | 全绿；`measure()` 前后值写进 closeout；D 项修复的增量单列 | `TEST.md` §7 | 本步自动检查 |

## 提交边界

- 纳入：上述文件与测试。
- 排除：本目录文件；step-05 的 R18 残料（同文件顺手改的注释可纳入，closeout 注明）。
- 完成条件：验收全过；D01–D03 在 closeout 单列；`approved_for_commit` 后提交。

## 停止条件

- 分派关系不能确定该由哪条 AC 验时，报「回 Plan 明确」，不由解析器猜。
- 发现必须改 Framework 验收 schema 才能表达多 AC 时停下交 Human。
