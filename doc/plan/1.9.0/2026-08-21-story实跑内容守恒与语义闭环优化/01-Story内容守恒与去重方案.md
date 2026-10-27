# Story 内容守恒与去重方案

> 状态：已完成离线实现与独立复核，等待人工确认
>
> 本阶段只解决事实缺失、事实走样、重复主叙述、正常/异常归位和直接妨碍验收的 Story/Review Extension 矛盾。标题风格和知识应用均不在本阶段修改。

## 一、目标

- 同轮 RR、SR、AR、UX、补充材料、最终 Spec、Acceptance 和有效决定中的事实都有落点。
- 每项事实只有一个完整主叙述；其他章节只保留必要承接、验收投影或精确查询。
- 当前特性内容完整保留；兄弟特性只保留拆分原因、职责、交接、顺序、共享状态生命周期和阻塞关系。
- 正常受限分支进入功能说明，真正失败及恢复进入异常与恢复。
- 开放决定不再作为 Story 的当前方案出现。

## 二、成文动作

继续使用十个章文件，但不再把“逐章装配”解释成十次彼此隔离的写作：

1. 一次读完任务书列出的同轮全部材料；
2. 在内部列出有效事实、编号、限定条件、否定条件和决定状态，并确定唯一主落点；
3. 完成十章初稿；
4. 同时打开全部章文件，按最终 Story 顺序做一次全文编辑，修正遗漏、重复、前后矛盾和正常/异常错位；
5. 全文核对通过后才 build/check。

内部事实清单不落盘，不新增来源台账。脚本不按关键词判断事实是否遗漏或语义是否重复。

## 三、决定投影

- `settled` 决定必须有同轮上游、可验证工程基线或人工确认依据，并在 Story 的自然位置投影一次。
- `source` 明示“无上游依据”的决定不能标为 `settled`。
- `open` 决定只进入 Review；Story 不能放 `{{DEC-...}}` 开放决定占位，也不能把建议写成当前处置、验收条件或正式事实。
- Review 继续同时展示开放和已定决定，人工区和状态模型不变。
- Review 使用人读说明表达 Story 关系，不生成 `story.md#...` 仓内文件链接。

不增加决定状态，不增加审批 DSL，也不让装配器判断来源语义是否真实。

## 四、失败级别

Story/Review 缺失、`story-build check` 失败或 `merge-story --check` 失败，表示本阶段交付物不可用。Spec 生命周期 hook 必须按 BLOCKER 返回。

其他既有 Spec 内容检查继续使用原有级别；不能因为其中混有 Story 故障，就把所有 Spec 提示统一升级。

## 五、四个组合 Case

正式 Case 从 15 个收敛为 4 个。一个 Case 必须同时包含多种会共同出现的业务条件；只改变标题、文件名或叙述顺序的输入不再单独起跑。

| Case | 组合场景 | 目标阶段 |
|---|---|---|
| `pattern-image-review` | 单特性、跨部件复杂业务、UX 图片、正常与失败路径、接口/数据/配置/事件/兼容/交付、Plan/Coding/Review 下游消费 | Story → Review |
| `split-interactive` | 任意文件名 docx 补料、初始范围意图、关卡内人话拆分、兄弟责任与阻塞、归档和评审回流 | Story → Story Review |
| `source-conflict-review` | 本地非 AR 单号起手、同轮来源冲突、人工定源、开放决定、单特性条件章节 | Story → Spec |
| `split-two-ar` | 上游已拆为多个 AR、交接标识、共享状态生命周期、正常受限分支与真实失败、范围传到 Plan | Story → Plan |

四个 Case 使用四个不同 feature，可被现有隔离并行 CLI 同批装载。`narrative-brief`、`narrative-role`、`narrative-process` 改为离线变形夹具：同一事实分别按简报、角色问答和办理顺序表达，只验证标题和组织变化不影响取材，不再重复执行 Story/Spec。

原 `cross-component-rich`、`cross-component-rich-plan-coding`、`cross-component-rich-coding-review`、`first-release` 的丰富业务和下游链路归入 `pattern-image-review`；`docx-supplement`、`split-by-feature`、`review-reflow` 归入 `split-interactive`；`local-ticket-start` 归入 `source-conflict-review`。被归并的 Case 不保留第二套 case.yaml。

每个组合 Case 各有一份 truth，只引用自身可执行输入：workspace、case.yaml 中的人类任务说明和 interaction-script.yaml 中实际会发送的人工回复。truth 逐项覆盖编号、规则、限定条件、否定条件、数值、图片、流程分支与决定状态，不再引用历史 mock 作为当前 Case 的事实来源。

## 六、验证

### 机械验证

- v5 十章、`reading_focus` 和全量材料枚举不回退；
- 开放决定在 Story 零投影，已定决定恰好一次；
- “无上游依据”的决定不能标为 settled；
- Review 不再含 `story.md#`；
- Story/Review 装配或归档检查失败时 lifecycle hook 返回 BLOCKER；
- 生产合同中仍不存在 selector、标题匹配、`primary/supporting` 和章节命中门禁；
- 正式 Case 定义恰好 4 个、feature 唯一，且每个 Case 至少承载 3 类场景；
- 4 份 truth 只引用各自 Case 的可执行输入，叙述变形只存在于 fixtures；
- 多场景 Case 的静态输入覆盖得到看护，但不启动 CLI。

### 语义验证

独立评审者对固定输入逐项记录来源位置、事实、Story/Review 唯一落点和最终证据。编号、表行、业务规则、限定与否定条件、数值、图片、流程分支和决定状态全部纳入；缺失、走样或多个完整主叙述均失败。

### 阶段停止点

离线测试、Extension Harness 与独立语义评审完成后写阶段一报告并停止。未获人工确认，不修改阶段二或阶段三的生产实现。
