# P3：选择性SVG、真实独审与阅读闭环

2026-10-17。依赖P2和00额度确认。沿用figure-view/figure-reading、VIEW_OWNER、现有flow与装置，不新增阅读调度器或后台服务。本页选择**保留一键显示/隐藏补充图**，不删除仍有效的用户能力，也不保留旧单图替换的并行模式。

## 1. 正式图与阅读图是不同对象

正式Mermaid继续用现有story-figure块和独立mmd，prepare首次建源、按源重铺和坏块诊断保留。它不再意味着必须制作SVG。SVG工作集合只取P2的reading.items，独立资产路径仍为 `AR/figures/<ID>.svg`，id不必等于任何Mermaid的id。

每个选择项在Story放置小节的末尾（同级下一节之前）有一个独立槽。同一位置多项按写作设计顺序排列。正式形态：

```markdown
<!-- story-reading:recovery-boundary:begin -->
<!-- story-reading:recovery-boundary:end -->
```

阅读形态只在槽内显示该候选：

```markdown
<!-- story-reading:recovery-boundary:begin -->
![清除后依据什么恢复操作](figures/recovery-boundary.svg)
<!-- story-reading:recovery-boundary:end -->
```

alt取选择项阅读问题，正确转义Markdown特殊字符。SVG支持多段文字、表格、多图的已有关系，不要求重画某单图；正文和Mermaid始终保留。正式Markdown没有本地SVG链接，上传端仍只接其已有合同的md；本地资产不能被宣传成远端已经归档。

这里禁止带入正式稿的是本机制生成的本地阅读SVG，不改变已登记原始材料图片的既有合同。正式检查/归档前沿现有链接解析核查：当前选择或 `AR/figures/` 阅读资产的普通链接/图片引用若在story-reading槽外，点名位置并阻断；作者移入合法槽或修正文，脚本不得为了清链接静默删除槽外内容。包含未选/已取消阅读图的遗留链接，不能因选择集合已空而漏检。

### view各命令的唯一语义

| 命令 | 本版动作 |
|---|---|
| prepare | 保留正式Mermaid建源；按当前选择在指定小节末尾建立空reading槽。位置不存在/歧义、标记坏或重复先一次报全、零写；不创造SVG |
| mermaid | 正式Mermaid按源还原；全部reading槽置空，块外正文不动 |
| svg | Mermaid不变；只把当前独审有效的选中SVG放入自己的reading槽；缺图/过期/失败的槽保持空并报原因，不展示旧图 |
| toggle/一键cmd | 有任一阅读槽展开则全部隐藏，否则展开当前可用的选中图；无选择时说明不需要SVG，正常无操作 |
| status | 只读报告当前选择、合法性与逐候选状态，不写文件、不触发自动重审 |
| review-request/review-check | 对选中候选生成/核对多依据请求；不存在于当前选择的ID明确拒绝 |

不保留SVG引用替换Mermaid块的逻辑。`story-figure`内出现旧SVG引用时明确报旧阅读格式，指向旧版切回正式形态或从init重起；不能按旧方式兼容读取并伪称新模式通过。

新增/删除/改位置的选择必须同时经prepare同步对应reading槽。已取消项的旧槽报告为孤立槽，清理时只移除脚本拥有且结构合法的槽，不改块外正文；SVG/证据不自动递归删除，作者按清理提示处理不再使用的资产并留必要历史。不把目录中恰好存在的SVG反向认成已选择项。

prepare是这一同步的明确修复入口：允许移除已取消项的成对合法槽，允许将仍选项的合法槽迁到声明的新位置并重排；正式处理/status检查仍报告孤立/错位，不能自行忽略。若边界坏、ID重复、槽内混入非脚本内容或新目标缺失/歧义，则整次零写，先修对应原因；不能因“改选择使旧槽非法”让prepare也永远拒绝合法迁位。

## 2. 多依据与请求身份

复用figure-reading现有目录：`AR/story-src/figures/<ID>.reading/{render.png,request.json,report.json}`。请求升为新version/METHOD，旧格式明确不支持，不并行维护v1分支。

请求由脚本生成并绑定：

- 当前候选的id、阅读问题、增益、放置位置及完整依据选择集合；
- 每项当前实际依据的规范化路径、唯一定位和内容摘要；完整文件绑定全文，选定章节绑定该章节实际内容，不额外绑定无关全文导致全图重审；
- 放置小节的正文范围与实际槽位置/顺序；
- SVG、实际递归本地资源、PNG的字节摘要；
- 新审查方法和必审维度。

内容以实际读取为准，不能只交作者手写摘要。请求生成时把依据内容和准确来源装入既有任务，独立审查者无需找维护仓或猜路径。依赖缺失/读取失败/标题歧义/越界均明确失败，不能发一个只含SVG的空依据请求。

**避免切换自激且不漏语义变化：**先验证story-reading标记配对、唯一、属于当前选择且放置正确，再在内存剔除整个阅读槽以计算正式Story依据；保留全部普通正文和Mermaid内容。不能像旧placement那样把所有图内容都剔除。切换槽的显示状态不改请求身份；改选择目的/依据、正式图源、正文事实、相关位置、SVG/资源/PNG会过期。status不为算摘要临时改盘。

所选Story范围包含story-figure块时，读取依据前只读核块内Mermaid与其权威mmd一致。只改mmd而正文未重铺时，报告“依据未同步”、旧图不得ready；不为计算哈希偷偷改正文，也不继续绑定旧正文假称当前。按现有正式重铺入口同步后重新取得依据与审查。

metadata只写可读依据说明，不再是权威来源或必须等于某份mmd；权威绑定是当前请求中实际取得的依据集合。XML、命名空间、有限正viewBox、受限本地引用及递归资源检查继续由现有figure-check一次产生，多个消费者复用同一结果，不能重复各写一套资源扫描。

## 3. 独立审查与价值判断

复用现有报告四键、执行引用、请求身份与状态判定，将旧semantic_equivalence替换为 `semantic_fidelity`，增加 `reading_gain`，保留 `visual_readability`、`placement`。报告缺必审项、互相矛盾、未读输入、UNKNOWN/SKIP或绑定过期均不算ready。

四项分别回答：

1. **事实与关系忠实**：相对全部依据，责任、条件、时序、结果、数量与未决是否准确；综合图可以补出已知关系，不须与单图逐节点相同，不得编造新规则。
2. **阅读增益**：是否回答选择中明确的阅读问题；与当前文字/表/Mermaid比较，是否把隐含或分散关系讲清。只有颜色/方向变化不足，图不需要时应回写作选择取消，并重新走正式内容审查，不在报告里硬给PASS。
3. **实际可读**：独立执行体确实打开当前PNG，核标签/箭头/布局/裁切；看不了就UNKNOWN，不以XML通过代替。
4. **位置相称**：图在该小节是否服务叙述，不替代必要正文、不与别处规则矛盾；输入须包括位置上下文，不能仅看SVG自洽。

作者先结构/渲染自验，再由独立上下文审查，原报告留存；真实独立发生仍由宿主日志证明，不让脚本从executor字符串认定。使用现有宿主独立能力，不依赖Agent hook、固定模型服务或新增依赖。

## 4. 完成与实际消费者

| 选择/证据 | readingWork结果 |
|---|---|
| 明确不采用、理由有效、声明/槽无冲突 | `applicable=false, complete=true, items=[]`；有Mermaid也不派补SVG任务 |
| 选择n项且全部当前ready | `applicable=true, complete=true` |
| 选择项缺SVG/渲染/报告、失败或过期 | `applicable=true, complete=false`，按项给恢复动作 |
| 缺选择节、坏声明、依据错误、标记/源结构坏、读失败 | `complete=false`及problems；不能当作不适用或零候选成功 |

complete只表示阅读集合，不能代替正式业务完成。删除选择或修改增益/依据会改变已有story-template正式输入身份，必须由原成文/审查链处理，不能因把失败候选删成零就绕过正式审查。写作设计已经进入登记与必审输入，沿原指纹责任，不新建签章状态。

`flow/routing.py::reading_work/reading_todo`、lifecycle/status/归档路由、test worker reading_facts/target_complete继续消费这一个生产结果；保持缺字段/矛盾状态不完成的既有反例。C01的host_concluded结束语义保持，不引入等待次数或重试上限。

保留VIEW_OWNER与现有正式前/后视图恢复：spec/plan author、pre-verifier、Story正式命令先隐藏补充SVG，完成或失败后只恢复当前可用的选择项；不吞业务错误。选择/依据变化使旧报告过期时恢复为正式空槽，说明哪些图需更新，不展示旧SVG。跨嵌套入口只由已有最外层所有者处理，避免二次往返。

必须检查并替换ensureMermaid及Python lifecycle中“没有story-figure就提前返回”的旧守卫：没有Mermaid、只有文字/表及选中reading槽也是合法输入，正式前隐藏和结束恢复照常执行。入口以实际两类标记/声明判断，不把无Mermaid当无阅读图或无须处理。

update/归档/restore仍使用正式形态，保留所需mmd、写作设计和既有内容快照；reading证据保持派生、恢复后重新按当前对象验。SVG未上传的事实写清楚；不要在archive适配器加未经授权的系统附件接口。仅本地可读不冒称远端SVG已交付。

## 5. 文件动作与退场

| 位置 | 动作 |
|---|---|
| figure-view.mjs | 正式图源检查保留，新增reading槽校验与显示；readingWork从选择枚举；替换旧svgRef/formOf中SVG替换Mermaid分支及metadata单源比较 |
| figure-reading.mjs | request/currentInputs/placement改为候选＋多依据；报告新方法；保留PNG/资源/摘要/原件和过期处理 |
| figure-check.py | 保留适用结构/引用/递归依赖，退出metadata必须是单mmd的规则；命令和JSON错误语义保留、同步消费者 |
| story-build.mjs、flow/client.mjs、flow/lifecycle.py、flow/routing.py、hooks/shared/story-view.mjs、相关author/pre-verifier | 接新结果与显示模式；保留正式前后所有权、失败恢复和一键入口，不另起守护流程 |
| story-write.md、reference/svg.md、SKILL/桥接/作者说明与升级演进 | 在做选择前交付价值标准、声明语法、依据/失败要求；退出每图必做/一对一等值/旧切换描述，说明本地与远端边界 |

任何移动不是新增另一套reader；旧metadata判据、旧请求/报告方法、旧完成集合及其专用测试在本包完整退出。保留普通Mermaid、原件图片、人工区、正式渲染、错误结构与所有权回归。

## 6. 定向验收

复用test_figure_view、test_reading_completion、test_story_build、test_verifier_chain、作者包、update/archive/restore相关用例，不新建测试平台：

- 有多个Mermaid但明确零SVG，阅读合法完成；缺声明不完成。正式与阅读两种状态不改变源和正文。
- 选择1份/多份SVG，依据可为正文＋表、多图、决策边界；错误ID、来源/位置缺失或歧义一次列全。
- 图源、相关正文、候选目的/依据、SVG/本地资源/PNG或位置变化使对应项过期；仅显示/隐藏和无关章节变化不误失效。
- 只修改权威mmd、Story尚未重铺时旧图不得ready；零Mermaid、只有综合reading槽时，author/pre-verifier/归档及失败恢复仍正确显隐且正式文本无SVG引用。
- 槽重复/孤立/错位置、Mermaid源缺失时正式动作报错且不破坏文件；不从metadata反写图源。
- 修改选择取消项/迁位置后，prepare可原子清理合法旧槽；边界损坏、重复ID、目标歧义时保持原字节，不能用强制清理删用户正文。
- 部分SVGready、部分失败：只显示可用项并说明其余；正式操作失败后仍正确恢复，业务返回码不被视图异常伪装成功。
- 一键脚本从带空格/特殊字符/自定义features_dir及extension_dir的位置可用，归档文本无本地SVG失效引用。
- 选中SVG/报告有效但槽外仍有普通阅读链接时，正式检查/归档必须拒绝并指出位置；已登记原始素材图片不被这条新规则误拦。
- 旧METHOD/旧SVG替换块明确拒绝，升级说明可达；没有为了兼容留下双协议路径。
- 独审输入确含全部依据与实际PNG；只结构完整但关系错、无增益的图不能被机械PASS当效果通过。

交回每个旧职责的新承担者、删除清单、消费者证据和G/X。离线证明机制契约，模型能否自然选图/少图但表达更好仍在P4后真实里程碑核验。
