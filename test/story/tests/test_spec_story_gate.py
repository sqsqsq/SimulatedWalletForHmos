"""story 是 spec 阶段的第三份产物——spec 门禁核它成没成文。

批次 3 曾把成文挪到 spec 之后当独立一步，触发条件写「spec 闭环之后、归档之前」。
本地单没有归档，这个时点不存在，于是没有任何阶段边界要求它：实测一个 Case
四个阶段 harness 全 pass，而 `AR/story.md` 从来没被写出来。

判据查**登记态**不查文件在不在：手写一份简版照样能骗过「文件存在」——
基线就是这么判的，它的注释里自己承认过。`story_flow.py story` 登记前会重跑
`story-build check`，登记成功即九项判据都过了。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOW_CHECK = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
              / "scripts" / "core" / "flow-check.mjs")
FEATURE = "AR90001"

MINIMAL_FLOW = {
    "schema": 3,
    "feature": FEATURE,
    "status": "complete",
    "rounds": [{"round": 1, "gates": []}],
}


class TestSpecStoryGate(unittest.TestCase):
    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.feature_root = Path(self._tmp.name) / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)

    def write_flow(self, status: str | None) -> None:
        """status=None 表示这个 feature 没走过 /story（没有契约文件）。"""
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        if status is None:
            path.unlink(missing_ok=True)
            return
        flow = dict(MINIMAL_FLOW, status=status)
        path.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self) -> list[str]:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(JSON.stringify(m.storyProduced(process.argv[2])));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(FLOW_CHECK), str(self.feature_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_not_written_is_blocked_and_says_how(self) -> None:
        self.write_flow("complete")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("缺叙事件", problems[0])
        self.assertIn("story_flow.py story", problems[0], "报错要带上登记命令")

    def test_registered_passes(self) -> None:
        self.write_flow("story_written")
        self.assertEqual(self.problems(), [])

    def test_feature_without_story_flow_is_untouched(self) -> None:
        """没走 /story 的 feature 不受本判据影响——扩展不给它凭空加要求。"""
        self.write_flow(None)
        self.assertEqual(self.problems(), [])

    def test_broken_contract_says_it_cannot_tell(self) -> None:
        """读不出状态就判不了成文态：既不当作没成文，也不当作成文了。"""
        (self.feature_root / "AR" / "story-src" / "story-flow.json").write_text("{ 坏的", encoding="utf-8")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("不是合法 JSON", problems[0])


class TestOriginalArSourceIsAReadableFile(unittest.TestCase):
    """原件定位只把**可读的普通文件**当原件——作者照着它去读上游原话。

    只判「存在」的话，`design.origin` 指到一个目录也会被当成已校验的原件：
    任务包于是告诉作者「上游原话在这里」，他打开的是一个目录。
    """

    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.feature_root = Path(self._tmp.name) / "doc" / "features" / FEATURE
        self.src = self.feature_root / "AR" / "story-src"
        self.src.mkdir(parents=True)

    def write_flow(self, origin) -> None:
        flow = dict(MINIMAL_FLOW, design={"origin": origin} if origin is not None else None)
        (self.src / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def origin(self) -> dict:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(JSON.stringify(m.originalArSource(process.argv[2])));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(FLOW_CHECK), str(self.feature_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_real_file_is_the_only_success(self) -> None:
        keep = self.src / "sources" / "ar" / "r1.md"
        keep.parent.mkdir(parents=True)
        keep.write_text("# 上游原 AR\n\n原话在这里。\n", encoding="utf-8")
        self.write_flow("AR/story-src/sources/ar/r1.md")
        got = self.origin()
        self.assertIsNone(got["problem"], got)
        self.assertTrue(got["path"].endswith("r1.md"), got)

    def test_a_directory_is_not_an_original(self) -> None:
        (self.src / "sources" / "ar").mkdir(parents=True)
        self.write_flow("AR/story-src/sources/ar")
        got = self.origin()
        self.assertIsNone(got["path"], got)
        self.assertIn("不是一份文件", got["problem"])

    def test_a_dead_pointer_says_where_it_pointed(self) -> None:
        self.write_flow("AR/story-src/sources/ar/r1.md")
        got = self.origin()
        self.assertIsNone(got["path"])
        self.assertIn("AR/story-src/sources/ar/r1.md", got["problem"])

    def test_no_origin_is_not_a_problem(self) -> None:
        """本轮没有可留存的原件（空骨架）：没有原件，不是出了问题。"""
        self.write_flow(None)
        got = self.origin()
        self.assertIsNone(got["path"])
        self.assertIsNone(got["problem"])

    def test_a_pointer_out_of_the_feature_is_named(self) -> None:
        self.write_flow("../../../etc/passwd")
        got = self.origin()
        self.assertIsNone(got["path"])
        self.assertIn("越出了需求目录", got["problem"])


class TestTheGateChoicesComeFromTheContract(unittest.TestCase):
    """第一级关卡的值域读自章节合同：**读不到要出声**，不退化成空集。

    退化成空集的话，每一条合法的 `material_scope` 记录都会被判成「chosen 非法」，
    作者拿着一份合法契约去改它，而坏掉的是合同的读取路径。
    """

    EXT = REPO_ROOT / "doc" / "extensions" / "skills" / "story"

    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # 按机制自己的相对定位复制一份：flow-check 从它自己的位置找 contracts/
        self.skill = Path(self._tmp.name) / "story"
        shutil.copytree(self.EXT / "scripts", self.skill / "scripts")
        shutil.copytree(self.EXT / "contracts", self.skill / "contracts")
        self.feature_root = Path(self._tmp.name) / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)
        flow = dict(MINIMAL_FLOW)
        flow["rounds"] = [{
            "round": 1, "materials": {"digest": "d1"},
            "positioning": {"scope_text": "本 AR 承载提交与回执", "sr_related_ars": []},
            "scope_options": [{"key": "carry_all", "label": "按当前范围整体承载"}],
            "gates": [{"gate": "material_scope", "chosen": "confirm_scope",
                       "options": [{"key": "confirm_scope"}], "outcome": "accepted",
                       "at": "2026-09-12T00:00:00", "by": "human"},
                      {"gate": "scope_decision", "chosen": "carry_all",
                       "options": [{"key": "carry_all"}], "outcome": "accepted",
                       "at": "2026-09-12T00:00:00", "by": "human"}],
        }]
        flow["design_generated_at"] = "2026-09-12T00:00:00"
        (self.feature_root / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self) -> list[str]:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(JSON.stringify(m.flowProblems(process.argv[2])));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(self.skill / "scripts" / "core" / "flow-check.mjs"), str(self.feature_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_legal_contract_judges_the_choice(self) -> None:
        self.assertEqual([], self.problems())

    def test_a_broken_contract_is_reported_not_swallowed(self) -> None:
        (self.skill / "contracts" / "story-chapters.json").write_text("{ 坏了", encoding="utf-8")
        problems = self.problems()
        self.assertTrue(any("章节合同" in p for p in problems), problems)
        self.assertFalse(any("chosen 非法" in p for p in problems),
                         f"合同读不到却去说人的选择非法：{problems}")


if __name__ == "__main__":
    unittest.main()
