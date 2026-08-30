# -*- coding: utf-8 -*-
"""必答集口径绑定：扩展侧（JS）与测试域侧（Python）必须派生出同一个集合。

两边各有各的用处——JS 那份给 verifier 注入清单、给阶段门禁核对；Python 这份在测试域
对真实目标跑回归。同一个口径写两遍，改了一边忘另一边就会出现「注入 14 行、只核 11 行」，
而两边各自都是绿的。这个测试就是那根绳子：口径一动，它先红。

**数据源是 spec §10「规约约束要求」表本身**。上一版两边都读 ``AR/story-src/knowledge.json``，
那是同一批结论的第二份写法——两处判定对不上时评审者无从知道哪个是准的，所以它退场了。
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

JS_MODULE = REPO / "doc" / "extensions" / "hooks" / "shared" / "verdict-set.mjs"

SPEC_MD = """# 甲需求规格

## 9. 技术契约

| 名称 | 说明 |
|---|---|
| createBusinessOrder | 下单接口 |

## 10. 规约约束要求

| 编号 | 本需求的要求 | 落点契约名 |
|---|---|---|
| UX-01 | 弹窗方向性参数只用 start/end | OrderSheet |
| OBS-01 | 六步骤每步进入与结果都记日志 | OrderFlowLogger |
| `SEC-01` | 敏感字段出口前脱敏 | OrderCloudAdapter |

## 11. 设计模式候选登记

| 适用单元 | 候选 | 信号 |
|---|---|---|
| 主流程 | decision-tree | 多分支多步 |
"""


class TestAdjudicationParity(unittest.TestCase):
    def test_js_and_python_derive_the_same_keys(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            feature = Path(d) / "doc" / "features" / "AR90001"
            (feature / "spec").mkdir(parents=True)
            (feature / "spec" / "spec.md").write_text(SPEC_MD, encoding="utf-8")

            py_keys = check_failure_modes.adjudication_keys(SPEC_MD)

            # Windows 上 ESM 只认 file:// URL，绝对盘符路径会被当成协议名
            script = (
                "import { adjudicationSet, adjudicationKeys } from "
                f"{json.dumps(JS_MODULE.as_uri())};\n"
                f"const r = adjudicationSet({json.dumps(str(Path(d)))}, 'AR90001', 'spec');\n"
                "if (r.error) { console.error(r.error); process.exit(1); }\n"
                "console.log(JSON.stringify(adjudicationKeys(r.rows)));\n"
            )
            r = subprocess.run(
                [_node(), "--input-type=module", "-e", script],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=str(REPO),
            )
            self.assertEqual(r.returncode, 0, f"JS 侧派生失败：{(r.stderr or '')[:400]}")
            js_keys = json.loads(r.stdout.strip().splitlines()[-1])

            self.assertEqual(js_keys, py_keys,
                             "两侧必答集口径已分叉——改一边就要改另一边")
            self.assertEqual(py_keys, ["UX-01", "OBS-01", "SEC-01"],
                             "编号应逐条取到（含反引号包裹的那条），且保持表内顺序")

    def test_missing_exit_chapter_yields_empty(self) -> None:
        """没有 §10 章时返回空集——**空集不是通过**，调用方须自己出声（G7）。"""
        self.assertEqual(check_failure_modes.adjudication_keys("# 只有标题\n"), [])


def _node() -> str:
    return "node"


if __name__ == "__main__":
    unittest.main()
