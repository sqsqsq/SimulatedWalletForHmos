"""`knowledge-use.yaml` 是 spec 阶段知识判断的唯一真源，§10/§11 是它的投影。

判两件事：

  ① **完备性与在册性由机器判**——激活清单里的每条约束都要有去处（逐条登记或整域不适用），
     编号与候选只能是在册的那些。漏一条是「没判过」，与「判了不命中」是两件事；
  ② **投影不能反向成为真源**——生成区与 YAML 对不上就报，手改生成区在这里被判出来。

不判内容质量：要求是不是本需求的设计、信号指不指向真实业务特征，都是语义判断，归 verifier。
本文件里没有任何一条断言去数字数、比相似度。
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
MODULE = EXT / "hooks" / "shared" / "knowledge-use.mjs"
FEATURE = "KU90001"

# 激活清单里真实存在的那几条——夹具不另造知识，判据要在真数据上成立
HIT = "SEC-01"
OTHER = "UX-01"
REVIEW_ACTION = "DLV-02"
PATTERN = "page-interaction"
ALL_DOMAINS = ("UX", "SEC", "DFX", "OBS", "RES", "COMPAT", "ENV", "DLV")

SPEC_HEAD = """# {feature} spec

## 9. 技术契约

### 9.2 数据存储

| 名称 | 用途 |
|---|---|
| wallet_receipt_temp | 凭证渲染产物的临时落点 |

## 10. 规约约束要求

<!-- 判定产生的代码要求，按命中条目派生。 -->

## 11. 设计模式候选登记

<!-- 只登记候选，不做选型。 -->
"""


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60, cwd=cwd)


def as_url(path: Path) -> str:
    """Windows 上动态 import 只认 file:// URL，绝对盘符路径会被当成协议名。"""
    return json.dumps(path.resolve().as_uri())


class KnowledgeUseCase(unittest.TestCase):
    """每个用例一份新工作区：扩展是真的那一份（软链太脆，直接复制）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "spec").mkdir(parents=True)
        self.spec_path = self.feature_root / "spec" / "spec.md"
        self.spec_path.write_text(SPEC_HEAD.format(feature=FEATURE), encoding="utf-8")
        self.use_path = self.feature_root / "spec" / "knowledge-use.yaml"

    # ---- 驱动 ----

    def digest(self) -> str:
        proc = node("-e", f"""
            import({as_url(self.root / 'doc/extensions/hooks/shared/knowledge-use/document.mjs')})
              .then(m => process.stdout.write(m.manifestDigest({json.dumps(self.root.as_posix())})));
        """)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def write_use(self, *, domains: list[str] | None = None,
                  constraints: str | None = None,
                  patterns: str | None = None,
                  digest: str | None = None) -> None:
        """默认写一份完备的判断：一条命中，其余整域不适用。"""
        rows = ["schema: 1", f'manifest_digest: "{digest or self.digest()}"']
        rows.append("facts:")
        rows.append("  - id: component-profile")
        rows.append("    used:")
        rows.append("      - facet: 部件申明")
        rows.append("        used_for: 本部件的组件边界按它取")
        na = domains if domains is not None else [d for d in ALL_DOMAINS if d != "SEC"]
        if na:
            rows.append("constraint_domains:")
            for prefix in na:
                rows.append(f"  - prefix: {prefix}")
                rows.append("    applicable: false")
                rows.append(f"    reason: 本需求不涉及 {prefix} 域管的那类改动，无新增落点")
        rows.append("constraints:")
        rows.append(constraints if constraints is not None else (
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 凭证临时文件写 wallet_receipt_temp，分享完成或离开页面即删\n"
            "    contract: wallet_receipt_temp"))
        rows.append("patterns:")
        rows.append(patterns if patterns is not None else (
            "  - unit: 交易详情页凭证生成\n"
            f"    candidate: {PATTERN}\n"
            "    signal: 成功、失败、取消三个分支各有独立状态与恢复动作"))
        self.use_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def render(self) -> subprocess.CompletedProcess:
        return node(str(self.root / "doc/extensions/hooks/shared/knowledge-use.mjs"),
                    "render", "--feature", FEATURE, "--project-root", str(self.root))

    def render_ok(self) -> str:
        proc = self.render()
        self.assertEqual(0, proc.returncode, proc.stderr + proc.stdout)
        return self.spec_path.read_text(encoding="utf-8")

    def assert_render_names(self, needle: str) -> str:
        proc = self.render()
        self.assertEqual(1, proc.returncode, f"该拦却过了：{proc.stdout}")
        out = proc.stderr + proc.stdout
        self.assertIn(needle, out)
        return out


class TestTheJudgementMustCoverEveryActiveEntry(KnowledgeUseCase):
    """激活的每一条都要有去处——漏掉是「没判过」，不是「不命中」。"""

    def test_a_complete_judgement_renders(self) -> None:
        self.write_use()
        text = self.render_ok()
        self.assertIn(HIT, text)
        self.assertIn("wallet_receipt_temp", text)

    def test_an_entry_with_no_home_is_named(self) -> None:
        """一个域既没判整域不适用、域里的条目也没逐条登记。"""
        self.write_use(domains=[d for d in ALL_DOMAINS if d not in ("SEC", "UX")])
        out = self.assert_render_names("没有去处")
        self.assertIn(OTHER, out)

    def test_an_unknown_id_is_named(self) -> None:
        self.write_use(constraints="  - id: ZZZ-99\n    applicable: false\n"
                                   "    reason: 本需求不新增任何对外接口，这一条够不着")
        self.assert_render_names("不在激活清单里")

    def test_a_domain_cannot_be_both_dismissed_and_itemised(self) -> None:
        """整域不适用又逐条登记：两种判法留一种，否则读者不知道该信哪个。"""
        self.write_use(domains=list(ALL_DOMAINS))
        self.assert_render_names("已判整域不适用，却又逐条登记")

    def test_a_reason_that_is_only_the_two_words_is_named(self) -> None:
        """判的是**确定性形态**：空，或者恰好就是「不涉及」那三个字。

        不设字数下限——多少字算够是配额不是不变量，依据站不站得住归 verifier。
        """
        self.write_use(domains=[d for d in ALL_DOMAINS if d != "SEC"],
                       constraints=f"  - id: {HIT}\n    applicable: false\n    reason: 不涉及")
        self.assert_render_names("没写依据")

    def test_a_short_but_concrete_reason_passes(self) -> None:
        """八个字的具体依据照过——它比一句十二字的套话更能回查。"""
        self.write_use(domains=[d for d in ALL_DOMAINS if d != "SEC"],
                       constraints=f"  - id: {HIT}\n    applicable: false\n    reason: 无任何出口")
        self.render_ok()

    def test_a_hit_without_a_requirement_is_named(self) -> None:
        self.write_use(constraints=f"  - id: {HIT}\n    applicable: true")
        self.assert_render_names("命中而不说要求做什么")

    def with_review_action(self, tail: str) -> None:
        """一份判断，最后一条是评审动作条目；`tail` 是它 applicable 之后那几行。"""
        self.write_use(domains=[d for d in ALL_DOMAINS if d not in ("SEC", "DLV")],
                       constraints=(
                           f"  - id: {HIT}\n    applicable: true\n"
                           "    requirement: 凭证临时文件写 wallet_receipt_temp，离开即删\n"
                           "    contract: wallet_receipt_temp\n"
                           "  - id: DLV-01\n    applicable: false\n"
                           "    reason: 本需求不新增也不修改任何面向用户的字符串\n"
                           f"  - id: {REVIEW_ACTION}\n" + tail))

    def test_a_review_action_entry_may_be_a_hit(self) -> None:
        """它照样可能命中——命中的结果是一次跨团队的动作，不是代码要求。

        判命中就报错的话，作者要绕开只能写「不命中」，那份判断从此与事实不符，
        而下游读的正是它。
        """
        self.with_review_action("    applicable: true\n"
                                "    reason: 本需求新增了对外开放的签约查询接口，"
                                "它的说明文档要随本轮归档\n")
        out = self.render_ok()
        self.assertIn(REVIEW_ACTION, out)

    def test_a_review_action_hit_must_say_why(self) -> None:
        """命中要说清为什么——那句话是评审者回查的依据。"""
        self.with_review_action("    applicable: true\n")
        self.assert_render_names("判命中要写 reason")

    def test_a_review_action_entry_is_not_a_code_requirement(self) -> None:
        """写成代码要求才点名，而且点名的是写了哪几个字段。"""
        self.with_review_action("    applicable: true\n"
                                "    reason: 本需求新增了对外开放接口，说明文档要随本轮归档\n"
                                "    requirement: 归档接口说明文档\n")
        out = self.assert_render_names("不产生代码要求")
        self.assertIn("requirement", out, "没点名是哪个字段写错了")

    def test_a_review_action_hit_gets_its_own_section(self) -> None:
        """它不进 §10 的命中表——混进去读者会当成要写的代码；
        从表里删掉又等于说「没命中」，而它确实命中了。所以单列一小节。
        """
        self.with_review_action("    applicable: true\n"
                                "    reason: 本需求新增了对外开放接口，说明文档要随本轮归档\n")
        out = self.render_ok()
        section = out.split("评审动作（命中，不产生代码要求）：", 1)
        self.assertEqual(2, len(section), "命中的评审动作没有自己那一小节")
        line = section[1].strip().split("\n")[0]
        self.assertIn(REVIEW_ACTION, line)
        self.assertIn("归档状态", line, "处置原文没带上，读者不知道命中之后要做什么")
        self.assertIn("说明文档要随本轮归档", line, "依据没带上")
        table = out.split("| 编号 | 强制力 | 本需求的要求 | 落点契约名 | 验法 |", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn(REVIEW_ACTION, table, "评审动作混进了命中表")


class TestPatternsAreCandidatesOnly(KnowledgeUseCase):
    """spec 只登记候选。选型缺方案上下文，那是 plan 的事。"""

    def test_an_unregistered_candidate_is_named(self) -> None:
        self.write_use(patterns="  - unit: 凭证生成\n    candidate: 状态机\n"
                                "    signal: 有三个状态互相转换")
        self.assert_render_names("不在册")

    def test_no_candidate_is_a_normal_conclusion(self) -> None:
        self.write_use(patterns="  - unit: 格式与隐藏选项\n    candidate: 无候选\n"
                                "    signal: 两个选项互不依赖，没有贯穿多步的状态")
        self.assertIn("无候选", self.render_ok())

    def test_an_empty_pattern_list_is_named(self) -> None:
        self.write_use(patterns="  - unit: \n    candidate: \n    signal: ")
        self.assert_render_names("没写 unit")

    def test_registered_patterns_with_no_rows_are_still_named(self) -> None:
        """有在册模式时空着不行——「判过了不需要」要写出单元与理由。"""
        self.write_use(patterns="")
        self.assert_render_names("一个适用单元都没登记")

    def test_zero_registered_patterns_make_an_empty_list_legal(self) -> None:
        """零在册模式是合法业务：patterns 空着不再被点名。

        候选集是空的，「这一段像哪个模式」注定只有一种答案——逼作者造一行
        假候选或假反证，得到的是凑数的登记，不是判断。
        """
        manifest = self.root / "doc" / "extensions" / "manifest.yaml"
        text = "\n".join(l for l in manifest.read_text(encoding="utf-8").split("\n")
                         if "design-patterns" not in l)
        manifest.write_text(text, encoding="utf-8")
        self.write_use(patterns="")
        self.render_ok()

    def test_choosing_in_spec_is_refused(self) -> None:
        """在 spec 里选型即点名——那一步的结论落 plan 的 contracts.yaml。"""
        self.write_use(patterns=f"  - unit: 凭证生成\n    candidate: {PATTERN}\n"
                                "    signal: 三个分支各有独立状态\n    chosen: true")
        self.assert_render_names("spec 只登记候选不选型")


class TestTheGeneratedZoneIsNotASecondSource(KnowledgeUseCase):
    """§10/§11 是投影。它与 YAML 对不上时，错的一定是投影。"""

    def zone_problems(self) -> list[str]:
        proc = node("-e", f"""
            const root = {json.dumps(self.root.as_posix())};
            Promise.all([
              import({as_url(self.root / 'doc/extensions/hooks/shared/knowledge-use/document.mjs')}),
              import({as_url(self.root / 'doc/extensions/hooks/shared/knowledge.mjs')}),
              import({as_url(self.root / 'doc/extensions/hooks/shared/knowledge-use/projection.mjs')}),
            ]).then(([d, k, pr]) => {{
              const kn = k.activeKnowledge(root);
              const use = d.readUse(root, {json.dumps(FEATURE)});
              const text = require('fs').readFileSync({json.dumps(self.spec_path.as_posix())}, 'utf-8');
              process.stdout.write(JSON.stringify(
                pr.zoneProblems(root, text, pr.renderZones(kn, use))));
            }});
        """)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_freshly_rendered_spec_has_no_problems(self) -> None:
        self.write_use()
        self.render_ok()
        self.assertEqual([], self.zone_problems())

    def test_rendering_twice_is_byte_stable(self) -> None:
        """同一份 YAML 生成两次字节完全相同——生成区没有随机量。"""
        self.write_use()
        first = self.render_ok()
        self.assertEqual(first, self.render_ok())

    def test_a_hand_edited_zone_is_named(self) -> None:
        self.write_use()
        text = self.render_ok()
        self.spec_path.write_text(
            text.replace("wallet_receipt_temp", "手改成了别的名字"), encoding="utf-8")
        problems = self.zone_problems()
        self.assertTrue(any("对不上" in p for p in problems), problems)

    def test_a_leftover_hand_written_table_is_named(self) -> None:
        """迁移期真会遇到：这一章原先是手填的表，加了生成区之后旧表还留着。

        两张表说同一件事，只有一张跟着 YAML 走。生成器不删人写的字节——
        它只报出来，删哪一张由人决定。
        """
        self.write_use()
        text = self.render_ok()
        stale = "\n".join([
            "<!-- knowledge-use:end -->",
            "| 编号 | 本需求的要求 | 落点契约名 |",
            "|---|---|---|",
            "| SEC-01 | 旧的手写表还在这儿 | — |",
        ])
        self.spec_path.write_text(
            text.replace("<!-- knowledge-use:end -->", stale, 1), encoding="utf-8")
        problems = self.zone_problems()
        self.assertTrue(any("生成区之外还有表" in p for p in problems), problems)

    def test_a_missing_zone_is_named(self) -> None:
        self.write_use()
        problems = self.zone_problems()
        self.assertEqual(2, len(problems), problems)
        for p in problems:
            self.assertIn("没有生成区", p)

    def test_a_changed_judgement_changes_the_projection(self) -> None:
        """改 YAML 里的一条为不命中，重新生成之后 §10 跟着变——投影是活的。"""
        self.write_use()
        self.assertIn("wallet_receipt_temp", self.render_ok())
        self.write_use(constraints=f"  - id: {HIT}\n    applicable: false\n"
                                   "    reason: 本需求不产生任何出口，凭证只在端侧生成不外传")
        text = self.render_ok()
        zone = text.split("knowledge-use:begin 规约约束要求")[1].split("knowledge-use:end")[0]
        self.assertNotIn("wallet_receipt_temp", zone, "改判之后生成区还留着旧的落点")
        self.assertIn("本需求不产生任何出口", zone)

    def test_the_zone_goes_after_the_template_note(self) -> None:
        """生成区排在模板给作者的写法说明之后——说明是给人看的，不被生成器吃掉。"""
        self.write_use()
        text = self.render_ok()
        self.assertLess(text.index("判定产生的代码要求"), text.index("knowledge-use:begin"))


class TestTheJudgementKnowsWhichKnowledgeItWasMadeAgainst(KnowledgeUseCase):
    """知识改了而判断没重做，要看得出来——否则「判过了」指的是哪一版没人知道。"""

    def test_a_stale_digest_is_named(self) -> None:
        self.write_use(digest="sha256:0000000000000000")
        self.assert_render_names("知识改过了而这份判断没重做")

    def test_a_missing_digest_is_named(self) -> None:
        self.write_use()
        text = self.use_path.read_text(encoding="utf-8")
        self.use_path.write_text(
            "\n".join(l for l in text.split("\n") if not l.startswith("manifest_digest")),
            encoding="utf-8")
        self.assert_render_names("缺 manifest_digest")

    def test_a_missing_file_says_what_it_is_for(self) -> None:
        proc = self.render()
        self.assertEqual(1, proc.returncode)
        self.assertIn("knowledge-use.yaml", proc.stderr)
        self.assertIn("唯一真源", proc.stderr)

    def test_a_broken_file_is_not_an_empty_judgement(self) -> None:
        self.use_path.write_text("schema: 1\nconstraints: 这不是列表\n", encoding="utf-8")
        self.assert_render_names("不是列表")


class TheRequirementIsOneLinePerThing(KnowledgeUseCase):
    """一条要求一行，落点由作者显式说是哪一种。

    五跑的 §10 一格 80–155 字、混着代码标识，十一行里四行落点写「—」——
    要求没有落点，等于判了命中却没说落在哪。
    """

    def test_a_list_renders_one_row_each(self) -> None:
        """同一个编号有几条要求就出几行：挤进一格，读者要数分号才分得出这是几件事。"""
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement:\n"
            "      - 凭证临时文件写 wallet_receipt_temp\n"
            "      - 分享完成或离开页面即删\n"
            "    contract: wallet_receipt_temp"))
        spec = self.render_ok()
        zone = spec.split("规约约束要求", 1)[1]
        self.assertIn("凭证临时文件写 wallet_receipt_temp", zone)
        self.assertIn("分享完成或离开页面即删", zone)
        rows = [l for l in zone.split("\n") if l.startswith(f"| {HIT} |")]
        self.assertEqual(2, len(rows), f"两条要求没各成一行：{rows}")

    def test_a_hit_without_a_landing_is_named(self) -> None:
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 凭证临时文件写 wallet_receipt_temp"))
        self.assert_render_names("没写落点")

    def test_both_kinds_of_landing_at_once_is_named(self) -> None:
        """二选一：落在 §9 实体上写 contract，落在别处写 impact。"""
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 凭证临时文件写 wallet_receipt_temp\n"
            "    contract: wallet_receipt_temp\n"
            "    impact: 交易详情页"))
        self.assert_render_names("同时写了 contract 与 impact")

    def test_a_column_header_is_not_an_entity(self) -> None:
        """表头那一格是列名，不是落点。收了它，`contract: 键名/表名` 就验得过。"""
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 凭证临时文件写 wallet_receipt_temp\n"
            "    contract: 名称"))
        self.assert_render_names("不在 §9 技术契约里")

    def test_an_empty_section_nine_still_refuses_a_contract(self) -> None:
        """§9 在而一个实体都没登记：任何 contract 都引不到东西，不能整条跳过。

        「没有这一章」与「有这一章而空」处置相反——前者不判，后者逐条报。
        """
        self.spec_path.write_text(
            "# 甲需求 spec\n\n## 9. 技术契约\n\n### 9.2 数据存储\n\n"
            "| 名称 | 用途 |\n|---|---|\n\n"
            "## 10. 规约约束要求\n\n<!-- 判定产生的代码要求，按命中条目派生。 -->\n\n"
            "## 11. 设计模式候选登记\n\n<!-- 只登记候选，不做选型。 -->\n",
            encoding="utf-8")
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 凭证临时文件写 wallet_receipt_temp\n"
            "    contract: wallet_receipt_temp"))
        self.assert_render_names("§9 现在一个实体都没登记")

    def test_an_impact_landing_is_accepted_and_prefixed(self) -> None:
        """RTL、图标、文案这类本来就没有 §9 实体，不强挂——但要点名影响对象。"""
        self.write_use(constraints=(
            f"  - id: {HIT}\n"
            "    applicable: true\n"
            "    requirement: 方向性布局参数一律用 start/end\n"
            "    impact: 签约页与管理页的布局参数"))
        zone = self.render_ok().split("规约约束要求", 1)[1]
        self.assertIn("影响 · 签约页与管理页的布局参数", zone)


class TheReportingFactsStayInTheirLane(unittest.TestCase):
    """上报事实一处维护：VOC、Chart、BI 在同一份 facts，Chart 独有的语义不套给其它渠道。

    渠道各自使用项目定义的字段；共用的渠道分工说明不等于把 Chart 编码协议套给 VOC。
    """

    KNOWLEDGE = REPO_ROOT / "doc" / "extensions" / "knowledge"

    def sections(self) -> dict[str, str]:
        text = (self.KNOWLEDGE / "facts" / "reporting.md").read_text(encoding="utf-8")
        parts = re.split(r"^## ", text, flags=re.M)
        return {part.split("\n", 1)[0]: part for part in parts[1:]}

    def test_one_entry_in_the_activation_list(self) -> None:
        manifest = (REPO_ROOT / "doc" / "extensions" / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn("knowledge/facts/reporting.md", manifest)
        self.assertNotIn("chart-reporting", manifest)
        self.assertFalse((self.KNOWLEDGE / "facts" / "chart-reporting.md").exists())

    def test_each_facet_keeps_its_own_heading_and_confirmation(self) -> None:
        """业务语义在前、协议映射在后只是阅读顺序：每个事实面仍是独立 H2，未确认的面仍要求取证。"""
        proc = node("--input-type=module", "-e",
                    f"const k = (await import({as_url(EXT / 'hooks/shared/knowledge.mjs')}))"
                    f".activeKnowledge({json.dumps(REPO_ROOT.as_posix())});"
                    "process.stdout.write(JSON.stringify(k.facts.find(f => f.name === 'reporting')));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        fact = json.loads(proc.stdout)
        self.assertEqual(["业务统计语义", "渠道与已有能力", "身份与 SDK 映射", "结果与字段映射",
                          "业务扩展字段", "登记与复用", "使用参考"], fact["facets"])
        self.assertEqual(["业务扩展字段"], fact["unconfirmed"])

    def test_engineering_capabilities_do_not_repeat_reporting(self) -> None:
        text = (self.KNOWLEDGE / "facts" / "engineering-capabilities.md").read_text(encoding="utf-8")
        for token in ("WalletHAManager", "vocBuilder", "chartBuilder", "logAndReport"):
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_every_channel_has_its_row(self) -> None:
        """项目的四种上报来源各一行：只做 VOC、只做 BI 或只涉及页面交互的需求都读得到自己那一行。"""
        overview = next(v for k, v in self.sections().items() if "渠道与已有能力" in k)
        for channel in ("| VOC |", "| Chart |", "| BI |", "| 交互自动记录 |"):
            self.assertIn(channel, overview)

    def test_chart_only_semantics_stay_under_chart(self) -> None:
        sections = self.sections()
        voc = next(p for v in sections.values() for p in v.split("\n\n") if p.startswith("VOC "))
        shared = "".join(v for k, v in sections.items() if "渠道与已有能力" in k or "业务统计语义" in k) + voc
        # “终态”可用于解释渠道分工；这里只排除具体运维编码/枚举协议。
        for token in ("WalletFuncResult", "十位", "FuncID_SubFuncID", "STEP_"):
            with self.subTest(token=token):
                self.assertNotIn(token, shared, "Chart 独有的语义写进了公共或 VOC 部分")


class TheEntryIsOnlyACommand(unittest.TestCase):
    """判断的读取、验证与投影各在所属模块，入口只剩两条命令。

    入口若顺手把库 API 再导出一遍，调用方就有两条路径引到同一个函数——改归属时
    只有一条被改到，另一条静默还在。所以这里按「入口导出了什么」判，不按目录长相判。
    """

    KU = EXT / "hooks" / "shared" / "knowledge-use"

    def exports_of(self, module: Path) -> list[str]:
        proc = node("--input-type=module", "-e",
                    f"const m = await import({as_url(module)});"
                    "process.stdout.write(Object.keys(m).sort().join(','));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return [n for n in proc.stdout.strip().split(",") if n]

    def test_the_entry_exports_nothing(self) -> None:
        self.assertEqual([], self.exports_of(MODULE),
                         "入口又把库 API 转发了一遍——调用方会有两条路引到同一个函数")

    def test_importing_the_entry_runs_no_command(self) -> None:
        """被 import 时不许跑命令：写盘发生在「谁也没调它」的时候最难查。"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            proc = node("--input-type=module", "-e",
                        f"await import({as_url(MODULE)});"
                        "process.stdout.write('done');", cwd=work)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual("done", proc.stdout.strip(), "import 期还输出了别的")
            self.assertEqual([], sorted(p.name for p in work.iterdir()),
                             "import 期写了盘")

    def test_each_module_owns_its_own_question(self) -> None:
        """三个模块各答一问，导出集合就是它们的分界。"""
        self.assertIn("readUse", self.exports_of(self.KU / "document.mjs"))
        self.assertIn("coverageProblems", self.exports_of(self.KU / "validation.mjs"))
        for name in ("renderZones", "zoneProblems", "applyZones"):
            self.assertIn(name, self.exports_of(self.KU / "projection.mjs"))
        self.assertNotIn("coverageProblems", self.exports_of(self.KU / "document.mjs"),
                         "真源模块里还留着一份验证")

    def test_the_dependency_runs_one_way(self) -> None:
        """验证与投影都读 document 的规范化结果，document 不反过来依赖它们。"""
        doc = (self.KU / "document.mjs").read_text(encoding="utf-8")
        for sibling in ("validation.mjs", "projection.mjs"):
            self.assertNotIn(sibling, doc, f"document 反向依赖了 {sibling}")
        for name in ("validation.mjs", "projection.mjs"):
            body = (self.KU / name).read_text(encoding="utf-8")
            self.assertIn("from './document.mjs'", body,
                          f"{name} 没用 document 的规范化结果，自己又读了一遍")


if __name__ == "__main__":
    unittest.main()
