# S03 蓝图反馈与Story唯一交付

前置S02；G500/X970。AC03—09/11/19。这个步骤整体替换同一业务登记与交付集合，不能先删Review文件再让update/归档数步失效。必读story/review.mjs全部失败分支、context/recheck、flow/update.py::cmd_update_feedback和publish.py、story-chapters、design/story-write/update阶段页、adapters/story.js/fetch.js；原生900c feedback schema、blueprint-host-seams、component-design及本轮gap-probe。

## 1. 评审输入取得与重同步（R1）

### 1.1 系统单：先识别交付件的来源，再比较字节

修改fetch.js::fetchUpstream中wanted/逐件处理：在latestStored及与本地文件相等的短路判断**之前**，先看本单是否已有真实发布记录与发布的Story备份。首次未发布的本单design.md仍是AR需求原件，RR/SR仍走原材料导入。已经发布过Story后，该本单正文是交付回流表面；其相对最近实际发布/恢复外部基线的变化，作为“被改交付件”取回，**不再带role: AR写入材料批次.receipt**。即使它恰好等于某个旧AR原件或当前本地Story，也不能跳过这次回流身份。

落点统一用本需求`inbox/review/`，系统每次取材沿既有取材批次名写`inbox/review/<fetch-batch>/AR-design.md`与该批次.receipt.json；显式review-feedback及实际取得的历史评审附件也在这次评审批次保存。外部四态fetched/same/absent/failed保留；fetched.json仍唯一描述最近外部现状，各item.saved指真实原件，原件按批次保留不覆盖。未变且已有稳定原件的可引用原件，但不靠同名文件猜内容。publish读的item名仍为AR-design.md，不另复制远端摘要真源。

这里识别的是**交付回流通道**，不是“改过就有权批准”的语义推断。新业务要求、事实修正、普通批注和误改均从同一原件由模型分类，按S03四类处理；已有明确原始AR换版输入/独立正式需求来源仍进六类材料链。系统同一正文接口没有额外身份时，不能仅凭内容变化宣布它是新的权威AR；按已知交付历史保存回流原件，实质需求变化照样由有权依据进入蓝图，不丢业务事实，也不为区别文件名额外问人。

### 1.2 本地单及实际消费者

update.status的paths增加`review_inbox`，指`inbox/review/`；该目录是**现收件箱的评审用途区**，不是第七种需求分类。`materials/importer.py::scan_sources`和导入规则明确跳过此子树及其中系统.receipt，不把它报成未归类/待导入，不写RR/SR/AR阅读稿。正常需求子目录仍递归导入；不能把其它名含review的普通文件自动排除。

本地评审文档直接放该处；用户放普通inbox但明确说是评审意见/被改Story时，作者按内容和用户说明在导入前原字节移到review子树、记录原位置，不要求用户改格式或重上传；重名保原相对层级或以内容摘要区分，不覆盖。新需求材料仍原路径导入，不用文件名关键词判业务类型。会话转述保完整原话于同一输入区并标转述/说话人已知信息，不能伪造书面授权。docx用已有预览/转换能力取得可读稿及批注，原二进制保留；无法读出批注如实列未取得，不当无意见，不新增文档解析平台。

flow/update.py::_scan/_collect枚举评审用途区，与需求sources分列为review_inputs，`inputs`展示已取得/失败/未读，`prepare`在现record内存各项`path, sha256, origin`及对应系统item名（如有），并将原件/回执复制到本轮before；before亦保改前本地Story。update_files现有`inbox/**`的protected已覆盖评审用途区，无需加重复规则，restore不撤掉人的新原件。Story review-object及阶段review-inputs的updateInputs读取同一记录所指的before原件、当前稿与notes；不能仅保存但没送独审。

### 1.3 蓝图修订后的Story合入

已有Story批注/直接改稿时，以**人的这一版为编辑底稿**，先保before和输入原件，逐处比较最后已交付稿、人的改稿、当前本地稿。model在现update-notes记录每处采纳/不采纳及理由、影响和落点；有权且已采纳的修改保持到最终Story。蓝图owner先处理设计事实/裁决，作者据新蓝图局部同步受影响处，不能用蓝图重生成整章覆盖人的版本。人的意见不等于必须采纳：未获授权/与有效约束冲突的暂存或不采纳，原话仍在before，三条件成立才集中问。

系统和本地同时有真实改动时按现三方比较逐处合入，不能固定“远端赢/本地赢”；没有改稿底稿、只有意见文档时从现Story局部修订。写作合同的局部落盘、章主责、必要重述保持。脚本可核原件在场和差异，不用词数/文本相似度判意见已被正确承接；独审核原件→notes→Story真实去向。

## 2. 原生反馈的具体接线

保既有`update --action feedback`及每轮`design-feedback.json`；初始问答也复用该实现，经同一flow入口按当前init轮的answers目录定位反馈文件，不要求伪造一个update。它们仅作为原生`blueprint-review-feedback@1`传输件，**不承担另一套决定状态**。去掉读decisions.json、拆D号、查Review人工区/机器区的分支；`feedback_id`只认本轮输入的唯一身份，不从它解析业务目标。

输入来自本轮Story批注、改稿、追加、转述或S02原话记录。取得后先按现有before/来源版本保全，模型逐处对照Story原稿和当前蓝图，在update-notes写“输入原件位置→处理/理由→Story位置或原生目标”。复用现有notes，不新增意见台账/schema；结构检查不能证明每条意见被理解。

纯表达修订不写设计反馈；业务意见/建议/事实/裁决需要设计owner处理时，使用原生四类。字段直接按原生schema：批次`artifact, blueprint_id, component_id, source_revision, items`；条目`feedback_id, kind, source_revision, target_ref, body`；事实带`evidence_refs`；授权裁决另带真实`authority.owner/role`及明确`decision.verdict/rationale`，引用原话。body保存实际意见，模型解释不得假装原话。target_ref/source_revision只在此原生传输条目维护；evidence_refs引用S02绑定问法的原话原件或本节review_inputs原件。引用原件不再要求原件内有另一份目标/版本，当前性由反馈本身与原生资格承担。

目标已有gap直接用`gap:<gap_id>`，已有决定/节点等用其稳定地址。新问题尚无gap时，反馈可指向现有`blueprint:<blueprint_id>`并说明受影响范围，由owner形成真正的新gap；不编造不存在的gap，不先让人再签一张表。表达级输入不为齐套强造蓝图目标。

本轮实测900c `validateBlueprintReviewFeedback`：gap有效→候选f1、requiresReconciliation=true；过期版本、目标不存在、缺authority→BLOCKER且候选为空；opinion→无候选、requiresReconciliation=false。调用仍走framework-access `--action feedback --blueprint ...`；只读资格返回不是写回，不凭它填accepted。

已登记Story时从`story_basis.blueprint_ref`取被评版本；无Story首次问答取实际质询的蓝图引用。**不能把旧输入source_revision改成当前值来通过**。收到旧稿意见，保其原件与被评版本，在notes比较当前差异：已解决/无关写去向；仍适用的先由owner明确当前目标及依据，再形成一个当前版本的新反馈，引用旧原件及解释，不伪造新的人答。

原生component-design的write owner读取原件和候选，判接受/不接受，按既有reconciliation生成新revision及provenance；Extension的feedback-related只展示原生精确来源关联，不能用“记录成功”推接受，也不自动扩大CU施工权限。原生质询复核修订后的正文；Story随后按实际影响同步。明确已有授权的当前裁决不另要求确认。

## 3. Story主责与必要重述

沿现章节合同，不另建章节体系：范围章写本单/兄弟单/不做与影响；业务方案说明关键取舍及依据；业务流程完整承接页面入口→操作→可见反馈→去向；功能说明定义规则与状态；异常与恢复区分明确失败/未知/取消及责任；验收给可观察结果；交付说明未决/未验/未审及承接边界。各受影响处可重述局部理解必需的条件和后果，不能只留蓝图链接；完整契约/统计精确内容保现唯一附录投影，不整篇复制技术稿。

原Review每项有效事实按主题进入相关正文：关键已定给原话/依据与取舍；第三方待定给谁定、等什么、当前影响与已定共同能力；模型自主决定标理由，非人签。蓝图gap保owner/unlock_condition/影响，Story不重建D号表、勾选区或“待确认”汇总附录。

机器只核结构/原件/登记；是否完整、自然、准确由独立语义核原件和Story。已有页面/图文/统计要求不因删除Review压缩；受影响事实不能“原Review删除所以不适用”。

## 4. 全部消费者与旧路径退出

| 生产/消费面 | 本步决定 |
|---|---|
| story/review.mjs、story-build/context/recheck、章节合同 | 移除业务decisionList/registrationGap/Review渲染、D号引用及人工区校验。只删专属函数/文件；独审review子命令、review-report-contract、图面报告和原生code review保持 |
| flow/state与lifecycle/check | STORY_REGISTERED保Story、写作设计与真实依据；删除Review/decisions指纹要求；按当前蓝图与材料核登记，空业务议题合法不要求no_pending表 |
| review-object/task/review-inputs/story-reader-rules | 待审人读件只有Story；保原件、当前答复、蓝图引用、知识/写作合同。删除业务Review判断，不删阶段verifier或必需核源 |
| update/answers/restore | 不再按Review机器区hash判答复效力，原话本身只作证据、目标/版本由反馈承担；本轮输入保留在既有来源和before，逐处去向写notes；更新及撤回仍保护直接编辑和原件 |
| publish/adapters/story、fetch及系统回执 | `ITEMS`只保AR-design.md与按真实要求选入的design-review.md；prepare产生一次delivery集合，对接上传/读回/登记/备份恢复消费它。Review不再生成/要求/上传；旧外部Review若真实取回仍保为输入原件，不自动删远端历史附件 |
| 归档失败与冲突 | 保逐件取材回执、外部当前摘要、冲突/部分成功/备份、三方比较；集合变了仍按每件实际身份核。未知不是未变，不取消恢复副作用测试 |
| 成功说明 | 从当前蓝图/Story及真实审查结论说明待定与未验证；纯说明不另建状态，不改变成功退出码，不增加批准 |

初始/更新的design指令一并改为“原生决定→Story→独审→登记”；旧Review模板/命令提示/前置/专用测试随步退出。流程schema仍用S02的7，不再创建另一版本兼容分支。GLOSSARY的业务Review定义同步为已退出载体，并明确区别原生代码检视及独立报告；这是本版语义承接，不删除旧文档。

## 5. 已承接外部版本成为发布比较基线（R2）

保publish.py的三方比较与真实发布记录，**不能在fetch时就把E写进允许覆盖基线，也不改archived.external_digest伪造一次已发布**。复用update.record的review_inputs、status、requested_result、closed_at、owned_after及本轮notes/原件；不新增已批准状态或平行基线账本。

修订3。prepare 从当次 fetched.json 的逐件结果定位实际批次、saved 原件及回执，核 SHA；明确取得的本地评审输入同样留 before。系统的历史批次可回查，当前与历史不能按目录排序选第一条。已取得且需处理的设计参考与正文一样留本批外部原件（外部 absent/failed 仍有准确去向）。按本次输入和成稿重新审查、登记并在 notes 逐处交代采纳、有据不采纳或未决。close 保留已送审的输入快照；之后取到的新稿不能补列为本轮已承接，可沿正常 update 另行承接。此前已经失败/缺失的项也不能变为成功。

消费者：publish 只读最近有效 documents 轮与该件真实外部事件。该轮已 closed、无在途 update、晚于该件最近实际发布/远端恢复；以 before 的原件与回执核同一系统件、同一完整摘要。正文的本地版本比该轮 owned_after。对实际承接的设计附件，在现 record 对应的 review_inputs 行随成文登记记录本次只读投影字节摘要，条件为已纳入本轮审查对象且原生 readProjection 返回 valid；发布时须仍为该登记投影，投影继续归蓝图保护，不进可撤回文件。未送审的件没有该依据。最近一轮不能证明承接该件时回到该件真实发布/恢复基线，不向更早的轮次搜一个能放行的摘要。只有条件同时具备时 B 取该轮处理的 E；随后仍走 E=L / E=B / 明确覆盖或冲突的原接口。

发布前仍重新取外部E：E=L跳过，E=B直接写，E既不等于L也不等于有效B才冲突。于是“人改外部→update实际承接并close→外部没再变”不需--reply；承接后再被改则仍冲突。原有已明确授权的准确E/L覆盖保持，不能授权未来别的版本。close后本地又改到不等于owned_after须先正常update/独审登记，不能用旧承接事实给新稿盖章。

归档成功继续按真实读回写archived发布事实；下一轮以它为基线，不把已承接版本冒作已上传。已承接E只消除同一次外部变化的重复冲突，不产生送审授权，真实归档仍在原用户授权范围内。上传前本地/外部变化、部分写入失败、读回不符与恢复副作用仍按现协议处理，不为理论原子并发增加锁或历史基线扫描平台。

## 6. 验证与完成

现有test_story_build/test_story_update/test_update_dispatch/test_update_checkpoints/test_evidence_delivery/test_design_handover/test_material_delivery及归档/恢复测试按新合同改输入；删除只验证旧D表布局的用例，保护直接编辑/冲突/完整性负例换新载体继续验证。test/scripts/design_fixture.py等共享夹具按真实消费者同步，不因某个用例不用就删除整个夹具。

必须区分：普通建议不触发revision；有证事实/有权裁决经资格后owner仍可不接受并说明；缺来源、过期、错目标被准确指出；正文直接修改不能自动成为批准；引用旧Review作为输入仍可读；新init不生产Review/decisions。原生调和产物再由真实来源索引/反馈关联读取，不能在测试里预填“accepted”代替此链。

新增必须分辨的正常/负例：

| 场景 | 预期实际生产/消费 |
|---|---|
| 系统已有发布Story，评审人在线改正文，再fetch/update | 原件及receipt进review用途区，不生成system:AR的新需求版本；notes逐处处理，作者/独审实际取得改稿 |
| 本地在inbox/review放意见文档（或普通inbox明确评审后移入） | 不进入六类阅读稿，不报待归类；update原件/比较/notes/独审链完整；普通新AR文档仍正常导入 |
| 人改段落后蓝图修订，再同步Story | 以人改稿为底稿局部合入；采纳段落保留，不采纳可查理由与before原话；不能整章覆盖 |
| 远端E1≠上次发布B；update处理E1并close，L是新稿；再次fetch仍E1 | publish基线来源该closed轮，E1=B可写，不需--reply；archived仍是上次真实发布事实，直到新读回成功 |
| 同上但承接后远端又成E2；或未close/materials-only/本地撤回/更晚远端restore | E2不等有效B/L则仍冲突；未完成/撤回轮不能成为承接基线，不丢F3保护 |
| 正文已处理、设计附件未取得或未处理 | 逐件报缺口/冲突；不因正文可以发布而放行附件 |

系统组合仍核正常上传、读回不符、远端人工修改冲突、部分上传失败/恢复；本地需求零远端。Story源文件受外部服务失败保护。业务完整性另由设计者对照材料/当前金样逐处检查，不用文件少了即性能通过。

完成时交回01批，包含S02及本步全部提交、正常组合/负路径、预算、退出清单处置及剩余FR1。未进入02批前由reviewer确认业务真源替换未丢能力。

预算分文件依据见[预算拆分](../02-预算拆分.md)S03；取材/识别与发布基线的新增职责已计G500/X970，adapters按AGENTS排除但仍有完整交付/验证责任。
