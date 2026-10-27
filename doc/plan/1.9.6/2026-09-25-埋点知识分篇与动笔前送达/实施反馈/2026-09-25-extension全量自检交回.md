# extension 全量自检交回：过拟合与打补丁（2026-09-25）

用户要求：CLI 测试之前，对 extension 做一次全量自检，范围包括正文、脚本与注释，查过拟合和打补丁两类问题。

做法：三个只读审计分别逐行读完三块——`hooks/`、`skills/story/scripts`（含 contracts 与 adapt-scan），以及正文、规则、模板与知识。每条发现我都回原文核对后再处置。提交 **2e429459**。

结果：全量离线 **1379 passed、15 skipped、523 subtests**；机制 13075 → **13053**。

## 1. 已修（按类）

### 与本轮测试用例同形的内容（最高优先级，会直接污染实跑）

- `phases/update.md`：「把单日上限改成 300」「时限从 24 小时改成 36 小时」——正是两个 Case 的 update 输入。改为中性说法：「把默认排序改成按时间」「一个数值变化不只是换一个数字」。
- `rules/spec-rules.overlay.yaml`：跨章核对的例子「未登录、未实名、开关关闭、配额用尽」是 auto-topup 的三个关键条件，改为「决定用户能否继续的关键条件」。
- `story-write.md`：
  - 「宽限期」→「截止时间」；
  - 「关闭入口不等于撤销业务」→「入口开关影响哪些用户、哪些已有业务照常」；
  - 「为什么不是十分钟」→「为什么是半小时」；
  - 「两单分工」「支线一」「能力承接」「机制闭环」「已安排」「开发侧确认」这类取自实跑的原话删掉，只留正向规则。
- `scripts/core/story/review.mjs` 注释「单日上限口径 200 元」删掉。
- `knowledge/facts/component-profile.md`：交互方表单独补进的「车钥匙」删掉——职责列表里本来没有它。
- 号段 `AR900xx` / `ARxxxx` / `RR90xxx` / `SR90xxx` 换成 `<兄弟 AR 单号>` 这类占位，涉及 ar_design_init、init_analysis、scope_gate 与 overlay。

### 机制按某份具体知识的结构取名

- `rules/ar_design_init.md`、`init_analysis.md` 里的「部件画像」「部件申明」「交互方清单」「运行形态」，是 Demo 那份知识的小节名。改为「回答本部件是谁、与谁交互的那份知识」给出的职责范围与交互方类别。
- `hooks` 里取自具体规约的例子改为中性：
  - `(left\|right)` → `(a\|b)`；
  - `flowId`、`.ets` → `A.b`、`X.ext`；
  - 「账号 / 通用 UI / 工具」→「不在 in_scope_modules」；
  - 「本需求无新增对外开放页面」「RTL、图标、文案」「界面沿用现有样式」「撤销后要留痕」「单个清单最多 50 项」→ 占位或只写规则；
  - `NodeTable` 删掉。
- 宿主专属：`story-write.md` 不再写死 PowerShell；`update.md` 的 `Move-Item … -20260921T1030` 命令删掉。

### 叙述历史、查不到出处的编号

`hooks` 与 `scripts` 里的「基线态 / 平行账本 / 从前 / 后来 / 出过事 / 这次重写 / 洋葱式 FAIL / 1.0 逐章生产线 / 每一样都被裁掉过」等叙述，改成现行规则加原因。以下编号与标注一律删掉：

- 查不到出处的编号：G7、E9、KB-11、D1、A7、A12；
- 与代码不符的行号引用：`hooks-dispatcher.ts:190-200`。

### 失效引用与自相矛盾

- **story 数值的来源括注**：`evidence-rules` 说 story 正文不带，overlay 却说带。统一为不带，来源由 spec 承担。
- **评审回流**：`phases/spec.md` 写「只改 spec、不动 story」，与同页和 `update.md` 相反。改为「要改先 reopen」。
- **指向不存在位置的引用**，全部改为附录·规约判定或现行章节：「影响面回显 / 合规回显 / story 影响面 / 兼容性自检 / 上线时序 B4」、`evidence-rules §0`、SKILL「检视」节、`hooks/coding/pre_check.mjs`。
- **章节与命令名**：
  - story-write 的章节名：「五、十章各自怎么组织」→「五、照骨架写一章」，「四、回看」→「六、回看」；
  - 「质量与验收」章 →「验收」章；
  - 已改名的 `init` 命令 → `skeleton`；
  - 冻结守卫的命令范围写对。
- **写死的计数与数字**：「十一类」改成按合同计数；「五个读点」「九项判据」「三缺一」「300 行」这类写死的数改掉或删去。
- **注释与实现不符**：
  - ut/testing 头注释说按 `ut_layer` 分派，实际按 `must.verify`，改成后者；
  - spec 任务包注释说「十章各答什么」，改成任务包实际的各节；
  - 错位的 JSDoc 归位；
  - 与代码不符的「给坐标不给副本」注释按实际行为重写；
  - 孤立的「影响面与合规」JSDoc 删掉。
- **归类值域**：inbox 归类值域补全 `IMAGES|MEETING`，importer 报错改从 `CLASSES` 生成。

### 打补丁：旧格式兼容、静默兜底、死代码

- **图片说明**：`.captions.json` 字符串值升格为 `{caption}` 的兼容分支退出，相应专用测试删掉。
- **投影区与评审议题的机器区**：「标记没有摘要就与这次渲染比」的旧稿分支退出，没有摘要一律按改过处理、停下问人。两条旧稿用例合为一条。
- **材料清单**：旧形状 `items/path` 的专门提示删掉。
- **静默兜底改为报错**：
  - `routing.py` 读不到合同时回落「待写」→ 照实报错；
  - `inputs.py` 包内模板缺失时写内置文案 → 直接读模板。
- **判据兜底**：
  - 术语映射表按位置找列、最后一列复选框的兜底 → 缺列直接报；
  - 评审复核依据「少于 6 个字」的字数配额 → 与知识判断同一判据（空，或只写了判词本身）；
  - `pre_verifier` 未知阶段静默套用 plan → 显式报错。
- **overlay 读取**：`pre_verifier` 逐行手解 overlay YAML → 用同一个 YAML 读取器。
- **死代码与残留**：
  - 章节合同里没人读的 `"version": "4.0"`；
  - 两处空分节头；
  - 没有外部使用者的 `basename` 导出；
  - `decisions.py` 的重复判断；
  - 语言红线里只匹配 `A1–A8` 的一条正则（按一次输出定制；「不写小节互指」的规则仍在 evidence-rules）；
  - 知识判断里旧格式 `used_for` 的专门提示。

### 真实缺陷

- `hooks/spec/post_check.mjs` 数值来源正则：中文单位后的 `\b` 永远不成立，「300毫秒，」「重试3次。」原先都扫不到，改为 `(?![A-Za-z])`。
- `hooks/spec/author.mjs` 用正则扫 YAML 找 `applicable: true`：会跨条目串读、读进注释。改用 `readUse`。
- 「命中、本轮落实、产生代码要求」在 spec 门禁、plan 门禁、plan 任务包、spec 任务包四处各写一遍，plan 任务包还漏了排除评审动作。收成 `codeRequirementIds` 一处定义。
- spec 任务包给的 acceptance 最小条目缺 framework 必填的 `ut_layer`，照抄会被门禁拦，已补上。

## 2. 核对后保留

- **读者心智示例**：`story-write.md` 开头的中性示例与「不这样写：…」。这是设计者定的读者心智示例，有用例守着，第一次改动时误删，已恢复。
- **切分规则的同句**：在 plan 作者页、spec.md、update.md 三处逐字相同。这是设计定的「在每个读者动作处送达」，有同句测试守着，已恢复。
- **决策登记接受 `{"decisions":[…]}` 与 `[…]` 两种顶层形状**：这是明确的输入合同，带理由与用例，不属于旧格式兼容。
- **`validation` 对 patterns 写 `chosen` 的报错**：spec 只登记候选、不选型，是阶段职责，只把条件写简。
- **「承载会换，业务不会」**：protocol、spec 模板、plan 模板三处都写了。它是通用规则，按「在动作处送达」保留，plan 门禁的措辞改成「不能拿实现载体的现状当理由」。
- **`decision-tree.md`「本工程存量的开卡流程编排」**：这是项目事实，不在测试用例里。
- **event-tracking 的示例题材**：与金样同类（开通、短信验证），这是设计 D6 定的「金样是形状来源」。它不与两个测试用例同形。

## 3. 结构性问题，需要设计者决定（本轮未改）

| 问题 | 位置 | 为什么没顺手改 |
|---|---|---|
| 「哪种单挂在需求系统上」（AR 前缀）在 core 写死，三处各实现一份 | `flow/state.py`、`story/context.mjs`、`adapters/story.js` | 部署环境的约定该由对接合同或配置声明，要定落点 |
| adapt 按 Demo 包名 `wallet-sdk-demo` 判对接层来源 | `adapt-scan.mjs`、adaptation SKILL | 要改成 manifest 声明的替身标记，涉及安装合同 |
| 扩展根与需求目录写死 `doc/extensions`、`doc/features` | hooks 多处、scripts 多处、合同标签 | 应从 `paths.*` 派生；改动面大 |
| 宿主 shell 写死 PowerShell（`shellArg` 引号规则、任务包的 `powershell` 围栏） | `story/drafts.mjs`、`spec/author.mjs` | 要定按运行环境选还是只支持一种 |
| 源码扩展名写死 `ets/ts/js/json5` | `knowledge.mjs` selfCheck、`ut/post_check.mjs` | 应从 profile 读 |
| 「端云 / TA / 风控」与 client_vocabulary 当作所有目标仓的前提 | `inputs.py` 骨架、`story-chapters.json`、合同 README | 是否改为可适配的数据要设计决定 |
| 章节名、小节清单在代码里写死一份（`DESIGN_HEADING_RE`、`SPEC_EXT_SECTIONS`、按「验收」「材料」字面找章） | plan/spec post_check、story check、appendix | 应从模板或合同读 |
| 表格解析实现了 6 次，「不涉及」判定 4 份，framework.config 读取器 3 份 | hooks/shared、spec/plan/review post_check、paths / chapters / language | 收敛是重构，放到 2.0.1 |
| `update.py` 写 `.last-prepare.json` 只为测试装置 | `flow/update.py`、`run_case.py` | 本轮 update 实跑靠它判检查点，实跑前不动 |
| `ut_layer` 与 `must.verify` 两个分派源 | framework acceptance 与扩展 | 要定两者关系与核对方式 |
| 判据编号 ①…⑮ 缺号乱序 | `story/check.mjs`、`adapt-scan.mjs` 与引用处 | 改成语义名要连同测试与作者文字一起改 |

## 4. 未验证

以上只有离线证据。与用例同形内容退出后对模型行为的影响，看本轮实跑。
