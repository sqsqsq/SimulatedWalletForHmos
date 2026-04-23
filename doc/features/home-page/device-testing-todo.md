# 真机测试待办 — home-page

> 由 Skill 5（业务级 UT）产出，Skill 6（真机测试）消费。
> 每条对应 `acceptance.yaml` 中 `ut_layer ∈ {device, both}` 的 AC / BD：
> - UT 已在业务层覆盖数据契约（`HomeRepository` Mock 返回值）；
> - 本文件列出真机侧需补验的 UI / 交互 / 渲染层要点。

## 真机覆盖项

### AC-1 首页基本渲染 · ut_layer=both

- **来源**：`acceptance.yaml > criteria > AC-1`
- **UT 已保证**：`HomeRepository.getServiceEntries / getPromoList` 返回值不为 null、数据模型字段齐全
- **真机需验证**：
  - [ ] 切到「首页」Tab 后无白屏、无崩溃
  - [ ] 标题区可见（文案、加号、消息图标）
  - [ ] 主区域可滚动

### AC-3 卡引导点击进入卡包 · ut_layer=device

- **UT 不覆盖**（纯 UI 导航交互）
- **真机需验证**：
  - [ ] 点击卡引导区后导航栈栈顶为 `CardPackPage`
  - [ ] 转场动画自然无异常

### AC-4 主按钮进入卡包 · ut_layer=device

- **真机需验证**：
  - [ ] 点击「添加/管理卡」主按钮，导航栈栈顶为 `CardPackPage`

### AC-5 加号进入添卡入口 · ut_layer=device

- **真机需验证**：
  - [ ] 点击标题栏加号，导航栈栈顶为 `AddCardEntryPage`

### AC-6 消息入口反馈 · ut_layer=device

- **真机需验证**：
  - [ ] 点击消息图标出现 Toast（文案匹配 `msg_center_welcome`）
  - [ ] Toast 持续时长 ≥ 1.5s

### AC-7 服务宫格 3 列 · ut_layer=device

- **真机需验证**：
  - [ ] 宫格实际列数为 3
  - [ ] 超过 3 项时能进入第二页/滑动

### AC-8 活动区标题、轮播、指示器 · ut_layer=device

- **真机需验证**：
  - [ ] 活动区有标题
  - [ ] 至少 1 张活动卡可见
  - [ ] 存在轮播指示/自动播行为

### AC-9 活动卡点击 · ut_layer=device

- **真机需验证**：
  - [ ] 点击活动卡出现 Toast 或占位
  - [ ] 不崩溃

### AC-10 无网不崩溃 · ut_layer=device

- **说明**：当前 `HomeRepository` 是本地 Mock 数据源，无真实网络路径，业务 UT 无法构造网络异常
- **真机需验证**：
  - [ ] 飞行模式下切到首页不白屏
  - [ ] Toast 文案为 `home_data_unavailable` 对应字符串
  - [ ] 页面能自然滚动（空态/占位）

### AC-G1 目标设备布局无严重错位 · ut_layer=device

- **真机需验证**：
  - [ ] 在目标机型上页面布局无重叠、截断

### AC-G2 主操作 300ms 内反馈 · ut_layer=device

- **真机需验证**：
  - [ ] 点击主按钮后 300ms 内出现视觉/导航反馈

### BD-1 无网络 · ut_layer=device

- **说明**：Mock 数据源不触发网络异常分支，全部交真机验证
- **真机需验证**：
  - [ ] 无网络下 Toast 出现且文案正确
  - [ ] 刷新后网络恢复能重试加载

### BD-2 空数据 · ut_layer=device

- **说明**：Mock 固定返回非空列表，空态路径交真机观察
- **真机需验证**：
  - [ ] 服务为空时宫格区域隐藏或显示空态
  - [ ] 活动为空时活动区隐藏或显示空态
  - [ ] 都为空时页面不崩溃，仍可滚动

### BD-3 无 navPathStack · ut_layer=device

- **真机需验证**：
  - [ ] 无导航栈时点击跳转按钮不崩溃，可出现 Toast 或静默

## 与测试计划的对接

Skill 6 将本文件每条 checklist 子项转化为真机用例的测试步骤，
用例的「关联 AC」字段记录 `AC-X (ut_layer=...)`。
