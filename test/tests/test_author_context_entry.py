# -*- coding: utf-8 -*-
"""作者起手内容有没有在**动笔之前**送到作者手上（A03/A05）。

宿主的作者事件只在装配 verifier ai-prompt 时消费，从不进入作者动笔前的上下文——
登记在那里，作者要到产物落盘之后才读得到。所以本扩展的作者要求由作者自己取：
原则页是 `doc/extensions/hooks/<动作>/author.md`，这一次的知识、承接的判断与缺口由知识任务命令给出。

所以这里测的不是「文件在不在」，是**通道**：

1. 蓝图设计与六个阶段各有自己那一份原则页，知识任务命令跑得出内容并指回原则页；
2. 参数缺席 / 真源读不到 → 明确失败、退出非零，**不降级成空**（静默的空和真正的空长得一样）；
3. 取法写在作者一定读得到的地方：流程的下一步文本、SKILL；每个阶段动笔前 Framework 按 phase_bindings 调知识 Skill；
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
from ext_workspace import link_harness_yaml, DEV_EXT, DEV_ROOT
from flow_steps import ensure_framework

REPO = Path(__file__).resolve().parents[2]
EXT = DEV_EXT
MANIFEST = EXT / "manifest.yaml"
RULES = EXT / "rules"
TASK_CLI = "doc/extensions/hooks/shared/knowledge-task.mjs"
FLOW = EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")
# context-exploration 门禁只覆盖这五个；testing 没有，如实无留痕。
GATED_PHASES = ("spec", "plan", "coding", "review", "ut")


def workspace(case: unittest.TestCase | None = None) -> Path:
    """一份装了开发版扩展的工作区，带一个平铺维护 Feature `demo`。"""
    ws = Path(tempfile.mkdtemp())
    if case:
        case.addCleanup(shutil.rmtree, ws, True)
    shutil.copytree(EXT, ws / "doc" / "extensions",
                    ignore=shutil.ignore_patterns("__pycache__", ".adapt-*", "node_modules"))
    link_harness_yaml(ws)
    (ws / "doc" / "features" / "demo").mkdir(parents=True)
    return ws


def task(ws: Path, *args: str) -> subprocess.CompletedProcess:
    return _node([TASK_CLI, "--project-root", str(ws), *args], ws)


def _node(args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", stdin=subprocess.DEVNULL,
    )


class AuthorRequirementsAreReachable(unittest.TestCase):
    """蓝图设计与六个阶段的原则页在，知识任务命令出得来这一次的内容。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ws = workspace()
        cls.task = task(cls.ws, "--feature", "demo", "--action", "spec", "--audience", "author")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.ws, True)

    def test_every_phase_has_its_own_principles_page(self):
        for phase in ("blueprint", *PHASES):
            with self.subTest(phase=phase):
                self.assertTrue((EXT / "hooks" / phase / "author.md").is_file(),
                                f"{phase} 没有原则页，作者动笔前无从取要求")

    def test_the_task_command_prints_this_round(self):
        proc = self.task
        self.assertEqual(0, proc.returncode, f"知识任务命令挂了：{proc.stderr[-600:]}")
        self.assertIn("demo", proc.stdout, "知识任务没带上本次 feature")
        self.assertIn("doc/extensions/hooks/spec/author.md", proc.stdout,
                      "知识任务没指回原则页——那是 key_inputs_read 要逐字引用的坐标")

    def test_the_task_carries_its_six_blocks(self):
        """对象、知识原文、事实与决定、契约与义务、完成条件、缺口：一份不缺。"""
        for needle in ("当前动作与对象", "激活知识及原文", "有效事实与决定", "当前契约与义务", "本次完成条件", "缺口与责任"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.task.stdout)


class ChannelFailuresAreLoud(unittest.TestCase):
    """参数缺席 / 真源读不到必须能分辨——它们的处置完全不同，都不许静默出空。"""

    def test_missing_object_is_refused_with_the_usage(self):
        proc = task(workspace(self), "--action", "spec", "--audience", "author")
        self.assertNotEqual(0, proc.returncode, "没给对象却当成功返回")
        self.assertIn("--feature", proc.stderr)
        self.assertEqual("", proc.stdout.strip(), "失败了还印出半份任务")

    def test_missing_knowledge_fails_loudly_instead_of_degrading_to_empty(self):
        """激活的知识文件读不到 → 明确失败，**不**降级成空。

        静默的空和真正的空长得一样；这条链路一旦静默失效，现场只表现为「作者又漏判了几条」。
        """
        ws = workspace(self)
        manifest = yaml.safe_load((ws / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
        first = manifest["provides"]["knowledge"][0]
        (ws / "doc" / "extensions" / (first if isinstance(first, str) else first["path"])).unlink()
        proc = task(ws, "--feature", "demo", "--action", "spec", "--audience", "author")
        self.assertNotEqual(0, proc.returncode, "知识读不到却照样返回成功")
        self.assertIn("知识", proc.stderr)
        self.assertEqual("", proc.stdout.strip())


class ThePointersAreWhereTheAuthorLooks(unittest.TestCase):
    """取法写在作者一定读得到的地方——文件在磁盘上不等于作者看见了。"""

    def test_the_flow_next_step_text_carries_the_knowledge_entry(self):
        """输入交给设计之后，作者逐步跟的 `status` 下一步文本要带着设计前取知识的入口。"""
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, True)
        ensure_framework(ws)
        feature_root = ws / "doc" / "features" / "demo"
        (feature_root / "AR" / "story-src").mkdir(parents=True)
        (feature_root / "AR" / "story-src" / "story-flow.json").write_text(json.dumps({
            "schema": 5, "feature": "demo", "status": "complete",
            "design_binding": {"component_id": "wallet-home", "blueprint_id": "bp-demo"},
            "input": {"snapshot_ref": "doc/features/demo/AR/story-src/inputs/0/snapshot.json"},
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
        self.assertIn("component-design", action)
        self.assertIn("story-knowledge", action, "流程的下一步文本没给设计前取知识的入口")

    def test_the_skill_carries_both_entries(self):
        text = (EXT / "skills" / "story" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("story-knowledge", text)
        self.assertIn("doc/extensions/hooks/<阶段>/author.md", text)


    def test_every_phase_binds_the_knowledge_skill_before_work(self):
        """每个阶段动笔前，Framework 按 phase_bindings 调 story-knowledge 取当前动作的知识任务。"""
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("story-knowledge", doc["provides"]["skills"])
        self.assertTrue((EXT / "skills" / "story-knowledge" / "SKILL.md").is_file())
        for phase in PHASES:
            with self.subTest(phase=phase):
                slot = doc["phase_bindings"][phase]["before_phase_work"]
                self.assertIn({"kind": "skill", "ref": "story-knowledge"}, slot)


class TheHostChannelIsNotUsed(unittest.TestCase):
    """作者要求不占宿主的作者事件，也不再引用已退场的框架入口。"""

    def test_manifest_registers_no_author_event(self):
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        for phase, events in doc["provides"]["hooks"].items():
            with self.subTest(phase=phase):
                self.assertNotIn("on_context_load", events,
                                 "作者要求又登记回宿主的作者事件了——那里到不了动笔之前")

    def test_no_delivery_surface_points_at_the_retired_framework_entry(self):
        surfaces = [MANIFEST, EXT / "skills" / "story" / "SKILL.md"]
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
                self.assertTrue((DEV_ROOT / declared).is_file(), f"{declared} 不存在")


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
                 "extensions", "demo/framework", "demo/CLAUDE.md", "demo/AGENTS.md"],
                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
            hits = [h for h in proc.stdout.splitlines() if h.strip()]
            with self.subTest(phase=phase):
                self.assertEqual([f"extensions/hooks/{phase}/author.md"], hits,
                                 f"{phase} 的作者内容出现了第二份：{hits}")


if __name__ == "__main__":
    unittest.main()
