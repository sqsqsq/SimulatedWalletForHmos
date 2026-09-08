---
name: story-adaptation
description: /story adapt——把 Story Extension 装到或升级到目标工程。所有权由目录表达，升级 = 换 core/ + 覆盖跳板 + 一次 git diff 确认；知识与对接层一个字节不碰。
---

# story adapt — 把 Story Extension 装到 / 升级到目标工程

**包** = 发起本命令的仓库（缺省当前仓）。**目标** = `/story adapt <目标工程>` 的参数。
路径相对各自 `framework.config.json > paths.extension_dir`（缺省 `doc/extensions`）。

## 所有权由目录表达

| 目录 | 归谁 | 升级时 |
|---|---|---|
| `<ext>/skills/story/scripts/core/` | 包 | 整份换掉，包里没有的删掉 |
| `<ext>/skills/story/scripts/adapters/` | **目标仓自己实现**（`story.js`、`token.js`、`review.js`） | 一个字节不碰 |
| `<ext>/knowledge/` | 目标 | 不读不写 |
| `<ext>/` 下其余一切 | 包 | 整份换掉 |
| `<ext>/manifest.yaml` | 机制登记归包，`provides.knowledge` 归目标 | 按这条规则合成 |

边界这么一分，「升级之后哪些文件变了」本身就是答案——所以确认用 `git diff`，不必读两棵树逐文件比。
**没有第三种要你判断的情形**：一个文件归谁，看它在哪个目录。

## 你要做的四件事

### 1 前置（脚本自己查，不过就停）

```
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --apply --target <目标根> --package <包根>
```

它先查三件，任一不满足就退出并点名：

- **目标是 git 仓库的根**——升级的确认靠 `git diff`，没有 git 就没有「哪些文件变了」这个答案；
- **写入面上没有未提交改动**——工作区脏的话 diff 里混着目标自己的改动，分不清哪些是升级带来的，而「升级把没提交的改动盖了、diff 里还看不出来」没法补救；
- **包与目标都读得到**（各自的 `framework.config.json` 与包的 `manifest.yaml`）。

**不替用户动他的工作区**：不自动 stash、不自动提交。报错会点名脏的路径，让他自己先提交或暂存。

### 2 判态（脚本判，你不猜）

目标有没有 `manifest.yaml`——**有就是升级，没有就是首次**。历史版本识别、结构签名、混合状态处理都不存在于本实现。
版本相同且没有文件要写时，它报「当前适配仍有效」并退出 0。

### 3 写入

`--apply` 一次做完全部确定性写入：删掉退场文件、复制机制面、合成 manifest、覆盖跳板、重写入口标记区、补 `.gitignore` 那一行。
你只下命令、读结果。

**升级不停等**：一次升级指令授权到写入完成加自检，只有失败才回头问人。写入面已由目录边界完全确定，没有可拍板的选项。

**首次安装多两件**，其中一件归你：

- 脚本做的：确保 `framework.config.json` 有 `paths.extension_dir` 这个键（缺就加），建知识目录与各类 `README.md`（读法与清单说明）。**不放包里的知识正文**——那是目标仓自己的东西，从空的开始。
- **你做的：写部件画像**。这是首次安装里唯一归模型的一件事：

| 项 | 内容 |
|---|---|
| 看什么 | 目标仓的 `framework.config.json` 架构 DSL（层、模块、跨模块出口文件）、`doc/module-catalog.yaml`、`doc/architecture.md`；三者缺的按仓内目录实扫 |
| 写什么 | 部件画像。**落点与形态照 `<ext>/knowledge/facts/README.md` 写**——那份说明归知识侧，文件名与节结构都在它里面，机制不复述一遍 |
| 「能核实」是什么 | 每条事实后面带仓内路径或 DSL 键名；查不到的写「未确认」，不写推断 |
| 停一次问人 | 摆出这份画像与 `framework.config.json` 的配置键，人改过再落盘。首次安装保留这一次确认，因为这里有两处真实取舍 |

画像写完记得登记进 `manifest.yaml` 的 `provides.knowledge`——那份清单归目标，脚本不替它写。

### 4 确认

```
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --check --target <目标根> --package <包根>
```

四组，全过退出 0：

| 组 | 判什么 |
|---|---|
| diff 落点 | 升级没有伸进 `knowledge/` 与 `scripts/adapters/`；`manifest.yaml` 的 `provides.knowledge` 与升级前逐字相同 |
| ⑤ | 入口文件（`AGENTS.md` / `CLAUDE.md`）含扩展段与 `<!-- story-ext:begin -->` … `<!-- story-ext:end -->` 标记区 |
| ⑦ | 目标 `.gitignore` 有章草稿目录那一行——本命令自己不落工作件，没有第二行要挡的 |
| ⑧ | **包**的 `skills/story/scripts/` 这一层只有 `core/` 与 `adapters/`，根下除了 `README.md` 没有独立文件 |

`--check` 不查工作区干不干净（那是 `--apply` 的前置）：它只读，而本仓自适配跑的就是它。
包与目标是同一棵树时 diff 没有对象，那一组不判，⑤⑦⑧ 照跑。

## 对接层的输出合同

`adapters/` 里那三个由目标仓自己实现，包里那份是替身。它们的 CLI 参数、stdout JSON 与写盘落点写在 `<ext>/skills/story/scripts/README.md`——那是目标仓实现自己那份时的唯一依据。

## 不做的事

- **不做历史兼容**：旧结构、混合目录、部分迁移状态都不进设计、不进分支、不进验收。已有产物由用户手动调整。
- **不动 knowledge 内容**：升级不读不写，首次不填包里的正文。
- **不动 framework**：包不依赖任何 framework 改动。
- **不动目标 `framework.config.json` 的其它键**：它是目标工程的架构 DSL 真源，adapt 只在首次安装时确保 `paths.extension_dir` 存在。
