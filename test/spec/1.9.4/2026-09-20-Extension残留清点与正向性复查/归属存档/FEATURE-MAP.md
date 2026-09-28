# Extension 逐文件归属与处置判定（2026-09-11 轮退场诊断存档）

> 本文件是当年为定位「旧机制、废弃功能无法退场」所做的全文件扫描判定，属一次性诊断存档，不随实现维护；当前事实以[全盘分析](../00-全盘分析报告.md)为准。
> 2026-09-20 由 `plan/1.9.1/2026-09-11-Extension功能全集与机制归属/` 迁入本目录 `归属存档/`（1.9.1 遗留 L14 落地）。

> 基线 `d36edb70f04c60128c2e07501c7eff5fa299c07f`。基线时点实现未清理（其后的清理已由 1.9.2/1.9.3 轮实施，落地状态见[全盘分析](../00-全盘分析报告.md) §4）；本表的目标由38组必要性比较和R01–R21确定，不再仅写“同左保留”。D01–D03须保住原功能后修正，不能按旧机制删除。
> 本表约定：区间级功能归属以 FEATURE-CONTENT-MAP 各区间行的「功能」列为真源，承担文件链接跳转对应节，本表不重复区间号；待处理列为「—」＝按同功能实现比较结论保留其必要职责、不新增平行实现；同一 M 编号只在首次出现的节保留摘录，定义见 01-归属判定与整体审查.md。

[功能全集](FEATURES.md)定义目标；[逐内容判定](FEATURE-CONTENT-MAP.md)提供全部区间；[比较依据](../../../../plan/1.9.1/2026-09-11-Extension功能全集与机制归属/01-归属判定与整体审查.md)和[退出范围](../../../../plan/1.9.1/2026-09-11-Extension功能全集与机制归属/02-旧机制退出范围.md)给决定。其中经 1.9.2/1.9.3 已实施的 R 动作，落地状态见[全盘分析](../00-全盘分析报告.md) §4 与 [FEATURE-CONTENT-MAP](FEATURE-CONTENT-MAP.md)「2026-09-20 漂移记录」。

## F1 需求取材与范围确定

- **M01 保留两种职责，旧成文init不受保护**：适配器按协议取材，flow一次建缺件；真实仓对接与demo替身分开。保护：删适配器会失去远程取材；删flow骨架会失去本地起手，二者不能互代。
- **M02 保留共享转换，调用成本列运行观察**：导入算法一份；轮次核验复用；不新增“导入成功”自证状态。保护：只保留导入日志无法发现原件同名换内容；只比文件名会误判已导入。
- **M03 合并输入并退出未登记副本旁路（R11/R12）**：一个身份一项输入，保留路径别名；引用必须登记；现有已登记assets合法。保护：不能删除图片采用/排除判断或内容身份，不能把登记路径数当图片数。
- **M04 保留三种对象；不扩通用版本系统**：同一材料计算复用；只记录会影响确认或引用的时点。保护：删轮次关联会使旧决定套新料；删basis会让SE#编号错绑。
- **M05 保留，压缩重复说明而非删确认链**：一个人决定只落一次，原选择集可追溯；字段约束共用。保护：删选项集会失去可推翻的范围依据，删份表无法解释兄弟边界。
- **M06 保留完整职责**：预检→留原输入→候选覆盖→同轮基准→complete，部分失败可重试。保护：删留存会让派生稿冒充原始证据；不允许任意现状重新签基准。
- **M16 R10退全量围栏复制，保留图源检测**：作者包给来源图目录/精确位置；初筛和编排读原文；最终核对应。保护：不能借减输入删除图源对应或把图压成箭头散文。

| 当前承担文件 | 待处理 |
|---|---|
| 组合特性 | 由子特性承担 | 不另建父级实现层 |
## F1.1 需求系统与本地起手

- **M01**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | — |
| [skills/story/scripts/README.md](FEATURE-CONTENT-MAP.md#P597ffdca) | — |
| [skills/story/scripts/adapters/story.js](FEATURE-CONTENT-MAP.md#Pc2301217) | — |
| [skills/story/scripts/adapters/token.js](FEATURE-CONTENT-MAP.md#P456ec299) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
| [skills/story/templates/inbox-readme.md](FEATURE-CONTENT-MAP.md#P685a03be) | — |
## F1.2 补充正文与格式转换

- **M02**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/rules/inbox_import.md](FEATURE-CONTENT-MAP.md#Pbf4c9f32) | — |
| [skills/story/scripts/README.md](FEATURE-CONTENT-MAP.md#P597ffdca) | — |
| [skills/story/scripts/core/import_sources.py](FEATURE-CONTENT-MAP.md#P5a530458) | — |
| [skills/story/templates/inbox-readme.md](FEATURE-CONTENT-MAP.md#P685a03be) | — |
## F1.3 图片身份与用途

- **M03**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。
- **M16**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | — |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R10,R12；其余按职责保留 |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R11；其余按职责保留 |
| [skills/story/rules/inbox_import.md](FEATURE-CONTENT-MAP.md#Pbf4c9f32) | — |
| [skills/story/scripts/core/import_sources.py](FEATURE-CONTENT-MAP.md#P5a530458) | — |
| [skills/story/scripts/core/materials.py](FEATURE-CONTENT-MAP.md#Pa2f7a68f) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R11；其余按职责保留 |
## F1.4 来源盘点与增量变化

- **M04**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/rules/init_analysis.md](FEATURE-CONTENT-MAP.md#Peb731b33) | — |
| [skills/story/scripts/core/materials.py](FEATURE-CONTENT-MAP.md#Pa2f7a68f) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01,R13；其余按职责保留 |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F1.5 需求与范围分析

- **M05**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/rules/ar_design_init.md](FEATURE-CONTENT-MAP.md#Pacd7f161) | — |
| [skills/story/rules/init_analysis.md](FEATURE-CONTENT-MAP.md#Peb731b33) | — |
## F1.6 人定材料与承载范围

- **M05**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | — |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | — |
| [skills/story/rules/init_analysis.md](FEATURE-CONTENT-MAP.md#Peb731b33) | — |
| [skills/story/rules/scope_gate.md](FEATURE-CONTENT-MAP.md#P366a5367) | — |
| [skills/story/scripts/core/flow-check.mjs](FEATURE-CONTENT-MAP.md#P4ec8b22e) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F1.7 形成开发需求输入

- **M06**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/rules/ar_design_init.md](FEATURE-CONTENT-MAP.md#Pacd7f161) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F2 面向人的Story

- **M07 删除旧入口并统一来源存在性职责（R01/R13）**：indexSources及同一必需来源判据供sources/assembly/check，optional只提示；offline显式结构模式保留。保护：不删除ensureDecisions，也不因最小夹具改变正常运行的必需来源语义。
- **M08 保留当前职责**：ATX/父前导与原文位置，文件级basis，变化给候选不自动重绑。保护：删context会丢上级前提；逐单元强填会恢复已退台账。
- **M09 合并为已有纯模块的同一读取/解析职责（R09）**：story-sources提供文本解析与有效取舍；作者/审查各自渲染，不跨进程、不复制政策。保护：不能删除审查者对omit/defer/未分配的访问，不能以作者布局裁定真实覆盖。
- **M10 保留，元数据由脚本提供**：按需求编排一次，新增认识允许深化，业务变化回真源。保护：删template会回到每章重新规划；把它当答案又会限制正文。
- **M11 保留，不判为旧双源**：一个视图写入口，原件不改；只在本章需要时读共享正文。保护：删视图会把定位和上下文搬运还给模型；盲减输入会损失前提。
- **M12 保留有界提示；撤回原Q03强改要求**：可比旧/新标记和文字变动；不增持久化快照；不当完整影响分析。保护：直接删去会失去现有改动提示；换结构化却不保存旧输入逻辑不成立。
- **M13 保留可靠落盘**：只替目标章；已有稿不重播；必要种子说明剥离，机器区标记保留。保护：删章提交会恢复整篇重写和中断丢稿风险。
- **M14 保留两类要求，合并重叠执行结果**：稳定凭据不可由作者取消；动态结构可随编排改；同项重叠不重复播种。保护：删稳定要求会丢验收/附录凭据；只保留稳定要求又不能落实本次选择。
- **M15 R02/R14退出阈值与重复禁令，保留方法**：按读者问题、关系与复杂度选形式；独有信息优先。保护：不能全删通用指导让模型自觉，也不能以表格配额证明可读。
- **M16**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。
- **M17 R07替换两套旧行核对为同源只读投影比对**：复用现行投影计算，比较机器区与当前预期；作者解释区不参与机器区比较；手改保护保留。保护：不能直接删⑦/⑫b造成单独check失去校验；替代必须能发现丢行与改值。
- **M18 R15退出散文块数量规则，保留目录与引用核验**：材料一项能追溯贡献及来源，额外说明按语义检查；保留五节与机器区。保护：不删来源完整、非来源混入、坏链接检查，不开放任意影子契约表。
- **M19 保留明确机械规则；整理旧解释按R18**：规范化只处理编号/标识/路径；语义风格不凭关键词外推。保护：删路径检查可能产出打不开的归档件；单有number不能保证输入身份。
- **M25 保留差异化投影，不合并业务判断副本**：只读knowledge-use，领域规范化结果复用；各视图只渲染本消费者需要的列。保护：只剩Spec命中表会丢不适用依据；只剩Story汇总不够编码。
- **M38 保留整稿；R21补回稳定读者目标的作者送达，非恢复整份旧note**：编排前从现有合同读questions，聚焦控制对象/存量/在途/恢复；正文按需求实例化，不复制两份细则。保护：删整稿会漏跨章；把旧note全恢复会恢复双源。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01；其余按职责保留 |
## F2.1 成文前原材料定位与初筛

- **M07**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M08**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R11；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01,R13；其余按职责保留 |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
## F2.2 Spec与写作设计衔接

- **M08**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M09**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M10**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | — |
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | R09；其余按职责保留 |
| [hooks/spec/author.md](FEATURE-CONTENT-MAP.md#Pf87c4656) | — |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R19；其余按职责保留 |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R16,R18,R19；其余按职责保留 |
| [rules/spec-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P4ccef0f2) | R16；其余按职责保留 |
| [skills/story/phases/spec.md](FEATURE-CONTENT-MAP.md#P57e420ad) | — |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R21；其余按职责保留 |
| [skills/story/reference/evidence-rules.md](FEATURE-CONTENT-MAP.md#P73dcd951) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R09；其余按职责保留 |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
| [skills/story/templates/spec-sections.md](FEATURE-CONTENT-MAP.md#P12ec7582) | — |
## F2.3 按需材料送达

- **M11**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M12**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R10；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R10；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
## F2.4 正文表达与可靠落盘

- **M13**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M14**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M15**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M16**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。
- **M38**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | — |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R02,R14；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R18；其余按职责保留 |
## F2.4.1 读者问题与章节职责

- **M14**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R21；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R02,R14,R21；其余按职责保留 |
## F2.4.2 图表与正文协作

- **M14**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M15**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M16**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | R02,R20；其余按职责保留 |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R10,R12；其余按职责保留 |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R15；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R02,R10,R14；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
## F2.4.3 验收与交付可操作

- **M15**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M38**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R21；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R21；其余按职责保留 |
## F2.5 契约查阅附录

- **M17**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M18**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M25**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R15；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R07,R15,R18；其余按职责保留 |
## F2.6 标题引用与可读整理

- **M18**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M19**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R16；其余按职责保留 |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | R11,R15；其余按职责保留 |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R02,R14；其余按职责保留 |
| [skills/story/scripts/core/headings.mjs](FEATURE-CONTENT-MAP.md#Pb26a1685) | — |
| [skills/story/scripts/core/lint-rules.mjs](FEATURE-CONTENT-MAP.md#P7cd4d399) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R07,R11,R13,R15,R18；其余按职责保留 |
## F2.7 写后整篇核对

- **M38**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | — |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | — |
## F3 决策与评审回流

- **M20 保留功能；将重复方法归规则源**：Review文档由一份decisions渲染，人工区域原样保留。保护：删除机器区保护会覆盖人意见；删除类别词表会改变当前组织协议。
- **M21 保留，R04清授权冲突**：用户选择后上传；反馈原样回流并修责任产物；本地单无远程动作。保护：不能因restore与reopen名称像就删一个。

| 当前承担文件 | 待处理 |
|---|---|
| 组合特性 | 由子特性承担 | 不另建父级实现层 |
## F3.1 发现并解释判断

- **M20**：摘录见「F3 决策与评审回流」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | — |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | — |
| [skills/story/scripts/core/review-render.mjs](FEATURE-CONTENT-MAP.md#P96d19165) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01,R13；其余按职责保留 |
## F3.2 生成评审件并保护人工区

- **M20**：摘录见「F3 决策与评审回流」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/scripts/core/review-render.mjs](FEATURE-CONTENT-MAP.md#P96d19165) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01,R18；其余按职责保留 |
## F3.3 归档与远程恢复

- **M21**：摘录见「F3 决策与评审回流」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | R04；其余按职责保留 |
| [skills/story/scripts/adapters/story.js](FEATURE-CONTENT-MAP.md#Pc2301217) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F3.4 获取并处置评审反馈

- **M21**：摘录见「F3 决策与评审回流」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | — |
| [skills/story/rules/review_reflow.md](FEATURE-CONTENT-MAP.md#P2adb3d49) | — |
| [skills/story/scripts/adapters/review.js](FEATURE-CONTENT-MAP.md#P09f94671) | — |
| [skills/story/scripts/adapters/story.js](FEATURE-CONTENT-MAP.md#Pc2301217) | — |
## F4 知识应用与维护解耦

- **M22 保留并区分错误与未配置**：manifest一份声明、纯解析复用、知识域动态发现。保护：按目录文件名猜类型会把目标知识配置错读；不允许坏清单静默空集。
- **M23 R17替换禁止新增的泛化，保留事实约束**：既有能力按仓核实；本轮新增按需求设计说明。保护：不删除画像或核实现状；不得凭事实库缺项断定需求禁止。
- **M24 保留知识判断，R16退出词面等同语义的裁决**：机械检查只核来源字段与可定位性；真假/换算由既有verifier核，不增另一份说明台账。保护：不能整个删来源保护或把空理由通过；不能为匹配字符改事实。
- **M25**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M26 保留功能，D02/D03修缺口，不称旧机制删除**：无在册模式空表合法；有模式仍需判断；候选以unit+pattern完整保留。保护：不能把整个模式功能因未测删掉，不能用只能一个模式规避数据丢失。
- **M27 保留，限定结论能力**：Plan实体must是下游输入，脚本仅核存在/给定模式，verifier看实际作用。保护：删义务链等于删已交付知识能力，不是清残留。
- **M28 保留**：报告完整与语义落实分工；统一同一id定义，不复述原规约充数。保护：删结构会难以查漏；删语义则只有“名字出现”。
- **M29 R19合并解析保留策略；D01修一对多；R06退困难即转device**：结构化条目全集一次提取，调用者选集合，must.verify不因测不了自动改。保护：不得放宽Spec桥接，不得删both、不用测试名代替断言。
- **M37 保留有效内容，不按无import删除；R17仅修明确歧义**：域/模式条目不固化成机制枚举；阶段建议不能冒充Framework路由。保护：删样板即删内容能力，不能计作机制瘦身。

| 当前承担文件 | 待处理 |
|---|---|
| 组合特性 | 由子特性承担 | 不另建父级实现层 |
## F4.1 知识登记与读取

- **M22**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M37**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | — |
| [hooks/shared/knowledge.mjs](FEATURE-CONTENT-MAP.md#Pef6ceb7a) | — |
| [knowledge/README.md](FEATURE-CONTENT-MAP.md#P40d54a8c) | — |
| [manifest.yaml](FEATURE-CONTENT-MAP.md#P7a130749) | — |
## F4.2 项目事实与部件画像

- **M23**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M37**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/knowledge.mjs](FEATURE-CONTENT-MAP.md#Pef6ceb7a) | — |
| [knowledge/facts/README.md](FEATURE-CONTENT-MAP.md#P398c66b1) | R17；其余按职责保留 |
| [knowledge/facts/codebase-facts.md](FEATURE-CONTENT-MAP.md#P21b2c3ab) | — |
| [knowledge/facts/component-profile.md](FEATURE-CONTENT-MAP.md#P960ae9dd) | — |
## F4.3 规约适用与具体要求

- **M24**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M25**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M37**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/contracts.mjs](FEATURE-CONTENT-MAP.md#P583825d8) | D01,R19；其余按职责保留 |
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | D02；其余按职责保留 |
| [hooks/shared/knowledge.mjs](FEATURE-CONTENT-MAP.md#Pef6ceb7a) | — |
| [hooks/spec/author.md](FEATURE-CONTENT-MAP.md#Pf87c4656) | — |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R19；其余按职责保留 |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R16,R18,R19；其余按职责保留 |
| [knowledge/constraints/README.md](FEATURE-CONTENT-MAP.md#P81b126c3) | — |
| [knowledge/constraints/compatibility-checklist.md](FEATURE-CONTENT-MAP.md#P35e5bb95) | — |
| [knowledge/constraints/deliverables.md](FEATURE-CONTENT-MAP.md#Pb5a8f608) | — |
| [knowledge/constraints/dfx-baseline.md](FEATURE-CONTENT-MAP.md#P1cbb8906) | — |
| [knowledge/constraints/env-exceptions.md](FEATURE-CONTENT-MAP.md#P65753a34) | — |
| [knowledge/constraints/observability.md](FEATURE-CONTENT-MAP.md#P976a8bf4) | — |
| [knowledge/constraints/resource-usage.md](FEATURE-CONTENT-MAP.md#P8e53b7cd) | — |
| [knowledge/constraints/security-privacy.md](FEATURE-CONTENT-MAP.md#Pce1f6404) | — |
| [knowledge/constraints/ux-consistency.md](FEATURE-CONTENT-MAP.md#P6805ef8a) | — |
| [rules/spec-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P4ccef0f2) | R16；其余按职责保留 |
| [skills/story/phases/spec.md](FEATURE-CONTENT-MAP.md#P57e420ad) | — |
| [skills/story/reference/evidence-rules.md](FEATURE-CONTENT-MAP.md#P73dcd951) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R18；其余按职责保留 |
| [skills/story/templates/spec-sections.md](FEATURE-CONTENT-MAP.md#P12ec7582) | — |
## F4.4 设计模式候选与选择

- **M26**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M37**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/plan/post_check.mjs](FEATURE-CONTENT-MAP.md#P4cf2f673) | D03；其余按职责保留 |
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | — |
| [hooks/shared/knowledge.mjs](FEATURE-CONTENT-MAP.md#Pef6ceb7a) | — |
| [hooks/shared/obligations.mjs](FEATURE-CONTENT-MAP.md#Pf51c4105) | — |
| [hooks/spec/author.md](FEATURE-CONTENT-MAP.md#Pf87c4656) | — |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R19；其余按职责保留 |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [knowledge/design-patterns/README.md](FEATURE-CONTENT-MAP.md#Pd2c1a3f3) | R22；其余按职责保留 |
| [knowledge/design-patterns/decision-tree.md](FEATURE-CONTENT-MAP.md#P7f2b4ecd) | R22；其余按职责保留 |
| [knowledge/design-patterns/page-interaction.md](FEATURE-CONTENT-MAP.md#P58a4ee39) | R22；其余按职责保留 |
| [rules/spec-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P4ccef0f2) | R16；其余按职责保留 |
| [skills/story/phases/spec.md](FEATURE-CONTENT-MAP.md#P57e420ad) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/templates/spec-sections.md](FEATURE-CONTENT-MAP.md#P12ec7582) | — |
## F4.5 Plan知识设计与义务传递

- **M27**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/plan/author.md](FEATURE-CONTENT-MAP.md#Pa01400a4) | R23；其余按职责保留 |
| [hooks/plan/post_check.mjs](FEATURE-CONTENT-MAP.md#P4cf2f673) | D03；其余按职责保留 |
| [hooks/shared/contracts.mjs](FEATURE-CONTENT-MAP.md#P583825d8) | — |
| [hooks/shared/knowledge-use.mjs](FEATURE-CONTENT-MAP.md#P9aa3042d) | — |
| [hooks/shared/knowledge.mjs](FEATURE-CONTENT-MAP.md#Pef6ceb7a) | — |
| [hooks/shared/obligations.mjs](FEATURE-CONTENT-MAP.md#Pf51c4105) | — |
| [knowledge/design-patterns/README.md](FEATURE-CONTENT-MAP.md#Pd2c1a3f3) | R22；其余按职责保留 |
| [knowledge/design-patterns/decision-tree.md](FEATURE-CONTENT-MAP.md#P7f2b4ecd) | R22；其余按职责保留 |
| [knowledge/design-patterns/page-interaction.md](FEATURE-CONTENT-MAP.md#P58a4ee39) | R22；其余按职责保留 |
| [rules/plan-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Paafa935f) | — |
| [skills/story/templates/plan-sections.md](FEATURE-CONTENT-MAP.md#Pa8025ed4) | — |
## F4.6 Coding落实与可执行检查

- **M27**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/coding/author.md](FEATURE-CONTENT-MAP.md#Pb9ae9229) | — |
| [hooks/coding/post_check.mjs](FEATURE-CONTENT-MAP.md#P5e70c0fd) | — |
| [hooks/shared/contracts.mjs](FEATURE-CONTENT-MAP.md#P583825d8) | — |
| [hooks/shared/obligations.mjs](FEATURE-CONTENT-MAP.md#Pf51c4105) | — |
| [hooks/shared/probes.mjs](FEATURE-CONTENT-MAP.md#P217c29f4) | — |
| [knowledge/design-patterns/README.md](FEATURE-CONTENT-MAP.md#Pd2c1a3f3) | R22；其余按职责保留 |
| [knowledge/design-patterns/decision-tree.md](FEATURE-CONTENT-MAP.md#P7f2b4ecd) | R22；其余按职责保留 |
| [knowledge/design-patterns/page-interaction.md](FEATURE-CONTENT-MAP.md#P58a4ee39) | R22；其余按职责保留 |
| [rules/coding-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Pb04de125) | — |
## F4.7 Review知识复核

- **M28**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/review/author.md](FEATURE-CONTENT-MAP.md#P5e948c22) | — |
| [hooks/review/post_check.mjs](FEATURE-CONTENT-MAP.md#P2cb62240) | — |
| [hooks/shared/pre_verifier.mjs](FEATURE-CONTENT-MAP.md#P17056b41) | — |
| [rules/review-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P8820de89) | — |
## F4.8 UT义务验证

- **M29**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/contracts.mjs](FEATURE-CONTENT-MAP.md#P583825d8) | D01,R19；其余按职责保留 |
| [hooks/shared/obligations.mjs](FEATURE-CONTENT-MAP.md#Pf51c4105) | — |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [hooks/ut/author.md](FEATURE-CONTENT-MAP.md#P39c90524) | R06；其余按职责保留 |
| [hooks/ut/post_check.mjs](FEATURE-CONTENT-MAP.md#P074e60a5) | R06；其余按职责保留 |
| [rules/ut-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P3bed6c8d) | — |
## F4.9 实机及其他验证分派

- **M29**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/contracts.mjs](FEATURE-CONTENT-MAP.md#P583825d8) | D01,R19；其余按职责保留 |
| [hooks/shared/obligations.mjs](FEATURE-CONTENT-MAP.md#Pf51c4105) | — |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [hooks/testing/author.md](FEATURE-CONTENT-MAP.md#P66e23afd) | — |
| [hooks/testing/post_check.mjs](FEATURE-CONTENT-MAP.md#P11d3a6c3) | — |
| [rules/testing-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Pa3bfe6c6) | — |
## F5 推进恢复与交付保障

- **M12**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M30 保留入口与必要当次提示，R05/R10/R14/R18去旧段**：原则一份、动态数据一份、当前动作简短；不必为每阶段再写全文方法。保护：一味只留链接可能导致行动前未送达；不能只靠报错教学。
- **M31 R08退Python子路由**：complete后Python只指prepare；prepare承接缺知识判断入口及Spec时点，不起Node查询。保护：不能先删Python再留下知识init无人指路；不是删除范围/S4状态机。
- **M32 保留复用，退出并行旧来源检查见R13**：字段校验与来源变化一次定义，登记固定当前结果，返修解相应冻结。保护：删任一时点会让错误输入先成文或变更后登记；不增加分章版本票据。
- **M33 R09复用数据解析；R20退重复语义规则文本；R04授权对齐**：overlay唯一定义如何审，request装输入/必要读法，Framework原生凭据。保护：不能删Story/template全文或未采用来源入口；不把能力缺失当PASS。
- **M34 保留，不能以只有维护者读取为由删除**：维护者是合法消费者；证据不参与另一套状态机。保护：删evidence会失去当前PASS执行事实；删旁路不省任务算法只损可查性。

| 当前承担文件 | 待处理 |
|---|---|
| 组合特性 | 由子特性承担 | 不另建父级实现层 |
## F5.1 阶段作者任务送达

- **M30**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/coding/author.md](FEATURE-CONTENT-MAP.md#Pb9ae9229) | — |
| [hooks/plan/author.md](FEATURE-CONTENT-MAP.md#Pa01400a4) | R23；其余按职责保留 |
| [hooks/review/author.md](FEATURE-CONTENT-MAP.md#P5e948c22) | — |
| [hooks/spec/author.md](FEATURE-CONTENT-MAP.md#Pf87c4656) | — |
| [hooks/spec/author.mjs](FEATURE-CONTENT-MAP.md#P2aad25c7) | R10,R12,R19；其余按职责保留 |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [hooks/testing/author.md](FEATURE-CONTENT-MAP.md#P66e23afd) | — |
| [hooks/ut/author.md](FEATURE-CONTENT-MAP.md#P39c90524) | R06；其余按职责保留 |
| [skills/story/AGENTS.section.md](FEATURE-CONTENT-MAP.md#P1c4934f5) | — |
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | R03,R04,R05；其余按职责保留 |
| [skills/story/phases/spec.md](FEATURE-CONTENT-MAP.md#P57e420ad) | — |
| [skills/story/phases/story-write.md](FEATURE-CONTENT-MAP.md#P3907448a) | R10；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R18；其余按职责保留 |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | R08；其余按职责保留 |
| [skills/story/templates/spec-sections.md](FEATURE-CONTENT-MAP.md#P12ec7582) | — |
## F5.2 进度与中断恢复

- **M31**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | R03,R04,R05；其余按职责保留 |
| [skills/story/rules/init_analysis.md](FEATURE-CONTENT-MAP.md#Peb731b33) | — |
| [skills/story/scripts/core/flow-check.mjs](FEATURE-CONTENT-MAP.md#P4ec8b22e) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | R08；其余按职责保留 |
## F5.3 确定性校验与登记

- **M32**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/evidence.mjs](FEATURE-CONTENT-MAP.md#Pbfd0b8c5) | — |
| [hooks/shared/gate.mjs](FEATURE-CONTENT-MAP.md#P2db84dee) | — |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [rules/spec-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P4ccef0f2) | R16；其余按职责保留 |
| [skills/story/scripts/core/flow-check.mjs](FEATURE-CONTENT-MAP.md#P4ec8b22e) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R01,R07,R11,R13,R15,R18；其余按职责保留 |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F5.4 返修与错误恢复

- **M12**：摘录见「F2 面向人的Story」节；定义见 01-归属判定与整体审查.md。
- **M32**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | R03,R04；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |
## F5.5 独立审查与Framework闭环

- **M33**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/coding/post_check.mjs](FEATURE-CONTENT-MAP.md#P5e70c0fd) | — |
| [hooks/plan/post_check.mjs](FEATURE-CONTENT-MAP.md#P4cf2f673) | — |
| [hooks/review/post_check.mjs](FEATURE-CONTENT-MAP.md#P2cb62240) | — |
| [hooks/shared/pre_verifier.mjs](FEATURE-CONTENT-MAP.md#P17056b41) | — |
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | R02,R09,R20；其余按职责保留 |
| [hooks/shared/verifier-report.mjs](FEATURE-CONTENT-MAP.md#P9e0e1fc3) | — |
| [hooks/spec/post_check.mjs](FEATURE-CONTENT-MAP.md#Pf46b01c8) | R18,R19；其余按职责保留 |
| [hooks/testing/post_check.mjs](FEATURE-CONTENT-MAP.md#P11d3a6c3) | — |
| [hooks/ut/post_check.mjs](FEATURE-CONTENT-MAP.md#P074e60a5) | R06；其余按职责保留 |
| [manifest.yaml](FEATURE-CONTENT-MAP.md#P7a130749) | — |
| [rules/coding-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Pb04de125) | — |
| [rules/plan-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Paafa935f) | — |
| [rules/review-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P8820de89) | — |
| [rules/spec-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P4ccef0f2) | R16；其余按职责保留 |
| [rules/testing-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#Pa3bfe6c6) | — |
| [rules/ut-rules.overlay.yaml](FEATURE-CONTENT-MAP.md#P3bed6c8d) | — |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | — |
| [skills/story/reference/evidence-rules.md](FEATURE-CONTENT-MAP.md#P73dcd951) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | R09；其余按职责保留 |
## F5.6 交付选择与能力披露

- **M33**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/verifier-report.mjs](FEATURE-CONTENT-MAP.md#P9e0e1fc3) | — |
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | R03,R04,R05；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
## F5.7 必要运行证据与诊断

- **M34**：摘录见「F5 推进恢复与交付保障」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/evidence.mjs](FEATURE-CONTENT-MAP.md#Pbfd0b8c5) | — |
| [hooks/shared/gate.mjs](FEATURE-CONTENT-MAP.md#P2db84dee) | — |
| [hooks/shared/reader-review-task.mjs](FEATURE-CONTENT-MAP.md#Pa27ccc8e) | R02,R09,R20；其余按职责保留 |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
## F6 跨仓安装升级

- **M01**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。
- **M35 保留现行目录所有权方案**：demo不覆目标adapters，业务仓覆adapters，知识不改，首次画像只扫描一次。保护：删来源区别会把demo替身装入业务仓；删删除旧文件操作会保留包外残留。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story-adaptation/SKILL.md](FEATURE-CONTENT-MAP.md#P8b8e8eba) | — |
| [skills/story-adaptation/scripts/adapt-scan.mjs](FEATURE-CONTENT-MAP.md#P8c0742fa) | — |
## F6.1 首次接入与画像

- **M35**：摘录见「F6 跨仓安装升级」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story-adaptation/scripts/adapt-scan.mjs](FEATURE-CONTENT-MAP.md#P8c0742fa) | — |
## F6.2 机制升级与文件退出

- **M35**：摘录见「F6 跨仓安装升级」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story-adaptation/scripts/adapt-scan.mjs](FEATURE-CONTENT-MAP.md#P8c0742fa) | — |
## F6.3 业务对接所有权

- **M01**：摘录见「F1 需求取材与范围确定」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story-adaptation/scripts/adapt-scan.mjs](FEATURE-CONTENT-MAP.md#P8c0742fa) | — |
| [skills/story/SKILL.md](FEATURE-CONTENT-MAP.md#P7729a47e) | — |
| [skills/story/scripts/README.md](FEATURE-CONTENT-MAP.md#P597ffdca) | — |
| [skills/story/scripts/adapters/review.js](FEATURE-CONTENT-MAP.md#P09f94671) | — |
| [skills/story/scripts/adapters/story.js](FEATURE-CONTENT-MAP.md#Pc2301217) | — |
| [skills/story/scripts/adapters/token.js](FEATURE-CONTENT-MAP.md#P456ec299) | — |
| [skills/story/templates/inbox-readme.md](FEATURE-CONTENT-MAP.md#P685a03be) | — |
## F6.4 安装结果与配置边界

- **M35**：摘录见「F6 跨仓安装升级」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [manifest.yaml](FEATURE-CONTENT-MAP.md#P7a130749) | — |
| [skills/story-adaptation/scripts/adapt-scan.mjs](FEATURE-CONTENT-MAP.md#P8c0742fa) | — |
## F7 共同支撑（不新增用户功能）

- **M22**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M36 保留跨语言与不同语义；同编排解析合并见R09**：稳定配置路径共享；无持久化通用缓存/无跨进程抽象。保护：强合会增加调用开销或改变缺失/坏件处理；不能以共享名义扩大平台。

| 当前承担文件 | 待处理 |
|---|---|
| 组合特性 | 由子特性承担 | 不另建父级实现层 |
## F7.1 配置路径与数据解析

- **M22**：摘录见「F4 知识应用与维护解耦」节；定义见 01-归属判定与整体审查.md。
- **M36**：摘录见「F7 共同支撑（不新增用户功能）」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [hooks/shared/paths.mjs](FEATURE-CONTENT-MAP.md#P7b12f336) | — |
| [hooks/shared/yaml-lite.mjs](FEATURE-CONTENT-MAP.md#P1ed38028) | — |
| [skills/story/contracts/story-chapters.json](FEATURE-CONTENT-MAP.md#Pe4cb5df8) | — |
## F7.2 材料与输出操作支撑

- **M36**：摘录见「F7 共同支撑（不新增用户功能）」节；定义见 01-归属判定与整体审查.md。

| 当前承担文件 | 待处理 |
|---|---|
| [skills/story/scripts/core/import_sources.py](FEATURE-CONTENT-MAP.md#P5a530458) | — |
| [skills/story/scripts/core/materials.py](FEATURE-CONTENT-MAP.md#Pa2f7a68f) | — |
| [skills/story/scripts/core/story-build.mjs](FEATURE-CONTENT-MAP.md#P78aef573) | — |
| [skills/story/scripts/core/story-sources.mjs](FEATURE-CONTENT-MAP.md#P5d48ac7f) | — |
| [skills/story/scripts/core/story_flow.py](FEATURE-CONTENT-MAP.md#Pddb5eac2) | — |

## 全演进范围

[H01–H24](../../../../plan/1.9.1/2026-09-11-Extension功能全集与机制归属/01-归属判定与整体审查.md#整个extension演进的职责替换与退场)覆盖知识账本、作者通道、逐单元系统、材料回执、评审发布、附录、图文、安装器和恢复，不限2.3。新增R22/R23说明知识文档与读取策略中的旧机制残留。

## 替换事实与退场状态

[逐项核对T01–T14](../../../../plan/1.9.1/2026-09-11-Extension功能全集与机制归属/01-归属判定与整体审查.md#新旧机制实际替换与退场核对)：指导区/context_chapters/长stdout已退；旧init、Python子路由、全量图送达未退；审查双源部分退；附录投影早于2.3；审查侧编排解析是2.3新增重复。不能按函数名消失计算用户功能或净收益。

## 明确退出/替换与缺口（长期保留）

- **R01 退出旧成文init入口 / 待实施**：删除cmdInit、COMMANDS中的init、main分发及其专属帮助/错误路由；逐个迁移init_audit及直接init测试。只删此命令的独占代码，不删其他cmd_init/knowledge-use init。 保留：ensureDecisions、scanSources被check读取的缺件检查、story_flow.cmd_init、材料身份和骨架重跑保护。 验证：原材料缺失/损坏、已有decisions不覆盖、sources初筛建立、成文冻结拒绝重建四类行为仍有测试；生产入口不再指向旧init。 **归因**：2.3接管职责后旧入口未退。 **评审补齐**：测试迁移明确含test_story_build.py与test_negative_guards.py；基线init_audit 31处使用、两文件7处直接init调用，按实际调用再核；DECISION_SHAPE指路同步。
- **R02 退出按人数选图 / 待实施**：删除三个以上/两个以内决定图种的门槛；保留关系选图说明。两方调用也可画时序，多方状态也可用状态图。 保留：业务过程完整总览、调用与返回、分支终态、图源对应；不删除整个图形指导。 验证：两方时序、多方流程和对象状态均允许；不按人数强制图种；声明结构仍由脚本落实。 **归因**：沿用旧表达启发式，与最新目标冲突。 **评审补齐**：作者表中状态图统一stateDiagram-v2；structures只支持sequenceDiagram/flowchart/stateDiagram-v2，erDiagram等仅放form与正文，不扩大图种协议。
- **R03 退出固定三次失败资格 / 待实施**：替换整个“失败出口”小节的次数资格：可修错误回责任位置；外部缺件或权限等不可修障碍立即具体报告；错误不收敛回维护者审视。同步引用该资格的“直到触发”措辞。 保留：不随意停工、报错定位、已落盘产物保护；不新增重试计数状态。 验证：不可恢复依赖不被要求空跑三次；正常可修错误仍继续；无固定次数作为结束证明。 **归因**：沿用旧重试资格，与当前维护原则冲突。
- **R04 统一启动与归档授权边界 / 待实施**：授权表明确启动范围止于交付门；归档/Plan根据交付后的用户选择执行。把“两处”限定为取材与范围阶段，不改用户已批准的确认结果。 保留：材料与范围确认、交付后选择、明确归档指令的连续执行；本地单不归档。 验证：只启动Story不会自动上传；用户已选归档无需重复问；本地与远程出口一致。 **归因**：授权表述的旧规则冲突。
- **R05 纠正作者输入在检查之后的倒序 / 待实施**：替换“成文到闭环”的倒置动作链：取作者要求→写产物→登记内检查→Framework harness/verifier/回执；这里只保留接续摘要，详细顺序指现行阶段作业。 保留：现有Framework闭环及check PASS不等于语义通过；不要求模型为了清理再跑阶段。 验证：全入口没有先check再首次取作者要求的指令；阶段内顺序与spec.md一致。 **归因**：作者输入顺序的旧表述冲突。
- **R06 退出UT困难即转device的指令 / 待实施**：替换为先判断障碍原因，保留未验证状态；只有验证方式确实不适配且责任阶段重新确定有效分派时才改verify，不指定必改device。同步ut post_check的修法说明。 保留：must.verify分派、UT/device/both区别、验收原要求、真实未验证披露。 验证：UT环境暂缺不自动改device；both不能降成device；合理重分派仍回Plan和受影响验收。 **归因**：知识验证指令的既有目标偏差，不是2.3接管。
- **R07 退出附录手工行核对的第二套算法 / 待实施**：把现行附录投影的纯计算用于只读check，逐机器区比较实际与当前期望，再删除⑦和⑫b独立取行/集合代码与专属解释。不能直接删除检查，也不能让check修改Story。保留不同错误的简短定位。 保留：appendixProjection/projectAppendix、机器区手改保护、作者解释区、必要五节、单独check和offline结构模式。生成函数正确性由有独立期望的测试验证，不用运行时复制一套生成器自证。 验证：删除行、改第二列值、加入错误行、Spec更新都被只读check识别；作者说明不因措辞变化误判；校验不写盘；与生成共享计算但测试期望独立。 **归因**：早于2.3的投影/行核对收敛，不是2.3引入投影。 **评审补齐**：区分力在不先project的单独check与check --deliver验证；须断言新比对具体结果，不把其他门失败或登记中刚重投影后的相等当证明。投影生成自身正确性仍用独立期望。
- **R08 退出Python重复的写作子路由 / 待实施**：complete分支只返回现有prepare入口；删除spec_stage_step的五分支与仅由它使用的长顺序说明。prepare先补齐knowledge-use不存在时指向现有knowledge-use init及其Spec作者时点，不起Python→Node查询；其它引用SPEC_STAGE_ORDER先简化到指针，不误删授权声明。 保留：取材范围S4状态机、用户授权、首次知识骨架入口、Spec阶段原有顺序、已登记后的Framework闭环。 验证：缺索引、缺初筛、缺知识判断、Spec未形成、缺编排、部分章已写及已登记分别由唯一责任入口指路；同状态Python不再另给矛盾子步骤。 **归因**：2.3明确接管后Python子路由未退。
- **R09 合并作者与审查的编排协议解析 / 待实施**：在现有story-sources纯模块提供文本解析，readTemplate只负责读文件；sourceCatalogue复用flatSections/effectiveDispositions输出再渲染。删除planJson及sourceCatalogue自己的覆盖Map和子节遍历。读坏不能当空编排。 保留：Story/template全文、所有未分配/omit/defer来源目录、审查侧独立语义判断；不引入新模块、新状态或子进程。 验证：相同JSON两侧同判坏件；同单元覆盖、子节及多位置结果一致；不可因仅一侧放宽而绕过；审查材料仍全。 **归因**：2.3新增的重复协议实现。 **评审补齐**：先由renderTemplate起头头部说明structures/children/related/replaced_by的用途和写法，四字段保留但不强制预填；说明用行内代码或text围栏，文件仍只有一个json编排块。
- **R10 退出作者任务包的全量Mermaid搬运 / 待实施**：diagramSection只列图源身份/主题/读取位置，不再carryableBlock复制全部围栏；作业书统一“来源语义与对应保留，画法可合并/改画”，删原样搬运命令。原文仍在材料视图或按需原件里。只删除零消费者的私有helper，diagramsOf等检查共用函数保留。 保留：上游图源对应、完整过程、合图多来源标记、原件可读。不能借此取消用户要求的图承接，也不强制作者自己再造不同图。 验证：作者任务包不内联全部源图；SR/Spec图仍能精确定位、对应漏失能被检查；合图/改画合法。 **归因**：2.3输入视图接管后旧全量送达未退。
- **R11 退出未登记归档副本的特殊放行 / 待实施**：删archiveDir/inArchive及未登记副本字节搜图分支，删专属contract字段；同一图片通过materials登记别名的正常路径继续使用。sameBytes若还有消费者不删，否则随分支退场。 保留：已登记的assets路径、原图身份、正常UX导入/注册、图片存在性与重复使用保护；不迁移或删除任何业务图片文件。 验证：未登记副本不因放在assets就通过；登记过的assets与UX图仍通过；同图身份不变；图文件零删除。 **归因**：历史未登记图片副本旁路与现行路径策略冲突。
- **R12 合并一张图多路径的重复作者任务 / 待实施**：按每个materials图片对象只输出一条任务/命令，选实际可读登记路径为代表，其余路径仅作别名；删未经当前材料schema生产的items/path兼容读取，不删paths合法多值。 保留：每张图的图意、采用/排除理由和可执行命令；空caption仍给补法。 验证：同图两个登记路径只一条处理任务；两张不同图不合并；没有图片与坏清单区分。 **归因**：旧按路径展开与现行按图片身份处理不一致。
- **R13 合并旧来源扫描与当前来源必需性规则 / 待实施**：复用现行来源枚举和required判据，check同一输入要求只检查一次，optional缺失保持提示。删scanSources独占读取/重复告警；offline继续只核能判的结构，不假造业务材料。 保留：必需/可选区别、可选索引缺席合法、解析错误明确；不以新判据缩减测试需求。 验证：同一来源在准备与登记同判必需性；可选不误拦；最小测试使用局部/明确offline路径；坏必需材料不能因夹具而放宽。 **归因**：旧来源扫描与新准备/装配判据未统一。
- **R14 退出段长/项数与绝对零重复的表达配额 / 待实施**：删固定字数/项数触发以及绝对一次的禁止语；并入已有关系选形式与第四步互补判断，不新增另一段方法。 保留：完整句子、可读停顿、避免整段复述、事实完整、必要重现。 验证：有必要的长解释和验收重复条件不因数字/重复字面被要求删掉；堆散文与整段复制仍由效果审查发现。 **归因**：沿用旧表达配额，与自适应目标冲突。
- **R15 退出材料清单的一段散文配额 / 待实施**：删listOnly分支内按段数报错及合同对应配额，保留清单身份/链接/格式。正文是否塞错位置由已有语义审查依据内容判，不另加字数门。 保留：附录必要五节、原材料集合与坏链接、非来源混入检查；不取消机器投影保护。 验证：两段必要来源说明不被计数误伤；漏材料、错链、把非原始文件列成来源仍被拦；业务叙述倾倒有语义审查。 **归因**：历史附录段数代理的替换，不是2.3新旧函数交接。
- **R16 退出数值字面匹配等于出处真假的裁决 / 待实施**：保留出处类型与引用位置的结构检查；退出NUMERIC_RE/UNIT_ALIASES词面命中充当真实性通过/阻断的分支，实际来源一致性并入已有Spec语义检查。不新增逐数值台账。 保留：无依据阈值不能当已确认承诺，来源可定位；现行安全/规约阈值不能因清理放松。 验证：单位换算可由真实依据解释；同数字不同含义仍由语义审查报；结构过不标语义过，模型未审不称已核。 **归因**：历史数值词面代理的职责纠正。
- **R17 纠正事实库禁止合法新建的过度表述 / 待实施**：改为“不能作为已存在的能力复用；本轮新建须有需求/设计依据并说明”。不修改目标仓业务事实或批量同步知识。 保留：已核实不存在的事实、用前核查、冲突登记。 验证：虚构已有封装不允许，有依据的新建能力可进入设计。 **归因**：事实库既有过度表述，非2.3替换遗漏。
- **R18 删除指向已退职责的实现注释与指令 / 待实施**：删除或改成现行职责解释，不重新要求按旧规则改实现。与R07/R15同步清理其它同义说明；不扩大成关键词全仓禁令。 保留：必要的边界/失败语义注释，函数本身按其职责另判。 验证：说明不再提不存在参数或要求作者改机器投影，脚本与作者文档口径一致。 **归因**：旧代码/参数退出后失效说明未同步。 **评审补齐**：补齐质量与验收旧章名、requiredShapes的at==='*'分支、DECISION_SHAPE旧init指路，以及R19完成后“合并会放宽”的失效说明；R01/R19当步改其兄弟，05复核。
- **R19 合并验收读取与条目解析，保留阶段策略 / 待实施**：复用readAcceptance与保留所有条目的解析结果；Spec调用者只选criteria并核形状/命中集，UT/testing选择各自集合。解析不按rule覆盖条目；错误/缺失不能变空成功。 保留：Spec桥接要求、普通业务验收无knowledge_rule合法、多规则多条与verify分派。D01的数据丢失必须同时修，不只去重复函数。 验证：Spec不会接受仅boundaries完成桥接；下游已有boundaries不丢；坏YAML/坏rule形态一致报出；同rule多个AC保留。 **归因**：既有验收读取的重复解析收敛，不改变阶段策略。 **评审补齐**：作者样例AC-K1改AC-1（实际按已有编号顺延），保留现有AC/BD数字及G数字形态；从真实任务包样例到UT/testing检查加正例；共享提取的注释同改。
- **R20 退出审查任务书中的第二套语义规则与结果说明 / 待实施**：将该段独有的有效语义要求并入现有overlay一次；任务书删除规则正文和重复输出示例，只给本轮输入、必要的读取说明与规则入口。图片实例数据保留，不删所有图审查。 保留：Story/template全文、章questions数据、图片目录、未采用来源、真实verdict及输出结构校验。R02的数量阈值不搬过去。 验证：每项有效审查问题在唯一规则源可查；任务书只装本次对象；FAIL/WARN仍有明细，PASS证据要求未消失。 **归因**：审查规则接管仅部分退出，旧段仍在。
- **R21 恢复稳定章节目标在编排前的送达 / 待实施**：在现有编排动作中明确读取合同questions/必要结构，或由现有template起头输出给出精确位置；只选择一个送达处，不恢复每章指导区或旧note。覆盖控制对象/存量/在途/恢复，不穷举业务答案。 保留：运行时模板开放性、稳定十章职责、原需求事实；保留已有集中表达方法。 验证：编排前能取得十章读者目标；不同控制对象写清影响，未涉及不造场景；审查不成为首次交付要求的位置。 **归因**：旧指导区/form.note已退但作者输入接替不完整。 **评审补齐**：协议写法在renderTemplate头部，稳定读者目标仍取合同；不可逆影响与开关能力依据在现有指引中保留，不恢复整份旧form.note。
- **D01 / 功能缺口待修复**：两条criteria同为RULE-01，输入AC-1/AC-2，实际Map只剩AC-2（本轮纯函数复现）。 保留一条规约可对应多个验收的完整关系；与R19同步修读取和UT/testing消费者，不能把删掉第二条验收当清理。 同rule两AC、criteria/boundaries同rule、不同verify分派均不静默覆盖；合并读取不放宽Spec策略。
- **D02 / 功能缺口待修复**：renderSkeleton对空patternIds输出patterns: []；本轮调用coverageProblems仍报“patterns一个适用单元都没登记”。 只有在册模式非空才要求进行适用判断；空模式集没有候选判断任务，保持合法空表。不是取消模式功能。 空模式集空表通过；有模式未判断仍提示；有模式但无候选需有依据。
- **D03 / 功能缺口待修复**：两函数分别以unit为Map键set单值，代码会覆盖同单元的第二个候选/选择；知识README明确同单元可命中多个模式。此项为源码证明，未运行完整Plan场景。 候选/选择以unit+pattern或保留列表对应；消费方一起改，保留多模式能力和拒绝依据。 一个单元两候选、选择一项拒绝一项、两项组合、重复同一项均有对应结论。

## 清理后维护方式（待启用）

先问有效功能目的，再比较该功能下全部实现，不以引用、文档承诺或测试存续自动判保留。新实现必须列被接替的旧函数/规则/数据/消费者，并在同次工作中完成接替；未能退出须写出尚缺的具体条件，不用“测试多”作为永久保留理由。

改功能更新FEATURES；改实现更新本表及内容区间和摘要。R落地后记录实际提交并将目标升级为当前，历史分析保留，但不并排维护两套现行职责。被删除的有效行为必须已在目标位置仍可验证；派生视图不算第二份事实真源，模型一次真正得到的输入另计。

这些是维护清单，不注入业务执行者，不新增运行状态或自证字段。持续比较代码/完整字符/实际读取和返修成本；不把清理后的功能完整性检查简化成“所有文件都还有标签”。

- **R22 退出知识模式文档中的旧project_knowledge落点 / 待实施**：仅替换三处project_knowledge/pattern_applications.instance落点说明为现行files/interfaces实体及files.pattern/role，保留模式实例/所有者/角色关系。不得删除模式正文、SDK行为或组合要求，不在目标仓批量同步。 保留：模式候选与选型、实例所有权、多模式交接、已选模式实现篇，现行契约字段。 验证：模式知识→Plan实体→coding角色读取能贯通；作者不被要求再造project_knowledge旁账；模式语义和示例能力不减少。

- **R23 退出冻结后全面禁止读取知识的过度指令 / 待实施**：把全面禁读改为不重新做规约适用/模式选择；实现时按已选模式读取实现篇及必要工程事实。与coding作者现行要求统一，不添加第二份模式决定。 保留：must作为本次义务真源、Plan选型时点、必要实现知识读取、上游错误回责任阶段。 验证：coding可读取已选模式实现篇，不因旧禁止句停止；不能绕过Plan自行重新选型。
