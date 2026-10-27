# 步骤 5 · Extension 六阶段作者入口接入

## 目标

使用步骤 4 的 Framework 入口，把 Extension 已有六份 `hooks/<phase>/author.md` 在作者行动前送达。这里只修通道，
不改 Story 或 Knowledge 语义内容，以便问题可以归因到“是否送达”。

## 实施内容

1. 在 `doc/extensions/manifest.yaml` 的六个 phase 登记现有 `author.md` 为 `on_context_load`；
2. 保持 author 内容一份真源，不复制到 Skill、AGENTS、模板或新的 wrapper；
3. 新入口稳定后，从 Extension 交付入口删除“靠执行者主动去找 author.md”的远距离流程要求，只保留简短机制说明；
4. 建立隔离行为夹具：每个 phase 的作者起手输出必须包含一个该 phase 独有的中性标记，且 verifier prompt 不得出现；
5. 覆盖直接进入 phase、Story 转入 Spec、correction 和恢复后的再次进入；
6. 在六份 `rules/<phase>-rules.overlay.yaml` 的 `exploration_thresholds.phase_input_snippets_extra` 里声明本阶段 author 钩子的
   仓内相对路径（与步骤 4 入口输出的来源标识同一字符串）。作者没把它写进 `context-exploration.md` 的 `key_inputs_read`，
   既有门禁 `context_exploration_inputs_coverage` 即 FAIL——这是「作者读到了」的唯一机械留痕，不新增门禁、状态或字段。
   没有 context-exploration 门禁的阶段（如 testing）不声明，如实记为无留痕。

## 允许范围

- `doc/extensions/manifest.yaml`、六份现有 `hooks/<phase>/author.md`、六份 `rules/<phase>-rules.overlay.yaml`（只加 `exploration_thresholds.phase_input_snippets_extra`）；
- `doc/extensions/skills/story/AGENTS.section.md` 与生成入口的直接源文件；
- Extension loader/author 入口的行为测试和 `TEST.md`。

本步不改 author.md 的业务要求，不改 post_check、pre_verifier、Story build、Knowledge 正文、Framework 或产品代码。

## 完成条件

- 六个 phase 各只有一份作者内容，manifest 引用全部可达；
- 内容在作者第一次写产物之前出现，不依赖门禁失败；
- 缺失 hook 明确为空，损坏/抛错明确失败；
- verifier 上下文只收到 `pre_verifier`，没有作者片段；
- 根 AGENTS/生成入口不再承担逐阶段内容传输；
- A03/A05 的新行为测试能对好/坏通道稳定区分；
- 夹具：`key_inputs_read` 不含 author 钩子路径的 `context-exploration.md` 在既有 `context_exploration_inputs_coverage` 上 FAIL，含则 PASS；
  overlay 未声明的阶段行为不变；
- 无真实 Story，现有 Story/Knowledge 输出不变。
