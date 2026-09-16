# 会议材料 · 读会作业书

> `status` 的 next 是 `read_meeting` 或 `refresh_meeting` 时读这一页。导入已经把每一版会议材料
> 留在 `AR/story-src/meetings/<主名>/<版本>/`：`original.docx` 是原件，`raw.md` 是转换出来的文本。
> **内容由你理解**——谁在发言、哪一段是议题、哪句话是结论，脚本不替你划。
> 你产出三份：纠偏差异、话题索引、会议结论。写完跑 `status`，自检不过它会点名。

## 一、这份材料是什么

一场围绕需求的讨论记录。它比需求文档新，是需求变化的唯一记录；但它是讨论态：有转写错误、
有说了又改的话、有没收敛的分歧、有跳跃。一个议题通常对应一个需求，一场会常覆盖多个需求。
**它是证据，不是定论。**

要做的是找出会议对**本需求**输入的实际改变，写成会议结论，同时让人看出文档哪里过期。
不复述会议、不整理纪要、不改 RR / SR 正文，也不直接改 spec。

`raw.md` 是**引用的基底**：所有引用都写它的行号，1 起、首尾包含。读它时记下行号
（`status` 给的路径直接可读）。`raw.md` 与 `original.docx` 都不要改。

## 二、纠偏：只交差异（`corrections.json`，与 raw.md 同目录）

先读本需求已有的材料（RR、SR、AR、需求分析），再纠正转写里的字面错误，让讨论可读。
依据只来自四处：会议材料里的参会人、本需求材料、项目事实、术语表。

| 可以改 | 不可以 |
|---|---|
| 人名、术语、拼音、错别字的字面，无论它在行首的抬头里还是正文里 | 删行、加行、并行、拆行、调顺序、摘要、消解矛盾、改意思；源外拿不准的字照原样留着 |

```json
[{"line": 12, "original": "这一行在 raw.md 里的全文", "corrected": "纠偏后的这一行全文", "basis": "依据哪一条"}]
```

- `line` 是 `raw.md` 的物理行号；一行至多一条，同一行的几处改动写进同一条；
- `original` 与那一行逐字相同，`corrected` 里不能有换行，非空行不能改成空行；
- 没有要改的写 `[]`。

写完出阅读件（**不要手写 `evidence.md`**）：

```
python doc/extensions/skills/story/scripts/core/story_flow.py meeting-refresh --feature <AR> --meeting <主名>@<sha8>
```

它按差异生成 `evidence.md`：行号与 `raw.md` 一一对应，没改的行逐字保留。行号错、原文对不上、
重复行、缺依据会一次全部报出来，改 `corrections.json` 再跑。

## 三、切话题：`topics.json`（同目录）

只做索引，判断不写在这里：

```json
[{"id": "T1", "title": "议题 · 话题", "evidence": [{"start": 12, "end": 15}]}]
```

一个范围可以属于多个话题，一个话题可以有几段不连续的范围；寒暄、重复、与任何需求无关的段落
可以不引用——不要求覆盖每一行，也不要为了覆盖而编话题。

## 四、会议结论：`AR/story-src/meeting-notes.json`

**先整体、后逐条**：带着对需求的理解通读整场，形成每个话题「最后定了什么、中间怎么变、
哪里没收敛」的判断，再对照文档定位每一处改变落在哪份文档的哪一段、是增强、修正还是裁剪。
不逐句扫描。

**归属**：判得准属于本需求的直接取（`ours`）；判得准不属于的写 `not_ours`，只记不消费；
判不准的写 `unclear`，一定问人。

**三个尺度**：

- 会上明确收口的，你自己定为结论——判据是记录里收口的那句话，引得出来；没有那句话的一律
  记为遗留问题，不替人定；
- 说话人自己改口的，按后说的算；
- 文档与会议冲突时以会议为准写进变化，但它属于修正，要问人。

一份文件，每场会的每个版本一节；`source` 与 `source_sha` 照抄那一版 `source.json` 的
`file` 与 `sha256`：

```json
{"meetings": [{
  "source": "xxx.docx", "source_sha": "…", "title": "你读出的会名", "date": "你读出的时间",
  "attendee_roles": [{"name": "张三", "role": "产品"}],
  "topics": [{
    "id": "T3", "ownership": "ours | not_ours | unclear",
    "changes": [{"id": "C1", "kind": "add | remove | modify", "doc": "SR/design.md", "section": "§3.2",
                 "before": "…", "after": "…", "impact": "…", "evidence": [{"start": 12, "end": 13}]}],
    "conclusion": {"text": "会上定了什么", "scope": "适用到哪", "evidence": [{"start": 15, "end": 15}]},
    "open_points": [{"id": "O1", "what": "还缺什么决定或事实", "impact": "…", "needs": "谁来定",
                     "suggestion": "（你的建议）", "evidence": [{"start": 18, "end": 19}]}],
    "ask": true, "ask_reason": "unclear_ownership | unresolved | transcript_doubt | high_impact | overturns",
    "overturns": "xxx.docx@a1b2c3d4/T1", "recommend": "opt_a",
    "options": [
      {"key": "opt_a", "label": "按会上定的改 SR §3.2，阈值取 5",
       "effect": {"ownership": "ours", "apply_changes": ["C1"],
                  "add_changes": [{"kind": "modify", "doc": "SR/design.md", "section": "§3.2", "before": "阈值未定",
                                   "after": "阈值 5", "impact": "验收的数值", "resolves": "O1"}],
                  "supersedes": ["xxx.docx@a1b2c3d4/T1"]}},
      {"key": "opt_b", "label": "维持文档口径，阈值仍待产品定",
       "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [], "supersedes": [],
                  "keep_open": ["O1"]}}]
  }]
}]}
```

- `topics.json` 登记的每个话题在这里都要有一条，编号对同一批；一个话题可以同时有变化与遗留，
  也可以只有结论没有变化；
- `conclusion` 与每条 `changes` 都带 `evidence`：本版本 `raw.md` 的行范围；遗留有原话就一并给；
- **值得问的才问**（`ask: true`，并写明 `ask_reason`）：归属判不准的（`unclear_ownership`）、
  没收敛而影响本需求的（`unresolved`）、影响结论的转写存疑（`transcript_doubt`）、
  改动范围/接口/已归档文档口径的高影响修正（`high_impact`）、推翻前面已确认决定的（`overturns`）。
  每条带 `recommend` 与至少两个选项；
- **每个选项自带选完的结果** `effect`：归属定成什么；`apply_changes` 会上已定的哪几条变化生效；
  `add_changes` 人补定的决定落到需求哪里（与 changes 同形，不带 evidence，`resolves` 指向本话题的
  遗留）；`supersedes` 替代哪些旧决定（可以为空）；`keep_open` 明确保留哪些遗留。同一个遗留
  不能既 `resolves` 又 `keep_open`。脚本不读 label，只按人选的 key 取 effect；
- 会上达成的写进 `changes`；人后来定的只写在选项的 `add_changes` 里，不写成会上已定；
- **没有变化不等于已经收敛**：没定的事写进 `open_points`，它会跟着话题一起传到下游。

## 五、摆给人那一轮

`status` 给出 `await_gate:meeting` 时，与第一级材料关卡一起摆给人，不另停一次。
`status` 的 `meetings` 已经把全部版本与话题逐条列好（归属、变化、原结论、遗留、待裁决项与
推荐选项），你不必再从文件里抄一遍；你要补的是：

- 每个待裁决话题：推荐哪一项、为什么，选了各会怎样；
- 你提出的参会人角色；
- 摆之前回 `raw.md` 自查一遍：话题有没有漏、关键变化的原话依据指得对不对、遗留与归属跟
  已有决定有没有冲突。

人一轮答完。先逐条记会议话题：

```
python doc/extensions/skills/story/scripts/core/story_flow.py decide --feature <AR> --gate meeting --meeting <主名>@<版本> --item <话题 id> --chosen <key> --basis "<人的原话>"
```

再照 `rules/init_analysis.md` 记第一级材料关卡。人对第一级表态，就是对摆出的整体的确认：
没有逐条问的条目从这一刻生效。之后 `AR/story-src/doc-refresh.md` 由脚本写出——采纳的变化、
仍未决、会议原结论及采纳情况三段，提取稿据它修正（`rules/ar_design_init.md`），
它也是交给人的文档刷新清单。需求分析第 ⑥ 节按话题登记会议（`rules/init_analysis.md`）。

## 六、之后再来会议

一场会一轮：新会议、或同名 docx 换了内容的新版本导入后开新一轮；旧版本的原文、结论与人的
裁决照旧可查、照旧有效。

读新会议时先取 `doc-refresh.md` 里已经生效的结果与它们的来源，再判断这一场是补充、修正还是
冲突：**不预设会议一定比文档新，也不按文件名或时间自动覆盖**。要推翻旧决定就写 `overturns`
并问人，人选的那个选项的 `supersedes` 决定旧决定是否失效；先后说不清或语义对不上的，
保留成待裁决，不自己定。收口之后才到的会议，`status` 会让你先 `reopen`。
