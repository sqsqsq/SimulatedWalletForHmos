# 步骤 2 · Adapt 轻量化：按目录换，核安装结果

> 状态：实施 `e54b6c2e`、返修 `f23b245f`（`reviews/02` 收口）、返修二 `cdb24f20`（A12 + F1–F3）、返修三 `2fe674f4`（N2 关闭）、返修四（`reviews/05` R1：`yaml-lite` 标量词法）。**四轮返修的问题均已落地，等评审复核**。
> 需求真源：[01-Adapt 轻量化](../../../../spec/1.9.1/2026-09-04-会议转写修正需求输入/01-Adapt轻量化/00-需求澄清.md)（A1–A12、§4 所有权表、§5 验收方向）。
> 依赖：与步骤 1 串行（两步都改 `skills/story/SKILL.md`），先 1 后 2，已按此做完。
> 做完：已集成的目标仓升级 = 换 `core/`（业务仓来源连同 `adapters/`）+ 覆盖跳板 + 合成 manifest + 核安装结果；目标的知识、激活清单、身份（`name` / `description`）一个字节不动；空仓装完就能跑、模型写完画像自检仍过。

## 1. 这一步是重写，不是改造

用户 2026-09-07 明确：**按最新设计重写脚本，不要基于旧功能改**。旧实现（403 行脚本、200 行 SKILL）整体作废；它的重量来自三个已不成立的前提（需求 §3）：知识要在包与目标之间做语义合并（A2 否）、所有权靠路径正则与文件头自述推断（A6 否）、要识别历史版本与混合状态（A1 否）。前提没了，「读两棵树 → 逐文件判 → 写四段方案 → 确认 → 写入 → 校验」这条链也就没了。

## 2. 所有权：目录表达，来源由包的身份决定

```
<ext>/skills/story/scripts/
├─ core/       公共，升级按目录替换（含删除已退场文件）
└─ adapters/   story.js / token.js / review.js——看来源（下表）
<ext>/knowledge/            目标的，升级不读不写
<ext>/manifest.yaml         机制登记归包；name / description / provides.knowledge 归目标
<ext>/ 其余                  机制，升级整份换掉
```

**两边都进子目录，`scripts/` 根下只有 `README.md`**（用户 2026-09-08 裁定；`--check` ⑧ 守）。新增的公共脚本一律进 `core/`，含步骤 5 的会议解析。`README.md` 写两个目录各归谁与三个对接脚本的输出合同——内网实现自己那份时的唯一依据。

**两种来源**（A12，用户 2026-09-08）：

| 来源 | `adapters/` | 为什么 |
|---|---|---|
| Demo | 不给、不覆盖 | 它的三个 js 是用本地目录模拟需求系统的替身 |
| 业务仓 | 整体替换为来源版本，与 `core/` 同一待遇 | 业务仓对接同一个需求系统，共用一套实现 |

**来源看包 `manifest.yaml` 的 `name`**（用户 2026-09-08 裁定）：Demo 的包 `name` 是 `wallet-sdk-demo`，其它都是业务仓。不看仓名长相、目录或脚本内容，不加 CLI 参数。`name` 能当来源标识，是因为它**归目标、升级不改**——每个仓的 manifest 里那个名字始终是它自己的。不另加 `provides.adapters` 字段：归包会在 Demo 升级时把业务仓的声明盖成替身，归目标则每仓装完都要人改一次。

**`name` 的值按 YAML 实际值读**（`reviews/04` N1，返修三）：`name: "wallet-sdk-demo"`、单引号、行尾带注释，与裸写是同一个值。用 `yaml-lite` 读，不取冒号后的原始字符串；缺失或非法值明确报错，不当业务仓——判错的方向是把业务仓的真实现盖成替身，那是最坏的一种错。

**`name` 与 `description` 归目标**（用户同日裁定）：它们说的是这个仓叫什么、是什么；`version` 归包——目标从它看出自己拿到的是哪一批产物形态。首次安装时脚本按目标 `framework.config.json > project_name` 生成初值，描述由模型在首次那一次确认里改准。

**跳板清单登记在包的 `manifest.yaml` 的 `provides.bridges`**（四个宿主入口文件），adapt 从那里读；`framework.config.json` 不是跳板，adapt 只在首次安装时确保 `paths.extension_dir` 存在。

**manifest 合成**：包的为底；`name`、`description`、`provides.knowledge` 三处原样放回目标的。目标没有 `provides.knowledge` 块或块为空，合成结果就是空块——不用包的清单补齐（F3）。首次安装只登记初始化的各类 README；画像由模型写完后自己登记。

## 3. 写入面与自检

**写入面按来源生成一次，四处共用**：`--apply` 的复制、退场清理、写入前脏检查，`--check` 的判据，都从同一个函数取（`coveredFiles`，进目录前就排除 `knowledge/`，Demo 来源再排除 `adapters/`）。

| 位置 | 升级 | 首次 |
|---|---|---|
| `<ext>/` 机制面（`hooks/`、`rules/`、`overlays/`、`skills/`，`scripts/` 下只含 `core/`） | 整体替换 | 整体写入 |
| `<ext>/skills/story/scripts/adapters/` | Demo 来源不碰；业务仓来源整体替换 | 同左 |
| `<ext>/manifest.yaml` | 按 §2 合成 | 合成（身份取初值、知识清单只登记 README） |
| `provides.bridges` 里的四个跳板 | 覆盖 | 写入 |
| 入口文件 `AGENTS.md`（有 `CLAUDE.md` 时也写）的 `<!-- story-ext:begin/end -->` 标记区 | 只重写标记之间 | 追加带标记的一段 |
| 目标 `.gitignore` 的章草稿目录一行 | 缺就补 | 写入 |
| `framework.config.json` 的 `paths.extension_dir` | 不碰 | 缺就加 |
| `knowledge/` 各类 README | 不碰 | 写入骨架；画像由模型按 §5 写 |

**写入由脚本做**：`adapt-scan.mjs --apply` 一次做完；模型只下命令、读结果。首次安装里唯一归模型的是部件画像。

**前置检查只装在 `--apply` 上**（不满足就停，目标一个字节不写）：包登记的跳板都在；目标是 git 仓库的根；写入面上的路径没有未提交改动。写入面之外脏不拦。不 stash、不提交。

**`--check` 核的是安装结果，完全不用 git**（F2）：

| 组 | 判什么 |
|---|---|
| ① | 写入面上每个文件目标与包逐字相同；包里没有的目标也不该有 |
| ② | `manifest.yaml` 合成一遍等于盘上那份——**按块比，排除纯换行差异**（N2：目标用 CRLF 不是错） |
| ③ | `provides.bridges` 的四个跳板与包逐字相同（N2：跳板正确是 A7 的交付要求） |
| ⑤ | 入口文件含扩展段与标记区 |
| ⑦ | 目标 `.gitignore` 有章草稿目录那一行 |
| ⑧ | 包的 `scripts/` 下只有 `core/` 与 `adapters/`，根下除 `README.md` 无独立文件 |

`knowledge/` 一条都不判（F1）：首次安装后目标往知识目录写画像、放规约都正当；「adapt 有没有碰知识」由写入面的构造保证，用夹具锁，不在运行期找证据。包与目标同一棵树（本仓自适配）时 ① ② ③ 无对象，只跑 ⑤⑦⑧。

## 4. 判态：两态

目标无 `manifest.yaml` = 首次；有 = 升级（无文件要写时报「当前适配仍有效」）。历史版本识别、结构签名、混合状态处理都不存在（A1）。来源与安装状态是两个独立维度：业务仓来源首次安装同时写入 adapters；知识仍只建骨架与目标画像。

## 5. 知识：按注册校验

**没注册就不校验**（用户 2026-09-07）：`provides.knowledge` 为空或缺失 = 尚未配置知识，`activeKnowledge` 返回四类皆空，链条照走；登记了却读不到仍报错；不是数组的非法值报「类型错」。8 个调用点加 `selfCheck` 在空清单下都走得通（任务包写「本仓未配置知识」，`knowledge-use.yaml` 零条目，附录 D 不投影）。

**部件画像是首次安装时模型做的一件事**，任务写在 SKILL 首次安装那一节：看目标的架构 DSL、`module-catalog`、`architecture.md`，缺的按目录实扫；写 `knowledge/facts/component-profile.md`（`kind: facts`，节结构照本仓画像）；每条事实带仓内路径或 DSL 键名，查不到写「未确认」；摆给人确认一次（画像、`name` / `description` 初值、配置键），确认后落盘并登记进 `provides.knowledge`。

## 6. `SKILL.md`

四件事：前置（脚本查）→ 判两态（脚本判）→ 写入（`--apply`；首次另加画像与一次确认）→ 确认（`--check`）。**升级不停等**（A10）。两种来源、目录所有权、对接合同的位置都写在里面；没有「adapters 一律不碰」这句。

## 7. 不做的事

不做历史兼容（A1 / A9）；不动 knowledge 内容；不为「只有骨架」另建知识框架；不动 framework；不定升级耗时的秒数；不加来源类型参数或字段。

## 8. 验收

| # | 需求（01 分册 §5） | 怎么验 |
|---|---|---|
| 1 | Demo 向业务仓升级：知识、对接脚本、无关宿主配置不变 | 夹具目标带自实现 adapters、自定义知识与清单、改过的配置：升级后 adapters 字节不变、`provides.knowledge` 逐字不变、配置自定义键在 |
| 2 | 新仓装完只有骨架与画像，无 Demo 业务内容；空清单能跑 | 空仓首次：`knowledge/` 只有 README；`activeKnowledge` 不抛；模型写完画像并登记后 `--check` 退出 0（LF 与 CRLF 各一次） |
| 3 | 固定机制与跳板更新到目标版本，退场文件清除 | 目标退回旧态再升：退场文件消失、缺的补回、跳板与包一致；改坏一个跳板 `--check` 退出 1 |
| 4 | 同版本重复执行不损坏 | 连跑两次，第二次报「当前适配仍有效」 |
| 5 | 读取字符与耗时显著降低 | 对改动前记一次实测 |
| 6 | 必要失败有明确结果 | 非 git、写入面脏、包缺跳板、`name` 缺失或非法——各退出非 0，目标未写 |
| 7 | Demo 按目标结构交付 | 自适配通过；历史签名、`framework-patch` 零命中 |
| 8 | 业务仓来源复刻 | 业务仓来源升级：adapters 与来源一致、退场文件清除、目标知识与清单不变；首次安装得到 adapters、骨架、画像 |
| 9 | 来源值等价写法 | `name` 裸写、单引号、双引号、行尾注释四种写法的 Demo 包，对带真实 adapters 的目标升级，adapters 都不被覆盖（N1） |
| 10 | 四道门 | 离线全量、失效形态 FAIL 0、`adapt-scan --check`、`framework/` 零改动 |

## 9. 预算

`skills/story-adaptation/**` 与三个 `.js` 不占配额（预算文件「范围」段）。进配额的是 `manifest.yaml` 的 `provides.bridges`（`data` +5）与 `knowledge.mjs` 空清单那两处（±0）。总量用户 2026-09-08 签 9700。

## 10. 返修记录

- 返修三 `2fe674f4`：N1 `manifestValue` 改走 `parseYaml`；N2 `--check` 加 ③ 跳板、② 归一换行。`reviews/05` 关闭 N2。
- 返修四 R1：`yaml-lite` 的标量读取先判整串是否被引号包裹、再剥行尾注释、剥完不再处理引号，于是 `name: "wallet-sdk-demo" # source` 返回带引号的值，Demo 被判成业务仓、目标的真实 adapters 被替身覆盖。修在**词法**上：引号标量先找到收尾的那个引号，它之后只能是行尾注释；引号内的 `#` 是内容。没在 adapt 里加字符串替换或 Demo 特例。

  夹具两处：`test_adapt_source_kinds.py` 的等价写法从三种扩到五种（补引号 + 注释的两个组合）；新增 `test_yaml_lite_scalars.py` 锁标量词法本身——这个读取器此前没有自己的单测，而它的输出要参加相等判断，下次再改没人拦。
