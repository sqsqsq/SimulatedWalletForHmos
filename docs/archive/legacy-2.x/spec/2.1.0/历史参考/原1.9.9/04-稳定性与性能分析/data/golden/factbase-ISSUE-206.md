# 事实基线 · ISSUE-206（数字车钥匙分享，钱包端）金样写作基线

> **性质**：本文件与 `ISSUE-206/{spec,story,review,plan}.md` 四份金样是 1.9.9 B5 分析的**写作产物**，不是任何一次真实运行的原生产物；金样头部均带同款标注块。
> **写作日期**：2026-09-29。
> **判据**：C1 现行合同/模板/写作页硬性要求；C2 结构完整性（金样无门禁运行，以现行模板逐章核对代替）；C3 信息完整可核查、无编造（数值/接口/模块名逐项有来源，见 §3、§6、§7）；C4 表达质量（辅助）。判据框架沿用 [analysis-b5-spec-draft.md](../analysis-b5-spec-draft.md) §1 与 §5-D。
> **材料代指**：「回灌版」= `doc/features/ISSUE-206/`（2026-09-28 update 对应的现行基线）；快照用短名（如 214925 = `doc/features/archive/Story-Features-20260928-214925/`）。逐章最佳写法依据 [analysis-b5-issue206.md](../analysis-b5-issue206.md)（下称「spec/story/review 档案」）与 [analysis-b5-plan.md](../analysis-b5-plan.md)（下称「plan 档案」）。
> **禁用素材**：Story-Features-20260829-221817 与 Story-Features-20260830-104850 的 ISSUE-206 目录实为「交通卡自动充值」错装产物（spec/story/review 档案 §2 口径澄清），全程未使用。
> **消费方式**：四份金样与事实的冲突以本文件为准；本文件与现行规则真源（`extensions/` 模板/合同、回灌版上游材料 RR/SR）的冲突以规则真源为准。

## 1. 业务口径与范围

### 1.1 一句话口径

车主在手机钱包把数字车钥匙分享给家人或联系人：端侧（钱包）承担分享的设置、创建、状态展示与撤销，车云维护分享关系，车厂云签发凭据并裁决钥匙可用性，消息推送送达通知；未接真实后端前以本地模拟数据承载（议题 D4）。

### 1.2 Scope（金样口径，含对回灌版退步项的裁定）

| 字段 | 金样取值 | 依据 |
|---|---|---|
| in_scope | `WalletMain`、`Phone` | 后期五份多数派自洽口径（004631/125732/233718/191025/214925，spec 档案 §3.2）；Phone 限定仅「为新增页面在宿主 navDestinationMap 注册名字分支」。工程事实：`demo/01-Product/Phone/src/main/ets/pages/index.ets:15-21` 的 `navDestinationMap` 是硬编码 if/else 分支，新增页面必须加分支——注册映射即修改 Phone，故 Phone 必须在 in（**修正回灌版退步项：回灌版 out_of_scope 含 Phone 却自述「宿主壳仅新增 NavDestination 映射」，自相矛盾**，spec 档案 §7-B.1） |
| out_of_scope | `AccountManager`、`CommFunc`、`CommUI` | 三模块只读复用既有导出（登录态、MaskUtil/Logger/WalletHAManager、SectionCard/ActionListItem/showToast/Maison* 组件），不新增对外接口；rationale 写明「只读用既有导出，不新增跨模块接口，若需要属 scope 扩展须停下提议」（回灌版 plan rationale 同型句，plan 档案 §3.1） |
| 工程惯例事实（rationale 引用） | 「三处登记：页面文件导出 builder → WalletMain index.ets 导出 → Phone 宿主 navDestinationMap 加路由分支」 | 125732 Scope rationale（全池最扎实的 Phone 取舍依据，spec 档案 §3.2）；已核 `Phone/index.ets` 为硬编码分支、`WalletMain/src/main/ets/index.ets` 导出页面 builder |
| plan 继承 | plan 直接继承 in=[WalletMain, Phone]，`expansions_with_user_approval: []` | spec 已把 Phone（限路由注册）收进范围，plan 无需再扩展；回灌版 plan 的 Phone 扩展实例随 Scope 口径修正而不再需要（口径裁定见上） |

不做（显式）：

- 不做「改权限」——换权限就撤销这条重新分享（上游约束：产品需求稿产品规则表）。
- 转赠（被分享人再转第三人）与长期不联网的强制下线：本期不结论，方案与验收均不包含、不预留入口（上游约束：产品需求稿「还没定的两件事」；议题 D9 登记）。
- 被分享人接受侧**并入本单一起交付**，不另立单据：接受侧界面说明材料已入材料目录，需求人已裁决「接受那一侧也一起做，别另立单」（0901 review 2.1.1 人裁原话；议题 D8 已定；**0914 起多数快照按 PRD 旧句误读为「材料未到」，金样按 0901 口径与材料实况取「建页」一侧**，spec 档案 §7-E.2）。

### 1.3 范围两条链

- 车主发起与管理：入口、设置页（对象/权限/有效期）、创建（幂等）、草稿续办、管理页（列表/剩余可分享数/单条撤销）、配额判定、开关、隐私脱敏、事件上报。
- 被分享人接受与持有：接受页（车辆信息卡 + 添加到钱包，无拒绝按钮）、卡片入卡包、卡片详情（权限/有效期）、六态展示。

## 2. 最终功能清单（F 编号集，spec/story/plan 同号同义）

来源：回灌版 spec §3（F1–F14）为基线；行文按 spec 档案 §3.4 融合 004631 集中声明式 mock 注与 191025/214925 行覆盖。优先级 P0：F1、F2、F3、F5、F7、F8、F9、F10、F12（9 项）；P1：F4、F6、F11、F13、F14（5 项）。

| 编号 | 名称 | 优先级 | 描述要点 | 关联场景 |
|---|---|---|---|---|
| F1 | 分享入口 | P0 | 车钥匙卡片上「分享」入口；未登录或没有车钥匙的用户看不到入口；开关关闭后不可发起新分享 | S1 |
| F2 | 分享设置页 | P0 | 三段式：给谁（通讯录/输入账号）、权限档位、有效期（7/30 天/自定义≤180 天）；三项选齐「发出」才可点击；进入时查配额 | S1 |
| F3 | 权限随对象定 | P0 | 选定对象后按权限档位接口返回呈现；换对象重查；已选档位不可用请车主重选，不静默降级 | S1 |
| F4 | 配额校验 | P1 | 生效+待接受合计满 5 后发起入口置灰并显示可读原因（原因取配额接口返回，不端侧编造） | S1, S6 |
| F5 | 创建分享 | P0 | 带幂等标识创建；成功后对方收到待接受钥匙；车厂云签发失败提示可重试、车云回滚不留半生效 | S1 |
| F6 | 草稿续办 | P1 | 发起途中退出/断网回来接着办，同一幂等标识不发出第二条；按账号隔离，退出登录清除 | S5 |
| F7 | 分享管理页 | P0 | 顶部车辆与剩余可分享数；按条列对象（昵称+打码账号）、权限、有效期、状态；可单独撤销 | S3 |
| F8 | 撤销 | P0 | 对方在线立即失效返回已撤销；离线进入撤销中，宽限期内收敛；车辆侧自撤销起拒绝 | S4 |
| F9 | 接受页 | P0 | 车辆信息卡（车型、车主昵称、权限范围、有效期）+「添加到钱包」；无拒绝按钮 | S2 |
| F10 | 添加后卡片详情 | P0 | 钥匙卡进卡包，详情可见权限范围与有效期；权限之外功能不呈现而非置灰 | S2 |
| F11 | 状态同步与补拉 | P1 | 列表状态与实际一致（六态）；推送未到达时对方打开钱包按待接受列表补拉兜底 | S3 |
| F12 | 隐私 | P0 | 页面/日志/事件全程只显示对方昵称与打码账号，不出现完整账号或手机号 | S1,S2,S3 |
| F13 | 功能开关 | P1 | 默认关闭；关闭后不能发起新分享，已生效分享不受影响 | S1 |
| F14 | 事件上报 | P1 | 发起/接受/撤销/失效四类事件；只带车型类别、阶段与结果分类，不带车牌/账号/位置；上报失败不改变分享关系 | S1,S2,S3,S4 |

场景编号 S1–S7（金样 §2 场景表）：S1 发起分享、S2 接受生效、S3 管理查看、S4 撤销、S5 中断续办、S6 配额已满、S7 对象不可分享（S1–S5 取回灌版场景集，S6/S7 按 spec 档案 §3.3 补 004456 两类受限场景；角色表含 191025 的「其他联系人（临时借车，最小权限）」）。

异常编号 E1–E14（金样 spec §6，五列表）：E1 网络断开、E2 数据为空、E3 功能暂不支持（未登录/无车钥匙/开关关闭）、E4 配额已满、E5 车厂云签发失败、E6 接受时凭据下发失败、E7 撤销时对方离线、E8 发起中断、E9 对象不可分享、E10 换对象后已选档位不可用（不静默降级）、E11 账号切换（草稿清空、列表按新账号拉取，不跨账号带出）、E12 清除数据/缓存（草稿可自恢复，列表照常拉取，挂规约 ENV-01）、E13 重复提交（幂等去重+提交期防抖，不重复弹窗）、E14 推送未到达（对方打开钱包补拉待接受列表兜底）。来源：回灌版 E1–E10 + spec 档案 §3.7 补行（E11/E12 取 004631，E13 取 233718，E14 取 191025）。

## 3. 数值清单（三标法：上游约束：<文档名> / 本工程设定，无上游依据 / 平台基线）

| 数值 | 值 | 来源标签（金样正文写法） | 来源与裁定 |
|---|---|---|---|
| 同车分享上限 | 5 人（生效+待接受合计） | 上游约束：产品需求稿 | 回灌版 RR/prd.md 产品规则表；SR §4.1 配额口径一致 |
| 待接受有效期 | 72 小时，逾期自动作废、可重发 | 上游约束：产品需求稿 | RR/prd.md 产品规则表 + AC-K3；SR 状态机「72 小时未接受」一致 |
| 有效期选项 | 7 天 / 30 天 / 自定义至多 180 天，到期自动失效 | 上游约束：产品需求稿 | RR/prd.md 产品规则表 |
| 撤销离线宽限窗 | 产品稿 24 小时 / 系统设计 48 小时，**冲突披露、不写死** | 正文写「车辆侧自撤销发起即拒绝；宽限窗只影响对方设备上卡片消失时间，端侧只展示车云返回的状态，不裁决时长」 | RR/prd.md「离线的最长 24 小时内失效」vs SR/design.md §4.4「宽限窗按 48 小时计」；spec §7.1 行披露双值并挂议题 D1（233718 披露式写法，spec 档案 §3.8）；story 正文不出现数值裁决（回灌版 story §8.5 说明句形态）；D1 open（decisions.json 真源） |
| 业务目标 | 上线三个月内发起过分享比例 ≥ 15%；「借车送钥匙」类客服咨询量下降一半 | 上游约束：产品需求稿 | RR/prd.md 背景；spec §1 与 story §1.2 引用 |
| 页面首屏可交互 | 首次进入 ≤ 1.5 秒 | 本工程设定，无上游依据（登记议题 D2） | decisions.json D2；回灌版 spec §7.1 同 |
| 本地选择反馈 | ≤ 300 ms | 本工程设定，无上游依据（与首屏时延同批登记，见议题 D2） | 233718 spec §7.1 写法（spec 档案 §3.8）；回灌版误标「平台基线」，金样改三标法 |
| 列表滚动帧率 | ≥ 54 FPS | 本工程设定，无上游依据（与首屏时延同批登记，见议题 D2） | **FPS 54/55 漂移裁定**：spec/story 档案 §7-E.1 判「平台基线」标注可疑——RR/SR 均无此值，工程内无基线文件（已核：`54 FPS` 在本仓仅作为框架 spec 门禁描述的示例文案出现于 `demo/framework/specs/phase-rules/spec-rules.yaml:253` 与 `demo/framework/harness/scripts/check-spec.ts:816`，非工程基线）。取 54（214925 与回灌版两份一致，191025 的 55 为孤例漂移）；来源标签改按三标法如实标「本工程设定，无上游依据」，不再标「平台基线」 |
| 端云请求频次 | 进设置页配额查询 1 次、选定对象权限查询 1 次（换对象重查 1 次）、进管理页列表查询 1 次；无轮询/定时任务，失败按用户重试触发 | 接口语义为上游约束：系统设计说明（按页触发、无轮询）；频次上限为本工程设定 | 回灌版 spec §7.1 + 规约 DFX-01（金样去掉文档坐标「SR/design.md §4」，改写「系统设计说明」，spec 档案 §7-B.3） |
| 系统版本 | 目标 SDK 6.0.2（API 22），兼容 SDK 6.0.1（API 21） | 本工程配置，来源于 build-profile | **已核** `demo/build-profile.json5:6-7`（targetSdkVersion 6.0.2(22)、compatibleSdkVersion 6.0.1(21)）；233718 写法（spec 档案 §3.8，214925 把它误标「平台基线」，不取） |
| 图片资源上限 | 新引入单张 ≤ 10KB 并给依据 | 规约基线值（RES-01），标注「本工程设定值，非平台限制」 | `extensions/knowledge/constraints/resource-usage.md` RES-01；233718 §9.2 落法 |
| 状态机 | 六态互斥：待接受/生效/已作废/已到期/撤销中/已撤销 | 上游约束：系统设计说明 | SR §3；spec §5、story §2.2、术语与验收同 |
| 事件约定 | 四类事件（发起/接受/撤销/失效），只带车型类别、阶段与结果分类，不带车牌/账号/位置 | 上游约束：系统设计说明 | SR §6 |

## 4. 议题体系（统一 D 编号）

来源：D1–D3 取回灌版 `AR/story-src/decisions.json`（真源；其中 D2 按本文件 §3 的 FPS 裁定做一次扩展改写——标题与决策点扩到「同批自设性能指标（首屏 1.5 秒、300ms、54 FPS）的登记」，可选做法/建议/理由沿用真源原文，D1/D3 逐字保留）；D4–D9 为档案最佳实践增补议题（004631 D2/D6、214925 D2/D3/D4、0901 人裁），内容均改写为脱装置形态。本需求无澄清会议记录，无 T 系列议题号。D3 依据**去内部装置改写**：删去 `.scope-options.json`、`scope_decision`、`carry_all`、round 2 等装置词（回灌版退步项，spec/story/review 档案 §7-B.2；story-write 明令「不写关卡号、命令、轮次号」「评审人不读这个仓库」）。

| 编号 | 状态 | 类目 | 标题 | decider（只写角色） | 来源 |
|---|---|---|---|---|---|
| D1 | open | 业务规则 | 撤销离线宽限窗取 24 小时还是 48 小时 | 出行产品负责人 | decisions.json D1（真源） |
| D2 | open | 质量指标 | 分享页面首屏可交互时延等自设性能指标的登记 | 性能负责人 | decisions.json D2（真源；金样把 300ms/54FPS 归入同批自设指标登记，见 §3 FPS 裁定） |
| D3 | settled | 范围与交付 | 本 AR 按当前范围整体承载，不拆分 | 产品负责人 | decisions.json D3（真源；依据去装置改写） |
| D4 | open | 依赖与承载 | 车云六接口在本工程无后端、无网络封装前提下以本地模拟数据承载 | 端侧负责人 | 214925 review D2（spec/story/review 档案 §5.1 最佳 open 块） |
| D5 | open | 依赖与承载 | 发起草稿的持久化边界：页面级内存续办与进程被杀恢复到什么程度 | 端侧负责人 | 214925 review D4（spec 档案 §7-B.2 点名议题） |
| D6 | open | 交互与界面 | 分享入口挂点：工程尚无车钥匙卡片本人能力，以模拟车钥匙卡片承载入口 | 产品负责人 | 214925 review D3（004631 D6 同议题；spec 档案 §5.4/§7-B.2） |
| D7 | settled | 上线与开关 | 分享功能开关默认关闭、随版本放开，已生效分享不受影响（上游已定） | 车云侧负责人 | 004631 review D4（spec 档案 §5.2 最佳 settled 块；结论落到 `key_sharing_feature_enabled` 默认值与 AC-K10 一致性） |
| D8 | settled | 范围与交付 | 被分享人接受侧并入本单一起交付，不另立单据 | 需求评审人 | 0901 review 2.1.1（人裁原话「接受那一侧也一起做，别另立单」+《车钥匙接受侧界面说明》已入材料；spec 档案 §7-E.2 按 0901 口径裁定） |
| D9 | open | 业务规则 | 转赠与长期不联网强制下线两件事本期不结论，方案不得写成已定 | 安全评审负责人 | 004631 review D3（004631 D2/0901 DEC-3/DEC-4 同议题；上游约束：产品需求稿「还没定的两件事」） |

人工区口径（金样 review）：已定事项（D3/D7/D8）的评审结论与修改意见按 0901 真实回填形态写（勾选 + 结论 + 日期 2026-09-29 + 角色）；待确认事项（D1/D2/D4/D5/D6/D9）人工区留空待评审。文档头部标注：人工区在装置运行时由裁决命令填充，金样中的已定回填为写作示范。

## 5. 编号体系

- **AC 编号与上游承接**：AC-K1–AC-K11 逐条承接产品需求稿「六、验收意图」原编号，无「不承接」项（表头注沿用 125732：「编号行首为 AC-K1–AC-K11（承接上游 PRD 既有验收编号）」，spec 档案 §3.9）。关联功能映射：AC-K1→F1,F2,F5；AC-K2→F9,F10；AC-K3→F11；AC-K4→F4；AC-K5→F8；AC-K6→F6；AC-K7→F7,F11；AC-K8→F12；AC-K9→**F1**；AC-K10→F13；AC-K11→F3。**勘误裁定：AC-K9（入口门槛）在回灌版 spec §8 与 acceptance.yaml 均挂 (F3,F4)，属编号挂接笔误——AC-K9 内容是入口可见性，F1 功能描述即含「未登录或没有车钥匙的用户看不到入口」；金样按内容改挂 F1**（其余映射与回灌版一致）。
- **派生验收编号**：AC-F14（事件上报，P1 组）；AC-G1–G4（通用组：UX 显示与深色大字体、≤300ms 交互响应、失败提示与重试、端云兼容）；规约派生验收（AC-OBS02/05/06/07、AC-RES01/02、AC-COMPAT01/02、AC-ENV01/02、AC-DFX01/02、AC-DLV01）真源在回灌版 `acceptance.yaml`，spec §8 以尾注桥接（125732「另有……见 acceptance.yaml」句式），不在 spec 正文另立桥接小节（AR90006 档案 §3.9：正文另立桥接小节属结构越界）。
- **规约编号**（真源 `extensions/knowledge/constraints/*`，经 `spec/knowledge-use.yaml` 投影）：命中规约 16 条（投影表 17 行，SEC-01 拆两行）——UX-01、SEC-01（两行）、DFX-01、DFX-02、OBS-02、OBS-03、OBS-05、OBS-06、OBS-07、RES-01、RES-02、COMPAT-01、COMPAT-02、ENV-01、ENV-02、DLV-01；不命中 1 条——DLV-02（对外开放面不成立）。金样 spec 9.2/plan 9.2/story 附录规约节同此集合。
- **埋点统计点**（spec 9.4 中文名，全链统一）：分享发起流程 / 创建分享；分享接受流程 / 接受凭据下发；分享撤销流程 / 撤销；分享失效流程 / 状态回读。流程号 001–004；内码候选值 `0101000000`、`0101010001`、`0101000002`、`0102000000`、`0102010001`、`0103000000`、`0103000001`、`0103010002`、`0104000000`、`0104000001`（全部标「候选，待登记：KeySharingChartCodes」；取号按 `extensions/knowledge/facts/event-tracking.md` §7：十位「模块→流程→节点→子节点→结果」，结果 00 成功/10 主动取消/其余失败，步骤 000 表示流程整体）。能力差距：仓内模板仅 `Wallet_COMMON`（已核 `demo/05-SystemBase/CommFunc/src/main/ets/shared/ha/WalletHAEventID.ets:2` 当前仅此一值），流程/步骤/内码须新增登记。
- **议题编号**：D1–D9（见 §4）。

## 6. 契约实体

### 6.1 端云接口（六支，全部新增；出参含 0901 已定的档位文案承载说明）

来源：SR §4.1–4.5 接口约定（字段级入出参写法取 214925 spec 9.1.1 + 233718 表后声明）。

| 接口 | 入参 → 出参 | 错误码口径 |
|---|---|---|
| `queryKeySharingQuota` | `{ vehicleId }` → `{ remainingCount, summary[] }` | 无新增（网络/通用失败） |
| `queryGranteePermission` | `{ vehicleId, granteeAccount }` → `{ availablePermissions[], permissionText[] }`；对象不可分享返回原因、档位区不呈现 | 无新增；对象不可分享为业务原因非错误码 |
| `createKeySharing` | `{ vehicleId, granteeAccount, permission, expireAt, idempotencyKey }` → `{ shareId, state=PENDING_ACCEPT }` | 签发失败/配额满以失败分类返回；车云回滚不留半生效 |
| `acceptKeySharing` | `{ shareId }` → `{ credentialState }` | 凭据下发失败（保持待接受可重试） |
| `revokeKeySharing` | `{ shareId }` → `{ state=REVOKED \| REVOKING }` | 无新增 |
| `queryKeySharingList` | `{ vehicleId }` → `{ shares[] }`（每条含状态、权限、有效期、对方脱敏标识） | 无新增 |

注：`permissionText[]`（权限档位文案随档位查询接口返回）是 0901 已定承载（0901 review 2.3.1 人裁「档位文案先随那个查询接口带回来」）；SR 上游口径为「云侧配置下发、端侧不写死」，金样 spec 9.1.3 配置项行保留上游口径并注明本期承载。表后声明（233718）：真实服务联调按接口名、字段与车云错误码补齐，接口契约不变；模拟阶段不改业务状态机语义，只换数据来源。

### 6.2 存储

| 键名/表名 | 介质 | 值结构 | 有效期 | 用途 | 代码现状 |
|---|---|---|---|---|---|
| `key_sharing_draft` | 待 plan 定（候选：页面级内存 / Preferences；见议题 D5） | `{ vehicleId, granteeMaskedAccount, permissionLevel, expireDays, idemKey }` | 发起成功即清除；退出登录清除 | 发起途中中断/断网续办，同一幂等不重发第二条；按账号隔离 | 现有 WalletMain 无本地草稿持久化（检索 Preferences 于 WalletMain 零命中），属新增域（191025 介质诚实写法 + 233718 两行式） |
| 分享列表 | 不落本地 | — | — | 车钥匙类数据不缓存，每次进页从云侧拉取 | 仓内无分享列表缓存，检索零命中（233718） |

### 6.3 配置

| 配置项 | 默认值 | 关闭态行为 | 兼容 | 代码现状 |
|---|---|---|---|---|
| `key_sharing_feature_enabled` | `false` | 未登录/无车钥匙/开关关闭不显示分享入口；关闭不能发起新分享，已生效分享不受影响 | 旧版本读不到视为关闭态 | 既有开关常量先例 `HomeConstants.SHOW_LOCAL_CARD_SECTION`（**已核** `demo/02-Feature/WalletMain/src/main/ets/shared/constant/HomeConstants.ets:4`），新增于 WalletMain 同名常量区；实现方式（云侧下发或本地常量）待 plan 定 |
| 权限档位文案 | 云侧配置下发 | 端侧不写死档位名 | — | 本期随 `queryGranteePermission` 返回承载（0901 已定，见 §6.1 注） |

### 6.4 设计模式 pattern/role（金样取 page-interaction 选 + decision-tree 反证不选）

| 模式 | 选/不选 | 角色 → 实体 | 依据 |
|---|---|---|---|
| page-interaction | 选 | 动作表 `ShareSetupPageOperates`（动作枚举 `ShareSetupActions` 同文件）、交互封装 `ShareSetupPageInteraction`、上下文 `ShareSetupContext`、页面组件 `KeySharingSetupPage` | 回灌版 plan 9.3 选型（五角色实例名，plan 档案 §8「选=回灌版」）；角色集已核 `extensions/knowledge/design-patterns/page-interaction.md` frontmatter roles=[动作表,动作枚举,交互封装,上下文,页面组件] |
| decision-tree | 不选 | —（反证） | 191025 反证 + 回灌版反证合并：端侧发起链路的分支（配额满、对象不可分享、签发失败）都是前置校验或单次提交的结果判断，每支一步即收敛，不构成「每个分支自身多步、各有失败处理」的编排需求；尾注声明理由基于业务过程本身的复杂度而非承载方式，换真实云后仍成立（plan 档案 §8「反证=191025」）；role 集已核 `decision-tree.md` roles=[节点表,步骤枚举,上下文,构建与启动] |

投影形态（233718 全标注）：选型表后单独一段逐文件列 pattern/role 并声明投到契约——`ShareSetupPageOperates.ets`（pattern=page-interaction，role=动作表；动作枚举同文件）、`ShareSetupPageInteraction.ets`（role=交互封装）、`ShareSetupContext.ets`（role=上下文）、`KeySharingSetupPage.ets`（role=页面组件）；`contracts.files[].pattern/role` 逐条对应，`ShareSetupPageInteraction.doOperator/selectGrantee/selectPermission/selectValidity` 进入 `interfaces[].methods[]`（0901 verifier 修复意见的落法，plan 档案 §4.1）。

### 6.5 工程事实（金样引用的全部工程标识，已核来源）

| 事实 | 来源（已核） |
|---|---|
| `CommFunc.MaskUtil.maskAccount`（脱敏，采集处调用） | `demo/05-SystemBase/CommFunc/src/main/ets/shared/utils/MaskUtil.ets:11`；知识 `engineering-capabilities.md` §33 |
| `WalletHAManager.chartBuilder/vocBuilder`、模板 `Wallet_COMMON`（仓内唯一模板值、业务零 Chart/VOC 调用） | `demo/05-SystemBase/CommFunc/src/main/ets/shared/ha/WalletHAManager.ets:6`、`WalletHAEventID.ets:2`；知识 `event-tracking.md` §4 |
| `CommFunc.Logger` 统一日志入口 | `extensions/knowledge/constraints/observability.md` OBS-02 |
| `CommUI` 组件：`SectionCard`、`ActionListItem`、`showToast`、`MaisonPrimaryButton`、`MaisonNavBar`、`MaisonDetailSection`、`MaisonSelector` | `demo/05-SystemBase/CommUI/src/main/ets/`（各文件实存）与 `index.ets` 导出 |
| 编排 SDK：`PageInteractionBuilderV3`、`PageInteractionManager.doOperator`、`DefaultPageInteractionContext`（oh 包名 `framework`，libs HAR） | `extensions/knowledge/design-patterns/page-interaction.md` §4–§6 |
| `HomeConstants.SHOW_LOCAL_CARD_SECTION` 开关常量先例 | `demo/02-Feature/WalletMain/src/main/ets/shared/constant/HomeConstants.ets:4` |
| `CardRepository` 卡种列表含「车钥匙」（c4），卡片列表为本地模拟数据、无车钥匙本人能力 | `demo/02-Feature/WalletMain/src/main/ets/data/repository/CardRepository.ets:33-40` |
| `Phone/index.ets` navDestinationMap 为硬编码分支（CardPackPage/AddCardEntryPage） | `demo/01-Product/Phone/src/main/ets/pages/index.ets:15-21` |
| WalletMain 资源目录仅 `base`（无 zh_CN/en 分目录） | `demo/02-Feature/WalletMain/src/main/resources/` 目录实查（RES-02 中英齐备与工程现状的差异登记进 plan 9.1 项目知识，084606 冲突登记形态） |
| 账号登录态：AccountManager 既有能力（AppStorage 键 + AccountService） | 回灌版 plan §5；`demo/04-BusinessBase/AccountManager` 模块实存 |

## 7. 来源映射

| 金样内容项 | 来源 |
|---|---|
| 业务规则全表（5 人/72h/7-30-180 天/撤销时限/隐私/权限档位） | 回灌版 `RR/prd.md`（产品规则表、用户旅程）；SR §3/§4/§5 复核一致 |
| F1–F14 功能清单 | 回灌版 `spec/spec.md` §3；行覆盖融合 191025（F10 权限外不呈现）、214925（F9 无拒绝按钮）、004631（表前集中 mock 声明） |
| 六接口入出参与失败语义 | 回灌版 `SR/design.md` §4.1–4.5；字段级形态取 214925 spec 9.1.1、story 附录 10.1.1 |
| 六态状态机与「车辆侧自撤销即拒绝」语义 | SR §3 + 191025 spec §5.2 图后语义句（spec 档案 §3.6） |
| Scope 口径与三处登记 rationale | spec 档案 §3.2（多数派口径 + 125732 rationale）；Phone/index.ets 工程事实 |
| Visual Handoff 四图 id+path+caption + 视觉证据声明 | 回灌版 spec Visual Handoff（四图实存于 `doc/features/ISSUE-206/ux-reference/`）+ 214925 图全量 + 125732 声明式（spec 档案 §3.2） |
| §0 术语表列序/确认注/回写约定/易混项 | 191025 主体 + 004631 确认注 + 回灌版回写句 + 233718 易混项质量（spec 档案 §3.0） |
| 场景集 S1–S7 | 回灌版 S1–S5 + 004456 S6/S7 + 191025 角色行（spec 档案 §3.3） |
| 异常表 E1–E14 | 回灌版 E1–E10 + spec 档案 §3.7 补行（E11/E12=004631、E13=233718、E14=191025、E10 不静默降级=125732） |
| §7.1 性能四行（含冲突披露行） | 233718 spec §7.1 原句（spec 档案 §3.8）；频次行取 214925（按接口名落）；FPS 裁定见 §3 |
| §7.2 SDK 行 | 233718 spec §7.2（已核 build-profile） |
| §7.3 安全边界 | 233718（凭据边界、不扩大权限）+ 回灌版（不落盘/账号隔离/不缓存）+ 191025（调用方校验） |
| §8 验收结构 | 125732 表头注 + 回灌版 P0/P1/通用分组 + 214925 未决口径说明 + acceptance.yaml 桥接尾注（125732 句式） |
| §9 锚点表/9.1.1 表前声明/9.1.2 两行式/9.1.3 具名+先例/9.1.4 不涉及一行 | 214925 + 233718 + 回灌版 + 191025（spec 档案 §3.10 逐节最佳） |
| 9.2 规约投影（落点三形、统计点全名、DLV-02 依据） | 回灌版 spec 9.2 + 233718 落点写统计点全名（spec 档案 §3.10） |
| 9.3 设计模式候选登记 | 回灌版 spec/knowledge-use.yaml 投影（两候选） |
| 9.4 埋点总述/定义段/六列表/边界句 | 回灌版 9.4 + 191025 四问形与边界句 + 233718 失效定性（spec 档案 §3.10） |
| story 十章骨架、十章合同、附录五节 | `extensions/skills/story/contracts/story-chapters.json`；回灌版 story 结构 |
| story 1.4 未定案/3.3 承载表挂 D 号/5.1 时序图源标记/6.7 模拟承载/8.4 可算口径/9.2 开关三列表/9.3 替换点 | 233718 §1.4、214925 §3.3/§5.1/§6.7/§8.4、233718 §9.3、214925 §9.3（spec/story 档案 §4/§8 逐章最佳） |
| story 六态判别表（状态/判别条件/谁发起的）+ 分清句 | 214925 story §2.2 |
| story 草稿×配额组合句、恢复兜底四条 | 004631 story §7.3 + 回灌版 story §7.3 |
| story 主叙事红线（零工程标识/零来源括注/零文档坐标） | `story-chapters.json` language_redline；回灌版 story 正文形态 |
| review 三章/七维类目/机器区+人工区/decider 只写角色 | 现行渲染合同（214925/回灌版形态）+ `story-chapters.json` decision_categories |
| review open 块（双材料原话依据、选项带后果、建议/理由解耦端云） | 214925 D1/D2/D4（spec 档案 §5.1） |
| review settled 块（引 SR 原文/引人的原话、四件套取舍、不同意时改什么） | 004631 D4 + 0901 2.1.1/2.2.1/2.6.2（spec 档案 §5.2） |
| review 人工区回填形态（结论+日期+角色） | 0901 review（全池唯一评审人真实回填样本，spec 档案 §5.3） |
| review 议题覆盖（入口挂点/草稿持久化/接受侧归属/自设阈值/转赠强制下线/开关已定） | 004631 六条最广 + 214925 两条（spec 档案 §5.4） |
| plan 头部真源说明/§1 架构图含编排 SDK 节点/§2 三列表+绑定句/§3 模型对齐句与状态收窄/§4 挂真实组件名/§5 六列/§6 settle 进契约/§7 注册链注/§8 覆盖率自洽 | 214925 头部、233718 §1/§3、004631 §2/§3、125732 §4/§5、AR90006-0824 §7 注册链、214925 §8（plan 档案 §3/§8 逐章最佳） |
| plan 9.1 项目知识（不符之处写实、RES-02 冲突登记）/9.2 规约（落实写具体动作、章名「号+章名」）/9.3 选型+反证+投影/9.4 九列+共同约定+待登记 | 214925/084606、214925/233718/130326、回灌版/191025/233718、233718/125732/214925（plan 档案 §3.10） |
| plan 埋点九列与候选取号规则 | `extensions/knowledge/facts/event-tracking.md` §5–§7 |
| 错装快照排除 | spec/story/review 档案 §2 口径澄清；已抽验 20260829-221817 的 ISSUE-206/spec.md 标题为交通卡自动充值 |

## 8. 自查记录

自查日期：2026-09-29（写作当轮完成；机械核对以脚本统计，语义连贯以全文通读核对）。

### 8.1 四份互查（以本文件为准）

| 检查项 | 结果 |
|---|---|
| F 编号 | spec §3 与 plan §8 均为 F1–F14 共 14 行；P0 9 项 / P1 5 项两侧一致；story 正文按十章合同不携带 F 号（drop 列表），功能名与 spec 同义 |
| AC 编号 | spec §8 与 story §8 的 AC-K 去重集合均为 K1–K11 全集（story 每号恰出现一次，AC-K5 另有说明句一次）；AC-K9 挂 F1（勘误裁定见 §5）；plan §5/§6 引用的 AC-K9/K5/K6/K7/K2 均在 spec §8 在册；AC-F14 与通用组 AC-G1–G4 spec/story（验收点覆盖）/acceptance 桥接尾注一致 |
| 议题编号 | review 渲染 D1–D9 全部 9 块（story-build 标记 9、decision 注记 9，一一配对）；spec 锚点表引 D1/D2/D4/D5/D6/D9；story 引 D1/D2/D4/D5/D6/D8/D9；plan 引 D5/D6——全部在册，无悬空 |
| 数值 | 5 人 / 72 小时 / 7·30·180 天 / 24h vs 48h 披露 / 15% / 1.5s / 300ms / 54 FPS / SDK 6.0.2(22)·6.0.1(21) / 10KB：spec §7 与 story §1/§3/§4/§6/§8 同值同口径；来源标签只出现在 spec（story 红线核对为零命中） |
| 接口/存储/配置名 | 六接口名 spec（15 次）/story（6 次，全部在附录投影）/plan（20 次，端侧方法名已统一为 queryKeySharingQuota/queryGranteePermission 等）一致；`key_sharing_draft` 值结构三处一致；`key_sharing_feature_enabled` 四处一致；plan 中旧方法名残留 0 |
| pattern/role | plan §9.3 选 page-interaction（4 角色文件 + 投影说明）、decision-tree 不选（业务反证）；§2 文件表含全部角色文件；与 factbase §6.4 的 role 集（page-interaction frontmatter roles）逐条对应 |
| 埋点 | spec 9.4 四指标 + 六列统计点表与 story 10.3 投影、plan 9.4.2 九列逐点表（10 行，统计点×结果零重复）对齐；统计点名中文四处统一；内码候选值 10 个与本文件 §5 清单一致；流程号 001–004 |
| 规约 | spec 9.2（17 行）/ story 10.2（17 行）/ plan 9.2（16 条目）同集合：16 条命中（SEC-01 两行）+ DLV-02 不命中 |
| 红线（story 第 1–9 章） | 来源括注 0、工程标识 0、F/S/E/BD 编号 0、文档坐标 0（机械扫描） |
| 文档坐标（spec） | 9.2 落点零「§9.1 ·」前缀；§3 与 9.1.3 的两处小节指针已改为按名字指（附录 A 的「§0 术语映射表」为模板规定句，保留） |
| plan 覆盖率自洽 | §8 表实际 P0 行 9、P1 行 5，覆盖率「P0: 9/9 / P1: 5/5」与括注项数一致（回灌版 8/8、6/6 的矛盾已修正） |

### 8.2 独立通读结论

- spec：头部 → §0 术语（七列+确认注+回写）→ Scope（含三处登记 rationale 与视觉证据声明）→ 场景/功能/页面/流程/异常/非功能/验收 → §9 四节平列 → 附录，叙事按模板推进；扩展章锚点表与 9.1–9.4 的每个实体（接口、存储、配置、统计点）都可在 §3/§6/§7/§8 找到业务落点，无孤立登记。
- story：十章骨架完整；背景交代未定案三件事（D1/D9/自设指标），范围承载表与功能说明、异常、验收的承载口径一致（同一句式「以本地模拟数据按接口语义承载」贯穿）；图前有过程、图后有分支去向；附录投影与 spec 真源逐表对应。
- review：三章固定、类目按七维词表分组；open 块依据含双材料原话与工程事实，settled 块依据引上游原文或人的原话并给「不同意时改什么」；D3 依据无任何内部装置词（关卡号/命令/轮次号零命中）；人工区已定回填、待确认留空，与头部标注一致。
- plan：头部 → Scope 继承（无扩展，与 spec 修正口径一致）→ §1–§8 设计章（三列表、六列状态表、settle 进契约、注册链注、覆盖率自洽）→ §9 四节固定序 → 附录；规约表承载设计章全部用「号 + 章名」实际章名，无纯坐标。

### 8.3 遗留说明（不影响金样成立的已知边界）

- 金样中的生成区标记（knowledge-use / story-build）省略了真实运行的校验值，已在其注释内注明「金样示意」。
- 图片相对路径按消费工程材料布局书写；图片实体已复制进本目录（spec 的 `ux-reference/`、story 的 `assets/`，来源快照 Story-Features-20260928-214925，登记见 §9），spec/story 头部标注块已同步更新。
- AC-K9 挂 F1 为对回灌版两处（spec §8、acceptance.yaml）挂接笔误的勘误，见 §5；如需回灌版同步修正，属回灌版维护事务，不在本轮金样范围。
- plan §6 的 `KeySharingService` 结算方法按每统计点一个 settle 方法声明（settleCreateResult 等），与 event-tracking 知识「settle<结果>」的拟定命名惯例一致；知识原文以逐结果命名为示例，两种粒度均为「结算方法写进契约」的合规落法。

## 9. 图形资产清单

> 金样中每个 mermaid 图/图片资产一行；图类型选择依据为 extensions/skills/story/phases/story-write.md「图类型选择表」，图文组织按「每张图三件套」（图前一段讲过程、图、图后写图上没有的分支细节）。业务口径一律以本 factbase 为准。
>
> **spec 图片承载裁定**：spec 的参考图统一由「Visual Handoff（由 check-spec 读取）」承载（`authoritative_refs` 逐图 id+path+caption）；spec 正文不嵌 markdown 图片——初稿曾在 §4.2 区域节嵌 4 图，经核非模板形态（历史 27 份仅 2 份自由发挥过）后移除，区域标题保留文字图号引用（`区域 N: …（<id>，图 N）`，20260927-125732 最佳形态）。Visual Handoff `path` 保持真实运行形态（`doc/features/ISSUE-206/ux-reference/…`）；金样目录内同图实体位于 `ux-reference/`。story 的 markdown 图片引用是机制支持形态（真实运行中经 `materials.json` 登记并标注 caption/used）。

| 所在产物与节 | 图类型 | 选择依据（选择表行） | 素材来源 |
|---|---|---|---|
| spec §5.1 发起主路径 | flowchart TD | 「主路径与条件分流」行：两条以上有依据的分支 | 回灌版 spec §5.1 核心业务流（同主题主图）；分支按本 factbase §2 与异常 E4/E5/E9 增强 |
| spec §5.2 分享状态机（六态） | stateDiagram-v2 | 「一个对象的状态与允许的动作」行：状态互斥且迁移有条件；原 flowchart LR 不承载状态语义，按选择表改绘 | 状态与迁移按 SR §3 六态与议题 D1 口径（与正文同源）；状态图形态底取历史快照 20260901-122028 story §5.5，业务事实不取自快照 |
| spec §5.2 状态×动作对照表 | 对照表（markdown 表，行 3 配套件） | 选择表行 3 完整形态为「stateDiagram + 状态与动作对照表」；迁移全集速查、备注只写图上没有的语义（生效条件、终态不迁出、仅已作废可重发） | 按上方状态机与 D1 口径构造，与正文同源 |
| spec §5.3 接受子流程 | flowchart TD | 「主路径与条件分流」行 | 历史快照 20260901-122028 story §5.3 接受与添加（同主题）；失败语义按本 factbase §6.1 acceptKeySharing 口径 |
| spec §5.4 中断续办子流程 | flowchart TD | 「主路径与条件分流」行 | 历史快照 20260901-122028 story §5.6 中断续办（同主题）；账号切换不进图，归异常表 E11 |
| spec Visual Handoff 图 1（ux-reference/share-setup.png，id=share_setup） | 原型原图（Visual Handoff authoritative_refs） | spec 参考图承载机制；「页面长什么样」行 | 历史快照 Story-Features-20260928-214925 |
| spec Visual Handoff 图 2（ux-reference/share-manage.png，id=share_manage） | 原型原图（Visual Handoff） | 同上 | 历史快照 Story-Features-20260928-214925 |
| spec Visual Handoff 图 3（ux-reference/accept-page.png，id=accept_page） | 原型原图（Visual Handoff） | 同上 | 历史快照 Story-Features-20260928-214925 |
| spec Visual Handoff 图 4（ux-reference/key-card-detail.png，id=key_card_detail） | 原型原图（Visual Handoff） | 同上 | 历史快照 Story-Features-20260928-214925 |
| story §5 总览（图源 需求规格·发起主路径） | flowchart TD | 「主路径与条件分流」行 | 承接 spec §5.1 发起主路径（图源标记在图上），补入口门槛与配额拦截分流 |
| story §5.1 分享建立时序（图源 系统设计说明·发起时序） | sequenceDiagram | 「谁调用谁、谁返回、谁补偿」行：三方以上且有失败责任要分清 | 图源标记 系统设计说明·发起时序；四泳道与全链形态底取历史快照 20260901-122028 story §5.1 时序图，接受生效段按本 factbase §6.1 接口语义补足，业务事实不取自快照 |
| story §5.3 分享状态机（图源 系统设计说明·分享状态机；需求规格·分享状态机） | stateDiagram-v2 | 「一个对象的状态与允许的动作」行：状态互斥且迁移有条件 | 承接 spec §5.2 分享状态机（图源标记在图上） |
| story §5.3 撤销子流程（图源 需求规格·撤销子流程） | flowchart TD | 「主路径与条件分流」行：在线/离线两分支 | 历史快照 20260901-122028 story §5.4 撤销与宽限窗（同主题）；宽限窗不写数值（议题 D1） |
| story §6.2 图 1（assets/share-setup.png） | 原型原图（图片资产） | 「页面长什么样」行：有真实素材 | 历史快照 Story-Features-20260928-214925 |
| story §6.6 图 2（assets/share-manage.png） | 原型原图（图片资产） | 「页面长什么样」行 | 历史快照 Story-Features-20260928-214925 |
| story §6.8 图 3（assets/accept-page.png） | 原型原图（图片资产） | 「页面长什么样」行 | 历史快照 Story-Features-20260928-214925 |
| story §6.8 图 4（assets/key-card-detail.png） | 原型原图（图片资产） | 「页面长什么样」行 | 历史快照 Story-Features-20260928-214925 |
| plan §1 模块架构图 | graph TD | 「依赖与开放顺序」行：模块依赖有方向分层 | 233718 §1 架构图写法（含编排 SDK 节点，见 §7 来源映射） |
| plan §7 页面流转图 | flowchart LR | 「主路径与条件分流」行：入口与页面跳转分支 | 页面与路由名按 plan §7 注册链注与本 factbase §6.5 Phone 路由现状；推送/补拉双入口按异常 E14 |
