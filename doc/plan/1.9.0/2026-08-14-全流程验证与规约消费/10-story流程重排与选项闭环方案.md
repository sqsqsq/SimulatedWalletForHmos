# W6：story 流程重排（先材料后分析）+ 选项集闭环 + 测试侧修正

> **触发**：两轮实测——驱动器自动跑 `split-two-ar`（carry_all 路径）与用户手工跑
> （split 路径，同一个 AR90005）。前者验证了主链路，后者暴露了 story 本身的结构矛盾。
> **状态**：方案，待实施。

## 1. 起点：两轮实测的结论

### 1.1 自动跑（carry_all 路径）——主链路符合预期

范围定法**六层穿透，无一层走样**：

```
SR 关联行（材料）
  → 契约 positioning.scope_source=sr_related（范围＝补卡支付与制卡跟踪）
  → design.md §1.2 形态②（点名 AR90004 ＋ 写出范围来源）
  → story 05 章三层叙事（含先后依赖，从契约 depends_on 传下来）
  → spec 功能清单 F1–F7（与 carry_all 选项 label 的 7 项逐一对应，无一混入兄弟份）
  → plan 接口设计（SR 四个接口只做本 AR 那两个）
```

四道门禁全绿；spec 四件套闭环；plan 曾报 1 个 blocker（`interface_signatures_complete`）
被测模型自愈后闭环——门禁在正常工作。

**规约生效并正确应用**（本轮第二个核查目标）：

| 阶段 | 注入证据 | 消费证据 |
|---|---|---|
| spec | `reports/ai-prompt.md:1885` 含 `hook:on_context_load:extension:constraint-application.md` | spec.md **11 处编号引用**，且是设计结论形态：「新增页面与应用能力均不设 `exported: true`（对照 SEC-03/04/05）」「base 与 dark 同名成对（对照 UX-01）」「24 小时超期后删除（对照 SEC-01）」 |
| plan | `reports/ai-prompt.md:2020` 同 hook | `plan.md:269` 声明跨切面要求已落入 spec 非功能章（继承而非复述，单一落点）；**数据模型落实规约实质**——`expiresAt: number //（epoch ms，24 小时 TTL）`、`maskedCardTail: string // 脱敏卡号尾号` |

规约不只进了 prompt，还塑形了数据模型。

### 1.2 手工跑（split 路径）——暴露四个问题

| # | 问题 | 性质 |
|---|---|---|
| P1 | **流程顺序颠倒**：材料还没确认就做完了全量需求分析 | 结构矛盾 |
| P2 | **初析与关卡脱节**：初析说「不提供拆分选项」，关卡却现编三项 | 结构矛盾 |
| P3 | 材料清单列机制内文件（`AR/upstream.md`），且不说明每项是什么 | 呈现缺陷 |
| P4 | 未用 AskUserQuestion；`basis` 只记编号无语义；契约两处小缺口 | 呈现＋校验缺陷 |

## 2. P1：流程顺序颠倒

### 现状

S2 一口气写完五节初析（概览／本部件／本 AR 定位／功能清单／范围定法），S3 才问
「材料够不够」。

### 为什么错

规则自己写着「**材料不全时范围判断本身就不可靠，在一个还会变的范围上讨论怎么切，
讨论了也白讨论**」——但流程恰恰让全量分析发生在材料确认之前。材料不足时那份分析
注定作废，每轮补料都要重做一遍。

### 用户定的正确顺序

> story 应先快速进入材料清单确认，这里不做过度需求分析。待确认材料充足后，
> 进行需求粒度分析（全景＋本部件＋本 AR＋特性拆分），并给出用户看得懂的选项，
> 这样才能理解用户意图、给出正确的选择；之后就自动进入 spec 流程。

### 新链条

```
S1   init 拉材料
S2a  导入 ＋ 材料盘点（轻量：清单 ＋ 一句缺口判断，不做需求分析）
S3a  第一级：1=补充材料  2=材料充足，开始需求分析
       补料循环：放料 → 导入 → 重新盘点 → 再问（快速、廉价）
S2b  需求粒度分析（材料已确认才做）：
       ① 需求概览（全景）② 本部件视角 ③ 本 AR 定位 ④ 待实现功能清单
       ⑤ 范围定法选项（每项带人看得懂的内容）
       → 落 .positioning.json ＋ .scope-options.json
S3b  第二级：范围怎么定（选项＝契约里的，见 §3）
S3c  第三级：本 AR 承载哪份（仅选了切分维度时）
S4   范围已定 → 生成 design.md → 自动进 /spec
```

三级 gate 的语义天然对齐（第一级问材料、第二三级问范围），**分级不变**，
变的是分析从「全部前置」挪到「两级之间」。

### 轮次语义随之修正

一轮 ＝ **一次材料状态**（原为「一次初析」）：

- `cmd_round` 的轮次边界判据由「初析 sha」改为**材料指纹**（`inputs` 哈希集合，
  契约本来就每轮记录）。补料导入 → 材料变 → 新轮；材料没变 → 幂等；
- 「防伪造轮次」职责由材料指纹承接——重析的正当触发本来就是材料变化，
  这个判据比初析 sha 更贴近事实；
- `analysis` 字段保留，但允许同轮内更新（盘点版 → 完整版是同轮内的正常演进）；
- `positioning` / `scope_options` 不再要求 round 时到位，改为 S2b 完成后消费；
- `next_step` 增加 `run_analysis`：材料已确认但 positioning/scope_options 未落盘时，
  下一步是做需求粒度分析。

## 3. P2：初析与关卡脱节（核心）

### 现状证据

初析 §⑤4 写：

> **推导**：三源信号均未命中，本 AR 由上游按阶段切好后段、内部耦合成单一交付闭环，
> 未找到具名可切维度 → 推荐**按当前范围整体承载**。
> 未找到可切维度说明：本 AR 内部各功能点同属「补卡→制卡」一条用户旅程段，
> 任一子集都无法独立交付用户价值，**故不提供拆分选项**。

只列一项，**理由写得很充分，完全合规**。但关卡摆出三项：

```
1 = 按当前范围整体承载（推荐）
2 = 按业务链路切
3 = 按交付批次切
```

契约留痕 `scope_decision.options = [carry_all, 业务链路切, 交付批次切]`——
后两项是**现编的空壳**（无内容，所以用户看不懂）；用户选了「业务链路切」之后，
第三级份表同样是现编的。

### 诱因

`rules/scope_gate.md` 的三级示意写死了 `1) 整体承载 2) 按<维度>切 3) 按<另一维度>切`
三项形态——模型把示例当模板，**示例形态压过了初析结论**。
「选项按初析原样带出」只是文字约束，没有任何机械校验。

值得注意：**下游机制全对**（现编份表照样正确成形为 §1.2 拆分表、「份 2 待立项」、
依赖关系）。机制健全，唯独选项**来源**失真——这正说明问题在链路的这一环，不在别处。

### 改法：选项集机器面闭环

复用 positioning 已验证的模式（侧车 → 契约 → 消费）：

1. S2b 完成后，选项集落 `AR/story-src/.scope-options.json`：

   ```jsonc
   [{"key": "carry_all",
     "label": "按当前范围整体承载：<列功能点>",
     "recommended": true},
    {"key": "<维度名>",
     "label": "按<维度>切：<每份一句摘要，让人看得懂切完是什么样>",
     "parts": [{"seq": 1, "scope": "…", "depends_on": []}, …]}]
   ```

   消费进契约 `rounds[].scope_options`；

2. **`scope_decision` 这一级不再读 `.gate-options.json`**——`decide` 直接以契约
   `scope_options` 为 options，`chosen` 必须在其中。
   **初析只定一项，关卡就摆不出第二项**——现编空壳被结构性消灭，而不是靠文字劝阻；

3. **`split_carrier` 的 options 由脚本从选定维度的 `parts` 生成**（key＝seq），
   不读侧车、不混退回项。定案份表侧车仍允许人微调（「认可或改一两句」），
   既有「定案的必须是选中的」校验保留；

4. 用户想要初析没给的切法 → 口述修正 → 回 S2b 重做分析（补该维度、重落侧车）。
   这正是「先做完再问」的原意：分析先行，关卡只照出，不现编；

5. `material_scope` 保留 `.gate-options.json`（label 需带材料语境，值域已闭合）。

### 配套校验

- `read_positioning` 拒绝 `sr_related_ars` 含本 feature 名（字段是「同 SR 的**其它** AR」；
  实测把 AR90005 自己列了进去）；
- `post_check.mjs`：`scope_decision` 的 options 与契约 `scope_options` 一致；
  split 定案时 `scope_options` 里存在被选维度。

## 4. P3：材料清单形态

### 现状问题

```
| AR/upstream.md | 不存在 |
| ux-reference/  | 不存在 |
```

`AR/upstream.md` 是 **inbox 导入的落点产物**，不是用户提供的材料——首轮列它
（还标「不存在」）只制造困惑：用户会问「这是什么？该有吗？」。

### 改法

**只列实际存在的输入源，按来源标注，说清每项是什么**：

| 源 | 来源 | 是什么 | 状态 |
|---|---|---|---|
| `RR/prd.md`（RR90004） | 需求系统拉取 | 产品需求（业务背景与验收意图） | 已归档正文 |
| `SR/design.md`（SR90004） | 需求系统拉取 | 系统级设计（分工、接口、时序） | 已归档正文 |
| `AR/design.md` | 需求系统拉取 | 本 AR 提取件现状（可能已预填） | 空模板（无预填） |
| `inbox/交通卡补卡.docx` | 人工提供 | 待导入材料 | 待导入 |

- **机制内文件不列**（`AR/upstream.md`、`init-analysis.md`、`story-flow.json`…）；
- 人工补录与界面设计图的**有无**收进缺口判断一句话（「无人工补录材料、无界面设计图」），
  不逐行写「不存在」；
- 保留：多份材料写文件夹名 ＋ 件数不穷举；逐项标内容状态
  （已归档正文／占位件／空模板／空／无法解读）——「文件在」不等于「有内容」。

## 5. P4：呈现与契约小缺口

| 缺口 | 改法 |
|---|---|
| 未调 AskUserQuestion，只给 portable 编号 | `scope_gate.md` 每级呈现处明确：确认组件可用时**必须**用组件，同轮附 portable 编号——与 `.claude/rules/interaction-renderer.md`（BLOCKER）对齐。现状是 scope_gate.md 通篇只有 portable 示例，把模型带偏了 |
| `basis: "2"` 无语义 | 编号回复时 `--basis` 记「用户回复：2（＝按业务链路切）」——编号与语义都留住 |
| 三级示意暗示固定三项 | 改为「有几个真实维度摆几个；未找到维度时只有整体承载一项」，并写明理由：**凑数的切法比不摆更糟——那是把现编的说明书递给裁决者** |
| `sr_related_ars` 含本 AR 自己 | 见 §3 配套校验 |

## 6. 测试侧修正

| # | 改什么 | 为什么 |
|---|---|---|
| B1 | S2「内容不丢」的**术语组**降为语义复核（PENDING ＋ 输出清单），机械层只判精确标识（编号／技术契约标识） | `assert_story.py:144` 用纯子串包含判落点，与 `rules.md` 第 6 条「**可换措辞**，但一条都不能少」直接矛盾。实测 story 全篇以「提示」承载轻提示交互（6 处），`Toast` 换了措辞——内容没丢，判据抓不到。编号不会换措辞，子串对它们成立；术语天然会换，机械层判不了 |
| B2 | S6「不含议程」豁免含《决策与评审记录》前缀的行 | `AGENDA_CUE` 里「建议」是裸词，命中的是 `story.md:57`「《决策与评审记录》——…就…**给出建议**」。这句在描述 review 文档做了什么（review 渲染器里就有「当前建议」字段），而 `rules.md` 第 7 条**要求**用这个前缀引用决策件——**规范要求的引用形态撞上了裸词检查**。结构化豁免，同 `lint-rules.mjs` 的 `EXEMPT_LINE_PATTERNS` 机制 |
| B3 | P-06 判据修正 | 我此前把**模块 scope**（framework 红线 3，管模块改不改）与 **AR 范围**（story 范围定法，管功能归谁）两个正交维度混为一谈。兄弟 AR 的功能不是模块，不该要求 `out_of_scope_modules.rationale` 写「归属 ARxxxx」。改为「功能清单不含兄弟份；凡提到范围外内容处点名承接方单号或『待立项』（落点不限定）」——实测归属信息的自然落点是术语表、场景表、异常表 |
| B4 | pytest 并行化 | 367 个用例串行约 5 分钟，慢在子进程型（`story_flow.py` 子进程调用上百次、node hook 调用）。各用例用 `tempfile.mkdtemp()` 自建目录、其余只读仓库文件，**天然可并行**。加 `pytest-xdist`，`-n auto`。实施前扫一遍确认无用例写仓库真实路径 |
| B5 | 阶段槽冲突定界 ＋ 文档化 | 根因：harness 全局槽是单会话设计——被测 CLI 写的 state 无 `session_id`，观测者会话 stop 时 hook 在 grace 期内把它**认领**为自己的（`check-phase-completion.mjs` 的 fresh-unstamped 分支），此后按当前会话未闭环 block。双会话拓扑下必然误判。`MAISON_GOAL_HEADLESS=1` 能免写但会把被测 run 判成 goal 上下文、owner 变 process（**改变被测行为**），不可用。作为 framework 改进建议记录；测试侧维持既有 snapshot/restore ＋ 被拦即 `--clear-state` |

`gate-pause` 自动化用例**暂缓**——用户手工测试已实际验证「关卡真停 ＋ 人选择 ＋
`by:"human"` 落盘」这条链（虽同时暴露了 P2，但停等机制本身工作正常）。

## 7. 涉及文件

| 文件 | 改动 |
|---|---|
| `doc/extensions/skills/story/scripts/story_flow.py` | 轮次语义（材料指纹）、`next_step` 增 `run_analysis`、scope_options 侧车与消费、scope_decision／split_carrier 选项来源、`sr_related_ars` 校验 |
| `doc/extensions/skills/story/rules/init_analysis.md` | 两段式结构（盘点／分析）、材料清单形态、scope-options 侧车说明 |
| `doc/extensions/skills/story/rules/scope_gate.md` | 新顺序、选项来源、AskUserQuestion 呈现、示意去固定三项、basis 语义 |
| `doc/extensions/skills/story/SKILL.md` | 链条表与「先做完再问」表述同步 |
| `doc/extensions/hooks/spec/post_check.mjs` | scope_options 相关契约校验 |
| `test/story/scripts/assert_story.py` | B1、B2 |
| `test/story/truth/facts/split-two-ar.yaml` | B3 |
| `test/story/tests/`、依赖声明 | B4（xdist）＋ 新契约行为单测 |
| `test/story/TEST.md` | B5 |
| `output/story/evaluation/split-two-ar.md` | 两轮结论收尾 |

## 8. 不做

- `framework/` 与 `.claude/hooks/` 不动（P4 的呈现问题靠 skill 规则与 interaction-renderer
  对齐解决，不改 hook）；
- 不提交。

## 9. 验证

1. `pytest test/story/tests/` 串行跑一次确认基线（367 passed），再 `-n auto` 验证结果一致；
2. 契约冒烟四条路径：材料不足补料循环（轻量盘点、不做分析）／ carry_all ／
   真实维度切分 ／ **初析仅一项时关卡摆不出第二项**（P2 的回归锁）；
3. 复跑 `assert_story.py` 两份既有产物：S2 → 精确标识 PASS ＋ 术语 PENDING、S6 → PASS；
4. 重跑一次 story 阶段（手工或驱动器）确认：先材料清单后需求分析、选项与初析一致、
   AskUserQuestion 呈现、`basis` 带语义。
