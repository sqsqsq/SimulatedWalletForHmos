---
name: story-adaptation
description: /story adapt——把 Story Extension 装到或升级到目标工程。所有权由目录表达：换 core/、覆盖跳板、按来源决定带不带对接实现，脚本不碰知识与目标身份；知识由模型按适配方法识别差异、人定范围后依据真实代码补齐。
---

# story adapt — 把 Story Extension 装到 / 升级到目标工程

**包** = 发起本命令的仓库（缺省当前仓）。**目标** = `/story adapt <目标工程>` 的参数。
路径相对各自 `framework.config.json > paths.extension_dir`（缺省 `doc/extensions`）。

## 所有权由目录表达

| 目录 | 归谁 | 复制时 |
|---|---|---|
| `<ext>/skills/story/scripts/core/` | 包 | 整份换掉，包里没有的删掉 |
| `<ext>/skills/story/scripts/adapters/`（入口、鉴权及其内部实现模块） | **看来源**，见下 | Demo 来源不碰；业务仓之间整份换掉 |
| `<ext>/knowledge/` | 目标 | 脚本不读不写；内容由你按「知识适配」一节改 |
| `<ext>/` 下其余一切 | 包 | 整份换掉 |
| `<ext>/manifest.yaml` | 机制登记归包；`name`、`description`、`provides.knowledge` 归目标 | 按这条规则合成 |

> **目标工程的 `story.js` 要实现 `fetch`**（只读取材到本单 `inbox/`，回执写 `AR/story-src/fetched.json`，
> 合同见 `skills/story/scripts/README.md`）：`/story update` 靠它取上游与评审回稿，命令失败时 update 报出来并停下。

**没有第三种要你判断的情形**：一个文件归谁，看它在哪个目录。

### 两种来源

| 来源 | 对接层 | 为什么 |
|---|---|---|
| **替身包**（manifest 写 `adapters: stand-in`） | 不给、也不覆盖 | 它的对接实现用本地目录模拟需求系统，装进业务仓会往一个不存在的地方读写单据 |
| **业务仓**（没有这个键） | 整份换成来源版本 | 业务仓对接的是同一个需求系统，共用一套实现 |

判来源看包 `manifest.yaml` 的 `adapters`——它归目标、升级不改，所以每个仓说的都是它自己的对接层。不靠仓名、目录结构或脚本内容猜。

Demo 装出来的仓没有 `adapters/`：目标要照 `<ext>/skills/story/scripts/README.md` 的合同实现公共入口及所需内部模块，或者从一个已经实现好的业务仓复刻过来。

## 对接能力交接

安装或升级前，读取包的 `skills/story/scripts/README.md`，核对本次对接能力的新增、变更与删除。逐项向目标维护者说明：哪项流程需要它、入口参数/结果/失败语义、目标需改什么、怎样验证；公共入口不变也不表示对接内部无需调整。

对照目标实现确认各项能力。所需功能尚未实现时明确列为未适配，不声称整个流程已经可用；继续按目录所有权安装机制，不自动覆盖目标对接实现或为某个项目添加复制特例。对接实现与验证由获授权的目标维护任务承担。

本命令的 `--check` 只核安装一致性，不能代替真实对接能力验证。交回分别说明机制安装结果、对接能力结果和剩余动作；Demo 替身的测试结果不冒充内网对接已经通过。

## 知识适配

安装或升级前先读两份：包的 `skills/story/reference/knowledge/protocol.md`（知识怎样描述自己、四个合法格、怎样写给模型用）与 `skills/story-adaptation/reference/knowledge-adaptation.md`（从目标仓自己的代码与业务出发写知识、走查、交回的方法与中性示例）。脚本装完机制后，按方法页完成知识部分。

## 你要做的四件事

### 1 前置（脚本自己查，不过就停）

```
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --apply --target <目标根> --package <包根>
```

它先查三件，任一不满足就退出并点名：

- **目标是 git 仓库的根**、**这次要覆盖的路径上没有未提交改动**——升级会整份换掉那些文件，没存档的改动被盖掉就找不回来了。git 在这里回答的是「你的改动存过没有」，不是「谁改的」；
- **包与目标都读得到**（各自的 `framework.config.json` 与包的 `manifest.yaml`）。

**不替用户动他的工作区**：不自动 stash、不自动提交。报错会点名脏的路径，让他自己先提交或暂存。

### 2 判态（脚本判，你不猜）

目标有没有 `manifest.yaml`——**有就是升级，没有就是首次**。历史版本识别、结构签名、混合状态处理都不存在于本实现。
版本相同且没有文件要写时，它报「当前适配仍有效」并退出 0——这只说机制不用再装，知识照样按方法页核一遍。

### 3 写入

`--apply` 一次做完全部确定性写入：删掉退场文件、复制机制面、合成 manifest、覆盖跳板、重写入口标记区、补 `.gitignore` 那一行。
你只下命令、读结果。

**升级不停等**：一次升级指令授权到写入完成加自检，只有失败才回头问人。写入面已由目录边界完全确定，没有可拍板的选项。

**首次安装多两件**，其中一件归你：

- 脚本做的：确保 `framework.config.json` 有 `paths.extension_dir` 这个键（缺就加），按目标的 `project_name` 生成 manifest 的 `name` 与 `description`，知识激活清单为空。**不放包里的任何知识**——那是目标仓自己的东西，从空的开始。
- **你做的：写部件定位知识**——回答本部件是谁、职责边界、与哪些交互方怎样交互，初析与 AR 提取靠它判断上游内容归不归本部件。这是首次安装里唯一归模型的一件事：

| 项 | 内容 |
|---|---|
| 看什么 | 目标仓的 `framework.config.json` 架构 DSL（层、模块、跨模块出口文件）、`doc/module-catalog.yaml`、`doc/architecture.md`；三者缺的按仓内目录实扫 |
| 写什么 | 一份 facts：写法见 `protocol.md`，`applies_when` 写明它回答本部件是谁、与谁交互；放在 `<ext>/knowledge/facts/` 下，文件名由你定 |
| 「能核实」是什么 | 每条事实后面带仓内路径或 DSL 键名；依据在别人手里的写明向谁取得，不写推断 |
| 停一次问人 | 摆出这份知识、manifest 的 `name` 与 `description`（脚本按工程名生成的初值，你把描述改准）、`framework.config.json` 的配置键，人改过再落盘 |

写完登记进 `manifest.yaml` 的 `provides.knowledge`——那份清单归目标，脚本不替它写。其余知识按方法页，从目标仓自己的代码与需求出发决定写哪些。

### 4 确认

```
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --check --target <目标根> --package <包根>
```

五组，全过退出 0：

| 组 | 判什么 |
|---|---|
| ① 机制面 | 这一次覆盖范围内的文件与包逐字一致，包里没有的目标也不该有 |
| ② manifest | 合成一遍等于盘上那份——机制登记跟包，`name` / `description` / `adapters` / `knowledge_adapted_for` / `provides.knowledge` 跟目标 |
| ③ 入口文件 | `AGENTS.md` / `CLAUDE.md` 含扩展段与 `<!-- story-ext:begin -->` … `<!-- story-ext:end -->` 标记区 |
| ④ `.gitignore` | 有章草稿目录那一行——本命令自己不落工作件，没有第二行要挡的 |
| ⑤ 包的脚本层 | **包**的 `skills/story/scripts/` 这一层只有 `core/` 与 `adapters/`，根下除了 `README.md` 没有独立文件 |

### 升级之后：知识要不要适配

升级的 `--apply` 最后打印「知识适配」：演进记录（`reference/knowledge-changes.md`）里晚于目标
`knowledge_adapted_for` 的条目，与按当前协议加载目标知识的结果。`--check` 通过、机制交回之后：

- 任一非空：把条目与问题原样摆给人，停一次问「现在做知识适配吗」。要做就按方法页做，交回时把目标 manifest 的
  `knowledge_adapted_for` 写成这一版；选稍后，不写任何东西；
- 都空：报一句「知识与当前协议一致」，不问。

`--check` 不查工作区干不干净、也不看 git（那是 `--apply` 的前置）：它只读，回答的是
**这个目标现在装的是不是包的这一版**。知识能不能加载、内容够不够是另一件事，交回时与它分开报（方法页「交回」）。

拿 `git diff` 判「升级碰了什么」不成立：目标自己改过知识、`--apply` 一个字节没写，
diff 照样把那处算到 adapt 头上；反过来目标把上一次升级提交了，diff 为空，装错了也看不出来。
「adapt 碰没碰 `knowledge/` 与 `adapters/`」由复制范围保证，不需要事后找证据。

## 对接层的输出合同

`adapters/` 的入口及内部模块由目标仓自己实现，包里那份是替身。它们的 CLI 参数、stdout JSON 与写盘落点写在 `<ext>/skills/story/scripts/README.md`——那是目标仓实现自己那份时的唯一依据。

## 不做的事

- **不做历史兼容**：旧结构、混合目录、部分迁移状态都不进设计、不进分支、不进验收。已有产物由用户手动调整。
- **脚本不动 knowledge**：升级不读不写，首次不放包里的正文；知识内容只由你在人定的范围内按方法页改。
- **不动 framework**：包不依赖任何 framework 改动。
- **不动目标 `framework.config.json` 的其它键**：它是目标工程的架构 DSL 真源，adapt 只在首次安装时确保 `paths.extension_dir` 存在。
