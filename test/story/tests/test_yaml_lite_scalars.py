"""标量的词法：引号与行尾注释各管各的。

`yaml-lite` 是机制里唯一的 YAML 读取器，manifest 的字段值经它出来之后要参加**相等判断**
——adapt 靠 `name` 判来源是替身包还是业务仓，判错的那一边会把目标的对接实现覆盖成替身。
多带一对引号就足以把判断带向相反的一边。

所以这一份锁的是「同一个值的几种合法写法读出来一样」：引号包裹、行尾注释、两者组合，
以及引号里的 `#` 仍是内容。不扩到本机制用不到的 YAML 特性（转义、锚点、多文档）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_LITE = REPO_ROOT / "doc" / "extensions" / "hooks" / "shared" / "yaml-lite.mjs"

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
    # 引号没收尾就不是引号标量，原样留着——猜不如照实给
    ('name: "unclosed', '"unclosed'),
    ('name: ""', ""),
]


class ScalarLexing(unittest.TestCase):
    """跑真的读取器，不在这里重实现一份判断。"""

    def setUp(self) -> None:  # noqa: D102
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def parse(self, line: str):
        probe = (
            "const { parseYaml } = await import(process.argv[1]);"
            "process.stdout.write(JSON.stringify(parseYaml(process.argv[2]) ?? null));"
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", probe, YAML_LITE.resolve().as_uri(), line],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_equivalent_spellings_read_the_same(self) -> None:
        for line, want in CASES:
            with self.subTest(line=line):
                self.assertEqual(want, self.parse(line).get("name"))

    def test_a_quoted_value_with_a_trailing_comment_carries_no_quotes(self) -> None:
        """这一条单拎出来：它是 adapt 判来源时踩过的那个形态。

        `"值" # 说明` 两头不对称，按「整串被引号包裹」判会落到剥注释那一支，
        剥完却不再处理引号——读出来多带一对引号，而下游拿它做相等判断。
        """
        got = self.parse('name: "wallet-sdk-demo"  # 发布源')["name"]
        self.assertEqual("wallet-sdk-demo", got)
        self.assertNotIn('"', got, "值里还留着引号——相等判断会走向相反的一边")


if __name__ == "__main__":
    unittest.main()
