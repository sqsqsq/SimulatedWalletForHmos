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


class PatternSignalSourceIsStatedToBothReaders(unittest.TestCase):
    """「信号来自业务流程本身」这句话，两个读者面都要看得到，且逐字一致。

    F6 实证：spec §11 五个单元全判「无候选」，反证逐句复述模式索引的判定语言
    （「无跨步骤状态」「几个彼此独立的按钮」）。四环因果里的一环是**读者面缺口**
    ——那句「承载会换，业务不会」只写在模式索引里，而模式索引的读者标注只面向 plan；
    spec 阶段做候选判定的人，手上是 spec 模板，看不到它。

    所以它现在写在两处。两处就有漂移的风险，用这条测试锁住：改一处必须改另一处。
    """

    SENTENCES = (
        "信号来自**业务流程本身**：数分支、数步数、看失败处理时，以需求描述的那个业务过程为准。",
        "当前用模拟、演示或简化方式承载某一步，不改变业务信号——承载会换，业务不会。",
    )
    READERS = (
        Path("doc/extensions/knowledge/design-patterns/README.md"),
        Path("doc/extensions/skills/story/templates/spec-sections.md"),
    )

    def test_both_readers_carry_the_same_sentences(self) -> None:
        for rel in self.READERS:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for sentence in self.SENTENCES:
                self.assertIn(sentence, text,
                              f"{rel.name} 里没有这句：{sentence[:24]}…"
                              "——两个读者面必须逐字一致，改一处就要改另一处")

    def test_the_copyable_verdict_wording_is_gone_from_the_routing_table(self) -> None:
        """路由表里那句可照抄的具体描述已退场。

        原文是「单一线性流程、两三个分支且各自只有一两步、无跨步骤状态；或页面只有
        几个彼此独立的按钮」——它被整句抄进反证栏，连「无跨步骤状态」这个与业务不符的
        断言也照抄。判定标准换成「以上信号都不成立」，读者要自己去看前两行。
        """
        text = (REPO_ROOT / self.READERS[0]).read_text(encoding="utf-8")
        for gone in ("无跨步骤状态；或页面只有几个彼此独立的按钮",
                     "两三个分支且各自只有一两步"):
            self.assertNotIn(gone, text, f"可照抄的判定话术还在：{gone}")
