# car-key-sharing 金样（可评审到 Plan）

- **情景终点**：本地问题单 ISSUE-206 从半份材料起手，规格定稿后接着做到实现方案（`case.yaml` 的 `end_phase: plan`）。可评审与可实施合并为一组，止于 Plan；不含 update 情景（用户 2026-10-12 裁定）。
- **目标产物**：`AR/story.md`、`AR/review.md`、`spec/spec.md`、`plan/plan.md`、`ux-reference/` 四张界面图。`contracts.yaml`、`use-cases.yaml`、`acceptance.yaml`、`decisions.json`、`knowledge-use.yaml`、`materials.json`、`AR/design.md` 等中间产物不入金样。
- **输入**：`test/cases/car-key-sharing`（P6 S1 承接后的版本）：`workspace/SR/design.md`（车云开放接口 2.1 字段，`68ff916d`）、`workspace/AR/detail.json`；补料《数字车钥匙分享.docx》（产品需求说明 v0.4，归 RR）与《车钥匙接受侧界面说明.docx》（归 UX，并入 `ux-reference/README.md`）。目标工程事实取本线 demo，知识判断取本轮开发源 `extensions/knowledge/`（两者的 SEC-01 版本不同，Plan 9.1 有说明）。
- **有效宿主立场**（取自 `interaction-script.yaml`）：
  - 补料一次交齐；不拆单；
  - `grace-window-initial`：宽限 48 小时指对方卡片收回，车辆侧撤销即拒绝（D1）；
  - `car-key-card-scope`：一并补卡包车钥匙卡片与分享入口（D4）；
  - `no-real-interface`：模拟数据验证，真实联调另算（D3）；
  - `draft-resume-boundary`：退出页面、断网、应用关闭都能续办，发出成功、退出登录、换账号清除（D6）；
  - `acceptance-ratio-owner`：被接受比例按车云分享记录统计，钱包端只报三个流程（D7）；
  - 术语确认；进入 plan。

  产品稿明写未定的再转第三人（D2）与极端断网强制下线（D5）保持待定。
- **设计选择**：
  - 草稿每账号每车辆一条系统 Asset，完整草稿放在一个 SECRET，发出前持久化原请求，读取结果分不存在、有草稿、不可访问、损坏四种。
  - 主动退出先标记不可恢复再删除，清理失败照常退出但禁止分享。
  - 同账号同车辆串行创建，回调按账号与会话匹配。
  - 接受与撤销失败按重取的车云状态显示，凭据下发失败（failed 加 pending）保持待接受。
  - 稳定账号标识、模拟联系人与车型类别由 WalletMain 模拟数据源提供；权限选项原样显示、原样传回。
  - 失败说明按错误码映射成安全说明。
  - 只有生效的分享可撤销（待接受能否撤回待 D8），已作废与已到期可重新发起。
  - 设置页选 page-interaction，发起主链路不选 decision-tree。
  - 埋点只做发起、接受、撤销三个流程，编号为按分配规则取的候选值；分享被接受比例的批次口径写在 Story 第 8 章。

  换一种合理的类名、文件划分不算错。
- **本轮设计前提**（2026-10-16 维护设计，随具体稿待用户审定）：
  - API 12 与设备具备 `SystemCapability.Security.Asset`；
  - 模拟输入的完整草稿按 UTF-8 序列化不超过 1024 字节；
  - 模拟账号的 `accountKey` 重开后不变；
  - 模拟车云的幂等记录独立于钱包进程保留。

  以上都没有在真实工程或设备上验证，真实接入时须核目标环境与字段上限。这些不是已有人签，也不改写原始材料或人工答复。
- **保留的真实未决**：D2、D5；本轮新增 D8（待接受的分享能否撤回：产品原文「随时可撤」与车云状态机只给生效撤销不一致，推荐支持但须车云补能力）。D7 的批次口径标为维护设计对需求方答复的深化。
- **图的来源**：
  - story 发起时序承接系统设计「2. 发起分享的时序」，补了推送未送达不改变创建结果的说明；
  - 生命周期图承接「3. 分享状态机」，并同时承接 spec 5.2；
  - 发起主路径、中断续办与草稿保护、被分享人接受、管理与撤销四张承接 spec 5.1、5.3（撤销图在 spec 基础上补了车辆侧即刻拒绝一步）；
  - 联调顺序图按设计新绘；
  - 四张界面图由两份原件抽出后登记进 `ux-reference/`。
- **机器区与生成区**：同 auto-topup，spec 9.2 / 9.3、story 附录机器区与 review 都由真实工具生成。2026-10-16 修订后在临时模板按真实导入链重跑 render、project、number、build，再跑一次与候选逐字节一致；`story-build check` 10 章通过。
- **门禁**：
  - spec 门禁除临时目录里的流程契约占位外无内容问题；
  - plan 门禁除 `contracts.yaml` 不在（中间产物）外无问题，因此 must 编号、义务集合、模式角色、责任方法四条契约侧判据未执行。
- **未核**：Mermaid 的逐图渲染查看见本轮交审记录。
- 这是期望结果：人的回答取自 Case 设计的宿主立场，不是已发生的人签；评审记录的人工区一律留空，Spec、Plan 头部状态是情景终点的示例。
