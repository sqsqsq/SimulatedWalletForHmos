# 步骤 6 · 材料版本与流程状态单一真源

## 目标

消除 P5/P13：材料、图片、轮次、Story flow 和 Framework phase 各有唯一所有者。输入版本变化可确定发现，
但脚本不判断材料语义是否充足。

## 所有权

| 内容 | 唯一所有者 |
|---|---|
| 原始材料、图片身份与版本 | material manifest |
| 材料是否齐备、AR 范围与承载选择 | Story flow |
| `init-analysis.md` 内容 | 分析产物自身 |
| Spec～Testing 状态和闭环 | Framework |
| 测试运行状态 | 测试装置 |

## 实施内容

1. `AR/story-src/materials.json` 是唯一 material manifest；由一个共享 Python 模块枚举材料并计算文件/资产 hash 与总 digest；
2. 需求系统初始化、inbox 导入和补料入口在落盘成功后调用同一 manifest 写入者；其他脚本只读，不重复计算材料 hash；
3. `import_sources.py` 不再写独立导入回执；成功结果直接返回本次事件摘要，持久材料事实只在 manifest；
4. `story-flow.json` 删除 `inputs` 与逐文件 hash，只保存 manifest 的路径和 digest 引用；轮次的新旧只比较该 digest；
5. 图片只登记权威来源路径和资产身份，不再由 README 与复制目录各写一份；
6. material digest 是材料版本/轮次的唯一边界；只补图片也必须改变版本；
7. `init-analysis.md` 可在同一材料版本内迭代，它的 hash 不再划分轮次或与收口条件互斥；
8. Story flow 只记录材料、范围、承载和 Story 流程动作，不镜像 Framework phase 状态；
9. flow/check/import 的读取者统一字段含义；解析失败与真实空材料必须可区分；
10. 当前测试均为隔离 workspace，不增加 legacy schema 识别、迁移或兼容分支。

## 允许范围

- `import_sources.py`、`story_flow.py`、`flow-check.mjs`、新增的唯一 manifest 写入模块、材料合同及直接测试；
- `test/story` 的材料、轮次和状态测试；
- 与材料清单派生直接相关的模板/脚本。

不改 Story 语义作者任务、Knowledge 生命周期、Framework phase、Review 形态或现有 Case 输入。

## 完成条件

- 同一组材料重复导入 digest 不变；正文或图片任一字节改变 digest 改变；
- 全仓消费者扫描证明材料文件 hash 只在唯一 manifest 模块计算；
- 独立导入回执已删除，`story-flow.json` 不含 `inputs`，只引用 manifest path/digest；
- README 删除或变化不影响材料身份；图片没有第二份登记真源；
- 同一 material digest 下分析内容可修订并正常收口；
- Story flow 不写/推断 Framework phase；
- 空材料、解析失败、材料变化和合法不变四种结果可区分；
- P5/P13 与相关失效形态迁移到新字段或生成方式；
- 不运行真实 Story。
