"""评审记录渲染：用本文件里的中性登记表核 review 的结构、人工区与字段诊断。

结构预期按评审记录合同写出，不从渲染结果反推：
- 待确认在前、已定在后；
- 每类成一节，节号、项号按登记顺序编；
- 议题标题是陈述句；
- 澄清正文按加粗段首分段，之后一行「请<角色>评审。」；
- 三态加修改意见的人工区不预选，最后是议题锚。

金样正本的文件身份由 `test_golden_sample.py` 登记，本文件不读金样。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import HUMAN_ZONE, open_decision, settled_decision  # noqa: E402
from ext_workspace import DEV_EXT  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = DEV_EXT / "skills/story/scripts/core/story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "REQ-DEMO"


def neutral_decisions() -> list[dict]:
    """会议室预订的五条议题：三条待确认、两条已定，类别交错；D5 与 D1 同状态同类别，登记在别的类别之后。"""
    return [
        open_decision("D1", "超时未签到的预订是否自动释放待定",
                      "预订开始后十五分钟没人签到，会议室要不要自动放给别人。",
                      [("自动释放并通知预订人", "空置减少；预订人迟到时会被占走"),
                       ("保留到预订结束", "迟到的人照常能用；空置时间更长")],
                      "选择方案 1；行政确认迟到投诉可接受后定稿。",
                      category="业务规则", decider="行政负责人"),
        settled_decision("D2", "预订记录只对本部门可见",
                         "其他部门能不能看到某间会议室被谁预订。", "预订人姓名只对本部门显示，其他部门只看到已占用。",
                         said="别的部门看到占用就行，看不到人名", who="安全负责人在评审会上",
                         category="数据与隐私", decider="安全负责人"),
        open_decision("D3", "新功能先对哪几层楼开放待定",
                      "灰度时先开哪几层楼。",
                      [("先开一层楼", "问题暴露面小；样本少"),
                       ("全楼同时开", "样本足；出问题影响全楼")],
                      "选择方案 1。", category="上线与开关", decider="运维负责人"),
        settled_decision("D4", "同一时段同一会议室只能有一条预订",
                         "两人同时提交同一时段时以谁为准。", "以先到服务器的为准，后到的提示已被占用。",
                         said="先到先得", category="业务规则", decider="产品负责人"),
        open_decision("D5", "跨楼层预订是否需要审批待定",
                      "预订别的楼层的会议室要不要先经那层的行政同意。",
                      [("需要审批", "各层自己的会议室不被占满；预订多一步"),
                       ("不需要审批", "预订最快；楼层之间可能抢会议室")],
                      "选择方案 2；冲突多了再加审批。", category="业务规则", decider="行政负责人"),
    ]


ZONE = ["评审结论：", "- [ ] 同意", "- [ ] 需修改", "- [ ] 暂缓", "修改意见："]
OPEN_HEADS = ["**决策点**：", "**可选的做法**：", "**建议**："]
SETTLED_HEADS = ["**决策点**：", "**依据**：", "**结论与影响**："]

#: 上面五条按合同应渲成的骨架：章、节、项的标题与编号，各项的段首、人工区与锚。
#: D5 登记在 D3、D4 之后，仍回到 D1 所在的「业务规则」节，项号接着递增为 1.1.2
EXPECTED_SKELETON = [
    "## 1. 待确认事项",
    "### 1.1 业务规则",
    "#### 1.1.1 D1 超时未签到的预订是否自动释放待定", *OPEN_HEADS,
    "请行政负责人评审。", *ZONE, "<!-- decision: D1 -->",
    "#### 1.1.2 D5 跨楼层预订是否需要审批待定", *OPEN_HEADS,
    "请行政负责人评审。", *ZONE, "<!-- decision: D5 -->",
    "### 1.2 上线与开关",
    "#### 1.2.1 D3 新功能先对哪几层楼开放待定", *OPEN_HEADS,
    "请运维负责人评审。", *ZONE, "<!-- decision: D3 -->",
    "## 2. 已定事项",
    "### 2.1 数据与隐私",
    "#### 2.1.1 D2 预订记录只对本部门可见", *SETTLED_HEADS,
    "请安全负责人评审。", *ZONE, "<!-- decision: D2 -->",
    "### 2.2 业务规则",
    "#### 2.2.1 D4 同一时段同一会议室只能有一条预订", *SETTLED_HEADS,
    "请产品负责人评审。", *ZONE, "<!-- decision: D4 -->",
    "## 3. 其他意见",
]


def skeleton(text: str) -> list[str]:
    """review 里的结构行：编号标题、段首小标题、请谁评审、人工区五行、议题锚。机器标记里的摘要不比。"""
    keep = re.compile(r"^(#{2,4} \d|\*\*[^*]+\*\*：|请.+评审。$|评审结论：|- \[ \] |修改意见：|<!-- decision: )")
    out = []
    for line in text.split("\n"):
        if keep.match(line):
            out.append(line.split("：", 1)[0] + "：" if line.startswith("**") else line)
    return out


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


class RenderFollowsTheContract(RendererCase):
    def test_open_before_settled_numbered_in_registration_order(self) -> None:
        self.write_decisions(neutral_decisions())
        proc = self.run_build()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(EXPECTED_SKELETON, skeleton(self.review.read_text(encoding="utf-8")))

    def test_each_entry_carries_its_text_and_an_empty_human_zone(self) -> None:
        """已定与待定的机器区按形态不同，人工区是同一个样子：三态与修改意见，不预选。"""
        entries = neutral_decisions()
        self.write_decisions(entries)
        self.assertEqual(0, self.run_build().returncode)
        out = self.review.read_text(encoding="utf-8")
        for entry in entries:
            with self.subTest(entry["id"]):
                self.assertIn(entry["clarification"], out)
                self.assertIn(f"请{entry['decider']}评审。\n\n{HUMAN_ZONE}\n"
                              f"<!-- decision: {entry['id']} -->", out)
        self.assertNotIn("- [x]", out, "替人预选了")
        self.assertIn("## 3. 其他意见", out)

    def test_a_single_settled_entry_has_no_open_items(self) -> None:
        """条目数与类别都跟着登记表走：只有一条已定时，待确认章下没有议题。"""
        self.write_decisions([neutral_decisions()[1]])
        self.assertEqual(0, self.run_build().returncode)
        lines = skeleton(self.review.read_text(encoding="utf-8"))
        self.assertEqual(["### 2.1 数据与隐私", "#### 2.1.1 D2 预订记录只对本部门可见"],
                         [x for x in lines if x.startswith("###")])


class HumanZoneSurvivesRerender(RendererCase):
    def test_what_the_reviewer_wrote_is_kept_byte_for_byte(self) -> None:
        entries = neutral_decisions()[:2]
        self.write_decisions(entries)
        self.assertEqual(0, self.run_build().returncode)
        said = "修改意见：释放前先给预订人推一次提醒。"
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
        self.write_decisions(neutral_decisions())
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
                entry = dict(neutral_decisions()[0])
                entry[field] = ""
                self.write_decisions([entry])
                code, out = self.run_check()
                self.assertEqual(1, code, out)
                self.assertIn(needle, out)

    def test_a_category_outside_the_word_list_is_named(self) -> None:
        """类别决定它成章落在哪一节——不在词表里，成章就成不出自然名。"""
        entry = dict(neutral_decisions()[0])
        entry["category"] = "我自己起的类别"
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("不在词表里", out)

    def test_a_missing_category_is_named(self) -> None:
        entry = dict(neutral_decisions()[0])
        entry.pop("category")
        self.write_decisions([entry])
        code, out = self.run_check()
        self.assertEqual(1, code, out)
        self.assertIn("类别", out)

    def test_the_word_list_is_a_map_not_a_quota(self) -> None:
        """决策类别是词表：机器不判每类有没有条目、不判空类要不要解释。"""
        self.write_decisions([e for e in neutral_decisions() if e["category"] == "业务规则"])
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
