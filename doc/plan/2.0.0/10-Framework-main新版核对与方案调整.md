# Framework main新版核对与方案调整

2026-10-18，维护设计者。按用户反馈刷新origin/main并读取正式发布树，核来源清单、入口说明和实际源码消费者。此次只做源码/合同核查和方案更新，未接入demo、未替换Extension、未运行harness或真实CLI。既有四步及1.9.9起点保持，本轮在S2补齐已交合同和剩余决定，不重写整套方案。

## 1. 输入已取得，当前checkout尚未接入

| 身份 | 本次核实 |
|---|---|
| 仓库/分支 | origin的main；已执行fetch，不合并、不切分支 |
| main固定提交 | `2c83c1824e38f67f7c1141a3be155360266bad30` |
| 发布树位置 | main根`framework/`；不是当前story的`demo/framework/` |
| Framework版本 | 3.1.0，同号新构建 |
| RELEASE-MANIFEST source_commit | `8deb32d01caa56701e6dbc0090dacd52e60ae825` |
| built_at | 2026-10-18 06:47:11.659 UTC，即Asia/Shanghai 14:47:11.659 |
| 文件完整性 | 清单1241项，缺失0、SHA256不一致0；源码快照逐文件核Git blob身份 |
| 当前story发布件 | 仍为旧source_commit `074a4c3c4a0591c8ed2162e2a0d048a1fdec081f`，未改动 |

[身份及摘要证据](../../../output/story/2.0.0-framework-main/2c83c182/identity.json)与同目录`source-files.json`、`main-framework-source.zip`保存本次输入。zip是从固定main原始Git字节生成的调查副本，另含main根AGENTS和framework.config用于查来源；正式接入只取其中framework发布树，不能把main业务工程、根配置或AGENTS整体覆盖到demo。

以下源码引用统一指该main提交的`framework/`根（简称N），不是当前demo文件。解包只读副本在`output/scratch/2.0.0-framework-main/2c83c182/`。新发布树足以开展设计核对，不再等待“明天推送”；1.9.9正式发布身份和最后增量仍未取得，此次没有刷新或认证1.x发布线。

## 2. F1：人读蓝图已成为原生交付

实际文件名为蓝图目录的`component-blueprint.review.md`，不是另一个`blueprint.md`。格式标识为`component-blueprint-review@12`。该文档默认交付，零CU也可先交需求级设计；有CU时同页显示有效CU的拆分、风险和精确映射。依据：N `skills/project/component-design/SKILL.md:124`起，`harness/scripts/utils/blueprint-review-projection.ts:18,565–568,710`起及`blueprint-review-materialization.ts`。

canonical蓝图/CU仍维护设计事实，人读Markdown由确定性renderer生成。作者可在`review_summary.reader_guide`写说明，不能直接改生成Markdown作为新事实。guide不参与整蓝图施工摘要，设计来源变化则guide自己的source_digest过期；渲染器保留当前事实并给诊断，不自动替作者盖摘要。修改原设计字段仍走设计修订；CU集合变化更新施工说明与参考，不把其数量/身份固化到guide。依据：N `blueprint-reader-guide.ts:67–82,133–172`、`identity-neutral-digest.ts:59`及设计Skill第31行。

正文有13个固定问题域：摘要、背景/目标/边界、术语、用户旅程、整体方案、关键流程、数据/存储、关键取舍、恢复、质量与安全、施工/上线、验收、待补问题。其后是完整技术与追溯参考。guide可在同域内按作者顺序安排多个title/prose小节，以canonical内JSON Pointer `source_refs`和已有`graph_ids`绑定来源。没有已发布的任意顶层章节插件合同；新增语义不能靠prose变成权威事实。依据：N `blueprint-reader-guide.ts:6,86–96,151–170`，`blueprint-review-projection.ts:565–568`。

### 原生写作和恢复顺序

命令由设计agent按正式Skill使用，下表只登记接口及效果，不在本次执行。cwd为目标工程的`framework/harness`，project-root显式指目标工程。

| 动作 | 已发布入口与效果 |
|---|---|
| 说明来源摘要 | `npm run check:component-blueprint -- --project-root <host> --blueprint <id> --reader-guide-digest`：独立只读模式；不与其它模式混用 |
| 写人读草稿/刷新 | `npm run check:component-blueprint -- --project-root <host> --blueprint <id> --write-review --json`：物化文档，作者先检查当前事实/图/说明并登记正确source_digest |
| 首次独立阅读 | 先渲染可读草稿；实际派发要求质询者不继承父YAML/摘要，先读首屏和正文答八问，再核原scope、来源与参考；不是先过完整准入才允许渲染 |
| 修订后交付 | 设计或CU修改后刷新；读取本轮结果的review_document及真实正文。文档current/refreshed与checker PASS/FAIL分别报告 |
| 文档故障 | 返回failed、原因、已写路径和重建入口；只重试物化，不回滚已接受设计或改变readiness；过程中来源变化拒绝落为当前文档 |

依据：N `check-component-blueprint.ts:138–154,187–211`、`blueprint-review-materialization.ts:35`起、P1工作流§4–5。原生质询新增读者任务是已发布要求，实际隔离输入、阅读质量和纠偏效果尚未在本仓验证。

## 3. F2–F8与旧问题的当前状态

| 项 | 新事实及证据 | 当前决定/剩余验收 |
|---|---|---|
| F2 设计前知识 | N设计Skill第88行与`knowledge-context.ts:132–141,188–192`消费可选`provides.skill_assets.component-design.knowledge`；extension优先，未声明才回profile，声明不可读给notice；直接Skill也读取 | 该资产通道可作为项目知识输入候选。全发布树未见旧`extension_author_requirements`/`extension_review_requirements`键消费者；不能称旧请求原样交付，也不强迫恢复旧键。先核新通道+原生质询能否完整承担三类知识/作者及独审义务；阶段路由/派审机制不塞进knowledge事实 |
| F3 初次CU准备/U01 | N设计Skill第98–115行给JSON数组`[{providerId, artifact}]`、候选落点和公开`check:change-unit --accept-candidates`、`--readiness`；`check-change-unit.ts:57–86`实际执行 | “仅有内部函数名”的旧缺口在文档和实现层已接替；本仓真实交接待验。接受成功即清候选，readiness/文档失败不要求重新接受；busy等竞争结束后重试 |
| F3 已有CU内容修订 | N `docs/concepts/blueprint-design-inputs.md:98–136`明确无修订CLI，使用已发布`reviseChangeUnitContent(projectRoot, blueprintId, [{expectedRef,candidate}])`和官方ts-node示例 | 未完成、无运行或已停住的活动CU可同ID修订，revision由框架算；不使用accept重复覆盖，不直接改canonical，不在Extension自建shadow writer；具体update调用按官方资格核 |
| F4 FW-04准入 | N `blueprint-admission.ts:27–49,75–95`仍按上游BLOCKER及当前component-assets gap派生；普通当前gap标blocker未在该派生函数一并加入 | 旧风险尚无关闭证据；本次未运行新版复现，不能断言整个新调用链必复现。要求用合法当前一般gap复验正常准入，不能靠人读待补问题展示关闭机械准入问题 |
| F4 FW-05无run接续 | N `context-facts.ts:59–60,228–234`仍核当前冻结指纹且基线不豁免；`capability-resolution-entry-input.ts:430`仍提供当前scope指纹 | 旧故障条件仍需完整正常入口复验。此轮不手改facts身份、不复制原生增量承接；仅本轮触发的无run Spec→Plan终点受影响，不笼统阻所有Story设计 |
| F4 interactive术语 | N P1要求medium/low交互确认；`blueprint-discovery.ts:193–209`仍对headless_assumed给WARN，未由该函数区分实际运行模式 | 不能用人读第13节披露假定代替interactive人签；核真实入口/上下文与确认轨迹，保留模式问题待验 |
| F5 独立审查/U02 | N P1§4规定隔离、先读正文后核源；`blueprint-questioning.ts:78–99`核complete、isolated_context、provider不同于authored_by及scope | 是职责/声明校验，不是执行者身份或报告首次字节锁；旧作者改派审/改原件风险仍需实际轨迹和最早消费者验证。不能把原生文档来源摘要当审查原件防伪 |
| F6 安装与入口 | N manifest schema接受1.0/1.1，1.1公开skills/knowledge/hooks/overlays/skill_assets/mcp_actions及Feature phase_bindings；仍无before_component_design绑定 | 首包沿新原生加载/物化与已核manifest合同，不整包回灌B旧bridge。schema可解析不等于B安装行为直接兼容；直接蓝图入口的知识通道已见F2 |
| F7 来源、图片、反馈 | N宿主指南§2–5仍保留materialization/publication/feedback；人读支持journey单图精确引用、graph_ids及当前CU绑定，publication零新设计事实 | 继续由Extension承担取材/人签、Review、系统归档/读回/恢复及资源传输。新版未提供需求系统二进制附件能力，不把本地截图/SVG可见等同外部交付完成 |
| F8 usage/stats | 原生新增了蓝图人读及CU命令，本次未见替代B需求级usage/stats产品的交付 | 保留B单writer/快照/终态/统计；对新蓝图、CU及阶段的事件/事实对应需另定。不把readiness刷新或多CU重复计为需求完成/多份需求 |

F2/F5的剩余问题先以实际目标和新合同判定，旧字段名只是历史请求，不是此次重新适配必须保留的架构。确实缺原生通用能力时形成精确输入/消费者/失败/验收要求交上游，不在Extension绕行；本次不向外发送消息。

## 4. 对适配方案的具体调整

### 原生承接与Extension保留

采用原生canonical蓝图/CU作为设计权威，默认使用原生@12文档作为需求级设计评审载体；不另造blueprint.md文件或第二个原生文档renderer。B的设计、页面叙事和知识效果按原生字段/reader_guide的实际可表达范围承接，旧Spec设计信息不能只迁成一段guide文字。

Extension保留1.9.9的业务取材、材料/会议/范围裁决、来源整理、Review人工意见、归档/读回/恢复、update、资源和usage/stats职责。Story对外仍需交付可独立阅读的业务结果；是否需要独立story.md正文作者，待下表差距核清后定案。此次不根据接口存在就提前删除整套Story成文，也不继续把“完整人读蓝图缺失”作为重复建设理由。

| B保持目标 | 新原生可用承载 | 必须补核的边界 |
|---|---|---|
| 背景/范围/业务方案/页面流程/异常/验收 | canonical事实及13域reader_guide，多小节、既有图和已登记截图 | 1.9.9已审业务关系/页面连续性是否完整，固定13域能否讲清本项目，不只核字段存在 |
| 精确接口/数据/存储/验收/用例/施工 | canonical typed内容、同文档技术参考、CU design_refs派生 | 真实字段/层级和共同继承；原Spec中事实回设计目标，专属change_unit映射由Plan负责 |
| 规约/模式/指标与共同义务 | 设计知识资产、设计目标/契约、质量/数据域、说明及CU | 所有B有效判断及每指标定义、角色/落点能否进入真实消费链；不把source_refs指回声明当应用 |
| Review、人签与送审更新 | 独立Review及host materialization/publication/feedback | 既有三态、授权、冲突、原件身份、归档回执和资源路径不能被原生人读稿取代 |
| 选择性SVG/本地阅读 | 原生graph/截图展示与B图形能力候选 | 本地视图切换不可改写应由原生renderer唯一维护的MD后冒称current；须定交付副本/资源边界，B尚未完成的选择性合同不假签 |

先对26项能力及B正本的有效内容做逐项落点核对，再比较“原生人读稿直接交付/配套Review”和“另有独立业务叙事”两种交付的实际缺口、维护成本。只有新增读者价值或原生表达不足有具体证据时才保留第二套全文成文职责；涉及最终合并/独立的关键选择仍交用户确认，不靠固定章数选择。

### 入口顺序与失效语义

范围/材料/人签确认 → 按来源类型形成原生currentScopeItem → 设计前读项目知识与有效机制要求 → canonical设计/图/reader_guide → 原生摘要及草稿渲染 → 独立读者任务与原scope质询 → 修订/刷新 → 明确准入、文档状态及未决 → 按授权交付或CU候选接受/readiness → 后续Spec/Plan与业务交付。

来源由外部provider取得时用`requirement-source-materialization@1`；直接人工/仓内本地材料可以由builder规范为同样合法来源，不为了统一多造JSON。`--materialization`验证不能等同已写canonical，`--feedback`验证资格也不等同已接受裁决；只有设计owner接受的新事实/授权决定引起真实修订。

纯表达调整先用reader_guide；设计事实变化回canonical并按新身份重渲/调和。`--readiness`带指针调和与文档物化副作用，不用于“只读状态查询”；候选已接受后下游失败继续readiness/文档恢复，不重复accept。独立审查结果和资源交付各有自己的真实证据，不能被review_document=current替代。

## 5. 首包、保留项和下一步

首包仍是可验证的源码起点切换＋最小适配＋安装/物化＋测试装配。现在可以按固定N核loader/schema、原生文档命令与CU入口，设计测试fixture与恢复预期；不再等未知文件名或自编CU接受脚本。正式接入取N的framework子树，沿根AGENTS §6处理本地定制及已装Story入口，不能merge整个main或覆盖现有归档/方案。

旧2.x可复用目标保持：采用版本/冻结来源、知识落点与下游义务、更新撤回、忠实宿主投递等；旧设计读取、文档投影、章作者、报告目录、CU调用代码须重核N真实接口。旧@author/reviewer资产键、旧renderer字段、旧硬拼路径或B的阶段结构不作为兼容层保留。已有场景反例全部保持适用语义，换新消费者与身份。

S2剩余交付是：B正式发布差额；26项能力对N真实字段/读者结果的对应；F2/F5职责覆盖与F4关键复验；对外Story/Review/资源/usage最终接口；逐文件首包及后续包动作、退出、G/X、峰值和验收。N源码完整不等于这些工作已完成。当前不签S2整体通过或S3可开工，不提前批准产品增长。

可继续的维护工作是差距/落点设计、只读引用核实及具体首包估量准备；依赖B发布身份、业务交付选择或实际行为证据的部分按其条件保留。headless/Goal模式的新功能不因本次Framework升级扩大到Extension维护范围。
