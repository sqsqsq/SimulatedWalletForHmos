"""交付门拦不拦得住、读者审查的任务送不送得到。

## 审查、登记与交付门

审查用 Story 专属报告：准备时定稿、算材料键，审查者的回复原样存下，按报告合同只读核对后归类。
登记只读核对，审查结果可消费才写新依据，失败保留旧依据；`check --deliver` 核的是**登记过、审过的那一份**，
登记之后蓝图、输入、知识或被审文件变了就拦下；通过之后给出一次交付选择（本地单没有送审）。

## 送达与任务定义

判据没进审查者的任务清单，或者任务里没有一条问「材料登记的每张图用了没有」，
审查那一步就没有对象。这两道也在这一份里锚住。
"""
import json
import re
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
    """一条真实的正常链：定稿并准备审查 → 审查者回复 → 按报告合同核对 → 登记 → 交付门。

    审查者是夹具（按 Story 报告合同写回复），只验证协议接得上；真实的独立执行与业务效果在 CLI 里核。
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

    def prepare(self) -> dict:
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        return json.loads([line for line in out.stdout.splitlines() if line.startswith("{")][-1])

    def reviewed(self, kind: str = "pass") -> Path:
        prepared = self.review("prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        return design_kit.write_review(self.root, "REQ-DEMO", kind)

    def flow(self) -> dict:
        return json.loads(self.flow_path.read_text(encoding="utf-8"))

    def prepared(self) -> dict:
        return json.loads((self.flow_path.parent / "review" / "prepared.json").read_text(encoding="utf-8"))

    def tree(self) -> dict:
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in (self.root / "doc").rglob("*") if p.is_file()}

    def restored(self, kind: str) -> tuple[Path, dict, dict]:
        """材料 A 有了回复 → 改成 B 并准备 → 恢复 A 的原始字节再准备。返回 A 的回复、第二次准备 A 的输出、check 的结果。"""
        original = self.reviewed(kind)
        a = self.story.read_bytes()
        self.story.write_bytes(a + "\n改成 B 的一句。\n".encode("utf-8"))
        self.assertEqual(0, self.review("prepare").returncode)
        self.story.write_bytes(a)
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        prepared = json.loads([line for line in out.stdout.splitlines() if line.startswith("{")][-1])
        return original, prepared, self.result()

    def blueprint_path(self) -> str:
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        return next(part for part in task.split("`") if part.endswith("component-blueprint.yaml"))

    def unreviewed(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["python", str(self.FLOW), "unreviewed", "--feature", "REQ-DEMO", "--project-root", str(self.root),
                               *extra], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def authorize(self) -> subprocess.CompletedProcess:
        return self.unreviewed("--reason", "宿主没有可派的审查子代理", "--reply", "这版先不审，直接交")


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
        """任务列出 Story、Review 与对照材料；审查通过之后登记，交付门放行并按授权问交付选择。"""
        original = self.reviewed("pass")
        kept = original.read_bytes()
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        for need in ("doc/features/REQ-DEMO/AR/story.md", "doc/features/REQ-DEMO/AR/review.md",
                     "doc/extensions/rules/story-reader-rules.yaml"):
            self.assertIn(f"`{need}`", task)
        self.assertIn("/AR/story-src/inputs/", task, "冻结输入没进审查对象")
        self.assertIn("component-blueprint.yaml", task, "蓝图没进审查对象")
        self.assertNotIn(self.prepared()["material_key"], task, "任务里嵌了由它自己算出的材料键")
        self.assertEqual("pass", self.result()["result"])
        registered = self.register()
        self.assertEqual(0, registered.returncode, registered.stdout + registered.stderr)
        self.assertEqual("story_written", self.flow()["status"])
        self.assertIn("AR/review.md", self.flow()["story_basis"]["files"])
        out = self.check("--deliver")
        text = out.stdout + out.stderr
        self.assertEqual(0, out.returncode, text)
        for choice in ("完整设计交接", "实现方案", "完整实现", "暂不推进"):
            self.assertIn(choice, text)
        self.assertIn("已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择", text, "交付门输出仍是无条件问人")
        self.assertIn("止于 Plan、不进入 Coding", text)
        self.assertIn("phases/design.md「五、独立审查、登记与交付」第 6 步", text, "交付选项没指向执行方法")
        method = (DEV_EXT / "skills/story/phases/design.md").read_text(encoding="utf-8").split("6. **交付选择**", 1)[1]
        self.assertIn("--requested-phases spec,plan", method, "实现方案没把 Plan 上限交给范围准备")
        self.assertNotIn("/story archive", text, "本地单没有送审")
        self.assertEqual(kept, original.read_bytes(), "核对、登记或交付门改了审查者的原回复")
        again = json.loads([l for l in self.register().stdout.splitlines() if l.startswith("{")][-1])
        self.assertFalse(again["registered"], "同一份对象重复登记换了身份")


class TheStoryIsReviewedRegisteredAndDeliveredPart2(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_advisories_on_markdown_are_delivered_with_the_story(self) -> None:
        """只指向 Markdown 的非阻断发现：报告可读、判 warn，登记并带建议交付，不需要无关引用。"""
        self.reviewed("advice")
        result = self.result()
        self.assertEqual("warn", result["result"], result)
        self.assertEqual(0, self.register().returncode)
        out = self.check("--deliver")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn("F-1", out.stdout)

    def test_a_reply_out_of_the_report_format_is_kept_and_not_registered(self) -> None:
        """审查者的回复不合报告合同：判 report_invalid，原回复一字不改地留着，不登记。"""
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
        revision = self.blueprint_revision()
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "本需求没有任何上报动作", "本需求只在提交时上报一次")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn(f"登记之后蓝图内容变了（版本仍是 r{revision}，内容摘要 ", out.stdout + out.stderr)

    def test_a_new_blueprint_revision_is_named_as_such(self) -> None:
        """换了 revision 报换版；只改内容不换版报内容变了——提示说的是实际变的那一类。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        revision = self.blueprint_revision()
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS,
                                    f"\nrevision: {revision}\n", f"\nrevision: {revision + 1}\n")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn(f"登记之后蓝图换了版本（登记时 r{revision}，现在 r{revision + 1}）", out.stdout + out.stderr)

    def blueprint_revision(self) -> int:
        """需求关联的蓝图现在的 revision。"""
        blueprint = design_kit.blueprint_of(self.root, "REQ-DEMO")
        text = (self.root / design_kit.features_dir(self.root) / blueprint / "blueprint"
                / "component-blueprint.yaml").read_text(encoding="utf-8")
        return int(re.search(r"^revision: (\d+)$", text, re.M).group(1))

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


class TheReportIsCheckedReadOnly(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """报告按合同只读核对：显式 check 与交付门共用一份判定，同材料通过复用，重新派审的新报告不因不是第一份被拒。"""

    def test_checking_writes_nothing(self) -> None:
        self.reviewed("pass")
        before = self.tree()
        self.assertEqual("pass", self.result()["result"])
        self.assertEqual(before, self.tree(), "核对写了盘")

    def test_the_same_material_reuses_its_passed_report(self) -> None:
        original = self.reviewed("pass")
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        again = json.loads([line for line in out.stdout.splitlines() if line.startswith("{")][-1])
        self.assertTrue(again["reused"])
        self.assertEqual(original, self.root / again["report_file"])

class TheReportIsCheckedReadOnlyPart2(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """材料改走又改回来：通过的回复复用，阻断的保持；不通过之后的新回复按它自己判。"""

    def test_a_restored_material_reuses_its_passing_report(self) -> None:
        """A→B→A：A 目录里的 pass 由 prepare 复用（reused、原回复），check 读的是同一份。"""
        original, prepared, result = self.restored("pass")
        self.assertTrue(prepared["reused"], prepared)
        self.assertEqual(original, self.root / prepared["report_file"])
        self.assertEqual(("pass", prepared["report_file"]), (result["result"], result["report_file"]))

    def test_a_restored_material_reuses_its_advisory_report(self) -> None:
        original, prepared, result = self.restored("advice")
        self.assertTrue(prepared["reused"], prepared)
        self.assertEqual(("warn", prepared["report_file"]), (result["result"], result["report_file"]))

    def test_a_restored_material_keeps_its_blocker(self) -> None:
        """A→B→A：A 的 fail 不被复用成通过；prepare 另起回复位置，check 仍是 fail，之后在原目录复审可更新。"""
        original, prepared, result = self.restored("block")
        self.assertFalse(prepared["reused"], prepared)
        self.assertNotEqual(original, self.root / prepared["report_file"])
        self.assertEqual("fail", result["result"])
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual("pass", self.result()["result"])

    def test_a_new_reply_after_a_failing_one_is_judged_on_its_own(self) -> None:
        first = self.reviewed("block")
        self.assertEqual("fail", self.result()["result"])
        second = self.reviewed("pass")
        self.assertNotEqual(first, second, "不通过之后重新派审没有另起一份")
        self.assertTrue(first.is_file(), "旧回复没保留")
        self.assertEqual("pass", self.result()["result"])

class TheReportIsCheckedReadOnlyPart3(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """报告合同：信不过的回复不计结论，材料位置按引用边界取完整路径。"""

    def test_the_contract_refuses_what_it_cannot_trust(self) -> None:
        story = "doc/features/REQ-DEMO/AR/story.md"
        cases = {
            "材料位置不是审查材料": ("advice", lambda t: t.replace(f"`{story}`", "`doc/other/notes.md`"), "report_invalid"),
            "结论与发现矛盾": ("major", lambda t: t.replace("fail：", "pass："), "report_invalid"),
            "标题只是含「结论」": ("pass", lambda t: t.replace("## 总体结论", "## 总体结论与建议"), "report_invalid"),
            "材料键不是这一份": ("pass", lambda t: t.replace(self.prepared()["material_key"], "0" * 64), "subject_stale"),
            "引用 YAML 材料": ("advice", lambda t: t.replace(f"`{story}`", f"`{self.blueprint_path()}`"), "warn"),
            "带章节定位的真实路径": ("advice", lambda t: t.replace(f"`{story}`", f"`{story}#背景`"), "warn"),
            "引用不存在的副本": ("advice", lambda t: t.replace(f"`{story}`", f"`{story}.bak`"), "report_invalid"),
            "发现表缺分隔行，MAJOR 不能被当成分隔行丢掉": ("major", lambda t: t.replace("|---|---|---|---|---|---|\n", "")
                                                 .replace("| story_reader_review | fail |", "| story_reader_review | pass |")
                                                 .replace("fail：", "pass："), "report_invalid"),
            "发现行少一列": ("advice", lambda t: t.replace(" 作者把依据移到结论之前 |", ""), "report_invalid"),
            "总体结论不在第一行": ("pass", lambda t: t.replace("pass：按判据与发现判定。", "说明见下。\npass：按判据与发现判定。"),
                          "report_invalid"),
        }
        for label, (kind, mutate, want) in cases.items():
            with self.subTest(case=label):
                original = self.reviewed(kind)
                original.write_text(mutate(original.read_text(encoding="utf-8")), encoding="utf-8")
                self.assertEqual(want, self.result()["result"])

    def test_locations_keep_their_quoting(self) -> None:
        """材料位置按引用边界取完整路径：整格一条路径可含空格，多条或夹说明时逐条反引号；取完再去定位片段。"""
        meeting = self.flow_path.parent / "meetings" / "中性 会议" / "v1" / "raw.md"
        meeting.parent.mkdir(parents=True)
        meeting.write_text("主持人：先看续期。\n", encoding="utf-8")
        story = "doc/features/REQ-DEMO/AR/story.md"
        raw = "doc/features/REQ-DEMO/AR/story-src/meetings/中性 会议/v1/raw.md"
        cases = {
            "整格一条含空格的路径": (f"{raw}#续期", "warn"),
            "反引号括住含空格的路径与行号": (f"`{raw}:1`", "warn"),
            "两条路径夹说明": (f"`{story}#背景` 与会议原话 `{raw}`", "warn"),
            "含空格但不存在的路径": (f"`doc/features/REQ-DEMO/AR/story-src/meetings/中性 会议/v2/raw.md`", "report_invalid"),
            "多条路径没逐条括起": (f"{story} {raw}", "report_invalid"),
        }
        for label, (where, want) in cases.items():
            with self.subTest(case=label):
                original = self.reviewed("advice")
                original.write_text(original.read_text(encoding="utf-8").replace(f"`{story}`", where), encoding="utf-8")
                self.assertEqual(want, self.result()["result"], self.result())


class TheDispatchCarriesTheReviewIdentity(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """派审载体：prepare 把完整材料键、任务与回复位置写进 dispatch.md，返修与复审的上下文也在里面；check 核它与准备记录一致。"""

    def dispatch_file(self) -> Path:
        return self.flow_path.parent / "review" / "dispatch.md"

    def test_the_dispatch_carries_the_full_identity_and_is_checked(self) -> None:
        out = self.prepare()
        text = self.dispatch_file().read_text(encoding="utf-8")
        self.assertEqual(text, out["dispatch_text"])
        for needle in (out["material_key"], out["task"], out["report_file"]):
            self.assertIn(needle, text)
        self.assertEqual(64, len(out["material_key"]))
        self.dispatch_file().write_text(text.replace(out["material_key"], out["material_key"][:16]), encoding="utf-8")
        self.assertEqual("input_invalid", self.result()["result"], "改过的派审载体没被认出来")
        self.dispatch_file().unlink()
        self.assertEqual("input_invalid", self.result()["result"], "缺派审载体没被认出来")
        again = self.prepare()
        self.assertEqual(out["report_file"], again["report_file"], "同一份材料再准备，空回复位置又递增了")
        self.assertEqual("report_missing", self.result()["result"])

    def test_a_bad_reply_goes_back_to_an_isolated_reviewer_with_its_diagnosis(self) -> None:
        first = self.reviewed("pass")
        first.write_text("看过了，整体还行。\n", encoding="utf-8")
        kept = first.read_bytes()
        diagnosis = self.result()
        self.assertEqual("report_invalid", diagnosis["result"])
        out = self.prepare()
        self.assertNotEqual(first, self.root / out["report_file"], "坏回复的位置被拿来写新回复")
        context = self.prepared()["review_context"]
        self.assertEqual(("format_repair", first.relative_to(self.root).as_posix()), (context["kind"], context["report_file"]))
        self.assertEqual(diagnosis["detail"], context["diagnostic"]["detail"])
        self.assertIn(diagnosis["detail"].splitlines()[0], out["dispatch_text"], "诊断没原样进派审载体")
        self.assertIn(context["report_sha256"], out["dispatch_text"])
        again = self.prepare()
        self.assertEqual(out["report_file"], again["report_file"], "同一次返修再准备，回复位置递增了")
        self.assertEqual(context, self.prepared()["review_context"], "再准备丢了返修上下文")
        self.assertEqual(kept, first.read_bytes(), "原回复被改了")
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual("pass", self.result()["result"])
        first.write_text("改过的原回复\n", encoding="utf-8")
        self.assertEqual("input_invalid", self.result()["result"], "派审带着的原回复被改，没被认出来")

    def test_an_altered_original_leads_to_a_fresh_independent_review(self) -> None:
        """格式返修带出去的原回复被改成一份「通过」：check 报 input_invalid；重新 prepare 改为对当前材料的完整独立审查，
        位置不变、改过的那份留作现场且不被读出结论；新回复到了才可消费。"""
        first = self.reviewed("pass")
        first.write_text("看过了，整体还行。\n", encoding="utf-8")
        kept = first.read_bytes()
        out = self.prepare()
        pending = self.root / out["report_file"]
        passing = design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual(pending, passing)
        forged = passing.read_bytes()
        passing.unlink()
        first.write_bytes(forged)
        self.assertEqual("input_invalid", self.result()["result"])
        again = self.prepare()
        self.assertEqual(out["report_file"], again["report_file"], "换了回复位置")
        self.assertFalse(again["reused"], "改过的原回复被当成通过复用了")
        context = self.prepared()["review_context"]
        self.assertEqual(("fresh_review", first.relative_to(self.root).as_posix()),
                         (context["kind"], context["damaged"]["report_file"]))
        self.assertIn("原件已被改动", again["dispatch_text"])
        self.assertEqual("report_missing", self.result()["result"], "新回复没到，却借改过的历史放行了")
        self.assertEqual(forged, first.read_bytes(), "现场被改了")
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual("pass", self.result()["result"])
        first.write_bytes(kept)
        self.assertEqual("pass", self.result()["result"], "原件恢复之后正常审查结果反而不可消费")

    def test_a_failed_review_is_rechecked_with_its_report(self) -> None:
        failed = self.reviewed("block")
        out = self.prepare()
        context = self.prepared()["review_context"]
        self.assertEqual(("recheck", failed.relative_to(self.root).as_posix()), (context["kind"], context["report_file"]))
        self.assertIn("F-1", out["dispatch_text"], "失败报告的阻断结论没进派审载体")
        self.assertEqual("fail", self.result()["result"], "新位置还空着，原有效 fail 被撤销")


class ChangedMaterialCarriesThePriorReport(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """材料换了新键：紧前一次准备的原报告随派审交出作待核参考，结论只对新材料；前一份缺席或改过就完整审查，不往更早找。"""

    def change(self, line: str) -> None:
        self.story.write_text(self.story.read_text(encoding="utf-8") + f"\n{line}\n", encoding="utf-8")

    def reference_only(self, kind: str) -> None:
        old = self.reviewed(kind)
        old_key, kept = self.prepared()["material_key"], old.read_bytes()
        self.change("换成新材料的一句。")
        out = self.prepare()
        context = self.prepared()["review_context"]
        self.assertEqual(("prior_revision", old_key, old.relative_to(self.root).as_posix()),
                         (context["kind"], context["material_key"], context["report_file"]))
        self.assertEqual(context["report_sha256"], self.prepared()["originals"][context["report_file"]])
        self.assertNotEqual(old, self.root / out["report_file"], "新材料的回复写回了旧报告")
        self.assertFalse(out["reused"], "旧材料的结论被当成新材料的结论")
        self.assertEqual("report_missing", self.result()["result"], "新材料继承了旧材料的结论")
        for needle in (old.relative_to(self.root).as_posix(), old_key, "只作参考", out["material_key"]):
            self.assertIn(needle, out["dispatch_text"])
        again = self.prepare()
        self.assertEqual((out["report_file"], context), (again["report_file"], self.prepared()["review_context"]),
                         "同一份新材料再准备，位置或参考变了")
        self.assertEqual(kept, old.read_bytes(), "旧原报告被改了")
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        self.assertEqual("pass", self.result()["result"])

    def test_a_passed_report_is_a_reference_not_a_pass(self) -> None:
        self.reference_only("pass")

    def test_a_failed_report_is_a_reference_not_a_fail(self) -> None:
        self.reference_only("block")

    def test_an_altered_reference_is_caught_and_replaced_by_a_full_review(self) -> None:
        old = self.reviewed("advice")
        self.change("换成新材料的一句。")
        out = self.prepare()
        old.write_text(old.read_text(encoding="utf-8").replace("MINOR", "INFO"), encoding="utf-8")
        self.assertEqual("input_invalid", self.result()["result"], "派审带出的旧报告被改，没被认出来")
        again = self.prepare()
        self.assertEqual(out["report_file"], again["report_file"])
        context = self.prepared()["review_context"]
        self.assertEqual(("fresh_review", old.relative_to(self.root).as_posix()),
                         (context["kind"], context["damaged"]["report_file"]))
        self.assertEqual("report_missing", self.result()["result"])

    def test_without_a_trustworthy_prior_report_the_review_is_complete(self) -> None:
        """A 没有回复转 B；B 还没回复又转 C：都完整审查，不追溯更早的那一份。"""
        self.prepare()
        self.change("B 的一句。")
        b = self.prepare()
        self.assertNotIn("review_context", self.prepared(), "前一份回复不在，却带了参考")
        self.assertIn("没有可信的前轮审查报告", b["dispatch_text"])
        self.reviewed("pass")
        self.change("C 的一句。")
        self.prepare()
        self.change("D 的一句。")
        d = self.prepare()
        self.assertNotIn("review_context", self.prepared(), "C 还没回复，D 却追溯了 B 的报告")
        self.assertIn("没有可信的前轮审查报告", d["dispatch_text"])

    def test_a_failure_of_the_current_material_wins_over_a_later_reference(self) -> None:
        """A 失败 → B → 回到 A：A 的 fail 优先，按复审交出，不被 B 的参考盖掉。"""
        failed = self.reviewed("block")
        a = self.story.read_bytes()
        self.change("B 的一句。")
        self.prepare()
        self.assertEqual("prior_revision", self.prepared()["review_context"]["kind"])
        self.story.write_bytes(a)
        self.prepare()
        context = self.prepared()["review_context"]
        self.assertEqual(("recheck", failed.relative_to(self.root).as_posix()), (context["kind"], context["report_file"]))
        self.assertEqual("fail", self.result()["result"])


class ABrokenPreparationRecordIsAnInputFault(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """准备记录在却读不出：prepare 在定稿写盘之前报错退出、现场不动；check 判 input_invalid。不当作首次，不换默认目录。"""

    def test_a_broken_record_stops_before_anything_is_written(self) -> None:
        self.reviewed("block")
        record = self.flow_path.parent / "review" / "prepared.json"
        good = record.read_bytes()
        broken = {"坏 JSON": b"{\"material_key\": ", "缺字段": json.dumps({"material_key": "0" * 64}).encode("utf-8"),
                  "不是对象": b"[]"}
        for label, data in broken.items():
            with self.subTest(case=label):
                record.write_bytes(data)
                before = self.tree()
                out = self.review("prepare")
                self.assertNotEqual(0, out.returncode, label)
                self.assertIn("review/prepared.json", out.stderr)
                self.assertEqual(before, self.tree(), "坏准备记录之下 prepare 仍写了盘")
                result = self.review("check")
                self.assertEqual(1, result.returncode)
                self.assertEqual("input_invalid", json.loads(result.stdout.strip().splitlines()[-1])["result"])
        record.write_bytes(good)
        self.assertEqual("fail", self.result()["result"], "恢复原记录后，原 fail 不见了")


class TheDesignAttachmentIsTheNativeProjection(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """设计附件 AR/design-review.md：定稿时从原生评审投影逐字节复制，是被审、被登记的一件；手改不盖，蓝图换版照常重写。"""

    def attachment(self) -> Path:
        return self.story.parent / "design-review.md"

    def projection(self) -> Path:
        return self.root / "doc" / "features" / design_kit.blueprint_of(self.root, "REQ-DEMO") / "blueprint" / "component-blueprint.review.md"

    def test_prepare_copies_the_projection_byte_for_byte_and_reviews_it(self) -> None:
        self.reviewed("pass")
        self.assertEqual(self.projection().read_bytes(), self.attachment().read_bytes())
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        self.assertIn("doc/features/REQ-DEMO/AR/design-review.md`", task, "设计附件不在审查材料里")
        self.assertEqual(0, self.register().returncode)
        self.assertEqual(0, self.check("--deliver").returncode)

    def reading(self) -> str:
        """现在这份材料的审查任务里「怎么读」一节。"""
        module = DEV_EXT / "hooks/shared/reader-review-task.mjs"
        r = subprocess.run(
            ["node", "--input-type=module", "-e",
             "const m = await import(process.argv[1]); process.stdout.write(m.readerReviewTask(process.argv[2], 'REQ-DEMO'));",
             module.resolve().as_uri(), str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout.split("### 怎么读", 1)[1].split("\n### ", 1)[0]

    def test_the_identical_projection_is_read_once(self) -> None:
        """附件与原生投影同字节：读法写明两处是同一份、完整读附件一次；字节不同就两处都读。"""
        self.assertEqual(0, self.review("prepare").returncode)
        projection = self.projection().relative_to(self.root).as_posix()
        self.assertIn(f"`{projection}` 字节相同，完整读设计附件一次即可", self.reading())
        self.attachment().write_bytes(self.attachment().read_bytes() + "手加的一行。\n".encode("utf-8"))
        reading = self.reading()
        self.assertIn("蓝图与它的原生评审投影", reading)
        self.assertNotIn("字节相同", reading)

    def test_a_hand_edit_is_kept_and_stops_the_prepare(self) -> None:
        self.assertEqual(0, self.review("prepare").returncode)
        edited = self.attachment().read_bytes() + "手加的一行。\n".encode("utf-8")
        self.attachment().write_bytes(edited)
        out = self.review("prepare")
        self.assertNotEqual(0, out.returncode, "被改过的设计附件被静默覆盖")
        self.assertIn("被改过", out.stdout + out.stderr)
        self.assertEqual(edited, self.attachment().read_bytes())

    def test_a_revised_blueprint_rewrites_it_and_the_old_registration_is_not_delivered(self) -> None:
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "target_state: refresh trigger",
                                    "target_state: refresh trigger and badge")
        self.assertNotEqual(0, self.check("--deliver").returncode, "蓝图换版之后旧附件仍被交付")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(self.projection().read_bytes(), self.attachment().read_bytes(), "蓝图换版之后附件没跟着重写")


class AnUnreviewedDeliveryNeedsAHuman(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """当前 adapter 没声明审查子代理、这一版的结果是 report_missing 时，人明确授权才可不经审查交付；
    授权记在流程契约，审查状态写进最终的 Story 与 Review，材料一变就不再适用。"""

    def test_the_authorization_is_recorded_and_disclosed_in_both_documents(self) -> None:
        self.assertNotEqual(0, self.authorize().returncode, "没定稿就记了授权")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertNotEqual(0, self.unreviewed("--reason", "宿主没有可派的审查子代理").returncode, "没有人的原话也记了授权")
        recorded = self.authorize()
        self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
        self.assertEqual("human", self.flow()["review_waiver"]["by"])
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("unreviewed", self.result()["result"])
        story = self.story.read_text(encoding="utf-8")
        chapter = story.split("## 9.", 1)[1].split("\n## ", 1)[0]
        self.assertIn("本版未经独立审查", chapter, "Story 交付章没有审查状态")
        self.assertIn("这版先不审，直接交", chapter)
        review = (self.story.parent / "review.md").read_text(encoding="utf-8")
        head = review.split("\n## ", 1)[0]
        self.assertIn("本版未经独立审查", head, "Review 题头之后、议题之前没有审查状态")
        before = self.tree()
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(before, {k: v for k, v in self.tree().items()}, "同样的输入重跑准备改了字节")
        self.assertEqual("unreviewed", self.result()["result"])
        self.assertEqual(0, self.register().returncode)
        out = self.check("--deliver")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn("本版未经独立审查", out.stdout)

    def test_a_crlf_story_gets_one_disclosure(self) -> None:
        """以 CRLF 交来的 Story：披露写进交付章一次，重跑准备字节不变。"""
        self.story.write_bytes(self.story.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(0, self.authorize().returncode)
        self.assertEqual(0, self.review("prepare").returncode)
        first = self.story.read_bytes()
        self.assertEqual(1, first.decode("utf-8").count("本版未经独立审查"))
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(first, self.story.read_bytes(), "重跑准备改了 Story 的字节")
        self.assertEqual("unreviewed", self.result()["result"])

    def test_a_host_that_can_review_is_not_waived(self) -> None:
        (self.root / "framework.local.json").write_text('{"schema_version": "1.0", "agent_adapter": "opencode"}',
                                                         encoding="utf-8")
        self.assertEqual(0, self.review("prepare").returncode)
        refused = self.authorize()
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("声明能派独立审查子代理", refused.stdout + refused.stderr)

    def test_a_failing_review_is_not_turned_into_an_unreviewed_delivery(self) -> None:
        self.reviewed("block")
        self.assertEqual("fail", self.result()["result"])
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("fail", self.result()["result"], "重新准备撤销了同一份材料的已知阻断")
        refused = self.authorize()
        self.assertNotEqual(0, refused.returncode, "已有不通过的结论还记了未审查授权")
        self.assertNotIn("review_waiver", self.flow())

class AnUnreviewedDeliveryNeedsAHumanPart2(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """未审查授权与报告目录、材料变化：同一份材料换目录不消掉阻断，材料一变授权就不再适用。"""

    def test_another_report_dir_keeps_the_known_blocker(self) -> None:
        """同一份材料的报告目录在首次准备时定下：另指目录报冲突、不改文件，已知的阻断仍在，也记不了未审查授权；
        原目录里真实复审的新报告照常更新结论。"""
        self.reviewed("block")
        self.assertEqual("fail", self.result()["result"])
        before = self.tree()
        moved = self.run_node("review", "--action", "prepare", "--report-dir", "doc/reports/alternate-neutral")
        self.assertNotEqual(0, moved.returncode)
        self.assertIn("报告目录冲突", moved.stdout + moved.stderr)
        self.assertEqual(before, self.tree(), "目录冲突的准备改了文件")
        self.assertEqual("fail", self.result()["result"])
        self.assertNotEqual(0, self.authorize().returncode, "换目录之后记上了未审查授权")
        self.assertNotIn("review_waiver", self.flow())
        self.reviewed("pass")
        self.assertEqual("pass", self.result()["result"], "原目录里的复审没更新结论")

    def test_a_chosen_report_dir_stays_with_its_material(self) -> None:
        """首次准备指定的目录随材料键沿用：之后不带参数准备仍写进它。"""
        first = self.run_node("review", "--action", "prepare", "--report-dir", "doc/reports/chosen")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual("doc/reports/chosen", self.prepared()["report_dir"])
        design_kit.write_review(self.root, "REQ-DEMO", "block")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("doc/reports/chosen", self.prepared()["report_dir"])
        self.assertEqual("fail", self.result()["result"])

    def test_a_changed_story_drops_the_authorization_and_a_real_review_takes_over(self) -> None:
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(0, self.authorize().returncode)
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("unreviewed", self.result()["result"])
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n登记前补的一句。\n", encoding="utf-8")
        self.assertEqual("subject_stale", self.result()["result"])
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("report_missing", self.result()["result"], "材料变了还沿用旧授权")
        self.assertNotIn("本版未经独立审查", self.story.read_text(encoding="utf-8"), "授权不适用了，披露还留在 Story 里")
        self.assertEqual(0, self.unreviewed("--withdraw").returncode)
        self.reviewed("pass")
        self.assertEqual("pass", self.result()["result"])


class ARequirementWithUiReferenceGoesThrough(unittest.TestCase):
    """带界面参考图的需求：需求目录保留 `ux-reference/`，蓝图在异名的工作区（`bp-<需求>`），
    冻结、蓝图消费、审查准备、登记与交付一路走通（审查者是夹具）。"""

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
        task = (self.root / "doc/features/REQ-DEMO/AR/story-src/review/task.md").read_text(encoding="utf-8")
        self.assertIn("/files/ux-reference/home.png`", task)
        self.assertIn("`doc/features/bp-REQ-DEMO/blueprint/component-blueprint.yaml`", task)
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
        """仍开着的选择对着本次 Story、Review 与关联蓝图判，结论写进报告的审查方法；零 Spec 时不要求读它。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [{
            "id": "D1", "status": "open", "title": "超时由谁释放", "decider": "需求负责人",
            "clarification": "**要定的事**：超时由谁释放。"}]}, ensure_ascii=False), encoding="utf-8")
        task = self.inject()
        section = task.split("### 仍开着的选择", 1)[1].split("\n### ", 1)[0]
        self.assertIn("「判据核对」表后的审查方法", section)
        self.assertIn("在「发现」表记一条", section)
        self.assertIn("关联蓝图", section)
        for gone in ("Spec", "acceptance.yaml", "证据格"):
            self.assertNotIn(gone, section, f"开着的选择还要对着「{gone}」判")
        self.assertIn("本需求还没有冻结的采用来源，没有来源图要对照。", task)
        self.assertNotIn("spec）里没有图", task)

    def test_the_task_carries_its_criteria(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text)
        self.assertIn("### 判据", text)

    def test_every_registered_criterion_is_sent_and_required(self) -> None:
        """判据文件登记几项，任务就发几项、报告就核几项：两边读的是同一份，不靠「现在只有一条」。"""
        rules = self.root / "doc/extensions/rules/story-reader-rules.yaml"
        rules.write_text(rules.read_text(encoding="utf-8").rstrip("\n") + "\n  neutral_second_criterion:\n"
                         "    description: 第二条中性判据的说明。\n    severity: MAJOR\n"
                         "    ai_prompt_hint: 第二条判据怎么审。\n", encoding="utf-8")
        text = self.inject()
        for needle in ("### 判据 story_reader_review（BLOCKER）", "### 判据 neutral_second_criterion（MAJOR）",
                       "第二条中性判据的说明。", "第二条判据怎么审。"):
            self.assertIn(needle, text)
        module = self.root / "doc/extensions/hooks/shared/reader-review-task.mjs"
        ids = subprocess.run(["node", "--input-type=module", "-e",
                              "const m = await import(process.argv[1]); process.stdout.write(JSON.stringify(m.readerCheckIds()));",
                              module.resolve().as_uri()], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(["story_reader_review", "neutral_second_criterion"], json.loads(ids.stdout))

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

    def test_the_number_and_source_semantics_reach_the_reviewer_once(self) -> None:
        """数值同值同义、比例分母、按条件不同的值、来源可回查、引文与残文：任务里各出现一次，规则不在构造器里另写。"""
        task = self.inject()
        for needle in ("换算要对得回原值与单位", "比例换了分母不算一致", "不同适用条件下的不同值不算冲突",
                       "回查不到的泛称不算来源", "模板残文", "数值换算错误或漂移改变了验收"):
            self.assertEqual(1, task.count(needle), f"审查任务里「{needle}」不是恰好一处")
        source = (self.root / "doc/extensions/hooks/shared/reader-review-task.mjs").read_text(encoding="utf-8")
        self.assertNotIn("比例换了分母", source, "构造器又复制了一份判据")

    def test_the_task_really_carries_the_method(self) -> None:
        """正常路径的证据：审查者手上的任务里有这份方法——判据原文随任务送达。"""
        task = self.inject()
        for needle in ("跨章对着读", "阻断发现", "**建议**", "不许空", "按实际关系判"):
            self.assertIn(needle, task, f"审查任务里没有「{needle}」")


class ALargeTaskKeepsEveryItem(ReviewTaskReachesTheVerifierCase):
    def test_many_images_choices_and_topics_are_all_listed_and_the_rules_once(self) -> None:
        """条目多时不丢项、不截断，判据仍只出现一次；普通材料不因数量变成逐条裁决表。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        images = [{"kind": "image", "paths": [f"assets/doc-{i}/p{i}.png"], "caption": f"页面{i}" + "说明" * (i % 5)}
                  for i in range(1, 13)]
        (src / "materials.json").write_text(json.dumps({"materials": images}, ensure_ascii=False), encoding="utf-8")
        choices = [{"id": f"D{i}", "status": "open", "title": f"中性议题{i}" + "很长的标题" * (i % 4),
                    "decider": "需求负责人", "clarification": f"**决策点**：第{i}件事。"} for i in range(1, 16)]
        (src / "decisions.json").write_text(json.dumps({"decisions": choices}, ensure_ascii=False), encoding="utf-8")
        raw = "\n".join(f"第{i}行原话。" for i in range(1, 61))
        (src / "meetings" / "评审会" / "abcdef12").mkdir(parents=True)
        (src / "meetings" / "评审会" / "abcdef12" / "raw.md").write_text(raw, encoding="utf-8")
        topics = [{"id": f"T{i}", "title": f"话题{i}", "finding": f"判断{i}",
                   "evidence": [{"start": i * 3 - 2, "end": i * 3}]} for i in range(1, 21)]
        (src / "meeting-notes.json").write_text(json.dumps({"meetings": [
            {"source": "评审会.md", "source_sha": "abcdef1234", "topics": topics}]}, ensure_ascii=False), encoding="utf-8")
        task = self.inject()
        for c in choices:
            self.assertEqual(1, task.count(f"#### {c['id']} {c['title']}\n"), c["id"])
        for tp in topics:
            self.assertEqual(1, task.count(f"#### 评审会@abcdef12/{tp['id']} {tp['title']}\n"), tp["id"])
        self.assertIn("第60行原话。", task, "最后一个话题的原话没带上")
        images_section = task.split("### 材料里的图", 1)[1].split("\n### ", 1)[0]
        for img in images:
            self.assertIn(img["paths"][0], images_section)
        self.assertEqual(1, task.count("### 判据 story_reader_review（BLOCKER）"))
        self.assertEqual(1, task.count("跨章对着读这几问"))


class ReviewTaskReachesTheVerifierPart2(ReviewTaskReachesTheVerifierCase):
    def test_the_method_is_maintained_only_in_the_rules(self) -> None:
        """方法一份：`story-reader-rules.yaml` 维护「怎么判」，构造器运行时读它、代码里不另写一份。

        两处各写一遍时改一处另一处静默过期——而过期的那一份仍会被送到审查者手上。
        """
        method = self.overlay_method()
        for needle in ("总览与局部加起来", "端到端过程", "分支去向", "理由成不成立",
                       "跨章对着读", "阻断发现", "**建议**", "不许空"):
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

    def test_the_task_is_one_index_and_embeds_no_document(self) -> None:
        """任务只给一份文件索引与读法，被审文件与写作设计都按索引去读，任务里不嵌它们的全文。"""
        self.plan_path().write_text(self.base_plan().replace("## 阅读主线\n\n", "## 阅读主线\n\n设计里独有的一句甲。\n"),
                                    encoding="utf-8")
        task = self.inject()
        self.assertIn("### 怎么读", task)
        index = task.split("### 本次审查的材料", 1)[1].split("\n### ", 1)[0]
        for rel in ("AR/story.md", "AR/story-src/story-template.md"):
            self.assertEqual(1, index.count(f"doc/features/{FEATURE}/{rel}`"), f"{rel} 在索引里不是恰好一次")
        self.assertNotIn("用户现在拿不到凭据。", task, "Story 正文又嵌进了任务")
        self.assertNotIn("设计里独有的一句甲。", task, "写作设计全文又嵌进了任务")
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        story.write_text(STORY_MD + "\n作者补的一句。\n", encoding="utf-8")
        self.assertEqual(task, self.inject(), "改正文的措辞改了任务——正文按索引去读")

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
        """结论写成 Story 报告：阻断与建议各进「发现」的哪几级、证据写在哪、没有发现怎么写，与方法同处一份。

        输出要求与判据分在两个文件时，改一处就对不上；任务书的「报告怎么写」给章节与表头。
        """
        method = self.overlay_method()
        for needle in ("Story 报告", "不许空", "阻断发现", "**建议**", "「发现」", "只留表头"):
            self.assertIn(needle, method)
        for gone in ("汇总表", "YAML 明细", "为标记的一块"):
            self.assertNotIn(gone, method, f"旧的输出契约「{gone}」还在")
        task = self.inject()
        for needle in ("### 报告怎么写", "`material_key:", "`判据 ID | 结果 | 依据`",
                       "`编号 | 严重程度 | 判据 ID | 材料位置 | 问题与依据 | 修正责任`"):
            self.assertIn(needle, task)

    def test_the_index_names_a_missing_required_source(self) -> None:
        """该有而读不到的来源在索引里点名：系统需求缺系统设计要说，本地需求没有它是正常的。"""
        feature = self.root / "doc" / "features" / FEATURE
        index = lambda name: self.inject(name).split("### 本次审查的材料", 1)[1].split("\n### ", 1)[0]  # noqa: E731
        self.assertNotIn("读不到 `SR/design.md`", index(FEATURE), "本地单没有系统设计是正常的")
        remote = f"AR{FEATURE}"
        shutil.copytree(feature, feature.parent / remote)
        self.assertIn("读不到 `SR/design.md`", index(remote), "系统需求缺必备来源没点名")

    def test_the_rules_judge_against_sources_not_the_design(self) -> None:
        """先按原材料独立判断，再用设计定位作者的安排——设计不是审查标准；方法只在判据文件。"""
        method = self.overlay_method()
        for needle in ("先独立想清楚", "写作设计", "设计漏掉的不因此算不在范围", "写了理由不等于理由成立",
                       "还开着的决定被写成已定", "已准入蓝图", "正文提到过", "真实待决写清了边界",
                       "写明未验证与影响"):
            self.assertIn(needle, method, f"判据里没有「{needle}」")
        self.assertNotIn("acceptance.yaml", method, "Story 判据还指着 Spec 的验收文件")

    def test_consistency_is_judged_on_two_layers(self) -> None:
        """原始决定对设计、设计对人读件各核一层：人读件忠实复述了与原始决定相反的蓝图主张，仍是阻断。"""
        method = self.overlay_method()
        for needle in ("一致性分两层核", "原始决定（材料原文、会议原话、人的裁决、评审回稿）与蓝图的设计是否一致",
                       "蓝图的设计与人读件", "仍是阻断发现，修正责任写回蓝图负责方",
                       "结果未知", "脱敏值", "云侧的业务状态", "实际接入者"):
            self.assertIn(needle, method)
        task = self.inject()
        self.assertEqual(1, task.count("一致性分两层核"), "判据原文在任务里装配了不止一次")

    def test_the_task_does_not_mention_a_publisher(self) -> None:
        """报告由调用方原样写出，没有钩子代它发布——任务书里不该还有那一环。"""
        text = self.inject()
        self.assertNotIn("插件", text)



class TheTaskMovesOnlyWithTheAuthorsInput(unittest.TestCase):
    """U38：审查对象只随被审材料变化，报告与检查结果落盘不铸出新的审查对象。

    材料键按审查对象的原始字节算。报告目录在对象之外：审过、核过之后重新准备，材料键不变、通过的报告复用；
    作者改了被审材料，材料键跟着变（09-26 实跑同一份材料审了又审 20 次）。
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
        again = self.prepared()
        self.assertEqual((first["material_key"], first["report_file"]), (again["material_key"], again["report_file"]),
                         "报告落盘换了审查对象，或通过的报告没有复用")

    def test_the_authors_input_still_moves_the_object(self) -> None:
        first = self.prepared()
        decisions = self.flow_path.parent / "decisions.json"
        data = json.loads(decisions.read_text(encoding="utf-8"))
        decisions.write_text(json.dumps({**data, "no_pending": "作者改了理由"}, ensure_ascii=False), encoding="utf-8")
        again = self.prepared()
        self.assertNotEqual(first["material_key"], again["material_key"], "决策登记改了，审查对象没变")


if __name__ == "__main__":
    unittest.main()
