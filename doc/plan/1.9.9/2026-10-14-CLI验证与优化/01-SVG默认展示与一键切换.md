# SVG 默认展示、自动恢复与 AR 一键切换

> 2026-10-14：本稿的未实施方案与执行安排已由[全功能优化实施方案](../2026-10-14-全功能优化实施方案/00-实施总览.md)统一替代。本文保留为来源与历史依据，不再作为当前实施入口；原始CLI分析与证据仍有效。

必读：[总览](00-本轮总览.md)、[设计者澄清 §6](../澄清-设计者说明.md)。2026-10-14从原P4整理迁入，本稿承接已有图义与切换机制，新增自动恢复及一键入口；本分册按用户 2026-10-12 的重设计裁定定案，R4 spec 及前轮评审中与之冲突的交付/打包要求不执行。当前执行 G630；初始批准 G650、此前收减 G430 及 X40 估算保留在总览预算记录中，不重置累计。本次按用户 2026-10-13 裁定局部修订已实施机制：本地默认可用 SVG，由 Extension 自动管理临时 Mermaid 操作与恢复；不修改 adapters 的视图职责。

## 1. 目标、范围和所有权

只处理 `AR/story.md` 中 Mermaid 可表达的流程图类，六类指导仍用于流程/分支、时序、状态、对象关系、架构责任、依赖顺序。Mermaid 表达不了的图型不在本版，不借视图能力增加业务图型承诺。

每张图只有一份 Mermaid 语义真源。作者依据它按六类指导重述为 SVG，可换布局、拆泳道和合并表达上的冗余；不增加、删除或改变关系、条件、责任及结果。SVG 是本地阅读视图，不上传、不作业务决定的来源，也不改变正式审查对象。

本地完成态默认展示可用 SVG，读者仍打开同一份 story.md。Extension 的归档、update、Story 生成/检查/状态命令在确需正式读取时实际切回 Mermaid，操作结束后自动恢复当前可用 SVG；没有可用视图的图块保留 Mermaid 并逐项说明。脚本不做“两份字节不同但指纹视为相同”的归一化计算。Spec、Review、原图与其图片取舍路径保持原状。

用户已确认本次自动恢复边界限于 Extension 拥有的上述命令；Framework 原生 harness/独立审查运行期间仍保持 Mermaid，不在其尚未读完时恢复 SVG。本次不承诺原生 harness 退出即自动恢复，不修改 Framework。SVG 仍由模型重述并完成三层质量核对，命令不自动绘制或伪造视图。

本版退出 zip、引用闭包打包、系统图片上传、派生 SVG 纳入 story_digests、资源注入 pre_verifier、R4 导致的 flow schema 4→5 迁移。P1 的材料 schema 1→2 属于来源集合职责，继续实施。

## 2. 图块及切换合同

### 2.1 落点与绑定

本地 Mermaid 源放 `AR/story-src/figures/<图块ID>.mmd`，SVG 放 `AR/figures/<图块ID>.svg`。ID 是文档内稳定身份，不用图序/章号作 ID；章节移动或重新编号不改变 ID，语义图被替换时显式重建对应视图。

脚本给选中的 Mermaid 围栏加管理边界：`<!-- story-figure:<ID>:begin -->` 至 `<!-- story-figure:<ID>:end -->`。边界内只有该图的 Mermaid 围栏或 SVG 图片引用；图前图后正文留在块外，不纳入切换。源文件保留 Mermaid 中的现有图源标记，切回后现有 images.mjs 仍按原规则核上游承接。

初次准备从已完成且尚未受管理的 Mermaid 围栏提取源；一旦建成 `.mmd`，它就是该 ID 的唯一语义真源。之后修改图义只改源，mermaid 模式按源重建正文，不从 SVG 或旧正文反写源。SVG→Mermaid 是还原同一源，不是反编译。脚本管理区禁止手改；正文段落可正常修改。

共用实现放 `core/story/figure-view.mjs`，由现有 story-build 的 `view --mode prepare|mermaid|svg|toggle --feature <名>` 消费。无 --id 的 prepare 只为未管理围栏首次建源和边界；已有源路径不允许无条件覆盖，冲突须先明确身份。`prepare --id <ID>` 改为从已有 `.mmd` 显式重建这个 ID 的管理区，绝不从正文覆盖源；源缺失则报缺口。mermaid 还原源，svg 切到完成质量核对的视图。不另建形式状态、归一化指纹或第二份权威源。

自动入口进入正式读取前调用 mermaid，最外层 Extension 操作退出时调用 svg；不自动为未知内容编号或创建 SVG。成对且唯一的 ID、可读源、块内恰好一个合法 Mermaid 围栏或该 ID 的 SVG 引用，就是可以按源重建的结构；其中 Mermaid 文字与 `.mmd` 不同不是结构损坏。脚本不猜是谁改过，两种来源的差异都按同一权威 `.mmd` 重铺，并在输出说明该 ID 已从源刷新，不静默丢弃差异。

孤立标记、重复 ID、源缺失、块内夹了正文等结构损坏，自动入口整次不写；点名损坏的结构与恢复入口。边界仍可唯一定位且源可读时，显式 `prepare --id` 可从源重建块内内容；边界无法唯一定位或源缺失时先恢复正确边界/源，不按相似文本猜，也不从坏正文生成新权威源。源可从既有备份或作者按真实依据恢复，不得把“重建”实现成正文覆盖源。

### 2.2 更新与失效

`.mmd` 是唯一可编辑语义真源；SVG 的 `<metadata>` 保留生成时采用的 Mermaid 原文，作为视图来源快照。切换时仅按原文精确比较检查“视图是否仍对应当前源”，不做图义推断，也不新增哈希、版本号或状态机。快照是派生视图的来源证据，不能反向改写真源。

源变化后旧 SVG 不再提供默认阅读视图，须重新重述、结构检查、渲染核和对照审。只改 SVG 布局，重新完成该图的视图质量核对即可，正式 Mermaid 审查不重派。元数据对应只证明源版本相同，不证明 SVG 语义等值。

R01 关闭反例：当前为 Mermaid 时改 `.mmd`，下一次 mermaid/正式入口应将新源写进图块并由既有成文检查发现真实改动；当前为 SVG 时改源同样成立。两种形态均不能通过 `prepare --id` 把新源退回旧内容。只改变派生区刷新规则，不改变正式审查必须读实际 Mermaid 正文的纪律。

相同目标形态重跑零改写；Mermaid→SVG→Mermaid 必须精确还原管理块的 Mermaid 字节和现有图源标记，块外正文及人工改动不变。view 命令不跑 number；编号/章提交在 Mermaid 形态执行，SVG 引用的展示图题在切换时从当前文档派生，不反写 Mermaid 源。prepare 是一次内容结构改动，完成后照常成文登记和正式审查，不能将添加管理标记伪装为已审原稿。

## 3. Extension 拥有一次操作的切换与恢复

### 3.1 已核事实与边界

- `core/story-build.mjs::main` 当前在创建 ctx 后统一切 Mermaid，`core/story/context.mjs::fail` 直接 `process.exit(1)`；若仅在外层加 finally 而不处理该退出，失败时恢复不会执行。
- `core/story_flow.py::main` 在 VIEW_READERS 分派前调用 `ensure_mermaid`；`flow/lifecycle.py` 调用 project/number/build/check 子进程，随后才登记摘要。子进程不能各自提前恢复 SVG，否则父进程登记的就变成阅读形态。
- `flow/update.py` 的 inputs/prepare/status/close/restore 都由同一分派进入；prepare 保存 before，close 保存 after，restore 写回 before。这些读写必须全部在 Mermaid 操作范围内结束，再恢复展示。
- `adapters/story.js archive <AR> <token> --project-root <root>` 现有协议返回 JSON，成功含 `success:true`、`verified:true`；它上传当前 story 并读回，不认识视图。底层 adapter 的备份/真实系统接入继续归目标仓。
- Framework 3.0.0 的 `harness/harness-runner.ts` 第1074行调用 pre_phase，第1124–1127行调用 pre_verifier/post_verifier/post_phase，之后第1175行才 collectContextFiles、第1201行构造审查材料。**post_phase 不是可安全恢复 SVG 的结束点**；不得因钩子名称看似合适就把恢复接在那里。

### 3.2 公共命令的执行边界

复用 `figure-view.mjs` 的同一切换器，为现有命令增加局部的“进入 Mermaid → 执行业务 → finally 尝试 SVG”保护。它只管理本次进程调用，不新增持久形态状态、锁服务、任务调度器或 Framework 包装平台。必要性是同时覆盖成功、失败和嵌套调用；仅在方法页写几步或只在成功分支补切换都不能满足用户目标。

| 入口 | Mermaid 范围包含什么 | 自动结束动作 |
|---|---|---|
| story-build 的 skeleton/chapter/project/number/build/check | 当前命令的全部读取、改写、编号和判定 | 对操作后的当前源恢复可用 SVG |
| story_flow 的 story/status/round/reopen/complete/archived | 当前动作及它启动的内部检查、登记与摘要计算 | 最外层动作结束后恢复，不让子检查提前恢复 |
| story_flow update 的 inputs/prepare/status/close/restore | 当次读取、变更比较、before/after快照、收口或恢复写回 | 每次命令返回都恢复，不等整轮update完成；失败也尝试恢复当前现场 |
| 下节统一 archive 命令 | 交付门、adapter上传读回、归档登记 | 全部步骤结束或任一步失败后恢复 |
| 人工 view prepare/mermaid/svg/toggle（含AR启动脚本） | 显式指定的操作 | 保持人指定的结果，不被自动恢复抵消 |
| 原生 harness / pre_verifier /作者任务的正式读取 | 原有 pre_phase、单独读取入口的 Mermaid 前置 | 不在尚未装配/审查完时恢复；不归本次自动退出边界 |

嵌套由机制传递私有调用上下文：最外层拥有恢复责任，内部调用只执行 Mermaid 前置和业务。可以用现有 subprocess 的私有参数/环境传递限定到同一工程、同一需求的“外层已拥有恢复”标记；该标记不写盘、不进入用户方法页，不豁免任何门禁，不由模型填写。子进程不得提前恢复；独立调用同一命令则自带完整切换与恢复。不可仅按“当前已经是 Mermaid”判断自己是否拥有恢复责任。hooks/author/pre_verifier及正式post_check内部经flow/client查询状态时，调用者明确属于正式读取范围，查询不得自行恢复SVG；这是内部调用协议，由代码传递，不要求模型设置标记。

切入失败（坏边界、重复ID、缺源）时业务不执行，维持切换器的整次零写入保证，不在 finally 又猜测改写坏块。成功切入后，无论业务成功、返回失败还是抛异常，都尝试恢复**操作后的当前图源**；不把入口保存的全文写回，避免覆盖本次业务修改和人的内容。恢复不跑 number，不写新的材料/成文登记。

JS 在命令业务范围内把直接 process.exit 改成可返回/抛出的退出结果，最终退出集中到恢复之后，保留原退出码与诊断；不改全仓异常框架。Python 用同等的 try/finally 边界。进程被强杀、断电不可能保证 finally 执行：明确此限制，下一次正常 Extension 命令按当前源处理并恢复；可人工 `view --mode svg`，不制造持久恢复状态机。同一需求的操作仍串行，不引入新的并发承诺。

### 3.3 archive 从模型三步改为一个核心命令

正式入口定为：

```text
node doc/extensions/skills/story/scripts/core/story-build.mjs archive --feature <AR> --mcp-token <token> [--project-root <root>]
```

沿现有 command 分派实现专用归档动作；必要的局部实现可拆在 `core/story/`，不是新增通用运行器。模型只调用这个入口，不再排列三条命令：

1. 核需求与参数，切入 Mermaid；调用现有交付门，失败则不访问系统。
2. 按现有 adapter CLI 协议调用同一安装包 `scripts/adapters/story.js archive`，参数数组传递并显式给工程根。必须同时满足退出0、可解析回执mode/reqNo对应本次归档、success/verified/archived/reviewArchived为true（沿现有archive回执）；缺回执、坏回执、非零或 verified=false 均不登记。保留原诊断，日志不回显 token，不靠 shell 拼命令。
3. 调现有核心 archived 登记与其校验，不复制状态算法。它作为内部调用保持 Mermaid，不能独立抢先恢复；登记成功后由最外层统一恢复 SVG。

adapter只负责需求系统通信、备份、上传与核读回，**不加入切换、恢复或调用core的代码**。Extension 调用 adapter 是业务访问，不是把视图职责下放。适配后的真实 adapter 继续满足原有协议；升级说明告知官方归档入口改变，不要求目标仓照抄本仓替身。

`story_flow.py archived` 保留为既有登记能力及异常后的本地补登记入口，不再作为正常归档流程中由模型记住的第三步。已确认上传成功而本地登记失败时，输出“远端已核验、本地未登记”和补登记的实际入口，后续只补本地登记；不得为本地错误自动重传。远端核验失败不宣布上传成功、不回滚远端；按adapter现有恢复语义报告。没有远端核验依据时不能凭一个恢复参数宣称已上传。

### 3.4 恢复结果、过期提示与错误优先级

操作结果与阅读视图结果分开交回。JSON消费者保留现有业务字段，增加 view 结果（恢复SVG的ID、保持Mermaid的ID及原因、恢复错误）；文本命令同样逐项输出，不要求模型从stderr猜发生了什么。

| 情况 | 必须交回 |
|---|---|
| 有当前有效SVG | 自动恢复该图；既有 `.mmd` 与正文外区域不变 |
| SVG缺失 | 保留Mermaid，点名ID与预期SVG路径，说明尚未生成阅读图 |
| SVG快照过期 | 保留Mermaid，点名ID、源与视图路径，说明源已变、旧视图未采用，要求按当前源重述并重做质量三件套；不自动绘制或改metadata冒充新图 |
| SVG结构/引用不合法 | 保留Mermaid，给出结构检查原原因和视图修复入口 |
| 无管理图/无图 | 无需恢复，不凭空生成资源 |
| 业务失败但视图可恢复 | 保留原业务失败与退出码，仍恢复可用SVG；恢复不等于业务通过 |
| 业务成功但视图恢复I/O失败 | 明确哪些业务动作已完成、视图未恢复及仅补视图入口；业务成功不伪报失败重试上传。保留业务退出码，view显式失败，stderr同时可见 |
| 业务和恢复同时失败 | 两类错误都保留，原业务错误优先，不用恢复异常覆盖它 |

“默认 SVG”表示优先恢复已具备有效视图的图块；不把生成/渲染/独审未做完的SVG自动算作通过。图变更后的生成仍归作者，三层质量责任不变。人工 mermaid 模式保留，后续正式 Extension 命令完成后再次按默认规则恢复可用SVG。

### 3.5 AR 下的一键切换入口

用户2026-10-13要求：每个需求的 `AR/切换视图.cmd` 可在Windows资源管理器中双击，无需填写工程根或需求编号。它是本地阅读工具；模板与切换实现归Extension，生成到需求目录的是可再生入口。只新增这一种Windows启动文件，其他平台继续用已有Node命令，不为本需求增加多平台启动器。

**切换真源**仍是 `core/story/figure-view.mjs`。新增 `story-build.mjs view --mode toggle --feature <名> [--project-root <根>]`，先读取并校验管理块的实际形态，再选择目标，不调用会先改形态的 `story_flow status` 来猜当前状态：

| 当前盘上状态 | toggle结果 |
|---|---|
| 至少一个合法管理块当前显示SVG（包括SVG/Mermaid混合） | 全部受管理图切回Mermaid |
| 全部合法管理块当前显示Mermaid | 尝试切到可用SVG；缺失、过期、结构不合格的逐图保留Mermaid并说明，允许得到混合形态 |
| 没有管理块，包括仅有未prepare的Mermaid围栏或无图 | 不写文件，说明没有可切换管理图；有未管理图时给prepare入口，不替人自动prepare或生成SVG |
| 管理边界损坏、重复ID或缺源 | 沿既有结构合同整次零写入，报告原因及修复入口 |

toggle只是选一次目标，随后复用已有mermaid/svg实现；不得在CMD中另写状态判断、过期判据或图块替换。显式人工命令不进入§3.2结束时默认恢复SVG的分支，保证“切回Mermaid”不会立即被切回来。再次archive/update等正式Extension操作仍按默认恢复规则执行；不是新增长期显示偏好状态。

**启动与定位**：CMD只完成运行时定位、调用和结果展示。从自身所在AR目录定位需求目录，向上寻找最近的 `framework.config.json`，按配置的features_dir验证此需求位置，并按extension_dir定位当前安装的core入口；不依赖启动工作目录，不写维护机绝对路径，不把生成时的需求名或安装位置写死。配置坏了、位置不匹配、Node/核心入口缺失时明确失败，不越过坏配置猜另一个工程。可以用Windows自带PowerShell读取配置，调用Node时逐参数传递；中文、空格及shell特殊字符路径不得被拼成可执行语句。无需管理员权限、无需修改全局执行策略。双击后保留结果窗口供人查看，再保留核心退出码；不用颜色或一闪而过的窗口代替缺口说明。

**文件名及白名单**：在已有 `story-chapters.json` 登记单一字段 `local_reading_entry: "切换视图.cmd"`，生成器、`context.mjs::AR_ROOT_FILES` 的本地工具扩展项和必要的update排除从该字段取名。只放行这一精确文件名，不放行全部cmd/ps1/js或任意可执行文件；其他过程件仍放story-src。白名单说明和对应测试从“只有交付文档与单据身份”改成“交付文档、单据身份与这一项本地阅读入口”。不在机器维护合同AGENTS中增加宽泛例外。

**生成入口**：复用 `story-build build`——存在story.md且该命令正常完成时创建/刷新启动文件，正常 `story_flow story` 已调用build，因此新Story完成登记时入口已在。显式 `view --mode prepare` 成功后也调用同一生成函数，供已有Story补齐。没有Story时不生成；check/status/单纯toggle不补写入口。启动文件丢失可重跑上述生成入口，不依赖模型手写CMD。生成内容逐字相同则零改写；模板更新仅覆盖带本工具明确生成标记的文件。同名无标记文件按冲突报出并保留，不能覆盖用户文件或因此跳过其他白名单检查；如业务产物此前已写，按P7报告已生效范围。

**生命周期与排除**：脚本不上传，不进materials/origins/digest、story_digests、语义读审材料、两组七件金样或update八项业务比较。update的before镜像与restore删除/覆盖枚举对这一精确路径采用同一排除规则，保留本地当前工具，不让旧业务快照退回启动模板；不豁免同目录其他文件。核现有Framework生产材料函数与实际context枚举：只增删/刷新入口文件不得改变正式审查身份；若发现未预期纳入，回其真实枚举者定位，不改只读Framework或做哈希归一化。adapter仍只接收原有Story/Review，不读取该脚本。

产品指引在story-write、svg.md及SKILL说明双击用法、混合形态规则、过期提示与正式作业期间不并发操作。本地入口是对现有手工Node切换命令的便利用法，后者保留；没有新的图义、状态库或运行顺序职责。

## 4. 质量三件套

1. **结构检查**：`core/story/figure-check.py` 用标准库 XML 核 svg 根、合法 viewBox、管理 ID 对应及引用。只校验确定性事实，不按字符宽度估算判内容可读。SVG 使用本地可解析/内嵌资源，绝对机器路径、逃逸引用、缺资源报错；不扩展为全工程资源闭包或打包器。
2. **渲染核**：用宿主可用预览工具实际渲染，由能看图的人核文字、裁切、遮挡和连接。无渲染/看图证据则该视图未完成，XML 通过不能代签。临时预览证据放既有工作件位置，不作为第二个交付版本。
3. **对照审**：独立于 SVG 作者的审查者同时读 Mermaid 源与 SVG 渲染，逐关系核分支条件、正常/异常终点、先后、状态迁移、数量与责任；重述可以换布局，不能多画分支、漏去向或混责任。该视图对照审与正式需求审查分工，不把 SVG 纳入 Framework 正式业务审查对象。

源或 SVG 改动后，作者重做受影响视图的三件套并交实际结果；不得以元数据相同或“有审查报告文件”自动宣布语义等值。六类指导收束在 `reference/svg.md`，不固定图数、节点数、坐标或业务答案。

定向验证是主要能力证据：在两个 Case 已完成 Story 上指定 SVG 重述，走“源→重述→结构→渲染→对照→双向切换”，不改业务需求逼模型选 SVG，也不依赖生成时自然选型。成本照实际生成、检查、切换、返修与人工操作记录；如声称更清楚且成本不增加，仍须同语义、同质量和终点的配对证据，不预宣称更快。

## 5. 原机制实施基线与保持验收（此前G430分额）

| 步 | 文件动作 | G/X | 必须成立 |
|---|---|---:|---|
| S1 管理块与入口 | figure-view.mjs、story-build.mjs 参数及入口、story_flow.py、flow/lifecycle.py、hooks/shared/story-view.mjs、manifest pre_phase；SKILL 和 spec/update 指引；adapter 只修 verified 回执语义 | 170/20 | 准备/双向/幂等；两种形态下改源可刷新且源不回退；正文手改保留；坏块不写；正式入口读 Mermaid；官方归档链最后回 SVG |
| S2 结构与三层质量 | figure-check.py、view 的结构前置、独立对照任务与渲染要求、现有 delivery 调用边界 | 120/10 | XML/viewBox/引用正反例；多分支/漏异常由对照审发现；过期源快照拒绝旧视图；失败类别不混淆 |
| S3 六类指导与两 Case 定向验证 | reference/svg.md、story-write.md 选读与阅读窗口说明、两 Case 验证及回归 | 140/10 | 六类有验证例；两个 Case 的定向链走通；Mermaid-only/无图/原图/人工区保持 |

测试用现有 `test_story_build.py`、`test_material_rounds.py`、`test_story_update.py`、`test_verifier_report_protocol.py` 和 adapter 回归；需要局部测试文件时只为本职责分开，不新增框架。验证入口 hook 的真实执行顺序、独立 sync 绕过路径、归档后再 archived 的二次切换，以及 update 快照/恢复均为 Mermaid。

本版 schema 不因 R4 升级；没有图形归一化指纹、派生资源审查登记、zip 或通用附件协议。原05提出但尚未实施的这些动作从实施清单退出，不把“没写过的代码”记为 X。X40 仅对应真实旧指引/局部分支替换，按实际 diff 核。

1.x 与 2.x 的外部行为合同在此明确分叉：本线 SVG 为本地阅读视图，另一线 SVG 为交付物。两线不互改、不为过渡留桩；以后过渡由用户另行裁定。

## 6. 本次追加实施与验收（当前源码已完成原三步的局部机制）

这是对已实施P4的局部修改，不重做图义真源、结构检查或三层质量设计。当前P4累计G429，本次预计G190/X45（自动恢复/归档G150，加一键入口G40）；当前全版15076，预计完成15221。步骤按以下三项独立交回，先解决嵌套恢复再接归档，最后统一验证。

| 步 | 文件动作与保持项 | 预计G/X | 完成条件 |
|---|---|---:|---|
| A 操作自动恢复 | figure-view.mjs复用切换/逐图原因；story-build.mjs/context.mjs处理命令退出；story_flow.py、flow/lifecycle.py、flow/update.py接外层恢复及内部调用传递；flow/client.mjs与hooks内状态查询保持外层正式读取形态。保留全部业务检查、摘要与快照算法 | 70/20 | 生成/检查/status及update五动作成功、失败、嵌套均先读Mermaid后恢复；prepare/人工view不被抵消 |
| B 归档单入口 | story-build archive及core内专用实现串联交付门、现有adapter、archived；SKILL、spec/update/story-write、svg.md改为一个入口与自动恢复。adapters不加视图代码 | 55/15 | 模型只调用一次core命令；系统读到Mermaid；所有出口本地恢复或明确缺口；不因本地视图故障重复上传 |
| C 一键入口、消费者与回归退出 | figure-view/story-build实现toggle与共用CMD生成；story-chapters登记入口名、context白名单及update精确路径排除；相关tests、run_case、升级说明和用户指引同步。测试域不计机制预算 | 65/10 | AR入口自动生成且可双击；白名单不扩大，身份/业务比较不受脚本影响；旧三步编排与手动恢复要求退出，离线通过后按CLI取证 |

新增按分类预估：scripts_mjs G115/X20、scripts_py G29/X8、hooks G10/X7、prompts G35/X10、data G1/X0。没有新增通用调度、持久会话状态或身份归一化层；预计删除对应旧单向前置/独立恢复分支、三步指引与不再成立的测试断言，实际删除不足如实记录，不删有效保护凑数。预算当前分配及分类容量见总览，本次不修改产品预算台账，由实施者开工时按总览同步。

必验矩阵：

- 有效/缺失/过期/结构损坏SVG，混合多图、Mermaid-only、无图；自动恢复之后再次status不出现伪业务漂移。
- 用真实入口观察执行期间上传字节、update比较/快照/恢复字节、成文登记摘要均为Mermaid；命令返回后有效SVG显示，源变更则旧SVG不恢复。
- 父级story登记调用project/number/build/check，父级archive调用交付门/archived，内部不得提前恢复；不同feature上下文不共用恢复标记。
- 交付门失败不调用adapter；adapter非零、无/坏JSON、verified=false不登记；远端成功而本地登记失败与视图恢复失败分别返回事实，不重复上传。
- 普通return、原有fail出口、异常、恢复失败均覆盖；块外正文、review人工区、源文件与业务错误完整保留。
- Framework阶段仍通过pre_phase读取Mermaid；直接post_check测试/维护入口在其完整检查范围内保持Mermaid，不因内部status查询恢复SVG而读错对象。原生独立审查不接提前恢复钩子。
- 图语义、渲染和完整CLI仍按用户既定里程碑验证；离线构造报告只证明协议。原V01的“三步由模型执行”改为“一条core命令”，异常与update验收项不减少。

一键入口追加验收（属于C步，不另开实施包）：

- 正常Story生成/登记和既有Story prepare均生成唯一CMD；重复生成字节不变，同名非工具文件拒绝覆盖，脚本丢失可由既有生成入口恢复。
- 从资源管理器双击，或从无关工作目录调用，均定位正确需求；覆盖中文/空格/特殊字符路径、配置自定义features_dir/extension_dir、工程整体搬迁及两个需求并存。缺Node、坏配置、缺核心入口不改Story，错误窗口可读。
- 全Mermaid→可用SVG、全SVG→Mermaid、混合→全Mermaid；缺失/过期SVG明确点名，无管理图不写；坏管理块拒绝。验证实际Story、源文件和块外正文，不仅断言参数字符串。
- 白名单接受且仅接受登记文件名；额外cmd/ps1和原有过程文件仍拒绝。只增删或刷新该脚本不影响材料轮次、成文漂移、update业务差异和Framework生产函数算出的正式subject；before/restore不复制、删除或退回当前工具。
- 系统上传内容仍仅为既有Story/Review；两组七件金样不加入启动脚本。人工切回Mermaid不会在同次调用末尾被恢复SVG，后续archive/update自动切换与恢复照常。

G40包括CMD模板正文及其生成/调用逻辑，不因生成文件在需求目录或cmd扩展名未被旧计量器分类就漏记。模板正文维护在计入预算的机制源码中，不额外复制一份模板或新建通用生成器；实际有效行按既有计量规则交回。
