"""流程契约只有一个写入者，交付门之后只问一件事。

  ① 契约带自身摘要：手改之后任一命令报「契约被手改」并给恢复路径，命令照常执行；
     下一次由脚本写入就重算摘要，提示消失（AC14）；
  ② 交付门之后的问法只有「归档送审 / 进入 plan」，交付门上的口头评审不再是 update 的入口（AC18）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL = REPO_ROOT / "doc" / "extensions" / "skills" / "story"
FLOW = SKILL / "scripts" / "core" / "story_flow.py"
FEATURE = "AR90001"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import write_gaps  # noqa: E402


class AHandEditIsReportedNotBlocking(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fr = self.root / "doc" / "features" / FEATURE
        for part in ("RR", "SR", "AR"):
            (self.fr / part).mkdir(parents=True)
        (self.fr / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n", encoding="utf-8")
        (self.fr / "SR" / "design.md").write_text("# 系统设计\n\n分工。\n", encoding="utf-8")
        self.contract = self.fr / "AR" / "story-src" / "story-flow.json"

    def flow(self, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def test_a_hand_edit_is_reported_and_the_command_still_runs(self) -> None:
        self.flow("init")
        self.assertNotIn("warning", self.flow("round"))
        data = json.loads(self.contract.read_text(encoding="utf-8"))
        data["split"]["scope_text"] = "手改的一句范围"
        self.contract.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        out = self.flow("status")
        self.assertTrue(out["success"], out)
        self.assertIn("被手改", out["warning"])
        self.assertIn("status", out["warning"], "没给出恢复路径")

        write_gaps(self.fr / "AR" / "story-src")
        again = self.flow("round")
        self.assertTrue(again["success"], "摘要不符把后续命令挡住了")
        self.assertNotIn("warning", self.flow("status"), "脚本重写之后摘要没重算")


class TheDeliveryGateAsksOneThing(unittest.TestCase):
    def test_no_page_routes_a_delivery_gate_opinion_into_update(self) -> None:
        for rel in ("phases/spec.md", "scripts/core/flow/routing.py", "SKILL.md"):
            text = (SKILL / rel).read_text(encoding="utf-8")
            for gone in ("交付门上人给的评审意见", "交付门上人的评审意见"):
                self.assertNotIn(gone, text, f"{rel} 里还有交付门口头评审入口")

    def test_the_route_after_registration_asks_archive_or_plan(self) -> None:
        sys.path.insert(0, str(SKILL / "scripts" / "core"))
        from flow import routing  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            fr = Path(tmp)
            step, action = routing.next_step(fr, {"rounds": [{"round": 1}], "status": "story_written"})
        self.assertEqual("run_archived", step)
        self.assertIn("归档送审 / 进入 plan", action)
        self.assertIn("phases/spec.md", action, "规则应只写在 phase 文档，路由指过去")

    def test_the_delivery_gate_prints_two_choices(self) -> None:
        text = (SKILL / "scripts" / "core" / "story" / "delivery.mjs").read_text(encoding="utf-8")
        self.assertIn("归档送审", text)
        self.assertIn("进入 plan", text)
        self.assertNotIn("先归档，再进 plan", text)


if __name__ == "__main__":
    unittest.main()
