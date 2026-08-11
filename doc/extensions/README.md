# 实例扩展目录（`paths.extension_dir`）

本目录承载**与具体 feature 目录相独立**的实例级扩展：`manifest.yaml`、`skills/`、`knowledge/`、`lifecycle hooks` 等。协议与叠加顺序见：

- [framework/docs/concepts/extensibility.md](../../framework/docs/concepts/extensibility.md)
- [framework/specs/instance-extension-manifest.schema.yaml](../../framework/specs/instance-extension-manifest.schema.yaml)

初始化时若目录不存在，可由 **framework-init** 从 [framework/skills/project/framework-init/templates/extension-skeleton/](../../framework/skills/project/framework-init/templates/extension-skeleton/) 拷贝骨架。

本仓库内含 **wallet-sdk-demo** 演示包（文件名与演进计划白名单对齐），仅作引用示例；生产环境请按业务改写 `manifest.yaml` 与路径。
