# car-key-sharing/plan-ready

- 情景终点：交付门选实现方案，施工单位做到 Plan 为止。
- 目标产物：`AR/story.md`、`AR/review.md`（同 reviewable）；施工单位 `sharing-wallet-slice/spec/spec.md`、`sharing-wallet-slice/plan/plan.md`；`assets/` 配图。
- 输入：`test/cases/car-key-sharing`（基底 `15844e09`；交互脚本 10-09 补立场后为 `0d48bdfea52c1989`，`case.yaml` 为 `720a0293704355c6`，评审回稿 `ebbad8571f846f95`，记账见 `test/EVOLUTION.md` §7）。目标工程 demo 与知识取 `15844e09`。
- 有效宿主立场：同 reviewable。
- 设计选择：一个施工单位承担全部钱包端改动；修改范围是 WalletMain 与 Phone（Phone 只加页面映射）；卡包页嵌入车钥匙卡片分区；数据经一个分享数据源接口取得，本单元提供模拟实现；草稿要扛过应用关闭，工程里没有现成的持久化封装，在草稿存储里用系统轻量键值存储、按账号分键。换一种合理的类名、文件划分或施工单位划分，不算错。被分享人一侧按账号查收到的分享，六个车云接口里没有对应接口，同样由模拟数据源提供，真实接口另列依赖；撤销只对生效的分享提供。
- Spec、Plan 头部的「已闭环」是目标情景终点的示例状态，不代表实际完成，也不附原生回执或质询记录。
- 这是期望结果：人的回答取自 Case 设计的宿主立场，是构造预期的输入，不是已发生的人签；它不证明产品已能产出这份结果。
