---
derived_from:
  artifact: component-blueprint@1
  component_id: WalletMain
  blueprint_id: bp-ISSUE-206
  revision: 2
  source_fingerprint: sha256:1747e9ad44080128d278b178bb6670d6b7f27f25b18776e4c48ef3061ab4b6f6
  artifact_sha256: sha256:1c4aadb3d773726bc130fb15d4dd4893e99d75771d7b3643eaf47b5801a52ffc
projection: component-blueprint-review@1
---

# 数字车钥匙分享（钱包端）— 部件演进蓝图

钱包端（WalletMain）承载数字车钥匙分享的端侧链路：车主发起分享（对象/权限/有效期三要素、配额、草稿续办）、被分享人接受、双方状态管理与撤销。分享关系真源在车云、钥匙可用性裁决在车厂云，钱包端只做端侧 UI、端云调用、草稿与状态展示，不裁决钥匙可用性。本演进新增四个页面与一个数据服务，全部落在 WalletMain（02-Feature）。

## Design views

### logical

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 定义车钥匙分享的领域对象：分享关系与六态、对象权限档位、发起草稿与分享功能开关；划定对车云开放接口的领域消费边界。
- Stakeholders: 产品经理, 设计, 开发
- Current: 车钥匙仅为 AddCardEntryPage 中一个不可点分类 c4（CardRepository.getCardCategories 写死返回，点击 toast 暂不支持），无分享领域对象、无端云分享接口调用。
- Target: 建立钱包端分享领域：分享状态六态（待接受/生效/已作废/已到期/撤销中/已撤销）、对象与车辆关系的权限档位、发起草稿（联系人/权限/有效期/幂等标识）、分享功能开关。真源在车云，端侧只投影状态。
- Delta: 新增分享领域对象与端云分享接口消费边界；端侧不裁决钥匙可用性。
- Decisions/gaps: decision:atomic-share-rollback, decision:privacy-masking
- Verification: doc/features/ISSUE-206/SR/design.md, doc/features/ISSUE-206/RR/prd.md, doc/module-catalog.yaml

Nodes:

- share-domain — owner=design-author; current=无分享领域模型; target=分享关系领域对象：ShareRequest（vehicleId/granteeId/permissionLevel/validUntil/idempotencyKey）、ShareStatus 六态映射；真源在车云; basis=—; verification=doc/features/ISSUE-206/SR/design.md
- grantee-permission-domain — owner=design-author; current=权限档位只在车云判定，端侧不建模; target=queryGranteePermission 结果：shareable/permissionLevels/reason；换对象重查; basis=—; verification=doc/features/ISSUE-206/SR/design.md
- draft-domain — owner=design-author; current=无草稿概念; target=发起草稿领域对象（联系人、权限档位、有效期、幂等标识）；成功即清、按账号隔离; basis=—; verification=doc/features/ISSUE-206/SR/design.md
- feature-flag — owner=design-author; current=无分享功能开关; target=分享功能开关（默认关闭随版本放开）；关闭后不能发起新分享、已生效分享不受影响; basis=—; verification=doc/features/ISSUE-206/SR/design.md

### runtime

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 闭合分享状态读取与写入两条数据流：管理列表/配额每次进页从云端拉取、创建/接受/撤销写车云并经消息推送刷新，发起草稿本地续办，账号切换清草稿。
- Stakeholders: 开发, 测试, 运维
- Current: 无分享数据流：不分列表、无草稿、无写操作；车钥匙分类点击只 toast。
- Target: KeySharingRepository 封装六个端云接口调用；管理页/设置页按 vehicleId 拉取状态与配额；后台无分享关系写入；草稿 key_sharing_draft 本地存取、成功即清、按账号隔离。
- Delta: 新增分享状态读取流与分享写入流；端侧不缓存分享列表、不打堆本地真源。
- Decisions/gaps: decision:atomic-share-rollback
- Verification: doc/features/ISSUE-206/SR/design.md, 02-Feature/WalletMain/src/main/ets/data/repository/CardRepository.ets

Nodes:

- share-repository — owner=design-author; current=无分享 Repository（CardRepository 仅写死返回卡分类）; target=KeySharingRepository：六个端云接口的调用封装（配额/权限/创建/接受/撤销/列表），返回脱敏视图; basis=view:logical/node:share-domain; verification=doc/features/ISSUE-206/SR/design.md
- share-manage-view — owner=design-author; current=无分享状态展示; target=管理列表与钥匙卡片的六态投影；不做本地缓存，断网给网络失败态; basis=view:logical/node:share-domain; verification=doc/features/ISSUE-206/SR/design.md
- share-draft-store — owner=design-author; current=无本地草稿存储; target=key_sharing_draft 存发起草稿；中途退出/断网回来续办、成功即清、按账号隔离、退出登录清除; basis=view:logical/node:draft-domain; verification=doc/features/ISSUE-206/SR/design.md
- share-accept-processor — owner=design-author; current=无接受侧实现; target=接受页进入 → acceptKeySharing 触发下发凭据；失败保持待接受可重试；添加后卡片详情显示权限与有效期、权限外功能不出现; basis=view:logical/node:share-domain; verification=doc/features/ISSUE-206/SR/design.md

### development

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 分配分享端侧实现的模块归属与组件形态：四个页面与一个数据服务全部落在 WalletMain，复用 CommUI 可复用组件与 CommFunc 脱敏/日志/导航。
- Stakeholders: 开发, 测试
- Current: WalletMain 仅 HomeTabPage/MineTabPage/CardPackPage/AddCardEntryPage 四个页面；车钥匙只是 AddCardEntryPage 里不可点的 c4 分类；无 domain 层。
- Target: WalletMain 新增分享数据服务（KeySharingRepository + 草稿存储）与四个页面（分享设置、分享管理、接受页、钥匙卡片详情）及分享入口门槛；跨模块只经各模块 index.ets。
- Delta: 新增开发节点 share-data-service、share-setup-page、share-manage-page、share-accept-page、key-card-detail-page、share-entry；模块均为 WalletMain。
- Decisions/gaps: decision:atomic-share-rollback
- Verification: 02-Feature/WalletMain/src/main/ets/index.ets, doc/module-catalog.yaml, framework.config.json

Nodes:

- share-entry — owner=design-author; current=本工程没有车钥匙卡片：车钥匙只是添加卡片页里不可点的分类，分享入口没有可挂载的宿主页面; target=卡包车钥匙卡片上的分享入口；未登录或没有车钥匙的用户看不到（AC-K9）；功能开关关闭时不能发起新分享; basis=view:logical/node:feature-flag; verification=doc/features/ISSUE-206/RR/prd.md
- car-key-card — owner=design-author; current=卡包页没有车钥匙卡片的展示; target=卡包里展示车钥匙卡片：车主本人的钥匙（来源见 gap:owner-key-source）与接受成功的钥匙；卡片承载分享入口与钥匙卡片详情的入口; basis=view:logical/node:feature-flag; verification=doc/features/ISSUE-206/RR/prd.md
- share-setup-page — owner=design-author; current=无分享设置页; target=分享设置页三段：给谁/权限/有效期；先选对象权限区才确定；三项选好「发出」可点；满额置灰给原因；可复用 MaisonNavBar/MaisonPrimaryButton/MaisonSelector; basis=view:logical/node:grantee-permission-domain; verification=doc/features/ISSUE-206/RR/prd.md
- share-manage-page — owner=design-author; current=无分享管理页; target=分享管理页顶部车辆+剩余可分享数，列表逐条对象/权限/有效期/状态，可单独撤销；不缓存、断网给网络失败态; basis=view:runtime/node:share-manage-view; verification=doc/features/ISSUE-206/RR/prd.md
- share-accept-page — owner=design-author; current=无接受侧页面; target=接受页车辆信息卡（车型/车主昵称/权限/有效期）+「添加到钱包」；不设拒绝按钮，72 小时未接受作废; basis=view:runtime/node:share-accept-processor; verification=doc/features/ISSUE-206/ux-reference/README.md
- key-card-detail-page — owner=design-author; current=无钥匙卡片详情; target=添加后钥匙卡片进入钱包卡包，详情显示权限范围与有效期；权限之外功能不出现、不置灰; basis=view:runtime/node:share-accept-processor; verification=doc/features/ISSUE-206/ux-reference/README.md
- share-data-service — owner=design-author; current=无分享 Repository 与草稿存储; target=KeySharingRepository（六接口封装）+ key_sharing_draft 草稿存储（按账号隔离、成功即清）+ 分享功能开关常量; basis=view:runtime/node:share-repository, view:runtime/node:share-draft-store; verification=doc/features/ISSUE-206/SR/design.md

### deployment

- Applicability: not_applicable
- Evolution impact: —
- Unchanged evidence: —
- Purpose: 裁决本次演进是否触及部署拓扑。
- Stakeholders: 架构, 运维
- Current: 单进程 HAP 应用，无独立部署拆分。
- Target: 无部署变化。
- Delta: none
- Decisions/gaps: —
- Verification: framework.config.json

Nodes:

- None (evidence-backed not applicable view).

### scenarios

- Applicability: applicable
- Evolution impact: changed
- Unchanged evidence: —
- Purpose: 将两个用户可见旅程与设计视图与实现 owner 绑定：车主发起分享并管理与撤销；被分享人接受并查看卡片。
- Stakeholders: 产品经理, 开发, 测试
- Current: 无分享旅程（车钥匙分类不可点）。
- Target: 车主旅程（发出→待接受→管理→撤销）与被分享人旅程（推送→接受页→添加→卡片详情）可按设计视图追踪到实现。
- Delta: 新增 owner-share-journey 与 grantee-accept-journey 两个场景，并补齐跨视图追踪。
- Decisions/gaps: —
- Verification: doc/features/ISSUE-206/RR/prd.md, doc/features/ISSUE-206/ux-reference/README.md

Nodes:

- owner-share-journey — owner=design-author; current=车主无法发起分享; target=车主在车钥匙卡点分享 → 设置页（对象/权限/有效期）→ 发出 → 待接受 → 管理/撤销完整旅程；72 小时未接受作废可重发; basis=—; verification=doc/features/ISSUE-206/RR/prd.md
- grantee-accept-journey — owner=design-author; current=被分享人无接受入口; target=收推送 → 接受页车辆信息卡 → 添加到钱包 → 卡片详情显示权限与有效期、权限外功能不出现; basis=—; verification=doc/features/ISSUE-206/ux-reference/README.md

## Runtime data flows

### share-status-flow

- Data domains: data-domain:sharing-status
- External contracts: contract:query-key-sharing-list-v1, contract:query-key-sharing-quota-v1
- Logical contracts: contract:query-key-sharing-list-v1, contract:query-key-sharing-quota-v1
- Development owner: view:development/node:share-manage-page
- Source of truth: authority=view:runtime/node:share-repository; persistence=server:car-cloud（端侧不持久化分享列表）; projections=view:runtime/node:share-manage-view; reconciliation=每次进页按 vehicleId 拉取列表与配额，不落地缓存；断网给网络失败态；推送失败由对方主动打开钱包补拉
- Initial load: id=share-list; strategy=进页拉取列表与配额; owner=design-author; freshness=每次进页拉取
- State owner: view:runtime/node:share-repository; states=share-list, remaining-quota
- Recovery: id=recovery:share-list-reload; persistence=无本地持久化，恢复到进页拉取; subscription=断网显示网络失败态，回网重进重拉; process=进程重建后按进页路径重拉
- Evidence: doc/features/ISSUE-206/SR/design.md, 02-Feature/WalletMain/src/main/ets/data/repository/CardRepository.ets
- Verification: doc/features/ISSUE-206/SR/design.md

Triggers:

- page_enter — timing=on-enter; idempotency=每次进页一次 queryKeySharingList/Quota，重复进入替换投影
- remote_notify — timing=on-push; idempotency=推送到达补拉列表，失败不改变分享关系

Mutations and publications:


Subscriptions and consumers:

- consumer manage-page — initial_load=initial-load:share-list; update=—

### share-mutate-flow

- Data domains: data-domain:sharing-mutation, data-domain:sharing-draft
- External contracts: contract:create-key-sharing-v1, contract:accept-key-sharing-v1, contract:revoke-key-sharing-v1
- Logical contracts: contract:create-key-sharing-v1, contract:accept-key-sharing-v1, contract:revoke-key-sharing-v1
- Development owner: view:development/node:share-data-service
- Source of truth: authority=view:runtime/node:share-repository; persistence=key_sharing_draft; projections=view:runtime/node:share-manage-view; reconciliation=创建/接受/撤销结果以车云响应为准；一成一败必须回滚；撤销发起即车辆侧拒绝、宽限窗只影响对方卡片消失时间
- Initial load: id=share-draft; strategy=进分享设置页读草稿续办; owner=design-author; freshness=进入时读取，发起成功即清除
- State owner: view:runtime/node:share-draft-store; states=draft, pending, active, revoked, revoking
- Recovery: id=share-mutate-recover; persistence=起草中失败保留草稿可续办，成功即清；签发失败可重试、凭据下发失败保持待接受; subscription=撤销离线进入撤销中，宽限窗内回网即失效；车辆侧拒绝自撤销发起生效; process=进程重建后恢复草稿或按进页路径重拉
- Evidence: doc/features/ISSUE-206/SR/design.md
- Verification: doc/features/ISSUE-206/SR/design.md

Triggers:

- user_mutation — timing=on-submit; idempotency=createKeySharing 使用 idempotencyKey，重复请求返回同一条分享
- account_switch — timing=on-account-switch; idempotency=草稿按账号隔离，切换即清、不跨账号带出

Mutations and publications:

- mutation mutate-create — persistence=key_sharing_draft; publication=publication:share-status; recovery=recovery:share-mutate-recover
- mutation mutate-accept — persistence=—; publication=publication:share-status; recovery=recovery:share-mutate-recover
- mutation mutate-revoke — persistence=—; publication=publication:share-status; recovery=recovery:share-mutate-recover
- publication share-status — snapshot=最新分享状态，供管理页/接受侧刷新

Subscriptions and consumers:

- subscription subscription:manage-refresh — consumer=consumer:manage-mutate-update; attach=页挂载后订阅; detach=页卸载取消; cleanup=移除通知回调; replay=取最新分享状态列表; ordering=到达顺序
- consumer manage-mutate-update — initial_load=initial-load:share-draft; update=publication:share-status

## Authority contracts

### query-key-sharing-quota-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: queryKeySharingQuota 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/queryKeySharingQuota
- Request DTO: QueryKeySharingQuotaRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaRequest
  - vehicleId: string; required=true; nullable=false; semantics=车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaRequest/fields/0
- Response DTO: QueryKeySharingQuotaResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaResponse
  - canShare: boolean; required=true; nullable=false; semantics=是否还能发起分享; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaResponse/fields/0
  - remaining: integer; required=true; nullable=false; semantics=剩余可分享数; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaResponse/fields/1
  - reason: string; required=false; nullable=true; semantics=满额时的可读原因，可为空; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaResponse/fields/2
  - shares: list; required=true; nullable=false; semantics=现有分享清单摘要；每项含 shareId（字符串）与 status（字符串）; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingQuotaResponse/fields/3
- Mappings:
  - quota-vehicleId (direct): vehicleId → KeySharingQuotaQuery.vehicleId; rule=透传车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/quota-vehicleId
  - quota-canShare (direct): canShare → KeySharingQuotaView.canShare; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/quota-canShare
  - quota-remaining (direct): remaining → KeySharingQuotaView.remaining; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/quota-remaining
  - quota-reason (direct): reason → KeySharingQuotaView.reason; rule=透传，可为空; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/quota-reason
  - quota-shares (direct): shares → KeySharingQuotaView.shares; rule=摘要列表原样承接（shareId/status 透传）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/quota-shares
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 查询接口无写副作用，重复调用幂等；进页时调用
- NFR: {"freshness":"每次进页拉取，不落地缓存","retry":"接口失败提示可重试"}

### query-grantee-permission-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: queryGranteePermission 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/queryGranteePermission
- Request DTO: QueryGranteePermissionRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionRequest
  - vehicleId: string; required=true; nullable=false; semantics=车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionRequest/fields/0
  - granteeId: string; required=true; nullable=false; semantics=对方账号标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionRequest/fields/1
- Response DTO: QueryGranteePermissionResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionResponse
  - shareable: boolean; required=true; nullable=false; semantics=对象是否可分享; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionResponse/fields/0
  - permissionLevels: list; required=true; nullable=false; semantics=可用权限档位列表；不可分享时为空列表; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionResponse/fields/1
  - reason: string; required=false; nullable=true; semantics=不可分享原因，可为空; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryGranteePermissionResponse/fields/2
- Mappings:
  - permission-vehicleId (direct): vehicleId → GrantPermissionQuery.vehicleId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/permission-vehicleId
  - permission-granteeId (direct): granteeId → GrantPermissionQuery.granteeId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/permission-granteeId
  - permission-shareable (direct): shareable → GrantPermissionView.shareable; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/permission-shareable
  - permission-levels (direct): permissionLevels → GrantPermissionView.permissionLevels; rule=档位列表原样承接; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/permission-levels
  - permission-reason (direct): reason → GrantPermissionView.reason; rule=透传，可为空; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/permission-reason
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 查询接口无写副作用，重复调用幂等；换对象重查以最近一次结果为准
- NFR: {"freshness":"选定对象后调用，换对象重查","retry":"接口失败提示可重试"}

### create-key-sharing-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: createKeySharing 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/createKeySharing
- Request DTO: CreateKeySharingRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest
  - vehicleId: string; required=true; nullable=false; semantics=车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest/fields/0
  - granteeId: string; required=true; nullable=false; semantics=对方账号标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest/fields/1
  - permissionLevel: string; required=true; nullable=false; semantics=权限档位; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest/fields/2
  - validUntil: datetime; required=true; nullable=false; semantics=有效期（ISO 8601 时间）; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest/fields/3
  - idempotencyKey: string; required=true; nullable=false; semantics=幂等标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingRequest/fields/4
- Response DTO: CreateKeySharingResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingResponse
  - shareId: string; required=true; nullable=false; semantics=分享标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingResponse/fields/0
  - status: string; required=true; nullable=false; semantics=固定为 pending; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/CreateKeySharingResponse/fields/1
- Mappings:
  - create-vehicleId (direct): vehicleId → ShareDraft.vehicleId; rule=草稿记录车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-vehicleId
  - create-granteeId (direct): granteeId → ShareDraft.granteeId; rule=草稿记录对方账号; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-granteeId
  - create-permissionLevel (direct): permissionLevel → ShareDraft.permissionLevel; rule=草稿记录权限档位; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-permissionLevel
  - create-validUntil (direct): validUntil → ShareDraft.validUntil; rule=草稿记录有效期; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-validUntil
  - create-idempotencyKey (direct): idempotencyKey → ShareDraft.idempotencyKey; rule=草稿记录幂等标识，续办沿用，成功即清; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-idempotencyKey
  - create-shareId (direct): shareId → ShareCreated.shareId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-shareId
  - create-status (direct): status → ShareCreated.status; rule=透传（期望 pending）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/create-status
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 同一幂等标识重复请求返回同一条分享，不重复建立；车厂云签发失败时本接口失败且不留关系
- NFR: {"idempotency":"idempotencyKey 全程保持","atomic":"车厂云签发失败即回滚，不留半生效状态","retry":"失败提示可重试"}

### accept-key-sharing-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: acceptKeySharing 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/acceptKeySharing
- Request DTO: AcceptKeySharingRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/AcceptKeySharingRequest
  - shareId: string; required=true; nullable=false; semantics=分享标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/AcceptKeySharingRequest/fields/0
- Response DTO: AcceptKeySharingResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/AcceptKeySharingResponse
  - credentialStatus: string; required=true; nullable=false; semantics=issued / failed; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/AcceptKeySharingResponse/fields/0
  - status: string; required=true; nullable=false; semantics=active / pending; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/AcceptKeySharingResponse/fields/1
- Mappings:
  - accept-shareId (direct): shareId → AcceptShareQuery.shareId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/accept-shareId
  - accept-credentialStatus (direct): credentialStatus → AcceptShareResult.credentialStatus; rule=透传（issued/failed）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/accept-credentialStatus
  - accept-status (direct): status → AcceptShareResult.status; rule=透传（active/pending）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/accept-status
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 凭据下发失败保持待接受，可重试；重试不产生新分享
- NFR: {"retry":"凭据下发失败保持待接受，可重试","atomic":"不改变分享关系"}

### revoke-key-sharing-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: revokeKeySharing 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/revokeKeySharing
- Request DTO: RevokeKeySharingRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/RevokeKeySharingRequest
  - shareId: string; required=true; nullable=false; semantics=分享标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/RevokeKeySharingRequest/fields/0
- Response DTO: RevokeKeySharingResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/RevokeKeySharingResponse
  - status: string; required=true; nullable=false; semantics=revoked / revoking; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/RevokeKeySharingResponse/fields/0
  - graceHours: integer; required=false; nullable=true; semantics=revoking 时为 48; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/RevokeKeySharingResponse/fields/1
- Mappings:
  - revoke-shareId (direct): shareId → RevokeShareQuery.shareId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/revoke-shareId
  - revoke-status (direct): status → RevokeShareResult.status; rule=透传（revoked/revoking）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/revoke-status
  - revoke-graceHours (direct): graceHours → RevokeShareResult.graceHours; rule=透传，可为空；revoking 时为 48; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/revoke-graceHours
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 撤销以首次结果为准，重复请求返回当前状态；车辆侧自撤销发起即拒绝
- NFR: {"atomic":"车辆侧拒绝自撤销发起即生效","timing":"对方离线宽限窗 48 小时"}

### query-key-sharing-list-v1

- Owner: 车云开放接口负责人; needed by: slice-bp-issue-206
- Operation: queryKeySharingList 2.1 (client-to-server); source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/operations/queryKeySharingList
- Request DTO: QueryKeySharingListRequest; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingListRequest
  - vehicleId: string; required=true; nullable=false; semantics=车辆标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingListRequest/fields/0
- Response DTO: QueryKeySharingListResponse; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingListResponse
  - items: list; required=true; nullable=false; semantics=每条分享的状态、权限、有效期与对方脱敏标识; source=doc/features/bp-ISSUE-206/blueprint/contracts/se-interfaces.yaml#/dtos/QueryKeySharingListResponse/fields/0
- Mappings:
  - list-vehicleId (direct): vehicleId → ShareListQuery.vehicleId; rule=透传; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/list-vehicleId
  - list-items (direct): items → ShareListView.items; rule=列表原样承接（shareId/status/permissionLevel/validUntil/granteeMasked）; source=doc/features/bp-ISSUE-206/blueprint/contracts/mappings.yaml#/mappings/list-items
- Errors: {"car_cloud_error":"车云错误码与可读信息，本需求不新增错误码"}
- Idempotency: 查询接口无写副作用，每次进页拉取
- NFR: {"freshness":"每次进页拉取，不落地缓存","retry":"断网给网络失败态"}

## Cross-view relations

- share-setup-consumes-repo: view:development/node:share-setup-page → view:runtime/node:share-repository (calls_data); owner=design-author; verification=doc/features/ISSUE-206/SR/design.md
- share-manage-consumes-repo: view:development/node:share-manage-page → view:runtime/node:share-repository (calls_data); owner=design-author; verification=doc/features/ISSUE-206/SR/design.md
- share-repo-uses-draft: view:runtime/node:share-repository → view:runtime/node:share-draft-store (reads_writes); owner=design-author; verification=doc/features/ISSUE-206/SR/design.md
- share-accept-consumes-processor: view:development/node:share-accept-page → view:runtime/node:share-accept-processor (calls_data); owner=design-author; verification=doc/features/ISSUE-206/ux-reference/README.md
- share-domain-implemented: view:logical/node:share-domain → view:runtime/node:share-repository (implemented_by); owner=design-author; verification=doc/features/ISSUE-206/SR/design.md

## Independent questioning

- Provider: isolated-reviewer-subagent; status=pending; isolated=true; writes_ssot=false
- view:logical [answered_with_evidence]: 逻辑视图是否由当前材料支持且 delta 明确 — 逻辑视图由 SR/PRD 支持且 delta 明确：新增 share-domain/grantee-permission-domain/draft-domain/feature-flag 四节点、六态与权限档位映射，verification_refs 均指向 design.md 与 prd.md。; owner=design-author; evidence=doc/features/ISSUE-206/SR/design.md, doc/features/ISSUE-206/RR/prd.md, doc/module-catalog.yaml; verification=doc/features/ISSUE-206/SR/design.md, doc/features/ISSUE-206/RR/prd.md, doc/module-catalog.yaml
- view:runtime [answered_with_evidence]: 运行时数据闭环（读取/写入/草稿）是否闭合到 state owner、发布订阅与恢复 — 两条 flow 各自闭合到 state owner：status-flow 每次进页拉取、不缓存、state_owner=share-repository、恢复=进页重拉；mutate-flow 三个突变发布到 publication:share-status、subscription 页挂载/卸载 attach/detach、恢复=草稿续办+宽限窗。; owner=design-author; evidence=doc/features/ISSUE-206/SR/design.md, view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow; verification=doc/features/ISSUE-206/SR/design.md, view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- view:development [answered_with_evidence]: 开发视图模块归属与组件形态是否一致 — 四页一服务一入口（share-entry 为 component 形态）全部声明 module=WalletMain，跨模块只经 index.ets；组件形态与模块归属一致，且复用 CommUI/CommFunc 已在 purpose/delta 写明。; owner=design-author; evidence=doc/module-catalog.yaml; verification=doc/module-catalog.yaml
- view:scenarios [answered_with_evidence]: 两个用户旅程是否可追踪到逻辑/运行时/开发视图 — owner-share-journey 与 grantee-accept-journey 均显式带 logical_refs/runtime_refs/development_owner_ref，可追踪到逻辑/运行时/开发节点。; owner=design-author; evidence=doc/features/ISSUE-206/RR/prd.md, doc/features/ISSUE-206/ux-reference/README.md; verification=doc/features/ISSUE-206/RR/prd.md, doc/features/ISSUE-206/ux-reference/README.md
- flow:share-status-flow [answered_with_evidence]: 状态读取流是否闭合生命周期、幂等与恢复 — 生命周期七类已闭合：page_enter/remote_notify 触发器带幂等（重复进入替换投影），冷启/回温/挂载/卸载/切账号/进程重建均 covered，background_write 标 not_applicable；恢复=无本地持久化则进页重拉。; owner=design-author; evidence=doc/features/ISSUE-206/SR/design.md, contract:query-key-sharing-list-v1; verification=doc/features/ISSUE-206/SR/design.md, contract:query-key-sharing-list-v1
- flow:share-mutate-flow [answered_with_evidence]: 写入流是否闭合 mutation→publication→subscription→consumer 与失败恢复 — mutation(create/accept/revoke)→publication:share-status→subscription:manage-refresh→consumer:manage-mutate-update 闭环；恢复=起草失败留草稿/成功即清/签发失败可重试/离线撤销进撤销中宽限窗内回网失效；account_switch 触发清草稿。; owner=design-author; evidence=doc/features/ISSUE-206/SR/design.md, contract:create-key-sharing-v1; verification=doc/features/ISSUE-206/SR/design.md, contract:create-key-sharing-v1
- relation:share-setup-consumes-repo [answered_with_evidence]: 关系 share-setup-consumes-repo 的端点是否都在本演进内且关系类型成立？ — 端点均在演进内（share-setup-page → share-repository），calls_data 类型与两端语义一致。; owner=design-author; evidence=view:development/node:share-setup-page, view:runtime/node:share-repository; verification=view:development/node:share-setup-page, view:runtime/node:share-repository
- relation:share-manage-consumes-repo [answered_with_evidence]: 关系 share-manage-consumes-repo 的端点是否都在本演进内且关系类型成立？ — 端点均在演进内（share-manage-page → share-repository），calls_data 类型与两端语义一致。; owner=design-author; evidence=view:development/node:share-manage-page, view:runtime/node:share-repository; verification=view:development/node:share-manage-page, view:runtime/node:share-repository
- relation:share-repo-uses-draft [answered_with_evidence]: 关系 share-repo-uses-draft 的端点是否都在本演进内且关系类型成立？ — 端点均在演进内（share-repository → share-draft-store），reads_writes 类型与两端语义一致。; owner=design-author; evidence=view:runtime/node:share-repository, view:runtime/node:share-draft-store; verification=view:runtime/node:share-repository, view:runtime/node:share-draft-store
- relation:share-accept-consumes-processor [answered_with_evidence]: 关系 share-accept-consumes-processor 的端点是否都在本演进内且关系类型成立？ — 端点均在演进内（share-accept-page → share-accept-processor），calls_data 类型与两端语义一致。; owner=design-author; evidence=view:development/node:share-accept-page, view:runtime/node:share-accept-processor; verification=view:development/node:share-accept-page, view:runtime/node:share-accept-processor
- relation:share-domain-implemented [answered_with_evidence]: 关系 share-domain-implemented 的端点是否都在本演进内且关系类型成立？ — 端点均在演进内（share-domain → share-repository），implemented_by 类型与两端语义一致。; owner=design-author; evidence=view:logical/node:share-domain, view:runtime/node:share-repository; verification=view:logical/node:share-domain, view:runtime/node:share-repository
- app_lens:module_boundaries [answered_with_evidence]: App lens 根问题 模块边界是否明确，跨模块只经 index.ets 是否以证据回答？ — 分享实现全部落在 WalletMain（02-Feature），跨模块只经 index.ets；账号域复用 AccountManager，脱敏/日志/导航复用 CommFunc; owner=design-author; evidence=doc/module-catalog.yaml, framework.config.json; verification=doc/module-catalog.yaml, framework.config.json
- app_lens:capability_seams [answered_with_evidence]: App lens 根问题 端云能力接缝是否单一入口封装 是否以证据回答？ — 端云接口经 KeySharingRepository 单一入口封装；对外不暴露除钱包 UI 之外的 seam; owner=design-author; evidence=contract:create-key-sharing-v1, contract:query-key-sharing-list-v1; verification=contract:create-key-sharing-v1, contract:query-key-sharing-list-v1
- app_lens:feature_flags [answered_with_evidence]: App lens 根问题 分享功能开关是否纳入演进 是否以证据回答？ — 分享功能开关（默认关闭随版本放开），关闭后不能发起新分享、已生效分享不受影响；配置落 WalletMain 常量; owner=design-author; evidence=view:logical/node:feature-flag; verification=view:logical/node:feature-flag
- app_lens:data_producers_consumers [answered_with_evidence]: App lens 根问题 分享数据产生者与消费者是否明确 是否以证据回答？ — 车云 produce 分享状态；KeySharingRepository consume 并投影到管理页/接受页；草稿 key_sharing_draft 仅端侧使用; owner=design-author; evidence=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- app_lens:lifecycle_triggers [answered_with_evidence]: App lens 根问题 六类生命周期触发是否逐条评估 是否以证据回答？ — 六类触发条件逐条评估：列表拉取/page_enter、写操作/on-submit、账号切换、进程重建均已在 flow 中闭合; owner=design-author; evidence=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- app_lens:state_owners [answered_with_evidence]: App lens 根问题 分享状态与草稿的 owner 是否无歧义 是否以证据回答？ — 分享状态真源在车云，端侧 share-repository 为投影 owner；草稿状态 owner 为 share-draft-store；状态 owner 无歧义; owner=design-author; evidence=view:runtime/node:share-repository, view:runtime/node:share-draft-store; verification=view:runtime/node:share-repository, view:runtime/node:share-draft-store
- app_lens:initialization [answered_with_evidence]: App lens 根问题 初始化（冷启动/进页/草稿续办）是否显式 是否以证据回答？ — 冷启动按进页路径拉取列表；设置页读草稿续办；初始化不落堆本地列表缓存; owner=design-author; evidence=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- app_lens:publication_subscription [answered_with_evidence]: App lens 根问题 发布订阅是否闭合到各消费方 是否以证据回答？ — share-mutate-flow 内 publication:share-status 经 subscription 通知管理/接受侧刷新；订阅在页挂载/卸载时 attach/detach/cleanup; owner=design-author; evidence=view:runtime/flow:share-mutate-flow; verification=view:runtime/flow:share-mutate-flow
- app_lens:ui_refresh [answered_with_evidence]: App lens 根问题 UI 刷新时机与失败态是否确定性 是否以证据回答？ — 管理页列表每次进页拉取、不缓存；断网给网络失败态；刷新确定性由进页路径与失败态保证; owner=design-author; evidence=view:runtime/flow:share-status-flow; verification=view:runtime/flow:share-status-flow
- app_lens:process_recovery [answered_with_evidence]: App lens 根问题 进程重建恢复路径是否闭合 是否以证据回答？ — 进程重建后：分享列表按进页路径重拉；发起草稿从 key_sharing_draft 恢复续办; owner=design-author; evidence=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- terminology:current_scope_items [answered_with_evidence]: 当前范围引用的业务名词是否都有术语事实且映射合理？ — 车钥匙分享/权限档位/分享状态映射到 WalletMain（medium、记录为 headless_assumed）；部件画像与工程能力已登记为 facts，语义无歧义。; owner=design-author; evidence=doc/glossary.yaml, doc/extensions/knowledge/facts/component-profile.md; verification=doc/glossary.yaml, doc/extensions/knowledge/facts/component-profile.md

## Admission

- Status: blocker
- Root questions complete: false
- Current slice: slice-bp-issue-206; contracts_ready=true; design_refs_ready=true; controlled_fakes=[]
- Blockers: —

## Decisions and gaps

- decision knowledge-ux-01: answered_with_evidence; owner=design-author; verification=view:development/node:share-setup-page, view:development/node:share-manage-page, view:development/node:share-accept-page, view:development/node:key-card-detail-page
- decision knowledge-sec-01: answered_with_evidence; owner=design-author; verification=view:runtime/node:share-repository, view:logical/node:share-domain, view:development/node:share-data-service
- decision knowledge-dfx-01: answered_with_evidence; owner=design-author; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- decision knowledge-dfx-02: not_applicable; owner=design-author; verification=view:development/node:share-setup-page
- decision knowledge-obs-02: answered_with_evidence; owner=design-author; verification=view:runtime/flow:share-status-flow, view:runtime/flow:share-mutate-flow
- decision knowledge-obs-03: answered_with_evidence; owner=design-author; verification=view:runtime/flow:share-mutate-flow
- decision knowledge-obs-05: answered_with_evidence; owner=design-author; verification=view:development/node:share-data-service
- decision knowledge-obs-06: answered_with_evidence; owner=design-author; verification=view:development/node:share-data-service
- decision knowledge-obs-07: not_applicable; owner=design-author; verification=—
- decision knowledge-res-01: answered_with_evidence; owner=design-author; verification=view:development/node:share-setup-page, view:development/node:share-manage-page
- decision knowledge-res-02: answered_with_evidence; owner=design-author; verification=view:development/node:share-setup-page, view:development/node:share-manage-page, view:development/node:share-accept-page
- decision knowledge-compat-01: answered_with_evidence; owner=design-author; verification=contract:query-key-sharing-quota-v1, contract:query-grantee-permission-v1, contract:create-key-sharing-v1, contract:accept-key-sharing-v1, contract:revoke-key-sharing-v1, contract:query-key-sharing-list-v1
- decision knowledge-compat-02: not_applicable; owner=design-author; verification=—
- decision knowledge-env-01: answered_with_evidence; owner=design-author; verification=view:runtime/node:share-draft-store, view:runtime/flow:share-mutate-flow
- decision knowledge-env-02: answered_with_evidence; owner=design-author; verification=view:runtime/flow:share-mutate-flow, view:development/node:share-entry
- decision knowledge-dlv-01: answered_with_evidence; owner=design-author; verification=view:development/node:share-setup-page, view:development/node:share-manage-page, view:development/node:share-accept-page
- decision knowledge-dlv-02: not_applicable; owner=design-author; verification=—
- decision atomic-share-rollback: answered_with_evidence; owner=design-author; verification=contract:create-key-sharing-v1
- decision revoke-grace-window-drift: decided_with_authority; owner=需求负责人; verification=contract:revoke-key-sharing-v1
- decision privacy-masking: answered_with_evidence; owner=design-author; verification=view:runtime/node:share-repository
- decision share-undecided-ahead: open_decision; owner=需求负责人; verification=contract:create-key-sharing-v1, contract:revoke-key-sharing-v1
- decision share-force-offline-undecided: open_decision; owner=需求负责人; verification=contract:create-key-sharing-v1, contract:revoke-key-sharing-v1
- decision scope-carry-all: decided_with_authority; owner=需求负责人; verification=view:logical/node:share-domain
- decision share-entry-host: decided_with_authority; owner=出行产品组; verification=view:development/node:share-entry, view:development/node:key-card-detail-page
- gap share-undecided-policy: open_decision; owner=需求负责人; needed_by=slice:policy-review-future; unlock=安全评审与车厂协商给出确定性结论后，决定是否承载再转发与强制下线
- gap component-asset-curation-future: open_decision; owner=design-author; needed_by=slice:component-assets-future; unlock=建立 doc/component-index.yaml / component-catalog.yaml 后可完成共享 UI 组件选型；当前共享组件选型不可评估
- gap grace-hours-alignment: blocker; owner=车云; needed_by=slice:grace-hours-alignment; unlock=车云把 revokeKeySharing 的 graceHours 从 48 调整为 36 并更新接口约定；之前钱包端按 36 小时展示，与车云联调返回值不一致
- gap owner-key-source: blocker; owner=出行产品组; needed_by=slice:owner-key-source; unlock=确认卡包里车主本人车钥匙的车辆标识与钥匙信息由谁提供、经哪个接口取得（议题 D8）；之后施工单位才能把车钥匙卡片与分享入口接到真实数据

> Derived projection only. The canonical YAML remains the machine SSOT.
