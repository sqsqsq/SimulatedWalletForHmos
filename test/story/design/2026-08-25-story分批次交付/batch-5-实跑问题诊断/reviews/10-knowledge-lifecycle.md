# 步骤 10 · 三类 Knowledge 消费与传递 · 独立评审（Claude）

## 小段 1「knowledge-use.yaml 成为唯一真源」（`fcef8a01`，2026-09-04）

### 1. 结论

- 状态：**通过**，附两条要在小段 2/3 收的桥与三条 advisory。
- 复审者复跑：story 527 全绿（51 s，505 + 22 新增）；73 条 FAIL 0、委派 12；预算门 5 条通过；`node --check` 通过；`framework/` 零差异。
  机制层：hooks_mjs 3984（ceiling 4000，**只剩 16 行余量**）。

### 2. 行为重建

- `hooks/shared/knowledge-use.mjs`（476 行）：读 `spec/knowledge-use.yaml`（schema 1；`manifest_digest`、`facts`、`constraint_domains`、`constraints`、`patterns`），
  `coverageProblems` 只判集合与字段：digest 与激活清单文件内容对得上、facts id 在册、每条激活约束有去处（逐条或整域不适用）、域不适用与逐条登记不并存、
  命中必有 `requirement`、评审动作条目不得判命中、候选在册、spec 里不得写 `chosen`。`renderZones` 生成 §10/§11 两个带标记的只读区；
  `zoneProblems` 判生成区缺失、与 YAML 不一致、章内生成区之外还有表。`render` 子命令幂等写入，章标题不存在时拒绝代写。
- `hooks/spec/post_check.mjs`：`knowledgeExitProblems` 不再解析人写的表；`isPureCopy` / `paraphraseSources` 在 spec 侧失去调用点；
  `idSetProblems` 只剩「命中集 ↔ acceptance」一对。
- 作者面：`hooks/spec/author.md`（60 行）与 `spec-sections.md` 改成「只编辑 YAML，跑 render」，§10/§11 模板表删除，字段说明在两节注释里。
- 判据全是确定性不变量：没有相似度、没有复述、没有行数配额。新模块无业务域词；`ZONES` 里的两个章名是模板章名，不是业务名。
- 22 条测试逐类对应：完备性 7、候选 4、生成区 7、digest 4。台账当场抓到 M05/M16/A03/W01 四条并修，W01 夹具补了 YAML 与投影。

### 3. 桥（登记，后续小段收）

- **B1** `hooks/plan/post_check.mjs` 仍解析 spec §10/§11 的 markdown 表（L61–150 `tableRows`）取命中集与候选集。生成区的表头与旧手写表相同，所以现在能跑，
  但它读的是投影不是真源——小段 3 改读 YAML 后这段解析器与 `isPureCopy` 调用一起删。
- **B2** hooks_mjs 距 ceiling 16 行。小段 3 若先加 plan 侧代码再退旧路径，会红。顺序必须是先退（paraphrase 132、pre_verifier 逐行必答表、verifier-report 引文核实）再建，
  或同一提交净减；**不申请抬 ceiling**。

### 4. advisory

- **A1** `coverageProblems` 里「依据太薄」用的是 `reason.length < 6 || /^不涉及。?$/`。六个字是配额不是不变量；「依据可不可回查」是语义，归 verifier。
  建议只留「空」与「恰为不涉及」两种确定性形态。
- **A2** YAML 的 `constraints[].contract`（渲染成 §10「落点契约名」列）与 steps/10「落点由 plan 定、写进 contracts.yaml」之间要说清是哪一层的落点：
  若它是 §9 技术契约名的引用，小段 3 的 plan 集合一致性要把「spec 说的 §9 名 ↔ contracts.yaml 实体」核起来；若不核，它就是同一结论的第二处写法，应删。
- **A3** overlay 的 `knowledge_candidates_registered` 仍让 verifier「读 spec 的候选登记章」并附 12 字引文；投影与 YAML 按构造一致，读哪个都行，
  但「引文 ≥12 字」这类形态要求属小段 2 退场的引文核实路径，改判据措辞时一并去掉。

### 5. 分段安排的评审意见（用户问：四段是否必要、剩余能否一次做完）

- 小段 1 单独成段是对的：它定了 YAML 形态，后面三段都以它为输入。
- 小段 2 与小段 3 **应合并**：两者动的是同一批文件（`plan/post_check.mjs`、`pre_verifier.mjs`、overlay），分开做会留下「plan 读投影」这座桥和 16 行的预算悬崖；
  合起来就是「plan 侧换真源 + 旧路径退场」一件事，净减，可一次回退。
- 小段 4 保持独立提交但**与 2+3 同批交付、一次评审**：中性 Knowledge 行为测试是整步的验收，要在 2+3 之后跑；story 知识摘要生成与 P6 发现者、预算压现值是收口动作，
  单独一个提交便于回退，但不必单独等一轮评审。
- 也就是：剩余工作**一次做完、两个提交、一次评审**。进入条件写在下面。

### 6. 剩余工作的进入条件（给执行会话）

1. 先退后建或同提交净减：`paraphrase.mjs` 整份、`pre_verifier.mjs` 逐行必答表与相似度排序、`verifier-report.mjs` 的 `evidenceVerified` 与 `min_quote_chars`、
   `plan/post_check.mjs` 的 `isPureCopy`、`knowledge.mjs` 的 `paraphraseSources`；结果判据是 hooks 与 skills 的语义代理标识 **0**（现 24）。
2. plan 侧真源：命中集、候选集从 `knowledge-use.yaml` 读；contracts.yaml 的 must 与 pattern 裁定与它做集合一致；A2 的 `contract` 字段先定归属。
3. overlay 里的知识判据改成按 YAML + 材料判语义（要求是不是本需求的设计、反证与材料对不对得上），不带引文长度、不出逐行裁决表；不新增任何字符串近似。
4. 中性 Knowledge 行为测试：夹具 manifest 加一条机制不认识的 fact / constraint / pattern，不改任何通用脚本，spec YAML 完备性 → plan 集合一致 → 下游分派逐段有证据。
5. story 知识摘要从 YAML 生成；P6 与 knowledge 相关形态登记新发现者（确定性的带夹具，语义的登 `observed`）。
6. 收口：hooks_mjs 与 semantic_proxy ceiling 压到现值；步骤 9 返修漏网四处一并清零。
7. 完成条件对照 `steps/10` 末尾逐条给证据；两个提交各自可回退；自述附 grep 命令与命中数。
