# 步骤 14（main → story 同步，framework 升 3.0.0 正式版）· 独立评审（Claude，2026-09-05）

对象：`99b4d584`（1.1 反合）、`c39e50d4`（1.2 opencode 适配重打 + subject @2）、`07b7bb8a`（1.3 author 适配重打）、
`af5554f3` / `01492bd8` / `1c8d03d1`（交接件、提案、报告文本）。全部亲自复跑。

## 1. 结论

**机制通过，一条返修**：`artifacts/01-framework-opencode-verifier.patch` 与它的交接件停在旧基线，在 3.0.0 正式版上打不上、也不含 @2 的插件改动；要按新基线重生成。其余通过。

## 2. 核过的事实

| 项 | 结果 |
|---|---|
| `framework/` 与 main（`363c6e13`，3.0.0 @ `85e266f`）的差异 | 恰好 18 个文件，与 `doc/extensions/framework-patch.yaml` 声明的 18 条逐一相等，无多无少 |
| `drift_allowlist` | 21 条：18 条对应真实差异；`harness/state/.gitkeep`、`harness/trace/gap-notes.template.md`、`harness/trace/trace.schema.json` 三条与 main 已无差异（批次 5 之前的遗留），是陈旧条目，不报错，顺手删 |
| 作者入口 12 文件 | 把 `artifacts/04-*.patch` 打在纯净 main 树上，12 个文件与 story 逐字节相同；04 交接件已写明 3.0.0 复验 |
| opencode 6 文件 | `artifacts/01-*.patch` 在纯净 main 树上 **打不上**（`adapter-schema.yaml:444` 冲突，上游改写了同一段），且不含 1.2 的 @2 改动；6 个文件与「main + 旧补丁」都不同。01 交接件基线仍写 `7401f22` |
| `adapter-schema.yaml` 手工合 | 在上游新措辞上只加 `task_tool_result` 一档与其说明，`subagent_stop` 的上游新文字保留；合理 |
| subject @2 | 插件与 `verifier-request.ts` 的 `canonicalRequestInput` 字段与顺序逐项相同；`.opencode/` 物化件与模板逐字节相同；claude 钩子同为 @2 |
| 离线 | 608 绿（并行 28 s）；失效形态 70 条 FAIL 0、委派 15；`adapt-scan --check` 要先 `--scan`（工作目录未建，非缺陷） |

## 3. 返修

- 从 `git diff main story -- <6 个 opencode 文件>` 重生成 `01-framework-opencode-verifier.patch`，路径剥 `framework/`；交接件基线改 `85e266f`，验证行改为「纯净 3.0.0 树 apply 后逐字节一致」，并写明 `adapter-schema.yaml` 那段是在上游新措辞上加档。
- 删 allowlist 三条陈旧条目（可与上一条同一提交）。

## 4. 对执行会话《14-四跑实跑报告》的独立看法

- §2「第一次起跑 T1–T5 全部一次通过、story 段停 2 次」：证据已随工作区重建丢失，报告自己也这么写；不作依据。
- §4.2 对 T1 的判法（看上一轮有没有选过 supplement）仍绑在 gate 记录上，覆盖不到探针证明的第二级关卡回拨（`reviews/11` §14.4 E1）；步骤 15 的 F3 按轮次与本级侧车判，两处一起关。
- §6 第 2 条「读 checker 源码 41 次要查读的是哪几个」：已查明——`story-build.mjs` 12 次、`story_flow.py` 6 次、`knowledge-use.mjs` 2 次，起因分别是图片引用串、附录 D/E 形态、补料顺序（`reviews/11` §14.4）。
- 三轴建议分：性能 72 与 Knowledge 90 无异议；**产物结果 90 偏高**——除报告已扣的「主路径没画图」外，还有术语成列表、异常九段标签、验收九节各一条、`§9.1` 病句、评审记录漏进 framework 档位术语、附录 A/B 相对 spec §9 略写（`reviews/11` §14.8、步骤 15 §0）。我的建议是 80–85；最终由用户定。

## 5. 五跑首次起跑暴露的同步遗漏（2026-09-05 15:50）· 评审漏判

五跑（`story-suite-20260905-145704`）story 段 3 次停等（材料、范围、术语），T1 生效；verifier 15:35 起跑、15:42 交稿，但插件把 request 判成 `invocation_request_unparseable`，报告只落 bedside，主模型从 15:42 起在 framework 里查原因，卡住。

根因：framework 3.0.0 正式版把 verifier request 的 `schema_version` 从 1.0 升到 1.1（`verifier-request.ts` 第 32 行，claude 钩子模板同步为 1.1），而步骤 14 · 1.2 重打 opencode 适配时只跟上了 subject @2 的派生，`record-verifier-report.js` 第 55 行的 `VERIFIER_REQUEST_SCHEMA_VERSION` 仍是 `"1.0"`——插件第 160 行按它整份拒收。字段集两边一致，只差这一个常量。`.opencode/plugin/` 物化件同样是 1.0，测试夹具（`test_opencode_verifier_publisher.py` 第 140 行）也写的 1.0，所以 24 条全绿。

我在 §2 核 @2 时只比了 `canonicalRequestInput` 的字段与顺序，没比 schema 常量——漏判。

修法（执行会话）：模板与物化件常量改 `"1.1"`；夹具改 1.1 并加一条「harness 现值 schema 与插件常量相等」的对账（从 `verifier-request.ts` 读，不写死）；`artifacts/01-*.patch` 重生成。这一跑的工作区带的是旧插件，修完要重跑。
