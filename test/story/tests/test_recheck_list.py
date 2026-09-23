"""回看清单：十章齐后作者逐条处置的对象，由脚本枚举与定位，不判去向。

清单五类各有确定的来源——初筛表里「还要核实」那一格非空的行、决策登记的未决与已定、
骨架里的 `待核：` 行、正文里每张图所在的节。这一组锁的是「枚举对不对得上来源」：
表外的行、占位的「—」不算疑点；图按它所在的节定位。

测不了的是作者处置得对不对——那归独立审查拿同一张清单复核。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story"
CONTRACT = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "contracts" / "story-chapters.json"
PLAN_FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes" / "R01-verdict-echo"
                / "good" / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-template.md")

ANALYSIS = """# 需求分析

## ⑥ 来源初筛

| 来源位置 | 对本需求的作用 | 还要核实的矛盾或缺口 | 不适用的依据 |
|---|---|---|---|
| RR §2 流程 | 两条路径 | — | — |
| SR §3 接口 | 四个接口 | 修改设置走哪个接口没写 | — |
| SR §4 失败 | 失败分支 | 超时后谁重试两份材料说法不同 |  |

## 其它

| 来源位置 | 还要核实的矛盾或缺口 |
|---|---|
| 不该算 | 这一行不在初筛表里 |
"""
DECISIONS = {"decisions": [
    {"id": "DEC-1", "status": "open", "title": "超时后由谁发起重试"},
    {"id": "DEC-2", "status": "settled", "title": "本机只保存到提交成功"},
]}
STORY = ("# AR1 甲需求\n\n## 业务流程\n\n### 总览\n\n先说一句这张图讲什么。\n\n"
         "```mermaid\ngraph TD\nA-->B\n```\n\n## 功能说明\n\n正文，没有图。\n\n"
         "```text\n不是图\n```\n")


def with_chapter(text: str, chapter_id: str, block: str) -> str:
    start = text.index(f"### {chapter_id}\n")
    nxt = text.find("\n### ", start + 1)
    end = len(text) if nxt < 0 else nxt + 1
    return text[:start] + f"### {chapter_id}\n{block.strip()}\n\n" + text[end:]


class TheListComesFromItsSources(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        src = self.root / "AR" / "story-src"
        src.mkdir(parents=True)
        (src / "init-analysis.md").write_text(ANALYSIS, encoding="utf-8")
        (src / "decisions.json").write_text(json.dumps(DECISIONS, ensure_ascii=False), encoding="utf-8")
        plan = PLAN_FIXTURE.read_text(encoding="utf-8")
        plan = with_chapter(plan, "02-terms", "- 本章主线：解释等待态\n- 待核：等待态这个词评审人认不认得")
        plan = with_chapter(plan, "06-features", "- 本章主线：x\n#### 本地数据\n- 待核：保存多久由谁定")
        (src / "story-template.md").write_text(plan, encoding="utf-8")
        (self.root / "AR" / "story.md").write_text(STORY, encoding="utf-8")

    def items(self) -> dict:
        script = (
            "import {pathToFileURL} from 'node:url'; import * as fs from 'node:fs';"
            "import * as path from 'node:path';"
            "const [core, contractPath, root] = process.argv.slice(1);"
            "const recheck = await import(pathToFileURL(path.join(core, 'recheck.mjs')).href);"
            "const wp = await import(pathToFileURL(path.join(core, 'writing-plan.mjs')).href);"
            "const src = path.join(root, 'AR', 'story-src');"
            "const ctx = {contract: JSON.parse(fs.readFileSync(contractPath, 'utf-8')), featureRoot: root,"
            " srcDir: src, decisionsPath: path.join(src, 'decisions.json'),"
            " templatePath: path.join(src, 'story-template.md'), storyPath: path.join(root, 'AR', 'story.md')};"
            "const story = fs.readFileSync(ctx.storyPath, 'utf-8');"
            "const items = recheck.recheckItems(ctx, wp.readWritingPlan(ctx), story);"
            "process.stdout.write(JSON.stringify({items, rows: recheck.recheckRows(items)}));")
        proc = subprocess.run(["node", "--input-type=module", "-e", script, "--",
                               str(CORE), str(CONTRACT), str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=60, cwd=str(REPO_ROOT))
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def of(self, got: dict, kind: str) -> list[dict]:
        return [i for i in got["items"] if i["kind"] == kind]

    def test_each_kind_matches_its_source(self) -> None:
        got = self.items()
        doubts = self.of(got, "初筛疑点")
        self.assertEqual(["SR §3 接口", "SR §4 失败"], [d["where"] for d in doubts])
        self.assertEqual("修改设置走哪个接口没写", doubts[0]["text"])
        self.assertEqual([("DEC-1", "超时后由谁发起重试")],
                         [(d["where"], d["text"]) for d in self.of(got, "未决")])
        self.assertEqual(["DEC-2"], [d["where"] for d in self.of(got, "已定取舍")])
        self.assertEqual({("02-terms", "等待态这个词评审人认不认得"), ("06-features·本地数据", "保存多久由谁定")},
                         {(d["where"], d["text"]) for d in self.of(got, "骨架待核")})
        self.assertEqual(["业务流程·总览"], [d["where"] for d in self.of(got, "图")])

    def test_rows_ask_the_two_questions_and_do_not_judge(self) -> None:
        rows = "\n".join(self.items()["rows"])
        self.assertIn("这句话材料里有吗", rows)
        self.assertIn("材料给的靠得住吗", rows)
        self.assertNotIn("不该算", rows, "初筛表之外的行被当成了疑点")
        self.assertIn("[未决] DEC-1：超时后由谁发起重试", rows)

    def test_nothing_to_list_is_said_plainly(self) -> None:
        for name in ("init-analysis.md", "decisions.json", "story-template.md"):
            (self.root / "AR" / "story-src" / name).unlink()
        (self.root / "AR" / "story.md").write_text("# AR1\n\n## 背景\n\n正文。\n", encoding="utf-8")
        got = self.items()
        self.assertEqual([], got["items"])
        self.assertIn("这句话材料里有吗", "\n".join(got["rows"]))


if __name__ == "__main__":
    unittest.main()
