# -*- coding: utf-8 -*-
"""§9 技术契约「表外有段落」这条判据，跑在**真实产物**上。

它只在真实输入上才现形：判的是节内正文的行，而行的边界由切节那一步给。
判据自己把它拼成字符串再切一遍的话，数组会以逗号连成一整行，节首那个空行
也就不再是空行——于是五节全被报成「表外有段落」，而它们都只有表。

所以这一份的输入是 `fixtures/real-run` 的 spec.md：CRLF、五节俱全、每节首行是空行的
那份真东西（目录自带 `.gitattributes: * -text` 保住换行）。构造用例看不见这个形态。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
REAL = REPO_ROOT / "test" / "story" / "fixtures" / "real-run" / "AR90006"
FEATURE = "AR90006"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [hookPath, feature, projectRoot] = process.argv.slice(-3);
const hook = (await import(pathToFileURL(hookPath).href)).default;
process.stdout.write(JSON.stringify(await hook({ phase: 'spec', feature, projectRoot })));
"""


class TheContractSectionIsJudgedOnRealOutput(unittest.TestCase):
    """一个类建一次工作区：它是只读夹具，而建一次要复制一份完整扩展。"""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "work"
        (cls.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, cls.root / "doc" / "extensions")
        shutil.copytree(REAL, cls.root / "doc" / "features" / FEATURE)
        # §9 那一章只在走过 /story 的 feature 上判——夹具里补一份流程契约，
        # 否则这一整组判据整块跳过，测出来的绿是「没判」不是「判过」。
        (cls.root / "doc" / "features" / FEATURE / "AR" / "story-flow.json").write_text(
            json.dumps({"schema": 3, "feature": FEATURE, "status": "complete",
                        "rounds": [{"round": 1, "gates": []}]}, ensure_ascii=False),
            encoding="utf-8")
        driver = cls.root / "drive.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(driver),
             str(cls.root / "doc/extensions/hooks/spec/post_check.mjs"),
             FEATURE, str(cls.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert proc.returncode == 0, proc.stderr[-800:]
        cls.report = proc.stdout

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_a_real_spec_has_no_stray_prose_report(self) -> None:
        """五节都是表，一段散文也没有。"""
        self.assertNotIn("表外有段落", self.report,
                         f"真实 spec 的 §9 被误报：{self.report[:600]}")

    def test_the_five_subsections_are_all_seen(self) -> None:
        """判据确实跑到了这五节上——一条都没报不等于一条都没判。"""
        spec = (REAL / "spec" / "spec.md").read_text(encoding="utf-8")
        for name in ("端云接口", "数据存储", "配置项", "埋点", "依赖变更"):
            with self.subTest(section=name):
                self.assertIn(name, spec, "夹具的 §9 少了这一节，判据没有对象")
        self.assertNotIn("缺少小节", self.report, f"§9 的小节没被认出来：{self.report[:600]}")


if __name__ == "__main__":
    unittest.main()
