---
name: story-adaptation
description: /story adapt——在已解包 `<ext>/base/` 的业务工程内就地安装、升级、校验、清理样例并记录适配版本。所有权由目录表达：机制包在 `<ext>/base/`，对接实现固定在 `<ext>/adapters/story.js` 与 `token.js`，业务知识在 `<ext>/knowledge/`，运行时唯一清单在 `<ext>/manifest.yaml`。
---

# story adapt — 业务工程内就地安装与升级

从正在运行 adapt 的业务工程定位目标。用项目实际文件决定哪些知识成立并登记；示例只说明写法。已有知识保留有依据的差异。只有目标知识能被实际入口取得且对接已核，再完成本次适配。

路径相对目标工程 `framework.config.json > paths.extension_dir`（缺省 `doc/extensions`）。

## 所有权由目录表达

| 位置 | 归谁 | 说明 |
|---|---|---|
| `<ext>/base/` | 通用机制包 | 发行包整目录覆盖；含 `package-manifest.yaml`、`.gitignore`（忽略 `/examples/`）与首装临时 `examples/knowledge/` |
| `<ext>/adapters/story.js`、`token.js` | 业务侧 / 内网发行 | 固定对接入口，adapt 不覆盖；替身与演示样例不进通用机制包 |
| `<ext>/knowledge/` | 业务目标仓 | 脚本不读不写；首装参考 `base/examples/knowledge/` 形状并从目标实际代码与规约取证起草 |
| `<ext>/manifest.yaml` | 运行时唯一清单 | 机制登记（`docs.post_check`、六阶段 hooks/overlays/phase_bindings、`skill_assets`）由 `base/package-manifest.yaml` 合并；`name`/`description`/业务 `provides.knowledge` 归目标 |
| `<ext>/adaptation.yaml` | 业务目标仓 | 对接标记 `adapters` 与已适配版本 `adapted_for`（只由脚本最后写入） |
| 宿主入口（Skill 跳板、`AGENTS.md`/`CLAUDE.md`） | Framework | 由 `base/skills/story-adaptation/scripts/entries.mjs`（含 `framework-init` 的 `docs.post_check` 钩子）调原生桥生成器指向 `<ext>/base/skills/<id>/SKILL.md`，保护其他所有者的有效入口 |

## 解包覆盖前的 git 检查

人工或内网流程把新版 `base/` 解包覆盖进目标仓之前，必须先核对目标工程 `git status --porcelain -uall`，确认没有未提交修改会被覆盖；事后运行的 adapt 不能恢复已被手工覆盖的文件。旧版（≤2.0.5）首次切换前，在覆盖前先核写面与桥归属，再解包 `base/` 并执行一次 `node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --prepare-init`，把 `docs.post_check` 合入原位根清单；无 `framework.config.json` 的空仓首次接入先走 `framework-init CREATE` 或放置最小根清单（仅登记 `docs.post_check`），再执行 `framework-init` 生成宿主桥。`framework-init` 遇同名他属桥即使退出 0 也会跳过覆盖，随后务必跑 `--check` 核对具体缺桥宿主与冲突来源，不可仅凭退出码判断就绪。

## 你要做的四件事

### 1 就地安装 / 升级与写前核

在业务工程（仓根或仓内子工程如 `repo/apps/pay`）内直接运行：

```
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --apply
```

脚本从自身位置向上找 `framework.config.json` 定位当前业务工程，用 Git 顶层加工程相对写面核未提交改动（兄弟子工程脏文件不挡，本次将覆盖或删除的已跟踪/未跟踪文件在写入前阻止）：

- 校验 `base/package-manifest.yaml` 与合成后的根 `manifest.yaml` 能否通过目标 Framework 原生加载器；
- **旧混装首升**：先读旧 `manifest.yaml`、入口归属、适配游标与现有业务知识，保留业务知识与真实业务 `adapters/`（迁至 `<ext>/adapters/`），再退出旧 `<ext>/{hooks,rules,skills}` 并原位更新根 `manifest.yaml`，使项目级 `framework-init` 与全部阶段绑定立即可触发；
- **宿主入口**：撤下旧版受管入口，物化全部宿主入口指向 `<ext>/base/skills/<id>/SKILL.md`，保留其他所有者的有效入口；
- **使用记录**：确保 `doc/usage.json` 存在、合法且不被 `.gitignore` 挡住；
- **同版重入**：版本相同且无文件变更时，仍核宿主入口、目标知识可读性与对接状态，不凭版本号宣布完成。

### 2 知识适配与独立审查

安装或升级前先读 `doc/extensions/base/skills/story/reference/knowledge/protocol.md` 与 `doc/extensions/base/skills/story-adaptation/reference/knowledge-adaptation.md`。

- **首次安装**（或无 `adapted_for`）：读 `base/examples/knowledge/` 只作组织形状参考，不照搬示范正文；先据目标代码、架构配置与模块画像写部件定位知识并登记进根 `manifest.yaml > provides.knowledge`，再按 `--apply` 列出的演进主题逐题判适用、从项目真实文件取证起草起步知识。
- **升级**：只按晚于 `adapted_for` 的演进条目定向修订，保留已有知识中有依据的差异；没有条目且知识加载正常时无需全量重盘。
- 知识改动交回前按 `reference/knowledge-review.md` 交独立执行体审一遍，结论留进 `<ext>/.adapt/knowledge-review.md`。
- 对接层核 `<ext>/adapters/story.js` 与 `<ext>/adapters/token.js` 是否就位并按真实环境验证；未就位或未验证的在交回里明示，不以测试替身冒充通过。

### 3 校验与清样例记版本

```
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --check
node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --mark-adapted
```

- `--check` 只读核 `base/` 布局、根 `manifest.yaml`、宿主入口、`.gitignore` 与 `doc/usage.json`、知识加载可读性与对接状态；
- `--mark-adapted` 依次核宿主入口、目标知识读回与独审证据、**清理本次装入的 `base/examples/`（保留 `base/.gitignore`）**，全部成功后**最后**写入 `adaptation.yaml > adapted_for`。清理或落盘中断可幂等重入；清理失败不报适配完成、不写 `adapted_for`；
- 另起会话查看当前状态跑 `node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --status`（只读）。

## 不做的事

- 脚本不读写 `<ext>/knowledge/`、不覆盖 `<ext>/adapters/`、不改动 `framework/`；
- 不自动 stash / commit 用户工作区；
- 不迁移旧版在途需求现场（旧版按旧版收口，新需求走 `/story init`）。
