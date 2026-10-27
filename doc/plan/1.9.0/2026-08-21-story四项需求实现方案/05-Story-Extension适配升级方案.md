# 05 · Story Extension 适配与升级

## 1. 入口

四类 Story 跳板增加：

```text
/story adapt [<目标工程>]
```

入口路由到独立 `doc/extensions/skills/story-adaptation/SKILL.md`。目标缺省为当前工程。Framework 未集成时只报告并退出。

## 2. 版本

- Manifest 的 `version` 是 Story 跳板与 Extension 的共同版本真源。
- 1.0 的来源证据由 `test/story` 维护记录保留；交付包内只保留已据此固化的不可变
  `releases/1.0.json`，适配器不依赖来源提交或 Git 历史。
- 2.0 清单在全部内容定稿后生成，Manifest 声明为 `2.0`；行为验证状态单独记录。

发布清单只维护：

- `managed_files`：版本直接维护、升级时新增/替换/删除的文件及 SHA-256。
- `adapted_files`：目标工程保留并重新核实的 `component-profile.md`、`codebase-facts.md`、
  `story.js`、`token.js`、`review.js`。
- `manifest_fields`：Manifest 中固定的直接维护字段与唯一的目标激活字段 `provides.knowledge`。

不建立通用 adaptation unit、字段所有权平台或可扩展扫描框架。

`doc/extensions` 是独立交付包。包内直接维护文件只可依赖包内内容和目标工程已声明的
前置能力，不得读取外部工程、来源绝对路径或来源工程 Git 历史。目标适配文件仍按发布清单
承载对目标工程的真实对接。

## 3. 三种流程

### 首次适配

在临时影子目录复制完整 2.0 managed 内容；扫描目标工程后适配两份工程知识、需求系统接入的
`story.js`、`token.js`、`review.js` 和知识激活建议。用户确认后一次写入。

### 版本升级

按来源/目标发布清单计算 managed 文件变化；保留 adapted 文件并重新扫描。向用户一次展示直接变化和适配变化，确认后统一写入。

### 同版本重新适配

不替换 managed 文件，只扫描并更新 adapted 文件和 `provides.knowledge`；没有变化时零写入。

## 4. 写入与恢复

适配脚本只负责路径检查、影子树、备份、复制、删除、校验和失败恢复。AI 负责阅读目标代码、形成适配内容和向用户解释方案。

安装记录保存当前版本、发布清单摘要、adapted 文件摘要和最后核实时间。失败后目标内容必须与写前指纹一致。

## 5. 验收

- Framework 缺失时目标零写入。
- 首次适配、1.0→2.0、同版本重新适配状态判定正确。
- managed 内容直接升级，adapted 内容保留并经用户确认后更新。
- 目标工程不依赖当前工程或原型工程绝对路径。
- 将 `doc/extensions` 单独交付后，1.0/2.0 识别、影子目录准备和升级均不需要来源工程或其 Git 历史。
