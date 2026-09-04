# 步骤 12 · 验收前正向重设计 · 独立评审（Claude，2026-09-05）

对象：`ebd48e04`（作者链）、`0615dd95`（图片）、`08784d77`（审查）、`a1bd79e0`（装置）。
复审者复跑：story 600 全绿（串行 86 s；`pytest -n 4` 并行 32 s 全过，说明测试彼此隔离）；73 条 = 活跃 70（FAIL 0、委派 15）+ retired 3；
语义代理 0；改动的 7 个 `.mjs` 语法通过；无无调用函数；`framework/` 与 `.opencode/` 零差异。

## 1. 结论

- **机制面通过**：13 号十二项全部落地，退场核对——合同 `UX` 来源与 `warn_if_siblings`、脚本内词表、markdown 块要求、`pre_verifier` 前缀过滤、门读任意文件名、工作区白名单，全部 grep 为零。
  新判据「材料图片集合一致」在二跑真产物上逐张报出用户找到的三张图，是本批第一条在真实产物上抓到已知缺陷的新判据。
- **返修一个提交**（§3），不重做；通过后进 CLI 三跑。

## 2. 用户三条提醒的核对

**① 图片有没有被强制塞进 story。** 没有。`check ④` 判的是「去处」：清单里的图要么被引用，要么正文里提到它的文件名（附录材料清单那一行写不引用的理由即可）——两条出路成本相当，报错文案两条并列。
读者审查问的是「用了没有；没用，理由成不成立」，理由归它判，脚本只报差集。**但有一处旧措辞要改**：`story-build.mjs` 附录不放图那条的注释仍写「与『每张登记的图都必须被引用』是合围」，那句话描述的是已经不存在的义务，会误导下一个维护者。

**② 提示词与脚本有没有膨胀、有没有补丁。** 有膨胀，两个来源，都不是补丁而是**放错了地方**：

- 总量 8115 → 8591（+476，13 号估 +250）。多出的一半是**散文进了脚本**：`author.mjs` 47 行、`reader-review-task.mjs` 42 行字符串字面量是纯文字（决策登记怎么写、数值来源三选一、验收桥、门禁清单、审查者「还要看两件」「不要做的事」）——
  它们既不是数据派生，也不在可读的 `.md` 里，违反 AGENTS §4.3「语义指引保持人可读，不强塞进机器 schema」，还把 `hooks_mjs` 顶到 2715（target 2450）。
- **读者审查的判据现在有两份散文**：overlay 的 `story_reader_review` 描述 41 行 + 任务书里的输入清单/两问/不要做的事。同一件事两处写，是 §5.2 单一真源的反面。
- `sidecar_shape` 的字段是手写的第二份 schema，与读取函数并列；13 号写的是「从读取函数派生」。有测试守着，先记 advisory。
- 未按 13 号退场的两处：`story-write.md` 的「动笔前你手上要有什么」输入表、`rules.md` story 段的数据性条款——任务包已覆盖，它们成了第二份。

更要紧的一条：**交付面又写进了实跑故事**，而且这次写进了**提示词**——作者任务包里「两轮实跑各丢过一次：一次主流程没画图，一次三张图一张没进正文」（`author.mjs` L121），verifier 任务书里「两轮实跑各丢过一次图，第二次三张全丢，而上一轮的审查判了『零阻断』」（`reader-review-task.mjs` L93），
`phases/spec.md` 的「一次真实实跑为此重复审了 11 分钟」，`inbox_import.md` 与 `import_sources.py` 报错里的「两轮实跑丢图都是从这里开始的」，加上 `author.mjs` 头注释的「34 次、17 次、9 次」等十余处。
这正是用户 09-04 定的规则（§5.3）禁止的东西，且这次进的是被测模型会直接读到的文本。M02 兜底没拦住，因为它的词表是「实测/首跑/上一版/曾经/改动前」，而这批用的是「实跑/两跑/二跑/两轮」。

**③ 测试慢不慢、并不并行。** 离线全量 600 条串行 86 s，`pytest -n 4` 并行 32 s 全过——测试本身已隔离，只是默认命令是串行的 `unittest`。86 s 里 19 s 是两条新测试各复制一次带 `node_modules` 的工作区模板（154 MB）；`ts-node` 起动的三条各 1–7 s。
CLI 用例层面本来就并行（`jobs ≥ Case 数`）。规约缺的是：离线全量的默认跑法、并行安全的要求、重夹具只建一次、慢测试要报出来。

## 3. 返修（一个提交）

- **B1 清交付面的实跑故事**，包括提示词与报错文案：`author.mjs` L4–6、L121；`reader-review-task.mjs` L4、L93；`pre_verifier.mjs` L66、L93；`verifier-report.mjs` L28；`spec.md` L88；`inbox_import.md` L81；`import_sources.py` L418；`headings.mjs` L31；`lint-rules.mjs` L9；`story-build.mjs` L176、L1425、L1449；`story_flow.py` L729、L757；`obligations.mjs` L6。
  用现在时讲道理，不讲哪一跑。M02 的运行计数词表加「实跑|两跑|二跑|三跑|两轮」（`上一轮` 是流程概念，不加）；AGENTS §8 自检同步。
- **B2 散文回到可读的地方，脚本只出数据**：`author.mjs` 只渲染位置与侧车、激活条目数与骨架指引、图片逐张、十章问题、词表、登记那一行；决策六键从 `story-build` 校验决策时用的那份字段表派生，三段式与「怎么写 requirement」这类说明回 `author.md` / `story-write.md`（`author.md` 上限 60 行，放不下的归 `story-write.md` 决策登记节）；门禁清单整段删——报错负责指路，提示词不复述门禁。
  `reader-review-task.mjs` 只出输入路径、十章问题、图片逐张、输出形态；判据定义只留 overlay 一份。目标：`hooks_mjs` 回到 2600 以下。
- **B3** `story-build.mjs` L1116 那句「合围」改成现在的判据：图不进附录，且每张登记的图在正文有去处（引用或点名）。
- **B4 测试**：两条模板测试改为一个类里建一次模板（`setUpClass`）；`TEST.md` 加离线回归规约——默认 `pytest -n auto`，串行只作排障；每条测试只写临时目录；重夹具一模块建一次；`--durations 10` 报最慢十条，单条 >5 s 要写明原因。
- **顺手**：`story-write.md` 输入表与 `rules.md` 数据性条款按 13 号退场。

## 4. 用户要拍板的两处（执行会话已列）

- `hooks_mjs` 收口 target：B2 之后再看差额，回不到 2450 的部分按类别列出交裁定，不砍判据。
- verifier 证据只认发布器 JSON，无发布器宿主（`codex-luna`）该项记 `NOT_APPLICABLE`：评审同意——主模型能写出来的东西不能作它被审过的证据。

## 5. advisory

- `sidecar_shape` 手写字段：让 `read_positioning / read_scope_options / read_gate_options` 与它共用一份字段常量。
- `story_flow.py` 的 `order` 长串在四个分支各拼一次，抽成一处。

## 6. 用户裁定（2026-09-05）与返修口径

用户：**允许正确、必要的额度增长，不影响正常功能实现；不合理的要优化。测试串行须修正。**

据此返修口径改成三档，执行会话自己判每一行属于哪档，自述里按档列：

| 档 | 判据 | 处置 |
|---|---|---|
| 必要增长 | 从真源派生的数据渲染、新的确定性判据、新的登记动作——没有它功能不成立 | 保留；预算按实际抬，reason 写清它替代了什么、为什么不能更少，用户签字 |
| 放错地方 | 散文写在脚本字符串里；同一判据在两处各写一份；门禁清单在提示词里复述 | 搬回可读的 md 或合并成一份，不是删功能 |
| 维护痕迹 | 实跑故事、次数、轮次编号进了交付面（含提示词与报错文案） | 清零，M02 与 §8 词表补「实跑/两跑/二跑/三跑/两轮」 |

具体到本步：`author.mjs` 与 `reader-review-task.mjs` 里数据派生的段落属第一档，保留；纯文字段落属第二档，回 `author.md` / `story-write.md` / overlay；
`knowledge-use init`、`register-ux`、`check ④` 集合一致、`spec_stage_step`、`stripOwnHeading` 全属第一档。收口时 `hooks_mjs` 回不到 2450 的部分，按第一档写明理由交用户签字，不砍。

**测试**：默认命令改为 `python -m pytest test/story/tests -n auto`（`TEST.md` 与 `AGENTS.md` 同改），串行 `unittest` 只作排障；两条模板测试一个类内建一次；
新增规约三条——每条测试只写临时目录、重夹具一模块建一次、`--durations 10` 报最慢十条且单条 >5 s 要写明原因。

## 7. 复审者亲自复现（2026-09-05 补）

用当前脚本对二跑工作区与临时副本各跑一遍，不靠自述：

| 项 | 复现 | 结果 |
|---|---|---|
| D1 任务包 | 直接调 `author.mjs` 钩子渲染 AR90006 | 7332 字节、七段；位置、条目数、候选、图片清单、十章问题、词表全是数据派生；散文段与实跑故事见 §3 |
| D2 骨架 | `knowledge-use.mjs init` 到临时副本 | 15 条约束 + 2 份事实一条不落，`applicable` 留空，「无候选」字面在注释里 |
| D3 登记 | `--register-ux` 登记 image1 并写说明 | 复制到 `ux-reference/signup-page.png`，`.captions.json` 按 sha 落盘，`materials.json` 该图 `caption` 带上，未登记的两张 caption 为空但仍在清单 |
| ④ 集合一致 | 对二跑真产物跑 `check` | 逐张报出三张未引用未提及的图，与用户发现的一致 |
| D5 状态 | `status` 在 story_written 态 | 打印 build → harness → verifier 一次 → 归档，并写明 verifier 之后不改产物 |
| D7 装置 | 黑名单常量与 `measure_run` 复算二跑 | `node_modules` 不在排除表；读 checker 源码 68、规则文本 113、起跑空档 270 s，与人工统计一致 |

**多出一条要返修的（B5）**：说明只能经 `--register-ux` 写，而它会把图复制进 `ux-reference/`。材料里不是界面的图——二跑的 `image3`（服务端触发与扣款流程图）——没有登记路径：
任务包对它写着「没有说明，登记时补一句」，作者要么把流程图误登成界面参考（framework 的 `ux_reference_mapping` 随即 WARN 它未映射到屏），要么让它一直没有说明。
改法：给任何材料图片写说明的动作与「复制为界面参考」分开（例如 `--caption-image <路径> --caption "…"`，不复制）；`inbox_import.md` 在判图那一步要求**每张抽出的图**都给一句说明，界面图另加 `--register-ux`。

## 8. 返修（`44ddf5da`）· 独立评审（Claude，2026-09-05）

- 状态：**通过，步骤 12 收口。** 复跑：`pytest -n auto` 600 全过 32 s（本机）；73 条 FAIL 0、委派 15；语义代理 0；9 个 `.mjs` 语法通过；无无调用函数；`framework/` 与 `.opencode/` 零差异。
- B1：交付面轮次叙述与实跑计数归零（剩两处「上一版」是 `/story restore` 的产品概念）；M02 加「轮次叙述」一档，不带数字也算；AGENTS §5.3/§8 同步。
- B2：`author.mjs` 只剩数据渲染（151 行，纯文字段从 47 降到 23 且都是字段标签），门禁清单删；`reader-review-task.mjs` 93 行，判据定义只留 overlay；决策六键从 `DECISION_FIELDS` 派生；散文回 `author.md`（59 行，≤60）与 `story-write.md`；
  任务包 7332 → 4813 字节、六段，复审者重新渲染核过。`story-write.md` 输入表与 `rules.md` 登记字段 JSON 已退。
- B3：「合围」旧注释已改。
- B4：`TEST.md §7.9` 离线回归规约（默认并行、只写自己的临时目录、重夹具一类一次、最慢十条且 >5 s 说明）；`AGENTS §8` 同步；模板测试 `setUpClass` 一次；并行还暴露并修了两处固定 `%TEMP%` 路径撞车。
- B5：`--caption-image` 只写说明不动文件，`--register-ux` 是复制为界面参考外加说明；`inbox_import.md` 要求每张抽出的图都有一句说明；顺带把重复的哈希计算收回 `materials.file_digest`。
- advisory：`POSITIONING_FIELDS` 与 `SPEC_STAGE_ORDER` 已抽成一处。
- 预算：scripts_mjs 1907、scripts_py 1342、hooks_mjs 2657、prompts_md 1995、data 683，总 8584（峰值 8700 内）。`hooks_mjs` 高于 target 2450 的 207 行属第一档（任务包、审查任务书、骨架三段数据渲染），收口时按用户 09-05 裁定签字。
- 小观察（不阻塞）：xdist 下 `setUpClass` 建的 150 MB 模板在拿到该类用例的每个 worker 上各建一次；用 `--dist loadscope` 可让同类用例落同一 worker。

### 进入 CLI 三跑的条件（已满足）

步骤 9、10、11（首二跑）、12 全部通过；全量离线、金样、73 条、静态测试全绿；硬条件不变：verifier 证据由插件发布、`agent_id` 非 stub、插件不触发当场停。
三跑观察项：任务包是否被读（`key_inputs_read` 含 `author.md`）、读脚本 0、图片逐张有去处且审查逐张答复、上下文 ≤150K、verifier 只跑一次、framework 前置单列。
