# S37 退出维护仓根 OpenCode 副本

**设计裁定。** 退出维护仓根 `.opencode/` 及其专用同步和自比测试；宿主运行资产留在消费工程。当前 f894 候选暂保 demo 里的 OpenCode／DSH verifier 供阶段独核；蓝图质询、Story 读者及阶段 verifier 分别核。上游 db29eb82 已实现统一阶段独核，正式分发接入后按实证退掉被接替的宿主定制。两者均不属于对外发行的 `extensions/base/`。本步为 05 批维护域 G0/X0，与 S34–S36 并行，在 S36 的同一候选上验收。

| 对象 | 基线 1a4e82f9 查到的来源、实际消费者 | 动作 |
|---|---|---|
| 维护仓根 `.opencode/agent/verifier.md` | 1.x 的 `6d8bea7e` 为运行现场缺 verifier 链而引入根资产；当时同处的 `plugin/record-verifier-report.js` 在 `55b24abb` 已退。当前根文件、demo 宿主文件和 demo Framework 的 OpenCode 模板是同一 Git blob，`60ea8362`。CLI 从 demo 复制到各 Case，维护根的副本仅由原 AGENTS §6 同步约定及单独相等断言维持。 | 删除跟踪文件及空目录，退出同步约定、当前操作说明中的根副本和专用相等断言。维护根因此不再提供项目级 OpenCode verifier。历史交回作为当时的证据保留。 |
| 根 `.opencode/` 的非跟踪文件 | 本机目录里另有自忽略的 .gitignore、package.json、package-lock.json 及 node_modules；这是根宿主留下的本地运行产物，干净 checkout 不携带。 | 清退当前维护根的这些已核运行产物。先枚举未跟踪／忽略项与链接，确认目标绝对路径就是本仓根下的 .opencode；若有本表以外的人工资产，先保住并列明。清理限根目录，不写 demo。 |
| `demo/.opencode/` | 项目级 framework-init 按已选 OpenCode adapter 物化 OpenCode 的角色、规则和 Skill 等；Case 从 demo 创建。现行验收在 demo/template 核 verifier 与 Framework 模板同源、只读声明及 Story 入口。 | 保留宿主安装态及有消费者的回归。Framework 模板和本地定制各按现有唯一补丁来源维护；变化后从正常入口刷新 demo。 |
| `demo/.dsh/framework-verifier.patch.yml` | 与 `demo/framework/agents/dsh/templates/agents/framework-verifier.patch.yml` 同 blob `5bc85082`。既有 test pin 的宿主补丁提供 dsh adapter，init 物化。CLI suite 给启动和续跑都加 `--patch {cwd}/.dsh/framework-verifier.patch.yml`；每个 Case 的 cwd 指它自己的隔离工程。 | 保留配置层、启动与续跑参数、源模板及其回归。使用完整与省略该层的同 profile 离线 dump-config，均可选相同模型，仅完整配置注册专用 verifier 工具和 maison-verifier preset。当前无需改中央 cli-runtime 或外网包。保留期限以新正式分发接管相同消费者为准。[配置对照](../../../../../output/evidence/2.0.6-host-directory-review/dsh-comparison.json) |

**提交与验收。** 在 `test/tests/test_verifier_chain_in_workspace.py` 移除仅消费维护根的 `test_the_maintenance_copy_of_the_verifier_is_the_demo_one`。同文件中的 `VERIFIER_DEF` 等常量还有 demo/template 消费者，保住真实装配、角色协议、入口同源和 Case 工作区断言；保住 `test_cli_registry_snapshot.py` 的 DSH 调用验证。核本轮规约和维护操作说明已不要求复制回根。交回根已跟踪路径清单、当前现场清理结果、干净候选外网包与模板的实际清单、两套宿主的保留回归。重建隔离模板后须仍能找到 OpenCode 的 verifier 和选定 DSH 的配置层；确认两条宿主目录均未混入外网发行件。此清理可先做，S36 统一核最终候选并汇总交回；S12/S13 的冻结与启动条件沿用既有裁定。

**Verifier 专项裁定。** [两版对照、完整退出清单及给作者的问题](../04-Framework阶段verifier接替与上游确认.md)。根镜像立即退出；宿主专用的阶段角色与运输定制按下一次正式接入逐项退出。S36 仅验本轮实际候选。
