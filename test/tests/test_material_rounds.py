"""一轮 = 一次材料状态 —— **界面参考也是材料**。

轮次指纹曾只算四份文本源（`RR/prd.md`、`SR/design.md`、`AR/design.md`、
`AR/story-src/upstream.md`）。补料如果只有界面图，转换后只落 `ux-reference/`，四份文本
一个字节没变 → 指纹不变 → 不算新一轮 → 关卡列表永不重置 → 流程停在
「回去导入再盘点」上出不来，导多少次都一样。模型只能自己改机制层绕过去。

这一份锁的就是「什么算材料变了」这个定义的完整性。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ext_workspace import DEV_EXT, DEV_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"
MATERIALS = STORY_SCRIPTS / "materials" / "registry.py"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.inputs import MATERIAL_CHOICES, MATERIAL_REQUEST_KEYS, material_options  # noqa: E402
from flow.state import CONTRACT, STORY_REGISTERED, ledger_digest  # noqa: E402
from materials import importer  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import write_gaps  # noqa: E402
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
                    story_digests={"AR/story-src/decisions.json": "sha"})
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
        """把契约摆成收口态——这里只测 round/reopen，不重演整条关卡链。已登记的带上此刻的登记指纹。"""
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        if status == "story_written":
            data["story_digests"] = {rel: ledger_digest(self.feature_root / rel) for rel in STORY_REGISTERED}
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
        (inbox / name).write_text("# 后到的稿" + chr(10) * 2 + "登记之后才来的材料。" + chr(10),
                                  encoding="utf-8")

    def test_a_registered_story_still_says_what_is_sitting_in_the_inbox(self) -> None:
        """登记之后放的料不顺手导（导了 story 就对不上它据以成文的依据），
        但要**说出来**并给出路：导入、登记到本轮、改完重跑 `story`——不提的话那份文件从此没人知道。
        """
        self.complete_it("story_written")
        self.put_inbox_file("补的界面稿.md")
        proc = self.run_flow("round")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("补的界面稿.md", out, "收件箱里那份原件一个字都没提")
        self.assertIn("重跑 `story`", out, "没说清要纳入该走哪条路")

        proc = self.run_flow("status")
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual("run_archived", payload["next"], "已登记的下一步被改掉了")
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
        """重拍范围时成文登记一起作废：范围定了之后 story 按新范围重新登记。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["story_written_at"] = "2026-09-04T00:00:00+08:00"
        data["story_digests"] = {"AR/story-src/decisions.json": "sha"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        contract = self.contract()
        self.assertNotIn("story_written_at", contract)
        self.assertNotIn("story_digests", contract)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(["story_digests", "story_written_at"], out["storyRegistrationUndone"],
                         "作废了什么要说出来——不然查不回来产物为什么对不上")

    def test_reopen_opens_a_round_for_the_scope_gate(self) -> None:
        """材料没变也另开一轮：当前轮已记的范围关卡不替重拍授权，下一步回到范围关卡。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        before = data["rounds"][-1]
        before["positioning"] = {"scope_text": "整单", "sr_related_ars": []}
        before["scope_options"] = [{"key": "all", "label": "整体承载"}]
        before["gates"] = [{"gate": "scope_decision", "chosen": "all", "outcome": "accepted", "by": "human"}]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        self.assertEqual(0, self.run_flow("reopen").returncode)
        rounds = self.contract()["rounds"]
        self.assertEqual(len(data["rounds"]) + 1, len(rounds))
        self.assertEqual(before["materials"], rounds[-1]["materials"], "重拍沿用本轮的材料基准")
        self.assertEqual([], rounds[-1]["gates"])
        status = self.run_flow("status")
        payload = json.loads(status.stdout[status.stdout.index("{"):])
        self.assertEqual("await_gate:scope_decision", payload["next"],
                         "重开之后没回到范围关卡：当前轮已记的范围替重拍授权了")

    def test_reopen_waits_for_an_open_update(self) -> None:
        """update 这一轮开着时不重拍：它沿用已定范围，先收口这一轮。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["update"] = {"open": "20260926-000000"}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = self.run_flow("reopen")
        self.assertEqual(1, proc.returncode)
        self.assertIn("update", proc.stdout + proc.stderr)
        self.assertEqual("story_written", self.contract()["status"])

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
        self.assertIn("还没收口", (proc.stdout or "") + (proc.stderr or ""))

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

    def test_registering_again_replaces_the_registration(self) -> None:
        """已经登记过再跑 `story`：上一次登记作废、按当前内容重新登记。

        这里盘上没有 story.md，登记失败——状态停在已收口、未登记，说的是缺 story，
        不是「只登记一次」，也不是「没收口」。
        """
        self.complete_it("story_written")
        proc = self.run_flow("story")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("重新登记", out)
        self.assertIn("AR/story.md 不存在", out)
        self.assertNotIn("没收口", out)
        self.assertEqual("complete", self.contract()["status"])


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
    作者把缺口写进缺口文件，问法（两项固定、顺序固定、推荐按缺口算）由 `status` 生成；
    人回的是哪一项，收件箱里的原件都会被导入；导完重新盘点，还缺什么才再停一次。
    """

    def src(self) -> Path:
        return self.feature_root / "AR" / "story-src"

    def gaps(self, *missing: str, why: str = "来的原稿只有签约页，管理页那一节没有可参照的界面") -> None:
        write_gaps(self.src(), missing, why)

    def write_analysis_sidecars(self) -> None:
        """需求分析（S2b）的两份产出，round 消费进契约。"""
        src = self.src()
        src.mkdir(parents=True, exist_ok=True)
        (src / ".positioning.json").write_text(json.dumps({
            "scope_text": "本 AR 承载自动充值签约与管理", "sr_related_ars": [],
        }, ensure_ascii=False), encoding="utf-8")
        (src / ".scope-options.json").write_text(json.dumps([
            {"key": "carry_all", "label": "按当前范围整体承载：签约、管理、扣款回执"},
        ], ensure_ascii=False), encoding="utf-8")

    def status(self) -> dict:
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def next_of(self) -> str:
        return self.status()["next"]

    def ask(self) -> dict:
        return json.loads((self.src() / ".ask.json").read_text(encoding="utf-8"))

    def sign(self, reply: str, *extra: str) -> subprocess.CompletedProcess:
        return self.run_flow("decide", "--gate", "material_scope", "--ask", self.ask()["ask_id"],
                             "--reply", reply, *extra)

    def sign_supplied(self) -> subprocess.CompletedProcess:
        return self.sign("材料放好了", "--chosen", "1")

    def asked(self) -> None:
        """盘点写下缺口，`status` 生成问法——人被问到的那一刻。"""
        self.gaps("管理页的界面图")
        self.assertEqual("await_gate:material_scope", self.next_of())

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
        """走完一次完整的补料：问 → 放料 → 人陈述事实 → 导入 → 开新一轮。"""
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        self.import_now()
        self.round_now()

    def out_of(self, proc) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    # -- 问法由脚本生成 -------------------------------------------------------

    def test_the_first_round_stops_after_the_inventory(self) -> None:
        """第一轮必停；先盘点、写下缺口，才有问法。"""
        self.round_now()
        self.assertEqual("inventory_materials", self.next_of())
        self.asked()

    def test_the_ask_has_fixed_order_labels_and_a_recommendation(self) -> None:
        """AC12：两项顺序与标签来自合同，占位已换成本单编号；缺口非空时推荐补料。"""
        self.round_now()
        self.asked()
        ask = self.status()["ask"]
        want = [o["key"] for o in material_options()]
        self.assertEqual(want, [o["key"] for o in ask["options"]])
        self.assertEqual([1, 2], [o["no"] for o in ask["options"]])
        self.assertTrue(all("<单>" not in o["label"] for o in ask["options"]))
        self.assertIn(FEATURE, ask["options"][0]["label"])
        self.assertEqual(MATERIAL_REQUEST_KEYS[0], ask["recommend"]["key"])
        self.assertIn("推荐：", ask["block"])
        self.assertEqual(ask, self.ask(), "摆给人的问法与盘上的侧车不是同一份")

    def test_no_gap_recommends_starting_the_analysis(self) -> None:
        self.round_now()
        self.gaps(why="产品稿、系统设计与会议记录都在")
        ask = self.status()["ask"]
        self.assertNotIn(ask["recommend"]["key"], MATERIAL_REQUEST_KEYS)

    def test_the_recorded_choice_is_the_asked_one_with_the_words(self) -> None:
        """AC11：人签记下问法编号、全部选项、原话与映射到的那一项。"""
        self.round_now()
        self.asked()
        ask_id = self.ask()["ask_id"]
        self.assertEqual(0, self.sign("2").returncode)
        gate = json.loads((self.src() / "story-flow.json").read_text(encoding="utf-8"))["rounds"][-1]["gates"][-1]
        self.assertEqual((ask_id, "2", "human", "reply"),
                         (gate["ask_id"], gate["reply"], gate["by"], gate["mapped_by"]))
        self.assertEqual([o["key"] for o in material_options()], [o["key"] for o in gate["options"]])

    def test_a_sign_without_the_current_ask_is_refused(self) -> None:
        """AC11：没问过、或问法换过了，人签写不进契约。"""
        self.round_now()
        self.gaps()
        proc = self.run_flow("decide", "--gate", "material_scope", "--ask", "deadbeef",
                             "--reply", "2")
        self.assertEqual(1, proc.returncode)
        self.assertIn("没有待回答的问法", self.out_of(proc))
        self.status()
        proc = self.run_flow("decide", "--gate", "material_scope", "--ask", "deadbeef",
                             "--reply", "2")
        self.assertEqual(1, proc.returncode)
        self.assertIn("不是当前问法", self.out_of(proc))

    def test_a_reply_pointing_elsewhere_than_chosen_is_refused(self) -> None:
        self.round_now()
        self.asked()
        proc = self.sign("选 2", "--chosen", "1")
        self.assertEqual(1, proc.returncode)
        self.assertIn("记人说的那一项", self.out_of(proc))

    def test_a_model_proposal_waits_for_the_human(self) -> None:
        """AC11：提议记为 by: model、不推进流程，下一次问法里请人确认。"""
        self.round_now()
        self.gaps()
        proc = self.run_flow("decide", "--gate", "material_scope", "--propose",
                             "--chosen", "confirm_scope", "--why", "材料都在")
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        contract = json.loads((self.src() / "story-flow.json").read_text(encoding="utf-8"))
        self.assertEqual("model", contract["proposals"][0]["by"])
        self.assertEqual([], contract["rounds"][-1]["gates"], "提议记成了人签")
        ask = self.status()["ask"]
        self.assertEqual("confirm_scope", ask["proposals"][0]["chosen"])
        self.assertIn("待你确认的提议", ask["block"])

    # -- 人回哪一项，料都进来 -------------------------------------------------

    def test_material_on_disk_is_imported_before_anyone_answers(self) -> None:
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())

    def test_answering_still_works_while_the_import_is_pending(self) -> None:
        """人说放好了、料也在收件箱：表态照记，下一步仍是导入。"""
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())
        proc = self.sign_supplied()
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        self.assertEqual("import_materials", self.next_of(), "签完下一步变了")

    def test_the_same_level_cannot_be_signed_twice_in_one_round(self) -> None:
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        proc = self.run_flow("decide", "--gate", "material_scope", "--ask", "x", "--reply", "2")
        self.assertEqual(1, proc.returncode, "同一轮里签了两次")
        self.assertIn("本轮第一级已经定了", self.out_of(proc))

    def test_after_a_rejection_new_material_points_at_the_import(self) -> None:
        self.round_now()
        self.asked()
        self.assertEqual(2, self.sign_supplied().returncode)
        self.assertEqual("await_gate:material_scope", self.next_of())
        self.put_inbox()
        self.assertEqual("import_materials", self.next_of())

    def test_saying_the_material_is_all_there_still_imports_the_inbox(self) -> None:
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual(0, self.sign("现有材料就是全部").returncode)
        self.assertEqual("import_materials", self.next_of())

    def test_the_import_step_names_the_files_and_gives_the_command(self) -> None:
        self.round_now()
        self.asked()
        self.put_inbox("签约页.md")
        self.assertEqual(0, self.sign("2").returncode)
        out = self.out_of(self.run_flow("status"))
        self.assertIn("import_sources.py --feature", out, "没给出可跑的导入命令")
        self.assertIn("签约页.md", out, "没点名要导的是哪一件")

    def test_after_importing_it_asks_to_register_the_new_round(self) -> None:
        self.round_now()
        self.asked()
        self.put_inbox()
        self.assertEqual(0, self.sign_supplied().returncode)
        self.import_now()
        self.assertEqual("run_round", self.next_of())

    # -- 「放进去了」是一句会被当场核对的事实 --------------------------------

    def test_saying_supplied_after_the_material_landed_is_accepted(self) -> None:
        self.round_now()
        self.asked()
        self.add_ux("signup.png")
        proc = self.sign_supplied()
        self.assertEqual(0, proc.returncode, self.out_of(proc))
        self.assertEqual("run_round", self.next_of())

    def test_saying_supplied_with_nothing_on_disk_is_refused(self) -> None:
        self.round_now()
        self.asked()
        proc = self.sign_supplied()
        self.assertEqual(2, proc.returncode)
        self.assertIn("没有待导入的原件", self.out_of(proc))
        self.assertEqual("await_gate:material_scope", self.next_of())

    # -- 导入之后：还缺什么才再停 --------------------------------------------

    def test_no_new_gap_goes_straight_to_analysis(self) -> None:
        self.one_supply_round()
        self.assertEqual("run_analysis", self.next_of())

    def test_a_new_gap_stops_again(self) -> None:
        self.one_supply_round()
        self.gaps("管理页的界面图", why="这一份补来的还是签约页")
        self.assertEqual("await_gate:material_scope", self.next_of())
        self.put_inbox("管理页.md")
        self.assertEqual(0, self.sign_supplied().returncode)

    def test_a_later_round_gap_file_must_say_what_is_missing(self) -> None:
        """补过一轮之后再停，问的必须是剩余的缺口；写了空缺口就在问人之前报出来。"""
        self.one_supply_round()
        self.gaps(why="都齐了")
        payload = self.status()
        self.assertEqual("fix_material_gaps", payload["next"])
        self.assertNotIn("ask", payload, "缺口立不住却先把人拦下来问了")

    def test_the_second_level_ask_comes_from_the_contract(self) -> None:
        self.one_supply_round()
        self.write_analysis_sidecars()
        self.round_now()
        self.assertEqual("await_gate:scope_decision", self.next_of())
        self.assertEqual(["carry_all"], [o["key"] for o in self.status()["ask"]["options"]])
        proc = self.run_flow("decide", "--gate", "scope_decision",
                             "--ask", self.ask()["ask_id"], "--reply", "1")
        self.assertEqual(0, proc.returncode, self.out_of(proc))

    # -- 选项集只有一处登记 ---------------------------------------------------

    def test_the_option_keys_live_in_the_contract_only(self) -> None:
        contract = json.loads(
            (STORY_SCRIPTS.parents[1] / "contracts" / "story-chapters.json")
            .read_text(encoding="utf-8"))
        keys = [o["key"] for o in contract["gates"]["material_scope"]["options"]]
        self.assertEqual(list(MATERIAL_CHOICES), keys)
        for path in (FLOW, STORY_SCRIPTS / "flow" / "check.mjs", STORY_SCRIPTS / "flow" / "asks.py"):
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

    SKILL = (DEV_EXT / "skills/story/SKILL.md")
    FLOW = (DEV_EXT / "skills/story/scripts/core/story_flow.py")

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
                 "--chosen", MATERIAL_CHOICES[0], "--by", "ai", "--reply", "他说的原话"],
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

    def test_the_failure_exit_is_a_handover_not_a_counter(self) -> None:
        """「修不动了」是请人接手，不是确认点；停不停由作者判断，要说清缺什么、需要谁提供。"""
        text = self.skill()
        self.assertIn("失败出口", text, "失败上报要与停等点分开写")
        self.assertIn("缺什么、需要谁提供", text)
        self.assertNotIn("连续三次运行", text, "机械次数替掉了作者的判断")
        self.assertNotIn("触发白名单第 3 条", text, "旧的自述式出口还在被引用")

    def test_no_delegated_choice_path_remains(self) -> None:
        """代选路径整个退场——它就是材料环节被跳过的那条路。"""
        for rel in ("doc/extensions/skills/story/rules/scope_gate.md",
                    "doc/extensions/skills/story/rules/init_analysis.md",
                    "doc/extensions/skills/story/SKILL.md"):
            text = (DEV_ROOT / rel).read_text(encoding="utf-8")
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


class OriginsAreDerivedNotListed(TheManifestIsTheOnlyMaterialTruth):
    """`origins` 回答「本轮实际采用了哪些原件、各读哪份阅读稿」，从材料与收件箱两张表派生。

    远端直接给的正文是原件本身；收件箱原件确定性并入的正文不再算第二份原件；
    没导入的原件不进来，走待导入；身份是相对 inbox 的路径加内容摘要。
    """

    def origins(self) -> dict[str, dict]:
        return {o["path"]: o for o in self.manifest()["origins"]}

    def test_remote_documents_are_direct_origins(self) -> None:
        self.round_now()
        origins = self.origins()
        self.assertEqual({"RR/prd.md", "SR/design.md", "AR/design.md"}, set(origins))
        self.assertEqual({"direct"}, {o["kind"] for o in origins.values()})
        self.assertEqual(["RR/prd.md"], origins["RR/prd.md"]["readable_paths"])

    def test_several_originals_merged_into_one_document(self) -> None:
        """同类两份原件合成一份正文：两份各自是来源，合成的正文不再算第三份。"""
        self.put_inbox("2-补充 说明.md", "# 补充\n\n规则二。\n", "RR")
        self.put_inbox("1-总体.md", "# 总体\n\n规则一。\n", "RR")
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        origins = self.origins()
        self.assertNotIn("RR/prd.md", origins, "被收件箱完全承接的正文又算成了一份原件")
        for key in ("inbox/1-总体.md", "inbox/2-补充 说明.md"):
            self.assertEqual("converted-source", origins[key]["kind"])
            self.assertEqual(["RR/prd.md"], origins[key]["readable_paths"])
            self.assertTrue(origins[key]["sha256"])
        self.assertEqual("direct", origins["SR/design.md"]["kind"])

    def test_a_pending_original_is_not_an_origin(self) -> None:
        """没导入的原件不进来源关系：远端正文仍是来源，原件走待导入。"""
        self.put_inbox("产品原稿.md", "# 原稿\n", "RR")
        self.round_now()
        origins = self.origins()
        self.assertNotIn("inbox/产品原稿.md", origins)
        self.assertEqual("direct", origins["RR/prd.md"]["kind"])
        self.assertEqual(["产品原稿.md"], [s["file"] for s in self.manifest()["sources"]
                                          if not s["ingested"]])

    def test_a_missing_source_is_not_invented(self) -> None:
        (self.feature_root / "SR" / "design.md").unlink()
        self.round_now()
        self.assertNotIn("SR/design.md", self.origins())

    def test_images_themselves_stay_with_the_image_chain(self) -> None:
        self.add_ux("签约页.png")
        self.put_inbox("首页.png", "PNG", "UX")
        self.round_now()
        self.assertFalse([p for p in self.origins() if p.endswith(".png")])


class ImageOnlyOriginalsAreOrigins(TheManifestIsTheOnlyMaterialTruth):
    """只抽图的原件（IMAGES）也是来源（R03）：原件一行，阅读稿是它自己，`image_paths` 是它抽出的图。

    图本身仍只在材料的图片条目里（按内容身份），取舍走图片登记；漏写这份原件照样报漏源。
    """

    PNG = b"\x89PNG\r\n\x1a\n"

    def docx(self, name: str, pictures: dict[str, bytes], cls: str = "IMAGES") -> None:
        import zipfile  # noqa: PLC0415
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        body = "".join(f'<w:p><w:r><w:drawing><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" r:embed="rId{i}"/></w:drawing></w:r></w:p>'
                       for i in range(1, len(pictures) + 1))
        rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{n}"/>'
                       for i, n in enumerate(pictures, start=1))
        with zipfile.ZipFile(inbox / name, "w") as zf:
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
                        f'<w:p><w:r><w:t>原稿正文</w:t></w:r></w:p>{body}</w:body></w:document>')
            zf.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        f'{rels}</Relationships>')
            for n, blob in pictures.items():
                zf.writestr(f"word/media/{n}", blob)
        cf = inbox / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        classify[name] = cls
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def origins(self) -> dict[str, dict]:
        return {o["path"]: o for o in self.manifest()["origins"]}

    def test_an_image_only_original_is_one_origin_with_its_pictures(self) -> None:
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a", "image2.png": self.PNG + b"b"})
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        o = self.origins()["inbox/产品原稿.docx"]
        self.assertEqual("converted-source", o["kind"])
        self.assertEqual(["inbox/产品原稿.docx"], o["readable_paths"], "没有正文转换稿，阅读稿是原件自己")
        self.assertEqual(["assets/产品原稿/image1.png", "assets/产品原稿/image2.png"], o["image_paths"])
        self.assertTrue(o["sha256"])
        self.assertEqual("direct", self.origins()["RR/prd.md"]["kind"], "只抽图不动正文，正文仍是远端原件")

    def test_all_pictures_unused_still_keeps_the_original(self) -> None:
        from materials import importer  # noqa: PLC0415
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a"})
        self.assertEqual(0, self.import_now().returncode)
        importer.mark_unused(self.feature_root, self.feature_root / "assets" / "产品原稿" / "image1.png", "旧稿，不属于本单")
        self.round_now()
        self.assertIn("inbox/产品原稿.docx", self.origins(), "图全不用，原件就从来源里消失了")

    def test_two_originals_sharing_a_picture_both_stay_traceable(self) -> None:
        same = self.PNG + b"same"
        self.docx("甲稿.docx", {"image1.png": same})
        self.docx("乙稿.docx", {"image1.png": same})
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        self.assertEqual(["assets/甲稿/image1.png"], self.origins()["inbox/甲稿.docx"]["image_paths"])
        self.assertEqual(["assets/乙稿/image1.png"], self.origins()["inbox/乙稿.docx"]["image_paths"])
        images = [m for m in self.manifest()["materials"] if m["kind"] == "image" and "assets/甲稿/image1.png" in m["paths"]]
        self.assertEqual(1, len(images))
        self.assertIn("assets/乙稿/image1.png", images[0]["paths"], "同一张图没有按内容身份合在一起")

    def test_a_missing_or_unimported_picture_is_pending_not_an_origin(self) -> None:
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a", "image2.png": self.PNG + b"b"})
        self.round_now()
        self.assertNotIn("inbox/产品原稿.docx", self.origins(), "没导入就成了来源")
        self.assertEqual(["产品原稿.docx"], [x["file"] for x in self.manifest()["sources"] if not x["ingested"]])
        self.assertEqual(0, self.import_now().returncode)
        (self.feature_root / "assets" / "产品原稿" / "image2.png").unlink()
        self.round_now()
        self.assertNotIn("inbox/产品原稿.docx", self.origins(), "少一张抽取图仍算并入")
        self.assertEqual(["产品原稿.docx"], [x["file"] for x in self.manifest()["sources"] if not x["ingested"]])

    def test_a_failure_inside_one_picture_directory_says_how_far_it_got(self) -> None:
        """同一图片目录写到第二张坏了：旧图已删、第一张已写，报错照实说，且说清图没有旧版备份、重跑导入即可（G01）。"""
        from unittest import mock  # noqa: PLC0415
        from materials import importer  # noqa: PLC0415
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a", "image2.png": self.PNG + b"b"})
        self.assertEqual(0, self.import_now().returncode)
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a2", "image2.png": self.PNG + b"b2"})
        real = Path.write_bytes

        def flaky(path, data):
            if path.name == "image2.png" and "assets" in path.parts:
                raise OSError("磁盘写保护（注入）")
            return real(path, data)

        with mock.patch.object(Path, "write_bytes", flaky):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        msg = str(caught.exception)
        folder = self.feature_root / "assets" / "产品原稿"
        self.assertTrue((folder / "image1.png").is_file())
        self.assertFalse((folder / "image2.png").exists())
        self.assertIn("中断在：assets/产品原稿/（旧图已删，新图写成 1/2 张", msg)
        self.assertIn("已完成：无", msg)
        self.assertIn("没有旧版备份", msg)
        self.assertIn("重跑导入", msg)
        self.assertEqual(0, self.import_now().returncode)
        self.assertEqual(self.PNG + b"b2", (folder / "image2.png").read_bytes(), "重跑导入没有把图写全")

    def test_a_failure_while_saving_a_meeting_version_is_named_and_rerun_recovers(self) -> None:
        from unittest import mock  # noqa: PLC0415
        from materials import importer  # noqa: PLC0415
        self.docx("澄清会.docx", {}, cls="MEETING")
        real = Path.write_text

        def flaky(path, *args, **kwargs):
            if path.name == "raw.md" and "meetings" in path.parts:
                raise OSError("磁盘写保护（注入）")
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "write_text", flaky):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        self.assertIn("中断在：会议留存 澄清会.docx", str(caught.exception))
        self.assertEqual(0, self.import_now().returncode)
        self.assertTrue(list(self.feature_root.glob("AR/story-src/meetings/澄清会/*/raw.md")), "重跑导入没有补全会议留存")

    def test_an_overwrite_failure_of_a_ux_image_is_named(self) -> None:
        from unittest import mock  # noqa: PLC0415
        from materials import importer  # noqa: PLC0415
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "首页.png").write_bytes(self.PNG + b"ux")
        (inbox / ".classify.json").write_text(json.dumps({"首页.png": "UX"}, ensure_ascii=False), encoding="utf-8")

        def broken(*args, **kwargs):
            raise OSError("目标被占用（注入）")

        with mock.patch.object(importer.shutil, "copyfile", broken):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        msg = str(caught.exception)
        self.assertIn("中断在：ux-reference/首页.png（正在覆盖写入", msg)
        self.assertIn("未执行：无", msg)
        self.assertEqual(0, self.import_now().returncode)
        self.assertTrue((self.feature_root / "ux-reference" / "首页.png").is_file())

    def test_a_new_version_of_the_original_shows_up(self) -> None:
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"a"})
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        first = self.origins()["inbox/产品原稿.docx"]["sha256"]
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"v2"})
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        self.assertNotEqual(first, self.origins()["inbox/产品原稿.docx"]["sha256"], "原件换了版本，来源关系没跟着变")

    def test_origins_do_not_move_the_material_version(self) -> None:
        """digest 只算材料：重算不变，改作者贡献说明不变，改有效输入内容才变。"""
        self.put_inbox("1-总体.md", "# 总体\n\n规则一。\n", "RR")
        self.assertEqual(0, self.import_now().returncode)
        first = self.round_now()["materials"]
        self.assertEqual(first, self.round_now()["materials"])
        (self.feature_root / "AR" / "story.md").write_text(
            "| 材料 | 来源 | 贡献 |\n|---|---|---|\n| 总体 | 原件 | 换了一种说法 |\n", encoding="utf-8")
        self.assertEqual(first, self.round_now()["materials"])
        self.put_inbox("1-总体.md", "# 总体\n\n规则一改了。\n", "RR")
        self.assertEqual(0, self.import_now().returncode)
        self.assertNotEqual(first, self.round_now()["materials"])

    def test_an_old_schema_and_a_broken_one_are_told_apart(self) -> None:
        from materials import registry  # noqa: PLC0415
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "materials.json"
        data = self.manifest()
        path.write_text(json.dumps({**data, "schema": 1}), encoding="utf-8")
        with self.assertRaises(registry.MaterialError) as old:
            registry.read(self.feature_root)
        self.assertIn("旧版", str(old.exception))
        self.assertIn("init", str(old.exception))
        broken = {k: v for k, v in data.items() if k != "origins"}
        broken["sources"] = "坏了"
        path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaises(registry.MaterialError) as bad:
            registry.read(self.feature_root)
        self.assertIn("缺 sources 列表", str(bad.exception))
        self.assertIn("缺 origins 列表", str(bad.exception))
        self.assertIn("story_flow.py round", str(bad.exception))
        self.assertNotIn("旧版", str(bad.exception))


class TheInboxIsReadRecursively(TheManifestIsTheOnlyMaterialTruth):
    """收件箱按目录原样收料：子目录里的原件按相对路径识别、归类、导入与登记。

    落点仍按名字取（正文分节标题、`assets/<主名>/`、`ux-reference/<文件名>`），
    所以会互相覆盖的原件在写入前就点名，一个字节不动。
    """

    def put(self, rel: str, body: str = "# 原件\n\n正文。\n", cls: str | None = "RR") -> Path:
        path = self.feature_root / "inbox" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        if cls:
            cf = self.feature_root / "inbox" / ".classify.json"
            classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
            classify[rel] = cls
            cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        return path

    def snapshot(self) -> dict[str, bytes]:
        return {p.relative_to(self.feature_root).as_posix(): p.read_bytes()
                for p in self.feature_root.rglob("*") if p.is_file() and "inbox" not in p.parts}

    def refused(self, *needles: str) -> str:
        before = self.snapshot()
        proc = self.import_now()
        out = proc.stdout + proc.stderr
        self.assertEqual(1, proc.returncode, out)
        for needle in needles:
            self.assertIn(needle, out)
        self.assertEqual(before, self.snapshot(), "冲突没在写入前拦下，盘上已经动了")
        return out

    def test_nested_and_flat_originals_import_together_in_path_order(self) -> None:
        self.put("2026-09 评审/第二轮/补充 说明.md", "# 补充\n\n规则二。\n")
        self.put("总体.md", "# 总体\n\n规则一。\n")
        self.put("界面稿/首页说明.md", "# 首页\n\n入口在顶部。\n", "UX")
        self.put("系统/接口.md", "# 接口\n\n字段。\n", "SR")
        (self.feature_root / "inbox" / "空目录" / "更深").mkdir(parents=True)
        self.put(".git/废料.md", cls=None)
        self.put("界面稿/.草稿.md", cls=None)
        self.put("界面稿/README.md", "说明书", cls=None)
        proc = self.import_now()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(["2026-09 评审/第二轮/补充 说明.md", "总体.md", "界面稿/首页说明.md", "系统/接口.md"],
                         result["converted"])
        prd = (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8")
        self.assertLess(prd.index("## 补充 说明"), prd.index("## 总体"), "正文没按相对路径排序拼接")
        self.assertIn("入口在顶部", (self.feature_root / "ux-reference" / "README.md").read_text(encoding="utf-8"))
        def products() -> dict[str, bytes]:
            return {k: v for k, v in self.snapshot().items() if not k.startswith(".backups/")}
        first = products()
        self.assertEqual(0, self.import_now().returncode)
        self.assertEqual(first, products(), "重跑不是字节一致")
        self.round_now()
        sources = {s["file"]: s for s in self.manifest()["sources"]}
        self.assertTrue(sources["2026-09 评审/第二轮/补充 说明.md"]["ingested"])
        self.assertNotIn(".git/废料.md", sources)
        self.assertNotIn("界面稿/README.md", sources)
        origins = {o["path"] for o in self.manifest()["origins"]}
        self.assertIn("inbox/2026-09 评审/第二轮/补充 说明.md", origins)

    def test_an_inbox_root_link_is_refused_by_import_and_the_manifest(self) -> None:
        """inbox 根本身指到别处：导入、材料清单都在写入前拒绝，与退原件同一条边界（G03）。"""
        outside = self.root / "外面"
        outside.mkdir()
        (outside / "别处原件.md").write_text("# 别处\n\n不属于这张单。\n", encoding="utf-8")
        (outside / ".classify.json").write_text(json.dumps({"别处原件.md": "RR"}, ensure_ascii=False), encoding="utf-8")
        inbox = self.feature_root / "inbox"
        if inbox.exists():
            shutil.rmtree(inbox)
        try:
            import _winapi  # noqa: PLC0415
            _winapi.CreateJunction(str(outside), str(inbox))
        except (ImportError, OSError):
            try:
                inbox.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("这台机器建不了目录联接或符号链接")
        before = self.snapshot()
        proc = self.import_now()
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("需求目录之外", proc.stdout + proc.stderr)
        self.assertEqual(before, self.snapshot(), "根联接被跟随，别处的原件进了正文")
        flow = self.run_flow("round")
        self.assertNotEqual(0, flow.returncode, flow.stdout)
        self.assertIn("需求目录之外", flow.stdout + flow.stderr)

    def test_a_linked_file_inside_the_inbox_is_refused(self) -> None:
        outside = self.root / "外面.md"
        outside.write_text("# 别处\n", encoding="utf-8")
        link = self.feature_root / "inbox" / "链接.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("这台机器建不了文件符号链接")
        self.refused("链接.md", "是链接或指到收件箱之外")

    def test_a_new_original_in_a_subdirectory_is_pending(self) -> None:
        self.round_now()
        self.put("补料/第三轮/新规则.md")
        self.round_now()
        pending = [s["file"] for s in self.manifest()["sources"] if not s["ingested"]]
        self.assertEqual(["补料/第三轮/新规则.md"], pending)

    def test_the_same_name_in_two_directories_is_refused_before_writing(self) -> None:
        self.put("甲/说明.md")
        self.put("乙/说明.md", cls="SR")
        self.refused("不同目录下有同名原件", "甲/说明.md", "乙/说明.md")

    def test_a_case_only_difference_is_the_same_name(self) -> None:
        self.put("甲/Flow.md")
        self.put("乙/flow.md")
        self.refused("同名原件", "甲/Flow.md", "乙/flow.md")

    def test_the_same_stem_in_one_class_collides_on_the_section_title(self) -> None:
        self.put("规则.md")
        self.put("规则.txt")
        self.refused("同一个落点", "规则.md", "规则.txt", "## 规则")

    def test_a_key_that_is_not_canonical_is_refused(self) -> None:
        self.put("甲/说明.md", cls=None)
        cf = self.feature_root / "inbox" / ".classify.json"
        for key in ("./甲/说明.md", "甲//说明.md", "../说明.md", "/甲/说明.md", "甲\\说明.md"):
            with self.subTest(key=key):
                cf.write_text(json.dumps({key: "RR"}, ensure_ascii=False), encoding="utf-8")
                self.refused("不是规范的相对路径")

    def test_a_key_without_its_original_is_refused(self) -> None:
        self.put("甲/说明.md")
        cf = self.feature_root / "inbox" / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8"))
        classify["旧/挪走了.md"] = "RR"
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        self.refused("没有对应的原件", "旧/挪走了.md")

    def test_all_input_problems_come_in_one_report(self) -> None:
        self.put("甲/说明.md")
        self.put("乙/说明.md")
        self.put("没归类.md", cls=None)
        out = self.refused("同名原件", "「没归类.md」未给出归类")

    def test_a_linked_directory_is_not_followed(self) -> None:
        import os  # noqa: PLC0415
        outside = self.root / "inbox 之外"
        outside.mkdir()
        (outside / "外部.md").write_text("# 外部\n", encoding="utf-8")
        (self.feature_root / "inbox").mkdir(exist_ok=True)
        link = self.feature_root / "inbox" / "链过去"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError as exc:
            try:
                import _winapi  # noqa: PLC0415  Windows 无符号链接权限时用目录联接
                _winapi.CreateJunction(str(outside), str(link))
            except (ImportError, OSError):
                self.skipTest(f"本机建不了目录链接：{exc}")
        self.refused("是链接或指到收件箱之外", "链过去")

    def test_a_write_failure_midway_says_what_was_written(self) -> None:
        """写盘中途坏了：报出已写的目标与旧版备份，不冒称整批没变。"""
        from unittest import mock  # noqa: PLC0415
        self.put("总体.md")
        self.put("系统/接口.md", cls="SR")
        real = Path.write_text

        def flaky(path, *args, **kwargs):
            if path.as_posix().endswith("SR/design.md"):
                raise OSError("磁盘写保护（注入）")
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "write_text", flaky):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        msg = str(caught.exception)
        self.assertIn("写盘中途失败", msg)
        self.assertIn("已完成：RR/prd.md", msg)
        self.assertIn("中断在：SR/design.md", msg)
        self.assertIn(".backups/local/RR-prd.md-", msg)
        self.assertIn("磁盘写保护（注入）", msg)


class SubdirectoryOriginalsThroughUpdate(TheInboxIsReadRecursively):
    """update 对子目录原件同样按相对路径比较、提示替代与恢复；读不出清单不说成「没有新料」。"""

    def test_changed_content_and_a_new_path_are_both_seen(self) -> None:
        from flow import update  # noqa: PLC0415
        self.put("评审/第一轮.md", "# 一\n\n旧。\n")
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        closed = [("u1", {"status": "closed", "sources": [
            {"file": s["file"], "sha256": s["sha256"]} for s in self.manifest()["sources"]]})]
        self.put("评审/第一轮.md", "# 一\n\n改了。\n")
        self.put("评审/第二轮.md", "# 二\n\n新增。\n")
        self.assertEqual(0, self.import_now().returncode)
        self.round_now()
        got = sorted(s["file"] for s in update._imported_since(self.feature_root, closed))
        self.assertEqual(["评审/第一轮.md", "评审/第二轮.md"], got)

    def test_the_superseded_hint_lists_relative_paths_and_points_at_the_rule(self) -> None:
        from flow import update  # noqa: PLC0415
        self.put("旧版/规则.md")
        self.put("新版/规则 v2.md")
        self.put("系统/接口.md", cls="SR")
        hint = update._superseded_hint(self.feature_root, ["新版/规则 v2.md"])
        self.assertEqual(["旧版/规则.md"], hint[0]["same_class"], "只列同类的已归类原件")
        self.assertIn("新原件取代旧原件", hint[0]["note"])

    def retire(self, key: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(STORY_SCRIPTS / "import_sources.py"),
             "--feature", FEATURE, "--project-root", str(self.root), "--retire", key],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO_ROOT))
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def test_a_replaced_original_is_moved_with_its_directory_and_no_longer_merged(self) -> None:
        self.put("旧版/规则.md", "# 规则\n\n第一版。\n")
        self.assertEqual(0, self.import_now().returncode)
        out = self.retire("旧版/规则.md")
        self.assertTrue(out["ok"], out)
        backup = self.feature_root / out["backup"]
        self.assertEqual(".backups/local/inbox/旧版", backup.parent.relative_to(self.feature_root).as_posix())
        self.assertNotIn("旧版/规则.md", json.loads((self.feature_root / "inbox" / ".classify.json").read_text(encoding="utf-8")))
        self.put("新版/规则 v2.md", "# 规则\n\n第二版。\n")
        self.assertEqual(0, self.import_now().returncode)
        prd = (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("第二版", prd)
        self.assertNotIn("第一版", prd, "移走的旧原件又拼回了正文")
        self.assertIn("第一版", backup.read_text(encoding="utf-8"))
        old = [b for b in (self.feature_root / ".backups" / "local").glob("RR-prd.md-*.md")
               if "第一版" in b.read_text(encoding="utf-8")]
        self.assertTrue(old, "被覆盖的旧正文没有备份可恢复")

    def test_three_versions_at_one_path_each_keep_a_backup_and_can_come_back(self) -> None:
        """同一路径连续替代：每一版各留一份、互不覆盖；任一版能移回原路径、补回归类键再导入。"""
        backups = []
        for n in ("一", "二"):
            self.put("规则.md", f"# 规则\n\n第{n}版。\n")
            self.assertEqual(0, self.import_now().returncode)
            out = self.retire("规则.md")
            self.assertTrue(out["ok"], out)
            backups.append(self.feature_root / out["backup"])
        self.put("规则.md", "# 规则\n\n第三版。\n")
        self.assertEqual(0, self.import_now().returncode)
        self.assertEqual(2, len(set(backups)), f"两版落到了同一个备份名：{backups}")
        self.assertEqual(["第一版", "第二版"], [("第一版" if "第一版" in b.read_text(encoding="utf-8") else "第二版") for b in backups])
        for b in backups:
            self.assertEqual("inbox", b.parent.name)
            self.assertTrue(b.name.startswith("规则.") and b.suffix == ".md", b.name)
        # 恢复第一版：退掉当前的第三版，第一版移回原路径、补回归类键
        self.assertTrue(self.retire("规则.md")["ok"])
        self.put("规则.md", backups[0].read_text(encoding="utf-8"))  # 移回原路径、补回归类键
        backups[0].unlink()
        self.assertEqual(0, self.import_now().returncode)
        self.assertIn("第一版", (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8"))

    def test_retiring_the_same_content_twice_does_not_overwrite_and_bad_keys_are_refused(self) -> None:
        self.put("规则.md", "# 规则\n\n同一份。\n")
        first = self.retire("规则.md")
        self.put("规则.md", "# 规则\n\n同一份。\n")
        second = self.retire("规则.md")
        self.assertEqual(first["backup"], second["backup"])
        self.assertFalse((self.feature_root / "inbox" / "规则.md").exists())
        for key in ("../外面.md", "/规则.md", "没有这份.md", "./规则.md"):
            with self.subTest(key=key):
                out = self.retire(key)
                self.assertFalse(out["ok"], out)

    def everything(self) -> dict[str, bytes]:
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def assert_refused_untouched(self, key: str, *needles: str) -> None:
        before = self.everything()
        out = self.retire(key)
        self.assertFalse(out["ok"], out)
        for needle in needles:
            self.assertIn(needle, out["error"])
        self.assertEqual(before, self.everything(), f"「{key}」被拒，盘上却动了")

    def test_a_drive_or_linked_path_moves_nothing(self) -> None:
        """盘符路径、盘符相对路径、反斜杠与经链接逃出 inbox 的路径：一律拒绝，一个文件都不动。"""
        outside = self.root / "外面" / "文档.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("不属于这张单。", encoding="utf-8")
        self.put("规则.md")
        drive = outside.resolve().as_posix()
        for key in (drive, drive[:2] + "文档.md", "子目录\\规则.md", "//server/share/a.md"):
            with self.subTest(key=key):
                self.assert_refused_untouched(key, "不动任何文件")
        link = self.feature_root / "inbox" / "链接"
        try:
            import _winapi  # noqa: PLC0415
            _winapi.CreateJunction(str(outside.parent), str(link))
        except (ImportError, OSError):
            try:
                link.symlink_to(outside.parent, target_is_directory=True)
            except OSError:
                self.skipTest("这台机器建不了目录联接或符号链接")
        self.assert_refused_untouched("链接/文档.md", "inbox 之外")
        self.assertTrue(outside.is_file())
        self.assertTrue(self.retire("规则.md")["ok"], "正常输入不该被链接检查误伤")

    def test_an_inbox_that_is_itself_a_link_moves_nothing(self) -> None:
        """inbox 根本身是指到别处的联接：合法的相对键也不能把别处的文件纳入退原件。"""
        outside = self.root / "外面"
        outside.mkdir()
        (outside / "source.md").write_text("别处的文件。", encoding="utf-8")
        inbox = self.feature_root / "inbox"
        if inbox.exists():
            import shutil as sh  # noqa: PLC0415
            sh.rmtree(inbox)
        try:
            import _winapi  # noqa: PLC0415
            _winapi.CreateJunction(str(outside), str(inbox))
        except (ImportError, OSError):
            try:
                inbox.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("这台机器建不了目录联接或符号链接")
        self.assert_refused_untouched("source.md", "需求目录之外")
        self.assertTrue((outside / "source.md").is_file())

    def test_a_broken_classify_file_moves_nothing(self) -> None:
        self.put("规则.md")
        (self.feature_root / "inbox" / ".classify.json").write_text("{坏了", encoding="utf-8")
        self.assert_refused_untouched("规则.md", "不是合法 JSON")

    def test_an_unwritable_backup_place_leaves_the_original(self) -> None:
        self.put("规则.md")
        blocker = self.feature_root / ".backups" / "local" / "inbox"
        blocker.parent.mkdir(parents=True)
        blocker.write_text("这里本该是目录", encoding="utf-8")
        out = self.retire("规则.md")
        self.assertFalse(out["ok"], out)
        self.assertIn("没有移动", out["error"])
        self.assertTrue((self.feature_root / "inbox" / "规则.md").is_file())

    def test_a_classify_write_failure_says_where_the_original_went(self) -> None:
        import os  # noqa: PLC0415
        import stat  # noqa: PLC0415
        self.put("规则.md", "# 规则\n\n写不回。\n")
        cf = self.feature_root / "inbox" / ".classify.json"
        os.chmod(cf, stat.S_IREAD)
        self.addCleanup(os.chmod, cf, stat.S_IWRITE | stat.S_IREAD)
        out = self.retire("规则.md")
        self.assertFalse(out["ok"], out)
        self.assertIn("归类件写不回", out["error"])
        backups = list((self.feature_root / ".backups" / "local" / "inbox").glob("规则.*.md"))
        self.assertEqual(1, len(backups))
        self.assertIn(backups[0].relative_to(self.feature_root).as_posix(), out["error"], "没说原件去了哪")

    def test_an_unreadable_manifest_is_not_reported_as_nothing_new(self) -> None:
        from flow import update  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "materials.json"
        path.write_text("{坏了", encoding="utf-8")
        with self.assertRaises(FlowError) as caught:
            update._imported_since(self.feature_root, [])
        self.assertIn("说不出上次以来并入了哪些原件", str(caught.exception))


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
        for name in ("story.js", "token.js"):
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
    """材料清单留在 `story-src/`，但不进登记指纹。

    它是材料真源，会随材料继续演化；登记那一刻手里是哪版材料，记在契约当轮的
    `materials.digest` 里——那才是快照。把它也记进登记指纹，材料一变 check 就报
    「登记之后改过」，而那正是**正常**的。
    """

    def test_the_manifest_is_not_a_frozen_ledger(self) -> None:
        self.assertNotIn("AR/story-src/materials.json", STORY_REGISTERED,
                         "材料清单进了登记指纹，材料一演化就会被判成登记之后改过")


class TheMovedInThreeAreNotFrozenLedgers(unittest.TestCase):
    """流程契约、需求分析件、导入落点住在 `story-src/`，但都不进登记指纹。

    三件在登记之后还要写：契约要记归档态与重新登记，清单与落点随材料重算，
    分析件随初析演进。记进登记指纹，登记之后的每一步都会被判成「登记之后改过」。
    """

    NAMES = property(lambda self: [
        CONTRACT[-1], "init-analysis.md",
        importer.doc_targets()["AR"].name,
    ])

    def test_none_of_them_is_a_frozen_ledger(self) -> None:
        """三件都留，但都不进登记指纹——指纹记的是 story 与「据以成文的依据」，它们还要继续变。"""
        for name in self.NAMES:
            self.assertNotIn(f"AR/story-src/{name}", STORY_REGISTERED)

    def test_they_live_under_story_src_not_the_ar_root(self) -> None:
        """路径本身就是判据：`AR/` 根下只放交付文档，辅助件在 `story-src/` 这一层。"""
        self.assertEqual(("AR", "story-src", "story-flow.json"), CONTRACT)
        self.assertEqual("AR/story-src/upstream.md",
                         importer.doc_targets()["AR"].as_posix())


class DraftsAreNotFrozenIntoTheLedger(unittest.TestCase):
    """草稿不进登记指纹：它不是 story 据以成文的依据，是写它的过程。"""

    def test_drafts_are_not_frozen_into_the_ledger(self) -> None:
        self.assertFalse(any("/drafts" in rel for rel in STORY_REGISTERED))


class RegistrationReprojectsFirst(unittest.TestCase):
    """登记的顺序是 project → number → check。

    附录的机器区是 spec 扩展章与 knowledge-use.yaml 的投影，而真源在成文期间还会变；
    以登记这一次为准，否则归档件里留的是一份会漂移的副本。
    """

    def test_the_order_is_project_then_number_then_check(self) -> None:
        source = (DEV_EXT / "skills" / "story" / "scripts"
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
        source = (DEV_EXT / "skills" / "story" / "scripts"
                  / "core" / "flow" / "lifecycle.py").read_text(encoding="utf-8")
        body = source.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        for gone in ("rmtree", "unlink", "sweep"):
            self.assertNotIn(gone, body, f"登记还在删 story-src/ 下的东西（{gone}）")


if __name__ == "__main__":
    unittest.main()
