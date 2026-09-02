# 步骤 5 · Extension 六阶段作者入口接入

## 目标

使用步骤 4 的 Framework 入口，把 Extension 已有六份 `hooks/<phase>/author.md` 在作者行动前送达。这里只修通道，
不改 Story 或 Knowledge 语义内容，以便问题可以归因到“是否送达”。

## 实施内容

1. 在 `doc/extensions/manifest.yaml` 的六个 phase 登记现有 `author.md` 为 `on_context_load`；
2. 保持 author 内容一份真源，不复制到 Skill、AGENTS、模板或新的 wrapper；
3. 新入口稳定后，从 Extension 交付入口删除“靠执行者主动去找 author.md”的远距离流程要求，只保留简短机制说明；
4. 建立隔离行为夹具：每个 phase 的作者起手输出必须包含一个该 phase 独有的中性标记，且 verifier prompt 不得出现；
5. 覆盖直接进入 phase、Story 转入 Spec、correction 和恢复后的再次进入。

## 允许范围

- `doc/extensions/manifest.yaml`、六份现有 `hooks/<phase>/author.md`；
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
- 无真实 Story，现有 Story/Knowledge 输出不变。
