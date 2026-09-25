"""知识与机制的协议：知识声明强制力、执行体与探针职责，各道门按同一份协议、同一个粒度执行。

全部用中性知识（机制从没见过的域前缀与模式），机制零改动：
  载入——协议版本与值域不合就点名，一次列全；
  看到——骨架每条带条目内容行，§10 带强制力与验法；
  识别——本轮豁免按强制力允许，未确认的事实面要写核实位置；
  应用——每处落点的 verify 符合规约声明的执行体，契约流式与块式同一读法、resource_keys 按 framework 两层合同；
  传递——review 一处落点一行、结论按列取准确值、未落实按强制力处置；
        coding 探针按「阻断」声明与强制力处置，注释不当代码证据，注释里的在册编号报到行号。
改知识（执行体、强制力、阻断前缀）会改同一份产物的门禁结论——这是「知识驱动机制」的验收。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_neutral_knowledge as nk  # noqa: E402

CONSTRAINT = """---
name: 中性域
kind: constraints
applies_when: 需求有新增出口时：出口的标识与字段要求
domain: NEU
---

# 中性域

| 编号 | 约束 | 强制力 | 命中条件 | 处置 | 验证（执行体） | 探针 |
|---|---|---|---|---|---|---|
| NEU-01 | 出口要带一个可回查的标识 | 基线 | 有新增出口 | 出口处生成标识 | 模型：核对生成点 | 无 |
| NEU-02 | 重复触发时复用同一个标识 | 红线 | 有重试路径 | 重试复用 | 模型：核对重试分支。实机：重复触发走查 | present_in_method:cachedTrace |
| NEU-03 | 出口字段不写方向词 | 红线 | 有新增出口 | 字段名用中性词 | 模型：检索方向词 | 阻断：absent_regex:\\bleftSide\\b |
| NEU-04 | 出口处记一条耗时 | 建议 | 有新增出口 | 记耗时 | 模型：核对耗时点 | 无 |
"""

FACT = """---
name: neutral-facts
kind: facts
applies_when: 设计出口与重试时：本工程已有的出口登记与重试入口
---

# 中性工程画像

## 出口登记

本工程的出口统一登记在中性出口表里。

## 重试入口

重试入口可能在中性调度器里。
"""

#: 一份判全的判断：三条命中并落实，一条不命中。键里的 `-` 换成 `_` 就是覆写参数名。
JUDGED = {
    "NEU-01": "applicable: true\n    requirement: 出口生成一次标识\n    contract: 中性出口接口",
    "NEU-02": "applicable: true\n    requirement: 重试复用标识\n    contract: 中性出口接口",
    "NEU-03": "applicable: true\n    requirement: 出口字段不用方向词\n    contract: 中性出口接口",
    "NEU-04": "applicable: false\n    reason: 本需求的出口不计耗时",
}


def judgement(**over: str) -> str:
    return "\n".join(f"  - id: {k}\n    {over.get(k.replace('-', '_'), v)}" for k, v in JUDGED.items())


def waived(reason: str, compensation: str = "") -> str:
    tail = f"\n      compensation: {compensation}" if compensation else ""
    return f"applicable: true\n    waived:\n      reason: {reason}{tail}"


def landing(rule: str, text: str, verify: str) -> str:
    return (f"          - rule: {rule}\n            text: {text}\n            verify: {verify}\n")


def contracts(v01: str = "review", v02: str = "ut", *, second02: str = "", head: str = "") -> str:
    """两个方法：emitWithTrace 扛 NEU-01 / NEU-03，reuseTrace 扛 NEU-02；`second02` 给 NEU-02 再加一处落点。"""
    return (head + "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n    methods:\n"
            "      - name: emitWithTrace\n        must:\n"
            + landing("NEU-01", "入口生成标识并透传", v01)
            + landing("NEU-03", "出口字段名不用方向词", "review")
            + (landing("NEU-02", "重试时复用入口生成的标识", second02) if second02 else "")
            + "      - name: reuseTrace\n        must:\n"
            + landing("NEU-02", "重试时复用入口生成的标识", v02))


class ProtocolCase(nk.NeutralKnowledgeCase):
    """中性工作区之上换一份带四种强制力 / 执行体 / 探针组合的中性域，事实带一个未确认的面。"""

    def setUp(self) -> None:
        super().setUp()
        self.put("constraints/neutral-domain.md", CONSTRAINT)
        self.put("facts/neutral-facts.md", FACT)

    def put(self, rel: str, text: str) -> None:
        (self.ext / "knowledge" / rel).write_text(text, encoding="utf-8")

    def edit(self, path: Path, old: str, new: str) -> None:
        body = path.read_text(encoding="utf-8")
        self.assertIn(old, body, f"{path.name} 里没有要改的「{old}」")
        path.write_text(body.replace(old, new), encoding="utf-8")

    def edit_knowledge(self, rel: str, old: str, new: str) -> None:
        self.edit(self.ext / "knowledge" / rel, old, new)

    def load_error(self) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const k = await import({nk.as_url(self.module('knowledge.mjs'))});"
                       f"try {{ k.activeKnowledge({json.dumps(self.root.as_posix())}); }}"
                       " catch (e) { process.stdout.write(e.message); }")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def hook(self, phase: str) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const hook = (await import({nk.as_url(self.ext / 'hooks' / phase / 'post_check.mjs')})).default;"
                       f"const out = await hook({{ phase: '{phase}', feature: {json.dumps(nk.FEATURE)},"
                       f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                       "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def judged(self, **over: str) -> None:
        self.write_use(neutral=judgement(**over))
        self.assertEqual(0, self.render().returncode, self.render().stderr)

    def write_contracts(self, text: str) -> None:
        (self.feature_root / "contracts.yaml").write_text(text, encoding="utf-8")


class KnowledgeDescribesItself(ProtocolCase):
    """知识靠自己的 applies_when 描述自己：解析结果带上它，任务包与审查按它列出；缺了与别的错误一起报。"""

    def loaded(self) -> dict:
        proc = nk.node("--input-type=module", "-e",
                       f"const k = await import({nk.as_url(self.module('knowledge.mjs'))});"
                       f"const r = k.activeKnowledge({json.dumps(self.root.as_posix())});"
                       f"process.stdout.write(JSON.stringify({{ facts: r.facts, guide: k.knowledgeGuide({json.dumps(self.root.as_posix())}, r) }}));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_each_file_carries_its_own_description(self) -> None:
        got = self.loaded()
        fact = next(f for f in got["facts"] if f["name"] == "neutral-facts")
        self.assertEqual("设计出口与重试时：本工程已有的出口登记与重试入口", fact["appliesWhen"])
        self.assertIn("- `doc/extensions/knowledge/facts/neutral-facts.md` —— 设计出口与重试时：本工程已有的出口登记与重试入口",
                      got["guide"])
        self.assertTrue(any("protocol.md" in line for line in got["guide"]))

    def describe(self, value: str) -> None:
        self.edit_knowledge("facts/neutral-facts.md",
                            "applies_when: 设计出口与重试时：本工程已有的出口登记与重试入口\n", value)

    def test_every_legal_yaml_form_reaches_the_reader(self) -> None:
        """引号、折叠与保留换行都是合法 YAML：读者拿到的是它们的真实文字，不是 `>` 或两个引号。"""
        cases = {
            "引号": ('applies_when: "设计出口时: 出口登记在哪"\n', "设计出口时: 出口登记在哪"),
            "折叠": ("applies_when: >\n  设计出口时：\n  出口登记在哪\n", "设计出口时： 出口登记在哪"),
            "保留换行": ("applies_when: |\n  设计出口时：\n  出口登记在哪\n", "设计出口时：\n出口登记在哪"),
        }
        before = self.ext.joinpath("knowledge/facts/neutral-facts.md").read_text(encoding="utf-8")
        for form, (value, want) in cases.items():
            with self.subTest(form=form):
                self.ext.joinpath("knowledge/facts/neutral-facts.md").write_text(before, encoding="utf-8")
                self.describe(value)
                got = self.loaded()
                fact = next(f for f in got["facts"] if f["name"] == "neutral-facts")
                self.assertEqual(want, fact["appliesWhen"])
                self.assertIn("—— " + want.replace("\n", "\n  "), "\n".join(got["guide"]))

    def test_an_empty_or_non_text_description_is_named(self) -> None:
        before = self.ext.joinpath("knowledge/facts/neutral-facts.md").read_text(encoding="utf-8")
        for value, needle in (('applies_when: ""\n', "applies_when 是空的"),
                              ("applies_when: '   '\n", "applies_when 是空的"),
                              ("applies_when:\n", "缺 applies_when"),
                              ("applies_when: [a, b]\n", "applies_when 不是文字"),
                              ("applies_when: 1\n", "applies_when 不是文字")):
            with self.subTest(value=value):
                self.ext.joinpath("knowledge/facts/neutral-facts.md").write_text(before, encoding="utf-8")
                self.describe(value)
                self.assertIn(f"knowledge/facts/neutral-facts.md 的 {'frontmatter ' if needle.startswith('缺') else ''}{needle}",
                              self.load_error())

    def test_every_file_problem_is_reported_in_one_load(self) -> None:
        """缺文件、缺 kind、缺 applies_when、kind 不在三类里、frontmatter 读不出，与合法文件混在一起：一次报全。"""
        facts = self.ext / "knowledge" / "facts"
        (facts / "no-kind.md").write_text("---\nname: x\n---\n\n# x\n", encoding="utf-8")
        (facts / "no-use.md").write_text("---\nname: y\nkind: facts\n---\n\n# y\n", encoding="utf-8")
        (facts / "odd-kind.md").write_text("---\nname: z\nkind: index\napplies_when: 说明\n---\n\n# z\n", encoding="utf-8")
        (facts / "bad-yaml.md").write_text("---\nname: w\nkind: facts\napplies_when: 何时: 回答: 什么\n---\n\n# w\n",
                                           encoding="utf-8")
        manifest = self.ext / "manifest.yaml"
        self.edit(manifest, "  knowledge:\n",
                  "  knowledge:\n    - knowledge/facts/missing.md\n    - knowledge/facts/no-kind.md\n"
                  "    - knowledge/facts/no-use.md\n    - knowledge/facts/odd-kind.md\n"
                  "    - knowledge/facts/bad-yaml.md\n")
        message = self.load_error()
        for needle in ("读不到 —— knowledge/facts/missing.md", "knowledge/facts/no-kind.md 的 frontmatter 缺 kind",
                       "knowledge/facts/no-use.md 的 frontmatter 缺 applies_when",
                       'knowledge/facts/odd-kind.md 的 kind="index" 不在封闭集合里',
                       "knowledge/facts/bad-yaml.md 的 frontmatter 不是合法 YAML"):
            with self.subTest(needle=needle):
                self.assertIn(needle, message)

    def test_renaming_or_splitting_knowledge_touches_only_knowledge_and_manifest(self) -> None:
        """维护知识只动知识文件与清单：改名并拆成两份之后照常加载，机制一行不改。"""
        facts = self.ext / "knowledge" / "facts"
        body = (facts / "neutral-facts.md").read_text(encoding="utf-8")
        (facts / "neutral-facts.md").unlink()
        (facts / "exit-registry.md").write_text(body.replace("name: neutral-facts", "name: exit-registry"),
                                               encoding="utf-8")
        (facts / "retry-entry.md").write_text("---\nname: retry-entry\nkind: facts\napplies_when: 设计重试时：重试从哪进\n"
                                              "---\n\n# 重试\n\n## 重试入口\n\n中性调度器。\n", encoding="utf-8")
        manifest = self.ext / "manifest.yaml"
        self.edit(manifest, "knowledge/facts/neutral-facts.md",
                  "knowledge/facts/exit-registry.md\n    - knowledge/facts/retry-entry.md")
        self.assertEqual("", self.load_error())
        names = sorted(f["name"] for f in self.loaded()["facts"])
        self.assertIn("exit-registry", names)
        self.assertIn("retry-entry", names)


class TheProtocolIsCheckedOnLoad(ProtocolCase):
    """载入即核：版本不一致、值域不合，各自点名，一次列全。"""

    def test_the_shipped_knowledge_loads_clean(self) -> None:
        self.assertEqual("", self.load_error())

    def test_every_breach_is_named_at_once(self) -> None:
        self.edit_knowledge("constraints/neutral-domain.md", "| 基线 | 有新增出口 |", "| 必须 | 有新增出口 |")
        self.edit_knowledge("constraints/neutral-domain.md", "| 模型：核对生成点 | 无 |", "| 模型：核对生成点 | grep:出口 |")
        self.edit_knowledge("constraints/neutral-domain.md", "| 记耗时 | 模型：核对耗时点 |", "| （评审动作）记耗时 | 测试：核对耗时点 |")
        self.edit_knowledge("design-patterns/neutral-pattern.md", "# 下篇 · 结构与落地", "## 结构与落地")
        message = self.load_error()
        for needle in ("强制力「必须」", "探针形态未知", "不认识的执行体「测试」", "验证列要有「人工」",
                       "「# 下篇 · …」"):
            self.assertIn(needle, message)


class TheJudgementSeesTheEntry(ProtocolCase):
    """看到：判命中时要的内容送到骨架那一行；§10 带着 plan 定证据来源要的两列。"""

    def test_the_skeleton_carries_each_entry_and_facet(self) -> None:
        proc = nk.node(str(self.module("knowledge-use.mjs")), "init",
                       "--feature", nk.FEATURE, "--project-root", str(self.root))
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.use_path.read_text(encoding="utf-8")
        # 条目原义分行送达：约束原文与强制力、命中条件、命中后要给出、验法——处置与命中条件不挤在一行
        block = text.split("  - id: NEU-02", 1)[1].split("  - id: ", 1)[0]
        for line in ("# 红线 · 重复触发时复用同一个标识", "# 命中条件：有重试路径", "# 命中后要给出：", "# 验法：模型 / 实机"):
            self.assertIn(line, block)
        self.assertNotIn("命中：", text, "命中条件又挤回同一行")
        self.assertIn("# 面：出口登记 / 重试入口\n", text)

    def init_skeleton(self) -> str:
        proc = nk.node(str(self.module("knowledge-use.mjs")), "init",
                       "--feature", nk.FEATURE, "--project-root", str(self.root))
        self.assertEqual(0, proc.returncode, proc.stderr)
        return self.use_path.read_text(encoding="utf-8")

    def test_each_fact_says_when_to_read_it(self) -> None:
        """骨架每份项目事实带自己的「何时读」，作者据它判用不用；多行自述续行仍是注释，骨架照常读回。"""
        text = self.init_skeleton()
        self.assertIn("    # 何时读：设计出口与重试时：本工程已有的出口登记与重试入口\n    # 面：", text)
        self.edit_knowledge("facts/neutral-facts.md",
                            "applies_when: 设计出口与重试时：本工程已有的出口登记与重试入口\n",
                            "applies_when: |\n  设计出口时：\n  出口登记在哪\n")
        self.use_path.unlink()
        text = self.init_skeleton()
        self.assertIn("    # 何时读：设计出口时：\n    #   出口登记在哪\n    # 面：", text)
        proc = nk.node("--input-type=module", "-e",
                       f"const d = await import({nk.as_url(self.module('knowledge-use/document.mjs'))});"
                       f"const u = d.readUse({json.dumps(self.root.as_posix())}, {json.dumps(nk.FEATURE)});"
                       "process.stdout.write(JSON.stringify(u.facts.map(f => f.id)));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("neutral-facts", json.loads(proc.stdout))

    def test_the_projection_carries_force_and_method(self) -> None:
        self.judged()
        zone = self.spec_path.read_text(encoding="utf-8").split("knowledge-use:begin 规约约束要求")[1]
        self.assertIn("| NEU-02 | 红线 | 重试复用标识 | §9 · 中性出口接口 | 模型 / 实机 |", zone)


class AWaiverFollowsTheForce(ProtocolCase):
    """识别：命中但本轮豁免，红线不许、基线要补偿、建议可空；未确认的事实面要写核实位置。"""

    def render_output(self) -> tuple[int, str]:
        proc = self.render()
        return proc.returncode, proc.stderr + proc.stdout

    def test_a_red_line_cannot_be_waived(self) -> None:
        self.write_use(neutral=judgement(NEU_02=waived("这一轮只有单次出口", "下一轮补重试")))
        code, out = self.render_output()
        self.assertEqual(1, code, out)
        self.assertIn("NEU-02 是红线", out)

    def test_a_baseline_waiver_needs_a_compensation(self) -> None:
        self.write_use(neutral=judgement(NEU_01=waived("这一轮出口沿用旧标识")))
        code, out = self.render_output()
        self.assertEqual(1, code, out)
        self.assertIn("要写 compensation", out)

    def test_a_suggestion_waiver_may_skip_the_compensation(self) -> None:
        self.write_use(neutral=judgement(NEU_04=waived("这一轮不计耗时")))
        code, out = self.render_output()
        self.assertEqual(0, code, out)
        zone = self.spec_path.read_text(encoding="utf-8").split("knowledge-use:begin 规约约束要求")[1]
        self.assertIn("命中但本轮豁免（评审判）", zone)
        self.assertNotIn("| NEU-04 |", zone, "豁免的命中不进落实表")

    def test_an_empty_facet_says_it_is_empty(self) -> None:
        self.write_use(neutral=judgement())
        self.edit(self.use_path, "facet: 出口登记", 'facet: ""')
        code, out = self.render_output()
        self.assertEqual(1, code, out)
        self.assertIn("facet 空着", out)

    def test_a_file_level_use_is_refused(self) -> None:
        self.write_use(neutral=judgement())
        self.edit(self.use_path, "    used:\n      - facet: 出口登记\n        used_for:", "    used_for:")
        code, out = self.render_output()
        self.assertEqual(1, code, out)
        self.assertIn("没写 used", out)


class EachLandingCarriesTheEvidenceItsRuleAsks(ProtocolCase):
    """应用：一条 must 一处落点，它的 verify 由规约声明的执行体定。"""

    def plan(self, text: str) -> str:
        self.judged()
        (self.feature_root / "plan").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "plan" / "plan.md").write_text(
            "# 计划\n\n## 知识决策（设计输入）\n\n### 设计模式选型\n\n"
            "| 适用单元 | 候选 | 选型 | 角色 | 理由 |\n|---|---|---|---|---|\n"
            "| 出口标识的生成与消费 | neutral-pattern | 采用 | 标识生成者 | 标识贯穿三步 |\n"
            "\n## 2. 模块架构图\n\n略。\n", encoding="utf-8")
        self.write_contracts(text)
        return self.hook("plan")

    def test_a_device_rule_landing_marked_review_is_named(self) -> None:
        message = self.plan(contracts(v02="review"))
        self.assertIn("reuseTrace 的 NEU-02 标了 verify: review，而该规约声明要「实机」证据", message)

    def test_every_landing_with_device_evidence_passes(self) -> None:
        message = self.plan(contracts(v02="ut", second02="both"))
        self.assertNotIn("证据", message)
        self.assertNotIn("NEU-01", message, "只声明「模型」的规约标 review 就够了")

    def test_probe_is_no_longer_a_verify_value(self) -> None:
        self.assertIn("verify「probe」不是", self.plan(contracts(v01="probe")))

    def test_a_method_probe_without_a_method_landing_is_reported(self) -> None:
        text = ("data_models:\n  - name: 出口上下文\n    fields:\n      - name: traceId\n        must:\n"
                "          - rule: NEU-02\n            text: 重试复用标识\n            verify: ut\n"
                "interfaces:\n  - name: 中性出口接口\n    file: src/exit.ets\n    methods:\n"
                "      - name: emitWithTrace\n        must:\n"
                + landing("NEU-01", "入口生成标识并透传", "review") + landing("NEU-03", "出口字段名不用方向词", "review"))
        self.assertIn("探针无落点", self.plan(text))

    def test_changing_the_declared_executor_changes_the_verdict(self) -> None:
        self.assertIn("要「实机」证据", self.plan(contracts(v02="review")))
        self.edit_knowledge("constraints/neutral-domain.md", "模型：核对重试分支。实机：重复触发走查", "模型：核对重试分支")
        self.assertNotIn("要「实机」证据", self.plan(contracts(v02="review")))

    def test_flow_style_and_block_style_read_the_same(self) -> None:
        """契约与 framework 同一读法：流式 `- { … }` 是合法 YAML，不再被扩展点名。

        同一条 must 用两种写法挂在同一字段上，门禁给出同样的结论——读取器不再给作者加限制。
        """
        flow = ("data_models:\n  - name: 出口记录\n    fields:\n"
                "      - { name: traceId, type: string,\n"
                "          must: [ { rule: NEU-02, text: 重试复用标识, verify: ut } ] }\n")
        block = ("data_models:\n  - name: 出口记录\n    fields:\n      - name: traceId\n        type: string\n"
                 "        must:\n          - rule: NEU-02\n            text: 重试复用标识\n            verify: ut\n")
        self.assertNotIn("流式", self.plan(contracts(head=flow)))
        self.assertEqual(self.plan(contracts(head=flow)), self.plan(contracts(head=block)))

    def test_resource_keys_are_read_as_the_framework_contract(self) -> None:
        """`resource_keys` 是 framework 合同里的两层对象：模块 → 分类 → 资源条目。

        义务挂在资源条目上，引用写完整的 `resource_keys.<模块>.<分类>.<key>`，key 带点也按整串认；
        挂在分类层的 must 被点名。
        """
        rk = ("resource_keys:\n  中性模块:\n    string:\n"
              "      - key: exit.trace.label\n        value: 出口标识\n"
              "        must:\n          - rule: NEU-03\n            text: 出口文案不用方向词\n            verify: review\n"
              "    media:\n      - key: exit_icon\n        value: 图\n")
        message = self.plan(contracts(head=rk))
        self.assertNotIn("resource_keys", message, message)
        layered = ("resource_keys:\n  中性模块:\n    string:\n"
                   "      must:\n        - rule: NEU-03\n          text: 出口文案不用方向词\n          verify: review\n")
        self.assertIn("resource_keys.中性模块.string 分类层挂了 must", self.plan(contracts(head=layered)))
        flat = "resource_keys:\n  - key: exit.trace.label\n    value: 出口标识\n"
        self.assertIn("resource_keys 不是「模块 → 分类 → 资源列表」的两层对象", self.plan(contracts(head=flat)))



class TheReviewTableIsOneRowPerLanding(ProtocolCase):
    """传递（review）：按 rule + 落点定位，结论从结论列取准确值，未落实按强制力处置。"""

    EMIT = "interfaces.中性出口接口.emitWithTrace"
    REUSE = "interfaces.中性出口接口.reuseTrace"

    def review(self, *rows: tuple[str, str, str, str]) -> str:
        self.judged()
        self.write_contracts(contracts(second02="ut"))
        (self.feature_root / "review").mkdir(parents=True, exist_ok=True)
        table = "\n".join(f"| {r} | {at} | src/exit.ets | {verdict} | {basis} |" for r, at, verdict, basis in rows)
        (self.feature_root / "review" / "review-report.md").write_text(
            "# 审查报告\n\n## 知识义务复核\n\n| rule | 落点（契约实体） | 落实位置（文件:符号） | 结论 | 依据 |\n"
            f"|---|---|---|---|---|\n{table}\n", encoding="utf-8")
        return self.hook("review")

    def full(self, **over: tuple[str, str]) -> list[tuple[str, str, str, str]]:
        rows = {("NEU-01", self.EMIT): ("落实", "入口处生成"), ("NEU-03", self.EMIT): ("落实", "字段名无方向词"),
                ("NEU-02", self.EMIT): ("落实", "重试复用"), ("NEU-02", self.REUSE): ("落实", "重试复用")}
        rows.update({k: v for k, v in over.items()})
        return [(r, at, *v) for (r, at), v in rows.items()]

    def test_every_landing_with_a_verdict_passes(self) -> None:
        self.assertEqual("", self.review(*self.full()))

    def test_one_landing_does_not_cover_the_other(self) -> None:
        rows = [row for row in self.full() if not (row[0] == "NEU-02" and row[1] == self.EMIT)]
        self.assertIn(f"义务 NEU-02（{self.EMIT}） 在复核表里没有对应行", self.review(*rows))

    def test_not_landed_is_not_read_as_landed(self) -> None:
        rows = [(r, at, "未落实", b) if (r, at) == ("NEU-02", self.REUSE) else (r, at, v, b)
                for r, at, v, b in self.full()]
        self.assertIn(f"义务 NEU-02（{self.REUSE}） 判「未落实」，这条规约是红线", self.review(*rows))

    def test_a_baseline_not_landed_needs_a_basis_and_the_force_decides(self) -> None:
        bare = [(r, at, "未落实", "—") if r == "NEU-01" else (r, at, v, b) for r, at, v, b in self.full()]
        self.assertIn("NEU-01", self.review(*bare))
        argued = [(r, at, "未落实", "本轮沿用旧标识，下一轮补齐") if r == "NEU-01" else (r, at, v, b)
                  for r, at, v, b in self.full()]
        self.assertEqual("", self.review(*argued))
        self.edit_knowledge("constraints/neutral-domain.md", "| 基线 | 有新增出口 |", "| 红线 | 有新增出口 |")
        self.assertIn("这条规约是红线", self.review(*argued))


class TheCodeIsTheEvidence(ProtocolCase):
    """传递（coding）：探针按「阻断」声明与强制力处置；注释不是证据，注释里的在册编号报到行号。"""

    GOOD = ("export class 中性出口接口 {\n"
            "  emitWithTrace(): string {\n"
            "    const trace = this.newTrace();\n"
            "    return trace;\n"
            "  }\n"
            "  reuseTrace(prev: string): string {\n"
            "    const current = prev;\n"
            "    return current;\n"
            "  }\n"
            "}\n")

    def coding(self, source: str) -> str:
        self.judged()
        self.write_contracts(contracts())
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src" / "exit.ets").write_text(source, encoding="utf-8")
        return self.hook("coding")

    def test_a_clue_probe_that_misses_does_not_fail(self) -> None:
        """NEU-02 的方法体探针只是线索：换一种写法认不出，不等于没做。"""
        self.assertEqual("", self.coding(self.GOOD))

    def test_a_blocking_probe_follows_the_force(self) -> None:
        bad = self.GOOD.replace("const trace = this.newTrace();", "const trace = this.newTrace({ leftSide: 1 });")
        self.assertIn("而这条规约是红线", self.coding(bad))
        self.edit_knowledge("constraints/neutral-domain.md", "| 红线 | 有新增出口 | 字段名用中性词",
                            "| 基线 | 有新增出口 | 字段名用中性词")
        self.assertEqual("", self.coding(bad), "基线只记未落实，交 review 写依据")
        self.edit_knowledge("constraints/neutral-domain.md", "| 基线 | 有新增出口 | 字段名用中性词",
                            "| 红线 | 有新增出口 | 字段名用中性词")
        self.edit_knowledge("constraints/neutral-domain.md", "阻断：absent_regex", "absent_regex")
        self.assertEqual("", self.coding(bad), "不带阻断的同一个表达式只是证据缺口")

    def test_a_file_probe_is_reported_once_per_rule(self) -> None:
        """同一规约挂两处、探针不按实体收窄：扫的是同一批文件，同样的行号只报一次。"""
        bad = self.GOOD.replace("const trace = this.newTrace();", "const trace = this.newTrace({ leftSide: 1 });")
        self.judged()
        self.write_contracts(contracts().replace(
            "      - name: reuseTrace\n        must:\n",
            "      - name: reuseTrace\n        must:\n" + landing("NEU-03", "出口字段名不用方向词", "review")))
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src" / "exit.ets").write_text(bad, encoding="utf-8")
        self.assertEqual(1, self.hook("coding").count("而这条规约是红线"))

    def test_an_entity_only_in_a_comment_is_not_found(self) -> None:
        source = self.GOOD.replace("reuseTrace(prev: string)", "// reuseTrace 在这里\n  retry(prev: string)")
        self.assertIn("代码里找不到「reuseTrace」", self.coding(source))

    def test_a_rule_id_in_a_comment_is_named_but_not_in_a_string(self) -> None:
        source = self.GOOD.replace("    const trace = this.newTrace();",
                                   "    // 按 NEU-01 生成\n    const trace = this.newTrace('NEU-01');")
        message = self.coding(source)
        self.assertIn("src/exit.ets:3 注释里写了规约编号 NEU-01", message)
        self.assertNotIn("src/exit.ets:4", message, "字符串里的同名字面不是注释")


class TheAuthorPagesSayWhereThingsGo(unittest.TestCase):
    """作者页：coding 不再要「说法」、模式指针指下篇；plan 有执行体对照、借挂的落点与中性反例。"""

    def read(self, phase: str) -> str:
        return (nk.EXT / "hooks" / phase / "author.md").read_text(encoding="utf-8")

    def test_the_coding_page(self) -> None:
        page = self.read("coding")
        self.assertNotIn("每条义务在本阶段都要有个说法", page)
        self.assertNotIn("sections.implement", page)
        self.assertIn("下篇", page)

    def test_the_plan_page(self) -> None:
        page = self.read("plan")
        for needle in ("不是某条规约要求的业务规则写在这里", "借挂", "含「实机」", "`review` 即可"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
