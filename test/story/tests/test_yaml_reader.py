"""YAML 读取与 framework 同一解析器：合法写法两边读出同一个对象，读不到包时响亮报错。

扩展曾自造一份最小读取器，两周里三次为合法 YAML 打补丁，第四次是流式映射——读取器的局限
变成作者的限制。现在 `hooks/shared/yaml.mjs` 只借 framework harness 的 `yaml` 包。这一份锁三件事：

1. 标量词法：引号、行尾注释、引号里的 `#`，同一个值的几种合法写法读出来一样
   （adapt 靠 `name` 相等判来源，多一对引号就把判断带向相反的一边）；
2. 四类真实样本（framework 契约模板、带流式写法的契约、knowledge-use 骨架、verifier 报告的
   YAML 围栏）扩展读出的对象与 framework 侧 `YAML.parse` 深相等；
3. 临时根没有 `framework/harness` 时，第一次解析抛错且文案带安装命令——不下载、不退回别的读法。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
READER = REPO_ROOT / "doc" / "extensions" / "hooks" / "shared" / "yaml.mjs"
HARNESS_PKG = REPO_ROOT / "framework" / "harness" / "package.json"

#: 写法 → 期望读出的值。前七条是同一个值的合法写法，后面几条各锁一件别的事。
CASES = [
    ('name: wallet-sdk-demo', "wallet-sdk-demo"),
    ('name: "wallet-sdk-demo"', "wallet-sdk-demo"),
    ("name: 'wallet-sdk-demo'", "wallet-sdk-demo"),
    ('name: wallet-sdk-demo  # 说明', "wallet-sdk-demo"),
    ('name: "wallet-sdk-demo"  # 说明', "wallet-sdk-demo"),
    ("name: 'wallet-sdk-demo'  # 说明", "wallet-sdk-demo"),
    ('name: "wallet-sdk-demo" # 紧挨着', "wallet-sdk-demo"),
    # 引号里的 # 是内容，不是注释的起点
    ('name: "a # b"', "a # b"),
    ("name: 'a # b'", "a # b"),
    # 没有空白的 # 也是内容（`a#b` 是一个值）
    ('name: a#b', "a#b"),
    ('name: ""', ""),
]


def node_json(script: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", "--input-type=module", "-e", script, "--", *argv],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


class ScalarLexing(unittest.TestCase):
    """跑真的读取器，不在这里重实现一份判断。"""

    def setUp(self) -> None:  # noqa: D102
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def parse(self, text: str, reader: Path = READER):
        probe = ("import {pathToFileURL} from 'node:url';"
                 "const { parseYaml } = await import(pathToFileURL(process.argv[1]).href);"
                 "process.stdout.write(JSON.stringify(parseYaml(process.argv[2]) ?? null));")
        proc = node_json(probe, str(reader), text)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def parse_error(self, text: str, reader: Path = READER) -> str:
        probe = ("import {pathToFileURL} from 'node:url';"
                 "const { parseYaml } = await import(pathToFileURL(process.argv[1]).href);"
                 "try { parseYaml(process.argv[2]); process.stdout.write('NO-ERROR'); }"
                 "catch (e) { process.stdout.write(String(e.message)); }")
        proc = node_json(probe, str(reader), text)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotEqual("NO-ERROR", proc.stdout, "该抛错却读出了东西")
        return proc.stdout

    def test_equivalent_spellings_read_the_same(self) -> None:
        for line, want in CASES:
            with self.subTest(line=line):
                self.assertEqual(want, self.parse(line).get("name"))

    def test_a_quoted_value_with_a_trailing_comment_carries_no_quotes(self) -> None:
        """这一条单拎出来：它是 adapt 判来源时踩过的那个形态。"""
        got = self.parse('name: "wallet-sdk-demo"  # 发布源')["name"]
        self.assertEqual("wallet-sdk-demo", got)
        self.assertNotIn('"', got, "值里还留着引号——相等判断会走向相反的一边")

    def test_unclosed_quote_is_a_loud_error_not_a_guess(self) -> None:
        """引号没收尾就是语法错——与 framework 同一判法，带行列，不猜成一个值。"""
        self.assertIn("quote", self.parse_error('name: "unclosed'))

    def test_a_colon_inside_a_list_item_reads_as_the_framework_reads_it(self) -> None:
        """`- 键: 值` 在 YAML 里就是一条映射，framework 也这么读；要一句话就加引号，全角冒号不是分隔。"""
        self.assertEqual({"items": [{"布局与文本对齐": "用 start/end"}]},
                         self.parse("items:\n  - 布局与文本对齐: 用 start/end"))
        self.assertEqual({"items": ["布局与文本对齐: 用 start/end"]},
                         self.parse('items:\n  - "布局与文本对齐: 用 start/end"'))
        self.assertEqual({"items": ["说明：全角冒号不是分隔"]}, self.parse("items:\n  - 说明：全角冒号不是分隔"))

    def test_quoted_keys_and_flow_style_open_mappings(self) -> None:
        quoted = self.parse('deps:\n  "a/b -> c/d":\n    kind: import')["deps"]
        self.assertEqual({"a/b -> c/d": {"kind": "import"}}, quoted)
        self.assertEqual({"items": [{"id": "AC-1", "text": "提交"}]},
                         self.parse("items:\n  - { id: AC-1, text: 提交 }"))

    def test_an_empty_document_is_an_empty_mapping(self) -> None:
        self.assertEqual({}, self.parse(""))
        self.assertEqual({}, self.parse("# 只有注释\n"))

    def test_duplicate_keys_are_a_loud_error(self) -> None:
        self.assertIn("unique", self.parse_error("a: 1\na: 2"))


class SameObjectAsFramework(unittest.TestCase):
    """四类真实样本：扩展读出的对象与 framework 侧 `yaml` 包直接读出的深相等。"""

    SAMPLES = {
        "framework 契约模板": REPO_ROOT / "framework" / "skills" / "feature" / "plan" / "contracts-template.yaml",
    }

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        out = REPO_ROOT / "output" / "story"
        flow_contract = next((p for p in sorted(out.glob("*/cases/*/*/artifact/contracts.yaml"))
                              if "- {" in p.read_text(encoding="utf-8", errors="replace")), None)
        if flow_contract:
            cls.SAMPLES["带流式写法的契约"] = flow_contract
        use = sorted(out.glob("*/cases/*/*/artifact/spec/knowledge-use.yaml"))
        if use:
            cls.SAMPLES["knowledge-use"] = use[-1]
        cls.fences: dict[str, str] = {}
        for report in sorted(out.glob("*/cases/*/*/artifact/*/reports/verifier.report.*.md"))[-3:]:
            text = report.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"```ya?ml\r?\n(.*?)\r?\n```", text, re.S)
            if m:
                cls.fences[f"verifier 报告围栏 {report.parent.parent.name}"] = m.group(1)
                break

    def both(self, text: str) -> tuple[object, object]:
        probe = ("import {pathToFileURL} from 'node:url';"
                 "import {createRequire} from 'node:module';"
                 "const { parseYaml } = await import(pathToFileURL(process.argv[1]).href);"
                 "const YAML = createRequire(process.argv[2])('yaml');"
                 "const text = process.argv[3];"
                 "process.stdout.write(JSON.stringify([parseYaml(text), YAML.parse(text) ?? {}]));")
        proc = node_json(probe, str(READER), str(HARNESS_PKG), text)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return tuple(json.loads(proc.stdout))

    def test_each_sample_reads_deep_equal(self) -> None:
        samples = {k: p.read_text(encoding="utf-8", errors="replace") for k, p in self.SAMPLES.items()}
        samples.update(self.fences)
        self.assertIn("framework 契约模板", samples)
        for name, text in samples.items():
            with self.subTest(sample=name):
                ours, theirs = self.both(text)
                self.assertEqual(theirs, ours)
                self.assertTrue(ours, f"{name} 读成了空对象")


class WithoutTheHarness(unittest.TestCase):
    """扩展拷到一个没有 `framework/harness` 的工程根：第一次解析抛错，文案给安装命令。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "bare"
        (self.root / "doc" / "extensions" / "hooks" / "shared").mkdir(parents=True)
        (self.root / "framework.config.json").write_text("{}", encoding="utf-8")
        shutil.copy(READER, self.root / "doc" / "extensions" / "hooks" / "shared" / "yaml.mjs")

    def test_the_first_parse_says_how_to_install(self) -> None:
        probe = ("import {pathToFileURL} from 'node:url';"
                 "const m = await import(pathToFileURL(process.argv[1]).href);"
                 "process.stdout.write('imported;');"
                 "try { m.parseYaml('a: 1'); process.stdout.write('NO-ERROR'); }"
                 "catch (e) { process.stdout.write(String(e.message)); }")
        proc = node_json(probe, str(self.root / "doc" / "extensions" / "hooks" / "shared" / "yaml.mjs"))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(proc.stdout.startswith("imported;"), "读取器不可用不该在 import 时就崩")
        self.assertNotIn("NO-ERROR", proc.stdout)
        self.assertIn("npm install", proc.stdout)
        self.assertIn("framework", proc.stdout)


if __name__ == "__main__":
    unittest.main()
