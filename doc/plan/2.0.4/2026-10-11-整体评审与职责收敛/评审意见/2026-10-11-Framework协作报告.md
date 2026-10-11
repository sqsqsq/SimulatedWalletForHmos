# Framework 协作报告：设计准备正常调用与既有事项

> 本文保留调查/评审证据；现行执行规则以[实施总览及四份步骤](../00-实施总览.md)为准，不与方案正文并行下发。

2026-10-11，维护设计者，供用户反馈上游；本轮未向上游发送。基线 Framework 3.1.0，source_commit `074a4c3c4a0591c8ed2162e2a0d048a1fdec081f`。证据见[架构调查A4](../调查/01-架构与原生协作调查.md)。

## U01：功能存在，公开调用方法需完整交付

现有 `/component-design` SKILL 第98–101行指向 `change-unit-design-preparation.ts`，列 `evaluateDesignPreparationEntry`、`acceptChangeUnitDecomposition`、`deriveDesignPreparationReadiness`；候选信封在 `change-unit-provider-boundary.ts` 为 `{providerId, artifact}`。不是“Framework没有CU准备功能”。

实际正常场景：用户在Story交付门选择实现方案（到Plan）。已有admitted蓝图、0 CU，主模型需首次分解并经原生consumer接受。当前入口没有在动作前交齐调用参数、候选信封与完整运行方法，模型到源码里找CLI、自造provider/candidate封装，并在framework/harness写p2-accept.ts和p2-accept2.ts。证据：本轮车钥匙runlog第6710、6815、6837–6852、6961、7598行，以及events对应12:07–12:10调用。

consumer拒绝缺闭包候选是正确行为。本报告不请求放松准入、自动补所有闭包引用或新增Extension写入器；请求修正常入口的信息交付。

## 最小交付合同

在现有component-design/change-unit-progression入口交一份完整设计准备方法：

1. 输入：项目根、指定蓝图、当前请求终点、候选文件；候选信封和provider身份来自哪、artifact使用哪个原生schema及中性有效示例。
2. 执行：明确如何在实际宿主运行这三个公共函数，给可复制且参数完整的正常调用方法。若现有运行器可承载则复用；若提供薄CLI，只调用现有consumer/readiness，不另建registry/调度/完成状态。
3. 输出：canonical CU列表、readiness、问题及下一原生动作；区分失败未写、成功写入、已有CU复用。反馈给主执行者，不靠读内部实现拼返回语义。
4. 恢复：整批拒绝无写入、重复接受已存在CU、引用升版、真实共同设计不足分别回原生负责方；不得让作者手改canonical回执或为过gate胡乱补引用。
5. 目录：候选/必要调用临时件位于项目允许的工作目录，Framework发布件保持只读。模块加载与工作目录在方法中明确，不能依赖碰巧在harness下新建脚本才运行。

验收：中性薄蓝图→首次1 CU→readiness；多个合理CU；错误候选整批不写；既有CU复用；stale引用沿原生调和。随后本仓正常CLI观察消费模型能依据入口调用，未临时修改Framework，未从checker逆推业务设计。

上游选择完整公共函数调用示例或正式薄入口属于上游实现，但上述输入/执行/失败/完成合同是固定验收，不留给Extension实施者自行设计另一条路径。本仓等待实际交付后记录版本与校验，不把请求当已发布接口。

## 影响与推进边界

可先完成本仓P1–P3离线修正。U01未就绪时不签“CU正常交接已解决/Plan正常链已通过”；已有公共函数可用于只读理解或获授权验证，不能把本轮临时桥接成功当正式能力验收。是否可继续部分真实业务测试由具体终点与环境前置判断，不笼统说Framework整体阻塞。

阶段报告自定义路径、Extension结构检查、Story原件被改写都是本仓责任，不转嫁上游。输入超限先核宿主/服务，不认成Framework蓝图缺陷。FW-04/05及术语模式仍沿既有报告的原责任与证据状态，当前调查未补足证据不重新声称已修或必须阻塞。
