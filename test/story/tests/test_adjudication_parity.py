# -*- coding: utf-8 -*-
"""必答集口径绑定：扩展侧（JS）与测试域侧（Python）必须派生出同一个集合。

两边各有各的用处——JS 那份给 verifier 注入清单、给阶段门禁核对；Python 这份在测试域
对真实目标跑回归。同一个口径写两遍，改了一边忘另一边就会出现「注入 14 行、只核 11 行」，
而两边各自都是绿的。这个测试就是那根绳子：口径一动，它先红。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "test" / "story" / "scripts"))

import check_failure_modes  # noqa: E402

JS_KEYS = REPO / "doc" / "extensions" / "hooks" / "shared" / "adjudication.mjs"

REGISTRY = {
    "domains": [
        {"prefix": "CND", "applies": False, "basis": "本需求不改界面"},
        {"prefix": "OTH", "applies": True, "basis": "本需求新增业务流程"},
    ],
    "constraints": [
        {"id": "SMP-01", "hit": True, "conclusion": "受理单编号在提交入口生成"},
        {"id": "SMP-02", "hit": False, "conclusion": "无对外新增接口"},
        {"id": "OTH-01", "hit": True, "conclusion": "流程每步记日志"},
    ],
    "patterns": [
        {"unit": "提交受理流程", "candidate": "sample-pattern", "signal": "多分支各有失败处理"},
    ],
}


class TestAdjudicationParity(unittest.TestCase):
    def test_js_and_python_derive_the_same_keys(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            src = tmp / "AR" / "story-src"
            src.mkdir(parents=True)
            (src / "knowledge.json").write_text(
                json.dumps(REGISTRY, ensure_ascii=False), encoding="utf-8")

            py_keys = check_failure_modes.adjudication_keys(REGISTRY)

            # Windows 上 ESM 只认 file:// URL，绝对盘符路径会被当成协议名
            script = (
                "import { adjudicationKeys } from "
                f"{json.dumps(JS_KEYS.as_uri())};\n"
                "import * as fs from 'node:fs';\n"
                f"const reg = JSON.parse(fs.readFileSync({json.dumps((src / 'knowledge.json').as_posix())}, 'utf-8'));\n"
                # 复制 specSet 的行构造：本测试绑的是「键集」，不重跑整条派生链
                "const rows = [];\n"
                "for (const c of reg.constraints ?? []) rows.push({ key: c.id });\n"
                "for (const d of reg.domains ?? []) if (d.applies !== true) rows.push({ key: d.prefix });\n"
                "for (const p of reg.patterns ?? []) rows.push({ key: p.unit });\n"
                "console.log(JSON.stringify(adjudicationKeys(rows)));\n"
            )
            r = subprocess.run(
                [_node(), "--input-type=module", "-e", script],
                capture_output=True, text=True, encoding="utf-8", cwd=str(REPO),
            )
            self.assertEqual(r.returncode, 0, f"JS 侧派生失败：{r.stderr[:400]}")
            js_keys = json.loads(r.stdout.strip().splitlines()[-1])

            self.assertEqual(js_keys, py_keys,
                             "两侧必答集口径已分叉——改一边就要改另一边")


def _node() -> str:
    return "node"


if __name__ == "__main__":
    unittest.main()
