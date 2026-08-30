"""契约只有一份真源——扩展与 framework 读同一个路径。

原来扩展读 `<feature>/plan/` 下的另一份、framework 读 feature 根下那份，
两个物理位置各存各的。实测被测模型只能复制一份去同步，而义务（契约实体上的 `must`）
就挂在那份副本上：改了根的那份，扩展的判据看不见。

这里判两件事：根下那份读得到；**只有子目录那份时不回退**——回退看着稳，
实际是把「两份真源」合法化，哪一份被读到取决于哪一份先存在。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_MJS = REPO_ROOT / "doc" / "extensions" / "hooks" / "shared" / "contracts.mjs"
FEATURE = "AR90001"

CONTRACT_YAML = """modules:
  - name: 甲模块
    must:
      - text: 缓存凭证读取前校验签名
        verify: ut
"""


class TestContractsSingleSource(unittest.TestCase):
    def read_contracts(self, root: Path) -> dict:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "const r=m.readContracts(process.argv[2], process.argv[3]);"
            "console.log(JSON.stringify({exists:r.exists,error:r.error,"
            "names:(r.contracts?.modules??[]).map(x=>x.name)}));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(CONTRACTS_MJS), str(root), FEATURE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def setUp(self) -> None:
        import shutil
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "plan").mkdir(parents=True)

    def test_reads_the_one_at_feature_root(self) -> None:
        (self.feature_root / "contracts.yaml").write_text(CONTRACT_YAML, encoding="utf-8")
        result = self.read_contracts(self.root)
        self.assertTrue(result["exists"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["names"], ["甲模块"])

    def test_does_not_fall_back_to_the_plan_subdirectory(self) -> None:
        """只有子目录那份时报「缺契约」，不悄悄读它——回退等于承认两份真源。"""
        (self.feature_root / "plan" / "contracts.yaml").write_text(CONTRACT_YAML, encoding="utf-8")
        result = self.read_contracts(self.root)
        self.assertFalse(result["exists"], "子目录下的那份不该被读到")
        self.assertEqual(result["names"], [])

    def test_path_matches_framework_loader(self) -> None:
        """路径与 framework 的 spec-loader 同源：feature 根下的 contracts.yaml。"""
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(m.contractsPath(process.argv[2], process.argv[3]));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(CONTRACTS_MJS), str(self.root), FEATURE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(Path(proc.stdout.strip()), self.feature_root / "contracts.yaml")


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
