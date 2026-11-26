# 知识适配的独立审查

> 读者：执行 `/story adapt` 的适配模型（发起与收回），以及被派来审查的独立执行体。时机：知识写完、自查过、交回与跑 `--mark-adapted` 之前；知识改过后按新摘要重审受影响的文件。

## 独立知识读者

拿本次正常需求，先从目标仓给出你的业务判断和源位置，然后用作者的知识再作一次判断。点出会选错的承担者、误用的能力、遗漏的条件和没有采用证据的模式。对错处给出所在文件、错误动作、可核依据和要修改的正文；对作者根本没写的关键项也给出影响。逐份复核粒度、用途、重复和编码边界，在现有报告里分别填结论与 blocking。已定范围正确、关键判断有据且读者能用时才接收。

## 为什么要独立

写知识的上下文已装着作者的预设，自查无法发现盲区。审查必须由不共享作者上下文的独立只读执行体完成（原生独立只读子代理，或独立会话/维护者并在交回写明未审）；同一上下文自查不能代签，阶段 verifier 协议也不替代本次审查。

## 发起：把这些交给审查者

| 交什么 | 从哪取 |
|---|---|
| 目标根路径、激活清单与当前摘要 | `adapt-scan --status` 的 `knowledge.digest` |
| 已定适配范围、按主题三态盘点与本次演进主题 | `knowledge-adaptation.md` 盘点、`--status` 的 `items.知识` |
| 激活知识文件与对应源码/规范位置 | 根 `manifest.yaml > provides.knowledge` 与取证记录 |
| 本次正常检查需求（及条件变化的邻近需求） | 作者走读所用需求 |
| 质量标准与同用途候选 | `knowledge-adaptation.md` 四格标准、`knowledge-topics.md`、`protocol.md`、`--status` 的 `knowledge.sameUse` |

## 审查步骤与判退边界

1. **先独立作决定**：不看作者走查结论，直接打开目标仓源码与规范回答——谁承担关键结果、哪项能力可复用、哪个条件会改变允许的处理、有哪些真实证据或缺口。
2. **再对照知识逐份核查**：用作者知识重作一次判断，查错指的承担者/公共依赖、虚构权限、无采用证据的模式、遗漏的验收/处置条件，以及整套稿件漏写的关键项；再逐份核四项维度：
   - `granularity`（条目粒度与归类）：是否先归并再归纳、是否遵守首批每份最多三项且未强压独立义务；
   - `fact_use`（项目事实的用途）：是否讲清有什么、在哪、怎么用与边界，能否指导正确决策；
   - `duplication`（跨文件重复）：同一事实/约束是否多处重写（`sameUse` 仅作线索，异名同义同样核）；
   - `coding_boundary`（编码规范边界）：是否误把语言写法、命名或 lint 规范写成项目知识。
3. **严格区分 `FAIL` / `blocking` 与 `WARN`**：
   - **必须判 `FAIL`（对应维度）并记入 `blocking`**：错误公共依赖或模块归属、虚构权限或改变业务对端语义、无采用证据的模式断言、漏掉会改变验收或处置的条件（整套漏项记 `blocking`）。实质错误即使表述清晰也不得判 `WARN` 放行。
   - **仅 `WARN`**：措辞润色或非关键扩充建议。
   - 仅在已定范围正确、关键判断有据、无 `FAIL`、且 `blocking` 与 `unreviewed` 均为空时接收。

## 收回

审查结论原样写进目标扩展目录 `<ext>/.adapt/knowledge-review.md`，其中恰好一个 `knowledge_review:` YAML 块（作者只传输，不改写结论）：

```yaml
knowledge_review:
  digest: <审查时 --status 给的 knowledge.digest>
  executor: <宿主返回的独立执行或会话引用>
  files:                       # 激活清单里每份一项
    - path: knowledge/<类>/<文件>.md
      granularity: {verdict: PASS, evidence: <核过什么、证据位置>}
      fact_use: {verdict: PASS, evidence: …}
      duplication: {verdict: PASS, evidence: …}
      coding_boundary: {verdict: PASS, evidence: …}
  blocking: []                 # 实质错漏或整套缺项，没有写空列表
  unreviewed: []               # 未核到的知识或维度及原因
```

`--status` 的 `knowledge.review` 只读核缺失、摘要过期、漏审、FAIL 与 `blocking`/`unreviewed`；知识改过后按新摘要重审受影响文件，旧结论自动失效。无独立执行能力时机制照常装好，交回写明知识适配未完成，不写 `adapted_for`。
