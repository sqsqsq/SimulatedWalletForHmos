"""阶段报告目录与 framework 原生 `featurePhaseReportsDir` 逐项对照：同一组配置，原生、JS（paths.mjs）、
Python（importer.py）三方要得到同一个目录，或同样判不了（报错）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "demo" / "framework" / "harness"
PROBE = REPO / "test" / "fixtures" / "native" / "reports-dir-probe.ts"
CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"
JS = ("const m = await import(process.argv[1]); const out = process.argv.slice(2).map(r => {"
      " try { return { dir: m.phaseReportsDir(r, 'F1', 'spec') }; } catch (e) { return { error: e.message }; } });"
      " process.stdout.write(JSON.stringify(out));")

#: 名称 → (framework.config.json 内容或 None 表示没有这个文件, 框架树位置: framework / root / none, features_dir)
MATRIX = {
    "没有配置文件": (None, "framework", "doc/features"),
    "空配置": ("{}", "framework", "doc/features"),
    "字段缺失、自定义需求目录": ('{"paths": {"features_dir": "specs/features"}}', "framework", "specs/features"),
    "非空自定义": ('{"paths": {"reports_dir_pattern": "audit/<feature>/<phase>"}}', "framework", "doc/features"),
    "显式空串": ('{"paths": {"reports_dir_pattern": ""}}', "framework", "doc/features"),
    "显式 null": ('{"paths": {"reports_dir_pattern": null}}', "framework", "doc/features"),
    "只有空白": ('{"paths": {"reports_dir_pattern": "   "}}', "framework", "doc/features"),
    "paths 为 null": ('{"paths": null}', "framework", "doc/features"),
    "空值且框架就是工程根": ('{"paths": {"reports_dir_pattern": ""}}', "root", "doc/features"),
    "空值且认不出框架树": ('{"paths": {"reports_dir_pattern": ""}}', "none", "doc/features"),
    "配置不是合法 JSON": ("{ 坏了", "framework", "doc/features"),
}


def norm(result: dict) -> str:
    return f"dir:{os.path.normcase(os.path.normpath(result['dir']))}" if "dir" in result else "error"


class ReportsDirMatchesTheFramework(unittest.TestCase):
    def test_native_js_and_python_agree(self) -> None:
        runner = HARNESS / "node_modules" / "ts-node" / "dist" / "bin.js"
        if not runner.is_file():
            self.skipTest("demo/framework/harness 没有 ts-node，原生对照跑不了")
        with tempfile.TemporaryDirectory() as tmp:
            roots = {}
            for name, (config, tree, features) in MATRIX.items():
                root = Path(tmp) / f"p{len(roots)}"
                (root / features / "F1").mkdir(parents=True)
                if tree != "none":
                    (root / ("framework" if tree == "framework" else "") / "skills").mkdir(parents=True, exist_ok=True)
                if config is not None:
                    (root / "framework.config.json").write_text(config, encoding="utf-8")
                roots[name] = (root, features)
            args = [str(r) for r, _ in roots.values()]
            native = subprocess.run(["node", str(runner), "--transpile-only", "--project", "tsconfig.json", str(PROBE), *args],
                                    cwd=HARNESS, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, native.returncode, native.stderr[-800:])
            js = subprocess.run(["node", "--input-type=module", "-e", JS, (DEV_EXT / "hooks" / "shared" / "paths.mjs").as_uri(), *args],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, js.returncode, js.stderr)
            sys.path.insert(0, str(CORE))
            from materials import importer  # noqa: PLC0415
            for (name, (root, features)), n, j in zip(roots.items(), json.loads(native.stdout), json.loads(js.stdout)):
                try:
                    py = {"dir": str(importer.phase_reports_dir(root / features / "F1", "spec"))}
                except importer.ImportError_ as exc:
                    py = {"error": str(exc)}
                with self.subTest(name):
                    self.assertEqual(norm(n), norm(j), f"JS 与原生不一致：{n} / {j}")
                    self.assertEqual(norm(n), norm(py), f"Python 与原生不一致：{n} / {py}")


if __name__ == "__main__":
    unittest.main()
