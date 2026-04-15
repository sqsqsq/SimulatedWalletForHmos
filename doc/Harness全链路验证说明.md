# Skill + Spec + Harness 全链路验证（home-page）

## 本文档在做什么 / 不做什么

| 范围 | 说明 |
|------|------|
| **本文档覆盖** | 在已有产物（PRD、design、代码、review 报告、UT、测试计划/报告等）的前提下，**一次性跑完 6 个 phase 的脚本 Harness**：读 Spec 与文档/代码，执行 `check-*.ts`，生成 `harness/reports/...` 与 `ai-prompt.md`。 |
| **本文档不覆盖** | **不是**「一键完成」PRD → 设计 → 编码 → Review → UT → 真机测试的**开发流水线**。各阶段文档与代码仍需按 `skills/` 中 Skill 人工或借助 AI 编写；Harness 是每步归档后的**质量门禁**。 |
| **AI Harness** | 脚本只生成 `ai-prompt.md`，**不会**自动调用任何大模型；语义审查需自行把 prompt 发给所选模型。 |

## 一次性跑 6 个阶段（仅脚本检查）

在仓库根目录下执行（PowerShell）：

```powershell
Set-Location "harness"
foreach ($p in @('prd','design','coding','review','ut','testing')) {
  npx ts-node harness-runner.ts --phase $p --feature home-page
}
```

单阶段示例：`npx ts-node harness-runner.ts --phase coding --feature home-page`

## 本次为打通链路做的要点

1. **Markdown CRLF**：`harness/scripts/utils/markdown-parser.ts` 对 `split(/\r?\n/)` 统一处理，避免 Windows 下标题解析失败。
2. **contracts 快照**：`specs/features/home-page/contracts.yaml` 与当前 `phone/` 工程对齐；完整规划见 `contracts.planned.yaml`。
3. **测试计划 AC-G 编号**：`check-testing.ts` 中关联 AC 的正则支持 `AC-G1` 等形式。
4. **Hypium 入口文件**：`check-ut.ts` 跳过仅导出 `testsuite()`、无 `describe` 的入口 shim（如 `List.test.ets`）。
5. **真机测试文档**：`doc/features/home-page/test-plan.md`、`test-report.md` 覆盖 acceptance 中全部 P0/P1 的 AC 追溯。
6. **Cursor 跳板**：`.cursor/skills/*/SKILL.md` 指向 `skills/` 下正文。

报告输出目录：`harness/reports/home-page/{prd|design|coding|review|ut|testing}/`。
