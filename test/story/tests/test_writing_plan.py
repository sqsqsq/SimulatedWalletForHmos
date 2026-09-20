"""写作设计的骨架：协议、草稿、提交核对、回看交接与随稿冻结。

`AR/story-src/story-template.md` 由作者写成骨架——每章一个 `### <章 ID>`，下面是正文将要有的
`####`/`#####` 小节、每节要答什么（`- ` 说明行）、以及用什么形式承载（`形式：`）与它表达什么（`- 描述：`）。
脚本只做确定的事：建空壳、读骨架、把骨架铺成草稿、提交时核骨架里的标题与表图在不在。
这一组锁住其中确定的那几件：

  ① 空壳与旧协议都不算设计过；骨架缺在哪一次报全、指得到位置；
  ② 没动过的草稿按骨架铺好标题、说明与表图；动过的一个字节不改，只给缺的起点；
  ③ 章提交与全篇 check 同一份核对：骨架里的标题、表、图正文都要有，正文可以多；
  ④ 十章齐后下一步是回看清单；设计随稿冻结，reopen 之后可以再改。

测不了的是骨架合不合理、作者照没照它把问题答清——那归回看、独立审查与真实运行。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_story_build import (  # noqa: E402
    BUILD, FEATURE, FLOW, PLAN_FIXTURE, REPO_ROOT, StoryBuildCase, ensure_flow_state, minimal_body,
)

CONTRACT_PATH = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "contracts" / "story-chapters.json"
PLAN_MODULE = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
               / "story" / "writing-plan.mjs")
BASE = PLAN_FIXTURE.read_text(encoding="utf-8")

#: 功能说明的一份中性骨架：本机数据一节带表，失败提示一节下面还有一小节。
FEATURES = ("- 本章主线：提交之后到回执之前用户看到什么\n"
            "#### 本地数据\n"
            "- 答：哪些数据存在本机、保存多久、何时清除\n"
            "- 待核：退出登录时是否清除待提交内容\n"
            "形式：表格\n"
            "- 描述：把每类本机数据与它的保存与清除时机对照起来\n"
            "#### 失败提示\n"
            "- 答：提交失败时用户看到什么、怎么继续\n"
            "##### 重试入口\n"
            "- 答：从哪里再次提交\n")
TABLE = ("### 本地数据\n\n| 数据 | 保存多久 | 何时清除 |\n|---|---|---|\n"
         "| 待提交内容 | 到提交成功 | 退出登录 |\n")
FAILURE = "### 失败提示\n\n提交失败时停在原页面并说明原因。\n\n#### 重试入口\n\n在原页面再次提交。\n"
FEATURES_BODY = "提交后界面停在等待态。\n\n" + TABLE + "\n" + FAILURE
#: 只有一节带表的骨架，给「已落盘的章改骨架」那一组用。
LOCAL = ("#### 本地数据\n- 答：本机数据的保存与清除\n形式：表格\n"
         "- 描述：本机数据与它的保存、清除时机对照\n")
#: 合同要求验收章有一张表；作者在骨架里只声明形式，列由写章时按内容定。
ACCEPTANCE = ["编号", "场景与前置", "可观察的通过条件", "主责"]
ACCEPTANCE_LINE = "形式：表格\n- 描述：每条验收一行，写清情形与可观察的通过条件"


def with_chapter(chapter_id: str, block: str, base: str | None = None) -> str:
    """最小设计里换掉一章的骨架。"""
    text = BASE if base is None else base
    start = text.index(f"### {chapter_id}\n")
    nxt = text.find("\n### ", start + 1)
    end = len(text) if nxt < 0 else nxt + 1
    return text[:start] + f"### {chapter_id}\n{block.strip()}\n\n" + text[end:]


def read_plan(text: str) -> dict:
    """直接调 `readWritingPlan`：协议判定是纯函数，不必为每种坏形状走一遍整条命令。"""
    script = (
        "import {pathToFileURL} from 'node:url'; import * as fs from 'node:fs';"
        "import * as os from 'node:os'; import * as path from 'node:path';"
        "const m = await import(pathToFileURL(process.argv[1]).href);"
        "const contract = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));"
        "const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-'));"
        "const file = path.join(dir, 'story-template.md');"
        "fs.writeFileSync(file, process.argv[3], 'utf-8');"
        "const plan = m.readWritingPlan({contract, featureRoot: dir, templatePath: file});"
        "fs.rmSync(dir, {recursive: true, force: true});"
        "process.stdout.write(JSON.stringify({problems: plan.problems, structures: plan.structures,"
        " rechecks: plan.rechecks, ids: [...plan.skeletons.keys()],"
        " acceptance: m.selectedStructure(plan, '08-acceptance'),"
        " features: m.selectedStructure(plan, '06-features')}));")
    proc = subprocess.run(["node", "--input-type=module", "-e", script, "--",
                           str(PLAN_MODULE), str(CONTRACT_PATH), text],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=60, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TheSkeletonIsReadInOnePlace(unittest.TestCase):
    """骨架缺在哪，一次报全、指得到位置；形状合法的标题、表、图原样交给核对与打底。"""

    def test_the_minimal_design_is_valid(self) -> None:
        got = read_plan(BASE)
        self.assertEqual([], got["problems"])
        ids = [c["id"] for c in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]]
        self.assertEqual(ids, got["ids"])
        self.assertEqual([], got["structures"], "只有说明行的骨架没有要脚本落实的表图")
        self.assertEqual([], got["rechecks"])

    def test_the_shell_is_not_a_design(self) -> None:
        script = (
            "import {pathToFileURL} from 'node:url'; import * as fs from 'node:fs';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "process.stdout.write(m.writingPlanShell(JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'))));")
        shell = subprocess.run(["node", "--input-type=module", "-e", script, "--",
                                str(PLAN_MODULE), str(CONTRACT_PATH)],
                               capture_output=True, text=True, encoding="utf-8", timeout=60).stdout
        self.assertIn("## 骨架", shell)
        problems = read_plan(shell)["problems"]
        self.assertTrue(problems, "空壳被当成了已经写好的设计")
        self.assertTrue(all("模板占位符" in p for p in problems), problems)

    def test_the_old_protocol_is_refused_without_being_read(self) -> None:
        """旧形态（章节安排 + 结构选择 JSON）不双读：报一次，说清按骨架重写。"""
        old = (BASE.replace("## 骨架", "## 章节安排")
               + "\n## 结构选择\n\n```json\n[{\"chapter\": \"06-features\", \"at\": \"\", \"kind\": \"diagram\"}]\n```\n")
        got = read_plan(old)
        self.assertEqual(1, len(got["problems"]), got["problems"])
        self.assertIn("旧协议", got["problems"][0])
        self.assertIn("按骨架协议重写", got["problems"][0])
        self.assertEqual([], got["structures"], "旧形态的 JSON 被读进来了")

    def test_each_broken_shape_is_located(self) -> None:
        cases = {
            "未知章 ID": (BASE.replace("### 03-scope", "### 03-范围"),
                       ["「### 03-范围」不是章节合同里的章 ID", "缺「### 03-scope」"]),
            "重复章 ID": (BASE.replace("### 03-scope", "### 02-terms\n- 又一段\n\n### 03-scope"),
                       ["「### 02-terms」出现了两次"]),
            "没有骨架": (with_chapter("02-terms", ""), ["「### 02-terms」没有骨架"]),
            "缺阅读主线": (BASE.replace("## 阅读主线", "## 读法"), ["缺「## 阅读主线」"]),
            "形式为空": (with_chapter("06-features", "#### 本地数据\n形式："),
                     ["「形式：（空）」不认识", "表格", "有序列表"]),
            "不认识的形式": (with_chapter("06-features", "#### 本地数据\n形式：随手画"),
                        ["「形式：随手画」不认识", "流程图", "时序图", "状态图"]),
            "旧表头写法": (with_chapter("06-features", "#### 本地数据\n表头：数据 | 何时清除"),
                       ["是上一版写法", "形式：<类型>"]),
            "旧图写法": (with_chapter("06-features", "#### 本地数据\n图：时序图"),
                     ["是上一版写法", "形式：<类型>"]),
            "形式写成说明行": (with_chapter("06-features", "#### 本地数据\n- 形式：表格"),
                         ["形式要单起一行"]),
            "不涉及还留小节": (with_chapter("06-features", "- 不涉及：没有功能变化\n#### 本地数据\n- 答：x"),
                          ["写了不涉及，却还留着"]),
            "五级标题没有上级": (with_chapter("06-features", "##### 重试入口\n- 答：x"),
                           ["前面没有 #### 小节"]),
            "小节重名": (with_chapter("06-features", "#### 本地数据\n- 答：x\n#### 本地数据\n- 答：y"),
                      ["「本地数据」重复"]),
            "不是骨架写法": (with_chapter("06-features", "#### 本地数据\n这一节讲本机数据。"),
                         ["不是骨架写法"]),
            "附录外小节": (with_chapter("10-appendix", "#### 补充说明\n- 答：x"), ["附录只有合同那几节"]),
        }
        for name, (text, needles) in cases.items():
            with self.subTest(case=name):
                problems = "\n".join(read_plan(text)["problems"])
                for needle in needles:
                    self.assertIn(needle, problems)

    def test_the_skeleton_carries_titles_forms_and_open_questions(self) -> None:
        block = FEATURES + "形式：时序图\n"          # 挂在「重试入口」这一小节下
        got = read_plan(with_chapter("06-features", block))
        self.assertEqual([], got["problems"])
        picks = [{k: v for k, v in s.items() if k != "index"} for s in got["structures"]]
        self.assertIn({"chapter": "06-features", "at": "本地数据", "kind": "table"}, picks,
                      "模板选的表格带上了列——列归写章时定")
        self.assertIn({"chapter": "06-features", "at": "失败提示", "under": "重试入口",
                       "kind": "diagram", "syntax": "sequenceDiagram"}, picks)
        self.assertEqual([{"chapter": "06-features", "at": "本地数据",
                           "text": "退出登录时是否清除待提交内容"}], got["rechecks"])
        titles = [h["title"] for h in got["features"]["h3"] if h.get("selected")]
        self.assertEqual(["本地数据", "失败提示"], titles)
        self.assertEqual([{"title": "重试入口", "parent": "失败提示"}], got["features"]["h4"])

    def test_the_template_never_fixes_the_columns(self) -> None:
        """模板只声明形式：同位置写两遍合并成一项，合同那张必要表的锚列原样留着。"""
        got = read_plan(with_chapter("08-acceptance", f"{ACCEPTANCE_LINE}\n{ACCEPTANCE_LINE}"))
        self.assertEqual([], got["problems"])
        self.assertEqual(1, len(got["structures"]), "同一处形式写两遍没合并")
        tables = got["acceptance"]["tables"]
        self.assertEqual(1, len(tables), "合同那张必要表被模板改掉了")
        self.assertNotIn("selected", json.dumps(tables, ensure_ascii=False),
                         "合同表被当成了模板选的表")
        anchors = json.dumps(tables[0]["anchors"], ensure_ascii=False)
        self.assertIn("通过条件", anchors, "合同自己的锚列丢了")
        self.assertNotIn("主责", anchors, "模板的列混进了合同的锚列")
        forms = got["acceptance"]["forms"]
        self.assertEqual([{"at": "", "kind": "table", "selected": True}], forms)


class PlanCase(StoryBuildCase):
    """从「Spec 写完、还没起手」开始：流程收口，设计、草稿与 Story 都不在。"""

    def setUp(self) -> None:
        super().setUp()
        ensure_flow_state(self.root, FEATURE, self.src, self.DRAFT)
        self.plan = self.src / "story-template.md"
        self.plan.unlink(missing_ok=True)
        shutil.rmtree(self.src / "drafts", ignore_errors=True)
        self.story_path.unlink(missing_ok=True)

    def cmd(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run(["node", str(BUILD), *args, "--feature", FEATURE,
                               "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def put(self, title: str, body: str) -> tuple[int, str]:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return self.cmd("chapter", "--chapter", title, "--from", str(src))

    def write_plan(self, text: str = BASE) -> None:
        self.plan.write_text(text, encoding="utf-8")

    def draft(self, prefix: str) -> Path:
        return next((self.src / "drafts").glob(f"{prefix}-*.md"))


class TheFirstSkeletonAsksForTheDesign(PlanCase):
    def test_a_shell_is_made_and_the_next_action_is_to_write_it(self) -> None:
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        head = out.split("\n")[:3]
        self.assertTrue(head[0].startswith("NEXT: 先写整篇写作设计"), head)
        self.assertIn("story-template.md", head[1], "INPUT 没给写作设计在哪")
        self.assertIn("init-analysis.md", head[1], "INPUT 没给来源初筛在哪")
        self.assertIn("写作设计空壳", head[2])
        self.assertNotIn("还留着模板占位符", out, "刚建的空壳不该逐条报占位——下一步就是写它")
        shell = self.plan.read_text(encoding="utf-8")
        self.assertIn("## 骨架", shell)
        for ch in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]:
            self.assertIn(f"### {ch['id']}", shell)

    def test_the_current_inputs_come_with_the_skeleton(self) -> None:
        """Spec 写完之后才列得出它的图：成文要用的输入在起手这一刻给。"""
        _, out = self.cmd("skeleton")
        for heading in ("## 4. 材料里的图", "## 4a. 系统设计里的图", "## 4b. spec 里的图"):
            self.assertIn(heading, out)
        self.assertNotIn("还没写成", out.split("## 4b.", 1)[1], "Spec 已在，却说还没写成")

    def test_a_chapter_cannot_land_on_a_shell(self) -> None:
        self.cmd("skeleton")
        before = self.story_path.read_text(encoding="utf-8")
        code, out = self.put("背景", minimal_body("背景", "用户现在拿不到凭据。"))
        self.assertEqual(1, code, out)
        self.assertIn("写作设计还读不了", out)
        self.assertIn("模板占位符", out, "没说清设计缺在哪")
        self.assertEqual(before, self.story_path.read_text(encoding="utf-8"), "设计读不了却落了盘")

    def test_check_names_a_missing_design(self) -> None:
        """设计是随稿冻结的依据之一：缺了当场点名，删掉它不能让报错变少。"""
        self.cmd("skeleton")
        self.plan.unlink()
        code, out = self.cmd("check")
        self.assertEqual(1, code, out)
        self.assertIn("台账缺", out)
        self.assertIn("story-template.md（跑 skeleton 建空壳", out)

    def test_check_names_a_shell_design_under_its_own_class(self) -> None:
        self.cmd("skeleton")
        code, out = self.cmd("check")
        self.assertEqual(1, code, out)
        self.assertIn("[⓪c 写作设计]", out)
        self.assertIn("模板占位符", out.split("[⓪c 写作设计]", 2)[-1])

    def test_an_old_design_is_refused_with_the_way_out(self) -> None:
        self.cmd("skeleton")
        self.write_plan(BASE.replace("## 骨架", "## 章节安排"))
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        self.assertTrue(out.startswith("NEXT: 先写整篇写作设计"), out[:200])
        self.assertIn("记一笔：写作设计", out)
        self.assertIn("按骨架协议重写", out)

    def test_a_valid_design_moves_on_to_the_first_chapter(self) -> None:
        self.cmd("skeleton")
        self.write_plan()
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        head = out.split("\n")[:2]
        self.assertTrue(head[0].startswith("NEXT: 写「背景」"), head)
        self.assertIn("「01-background」的骨架", head[1])
        self.assertEqual(0, self.put("背景", minimal_body("背景", "用户现在拿不到凭据。"))[0])


class TheSkeletonBecomesTheDraft(PlanCase):
    def test_an_untouched_draft_is_laid_out_from_the_skeleton(self) -> None:
        self.cmd("skeleton")
        self.write_plan(with_chapter("06-features", FEATURES))
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        draft = self.draft("06").read_text(encoding="utf-8")
        for needle in ("### 本地数据", "<!-- story-draft:guide 骨架：答：哪些数据存在本机",
                       "### 失败提示", "#### 重试入口"):
            self.assertIn(needle, draft)
        self.assertLess(draft.index("### 本地数据"), draft.index("### 失败提示"))
        self.assertLess(draft.index("### 失败提示"), draft.index("#### 重试入口"))
        local = draft.split("### 本地数据", 1)[1].split("### 失败提示", 1)[0]
        self.assertIn("完成表达", local, "草稿没说这一节要完成什么")
        self.assertNotIn("| 数据 |", local, "模板给表造了占位表头")
        self.assertNotIn("|---|", local, "模板给表造了占位表头")
        self.assertIn("按写作设计骨架给", out)

    def test_a_not_applicable_chapter_draft_carries_only_that_line(self) -> None:
        self.write_plan()
        self.cmd("skeleton")
        draft = self.draft("03").read_text(encoding="utf-8")
        self.assertIn("骨架：不涉及：范围已在背景里交代", draft)
        self.assertIn("本需求不涉及。", draft)
        self.assertNotIn("\n### ", draft)

    def test_submit_and_check_hold_the_skeleton(self) -> None:
        self.write_plan(with_chapter("06-features", FEATURES))
        self.cmd("skeleton")
        code, out = self.put("功能说明", "提交后界面停在等待态。\n\n" + TABLE)
        self.assertEqual(1, code, out)
        self.assertIn("「功能说明」缺「失败提示」这一节", out)
        self.assertIn("删掉骨架里那一行", out, "没给出改骨架这条出路")
        code, out = self.put("功能说明", "提交后界面停在等待态。\n\n" + TABLE
                             + "\n### 失败提示\n\n提交失败时停在原页面。\n")
        self.assertEqual(1, code, out)
        self.assertIn("缺「重试入口」这一小节", out)
        code, out = self.put("功能说明", FEATURES_BODY)
        self.assertEqual(0, code, out)
        story = self.story_path.read_text(encoding="utf-8")
        self.story_path.write_text(story.replace("#### 重试入口\n\n在原页面再次提交。\n", ""),
                                   encoding="utf-8")
        _, out = self.cmd("check")
        self.assertIn("缺「重试入口」这一小节", out, "全篇 check 与章提交不是同一份核对")

    def test_the_skeleton_does_not_cap_the_body(self) -> None:
        """骨架是最小集合：正文多出来的小节照样合法。"""
        self.write_plan(with_chapter("06-features", FEATURES))
        self.cmd("skeleton")
        body = FEATURES_BODY + "\n### 骨架里没列的一节\n\n写作中发现的另一种受限情形。\n"
        self.assertEqual(0, self.put("功能说明", body)[0])

    def test_two_different_column_sets_both_pass(self) -> None:
        """模板选表格只要求这里真有一张表：两套有意义而不同的列都合法。"""
        self.write_plan(with_chapter("06-features", FEATURES))
        self.cmd("skeleton")
        other = ("### 本地数据\n\n| 内容 | 存到哪 | 什么时候没了 |\n|---|---|---|\n"
                 "| 待提交内容 | 本机 | 退出登录 |\n")
        body = "提交后界面停在等待态。\n\n" + other + "\n" + FAILURE
        code, out = self.put("功能说明", body)
        self.assertEqual(0, code, out)

    def test_a_horizontal_rule_is_not_a_list(self) -> None:
        """`* * *` 是分隔线不是列表项；真的星号列表算数。"""
        block = "#### 继续操作\n- 答：用户还能做什么\n形式：无序列表\n- 描述：列出可继续的操作\n"
        self.write_plan(with_chapter("06-features", block))
        self.cmd("skeleton")
        head = "提交后界面停在等待态。\n\n### 继续操作\n\n"
        code, out = self.put("功能说明", head + "* * *\n")
        self.assertEqual(1, code, out)
        self.assertIn("缺无序列表", out, "分隔线被当成了列表项")
        self.assertEqual(0, self.put("功能说明", head + "* 重新提交\n* 联系客服\n")[0])


    def test_a_form_is_checked_under_its_own_parent(self) -> None:
        """H4 的形式先定位父节：别的父节下的同名子节顶替不了。"""
        block = ("#### 甲路径\n- 答：甲怎么走\n##### 结果\n- 答：甲的结果\n形式：表格\n"
                 "- 描述：甲的结果与后续对照\n#### 乙路径\n- 答：乙怎么走\n##### 结果\n- 答：乙的结果\n")
        self.write_plan(with_chapter("06-features", block))
        self.cmd("skeleton")
        body = ("提交后界面停在等待态。\n\n### 甲路径\n\n甲这样走。\n\n#### 结果\n\n甲的结果说明。\n\n"
                "### 乙路径\n\n乙这样走。\n\n#### 结果\n\n| 结果 | 后续 |\n|---|---|\n| 成功 | 结束 |\n")
        code, out = self.put("功能说明", body)
        self.assertEqual(1, code, out)
        self.assertIn("甲路径·结果", out, "甲节缺的表被乙节的同名子节顶替了")

    def test_a_list_form_needs_a_real_list(self) -> None:
        """选了有序列表：无序列表与围栏里的示例都不算，真有有序项就过，不数条目。"""
        block = ("#### 继续操作\n- 答：用户还能做什么\n形式：有序列表\n- 描述：按先后写出可继续的操作\n")
        self.write_plan(with_chapter("06-features", block))
        self.cmd("skeleton")
        head = "提交后界面停在等待态。\n\n### 继续操作\n\n"
        code, out = self.put("功能说明", head + "- 重新提交\n- 联系客服\n")
        self.assertEqual(1, code, out)
        self.assertIn("缺有序列表", out)
        fenced = head + "```text\n1. 这是示例\n```\n"
        code, out = self.put("功能说明", fenced)
        self.assertEqual(1, code, out)
        self.assertIn("缺有序列表", out, "围栏里的示例被当成了真列表")
        self.assertEqual(0, self.put("功能说明", head + "1. 重新提交\n")[0])

    def test_changing_the_skeleton_never_rewrites_a_touched_draft(self) -> None:
        self.write_plan()
        self.cmd("skeleton")
        draft = self.draft("06")
        mine = draft.read_text(encoding="utf-8") + "\n我写到一半的内容。\n"
        draft.write_text(mine, encoding="utf-8")
        self.write_plan(with_chapter("06-features", FEATURES))
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        self.assertEqual(mine, draft.read_text(encoding="utf-8"), "动过的草稿被改写了")
        starts = out.split("结构起点：", 1)[1]
        for needle in ("### 本地数据", "完成表达", "#### 重试入口"):
            self.assertIn(needle, starts)
        self.assertNotIn("| 数据 |", starts, "起点里造了模板表头")

    def test_the_starts_group_by_section_not_by_kind(self) -> None:
        """一节要两样（状态图讲转移、表讲每个状态允许什么）时，两样排在它自己的标题下。

        起点这段文字是给作者「按需贴进去」的。按种类排的话，图在图那一轮出、表在表那一轮出，
        中间隔着别的小节的标题——后一节的表就印在了前一节下面，照着贴必然贴错位置。
        """
        two = ("#### 改约与取消\n- 答：揽收前能改什么\n"
               "形式：状态图\n- 描述：揽收前后的状态与各状态允许的动作\n"
               "形式：表格\n- 描述：每个状态允许的动作与限制条件\n"
               "#### 下单\n- 答：填哪些信息\n形式：表格\n- 描述：每项信息的来源与是否可改\n")
        self.write_plan()
        self.cmd("skeleton")
        draft = self.draft("06")
        draft.write_text(draft.read_text(encoding="utf-8") + "\n我写到一半的内容。\n",
                         encoding="utf-8")
        self.write_plan(with_chapter("06-features", two))
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        starts = out.split("结构起点：", 1)[1]
        mine = starts.split("### 改约与取消", 1)[1].split("### 下单", 1)[0]
        self.assertIn("stateDiagram", mine, "这一节的图起点跑到别的小节下面去了")
        self.assertIn("「改约与取消」这一节要一张表", mine,
                      "同一节的第二样起点没跟着它自己的标题")

    def test_a_skeleton_diagram_is_checked_in_its_own_section(self) -> None:
        self.write_plan(with_chapter("07-exceptions", "#### 跨方恢复\n- 答：两边怎么恢复\n形式：图"))
        self.cmd("skeleton")
        elsewhere = ("中断后重新进入。\n\n```mermaid\ngraph TD\nA-->B\n```\n\n"
                     "### 跨方恢复\n\n两边各自重试。\n")
        code, out = self.put("异常与恢复", elsewhere)
        self.assertEqual(1, code, out)
        self.assertIn("「异常与恢复·跨方恢复」没有图", out)
        inside = "中断后重新进入。\n\n### 跨方恢复\n\n两边各自重试：\n\n```mermaid\ngraph TD\nA-->B\n```\n"
        self.assertEqual(0, self.put("异常与恢复", inside)[0])

    def test_not_applicable_body_conflicts_with_a_skeleton_that_lists_structure(self) -> None:
        """骨架还列着小节或表图、正文却写「不涉及」：两个明确声明冲突，章提交与全篇 check 都点名。

        骨架里的表图恰好与合同要求重合时同样算列过。骨架改成「不涉及」之后，照原语义合法。
        """
        cases = {
            "小节与表": ("功能说明", "06-features", FEATURES),
            "小节图": ("异常与恢复", "07-exceptions", "#### 跨方恢复\n- 答：x\n形式：图"),
            "章级图与合同重合": ("业务流程", "05-flow", "- 本章主线：x\n形式：图"),
            "表与合同重合": ("验收", "08-acceptance", ACCEPTANCE_LINE),
        }
        for name, (title, chapter_id, block) in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.write_plan(with_chapter(chapter_id, block))
                self.cmd("skeleton")
                src = self.root / "chapter.md"
                src.write_bytes("本需求不涉及。\n".encode("utf-8"))
                story_before = self.story_path.read_bytes()
                code, out = self.cmd("chapter", "--chapter", title, "--from", str(src))
                self.assertEqual(1, code, out)
                self.assertIn("两处说法冲突", out)
                self.assertIn("- 不涉及：", out, "没给出改骨架这条出路")
                self.assertEqual(story_before, self.story_path.read_bytes(), "冲突却写了盘")

                story = self.story_path.read_text(encoding="utf-8")
                self.story_path.write_text(story.replace(f"<!-- 待写：{title} -->", "本需求不涉及。"),
                                           encoding="utf-8")
                _, out = self.cmd("check")
                self.assertIn("两处说法冲突", out, "全篇 check 与章提交不是同一条检查")

                self.story_path.write_bytes(story_before)
                self.write_plan(with_chapter(chapter_id, "- 不涉及：本需求没有这部分"))
                code, out = self.cmd("chapter", "--chapter", title, "--from", str(src))
                self.assertEqual(0, code, f"骨架写了不涉及之后「不涉及」该照原语义合法：{out}")

    def test_a_structure_both_required_and_listed_is_reported_and_seeded_once(self) -> None:
        """合同要求与骨架重合：同一个缺口只报一次，起点只给一次。"""
        text = with_chapter("05-flow", "- 本章主线：x\n形式：图")
        self.write_plan(with_chapter("08-acceptance", ACCEPTANCE_LINE, text))
        self.cmd("skeleton")
        self.assertEqual(1, self.draft("05").read_text(encoding="utf-8").count("作图："))
        acceptance = self.draft("08").read_text(encoding="utf-8")
        self.assertEqual(1, acceptance.count("| 编号 |"), "合同那张表的起点没给或给了两次")
        self.assertNotIn("场景与前置", acceptance, "模板的列被当成了表头")

        code, out = self.put("业务流程", "提交之后等回执。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("没有图"), f"同一个缺图报了不止一次：{out}")
        code, out = self.put("验收", "验收按上游约定。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("缺一张表"), f"同一个缺表报了不止一次：{out}")

        for prefix in ("05", "08"):
            self.draft(prefix).write_text("先写到这里。\n", encoding="utf-8")
        _, out = self.cmd("skeleton")
        self.assertEqual(1, out.count("| 编号 |"), f"表的起点给了不止一次：{out[-1200:]}")
        self.assertEqual(1, out.count("作图："), f"图的起点给了不止一次：{out[-1200:]}")


#: 骨架点名要时序图的一节；围栏开头可以先有空行与 `%%` 注释，之后才是声明。
SEQUENCE = "#### 跨方恢复\n- 答：受理结果回到谁\n形式：时序图"
FLOW_FENCE = "```mermaid\nflowchart TD\nA-->B\n```\n"
SEQ_FENCE = ("```mermaid\n%% 先讲受理，再讲结果回到谁\n\nsequenceDiagram\n"
             "  申请方->>受理方: 提交\n  受理方-->>申请方: 受理结果\n```\n")


class ASkeletonDiagramTypeIsHeld(PlanCase):
    """点名时序图之后流程图顶替不了；与不点名的图或合同要求重合时，一个缺口只报一次、只给一次起点。"""

    def section(self, fence: str) -> str:
        return f"中断后重新进入。\n\n### 跨方恢复\n\n两边各自重试：\n\n{fence}"

    def test_a_flowchart_does_not_stand_in_for_a_sequence(self) -> None:
        self.write_plan(with_chapter("07-exceptions", SEQUENCE))
        self.cmd("skeleton")
        self.assertIn("时序图", self.draft("07").read_text(encoding="utf-8"), "起点没说这里要时序图")
        code, out = self.put("异常与恢复", self.section(FLOW_FENCE))
        self.assertEqual(1, code, out)
        self.assertIn("「异常与恢复·跨方恢复」没有时序图", out)
        self.assertEqual(0, self.put("异常与恢复", self.section(SEQ_FENCE))[0])

    def test_any_named_diagram_type_is_held(self) -> None:
        """图种由写作设计按内容判定，不偏向时序图：点名流程图，正文就要流程图，时序图也顶替不了。"""
        self.write_plan(with_chapter("07-exceptions", "#### 跨方恢复\n- 答：失败后走哪条分支\n形式：流程图"))
        self.cmd("skeleton")
        draft = self.draft("07").read_text(encoding="utf-8")
        self.assertIn("流程图", draft)
        self.assertNotIn("谁调谁", draft, "作图提示还带着时序图专属的说法")
        code, out = self.put("异常与恢复", self.section(SEQ_FENCE))
        self.assertEqual(1, code, out)
        self.assertIn("「异常与恢复·跨方恢复」没有流程图", out)
        self.assertEqual(0, self.put("异常与恢复", self.section("```mermaid\ngraph TD\nA-->B\n```\n"))[0],
                         "graph 与 flowchart 是同一种图")

    def test_an_untyped_and_a_typed_diagram_at_one_place_count_once(self) -> None:
        self.write_plan(with_chapter("07-exceptions", SEQUENCE + "\n形式：图"))
        self.cmd("skeleton")
        draft = self.draft("07").read_text(encoding="utf-8")
        self.assertEqual(1, draft.count("作图："), draft)
        self.assertIn("时序图", draft, "留下的不是更具体的那项")
        code, out = self.put("异常与恢复", self.section("没有图。\n"))
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("跨方恢复」没有"), out)
        self.assertIn("没有时序图", out)

    def test_with_the_contract_diagram_the_gap_is_reported_once(self) -> None:
        self.write_plan(with_chapter("05-flow", "- 本章主线：x\n形式：时序图"))
        self.cmd("skeleton")
        self.assertEqual(1, self.draft("05").read_text(encoding="utf-8").count("作图："))
        code, out = self.put("业务流程", "提交之后等回执。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("没有图") + out.count("没有时序图"), f"同一个缺口报了不止一次：{out}")
        code, out = self.put("业务流程", "提交之后等回执。\n\n" + FLOW_FENCE)
        self.assertEqual(1, code, out)
        self.assertIn("「业务流程」没有时序图", out, "章里已有流程图时没核图类型")
        self.assertEqual(0, self.put("业务流程", "提交之后等回执。\n\n" + SEQ_FENCE)[0])


class TenChaptersHandOverToTheRecheck(PlanCase):
    """十章齐了：下一步是回看清单，输入给全——全文、设计、决策登记、来源初筛与原材料。"""

    def test_the_last_chapter_hands_over_to_the_recheck_list(self) -> None:
        self.write_plan(with_chapter("02-terms", "- 本章主线：解释等待态\n- 待核：等待态这个词评审人认不认得"))
        self.cmd("skeleton")
        out = ""
        for ch in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]:
            code, out = self.put(ch["title"], minimal_body(ch["title"], f"「{ch['title']}」的正文。"))
            self.assertEqual(0, code, out)
        head = out.split("\n")[:2]
        self.assertTrue(head[0].startswith("NEXT: 十章齐了——回看"), head)
        for needle in ("story-template.md", "decisions.json", "init-analysis.md", "RR/prd.md", "「四、回看」"):
            self.assertIn(needle, head[1], f"回看的输入少了「{needle}」")
        self.assertIn("[骨架待核] 02-terms：等待态这个词评审人认不认得", out)
        code, again = self.cmd("skeleton")
        self.assertEqual(0, code, again)
        self.assertTrue(again.startswith("NEXT: 十章齐了——回看"), again[:200])
        self.assertIn("[骨架待核] 02-terms", again, "再跑 skeleton 没再给一次回看清单")


class ALandedChapterStillGetsItsStarts(PlanCase):
    """已经合法提交的章，骨架改了：原稿与 Story 字节不动，但当前缺的结构照样给出起点。"""

    def starts_in(self, out: str) -> str:
        return out.split("结构起点：", 1)[1] if "结构起点：" in out else ""

    def land(self) -> tuple[Path, bytes, bytes]:
        self.write_plan(with_chapter("06-features", LOCAL))
        self.cmd("skeleton")
        draft = self.draft("06")
        draft.write_bytes(("提交后界面停在等待态。\n\n" + TABLE).encode("utf-8"))
        code, out = self.cmd("chapter", "--chapter", "功能说明", "--from", str(draft))
        self.assertEqual(0, code, out)
        return draft, draft.read_bytes(), self.story_path.read_bytes()

    def test_changes_to_the_skeleton_of_a_landed_chapter(self) -> None:
        draft, draft_bytes, story_bytes = self.land()
        cases = {
            "骨架不变": (LOCAL, []),
            "新增一节": (LOCAL + "#### 失败提示\n形式：表格\n- 描述：每种失败情形与用户看到什么\n",
                     ["### 失败提示", "完成表达"]),
            "改名": (LOCAL.replace("本地数据", "本机保存的数据"),
                   ["### 本机保存的数据", "完成表达"]),
            "改形式": (LOCAL.replace("形式：表格", "形式：无序列表"), ["完成表达"]),
            "撤掉小节": ("- 本章主线：只讲等待态", []),
        }
        for name, (block, needles) in cases.items():
            with self.subTest(case=name):
                self.write_plan(with_chapter("06-features", block))
                code, out = self.cmd("skeleton")
                self.assertEqual(0, code, out)
                starts = self.starts_in(out)
                if needles:
                    for needle in needles:
                        self.assertIn(needle, starts, f"缺的结构没给起点：{out[-800:]}")
                    if "本机保存的数据" not in block:
                        self.assertNotIn("### 本地数据", starts, "已经有的结构又给了一遍")
                else:
                    self.assertEqual("", starts, "没缺什么却给了起点")
                self.assertEqual(draft_bytes, draft.read_bytes(), "已提交章的草稿被改写了")
                self.assertEqual(story_bytes, self.story_path.read_bytes(), "Story 被改写了")

    def test_a_landed_chapter_whose_draft_is_gone_gets_current_text_and_starts(self) -> None:
        draft, _, _ = self.land()
        name = draft.name
        draft.unlink()
        self.write_plan(with_chapter("06-features", LOCAL + "#### 失败提示\n形式：图\n"))
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        back = (self.src / "drafts" / name).read_text(encoding="utf-8")
        self.assertIn("待提交内容", back, "补回来的不是现稿")
        self.assertIn("### 失败提示", self.starts_in(out))


class TheDesignFreezesWithTheStory(PlanCase):
    """登记那一刻设计与决策登记一起定稿：之后改了 check 点名，reopen 撤销登记后可以再改。"""

    def register(self) -> None:
        sys.path.insert(0, str(FLOW.parent))
        from flow.state import STORY_SRC_FROZEN, ledger_digest  # noqa: PLC0415
        self.assertIn("story-template.md", STORY_SRC_FROZEN)
        path = self.src / "story-flow.json"
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["status"] = "story_written"
        flow["story_src_digests"] = {n: ledger_digest(self.src / n) for n in STORY_SRC_FROZEN}
        path.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_an_edit_after_registration_is_named_and_reopen_releases_it(self) -> None:
        self.write_plan()
        self.cmd("skeleton")
        self.register()
        self.plan.write_text(self.plan.read_text(encoding="utf-8")
                             .replace("先讲一次提交", "登记之后改了：先讲一次提交"), encoding="utf-8")
        _, out = self.cmd("check")
        self.assertIn("story-template.md 与成文登记时的台账对不上", out)
        code, out = self.cmd("skeleton")
        self.assertEqual(1, code, "登记之后 skeleton 还能跑")

        proc = subprocess.run([sys.executable, str(FLOW), "reopen", "--feature", FEATURE,
                               "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        _, out = self.cmd("check")
        self.assertNotIn("story-template.md 与成文登记时的台账对不上", out, "reopen 之后设计仍被当成冻结")


if __name__ == "__main__":
    unittest.main()
