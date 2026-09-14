"""整篇写作设计：协议、空壳、选定结构的落实，与随稿冻结。

`AR/story-src/story-template.md` 由作者写；脚本只建空壳、读协议、把选定的表图交给章节合同的
打底与核对。这一组锁住其中确定的那几件：

  ① 首次起手只有空壳，空壳不算设计过——下一步是写设计，章提交与 check 都不放行；
  ② 协议缺在哪能定位：未知或重复的章 ID、坏 JSON、表缺列、与合同必要表冲突；
  ③ 选定的表头搭进没动过的草稿，章提交与全篇 check 同一份核对；改选择不覆盖动过的草稿；
  ④ 设计不限制正文：没列的小节照样合法；
  ⑤ 成文登记时设计随稿冻结，登记后改了 check 点名，reopen 之后可以再改。

测不了的是设计合不合理、作者照没照它写——那归整稿、独立审查与真实运行。
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

#: 一张中性的选定表：本地数据的保存与清除。
PICKS = [{"chapter": "06-features", "at": "本地数据", "kind": "table",
          "columns": ["数据", "保存多久", "何时清除"]}]
TABLE = ("### 本地数据\n\n| 数据 | 保存多久 | 何时清除 |\n|---|---|---|\n"
         "| 待提交内容 | 到提交成功 | 退出登录 |\n")
#: 作者为验收章选的列：与合同那张必要表同主语，是同一张表。
ACCEPTANCE = ["编号", "场景与前置", "可观察的通过条件", "主责"]


def with_picks(picks) -> str:
    """最小设计，只换结构选择那一块。"""
    return PLAN_FIXTURE.read_text(encoding="utf-8").replace(
        "```json\n[]\n```", "```json\n" + json.dumps(picks, ensure_ascii=False, indent=2) + "\n```")


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
        "const merged = m.selectedStructure(plan, '08-acceptance');"
        "fs.rmSync(dir, {recursive: true, force: true});"
        "process.stdout.write(JSON.stringify({problems: plan.problems, structures: plan.structures,"
        " ids: [...plan.chapterPlans.keys()], acceptance: merged}));")
    proc = subprocess.run(["node", "--input-type=module", "-e", script, "--",
                           str(PLAN_MODULE), str(CONTRACT_PATH), text],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=60, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TheProtocolIsReadInOnePlace(unittest.TestCase):
    """协议缺在哪，一次报全、指得到位置；形状合法的选择原样登记。"""

    def test_the_minimal_design_is_valid(self) -> None:
        got = read_plan(PLAN_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([], got["problems"])
        ids = [c["id"] for c in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]]
        self.assertEqual(ids, got["ids"])
        self.assertEqual([], got["structures"], "空数组是合法的：没有要脚本落实的结构")

    def test_the_shell_is_not_a_design(self) -> None:
        script = (
            "import {pathToFileURL} from 'node:url'; import * as fs from 'node:fs';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "process.stdout.write(m.writingPlanShell(JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'))));")
        shell = subprocess.run(["node", "--input-type=module", "-e", script, "--",
                                str(PLAN_MODULE), str(CONTRACT_PATH)],
                               capture_output=True, text=True, encoding="utf-8", timeout=60).stdout
        problems = read_plan(shell)["problems"]
        self.assertTrue(problems, "空壳被当成了已经写好的设计")
        self.assertTrue(all("模板占位符" in p for p in problems), problems)

    def test_each_broken_shape_is_located(self) -> None:
        base = PLAN_FIXTURE.read_text(encoding="utf-8")
        cases = {
            "未知章 ID": (base.replace("### 03-scope", "### 03-范围"),
                       ["「### 03-范围」不是章节合同里的章 ID", "缺「### 03-scope」"]),
            "重复章 ID": (base.replace("## 结构选择", "### 02-terms\n\n又一段。\n\n## 结构选择"),
                       ["「### 02-terms」出现了两次"]),
            "没有安排": (base.replace("解释提交、回执与等待态这几个词，依据 `spec/spec.md` 术语映射表。", ""),
                      ["「### 02-terms」没有安排"]),
            "缺一部分": (base.replace("## 阅读主线", "## 读法"), ["缺「## 阅读主线」"]),
            "坏 JSON": (base.replace("```json\n[]\n```", "```json\n[{\n```"), ["不是合法 JSON"]),
            "不是数组": (with_picks({"chapter": "05-flow"}), ["要是一个数组"]),
            "表没给列": (with_picks([{"chapter": "06-features", "at": "", "kind": "table"}]),
                      ["第 1 项", "表要给 columns"]),
            "协议外字段": (with_picks([{"chapter": "05-flow", "at": "", "kind": "diagram",
                                    "section": "总览"}]), ["协议外的字段 section"]),
            "表带图类型": (with_picks([{**PICKS[0], "syntax": "sequenceDiagram"}]), ["表不带 syntax"]),
            "不认识的图类型": (with_picks([{"chapter": "05-flow", "at": "", "kind": "diagram",
                                     "syntax": "flowchart"}]), ["syntax 目前只认 sequenceDiagram"]),
            "未知章": (with_picks([{"chapter": "99-x", "at": "", "kind": "diagram"}]),
                     ["chapter「99-x」不是章节合同里的章 ID"]),
            "附录外小节": (with_picks([{"chapter": "10-appendix", "at": "补充说明", "kind": "diagram"}]),
                       ["附录只有合同那几节"]),
            "同主语两种列": (with_picks(PICKS + [{**PICKS[0], "columns": ["数据", "位置"]}]),
                        ["第 1 项与第 2 项", "选了两种列"]),
            "与合同必要表冲突": (with_picks([{"chapter": "08-acceptance", "at": "", "kind": "table",
                                       "columns": ["编号", "场景"]}]),
                           ["与章节合同", "要求的表冲突", "通过条件"]),
        }
        for name, (text, needles) in cases.items():
            with self.subTest(case=name):
                problems = "\n".join(read_plan(text)["problems"])
                for needle in needles:
                    self.assertIn(needle, problems)

    def test_repeated_picks_merge_and_a_contract_twin_seeds_from_the_authors_columns(self) -> None:
        """同一项写两遍合并成一项；与合同同主语的必要表是同一张表：一个槽位，表头用作者的列，
        锚列含合同要求，而且仍记着是作者选的。"""
        pick = {"chapter": "08-acceptance", "at": "", "kind": "table", "columns": ACCEPTANCE}
        got = read_plan(with_picks([pick, dict(pick)]))
        self.assertEqual([], got["problems"])
        self.assertEqual(1, len(got["structures"]), "重复项没合并")
        tables = got["acceptance"]["tables"]
        self.assertEqual(1, len(tables), "合同那张与作者选的是同一张表，却成了两个槽位")
        self.assertEqual("|".join(ACCEPTANCE), tables[0]["header"], "打底没用作者的列")
        self.assertTrue(tables[0].get("selected"), "合并之后丢了「作者选过」")
        anchors = json.dumps(tables[0]["anchors"], ensure_ascii=False)
        for need in ("通过条件", "主责"):
            self.assertIn(need, anchors, f"合并后的锚列少了「{need}」")


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

    def write_plan(self, picks) -> None:
        self.plan.write_text(with_picks(picks), encoding="utf-8")

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
        for ch in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]:
            self.assertIn(f"### {ch['id']}", shell)

    def test_the_current_inputs_come_with_the_skeleton(self) -> None:
        """Spec 写完之后才列得出它的图：成文要用的输入在起手这一刻给。"""
        _, out = self.cmd("skeleton")
        for heading in ("## 4. 材料里的图", "## 4a. 上游原 AR", "## 4c. spec 里的图"):
            self.assertIn(heading, out)
        self.assertNotIn("还没写成", out.split("## 4c.", 1)[1], "Spec 已在，却说还没写成")

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

    def test_a_rerun_with_a_broken_design_lists_what_is_wrong(self) -> None:
        self.cmd("skeleton")
        self.plan.write_text(with_picks({"chapter": "05-flow"}), encoding="utf-8")
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        self.assertTrue(out.startswith("NEXT: 先写整篇写作设计"), out[:200])
        self.assertIn("记一笔：写作设计", out)
        self.assertIn("要是一个数组", out)

    def test_a_valid_design_moves_on_to_the_first_chapter(self) -> None:
        self.cmd("skeleton")
        self.write_plan([])
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        head = out.split("\n")[:2]
        self.assertTrue(head[0].startswith("NEXT: 写「背景」"), head)
        self.assertIn("「01-background」那一段", head[1])
        self.assertEqual(0, self.put("背景", minimal_body("背景", "用户现在拿不到凭据。"))[0])


class PickedStructuresAreSeededAndChecked(PlanCase):
    def test_an_untouched_draft_gets_the_picked_table(self) -> None:
        self.cmd("skeleton")
        self.write_plan(PICKS)
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        draft = self.draft("06").read_text(encoding="utf-8")
        self.assertIn("### 本地数据", draft)
        self.assertIn("| 数据 | 保存多久 | 何时清除 |", draft.split("### 本地数据", 1)[1])
        self.assertIn("搭好选定的表图", out)

    def test_the_acceptance_draft_is_seeded_once_from_the_authors_columns(self) -> None:
        columns = ["编号", "场景与前置", "可观察的通过条件", "主责"]
        self.write_plan([{"chapter": "08-acceptance", "at": "", "kind": "table", "columns": columns}])
        self.cmd("skeleton")
        draft = self.draft("08").read_text(encoding="utf-8")
        self.assertIn("| 编号 | 场景与前置 | 可观察的通过条件 | 主责 |", draft)
        self.assertNotIn("| 编号 | 验收点 | 可观察的通过条件 |", draft, "合同那张又打了一遍底")

    def test_submit_and_check_hold_the_same_picked_table(self) -> None:
        self.write_plan(PICKS)
        self.cmd("skeleton")
        code, out = self.put("功能说明", "提交后界面停在等待态。\n")
        self.assertEqual(1, code, out)
        self.assertIn("「功能说明」缺「本地数据」这一节", out)
        self.assertIn("写作设计里选定的结构", out, "没说清这是写作设计里定的")
        code, out = self.put("功能说明", "提交后界面停在等待态。\n\n" + TABLE)
        self.assertEqual(0, code, out)
        story = self.story_path.read_text(encoding="utf-8")
        self.story_path.write_text(story.replace("| 待提交内容 | 到提交成功 | 退出登录 |\n", "")
                                   .replace("| 数据 | 保存多久 | 何时清除 |\n|---|---|---|\n", ""),
                                   encoding="utf-8")
        _, out = self.cmd("check")
        self.assertIn("「功能说明·本地数据」缺一张表", out, "全篇 check 与章提交不是同一份核对")

    def test_changing_the_picks_never_rewrites_a_touched_draft(self) -> None:
        self.write_plan([])
        self.cmd("skeleton")
        draft = self.draft("06")
        mine = draft.read_text(encoding="utf-8") + "\n我写到一半的内容。\n"
        draft.write_text(mine, encoding="utf-8")
        self.write_plan(PICKS)
        code, out = self.cmd("skeleton")
        self.assertEqual(0, code, out)
        self.assertEqual(mine, draft.read_text(encoding="utf-8"), "动过的草稿被改写了")
        starts = out.split("结构起点：", 1)[1]
        self.assertIn("### 本地数据", starts)
        self.assertIn("| 数据 | 保存多久 | 何时清除 |", starts)

    def test_a_picked_diagram_is_checked_in_its_own_section(self) -> None:
        self.write_plan([{"chapter": "07-exceptions", "at": "跨方恢复", "kind": "diagram"}])
        self.cmd("skeleton")
        elsewhere = ("中断后重新进入。\n\n```mermaid\ngraph TD\nA-->B\n```\n\n"
                     "### 跨方恢复\n\n两边各自重试。\n")
        code, out = self.put("异常与恢复", elsewhere)
        self.assertEqual(1, code, out)
        self.assertIn("「异常与恢复·跨方恢复」没有图", out)
        inside = "中断后重新进入。\n\n### 跨方恢复\n\n两边各自重试：\n\n```mermaid\ngraph TD\nA-->B\n```\n"
        code, out = self.put("异常与恢复", inside)
        self.assertEqual(0, code, out)

    def test_not_applicable_does_not_bypass_a_picked_structure(self) -> None:
        """设计还选着表或图、正文却写「不涉及」：两个明确声明冲突，章提交与全篇 check 都点名。

        作者的选择恰好与合同要求重合时同样算选过——合并只核一次，但「选过」这件事不能丢。
        撤回选择之后，这一章回到只有合同要求的状态，「不涉及」照原语义合法。
        """
        cases = {
            "新增小节表": ("功能说明", PICKS),
            "新增章级图": ("功能说明", [{"chapter": "06-features", "at": "", "kind": "diagram"}]),
            "新增小节图": ("异常与恢复", [{"chapter": "07-exceptions", "at": "跨方恢复",
                                     "kind": "diagram"}]),
            "章级图与合同重合": ("业务流程", [{"chapter": "05-flow", "at": "", "kind": "diagram"}]),
            "表与合同重合": ("验收", [{"chapter": "08-acceptance", "at": "", "kind": "table",
                                  "columns": ACCEPTANCE}]),
        }
        for name, (title, picks) in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.write_plan(picks)
                self.cmd("skeleton")
                src = self.root / "chapter.md"
                src.write_bytes("本需求不涉及。\n".encode("utf-8"))
                story_before = self.story_path.read_bytes()
                code, out = self.cmd("chapter", "--chapter", title, "--from", str(src))
                self.assertEqual(1, code, out)
                self.assertIn("两处说法冲突", out)
                self.assertIn("撤掉这几项", out, "没给出撤回选择这条出路")
                self.assertEqual(story_before, self.story_path.read_bytes(), "冲突却写了盘")
                self.assertEqual("本需求不涉及。\n".encode("utf-8"), src.read_bytes(), "候选被改了")

                story = self.story_path.read_text(encoding="utf-8")
                self.story_path.write_text(story.replace(f"<!-- 待写：{title} -->", "本需求不涉及。"),
                                           encoding="utf-8")
                _, out = self.cmd("check")
                self.assertIn("两处说法冲突", out, "全篇 check 与章提交不是同一条检查")

                self.story_path.write_bytes(story_before)
                self.write_plan([])
                code, out = self.cmd("chapter", "--chapter", title, "--from", str(src))
                self.assertEqual(0, code, f"只剩合同要求时「不涉及」该照原语义合法：{out}")

    def test_a_structure_both_required_and_picked_is_reported_and_seeded_once(self) -> None:
        """合同要求与作者选择重合：同一个缺口只报一次，起点只给一次。"""
        self.write_plan([{"chapter": "05-flow", "at": "", "kind": "diagram"},
                         {"chapter": "08-acceptance", "at": "", "kind": "table",
                          "columns": ACCEPTANCE}])
        self.cmd("skeleton")
        header = "| " + " | ".join(ACCEPTANCE) + " |"
        self.assertEqual(1, self.draft("05").read_text(encoding="utf-8").count("作图："))
        self.assertEqual(1, self.draft("08").read_text(encoding="utf-8").count(header))
        self.assertNotIn("| 编号 | 验收点 |", self.draft("08").read_text(encoding="utf-8"))

        code, out = self.put("业务流程", "提交之后等回执。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("没有图"), f"同一个缺图报了不止一次：{out}")
        code, out = self.put("验收", "验收按上游约定。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("缺一张表"), f"同一个缺表报了不止一次：{out}")

        for prefix in ("05", "08"):
            self.draft(prefix).write_text("先写到这里。\n", encoding="utf-8")
        _, out = self.cmd("skeleton")
        self.assertEqual(1, out.count(header), f"表的起点给了不止一次：{out[-1200:]}")
        self.assertEqual(1, out.count("作图："), f"图的起点给了不止一次：{out[-1200:]}")

    def test_the_design_does_not_cap_the_body(self) -> None:
        """设计没列的小节照样合法：写作中发现的有效内容不因设计未列而违规。"""
        self.write_plan(PICKS)
        self.cmd("skeleton")
        body = ("提交后界面停在等待态。\n\n" + TABLE
                + "\n### 设计里没列的一节\n\n写作中发现的另一种受限情形。\n")
        code, out = self.put("功能说明", body)
        self.assertEqual(0, code, out)


#: 作者点名要时序图的一节；围栏开头可以先有空行与 `%%` 注释，之后才是声明。
SEQUENCE = {"chapter": "07-exceptions", "at": "跨方恢复", "kind": "diagram", "syntax": "sequenceDiagram"}
FLOW_FENCE = "```mermaid\nflowchart TD\nA-->B\n```\n"
SEQ_FENCE = ("```mermaid\n%% 先讲受理，再讲结果回到谁\n\nsequenceDiagram\n"
             "  申请方->>受理方: 提交\n  受理方-->>申请方: 受理结果\n```\n")


class APickedDiagramTypeIsHeld(PlanCase):
    """点名时序图之后流程图顶替不了；与不点名的选择或合同要求重合时，一个缺口只报一次、只给一次起点。"""

    def section(self, fence: str) -> str:
        return f"中断后重新进入。\n\n### 跨方恢复\n\n两边各自重试：\n\n{fence}"

    def test_a_flowchart_does_not_stand_in_for_a_sequence(self) -> None:
        self.write_plan([SEQUENCE])
        self.cmd("skeleton")
        self.assertIn("时序图", self.draft("07").read_text(encoding="utf-8"), "起点没说这里要时序图")
        code, out = self.put("异常与恢复", self.section(FLOW_FENCE))
        self.assertEqual(1, code, out)
        self.assertIn("「异常与恢复·跨方恢复」没有时序图", out)
        code, out = self.put("异常与恢复", self.section(SEQ_FENCE))
        self.assertEqual(0, code, out)

    def test_an_untyped_and_a_typed_pick_at_one_place_count_once(self) -> None:
        plain = {k: v for k, v in SEQUENCE.items() if k != "syntax"}
        self.write_plan([plain, SEQUENCE])
        self.cmd("skeleton")
        draft = self.draft("07").read_text(encoding="utf-8")
        self.assertEqual(1, draft.count("作图："), draft)
        self.assertIn("时序图", draft, "留下的不是更具体的那项")
        code, out = self.put("异常与恢复", self.section("没有图。\n"))
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("跨方恢复」没有"), out)
        self.assertIn("没有时序图", out)

    def test_with_the_contract_diagram_the_gap_is_reported_once(self) -> None:
        self.write_plan([{"chapter": "05-flow", "at": "", "kind": "diagram", "syntax": "sequenceDiagram"}])
        self.cmd("skeleton")
        self.assertEqual(1, self.draft("05").read_text(encoding="utf-8").count("作图："))
        code, out = self.put("业务流程", "提交之后等回执。\n")
        self.assertEqual(1, code, out)
        self.assertEqual(1, out.count("没有图") + out.count("没有时序图"), f"同一个缺口报了不止一次：{out}")
        code, out = self.put("业务流程", "提交之后等回执。\n\n" + FLOW_FENCE)
        self.assertEqual(1, code, out)
        self.assertIn("「业务流程」没有时序图", out, "章里已有流程图时没核图类型")
        code, out = self.put("业务流程", "提交之后等回执。\n\n" + SEQ_FENCE)
        self.assertEqual(0, code, out)


class TheWholeDraftIsCheckedAgainstItsSources(PlanCase):
    """十章齐了：下一步是从来源核实际全文，输入给全——全文、设计、决策登记、来源初筛与原材料。"""

    def test_the_last_chapter_hands_over_to_the_source_check(self) -> None:
        self.write_plan([])
        self.cmd("skeleton")
        out = ""
        for ch in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["chapters"]:
            code, out = self.put(ch["title"], minimal_body(ch["title"], f"「{ch['title']}」的正文。"))
            self.assertEqual(0, code, out)
        head = out.split("\n")[:2]
        self.assertTrue(head[0].startswith("NEXT: 十章齐了——从来源核实际全文"), head)
        for needle in ("story-template.md", "decisions.json", "init-analysis.md", "RR/prd.md",
                       "「四、写后核对」"):
            self.assertIn(needle, head[1], f"整稿的输入少了「{needle}」")


class ALandedChapterStillGetsItsStarts(PlanCase):
    """已经合法提交的章，设计改了选择：原稿与 Story 字节不动，但当前缺的选定结构照样给出起点。"""

    def starts_in(self, out: str) -> str:
        return out.split("结构起点：", 1)[1] if "结构起点：" in out else ""

    def test_changes_to_the_picks_of_a_landed_chapter(self) -> None:
        self.write_plan(PICKS)
        self.cmd("skeleton")
        draft = self.draft("06")
        draft.write_bytes(("提交后界面停在等待态。\n\n" + TABLE).encode("utf-8"))
        code, out = self.cmd("chapter", "--chapter", "功能说明", "--from", str(draft))
        self.assertEqual(0, code, out)
        draft_bytes, story_bytes = draft.read_bytes(), self.story_path.read_bytes()

        cases = {
            "现有结构不变": (PICKS, []),
            "新增一处": (PICKS + [{"chapter": "06-features", "at": "失败提示", "kind": "table",
                                 "columns": ["情形", "用户看到什么"]}],
                     ["### 失败提示", "| 情形 | 用户看到什么 |"]),
            "改名": ([{**PICKS[0], "at": "本机保存的数据"}],
                   ["### 本机保存的数据", "| 数据 | 保存多久 | 何时清除 |"]),
            "改列": ([{**PICKS[0], "columns": ["数据", "保存多久", "何时清除", "谁能看到"]}],
                   ["| 数据 | 保存多久 | 何时清除 | 谁能看到 |"]),
            "撤回选择": ([], []),
        }
        for name, (picks, needles) in cases.items():
            with self.subTest(case=name):
                self.write_plan(picks)
                code, out = self.cmd("skeleton")
                self.assertEqual(0, code, out)
                starts = self.starts_in(out)
                if needles:
                    for needle in needles:
                        self.assertIn(needle, starts, f"缺的选定结构没给起点：{out[-800:]}")
                    self.assertNotIn("### 本地数据", starts.replace("### 本机保存的数据", ""),
                                     "已经有的结构又给了一遍")
                else:
                    self.assertEqual("", starts, "没缺什么却给了起点")
                self.assertEqual(draft_bytes, draft.read_bytes(), "已提交章的草稿被改写了")
                self.assertEqual(story_bytes, self.story_path.read_bytes(), "Story 被改写了")

    def test_a_landed_chapter_whose_draft_is_gone_gets_current_text_and_starts(self) -> None:
        self.write_plan(PICKS)
        self.cmd("skeleton")
        draft = self.draft("06")
        draft.write_bytes(("提交后界面停在等待态。\n\n" + TABLE).encode("utf-8"))
        self.assertEqual(0, self.cmd("chapter", "--chapter", "功能说明", "--from", str(draft))[0])
        name = draft.name
        draft.unlink()
        self.write_plan(PICKS + [{"chapter": "06-features", "at": "失败提示", "kind": "diagram"}])
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
        self.write_plan([])
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
