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
from ext_workspace import link_framework, link_harness_yaml, DEV_EXT
from designed_fixture import designed_copy
import design_kit
import shared_state

REPO = Path(__file__).resolve().parents[2]
STORY_BUILD = DEV_EXT / "skills/story/scripts/core/story-build.mjs"
CONTRACT = DEV_EXT / "skills/story/contracts/story-chapters.json"
ACCESS = DEV_EXT / "hooks/shared/framework-access.mjs"
FEATURE = "RT90001"
#: 主执行者核过、本次准备给出的独立读者情况：有可用读者，或没有可用读者及其原因
READER_TASK = ("--reader", "task")
READER_NONE = ("--reader", "unavailable", "--reader-reason", "夹具宿主没有能接收自足只读任务的隔离读者")


def with_reader(args: tuple, reader: tuple = READER_TASK) -> tuple:
    """story-build 参数：review --action prepare 没给读者情况时按 `reader` 补上。"""
    return (*args, *reader) if args[:3] == ("review", "--action", "prepare") and "--reader" not in args else args
#: 导入用的图：明确选定一张现有图片，它的字节进共享前态的键
PICTURE = REPO / "test/fixtures/real-run/AR90006/assets/ux/auto-topup-manage-page.b3fad248696b67a1.png"
#: 这张图按内容身份导入后的名字后缀
PICTURE_ID = "b3fad248696b67a1"

STORY_MD = """# 甲需求（SMPFEAT）

## 背景

用户现在拿不到凭据。
"""

class TheStoryIsReviewedRegisteredAndDeliveredCase(unittest.TestCase):
    """一条真实的正常链：定稿并准备审查 → 审查者回复 → 按报告合同核对 → 登记 → 交付门。

    审查者是夹具（按 Story 报告合同写回复），只验证协议接得上；真实的独立执行与业务效果在 CLI 里核。
    默认有可用的独立读者（`--reader task`，没给时由 `run_node` 补上）。
    """

    FIXTURE = REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"

    FLOW = DEV_EXT / "skills/story/scripts/core/story_flow.py"
    reader = READER_TASK

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(self.FIXTURE, "REQ-DEMO", self.root)
        design_kit.install_review_mechanism(self.root, DEV_EXT)
        self.assertFalse((self.root / "doc" / "features" / "REQ-DEMO" / "spec").exists(), "2.0 的需求目录没有 Spec 产物")
        self.flow_path = self.root / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-flow.json"
        self.story = self.flow_path.parent.parent / "story.md"

    def run_node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(STORY_BUILD), *with_reader(args, self.reader), "--feature", "REQ-DEMO",
                               "--project-root", str(self.root)],
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

    def replied(self, kind: str = "pass", mutate=None) -> Path:
        """准备、审查者原样回复（还没接收）。`mutate` 改的是审查者给出的回复本身：造合同反例用。返回回复原件。"""
        prepared = self.review("prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        reply = design_kit.write_review(self.root, "REQ-DEMO", kind)
        if mutate:
            reply.write_text(mutate(reply.read_text(encoding="utf-8")), encoding="utf-8")
        return reply

    def reviewed(self, kind: str = "pass", mutate=None) -> Path:
        """正常一轮：准备、审查者原样回复、主执行者重跑 prepare 接收。返回回复原件。"""
        reply = self.replied(kind, mutate)
        self.receive()
        return reply

    def answer(self, kind: str = "pass") -> Path:
        """审查者按当前派审载体回复，主执行者接收。"""
        reply = design_kit.write_review(self.root, "REQ-DEMO", kind)
        self.receive()
        return reply

    def context_text(self) -> str:
        """前轮上下文：首读之后读，没有就是空串。"""
        f = self.flow_path.parent / "review" / "context.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def fresh(self) -> None:
        """回到没准备过的审查状态：准备记录、载体与报告目录都清掉。"""
        for name in ("prepared.json", "dispatch.md", "context.md"):
            (self.flow_path.parent / "review" / name).unlink(missing_ok=True)
        shutil.rmtree(self.root / "doc" / "reports", ignore_errors=True)

    def replies(self, cases: dict) -> None:
        """报告合同的局部变体（标签 → 回复种类、改法、应得结果）：真实准备一次，记下准备之后的审查现场；
        每个变体回到这份现场、只换审查者的回复再核结果：合合同的回复先接收才读出结论，信不过的回复不接收也直接判出，回复原件不被改。"""
        self.prepare()
        roots = (self.flow_path.parent / "review", self.root / "doc" / "reports")
        scene = {f: f.read_bytes() for r in roots if r.is_dir() for f in r.rglob("*") if f.is_file()}
        for label, (kind, mutate, want) in cases.items():
            with self.subTest(case=label):
                for f in [f for r in roots if r.is_dir() for f in r.rglob("*") if f.is_file() and f not in scene]:
                    f.unlink()
                for f, data in scene.items():
                    f.write_bytes(data)
                reply = design_kit.write_review(self.root, "REQ-DEMO", kind)
                reply.write_text(mutate(reply.read_text(encoding="utf-8")), encoding="utf-8")
                kept = reply.read_bytes()
                if want in ("pass", "warn"):
                    self.receive()
                got = self.result()
                self.assertEqual(want, got["result"], got)
                self.assertEqual(kept, reply.read_bytes(), "接收或核对改了回复原件")

    def receive(self) -> None:
        """回复落盘后重跑 prepare 接收它（记下原样字节的摘要）。"""
        out = self.review("prepare")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)

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

    def host(self, reviewer: bool) -> None:
        """之后的准备按哪种读者情况给参数：有可用的独立读者，或没有（带实际原因）。"""
        self.reader = READER_TASK if reviewer else READER_NONE


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
        self.assertIn("`doc/features/REQ-DEMO/.backups/local/RR/prd-直接-v1.md` —— 设计采用的阅读稿", task, "设计采用的材料版本没进审查对象")
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
        self.assertIn("phases/design.md「六、交付门之后：施工单位设计准备与 Spec/Plan」", text, "交付选项没指向执行方法")
        method = (DEV_EXT / "skills/story/phases/design.md").read_text(encoding="utf-8").split("## 六、交付门之后", 1)[1]
        self.assertIn("--requested-phases spec,plan", method, "实现方案没把 Plan 上限交给范围准备")
        self.assertNotIn("/story archive", text, "本地单没有送审")
        self.assertEqual(kept, original.read_bytes(), "核对、登记或交付门改了审查者的原回复")
        again = json.loads([l for l in self.register().stdout.splitlines() if l.startswith("{")][-1])
        self.assertFalse(again["registered"], "同一份对象重复登记换了身份")


class TheStoryIsReviewedRegisteredAndDeliveredPart2(TheStoryIsReviewedRegisteredAndDeliveredCase):
    def test_advisories_on_markdown_are_delivered_with_the_story(self) -> None:
        """读者判 warn：登记并带建议交付，交付说明指向原样报告，建议由主执行者按原报告如实说明，不在这里重抄一份。"""
        report = self.reviewed("advice").relative_to(self.root).as_posix()
        result = self.result()
        self.assertEqual("warn", result["result"], result)
        self.assertEqual(0, self.register().returncode)
        out = self.check("--deliver")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn(f"非阻断建议在原样报告 {report} 里", out.stdout)

    def test_a_reply_out_of_the_report_format_is_kept_and_not_registered(self) -> None:
        """审查者的回复不合报告合同：判 report_invalid，原回复一字不改地留着，不登记。"""
        original = self.replied("pass", lambda _t: "看过了，整体还行。\n")
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
                self.assertEqual("gathering", self.flow()["status"])


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

    def test_a_late_design_change_returns_to_the_delivery_gate_through_review_and_registration(self) -> None:
        """施工段改了共同设计：交付门说先按新蓝图同步稿、交原读者复核、重新登记；照做之后最后交接的交付门按新依据通过。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        revision = self.blueprint_revision()
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS,
                                    f"\nrevision: {revision}\n", f"\nrevision: {revision + 1}\n")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        for step in ("同步 Story 与 Review 里受影响的章节", "交原读者按改动影响复核", "`story_flow.py story` 重新登记"):
            self.assertIn(step, out.stdout + out.stderr)
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        self.assertEqual(revision + 1, self.flow()["story_basis"]["blueprint_ref"]["revision"])
        again = self.check("--deliver")
        self.assertEqual(0, again.returncode, again.stdout + again.stderr)

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

    def test_a_received_first_reply_rewritten_in_place_is_not_consumed(self) -> None:
        """R3：合法的首份 PASS / WARN 经正常接收后，原位改写成另一份仍合合同、材料键不变的回复：不再读出结论；
        改回原样照常复用；重新准备另起编号，改过的那份留作现场。"""
        for kind, want in (("pass", "pass"), ("advice", "warn")):
            with self.subTest(kind=kind):
                self.fresh()
                reply = self.reviewed(kind)
                self.assertEqual(want, self.result()["result"])
                kept = reply.read_bytes()
                rewritten = kept.decode("utf-8").replace("对着业务来源与人签通读了", "通读了").encode("utf-8")
                self.assertNotEqual(kept, rewritten, "夹具变了，用例要跟着改")
                reply.write_bytes(rewritten)
                self.assertEqual("report_invalid", self.result()["result"], "接收后原位改写的回复仍被当作结论")
                self.assertNotEqual(0, self.register().returncode, "改写过的回复被登记了")
                reply.write_bytes(kept)
                self.assertEqual(want, self.result()["result"], "改回原样后不能复用")
                reply.write_bytes(rewritten)
                out = self.prepare()
                self.assertNotEqual(reply, self.root / out["report_file"], "改写过的回复位置又被复用")
                self.assertFalse(out["reused"])
                self.assertEqual(rewritten, reply.read_bytes(), "现场被改了")

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
        self.answer("pass")
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
        """回复只核开头两行：材料键是这一份、结论是 pass / warn / fail；正文怎么组织由读者定，脚本不从正文推结论。"""
        cases = {
            "没有结论行": ("pass", lambda t: t.replace("conclusion: pass\n", ""), "report_invalid"),
            "结论不是三个词之一": ("pass", lambda t: t.replace("conclusion: pass", "conclusion: ok"), "report_invalid"),
            "结论不在第二行": ("pass", lambda t: t.replace("conclusion: pass\n", "\nconclusion: pass\n"), "report_invalid"),
            "开头多了说明": ("pass", lambda t: "以下是报告。\n" + t, "report_invalid"),
            "材料键不是这一份": ("pass", lambda t: t.replace(self.prepared()["material_key"], "0" * 64), "subject_stale"),
            "正文写了 fail 字样、结论行 pass": ("pass", lambda t: t + "\n我差点判 fail。\n", "pass"),
            "正文自由组织": ("advice", lambda t: t.replace("首读结论：", "## 读后\n\n"), "warn"),
        }
        self.replies(cases)


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
        """开头两行不合格的回复留在原处、不成为最近可消费的回复；下一次载体请读者补正它，原因进载体，不改成首读。"""
        first = self.replied("pass", lambda _t: "看过了，整体还行。\n")
        kept = first.read_bytes()
        diagnosis = self.result()
        self.assertEqual("report_invalid", diagnosis["result"])
        out = self.prepare()
        self.assertNotEqual(first, self.root / out["report_file"], "坏回复的位置被拿来写新回复")
        self.assertNotIn("last_received", self.prepared(), "坏回复成了最近可消费的回复")
        rel = first.relative_to(self.root).as_posix()
        self.assertIn("## 补正上一份回复", out["dispatch_text"])
        self.assertIn(f"`{rel}`", out["dispatch_text"])
        self.assertIn("开头两行要是", out["dispatch_text"], "不能接收的原因没进载体")
        self.assertNotIn("## 先首读", out["dispatch_text"], "补正又被要求重做首读")
        self.assertIn("只读，不写任何文件", out["dispatch_text"])
        self.assertEqual("report_invalid", self.result()["result"], "接收之后不能接收的原因不见了")
        again = self.prepare()
        self.assertEqual(out["report_file"], again["report_file"], "同一次补正再准备，回复位置递增了")
        self.assertEqual(out["dispatch_text"], again["dispatch_text"], "再准备丢了补正的原回复")
        self.assertEqual(kept, first.read_bytes(), "原回复被改了")
        self.answer("pass")
        self.assertEqual("pass", self.result()["result"])
        first.write_text("改过的原回复\n", encoding="utf-8")
        self.assertEqual("pass", self.result()["result"], "接收过的新结论被旧回复的改动带偏了")

    def test_an_altered_original_is_an_evidence_gap(self) -> None:
        """接收过的原回复被改：结果是证据错误，不读它的结论；恢复原样后照常可消费。"""
        passing = self.reviewed("pass")
        kept = passing.read_bytes()
        passing.write_bytes(kept.replace(b"conclusion: pass", b"conclusion: warn"))
        got = self.result()
        self.assertEqual("report_invalid", got["result"])
        self.assertIn("接收之后被改过", got["detail"])
        self.assertNotEqual(0, self.register().returncode, "改过的原回复被登记了")
        passing.write_bytes(kept)
        self.assertEqual("pass", self.result()["result"], "原件恢复之后正常审查结果反而不可消费")

    def test_a_failed_review_is_rechecked_with_its_report(self) -> None:
        """判了 fail 再准备：载体写明是复核并给原报告，不再要求像第一次那样首读；原 fail 在新回复前保持。"""
        failed = self.reviewed("block").relative_to(self.root).as_posix()
        out = self.prepare()
        text = out["dispatch_text"]
        self.assertIn("## 复核", text)
        self.assertIn(f"- 原报告：`{failed}`（只读）", text)
        for gone in ("## 先首读", "像第一次", "记下首读结论之前不读别的文件"):
            self.assertNotIn(gone, text, f"复核载体仍要求「{gone}」")
        self.assertNotIn("F-1", text, "阻断结论被抄进载体，读者应读原报告")
        self.assertEqual("fail", self.result()["result"], "新位置还空着，原有效 fail 被撤销")


class AWrittenStoryFollowsItsPlanThroughRegistration(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """已经成文登记的 Story，写作设计后来改了验收章的展示标题、又把两章换了位置：重交那一章、编号按有效章序移动章块，
    全篇检查按职责认验收章，重新审查并登记都成立；章内正文与评审记录的人工区不动。"""

    ACCEPTANCE = ("## 完成条件与验证\n\n| 编号 | 验收点 | 可观察的通过条件 |\n|---|---|---|\n"
                  "| AC-01 | 提交后看到回执 | 云侧回执到达后界面显示受理单编号 |\n")

    def tag_chapters(self) -> None:
        """夹具成稿早于章锚：按现行 skeleton 的写法，在每章标题前补上它的章锚（章 ID 按合同默认章序）。"""
        ids = [c["id"] for c in json.loads((DEV_EXT / "skills/story/contracts/story-chapters.json").read_text(encoding="utf-8"))["chapters"]]
        lines, out, k = self.story.read_text(encoding="utf-8").split("\n"), [], 0
        for line in lines:
            if line.startswith("## "):
                out.append(f"<!-- story-build:chapter {ids[k]} -->")
                k += 1
            out.append(line)
        self.story.write_text("\n".join(out), encoding="utf-8")

    def test_a_retitled_acceptance_and_swapped_chapters_are_moved_checked_and_registered(self) -> None:
        self.tag_chapters()
        self.reviewed("pass")
        first = self.register()
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        review = self.story.parent / "review.md"
        human = review.read_text(encoding="utf-8").split("<!-- human", 1)[-1]
        plan = self.flow_path.parent / "story-template.md"
        text = plan.read_text(encoding="utf-8").replace(
            "### 08-acceptance\n", "### 08-acceptance\n- 展示标题：完成条件与验证\n", 1)
        six, seven = text.index("### 06-features\n"), text.index("### 07-exceptions\n")
        block6, block7 = text[six:seven], text[seven:text.index("### 08-acceptance\n")]
        plan.write_text(text[:six] + block7 + block6 + text[seven + len(block7):], encoding="utf-8")
        before = self.story.read_text(encoding="utf-8")
        features = before.split("<!-- story-build:chapter 06-features -->", 1)[1].split("<!-- story-build:chapter 07-exceptions -->", 1)[0]
        draft = self.flow_path.parent / "drafts" / "08-验收.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(self.ACCEPTANCE, encoding="utf-8")
        put = self.run_node("chapter", "--chapter", "08-acceptance", "--from", str(draft))
        self.assertEqual(0, put.returncode, put.stdout + put.stderr)
        numbered = self.run_node("number")
        self.assertEqual(0, numbered.returncode, numbered.stdout + numbered.stderr)
        self.assertIn("移动了章块", numbered.stdout)
        story = self.story.read_text(encoding="utf-8")
        heads = [line for line in story.splitlines() if line.startswith("## ")]
        self.assertEqual(["异常与恢复", "功能说明"], [h.split(". ", 1)[1] for h in heads[5:7]], heads)
        self.assertEqual("## 8. 完成条件与验证", heads[7])
        prose = [line for line in features.splitlines() if line.strip() and not line.startswith("#")]
        self.assertTrue(prose and all(line in story for line in prose), "移动章块改了章内正文（编号随章号重编之外）")
        checked = self.check()
        out = checked.stdout + checked.stderr
        self.assertNotIn("承担验收的那一章", out, out)
        self.assertNotIn("章标题与顺序", out, out)
        self.reviewed("pass")
        again = self.register()
        self.assertEqual(0, again.returncode, again.stdout + again.stderr)
        self.assertEqual(human, review.read_text(encoding="utf-8").split("<!-- human", 1)[-1], "评审记录的人工区被动了")


class TheWholeSourceSetIsReviewed(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """完整核源：设计未见引用的阅读稿、登记不用的图与会议纠偏留痕也在独立审查的对象里——任务列它、读者可以回查它；
    冻结采用版本仍是设计权威，同字节的当前文件是它的别名，换了内容的当前文件另列对照；二进制原件只核在场与来源摘要。"""

    IMPORT = DEV_EXT / "skills/story/scripts/core/import_sources.py"
    FEATURE = "doc/features/REQ-DEMO"
    CORRECTIONS = f"{FEATURE}/AR/story-src/meetings/续期会/v1/corrections.json"

    def put(self, files: dict[str, tuple[bytes, str]]) -> None:
        """经真实导入命令导成材料版本并登记本轮。"""
        inbox = self.root / self.FEATURE / "inbox"
        classify = {}
        for rel, (body, cls) in files.items():
            (inbox / rel).parent.mkdir(parents=True, exist_ok=True)
            (inbox / rel).write_bytes(body)
            classify[rel] = cls
        (inbox / ".classify.json").write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        self.run_py(self.IMPORT)
        self.run_py(self.FLOW, "round")

    def latest(self, key: str) -> str:
        index = json.loads((self.flow_path.parent / "materials.json").read_text(encoding="utf-8"))
        return next(s for s in index["sources"] if s["source_id"] == f"local:{key}")["versions"][-1]["original"]["path"]

    def origin(self, key: str) -> tuple[str, str]:
        """材料表那一行该写的 (原件, 阅读稿)：原件在收件箱原处，阅读稿是它所在的当前阅读稿。"""
        index = json.loads((self.flow_path.parent / "materials.json").read_text(encoding="utf-8"))
        o = next(o for o in index["origins"] if o["source_id"] == f"local:{key}")
        return o["path"], o["readable_paths"][0]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        target = Path(self._tmp.name) / "work"
        prepared_copy("whole-source", "base", self.build, target)
        self.root = target   # 前态在这个用例里建时，build 临时指向了构建目录
        self.flow_path = self.root / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-flow.json"
        self.story = self.flow_path.parent.parent / "story.md"
        self.sr_original, self.sr_rel = self.origin("SR/design.md")
        sr_original = self.sr_original
        self.SR = f"{self.FEATURE}/{self.sr_rel}"
        self.IMAGE = f"{self.FEATURE}/{self.latest('old.png')}"
        self.SR_ROW = (f"| 系统设计 [design.md](../{self.sr_rel}) | [design.md](../{sr_original}) "
                       "| 续期按月的提法与产品需求冲突，未采用：以产品需求的按年为准。 |")

    def build(self, base: Path) -> None:
        """完整核源的前态：设计准备之后经真实导入命令补一份没采用的系统设计与一张登记不用的图，作者在材料表写明，
        另放一次会议的原文、纠偏与阅读件。"""
        self.root = base
        designed_copy(self.FIXTURE, "REQ-DEMO", base)
        design_kit.install_review_mechanism(base, DEV_EXT)
        self.flow_path = base / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-flow.json"
        self.story = self.flow_path.parent.parent / "story.md"
        self.put({"SR/design.md": ("# 系统设计\n\n续期改为按月扣费，与产品需求的按年不同。\n".encode("utf-8"), "SR"),
                  "old.png": (PICTURE.read_bytes(), "UX")})
        sr_original, sr_rel = self.origin("SR/design.md")
        image = f"{self.FEATURE}/{self.latest('old.png')}"
        self.run_py(self.IMPORT, "--caption-image", image, "--unused", "旧版签约页，本需求不改签约页")
        # 作者在材料表里写明没采用的那份与原因：材料表按 origins 核覆盖
        row = (f"| 系统设计 [design.md](../{sr_rel}) | [design.md](../{sr_original}) "
               "| 续期按月的提法与产品需求冲突，未采用：以产品需求的按年为准。 |")
        anchor = "| 开发需求 [design.md](design.md) |"
        self.story.write_text(self.story.read_text(encoding="utf-8").replace(anchor, row + "\n" + anchor), encoding="utf-8")
        meeting = self.flow_path.parent / "meetings" / "续期会" / "v1"
        meeting.mkdir(parents=True)
        (meeting / "raw.md").write_text("主持人：续期按年。\n", encoding="utf-8")
        (meeting / "corrections.json").write_text(json.dumps({"corrections": [{"line": 1, "note": "按年无误"}]}, ensure_ascii=False),
                                                  encoding="utf-8")
        (meeting / "evidence.md").write_text("续期按年。\n", encoding="utf-8")

    def run_py(self, script: Path, *args: str) -> None:
        out = subprocess.run(["python", str(script), *args, "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)

    def task_text(self) -> str:
        return (self.root / self.prepare()["task"]).read_text(encoding="utf-8")

    def test_the_task_lists_what_the_author_left_out(self) -> None:
        task = self.task_text()
        for rel in (self.SR, self.IMAGE, self.CORRECTIONS):
            self.assertIn(f"`{rel}`", task)
        self.assertIn(f"`{self.SR}` —— 设计未见引用的阅读稿 {self.sr_rel}（核是有据不用，还是漏了依据）", task)
        self.assertIn("当前有效人答（必读：问法与原话）", task, "必读人答没进独立审查的核源集合")
        self.assertIn("作者登记不用：旧版签约页，本需求不改签约页", task)

    def test_a_missing_meeting_correction_is_named_not_dropped(self) -> None:
        """会议版本在、纠偏留痕或阅读件缺了：准备审查报缺件、点名那份文件，不缩成更小的必审集合。"""
        for name in ("corrections.json", "evidence.md"):
            with self.subTest(missing=name):
                target = self.root / self.CORRECTIONS if name == "corrections.json" else \
                    self.root / self.CORRECTIONS.replace("corrections.json", "evidence.md")
                kept = target.read_bytes()
                target.unlink()
                out = self.review("prepare")
                self.assertNotEqual(0, out.returncode)
                self.assertIn(name, out.stdout + out.stderr)
                target.write_bytes(kept)

    def test_landings_with_different_bytes_are_read_apart(self) -> None:
        """同一条图片登记的几个落点：同字节的是别名，内容不同的各自核读，不共用一份阅读声明。"""
        manifest = self.flow_path.parent / "materials.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        image = next(m for m in data["materials"] if "image" in str(m.get("kind")) and any("/old." in p for p in m["paths"]))
        folder = Path(self.IMAGE).parent.relative_to(self.FEATURE).as_posix()
        original = self.root / self.IMAGE
        (original.parent / "old-copy.png").write_bytes(original.read_bytes())
        (original.parent / "old-edited.png").write_bytes(original.read_bytes() + b"x")
        image["paths"] += [f"{folder}/old-copy.png", f"{folder}/old-edited.png"]
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        task = self.task_text()
        copy_rel, edited_rel = f"{self.FEATURE}/{folder}/old-copy.png", f"{self.FEATURE}/{folder}/old-edited.png"
        self.assertIn(f"`{copy_rel}` —— ", task)
        self.assertIn(f"（与 `{self.IMAGE}` 同一内容）", task.split(f"`{copy_rel}`", 1)[1].split("\n", 1)[0])
        edited = task.split(f"`{edited_rel}`", 1)[1].split("\n", 1)[0]
        self.assertIn("内容不同，单独核读", edited)
        self.assertNotIn("同一内容", edited)

    def test_a_binary_origin_is_checked_not_read(self) -> None:
        import hashlib
        feature = self.root / self.FEATURE
        docx_rel = f"{Path(self.sr_rel).parent.as_posix()}/系统设计.docx"
        docx = feature / docx_rel
        docx.write_bytes(b"PK\x03\x04 binary original")
        manifest = self.flow_path.parent / "materials.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["origins"].append({"path": docx_rel, "kind": "local", "readable_paths": [self.sr_rel],
                                "sha256": hashlib.sha256(docx.read_bytes()).hexdigest()})
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        link = f"[design.md](../{self.sr_original})"
        self.story.write_text(self.story.read_text(encoding="utf-8").replace(
            self.SR_ROW, self.SR_ROW.replace(f"| {link} |", f"| {link} [系统设计.docx](../{docx_rel}) |")), encoding="utf-8")
        rel = f"{self.FEATURE}/{docx_rel}"
        self.assertIn(f"`{rel}` —— 原件 {docx_rel}（核在场与来源摘要，正文读它的阅读稿）　（核在场与来源摘要，不必通读）",
                      self.task_text())
        self.fresh()
        self.reviewed("pass")
        self.assertEqual("pass", self.result()["result"], "只核在场的二进制原件被当成必读")
        docx.write_bytes(b"PK\x03\x04 another version")
        out = self.review("prepare")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("与材料清单登记的", out.stdout + out.stderr)
        self.assertEqual("input_invalid", self.result()["result"])

    def test_the_adopted_version_stays_beside_a_newer_version(self) -> None:
        """产品需求取得了新版本：设计采用的那一版仍是设计权威；新版本单独列作设计未见引用的阅读稿，核是有据不用还是漏了依据。"""
        prd = ".backups/local/RR/prd-直接-v1.md"
        self.assertIn(f"`{self.FEATURE}/{prd}` —— 设计采用的阅读稿 {prd}", self.task_text())
        current = self.root / self.FEATURE / "RR" / "prd.md"
        current.write_bytes(current.read_bytes() + "\n新版补了一句。\n".encode("utf-8"))
        self.put({})
        task = self.task_text()
        new = "RR/prd.md"     # 当前版本的阅读稿就是原处的直接原文
        self.assertIn(f"`{self.FEATURE}/{new}` —— 设计未见引用的阅读稿 {new}（核是有据不用，还是漏了依据）", task)
        self.assertIn(f"`{self.FEATURE}/{prd}` —— 设计采用的阅读稿 {prd}", task)
        self.assertIn("设计引证 v1，取得的 v2 未见引用", task, "材料表让最新取得的一版冒充了设计采用")

    def test_a_changed_left_out_source_retires_the_report(self) -> None:
        self.reviewed("pass")
        self.assertEqual("pass", self.result()["result"])
        self.put({"SR/design.md": ("# 系统设计\n\n续期改为按季。\n".encode("utf-8"), "SR")})
        self.assertEqual("subject_stale", self.result()["result"])


class TheReaderAnswersAndTheLatestReplyIsKept(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """准备记录只记当前请求与最近一次可消费的回复：不合格回复不成为依据，最近 fail 在新结论前保持，不回找历史 PASS；
    读者情况由 --reader 给出，已有结论正是当前对象时换了读者情况也直接复用。"""

    def test_an_invalid_reply_never_becomes_the_basis_of_a_later_review(self) -> None:
        """首审回复不合格、作者随后改稿：不合格的那份不是最近可消费的回复，新载体按首读交出，不把它当原报告。"""
        bad = self.replied("pass", lambda t: t.replace("conclusion: pass\n", "")).relative_to(self.root).as_posix()
        self.assertEqual("report_invalid", self.result()["result"])
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n作者改的一句。\n", encoding="utf-8")
        out = self.prepare()
        self.assertNotIn("last_received", self.prepared())
        self.assertNotIn(bad, out["dispatch_text"], "改稿之后不合格的旧回复成了复核依据")
        self.assertIn("## 先首读", out["dispatch_text"])
        self.assertEqual("report_missing", self.result()["result"])
        self.answer("pass")
        self.assertEqual("pass", self.result()["result"])

    def test_the_latest_fail_holds_until_a_new_consumable_reply(self) -> None:
        self.reviewed("block")
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n按发现补的一句。\n", encoding="utf-8")
        self.prepare()
        got = self.result()
        self.assertEqual("fail", got["result"], got)
        self.assertIn("已知必修未复核", got["detail"])
        self.replied("pass", lambda t: t.replace("conclusion: pass", "conclusion: 通过"))
        self.assertEqual("report_invalid", self.result()["result"])
        self.prepare()
        self.assertEqual("fail", self.result()["result"], "不合格的补正把已知 fail 洗掉了")
        self.answer("pass")
        self.assertEqual("pass", self.result()["result"])

    def test_no_older_pass_is_searched_after_a_newer_reply(self) -> None:
        """A 通过 → B 也有了回复 → 改回 A：最近一次可消费的是 B 的回复，A 的旧 PASS 不被翻出来复用。"""
        self.reviewed("pass")
        a = self.story.read_bytes()
        self.story.write_bytes(a + "\nB 的一句。\n".encode("utf-8"))
        self.reviewed("pass")
        self.story.write_bytes(a)
        out = self.prepare()
        self.assertFalse(out["reused"], "改回 A 时翻出了更早的 PASS")
        self.assertEqual("report_missing", self.result()["result"])

    def test_the_record_keeps_only_the_request_and_the_latest_reply(self) -> None:
        self.reviewed("block")
        self.prepare()
        record = self.prepared()
        allowed = {"material_key", "project_root", "report_dir", "report_file", "reused", "prior_report", "prior_problem",
                   "disclosure", "last_received"}
        self.assertLessEqual(set(record), allowed, set(record) - allowed)
        self.assertEqual({"material_key", "report_file", "report_sha256"}, set(record["last_received"]))
        old = self.flow_path.parent / "review" / "prepared.json"
        old.write_text(json.dumps({**record, "review_contexts": {}}, ensure_ascii=False), encoding="utf-8")
        got = self.result()
        self.assertEqual("input_invalid", got["result"])
        self.assertIn("旧版审查格式", got["detail"])

    def test_preparing_needs_the_reader_fact(self) -> None:
        before = self.tree()
        for args in (("review", "--action", "prepare", "--reader", "maybe"),
                     ("review", "--action", "prepare", "--reader", "unavailable")):
            with self.subTest(args=args):
                out = subprocess.run(["node", str(STORY_BUILD), *args, "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
                self.assertNotEqual(0, out.returncode)
                self.assertIn("--reader", out.stderr)
                self.assertEqual(before, self.tree(), "读者情况没给全就写了盘")

    def test_a_current_conclusion_survives_a_later_reader_change(self) -> None:
        """当前对象已有可消费的 pass：之后准备时没有可用读者，也直接复用，不改写正文去加未审披露。"""
        self.reviewed("pass")
        story = self.story.read_bytes()
        self.host(reviewer=False)
        out = self.prepare()
        self.assertTrue(out["reused"])
        self.assertEqual(story, self.story.read_bytes(), "已有结论还被改写成未审")
        self.assertEqual("pass", self.result()["result"])


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


class TheDesignReferenceIsTheNativeProjection(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """设计参考是同根蓝图的原生评审投影：审查任务把它列作只读对照，待审的只有 Story 与 Review；本地不另存副本，
    蓝图换版后旧登记不再交付。"""

    def projection(self) -> Path:
        return self.root / "doc" / "features" / design_kit.blueprint_of(self.root, "REQ-DEMO") / "blueprint" / "component-blueprint.review.md"

    def test_the_review_reads_the_projection_and_nothing_is_copied(self) -> None:
        self.reviewed("pass")
        self.assertFalse((self.story.parent / "design-review.md").exists(), "定稿又在交付层复制了一份设计")
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        objects, sources = task.split("待审（结论针对它们）：", 1)[1].split("只读对照（据以判断，不在这次改）：", 1)
        projection = self.projection().relative_to(self.root).as_posix()
        self.assertIn(f"`{projection}` —— 蓝图的原生评审投影（设计参考", sources)
        self.assertEqual(["AR/review.md", "AR/story.md"],
                         sorted(line.split("`")[1].split("REQ-DEMO/", 1)[1] for line in objects.splitlines() if line.startswith("- `")))
        self.assertEqual(0, self.register().returncode)
        self.assertEqual(0, self.check("--deliver").returncode)

    def test_business_sources_are_read_and_technical_references_are_looked_up(self) -> None:
        """审查对象仍是完整库存：业务入口逐份读，蓝图、原生评审投影与知识按问题回查，激活清单只核在场；
        后读任务给蓝图的知识判断作定位，适用与不适用都在。"""
        self.assertEqual(0, self.review("prepare").returncode)
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        sources = task.split("只读对照（据以判断，不在这次改）：", 1)[1].split("\n### ", 1)[0]
        lines = [line for line in sources.splitlines() if line.startswith("- `")]
        blueprint = design_kit.blueprint_of(self.root, "REQ-DEMO")

        def marked(needle: str) -> list[str]:
            hits = [line for line in lines if needle in line]
            self.assertTrue(hits, f"材料表里没有「{needle}」")
            return hits

        for needle in ("蓝图的原生评审投影", f"{blueprint}/blueprint/component-blueprint.yaml", "激活知识 knowledge/"):
            self.assertTrue(all(line.endswith("（按问题回查）") for line in marked(needle)), f"「{needle}」没标按问题回查")
        self.assertTrue(all(line.endswith("（核在场与来源摘要，不必通读）") for line in marked("知识激活清单")))
        for needle in ("—— 设计采用的阅读稿", "—— 审查判据"):
            self.assertFalse(any("按问题回查" in line or "不必通读" in line for line in marked(needle)), f"业务入口「{needle}」被降成了回查")
        located = task.split("### 蓝图里的知识判断（定位用，待核）", 1)[1].split("\n### ", 1)[0]
        self.assertIn("→ applied：本需求新增提交入口", located)
        self.assertIn("→ not_applicable：本需求没有任何上报动作", located)

    def test_the_rule_text_keeps_its_paragraph_lines(self) -> None:
        """判据按原段落分行交给审查者，不折成一条多页长行。"""
        self.assertEqual(0, self.review("prepare").returncode)
        task = (self.flow_path.parent / "review" / "task.md").read_text(encoding="utf-8")
        rules = task.split("### 判据 story_reader_review", 1)[1].split("### 怎么读", 1)[0]
        self.assertGreater(len(rules.splitlines()), 60)
        self.assertLess(max(len(line) for line in rules.splitlines()), 300, "判据又被折成了长行")
        self.assertIn("\n**核的先后**：", rules)

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

    def test_the_reading_scope_is_chosen_before_the_full_reading_order(self) -> None:
        """入口按载体写的情形定读法：首次阅读完整核源、复核按原报告与改动的实际影响回查、补正只补缺的部分；
        核源顺序只在这之后给一次，没有末尾追加的例外条，也没有「每轮像第一次」的统一首读。"""
        self.assertEqual(0, self.review("prepare").returncode)
        reading = self.reading().strip()
        head, order = reading.split("\n\n1. ", 1)
        for words in ("**首次阅读**", "**复核**", "**补正**", "实际涉及", "照用"):
            self.assertIn(words, head)
        self.assertNotRegex(order, r"(?m)^5\. ", "又在末尾追加了例外条")
        self.assertNotIn("像第一次", reading)
        self.assertIn("蓝图与它的原生评审投影", order)

    def test_a_revised_blueprint_retires_the_old_registration(self) -> None:
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "target_state: refresh trigger",
                                    "target_state: refresh trigger and badge")
        self.assertNotEqual(0, self.check("--deliver").returncode, "蓝图换版之后旧登记仍被交付")


class AHostWithoutAReviewerDisclosesUnreviewed(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """本次准备没有可用的独立读者（`--reader unavailable` 带实际原因）：未审披露写进 Story 交付章与 Review 题头，结果 unreviewed，
    可以登记与交付，不问人要授权、流程契约里没有授权记录。已知必修未复核不按未审放行；之后有了读者，重新准备撤掉披露。"""

    def setUp(self) -> None:
        super().setUp()
        self.host(reviewer=False)

    def test_unreviewed_is_disclosed_in_both_documents_without_asking(self) -> None:
        prepared = self.review("prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        self.assertIn("本版不派审", prepared.stdout)
        self.assertIn("直接跑 story-build review --action check", prepared.stdout)
        self.assertNotIn("交给审查者", prepared.stdout, "没有审查员还叫人派审")
        dispatch = (self.flow_path.parent / "review" / "dispatch.md").read_text(encoding="utf-8")
        self.assertIn("本版不派审", dispatch)
        self.assertNotIn("独立审查者", dispatch, "派审载体还在给一个不存在的审查者下任务")
        self.assertEqual("unreviewed", self.result()["result"])
        story = self.story.read_text(encoding="utf-8")
        chapter = story.split("## 9.", 1)[1].split("\n## ", 1)[0]
        self.assertIn("本版未经独立审查", chapter, "Story 交付章没有审查状态")
        self.assertIn("夹具宿主没有能接收自足只读任务的隔离读者", chapter, "未审披露没写实际原因")
        review = (self.story.parent / "review.md").read_text(encoding="utf-8")
        self.assertIn("本版未经独立审查", review.split("\n## ", 1)[0], "Review 题头之后、议题之前没有审查状态")
        before = self.tree()
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(before, self.tree(), "同样的输入重跑准备改了字节")
        self.assertEqual(0, self.register().returncode)
        out = self.check("--deliver")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn("本版未经独立审查", out.stdout)
        self.assertNotIn("review_waiver", self.flow())
        retired = subprocess.run(["python", str(self.FLOW), "unreviewed", "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertNotEqual(0, retired.returncode, "免审授权命令还在")

    def test_a_crlf_story_gets_one_disclosure(self) -> None:
        """以 CRLF 交来的 Story：披露写进交付章一次，重跑准备字节不变。"""
        self.story.write_bytes(self.story.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(0, self.review("prepare").returncode)
        first = self.story.read_bytes()
        self.assertEqual(1, first.decode("utf-8").count("本版未经独立审查"))
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual(first, self.story.read_bytes(), "重跑准备改了 Story 的字节")
        self.assertEqual("unreviewed", self.result()["result"])

    def test_a_known_blocker_is_not_released_as_unreviewed(self) -> None:
        """有审查员时判了阻断；之后宿主没有审查员：同一份材料仍是 fail，改过之后也不按未审放行，登记不了。"""
        self.host(reviewer=True)
        self.reviewed("block")
        self.host(reviewer=False)
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("fail", self.result()["result"], "宿主没了审查员，已知阻断就消失了")
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n按审查意见补的一句。\n", encoding="utf-8")
        self.assertEqual(0, self.review("prepare").returncode)
        got = self.result()
        self.assertEqual("fail", got["result"], got)
        self.assertIn("已知必修未复核", got["detail"])
        self.assertNotEqual(0, self.register().returncode, "已知必修未复核还登记了")
        self.story.write_text(self.story.read_text(encoding="utf-8") + "\n再补一句。\n", encoding="utf-8")
        prepared = self.review("prepare")
        self.assertIn("已知必修未复核", self.result()["detail"], "再改一版就把已知阻断丢了")
        self.assertIn("之后还没有新的可消费回复", prepared.stdout)
        self.assertNotIn("unreviewed", prepared.stdout.split("之后还没有新的可消费回复", 1)[1], "已知必修待复核还说成未审放行")
        # 有了可用读者：载体按复核交出原报告，复核给出新的可消费结论才解除
        blocked = self.prepared()["last_received"]["report_file"]
        self.host(reviewer=True)
        out = self.prepare()
        self.assertIn(f"- 原报告：`{blocked}`（只读）", out["dispatch_text"])
        self.assertIn("## 复核", out["dispatch_text"])
        self.assertEqual("fail", self.result()["result"], "复核还没来，已知必修就解除了")
        self.answer("pass")
        self.assertEqual("pass", self.result()["result"])

    def test_a_reader_found_later_removes_the_disclosure(self) -> None:
        """准备时没有可用读者、之后有了：以 --reader task 重新准备撤掉披露，按正常审查走；check 不自己探宿主。"""
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("unreviewed", self.result()["result"])
        self.host(reviewer=True)
        self.assertEqual("unreviewed", self.result()["result"], "check 自己去探了宿主")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertNotIn("本版未经独立审查", self.story.read_text(encoding="utf-8"))
        self.assertEqual("report_missing", self.result()["result"])
        self.answer("pass")
        self.assertEqual("pass", self.result()["result"])


class TheReportDirStaysWithItsMaterial(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """报告目录随材料键定一次：另指目录报冲突、不改文件，已知的阻断仍在；不带参数准备仍写进首次定下的目录。"""

    def test_another_report_dir_keeps_the_known_blocker(self) -> None:
        self.reviewed("block")
        self.assertEqual("fail", self.result()["result"])
        before = self.tree()
        moved = self.run_node("review", "--action", "prepare", "--report-dir", "doc/reports/alternate-neutral")
        self.assertNotEqual(0, moved.returncode)
        self.assertIn("报告目录冲突", moved.stdout + moved.stderr)
        self.assertEqual(before, self.tree(), "目录冲突的准备改了文件")
        self.assertEqual("fail", self.result()["result"])
        self.reviewed("pass")
        self.assertEqual("pass", self.result()["result"], "原目录里的复审没更新结论")

    def test_a_chosen_report_dir_stays_with_its_material(self) -> None:
        first = self.run_node("review", "--action", "prepare", "--report-dir", "doc/reports/chosen")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual("doc/reports/chosen", self.prepared()["report_dir"])
        design_kit.write_review(self.root, "REQ-DEMO", "block")
        self.assertEqual(0, self.review("prepare").returncode)
        self.assertEqual("doc/reports/chosen", self.prepared()["report_dir"])
        self.assertEqual("fail", self.result()["result"])


def prepared_copy(name: str, variant: str, build, target: Path) -> None:
    """一组用例共同的前态（还没准备独审、没登记报告）：同一业务输入只真实生产一次，各用例拿私有副本，副本重接 Framework。
    前态由当前生产者产生，键是输入内容（夹具、开发源与造状态的脚本、构造前态的本文件、导入的图、被测 Framework）
    与变体名，不剥导入时刻、不手补状态。"""
    key = shared_state.digest(REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good",
                              *shared_state.COMMON, Path(__file__), PICTURE, shared_state.framework_version(), name, variant)
    shared_state.copy_tree(shared_state.shared_tree(name, key, build), target)
    link_framework(target)


def import_fixture(fixture: Path, files: dict[str, tuple[bytes, str]]) -> None:
    """在夹具副本上经真实导入命令导成材料版本（需求 REQ-DEMO）。"""
    inbox = fixture / "doc" / "features" / "REQ-DEMO" / "inbox"
    classify = {}
    for rel, (body, cls) in files.items():
        (inbox / rel).parent.mkdir(parents=True, exist_ok=True)
        (inbox / rel).write_bytes(body)
        classify[rel] = cls
    (inbox / ".classify.json").write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["python", str(DEV_EXT / "skills/story/scripts/core/import_sources.py"), "--feature", "REQ-DEMO",
                           "--project-root", str(fixture)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


class ARequirementWithUiReferenceGoesThrough(unittest.TestCase):
    """带界面参考图的需求：界面图是需求根下的材料版本，蓝图在异名的工作区（`bp-<需求>`），
    冻结、蓝图消费、审查准备、登记与交付一路走通（审查者是夹具）。"""

    FLOW = DEV_EXT / "skills/story/scripts/core/story_flow.py"
    IMPORT = DEV_EXT / "skills/story/scripts/core/import_sources.py"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        fixture = Path(self._tmp.name) / "fixture"
        shutil.copytree(REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good", fixture)
        import_fixture(fixture, {"home.png": (PICTURE.read_bytes(), "UX")})
        self.root = Path(self._tmp.name) / "work"
        designed_copy(fixture, "REQ-DEMO", self.root)
        design_kit.install_review_mechanism(self.root, DEV_EXT)

    def run_node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(STORY_BUILD), *with_reader(args), "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def test_the_story_is_reviewed_and_delivered_next_to_its_ui_reference(self) -> None:
        self.assertTrue((self.root / "doc/features/REQ-DEMO/blueprint/component-blueprint.yaml").is_file(), "蓝图不在需求同根")
        # 参考图没用上：照检查给的那条命令原样登记不用的理由
        hint = self.run_node("check").stderr
        command = hint.split("`import_sources.py ", 1)[1].split("`", 1)[0]
        image = command.split("--caption-image ", 1)[1].split(" ", 1)[0]
        self.assertEqual(f"doc/features/REQ-DEMO/assets/ux/home.{PICTURE_ID}.png", image)
        done = subprocess.run(["python", str(self.IMPORT), "--feature", "REQ-DEMO", "--project-root", str(self.root),
                               "--caption-image", image, "--unused", "首页现状参考，本需求不改首页"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        prepared = self.run_node("review", "--action", "prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        task = (self.root / "doc/features/REQ-DEMO/AR/story-src/review/task.md").read_text(encoding="utf-8")
        self.assertIn(f"`doc/features/REQ-DEMO/assets/ux/home.{PICTURE_ID}.png`", task)
        self.assertIn("`doc/features/REQ-DEMO/blueprint/component-blueprint.yaml`", task)
        design_kit.write_review(self.root, "REQ-DEMO", "pass")
        received = self.run_node("review", "--action", "prepare")
        self.assertEqual(0, received.returncode, received.stdout + received.stderr)
        registered = subprocess.run(["python", str(self.FLOW), "story", "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, registered.returncode, registered.stdout + registered.stderr)
        delivered = self.run_node("check", "--deliver")
        self.assertEqual(0, delivered.returncode, delivered.stdout + delivered.stderr)


class TheVisualRulingIsTheNativeRouting(unittest.TestCase):
    """冻结输入里有图时，看图能力与保真路由由独立 Story 审查在准备与核对时调原生纯函数算，不读预置的裁定文件。

    夹具宿主是 generic（看不了图、OCR 就绪）：需求没写强保真时原生路由 semantic_layout / best_effort、不延期，
    图面未核是能力缺口，文本审完最高判 WARN；需求写了强保真时 strictness=hard，图没核就是没审完。
    """

    FLOW = DEV_EXT / "skills/story/scripts/core/story_flow.py"
    IMPORT = DEV_EXT / "skills/story/scripts/core/import_sources.py"
    IMAGE = f"assets/ux/home.{PICTURE_ID}.png"

    def make(self, hard: bool = False) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        prepared_copy("visual-ruling", "hard" if hard else "normal", lambda base: self.build(base, hard), self.root)

    def build(self, base: Path, hard: bool) -> None:
        """有图的前态：真实导入图（强保真再导一版产品需求、Story 改引新版）、设计准备、登记这张图不用的理由。"""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "fixture"
            shutil.copytree(REPO / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good", fixture)
            feature = fixture / "doc" / "features" / "REQ-DEMO"
            files = {"home.png": (PICTURE.read_bytes(), "UX")}
            if hard:
                prd = feature / "RR" / "prd.md"
                prd.write_bytes(prd.read_bytes() + "\n签约页必须像素级还原设计稿，不接受降级。\n".encode("utf-8"))
            import_fixture(fixture, files)
            designed_copy(fixture, "REQ-DEMO", base)
        design_kit.install_review_mechanism(base, DEV_EXT)
        done = subprocess.run(["python", str(self.IMPORT), "--feature", "REQ-DEMO", "--project-root", str(base),
                               "--caption-image", f"doc/features/REQ-DEMO/{self.IMAGE}", "--unused", "签约页现状参考，本需求不改签约页"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr

    def run_node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(STORY_BUILD), *with_reader(args), "--feature", "REQ-DEMO", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def result(self) -> dict:
        out = self.run_node("review", "--action", "check")
        return json.loads([line for line in out.stdout.splitlines() if line.startswith("{")][-1])

    def review(self, kind: str) -> dict:
        """准备审查、夹具审查者回复（写明图面未核）、接收；返回核对结果。"""
        prepared = self.run_node("review", "--action", "prepare")
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        report = design_kit.write_review(self.root, "REQ-DEMO", kind)
        report.write_text(report.read_text(encoding="utf-8") + "\n宿主看不了图，图面未核。\n", encoding="utf-8")
        received = self.run_node("review", "--action", "prepare")
        self.assertEqual(0, received.returncode, received.stdout + received.stderr)
        return self.result()

    def task(self) -> str:
        return (self.root / "doc/features/REQ-DEMO/AR/story-src/review/task.md").read_text(encoding="utf-8")

    def test_the_task_states_the_native_ruling(self) -> None:
        self.make()
        self.assertEqual(0, self.run_node("review", "--action", "prepare").returncode)
        task = (self.root / "doc/features/REQ-DEMO/AR/story-src/review/task.md").read_text(encoding="utf-8")
        self.assertIn("**本次看图能力**：看图能力：看不了图（adapter generic", task)
        self.assertIn("effective=semantic_layout、strictness=best_effort、defer=false", task)

    def test_a_blind_host_with_zero_change_units_gets_a_bounded_text_review(self) -> None:
        """零施工单位、没有主需求 Spec：原生裁定可延期，任务照实告诉读者；读者写明图面未核、判 WARN 照常可消费。"""
        self.make()
        got = self.review("advice")
        self.assertEqual("warn", got["result"], got)
        self.assertIn("**图面核对可以按能力缺口延期**", self.task())

    def test_a_hard_fidelity_requirement_is_not_deferred(self) -> None:
        """需求写了强保真：原生路由 strictness=hard，任务告诉读者图面不能延期、看不了图就是没读完。"""
        self.make(hard=True)
        self.assertEqual(0, self.run_node("review", "--action", "prepare").returncode)
        task = self.task()
        self.assertIn("strictness=hard", task)
        self.assertIn("图面核对不能延期：看不了图就是没读完", task)
        self.assertNotIn("**图面核对可以按能力缺口延期**", task)

    def test_a_missing_picture_is_not_a_capability_gap(self) -> None:
        """登记的那张图盘上没了：审查对象不成立，不按「看不了图」放行。"""
        self.make()
        self.assertEqual("warn", self.review("advice")["result"])
        (self.root / "doc/features/REQ-DEMO" / self.IMAGE).unlink()
        self.assertNotIn(self.result()["result"], ("pass", "warn"))

    def test_a_changed_design_identity_retires_the_report(self) -> None:
        """蓝图修订换了审查身份：上一份按旧身份写的报告不再是当前结论。"""
        self.make()
        self.assertEqual("warn", self.review("advice")["result"])
        design_kit.change_blueprint(self.root, "REQ-DEMO", ACCESS, "  admission:\n    status: pass", "  admission:\n    status: fail")
        self.assertNotIn(self.result()["result"], ("pass", "warn"))


class TheCoverageRulesJudgeTheDetails(unittest.TestCase):
    """覆盖明细的判法（`review-inputs.mjs::detailProblems`）：给定必审集合与视觉延期，逐例判结论与明细是否自洽。

    这里的必审集合是手写的；集合由谁、按什么生产（任务列齐、别名、原生视觉裁定）由上面几组真实链核。
    """

    FEATURE = "doc/features/REQ-DEMO"
    STORY = f"{FEATURE}/AR/story.md"
    SR = f"{FEATURE}/SR/design.md"
    OLD = f"{FEATURE}/assets/ux/old.{PICTURE_ID}.png"
    CORRECTIONS = f"{FEATURE}/AR/story-src/meetings/续期会/v1/corrections.json"
    HOME = f"{FEATURE}/assets/ux/home.{PICTURE_ID}.png"
    DRIVER = """
const m = await import(process.argv[1]);
let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const out = JSON.parse(raw).map(c => m.detailProblems(c.details, c.status, c.basis && {
  inputs: c.basis.inputs, gaps: c.basis.gaps, alias: new Map(),
  visual: c.basis.visual && { fact: c.basis.visual.fact, deferred: new Set(c.basis.visual.deferred) },
}, []));
process.stdout.write(JSON.stringify(out));
"""

    @staticmethod
    def basis(inputs: list[tuple[str, str]], deferred: list[str] | None = None) -> dict:
        return {"inputs": [{"path": rel, "purpose": why, "required": True, "missing": False, "digest": None} for rel, why in inputs],
                "gaps": [],
                "visual": None if deferred is None else {"fact": "看图能力：看不了图（adapter generic）", "deferred": deferred}}

    @staticmethod
    def details(examined: list[str], unreviewed: list[tuple[str, str]] = ()) -> dict:
        return {"blocking_findings": [], "advisories": [], "examined_inputs": list(examined),
                "unreviewed": [{"path": rel, "reason": why} for rel, why in unreviewed]}

    def judge(self, cases: list[dict]) -> list[list[str]]:
        module = DEV_EXT / "hooks/shared/review-inputs.mjs"
        r = subprocess.run(["node", "--input-type=module", "-e", self.DRIVER, module.resolve().as_uri()],
                           input=json.dumps(cases, ensure_ascii=False), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return json.loads(r.stdout)

    def test_every_case(self) -> None:
        whole = [(self.STORY, "审查对象：Story 正文"),
                 (self.SR, "设计未见引用的阅读稿（核是有据不用，还是漏了依据）"),
                 (self.OLD, "作者登记不用：旧版签约页，本需求不改签约页"),
                 (self.CORRECTIONS, "会议纠偏留痕")]
        visual = [(self.STORY, "审查对象：Story 正文"), (self.HOME, "登记的图片")]
        blind = "宿主看不了图，图面未核"
        # (名字, 明细, 结论, 必审集合, 每条问题各含的片段；空表示自洽)
        cases = [
            ("完整核源全读过", self.details([x for x, _ in whole]), "PASS", self.basis(whole), []),
            *[(f"漏报{why}", self.details([x for x, _ in whole if x != rel]), "PASS", self.basis(whole),
               [f"必审输入既没出现在 examined_inputs 也没列进 unreviewed：{rel}"])
              for rel, why in whole[1:]],
            ("看不了图、文本审完判 WARN", self.details([self.STORY], [(self.HOME, blind)]), "WARN",
             self.basis(visual, [self.HOME]), []),
            ("看不了图却判 PASS", self.details([self.STORY], [(self.HOME, blind)]), "PASS",
             self.basis(visual, [self.HOME]), [f"判了 PASS，图面却没核：{self.HOME}"]),
            ("图可延期、正文没读完判 WARN", self.details([], [(self.HOME, blind), (self.STORY, "没读完")]), "WARN",
             self.basis(visual, [self.HOME]), [f"判了 WARN，必审输入却有没核完的：{self.STORY}——"]),
            ("图不延期、图没核判 WARN", self.details([self.STORY], [(self.HOME, blind)]), "WARN",
             self.basis(visual, []), [f"判了 WARN，必审输入却有没核完的：{self.HOME}——"]),
            ("图不延期、图没核判 PASS", self.details([self.STORY], [(self.HOME, blind)]), "PASS",
             self.basis(visual), [f"判了 PASS，必审输入却有没核完的：{self.HOME}——"]),
        ]
        got = self.judge([{"details": d, "status": s, "basis": b} for _, d, s, b, _ in cases])
        for (name, _, _, _, want), problems in zip(cases, got):
            with self.subTest(case=name):
                self.assertEqual(len(want), len(problems), problems)
                for piece, problem in zip(want, problems):
                    self.assertIn(piece, problem)


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
        """仍开着的选择在逐章核查之前、按判据「核的先后」①对着本次 Story、Review 与蓝图判，结论写进回复；不要求读 Spec。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [{
            "id": "D1", "status": "open", "title": "超时由谁释放", "decider": "需求负责人",
            "clarification": "**要定的事**：超时由谁释放。"}]}, ensure_ascii=False), encoding="utf-8")
        task = self.inject()
        section = task.split("### 先核：仍开着的选择", 1)[1].split("\n### ", 1)[0]
        self.assertIn("写进回复", section)
        self.assertIn("记一条发现", section)
        self.assertIn("「核的先后」①", section)
        for gone in ("Spec", "acceptance.yaml", "证据格"):
            self.assertNotIn(gone, section, f"开着的选择还要对着「{gone}」判")
        self.assertIn("本次采用的上游原件里没有图。", task)
        self.assertNotIn("spec）里没有图", task)

    def test_the_task_carries_its_criteria(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text)
        self.assertIn("### 判据", text)

    def test_every_registered_criterion_is_sent(self) -> None:
        """判据文件登记几项，任务就发几项：读的是同一份，不靠「现在只有一条」。"""
        rules = self.root / "doc/extensions/rules/story-reader-rules.yaml"
        rules.write_text(rules.read_text(encoding="utf-8").rstrip("\n") + "\n  neutral_second_criterion:\n"
                         "    description: 第二条中性判据的说明。\n    severity: MAJOR\n"
                         "    ai_prompt_hint: 第二条判据怎么审。\n", encoding="utf-8")
        text = self.inject()
        for needle in ("### 判据 story_reader_review（BLOCKER）", "### 判据 neutral_second_criterion（MAJOR）",
                       "第二条中性判据的说明。", "第二条判据怎么审。"):
            self.assertIn(needle, text)

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
            json.dumps({"schema": 5, "sources": [], "inbox": [], "materials": [{"kind": "doc", "paths": ["RR/prd.md"]}],
                        "origins": [], "files": []}, ensure_ascii=False), encoding="utf-8")
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
        for needle in ("跨章对着读", "阻断发现", "**建议**", "空着与没审同形", "按实际关系判"):
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
                       "跨章对着读", "阻断发现", "**建议**", "空着与没审同形"):
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
        """任务只给一份文件索引与读法，被审文件与写作设计都按索引去读，任务里不嵌它们的全文；
        正文的阅读入口带作者区摘要，作者改字换任务，正文仍不嵌入。"""
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
        again = self.inject()
        self.assertNotEqual(task, again, "作者改了正文，阅读入口的作者区摘要没跟着换")
        self.assertNotIn("作者补的一句。", again, "Story 正文又嵌进了任务")

    def test_the_task_reads_the_adopted_versions_first(self) -> None:
        """核源先读业务来源与人签：上游原话在原件里，不拿作者摘要自证；蓝图与技术参考按问题回查。"""
        task = self.inject()
        reading = task.split("### 怎么读", 1)[1].split("\n### ", 1)[0]
        self.assertIn("1. 先读业务来源与人签", reading)
        self.assertIn("当前有效人答", reading.split("\n2. ", 1)[0])
        self.assertIn("按问题回查", reading.split("\n3. ", 1)[1])
        self.assertNotIn(".backups/local/AR-design", task, "上游 AR 不再被覆盖，没有覆盖备份可指")

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
        """结论按「报告怎么写」写：阻断与建议各进「发现」的哪几级、工作与依据写在哪、没有发现怎么写，与方法同处一份。

        输出要求与判据分在两个文件时，改一处就对不上；任务书的「报告怎么写」给章节与表头。
        """
        method = self.overlay_method()
        for needle in ("报告怎么写", "空着与没审同形", "阻断发现", "**建议**", "没有发现时写明没有发现"):
            self.assertIn(needle, method)
        for gone in ("汇总表", "YAML 明细", "为标记的一块", "review_scope", "「判据核对」"):
            self.assertNotIn(gone, method, f"旧的输出契约「{gone}」还在")
        task = self.inject()
        for needle in ("### 报告怎么写", "material_key: <派审时给的材料键", "conclusion: pass|warn|fail", "开头恰好两行"):
            self.assertIn(needle, task)

    def test_the_index_names_a_missing_required_source(self) -> None:
        """该有而读不到的来源在索引里点名：系统需求缺系统设计要说，本地需求没有它是正常的。"""
        feature = self.root / "doc" / "features" / FEATURE
        index = lambda name: self.inject(name).split("### 本次审查的材料", 1)[1].split("\n### ", 1)[0]  # noqa: E731
        self.assertNotIn("读不到系统设计（SR）", index(FEATURE), "本地单没有系统设计是正常的")
        remote = f"AR{FEATURE}"
        shutil.copytree(feature, feature.parent / remote)
        self.assertIn("读不到系统设计（SR）", index(remote), "系统需求缺必备来源没点名")

    def test_the_rules_judge_against_sources_not_the_design(self) -> None:
        """先按原材料独立判断，再用设计定位作者的安排——设计不是审查标准；方法只在判据文件。"""
        method = self.overlay_method()
        for needle in ("先独立想清楚", "写作设计", "设计漏掉的不因此算不在范围", "写了理由不等于理由成立",
                       "还开着的决定被写成已定", "蓝图与已登记的判断", "正文提到过", "真实待决写清了边界",
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
    reader = READER_TASK
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
        self.assertEqual("report_unreceived", self.result()["result"], "没接收的回复被当成了结论")
        again = self.prepared()
        self.assertEqual("pass", self.result()["result"])
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
