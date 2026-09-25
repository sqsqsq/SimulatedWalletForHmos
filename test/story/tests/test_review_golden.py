"""review 金样是评审记录的效果定义——渲染器渲不出它，改的是渲染器。

形态从金样正推：带序号的陈述句标题、带小标题分段的正文、一行「请<角色>评审。」、
三态加修改意见的人工区。本文件守三件事：

  ① 金样一个字节没变（指纹）；
  ② 拿金样自己的条目倒推登记表，`build` 渲出来的与金样**逐字节相同**；
  ③ 人写在人工区里的内容，重渲染时一个字节不动。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import HUMAN_ZONE  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = REPO_ROOT / "test" / "story" / "golden" / "review-金样-AR90006.md"
BUILD = REPO_ROOT / "doc/extensions/skills/story/scripts/core/story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "REQ-DEMO"

#: 2026-09-26 按现行载体重立（三态人工区、议题形态随状态、通用决策类别）。sha256 前 16 位。
FINGERPRINT = "33089aeaf423a229"
HUMAN_ZONE_HEAD = "评审结论："


def golden_body() -> str:
    """金样的正文——顶部那段 HTML 注释是它自己的效果口径，不是渲染产物。"""
    text = GOLDEN.read_text(encoding="utf-8")
    return text[text.index("# 评审记录"):]


def parse_golden() -> list[dict]:
    """把金样倒推成登记表。

    倒推而不是另写一份样本：另写一份就有了第二个真源。三级分层各承载一个字段：
    一级章名给 `status`、二级章名给 `category`、三级标题给 `title`；「请…评审。」之前是
    `clarification`，之后是人工区。形态由状态定：待确认是 choice，已定是 confirm。
    """
    out: list[dict] = []
    status, category, cur = "open", "", None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            cur["clarification"] = "\n".join(cur["clarification"]).strip()
            out.append(cur)
        cur = None

    for line in golden_body().split("\n"):
        if line.startswith("## "):
            flush()
            status = "settled" if "已定事项" in line else "open"
            continue
        if line.startswith("### "):
            flush()
            category = re.sub(r"^###\s+\d+(?:\.\d+)*\s+", "", line).strip()
            continue
        if line.startswith("#### "):
            flush()
            cur = {"id": "", "status": status, "category": category,
                   "review_mode": "confirm" if status == "settled" else "choice",
                   "title": re.sub(r"^####\s+\d+(?:\.\d+)*\s+", "", line).strip(),
                   "clarification": [], "decider": ""}
            continue
        if cur is None:
            continue
        ask = re.fullmatch(r"请(.+)评审。", line.strip())
        if ask:
            cur["decider"] = ask.group(1)
            continue
        mark = re.fullmatch(r"<!-- decision: (\S+) -->", line.strip())
        if mark:
            cur["id"] = mark.group(1)
            continue
        if cur["decider"]:
            continue                      # 「请…评审。」之后到锚之间是人工区
        cur["clarification"].append(line)
    flush()
    return out


class ReviewGoldenIsFrozen(unittest.TestCase):
    def test_fingerprint(self) -> None:
        self.assertTrue(GOLDEN.is_file(), "review 金样正本不存在")
        actual = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()[:16]
        self.assertEqual(FINGERPRINT, actual,
                         "review 金样变了——只有维护者能改，改了要同步这里的指纹")

    def test_it_parses_into_ten_entries(self) -> None:
        """倒推得出的登记表要真的有内容——解析坏掉时下面两条会静默空转。"""
        entries = parse_golden()
        self.assertTrue(entries, "金样倒推不出登记表")
        self.assertTrue(all(e["title"] and e["clarification"] and e["decider"]
                            for e in entries))
        self.assertIn("settled", {e["status"] for e in entries})
        self.assertIn("open", {e["status"] for e in entries})


class RendererCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        self.review = self.root / "doc" / "features" / FEATURE / "AR" / "review.md"

    def write_decisions(self, decisions: list[dict]) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": decisions}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def run_build(self, command: str = "build") -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(BUILD), command, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


class RenderMatchesGolden(RendererCase):
    """渲染器渲不出金样，改的是渲染器。"""

    def test_whole_document_is_byte_identical(self) -> None:
        self.write_decisions(parse_golden())
        proc = self.run_build()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(golden_body(), self.review.read_text(encoding="utf-8"))

    def test_a_settled_and_an_open_entry_share_one_human_zone(self) -> None:
        """已定与待定的机器区按形态不同，人工区是同一个样子：三态与修改意见，不预选。"""
        entries = parse_golden()
        pick = [next(e for e in entries if e["status"] == "settled"),
                next(e for e in entries if e["status"] == "open")]
        self.write_decisions(pick)
        self.assertEqual(0, self.run_build().returncode)
        out = self.review.read_text(encoding="utf-8")
        self.assertIn("## 1. 待确认事项", out)
        self.assertIn("## 2. 已定事项", out)
        for entry in pick:
            self.assertIn(f"{entry['title']}\n", out)
            self.assertIn(entry["clarification"], out)
            self.assertIn(f"请{entry['decider']}评审。\n\n{HUMAN_ZONE}\n"
                          f"<!-- decision: {entry['id']} -->", out)
        self.assertNotIn("- [x]", out, "替人预选了")


class HumanZoneSurvivesRerender(RendererCase):
    def test_what_the_reviewer_wrote_is_kept_byte_for_byte(self) -> None:
        entries = parse_golden()[:2]
        self.write_decisions(entries)
        self.assertEqual(0, self.run_build().returncode)
        said = "修改意见：页面要显示这个数是云侧给的。"
        anchor = "<!-- decision: {} -->".format(entries[0]["id"])
        text = self.review.read_text(encoding="utf-8")
        self.review.write_text(
            text.replace("修改意见：\n\n" + anchor, said + "\n\n" + anchor, 1),
            encoding="utf-8")

        # 登记表改了（标题换一个字），机器区该重算，人工区不该动
        entries[0]["title"] = entries[0]["title"] + "（复议）"
        self.write_decisions(entries)
        self.assertEqual(0, self.run_build().returncode)
        after = self.review.read_text(encoding="utf-8")
        self.assertIn(said, after)
        self.assertIn("（复议）", after)

    def test_rerender_is_idempotent(self) -> None:
        """连渲两次要一模一样——不然计划外意见区每 build 一次就多一个空行。"""
        self.write_decisions(parse_golden())
        self.assertEqual(0, self.run_build().returncode)
        once = self.review.read_text(encoding="utf-8")
        self.assertEqual(0, self.run_build().returncode)
        self.assertEqual(once, self.review.read_text(encoding="utf-8"))


class FieldsAreRequired(RendererCase):
    """三个字段缺一条，渲染出来就是半个议题——check 要点名，不是渲个空格出去。"""

    def run_check(self) -> tuple[int, str]:
        proc = self.run_build("check")
        return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()

    def test_each_missing_field_is_named(self) -> None:
        for field, needle in (("title", "陈述句标题"),
                              ("clarification", "澄清正文"),
                              ("decider", "请谁评审")):
            with self.subTest(field=field):
                entry = dict(parse_golden()[0])
                entry[field] = ""
                self.write_decisions([entry])
                code, out = self.run_check()
                self.assertEqual(1, code, out)
                self.assertIn(needle, out)

    def test_a_category_outside_the_word_list_is_named(self) -> None:
        """类别决定它成章落在哪一节——不在词表里，成章就成不出自然名。"""
        entry = dict(parse_golden()[0])
        entry["category"] = "我自己起的类别"
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("不在词表里", out)

    def test_a_missing_category_is_named(self) -> None:
        entry = dict(parse_golden()[0])
        entry.pop("category")
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("类别", out)

    def test_the_word_list_is_a_map_not_a_quota(self) -> None:
        """决策类别是词表：机器不判每类有没有条目、不判空类要不要解释。"""
        entries = [e for e in parse_golden() if e["category"] == parse_golden()[0]["category"]]
        self.write_decisions(entries)
        _, out = self.run_check()
        for quota in ("每类", "空类", "十一类都要", "类别齐"):
            self.assertNotIn(quota, out, f"出现了按类别配额的判据：\n{out}")

    def test_no_quota_on_how_many_entries(self) -> None:
        """**不设数量下限**：凑数议题比零议题更坏，它把注意力摊薄在假议题上。

        夹具走到这一步还有别的判项没满足（分配没做完），所以不断言整体通过，
        断言的是**没有一条问题是冲着议题数量来的**——数量判据一加进来这里就会红。
        """
        self.write_decisions([])
        _, out = self.run_check()
        for quota in ("议题数", "至少", "条以上", "数量"):
            self.assertNotIn(quota, out, f"出现了议题数量判据：\n{out}")


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
