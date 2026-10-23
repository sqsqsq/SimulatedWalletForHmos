"""story 里由脚本管理的正式图：一张图一个 ID，`.mmd` 是唯一真源，同一块里在 Mermaid 与同 ID 的增强 SVG 之间切换。

锁的是视图合同：正式图源的建立、按源重铺与坏块零写入；一块一次只放一种形态，块外正文一个字节不动；
没有正式图就不适用，有图时逐张列增强进度；验收请求只绑图源、SVG 与本地资源，任一变化让这一张过期，
别的章节、编号、分隔空行与显隐不让它过期；旧版补充阅读槽与旧补充图报告不被当成本版对象；
正式入口（story-build 其它命令、阶段钩子、预检、story_flow）先回到 Mermaid，结束或失败后恢复可用的 SVG。
SVG 与源对不对、好不好读不在这里——那是独立审查的事。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
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
SEQ_SRC = "sequenceDiagram\n  用户->>钱包: 申请退款\n  钱包->>云侧: 提交退款\n  云侧-->>钱包: 受理结果\n  钱包-->>用户: 展示结果\n"
PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
SUBMIT = ("### 提交与回执\n\n看这张图要看出受理失败去哪。\n\n```mermaid\n" + FLOW_SRC + "```\n\n图后：回执超时由服务端重试。\n\n"
          "| 情形 | 去向 |\n|---|---|\n| 受理失败 | 提示重试 |\n\n")
REST = "### 取消\n\n取消后退款。\n\n## 异常与恢复\n\n### 共同恢复规则\n\n本地记录清掉后按远端事实恢复。\n"
STORY = "# FIG90001 甲需求\n\n## 业务流程\n\n" + SUBMIT + REST
#: 两种题材：流程与时序各一张
TWO = STORY.replace("取消后退款。\n", "取消后退款。\n\n```mermaid\n" + SEQ_SRC + "```\n")


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
        link_harness_yaml(self.root)

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

    def ids(self) -> list[str]:
        """story 里正式图块的 ID，按出现顺序。"""
        text = self.text()
        return [line.split(":")[1] for line in text.splitlines() if line.startswith("<!-- story-figure:") and line.endswith(":begin -->")]

    def fig_id(self, src: str = FLOW_SRC) -> str:
        return next(p.stem for p in self.fr.glob("AR/story-src/figures/*.mmd") if p.read_text(encoding="utf-8") == src)

    def block(self, fid: str | None = None) -> list[str]:
        """图块里的形态行（去掉标记与内侧分隔空行）。"""
        fid = fid or self.fig_id()
        text = self.text()
        begin, end = f"<!-- story-figure:{fid}:begin -->", f"<!-- story-figure:{fid}:end -->"
        return [l for l in text[text.index(begin) + len(begin):text.index(end)].splitlines() if l.strip()]

    def shown(self, fid: str | None = None) -> bool:
        fid = fid or self.fig_id()
        return self.block(fid) == [f"![{fid}](figures/{fid}.svg)"]

    def src(self, fid: str) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd"

    def reading(self, fid: str | None = None) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid or self.fig_id()}.reading"

    def work(self) -> dict:
        return json.loads(self.view("status").stdout)

    def item(self, fid: str | None = None) -> dict:
        fid = fid or self.fig_id()
        return next(i for i in self.work()["items"] if i["id"] == fid)

    def state(self, fid: str | None = None) -> str:
        return self.item(fid)["state"]

    def put_svg(self, fid: str | None = None, text: str | None = None) -> Path:
        path = self.fr / "AR" / "figures" / f"{fid or self.fig_id()}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else svg(), encoding="utf-8")
        return path

    def make_ready(self, fid: str | None = None, verdict: str = "PASS", **report: object) -> dict:
        """走完验收：生成请求、放一份独立审查报告（替身，只为绑定与结论自洽）。"""
        fid = fid or self.fig_id()
        self.ok("review-request", "--id", fid)
        request = json.loads((self.reading(fid) / "request.json").read_text(encoding="utf-8"))
        body = {"request_id": request["request_id"], "executor": "subagent-7",
                "checks": [{"id": c, "verdict": verdict, "evidence": f"核过 {c}"} for c in request["checks"]],
                "blocking_findings": [], "advisories": [], "unreviewed": [], **report}
        (self.reading(fid) / "report.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return request

    def ready(self, fid: str | None = None) -> None:
        self.ok("prepare")
        fid = fid or self.fig_id()
        self.put_svg(fid)
        self.make_ready(fid)
        self.assertEqual("ready", self.state(fid))


class OneFigureTwoForms(FigureViewCase):
    def test_no_figure_is_not_applicable_and_the_views_change_nothing(self) -> None:
        self.story.write_text(STORY.replace("```mermaid\n" + FLOW_SRC + "```\n\n", ""), encoding="utf-8")
        self.ok("prepare")
        self.assertEqual({"applicable": False, "complete": True, "items": [], "problems": [], "next": None}, self.work())
        before = self.story.read_bytes()
        for mode in ("svg", "mermaid"):
            self.ok(mode)
        self.assertIn("不需要 SVG", self.ok("toggle").stdout)
        self.assertEqual(before, self.story.read_bytes(), "没有图时视图改了 story")
        self.assertFalse((self.fr / "AR" / "figures").exists())

    def test_every_figure_is_work_until_its_svg_is_reviewed(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        work = self.work()
        self.assertEqual((True, False), (work["applicable"], work["complete"]))
        self.assertEqual([(fid, "no-svg")], [(i["id"], i["state"]) for i in work["items"]])
        self.assertIn(f"{fid}.mmd 制作", work["next"], "没指向同 ID 的图源")
        self.put_svg()
        self.assertEqual("no-request", self.state())
        self.make_ready()
        work = self.work()
        self.assertEqual((True, None), (work["complete"], work["next"]))

    def test_svg_replaces_mermaid_in_the_same_block_and_comes_back_byte_for_byte(self) -> None:
        self.ready()
        fid = self.fig_id()
        formal = self.text()
        proc = self.ok("svg")
        self.assertIn("其中显示增强 SVG 的 1 张", proc.stdout)
        self.assertTrue(self.shown(), "SVG 没有放进原图块")
        self.assertNotIn("```mermaid", self.text(), "两种形态同时出现")
        outside = lambda t: t[:t.index(f"<!-- story-figure:{fid}:begin -->")] + t[t.index(f"<!-- story-figure:{fid}:end -->"):]  # noqa: E731
        self.assertEqual(outside(formal), outside(self.text()), "切换动了块外正文")
        self.ok("mermaid")
        self.assertEqual(formal, self.text(), "收回后不是原来的 Mermaid")
        self.ok("toggle")
        self.assertTrue(self.shown())
        self.ok("toggle")
        self.assertEqual(formal, self.text())

    def test_flow_and_sequence_figures_are_handled_one_by_one(self) -> None:
        self.story.write_text(TWO, encoding="utf-8")
        self.ok("prepare")
        flow, seq = self.fig_id(FLOW_SRC), self.fig_id(SEQ_SRC)
        self.assertEqual([flow, seq], self.ids())
        self.put_svg(seq)
        self.make_ready(seq)
        proc = self.ok("svg")
        self.assertTrue(self.shown(seq))
        self.assertEqual("```mermaid", self.block(flow)[0], "没审过的图也换成了 SVG")
        self.assertIn(f"{flow}：还没有增强阅读图", proc.stdout, "没说清哪张为什么没显示")
        work = self.work()
        self.assertEqual((False, {flow: "no-svg", seq: "ready"}), (work["complete"], {i["id"]: i["state"] for i in work["items"]}))
        self.ok("mermaid", "--id", seq)
        self.assertEqual("```mermaid", self.block(seq)[0], "--id 只收回这一张")
        self.ok("svg", "--id", seq)
        self.assertTrue(self.shown(seq))

    def test_a_reference_to_another_figure_is_a_broken_block(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        text = self.text()
        begin, end = f"<!-- story-figure:{fid}:begin -->", f"<!-- story-figure:{fid}:end -->"
        self.story.write_text(text[:text.index(begin) + len(begin)] + "\n\n![别的图](figures/other.svg)\n\n" + text[text.index(end):],
                              encoding="utf-8")
        before = self.story.read_bytes()
        for mode in ("mermaid", "svg"):
            with self.subTest(mode):
                proc = self.view(mode)
                self.assertEqual(1, proc.returncode)
                self.assertIn(f"不是 ![{fid}](figures/{fid}.svg) 这一行", proc.stderr)
        self.assertEqual(before, self.story.read_bytes())
        self.ok("prepare", "--id", fid)
        self.assertEqual("```mermaid", self.block()[0])


class EvidenceFollowsTheFigure(FigureViewCase):
    def test_the_request_binds_only_the_source_the_svg_and_its_resources(self) -> None:
        self.ready()
        fid = self.fig_id()
        request = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))
        self.assertEqual((1, "story-figure-svg/1"), (request["version"], request["method"]))
        self.assertEqual(["semantic_fidelity", "reading_quality"], request["checks"])
        self.assertEqual({"source", "svg", "resources"}, set(request["inputs"]), "请求还绑着章节、依据或放置")
        self.assertEqual(f"AR/story-src/figures/{fid}.mmd", request["inputs"]["source"]["path"])
        self.assertEqual(f"AR/figures/{fid}.svg", request["inputs"]["svg"]["path"])
        out = self.ok("review-request", "--id", fid).stdout
        lines = out.splitlines()
        reviewer = "\n".join(lines[lines.index("【交给审查者】") + 1:lines.index("【作者收尾】")])
        self.assertIn(FLOW_SRC.strip(), reviewer, "任务里没有图源原文")
        for needle in ("方向错", "漏异常", "把动作画成状态变化", "不以「与 Mermaid 重复」拒绝", "重叠"):
            self.assertIn(needle, reviewer, f"审查要点缺「{needle}」")
        self.assertNotIn("review-check", reviewer, "让只读审查者去跑核对命令")
        self.assertNotIn("reading_gain", out)
        self.assertNotIn("placement", out)

    def test_only_the_figure_itself_makes_it_stale(self) -> None:
        self.ready()
        fid = self.fig_id()
        story = self.story.read_bytes()
        source = self.src(fid).read_bytes()
        changes = {
            "SVG": (lambda: self.put_svg(fid, svg("<text>多一句</text>")), lambda: self.put_svg(fid)),
            "图源": (lambda: self.src(fid).write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8"),
                   lambda: self.src(fid).write_bytes(source)),
        }
        for name, (change, undo) in changes.items():
            with self.subTest(name):
                change()
                item = self.item(fid)
                self.assertEqual("stale", item["state"], f"{name}变了，旧验收照样成立")
                self.assertIn("生成新请求，交独立审查", item["reason"])
                undo()
                self.assertEqual("ready", self.state(fid))
        unrelated = {
            "别的章节": lambda: self.edit("取消后退款。", "取消后原路退款。"),
            "放置小节的正文": lambda: self.edit("图后：", "图后（改了）："),
            "分隔空行": lambda: self.edit(f"<!-- story-figure:{fid}:begin -->\n\n", f"<!-- story-figure:{fid}:begin -->\n"),
            "标题编号": lambda: self.edit("### 提交与回执", "### 5.1 提交与回执"),
        }
        for name, change in unrelated.items():
            with self.subTest(name):
                change()
                self.assertEqual("ready", self.state(), f"{name}变了，验收被误判过期")
                self.story.write_bytes(story)
        for mode in ("svg", "mermaid", "svg", "mermaid"):
            self.ok(mode)
        self.assertEqual("ready", self.state(), "显隐让验收过期")
        (self.reading() / "render.png").write_bytes(PNG + b"left over")
        self.assertEqual("ready", self.state(), "遗留的渲染图参与了验收")

    def test_each_change_names_the_smallest_recovery(self) -> None:
        self.ready()
        before = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))["request_id"]
        self.put_svg(text=svg("<text>多一句</text>"))
        self.ok("review-request", "--id", self.fig_id())
        after = json.loads((self.reading() / "request.json").read_text(encoding="utf-8"))["request_id"]
        self.assertNotEqual(before, after, "SVG 变了却没换请求")
        item = self.item()
        self.assertEqual("invalid", item["state"], "旧报告被当成新请求的结论")
        self.assertIn("不重建输入", item["reason"])
        (self.reading() / "report.json").unlink()
        item = self.item()
        self.assertEqual("no-report", item["state"])
        self.assertIn("请求不变", item["reason"])
        self.make_ready()
        self.assertEqual("ready", self.state())
        self.make_ready(verdict="FAIL")
        reason = self.item()["reason"]
        self.assertIn("按意见改 SVG", reason)
        self.assertIn("改 .mmd", reason, "要改图义时没指回图源")

    def test_reports_that_do_not_complete_the_review_are_not_usable(self) -> None:
        self.ready()
        fid = self.fig_id()
        cases = {
            "FAIL": ({}, "FAIL", "failed"),
            "UNKNOWN": ({}, "UNKNOWN", "incomplete"),
            "非法值": ({}, "OK", "invalid"),
            "阻断项": ({"blocking_findings": ["时序方向反了"]}, "PASS", "failed"),
            "未核": ({"unreviewed": ["关键状态名只在嵌入位图里"]}, "PASS", "incomplete"),
            "没有执行引用": ({"executor": ""}, "PASS", "invalid"),
        }
        for name, (extra, verdict, want) in cases.items():
            with self.subTest(name):
                self.make_ready(verdict=verdict, **extra)
                self.assertEqual(want, self.state())
                self.assertEqual(1, self.view("review-check", "--id", fid).returncode)
        self.make_ready()
        report = json.loads((self.reading() / "report.json").read_text(encoding="utf-8"))
        report["checks"] = [c for c in report["checks"] if c["id"] != "reading_quality"]
        (self.reading() / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("incomplete", self.state(), "缺可读性结论也收了")
        report["checks"].append({"id": "reading_gain", "verdict": "PASS", "evidence": "旧补充图的增益项"})
        (self.reading() / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("invalid", self.state(), "旧补充图的必核项被当成本版结论")

    def test_an_old_supplementary_request_or_an_edited_request_is_refused(self) -> None:
        self.ready()
        req_file = self.reading() / "request.json"
        req = json.loads(req_file.read_text(encoding="utf-8"))
        req_file.write_text(json.dumps({**req, "version": 3, "method": "story-reading-review/3"}), encoding="utf-8")
        self.assertEqual("invalid", self.state())
        reason = self.item()["reason"]
        self.assertIn("story-figure-svg/1", reason)
        self.assertIn("旧补充图的请求与报告不能当这张图的验收", reason)
        for name, change in (("改 ID", lambda r: r.update(id="other")),
                             ("改图源路径", lambda r: r["inputs"]["source"].update(path="AR/story-src/figures/x.mmd")),
                             ("删必核项", lambda r: r.update(checks=r["checks"][:1]))):
            with self.subTest(name):
                bad = json.loads(json.dumps(req))
                change(bad)
                req_file.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual("invalid", self.state())
        req_file.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
        self.assertEqual("ready", self.state())
        proc = self.view("review-request", "--id", self.fig_id(), "--render", str(self.root / "shot.png"))
        self.assertEqual(1, proc.returncode)
        self.assertIn("不认识的选项 --render", proc.stderr)

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

    def test_review_only_accepts_figures_in_the_story(self) -> None:
        self.ready()
        self.put_svg("other")
        for mode in ("review-request", "review-check"):
            with self.subTest(mode):
                proc = self.view(mode, "--id", "other")
                self.assertEqual(1, proc.returncode)
                self.assertIn("没有 ID 为 other 的正式图块", proc.stderr)


class TheMarksStandApart(FigureViewCase):
    """正式图块的标记与内容各隔一个空行（B4）；切换只动块里那一行，不累积空行。"""

    def test_show_and_hide_cycles_change_only_the_block_and_keep_the_evidence(self) -> None:
        self.ready()
        fid = self.fig_id()
        formal = self.text()
        self.assertIn(f"去哪。\n\n<!-- story-figure:{fid}:begin -->\n\n```mermaid\n", formal)
        self.assertIn(f"```\n\n<!-- story-figure:{fid}:end -->\n\n图后", formal)
        shown = None
        for _ in range(3):
            self.ok("svg")
            shown = shown or self.text()
            self.assertEqual(shown, self.text(), "再显示一次又改了 story")
            self.ok("mermaid")
            self.assertEqual(formal, self.text(), "收回后没回到正式形态")
        self.assertIn(f"<!-- story-figure:{fid}:begin -->\n\n![{fid}](figures/{fid}.svg)\n\n<!-- story-figure:{fid}:end -->\n\n图后", shown)
        for _ in range(2):
            self.ok("prepare")
            self.assertEqual(formal, self.text(), "重跑 prepare 改了已就位的 story")
        self.assertNotIn("\n\n\n", formal + shown)
        self.assertEqual("ready", self.state(), "格式与显隐让验收失效")

    def test_an_old_tight_block_is_still_a_block_and_prepare_spaces_it_once(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        canon = self.text()
        tight = (canon.replace(f"<!-- story-figure:{fid}:begin -->\n\n", f"<!-- story-figure:{fid}:begin -->\n")
                 .replace(f"\n\n<!-- story-figure:{fid}:end -->", f"\n<!-- story-figure:{fid}:end -->"))
        self.assertNotEqual(canon, tight)
        self.story.write_bytes(tight.encode("utf-8"))
        self.assertFalse(self.work()["problems"], "紧贴的旧图块被当成坏块")
        self.ok("mermaid")
        self.assertEqual(tight.encode("utf-8"), self.story.read_bytes(), "正式入口无可改时重排了旧稿（只读命令会写盘）")
        self.ok("prepare")
        self.assertEqual(canon, self.text())


class SeparateMarksIsLocal(unittest.TestCase):
    """`separateMarks` 只在标记缺空行处补一行：首尾位置、标题、表格、连续块、围栏里的样例各按规矩。"""

    def run_it(self, lines: list[str]) -> list[str]:
        doc = (CORE / "story" / "document.mjs").as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e",
                               f"import {{ separateMarks }} from {json.dumps(doc)};"
                               "process.stdout.write(JSON.stringify(separateMarks(JSON.parse(process.argv[1]))));",
                               json.dumps(lines, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_each_neighbour_gets_one_blank_line_and_reruns_change_nothing(self) -> None:
        fb, fe = "<!-- story-figure:f:begin -->", "<!-- story-figure:f:end -->"
        gb, ge = "<!-- story-figure:g:begin -->", "<!-- story-figure:g:end -->"
        zb, ze = "<!-- story-build:begin 规约 · 由x生成 · sha256:0 -->", "<!-- story-build:end -->"
        cases = {
            "文件开头的图块、紧接章标题": (
                [fb, "![f](figures/f.svg)", fe, "## 下一章"], [fb, "", "![f](figures/f.svg)", "", fe, "", "## 下一章"]),
            "标题下两块相连": (
                ["### 节", fb, "```mermaid", "A-->B", "```", fe, gb, "![g](figures/g.svg)", ge],
                ["### 节", "", fb, "", "```mermaid", "A-->B", "```", "", fe, "", gb, "", "![g](figures/g.svg)", "", ge]),
            "表格与段落两侧": (
                ["| a |", "|---|", zb, "| x |", "|---|", ze, "图后一句。"],
                ["| a |", "|---|", "", zb, "", "| x |", "|---|", "", ze, "", "图后一句。"]),
            "已有空行不再加": (
                ["段落。", "", fb, "", "```mermaid", "X", "```", "", fe, "", "  ", "下一段。"],
                ["段落。", "", fb, "", "```mermaid", "X", "```", "", fe, "", "  ", "下一段。"]),
            "围栏里的样例标记不碰": (
                ["```text", fb, "```", "正文。"], ["```text", fb, "```", "正文。"]),
        }
        for name, (given, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(want, self.run_it(given))
                self.assertEqual(want, self.run_it(want), "第二遍又改了")


class OldReadingSlotsAreRefused(FigureViewCase):
    """旧版补充阅读槽不是本版对象：各入口拒绝、零写入，并给出旧版收口或 init 重起的去向。"""

    SLOT = "<!-- story-reading:recovery:begin -->\n<!-- story-reading:recovery:end -->\n\n"

    def test_a_story_with_an_old_slot_writes_nothing_and_says_where_to_go(self) -> None:
        self.ok("prepare")
        self.edit("### 取消\n", self.SLOT + "### 取消\n")
        before = self.story.read_bytes()
        work = self.work()
        self.assertFalse(work["complete"])
        self.assertIn("旧版的补充阅读槽", "；".join(work["problems"]))
        for mode in ("prepare", "mermaid", "svg", "toggle"):
            with self.subTest(mode):
                proc = self.view(mode)
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn("旧版收口，或从 init 重起", proc.stderr)
        self.assertEqual(1, self.build("number").returncode, "带着旧阅读槽的 story 照常进了正式命令")
        self.assertEqual(before, self.story.read_bytes())

    def test_a_stray_reading_link_blocks_check_and_a_registered_image_does_not(self) -> None:
        self.ready()
        fid = self.fig_id()
        (self.fr / "AR" / "story-src" / "decisions.json").write_text(json.dumps({"decisions": []}), encoding="utf-8")
        (self.fr / "AR" / "story-src" / "story-template.md").write_text(
            "# 写作设计\n\n## 阅读主线\n\n先讲提交。\n\n## 骨架\n\n### 05-flow\n\n#### 提交与回执\n- 答：受理失败去哪\n", encoding="utf-8")
        (self.fr / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"origins": [{"path": "AR/figures/shot.png"}]}), encoding="utf-8")
        self.edit("取消后退款。", f"取消后退款。\n\n![旧图](figures/{fid}.svg)\n\n![截图](figures/shot.png)\n\n[旧链接]: figures/old.svg")
        shutil.copytree(DEV_EXT, self.root / "doc" / "extensions", ignore=shutil.ignore_patterns("__pycache__"))
        self.ok("svg")
        proc = self.build("check")
        self.assertEqual(1, proc.returncode)
        self.assertIn(f"正式图块之外引用了本地阅读资产 AR/figures/{fid}.svg", proc.stderr)
        self.assertIn("AR/figures/old.svg", proc.stderr, "引用式定义漏检")
        self.assertNotIn("本地阅读资产 AR/figures/shot.png", proc.stderr, "登记过的原始材料图片被误拦")
        self.assertEqual(1, proc.stderr.count(f"本地阅读资产 AR/figures/{fid}.svg"), "块里的 SVG 也被当成了块外引用")
        self.assertTrue(self.shown(), "check 之后没有恢复 SVG")


class TheFormalFormIsMermaid(FigureViewCase):
    def test_hooks_and_preflight_bring_back_mermaid(self) -> None:
        self.ready()
        self.ok("svg")
        hook = DEV_EXT / "hooks" / "shared" / "story-view.mjs"
        driver = ("const h = (await import(process.argv[1])).default;"
                  "process.stdout.write(JSON.stringify(await h({phase:'spec', feature: process.argv[2], projectRoot: process.argv[3]})));")
        got = json.loads(subprocess.run(["node", "--input-type=module", "-e", driver, hook.as_uri(), FEATURE, str(self.root)],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout)
        self.assertEqual({"ok": True}, got)
        self.assertFalse(self.shown(), "阶段钩子没有收回 Mermaid")
        self.assertNotIn("figures/", self.text())
        self.ok("svg")
        pre = DEV_EXT / "hooks" / "shared" / "pre_verifier.mjs"
        driver = ("const h = (await import(process.argv[1])).default;"
                  "process.stdout.write(JSON.stringify(await h({feature: process.argv[2], projectRoot: process.argv[3]})));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver, pre.as_uri(), FEATURE, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertFalse(self.shown(), "预检没有收回 Mermaid")

    def test_formal_commands_bring_back_mermaid_then_restore_and_keep_their_exit_code(self) -> None:
        self.ready()
        self.ok("svg")
        proc = self.build("number")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("已恢复 1 张图的增强 SVG", proc.stderr)
        self.assertTrue(self.shown(), "成功之后没有恢复 SVG")
        proc = self.build("check")
        self.assertEqual(1, proc.returncode, "业务失败被视图恢复盖掉了")
        self.assertTrue(self.shown(), "失败之后没有恢复 SVG")

    def test_partly_ready_shows_only_what_is_ready_in_one_line(self) -> None:
        self.story.write_text(TWO, encoding="utf-8")
        self.ok("prepare")
        flow, seq = self.fig_id(FLOW_SRC), self.fig_id(SEQ_SRC)
        self.put_svg(flow)
        self.make_ready(flow)
        self.ok("svg")
        proc = self.build("number")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(f"1 张图保持 Mermaid（增强 SVG 未就绪，业务结果不受影响）：{seq}", proc.stderr)
        self.assertTrue(self.shown(flow))
        self.assertEqual("```mermaid", self.block(seq)[0])

    def test_the_flow_reader_restores_and_an_internal_query_does_not(self) -> None:
        self.ready()
        client = CORE / "flow" / "client.mjs"
        driver = ("const m = await import(process.argv[1]);"
                  "const r = m.queryFlowStatus(process.argv[2], process.argv[3], { timeoutMs: 120000 });"
                  "process.stdout.write(JSON.stringify({ error: r.error }));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver, client.as_uri(), str(self.root), FEATURE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertFalse(self.shown(), "内部查询把正式读取的 story 换成了阅读形态")
        proc = subprocess.run([sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertIn("view", out, "story_flow 没有交回视图的去向")
        self.assertTrue(self.shown(), "用户直接跑 status 没恢复 SVG")

    def test_the_business_step_leads_and_the_unfinished_enhancement_is_listed_aside(self) -> None:
        """spec 闭环后、归档后增强 SVG 没完成：下一步仍是业务动作（交付门 / 已归档），阅读待办另列、不当主动作。"""
        self.ok("prepare")
        fid = self.fig_id()
        sys.path.insert(0, str(CORE))
        from flow import routing, state  # noqa: PLC0415
        contract = {"rounds": [{"round": 1}], "status": "story_written",
                    "story_digests": {rel: state.ledger_digest(self.fr / rel) for rel in state.STORY_REGISTERED}}
        reports = self.fr / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(json.dumps({"closure_status": "closed"}), encoding="utf-8")
        step, action = routing.next_step(self.fr, contract)
        self.assertEqual("run_archived", step, "阅读待办顶替了业务下一动作")
        self.assertTrue(action.startswith("spec 阶段已闭环：跑 `story-build check --deliver` 交付门"), action)
        self.assertIn("本地阅读另列", action)
        self.assertIn(fid, action, "图还没有增强 SVG 却没说")
        archived = {**contract, "archived": {"at": "2026-10-21T00:00:00+00:00"}}
        step, action = routing.next_step(self.fr, archived)
        self.assertEqual("done", step)
        self.assertIn("本地阅读另列", action)
        self.put_svg()
        self.make_ready()
        self.ok("svg")
        self.ok("mermaid")
        step, action = routing.next_step(self.fr, contract)
        self.assertEqual("run_archived", step)
        self.assertNotIn("本地阅读", action, "增强完成后还挂着阅读待办")

    def test_an_outer_owner_switches_once_and_nested_calls_do_not_switch_again(self) -> None:
        """外层持有同一需求的视图时，嵌套的 story-build 与 story_flow 不再切入、也不恢复；没有外层的独立调用照常切入。"""
        self.ready()
        self.ok("svg")
        fid = self.fig_id()
        shown = self.story.read_bytes()
        env = {**os.environ, "STORY_VIEW_OWNER": os.path.realpath(self.fr).lower()}
        nested = [["node", str(BUILD), "check", "--feature", FEATURE, "--project-root", str(self.root)],
                  [sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)]]
        for argv in nested:
            with self.subTest(argv[1]):
                proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=180, env=env)
                self.assertEqual(shown, self.story.read_bytes(), f"{Path(argv[1]).name} 在外层持有时又切了一次")
                self.assertNotIn("已恢复", proc.stderr, "嵌套调用自己恢复了 SVG")
        self.ok("mermaid")
        self.edit("D[提示重试]", "D[提示稍后重试]")       # 正文块与源不同：切入正式形态就会按源重铺
        self.build("check")
        self.assertNotIn("D[提示稍后重试]", self.text(), "独立调用没有先回到正式形态")
        self.assertEqual(FLOW_SRC, self.src(fid).read_text(encoding="utf-8"), "切换把正文改动写回了源")
        self.assertTrue(self.shown(), "独立调用结束没有恢复 SVG")

class TheReadingTodoNeverHidesAProblem(unittest.TestCase):
    def test_only_a_consistent_finish_is_done(self) -> None:
        sys.path.insert(0, str(CORE))
        from flow import routing  # noqa: PLC0415
        base = {"items": [], "next": None}
        self.assertIsNone(routing.reading_todo({**base, "applicable": False, "complete": True, "problems": []}))
        masked = routing.reading_todo({**base, "applicable": False, "complete": False, "problems": ["图块结构坏了"]})
        self.assertIn("图块结构坏了", masked, "不适用掩盖了坏结构")
        self.assertIn("自相矛盾", routing.reading_todo({**base, "applicable": True, "complete": True, "problems": ["图块坏了"]}))
        self.assertIn("读不出", routing.reading_todo({"complete": True}))


class TheSourceOwnsTheMeaning(FigureViewCase):
    """`.mmd` 是唯一真源，正文块只按它派生（R01）：改源能刷新，重建不回退源，手改块按源恢复并说明。"""

    def test_prepare_wraps_the_figure_writes_its_source_and_is_idempotent(self) -> None:
        self.ok("prepare")
        fid = self.fig_id()
        self.assertIn(f"\n\n<!-- story-figure:{fid}:begin -->\n\n```mermaid\n{FLOW_SRC}```\n\n<!-- story-figure:{fid}:end -->\n\n", self.text())
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
        self.edit(f"```\n\n<!-- story-figure:{fid}:end -->",
                  f"```\n受理失败三次转人工。\n```mermaid\nflowchart TD\n  X --> Y\n```\n\n<!-- story-figure:{fid}:end -->")
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
        self.assertIn("与正式图 ID fig-b 不一致", renamed.stdout)


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
        build = ext / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
        run = lambda *a: subprocess.run(["node", str(build), "view", *a, "--feature", FEATURE, "--project-root", str(project)],  # noqa: E731
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, run("--mode", "prepare").returncode)
        fid = next(fr.glob("AR/story-src/figures/*.mmd")).stem
        (fr / "AR" / "figures").mkdir(parents=True)
        (fr / "AR" / "figures" / f"{fid}.svg").write_text(svg(), encoding="utf-8")
        out = run("--mode", "review-request", "--id", fid)
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
                self.assertIn("的增强 SVG 验收没有成立（no-report）", said, "核对命令没到达正确的入口")


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
        self.assertIn("还没有增强阅读图", said)


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

    def test_a_story_without_figures_is_not_applicable_anywhere(self) -> None:
        self.story.write_text("# FIG90001 甲需求\n\n## 业务流程\n\n### 提交与回执\n\n没有图。\n", encoding="utf-8")
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
