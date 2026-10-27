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

## 小段 3「生产环节与作业书退场」（`b991a22d`）· 独立评审（Claude，2026-09-04）

### 1. 结论

- 状态：**返修后通过**——机制面对了，交付面的文字与死代码没跟上。需要一个返修提交（只删只改措辞，不加判据），不重做。
- 复审者复跑：story 505 全绿（46 s）；cli 18；失效形态 73 条：FAIL 0、委派 12、PASS 61；预算门 5 条通过；`node --check` 三个 `.mjs` 通过；
  `framework/` 零差异。机制层现值：scripts_mjs 3144（= ceiling）、scripts_py 1810、hooks_mjs 3567、prompts_md 2714（已低于 target 2800）、data 839、总 12074。
- 三座桥全部收到：B1 `requireLedgers` 与 `STORY_SRC_FROZEN` 同收为 `decisions.json` + `copyedit.md`；B2 ⑫e/⑫b/⑪/⑫c 图承接随作业书改写退场，
  S02/S03/S04/S08/S09/S12/S13/S14/S20 九条迁 `observed`，`observed_by` 逐条对得上合同 `chapter_dimensions` 与 overlay `story_reader_review` 的维度；
  B3 `materialUnitsNow`、`init` 枚举、`source-units.mjs` 一并删除。
- 两处「误删救回」核实：⓪b 台账指纹核对独立成块、报错文案与改前一致；`TestArchiveRedlines` 类头恢复，仓内路径红线那条测试仍在。

### 2. 行为重建

- `story-build` 六个命令：`init` 只查材料齐备、建 `decisions.json` 骨架；`skeleton` / `chapter` 不变；`check` 现存 15 条判据
  （⓪a ⓪b ① ①b ③ ⑤ ⑦ ④ ⑨ ⑩ ⑫ ⑫a ⑫c ⑫d ⑬），逐条看过，没有一条读内容判语义；`audit` 命令与入口分派删除。
- 新测试 `test_no_unit_ledger_is_produced_at_any_point`：init → 十章 chapter → check，三份逐单元台账全程不落盘。这是完成条件第一条的机械证据。
- `check_failure_modes.py`：`_seed_author_side` 删除；G01 反例改注入占位符，不再挂在已退场的可读性判据上；F02 改核 overlay 而非已删的 `story-verify.md`——判据跟着对象走，没有静默放过。
- 预算：`scripts_mjs` ceiling 5200 → 3144、`semantic_proxy` 37 → 34，reason 写明退了什么，符合 steps/09 预算节「第二段完成后压到现值」。

### 3. 要返修的（交付面）

**B1 · 作者作业书仍在描述已退场的角色与步骤。** 这是给作者读的正式文本，步骤 11 真实跑时作者会照着找不存在的东西：
- `phases/story-write.md`：L97–100「决策单元…落点…开放议题不在待分配清单里」；L134–136「分给这一章的十几条单元是素材…一条单元对应一个句子」；
  L200「由裁决者按语义判」；L231「裁决者逐条对齐单元、也不看整篇」；L254「内容真不真由裁决者与抽样人核管」；
  L275–276「裁决者不看它们——他的任务是逐条对齐『这个单元 → 那一章讲没讲』」。裁决者这个角色已经不存在，语义面现在是 `story_reader_review`；
  「分给本章的单元」这件事也不存在了——材料整份在作者手上。
- `phases/spec.md`：L48–49「按下面五步走完…（分配、逐章渲染、统稿各一段）」（下方实际是 ①–⑥、作业书是两步）；L70「自查清单见 story-write.md 第三步」（现在是第二步）；
  L74–75「② 与 ③ 分开…分配先把『每件事去哪一章』定死并落盘」（② 现在是 skeleton，没有分配）。

**B2 · spec harness 给作者的处置指引指向不存在的步骤。** `scripts/flow-check.mjs` L307–308：「`story-build.mjs init` → 分配落点 → 逐章渲染 → 统稿 → 按 story-write.md 逐章落盘 → 登记」。
这是叙事件未登记时 harness 打印给作者的修法，顺序错、步骤名错。应与 `phases/spec.md` 的 ①–⑤ 同一口径：init → skeleton → 按章 chapter 落盘 → 统稿 → build → `story_flow.py story` 登记。

**B3 · `rules/review_reflow.md` L9–10 是一句改坏的话**：「那两件（`decisions.json` / `copyedit.md`，加上 `decisions.json` / `story-verdicts.md` / `copyedit.md`）」——半句旧文没删，还点名了已删除的 `story-verdicts.md`。

**B4 · `story-build.mjs` 里没有消费者的代码与过时的对外文案。**
- 无调用者的函数：`sourceDocs`、`chapterForms`、`pushInto`、`isEngineeringIdentifier`、`fencedText`、`appendixRowFor`、`buildTokenExclusion`、`missingGlossaryTerms`；
  无引用的常量与函数：`VERDICT_WORDS`、`IMAGE_KINDS`、`minQuoteChars`。它们是本段与小段 2 退掉的判据的残肢，AGENTS §8「无消费者代码」不允许留到步骤 11。
  删掉 `minQuoteChars` 与 L863 那句「回声」注释后，`story-build.mjs` 的语义代理标识归零（34 → 31），与 steps/09 预算节「story-build 归零」一致。
- 对外文案仍说旧流程：`refuseIfFrozen` L233–234「那一刻的来源单元、落点账、裁决与决策登记」；`cmdInit` 阻断文案 L482–484「这一类材料缺席时枚举不出任何单元…守恒面小了一圈」（init 已不枚举）；
  注释 L447「init：枚举来源单元」、L195–201「五件台账…裁决件只在存在 by: author 记录时」、L135–138「单元清单与核对记录给空」、L61–68 `material_only`/`at`/`covered_by` 三态说明、L1326「归裁决者」。
- `story_flow.py` `sweep_story_src` 文档串 L86–98 仍说「只留台账那五件」。

**B5 · 合同里没人读的数据。** `contracts/story-chapters.json` 仍带 `section_form`（含 `__two_tables__` / `__each_h3__` / `prose_budget`）、`min_sections`、`section_required`、
`section_required_with_settled_decisions`、`section_note`、`allocation.appendix_bound`、`machine_facing`——全仓 `.mjs/.py/.yaml/.md` 没有消费者（`subsection_form`、`questions`、
`chapter_dimensions`、`id_shapes` 仍有消费者，保留）。判据在本段退场，它们的数据应同段退，否则下一个维护者会去找「谁在读 section_form」。
`verdicts.min_quote_chars` 的消费者只剩 `hooks/shared/verifier-report.mjs`，归步骤 10 随引文核实一起退。

返修的结果判据：B1–B5 全部只删只改措辞；story 505、cli 18、73/73、预算门仍绿；`semantic_proxy` 现值降到 31 后把 ceiling 压到 31；交付面 grep
`audit|source-units|story-verify|story-verdicts|by: author|裁决者|待分配|来源单元` 在 `doc/extensions`（knowledge 之外）为零命中（设计模式候选登记里的「适用单元」是另一个概念，不在此列）。

### 4. advisory

- **A1** 实施记录写「全仓 grep 只剩设计文档里的历史记录」，与 B1–B4 的事实不符。按 AGENTS §7.3，自述不替代审查；下次自述里附 grep 命令与命中数。
- **A2** 12 条 `observed` 形态的夹具目录（`fixtures/failure-modes/C01、R01、S01、S02、S03、S04、S08、S09、S12、S13、S14、S20`，约 200 个文件）已无任何消费者，
  只有批次 3/4 的历史文档提到。按 steps/11「删除旧回归 checker、夹具」处理，本段不动。
- **A3** `check_failure_modes.py` 里 `_chapter_for`、`_quote_for`、`_verdict_tables` 只剩定义；`_story_build_cycle` 文档串仍写「init → audit」。测试域，归步骤 11 清理。
- **A4** 判据编号跳号（②④⑥⑧⑪ 空缺、④ 排在 ⑦ 后）：同意留到步骤 11 统一重排。
- **A5** P13 作者侧：作业书把作者指向 `materials.json`（每张图 kind / paths / sha256），满足「从 materials.json 逐张列出含路径」的最小形态；作者拿到的是 JSON 而非渲染清单，
  步骤 11 要观察作者是否真按这些路径引图。

### 5. 范围与预算

- 允许范围内；保护区（framework、knowledge、金样、真实 Case 输入）零差异。
- 预算：本段净减 scripts_mjs −1049、prompts_md 净减、data −7；未超任何峰值；prompts_md 已低于 target。B4/B5 返修后 scripts_mjs 与 data 再降，ceiling 随之压到现值。

### 6. 后续

- 允许提交：已提交。**返修一个提交**（B1–B5），评审通过后步骤 9 收口，步骤 10 可开工。

## 小段 3 返修（`20f7841f`）· 独立评审（Claude，2026-09-04）

- 状态：**通过，步骤 9 收口**。B1–B5 逐项核过：作业书与 spec.md 不再有分配/裁决者；flow-check 指引与 spec.md ①–⑤ 同口径；
  review_reflow 那句已改好；八个无调用函数与三个常量已删，`story-build.mjs` 语义代理标识 0；合同死键已删（`prose_budget` 见下）。
  复跑：story 505 → 527 全绿（含步骤 10 小段 1 的 22 条）、73 条 FAIL 0 委派 12、预算门通过、`framework/` 零差异；
  ceiling 压到现值：scripts_mjs 2979、semantic_proxy 31。
- **grep 漏网四处**（不另开返修，随步骤 10 下一个提交顺手清，步骤 11 前必须为零）：
  `skills/story/SKILL.md:24`「story：分配落点 → 逐章渲染 → 裁决 → 登记」是 skill 入口图，作者第一眼看到的就是它；
  `hooks/spec/post_check.mjs:6` 注释「分配落点后逐章渲染」；`story-build.mjs:566` `glossaryMainName` 随 `missingGlossaryTerms` 删除后成了新的无调用函数；
  合同 `story-chapters.json:157` `prose_budget: 1` 无消费者。
- 实施记录这次附了 grep 结论但仍漏了 SKILL.md——grep 词表里没有「裁决」单字形态。下次用 `分配落点|裁决|单元` 这种宽词再人工筛。
