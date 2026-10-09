# car-key-sharing/update

- 情景终点：承接评审人在 Review 人工区的表态，更新 Story、Review 与受影响的已有 Spec、Plan。
- 目标产物：`AR/story.md`、`AR/review.md`；`sharing-wallet-slice/spec/spec.md`、`sharing-wallet-slice/plan/plan.md`；`assets/` 配图。
- 输入：`test/cases/car-key-sharing`（基底 `15844e09`；交互脚本 10-09 补立场后为 `0d48bdfea52c1989`，`case.yaml` 为 `720a0293704355c6`，评审回稿 `ebbad8571f846f95`，记账见 `test/EVOLUTION.md` §7）。目标工程 demo 与知识取 `15844e09`。
- 有效宿主立场：评审预置输入 `car-review-feedback.yaml`（D1 需修改：36 小时、「仍可开门」、提示语「正在收回」；D2、D6 暂缓）；`update-material`（不补）；`grace-window-conflict`（车辆侧撤销即拒绝不变，36 小时是卡片收回期限）。
- 设计选择：「仍可开门」与安全口径冲突，登记 D8 问需求方后定案；D1 改为 36 小时卡片收回、被分享人一侧提示「正在收回」；车云接口宽限值仍是 48，要由车云调整，调整前联调口径不一致。
- 这是期望结果：人的回答取自 Case 设计的宿主立场，是构造预期的输入，不是已发生的人签；它不证明产品已能产出这份结果。
