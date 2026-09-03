# 步骤 9 · 正向 Story 作者路径切换 · 独立评审（Claude）

## 第二段 2a「⑦⑨ 换输入模型」（`2e59e110`，2026-09-03）

### 1. 结论

- 状态：**不通过（方向）**。代码本身干净、回归全绿（复审者复跑：story 619、失效形态 73/73 委派 0、`node --check`、预算门），
  但这一小段把一条本该退场的语义代理判据当成「要保留的判据」加固了，与步骤 9 的分工表、04 审计的迁移方向和用户
  「脚本只做纠偏兜底」的要求相反。改法很小，见 §4。
- 审查基线 `c8ad6f47`；对象 `story-build.mjs` 80 行 diff。预备提交 `c8ad6f47`（台账 `responsibility` 委派档）同审：通过——
  委派须 reason + approved_by、两步都不跑、单列一档报出，没有造夹具，与 D10 修订一致。

### 2. 行为重建

- ⑦ 规约判定表：编号与域名改从 `activeKnowledge(projectRoot).entries` 直接取（`activeKnowledgeEntries`），派生失败 `fail` 出声，
  离线给空。同一份数据换形状，与激活清单不再有第二层可失同步。**可接受**：它是集合完整性检查（每条激活规约在判定表里有一行），
  步骤 10 把判定表改为由 `knowledge-use.yaml` 生成后，这条自然变成生成一致性检查。
- ⑨ 归档件语言红线：`identifiers`（材料里出现过的 ASCII 标识清单）改为现场调 `materialUnitsNow(ctx, sourceDocs(ctx))` 枚举，
  `ruleIds` 改取激活清单。新增 `materialUnitsNow` 让 `init` 与 `check` 共用同一套枚举参数。

### 3. 问题

**B1 · ⑨ 的标识清单是 P1 的根因，本段把它从「init 落盘的旁路」升级成「check 现场枚举的正式输入」。**
`00-问题记录与原因分析.md` P1 已定位：`source-units.mjs` 的 `tokensOf` 按 `IDENT_RE` 切词，`（share-setup.png）` 切出 `share`，
`IDENTIFIER_SHAPE` 放行后成了「材料里出现过的工程标识」，红线于是拦下 story 里的图片引用行，与形态守恒互斥，作者只剩
`material_only` 一条出路。本段没有改 `tokensOf`（diff 只在 `story-build.mjs`），所以同一输入现在直接进 `check`。
`steps/09` 的「新检查分工」里脚本那一栏是：十章、非占位、材料版本未变、生成区、链接/图片、decision/状态/subject 一致性——
**没有「主叙事不得出现材料里的英文词」这一条**；`04-失效形态长期要求审计.md` 对 M10（全文标识扫描）的迁移方向是
「确定性生成技术区 + verifier 判断正文边界」，对 P08 是「确定性扫描（仓内路径、机制名）+ verifier」。
也就是说，材料派生的词表这一半在方案里本来就是要退的语义代理；本段把它当保留项来「等价迁移」，方向反了。

**B2 · 等价性证据对 ⑨ 没有区分力。** 九次运行 ⑦⑨ 都是 0 条，只证明不误报；能暴露 ⑨ 行为的形状（story 引用带连字符文件名的图）
不在这九份里。改前改后一样并不说明这条判据该留。

**A1 · `materialUnitsNow` 的存在理由随 B1 消失一半。** 它现在服务 `init`（第三小段退场）与 ⑨（应删）。删掉 ⑨ 的调用后它只剩
`init` 一个消费者，第三小段随 `init` 枚举一起退，不要留成「以后可能有用」的公共函数。

### 4. 要改成什么（只减不加）

- ⑨ 只保留**明确形态**的红线：`rule_id`（取激活清单，本段已改对）、`doc_coordinate`、`source_tag`、`search_phrase`、
  `placeholder_heading`、`ai_heading`、`harness_artifact`，以及 `repo_identifier` 里**行内代码、驼峰、下划线、仓内路径**这几种机械形态；
  **删除 `identifiers` 这一路输入**（`scanLanguageRedline` 的 `identifiers` 选项与 `materialUnitsForRedline`），主叙事里「这个英文词该不该出现」
  交 `story_reader_review`（它已在审「主叙事是否被工程语言打断」这一维度）。
- `materialUnitsNow` 暂留给 `init`，第三小段随 `init` 枚举一起删；不在 `check` 里留任何调用。
- 结果判据：把 P1 那份实跑快照（story 引用 `../assets/…/share-setup.png` 的版本）跑 `check`，⑩ 不再报 `share` / `accept`；
  其余七类红线在金样与两份快照上报错逐条与改前相同；73/73、619 全绿；`semantic_proxy` 计数不升。

### 5. 范围与回归

- 允许范围内；保护区零差异；未跑真实 Story（本段不要求）。
- 预算：`scripts_mjs` +57 行，在峰值内；本段目的就是为删判据铺路，净减要在 2b 兑现。

### 6. 后续

- 允许提交：已提交；**2a 需要一个返修提交**（删 `identifiers` 输入），不重做。
- 2b（删五类判据并迁台账）在 2a 返修评审通过后开始。

## 小段 1 返修（`41ff385f`）与小段 2（`d78b69e0`）· 独立评审（Claude，2026-09-03 晚）

### 1. 结论

- 小段 1 返修：**通过**。`identifiers` 输入与 `materialUnitsForRedline` 已删，`lint-rules.mjs` 只认行内代码、驼峰、下划线、仓内路径这几种
  机械形态，注释写明了连字符文件名切出伪标识的成因；`materialUnitsNow` 只剩 `init` 一个消费者，随小段 3 退。
- 小段 2：**通过**，附三条要在小段 3 收的桥与一条 advisory。
- 复审者复跑：story 548 全绿（55 s）；失效形态 73 条：FAIL 0、委派 3、PASS 70；预算门 5 条通过，语义代理标识 34 处（冻结 37）；
  `node --check` 通过；`story-build.mjs` 2409 行。**一次异常**：同一套测试我先跑了一次，1443 秒、1 条 error，第二次 55 秒全绿，
  首轮日志没留下是哪条——记为 advisory A2。

### 2. 行为重建

- 五类判据（② 落点守恒、④ 形态守恒、⑥ 裁决核实、⑥b 逐问逐章、⑧ 术语实体词）整段删除；现存判据：⓪a/⓪ 来源与材料版本、
  ① 章标题顺序、①b 大标题编号、③ 编号形态、④ 图片身份、⑤ 决策字段、⑦ 规约判定表、⑨/⑩ 红线（机械形态）、⑪ 可读性、
  ⑫ 附录结构、⑫a 非占位、⑫b 章节级形态、⑫c 形态 lint、⑫d 统稿留痕、⑫e 固定形式、⑬ 评审渲染语法。
- 图片身份从形态守恒块救出独立成 ④：只判 alt、重复引用、引用是否在材料清单登记、归档副本是否字节相同——确定性的链接与图片检查，符合 steps/09 分工。
- 台账：C01、R01、S01 登记 `observed`，reason / approved_by / observed_by 齐；`check_failure_modes.py` 对 observed 只核字段、两步不跑、单列报出；checker 与夹具字段删除。
- 测试：71 条按类主题退场，处置表逐类可核；忽略空白后 `test_story_allocate_render.py` 实际只删 `covered_by` 一条；`TheLibraryItselfIsComplete` 判据未动、基线重编号。
- `CliRuntimeIsolationTest` 的「全量红」经在 `41ff385f` 复现为假阳性（诊断脚本传了精简 env），仓内无此问题。

### 3. 桥（登记，小段 3 收）

- **B1** `check` 的 `requireLedgers` 仍要求五件台账在（`source-units.json`、`audit.json`、`decisions.json`、`story-verdicts.md`、`copyedit.md`），
  而现在没有任何判据读 audit 与裁决表。小段 3 之前作者仍要产出它们，只是没人看——退场 `audit`/`init` 枚举时把 `STORY_SRC_LEDGERS` 与
  `story_flow.py` 的 `STORY_SRC_FROZEN` 一起收到 `decisions.json`（+ `copyedit.md` 若统稿留痕保留）。
- **B2** 固定形式类判据还在：⑫e 固定形式、⑫b 章节级形态（`min_sections`）、⑪ 可读性、⑫c 形态 lint。04 审计把 S02、S13、S14、S08、S09、
  S03、S04、S18、S20 的目标全部迁给 verifier「按效果判」，steps/09 的脚本分工里也没有它们，但至今没有一个步骤点名退它们。
  **归小段 3**：随作业书改写一起退，对应形态改 `observed`（observed_by = `story_reader_review` 的对应维度 + 用户三轴评分「产物结果」）。
  留着它们，作者仍会被「必须成表 / 必须分节」拦住，那是批次 4 的老路。
- **B3** `materialUnitsNow` 与 `init` 枚举、`source-units.mjs` 一起退；`materials.json` 是唯一材料真源。

### 4. advisory

- **A1** 三条 observed 的 `observed_by` 写的是「审查者报不报 + 用户评分看」，步骤 11 的评审报告要按这三条各写一行实际观察结果，不能只写「已委派」。
- **A2** 全量测试出现过一次 1443 秒 + 1 error 的不稳定运行，第二次 55 秒全绿。测试域里有会等外部进程或网络的用例（`verifier-smoke`、`test_harness` 一类），
  归步骤 3 的范围补一个「无外部依赖时必须 60 秒内跑完」的自检，或把那几条标成需显式开启。

### 5. 后续

- 允许提交：已提交。小段 3 可开工，范围 = 原定内容 + 上面 B1、B2、B3。
