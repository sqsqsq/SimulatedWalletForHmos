---
derived_from:
  artifact: component-blueprint@1
  component_id: WalletMain
  blueprint_id: bp-AR90006
  revision: 2
  source_fingerprint: sha256:5cf72e412d8e71f533b53f5566bcea7c6e14c6cf0aacaacff2b1780cd7003aaa
  artifact_sha256: sha256:89a43ce71b62943c4b35e0d0fe5c2763419115f838b52a3a781309486df0b3a9
projection: component-blueprint-review@1
---

# 交通卡自动充值（钱包端）— 部件演进蓝图

钱包端交通卡自动充值：签约入口与签约交互、状态展示与管理、未实名引导与端侧暂存。判定与扣款都在服务端；端侧通过交通卡云五个接口实现签约/状态/改档/解约，并经支付部件完成免密验证。人已确认整体承载（无拆分），会议 T1–T4/T6 已裁决，T5 已采纳。入口可见性按矩阵细分（可签约/未实名/开关/已签约）；改档/关闭走 update/cancel 原关系不断。

## Design views

### logical

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 自动充值领域概念与接口契约的部件侧视图：签约关系、签约/管理链路、入口显示控制
- Stakeholders: 钱包产品组, 钱包端开发, 交通卡云开发, 支付部件
- Current: 钱包端无自动充值概念；交通卡详情页无自动充值入口
- Target: 签约关系（contractNo/门限/面额/状态）为端侧展示依据；签约与管理两条链路经五个接口对接卡云
- Delta: 新增自动充值概念与签约/管理链路，入口分流由可签约性、开关与已签约状态共同决定
- Decisions/gaps: decision:scope-human-1, decision:knowledge-sec-01, decision:knowledge-ux-01, gap:gap-update-response, gap:gap-amount-verify
- Verification: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md

Nodes:

- contract-concept — owner=WalletMain; current=钱包端无自动充值签约关系概念; target=端侧签约关系展示模型：contractNo、门限、面额、状态（none/active/disabled），来源为云侧状态查询; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md, contract:getAutoTopupStatus
- signup-flow — owner=WalletMain; current=不存在; target=详情页入口→签约页（门限/面额单选、协议勾选）→免密验证→创建签约→详情页显示已开启；失败/取消/退出保留选择; basis=—; verification=contract:getAutoTopupPolicy, contract:createAutoTopupContract
- manage-flow — owner=WalletMain; current=不存在; target=管理页（状态/记录/停用态）→ 改门限面额（update）或关闭（cancel）或停用态查看原因后重签; basis=—; verification=contract:getAutoTopupStatus, contract:updateAutoTopupContract, contract:cancelAutoTopupContract
- entry-control — owner=WalletMain; current=交通卡详情页无自动充值入口; target=入口可见性矩阵：未签约+开关开+可签约→签约页；未签约+开关开+未实名→可见并引导实名；未签约+开关关→隐藏；已签约→始终可见进管理页。分流字段用 getAutoTopupPolicy.signable/unsignableReason 与运营开关，不把开关折叠进 signable; basis=—; verification=contract:getAutoTopupPolicy, contract:getAutoTopupStatus

### runtime

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 自动充值在钱包端运行时的数据流与状态归属：策略加载、签约状态缓存、改档与解约的写入闭合
- Stakeholders: 钱包端开发, 测试, 交通卡云开发
- Current: 无自动充值运行时数据流
- Target: 策略/状态来自卡云，端侧缓存 wallet_auto_topup_contract（按账号隔离、退出登录清除、不备份）供免网展示
- Delta: 新增配置加载流与签约状态流两条数据流；状态 owner 为钱包端缓存，权威在卡云
- Decisions/gaps: decision:knowledge-sec-01, gap:gap-agreement-retry
- Verification: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md

Nodes:

- contract-cache — owner=WalletMain; current=无自动充值缓存; target=wallet_auto_topup_contract 缓存 contractNo/门限/面额/状态；按账号隔离、退出登录清除、不参与备份恢复、仅免网展示; basis=contract:getAutoTopupStatus; verification=contract:getAutoTopupStatus
- strategy-loading — owner=WalletMain; current=无; target=详情页入口处按需加载可签约性与档位；支付能力不可用时隐藏新签约入口; basis=contract:getAutoTopupPolicy; verification=contract:getAutoTopupPolicy

### development

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 钱包端实现位置与模块归属：入口、签约页、管理页、仓储与缓存
- Stakeholders: 钱包端开发, 测试
- Current: WalletMain 无自动充值页面与仓储
- Target: 新增 entry/signup/manage 页面节点与 AutoTopupRepository、AutoTopupContractCache，全部归 WalletMain 模块
- Delta: 新增 5 个开发节点，module=WalletMain
- Decisions/gaps: decision:knowledge-sec-01, decision:knowledge-ux-01
- Verification: doc/module-catalog.yaml#WalletMain

Nodes:

- auto-topup-entry-builder — owner=WalletMain; current=不存在; target=交通卡详情页自动充值入口 builder（整行，余额行之下、记录之上）；分流到签约页或管理页；未实名引导; basis=contract:getAutoTopupPolicy, contract:getAutoTopupStatus; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md, contract:getAutoTopupPolicy
- auto-topup-signup-page — owner=WalletMain; current=不存在; target=签约页：门限/面额单选数据来自 getAutoTopupPolicy.thresholdOptions/amountOptions（运营下发，现行值 5/10/20/30 与 20/50/100 仅作说明）；协议勾选后「开启」可点；拉起免密验证；失败/取消/退出保留选择; basis=contract:getAutoTopupPolicy, contract:createAutoTopupContract; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md, contract:createAutoTopupContract
- auto-topup-manage-page — owner=WalletMain; current=不存在; target=管理页：顶部签约状态、最近记录（失败展示原因）、停用态横幅与原因；改门限面额与关闭入口；停用重签入口; basis=contract:getAutoTopupStatus, contract:updateAutoTopupContract, contract:cancelAutoTopupContract; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md, contract:getAutoTopupStatus
- auto-topup-repository — owner=WalletMain; current=不存在; target=AutoTopupRepository：getPolicy / createContract / getStatus / updateContract / cancelContract 到卡云，金额以分; basis=contract:getAutoTopupPolicy, contract:createAutoTopupContract, contract:getAutoTopupStatus, contract:updateAutoTopupContract, contract:cancelAutoTopupContract; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- auto-topup-cache — owner=WalletMain; current=不存在; target=wallet_auto_topup_contract 缓存读写；按账号隔离、退出登录清除、不参与备份恢复; basis=contract:getAutoTopupStatus; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md

### deployment

- Applicability: not_applicable
- Evolution impact: —
- Unchanged evidence: —
- Purpose: 部署视图裁决：单手机应用无独立部署单元
- Stakeholders: 钱包端开发
- Current: 无变化
- Target: 无变化
- Delta: none
- Decisions/gaps: —
- Verification: doc/architecture.md

Nodes:

- None (evidence-backed not applicable view).

### scenarios

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 验收场景怎么走：签约、管理、异常分支与开关
- Stakeholders: 钱包产品组, 测试, 钱包端开发
- Current: 无自动充值场景
- Target: 验收意图与场景逐条落实到逻辑/运行时/开发对象
- Delta: 新增 9 个场景节点，对应 RR 验收意图与会议裁决
- Decisions/gaps: decision:scope-human-1
- Verification: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md

Nodes:

- scenario-unauth-guide — owner=WalletMain; current=不存在; target=未实名用户能看到入口，点进去被引导实名，完成实名前无法签约（会议 T3 修订 AC-R1）; basis=—; verification=doc/features/AR90006/AR/story-src/meetings/交通卡澄清会记录-0903/23fdc64d/raw.md
- scenario-signup-success — owner=WalletMain; current=不存在; target=签约成功：详情页显示已开启与门限面额；余额低于门限自动充值（云侧）并在记录可见; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- scenario-verify-cancel-resume — owner=WalletMain; current=不存在; target=验证界面取消回到签约页，门限面额仍在可直接再开启（AC-R7）; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md
- scenario-signed-reentry — owner=WalletMain; current=不存在; target=已签约卡再点入口进入管理页而非重新签约（AC-R9；existed 分流）; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- scenario-switch-off-signed — owner=WalletMain; current=不存在; target=功能开关关闭：未签约看不到入口；已签约入口不隐藏、照常自动充值（会议 T4 修订 AC-R4）; basis=—; verification=doc/features/AR90006/AR/story-src/meetings/交通卡澄清会记录-0903/23fdc64d/raw.md
- scenario-disabled-restart — owner=WalletMain; current=不存在; target=连续 3 次扣款失败停用：管理页看到停用状态与失败原因并可重新签约（AC-R3）; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- scenario-update-and-cancel — owner=WalletMain; current=不存在; target=修改门限面额按新值生效（update 原关系不断，会议 T1）；关闭后不再触发（AC-R6）; basis=—; verification=doc/features/AR90006/AR/story-src/meetings/交通卡澄清会记录-0903/23fdc64d/raw.md
- scenario-record-mask — owner=WalletMain; current=不存在; target=充值记录卡号按现有规则脱敏展示（AC-R5）; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md
- scenario-exit-resume — owner=WalletMain; current=不存在; target=中途退出签约页，下次进入回填此前门限面额（仅本账号本卡，退出登录清除）; basis=—; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md

## Runtime data flows

### flow:auto-topup-signup-bind

- Data domains: wallet-auto-topup-contract
- External contracts: contract:getAutoTopupPolicy, contract:createAutoTopupContract
- Logical contracts: contract:createAutoTopupContract
- Development owner: view:development/node:auto-topup-repository
- Source of truth: authority=contract:createAutoTopupContract; persistence=view:development/node:auto-topup-repository; projections=view:runtime/node:contract-cache; reconciliation=端侧缓存缺失以云侧查询为准；云侧查询失败时状态未知，不以缓存缺失推断未签约；写入结果即时刷新缓存
- Initial load: id=signup-open; strategy=入口打开时拉取策略; owner=view:development/node:auto-topup-repository; freshness=每次入口进入时刷新
- State owner: view:runtime/node:contract-cache; states=无签约, 已签约
- Recovery: id=signup-failure; persistence=免密验证取消或未通过：不建签约、保留已选门限面额；授权后创建明确失败：不写半签约状态，留在签约页保留选择，再次尝试的方式待 pending-agreement-retry；创建结果未知（超时）：不显示成功也不显示未签约，以 getAutoTopupStatus 确认云侧状态（active 按已开启展示，none 视为本次未建成，查询失败保持未知、可再查）; subscription=无订阅; process=暂存选择（仅本账号本卡）退出登录清除
- Evidence: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md, doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- Verification: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md

Triggers:

- user_action — timing=入口打开/签约页; idempotency=以「卡片+生效状态」判重，已有生效签约返回既有 contractNo

Mutations and publications:

- mutation create-contract-mutation — persistence=view:development/node:auto-topup-repository; publication=publication:contract-written; recovery=recovery:signup-failure
- publication contract-written — snapshot=contractNo、门限、面额、状态写入缓存并驱动详情页展示

Subscriptions and consumers:

- consumer signup-page — initial_load=initial-load:signup-open; update=publication:contract-written
- consumer card-detail — initial_load=initial-load:signup-open; update=publication:contract-written

### flow:auto-topup-status-manage

- Data domains: wallet-auto-topup-contract
- External contracts: contract:getAutoTopupStatus, contract:updateAutoTopupContract, contract:cancelAutoTopupContract
- Logical contracts: contract:getAutoTopupStatus
- Development owner: view:development/node:auto-topup-repository
- Source of truth: authority=contract:getAutoTopupStatus; persistence=view:development/node:auto-topup-repository; projections=view:runtime/node:contract-cache; reconciliation=端侧缓存缺失以云侧查询为准；云侧查询失败时状态未知，不以缓存缺失推断未签约；写入结果即时刷新缓存
- Initial load: id=manage-open; strategy=进入管理页时查询状态; owner=view:development/node:auto-topup-repository; freshness=每次进入管理页刷新
- State owner: view:runtime/node:contract-cache; states=无签约, 生效中, 停用
- Recovery: id=manage-failure; persistence=改档/关闭失败留在管理页并提示；回滚不适用，解约不回滚进行中订单; subscription=无订阅; process=缓存缺失以云侧查询为准（管理页重查）；查询失败显示状态未知可重试，不推断未签约
- Evidence: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md, doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- Verification: doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md

Triggers:

- user_action — timing=进入管理页/改档/关闭/查看停用; idempotency=以「卡片+生效状态」判重，已有生效签约返回既有 contractNo

Mutations and publications:

- mutation update-contract-mutation — persistence=view:development/node:auto-topup-repository; publication=publication:manage-state-written; recovery=recovery:manage-failure
- mutation cancel-contract-mutation — persistence=view:development/node:auto-topup-repository; publication=publication:manage-state-written; recovery=recovery:manage-failure
- publication manage-state-written — snapshot=管理页与详情页展示新的签约状态/门限面额

Subscriptions and consumers:

- consumer manage-page — initial_load=initial-load:manage-open; update=publication:manage-state-written
- consumer card-detail-state — initial_load=initial-load:manage-open; update=publication:manage-state-written

## Authority contracts

### getAutoTopupPolicy

- Owner: WalletMain; needed by: slice:ar90006-all
- Operation: getAutoTopupPolicy 1.0 (outbound); source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/operations/getAutoTopupPolicy
- Request DTO: AutoTopupPolicyRequest; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyRequest
  - accountId: string; required=true; nullable=false; semantics=去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyRequest/fields/0
  - cardId: string; required=true; nullable=false; semantics=卡片标识; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyRequest/fields/1
- Response DTO: AutoTopupPolicyResponse; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse
  - signable: boolean; required=true; nullable=false; semantics=是否可签约; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/0
  - unsignableReason: string; required=true; nullable=true; semantics=不可签约的原因（如未实名），可签约时为空; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/1
  - thresholdOptions: int[]; required=true; nullable=false; semantics=门限档位; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/2
  - amountOptions: int[]; required=true; nullable=false; semantics=面额档位; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/3
  - dailyLimit: int; required=true; nullable=false; semantics=单日限额; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/4
  - agreementText: string; required=true; nullable=false; semantics=协议文案; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/AutoTopupPolicyResponse/fields/5
- Mappings:
  - policy-req-account (direct): accountId → 钱包端账号标识（来自登录态）; rule=直取当前登录的去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-req-account
  - policy-req-card (direct): cardId → 当前详情页卡片标识; rule=直取当前交通卡卡片标识; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-req-card
  - policy-resp-signable (direct): signable → 可签约性状态; rule=控制入口显示与可点; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-signable
  - policy-resp-unsignableReason (direct): unsignableReason → 不可签约原因; rule=用于实名引导提示文案; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-unsignableReason
  - policy-resp-thresholdOptions (direct): thresholdOptions → 门限档位列表; rule=签约页单选数据源; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-thresholdOptions
  - policy-resp-amountOptions (direct): amountOptions → 面额档位列表; rule=签约页单选数据源; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-amountOptions
  - policy-resp-dailyLimit (direct): dailyLimit → 单日限额; rule=展示与协议文案引用; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-dailyLimit
  - policy-resp-agreementText (direct): agreementText → 协议文案; rule=签约页展示；协议文案写明单日最多充 200 元，由云侧文案带入（D11：v1.1 的 300 不采纳）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/policy-resp-agreementText
- Errors: 卡云统一错误结构（错误码 + 可读信息），本需求不新增错误码
- Idempotency: 只读查询，天然幂等
- NFR: ["金额一律以「分」为单位的整数","createAutoTopupContract 失败或超时的协议号复用时限待卡云与支付对齐（会议 T6，见蓝图 gap agreement-retry）"]

### createAutoTopupContract

- Owner: WalletMain; needed by: slice:ar90006-all
- Operation: createAutoTopupContract 1.0 (outbound); source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/operations/createAutoTopupContract
- Request DTO: CreateAutoTopupContractRequest; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest
  - accountId: string; required=true; nullable=false; semantics=去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest/fields/0
  - cardId: string; required=true; nullable=false; semantics=卡片标识; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest/fields/1
  - agreementNo: string; required=true; nullable=false; semantics=支付部件返回的协议号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest/fields/2
  - threshold: int; required=true; nullable=false; semantics=触发门限; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest/fields/3
  - amount: int; required=true; nullable=false; semantics=单笔充值面额; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractRequest/fields/4
- Response DTO: CreateAutoTopupContractResponse; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractResponse
  - contractNo: string; required=true; nullable=false; semantics=签约号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractResponse/fields/0
  - existed: boolean; required=true; nullable=false; semantics=是否为既有生效签约（true 时没有新建）; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CreateAutoTopupContractResponse/fields/1
- Mappings:
  - create-req-account (direct): accountId → 钱包端账号标识; rule=直取当前登录去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-req-account
  - create-req-card (direct): cardId → 当前卡片标识; rule=直取当前交通卡; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-req-card
  - create-req-agreementNo (direct): agreementNo → 免密协议号（仅透传，不持久化）; rule=支付部件验证返回的协议号原样透传; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-req-agreementNo
  - create-req-threshold (direct): threshold → 触发门限; rule=签约页所选门限（分）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-req-threshold
  - create-req-amount (direct): amount → 单笔面额; rule=签约页所选面额（分）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-req-amount
  - create-resp-contractNo (direct): contractNo → wallet_auto_topup_contract.contractNo; rule=缓存签约号，用于后续状态查询与解约; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-resp-contractNo
  - create-resp-existed (direct): existed → 转管理页判定; rule=existed=true 时入口与管理页分流，不重复建约; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/create-resp-existed
- Errors: 卡云统一错误结构（错误码 + 可读信息），本需求不新增错误码
- Idempotency: 创建签约以「卡片 + 生效状态」判重，已有生效签约返回既有 contractNo
- NFR: ["金额一律以「分」为单位的整数","createAutoTopupContract 失败或超时的协议号复用时限待卡云与支付对齐（会议 T6，见蓝图 gap agreement-retry）"]

### getAutoTopupStatus

- Owner: WalletMain; needed by: slice:ar90006-all
- Operation: getAutoTopupStatus 1.0 (outbound); source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/operations/getAutoTopupStatus
- Request DTO: GetAutoTopupStatusRequest; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusRequest
  - accountId: string; required=true; nullable=false; semantics=去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusRequest/fields/0
  - cardId: string; required=true; nullable=false; semantics=卡片标识; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusRequest/fields/1
- Response DTO: GetAutoTopupStatusResponse; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse
  - contractStatus: string; required=true; nullable=false; semantics=none / active / disabled; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/0
  - contractNo: string; required=true; nullable=true; semantics=未签约时为空; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/1
  - threshold: int; required=true; nullable=true; semantics=当前门限，未签约时为空; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/2
  - amount: int; required=true; nullable=true; semantics=当前面额，未签约时为空; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/3
  - recentRecords: object[]; required=true; nullable=false; semantics=最近记录，可为空列表；每项含 time、amount、result; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/4
  - consecutiveFailures: int; required=true; nullable=false; semantics=连续扣款失败次数; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/5
  - disabledReason: string; required=true; nullable=true; semantics=停用原因，未停用时为空; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/GetAutoTopupStatusResponse/fields/6
- Mappings:
  - status-req-account (direct): accountId → 钱包端账号标识; rule=直取登录去标识账号; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-req-account
  - status-req-card (direct): cardId → 当前卡片标识; rule=直取当前交通卡; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-req-card
  - status-resp-contractStatus (direct): contractStatus → 签约状态（none/active/disabled）; rule=管理页顶部状态与入口分流依据; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-contractStatus
  - status-resp-contractNo (direct): contractNo → wallet_auto_topup_contract.contractNo; rule=状态查询回填缓存签约号（可为空）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-contractNo
  - status-resp-threshold (direct): threshold → 当前门限; rule=管理页展示（可为空）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-threshold
  - status-resp-amount (direct): amount → 当前面额; rule=管理页展示（可为空）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-amount
  - status-resp-recentRecords (direct): recentRecords → 最近充值记录列表; rule=管理页记录区（每项 time/amount/result），卡号按现有规则脱敏; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-recentRecords
  - status-resp-consecutiveFailures (direct): consecutiveFailures → 连续失败次数; rule=管理页展示; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-consecutiveFailures
  - status-resp-disabledReason (direct): disabledReason → 停用原因; rule=停用态横幅展示（可为空）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/status-resp-disabledReason
- Errors: 卡云统一错误结构（错误码 + 可读信息），本需求不新增错误码
- Idempotency: 只读查询，天然幂等
- NFR: ["金额一律以「分」为单位的整数","createAutoTopupContract 失败或超时的协议号复用时限待卡云与支付对齐（会议 T6，见蓝图 gap agreement-retry）"]

### cancelAutoTopupContract

- Owner: WalletMain; needed by: slice:ar90006-all
- Operation: cancelAutoTopupContract 1.0 (outbound); source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/operations/cancelAutoTopupContract
- Request DTO: CancelAutoTopupContractRequest; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CancelAutoTopupContractRequest
  - contractNo: string; required=true; nullable=false; semantics=签约号; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CancelAutoTopupContractRequest/fields/0
- Response DTO: CancelAutoTopupContractResponse; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CancelAutoTopupContractResponse
  - cancelled: boolean; required=true; nullable=false; semantics=是否已解约; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/CancelAutoTopupContractResponse/fields/0
- Mappings:
  - cancel-req-contractNo (direct): contractNo → 签约号; rule=从缓存或状态查询取得后透传; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/cancel-req-contractNo
  - cancel-resp-cancelled (direct): cancelled → 关闭结果; rule=关闭成功后在管理页/详情页更新状态，清理缓存; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/cancel-resp-cancelled
- Errors: 卡云统一错误结构（错误码 + 可读信息），本需求不新增错误码
- Idempotency: 解约不回滚进行中的订单；重复解约幂等返回已解约结果
- NFR: ["金额一律以「分」为单位的整数","createAutoTopupContract 失败或超时的协议号复用时限待卡云与支付对齐（会议 T6，见蓝图 gap agreement-retry）"]

### updateAutoTopupContract

- Owner: WalletMain; needed by: slice:ar90006-all
- Operation: updateAutoTopupContract 1.0 (outbound); source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/operations/updateAutoTopupContract
- Request DTO: UpdateAutoTopupContractRequest; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractRequest
  - contractNo: string; required=true; nullable=false; semantics=签约号（会议 T1：原签约关系不断）; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractRequest/fields/0
  - threshold: int; required=true; nullable=false; semantics=触发门限（改动值）; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractRequest/fields/1
  - amount: int; required=true; nullable=false; semantics=单笔充值面额（改动值）; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractRequest/fields/2
- Response DTO: UpdateAutoTopupContractResponse; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractResponse
  - updated: boolean; required=true; nullable=false; semantics=是否已更新（字段为待定占位，细节由卡云定稿；见蓝图 gap update-response）; source=doc/features/bp-AR90006/blueprint/contracts/se-interfaces.yaml#/dtos/UpdateAutoTopupContractResponse/fields/0
- Mappings:
  - update-req-contractNo (direct): contractNo → 签约号（原签约关系不断）; rule=会议 T1：改门限/面额走 update 不重签; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/update-req-contractNo
  - update-req-threshold (direct): threshold → 新门限; rule=管理页改门限后的值（分）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/update-req-threshold
  - update-req-amount (direct): amount → 新面额; rule=管理页改面额后的值（分）；面额调高是否需重验待定（会议 T2）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/update-req-amount
  - update-resp-updated (direct): updated → 更新结果; rule=更新成功后在管理页刷新状态；字段待卡云定稿（见蓝图 gap update-response）; source=doc/features/bp-AR90006/blueprint/contracts/mappings.yaml#/mappings/update-resp-updated
- Errors: 卡云统一错误结构（错误码 + 可读信息），本需求不新增错误码
- Idempotency: 按 contractNo 更新门限面额，原签约关系不断；重复提交按目标值收敛
- NFR: ["金额一律以「分」为单位的整数","createAutoTopupContract 失败或超时的协议号复用时限待卡云与支付对齐（会议 T6，见蓝图 gap agreement-retry）"]

## Cross-view relations

- rel-signup-scenario-to-flow: view:scenarios/node:scenario-signup-success → view:runtime/flow:flow:auto-topup-signup-bind (scenario_depends_on); owner=WalletMain; verification=view:runtime/flow:flow:auto-topup-signup-bind
- rel-signup-scenario-to-page: view:scenarios/node:scenario-signup-success → view:development/node:auto-topup-signup-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-signup-page
- rel-manage-scenario-to-flow: view:scenarios/node:scenario-update-and-cancel → view:runtime/flow:flow:auto-topup-status-manage (scenario_depends_on); owner=WalletMain; verification=view:runtime/flow:flow:auto-topup-status-manage
- rel-manage-scenario-to-page: view:scenarios/node:scenario-update-and-cancel → view:development/node:auto-topup-manage-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-manage-page
- rel-entry-to-signup-flow: view:development/node:auto-topup-entry-builder → view:logical/node:signup-flow (directs_to); owner=WalletMain; verification=view:logical/node:signup-flow
- rel-entry-to-manage-flow: view:development/node:auto-topup-entry-builder → view:logical/node:manage-flow (directs_to); owner=WalletMain; verification=view:logical/node:manage-flow
- rel-repo-to-contract-status: view:development/node:auto-topup-repository → contract:getAutoTopupStatus (calls_contract); owner=WalletMain; verification=contract:getAutoTopupStatus
- rel-repo-to-contract-policy: view:development/node:auto-topup-repository → contract:getAutoTopupPolicy (calls_contract); owner=WalletMain; verification=contract:getAutoTopupPolicy
- rel-repo-to-contract-create: view:development/node:auto-topup-repository → contract:createAutoTopupContract (calls_contract); owner=WalletMain; verification=contract:createAutoTopupContract
- rel-repo-to-contract-update: view:development/node:auto-topup-repository → contract:updateAutoTopupContract (calls_contract); owner=WalletMain; verification=contract:updateAutoTopupContract
- rel-repo-to-contract-cancel: view:development/node:auto-topup-repository → contract:cancelAutoTopupContract (calls_contract); owner=WalletMain; verification=contract:cancelAutoTopupContract
- rel-unauth-scenario-to-page: view:scenarios/node:scenario-unauth-guide → view:development/node:auto-topup-entry-builder (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-entry-builder
- rel-verify-cancel-to-page: view:scenarios/node:scenario-verify-cancel-resume → view:development/node:auto-topup-signup-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-signup-page
- rel-reentry-to-entry: view:scenarios/node:scenario-signed-reentry → view:development/node:auto-topup-entry-builder (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-entry-builder
- rel-switchoff-to-entry: view:scenarios/node:scenario-switch-off-signed → view:development/node:auto-topup-entry-builder (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-entry-builder
- rel-disabled-to-manage: view:scenarios/node:scenario-disabled-restart → view:development/node:auto-topup-manage-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-manage-page
- rel-mask-to-manage: view:scenarios/node:scenario-record-mask → view:development/node:auto-topup-manage-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-manage-page
- rel-exit-to-signup-page: view:scenarios/node:scenario-exit-resume → view:development/node:auto-topup-signup-page (scenario_owned_by); owner=WalletMain; verification=view:development/node:auto-topup-signup-page

## Independent questioning

- Provider: independent-questioner; status=pending; isolated=true; writes_ssot=false
- view:logical [answered_with_evidence]: logical 视图与上游是否一致 — 概念与链路视图（contract-concept/signup-flow/manage-flow/entry-control）与冻结上游一致；入口可见性矩阵按 T3（未实名可见引导实名）与 T4（开关只管新签约）细分，开关不折叠进 signable; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- view:runtime [answered_with_evidence]: runtime 视图与缓存语义是否一致 — 运行时数据流与 SR 缓存语义一致；wallet_auto_topup_contract 按账号隔离、退出登录清除、不数据备份、仅免网展示；缓存 freshness 与首帧免网展示在实现层合并理解; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- flow:flow:auto-topup-signup-bind [answered_with_evidence]: 签约流程语义与材料是否一致 — 签约流程触发器/判重（卡片+生效状态）/失败恢复与 SR、RR 一致；埋点流程级判断成立；统计点逐点明细交 plan 承接; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- flow:flow:auto-topup-status-manage [answered_with_evidence]: 管理流程语义与材料是否一致 — 管理流程 authority（状态查询）与 reconciliation（缓存缺失以云侧为准）一致；update 响应 updated 字段登记为设计者推断并挂 blocker gap（未决项2/14）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- view:development [answered_with_evidence]: development 视图与模块归属是否一致 — 五个开发节点全部归 WalletMain，AutoTopupRepository 五方法对应五契约；签约页档位以 thresholdOptions/amountOptions 为数据源不硬编码；SEC-01 落点成立但脱敏卡号来源待澄清（未决项7）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- view:scenarios [answered_with_evidence]: 场景视图与验收意图是否对齐 — 9 个场景逐条对齐 AC-R1..R9 与会议 T1/T3/T4；AC-R2 云侧自动充值语义不端侧主测；relation 现已补全场景与契约调用关系; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-signup-scenario-to-flow [answered_with_evidence]: relation rel-signup-scenario-to-flow 关系是否真实 — 签约成功场景依赖签约流程（入口→选额→验证→创建→显示已开启），与 SR 签约路径一致; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-signup-scenario-to-page [answered_with_evidence]: relation rel-signup-scenario-to-page 关系是否真实 — 签约成功验收落在签约页执行面，owner 与 execution owner 一致; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-manage-scenario-to-flow [answered_with_evidence]: relation rel-manage-scenario-to-flow 关系是否真实 — 改档（update 原关系不断）与关闭（cancel）均由管理 flow 承接; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-manage-scenario-to-page [answered_with_evidence]: relation rel-manage-scenario-to-page 关系是否真实 — 管理页为改档/关闭/停用重签实现承载; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-entry-to-signup-flow [answered_with_evidence]: relation rel-entry-to-signup-flow 关系是否真实 — 未签约且可签约/未实名用户由入口进入签约（含实名引导回跳）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-entry-to-manage-flow [answered_with_evidence]: relation rel-entry-to-manage-flow 关系是否真实 — 已签约再进入与开关关闭后已签约不隐藏均经入口分流到管理页; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-repo-to-contract-status [answered_with_evidence]: relation rel-repo-to-contract-status 关系是否真实 — AutoTopupRepository.getStatus 调 getAutoTopupStatus; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-repo-to-contract-policy [answered_with_evidence]: relation rel-repo-to-contract-policy 关系是否真实 — AutoTopupRepository.getPolicy 调 getAutoTopupPolicy; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-repo-to-contract-create [answered_with_evidence]: relation rel-repo-to-contract-create 关系是否真实 — AutoTopupRepository.createContract 调 createAutoTopupContract; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-repo-to-contract-update [answered_with_evidence]: relation rel-repo-to-contract-update 关系是否真实 — AutoTopupRepository.updateContract 调 updateAutoTopupContract（会议 T1 新增）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-repo-to-contract-cancel [answered_with_evidence]: relation rel-repo-to-contract-cancel 关系是否真实 — AutoTopupRepository.cancelContract 调 cancelAutoTopupContract; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-unauth-scenario-to-page [answered_with_evidence]: relation rel-unauth-scenario-to-page 关系是否真实 — 未实名引导场景由入口 builder 承载（T3 修订 AC-R1）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-verify-cancel-to-page [answered_with_evidence]: relation rel-verify-cancel-to-page 关系是否真实 — 验证取消保留选择场景落在签约页; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-reentry-to-entry [answered_with_evidence]: relation rel-reentry-to-entry 关系是否真实 — 已签约再进入（AC-R9，existed 分流）由入口 builder 承载; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-switchoff-to-entry [answered_with_evidence]: relation rel-switchoff-to-entry 关系是否真实 — 开关关闭后已签约入口不隐藏（T4）由入口 builder 承载; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-disabled-to-manage [answered_with_evidence]: relation rel-disabled-to-manage 关系是否真实 — 停用态查看与重签场景落在管理页; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-mask-to-manage [answered_with_evidence]: relation rel-mask-to-manage 关系是否真实 — 记录脱敏展示（AC-R5）落在管理页记录区; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- relation:rel-exit-to-signup-page [answered_with_evidence]: relation rel-exit-to-signup-page 关系是否真实 — 中途退出保留选择（情形表）落在签约页; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:module_boundaries [answered_with_evidence]: App lens 根问题 module_boundaries — 签约/管理链路整体落在 WalletMain，无跨模块新边界；支付验证/实名属外部能力接缝; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:capability_seams [answered_with_evidence]: App lens 根问题 capability_seams — 免密验证拉起支付部件、实名取账号能力、五接口落 AutoTopupRepository；agreementNo 仅透传不持久化; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:feature_flags [answered_with_evidence]: App lens 根问题 feature_flags — 运营开关经 getAutoTopupPolicy 返回；开关只影响未签约入口，已签约用户持续显示（与未实名可见以 signable/unsignableReason 区分）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:data_producers_consumers [answered_with_evidence]: App lens 根问题 data_producers_consumers — 生产者=卡云接口，消费者=入口/签约页/管理页/详情页；缓存供免网展示与两条 flow 消费者吻合; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:lifecycle_triggers [answered_with_evidence]: App lens 根问题 lifecycle_triggers — 入口进入加载策略、管理页进入查状态、改档/关闭由用户动作触发，均为低频用户动作时机; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:state_owners [answered_with_evidence]: App lens 根问题 state_owners — 缓存 owner、卡云权威（SR §3）；领域态为 none/active/disabled，瞬态（免密验证中）移出契约状态集; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:initialization [answered_with_evidence]: App lens 根问题 initialization — 缓存键退出登录清除、暂存仅本账号本卡、入口显示按策略与状态决定；实名回跳清暂存; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:publication_subscription [answered_with_evidence]: App lens 根问题 publication_subscription — 无全局订阅；跨页刷新机制（AppStorage 键或返回刷新）由 plan 定（未决项10）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:ui_refresh [answered_with_evidence]: App lens 根问题 ui_refresh — 首帧缓存免网展示、云侧返回后刷新、失败/取消保留选择，均符合 SR; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- app_lens:process_recovery [answered_with_evidence]: App lens 根问题 process_recovery — 进程重建后缓存按账号本地存在、缺失以云侧查询为准；清除数据后按云侧查询恢复，云侧确认无签约才引导签约（ENV-01）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/SR/design.md
- terminology:current_scope_items [open_decision]: 需求输入点是否闭环、新术语是否登记 — 13 个 requirement item 全部经 requirement_traceability 闭环到蓝图对象；新业务术语（自动充值/触发门限/单笔面额/免密协议号/生效签约/停用）本仓 glossary 未登记，由 catalog-bootstrap 补登（未决项13）; owner=independent-questioner; evidence=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md; verification=doc/features/AR90006/AR/story-src/inputs/12f4a1ea6739330b0a9ae5a0036e2097e0516d64d913c48389859ae9462d230f/files/RR/prd.md

## Admission

- Status: blocker
- Root questions complete: false
- Current slice: slice:ar90006-all; contracts_ready=true; design_refs_ready=true; controlled_fakes=[]
- Blockers: —

## Decisions and gaps

- decision scope-human-1: decided_with_authority; owner=钱包产品组; verification=view:development/node:auto-topup-manage-page
- decision knowledge-sec-01: answered_with_evidence; owner=design-author; verification=view:scenarios/node:scenario-record-mask, view:development/node:auto-topup-manage-page
- decision knowledge-ux-01: answered_with_evidence; owner=design-author; verification=view:development/node:auto-topup-signup-page, view:development/node:auto-topup-manage-page
- decision knowledge-dfx-01: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-status-manage, view:runtime/node:contract-cache
- decision knowledge-dfx-02: not_applicable; owner=design-author; verification=view:development/node:auto-topup-signup-page, view:development/node:auto-topup-manage-page
- decision knowledge-obs-02: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind, view:runtime/flow:flow:auto-topup-status-manage
- decision knowledge-obs-03: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind, view:runtime/flow:flow:auto-topup-status-manage
- decision knowledge-obs-05: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind, view:runtime/flow:flow:auto-topup-status-manage
- decision knowledge-obs-06: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind, view:runtime/flow:flow:auto-topup-status-manage
- decision knowledge-obs-07: not_applicable; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind
- decision knowledge-res-01: answered_with_evidence; owner=design-author; verification=view:development/node:auto-topup-signup-page, view:development/node:auto-topup-manage-page
- decision knowledge-res-02: answered_with_evidence; owner=design-author; verification=view:development/node:auto-topup-signup-page, view:development/node:auto-topup-manage-page
- decision knowledge-compat-01: answered_with_evidence; owner=design-author; verification=contract:updateAutoTopupContract
- decision knowledge-compat-02: not_applicable; owner=design-author; verification=contract:getAutoTopupPolicy
- decision knowledge-env-01: answered_with_evidence; owner=design-author; verification=view:runtime/node:contract-cache
- decision knowledge-env-02: answered_with_evidence; owner=design-author; verification=view:runtime/flow:flow:auto-topup-signup-bind, view:runtime/flow:flow:auto-topup-status-manage
- decision knowledge-dlv-01: answered_with_evidence; owner=design-author; verification=view:development/node:auto-topup-signup-page, view:development/node:auto-topup-manage-page
- decision knowledge-dlv-02: not_applicable; owner=design-author; verification=view:development/node:auto-topup-entry-builder
- decision pending-amount-verify: open_decision; owner=支付侧（刘洋/风控）; verification=view:development/node:auto-topup-manage-page, gap:gap-amount-verify
- decision pending-agreement-retry: open_decision; owner=支付侧（陈静/刘洋）; verification=view:runtime/flow:flow:auto-topup-signup-bind, gap:gap-agreement-retry
- gap gap-update-response: blocker; owner=交通卡云; needed_by=slice:ar90006-all; unlock=卡云定稿 updateAutoTopupContract 的响应字段后解除；在此之前 Updated 字段为占位、后续契约升版
- gap gap-agreement-retry: blocker; owner=支付侧（陈静/刘洋）; needed_by=slice:ar90006-all; unlock=卡云与支付对齐协议号有效期、复用规则与端侧再次尝试的方式后解除（会议 T6）
- gap gap-amount-verify: blocker; owner=支付侧（刘洋/风控）; needed_by=slice:ar90006-all; unlock=支付侧与风控确认面额调整（调高、调低）是否需要重新免密验证后解除（会议 T2）
- gap gap-component-assets: open_decision; owner=design-author; needed_by=slice:ar90006-b; unlock=本仓建立 component-index 后做共享 UI 资产选型；当前页面属专题页，缺口留远期

> Derived projection only. The canonical YAML remains the machine SSOT.
