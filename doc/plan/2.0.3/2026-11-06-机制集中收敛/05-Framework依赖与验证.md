# Framework依赖、可独立推进与关闭证据

此页是本Plan的依赖真源，不把独立反馈文档当上游已经修好。对象ff111909/source879f1e8b；本地dsh只声明interactive。当前未向Framework作者发送消息，用户可转交原独立反馈及本页Q2补证。

| 事项 | 已核事实/性质 | 阻塞范围 | 关闭结果及责任 |
|---|---|---|---|
| F1 gap闭包 | 原生deriveClosure收gap，complete refs/schema不支持gap；原函数窄反例失败、删关联对照通过，是真实契约不一致 | B02含合法gap的CU闭合与整版phase:plan证据；不阻A | Framework修同一引用/闭包语义并发布；设计者核正式组合既保真实关联又保当前未决阻塞 |
| F2人读渲染 | guide优先、大参考、部分fallback叠加有真实阅读成本；不是全部写作缺失的原因 | 非硬前置；若最终阅读效果仍不达，本版效果不能签通过 | Framework可改原生展示；本仓作者/审查仍负自身内容质量，不另造renderer |
| Q1设计authority与来源 | 只承载选中typed的目标要求authoritative；不要求所有ref或自指。Extension材料support解释仍有接缝 | 涉及改变authority/provenance表达及其消费的B02产品修正 | Framework确认合法设计来源/外部事实边界；设计者给出确定合同、现消费者改动和预算后才实施，不让执行者猜 |
| Q2独立Spec→Plan正式证据 | prepare-blueprint-design只导阶段输入；原生无run阶段可闭环，但当前Case消费者要求冻结范围。新CU两个独立阶段的范围/修订/证据链尚未完整闭合 | B01路线启用及C02 car目标达成；不阻A/B01回写核验/C01准备 | 设计者与Framework所有者确定官方请求范围/冻结/阶段证据路径，实际生产→既有observer取得闭合；保持原phase:plan要求，不改为文件存在 |

## Q2追加核查：为什么现在不能写成已解决

1. ff111909 `docs/operations/project-entry.md:32–34`：新完整交付统一run；独立spec/plan可到本职责，不能签Feature完成。`skills/feature/spec/SKILL.md:7`和plan独立准备提供阶段导出命令。
2. `prepare-blueprint-design.ts::prepareBlueprintDesign`只调用`materializeBlueprintSkillInputs(..., phase)`，不建立范围候选、不冻结范围。
3. `test/scripts/observe_target.mjs`通过`goal-run-creation.ts::resolveEffectiveScopeSource`只读run或feature冻结，`end_target.py::observe`先要求每CU scope=frozen；summary存在不替代范围。
4. 原生`ensureFeatureExecutionScopeFrozen`在workflow1.2没有候选时阻断，要求先prepare-scope。无Goal阶段的`finalizePhaseClosure`可产closed summary/阶段证据，但它并不消除范围前置。
5. 同一新CU的Spec→Plan如何在无run请求范围下续行还涉及义务链、`applyFeatureScopeRevisionsThenMaybeComplete`不对无run应用修订，以及单阶段设计修订范围；不能仅因参数接受requested-phases spec,plan就宣称正常组合成立。`--request-file --report-dir`与`--feature`互斥，也不能直接替换CU消费者。

因此撤回调查中“无须prepare-scope即可直接达到phase:plan”的初步判断。当前正式设计是：**不用不支持的路线、不造旁路，待官方范围和阶段证据合同闭合后启用；未关闭时如实阻塞对应后段。** 这不是让执行者补设计，也不是索要新增dsh goal/headless能力。设计者收到上游答复后把精确命令顺序、输入输出、合法回修及失败恢复写回B01，再集中复核，预算变化同时处理。现有终点和本版范围不降低。

## 组合验证与上游接入

- 发布件固定release/source和受控patch；修改`test/config/framework-under-test.json`及匹配patch只能在获准B02工作中，测试装一次性template，不写demo。
- F1窄反例可定位缺陷；验收须通过原生完整生产入口得到真实蓝图/CU，保gap关联，原生补全/校验/typed消费者都成立。无影响的其他引用种类回归保持，不扩大极端矩阵。
- Q1采用同一合法设计对象，分别核原料来源和设计authority，Extension索引及独审取得真实证据；坏引用仍拒，不能注释/迁址/虚导入求绿。
- Q2从新CU官方入口起步，由真实生产者给范围、harness与独审结果，经observer/end_target判phase:plan；不在夹具先补关键冻结或完成文件。正式终点需每个实际CU通过，不能拿一个单位或一份Plan代整单。
- pin/patch/装配变化时assembly；受影响定向检查后批末handback。新Framework结果不能移签旧CLI，最终C02必须固定一个组合；不混几个版本局部通过。
- 暂无新发布件/答复时，A及C01可在授权后独立推进，上游受阻项保留明确未完成，不额外建维护平台。

## 本轮新增事实与依赖收缩

十二会话证明的材料角色误判、候选反写转写、Story报告重负担、派审预置旧结论及长行截断，A批从Extension现责任处处理，不升级为Framework全局前置。蓝图正文/参考的边界在固定ff111909 renderer已有reference标记，06沿原物做只读定位；F2不是新硬依赖。原生八问/质询shape及候选资格不由Extension改写。

frontier_fingerprint只校非空是已知能力边界，尚不足证明Framework算法违约，本轮不新增修复依赖或本地指纹协议。父机器登记必须忠实原答，修后对象是否需复核沿原生合同；不把缺少“更强校验器”当虚签许可。F1/Q1/Q2的原结果、受阻范围与正式组合关闭条件保持。
