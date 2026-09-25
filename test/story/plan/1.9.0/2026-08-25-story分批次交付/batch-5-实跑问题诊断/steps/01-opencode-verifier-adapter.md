# 步骤 1 · OpenCode interactive verifier adapter

## 目标

补齐 Framework 已有 verifier 能力在 OpenCode interactive 下的 adapter 实现。完成后，OpenCode 能用独立只读执行体读取
Framework request、发布身份绑定报告，并由现有 receipt/closure 消费。本步不改变任何 Story 或 Knowledge 语义。

## 前提与输入

- 用户已明确授权本步在当前工程直接修改 vendored `framework/`；授权不延伸到 D3。
- 先读 `03-方案讨论决策.md` 的 D1，以及 Framework 现有 Claude/CodeAgent verifier 协议。
- OpenCode 原生 agent/event 的事实必须来自本机 1.18.x 实抓或已安装包源码，不从文档名猜测。

## 实施顺序

1. 用最小 OpenCode 原生实验取得：独立 agent/session 身份、首条任务输入、只读工具约束、完成事件和可信终稿字段。
2. 若事件不能同时证明独立身份、任务归属和稳定终稿，停止并标记 `阻塞`；不实现独立子进程备用 provider。
3. 复用 `repo_file_request`、subject 推导、prompt hash、报告 JSON 和 evidence loader；只新增 OpenCode 所需的发布机制。
4. publisher 使用机制名称，不伪装成 `subagent_stop`，不在 TypeScript 中建立 adapter 名单分支。
5. 对 request 自述、磁盘原件、当前 summary、终态块和执行身份做与现有协议等强度的绑定；错误或迟到报告进入明确失败。
6. 全链实证后才在 `framework/agents/opencode/adapter.yaml` 登记 `interactive`。
7. 从 `framework/RELEASE-MANIFEST.json.source_commit` 生成只包含 Framework 产品改动的上游补丁和交接说明；验证补丁能在该基线应用。
8. 在 `TEST.md` 的 verifier 专节维护本步离线验证命令；步骤文件不复制命令。

## 允许范围

- `framework/agents/opencode/**`；
- `framework/agents/adapter-schema.yaml`、`framework/agents/README.md`；
- publisher 枚举和 adapter 声明解析的直接消费者；
- 若物化 OpenCode plugin/agent 配置确需，允许修改对应 init 物化代码；须用实抓证据说明必要性；
- verifier 协议回归测试、`test/story/TEST.md`；
- `framework.config.json` 仅允许为本步实际修改的 Framework 文件增加真人具名 drift allowlist。
- 本方案目录下的 `artifacts/01-framework-opencode-verifier.patch` 与 `artifacts/01-upstream-handoff.md`。

不得修改 `framework/RELEASE-MANIFEST*` 来迁就漂移，不得修改 Extension、现有 Story Case、phase 语义、headless/goal 或其他 adapter 行为。

## 必须覆盖的反例

- 主执行者自行写报告；
- 错/旧 subject，request 或 prompt 被改，缺终态块；
- event 来自另一 agent/session；
- 同 subject 不同 agent 或不同结论冲突；
- verifier 工具具有写权限；
- policy off/not_applicable；
- adapter 未声明或声明不完整。

## 完成条件

- OpenCode 原生事件证据足以支持发布机制；
- required × interactive × opencode 从 `blocked` 变为 `enabled`，其余 policy 三态不变；
- 合法报告可被现有 evidence/receipt/closure 接受，全部反例拒绝；
- Claude/CodeAgent 原有 request、publisher、报告与闭环回归不变；
- 没有 OpenCode 配置的工程不产生新文件或行为；
- Framework 变更均在精确授权范围，保护区零差异。
- 上游补丁以发布件 `source_commit` 为基线、可复现本地 adapter 行为，且不包含本仓 allowlist、测试输出或 Extension 改动；
- drift allowlist 每项写明“仅用于上游发布前本地验证；UPDATE 到包含此变更的 Framework 后删除”，不得成为永久交付路径；
- STATUS 明确区分“本仓验证通过”和“内网已随上游发布”，后者在实际发布前保持未完成。

实施者只回写“步骤 1 已实施，等待评审”。真实 Spec CLI 留给步骤 2。
