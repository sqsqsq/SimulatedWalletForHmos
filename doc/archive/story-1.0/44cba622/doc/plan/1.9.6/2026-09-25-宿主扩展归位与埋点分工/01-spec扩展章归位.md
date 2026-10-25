# 01 spec 扩展章归位

前置与决定见[总览](00-总览.md)。本分册只改位置与编号；埋点表达见 03。行号以 2e429459 为准。

## 1. 编号映射

| 旧 | 新 |
|---|---|
| `## 9. 技术契约` | `### 9.1 技术契约`（挂在 `## 9. 宿主扩展治理项` 下） |
| `### 9.1 端云接口` … `### 9.5 依赖变更` | `#### 9.1.1` … `#### 9.1.5` |
| `### 9.4 埋点` | `#### 9.1.4 埋点` |
| 埋点下的指标 `####` | `#####` |
| `## 10. 规约约束要求` | `### 9.2 规约约束要求` |
| `## 11. 设计模式候选登记` | `### 9.3 设计模式候选登记` |
| 「宿主扩展治理项」一句套话 | `## 9. 宿主扩展治理项` + 锚点表 |
| `## 附录`（位置不定） | `## 附录`，全文最后 |

文字里的引用一律跟着改：`§9` 改为 `§9.1`，`§9.x` 改为 `§9.1.x`，`§9.4` 改为 `§9.1.4`，`§10` 改为 `§9.2`，`§11` 改为 `§9.3`。「§9 · <名字>」这类落点写法改为「§9.1 · <名字>」。

## 2. 锚点章

锚点保留 framework 模板的表头「扩展项 / 是否涉及 / 宿主模板或检查来源」，列名改为「承载位置」，逐行写：

| 扩展项 | 是否涉及 | 承载位置 |
|---|---|---|
| 技术契约 | 是（走 /story） | 9.1 |
| 规约约束要求 | 是 | 9.2 |
| 设计模式候选登记 | 是 | 9.3 |
| 流程性事项（排期、翻译、联调等） | 本需求实际涉及的写「是」 | 《决策与评审记录》对应议题 |

锚点表按本需求实际写。不走 /story 的需求，技术契约一行写「否」。

## 3. 改动清单

### 3.1 解析：按名字定位，层级取相对值

原则：按名字找章，子节取「比它低一级」的标题；层级一律由所找到的父标题推出。

| 位置 | 现状 | 改为 |
|---|---|---|
| `hooks/shared/stat-points.mjs:16–19, 39, 42` `section` / `specStatPoints` | 埋点只认 H3，指标只认 H4 | 按名字找「埋点」，不限层级（取技术契约之下的那一个）；指标 = 埋点层级 +1 |
| `hooks/spec/post_check.mjs:359–364` `indicatorShape` | `/^####\s/` 判指标，调用时自拼 `'### 埋点'` | 由调用方传入埋点层级，指标层级 = 埋点 +1；拼头改为按实际层级 |
| `hooks/spec/post_check.mjs:51–53` `findHeading` | 只找 H2–H4 | 改为 H2–H5 或不限层级（技术契约 H3、9.1.x H4 都在范围内） |
| `hooks/spec/post_check.mjs:377–379, 424–430` `SPEC_EXT_SECTIONS` 与「缺少宿主扩展章节」 | `ch: '9 技术契约'`；提示「须在验收标准之后追加」 | `ch: '9.1 技术契约'`；提示「写在『9. 宿主扩展治理项』下」 |
| `hooks/spec/post_check.mjs:173–190` 独立成节 | 按名字找，范围来自 `headingEnd` | 不变（名字不变，范围照样截在下一个同级标题） |
| 新增章序检查（`hooks/spec/post_check.mjs`） | 无 | 核：9.1、9.2、9.3 挂在「宿主扩展治理项」下；附录是最后一个二级章；锚点在 §8 之后 |
| `skills/story/scripts/core/story/appendix.mjs:82–89, 135, 227–264` `specSection` / `specHeading` / `wholeSection` | 只看 2–3 级；`^###\s*9\.x` | 按合同给的编号找，不限层级；`wholeSection` 按源节层级算降级幅度 |
| `skills/story/contracts/story-chapters.json:165–171` 附录投影源 | `from: "9.1"…"9.5"` | `from: "9.1.1"…"9.1.5"`；150 行 boundary 里「真源归 spec 第 9 节」改为「真源归 spec 9.1」 |
| `hooks/shared/knowledge-use/projection.mjs:143, 166–175` 生成区 | `/^#{2,3}\s/` 加章名 | 不限层级（改后 9.2/9.3 是 H3，仍可用；按原则去掉绝对层级） |
| `hooks/shared/knowledge-use/validation.mjs:42–49` `contractNames` | `/^#{2,4}\s+.*技术契约/` | 起点按名字找、不限层级；结束规则不变 |
| `hooks/shared/chapters.mjs:58–63, 108–124` 章号核对 | 模板只取 H2 当主章 | 扩展模板的主章改为「9. 宿主扩展治理项」（H2），子节 9.1–9.3 按前缀核；模板注释里的伪标题（83–90 行）改为不以 `#` 起头，免得被当成模板章 |
| `skills/story/scripts/core/story/images.mjs:27` | 用 2–4 级标题定图的「§节」身份 | 取到 5 级 |
| `test/story/scripts/check_failure_modes.py:2474–2485` `adjudication_keys` | `^#{2,4}` 加「规约约束要求」 | 不限层级 |

### 3.2 写给模型的文字

- `skills/story/templates/spec-sections.md`：
  - 整份按新结构重写：「## 9. 宿主扩展治理项」加锚点表、9.1 与 9.1.1–9.1.5、9.2、9.3；
  - 头注释写明「写在 §8 之后，附录之前；附录是全文最后一章」；
  - 12、41、42、48 行里写死的 H4 说法改为「埋点下一级」，具体写法见 03；
  - 83–90 行的「宿主扩展治理项只写一句索引」退出。
- `skills/story/phases/spec.md`：
  - 102 行改为「§8 之后是『9. 宿主扩展治理项』，技术契约、规约约束要求、设计模式候选是它的 9.1–9.3」；
  - 107 行「按流程用 H4」改为按指标（见 03）；
  - 122 行与 5、15、61、99 行按编号映射改。
- `hooks/spec/author.md`：
  - 23 行（H4）按 03 改；
  - 54 行改为「扩展内容是『9. 宿主扩展治理项』的子节，号照 spec-sections.md」；
  - 11、29、32 行按编号映射改。
- `hooks/spec/author.mjs` 第 5 节（377–389 行）：「§9.4」改为「§9.1.4」，层级说法按 03 改。
- `hooks/spec/post_check.mjs` 的提示语：348、361、364、424、427 行。
- 只按编号引用的文字，逐处按映射改：
  - `rules/spec-rules.overlay.yaml`：10、13、52、56、60、82、88、93、169 行；
  - `rules/plan-rules.overlay.yaml`：18、24 行；
  - `templates/plan-sections.md`：13、32、108、134 行；
  - `hooks/plan/author.md`：11、13、43、58 行；
  - `phases/story-write.md`：93、270–271 行；
  - `reference/evidence-rules.md`：3、5、25、67 行；
  - `rules/ar_design_init.md`：123–132、142、147 行；
  - `hooks/shared/knowledge-use/document.mjs`：5、68、120、125、173 行；
  - `hooks/shared/knowledge-use.mjs`：8、13、67 行；
  - `hooks/shared/knowledge-use/validation.mjs`：23–31、194–215 行；
  - `hooks/shared/knowledge-use/projection.mjs:40`；
  - `hooks/shared/pre_verifier.mjs:62、128`；
  - `skills/story/scripts/core/flow/routing.py`：118、153 行；
  - `skills/story/scripts/core/flow/lifecycle.py:76`；
  - `skills/story/scripts/core/flow/inputs.py:400`；
  - `skills/story/scripts/core/story-build.mjs`：24、97 行；
  - `skills/story/scripts/core/story/appendix.mjs`：308、314、454、480 行；
  - `skills/story/contracts/README.md:32`。
- `hooks/plan/post_check.mjs:451`「指标 H4」按 03 改。

### 3.3 测试与夹具

- 夹具（内嵌 spec 结构的），改为新结构：
  - `fixtures/failure-modes/` 下 R01、R02、S05、S06、S07、S10、S11、S15、S16、S17、S18、S19、P16、W01 的 good/bad；
  - `fixtures/golden/AR90004/spec/spec.md`、`fixtures/real-run/AR90006/spec/spec.md`、`fixtures/content-baseline/{AR90004,AR90006,ISSUE-410}/spec/spec.md`。
- 锁哈希的夹具：重锁 `test_golden_sample.py:59`、`test_content_baseline.py:25,30,35` 的哈希。
- 内嵌 spec 的测试：
  - `test_indicator_reporting.py`：`SPEC` 常量、按 `### 9.4 埋点` 与 `## 10.` 切分的各处；
  - `test_knowledge_use.py` 的 `SPEC_HEAD`；
  - `test_neutral_knowledge.py` 的 `SPEC_HEAD`（`test_knowledge_protocol`、`test_gate_groups`、`test_evidence_delivery` 共用）；
  - `test_gate_groups.py` 的 `drop_heading`；
  - `test_author_task_package.py`：674–686、976 行；
  - `test_image_registration.py:39`；
  - `test_story_build.py`：投影后的 story 层级断言（464–509 行）随 03 的层级再核；
  - `test_spec_contract_section.py`；
  - `test_chapter_numbers.py:75–79`。
- 新增用例：
  - 章序：附录不在最后、9.x 不在锚点下，都报出；
  - 旧结构（`## 9. 技术契约` 二级章）被拒，提示写到锚点下；
  - `stat-points` 在任意合法层级下都认得出埋点与指标。
- `test_plan_pattern_crosscheck.py` 的 `ARCHIVE` 路径指向不存在的目录，整类一直被跳过。本次一并修正路径或退出这条用例，退出要说明理由。

## 4. 失败处理

- 找不到「宿主扩展治理项」：报「缺『9. 宿主扩展治理项』章：扩展内容写在它下面」。
- 9.1–9.3 写成二级章，或挂在别处：按章序检查报出，并给出正确位置。
- 不走 /story 的需求没有 9.1：只核 9.2、9.3 与锚点；现有的 SKIP 规则不变。
