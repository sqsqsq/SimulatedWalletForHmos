# 步骤03：update与本地恢复

本步保留真实比较、源头修订、局部撤回与人工内容保护，切换为同根版本和原生当前处置。当前仅方案，未执行update或恢复。

## 1. 输入和状态合同

必读[批次方案](00-批次方案.md)、[共享接口](../参考/01-目标接口与状态.md)、步骤01/02及主Spec R1/R5—R10、AC9—AC11。输入为本轮真实fetch/本地导入回执、`materials.json`来源版本、有效人答/外部意见、当前蓝图的真实scope与支撑来源引用、独立必读人答身份、实际CU原生阶段报告、Story/Review与其当前审查事实、上一比较基线和进行中update记录。

沿现有`update-inputs`→`update-prepare`→修订→`update-status`/`update-feedback`→`update-close`；`unchanged`表示本轮比较确无变化，`resume`表示已有未完工作待续，`incomplete`表示不可比较范围，`changed`表示有变化。不得以“上一轮closed”或历史PASS推当前无待办。历史closed可提供字节比较基线，但当前处置必须读取当前对象、原生新鲜度、必修和待核；两种用途分开。

本地恢复只撤回Extension本轮确权的可改/可重生工作件及其自有流程字段。原件和来源版本、会议原话、人答、Review人工区、原生蓝图提交/CU/阶段完成与外部系统不由本地撤回回滚；已原生完成后需要更正仍走原生更新，不以恢复旧文件伪装没有发生。

## 2. 工程动作与正常顺序

1. `scripts/core/flow/update.py`的`cmd_update_inputs`、`_collect`、`_sources`、`_imported_since`、`_fetched_this_round`先汇集实际输入，再由`cmd_update_prepare`建立轮次和可比较before。导入新来源时已版本化到`sources/<材料名版本>/`，本步只读`materials.json`及本轮回执判断新增/替换，不再调用`frozen.current_version`或要求重跑`complete`补登记。新材料到达不自动否定有效人答，是否采用由模型按当前事实决定并回写原生采用版本。
2. 模型先判影响位置：原件/会议解释变化修其真实来源和纠偏；共同业务/接口/状态/知识义务变化修蓝图及原生decision；仅叙事变化修Story；真实裁决变化更新`decisions.json`并保人工区；CU按原生准备/更新取得当前Spec/Plan投影，不手改投影补共同决定。普通文件/模块预测调整不视为授权扩大，真实业务边界或明确限制变化才取得对应授权。
3. `update.py`的`_unit_facts`、`_phase_facts`、`stale_units`、`cmd_update_status`、`cmd_update_feedback`与`phase_facts.py`经`flow/native.py`和`hooks/shared/framework-access.mjs`取同根实际CU/阶段事实。删除`design_binding.blueprint_id`定位及`closure_status == closed && fresh`单项代签。上游`ff111909`的`framework/harness/scripts/utils/check-disposition.ts`负责当前失败去向，`phase-closure-finalizer.ts`负责真实闭环；Extension消费原生当前处置与完成/发布资格，不复制处置表、不自行改FAIL为WARN。
4. 来源、设计或正文变化后调用步骤01当前输入/写作/定稿，步骤02按对象变化确定必要复核。A04已退出`registered_input_stale`，本步不恢复该旧函数。现有登记/来源当前性读者按参考01及A05核实际采用＋必读人答联合身份、当前原生依据与登记对象；不以普通材料digest遮人答变化，也不重复实现A05已有来源读取。旧冻结快照/五段稿算法保持退出。真实旧FAIL、当前待核与普通完成资格分别显示，不为重新取报告而虚构内容返修。
5. `cmd_update_close`确认本轮真实比较范围、真源修订、Story/Review登记、当前必修处置及已授权终点。可保历史收口记录但同时列出未执行验证、仍需原生处理的CU及发布限制；不能因本轮closed结束实际待续工作。`flow/routing.py`的`next_step`、`story-build check --deliver`、`flow/publish.py`和usage/stats消费者取当前处置，不从closed产生额外批准或伪完成；已有授权范围内直接续行，未授权阶段不创建。

所有核心路径前缀为`extensions/skills/story/`；Framework路径仅指上游合同来源，不授权改vendored代码。原生没有可读取的当前事实时按共享接口保读取失败/依赖缺口，不能用历史报告或自行重建聚合规则兜底。

## 3. 恢复实现与保护范围

`contracts/story-chapters.json`的`update_files`继续是四类归属真源，`update.py`的`owner`/`_owned`/`_mirror`/`record_owned_after`/`cmd_update_restore`共用；更新路径后把`sources/**`、原件版本、备份、会议原话、人答及原生蓝图/CU/阶段产物列为受保护。未登记路径仍默认protected。流程契约仅恢复明确归Extension且属于本轮的字段，不整文件回退其他人的状态。

保before/after/current三方指纹：current=before不动；current=本轮确权after才可退before或删本轮新建工作件；其他改动留当前并报冲突。恢复前将当前差异和Review原件保存到`sources/backups/`下本轮可定位备份，失败即停止后续写入；Review人工意见与有效人答始终保留。原生已完成对象不放进可撤回集合，恢复后按当前原生事实重算需要同步的Story/Review及审查状态，不恢复旧登记来制造一致。`restore_conflicted`继续保轮次可续，不对冲突自动选旧版。

这替换的是旧根/旧冻结输入/旧closed判完成，不替换三方比较和所有权保护；只对本版新初始化的需求做多轮更新/恢复；1.x与旧试验2.x现场不接续、不转换，旧记录不回填。

## 4. 验证、完成和预算

后续定向调整`test/tests/test_story_update.py`、`test_update_checkpoints.py`、`test_update_dispatch.py`：从真实导入/版本记录开始验证四种比较结果；会议合法更正或材料v2确被设计采用时，下游按实际影响同步；仅取得v2不得自动替换采用v1；无变化不重复成文计时；历史closed/PASS与当前必修、待核、新鲜度失效并存仍能给正确下一步；原授权续行不重问、未授权Coding不创建。构造普通预测位置调整与真实范围变化对照，核处置沿原生返回消费，不在测试预置一个Extension完成结论。

恢复定向验证人工区、来源原字节与原生已完成CU均不回滚；after之后的外部编辑保留冲突，恢复前备份失败不继续，确权工作件可恢复。源头修正→Story更新→必要复核→再次交付组合在本批末验证。

独立语义核变化归因和共同决定是否回真源、知识义务是否随真实实体传递、未决/未知是否被误改为已定。真实update与恢复需后续正常DSH按既有Case终点取证；离线三方恢复不证明业务模型理解变化，旧2.0结果不移签。

完成须比较、源头修正、原生当前性、正文/登记/交付、局部恢复所有直接消费者闭合；退出`frozen`/`complete`/`design_binding`及旧处置专用回归，保合法历史字节基线。预计G330/X420，按[共享预算](../参考/03-预算与计量.md)和AGENTS§5计量，交回并提交后前置成立继续04。

本次C00已补正的聚合职责由本步复用：各CU Feature查询不自动带环境run；单位级完成/发布/披露/unknown独立可见，不按阶段列表过滤丢失，不把发布限制变成普通完成失败或update收口前置。详见参考01§6、C00§5。
