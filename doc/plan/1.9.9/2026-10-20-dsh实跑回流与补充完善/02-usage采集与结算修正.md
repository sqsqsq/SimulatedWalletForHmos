# S2：usage初始化与结算修正

2026-10-20。只修本轮暴露的真实职责，不扩大为跨仓平台或效果评分。沿用`usage.py`唯一写入者、现有入口与Framework事实，不加agent hook，不让模型填时间。

## 1. 初始化顺序与版本判断

输入仍是需求根`.usage-input.json`，正常初始化时一次提供requirement/name/version及可知agent/model。**不再要求材料取得前写完整初始化信息。** 系统单由已有取材与init取得实际需求，本地单由现有材料入口取得内容；原作者任务随后在首次正式分析前写完整输入，下一个已有命令自动接收。

机械观察可以在输入缺失时记录使用事实、首次fw/ext；`name is None`沿现有字段表示语义初始化尚未接收。`usage.py::apply`在接收首份合法name/version时同时接收agent/model，四项一次冻结，显式null也冻结。name已有值后绝不补填或覆盖agent/model，后续切换不记录。本次已完成初始化的历史记录不回填。

这纠正的是“输入还没形成就把可选初始化值永久冻结”的时机，不引入新初始化状态文件。同步R8 spec原“晚来agent/model不覆盖首次未知”的句子：已接收初始化输入的未知不覆盖，输入尚未形成的机械暂存不算已接受语义初始化。不得让两个口径并存。需求明确名称优先，没有再按功能命名的现行规则不变。

业务版本优先级保持：明确需求交付版本 > 工程配置 > 未知。补清判别：需求文档“v0.4草稿/v1.0归档版”、Framework/Extension版本均不是业务发布版本；没有明确指定时读取本工程`AppScope/app.json5 > app.versionName`等真实配置。给一个与测试Case无关的中性正反例，不用AR90006硬编码。

测试worker在现有首次prompt里提供本次明确选择的宿主与模型身份事实，供正常输入使用；不把它写入knowledge、不修改用户DSH凭据，不凭generic adapter推断实际agent。一般业务仓模型不掌握精确路由时仍填null。这不是新metadata文件或额外上报动作。

验收：输入早于首次observe及晚于首次observe两条合法路径得到相同初始化值；首份输入明确null后不能补成其它值；首次缺输入仍记录使用并提示待补；重复和后续切换不更新；文档版号不冒充业务版号，明确交付版本覆盖工程配置。输入失败不消费文件、不覆盖既有初始化字段，允许既有机械使用事实照常记录并返回错误。

## 2. 时间与完成口径

保持start为“当前未结算工作区间起点”、spent为已结算步骤累计秒数，完成后start清空；统计仍按业务版本/初始化环境/步骤计算每需求平均耗时，未知不当0、不并成需求总耗时。

已核真实入口执行过begin，重点修复`flow/phase_facts.py::closure_event`与`usage.py::take_terminal`的事件身份和结算协作。不能只把“spent=None”改成“不赋值”，那会把真正缺起点的新工作冒充已知。

### 2.1 使用已有原生事实识别对象

- Framework阶段的材料身份优先取有效`verifier_subject_id`；没有verifier时，从现有`phase-evidence-manifest.json`取得业务inputs/outputs的路径、存在性、摘要及environment配置指纹。两条是当前Framework已存在的两种原生证据形态，不是旧格式兼容。排除该阶段报告目录内的运行报告与receipt自身；报告目录使用现有配置解析，不能写死路径。不把generated_at、closure_commit.committed_at、trace/summary摘要纳入同一业务对象身份。
- Story身份使用现有`story-flow.json > story_digests`和对应spec对象身份，不以story_written_at刷新认成新工作。
- update沿现有record的轮次ID与close/restore终态。

这是usage消费原生材料登记的稳定投影，仅用于去重结算；不代替Framework审查对象算法、闭环判定或生成另一份材料台账。清单缺失/损坏、对象无法证明时不猜，保留完成事实并明确耗时未知。

### 2.2 结算规则

`last_result.id`记上述对象/终态的稳定身份，`ended_at`保存已采纳的时间。沿现有字段，不另增运行状态文件。新游标ID使用`usage-terminal@2:<sha256>`显式标识身份算法；不要继续生成外形相同、含义不同的旧`sha256:...`。

规范化定案：manifest选中项按仓根相对POSIX路径排序，只投影`path/role/exists/sha256`，同一路径重复项一致时合并、不一致报身份未知；environment使用其已有配置/规则指纹键，规范JSON排序，不含机器绝对根。Story的story_digests按键排序。最终id包含来源种类、feature、step、终态种类及材料投影；同一材料在不同feature或不同step不能碰成同一事件。update保留其既有轮次身份。禁止对整份summary或manifest原文做摘要冒充稳定身份。

1. 无新begin、同对象仅刷新闭环时间：不新增区间，不清空已有spent，不推进已采纳终点。重复reconcile字节幂等。
2. 有新begin：旧终态时间不晚于该起点时不结束新区间；本次实际新闭环发生在起点之后才结算。即使业务对象最终未变化，也可结算真实进入过的工作区间；重复对账不再加时。
3. 无begin、对象确实变化后出现新完成：完成事实照记，累计耗时未知，不能保留旧数字冒充完整累计。
4. 多feature无法证明起止属于同一来源、同时刻相互冲突、缺证据：沿原未知规则；不拼接或平均猜值。

`take_terminal`执行顺序固定：先判断身份/归属是否可核 → 有active start时检查终点相对start并结算 → 无active start时按last_result身份判重复或缺起点的新对象。不能继续先过滤`id == last_result.id`，否则“新begin但最终材料相同”的合法工作永远无法结算。首次begin仍先对账旧终态再创建起点，重复begin不重置起点。

单源、起点10:00:00、首次完成10:01:00的预期为spent=60/start=null；同材料10:02:00再闭环仍为60；10:03:00显式begin、同材料10:03:30闭环变为90；随后同一事件重复读取仍为90；无begin而业务材料变化后10:04:00完成则为unknown。此序列同时覆盖“重复检查不能毁掉已知时间”和“真实未知不能保留假精确数字”。

实现前在当前运行副本按原工具序列复现首次begin、首次闭环、重新harness/成文登记，留下中间usage；正式原件不改。读取非空旧算法游标时在合同校验处明确报不支持，原文件不改，指向旧开发版收口或保留旧记录后从init重起；不猜测迁移、不混用两种身份算法。空usage和last_result=null仍合法，不制造历史数据。适配升级说明写明本版开发期间的算法变更与处置，样例/夹具重建新身份，旧实跑证据保持原字节。

## 3. 消费者、退出与验证

修改`usage.py`、`phase_facts.py`中上述对应职责；检查update也消费phase_facts的地方，不能改变其业务闭环语义。删除旧“以闭环时间刷新作为新对象”的结算解释和专用断言，迁移有效的毫秒、时区、多源、重复、撤回、锁与原子写覆盖。

文件责任具体如下：`phase_facts.py`只增加只读的usage结算身份提取，已有`summary/phase_facts/closure_status`对update的返回语义不改；`usage.py::events/take_terminal/apply`消费该身份、执行上述顺序；`hooks/shared/usage.mjs`仍只observe/reconcile，不能把首次检查时间当start；spec/plan作者入口和story skeleton/chapter继续begin；`story-stats/scripts/stats.py`只读既有spent，不自行重算区间。更新现有`test_usage.py`与stats测试，不另建计时器。

定向组合测试必须包含：同对象三次harness/登记spent保持；新begin+新闭环只加一次；未调用begin但换对象记未知；generic无verifier仍能按可核材料识别，同材料报告刷新不计新轮；坏清单不假精确；Story和spec各自结算且重叠不相加为需求总时长；stats均值分母只取该步骤已知耗时样本，未知计数仍显示。

使用记录中的PASS/completed继续描述原生结果与完成事实，不额外定义“质量评分”字段；报告说明不能把它当独立审查通过。DSH无verifier的问题由S1解决，不用usage旁路改变Framework完成判定。

同步`contracts/usage.json`的字段说明、R8 spec/方案当前口径、stats方法/模板与预期样例中受影响的时间说明。样例数字不因新实现而随意重算，不新增逐需求明细。测试装置全局usage快照由S3承担，不修改生产记录器的Git身份统计口径。

预计交付实现G130/X30。完成后独立交审，预算与上游依赖见99。
