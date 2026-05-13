# 命名与公开 API 禁忌（演示 knowledge）

本文件由 `manifest.yaml` → `provides.knowledge` 引用，用于验证 extension bundle 中静态 knowledge 路径。

- 业务模块、对外 RPC/URI **禁止**与 catalog 中其他模块的 `easily_confused_with` 混淆命名。
- SDK 封装层类型前缀建议与业务模块前缀一致，避免深路径 import（跨模块仍走出口 `index.ets` 约定）。

白名单路径：plan §7.13 knowledge/naming-taboos.md
