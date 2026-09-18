"""一轮 = 一次材料状态 —— **界面参考也是材料**。

轮次指纹曾只算四份文本源（`RR/prd.md`、`SR/design.md`、`AR/design.md`、
`AR/story-src/upstream.md`）。补料如果只有界面图，转换后只落 `ux-reference/`，四份文本
一个字节没变 → 指纹不变 → 不算新一轮 → 关卡列表永不重置 → 流程停在
「回去导入再盘点」上出不来，导多少次都一样。模型只能自己改机制层绕过去。

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
STORY_SCRIPTS = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"
MATERIALS = STORY_SCRIPTS / "materials" / "registry.py"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.inputs import MATERIAL_CHOICES, MATERIAL_REQUEST_KEYS, material_options  # noqa: E402
from flow.state import CONTRACT, STORY_SRC_FROZEN  # noqa: E402
from materials import importer  # noqa: E402
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


class ReopenReportsWhatActuallyHappened(MaterialRoundCase):
    """重开写进盘之后，算下一步失败不能把重开报成失败；写入本身失败也不能报成成功。

    报错的后果是具体的：模型以为没重开、再跑一次 reopen，而那一次会被「不在收口态」挡回——
    它收到的两句话都与盘上的事实相反。用真实临时文件，在进程内注入失败。
    """

    def setUp(self) -> None:
        super().setUp()
        self.round_now()
        self.contract_path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(self.contract_path.read_text(encoding="utf-8"))
        data.update(status="story_written", story_written_at="2026-09-14T00:00:00+08:00",
                    story_src_digests={"decisions.json": "sha"})
        self.written = json.dumps(data, ensure_ascii=False, indent=2)
        self.contract_path.write_text(self.written, encoding="utf-8")

    def disk(self) -> dict:
        return json.loads(self.contract_path.read_text(encoding="utf-8"))

    def test_a_failing_next_step_still_reports_the_reopen(self) -> None:
        from unittest import mock  # noqa: PLC0415
        from flow import rounds  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415

        def boom(*_args, **_kwargs):
            raise FlowError("材料清单读不出（注入）")

        for name in ("live_materials", "next_step"):
            with self.subTest(fails=name):
                self.contract_path.write_text(self.written, encoding="utf-8")
                with mock.patch.object(rounds, name, boom):
                    result = rounds.cmd_reopen(self.feature_root)
                disk = self.disk()
                self.assertEqual("in_progress", disk["status"], "盘上没重开")
                self.assertNotIn("story_written_at", disk, "成文登记没撤销")
                self.assertEqual("in_progress", result["status"])
                self.assertIsNone(result["next"], "算不出来的下一步被编了一个")
                self.assertIn("材料清单读不出（注入）", result["action"], "没说清为什么算不出来")
                self.assertIn("不要再跑 reopen", result["action"], "诱导重跑 reopen")
                self.assertIn("story_flow.py status", result["action"], "没给出恢复命令")

    def test_a_failing_save_is_not_reported_as_success(self) -> None:
        from unittest import mock  # noqa: PLC0415
        from flow import rounds  # noqa: PLC0415

        with mock.patch.object(rounds, "save", side_effect=OSError("磁盘写不进（注入）")):
            with self.assertRaises(OSError):
                rounds.cmd_reopen(self.feature_root)
        self.assertEqual("story_written", self.disk()["status"], "写入失败却动了盘上的状态")


class RegisteringBeforeTheCloseSaysSoFirst(MaterialRoundCase):
    """没收口就来登记成文态：先说「还没收口」，算下一步失败也不顶掉这一句。"""

    def test_a_failing_next_step_does_not_hide_the_open_flow(self) -> None:
        from unittest import mock  # noqa: PLC0415
        from flow import lifecycle  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415

        self.round_now()

        def boom(*_args, **_kwargs):
            raise FlowError("材料清单读不出（注入）")

        for name in ("live_materials", "next_step"):
            with self.subTest(fails=name), mock.patch.object(lifecycle, name, boom):
                with self.assertRaises(FlowError) as caught:
                    lifecycle.cmd_story(self.feature_root, self.root)
                message = str(caught.exception)
                self.assertIn("还没收口", message, "材料那边的错顶掉了「还没收口」")
                self.assertIn("story_flow.py status", message, "没给出取下一步的命令")


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
        return importlib.import_module("materials.registry")

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
            (self.feature_root / "AR" / "story-src" / "story-flow.json").read_text(encoding="utf-8"))

    def complete_it(self, status: str = "complete") -> None:
        """把契约摆成收口态——这里只测 round/reopen，不重演整条关卡链。"""
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
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
        """不开轮不等于当没发生：那一轮的材料指纹要更新，日志说清出口在哪。"""
        self.complete_it()
        digest_before = self.contract()["rounds"][-1]["materials"]["digest"]
        self.add_ux("manage.png")
        proc = self.run_flow("round")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        current = self.contract()["rounds"][-1]
        self.assertNotEqual(digest_before, current["materials"]["digest"],
                            "材料变了而指纹没跟上——那份快照就不是当下的事实了")
        self.assertIn("reopen", proc.stderr, "记一笔要说清出口在哪")

    def test_status_stays_at_complete(self) -> None:
        """补料不改变流程状态——它仍然是收口的，仍然可以进 spec。"""
        self.complete_it()
        self.add_ux("extra.png")
        self.round_now()
        self.assertEqual("complete", self.contract()["status"])

    def test_reopen_puts_it_back_and_leaves_a_trace(self) -> None:
        """`reopen` 是唯一出口：状态回到进行中，日志说清从哪个状态退回。"""
        self.complete_it()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("in_progress", self.contract()["status"])
        self.assertIn("complete → in_progress", proc.stderr)

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

    def test_status_after_the_story_is_written_gives_no_import(self) -> None:
        """成文登记之后放料，`status` 不引导导入——那条路归 `round` 与 `reopen`。

        引导导入的话，材料会并进正文，而已经定稿的 story 声称的依据是当轮的快照，
        两边当场对不上。此后材料再变只有一个出口：显式 `reopen`。
        """
        self.complete_it("story_written")
        (self.feature_root / "inbox").mkdir(exist_ok=True)
        (self.feature_root / "inbox" / "补的稿.md").write_text(
            "# 补的稿\n\n后到的材料。\n", encoding="utf-8")
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertNotEqual("import_materials", payload["next"],
                            "成文之后还引导导入，story 的依据就被改掉了")
        self.assertEqual("run_archived", payload["next"])

    def put_inbox_file(self, name: str = "后到的稿.md") -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / name).write_text("# 后到的稿" + chr(10) * 2 + "冻结之后才来的材料。" + chr(10),
                                  encoding="utf-8")

    def test_a_frozen_story_still_says_what_is_sitting_in_the_inbox(self) -> None:
        """冻结之后放的料不能顺手导（导了 story 就对不上它自己声称的依据），
        但要**说出来**——不提的话那份文件从此没人知道，`round` 只会说「材料未变」。
        """
        self.complete_it("story_written")
        self.put_inbox_file("补的界面稿.md")
        proc = self.run_flow("round")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("补的界面稿.md", out, "收件箱里那份原件一个字都没提")
        self.assertIn("reopen", out, "没说清要纳入该走哪条路")

        proc = self.run_flow("status")
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual("run_archived", payload["next"], "冻结态的下一步被改掉了")
        self.assertIn("补的界面稿.md", (proc.stdout or "") + (proc.stderr or ""))

    def test_an_empty_inbox_after_freezing_says_nothing_extra(self) -> None:
        """没有待导入的原件就不多说一句——每次都提一遍，读的人就不看它了。"""
        self.complete_it("story_written")
        proc = self.run_flow("status")
        self.assertNotIn("收件箱里有", (proc.stdout or "") + (proc.stderr or ""))

    def test_archived_also_opens_no_round(self) -> None:
        """已归档同理——它比成文登记还靠后。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["archived"] = {"at": "2026-09-04T00:00:00+08:00"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        before = len(self.contract()["rounds"])
        self.add_ux("after-archive.png")
        self.assertFalse(self.round_now().get("created"))
        self.assertEqual(before, len(self.contract()["rounds"]))

    def test_an_archived_story_routes_to_done(self) -> None:
        """归档之后下一步是 done：不再引导跑 harness 与交付门，回流与补料各有出口。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["archived"] = {"at": "2026-09-04T00:00:00+08:00"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = self.run_flow("status")
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual("done", payload["next"])
        self.assertEqual("story_written", payload["status"], "归档不是新的状态值")
        self.assertIn("reopen", payload["action"])

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
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["story_written_at"] = "2026-09-04T00:00:00+08:00"
        data["story_src_digests"] = {"decisions.json": "sha"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        contract = self.contract()
        self.assertNotIn("story_written_at", contract)
        self.assertNotIn("story_src_digests", contract)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(["story_src_digests", "story_written_at"], out["storyRegistrationUndone"],
                         "撤销了什么要说出来——不然查不回来产物为什么对不上")

    def test_reopen_from_complete_has_nothing_to_undo(self) -> None:
        """还没成文时没有成文登记可撤——留痕里就是空的，不编造。"""
        self.complete_it()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual([], out["storyRegistrationUndone"])

    def test_reopen_refuses_when_not_complete(self) -> None:
        """没收口就没有要打开的东西——这条防的是把 reopen 当成万能重置键。"""
        self.round_now()
        proc = self.run_flow("reopen")
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在收口态", (proc.stdout or "") + (proc.stderr or ""))

    def test_reopen_says_what_to_do_next(self) -> None:
        """重开之后先做什么由现状回答——不说的话作者会直接去登记，而那一步会被拒。"""
        self.complete_it("story_written")
        proc = self.run_flow("reopen")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertTrue(payload.get("next") and payload.get("action"), f"reopen 没给出下一步：{payload}")
        self.assertIn("下一步", out)

    def test_registering_right_after_reopen_names_the_next_step(self) -> None:
        """reopen 之后直接 `story`：拒绝，但说出与 `status` 同一句的下一步，不只说「没收口」。"""
        self.complete_it("story_written")
        self.assertEqual(0, self.run_flow("reopen").returncode)
        status = self.run_flow("status")
        action = json.loads(status.stdout[status.stdout.index("{"):])["action"]
        proc = self.run_flow("story")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("下一步", out)
        self.assertIn(action[:16], out, "登记被拒时给的下一步与 status 不是同一句")

    def test_registering_twice_says_it_is_one_time(self) -> None:
        """已经成文登记过再来一次：说清只登记一次、要改走 reopen，不说成「没收口」。"""
        self.complete_it("story_written")
        proc = self.run_flow("story")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("只登记一次", out)
        self.assertIn("reopen", out)
        self.assertNotIn("没收口", out)


    def put_classified_inbox(self, name: str = "后到的稿.md") -> None:
        """放一份**已归类**的原件：`round` 看得见它，而它还没并入正文。"""
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / name).write_text("# " + name + "\n\n收口之后才到的材料。\n",
                                  encoding="utf-8")
        cf = inbox / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        classify[name] = "AR"
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def import_inbox(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(STORY_SCRIPTS / "import_sources.py"),
             "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))

    def status_payload(self) -> dict:
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def test_registering_a_new_baseline_does_not_clear_pending(self) -> None:
        """`round` 登记的是基准，不是「原件已经并入正文」。

        只看「材料变没变」的消费者在这一步之后就再也看不到那份原件：指纹已经跟上，
        而文件还躺在收件箱里。实测到的形状是起手照过、Story 照建，成文据以写的材料
        少一份而没有任何信号。
        """
        self.complete_it()
        self.put_classified_inbox()
        self.round_now()
        payload = self.status_payload()
        state = payload["material_state"]
        self.assertEqual(["后到的稿.md"], state["pending"], "未导入的原件没被报出来")
        self.assertFalse(state["changed"], "基准刚登记过，这一项本来就该是假")
        self.assertEqual("import_materials", payload["next"],
                         "基准登记之后就不再提那份原件了")

    def test_importing_then_registering_moves_on(self) -> None:
        """处置不是死路：导入并登记之后，材料事实干净，位置回到 spec 阶段。"""
        self.complete_it()
        self.put_classified_inbox()
        self.round_now()
        self.import_inbox()
        self.round_now()
        payload = self.status_payload()
        self.assertEqual([], payload["material_state"]["pending"])
        self.assertFalse(payload["material_state"]["changed"])
        self.assertNotEqual("import_materials", payload["next"])

    def test_the_status_json_carries_the_material_facts(self) -> None:
        """事实直接给出去：消费者按 pending/changed 判断，不去猜 `next` 的字面值。"""
        self.complete_it()
        payload = self.status_payload()
        self.assertEqual({"pending": [], "changed": False}, payload["material_state"])
        self.add_ux("manage.png")
        self.assertTrue(self.status_payload()["material_state"]["changed"])

class TheMaterialGateAsksForFacts(MaterialRoundCase):
    """第一级请人陈述事实：料放进去了，或者现有材料就是全部。

    够不够由作者盘点、由人定——**文件到了不等于内容够了**，机器不判这件事。
    人回的是哪一项，收件箱里的原件都会被导入；导完重新盘点，还缺什么才再停一次。
    上一轮缺的没补上照样可以再问，问的是「还缺什么」而不是「够不够」。
    """

    def gate_options(self) -> list[dict]:
        """第一级摆哪两项——**从合同取**，夹具与脚本读的是同一份登记。

        夹具自己抄一份 key 的话，合同改了它照样绿：它守的就不再是「两边一致」。
        """
        return [dict(o) for o in material_options()]

    def write_gate_options(self, gate: str = "material_scope",
                           options: list[dict] | None = None) -> None:
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        if options is None:
            options = (self.gate_options() if gate == "material_scope"
                       else [{"key": "carry_all", "label": "按当前范围整体承载"}])
        (src / ".gate-options.json").write_text(
            json.dumps({"gate": gate, "options": options}, ensure_ascii=False),
            encoding="utf-8")

    def write_gap_options(self, missing: str = "管理页的界面图",
                          why: str = "来的原稿只有签约页，管理页那一节没有可参照的界面",
                          with_gap: bool = True) -> None:
        """摆一次带缺口的第一级选项：`missing` / `why` 是第 2 轮起的硬要求。"""
        options = self.gate_options()
        if with_gap:
            for opt in options:
                if opt["key"] in MATERIAL_REQUEST_KEYS:
                    opt["missing"], opt["why"] = missing, why
        self.write_gate_options(options=options)

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
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        return json.loads(proc.stdout[proc.stdout.index("{"):])["next"]

    def sign(self, chosen: str) -> subprocess.CompletedProcess:
        return self.run_flow("decide", "--gate", "material_scope", "--chosen", chosen,
                             "--basis", f"用户回复：{chosen}")

    def sign_supplied(self) -> subprocess.CompletedProcess:
        return self.sign(MATERIAL_REQUEST_KEYS[0])

    def put_inbox(self, name: str = "原稿.md") -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / name).write_text(f"# {name}\n\n后放进来的材料。\n", encoding="utf-8")
        cf = inbox / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        classify[name] = "AR"
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def import_now(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(STORY_SCRIPTS / "import_sources.py"),
             "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        self.assertEqual(0, proc.returncode, self.out_of(proc))

    def one_supply_round(self) -> None:
        """走完一次完整的补料：摆选项 → 放料 → 人陈述事实 → 导入 → 开新一轮。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        self.import_now()
        self.round_now()

    def out_of(self, proc) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    # -- 人回哪一项，料都进来 -------------------------------------------------

    def test_the_first_round_always_stops(self) -> None:
        """第一轮照停：那一轮没有任何人对材料表过态。"""
        self.round_now()
        self.assertEqual("await_gate:material_scope", self.next_of())

    def test_material_on_disk_is_imported_before_anyone_answers(self) -> None:
        """料到了，关卡还没人回答——下一步就是导入，不必等表态。

        等表态才导的话，人回答之前流程里每一个判断都建立在一份不全的材料上；
        而文件已经在盘上，导入是脚本的活。
        """
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())

    def test_answering_still_works_while_the_import_is_pending(self) -> None:
        """`status` 说去导入，不挡人表态——两件事互不排斥。

        表态的前置是「本轮这一级还没定」，不是「下一步恰好是这一级」：
        挂在后者上的话，人刚放好料那一笔就永远签不下去。
        """
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())
        proc = self.sign_supplied()
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        self.assertEqual("import_materials", self.next_of(), "签完下一步变了")

    def test_the_same_level_cannot_be_signed_twice_in_one_round(self) -> None:
        """本轮这一级定过了就不再收——材料再变会开新一轮，那时才轮到重新表态。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        self.write_gate_options()
        proc = self.sign("confirm_scope")
        self.assertEqual(1, proc.returncode, "同一轮里签了两次")
        self.assertIn("本轮第一级已经定了", self.out_of(proc))

    def test_after_a_rejection_new_material_points_at_the_import(self) -> None:
        """上一笔被驳回、人这才把料放上来：下一步是导入，不是再问一遍。"""
        self.round_now()
        self.write_gate_options()
        self.assertEqual(2, self.sign_supplied().returncode)
        self.assertEqual("await_gate:material_scope", self.next_of())
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())

    def test_saying_the_material_is_all_there_still_imports_the_inbox(self) -> None:
        """人说「现有材料就是全部」，收件箱里的原件照样先导入。

        不导的话，那份料要到成文登记时才被发现，之前每个判断都建立在一份不全的材料上。
        人回的是「不再补了」，不是「盘上那份不算数」。
        """
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual(0, self.sign("confirm_scope").returncode)
        self.assertEqual("import_materials", self.next_of())

    def test_the_import_step_names_the_files_and_gives_the_command(self) -> None:
        """命令给全、点名是哪几件——不问人，直接做。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox("签约页.md")
        self.assertEqual(0, self.sign("confirm_scope").returncode)
        proc = self.run_flow("status")
        out = self.out_of(proc)
        self.assertIn("import_sources.py --feature", out, "没给出可跑的导入命令")
        self.assertIn("签约页.md", out, "没点名要导的是哪一件")

    def test_after_importing_it_asks_to_register_the_new_round(self) -> None:
        """导完材料就变了：先登记新一轮，再拿新材料重新盘点。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        self.import_now()
        self.assertEqual("run_round", self.next_of())

    # -- 「放进去了」是一句会被当场核对的事实 --------------------------------

    def test_saying_supplied_with_material_in_the_inbox_is_accepted(self) -> None:
        """人把料放进收件箱、回一句「放进去了」——成立，下一步是导入。"""
        self.round_now()
        self.write_gate_options()
        self.put_inbox()
        proc = self.sign_supplied()
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        self.assertEqual("import_materials", self.next_of())

    def test_saying_supplied_after_the_material_landed_is_accepted(self) -> None:
        """料已经并进正文、只是本轮还没登记——同样成立，下一步是登记新一轮。

        「料到没到」看的是磁盘：收件箱里有没导的，或者材料指纹已经不是本轮那个。
        只认前一种的话，料先落进正文的那条路会被驳回，而料明明已经在手上。
        """
        self.round_now()
        self.write_gate_options()
        self.add_ux("signup.png")
        proc = self.sign_supplied()
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        self.assertEqual("run_round", self.next_of())

    def test_saying_supplied_with_nothing_on_disk_is_refused(self) -> None:
        """盘上什么都没有——那一笔记下去下一步无处可去，原地重提。"""
        self.round_now()
        self.write_gate_options()
        proc = self.sign_supplied()
        self.assertEqual(2, proc.returncode)
        self.assertIn("收件箱里没有新文件", self.out_of(proc))
        self.assertEqual("await_gate:material_scope", self.next_of())

    # -- 导入之后：还缺什么才再停 --------------------------------------------

    def test_no_new_gap_goes_straight_to_analysis(self) -> None:
        """盘完不缺了就直接进需求分析，不把上一轮的选项再摆一遍。"""
        self.one_supply_round()
        self.assertEqual("run_analysis", self.next_of())

    def test_a_new_gap_stops_again(self) -> None:
        """盘出剩下的缺口、写进侧车 → 再停一次。这不是无效询问。"""
        self.one_supply_round()
        self.write_gap_options()
        self.assertEqual("await_gate:material_scope", self.next_of())

    def test_the_same_gap_can_be_asked_again(self) -> None:
        """上一轮缺的没补上，照样可以再问——问的是「还缺什么」，不是「够不够」。

        「人上一次已经回答过」不成立：他上一次回答的是上一轮的缺口。
        """
        self.one_supply_round()
        self.write_gap_options(missing="管理页的界面图", why="这一份补来的还是签约页")
        self.assertEqual("await_gate:material_scope", self.next_of())
        self.put_inbox("管理页.md")
        self.assertEqual(0, self.sign_supplied().returncode)

    def test_a_second_round_request_must_say_what_is_still_missing(self) -> None:
        """补过一轮之后再停，问的必须是**剩余**的缺口，不能把旧选项原样再摆。"""
        self.one_supply_round()
        self.write_gap_options(with_gap=False)
        proc = self.sign_supplied()
        self.assertEqual(1, proc.returncode)
        out = self.out_of(proc)
        self.assertIn("missing", out)
        self.assertIn("剩余的缺口", out)

    def test_a_non_request_option_needs_no_gap_fields(self) -> None:
        """「现有材料就是全部」不是缺口，不受这一条约束。"""
        self.one_supply_round()
        self.write_gate_options(options=[
            o for o in self.gate_options()
            if o["key"] not in MATERIAL_REQUEST_KEYS])
        proc = self.sign("confirm_scope")
        self.assertEqual(0, proc.returncode, self.out_of(proc))

    def test_status_refuses_to_stop_on_a_sidecar_that_will_be_rejected(self) -> None:
        """校验要在 `status` 决定停不停之前。

        只写在 `decide` 里的话，顺序是：`status` 说停 → 人被问了一次 → `decide` 才拒收。
        人已经答过，缺的字段却要模型回头补，那一次询问白问了。
        """
        self.one_supply_round()
        self.write_gap_options(with_gap=False)
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual("fix_gate_options", payload["next"],
                         "侧车立不住却先把人拦下来问了")
        self.assertIn("missing", self.out_of(proc))

    # -- 三级共用一个侧车文件名，级别要写明 ----------------------------------

    def test_the_second_level_is_not_pulled_back_by_its_own_sidecar(self) -> None:
        """走到第二级：为第二级摆的侧车不该把 next 拨回第一级。

        侧车不带级别时就是这样坏的——第一级读到「盘上有侧车」，判成材料上又有新缺口，
        于是 `next` 回到第一级，而 `decide --gate scope_decision` 被
        「当前这一步不是它」挡住，流程卡死在两级之间。
        """
        self.one_supply_round()
        self.write_analysis_sidecars()
        self.round_now()
        self.assertEqual("await_gate:scope_decision", self.next_of())

        self.write_gate_options("scope_decision")
        self.assertEqual("await_gate:scope_decision", self.next_of(),
                         "第二级的侧车把流程拨回了第一级")
        proc = self.run_flow("decide", "--gate", "scope_decision", "--chosen", "carry_all",
                             "--basis", "用户回复：1（=按当前范围整体承载）")
        self.assertEqual(0, proc.returncode, self.out_of(proc))

    def test_a_sidecar_for_another_level_is_refused(self) -> None:
        """摆错级别当场拦下，不放它进契约。"""
        self.round_now()
        self.write_gate_options("scope_decision")
        proc = self.sign_supplied()
        self.assertEqual(1, proc.returncode)
        self.assertIn("侧车是给 scope_decision 级摆的", self.out_of(proc))

    # -- 选项集只有一处登记 ---------------------------------------------------

    def test_the_labels_are_fixed_whatever_the_author_writes(self) -> None:
        """两句标签固定：作者写了自己的措辞，落进契约的仍是合同那两句。

        实跑里他把「材料已补齐，放进 inbox，请导入」改成了「**界面设计图**已放进…」——
        往标签里塞了一个具体类别。标签可改写的话，摆给人的那句话是合同给的还是他当场
        编的，事后分不出来，而那正是「他问了什么」的全部内容。本轮缺什么走 missing / why。
        """
        self.round_now()
        编的 = [dict(o, label="界面设计图已放进 doc/features/AR90001/inbox/，请导入")
              for o in self.gate_options()]
        self.write_gate_options(options=编的)
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        gates = json.loads((self.feature_root / "AR" / "story-src" / "story-flow.json")
                           .read_text(encoding="utf-8"))["rounds"][-1]["gates"]
        landed = {o["key"]: o.get("label") for o in gates[-1]["options"]}
        for o in material_options():
            self.assertEqual(o["label"], landed[o["key"]],
                             f"{o['key']} 的标签被作者的措辞盖掉了")

    def test_the_option_keys_live_in_the_contract_only(self) -> None:
        """键只登记在合同里：脚本与流程校验都从那里读，谁也不另存一份字面。

        各存一份的话，只改一处，`decide` 写进契约的选择会在阶段门禁上被判非法——
        而那两处相隔一个目录，改的人看不见另一处。
        """
        contract = json.loads(
            (STORY_SCRIPTS.parents[1] / "contracts" / "story-chapters.json")
            .read_text(encoding="utf-8"))
        keys = [o["key"] for o in contract["gates"]["material_scope"]["options"]]
        self.assertEqual(list(MATERIAL_CHOICES), keys)
        for path in (FLOW, STORY_SCRIPTS / "flow" / "check.mjs"):
            text = path.read_text(encoding="utf-8")
            for key in keys:
                self.assertNotIn(f"'{key}'", text, f"{path.name} 里还留着 {key} 的字面")
                self.assertNotIn(f'"{key}"', text, f"{path.name} 里还留着 {key} 的字面")


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
    FLOW = (REPO_ROOT / "doc/extensions/skills/story/scripts/core/story_flow.py")

    def skill(self) -> str:
        return self.SKILL.read_text(encoding="utf-8")

    def test_there_is_no_signer_to_choose(self) -> None:
        """**物理门禁**：没有「谁签的」这个参数，代签连参数校验都过不去。

        只改文档没用——「记得停下问人」这种话模型会忘，门禁不会。
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR90001" / "AR").mkdir(parents=True)
            proc = subprocess.run(
                [sys.executable, str(self.FLOW), "decide", "--feature", "AR90001",
                 "--project-root", str(root), "--gate", "material_scope",
                 "--chosen", MATERIAL_CHOICES[0], "--by", "ai", "--basis", "他说的原话"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, cwd=str(REPO_ROOT))
            self.assertNotEqual(0, proc.returncode, "代签参数竟然被接受了")
            self.assertIn("--by", proc.stderr)

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
        return json.loads((self.feature_root / "AR" / "story-src" / "story-flow.json")
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
        """契约不再自己存一份逐文件哈希，只留清单的版本（清单位置是固定的，不另记）。

        同一份材料事实两处写，改一处忘一处时，两边都还理直气壮。
        """
        self.round_now()
        entry = self.contract()["rounds"][-1]
        self.assertNotIn("inputs", entry, "契约里还留着第二份材料哈希")
        self.assertEqual({"digest"}, set(entry["materials"]), "契约里材料只该记版本")
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
        """导入之后：正文变了 → 新一轮；清单说它已并入（导过什么只在清单里，契约不再记一遍）。"""
        before = self.round_now()
        self.put_inbox("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.assertEqual(0, self.import_now().returncode)
        after = self.round_now()
        self.assertNotEqual(before["materials"], after["materials"])
        self.assertTrue(self.manifest()["sources"][0]["ingested"])
        self.assertNotIn("imported", self.contract()["rounds"][-1], "并入名单又落回契约")

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
                          "AR/design.md": None, "AR/story-src/upstream.md": None}, entries)

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
        analysis = self.feature_root / "AR" / "story-src" / "init-analysis.md"
        analysis.write_text("# 初析\n\n盘点版。\n", encoding="utf-8")
        second = self.round_now()
        self.assertEqual(first["round"], second["round"])
        analysis.write_text("# 初析\n\n完整版，结论改了。\n", encoding="utf-8")
        third = self.round_now()
        self.assertEqual(first["round"], third["round"],
                         "重写一遍分析就造出了一个新轮次")

    def test_the_contract_records_no_field_without_a_reader(self) -> None:
        """契约只记有读者的事实：分析件哈希与需求名没有任何判据读，不写。"""
        self.round_now()
        contract = self.contract()
        self.assertNotIn("feature", contract, "需求名又写回契约了——目录名就是它")
        self.assertNotIn("analysis", contract["rounds"][-1], "分析件哈希又写回契约了")

    def test_status_reports_when_the_story_was_registered(self) -> None:
        """成文登记的时刻由 status 报出来——契约里这一笔留痕的读者就是它。"""
        from flow import lifecycle  # noqa: PLC0415
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["story_written_at"] = "2026-09-14T00:00:00+08:00"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual("2026-09-14T00:00:00+08:00",
                         lifecycle.cmd_status(self.feature_root)["story_written_at"])

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
            text = (STORY_SCRIPTS.parent / "adapters" / name).read_text(encoding="utf-8")
            for word in ("materials.json", "manifest"):
                self.assertNotIn(word, text,
                                 "%s 里出现了 %s —— 清单的事不该落到对接层" % (name, word))


class SourceDocumentsComeFromTheContract(unittest.TestCase):
    """正文来源的路径只在章节合同登记一份：材料清单与导入落点都从那里取。

    两处各写一份的话，合同改了来源路径，清单仍按旧路径算指纹，导入仍往旧路径写。
    """

    CONTRACT = STORY_SCRIPTS.parents[1] / "contracts" / "story-chapters.json"

    def test_the_manifest_and_the_import_read_the_contract(self) -> None:
        from materials import registry  # noqa: PLC0415
        sources = json.loads(self.CONTRACT.read_text(encoding="utf-8"))["sources"]
        upstream = [d["path"] for d in sources.values() if not d.get("derived")]
        self.assertEqual(upstream, registry.source_docs(), "清单的正文来源不是合同登记的那几份")
        self.assertEqual(sources["UPSTREAM"]["path"], importer.doc_targets()["AR"].as_posix(),
                         "AR 类补料的落点不是合同登记的那一份")


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


class TheManifestIsNotAFrozenLedger(unittest.TestCase):
    """材料清单留在 `story-src/`，但不随稿冻结。

    它是材料真源，会随材料继续演化；定稿那一刻手里是哪版材料，记在契约当轮的
    `materials.digest` 里——那才是快照。把它也当台账冻结，材料一变 check 就报
    「台账被换过」，而那正是**正常**的。
    """

    def test_the_manifest_is_not_a_frozen_ledger(self) -> None:
        self.assertNotIn("materials.json", STORY_SRC_FROZEN,
                         "材料清单被当成随稿冻结的台账，材料一演化就会被判成台账被换过")


class TheMovedInThreeAreNotFrozenLedgers(unittest.TestCase):
    """流程契约、需求分析件、导入落点住在 `story-src/`，但都不随稿冻结。

    三件在登记之后还要写：契约要记归档态、`reopen` 要撤销登记，清单与落点随材料重算，
    分析件随初析演进。当成台账冻结，登记之后的每一步都会被判成
    「台账被换过」。
    """

    NAMES = property(lambda self: [
        CONTRACT[-1], "init-analysis.md",
        importer.doc_targets()["AR"].name,
    ])

    def test_none_of_them_is_a_frozen_ledger(self) -> None:
        """三件都留，但都不随稿冻结——冻结的是「据以成文的依据」，它们还要继续变。"""
        for name in self.NAMES:
            self.assertNotIn(name, STORY_SRC_FROZEN)

    def test_they_live_under_story_src_not_the_ar_root(self) -> None:
        """路径本身就是判据：`AR/` 根下只放交付文档，辅助件在 `story-src/` 这一层。"""
        self.assertEqual(("AR", "story-src", "story-flow.json"), CONTRACT)
        self.assertEqual("AR/story-src/upstream.md",
                         importer.doc_targets()["AR"].as_posix())


class DraftsAreNotFrozenIntoTheLedger(unittest.TestCase):
    """草稿不进冻结台账：它不是 story 据以成文的依据，是写它的过程。"""

    def test_drafts_are_not_frozen_into_the_ledger(self) -> None:
        self.assertNotIn("drafts", STORY_SRC_FROZEN)


class RegistrationReprojectsFirst(unittest.TestCase):
    """登记的顺序是 project → number → check。

    附录的机器区是 spec §9 与 knowledge-use.yaml 的投影，而真源在成文期间还会变；
    以登记这一次为准，否则归档件里留的是一份会漂移的副本。
    """

    def test_the_order_is_project_then_number_then_check(self) -> None:
        source = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
                  / "core" / "flow" / "lifecycle.py").read_text(encoding="utf-8")
        body = source.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        order = [cmd for cmd in ("\"project\"", "\"number\"", "\"check\"")
                 if cmd in body]
        self.assertEqual(['"project"', '"number"', '"check"'], order,
                         "登记时没有先按真源重投影")
        self.assertLess(body.index('"project"'), body.index('"number"'))

    def test_registration_deletes_nothing_under_story_src(self) -> None:
        """登记不删 `story-src/` 里的任何过程件——它们是「这份 story 怎么写出来的」现场。

        过程件走不漏：归档只上传 story.md 与 review.md，这一层整个留在本地。
        删掉的代价倒是实的——`reopen` 之后作者要改某一章，手上却没有可改的东西。
        """
        source = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
                  / "core" / "flow" / "lifecycle.py").read_text(encoding="utf-8")
        body = source.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        for gone in ("rmtree", "unlink", "sweep"):
            self.assertNotIn(gone, body, f"登记还在删 story-src/ 下的东西（{gone}）")


if __name__ == "__main__":
    unittest.main()
