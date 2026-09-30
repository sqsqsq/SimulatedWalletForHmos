"""交付门拦不拦得住、读者审查的任务送不送得到。

## 交付门

`check --deliver` 核的是**登记过的那一份**：没登记不交付；登记之后蓝图、交给设计的输入或激活知识变了，
登记说的就不是现在这份，拦下并指回重新登记。独立人读审查的原生调用接通之前，审查结论取不到——
照实说这份 Story 未经审查，不写成通过；通过之后给出一次交付选择（本地单没有送审）。

## 送达与任务定义

判据没进审查者的任务清单，或者任务里没有一条问「材料登记的每张图用了没有」，
审查那一步就没有对象。这两道也在这一份里锚住。
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml, DEV_EXT
from designed_fixture import DRAFT, designed_copy
import design_kit

REPO = Path(__file__).resolve().parents[2]
STORY_BUILD = DEV_EXT / "skills/story/scripts/core/story-build.mjs"
CONTRACT = DEV_EXT / "skills/story/contracts/story-chapters.json"
FEATURE = "RT90001"

STORY_MD = """# 甲需求（SMPFEAT）

## 背景

用户现在拿不到凭据。
"""

class TheDeliveryGateChecksTheRegisteredBasis(unittest.TestCase):
    """交付门只在 `--deliver` 起作用：交付的是登记过的那一份，依据变了要拦，没经过独立审查要照实说。"""

    FIXTURE = REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(self.FIXTURE, "REQ-DEMO", DRAFT, self.root)
        self.flow_path = self.root / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-flow.json"

    def check(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(STORY_BUILD), "check", "--feature", "REQ-DEMO",
             "--project-root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def register(self) -> None:
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        flow["status"] = "story_written"
        flow["story_basis"] = design_kit.registered_basis(self.root, "REQ-DEMO")
        self.flow_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_plain_check_never_touches_the_delivery_gate(self) -> None:
        """登记前与返修中跑的是普通 check：那时独立审查还没发生。"""
        out = self.check()
        self.assertNotIn("交付门", out.stdout + out.stderr, "普通 check 去判了还没发生的事")

    def test_an_unregistered_story_is_not_delivered(self) -> None:
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("还没登记成文", out.stdout + out.stderr)

    def test_a_registered_story_passes_and_says_it_was_not_reviewed(self) -> None:
        """审查结论取不到时照实说未审，给出交付选择；本地单没有送审。"""
        self.register()
        out = self.check("--deliver")
        text = out.stdout + out.stderr
        self.assertEqual(0, out.returncode, text)
        self.assertIn("未经独立人读审查", text)
        self.assertNotIn("PASS", text)
        for choice in ("完整设计交接", "完整实现", "暂不推进"):
            self.assertIn(choice, text)
        self.assertNotIn("/story archive", text, "本地单没有送审")

    def test_a_blueprint_revised_after_registration_blocks(self) -> None:
        self.register()
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "本需求没有任何上报动作", "本需求只在提交时上报一次")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("登记之后", out.stdout + out.stderr)


class ReviewTaskReachesTheVerifier(unittest.TestCase):
    """判据要先成为「任务」，才谈得上做没做。

    注入的清单只列 framework 自己那十项、扩展这边又按前缀过滤，两道都漏，
    读者审查就不是「任务」，审查者不会去做它。

    输入自带：临时工作区里造一个最小需求目录。拿仓内真实需求当输入的话，
    CLI 起跑时装置会把 `doc/features` 整个迁走，测试跟着一起塌。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(DEV_EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        src.mkdir(parents=True)
        (src.parent / "story.md").write_text(STORY_MD, encoding="utf-8")
        (src / "materials.json").write_text(json.dumps({"materials": [
            {"kind": "image", "paths": ["assets/doc-a/one.png"], "caption": "签约页"},
        ]}, ensure_ascii=False), encoding="utf-8")

    def inject(self, feature: str = FEATURE) -> str:
        driver = """
        import(process.argv[2]).then(async m => {
          const out = await m.default({ projectRoot: process.argv[3],
                                        feature: process.argv[4], phase: 'spec' });
          process.stdout.write((out.promptFragments || []).join('\\n\\n'));
        });
        """
        script = self.root / "drive.mjs"
        script.write_text(driver, encoding="utf-8")
        hook = self.root / "doc/extensions/hooks/shared/pre_verifier.mjs"
        r = subprocess.run(
            ["node", str(script), hook.resolve().as_uri(), str(self.root), feature],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout

    def test_the_reader_review_is_injected_not_filtered_out(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text, "读者审查被滤掉了")

    def test_it_comes_first(self) -> None:
        """它要通读一份 300 行的归档件，排在后面最容易被当附注跳过。"""
        text = self.inject()
        self.assertLess(text.index("story_reader_review"), text.index("知识判据"))

    @property
    def overlay(self) -> Path:
        return self.root / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml"

    def overlay_method(self) -> str:
        """判据与结论要求的**唯一维护处**：spec overlay 的 `story_reader_review`。"""
        text = self.overlay.read_text(encoding="utf-8")
        at = text.index("story_reader_review:")
        end = text.index("\n# ", at)
        return text[at:end]

    def test_the_task_lists_every_image_with_its_state(self) -> None:
        """任务里没有的**数据**，审查者拿不到：图逐张列出，连它是什么、用不用一起。"""
        text = self.inject()
        self.assertIn("材料里的图", text)
        self.assertIn("assets/doc-a/one.png", text)
        self.assertIn("签约页", text)

    def test_a_broken_manifest_is_an_input_gap_not_no_images(self) -> None:
        """审查端与作者端对同一份坏清单给同一个含义：**缺口**，不是「本项无图不适用」。

        `materials` 是字符串时直接 `.filter` 会抛——审查者拿到的会是一个没有来源说明的
        TypeError，而它本该读到「清单坏了」。
        """
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        for name, payload in (("空对象", "{}"),
                              ("materials 是字符串", '{"materials":"invalid"}'),
                              ("旧的 items/path",
                               '{"items":[{"kind":"image","path":"a.png"}]}'),
                              ("坏 JSON", "{ 坏了")):
            with self.subTest(shape=name):
                (src / "materials.json").write_text(payload, encoding="utf-8")
                text = self.inject()
                self.assertIn("输入有缺口", text, "坏清单被当成「无图不适用」")
                self.assertIn("story_flow.py round", text, "没给修法")
                self.assertNotIn("材料清单里没有图片", text)

    def test_a_legal_empty_manifest_is_no_images(self) -> None:
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "materials.json").write_text(
            json.dumps({"materials": [{"kind": "doc", "paths": ["RR/prd.md"]}]},
                       ensure_ascii=False), encoding="utf-8")
        text = self.inject()
        self.assertIn("材料清单里没有图片", text)
        self.assertNotIn("输入有缺口", text)

    def test_an_image_the_disk_cannot_read_is_marked(self) -> None:
        """登记着而盘上读不到：审查要知道这一张现在看不了，不是「作者没用它」。"""
        text = self.inject()
        self.assertIn("盘上读不到", text)

    def test_the_host_assembly_really_carries_the_overlay_method(self) -> None:
        """正常路径的证据：**宿主装配之后**任务里有这份方法。

        只断言「fragment 里没有方法」加「overlay 文件里有那段文字」证明不了它到得了
        审查者手上——中间那一步（框架把 overlay 合进本阶段判据）没被核过。
        这里调框架自己那个合并函数（`mergePhaseRuleSpec`），不启动真实 CLI、不改 Framework。
        """
        harness = REPO / "demo" / "framework" / "harness"
        runner = harness / "node_modules" / "ts-node" / "dist" / "bin.js"
        if not runner.is_file():
            self.skipTest("framework/harness 里没有 ts-node")
        script = (
            "const { mergePhaseRuleSpec } = require('./profile-loader');"
            "const YAML = require('yaml'); const fs = require('fs');"
            f"const overlay = YAML.parse(fs.readFileSync({json.dumps(str(self.overlay))}, 'utf-8'));"
            "const base = { phase: 'spec', semantic_checks: { framework_own: { description: 'x' } } };"
            "const merged = mergePhaseRuleSpec(base, overlay);"
            "const item = merged.semantic_checks.story_reader_review || {};"
            "process.stdout.write(JSON.stringify({"
            "  hint: String(item.ai_prompt_hint || ''),"
            "  desc: String(item.description || ''),"
            "  keptFrameworkOwn: !!merged.semantic_checks.framework_own }));")
        out = subprocess.run(["node", str(runner), "-e", script],
                             cwd=str(harness), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, out.returncode, out.stderr[-600:])
        got = json.loads(out.stdout)
        self.assertTrue(got["keptFrameworkOwn"], "合并把框架自己那几项挤掉了")
        both = got["desc"] + got["hint"]
        for needle in ("跨章对着读", "blocking_findings", "advisories", "不许空",
                       "按实际关系判"):
            self.assertIn(needle, both, f"宿主装配后的任务里没有「{needle}」")

    def test_the_method_is_maintained_only_in_the_overlay(self) -> None:
        """方法一份：overlay 维护「怎么判」，构造器只给这一次的数据。

        两处各写一遍时改一处另一处静默过期——而过期的那一份仍会被送到审查者手上。
        """
        method = self.overlay_method()
        for needle in ("总览与局部加起来", "端到端过程", "分支去向", "理由成不成立",
                       "跨章对着读", "blocking_findings", "advisories", "不许空"):
            self.assertIn(needle, method, f"overlay 里没有「{needle}」")
        fragment = self.inject()
        for needle in ("总览与局部加起来", "端到端过程", "理由成不成立", "blocking_findings"):
            self.assertNotIn(needle, fragment, f"构造器又复制了一份方法：{needle}")

    def test_the_collaboration_order_is_judged_by_relation_not_headcount(self) -> None:
        """两方之间也可能有复杂往返，多方单向直通反而不需要——不设人数门槛。"""
        method = self.overlay_method()
        self.assertNotIn("三个以上参与方", method)
        self.assertIn("按实际关系判", method)
        self.assertNotIn("三个以上参与方", self.inject())

    def test_the_task_carries_the_story_full_text_once(self) -> None:
        """审查对象**放全文**，一次。

        只给路径让它自己去开的话，截断、读旧稿、读不到都会变成「看起来审过了」，
        而三种都分不出来。外层围栏比正文里最长的那道再多一个反引号——固定长度时，
        正文里合法地出现一道更长的示例围栏就会把包装提前关上。
        """
        task = self.inject()
        self.assertIn("### 审查对象：当前 `AR/story.md`", task)
        fence = next(l for l in task.split("\n")
                     if l.startswith("```") and l.endswith("markdown"))
        self.assertGreaterEqual(len(fence) - len("markdown"), 4, fence)
        for line in STORY_MD.strip().split("\n"):
            if line.strip():
                self.assertIn(line, task, f"全文里少了这一行：{line}")
        self.assertEqual(1, task.count(fence), "全文放了不止一次")

    def test_a_projection_refresh_keeps_the_task_and_an_authored_edit_changes_it(self) -> None:
        """AC22：机器区重投不改审查片段（审查对象不变）；作者区改了，片段跟着变。片段不含机器区内容。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        zone = ("\n<!-- story-build:begin 技术契约·端云接口 · 由spec 「宿主扩展治理项 › 技术契约 › 端云接口」生成，改它请改真源 · sha256:0000000000000000 -->\n"
                "| 接口 | 用途 |\n|---|---|\n| queryState | 查状态 |\n<!-- story-build:end -->\n")
        story.write_text(STORY_MD + zone, encoding="utf-8")
        first = self.inject()
        story.write_text(STORY_MD + zone.replace("queryState | 查状态", "queryState | 查处理状态"), encoding="utf-8")
        self.assertEqual(first, self.inject(), "机器区重投换了审查对象")
        self.assertNotIn("queryState", first, "机器区内容进了审查片段")
        story.write_text(STORY_MD + "\n作者补的一句。\n" + zone, encoding="utf-8")
        self.assertNotEqual(first, self.inject(), "作者区改了，审查对象没跟着变")

    def test_a_longer_inner_fence_does_not_close_the_wrapper(self) -> None:
        """正文里合法地出现一道更长的围栏（贴一段 markdown 示例）时，包装不能被它关上。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        story.write_text(STORY_MD + "\n`````markdown\n```mermaid\nA-->B\n```\n`````\n",
                         encoding="utf-8")
        task = self.inject()
        fence = next(l for l in task.split("\n")
                     if l.startswith("```") and l.endswith("markdown"))
        self.assertGreaterEqual(len(fence) - len("markdown"), 6, fence)
        after = task.split(fence, 1)[1]
        self.assertIn("`````markdown", after, "更长的内层围栏没被包进来")

    def test_an_unreadable_story_is_a_skip_not_an_empty_full_text(self) -> None:
        """空串冒充全文 = 审查会对着空白作答；如实 SKIP。"""
        (self.root / "doc" / "features" / FEATURE / "AR" / "story.md").write_text(
            "   \n", encoding="utf-8")
        task = self.inject()
        self.assertIn("SKIP", task)
        self.assertNotIn("```````markdown", task)

    def test_the_task_says_where_the_overwritten_ar_is_kept(self) -> None:
        """当前 AR/design.md 是提取稿：回查上游原话给 .backups/local/ 的位置，不让它用提取稿替。"""
        task = self.inject()
        self.assertIn("`.backups/local/`", task)
        self.assertIn("提取稿", task)

    def test_the_task_carries_the_recheck_list(self) -> None:
        """审查拿到的回看清单与作者手里的是同一张：逐条核去向，不另编一份。"""
        task = self.inject()
        self.assertIn("### 回看清单", task)
        self.assertIn("这句话材料里有吗", task.split("### 回看清单", 1)[1])
        method = self.overlay_method()
        for needle in ("回看清单逐条核去向", "撞点", "算没写依据"):
            self.assertIn(needle, method, f"overlay 的审查提示里没有「{needle}」")

    def test_the_task_carries_the_contract_questions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        text = self.inject()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["questions"][0], text,
                          f"「{chapter['title']}」的读者问题没送到")

    def test_the_output_contract_lives_with_the_method(self) -> None:
        """PASS 只进汇总表、明细只列非 PASS——本项不设例外，否则正常 PASS 会被拒。

        它与方法同处一份（overlay）：输出要求与判据分在两个文件时，改一处就对不上。
        """
        method = self.overlay_method()
        self.assertIn("汇总表", method)
        self.assertIn("不许空", method)
        self.assertIn("blocking_findings", method)
        self.assertIn("advisories", method)
        self.assertNotIn("为标记的一块", method, "又要求了 markdown 块")

    def plan_path(self) -> Path:
        return self.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-template.md"

    def base_plan(self) -> str:
        return (REPO / "test/fixtures/failure-modes/R01-verdict-echo/good/doc/features"
                / "REQ-DEMO/AR/story-src/story-template.md").read_text(encoding="utf-8")

    def test_the_task_carries_the_writing_design_once_and_follows_it(self) -> None:
        """写作设计全文随任务到审查者手上一次；改了设计，任务跟着变——审查核的是这一版。"""
        base = self.base_plan()
        self.plan_path().write_text(
            base.replace("## 阅读主线\n\n", "## 阅读主线\n\n设计里独有的一句甲。\n"), encoding="utf-8")
        task = self.inject()
        self.assertIn("### 作者的写作设计", task)
        self.assertEqual(1, task.count("设计里独有的一句甲。"), "设计全文没送到，或送了不止一次")
        self.assertIn("待核的作者判断", task, "没说清设计是待核的判断而不是标准")
        self.plan_path().write_text(
            base.replace("## 阅读主线\n\n", "## 阅读主线\n\n改过之后的一句乙。\n"), encoding="utf-8")
        task = self.inject()
        self.assertIn("改过之后的一句乙。", task)
        self.assertNotIn("设计里独有的一句甲。", task, "任务没跟着当前设计走")

    def test_a_missing_writing_design_is_a_gap_not_an_empty_design(self) -> None:
        section = self.inject().split("### 作者的写作设计", 1)[1].split("###", 1)[0]
        self.assertIn("写作设计缺口", section)
        self.assertNotIn("```", section, "拿一段空围栏冒充审过了设计")

    def test_the_task_points_at_the_original_materials(self) -> None:
        """审查要能回到原件：原文逐份给位置；该有而读不到的点名，不替它下结论。"""
        feature = self.root / "doc" / "features" / FEATURE
        (feature / "RR").mkdir(parents=True, exist_ok=True)
        (feature / "RR" / "prd.md").write_text("# 产品需求\n", encoding="utf-8")
        section = self.inject().split("### 原材料原文", 1)[1].split("###", 1)[0]
        self.assertIn("`RR/prd.md`", section)
        self.assertIn("acceptance.yaml", section)
        self.assertNotIn("读不到 `SR/design.md`", section, "本地单没有系统设计是正常的")
        (feature / "AR" / "detail.json").write_text("{}", encoding="utf-8")
        section = self.inject().split("### 原材料原文", 1)[1].split("###", 1)[0]
        self.assertNotIn("读不到 `SR/design.md`", section, "本地需求留着 detail.json 仍是本地需求")
        remote = f"AR{FEATURE}"
        shutil.copytree(feature, feature.parent / remote)
        section = self.inject(remote).split("### 原材料原文", 1)[1].split("###", 1)[0]
        self.assertIn("读不到 `SR/design.md`", section, "系统需求缺必备来源没点名")

    def test_the_overlay_judges_against_sources_not_the_design(self) -> None:
        """先按原材料独立判断，再用设计定位作者的安排——设计不是审查标准；方法只在 overlay。"""
        method = self.overlay_method()
        for needle in ("先独立想清楚", "写作设计", "设计漏掉的不因此算不在范围", "写了理由不等于理由成立",
                       "还开着的决定被写成已定", "acceptance.yaml", "正文提到过", "真实待决写清了边界",
                       "写明未验证与影响"):
            self.assertIn(needle, method, f"overlay 里没有「{needle}」")
        fragment = self.inject()
        for needle in ("先独立想清楚", "设计漏掉的不因此算不在范围", "还开着的决定被写成已定"):
            self.assertNotIn(needle, fragment, f"构造器又复制了一份方法：{needle}")

    def test_the_task_does_not_mention_a_publisher(self) -> None:
        """报告由调用方原样写出，没有钩子代它发布——任务书里不该还有那一环。"""
        text = self.inject()
        self.assertNotIn("插件", text)



class TheTaskMovesOnlyWithTheAuthorsInput(unittest.TestCase):
    """U38：审查片段只随作者输入变化，登记一份报告不铸出新的审查对象。

    framework 按材料摘要给审查对象寻址，钩子片段在摘要里。片段里写「上一份报告的路径」时，
    每登记一份报告下一次就是新对象，同一份材料审了又审（09-26 实跑 auto 派审 20 次）。
    """

    setUp = ReviewTaskReachesTheVerifier.setUp
    inject = ReviewTaskReachesTheVerifier.inject

    def register_report(self, subject: str) -> None:
        reports = self.root / "doc" / "features" / FEATURE / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        ledger = reports / "verifier.conclusions.json"
        data = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
        data[subject] = {"verdict": "PASS"}
        ledger.write_text(json.dumps(data), encoding="utf-8")
        (reports / f"verifier.report.{subject}.md").write_text("审查正文。\n", encoding="utf-8")

    def decisions(self, title: str) -> None:
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D1", "status": "open", "title": title, "decider": "需求方",
             "clarification": "1. 甲\n2. 乙"}]}, ensure_ascii=False), encoding="utf-8")

    def test_registering_reports_leaves_the_task_unchanged(self) -> None:
        self.decisions("超时后怎么办")
        first = self.inject()
        self.register_report("a" * 64)
        second = self.inject()
        self.register_report("b" * 64)
        third = self.inject()
        self.assertEqual(first, second, "登记一份报告就改了审查片段：审查对象会跟着换代")
        self.assertEqual(first, third)
        self.assertIn("verifier.conclusions.json", self.overlay_text(),
                      "上一份报告的找法要写在判据里，片段里不写")

    def test_the_authors_input_still_moves_the_task(self) -> None:
        self.decisions("超时后怎么办")
        before = self.inject()
        self.decisions("超时之后是否自动重试")
        self.assertNotEqual(before, self.inject(), "决策登记改了，审查片段却没变")

    def overlay_text(self) -> str:
        return (self.root / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml").read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
