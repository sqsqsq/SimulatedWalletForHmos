"""产品代码里没有只为测试存在的入口：每个具名导出都有一个产品模块在用。

测试经生产入口（命令、门禁结果，或产品模块也在用的导出）检验行为；只给测试开的导出与参数
会让产品代码为测试长出第二条路径。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
EXPORT = re.compile(r"^export (?:async )?(?:function\*? |const |let |class )(\w+)", re.M)


class EveryExportHasAProductConsumer(unittest.TestCase):
    def test_no_export_is_consumed_only_by_tests(self) -> None:
        files = [p for p in EXT.rglob("*.mjs") if "node_modules" not in p.parts]
        texts = {p: p.read_text(encoding="utf-8") for p in files}
        orphans = []
        for path, text in texts.items():
            for name in EXPORT.findall(text):
                used = any(re.search(rf"\b{name}\b", other) for p, other in texts.items() if p != path)
                if not used:
                    orphans.append(f"{path.relative_to(EXT).as_posix()}：{name}")
        self.assertEqual([], orphans)

    def test_story_build_has_no_offline_mode(self) -> None:
        core = EXT / "skills" / "story" / "scripts" / "core"
        hits = [p.relative_to(EXT).as_posix() for p in core.rglob("*.mjs")
                if re.search(r"\boffline\b", p.read_text(encoding="utf-8"))]
        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
