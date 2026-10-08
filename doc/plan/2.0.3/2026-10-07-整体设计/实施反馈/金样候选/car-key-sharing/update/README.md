# car-key-sharing/update 候选：来源与语义差异

> 情景终点：承接评审人在 Review 人工区的表态。宽限窗那条意见与「车辆侧撤销即拒绝」冲突，按 update 规则登记为待确认议题 D6，停下问人。实跑没有跑到这一段，没有人的回答，所以本候选是**停在 D6 的待裁定候选**。
> 状态：**待裁定候选**。以 [reviewable 候选](../reviewable/README.md)为起点，蓝图未改动、仍未准入。这份候选不是正式金样。

## 1. 阅读入口

| 读什么 | 打开 |
|---|---|
| Story、Review、设计附件 | `output/story/2.0.3-p1-candidates/car-key-sharing/update/doc/features/ISSUE-206/AR/` 下的 `story.md`、`review.md`、`design-review.md` |
| 本轮记录 | 本目录 `AR/story-src/updates/候选-评审回流/update-notes.md` |

导出时核两件事：人读三件与蓝图跟本目录逐字节相同；19 个本地链接全部可达。

## 2. 生成方式

| 步骤 | 做法 |
|---|---|
| 起点 | reviewable 候选的工作区 `ck-review` 复制为 `ck-update` |
| 评审表态 | 用测试域现成的 `run_case._write_review_zones` 把 `test/cases/car-key-sharing/update-inputs/car-review-feedback.yaml` 写进 Review 人工区：D1 需修改（36 小时那句），D2 暂缓 |
| 修订 | `revise_ck_update.py`：登记 D6（open，选择题，建议按卡片收回期限理解）；业务方案与验收的撤销宽限处各补一句指向 D6。经 `chapter` 提交、`build` 渲染 Review、`number` 编号 |
| 没做 | 没有开流程轮次（`update --action prepare`），没有跑 `decide`（见 §4） |

## 3. 语义差异（相对 reviewable 候选）

| 项 | reviewable | update 候选 | 依据 |
|---|---|---|---|
| D1 人工区 | 空 | 需修改，原话照录 | 评审输入 |
| D2 人工区 | 空 | 暂缓，原话照录 | 评审输入 |
| D6 | 无 | 新登记：36 小时指卡片收回期限还是车辆侧仍认钥匙，两边来源并列 | 系统设计状态机一节、产品稿「失效前车辆侧就要拒绝」与评审原话冲突 |
| 正文 | 宽限待对齐 | 补一句：评审人提出 36 小时，含义待确认（D6），确认前不改方案 | 同上 |

保持不变的部分：D1 正文（评审人已对它表态，改了渲染会拦下）、D2–D5、蓝图、状态机与车辆侧拒绝的口径。

## 4. 交给设计者的问题

1. 材料关卡要记一次人的回答，这一段只有交互脚本预置的「不补」。我没有开流程轮次，也没有记 `decide`，update 记录作为候选文件交出。待裁定的 update 候选是否应当这样交？还是应当用标明为测试输入的方式把轮次开起来？
2. 车钥匙用例的两条「暂缓」意见本来分别针对再转分享和强制下线，但 reviewable 的 D2 把两件事合成了一条议题，于是两条意见都落在 D2 上。用例的投放说明写的是「每条的词只命中一条议题」，现在两条命中的是同一条议题。要不要把 D2 拆成两条议题？
