# 升级演进记录

> 读者：执行 `/story adapt` 升级的维护模型。时机：`--apply` 末尾按块列出条目时，逐条在目标仓做完并验证。知识与对接层列晚于目标 `adapted_for` 的条目；目标没有 `adapted_for`（首次安装或从未适配）时从最早一节列起。

按扩展版本分节，每条一行、以块开头，不用子项：

| 块 | 归谁做 | 条目写什么 |
|---|---|---|
| `[知识]` | 按 `reference/knowledge-adaptation.md` 改目标知识 | 协议或约定变了什么、目标知识要改什么、怎样核 |
| `[对接层]` | 目标仓自己的 `skills/story/scripts/adapters/` | 扩展调用或读取的命令、参数、stdout、写盘落点与失败语义变了什么，怎样验证 |

同一目标跨几个版本升级时，按版本顺序读完再动手：后一版改掉前一版做法的，直接做到后一版。协议正文在 `skills/story/reference/knowledge/protocol.md`，调用方式以 `skills/story/SKILL.md` 为准。

## 1.9.3

本节是 1.9.3 及以前形成的知识基线，不分小版本：每条一个知识主题及它回答的问题，写法见 `reference/knowledge-topics.md` 的同名一节。目标没有这份知识时，按主题页与方法页的质量判据写一份；不适用的，交回里写明查过哪里、为什么不适用。

- [知识] 部件画像（facts）：本部件是谁、职责边界、与哪些交互方怎样交互。写法见 `knowledge-topics.md`「部件画像」。
- [知识] 工程能力（facts）：设计与编码要复用的项目已有能力在哪、怎样用。写法见 `knowledge-topics.md`「工程能力」。
- [知识] 可观测（constraints）：新增或修改业务流程时，问题定位与统计上报要尽哪些义务。写法见 `knowledge-topics.md`「可观测」。
- [知识] 安全隐私（constraints）：涉及个人数据、权限或对外暴露面时必须守的要求。写法见 `knowledge-topics.md`「安全隐私」。
- [知识] 兼容性（constraints）：改动接口、数据或版本时必须保持的兼容要求。写法见 `knowledge-topics.md`「兼容性」。
- [知识] 环境异常（constraints）：用户调整设备环境引起的异常场景要怎样处理。写法见 `knowledge-topics.md`「环境异常」。
- [知识] 性能与资源引入（constraints）：性能要守的基线，以及引入新开销时要做的评估。写法见 `knowledge-topics.md`「性能与资源引入」。
- [知识] 界面一致性（constraints）：新页面或界面改版时，不同设备形态与显示设置下要保持一致的要求。写法见 `knowledge-topics.md`「界面一致性」。
- [知识] 资源复用（constraints）：界面资源与用户可见文案何时复用、何时可以新增。写法见 `knowledge-topics.md`「资源复用」。
- [知识] 交付事项（constraints）：代码之外阻塞上线或协作、容易遗漏的交付事项。写法见 `knowledge-topics.md`「交付事项」。
- [知识] 流程编排（patterns）：业务流程多分支、各分支多步且各有失败处理时怎样组织结构；目标具备包内对应模式声明的依赖（`depends_on`）时才写。写法见 `knowledge-topics.md`「设计模式」。
- [知识] 页面交互编排（patterns）：页面内交互多、由业务结果驱动下一个交互时怎样组织结构；目标具备包内对应模式声明的依赖（`depends_on`）时才写。写法见 `knowledge-topics.md`「设计模式」。

## 1.9.4

- [对接层] 命令 `review` 退出，新增 `fetch <AR单号> <token> --project-root <工程根> --out <本单 inbox>`：只读取回这张单现在关联的 AR / SR / RR 正文与评审回稿，业务文件（`AR/design.md`、`AR/review.md`、Spec、Story、Plan）不写。三份正文写进 `--out`，文件名 `AR-design.md` / `SR-design.md` / `RR-prd.md`，与本地对应文件逐字相同的不落盘；评审回稿写 `AR/story-src/review-feedback.md`；回执写 `AR/story-src/fetched.json`，逐份记 `name`、`label`、`ticket`、`status`、`digest`、`origin`、`bytes`，`status` 取 `fetched`（取到）/ `same`（与本地相同）/ `absent`（系统上没有）/ `failed`（读取故障）之一，有 `failed` 时 `success: false` 并非零退出；stdout 返回 `{ out, fetched, failed, items }`。验证：四态各造一次，`/story update` 读得到回执、`failed` 报为失败，写入范围只有 inbox 与 `AR/story-src/` 下两个文件。

## 1.9.5

- [对接层] 入口 `story.js <init|archive|restore|fetch> <AR单号> <token> [--project-root <abs>] [--out <本单 inbox>]` 两层错误：参数错（缺命令、缺单号、缺 token、非 AR 单号、`fetch` 缺 `--out`）只写 stderr、退出码 1、stdout 不输出 JSON；命令执行出错写 `{ mode, reqNo, success: false, error }`、退出码 1；成功时 stdout 最后一行是 `{ mode, reqNo, success: true, ...命令字段 }`，日志走 stderr。验证：各造一次参数错与执行错，核 stdout 与退出码。
- [对接层] 只有 AR 开头的编号走需求系统，其余编号是本地需求，四条命令都在访问系统之前失败。验证：ISSUE、自定义名、local 开头各跑一次，都不发请求、stdout 无 JSON。
- [对接层] `archive` 覆盖系统正文前，把它备份到需求目录 `.backups/cloud/design-<时刻>.md`，返回的 `backupPath` 是相对需求目录的路径；`restore` 取 `.backups/cloud/` 最新一份写回系统。需求目录的 `.backups/local/` 归扩展，对接层不写。验证：archive 后多一份备份，restore 用它恢复系统正文，本地业务文件不变；没有线上写入授权时在测试环境核。
- [对接层] 扩展不再生成取材命令：`/story update` 由模型拿 `update --action status` 返回的 `paths`（`project_root`、`inbox`）调用 `fetch`。验证：按 SKILL 的调用写法跑一次 update 取材。
- [知识] spec 与 plan 的埋点设计靠项目上报知识：目标有上报封装的，新建一份上报知识，写渠道与已有自动采集、事件身份与 SDK 映射、结果与字段、编号登记与分配；其他 facts 里讲上报渠道的内容挪进这一份。可观测规约按「定位记录、运维统计点完整、协议字段正确、编码复用与唯一、运营采集要有需求依据」五条基线义务写。验证：拿一个真实需求能写出一个指标的统计点与各字段的值。

## 1.9.6

- [知识] 每份知识的 frontmatter 写 `name`、`kind`、`applies_when`；`applies_when` 写成「什么情况下读：它回答什么」，任务包与审查据它交给读者。`knowledge/README.md` 与 `knowledge/{facts,constraints,design-patterns}/README.md` 从激活清单与目录中删去：其中目标自己加的说明并入相应知识文件。验证：只读检查（方法页「确认与交回」）PASS。
- [知识] 面标题只写 `## <面名>`，去掉 `— confirmed: …`；标着「未确认」的面改写成确定陈述：已核的写上依据位置，依据在别人手里的写明向谁取得什么。知识使用记录按面名引用。
- [知识] 上报知识按「上篇读者 spec、下篇读者 plan、coding、review」分两篇：上篇讲指标、统计点与边界，下篇讲 SDK 行为、角色与结构、怎样用与怎样判完成；指标是由事件结果算出的比率，失败原因是随上报带的字段，耗时只在时延类指标里带。

## 1.9.7

- [知识] 每份知识的 frontmatter 写齐 `name`、`kind`、`form`、`applies_when` 四项，类型与形态只认四格（facts × facets、facts × halves、constraints × entries、patterns × halves）：逐份定格、补 `form`，只读检查按「类型 × 形态」计数核对。知识使用登记按 `name` 认知识，上下篇知识按「上篇 / 下篇」登记。
- [知识] 多步推导的项目方法写成 facts × halves（上篇给设计侧、下篇给实现侧）：spec 登记用了上篇的，plan 任务包附它的下篇全文，所以下篇要能单独读懂。
- [知识] 方法型知识里的必须设计项写成具名列，每一行要给具体值；原来合并在一格里的字段拆开。
- [知识] 上报知识写明同一统计点只走一个渠道：进统计的结果走统计上报，定位要用的原因、场景与关键状态写进它的描述字段，不再另报定位事件；定位事件只用于不进统计的过程点。逐结果要给的值里加上描述（固定说法加本次关键值及其来源）。可观测规约的「避免重复记录」同样写明。验证：走查一个统计点，能写出用哪个渠道、描述写什么、日志怎样记。
- [知识] spec 统计点表与 plan 埋点表的列由上报知识给出：机制只认 spec 表的「统计点」列、plan 表的「统计点」「责任方法」列，上篇写 spec 统计点表要哪些列，下篇写 plan 埋点表要哪些列与每列的取值来源。验证：按知识写出两张表，spec 与 plan 门禁通过。
- [知识] 上报知识下篇逐结果要给的值加「外码来源」：外部错误码取自哪个响应或回调，这种结果拿不到外部错误码写「无」。验证：按知识写 plan 埋点表，每行都有外码来源。
- [对接层] `fetch` 回执 `AR/story-src/fetched.json` 带取材时刻 `fetchedAt`（带时区的 ISO 8601，如 `2026-09-26T08:30:00.000Z`），扩展据它判断这一轮取过上游没有，读不出直接报错。验证：update 取材后回执有 `fetchedAt`，扩展判为本轮已取。

## 1.9.8

本版新增 Cursor 与 `.agents` 两份宿主入口，入口登记改为 target / source 对，均由 `--apply` 写入；目标没有需要人工适配的事项。

## 1.9.9

- [知识] 知识独立审查：已有知识按 `reference/knowledge-review.md` 交独立执行体审一遍——条目粒度与归类、项目事实的用途、跨文件重复、编码规范边界四个维度，问题回各自知识修正。核：`.adapt/knowledge-review.md` 的证据块对得上当前知识摘要、逐份四维结论完整，交回写明审查执行体。
- [知识] 敏感数据的必要业务使用与输出边界，按用途分面核实（业务处理、展示与观察性输出、跨重启存储、缺依据）。目标仓按自己的隐私规范回答：哪些业务身份必须以可识别形式交给哪些对端；展示与日志、事件出口在哪一处排除或脱敏；需要跨重启留存的敏感字段有哪些、保护方式与清除时机的依据是什么；现有脱敏封装对短标识的行为。核：规约条目与项目事实各有回答，没有依据的写成缺口。
- [对接层] `story.js archive` 与 `restore` 读回的系统正文（与附件）和上传内容不一致时（`verified` 不成立），stdout 写 `success: false` 与原因并非零退出，不再报成功。验证：让读回内容与上传不同各跑一次，核退出码与 JSON。
- [对接层] 归档改由核心入口 `story-build archive --feature <AR> --mcp-token <token>` 调对接层的 `archive` 协议（入口路径登记在章节合同 `system_archive_entry`），对接层的参数与回执不变，不需要改。核：用对接层的测试替身跑一次归档，回执字段齐全时登记成功。

## 2.0.0

- [知识] 知识的适用判断由蓝图设计作出：需求级 spec 与 `knowledge-use.yaml` 不再承载判断，设计把判断写进蓝图的知识应用决定，施工单位契约实体上的 `must` 与模式角色承接。目标知识里「替谁作什么判断」或读取时机写着 spec 阶段判断的，改成蓝图设计判断、plan 落实体、检视与测试核，写法见 `knowledge-topics.md` 各主题。核：知识里不再把 spec 写成判断的出处，`/extension inspect` 无报错。
- [知识] 埋点设计落在蓝图的精确明细：一条 `kind: event` 的明细是一个指标，先写定义段，再给表头含「统计点」的点位表；plan 用表头含「统计点」「责任方法」的逐点表落实。目标的上报或可观测知识若示范了 spec「埋点」一节的写法，改为指向蓝图埋点明细与 plan 逐点表。核：知识里不再出现 spec 埋点章节作为落点。
