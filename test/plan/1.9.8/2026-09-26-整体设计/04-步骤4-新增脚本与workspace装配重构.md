# 工作分册 04：安装动作、漂移检查与 workspace 装配

属于 [总览 P2](00-总览.md#2-三个实施包)，前置 P1 通过。先在临时 fixture 验安装与错误路径，再按 05 初始化 demo，最后做完整装配演练。产品源以本版允许面为限。

## 1. 统一安装动作

维护命令为：

```text
python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]
```

名称保留，source/target 必须显式给出。测试目标是隔离 template，发布目标是 demo。目标配置决定 extension_dir；脚本不根据 dev/release 切换目录、不读取历史 commit。

正常 CLI 从 source/manifest.yaml 读取当前 target/source 对。CLI 和 05 的一次性初始化调用者都使用本节定义的 install_extension；内部函数只消费明确文件对。

写入前完成：源清单和桥接源存在、目标配置可读、目标在显式目录内、source/target 不互相覆盖、扩展段边界有效，以及发布目标覆盖面无未保存的人工工作。dry-run 只输出计划，不写目标或运行状态。

实际写入面：

1. 按 §1.1 枚举源内容，整体安装到目标 extension_dir，含该源的完整示范知识；源集合中缺失的旧机制文件退出。开发源包含未提交修改和新增未跟踪文件。
2. bridge 文件对写到目标宿主路径；默认消费位保持源内容，自定义安装位按 03 改引用路径。
3. 用同一源的 AGENTS.section.md 重写 AGENTS/CLAUDE 的 story-ext 标记区，区外字节保持；无标记按现有首装语义追加，破损/重复标记在写前报告。

输出清单到维护域 output/story：源路径和版本、目标、实际文件/摘要、标记区以及完成/失败面。清单用来核同源与定位失败，不引入新的运行调度状态。

本次 `.agents/skills/story-adaptation/SKILL.md` 不在 Extension 映射写入面，安装保持它；template 中的 `.agents/skills/story/SKILL.md` 则按开发版映射替换。清单区分安装修改与从 demo 继承的 Framework 保持面，不能因名字都带 story 就一起覆盖。

缺源等预检失败时目标不写。template 中途失败后重建；demo 中途失败先按 §1.3 恢复、重新通过预检，再安装，重试不绕过脏文件检查。

### 1.1 源集合的唯一算法

`publish_to_demo.py` 内 `enumerate_source(source)` 返回相对源根 POSIX 路径排序的文件集合，安装、dry-run、清单和安装结果核对均使用它。遍历实际目录，不使用 git ls-files 筛选：已修改文件按当前字节读取，新文件即使 untracked 也入集合。

明确排除：源根的 `adapt/`、名称以 `.adapt-` 开头的文件/目录；任意层级 `.git`、`node_modules`、`__pycache__`、`.pytest_cache`；任意 `.pyc`、`.pyo` 文件。该清单唯一放在枚举函数使用的常量中，其他调用者不复制。未列出的隐藏文件和代码资产照常纳入；遇符号链接/重解析点、不可读文件或大小写冲突路径时报告，不跟随到源外。以后出现真实运行态再按责任修改清单，不用宽泛后缀删除可能的业务资产。

开发调用者直接给工作区 extensions；发布调用者从指定发布提交导出干净源再给安装器。安装器不解析 Git 提交、不自动读 HEAD、不自行选发布版本。源字节和清单在预检固定；应用前发现源变化时失败，避免同一安装混入两次编辑。

### 1.2 共同函数与结果合同

新增职责均位于同一个 `test/scripts/publish_to_demo.py`，导入模块不执行 CLI。

```python
install_extension(source: Path, target: Path,
                  bridge_files: list[BridgeFile], *, dry_run: bool = False) -> InstallResult
```

`BridgeFile` 为 `{source: Path, target: str}`；source 是已存在的明确源文件，可由初始化调用者指向导出仓根宿主位；target 是消费工程相对文件路径。正常 CLI 将 manifest 的 source 先对扩展根解析后传入。重复 target、目标越界和源目标重叠在写入前失败。

`InstallResult` 为 `{status, source_version, target, planned, completed, failed, manifest_path}`。status 取 `planned|installed|preflight_failed|write_failed`；三个列表均为目标相对路径条目。CLI stdout 输出该 JSON，stderr 输出诊断；退出码 0 为 planned/installed，2 为预检失败，1 为写入失败。dry-run 的 manifest_path 为 null，不写文件。

非 dry-run 清单写入维护仓 `output/story/install-<唯一目录>/manifest.json`，目录由标准库创建唯一名；同目录 `before/<目标相对路径>` 保存覆盖/删除前原始字节。每项包含 `path, operation(add|replace|delete), before_sha256, before_path, desired_sha256, result(pending|done|failed), error`，无文件用 null。摘要为原始字节完整 SHA-256。写前先落完整计划和备份，备份失败不动目标；每个文件完成后更新清单。此清单只服务这次文件操作和恢复，不参与 Story/Framework 状态。

预检只对覆盖面检查脏文件。位于 Git 内的 demo 采用仓根相对路径转目标相对路径核对；不在 Git 内的隔离 template 可以安装。要发布的 demo 初次迁移内容须先形成可回查的提交基线。目录删除仅作用于明确列出的文件，空目录随后收拢；不删除清单外的目标内容。目标已有排除运行态保持，template 的消费运行态由装配步骤清理。

### 1.3 发布失败的恢复表

恢复由维护者消费安装清单，不增加 restore 子命令。先核目标绝对路径仍属于该次 target；每项核 current、before、desired 三个摘要，null 表示不存在。

| 现场 | 动作 |
|---|---|
| current == before | 已在原状，保持 |
| replace 且 current == desired | 从 before_path 恢复原字节 |
| delete 且 current 为 null | 从 before_path 恢复原字节 |
| add 且 current == desired | 删除本次新增的该文件 |
| 其他内容或备份缺失/损坏 | 保持现场，列冲突路径与三方摘要，停止宣称完整恢复 |

单文件使用同目录临时文件加原子替换，临时路径登记在清单；异常临时文件仅在仍符合记录且无人修改时清理。进程在写入后、登记 done 前中断，也按字节而非 result 标志判断恢复。清单不能证明来源的部分写入保留为冲突。

恢复后逐项重验安装面及 git 状态。无冲突且等于安装前基线才重新进入预检；有人工新增修改时交其责任人处理，不能为了重试覆盖它。template 失败则保留证据、整次重建，不执行 demo 的恢复操作。

## 2. workspace 装配

run_multi_case.py 使用以下固定顺序：

1. 检查 demo 基线和源卫生。记录版本化安装面、相关文件摘要和 git 状态；有在途人工修改时报告，不替用户还原。
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

- 安装正例核所有文件、目标配置、自定义 extension_dir、标记区外保护和重复执行；缺源/错目标/坏映射的负例核目标未写。
- 新增未跟踪 mjs 和已修改 tracked 文件都进入开发 template；同级 node_modules、.adapt-*、adapt、__pycache__、pyc 不进入源集合，普通隐藏资产保留。
- 在 replace/delete/add 三种操作后分别中断，按恢复表回到原字节；中断后再人工编辑的文件保持并报告冲突；恢复前的再次发布仍被脏面检查拒绝。
- fixture 验卫生断言、运行态排除、hooks 依赖、失败 template 不启动 Case；合法消费路径保留 framework/...、doc/extensions/... 或其配置安装位。
- 核两份 .agents 在 demo→template 的内容来源：story 按开发映射变，story-adaptation 按 Framework 保持。四份消费钩子配置及脚本随复制在 template，Codex command 无旧机器路径，命令从消费根可解析；不声称未经实测的宿主自动触发成立。
- 完整演练：R197 demo → 开发版 template → 两个独立 Case 副本；比较安装面同源及 demo 前后不变。之后一次使用新开发源重建，验证不会残留上一版已删除文件。
- 漂移同版本、版本差、缺文件/坏 JSON 正反例通过。
- 在开发版 template 上运行失效形态与集成相关测试；源静态扫描仍以 extensions 为对象。

本分册不启动真实 CLI。交回清单、演练/失败证据、实际路径、demo 保持证据及预算；P2 维护代码/测试估 +460/−150，见 [总览 §5](00-总览.md#5-预算与计量)。
