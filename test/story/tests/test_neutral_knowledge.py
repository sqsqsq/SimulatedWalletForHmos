"""行为测试：往激活清单里加一条机制**不认识**的知识，全链要自己接住它。

这条测试守的是「三类知识的消费与传递不靠硬编码」——新增一条 fact / constraint / pattern，
**不改任何通用脚本**，它就该分别到达正确的消费者：

  spec：完备性判据要求它有去处（漏了就点名），生成区里出现它；
  plan：命中的约束要在契约里有实体扛着，登记的候选要在选型表里有结论；
  下游：义务经 contracts 的 `must.verify` 分派到对应阶段。

为什么要有它：判据里凡是写死了域前缀、条目编号、模式名的地方，在现有知识上都测不出来
——现有知识恰好满足那些写死的假设。只有塞一条机制从没见过的知识，才知道它是按数据走的，
还是按当初那几条的样子写的。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
FEATURE = "NK90001"

# 机制没见过的一条约束域、一份事实、一个模式。前缀 NEU 不在任何脚本里。
NEUTRAL_CONSTRAINT = """---
name: 中性域
kind: constraints
domain: NEU
---

# 中性域

| 编号 | 约束 | 强制力 | 命中条件 | 处置 | 验证（执行体） | 探针 |
|---|---|---|---|---|---|---|
| NEU-01 | 中性域的第一条：出口要带一个可回查的标识 | 基线 | 有新增出口 | 出口处生成标识 | 模型：核对生成点 | 无 |
| NEU-02 | 中性域的第二条：重复触发时复用同一个标识 | 基线 | 有重试路径 | 重试复用 | 模型：核对重试分支 | 无 |

## 落法附注

标识由入口生成一次，向后透传；重试不重新生成。
"""

NEUTRAL_FACT = """---
name: neutral-facts
kind: facts
---

# 中性工程画像

## 出口登记

本工程的出口统一登记在中性出口表里。
"""

NEUTRAL_PATTERN = """---
name: neutral-pattern
kind: patterns
applies_when: 同一标识要贯穿多个步骤
not_applies_when: 单步完成、无状态贯穿
roles: [标识生成者, 标识消费者]
coordinator_role: 标识生成者
sections:
  - 上篇 · 适用与选型
---

# 中性模式

## 上篇 · 适用与选型

多步之间要传同一个标识时适用；单步完成时不适用。
"""

SPEC_HEAD = """# {feature} spec

## 9. 技术契约

### 9.1 端云接口

| 名称 | 用途 |
|---|---|
| 中性出口接口 | 带标识的出口 |

## 10. 规约约束要求

<!-- 由 knowledge-use.yaml 生成 -->

## 11. 设计模式候选登记

<!-- 由 knowledge-use.yaml 生成 -->
"""


def node(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=90)


def as_url(path: Path) -> str:
    return json.dumps(path.resolve().as_uri())


class NeutralKnowledgeCase(unittest.TestCase):
    """一份工作区：真实扩展 + 三份中性知识，只改 manifest 与知识正文。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        self.ext = self.root / "doc" / "extensions"

        # ① 放三份中性知识
        (self.ext / "knowledge" / "constraints" / "neutral-domain.md").write_text(
            NEUTRAL_CONSTRAINT, encoding="utf-8")
        (self.ext / "knowledge" / "facts" / "neutral-facts.md").write_text(
            NEUTRAL_FACT, encoding="utf-8")
        (self.ext / "knowledge" / "design-patterns" / "neutral-pattern.md").write_text(
            NEUTRAL_PATTERN, encoding="utf-8")

        # ② 只在 manifest 的激活清单里加三行——**通用脚本一个字不改**
        manifest = self.ext / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        text = text.replace(
            "    - knowledge/design-patterns/page-interaction.md",
            "    - knowledge/design-patterns/page-interaction.md\n"
            "    - knowledge/constraints/neutral-domain.md\n"
            "    - knowledge/facts/neutral-facts.md\n"
            "    - knowledge/design-patterns/neutral-pattern.md")
        manifest.write_text(text, encoding="utf-8")

        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "spec").mkdir(parents=True)
        self.spec_path = self.feature_root / "spec" / "spec.md"
        self.spec_path.write_text(SPEC_HEAD.format(feature=FEATURE), encoding="utf-8")
        self.use_path = self.feature_root / "spec" / "knowledge-use.yaml"

    # ---- 驱动 ----

    def module(self, name: str) -> Path:
        return self.ext / "hooks" / "shared" / name

    def eval_js(self, expr: str) -> str:
        proc = node("--input-type=module", "-e",
                    f"const u = await import({as_url(self.module('knowledge-use.mjs'))});"
                    f"const k = await import({as_url(self.module('knowledge.mjs'))});"
                    f"const root = {json.dumps(self.root.as_posix())};"
                    f"process.stdout.write(String({expr}));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def entries(self) -> list[str]:
        return self.eval_js("k.activeKnowledge(root).entries.map(e => e.id).join(',')").split(",")

    def write_use(self, *, neutral: str | None = None) -> None:
        """一份完备的判断：中性域按参数写，其余域整域不适用。"""
        rows = ["schema: 1", f'manifest_digest: "{self.eval_js("u.manifestDigest(root)")}"',
                "facts:",
                "  - id: neutral-facts",
                "    used_for: 出口登记在哪张表按它取",
                "constraint_domains:"]
        for prefix in ("UX", "SEC", "DFX", "OBS", "RES", "COMPAT", "ENV", "DLV"):
            rows += [f"  - prefix: {prefix}", "    applicable: false",
                     f"    reason: 本需求不涉及 {prefix} 域管的那类改动"]
        rows.append("constraints:")
        rows.append(neutral if neutral is not None else (
            "  - id: NEU-01\n"
            "    applicable: true\n"
            "    requirement: 中性出口接口在入口生成一次标识并向后透传\n"
            "    contract: 中性出口接口\n"
            "  - id: NEU-02\n"
            "    applicable: false\n"
            "    reason: 本需求没有重试路径，出口只走一次"))
        rows += ["patterns:",
                 "  - unit: 出口标识的生成与消费",
                 "    candidate: neutral-pattern",
                 "    signal: 标识由入口生成、被后续两个步骤消费，贯穿多步"]
        self.use_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def render(self) -> subprocess.CompletedProcess:
        return node(str(self.module("knowledge-use.mjs")), "render",
                    "--feature", FEATURE, "--project-root", str(self.root))


class TheNewDomainReachesEveryConsumer(NeutralKnowledgeCase):
    """新增一条机制不认识的知识，各环节自己接住它——没有一处要改脚本。"""

    def test_the_new_entries_are_derived(self) -> None:
        """派生先认得它：域前缀、条目、模式都不是写死的。"""
        ids = self.entries()
        self.assertIn("NEU-01", ids)
        self.assertIn("NEU-02", ids)
        self.assertIn("neutral-pattern",
                      self.eval_js("k.activeKnowledge(root).patternIds.join(',')"))

    def test_leaving_the_new_domain_unjudged_is_named(self) -> None:
        """完备性判据认新条目：不判它就点名——这正是「机制不认识」时会静默漏掉的那一类。"""
        self.write_use(neutral="  - id: NEU-01\n    applicable: false\n"
                               "    reason: 本需求没有新增出口")
        proc = self.render()
        self.assertEqual(1, proc.returncode, f"漏判 NEU-02 却过了：{proc.stdout}")
        self.assertIn("NEU-02", proc.stderr)
        self.assertIn("没有去处", proc.stderr)

    def test_a_complete_judgement_reaches_the_projection(self) -> None:
        """判全之后，中性域的结论出现在 §10 生成区里。"""
        self.write_use()
        proc = self.render()
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.spec_path.read_text(encoding="utf-8")
        zone = text.split("knowledge-use:begin 规约约束要求")[1].split("knowledge-use:end")[0]
        self.assertIn("NEU-01", zone)
        self.assertIn("中性出口接口", zone)
        self.assertIn("NEU-02", zone, "不命中的依据也要在这一区里")

    def test_the_new_pattern_is_a_legal_candidate(self) -> None:
        """新模式一登记就是合法候选——候选在册与否查的是激活清单，不是一份写死的名单。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        zone = (self.spec_path.read_text(encoding="utf-8")
                .split("knowledge-use:begin 设计模式候选登记")[1]
                .split("knowledge-use:end")[0])
        self.assertIn("neutral-pattern", zone)

    def test_an_unregistered_pattern_is_still_refused(self) -> None:
        """反面：没登记进激活清单的模式名照样不是合法候选。"""
        self.write_use()
        text = self.use_path.read_text(encoding="utf-8")
        self.use_path.write_text(
            text.replace("candidate: neutral-pattern", "candidate: 我自己想的模式"),
            encoding="utf-8")
        proc = self.render()
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在册", proc.stderr)

    def test_the_contract_name_is_checked_against_the_new_spec(self) -> None:
        """落点名核的是这份 spec 的 §9，不是一份预置清单。"""
        self.write_use()
        text = self.use_path.read_text(encoding="utf-8")
        self.use_path.write_text(
            text.replace("contract: 中性出口接口", "contract: 不存在的接口"),
            encoding="utf-8")
        proc = self.render()
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在 §9 技术契约里", proc.stderr)


class ThePlanSideReadsTheSameSource(NeutralKnowledgeCase):
    """plan 侧的集合一致读的是同一份真源——中性域的命中条目要在契约里有实体扛着。"""

    def plan_check(self) -> str:
        contracts = self.feature_root / "contracts.yaml"
        (self.feature_root / "plan").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "plan" / "plan.md").write_text(
            "# 计划\n\n## 知识决策（设计输入）\n\n### 设计模式选型\n\n"
            "| 适用单元 | 候选 | 选型 | 角色 | 理由 |\n|---|---|---|---|---|\n"
            "| 出口标识的生成与消费 | neutral-pattern | 采用 | 标识生成者 | 标识贯穿三步 |\n"
            "\n## 2. 模块架构图\n\n略。\n", encoding="utf-8")
        if not contracts.exists():
            contracts.write_text(
                "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n"
                "    methods:\n      - name: emitWithTrace\n"
                "        must:\n          - rule: NEU-01\n"
                "            text: 入口生成标识并透传给后两步\n            verify: ut\n",
                encoding="utf-8")
        proc = node("--input-type=module", "-e",
                    f"const hook = (await import({as_url(self.ext / 'hooks/plan/post_check.mjs')})).default;"
                    f"const out = await hook({{ phase: 'plan', feature: {json.dumps(FEATURE)},"
                    f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                    "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def test_a_hit_carried_by_an_entity_passes(self) -> None:
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        message = self.plan_check()
        self.assertNotIn("没有任何实体扛着", message)
        self.assertNotIn("不在 spec 的命中集内", message)

    def test_a_hit_with_no_entity_is_named(self) -> None:
        """命中却没人扛：知识在设计阶段就丢了。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        (self.feature_root / "contracts.yaml").write_text(
            "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n"
            "    methods:\n      - name: emitWithTrace\n", encoding="utf-8")
        self.assertIn("没有任何实体扛着", self.plan_check())

    def test_an_obligation_outside_the_hit_set_is_named(self) -> None:
        """反过来也不许多出来——两处判定对不上，评审者会看到互相矛盾的结论。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        (self.feature_root / "contracts.yaml").write_text(
            "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n"
            "    methods:\n      - name: emitWithTrace\n"
            "        must:\n          - rule: NEU-01\n"
            "            text: 入口生成标识并透传\n            verify: ut\n"
            "          - rule: NEU-02\n"
            "            text: 重试复用同一个标识\n            verify: ut\n",
            encoding="utf-8")
        self.assertIn("不在 spec 的命中集内", self.plan_check())


class TheObligationReachesTheDownstream(NeutralKnowledgeCase):
    """约束的消费者不止 plan —— `must.verify` 是四阶段分派的单源。

    这一条验的是**分派不按编号前缀写死**：机制从没见过 NEU 这个域，
    但只要契约里挂着它、`verify` 写了 `ut`，ut 阶段就该把它当成本阶段的义务。
    """

    def write_contracts(self, verify: str = "ut") -> None:
        (self.feature_root / "contracts.yaml").write_text(
            "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n"
            "    methods:\n      - name: emitWithTrace\n"
            "        must:\n          - rule: NEU-01\n"
            "            text: 入口生成标识并透传给后两步\n"
            f"            verify: {verify}\n", encoding="utf-8")

    def ut_check(self) -> str:
        (self.feature_root / "ut").mkdir(parents=True, exist_ok=True)
        proc = node("--input-type=module", "-e",
                    f"const hook = (await import({as_url(self.ext / 'hooks/ut/post_check.mjs')})).default;"
                    f"const out = await hook({{ phase: 'ut', feature: {json.dumps(FEATURE)},"
                    f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                    "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def test_the_new_rule_is_dispatched_to_ut(self) -> None:
        """挂了 verify: ut 的中性条目，ut 阶段认它——报错点名的是 NEU-01。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_contracts("ut")
        message = self.ut_check()
        self.assertIn("NEU-01", message,
                      f"ut 阶段没把中性域的义务列进来——分派按编号前缀写死了：{message}")

    def test_a_rule_for_another_phase_is_not_claimed_here(self) -> None:
        """反面：verify 写的是别的阶段，ut 就不该认领它。

        分派是按 `verify` 走的，不是按「契约里有什么就都算我的」——
        后者会让每个阶段都为别人的义务报错。
        """
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_contracts("device")
        self.assertNotIn("NEU-01 缺", self.ut_check())


if __name__ == "__main__":
    unittest.main()
