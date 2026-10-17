# car-key-sharing 金样（可评审到 Plan）

- **情景终点**：本地问题单 ISSUE-206 从半份材料起手，规格定稿后接着做到实现方案（`case.yaml` 的 `end_phase: plan`）。可评审与可实施合并为一组，止于 Plan；不含 update 情景（用户 2026-10-12 裁定）。
- **目标产物**：`AR/story.md`、`AR/review.md`、`spec/spec.md`、`plan/plan.md`、`ux-reference/` 四张界面图，以及 Story 三张正式 Mermaid 的图源 `AR/story-src/figures/<ID>.mmd` 与 5.5 的综合阅读图 `AR/figures/car-key-revocation-responsibility.svg`。`contracts.yaml`、`use-cases.yaml`、`acceptance.yaml`、`decisions.json`、`knowledge-use.yaml`、`materials.json`、`AR/design.md` 等中间产物不入金样。
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
  - 本地没有草稿或草稿损坏时，先按账号与车辆向模拟车云做创建恢复（pending / established / clear / unknown），确认旧请求去向后才开放新建，首次进入与成功发出清稿后再次发起同样如此；退出、换号、清数据只清本地。
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
  - 模拟车云的幂等记录独立于钱包进程保留；
  - 模拟车云按账号与车辆保留未终结的创建，给出创建恢复结果：只在确认旧请求已终结、或它迟到也建不出分享时回答 clear，受理新的创建时再核一次未决请求。真实车云六个接口没有这项，列为正式开放前的依赖：缺它时，凡要先做创建恢复的新建都不能正式开放，接受、撤销与管理按各自条件。

  以上都没有在真实工程或设备上验证，真实接入时须核目标环境与字段上限。这些不是已有人签，也不改写原始材料或人工答复。
- **保留的真实未决**：D2、D5；本轮新增 D8（待接受的分享能否撤回：产品原文「随时可撤」与车云状态机只给生效撤销不一致，推荐支持但须车云补能力）。D7 的批次口径标为维护设计对需求方答复的深化。
- **图的来源**：
  - 4.1 双云协作时序承接系统设计「2. 发起分享的时序」，补了推送未送达不改变创建结果的说明；
  - 5.1 跨角色旅程承接 spec 5.1 的发起主路径，以及 spec 5.3 接受与撤销两张子流程的正常过程；接受时的状态分流由 5.4 的状态显示表承接，撤销失败后的重拉由 5.5 承接；
  - 5.2 生命周期图承接「3. 分享状态机」，并同时承接 spec 5.2；
  - spec 5.3 的中断续办与草稿保护子流程由 Story 5.3 的保存与恢复两张表承接，Story 不另画图；现行 `story-build check` 按图源标记认承接，对这一项报 1 处「上游图承接」，交维护设计者裁定（见本轮交回）；
  - 四张界面图由两份原件抽出后登记进 `ux-reference/`。
- **材料来源对照**：Story 材料清单里的链接是消费工程需求目录 `doc/features/ISSUE-206/` 下的路径，保持产品应输出的样子；在本目录里直接点不开。下表把每个链接对到仓内可点的权威输入（路径相对本 README），摘要取 sha256 前 16 位：

  | Story 中的链接 | 性质 | 仓内权威输入 | 版本或摘要 | 派生方式 |
  |---|---|---|---|---|
  | `../inbox/数字车钥匙分享.docx` | 原件：补料，产品需求说明 | [supplements/数字车钥匙分享.docx](../../../../../test/cases/car-key-sharing/supplements/数字车钥匙分享.docx) | v0.4，`2a5b166b8b3e6ab4` | —— |
  | `../RR/prd.md` | 导入阅读稿 | 同上一行的产品原件 | `08191c0b44384c12` | 补料交齐后 `import_sources.py --feature ISSUE-206` 按产品需求分类导入：docx 转成正文，图抽到 `assets/` |
  | `../SR/design.md` | 原件：车云同事放进需求目录的系统设计 | [workspace/SR/design.md](../../../../../test/cases/car-key-sharing/workspace/SR/design.md) | `68ff916dff8a6b00` | —— |
  | `design.md` | 运行中写出的开发需求提取件；Case 与金样都不归档这份文件 | [workspace/AR/detail.json](../../../../../test/cases/car-key-sharing/workspace/AR/detail.json)（本地问题单登记） | `cb653fff6d3367be` | story 初析读问题单与已交材料、确认整单承载后写出 |
  | `../inbox/车钥匙接受侧界面说明.docx` | 原件：补料，接受侧界面说明 | [supplements/车钥匙接受侧界面说明.docx](../../../../../test/cases/car-key-sharing/supplements/车钥匙接受侧界面说明.docx) | `fbc813c5206c9b52` | —— |
  | `../ux-reference/README.md` | 导入阅读稿 | 同上一行的界面说明原件 | `f70ca30fc6000186` | 同一导入按界面参考分类：正文并入界面参考说明，图登记进 `ux-reference/` |

  阅读稿的摘要来自 2026-10-16 在临时模板里按真实导入链重跑的结果（证据见本轮交回）；原件改了，阅读稿摘要随之变化，要重跑导入核对。
- **图源与综合阅读图**：Story 的三张 Mermaid 带 `story-figure` 管理标记，图义真源是 `AR/story-src/figures/<ID>.mmd`，正文块与源逐字一致，正本里保持 Mermaid 形态。`AR/figures/car-key-revocation-responsibility.svg` 是 5.5 的综合阅读图：沿同一个撤销事件对齐车云里的分享状态、车辆使用权与接受方手机卡片，依据 Story 5.2、5.4、5.5 与 4.2、spec 的撤销规则；它不是哪一张 Mermaid 的等值副本，`<metadata>` 写依据位置，业务事实以 Spec 与正文为准。
  - 改图义只改 `.mmd`，再用 `story-build view --mode mermaid` 重铺正文块；综合阅读图的依据变了要重画并重做独立审查。
  - 现行产品的阅读视图按「每张 Mermaid 一张等值 SVG」切换，综合阅读图不走这条路径：Story 里给的是普通链接，`story-build view --mode status` 对三张 Mermaid 报「还没有阅读图」属于这项运行机制差异，不是金样缺件。
  - 渲染图、独立审查请求与报告、绘图脚本不进金样，留在本轮证据目录。
- **机器区与生成区**：同 auto-topup，spec 9.2 / 9.3、story 附录机器区与 review 都由真实工具生成。2026-10-17 修订后在临时模板按真实导入链重跑 render、project、number、build，再跑一次与候选逐字节一致；`story-build check` 除上面那 1 处「上游图承接」外通过。
- **门禁**：
  - spec 门禁除临时目录里的流程契约占位外无内容问题；
  - plan 门禁除 `contracts.yaml` 不在（中间产物）外无问题，因此 must 编号、义务集合、模式角色、责任方法四条契约侧判据未执行。
- **未核**：Mermaid 的逐图渲染查看见本轮交审记录。
- 这是期望结果：人的回答取自 Case 设计的宿主立场，不是已发生的人签；评审记录的人工区一律留空，Spec、Plan 头部状态是情景终点的示例。
