# AGENTS.md 重构：逐节有用性分析与结果

> 日期：2026-09-14。基线 HEAD `b4984fd7`。状态：已实施，等待用户审阅；未提交。

## 判定尺度

用户级 AGENTS 承担跨项目的角色、方法、工作和交付要求；项目级只承担产品目标、当前能力、职责、事实来源、项目约束和维护入口。
每段按四问判定：是否本项目特有；维护者在哪个动作前需要它；有没有实际消费者；是否与仓库现状一致。

## 分析结论

### 与用户级重叠（删除）

§1 引言与角色边界列、§1.2 消费模型通用定义、§4.4 第 1–2 条、§7.1 第 2–4 条、§7.2 全部、§7.3 全部、§7.4 通用部分、§8 七条。
逐句对应见 [03-AGENTS逐句迁移清单.md](03-AGENTS逐句迁移清单.md)。

### 消费矩阵（谁在用）

- §7.5 是全仓唯一被机械消费的节（`tests/test_mechanism_budget.py` 把「按 AGENTS §x」拼进断言失败信息），另有预算 yaml 3 处注释、
  旧机制退场目录约 30 处方案引用、TEST 3 处。
- §3 所有权表、§7.4 分层证据全仓零引用；§4.4 只在「保留不动」一句里出现过。
- §5.3 被 `check_failure_modes.py` docstring 与 TEST §7.3 引用；§4.2 被预算 yaml 注释引用。
- `regression/failure-modes.yaml` 6 条 clause 引用的是 2026-08-25 旧版 §2「维护不变量」的**条款名**（机制层零测试特征、正向实现不打补丁、
  引用必须真实存在、知识不含维护信息定位只写一处、声明不是应用、显式不适用优于静默跳过），重构前的文件里一个都不存在，
  `check_failure_modes.py:451`、`run_case.py:20` 同样引旧节。`clause` 字段无机器消费者，漂移不会被任何回归发现。
- 方案文档把 §4.1/§4.2/§4.3/§6 当作特性「需求依据」（FEATURES.md）和设计约束输入（03-知识协议）。

### 与仓库现状不符（已修正）

| 旧陈述 | 实际 | 新写法 |
|---|---|---|
| 知识正文不写消费阶段坐标 | `design-patterns/decision-tree.md:19,52,63,164-168`、`page-interaction.md`、`constraints/compatibility-checklist.md:22`、`deliverables.md:27` 写了「读者：plan」和按阶段完成判据表 | 条目可写适用阶段、读者与完成判据，不写落点坐标（章节号、契约字段路径、表名）。用户决定改规则不改知识 |
| 知识正文不给维护者讲如何维护 knowledge | `knowledge/facts/README.md`、`design-patterns/README.md` 含维护说明，二者 `kind: index` | 维护说明只在各类 README（index）与 AGENTS |
| 按 drift 具名长期放行；`init.task_decision` 选保留 | `framework.config.json:126-138` 的 `integrity.drift_allowlist` 在 vendored 3.0.0 已退役、读取即忽略（`framework/MIGRATION.md:259`） | 写明已退役；保留靠 UPDATE 时逐文件选「保留」 |
| `.opencode/` 不进 story-adaptation 的包 | `manifest.yaml` `provides.bridges` 含 `.opencode/skill/story/SKILL.md`，`adapt-scan.mjs` 写进目标仓 | 不进包的是 `agent/verifier.md` 与 framework opencode adapter 改动 |
| 机制层含 overlays、scripts 目录 | 实际为 `rules/*.overlay.yaml`、`hooks/**`、`skills/story/scripts/` | 按实际命名 |
| headless/goal 不进入当前范围 | framework 完整支持三模式，本仓已物化 goal-mode 跳板；Extension 零涉及 | 「framework 具备，Extension 维护范围不含」 |

## 新结构

| 节 | 内容 | 来源 |
|---|---|---|
| 0 入口 | 需求定位、TEST 入口、历史入口、运行模式范围 | 旧 §0 |
| 1 本项目的角色职责 | 两行职责表、被维护对象与直接检查、宿主指向 TEST §0.2、消费模型三点 | 旧 §0、§1 |
| 2 产品定位与所有权 | AI Agent 系统与行为链、所有权表、归属句、本仓特殊事实三条 | 旧 §2、§3 |
| 3 不变量（3.1 Agent-first / 3.2 Extension 结构 / 3.3 Knowledge） | 命名条款，与 failure-modes clause 对齐 | 旧 §4–§6、§7.2 特有句 |
| 4 验收 | 设计闭合、分层证据、指向 TEST §8.1/§7 | 旧 §4.4、§7.4 |
| 5 维护预算与分级复核 | 规则、阈值、权限、接线状态全保留，去掉重复的送达论证 | 旧 §7.5 |

## 引用同步

| 文件 | 改动 |
|---|---|
| `regression/failure-modes.yaml` | 6 条 clause「AGENTS.md §2/§2.1」→「§3」，条款名不变 |
| `scripts/check_failure_modes.py` | 3 处 docstring/注释：§2 → §3；§5.3 → §3「机制层零测试特征」 |
| `scripts/run_case.py` | 模块 docstring「按 AGENTS.md §5 自己做」→「维护设计者按 AGENTS.md §4 与 TEST.md §8」 |
| `tests/test_mechanism_budget.py`（在途，用户同意） | docstring 与 REMINDER 的「§7.5」→「§5」 |
| `regression/mechanism-budget.yaml`（在途，用户同意） | 「§7.5」→「§5」；「AGENTS §4.2」→「§3.1「模型与脚本按能力分工」」 |
| `TEST.md` | §7.3「§5.3」→「§3「机制层零测试特征」」；§8 三处「§7.5」→「§5」 |
| `plan/2026-09-11-*` 约 30 处 `#75-…` 锚点 | 历史过程稿，不改 |

## 篇幅

| 版本 | 字符 |
|---|---|
| HEAD | 11775 |
| 上一轮精简 | 11420 |
| 本轮（独立核对修回后） | 约 9100 |

## 验收

| 检查 | 结果 |
|---|---|
| `pytest test/story/tests -n auto --dist loadscope -q` | 962 passed, 284 subtests |
| `check_failure_modes.py`（`PYTHONIOENCODING=utf-8`） | 形态 64 条：FAIL 0，委派 8，PASS 56。在默认 GBK 控制台下脚本打印 `⑫` 类字符会 UnicodeEncodeError，HEAD 版本同样如此，与本次改动无关 |
| `git diff --check`、`py_compile` | 通过 |
| 残留旧节号引用扫描（§7.5/§5.3/§4.2/§2） | 无 |
| 独立逐句核对（旧 AGENTS → 新 AGENTS + 用户级 + TEST） | §5 预算节规则、阈值、权限、接线状态逐句保留；不变量名与 failure-modes clause 逐字一致；内部引用无错位；事实陈述有证据。首轮发现 15 处弱化、7 处「用户级未覆盖」、1 处路径错误、1 处混入 WalletKit 项目措辞，已全部修回：补回预算「先推演再估量」、流程审视四项、安全边界落盘、允许补充关系、控制层表、合理成本、过拟合自查三项、Story/Review 完整性判据、旧称「执行者」映射、启动前读运行协议、独立会话一次一步与只能声明已实施、评审拒绝给依据、TEST §10 评价范围、只运行授权验证；framework 差异路径改为 `framework/agents/opencode/...`；「机制层零测试特征」恢复 Story 原措辞（机制层与注入件不含 Case 单号、业务名或需求特征）。保留的三处有意新增：知识维护说明定位规则、允许写适用阶段（用户决定）、「声明不是应用」与「正向实现」按旧版 §2 条款定义补细则以对齐 clause |
| 修回后回归 `-k "mechanism_budget or requirement_system or OperatorProtocol"` | 28 passed |
