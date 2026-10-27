# 方案准备评审

> 2026-09-10，reviewer 会话（Fable）。方案正文在 `../steps/02.3-*.md` 四份，本目录只承载 implementation-loop 的步骤组织、评审记录与状态；不复制方案。

## 需求理解

- 目标：Story 写作链从「逐章重新理解 + 末尾统稿」换成「原材料初筛 → Spec 后整篇编排 → 按编排成文 → 写后核对」，S4 的输入/输出混用一并修掉；v3 草稿指导区、`context_chapters`、长 stdout 分发整体退出。最终效果按 03 分册 §7 由真实运行验收，本 loop 只闭合实现与确定性验收。
- 已确定设计：总方案 §1–§7；01 分册（S4 顺序提交、`story-sources.mjs`、短 ID + `basis`、稀疏 selection、`--accept-source`）；02 分册（story-template 合同与「编排调整规则」、structures 三种、skeleton 唯一视图写入口、prepare 六条谓词、提示词接线表、退出清单）；03 分册（写后核对、最终 check 条件、verifier 输入、冻结、确定性验收表、过拟合自查）。编码前须关闭的选择都已在分册里关闭；本轮评审对方案的意见已由方案作者写回分册，无平行版本。
- 范围与排除：只改 interactive Story 写作链与 S4；不动 knowledge 内容与适用协议（步骤 3）、审核点发现方法（步骤 4）、会议输入（步骤 5）；不改 `framework/`；总方案 §2「不做」清单全部有效。
- 验收：01 §7 六条、02 §7 十条、03 §6 十一行确定性验收、03 §5 整体退出核对、03 §8 过拟合自查。03 §7 行为验收由用户启动真实 CLI，不在 loop 的自动检查内，最终报告如实标「行为待验」。
- 未决事项：① 金样 11 个未提交文件入不入库、要不要登记进 `EXPECTED_CANONICAL_FILES`，待用户裁定；在此之前离线全量恒有 `test_golden_sample` 1 红，各步验收按「除该条外全绿」判。② 本目录在 `.gitignore`（`test/story/plan/`），最终 `complete-report --commit` 要求提交 `FINAL_REVIEW.md`，与用户 2026-09-06「设计件不入库、评审会话不提交」的裁定冲突；到 step-04 收口时请用户裁定（force-add 一份报告，或以 executor 的最后一笔实现提交作为报告引用）。③ 无其它待 Human 的真实取舍。

## 工程与上下文发现

- 实施工程根：`E:\Project\SimulatedWalletForHmos`（当前 checkout 的 Git 根，分支 `story`，HEAD `804db2d3`）。
- 全需求共享入口：项目 `CLAUDE.md`（宿主已加载）；`test/story/AGENTS.md`（2026-09-10 用户授权重写版：§1 角色「维护实施者 / 执行者」、§5.3 交付面通用性、§7.5 规模预算、§8 完成前自检）；`test/story/TEST.md` §7 离线验证（四道门：`pytest test/story/tests -n auto --dist loadscope`、`check_failure_modes.py`、`adapt-scan --check --target . --package .`、`git status framework/`）、§7.2–7.3 过拟合扫描；`test/story/regression/mechanism-budget.yaml`（`interim_ceiling: null`，只测量不设限，每步记录前后值）；`../99-执行者会话交接.md` §1 红线与 §5 只在对话里存在的事（heredoc 吃反斜杠、失效形态比单测严、`PYTHONIOENCODING=utf-8`）。
- 步骤上下文：逐项写在各步「必读上下文」表，区分共享 / 本步新增 / 条件材料。
- 未找到或冲突：无缺失。一个事实提示：`reviews/` 的编号在 `../reviews/` 里 20/21 各有两份（实施线与效果线），按文件名认，本目录的 review 用 step-id 命名，不与之混。

## 方案判断

- 模式：`accepted_existing`
- 判断依据：2.3 总方案 §5 已把需求切成 01/02/03 三份分册，每份写明独立交付目标、修改清单与验收；01 分册 §1 末段与 §7 又规定「S4 作为第一个独立实施提交，通过后才实现来源索引」，且 S4 已提交（`804db2d3`）并评审（`../reviews/25`，通过附 R1–R3）。因此步骤 = S4 返修（step-01）、来源索引（step-02）、02 分册（step-03）、03 分册（step-04），与方案自己的提交边界一致，不是新拆分。
- 覆盖核对：01 §1 → step-01（返修）；01 §2–§7 → step-02；02 §1–§7 → step-03；03 §1–§6、§8、§9 → step-04；03 §7 → 用户启动的真实运行（后置，最终报告标注）；总方案 §6 退出清单 → step-03 执行、step-04 核对归零；总方案 §7 规模记录 → 每步 closeout。
- 依赖与提交核对：step-02 依赖 step-01 落下的 `contract.design.origin` 与 `sources/ar/rN.md`（01 §3 的「S4 原 AR 来源定位」读它们）；step-03 依赖 step-02 的 source-index / selection / basis 合同与 `story-sources.mjs` 的解析函数；step-04 依赖 step-03 的 template、视图与 prepare。每步一笔提交即可独立说明与验证：step-01 是纯返修；step-02 接入输入侧而 v3 作者链照常运行（01 分册允许的明确中间态）；step-03 切换作者入口并退出 v3（02 分册要求不兼容两条链，所以不能再拆到「v3 半退」）；step-04 只加核对与接线。
- 就绪核对：四步都有分册级设计，近期两步可直接实施。step-03 是大步（估算净 +200～+400 行加提示词重写），送审前 executor 可用 `executor_question` 提议拆成「输入侧接入」与「作者入口切换 + 退出」两笔，reviewer 在问答里裁决并同步 STATUS；不拆也合法。step-04 无设计任务，只有一个 Human 决定（FINAL_REVIEW 入库方式）。
- 执行推演：S4 返修的输入（`../reviews/25` §4 复现步骤）与反例（half_commit 后改稿）已给出；来源索引的生产者是 `story-build sources`、消费者是 step-03 的 after-spec / skeleton，step-02 内以 `test/story/fixtures/golden/AR90006-template/` 输入做切片确定性验证（03 §6 末段允许）；step-03 的反例（缺列 / 改图类型 / 图片错节 / 未声明标题不拦 / 修改编排不覆盖正文）在 02 §7 与 03 §6 列全；step-04 的反例（报告 PASS 而 reviewVerdict FAIL、退出项零命中）在 03 §6。缺口未发现；发现即回对应分册改，不另建质量报告。

## 授权与确认

- 用户 2026-09-10 接受「原材料初筛→Spec 后增量整理与整篇编排→按编排成文」方向并授权制定 2.3 方案（总方案文件头）；方案作者已按三轮评审意见改到位（`../reviews/` 无独立编号，意见直接写回分册，按 [[plan-author-edits-directly]] 惯例）。
- 用户本轮（2026-09-10）指定本会话为 reviewer 并按 implementation-loop 继续本需求；executor 由用户另建会话。
- 预算：用户 2026-09-10 裁定 Step2.3 期间 `interim_ceiling: null`，只测量不设限；最终期望总量下降，未降须专项审视旧职责退出。executor 不得改预算文件。
- `AGENTS.md` / `TEST.md` 2026-09-10 的重写已由用户确认授权，按新版执行。
- 本模式为沿用既有拆分，无需再取确认。仅审查不构成实施授权的条款不适用：实施授权来自上述 2.3 方案授权与本轮 loop 启动。
