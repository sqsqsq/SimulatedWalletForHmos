# Step2.3 四项返修

> 2026-09-10。**这四项是 Step2.3 的缺陷，不是历史清理**：三项与 02.3 分册明写的合同对不上，一项是更早一轮分层改动的残留。它们先于 [B5](01-B5执行方案.md) 完成；B5 只核对这些修正的消费者是否同步，不另写一套兜底。
>
> 载体说明：Step2.3 的 implementation-loop 已在 `final_report_completed` 关闭，不在已关闭的工作流里补事件。这份文件是它们的载体，可以单独执行，也可以并进一个新的 loop。
>
> 状态：待实施。

## 返修 1 · skeleton 的装配前校验缺口

**依据**：`02.3-02` §3「`story-build skeleton` 改为消费当前 source-index 与 story-template……它**先校验编排结构、来源版本、引用目标和原合同必要章节**，再更新材料视图和输出草稿」；§5 谓词表的「template 可装配」含「selection/index/basis **为当前版本**」。

**现象**（评审侧在真实工作区实测，三种情形）：

| 情形 | `skeleton` | 登记前 `check` |
|---|---|---|
| 源文件在盘上变了、索引未重建 | 退出 0，输出不提 SE | 退出 1，报「成文依据：来源 SE 变了」 |
| 初筛（`source-selection.json`）整份删掉 | 退出 0 | 退出 1 |
| 初筛 `basis` 过期 | 退出 0 | 退出 1 |

`assemblyInputs` 现在只比 `template.basis` 与 `index.sources` 的摘要——两份都是索引侧的记录，谁都没问过磁盘；selection 缺失时 `selection?.items ?? []` 静默走过。

**后果**：作者照着一份已经不成立的依据写完十章，错误要到登记前才暴露。这正是「报错太晚」那一类。

**要求**：`skeleton` 写盘之前补三项校验，任一不成立即一个字节不写，并报出缺的是哪一份、怎么补：

1. 索引登记的来源摘要与磁盘现状一致（**与 `check ⑯` 共用同一实现**——03 §2 明写表头/图类型校验不能在局部与最终 check 各写一份，来源版本同理）；
2. `source-selection.json` 存在且可读；
3. `selection.basis` 与 `index.sources` 一致。

**验收**：三种情形各一条用例，`skeleton` 退出非零且工作区一个字节未变；正常路径仍退出 0；`check ⑯` 的既有用例不变。

**边界**：不新增第二套判据。若共用实现需要把 ⑯ 里那一段提成函数，那是重构不是新增。

## 返修 2 · UX 交互正文在成文链上没有落点

**现象**（审计 B20，四方各说各话）：

| 一方 | 说法 | 位置 |
|---|---|---|
| 导入端 | UX 类文档的正文并进 `ux-reference/README.md` | `import_sources.py:72` |
| 索引端 | 按 `material_dirs`（RR/SR/AR/inbox）过滤，`ux-reference` 不在其中，它永不进 `source-index.json` | `story-build.mjs:503` |
| 清单端 | 把它记成 `kind:doc`，于是它成为附录材料清单的必列行 | `materials.py:158`、`story-build.mjs:1116` |
| 合同 | 「`ux-reference/` 下的 README 不是登记，也不是来源」 | `story-chapters.json` 的 `sources_note` |

**用户 2026-09-10 裁定：可以引用，它是一种输入形式。** 所以 UX 交互说明文档的正文**该进成文链**，下面按这条执行。

**改法（最小）**：给 UX 一个合同 source key，与 `UPSTREAM` 同一档。

```json
"UX": { "path": "ux-reference/README.md", "required": false, "label": "界面参考" }
```

这样走的是 `indexSources` 的**第一支**（遍历 `ctx.contract.sources`），不动 `material_dirs` 那一支的过滤规则。`required: false` 与 `UPSTREAM` 一致：没有 UX 材料时不报缺件，只记一笔。

**四方随之对齐**：

| 一方 | 现在 | 改成 |
|---|---|---|
| 导入端 `import_sources.py:72` | UX 类正文并进 `ux-reference/README.md` | **不动**。它现在就是这个落点 |
| 索引端 `story-build.mjs:485-500` | 按 `material_dirs` 过滤，收不到 | 合同加了 key 之后自动收，**不改代码** |
| 清单端 `materials.py:158`、`story-build.mjs:1116` | 记成 `kind:doc`、附录材料清单必列行 | **不动**。它本来就与「是来源」一致 |
| 合同 `sources_note` | 「`ux-reference/` 下的 README 不是登记，也不是来源」 | 改掉这句。**界面图不在来源表里**那一句保留——加的是正文的 key，不是图片的 |

**验收**：

1. 放一份 UX 类文档进收件箱 → 导入 → `sources --stage before-spec`：`source-index.json` 里有 `UX` 这份来源，它的内容单元可被编排引用；
2. 没有 UX 材料时 `sources` 仍退出 0，不报缺件（`required: false`）；
3. 图片的身份与登记不变——仍在 `materials.json`，不因为加了正文 key 而多一条路径；
4. 附录材料清单里 UX 那一行的形态不变。

**注意**：`ux-reference/` 同时是 framework 像素保真链扫描界面图的目录（`fidelity-shared.ts:460-465`、`check-spec.ts:1613-1620`）。加的是**正文的来源 key**，那条链不受影响；实施时确认一遍。

## 返修 3 · 父级上下文进了索引却没有送达

**现象**：`story-sources.mjs:62` 计算 `units[].context`（各祖先在其第一个子标题之前的正文范围，由外到内），`story-build.mjs:555` 写进 `source-index.json`，**交付面零读取**——材料视图、草稿、审查任务书都不用它，读它的四处全在 `test_source_index.py`。

**分册的保证本身没破**：`02.3-01` §3 让「父章节在第一个子章节前的正文另成一个单元」，所以父级前提有身份可以被引用；`context` 是额外的定位信息，分册没有规定谁消费它。

**但作者面有个实际缺口**：编排只引用了子单元时，父级的口径表或前提不在同一份材料视图里，而编排未必想得到要一起引。

**两条路，选一条并说明**：

1. **接上消费者**：材料视图里，给引用了子单元的那一章附上其祖先前导正文的**读取位置**（`文件:行范围`，不复制正文——与来源目录同一口径）。
2. **判定无用**：删 `context` 字段与它的计算，理由是父级前提已经自成单元、要用就引它。

**建议第 1 条**，理由是「不能丢掉父级前提与表格」是分册为切法给的理由，而现在这个理由只在切法里兑现、没在送达里兑现。

**验收**：选 1 则用例证明视图里能定位到祖先前导正文；选 2 则 `context` 在全仓零命中，且切法用例不变。

## 返修 4 · 作者任务包的第一节从来没有工作过

**现象**：`hooks/spec/author.mjs:40` 拼 `path.join(SKILL_ROOT, 'scripts', 'story_flow.py')`，实际路径是 `scripts/core/story_flow.py`，该文件不存在。于是 `flowStatus` 永远返回 `null`，任务包「§1 你现在在哪」恒走降级分支（`:56-58`），只打一句「你自己去跑那条命令」。

全仓只有这一处还用旧路径，是 `core/` 与 `adapters/` 分层那一轮的残留。

**这一项不需要任何设计裁定，直接修。**

**验收**：一条用例——流程契约存在时，任务包 §1 给出真实的 `next` 与 `action`，而不是降级文案。

## 交回

四项各自说清：改了哪里、依据是分册哪一条、反例是什么、正常路径有没有变。返修 2 与 3 另说选了哪条路、为什么。

四道门照旧：离线全量、失效形态 70 条 FAIL 0、`adapt-scan --check` 退出 0、`git status framework/` 为空。

规模按 `test_mechanism_batch` 口径记前后值。这四项预计是净增（返修 1 与 3 都要加实现），如实记，不与 B5 的账混算。
