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
              / "scripts" / "flow-check.mjs")
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
        (self.feature_root / "AR").mkdir(parents=True)

    def write_flow(self, status: str | None) -> None:
        """status=None 表示这个 feature 没走过 /story（没有契约文件）。"""
        path = self.feature_root / "AR" / "story-flow.json"
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

    def test_archived_passes(self) -> None:
        """已送审归档的自然也成过文——状态机往前走了，不该被回头拦住。"""
        self.write_flow("archived")
        self.assertEqual(self.problems(), [])

    def test_feature_without_story_flow_is_untouched(self) -> None:
        """没走 /story 的 feature 不受本判据影响——扩展不给它凭空加要求。"""
        self.write_flow(None)
        self.assertEqual(self.problems(), [])

    def test_broken_contract_says_it_cannot_tell(self) -> None:
        """读不出状态就判不了成文态：既不当作没成文，也不当作成文了。"""
        (self.feature_root / "AR" / "story-flow.json").write_text("{ 坏的", encoding="utf-8")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("不是合法 JSON", problems[0])


if __name__ == "__main__":
    unittest.main()
