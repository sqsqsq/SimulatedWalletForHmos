# M4 脚本参数不承载 JSON · 方案（已实施）

**不变量**：交付脚本的命令行参数只放标量，结构化数据一律走文件。

理由是通道性质，不是某次事故：JSON 全是引号，而任何 shell 都要对参数再解析一遍。
同一条命令在 bash 下原样送达，在 Windows PowerShell 下双引号被吞：

```
--classify '{"a.docx":"RR"}'      → python 收到  {a.docx:RR}
--classify '{\"a.docx\":\"RR\"}'  → python 收到  {"a.docx":"RR"}
```

宿主是变量（bash / pwsh / 其它），指引没法枚举各家的引号规则，所以约束落在接口上。

## 一、归责

AR90006 第三次实测（`ses_005c78b2cffexMCNKrHYbNreZ0`）里，`--classify` 连续失败 6 次、
`--import-result` 再失败 1 次；模型把原因误判为 ANSI 代码页 / cp936 / BOM，最终放弃 CLI，
改用 `python -c "importlib.util.spec_from_file_location(...)"` 在进程内加载模块，
此后连纯 ASCII 参数的 `decide` / `complete` 也不再走命令行。

| 层 | 判定 | 改它会怎样 |
|---|---|---|
| skill 指引 | 直接触发因：`SKILL.md` 的示例标 ```bash，模型逐字照抄，宿主是 PowerShell | 只加转义示例 = 补丁，换宿主再犯 |
| **脚本接口** | **根因**：把跨宿主不可靠的通道当接口。且 `--import-result` 违背 `SKILL.md` 自立的原则——导入结果是兄弟脚本产出的，不属于「脚本无从得知」 | **通道消失，不可能再犯** |
| 被测模型 | 有过错（诊断错、绕路重），但不是可依赖的修复点 | 换模型、换宿主还要再发现一次 |

同一条教训 `test/story/AGENTS.md:150` 已记过一次（当时的面孔是 heredoc 吃反斜杠）（「heredoc 吃转义 → 用 Write/Edit 工具，
**参数不过 shell**」），当时只落成开发侧的自我提醒，没变成接口约束。本次落到接口上。

## 二、改动

**`import_sources.py`**

- 删 `--classify`；归类读 `inbox/.classify.json`（AI 用 Write 写，不过 shell），
  按 `utf-8-sig` 解析——写它的可能是任何宿主，PowerShell 的 UTF8 带 BOM，多一个字节不该是失败；
  文件不存在 = 空归类，有料却没归类仍按既有规则显式报错；
- `scan_sources` 跳过点文件——**点文件是控制件不是材料**，是不变量而非对某个名字的豁免；
- 成功后把回执落在 `AR/.last-import.json`（内容即 stdout 那份），失败不落。

**`story_flow.py`**

- 删 `--import-result`；`cmd_round` 读 `AR/.last-import.json`，没有回执 = 本轮没导入；
- 契约落盘成功后销毁回执——回执是一次性的（先删后写会在写失败时丢掉事实）；
- `pending_material` 同样跳过点文件：两个脚本对「什么算材料」必须同口径，
  否则归类件会被当成「新放的料」，让补料关卡误判为通过；
- M1 的跨轮去重保留作兜底：导入重跑会再落一份内容相同的回执，仍不重复计入。

**`SKILL.md`**：导入章改为「先写 `inbox/.classify.json`，再跑脚本」两步；契约章的时机表
去掉 `--import-result`；两处都写明结构化数据走文件的理由（写成通道性质，不写事故）。

**机械断言**：`ShellChannelTest` 扫 `skills/story/scripts/*.py` 的全部 `add_argument`，
凡参数值是 JSON 即失败——覆盖将来新增的脚本，不靠人记得这条。

## 三、验证

1. 全量 290 项机械测试绿（新增 8 项：归类件读取/缺失/损坏、点文件不算材料、
   回执写入/失败不写/消费即销毁、参数不承载 JSON）；
2. `--phase extensions` PASS（6/6）；`export_delivery_patch.py --verify` 干净可应用；
3. **PowerShell 零转义复演**（关键判据，必须用 PowerShell 而非 Bash 工具跑，
   用 Bash 会绕开引号规则等于没验）：`round` → `decide supplement` →
   `Set-Content .classify.json`（带 BOM）→ 导入 → 重析 `round` → `split` → `proceed` →
   `complete`，全程不加任何转义技巧，**一次通过**。产出契约：round1 `imported: []` +
   占位哈希；round2 `imported: ["AR90006-交通卡自动充值.docx"]` +
   `inputs.RR` = 当前 RR 实际哈希；2 轮 3 决策；回执已销毁；中文文件名与中文决策依据原样落盘。

**指引有效性**（冷启动模型会不会照新指引先写文件再跑脚本）自测不了，搭下次 AR90006
实测的便车验证即可，不值得为此单跑一轮：失败模式已从「误导性 JSON 解析错误 + 反复绕路」
降为「脚本明确报未分类文件」——那是既有用例覆盖的、可自恢复的路径；且模型即使完全不看指引，
也不会再撞上引号。

## 四、不做

- 不保留 `--classify` / `--import-result` 作兼容路径——留两条路模型会继续选错；
- 不改 `inbox/README.md`：它的读者是放材料的人，不会创建点文件；
- 不提交。
