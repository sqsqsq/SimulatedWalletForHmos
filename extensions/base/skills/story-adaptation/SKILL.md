---
name: story-adaptation
description: /story adapt——在已解包 `<ext>/base/` 的业务工程内就地安装、升级、校验并记录适配版本。所有权由目录表达：机制包在 `<ext>/base/`，对接实现固定在 `<ext>/adapters/story.js` 与 `token.js`，业务知识在 `<ext>/knowledge/`，运行时唯一清单在 `<ext>/manifest.yaml`。
---

# story adapt — 业务工程内就地安装与升级

从正在运行 adapt 的业务工程定位目标。用项目实际文件决定哪些知识成立并登记；已有知识保留有依据的差异。只有目标知识能被实际入口取得、独审通过且对接已核，再完成本次适配。

路径相对目标工程 `framework.config.json > paths.extension_dir`（缺省 `doc/extensions`）。

## 所有权由目录表达

| 位置 | 归谁 | 说明 |
|---|---|---|
| `<ext>/base/` | 通用机制包 | 发行包整目录覆盖；含 `package-manifest.yaml`、通用机制脚本、规则与引用，不含业务成品样例 |
| `<ext>/adapters/story.js`、`token.js` | 业务侧 / 内网发行 | 固定对接入口，adapt 不覆盖；替身与演示样例不进通用机制包 |
| `<ext>/knowledge/` | 业务目标仓 | 脚本不读不写；首装与升级按 `reference/knowledge-adaptation.md` 与 `reference/knowledge-topics.md` 从目标仓真实文件取证起草或修订 |
| `<ext>/manifest.yaml` | 运行时唯一清单 | 机制登记由 `base/package-manifest.yaml` 合并；`name`/`description`、业务 `provides.knowledge` 与合法业务自定义登记归目标 |
| `<ext>/adaptation.yaml` | 业务目标仓 | 对接标记 `adapters` 与已适配版本 `adapted_for`（只由脚本最后写入） |
| 宿主入口（Skill 跳板、`AGENTS.md`/`CLAUDE.md`） | Framework | 由 `base/skills/story-adaptation/scripts/entries.mjs`（含 `framework-init` 的 `docs.post_check` 钩子）调原生桥生成器指向 `<ext>/base/skills/<id>/SKILL.md`，保护其他所有者的有效入口 |

## 解包覆盖前的 git 检查

人工或内网流程把新版 `base/` 解包覆盖进目标仓之前，必须先核对目标工程 `git status --porcelain -uall`，确认没有未提交修改会被覆盖；事后运行的 adapt 不能恢复已被手工覆盖的文件。旧版（≤2.0.5）首次切换前，在覆盖前先核写面、旧文件归属与桥归属，再解包 `base/` 并执行一次 `node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --prepare-init`，把 `docs.post_check` 合入原位根清单；无 `framework.config.json` 的空仓首次接入先走 `framework-init CREATE` 或放置最小根清单（仅登记 `docs.post_check`），再执行 `framework-init` 生成宿主桥。`framework-init` 遇同名他属桥即使退出 0 也会跳过覆盖，随后务必跑 `--check` 核对具体缺桥宿主与冲突来源，不可仅凭退出码判断就绪。

## 你要做的三件事

### 1 就地安装 / 升级与写前核

在业务工程（仓根或仓内子工程）内直接运行：

```
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --apply
```

脚本向上找 `framework.config.json` 定位当前业务工程，在写入前核对 Git 写面、原生清单加载、旧包原件归属与宿主桥冲突：保留业务知识、业务自定义登记与真实业务 `adapters/`（旧混装迁至 `<ext>/adapters/`），退出可信旧版机制文件并原位更新根 `manifest.yaml`，物化宿主入口指向 `<ext>/base/skills/<id>/SKILL.md`，确保 `doc/usage.json` 合法且不被 `.gitignore` 挡住。同版重入仍核宿主入口、知识可读性与对接状态。

### 2 知识适配与独立审查（按情景分流）

写或改任何知识前，先读 `doc/extensions/base/skills/story/reference/knowledge/protocol.md`（四格语法与下游引用合同），再按 `--apply` 返回的状态只进入 `doc/extensions/base/skills/story-adaptation/reference/knowledge-adaptation.md` 对应分支，按需查阅 `reference/knowledge-topics.md`：

- **首次（正式知识为空）**：走 `knowledge-adaptation.md`「首次安装作者」——从工程配置、入口和一个真实常规业务操作起手，取证、用主题页查漏、一次范围确认后按四格起草起步知识并登记进根 `manifest.yaml > provides.knowledge`；
- **已有正式知识、缺 `adapted_for`**：走 `knowledge-adaptation.md`「无游标已有知识」——从基线逐主题核已有知识与目标仓真源，保留有效原文、编号与人工决定，只补漏、纠错、消重复，不自行推测游标；
- **已适配、收到版本变更**：走 `knowledge-adaptation.md`「已有知识的升级作者」——按晚于 `adapted_for` 的演进条目与当前加载错误定向修订，无适用变化且可读时允许零新增。

知识改完并自查后，按 `reference/knowledge-review.md` 交独立读者审查，结论原样写进 `<ext>/.adapt/knowledge-review.md`。对接层核 `<ext>/adapters/story.js` 与 `token.js` 在真实环境可用；未就位或未验证的在交回里明示，不以测试替身冒充通过。

### 3 校验与记版本

```
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --check
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --mark-adapted
```

- `--check` 只读核 `base/` 布局、根 `manifest.yaml`、宿主入口、`.gitignore` 与 `doc/usage.json`、知识加载可读性与对接状态；
- `--mark-adapted` 依次核宿主入口、目标知识读回、独审证据有效与对接层就位，全部通过后最后写入 `adaptation.yaml > adapted_for`；
- 另起会话查看当前状态跑 `node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --status`（只读）。

## 不做的事

- 脚本不读写 `<ext>/knowledge/`、不覆盖 `<ext>/adapters/`、不改动 `framework/`；
- 不自动 stash / commit 用户工作区；
- 不迁移旧版在途需求现场（旧版按旧版收口，新需求走 `/story init`）。
