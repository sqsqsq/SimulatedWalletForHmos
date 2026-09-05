# real-run 夹具：取自真实一跑的产物

`AR90006` 是 2026-09-04 那一跑（`story-suite-20260904-194427`，opencode + bailian-deepseek）
落在 `doc/features/AR90006` 的产物，原样复制，**不做行尾转换、不重排字段**：

| 文件 | 为什么留它 |
|---|---|
| `spec/spec.md` | CRLF，385 行。骨架的术语起始行、流程图、附录 A/B/C 都从它派生 |
| `spec/knowledge-use.yaml` | 附录 D 的判定与依据的真源 |
| `AR/story-src/materials.json` | CRLF。附录 E 的类别与链接、图引用串都从它来 |
| `AR/story-src/decisions.json`、`copyedit.md` | `check` 要的台账 |
| `assets/`、`ux-reference/` | 图片实体：图引用与断链判据要它们真的在盘上 |
| `RR/`、`SR/`、`AR/design.md` | 合同声明的来源，缺了 `check` 会记一笔 |

**手造的最小样本证明不了行为**：它们全是 LF、字段规整、图片路径不带中文目录名，
而真实产物哪一样都不是。新增派生或形态判据时，夹具从这里取。
