# `step-02-source-index`：原材料内容单元与稀疏初筛

## 目标结果

01 分册 §2–§7（S4 除外）落地：`core/story-sources.mjs` 提供 Markdown 定位、引用解析与视图构建函数；`story-build sources --feature <名> --stage before-spec` 生成 `source-index.json` 并首次落 `source-selection.json` 骨架（含 `basis`）；短 ID `<source-key>#<序号>`；源变化时报「旧 ID/旧范围 → 同标题路径新候选」并以 `--accept-source <key>` 显式刷新 basis；decisions 空容器初始化前移到初筛之前；S4 收口之后的作者指令送达「跑 sources → 读原文 → 填稀疏 selection → 进 Spec」。**不实现 collect，不生成 Spec 前视图**（01 §6）。v3 作者链在本步照常运行，是 01 分册允许的明确中间态；本步不发布、不跑正式效果比较。

## 前置与依赖

- 输入产物：step-01 之后的 `contract.design.origin` 与 `AR/story-src/sources/ar/rN.md`（01 §3 的「S4 原 AR 来源定位」从这里取，key `AR_ORIGINAL`）；`materials.json` 的 `file_digest` 口径；章节合同 `contracts/story-chapters.json` 的 `sources` 键与章 ID。
- 真实依赖：step-01（origin 字段与留存件）。
- 执行顺序：无。
- 就绪程度：可实施。

## 必读上下文

路径相对工程根 `E:\Project\SimulatedWalletForHmos`。

| 路径 | 加载时机 | 影响的决定 |
|---|---|---|
| `CLAUDE.md`、`test/story/AGENTS.md`、`test/story/TEST.md` §7、`99-执行者会话交接.md` §1/§5 | 共享已加载 | 同 step-01 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-Story写作流程重设计.md` §1–§4、§6、§7 | 本步新增 | 角色边界（脚本不判来源重要性）、退出清单时点、规模记录口径与基线数字 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-01-原材料与初筛.md` §2–§7 | 本步新增 | 文件所有权、切法、source-index / selection 合同、basis 与 `--accept-source`、命令输出格式、修改清单与验证六条——本步的全部合同 |
| `test/story/plan/2026-09-07-新需求四项/steps/02.3-02-整篇编排与成文.md` §1、§2（basis、预填 sources 段）、§5 谓词表、§6 提示词表 | 本步新增 | after-spec 是下一步的消费者：本步的索引与 selection 形状要让它能直接读；「selection 可读」谓词的定义在这里 |
| `doc/extensions/skills/story/scripts/core/story-build.mjs` :86–91、:389（`cmdInit`）、:1089（`withoutDiagrams`）、:3148（用法/`COMMANDS`） | 本步新增 | 已有围栏/标题能力复用点；decisions 骨架现在在 `cmdInit` :403 建；新命令怎么挂 |
| `doc/extensions/skills/story/scripts/core/materials.py` :35–62、:286–330 | 本步新增 | `SOURCE_DOCS` / `file_digest`（sha256 前 16 位 + `sha256:` 前缀）/ `build` 的 `sources` 字段——MJS 摘要要与它一致 |
| `doc/extensions/skills/story/scripts/core/story_flow.py` :81（`STORY_SRC_FROZEN`）、:971–1081（`next_step` / `scope_step`）、:1461（`contract.design`） | 本步新增 | 冻结名单先不动（03 分册再加 selection/template）；complete 之后 `next_step` 给什么动作（本步只加一句「跑 sources before-spec」，写作子步骤仍归 story-build，02 §5 末段） |
| `doc/extensions/skills/story/contracts/story-chapters.json` :5–45 | 本步新增 | `sources` 的 key 与 `required`；章 ID 值域（selection 的 `chapters` 合法性） |
| `doc/extensions/skills/story/SKILL.md`、`phases/story-write.md`（结构见 :6/:142/:200/:291/:333/:388） | 本步新增 | 只加「S4 收口后进初筛」一小段与入口指向；四段式重写留给 step-03（02 §6 表） |
| `test/story/golden/story-template-金样-AR90006-source-index.json`、`…-source-selection.json`、`test/story/fixtures/golden/AR90006-template/` | 本步新增 | 切片确定性测试的输入与期望（03 §6 末段：先按本期 ATX 规则核，不把人工索引未经核对当答案）；selection 样例是稀疏形态的对照 |
| `test/story/tests/test_material_rounds.py`、`test_writing_flow.py`、`test_s4_commit.py` | 本步新增 | 复用的临时夹具与 S1–S4 驱动方式 |
| `test/story/regression/mechanism-budget.yaml` | 条件：规模记录时 | 计数口径；`interim_ceiling: null` 只测量 |
| `test/story/scripts/check_failure_modes.py`、`TEST.md` §7.2–7.3 | 条件：改完提示词与注释后 | 交付面无历史叙述、无 Case 专名 |

共享内容未变且仍在上下文时复用，恢复时重载；宿主强制的 scoped 规则仍适用。

## 修改边界

- 负责：新建 `doc/extensions/skills/story/scripts/core/story-sources.mjs`（只提供解析、引用解析、视图构建函数）；`story-build.mjs` 加 `sources` 命令、`--stage before-spec`、`--accept-source`、NEXT/INPUT/RESULT 输出、decisions 初始化前移；`story_flow.py` 的 `next_step` 在 complete 之后指向 `story-build sources`；`SKILL.md` / `phases/story-write.md` 的初筛指令段；对应测试（允许新建一份本能力的独立测试文件，不建新平台）。
- 排除：after-spec、story-template、skeleton 视图正式接线、chapter/prepare 改动、v3 退出（全部 step-03）；`collect` 不实现；Spec 前视图不生成；knowledge 与 decisions 的内容协议。
- 公共规则：四道门见 `TEST.md` §7；注释与提示词按 `AGENTS.md` §5.3。

## 关键决定

- 已确定：01 §3 切法（围栏外 ATX H1–H6；最小节正文一单元、父级前导正文另一单元；`context` 只列各祖先前导正文范围，一基闭区间；只有标题无正文的父节不成单元；表/列表/围栏整体；无标题文件整份一单元；不做 setext、不做子范围）。
- 已确定：01 §4 合同（`sources[].kind/digest`、`units[].id/source/heading/start/end/context`、`images[]{id,path,source|null}`、ID `<key>#<n>`、`basis` 只在 sources 与选择/编排两侧）。
- 已确定：01 §5 稀疏 selection（默认 keep 不登记；只写 keep 归章 / omit 理由 / defer 问题 + decisions ID；空 items 合法）。
- 已确定：01 §4 末两段的源变化处理（错误输出逐项列变更文件、旧/新摘要、受影响坐标、同标题路径候选；`--accept-source` 只刷新指定源的 basis；不自动重绑）。
- 已确定：`story_flow.py status` 只给阶段级动作，不起 Node（02 §5 末段）。
- 已确定（reviewer 裁定，属内部组织）：本步给作者的初筛指令只写一段（S4 收口 → `story-build sources --stage before-spec` → 读 INPUT 列出的原文 → 填 selection → 进 Spec），放 `phases/story-write.md` 现有结构里一个独立小节并由 SKILL 指向；02 §6 的四段式重写在 step-03 一次做完，避免同一页改两遍。
- 设计任务：无。函数切分、正则实现、测试文件名由 executor 定。

## 验收

| 前置状态/触发 | 可观察结果 | 实际验证方法 | 完成阶段 |
|---|---|---|---|
| 金样输入目录（RR/SR/AR 原件 + `sources/ar` 形态）跑 `sources --stage before-spec` | 索引里每个单元的标题路径与行范围与 `…-source-index.json` 逐项对得上（按本期 ATX 规则核，差异逐条给理由）；`images[]` 五张有效图 `source` 指向首次出现单元，未被引用的图 `source: null` | 确定性测试，输入按既有临时夹具装配，不改 golden 正本 | 本步自动检查 |
| 含围栏内假标题、同名标题、无标题文件、父级前导表格的自造样例 | 假标题不切；同名标题各成单元且 `heading` 路径可区分；无标题文件一单元；父级表格在前导单元里不丢 | 新增用例（01 §7 验证 2） | 本步自动检查 |
| selection：空 items / 只写 omit+defer / 未知 ID / 重复 unit / 非法章 ID / 无理由 omit / defer 引用不存在的 decisions | 前两种通过；后五种被拒且报出坐标（01 §7 验证 3） | 新增用例 | 本步自动检查 |
| 只改一个源文件后重跑 `sources` | 该源单元重编号；错误输出列旧/新摘要、受影响 selection 坐标、同标题路径候选；selection 文件与 basis 未被改；`--accept-source <key>` 后只有该 key 的 basis 更新（01 §7 验证 5） | 新增用例 | 本步自动检查 |
| 视图构建函数对一个章 ID 与共享集合生成文本 | 相对链接与图片路径可读；公共正文只出现一次；未分配单元只有索引行（02 §3.1 规则） | 新增用例（函数级；正式落盘接线在 step-03） | 本步自动检查 |
| S1–S4 → complete 之后 `status` | `next` 指向 `story-build sources --stage before-spec`，不起 Node、不越过范围确认 | 用 `test_s4_commit` 的驱动方式加一例 | 本步自动检查 |
| decisions 初始化前移 | 初筛前 `decisions.json` 空容器已在；随后 `story-build init` 不清空已有条目；成文冻结后的保护仍在（`STORY_SRC_FROZEN`） | 既有 `test_writing_flow` 相关用例 + 新增一例 | 本步自动检查 |
| 过拟合 | 新代码与提示词零处出现 AR90006 金额、接口、章节措辞；`check_failure_modes` FAIL 0 | 脚本 + 人读 diff | 本步自动检查 |
| 四道门与规模 | 离线全量除金样 1 条外全绿；adapt-scan 通过；framework 零改动；`measure()` 前后值写进送审说明并按总方案 §7 口径拆到函数级 | `TEST.md` §7 | 本步自动检查 |

## 提交边界

- 纳入：`story-sources.mjs`、`story-build.mjs`、`story_flow.py`、`SKILL.md`、`phases/story-write.md`、测试文件；如新建测试夹具目录，随本笔。
- 排除：golden 正本；他人未提交改动；`98` / 本目录文件。
- 完成条件：验收全过；送审说明含规模表与「退出量为零」的如实说明（本步只加不退，退出在 step-03）；`approved_for_commit` 后提交。

## 停止条件

- 01 §3/§4 合同与 02 §2/§5 的消费者需求对不上（例如 after-spec 需要索引里没有的字段）时，`executor_question` 交 reviewer，由 reviewer 与方案作者修分册后再继续。
- 发现必须改 `framework/` 或必须扩大到 collect/视图落盘才能验证时停下。
