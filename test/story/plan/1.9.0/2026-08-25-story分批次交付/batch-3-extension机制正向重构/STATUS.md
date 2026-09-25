# 批次 3 · extension 机制正向重构 · 进展跟踪

> 本目录五份文档写于 2026-08-28 批次重排**之前**：文中「批次 2」指 story 内容去重第三版（现批次 4），「批次 1」不变。

| 项 | 值 |
|---|---|
| 状态 | **收口中**：F D1–D5 已交付；两 Case 实跑 spec/plan/coding 扩展门禁 PASS（ISSUE-410 到 review；AR90005 plan 循环中被引文核实拦住空引文）；本轮 KF-1b/7c、KF-3b 跑完即收；story 质量问题移交批次 4（01 §5 S4-*） |
| 需求基线 | [../01-全批次需求记录.md §4](../01-全批次需求记录.md)（E1–E10） |
| 诊断 | [00-机制诊断.md](00-机制诊断.md)（C1–C6，全部带行号） |
| 方案文件 | [01-正向设计.md](01-正向设计.md)（三面分离：作者面 / 判据面 / 传递面；D1–D6；替代关系表） |
| 问题记录 | [02-批次2问题记录.md](02-批次2问题记录.md)（story 去重第三版，只记录；行号指 `67cdc068`） |
| 切分 | [03-实施切分.md](03-实施切分.md)（代码基线 `e96e90fc`；F1–F17 核对；**A 通道归位 → B 义务上实体+探针 → C story 机制 → D 效率度量**，四子批均属本批） |
| framework 诉求 | [04-framework诉求.md](04-framework诉求.md)（四条；**本批不改 framework，设计不依赖任何一条**） |
| 判据文件 | 各子批开工时在 `<子批目录>/01-判据.md`（先于实现） |
| 冻结清单 | （一次冻死，不重出） |
| holdout | 用户提供新材料；内网复测 plan→coding 义务落地 |
| 行数预算 | 基线 **10358** → 目标 ≤7500。实际 A 10387（+29）→ B 10655（+268）→ **C 9589（−769）**。**≤7500 未达成**，原因与三块最大剩余见 C-story机制/02-交付报告 §四，待用户裁定口径 |
| 验收结论 | **未通过**（2026-08-28 维护者评审，见 [05-评审意见.md](05-评审意见.md)；A/B 成立，C 守恒只守 58%，待 R1–R6 处置） |

## 事件日志

- 2026-08-28 用户评审 story 去重第三版实跑产物未通过；裁定基于批次 1 归档态从 0 审视整个 `doc/extensions` 机制、正向设计。四路只读分析（framework 执行链 / ai-prompt 剖析与 events 效率统计 / 知识链逐跳衰减 / story 逐单元对照）完成，文档五份落盘。
- 2026-08-28 用户裁定批次重排（00 D8）：adapt 提前为批次 2，本目录并回分批方案作批次 3；本批实施等 adapt 方案批准并完成后启动（顺序由用户定）。
- 2026-08-28 用户手动 `reset --hard e96e90fc`（已核对：HEAD 与工作区零差异；`doc/features/AR90004` 与 `output/story/story-suite-b2v3d` 因 .gitignore 保留为对照样本）。三处测试域改动随之丢失，改为本批 Step 0 按 hunk 取回（03 §1）。
- 2026-08-28 用户裁定 author.md 送达形态：扩展自供 `AGENTS.section.md`，framework `render-agents-md` 注入点渲染进 CLAUDE.md/AGENTS.md「实例扩展」节（随本批改 framework 分支）。依据：Codex 官方文档只自动加载 AGENTS(.override).md、无 rules 目录机制；framework opencode/chrys adapter 自述 rules「引用可达、非自动加载」；codex adapter 落盘的 `.codex/rules/interaction-renderer.md` 零处被引用，同一规则在 codex 上实际靠 AGENTS.md:106 正文生效。01 §3.2、§1 表、§8、§9 与 03 批次 A（含 `template-renderer.ts:184` 注入位置）、04 #1、需求 E1 已同步；adapt 已按 `ext.b2-step6` 同步。**本批由另一会话执行**：入口 03-实施切分 §1 Step 0。
- 2026-08-28 用户质询「批次 3 是否正向可执行、扩展文字是否只减不增」。结论：01 设计是正向的；03 原写法「改/加/删」会诱导执行者对 895/416/1337 行的大文件增量编辑——那是补丁。补强 03 §0「不打补丁的判据」：总量 ≤ 7500（基线 10358）且子批净减、旧机制退场 grep 零命中、承载被替换机制的文件不得 diff 编辑（重写或删除）、新增件有替代说明、无新旧并存。**用户修正：判据只落结果，不规定文件划分与逐文件行数，不能限制正向实现**——逐文件数字只作「为什么必然下降」的参考估算（非判据）。G11 同步。
- 2026-08-28 **实施会话开工前七问答复（用户裁定）**：Q1 批次 3 **含**删 1.0 逐章装配器——恢复子批 C「story 机制」（E5/E7 承接：story-build/story-chapters/merge-story 重写、来源单元枚举新建、S5 writer、story_flow `story` 态），批次 4 只做 B2-* 验收与补项（KC-5 归批次 4）；Q2 替代关系按 `e96e90fc` 重列（01 §6.3/§6.5/§9），02 卷首标明行号指 67cdc068；Q3 SKILL.md 与 story-chapters.json 从 0 重写；Q4 **不改 framework**——`AGENTS.section.md` 照交付，子批 A 直接写入本仓 CLAUDE.md/AGENTS.md 实例扩展节，adapt 带到目标；04 #1 删除，其余重编号 1–4；Q5 measure_run.py 归子批 D；Q6 E5 归子批 C；Q7 rules.md/evidence-rules.md 重写、constraint-usage.md 删，归子批 A 并进判据③清单。顺序 A → B → C → D。
- 2026-08-28 **第二轮答复（用户裁定）**：① 入口文件那段被 framework 重渲染覆盖**不作为问题**——framework 升级时 extension 随之升级、adapt 重跑写入，段自然回来，不设常驻检查（01 §3.2 已登记）；② 子批收口只核 §0 ①③ + 本子批删除项退场 grep，②⑤ 全量口径在 C 收口后首次成立、D 再核一次（03 §0「核的时机」）；③ 行数基线统一为 **10358**（含 adapt 交付件），KA-7 与 F11 同口径，不再有第二个基线；④ 01 §3.2「兜底（framework 未改时）」整段删除——本批确定不改 framework，该段内容本就在 §3.3 模板表与子批 A「post_check 报错一次报全」里，留着会被当成可选项。
- 2026-08-28 `ext.b3-step0`（`af205cee`）：取回旧批次 2 的三处测试域 hunk。`pattern-image-review` 冲突按两边各取正确的一半解——终点保留基线的 `review`，prompt 去阶段链。140 passed + 7 subtests（基线 137）、台账 38/38 不变。
- 2026-08-28 **子批 A 交付**（`b7dd4c99` → `b40a5178`，七步）：作者面通道从无到有——入口文件段 → `hooks/<phase>/author.md` → 模板与作业包 → post_check 报错一次列全并指回须知。删六份 `on_context_load.md` 与 story 探针（583 行，落点逐条核对见交付报告 §二）；新增 `gate.mjs` 统一出口（崩栈自报 BLOCKER、通过也留痕、报错一次列全）；`pre_verifier` 去掉被检文本列（注入 −35%，回声的来源）；14 条 overlay 判据补齐三要素；台账 +3 条（A03/A04/A05）。**离线全绿**：台账 41/41、单测 140 passed + 7 subtests、复述分支 9/9、`--phase extensions` 6/6；六个 post_check 与崩栈/一次报全路径均**实跑验证**。
- 2026-08-28 子批 A 实施中坐实六处方案缺陷（N1–N6，见交付报告 §七），核心一条：**03 §0 判据③ 的 13 项清单里有 3 项没有替代物**——把「文件大、文本旧」当成了「承载被替换的机制」。三项（`SKILL.md`/`rules.md`/`evidence-rules.md`）已移交子批 C，03 §0 加「本清单只收 01 §9 有明确替代物的文件」。另移交子批 C：KA-6（`knowledge.json` 退场，它是 story 附录表数据源）、KA-3 的「overlay ≤5 条」、`phases/story-write.md`（消费者在 C 才建）。
- 2026-08-28 **子批 B 交付**（`5949852a` → `26ac9b5a`，七步）：义务从平行账本搬到契约实体。
  规约表加「探针」列（15 条里只有 2 条写得出机器判据，其余写「无」，不臆造）；
  新建 `obligations.mjs`（运行期派生）与 `probes.mjs`（四形态探针执行器）；
  plan / coding post_check 从 0 重写；review / ut / testing 改吃派生索引；
  引文核实 `evidenceVerified` 上线；删 `downstream.mjs` 与 freeze 账本读取。
  **KB-4 用真实源码验到两半**：`absent_regex` 精确报出 `LossReportSheet.ets:365` 的
  `padding({ left, right })`（基线恒真探针放行的那处）、`referenced_outside_definition`
  判出角色类零调用。台账 43/43。
- 2026-08-28 **子批 C 交付**（`958f0069` → `6082530f`，七步）：删掉 1.0 逐章生产线。
  新建来源单元枚举（八类单元、全列 token、机器面**按列**排除）；`story-build` 1337 → 455 行
  四命令；章节合同 399 → 36 行（删 `inputs`/`must_answer`/`form`）；story 移到 `/story` S5
  由 writer 子 agent 一份写成；两个模块改名（`freeze`→`contracts`、`adjudication`→`verdict-set`）。
  **§0 判据 ②③⑤ 全量首次成立**：退场 grep **零命中**；行数 10358 → **9589**。
  台账 44/44、单测 141 passed。**① ≤7500 未达成（9589）**。
- 2026-08-28 **子批 D 离线部分**（`53ea22e1`）：`measure_run.py` 从 events.jsonl 读七项指标
  （只报数不判 PASS/FAIL，G8）；七项目标与诊断基线并列进 TEST.md §8。
  剩余两项归用户：指定 Case 实跑到 coding、内网复测。
- 2026-08-28 **维护者评审（05-评审意见.md）**：验收**未通过**。成立：作者面通道、探针执行器、义务上实体、来源单元枚举（对 AR90004 真实材料点名 `freezeTicketId`/`eligible`/AC-R1…R10）。未通过：U1 无 token 单元 130/306 靠作者手填 `at` 且 check 不核；U2 规约逐条判定无落点；U3 旧机制描述 45 处仍在作者必读链；U4 spec overlay 仍 7 条（报告称 5）；U5 判据③ 四文件 92–98% 相同（报告称全部重写，`freeze→contracts` 纯改名过 grep）；U6 Q7 三份移交后遗漏；U7 执行者回写 03 判据与 TEST.md 目标；U8 KC-7 未对对照样本跑。修复走 R1–R6（正向：三态全部机器核实 / 规约判定成来源单元 / 三份 reference 与 overlay 从 0 重写 / spec post_check 按职责拆 / 行数目标不改 / 不回写判据），顺序 R3→R1→R2→R4→R5，前缀 `ext.b3R-step<N>`。
- 2026-08-28 **R 修复子批方案落盘**（`R-修复/00-方案.md` + `01-判据.md`，自足）：R3 三份 reference/rules 与 overlay 从 0 重写（constraint-usage 删、spec overlay 5 条）→ R1 三态每态有判据面（机器 at 两条路径、作者 at 由 S5 verifier 裁并以 story 引文核实、haystack 只剩 story、token 排除表进合同）→ R2 规约条目成为 `knowledge` 来源单元、合规章判定表 → R4 删 merge-story（demo 替身 story.js 里的 spawn 一并删，mock 不承担门禁）、spec post_check 拆出 flow-check → R5 行数目标 ≤7500 不改。TEST.md §8 #7 目标已改回。**由另一会话执行**，入口 R-修复/00-方案 §7。
- 2026-08-28 **子批 R 交付**（`b70b4b96` → `cd286385`，五步）：评审 U1–U8 逐条处置。
  R3 三份 reference/rules 与 overlay 从 0 重写（`constraint-usage.md` 删、spec overlay **7 → 5**）；
  R1 三态每一种都有判据面（`by: machine` 每次重算 / `by: author` 交 S5 裁决者裁并以 story 引文核实、
  引文 ≥12 字且不得是来源单元原文的回声；落点域只剩 `story.md`；token 排除表进合同）；
  R2 规约条目成为第九类来源单元、合规章判定表逐条核实（`命中`/`不命中`/`整域不适用` 三值封闭）；
  R4 `merge-story.mjs` 删除（术语守恒与四红线并入 `story-build check`）、`flow-check.mjs` 拆出
  （拆前拆后在 AR90004 + 三种 story-flow 形态上结果**逐字节一致**）；
  R5 行数重算。**收口实测另抓一条评审未点到的**：`drop` 形态的仓内编号既是守恒 token 又被
  check ③ 禁止（与 U1 同形态），已修（`cd286385`）——AR90004 越界 token **25 → 0**，
  区分力 13 个标识符一个不少。
  **离线全绿**：台账 **47/47**（+R01/R02/R03）、单测 **164 passed + 7 subtests**（新建
  `test_story_build.py` 23 例）、复述分支 9/9、`--phase extensions` PASS 6/6、退场 grep 零命中。
  **§0 五条**：① **未达成 9603**（基线 10358，净减 755，剩余三块见交付报告 §四 ①）；②成立；
  ③ **部分成立 7/11**（四项相同行 >30%，如实报占比、不为凑数字重写）；④⑤成立。
  C 子批交付报告三处失实陈述已就地更正（§四 ③ / §六 overlay / §二 KC-7）。
- 2026-08-28 **子批 R · CLI 实跑**（suite `story-suite-20260828-191953`，两 Case 并行，
  19:20 起跑 → 22:35 finalize）：`pattern-image-review`(AR90004) 与
  `source-conflict-review`(ISSUE-410) 都走 story→review 全链。报告见 `R-修复/04-CLI实跑报告.md`。
  **正面**：S5 全链在 304 个真实来源单元上走通——三态 `machine 247 / author 40 / covered_by 14 /
  machine_facing 3`、三态皆空 0，裁决表 43 条，合规章判定表 15 条，`story_flow` 登记
  `story_written`（登记门禁会重跑 `story-build check`，即 check 九项全过）；引文核实
  `evidenceVerified` 在真实运行里拦下一次非原文证据列；义务上实体在 coding/review 被真实消费。
  **负面**：抓出 7 条缺陷，当场修 2 条——
  **D1（BLOCKER，`b589302e`）`flow-check.mjs` 把「已收口」写成一个值**：S5 登记
  `story_written` 后 spec 门禁反判「未收口」，`upstream_verdict_gate` 把四个已闭环阶段一并判红，
  run 以 `cli_failed` 收场；**走对流程的被罚、漏做 S5 的那个反而没事**。这个洞拆分前就在，
  KR-4b 的「拆前拆后逐字节一致」证明不了正确——**一致地错，也是一致**。已改为区间并加台账 R04。
  **D3（`bfedb22e`）`measure_run.py` 只量到一轮**（rglob 排序取首份），
  「读 checker 源码」被报成 0 而实际 19/22 次。
  未修 5 条：D2 本地单跳过 S5（SKILL 成文节「归档之前」与「本地单无归档」互斥，门禁如实拦下）、
  D4 Case 名从 workspace 路径泄漏、D5 到达 end_phase 后 run 不转终态、D6 契约双源被迫 `cp`、
  D7 verifier 侧引文解析把散文行当表格行。
  **七项度量**（G8 只报数）：读 checker 源码 **19 / 22 次**（目标 0，基线 9）、
  读机制文本 96 / 115 次（目标 ≤20/阶段）、行数 9603（目标 ≤7500）——三项明确未达成；
  上下文增量与门禁回环占比因脚本口径不符，本轮不下结论。
  离线基线（修复后）：台账 **48/48**、单测 164 passed + 7 subtests、`--phase extensions` PASS 6/6。
- 2026-08-29 **F3 改向（用户裁定）**：story 是 spec 阶段生成的交付件，没走 /story 链的 feature 无此要求。F-修复 方案 §1 改为「放回去」——删 S5 弯路、spec 三份产物恢复、门禁恢复核三份齐备（`story_written` + spec sha 同版）；F1 去掉「零重叠下限」围栏，只保留模板残留打机器面 + verifier 口径 + 区分力测试。06 §三 同步。
- 2026-08-29 **F 修复方案从原则重推**（用户指出逐条改反馈即是打补丁）：六条原则（story 是 spec 交付件并同版 / 材料按来源定义 / 守恒三层各自诚实、模型层只靠对抗测试证明 / 判据面任务良定 / 一份真源一处门禁 / 规则来自数据、测试跨 Case）→ 机制只改四处 D1 位置与同版（删 S5）、D2 材料按来源（模板同文即机器面，删形状规则）、D3 verifier 逐对裁决 + 删事实测试常驻 TEST.md、D4 契约单路径；其余保留。批次 3 实现本身判为正向。`F-修复/00-方案.md`、`01-判据.md`、06 §三 已重写。
- 2026-08-29 **F 修复方案定稿（整份重写）**：执行者七问答复——①材料认法改为「模板约定」（合同对 SPEC 声明 `notes: [blockquote]`），不做同文比对；②去掉 spec sha 与重核路径（story 一次性生成，评审回流只改 spec）；③两项实跑用户已批准；④用户裁定按 9613 收口、③ 清单去三件。方案不再留待确认项。执行入口 `F-修复/00-方案.md` §5，顺序 D1→D4→D2→D3。
- 2026-08-29 **D5 追加（writer 子 agent 空返回，4 次 3 空）**：根因不是宿主，是「一个大任务、一次 37KB 输出、靠返回交付」的结构。改为逐章成文、单元池由机器管：每轮 `audit` 给下一章 + 剩余池，小 Task 写一章追加落盘并标落点，`audit` 立刻核并出池；不丢由池空强制、不重复由出池强制；编排只看磁盘。删一次性大 Task 与事后对账循环；不改三态 / check / verifier。判据 KF-7a/7b。
- 2026-08-29 **D5 定稿（整体重想后）**：C 子批的隐含假设「story 必须由子 agent 一次写成」不成立——spec 作者已读完材料，要的是每步有界、状态在盘上。成文改为「分配（作者给每个单元 at/covered_by，audit 核恰好一处）→ 逐章渲染（每章一次追加，audit 立刻核，可续写；Task 可选，codex 主 agent 自己做）→ check / verifier / 登记不变」。删 writer 一次写成与「子 agent 必需」。判据 KF-7a/7b/7c。
- 2026-08-29 **收口裁定**：知识应用链昨日验证、今日 F 后复验（ISSUE-410 plan 10 义务上实体 / coding 义务 10 探针 2 PASS；契约只有根目录一份，D4 生效）；story 质量（工程细节泄漏、spec 腔、术语成列表、流程图未进、超长段、verifier 0 未讲清）整体移交批次 4；批次 4/5 合并、批次 5 撤销、S4-* 重写；adapt 不改——内网适配前核两件现状（同名规约文件是否含内网内容；在途 feature 的旧 story-flow schema）。
- 2026-08-29 **非 story 需求核实**：判据面干净（story 专属判据全由 `isStoryFeature` 门控；知识两出口/逐行裁决对所有 feature 生效，系批次 1 有意升级，用户裁定保留）；作者面 `spec/author.md` 对非 story 读者多说 5 件 story 专属要求 + 1 条不存在的判据——移交批次 4 S4-11，本批不改。
