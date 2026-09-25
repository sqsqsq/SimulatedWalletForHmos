# 盘点 C · `hooks/**`、`rules/*.overlay.yaml`、`knowledge/**`、`manifest.yaml` 与 framework 挂接点（只读，2026-09-16，基线 9b4637fa）

## 0. framework 挂接点

| 挂接 | framework 读取处 | 扩展供给 |
|---|---|---|
| 扩展加载 | `extension-loader.ts:153-160/177-222/311-341` | `manifest.yaml:33-49/63-93/95-101` |
| overlay 合并 | `profile-loader.ts:174-176`（扩展最后合并覆盖 profile），`mergePhaseRuleSpec:73-104` 浅合并 | `rules/*.overlay.yaml` |
| overlay 进 verifier | `harness-runner.ts:1180` `YAML.stringify(phaseRule)` → ai-prompt.md | `semantic_checks.<id>.description/ai_prompt_hint` 原文进 prompt |
| `phase_input_snippets_extra` | `context-exploration.ts:289-305` → `:512-529` BLOCKER，子串大小写不敏感匹配 `key_inputs_read` | 五份 overlay 末段 |
| post_check / pre_verifier | `hooks-dispatcher.ts:82-98/135-203`；`harness-runner.ts:1107/1124` | `hooks/<phase>/post_check.mjs`、`hooks/shared/pre_verifier.mjs` |
| 失败严重度 | `hooks-dispatcher.ts:47-49` extension 默认 MAJOR | `gate.mjs:46,107` 一律 BLOCKER |
| 知识进作者上下文 | 不进：`extension-runtime.ts:16-27` 只渲染路径 | — |

## 1. 机制清单

### 1.1 基础设施
- 激活清单 `provides.knowledge`（`knowledge.mjs:341`）：写成 `[]` 与不写同义。
- `provides.hooks` 只登记 post_check/pre_verifier 两事件（dispatcher 支持 9 种）。
- `guard()`（`gate.mjs:35-54`）入口不符静默 `ok:true` 不留痕；`gate()`（`:70-108`）`skipped` 非空而 problems 空时返回 `ok:true`+message，该 message 不进 harness 报告（dispatcher 只在 `ok:false` 记）。
- `ext-post-check.json` 留痕（`evidence.mjs`）无任何代码读者。
- `paths.mjs:57` 注释错位。
- `yaml-lite.mjs`：见 §8。

### 1.2 知识派生层（`knowledge.mjs`）
- `kind` 封闭集合；index 件 `protocol` 必须为 1，顶层 `knowledge/README.md` 没写 protocol。
- 条目表按列名 `h.includes(keyword)` 取格（`:109-130`）；编号正则不匹配的数据行静默 `continue`（`:204`）。
- 一文件一域，只有两份显式写 `domain:`。
- 执行体解析 `parseExecutors:184-189`：段首词 ≤6 字符、分隔符限 `。；;`。
- 评审动作↔人工互核（`:217-220`）：DLV-01「模型…人工：…」既非评审动作又带人工，不报。
- 探针四形态封闭（`:137-178`）。
- markdown 转义竖线：`knowledge.mjs:92-103` 处理；`spec/post_check.mjs:51-54` 处理；`plan/post_check.mjs:104-105`、`review/post_check.mjs:44` 不处理——四份切列实现。
- facts 面派生：`component-profile.md` 两面无 `confirmed:`，既不报错也不进 unconfirmed。
- patterns：`applies_when/not_applies_when/triggers_usecase_spec` 三个 frontmatter 字段零读者。
- `selfCheck` 四判据只在 `spec/post_check.mjs:181` 调用一次（形态代理见 §10）。

### 1.3 spec 判断真源层（`knowledge-use*`）
- `manifestDigest` 算激活文件全文，改一个错别字全仓在途需求 digest 失配。
- `renderSkeleton`（`document.mjs:107-167`）注释行 `# ${force} · ${constraint} · 命中：${when} · 验法：${executors}`（`:138-139`）——处置列不送达。
- `coverageProblems`（`validation.mjs:67-262`）约 25 条子判据；`isEmptyReason` 只认空串与「不涉及。」。
- `contractNames` §9 验真：判表头靠「下一行是分隔行」。
- `zoneProblems` 字节级比对。
- CLI `init` 拒绝覆盖，知识升级后无「重生成骨架保留旧判断」路径。

### 1.4 契约/义务/探针
- `obligationsFromContracts`（`obligations.mjs:54-93`）五类实体；`components` 顶层与 `state[]` 都收，与 `misplacedMust` 规则不对称。
- `misplacedMust`（`:101-116`）；`state_management` 同时在 `ENTITY_KINDS` 与越位黑名单。
- `verifyProblem`（`:22-38`）`VERIFY_BY_EXECUTOR` 只映射「实机」。
- `flowStyleProblems`（`contracts.mjs:144-158`）只查一层。
- `knowledgeCriteria`（`contracts.mjs:207-239`）spec 传 `['criteria']`，ut/testing 传 `['criteria','boundaries']`。
- `resolveEntityRef`（`contracts.mjs:85-136`）files/resource_keys 用 `includes`；coding 只用 `tail`，`ok/reason` 被丢弃。
- `runProbe` 四形态（`probes.mjs:122-199`）；`blankComments` 不处理转义、URL `//` 当注释；`filesForEntity` 放宽只在一处出声。

### 1.5 verifier 三件套
- `pre_verifier.mjs`：`overlayCheckIds` 用两空格缩进正则认 id（`:61`）；`SOURCE_OF_TRUTH` 只有 spec/plan 两键，其余 fallback 到 plan 文案（`:73`）；`:103`「唯一真源，读哪个都行」。
- `reader-review-task.mjs`：只在 spec 出；story 全文与 template 全文内嵌；会议材料只给路径（`:135-146`）；自称只出数据但含方法性指令（`:89/107-108/126/152/171-172`）。
- `verifier-report.mjs`：唯一调用方 `delivery.mjs:95`；`pre_verifier.mjs:15` 说它由 post_check 调，不符；`PER_UNIT_TABLE_RE` 硬判。

## 2. 知识管线全链：谁决定 / 谁使用

| 列 | 谁读（机器） | 谁读（人/模型） |
|---|---|---|
| 编号 | 形态/去重/集合核/must.rule/注释禁写/acceptance 桥 | 全链 |
| 约束 | 存 entry，唯一机器用途渲进骨架注释 | 作者、verifier |
| 强制力 | 值域、豁免规则、§10 列、coding/review 分支 | 骨架注释 |
| 命中条件 | 零机器读者，只进骨架注释 | 作者判 applicable 的唯一依据 |
| 处置 | 只取「是否以（评审动作）开头」；渲进评审动作清单 | **不进骨架** |
| 验证（执行体） | 值域、must.verify、§10 验法列 | 骨架注释 |
| 探针 | coding 执行；plan 无落点 skipped | coding author.md |

作者做适用判断那一刻看到的是四样：强制力、约束、命中条件、验法；处置不到；命中条件与处置不是分栏送达。`author.mjs:96-98` 只列 facts 文件路径不列 constraints 路径。`notes`（落法附注）与 `when` 一样无机器消费者。桥接键：`acceptance.yaml.criteria[].knowledge_rule`；分派单源 `must.verify`。

## 3. 六阶段 post_check 判据与早退

**spec**（470 行）早退链：guard 不符→`ok:true`；spec 不在→skipped；`activeKnowledge` 抛→只返回这一条（:175-177）；缺「规约约束要求」章→只返回这一条（:188-193）；`readUse` UseError→返回；`coverageProblems` 非空→提前 return 不核投影（:219）。14 类判据（章节/术语解释列/文档坐标/客户端词/知识自检/§10§11 在/不并进§9/coverage/zone/acceptance 桥双向差集/数值来源）合成一个 check id `knowledge_exit_structure`。
**plan**（376 行）：plan 不在→skipped；`activeKnowledge` 抛→返回；契约 error→返回；契约不存在→返回。9 条判据；`planPatternChoices` 按位置取列（与「按列名」原则相反）。
**coding**（174 行）：4 条判据；warnings 不进 problems 只拼 detail；`resolveEntityRef` 的 `ok:false` 无信号；`:166-167` 注释「名字沿用、判的不是落实」。没有任何现役探针能在 coding 产生 problem（blocking+红线组合不存在）。
**review**（131 行）：5 条；依据列长度 ≥6 字数阈值（`:111-116`），与 `validation.mjs:14-17` 拒绝字数下限立场相反；pattern id 全行子串匹配。
**ut / testing**：文件头注释写 `ut_layer` 是分派单源，代码读的是 `ob.verify`；acceptance 缺失与没写文案相同。testing 无 `exploration_thresholds`（framework `ContextExplorationPhase` 无 testing）。

## 4. 六份 author.md 重复
「推进不逐段问」blockquote 6/6 逐字相同；「must 是本阶段知识来源」4 份；ut/testing 互为镜像；跑命令一句 6/6；与 overlay 跨文件重复三处。

## 5. overlay
`semantic_checks` 的 id 清单由扩展自己正则扫；spec overlay 210 行，`story_reader_review` 占 87 行/42%。重复：「每条裁决给得出回查位置」7 处、「按未裁处理」8 处、「只是把 X 复制一遍」7 处、末段 7 行注释块五份逐字相同。

## 6. 三件套内容重叠
「不逐条对账/不出裁决表」三处；「details 写…」三处同义；「真源是 knowledge-use.yaml」六处；「不涉及三个字不构成依据」七处。

## 7. 探针
`absent_regex` / `present_in_method`（遇第一个含方法的文件即返回）/ `referenced_outside_definition` / `count_eq`。现役 4 条：UX-01 阻断 absent_regex（基线，coding 侧只 warning）；OBS-01/02/03 present_in_method（红线非阻断，只 warning，且须 must 挂 `interfaces[].methods[]`）。

## 8. yaml-lite 边界 vs 契约写法
不支持锚点、复杂键、流式映射；中文键解析不了；缩进不一致直接抛；序列项与映射键混块抛。`flowStyleProblems` 是对边界的补偿。`verifier-report.mjs` 用它读模型自由生成的 YAML，遇不支持形态报「结构块读不出来」。framework 用 `yaml` 包，同一份文件两套读法。

## 9. 知识内容本身（15 条命中条件可判定性）
不能不看实现判：DFX-01（命中要知会不会调）；部分：DFX-02（新增依赖 plan 才定；基线表四行 `<待补充>`）、ENV-01。OBS-02/03 命中条件写「同上」。COMPAT-01 在本仓恒不命中（零网络出口）。RES-02 与 DLV-01 联动写在知识里无机制执行。DLV-02 附注指向不存在的「安全隐私域对外接口条目」。`constraints/README.md:32-41` 是第二份域清单。三份附注标题「判定附注」而解析只认「落法附注」。facts 10 面 0 个未确认，`verified` 判据恒不触发。

## 10. `selfCheck` 四判据形态代理
1 扩展名正则（`Logger\.`、`createBusinessOrder` 不拦）；2 只查行首 `|` 且同行 ≥3 阶段词（竖排矩阵不拦）；3 编号正则（按名引用不拦）；4 目录名正则（中文引号前缀匹配不到）。

## 11. 跨机制观察
11.1 多处重复的提示（九组，见 §4–§6）。
11.2 形态代理：`context_exploration_inputs_coverage` 子串、coding 落点标识符存在、review 依据 ≥6 字、ut/testing AC 编号正则、review pattern 子串、verifier-report 形态、selfCheck、plan 章位置、spec 数值来源、spec 文档坐标。
11.3 互为真源冲突：两份域清单；plan 设计章名两份抄本；切列四份；acceptance 集合名两份读法；YAML 两套解析器；`state_management` 既认又拒；`verifier-report.mjs` 宿主三说法；hooks ↔ skills 双向依赖。
11.4 framework vs extension 读法差异：overlay 解析失败 framework 静默/extension 出声；扩展可无声覆盖 profile 同名判据；hook 失败扩展自提 BLOCKER；PASS 两套留痕；`contracts.yaml` 路径同源解析器不同；framework 从不读知识正文；`phase_input_snippets_extra` 在 schema 1.0.0 下整条失效；testing 无留痕；扩展生成器直接改 framework 法定产物 spec.md。
11.5 单点：`acceptance.yaml` 不存在时 spec 不报；`:219` 提前 return 与 gate.mjs「一次列全」相抵；`planPatternChoices` 按位置取列；coding `ok:false` 无输出；skipped 的 check id 全是中文串；`manifest.yaml` version 1.9.1；`knowledge-use.mjs init` 拒绝覆盖。
