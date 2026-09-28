# 工作分册 05：demo 初始化与维护文档

§1 属于 [P2](00-总览.md#2-三个实施包)，§2–4 属于 P3。源为最终发布 R197，安装函数来自 [04](04-步骤4-新增脚本与workspace装配重构.md)。当前没有发布身份时不得以 HEAD 或旧发布版代替。

## 1. demo 初始化

1. 记录 R197 提交及发布说明，核其 manifest.version 为 1.9.7。将该提交实际扩展目录、已登记 bridge 和 AGENTS.section.md 取到本次 scratch 暂存目录；只取发布文件，不收本地运行态。
2. 按下方命令导出 R197，读取导出目录 doc/extensions/manifest.yaml 中已登记的宿主文件列表，为每条 p 构造 `BridgeFile(source=export_root/p, target=p)`，调用 04 的 install_extension。扩展目录按 R197 原字节安装，manifest 保持发布版格式/版本；不重写为开发版映射。
3. 该一次性脚本/命令及清单作为初始化证据保存到 output/story，不进入正常安装 CLI。此后日常安装只消费当前显式映射源，正常工具没有 --init-from 或旧列表兼容分支。
4. demo/.opencode 和 demo/framework/harness 的依赖随迁移核对，缺失按自身 package 安装；根维护装置按实际需要具备依赖。
5. 核四类安装面：机制和知识等于 R197，bridge 按 R197 已登记集合核；AGENTS/CLAUDE 扩展段来自 R197，区外为 demo 自身内容。开发新增 cursor/agents 的六份要求在开发 template 验，不套到旧发布基线。
6. 核 root/demo verifier 装置逐字节一致、demo 业务/framework 保持面无意外变化，然后提交 demo 发布基线。证据保存命令、发布身份、清单和核对结果。

这只是旧布局发布文件的一次性落位，不增加长期兼容功能。后续正式发布用当前 source/target 安装 CLI；本版范围内 demo 基线保留 1.9.7，开发源 manifest 在本版产品首次改动时按既有发布纪律标 1.9.8。

R197 已固定为 `c026a70497b511b399c7e15dabd153f852b3a2fe`。两份 `.agents/skills/{story,story-adaptation}/SKILL.md` 由 P1 随 Framework 物化迁入，另归物化保持面，不追加到 R197 的四份 manifest bridge 文件对；初始化安装必须保持它们原字节。四份钩子配置也按消费配置面核，唯 Codex Stop command 的旧机器路径按 01 §1.1 单列例外。这样 R197 安装面和 Framework 保持面各有来源，不能把未列在 bridge 清单的入口误报为残留或自动删除。

初始化缺文件先回 R197 清单核实，不混用当前开发源补齐；源版本不一致不继续。失败按 04 §1.3 恢复并重新通过预检，再从同一源安装。完成后进入 04 的装配演练。

### 1.1 可执行的导出和调用顺序

实施者把已发布的完整提交号赋给 `$release197`，变量来源必须是 1.9.7 发布交回。所有命令在维护仓根执行，`$export197` 是本次 scratch 下新建空目录；先核绝对路径，再创建，禁止复用有未知内容的目录。

```powershell
git cat-file -e "$release197^{commit}"
git archive --format=zip --output=scratch/release-1.9.7.zip $release197 doc/extensions .opencode/skill/story .cac/commands/story.md .claude/commands/story.md .codex/skills/story
Expand-Archive -LiteralPath scratch/release-1.9.7.zip -DestinationPath $export197
```

四份宿主文件清单以 R197 manifest 校验；若最终发布集合变化，导出其实际登记的路径并记录，不从本版六份入口补足。导出前清点 commit 树，每个登记项必须存在。压缩包/导出目录属于一次性证据；使用实际 shell 参数数组传路径，不拼接不可信命令。

初始化调用者使用 `importlib.util.spec_from_file_location` 导入 `test/scripts/publish_to_demo.py`，构造 BridgeFile，先 `install_extension(export_root/'doc/extensions', demo, pairs, dry_run=True)`；退出码成功及清单核对后调用同一函数的 dry_run=False。两次输入摘要须一致。调用者只解析这次 R197 清单，产品安装器保持当前映射语义。

四类核对分别为：枚举算法所得机制文件、激活知识及其实际文件、R197 bridge 集合、两份入口的扩展标记区。使用导出字节/确定性标记区渲染结果比较，不以 manifest.version 相同代替内容一致。记录 R197、归档 hash、dry-run 计划、实际结果和 demo 提交；该提交是随后不变性验证的发布基线。

## 2. 根维护入口

- 根 AGENTS.md：P1 先建立仓定位、demo/framework 只读和 test/AGENTS 必读入口；本包在同一文件补齐结构、framework 接入、Extension 安装/发布及测试/预算索引。详细不变量引用 test/AGENTS.md，不复制两份。
- 根 CLAUDE.md：P1 建立指向根 AGENTS.md 的入口，本包核对有效；不复制 demo 的 Framework 阶段钩子。
- 根 README.md：仓定位、extensions/demo/test 结构和维护入口。
- demo 的入口文档保持消费职责，维护材料不进入消费模型上下文。

framework 协议写清发布件输入、实际 UPDATE、两处本地定制、装置同步、验证和 EVOLUTION 登记。Extension 协议写清测试只装 template、正式发布装 demo，以及失败、验证和登记。独立入口渲染命令的写入面按事实说明，不写固定升级后重装。

## 3. 当前维护材料同步

- test/AGENTS.md 保留角色/所有权/不变量/预算原则，更新 framework 的 demo 路径、开发源位置、测试域路径和两处定制的实际处理方式；退役 integrity 字段不成为有效机制。
- 维护者开工必读的 test/AGENTS §0 索引、§2 发布件路径及 TEST §7 当前命令，作为 P1 最小入口的直接消费者提前修正；本包负责剩余完整说明，不重复计量、不改历史记录。
- TEST.md 更新脚本路径、bootstrap 默认 demo、复制→template 安装→Case 顺序、发布基线保护、开发版检查目标和回灌位置。删除测试后 git 还原 demo 的安排。
- EVOLUTION 追加本版结果及证据入口，历史条目保持；release/1.9.8.md 如实描述结构与安装职责及验证边界。
- 当前其他文档/命令经引用清点随源同步。2.0.1 材料随维护目录迁移，保持本轮已经明确的前置和职责，历史代码观察路径可以保留为证据。
- 1.9.7 已退出的独立内网指南不创建、不恢复维护；升级内容只维护 adapt/reference/upgrade-changes.md。

人手试用按 bootstrap 回执先设置 `STORY_REQUIREMENT_SYSTEM_DIR` 为维护域实际系统目录，再以 demo 为消费根启动会话。给出该宿主可复制执行的环境变量/切换目录命令及 --verify 操作，不承诺未配置变量时旧 test/story 回落仍可用。正式 CLI 始终用各 Case 自己的隔离系统快照。

新 checkout 验收须从无 `.opencode/package.json`/node_modules 的状态列清依赖恢复命令及依赖身份；这些当前是 ignored 本地现场，不能仅写“已有依赖随迁移”。P2 依赖就位与 P3 人读启动说明使用同一操作来源。

## 4. 验收与交回

AC04/13：R197 原字节、发布时入口集合、标记区、依赖加载和基线入库证据完整。AC09：当前结构、命令和链接有效。AC10：两条操作协议明确输入、动作、验收、登记及失败责任。

根只读职责由维护契约送达，不能把已迁入 demo 的合作式 hook 记作根维护会话的物理保护；本版只核迁移保持，未新增强隔离机制。若宿主有实际只读沙箱，交回如实说明其覆盖，不以规则文字代替隔离证据。

运行证据留 output/story，在交回中引用，不把 gitignored 日志声明为已入库。维护文档、安装和初始化维护脚本均不计预算；范围及分级规则见 [总览 §5](00-总览.md#5-预算与计量)。
