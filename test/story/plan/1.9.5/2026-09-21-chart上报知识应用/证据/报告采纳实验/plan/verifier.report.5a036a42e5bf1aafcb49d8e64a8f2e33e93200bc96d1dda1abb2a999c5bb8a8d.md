# Plan 阶段语义验证报告 — ISSUE-206（数字车钥匙分享·钱包端）· update 复审

## 汇总表（12 项 = 10 项语义检查 + 2 项知识判据检查 per hook）

| id | status | severity | 证据（一行） |
|---|---|---|---|
| five_layer_compliance | PASS | BLOCKER | 架构图 Phone(01)→WalletMain(02)→AccountManager(04)/CommUI/CommFunc(05)，满足 can_depend_on，无逆向、无新模块 |
| module_internal_layer_compliance | PASS | BLOCKER | 新文件全落在 shared/data/model/api/repository/presentation；index.ets 出口；Phone 仅改既有 shell |
| module_minimality | PASS | MAJOR | 未新增模块；CommFunc/AccountManager/CommUI 只消费不改的排除原因在 Scope rationale |
| feature_split_accuracy | PASS | MAJOR | F1-F14 全映射 WalletMain，层级与职责匹配，无业务下沉基座 |
| data_type_legality | PASS | BLOCKER | 全部 string/number/boolean/\|null/枚举 KeySharingState，无 any；DTO 均定义 |
| no_tbd_in_p0_p1 | PASS | BLOCKER | 无 TBD/TODO；「D-3 open 接真实云待联调」为决策状态非设计未决 |
| architecture_doc_consistency | PASS | MAJOR | impact=none，feature 级不要求对齐 architecture.md |
| navigation_flow_consistency | PASS | MAJOR | 路由与 spec 5.1/5.2 逐条对应；注册名一致 |
| acceptance_to_interface | PASS | MAJOR | AC 全有模型/接口/组件/常量支撑（REVOKE_GRACE_HOURS=36、REVOKING_PROMPT=正在收回）|
| reference_crosscheck | PASS | MAJOR | AC/BD、contracts 实体、六接口名、复用入口均核到原文与磁盘 |
| knowledge_obligation_substance | WARN | MAJOR | OBS-01/02/03 义务锚点在 plan 义务表(components)与 contracts(repository 接口)间漂移；其余义务逐条实质落地 |
| knowledge_facts_reuse | PASS | MAJOR | 7 类新增能力 5 复用+2 未复用均给可回查理由，无登记矛盾 |

## YAML 明细（status ≠ PASS 项 + hook 追加两条）

```yaml
verification_result:
  phase: "plan"
  feature: "ISSUE-206"
  timestamp: "2026-09-21T06:15:23.192Z"
  checks:
    - id: knowledge_obligation_substance
      status: WARN
      severity: MAJOR
      details: |
        OBS-01/02/03 在 contracts.yaml 挂在 interfaces.KeySharingRepository.createShare/revokeShare/
        queryShareList（contracts.yaml:206-247），而 plan.md 规约义务表把三者落点实体写成
        components.KeySharingSetupFlow / components.KeySharingManagePage、承载章写「页面组件树」。
        设计本体不缺（服务层接口定义章与方法签名齐全、页面组件树含两节点），义务要求的行为在三条链路
        均有对应步骤，业务可走通。但义务挂载真源（contracts=repository 接口）与 plan 义务表
        （components）不一致，会给 coding 造成"日志写在哪层"歧义。其余义务逐条核过无问题。
      suggestion: |
        plan.md 义务表 OBS-01/02/03 落点实体改为 interfaces.KeySharingRepository.createShare/
        revokeShare/queryShareList，与 contracts.yaml 一致；或在 contracts 另挂 components 实体——
        两处锚点名必须一致。属 plan 阶段产物修正，不阻塞闭环。
    - id: knowledge_facts_reuse
      status: PASS
      severity: MAJOR
      details: |
        7 类新增能力对照登记入口核：脱敏→MaskUtil.ets、日志/事件/Chart→Logger+WalletHAManager、
        登录态→AccountService、UI→ActionListItem/showToast/SectionCard、开关→HomeConstants 均磁盘实存；
        六接口未复用（端侧无网络出口→mock）、草稿用 AppStorage（preferences/distributedKVStore 未用）
        均给可回查理由。
  summary:
    total: 12
    pass: 11
    fail: 0
    warn: 1
    blockers: 0
    verdict: PASS
```

<!-- maison-verifier-result:v1 -->
verifier_subject_id: 5a036a42e5bf1aafcb49d8e64a8f2e33e93200bc96d1dda1abb2a999c5bb8a8d
verdict: PASS
blocker_count: 0
<!-- /maison-verifier-result:v1 -->
