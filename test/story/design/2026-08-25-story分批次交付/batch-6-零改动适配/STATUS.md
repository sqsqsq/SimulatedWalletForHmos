# 批次 6 · 零改动适配 · 进展跟踪

| 项 | 值 |
|---|---|
| 状态 | **六跑已跑、已评审（`reviews/03-六跑.md`）：闭环成立、机制判据基本通过；S7 未执行、作者翻源码 59 次；三轴建议 82 / 90 / 55 待用户定；建议开 steps/03（R45–R48）** |
| 起点 | 上游 `0143e21`（`origin/main` `ea2365d1`）；本仓 story 分支 `framework/` = `85e266f` + 18 处 |
| 用户裁定 | framework 不改逻辑、只允许 opencode 登记两处且不交上游；`.opencode/` 只是本仓测试装置，内网用 codex；extension 支持批次 5 全部功能 |
| 方案文件 | [00-总览.md](00-总览.md)；`steps/01`、`steps/02` |

## 步骤状态

| 步骤 | 状态 | 评审报告 |
|---|---|---|
| 1 对齐上游与能力落回 | **通过收口**（`reviews/01` §7.8 R39b 返修 `d8e92cb7` 复核：三个反例全 FAIL、三种正常形态 PASS）。此前：四提交 55b24abb / 9c0a6148 / 18581b0a / 5e0230a1 + 返修 4fd1b42a（R36 交付门改用 node 直起 harness 的 ts-node，Windows 实测回执跑通；R37 归档 ① 接 `--deliver`；m1/m2）。635 绿、形态 70 条 FAIL 0、drift 恰好登记两文件、预算 8932/8940；hooks_mjs 用户 2026-09-06 签 2800 | [reviews/01-对齐上游与能力落回.md](reviews/01-对齐上游与能力落回.md) |
| 六跑 | 已评审：通过 11 项判据（verifier 启用一次、交付门拦真问题并走通 reopen、图标记含双标记、标签、§9/§10、知识链、矛盾口径、停等 2）；未过 S7（5 张陪衬进正文，E 不种图行 + 规则二选一）与效率（读源码 59、上下文 462K）；scorecard「读源码 0 次」不实 | [reviews/03-六跑.md](reviews/03-六跑.md) |
| 2 步骤 16 返修与追加（原批次 5 步骤 17） | **通过收口**（`reviews/02` §11；C5 用户纠正改向 + C6 一围栏多标记复核一致；此前 §9：返修 `df6b194e` R41/R42/R43 + F1/F2 复核一致：失效形态 FAIL 0、author.md 60 行、660 绿、预算 9123/9200）。此前不通过项：机制与装置全部按方案落地并亲核（R33/R34/M02、S5/S6/S7）；返修 R41（spec 作者侧缺「SR 图搬进 spec」规则，只在报错里）、R42（七个机制文件改了 272 行而版本仍 1.6.0，adapt 判 package_not_bumped）、R43（5.x 标签 ⑪ 核，用户裁定）；预算已签 | [reviews/02-步骤16返修与追加.md](reviews/02-步骤16返修与追加.md) |

## 事件日志

- 2026-09-05 上游发布 `0143e21`：verifier 报告真源改回调用方写出的 MD，`verifier_capability` 矩阵换布尔 `verifier_subagent`（claude / codex / codeagent 登记，opencode 未登记），`on_context_load` 明确只进 verifier 上下文，行为规约加第 8 条。用户裁定 framework 0 改动、能力落回 extension。执行会话写 `steps/01`。
- 2026-09-05 评审 `steps/01`（reviews/01）：事实全部核对成立；设计三处必修——读者审查要一条路（推荐：扩展在 ⑤b 承载、`story_reader_review` 搬出 overlay、`pre_verifier` 不再注入、`verifier-report.mjs` 单来源）、任务书自足并沿用 framework 终态块、指纹定义为 story 正文 sha256；同步范围补物化目录（24 文件，`.claude/settings.json` 仍登记已删钩子）；§5「回落 8600」删；退场清单补内网升级件、overlay/任务书里的插件字句、五份受影响测试；披露装置上 framework verifier 不跑、知识轴待内网。
- 2026-09-05 批次 5 `steps/17` 迁为本批次 `steps/02`：R35 随插件退场删除，其余 R33 / R34 / M02 与 S5–S7 原样；六跑判据里「插件发布 canonical」换成读者审查报告三条；预算起点改为步骤 1 落地后实测。
- 2026-09-05 用户指定评审会话直接改步骤 1 方案。重写要点：读者审查一条路（overlay 的 `story_reader_review` 搬到 `reference/reader-review.md`，`pre_verifier` 不再注入，framework 的 verifier 只审 spec）；任务书自足（给定 `subject_id` = story 正文 sha256、只读要求、沿用 framework 终态块），派宿主只读子代理而非 `verifier`，装置的 `.opencode/agent/verifier.md` 加第二输入形态；`post_check` 单来源四条核对，缺报告即 FAIL；同步范围补物化目录（本仓钩子与 `85e266f` 模板逐字节相同，可直接取上游）；退场清单补五份测试、内网升级件、TEST.md 两节；预算 8856 → 约 8860；六跑披露知识轴待内网。§0、§1、§3.1 drift、§3.4 插件与补丁、§3.5 保留原稿。
- 2026-09-05 外部评审五条：① 失败恢复路径——机制已有（`story_flow.py reopen` 是唯一回退出口，撤销成文登记），方案只是没写，补上并把「只审一次」改为「指纹未变不重派」；② 指纹只算 story 正文——成立，改为复用登记时已写入 story-flow.json 的 materials.digest / decisions 指纹 / story_written_at，spec 不进（由 ⑫b 拦真会影响 story 的变化）；③ blocking 非空却 PASS——成立，改为 blocker_count 等于 blocking_findings 条数且 PASS 当且仅当零；④ 批次完成条件不能只凭六跑——成立，00-总览加四条条件与验证里程碑；⑤ 步骤 2 来源标记两种写法——成立，统一为「%% 图源 <文档> §<节> #<序>」指向直接上游、只有围栏首行算。预算改口径：8860+64≈8924 超 24 行，写成待实测与用户裁定。
- 2026-09-05 用户三条裁定：读者审查不在扩展里另建派发链（AGENTS §3）；opencode 参考 claude / codex 的方式登记，只登记不改逻辑；不交上游，story 分支支持即可。评审第二次重写 steps/01：drift 收到 2 文件长期放行；overlay / pre_verifier / 任务书不动；`verifier-report.mjs` 改读 `summary.verifier_report` 的 MD、从 post_check 挪到归档门（原位置在正常流程里永远 NOT_APPLICABLE）；overlay severity MAJOR→BLOCKER 与任务书对齐；⑦ 看 NEXT 行、⑧ 补 reopen 恢复路径；manifest 1.6.0；预算 8856→约 8840。reviews/01 加后记。
- 2026-09-05 外部第十二轮三条核实成立：① 归档顺序是 check → 上传 → 登记，本地单无归档——落盘核对改进 `story-build check`（未派 N/A、已派未落盘 FAIL、在则判），远程单在上传前拦、本地单在 ⑧ 闭环后跑 check 作交付门；framework 在 verifier 之后没有钩子点（post_verifier 在 harness 内触发）。② 上游 PASS 只进汇总表、明细只列非 PASS——扩展不设例外：PASS 汇总行证据非空即可，非 PASS 明细带两键。③ summary.json 在 `<phase>/reports/`，改口径。文档同步：总览完成条件改两文件差异；步骤 2 起点 8840、超约 4 行。
- 2026-09-05 外部第十三轮三条成立：① 落盘核对靠 summary 在不在推断阶段是错的——改为 `check`（恒 N/A）与 `check --deliver`（先 spawn framework `check-receipt`，退出 0 再核报告内容）两个入口同一实现，归档 ① 与本地单 ⑧ 都用 `--deliver`；② 交付门通过 = 回执通过且报告内容三条，FAIL 报告只算解析通过；③ 步骤 2 verifier 判据同步 PASS 新格式。用户裁定预算上限改为测算值 + 100：步骤 1 8940、步骤 2 起点 + 164，写进 mechanism-budget.yaml。

- 2026-09-05 执行会话实施步骤 1，四个提交。实施前核出方案五处要修，都按修正后的做法落地：
  ① `git checkout origin/main -- .cac` 会冲掉 `.cac/commands/story.md`（story 扩展入口），
  checkout 与验收路径收窄成 `.cac/agents .cac/hooks .cac/settings.json`；
  ② 上游 opencode `commands: null`，只加一行布尔的话子代理模板没有物化落点，
  adapter.yaml 同时补 `commands.subagents`（仍是两个文件，但「只加一行布尔」不成立，
  drift 理由如实写成「登记 + 子代理物化落点」）；
  ③ 五个 overlay 的注释都指着已退场的 `author-context.ts`，一并改写；
  ④ `--deliver` 在 verifier plan 为 `disabled` 的宿主上报告本就不存在，判 NOT_APPLICABLE 而非 FAIL；
  ⑤ `framework/agents/claude/templates/hooks/record-verifier-report.mjs` 上游已删、checkout 不会删它，
  §3.1 的 `git rm` 清单漏了这一件。
- 实施结果：framework 与物化目录同 `origin/main` 的差异恰好是登记那两个文件；离线全量 633 passed；
  失效形态 FAIL 0；`adapt-scan --check` 通过；预算 8909（上限 8940）。
  `resolveVerifierPlan` 实测：`verifier_subagent=true → enabled/policy_required`，
  缺省 → `disabled/adapter_has_no_reviewer`。
- 预算与方案 §6 的差异（已具名记进 `mechanism-budget.yaml`）：scripts_mjs 实际 +37（方案估 +12），
  多出来的是交付门的接线与三条失败路径；hooks_mjs 净 +7（方案估 −30），
  读者审查的报告读法换成汇总表解析后与旧的 JSON 解析等量，没有省下来。
  hooks_mjs 2741 仍高于 target 2700 共 41 行，挂账等收口裁定。
- 2026-09-05 评审步骤 1 四提交（reviews/01 §7）：同步、登记、退场、作者输入、读者审查读法与离线证据全部亲核一致；执行者五处方案修正采纳四处。不通过两项：R36 `check --deliver` 用 `spawnSync('npx.cmd')` 不带 shell，Node 24 实测 EINVAL，交付门在 Windows 上恒「跑不了」，夹具没有一条真 spawn；R37 SKILL 归档块 ① 仍是普通 check，`--deliver` 只在 ③ 登记时跑，上传前拦不住。小项 m1（无审查员宿主静默通过要记一笔）、m2（上游状态件措辞）。预算 8909/8940，hooks_mjs 2741 高于 2700 待用户签。
- 2026-09-06 实施评审 §7 返修（`4fd1b42a`）：
  R36 交付门原来 spawn `npx.cmd`，Windows 上 Node 拒绝不带 shell 起 `.cmd`（实测 EINVAL），
  门恒走「跑不了」——改成解析 framework/harness 自己那份 ts-node 用 node 直接起，
  本仓实跑核到 stderr 已是 `check-receipt` 自己的话；补两条真接线夹具。
  R37 `SKILL.md` 归档块 ① 改 `check --deliver`。
  m1 无审查员宿主上交付门不拦但出声，走 check 的「记一笔」通道，夹具一条。
  m2 `00-上游状态.md` 改成不交上游。
  预算 scripts_mjs 2220→2240（实测 2235），总量 8932 ≤ 8940。
  **仍挂着**：hooks_mjs 2741 高于 target 2700 共 41 行，评审建议签 2750，等用户裁定。
- 2026-09-06 复核返修 `4fd1b42a`（reviews/01 §7.5）：R36 本机 Windows 实测 `check --deliver` 的 stderr 已是 `check-receipt` 原话且带 `policy_required`（opencode 登记生效）；R37 归档 ① 已改；m1 记一笔在；m2 改「不交上游」。635 绿、FAIL 0、预算 8932。步骤 1 通过；hooks_mjs 41 行超额待用户签 2750。
- 2026-09-06 用户签字 hooks_mjs target 2700→2800（评审建议 2750），峰值同值；写进 `mechanism-budget.yaml`，总量 reason 里的挂账句改平。步骤 1 收口。
- 2026-09-06 外部第十四轮四条核实成立，§7.5「通过」收回：R38 汇总行只要两格、证据取末格，三格行判 PASS（评审复现）；R39 两键在全文搜，别项的键算本项（评审复现）；R40 登记即删草稿、reopen 不恢复、skeleton 不给已写章建草稿，指引「在草稿上改」走不通——正向修法是 skeleton 以现稿正文补回草稿；m3 报错让作者「补一行」等于代写审查证据，改成恢复原始回复或重投 verifier。
- 2026-09-06 外部第十四轮返修（§7.6）：
  R38 汇总表按四列判（id / status / severity / 证据），证据取第 4 格——原来取最后一格，
  三格行的 severity 被当成证据放过去；R39 非 PASS 的两键只在 `- id: story_reader_review`
  这一条的范围内找，别项的键不算本项的；R40 `skeleton` 对「章已写完、草稿缺席」按**现稿**
  把草稿补回来（登记会删草稿目录，之后 reopen 返修没有落点），`phases/spec.md` 的返修路径
  补上 `skeleton` 那一步；m3 报错改成两分支，都不叫作者自己补——报告必须是子代理回复的
  原样落盘，作者补出来的是伪造证据。夹具四条（三格行、借键、按现稿补回且再落盘恒等、
  三种缺陷的文案都说「再投给 verifier」）。
  离线 640 passed / 181 subtests；失效形态 FAIL 0；adapt-scan --check 通过。
  预算 scripts_mjs 2240→2250（实测 2243）；hooks_mjs 用户已签 2800（现值 2761）。
  **总量 8961，超 target 8940 共 21 行**：超出的三样都是评审查出的真缺陷，
  按 §7.5 不砍方案，收口前要用户按实签 target 或在步骤 2 压回去。峰值 9260 未破。
- 2026-09-06 复核 `2c75742a`（reviews/01 §7.7）：三格行与借键两个复现现在都 FAIL，正常 PASS/FAIL 与末条 FAIL 三形态都过；reopen 后 skeleton 以现稿补草稿、再落盘恒等；报错改成重投 verifier。640 绿、FAIL 0、drift 两文件。用户签 scripts_mjs 2350；总量 8961 高于 8940 共 21 行，待签（按测算值+100 是 9060）。步骤 1 收口。
- 2026-09-06 外部第十五轮：R39 未修完，两个反例评审复现（details 为空而键名在围栏外；details 是提到键名的文字）——`detailBlock` 不止于围栏且仍子串搜。R39b：范围止于下一 `- id:` 或围栏结束，键按 YAML 结构判（优先用 yaml-lite 读本项 details）。用户签总量 8940→9100。步骤 1 收口收回。
- 2026-09-06 R39b 返修：明细两键改按 YAML 结构判。范围止于下一条 `- id:` **或围栏结束**
  （取先到者），再把这一条去掉公共缩进交给 `yaml-lite` 读；`details` 不是映射（`{}`、
  `|` 后跟一段话、解析不动）即算缺键。评审的两个反例复现过：修之前判 PASS，修之后判 FAIL。
  夹具三条（围栏外的附注、散文 details、本项排在末尾仍读得出来）。
  离线 643 passed / 181 subtests；失效形态 FAIL 0。
  预算：hooks_mjs 2784（签 2800）、scripts_mjs 2243（签 2350）、总量 8984（签 9100）。
- 2026-09-06 步骤 2 实施，三个提交：
  C1 `aa099100`（R33/R34/M02）——R33 除方案写的「数组拼串」外，真实产物上还有一处只在
  那里现形的误报：章末的 `---` 横线落在最后一节正文里，一并跳过；夹具补一份流程契约，
  否则 §9 那一组判据整块跳过，绿的是「没判」。R34 表头行排除 + 空 §9 与无 §9 分开。
  M02 词表「N 跑」补到十，bad 夹具加一行验它真的会红。
  C2 `db1f307a`（S5/S6）——图的身份由位置给、来源由围栏第一行自报，两处核同一件事
  （SR→spec 在 post_check，spec→story 在 ⑫b），缺了报主题指向功能；任务包多一节
  「spec 里的图」逐张给可粘贴围栏，不指定章；读者审查加第 5 问。标签换词，金样指纹更新。
  C3 `eb61d11d`（S7）——⑫c 两条机械事实；装置补料从 3 张图扩到 10 张（5 引 5 陪衬，
  每张陪衬都有依据）；流程图 PNG 退场，改画进 SR 的设计稿。
- 预算：hooks_mjs 2800→2840（实测 2827，方案 §4 估 +15 漏了任务包那一节）；
  scripts_mjs 2331（签 2350 内）；**总量 9115，超 target 9100 共 15 行**，
  在峰值 9300 与方案 §4 的 9125 之内，收口按实签一个数。
- 2026-09-06 评审步骤 2 三提交 + R39b（reviews/02）：R39b 三反例全 FAIL 通过；R33/R34/M02、S5/S6/S7 机制与装置逐项亲核成立，657 绿、FAIL 0、drift 两文件。不通过两项：R41 SR→spec 的图规则只在 post_check 报错里（AGENTS §4.1）；R42 用户问「adapt 顺便改了没」——没有，拿步骤 1 的树当目标 scan 判 package_not_bumped，要升 1.7.0。Q1：5.x 标签 labels_draft_only 沿用步骤 16，与 steps/02「⑪ 照核」不一致，请用户定。预算：执行者自改 hooks_mjs 2800→2840 未经签字，总量 9115>9100，建议签 9200。
- 2026-09-06 用户裁定：Q1 5.x 标签核（与 9.3 一致）→ R43；预算按建议签 hooks_mjs 2840、总量 9200，已写进预算文件。步骤 2 返修清单 R41 / R42 / R43。
- 2026-09-06 评审工作区里的 R41/R42/R43 返修（reviews/02 §8）：R42 通过（1.7.0，拿步骤 1 的树当目标判 upgrade）；R41 规则送达三处、任务包分 SR→spec / spec→story 两环；R43 合同与 ⑪ 改核、金样 5.5 说明并入章首段（符合设计 §2，评审上一轮「金样核也过」说错）。不通过：失效形态 FAIL 2——A03 `author.md` 66 行超 60（R41 加的六行），S09 正例样本还是旧标签「什么时候发生」（S6 换词时没跟）。要求一个提交落地、FAIL 0。
- 2026-09-06 复核 `df6b194e`（reviews/02 §9）：失效形态 70 条 FAIL 0；author.md 60 行；S09 正例改三段；660 绿；预算 9123 ≤ 9200；drift 两文件。步骤 2 收口，批次 6 两步全过。下一步六跑，由用户按 TEST.md 启动。
- 2026-09-06 用户纠正执行者：系统设计的图搬进 story 不是 spec，PRD 不留通道。C5 `79a12ea9` 据此改向（spec 侧核退场、⑫b 核 SR 与 spec 两份上游、骨架不预放图、status 骨架前重取任务包、审查问法去专名），离线全绿。评审（reviews/02 §10）：方向对；R44 spec 模板 §5 就是流程图，同一张图两份上游各要一个标记而围栏只认首行——改成开头连续的图源行都算；m4 story-write.md 第 203 行残留旧话。steps/02 判据与 S5 口径同步改。
- 2026-09-06 复核 C6 `cc9671e3`（reviews/02 §11）：一个围栏两行标记两处核各自通过、正文里的标记不算登记、换标记不叠加，三件事评审自己探过；m4 旧话零命中；662 绿、FAIL 0、预算 9122、drift 两文件。步骤 2 收口，批次 6 两步全过，扩展 1.7.0。下一步六跑，由用户按 TEST.md 启动。
- 2026-09-06 六跑评审（reviews/03）：opencode 上 verifier 启用、派一次、报告按上游契约、交付门拦下 review 两处真问题并经 reopen 走通、图一围栏两标记、5.x/9.3 标签、§9/§10 不误报、知识链 16 条有落点、未实名矛盾定口径、停等 2 次——都亲核。没过：S7（10 张全引、E 无图行、规则与报错二选一）；作者翻源码 59 次（init_analysis「本阶段注入的画像」无通道、acceptance.yaml 路径写错、禁用词表只在脚本、build/登记顺序两处文本相反）；scorecard 写「读源码 0 次」不实。三轴建议 82/90/55。建议 steps/03：R45 路径、R46 S7 单向、R47 顺序、R48 画像路径与禁用词进 md。
