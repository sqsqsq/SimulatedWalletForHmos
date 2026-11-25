"""需求交给设计：材料确认后直接进原生 component-design，蓝图与需求同根，需求条目引 `sources/` 的材料版本。

这一份锁：材料确认之后路由按原生蓝图派生位置，没有交接命令、不写契约；`import_sources.py --scope` 按材料索引
补齐需求条目的来源——系统来源另写原生物化信封并过原生检查，本地来源不落 provider 文件，引了没登记的文件拒绝且不写盘；
蓝图的需求条目采用了本需求的材料版本才进成文；设计开始之后材料再变只登记进本轮，设计开始之前照常开新轮；
旧 schema 的契约明确拒绝；同一时点只取一份材料事实；成文登记跑真的检查器。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT, REPO_ROOT
import design_kit
import shared_state
from flow_steps import answer, ensure_framework, write_gaps

STORY_SCRIPTS = DEV_EXT / "base" / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"
IMPORT = STORY_SCRIPTS / "import_sources.py"
ACCESS = DEV_EXT / "base" / "hooks" / "shared" / "framework-access.mjs"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.decisions import cmd_decide  # noqa: E402
from flow.inputs import MATERIAL_REQUEST_KEYS  # noqa: E402
from flow.lifecycle import cmd_status  # noqa: E402
from materials import importer, registry  # noqa: E402

FEATURE = "AR90001"
#: 原件按它在收件箱里的位置引用图（RR/prd.md → assets/flow.svg）；导入后阅读稿改指图的版本位置
PRD = "# 产品需求\n\n## 背景\n\n签约流程见下图：\n\n![签约流程](../assets/flow.svg)\n"
AUTHORITY = {"owner": "需求负责人", "formality": "formal_requirement"}


class HandoverCase(unittest.TestCase):
    """一份接入 demo Framework 的新工程，跑真脚本走到「材料已确认」，再各自测交给设计。"""

    feature = FEATURE

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lay_out(Path(self._tmp.name))
        #: 还停在默认材料、没有别的改动：第一次 ready() 可以从共享的「范围已定」前态起手
        self._pristine = True

    def lay_out(self, root: Path) -> None:
        """接入 demo Framework 的新工程，默认三份材料经真实导入器导成材料版本。"""
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        ensure_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / self.feature
        (self.feature_root / "AR").mkdir(parents=True)
        self.src = self.feature_root / "AR" / "story-src"
        self.seed({"RR/prd.md": (PRD, "RR"), "assets/flow.svg": ("<svg xmlns='http://www.w3.org/2000/svg'/>\n", "UX"),
                   "SR/design.md": ("# 系统设计\n\n分工。\n", "SR")})

    def seed(self, files: dict[str, tuple[str, str]], receipt: dict | None = None) -> None:
        """经真实导入器导成材料版本，各来源最新版本的原件路径存成属性。给了 `receipt` 时这批件是一次系统取材。"""
        self._pristine = False
        inbox = self.feature_root / "inbox"
        batch = inbox / "fetch-1" if receipt else inbox
        classify = {}
        for rel, (text, cls) in files.items():
            (batch / rel).parent.mkdir(parents=True, exist_ok=True)
            (batch / rel).write_text(text, encoding="utf-8")
            classify[rel] = cls
        if receipt:
            (batch / ".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        else:
            (inbox / ".classify.json").write_text(json.dumps(classify), encoding="utf-8")
        importer.cmd_import(self.feature_root, self.root)
        self.note_latest()

    def note_latest(self) -> None:
        latest = {s["source_id"]: s["versions"][-1]["original"]["path"] for s in registry.read(self.feature_root)["sources"]}
        self.prd_rel = latest.get("local:RR/prd.md")
        self.flow_rel = latest.get("local:assets/flow.svg")

    # -- 驱动 ---------------------------------------------------------------

    def flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", self.feature, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO_ROOT))

    def ok(self, *args: str) -> dict:
        proc = self.flow(*args)
        self.assertEqual(0, proc.returncode, f"{args} 失败：{proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def write_analysis(self) -> None:
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / ".positioning.json").write_text(json.dumps(
            {"scope_source": "user_stated", "scope_text": "本 AR 承载自动充值签约与管理", "sr_related_ars": []},
            ensure_ascii=False), encoding="utf-8")

    def ready(self) -> None:
        """S1–S3 走完、材料确认：停在「交给设计」。

        默认材料上、没有别的改动时，这一段同一组输入只真实跑一次（共享），本例换成那份结果；改过材料或已走过的照常真跑。"""
        if self._pristine:
            self._pristine = False
            key = shared_state.digest(*shared_state.COMMON, Path(__file__), shared_state.framework_version(), self.feature)
            base = shared_state.shared_tree("handover-ready", key, self._walk_default)
            for child in self.root.iterdir():
                if child.name != "framework":
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            shared_state.copy_tree(base, self.root)
            self.note_latest()
            return
        self.walk()

    def _walk_default(self, base: Path) -> None:
        saved = (self.root, self.feature_root, self.src)
        try:
            self.lay_out(base)
            self.walk()
        finally:
            self.root, self.feature_root, self.src = saved

    def walk(self) -> None:
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "2")
        self.write_analysis()
        self.ok("round")

    def answers_rel(self) -> str:
        """人工答复的最新版本里给人读的那份。"""
        answers = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "answer")
        return answers["versions"][-1]["readable"]["path"]

    def scope(self, items: list[dict], *extra: str) -> subprocess.CompletedProcess:
        path = self.root / "scope-items.json"
        path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(IMPORT), "--feature", self.feature, "--project-root", str(self.root), "--scope", str(path), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def scoped(self, items: list[dict], *extra: str) -> dict:
        proc = self.scope(items, *extra)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def tree(self) -> dict[str, bytes]:
        features = self.root / "doc" / "features"
        return {p.relative_to(features).as_posix(): p.read_bytes() for p in features.rglob("*") if p.is_file()}


def item(source: str, item_id: str = "request-main", kind: str = "requirement") -> dict:
    return {"item_id": item_id, "kind": kind, "source": source, "authority": AUTHORITY}


class MaterialConfirmedGoesStraightToDesign(HandoverCase):
    """材料确认，下一步就是原生 component-design：没有交接命令，契约里不记设计关联与输入。"""

    def test_status_points_at_component_design_and_writes_nothing(self) -> None:
        self.ready()
        before = self.tree()
        status = self.ok("status")
        self.assertEqual(("waiting_for_design", "design_blueprint"), (status["state"], status["next"]))
        self.assertEqual({"blueprint_id": FEATURE, "exists": False}, status["blueprint"])
        for needle in ("component-design", f"`{FEATURE}/blueprint/`", "import_sources.py --scope"):
            self.assertIn(needle, status["action"])
        contract = self.contract()
        self.assertEqual("gathering", contract["status"])
        self.assertFalse({"input", "design_binding"} & set(contract), "契约又记了设计关联或输入")
        self.assertEqual(before, self.tree(), "status 是只读查询，却写了需求目录")

    def test_the_retired_commands_are_gone(self) -> None:
        self.ready()
        for mode in ("bind-design", "complete", "reopen"):
            with self.subTest(mode=mode):
                proc = self.flow(mode)
                self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("invalid choice", proc.stderr)

    def test_an_old_contract_is_refused_with_its_schema(self) -> None:
        """旧版本的契约不迁移：明确说是哪一版、当前是哪一版。"""
        self.ready()
        old = {**self.contract(), "schema": 5, "status": "complete"}
        (self.src / "story-flow.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        before = (self.src / "story-flow.json").read_bytes()
        proc = self.flow("status")
        self.assertEqual(1, proc.returncode)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertIn("schema 5", error)
        self.assertIn("当前 7", error)
        self.assertIn("不接续", error)
        self.assertEqual(before, (self.src / "story-flow.json").read_bytes(),
                         "旧现场被自动迁移或改写了字节")


class DesignQuestionsAreBoundToWhatWasAsked(HandoverCase):
    """设计后必要问答：一次集中 ask、内容身份绑定、错绑拒绝；原话只作证据，部分答复只续问未答部分。"""

    def setUp(self) -> None:
        super().setUp()
        self.ready()
        # 只证明设计已开始（同根蓝图在盘上）；本组不核蓝图内容
        (self.feature_root / "blueprint").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "blueprint" / "component-blueprint.yaml").write_text(
            "component_id: wallet-main\n", encoding="utf-8")

    def item(self, item_id: str, question: str, options: list[str] | None = None,
             recommend: str = "", **extra) -> dict:
        return {"item_id": item_id, "question": question,
                "options": options if options is not None else [],
                "recommend": recommend, "reason": "阻断当前切片，当前用户有权决定",
                "source_ref": f"doc/features/{self.feature}/AR/story.md", **extra}

    def questions(self, *items: dict, name: str = "questions.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps({"items": list(items)}, ensure_ascii=False), encoding="utf-8")
        return path

    def ask(self, *items: dict) -> dict:
        path = self.questions(*items)
        out = self.ok("status", "--questions-file", str(path))
        self.assertEqual("await_questions", out["next"], out)
        return out["ask"]

    def test_two_questions_share_one_ask_and_one_display_block(self) -> None:
        """两个符合条件的问题用同一个 ask、同一个展示块；第三方待定的那项仍留在待答集合。"""
        gates_before = [g["gate"] for g in self.contract()["rounds"][-1]["gates"]]
        ask = self.ask(
            self.item("Q1", "失败后是否允许自动重试？", ["允许再试一次", "保持待定"], "允许再试一次"),
            self.item("Q2", "宽限期多长？", ["24 小时", "48 小时"]))
        self.assertEqual(["Q1", "Q2"], ask["pending"])
        self.assertEqual([], ask["answered"])
        self.assertEqual("Q1", ask["items"][0]["item_id"])
        block = ask["block"]
        self.assertIn("【Q1】失败后是否允许自动重试？", block)
        self.assertIn("【Q2】宽限期多长？", block)
        self.assertIn("建议：允许再试一次", block)
        # 出处留在结构字段与导出，不贴进给人的展示块
        self.assertNotIn("出处", block, "展示块又贴了内部出处")
        self.assertNotIn(f"doc/features/{self.feature}", block, "展示块里出现了机器路径")
        self.assertEqual(f"doc/features/{self.feature}/AR/story.md", ask["items"][1]["source_ref"],
                         "出处没有留在结构字段里")
        self.assertEqual(gates_before, [g["gate"] for g in self.contract()["rounds"][-1]["gates"]],
                         "设计问答写进了 material 关卡记录")
        self.assertNotIn("gates", json.dumps(ask, ensure_ascii=False), "问法把 gate 状态带进了展示")
        self.assertEqual([], self.contract()["rounds"][-1].get("answers") or [],
                         "只生成问法就写了答复")

    def test_the_same_question_file_is_idempotent(self) -> None:
        first = self.ask(self.item("Q1", "要不要重试？", ["要", "不要"]))
        second = self.ask(self.item("Q1", "要不要重试？", ["要", "不要"]))
        self.assertEqual(first["ask_id"], second["ask_id"], "同一问法重跑换了身份")
        self.assertEqual([], second.get("replaced_unanswered") or [])

    def test_an_invalid_question_file_writes_nothing(self) -> None:
        """缺必需字段 / 建议不在候选里：一次报全，不生成问法。"""
        bad = self.questions({"item_id": "Q1", "question": "要不要重试？", "options": ["要"], "recommend": "不要"})
        (self.src / ".ask.json").unlink(missing_ok=True)
        proc = self.flow("status", "--questions-file", str(bad))
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        for needle in ("reason", "source_ref", "recommend 不在 options 里"):
            self.assertIn(needle, error, error)
        self.assertFalse((self.src / ".ask.json").exists(), "形状不立住却写了问法")

    def test_a_question_file_before_the_design_is_refused(self) -> None:
        (self.feature_root / "blueprint" / "component-blueprint.yaml").unlink()
        proc = self.flow("status", "--questions-file", str(self.questions(self.item("Q1", "要不要重试？"))))
        self.assertEqual(1, proc.returncode)
        self.assertIn("设计还没开始", json.loads(proc.stdout[proc.stdout.index("{"):])["error"])

    def test_a_partial_answer_keeps_only_the_unanswered_questions(self) -> None:
        ask = self.ask(self.item("Q1", "失败后是否允许自动重试？", ["允许再试一次", "保持待定"]),
                       self.item("Q2", "宽限期多长？", ["24 小时", "48 小时"]))
        out = self.ok("decide", "--ask", ask["ask_id"], "--item", "Q1", "--reply", "保持待定")
        self.assertEqual(["Q2"], out["pending"])
        self.assertEqual("await_questions", out["next"])
        self.assertIn("【Q2】宽限期多长？", out["ask_block"])
        self.assertNotIn("【Q1】", out["ask_block"], "已答的题又被重问一遍")
        self.assertTrue(out["nextAction"].endswith(out["ask_block"]), "action 与 ask_block 不是同一个展示块")
        state = self.ok("status")
        self.assertEqual((ask["ask_id"], ["Q2"], "await_questions"),
                         (state["ask"]["ask_id"], state["ask"]["pending"], state["next"]),
                         "普通 status 没返回同一组未答完的问法")
        self.assertEqual(out["ask_block"], state["ask"]["block"], "部分答复后两个入口给出的展示块不一致")
        self.assertNotIn("【Q1】", state["ask"]["block"], "status 的展示块里仍有已答的题")
        self.assertEqual([], [it for it in state["ask"]["items"] if it["item_id"] == "Q1"],
                         "status 的展示问法里仍有已答的题")
        row = self.contract()["rounds"][-1]["answers"][0]
        self.assertEqual("保持待定", row["reply"], "「保持待定」不是真实答复")
        self.assertNotIn("chosen", row)
        self.assertFalse({"target_ref", "source_revision", "mapped_by"} & set(row))
        export = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "answer")
        text = (self.feature_root / export["versions"][-1]["readable"]["path"]).read_text(encoding="utf-8")
        self.assertIn("保持待定", text)
        self.assertIn("出处：", text, "导出里没留出处")
        self.assertNotIn("人的裁决", text)

    def test_a_path_like_item_id_gets_a_human_number_and_the_record_keeps_the_id(self) -> None:
        """item_id 是原生地址时展示层按本组原顺序给人读序号；记录仍取原 item_id，部分答复后保原序。"""
        first = "view:logical/node:wallet-balance"
        ask = self.ask(self.item(first, "余额刷新在哪触发？", ["回到首页", "切账号"]),
                       self.item("view:logical/node:grace", "宽限期多长？", ["24 小时", "48 小时"]))
        self.assertIn("【第 1 题】余额刷新在哪触发？", ask["block"])
        self.assertIn("【第 2 题】宽限期多长？", ask["block"])
        self.assertNotIn("view:logical", ask["block"], "展示块里出现了原生地址")
        out = self.ok("decide", "--ask", ask["ask_id"], "--item", first, "--reply", "回到首页")
        self.assertIn("【第 2 题】宽限期多长？", out["ask_block"], "部分答复后余题的序号没有按本组原顺序")
        self.assertNotIn("【第 1 题】", out["ask_block"])
        self.assertNotIn("view:logical", out["ask_block"])
        self.assertIn("ask_block", out["nextAction"])
        self.assertNotIn("ask.block", out["nextAction"], "decide 的下一步又指了它没有的字段")
        state = self.ok("status")
        self.assertEqual(out["ask_block"], state["ask"]["block"], "两个入口的展示块不一致")
        self.assertNotIn("view:logical", state["action"], "普通 status 的展示里出现了原生地址")
        row = self.contract()["rounds"][-1]["answers"][0]
        self.assertEqual(first, row["item_id"], "记录把展示序号当成了新的绑定身份")
        self.assertEqual(f"doc/features/{self.feature}/AR/story.md", row["source_ref"],
                         "系统侧查不回原问法的出处")

    def test_a_readable_id_colliding_with_a_generated_number_stays_unique(self) -> None:
        """一组里只要有一题要改人读序号，整组就按原位置编号：`decision:one` 与可读的「第 1 题」不再同名。

        展示唯一、稳定；记录仍取结构化 items 的原 item_id；部分答复只筛余题、序号不重排；零待答照原协议退出。
        """
        first, second = "decision:one", "第 1 题"
        ask = self.ask(self.item(first, "谁负责验收？"), self.item(second, "何时生效？"))
        self.assertIn("【第 1 题】谁负责验收？", ask["block"])
        self.assertIn("【第 2 题】何时生效？", ask["block"])
        self.assertNotIn("decision:one", ask["block"], "展示块里出现了原生地址")
        self.assertEqual(2, len(re.findall(r"【第 \d+ 题】", ask["block"])), "同一题号被两题共用")
        self.assertEqual(2, len(set(re.findall(r"【第 (\d+) 题】", ask["block"]))), "展示题号重名")
        out = self.ok("decide", "--ask", ask["ask_id"], "--item", first, "--reply", "由业务方验收。")
        self.assertEqual([second], out["pending"])
        self.assertIn("【第 2 题】何时生效？", out["ask_block"])
        self.assertNotIn("【第 1 题】", out["ask_block"], "部分答复后余题被重新编号")
        state = self.ok("status")
        self.assertEqual(out["ask_block"], state["ask"]["block"], "两个入口的展示块不一致")
        self.assertEqual([second], state["ask"]["pending"])
        rows = self.contract()["rounds"][-1]["answers"]
        self.assertEqual(first, rows[0]["item_id"], "记录把展示序号当成了新的绑定身份")
        # 第二题的显示号是「第 2 题」，记录仍取原 item_id「第 1 题」
        last = self.ok("decide", "--ask", ask["ask_id"], "--item", second, "--reply", "上线当轮生效。")
        self.assertEqual([], last["pending"])
        self.assertEqual(second, self.contract()["rounds"][-1]["answers"][-1]["item_id"])
        done = self.ok("status")
        self.assertNotIn("ask", done, "零待答还返回了一组问法")
        self.assertNotIn("【", done["action"], "零待答还展示了一份空问卷")

    def test_a_readable_group_keeps_its_original_ids(self) -> None:
        """整组都适合直接展示时保留原号，不为它们另造一套位置号。"""
        ask = self.ask(self.item("Q1", "第一问？"), self.item("Q2", "第二问？"))
        self.assertIn("【Q1】第一问？", ask["block"])
        self.assertIn("【Q2】第二问？", ask["block"])
        self.assertNotIn("【第 1 题】", ask["block"], "全部可读时也改成了位置号")

    def test_a_mixed_group_numbers_every_item_by_original_position(self) -> None:
        """可读 ID 在前、原生地址在后：整组统一按原位置编号，不做「逐题混搭」。"""
        ask = self.ask(self.item("第 1 题", "第一问？"), self.item("view:logical/node:grace", "第二问？"),
                       self.item("Q3", "第三问？"))
        self.assertIn("【第 1 题】第一问？", ask["block"])
        self.assertIn("【第 2 题】第二问？", ask["block"])
        self.assertIn("【第 3 题】第三问？", ask["block"])
        self.assertNotIn("view:logical", ask["block"])
        self.assertNotIn("【Q3】", ask["block"], "整组改编号时还有题目保留原号")
        out = self.ok("decide", "--ask", ask["ask_id"], "--item", "Q3", "--reply", "第三问已定。")
        self.assertIn("【第 1 题】", out["ask_block"], "部分答复后余题序号没有按整组原位置")
        self.assertIn("【第 2 题】", out["ask_block"])
        self.assertNotIn("【第 3 题】", out["ask_block"])

    def test_one_reply_can_answer_two_questions_via_the_file(self) -> None:
        ask = self.ask(self.item("Q1", "失败后是否允许自动重试？"),
                       self.item("Q2", "宽限期多长？"))
        replies = self.root / "replies.json"
        replies.write_text(json.dumps({"items": [
            {"item_id": "Q1", "reply": "按这个方案做"}, {"item_id": "Q2", "reply": "按这个方案做"}]},
            ensure_ascii=False), encoding="utf-8")
        out = self.ok("decide", "--ask", ask["ask_id"], "--replies-file", str(replies))
        self.assertEqual([], out["pending"])
        rows = self.contract()["rounds"][-1]["answers"]
        self.assertEqual([("Q1", "按这个方案做"), ("Q2", "按这个方案做")],
                         [(r["item_id"], r["reply"]) for r in rows], "同一原话没有逐题引用")
        self.assertFalse((self.src / ".ask.json").exists(), "全部答完却还留着临时问法")

    def test_a_replacement_names_the_questions_it_left_unanswered(self) -> None:
        ask = self.ask(self.item("Q1", "失败后是否允许自动重试？"),
                       self.item("Q2", "宽限期多长？"))
        self.ok("decide", "--ask", ask["ask_id"], "--item", "Q1", "--reply", "允许再试一次")
        replacement = self.questions(self.item("Q3", "新发现的边界怎么定？"), name="questions-2.json")
        out = self.ok("status", "--questions-file", str(replacement))
        self.assertEqual(["Q2"], [it["item_id"] for it in out["ask"]["replaced_unanswered"]],
                         "替换掉未答问题时没说被替换的是哪题")
        self.assertEqual("宽限期多长？", out["ask"]["replaced_unanswered"][0]["question"],
                         "被替换的问法只留了题号、没留当时的原问题")
        kept = self.feature_root / out["ask"]["replaced_kept"]
        self.assertTrue(kept.is_file(), "被替换的未答问题没有留下原件")
        self.assertIn("宽限期多长？", kept.read_text(encoding="utf-8"))
        answers = self.contract()["rounds"][-1]["answers"]
        self.assertEqual(["Q1"], [a["item_id"] for a in answers], "替换问法丢了已答的原话")
        self.assertIn("为何失效", out["action"])

    def test_a_retry_with_the_same_file_shows_only_the_unanswered(self) -> None:
        """部分答过之后重试同一文件：停等状态与展示都只含未答的题，不重问已答的 A。"""
        path = self.questions(self.item("A", "第一问？"), self.item("B", "第二问？"))
        ask = self.ok("status", "--questions-file", str(path))["ask"]
        self.ok("decide", "--ask", ask["ask_id"], "--item", "A", "--reply", "答过了")
        again = self.ok("status", "--questions-file", str(path))
        self.assertEqual("await_questions", again["next"])
        self.assertEqual(["B"], again["ask"]["pending"])
        self.assertIn("【B】", again["action"])
        self.assertNotIn("【A】", again["action"], "同一文件重试又把已答的题摆了一遍")
        self.assertEqual(ask["ask_id"], again["ask"]["ask_id"], "同一问法重试换了身份")

    def test_after_every_question_is_answered_the_native_next_step_runs(self) -> None:
        """全部答完后重试同一文件：不再停在 await_questions，按原生下一步续行。"""
        path = self.questions(self.item("A", "第一问？"))
        ask = self.ok("status", "--questions-file", str(path))["ask"]
        self.ok("decide", "--ask", ask["ask_id"], "--item", "A", "--reply", "答完了")
        out = self.ok("status", "--questions-file", str(path))
        self.assertNotEqual("await_questions", out["next"], out)
        self.assertNotIn("ask", out, "零待答还返回了一组问法")
        self.assertNotIn("ask_block", out, "零待答还返回了展示块")
        self.assertNotIn("【", out["action"], "零待答还展示了一份空问卷")
        self.assertFalse((self.src / ".ask.json").exists(), "零待答还留着临时问法")

    def test_a_question_changed_behind_its_ask_id_is_refused(self) -> None:
        ask = self.ask(self.item("Q1", "失败后是否允许自动重试？"))
        sidecar = self.src / ".ask.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["items"][0]["question"] = "换了一个问法"
        sidecar.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        proc = self.flow("decide", "--ask", ask["ask_id"], "--item", "Q1", "--reply", "允许再试一次")
        self.assertEqual(1, proc.returncode)
        self.assertIn("ask_id 对不上", json.loads(proc.stdout[proc.stdout.index("{"):])["error"])

    def test_a_wrong_ask_or_item_is_refused(self) -> None:
        ask = self.ask(self.item("Q1", "失败后是否允许自动重试？"))
        for extra, needle in ((("--ask", "deadbeef", "--item", "Q1", "--reply", "允许再试一次"), "不是当前问法"),
                              (("--ask", ask["ask_id"], "--item", "Q9", "--reply", "允许再试一次"), "没有题「Q9」")):
            with self.subTest(needle=needle):
                proc = self.flow("decide", *extra)
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn(needle, json.loads(proc.stdout[proc.stdout.index("{"):])["error"])
        self.assertEqual([], self.contract()["rounds"][-1].get("answers") or [], "拒绝的答复写进了记录")


class ScopeItemsAreFilledFromTheIndex(HandoverCase):
    """需求条目的语义模型写一次，来源路径、摘要与 provenance 由脚本按材料索引补。"""

    def test_a_local_source_gets_native_items_and_no_provider_file(self) -> None:
        self.ready()
        answers = self.answers_rel()
        out = self.scoped([item(self.prd_rel), item(answers, "scope-ruling", "invariant")])
        main, ruling = out["current_scope_items"]
        prd = self.feature_root / self.prd_rel
        self.assertEqual(f"doc/features/{FEATURE}/{self.prd_rel}", main["source_ref"])
        self.assertEqual("sha256:" + hashlib.sha256(prd.read_bytes()).hexdigest(), main["source_sha256"])
        self.assertEqual(("requirement_material", "observed", "imported_file_observation"),
                         (main["provenance"]["source_kind"], main["provenance"]["evidence_strength"],
                          main["provenance"]["extraction_method"]))
        self.assertEqual(main["source_ref"], main["provenance"]["source_ref"])
        self.assertEqual(("human_statement", "observed"),
                         (ruling["provenance"]["source_kind"], ruling["provenance"]["evidence_strength"]),
                         "人工答复只作原话证据，整份 answer 不是 authoritative 授权")
        self.assertEqual(AUTHORITY, main["authority"])
        self.assertNotIn("materialization", out)
        self.assertFalse((self.feature_root / "blueprint").exists(), "本地来源不该落 provider 文件")

    def test_a_fragment_stays_on_the_reference(self) -> None:
        self.ready()
        [main] = self.scoped([item(f"{self.prd_rel}#背景")])["current_scope_items"]
        self.assertTrue(main["source_ref"].endswith(f"{self.prd_rel}#背景"))

    def test_a_file_outside_the_index_is_refused_and_nothing_is_written(self) -> None:
        self.ready()
        before = self.tree()
        proc = self.scope([item("AR/story-src/init-analysis.md"), item(self.prd_rel, "other")])
        self.assertEqual(1, proc.returncode)
        self.assertIn("不是材料索引登记的文件", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.tree())

    def test_a_bad_shape_is_named_item_by_item(self) -> None:
        self.ready()
        proc = self.scope([{"item_id": "x", "kind": "story", "source": self.prd_rel}])
        error = json.loads(proc.stdout)["error"]
        self.assertIn("kind 取", error)
        self.assertIn("authority 要有 owner 与 formality", error)


class SystemSourcesGetTheNativeEnvelope(HandoverCase):
    """需求系统取得的来源：同一组条目另写成原生来源物化信封，放在需求的 blueprint/ 里并过原生检查。"""

    def seed_system(self) -> str:
        self.seed({"RR-prd.md": ("# 系统上的产品需求\n\n签约。\n", "RR")},
                  receipt={"reqNo": FEATURE, "rrNo": "RR90001",
                           "items": [{"name": "RR-prd.md", "role": "RR", "ticket": "RR90001", "title": "产品需求",
                                      "status": "fetched"}]})
        source = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "system")
        return source["versions"][-1]["original"]["path"]

    def test_the_envelope_is_written_once_and_checked_natively(self) -> None:
        system = self.seed_system()
        self.ready()
        out = self.scoped([item(system)], "--component", "wallet-home")
        envelope = self.feature_root / "blueprint" / "requirement-source-materialization.json"
        self.assertEqual(f"doc/features/{FEATURE}/blueprint/requirement-source-materialization.json", out["materialization"])
        doc = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(("requirement-source-materialization@1", FEATURE, "wallet-home"),
                         (doc["artifact"], doc["blueprint_id"], doc["component_id"]))
        self.assertEqual(out["current_scope_items"], doc["items"])
        self.assertTrue(doc["items"][0]["provenance"]["source_revision"].startswith("system:RR:RR90001@v"))
        before = envelope.stat().st_mtime_ns
        self.scoped([item(system)], "--component", "wallet-home")
        self.assertEqual(before, envelope.stat().st_mtime_ns, "同一组条目重跑不该重写信封")

    def test_without_a_blueprint_the_component_must_be_given(self) -> None:
        system = self.seed_system()
        self.ready()
        proc = self.scope([item(system)])
        self.assertEqual(1, proc.returncode)
        self.assertIn("--component", json.loads(proc.stdout)["error"])
        self.assertFalse((self.feature_root / "blueprint").exists())

    def test_an_existing_blueprint_decides_the_component(self) -> None:
        system = self.seed_system()
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        doc = self.scoped([item(system)])
        self.assertTrue(doc["materialization"])
        proc = self.scope([item(system)], "--component", "wallet-other")
        self.assertIn(f"归属组件 {design_kit.COMPONENT}", json.loads(proc.stdout)["error"])


class TheDesignAdoptsThisRequirement(HandoverCase):
    """成文按的蓝图要真的采用了本需求的来源：准入、标识对得上还不够，需求条目要指向本需求已导入的材料版本。"""

    SOURCE = """
    const [module, root, feature] = process.argv.slice(1);
    const { designSource } = await import(module);
    const ctx = { projectRoot: root, args: { feature }, featureRoot: `${root}/doc/features/${feature}`,
                  flowPath: `${root}/doc/features/${feature}/AR/story-src/story-flow.json` };
    process.stdout.write(JSON.stringify(designSource(ctx).problems));
    """

    def source_problems(self) -> list[str]:
        module = (STORY_SCRIPTS / "story" / "design-source.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", self.SOURCE, module, str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_blueprint_adopting_this_requirement_is_ready_to_write(self) -> None:
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        before = self.tree()
        self.assertEqual(("ready_to_write", "story_skeleton"), (self.ok("status")["state"], self.ok("status")["next"]))
        self.assertEqual(before, self.tree(), "status 是只读查询，却写了需求或蓝图")
        self.assertEqual([], self.source_problems())

    def test_an_unadmitted_blueprint_is_written_from_its_draft(self) -> None:
        """准入没过：成文读原生草稿，照样到成文（准入只管施工单位开工）。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        design_kit.change_blueprint(self.root, self.feature, ACCESS,
                                    "  admission:\n    status: pass\n", "  admission:\n    status: blocked\n")
        self.assertEqual("ready_to_write", self.ok("status")["state"])

    def test_a_blueprint_on_another_requirements_sources_waits_for_the_design(self) -> None:
        """蓝图的需求条目还是夹具里另一份需求的来源：等设计同步，不成文。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS, consume=False)
        status = self.ok("status")
        self.assertEqual(("waiting_for_design", "design_blueprint"), (status["state"], status["next"]))
        self.assertIn("没有采用本需求的来源", status["action"])
        [problem] = self.source_problems()
        self.assertIn(f"没有引用需求 {FEATURE} 登记的材料", problem)

    def test_an_overstated_evidence_strength_is_not_adoption(self) -> None:
        """条目把材料文件声明成 authoritative：材料只证明读到了这些字节，人的原话才是权威。"""
        self.ready()
        items = design_kit.handed_items(self.root, self.feature, ACCESS)
        items[0]["provenance"]["evidence_strength"] = "authoritative"
        design_kit.install_blueprint(self.root, self.feature, ACCESS, items=items)
        self.assertEqual("design_blueprint", self.ok("status")["next"])
        self.assertTrue(any("只能证明 observed" in p for p in self.source_problems()))

    def test_an_older_adopted_version_stays_the_basis(self) -> None:
        """设计开始之后产品需求取得了新版本：不开新轮，蓝图仍采用旧版本，照样可以成文——采不采用新版本由设计判断。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        rounds = len(self.contract()["rounds"])
        self.seed({"RR/prd.md": (PRD + "\n新版补了一句。\n", "RR")})
        self.assertEqual("refresh_round", self.ok("status")["next"])
        self.ok("round")
        self.assertEqual(rounds, len(self.contract()["rounds"]), "设计开始之后材料变了却开了新轮")
        self.assertEqual("ready_to_write", self.ok("status")["state"])
        self.assertEqual([], self.source_problems())


class MaterialChangesBeforeTheDesignOpenANewRound(HandoverCase):
    """材料已确认、设计还没开始：材料再变照常开新一轮重新确认，不当作已经交给设计。"""

    def test_a_new_round_opens(self) -> None:
        self.ready()
        rounds = len(self.contract()["rounds"])
        self.seed({"RR/prd.md": (PRD + "\n补充。\n", "RR")})
        self.assertEqual("run_round", self.ok("status")["next"])
        self.assertTrue(self.ok("round")["created"])
        self.assertEqual(rounds + 1, len(self.contract()["rounds"]))


class TheMaterialFactIsTakenOncePerTimepoint(HandoverCase):
    """同一条命令、同一个时点只取一份材料事实：消费者各拿一份「现在的材料」时，谁也说不清读的是哪一份。
    答复生效的那一刻另有一次刷新：把刚生效的人答导出，下一步读到的就是它（刷新里自己的那次计算不算另取）。"""

    def count_material_reads(self) -> tuple[list, list]:
        builds, refreshes = [], []
        real_build, real_refresh = registry.build, registry.refresh
        inside = []

        def counting_build(feature_root, *rest, **kw):
            if not inside:
                builds.append(feature_root)
            return real_build(feature_root, *rest, **kw)

        def counting_refresh(feature_root):
            refreshes.append(feature_root)
            inside.append(True)
            try:
                return real_refresh(feature_root)
            finally:
                inside.pop()

        registry.build, registry.refresh = counting_build, counting_refresh
        self.addCleanup(setattr, registry, "build", real_build)
        self.addCleanup(setattr, registry, "refresh", real_refresh)
        return builds, refreshes

    def test_status_asks_the_disk_once(self) -> None:
        self.ready()
        builds, refreshes = self.count_material_reads()
        cmd_status(self.feature_root)
        self.assertEqual(1, len(builds), f"status 取了 {len(builds)} 次材料事实——路由、提示与输出该共用一份")
        self.assertEqual([], refreshes, "status 只读，不该刷新清单")

    def decide_now(self, gate: str, chosen: str | None = None, reply: str | None = None,
                   item: str | None = None, ask: str | None = None) -> tuple[dict, int]:
        current = json.loads((self.src / ".ask.json").read_text(encoding="utf-8"))
        if reply is None:
            reply = "2" if chosen in (None, "confirm_scope") else "1"
        args = argparse.Namespace(gate=gate, ask=ask or current["ask_id"],
                                  reply=reply, item=item, replies_file=None)
        return cmd_decide(self.feature_root, args)

    def first_gate_ready(self) -> None:
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        self.ok("status")

    def test_the_first_gate_asks_the_disk_once(self) -> None:
        self.first_gate_ready()
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("material_scope", "confirm_scope")
        self.assertEqual((0, 1, 1), (code, len(builds), len(refreshes)))

    def test_a_rejected_supply_request_asks_the_disk_once(self) -> None:
        """人说「料放进去了」而盘上什么也没有：原地驳回，同样只读一次。"""
        self.first_gate_ready()
        builds, refreshes = self.count_material_reads()
        result, code = self.decide_now("material_scope", MATERIAL_REQUEST_KEYS[0])
        self.assertEqual((2, "rejected", 1, []), (code, result["outcome"], len(builds), refreshes))

    def test_the_design_question_asks_the_disk_once(self) -> None:
        """设计问答记一次原话：材料事实只取一份，答复生效时只刷新一次导出。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        questions = self.root / "questions.json"
        questions.write_text(json.dumps({"items": [{
            "item_id": "Q1", "question": "撤销宽限改多少小时？", "options": ["保持 24 小时", "改 36 小时"],
            "recommend": "改 36 小时", "reason": "阻断当前切片，当前用户有权决定",
            "source_ref": f"doc/features/{self.feature}/AR/story.md"}]}, ensure_ascii=False), encoding="utf-8")
        built = self.ok("status", "--questions-file", str(questions))
        self.assertEqual("await_questions", built["next"])
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now(None, reply="改 36 小时", item="Q1", ask=built["ask"]["ask_id"])
        self.assertEqual((0, 1, 1), (code, len(builds), len(refreshes)))


class TheEffectiveAnswersReachTheDesign(HandoverCase):
    """人答一生效就导出，设计作者、核源与 Story 审查读到的是同一份人答原件；它独立必读，不取决于需求条目写没写它。"""

    SOURCE = """
    const [module, access, root, feature] = process.argv.slice(1);
    const { designSource, requiredAnswers } = await import(module);
    const { sourcesIdentity } = await import(access);
    const ctx = { projectRoot: root, args: { feature }, featureRoot: `${root}/doc/features/${feature}`,
                  flowPath: `${root}/doc/features/${feature}/AR/story-src/story-flow.json` };
    const src = designSource(ctx);
    process.stdout.write(JSON.stringify({ problems: src.problems, answers: requiredAnswers(ctx),
      versions: src.adopted?.own?.versions ?? [], adopted: (src.adopted?.answers ?? []).map(f => f.path),
      // 成文依据的来源身份（currentBasis 的 sources_sha256）由这几部分算
      identity: src.adopted ? sourcesIdentity([...src.adopted.sources, ...(src.adopted.own?.files ?? []),
        ...src.adopted.projectFiles, ...src.adopted.answers]) : null }));
    """

    def design_view(self) -> dict:
        module = (STORY_SCRIPTS / "story" / "design-source.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", self.SOURCE, module, ACCESS.resolve().as_uri(),
                               str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def exported(self) -> dict:
        answers = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "answer")
        return json.loads((self.feature_root / answers["versions"][-1]["original"]["path"]).read_text(encoding="utf-8"))

    def test_a_material_confirmation_reaches_the_design_without_another_refresh(self) -> None:
        """真实 decide 之后不再刷新：导出里有问法与原话；需求条目只写真实需求，人答照样进设计来源。"""
        self.ready()
        status = json.loads(self.flow("status", "--materials").stdout)
        self.assertTrue(status["required_answers"]["in_sync"], status)
        current = self.exported()["records"]
        self.assertEqual(["material_scope"], [d["gate"] for d in current])
        self.assertEqual("2", current[0]["reply"])
        self.assertTrue(all(d["question"] for d in current), "导出的人答没带问法")
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        scope = [i["item_id"] for i in yaml_scope(self.root, self.feature)]
        self.assertEqual(["request-main"], scope, "夹具不该为人答或支撑材料造需求条目")
        view = self.design_view()
        self.assertEqual([], view["problems"])
        self.assertIn(self.answers_rel(), [p.split(f"{self.feature}/", 1)[1] for p in view["adopted"]])

    def test_a_design_answer_is_exported_as_evidence_only(self) -> None:
        """设计问答的原话导出成证据：问题、原话、出处都在；没有「所选 = 人的裁决」，也不带目标/版本。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        questions = self.root / "questions.json"
        questions.write_text(json.dumps({"items": [{
            "item_id": "Q1", "question": "撤销宽限改多少小时？", "options": ["保持 24 小时", "改 36 小时"],
            "recommend": "改 36 小时", "reason": "阻断当前切片，当前用户有权决定",
            "source_ref": f"doc/features/{self.feature}/AR/story.md"}]}, ensure_ascii=False), encoding="utf-8")
        built = self.ok("status", "--questions-file", str(questions))
        decided = self.ok("decide", "--ask", built["ask"]["ask_id"], "--item", "Q1", "--reply", "改 36 小时")
        self.assertTrue(decided.get("success", True), decided)
        [row] = [d for d in self.exported()["records"] if d.get("item_id") == "Q1"]
        self.assertEqual(("撤销宽限改多少小时？", "改 36 小时", "Q1",
                          f"doc/features/{self.feature}/AR/story.md"),
                         (row["question"], row["reply"], row["item_id"], row["source_ref"]))
        self.assertNotIn("chosen", row)
        self.assertFalse({"target_ref", "source_revision", "mapped_by"} & set(row))
        text = (self.feature_root / self.answers_rel()).read_text(encoding="utf-8")
        self.assertIn("只陈列当时的问法、原话与出处", text)
        self.assertNotIn("当前有效", text, "导出给历史答复贴了当前有效的业务标签")
        self.assertNotIn("人的裁决", text)
        self.assertNotIn("所选", text)

    def test_a_support_source_is_adopted_through_its_fact(self) -> None:
        """系统设计只在事实的 provenance 里引用：它的版本进采用集合，不需要伪造约束条目。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        versions = self.design_view()["versions"]
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in versions), versions)
        self.assertTrue(any(re.fullmatch(r"prd(-[0-9a-f]{6})?-v1", v) for v in versions), versions)

    def test_a_support_reference_to_an_unregistered_file_is_named(self) -> None:
        """设计依据引了本需求下没登记的文件：报出位置，不静默省略。"""
        self.ready()
        stray = f"doc/features/{self.feature}/.backups/local/SR/design-v9.md"
        design_kit.install_blueprint(self.root, self.feature, ACCESS, support=[stray])
        self.assertTrue(any("discovery.facts" in p and stray in p for p in self.design_view()["problems"]))

    def test_an_export_failure_keeps_the_answer_and_round_retries(self) -> None:
        """导出写失败：答复已经生效、报清楚怎么重试；重跑 round 只补导出，不开新轮、不重问。"""
        from flow.state import FlowError  # noqa: PLC0415
        from materials import answers  # noqa: PLC0415
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        self.ok("status")
        ask = json.loads((self.src / ".ask.json").read_text(encoding="utf-8"))
        args = argparse.Namespace(gate="material_scope", ask=ask["ask_id"], reply="2",
                                  item=None, replies_file=None)
        real = answers.export

        def broken(*_a, **_k):
            raise OSError("磁盘写满")

        answers.export = broken
        self.addCleanup(setattr, answers, "export", real)
        with self.assertRaises(FlowError) as got:
            cmd_decide(self.feature_root, args)
        self.assertIn("已经记下并生效", str(got.exception))
        self.assertIn("story_flow.py round", str(got.exception))
        answers.export = real
        rounds = len(self.contract()["rounds"])
        self.assertEqual(["material_scope"], [g["gate"] for g in self.contract()["rounds"][-1]["gates"]])
        self.assertFalse(json.loads(self.flow("status", "--materials").stdout)["required_answers"]["in_sync"])
        self.assertFalse(self.ok("round")["created"])
        self.assertEqual(rounds, len(self.contract()["rounds"]))
        self.assertTrue(json.loads(self.flow("status", "--materials").stdout)["required_answers"]["in_sync"])
        self.assertNotEqual("await_gate:material_scope", self.ok("status")["next"], "导出补上之后又问了一遍")

    def test_a_new_answer_moves_the_basis_but_not_the_materials(self) -> None:
        """设计问答里人又答了一次：材料摘要不动（不开补料轮），成文依据的来源身份（currentBasis 的算法）跟着变。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        before = (registry.read(self.feature_root)["digest"], self.design_view()["identity"])
        questions = self.root / "questions.json"
        questions.write_text(json.dumps({"items": [{
            "item_id": "Q1", "question": "撤销宽限改多少小时？", "options": ["保持 24 小时", "改 36 小时"],
            "recommend": "", "reason": "阻断当前切片，当前用户有权决定",
            "source_ref": f"doc/features/{self.feature}/AR/story.md"}]}, ensure_ascii=False), encoding="utf-8")
        built = self.ok("status", "--questions-file", str(questions))
        self.assertTrue(self.ok("decide", "--ask", built["ask"]["ask_id"], "--item", "Q1",
                                "--reply", "改 36 小时").get("success", True))
        after = (registry.read(self.feature_root)["digest"], self.design_view()["identity"])
        self.assertEqual(before[0], after[0], "答一句话把材料摘要顶动了")
        self.assertNotEqual(before[1], after[1], "新的人答没进成文依据的来源身份")

    def test_a_record_without_its_question_is_a_production_defect(self) -> None:
        """本版生产的人答记录缺问法：明确失败，不补默认值。"""
        from materials import answers  # noqa: PLC0415
        self.ready()
        data = self.contract()
        del data["rounds"][-1]["gates"][-1]["question"]
        (self.src / "story-flow.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(answers.AnswerError) as got:
            answers.collect(self.feature_root)
        self.assertIn("缺 question", str(got.exception))


class SourceIndexCase(HandoverCase):
    """把一个蓝图对象放到同根蓝图的位置，经原生读取取它的来源索引（作者、Story 与审查都消费这一份）。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const { sourcesIdentity } = await import(access);
    const own = out.requirements[0] ?? { versions: [], files: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, versions: own.versions,
      projectFiles: out.projectFiles, authorityFiles: out.authorityFiles, authorityIssues: out.authorityIssues, status: out.status,
      identity: sourcesIdentity([...out.sources, ...own.files, ...out.projectFiles, ...out.authorityFiles]) }));
    """

    def collect(self, blueprint: dict) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(blueprint, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def blueprint(self, *, contract_ref: str, conflict_ref: str | None = None) -> dict:
        prov = lambda ref: {"source_kind": "system_design", "source_ref": ref, "observed_at": "2026-10-30T10:00:00+08:00",
                            "evidence_strength": "observed", "extraction_method": "read-source"}
        conflicts = [{"sources": [{"source_ref": conflict_ref}, {"source_ref": contract_ref}], "owner": "需求负责人"}] if conflict_ref else []
        return {"blueprint_id": self.feature, "discovery": {"inputs": {"current_scope_items": []}, "facts": [], "conflicts": conflicts},
                "contracts": [{"contract_id": "c-sign", "provenance": prov(contract_ref)}]}

    def setUp(self) -> None:
        super().setUp()
        self.ready()
        self.base = f"doc/features/{self.feature}"
        self.sr = f"{self.base}/{next(s for s in registry.read(self.feature_root)['sources'] if s['source_id'] == 'local:SR/design.md')['versions'][-1]['original']['path']}"


class TheSupportSourcesAreCollectedNatively(SourceIndexCase):
    """设计依据按原生出处收全：合同对象自身的 provenance 也算；引用带的片段按原生来源解析核；需求目录里没登记的冲突依据报出；
    需求目录以外的工程文件读出摘要进来源身份。"""

    def test_a_contract_level_reference_adopts_its_version(self) -> None:
        got = self.collect(self.blueprint(contract_ref=f"{self.sr}#分工"))
        self.assertEqual([], got["problems"])
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in got["versions"]), got["versions"])

    def test_a_fragment_that_is_not_in_the_file_is_named(self) -> None:
        got = self.collect(self.blueprint(contract_ref=f"{self.sr}#没有这一节"))
        self.assertTrue(any("contracts[c-sign]" in p and "fragment" in p for p in got["problems"]), got["problems"])

    def test_an_unregistered_conflict_source_is_named(self) -> None:
        stray = f"{self.base}/.backups/local/SR/design-v9.md"
        got = self.collect(self.blueprint(contract_ref=self.sr, conflict_ref=stray))
        self.assertTrue(any("冲突依据" in p and stray in p for p in got["problems"]), got["problems"])

    def test_a_project_file_outside_the_requirement_enters_the_identity(self) -> None:
        doc = self.root / "doc" / "architecture" / "签约边界.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# 签约边界\n\n钱包只发起签约。\n", encoding="utf-8")
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-boundary", "provenance": {"source_ref": "doc/architecture/签约边界.md#签约边界"}}]
        first = self.collect(bp)
        self.assertEqual([], first["problems"])
        self.assertEqual(["doc/architecture/签约边界.md"], [f["path"] for f in first["projectFiles"]])
        doc.write_text("# 签约边界\n\n钱包发起并确认签约。\n", encoding="utf-8")
        self.assertNotEqual(first["identity"], self.collect(bp)["identity"], "工程文件变了，来源身份没跟着变")

    def test_a_missing_project_file_is_named(self) -> None:
        """需求目录以外的工程相对路径不在：报出来源缺口，不当作非文件出处静默留下。"""
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-gone", "provenance": {"source_ref": "doc/missing-project-design.md#边界"}}]
        got = self.collect(bp)
        self.assertTrue(any("discovery.facts[f-gone]" in p and "doc/missing-project-design.md" in p and "不在" in p
                            for p in got["problems"]), got["problems"])
        self.assertEqual([], got["projectFiles"])

    def test_a_non_file_provenance_is_left_to_the_native_contract(self) -> None:
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-talk", "provenance": {"source_ref": "interview:2026-10-30-产品"}}]
        got = self.collect(bp)
        self.assertEqual(([], []), (got["problems"], got["projectFiles"]))


class ADesignRecordIsADesignSource(SourceIndexCase):
    """设计实体的出处可以是本蓝图设计目录里的设计记录：读出原字节进来源身份（`design_file`），不算采用了本需求的材料；
    事实来源、需求目录里别处没登记的文件、只有设计自引而没有材料采用，都照旧不放行，来源类别换名不改变结果。"""

    RECORD = "blueprint/local-design.md"

    def setUp(self) -> None:
        super().setUp()
        self.record = self.feature_root / self.RECORD
        self.record.parent.mkdir(parents=True, exist_ok=True)
        self.record.write_text("# 刷新职责\n\n返回首页时由本部件刷新余额，刷新结果只在本部件内使用。\n", encoding="utf-8")
        self.addCleanup(self.record.unlink, missing_ok=True)

    def with_node(self, ref: str, *, kind: str = "component_design", contract_ref: str | None = None) -> dict:
        bp = self.blueprint(contract_ref=contract_ref or self.sr)
        bp["design_views"] = [{"view_id": "logical", "nodes": [{"node_id": "wallet-balance", "provenance": {
            "source_kind": kind, "source_ref": ref, "observed_at": "2026-10-30T10:00:00+08:00",
            "evidence_strength": "observed", "extraction_method": "local-design"}}]}]
        return bp

    def test_a_node_citing_the_design_record_reads_it_as_design(self) -> None:
        control = self.collect(self.blueprint(contract_ref=self.sr))
        got = self.collect(self.with_node(f"{self.base}/{self.RECORD}#刷新职责"))
        self.assertEqual([], got["problems"])
        self.assertEqual([(f"{self.base}/{self.RECORD}", "design_file")], [(f["path"], f["role"]) for f in got["projectFiles"]])
        self.assertEqual(control["versions"], got["versions"], "设计记录被算成了本需求的材料版本")
        self.record.write_text("# 刷新职责\n\n返回首页与下拉时由本部件刷新余额。\n", encoding="utf-8")
        self.assertNotEqual(got["identity"], self.collect(self.with_node(f"{self.base}/{self.RECORD}#刷新职责"))["identity"],
                            "设计记录改了，来源身份没跟着变")

    def test_the_source_kind_name_does_not_decide(self) -> None:
        ref = f"{self.base}/{self.RECORD}"
        self.assertEqual(self.collect(self.with_node(ref))["projectFiles"],
                         self.collect(self.with_node(ref, kind="product_requirement"))["projectFiles"])
        stray = f"{self.base}/inbox/草稿.md"
        (self.feature_root / "inbox").mkdir(exist_ok=True)
        (self.feature_root / "inbox" / "草稿.md").write_text("# 草稿\n", encoding="utf-8")
        self.addCleanup((self.feature_root / "inbox" / "草稿.md").unlink, missing_ok=True)
        for kind in ("component_design", "product_requirement"):
            with self.subTest(kind=kind):
                got = self.collect(self.with_node(stray, kind=kind))
                self.assertTrue(any(stray in p and "不是需求" in p for p in got["problems"]), got["problems"])

    def test_a_missing_record_and_a_bad_fragment_are_named(self) -> None:
        missing = f"{self.base}/blueprint/没有这份.md"
        got = self.collect(self.with_node(missing))
        self.assertTrue(any("设计记录" in p and missing in p for p in got["problems"]), got["problems"])
        got = self.collect(self.with_node(f"{self.base}/{self.RECORD}#没有这一节"))
        self.assertTrue(any("design_views[logical].nodes[wallet-balance]" in p and "fragment" in p for p in got["problems"]),
                        got["problems"])

    def test_a_fact_citing_the_design_record_is_still_a_material_reference(self) -> None:
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-local", "provenance": {"source_ref": f"{self.base}/{self.RECORD}"}}]
        got = self.collect(bp)
        self.assertTrue(any("discovery.facts[f-local]" in p and "不是需求" in p for p in got["problems"]), got["problems"])

    def test_design_records_alone_do_not_adopt_the_requirement(self) -> None:
        ref = f"{self.base}/{self.RECORD}"
        got = self.collect(self.with_node(ref, contract_ref=ref))
        self.assertEqual([], got["problems"])
        self.assertEqual([], got["versions"], "只有设计记录，却算出了采用的材料版本")


class ContractSectionsReadTheirAuthority(SourceIndexCase):
    """契约段的 source_ref 是设计转写出的接口契约（JSON Pointer 指到段），放在需求自己的 blueprint/ 下：
    指针与内容由原生契约校验核，不按材料登记、不按文字片段核；依据引用与某段完全相同就是这一段。坏指针、内容不符照原生报，
    同文件里原生没核过的位置单独报出；权威文件的字节进来源身份。"""

    AUTHORITY = "operations:\n  sign:\n    operation:\n      operation_id: sign\n      direction: outbound\n      version: v1\n"

    def setUp(self) -> None:
        super().setUp()
        self.file = f"{self.base}/blueprint/contracts/sign.yaml"
        self.authority = self.root / Path(*self.file.split("/"))
        self.authority.parent.mkdir(parents=True, exist_ok=True)
        self.authority.write_bytes(self.AUTHORITY.encode("utf-8"))

    def with_contract(self, pointer: str, *, version: str = "v1", fact_ref: str | None = None) -> dict:
        bp = self.blueprint(contract_ref=f"{self.sr}#分工")
        bp["contracts"][0]["operation"] = {"operation_id": "sign", "direction": "outbound", "version": version,
                                           "source_ref": f"{self.file}#{pointer}", "verification_refs": ["ut:sign"]}
        if fact_ref:
            bp["discovery"]["facts"] = [{"fact_id": "f-op", "provenance": {"source_kind": "system_design", "source_ref": fact_ref}}]
        return bp

    def test_a_section_pointer_and_an_equal_design_reference_are_the_authority(self) -> None:
        ref = f"{self.file}#/operations/sign/operation"
        got = self.collect(self.with_contract("/operations/sign/operation", fact_ref=ref))
        self.assertEqual(([], "ok", []), (got["problems"], got["status"], got["authorityIssues"]))
        [row] = got["authorityFiles"]
        self.assertEqual((self.file, f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}", "contract_authority"),
                         (row["path"], row["sha256"], row["role"]))
        self.assertEqual({"contracts[c-sign].operation", "discovery.facts[f-op]"}, {r["where"] for r in row["refs"]})
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in got["versions"]), "合同自身的原始出处没再采用")

    def test_a_pointer_the_authority_does_not_have_is_the_native_finding(self) -> None:
        got = self.collect(self.with_contract("/operations/refund/operation"))
        self.assertEqual("incomplete", got["status"])
        self.assertEqual(["blueprint_contract_authority_source_invalid"], [i["id"] for i in got["authorityIssues"]])
        self.assertEqual([None], [f["sha256"] for f in got["authorityFiles"]], "坏的契约权威不能给出可复用的摘要")
        self.assertTrue(any("契约权威" in p and "refund" in p for p in got["problems"]), got["problems"])

    def test_content_that_differs_from_its_authority_is_the_native_finding(self) -> None:
        got = self.collect(self.with_contract("/operations/sign/operation", version="v2"))
        self.assertEqual(["blueprint_contract_authority_mismatch"], [i["id"] for i in got["authorityIssues"]])

    def test_another_place_in_the_authority_file_is_named(self) -> None:
        got = self.collect(self.with_contract("/operations/sign/operation", fact_ref=f"{self.file}#/operations"))
        self.assertEqual("ok", got["status"])
        [problem] = got["problems"]
        self.assertIn("discovery.facts[f-op]", problem)
        self.assertIn("原生核过", problem)

    def test_the_authority_bytes_enter_the_identity(self) -> None:
        bp = self.with_contract("/operations/sign/operation")
        first = self.collect(bp)
        self.authority.write_bytes(("# 签约接口\n" + self.AUTHORITY).encode("utf-8"))
        again = self.collect(bp)
        self.assertEqual(([], []), (first["problems"], again["problems"]))
        self.assertNotEqual(first["identity"], again["identity"], "权威文件换了字节，来源身份没跟着变")

    def test_an_equivalent_path_the_native_loader_accepts_is_the_same_authority(self) -> None:
        """原生 loader 接受 `contracts/../contracts/sign.yaml` 这样的根内等价写法：它与标准写法是同一份权威文件、同一摘要、同一来源身份。"""
        pointer = "/operations/sign/operation"
        standard = self.collect(self.with_contract(pointer))
        bp = self.with_contract(pointer)
        bp["contracts"][0]["operation"]["source_ref"] = f"{self.base}/blueprint/contracts/../contracts/sign.yaml#{pointer}"
        equivalent = self.collect(bp)
        self.assertEqual(([], []), (equivalent["problems"], equivalent["authorityIssues"]))
        self.assertEqual([(self.file, f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}")],
                         [(f["path"], f["sha256"]) for f in equivalent["authorityFiles"]], "等价写法的权威文件没进来源集合")
        self.assertEqual(standard["identity"], equivalent["identity"])

    def test_an_authority_outside_the_project_stays_the_native_finding(self) -> None:
        bp = self.with_contract("/operations/sign/operation")
        bp["contracts"][0]["operation"]["source_ref"] = "../outside/sign.yaml#/operations/sign/operation"
        got = self.collect(bp)
        self.assertEqual("incomplete", got["status"])
        self.assertEqual(["blueprint_contract_authority_source_invalid"], [i["id"] for i in got["authorityIssues"]])
        self.assertEqual([], got["authorityFiles"])

    def test_the_review_object_lists_the_authority_reached_by_an_equivalent_path(self) -> None:
        """独审对象是来源集合的直接读者：等价写法引到的权威文件照样进必读材料。"""
        probe = """
        const [access, review, root, feature, BLUEPRINT] = process.argv.slice(1);
        const fs = await import('node:fs');
        const path = await import('node:path');
        const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
        fs.writeFileSync(file, BLUEPRINT);
        const { reviewObject } = await import(review);
        const object = reviewObject(root, feature, { withTask: false });
        fs.rmSync(file);
        process.stdout.write(JSON.stringify(object.rows.map(r => r.path)));
        """
        bp = self.with_contract("/operations/sign/operation")
        bp["contracts"][0]["operation"]["source_ref"] = f"{self.base}/blueprint/contracts/../contracts/sign.yaml#/operations/sign/operation"
        review = DEV_EXT / "base" / "skills" / "story" / "scripts" / "core" / "story" / "review-object.mjs"
        manifest = self.root / "doc" / "extensions" / "manifest.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("provides:\n  knowledge: []\n", encoding="utf-8")   # 审查对象要列激活清单；本例不涉知识
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, ACCESS.resolve().as_uri(), review.resolve().as_uri(),
                               str(self.root), self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(self.file, json.loads(proc.stdout), "独审必读材料里没有等价写法引到的权威文件")

    def test_a_read_after_an_edit_in_the_same_process_sees_the_new_bytes(self) -> None:
        """同一进程里先读、改了权威文件再读：后一次按此刻的字节，不沿用前一次的结果。"""
        probe = """
        const [access, root, feature, file, bp, extra] = process.argv.slice(1);
        const fs = await import('node:fs');
        const path = await import('node:path');
        const canonical = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
        fs.writeFileSync(canonical, bp);
        const { readBlueprint } = await import(access);
        const sha = () => readBlueprint(root, feature, 'draft', feature).source_index.authorityFiles.map(f => f.sha256);
        const before = sha();
        fs.writeFileSync(path.join(root, ...file.split('/')), extra + fs.readFileSync(path.join(root, ...file.split('/')), 'utf8'));
        process.stdout.write(JSON.stringify({ before, after: sha() }));
        """
        bp = json.dumps(self.with_contract("/operations/sign/operation"), ensure_ascii=False)
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, ACCESS.resolve().as_uri(), str(self.root), self.feature,
                               self.file, bp, "# 签约接口\n"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual([f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}"], got["before"])
        self.assertEqual([f"sha256:{hashlib.sha256(('# 签约接口' + chr(10) + self.AUTHORITY).encode('utf-8')).hexdigest()}"], got["after"])


class ACitedCurrentDraftStaysAtItsVersion(HandoverCase):
    """作者按当前阅读稿 `RR/prd.md#节` 写需求条目：补出的引用指当时那一版聚合稿的稳定副本与它固定的组成；
    之后一份原件换版，当前稿换成新的一版，旧条目与旧支撑引用仍读旧正文、展开旧组成，新条目指新的一版。
    设计引用当前位置不算依据，报出它此刻对应的稳定文件。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const own = out.requirements[0] ?? { versions: [], files: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, versions: own.versions, files: own.files.map(f => f.path) }));
    """

    LIMIT = "# 限额\n\n## 单笔\n\n单笔上限 {} 元。\n"

    def collect(self, items: list[dict], support: str | None = None) -> dict:
        prov = {"source_kind": "requirement_reading", "source_ref": support, "observed_at": "2026-11-02T10:00:00+08:00",
                "evidence_strength": "observed", "extraction_method": "read-source"}
        bp = {"blueprint_id": self.feature, "discovery": {"inputs": {"current_scope_items": items}, "conflicts": [],
                                                          "facts": [{"fact_id": "f-limit", "provenance": prov}] if support else []}}
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def current(self) -> dict:
        """材料索引里当前稿 `RR/prd.md` 那一行（会换版的当前位置）。"""
        return next(r for r in registry.read(self.feature_root)["files"] if r["path"] == "RR/prd.md")

    def test_the_cited_version_and_its_components_survive_a_new_version(self) -> None:
        self.ready()
        self.seed({"RR/限额.md": (self.LIMIT.format(500), "RR")})
        [old] = self.scoped([item("RR/prd.md#单笔")])["current_scope_items"]
        alias = self.current()
        stable = alias["reference"]["path"]
        self.assertEqual(f"doc/features/{FEATURE}/{stable}#单笔", old["source_ref"], "条目指了会换版的当前稿")
        self.assertEqual(f"draft:RR/prd.md@v{alias['version']}", old["provenance"]["source_revision"])
        self.assertIn("单笔上限 500 元", (self.feature_root / stable).read_text(encoding="utf-8"))
        support = f"doc/features/{FEATURE}/{stable}#背景"
        first = self.collect([old], support)
        self.assertEqual([], first["problems"])
        self.assertIn("限额-v1", first["versions"], "聚合稿的组成没展开")

        self.seed({"RR/限额.md": (self.LIMIT.format(800), "RR")})
        self.assertNotEqual(stable, self.current()["reference"]["path"], "原件换版后当前稿没换成新的一版")
        again = self.collect([old], support)
        self.assertEqual([], again["problems"], "旧引用在材料换版后读不了")
        self.assertEqual(first["versions"], again["versions"], "旧引用展开到了新的组成")
        self.assertIn("单笔上限 500 元", (self.feature_root / stable).read_text(encoding="utf-8"), "旧稳定副本被改了")
        [new] = self.scoped([item("RR/prd.md#单笔")])["current_scope_items"]
        self.assertNotEqual(old["source_ref"], new["source_ref"])
        latest = self.collect([new])
        self.assertIn("限额-v2", latest["versions"])
        self.assertNotIn("限额-v1", latest["versions"])

    def test_a_design_reference_to_the_current_draft_names_its_stable_file(self) -> None:
        self.ready()
        [scoped] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        got = self.collect([scoped], f"doc/features/{FEATURE}/RR/prd.md#背景")
        [problem] = got["problems"]
        self.assertIn("f-limit", problem)
        self.assertIn(self.current()["reference"]["path"], problem, "没指出当前位置对应的稳定文件")


class DirectOriginalsAreCitedAtTheirVersions(HandoverCase):
    """直接写在 RR/SR/AR 的原文：同一批里互相链接时，阅读稿链对方这一批的版本，与先后无关；被链的那份换版，旧版仍读旧正文。
    设计引用的图按用途归集：采用的图进采用，冲突依据直接引或经它的文稿链到的图进冲突核源，不凭空变成采用。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const own = out.requirements[0] ?? { files: [], conflictFiles: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, files: own.files.map(f => f.path),
      conflictFiles: own.conflictFiles.map(f => f.path) }));
    """

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        ensure_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / self.feature
        (self.feature_root / "inbox").mkdir(parents=True)
        self.src = self.feature_root / "AR" / "story-src"
        self.base = f"doc/features/{self.feature}"

    def give(self, files: dict[str, str | bytes]) -> None:
        """直接写进需求目录（不经收件箱），再经真实导入器登记。"""
        for rel, body in files.items():
            (self.feature_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.feature_root / rel).write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        importer.cmd_import(self.feature_root, self.root)

    def latest(self, rel: str) -> dict:
        return next(s for s in registry.read(self.feature_root)["sources"] if s["source_id"] == f"direct:{rel}")["versions"][-1]

    def collect(self, items: list[dict], support: list[str] = (), conflicts: list[str] = ()) -> dict:
        prov = lambda ref: {"source_kind": "requirement_reading", "source_ref": ref, "observed_at": "2026-11-02T10:00:00+08:00",  # noqa: E731
                            "evidence_strength": "observed", "extraction_method": "read-source"}
        bp = {"blueprint_id": self.feature, "discovery": {
            "inputs": {"current_scope_items": items},
            "facts": [{"fact_id": f"f-{i}", "provenance": prov(ref)} for i, ref in enumerate(support)],
            "conflicts": [{"sources": [{"source_ref": ref} for ref in conflicts], "owner": "需求负责人"}] if conflicts else []}}
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_link_between_direct_originals_reads_the_linked_version(self) -> None:
        self.give({"RR/prd.md": "# 产品需求\n\n## 背景\n\n分工见[系统设计](../SR/design.md#分工)。\n",
                   "SR/design.md": "# 系统设计\n\n## 分工\n\n钱包发起签约。\n"})
        [old] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        first = self.collect([old])
        self.assertEqual([], first["problems"], "同一批登记的直接原文链到了会换版的当前位置")
        sr_v1 = f"{self.base}/{self.latest('SR/design.md')['readable']['path']}"
        self.assertIn(sr_v1, first["files"], "链到的系统设计没随采用展开")
        self.assertIn("钱包发起签约", (self.root / sr_v1).read_text(encoding="utf-8"))

        self.give({"SR/design.md": "# 系统设计\n\n## 分工\n\n钱包发起并确认签约。\n"})
        sr_v2 = f"{self.base}/{self.latest('SR/design.md')['readable']['path']}"
        self.assertNotEqual(sr_v1, sr_v2)
        again = self.collect([old])
        self.assertEqual([], again["problems"])
        self.assertIn(sr_v1, again["files"], "旧引用展开到了新版本")
        self.assertNotIn(sr_v2, again["files"])
        self.assertIn("钱包发起签约", (self.root / sr_v1).read_text(encoding="utf-8"), "旧版正文被改了")
        [new] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        self.assertNotEqual(old["source_ref"], new["source_ref"], "被链的原文换版，链它的阅读稿没出新版本")
        self.assertIn(sr_v2, self.collect([new])["files"])

    READERS = """
    const [core, root, feature] = process.argv.slice(1);
    const { createContext } = await import(new URL('context.mjs', core));
    const { adoptedUpstreamTexts, upstreamDocs } = await import(new URL('sources.mjs', core));
    const ctx = createContext({ feature, projectRoot: root });
    process.stdout.write(JSON.stringify({ texts: adoptedUpstreamTexts(ctx), docs: upstreamDocs(ctx).map(([, , rel]) => rel) }));
    """

    def test_two_direct_originals_of_the_same_name_stay_apart(self) -> None:
        """SR/design.md 与 AR/design.md 同一批直接给出、主名相同：各是各的来源版本；设计只采用开发需求时，
        Story 读上游正文与上游图的读者都不把系统设计算作采用。"""
        self.give({"SR/design.md": "# 系统设计\n\n## 分工\n\n云侧负责扣款。\n",
                   "AR/design.md": "# 开发需求\n\n## 范围\n\n钱包发起签约。\n"})
        sr, ar = self.latest("SR/design.md"), self.latest("AR/design.md")
        self.assertNotEqual(sr["dir"], ar["dir"], "两份直接原文的版本身份相同")
        [scoped] = self.scoped([item("AR/design.md#范围")])["current_scope_items"]
        design_kit.install_blueprint(self.root, self.feature, ACCESS, items=[scoped], support=[])
        proc = subprocess.run(["node", "--input-type=module", "-e", self.READERS,
                               (STORY_SCRIPTS / "story").resolve().as_uri() + "/", str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertTrue(any("钱包发起签约" in text for text in got["texts"]), "采用的开发需求没交给上游正文的读者")
        self.assertFalse(any("云侧负责扣款" in text for text in got["texts"]), "没被采用的系统设计算成了采用的上游正文")
        self.assertEqual([], got["docs"], "没被采用的系统设计进了上游图的读者")

    def test_pictures_follow_the_use_they_were_cited_for(self) -> None:
        picture = self.feature_root / "assets" / "ux" / "界面.png"
        picture.parent.mkdir(parents=True, exist_ok=True)
        picture.write_bytes(b"\x89PNG\r\n\x1a\nui")
        self.give({"RR/prd.md": "# 产品需求\n\n## 背景\n\n签约。\n",
                   "AR/design.md": "# 开发需求\n\n## 界面\n\n![界面](../assets/ux/界面.png)\n"})
        [scoped] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        shown = f"{self.base}/{self.latest('AR/design.md')['images'][0]['path']}"
        reading = f"{self.base}/{self.latest('AR/design.md')['readable']['path']}"
        direct = self.collect([scoped], conflicts=[shown])
        self.assertEqual([], direct["problems"])
        self.assertIn(shown, direct["conflictFiles"], "冲突依据直接引的图没进冲突核源")
        self.assertNotIn(shown, direct["files"], "只作冲突依据的图变成了采用")
        linked = self.collect([scoped], conflicts=[reading])
        self.assertEqual([], linked["problems"])
        self.assertTrue({reading, shown} <= set(linked["conflictFiles"]), "冲突文稿链到的图没随冲突核源交出")
        self.assertNotIn(shown, linked["files"])
        used = self.collect([scoped], support=[shown])
        self.assertIn(shown, used["files"], "设计引用的图没进采用")
        self.assertNotIn(reading, used["files"], "引了文稿里的一张图，把整份文稿都算成了采用")


def yaml_scope(root: Path, feature: str) -> list[dict]:
    """蓝图里的原生需求条目（夹具写成单行 JSON）。"""
    text = (root / "doc" / "features" / feature / "blueprint" / "component-blueprint.yaml").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.strip().startswith("current_scope_items:"))
    return json.loads(line.split(":", 1)[1])


class RegistrationRunsTheRealChecker(HandoverCase):
    """成文态登记的结论，就是 `story-build` 这一次的结论：跑不起来与没通过必须分得开。"""

    def test_the_checker_runs_and_its_own_finding_is_the_verdict(self) -> None:
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        (self.feature_root / "AR" / "story.md").write_text("# 随手写的一行\n", encoding="utf-8")
        proc = self.flow("story")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertNotIn("Cannot find module", error, "node 找不到 story-build.mjs——公共 CLI 的定位错了")
        self.assertIn("[story-build]", error, "登记没把 story-build 的结论带出来，只报了自己跑不通")
        self.assertEqual("gathering", self.contract()["status"], "检查没通过却记了成文态")


if __name__ == "__main__":
    unittest.main()
