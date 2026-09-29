# features 归档改到 doc/features/archive/ 与 README 按读者重排：实施者意见

2026-09-29，维护实施者。交维护设计者定稿，用户确认后实施。依据：用户 2026-09-29 两项要求；README 现状为 `de529f1e`（按 [README 合并方案复审](2026-09-29-README合并方案复审.md) 实施）。

## 1. 用户的要求

1. 「当前把 doc/features 每次移动到项目外 bak 进行备份，感觉不太好，是否考虑改成 doc/features/archive/ 下？」实施者分析后认为可行（§2），用户确认：已有的 `E:\Project\bak\Story-Features-*` 一并迁入 `doc/features/archive/`。
2. 「当前 README 的叙述逻辑可能要优化下，即先快速讲清楚怎么用，FAQ，如何适配，最后讲必要的机制与说明。原来的使用指南就是这么做的。现状把怎么用和机制混在一起，对于想快速上手的人，看起来很费劲。」读者按优先级：① 想用 story 进行开发的需求开发者；② 想移植 extension 的业务工程维护者；③ 想了解和学习 extension 特性与机制的开发者。
3. 两项都先交设计者定稿，再实施（用户 2026-09-29 选定）。

## 2. features 归档

### 2.1 事实

| 位置 | 现在的行为 |
|---|---|
| `test/scripts/run_multi_case.py` `migrate_existing_features` | 起跑前把维护仓 `doc/features` 的全部子目录移到 `FEATURE_ARCHIVE_ROOT/Story-Features-<时间>/`；根来自 `test/config/test.yaml > feature_history.archive_root`（`E:\Project\bak`），并强制「必须是代码仓外」 |
| `test/scripts/run_case.py` `migrate_feature_history` | 新链起跑时把运行根（隔离 workspace）里同名 feature 移到同一个配置根，允许「运行根外或本轮输出根内」；隔离 workspace 的模板 `doc/features` 为空，正常 suite 里返回 `no_existing_feature` |
| `test/scripts/check_failure_modes.py` `--historical` | 样本读 `doc/features/*` 与写死的 `E:/Project/bak/Story-Features-20260824-121838` |
| TEST §1.2 第 5 步、§5.4、§6.4；`test_multi_case_cli.py::SuiteFeatureArchiveTest` | 按仓外归档描述与断言 |
| `E:\Project\bak` | 55 份 `Story-Features-*`（单份约 5 MB），另有其他非本流程的备份 |

放仓外的原因已不成立：当初维护仓根就是消费工程，`doc/features` 在被复制的工程树里，历史产物放仓内会被带进被测侧。P3 之后回流根是维护仓 `doc/features`（已 gitignore），Case 工作区只从 demo 复制，`doc/features/archive/` 既不进被测侧也不入库。

### 2.2 方案

- `run_multi_case.py`：归档根固定为 `FEATURES_ROOT / "archive"`，不再读配置；`migrate_existing_features` 只移动 `archive` 以外的子目录到 `archive/Story-Features-<时间>/`；校验改为「归档根必须是 `doc/features/archive`」，删去「必须仓外」。回流与检查点回流拒绝名为 `archive` 的 feature。
- `run_case.py`：工作区内的新链迁移改落本轮输出根下的 `feature-history/`（现有校验已允许），证据随 suite 保留；`STORY_FEATURE_ARCHIVE_ROOT` 与 `archive_root` 配置退出。
- `check_failure_modes.py --historical`：样本读 `doc/features/*`（跳过 `archive`）与 `doc/features/archive/*/*`；写死的归档目录退出。
- `test/config/test.yaml`：删 `archive_root`，注释改为归档到 `doc/features/archive/`。
- TEST §1.2 第 5 步、§5.4、§6.4 与根 AGENTS §0 结构表同步（`doc/features` 说明加「`archive/` 为历次起跑前归档」）。
- 测试：`SuiteFeatureArchiveTest` 改为归档落在 `doc/features/archive/`、`archive` 自身不被搬、`doc/spec` 等不动；加一条回流拒绝名为 `archive` 的 feature；`--historical` 读 archive 子目录。
- 已有 55 份 `E:\Project\bak\Story-Features-*` 逐份迁入 `doc/features/archive/`，核文件数；`E:\Project\bak` 里的其他备份不动。

## 3. README 按读者重排

保留复审修正的 9 处事实与走查修正的 12 处，任何表述不回退，只调整组织：

| 部分 | 读者 | 内容 |
|---|---|---|
| 1. 快速上手 | ① 需求开发者 | 一句定位与使用前提（含「文中路径指目标工程里的位置」）；命令表（init / archive / update / restore / help / adapt）；一次需求的主线（起手 → 材料 → 会议 → 范围 → 生成 → 交付之后 → 评审 → 更新）；AI 在哪停下问你（停等表）；定范围怎么答；评审怎么表态 |
| 2. 常见问题 | ① | token、材料格式、中断继续、改范围、改 Story 措辞、会议转写、撤回本轮 update 与撤回线上归档、之后的阶段谁推进、没有审查员时会怎样 |
| 3. 安装与升级（移植到业务工程） | ② 业务工程维护者 | 现 §5 全部：前置、来源、所有权表、首装与升级时人要做的事、写入面、宿主入口 |
| 4. 机制与说明 | ③ 学习机制的开发者 | 需求目录与产物、工程知识三类与阶段承接、授权范围（`/story` 到交付门为止）、审查与交付门规则、update 的处理规则（重审条件、已到 plan 或代码时的处理）、当前边界与已知局限 |

- 快速上手只放「做什么、你要答什么」；规则解释（审查判定、update 内部处理、派生附录等）放第 4 部分，从上手与 FAQ 链过去。
- FAQ 每条先给一句答案，再指向第 4 部分的规则；复审 §3 把 FAQ 并进各节的安排由此恢复为独立一节，但每条只给答案与指向，规则仍只在第 4 部分写一次。
- 复审定的「命令直接写在动作旁」改为快速上手里一张命令表加主线；停等规则仍只有停等表一处。

## 4. 请设计者定

1. `run_case.py` 工作区内新链迁移改落本轮输出根 `feature-history/` 是否合适（另一选择：该迁移在隔离 workspace 下已无实际对象，直接退出）。
2. README 四部分的细分与 FAQ 条目是否完整；复审 §3「FAQ 并入各节、命令写在动作旁」的安排按用户要求调整为上表。
3. 是否并入 1.9.8 收口（建议并入：两项都是本版目录与文档调整的延续）。

## 5. 验收建议

- 归档：定向测试 `test_multi_case_cli.py`、`test_features_dir_config.py`、`test_driver_deadlock.py` 与 `check_failure_modes.py --self-check` 通过，新增断言在改前实现上失败；全量一次；55 份历史归档迁入后文件数一致；demo 与维护仓 git 干净，`doc/features/archive` 被忽略。
- README：三类读者各走最短路径——需求开发者读完第 1 部分能跑完一次需求，业务工程维护者只读第 3 部分能装好，学习者在第 4 部分找到规则；9 + 12 处修正逐条仍在；链接无新增失效；无版本演进字样。
