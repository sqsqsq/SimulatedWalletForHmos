# A5 报错质量 / A6 推理链：语义分批结论

2026-09-29，A5/A6 语义分批（04-稳定性与性能分析 Phase 2 产物之一）。任务：评价执行模型犯错后的修复体验。只做现象与归因，不给优化方案。置信度标注：**高** = 直接读原文（runlog 节、gate log、DB part 原文、快照报告）；**中** = 抽样或推断。

- 分析对象：A5 取 `runs.json` 中 30 个失败 run 里的 10 个样本（覆盖 20260822–20260928、四种失败状态）；A6 深挖 AR90006 spec 返修战役的会话库。
- 证据路径约定：`RL` = `output/story/<suite>/cases/<case>/<run>/runlog.md`（后跟节号）；`GATE` = 同目录 `gate_*.log`；`SNAP` = `doc/features/archive/Story-Features-*`；`DB` = run 目录下 `opencode-xdg-data/opencode/opencode.db`。中间提取件在 `output/scratch/2026-09-29-stability-performance/`（不入库）。

---

## A5 报错质量（10 个失败样本）

### A5.0 样本与最终失败点

| # | suite / case / run | 状态 | 最终失败点 | 证据 |
|---|---|---|---|---|
| 1 | story-suite-20260822-225100-retry3 / pattern-image-review / 20260822-221148-16368-310f539b | cli_failed | 会话中段 API key 失效（401），非模型可修 | RL[396]；a5_scan.txt L1-49 |
| 2 | story-suite-20260823-172448 / split-interactive / 20260823-172508-35436-f5ad7915 | stop_failed | 宿主停工时 spec 未闭环（回执卡已知框架缺陷） | RL[506]-[550]；state.json closure |
| 3 | story-suite-20260828-191953 / pattern-image-review / 20260828-192045-33432-00356200 | cli_failed | review 阶段修路径中途 API key 失效 | RL[904]；GATE gate_harness_review.log |
| 4 | story-suite-20260831-165400 / car-key-sharing / 20260831-165508-24340-0ab524f1 | gate_failed | 终检 story-build：story-verdicts.md 缺失（218 条待裁） | GATE gate_story_build.log / gate_post_check.log |
| 5 | story-suite-20260907-004500 / auto-topup / 20260907-003502-29492-f0fb4d93 | stop_failed | 宿主停工时 spec 未闭环（卡工具内部矛盾 ⑫） | RL[262]-[499]；state.json closure |
| 6 | story-suite-20260908-step12 / auto-topup / 20260908-152025-31372-69b35fd7 | gate_failed | 终检 story_build_check 进程崩溃 rc=3221225794（0xC0000142），日志 0 字节 | gate_diagnostics.json |
| 7 | story-suite-20260914-143310 / car-key-sharing / 20260914-143556-2904-b9794c01 | gate_failed | 终检 story-build：AR/review-disposition.json 位置违规（run 结束后才发现） | GATE gate_story_build.log |
| 8 | story-suite-20260918-084325 / car-key-sharing / 20260918-084624-21600-39753863 | gate_failed | 同 #6，终检进程崩溃 | gate_diagnostics.json |
| 9 | story-suite-20260921-1239 / auto-topup / 20260921-124212-17556-f0cc7594 | gate_failed | 同 #6，终检进程崩溃（会话内 spec 已完整闭环） | gate_diagnostics.json；RL[744]-[773] |
| 10 | story-suite-20260928-091518 / auto-topup / 20260928-091916-8348-477b97a6 | stop_failed | 宿主停工时停在 story 范围关卡（doc-refresh 校验返修已完成） | RL[101]-[131] |

失败状态与修复体验的关系（**高**，样本内）：6 个 gate_failed 中 3 个是终检进程崩溃（#6/8/9，Windows 0xC0000142，模型从未见到任何报错），1 个是 run 结束后才发现的产物位置违规（#7），1 个是模型 34 分钟未能产出的裁决台账（#4），1 个后验（#9 会话内实际闭环成功）。3 个 stop_failed 是宿主主动停止、阶段未闭，报错体验要看会话内；2 个 cli_failed 是 API key 失效。即：**最终失败状态多数不反映模型修复失败**，修复体验要从会话内证据看。

### A5.1 逐样本判定

判定口径：三要素 = 「什么没满足 + 差在哪 + 如何回到正确路径」；对准 = 模型报错后的动作是否指向该报错的根因；重复 = 同一错误/同类错误在同一 run 内再次出现。

**#1 0822 pattern-image-review（cli_failed）**
- 会话内主要报错：`framework_integrity` BLOCKER（3 个 gitignored 发布文件缺失）。文案三要素齐：缺什么（逐文件列出）、差在哪（RELEASE-MANIFEST 声明但全 workspace 均无、非本次改动）、怎么回正路（真人具名 `integrity.drift_allowlist` 或源头还原；明说 agent 不得自改 framework 不得自签放行）。证据：RL[347]（`Fix: 上游修复请回 agent-maison 并重新发布；确需本地 fork：由**真人**…添加 {path, rationale, approved_by} 具名审批…或还原文件后重跑`）。
- 模型对准（**高**）：核对姊妹实例确认是环境预存缺口，按失败出口向人报两个选项；发现姊妹 workspace 已有真人签发的 allowlist 后照抄其配置（RL[392]-[395]）。对准中有一处边界疑问：把**另一次运行**里用户签发的 allowlist 当作对本工作区生效（当时用户确曾两次口头要求推进到闭环，模型也如实说明了来源与拟动作）。置信度：现象**高**，定性**中**。
- 重复轮次：该环境 BLOCKER 在第 2/3/4 轮重复出现（每次重跑 harness 必然复现，属环境项不是模型修错）。另有 check-receipt FATAL（回执不存在）报错给出「复制模板→真实填写→重跑」三步指引，模型照做一次通过（RL[361]-[363]）。
- 终态：写 allowlist 前一刻 API key 失效，run 死于环境。

**#2 0823 split-interactive（stop_failed）**
- 会话内报错主要是环境类：npx ts-node 全局安装损坏（`imaginaryUncacheableRequireResolveScript`），报错只有堆栈没有指引；模型自行定位并 `npm install` 修复（RL idx_0823 前段）。这类报错三要素缺「如何回正路」，靠模型自己探索，属报错质量短板（**高**：报错原文无指引；**中**：代价估计）。
- 语义链全部走通：spec harness PASS + verifier PASS 15/15；收口卡在 `capability_spec_requirement`（框架 fixed-track 缺陷投影 INCOMPLETE）——报错点名了具体 gate 与根因，模型正确归类为框架缺陷并按用户选择挂起，没有绕改（RL[526][534][538]）。对准（**高**）。
- 重复轮次：ts-node 环境报错在同一 run 内多次出现（每次 harness 调用），直到模型改用 `node -r ts-node/register` 等本地方式规避（idx_0823.txt 多处 `imaginaryUncacheableRequireResolveScript`）。

**#3 0828 pattern-image-review（cli_failed）**
- 本样本是「同一错误跨阶段重复 + 每次报错质量高」的代表。
- spec 阶段：post_check 报「verifier 报告有 12/12 个对象未裁：UX-01（引文在目标产物里检索不到——把清单里的字抄一遍不算裁决，那只是回声）…裁决表写进报告文件本身，固定表头…引文抄目标产物里的原话」（RL[343]）。三要素齐、措辞直指根因。模型读 verifier-report.mjs 确认口径后一轮修准（RL[347]：判定「证据列混入了『spec §10：』等非原文前后缀，归一化后不是 spec.md 的子串」）。
- plan 阶段同类错误再报（15/15 未裁，RL[536]），模型按已学口径修复（RL[537]-[541]）；verifier 语义判 RES-02/DLV-01「复述」→ 模型补 9 个资源键落点 → 复核改「设计」（RL[562]）。**这是报错→对准→修复闭环工作良好的直接证据**（**高**）。
- coding 阶段遇到 `upstream_verdict_gate`（上游证据链 stale，报错明说「回到对应上游阶段修复并重跑其 harness…不得手改上游 summary.json」，RL[605]），模型回 plan 重闭（RL[721]）。回 plan 时裁决表引文因 contracts.yaml 变更再次失效重报（RES-02/DLV-01 两处，RL[721]）——同类错误第 3 次出现，模型仍能按文案修准，但**每次产物变更都会重触发该类校验**，重复不是模型修错而是机制性重验（**高**：报错原文；**中**：重复定性）。
- review 阶段：`issue_to_file` 报「4/4 个引用文件不存在」，模型改为全路径；重跑仍报「2/5 个引用文件不存在」——剩余两条是**一个表格单元里用顿号连接的两个路径**，报错未提示这一形态，模型未及反应即遇 API key 失效（RL[891][893][903][904]）。该条是本次抽样中唯一「报错三要素缺『差在哪』的精确形态」的确定性脚本案例（**高**）。

**#4 0831 car-key-sharing（gate_failed）**
- 会话内 story-build check 报错从 64 处收敛到 15→4→1（RL[591][623][636]），报错文案质量高：`lostHint` 按 token 类别指路（「阈值『72小时』要随它所属的那句叙述或验收行一起讲——单独摆着的数字，读者不知道它约束的是哪一步」），并给出 covered_by/改 at 两条合法路径。模型两轮修完全部结构问题（RL[593][624]）。
- 最后一条「221 个单元的落点机器定不了，需要裁决者逐条裁，但 story-verdicts.md 不存在」（GATE gate_story_build.log 同文，RL[636]）三要素齐，但**任务本体超出模型单轮承载力**：218 条逐单元语义引文（≥12 字、非素材回声、句边界、引文复用上限）。模型在 18:39–19:09（30 分钟）内尝试：子 agent 两次空返回（RL[643][647]）→ 自动匹配只命中 64/218（RL[696]）→ 手写映射（RL[703][704]）→ 试图用 covered_by/语义簇复用绕行（RL[676]-[684]）→ 发现格式类单元（`---` 分隔线、图注）被枚举成待裁单元且无任何合法出口（RL[682]：「这是 check 对『无事实单元』的死角」）。宿主以「退回自主裁决又绕回 audit 分配纠结 34 分钟」裁定停止（RL[741]）。
- 归因：报错本身不糊涂，糊涂的是**任务规模**——报错说「需要裁决者逐条裁」，但单轮上下文装不下 218 条高质量语义判断，机制没有提供分批/减载路径；加上枚举器噪音单元无出口。重复轮次：同一报错在 18:38–19:09 间出现 3+ 次未解（**高**）。

**#5 0907 auto-topup（stop_failed）**
- check-receipt BLOCKER（slim_summary_missing / verifier_request_absent）报错自带处置（「请先自跑 harness-runner 生成本次 base summary，再校验回执」），模型照做通过（RL[108][113]）。对准（**高**）。
- 核心事件：story-build ⑫ 报「附录·改动边界 表后还有一段正文」——该段正文（`**Scope 的说明原文**`）恰是生成器自己按 manifest 1.7.0「Scope 的说明原文引在表下」写进去的。**同一文件里的生成器与检查器互相矛盾**。模型从 00:57 到 01:44（约 47 分钟）做了逐层实验（定位 `proseBlocks` 的 afterRows 判定、写临时脚本验证、核对 zone 标记），最终确认「快照内生成器与检查器的真实冲突」，按失败出口停等宿主（RL[262]-[499]，索引 idx_0907.txt [461]-[499]）。
- 归因：模型判断过程本身高质量（没有瞎改产物凑通过），但**报错完全没有提示矛盾来自工具侧**，模型只能靠自我实验排除自身嫌疑，耗掉整段尾部时间。重复轮次：⑫ 项连续 10+ 次重跑均复现（**高**）。

**#6/#8/#9 0908 / 0918 / 0921（gate_failed，终检崩溃）**
- 三例同型：会话内 spec 均正常闭环（#9 在会话内完成 check-receipt PASS、交付门通过、update 收口，RL[759]-[771]），run 结束后 runner 终检 `story_build_check` 进程以 rc=3221225794（0xC0000142，Windows DLL 初始化失败）崩溃，日志 0 字节。gate_diagnostics.json 完整记录。
- 结论：这 3 个 gate_failed 与修复体验无关，是终检基础设施崩溃；模型无任何可对准的报错（**高**）。
- #9 会话内另有一次小型返修：`AC-21 的 knowledge_rule: ""` 空串不被接受——报错精确到字段与原因，模型删字段一次过（RL[744]-[746]）。三要素齐、对准（**高**）。

**#7 0914 car-key-sharing（gate_failed）**
- 会话内修复链是 10 个样本中最好的：story_flow 6 处红线（含「搬图到哪一章、围栏第一行写 `%% 图源`」的搬法指引）一轮修准（RL[294]-[309]）；spec harness 10 个 BLOCKER 一轮分类修准（RL[314]-[346]，模型自行读 check-spec 源码确认 AC 粗体格式、facts frontmatter schema、criteria 桥接三种判据）；plan harness 6 个 BLOCKER 一轮修准，期间通过读源码发现 resource_keys 的 map/数组形态差异（RL[499][504]）。对准率：三次门禁失败全部一次修准（**高**）。
- 最终失败：run 结束后 runner 终检 story-build 报「AR/review-disposition.json 不该在这一层——根下只放交付文档与单据身份…把它挪进 AR/story-src/；目录不受这条限制」（GATE gate_story_build.log）。报错三要素齐全且给了精确去处，但**送达时机在 run 终止后**，模型无返修机会。诱因：规则页让模型「写处置台账」却未规定落点，模型选了 `AR/` 根（RL[383][385]）。归因：信息先于决策缺口（位置约束未在动笔前送达）+ 终检时机无修复回路（**高**）。

**#10 0928 auto-topup（stop_failed）**
- doc-refresh.md 校验失败：模型初版用 `##` 标题与 markdown 链接引用，校验报「缺标题与引用无效」但问题清单未写期望形态；期望形态写在 `status` 的 action 文本里（`### <版本>/<话题 id> <标题>`、`<版本目录>/raw.md:L起-L止`）。模型读校验脚本 meetings.py 后按「`###` + 纯文本引用」重写一次通过（RL[104]-[116]）。
- 判定：报错要素分裂在两处（问题清单 + action 提示），模型花 2 轮对准；属轻度「三要素分散」而非缺失（**高**）。run 停在 story 范围关卡等宿主回话，与修复体验无关。

### A5.2 汇总发现

1. **门禁/回执报错文案的三要素齐备率在样本内很高**。确定性脚本报错（story-build check、post_check、check-receipt、harness FAIL）普遍同时给出未满足条件、差距形态与修复路径，且多处给「一次列全，不必逐轮试」的批量修指引；模型对准率也高——10 个样本中所有会话内出现过的结构性报错均在 1–2 轮内修准（#3、#4 前半、#7、#9、#10）。置信度：**高**（逐条读原文）。
2. **报错质量问题集中在三类**（**高**，各 1–2 例）：a) 环境类报错无指引（#2 的 ts-node 损坏只有堆栈）；b) 形态细节不报（#3 的顿号合并路径被当单个路径判缺失）；c) 要素分裂在多处输出（#10 的期望格式在 action 文本而非问题清单）。
3. **「送达时机」与「任务规模」是比文案更大的失败源**：#7 报错完美但 run 已结束、模型永远看不到；#4 报错正确但隐含工作量超出单轮模型能力且无减载路径。3 个终检崩溃（#6/8/9）则让 gate_failed 完全脱离修复体验语义。置信度：**高**。
4. **「只修局部再报错」的重复主要不是模型修错**：#3 的裁决表引文回声跨 spec/plan/upstream 三次出现，是「产物每次变更即重验」的机制性重触发；#1 的 framework_integrity 是环境项复现；真正可归为模型重复犯错的样本内未见明确一例。置信度：现象**高**，定性**中**（抽样 10/30）。
5. **工具自身矛盾类报错（#5 的 ⑫）没有转译提示**，模型需要用数分钟到数十分钟的自我实验才能把嫌疑从自身产物移到工具，这段成本在 stop_failed run 的尾部占比显著（#5 约 47 分钟、#4 约 34 分钟）。置信度：**高**（时间戳与节序可复算）。

---

## A6 推理链（AR90006 spec 返修战役）

### A6.0 现场还原与数据偏差说明

- 任务指定的 DB（story-suite-20260927-004309/cases/auto-topup/20260927-004648-29900-3f22aae1）**只覆盖战役尾部**：主会话 400 条消息（00:46–01:57），3 次 verifier 派审（01:24 / 01:44 / 01:51），负责 update 收口与 BD-10 残留修复。
- 17 轮返修的主体现场在**前一晚的 run**：story-suite-20260926-190654/cases/auto-topup/20260926-191041-29640-9e66a060 的 DB（65MB，主会话 655 条消息，19:10–22:16，**20 次 verifier 派审**，最后一次被宿主停止时仍在跑）。本次分析两个 DB 都解析了，下文以 26 号 DB 为主。快照 `SNAP Story-Features-20260927-004631/AR90006-update/spec/reports/` 留存 18 份 verifier.report.\*.md，与任务描述「18 份报告」吻合。
- 提取件：a6_main26_parts.jsonl、a6_round_01–21.txt（逐派审轮切片）、a6_stats26.json。

### A6.1 战役弧线（**高**，逐轮读 part 序列）

| 段落 | 时间 | 派审 | 内容 |
|---|---|---|---|
| 首轮真缺陷 | 19:40–19:46 | 1 | verifier 判 1 BLOCKER：AC-G3 在 spec §8 与 acceptance.yaml 语义不一致。模型一轮修准（统一口径 + 网络异常另编 AC-G5），并顺手处理 2 个 WARN |
| subject 漂移循环 Ⅰ | 19:46–20:18 | 2–8 | 每次「写报告→跑 full harness→交付门」都产生新审查对象；模型边审边根因定位，最终用「不跑 full harness、走 sync-closure/交付门」收敛，spec 闭环并归档 |
| update 开轮 + 状态陷阱 | 20:45–21:01 | — | 导入 v1.1 PRD 与评审回稿；模型为渲染评审记录误用 `reopen`，撤销成文登记后 `complete` 被归档态挡死，手改 story-flow.json 恢复 |
| 业务返修 + 循环 Ⅱ | 21:02–22:17 | 9–20 | spec/acceptance 业务同步后每轮 verifier PASS 但报告持续指出残留（WARN/advisory），每修一处材料即变、新对象再派审；宿主 22:17 停止时循环未收敛 |
| 尾段收口（27 号 DB） | 09-27 01:24–01:57 | 3 | 三处落实（AC-R10、story/SR 一致性、材料清单）+ BD-10 滚替残留修复，update 收口 |

### A6.2 循环机制还原（**高**，模型推理原文 + 框架行为互证）

循环链条（模型在多轮推理中逐级确认，最终读到框架源码定案）：

1. verifier 报告落盘后，框架把报告登记进 `verifier.conclusions.json` 台账；
2. pre_verifier 的 hook fragment 引用「上一份审查报告」路径（a6_round_07.txt [20:14:23]：「Hook fragment 1 包含『上一份审查报告』的引用…每次写一个新报告、再跑 harness，这个引用就换成一个新文件名，于是 lifecycle fragment 变化 → 新 subject」）；
3. full harness 重跑时按材料重新寻址 subject（a6_round_20.txt [22:16:43]：「subject 按材料寻址（material_sha256），相同材料复用同一 subject，材料变化必换 subject」；[22:17:05]：「循环根因已完全明确…这是 framework 固有行为」）；
4. 于是「写报告 → 台账/引用变 → 材料变 → 新 subject → 交付门/update close 要求当前对象独立审查 → 再派审」自激，**写报告这个必需动作本身就是材料变化源**。
5. 收敛出口存在且模型找到了两次：报告落盘后**不跑 full harness**，走 `--sync-closure`（不重算 subject）让交付门放行（a6_round_08 [20:14:30][20:18:40]、round_20 [22:13:12]）。

量化：26 号 DB 主会话 full harness 运行 28 次、sync-closure 仅 4 次、update close 调用 8 次、模型文本中「循环/死循环/自激」出现 43 次、「收敛」24 次（a6_stats26.json，**高**）。20 次派审中，**只有 2 次发现实质缺陷**（首轮 AC-G3 BLOCKER；第 9 轮后陆续的 WARN 残留项），其余轮次的产物文件哈希与已审对象逐字节一致、仅 lifecycle 片段不同——模型在多轮中用产物哈希对照主动证明了这一点（如 a6_round_06 [20:08:04]、round_09 [21:09:16]、round_13 [21:31:44]）。

### A6.3 典型返修段落（原文引用 + 归因）

**段 1｜首轮真缺陷：一次修准（19:45）**
> 「verifier 报告有 1 个 BLOCKER：AC-G3 在 spec §8 与 acceptance.yaml 中含义不一致。- spec §8 AC-G3: 网络异常有明确提示…- acceptance.yaml AC-G3: 创建签约接口失败/超时展示失败并允许重试…修复：统一两者。」（a6_round_01.txt）

模型 11 秒内给出修法并执行，同时把两个 WARN（模拟数据标注、200 元来源标注）一并处理。归因：审查结论清晰、落点明确，模型理解与执行无偏差。**这段代表报错质量好时的修复体验**（**高**）。

**段 2｜发现循环并自证（19:56–20:08）**
> 「又出现新对象 c682308a，因为每次 harness 跑都重投附录机器区…产生新的 fingerprint。我现在每次…跑 harness 又生成新 subject。**需要停止这种反馈循环**。」（round_03 [19:56:44]）
> 「关键结论：a28caeb 与 1a2fd8 的产物文件（acceptance.yaml、spec.md）哈希完全一致，仅 lifecycle_sha256 不同。」（round_06 [20:08:04]）

模型没有盲目服从「为每个新对象派审」，而是先做哈希对照把「材料真变」与「仅片段变」区分开，再读框架源码定位 fragment 来源。归因：卡点不在理解报错，在**机制没有给「产物未变则不重审」的判定出口**，模型只能靠自助取证（**高**）。

**段 3｜update 状态机陷阱与危险恢复（20:56–21:01）**
> 「update 流程并未在 update.py 内处理 story 重新登记…我的问题：reopen 已撤销 story_written，但 update 进行中 complete 报『已收口』。」
> 「症结找到：我在 update 中误执行了 `reopen`，它撤销了成文登记…恢复：把 status 改回 `complete`，再重跑 `story` 重新登记成文。」（round_08 段内 [20:57:13]–[21:01:15]）
> 契约弹出「手改警告——这是必要的恢复操作」（[21:01:28]）

诱因链：update.md 的「story 侧改动走 reopen → complete 收口 → chapter → 重新登记」指引与归档单（archived=True）现实组合成一个 `reopen` 进得去、`complete` 出不来的状态；模型两次落入（21:41–21:42 第二次误 reopen 后再次手改恢复，round_15）。归因：**规则理解偏差的责任不在模型侧**——方法页给的路径在该状态下不可走通，模型最终选择了手改状态文件这种规则外恢复（契约自己警告了手改），这是全场唯一一次越过「不得手改状态」边界的动作，且模型留了痕。该段在 26/27 两天共发生 2 次（**高**）。

**段 4｜verifier 连续指出残留：循环中的真实收益（21:17–21:26，27 号 DB 01:49）**
> 「d0cf828 verdict=PASS，但增加了 reference_crosscheck WARN（spec 附录 B 与 AR/design.md §1.3 标 v0.4，应 v0.5）」（round_11）
> 「4c57966 verdict=PASS，3 WARN。需修复的 WARN：AR/design.md 提取稿仍写 200 元（应 300）、spec §9.1.3 历史版本默认方向不一致…统一为『按关闭处理』」（round_12 [21:24:39][21:25:06]）
> 「verifier PASS，但指出三处需落实：①spec §8 缺 AC-R10（update-notes 声称补了却没补）；②story §6.1/§9.2『支付部件不可用时给提示』与 SR §5『隐藏新签约入口』不一致——**这是我上轮误改**；③story 材料清单缺 review-feedback.md。」（27 号 DB timeline [01:49:33]）

每轮 PASS 报告带出的 WARN/advisory 都是真实残留（版本标注漏改、数值漏改、口径矛盾、模型自己上轮改错的方向），模型逐条对准修复，无一条误判或拒绝。归因：verifier 的语义审查在持续产出价值；但每修一条 → 材料变 → 新对象 → 再派审，**修复行为本身拉长了循环**（**高**）。

**段 5｜「不再改文件」的自我约束反复失守（21:57–22:16）**
> 「notes.md 更新会再次改变 material——但我已在上一条消息里把…报告写好了。问题在于：我每次改文件（notes/spec）都会触发材料变化 → 新 subject → 又要派审，形成死循环。」（round_17 [21:58:12]）
> 「18…之后不再改任何文件，直接 harness + close 收敛」→ 3 分钟后「我误跑了 full harness 重置了 subject。正确路径：写报告后**不用 full harness**，用 `--sync-closure` 采纳」（round_18 [22:02:46][22:03:18]）
> 「这个循环已消耗过多轮次。我需要停止盲目派审，读 harness 生成 verifier request 的决定逻辑」（round_20 [22:15:48]）

模型在 round_16–20 反复宣布「不再改任何文件/不再跑 full harness」，随后因 notes.md 处置记录、WARN 修复、知识词修正等**被报错或报告要求**的修改再次破戒。归因：卡点不是模型忘了，而是「每条报错都要求修改、每次修改都重置审查对象」的结构约束下，**没有一条两全的执行顺序**；「先修完所有残留→再统一派审→不再动文件」的正确顺序是模型到 22:13 才试出来的（round_20 [22:13:12] sync-closure 收敛成功），而宿主在 22:17 停止（**高**）。

### A6.4 卡点归纳（按任务给的四类，另加一类）

1. **报错难懂**：不是主要卡点。A6 战役中所有审查结论、报错文案模型全部正确理解，无一误读（**高**，21 轮逐轮核对）。
2. **找不到依据来源**：中度卡点。「交付门为何拒绝」「close 为何 stuck」「subject 为何漂移」的判据分散在框架层（verifier-report.mjs、check-receipt.ts、verifier-material.ts、verifier-plan.ts），模型共发起 8 次框架源码检索才拼出完整机制图景；规则页（spec.md 闭环表、update.md）与框架实际行为存在表述缝隙（completed_with_prior_review 在闭环表里是合法收口、在 update close 的 unadopted 判定里被卡）。证据：a6_round_06/07/16/20 的源码检索序列（**高**：检索行为可数；**中**：缝隙定性）。
3. **规则理解偏差**：一处——update 期间 reopen 的适用条件（段 3）。方法页指引与状态机现实冲突，模型按指引走即入坑；属规则侧缺陷而非模型误读（**高**：两次落入走的是同一条按文档的路径）。
4. **范围不清**：一处——「verifier WARN/UNKNOWN 本轮不修，记入 notes」与「报告 advisory 建议落实」之间的边界由模型自行裁量；模型选择了修（多数正确），但每次修复都推动材料变化。这是范围裁量权与材料寻址机制耦合出的次生成本（**中**：裁量行为可数，反事实无法验证）。
5. **结构性自激循环（补充类，本场主导卡点）**：写报告→材料变→新对象→再派审的闭环使 20 次派审中约 9 成轮次的产物与已审对象逐字节一致；模型消耗大量推理在哈希对照、路径试探与自我约束上，真正语义修复只占少数轮次。出口（sync-closure）存在但未被任何规则页写明，模型两次靠自救找到、一次丢失后重找（**高**）。

---

## 样本量与未覆盖范围（如实登记）

- A5 样本 10/30 个失败 run；未覆盖：timeout（2）、worker_lost（2）、harness_incomplete（2）三类失败，以及 47 个 finished run 中不可见的会话内返修。A6 只深挖 AR90006 一条链；ISSUE-206（car-key-sharing）未做 DB 级推理链分析，其结论仅来自 A5 的 runlog 抽样。样本只覆盖 auto-topup / car-key-sharing 与早期 Case 的业务域，外推需谨慎。
- A6 的 reasoning 字段仅采样到轮次切片粒度（每节前 220–260 字）；逐 token 的思考流未完整回放。26 号 DB 末轮派审（round 21）被宿主停止打断，其报告未入快照。
- 「模型对准」判定基于 runlog/DB 中的显式动作与自述；模型内部未表达的对准偏差不可见（工具盲区，未验证）。
- A5.2-4 的「无模型重复犯错」结论受抽样规模限制，样本外不能保证。
