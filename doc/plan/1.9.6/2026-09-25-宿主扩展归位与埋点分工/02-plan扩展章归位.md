# 02 plan 扩展章归位

前置与决定见[总览](00-总览.md)。埋点小节的内容组织见 03；本分册只定位置、编号与「决策先于设计」的保证方式。

## 1. 编号映射

| 旧 | 新 |
|---|---|
| `## 知识决策（设计输入）`，排在 §1 之前 | `### 9.1 知识决策（设计输入）`，挂在 `## 9. 宿主扩展` 下 |
| `### 设计模式选型` / `### 规约义务` / `### 项目知识影响` | `#### 9.1.1` / `#### 9.1.2` / `#### 9.1.3` |
| `### 埋点`，在「## 6. 服务层接口定义」下 | `### 9.2 埋点` |
| 空的「## 宿主扩展（可选）」 | `## 9. 宿主扩展` |

## 2. 「决策先于设计」怎样保留

旧设计靠文件位置保证：知识决策排在设计章之前，门禁核行号（`hooks/plan/post_check.mjs:37–58、266–272`）。理由是「排在设计之后只是事后声明」，而实跑也证实模型是整篇一次写出 plan 的。

改后位置在末尾，这件事改由流程与内容保证：

- **plan 任务包**（`hooks/plan/author.mjs`）：第 1 节后写明「先写 9.1 知识决策：设计模式选型、规约义务、项目知识影响；再按它写设计章 1–8；设计章里的实体与方法照 9.1 定」。
- **plan 作者页**（`hooks/plan/author.md` 24 行的 ①）：改为「9.1 知识决策是设计输入，先写它，再写设计章；设计章要能看出按它展开」。
- **门禁**（`hooks/plan/post_check.mjs`）：
  - 去掉 `DESIGN_HEADING_RE` 与「知识决策在设计章之前」的行号比较；
  - 改为核「9.1 在『9. 宿主扩展』下、三节齐全」。
  - 与契约一致的核法已存在，不变：规约义务行与 `must` 一致、选型与 `files[].pattern` 一致。
- **审查**：`rules/plan-rules.overlay.yaml:35` 已有「只在『知识决策』章声明、设计章里看不出痕迹的，是没落地」，改为指向 9.1，这条正是内容上的「先于设计」判据。

权衡：先后顺序由任务包与作者页在动笔那一刻说清，审查按设计章是否体现 9.1 判。实跑观察项加一条：plan 的 9.1 是否先于设计章写出（runlog 的 write 顺序），见 04。

## 3. 改动清单

| 位置 | 改为 |
|---|---|
| `skills/story/templates/plan-sections.md:2–45` | 「## 9. 宿主扩展」、「### 9.1 知识决策（设计输入）」、9.1.1–9.1.3 骨架；头注释写明位置在 §8 之后，并说明先写 9.1 |
| `skills/story/templates/plan-sections.md:106–135` | 「### 9.2 埋点」，挂在「9. 宿主扩展」下；内容组织按 03 |
| `hooks/plan/post_check.mjs:37–58、148、245–272` | 如上；提示语里的「知识决策（设计输入）章」改为「9.1 知识决策」 |
| `hooks/plan/post_check.mjs:443–461` 埋点逐统计点 | 提示「在服务层接口定义章下」改为「在 9.2 埋点」 |
| `hooks/shared/stat-points.mjs:70–84` `planStatRows` | 按名字找「宿主扩展」下的「埋点」，不限层级；注释「挂在服务层接口定义章下」退出 |
| `hooks/shared/chapters.mjs` 章号核对 | plan 扩展模板主章改为「9. 宿主扩展」 |
| `hooks/plan/author.md`：12、24、43、53、58 行 | 位置与编号按映射改 |
| `hooks/plan/author.mjs:40–71` | 第 2 节标题「埋点」指向 9.2；末句「契约挂法与『知识决策』章骨架」改为「9.1、9.2 骨架」；加第 2 节的先后说明 |
| `hooks/shared/pre_verifier.mjs:62` 与 plan 片段 | 「plan 埋点小节」改为「plan 9.2 埋点」 |
| `rules/plan-rules.overlay.yaml:18、24、35` | 指向 9.1、9.2 |

### 测试与夹具

- `fixtures/failure-modes/P06-knowledge-decision-after-design`：按新结构改为「9.1 缺节或不在锚点下」这一失效形态，good/bad 重做；fixture 目录改名，同步改 `failure-modes.yaml` 条目。
- `fixtures/failure-modes/P17-landing-md-yaml-mismatch`、P05 等含「知识决策」的 plan 夹具：换成新结构。
- 内嵌 plan 的测试：
  - `test_indicator_reporting.py` 的 `PLAN` 常量；
  - `test_gate_groups.py`、`test_knowledge_protocol.py`、`test_neutral_knowledge.py`、`test_story_build.py`、`test_plan_pattern_crosscheck.py`（路径问题见 01）。
- 新增：
  - 9.1 在锚点下、三节齐全时通过；
  - 旧的 §1 之前写法被拒，并提示新位置；
  - 埋点写在服务层接口定义章下被拒，提示写到 9.2。

## 4. 失败处理

- 缺「9. 宿主扩展」：报「缺『9. 宿主扩展』章：知识决策与埋点写在它下面」。
- 9.1 缺某节：逐节报。
- 不走 /story 的需求：9.1 照常要求（知识决策对所有需求生效，与现行一致）；9.2 按现有 `statDesignState` 的四种状态处理，不变。
