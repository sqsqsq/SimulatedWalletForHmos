# `step-03-appendix-image`：附录与图片旧检查退场

## 目标结果

02.4-03 分册落地：R07 用现行 `appendixProjection` 的纯计算做一条**只读**机器区比对路径，由 `check` 调用，覆盖后删除 ⑦ 的规约行再解析与 ⑫b 的首列集合比较；R11 删 `story_image_dir` / `archiveDir` / `inArchive` 与未登记副本字节搜图放行，`sameBytes` 若再无消费者随之退场；R15 删材料清单 `proseBlocks(...).slice(1)` 段数约束与合同对应配额。**不删**投影生成、机器区手改保护、附录五节、单独 check 与 offline 结构模式；**不删、不移动**任何业务图片文件。

## 前置与依赖

- 输入产物：step-02 之后的 HEAD。
- 真实依赖：无（附录/图片判据与编排协议无耦合）。
- 执行顺序：step-02 之后。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根；行号按 HEAD `5203ca30`，实施前按符号重核。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| 共享入口（同 step-02 第一、二行） | 共享已加载 | 同上 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.4-03-附录与图片旧检查退场.md` 全文 | 本步新增 | 本步全部合同；§3.1 明写只读比对的区分力只在**不先 project 的单独 check 与 `check --deliver`**，测试须断言新比对的具体诊断 |
| `doc/extensions/skills/story/scripts/core/story-build.mjs` `cmdCheck` :1785 内 ⑦ :1933、④ :1983（`archiveDir` :2013）、⑫ listOnly :2197、⑫b :2221；`zoneHandEdited` :1503；`appendixProjection` :2757；`cmdProject` :2880（手改拒绝）；`verdictSkeleton` :2897；`sameBytes` :1134 | 本步新增 | 要接替与要删的代码、可复用的区块定位与手改保护 |
| `doc/extensions/skills/story/scripts/core/story_flow.py` `cmd_story`（project → number → build → check）、`cmd_archived`（`check --deliver`） | 本步新增 | 为什么登记链里比对恒相等、`--deliver` 才是有区分力的入口 |
| `doc/extensions/skills/story/contracts/story-chapters.json` `subsection_form` :197、`material_dirs` :374、`story_image_dir` :381–:382 | 本步新增 | R15 的合同配额、R11 的专属字段 |
| `doc/extensions/skills/story/scripts/core/import_sources.py` :396/:652、`materials.py` :45–:47/:264 | 条件：R11 时 | 证明 `<feature>/assets/<源文档名>/` 是登记过的材料目录，与 `AR/assets` 不是一回事 |
| `test/story/tests/test_final_check.py`、`test_negative_guards.py`、`test_image_registration.py`、`test_material_delivery.py` | 本步新增 | 旧行核对与旁路的用例迁到同一读写合同 |

## 修改边界

- 负责：`story-build.mjs` 的 check ⑦/⑫b/④/⑫、只读比对路径；合同两处字段；相关测试。
- 排除：`project` 的写入逻辑与投影算法；`--offline` 语义；图片导入/注册；编排协议（step-02）；知识（step-04）。
- 公共规则：四道门见 `TEST.md` §7。

## 关键决定

- 已确定（分册 §3.1）：比对范围只含机器生成正文，作者解释区与材料贡献说明不参与；换行沿用现有口径；真源缺失不降成空成功；check 绝不写盘。
- 已确定（分册 §3.1）：投影生成器自身正确性由独立期望的测试验证，不以「函数输出等于自身输出」代替。
- 已确定（分册 §3.2）：删的是「只因放在特殊目录就可不登记」的机制，已登记的任意合法路径（含已登记的 `AR/assets`）继续通过。
- 设计任务：无。只读比对函数的切分与命名由 executor 定。

## 验收

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 已登记 Story，**不先 project**，直接改机器区：删一行 / 改非首列值 / 加错行 / 破坏边界标记 / 作者手改 | 单独 `check` 与 `check --deliver` 各给出具体诊断（哪一节、哪一类不一致），不是笼统退出码 | 新增用例，断言诊断文案 | 本步自动检查 |
| Spec §9 或 knowledge-use 更新后不重投 | 单独 check 报「实际区块与当前投影不一致」并给修真源/重投出口 | 新增用例 | 本步自动检查 |
| 经 `story_flow.py story` 正常登记 | 通过；check 前后 story.md 逐字节不变 | 既有用例 + 字节比对 | 本步自动检查 |
| 作者解释区措辞变化、材料清单两段必要来源说明 | 不报 | 新增用例 | 本步自动检查 |
| 未登记副本放在 `AR/assets` / 同图登记后引用 / 引用已登记的 UX 图 | 前者拒绝，后两者通过；图文件零删除 | 旧旁路用例改写 | 本步自动检查 |
| 漏材料、错链、非原始文件列成来源 | 仍被拦 | 既有用例 | 本步自动检查 |
| 四道门与规模 | 全绿；`measure()` 前后值写进 closeout | `TEST.md` §7 | 本步自动检查 |

## 提交边界

- 纳入：`story-build.mjs`、合同、测试。
- 排除：业务图片文件；本目录文件。
- 完成条件：验收全过；`approved_for_commit` 后提交。

## 停止条件

- 发现只读比对必须让 check 写盘、或必须另存一份附录状态文件才能实现时停下交 reviewer。
- 发现 `sameBytes` 还有 ④ 之外的消费者时不删，记入 closeout。
