# SimulatedWalletForHmos 维护仓

本仓维护 Story Extension，写给维护设计者与维护实施者。消费模型在 `demo/` 或隔离 workspace 里工作，不读本文件与 `test/`。

## 结构

| 目录 | 是什么 |
|---|---|
| `extensions/` | Story Extension 开发源（机制、知识样板、宿主入口 `bridges/`） |
| `demo/` | 完整消费工程：业务代码、`framework/` 发布件、消费配置、宿主物化与已安装的 Extension（发布版） |
| `test/` | 维护域：维护契约、测试协议、脚本、Case、夹具、需求与方案 |
| `tools/cli/` | 实跑用的 CLI runtime |
| `output/`、`scratch/` | 运行证据与临时脚本，不入库 |

三处各有一份身份：`extensions/` 是当前开发版；测试时它被装进从 demo 复制的一次性 template；demo 只在正式发布时更新，平时保持上一个发布版。

## 开工前

- 先完整读 [test/AGENTS.md](test/AGENTS.md)：角色、所有权、不变量与预算都在那里。运行或修改测试按 [test/TEST.md](test/TEST.md)。
- `demo/framework/` 是 AgentMaison 发布件，只读。framework 的变化只经下面的接入协议进入 demo；本仓的两处本地定制见 test/AGENTS.md §2。
- 本仓根不挂 Framework 的阶段钩子与写保护钩子；遵守发布件只读边界由维护者负责。
- 开发 `extensions/` 时，链接、命令和相对路径按装进消费工程 `doc/extensions/` 后的位置写（test/AGENTS.md §3.2「按运行位置设计」）。

## framework 接入

输入是 Maison 的已验证发布件（zip），版本与构建身份看其中 `framework/RELEASE-MANIFEST.json`。
`python test/scripts/check_framework_drift.py` 比较 main 与 demo 接入的版本：退出 0 相同，1 不同，2 读取失败。

1. demo 先干净：`git status --porcelain -- demo` 为空。
2. 把发布件解压到 demo 根，替换 `demo/framework/`；用 `git diff --stat -- demo/framework` 核改动面与发布件的 `MIGRATION.md` 相符。
3. 两处本地定制（opencode `adapter.yaml` 的 `verifier_subagent` 登记、`templates/agents/verifier.md`）被发布件覆盖时，
   在新文件上重新加回这两处定制内容，不整文件回退到旧版。
4. 在 demo 根按 [framework-init](demo/framework/skills/project/framework-init/SKILL.md) 做 UPDATE（S1–S4），物化清单按本轮实际选择。
5. 核 Extension 入口（规则见方案 1.9.8 分册 03 §2.2）：用 demo 已装版本的 manifest 判断 diff 里的入口是否属于 Extension。
   已登记入口或 AGENTS/CLAUDE 的 story-ext 扩展段确实被换成通用内容时，只把该文件恢复为已装版本的内容，不重装 Extension。
   单独运行 `render-agents-md` 会按模板整体重写 `--out` 给的入口文件（扩展段随之消失），并按当前 adapter
   为 `doc/extensions/skills/*` 写 skill 跳板；它不代表 UPDATE 的全部行为，按实际 diff 处理。
6. 装置同步：根 `.opencode/agent/verifier.md` 逐字节复制自 `demo/.opencode/agent/verifier.md`。
7. 验证：demo 下 `cd framework/harness && npm test`；`check_framework_drift.py` 结果与本次接入一致；
   按 [TEST §7](test/TEST.md) 跑与改动相关的离线回归。
8. 提交 demo，并在 [test/EVOLUTION.md](test/EVOLUTION.md) 登记发布件版本、source_commit、定制处理与验证结果。

失败时用 git 查看并还原 demo；framework 自身的缺陷报回上游，不在本仓修。

## Extension 安装与发布

同一个安装函数（`test/scripts/publish_to_demo.py`）服务两种目标，顺序固定：整体替换目标 `doc/extensions` → 按 manifest
`provides.bridges` 的 target/source 对写宿主入口 → 更新 AGENTS.md / CLAUDE.md 的 story-ext 扩展段（区外不动）。

- **测试**：只装一次性 template。`run_multi_case.py` 按 TEST §2 的顺序装配（核 demo → 复制 → 装开发源 → 核同源 → 再核 demo），
  离线检查要的 template 按 TEST §7 现建。测试不写 demo。
- **正式发布**：前置是本版本已按发布纪律签认、demo 干净。

  ```powershell
  python test/scripts/publish_to_demo.py --source extensions --target demo --dry-run   # 看计划
  python test/scripts/publish_to_demo.py --source extensions --target demo             # 退出 0 = 已安装
  ```

  验证：`git status -- demo` 的改动只在 `demo/doc/extensions/`、manifest 登记的入口和两份入口文件的扩展段；demo 扩展与开发源同源：

  ```powershell
  python -c "import sys; from pathlib import Path; sys.path.insert(0, 'test/scripts'); import publish_to_demo as p; s, t = Path('extensions'), Path('demo/doc/extensions'); a = p.enumerate_source(s); print(a == p.enumerate_source(t) and all((s / r).read_bytes() == (t / r).read_bytes() for r in a))"
  ```

  打印 `True` 后跑 `python test/scripts/check_failure_modes.py`（缺省检查 demo），再随发布提交 demo，写 `test/release/<版本>.md`
  并在 EVOLUTION 登记。
- **失败**：退出 2 是输入读取或 git 前置不成立，目标没写；退出 1 是写入中途失败，结果 JSON 列出实际完成项。用 git 查看并还原 demo，
  修好后从同一源重装。脚本不回滚、不留安装日志。
- **对外升级**：其他仓的安装与升级用 demo 里已装的发布版 adapt（`demo/doc/extensions/skills/story-adaptation/`），不从开发源执行。

## 测试与预算

- 测试入口、离线回归与实跑协议：[test/TEST.md](test/TEST.md)。
- 预算只计 `extensions/` 的交付内容（知识、对接层与安装器 changelog 除外），范围与分级复核见 test/AGENTS.md §5，
  台账是 `test/regression/mechanism-budget.yaml`。
- 新 checkout 的依赖恢复见 [README.md](README.md)。
