# test/golden：两组金样正本

金样是用户审定过的**目标效果**：拿被测产物与它并排看，需求是否完整准确、关系是否清楚、形式是否适合、责任与交付是否可判断。
它给人对照效果，不当判据的机器否决锚；判据对错按真实依据与中性正反例判。

## 两组正本

| 组 | 情景终点 | 正文 | 配套 |
|---|---|---|---|
| [auto-topup](auto-topup/README.md)：AR90006 交通卡自动充值 | Spec | `AR/story.md`、`AR/review.md`、`spec/spec.md` | 3 份 Mermaid 图源 `AR/story-src/figures/`、综合阅读图 `AR/figures/auto-topup-recovery-boundary.svg`、5 张界面参考图 `ux-reference/` |
| [car-key-sharing](car-key-sharing/README.md)：ISSUE-206 数字车钥匙分享 | Plan | `AR/story.md`、`AR/review.md`、`spec/spec.md`、`plan/plan.md` | 3 份 Mermaid 图源、综合阅读图 `AR/figures/car-key-revocation-responsibility.svg`、4 张界面参考图 |

各组 README 写输入来源、宿主立场、设计选择、维护设计细化与模拟建设前提、保留的未决，以及 Story 里产品形态链接到仓内权威输入的对照。

## 审定状态

- 2026-10-17 用户认可整组及模拟前提，原话与审定对象见 [06 审定记录](../../doc/plan/1.9.9/2026-10-17-R3页面交互金样修订/06-审定记录与迁移交接.md)，逐文件身份见 [05 最终审定清单](../../doc/plan/1.9.9/2026-10-17-R3页面交互金样修订/05-最终审定清单.md)。
- 业务未决保持待定：自动充值 D3（改面额是否重新验证）、D4（授权后未建成怎样再次开启）、D8（关闭交互），以及停用重签在开关关闭时的边界；车钥匙 D2（再转第三人）、D5（极端断网强制下线）、D8（待接受撤回）。Review 人工区为空，金样获认可不等于需求方已裁定这些问题。
- 自动充值改门限的控件、车钥匙自定义有效期的日期控件材料没有给，金样只到行为级，不是控件或像素规格。
- 真实接口、设备与被测模型的生成效果没有因审定变成已验证。

## 怎样用

- 对照效果时读两份 Story，再按需读 Spec、Review 与车钥匙 Plan。不要求同名小节、同字数或同句式；有依据的新增解释不因金样没写而判错。
- 金样与维护分析留在评价域，不进入被测 Case，也不复制进运行工作区。
- Story 材料清单里的链接按消费工程需求目录 `doc/features/<单号>/` 写，在本目录里点不开；仓内可点的权威输入在各组 README 的来源对照里。
- 三张 Mermaid 在正本里保持 Mermaid 形态，不需要 SVG；综合阅读图在 Story 正本里是放置小节末尾的空阅读槽（正式形态），依据写在 SVG 的 `<metadata>`，各组 README 给独立阅读入口。车钥匙 spec §5.3 #1 由表承接，承接位置登记在写作设计里（金样只放目标产物，不含写作设计）。

## 维护

- 文件身份只登记在 `test/tests/test_golden_sample.py` 的 `REGISTRY`（sha256 前 16 位，Markdown、Mermaid 源与 SVG 按 LF 归一）。同一文件还核正文链接、来源对照、图源与正文一致、综合阅读图登记与依据说明、阅读槽的位置与正式形态、README 的阅读入口，以及 Story 与 Spec、Review 的编号互引。
- `test_run_measurement.py` 读同一份登记，核审定正文在本目录之外没有第二份。
- 实质修改要重新交用户审定；只改路径等机械调整也要在交回里列前后差异，再改登记。
- 旧正本（AR90004 story、AR90006 story 与 review、银行卡开卡上报候选）已于 2026-10-17 由这两组接替，历史由 Git 保存。
