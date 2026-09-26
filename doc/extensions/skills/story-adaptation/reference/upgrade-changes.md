# 升级演进记录

> 读者：执行 `/story adapt` 升级的维护模型。时机：`--apply` 末尾按块列出晚于目标 `adapted_for` 的条目时，逐条在目标仓做完并验证。

按扩展版本分节，每条以块开头：

| 块 | 归谁做 | 条目写什么 |
|---|---|---|
| `[知识]` | 按 `reference/knowledge-adaptation.md` 改目标知识 | 协议或约定变了什么、目标知识要改什么、怎样核 |
| `[对接层]` | 目标仓自己的 `skills/story/scripts/adapters/` | 扩展调用或读取的命令、参数、stdout、写盘落点与失败语义变了什么，怎样验证 |
| `[在途单]` | 需求负责人 | 升级前做到一半的单怎样处理 |

同一目标跨几个版本升级时，按版本顺序读完再动手：后一版改掉前一版做法的，直接做到后一版。协议正文在 `skills/story/reference/knowledge/protocol.md`，调用方式以 `skills/story/SKILL.md` 为准。

## 1.9.4

- [对接层] 命令 `review` 退出，新增 `fetch <AR单号> <token> --project-root <工程根> --out <本单 inbox>`：只读取回这张单现在关联的 AR / SR / RR 正文与评审回稿，业务文件（`AR/design.md`、`AR/review.md`、Spec、Story、Plan）不写。三份正文写进 `--out`，文件名 `AR-design.md` / `SR-design.md` / `RR-prd.md`，与本地对应文件逐字相同的不落盘；评审回稿写 `AR/story-src/review-feedback.md`；回执写 `AR/story-src/fetched.json`，逐份记 `name`、`label`、`ticket`、`status`、`digest`、`origin`、`bytes`，`status` 取 `fetched`（取到）/ `same`（与本地相同）/ `absent`（系统上没有）/ `failed`（读取故障）之一，有 `failed` 时 `success: false` 并非零退出；stdout 返回 `{ out, fetched, failed, items }`。验证：四态各造一次，`/story update` 读得到回执、`failed` 报为失败，写入范围只有 inbox 与 `AR/story-src/` 下两个文件。
- [在途单] 用 `/story review` 回流评审意见的单，改用 `/story update` 承接；review 流程留下的处置台账不再读取。

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
- [在途单] spec 的扩展章挂到「## 9. 宿主扩展治理项」下（9.1 技术契约、9.2 规约约束要求、9.3 设计模式候选登记，附录是全文最后一章），plan 的扩展章挂到「## 9. 宿主扩展」下（9.1 知识决策、9.2 埋点）。按旧章号写的单在旧版本收口，或清掉需求目录后从 `/story init` 重起。

## 1.9.7

- [知识] 每份知识的 frontmatter 写齐 `name`、`kind`、`form`、`applies_when` 四项，类型与形态只认四格（facts × facets、facts × halves、constraints × entries、patterns × halves）：逐份定格、补 `form`，只读检查按「类型 × 形态」计数核对。知识使用登记按 `name` 认知识，上下篇知识按「上篇 / 下篇」登记。
- [知识] 多步推导的项目方法写成 facts × halves（上篇给设计侧、下篇给实现侧）：spec 登记用了上篇的，plan 任务包附它的下篇全文，所以下篇要能单独读懂。
- [知识] 方法型知识里的必须设计项写成具名列，每一行要给具体值；原来合并在一格里的字段拆开。
- [知识] 上报知识写明同一统计点只走一个渠道：进统计的结果走统计上报，定位要用的原因、场景与关键状态写进它的描述字段，不再另报定位事件；定位事件只用于不进统计的过程点。逐结果要给的值里加上描述（固定说法加本次关键值及其来源）。可观测规约的「避免重复记录」同样写明。验证：走查一个统计点，能写出用哪个渠道、描述写什么、日志怎样记。
- [对接层] `fetch` 回执 `AR/story-src/fetched.json` 带取材时刻 `fetchedAt`（ISO 8601，如 `2026-09-26T08:30:00.000Z`），扩展据它判断这一轮取过上游没有，读不出直接报错。验证：update 取材后回执有 `fetchedAt`，扩展判为本轮已取。
- [在途单] 流程契约只读当前 schema（4），评审记录人工区只认「同意 / 需修改 / 暂缓」加修改意见，知识使用登记按新登记单元核；旧格式直接报错。升级前做到一半的单在旧版本收口，或清掉需求目录后从 `/story init` 重起，不手改契约、评审记录或登记去凑新格式。
