# 可测性预检 — home-page

> 自动生成/维护以通过 `ut_testability_audit_present`；模板见 `framework/profiles/hmos-app/skills/5-business-ut/templates/testability-audit-template.md`。

```yaml
schema_version: "1.0"
feature: home-page
records:
  - acceptance_id: AC-1
    entry_point:
      symbol: HomeRepository.getServiceEntries
      file: 02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets
    testability_level: L1
    dependencies:
      - name: HomeRepository
        kind: pure
        seam: none
    verdict: testable
  - acceptance_id: AC-2
    entry_point:
      symbol: HomeRepository.getPromoList
      file: 02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets
    testability_level: L1
    dependencies:
      - name: HomeRepository
        kind: pure
        seam: none
    verdict: testable
```
