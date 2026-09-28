# 方案准备评审

> 2026-09-11，reviewer 会话（Fable，同 2.3 那轮）。方案正文是 `../steps/02.4-旧机制退场清理.md` 与五份分册 `02.4-01`…`02.4-05`，本目录只承载 implementation-loop 的步骤组织、评审记录与状态；不复制方案。

## 需求理解

- 目标：清理整个 Extension 演进中尚未退出的旧职责、旧配套规则与重复实现（R01–R23），同步关闭三项已确认功能缺口（D01–D03），保持功能全集（`../../2026-09-11-Extension功能全集与机制归属/FEATURES.md` 50 节点）完整；收口时三份 FEATURE 文档正式移回 `test/story/`。
- 已确定设计：总览 §1 三条清理依据、§4 退到哪里、§6 执行者边界、§7 规模口径、§9 评审采纳；五份分册各自的「逐项动作边界」「固定分工」与「本步验证」。评审六处（`../../2026-09-11-Extension功能全集与机制归属/03-评审·梳理与Step2.4方案.md` §2）已由方案作者并入分册，无平行版本。
- 范围与排除：只改 `doc/extensions` 与 `test/story` 的测试/检查器；不动 `framework/`、knowledge 业务正文、远程需求数据、历史 Story；不实施步骤 3/4/5（知识协议升级、决策发现算法、会议转写）；不新增用户功能；不改预算文件。
- 验收：每份分册的「本步验证」；总览 §8 完成条件（R01–R23 逐项有处理/接替/验证及提交；D01–D03 单列闭合；05 的六条功能链完整；离线与适配检查通过且 Framework 无修改）。真实 CLI 由用户按 `TEST.md` 启动，不在 loop 的自动检查内，最终报告标「行为待验」。
- 未决事项：无待 Human 的真实取舍。两件事实：① 本目录在 `.gitignore`，`FINAL_REVIEW.md` 不入库（2.3 同样处理，沿用）；② `test/story/AGENTS.md` 有一处用户自己的未提交改动（链到本轮分析入口），不属任何步骤，随维护者决定提交。

## 工程与上下文发现

- 实施工程根：`E:\Project\SimulatedWalletForHmos`（分支 `story`，HEAD `5203ca30`）。
- 全需求共享入口：项目 `CLAUDE.md`；`test/story/AGENTS.md`（维护角色、§5.3 交付面通用性、§7.5 预算、§8 自检）；`test/story/TEST.md` §7 四道门（`pytest test/story/tests -n auto --dist loadscope`、`check_failure_modes.py`、`adapt-scan.mjs --check --target . --package .`、`git status framework/`）；`test/story/regression/mechanism-budget.yaml`（`interim_ceiling: null` 只测量，`test_mechanism_budget.measure()` 记前后值）；`../99-执行者会话交接.md` §1/§5（heredoc 吃反斜杠、`PYTHONIOENCODING=utf-8`）。
- 步骤上下文：逐项写在各步「必读上下文」表；行号按 HEAD `5203ca30`，实施前按符号重核（总览 §6）。
- 未找到或冲突：无。

## 方案判断

- 模式：`accepted_existing`
- 判断依据：总览 §3 已把 R01–R23 切成五步（01 入口与来源 → 02 作者输入与审查 → 03 附录与图片 → 04 知识协议与验证桥接 → 05 全链退场与完整性验收），每步写明清理对象、可清理理由与独立完成条件，顺序 01→02→03→04→05、05 做合并收口。这就是既有拆分，不改。
- 与 loop 外进度的衔接：**01 与 02 已在 loop 建立前完成并提交**——01：`d97e2701` + 返修 `f1f83c20`，评审见 `../steps/02.4-01-评审.md`（已关闭）；02：`5203ca30`，交回见 `../steps/02.4-02-交回.md`，**尚未评审**。因此 loop 从 `step-02` 起：executor 加入后不重做实现，直接以 `5203ca30` 送审；reviewer 评审后批准或要求返修（返修另起提交，与 01-R1 同法）。01 不进事件日志，只在 STATUS 记为 loop 外完成。
- 覆盖核对：R01/R03/R04/R05/R08/R13 → 01（已完成）；R02/R09/R10/R12/R14/R20/R21 → step-02；R07/R11/R15 → step-03；R06/R16/R17/R19/R22/R23 + D01/D02/D03 → step-04；R18 + 六条功能链反查 + 三份 FEATURE 正式启用 → step-05。
- 依赖与提交核对：step-03 不依赖 02 的产物（附录/图片判据与编排协议无耦合），只是执行顺序；step-04 同理；step-05 依赖前四步全部提交（它做消费者反查与映射更新）。每步一笔提交可独立说明与验证；返修提交允许。
- 就绪核对：02/03/04 分册都到「逐项动作边界 + 固定分工 + 本步验证」的程度，可直接实施；05 是收口步，输入是前四步的实际 diff，完成条件在分册 §5/§6 写全，无设计任务。
- 执行推演：02 的反例在分册 §4（坏围栏两侧同判、多路径一任务、erDiagram 进 structures 报错）；03 的反例在 §4（不先 project 的单独 check 与 `--deliver` 下少行/改值/增错行/手改都出具体诊断）；04 的反例在 §4（同 rule 两 AC、criteria/boundaries 同 rule、坏 YAML、AC 样例 ID 在 UT/testing 端能找到）；05 的反查在 §3。缺口发现即回分册改，不另建质量报告。

## 授权与确认

- 用户 2026-09-11 要求制定 Step2.4（总览文件头）；评审六处并入后用户确认「可以进入实施」；01、02 已由用户另建的执行者会话实施并提交。
- 用户本轮指定本会话为 reviewer，按 implementation-loop 继续本需求；executor 由用户另建会话。
- 预算：沿用 2.3 期间 `interim_ceiling: null` 只测量的裁定（总览 §7 明写不新增峰值、不重签 target、不改预算文件）。
- 本模式为沿用既有拆分，无需再取确认。实施授权来自上述 Step2.4 制定授权与本轮 loop 启动，不是「仅审查」。
