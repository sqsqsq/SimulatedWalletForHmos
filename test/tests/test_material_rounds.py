"""一轮 = 一次材料状态 —— **界面参考也是材料**。

轮次指纹曾只算四份文本源，补料如果只有界面图，四份文本一个字节没变 → 指纹不变 → 不算新一轮 →
关卡列表永不重置 → 流程停在「回去导入再盘点」上出不来。现在材料是 `sources/` 下的材料版本，
指纹按各来源最新版本的原件、阅读稿与图算，界面图同样是一份来源。

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
from flow.inputs import MATERIAL_REQUEST_KEYS, material_options  # noqa: E402
from flow.state import CONTRACT, STORY_REGISTERED, file_sha256  # noqa: E402
from materials import importer, registry  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import ensure_framework, project_root_of, write_gaps  # noqa: E402
import design_kit  # noqa: E402
FEATURE = "AR90001"


class MaterialRoundCase(unittest.TestCase):
    """每个用例一份新工作区，跑真脚本、读真契约。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "AR").mkdir(parents=True)
        self.seed({"RR/prd.md": ("# 产品需求\n\n背景。\n", "RR"), "SR/design.md": ("# 系统设计\n\n分工。\n", "SR"),
                   "AR/design.md": ("# 开发需求\n\n范围。\n", "AR")})

    def seed(self, files: dict[str, tuple[str | bytes, str]]) -> None:
        """经真实导入器把这几份原件导成材料版本（键是收件箱里的相对路径，值是内容与类）。"""
        inbox = self.feature_root / "sources" / "inbox"
        cf = inbox / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        for rel, (body, cls) in files.items():
            (inbox / rel).parent.mkdir(parents=True, exist_ok=True)
            (inbox / rel).write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
            classify[rel] = cls
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        importer.cmd_import(self.feature_root, self.root)

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
        """补一张界面图：放进来源收件箱并导入。"""
        self.seed({f"ux/{name}": (body, "UX")})


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
                    story_basis={"files": {"AR/story-src/decisions.json": "sha"}})
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
                self.assertEqual("gathering", disk["status"], "盘上没重开")
                self.assertTrue(disk["rounds"][-1].get("reopened"), "重开的一轮没留标记")
                self.assertEqual("gathering", result["status"])
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
    """范围还没定就来登记成文态：先说「范围还没定」，算下一步失败也不顶掉这一句。"""

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
                self.assertIn("范围还没定", message, "材料那边的错顶掉了「范围还没定」")
                self.assertIn("story_flow.py status", message, "没给出取下一步的命令")


class MaterialFingerprintCoversEveryInput(MaterialRoundCase):

    def test_a_ux_only_supplement_starts_a_new_round(self) -> None:
        """只补一张界面图——那也是材料变了，必须算新一轮。"""
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
        self.seed({"RR/prd.md": ("# 产品需求\n\n背景。\n\n补充一段。\n", "RR")})
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"))
        self.assertGreater(second.get("round", 0), first.get("round", 0))

    def test_no_ux_directory_is_not_an_error(self) -> None:
        """没有界面材料的单子照常跑，不因为多了一类材料就变了口径。"""
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
    说明记在材料索引里、按图的内容摘要键，所以同一张图出现在几个版本里，两件事都跟着这张图走。
    """

    def store(self):
        import importlib
        return importlib.import_module("materials.registry")

    def a_sha(self) -> str:
        return "a" * 64

    def test_writing_a_reason_keeps_the_caption(self) -> None:
        m = self.store()
        m.write_note(self.feature_root, self.a_sha(), "caption", "签约页")
        m.write_note(self.feature_root, self.a_sha(), "unused", "属别的需求")
        entry = m.read_notes(self.feature_root)[self.a_sha()]
        self.assertEqual("签约页", entry["caption"])
        self.assertEqual("属别的需求", entry["unused"])

    def test_rewriting_the_caption_keeps_the_reason(self) -> None:
        m = self.store()
        m.write_note(self.feature_root, self.a_sha(), "unused", "属别的需求")
        m.write_note(self.feature_root, self.a_sha(), "caption", "签约页：换个说法")
        entry = m.read_notes(self.feature_root)[self.a_sha()]
        self.assertEqual("属别的需求", entry["unused"], "改说明把取舍抹掉了")

    def test_clearing_the_reason_keeps_the_caption(self) -> None:
        m = self.store()
        m.write_note(self.feature_root, self.a_sha(), "caption", "签约页")
        m.write_note(self.feature_root, self.a_sha(), "unused", "先不用")
        m.write_note(self.feature_root, self.a_sha(), "unused", None)
        entry = m.read_notes(self.feature_root)[self.a_sha()]
        self.assertEqual("签约页", entry["caption"])
        self.assertNotIn("unused", entry)

    def test_the_notes_survive_a_rebuild_of_the_index(self) -> None:
        """索引按磁盘现状重算时，说明与取舍原样带过去——它们不是磁盘能重算出来的事实。"""
        m = self.store()
        m.write_note(self.feature_root, self.a_sha(), "caption", "签约页")
        m.refresh(self.feature_root)
        self.assertEqual("签约页", m.read_notes(self.feature_root)[self.a_sha()]["caption"])


class CompleteThenMaterialChangedCase(MaterialRoundCase):
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

    def complete_it(self, status: str = "gathering") -> None:
        """把契约摆成收口态（本轮范围已定、同根蓝图已在）——这里只测 round/reopen，不重演整条关卡链。
        已登记的带上此刻的登记指纹。"""
        self.round_now()
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        at = "2026-10-30T00:00:00Z"
        data["rounds"][-1]["gates"] = [
            {"gate": "material_scope", "ask_id": "m1", "question": "材料齐了吗？",
             "options": [{"no": 1, "key": "confirm_scope", "label": "现有材料就是全部"}],
             "chosen": "confirm_scope", "no": 1, "label": "现有材料就是全部", "reply": "1",
             "outcome": "accepted", "by": "human", "at": at},
            {"gate": "scope_decision", "ask_id": "s1", "question": "这个需求承载哪些？",
             "options": [{"no": 1, "key": "carry_all", "label": "按当前范围整体承载"}],
             "chosen": "carry_all", "no": 1, "label": "按当前范围整体承载", "reply": "1",
             "outcome": "accepted", "by": "human", "at": at, "context": {"scope_text": "本 AR 承载全部"}}]
        # 收口意味着设计已经开始：放好同根蓝图，收口之后的路由要读原生蓝图
        root = project_root_of(self.feature_root)
        ensure_framework(root)
        data = design_kit.hand_over_state(root, self.feature_root.name, data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        registry.refresh(self.feature_root)    # 答复生效时 decide 做的那一步：导出人答
        if status == "story_written":
            data["story_basis"] = design_kit.registered_basis(root, self.feature_root.name)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def put_inbox_file(self, name: str = "后到的稿.md") -> None:
        inbox = self.feature_root / "sources" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / name).write_text("# 后到的稿" + chr(10) * 2 + "登记之后才来的材料。" + chr(10),
                                  encoding="utf-8")

    def put_classified_inbox(self, name: str = "后到的稿.md") -> None:
        """放一份**已归类**的原件：`round` 看得见它，而它还没导入。"""
        inbox = self.feature_root / "sources" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
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


class CompleteThenMaterialChanged(CompleteThenMaterialChangedCase):
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

    def test_the_scope_stays_settled(self) -> None:
        """补料不改变流程位置——本轮范围仍是定了的，设计照常进行。"""
        self.complete_it()
        self.add_ux("extra.png")
        self.round_now()
        self.assertEqual("gathering", self.contract()["status"])
        self.assertIn(self.status_payload()["state"], ("waiting_for_design", "ready_to_write"))

    def test_reopen_puts_it_back_and_leaves_a_trace(self) -> None:
        """`reopen` 是唯一出口：回到范围关卡，日志说清从哪个状态重开。"""
        self.complete_it()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("gathering", self.contract()["status"])
        self.assertIn("范围已重开（原状态 gathering）", proc.stderr)

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
        """`story_written` 比设计开始更靠后，同样不开轮。

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


class CompleteThenMaterialChangedPart2(CompleteThenMaterialChangedCase):
    def test_status_after_the_story_is_written_gives_no_import(self) -> None:
        """成文登记之后放料，`status` 不引导导入——那条路归 `round` 与 `reopen`。

        引导导入的话，材料会并进正文，而已经定稿的 story 声称的依据是当轮的快照，
        两边当场对不上。此后材料再变只有一个出口：显式 `reopen`。
        """
        self.complete_it("story_written")
        (self.feature_root / "sources" / "inbox").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "sources" / "inbox" / "补的稿.md").write_text(
            "# 补的稿\n\n后到的材料。\n", encoding="utf-8")
        proc = self.run_flow("status")
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertNotEqual("import_materials", payload["next"],
                            "成文之后还引导导入，story 的依据就被改掉了")
        self.assertEqual("run_delivery_gate", payload["next"])

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
        self.assertEqual("run_delivery_gate", payload["next"], "已登记的下一步被改掉了")
        self.assertIn("补的界面稿.md", (proc.stdout or "") + (proc.stderr or ""))

    def test_an_empty_inbox_after_freezing_says_nothing_extra(self) -> None:
        """没有待导入的件就不多说一句——每次都提一遍，读的人就不看它了。"""
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
        """归档之后下一步是 done：不再引导跑 harness 与交付门，回流与补料各有出口。

        已成文的单有 story，写作设计写明不采用阅读图——阅读不适用，才轮得到 done。"""
        (self.feature_root / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story.md").write_text(f"# {FEATURE} 甲需求\n\n## 背景\n\n没有图。\n", encoding="utf-8")
        (self.feature_root / "AR" / "story-src" / "story-template.md").write_text(
            "# 写作设计\n\n## 阅读主线\n\n主线。\n\n## 骨架\n\n## 阅读图选择\n\n不采用：正文已经讲清\n", encoding="utf-8")
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
        self.assertEqual("gathering", self.contract()["status"])


class CompleteThenMaterialChangedPart3(CompleteThenMaterialChangedCase):
    def test_reopen_keeps_the_registration_on_hold(self) -> None:
        """重拍范围不抹掉上一次成文登记：它留作依据，但在范围重新定了、重新登记之前不可交付。"""
        self.complete_it("story_written")
        before = self.contract()
        canonical = (self.feature_root / "blueprint" / "component-blueprint.yaml").read_bytes()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        contract = self.contract()
        self.assertEqual(before["story_basis"], contract["story_basis"])
        self.assertEqual(canonical, (self.feature_root / "blueprint" / "component-blueprint.yaml").read_bytes(), "重开动了蓝图")
        self.assertEqual("gathering", contract["status"], "重开之后仍是可交付的成文态")
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertTrue(out["basisOnHold"], "保留了什么、为什么暂不可交付要说出来")

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

    def test_reopen_inside_an_open_update_keeps_it_open(self) -> None:
        """update 里重开范围：update 照旧开着，下一步回到范围关卡，不要求先伪造一次收口。"""
        self.complete_it("story_written")
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["update"] = {"open": "20260926-000000"}
        data["rounds"][-1]["positioning"] = {"scope_text": "整单", "sr_related_ars": []}
        data["rounds"][-1]["scope_options"] = [{"key": "all", "label": "整体承载"}]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("20260926-000000", self.contract()["update"]["open"], "重开把 update 关掉了")
        status = self.run_flow("status")
        payload = json.loads(status.stdout[status.stdout.index("{"):])
        self.assertEqual("await_gate:scope_decision", payload["next"])

    def test_reopen_from_complete_has_nothing_on_hold(self) -> None:
        """还没成文时没有成文登记可保留——留痕里如实说没有，不编造。"""
        self.complete_it()
        proc = self.run_flow("reopen")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertFalse(out["basisOnHold"])

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


class CompleteThenMaterialChangedPart4(CompleteThenMaterialChangedCase):
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

    def test_registering_again_keeps_the_old_registration_when_it_fails(self) -> None:
        """已经登记过再跑 `story`：通过才换成新登记；这里盘上没有 story.md，登记失败——
        说的是缺 story，不是「只登记一次」也不是「没收口」，已有的登记原样留着。
        """
        self.complete_it("story_written")
        before = self.contract()
        proc = self.run_flow("story")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("AR/story.md 不存在", out)
        self.assertNotIn("没收口", out)
        after = self.contract()
        self.assertEqual((before["status"], before.get("story_basis")), (after["status"], after.get("story_basis")))

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
        inbox = self.feature_root / "sources" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
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
        self.assertIn("没有待导入的件", self.out_of(proc))
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
        self.assertEqual([o["key"] for o in material_options()], keys)
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
                 "--chosen", material_options()[0]["key"], "--by", "ai", "--reply", "他说的原话"],
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
            self.assertNotIn(gone, text, "「%s」还在，交给设计前仍会停一次" % gone)
        self.assertIn("直接进 component-design，不问", text)

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


class ManifestCase(MaterialRoundCase):
    """材料索引用例的辅助：读索引与契约、往来源收件箱放件、造 docx、跑真实导入命令。本类不含用例。"""

    PNG = b"\x89PNG\r\n\x1a\n"

    def manifest(self) -> dict:
        path = self.feature_root / "AR" / "story-src" / "materials.json"
        self.assertTrue(path.is_file(), "round 之后没有材料索引")
        return json.loads(path.read_text(encoding="utf-8"))

    def contract(self) -> dict:
        return json.loads((self.feature_root / "AR" / "story-src" / "story-flow.json")
                          .read_text(encoding="utf-8"))

    def inbox(self) -> Path:
        return self.feature_root / "sources" / "inbox"

    def classify(self, rel: str, cls: str | None) -> None:
        if not cls:
            return
        cf = self.inbox() / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8")) if cf.is_file() else {}
        classify[rel] = cls
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def put(self, rel: str, body: str | bytes = "# 原件\n\n正文。\n", cls: str | None = "RR") -> Path:
        path = self.inbox() / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        self.classify(rel, cls)
        return path

    def docx(self, name: str, pictures: dict[str, bytes], cls: str = "IMAGES", text: str = "原稿正文") -> None:
        import zipfile  # noqa: PLC0415
        path = self.inbox() / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f'<w:p><w:r><w:drawing><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" r:embed="rId{i}"/></w:drawing></w:r></w:p>'
                       for i in range(1, len(pictures) + 1))
        rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{n}"/>'
                       for i, n in enumerate(pictures, start=1))
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
                        f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>{body}</w:body></w:document>')
            zf.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        f'{rels}</Relationships>')
            for n, blob in pictures.items():
                zf.writestr(f"word/media/{n}", blob)
        self.classify(name, cls)

    def import_now(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(STORY_SCRIPTS / "import_sources.py"),
             "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def imported(self) -> None:
        proc = self.import_now()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def source(self, key: str) -> dict:
        """收件箱键为 `key` 的那个本地来源。"""
        return next(s for s in self.manifest()["sources"] if s["origin"].get("inbox_path") == key)

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
        self.assertEqual(before, self.snapshot(), "问题没在写入前拦下，盘上已经动了")
        return out


class TheManifestIsTheOnlyMaterialTruth(ManifestCase):
    """材料现在是什么、导没导过、取得过哪些版本，只有材料索引 `AR/story-src/materials.json` 说了算。"""

    def test_the_contract_only_points_at_the_manifest(self) -> None:
        """契约不再自己存一份逐文件哈希，只留索引的材料版本。

        同一份材料事实两处写，改一处忘一处时，两边都还理直气壮。
        """
        self.round_now()
        entry = self.contract()["rounds"][-1]
        self.assertNotIn("inputs", entry, "契约里还留着第二份材料哈希")
        self.assertEqual({"digest"}, set(entry["materials"]), "契约里材料只该记版本")
        self.assertEqual(self.manifest()["digest"], entry["materials"]["digest"])

    def test_importing_leaves_no_receipt(self) -> None:
        """导入不落一次性回执：本次导了什么，版本记录与索引里按磁盘现状问。"""
        self.put("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.imported()
        self.assertFalse((self.feature_root / "AR" / ".last-import.json").exists(), "导入回执又回来了")
        for script in ("story_flow.py", "import_sources.py"):
            self.assertNotIn(".last-import", (STORY_SCRIPTS / script).read_text(encoding="utf-8"),
                             "%s 还在读写导入回执" % script)

    def test_material_placed_but_not_imported_is_pending(self) -> None:
        """放进收件箱还没导 —— 材料版本不动，但索引要说这份料还在收件箱里。"""
        before = self.round_now()
        self.put("上游需求.md", "# 上游\n\n正文。\n", "AR")
        after = self.round_now()
        self.assertEqual(before["materials"], after["materials"], "料还没导，材料版本就变了")
        self.assertEqual(["上游需求.md"], [i["file"] for i in self.manifest()["inbox"]])
        self.assertNotIn("local:上游需求.md", [s["source_id"] for s in self.manifest()["sources"]])

    def test_a_readme_in_the_inbox_is_not_a_material(self) -> None:
        self.put("README.md", "# 说明\n", None)
        self.round_now()
        self.assertEqual([], self.manifest()["inbox"])

    def test_importing_makes_a_version_and_moves_the_material_version(self) -> None:
        """导入之后：原件成为材料版本、移出收件箱 → 材料版本变了；导过什么只在索引里，契约不再记一遍。"""
        before = self.round_now()
        self.put("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.imported()
        after = self.round_now()
        self.assertNotEqual(before["materials"], after["materials"])
        self.assertEqual([], self.manifest()["inbox"])
        self.assertFalse((self.inbox() / "上游需求.md").exists(), "导入成功的原件还留在收件箱")
        source = self.source("上游需求.md")
        self.assertEqual(("local", "AR", 1), (source["kind"], source["class"], source["latest_version"]))
        version = source["versions"][0]
        self.assertEqual("# 上游\n\n正文。\n", (self.feature_root / version["original"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(64, len(version["original"]["sha256"]), "来源身份要用完整摘要")
        self.assertNotIn("imported", self.contract()["rounds"][-1], "导入名单又落回契约")

    def test_the_same_content_again_reuses_the_version(self) -> None:
        """同一来源同一内容再导一次：不出新版本，材料版本一个字节都不动。"""
        self.put("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.imported()
        first = self.round_now()
        self.put("上游需求.md", "# 上游\n\n正文。\n", "AR")
        self.imported()
        second = self.round_now()
        self.assertEqual(first["materials"], second["materials"])
        self.assertEqual(1, self.source("上游需求.md")["latest_version"])
        self.assertEqual([], self.manifest()["inbox"])

    def test_changed_content_at_the_same_place_is_a_new_version_and_the_old_one_stays(self) -> None:
        """同一位置换了内容就是新版本；旧版本原样留着，已经引用它的依据仍指得回原字节。"""
        self.put("上游需求.md", "# 上游\n\n第一版。\n", "AR")
        self.imported()
        first = self.round_now()
        self.put("上游需求.md", "# 上游\n\n第二版。\n", "AR")
        self.imported()
        second = self.round_now()
        self.assertNotEqual(first["materials"], second["materials"])
        source = self.source("上游需求.md")
        self.assertEqual([1, 2], [v["version"] for v in source["versions"]])
        old, new = (self.feature_root / v["original"]["path"] for v in source["versions"])
        self.assertEqual("# 上游\n\n第一版。\n", old.read_text(encoding="utf-8"))
        self.assertEqual("# 上游\n\n第二版。\n", new.read_text(encoding="utf-8"))
        self.assertEqual(source["versions"][1]["original"]["path"],
                         next(o for o in self.manifest()["origins"] if o["source_id"] == "local:上游需求.md")["path"],
                         "来源关系没跟到最新版本")

    def test_the_same_bytes_from_two_places_keep_both_sources(self) -> None:
        """两处放了字节相同的原件：各是一个来源，来源关系各自留着，版本目录不互相覆盖。"""
        self.put("产品/说明.md", "# 说明\n\n同一份。\n", "RR")
        self.put("研发/说明.md", "# 说明\n\n同一份。\n", "SR")
        self.imported()
        a, b = self.source("产品/说明.md"), self.source("研发/说明.md")
        self.assertNotEqual(a["versions"][0]["dir"], b["versions"][0]["dir"])
        self.assertEqual(a["versions"][0]["original"]["sha256"], b["versions"][0]["original"]["sha256"])
        self.assertEqual(("RR", "SR"), (a["class"], b["class"]))

    def test_a_user_file_named_like_a_construction_product_stays_inside_its_version(self) -> None:
        """用户原件叫 spec.md：原名保存在材料版本目录里，版本目录名带版本号，不与施工产物的名字相撞。"""
        self.put("spec.md", "# 用户给的说明\n", "AR")
        self.imported()
        version = self.source("spec.md")["versions"][0]
        self.assertEqual("spec.md", Path(version["original"]["path"]).name)
        self.assertRegex(Path(version["dir"]).name, r"-v1$")
        self.assertNotIn(Path(version["dir"]).name, ("spec", "plan", "review", "ux-reference"))
        self.assertTrue((self.feature_root / version["dir"] / "spec.md").is_file())

    def test_a_docx_keeps_original_converted_text_and_pictures_together(self) -> None:
        """docx 导成一个版本：原件字节、转换正文与内嵌图都在里面，正文的图引用指回本版本的图。"""
        self.docx("产品需求.docx", {"image1.png": self.PNG + b"a", "image2.png": self.PNG + b"b"}, cls="RR", text="签约规则")
        original = (self.inbox() / "产品需求.docx").read_bytes()
        self.imported()
        self.round_now()
        version = self.source("产品需求.docx")["versions"][0]
        folder = self.feature_root / version["dir"]
        self.assertEqual(original, (folder / "产品需求.docx").read_bytes())
        text = (folder / "text.md").read_text(encoding="utf-8")
        self.assertIn("签约规则", text)
        self.assertIn("](images/image1.png)", text)
        self.assertEqual(self.PNG + b"b", (folder / "images" / "image2.png").read_bytes())
        origin = next(o for o in self.manifest()["origins"] if o["source_id"] == "local:产品需求.docx")
        self.assertEqual([f"{version['dir']}/text.md"], origin["readable_paths"])
        images = [m for m in self.manifest()["materials"] if m["kind"] == "image"]
        self.assertEqual({f"{version['dir']}/images/image1.png", f"{version['dir']}/images/image2.png"},
                         {p for m in images for p in m["paths"]})

    def test_an_edited_version_is_reported_as_damage_not_rehashed(self) -> None:
        """已登记版本的字节被改：round 停下并报出那份文件与登记不一致，不按新字节重填摘要放行。"""
        self.round_now()
        rel = self.source("RR/prd.md")["versions"][0]["original"]["path"]
        before = (self.feature_root / "AR" / "story-src" / "materials.json").read_bytes()
        (self.feature_root / rel).write_text("# 被手改了\n", encoding="utf-8")
        proc = self.run_flow("round")
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn(rel, proc.stdout + proc.stderr)
        self.assertIn("不一致", proc.stdout + proc.stderr)
        self.assertEqual(before, (self.feature_root / "AR" / "story-src" / "materials.json").read_bytes())

    def test_a_broken_classify_file_is_not_an_empty_inbox(self) -> None:
        """归类件坏了要停下报错，不能算成「收件箱是空的」放过去。"""
        self.put("上游需求.md", "# 上游\n", None)
        (self.inbox() / ".classify.json").write_text("{坏了", encoding="utf-8")
        proc = self.run_flow("round")
        self.assertEqual(1, proc.returncode, "坏归类件没有让 round 停下")
        self.assertIn("不是合法 JSON", proc.stdout + proc.stderr)

    def test_a_broken_index_is_not_reported_as_no_materials(self) -> None:
        """索引坏了也停下报错：图片说明记在它里面，按「没有材料」重建会悄悄丢掉作者写的说明。"""
        self.round_now()
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text("{坏了", encoding="utf-8")
        proc = self.run_flow("round")
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("不是合法 JSON", proc.stdout + proc.stderr)

    def test_an_empty_feature_still_has_a_manifest(self) -> None:
        """真的一份材料都没有，也要有索引说「没有来源」——空与没查是两件事。"""
        shutil.rmtree(self.feature_root / "sources")
        (self.feature_root / "AR" / "story-src" / "materials.json").unlink()
        self.round_now()
        manifest = self.manifest()
        self.assertEqual(([], [], []), (manifest["sources"], manifest["materials"], manifest["origins"]))
        self.assertTrue(manifest["digest"])

    def test_effective_human_answers_are_exported_without_moving_the_material_version(self) -> None:
        """人答在流程里生效后导出成来源版本：原话进 answers.json；答一句话不是材料变了，不进材料表来源关系。"""
        before = self.round_now()
        write_gaps(self.feature_root / "AR" / "story-src")
        status = self.run_flow("status").stdout
        ask = json.loads(status[status.index("{"):])["ask"]
        proc = self.run_flow("decide", "--gate", "material_scope", "--ask", ask["ask_id"],
                             "--reply", "现有材料就是全部", "--chosen", "confirm_scope")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        after = self.round_now()
        self.assertEqual(before["materials"], after["materials"], "记一句人答把材料版本顶出了新一轮")
        answers = next(s for s in self.manifest()["sources"] if s["kind"] == "answer")
        record = json.loads((self.feature_root / answers["versions"][-1]["original"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(["现有材料就是全部"], [d["reply"] for d in record["current"]])
        self.assertEqual(["material_scope"], [d["gate"] for d in record["current"]])
        self.assertTrue(record["current"][0]["question"], "导出的人答没带问法")
        self.assertNotIn("answers", [o["source_id"] for o in self.manifest()["origins"]])
        self.round_now()
        self.assertEqual(1, next(s for s in self.manifest()["sources"] if s["kind"] == "answer")["latest_version"],
                         "人答没变却又导出了一版")

    def test_revising_the_analysis_does_not_open_a_round(self) -> None:
        """同一材料版本内，初析可以从盘点版改到完整版，不划新轮次。"""
        first = self.round_now()
        analysis = self.feature_root / "AR" / "story-src" / "init-analysis.md"
        analysis.write_text("# 初析\n\n盘点版。\n", encoding="utf-8")
        second = self.round_now()
        self.assertEqual(first["round"], second["round"])
        analysis.write_text("# 初析\n\n完整版，结论改了。\n", encoding="utf-8")
        third = self.round_now()
        self.assertEqual(first["round"], third["round"], "重写一遍分析就造出了一个新轮次")

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
        self.assertEqual("2026-09-14T00:00:00+08:00", lifecycle.cmd_status(self.feature_root)["story_written_at"])

    def test_the_flow_never_mirrors_a_framework_phase(self) -> None:
        """Story flow 只记材料、范围与承载，不镜像 Framework 的阶段状态。"""
        self.round_now()
        body = json.dumps(self.contract(), ensure_ascii=False)
        for word in ("highest_phase", "phase_source", "spec_done"):
            self.assertNotIn(word, body, "契约里长出了 Framework 阶段状态：%s" % word)


class OriginsFollowTheLatestVersions(ManifestCase):
    """`origins` 回答「各来源最新取得的原件是什么、读哪份阅读稿」，由版本记录派生；设计采用哪一版不在这里。"""

    def test_every_imported_original_is_an_origin_with_its_readable_copy(self) -> None:
        self.round_now()
        origins = {o["source_id"]: o for o in self.manifest()["origins"]}
        self.assertEqual({"local:RR/prd.md", "local:SR/design.md", "local:AR/design.md"}, set(origins))
        for o in origins.values():
            self.assertEqual([o["path"]], o["readable_paths"], "文本原件自己就是阅读稿")

    def test_a_pending_original_is_not_an_origin(self) -> None:
        self.put("补充.md", "# 补充\n", "AR")
        self.round_now()
        self.assertNotIn("local:补充.md", [o["source_id"] for o in self.manifest()["origins"]])

    def test_an_image_original_is_an_image_not_an_origin(self) -> None:
        """界面图原件进图片登记，不进来源关系：图的去向由图片说明与取舍说明。"""
        self.add_ux("签约页.png")
        self.round_now()
        self.assertNotIn("local:ux/签约页.png", [o["source_id"] for o in self.manifest()["origins"]])
        images = [m for m in self.manifest()["materials"] if m["kind"] == "image"]
        self.assertEqual(1, len(images))
        self.assertTrue(images[0]["paths"][0].endswith("/签约页.png"))

    def test_a_system_batch_is_identified_by_its_receipt(self) -> None:
        """取材批次里回执列着的件按角色与单号认来源，不用写归类；同一张单再取到新内容就是新版本。"""
        batch = self.inbox() / "fetch-1"
        batch.mkdir(parents=True)
        (batch / "SR-design.md").write_text("# 系统设计\n\n第一版。\n", encoding="utf-8")
        receipt = {"mode": "fetch", "reqNo": FEATURE, "parentNo": "SR9", "rrNo": None, "fetchedAt": "2026-10-29T10:00:00+08:00",
                   "items": [{"name": "SR-design.md", "role": "SR", "ticket": "SR9", "title": "甲系统设计", "status": "fetched"}]}
        (batch / ".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        self.imported()
        source = next(s for s in self.manifest()["sources"] if s["source_id"] == "system:SR:SR9")
        self.assertEqual(("system", "SR", "甲系统设计"), (source["kind"], source["class"], source["origin"]["title"]))
        self.assertFalse(batch.exists(), "导空了的取材批次还留在收件箱")
        batch2 = self.inbox() / "fetch-2"
        batch2.mkdir()
        (batch2 / "SR-design.md").write_text("# 系统设计\n\n第二版。\n", encoding="utf-8")
        (batch2 / ".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        self.imported()
        source = next(s for s in self.manifest()["sources"] if s["source_id"] == "system:SR:SR9")
        self.assertEqual(2, source["latest_version"])


class ImageOnlyOriginalsAreOrigins(ManifestCase):
    """只取图的原件（IMAGES）是来源：阅读稿是它自己，抽出的图逐张进图片登记。"""

    def test_an_image_only_original_is_one_origin_with_its_pictures(self) -> None:
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"1", "image2.png": self.PNG + b"2"})
        self.imported()
        self.round_now()
        origin = next(o for o in self.manifest()["origins"] if o["source_id"] == "local:产品原稿.docx")
        self.assertEqual([origin["path"]], origin["readable_paths"])
        self.assertEqual(2, len(origin["image_paths"]))
        self.assertFalse((self.feature_root / Path(origin["path"]).parent / "text.md").exists(), "只取图的原件不该生成阅读稿")

    def test_all_pictures_unused_still_keeps_the_original(self) -> None:
        self.docx("产品原稿.docx", {"image1.png": self.PNG + b"1"})
        self.imported()
        for m in [m for m in self.manifest()["materials"] if m["kind"] == "image"]:
            importer.mark_unused(self.feature_root, self.feature_root / m["paths"][0], "旧稿")
        self.round_now()
        self.assertIn("local:产品原稿.docx", [o["source_id"] for o in self.manifest()["origins"]])

    def test_two_originals_sharing_a_picture_both_stay_traceable(self) -> None:
        self.docx("甲.docx", {"image1.png": self.PNG + b"same"})
        self.docx("乙.docx", {"image1.png": self.PNG + b"same"})
        self.imported()
        self.round_now()
        images = [m for m in self.manifest()["materials"] if m["kind"] == "image"]
        self.assertEqual(1, len(images), "同一张图按内容只登记一次")
        self.assertEqual(2, len(images[0]["paths"]))
        for key in ("甲.docx", "乙.docx"):
            origin = next(o for o in self.manifest()["origins"] if o["source_id"] == f"local:{key}")
            self.assertEqual(1, len(origin["image_paths"]))

    def test_images_without_pictures_are_refused(self) -> None:
        self.docx("没有图.docx", {})
        self.refused("没有图.docx", "IMAGES")


class TheInboxIsReadRecursively(ManifestCase):
    """收件箱按目录原样收件：子目录里的原件按相对路径识别、归类、导入与登记。

    不同目录下的同名原件各成一个来源，不请人改名，也不互相覆盖。
    """

    def test_nested_and_flat_originals_import_together(self) -> None:
        self.put("2026-09 评审/第二轮/补充 说明.md", "# 补充\n\n规则二。\n")
        self.put("总体.md", "# 总体\n\n规则一。\n")
        self.put("界面稿/首页说明.md", "# 首页\n\n入口在顶部。\n", "UX")
        self.imported()
        self.round_now()
        for key, cls in (("2026-09 评审/第二轮/补充 说明.md", "RR"), ("总体.md", "RR"), ("界面稿/首页说明.md", "UX")):
            self.assertEqual(cls, self.source(key)["class"])
        self.assertEqual([], self.manifest()["inbox"])

    def test_an_inbox_root_link_is_refused_by_import_and_the_manifest(self) -> None:
        """收件箱根本身指到别处：导入、材料索引都在写入前拒绝。"""
        outside = self.root / "外面"
        outside.mkdir()
        (outside / "别处原件.md").write_text("# 别处\n\n不属于这张单。\n", encoding="utf-8")
        (outside / ".classify.json").write_text(json.dumps({"别处原件.md": "RR"}, ensure_ascii=False), encoding="utf-8")
        inbox = self.inbox()
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
        self.assertEqual(before, self.snapshot(), "根联接被跟随，别处的原件进了材料")
        flow = self.run_flow("round")
        self.assertNotEqual(0, flow.returncode, flow.stdout)
        self.assertIn("需求目录之外", flow.stdout + flow.stderr)

    def test_a_linked_file_inside_the_inbox_is_refused(self) -> None:
        outside = self.root / "外面.md"
        outside.write_text("# 别处\n", encoding="utf-8")
        link = self.inbox() / "链接.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("这台机器建不了文件符号链接")
        self.refused("链接.md", "是链接或指到收件箱之外")

    def test_a_linked_directory_is_not_followed(self) -> None:
        import os  # noqa: PLC0415
        outside = self.root / "inbox 之外"
        outside.mkdir()
        (outside / "外部.md").write_text("# 外部\n", encoding="utf-8")
        self.inbox().mkdir(parents=True, exist_ok=True)
        link = self.inbox() / "链过去"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError as exc:
            try:
                import _winapi  # noqa: PLC0415  Windows 无符号链接权限时用目录联接
                _winapi.CreateJunction(str(outside), str(link))
            except (ImportError, OSError):
                self.skipTest(f"本机建不了目录链接：{exc}")
        self.refused("是链接或指到收件箱之外", "链过去")

    def test_a_new_original_in_a_subdirectory_is_pending(self) -> None:
        self.round_now()
        self.put("补料/第三轮/新规则.md")
        self.round_now()
        self.assertEqual(["补料/第三轮/新规则.md"], [i["file"] for i in self.manifest()["inbox"]])

    def test_the_same_name_in_two_directories_imports_both_without_overwriting(self) -> None:
        """两份同名 docx 各带不同的图：各成一个来源，正文与图各在自己的版本里。"""
        self.docx("产品/说明.docx", {"image1.png": self.PNG + b"product"}, cls="RR", text="产品侧规则")
        self.docx("研发/说明.docx", {"image1.png": self.PNG + b"dev"}, cls="RR", text="研发侧规则")
        self.imported()
        for key, text, blob in (("产品/说明.docx", "产品侧规则", b"product"), ("研发/说明.docx", "研发侧规则", b"dev")):
            folder = self.feature_root / self.source(key)["versions"][0]["dir"]
            self.assertIn(text, (folder / "text.md").read_text(encoding="utf-8"))
            self.assertEqual(self.PNG + blob, (folder / "images" / "image1.png").read_bytes())

    def test_a_case_only_difference_imports_both(self) -> None:
        self.put("甲/Flow.md", "# 甲\n\n大写那份。\n")
        self.put("乙/flow.md", "# 乙\n\n小写那份。\n")
        self.imported()
        self.assertNotEqual(self.source("甲/Flow.md")["versions"][0]["dir"], self.source("乙/flow.md")["versions"][0]["dir"])

    def test_the_same_stem_with_another_extension_is_another_source(self) -> None:
        self.put("规则.md", "# 规则\n\nmd 那份。\n")
        self.put("规则.txt", "txt 那份。\n")
        self.imported()
        self.assertNotEqual(self.source("规则.md")["versions"][0]["dir"], self.source("规则.txt")["versions"][0]["dir"])

    def test_changing_one_same_name_original_leaves_the_other_alone(self) -> None:
        """改其中一份重导，只有它出新版本，另一份的版本一个字节不动。"""
        self.docx("产品/说明.docx", {"image1.png": self.PNG + b"product"}, cls="RR", text="产品侧规则")
        self.docx("研发/说明.docx", {"image1.png": self.PNG + b"dev"}, cls="RR", text="研发侧规则")
        self.imported()
        first = self.snapshot()
        self.docx("研发/说明.docx", {"image1.png": self.PNG + b"dev v2"}, cls="RR", text="研发侧规则第二版")
        self.imported()
        after = self.snapshot()
        product = self.source("产品/说明.docx")
        self.assertEqual(1, product["latest_version"])
        for rel in (k for k in first if k.startswith(product["versions"][0]["dir"] + "/")):
            self.assertEqual(first[rel], after[rel], f"改了研发那份，产品那份的 {rel} 也被动了")
        self.assertEqual(2, self.source("研发/说明.docx")["latest_version"])

    def test_a_key_that_is_not_canonical_is_refused(self) -> None:
        self.put("甲/说明.md", cls=None)
        cf = self.inbox() / ".classify.json"
        for key in ("./甲/说明.md", "甲//说明.md", "../说明.md", "/甲/说明.md", "甲\\说明.md"):
            with self.subTest(key=key):
                cf.write_text(json.dumps({key: "RR"}, ensure_ascii=False), encoding="utf-8")
                self.refused("不是规范的相对路径")

    def test_a_key_without_its_original_is_refused(self) -> None:
        self.put("甲/说明.md")
        cf = self.inbox() / ".classify.json"
        classify = json.loads(cf.read_text(encoding="utf-8"))
        classify["旧/挪走了.md"] = "RR"
        cf.write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        self.refused("没有对应的原件", "旧/挪走了.md")

    def test_all_input_problems_come_in_one_report(self) -> None:
        self.put("甲/说明.md")
        self.put("乙/说明.md")
        self.put("没归类.md", cls=None)
        cf = self.inbox() / ".classify.json"
        cf.write_text(json.dumps({**json.loads(cf.read_text(encoding="utf-8")), "旧/挪走了.md": "RR"},
                                 ensure_ascii=False), encoding="utf-8")
        out = self.refused("「没归类.md」未给出归类", "旧/挪走了.md")
        self.assertNotIn("同名", out, "同名原件不是问题，不该进报告")

    def test_a_write_failure_midway_says_what_was_written_and_leaves_no_half_version(self) -> None:
        """写盘中途坏了：报出已导入与还在收件箱的件；没写全的版本不落位，重跑补全。"""
        from unittest import mock  # noqa: PLC0415
        self.put("总体.md")
        self.put("系统/接口.md", cls="SR")
        real = shutil.copyfile

        def flaky(src, dst, *args, **kwargs):
            if str(src).endswith("接口.md"):
                raise OSError("磁盘写保护（注入）")
            return real(src, dst, *args, **kwargs)

        with mock.patch.object(shutil, "copyfile", flaky):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        msg = str(caught.exception)
        self.assertIn("写盘中途失败", msg)
        self.assertIn("磁盘写保护（注入）", msg)
        self.assertIn("总体.md", msg)
        self.assertIn("系统/接口.md", msg)
        self.assertTrue((self.inbox() / "系统" / "接口.md").exists(), "没导成的原件不该离开收件箱")
        self.assertFalse([p for p in (self.feature_root / "sources").glob("接口*")], "半个版本落了位")
        self.imported()
        self.assertEqual(1, self.source("系统/接口.md")["latest_version"])

    def test_a_failure_while_saving_a_meeting_version_is_named_and_rerun_recovers(self) -> None:
        from unittest import mock  # noqa: PLC0415
        self.docx("澄清会.docx", {}, cls="MEETING")
        real = Path.write_text

        def flaky(path, *args, **kwargs):
            if path.name == "raw.md" and "meetings" in path.parts:
                raise OSError("磁盘写保护（注入）")
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "write_text", flaky):
            with self.assertRaises(importer.ImportError_) as caught:
                importer.cmd_import(self.feature_root, self.root)
        self.assertIn("澄清会.docx", str(caught.exception))
        self.imported()
        self.assertTrue(list(self.feature_root.glob("AR/story-src/meetings/澄清会/*/raw.md")), "重跑导入没有补全会议留存")


class UpdateSeesNewVersions(ManifestCase):
    """update 按来源与版本认「上次以来新导入了什么」，提示可能被取代的同类来源；读不出索引不说成「没有新料」。"""

    def test_a_new_version_and_a_new_source_are_both_seen(self) -> None:
        from flow import update  # noqa: PLC0415
        self.put("评审/第一轮.md", "# 一\n\n旧。\n")
        self.imported()
        self.round_now()
        closed = [("u1", {"status": "closed", "sources": update._sources(self.feature_root)})]
        self.put("评审/第一轮.md", "# 一\n\n改了。\n")
        self.put("评审/第二轮.md", "# 二\n\n新增。\n")
        self.imported()
        self.round_now()
        got = sorted((s["source_id"], s["version"]) for s in update._imported_since(self.feature_root, closed))
        self.assertEqual([("local:评审/第一轮.md", 2), ("local:评审/第二轮.md", 1)], got)

    def test_the_superseded_hint_lists_same_class_sources(self) -> None:
        from flow import update  # noqa: PLC0415
        self.put("新版/规则 v2.md")
        self.round_now()
        hint = update._superseded_hint(self.feature_root, ["新版/规则 v2.md"])
        self.assertEqual(["local:RR/prd.md"], hint[0]["same_class"], "只列同类的已有来源")

    def test_an_unreadable_manifest_is_not_reported_as_nothing_new(self) -> None:
        from flow import update  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415
        self.round_now()
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text("{坏了", encoding="utf-8")
        with self.assertRaises(FlowError) as caught:
            update._imported_since(self.feature_root, [("u1", {"status": "closed", "sources": []})])
        self.assertIn("说不出上次以来导入了哪些版本", str(caught.exception))


class ImageLinksKeepTheirFullTarget(ManifestCase):
    """原件名带空格与括号不要求改名：图片引用按完整目标认出登记的那一张，身份、去处与断链三处核对都成立（A4）。"""

    NAME = "界面稿/申请 页（一）(v2).png"
    STORY_JS = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story"

    def prepare(self, name: str = NAME) -> None:
        """真实导入一张名字带空格与括号的界面图。"""
        self.put(name, self.PNG + b"a", "UX")
        self.imported()
        self.round_now()
        self.registered = self.source(name)["versions"][0]["original"]["path"]
        self.generated = f"![申请页]({importer.md_target('../' + self.registered)})"

    def node(self, script: str, *args: str) -> object:
        head = "".join(f"const {n} = await import({json.dumps((self.STORY_JS / f).resolve().as_uri())});"
                       for n, f in (("img", "images.mjs"), ("lang", "language.mjs")))
        proc = subprocess.run(["node", "--input-type=module", "-e", head + script, "--", *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def check(self, story: str) -> dict:
        """正文交给三处真实核对：本章身份、整篇去处与重复、断链。"""
        ar = self.feature_root / "AR"
        return self.node(
            "import * as fs from 'node:fs'; import * as path from 'node:path';"
            f"const ctx = {{projectRoot: {json.dumps(str(self.root))}, srcDir: {json.dumps(str(ar / 'story-src'))},"
            f" featureRoot: {json.dumps(str(self.feature_root))},"
            f" storyPath: {json.dumps(str(ar / 'story.md'))}}};"
            "const t = process.argv[1];"
            "process.stdout.write(JSON.stringify({chapter: img.chapterImageProblems(ctx, t, n => `L${n}`),"
            f" whole: img.imageProblems(ctx, t).problems, broken: lang.scanBrokenImages(t, {json.dumps(str(ar))}, fs, path)}}));",
            story)

    def test_the_docx_text_links_its_pictures_with_a_legal_target(self) -> None:
        """docx 的转换正文引用本版本的图：目标合法、文件在。"""
        self.docx("界面稿/申请 页（一）(v2).docx", {"image1.png": self.PNG + b"a"}, cls="RR")
        self.imported()
        folder = self.feature_root / self.source("界面稿/申请 页（一）(v2).docx")["versions"][0]["dir"]
        self.assertIn("![image1.png](images/image1.png)", (folder / "text.md").read_text(encoding="utf-8"))
        self.assertTrue((folder / "images" / "image1.png").is_file())

    def test_every_legal_spelling_reaches_the_registered_image(self) -> None:
        self.prepare()
        self.assertIn(" ", self.registered)
        self.assertIn("(v2)", self.registered)
        plain = "../" + self.registered
        spellings = {
            "任务包给出的引用": self.generated,
            "空格编码、成对括号": "![申请页](" + plain.replace(" ", "%20") + ")",
            "空格编码、括号转义": "![申请页](" + plain.replace(" ", "%20").replace("(", "\\(").replace(")", "\\)") + ")",
            "尖括号里再编码": "![申请页](<" + plain.replace("（", "%EF%BC%88") + ">)",
        }
        for label, ref in spellings.items():
            with self.subTest(label):
                out = self.check(f"申请页如下。\n\n{ref}\n")
                self.assertEqual([], out["chapter"], ref)
                self.assertEqual([], out["broken"], ref)
                self.assertEqual([], out["whole"], f"{ref} 没认作登记的那张，或误报没被引用")

    def test_real_problems_are_still_reported(self) -> None:
        self.prepare()
        plain = "../" + self.registered
        out = self.check("![别的图](<../sources/别的 图.png>)\n")
        self.assertTrue(any("不在材料的图片登记里" in p for p in out["chapter"]), out)
        self.assertTrue(out["broken"], "真实不存在的文件没报断链")
        self.assertTrue(any("没被引用" in p for p in out["whole"]), "登记的图没去处却没报")
        out = self.check(f"{self.generated}\n\n{self.generated}\n")
        self.assertTrue(any("被引用了不止一次" in p for p in out["whole"]), out)
        out = self.check(f"{self.generated}\n\n![申请页]({plain.replace(' ', '%20')})\n")
        self.assertTrue(any("同一张图被两个路径引用" in p for p in out["whole"]), out)
        out = self.check(f"![申请页]({plain})\n")
        self.assertTrue(any("写法解析不了" in p for p in out["chapter"]), "空格没包尖括号的写法被静默跳过")
        out = self.check("![坏编码](../sources/%E4%ZZ.png)\n")
        self.assertTrue(out["broken"], "坏编码既没报也不该抛栈")
        importer.mark_unused(self.feature_root, self.feature_root / self.registered, "旧稿，不属于本单")
        self.round_now()
        out = self.check(f"申请页如下。\n\n{self.generated}\n")
        self.assertTrue(any("登记着不用的理由" in p for p in out["chapter"]), out)

    def test_url_separators_in_the_real_name_stay_part_of_the_path(self) -> None:
        """原名带 `#`、`&`、`;`：生成目标编码 `#`，读者不把后半截当片段；三者的百分编码都还原回原名。"""
        self.prepare("界面稿/方案#2 & 补充;v3.png")
        self.assertIn("#", self.registered)
        self.assertNotIn("#", self.generated.split("](", 1)[1], "未编码的 # 在读者那里是片段分隔")
        plain = "../" + self.registered
        encoded = plain.replace(" ", "%20").replace("#", "%23").replace("&", "%26").replace(";", "%3B")
        for ref in (self.generated, f"![方案页]({encoded})"):
            with self.subTest(ref):
                out = self.check(f"方案页如下。\n\n{ref}\n")
                self.assertEqual([], out["chapter"], ref)
                self.assertEqual([], out["broken"], ref)
                self.assertEqual([], out["whole"], ref)
        out = self.check(f"![方案页]({plain.replace(' ', '%20')})\n")
        self.assertTrue(out["broken"], "未编码的 # 之后是片段，路径只剩前半截，该报断链")
        self.assertTrue(any("不在材料的图片登记里" in p for p in out["chapter"]), out)

    def test_both_producers_share_one_spelling_that_round_trips(self) -> None:
        names = ["sources/首页 (旧)-v1/首页 (旧).png", "sources/a%20b<c>-v1/a.png", "sources/plain-v1/plain.png",
                 "sources/a#b?c&d;e-v1/x.png", "sources/100%25-v1/x.png"]
        js = self.node("process.stdout.write(JSON.stringify(process.argv.slice(1).map(p => {"
                       " const t = lang.markdownTarget(p); return [t, lang.imageLinks(`![x](${t})`).images[0]?.path]; })));",
                       *names)
        for name, (target, back) in zip(names, js):
            with self.subTest(name):
                self.assertEqual(importer.md_target(name), target, "导入端与作者任务包的写法不一致")
                self.assertEqual(name, back, "写出去的目标还原不回原名")


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


class SourceClassesComeFromTheContract(unittest.TestCase):
    """上游来源的类与必需性只在章节合同登记一份：系统取材的角色、导入的类与必需性判定都对得上它。

    合同只登记类，不登记路径：材料的位置由材料索引按版本给出，固定路径一写就会和版本目录分叉。
    """

    CONTRACT = STORY_SCRIPTS.parents[1] / "contracts" / "story-chapters.json"

    def test_the_contract_declares_classes_not_paths(self) -> None:
        sources = json.loads(self.CONTRACT.read_text(encoding="utf-8"))["sources"]
        self.assertEqual(set(importer.SYSTEM_ROLES), set(sources), "系统取材的角色与合同登记的类对不上")
        self.assertTrue(set(sources) <= set(importer.CLASSES))
        for cls, decl in sources.items():
            self.assertNotIn("path", decl, f"合同又给 {cls} 登记了固定路径")


class AManifestAppearsWithoutAnyDataLayer(unittest.TestCase):
    """材料是谁放的都不影响清单：换一份不认识清单的替身取材，round 照样算得出来。"""

    def test_a_stand_in_data_layer_still_gets_a_manifest(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feature_root = root / "doc" / "features" / FEATURE
        # 替身「对接层」：只把取回的正文和回执放进收件箱的批次目录，对索引一无所知
        batch = feature_root / "sources" / "inbox" / "fetch-1"
        batch.mkdir(parents=True)
        (batch / "RR-prd.md").write_text("# 产品需求\n", encoding="utf-8")
        (batch / ".receipt.json").write_text(json.dumps({"reqNo": FEATURE, "items": [
            {"name": "RR-prd.md", "role": "RR", "ticket": "RR1", "status": "fetched"}]}), encoding="utf-8")

        def run(script: Path, *args: str) -> None:
            proc = subprocess.run([sys.executable, str(script), *args, "--feature", FEATURE, "--project-root", str(root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=120, cwd=str(REPO_ROOT))
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        run(FLOW, "round")
        manifest = json.loads((feature_root / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["digest"])
        self.assertEqual(["fetch-1/RR-prd.md"], [i["file"] for i in manifest["inbox"]])
        self.assertEqual("RR", manifest["inbox"][0]["class"], "回执列着的件按角色归类")
        run(STORY_SCRIPTS / "import_sources.py")
        run(FLOW, "round")
        manifest = json.loads((feature_root / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))
        self.assertEqual(["system:RR:RR1"], [s["source_id"] for s in manifest["sources"]])


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
    """流程契约与需求分析件住在 `story-src/`，但都不进登记指纹。

    两件在登记之后还要写：契约要记归档态与重新登记，分析件随初析演进。
    记进登记指纹，登记之后的每一步都会被判成「登记之后改过」。
    """

    NAMES = property(lambda self: [CONTRACT[-1], "init-analysis.md"])

    def test_none_of_them_is_a_frozen_ledger(self) -> None:
        """两件都留，但都不进登记指纹——指纹记的是 story 与「据以成文的依据」，它们还要继续变。"""
        for name in self.NAMES:
            self.assertNotIn(f"AR/story-src/{name}", STORY_REGISTERED)

    def test_they_live_under_story_src_not_the_ar_root(self) -> None:
        """路径本身就是判据：`AR/` 根下只放交付文档，辅助件在 `story-src/` 这一层。"""
        self.assertEqual(("AR", "story-src", "story-flow.json"), CONTRACT)


class DraftsAreNotFrozenIntoTheLedger(unittest.TestCase):
    """草稿不进登记指纹：它不是 story 据以成文的依据，是写它的过程。"""

    def test_drafts_are_not_frozen_into_the_ledger(self) -> None:
        self.assertFalse(any("/drafts" in rel for rel in STORY_REGISTERED))


class RegistrationReprojectsFirst(unittest.TestCase):
    """定稿在审查之前：准备审查时按 project → number → build → check 把被审对象定成最终版；登记只读核对。

    附录的机器区是已准入蓝图的投影，而真源在成文期间还会变。登记再动它，审的就不是登记的那一份。
    """

    def test_the_order_is_project_then_number_then_check(self) -> None:
        source = (DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs").read_text(encoding="utf-8")
        body = source.split("function cmdReview(", 1)[1].split("\n}\n", 1)[0]
        order = [body.index(step) for step in ("cmdProject(ctx)", "cmdNumber(ctx)", "cmdBuild(ctx)", "storyCheck(ctx", "prepareReview(")]
        self.assertEqual(sorted(order), order, "准备审查时没有先定稿再检查、再准备请求")
        lifecycle = (DEV_EXT / "skills" / "story" / "scripts" / "core" / "flow" / "lifecycle.py").read_text(encoding="utf-8")
        registration = lifecycle.split("def cmd_story(", 1)[1].split("\ndef ", 1)[0]
        for gone in ('"project"', '"number"', 'build("build")'):
            self.assertNotIn(gone, registration, "登记又在改被审对象")

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
