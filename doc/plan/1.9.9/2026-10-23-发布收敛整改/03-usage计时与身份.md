# S3 在模型开始工作时计时（当前R01返修见07）

2026-10-23。用户已明确：usage统计模型实际执行各步骤的耗时，不是第一次检查到闭环的耗时。R01的开始/迟到/完成设计按[07局部返修](07-R01开始与完成事实返修.md)定案，属于本S3内一个返修步骤，不重开已通过部分。此分册替换先前trace/pre_phase起点设计；统一预算、权限见[总览](00-总览与预算.md)，交回见[05](05-执行接续与集中交回.md)，标准@10。当前工作区已有在途settle/close实现，保留其他步骤的改动，在其上按本分册收敛，不恢复旧源码、不另起第二记录器。

## 1. 已核入口与最小设计

- Spec/Plan已有动笔前CLI：`hooks/spec/author.mjs::main`、`hooks/plan/author.mjs::main`，生成任务包前可调用现有recordUsage。被导入的纯任务渲染函数仍只读，不能因为独审装配任务而开作者计时。
- coding/review/ut/testing当前只有`hooks/<phase>/author.md`，没有author.mjs，不能假设已有自动入口。复用现有usage.py，在这些作者页及AGENTS扩展段的开始工作动作中调用，不新建四个包装脚本或阶段调度器。
- `/story init`现有顺序先系统取材后story_flow init；`update`先status/fetch/inputs后prepare。只改命令成功后刷新或prepare时刻仍会漏工作；须在现有Skill相应流程的第一项业务动作前开始计时。
- Framework pre_phase在harness检查时发生，trace是首次harness运行时刻。它们不能充当工作起点或缺起点的静默替代。不修改Framework。

在**现有usage.py**提供唯一开始动作，CLI为 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <编号> --begin --step <步骤>`；内部recordUsage调用同一begin。步骤来自既有usage合同八步骤，无新清单。所有时间由脚本取当前机器时刻，模型不传时间。

“实际执行耗时”沿用已确认的完成轮日历跨度，包含本轮等待/中断，不是CPU活跃时间；不新增暂停、心跳或活动采样。开始必须在材料/代码分析、设计、编辑、测试等实际工作前；只读命令帮助/判断用户要哪个步骤不单独计一轮。当前设计依靠模型执行已交付的正常入口，不能声称能从任意自然语言或文件编辑自动发现开工。

## 2. 八步骤的起止与写入

| 步骤 | 开始动作及起点唯一持有者 | 完成及结算 |
|---|---|---|
| story | `/story init`按Skill先begin，再取token/拉取系统/建骨架/分析。begin确保.usage-id及usage节点，并在现有starts.story记机器起点；身份只标识需求，不作计时依据 | 首次成文登记成功的story_written_at为终点；原命令成功后结算Story。重复登记不重复算 |
| spec / plan | 开始本轮工作先执行既有author.mjs CLI；main在取业务上下文/渲染任务前调begin。原流程把它移到阶段工作开头，不能先写稿再取包 | 完成本轮编辑、独审及必要返修后执行既有finalize；有效原生闭环是结算前提，终点取本次有效收尾请求的机器时刻 |
| coding / review / ut / testing | 作者开始该阶段工作前调用同一个usage begin，再按现有作者页执行；只加入口动作，不复制阶段系统 | 同样在正常工作结束、有效闭环后执行finalize，结束取收尾机器时刻 |
| story update | 用户要求更新时，Skill先begin，再status/fetch/inputs/prepare；prepare前暂存在现有starts的story update项 | prepare把该值移入该轮已有record.json的started_at并退出暂存；closed_at为终点。按完成轮started_at→closed_at派生spent/rounds |

先前的summary.closure_commit仅保留为“确实已闭环且不早于本轮开始”的证据，不再代替实际收尾时间；这样闭环后属于本步骤的修正也不会遗漏。finalize应在本步骤工作结束后立即执行，不推迟到无关阶段结束；后续需要再次工作先重新begin。起止之间没有人工报时。

每阶段的工作开始和结束都能解释到正常入口。若漏begin，不能用trace、pre_phase、prepare或文件mtime补一个看似准确的时间；保留已知历史、当前完成事实可见，并明确本轮计时缺口，不称完整。不得拿整场CLI耗时或旧测试固定秒数补正式记录。

## 3. 复用状态与故障规则

1. 六阶段与Story只用现有`.usage-state.json`的starts[step]保存未结算开始；Story起点允许null表示真实动作已发生但未取得开始时刻。删除首轮trace例外与pre_phase重试起点分支。begin重复执行保留最早时刻，同轮检查/重验/重新取任务包不重置；收尾后清掉starts，不留持久完成游标。
2. 已完成阶段只读status/inspect、报告读取或harness检查不新开计时。Spec/Plan CLI被明确作为作者工作入口；收尾后仅为查看旧任务包应使用现有只读渲染/读取路径，不以作者CLI查状态。不得让pre_verifier导入调用的渲染函数写usage。
3. Story身份与起点分责：begin或真实init活动可按现有路径建身份；init不是开始时刻。无Story开始键而实际init发生时，starts.story记null并报缺口；正常begin只在没有键时记now，迟到begin保留null。成文前不写steps.story，只有真实story_written_at才结算已完成时间或缺口并清开始键。预置inbox/原件/流程文件存在不构成开工或完成证据；不再用身份时间计Story。具体转换与正反验收以07为准。
4. update prepare前没有record，所以临时起点是必要的，复用starts而不新建临时文件。prepare写record.started_at成功后删starts副本，稳定状态只保留一处；opened_at继续代表业务轮次prepare时间，两者意义不同。转移失败/中断重试优先读取已写record.started_at并清理残留，不能换成重试时刻。已open轮次再次begin/prepare沿同一started_at，不开新计时。
5. finalize对有start且有效闭环的新轮计一次，使用记录器机器now作为结束；重复finalize无start不累加、不改已有累计。写失败保留现有pending目标行与原子写保护，重试赋值不重复累加；错误记录/缺起点不清已知历史。未完成轮不累计，缺起点的完成轮明确缺口。
6. update close复用同一收尾入口结算本轮实际开始且已闭环的阶段，再关闭update；没开始的旧阶段不补时间。若独立阶段提前finalize，update close重复调用不得再计。Story交付门继续复用Spec finalize；stats不参与任何开始/结算。
7. 运行态仍不归档，最终只归档usage.json；stats只用usage/Git。starts/pending均无内容时删除运行态。不得新建时钟台账、并行计时历史、后台轮询、独立守护或Framework回调。图源/审查任务不因统计信息写入改变subject。
8. 记录失败沿现有错误通道披露并由模型处理，不新设用户审批或业务阶段门；恢复时不能假造错过的开始时间，未核实区间列缺口。已知agent/model一次固定，实际未知如实null，不猜、不新增人工问答。

## 4. 文件动作与退场

- `usage.py`：begin/settle及现有starts/pending消费者；退出trace_start计时消费、phase动作自动记起点、无begin fallback。保留schema/复合身份、最小完成行、原子写、防重、独立stats。
- `hooks/shared/usage.mjs`：具名recordUsage复用begin/finalize；`manifest.yaml`中六阶段usage pre_phase登记退出，不让检查自动开轮。其他story-view/pre_verifier hook保持，不改Framework。若默认导出只服务已退钩子，一并删除。
- `hooks/spec/author.mjs`、`hooks/plan/author.mjs`：只在真实CLI main开始工作处接begin，导出渲染函数无副作用；纯Framework需求也创建身份并记起点，不等首次检查。
- `AGENTS.section.md`、六阶段author.md及Story SKILL、init/update方法页、实际路由指引：工作入口先记录；更新原有同职责段落，不把同义提示复制到所有页。Spec/Plan沿原任务包CLI；其他四阶段沿共享begin，无新wrapper。
- `story_flow.py`与`flow/update.py`：update.started_at转移和收口；Story init复用或建立需求身份，但缺begin时只登记未知起点、不补init时刻。status保持只读，fetch/导入失败及等待也属于已开始轮次，不因失败另造起点。
- V5 §4/5与标准I3/I8同步实际工作时段；旧opened_at计时、检查起点测试退出。旧CLI证据不回填，不支持用旧完成格式猜测新时间。

## 5. 验收与交回

先做可核区分的离线时间序列：T0调用工作入口，T1读料/写稿，T2首次harness，T3闭环，T4完成本轮收尾。若已知T0、T4，必须计T4−T0，而非T3−T2；T0前后顺序用真实入口的调用证据验证，不在测试里手填starts绕过接线。

分别核：Spec/Plan真实CLI main自动begin与导出只读；另外四阶段入口指引及共享命令；Story先取材前begin、update先fetch/盘点前begin及prepare转移；重复begin/中间闭环/返修/等待/中断；新轮开始/旧闭环拒绝；缺begin不fallback；重复finalize；跨文件写失败恢复；纯Framework首次活动；无features统计保持。无需八种业务Case全排列，复用现有测试和隔离正常入口。

保留S23原始时间链作诊断，解释旧设计遗漏的区间；历史运行没调用新入口，不能追写为新方案实跑通过。新CLI应证明开始动作确实先于业务工作，未运行前仅签离线接线及算法。无模型运行授权，先按@10集中交回；预算增量确认范围见总览，不擅自扩大实现。
