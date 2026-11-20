# 请求 Framework 所有者核实两处公开消费位置

Story Extension 服务于 SimulatedWalletForHmos。我们在分发提交 `f894653134343de4d33dc62d157776352b05f545`（Framework 3.1.0、manifest 源 `fd5adea913cd3a8e1e0a78fb974e320bf5da32e0`）遇到两个独立问题。以下是设计者整理的转交正文和判定依据；外部回复尚未取得。

**一、首次选路前如何交付项目扩展的适用条件？** 该项目的 AR 单必须有本单 Story；普通非 AR 微型、小型开发可以免写。两类请求都从普通开发前门进。安装清单已登记 story；只修改已安装 Skill 的原生 description 并重新安装，检查通过，但根入口只渲染 Skill ID/路径，跳板仍是固定泛称，微型直接修改与小型短蓝图都未得到编号条件。请指出 f894 已支持的、在首次设计或产品写入前必达的实例说明入口，给一份已物化的主作者输入。若确需修复，建议复用 Skill 的同源 description 进入根入口和发现用元数据，不将 AR 规则写进通用 Framework，也不要求人把普通开发改成显式 /story。以普通 AR／非 AR、微／小两组对照验适用条件真实送达。

**二、同一已冻结 request 如何接收合法修订后的来源？** 输入为已准入蓝图与 CU，目标止于实现方案。使用公开 prepare-scope、harness 冻结；原设计 owner 将既有验收改成“余额服务不可用时保留上次成功值并标出更新时间”，通过原生 CU 修订/readiness，阶段 owner 保全旧投影并重新准备当前 Spec/Plan 输入。现象为旧 acceptance/contracts binding stale，receipt 不闭合，转 attended 出生也拒绝旧绑定。补全 f894 要求的 decision 施工／验证映射可恢复 CU 就绪，却没有让冻结请求取得新依据。900c 的缺定义→补齐→中断续作试验已通过，与此处“旧依据原先有效而语义改变”是不同条件。

请给出同一原请求保留原终点、required 义务与用户授权的公开 owner 动作、提案生产/消费入口及返回的当前 binding；若需要经 successor，请说明如何绑定原请求、保留有效成果并从中断恢复。我们会在对应正式 commit/tree 上以真实 harness、receipt、同次请求完成与负例复核。无需开放写冻结文件的接口。仓内复现入口与负例见 [S08](03-批次-原生组合与测试准备/S08-原生恢复组合.md) 与 [S27](05-批次-远端框架同步与Story适配/S27-编号分流与同装配交付补证.md)。
