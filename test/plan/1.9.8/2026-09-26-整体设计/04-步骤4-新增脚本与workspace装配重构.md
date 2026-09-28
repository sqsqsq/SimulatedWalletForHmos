# 工作分册 04：安装动作、漂移检查与 workspace 装配

属于 [总览 P2](00-总览.md#2-三个实施包)，前置 P1 通过。先在临时 fixture 验安装与错误路径，再核 05 已完成的初始化证据，最后做完整装配演练。产品源以本版允许面为限。

## 1. 统一安装动作

维护命令为：

```text
python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]
```

调用者明确给出 source/target。测试将当前 extensions 装进一次性 template；发布时将本次待发布 extensions 装进 demo，核对后随发布提交入库。安装器不选择 Git 版本。R197 首次初始化的导出与调用见 05，已完成的初始化不重跑。

目标只有 demo 及其临时消费副本，固定安装位 doc/extensions。向 demo 发布前，调用者检查 demo 的非忽略 Git 状态为空；查询失败或有修改时停止并报告。维护者在核对、提交或处理现有修改后再发布。template 无 Git 干净要求。

安装顺序：枚举源 → 整体替换目标 doc/extensions → 按登记写宿主入口 → 更新 AGENTS/CLAUDE 的 story-ext 标记区。扩展目录包含该源的完整示范知识，源中不存在的旧文件随替换退出；标记区外保持，无标记沿既有首装语义追加，破损标记报告失败。真实目标的知识保护由 adapt 承担。

正常 CLI 从 manifest 的 target/source 对构造文件对：source 相对扩展源码根，target 相对消费根。`.agents/skills/story/SKILL.md` 按映射安装；未登记的 `.agents/skills/story-adaptation/SKILL.md` 保持从 demo 继承的内容。dry-run 只输出源集合、扩展替换位置、入口文件对及标记区位置，不写目标。

### 1.1 源集合

`enumerate_source(source)` 是安装、dry-run、DEV_EXT 和结果核对共用的唯一枚举算法，返回按 POSIX 相对路径排序的文件集合。读取实际目录中的当前文件，包含未提交修改和新增未跟踪文件。

排除源根 adapt/、名称以 .adapt- 开头的文件/目录，以及任意层级 .git、node_modules、__pycache__、.pytest_cache 和 .pyc/.pyo 文件。排除集合只在枚举函数维护；普通隐藏资产保留。保留现有源枚举对链接、不可读文件及大小写冲突的诊断，不追加目标路径链预检。

### 1.2 共同调用与失败

同一文件提供 `install_extension(source, target, bridge_files, *, dry_run=False)`；`bridge_files` 是 `{source: Path, target: str}` 文件对。正常 CLI 解析当前 manifest；R197 初始化调用者给出导出仓宿主位置的源文件。导入模块不运行 CLI。

返回 `{status, source_version, target, planned, completed, failed}`，status 为 planned、installed、preflight_failed 或 write_failed；路径列表只作为本次调用结果，不持久化安装状态。CLI stdout 输出该结果，stderr 输出诊断；退出码分别为成功0、输入读取/解析失败2、写入失败1。发现错误即停止，失败项含路径和原因，completed 只报告实际完成项。读源、配置或登记失败如实报告；不承诺所有异常都在写入前发现。

template 安装或核对失败即作废，从 demo 重新装配，失败副本不启动 Case。demo 发布失败停止，维护者检查 Git diff，按发布前基线处理本次安装改动；人工后来修改先保留和核对。demo 恢复干净后再安装。脚本不负责回滚；不增加安装清单、备份、恢复表、原子替换、源冻结/途中复核或逐路径脏检查。

发布者在操作期间保持待发布源稳定，安装后核源与安装结果，再记录发布源身份和 demo 提交。该操作核对沿用装配的同源检查，不建立源快照机制。

## 2. workspace 装配

run_multi_case.py 使用以下固定顺序：

1. 检查 demo 基线和源卫生。Git 查询成功且 demo 非忽略变更为空才继续；有在途人工修改或 Git 查询失败时，在复制前报告并停止，不替用户还原。正常 ignored 依赖/运行态保持原规则。记录版本化安装面、相关文件摘要和 git 状态，单纯前后相等不能证明发布基线干净。
2. 从 DEMO_ROOT 整体复制到现有隔离 template。顶层维护目录 test/tools/output/scratch/.bak/.git 应触发结构错误。
3. 保留既有运行态排除：消费配置的 features 目录、Framework 状态中的活动内容、oh_modules/build/intermediates/.hvigor/.pytest_cache/__pycache__ 等；保留必要 .gitkeep。node_modules 保留并验证可用，不以存在代替 hooks 加载成功。
4. 在 template 内调用安装命令，source 为根 extensions，target 为 template。
5. 核扩展、知识、bridge 和扩展段同源，运行框架及 gate 可按消费相对路径加载。
6. 复制完成的 template 到各 Case workspace，沿原 Case 初始化/启动协议执行。缺前置的 template 不进入本步骤。
7. 核 demo 文件摘要和 git 状态与装配前一致；这只验证装配不写 demo，不包含用户授权的 finalize 回灌动作。

状态排除和相对路径计算以传入消费根为基点；回灌按 02 的 demo 目标处理。维护代码不注入被测模型上下文。开发源运行态不随安装进入 template，发布基线与开发版不会混装。

## 3. 漂移自查

check_framework_drift.py 读取 main:framework/RELEASE-MANIFEST.json 和 demo/framework/RELEASE-MANIFEST.json。比较 version，显示两侧 source_commit；同版本身份差异作为事实展示，不声称文件完全一致。

退出码 0 表示版本相同，1 表示版本差，2 表示 Git/文件/JSON/字段错误。错误保留原始诊断。版本差指向根维护契约的接入协议，不自动升级或重装 Extension。

## 4. 离线验收

- 安装正例核所有文件、目标配置、固定 doc/extensions、标记区外保护和重复执行；源/登记读取错误返回诊断；写入错误返回失败，不产生备份或安装日志目录。
- 新增未跟踪 mjs 和已修改 tracked 文件都进入开发 template；同级 node_modules、.adapt-*、adapt、__pycache__、pyc 不进入源集合，普通隐藏资产保留。
- demo 有非忽略修改或 Git 查询失败时，发布与装配均在写入/复制前停止；干净 demo 可以继续。安装失败报告实际完成项，template 不进入 Case；维护者通过 Git 处理失败的 demo 发布后可重试。
- fixture 验卫生断言、运行态排除、hooks 依赖、失败 template 不启动 Case；合法消费路径保留 framework/...、doc/extensions/...。
- 核两份 .agents 在 demo→template 的内容来源：story 按开发映射变，story-adaptation 按 Framework 保持。四份消费钩子配置及脚本随复制在 template，Codex command 无旧机器路径，命令从消费根可解析；不声称未经实测的宿主自动触发成立。
- 完整演练：R197 demo → 开发版 template → 两个独立 Case 副本；比较安装面同源及 demo 前后不变。之后一次使用新开发源重建，验证不会残留上一版已删除文件。
- 漂移同版本、版本差、缺文件/坏 JSON 正反例通过。
- 在开发版 template 上运行失效形态与集成相关测试；源静态扫描仍以 extensions 为对象。

本分册不启动真实 CLI。交回调用结果、演练/失败证据、实际路径、demo 保持证据及预算；P2 安装/装配属于维护域，不计预算，正确性仍按本分册验收，见 [总览 §5](00-总览.md#5-预算与计量)。
