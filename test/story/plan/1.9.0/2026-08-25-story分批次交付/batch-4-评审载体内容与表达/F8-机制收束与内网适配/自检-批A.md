# 批 A 自检报告 · S1 形态判据改成每章每类

> 判据出处：`08-判据-三次.md` §零（G1–G10）与 §一（KG8T-1.1–1.28）。
> 填法纪律：逐行执行「怎么验」，贴真实输出，禁止凭记忆。
> 基线 `899bcc80`，本批改动尚未提交时跑的这些命令。

---

## 一、全局硬门

| 编号 | 结论 | 事实证据 |
|---|---|---|
| G1 单测全绿 | **达成** | `python -m pytest test/story/tests -q` → `432 passed, 38 subtests passed in 45.29s`；`python -m pytest tools/cli/tests -q` → `27 passed in 2.24s` |
| G2 失效形态 | **达成** | `python test/story/scripts/check_failure_modes.py` → `形态 73 条：FAIL 0，SKIP(能力未建) 0，PASS 73` |
| G3 金样零 FAIL | **达成** | 含在 G1 的 432 条内（`test_golden_sample.py` 全绿）。**注意口径**：金样走 `--offline`，见下方 KG8T-1.2 的判据缺陷 |
| G4 扩展阶段 | **达成** | `npx ts-node harness-runner.ts --phase extensions` → `✅ 脚本 Harness 检查通过` |
| G5 语法 | **达成** | `node --check doc/extensions/skills/story/scripts/story-build.mjs` → 无输出（每次改完都跑，共 6 次） |
| G6 反例夹具 | **达成** | 含在 G1 内；`test_negative_guards.py` 单跑 → `42 passed, 5 subtests passed` |
| G7 framework 零改动 | **达成** | `git diff 689607c7..HEAD --stat -- framework/` → 0 行 |
| G8 金样未动 | **达成** | `git diff 689607c7..HEAD --stat -- test/story/golden test/story/fixtures/golden` → 0 行 |
| G9 装置未动 | **达成** | `git diff 899bcc80..HEAD --stat -- test/story/scripts/` → 0 行 |
| G10 历史方案未被改写 | **达成** | `sha256sum -c f8-plans-v3.sha` → `00-方案.md: OK` / `01-判据.md: OK` / `02-方案-重写.md: OK` / `03-判据-重写.md: OK` / `04-方案-二次优化.md: OK` / `05-判据-二次优化.md: OK` |

---

## 二、KG8T-1.1–1.7 正推

| 编号 | 结论 | 事实证据 |
|---|---|---|
| 1.1 金样不被新判据拦 | **达成** | `test_golden_sample.py` 全绿（含在 432 内） |
| 1.2 金样逐章形态表 | **判据缺陷，已改口径** | 金样 `test/story/fixtures/golden/AR90004/AR/` 下只有 `assets/ design.md story.md`，**没有 `story-src/`**；`cmdCheck` 在 `--offline` 下 `doc = { units: [] }`，形态判据整条不跑。**这条判据写的时候假设了金样有五件台账，事实上没有。** 改由两份实跑快照产出该表，见 §四 |
| 1.3 分几张画几张 | **达成** | `test_drawn_equals_allocated_passes` PASS（3 分 3 画，零报） |
| 1.4 多画不报 | **达成** | `test_drawing_more_than_allocated_passes` PASS（1 分 3 画，零报） |
| 1.5 `covered_by` 不进分母 | **达成** | `test_covered_by_is_not_in_the_denominator` PASS（4 张里 1 `at` + 3 `covered_by`，画 1 张，零报） |
| 1.6 `material_only` 不进分母 | **达成** | `test_material_only_image_is_not_in_the_denominator` PASS（3 张里 1 `at` + 2 `material_only`，引 1 张，零报） |
| 1.7 **30 图不逼引** | **达成** | `test_thirty_images_two_drawn_rest_marked` PASS（30 个 image 单元、2 `at` + 28 `material_only`、引 2 张，「只引了」「但那一章没有图片引用」「在 story 里没有落点」三串皆不出现）。**这条此前只是源码注释里的声称，仓里从来没有这个夹具**——`grep -rn "seed_images(30)" test/story/tests` 改动前零命中 |

---

## 三、KG8T-1.8–1.15 反例与实现

| 编号 | 结论 | 事实证据 |
|---|---|---|
| 1.8 **N10 多张分到一章只画一张** | **达成** | `test_N10_four_allocated_one_drawn` PASS，`assert_check_names("的图有 4 张，那一章只画了 1 张")`；另加图片侧 `test_N10_image_side`（`的图片有 4 张，那一章只引了 1 张`） |
| 1.9 **N11 diagram 不得用 `material_only`** | **达成** | `test_N11_diagram_cannot_be_material_only` PASS，报「不是图片」并在同一行给出 `covered_by` 出路 |
| 1.10 **N12 json 围栏不算图** | **达成** | `test_N12_json_fence_is_not_a_diagram` PASS（章里只有一个 json 围栏，仍报「但那一章没有图」） |
| 1.11 原布尔语义未丢 | **达成** | `test_original_wording_when_nothing_drawn` PASS：一张没画时走原措辞「但那一章没有图」，且不出现「只画了」 |
| 1.12 图片分了没引仍拦 | **达成** | `test_N3_image_placed_in_a_chapter_that_has_no_image` PASS（未改动） |
| 1.13 图片 `material_only` 无理由仍拦 | **达成** | `test_a_reason_is_required` PASS（改判为图片：这一态已收回图片专用） |
| 1.14 反例编号连续 | **达成** | `grep -oE "def test_N[0-9]+" … \| sort -un` → `1 2 3 4 5 6 7 8 9 10 11 12` |
| 1.15 每条点名判据 | **达成** | `TheLibraryItselfIsComplete::test_every_negative_names_the_judgement` PASS（元测试已从「恰好 9 条」改成「编号集 == 1..12，一个编号可有多条」） |
| 1.16 `chapterForms` 数个数 | **达成** | `diagram` / `image` 为 `(s.text.match(...) ?? []).length`，`table` 仍是 `/^\s*\|/m.test(...)` |
| 1.17 图形围栏白名单存在 | **达成** | `story-build.mjs:336` → `const DIAGRAM_FENCE = /^[ \t]*(?:```\|~~~)[ \t]*(?:mermaid\|plantuml\|puml\|dot\|graphviz)\b/gmi;` |
| 1.18 白名单带理由 | **达成** | 该常量上方注释写明「json / yaml / text 围栏是数据与摘抄，不是图……仓里就有这样的产物（附录倾倒那份夹具里有一个 `text` 围栏）」 |
| 1.19 `formShortfall` 比数量 | **达成** | 出口条件为 `if (want > drawn) out.push({ ...item, want, drawn });` |
| 1.20 `IMAGE_KINDS` 只含图片 | **达成** | `story-build.mjs:72` → `const IMAGE_KINDS = new Set(['image']);`；另有源码级守卫 `test_the_kind_set_names_only_images` |
| 1.21 diagram 落点判收回 | **达成** | 条件为 `if (!rec?.at && !rec?.covered_by)`，文案「在 story 里没有落点——图是读者最依赖的那部分，不能只在材料里有」 |
| 1.22 **全篇总数判据不回来** | **达成** | `grep -c "数量不该少于源\|story 里只引用了"` → `0`（连注释里都不逐字复现，因为反例守卫按文本判，quote 会被当成判据还在） |
| 1.23 两处调用不变 | **达成** | `grep -c "formShortfall(doc.units"` → `2`；`grep -c "function formShortfall("` → `1` |
| 1.24 表格分支未动 | **达成** | 与 `899bcc80` 逐字比对该分支（`// 表行：` 到 `return out;`）→ `True` |

---

## 四、KG8T-1.25–1.28 回归锚

用 `<scratch>/f8r-run-evidence/` 的两份实跑快照，装成临时 project-root 后跑真 `check`。

**两处必须说明的口径**：

1. 快照只含 `AR/` 与 `spec/`，**没有 `assets/`**，所以「图片断链」条目是快照不全的产物，不是本轮引入的；
2. `car-key` 快照**缺 `story-verdicts.md`**（那一轮被 stop 时还没走到裁决），`requireLedgers` 直接拦下整个 check。为跑通锚点补了一份**空表骨架**，仅为让台账判据放行；因此该轮里与裁决内容有关的报错是桩件产物。

| 编号 | 结论 | 事实证据 |
|---|---|---|
| 1.25 **回归被拦住** | **达成** | car-key 快照跑 `check` → `89. 材料里分到「业务流程」的图有 4 张，那一章只画了 1 张——把流程图压成箭头文字算降级，读者要的是一眼看出的结构；story 自己画的那张已经覆盖了其中几张，就给那几条标 covered_by` |
| 1.26 图片侧不误伤 | **达成** | 同一份快照，图片形态欠账条数 = **0** |
| 1.27 好产物不被拦 | **达成** | auto-topup 快照，图片形态欠账 **0**、流程图形态欠账 **0** |
| 1.28 同文件重复指向 | **达成** | 行为已定为**按文件名去重后比数**，写在 `formShortfall` 注释里；`test_two_units_one_file_counts_once` PASS |

### 逐章形态表（顶替 KG8T-1.2）

`auto-topup`：

| 章 | 类 | 分配数 | 画出数 | 差 |
|---|---|---|---|---|
| 功能说明 | 图片 | 2 | 2 | 0 |
| 业务流程 | 图 | 2 | 2 | 0 |

欠账章类数：**0**

`car-key-sharing`：

| 章 | 类 | 分配数 | 画出数 | 差 |
|---|---|---|---|---|
| 功能说明 | 图片 | 4 | 4 | 0 |
| 业务流程 | 图 | 4 | 1 | **欠 3** |

欠账章类数：**1**

这张表与 `07-方案-三次.md` §2.1 的逐章核对**逐格相同**，说明新判据数出来的东西与人工核出来的一致。

---

## 五、本批改了哪些文件

| 文件 | 改了什么 |
|---|---|
| `doc/extensions/skills/story/scripts/story-build.mjs` | S1a 计数化 `chapterForms`；S1b 新增 `DIAGRAM_FENCE`；S1c `formShortfall` 比数量、图片按文件去重；S1d `formShortfallLine` 与 `audit` 输出给两个数；S1e `IMAGE_KINDS` 收回图片、diagram 落点判去掉 `material_only`、两处报错文案随范围收回；S1f 数量判据退场注释重写 |
| `test/story/tests/test_negative_guards.py` | 改判 6 条（N1/N2/N4、audit 读数、`material_only` 收回图片的两条）；新增 `FormShortfallCountsPerChapterPerKind`（6 正例 + 4 反例）与 `DiagramsHaveNoMaterialOnly`（N11 + 源码守卫）；元测试从「恰好 9 条」改到「编号集 1..12」 |

**范围核对**：`git diff 899bcc80..HEAD --name-only` 只有这两个文件（判据 KG8T-11.1 允许的七个之内）。

---

## 六、本批发现、必须带进后续批次的两件事

1. **KG8T-1.2 判据本身错**（金样没有 story-src，离线模式下形态判整条不跑）。已改由快照产出该表。**`08-判据-三次.md` 不改**——它是本轮的验收基线，错在哪要留在报告里，不是回头改判据让自己通过。
2. **源码里「30 图夹具已证」是空头支票**：改动前 `test/story/` 全域没有 30 图夹具。本批把它建出来了（`test_thirty_images_two_drawn_rest_marked`），那句话现在才成立。
