# SimulatedWalletForHmos

本仓库具有**双重身份**：

1. **HarmonyOS 模拟钱包应用实例** — 可编译运行的示例工程，含 `01-Product/`、`02-Feature/` 等模块与业务文档（`doc/`、`specs/features/`）。
2. **`framework/` 通用框架的宿主仓库** — `framework/` 目录为可单独拆出、供其它工程以 **git submodule** 复用的 Skill + Harness + phase-rules + agent adapters；说明见 [framework/README.md](framework/README.md)。

---

## 新克隆后

若使用 submodule 拉取：

```bash
git submodule update --init --recursive
```

在 AI agent 中接入或更新 framework 配置：执行 **`/framework-init`**（或阅读 [framework/skills/00-framework-init/SKILL.md](framework/skills/00-framework-init/SKILL.md)）。

---

## 文档与约束入口

- 本实例全局指令（Claude Code）：[CLAUDE.md](CLAUDE.md)
- 架构与模块 SSOT：`doc/architecture.md`、`doc/module-catalog.yaml`、`doc/glossary.yaml`
- Harness 全链路说明：[doc/Harness全链路验证说明.md](doc/Harness全链路验证说明.md)
- 框架静态使用说明：[framework/README.md](framework/README.md)
- 框架升级与迁移：[framework/MIGRATION.md](framework/MIGRATION.md)

---

## Skill 索引

见 [framework/skills/README.md](framework/skills/README.md)。
