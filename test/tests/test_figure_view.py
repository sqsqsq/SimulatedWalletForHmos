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
        self.assertEqual(0, self.view("svg").returncode)
        self.assertNotIn("```mermaid", self.story.read_text(encoding="utf-8"))
        return fid

    def test_other_story_build_commands_switch_back_first(self) -> None:
        self.to_svg()
        subprocess.run(["node", str(BUILD), "number", "--feature", FEATURE, "--project-root", str(self.root)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"), "正式命令没先切回 Mermaid")

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
        self.to_svg()
        subprocess.run([sys.executable, str(FLOW), "status", "--feature", FEATURE, "--project-root", str(self.root)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("```mermaid", self.story.read_text(encoding="utf-8"), "story_flow 读 story 前没切回")


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
