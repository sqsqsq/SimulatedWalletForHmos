"""JS 侧问流程状态的那**一个**客户端（`core/flow/client.mjs`）。

作者任务包与成文起手预检此前各写一套查询：各自拼脚本路径、各自轮解释器、各自解析
JSON，其中一份还漏了 `--project-root`——Python 于是按脚本自身位置解析工程，同一份
任务包里位置读的是机制仓、材料与知识读的是目标工作区，作者拿到的两半对不上。

这一份锁的是：**问的是调用方给的那个工程**，以及四种结果各自可辨——没走过 /story、
业务失败、输出不是约定的形状、超时。解释器缺失不在这里模拟（环境里 python 一定在），
那一支由代码里「只有起不动才换候选」的注释与真实缺失时的报错承担。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
CLIENT = CORE / "flow" / "client.mjs"
FEATURE = "AR90001"

FLOW_JSON = {
    "schema": 3,
    "feature": FEATURE,
    "status": "complete",
    "design_generated_at": "2026-09-12T00:00:00",
    "rounds": [{
        "round": 1,
        "materials": {"path": "AR/story-src/materials.json", "digest": "seeded"},
        "positioning": {"scope_text": "本 AR 承载提交与回执", "sr_related_ars": []},
        "scope_options": [{"key": "carry_all", "label": "按当前范围整体承载"}],
        "gates": [],
    }],
}


class ClientCase(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "另一个工程"
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "RR").mkdir(parents=True)
        (self.feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n",
                                                         encoding="utf-8")

    def write_flow(self, data: dict | None) -> None:
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        if data is None:
            (src / "story-flow.json").unlink(missing_ok=True)
            return
        (src / "story-flow.json").write_text(json.dumps(data, ensure_ascii=False),
                                             encoding="utf-8")

    def query(self, client: Path | None = None, timeout_ms: int = 60000) -> dict:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "const out = m.queryFlowStatus(process.argv[2], process.argv[3],"
            "  {timeoutMs: Number(process.argv[4])});"
            "process.stdout.write(JSON.stringify(out));")
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script, "--",
             str(client or CLIENT), str(self.root), FEATURE, str(timeout_ms)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, cwd=str(REPO_ROOT))
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)


class TheQueryHitsTheProjectItWasGiven(ClientCase):
    """调用方给哪个工程根就问哪个工程 —— cwd 替代不了 `--project-root`。"""

    def test_a_legal_contract_in_another_project_comes_back(self) -> None:
        self.write_flow(FLOW_JSON)
        got = self.query()
        self.assertIsNone(got["error"], got)
        self.assertTrue(got["data"]["exists"])
        self.assertEqual("complete", got["data"]["status"])
        self.assertEqual(1, got["data"]["round"], "读到的不是这个工程的那一轮")
        self.assertIn("material_state", got["data"], "材料事实没带回来")

    def test_a_project_without_the_flow_is_not_an_error(self) -> None:
        """没走过 /story 与查询链坏了是两件事：前者照常往下走，后者必须停。"""
        self.write_flow(None)
        got = self.query()
        self.assertIsNone(got["error"], got)
        self.assertIs(False, got["data"]["exists"])

    def test_a_business_failure_keeps_its_own_reason(self) -> None:
        """契约坏了是业务失败：带着退出码与原话回来，不换个解释器再问一遍。"""
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "story-flow.json").write_text("{ 坏了", encoding="utf-8")
        got = self.query()
        self.assertIsNone(got["data"])
        self.assertIn("退出码", got["error"])
        self.assertIn("story-flow.json", got["error"])


class BadAnswersAreNamed(ClientCase):
    """答案不是约定的形状时说清是哪一种——客户端找的是**相邻上级**那个入口，
    所以把一份替身放到同样的相对位置，测的就是真实的定位与判形状路径。
    """

    def stub(self, body: str) -> Path:
        stub_root = Path(self._tmp.name) / "stub" / "core"
        (stub_root / "flow").mkdir(parents=True, exist_ok=True)
        shutil.copy2(CLIENT, stub_root / "flow" / "client.mjs")
        (stub_root / "story_flow.py").write_text(body, encoding="utf-8")
        return stub_root / "flow" / "client.mjs"

    def test_output_that_is_not_json_is_named(self) -> None:
        client = self.stub("print('这不是 JSON')\n")
        got = self.query(client)
        self.assertIsNone(got["data"])
        self.assertIn("没有输出 JSON", got["error"])

    def test_a_broken_shape_is_named(self) -> None:
        client = self.stub(
            "import json\n"
            "print(json.dumps({'exists': True, 'next': 'x', 'action': 'y',\n"
            "                  'material_state': {'pending': 'one'}}))\n")
        got = self.query(client)
        self.assertIsNone(got["data"])
        self.assertIn("material_state", got["error"])

    def test_a_missing_material_state_is_named(self) -> None:
        client = self.stub(
            "import json\nprint(json.dumps({'exists': True, 'next': 'x', 'action': 'y'}))\n")
        got = self.query(client)
        self.assertIsNone(got["data"])
        self.assertIn("material_state", got["error"])

    def test_a_timeout_says_it_timed_out(self) -> None:
        client = self.stub("import time\ntime.sleep(30)\n")
        got = self.query(client, timeout_ms=1500)
        self.assertIsNone(got["data"])
        self.assertIn("没跑完", got["error"])
        self.assertIn("ETIMEDOUT", got["error"], "超时要说得出是超时，不能混进「起不动」")


if __name__ == "__main__":
    unittest.main()
