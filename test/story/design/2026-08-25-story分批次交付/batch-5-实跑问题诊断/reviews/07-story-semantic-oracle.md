# 步骤 7 · Story 语义审查与区分力资格门 · 独立评审（Claude，2026-09-03）

## 1. 结论

- 状态：**装置通过，附一条返修（须在步骤 9 切换前落地）；资格实跑按用户授权暂缓，结论 A（区分力）未取得**
- 审查基线：`4e9a6d21`；审查对象：`01b7e74f` 的实际 diff（overlay 新增判据、两份 good 基底、`pairs.json`、生成器、13 条离线测试、TEST §8.1/§9.1、`baseline_coverage.py` 退场注释）
- 亲自复跑：`test_narrative_variants.py` 13 条、全量 story 599、cli 18、失效形态 73/73；生成器跑两次逐字节相同、17 个文件（14 份样本 + 2 份材料 + index）；交付面对夹具、金样、测试路径与 Case 业务名零命中。

## 2. 行为重建

- **审查任务**：`rules/spec-rules.overlay.yaml` 新增 `semantic_checks.story_reader_review`。输入是 `materials.json` 指向的材料、`story-flow.json` 已确认范围、`decisions.json`、spec 已成立约束；按合同 `chapters[].questions` 与 `verdicts.chapter_dimensions` 审十个方面；结论只有 `blocking_findings` / `advisories` 两类；明写「不逐条核来源单元、不出裁决表」；`AR/story.md` 不存在时 SKIP。
- **送达路径**：overlay 经 `profile-loader.ts:89-91` 并入 merged phase rule，随 `{spec_content}` 进入 `ai-prompt.md`（`report-generator.ts:337`）；`verify-spec.md:51` 要求 verifier「以 merged phase-rules 是否包含对应条目为准」逐项输出 `checks:`。
- **执行证明**：**没有**。扩展现有的「注入 ≠ 执行」收口只覆盖 `knowledge_` 前缀的判据（`hooks/shared/pre_verifier.mjs:39-70` 的 `KNOWLEDGE_CHECK_PREFIX`，`verifier-report.mjs` 只核必答集键）。`story_reader_review` 不在必答清单里，报告里有没有它、有没有那两类结论，目前没有任何机械核对。见 §4 返修。
- **资格器材**：两份 good 基底（交易凭证下载 / 门店排队叫号提醒，十章齐、各含一张流程图、术语与编号无重叠）+ `pairs.json` 六族 × 两变体的精确编辑（删事实、掏空章、编造、删流程图、知识回显、同义改写）；`make_narrative_variants.py` 由基底现生成，锚点非恰好一次即报错，编辑后与基底相同即报错。
- **旧发现者**：三张裁决表与 `story-verdicts.md` 仍在正式路径，TEST §9.1 登记为过渡态并存；`baseline_coverage.py` 登记随步骤 9 退场，在此之前不参与 PASS/FAIL。

## 3. 验收证据（对 `steps/07` 完成条件）

| 完成条件 | 证据 | 结果 |
|---|---|---|
| 成对样本 good 通过 / bad 命中本族 | 器材就位（`test_each_family_has_two_variants_in_two_domains`、`test_every_bad_sample_differs_from_its_base`、`test_a_same_meaning_variant_is_expected_clean`）；**区分力结论未取得**（授权暂缓） | 待验证 |
| 「十章在而内容大量丢失」稳定失败 | `chapter_hollow` 两变体已定义（抽查：业务流程章整章替换为一句空话，十章标题仍在） | 待验证 |
| 报告按问题族增长 | overlay 文案明令不出裁决表、两类结论；实跑前无法证明 | 待验证 |
| 各配置独立资格结论与矩阵 | TEST §9.1 定义了配置 × 问题族记法；无数据 | 待验证 |
| verifier 身份与 subject 由 D1 机制验证，扩展不自建通道 | overlay 只加判据，无报告通道；D1 链路见 `reviews/01` | PASS |
| 区分力不足只修任务与输入，不加 token/相似度/数量 checker | diff 中无任何新 checker；生成器无阈值 | PASS |
| P11/C01/R01/F02 及 S 类形态有新发现者，旧发现者保留 | 新判据已登记，旧三张表未动；但新发现者的**执行**无机械证明（§4） | 部分 |
| `baseline_coverage.py` 有消费者结论与退场步骤 | docstring + TEST §8.1：随步骤 9 退场，此前只作历史诊断 | PASS |
| 交付 prompt 不含 Case 单号、金样路径、期望 verdict | `test_no_fixture_or_test_path_in_the_extension`、`test_the_review_check_names_no_business_of_the_fixtures`；复审 `rg` 零命中 | PASS |

## 4. 返修（步骤 7 内补，步骤 9 切换前必须存在）

**执行证明缺失。** 步骤 9 会让 `story_reader_review` 成为 story 语义质量的唯一发现者，而现在没有任何机械核对证明 verifier 真的执行了它。批次 3 实测过整份清单一条没裁、harness 照收 PASS——同一形态会在这里重演，只是换了一个判据名。

目标形态：扩展既有的收口机制（`pre_verifier.mjs` 的必答清单 + `verifier-report.mjs` 的报告核对）覆盖 `story_reader_review`：verifier 报告里必须有该判据的结果块，且结构是 `blocking_findings` 与 `advisories` 两个列表（可为空列表，但不能缺席）；零 blocking 时须有逐章说明（overlay 文案已要求「不要只写未发现问题」），缺席即 spec post_check BLOCKER。**不核内容、不数条数**，只核「这一项被执行并按约定形态落进了报告」。

替代了什么：替代「注入了就当执行了」。结果判据：夹具里给一份没有该结果块的 verifier 报告 → BLOCKER 点名；给一份含空列表的 → 通过；给一份把它写成逐单元表的 → 点名形态不对。

## 5. advisory

- **A1 资格门没有驱动器。** TEST §9.1 的「怎么跑」是人工三步 × 14 份样本 × N 个配置。等授权恢复实跑时，复用 `verifier-smoke/run_smoke.py` 的隔离工作区与回复表模式加一个样本循环，不要临场手跑。
- **A2 severity 是 MAJOR。** framework 对 MAJOR 的 verifier FAIL 不一定阻断闭环；步骤 9 把它定为唯一发现者时要定 blocking_findings 非空是否映射为 BLOCKER（与 D2 §6 的「返修按收敛」一起定）。
- **A3 第二个 good 基底的材料是简报而非四源。** 资格夹具给 verifier 的「材料」是一页 brief，真实链路是 PRD/SR/AR/UX 四源。区分力结论对材料形态有敏感性，实跑时至少一族要在真实四源上复核。
- **A4** 12 份 bad 里 `chapter_hollow` 与 `flow_gutted` 都落在业务流程/功能章；异常与恢复、验收章没有掏空变体。当前六族够用，实跑后若这两章误判多，再补族，不预先加。

## 6. 范围与回归

- 允许范围内：overlay（Extension verifier 任务）、`fixtures/narrative-variants/**`、生成器与测试、TEST 入口、`baseline_coverage.py` docstring。
- 保护区差异：零。旧 checker、金样、Framework、真实 Case 未动。
- 未运行：资格实跑（授权暂缓）、真实 Story。

## 7. 后续

- 允许提交：已在库（`01b7e74f`）。
- 下一步：**步骤 9 前先做 §4 返修**（小改，仍归步骤 7）；步骤 9 的进入条件「步骤 7 通过」在实跑暂缓下只能是「装置通过 + 执行证明就位」，区分力结论仍挂账。

## 8. 资格实跑复审（Claude，2026-09-03 晚）

对象：`47d452d5`、`1c0ed73e` 与 STATUS「步骤 7 资格实跑」记录。**实跑产出（`qualification.json` 与各样本输出）在仓内与临时目录都找不到**，
读数只能采信记录里的表述，无法逐份复核点名——这本身是第一条问题。

### 8.1 结论

- 现有读数**不表明** verifier 任务定义或步骤 7 的装置设计有问题：deepseek 上五族里四族确证命中、good 基底最终零 blocking，
  审查者对基底挑出的问题「没有一条是误判」。它表明的是**资格测试的方法把被测模型当成了程序**，四处：
  1. **用穷举正则解析自由文本判「报没报」**，三种空结论写法各误判一轮，每次误判又触发一轮夹具修改。审查者是模型，不该让它的自然语言回复去适配解析器；该反过来——要求它在回复末尾给一个固定形态的结论块（与 framework 的 `maison-verifier-result` 同一做法），脚本只读那一块。
  2. **单次运行当结论**。同一份稿同一个问题一轮 advisory 一轮 blocking，记录自己也发现了；模型结论要按重复运行定，关键族至少两次一致才记入矩阵。
  3. **在同一个循环里既清夹具又评审查者**。四轮「跑一次改一处」把 good 基底修到它不报为止——这是拿审查者当 oracle 校准夹具，然后再拿夹具证审查者，循环自证（RC8）。good 基底该由维护者事先按材料人核定稿，运行后对审查者的每条 finding 逐条裁「成立 / 不成立」，误报率按不成立的条数算，不按「零 blocking」算。
  4. **实跑途中改了交付判据**：`spec-rules.overlay.yaml` 加了一句「依据只回显条目名称即 blocking」让 `knowledge_echo` 才点得出。改判据本身合理，但改完之前所有读数作废，须整套重跑；记录里把改前的确证读数继续当作有效。
- 另两条装置层事实：`flow_gutted` 族被换成 `image_dropped`，步骤 7 要求的是「图片**或**流程表达」，换法合规，但流程图那一侧现在没有样本；`fact_deleted` 悬空是夹具编辑区重叠，不是审查者的问题。
- 实跑没有走 framework 的 verifier 链（独立子会话、只读、`ai-prompt.md` 里与其它十项并列），而是一个主会话读 `REVIEW-TASK.md`。对「有没有区分力」这个问题它是可接受的近似，但结论不能直接外推到生产提示形态，步骤 11 的真实 Story 仍要复核。

### 8.2 要不要继续测

要，但按修正后的方法跑**一次有界的集合**，不再逐份试错：

1. 修四件事再跑：结论块固定形态；关键族两次重复；good 基底由维护者按材料人核后冻结，运行后逐条裁 finding；`image_dropped` 的插入位置挪出 `fact_deleted` 的删除区（把 `pairs.json` 各族编辑区互不相交写成自检）。
2. 只跑 `bailian-deepseek`：14 份 + 5 个 blocking 族各重复一次 = 24 次调用，按记录的 100–265 秒/份约 1～1.5 小时。`volcengine-glm-flash` 记为「本轮不具备运行资格（600 秒超时零输出）」，不再花时间；`codex-luna` 不跑。
3. 产出目录进版本管理（`test/story/design/.../artifacts/07-qualification/`），逐份输出留原文，矩阵写进本报告。
4. 跑之前不再改 overlay；跑完若要改，改完整套重跑。

拿到通过集合后步骤 9 第二段才能退场；拿不到就回开步骤 7 改任务定义，不动 checker。
