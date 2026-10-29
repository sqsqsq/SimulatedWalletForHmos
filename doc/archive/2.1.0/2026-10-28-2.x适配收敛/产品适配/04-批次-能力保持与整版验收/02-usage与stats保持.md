# 步骤02：usage与stats保持

## 输入与责任

读取主Spec R9、标准I1—I8全部子条件、前三批原生状态和update收尾合同、步骤01安装记录保护结果。代码输入为extensions/skills/story/contracts/usage.json、scripts/core/usage.py及它读取的phase_facts/命令观察者，story各实际入口、story-stats/SKILL.md、scripts/stats.py、templates/report.md，以及运行回流的usage快照消费者。R01/R02已技术关闭，本步保持其结果，不另立计时工程。

usage仍是记录真源，stats只读doc/usage.json与Git。沿现有合同保八步骤story、story update、spec、plan、coding、review、ut、testing，身份件.usage-id只作身份，不把同根/蓝图登记当实际开始。新身份映射按原生blueprint/CU及需求共同工作归属，不通过扫描目录猜身份。

## 工程动作和直接消费者

1. 将feature_dir、原生阶段事实读取、入口begin/成功收尾观察改到前批同根和原生CU身份。共同需求工作只记一次，CU阶段按自身身份计量；读取前批共享来源版本，不把旧独立绑定恢复成统计索引。
2. 保现有usage接口：实际工作开始前经--begin与--step记录；原生阶段真实成功后经--finalize/既有观察链收尾。具体命令形式以真实argparse和调用入口为准，不把内部record(action=begin)写成不存在的CLI子命令。Story真实story_written_at承担完成，不由文件存在推断；.usage-id生成不开始Story计时。
3. 对独立Spec/Plan分别接其真实入口和成功事件；attended run按原生next/report实际活动接续，不为记录强建完整run、不启动Coding、不新增第九收尾步骤。普通完成、独审语义通过与发布readiness分别记录事实；历史closed/PASS/回执不能补本轮完成。
4. 保多轮累计、幂等refresh、未知起点不造、旧完成不结束新轮、失败/等待不伪记成功；模型自报身份有依据，未知不猜，Framework/Extension版本随最后实际活动刷新。跨阶段当前有效结果可复用，不能抹原轮消耗。
5. 保usage合同、锁、原子落库、坏数据/冲突/中断保护和失败降级。安装ensure先检查合法性，已有合法账不重写，状态坏了不当空。未知历史保持错误和恢复提示，不自动迁移或补账。
6. stats collect继续从usage/Git产生逐需求事实至临时输出，模型按模板写报告；不读取业务目录、不改usage、不补未知数字。Git混合提交和坏历史按真实归属/错误处理，不能假空集。若新身份影响Git路径关联，修改其真实归属解析并保混合提交语义，不增加需求扫描器或影子计时层。

直接消费者包含实际八步骤作者入口/命令后观察者、Story/update完成记录、CU后续阶段、安装ensure、stats事实与报告、suite检查点及finalize的原字节usage快照、维护交回。检查既有消费者是否仍读旧绑定/waiver/frozen状态，改接真实事件或退出，不保无生产者字段兜底。

## 定向验证与预期

通过verify.py affected选择实际usage、phase facts、stats、观察及回流相关测试。正常链验证真实begin→工作→原生成功→记录→stats，不在测试中预写完成字段代生产者。独立验证：仅初始化身份没有可核Story起点；多轮及重复refresh不重计；旧完成后新begin只有新成功可结束；同一共同设计不因多个CU重复计时；CU步骤归属正确；独立Spec/Plan无需完整run即可记录；未完成、checker异常和未审不会伪成功。

保坏数据/写冲突前后原账字节，未知起点、身份和版本如实输出。用usage与Git独立算例核stats逐需求/混合提交事实；移走业务目录后仍可报告且原账不变。核suite initial/update/final快照与原账原字节一致，缺失明确missing。必要性是记录存在只能证明落库，必须证明真实生产事件、归属和统计消费未改变。

真实DSH中的起止与原生next/report对照留步骤04；无该证据时I项相应行为层未覆盖。Coding/设备等未获准不跑，确定性覆盖保留不代真实完成。

## 完成、交回与预算

交回列I1—I8各子条件的生产者、真实事件、账目、stats/Git消费、验证对象、未覆盖及失败保护；保原始usage和快照证据，不手工修账。必要验证后独立提交。D02 G80/X80，预计净零；只重接身份与事件、退出旧消费者，不加平台。峰值/总量引用总预算，产品返修累计D02，R权限按AGENTS §5。
