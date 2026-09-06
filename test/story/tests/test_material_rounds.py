"""一轮 = 一次材料状态 —— **界面参考也是材料**。

轮次指纹曾只算四份文本源（`RR/prd.md`、`SR/design.md`、`AR/design.md`、
`AR/upstream.md`）。补料如果只有界面图，转换后只落 `ux-reference/`，四份文本
一个字节没变 → 指纹不变 → 不算新一轮 → 关卡列表永不重置 → 流程卡死在
`import_and_reanalyze`。实跑撞到过一次：模型只能自己改机制层绕过去。

这一份锁的就是「什么算材料变了」这个定义的完整性。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STORY_SCRIPTS = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
FLOW = STORY_SCRIPTS / "story_flow.py"
MATERIALS = STORY_SCRIPTS / "materials.py"

sys.path.insert(0, str(STORY_SCRIPTS))
import story_flow  # noqa: E402
FEATURE = "AR90001"


class MaterialRoundCase(unittest.TestCase):
    """每个用例一份新工作区，跑真脚本、读真契约。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "RR").mkdir(parents=True)
        (self.feature_root / "SR").mkdir(parents=True)
        (self.feature_root / "AR").mkdir(parents=True)
        (self.feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n",
                                                         encoding="utf-8")
        (self.feature_root / "SR" / "design.md").write_text("# 系统设计\n\n分工。\n",
                                                            encoding="utf-8")
        (self.feature_root / "AR" / "design.md").write_text("# 提取件\n\n范围。\n",
                                                            encoding="utf-8")

    def run_flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def round_now(self) -> dict:
        proc = self.run_flow("round")
        self.assertEqual(proc.returncode, 0,
                         "round 失败：" + (proc.stdout or "") + (proc.stderr or ""))
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def add_ux(self, name: str, body: bytes = b"\x89PNG\r\n") -> None:
        ux = self.feature_root / "ux-reference"
        ux.mkdir(exist_ok=True)
        (ux / name).write_bytes(body)


class MaterialFingerprintCoversEveryInput(MaterialRoundCase):

    def test_a_ux_only_supplement_starts_a_new_round(self) -> None:
        """只往 `ux-reference/` 加一张图——那也是材料变了，必须算新一轮。"""
        first = self.round_now()
        self.add_ux("界面示意.png")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"),
                            "只补图片时指纹没变——补料等于没发生")
        self.assertGreater(second.get("round", 0), first.get("round", 0),
                           "指纹变了却没进新一轮")

    def test_a_text_only_supplement_still_starts_a_new_round(self) -> None:
        """补文字的老路一步没变。"""
        first = self.round_now()
        prd = self.feature_root / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n补充一段。\n",
                       encoding="utf-8")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"))
        self.assertGreater(second.get("round", 0), first.get("round", 0))

    def test_no_ux_directory_is_not_an_error(self) -> None:
        """没有界面参考的单子照常跑，不因为多了一个目录概念就变了口径。"""
        self.assertFalse((self.feature_root / "ux-reference").exists())
        first = self.round_now()
        self.assertTrue(first.get("materials"))
        self.assertEqual(first.get("round"), self.round_now().get("round"),
                         "材料没变，重跑 round 应当幂等")

    def test_rerunning_without_change_is_idempotent(self) -> None:
        """有界面参考时也一样：材料没动，重跑不造新轮次。"""
        self.add_ux("界面示意.png")
        first = self.round_now()
        second = self.round_now()
        self.assertEqual(first.get("materials"), second.get("materials"))
        self.assertEqual(first.get("round"), second.get("round"))

    def test_changing_one_image_is_a_new_round(self) -> None:
        """换掉同名图的内容也是材料变了——按文件内容算，不按文件名算。"""
        self.add_ux("界面示意.png")
        first = self.round_now()
        self.add_ux("界面示意.png", b"\x89PNG\r\n\x1a\n changed")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"))

    def test_the_deadlock_shape_does_not_come_back(self) -> None:
        """复刻实跑撞到的形状：第 1 轮四源齐，第 2 轮只加一张图。

        这一条是本文件的靶子。它红了就说明「什么算材料变了」的定义又缺了一块。
        """
        r1 = self.round_now()
        self.add_ux("签约页.png")
        self.add_ux("管理页.png")
        r2 = self.round_now()
        self.assertGreater(r2.get("round", 0), r1.get("round", 0),
                           "UX-only 补料没能开出新一轮——死锁又回来了")

    def test_the_input_definition_names_no_extras(self) -> None:
        """定义里不许出现「额外 / 附加 / extra」——那正是这个 bug 的根。

        把界面参考写成附加项，下一次谁再加一类材料源，又会被漏在版本外面。
        """
        body = MATERIALS.read_text(encoding="utf-8")
        for word in ("EXTRA", "额外", "附加"):
            self.assertNotIn(word, body,
                             "「%s」把某一类材料说成了二等的" % word)




class TheCaptionStoreHoldsTwoIndependentFacts(MaterialRoundCase):
    """一张图记两件事：它是什么，以及本需求为什么不用它。

    两件事各自可改：改说明不该把「为什么不用」抹掉，标记不用也不该把说明抹掉。
    库按 sha256 键，所以复制到第二个落点、换个名字，两件事都跟着这张图走。
    """

    def store(self):
        import importlib
        materials = importlib.import_module("materials")
        return materials

    def a_sha(self) -> str:
        return "sha256:" + "a" * 16

    def test_writing_a_reason_keeps_the_caption(self) -> None:
        m = self.store()
        m.write_caption(self.feature_root, self.a_sha(), "签约页")
        m.write_unused(self.feature_root, self.a_sha(), "属别的需求")
        entry = m.read_captions(self.feature_root)[self.a_sha()]
        self.assertEqual("签约页", entry["caption"])
        self.assertEqual("属别的需求", entry["unused"])

    def test_rewriting_the_caption_keeps_the_reason(self) -> None:
        m = self.store()
        m.write_unused(self.feature_root, self.a_sha(), "属别的需求")
        m.write_caption(self.feature_root, self.a_sha(), "签约页：换个说法")
        entry = m.read_captions(self.feature_root)[self.a_sha()]
        self.assertEqual("属别的需求", entry["unused"], "改说明把取舍抹掉了")

    def test_clearing_the_reason_keeps_the_caption(self) -> None:
        m = self.store()
        m.write_caption(self.feature_root, self.a_sha(), "签约页")
        m.write_unused(self.feature_root, self.a_sha(), "先不用")
        m.clear_unused(self.feature_root, self.a_sha())
        entry = m.read_captions(self.feature_root)[self.a_sha()]
        self.assertEqual("签约页", entry["caption"])
        self.assertNotIn("unused", entry)

    def test_a_bare_string_is_read_as_a_caption(self) -> None:
        """只记说明的写法：读到字符串按说明升格，已经登记过的一句不丢。"""
        m = self.store()
        path = self.feature_root / "ux-reference" / ".captions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({self.a_sha(): "签约页"}, ensure_ascii=False),
                        encoding="utf-8")
        self.assertEqual("签约页", m.read_captions(self.feature_root)[self.a_sha()]["caption"])


class CompleteThenMaterialChanged(MaterialRoundCase):
    """收口之后材料又变了：不开新轮，只记一笔；要重新决策显式 `reopen`。

    死锁的形状（首跑实测，耗掉 18 分钟）：
      收口 → 补一份说明文件 → 材料指纹变 → `round` 开出新轮 →
      新轮没有任何决策，而 `decide` 被 `status=complete` 挡住 →
      既走不下去也退不回来，模型最后**手改 story-flow.json 删掉那一轮**才出来。

    根因是轮次边界只看材料指纹，没有「收口之后材料又变了」这一态。
    收口的含义是「本轮范围已定、可以进 spec」，此后补个说明文件不该把流程推回未定。
    """

    def contract(self) -> dict:
        return json.loads(
            (self.feature_root / "AR" / "story-flow.json").read_text(encoding="utf-8"))

    def complete_it(self, status: str = "complete") -> None:
        """把契约摆成收口态——这里只测 round/reopen，不重演整条关卡链。"""
        self.round_now()
        path = self.feature_root / "AR" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_material_change_after_complete_opens_no_round(self) -> None:
        self.complete_it()
        before = len(self.contract()["rounds"])
        self.add_ux("signup.png")
        result = self.round_now()
        self.assertFalse(result.get("created"), "收口之后又开了新轮——死锁就是这么来的")
        self.assertTrue(result.get("afterComplete"))
        self.assertEqual(before, len(self.contract()["rounds"]))

    def test_the_change_is_recorded_not_swallowed(self) -> None:
        """不开轮不等于当没发生：那一轮的材料指纹要更新，并留下一条可查的记录。"""
        self.complete_it()
        digest_before = self.contract()["rounds"][-1]["materials"]["digest"]
        self.add_ux("manage.png")
        self.round_now()
        current = self.contract()["rounds"][-1]
        self.assertNotEqual(digest_before, current["materials"]["digest"],
                            "材料变了而指纹没跟上——那份快照就不是当下的事实了")
        note = current.get("materials_changed_after_complete") or {}
        self.assertIn("reopen", str(note.get("note", "")), "记一笔要说清出口在哪")

    def test_status_stays_at_complete(self) -> None:
        """补料不改变流程状态——它仍然是收口的，仍然可以进 spec。"""
        self.complete_it()
        self.add_ux("extra.png")
        self.round_now()
        self.assertEqual("complete", self.contract()["status"])

    def test_reopen_puts_it_back_and_leaves_a_trace(self) -> None:
        """`reopen` 是唯一出口：状态回到进行中，且谁在什么时候开的要留痕。"""
        self.complete_it()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        contract = self.contract()
        self.assertEqual("in_progress", contract["status"])
        self.assertEqual(1, len(contract.get("reopened") or []),
                         "撤销收口是有后果的判断，没有留痕就查不回来")

    def test_after_reopen_a_material_change_opens_a_round_again(self) -> None:
        """打开之后一切照旧：补料照常开新轮。"""
        self.complete_it()
        self.assertEqual(0, self.run_flow("reopen").returncode)
        before = len(self.contract()["rounds"])
        self.add_ux("after-reopen.png")
        result = self.round_now()
        self.assertTrue(result.get("created"))
        self.assertEqual(before + 1, len(self.contract()["rounds"]))

    def test_story_written_also_opens_no_round(self) -> None:
        """`story_written` 比 `complete` 更靠后，同样不开轮。

        story 的材料快照就是**当轮的 digest**——新轮一开，快照所指就换了一批材料，
        那份已经定稿的 story 就对不上它自己声称的依据了。
        """
        self.complete_it("story_written")
        before = len(self.contract()["rounds"])
        self.add_ux("after-written.png")
        result = self.round_now()
        self.assertFalse(result.get("created"), "成文登记之后还开新轮，story 的依据就换了")
        self.assertTrue(result.get("afterComplete"))
        self.assertEqual(before, len(self.contract()["rounds"]))

    def test_archived_also_opens_no_round(self) -> None:
        """已归档同理——它比成文登记还靠后。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["archived"] = {"at": "2026-09-04T00:00:00+08:00"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        before = len(self.contract()["rounds"])
        self.add_ux("after-archive.png")
        self.assertFalse(self.round_now().get("created"))
        self.assertEqual(before, len(self.contract()["rounds"]))

    def test_reopen_works_from_story_written_too(self) -> None:
        self.complete_it("story_written")
        self.assertEqual(0, self.run_flow("reopen").returncode)
        self.assertEqual("in_progress", self.contract()["status"])

    def test_reopen_undoes_the_story_registration(self) -> None:
        """已成文时 reopen 要把成文登记一起撤销——留着就成了两说。

        `story_written_at` 与 `story_src_digests` 是「这份 story 据以成文的依据」的快照。
        status 退回而它们还在：流程说还没成文，契约里却记着成文时刻与台账指纹，
        而台账冻结只看 status，重开后台账可以重算，那份快照指的却是重算之前的东西。
        """
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["story_written_at"] = "2026-09-04T00:00:00+08:00"
        data["story_src_digests"] = {"decisions.json": "sha", "copyedit.md": "sha"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        self.assertEqual(0, self.run_flow("reopen").returncode)
        contract = self.contract()
        self.assertNotIn("story_written_at", contract)
        self.assertNotIn("story_src_digests", contract)
        trace = contract["reopened"][-1]
        self.assertEqual("story_written", trace["from_status"])
        self.assertEqual(["story_src_digests", "story_written_at"],
                         trace["story_registration_undone"],
                         "撤销了什么要留痕——不然查不回来产物为什么对不上")

    def test_reopen_from_complete_has_nothing_to_undo(self) -> None:
        """还没成文时没有成文登记可撤——留痕里就是空的，不编造。"""
        self.complete_it()
        self.assertEqual(0, self.run_flow("reopen").returncode)
        self.assertEqual([], self.contract()["reopened"][-1]["story_registration_undone"])

    def test_reopen_refuses_when_not_complete(self) -> None:
        """没收口就没有要打开的东西——这条防的是把 reopen 当成万能重置键。"""
        self.round_now()
        proc = self.run_flow("reopen")
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在收口态", (proc.stdout or "") + (proc.stderr or ""))


class SupplementAnswersTheMaterialGate(MaterialRoundCase):
    """第一级停不停：第 1 轮无条件，第 2 轮起只看**本级**侧车在不在。

    人选「补充材料」就是对「材料够不够」的回答，补完不再问第二遍。要再停，
    得是模型在新一轮盘出新缺口并为**这一级**摆出选项。判据不看上一轮选了什么——
    先导后签与先签后导那样会判出两种结果，而顺序本来就不该有讲究。
    """

    def write_gate_options(self, gate: str = "material_scope") -> None:
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        options = ([{"key": "supplement", "label": "补充材料"},
                    {"key": "confirm_scope", "label": "材料充足，开始需求分析"}]
                   if gate == "material_scope"
                   else [{"key": "carry_all", "label": "按当前范围整体承载"}])
        (src / ".gate-options.json").write_text(
            json.dumps({"gate": gate, "options": options}, ensure_ascii=False),
            encoding="utf-8")

    def write_analysis_sidecars(self) -> None:
        """需求分析（S2b）的两份产出，round 消费进契约。"""
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        (src / ".positioning.json").write_text(json.dumps({
            "scope_source": "user_stated",
            "scope_text": "本 AR 承载自动充值签约与管理",
            "sr_related_ars": [],
        }, ensure_ascii=False), encoding="utf-8")
        (src / ".scope-options.json").write_text(json.dumps([
            {"key": "carry_all", "label": "按当前范围整体承载：签约、管理、扣款回执",
             "recommended": True},
        ], ensure_ascii=False), encoding="utf-8")

    def next_of(self) -> str:
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout[proc.stdout.index("{"):])["next"]

    def sign_supplement(self) -> subprocess.CompletedProcess:
        return self.run_flow("decide", "--gate", "material_scope", "--chosen", "supplement",
                             "--by", "human", "--basis", "补充材料，产品原稿已放入需求目录。")

    def put_inbox(self, name: str = "原稿.md") -> None:
        (self.feature_root / "inbox").mkdir(exist_ok=True)
        (self.feature_root / "inbox" / name).write_text(
            "# 原稿\n\n补的材料。\n", encoding="utf-8")

    def supplement_round(self) -> None:
        """走完一轮：摆选项 → 放料 → 人签补料 → 开新一轮。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        proc = self.sign_supplement()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.add_ux("signup.png")          # 料真的进来了，材料指纹随之变
        self.round_now()

    def out_of(self, proc) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    def test_material_in_the_inbox_says_import_it(self) -> None:
        """R64：料已在收件箱——直接导入，不再问人放好了没有。

        内网那次首次补料后模型仍让人「放好后回复」：`accepted` 只说「记录了」，
        它手上没有下一个动作，只好把问题又抛回去。
        """
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        out = self.out_of(self.sign_supplement())
        self.assertIn("直接跑", out)
        self.assertIn("不用再问人放好了没有", out)

    def test_material_already_imported_says_just_recount(self) -> None:
        """R64：原件已经进正文、只是指纹变了——重跑盘点即可，不用再导一次。"""
        self.round_now()
        self.write_gate_options()
        self.add_ux("signup.png")          # 先导后签：料已经落在正文侧
        out = self.out_of(self.sign_supplement())
        self.assertIn("重跑", out)
        self.assertNotIn("直接跑 `import_sources", out)

    def test_the_next_step_says_how_to_decide_whether_to_stop(self) -> None:
        """R65：盘点完怎么定停不停，要说出口。

        只说「重新盘点 → 重跑 round」的话，模型把上一轮的选项再摆一遍，流程又停一次。
        """
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplement().returncode)
        proc = self.run_flow("status")
        out = self.out_of(proc)
        self.assertIn("上一轮缺的补上了没有", out)
        self.assertIn("材料够了就直接进需求分析，不再问", out)

    def test_a_second_round_request_must_say_what_is_still_missing(self) -> None:
        """R65：补齐一轮之后再停，问的必须是剩余的缺口。"""
        self.supplement_round()
        self.write_gate_options()          # 补料选项没写 missing / why
        proc = self.sign_supplement()
        self.assertEqual(1, proc.returncode)
        out = self.out_of(proc)
        self.assertIn("missing", out)
        self.assertIn("剩余的缺口", out)

    def test_a_second_round_request_with_the_gap_named_is_accepted(self) -> None:
        """写清了还缺什么、为什么不够，就可以再停一次——这不是无效询问。"""
        self.supplement_round()
        src = self.feature_root / "AR" / "story-src"
        (src / ".gate-options.json").write_text(json.dumps({
            "gate": "material_scope",
            "options": [
                {"key": "supplement", "label": "补充材料",
                 "missing": "管理页的界面图",
                 "why": "补来的原稿只有签约页，管理页那一节没有可参照的界面"},
                {"key": "confirm_scope", "label": "材料充足，开始需求分析"},
            ]}, ensure_ascii=False), encoding="utf-8")
        self.put_inbox("管理页.md")
        self.assertEqual(0, self.sign_supplement().returncode)

    def test_a_non_request_option_needs_no_gap_fields(self) -> None:
        """「材料充足，继续」不是缺口，不受这一条约束。"""
        self.supplement_round()
        src = self.feature_root / "AR" / "story-src"
        (src / ".gate-options.json").write_text(json.dumps({
            "gate": "material_scope",
            "options": [{"key": "confirm_scope", "label": "材料充足，开始需求分析"}],
        }, ensure_ascii=False), encoding="utf-8")
        proc = self.run_flow("decide", "--gate", "material_scope",
                             "--chosen", "confirm_scope", "--by", "human",
                             "--basis", "用户回复：2（=材料充足）")
        self.assertEqual(0, proc.returncode, self.out_of(proc))

    def test_no_new_gap_means_no_second_stop(self) -> None:
        self.supplement_round()
        self.assertEqual("run_analysis", self.next_of(),
                         "补料之后又停了一次——问的是同一件事")

    def test_a_new_gap_stops_again(self) -> None:
        """模型在新一轮盘出新缺口 → 为这一级摆出选项 → 仍要停。"""
        self.supplement_round()
        self.write_gate_options()
        self.assertEqual("await_gate:material_scope", self.next_of(),
                         "模型摆出了新选项，却没有停")

    def test_the_first_round_still_stops(self) -> None:
        """第一轮照停：那一轮没有任何人对材料表过态。"""
        self.round_now()
        self.assertEqual("await_gate:material_scope", self.next_of())

    def test_signing_after_the_material_arrived_is_accepted(self) -> None:
        """先导后签：料先到了（已并入正文、指纹变了），人再回一句「已放进去了」。

        实跑里就是这个顺序——需求方把 docx 放进需求目录，再答复「补充材料」。
        只认「inbox 有未导入的」会把这一笔驳回，而料明明已经在手上。
        """
        self.round_now()
        self.write_gate_options()
        self.add_ux("signup.png")          # 料到了，指纹与本轮登记的不同
        proc = self.sign_supplement()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("import_and_reanalyze", self.next_of())

    def test_signing_before_the_material_arrives_is_accepted(self) -> None:
        """先签后导：人先签这一笔，料随后放进 inbox/。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        proc = self.sign_supplement()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_supplement_without_any_material_is_refused(self) -> None:
        """两条路都不成立——inbox 空、指纹也没变——才驳回。"""
        self.round_now()
        self.write_gate_options()
        proc = self.sign_supplement()
        self.assertEqual(2, proc.returncode)
        self.assertIn("材料没有变化", (proc.stdout or "") + (proc.stderr or ""))

    def test_the_second_level_is_not_pulled_back_by_its_own_sidecar(self) -> None:
        """补料轮走到第二级：为第二级摆的侧车不该把 next 拨回第一级。

        侧车不带级别时就是这样坏的——第一级读到「盘上有侧车」，判成材料上又有新缺口，
        于是 `next` 回到 `await_gate:material_scope`，而 `decide --gate scope_decision`
        被「当前这一步不是它」挡住，流程卡死在两级之间。
        """
        self.supplement_round()
        self.write_analysis_sidecars()
        self.round_now()
        self.assertEqual("await_gate:scope_decision", self.next_of())

        self.write_gate_options("scope_decision")
        self.assertEqual("await_gate:scope_decision", self.next_of(),
                         "第二级的侧车把流程拨回了第一级")
        proc = self.run_flow("decide", "--gate", "scope_decision", "--chosen", "carry_all",
                             "--by", "human", "--basis", "用户回复：1（=按当前范围整体承载）")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_a_sidecar_for_another_level_is_refused(self) -> None:
        """摆错级别当场拦下，不放它进契约。"""
        self.round_now()
        self.write_gate_options("scope_decision")
        proc = self.sign_supplement()
        self.assertEqual(1, proc.returncode)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("侧车是给 scope_decision 级摆的", out)


class OnlyTwoStopsAndBothUnconditional(unittest.TestCase):
    """本扩展新增的停等点只有两处，且都无条件。

    ## 为什么要锁

    白名单曾经是四条**条件句**：「材料缺口——**需要**人补料才能继续」。
    需不需要由模型判，等于把停等的开关交给被停的那一方。再配上 `--by ai`
    这一档（用户说「别逐个问」时代签关卡），实跑里就出现了：模型判「材料足够」
    → 条件不成立 → 不停 → 以自己的名义记掉关卡 → 材料补充环节整个被跳过。

    另一头是反的：契约要求模型在 S4 收口处问一次「本轮做到哪一步」，
    于是固定长出第三个停等点。那个问题在更早的两个地方已经有答案。
    """

    SKILL = (REPO_ROOT / "doc/extensions/skills/story/SKILL.md")
    FLOW = (REPO_ROOT / "doc/extensions/skills/story/scripts/story_flow.py")

    def skill(self) -> str:
        return self.SKILL.read_text(encoding="utf-8")

    def run_decide(self, root: Path, by: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.FLOW), "decide", "--feature", "AR90001",
             "--project-root", str(root), "--gate", "material_scope",
             "--chosen", "supplement", "--by", by, "--basis", "他说的原话"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def test_the_gate_decision_only_accepts_a_human_signature(self) -> None:
        """**物理门禁**：`--by ai` 连参数校验都过不去。

        只改文档没用——「记得停下问人」这种话模型会忘，门禁不会。
        """
        import ast
        body = self.FLOW.read_text(encoding="utf-8")
        tree = ast.parse(body)
        actors = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "ACTORS" for t in node.targets):
                actors = ast.literal_eval(node.value)
        self.assertEqual(("human",), actors, "关卡决策不该有人以外的签署者")

    def test_by_ai_is_refused_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR90001" / "AR").mkdir(parents=True)
            proc = self.run_decide(root, "ai")
            self.assertNotEqual(0, proc.returncode, "`--by ai` 竟然被接受了")
            self.assertIn("human", (proc.stdout or "") + (proc.stderr or ""))

    def test_the_whitelist_has_no_conditional_wording(self) -> None:
        """两处停等不许再写成条件句——条件由谁判，开关就在谁手里。"""
        text = self.skill()
        for conditional in ("需要人补料才能继续", "scope_gate 触发的"):
            self.assertNotIn(conditional, text,
                             "「%s」把停等的开关交回给了模型" % conditional)
        self.assertIn("必停", text, "两处停等要明写无条件")

    def test_the_spec_boundary_question_is_gone(self) -> None:
        """S4 收口处那一问退场——它固定长出第三个停等点。"""
        text = self.skill()
        for gone in ("一次问代替逐段问", "一次讲清", "做到哪一步"):
            self.assertNotIn(gone, text, "「%s」还在，进 spec 前仍会停一次" % gone)
        self.assertIn("直接进 spec，不问", text)

    def test_the_failure_exit_has_a_checkable_precondition(self) -> None:
        """「修不动了」是失败上报，不是确认点，而且前提必须可核。

        写成「同一处连续 3 次修不好」由模型自己判的话，试一次就能宣布修不好
        然后合法停下——与条件式白名单是同一个毛病。
        """
        text = self.skill()
        self.assertIn("失败出口", text, "失败上报要与停等点分开写")
        self.assertIn("连续三次运行", text, "前提要可核：连续三次 check 都报同一类")
        self.assertNotIn("触发白名单第 3 条", text, "旧的自述式出口还在被引用")

    def test_no_delegated_choice_path_remains(self) -> None:
        """代选路径整个退场——它就是材料环节被跳过的那条路。"""
        for rel in ("doc/extensions/skills/story/rules/scope_gate.md",
                    "doc/extensions/skills/story/rules/init_analysis.md",
                    "doc/extensions/skills/story/SKILL.md"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for gone in ('by:"ai"', "AI 代选", "代选永远不选"):
                self.assertNotIn(gone, text, "%s 里还留着代选路径：%s" % (rel, gone))


class TheManifestIsTheOnlyMaterialTruth(MaterialRoundCase):
    """材料现在是什么、导没导过，只有 `AR/story-src/materials.json` 说了算。"""

    def manifest(self) -> dict:
        path = self.feature_root / "AR" / "story-src" / "materials.json"
        self.assertTrue(path.is_file(), "round 之后没有材料清单")
        return json.loads(path.read_text(encoding="utf-8"))

    def contract(self) -> dict:
        return json.loads((self.feature_root / "AR" / "story-flow.json")
                          .read_text(encoding="utf-8"))

    def put_inbox(self, name: str, body: str, cls: str) -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / name).write_text(body, encoding="utf-8")
        cf = inbox / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        classify[name] = cls
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def import_now(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(STORY_SCRIPTS / "import_sources.py"),
             "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def test_the_contract_only_points_at_the_manifest(self) -> None:
        """契约不再自己存一份逐文件哈希，只留清单的位置与版本。

        同一份材料事实两处写，改一处忘一处时，两边都还理直气壮。
        """
        self.round_now()
        entry = self.contract()["rounds"][-1]
        self.assertNotIn("inputs", entry, "契约里还留着第二份材料哈希")
        self.assertEqual("AR/story-src/materials.json", entry["materials"]["path"])
        self.assertEqual(self.manifest()["digest"], entry["materials"]["digest"])

    def test_importing_leaves_no_receipt(self) -> None:
        """导入不再落一次性回执：本次导了什么，去清单里按磁盘现状问。"""
        self.put_inbox("上游需求.md", "# 上游\n\n正文。\n", "AR")
        proc = self.import_now()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertFalse((self.feature_root / "AR" / ".last-import.json").exists(),
                         "导入回执又回来了")
        for script in ("story_flow.py", "import_sources.py"):
            self.assertNotIn(".last-import",
                             (STORY_SCRIPTS / script).read_text(encoding="utf-8"),
                             "%s 还在读写导入回执" % script)

    def test_material_placed_but_not_imported_is_pending(self) -> None:
        """放进收件箱还没导 —— 材料版本不动，但清单要说这份料还没并入。"""
        before = self.round_now()
        self.put_inbox("上游需求.md", "# 上游\n\n正文。\n", "AR")
        after = self.round_now()
        self.assertEqual(before["materials"], after["materials"],
                         "料还没导进正文，材料版本就变了")
        sources = self.manifest()["sources"]
        self.assertEqual(["上游需求.md"], [s["file"] for s in sources])
        self.assertFalse(sources[0]["ingested"], "没导的料被记成已并入")

    def test_importing_marks_it_ingested_and_moves_the_version(self) -> None:
        """导入之后：正文变了 → 新一轮；清单说它已并入；契约记下本轮并入了它。"""
        before = self.round_now()
        self.put_inbox("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.assertEqual(0, self.import_now().returncode)
        after = self.round_now()
        self.assertNotEqual(before["materials"], after["materials"])
        self.assertTrue(self.manifest()["sources"][0]["ingested"])
        self.assertEqual(["上游需求.md"], self.contract()["rounds"][-1]["imported"])

    def test_replacing_a_source_with_new_content_is_pending_again(self) -> None:
        """同名原件换了内容就是新料 —— 任何一份「导过什么」的名单都记不住这件事。"""
        self.put_inbox("上游需求.md", "# 上游\n\n第一版。\n", "AR")
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        self.assertTrue(self.manifest()["sources"][0]["ingested"])
        self.put_inbox("上游需求.md", "# 上游\n\n第二版。\n", "AR")
        self.round_now()
        self.assertFalse(self.manifest()["sources"][0]["ingested"],
                         "同名料被换了内容，却仍算已并入")

    def test_reimporting_the_same_material_is_idempotent(self) -> None:
        """同一组材料重复导入，材料版本一个字节都不该动。"""
        self.put_inbox("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.assertEqual(0, self.import_now().returncode)
        first = self.round_now()
        self.assertEqual(0, self.import_now().returncode)
        second = self.round_now()
        self.assertEqual(first["materials"], second["materials"])

    def test_a_broken_classify_file_is_not_an_empty_inbox(self) -> None:
        """归类件坏了要停下报错，不能算成「收件箱是空的」放过去。"""
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "上游需求.md").write_text("# 上游\n", encoding="utf-8")
        (inbox / ".classify.json").write_text("{坏了", encoding="utf-8")
        proc = self.run_flow("round")
        self.assertEqual(1, proc.returncode, "坏归类件没有让 round 停下")
        self.assertIn("不是合法 JSON", proc.stdout + proc.stderr)

    def test_an_empty_feature_still_has_a_manifest(self) -> None:
        """真的一份材料都没有，也要有清单说「四份正文都不在」——空与没查是两件事。"""
        for rel in ("RR/prd.md", "SR/design.md", "AR/design.md"):
            (self.feature_root / rel).unlink()
        self.round_now()
        entries = {m["paths"][0]: m["sha256"] for m in self.manifest()["materials"]}
        self.assertEqual({"RR/prd.md": None, "SR/design.md": None,
                          "AR/design.md": None, "AR/upstream.md": None}, entries)

    def test_a_readme_change_does_not_move_any_image_identity(self) -> None:
        """图片的身份是它的内容与落点，不由任何一份说明文件的链接决定。"""
        self.add_ux("签约页.png")
        self.round_now()
        images = [m for m in self.manifest()["materials"] if m["kind"] == "image"]
        readme = self.feature_root / "ux-reference" / "README.md"
        readme.write_text("# 界面参考\n\n这里一个链接都没有。\n", encoding="utf-8")
        self.round_now()
        again = [m for m in self.manifest()["materials"] if m["kind"] == "image"]
        self.assertEqual(images, again, "改了说明文件，图片登记跟着变了")

    def test_revising_the_analysis_does_not_open_a_round(self) -> None:
        """同一材料版本内，初析可以从盘点版改到完整版，不划新轮次。"""
        first = self.round_now()
        analysis = self.feature_root / "AR" / "init-analysis.md"
        analysis.write_text("# 初析\n\n盘点版。\n", encoding="utf-8")
        second = self.round_now()
        self.assertEqual(first["round"], second["round"])
        analysis.write_text("# 初析\n\n完整版，结论改了。\n", encoding="utf-8")
        third = self.round_now()
        self.assertEqual(first["round"], third["round"],
                         "重写一遍分析就造出了一个新轮次")
        self.assertTrue(self.contract()["rounds"][-1]["analysis"]["sha256"],
                        "分析件哈希仍要照实登记，只是不划轮次")

    def test_the_flow_never_mirrors_a_framework_phase(self) -> None:
        """Story flow 只记材料、范围与承载，不镜像 Framework 的阶段状态。"""
        self.round_now()
        body = json.dumps(self.contract(), ensure_ascii=False)
        for word in ("highest_phase", "phase_source", "spec_done"):
            self.assertNotIn(word, body, "契约里长出了 Framework 阶段状态：%s" % word)


class OnlyTheManifestModuleHashesMaterial(unittest.TestCase):
    """材料哈希只有一处算法；对接层不知道清单的存在。"""

    def test_no_other_script_hashes_material_files(self) -> None:
        """全仓只有清单模块自己算材料文件的哈希。

        第二处算法一旦出现，两边差一个换行就会变成「材料每次都在变」。
        """
        offenders = [path.name for path in sorted(STORY_SCRIPTS.glob("*.py"))
                     if path.name != "materials.py"
                     and "read_bytes()).hexdigest" in path.read_text(encoding="utf-8")]
        self.assertEqual([], offenders, "这些脚本自己又算了一遍材料哈希：%s" % offenders)

    def test_the_data_layer_never_hears_about_the_manifest(self) -> None:
        """对接层的 js 各部署环境自备、不随包交付，不能要求它们跟着改。"""
        for name in ("story.js", "review.js", "token.js"):
            text = (STORY_SCRIPTS / name).read_text(encoding="utf-8")
            for word in ("materials.json", "manifest"):
                self.assertNotIn(word, text,
                                 "%s 里出现了 %s —— 清单的事不该落到对接层" % (name, word))


class AManifestAppearsWithoutAnyDataLayer(unittest.TestCase):
    """材料是谁放的都不影响清单：换一份不认识清单的替身取材，round 照样算得出来。"""

    def test_a_stand_in_data_layer_still_gets_a_manifest(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feature_root = root / "doc" / "features" / FEATURE
        # 替身「对接层」：只把正文与图片放到该在的位置，对清单一无所知
        (feature_root / "RR").mkdir(parents=True)
        (feature_root / "RR" / "prd.md").write_text("# 产品需求\n", encoding="utf-8")
        (feature_root / "ux-reference").mkdir(parents=True)
        (feature_root / "ux-reference" / "签约页.png").write_bytes(b"PNG")

        proc = subprocess.run(
            [sys.executable, str(FLOW), "round", "--feature", FEATURE,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        manifest = json.loads(
            (feature_root / "AR" / "story-src" / "materials.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(manifest["digest"])
        self.assertIn("ux-reference/签约页.png",
                      [p for m in manifest["materials"] for p in m["paths"]])


class TheManifestSurvivesTheStorySweep(unittest.TestCase):
    """成文登记时清扫 `story-src/`：材料清单留下，但不随稿冻结。

    它是材料真源，会随材料继续演化；定稿那一刻手里是哪版材料，记在契约当轮的
    `materials.digest` 里——那才是快照。把它也当台账冻结，材料一变 check 就报
    「台账被换过」，而那正是**正常**的。
    """

    def test_the_sweep_keeps_the_manifest(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "story-src"
        src.mkdir()
        (src / "materials.json").write_text("{}", encoding="utf-8")
        (src / "decisions.json").write_text("{}", encoding="utf-8")
        (src / "分章草稿.md").write_text("脚手架", encoding="utf-8")
        swept = story_flow.sweep_story_src(src)
        self.assertEqual(["分章草稿.md"], swept)
        self.assertTrue((src / "materials.json").is_file(), "材料清单被当成脚手架扫掉了")

    def test_the_manifest_is_not_a_frozen_ledger(self) -> None:
        self.assertNotIn("materials.json", story_flow.STORY_SRC_FROZEN,
                         "材料清单被当成随稿冻结的台账，材料一演化就会被判成台账被换过")


class DraftsLiveUntilRegistration(unittest.TestCase):
    """章草稿在登记前不能被扫掉，登记成功后才删。

    `check` 没过时作者要回到草稿接着改——清扫把它当中间件删了，他的起点就没了。
    登记成功之后 story 冻结，草稿失去用途，也不该留进归档。
    """

    def test_the_sweep_spares_the_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "story-src"
            (src / story_flow.DRAFTS_DIR).mkdir(parents=True)
            (src / story_flow.DRAFTS_DIR / "02-术语.md").write_text("写到一半", encoding="utf-8")
            (src / "decisions.json").write_text("[]", encoding="utf-8")
            (src / "候选池.md").write_text("脚手架", encoding="utf-8")
            swept = story_flow.sweep_story_src(src)
            self.assertIn("候选池.md", swept)
            self.assertNotIn(story_flow.DRAFTS_DIR, swept, "清扫把章草稿也删了")
            self.assertTrue((src / story_flow.DRAFTS_DIR / "02-术语.md").is_file())

    def test_drafts_are_not_frozen_into_the_ledger(self) -> None:
        """草稿不进冻结台账：它不是 story 据以成文的依据，是写它的过程。"""
        self.assertNotIn(story_flow.DRAFTS_DIR, story_flow.STORY_SRC_FROZEN)


class RegistrationReprojectsFirst(unittest.TestCase):
    """登记的顺序是 project → number → check。

    附录的机器区是 spec §9 与 knowledge-use.yaml 的投影，而真源在成文期间还会变；
    以登记这一次为准，否则归档件里留的是一份会漂移的副本。
    """

    def test_the_order_is_project_then_number_then_check(self) -> None:
        source = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
                  / "scripts" / "story_flow.py").read_text(encoding="utf-8")
        body = source.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        order = [cmd for cmd in ("\"project\"", "\"number\"", "\"check\"")
                 if cmd in body]
        self.assertEqual(['"project"', '"number"', '"check"'], order,
                         "登记时没有先按真源重投影")
        self.assertLess(body.index('"project"'), body.index('"number"'))

    def test_registration_deletes_the_drafts(self) -> None:
        source = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
                  / "scripts" / "story_flow.py").read_text(encoding="utf-8")
        body = source.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("DRAFTS_DIR", body, "登记成功后没有清理章草稿")


if __name__ == "__main__":
    unittest.main()
