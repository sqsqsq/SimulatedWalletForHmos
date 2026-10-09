"""Review 渲染回归：小型明确输入渲出确定的结构，人写在人工区里的内容重渲染时一个字节不动。

输入是四条中性议题（两条待定、两条已定，跨三个类别）。本文件守：

  ① 状态分章、类别分节、议题编号与 D 编号、段首小标题、人工区五行、议题锚，与预期结构一致；
  ② 已定与待定共用同一个人工区，不替人预选；
  ③ 人工区逐字节保留，分组与排序变了 D 编号随议题走，重复渲染不变；
  ④ 字段缺失与类别越出词表时 check 点名，不设类别配额与数量下限。

审定过的 Review 金样只由 test_golden_sample 守指纹，不进渲染回归。
"""
from __future__ import annotations

import copy
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
from ext_workspace import DEV_EXT

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = DEV_EXT / "skills/story/scripts/core/story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "REQ-DEMO"

#: 登记表输入：待定议题写决策点、依据、可选的做法（做法——后果）、建议、理由；已定议题写决策点、依据（引人原话）、结论与影响。
SAMPLE = [
    {"id": "D1", "status": "open", "review_mode": "choice", "category": "依赖与承载", "decider": "端侧负责人",
     "title": "预约接口就绪前先用模拟数据验证端侧交互",
     "clarification": "**决策点**：预约服务的接口还不可用，端侧怎样先行验证。\n\n**依据**：接口约定已给出，服务端实现排在下一迭代。\n\n"
                      "**可选的做法**：\n\n1. 先按接口约定用模拟数据验证端侧交互——端侧可先交付，验收只到本地模拟\n"
                      "2. 等接口就绪再交付端侧——端侧交付推迟到下一迭代\n\n"
                      "**建议**：选择方案 1。\n\n**理由**：端侧交互不依赖服务端实现即可验证，联调另行验收。"},
    {"id": "D2", "status": "open", "review_mode": "choice", "category": "业务规则", "decider": "产品负责人",
     "title": "预约提交超时后多久允许重新提交",
     "clarification": "**决策点**：提交超时、结果未知时，用户多久之后可以再提交。\n\n**依据**：材料只写了超时提示，没写重新提交的间隔。\n\n"
                      "**可选的做法**：\n\n1. 先查询预约结果，查到之前不允许重提——行为多一步查询，不会重复预约\n"
                      "2. 固定等待一段时间后允许重提——行为更简单，验收要覆盖重复预约\n\n"
                      "**建议**：选择方案 1。\n\n**理由**：结果未知时重提可能产生两条预约。"},
    {"id": "D3", "status": "settled", "review_mode": "confirm", "category": "业务规则", "decider": "产品负责人",
     "title": "同一时段只能有一条有效预约",
     "clarification": "**决策点**：同一用户在同一时段重复预约怎么处理。\n\n**依据**：评审会上产品负责人说「同一时段只保留一条，重复的直接返回已有那条」。\n\n"
                      "**结论与影响**：服务端按用户与时段判重，重复提交返回已有预约。"},
    {"id": "D4", "status": "settled", "review_mode": "confirm", "category": "上线与开关", "decider": "运营负责人",
     "title": "预约功能开关只管新预约",
     "clarification": "**决策点**：关闭预约开关后，已有预约怎么处理。\n\n**依据**：评审会上运营负责人说「开关关了只是不能新约，已经约好的照常」。\n\n"
                      "**结论与影响**：开关只控制新建入口，已有预约照常可查看与取消。"},
]


OPEN_HEADS = ["**决策点**：", "**依据**：", "**可选的做法**：", "**建议**：", "**理由**："]
SETTLED_HEADS = ["**决策点**：", "**依据**：", "**结论与影响**："]


def _entry(heading: str, heads: list[str], decision: str) -> list[str]:
    return [heading, *heads, "评审结论：", "- [ ] 同意", "- [ ] 需修改", "- [ ] 暂缓", "修改意见：",
            f"<!-- decision: {decision} -->"]


#: SAMPLE 渲出的结构：状态分章（待确认在前），类别按词表次序分节，节内按登记次序编号，标题带 D 编号。
EXPECTED = [
    "## 1. 待确认事项",
    "### 1.1 依赖与承载",
    *_entry("#### 1.1.1 D1 预约接口就绪前先用模拟数据验证端侧交互", OPEN_HEADS, "D1"),
    "### 1.2 业务规则",
    *_entry("#### 1.2.1 D2 预约提交超时后多久允许重新提交", OPEN_HEADS, "D2"),
    "## 2. 已定事项",
    "### 2.1 业务规则",
    *_entry("#### 2.1.1 D3 同一时段只能有一条有效预约", SETTLED_HEADS, "D3"),
    "### 2.2 上线与开关",
    *_entry("#### 2.2.1 D4 预约功能开关只管新预约", SETTLED_HEADS, "D4"),
    "## 3. 其他意见",
]


def sample() -> list[dict]:
    """用例会改条目，每次给一份新的。"""
    return copy.deepcopy(SAMPLE)


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


class RenderMatchesExpected(RendererCase):
    @staticmethod
    def structure(text: str) -> list[str]:
        """按结构比：章节与议题标题（含编号）、段首小标题、人工区五行、议题锚。机器标记里的摘要不比。"""
        keep = re.compile(r"^(#{2,4} |\*\*[^*]+\*\*：|评审结论：|- \[ \] |修改意见：|<!-- decision: )")
        return [line.split("：", 1)[0] + "：" if line.startswith("**") else line
                for line in text.split("\n") if keep.match(line)]

    def test_the_rendered_structure_matches_the_expected(self) -> None:
        self.write_decisions(sample())
        proc = self.run_build()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(EXPECTED, self.structure(self.review.read_text(encoding="utf-8")))

    def test_a_settled_and_an_open_entry_share_one_human_zone(self) -> None:
        """已定与待定的机器区按形态不同，人工区是同一个样子：三态与修改意见，不预选。"""
        entries = sample()
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
        entries = sample()[:2]
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

    def test_the_visible_id_follows_its_entry_when_the_order_changes(self) -> None:
        """标题里的 D 编号是议题自己的：分组与排序变了，章节号跟着变，D 编号随议题走，人工区一个字节不动。"""
        entries = sample()
        self.write_decisions(entries)
        self.assertEqual(0, self.run_build().returncode)
        said = "修改意见：这一条按会上的结论改。"
        target = entries[-1]
        anchor = "<!-- decision: {} -->".format(target["id"])
        text = self.review.read_text(encoding="utf-8")
        self.review.write_text(text.replace("修改意见：\n\n" + anchor, said + "\n\n" + anchor, 1),
                               encoding="utf-8")

        # 最后一条挪到最前、换进另一条已定议题的类别：分组与组内次序都变，它的章节号必然变
        other = next(e for e in entries if e["status"] == target["status"] and e["category"] != target["category"])
        moved = dict(target, category=other["category"])
        self.write_decisions([moved, *entries[:-1]])
        self.assertEqual(0, self.run_build().returncode)
        after = self.review.read_text(encoding="utf-8")
        for entry in [moved, *entries[:-1]]:
            with self.subTest(id=entry["id"]):
                heads = [line for line in after.split("\n")
                         if line.startswith("#### ") and line.endswith(" " + entry["title"])]
                self.assertEqual(1, len(heads), entry["title"])
                self.assertRegex(heads[0], r"^#### \d+\.\d+\.\d+ " + entry["id"] + " ")
        self.assertIn(said + "\n\n" + anchor, after)
        self.assertEqual(0, self.run_build().returncode)
        self.assertEqual(after, self.review.read_text(encoding="utf-8"))

    def test_rerender_is_idempotent(self) -> None:
        """连渲两次要一模一样——不然计划外意见区每 build 一次就多一个空行。"""
        self.write_decisions(sample())
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
                entry = dict(sample()[0])
                entry[field] = ""
                self.write_decisions([entry])
                code, out = self.run_check()
                self.assertEqual(1, code, out)
                self.assertIn(needle, out)

    def test_a_category_outside_the_word_list_is_named(self) -> None:
        """类别决定它成章落在哪一节——不在词表里，成章就成不出自然名。"""
        entry = dict(sample()[0])
        entry["category"] = "我自己起的类别"
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("不在词表里", out)

    def test_a_missing_category_is_named(self) -> None:
        entry = dict(sample()[0])
        entry.pop("category")
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("类别", out)

    def test_the_word_list_is_a_map_not_a_quota(self) -> None:
        """决策类别是词表：机器不判每类有没有条目、不判空类要不要解释。"""
        entries = [e for e in sample() if e["category"] == SAMPLE[0]["category"]]
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
