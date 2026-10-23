# S1：SVG以源码语义审查为主

依据用户2026-10-21决定；预算与推进按[00](00-执行总览与预算.md)。预计G30/X60。本步保留独立审查，退出强制PNG及多模态前置，不建新的视觉工作流。

## 1. 最终行为

作者按现有写作设计画SVG，跑结构检查，再跑 `story-build view --mode review-request --id <ID>`。请求绑定当前选择、依据、放置上下文、SVG和本地依赖资源；无需render.png，不再接受 `--render` 参数。审查者读SVG源码与实际依据，返回原JSON骨架，只核三项：`semantic_fidelity`、`reading_gain`、`placement`。

三项分别判断事实/关系忠实、相对正文/表/Mermaid是否真有增益、放置是否服务叙述。不是只读title/metadata，要核实际text、图元和连接，不能拿作者自述当图中实际内容。没有增益应取消候选或改表达，不能为“用了SVG”而保留换色副本。

XML、viewBox、资源存在/路径和正文保护仍由现有脚本承担。文字型SVG的坐标、标签和连线可供模型判断，但本结论只证明源码语义，不声称实际字体、裁切或遮挡已经逐像素验收。实际渲染按有需要时使用现有浏览器/工具或人检查；不要求每张图保存PNG证据，不加视觉状态字段或必跑审查阶段。发现真实显示缺陷照常修，不能因可选检查而隐瞒已知缺陷。

若必要业务事实只在嵌入位图/转曲路径中，文字依据也不能说明，审查者如实列该必要输入未核；应补可读依据或人工核实，不能以“文本优先”为由编造其内容。仅未查看可选渲染截图不进入阻塞性unreviewed。

## 2. 文件动作与退出

| 文件 | 实施动作 |
|---|---|
| `extensions/skills/story/scripts/core/story/figure-reading.mjs` | currentInputs退出render读取/缺件；readingRequest退出renderFrom复制与PNG签名校验；READING_CHECKS去visual_readability；requestBody只绑定必要输入；旧assetsOf/按渲染区分的分支退掉，变化后统一生成新语义请求并独审，无关章节/显隐仍保持有效 |
| 同文件reportProblems/reviewTask | 原有request_id、executor、checks、blocking_findings、advisories、unreviewed继续使用；三项PASS/WARN且无阻断/必要未审才ready。退出要求“打开PNG”的任务、UNKNOWN视觉阻塞和四项报告示例；ready原因说明“源码语义审查完成，本结论不含渲染外观验收”，不新增字段 |
| `core/story/figure-view.mjs::reviewRequest`、`core/story-build.mjs` | 删除render参数透传、命令选项及help；status/review-check/显示消费同一三项结果；不加第二套完成规则。部分ready、一键显隐、mmd真源、外层恢复、正式归档无SVG链接保持 |
| `extensions/skills/story/reference/svg.md`、`phases/story-write.md`相关段 | 写清默认源码审查、必要输入、调用角色、报告原样返回和最小失败处置；原“渲染→PNG→看图”必跑链与按渲染变化恢复表退出，保留简短“必要语义输入变化重审，缺报告补报告”规则 |
| `doc/spec/1.9.9/08-SVG表达与交付.md`与当前执行/验收入口 | 更新有效合同，取消旧四项/必渲染/必看图口径；已完成方案、CLI原件和历史评审不回写成新版本结果 |

只升级既有请求到version=3、method=`story-reading-review/3`，不另建schema体系。旧version=2明确报不支持，指向旧版收口或从init重起，不自动转换旧报告、不双轨兼容。测试夹具使用新请求；真实历史目录不清理补造。已遗留的render.png不再参与请求、状态或完成判断，不要求作者为了退场删除历史图片。

## 3. 宿主调用与失败

DSH当前 `demo/.dsh/framework-verifier.patch.yml`及 `demo/framework/agents/dsh/templates/agents/framework-verifier.patch.yml`已支持自足任务。生成任务明确调用现有专用 `verifier({description,prompt:<完整自足任务>})`，同步取得最终JSON；不走通用后台subagent，不用send_message/list_agents轮询催收，不附自拟报告格式。作者只填宿主执行引用，其余原样存入report.json。

其它宿主使用现有明确支持自足输入/JSON原回复的独立只读审查入口或独立会话，沿既有工具合同交接。已核OpenCode的阶段verifier只收maison request，不在本包将自足任务塞给它；不伪造Framework request，不新增角色、不改demo/framework或阶段审查协议。若当前宿主没有可用独立会话能力，明确报“独立审查入口缺失”，保留工作与请求；这与“无图像能力”不同，不据此假签通过。DSH为本轮已核可执行的真实验收主宿主，其它宿主不虚报资格。

无回复、格式不合或调用中断：保留当前请求和原回复，指出具体缺口；修好调用条件后将同一任务完整交审，不由父作者补结论。输入没变不重画图，不新建补偿/催收机制；业务流程仍可按既有规则完成，阅读状态单列。

## 4. 验收

复用test_figure_view.py、test_reading_completion.py、归档/update与原独审合同用例。删除只证明必需PNG、render字节改变导致过期、visual_readability缺项阻塞的专用断言，保留缺源/坏XML/资源/请求绑定/独立回复/正文保护的有效覆盖。

定向必须区分：无PNG可发新请求且结构合法三项报告可显示；错误request_id/缺必要语义项/语义FAIL仍不能显示；SVG或实际依据变化使旧报告失效，显隐/无关章节不失效；位图独占的必要事实未核不能假PASS；没有增益的报告FAIL保持不完成。脚本桩只证消费行为。真实DSH文本模型能读SVG并经专用verifier返回原报告、无read_image硬前置，由用户授权后取得。
