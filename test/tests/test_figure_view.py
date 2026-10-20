"""story 里由脚本管理的两类图：正式 Mermaid（`.mmd` 是唯一真源）与写作设计选中的补充阅读图（阅读槽里显隐）。

锁的是视图合同：正式图源的建立、按源重铺与坏块零写入；阅读槽按写作设计的选择、放置与顺序同步，槽外正文一个字节不动；
明确不采用时零 SVG 也算完成，缺选择不算；验收请求绑定候选的全部依据、放置小节、SVG、资源与渲染图，任一变化让这一张过期，
只显隐与无关章节变化不让它过期；正式入口（story-build 其它命令、阶段钩子、预检、story_flow）先回到正式形态，结束或失败后恢复可用的阅读图。
图对不对、有没有增益不在这里——那是独立审查的事。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT, link_harness_yaml

CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"
BUILD = CORE / "story-build.mjs"
CHECK = CORE / "story" / "figure-check.py"
FLOW = CORE / "story_flow.py"
FEATURE = "FIG90001"
FLOW_SRC = "flowchart TD\n  A[提交] --> B{受理?}\n  B -->|是| C[等回执]\n  B -->|否| D[提示重试]\n"
PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
SUBMIT = ("### 提交与回执\n\n看这张图要看出受理失败去哪。\n\n```mermaid\n" + FLOW_SRC + "```\n\n图后：回执超时由服务端重试。\n\n"
          "| 情形 | 去向 |\n|---|---|\n| 受理失败 | 提示重试 |\n\n")
REST = "### 取消\n\n取消后退款。\n\n## 异常与恢复\n\n### 共同恢复规则\n\n本地记录清掉后按远端事实恢复。\n"
STORY = "# FIG90001 甲需求\n\n## 业务流程\n\n" + SUBMIT + REST
SKELETON = ("# 写作设计\n\n## 阅读主线\n\n先讲提交，再讲恢复。\n\n## 骨架\n\n"
            "### 05-flow\n\n#### 提交与回执\n- 答：受理失败去哪\n\n#### 取消\n- 答：取消后怎样\n\n"
            "### 07-exceptions\n\n#### 共同恢复规则\n- 答：清掉之后靠什么恢复\n\n## 阅读图选择\n\n")
BASIS = ("AR/story.md > 业务流程 > 提交与回执", "AR/story.md > 异常与恢复 > 共同恢复规则")
NONE = "不采用：正文的流程图与表已经讲清，没有要另画的关系\n"


def candidate(cid: str = "recovery", place: str = "05-flow > 提交与回执", basis: tuple = BASIS,
              question: str = "受理失败之后靠什么恢复") -> str:
    return (f"### {cid}\n- 阅读问题：{question}\n- 增益：把分散在两章的失败与恢复放进一张图\n- 放置：{place}\n"
            + "".join(f"- 依据：{b}\n" for b in basis) + "\n")


def svg(extra: str = "") -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><text x="10" y="20">提交</text>{extra}</svg>\n'


class FigureViewCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        self.fr = self.root / "doc" / "features" / FEATURE
        (self.fr / "AR" / "story-src").mkdir(parents=True)
        self.story = self.fr / "AR" / "story.md"
        self.story.write_text(STORY, encoding="utf-8")
        self.design(candidate())
        link_harness_yaml(self.root)

    def design(self, reading: str, skeleton: str = SKELETON) -> None:
        (self.fr / "AR" / "story-src" / "story-template.md").write_text(skeleton + reading, encoding="utf-8")

    def view(self, mode: str, *extra: str) -> subprocess.CompletedProcess:
        return self.build("view", "--mode", mode, *extra)

    def build(self, command: str, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(BUILD), command, "--feature", FEATURE, "--project-root", str(self.root), *extra],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)

    def ok(self, mode: str, *extra: str) -> subprocess.CompletedProcess:
        proc = self.view(mode, *extra)
        self.assertEqual(0, proc.returncode, proc.stderr + proc.stdout)
        return proc

    def text(self) -> str:
        return self.story.read_text(encoding="utf-8")

    def edit(self, old: str, new: str) -> None:
        text = self.text()
        self.assertIn(old, text)
        self.story.write_text(text.replace(old, new), encoding="utf-8")

    def slot(self, cid: str = "recovery") -> str:
        text = self.text()
        begin, end = f"<!-- story-reading:{cid}:begin -->", f"<!-- story-reading:{cid}:end -->"
        return text[text.index(begin) + len(begin):text.index(end)].strip()

    def fig_id(self) -> str:
        return next(self.fr.glob("AR/story-src/figures/*.mmd")).stem

    def src(self, fid: str) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd"

    def reading(self, cid: str = "recovery") -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{cid}.reading"

    def work(self) -> dict:
        return json.loads(self.view("status").stdout)

    def item(self, cid: str = "recovery") -> dict:
        return next(i for i in self.work()["items"] if i["id"] == cid)

    def state(self, cid: str = "recovery") -> str:
        return self.item(cid)["state"]

    def put_svg(self, cid: str = "recovery", text: str | None = None) -> Path:
        path = self.fr / "AR" / "figures" / f"{cid}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else svg(), encoding="utf-8")
        return path

    def make_ready(self, cid: str = "recovery", verdict: str = "PASS", **report: object) -> dict:
        """走完验收：存一张渲染图、生成请求、放一份独立审查报告（替身，只为绑定与结论自洽）。"""
        shot = self.root / "shot.png"
        shot.write_bytes(PNG + b"render")
        self.ok("review-request", "--id", cid, "--render", str(shot))
        request = json.loads((self.reading(cid) / "request.json").read_text(encoding="utf-8"))
        body = {"request_id": request["request_id"], "executor": "subagent-7",
                "checks": [{"id": c, "verdict": verdict, "evidence": f"核过 {c}"} for c in request["checks"]],
                "blocking_findings": [], "advisories": [], "unreviewed": [], **report}
        (self.reading(cid) / "report.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return request

    def ready(self, cid: str = "recovery") -> None:
        self.ok("prepare")
        self.put_svg(cid)
        self.make_ready(cid)
        self.assertEqual("ready", self.state(cid))


class ZeroOrManyReadingFigures(FigureViewCase):
    def test_a_clear_no_with_mermaid_is_complete_and_the_views_change_nothing(self) -> None:
        self.design(NONE)
        self.ok("prepare")
        self.assertTrue(self.src(self.fig_id()).is_file(), "正式图没有建源")
        self.assertEqual({"applicable": False, "complete": True, "items": [], "unmanaged": [], "problems": [], "next": None},
                         self.work())
        before = self.story.read_bytes()
        for mode in ("svg", "mermaid"):
            self.ok(mode)
        self.assertIn("不需要 SVG", self.ok("toggle").stdout)
        self.assertEqual(before, self.story.read_bytes(), "不采用时视图改了 story")
        self.assertNotIn("story-reading", self.text())
        self.assertFalse((self.fr / "AR" / "figures").exists())

    def test_a_missing_or_open_choice_is_not_complete(self) -> None:
        cases = {
            "缺这一节": (SKELETON.replace("## 阅读图选择\n\n", ""), "", "阅读图选择"),
            "仍是占位": (SKELETON, "{{要不要阅读图}}\n", "还没有结论"),
            "两个结论": (SKELETON, NONE + candidate(), "两个结论只能有一个"),
            "不采用没理由": (SKELETON, "不采用：\n", "没写理由"),
        }
        for name, (skeleton, reading, needle) in cases.items():
            with self.subTest(name):
                self.design(reading, skeleton)
                work = self.work()
                self.assertEqual((True, False), (work["applicable"], work["complete"]), work)
                self.assertIn(needle, "；".join(work["problems"]))
                self.assertTrue(work["next"])

    def test_one_figure_from_prose_table_and_another_chapter_shows_in_its_slot(self) -> None:
        self.ready()
        formal = self.story.read_bytes()
        self.assertEqual("", self.slot(), "prepare 建的槽不是空的")
        self.ok("svg")
        self.assertEqual("![受理失败之后靠什么恢复](figures/recovery.svg)", self.slot())
        text = self.text()
        self.assertIn("```mermaid", text, "显示阅读图时正式 Mermaid 不见了")
        self.assertLess(text.index("| 受理失败 |"), text.index("<!-- story-reading:recovery:begin -->"))
        self.assertLess(text.index("<!-- story-reading:recovery:end -->"), text.index("### 取消"), "槽不在放置小节末尾")
        once = self.story.read_bytes()
        self.ok("svg")
        self.assertEqual(once, self.story.read_bytes(), "同一形态重跑不是零改写")
        self.ok("mermaid")
        self.assertEqual(formal, self.story.read_bytes(), "显示再隐藏没有精确还原")
        self.ok("toggle")
        self.assertTrue(self.slot())
        self.ok("toggle")
        self.assertEqual(formal, self.story.read_bytes())

    def test_the_alt_text_is_escaped(self) -> None:
        self.design(candidate(question="失败[两次]之后*谁*恢复"))
        self.ready()
        self.ok("svg")
        self.assertEqual(r"![失败\[两次\]之后\*谁\*恢复](figures/recovery.svg)", self.slot())
        self.assertEqual("ready", self.state())

    def test_two_figures_at_one_place_follow_the_design_order(self) -> None:
        self.design(candidate("b-second") + candidate("a-first"))
        self.ok("prepare")
        text = self.text()
        self.assertLess(text.index("story-reading:b-second:begin"), text.index("story-reading:a-first:begin"))
        once = self.story.read_bytes()
        self.ok("prepare")
        self.assertEqual(once, self.story.read_bytes(), "重跑 prepare 又改了 story")
        self.assertEqual(["b-second", "a-first"], [i["id"] for i in self.work()["items"]])

    def test_bad_ids_and_places_are_listed_at_once_and_nothing_is_written(self) -> None:
        self.design(candidate("bad.id") + candidate("x", place="05-flow > 不存在") + candidate("y", place="99-nope > 提交与回执"))
        before = self.story.read_bytes()
        proc = self.view("prepare")
        self.assertEqual(1, proc.returncode, proc.stdout)
        for needle in ("「### bad.id」ID 只能用", "放置「05-flow > 不存在」", "放置「99-nope > 提交与回执」"):
            self.assertIn(needle, proc.stderr)
        self.assertEqual(before, self.story.read_bytes())
        self.design(candidate(place="05-flow > 取消"))
        self.edit("### 取消\n\n取消后退款。\n", "### 取消\n\n取消后退款。\n\n### 取消\n\n又一节。\n")
        before = self.story.read_bytes()
        proc = self.view("prepare")
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("2 处同名", proc.stderr)
        self.assertEqual(before, self.story.read_bytes(), "放置有歧义也写了")


class EvidenceFollowsWhatTheFigureSays(FigureViewCase):
    def test_the_request_binds_every_basis_the_place_and_the_render(self) -> None:
        self.ready()
        request = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))
        self.assertEqual((2, "story-reading-review/2"), (request["version"], request["method"]))
        self.assertEqual(["semantic_fidelity", "reading_gain", "visual_readability", "placement"], request["checks"])
        inputs = request["inputs"]
        self.assertEqual([("AR/story.md", "业务流程 › 提交与回执"), ("AR/story.md", "异常与恢复 › 共同恢复规则")],
                         [(b["path"], b["section"]) for b in inputs["basis"]])
        self.assertEqual(("业务流程 › 提交与回执", ["recovery"]), (inputs["context"]["section"], inputs["context"]["order"]))
        self.assertEqual("受理失败之后靠什么恢复", inputs["selection"]["question"])
        self.assertEqual("AR/story-src/figures/recovery.reading/render.png", inputs["render"]["path"])
        out = self.ok("review-request", "--id", "recovery").stdout
        self.assertIn(f"工程根：{self.root}", out)
        self.assertIn(f"doc/features/{FEATURE}/AR/story-src/figures/recovery.reading/report.json", out)
        self.assertIn("「业务流程 › 提交与回执」", out)
        self.assertIn("本地记录清掉后按远端事实恢复。", out, "任务里没有另一章依据的原文")
        self.assertIn("reading_gain", out)
        command = next(line for line in out.splitlines() if "review-check" in line)
        self.assertIn(f"--feature '{FEATURE}' --project-root '{self.root}'", command, "核对命令照抄跑不起来")

    def test_each_input_change_makes_it_stale_and_display_or_unrelated_edits_do_not(self) -> None:
        self.ready()
        svg_path = self.fr / "AR" / "figures" / "recovery.svg"
        render = self.reading() / "render.png"
        story = self.story.read_bytes()
        changes = {
            "SVG": (lambda: self.put_svg(text=svg("<text>多一句</text>")), lambda: self.put_svg()),
            "渲染图": (lambda: render.write_bytes(PNG + b"other"), lambda: render.write_bytes(PNG + b"render")),
            "另一章依据的正文": (lambda: self.edit("按远端事实恢复。", "按远端事实与客服记录恢复。"), lambda: self.story.write_bytes(story)),
            "放置小节的正文": (lambda: self.edit("图后：", "图后（改了）："), lambda: self.story.write_bytes(story)),
            "阅读问题": (lambda: self.design(candidate(question="谁负责恢复")), lambda: self.design(candidate())),
            "依据": (lambda: self.design(candidate(basis=BASIS[:1])), lambda: self.design(candidate())),
        }
        for name, (change, undo) in changes.items():
            with self.subTest(name):
                change()
                self.assertEqual("stale", self.state(), f"{name}变了，旧验收照样成立")
                undo()
                self.assertEqual("ready", self.state())
        self.assertEqual(svg_path.read_text(encoding="utf-8"), svg())
        self.edit("取消后退款。", "取消后原路退款。")
        self.assertEqual("ready", self.state(), "无关章节的改动让阅读图过期")
        self.ok("svg")
        self.assertEqual("ready", self.state(), "显示阅读图改了请求身份")
        self.ok("mermaid")
        self.assertEqual("ready", self.state())

    def test_a_source_edit_not_yet_laid_into_the_story_is_not_ready(self) -> None:
        self.ready()
        self.src(self.fig_id()).write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8")
        item = self.item()
        self.assertEqual("stale", item["state"])
        self.assertIn("依据未同步", item["reason"])
        self.assertIn("已按源刷新", self.ok("mermaid").stdout)
        item = self.item()
        self.assertEqual("stale", item["state"], "图源改了，旧阅读图还当可用")
        self.assertNotIn("依据未同步", item["reason"])

    def test_reports_that_do_not_complete_the_review_are_not_usable(self) -> None:
        self.ready()
        cases = {
            "FAIL": ({}, "FAIL", "failed"),
            "UNKNOWN": ({}, "UNKNOWN", "incomplete"),
            "非法值": ({}, "OK", "invalid"),
            "阻断项": ({"blocking_findings": ["没有增益"]}, "PASS", "failed"),
            "未核": ({"unreviewed": ["visual_readability：看不了图"]}, "PASS", "incomplete"),
            "没有执行引用": ({"executor": ""}, "PASS", "invalid"),
        }
        for name, (extra, verdict, want) in cases.items():
            with self.subTest(name):
                self.make_ready(verdict=verdict, **extra)
                self.assertEqual(want, self.state())
                self.assertEqual(1, self.view("review-check", "--id", "recovery").returncode)
        self.make_ready()
        report = json.loads((self.reading() / "report.json").read_text(encoding="utf-8"))
        report["checks"].append({"id": "semantic_fidelity", "verdict": "FAIL", "evidence": "又审了一次"})
        (self.reading() / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("invalid", self.state(), "同一必核项两个结论没有拒收")
        report["checks"] = [c for c in report["checks"][:-1] if c["id"] != "reading_gain"]
        (self.reading() / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("incomplete", self.state(), "缺阅读增益的结论也收了")

    def test_the_old_contract_an_edited_request_and_a_fake_render_are_refused(self) -> None:
        self.ready()
        req_file = self.reading() / "request.json"
        req = json.loads(req_file.read_text(encoding="utf-8"))
        old = {**req, "version": 1, "method": "story-reading-review/1"}
        req_file.write_text(json.dumps(old), encoding="utf-8")
        self.assertEqual("invalid", self.state())
        self.assertIn("story-reading-review/2", self.item()["reason"])
        for name, change in (("改 ID", lambda r: r.update(id="other")),
                             ("改依据路径", lambda r: r["inputs"]["basis"][0].update(path="plan/plan.md")),
                             ("删必核项", lambda r: r.update(checks=r["checks"][:1]))):
            with self.subTest(name):
                bad = json.loads(json.dumps(req))
                change(bad)
                req_file.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual("invalid", self.state())
        req_file.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
        self.assertEqual("ready", self.state())
        fake = self.root / "fake.png"
        fake.write_text("not a png", encoding="utf-8")
        proc = self.view("review-request", "--id", "recovery", "--render", str(fake))
        self.assertEqual(1, proc.returncode)
        self.assertIn("不是 PNG", proc.stderr)

    def test_a_resource_reached_through_a_nested_svg_is_bound(self) -> None:
        self.ok("prepare")
        figs = self.fr / "AR" / "figures"
        figs.mkdir(parents=True, exist_ok=True)
        (figs / "nested.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><image href="../assets/deep.png"/></svg>',
                                         encoding="utf-8")
        (self.fr / "AR" / "assets").mkdir(parents=True, exist_ok=True)
        deep = self.fr / "AR" / "assets" / "deep.png"
        deep.write_bytes(PNG + b"deep")
        self.put_svg(text=svg('<image href="nested.svg"/>'))
        request = self.make_ready()
        self.assertIn("assets/deep.png", json.dumps(request["inputs"]["resources"]), "嵌套 SVG 引用的资源没进请求")
        deep.write_bytes(PNG + b"deep2")
        self.assertEqual("stale", self.state(), "改了嵌套资源，旧验收照样成立")

    def test_review_only_accepts_selected_figures(self) -> None:
        self.ready()
        fid = self.fig_id()
        for mode in ("review-request", "review-check"):
            with self.subTest(mode):
                proc = self.view(mode, "--id", fid)
                self.assertEqual(1, proc.returncode)
                self.assertIn("不在写作设计「## 阅读图选择」的候选里", proc.stderr)
        self.assertNotIn(fid, json.dumps(self.work()["items"]), "正式图被当成了阅读工作")


class SlotsBelongToTheScript(FigureViewCase):
    def refused(self, *modes: str, needle: str) -> None:
        before = self.story.read_bytes()
        for mode in modes:
            with self.subTest(mode=mode, needle=needle):
                proc = self.view(mode)
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn(needle, proc.stderr)
        self.assertEqual(before, self.story.read_bytes(), "坏槽也写了")

    def test_author_text_in_a_slot_is_kept_and_refused(self) -> None:
        self.ok("prepare")
        self.edit("<!-- story-reading:recovery:end -->", "作者写的一句。\n<!-- story-reading:recovery:end -->")
        self.refused("mermaid", "svg", "prepare", "toggle", needle="不是本机制生成的内容")
        self.assertIn("作者写的一句。", self.text())
        formal = self.build("number")
        self.assertEqual(1, formal.returncode, "槽里有作者文字，正式命令照常执行")

    def test_broken_or_duplicate_slots_write_nothing_anywhere(self) -> None:
        self.ready()
        self.ok("svg")
        good = self.text()
        begin, end = "<!-- story-reading:recovery:begin -->", "<!-- story-reading:recovery:end -->"
        block = good[good.index(begin):good.index(end) + len(end)]
        variants = {"重复": good.replace(block, f"{block}\n\n{block}"), "孤立开始标记": good.replace(end, "")}
        for name, text in variants.items():
            with self.subTest(name):
                self.story.write_text(text, encoding="utf-8")
                work = self.work()
                self.assertFalse(work["complete"])
                self.assertTrue(work["next"])
                self.refused("mermaid", "svg", "toggle", "prepare", needle="阅读槽")
                self.assertEqual(1, self.build("number").returncode)

    def test_cancel_and_move_are_synced_by_prepare_alone(self) -> None:
        self.ready()
        self.design(candidate(place="07-exceptions > 共同恢复规则"))
        work = self.work()
        self.assertEqual("misplaced", work["items"][0]["state"], work)
        before = self.story.read_bytes()
        self.assertEqual(1, self.view("svg").returncode, "错位的槽也被填了")
        self.assertEqual(before, self.story.read_bytes())
        self.ok("prepare")
        text = self.text()
        self.assertLess(text.index("按远端事实恢复。"), text.index("<!-- story-reading:recovery:begin -->"), "prepare 没把槽迁到新位置")
        self.assertEqual(1, text.count("story-reading:recovery:begin"))
        self.design(NONE)
        work = self.work()
        self.assertFalse(work["complete"], "取消后遗留的槽没被报出来")
        self.assertIn("不在当前选择里", "；".join(work["problems"]))
        self.assertIn("已移除不在当前选择里的阅读槽 recovery", self.ok("prepare").stdout)
        self.assertNotIn("story-reading", self.text())
        self.assertEqual(STORY, self.text().replace("\r\n", "\n").replace(f"<!-- story-figure:{self.fig_id()}:begin -->\n", "")
                         .replace(f"<!-- story-figure:{self.fig_id()}:end -->\n", ""), "清槽动了槽外正文")
        self.assertTrue((self.fr / "AR" / "figures" / "recovery.svg").is_file(), "取消选择删了作者的 SVG")
        self.assertEqual((False, True), (self.work()["applicable"], self.work()["complete"]))

    def test_moving_to_an_ambiguous_place_keeps_every_byte(self) -> None:
        self.ok("prepare")
        self.edit("本地记录清掉后按远端事实恢复。\n", "本地记录清掉后按远端事实恢复。\n\n### 共同恢复规则\n\n重复的一节。\n")
        self.design(candidate(place="07-exceptions > 共同恢复规则"))
        before = self.story.read_bytes()
        proc = self.view("prepare")
        self.assertEqual(1, proc.returncode)
        self.assertIn("同名", proc.stderr)
        self.assertEqual(before, self.story.read_bytes())

    def test_an_old_svg_reference_in_a_figure_block_is_refused(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        text = self.text()
        begin, end = f"<!-- story-figure:{fid}:begin -->", f"<!-- story-figure:{fid}:end -->"
        self.story.write_text(text[:text.index(begin) + len(begin)] + f"\n![提交与回执（阅读图）](figures/{fid}.svg)\n"
                              + text[text.index(end):], encoding="utf-8")
        self.refused("mermaid", "svg", needle="旧版阅读形态")
        self.ok("prepare", "--id", fid)
        self.assertIn("```mermaid", self.text())

    def test_a_stray_reading_link_blocks_check_and_a_registered_image_does_not(self) -> None:
        self.ready()
        (self.fr / "AR" / "story-src" / "decisions.json").write_text(json.dumps({"decisions": []}), encoding="utf-8")
        (self.fr / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"origins": [{"path": "AR/figures/shot.png"}]}), encoding="utf-8")
        self.edit("取消后退款。", "取消后退款。\n\n![旧图](figures/recovery.svg)\n\n![截图](figures/shot.png)\n\n[旧链接]: figures/old.svg")
        import shutil  # noqa: PLC0415
        shutil.copytree(DEV_EXT, self.root / "doc" / "extensions", ignore=shutil.ignore_patterns("__pycache__"))
        self.ok("svg")
        proc = self.build("check")
        self.assertEqual(1, proc.returncode)
        self.assertIn("阅读槽之外引用了本地阅读资产 AR/figures/recovery.svg", proc.stderr)
        self.assertIn("AR/figures/old.svg", proc.stderr, "已取消图的引用式定义漏检")
        self.assertNotIn("本地阅读资产 AR/figures/shot.png", proc.stderr, "登记过的原始材料图片被误拦")
        self.assertEqual(1, proc.stderr.count("本地阅读资产 AR/figures/recovery.svg"), "槽里的阅读图也被当成了槽外引用")
        self.assertTrue(self.slot(), "check 之后没有恢复阅读图")


class TheBasisIsWhatItSays(FigureViewCase):
    """依据按真实位置、登记身份与原件链解析：声明检查、请求生成与重验用同一份结果。"""

    TEXT_ONLY = STORY.replace("```mermaid\n" + FLOW_SRC + "```\n\n", "")
    PRD = "# 产品需求\n\n## 恢复规则\n\n清掉之后按远端事实恢复。\n\n## 其它\n\n无关的一节。\n"

    @staticmethod
    def bmp(blue: int) -> bytes:
        """一份合法的 1×1 24 位 BMP，只有像素的蓝色字节不同。"""
        pixel = bytes([blue, 0, 0, 0])
        return (b"BM" + struct.pack("<IHHI", 14 + 40 + len(pixel), 0, 0, 54)
                + struct.pack("<IiiHHIIiiII", 40, 1, 1, 1, 24, 0, len(pixel), 2835, 2835, 0, 0) + pixel)

    @staticmethod
    def registered(data: bytes) -> str:
        return "sha256:" + hashlib.sha256(data).hexdigest()[:16]

    def put(self, rel: str, data: bytes) -> bytes:
        path = self.fr / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def manifest(self, origins: list, materials: list) -> None:
        (self.fr / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"schema": 2, "origins": origins, "materials": materials, "sources": []}, ensure_ascii=False), encoding="utf-8")

    def link(self, link: Path, target: Path) -> None:
        if os.path.lexists(link):
            os.rmdir(link) if sys.platform == "win32" else os.unlink(link)
        if sys.platform == "win32":
            import _winapi  # noqa: PLC0415
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)

    def choose(self, *basis: str) -> None:
        self.story.write_text(self.TEXT_ONLY, encoding="utf-8")
        self.design(candidate(basis=basis))

    def test_a_linked_basis_counts_where_it_really_is(self) -> None:
        shot = self.bmp(128)
        self.manifest([], [{"kind": "image", "paths": ["assets/shots/a.bmp"], "sha256": self.registered(shot)}])
        inside = self.fr / "assets-real"
        self.put("assets-real/a.bmp", shot)
        (self.fr / "assets").mkdir()
        self.link(self.fr / "assets" / "shots", inside)
        self.choose("assets/shots/a.bmp")
        self.ready()
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (outside / "a.bmp").write_bytes(shot)
        self.link(self.fr / "assets" / "shots", outside)
        item = self.item()
        self.assertEqual("stale", item["state"], "联接改指到需求目录外，旧验收照样成立")
        self.assertIn("不在本需求的来源范围里", item["reason"])
        self.assertIn("不在本需求的来源范围里", "；".join(self.work()["problems"]), "写作设计的声明检查没发现改指")
        proc = self.view("review-request", "--id", "recovery")
        self.assertEqual(1, proc.returncode)
        self.assertIn("不在本需求的来源范围里", proc.stderr)
        shutil.rmtree(outside)
        item = self.item()
        self.assertEqual("stale", item["state"])
        self.assertIn("读不到", item["reason"], "断开的联接没被说出来")

    def test_an_image_basis_is_bound_by_its_bytes(self) -> None:
        first, second = self.bmp(128), self.bmp(129)
        self.manifest([], [{"kind": "image", "paths": ["ux-reference/a.bmp"], "sha256": self.registered(first)}])
        self.put("ux-reference/a.bmp", first)
        self.choose("ux-reference/a.bmp")
        self.ready()
        request = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(first).hexdigest(), request["inputs"]["basis"][0]["sha256"])
        self.assertIn("ux-reference/a.bmp（图片，自己打开看）", self.ok("review-request", "--id", "recovery").stdout)
        self.put("ux-reference/a.bmp", second)
        item = self.item()
        self.assertEqual("stale", item["state"], "换了一张图，旧验收照样成立")
        self.assertIn("登记之后变了", item["reason"])
        self.manifest([], [{"kind": "image", "paths": ["ux-reference/a.bmp"], "sha256": self.registered(second)}])
        self.assertEqual("stale", self.state(), "重新登记之后旧报告还算数")
        self.put("ux-reference/a.bmp", first)
        self.manifest([], [{"kind": "image", "paths": ["ux-reference/a.bmp"], "sha256": self.registered(first)}])
        self.assertEqual("ready", self.state())

    def test_an_original_is_read_through_its_registered_readable(self) -> None:
        docx = self.put("inbox/需求.docx", b"PK\x03\x04 fake docx v1")
        prd = self.put("RR/prd.md", self.PRD.encode("utf-8"))
        origin = {"path": "inbox/需求.docx", "sha256": self.registered(docx), "kind": "converted-source", "readable_paths": ["RR/prd.md"]}
        self.manifest([origin], [{"kind": "doc", "paths": ["RR/prd.md"], "sha256": self.registered(prd)}])
        self.choose("inbox/需求.docx > 恢复规则", "RR/prd.md > 恢复规则")
        self.ready()
        basis = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))["inputs"]["basis"]
        self.assertEqual([("inbox/需求.docx", "RR/prd.md"), ("RR/prd.md", "RR/prd.md")], [(b["path"], b["read"]) for b in basis])
        self.assertEqual([[("inbox/需求.docx", "原件")]] * 2, [[(f["path"], f["role"]) for f in b["related"]] for b in basis],
                         "选原件或选阅读稿都要带上原件身份")
        out = self.ok("review-request", "--id", "recovery").stdout
        self.assertIn("清掉之后按远端事实恢复。", out, "任务里没有阅读稿的实际段落")
        self.assertIn("同组原件", out)
        self.assertNotIn("fake docx", out, "原件按文本塞进了任务")
        prd = self.put("RR/prd.md", self.PRD.replace("无关的一节", "另一件事").encode("utf-8"))
        self.manifest([origin], [{"kind": "doc", "paths": ["RR/prd.md"], "sha256": self.registered(prd)}])
        self.assertEqual("ready", self.state(), "阅读稿里无关的一节变了也让它过期")
        self.put("inbox/需求.docx", b"PK\x03\x04 fake docx v2")
        item = self.item()
        self.assertEqual("stale", item["state"], "原件变了、阅读稿没重新并入，旧验收照样成立")
        self.assertIn("登记之后变了", item["reason"])

    def test_a_really_imported_original_is_bound_with_its_readable(self) -> None:
        """正例走真实导入与 round 生成的材料清单：选原件就读它并入的那份正文，原件变了没重新导入就过期。"""
        import zipfile  # noqa: PLC0415
        for rel, text in (("SR/design.md", "# 系统设计\n\n分工。\n"), ("AR/design.md", "# 提取件\n\n范围。\n")):
            self.put(rel, text.encode("utf-8"))
        inbox = self.fr / "inbox"
        inbox.mkdir()
        (inbox / ".classify.json").write_text(json.dumps({"原稿.docx": "RR"}, ensure_ascii=False), encoding="utf-8")

        def docx(words: str) -> None:
            with zipfile.ZipFile(inbox / "原稿.docx", "w") as zf:
                zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                            f'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{words}</w:t></w:r></w:p></w:body></w:document>')
        docx("清掉之后按远端事实恢复")
        for script, extra in (("import_sources.py", ()), ("story_flow.py", ("round",))):
            proc = subprocess.run([sys.executable, str(CORE / script), *extra, "--feature", FEATURE, "--project-root", str(self.root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.choose("inbox/原稿.docx")
        self.ready()
        basis = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))["inputs"]["basis"][0]
        self.assertEqual(("RR/prd.md", [("inbox/原稿.docx", "原件")]), (basis["read"], [(f["path"], f["role"]) for f in basis["related"]]))
        docx("清掉之后转人工")
        item = self.item()
        self.assertEqual("stale", item["state"], "原件换了内容、没重新导入，旧验收照样成立")
        self.assertIn("登记之后变了", item["reason"])

    def test_an_image_only_original_hands_over_its_pictures(self) -> None:
        """只抽图的原件：真实导入与 round 之后，要看的是抽出的每张原图，原件只作身份；原件或任一张图变了都过期。"""
        import zipfile  # noqa: PLC0415
        for rel, text in (("RR/prd.md", self.PRD), ("SR/design.md", "# 系统设计\n\n分工。\n"), ("AR/design.md", "# 提取件\n\n范围。\n")):
            self.put(rel, text.encode("utf-8"))
        inbox = self.fr / "inbox"
        inbox.mkdir()
        (inbox / ".classify.json").write_text(json.dumps({"界面稿.docx": "IMAGES"}, ensure_ascii=False), encoding="utf-8")
        ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        with zipfile.ZipFile(inbox / "界面稿.docx", "w") as zf:
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                        'wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                        '<w:body><w:p><w:r><w:t>草稿正文不采用</w:t></w:r></w:p>'
                        + "".join(f'<w:p><w:r><w:drawing><a:blip {ns} r:embed="rId{i}"/></w:drawing></w:r></w:p>' for i in (1, 2))
                        + '</w:body></w:document>')
            zf.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                        'package/2006/relationships">' + "".join(
                            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"'
                            f' Target="media/image{i}.png"/>' for i in (1, 2)) + '</Relationships>')
            for i in (1, 2):
                zf.writestr(f"word/media/image{i}.png", PNG + f"picture-{i}".encode())
        for script, extra in (("import_sources.py", ()), ("story_flow.py", ("round",))):
            proc = subprocess.run([sys.executable, str(CORE / script), *extra, "--feature", FEATURE, "--project-root", str(self.root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        manifest = json.loads((self.fr / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))
        pictures = next(o for o in manifest["origins"] if o["path"] == "inbox/界面稿.docx")["image_paths"]
        self.assertEqual(2, len(pictures))
        self.choose("inbox/界面稿.docx")
        self.ready()
        basis = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))["inputs"]["basis"][0]
        self.assertIsNone(basis["read"], "只抽图的原件被当成了要阅读的对象")
        self.assertEqual({"inbox/界面稿.docx": "原件", **{p: "原图" for p in pictures}}, {f["path"]: f["role"] for f in basis["related"]})
        task = self.ok("review-request", "--id", "recovery").stdout.splitlines()
        shown = [line for line in task if line.startswith("  - 同组原图：")]
        self.assertEqual(sorted(pictures), sorted(line.split("：", 1)[1].split("/", 3)[-1].split("（")[0] for line in shown))
        self.assertTrue(all((self.fr / p).is_file() for p in pictures))
        head = next(line for line in task if "界面稿.docx" in line and line.startswith("- "))
        self.assertNotIn("图片，自己打开看", head, "原件被要求按图片阅读")
        picture = self.fr / pictures[1]
        before = picture.read_bytes()
        picture.write_bytes(PNG + b"redrawn")
        self.assertEqual("stale", self.state(), "抽出的一张图换了，旧验收照样成立")
        picture.write_bytes(before)
        self.assertEqual("ready", self.state())
        with zipfile.ZipFile(inbox / "界面稿.docx", "a") as zf:
            zf.writestr("word/comments.xml", "<c/>")
        self.assertEqual("stale", self.state(), "原件换了，旧验收照样成立")

    def test_a_missing_readable_or_a_broken_list_is_not_an_empty_answer(self) -> None:
        docx = self.put("inbox/需求.docx", b"PK\x03\x04 fake docx")
        self.put("RR/prd.md", self.PRD.encode("utf-8"))
        cases = {
            "阅读稿不在": ([{"path": "inbox/需求.docx", "sha256": self.registered(docx), "kind": "converted-source",
                         "readable_paths": ["RR/missing.md"]}], "登记的阅读稿 RR/missing.md 读不到"),
            "没有阅读稿": ([{"path": "inbox/需求.docx", "sha256": self.registered(docx), "kind": "converted-source",
                         "readable_paths": []}], "还没经导入链并入"),
            "没有摘要": ([{"path": "inbox/需求.docx", "kind": "converted-source", "readable_paths": ["RR/prd.md"]}],
                     "没有原件 inbox/需求.docx 的摘要"),
        }
        self.choose("inbox/需求.docx")
        for name, (origins, needle) in cases.items():
            with self.subTest(name):
                self.manifest(origins, [])
                work = self.work()
                self.assertFalse(work["complete"])
                self.assertIn(needle, "；".join(work["problems"]))
        (self.fr / "AR" / "story-src" / "materials.json").write_text("{ 坏了", encoding="utf-8")
        self.assertIn("读不出来源关系", "；".join(self.work()["problems"]))
        self.design(candidate(basis=BASIS[:1]))
        self.assertEqual([], self.work()["problems"], "清单坏了也挡住了只用正式 Story 的依据")


class TheFormalFormHasNoReadingFigures(FigureViewCase):
    def text_only(self) -> None:
        """没有 Mermaid、只有文字与表和一张综合阅读图，显示中。"""
        self.story.write_text(STORY.replace("```mermaid\n" + FLOW_SRC + "```\n\n", ""), encoding="utf-8")
        self.ready()
        self.ok("svg")
        self.assertTrue(self.slot())

    def test_hooks_and_preflight_hide_a_reading_only_story(self) -> None:
        self.text_only()
        hook = DEV_EXT / "hooks" / "shared" / "story-view.mjs"
        driver = ("const h = (await import(process.argv[1])).default;"
                  "process.stdout.write(JSON.stringify(await h({phase:'spec', feature: process.argv[2], projectRoot: process.argv[3]})));")
        got = json.loads(subprocess.run(["node", "--input-type=module", "-e", driver, hook.as_uri(), FEATURE, str(self.root)],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout)
        self.assertEqual({"ok": True}, got)
        self.assertEqual("", self.slot(), "阶段钩子没有收起只有阅读槽的 story")
        self.assertNotIn("figures/", self.text())
        self.ok("svg")
        pre = DEV_EXT / "hooks" / "shared" / "pre_verifier.mjs"
        driver = ("const h = (await import(process.argv[1])).default;"
                  "process.stdout.write(JSON.stringify(await h({feature: process.argv[2], projectRoot: process.argv[3]})));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver, pre.as_uri(), FEATURE, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", self.slot(), "预检没有收起阅读图")

    def test_formal_commands_hide_then_restore_and_keep_their_exit_code(self) -> None:
        self.text_only()
        proc = self.build("number")
        self.assertIn("已恢复 1 张可用的本地阅读图", proc.stderr)
        self.assertTrue(self.slot(), "命令结束没有恢复阅读图")
        proc = self.build("check")
        self.assertEqual(1, proc.returncode, "业务失败被视图恢复盖掉了")
        self.assertTrue(self.slot(), "失败之后没有恢复阅读图")

    def test_partly_ready_shows_only_what_is_ready_and_says_why(self) -> None:
        self.design(candidate() + candidate("later", question="取消之后去哪"))
        self.ready()
        proc = self.ok("svg")
        self.assertTrue(self.slot())
        self.assertEqual("", self.slot("later"))
        self.assertIn("later：还没有阅读图", proc.stdout)
        work = self.work()
        self.assertEqual((False, ["ready", "no-svg"]), (work["complete"], [i["state"] for i in work["items"]]))
        proc = self.build("number")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("本地阅读还没完成", proc.stderr)
        self.assertIn("later", proc.stderr)
        self.assertTrue(self.slot())

    def test_the_flow_reader_restores_and_an_internal_query_does_not(self) -> None:
        self.ready()
        client = CORE / "flow" / "client.mjs"
        driver = ("const m = await import(process.argv[1]);"
                  "const r = m.queryFlowStatus(process.argv[2], process.argv[3], { timeoutMs: 120000 });"
                  "process.stdout.write(JSON.stringify({ error: r.error }));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver, client.as_uri(), str(self.root), FEATURE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", self.slot(), "内部查询把正式读取的 story 换成了阅读形态")
        proc = subprocess.run([sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertIn("view", out, "story_flow 没有交回视图的去向")
        self.assertTrue(self.slot(), "用户直接跑 status 没恢复阅读图")

    def test_a_closed_spec_still_routes_to_the_unfinished_reading(self) -> None:
        """spec 闭环后选中的阅读图没完成：路由把阅读作为下一步。路由在最外层持有的正式形态下判，这里照此切换。"""
        self.ok("prepare")
        sys.path.insert(0, str(CORE))
        from flow import routing, state  # noqa: PLC0415
        contract = {"rounds": [{"round": 1}], "status": "story_written",
                    "story_digests": {rel: state.ledger_digest(self.fr / rel) for rel in state.STORY_REGISTERED}}
        self.assertEqual("run_archived", routing.next_step(self.fr, contract)[0], "spec 没闭环时先走闭环")
        reports = self.fr / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text("{ 坏了", encoding="utf-8")
        with self.assertRaises(state.FlowError, msg="summary 读不出却当成没闭环"):
            routing.next_step(self.fr, contract)
        (reports / "summary.json").write_text(json.dumps({"closure_status": "closed"}), encoding="utf-8")
        step, action = routing.next_step(self.fr, contract)
        self.assertEqual("local_reading", step)
        self.assertIn("recovery", action)
        self.put_svg()
        self.make_ready()
        self.ok("svg")
        self.ok("mermaid")
        self.assertEqual("run_archived", routing.next_step(self.fr, contract)[0], "阅读完成后还卡在阅读")


class TheReadingTodoNeverHidesAProblem(unittest.TestCase):
    def test_only_a_consistent_finish_is_done(self) -> None:
        sys.path.insert(0, str(CORE))
        from flow import routing  # noqa: PLC0415
        base = {"items": [], "unmanaged": [], "next": None}
        self.assertIsNone(routing.reading_todo({**base, "applicable": False, "complete": True, "problems": []}))
        masked = routing.reading_todo({**base, "applicable": False, "complete": False, "problems": ["阅读图选择没写"]})
        self.assertIn("阅读图选择没写", masked, "不适用掩盖了坏声明")
        self.assertIn("自相矛盾", routing.reading_todo({**base, "applicable": True, "complete": True, "problems": ["槽坏了"]}))
        self.assertIn("读不出", routing.reading_todo({"complete": True}))


class TheSourceOwnsTheMeaning(FigureViewCase):
    """`.mmd` 是唯一真源，正文块只按它派生（R01）：改源能刷新，重建不回退源，手改块按源恢复并说明。"""

    def test_prepare_wraps_the_figure_writes_its_source_and_is_idempotent(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        self.assertIn(f"<!-- story-figure:{fid}:begin -->\n```mermaid\n{FLOW_SRC}```\n<!-- story-figure:{fid}:end -->", self.text())
        self.assertEqual(FLOW_SRC, self.src(fid).read_text(encoding="utf-8"))
        before = self.story.read_bytes()
        self.ok("prepare")
        self.assertEqual(before, self.story.read_bytes(), "重跑 prepare 又改了 story")

    def test_a_source_edit_reaches_the_mermaid_block(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        self.src(fid).write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8")
        proc = self.ok("mermaid")
        self.assertIn("转人工", self.text())
        self.assertIn("已按源刷新", proc.stdout)
        self.assertIn("图后：回执超时由服务端重试。", self.text(), "块外正文被动了")

    def test_prepare_id_never_puts_the_old_body_back_into_the_source(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        changed = FLOW_SRC.replace("提示重试", "转人工")
        self.src(fid).write_text(changed, encoding="utf-8")
        self.ok("prepare", "--id", fid)
        self.assertEqual(changed, self.src(fid).read_text(encoding="utf-8"), "prepare --id 拿正文覆盖了源")
        self.assertIn("转人工", self.text())

    def test_a_hand_edited_block_is_restored_from_the_source_with_a_note(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        self.edit("等回执", "等短信")
        proc = self.ok("mermaid")
        self.assertNotIn("等短信", self.text())
        self.assertIn(f"{fid}：正文里的图与源", proc.stdout, "差异被静默丢掉了")

    def test_two_fences_with_prose_between_are_a_broken_block(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        self.edit(f"```\n<!-- story-figure:{fid}:end -->",
                  f"```\n受理失败三次转人工。\n```mermaid\nflowchart TD\n  X --> Y\n```\n<!-- story-figure:{fid}:end -->")
        before = self.story.read_bytes()
        for mode in ("mermaid", "svg"):
            with self.subTest(mode=mode):
                proc = self.view(mode)
                self.assertNotEqual(0, proc.returncode, proc.stdout)
                self.assertIn(f"图块 {fid}", proc.stderr)
                self.assertEqual(before, self.story.read_bytes(), "结构坏的块被自动重铺，块里的正文没了")
        self.ok("prepare", "--id", fid)
        self.assertNotIn("X --> Y", self.text())

    def test_first_prepare_does_not_overwrite_a_different_source_at_the_same_id(self) -> None:
        import hashlib  # noqa: PLC0415
        fid = f"fig-{hashlib.sha256(FLOW_SRC.rstrip(chr(10)).encode('utf-8')).hexdigest()[:8]}"
        self.src(fid).parent.mkdir(parents=True, exist_ok=True)
        self.src(fid).write_text("flowchart TD\n  X --> Y\n", encoding="utf-8")
        before = self.story.read_bytes()
        proc = self.view("prepare")
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("不覆盖已有的源", proc.stderr)
        self.assertEqual(before, self.story.read_bytes())

    def test_broken_blocks_name_themselves_and_give_the_rebuild_entry(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        good = self.text()
        variants = {
            "夹了正文": (good.replace(f"<!-- story-figure:{fid}:end -->", f"夹进来的一句。\n<!-- story-figure:{fid}:end -->"), f"图块 {fid}"),
            "孤立标记": (good + "\n<!-- story-figure:lonely:begin -->\n", "没有结束标记"),
        }
        for name, (text, needle) in variants.items():
            with self.subTest(name):
                self.story.write_text(text, encoding="utf-8")
                before = self.story.read_bytes()
                proc = self.view("mermaid")
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn(needle, proc.stderr)
                self.assertIn("view --mode prepare --id", proc.stderr, "没给恢复入口")
                self.assertEqual(before, self.story.read_bytes())
        self.story.write_text(good, encoding="utf-8")
        self.src(fid).unlink()
        proc = self.view("mermaid")
        self.assertEqual(1, proc.returncode)
        self.assertIn(f"{fid}.mmd 不在", proc.stderr)


class TheStructureCheck(FigureViewCase):
    def check(self, text: str, fid: str = "fig-a") -> subprocess.CompletedProcess:
        path = self.put_svg(fid, text)
        return subprocess.run([sys.executable, str(CHECK), str(path), "--id", fid],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def test_a_valid_view_passes_with_or_without_metadata(self) -> None:
        (self.fr / "AR" / "figures" / "fonts").mkdir(parents=True, exist_ok=True)
        (self.fr / "AR" / "figures" / "icon.png").write_bytes(b"PNG")
        (self.fr / "AR" / "figures" / "fonts" / "ui.woff2").write_bytes(b"WOFF")
        extra = ('<image href="icon.png"/><image href="data:image/png;base64,AA=="/>'
                 '<image xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="icon.png"/>'
                 '<style>@font-face{font-family:ui;src:url("fonts/ui.woff2")} .t{font-family:ui}</style>'
                 '<defs><linearGradient id="g"/></defs><rect fill="url(#g)" transform="translate(1 2)" width="5" height="5"/>')
        self.assertEqual(0, self.check(svg(extra)).returncode)
        self.assertEqual(0, self.check(svg("<metadata>依据：业务流程 › 提交与回执</metadata>")).returncode)

    def test_each_structural_fault_is_named(self) -> None:
        cases = {
            "<svg": "不是合法 XML",
            '<g xmlns="http://www.w3.org/2000/svg"/>': "不是 svg",
            '<notsvg viewBox="0 0 1 1"></notsvg>': "不是 svg",
            '<svg viewBox="0 0 1 1"></svg>': "缺 SVG 命名空间",
            svg().replace("0 0 400 200", "0 0 400"): "viewBox",
            svg().replace("0 0 400 200", "0 0 NaN Infinity"): "四个有限数",
            svg("<style>@font-face{src:url(missing.woff2)}</style>"): "引用「missing.woff2」读不到",
            svg("<style>@import 'theme.css';</style>"): "引用「theme.css」读不到",
            svg('<text style="fill:url(https://cdn.example/p.svg#p)">x</text>'): "不是本地相对路径",
            svg('<image href="C:/机器/图.png"/>'): "不是本地相对路径",
            svg('<image href="../../../外面.png"/>'): "逃出了 AR/",
            svg('<image href="没有.png"/>'): "读不到",
        }
        for text, needle in cases.items():
            with self.subTest(needle=needle):
                proc = self.check(text)
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn(needle, proc.stdout)
        self.check(svg(), fid="fig-a")
        renamed = subprocess.run([sys.executable, str(CHECK), str(self.fr / "AR" / "figures" / "fig-a.svg"), "--id", "fig-b"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertIn("与阅读图 ID fig-b 不一致", renamed.stdout)


class TheCheckCommandRunsAsPrinted(unittest.TestCase):
    """审查任务末尾的核对命令照抄就能跑：入口按工程配置的扩展目录，工程与扩展路径带空格，从别的目录执行。"""

    def run_printed(self, project: Path, ext_dir: str | None) -> subprocess.CompletedProcess:
        fr = project / "doc" / "features" / FEATURE
        (fr / "AR" / "story-src").mkdir(parents=True)
        link_harness_yaml(project)
        if ext_dir:
            (project / "framework.config.json").write_text(json.dumps({"paths": {"extension_dir": ext_dir}}), encoding="utf-8")
        ext = project / (ext_dir or "doc/extensions")
        shutil.copytree(DEV_EXT, ext, ignore=shutil.ignore_patterns("__pycache__"))
        (fr / "AR" / "story.md").write_text(STORY, encoding="utf-8")
        (fr / "AR" / "story-src" / "story-template.md").write_text(SKELETON + candidate(), encoding="utf-8")
        build = ext / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
        run = lambda *a: subprocess.run(["node", str(build), "view", *a, "--feature", FEATURE, "--project-root", str(project)],  # noqa: E731
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, run("--mode", "prepare").returncode)
        (fr / "AR" / "figures").mkdir(parents=True)
        (fr / "AR" / "figures" / "recovery.svg").write_text(svg(), encoding="utf-8")
        shot = project / "shot.png"
        shot.write_bytes(PNG + b"render")
        out = run("--mode", "review-request", "--id", "recovery", "--render", str(shot))
        self.assertEqual(0, out.returncode, out.stderr)
        line = next(l for l in out.stdout.splitlines() if "review-check" in l)
        command = line[line.index("`") + 1:line.rindex("`")]
        self.assertIn(str(build), command)
        sys.path.insert(0, str(Path(__file__).parent))
        from test_adapt_ownership import run_in_shell  # noqa: PLC0415
        return run_in_shell(command, cwd=Path(tempfile.gettempdir()))

    def test_default_and_custom_extension_dirs_with_spaces(self) -> None:
        for name, ext_dir in (("work", None), ("带 空格 (副本)", "custom ext/extensions")):
            with self.subTest(ext_dir=ext_dir), tempfile.TemporaryDirectory() as tmp:
                done = self.run_printed(Path(tmp) / name, ext_dir)
                said = done.stdout + done.stderr
                self.assertNotIn("Cannot find module", said, said)
                self.assertEqual(1, done.returncode, said)
                self.assertIn("阅读图 recovery 的验收没有成立（no-report）", said, "核对命令没到达正确的入口")


class TheOneClickEntry(FigureViewCase):
    """AR 下的一键切换入口：合同登记的唯一文件名，只覆盖自己生成的同名文件，不依赖 cwd 与机器路径。"""

    NAME = "切换视图.cmd"

    def test_prepare_writes_it_once_and_keeps_a_users_file(self) -> None:
        self.ok("prepare")
        entry = self.fr / "AR" / self.NAME
        self.assertTrue(entry.is_file())
        body = entry.read_bytes()
        self.assertNotIn(str(self.root).encode("utf-8"), body, "入口里写死了机器路径")
        self.assertNotIn(FEATURE.encode("utf-8"), body, "入口里写死了需求名")
        self.ok("prepare")
        self.assertEqual(body, entry.read_bytes())
        entry.write_text("@echo off\nrem 我自己的脚本\n", encoding="utf-8")
        self.assertIn("不是本机制生成的", self.view("prepare").stdout)
        self.assertEqual("@echo off\nrem 我自己的脚本\n", entry.read_text(encoding="utf-8"))

    @unittest.skipUnless(sys.platform == "win32", "一键入口是 Windows 批处理")
    def test_double_click_from_any_cwd_in_a_path_with_spaces(self) -> None:
        import shutil  # noqa: PLC0415
        moved = Path(self._tmp.name) / "带 空格 (副本)" / "work"
        (moved / "doc").mkdir(parents=True)
        shutil.copytree(DEV_EXT, moved / "doc" / "extensions")
        shutil.copytree(self.fr, moved / "doc" / "features" / FEATURE)
        link_harness_yaml(moved)
        build = moved / "doc/extensions/skills/story/scripts/core/story-build.mjs"
        subprocess.run(["node", str(build), "view", "--mode", "prepare", "--feature", FEATURE, "--project-root", str(moved)],
                       capture_output=True, timeout=120)
        entry = moved / "doc" / "features" / FEATURE / "AR" / self.NAME
        proc = subprocess.run(["cmd", "/c", str(entry)], cwd=str(Path(self._tmp.name)), input="\n",
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        said = proc.stdout + proc.stderr
        self.assertIn("view] toggle", said, said[-800:])
        self.assertIn("还没有阅读图", said)


class TheCoreArchiveEntry(FigureViewCase):
    """归档只有一个核心入口：交付门不过零系统调用；本地单与缺 token 不调；token 不出现在输出里。"""

    FEATURE_AR = "AR90009"

    def fake_adapter(self) -> Path:
        """站在合同登记的对接入口位置：被调用就留一个标记文件，回一份成功回执。"""
        adapter = self.root / "doc" / "extensions" / "skills" / "story" / "scripts" / "adapters" / "story.js"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        marker = self.root / "adapter-called"
        adapter.write_text(
            "require('fs').writeFileSync(" + json.dumps(str(marker)) + ", process.argv.slice(2).join(' '));"
            "process.stdout.write(JSON.stringify({mode:'archive',reqNo:process.argv[3],archived:true,verified:true,"
            "reviewArchived:true,success:true}));", encoding="utf-8")
        return marker

    def archive(self, feature: str, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(BUILD), "archive", "--feature", feature, "--project-root", str(self.root), *extra],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)

    def test_a_local_requirement_and_a_missing_token_never_reach_the_system(self) -> None:
        marker = self.fake_adapter()
        proc = self.archive(FEATURE, "--mcp-token", "secret-123")
        self.assertEqual(1, proc.returncode)
        self.assertIn("本地需求", proc.stderr)
        ar = self.root / "doc" / "features" / self.FEATURE_AR / "AR"
        ar.mkdir(parents=True)
        (ar / "story.md").write_text(STORY.replace(FEATURE, self.FEATURE_AR), encoding="utf-8")
        proc = self.archive(self.FEATURE_AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("--mcp-token", proc.stderr)
        self.assertFalse(marker.exists())

    def test_a_failed_delivery_gate_makes_no_system_call(self) -> None:
        marker = self.fake_adapter()
        ar = self.root / "doc" / "features" / self.FEATURE_AR / "AR"
        ar.mkdir(parents=True)
        (ar / "story.md").write_text(STORY.replace(FEATURE, self.FEATURE_AR), encoding="utf-8")
        proc = self.archive(self.FEATURE_AR, "--mcp-token", "secret-123")
        self.assertEqual(1, proc.returncode)
        self.assertIn("交付门没过，没有调用需求系统", proc.stderr)
        self.assertFalse(marker.exists(), "交付门没过却调用了对接层")
        self.assertNotIn("secret-123", proc.stdout + proc.stderr)


class DerivedReadingEvidenceStaysOutOfUpdates(unittest.TestCase):
    """update 的镜像与还原精确排除一键入口与阅读图验收证据；图源与正文照常进镜像。"""

    def test_only_the_launcher_and_reading_evidence_are_skipped(self) -> None:
        sys.path.insert(0, str(CORE))
        try:
            from flow import update  # noqa: PLC0415
        finally:
            sys.path.remove(str(CORE))
        skipped = {rel: update._skipped(Path(rel)) for rel in (
            "AR/story-src/figures/fig-1.reading/report.json", "AR/story-src/figures/fig-1.reading/render.png",
            "AR/切换视图.cmd", "AR/story.md", "AR/story-src/figures/fig-1.mmd", "AR/figures/fig-1.svg",
            "assets/doc/a.png", "AR/story-src/reading/report.json")}
        self.assertEqual({"AR/story-src/figures/fig-1.reading/report.json": True,
                          "AR/story-src/figures/fig-1.reading/render.png": True, "AR/切换视图.cmd": True,
                          "AR/story.md": False, "AR/story-src/figures/fig-1.mmd": False, "AR/figures/fig-1.svg": False,
                          "assets/doc/a.png": False, "AR/story-src/reading/report.json": False}, skipped)


class OneVerdictEverywhere(FigureViewCase):
    """同一份结构在各入口结论一致（产品状态、视图、正式命令、装置）；阶段闭环按工程配置的报告目录判。"""

    def device_reading(self) -> dict:
        """装置读阅读状态的那条路：把这个临时工程当仓库根，扩展按运行态位置挂进去。"""
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import run_case as rc  # noqa: PLC0415
        ext = self.root / "doc" / "extensions"
        if not ext.exists():
            import shutil  # noqa: PLC0415
            shutil.copytree(DEV_EXT, ext, ignore=shutil.ignore_patterns("__pycache__"))
        from unittest import mock  # noqa: PLC0415
        with mock.patch.object(rc, "REPO_ROOT", self.root):
            return rc.reading_facts(self.fr)

    def test_a_broken_figure_block_is_refused_everywhere_and_nothing_is_written(self) -> None:
        self.ready()
        self.ok("svg")
        fid = self.fig_id()
        good = self.text()
        begin, end = f"<!-- story-figure:{fid}:begin -->", f"<!-- story-figure:{fid}:end -->"
        block = good[good.index(begin):good.index(end) + len(end)]
        variants = {
            "块体不是图": good.replace(block, f"{begin}\n这里被改成了普通文字\n{end}"),
            "重复 ID": good.replace(block, f"{block}\n\n{block}"),
            "孤立开始标记": good.replace(end, ""),
        }
        for name, text in variants.items():
            with self.subTest(name):
                self.story.write_text(text, encoding="utf-8")
                before = self.story.read_bytes()
                work = self.work()
                self.assertFalse(work["complete"], f"{name}：状态说阅读已完成")
                self.assertTrue(work["next"], f"{name}：没给下一动作")
                for mode in ("mermaid", "svg", "toggle"):
                    self.assertEqual(1, self.view(mode).returncode, f"{name}：view {mode} 没拒绝坏块")
                self.assertEqual(1, self.build("number").returncode, f"{name}：正式命令带着坏块照常执行")
                self.assertEqual(before, self.story.read_bytes(), f"{name}：坏块时写了 story")
                self.assertEqual("pending", self.device_reading()["state"], f"{name}：装置把坏块读成完成")
        self.story.write_text(good, encoding="utf-8")
        self.src(fid).unlink()
        work = self.work()
        self.assertFalse(work["complete"])
        self.assertIn(f"{fid}.mmd 不在", "；".join(work["problems"]))

    def test_a_clear_no_without_figures_is_not_applicable_anywhere(self) -> None:
        self.story.write_text("# FIG90001 甲需求\n\n## 业务流程\n\n### 提交与回执\n\n没有图。\n", encoding="utf-8")
        self.design(NONE)
        work = self.work()
        self.assertEqual((False, True, None), (work["applicable"], work["complete"], work["next"]))
        got = self.device_reading()
        self.assertEqual("not_applicable", got["state"], got)

    def closed_at(self, rel: str) -> bool:
        sys.path.insert(0, str(CORE))
        from flow import routing  # noqa: PLC0415
        target = self.root / rel / "summary.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"closure_status": "closed"}), encoding="utf-8")
        try:
            return routing.spec_closed(self.fr)
        finally:
            target.unlink()

    def test_spec_closure_is_read_where_the_project_puts_reports(self) -> None:
        config = self.root / "framework.config.json"
        self.assertTrue(self.closed_at(f"doc/features/{FEATURE}/spec/reports"), "默认布局没认出闭环")
        config.write_text(json.dumps({"paths": {"reports_dir_pattern": "audit/<feature>/<phase>"}}), encoding="utf-8")
        self.assertTrue(self.closed_at(f"audit/{FEATURE}/spec"), "自定义 reports_dir_pattern 没认出闭环")
        self.assertFalse(self.closed_at(f"doc/features/{FEATURE}/spec/reports"), "配置了别处却去读默认位置")
        sys.path.insert(0, str(CORE))
        from flow import routing, state  # noqa: PLC0415
        broken = self.root / "audit" / FEATURE / "spec" / "summary.json"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("{ 坏了", encoding="utf-8")
        with self.assertRaises(state.FlowError):
            routing.spec_closed(self.fr)
        broken.write_text(json.dumps({"closure_status": "open"}), encoding="utf-8")
        self.assertFalse(routing.spec_closed(self.fr), "没闭环判成闭环")

    def test_the_report_check_reads_the_configured_place(self) -> None:
        """交付门的报告核对与路由同一处取 summary：自定义布局下找得到，坏 summary 说读不出。"""
        (self.root / "framework.config.json").write_text(
            json.dumps({"paths": {"reports_dir_pattern": "audit/<feature>/<phase>"}}), encoding="utf-8")
        driver = ("const m = await import(process.argv[1]);"
                  "process.stdout.write(JSON.stringify(m.reportCheck(process.argv[2], process.argv[3], 'spec')));")
        mod = DEV_EXT / "hooks" / "shared" / "verifier-report.mjs"

        def check() -> dict:
            proc = subprocess.run(["node", "--input-type=module", "-e", driver, mod.as_uri(), str(self.root), FEATURE],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, proc.returncode, proc.stderr)
            return json.loads(proc.stdout)
        self.assertIn(f"audit/{FEATURE}/spec/summary.json 不在", check()["problems"][0])
        summary = self.root / "audit" / FEATURE / "spec" / "summary.json"
        summary.parent.mkdir(parents=True)
        summary.write_text(json.dumps({"phase": "spec", "verdict": "PASS"}), encoding="utf-8")
        self.assertEqual("NOT_REVIEWED", check()["status"], "自定义位置的 summary 没被读到")
        summary.write_text("{ 坏了", encoding="utf-8")
        got = check()
        self.assertEqual("ERROR", got["status"])
        self.assertIn("读不出", got["problems"][0])


if __name__ == "__main__":
    unittest.main()
