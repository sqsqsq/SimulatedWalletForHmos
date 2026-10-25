# 01 · story 适配指南方案（ADAPTATION.md）

> 读者：本方案的评审者与实施者。运行 story/spec 的模型不读本文件。

## 1. 问题

「把 story 移植/适配到别的工程要做什么」「规约怎么维护」这两类信息目前散落多处、互相矛盾、部分过期：

| 位置 | 内容 | 问题 |
|---|---|---|
| `AIDefectHelpler\docs\archive\需求开发\story使用指南.md` §7（135–192 行） | 复制清单 + 六处适配 + 自检 | **面向人**不面向 AI；过期 3 处（缺 `.codex` 跳板、缺 codebase-facts、规约维护指向已错） |
| `doc/extensions/knowledge/codebase-facts.md` 16–29 行「怎么维护」 | confirmed 协议、回灌、换工程重写 | 维护指导混进运行时知识 |
| `doc/extensions/knowledge/component-profile.md` 头注 11 行 | 「部件事实变化改本文件」 | 同上（轻度） |
| `doc/extensions/knowledge/constraints-source/AGENTS.md` | 规约维护全流程（147 行） | 依附于未归档的两层生成式设计；只讲本仓维护，不讲换工程 |
| `test/story/DELIVERY.md` + `export_delivery_patch.py` | patch 交付机制与交接项 | **交付方式已变**：story 代码已提交代码仓，patch 中转不再存在 |

用户裁决与诉求：适配指南**面向 AI**（内网模型按真实代码仓做针对性适配）、**像规约一样集中一份**、可让掌握真实仓的模型确认准确性；使用指南不再承载复用说明；**story 下的产物都是指导模型做需求开发的，不是指导模型维护这些产物**；交付即代码仓；规约机制简化为单层。

## 2. 定位：读者三分

`test/story/AGENTS.md` §1.0 现行分层是「交付物面向模型（运行期）／维护面向人（test/story）」。适配与维护动作的执行者是**第三类读者：适配/维护期的 AI**——它按目标仓现状改写画像与样板、按维护纪律修订规约。三类读者三个落点：

| 读者 | 读什么 | 落点 |
|---|---|---|
| 运行期模型 | 该做什么、怎么做、判据是什么 | `skills/story/**`、`hooks/**`、`knowledge/`（运行时知识） |
| 适配/维护期 AI | 换工程改哪些、怎么验证改对了；规约与画像怎么维护 | **`doc/extensions/ADAPTATION.md`（唯一落点）** |
| 评测维护的人 | 为什么这么设计、改过什么、踩过什么坑 | `test/story/`（EVOLUTION / AGENTS） |

产物红线不放宽：`skills/story/**` 与 `hooks/**` 仍不得出现任何维护/交接语义；所有适配与维护语义集中到 ADAPTATION.md 一个文件。

## 3. 交付形态：代码仓 + ADAPTATION

story 的交付方式是**代码仓本身**：内网拉仓（或同步仓内容）后，第一入口是 `doc/extensions/ADAPTATION.md`，按其中清单完成适配。

- **落点**：`doc/extensions/ADAPTATION.md`，单文件。在扩展包内、随仓走；不在 `test_product_reader_purity.py` 扫描面（`skills/story/**` + `hooks/**`）内。
- **不进 `manifest.yaml`**：它不是运行时知识，不被任何阶段注入。
- **适配清单的唯一载体**：ADAPTATION 说明哪些目录直接复用（`doc/extensions/` 整包，剔除 `wallet-sdk-onboarding`）、三份跳板（`.claude/commands/story.md`、`.codex/skills/story/SKILL.md`、`.opencode/skill/story/SKILL.md`）；`mock-data` 与 `SKILL-ori.md` 等本地评测材料不属于复用面。
- 看护：清单里的路径必须真实存在（机械断言，防清单腐烂）。

## 4. 内容结构（章节骨架）

面向 AI、按动作组织，每项给「改什么 / 判据是什么 / 怎么验证改对了」：

```
0. 读者与触发        —— 何时读本文件：拉仓适配 / 换目标工程 / 维护规约与画像
1. 移植前提          —— 同一 framework 实例（spec 阶段链、lifecycle_hooks_enabled: true）
2. 复制清单          —— 直接复用的目录与三份跳板；与 story 无关的排除项
3. 逐项适配
   3.1 工程画像整篇重写（两份）：component-profile.md、codebase-facts.md
       —— 实扫目标仓生成、不许照抄或凭平台常识填；confirmed 协议（初始未确认→
          掌握真实仓的人/模型核对后转已确认）；「没有」必须是核对过的结论；特征不列实例
   3.2 应用域规约（constraints/）：域名与编号体系不变则六份 overlay 零改；
       非 HarmonyOS 工程按维护章（§5）重写条目
   3.3 设计模式样板重写：design-patterns 两份模式文档按目标仓真实 SDK/惯例重写
       （对接 02 方案；与画像同款「整篇重写、规则与脚本零改」）
   3.4 spec 注入件换例：hooks/spec/on_context_load.md 中的业务示例
   3.5 manifest.yaml：name/version/description、provides 与实际提供物一致
   3.6 framework.config.json 核对（不复制）：paths.extension_dir / paths.features_dir /
       lifecycle_hooks_enabled；architecture.outer_layers 供 lint-rules 运行时推导;
       spec 形态声明核对（story-chapters.json 的编号/表头段，见 04 方案 P2）
   3.7 跳板补齐：按 framework.config.json 的 materialized_adapters
4. 机械自检          —— --phase extensions 扩展校验 → 本地单（非 AR 前缀）跑通
                        init/定范围/spec 三产物 → 真实 AR 单跑通 init/归档链路
5. 规约维护          —— 新增（域 / 条目两级）/ 更新 / 删除 / 换工程四个动作的操作与纪律：
                        constraints/ 是唯一真源，直接维护；编号一经分配不复用；
                        未验证条目不入库（核实来源后才进）；新增域同步 README 文件清单
                        与适用矩阵行，条目变更同步适用矩阵；声明了消费阶段就必须有
                        manifest 挂载（test_constraint_consumption 看护）
6. 画像与样板维护    —— 回灌（取证发现不符→修订并退回未确认）、样板与 SDK 版本对齐
```

## 5. 规约机制：单层可维护

`knowledge/constraints/` 是规约的**唯一真源，直接维护**。README（字段模型、执行体、适用矩阵、文件清单）与六份域文件即维护对象；维护纪律全部在 ADAPTATION §5。

两层生成式套件（`constraints-source/` 九域 + `generate.py` + 其 `AGENTS.md` + `test_constraints_generated.py`）不属于终态，删除——该设计未归档、复杂度没有真实消费者。其中仍有效的资产迁移安置：

| 资产 | 去向 |
|---|---|
| AGENTS.md 的维护纪律（编号冻结、未验证不入库、写作纪律） | 浓缩进 ADAPTATION §5 |
| 三个未入驻域（app-lifecycle-config / run-modes / telemetry）的条目草稿与档案线索 | 留在 `test/story/` 评测域作候选材料（不进 `knowledge/`——未验证条目不入库） |
| `test_constraint_style.py` / `test_constraint_consumption.py` | 保留；扫描对象统一改指 `constraints/`（实施时核对现扫描面，凡指向 constraints-source 的判据一并改指真源） |

## 6. 处置清单（删除 / 迁移 / 改写 / 历史保留 四类收口）

实施以「rg 零活引用」验收：清单执行完后，全仓对被删标识（DELIVERY、export_delivery_patch、
constraints-source、generate.py）的检索仅允许命中历史设计记录（`test/story/plan/`）与
EVOLUTION（白名单），其余任何命中即未收口。已知活引用（探索时点）：`test/story/AGENTS.md`、
`TEST.md`、`test_product_reader_purity.py` 头注、knowledge 相关测试——全部按下表归类处置。

| 源 | 类别 | 处置 |
|---|---|---|
| `codebase-facts.md` 16–29「怎么维护」节 | 迁移 | 迁入 ADAPTATION §3.1/§6；facts 只留头注边界声明 + 六面事实 + `confirmed` 标记本身 |
| `component-profile.md` 头注 11 行维护句 | 迁移 | 迁入 ADAPTATION §3.1 |
| `constraints-source/` 整目录（含 AGENTS.md、generate.py） | 删除 | 有效资产按 §5 安置后整目录删除 |
| `story使用指南.md` §7 整章 | 改写 | 撤除；原位留一句「移植与适配见仓内 `doc/extensions/ADAPTATION.md`」 |
| `test/story/DELIVERY.md`、`test/story/scripts/export_delivery_patch.py`、`test/story/tests/test_export_delivery_patch.py` | 删除 | 交付即代码仓；其中仍有效的知识（画像重写要求）在 ADAPTATION §3 原生表达 |
| 各域文件 `## 档案` 节、「入驻时补进 README 的两行」 | 迁移 | 随 §5 安置：已入驻域的档案线索移评测域候选材料，域文件只留条目与判定/落法附注 |
| `test/story/AGENTS.md`、`TEST.md`、`test_product_reader_purity.py` 等对 DELIVERY/两层机制的引用 | 改写 | 按终态改写指向（ADAPTATION / constraints 单层） |
| `test/story/plan/`、`EVOLUTION.md` 中的历史记载 | 历史保留 | 不回改（过程文档纪律），列入 rg 白名单 |

## 7. 一致性裁决(历史矛盾就此收口)

1. **规约改哪份**:`constraints/` 唯一真源直接维护(§5);「生成物勿手改」的说法随两层机制一并退场。
2. **必须重写的画像清单**:唯一清单在 ADAPTATION(两份画像 + 设计模式样板),其余位置只指向不列举。
3. **适配清单**:唯一载体是 ADAPTATION §2,由「路径真实存在」断言看护;不再有第二份复制/排除清单。
4. **§1.0 红线表述**:交接与适配说明**集中且仅**出现在 `doc/extensions/ADAPTATION.md`;`skills/story/**`、`hooks/**` 与运行时 knowledge 中不得出现。红线语义不变,落点精确化。

## 8. 看护方案

- `test/story/AGENTS.md` §1.0 禁列第 4 条按 §7.4 表述修订。
- `test_product_reader_purity.py`:扫描面与 BANNED 不变(运行时产物照旧被看护)。
- 新增 `AdaptationGuideTest`:
  1. `doc/extensions/ADAPTATION.md` 存在,§2 清单中的路径真实存在(glob 断言,防清单腐烂);
  2. `codebase-facts.md` 不含维护语义节(负向断言,防维护语义回流);
  3. 运行时产物(`skills/story/**`、`hooks/**`)不含「换工程」「移植」「对端」语义(集中性看护);
  4. `constraints/` 目录形态断言随单层化更新(README + 域文件直接为真源)。
- 删除项的测试(`test_constraints_generated.py`、`test_export_delivery_patch.py`)随功能同步删除,不留空壳。

## 9. 验收

- 离线:`pytest test/story/tests -q` 全绿;新增断言逐条反向验证(撤 ADAPTATION、塞维护句回 facts、清单写假路径,断言应红)。
- 实跑:本特性零运行时注入,跑一轮 TEST.md 案例确认行为不变(门禁结论与上轮一致)。
- 终验:内网模型拉仓后按 ADAPTATION 对真实仓走一遍适配并回馈准确性(对应用户「可让内网模型确认」诉求)。
