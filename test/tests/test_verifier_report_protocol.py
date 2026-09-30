"""交付门拦不拦得住、读者审查的任务送不送得到。

## 审查、登记与交付门

审查接 Framework 原生的无 Feature review request：准备时定稿、生成请求，审查者的回复原样存下，原生检查之后归类。
登记只读核对，审查结果可消费才写新依据，失败保留旧依据；`check --deliver` 核的是**登记过、审过的那一份**，
登记之后蓝图、输入、知识或被审文件变了就拦下；通过之后给出一次交付选择（本地单没有送审）。

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

class TheStoryIsReviewedRegisteredAndDeliveredCase(unittest.TestCase):
    """一条真实的正常链：定稿并准备原生审查请求 → 审查者回复 → 原生检查 → 登记 → 交付门。

    审查者是夹具（按原生格式写事实记录与报告），只验证协议接得上；真实的独立执行与业务效果在 CLI 里核。
    """

    FIXTURE = REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"

    FLOW = DEV_EXT / "skills/story/scripts/core/story_flow.py"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(self.FIXTURE, "REQ-DEMO", DRAFT, self.root)
        design_kit.install_review_mechanism(self.root, DEV_EXT)
        self.assertFalse((self.root / "doc" / "features" / "REQ-DEMO" / "spec").exists(), "2.0 的需求目录没有 Spec 产物")
        self.flow_path = self.root / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-flow.json"
        self.story = self.flow_path.parent.parent / "story.md"

    def run_node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(STORY_BUILD), *args, "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)

    def check(self, *extra: str) -> subprocess.CompletedProcess:
        return self.run_node("check", *extra)

    def review(self, action: str) -> subprocess.CompletedProcess:
        return self.run_node("review", "--action", action)

    def result(self) -> dict:
        out = self.review("check")
        return json.loads([l for l in out.stdout.splitlines() if l.startswith("{")][-1])

    def register(self) -> subprocess.CompletedProcess:
        return subprocess.run(["python", str(self.FLOW), "story", "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def reviewed(self, kind: str = "pass") -> Path:
        prepared = self.review("prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        return design_kit.write_review(self.root, "REQ-DEMO", kind)

    def flow(self) -> dict:
        return json.loads(self.flow_path.read_text(encoding="utf-8"))

    def native_summary(self) -> dict:
        prepared = json.loads((self.flow_path.parent / "review" / "prepared.json").read_text(encoding="utf-8"))
        return json.loads((self.root / prepared["report_dir"] / "summary.json").read_text(encoding="utf-8"))


class TheStoryIsReviewedRegisteredAndDelivered(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_plain_check_never_touches_the_delivery_gate(self) -> None:
        """登记前与返修中跑的是普通 check：那时独立审查还没发生。"""
        out = self.check()
        self.assertNotIn("交付门", out.stdout + out.stderr, "普通 check 去判了还没发生的事")

    def test_an_unregistered_story_is_not_delivered(self) -> None:
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("还没登记成文", out.stdout + out.stderr)

    def test_the_normal_chain_reviews_registers_and_delivers(self) -> None:
        """准备出的请求绑定 Story、Review 与对照材料；审查通过之后登记，交付门放行并问一次交付选择。"""
        original = self.reviewed("pass")
        kept = original.read_bytes()
        request = json.loads((self.flow_path.parent / "review" / "request.json").read_text(encoding="utf-8"))
        files = request["targets"]["files"]
        for need in ("doc/features/REQ-DEMO/AR/story.md", "doc/features/REQ-DEMO/AR/review.md",
                     "doc/features/REQ-DEMO/AR/story-src/review/task.md", "doc/extensions/rules/story-reader-rules.yaml"):
            self.assertIn(need, files)
        self.assertTrue(any("/AR/story-src/inputs/" in p for p in files), "冻结输入没进审查对象")
        self.assertTrue(any(p.endswith("component-blueprint.yaml") for p in files), "蓝图没进审查对象")
        self.assertEqual({"head": "WORKTREE"}, request["baseline"])
        self.assertEqual("pass", self.result()["result"])
        registered = self.register()
        self.assertEqual(0, registered.returncode, registered.stdout + registered.stderr)
        self.assertEqual("story_written", self.flow()["status"])
        self.assertIn("AR/review.md", self.flow()["story_basis"]["files"])
        out = self.check("--deliver")
        text = out.stdout + out.stderr
        self.assertEqual(0, out.returncode, text)
        for choice in ("完整设计交接", "完整实现", "暂不推进"):
            self.assertIn(choice, text)
        self.assertNotIn("/story archive", text, "本地单没有送审")
        self.assertEqual(kept, original.read_bytes(), "原生检查、登记或交付门改了审查者的原回复")
        again = json.loads([l for l in self.register().stdout.splitlines() if l.startswith("{")][-1])
        self.assertFalse(again["registered"], "同一份对象重复登记换了身份")


class TheStoryIsReviewedRegisteredAndDeliveredPart2(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_a_native_failure_is_not_turned_into_a_pass(self) -> None:
        """原生判 FAIL（问题只指向 Markdown 时 issue_to_file 是没声明不适用的阻断 SKIP）：如实交回，不归成 pass / warn。"""
        self.reviewed("advice")
        result = self.result()
        self.assertEqual("FAIL", self.native_summary()["verdict"])
        self.assertNotIn(result["result"], ("pass", "warn"), result)
        self.assertIn("issue_to_file", result["detail"])
        self.assertNotEqual(0, self.register().returncode)

    @unittest.expectedFailure
    def test_advisories_are_delivered_with_the_story(self) -> None:
        """产品目标：只有非阻断建议的审查可以交付，原生与 Extension 同次都给出可消费的结论。

        当前未满足：Framework 3.1.0 的 request 审查只把代码后缀当作可解析的涉及文件，问题只指向 Markdown 时
        判阻断 SKIP（见 doc/plan/2.0.0/评审意见/2026-09-30-Framework3.1专项审查文件引用问题.md）。
        上游修好后这条会意外通过，届时去掉标记。
        """
        self.reviewed("advice")
        result = self.result()
        self.assertEqual("PASS", self.native_summary()["verdict"])
        self.assertEqual("warn", result["result"], result)
        self.assertEqual(0, self.register().returncode)
        out = self.check("--deliver")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn("CR-001", out.stdout)

    def test_a_reply_out_of_the_native_format_is_kept_and_not_registered(self) -> None:
        """审查者的回复不合原生报告格式：判 report_invalid，原回复一字不改地留着，不登记。"""
        original = self.reviewed("pass")
        original.write_text("看过了，整体还行。\n", encoding="utf-8")
        kept = original.read_bytes()
        result = self.result()
        self.assertEqual("report_invalid", result["result"], result)
        self.assertEqual(kept, original.read_bytes(), "归类改了审查者的原回复")
        self.assertNotEqual(0, self.register().returncode)

    def test_a_blocking_review_is_not_registered(self) -> None:
        for kind in ("block", "major"):
            with self.subTest(kind=kind):
                self.reviewed(kind)
                self.assertEqual("fail", self.result()["result"])
                refused = self.register()
                self.assertNotEqual(0, refused.returncode)
                self.assertIn("fail", refused.stdout)
                self.assertEqual("complete", self.flow()["status"])


class TheStoryIsReviewedRegisteredAndDeliveredPart3(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_without_a_reply_nothing_is_registered(self) -> None:
        self.assertEqual("report_missing", self.result()["result"], "没准备也没回复却给了结果")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("report_missing", self.result()["result"])
        self.assertNotEqual(0, self.register().returncode)

    def test_a_story_changed_after_the_review_is_stale(self) -> None:
        self.reviewed("pass")
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual("subject_stale", self.result()["result"])
        self.assertNotEqual(0, self.register().returncode)

    def test_a_failed_registration_keeps_the_old_basis(self) -> None:
        """重新登记没过：旧依据原样留着，派生为待同步，不交付。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        before = self.flow()["story_basis"]
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.reviewed("block")
        self.assertNotEqual(0, self.register().returncode)
        self.assertEqual(("story_written", before), (self.flow()["status"], self.flow()["story_basis"]))
        self.assertNotEqual(0, self.check("--deliver").returncode)


class TheStoryIsReviewedRegisteredAndDeliveredPart4(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_a_blueprint_revised_after_registration_blocks(self) -> None:
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "本需求没有任何上报动作", "本需求只在提交时上报一次")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("登记之后", out.stdout + out.stderr)

    def test_the_review_is_prepared_once_the_structure_check_passes(self) -> None:
        """结构检查没过不准备；过了就生成带判据原文与报告格式的任务。"""
        text = self.story.read_text(encoding="utf-8")
        self.story.write_text(text.replace("## 附录", "## 附录外的一章\n\n写错的章。\n\n## 附录", 1), encoding="utf-8")
        refused = self.review("prepare")
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("结构检查没过", refused.stdout + refused.stderr)
        self.story.write_text(text, encoding="utf-8")
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        for needle in ("### 判据", "跨章对着读", "### 报告怎么写", "### 本次审查的材料", "待审（结论针对它们）"):
            self.assertIn(needle, task)
        self.assertNotIn("reviewer_unavailable", out.stdout + task)


class ARequirementWithUiReferenceGoesThrough(unittest.TestCase):
    """带界面参考图的需求：需求目录保留 `ux-reference/`，蓝图在异名的工作区（`bp-<需求>`），
    冻结、蓝图消费、原生审查准备、登记与交付一路走通（审查者是夹具）。"""

    FLOW = DEV_EXT / "skills/story/scripts/core/story_flow.py"
    IMPORT = DEV_EXT / "skills/story/scripts/core/import_sources.py"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        fixture = Path(self._tmp.name) / "fixture"
        shutil.copytree(REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good", fixture)
        feature = fixture / "doc" / "features" / "REQ-DEMO"
        (feature / "ux-reference").mkdir()
        shutil.copy2(next((REPO / "test" / "fixtures").rglob("*.png")), feature / "ux-reference" / "home.png")
        self.root = Path(self._tmp.name) / "work"
        designed_copy(fixture, "REQ-DEMO", DRAFT, self.root)
        design_kit.install_review_mechanism(self.root, DEV_EXT)

    def run_node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(STORY_BUILD), *args, "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def test_the_story_is_reviewed_and_delivered_next_to_its_ui_reference(self) -> None:
        flow = json.loads((self.root / "doc/features/REQ-DEMO/AR/story-src/story-flow.json").read_text(encoding="utf-8"))
        self.assertEqual("bp-REQ-DEMO", flow["design_binding"]["blueprint_id"])
        self.assertTrue((self.root / "doc/features/bp-REQ-DEMO/blueprint/component-blueprint.yaml").is_file())
        # 参考图没用上：照检查给的那条命令原样登记不用的理由
        hint = self.run_node("check").stderr
        command = hint.split("`import_sources.py ", 1)[1].split("`", 1)[0]
        image = command.split("--caption-image ", 1)[1].split(" ", 1)[0]
        self.assertEqual("doc/features/REQ-DEMO/ux-reference/home.png", image)
        done = subprocess.run(["python", str(self.IMPORT), "--feature", "REQ-DEMO", "--project-root", str(self.root),
                               "--caption-image", image, "--unused", "首页现状参考，本需求不改首页"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        prepared = self.run_node("review", "--action", "prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        request = json.loads((self.root / "doc/features/REQ-DEMO/AR/story-src/review/request.json").read_text(encoding="utf-8"))
        self.assertTrue(any(p.endswith("/files/ux-reference/home.png") for p in request["targets"]["files"]))
        self.assertIn("doc/features/bp-REQ-DEMO/blueprint/component-blueprint.yaml", request["targets"]["files"])
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        registered = subprocess.run(["python", str(self.FLOW), "story", "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, registered.returncode, registered.stdout + registered.stderr)
        delivered = self.run_node("check", "--deliver")
        self.assertEqual(0, delivered.returncode, delivered.stdout + delivered.stderr)


class ReviewTaskReachesTheVerifierCase(unittest.TestCase):
    """判据要先成为「任务」，才谈得上做没做：Story 的独立审查任务带着判据原文与这一次的输入交给审查者。

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
        """这一次的审查任务（`story-build review --action prepare` 写进审查目录的那一份）。"""
        module = self.root / "doc/extensions/hooks/shared/reader-review-task.mjs"
        r = subprocess.run(
            ["node", "--input-type=module", "-e",
             "const m = await import(process.argv[1]); process.stdout.write(m.readerReviewTask(process.argv[2], process.argv[3]));",
             module.resolve().as_uri(), str(self.root), feature],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout

    def spec_phase_fragments(self) -> str:
        """spec 阶段 pre_verifier 交给审查者的片段。"""
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
            ["node", str(script), hook.resolve().as_uri(), str(self.root), FEATURE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout

    @property
    def rules(self) -> Path:
        return self.root / "doc" / "extensions" / "rules" / "story-reader-rules.yaml"

    def overlay_method(self) -> str:
        """判据与结论要求的**唯一维护处**：`rules/story-reader-rules.yaml` 的 `story_reader_review`。"""
        text = self.rules.read_text(encoding="utf-8")
        return text[text.index("story_reader_review:"):]

    def material_key(self) -> str:
        module = (DEV_EXT / "skills/story/scripts/core/story/review-object.mjs").resolve().as_uri()
        r = subprocess.run(
            ["node", "--input-type=module", "-e",
             "const m = await import(process.argv[1]); const {rows} = m.reviewObject(process.argv[2], process.argv[3]);"
             "process.stdout.write(m.materialKey(process.argv[2], rows));", module, str(self.root), FEATURE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout

    def plan_path(self) -> Path:
        return self.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-template.md"

    def base_plan(self) -> str:
        return (REPO / "test/fixtures/failure-modes/R01-verdict-echo/good/doc/features"
                / "REQ-DEMO/AR/story-src/story-template.md").read_text(encoding="utf-8")


class ReviewTaskReachesTheVerifier(ReviewTaskReachesTheVerifierCase):
    def test_an_open_choice_is_judged_against_the_current_objects(self) -> None:
        """仍开着的选择对着本次 Story、Review 与关联蓝图判，结论写进原生报告的「审查方法」；零 Spec 时不要求读它。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [{
            "id": "D1", "status": "open", "title": "超时由谁释放", "decider": "需求负责人",
            "clarification": "**要定的事**：超时由谁释放。"}]}, ensure_ascii=False), encoding="utf-8")
        task = self.inject()
        section = task.split("### 仍开着的选择", 1)[1].split("\n### ", 1)[0]
        self.assertIn("「审查方法」", section)
        self.assertIn("关联蓝图", section)
        for gone in ("Spec", "acceptance.yaml", "证据格"):
            self.assertNotIn(gone, section, f"开着的选择还要对着「{gone}」判")
        self.assertIn("上游（系统设计）里没有图。", task)
        self.assertNotIn("spec）里没有图", task)

    def test_the_task_carries_its_criteria(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text)
        self.assertIn("### 判据", text)

    def test_the_spec_phase_no_longer_carries_the_story_review(self) -> None:
        """Story 的判据只在自己的位置：spec 阶段的审查任务里不再有它。"""
        self.assertNotIn("story_reader_review", self.spec_phase_fragments())

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

    def test_the_task_really_carries_the_method(self) -> None:
        """正常路径的证据：审查者手上的任务里有这份方法——判据原文随任务送达。"""
        task = self.inject()
        for needle in ("跨章对着读", "blocking_findings", "advisories", "不许空", "按实际关系判"):
            self.assertIn(needle, task, f"审查任务里没有「{needle}」")


class ReviewTaskReachesTheVerifierPart2(ReviewTaskReachesTheVerifierCase):
    def test_the_method_is_maintained_only_in_the_rules(self) -> None:
        """方法一份：`story-reader-rules.yaml` 维护「怎么判」，构造器运行时读它、代码里不另写一份。

        两处各写一遍时改一处另一处静默过期——而过期的那一份仍会被送到审查者手上。
        """
        method = self.overlay_method()
        for needle in ("总览与局部加起来", "端到端过程", "分支去向", "理由成不成立",
                       "跨章对着读", "blocking_findings", "advisories", "不许空"):
            self.assertIn(needle, method, f"判据里没有「{needle}」")
        source = (self.root / "doc/extensions/hooks/shared/reader-review-task.mjs").read_text(encoding="utf-8")
        for needle in ("总览与局部加起来", "端到端过程", "跨章对着读"):
            self.assertNotIn(needle, source, f"构造器又复制了一份方法：{needle}")
        spec = (self.root / "doc/extensions/rules/spec-rules.overlay.yaml").read_text(encoding="utf-8")
        self.assertNotIn("story_reader_review:", spec, "spec overlay 里还有一份 Story 判据")

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
        """AC22：审查任务片段不含机器区内容，机器区内容变了片段不变；审查对象按原始字节算，机器区内容变了对象跟着变，
        幂等重投（字节不变）对象不变；作者区改了，片段与对象都变。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        zone = ("\n<!-- story-build:begin 技术契约·端云接口 · 由蓝图 contracts（bp-RT90001 r3）生成，改它请改真源 · sha256:0000000000000000 -->\n"
                "| 接口 | 用途 |\n|---|---|\n| queryState | 查状态 |\n<!-- story-build:end -->\n")
        story.write_text(STORY_MD + zone, encoding="utf-8")
        first, key = self.inject(), self.material_key()
        self.assertNotIn("queryState", first, "机器区内容进了审查片段")
        story.write_text(STORY_MD + zone, encoding="utf-8")
        self.assertEqual(key, self.material_key(), "幂等重投换了审查对象")
        story.write_text(STORY_MD + zone.replace("queryState | 查状态", "queryState | 查处理状态"), encoding="utf-8")
        self.assertEqual(first, self.inject(), "机器区内容改了，任务片段跟着变")
        self.assertNotEqual(key, self.material_key(), "机器区内容变了，审查对象却没变")
        story.write_text(STORY_MD + "\n作者补的一句。\n" + zone, encoding="utf-8")
        self.assertNotEqual(first, self.inject(), "作者区改了，任务片段没跟着变")

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

    def test_the_task_says_the_extract_is_a_derived_analysis(self) -> None:
        """提取稿是派生分析：回查上游原话看 RR、SR 与 AR/design.md 原文，不拿提取稿自证。"""
        task = self.inject()
        self.assertIn("派生分析", task)
        self.assertNotIn(".backups/local/", task, "上游 AR 不再被覆盖，没有备份位置可指")

    def test_the_task_carries_the_recheck_list(self) -> None:
        """审查拿到的回看清单与作者手里的是同一张：逐条核去向，不另编一份。"""
        task = self.inject()
        self.assertIn("### 回看清单", task)
        self.assertIn("这句话材料里有吗", task.split("### 回看清单", 1)[1])
        method = self.overlay_method()
        for needle in ("回看清单逐条核去向", "撞点", "算没写依据"):
            self.assertIn(needle, method, f"overlay 的审查提示里没有「{needle}」")


class ReviewTaskReachesTheVerifierPart3(ReviewTaskReachesTheVerifierCase):
    def test_the_task_carries_the_contract_questions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        text = self.inject()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["questions"][0], text,
                          f"「{chapter['title']}」的读者问题没送到")

    def test_the_output_contract_lives_with_the_method(self) -> None:
        """结论写成原生 review 报告：阻断与建议各进问题清单的哪几级、证据写在哪、没有问题怎么写，与方法同处一份。

        输出要求与判据分在两个文件时，改一处就对不上；任务书的「报告怎么写」给章节与表头。
        """
        method = self.overlay_method()
        for needle in ("原生 review 报告", "不许空", "blocking_findings", "advisories", "问题清单", "无问题。"):
            self.assertIn(needle, method)
        for gone in ("汇总表", "YAML 明细", "为标记的一块"):
            self.assertNotIn(gone, method, f"旧的输出契约「{gone}」还在")
        task = self.inject()
        for needle in ("### 报告怎么写", "`编号 | 严重程度 | 分类 | 问题描述 | 涉及文件 | 修复建议`", "**审查结论**"):
            self.assertIn(needle, task)

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
        self.assertNotIn("spec/spec.md", section, "Story 不再以 Spec 为成文来源")
        self.assertNotIn("读不到 `SR/design.md`", section, "本地单没有系统设计是正常的")
        (feature / "AR" / "detail.json").write_text("{}", encoding="utf-8")
        section = self.inject().split("### 原材料原文", 1)[1].split("###", 1)[0]
        self.assertNotIn("读不到 `SR/design.md`", section, "本地需求留着 detail.json 仍是本地需求")
        remote = f"AR{FEATURE}"
        shutil.copytree(feature, feature.parent / remote)
        section = self.inject(remote).split("### 原材料原文", 1)[1].split("###", 1)[0]
        self.assertIn("读不到 `SR/design.md`", section, "系统需求缺必备来源没点名")

    def test_the_rules_judge_against_sources_not_the_design(self) -> None:
        """先按原材料独立判断，再用设计定位作者的安排——设计不是审查标准；方法只在判据文件。"""
        method = self.overlay_method()
        for needle in ("先独立想清楚", "写作设计", "设计漏掉的不因此算不在范围", "写了理由不等于理由成立",
                       "还开着的决定被写成已定", "已准入蓝图", "正文提到过", "真实待决写清了边界",
                       "写明未验证与影响"):
            self.assertIn(needle, method, f"判据里没有「{needle}」")
        self.assertNotIn("acceptance.yaml", method, "Story 判据还指着 Spec 的验收文件")

    def test_the_task_does_not_mention_a_publisher(self) -> None:
        """报告由调用方原样写出，没有钩子代它发布——任务书里不该还有那一环。"""
        text = self.inject()
        self.assertNotIn("插件", text)



class TheTaskMovesOnlyWithTheAuthorsInput(unittest.TestCase):
    """U38：审查对象只随被审材料变化，报告与检查结果落盘不铸出新的审查对象。

    原生按请求目标的原始字节给审查对象寻址。报告目录在对象之外：审过、检查过之后重新准备，
    材料键与原生 request_sha256 都不变；作者改了被审材料，两者都跟着变（09-26 实跑同一份材料审了又审 20 次）。
    """

    FIXTURE = TheStoryIsReviewedRegisteredAndDelivered.FIXTURE
    setUp = TheStoryIsReviewedRegisteredAndDelivered.setUp
    run_node = TheStoryIsReviewedRegisteredAndDelivered.run_node
    review = TheStoryIsReviewedRegisteredAndDelivered.review
    result = TheStoryIsReviewedRegisteredAndDelivered.result

    def prepared(self) -> dict:
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        return json.loads((self.flow_path.parent / "review" / "prepared.json").read_text(encoding="utf-8"))

    def test_a_report_and_its_check_leave_the_object_unchanged(self) -> None:
        first = self.prepared()
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual("pass", self.result()["result"])
        self.assertTrue((self.root / first["report_dir"] / "summary.json").is_file(), "原生检查没有落结果")
        again = self.prepared()
        self.assertEqual((first["material_key"], first["request_sha256"]), (again["material_key"], again["request_sha256"]),
                         "报告与检查结果落盘换了审查对象")

    def test_the_authors_input_still_moves_the_object(self) -> None:
        first = self.prepared()
        decisions = self.flow_path.parent / "decisions.json"
        data = json.loads(decisions.read_text(encoding="utf-8"))
        decisions.write_text(json.dumps({**data, "no_pending": "作者改了理由"}, ensure_ascii=False), encoding="utf-8")
        again = self.prepared()
        self.assertNotEqual(first["material_key"], again["material_key"], "决策登记改了，审查对象没变")
        self.assertNotEqual(first["request_sha256"], again["request_sha256"])


if __name__ == "__main__":
    unittest.main()
