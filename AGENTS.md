# SimulatedWalletForHmos 维护仓

本仓维护 Story Extension，写给维护设计者与维护实施者。消费模型在 `demo/` 或隔离 workspace 里工作，不读本文件与 `test/`。

## 结构

| 目录 | 是什么 |
|---|---|
| `extensions/` | Story Extension 开发源（机制、知识样板、宿主入口 `bridges/`） |
| `demo/` | 完整消费工程：业务代码、`framework/` 发布件、消费配置、宿主物化与已安装的 Extension |
| `test/` | 维护域：维护契约、测试协议、脚本、Case、夹具、需求与方案 |
| `tools/cli/` | 实跑用的 CLI runtime |
| `output/`、`scratch/` | 运行证据与临时脚本，不入库 |

## 开工前

- 先完整读 [test/AGENTS.md](test/AGENTS.md)：角色、所有权、不变量与预算都在那里。运行或修改测试按 [test/TEST.md](test/TEST.md)。
- `demo/framework/` 是 AgentMaison 发布件，只读。framework 的变化只经正式接入进入 demo；本仓的两处本地定制见 test/AGENTS.md §2。
- 本仓根不挂 Framework 的阶段钩子与写保护钩子；遵守发布件只读边界由维护者负责。
