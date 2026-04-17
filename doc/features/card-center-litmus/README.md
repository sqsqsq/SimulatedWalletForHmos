# card-center-litmus — 第二波术语消歧试金石

> 本目录是一个**故意制造歧义**的试金石用例，用于验证第二波改造（WP6）的核心
> 约束——**术语消歧 BLOCKER 能否正确拦住"卡中心 → CardManager"的误映射**。

## 背景

在真实内网跑动中出现过一个典型事故：

1. 用户写的需求里提到「**卡中心**」（UI 概念：用户打开钱包能看到的卡聚合入口页）。
2. 弱模型在生成 PRD 时，因「卡中心」和 03-CommonBusiness 层的「**卡管理 (CardManager)**」字面相似，
   误把"卡中心"映射为 `CardManager` 模块，后面的 design / 编码全部按错方向走。
3. 第一波的 Scope 守门只能在 design 阶段报"模块越界"，但此时 PRD 已经错了，Scope 也跟着错。

本 litmus 把问题压到输入端：**让 PRD 一启动就必须拿到一张映射表 + 用户逐条人工确认**。

## 使用方式（三种路径）

### 路径 A：正路径（AI 正确做术语消歧）

1. 以 [PRD-request.md](./PRD-request.md) 作为用户需求输入，调用 `/prd card-center-litmus`。
2. 期望 AI 的表现：
   - 在 Step 1.5 检出「卡中心」是 `medium` 置信度（命中 glossary 但有 `easily_confused_with`）。
   - 生成的术语映射表中，「卡中心」的"权威模块"列**应该是 `WalletMain`**，并且把「卡管理 (CardManager)」作为易混项亮给用户看。
   - 停下来等用户在每一行 `[ ]` 改成 `[x]` 后再继续生成 PRD 正文。
3. 预期 PRD 生成后：`check-prd.ts` 的 `terminology_mapping_table` PASS。

### 路径 B：误映射路径（AI 把卡中心误映射到 CardManager，被脚本拦截）

构造一个违规 PRD（见 [PRD-violation-sample.md](./PRD-violation-sample.md)），其中的术语映射表故意把：

| 原始术语 | 权威模块 |
|---------|---------|
| 卡中心 | CardManager | ← 错误映射，且用户确认未勾选

把这份 PRD 放到 `doc/features/card-center-litmus/PRD.md` 临时跑一次，期望：

```
❌ FAIL [BLOCKER] terminology_mapping_table
       详情：1 条术语映射未获得用户确认
```

即便把 `[ ]` 改成 `[x]`，`scope_matches_catalog` 也会因为 Scope 声明同步受污染而 FAIL（如果 Scope 声明里是 CardManager 但 out_of_scope 里是 WalletMain，与实际意图相反）。

### 路径 C：人工 auto-approve（故意把 [ ] 全部改成 [x] 但不思考）

验证即便用户随便勾选 `[x]`，只要权威模块没存在于 catalog，脚本会兜底拦截（`terminology_mapping_table` BLOCKER）。

## 相关文件

- [PRD-request.md](./PRD-request.md) — 给 AI 的原始自然语言需求（含"卡中心"歧义词）
- [PRD-violation-sample.md](./PRD-violation-sample.md) — 路径 B 用的违规 PRD 示例
- [doc/glossary.yaml](../../glossary.yaml) — 卡中心 / 卡管理的正确映射及 disambiguation
- [doc/module-catalog.yaml](../../module-catalog.yaml) — WalletMain 与 CardManager 的职责对比

## 结论（第二波交付凭证）

- 若 AI 能沿路径 A 产出合规 PRD → 第二波 Step 1.5 落地成功。
- 若 AI 走上路径 B 且被 `check-prd.ts` 拦下 → 第二波 BLOCKER 生效。
- 两条路径都能走通，说明术语守门既能前置规训（路径 A）又能兜底拦截（路径 B）。
