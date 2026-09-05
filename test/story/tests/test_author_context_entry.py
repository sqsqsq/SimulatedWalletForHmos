# -*- coding: utf-8 -*-
"""作者起手内容有没有在**动笔之前**送到作者手上（A03/A05）。

宿主的作者事件只在装配 verifier ai-prompt 时消费，从不进入作者动笔前的上下文——
登记在那里，作者要到产物落盘之后才读得到。所以本扩展的作者要求由作者自己取：
原则页是 `doc/extensions/hooks/<阶段>/author.md`，spec 阶段另有一条命令出**本次任务包**。

所以这里测的不是「文件在不在」，是**通道**：

1. 六个阶段各有自己那一份原则页，spec 的任务包命令跑得出内容；
2. 参数缺席 / 真源读不到 → 明确失败、退出非零，**不降级成空**（静默的空和真正的空长得一样）；
3. 取法写在作者一定读得到的三处：流程的下一步文本、SKILL、入口文件的扩展段；
4. 「读过了」有唯一机械留痕：原则页路径进了 `key_inputs_read` 才过既有门禁。
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
EXT = REPO / "doc" / "extensions"
MANIFEST = EXT / "manifest.yaml"
RULES = EXT / "rules"
AUTHOR_CLI = "doc/extensions/hooks/spec/author.mjs"
FLOW = EXT / "skills" / "story" / "scripts" / "story_flow.py"
SECTION = EXT / "skills" / "story" / "AGENTS.section.md"
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")
# context-exploration 门禁只覆盖这五个；testing 没有，如实无留痕。
GATED_PHASES = ("spec", "plan", "coding", "review", "ut")


def _node(args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", stdin=subprocess.DEVNULL,
    )


class AuthorRequirementsAreReachable(unittest.TestCase):
    """六份原则页在，spec 的任务包命令出得来内容。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.task_package = _node([AUTHOR_CLI, "--feature", "demo"], REPO)

    def test_every_phase_has_its_own_principles_page(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.assertTrue((EXT / "hooks" / phase / "author.md").is_file(),
                                f"{phase} 没有原则页，作者动笔前无从取要求")

    def test_the_task_package_command_prints_this_round(self):
        proc = self.task_package
        self.assertEqual(0, proc.returncode, f"任务包命令挂了：{proc.stderr[-600:]}")
        self.assertIn("demo", proc.stdout, "任务包没带上本次 feature")
        self.assertIn("doc/extensions/hooks/spec/author.md", proc.stdout,
                      "任务包没指回原则页——那是 key_inputs_read 要逐字引用的坐标")

    def test_the_task_package_covers_the_four_sources(self):
        """任务包是四处真源的投影：位置、激活清单、材料里的图、章节合同。"""
        for needle in ("你现在在哪", "知识判断", "决策登记", "材料里的图", "十章各回答读者什么"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.task_package.stdout)


class ChannelFailuresAreLoud(unittest.TestCase):
    """参数缺席 / 真源读不到必须能分辨——它们的处置完全不同，都不许静默出空。"""

    def test_missing_feature_is_refused_with_the_usage(self):
        proc = _node([AUTHOR_CLI], REPO)
        self.assertNotEqual(0, proc.returncode, "没给 feature 却当成功返回")
        self.assertIn("--feature", proc.stderr)
        self.assertEqual("", proc.stdout.strip(), "失败了还印出半份任务包")

    def test_missing_contract_fails_loudly_instead_of_degrading_to_empty(self):
        """章节合同读不到 → 明确失败，**不**降级成空。

        静默的空和真正的空长得一样；这条链路一旦静默失效，现场只表现为
        「作者又漏了几章」。
        """
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, True)
        shutil.copytree(EXT, ws / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*", "node_modules"))
        (ws / "doc/extensions/skills/story/contracts/story-chapters.json").unlink()

        proc = _node([AUTHOR_CLI, "--feature", "demo"], ws)
        self.assertNotEqual(0, proc.returncode, "合同没了却照样返回成功")
        self.assertIn("合同", proc.stderr)
        self.assertEqual("", proc.stdout.strip())


class ThePointersAreWhereTheAuthorLooks(unittest.TestCase):
    """取法写在作者一定读得到的三处——文件在磁盘上不等于作者看见了。"""

    def test_the_flow_next_step_text_carries_the_command(self):
        """作者逐步跟的是 `status` 的下一步文本——spec 段每一步都要带着取法。"""
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, True)
        feature_root = ws / "doc" / "features" / "demo"
        (feature_root / "AR").mkdir(parents=True)
        (feature_root / "AR" / "story-flow.json").write_text(json.dumps({
            "schema": 3, "feature": "demo", "status": "complete",
            "rounds": [{"round": 1, "gates": []}],
        }, ensure_ascii=False), encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(FLOW), "status", "--feature", "demo",
             "--project-root", str(ws)],
            cwd=str(ws), capture_output=True, text=True, encoding="utf-8",
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        action = json.loads(proc.stdout)["action"]
        self.assertIn(AUTHOR_CLI, action, "流程的下一步文本没给任务包命令")
        self.assertIn("doc/extensions/hooks/spec/author.md", action)

    def test_the_skill_carries_the_command(self):
        text = (EXT / "skills" / "story" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(AUTHOR_CLI, text)
        self.assertIn("doc/extensions/hooks/<阶段>/author.md", text)

    def test_the_entry_section_carries_the_command(self):
        section = SECTION.read_text(encoding="utf-8")
        self.assertIn(AUTHOR_CLI, section)
        for f in (REPO / "CLAUDE.md", REPO / "AGENTS.md"):
            with self.subTest(file=f.name):
                self.assertIn(AUTHOR_CLI, f.read_text(encoding="utf-8"),
                              "入口文件的扩展段没跟上真源")


class TheHostChannelIsNotUsed(unittest.TestCase):
    """作者要求不占宿主的作者事件，也不再引用已退场的框架入口。"""

    def test_manifest_registers_no_author_event(self):
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        for phase, events in doc["provides"]["hooks"].items():
            with self.subTest(phase=phase):
                self.assertNotIn("on_context_load", events,
                                 "作者要求又登记回宿主的作者事件了——那里到不了动笔之前")

    def test_no_delivery_surface_points_at_the_retired_framework_entry(self):
        surfaces = [MANIFEST, SECTION, EXT / "skills" / "story" / "SKILL.md"]
        surfaces += [RULES / f"{p}-rules.overlay.yaml" for p in GATED_PHASES]
        for f in surfaces:
            with self.subTest(file=f.name):
                self.assertNotIn("author-context", f.read_text(encoding="utf-8"),
                                 "还指着已退场的框架入口")


class ReadingItLeavesExactlyOneTrace(unittest.TestCase):
    """「读过了」的唯一机械留痕：原则页路径进 `key_inputs_read`。"""

    def test_gated_phases_declare_the_principles_page_as_required_snippet(self):
        for phase in GATED_PHASES:
            with self.subTest(phase=phase):
                doc = yaml.safe_load((RULES / f"{phase}-rules.overlay.yaml").read_text(encoding="utf-8"))
                extra = (doc.get("exploration_thresholds") or {}).get("phase_input_snippets_extra") or []
                self.assertIn(f"doc/extensions/hooks/{phase}/author.md", extra)

    def test_ungated_phase_declares_nothing(self):
        """testing 没有 context-exploration 门禁——如实不声明，不造一个假留痕。"""
        doc = yaml.safe_load((RULES / "testing-rules.overlay.yaml").read_text(encoding="utf-8"))
        self.assertIsNone(doc.get("exploration_thresholds"))

    def test_declared_snippet_is_a_file_that_exists(self):
        """声明的字符串必须逐字等于那份原则页的路径，否则门禁永远命中不了。"""
        for phase in GATED_PHASES:
            with self.subTest(phase=phase):
                doc = yaml.safe_load((RULES / f"{phase}-rules.overlay.yaml").read_text(encoding="utf-8"))
                declared = doc["exploration_thresholds"]["phase_input_snippets_extra"][0]
                self.assertTrue((REPO / declared).is_file(), f"{declared} 不存在")


class ManifestKeepsOneSourceOfTruth(unittest.TestCase):
    def test_author_content_is_not_duplicated_anywhere(self):
        """一份真源：author 正文不许被复制进 Skill / AGENTS / 模板。

        判据取每份 author.md 的首个非空标题行——它被复制出去就会在别处出现。
        """
        for phase in PHASES:
            author = EXT / "hooks" / phase / "author.md"
            heading = next(l.strip() for l in author.read_text(encoding="utf-8").splitlines()
                           if l.strip().startswith("#"))
            proc = subprocess.run(
                ["git", "grep", "-l", "--fixed-strings", heading, "--",
                 "doc/extensions", "framework", "CLAUDE.md"],
                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
            hits = [h for h in proc.stdout.splitlines() if h.strip()]
            with self.subTest(phase=phase):
                self.assertEqual([f"doc/extensions/hooks/{phase}/author.md"], hits,
                                 f"{phase} 的作者内容出现了第二份：{hits}")

    def test_the_entry_section_only_points_it_does_not_copy(self):
        """入口段只给取法，不搬正文——搬过去就有两份要同步。"""
        section = SECTION.read_text(encoding="utf-8")
        self.assertLess(len(section), 1200, "扩展段变长了，像是把正文搬了进来")
        self.assertNotIn("先完整读它", section)


if __name__ == "__main__":
    unittest.main()
