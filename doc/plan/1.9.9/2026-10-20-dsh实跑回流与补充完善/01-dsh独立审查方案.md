# S1：DSH独立审查接入

2026-10-20，维护设计者。按用户最新决定，DSH审查员作为demo本地定制归档，不改上游、不等待上游发布件。当前两项返修以[04集中返修](04-R1R2集中返修.md)为执行依据；真实资格未完成，不代表整条链当前即可起跑。

## 1. 定案与所有权

### 与OpenCode的逐项核对（2026-10-20）

用户要求具体确认是否参考OpenCode。结论：**复用OpenCode的架构与审查协议，替换宿主原生注册和调用方式；不新造verifier服务或Extension调度器。** 本节结论来自实际安装包源码，不是仅根据“有subagent”推断。

| 环节 | 本仓OpenCode现行实现 | DSH已核实的对应能力 | 实施决定 |
|---|---|---|---|
| 注册审查员 | adapter的commands.subagents物化`.opencode/agent/verifier.md` | `dsh-tool-subagent`按toolName注册具名工具，persona是配置字符串，不自动发现OpenCode Markdown | 配置专用`verifier`工具，persona从审查模板生成；不把Markdown拷入假定的`.dsh/agents`目录 |
| 独立上下文 | task派出独立verifier会话 | spawn源码`inheritsParentContext=false`，调用`startInProcessRun(request,{})`，没有fork seed | 只用spawn，不用subagent_fork |
| 只读 | frontmatter permission拒绝edit/write/patch/bash/task | `applyChildComposition`实际调用`childCtx.tools.restrict(toolFilter)` | 白名单read/glob/grep/read_image；不以persona代替权限 |
| 任务传递 | `task({subagent_type:"verifier",prompt:<完整request>})` | 工具schema必填description/prompt；关闭后台后不公开run_in_background参数 | `verifier({description:"阶段独立审查",prompt:<完整request>})`，不传DSH不支持的subagent_type |
| 任务执行 | 子级读取request.prompt_path及实际材料 | spawn继承工作目录、独立会话，具备相同文件读取能力 | 复用现行OpenCode verifier正文中的阶段输入、读取与报告职责 |
| 报告落盘 | 父模型原样保存终稿，子级不写 | one-shot前台等待最终结果；非正常终态返回错误 | 保持父模型写报告、Framework验真，错误输出不冒充最终报告 |
| 看图 | 宿主工具与所用模型共同决定 | read_image工具存在不代表模型有image input | 保持实际资格检查，盲模型不签视觉PASS |

核对位置：`demo/framework/agents/opencode/adapter.yaml`、`templates/agents/verifier.md`；已安装DSH `app.asar`中的`dsh-tool-subagent/lib/index.js`、`dsh-subagent-spawn-in-process/lib/index.js`、`dsh-subagent-in-process-driver/lib/index.js`及`dsh-subagent/lib/index.js::applyChildComposition`。前面三份已提取到`output/story/1.9.9-dsh-review-20261020/`。

特别注意：DSH的`captureDelegatedPolicyOverrides`会传递父级auto/danger-full-access等权限模式。独立会话不等于只读；只读依赖工具层restrict，资格负例必须验证写工具确实不可用。当前只确认实现机制，没有调用真实模型，不登记已实测可用。

OpenCode的现行模板只接收阶段request；阅读图任务不是这个JSON。DSH persona分为“Framework阶段request”和“自足的独立只读任务”：前者复用OpenCode阶段协议，后者遵守输入任务的输出约定。Framework模板不写Story的四项判据、路径或schema；阅读图合同仍全部由Extension任务生产者交付。不得让阶段终态块和阅读图report混写。

采用DSH现有spawn后端，加一个专用只读审查工具实例`verifier`。不采用fork，不允许通用subagent的默认工具权限承担正式审查。复用DSH已安装包，不增加npm依赖、Agent层级或审查调度器。

用户已将交付方式定为与OpenCode同类的demo本地定制：adapter/子级模板保存在`demo/framework/agents/dsh/`，物化配置在`demo/.dsh/`，父模型沿既有入口与宿主原生工具调用，不新增AGENTS.local.md。归档与升级保持范围记入本仓AGENTS，不改上游agent-maison、共享Framework逻辑或现有审查算法，也不升级3.1。原先“等上游兼容发布件”的前置撤回。

本项补的是一个已存在公共职责的宿主适配：仅有布尔声明无法让DSH理解Task调用协议，因此必须同步指引消费者。仅在generic上改true、在Extension额外编排verifier、让worker替模型审查均不采用。

## 2. DSH实际配置与调用

已核实当前官方包0.2.0-rc.2：

```yaml
# DSH原生 --patch overlay格式；这里的patch是宿主配置层，不是修改Framework源码的临时补丁。
- insert:
    - id: maison-verifier
      name: '@deepseek-ai/dsh-tool-subagent'
      config:
        provider: spawn
        toolName: verifier
        backgroundMode: one-shot
        enableRunInBackground: false
        maxDepth: 1
        toolFilter:
          allow: [read, glob, grep, read_image]
        persona: <构建时内联下面定义的完整persona；交付件不能保留占位符>
```

该格式已从DSH的`dsh-base/cordis.patch.yml`核实；加载层已从`dsh/lib/profile-boot-*.js::composeProfile`确认支持`--patch`。不改用户`cordis.patch.yml`，不编辑每次启动都会重写的`cordis.yml`。`--dump-config`本身也会重写profile根配置，不当作无副作用探针在用户profile反复调用。

**交付位置与入口定案：** 本地`demo/framework/agents/dsh/templates/agents/framework-verifier.patch.yml`由3.0基线adapter已有`commands.subagents`物化能力安装到工程`.dsh/framework-verifier.patch.yml`，与该基线OpenCode的登记位置同构。这是显式加载文件，不假设DSH会自动扫描`.dsh`。实际启动与resume都使用`dsh --profile headless --patch <工程绝对路径>/.dsh/framework-verifier.patch.yml ...`；一个进程只装载一次。不额外增加父级提示文件或Case任务注入。若profile已有同名工具或相同id，明确冲突，不静默覆盖。

**本仓测试接线：** 复用中央registry已支持的`{cwd}`参数，DSH start/resume的overlay参数均写`{cwd}/.dsh/framework-verifier.patch.yml`。无需为每个Case另生成registry。suite只保存一份DSH调用配置快照`cli-registry.json`：从当前中央defaults与选中DSH条目派生，在本suite使用的profile argv中插入`--patch`及上述参数，不修改中央默认调用、不复制其它宿主条目。所有Case的`CliClient(registry_path=...)`消费这一份，cwd仍取各Case自身工程；stop/poll读相同配置来源。快照由suite装配一次生成，不允许人工分别修改。一般业务仓由DSH启动说明给出同一带overlay的调用入口。未加载overlay的旧DSH会话需要新开，不能在旧会话中宣称已升级。

**persona完整职责：** 独立只读、不继承作者结论；阶段request读取prompt_path、以其检查项为准、回显subject并返回现行终态块；其它自足只读任务读取任务列出的依据并按其指定格式返回；缺输入或无法看图如实报告，不造PASS；不写文件、不执行shell、不再派子代理。报告落盘与检查命令始终归父作者。实现时从现行OpenCode正文提取阶段分支，不改其已有效的报告合同。

前置是该profile已有`dsh-subagent`服务和`dsh-subagent-spawn-in-process`；没有就按宿主现有profile组合方式加入。只安装一次服务/后端，不覆盖通用subagent，不写凭据，不改全局默认模型。`toolFilter`是真实工具白名单；不提供pwsh/bash、write/edit、嵌套委派或任意外部写工具。对子代理权限的约束不能只靠persona一句“只读”。

阶段调用固定为`verifier({description:"阶段独立审查", prompt:<request文件完整JSON正文>})`；不传作者结论、不抄ai-prompt全文、不使用subagent_type字段。工具前台返回最终正文，父作者将其原样写入现有summary指定的报告路径，再执行现有receipt检查。审查执行体从request读取prompt_path，并按实际任务读取材料；报告终态回显当前subject。

模型沿选定profile的已知路由，不由工具偷偷换模型。文本verifier与图像能力分开验收；若沿本次不支持图像的模型，文本审查可测试，阅读图视觉项仍为UNKNOWN。需要完整T2时由用户确定具备图像输入的审查路由，不自动推荐或切换付费模型。

阅读图独审复用同一个只读执行工具，输入为现有`review-request`生成的任务全文，并返回现行四项JSON报告。`figure-reading.mjs::reviewTask`须把“审查者返回报告”与“父作者原样保存、运行review-check”分成明确动作；修正现有任务中容易让只读子级去写报告/跑命令的表述。同步`reference/svg.md`，不改变报告schema与身份。两个原件路径和验真消费者保持，不合并schema、不将阶段PASS代替阅读图PASS。

## 3. demo本地定制文件动作

本仓实施者按AGENTS中的本地定制约定落实，当前已完成的部分不重做：

- `demo/framework/agents/dsh/adapter.yaml`及子级模板、confirmation-registry选项与物化配置维持已交回范围，身份为dsh，不伪装generic或opencode。
- 不新增verifier_instruction字段，不修改共享规则或其它宿主。不新增AGENTS.local.md；Task字样差异按04-B验证正常调用，不预判为必修。
- 现有request/material/subject/报告验证算法及回执代码不变。静态通用Task字样不作为实际渠道证据，实际调用由DSH会话/工具事件证明，不伪造执行引用。
- `verifier_subagent`仍只在资格实跑后登记true；开发中的adapter可先为false。不能让模型通过失败循环来发现宿主尚未配置。
- dsh现有读取/图片工具权限通过离线配置检查和真实只读负例验证；主agent的写权限不自动继承为verifier权限。

本地定制随demo归档并在Framework升级时按本仓约定保持，不另设上游发布依赖。交回必须包含父模型实际获得映射的证据；仅有adapter注释、子级persona或文件存在不算送达。

**资格顺序：** 先完成本地说明与配置装配离线检查；获授权后，在隔离工程临时启用dsh声明取得正常调用链资格证据，随后交审决定是否把本地声明登记true。临时资格试验不等于正式demo已可用，未实跑时保持false，不直接起跑完整Case。

Extension侧只检查并按其manifest已有桥接机制补dsh入口映射；沿通用AGENTS/Skill可用时直接复用，不制造同内容第二份Skill。阅读图作者页仍指向现行独立审查职责，具体工具由宿主说明承担。原阅读图父子职责缺陷记原图文包返修；真正DSH新增单列实际文件动作，不预申请G30/X10，归属见99。

## 4. 顺序与完成条件

1. 离线核对demo本地adapter/子级配置及装配，完成04-A返修并按04-B准备资格验证；用桩验证请求与报告交接，不称独立审查实跑。
2. 获用户授权后在隔离工程做最小资格：父子会话不同、子级空上下文、写工具实际不可用、父模型沿正常Framework任务调用并取得报告；错误关系负例被发现，合法正例不被固定词句误拒。交审确认后才登记本地true。
3. 正式两Case起跑前检查dsh adapter实际选择、专用verifier工具实例/路由、文本及图像能力，缺任一适用资格在模型业务工作前指出，不跑到末尾才发现“无报告”。不放宽装置的verifier完成条件去适配generic降级。

### 图文效果的具体交回

以下四类是验收关注点，不要求另建四套测试框架或每次重新造稿。先复用P4已有“表漏分支/无增益SVG”材料及现有qualification入口；仅对未覆盖的页面路径和重复主题补最小中性变体。材料仅用于隔离资格与事后评审，不送进正常Case输入：

| 主题 | 合法稿 | 缺陷稿 | 必须看到的审查结果 |
|---|---|---|---|
| 页面主线 | 操作入口、当前状态、下一动作与失败去向能沿流程读完 | 一行混装全部操作、路径只有“相关入口” | 指出读者无法执行/验收的具体跳转或状态，不按行数判错 |
| 唯一落点 | 流程说明操作，功能规则有唯一完整位置，验收保留可观察条件 | 流程/功能/异常三处重复完整规则 | 给出重复主题和保留位置，不删唯一异常或验收 |
| 图的职责 | 时序/状态/旅程各承担不同关系，纯表承接也完整 | 总览重画相邻两图、箭头把未知结果连成可重试 | 分别指出冗余与无依据的失败去向，不强迫固定图数 |
| SVG选择 | 无跨载体增益时明确不采用；有分散责任/时序时综合表达 | 因“已经有三张图”直接不采用，或只换颜色 | 区分真无增益与理由不成立；有价值但不能看图保持未完成 |

材料与实际发现对应后，作者在独立资格副本按发现修订，再由独立审查复核；保留原稿、任务、报告、修订稿，不能只看报告字段PASS。这里不规定固定返修次数，不要求把历史缺陷稿补成“本轮通过”。Mermaid用宿主现有解析/渲染入口核实际语法和画面，未取得渲染证据不写已可读。业务风险只按本次材料及实际用户决定处理，不从金样搬恢复接口。

若上述合法稿被误拒或缺陷稿漏审，先核任务是否实际收到现行要求。缺的是送达就修任务生产者；判据有歧义则在原判据位置改一处并同步消费者；契约已充分而模型漏判则记录为模型效果失败，不追加案例特例或“多跑几轮”来掩盖。此分类及负例交回是S1完成条件，不能整体留给未来正式CLI。

完成后交回给维护设计者评审，未授权不运行真实DSH。S2/S3可先做无此依赖的离线工作。
