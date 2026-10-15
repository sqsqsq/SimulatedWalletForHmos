# car-key-sharing 金样（可评审到 Plan）

- **情景终点**：本地问题单 ISSUE-206 从半份材料起手，规格定稿后接着做到实现方案（`case.yaml` 的 `end_phase: plan`）。可评审与可实施合并为一组，止于 Plan；不含 update 情景（用户 2026-10-12 裁定）。
- **目标产物**：`AR/story.md`、`AR/review.md`、`spec/spec.md`、`plan/plan.md`、`ux-reference/` 四张界面图。`contracts.yaml`、`use-cases.yaml`、`acceptance.yaml`、`decisions.json`、`knowledge-use.yaml`、`materials.json`、`AR/design.md` 等中间产物不入金样。
- **输入**：`test/cases/car-key-sharing`（P6 S1 承接后的版本）：`workspace/SR/design.md`（车云开放接口 2.1 字段，`68ff916d`）、`workspace/AR/detail.json`；补料《数字车钥匙分享.docx》（产品需求说明 v0.4，归 RR）与《车钥匙接受侧界面说明.docx》（归 UX，并入 `ux-reference/README.md`）。目标工程与项目知识取本线 demo。
- **有效宿主立场**（取自 `interaction-script.yaml`）：补料一次交齐；不拆单；`grace-window-initial`（宽限 48 小时指对方卡片收回，车辆侧撤销即拒绝，D1）；`car-key-card-scope`（一并补卡包车钥匙卡片与分享入口，D4）；`no-real-interface`（模拟数据验证，真实联调另算，D3）；`draft-resume-boundary`（退出页面、断网、应用关闭都能续办，发出成功、退出登录、换账号清除，D6）；`acceptance-ratio-owner`（被接受比例按车云分享记录统计，钱包端只报三个流程，D7）；术语确认；进入 plan。产品稿明写未定的再转第三人（D2）与极端断网强制下线（D5）保持待定。
- **设计选择**：车主本人钥匙、分享关系与被分享人一侧收到的分享都由可替换的模拟数据源提供（六个车云接口里没有按接受方账号查询的接口）；对方账号在业务请求里传可识别的 `granteeId`，展示用打码值；草稿要扛过应用关闭，用系统轻量键值存储、按账号分键；只有生效的分享可撤销，已作废与已到期可重新发起；设置页选 page-interaction，发起主链路不选 decision-tree；埋点只做发起、接受、撤销三个流程，编号为按分配规则取的候选值。换一种合理的类名、文件划分不算错。
- **图的来源**：story 发起时序承接系统设计「2. 发起分享的时序」，生命周期图承接「3. 分享状态机」并同时承接 spec 5.2；发起主路径、中断续办、被分享人接受、管理与撤销四张承接 spec 5.1、5.3（撤销图在 spec 基础上补了车辆侧即刻拒绝一步）；联调顺序图按设计新绘。四张界面图由两份原件抽出后登记进 `ux-reference/`。
- **机器区与生成区**：同 auto-topup，spec 9.2/9.3、story 附录机器区与 review 都由真实工具生成。
- **已核**：在临时模板工作区按真实导入链导入两份原件、登记界面图，`story-build check` 10 章通过；spec 门禁除流程契约占位外无内容问题；plan 门禁除 `contracts.yaml` 不在（中间产物）外无问题——因此 must 编号、义务集合、模式角色、责任方法四条契约侧判据未执行；Mermaid 全部渲染并看过。
- 这是期望结果：人的回答取自 Case 设计的宿主立场，不是已发生的人签；评审记录的人工区一律留空，Spec、Plan 头部状态是情景终点的示例。
- **2026-10-14 转正前修订**：草稿按账号与车辆定位、结果未知时冻结原请求（G05）；草稿 granteeId 的跨重启保存取证后定为阻断态，候选 Asset Store Kit 待端侧负责人按目标设备确认（G04）。story 附录对应机器区按修订后的 spec 同步，摘要用 `projectionDigest` 重算；SEC-01 那一行的判断件不在金样里，迁移正本前要在工作区重新 render、project 核一遍。
