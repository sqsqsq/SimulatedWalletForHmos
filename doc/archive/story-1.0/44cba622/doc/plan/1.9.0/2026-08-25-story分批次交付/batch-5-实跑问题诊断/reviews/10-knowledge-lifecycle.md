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

## 小段 2+3「旧路径退场 + plan 侧换真源」（`d158c5c6`）与小段 4「中性 Knowledge 与台账收口」（`57524cc3`）· 独立评审（Claude，2026-09-04）

### 1. 结论

- 机制面：**通过**。旧语义路径整条退场，plan 侧读真源，中性知识走通 spec → plan，story 侧判定表与 YAML 一致性判据是集合比对。
- 但有两件事**不是评审能签的**，要用户裁定（§3 B1、B2）；另有一处返修（§3 B3、B4）。步骤 10 在用户签字与返修提交之后收口。
- 复审者复跑：story 532 全绿（55 s）；失效形态 73 条 = 活跃 70（FAIL 0、委派 15、PASS 55）+ retired 3；预算门 5 条通过；改动的 8 个 `.mjs` 语法通过；
  hooks 无无调用函数；`framework/` 零差异。机制层现值：scripts_mjs 3014、scripts_py 1810、hooks_mjs 3451、prompts_md 2712、data 731，总 11718。
  语义代理标识：可执行代码 0；注释里剩 2 处（`pre_verifier.mjs`、`verifier-report.mjs`，都是在交代为什么退场）。

### 2. 行为重建

- 退场：`paraphrase.mjs`（132 行）与 `verdict-set.mjs`（121 行）整份删除；`verifier-report.mjs` 删 `evidenceVerified`、`minQuoteChars`、`adjudicationProblems`，
  只剩 story 审查报告的形态核对；`pre_verifier.mjs` 从「注入必答表 + 相似度排序」改为「指路」：spec 指 `spec/knowledge-use.yaml`，plan 起指 `plan/contracts.yaml`，
  给判据三问，明说不逐条对账、不出裁决表、不找引文；两处 post_check 的 `isPureCopy` 调用删除；`knowledge.mjs` 的 `paraphraseSources` 删除；
  合同 `verdicts.min_quote_chars` 及 note 删除；两个阶段的 `knowledge_adjudication_persisted` 判据项删除。
- plan 侧真源：`specHitIds` / `specPatternHits` 读 YAML（读不到记「这条没执行」，不静默过）；集合一致双向差集不变；`must.text` 只核有无。
- overlay：spec 两条与 plan 两条改成对着真源与材料判语义，不再要求裁决表与 12 字引文；`knowledge_facts_reuse` 同改。
- A1 已收：`isEmptyReason` 只认空与「不涉及」；A2 已收：`contract` 字段定为 spec 内部落点声明，引 §9 已登记的名字，§9 不存在（非 `/story` 需求）时不判。
- 小段 4：`story-build check ⑦` 新增「判定表结论 ↔ YAML applicable」一致性（35 行，读不到 YAML 不判）；`idSetProblems` 改名 `acceptanceCoverage`；
  中性知识测试 9 条：NEU 域两条约束、一份事实、一个模式，通用脚本零改动，验派生、完备性点名、投影、候选在册、§9 名核对、plan 命中 ↔ 实体双向；
  五个失去消费者的 checker 删除，B02/M11/P11 夹具目录删除。
- 测试处置按三类可核：`test_adjudication_parity` 整份退（5）、报告协议里逐行裁决三条删、读取层四条改搭建、`test_plan_pattern_crosscheck` 六条改搭建（存档不改）。

### 3. 要用户裁定的与要返修的

**B1 · 台账签名把评审当成了用户。** 六条登记写着 `approved_by: 用户（2026-09-04 步骤 10 评审进入条件 1/5）`：
B02、M11、P11 标 `retired`；P02、P03、P04 改 `responsibility: verifier`。「进入条件」是我在评审里写给执行会话的，不是用户签字。
用户实际签过的是 D10 修订那十条（B02、C01、R01、S01、S02、S05、S08、S09、S20、R02 部分），且 B02 在那里是「责任迁 verifier」，不是 retired；
M11、P11、P02–P04 不在那十条里。steps/11 写明「纯旧实现条目得到用户批准后才 retired」。
评审意见：六条的理由都成立——B02/M11/P11 的产生机制（必答清单 + 逐行裁决 + 引文核实）已经不存在，形态失去定义；P02–P04 形态仍在，发现者换成 overlay 语义判据。
**但签名要换成用户自己的裁定**：用户在本轮回复里批准或否决，执行会话把 `approved_by` 改成「用户（2026-09-04 裁定：…）」。否决的话 B02 按 D10 迁 `observed`，M11/P11 同样迁 `observed`（observed_by 写「报告结果块在、两类结论齐」与真实 Story 观察）。

**B2 · 预算门的两处改动同样只有执行会话的手笔。** ① `test_mechanism_budget.py` 的语义代理计数改为**只数可执行行**（跳过 `//`、`*`、`/*`、`#` 开头的行），
`semantic_proxy.ceiling` 由此压到 0；② `scripts_mjs.interim_ceiling` 2979 → 3014（story 侧一致性判据 +35 行）。两处 `approved_by` 仍写 WYK。
AGENTS §7.5：改预算任何数字要具名与理由——数字与口径都改了，理由写了，签名不是。评审意见：两处都该批——注释里交代「为什么退场」正是该留的文字，
数进去只会逼人删注释；+35 行对应完成条件「同一结论无双写」，且 target 2000 未动。**请用户签字**，执行会话把 reason 里补一句「用户 2026-09-04 批准」。

**B3 · 交付面文字第三次没清干净。** 上一轮点名的四处仍在：`skills/story/SKILL.md:24`「story：分配落点 → 逐章渲染 → 裁决 → 登记」（作者第一眼看到的入口图）、
`hooks/spec/post_check.mjs:6` 注释、`story-build.mjs:566` `glossaryMainName` 无调用者、合同 `story-chapters.json:157` `prose_budget` 无消费者。
本段又新增同类：`hooks/spec/post_check.mjs:200–206` 函数注释仍列「三方 ID 集合一致」「要求列不是规约原文的复制」「归 verifier 全集裁决」，L316「按注入的必答清单逐行裁决」；
`hooks/plan/author.md:57–58` 告诉作者门禁会拦「`must.text` …是原文复制」与「verifier 报告里没有逐行裁决表」——两条门禁本段都删了，作者面在说门禁没有的事。
实施自述写「grep 零命中」，用的词表还是那八个词；三轮下来的规律是**词表以外的残留靠人读**，不靠 grep。返修用 `分配|裁决|逐行|必答|复制|三方` 宽词过一遍再人工筛。

**B4 · 中性知识没有走到下游。** 测试文档串写「下游：义务经 contracts 分派」，但 9 条测试止于 plan 的集合一致；steps/10 完成条件是「分别到达正确消费者」，
约束的消费者不止 plan——coding/review/ut/testing 的 post_check 经 `obligations.mjs` 取 `must` 分派。补一条：contracts.yaml 里挂了 `NEU-01` 的 must，
下游某一阶段的钩子把它列进本阶段义务（不改通用脚本）。一条就够，验的是分派不按编号前缀写死。

### 4. advisory

- **A1** coding/review/ut/testing 与 spec 另外三条 overlay 判据仍写「每条裁决附引文，连续 12 字以上」。它们不属知识判据，机械核实已删，现在只是 verifier 的举证习惯，
  与同一文件里「不为每条找一段够长的引文」并存显得口径不一。步骤 11 前统一：留「写清依据在产物的哪一处」，去掉字数。
- **A2** P02/P03/P04 的夹具目录若仍在（本段只删了 B02/M11/P11 的），与 12 条 observed 的夹具一起归步骤 11 清理。
- **A3** 35 分钟慢跑归因锁屏断网（用户说明），我在 reviews/09 记的 A2 一并关闭，不进步骤 11 观察项。

### 5. 范围与预算

- 允许范围内；保护区零差异。hooks_mjs 净减 −533、scripts_mjs +35、data −5；ceiling 压到现值；语义代理 0。均在 AGENTS §7.5 规则内，只差 B2 的签名。

### 6. 后续

- 用户对 B1、B2 表态 → 执行会话一个返修提交：改签名措辞（B1、B2）、清 B3、补 B4。评审通过后步骤 10 收口，步骤 11 进入条件齐备。

### 7. 用户裁定（2026-09-04）

- **B1 同意**：B02、M11、P11 标 `retired`；P02、P03、P04 改 `responsibility: verifier`。六条的 `approved_by` 改写为「用户（2026-09-04 裁定，见 reviews/10 §7）」，reason 不动。
- **B2 OK**：语义代理计数只数可执行行、`semantic_proxy.ceiling` 0、`scripts_mjs.interim_ceiling` 3014 三处生效。两条 reason 末尾补「用户 2026-09-04 批准」。
- 返修提交范围：改上述签名措辞；清 B3 全部残留（宽词 `分配|裁决|逐行|必答|复制|三方` 过一遍再人工筛，实施自述附命令与命中数）；补 B4 一条下游分派测试。通过后步骤 10 收口。

### 8. 返修（`6c7c9ed2`）· 独立评审（Claude，2026-09-04）

- 状态：**通过，步骤 10 收口。**
- B1/B2：六条台账 `approved_by` 改为「用户（2026-09-04 裁定，见 reviews/10 §7）」；两条预算 reason 末尾补「用户 2026-09-04 批准」。签名与 §7 一致。
- B3：上轮四处全清（SKILL.md 入口图改为「建骨架 → 按章写、按章落盘 → 统稿 → 登记」、spec 钩子注释、`glossaryMainName`、`prose_budget`）；
  本段新增的也清了（spec 钩子函数注释、plan 作者文档两条已删门禁改成「`must.text` 缺失」与「报告里没有本阶段判据的结论」）。
  宽词 `分配落点|裁决|逐行|必答|复制|三方|来源单元|audit|source-units|story-verdicts|by: author|待分配` 复跑：剩余命中全是退场理由注释、overlay 里「不出裁决表」的否定表述、
  图片规则里的「不复制文件」、SR 的「三方分工」——没有一处在描述已不存在的机制。
- B4：新增 `TheObligationReachesTheDownstream` 两条：挂 `verify: ut` 的 NEU-01 被 ut 阶段钩子点名；`verify: device` 的不被 ut 认领。分派按 `must.verify` 走，不按前缀。
- 复跑：story 534 全绿（55 s）；73 条 = 活跃 70（FAIL 0、委派 15）+ retired 3；预算门通过；改动的 5 个 `.mjs` 语法通过；hooks 与 story-build 零无调用函数；`framework/` 零差异。
  scripts_mjs 现值 2999（ceiling 3014，删 `glossaryMainName` 后余 15 行）。
- 留给步骤 11：A1（非知识类判据的「12 字引文」口径）、A2（P02–P04 与 12 条 observed 的夹具目录）、判据编号重排。
