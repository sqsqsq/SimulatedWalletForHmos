"""资格门样本按生产必审合同装配：覆盖齐全才测区分力；读数身份跟着实际任务与完整配置走。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_review_qualification as rq  # noqa: E402


class TheSampleIsAFullProductionTask(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)
        self.sample = rq.maker.build(rq.maker.load_pairs())["receipt.good"]
        self.entry = {"id": "c1", "name": "cli", "model": "m", "profile": None, "env": {"A": "1"}}

    def test_every_required_input_is_present(self) -> None:
        ws = rq.build_workspace(self.out, self.sample)
        self.assertEqual({"missing": [], "gaps": []}, rq.coverage(ws))

    def test_the_identity_follows_the_inputs_and_the_whole_config(self) -> None:
        ws = rq.build_workspace(self.out, self.sample)
        first = rq.identity(self.sample, ws, self.entry)
        self.assertEqual(first, rq.identity(self.sample, ws, dict(self.entry)), "同一对象身份不稳")
        self.assertNotEqual(first, rq.identity(self.sample, ws, {**self.entry, "env": {"A": "2"}}),
                            "配置里没列进身份的键变了，旧读数照样复用")
        spec = ws / "doc" / "features" / rq.FEATURE / "spec" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\n补一句。\n", encoding="utf-8")
        (ws / rq.TASK_FILE).write_text(rq.task_document(self.sample, rq.input_table(ws)), encoding="utf-8")
        self.assertNotEqual(first, rq.identity(self.sample, ws, self.entry), "必审输入变了，旧读数照样复用")


if __name__ == "__main__":
    unittest.main()
