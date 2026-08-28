# Verifier 报告

## 逐行裁决

| 编号 | 裁决 | 引文 |
|---|---|---|
| SMP-01 | 设计 | 受理单编号在提交入口生成一次 |
| SMP-02 | 设计 | 上报失败只记本地日志，不阻断主流程 |

verification_result:
  checks:
    - id: knowledge_spec_exit_substance
      status: PASS
      details: 逐行裁决见上表，2 行全部有结论
