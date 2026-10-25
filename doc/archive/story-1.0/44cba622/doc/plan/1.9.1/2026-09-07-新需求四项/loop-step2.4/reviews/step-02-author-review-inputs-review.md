# step-02-author-review-inputs · 评审记录

> 本文件只追加，不改写。记录按事件序号或时间分节。步骤合同见 [../steps/step-02-author-review-inputs.md](../steps/step-02-author-review-inputs.md)；设计真源是 `../../steps/02.4-02-作者输入与审查职责收敛.md`。
>
> 本步实现已在 loop 建立前提交（`5203ca30`，交回 `../../steps/02.4-02-交回.md`）。executor 加入后完成实施前审视，直接送审该提交；返修另起提交。

## 2026-09-11 · 初始化（reviewer）

方案准备完成，见 [plan-review](plan-review.md)。等待 executor 加入。

## seq 4 后 · step_ready（reviewer）

executor 已加入。本步从 `5203ca30` 的送审开始，不重做实现。实施前审视请覆盖三件事，写进本文件再送审：

1. 交回 `../../steps/02.4-02-交回.md` 的逐项与 `5203ca30` 的 diff 一一对应，特别是分册 §3.0 四字段表的形状与 `story-sources.mjs` 实际读法一致；
2. 四道门在当前 HEAD 仍绿，`measure()` 前后值与交回表一致；
3. 交回自记的两处未验证边界（R21 头部说明能否让模型写出四字段、R20 后审查质量）如实保留为「行为待验」，不在本步补自证。

送审用 `submission`，返修若有另起提交。
