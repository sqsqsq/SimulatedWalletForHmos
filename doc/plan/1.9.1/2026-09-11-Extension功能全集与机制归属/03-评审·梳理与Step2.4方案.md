# 评审 · 旧机制梳理、Step2.4 方案与 B5 现状

> 2026-09-11。评审对象：本目录 00/01/02/FEATURES、[Step2.4 及五份分册](../2026-09-07-新需求四项/steps/02.4-旧机制退场清理.md)、B5 四次提交（`fb23378a`…`57ad3fdf`）。基线 `d36edb70`。
> 评审方法：R01–R23 引用的每个符号与行号逐一在 HEAD 上核；四道门在 HEAD 重跑一次。本评审不改方案、不提交。

## 1. 结论

- **梳理成立**。R01–R23 引用的符号与行号全部命中；H01–H24 的替换史与我在前一轮用 `git log -S` 独立查到的一致（判据数 22→18→15→19、`d78b69e0` 一次删五条、投影早于 2.3 存在）。「不能把全部增长归给 2.3、也不能说旧机制从不退场」这个归因是对的。
- **Step2.4 可以进入实施，先补下面 §2 的六处**。都是分册里已经在改的位置漏了同一处的兄弟，没有一处要求改方向。
- **B5 不需要单独返修**。四道门在 HEAD 仍绿；留下的都是零散残料，并进 Step2.4 的 R01/R18 即可（§3）。
- 规模预期：方案 §7 写明估计净减 150–250 行，不是上千行。梳理给出的原因是：成整块系统的旧机制（逐单元裁决、冻结账本、发布器、旧 adapt 主干）确实退了，剩下的增长是 2.3 的新职责（T13）。这个结论与我前一轮三次扫描（死符号 0、孤儿文件 0、多代并存 0）互相印证。

## 2. Step2.4 分册要补的六处

### 2.1 编排协议有读者没有生产者（进 02.4-02，R09 之前裁定）

`story-template.md` 的 JSON 里，`sections[].structures` / `sections[].children` / `sections[].related` / `source_changes[].replaced_by` 四个键被 17 处代码消费（`story-build.mjs:3156/3294/3513`，`story-sources.mjs:361/401-438/504/709/741`，`reader-review-task.mjs:57/66`），但：

- `templateSkeleton`（`story-build.mjs:757-785`）起头只写 `id / sections[{key,title,content,form,sources}] / source_changes: []`，四个键一个不出现；
- 作者面零说明：`SKILL.md`、六份 `phases/*.md`、六份 `rules/*.md`、六份 `hooks/*/author.md`、章节合同、任务包正文里都没有这四个词；`story-write.md:101` 说「已声明结构…变了，同步相应编排」，却没有一处说怎么声明；
- 唯一写了这套形状的是设计稿 `02.3-02`（20 处），它不交付给作者。

所以 F2.4.2「脚本落实已声明结构」与 M14 的 `template.structures` 分支，只有读过设计稿的人才走得到。R09 现在要合并的是这套「半份没人会写」协议的两份解析器。**先定一件事**：这四个键要么在唯一的生成处（`renderTemplate` 的头部说明，它是脚本生成的，天然单源）写清楚形状与用途，要么退出。02.3 既然要「已声明结构」，应当是前者；那么 R21 §3.2 的「必要结构的读取位置」就落实为「起头文件自己说明这四个键」，不另开文档。

### 2.2 图类型的作者说明与检查不一致（并入 R02，同一张表）

`story-write.md:307` 教 `stateDiagram`、`:308` 教 `erDiagram`；`story-sources.mjs:521` 的 `DIAGRAM_TYPES` 只认 `sequenceDiagram / flowchart / stateDiagram-v2`，`declarationProblems`（`:537`）对其它类型报「不在支持之列」。R02 改的正是这张表的 `:306-328`，顺手把「能声明成结构的只有三种、其余放 form 里说」写进去，与 `:521` 的注释同口径。

### 2.3 验收编号形态两头对不上（并入 R19，同一段代码）

`hooks/spec/author.mjs:128` 给作者的最小样例是 `id: AC-K1`；`hooks/ut/post_check.mjs:32,52` 与 `hooks/testing/post_check.mjs:51` 找覆盖证据只认 `/\b(?:AC|BD)-(?:G\d+|\d+)\b/`。按样例写的 `AC-K1` 永远匹配不到，于是「义务 X 的验收条目 AC-K1 在 UT 侧找不到覆盖证据」必报。R19 重写的就是这两个消费者，同一步把编号形态定成一种（样例改成 `AC-<n>`，或正则放开一位字母），并加一条正例测试。

### 2.4 只读附录比对在哪里有区分力（R07 合同要写明）

`story_flow.py story` 连跑 project → number → build → check；`cmdProject` 遇手改即 `fail`（`story-build.mjs:2846-2851`），否则重写机器区。所以在这条链里 check 的「实际区块 = 当前投影」恒成立。只读比对真正有用的是**单独 `check` 与 `check --deliver`**（登记后 Spec §9 或 knowledge-use 变了）。02.4-03 §4 的「Spec 更新都被只读 check 识别」要写成「在 `--deliver` / 单独 check 下识别」，否则执行者会写一条经 `story` 入口必绿的测试。⑫b 今天直接对 spec §9 表比对，能抓「投影自己丢行」，02.4-03 §3.1 末段「测试期望独立」保住了这一点，保留。

### 2.5 R18 清单再加三处

| 位置 | 现状 | 来历 |
|---|---|---|
| `story-build.mjs:1871` | 报错说「质量与验收」章，章名已是「验收」（查找按 `includes('验收')`，只是文案旧） | B5.1 A 类漏网 |
| `story-build.mjs:2956` | `at === '*' ? '每个小节'` 分支 | B5.4 C17 删了 slots 键 `*`，三元式没跟着删 |
| `story-build.mjs:1468` `DECISION_SHAPE` | 「骨架由 `story-build init` 生成」 | 随 R01 退；02.4-01 没点名，B5.4 交回点了 |

另外 `contracts.mjs:167-174` 那段「两处覆盖面不同是有意的…合并会放宽」是 B5.3 B14 写的，R19 落地后即失真，02.4-04 要一并改。

### 2.6 R01 的测试面

`init_audit()` 在 `test_story_build.py` 被 31 处调用，另有 7 处直接 `run_build("init")` 分布在 `test_story_build.py` 与 `test_negative_guards.py`。02.4-01 §3.3 只点了前一个文件，把后一个补上。

## 3. B5 现状与残料

在 HEAD 重跑：`pytest test/story/tests -n auto --dist loadscope` 944 passed / 6 skipped / 265 subtests；`check_failure_modes.py` 70 条 FAIL 0（Windows 下要 `PYTHONIOENCODING=utf-8`，否则打印阶段抛 gbk 编码错，不是判据问题）。adapt-scan 与 framework 两门本次未重跑，B5 收尾记录为通过。

逐次核对 B5 四次提交，没有要撤销的改动。留下的残料都已列进 §2.5，归 Step2.4 一并清：

- B5.2 B3 删 `form.note`：对照删掉的十段与合同 `questions`，控制对象/存量/在途/恢复、验收编号逐条、受限与异常分开这些读者目标都还在 `questions` 里；丢的只是「不可逆要说明白」「每项开关要有依据」两句。不是误删，但删掉了作者侧唯一一份同义送达，`questions` 现在只有 `reader-review-task.mjs:180` 渲染给审查端（`story-write.md` / `spec.md` / `story-build.mjs` / `author.mjs` 零处提到 questions）。R21 是正确的补法，不回滚 B3。
- B5.3 B14 保留两套验收读法：裁定不算错，但它守着的 `knowledgeCriteria` 本身有 D01 的覆盖丢失（`contracts.mjs:179` `out.set(rule, c)`）。R19 处理。
- B5.4 C6 删逐单元表哨兵、B18 删 `archived` 状态：梳理 H08 与本评审都接受，不恢复。

## 4. 已核实、方案无需再动的点

R03（`SKILL.md:137`「连续三次」）、R04（`:64` 把 S5 放进段内授权，与 `:30/:32/:74/:108`「止于交付门」冲突）、R05（`:154` check 在取作者要求之前）、R06（`ut/author.md:43`、`ut/post_check.mjs:92`）、R08（`spec_stage_step` 五分支在，`cmdPrepare` 确实没有 knowledge-use 缺件分支，先补后删的顺序对）、R11（`story_image_dir` 相对 story.md 是 `AR/assets`，而导入抽图写的是 `<feature>/assets/<源文档名>/`，两者不是一个目录，`AR/assets` 无生产者）、R13（⓪a `:1806-1809` 把 required 缺失也只 `notes.push`，`:1805` 注释「必备来源缺了拦」已经不成立）、R16（`:135-158` includes 判真假）、R17、R20（overlay `story_reader_review` 已含次序与结论分类；任务书六问里 §10 落点与上游路径两条 overlay 没有，其余重复）、R22（代码零处消费 `project_knowledge`）、R23（与 `coding/author.md:15,25` 冲突）——与分册所述一致。

`test/story/AGENTS.md` 未提交的那一行链到 `design/`（`.gitignore:97` 忽略，0 个跟踪文件）。`AGENTS.md:13` 与 `EVOLUTION.md` 早已这样链，是既有做法；02.4-05 第 4 步把三份 FEATURE 移出 `design/` 后此链要改指新位置。

## 5. 复核（11:08 版）

六处都已并入分册与 02 退出范围，责任分配未变。对新增内容再核一遍代码：

- 02.4-02 §3.0 字段表的形状与 `story-sources.mjs` 一致：`flatSections`（`:356-366`）只下探一层 children；`declarationProblems`（`:527-548`）认 table/columns、diagram/type、image/image+caption 并对索引 images 核；`language` 可省，默认 mermaid（`:565/:617`）；`relatedTargets` 与 `templateReadable` 读的正是 `{section, use}` 且要求指向已有项（`:504-508`、`:709-713`）；`replaced_by` 校验在 `:425-438`。头部用 `text` 围栏不会被 `readTemplate` 的 ```` ```json ```` 正则当成第二个编排块。
- 02.4-05 §3.1 点名的 `requiredShapes` 就是 `:2952` 那个函数，`at === '*'` 在 `:2956`。
- 02.4-03 §3.1 与 02.4-04 §3.2 的表述与 §2.3、§2.4 所核事实一致。

可以进入实施。
