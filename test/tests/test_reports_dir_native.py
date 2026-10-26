"""阶段报告目录只由原生 `featurePhaseReportsDir` 算：同一组配置，JS 桥（framework-access）与 Python 桥
（flow/native.feature_paths）读到同一个目录，或同样判不了（报错）。扩展不另存一份目录规则。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT
from design_fixture import _link_dir, framework_under_test

CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"
JS = ("const m = await import(process.argv[1]); const out = process.argv.slice(2).map(r => m.phaseReportsDir(r, 'F1', 'spec'));"
      " process.stdout.write(JSON.stringify(out));")

#: 名称 → (framework.config.json 内容或 None 表示没有这个文件, features_dir)
MATRIX = {
    "没有配置文件": (None, "doc/features"),
    "空配置": ("{}", "doc/features"),
    "字段缺失、自定义需求目录": ('{"paths": {"features_dir": "specs/features"}}', "specs/features"),
    "非空自定义": ('{"paths": {"reports_dir_pattern": "audit/<feature>/<phase>"}}', "doc/features"),
    "显式空串": ('{"paths": {"reports_dir_pattern": ""}}', "doc/features"),
    "显式 null": ('{"paths": {"reports_dir_pattern": null}}', "doc/features"),
    "只有空白": ('{"paths": {"reports_dir_pattern": "   "}}', "doc/features"),
    "paths 为 null": ('{"paths": null}', "doc/features"),
    "配置不是合法 JSON": ("{ 坏了", "doc/features"),
}


def norm(result: dict) -> str:
    return f"dir:{os.path.normcase(os.path.normpath(result['dir']))}" if "dir" in result else "error"


class ReportsDirMatchesTheFramework(unittest.TestCase):
    def test_both_bridges_read_the_native_answer(self) -> None:
        source = framework_under_test()
        with tempfile.TemporaryDirectory() as tmp:
            roots = {}
            for name, (config, features) in MATRIX.items():
                root = Path(tmp) / f"p{len(roots)}"
                (root / features / "F1").mkdir(parents=True)
                _link_dir(source, root / "framework")
                if config is not None:
                    (root / "framework.config.json").write_text(config, encoding="utf-8")
                roots[name] = root
            js = subprocess.run(["node", "--input-type=module", "-e", JS,
                                 (DEV_EXT / "hooks" / "shared" / "framework-access.mjs").as_uri(), *map(str, roots.values())],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, js.returncode, js.stderr)
            sys.path.insert(0, str(CORE))
            from flow import native  # noqa: PLC0415
            from flow.state import FlowError  # noqa: PLC0415
            for (name, root), j in zip(roots.items(), json.loads(js.stdout)):
                try:
                    reports = native.feature_paths(root, "F1", ("spec",))["reports"]["spec"]
                    py = {"dir": str(reports)}
                except FlowError as exc:
                    py = {"error": str(exc)}
                with self.subTest(name):
                    self.assertEqual(norm(j), norm(py), f"Python 与原生不一致：{j} / {py}")
            self.assertTrue(json.loads(js.stdout)[list(MATRIX).index("非空自定义")]["dir"].replace("\\", "/")
                            .endswith("audit/F1/spec"), "自定义报告目录没有按原生解析")


if __name__ == "__main__":
    unittest.main()
