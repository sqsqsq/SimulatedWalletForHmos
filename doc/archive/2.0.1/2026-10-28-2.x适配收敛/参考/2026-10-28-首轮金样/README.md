# 数字车钥匙分享：2.x完整候选金样

2026-10-28。**完整初段目标包，止于Plan，待用户审定；不是本次CLI生成结果，也尚未晋升test/golden正本。**本包以1.9.9已审定的车钥匙情景为基础，保业务效果、公开模拟前提及未决，使用一个物理需求目录。制作未修改Extension、Framework、测试代码、现有金样或运行现场，未启动模型/设备/测试套件。

## 先看这五份完整稿

| 阅读目的 | 完整稿 |
|---|---|
| 作为产品/测试评审者理解业务 | [Story](doc/features/ISSUE-206/AR/story.md) |
| 看哪些已定、哪些仍需决定 | [Review](doc/features/ISSUE-206/AR/review.md) |
| 看共同设计与知识如何改变方案 | [蓝图人读目标稿](doc/features/ISSUE-206/blueprint/blueprint.target.md) |
| 看本CU要满足的行为和验收 | [CU Spec](doc/features/ISSUE-206/wallet-key-sharing/spec/spec.md) |
| 看实体、方法、存储、模式、统计及验证怎样落实 | [CU Plan](doc/features/ISSUE-206/wallet-key-sharing/plan/plan.md) |

业务读者先读Story及需要裁决的Review，不必先读另外三份。开发负责人读蓝图，再按任务查看CU；不是要求每个读者从头读完五份。

这些是全稿，不是先前的五段说明。Story保完整入口/分享/接受/管理/六态/续办/未知恢复/隐私/统计与验收，CU Spec保F1–F9、46个验收条件及31个边界场景，Plan保完整实现责任。标题与图文组织可审，不要求照字面固定为产品模板。

## 有效输入与原有未决

[输入与前提](doc/features/ISSUE-206/source-inputs.md)是本候选的口径入口。原始产品/UX DOCX、系统设计、本地登记、阅读转写和图资源均随单目录提供；原件字节不改。

本候选采用旧审定情景：设备卡片最长48小时收回、车云受理成功撤销后车辆立即拒绝；卡包范围、草稿续办/清理、模拟联调及三个流程统计按旧金样。API12/Asset/1024字节和模拟创建恢复属于公开建设前提，未因此变成真实服务或设备已验证。

D2再转第三人、D5极端断网强制下线、D8待接受撤回均保未决；人工填写位不代填。自定义日期控件材料缺口保留。当前所有“已定”来自既有情景依据，不伪造本次新运行人签。

## 目标稿与原生输出请分开看

- [蓝图目标稿](doc/features/ISSUE-206/blueprint/blueprint.target.md)是维护者编写的目标呈现，依据canonical候选组织；没有伪造原生publication签名。
- [原生渲染对照稿](doc/features/ISSUE-206/blueprint/component-blueprint.review.md)是固定Framework N24ea6aeb/source226fee6f的真实渲染函数对同一canonical生成的原样输出。没有手改其内容；[生成记录](evidence/native-render/generation.json)保源码与字节身份。
- [AR/design-review.md](doc/features/ISSUE-206/AR/design-review.md)是这份原生稿的逐字节参考副本，用于显示当前交付附件关系，不是另一个作者或决定真源。
- 当前renderer仍会把知识判断展开为空取舍，并附全量技术参考。它的部分来源链接使用工程相对路径，普通Markdown查看器从当前文件目录解析时不能直接打开；原文件都在包内，可从输入与前提页访问。目标呈现需要原生/扩展适配才能正常产出；这份对照用于反查差距，不把手工目标稿说成现实现已支持。
- 原生对照稿未带已接受CU，故不能从其“暂无CU/用例”等措辞断言本候选包没有CU内容。蓝图验收节点的来源权威仍为候选推导，原生会显示相关诊断；未为消除诊断把它强改成已获批准。它与完整目标稿/候选验收分开披露。

## 机器与来源配套

- [蓝图canonical候选](doc/features/ISSUE-206/blueprint/component-blueprint.yaml)：同需求ID ISSUE-206，wallet-main组件候选。
- [CU候选](doc/features/ISSUE-206/wallet-key-sharing/change-unit.candidate.yaml)：一个wallet-key-sharing单位承接本例钱包端；尚未调用原生接受。
- [契约](doc/features/ISSUE-206/wallet-key-sharing/contracts.yaml)、[验收](doc/features/ISSUE-206/wallet-key-sharing/acceptance.yaml)、[用例](doc/features/ISSUE-206/wallet-key-sharing/use-cases.yaml)：当前候选的设计内容与来源对应；planned引用是拟建实现/验证位置，不是代码已经存在或测试已运行。
- [四屏参考图](doc/features/ISSUE-206/ux-reference/)、[三份Mermaid原图源](doc/features/ISSUE-206/AR/story-src/figures/)、[撤销责任综合阅读图](doc/features/ISSUE-206/AR/figures/car-key-revocation-responsibility.svg)：沿用旧审定字节；参考线框与文字结合阅读，不作为像素或新设备视觉验收。
- doc/extensions下只复制实际知识原文及其清单作依据，不是安装好的Extension。framework.config.json只服务候选路径描述，不代表完整消费工程或可直接起跑的项目。

单目录实物已经形成；固定N在真正枚举时与根ux-reference的兼容仍有已知接口依赖，本包没有调用该链、更没有修改N绕过。文件能放一起不等于原生运行接入已经成立。

## 已做与未做

已做：完整人读目标制作、原件/图资源保全、机器候选构造与真实字节摘要绑定、原生文档渲染、蓝图/CU候选静态schema校核、来源/链接/引用核对，以及独立维护审稿与发现修正。详情见[核对与反查](核对与反查.md)。

未做：Framework完整准入/正式CU接受、阶段闭环、正式产品独审、DSH/真实云端/设备运行、用户审定与金样晋升。用例有完整业务场景，但不是已执行测试，部分可执行参数序列需真实实施对象细化。静态schema无问题仅证明其形状，不证明语义、施工就绪或产物生成能力。

下一步请按五份主稿审目标效果，再用反查清单修订适配设计和实现范围；不直接以这份人工候选替代正常入口验证。本轮不覆盖旧金样，不自动扩大为update金样或第二Case。
