---
name: story-adaptation
description: /story adapt——把 Story Extension 装到或升级到目标工程：换机制、搬知识、重写清单。含逐类处置表、判态规则、方案确认与写入后校验。
---

# story adapt — 把 Story Extension 装到 / 升级到目标工程

**包** = 发起本命令的仓库（缺省当前仓）。**目标** = `/story adapt <目标工程>` 的参数（缺省当前仓自身 = 重适配）。
路径相对各自 `framework.config.json > paths.extension_dir`（缺省 `doc/extensions`）。

一句话：**换机制、搬知识、重写清单**。你读完包与目标两棵树，按 §2 表逐文件判，写成一页方案，
用户点头后再写入，写完跑校验。方案没点头之前，目标一个字节都不写。

## 0 前置（不满足就停，不要继续）

- 目标根有 `framework/` 与 `framework.config.json`；
- 目标 `framework/package.json` 的 `version` ≥ 包 `manifest.yaml` 声明的下限；
- 包声明的必需 framework 文件在目标就位；
- 缺任何一项：列出缺什么，停。

## 1 判态

读目标 `<extension_dir>/manifest.yaml` 的 `version`，与包的比：

| 情况 | 态 |
|---|---|
| 目标无 `manifest.yaml` | **首次** |
| 低于包 | **升级** |
| 与包相同 | **重适配** = 升级动作的子集：§2 表的机制行**不执行**，只做知识结构、索引表行、manifest、配置键。无变化就报「当前适配仍有效」，不动任何文件。但若 §3 扫描发现机制目录不等于包（上次升级中断），改按升级走 |
| 无 `version`，命中下方历史签名全部三条 | **旧版**，按升级走 |
| 无 `version`，签名只中一部分 | **停下问用户**来源版本，不要自行判定 |

历史版本结构签名（识别数据，随版本而变）：`hooks/constraint-application.md` 存在 ＋
知识文件平铺在 `knowledge/` 根下、没有按类分目录 ＋ 没有 `knowledge/facts/` 目录。

## 2 每个文件怎么办

| 目标仓里的东西 | 首次安装 | 升级 |
|---|---|---|
| `hooks/**`、`rules/**`、`skills/story/**`（`scripts/*.js` 除外）、`skills/story-adaptation/**`、`knowledge/README.md`、`AGENTS.section.md`（包有才有：渲染进入口文件的实例扩展段）；仓库根四个 story 跳板 | 从包整体复制 | 目标这些目录**整体删掉**，再从包整体复制——旧文件自然消失，新文件自然出现。目标改过的机制文件在方案第一段点名「升级会覆盖，改动迁到哪」 |
| `skills/story/scripts/*.js`（需求系统对接） | **看发起方**：包内这些 js 文件头自述为「本地替身 / 模拟」→ 不复制，目标要按自己的需求系统写，方案登记「数据对接待适配」；否则（已适配仓发起）→ 整目录覆盖 | 同左 |
| `knowledge/constraints/*.md`、`knowledge/design-patterns/*.md` —— **包里有的** | 从包复制，默认已确认、**默认在清单**（规约与模式是随包直接维护内容；缺 SDK 或既有案例只在方案里登记证据缺口，不删文件、不撤出清单） | 目标有同名的**换成包的版本**；**包新增的域 / 模式复制过去**，同样默认已确认、默认在清单 |
| 目标自己加的规约域 / 模式文件（包里没有同名的） | — | **原样保留**，仍在清单 |
| `knowledge/facts/*.md`（工程事实） | 从包复制为样板、frontmatter 加 `confirmed: 未确认`、**不进清单**；方案第三段按目标真实源码逐面填成已确认（附文件:行），填不了的登记证据缺口 | **正文一字不动**；只按包的新目录结构搬位置、补 frontmatter 键；包新增的事实面文件作样板未确认 |
| `knowledge/*/README.md`（索引） | 无表的整抄包（它只是读法）；有表的表前抄包、表行按目标目录里实际文件重算（目标原有行照抄，新文件取包内行） | 同左 |
| `manifest.yaml` | 手写合成：`schema_version`/`version`/`description`、`provides.hooks`、`provides.phase_rules_overlays`、`provides.skills` 里本包自带的两项抄包；`provides.knowledge` = 已确认的事实文件 + 全部规约与模式（含目标自加）+ 各级 README；目标其它 `skills` 与 `skill_assets` 原样保留 | 同左 |
| 目标自己的其它 `skills/*`、包不认识的任何文件 | 不动、不复制 | 不动 |
| `framework.config.json` 里包要求的配置键 | 核对；缺的在方案里提议值（目录类的值须是目标真实存在的目录；列表类只追加不删目标已有条目）；用户点头才写 | 同左 |
| `<extension_dir>/adapt/`（本命令的工作目录：`plan.md`、`before.json`、`installed.md`） | 目标所有；本次写入 | 不删；下次覆盖同名文件。**包不交付它**。`installed.md` 只记日期、发起方、缺口清单——**不记版本**，版本的唯一真源是 `manifest.yaml` |
| 包新增的知识字段 / 表列 | **不补列**（缺列由框架按声明默认值派生）；方案第三段登记「包新增字段 X，目标知识待填」 | 同左 |

## 3 读两棵树

```
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --scan --target <目标根>
```

它列出：机制目录逐文件（目标独有 / 包独有 / 同名有差异）、目标知识文件的 frontmatter 与所在目录、
目标 `provides.knowledge` 清单、包内对接 js 是否自述替身、目标自定义文件的内容指纹，
并写 `<目标 extension_dir>/adapt/before.json`。**清单是给你看的，判断由你按 §2 表做。**

## 4 写方案

写到 `<目标 extension_dir>/adapt/plan.md`，四段固定标题：

1. **机制与跳板**：新增 / 删除 / 覆盖逐文件；目标本地改动过的机制文件与迁回建议；
2. **知识**：事实文件逐个 保留 / 移动到 / 补键；包内同名规约与模式的换版本清单；目标自加文件的保留清单；
3. **待核实**：每个待填的事实面、每条随包能力在目标的对应物——已核实的写证据（`文件:行`），
   核实不了的写「证据缺口」；包新增字段待填项；manifest 与索引 README 的合成说明；配置键提议；
4. **执行**：写入顺序；写完要跑哪些校验。

## 5 确认（用户拍板）

展示 `plan.md` 全文，再给选项：`1=按方案执行` / `2=修改方案` / `3=放弃适配`。
同轮附编号菜单。**选 1 才动手**；动手前先把决策复述一遍。

## 6 写入

按顺序：机制 → 知识 → 数据对接 → 索引 README → manifest → 配置键 → **重渲染入口文件**（包有 `AGENTS.section.md` 时：按目标 framework 的用法跑 `render-agents-md`，让 CLAUDE.md / AGENTS.md 的「实例扩展」节带上这一段；这一步漏掉，目标的主 agent 就不知道要先读各阶段须知）。

## 7 校验

```
cd <目标>/framework/harness && npx ts-node harness-runner.ts --phase extensions
node <包>/skills/story-adaptation/scripts/adapt-scan.mjs --check --target <目标根>
```

前者确认 manifest 每条路径都存在（有一条不存在，框架会清空全部扩展能力，而且不会在阶段里报错）。
后者核五件事：机制目录 == 包、目标所有的知识文件旧内容仍在、清单里没有未确认的文件且路径都在、自定义文件没动过、入口文件（AGENTS.md，及存在的 CLAUDE.md）含 `AGENTS.section.md` 全文（包没有该文件时跳过）。

任一 FAIL → **照它报的那几项改，再重跑校验**。它点的是具体位置——机制缺哪个文件、
知识缺哪条事实、清单里哪个还是未确认、哪个自定义文件被动了——直接改到位即可。
**证据缺口不是失败**：未确认的事实文件不进清单、在 `installed.md` 里列出来，
目标工程把槽填了之后重跑一次本命令即可。

## 8 收口

写 `<目标 extension_dir>/adapt/installed.md`（日期、发起方、缺口清单），
再报告：态、动作计数、未确认清单与证据缺口、下一步。

## 9 填事实的取证顺序

目标源码 > 目标配置与依赖 > 目标既有业务案例 > 用户口述。
**核实不了就不写**——登记成证据缺口，不照抄包里的内容，不虚构 API、事件或结果。
