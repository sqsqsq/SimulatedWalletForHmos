"""story 里的图：Mermaid 是唯一语义真源，SVG 是本地阅读视图 —— 一份文档两种形态。

锁的是切换合同：准备与双向切换精确、幂等；块外正文一个字节不动；管理块坏了整次不写并点名；
没有阅读图、快照过期、结构不过的块保持 Mermaid；正式入口（story-build 其它命令、阶段 pre_phase、
story_flow 读 story 的动作）先切回 Mermaid。语义等值不在这里——那是对照审的事。
"""
from __future__ import annotations

import json
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
PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
STORY = ("# FIG90001 甲需求\n\n## 业务流程\n\n### 提交与回执\n\n看这张图要看出受理失败去哪。\n\n"
         "```mermaid\n" + FLOW_SRC + "```\n\n图后：回执超时由服务端重试。\n")


def svg(source: str, view_box: str = "0 0 400 200", extra: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">'
            f"<metadata><![CDATA[{source}]]></metadata><text x=\"10\" y=\"20\">提交</text>{extra}</svg>\n")


class FigureViewCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        self.fr = self.root / "doc" / "features" / FEATURE
        (self.fr / "AR").mkdir(parents=True)
        self.story = self.fr / "AR" / "story.md"
        self.story.write_text(STORY, encoding="utf-8")
        link_harness_yaml(self.root)

    def view(self, mode: str, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(BUILD), "view", "--mode", mode, "--feature", FEATURE,
                               "--project-root", str(self.root), *extra],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def prepared_id(self) -> str:
        proc = self.view("prepare")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return next(self.fr.glob("AR/story-src/figures/*.mmd")).stem

    def put_svg(self, fid: str, text: str) -> Path:
        path = self.fr / "AR" / "figures" / f"{fid}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def make_ready(self, fid: str, verdict: str = "PASS", **report: object) -> dict:
        """走完局部阅读验收：存一张渲染图、生成请求、放一份独立审查报告（替身，只为绑定与结论自洽）。"""
        shot = self.root / "shot.png"
        shot.write_bytes(PNG + b"render")
        proc = self.view("review-request", "--id", fid, "--render", str(shot))
        self.assertEqual(0, proc.returncode, proc.stderr)
        reading = self.fr / "AR" / "story-src" / "figures" / f"{fid}.reading"
        request = json.loads((reading / "request.json").read_text(encoding="utf-8"))
        body = {"request_id": request["request_id"], "executor": "subagent-7",
                "checks": [{"id": c, "verdict": verdict, "evidence": f"核过 {c}"} for c in request["checks"]],
                "blocking_findings": [], "advisories": [], "unreviewed": [], **report}
        (reading / "report.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return request


class PrepareAndSwitch(FigureViewCase):
    def test_prepare_wraps_the_figure_and_writes_its_source(self) -> None:
        fid = self.prepared_id()
        text = self.story.read_text(encoding="utf-8")
        self.assertIn(f"<!-- story-figure:{fid}:begin -->\n```mermaid\n{FLOW_SRC}```\n<!-- story-figure:{fid}:end -->", text)
        self.assertEqual(FLOW_SRC, (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").read_text(encoding="utf-8"))
        before = self.story.read_bytes()
        self.assertEqual(0, self.view("prepare").returncode)
        self.assertEqual(before, self.story.read_bytes(), "重跑 prepare 又改了 story")

    def test_svg_and_back_is_exact_and_leaves_the_prose_alone(self) -> None:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.story.write_text(self.story.read_text(encoding="utf-8").replace("图后：", "图后（人改过）："), encoding="utf-8")
        self.make_ready(fid)
        mermaid = self.story.read_bytes()
        proc = self.view("svg")
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.story.read_text(encoding="utf-8")
        self.assertIn(f"](figures/{fid}.svg)", text)
        self.assertNotIn("```mermaid", text)
        self.assertIn("图后（人改过）", text, "块外的人工改动被切换动了")
        once = self.story.read_bytes()
        self.assertEqual(0, self.view("svg").returncode)
        self.assertEqual(once, self.story.read_bytes(), "同一形态重跑不是零改写")
        self.assertEqual(0, self.view("mermaid").returncode)
        self.assertEqual(mermaid, self.story.read_bytes(), "Mermaid→SVG→Mermaid 没有精确还原")

    def test_without_a_ready_view_the_block_stays_mermaid(self) -> None:
        fid = self.prepared_id()
        before = self.story.read_bytes()
        proc = self.view("svg")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("还没有阅读图", proc.stdout)
        self.assertEqual(before, self.story.read_bytes())
        self.put_svg(fid, svg("flowchart TD\n  A --> B"))
        self.assertIn("来源快照", self.view("svg").stdout)
        self.put_svg(fid, svg(FLOW_SRC, view_box="0 0 0 200"))
        self.assertIn("结构检查没过", self.view("svg").stdout)
        self.assertEqual(before, self.story.read_bytes(), "不合格的视图被切了过去")

    def test_a_shown_view_that_breaks_is_rechecked_and_retired(self) -> None:
        """已经显示的阅读图被改坏而来源快照没变：再跑 svg 也要过结构核，不合格就切回 Mermaid。"""
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.make_ready(fid)
        self.assertEqual(0, self.view("svg").returncode)
        self.assertNotIn("```mermaid", self.story.read_text(encoding="utf-8"))
        self.put_svg(fid, svg(FLOW_SRC, view_box="0 0 0 200"))
        proc = self.view("svg")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"), "改坏的阅读图仍在显示")
        self.assertIn("结构检查没过", proc.stdout)

    def test_a_changed_source_retires_the_old_view(self) -> None:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.assertEqual(0, self.view("svg").returncode)
        src = self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd"
        src.write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8")
        proc = self.view("svg")
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.story.read_text(encoding="utf-8")
        self.assertIn("转人工", text, "源改了，旧视图仍在当默认阅读图")
        self.assertIn("来源快照", proc.stdout)
        self.assertIn("与当前源不同", proc.stdout)


class TheSourceOwnsTheMeaning(FigureViewCase):
    """`.mmd` 是唯一真源，正文块只按它派生（R01）：改源两种形态都能刷新，重建不回退源，手改块按源恢复并说明。"""

    def src(self, fid: str) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd"

    def test_a_source_edit_reaches_the_mermaid_block(self) -> None:
        fid = self.prepared_id()
        self.src(fid).write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8")
        proc = self.view("mermaid")
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.story.read_text(encoding="utf-8")
        self.assertIn("转人工", text)
        self.assertNotIn("提示重试", text)
        self.assertIn("已按源刷新", proc.stdout)
        self.assertIn("图后：回执超时由服务端重试。", text, "块外正文被动了")

    def test_a_source_edit_while_showing_svg_comes_back_on_mermaid(self) -> None:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.assertEqual(0, self.view("svg").returncode)
        self.src(fid).write_text(FLOW_SRC.replace("提示重试", "转人工"), encoding="utf-8")
        self.assertEqual(0, self.view("mermaid").returncode)
        self.assertIn("转人工", self.story.read_text(encoding="utf-8"))

    def test_prepare_id_never_puts_the_old_body_back_into_the_source(self) -> None:
        fid = self.prepared_id()
        changed = FLOW_SRC.replace("提示重试", "转人工")
        self.src(fid).write_text(changed, encoding="utf-8")
        self.assertEqual(0, self.view("prepare", "--id", fid).returncode)
        self.assertEqual(changed, self.src(fid).read_text(encoding="utf-8"), "prepare --id 拿正文覆盖了源")
        self.assertIn("转人工", self.story.read_text(encoding="utf-8"))

    def test_a_hand_edited_block_is_restored_from_the_source_with_a_note(self) -> None:
        fid = self.prepared_id()
        self.story.write_text(self.story.read_text(encoding="utf-8").replace("等回执", "等短信"), encoding="utf-8")
        proc = self.view("mermaid")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("等短信", self.story.read_text(encoding="utf-8"))
        self.assertIn(f"{fid}：正文里的图与源", proc.stdout, "差异被静默丢掉了")
        self.assertEqual(FLOW_SRC, self.src(fid).read_text(encoding="utf-8"))

    def test_two_fences_with_prose_between_are_a_broken_block(self) -> None:
        """块里两段围栏夹着业务正文：首尾像一个围栏也不算合法块，自动入口零写入，prepare --id 才从源重建。"""
        fid = self.prepared_id()
        text = self.story.read_text(encoding="utf-8")
        two = (f"<!-- story-figure:{fid}:begin -->\n```mermaid\n{FLOW_SRC}```\n受理失败三次转人工。\n"
               f"```mermaid\nflowchart TD\n  X --> Y\n```\n<!-- story-figure:{fid}:end -->")
        start = text.index(f"<!-- story-figure:{fid}:begin -->")
        end = text.index(f"<!-- story-figure:{fid}:end -->") + len(f"<!-- story-figure:{fid}:end -->")
        self.story.write_text(text[:start] + two + text[end:], encoding="utf-8")
        before = self.story.read_bytes()
        for mode in ("mermaid", "svg"):
            with self.subTest(mode=mode):
                proc = self.view(mode)
                self.assertNotEqual(0, proc.returncode, proc.stdout)
                self.assertIn(f"图块 {fid}", proc.stderr)
                self.assertEqual(before, self.story.read_bytes(), "结构坏的块被自动重铺，块里的正文没了")
        self.assertEqual(0, self.view("prepare", "--id", fid).returncode)
        self.assertNotIn("X --> Y", self.story.read_text(encoding="utf-8"))

    def test_a_stale_block_switched_to_a_ready_view_still_says_so(self) -> None:
        """阅读图按当前源就绪、正文块却还是旧图：照样切到阅读图，但要说出正文差异没保留。"""
        fid = self.prepared_id()
        changed = FLOW_SRC.replace("提示重试", "转人工")
        self.src(fid).write_text(changed, encoding="utf-8")
        self.put_svg(fid, svg(changed))
        self.make_ready(fid)
        proc = self.view("svg")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"))
        self.assertIn(f"{fid}：正文里的图与源", proc.stdout, "阅读图就绪时差异被静默替换")
        self.assertIn("改图义改 .mmd", proc.stdout)
        self.assertEqual(0, self.view("mermaid").returncode)
        self.assertIn("转人工", self.story.read_text(encoding="utf-8"))

    def test_first_prepare_does_not_overwrite_a_different_source_at_the_same_id(self) -> None:
        import hashlib  # noqa: PLC0415
        inner = FLOW_SRC.rstrip("\n")
        fid = f"fig-{hashlib.sha256(inner.encode('utf-8')).hexdigest()[:8]}"
        self.src(fid).parent.mkdir(parents=True, exist_ok=True)
        self.src(fid).write_text("flowchart TD\n  X --> Y\n", encoding="utf-8")
        before = self.story.read_bytes()
        proc = self.view("prepare")
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("不覆盖已有的源", proc.stderr)
        self.assertEqual(before, self.story.read_bytes())
        self.assertEqual("flowchart TD\n  X --> Y\n", self.src(fid).read_text(encoding="utf-8"))


class BrokenBlocksWriteNothing(FigureViewCase):
    def assert_refused(self, mode: str, needle: str) -> None:
        before = self.story.read_bytes()
        proc = self.view(mode)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn(needle, proc.stderr)
        self.assertIn("view --mode prepare --id", proc.stderr, "没给恢复入口")
        self.assertEqual(before, self.story.read_bytes(), "坏块也写了")

    def test_prose_inside_a_block_stops_and_prepare_id_rebuilds_from_the_source(self) -> None:
        """块里夹了正文是结构坏了：自动入口整次不写；边界与源都在时 prepare --id 从源重建，源不动。"""
        fid = self.prepared_id()
        src = (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").read_bytes()
        self.story.write_text(self.story.read_text(encoding="utf-8").replace(
            f"<!-- story-figure:{fid}:end -->", f"夹进来的一句。\n<!-- story-figure:{fid}:end -->"), encoding="utf-8")
        self.assert_refused("mermaid", f"图块 {fid}")
        self.assertEqual(0, self.view("prepare", "--id", fid).returncode)
        self.assertNotIn("夹进来的一句", self.story.read_text(encoding="utf-8"))
        self.assertEqual(src, (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").read_bytes(), "重建改了源")
        self.assertEqual(0, self.view("mermaid").returncode)

    def test_an_orphan_mark_and_a_duplicate_id_are_named(self) -> None:
        self.story.write_text(STORY + "\n<!-- story-figure:lonely:begin -->\n", encoding="utf-8")
        self.assert_refused("mermaid", "没有结束标记")
        fid = None
        self.story.write_text(STORY, encoding="utf-8")
        fid = self.prepared_id()
        text = self.story.read_text(encoding="utf-8")
        block = text[text.index(f"<!-- story-figure:{fid}:begin -->"):text.index(f"<!-- story-figure:{fid}:end -->") + 40]
        self.story.write_text(text + "\n" + block.split("-->", 2)[0] + "-->" + block.split("-->", 1)[1], encoding="utf-8")
        self.assert_refused("svg", "出现了不止一次")

    def test_a_missing_source_is_named(self) -> None:
        fid = self.prepared_id()
        (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").unlink()
        self.assert_refused("mermaid", f"{fid}.mmd 不在")


class FormalEntriesReadMermaid(FigureViewCase):
    def to_svg(self) -> str:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.make_ready(fid)
        self.assertEqual(0, self.view("svg").returncode)
        self.assertNotIn("```mermaid", self.story.read_text(encoding="utf-8"))
        return fid

    def test_other_story_build_commands_switch_back_first(self) -> None:
        """正式命令在 Mermaid 上做事，结束后恢复可用的阅读图；块坏了切不回来就不做事。"""
        fid = self.to_svg()
        proc = subprocess.run(["node", str(BUILD), "number", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("已恢复 1 张可用的本地阅读图", proc.stderr)
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"), "命令结束没有恢复阅读图")
        self.assertEqual(0, self.view("mermaid").returncode)
        self.story.write_text(self.story.read_text(encoding="utf-8").replace(
            f"<!-- story-figure:{fid}:end -->", f"夹进来的一句。\n<!-- story-figure:{fid}:end -->"), encoding="utf-8")
        proc = subprocess.run(["node", str(BUILD), "number", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(1, proc.returncode)
        self.assertIn("切不回来", proc.stderr)

    def test_the_phase_hook_switches_back_and_blocks_on_a_broken_block(self) -> None:
        self.to_svg()
        hook = DEV_EXT / "hooks" / "shared" / "story-view.mjs"
        driver = ("const h = (await import(process.argv[1])).default;"
                  "process.stdout.write(JSON.stringify(await h({phase:'spec', feature: process.argv[2], projectRoot: process.argv[3]})));")
        run = lambda: json.loads(subprocess.run(  # noqa: E731
            ["node", "--input-type=module", "-e", driver, hook.as_uri(), FEATURE, str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout)
        self.assertEqual({"ok": True}, run())
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"))
        fid = next(self.fr.glob("AR/story-src/figures/*.mmd")).stem
        self.story.write_text(self.story.read_text(encoding="utf-8").replace(
            f"<!-- story-figure:{fid}:end -->", f"夹进来的一句。\n<!-- story-figure:{fid}:end -->"), encoding="utf-8")
        got = run()
        self.assertFalse(got["ok"])
        self.assertEqual("BLOCKER", got["severityOverride"])

    def test_the_flow_reader_switches_back(self) -> None:
        """story_flow 读 story 的动作同样由最外层持有视图：结束后恢复，结果里说清视图去向。"""
        fid = self.to_svg()
        proc = subprocess.run([sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        out = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertIn("view", out, "story_flow 没有交回视图的去向")
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"))


class TheStructureCheck(FigureViewCase):
    def check(self, text: str, fid: str = "fig-a") -> subprocess.CompletedProcess:
        path = self.put_svg(fid, text)
        return subprocess.run([sys.executable, str(CHECK), str(path), "--id", fid],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def test_a_valid_view_passes(self) -> None:
        (self.fr / "AR" / "figures" / "fonts").mkdir(parents=True, exist_ok=True)
        (self.fr / "AR" / "figures" / "icon.png").write_bytes(b"PNG")
        (self.fr / "AR" / "figures" / "fonts" / "ui.woff2").write_bytes(b"WOFF")
        extra = ('<image href="icon.png"/><image href="data:image/png;base64,AA=="/>'
                 '<image xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="icon.png"/>'
                 '<style>@font-face{font-family:ui;src:url("fonts/ui.woff2")} .t{font-family:ui}</style>'
                 '<defs><linearGradient id="g"/></defs><rect fill="url(#g)" transform="translate(1 2)" width="5" height="5"/>')
        ok = self.check(svg(FLOW_SRC, extra=extra))
        self.assertEqual(0, ok.returncode, ok.stdout)

    def test_each_structural_fault_is_named(self) -> None:
        cases = {
            "<svg": "不是合法 XML",
            '<g xmlns="http://www.w3.org/2000/svg"/>': "不是 svg",
            '<notsvg viewBox="0 0 1 1"><metadata>x</metadata></notsvg>': "不是 svg",
            '<svg viewBox="0 0 1 1"><metadata>x</metadata></svg>': "缺 SVG 命名空间",
            svg(FLOW_SRC, view_box="0 0 400"): "viewBox",
            svg(FLOW_SRC, view_box="0 0 NaN Infinity"): "四个有限数",
            svg(FLOW_SRC, extra="<style>@font-face{src:url(missing.woff2)}</style>"): "引用「missing.woff2」读不到",
            svg(FLOW_SRC, extra="<style>@import 'theme.css';</style>"): "引用「theme.css」读不到",
            svg(FLOW_SRC, extra='<text style="fill:url(https://cdn.example/p.svg#p)">x</text>'): "不是本地相对路径",
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>': "来源快照",
            svg(FLOW_SRC, extra='<image href="C:/机器/图.png"/>'): "不是本地相对路径",
            svg(FLOW_SRC, extra='<image href="../../../外面.png"/>'): "逃出了 AR/",
            svg(FLOW_SRC, extra='<image href="没有.png"/>'): "读不到",
        }
        for text, needle in cases.items():
            with self.subTest(needle=needle):
                proc = self.check(text)
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn(needle, proc.stdout)
        wrong = self.check(svg(FLOW_SRC), fid="fig-a")
        self.assertEqual(0, wrong.returncode)
        renamed = subprocess.run([sys.executable, str(CHECK), str(self.fr / "AR" / "figures" / "fig-a.svg"), "--id", "fig-b"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertIn("与图块 ID fig-b 不一致", renamed.stdout)


if __name__ == "__main__":
    unittest.main()


class TheLocalReadingContract(FigureViewCase):
    """局部阅读验收：请求绑定源、SVG、本地资源与渲染图的字节，报告绑定请求；任一变化只让这张图的证据失效。"""

    def reading(self, fid: str) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid}.reading"

    def state(self, fid: str) -> str:
        work = json.loads(self.view("status").stdout)
        return next(i["state"] for i in work["items"] if i["id"] == fid)

    def ready_figure(self) -> str:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC, extra='<image href="../assets/icon.png"/>'))
        (self.fr / "AR" / "assets").mkdir(parents=True, exist_ok=True)
        (self.fr / "AR" / "assets" / "icon.png").write_bytes(PNG + b"icon")
        self.make_ready(fid)
        self.assertEqual("ready", self.state(fid))
        return fid

    def test_work_is_derived_from_the_story_itself(self) -> None:
        """普通 Story 的 Mermaid 图自动成为阅读工作；没有图才不适用，有图却没管理不是零项通过。"""
        work = json.loads(self.view("status").stdout)
        self.assertTrue(work["applicable"])
        self.assertFalse(work["complete"])
        self.assertEqual(1, len(work["unmanaged"]), "没管理的图没被列出来")
        self.story.write_text("# FIG90001 甲需求\n\n## 业务流程\n\n只有文字。\n", encoding="utf-8")
        self.assertFalse(json.loads(self.view("status").stdout)["applicable"])

    def test_the_request_is_stable_and_each_input_change_makes_it_stale(self) -> None:
        fid = self.ready_figure()
        request = (self.reading(fid) / "request.json").read_bytes()
        self.assertEqual(0, self.view("review-request", "--id", fid).returncode)
        self.assertEqual(request, (self.reading(fid) / "request.json").read_bytes(), "输入没变请求却重写了")
        icon = self.fr / "AR" / "assets" / "icon.png"
        render = self.reading(fid) / "render.png"
        for name, change, undo in (
            ("资源", lambda: icon.write_bytes(PNG + b"icon2"), lambda: icon.write_bytes(PNG + b"icon")),
            ("渲染图", lambda: render.write_bytes(PNG + b"other"), lambda: render.write_bytes(PNG + b"render")),
        ):
            with self.subTest(name):
                change()
                self.assertEqual("stale", self.state(fid))
                undo()
                self.assertEqual("ready", self.state(fid))
        svg_path = self.fr / "AR" / "figures" / f"{fid}.svg"
        svg_path.write_text(svg_path.read_text(encoding="utf-8").replace(">提交<", ">提交 <"), encoding="utf-8")
        self.assertEqual("stale", self.state(fid), "同源改过的 SVG 还沿用旧报告")
        (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").write_text(FLOW_SRC + "  C --> E[完成]\n", encoding="utf-8")
        self.assertEqual("svg-stale", self.state(fid), "源改了阅读图还当可用")

    def test_reports_that_do_not_complete_the_review_are_not_usable(self) -> None:
        fid = self.ready_figure()
        cases = {
            "FAIL": ({}, "FAIL", "failed"),
            "UNKNOWN": ({}, "UNKNOWN", "incomplete"),
            "非法值": ({}, "OK", "invalid"),
            "阻断项": ({"blocking_findings": ["分支丢了"]}, "PASS", "failed"),
            "未核": ({"unreviewed": ["visual_readability：看不了图"]}, "PASS", "incomplete"),
            "没有执行引用": ({"executor": ""}, "PASS", "invalid"),
        }
        for name, (extra, verdict, want) in cases.items():
            with self.subTest(name):
                self.make_ready(fid, verdict, **extra)
                self.assertEqual(want, self.state(fid))
                self.assertEqual(1, self.view("review-check", "--id", fid).returncode)
        request = self.make_ready(fid)
        report = json.loads((self.reading(fid) / "report.json").read_text(encoding="utf-8"))
        report["checks"].append({"id": "semantic_equivalence", "verdict": "FAIL", "evidence": "又审了一次"})
        (self.reading(fid) / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("invalid", self.state(fid), "同一必核项两个结论没有拒收")
        report["checks"].pop()
        report["request_id"] = "0" * 16
        (self.reading(fid) / "report.json").write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual("invalid", self.state(fid), "审的不是当前请求也收了")
        self.assertNotEqual(request["request_id"], report["request_id"])

    def test_an_unknown_request_contract_and_a_fake_render_are_refused(self) -> None:
        fid = self.ready_figure()
        req = self.reading(fid) / "request.json"
        req.write_text(req.read_text(encoding="utf-8").replace('"version": 1', '"version": 0'), encoding="utf-8")
        self.assertEqual("invalid", self.state(fid))
        fake = self.root / "fake.png"
        fake.write_text("not a png", encoding="utf-8")
        proc = self.view("review-request", "--id", fid, "--render", str(fake))
        self.assertEqual(1, proc.returncode)
        self.assertIn("不是 PNG", proc.stderr)

    def test_toggle_flips_the_whole_story(self) -> None:
        fid = self.ready_figure()
        self.assertEqual(0, self.view("toggle").returncode)
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"))
        self.assertEqual(0, self.view("toggle").returncode)
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"))

    def test_a_failed_formal_command_still_restores_the_view(self) -> None:
        """业务命令失败也在 finally 里恢复可用阅读图，原来的失败照样报出、退出码不变。"""
        fid = self.ready_figure()
        self.assertEqual(0, self.view("svg").returncode)
        proc = subprocess.run(["node", str(BUILD), "check", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"), "失败之后没有恢复阅读图")


class TheOneClickEntry(FigureViewCase):
    """AR 下的一键切换入口：合同登记的唯一文件名，只覆盖自己生成的同名文件，不依赖 cwd 与机器路径。"""

    NAME = "切换视图.cmd"

    def test_prepare_writes_it_once_and_keeps_a_users_file(self) -> None:
        self.prepared_id()
        entry = self.fr / "AR" / self.NAME
        self.assertTrue(entry.is_file())
        body = entry.read_bytes()
        self.assertNotIn(str(self.root).encode("utf-8"), body, "入口里写死了机器路径")
        self.assertNotIn(FEATURE.encode("utf-8"), body, "入口里写死了需求名")
        self.assertEqual(0, self.view("prepare").returncode)
        self.assertEqual(body, entry.read_bytes())
        entry.write_text("@echo off\nrem 我自己的脚本\n", encoding="utf-8")
        proc = self.view("prepare")
        self.assertIn("不是本机制生成的", proc.stdout)
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
    """update 的镜像与还原精确排除一键入口与局部阅读证据；图源与正文照常进镜像。"""

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


class TheSecondReviewFindings(FigureViewCase):
    """复评 N02–N05：正式读取里的内部查询不提前恢复、请求正文与传递资源完整绑定、任务给真实位置、阅读缺口总被说出来。"""

    def ready(self) -> str:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.make_ready(fid)
        return fid

    def reading(self, fid: str) -> Path:
        return self.fr / "AR" / "story-src" / "figures" / f"{fid}.reading"

    def state(self, fid: str) -> str:
        work = json.loads(self.view("status").stdout)
        return next(i["state"] for i in work["items"] if i["id"] == fid)

    def test_an_internal_status_query_keeps_the_callers_mermaid(self) -> None:
        """阶段里作者包、预检调的状态查询归调用方持有：它结束不把 story 切回 SVG；用户直接跑 status 照常恢复。"""
        fid = self.ready()
        self.assertEqual(0, self.view("mermaid").returncode)
        client = CORE / "flow" / "client.mjs"
        driver = ("const m = await import(process.argv[1]);"
                  "const r = m.queryFlowStatus(process.argv[2], process.argv[3], { timeoutMs: 120000 });"
                  "process.stdout.write(JSON.stringify({ error: r.error }));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver, client.as_uri(), str(self.root), FEATURE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"), "内部查询把正式读取的 Mermaid 换成了 SVG")
        subprocess.run([sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertIn(f"](figures/{fid}.svg)", self.story.read_text(encoding="utf-8"), "用户直接跑 status 没恢复阅读图")

    def test_an_edited_request_with_its_old_id_is_refused(self) -> None:
        fid = self.ready()
        req_file = self.reading(fid) / "request.json"
        req = json.loads(req_file.read_text(encoding="utf-8"))
        for name, change in (("改图号", lambda r: r.update(id="fig-other")),
                             ("改源路径", lambda r: r["inputs"]["mmd"].update(path="AR/story-src/figures/other.mmd")),
                             ("删必核项", lambda r: r.update(checks=r["checks"][:1]))):
            with self.subTest(name):
                bad = json.loads(json.dumps(req))
                change(bad)
                req_file.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual("invalid", self.state(fid))
                self.assertEqual(1, self.view("review-check", "--id", fid).returncode)
        req_file.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
        self.assertEqual("ready", self.state(fid))

    def test_a_resource_reached_through_a_nested_svg_is_bound(self) -> None:
        fid = self.prepared_id()
        figs = self.fr / "AR" / "figures"
        figs.mkdir(parents=True, exist_ok=True)
        (figs / "nested.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><image href="../assets/deep.png"/></svg>',
                                         encoding="utf-8")
        (self.fr / "AR" / "assets").mkdir(parents=True, exist_ok=True)
        deep = self.fr / "AR" / "assets" / "deep.png"
        deep.write_bytes(PNG + b"deep")
        self.put_svg(fid, svg(FLOW_SRC, extra='<image href="nested.svg"/>'))
        request = self.make_ready(fid)
        self.assertIn("assets/deep.png", json.dumps(request["inputs"]["resources"]), "嵌套 SVG 引用的资源没进请求")
        deep.write_bytes(PNG + b"deep2")
        self.assertEqual("stale", self.state(fid), "改了嵌套资源，旧验收照样成立")

    def test_the_task_names_real_paths_and_the_business_place(self) -> None:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        shot = self.root / "shot.png"
        shot.write_bytes(PNG + b"render")
        out = self.view("review-request", "--id", fid, "--render", str(shot)).stdout
        self.assertIn(f"工程根：{self.root}", out)
        self.assertIn(f"doc/features/{FEATURE}/AR/story-src/figures/{fid}.reading/report.json", out)
        self.assertNotIn("doc/…", out)
        self.assertIn("「FIG90001 甲需求 › 业务流程 › 提交与回执」一节", out)
        self.make_ready(fid)
        self.story.write_text(self.story.read_text(encoding="utf-8").replace("图后：", "图后（改了业务说明）："), encoding="utf-8")
        self.assertEqual("stale", self.state(fid), "图所在小节的业务说明变了，位置结论还在复用")

    def test_a_formal_command_says_which_figures_stay_unread(self) -> None:
        fid = self.ready()
        (self.reading(fid) / "render.png").write_bytes(PNG + b"other")
        proc = subprocess.run(["node", str(BUILD), "number", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("本地阅读还没完成", proc.stderr)
        self.assertIn(fid, proc.stderr)
        self.assertIn("view --mode svg", proc.stderr)

    def test_a_closed_spec_still_routes_to_the_unfinished_reading(self) -> None:
        """spec 闭环后本地阅读没完成：路由把阅读作为下一步，而不是停在业务闭环说明里。

        路由在最外层动作持有的 Mermaid 形态下判（登记指纹也按 Mermaid 记），这里照此切换。
        """
        fid = self.prepared_id()
        sys.path.insert(0, str(CORE))
        from flow import routing, state  # noqa: PLC0415
        contract = {"rounds": [{"round": 1}], "status": "story_written",
                    "story_digests": {rel: state.ledger_digest(self.fr / rel) for rel in state.STORY_REGISTERED}}
        step, action = routing.next_step(self.fr, contract)
        self.assertEqual("run_archived", step, "spec 没闭环时先走闭环")
        reports = self.fr / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text("{ 坏了", encoding="utf-8")
        with self.assertRaises(state.FlowError, msg="summary 读不出却当成没闭环"):
            routing.next_step(self.fr, contract)
        (reports / "summary.json").write_text(json.dumps({"closure_status": "closed"}), encoding="utf-8")
        step, action = routing.next_step(self.fr, contract)
        self.assertEqual("local_reading", step)
        self.assertIn(fid, action)
        self.put_svg(fid, svg(FLOW_SRC))
        self.make_ready(fid)
        self.assertEqual(0, self.view("svg").returncode)
        self.assertEqual(0, self.view("mermaid").returncode)
        self.assertEqual("run_archived", routing.next_step(self.fr, contract)[0], "阅读完成后还卡在阅读")



class OneBlockOneVerdict(FigureViewCase):
    """第二轮返修 Q01/Q03：同一块合不合法在各入口结论一致；阶段闭环按工程配置的报告目录判。"""

    def ready_svg(self) -> str:
        fid = self.prepared_id()
        self.put_svg(fid, svg(FLOW_SRC))
        self.make_ready(fid)
        self.assertEqual(0, self.view("svg").returncode)
        return fid

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

    def test_a_broken_block_is_refused_everywhere_and_nothing_is_written(self) -> None:
        fid = self.ready_svg()
        good = self.story.read_text(encoding="utf-8")
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
                work = json.loads(self.view("status").stdout)
                self.assertFalse(work["complete"], f"{name}：状态说阅读已完成")
                self.assertTrue(work["next"], f"{name}：没给下一动作")
                for mode in ("mermaid", "svg", "toggle"):
                    self.assertEqual(1, self.view(mode).returncode, f"{name}：view {mode} 没拒绝坏块")
                formal = subprocess.run(["node", str(BUILD), "number", "--feature", FEATURE, "--project-root", str(self.root)],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                self.assertEqual(1, formal.returncode, f"{name}：正式命令带着坏块照常执行")
                self.assertEqual(before, self.story.read_bytes(), f"{name}：坏块时写了 story")
                self.assertEqual("pending", self.device_reading()["state"], f"{name}：装置把坏块读成完成")
        self.story.write_text(good, encoding="utf-8")
        (self.fr / "AR" / "story-src" / "figures" / f"{fid}.mmd").unlink()
        work = json.loads(self.view("status").stdout)
        self.assertEqual("no-source", work["items"][0]["state"])
        self.assertEqual(1, self.view("mermaid").returncode)

    def test_a_story_without_figures_is_not_applicable_anywhere(self) -> None:
        self.story.write_text("# FIG90001 甲需求\n\n## 背景\n\n没有图。\n", encoding="utf-8")
        work = json.loads(self.view("status").stdout)
        self.assertEqual((False, None), (work["applicable"], work["next"]))
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
