# 会议转写 · 读会作业书

> `status` 的 next 是 `read_meeting` 时读这一页。导入已经把会议 docx 解析成
> `AR/story-src/meetings/<主名>/<版本>/transcript.json`（发言逐条编号，全场唯一）。
> 你产出三份：纠偏证据、话题索引、会议结论。写完跑 `status`：自检不过它会点名，过了就进材料关卡那一轮。

## 一、这份材料是什么

一场围绕需求的讨论记录。它比需求文档新，是需求变化的唯一记录；但它是讨论态：有转写错误、有说了又改的话、
有没收敛的分歧、有跳跃。一个议题对应一个需求，一场会通常覆盖多个需求。**它是证据，不是定论。**

要做的是找出会议对**本需求**输入的实际改变，写成会议结论，同时让人看出文档哪里过期。
不复述会议、不整理纪要、不改 RR / SR 正文，也不直接改 spec。

## 二、先纠偏：`evidence.json`（与 transcript 同目录）

先读本需求已有的材料（RR、SR、AR、需求分析），再纠正转写里的字面错误，让讨论可读。
依据只来自四处：参会人名单、本需求材料、项目事实、术语表。

| 可以改 | 不可以 |
|---|---|
| 人名、术语、拼音、错别字的字面 | 删发言、合并、摘要、消解矛盾、调顺序、改意思；源外拿不准的字照原样留着 |

形状与 `transcript.json` 相同，发言文本换成纠偏后的，另加两项：

- `attendees`：`[{"name": "张三", "role": "产品", "proposed": true}]`——角色由你提出，人在关卡那一轮确认；
- `corrections`：`[{"speech": "S12", "original": "原文片段", "corrected": "改成", "basis": "依据哪一条"}]`。

**每一处改动都要留痕**：脚本按 `corrections` 把原文替换一遍再与你的文本逐字比，对不上的就是没登记的改动。

## 三、切话题：`topics.json`（同目录）

只做索引：`[{"id": "T1", "title": "议题 · 话题", "speeches": ["S3", "S4"]}]`。发言原文一字不改，判断不写在这里。

## 四、会议结论：`AR/story-src/meeting-notes.json`

**先整体、后逐条**：带着对需求的理解通读整场，形成每个话题「最后定了什么、中间怎么变、哪里没收敛」的判断，
再对照文档定位每一处改变落在哪份文档的哪一段、是增强、修正还是裁剪。不逐句扫描。

**归属**：判得准属于本需求的直接取（`ours`）；判得准不属于的写 `not_ours`，只记不消费；判不准的写 `unclear`，一定问人。

**三个尺度**：

- 会上明确收口的，你自己定为结论——判据是转写里收口的那句话，引得出来；没有那句话的一律记为遗留问题，不替人定；
- 说话人自己改口的，按后说的算；
- 文档与会议冲突时以会议为准写进变化，但它属于修正，要问人。

一份文件，每场会的每个版本一节；`source` 与 `source_sha` 照抄那一版 `transcript.json` 的 `source`：

```json
{"meetings": [{
  "source": "xxx.docx", "source_sha": "…", "attendee_roles": [{"name": "张三", "role": "产品"}],
  "topics": [{
    "id": "T3", "ownership": "ours | not_ours | unclear",
    "changes": [{"id": "C1", "kind": "add | remove | modify", "doc": "SR/design.md", "section": "§3.2",
                 "before": "…", "after": "…", "impact": "…", "evidence": ["S12", "S15"]}],
    "conclusion": {"text": "会上定了什么", "scope": "适用到哪", "evidence": ["S15"]},
    "open_points": [{"id": "O1", "what": "还缺什么决定或事实", "impact": "…", "needs": "谁来定", "suggestion": "（你的建议）"}],
    "ask": true, "ask_reason": "unclear_ownership | unresolved | transcript_doubt | high_impact | overturns",
    "overturns": "xxx.docx@a1b2c3d4/T1", "recommend": "opt_a",
    "options": [
      {"key": "opt_a", "label": "按会上定的改 SR §3.2，阈值取 5",
       "effect": {"ownership": "ours", "apply_changes": ["C1"],
                  "add_changes": [{"kind": "modify", "doc": "SR/design.md", "section": "§3.2", "before": "阈值未定",
                                   "after": "阈值 5", "impact": "验收的数值", "resolves": "O1"}],
                  "supersedes": ["xxx.docx@a1b2c3d4/T1"]}},
      {"key": "opt_b", "label": "维持文档口径，阈值仍待产品定",
       "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [], "supersedes": [], "keep_open": ["O1"]}}]
  }]
}]}
```

- `topics.json` 登记的每个话题在这里都要有一条；一个话题可以同时有变化与遗留，也可以只有结论没有变化（讨论收敛、原文不变）；
- `conclusion` 与每条 `changes` 都带 `evidence`：本版本 `evidence.json` 里的发言编号；
- **值得问的才问**（`ask: true`）：归属判不准的、没收敛而影响本需求的、影响结论的转写存疑、改动范围或接口的高影响修正、
  推翻前面已确认决定的（写 `overturns`）。每条带 `recommend` 与至少两个选项；
- **每个选项自带选完的结果** `effect`：归属定成什么；`apply_changes` 会上已定的哪几条变化生效；`add_changes`
  人补定的决定落到需求哪里（与 changes 同形，不带 evidence，`resolves` 指向本话题的遗留问题）；
  `supersedes` 替代哪些旧决定（可以为空）；`keep_open` 仍然未决的遗留问题。脚本不读 label，只按人选的 key 取 effect；
- 会上达成的写进 `changes`；人后来定的只写在选项的 `add_changes` 里，不写成会上已定。

## 五、材料关卡那一轮

`status` 给出 `await_gate:meeting` 时，与第一级材料关卡一起摆给人，不另停一次：

- 每个话题一句：变化、结论、遗留各一句；
- `ask` 为真的逐条：推荐与理由、每个选项选了会怎样；
- 你提出的参会人角色。

人一轮答完。先逐条记会议话题：

```
python doc/extensions/skills/story/scripts/core/story_flow.py decide --feature <AR> --gate meeting --meeting <主名>@<版本> --item <话题 id> --chosen <key> --basis "<人的原话>"
```

再照 `rules/init_analysis.md` 记第一级材料关卡。人对第一级表态，就是对摆出的整体的确认：没有逐条问的条目从这一刻生效。
之后 `AR/story-src/doc-refresh.md` 由脚本写出——生效的变化与已确认的原文，提取稿据它修正（`rules/ar_design_init.md`），
它也是交给人的文档刷新清单。需求分析第 ⑥ 节按话题登记会议（`rules/init_analysis.md`）。

## 六、之后再来会议

一场会一轮：新会议、或同名 docx 换了内容的新版本导入后开新一轮；旧版本的结论与原话照旧可查、照旧有效。
新版本推翻旧决定时写 `overturns` 并问人，人选的那个选项的 `supersedes` 决定旧决定是否失效。
收口之后才到的会议，`status` 会让你先 `reopen`。
