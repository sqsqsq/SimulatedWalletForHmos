# 评审 · 步骤 2「Adapt 轻量化」

> **执行者注意（2026-09-08 最新）**：本文的收口结论是当时基线的记录。后续独立复核发现 F1–F3，用户另新增 A12“内网业务仓之间复刻”。Demo 来源保留目标 adapters；内网来源连同 adapters 覆盖，目标 knowledge 及激活清单保留。完整改动范围与验收见 [最新整体评审：已实施部分](03-整体审查与步骤1-2复核.md#已实施部分)，本轮继续工作须同时处理返修与新增要求。

评审 2026-09-08。对象：提交 `e54b6c2e`。方法：按 `steps/02` §9 七条行为核——在 `%TEMP%` 搭三个目标仓（旧版升级目标、空仓首次安装、非 git），包用 HEAD，`--apply` / `--check` 亲自跑；失败路径逐条触发；离线四道门复跑。

**结论：升级路径全部成立；首次安装路径两处失败，一处失败语义不对，三处返修后收口。**

## 1. 升级（目标：旧版扩展 + 自改的对接层 + 自定义知识与清单 + 改过的配置 + 一个退场文件 + 删掉一个 core 文件 + 改过的跳板）

| 动作 | 结果 |
|---|---|
| `--apply` | 写入 3、清除 1：退场文件删掉、缺的 `headings.mjs` 补回、跳板覆盖、manifest 合成 |
| 对接层 | `adapters/story.js` 末行仍是目标自己加的那行 |
| 知识与清单 | `my-facts.md` 在，manifest 的 `provides.knowledge` 仍含它；`version` 已是包的 |
| `framework.config.json` | 目标加的键在，文件不在 diff 里 |
| `--check` | 通过（diff 落点 / manifest 知识清单 / ⑤ / ⑦ / ⑧） |
| 未提交就再 `--apply` | 停，点名写入面上 4 处并给动作 |
| 写入面之外脏（`adapters/`、`knowledge/`、无关文件） | 照常升级——写入面之外的改动与本命令无关 |
| 写入面之内脏 | 停，点名文件 |
| 目标不是 git 仓 | 退出 2，说明为什么要 git |
| 包与目标同一棵树 `--apply` | 退出 2「没有可写的东西」；`--check` 只跑 ⑤⑦⑧，通过 |
| ⑧ | 包 `scripts/` 根下放一个 `stray.mjs` → 点名并说明两边都不认 |

夹具 `test_adapt_ownership.py` 十二条覆盖以上升级面、前置与 ⑧；`test_empty_knowledge_repo.py` 五条覆盖空清单的派生、`selfCheck`、任务包、骨架。

## 2. 首次安装（目标：只有 `framework.config.json` 与 `AGENTS.md` 的空仓）——**两处返修**

| 动作 | 结果 |
|---|---|
| `--apply` | 写入 70 个文件；`knowledge/` 下只有四个 README；`paths.extension_dir` 补上；`AGENTS.md` 末尾带标记区 |
| **R1 · 清单** | manifest 原样照抄包的，`provides.knowledge` 登记了 16 个 Demo 文件，目标里一个都没有。`activeKnowledge` → 「派生为空：激活清单登记的文件读不到 —— knowledge/facts/component-profile.md」；`spec/author.mjs` 同一句。**新仓装完跑不起来**——方案 §5 写明这是核心前提，§2 写明首次的清单「按首次安装建的骨架登记」。合成 manifest 时 `STATE === 'fresh'` 那一支要把 `provides.knowledge` 换成刚写进去的那几个 README（`kind: index`，派生结果四类皆空、链条照走），部件画像由模型写完再登记（SKILL §3 已这么说） |
| **R2 · `--check`** | 首次安装刚做完就 `--check`：「升级动了目标的知识」四条（四个 README 都是 `?? knowledge/…`），退出 1。首次安装的写入面含知识骨架（方案 §3 表最后一行），diff 判据没有区分两态——刚装完的仓通不过自己的自检。`--check` 在目标 HEAD 里没有 `manifest.yaml` 时按首次判：`knowledge/**/README.md` 允许出现，其余仍拦 |
| 派生 | 清单只登记四个 README 时 `activeKnowledge` 返回四类皆空——R1 修完这一步就是通的 |

首次安装没有夹具（`test_adapt_ownership.py` 没有一条走 `fresh`）——两处都是跑一遍就现的。返修要各加一条：空仓装完 `activeKnowledge` 不抛、`--check` 退出 0。

## 3. 失败语义——**一处返修**

**R3 · 包缺跳板要停，不是跳过。** 包里少一个跳板文件时 `--apply` 打一行「包里缺跳板 …，跳过」然后照常完成、退出 0。方案 §9 判据 6：包缺文件退出码非 0 且说清哪一步没做完。跳板清单是包自己在 manifest 里登记的，登记了却没有文件是包坏了，不是可选项；与「目标不是 git 仓」同一待遇——写盘之前查，缺就停。

## 4. 与方案不同、我认可并已写回方案的三处

- `.gitignore` 只补章草稿一行：新实现不落 `.adapt-*` 工作件，第二行没有要挡的东西。⑦ 与 SKILL 同步了；方案 §3、§6 改为一行。
- 对接层的输出合同放 `scripts/README.md` 而不是 `adapters/README.md`：它同时讲两个目录各归谁，放在这一层对；⑧ 对它单独放行并写明理由。
- 首次安装的标记区追加在入口文件末尾，不是「实例扩展」节末尾：内容一样，位置由人一次确认时顺手调，不值一条判据。

## 5. 离线与预算

747 passed / 195 subtests；失效形态 70 条 FAIL 0；`adapt-scan --check` 自适配通过；framework 差异仍是 opencode 两文件。

预算实测 9694（prompts_md 1841、hooks_mjs 3001、data 778、scripts_mjs 2488、scripts_py 1586），在用户 2026-09-08 签的 9700 以内；预算文件 `current` 已换成本轮，`framework-patch.yaml` 那半句已删。

## 6. 返修复核（`f23b245f`）——**步骤 2 收口**

临时根重新搭（空仓首次、旧版升级目标、缺跳板的包），退出码不经管道直接取：

| 项 | 我做了什么 | 结果 |
|---|---|---|
| R1 首次的清单 | 空仓 `--apply`：manifest 的 `provides.knowledge` 只登记四个 README；`activeKnowledge` 四类皆空不抛；`spec/author.mjs` 任务包写「本仓未配置知识……`knowledge-use.yaml` 也不用建」 | 通过 |
| R2 首次的 `--check` | 装完立刻 `--check` 退出 0；往 `knowledge/facts/` 放一份正文再 `--check` → 「首次安装往知识目录写了正文……只建目录与各类 README（A3）」退出 1。两态按目标 HEAD 里有没有 manifest 判，盘上那份是刚写的不算 | 通过 |
| R3 包缺跳板 | 「停：包里登记了跳板却没有文件（1 个）……目标一个字节未写」，退出 2，`git status` 为空 | 通过 |
| 升级回归 | 目标退回旧态（多一个退场文件、少 `headings.mjs`）再升：写 4 清 1，`--check` 退出 0 | 通过 |
| 夹具 | `AFreshInstallRunsOutOfTheBox` 四条：清单登记骨架、派生能跑、自检通过、仍拒知识正文 | 在 |
| 离线 | 752 passed / 195 subtests；失效形态 70 条 FAIL 0；自适配通过；framework 差异仍是两文件；预算 9694 / 9700 | 通过 |

**收口判定**：升级与首次安装两条路都按方案成立，失败路径三条各自退出非 0 且目标未写。步骤 2 收口。

## 7. 设计文档不归档（用户 2026-09-08 裁定）

`.gitignore` 只留 `test/story/plan/` 一条，批次 5、6 的放行例外去掉，注释改成「方案、评审与状态记录都留在工作区，不归档」。`f23b245f` 已把此前入库的设计件撤出索引，`git ls-files test/story/plan` 为零。
