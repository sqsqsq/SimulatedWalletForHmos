# 04 · story 独立性方案（与 framework 适度解耦）

> 读者：本方案的评审者与实施者。议题约束（用户原话）：一定程度解耦以增强可移植性与
> 可扩展性，**不强求**；不能为了解耦导致现有 story+framework 配合模式出问题。
> 已吸收 [06-Codex-方案检视意见](06-Codex-方案检视意见.md) 的 M1/M2（裁决记录见 00 §6）。

## 1. 耦合现状结论

framework 对 story **零感知**（framework 目录内 grep story 零命中），所有耦合都是 story→framework 单向 + 经公开扩展协议反向挂载。分级：

- **强耦合（拿掉 framework 即失效）**：① `spec/spec.md` 章节/编号体系被 story 两个脚本硬编码消费（`merge-story.mjs:158,168-181` 与 `story-build.mjs:416` 的同一 SPEC_ID 正则、术语表表头、技术契约章名）；② lifecycle-hooks + phase_rules_overlays 协议（story 全部机器门禁与语义门禁的执行环境）；③ SKILL.md 终点硬编码 framework spec SKILL 路径。
- **弱耦合（读配置，均有 fallback）**：`framework.config.json` 仅两键——`paths.features_dir`（**六处重复实现**：story_flow.py:111 / import_sources.py:80 / story.js:62 / story-build.mjs:82 / merge-story.mjs:45 / hooks 两份）、`architecture.outer_layers[].id`（lint-rules.mjs:45-79 运行时推导）。
- **纯约定**：`AR/ SR/ RR/ inbox/ story-src/` 等目录全部由 story 自定义；脚本以 `__dirname` 上溯 5 层定位工程根。
- **既成漂移（bug 级）**：framework 的上游读取记录契约是 `context/facts.md` frontmatter 的 **`key_inputs_read`** 字段（`context-exploration.ts:31,514` 消费，AR90004 实例已在用）；story 侧两处仍指向已弃用的 `spec/context-exploration.md`：`hooks/spec/story_on_context_load.md:7` 与 `rules/spec-rules.overlay.yaml:93-103`（`upstream_inputs_coverage`）——后者检查一个 framework 已不生成的文件，**等价于恒 SKIP**，这正是漂移未被发现的原因。

## 2. P0 · 漂移修复（必做，独立批 0，改动极小）

framework 现行契约里 `key_inputs_read` 字段就在 `context/facts.md` frontmatter——story 侧直接对齐，不发明任何同义落点：

- `story_on_context_load.md:7`：上游必读记录点改为「记入 `context/facts.md` frontmatter 的 `key_inputs_read`」（三份上游文件路径照旧）；
- `spec-rules.overlay.yaml` `upstream_inputs_coverage`：判据改为「SR/RR 存在时，facts.md 的 `key_inputs_read` 须含它们」，端云矛盾比对逻辑不变；
- 回归：TEST.md 案例复跑，该检查在有 SR/RR 的案例上从恒 SKIP 恢复为真实生效。

## 3. P1 · features_dir 读取收敛（排最后批）

六处重复实现收敛为跨语言各一份、语义一致：

- **JS 侧**：共享模块 `skills/story/scripts/lib/paths.cjs`（CJS——`story.js` 是 CJS 只能 require；`.mjs` 侧用 Node 对 CJS 的 default import 直接消费），配互操作单测（CJS require 与 ESM import 各取一次，结果全等）；
- **Python 侧**：`scripts/lib/paths.py` 语言内实现（不跨语言调用）；
- **跨语言 parity test**：同一组 fixture（配置存在/缺失/非法三态）分别驱动 JS 与 Python 实现，断言返回值逐字节一致；
- `hooks/spec/post_check.mjs` 对 `lint-rules.mjs` 的跨目录 import 登记为已知耦合，不改（扩展包整体移植时两目录同进退）。

## 4. P2 · spec 形态声明同源化（做，排最后批）

**问题的根**：spec 编号（S/F/E/AC/BD/NFR）与术语表表头的**定义源在 framework**——spec 模板 `framework/skills/feature/spec/templates/feature-card.md` 产生编号，`framework/harness/scripts/check-spec.ts:887` 用自己的正则校验，两者都只读。story 侧现有**两处**镜像硬编码：`merge-story.mjs:158` 与 `story-build.mjs:416`（同一 SPEC_ID 正则）。

**终态**：story 侧对 spec 形态的声明只存在一处——`contracts/story-chapters.json` 新增 `spec_shape` 段（编号正则、术语表表头、技术契约章名）；**`merge-story.mjs` 与 `story-build.mjs` 两个消费方都从它读取**，零硬编码。

**同源保证**（回答「编号在哪定义、两处要同源」）：定义源不可改（framework 只读），故同源 = story 侧唯一镜像 + **机械对账**——对账看护测试用 `spec_shape` 声明的正则/表头扫 framework 的 spec 模板与 check-spec.ts 正则，对不上即红。内网换 spec 模板时（其 framework 同步换），改配置一处，对账测试对着他们的模板生效；ADAPTATION §3.6 列「核对 spec 形态声明」。

**裁判独立**：评测侧 `assert_story.py` 继续**独立实现**其机械判据，不共享 `spec_shape`——被测产品与裁判共享同一配置会一起漂移而无人发现（该域「刻意分开维护词表」的既有纪律同源）。

**成本**：story-chapters.json 结构变更 + `test_story_build.py` / `test_merge_story_check.py` 判据同步 + 新增对账测试与 parity 断言。

## 5. 不做清单（本轮明确不碰）

- SKILL.md 终点跳 framework spec 的硬路径：流程契约不是耦合病，抽象它只会让指令变绕；
- `__dirname` 上溯 5 层的工程根定位：所有脚本已支持 `--project-root` 显式覆盖；
- lifecycle-hooks/overlay 协议依赖：这是 story 质量门禁的执行环境，解耦等于自废门禁；
- `lint-rules.mjs:65` 正则里的 `framework/` 通用段：目录名跨工程稳定（vendored 约定）。

## 6. 行为不变清单（实施轮回归基准）

P0–P2 全部落地后，以下行为必须逐条与现状一致（TEST.md 实跑 + 离线断言双口径）：

1. `merge-story --check` 对既有金标案例的 pass/fail 结论不变；
2. `post_check` 三份产物齐备性、§9 结构、红线扫描结论不变；
3. 六处 features_dir 读取在「配置存在/缺失/非法」三态下返回值不变（parity test 钉住）；
4. 非 story feature（无 `AR/story-flow.json`）各阶段行为完全不变（探针静默让路）;
5. `--phase extensions` 扩展校验通过;
6. `upstream_inputs_coverage` 从恒 SKIP 恢复为真实生效（P0 的正向变化，非回归项）。

## 7. 红线

不动 `framework/`（物理写保护 + 本方案自律）；不改 hook 事件名/ctx 契约/manifest schema 的用法；`integrity.drift_allowlist` 既有的 spec contract 热修为上游待修项，本轮仅在 00 计划登记跟踪。
