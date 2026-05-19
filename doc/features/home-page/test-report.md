# 测试报告 — home-page

> **模块标识**: `home-page`  
> **版本**: v1.5  
> **日期**: 2026-05-19  
> **测试执行人**: Hylyre 真机自动化 + agent 回填  
> **对应测试计划**: `doc/features/home-page/test-plan.md`

> **说明**: Hylyre 执行对齐 **`20260519-rerun-v8/hylyre/trace.json`**（`outcome=partial`，**8 / 11** 通过）。`TC-010` / `TC-013`～`TC-015` 为 **explicit_skip**。流水线耗时来自 **`device-test-timing.json`**（最后一轮：touch `HomeTabPage.ets` 触发重编后的完整 harness）。

---

## 一、测试概览

| 项目 | 内容 |
|------|------|
| 测试模块 | home-page / WalletMain 首页 |
| 测试日期 | 2026-05-19 |
| 测试环境 | 真机 3UJ0225327004147，HarmonyOS 6.1.0.117 (SP6)，API 23；Hylyre + hvigor debug 包 |
| 执行人 | Hylyre 自动化 |
| 用例总数（顶层计划） | 15 |
| 纳入自动化 | 11 |
| explicit_skip | 4（TC-010、TC-013、TC-014、TC-015） |

### 真机流水线耗时

> 数据来源：`doc/features/home-page/testing/reports/device-test-timing.json`（`generated_at`: 2026-05-19T13:27:31Z）

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 打包 (hvigor) | 8.2s | **未复用**（`build_reused: false`；touch `HomeTabPage.ets` 触发重编） |
| 装机 (hdc) | 0.5s | **未复用**（`install_reused: false`） |
| Hylyre 自动化 | 45.5s | 含设备预启动 |
| 快照写入 (page save) | 6.6s | 非致命；`hylyre_page_save.exit_code: 0` |
| **合计（脚本统计）** | **60.8s** | 各阶段 ms 之和 |

| 元数据 | 值 |
|--------|-----|
| HAP 落盘时间 (hapBuiltAt) | 2026-05-19T13:26:43.708Z |
| 本次 harness 跑 build 门禁时刻 | 2026-05-19T13:26:43.809Z |

**Plan 验收备注（同日多轮）**：

- 无改码连跑：第 1～2 轮 `device-test-build.result.json` → `reused: true`，`hvigorExecuted: false`；第 2 轮 `device-test-install.meta.json` → `install_reused: true`。
- `HARNESS_DEVICE_TEST_FORCE_BUILD=1`：`hvigorExecuted: true`（约 3.3s）。
- `doc/app-snapshot-cache/com.example.simulatedwallet/pages/home.json` 已生成（约 746KB）。

---

## 二、测试执行结果

| 用例编号 | 用例名称 | 优先级 | 执行状态 | 耗时 | 备注 |
|----------|----------|--------|----------|------|------|
| TC-001 | 首页进入后主结构无崩溃 | P0 | 通过 | 0.3s | Hylyre：`touch`「首页」 |
| TC-002 | 服务与活动区可见条目 | P0 | 通过 | 0.6s | scroll + 目视 Mock 数据区 |
| TC-003 | 卡面/卡引导可点进卡包 | P0 | 失败 | 0.1s | 找不到「首页」；DEF-001 |
| TC-004 | 「添加/管理卡」主按钮进卡包 | P0 | 失败 | 0.1s | 同上；DEF-001 |
| TC-005 | 标题栏加号进添卡入口 | P0 | 失败 | 0.1s | 同上；DEF-001 |
| TC-006 | 消息入口有轻量反馈 | P0 | 通过 | 2.8s | `touch`「消息」→ Toast |
| TC-007 | 服务宫格 3 列展示 | P1 | 通过 | 2.3s | scroll + `touch`「Huawei Card」 |
| TC-008 | 活动区标题+轮播+指示器/自动播 | P1 | 通过 | 2.8s | scroll 至「更多服务」区 |
| TC-009 | 活动卡点击有反馈不崩溃 | P1 | 通过 | 3.5s | `touch`「春日出行」→ Toast |
| TC-010 | 飞行模式进首页不白屏 | P1 | 跳过 | — | explicit_skip；需人工开关飞行模式 |
| TC-011 | 首屏与区块布局无严重错位 | P0 | 通过 | 1.9s | 上下 scroll 走查 |
| TC-012 | 主要可点区域有点击反馈 | P0 | 通过 | 3.1s | 消息 + Huawei Card 点击有反馈 |
| TC-013 | 无网与降级提示（边界 E1） | P0 | 跳过 | — | explicit_skip；需断网环境 |
| TC-014 | 服务/活动空列表不崩溃（边界 E2） | P0 | 跳过 | — | explicit_skip；Mock 固定非空 |
| TC-015 | 无 navPathStack 不盲目 push（边界 E3） | P1 | 跳过 | — | explicit_skip；极端宿主场景 |

---

## 三、缺陷清单

| 缺陷编号 | 关联用例 | 严重程度 | 描述 | 状态 |
|----------|---------|---------|------|------|
| DEF-001 | TC-003、TC-004、TC-005 | MAJOR | TC-004 执行后停留在卡包子页；`back` + swipe 未能回到首页 Tab，后续步骤 `BY.text('首页')` 找不到组件（Script-0203002） | 待修复 |

### 缺陷统计

| 严重程度 | 数量 | 待修复 | 已修复 | 已关闭 | 延期处理 |
|---------|------|--------|--------|--------|---------|
| BLOCKER | 0 | 0 | 0 | 0 | 0 |
| MAJOR | 1 | 1 | 0 | 0 | 0 |
| MINOR | 0 | 0 | 0 | 0 | 0 |
| **合计** | **1** | **1** | **0** | **0** | **0** |

---

## 四、通过率统计

| 优先级 | 总用例 | 通过 | 失败 | 阻塞 | 跳过 | 通过率 | 达标阈值 | 是否达标 |
|--------|--------|------|------|------|------|--------|---------|---------|
| P0 | 10 | 5 | 3 | 0 | 2 | 62.5%（5/8 执行） | 100% | ❌ |
| P1 | 5 | 3 | 0 | 0 | 2 | 100%（3/3 执行） | 按 AC | ✅ |
| **合计** | **15** | **8** | **3** | **0** | **4** | **72.7%**（8/11 自动化） | — | — |

> 自动化分母为纳入 Hylyre 的 11 条；explicit_skip 4 条不计入执行分母。

---

## 五、结论

**有条件达标**（框架门禁 PASS；Hylyre `partial` 8/11；P0 导航类 TC-003/004/005 仍失败）。

**后续建议**：按 `derive-hint-from-plan.json` 的 `navigation_hint` 重派生或补 `app-snapshot-cache` 探索后再跑 v9；Nav 修复不阻塞本 plan 的 harness/耗时/复用能力验收。
