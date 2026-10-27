# Story 章节取材软指导正向优化方案

> 日期：2026-08-21  
> 状态：已实施并通过离线与 Extension 验证；Story CLI/Case 未执行  
> 范围：局部优化 Story 章节写作任务书，不改变取材、装配、Review、归档或 CLI

## 1. 为什么要调整

已验证正常的父版本会按章节给作者取材提示，但提示未命中时回退到整篇，因此标题差异不会阻断写作。临时版本把提示收紧为精确 selector、必需来源和 `primary/supporting`，提示失效被提升成构建失败，最终使测试 Case 的标题和组织方式成为生产协议。

当前 v5 已删除这条硬依赖：每章都拿到同一轮完整材料，标题变化不会改变取材范围。这解决了致命错误，但也一并删除了父版本有价值的来源职责提示，模型必须从全量材料中自行判断每章应重点核对什么。

本轮只补回软指导：帮助作者定位证据，不选择、截取或拒绝材料。

## 2. 保持不变

- `story-chapters.json` 保持 v5 和已确认的十章顺序。
- 每章继续获得完全相同的实际材料清单。
- `loadSourceDocs`、材料枚举、build、check、Review 和归档行为不变。
- 事实实际出现在哪里，就从哪里采用；提示中的来源不是唯一来源。
- 同轮材料冲突仍登记 decisions/Review 并阻止定稿，由人确认后修正真源。
- 不恢复标题词、正则、标题路径、selector、`primary/supporting`、命中计数或缺失门禁。
- 现有章节文件与 Story 正文不迁移、不重写。

## 3. 合同调整

十章各增加必填字符串 `reading_focus`。它是写作元数据，不是输入合同，也不改变 v5 工作区结构。

| 章节 | reading_focus |
|---|---|
| 背景 | 重点核对 RR 中的用户问题、价值和目标，以及 AR 在完整需求中的位置。 |
| 术语 | 从全部材料识别理解正文必需的术语，以 Spec 最终用法核对表述，不照搬机器映射字段。 |
| 范围 | 重点核对 AR 范围与拆分、SR 参与方职责、Spec Scope 和 RR 产品边界。 |
| 业务方案 | 重点核对 SR 整体方案、RR 业务规则、Spec 最终行为和已确认决定。 |
| 业务流程 | 重点核对 RR 办理过程、SR 端到端协作、Spec 流程与状态、AR 交接边界。 |
| 功能说明 | 重点核对 Spec 场景、功能、页面和状态，结合 UX 与 AR 职责确认当前特性细节。 |
| 异常与恢复 | 综合 RR 用户结果、SR 失败影响和 Spec 异常恢复，不把正常受限分支误列为异常。 |
| 验收 | 重点核对 Acceptance、Spec 验收与质量要求、RR 成功条件和 SR 跨特性要求。 |
| 交付与上线 | 重点核对 RR/SR 协作依赖、Spec 配置与依赖，以及已确认的开放、观察和回退决定。 |
| 附录 | 重点核对 Spec 精确契约、SR 接口与数据、Acceptance 追溯、UX 和实际来源。 |

scaffold 在完整材料清单之后生成：

```text
取材关注（仅帮助阅读，不筛选材料）：<reading_focus>
```

随后继续生成本章边界、表达建议和通用写作判据。提示失效、提示所列来源不存在或事实位于其他材料时，均不得导致 scaffold/build/check 失败。

## 4. 规则同步

Story 成文规则和 Spec 阶段 Story 注入统一说明：

1. 先完整阅读全部同轮材料；
2. `reading_focus` 只指出优先核对的来源职责；
3. 事实出现在其他材料时仍须采用并按唯一主落点归章；
4. 提示不能替代来源版本、范围和冲突判断。

规则只在模型实际写章的位置出现。方案文档记录理由，运行期由章节任务书与 Spec Story 指令承载动作，避免创建新的参考文件或平行合同。

## 5. 实施范围

- 更新章节合同、合同校验和 scaffold 任务书渲染。
- 更新 Story 成文规则与 Spec 阶段 Story 写作指令。
- 更新直接验证章节合同和 scaffold 的离线测试。
- 在 `test/story/EVOLUTION.md` 记录长期决定：软指导可以失效，完整取材不能失效。

不修改 Framework、Knowledge、Review、归档、Case schema、Demo 能力、多 Case CLI 或现有 Case 材料。

## 6. 验收

- 十章均具有非空、职责不同的 `reading_focus`。
- 每章获得的材料清单仍完全相同。
- RR、SR、AR、Spec 的标题和组织方式任意变化，不改变 scaffold 成功与取材范围。
- 合同与脚本不存在章节 selector、标题匹配、`primary/supporting` 或命中门禁。
- 新提示正确进入章任务书，并明确标注“不筛选材料”。
- 现有 Story 工作区不需要迁移。
- Story 离线测试全集、Extension Harness 和独立 verifier 通过。
- 不执行任何 Story CLI 或 Case 实跑。

## 7. 实施顺序

1. 先完成本文并确认其已落盘；
2. 修改合同、scaffold、运行期写作规则和测试；
3. 完成离线验证；
4. 将本文状态更新为“已实施”，记录准确结果；
5. 后续 Demo、并行 CLI 和全部 Story CLI 实跑继续按上一轮交接执行。

## 8. 实施结果

本轮按方案完成以下调整：

- v5 十章各增加一个必填 `reading_focus`，章节 ID、标题、顺序和既有写作职责未变化；
- scaffold 在每章相同的完整材料清单之后渲染“取材关注（仅帮助阅读，不筛选材料）”；
- 合同校验只检查提示非空，不检查提示内容是否在来源中命中；
- Story 成文规则与 Spec 阶段注入已统一软指导、其他同轮材料和冲突处置语义；
- 离线测试补充了十章提示、相同材料清单、任意标题结构和无输入路由回退检查；
- 现有 v5 Story 工作区不迁移、不重写。

验证结果：

| 检查 | 结果 |
|---|---|
| 章节合同 JSON、JS/Python 语法检查 | PASS |
| 定向 Story 合同与 build 测试 | PASS：69 passed |
| `pytest test/story/tests -q -p no:cacheprovider` | PASS：422 passed，78 subtests passed |
| Framework `extensions` Harness | PASS：6/6，0 FAIL/WARN |
| 独立 verifier | PASS：0 BLOCKER、0 MAJOR、0 WARN |
| Story CLI/Case | 按用户边界未执行 |

最终行为仍是一条全量取材链。`reading_focus` 只影响之后新建章任务书中的阅读提示，不参与选择、截取、缺失判断或失败门禁。
