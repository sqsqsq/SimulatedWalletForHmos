# 03 · Knowledge 跨阶段应用

## 1. 原位维护

不新建 `project-facts/` 目录：

- `component-profile.md` 继续说明部件职责、不负责内容和交互方。
- `codebase-facts.md` 继续按对外能力、端云、存储、配置、埋点和依赖说明真实工程能力。
- Constraints 保留要求、适用条件和验证语义；只移动经逐项证明属于目标工程事实的内容。
- Design Patterns 保留完整方案、适用边界、结构和验证要求。

三类知识由 Manifest 现有 `provides.knowledge` 激活，不新增目录扫描器或统一 frontmatter 类型框架。

## 2. 阶段应用

- Spec：识别适用规约产生的需求要求，以及零个或多个设计模式候选。
- Plan：结合真实项目知识完成正常工程设计；知识必须实际改变复用、依赖、接口、文件、流程、状态、异常或验证方案。
- Coding、Review、UT、Testing：读取正常 Plan、contracts 和 use-cases，分别用代码、diff、用例和实际结果证明落实；不回到 Knowledge 重新选型。

现有共享 Hook 和 Overlay 继续作为阶段入口，只补充三类知识职责和消费结果，不建立平行知识合同。

## 3. 三层可观测性

新增 `constraints/diagnostics-metrics.md`：

- 日志用于本地调测和完整链路还原；
- VOC 用于缺少本地日志时的远程定位；
- Chart 用于成功率、时延和终态统计；
- 三层共用业务 flow/step 语义，密度为日志高于 VOC、高于 Chart，不设数量配额；
- Chart 每个业务步骤只有一个终态事件，结果字段区分成功与失败；
- 所有渠道排除秘密字段，失败不得改变业务结果或重试。

Demo 中 Logger、VOC、Chart 的真实 API、导出、非阻塞写入和失败语义补充到现有 `codebase-facts.md` 的“埋点”能力面，以连续说明和真实代码证据表达，不创建 CAP 清单。

## 4. 验收

- 两份项目知识文件完整保留且职责互补。
- Plan 不能只列知识名称；采用决定能指向正常设计落点。
- 下游无需解析新字段即可获得并执行 Plan 决定。
- 日志或上报失败不影响业务结果，秘密字段不进入任何渠道。
