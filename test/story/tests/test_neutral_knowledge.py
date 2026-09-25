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
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
FEATURE = "NK90001"

# 机制没见过的一条约束域、一份事实、一个模式。前缀 NEU 不在任何脚本里。
NEUTRAL_CONSTRAINT = """---
name: 中性域
kind: constraints
form: entries
applies_when: 需求有新增出口时：出口的标识与字段要求
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
form: facets
applies_when: 设计出口与重试时：本工程已有的出口登记与重试入口
---

# 中性工程画像

## 出口登记

本工程的出口统一登记在中性出口表里。
"""

NEUTRAL_PATTERN = """---
name: neutral-pattern
kind: patterns
form: halves
applies_when: 同一标识要贯穿多个步骤
not_applies_when: 单步完成、无状态贯穿
roles: [标识生成者, 标识消费者]
coordinator_role: 标识生成者
sections:
  - 上篇 · 适用与选型
---

# 中性模式

# 上篇 · 适用与选型

## 适用

多步之间要传同一个标识时适用；单步完成时不适用。

# 下篇 · 结构与落地

## 角色

标识生成者在入口生成标识，标识消费者只读不改。
"""

SPEC_HEAD = """# {feature} spec

## 9. 宿主扩展治理项

| 扩展项 | 是否涉及 | 承载位置 |
|---|---|---|
| 技术契约 | 是 | 9.1 |
| 规约约束要求 | 是 | 9.2 |
| 设计模式候选登记 | 是 | 9.3 |

### 9.1 技术契约

#### 9.1.1 端云接口

| 名称 | 用途 |
|---|---|
| 中性出口接口 | 带标识的出口 |

### 9.2 规约约束要求

<!-- 由 knowledge-use.yaml 生成 -->

### 9.3 设计模式候选登记

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
        link_harness_yaml(self.root)
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
                    f"const u = await import({as_url(self.module('knowledge-use/document.mjs'))});"
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
                "    used:",
                "      - facet: 出口登记",
                "        used_for: 出口登记在哪张表按它取",
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


# 一份与钱包上报协议完全不同的「统计上报」规约：编码是字母加六位、结果只有通过与拒绝、
# 没有取消也没有耗时的节点是合法的；它自己在落法附注里要求单独成节。机制一个字不认识它。
NEUTRAL_REPORTING = """---
name: 中性上报域
kind: constraints
form: entries
domain: NRP
applies_when: 需求涉及对外统计
---

# 中性上报域

| 编号 | 约束 | 强制力 | 命中条件 | 处置 | 验证（执行体） | 探针 |
|---|---|---|---|---|---|---|
| NRP-01 | 每个统计点在结果确定时报一条，编码为一个字母加六位数字 | 红线 | 需求涉及对外统计 | 列出统计点与编码 | 模型：核统计点与编码 | 无 |
| NRP-02 | 结果只取通过或拒绝 | 红线 | 需求涉及对外统计 | 逐统计点给出结果 | 模型：核结果取值 | 无 |

## 落法附注

- 命中 NRP-01 的需求，在业务章单独用一节讲统计方案。
- 有的统计点只有「通过」一种结果、也不计时，这是合法的，不补造拒绝或耗时。
"""


class TheRuleTextIsHandedOverByPath(NeutralKnowledgeCase):
    """规约原文按路径送到作者与审查者手里——**从激活清单派生，不认域名**。

    「要不要单独成节」「结果有哪几种」由规约原文自己说，机制只负责把原文送到；
    换一个编码格式、结果集合都不同的上报规约，通用层一行不改照样送到。
    """

    def setUp(self) -> None:
        super().setUp()
        (self.ext / "knowledge" / "constraints" / "neutral-reporting.md").write_text(
            NEUTRAL_REPORTING, encoding="utf-8")
        manifest = self.ext / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace(
            "    - knowledge/constraints/neutral-domain.md",
            "    - knowledge/constraints/neutral-domain.md\n"
            "    - knowledge/constraints/neutral-reporting.md"), encoding="utf-8")

    def test_the_task_package_lists_every_active_rule_file(self) -> None:
        proc = subprocess.run(
            ["node", str(self.ext / "hooks" / "spec" / "author.mjs"), "--feature", FEATURE],
            cwd=str(self.root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("doc/extensions/knowledge/constraints/neutral-reporting.md", proc.stdout)
        self.assertIn("NRP", proc.stdout)
        self.assertIn("落法附注同样有效", proc.stdout)

    def test_the_reviewer_gets_the_same_paths(self) -> None:
        for phase in ("spec", "plan"):
            with self.subTest(phase=phase):
                proc = node("--input-type=module", "-e",
                            f"const m = (await import({as_url(self.module('pre_verifier.mjs'))})).default;"
                            f"const out = await m({{ phase: '{phase}', feature: {json.dumps(FEATURE)},"
                            f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                            "process.stdout.write((out.promptFragments ?? []).join('\\n\\n'));")
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertIn("doc/extensions/knowledge/constraints/neutral-reporting.md", proc.stdout)
                self.assertIn("落法附注同样是要求", proc.stdout)

    def test_the_entries_derive_as_written(self) -> None:
        """条目按原文派生：结果集合就是「通过或拒绝」，没被补成别的集合。

        只证明派生不改写内容；知识在真实需求里被怎样应用，归 S4 的成品评价。
        """
        got = json.loads(self.eval_js(
            "JSON.stringify(k.activeKnowledge(root).entries.filter(e => e.prefix === 'NRP')"
            ".map(e => [e.id, e.constraint, e.handling]))"))
        self.assertEqual([["NRP-01", "每个统计点在结果确定时报一条，编码为一个字母加六位数字", "列出统计点与编码"],
                          ["NRP-02", "结果只取通过或拒绝", "逐统计点给出结果"]], got)


class TheRuleTextFollowsTheExtensionDir(TheRuleTextIsHandedOverByPath):
    """扩展不在默认目录时，送到作者与审查者手里的仍是**实际存在的**原文路径。

    知识加载按 `paths.extension_dir` 找文件；入口若写死默认目录，规则照常加载，
    拿到路径的人却打不开——原文没送到，还看不出来。
    """

    MOVED = "tools/story-ext"

    def setUp(self) -> None:
        super().setUp()
        moved = self.root / self.MOVED
        moved.parent.mkdir(parents=True)
        shutil.move(str(self.ext), str(moved))
        self.ext = moved
        (self.root / "framework.config.json").write_text(
            json.dumps({"paths": {"extension_dir": self.MOVED}}), encoding="utf-8")

    def listed(self, text: str) -> list[str]:
        return sorted(set(re.findall(r"`([^`\s]+/knowledge/[^`\s]+\.md)`", text)))

    def assert_all_exist(self, text: str) -> None:
        paths = self.listed(text)
        self.assertTrue(paths, "一条原文路径都没列出来")
        self.assertEqual([], [p for p in paths if not (self.root / p).is_file()], "列出了打不开的路径")
        self.assertTrue(all(p.startswith(self.MOVED + "/") for p in paths), paths)

    def test_the_task_package_lists_every_active_rule_file(self) -> None:
        proc = subprocess.run(
            ["node", str(self.ext / "hooks" / "spec" / "author.mjs"), "--feature", FEATURE],
            cwd=str(self.root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assert_all_exist(proc.stdout)

    def test_the_reviewer_gets_the_same_paths(self) -> None:
        for phase in ("spec", "plan"):
            with self.subTest(phase=phase):
                proc = node("--input-type=module", "-e",
                            f"const m = (await import({as_url(self.ext / 'hooks' / 'shared' / 'pre_verifier.mjs')})).default;"
                            f"const out = await m({{ phase: '{phase}', feature: {json.dumps(FEATURE)},"
                            f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                            "process.stdout.write((out.promptFragments ?? []).join('\\n\\n'));")
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assert_all_exist(proc.stdout)

    def test_the_entries_derive_as_written(self) -> None:
        """这一项与目录无关，父类已核。"""


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
        """判全之后，中性域的结论出现在 §9.2 生成区里。"""
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
        """落点名核的是这份 spec 的 §9.1，不是一份预置清单。"""
        self.write_use()
        text = self.use_path.read_text(encoding="utf-8")
        self.use_path.write_text(
            text.replace("contract: 中性出口接口", "contract: 不存在的接口"),
            encoding="utf-8")
        proc = self.render()
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在 §9.1 技术契约里", proc.stderr)


class ThePlanSideReadsTheSameSource(NeutralKnowledgeCase):
    """plan 侧的集合一致读的是同一份真源——中性域的命中条目要在契约里有实体扛着。"""

    def plan_check(self) -> str:
        contracts = self.feature_root / "contracts.yaml"
        (self.feature_root / "plan").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "plan" / "plan.md").write_text(
            "# 计划\n\n## 2. 模块架构图\n\n略。\n\n## 9. 宿主扩展\n\n### 9.1 知识决策（设计输入）\n\n#### 9.1.1 设计模式选型\n\n"
            "| 适用单元 | 候选 | 选型 | 角色 | 理由 |\n|---|---|---|---|---|\n"
            "| 出口标识的生成与消费 | neutral-pattern | 采用 | 标识生成者 | 标识贯穿三步 |\n"
            "\n#### 9.1.2 规约义务\n\n略。\n\n#### 9.1.3 项目知识影响\n\n略。\n", encoding="utf-8")
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


class TheAcceptanceBridgeKeepsEveryEntry(NeutralKnowledgeCase):
    """acceptance 桥接一对多：同一条规约的多个验收条目逐条核，不能只留最后一条。

    旧实现 `Map.set(rule, 单条)` 在同 rule 多条 AC 时静默只留最后一条——
    作者桥接了两条，下游只验一条。解析失败也要接住报出来，不能当空集合放行。
    """

    def write_acceptance(self, text: str) -> None:
        (self.feature_root / "acceptance.yaml").write_text(text, encoding="utf-8")

    def cover(self, ids: list[str]) -> None:
        """UT 侧的覆盖证据：报告文件里出现这些编号就算覆盖到。"""
        report = self.feature_root / "ut" / "reports"
        report.mkdir(parents=True, exist_ok=True)
        (report / "ac-coverage.json").write_text(json.dumps(ids), encoding="utf-8")

    def ut_message(self) -> str:
        (self.feature_root / "contracts.yaml").write_text(
            "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n"
            "    methods:\n      - name: emitWithTrace\n"
            "        must:\n          - rule: NEU-01\n"
            "            text: 入口生成标识并透传给后两步\n            verify: ut\n",
            encoding="utf-8")
        (self.feature_root / "ut").mkdir(parents=True, exist_ok=True)
        proc = node("--input-type=module", "-e",
                    f"const hook = (await import({as_url(self.ext / 'hooks/ut/post_check.mjs')})).default;"
                    f"const out = await hook({{ phase: 'ut', feature: {json.dumps(FEATURE)},"
                    f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                    "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def acceptance_with(self, body: str) -> str:
        return ("criteria:\n"
                "  - id: AC-1\n    knowledge_rule: NEU-01\n"
                "    description: 正常路径拿到标识\n"
                "  - id: AC-2\n    knowledge_rule: NEU-01\n"
                "    description: 重试路径复用同一标识\n") + body

    def test_two_entries_same_rule_must_both_be_covered(self) -> None:
        """同 rule 的 AC-1/AC-2 只覆盖第二条：第一条必须被点名。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(self.acceptance_with(""))
        self.cover(["AC-2"])
        message = self.ut_message()
        self.assertIn("AC-1", message, f"只验最后一条的话 AC-1 就静默溜了：{message}")
        self.assertNotIn("AC-2 在 UT 侧找不到覆盖证据", message)

    def test_both_entries_covered_and_plain_business_ac_not_flagged(self) -> None:
        """两条全覆盖通过；没有 knowledge_rule 的普通业务验收不误报。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(self.acceptance_with(
            "  - id: AC-9\n    description: 与规约无关的普通业务验收点\n"))
        self.cover(["AC-1", "AC-2"])
        message = self.ut_message()
        self.assertNotIn("找不到覆盖证据", message)
        self.assertNotIn("AC-9", message)
        self.assertNotIn("没写 id", message)

    def test_an_entry_without_an_id_is_named(self) -> None:
        """按编号回查覆盖证据的前提是有编号——缺 id 要逐条点名。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(
            "criteria:\n"
            "  - id: AC-1\n    knowledge_rule: NEU-01\n"
            "  - knowledge_rule: NEU-01\n")
        self.cover(["AC-1"])
        self.assertIn("没写 id", self.ut_message())

    def test_a_list_shaped_rule_is_refused_not_flattened(self) -> None:
        """一条 criteria 桥一串编号下游分派不了——报错，不悄悄拍平。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(
            "criteria:\n"
            "  - id: AC-1\n    knowledge_rule: [NEU-01, NEU-02]\n")
        self.assertIn("不是一个编号", self.ut_message())

    def test_a_broken_acceptance_is_surfaced_not_treated_as_empty(self) -> None:
        """解析失败接住报出来——当空集合放行，义务就全部静默失去验收条目。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        # 读取器与 framework 同一解析器：没收尾的流式序列是确定抛错的形态
        self.write_acceptance("criteria:\n - id: x\n  bad: [\n")
        self.assertIn("解析失败", self.ut_message())

    def test_a_section_that_is_not_a_list_is_named(self) -> None:
        """集合写成一句话：读不出结构就核不了，报明是哪个集合，不当空集合放行。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance("criteria: 还没写\n")
        message = self.ut_message()
        self.assertIn("不是列表", message)
        self.assertIn("criteria", message)

    def test_a_bare_value_row_is_named(self) -> None:
        """条目写成裸值：桥不到知识条目，要点名是第几条。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(
            "criteria:\n"
            "  - id: AC-1\n    knowledge_rule: NEU-01\n"
            "  - 只写了一句话\n")
        message = self.ut_message()
        self.assertIn("不是键值对象", message)
        self.assertIn("第 2 条", message)

    def test_an_empty_rule_is_named(self) -> None:
        """`knowledge_rule:` 留空与「没写这个字段」不是一回事：后者是普通业务验收。"""
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(
            "criteria:\n"
            "  - id: AC-1\n    knowledge_rule: NEU-01\n"
            '  - id: AC-2\n    knowledge_rule: ""\n')
        message = self.ut_message()
        self.assertIn("不是一个编号", message)
        self.assertIn("AC-2", message)

    def test_boundaries_count_for_spec_and_ut_alike(self) -> None:
        """spec 核桥接、UT/testing 按桥接分派，读的是同一组集合：criteria + boundaries。

        从前 spec 只认 criteria、UT/testing 认两个集合：同一条桥在 spec 那里算断链，
        到下游却分派得到——同链路两种读法（1.9.3 步骤 7 统一）。
        """
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        self.write_acceptance(
            "boundaries:\n"
            "  - id: BD-1\n    knowledge_rule: NEU-01\n")
        self.cover(["BD-1"])
        message = self.ut_message()
        self.assertNotIn("没有knowledge_rule: NEU-01 的验收条目", message,
                         f"boundaries 的条目该计入 UT 桥：{message}")
        spec_proc = node("--input-type=module", "-e",
                         f"const hook = (await import({as_url(self.ext / 'hooks/spec/post_check.mjs')})).default;"
                         f"const out = await hook({{ phase: 'spec', feature: {json.dumps(FEATURE)},"
                         f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                         "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, spec_proc.returncode, spec_proc.stderr)
        spec_message = json.loads(spec_proc.stdout or "{}").get("message") or ""
        self.assertNotIn("没有对应验收条目", spec_message,
                         f"boundaries 的条目该计入 spec 的桥：{spec_message}")

    def test_numeric_source_tags_are_structural_not_literal(self) -> None:
        """数值来源机械门只核「标没标」；标了的真假归 overlay 语义判据。

        标了「上游约束」的行不再因上游原文没有字面命中被拦——字面命中不等于
        同一个量，未命中也不等于没有真实来源。未标来源类型的数值仍要被点名。
        """
        self.write_use()
        self.assertEqual(0, self.render().returncode)
        # 数值红线是 story 场景的判据：有流程契约的 feature 才核它
        flow_dir = self.feature_root / "AR" / "story-src"
        flow_dir.mkdir(parents=True, exist_ok=True)
        (flow_dir / "story-flow.json").write_text(json.dumps({
            "schema": 4, "feature": FEATURE, "status": "complete",
            "rounds": [{"round": 1, "gates": []}],
        }), encoding="utf-8")
        self.spec_path.write_text(
            self.spec_path.read_text(encoding="utf-8")
            + "\n接口响应不超过 500ms（上游约束）。\n单次重试间隔 3s。\n",
            encoding="utf-8")
        spec_proc = node("--input-type=module", "-e",
                         f"const hook = (await import({as_url(self.ext / 'hooks/spec/post_check.mjs')})).default;"
                         f"const out = await hook({{ phase: 'spec', feature: {json.dumps(FEATURE)},"
                         f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                         "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, spec_proc.returncode, spec_proc.stderr)
        spec_message = json.loads(spec_proc.stdout or "{}").get("message") or ""
        self.assertIn("未标来源类型", spec_message, spec_message)
        self.assertIn("3s", spec_message)
        self.assertNotIn("500ms", spec_message,
                         f"标了来源的数值不该被字面匹配拦：{spec_message}")


if __name__ == "__main__":
    unittest.main()
