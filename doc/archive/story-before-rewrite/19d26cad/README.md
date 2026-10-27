# story重写前的1.x版本资料

2026-10-25 批次一01归档。来源是story重写准备基线 `19d26cad2eb77a70f4ea40bfe4b14c4cf3395aa6`；归档时这些路径自O起未再改动。

story分支原有的907件1.x版本资料（`doc/spec/1.x/`、`doc/plan/1.x/`、`doc/release/1.x.md`）与story-1.0的对应如下。2026-10-27起正常版本目录按story-1.0（B）的原件恢复连续历史，这里保留story分支自己的身份：

| 与story-1.0的关系 | 件数 | 归档位置 |
|---|---:|---|
| 同路径同blob | 904 | 不重复保存，读 [story-1.0归档](../../story-1.0/44cba622/README.md) 中的同一路径 |
| 同路径不同 | 3 | 本目录，保持原仓相对路径 |
| story独有 | 0 | — |

同路径不同的三件是 `doc/release/1.9.8.md`、`doc/spec/1.9.9/00-版本范围.md`、`doc/spec/1.9.9/04-稳定性与性能分析/01-分析报告.md`，两侧原件都保留：正常版本路径是B的版本（1.9.9按B正常结项），本目录是story分支当时的版本（其中「1.9.9已迁入旧2.1.0」是story分支当时的安排）。逐件身份见 [manifest.json](manifest.json)，907件旧路径到归档位置的对应见 [active-path-map.json](active-path-map.json)。本目录配置 `-text`，检出不改换行。

`test/golden/` 是story分支在 `19d26cad` 的旧金样全16件（2026-10-27按Git对象原样补入，清单见第三批01的[历史恢复清单](../../../plan/2.0.0/03-批次-更新与全量保持/实施反馈/2026-10-27-历史恢复清单.csv)）：AR90006 的 Story/Review 正本与说明、AR90004 Story、银行卡开户上报候选组及图片，保持当时的正本与候选身份；旧2.x评审对照的是这组，不是当前 `test/golden/`。[manifest.json](manifest.json) 仍只证明上面3件。

归档内相对链接按原仓布局解析；未随档复制的目标按 `19d26cad:<原路径>` 读取。`doc/spec/project/`、`doc/plan/project/` 与 `doc/project/` 按原归属留在原位，不在本次归档范围。
