"""`story-build` 各命令的单元断言——init 派生什么、chapter 怎么落盘、check 拦什么。

台账（`check_failure_modes.py`）判的是**形态回不回来**：一个已知会犯的错，机制现在抓不抓得住。
本文件判的是**判据本身的边界**：同一条判据，改一个字符就该翻面的那些地方。两者都要有，
因为台账只覆盖曾经真实发生过的错，而边界是它没走到的地方。

夹具借用 `R01-verdict-echo/good`——它是一份最小但完整的工作区（材料 + story + 激活清单 +
决策件）。每个用例在**副本**上跑：这几条命令会写 `decisions.json` 与 `story.md`，
在夹具原地跑会把它写脏，且上一个用例的产物会影响下一个。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import golden_workspace  # noqa: E402
from flow_steps import HUMAN_ZONE, open_decision, settled_decision, walk_to_complete

REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGES = (REPO_ROOT
         / "doc/extensions/skills/story/scripts/core/story/images.mjs")
BUILD = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "REQ-DEMO"
FLOW = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story_flow.py"
#: 一份协议齐全的最小写作设计（十章各一段、结构选择为空）——测正文路径的用例起手前放它。
PLAN_FIXTURE = FIXTURE / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-template.md"

CHAPTER_OUT_OF_CONTRACT = "第十五章"
QUOTE = "提交之后回执没到之前，界面停在等待态"


DRAFT_TEXT = (
    "# AR90006 — 开发需求（AR）\n\n"
    "## 1 简介\n\n### 1.1 需求介绍\n\nx\n\n"
    "## 2 需求分析\n\n### 2.1 场景与功能点\n\nx\n\n"
    "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\nx\n\n"
    "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
    "## 5 上游已声明线索\n\n无。\n")


# 机制按运行环境选 shell（`story/drafts.mjs` 的 `SHELL`）：有 SHELL 变量的是 POSIX shell，
# Windows 上没有它的是 PowerShell。测试用同一条规则选，跑的就是机制引参数时对准的那个。
SHELL = "bash" if os.environ.get("SHELL") or os.name != "nt" else "powershell"


def run_in_shell(command: str, cwd=None) -> subprocess.CompletedProcess:
    """把渲染出来的命令**原样交给宿主的命令行**跑一遍。"""
    exe = shutil.which("pwsh") or shutil.which("powershell")
    args = ([exe, "-NoProfile", "-Command", command + "; exit $LASTEXITCODE"]
            if SHELL == "powershell" else ["bash", "-lc", command])
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180,
                          cwd=None if cwd is None else str(cwd))


def _chapter_bodies(story_path) -> dict:
    """把 story 切成 {章标题: 正文}——夹具的引文要从真正的那一章里取。"""
    out, cur, buf = {}, None, []
    if story_path is None or not Path(story_path).is_file():
        return out
    for line in Path(story_path).read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = line[3:].strip(), []
            continue
        if cur is not None:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return out


def _is_empty_chapter(body: str) -> bool:
    """空章：正文恰是那一句。它已明说这件事不在本需求里，读者的问题也就不存在。"""
    return body.strip() == "本需求不涉及。"


def _chapter_quote(body: str) -> str:
    """取该章正文的一段连续原文作引文。

    不能只找散文句：术语章与异常章天然是表、业务流程章天然是图，
    它们里面的文字同样是「答了这个问题」的证据。所以按**原文顺序**拼，
    取够长的一段——check 只要求它是该章的逐字子串且 ≥12 字。
    """
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "```", "~~~")):
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            cells = [c for c in cells if c and not set(c) <= set("-: ")]
            if not cells:
                continue
            s = max(cells, key=len)
        if len(s) >= 14:
            return s[:60]
    return ""


def _appendix_title() -> str:
    """附录那一章的标题从合同取——用例不写死章名，合同改了它跟着变。"""
    contract = json.loads((REPO_ROOT / "doc/extensions/skills/story/contracts"
                           / "story-chapters.json").read_text(encoding="utf-8"))
    hit = next((c for c in contract.get("chapters") or [] if c.get("appendix")), None)
    return (hit or {}).get("title", "")


def ensure_flow_state(root: Path, feature: str, src: Path, draft_text: str) -> None:
    """skeleton 起手预检需要的流程状态：S1–S3 走完并收口（真实脚本生成契约）。

    08 §2.1 之后 skeleton 的起手预检要读流程契约与材料基准；夹具没有时，
    用真实流程命令把 S1–S3 走完并提交一份提取稿——生成的契约即收口态。
    """
    if (src / "story-flow.json").is_file():
        return
    def flow(*args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", feature,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, f"{args}: {proc.stdout}\n{proc.stderr}"
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    walk_to_complete(flow, src, draft_text)



class StoryBuildCase(unittest.TestCase):
    """每个用例一份新工作区；子类只关心自己那一条判据。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        self.story_path = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"

    # ---- 驱动 ----

    def run_build(self, command: str) -> subprocess.CompletedProcess:
        if command == "skeleton":
            ensure_flow_state(self.root, FEATURE, self.src, self.DRAFT)
        return subprocess.run(
            ["node", str(BUILD), command, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def init_audit(self) -> None:
        """起手状态：决策登记就位。

        init 命令已由 skeleton 接管（08 §2.1）；这里的夹具本就带决策件，
        缺了就补一份空骨架——等价于旧 init 为这些用例做的事。
        """
        decisions = self.src / "decisions.json"
        if not decisions.exists():
            decisions.write_text('{"decisions": [], "no_pending": "夹具：本单无待决"}', encoding="utf-8")

    DRAFT = (
        "# REQ-DEMO — 开发需求（AR）\n\n"
        "## 1 简介\n\n### 1.1 需求介绍\n\nx\n\n"
        "## 2 需求分析\n\n### 2.1 场景与功能点\n\nx\n\n"
        "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\nx\n\n"
        "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
        "## 5 上游已声明线索\n\n无。\n")

    def check_output(self) -> tuple[int, str]:
        proc = self.run_build("check")
        return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()

    def assert_check_names(self, needle: str) -> str:
        """check 必须失败，且**点名**了原因——笼统说「有问题」等于没有区分力。"""
        code, out = self.check_output()
        self.assertEqual(code, 1, f"check 应当失败却过了：{out}")
        self.assertIn(needle, out)
        return out

    # ---- 产物读写 ----

    def story(self) -> str:
        return self.story_path.read_text(encoding="utf-8")

    def rewrite_story(self, old: str, new: str) -> None:
        text = self.story()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.story_path.write_text(text.replace(old, new), encoding="utf-8")


class TestArchiveRedlines(StoryBuildCase):
    """归档件四红线里机器判得了的那条：正文不许出现仓内路径。

    术语表实体词守恒随逐单元系统退场，这个类只剩红线这一面。
    """

    def test_repo_path_in_story_is_named(self) -> None:
        self.init_audit()
        self.rewrite_story("本需求不涉及。\n\n## 术语",
                           "详见 doc/features/REQ-DEMO/AR/design.md。\n\n## 术语")
        self.assert_check_names("仓内路径")


class TestErrorWordingPointsAtForm(StoryBuildCase):
    """报错说的是「这一类事实的落点长什么样」，不是一张待抄的字面清单。

    上一版报的是「落点标在『附录』，但那一章里找不到：WalletMain、cardId、…」。
    模型逐轮照做，把这些字面一个个抄进附录——首跑那个占了全篇 58% 的倾倒区
    不是模型自己想出来的，是门禁一条一条教出来的（失败数 35→11→9→1→6→18）。
    """

    def drop_from_appendix(self, fragment: str) -> None:
        self.rewrite_story(fragment, "")

    def test_the_bare_token_list_style_is_gone_from_the_source(self) -> None:
        """禁止样式在源码里也不该留——留着下一轮就会有人接回去。"""
        source = (REPO_ROOT / "doc/extensions/skills/story/scripts/core/story-build.mjs"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("但那一章里找不到", source)


REVIEW_HUMAN_ZONE = HUMAN_ZONE


class TestReviewForm(StoryBuildCase):
    """评审人要填的只有议题末尾那处填写位——需要说明书就是设计错了。

    曾经这里还有暂缓责任人、完成期限、是否阻塞执行、后续动作、确认人、确认日期、
    确认依据七个字段。评审人打开它先要读一遍字段表，而其中六格他答不上来
    （责任人和期限是排期的事，确认依据是审计的事）。答不上来的格子只会被跳过或胡填。
    每条议题的人工区只有三态与修改意见。
    """

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def write_decision(self) -> None:
        (self.src / "decisions.json").write_text(json.dumps({
            "decisions": [settled_decision(
                "submit-boundary", "提交入口与补卡由两张开发单分别承接",
                "提交与补卡要不要放在同一张单里做。", "本单只做提交与回执展示，验收不含补卡。",
                said="补卡另起一张单")],
        }, ensure_ascii=False), encoding="utf-8")

    def test_the_human_zone_is_three_states_and_an_opinion(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.assertIn(REVIEW_HUMAN_ZONE, text)
        for gone in ("暂缓责任人", "完成期限", "是否阻塞执行", "后续动作",
                     "确认人", "确认日期", "确认依据", "**状态**",
                     "方案选择：", "审核结果：", "不同意原因", "调整结论"):
            self.assertNotIn(gone, text, f"「{gone}」不该再出现在评审记录里")

    def test_filled_human_zone_survives_a_rerender(self) -> None:
        """人填过的内容一个字节都不能动——重算它等于把做完的决定推回去一次。

        连**旧形态**留下的字也要保住：字段是被裁掉了，人当时写在里面的话不是。
        """
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        anchor = "<!-- decision: submit-boundary -->"
        filled = text.replace(
            "修改意见：\n\n" + anchor,
            "修改意见：范围要含补卡入口。\n\n**确认人**：某评审人\n\n" + anchor)
        self.assertNotEqual(text, filled, "夹具变了，用例要跟着改")
        self.review_path.write_text(filled, encoding="utf-8")

        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("修改意见：范围要含补卡入口。", again)
        self.assertIn("**确认人**：某评审人", again, "旧形态里人写过的字也要保住")

    def test_legacy_fields_in_the_review_are_named(self) -> None:
        """人工区之外又长回签署字段与状态行时，check 要点名。"""
        self.init_audit()
        self.review_path.write_text(
            "# 评审记录\n\n### 1. 提交入口与补卡由两张开发单分别承接\n\n"
            "评审结论：\n\n"
            "<!-- decision: submit-boundary -->\n\n"
            "**确认日期**：\n\n**状态**：草稿（待开发确认）\n",
            encoding="utf-8")
        out = self.assert_check_names("评审记录里出现")
        self.assertIn("确认日期", out)
        self.assertIn("状态行", out)


class TestProcessFilesStayOutOfTheArRoot(StoryBuildCase):
    """AR 根下只有交付文档：过程件（如评审处置台账）进 story-src。"""

    def ar(self) -> Path:
        return self.root / "doc" / "features" / FEATURE / "AR"

    def test_a_file_in_the_root_is_moved_as_is(self) -> None:
        self.init_audit()
        # 拿一个**中性的过程件**当例子：判的是「AR 根只放交付件」这条通用规则，
        # 不绑任何一份具体台账的名字（旧的 review-disposition.json 已随回流退场）。
        (self.ar() / "update-notes.md").write_text("过程记录\n", encoding="utf-8")
        out = self.assert_check_names("AR/update-notes.md 不该在这一层")
        self.assertIn("原样挪进 AR/story-src/", out)

    def test_the_ledger_in_story_src_is_not_a_stray(self) -> None:
        self.init_audit()
        (self.src / "update-notes.md").write_text("过程记录\n", encoding="utf-8")
        _, out = self.check_output()
        self.assertNotIn("update-notes.md", out)


class TestRequirementIdInTitle(StoryBuildCase):
    """大标题带需求编号——归档件离开这个仓库后，编号是它回到需求系统的唯一一根绳子。"""

    def test_title_without_the_id_is_named(self) -> None:
        self.init_audit()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, "# " + first[2:].replace(FEATURE, "").strip())
        out = self.assert_check_names("大标题缺需求编号")
        self.assertIn(FEATURE, out, "报错要把该写的编号给出来")


class TestRedlineScope(StoryBuildCase):
    """逐类作用域：工程标识只管附录之外，文档坐标全篇判；一行命中几种坐标只报一条。"""

    def _put_in_appendix(self, line: str) -> None:
        """作者说明写在技术约定那一节的末尾：机器区之外、下一节之前。"""
        anchor = "### 改动边界"
        self.assertIn(anchor, self.story())
        self.rewrite_story(anchor, line + "\n\n" + anchor)

    def test_a_doc_coordinate_in_the_appendix_is_named(self) -> None:
        """附录里作者写的那部分同样随归档走：指向不随归档的文件，放在哪里读者都打不开。"""
        self.init_audit()
        self.assertEqual(0, self.check_output()[0])
        self._put_in_appendix("口径以 PRD §3.2 为准。")
        self.assert_check_names("出现文档坐标")

    def test_one_line_with_several_coordinates_is_one_report(self) -> None:
        """同一行里既有章节坐标又有文件名：一条报错，两处都列出来——不再由两道判据各报一次。"""
        self.init_audit()
        self._put_in_appendix("口径见 spec §5.1 与 prd.md。")
        out = self.assert_check_names("出现文档坐标 1 处")
        self.assertIn("「spec §5.1」「prd.md」", out)
        self.assertNotIn("悬空引用", out)

    def test_identifiers_stay_legal_in_the_appendix(self) -> None:
        """附录仍是工程标识的落点——顺手把它一起收紧，作者就无处可写了。"""
        self.init_audit()
        self._put_in_appendix("| 接口 | 用途 |\n|---|---|\n| queryLossState | 查挂失结果 |")
        self.assertEqual(0, self.check_output()[0])


class TestDecisionUnits(StoryBuildCase):
    """决策登记走独立派生通道：取舍理由在材料里没有，它是起草时判出来的。"""

    DECISIONS = {
        "decisions": [
            settled_decision("D1", "挂失结果以卡片服务的回执为准",
                             "挂失办没办成，以哪一侧的说法为准。",
                             "以卡片服务的回执为准，页面照回执显示。",
                             said="以卡片服务回执为准", category="质量指标"),
            settled_decision("D2", "同卡同状态的重复提交按一次算",
                             "同一张卡短时间内重复提交怎么处理。",
                             "按一次算，第二次直接回到等待态。",
                             said="重复提交按一次算", category="业务规则"),
            open_decision("D3", "线下渠道的入口这轮收不收",
                          "线下渠道的入口要不要一起收进本单。",
                          [("本单先不收，等渠道方给时间表", "范围不变"),
                           ("一起收", "范围扩到渠道侧")],
                          "按第 1 种做。"),
        ],
    }

    def write_decisions(self, decisions=None) -> None:
        path = self.src / "decisions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["decisions"] = decisions if decisions is not None else self.DECISIONS["decisions"]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_an_empty_register_is_legal_and_untouched(self) -> None:
        """空数组合法（08 §2.1）：skeleton 收下它，也绝不覆盖这份登记。"""
        self.write_decisions([])
        before = (self.src / "decisions.json").read_text(encoding="utf-8")
        self.assertEqual(0, self.run_build("skeleton").returncode)
        self.assertEqual(before, (self.src / "decisions.json").read_text(encoding="utf-8"),
                         "空登记被改写了——合法状态不该被机制动过")

    def test_editing_a_decision_never_trips_the_material_drift_gate(self) -> None:
        """决策件是流程里的活件：评审回填、遗漏补写都是既定动作，不该撞指纹门禁。"""
        self.write_decisions()
        self.init_audit()
        self.assertEqual(0, self.check_output()[0])
        self.write_decisions(self.DECISIONS["decisions"] + [
            open_decision("D4", "回执超时的等待时长", "回执迟迟不到时等多久。",
                          [("先按现网默认值", "现在就能定"), ("等渠道方给数", "要等渠道方")],
                          "按第 1 种做。", category="业务规则")])
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertNotIn("材料在枚举之后变了", out)


class SourceNumbersStayInTheSpec(StoryBuildCase):
    """§9.1.4 里的局部编号（9.1.4.1）只在 spec 里成立：进附录时去掉，业务标题里的数字不动。"""

    EVENTS = ('#### 9.1.4 埋点\n\n##### 9.1.4.1 开户成功率\n\n| 统计点 | 适用结果 |\n|---|---|\n| 信息校验 | 步骤成功 |\n\n'
              '##### 2.0 版本的查询成功率\n\n- 查询结果按次记录。\n\n')

    def test_the_local_number_is_dropped_and_business_digits_kept(self) -> None:
        self.init_audit()
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start, end = text.index("#### 9.1.4"), text.index("#### 9.1.5")
        spec.write_text(text[:start] + self.EVENTS + text[end:], encoding="utf-8")
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        story = self.story()
        zone = story[story.index("<!-- story-build:begin 技术约定·埋点 "):]
        self.assertIn("##### 开户成功率", zone)
        self.assertNotIn("9.1.4.1", zone)
        self.assertIn("##### 2.0 版本的查询成功率", zone)


class TheEventDesignIsProjectedWhole(StoryBuildCase):
    """§9.1.4 是埋点设计的唯一完整说明：附录按原次序整节投影，不只搬表。

    只搬表的话，流程怎么分、指标是什么、哪些交互由自动上报采集全丢了，归档件里只剩名目表。
    """

    EVENTS = '#### 9.1.4 埋点\n\n开户与结果查询两个流程各看一个成功率。\n\n##### 开户成功率\n\n衡量开户办理的完成比例：分子是开户成功，分母是全部提交开户；打点在开户办理流程的信息校验与短信验证两步。\n\n| 统计点 | 所在流程 | 适用结果 | 代码现状 |\n|---|---|---|---|\n| 信息校验 | 开户办理 | 步骤成功 / 普通失败 | 检索零命中 |\n| 短信验证 | 开户办理 | 步骤成功 / 普通失败 / 主动取消 | 检索零命中 |\n\n- 页面进入、点击由自动运维上报采集。\n\n##### 查询成功率\n\n衡量开户结果查询的成功比例：分子是查询成功，分母是全部查询；打点在结果查询流程的查询开户结果一步。\n\n| 统计点 | 所在流程 | 适用结果 | 代码现状 |\n|---|---|---|---|\n| 查询开户结果 | 结果查询 | 步骤成功 / 普通失败 | 检索零命中 |\n\n'

    def setUp(self) -> None:
        super().setUp()
        self.init_audit()
        self.spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        text = self.spec.read_text(encoding="utf-8")
        start, end = text.index("#### 9.1.4"), text.index("#### 9.1.5")
        self.spec.write_text(text[:start] + self.EVENTS + text[end:], encoding="utf-8")
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def zone(self) -> str:
        return self.zone_of("技术约定·埋点")

    def zone_of(self, name: str) -> str:
        text = self.story()
        at = text.index(f"<!-- story-build:begin {name} ")
        return text[at:text.index("<!-- story-build:end -->", at)]

    def test_prose_headings_tables_and_lists_come_in_order(self) -> None:
        """埋点这个 H4 标题归作者（草稿铺好），机器区从它下面的总述开始。"""
        zone = self.zone()
        self.assertNotIn("#### 埋点", zone)
        order = ["开户与结果查询两个流程", "##### 开户成功率", "衡量开户办理的完成比例",
                 "| 信息校验 |", "| 短信验证 |", "- 页面进入、点击由自动运维上报采集", "##### 查询成功率",
                 "| 查询开户结果 |"]
        at = [zone.index(piece) for piece in order]
        self.assertEqual(sorted(at), at, "段落、小标题、表与列表没按原次序投影")

    def test_numbering_the_zone_headings_is_not_an_edit(self) -> None:
        """登记时先投影后编号：区里的指标小标题被编上号，核对不报、再投影也不当手改。"""
        proc = self.run_build("number")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertRegex(self.zone(), r"##### 10\.1\.4\.\d+ 开户成功率")
        code, out = self.check_output()
        self.assertNotIn("技术约定·埋点", out, out)
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_the_code_status_column_stays_in_spec(self) -> None:
        self.assertNotIn("代码现状", self.zone())
        self.assertNotIn("检索零命中", self.zone())

    def test_other_subsections_keep_their_own_conclusion(self) -> None:
        """数据、配置没有表时，各自的「不涉及」进各自的机器区——H4 标题已经说明是哪一项。"""
        self.assertIn("不涉及：", self.zone_of("技术约定·数据"))
        self.assertIn("不涉及：", self.zone_of("技术约定·配置"))

    def test_relative_references_are_rebased_to_the_story(self) -> None:
        """spec 在 spec/、归档件在 AR/：相对引用要换成从归档件出发，否则投过去就是坏链。

        锚点指回 spec 那一处（它指的标题在归档件里不存在）；外链与围栏里的样例不动。
        """
        text = self.spec.read_text(encoding="utf-8")
        start, end = text.index("#### 9.1.4"), text.index("#### 9.1.5")
        self.spec.write_text(text[:start] + '#### 9.1.4 埋点\n\n详见[口径说明](detail.md)与[上级材料](../assets/rules.md#口径)，外部规范见[平台](https://example.com/spec)。\n\n##### 开户成功率\n\n回看[本节开头](#开户成功率)；示意图 ![流程](img/flow.png)。\n\n| 步骤 | 依据 | 代码现状 |\n|---|---|---|\n| 信息校验 | [校验规则](rules/check.md) | 检索零命中 |\n\n```text\n[围栏里的样例](detail.md)\n```\n\n[ref]: notes/ref.md\n\n' + text[end:], encoding="utf-8")
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        zone = self.zone()
        for want in ("[口径说明](../spec/detail.md)", "[上级材料](../assets/rules.md#口径)",
                     "[平台](https://example.com/spec)", "[本节开头](../spec/spec.md#开户成功率)",
                     "![流程](../spec/img/flow.png)", "[校验规则](../spec/rules/check.md)",
                     "[围栏里的样例](detail.md)", "[ref]: ../spec/notes/ref.md"):
            with self.subTest(want=want):
                self.assertIn(want, zone)

    def test_the_projected_zone_passes_check_and_a_source_change_is_caught(self) -> None:
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.spec.write_text(self.spec.read_text(encoding="utf-8").replace(
            "分母是全部提交开户", "分母是全部进入开户页的用户"), encoding="utf-8")
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("技术约定·埋点", out)
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("分母是全部进入开户页的用户", self.zone())


class TheMachineZoneIsCheckedAgainstItsSource(StoryBuildCase):
    """附录的机器区与真源逐区逐行比 —— **不先 project 再比**。

    先 project 再比是必绿的：那等于拿刚写下去的东西跟自己比。这一组直接改盘上的机器区
    （非首列、删行、换序、破标记）与真源，check 必须发现，且**一个字节都不许写**。
    """

    def setUp(self) -> None:
        super().setUp()
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, "夹具起点本该是干净的：" + out)

    def zone_lines(self, name: str) -> tuple[int, int, list[str]]:
        lines = self.story().split("\n")
        at = next(i for i, l in enumerate(lines)
                  if l.startswith("<!-- story-build:begin " + name + " "))
        end = next(i for i in range(at + 1, len(lines))
                   if lines[i].strip() == "<!-- story-build:end -->")
        return at, end, lines

    def rewrite(self, lines: list[str]) -> None:
        self.story_path.write_text("\n".join(lines), encoding="utf-8")

    def expect_caught(self, needle: str = "机器区") -> None:
        before = self.story_path.read_bytes()
        code, out = self.check_output()
        self.assertEqual(1, code, "改过的机器区没被发现：" + out)
        self.assertIn(needle, out)
        self.assertEqual(before, self.story_path.read_bytes(), "只读检查写了盘")

    def test_a_change_outside_the_first_column_is_caught(self) -> None:
        """只比首列的老判据看不见这一类：标识没动，说明被改了。"""
        at, end, lines = self.zone_lines("规约判定")
        target = next(i for i in range(at + 1, end) if "SMP-01" in lines[i])
        lines[target] = "| 甲域约束 | SMP-01 | 不命中 | 改成了别的说法 |"
        self.rewrite(lines)
        self.expect_caught()

    def test_a_deleted_row_is_caught(self) -> None:
        at, end, lines = self.zone_lines("规约判定")
        del lines[end - 1]
        self.rewrite(lines)
        self.expect_caught()

    def test_a_reordered_pair_of_rows_is_caught(self) -> None:
        """行序算在内：拿 Set 比集合的老判据换了顺序也看不见。"""
        at, end, lines = self.zone_lines("规约判定")
        body = list(range(at + 1, end))
        self.assertGreaterEqual(len(body), 2)
        lines[body[-1]], lines[body[-2]] = lines[body[-2]], lines[body[-1]]
        self.rewrite(lines)
        self.expect_caught()

    def test_a_broken_end_marker_is_caught(self) -> None:
        at, end, lines = self.zone_lines("改动边界")
        lines[end] = "<!-- 结束标记被改坏了 -->"
        self.rewrite(lines)
        self.expect_caught("结束标记")

    def test_a_duplicated_zone_is_caught(self) -> None:
        at, end, lines = self.zone_lines("改动边界")
        self.rewrite(lines[:end + 1] + lines[at:end + 1] + lines[end + 1:])
        self.expect_caught("两段机器区")

    def test_a_deleted_required_spec_section_is_not_an_empty_expectation(self) -> None:
        """只删 spec §9.1.1 与对应的机器区，作者区留一句说明——旧判据返回 0。

        「没有这一节」与「这件事不涉及」不是一回事：后者是写出来的结论，评审者读得到。
        """
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start = text.index("#### 9.1.1")
        end = text.index("#### 9.1.2")
        spec.write_text(text[:start] + text[end:], encoding="utf-8")
        at, endline, lines = self.zone_lines("技术约定·接口")
        lines[at:endline + 1] = ["这一节的接口约定见业务方案章。"]
        self.rewrite(lines)
        self.expect_caught("§9.1.1")

    def test_an_unknown_machine_zone_is_not_author_text(self) -> None:
        """合同里没有这个名字的机器区：它没有真源可比，会一直冒充现行投影。"""
        at, endline, lines = self.zone_lines("改动边界")
        extra = ["<!-- story-build:begin obsolete · 由某处生成，改它请改真源 -->",
                 "| 旧 | 行 |", "|---|---|", "| 1 | 2 |", "<!-- story-build:end -->"]
        self.rewrite(lines[:endline + 1] + [""] + extra + lines[endline + 1:])
        self.expect_caught("obsolete")

    def test_an_orphan_end_marker_is_caught(self) -> None:
        at, endline, lines = self.zone_lines("改动边界")
        self.rewrite(lines[:endline + 1] + ["", "<!-- story-build:end -->"]
                     + lines[endline + 1:])
        self.expect_caught("孤立")

    def test_a_nested_begin_marker_is_caught(self) -> None:
        """一个结束只配一个开始：两个开始都去认后面同一行，其中一段的边界是编的。"""
        at, endline, lines = self.zone_lines("改动边界")
        inner = "<!-- story-build:begin 接口 · 由spec §9.1 技术契约生成，改它请改真源 -->"
        self.rewrite(lines[:at + 1] + [inner] + lines[at + 1:])
        self.expect_caught("还没关上")

    def test_a_changed_source_is_caught(self) -> None:
        """真源变了而机器区没跟着变——报的是区与它的责任真源，不是让作者改机器区。"""
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        self.assertIn("没有新增或变更的端云契约", text)
        spec.write_text(text.replace("没有新增或变更的端云契约",
                                     "接口改名成 submitBusinessOrder"), encoding="utf-8")
        before = self.story_path.read_bytes()
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("机器区", out)
        self.assertIn("改真源", out, "没有指出该改的是真源")
        self.assertEqual(before, self.story_path.read_bytes(), "只读检查写了盘")

    def test_an_unreadable_required_spec_is_not_an_empty_expectation(self) -> None:
        """spec 读不到不等于「期望是空的」：那会让缺一整节的附录静默通过。"""
        (self.root / "doc" / "features" / FEATURE / "spec" / "spec.md").unlink()
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("读不到 spec", out)

    def test_the_authors_own_words_next_to_the_zone_are_left_alone(self) -> None:
        """作者解释区在机器标记之外：不参加比较，也不被生成器重写。"""
        at, end, lines = self.zone_lines("改动边界")
        note = "这一节的取舍见业务方案章。"
        self.rewrite(lines[:at] + [note, ""] + lines[at:])
        code, out = self.check_output()
        self.assertEqual(0, code, "作者写在机器区旁边的话被当成了改动：" + out)
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(note, self.story(), "project 把作者的解释冲掉了")


class TestOwnRequirementIdIsNotAnIdentifier(StoryBuildCase):
    """本需求自己的编号不是工程标识。

    ①b 要求大标题带着它，材料清单也要写清这份文档出自哪张单——它恰恰是归档件与
    需求系统之间唯一的绳子。判它违规，两条判据就打架，作者无路可走。
    实测一轮实跑卡死在这里：模型反复改标题、始终过不了，最后没登记成文就交了。

    这条**离线跑不出来**（离线没有来源单元，标识符表是空的），所以必须在线跑。
    """

    def _put_id_in_materials(self) -> None:
        """在夹具的 spec 上**追加**一段带本需求编号的范围说明。

        不整份覆盖：spec §9.1 是附录机器区的真源，换掉它等于换了真源，
        那时 ⑫b 报「机器区与真源对不上」是对的——而这一条要测的是编号，不是附录。
        """
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        before = spec.read_text(encoding="utf-8") if spec.is_file() else "# " + FEATURE
        spec.write_text(
            before.rstrip("\n")
            + "\n\n## 1. 范围\n\n本单 " + FEATURE + " 只改提交入口。\n",
            encoding="utf-8")

    def test_the_title_carrying_the_id_passes(self) -> None:
        self._put_id_in_materials()
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertIn(FEATURE, self.story().split("\n", 1)[0], "夹具的大标题本来就带编号")

    def test_another_repo_identifier_is_still_named(self) -> None:
        """放行的只有本需求编号这一个——别的标识照拦，不然等于把 ⑩ 关掉。"""
        self._put_id_in_materials()
        self.init_audit()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n提交走 queryLossEligibility 这个接口。")
        self.assert_check_names("工程标识")


class TestFormLints(StoryBuildCase):
    """三条形态 lint：图的承接与图题、材料清单的行形态、正文小节的编号。

    三条此前都只写在模板注释里，实测两轮四份产物一条都没达成——三张图全部把说明
    写在图后（读者先看见图再看见它是什么）、材料清单被写成表且没有一条能定位到原件、
    小节编号一章一个样。有判据的形态则全部达成。形态要么接上判据，要么承认它是建议。
    """

    IMAGE = "![图 1 · 提交入口页面布局](entry.png)"

    def put_features(self, body: str) -> None:
        text = self.story()
        head = "## 功能说明\n\n"
        start = text.index(head) + len(head)
        end = text.index("\n## ", start)
        self.story_path.write_text(text[:start] + body + text[end:], encoding="utf-8")

    def put_materials(self, body: str) -> None:
        text = self.story()
        head = "### 材料清单\n\n本篇据以写成的材料。\n\n"
        start = text.index(head) + len(head)
        self.story_path.write_text(text[:start] + body, encoding="utf-8")

    # ---- lint 1：图前承接 + 图题形态 ----

    def test_an_image_with_a_lead_sentence_passes(self) -> None:
        self.put_features("### 6.1 提交与回执\n\n图 1 是提交入口的位置：\n\n"
                          + self.IMAGE + "\n")
        self.init_audit()
        code, out = self.check_output()
        self.assertNotIn("图前一句承接", out)
        self.assertNotIn("图题", out)

    # ---- lint 2：材料清单的行形态 ----

    def test_a_material_list_written_as_a_table_is_named(self) -> None:
        self.put_materials("| 材料 | 贡献 |\n|---|---|\n| 甲需求 PRD | 状态取值 |\n")
        self.init_audit()
        self.assert_check_names("材料清单用列表不用表")

    def test_a_material_row_without_a_link_is_named(self) -> None:
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。\n")
        self.init_audit()
        self.assert_check_names("每份材料给一条原文链接")

    def test_a_link_that_cannot_be_opened_is_named(self) -> None:
        """链接得能点开——裸相对路径解析错一层就是断链。

        实测的失效形态：E 节写 `[RR/prd.md](RR/prd.md)`。story.md 在 AR/ 下，
        这个路径解析出来是 `AR/RR/prd.md`，不存在。行形态判抓不到它——那条只看
        链接落在需求目录的哪一段，`RR` 在允许集里就放行。「这一段允许链」与
        「这个链接能不能点开」是两件事，得分开判。
        """
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](RR/prd.md)\n")
        self.init_audit()
        out = self.assert_check_names("链接点不开")
        self.assertIn("RR/prd.md", out, "报错要把点不开的那个目标给出来")

    def test_a_link_that_resolves_passes(self) -> None:
        """同一份材料写对了相对层级就该过——判的是能不能点开，不是长什么样。"""
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](../RR/prd.md)\n")
        self.init_audit()
        code, out = self.check_output()
        self.assertNotIn("链接点不开", out)

    def test_the_material_link_is_the_one_place_a_repo_path_may_appear(self) -> None:
        """豁免只到这一节的链接语法：正文里的仓内路径照拦。"""
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, out)          # 夹具的材料清单本来就带链接

        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n实现见 doc/features/REQ-DEMO/spec/spec.md。")
        self.assert_check_names("仓内路径")


class TestAuthorWrittenNumbersAreStripped(unittest.TestCase):
    """作者自己写的裸序号要先剥掉，否则 `number` 再铺一层就是两个号。

    实测（`story-suite-20260904-091600`）：39 处小节标题里 32 处长成
    `### 1.1 1 闸机前的窘境`——`1.1` 是机器铺的，后面那个 `1` 是作者写的。

    **判据是位置不是词**：作者编号是一条从 1 开始的递增序列，一个裸整数接得上
    这条序列才算序号。上一版拿「后面不是量词」当主判据，被钱包域最常见的形态打穿——
    `20 元面额`、`30 秒超时`、`4 位密码`、`7 天内生效` 全会被剥掉第一个字，
    而量词白名单是一张会不断长的词表。量词现在退为第二道，只挡「内容数字恰好接上序列」。

    剥的动作在 `renumberStory` 里，不在 `normalizeHeading`——后者没有位置信息，
    而它被十几处标题匹配共用，剥错一个字那一节就「找不到」。
    """

    @staticmethod
    def renumber(*subsections: str) -> list[str]:
        """把几个小节摆进同一章重编号，返回 `### ` 行。"""
        body = "".join(f"### {t}\n\n正文。\n\n" for t in subsections)
        doc = "# X\n\n## 背景\n\n" + body
        script = (
            "import { renumberStory } from "
            + json.dumps((REPO_ROOT / "doc/extensions/skills/story/scripts/core/story/document.mjs")
                         .resolve().as_uri())
            + ";import { readFileSync } from 'node:fs';"
            + "const c = JSON.parse(readFileSync("
            + json.dumps(str(REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json"))
            + ", 'utf-8'));"
            + "process.stdout.write(renumberStory(process.argv[1], c.chapters, c.heading_counters));")
        proc = subprocess.run(["node", "--input-type=module", "-e", script, "--", doc],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        assert proc.returncode == 0, proc.stderr
        return [l for l in proc.stdout.split("\n") if l.startswith("### ")]

    def test_a_bare_sequence_is_stripped(self) -> None:
        """1、2、3 接得上序列，全剥。"""
        self.assertEqual(
            ["### 1.1 闸机前的窘境", "### 1.2 本需求改变什么", "### 1.3 成功怎么衡量"],
            self.renumber("1 闸机前的窘境", "2 本需求改变什么", "3 成功怎么衡量"))

    def test_an_unnumbered_section_does_not_break_the_sequence(self) -> None:
        """作者漏编中间某节：他自己的序列没断，后面那个仍是序号。

        这正是实跑产物 6 章的形状——1、2、（页面状态无号）、3。
        按「等于机器序位」判就剥不掉最后那个，按序列判剥得掉。
        """
        self.assertEqual(
            ["### 1.1 签约入口", "### 1.2 签约页", "### 1.3 页面状态", "### 1.4 管理页"],
            self.renumber("1 签约入口", "2 签约页", "页面状态", "3 管理页"))

    def test_content_numbers_are_never_touched(self) -> None:
        """业务名开头的数字是内容——它们接不上序列，一个都不许动。

        这九个是复审者拿钱包域试出来的：上一版全被剥掉了第一个字。
        """
        for title in ("20 元面额的取舍", "30 秒超时", "7 天内生效", "24 小时",
                      "4 位密码", "6 位验证码", "3 方联调", "12 月账单", "2 期分批"):
            with self.subTest(title=title):
                self.assertEqual([f"### 1.1 {title}"], self.renumber(title))

    def test_a_content_number_that_lands_on_the_sequence_is_held_by_the_counter(self) -> None:
        """第二道：内容数字恰好接上序列时，看它后面是不是量词。"""
        self.assertEqual(["### 1.1 3 种签约情形"], self.renumber("3 种签约情形"))
        self.assertEqual(["### 1.1 1 元起充"], self.renumber("1 元起充"))

    def test_a_number_that_skips_the_sequence_stays(self) -> None:
        """作者跳号（1 之后直接写 3）是他写错了——留着让人看见，不猜。"""
        self.assertEqual(["### 1.1 签约入口", "### 1.2 3 管理页"],
                         self.renumber("1 签约入口", "3 管理页"))

    def test_normalize_heading_does_not_strip_bare_numbers(self) -> None:
        """`normalizeHeading` 被十几处标题匹配共用，它不碰裸序号。"""
        script = ("import { normalizeHeading } from "
                  + json.dumps((REPO_ROOT / "doc/extensions/skills/story/scripts/core/story/document.mjs")
                               .resolve().as_uri())
                  + ";process.stdout.write(normalizeHeading(process.argv[1]));")
        for title, want in (("1 闸机前的窘境", "1 闸机前的窘境"),   # 不剥
                            ("1.1 已经带号", "已经带号"),
                            ("1. 单级带点", "单级带点"),
                            ("10.1.1 接口", "接口"),
                            ("A. 接口", "A. 接口")):             # 字母序已退出，不再当序号剥
            with self.subTest(title=title):
                proc = subprocess.run(["node", "--input-type=module", "-e", script, "--", title],
                                      capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=60)
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertEqual(want, proc.stdout)


class TestNumbering(StoryBuildCase):
    """`number`：章序、小节序、图题序号由机器铺。

    上一轮它们是模板里的一句要求加一条 lint。实测顺境的那份做了、逆境的那份整章丢光
    ——而这件事根本不需要人来做：章序由合同定死，节序就是出现顺序，图序就是全篇顺序。
    机器铺完，判据也就不必再判自己的输出（lint 3 与图题前缀判随之退役）。
    """

    def put_features(self, body: str) -> None:
        text = self.story()
        head = "## 功能说明\n\n"
        start = text.index(head) + len(head)
        end = text.index("\n## ", start)
        self.story_path.write_text(text[:start] + body + text[end:], encoding="utf-8")

    def number(self) -> str:
        proc = self.run_build("number")
        self.assertEqual(proc.returncode, 0, f"number 跑不起来：{proc.stderr}")
        return self.story()

    def subsections(self, text: str) -> list:
        return [l for l in text.split("\n") if l.startswith("### ")]

    def test_a_missing_number_is_filled_in(self) -> None:
        self.put_features("### 提交与回执\n\n提交之后停在等待态。\n")
        self.assertIn("### 6.1 提交与回执", self.number())

    def test_a_number_from_another_chapter_is_corrected(self) -> None:
        """`### 4.1` 出现在第六章，「见 4.1」就指错地方——机器按它所在的章重编。"""
        self.put_features("### 4.1 提交与回执\n\n提交之后停在等待态。\n")
        self.assertIn("### 6.1 提交与回执", self.number())

    def test_out_of_order_numbers_are_resequenced(self) -> None:
        self.put_features("### 6.3 提交与回执\n\n提交之后停在等待态。\n\n"
                          "### 6.1 失败与重试\n\n失败之后可以重试。\n")
        subs = [s for s in self.subsections(self.number()) if s.startswith("### 6.")]
        self.assertEqual(["### 6.1 提交与回执", "### 6.2 失败与重试"], subs)

    def test_running_it_twice_changes_nothing(self) -> None:
        self.put_features("### 提交与回执\n\n提交之后停在等待态。\n")
        once = self.number()
        self.assertEqual(once, self.number(), "幂等：已经对的文件重跑一个字节都不该动")

    def test_figure_titles_are_numbered_across_the_whole_document(self) -> None:
        self.put_features("### 提交与回执\n\n下面是提交入口的位置：\n\n"
                          "![提交入口页面布局](entry.png)\n\n"
                          "状态走向如下：\n\n"
                          "![图 7 · 状态走向](flow.png)\n")
        text = self.number()
        self.assertIn("![图 1 · 提交入口页面布局](entry.png)", text)
        self.assertIn("![图 2 · 状态走向](flow.png)", text)

    def test_any_depth_is_numbered(self) -> None:
        """编号不设层级上限：几级小标题就几段号；换上级时下级从 1 重来。"""
        self.put_features("### 提交与回执\n\n#### 回执\n\n##### 超时\n\n###### 重试\n\n#### 撤回\n")
        text = self.number()
        for line in ("### 6.1 提交与回执", "#### 6.1.1 回执", "##### 6.1.1.1 超时",
                     "###### 6.1.1.1.1 重试", "#### 6.1.2 撤回"):
            self.assertIn(line, text)

    def test_the_appendix_is_numbered_like_the_body(self) -> None:
        """附录与正文同一条编号规则：章号.节号，H4、H5 往下接。"""
        text = self.number()
        self.assertIn("### 10.1 技术约定", text)
        self.assertIn("#### 10.1.1 接口", text)
        self.assertIn("### 10.4 材料清单", text)

    def test_a_chapter_outside_the_contract_is_left_alone(self) -> None:
        """合同里没有的章原样留着：那是 check ① 要点名的事，不是编号该悄悄接受的。"""
        self.rewrite_story("## 功能说明", "## " + CHAPTER_OUT_OF_CONTRACT)
        text = self.number()
        self.assertIn("## " + CHAPTER_OUT_OF_CONTRACT, text)


class TestGoldenNumbering(unittest.TestCase):
    """金样是编号的仲裁锚：跑一遍不变，去掉号再跑还原成它。"""

    GOLDEN = REPO_ROOT / "test" / "story" / "golden" / "story-金样-AR90004.md"

    def renumber(self, text: str) -> str:
        script = (
            "import * as fs from 'node:fs';"
            "import { renumberStory } from './doc/extensions/skills/story/scripts/core/story/document.mjs';"
            "const c = JSON.parse(fs.readFileSync("
            "'doc/extensions/skills/story/contracts/story-chapters.json','utf-8'));"
            "let s=''; process.stdin.on('data',d=>s+=d).on('end',()=>"
            "process.stdout.write(renumberStory(s, c.chapters)));"
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            input=text, capture_output=True, text=True, encoding="utf-8",
            cwd=str(REPO_ROOT), timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def test_the_golden_is_a_fixed_point(self) -> None:
        text = self.GOLDEN.read_text(encoding="utf-8")
        self.assertEqual(text, self.renumber(text), "编号拦金样即编号错")

    def test_a_de_numbered_golden_comes_back_byte_for_byte(self) -> None:
        import re
        text = self.GOLDEN.read_text(encoding="utf-8")
        stripped = "\n".join(
            re.sub(r"!\[图\s*\d+\s*[·・]\s*", "![",
                   re.sub(r"^(#{2,4})\s+\d+(?:\.\d+)*\.?\s+", r"\1 ", line))
            for line in text.split("\n"))
        self.assertNotEqual(text, stripped, "去号版该和金样不一样，否则这条什么都没验")
        self.assertEqual(text, self.renumber(stripped))


class TestSmallLedgerItems(StoryBuildCase):
    """六件小账里能机器判的那一条：澄清正文禁标题行。"""

    def decisions(self) -> dict:
        return json.loads((self.src / "decisions.json").read_text(encoding="utf-8"))

    def write_decisions(self, data: dict) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def a_decision(self, clarification: str) -> dict:
        """一条字段齐备的决策——本用例只想让澄清正文那一条判据翻面。"""
        contract = json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))
        category = (contract.get("decision_categories") or [{}])[0].get("key", "")
        return {
            "id": "D-1", "title": "入口的摆放位置按上游稿走", "status": "settled",
            "category": category, "decider": "产品负责人",
            "clarification": clarification,
        }

    def test_a_heading_line_in_the_clarification_is_named(self) -> None:
        """澄清正文里的小标题写成加粗段首，不用 `#` 标题行。"""
        self.init_audit()
        self.write_decisions({"decisions": [
            self.a_decision("### 背景\n\n本条说明这件事的来龙去脉。")]})
        out = self.assert_check_names("的澄清正文里有标题行")
        self.assertIn("加粗段首", out)

    def test_a_bold_lead_in_the_clarification_passes(self) -> None:
        """反面：加粗段首是定稿形态，不该被拦。"""
        self.init_audit()
        self.write_decisions({"decisions": [
            self.a_decision("**背景**：本条说明这件事的来龙去脉。")]})
        _, out = self.check_output()
        self.assertNotIn("的澄清正文里有标题行", out)



class TestRetiredThings(unittest.TestCase):
    """本轮退场的东西，机制层不该再有它们的痕迹——退场靠 grep 守，不靠记性。"""

    EXT = REPO_ROOT / "doc" / "extensions"

    def ext_text(self) -> str:
        out = []
        for path in sorted(self.EXT.rglob("*")):
            if path.suffix in (".mjs", ".js", ".py", ".md", ".json", ".yaml"):
                out.append(path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(out)

    def test_the_adapt_preconditions_are_gone(self) -> None:
        """framework 版本门槛与热修清单退场——framework 的事不归 adapt 管。"""
        text = self.ext_text()
        for gone in ("3.0.0", "capability-resolution", "MaisonPrimaryButton"):
            self.assertNotIn(gone, text, f"「{gone}」还留在扩展包里")

    def test_adapt_leaves_no_work_files_behind(self) -> None:
        """adapt 不落任何工作件：确认靠 git diff，不写 before 快照。

        写快照的做法要求「先扫一遍建基线、再核对」两步，而基线本身会过期——
        目标在两步之间被动过，核对拿的就是一份说谎的底。git 的索引已经是那份底。
        """
        scan = (self.EXT / "skills/story-adaptation/scripts/adapt-scan.mjs").read_text(
            encoding="utf-8")
        for gone in ("before.json", "--scan", "mkdirSync(WORK"):
            self.assertNotIn(gone, scan, f"adapt 还在落工作件：{gone}")

    def test_the_entry_section_moved_into_the_skill(self) -> None:
        """入口段随 skill 走，根目录不再有它——旧路径全仓零残留。"""
        self.assertTrue((self.EXT / "skills/story/AGENTS.section.md").is_file())
        self.assertFalse((self.EXT / "AGENTS.section.md").exists())
        for path in sorted(self.EXT.rglob("*.mjs")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.split("\n"):
                if "AGENTS.section.md" in line:
                    self.assertIn("skills/story/AGENTS.section.md", line,
                                  f"{path.name} 还指着旧路径：{line.strip()}")

    def test_the_manifest_version_covers_this_round(self) -> None:
        """机制变了，manifest 版本要跟着走——它是 adapt 升级路径的唯一真源。

        **版本号写死在这里是故意的**：谁改了机制面，这一条就会红，逼他回答
        「这轮该不该升版本」。版本不升的代价不是洁癖问题——目标工程只能从版本号
        看出自己拿到的是哪一批产物形态与报错集合，号不动，升过没升过就成了一笔糊涂账。
        红了就一起改，别只把断言改绿。
        """
        manifest = (self.EXT / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "1.9.6"', manifest)
        # 包不在 manifest 里记自己的演进：`version:` 上面那一段归装它的工程（那里写的是
        # 「我们这个仓怎么用它」），每一版改了什么在 test/story/release/ 的发布说明里。
        # 按行找 `version:`：`schema_version:` 也含这个子串，直接 split 会切在第一行。
        rows = manifest.splitlines()
        at = next(i for i, l in enumerate(rows) if l.startswith("version:"))
        self.assertEqual([], [l for l in rows[:at] if l.lstrip().startswith("#")],
                         "包又往 `version:` 上面写演进记录了——那一段归装它的工程")


class TestLedgerFrozenAfterRegistration(StoryBuildCase):
    """成文登记之后台账随稿冻结——story.md 冻了，账本也得冻。

    实测一轮：登记 00:04，spec 阶段 00:20 又跑了一次 init，登记那一刻的落点账被冲掉。
    产物还在，它据以成文的依据换了一批，谁也看不出来。
    """

    FROZEN = ("decisions.json",)

    def ledger_digest(self, name: str) -> str | None:
        path = self.src / name
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def register(self) -> None:
        """把成文态登记写进流程契约——含登记那一刻的台账指纹。"""
        flow = {
            "schema": 4, "feature": FEATURE, "status": "story_written",
            "rounds": [{"round": 1, "gates": []}],
            "story_src_digests": {n: self.ledger_digest(n) for n in self.FROZEN},
        }
        (self.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_skeleton_is_refused_after_registration(self) -> None:
        self.init_audit()
        self.register()
        proc = self.run_build("skeleton")
        self.assertEqual(1, proc.returncode, "登记之后 skeleton 还能跑，台账就没冻住")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("台账随稿冻结", out)
        self.assertNotIn("撤登记", out, "登记单向，报错不该指向一个不存在的动作")
        # 登记后改章只有 reopen 一条路（1.9.3 R8）：拒绝时要说出这条路
        self.assertIn("story_flow.py reopen", out, "登记后被拒却不说怎么改")

    def test_a_changed_ledger_is_named_by_check(self) -> None:
        """拒绝两条命令挡不住有人直接改文件——指纹核对补上那一面。"""
        self.init_audit()
        self.register()
        path = self.src / "decisions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("decisions", []).append({
            "id": "sneaked-in", "status": "settled", "title": "登记之后偷加的一条",
            "category": "范围与拆分",
            "clarification": "**要定的事**：无。\n\n**根据**：无。\n\n**结论与影响**：无。",
            "decider": "需求负责人",
        })
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.assert_check_names("与成文登记时的台账对不上")
        self.assertIn("decisions.json", out)

    def test_nothing_changes_before_registration(self) -> None:
        """登记之前一切照旧——冻结只在定稿之后生效。"""
        self.init_audit()
        self.assertEqual(0, self.run_build("skeleton").returncode,
                         "没登记就拦 skeleton，那是把正常流程拦了")

class Step8Case(StoryBuildCase):
    """本组用例都要一份真的材料清单——它由 `story_flow.py round` 按磁盘现状生成。"""

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def feature_root(self) -> Path:
        return self.root / "doc" / "features" / FEATURE

    def round_now(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(FLOW), "round", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def write_decision(self, extra: list[dict] | None = None) -> None:
        rows = [settled_decision(
            "submit-boundary", "提交入口与补卡由两张开发单分别承接",
            "提交与补卡要不要放在同一张单里做。", "本单只做提交与回执展示，验收不含补卡。",
            said="补卡另起一张单")] + (extra or [])
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": rows}, ensure_ascii=False), encoding="utf-8")


class TestArRootStaysClean(StoryBuildCase):
    """`AR/` 根下只放交付文档与单据身份，辅助件一律进 `story-src/`。

    守的是一个**持续的性质**：机制不往交付层散辅助件。所以是白名单不是黑名单——
    黑名单挡不住下一个往根下写的新文件，而下一个总会有。
    """

    def ar_root(self):
        return self.story_path.parent

    def test_a_stray_file_is_named_and_told_where_to_go(self) -> None:
        (self.ar_root() / "notes.md").write_text("随手记的东西", encoding="utf-8")
        out = self.assert_check_names("AR/notes.md 不该在这一层")
        self.assertIn("story-src", out,
                      "点名了还要说挪去哪——只说错了，作者不知道下一步做什么")

    def test_directories_are_left_alone(self) -> None:
        """`story-src/`、`assets/` 这类目录都是正当落点，限制它们没有意义。"""
        for name in ("story-src", "assets"):
            (self.ar_root() / name).mkdir(exist_ok=True)
        _, out = self.check_output()
        self.assertNotIn("不该在这一层", out)

    def test_the_delivery_documents_pass(self) -> None:
        """白名单上的照过——`detail.json` 由对接层写，它是这一层的正当住户。"""
        (self.ar_root() / "detail.json").write_text('{"id": "REQ-DEMO"}', encoding="utf-8")
        _, out = self.check_output()
        self.assertNotIn("不该在这一层", out)


class TheFieldCheckIsOneImplementation(Step8Case):
    """`build` 与只读 check 用同一份字段校验：**合法才渲染**。

    各写一份的话，build 渲得出来而 check 说不合法，作者在两条路上收到两种答案；
    先渲染再由 check 报错，等于让他拿着一份半成品去猜哪一条是根因。
    """

    BAD = [{k: v for k, v in settled_decision(
        "x-1", "少了请谁评审这一项", "甲。", "丙。").items() if k != "decider"}]

    def write_decisions(self, rows) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": rows}, ensure_ascii=False), encoding="utf-8")

    def test_build_refuses_and_writes_nothing(self) -> None:
        self.write_decisions(self.BAD)
        review = self.root / "doc" / "features" / FEATURE / "AR" / "review.md"
        before = review.read_bytes() if review.is_file() else None
        proc = self.run_build("build")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("没有渲染 review", out)
        after = review.read_bytes() if review.is_file() else None
        self.assertEqual(before, after, "判不过却已经渲染了")

    def test_the_read_only_check_names_the_same_thing(self) -> None:
        self.write_decisions(self.BAD)
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("请谁评审", out, "两条路要给同一个答案")

    def test_a_legal_register_renders(self) -> None:
        rows = [dict(self.BAD[0], decider="需求负责人")]
        self.write_decisions(rows)
        proc = self.run_build("build")
        self.assertEqual(0, proc.returncode, (proc.stderr or "") + (proc.stdout or ""))
        review = self.root / "doc" / "features" / FEATURE / "AR" / "review.md"
        self.assertIn("少了请谁评审这一项", review.read_text(encoding="utf-8"))

    def test_the_old_renderer_file_is_gone(self) -> None:
        """同包删旧文件，不留转发壳——留着它，下一个人还会从那里 import。"""
        core = REPO_ROOT / "doc/extensions/skills/story/scripts/core"
        self.assertFalse((core / "review-render.mjs").exists())
        for f in sorted(core.rglob("*.mjs")):
            imports = [l for l in f.read_text(encoding="utf-8").split("\n")
                       if "review-render" in l and "from" in l]
            self.assertEqual([], imports, f"{f.name} 还在 import 已经删掉的渲染器")


class TestReviewComesAfterTheStory(Step8Case):
    """review 是判断的台账，而判断在成文过程中还会长出来。

    实测形态是「story 还没写完，review 先出来了」——那不是模型跑偏，
    是作业顺序把渲染排在了成文前面。顺序本身因此要成为一条判据。
    """

    def write_raw_decisions(self, payload) -> None:
        """按给定的顶层形状写登记表——形状本身就是这几条要问的事。"""
        (self.src / "decisions.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    ROWS = [settled_decision(
        "submit-boundary", "提交入口与补卡由两张开发单分别承接",
        "提交与补卡要不要放在同一张单里做。", "本单只做提交与回执展示。", said="补卡另起一张单")]

    def test_a_bare_array_is_refused_with_the_shape(self) -> None:
        """登记表只有一种顶层形状：顶层直接写 `[ … ]` 当场报错并给出该写的形状。"""
        self.write_raw_decisions(self.ROWS)
        proc = self.run_build("build")
        out = proc.stdout + proc.stderr
        self.assertEqual(1, proc.returncode, out)
        self.assertIn('{"decisions"', out)

    def test_a_shape_that_cannot_be_read_speaks_up(self) -> None:
        """读不出来与「一条都没有」是两回事——后者合法，前者要当场喊。

        混成一件的代价是整类失效没有声音：作者看到的是成功，产物是空的。
        """
        for name, payload in (("单数键", {"decision": self.ROWS}),
                              ("空壳", {}),
                              ("字符串", "决策还没登记")):
            with self.subTest(形状=name):
                self.write_raw_decisions(payload)
                proc = self.run_build("build")
                out = proc.stdout + proc.stderr
                self.assertEqual(1, proc.returncode, f"{name}被默默当成了零条：{out[:300]}")
                self.assertIn("读不出条目", out)
                self.assertIn('{"decisions"', out, "没说清该长什么样")

    def test_an_empty_register_is_still_legal(self) -> None:
        """零条决策是合法状态（骨架刚建完就是），不能与读不出来同判。"""
        self.write_raw_decisions({"decisions": []})
        proc = self.run_build("build")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertNotIn("读不出条目", proc.stdout + proc.stderr)

    def test_check_names_the_shape_too(self) -> None:
        """`check` 那一侧同样点名，不静默放行。"""
        self.write_raw_decisions({"decision": self.ROWS})
        proc = self.run_build("check")
        out = proc.stdout + proc.stderr
        self.assertEqual(1, proc.returncode, f"check 放行了读不出的登记表：{out[:300]}")
        self.assertIn("读不出条目", out)

    def test_build_refuses_before_the_story_is_written(self) -> None:
        self.write_decision()
        self.story_path.write_text("# 交通卡紧急挂失（REQ-DEMO）\n", encoding="utf-8")
        proc = self.run_build("build")
        self.assertEqual(1, proc.returncode, "story 还没成文，review 却渲染出来了")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("story 还没成文", out)
        self.assertFalse(self.review_path.exists(), "拒绝渲染却还是落了一份 review")

    def test_build_runs_once_the_story_has_chapters(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        self.assertIn("提交入口与补卡由两张开发单分别承接",
                      self.review_path.read_text(encoding="utf-8"))

    def test_rebuilding_is_byte_stable(self) -> None:
        """同一份登记表渲染两次，字节完全相同——机器区没有随机量。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        first = self.review_path.read_bytes()
        self.assertEqual(0, self.run_build("build").returncode)
        self.assertEqual(first, self.review_path.read_bytes())

    def test_a_decision_found_while_writing_reaches_the_review(self) -> None:
        """成文时才发现的判断，登记之后能进 review，人已经填的表态不动。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        filled = text.replace(
            "修改意见：\n\n<!-- decision: submit-boundary -->",
            "修改意见：范围要含补卡入口。\n\n<!-- decision: submit-boundary -->")
        self.assertNotEqual(text, filled, "夹具变了，用例要跟着改")
        self.review_path.write_text(filled, encoding="utf-8")

        self.write_decision(extra=[open_decision(
            "receipt-timeout", "回执超时后由谁重试", "材料没说超时之后谁重试。",
            [("由本端重试一次", "用户少等一步"), ("交给用户手动重试", "本端不做重试")],
            "按第 1 种做。", decider="需求负责人")])
        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("回执超时后由谁重试", again, "成文中新登记的判断没进 review")
        self.assertIn("修改意见：范围要含补卡入口。", again, "人填的表态被重渲染冲掉了")

    def hand_edit_the_machine_zone(self) -> None:
        text = self.review_path.read_text(encoding="utf-8")
        self.review_path.write_text(
            text.replace("提交入口与补卡由两张开发单分别承接", "手改过的标题"),
            encoding="utf-8")

    def test_the_machine_zone_is_not_a_second_source(self) -> None:
        """议题正文由登记表生成——改它不生效，所以别让人以为改了就算数。

        它**不是**「改了会被重算回来」：那样他写的东西没了而他不知道，
        下一次还会再写一遍。停下来告诉他真源在哪，才是这一段的正确出口。
        """
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        self.hand_edit_the_machine_zone()
        proc = self.run_build("build")
        self.assertEqual(1, proc.returncode, "手改被静默盖掉了")
        out = proc.stdout + proc.stderr
        self.assertIn("由决策登记表生成", out, "没说清这一段的真源是什么")
        self.assertIn("手改过的标题",
                      self.review_path.read_text(encoding="utf-8"),
                      "拒绝了却还是把文件改了")

    def test_deleting_the_zone_lets_the_projection_write_it_again(self) -> None:
        """撤销手改的出口：把这一段连同标记删掉，重跑就重新写出来。

        没有出口的拒绝等于把人锁在原地——他只能去改判据。
        """
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        self.hand_edit_the_machine_zone()
        self.assertEqual(1, self.run_build("build").returncode)

        text = self.review_path.read_text(encoding="utf-8")
        head = text.index("<!-- story-build:begin 议题 ")
        tail = text.index("评审结论：", head)
        self.review_path.write_text(text[:head] + text[tail:], encoding="utf-8")

        self.assertEqual(0, self.run_build("build").returncode, "删干净了还是不让过")
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("提交入口与补卡由两张开发单分别承接", again, "投影没有重新写出来")
        self.assertNotIn("手改过的标题", again)

    def test_a_source_change_still_reprojects(self) -> None:
        """真源变了照常重投——这条纪律拦的是手改，不是拦更新。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        rows = json.loads((self.src / "decisions.json").read_text(encoding="utf-8"))
        rows["decisions"][0]["title"] += "（复议）"
        (self.src / "decisions.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(0, self.run_build("build").returncode)
        self.assertIn("（复议）", self.review_path.read_text(encoding="utf-8"))


class TestUxReferenceNeedsNoReadme(Step8Case):
    """`ux-reference/` 有图而没有 README —— 不阻断，也不再提起。

    那一档判据当初的话是「图片在而索引不在，导入做了一半」——它建立在
    **README 承载图片登记**之上。登记收成 `materials.json` 一处真源之后，
    README 不再是登记；图片的语义（哪张是签约页）也有了确定的家（`.captions.json`），
    于是它连「可选来源」都不是了，合同里那一条随之退场。

    实跑里这条的代价是具体的：首跑 `init` 被拦下 → 补 README → 材料指纹变了 →
    契约开出新一轮 → 轮次死锁，18 分钟；二跑它降成记一笔，仍出现两次，
    作者两次都停下来处理，其中一次顺手删了附录材料清单里的那一行。
    """

    def setUp(self) -> None:
        super().setUp()
        ux = self.feature_root() / "ux-reference"
        ux.mkdir(parents=True, exist_ok=True)
        (ux / "signup.png").write_bytes(b"\x89PNG\r\n\x1a\n1")
        (ux / "manage.png").write_bytes(b"\x89PNG\r\n\x1a\n2")
        self.assertFalse((ux / "README.md").exists(), "夹具要的就是没有 README")

    def test_skeleton_passes_without_mentioning_the_readme(self) -> None:
        """UX README 现在是可选来源：没有它不拦，也不该被当成缺件提起。"""
        proc = self.run_build("skeleton")
        self.assertEqual(0, proc.returncode,
                         f"有图无 README 又把 skeleton 拦住了：{proc.stderr}")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotIn("导入做了一半", out, "那句话属于已退场的判据")

    def test_the_image_check_still_reads_the_manifest(self) -> None:
        """不拦不等于放弃判据：④ 图片身份照旧按 materials.json 认图。"""
        self.round_now()
        self.init_audit()
        self.rewrite_story("## 业务方案",
                           "![图 1 签约页](../ux-reference/signup.png)\n\n## 业务方案")
        _, out = self.check_output()
        self.assertNotIn("不在材料的图片登记里", out, "清单里有的图被判成没登记")


class TestImageIdentityComesFromTheManifest(Step8Case):
    """图片的身份是它的内容，登记只有一处：材料清单。

    早先登记是从材料正文的 `![](…)` 语法枚举的，于是「算不算数」取决于有没有人
    给它写过一条 markdown 链接——目录里四张、登记里两张，作者只能把差额标成不进 story。
    """

    def setUp(self) -> None:
        super().setUp()
        self.material_image = self.feature_root() / "assets" / "上游文档" / "image1.png"
        self.material_image.parent.mkdir(parents=True, exist_ok=True)
        self.material_image.write_bytes(b"PNGDATA1")
        self.round_now()
        self.init_audit()

    def put_image_ref(self, *refs: str) -> None:
        block = "\n\n".join(f"![图 {i + 1} 上游页面示意]({ref})" for i, ref in enumerate(refs))
        self.rewrite_story("## 业务方案", block + "\n\n## 业务方案")

    def test_a_reference_to_a_registered_image_passes(self) -> None:
        self.put_image_ref("../assets/上游文档/image1.png")
        _, out = self.check_output()
        self.assertNotIn("不在材料的图片登记里", out)
        self.assertNotIn("同一张图被两个路径引用", out)

    def test_an_unregistered_image_is_named(self) -> None:
        self.put_image_ref("../assets/别处/image9.png")
        self.assert_check_names("不在材料的图片登记里")

    def test_an_unregistered_copy_is_named_even_if_the_bytes_match(self) -> None:
        """把材料里那张图复制进 `AR/assets/` 再改个名：**字节相同也不放行**。

        从前有一条「归档副本区按字节认」的特权，而它正是「自建一个图片目录、
        全树五份同一张图」的入口——登记里没有它，谁也说不出它是哪一轮、哪一份材料来的。
        """
        copy = self.feature_root() / "AR" / "assets" / "签约页.png"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(self.material_image.read_bytes())
        self.put_image_ref("assets/签约页.png")
        self.assert_check_names("不在材料的图片登记里")

    def test_a_stranger_in_the_archive_dir_is_named(self) -> None:
        """`AR/assets/` 下没登记的文件同样不放行——它凭空多出一张没有出处的图。"""
        stray = self.feature_root() / "AR" / "assets" / "自己画的.png"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"SOMETHINGELSE")
        self.put_image_ref("assets/自己画的.png")
        self.assert_check_names("不在材料的图片登记里")

    def test_a_registered_assets_path_is_legal(self) -> None:
        """已经登记进材料的 assets 路径照样合法——退的是特权，不是这个目录。"""
        manifest = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        rel = "AR/assets/签约页.png"
        copy = self.feature_root() / "AR" / "assets" / "签约页.png"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(self.material_image.read_bytes())
        img = next(m for m in manifest["materials"] if "image" in str(m.get("kind", "")))
        img["paths"] = sorted([*img["paths"], rel])
        (self.src / "materials.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.put_image_ref("assets/签约页.png")
        code, out = self.check_output()
        self.assertNotIn("不在材料的图片登记里", out, out[:400])

    def test_without_a_manifest_the_check_says_it_did_not_run(self) -> None:
        """没有清单时不许静默放过：说清楚这条判据没执行、怎么让它能执行。"""
        (self.src / "materials.json").unlink()
        self.put_image_ref("../assets/别处/image9.png")
        _, out = self.check_output()
        self.assertIn("图片身份与落点判据未执行", out)
        self.assertIn("story_flow.py round", out)


class TestMaterialListMatchesTheManifest(Step8Case):
    """材料清单列到的，与这一轮真正在手里的那几份材料对得上。"""

    LISTED = "- 甲需求 PRD：提交回执的业务诉求与状态取值。原文：[RR/prd.md](../RR/prd.md)"

    def setUp(self) -> None:
        super().setUp()
        self.round_now()
        self.init_audit()

    def test_the_listed_material_passes(self) -> None:
        _, out = self.check_output()
        self.assertNotIn("少了一份材料", out)
        self.assertNotIn("列了不是初始资料的东西", out)

    def test_a_missing_material_is_named(self) -> None:
        """漏一份等于那份材料没人知道——读者据这一节把材料找出来。"""
        self.rewrite_story(self.LISTED, "- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                                        "原文：[别的](../AR/story-src/decisions.json)")
        out = self.assert_check_names("少了一份材料")
        self.assertIn("RR/prd.md", out)

    def test_an_intermediate_product_is_named(self) -> None:
        """本轮自己生成的记录不是材料，进了清单就把它变成倾倒区。"""
        self.rewrite_story(self.LISTED, self.LISTED
                           + "\n- 本轮的落点账：原文：[audit](../AR/story-src/audit.json)")
        self.assert_check_names("列了不是初始资料的东西")

    def test_without_a_manifest_the_check_says_it_did_not_run(self) -> None:
        (self.src / "materials.json").unlink()
        self.rewrite_story(self.LISTED, "- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                                        "原文：[别的](../AR/story-src/decisions.json)")
        _, out = self.check_output()
        self.assertIn("的集合判据未执行", out)

    def test_one_wrong_row_is_reported_once(self) -> None:
        """同一行只报一次——同一件事报两遍，读的人以为是两个问题。"""
        self.rewrite_story(self.LISTED, self.LISTED
                           + "\n- 本轮的判断：原文：[decisions](../AR/story-src/decisions.json)")
        _, out = self.check_output()
        hits = [line for line in out.splitlines() if "story-src/decisions.json" in line]
        self.assertEqual(1, len(hits), "同一行被报了不止一次：%s" % hits)
        self.assertIn("列了不是初始资料的东西", hits[0])

    def register_an_image(self) -> str:
        """盘上放一张图并重算清单，返回它相对需求目录的路径。"""
        rel = "assets/入口原型说明/image1.png"
        image = self.feature_root() / rel
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"PNGDATA1")
        self.round_now()
        return rel

    def test_an_image_does_not_belong_in_this_section(self) -> None:
        """图不进材料清单：这一节回答「据哪几份材料写成」，列的是初始资料。

        图的去向（引了没有、不引为什么）跟着图的内容走，登记在材料清单里；
        写进这一节的话，读者要在这里读到十行图，其中一半是别的需求的页面。
        """
        rel = self.register_an_image()
        self.rewrite_story(self.LISTED,
                           self.LISTED + "\n- 界面图：[image1.png](../" + rel + ")——参考")
        out = self.assert_check_names("列了不是初始资料的东西")
        self.assertIn(rel, out)

    def test_an_image_on_disk_does_not_make_this_section_incomplete(self) -> None:
        """盘上有图不等于这一节少了一份材料——图压根不在这个集合里。"""
        self.register_an_image()
        _, out = self.check_output()
        self.assertNotIn("少了一份材料", out, out[:500])

    def test_the_inbox_original_is_required(self) -> None:
        """收件箱原件是人另外给的、没走需求系统——读者要知道有这份。"""
        manifest = self.src / "materials.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["sources"] = [{"file": "补充说明.docx", "ingested": True}]
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.assert_check_names("少了一份材料")
        self.assertIn("inbox/补充说明.docx", out)


class TestNonPlaceholderChecksOnlyTwoThings(Step8Case):
    """「写没写」可以机械判，「写得够不够」不行。

    所以这里只认两件事：章有正文、模板占位符换掉了。设了下限的判据逼出来的都是凑数——
    给不涉及表格的章设「至少一张表」，作者只会造一张空表。
    """

    def setUp(self) -> None:
        super().setUp()
        self.init_audit()

    def test_a_chapter_with_only_a_title_is_named(self) -> None:
        text = self.story()
        marker = "## 背景\n"
        start = text.index(marker) + len(marker)
        end = text.index("## 术语")
        self.story_path.write_text(text[:start] + "\n" + text[end:], encoding="utf-8")
        self.assert_check_names("只有标题没有正文")

    def test_a_leftover_template_placeholder_is_named(self) -> None:
        self.rewrite_story("## 术语", "## 术语\n\n{{在这里写本需求的术语}}\n")
        out = self.assert_check_names("模板占位符")
        self.assertIn("{{在这里写本需求的术语}}", out)

    def test_one_sentence_in_a_chapter_is_enough(self) -> None:
        """最短正例：某章只有一句合法内容，不因为「太短」被拦。"""
        text = self.story()
        marker = "## 背景\n"
        start = text.index(marker) + len(marker)
        end = text.index("## 术语")
        self.story_path.write_text(
            text[:start] + "\n本需求把提交回执的等待态补齐。\n\n" + text[end:],
            encoding="utf-8")
        _, out = self.check_output()
        self.assertNotIn("只有标题没有正文", out)
        for quota in ("至少", "不少于", "过短", "太短"):
            self.assertNotIn(quota, out, "有判据在拿长度下限说话：%s" % quota)


def minimal_body(title: str, text: str) -> str:
    """这一章的**最小合法正文**：一句话 + 合同点名要定位的那几样。

    章提交现在写前先核（Q5），一句「第 N 章的正文」对有必要结构的章本来就不合法。
    这里按合同派生，不抄一份结构清单——合同改了，夹具跟着改。
    """
    contract = json.loads(
        (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
        .read_text(encoding="utf-8"))
    ch = next((c for c in contract["chapters"] if c["title"] == title), None)
    st = (ch or {}).get("structure") or {}
    rows = [text]
    if st.get("diagram"):
        rows += ["", "```mermaid", "graph TD", "A[开始] --> B[结束]", "```"]
    at_rows = {}
    for tbl in st.get("tables", []):
        cols = [a[0] for a in tbl.get("anchors") or []] or ["列"]
        head = tbl.get("header", "|".join(cols)).split("|")
        cells = ["填" for _ in head]
        block = ["", "| " + " | ".join(head) + " |",
                 "|" + "|".join("---" for _ in head) + "|",
                 "| " + " | ".join(cells) + " |"]
        at_rows.setdefault(tbl.get("at"), []).extend(block)
    for h3 in st.get("h3", []):
        rows += ["", f"### {h3['title']}", ""] + at_rows.pop(h3["title"], [])
    for extra in at_rows.values():
        rows += extra
    return "\n".join(rows) + "\n"


class AWriteThatLandedIsNeverReportedAsFailed(unittest.TestCase):
    """落盘成立之后，接续算不出来也不冒充写入失败。

    说失败他会把这一章重写一遍，而盘上已经是新的了——重写的那一份会盖掉刚落盘的，
    或者他先去「修」一个根本没坏的东西。**故障注入在副本树上做**：
    把接续那一步换成抛异常，写入那一步一个字没改。
    """

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        self.mech = self.root / "doc" / "extensions"
        shutil.copytree(REPO_ROOT / "doc" / "extensions", self.mech)
        link_harness_yaml(self.mech.parents[1])
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)
        self.story_path = self.feature_root / "AR" / "story.md"
        titles = [c["title"] for c in json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))["chapters"]]
        rows = ["# " + FEATURE + " 夹具", ""]
        for t in titles:
            rows += ["## " + t, "", "<!-- 待写：" + t + " -->", ""]
        self.story_path.write_text("\n".join(rows), encoding="utf-8")
        shutil.copy2(PLAN_FIXTURE, self.feature_root / "AR" / "story-src" / "story-template.md")
        self.build = self.mech / "skills" / "story" / "scripts" / "core" / "story-build.mjs"

    def break_next_steps(self) -> None:
        f = self.mech / "skills" / "story" / "scripts" / "core" / "story" / "chapter.mjs"
        text = f.read_text(encoding="utf-8")
        hit = ("export function nextSteps(ctx, storyText, result,"
               " { warnings = [], plan = null, docs = null } = {}) {")
        self.assertIn(hit, text, "接续函数的签名变了，故障注入点要跟着改")
        f.write_text(text.replace(
            hit, hit + "\n  throw new Error('夹具注入：接续算不出来');", 1), encoding="utf-8")

    def submit(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(self.build), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def test_the_write_stands_and_the_recovery_command_is_given(self) -> None:
        self.break_next_steps()
        proc = self.submit("背景", "本章正文。\n")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertEqual(0, proc.returncode, "写入成立却按失败退出——他会把这一章重写一遍：" + out)
        self.assertIn("本章正文。", self.story_path.read_text(encoding="utf-8"),
                      "说已落盘，盘上却没有")
        self.assertIn("已落盘", out)
        self.assertIn("不要重交", out)
        self.assertIn("skeleton", out, "没给取回定位的命令")

    def test_a_real_write_failure_still_fails(self) -> None:
        """只兜住写入之后那一段；写入本身失败仍然失败。"""
        self.story_path.unlink()
        self.story_path.mkdir()           # 落点变成目录：写入必然失败
        proc = self.submit("背景", "本章正文。\n")
        self.assertNotEqual(0, proc.returncode, "写不进去却报成功")

class ABrokenIdShapeIsObservable(unittest.TestCase):
    """合同里写错一条形态正则：从前每个消费处各 catch 掉就跳过——那一条静默不判，
    而门禁全绿。编译放一处，坏配置报给人看。

    跑的是**副本树**里的入口：机制自己按相对位置找合同，副本跑起来与正本同一条路径。
    """

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.mech = Path(self._tmp.name) / "doc" / "extensions"
        shutil.copytree(REPO_ROOT / "doc" / "extensions", self.mech)
        link_harness_yaml(self.mech.parents[1])
        self.contract = (self.mech / "skills" / "story" / "contracts"
                         / "story-chapters.json")
        self.build = (self.mech / "skills" / "story" / "scripts" / "core"
                      / "story-build.mjs")
        self.story = REPO_ROOT / "test" / "story" / "golden" / "story-金样-AR90004.md"

    def check(self) -> str:
        """金样放进用这份副本机制搭的需求工作区，经生产入口 check。"""
        with tempfile.TemporaryDirectory() as ws:
            golden_workspace.build(Path(ws), extensions=self.mech)
            return golden_workspace.check(Path(ws))[1]

    def test_a_good_contract_says_nothing_about_id_shapes(self) -> None:
        self.assertNotIn("id_shapes", self.check())

    def test_a_bad_drop_shape_is_named(self) -> None:
        data = json.loads(self.contract.read_text(encoding="utf-8"))
        data["id_shapes"]["drop"] = data["id_shapes"]["drop"] + ["S(\\d+"]
        self.contract.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.check()
        self.assertIn("id_shapes.drop", out, "坏配置静默吞掉了")

    def test_the_shapes_are_compiled_once_per_command(self) -> None:
        """坏配置在**一条命令里只报一次**：从前每章各编译一遍，十章就该报十次。

        编译挪到建上下文那一刻，`new RegExp` 也只该出现在那一处——章内判据读现成的。
        """
        data = json.loads(self.contract.read_text(encoding="utf-8"))
        data["id_shapes"]["drop"] = data["id_shapes"]["drop"] + ["S(\\d+"]
        self.contract.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.check()
        self.assertEqual(1, out.count("id_shapes.drop"), "同一条坏配置报了不止一次")
        core = self.mech / "skills" / "story" / "scripts" / "core" / "story"
        compiled = [f.name for f in sorted(core.glob("*.mjs"))
                    if "new RegExp(shape" in f.read_text(encoding="utf-8")]
        self.assertEqual(["context.mjs"], compiled,
                         f"编号形态不止一处编译：{compiled}")

    def test_a_bad_keep_shape_is_named(self) -> None:
        data = json.loads(self.contract.read_text(encoding="utf-8"))
        data["id_shapes"]["keep"] = data["id_shapes"]["keep"] + ["AC-[0-9"]
        self.contract.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertIn("id_shapes.keep", self.check(), "坏配置静默吞掉了")


class TheCandidateKeepsWhatIsNotOurs(Step8Case):
    """清洗只剥草稿生产者自己写的那几行，别的原样留着。

    从前是「像注释就删」：作者自己的备注、围栏里的注释示例、来源标记都会在落盘那一刻
    静默消失，而他不知道——下一次他只会再写一遍。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink()
        self.assertEqual(0, self.run_build("skeleton").returncode)

    def put(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def test_only_the_generators_own_guide_lines_are_stripped(self) -> None:
        body = ("<!-- story-draft:guide 读完这一章，读者要能回答：这一章要回答什么 -->\n\n"
                "本章正文。\n\n"
                "<!-- 作者自己的备注：这段等确认后再改 -->\n\n"
                "```markdown\n<!-- story-draft:guide 举例：长这样 -->\n```\n")
        proc = self.put("背景", body)
        self.assertEqual(0, proc.returncode, (proc.stderr or "") + (proc.stdout or ""))
        story = self.story_path.read_text(encoding="utf-8")
        self.assertNotIn("读者要能回答：这一章要回答什么", story, "自有指导没剥掉")
        self.assertIn("作者自己的备注", story, "作者写的注释被当成指导删掉了")
        self.assertIn("举例：长这样", story, "围栏里的样例被按指导清洗了")


class TheBytesOutsideTheChapterAreBytes(Step8Case):
    """「其余章一个字节未动」按**字节**核，不按读出来的文本核。

    读取时剥掉 BOM 对「读一份文档来判」是对的，对「按区间把原文拼回去」是错的：
    读进来少一个字节，写回去就少一个字节，而这句声明随之不成立。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink()
        self.assertEqual(0, self.run_build("skeleton").returncode)

    def put(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def rewrite_as(self, text: str) -> None:
        self.story_path.write_bytes(text.encode("utf-8"))

    def test_a_bom_and_crlf_story_keeps_every_byte_outside_the_target(self) -> None:
        plain = self.story_path.read_text(encoding="utf-8")
        self.rewrite_as("\ufeff" + plain.replace("\n", "\r\n"))
        before = self.story_path.read_bytes()
        title = "背景"
        start = before.index(("## " + title).encode("utf-8"))
        end = before.index(b"\r\n## ", start) + 2
        proc = self.put(title, "本章正文。\n")
        self.assertEqual(0, proc.returncode, (proc.stderr or "") + (proc.stdout or ""))
        after = self.story_path.read_bytes()
        self.assertEqual(before[:start], after[:start],
                         "目标章之前的字节变了（BOM 很可能没了）")
        self.assertEqual(before[end:], after[len(after) - len(before[end:]):],
                         "目标章之后的字节变了（CRLF 很可能被改写了）")
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"), "BOM 没了")

    def test_the_appendix_keeps_the_bytes_outside_it_too(self) -> None:
        """附录那一章落盘时还要投影机器区——投影只许动它自己那一段。"""
        plain = self.story_path.read_text(encoding="utf-8")
        self.rewrite_as("\ufeff" + plain.replace("\n", "\r\n"))
        before = self.story_path.read_bytes()
        cut = before.index(b"\r\n## \xe9\x99\x84\xe5\xbd\x95")      # 「## 附录」之前
        proc = self.put("附录", "本章正文。\n")
        self.assertEqual(0, proc.returncode, (proc.stderr or "") + (proc.stdout or ""))
        after = self.story_path.read_bytes()
        self.assertEqual(before[:cut], after[:cut], "附录之前的字节变了")


class TheChapterIsCheckedBeforeItLands(Step8Case):
    """写前核对：坏候选不进 story.md，作者手上只有一份要改的东西（草稿）。

    从前判据只在全篇 check 那一步跑，于是坏的那一章先落盘、再被报出来——
    作者得同时改草稿与已经写进去的正文，而两者哪个是准的没人说得清。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink()
        self.assertEqual(0, self.run_build("skeleton").returncode)

    def put(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def out(self, proc) -> str:
        return (proc.stderr or "") + (proc.stdout or "")

    def test_a_bad_chapter_changes_nothing_on_disk(self) -> None:
        before = self.story_path.read_text(encoding="utf-8")
        proc = self.put("术语", "只有一句话，没有那张表。\n")
        self.assertEqual(1, proc.returncode, self.out(proc))
        self.assertIn("术语", self.out(proc))
        self.assertEqual(before, self.story_path.read_text(encoding="utf-8"),
                         "判不过却已经写盘了——作者要改的东西变成两份")

    def test_the_same_bad_chapter_is_named_by_the_whole_check_too(self) -> None:
        """单章与全篇同一个实现：一处过一处不过，作者只能把差别当成运气。"""
        bad = "只有一句话，没有那张表。\n"
        self.assertEqual(1, self.put("术语", bad).returncode)
        text = self.story_path.read_text(encoding="utf-8")
        start = text.index("## 术语")
        end = text.index("\n## ", start) + 1
        self.story_path.write_text(text[:start] + "## 术语\n\n" + bad + "\n" + text[end:],
                                   encoding="utf-8")
        self.init_audit()
        self.assert_check_names("术语")

    def test_a_legal_chapter_lands_in_one_go(self) -> None:
        proc = self.put("术语", minimal_body("术语", "本需求用到的词。"))
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("本需求用到的词。", self.story_path.read_text(encoding="utf-8"))

    def test_a_second_anchor_with_the_same_name_is_refused(self) -> None:
        """两处同名章锚：替换只替得掉第一处，另一处仍是旧的而读者读到两遍。"""
        text = self.story_path.read_text(encoding="utf-8")
        self.story_path.write_text(text + "\n## 术语\n\n又一处。\n", encoding="utf-8")
        proc = self.put("术语", minimal_body("术语", "本需求用到的词。"))
        self.assertEqual(1, proc.returncode)
        self.assertIn("章锚", self.out(proc))

    def test_a_foreign_heading_at_the_top_is_refused(self) -> None:
        """开头是别的章的标题：从前静默留在正文里，于是多出一个章锚。"""
        proc = self.put("术语", "## 背景\n\n" + minimal_body("术语", "本需求用到的词。"))
        self.assertEqual(1, proc.returncode)
        self.assertIn("背景", self.out(proc))

    def test_an_unclosed_fence_is_refused(self) -> None:
        """围栏没关上，它之后的正文全被当成围栏里的东西——判据看不见，读者看见一坨代码。"""
        body = minimal_body("术语", "本需求用到的词。") + "\n```mermaid\ngraph TD\nA-->B\n"
        proc = self.put("术语", body)
        self.assertEqual(1, proc.returncode)
        self.assertIn("围栏", self.out(proc))

    def test_a_work_id_inside_a_diagram_is_not_flagged(self) -> None:
        """上游那张图是原样搬来的，里头的节点名不是作者写的字——让他改只能改坏图。"""
        body = "讲这一段流程。\n\n```mermaid\ngraph TD\nA[REQ-DEMO 的节点] --> B[结束]\n```\n"
        proc = self.put("业务流程", body)
        self.assertEqual(0, proc.returncode, self.out(proc))
        proc2 = self.put("业务流程", body.replace("```mermaid", "```text"))
        self.assertEqual(1, proc2.returncode, "围栏外的仓内编号仍要拦")

    def test_blank_lines_inside_a_fence_survive(self) -> None:
        """清洗只去掉自有指导，**不顺手压空行**：围栏里的原文连着几个空行就是几个。

        从前末尾挂着一句 `.replace(/\n{3,}/g, '\n\n')`，对整份候选生效——
        源图标签与原文摘录里的空行都会被它改写，而那不是清洗的职责。
        """
        body = ("<!-- story-draft:guide 提交：跑那条命令 -->\n\n正文一句。\n\n"
                "```text\nfirst\n\n\nsecond\n```\n")
        proc = self.put("背景", body)
        self.assertEqual(0, proc.returncode, (proc.stderr or "") + (proc.stdout or ""))
        story = self.story_path.read_text(encoding="utf-8")
        self.assertIn("first\n\n\nsecond", story, "围栏里的空行被压掉了")
        self.assertNotIn("提交：跑那条命令", story, "自有指导没剥掉")

    def test_a_second_chapter_heading_after_the_body_is_refused(self) -> None:
        """H2 写在正文之后：从前重新切出来的「这一章」只到它为止，写前核对看不见后半段，
        而整段仍然落了盘——story 里于是多出一个章锚。"""
        before = self.story_path.read_text(encoding="utf-8")
        proc = self.put("背景", "本章有效正文。\n## 术语\n非法新增章。\n")
        self.assertEqual(1, proc.returncode, self.out(proc))
        self.assertIn("章级标题", self.out(proc))
        self.assertEqual(before, self.story_path.read_text(encoding="utf-8"),
                         "拒绝了却已经写盘")
        self.assertEqual(1, before.count("## 术语"))

    def test_a_heading_inside_a_fence_is_fine(self) -> None:
        """围栏里的标题是被引用的样例，不是新起一章。"""
        proc = self.put("背景", "本章有效正文。\n\n```markdown\n## 举例的标题\n```\n")
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_a_work_id_in_a_diagram_passes_the_whole_check_too(self) -> None:
        """单章放行而全篇报同一条，就是新旧判据并存——作者只能把差别当成运气。"""
        body = "讲这一段流程。\n\n```mermaid\ngraph TD\nS1 --> S2\n```\n"
        self.assertEqual(0, self.put("业务流程", body).returncode)
        self.init_audit()
        code, out = self.check_output()
        self.assertNotIn("仓内工作编号", out, "全篇还在用退了场的那条全文扫描")

    def test_a_work_id_outside_a_fence_is_named_by_both(self) -> None:
        body = "这一步由 S1 触发。\n"
        proc = self.put("背景", body)
        self.assertEqual(1, proc.returncode, self.out(proc))
        self.assertIn("仓内工作编号", self.out(proc))

    def test_the_first_three_lines_say_what_to_do_next(self) -> None:
        """首屏前三行固定 NEXT / INPUT / RESULT：当前动作、动作要读的东西、刚才做了什么。"""
        proc = self.put("术语", minimal_body("术语", "本需求用到的词。"))
        self.assertEqual(0, proc.returncode, self.out(proc))
        head = (proc.stdout or "").split("\n")[:3]
        self.assertTrue(head[0].startswith("NEXT: "), head)
        self.assertTrue(head[1].startswith("INPUT: "), head)
        self.assertTrue(head[2].startswith("RESULT: "), head)
        self.assertIn("术语", head[2], "RESULT 要写刚才真做过的那件事")
        self.assertIn("drafts/", head[1], "INPUT 要给出下一章的草稿在哪")

    def test_the_skeleton_never_claims_a_chapter_was_submitted(self) -> None:
        """skeleton 的 RESULT 只写它做过的事——说成「提交过一章」，作者会以为写过了。"""
        out = self.run_build("skeleton").stdout or ""
        result = next(l for l in out.split("\n") if l.startswith("RESULT: "))
        self.assertNotIn("已落盘", result)
        self.assertIn("草稿", result)


class ChaptersLandOneAtATime(Step8Case):
    """落盘只有一条路：一次一章，其余字节不动。

    作者拿编辑工具直接改整篇时，「已完成的章一个字节没动」只是期望；经这条命令落盘，
    它是机械事实。统稿也走它——要改第五章就替换第五章，不重新输出整篇：
    整篇重出是全有或全无，中途断了磁盘上什么都没有。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink()
        self.assertEqual(0, self.run_build("skeleton").returncode)

    def titles(self) -> list[str]:
        return [c["title"] for c in json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))["chapters"]]

    def put_chapter(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def chapter_text(self, title: str) -> str:
        text = self.story()
        start = text.index(f"## {title}")
        rest = text[start + 3:]
        nxt = rest.find("\n## ")
        return rest if nxt < 0 else rest[:nxt]

    def test_the_skeleton_has_every_chapter_and_a_pending_mark(self) -> None:
        text = self.story()
        for title in self.titles():
            self.assertIn(f"## {title}", text)
            self.assertIn(f"<!-- 待写：{title} -->", text)

    def test_the_skeleton_never_overwrites_an_existing_story(self) -> None:
        """骨架命令重跑不能把写过的内容抹掉——它是起手动作，不是重置键。"""
        self.put_chapter("背景", "用户现在拿不到凭据。\n")
        before = self.story_path.read_bytes()
        self.assertEqual(0, self.run_build("skeleton").returncode)
        self.assertEqual(before, self.story_path.read_bytes())

    def test_writing_one_chapter_leaves_the_others_byte_identical(self) -> None:
        others_before = {t: self.chapter_text(t) for t in self.titles() if t != "背景"}
        self.assertEqual(0, self.put_chapter("背景", "用户现在拿不到凭据。\n").returncode)
        self.assertIn("用户现在拿不到凭据。", self.chapter_text("背景"))
        for title, before in others_before.items():
            with self.subTest(chapter=title):
                self.assertEqual(before, self.chapter_text(title))

    def test_an_interrupted_run_only_writes_what_is_still_pending(self) -> None:
        """第 4 章中断：恢复时前三章逐字节不变，只写仍带 marker 的那几章。"""
        titles = self.titles()
        for i, title in enumerate(titles[:3]):
            self.assertEqual(0, self.put_chapter(title, minimal_body(title, f"第 {i + 1} 章的正文。")).returncode)
        done = {t: self.chapter_text(t) for t in titles[:3]}
        proc = self.put_chapter(titles[3], "第 4 章的正文。\n")
        self.assertEqual(0, proc.returncode)
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("还剩 6 章待写", out, "剩几章要报出来，恢复时才知道从哪续")
        for title, before in done.items():
            with self.subTest(chapter=title):
                self.assertEqual(before, self.chapter_text(title), "已完成的章被动过了")

    def test_no_unit_ledger_is_produced_at_any_point(self) -> None:
        """全程零 audit：从 init 到写满十章再到 check，逐单元台账一个都不该出现。

        逐单元系统退场的机械证据。它们只要还被生成，就还有人会去读、去维护，
        退场就只是名义上的。
        """
        gone = ("source-units.json", "audit.json", "story-verdicts.md")
        stages = ["skeleton"]
        self.assertEqual(0, self.run_build("skeleton").returncode)
        for i, title in enumerate(self.titles()):
            self.assertEqual(0, self.put_chapter(title, minimal_body(title, f"第 {i + 1} 章的正文。")).returncode)
            stages.append(f"chapter {i + 1}")
            for name in gone:
                self.assertFalse((self.src / name).exists(),
                                 f"{stages[-1]} 之后冒出了 {name}")
        self.check_output()
        for name in gone:
            self.assertFalse((self.src / name).exists(), f"check 之后冒出了 {name}")

    def test_a_copyedit_pass_replaces_one_chapter_only(self) -> None:
        """统稿夹具：十章写完之后只改第 5 章，其余九章字节相同。"""
        titles = self.titles()
        for i, title in enumerate(titles):
            self.assertEqual(0, self.put_chapter(title, minimal_body(title, f"第 {i + 1} 章的正文。")).returncode)
        before = {t: self.chapter_text(t) for t in titles}
        self.assertEqual(0, self.put_chapter(titles[4], minimal_body(titles[4], "统稿之后的第 5 章。")).returncode)
        for title in titles:
            with self.subTest(chapter=title):
                if title == titles[4]:
                    self.assertIn("统稿之后的第 5 章。", self.chapter_text(title))
                else:
                    self.assertEqual(before[title], self.chapter_text(title))

    def test_an_unknown_chapter_is_refused(self) -> None:
        proc = self.put_chapter("并不存在的章", "随便写点。\n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("合同里没有", (proc.stderr or "") + (proc.stdout or ""))

    def test_an_empty_body_is_refused(self) -> None:
        """空正文不是一章：真的不涉及时那句话本身就是结论。"""
        proc = self.put_chapter("背景", "   \n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("空正文不是一章", (proc.stderr or "") + (proc.stdout or ""))

    def test_the_content_goes_through_a_file_not_an_argument(self) -> None:
        """正文走文件：它带换行、引号与 markdown，任何 shell 都会再解析一遍。"""
        proc = subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", "背景"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode)
        self.assertIn("--from", (proc.stderr or "") + (proc.stdout or ""))

    def test_check_names_the_chapters_still_pending(self) -> None:
        """骨架当成品交，要被点名——marker 是明确记号，判它不用读懂任何一句话。"""
        self.init_audit()
        out = self.assert_check_names("待写 marker")
        self.assertIn("背景", out)


class RealRunCase(unittest.TestCase):
    """拿真实一跑的产物走作者路径。

    手造的最小样本全是 LF、字段规整、图片路径不带中文目录名，真实产物哪一样都不是。
    """

    REAL = REPO_ROOT / "test" / "story" / "fixtures" / "real-run" / "AR90006"
    EXTENSION = REPO_ROOT / "doc" / "extensions"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature = self.root / "doc" / "features" / "AR90006"
        shutil.copytree(self.REAL, self.feature)
        ext = self.root / "doc" / "extensions"
        ext.mkdir(parents=True)
        shutil.copy2(self.EXTENSION / "manifest.yaml", ext / "manifest.yaml")
        shutil.copytree(self.EXTENSION / "knowledge", ext / "knowledge")
        self.story_path = self.feature / "AR" / "story.md"
        self.drafts = self.feature / "AR" / "story-src" / "drafts"

    def build_raw(self, *args: str) -> subprocess.CompletedProcess:
        """跑一条命令，**不断言成功**——要核「它该拒绝」的用例用这一个。

        起手前放好写作设计：这一组测的是作者照设计写章之后的路径，设计本身另有用例。
        """
        if "skeleton" in args:
            ensure_flow_state(self.root, "AR90006", self.feature / "AR" / "story-src",
                              DRAFT_TEXT)
            plan = self.feature / "AR" / "story-src" / "story-template.md"
            if not plan.exists():
                shutil.copy2(PLAN_FIXTURE, plan)
        return subprocess.run(
            ["node", str(BUILD), *args, "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def build(self, *args: str) -> subprocess.CompletedProcess:
        proc = self.build_raw(*args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def check_output(self) -> tuple[int, str]:
        proc = self.build_raw("check")
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def draft(self, name: str) -> Path:
        return self.drafts / name

    def fill(self, draft: Path) -> Path:
        """把草稿里的 `{{…}}` 填掉再提交。

        它们是种子留给作者替换的位置，提交时机制会拦住没填的——夹具照抄未填的草稿，
        测的就不是这条判据要测的东西了。
        """
        text = re.sub(r"\{\{([^}]*)\}\}", lambda m: f"{m.group(1)}（夹具）",
                      draft.read_text(encoding="utf-8"))
        draft.write_text(text, encoding="utf-8")
        return draft

    def story(self) -> str:
        return self.story_path.read_text(encoding="utf-8")


class DraftsCarryTheDeterministicWork(RealRunCase):
    """作者拿到的不是白纸：形态、槽位表、术语起始行、流程图都已经在草稿里。

    这几样都是确定性工作，脚本在他动笔前做完；他填的是语义。
    草稿是作者区——`chapter --from` 消费它，story.md 的骨架只有章锚。
    """

    def test_a_draft_per_chapter(self) -> None:
        self.build("skeleton")
        made = sorted(p.name for p in self.drafts.glob("*.md"))
        self.assertEqual(10, len(made), made)
        self.assertTrue(made[0].startswith("01-"))

    def test_the_skeleton_itself_holds_no_seed(self) -> None:
        """种子只在草稿里：留在骨架里，作者就要把它们搬进自己的章文件。"""
        self.build("skeleton")
        story = self.story()
        self.assertNotIn("```mermaid", story, "流程图不该留在骨架里")
        self.assertNotIn("| 术语 |", story, "术语起始行不该留在骨架里")
        self.assertIn("<!-- 待写：术语 -->", story)

    def test_the_terms_seed_comes_from_the_real_crlf_spec(self) -> None:
        """真实的 spec 是 CRLF——`scopeList` 的正则曾在它上面静默零命中。"""
        self.build("skeleton")
        draft = self.draft("02-术语.md").read_text(encoding="utf-8")
        rows = [l for l in draft.split("\n") if l.startswith("|") and "---" not in l]
        self.assertGreaterEqual(len(rows), 3, "术语起始行没从 spec §0 派生出来")

    def test_no_diagram_is_preplaced_in_the_flow_draft(self) -> None:
        """图不预放：上游的图逐张送到任务包，放哪一章由作者按内容定。

        预放一张「第一张图」是另一条路径——它和「逐张送达、作者归位」并存，
        同一件事就有两个说法，作者不知道该照哪个来。
        """
        self.build("skeleton")
        draft = self.draft("05-业务流程.md").read_text(encoding="utf-8")
        self.assertNotIn("```mermaid", draft, "草稿又预放了一张图")
        self.assertIn("读者要能回答", draft, "章头指引还得在：这一章要一张作者自己画的图")

    def test_optional_form_quota_branches_are_gone(self) -> None:
        """可选形式（prose/list/labels/页面状态表）不再由草稿预置或机器核——
        形式由作者按内容的关系定（08 §3）。保留的只有验收/交付两张表。
        """
        self.build("skeleton")
        solution = self.draft("04-业务方案.md").read_text(encoding="utf-8")
        self.assertNotIn("| 参与方 |", solution, "强制参与方表该退了")
        self.assertNotIn("| 否了什么 |", solution, "取舍必须成表该退了")
        exceptions = self.draft("07-异常与恢复.md").read_text(encoding="utf-8")
        self.assertNotIn("### 设计内的受限结果", exceptions, "固定两个 H3 该退了")
        self.assertNotIn("| 受限情形 |", exceptions, "固定两张表该退了")

    def test_the_appendix_draft_only_asks_for_what_is_his(self) -> None:
        """附录的机器区由投影写，草稿里不放——放了他就要在两处维护同一张表。"""
        draft = (self.build("skeleton"), self.draft("10-附录.md").read_text(encoding="utf-8"))[1]
        self.assertIn("{{用一句话说清适用对象、成立条件或业务影响}}", draft)
        self.assertIn("- 产品需求：", draft, "材料清单的类别与链接该由清单给")
        self.assertNotIn("getAutoTopupPolicy", draft, "接口表不该进草稿")

    def test_the_draft_head_carries_the_contract_questions(self) -> None:
        """章头是读者要能回答的问题与别章分工的唯一送达面——合同改了它跟着变。"""
        self.build("skeleton")
        draft = self.draft("04-业务方案.md").read_text(encoding="utf-8")
        self.assertIn("<!-- story-draft:guide 读完这一章，读者要能回答：", draft)
        contract = json.loads((REPO_ROOT / "doc/extensions/skills/story/contracts"
                               / "story-chapters.json").read_text(encoding="utf-8"))
        ch = next(c for c in contract["chapters"] if c["title"] == "业务方案")
        self.assertIn(ch["questions"][0], draft, "章头没从合同渲染读者问题")
        self.assertIn(f"别的章负责：{ch['boundary']}；这里不重复", draft, "章头没从合同渲染别章分工")

    def test_a_written_chapter_gets_its_draft_back_from_the_current_story(self) -> None:
        """返修要有落点：成文登记删掉草稿目录，之后 verifier 报了阻断问题，
        作者手上就没有可改的东西了。补回来的必须是**现稿**——补起点等于把成品换掉，
        而他下一次落盘就把成品覆盖了。
        """
        self.build("skeleton")
        draft = self.draft("02-术语.md")
        mine = "| 术语 | 在本需求里的意思 |\n|---|---|\n| 自动充值 | 余额低于阈值时自动补 |\n"
        draft.write_text(mine, encoding="utf-8")
        self.build("chapter", "--chapter", "术语", "--from", str(self.fill(draft)))

        shutil.rmtree(self.drafts)          # 成文登记做的就是这件事
        self.build("skeleton")

        back = self.draft("02-术语.md").read_text(encoding="utf-8")
        self.assertIn("自动充值", back, "补回来的是起点，不是现稿——作者改完会把成品覆盖掉")
        self.assertNotIn("<!-- 待写", back)
        # 恒等：原样再落一次盘，story 一个字节不变
        before = self.story()
        self.build("chapter", "--chapter", "术语", "--from", str(self.fill(self.draft("02-术语.md"))))
        self.assertEqual(before, self.story(), "按现稿补回的草稿再落盘却改动了 story")

    def test_a_pending_chapter_still_gets_the_seed(self) -> None:
        """还没写的章补的仍是起点：必要表头与章头指引都在里面。"""
        self.build("skeleton")
        shutil.rmtree(self.drafts)
        self.build("skeleton")
        self.assertIn("| 编号 | 验收点 | 可观察的通过条件 |",
                      self.draft("08-验收.md").read_text(encoding="utf-8"))

    def test_existing_drafts_are_never_overwritten(self) -> None:
        """中断恢复：缺哪章补哪章，写过的一个字节不动。"""
        self.build("skeleton")
        mine = self.draft("02-术语.md")
        mine.write_text("## 术语\n\n我写到一半的内容\n", encoding="utf-8")
        self.draft("03-范围.md").unlink()
        self.build("skeleton")
        self.assertEqual("## 术语\n\n我写到一半的内容\n", mine.read_text(encoding="utf-8"))
        self.assertTrue(self.draft("03-范围.md").exists(), "缺的那份没补回来")


class TheContractCarriesTheKeptSeeds(RealRunCase):
    """保留的种子照旧打底：验收、交付两张表在草稿里就搭好。"""

    def setUp(self) -> None:
        super().setUp()
        self.build("skeleton")

    def test_the_acceptance_seed_is_a_table(self) -> None:
        draft = self.draft("08-验收.md").read_text(encoding="utf-8")
        self.assertIn("| 编号 | 验收点 | 可观察的通过条件 |", draft)

    def test_the_deliverables_section_is_a_table(self) -> None:
        """只写「交什么」，评审者读不出谁在等、拿去做什么、缺了会卡谁。"""
        draft = self.draft("09-交付与上线.md").read_text(encoding="utf-8")
        self.assertIn("| 交付物 | 给谁 | 做什么用 | 什么时候要 |", draft)

    def test_the_located_section_is_seeded_where_the_table_is_checked(self) -> None:
        """机器要定位的那一节进草稿，表打在它下面——打底与核对同一个位置。

        两处不同位置的话，作者第一次知道「这张表该在哪一节」是在报错里，而报错不是
        首次交付规则的渠道。内容目标那类小节不预置标题：名字由作者按业务起。
        """
        rollout = self.draft("09-交付与上线.md").read_text(encoding="utf-8")
        self.assertIn("### 交付物", rollout)
        self.assertIn("| 交付物 | 给谁 | 做什么用 | 什么时候要 |",
                      rollout.split("### 交付物", 1)[1], "表没打在它该在的那一节下面")
        self.assertNotIn("### 回退设计", rollout, "内容目标不靠预置标题，名字由作者起")
        scope = self.draft("03-范围.md").read_text(encoding="utf-8")
        self.assertNotIn("### ", scope, "范围章没有要机器定位的小节，不预置标题")

class TheMachineZoneComesFromTheSource(RealRunCase):
    """附录的机器区每次都从当前真源重算，不读旧 story、不含占位。

    读旧的就成了「真源 + 一份会漂移的副本」；含占位则作者填了会被下一次投影打回。
    """

    def author_appendix(self) -> str:
        """作者填完草稿里属于他的那几处。"""
        draft = self.draft("10-附录.md")
        text = (draft.read_text(encoding="utf-8")
                .replace("{{用一句话说清适用对象、成立条件或业务影响}}", "服务端返回的受理状态决定后续处理路径。")
                .replace("{{这份材料贡献了什么}}", "给出了业务规则"))
        draft.write_text(text, encoding="utf-8")
        self.build("chapter", "--chapter", "附录", "--from", str(self.fill(draft)))
        return self.story()

    def test_landing_the_appendix_projects_every_zone(self) -> None:
        """技术约定下接口、数据、配置、埋点各一区，改动边界、规约判定各一区。"""
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertEqual(6, appendix.count("story-build:begin"), "机器区没投全")
        for name in ("技术约定·接口", "技术约定·数据", "技术约定·配置", "技术约定·埋点", "改动边界", "规约判定"):
            self.assertIn(f"story-build:begin {name} ", appendix)
        self.assertIn("getAutoTopupPolicy", appendix)
        self.assertIn("服务端返回的受理状态决定后续处理路径。", appendix, "作者写的那一句丢了")
        self.assertIn("给出了业务规则", appendix, "材料贡献句丢了")

    def test_the_machine_zone_holds_no_placeholder(self) -> None:
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        for zone in appendix.split("<!-- story-build:begin ")[1:]:
            body = zone.split("<!-- story-build:end -->", 1)[0]
            self.assertNotIn("{{", body, "机器区里有作者要填的占位")

    def test_the_code_status_column_stays_out(self) -> None:
        """「代码现状」是 spec 给下游 AI 的仓内路径与检索结论，不进归档件。"""
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertNotIn("代码现状", appendix)
        self.assertNotIn("检索 WalletMain data 层端云调用零命中", appendix, "代码现状列进了归档件")

    def test_reprojection_follows_the_source(self) -> None:
        """真源变了，重投影跟上；作者区一个字节不动。"""
        self.build("skeleton")
        self.author_appendix()
        use = self.feature / "spec" / "knowledge-use.yaml"
        text = use.read_text(encoding="utf-8")
        self.assertIn("无新引入位图资源", text)
        use.write_text(text.replace("无新引入位图资源",
                                    "改过的依据：无新引入位图资源", 1),
                       encoding="utf-8")
        self.build("project")
        story = self.story()
        self.assertIn("改过的依据", story, "重投影没跟上真源")
        self.assertEqual(6, story.count("story-build:begin"), "重投影后机器区数量变了")
        self.assertIn("服务端返回的受理状态决定后续处理路径。", story)
        self.assertIn("给出了业务规则", story)

    def test_the_verdict_basis_comes_from_the_source(self) -> None:
        """判定的依据取 knowledge-use.yaml 的原文，不留 `{{依据}}` 让作者再抄。"""
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertIn("方向性布局参数使用 start/end", appendix)

    def test_tables_do_not_run_together(self) -> None:
        """每张投影表前面是空行、标题或机器区起始标记——连着写会被 markdown 并成一张错表。"""
        self.build("skeleton")
        story = self.author_appendix()
        data = story.split("技术约定", 1)[1].split("改动边界", 1)[0]
        lines = [l.strip() for l in data.split("\n")]
        # 表头 = 下一行是分隔行的那一行。分隔行必须**非空**且只由 | - : 空格组成——
        # 少了「非空」这一条，空行也满足，于是表后的第一行数据被当成新表头。
        heads = [i for i, l in enumerate(lines)
                 if l.startswith("|") and i + 1 < len(lines) and lines[i + 1]
                 and set(lines[i + 1]) <= set("|-: ")]
        self.assertGreaterEqual(len(heads), 3, "spec §9.1.1–9.4 的表没都投过来")
        for i in heads:
            before = lines[i - 1]
            self.assertTrue(before == "" or before.startswith("#") or before.startswith("<!-- story-build:begin"),
                            f"表前一行是「{before}」，markdown 会把它并进前一张表")


class WhatTheAuthorLandsIsCleanAndLinkable(RealRunCase):
    """草稿原样落盘之后，story.md 里不该留下写给作者的东西，链接也要点得开。

    作者按指引「在草稿上写、写完 chapter --from 草稿」，那么草稿里的一切都会进
    story.md：形态说明里的「spec §0」被语言红线判成工程坐标，待写标记让写完的章
    仍被数成待写，材料链接差一层 `AR/` 点不开。三样都是脚本给他的，算对是脚本的事。
    """

    def landed(self, name: str, title: str) -> str:
        draft = self.draft(name)
        self.build("chapter", "--chapter", title, "--from", str(self.fill(draft)))
        return self.story()

    def test_guidance_never_reaches_the_archive(self) -> None:
        self.build("skeleton")
        story = self.landed("02-术语.md", "术语")
        body = story.split("## 术语", 1)[1].split("## 范围", 1)[0]
        self.assertNotIn("<!--", body, "写给作者的注释进了归档件")
        self.assertIn("| 术语 |", body, "术语表本身该留下")

    def test_a_landed_chapter_is_no_longer_pending(self) -> None:
        """待写标记只在骨架里：它跟着草稿进正文，写完的章会一直被数成待写。"""
        self.build("skeleton")
        story = self.landed("02-术语.md", "术语")
        self.assertNotIn("待写：术语", story)
        self.assertIn("待写：范围", story, "别的章的待写标记该还在")

    def test_material_links_point_from_the_story(self) -> None:
        """链接按 story.md 所在目录算——`RR/prd.md` 在 `AR/story.md` 里点不开。"""
        self.build("skeleton")
        draft = self.draft("10-附录.md").read_text(encoding="utf-8")
        self.assertIn("(../RR/prd.md)", draft)
        self.assertNotIn("](RR/prd.md)", draft)


class ProjectionRefusesToInventContent(RealRunCase):
    """机器区宁可停下也不写占位——作者改不了它，挂着就永远不会被填。"""

    def test_a_missing_basis_stops_the_projection(self) -> None:
        """激活清单里有、判断骨架里没有——投影不替它编一个依据出来。"""
        self.build("skeleton")
        self.build("chapter", "--chapter", "附录", "--from", str(self.fill(self.draft("10-附录.md"))))
        use = self.feature / "spec" / "knowledge-use.yaml"
        text = use.read_text(encoding="utf-8")
        start = text.index("  - id: UX-01")
        end = text.index("  - id: ", start + 10)
        use.write_text(text[:start] + text[end:], encoding="utf-8")
        proc = subprocess.run(
            ["node", str(BUILD), "project", "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode, "缺依据还照投不误")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("UX-01", out, "没指向缺依据的那一条")
        self.assertIn("knowledge-use.yaml", out)

    def test_a_zone_outside_the_contract_is_removed(self) -> None:
        """合同里没有的旧机器区要删：它指的真源已经没人维护了。"""
        self.build("skeleton")
        draft = self.draft("10-附录.md")
        draft.write_text(draft.read_text(encoding="utf-8")
                         + "\n\n### 旧节\n\n作者留在这一节的一句说明。\n\n"
                         + "<!-- story-build:begin 旧节 · 由某处生成，改它请改真源 -->\n"
                         + "| 旧 |\n|---|\n| 行 |\n<!-- story-build:end -->\n",
                         encoding="utf-8")
        self.build("chapter", "--chapter", "附录", "--from", str(self.fill(draft)))
        story = self.story()
        self.assertNotIn("story-build:begin 旧节", story, "合同外的旧机器区没被删")
        self.assertIn("story-build:begin 技术约定·接口", story)



class UpstreamDiagramsAreCarriedByIdentity(unittest.TestCase):
    """图属于哪块内容，内容落在哪，图就该在哪——机械只核「每张各有一个围栏带着」。

    身份由位置给（`§<节> #<该节内第几张>`），来源由围栏第一行自报。
    不核位置、不核张数：放哪一章由作者按内容定，判据管不了也不该管。
    """

    SPEC = ("## 5. 业务流程\n\n### 5.1 签约流程\n\n"
            "```mermaid\ngraph TD\nA[进入签约页] --> B[免密验证]\n```\n\n"
            "### 5.2 自动充值触发\n\n"
            "```mermaid\ngraph TD\nC[余额上报] --> D[判定] --> E[扣款]\n```\n")

    UPSTREAM = {"SR": "SR/design.md", "spec": "spec/spec.md"}

    def missing(self, upstream: dict[str, str], story: str) -> list[tuple[str, str, str]]:
        """经 check 用的 `carriedDiagramProblems` 取「在 story 里没有」的那几张：(来源, 身份, 主题)。"""
        with tempfile.TemporaryDirectory() as tmp:
            for label, text in upstream.items():
                f = Path(tmp) / self.UPSTREAM[label]
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text, encoding="utf-8")
            proc = subprocess.run(
                ["node", "--input-type=module", "-e",
                 "const m = await import(process.argv[1]);"
                 "const ctx = { featureRoot: process.argv[2], contract: { sources: {"
                 " SE: { path: 'SR/design.md' }, SPEC: { path: 'spec/spec.md' } } } };"
                 "process.stdout.write(JSON.stringify(m.carriedDiagramProblems(ctx, process.argv[3])));",
                 IMAGES.resolve().as_uri(), tmp, story],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        out = []
        for line in json.loads(proc.stdout):
            m = re.match(r"^(\S+) (§\S+ #\d+)（(.*?)）在 story 里没有", line)
            self.assertIsNotNone(m, line)
            out.append(m.groups())
        return out

    def carried_for(self, upstream: str, label: str, story: str):
        return [i for _, i, _ in self.missing({label: upstream}, story)]

    def carried(self, story: str):
        return [[i, topic] for _, i, topic in self.missing({"spec": self.SPEC}, story)]

    def test_identity_comes_from_the_position(self) -> None:
        """作者不用给图起名：它在哪一节、是那一节的第几张，就是它的身份。"""
        missing = dict(self.carried(""))
        self.assertEqual(["§5.1 #1", "§5.2 #1"], sorted(missing))

    def test_only_the_first_line_of_the_fence_counts(self) -> None:
        """标记只认围栏第一行——正文里提一句「图源 spec §5.2 #1」不算带过来。"""
        story = ("## 五\n\n```mermaid\n%% 图源 spec §5.1 #1\ngraph TD\nA-->B\n```\n"
                 "\n这一节的图来自 图源 spec §5.2 #1。\n")
        self.assertEqual(["§5.2 #1"], [i for i, _ in self.carried(story)])

    def test_the_report_names_the_topic_not_the_count(self) -> None:
        """缺了指向的是那件事，不是「少了一张图」——所以报的是主题。"""
        topics = dict(self.carried(""))
        self.assertIn("余额上报", topics["§5.2 #1"])
        self.assertIn("自动充值触发", topics["§5.2 #1"])

    def test_one_fence_can_carry_two_upstream_marks(self) -> None:
        """同一张图两份上游都画过时，story 里只该有一张——两行标记写在同一个围栏开头。

        一个围栏只认一个标记的话，作者要么把同一张图贴两遍，要么必然被报一条
        「在 story 里没有」。判据逼出重复内容，那是设计问题不是作者问题。
        """
        sr = "## 1. 协作\n\n```mermaid\ngraph TD\nA[入口] --> B[签约]\n```\n"
        spec_one = ("## 5. 业务流程\n\n### 5.1 签约流程\n\n"
                    "```mermaid\n%% 图源 SR §1 #1\ngraph TD\nA[入口] --> B[签约]\n```\n")
        story = ("## 五\n\n签约这条路径这样走。\n\n```mermaid\n"
                 "%% 图源 SR §1 #1\n%% 图源 spec §5.1 #1\n"
                 "graph TD\nA --> B\n```\n")
        self.assertEqual([], self.carried_for(sr, "SR", story), "SR 那份登记没认")
        self.assertEqual([], self.carried_for(spec_one, "spec", story), "spec 那份登记没认")

    def test_a_marker_inside_the_body_is_not_a_registration(self) -> None:
        """只认开头连续那几行：图正文里再出现的 `%%` 是注释，不是登记。"""
        story = ("## 五\n\n```mermaid\ngraph TD\nA --> B\n"
                 "%% 图源 spec §5.1 #1\n```\n")
        self.assertEqual(["§5.1 #1", "§5.2 #1"], sorted(i for i, _ in self.carried(story)))

    def test_an_upstream_marker_riding_along_does_not_confuse_it(self) -> None:
        """上一环的标记随围栏带过来无妨：换成指向直接上游的那一行即可。"""
        story = ("## 五\n\n```mermaid\n%% 图源 spec §5.2 #1\n%% 图源 SR §3 #1\n"
                 "graph TD\nC-->D\n```\n")
        self.assertEqual(["§5.1 #1"], [i for i, _ in self.carried(story)])


class DraftsFollowWhatIsAlreadyWritten(RealRunCase):
    """恢复时缺哪章补哪章，但**已落盘的章补的是现稿**，不是起点。

    补起点等于把成品换回白纸，作者下一次落盘就把成品覆盖了。补现稿是恒等：
    不动它什么也不变，动了改的正是他要改的那一章。
    """

    def test_a_landed_chapter_comes_back_as_the_current_story_not_the_seed(self) -> None:
        self.build("skeleton")
        draft = self.draft("02-术语.md")
        draft.write_text("| 术语 | 在本需求里的意思 |\n|---|---|\n| 甲词 | 甲词的意思 |\n",
                         encoding="utf-8")
        self.build("chapter", "--chapter", "术语", "--from", str(self.fill(draft)))
        draft.unlink()
        self.build("skeleton")
        back = draft.read_text(encoding="utf-8")
        self.assertIn("甲词", back, "补回来的是起点，成品丢了")
        self.assertNotIn("<!-- 待写", back)
        self.assertTrue(self.draft("03-范围.md").exists(), "还没写的章该有草稿")


class TheProjectedBytesBelongToTheProjection(RealRunCase):
    """投影区的字节归投影者：真源变了照常重投，有人在这里写过字就停下问他。

    静默盖掉的代价是具体的：他花时间写的几行没了，而他不会知道——
    下一次打开还会再写一遍，直到他发现「这里写什么都不算数」。
    """

    def land(self) -> str:
        self.build("skeleton")
        self.build("chapter", "--chapter", "附录", "--from", str(self.fill(self.draft("10-附录.md"))))
        return self.story()

    def project(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(BUILD), "project", "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def edit_zone(self, text: str) -> str:
        """在改动边界那一段机器区里加一行——作者会做的事。"""
        at = text.index("story-build:begin 改动边界")
        end = text.index("story-build:end", at)
        cut = text.rindex("\n", at, end)
        return text[:cut] + "\n| 我加的一行 | 改动 |" + text[cut:]

    def test_a_hand_edit_stops_the_reprojection(self) -> None:
        self.story_path.write_text(self.edit_zone(self.land()), encoding="utf-8")
        proc = self.project()
        self.assertEqual(1, proc.returncode, "手改被静默盖掉了")
        out = proc.stdout + proc.stderr
        self.assertIn("改动边界", out, "没说清是哪一节")
        self.assertIn("删掉再跑", out, "拒绝了却没给撤销的出口")
        self.assertIn("我加的一行", self.story(), "拒绝了却还是把文件改了")

    def test_deleting_the_zone_lets_it_be_written_again(self) -> None:
        """撤销手改的出口：连同首尾标记删掉这一节，重跑就重新写出来。"""
        text = self.edit_zone(self.land())
        at = text.index("<!-- story-build:begin 改动边界")
        end = text.index("story-build:end -->", at) + len("story-build:end -->")
        self.story_path.write_text(text[:at] + text[end:], encoding="utf-8")
        self.assertEqual(0, self.project().returncode, "删干净了还是不让过")
        story = self.story()
        self.assertIn("story-build:begin 改动边界", story, "投影没有重新写出来")
        self.assertNotIn("我加的一行", story)

    def test_a_source_change_reprojects_as_usual(self) -> None:
        """真源变了照常重投——这条纪律拦的是手改，不是拦更新。"""
        self.land()
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        spec.write_text(text.replace("out_of_scope_modules:",
                                     "out_of_scope_modules:\n    - NewlyExcluded", 1),
                        encoding="utf-8")
        self.assertEqual(0, self.project().returncode)
        self.assertIn("| NewlyExcluded | 不改 |", self.story(), "真源改了却没重投")

    def test_a_zone_without_a_digest_counts_as_edited(self) -> None:
        """标记里没有摘要：无从分辨「真源变了」与「有人改了」，按改过处理，停下问人。"""
        text = self.land()
        at = text.index("<!-- story-build:begin 改动边界")
        end = text.index("-->", at) + 3
        marker = text[at:end]
        stripped = marker[:marker.index(" · sha256:")] + " -->"
        self.story_path.write_text(text[:at] + stripped + text[end:], encoding="utf-8")
        self.assertEqual(1, self.project().returncode, "没有摘要的投影区被当成原样覆盖了")


class TheProjectionSpeaksTheSourceLanguage(RealRunCase):
    """投影要认真源的每一种合法写法，也要跟着它变空。

    作者按 `knowledge-use.yaml` 的规矩写「整域不适用」，投影却说他缺依据；
    spec 某一节被删空，story 里挂着上一版冒充现状——两样都是「机器区不认真源」。
    """

    def landed_appendix(self) -> str:
        self.build("skeleton")
        self.build("chapter", "--chapter", "附录", "--from", str(self.fill(self.draft("10-附录.md"))))
        return self.story()

    def use_file(self):
        return self.feature / "spec" / "knowledge-use.yaml"

    def test_a_domain_marked_not_applicable_projects_one_row(self) -> None:
        """整域不适用：一个域一行，域内条目不必逐条登记——那份 YAML 就是这么规定的。"""
        self.landed_appendix()
        use = self.use_file()
        text = use.read_text(encoding="utf-8")
        start = text.index("  - id: RES-01")
        end = text.index("  - id: ", start + 10)
        text = (text[:start] + text[end:]).replace(
            "constraint_domains: []",
            "constraint_domains:\n  - prefix: RES\n    applicable: false\n"
            "    reason: 本需求不新增任何工程资源，整域不适用。", 1)
        # RES 域里另一条也要移走，整域才谈得上「不逐条登记」
        start = text.index("  - id: RES-02")
        end = text.index("  - id: ", start + 10)
        use.write_text(text[:start] + text[end:], encoding="utf-8")

        self.build("project")
        story = self.story()
        self.assertIn("| 整域不适用 |", story, "整域那一行没投出来")
        self.assertIn("本需求不新增任何工程资源", story, "域级依据没投出来")
        self.assertNotIn("| RES-01 |", story, "整域不适用时域内条目不该再逐条出现")

    def test_a_redline_in_a_machine_zone_is_reported_to_its_source(self) -> None:
        """机器区没有作者：真源里的「PRD §」投进附录后，报错指向真源那一行，不叫作者改机器区。"""
        self.landed_appendix()
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        cell = "| `getAutoTopupPolicy` | 新增 |"
        self.assertIn(cell, text, "夹具变了，用例要跟着改")
        spec.write_text(text.replace(cell, "| `getAutoTopupPolicy` | 新增（见 PRD §3） |", 1), encoding="utf-8")
        self.build("project")
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("的机器区从", out)
        self.assertIn("「PRD §3」", out)
        self.assertIn("story-build.mjs project", out)
        self.assertNotIn("story 出现文档坐标", out, "机器区里的问题又就地报给了作者")

    def test_an_emptied_required_section_stops_the_projection(self) -> None:
        """必需小节被删空：**不是「不涉及」**，投影拒绝且 Story 不变。

        文档有字不等于技术契约已明确不涉及。按空期望放行的话，`project` 会把旧机器区
        当成「真源没内容了」删掉——删完盘上看起来合法，而少了一整节没人看得出来。
        要说不涉及就在那一节写「不涉及：<依据>」一行，那是写出来的结论（见下一条）。
        """
        story = self.landed_appendix()
        self.assertIn("story-build:begin 技术约定·接口", story)
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start = text.index("#### 9.1.1")
        end = text.index("#### 9.1.2")
        spec.write_text(text[:start] + "#### 9.1.1 端云接口\r\n\r\n" + text[end:],
                        encoding="utf-8")
        before = self.story_path.read_bytes()
        proc = self.build_raw("project")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("§9.1.1", out)
        self.assertEqual(before, self.story_path.read_bytes(), "拒绝了却已经写盘")
        code, cout = self.check_output()
        self.assertEqual(1, code, cout)
        self.assertIn("§9.1.1", cout, "只读检查要给同一个结论")

    def test_a_not_applicable_line_reaches_the_appendix(self) -> None:
        """§9.1.5 写「不涉及：…」也是结论——丢了它，story 相对 spec 就减了一条。"""
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start = text.index("#### 9.1.5")
        end = text.index("### 9.2", start)
        spec.write_text(text[:start]
                        + "#### 9.1.5 依赖变更\r\n\r\n不涉及：本需求不新增任何三方依赖。\r\n\r\n"
                        + text[end:], encoding="utf-8")
        story = self.landed_appendix()
        boundary = story.split("### 改动边界", 1)[1].split("###", 1)[0]
        self.assertIn("不涉及：本需求不新增任何三方依赖。", boundary)
        self.assertIn("| 改动 |", boundary, "Scope 的模块行也要在")

    def zone(self, story: str, name: str) -> str:
        at = story.index(f"<!-- story-build:begin {name} ")
        return story[at:story.index("<!-- story-build:end -->", at)]

    def test_the_interface_columns_use_the_readers_names(self) -> None:
        """列名按合同换成读者用的名字，只丢列、改名，不造新列；「代码现状」不投。"""
        zone = self.zone(self.landed_appendix(), "技术约定·接口")
        self.assertIn("| 接口 | 性质 | 输入 → 输出 | 错误码 |", zone)
        self.assertNotIn("云侧接口", zone)
        self.assertNotIn("代码现状", zone)

    def test_one_requirement_one_row(self) -> None:
        """一条规约两条要求（夹具的 UX-01 就是）：出两行，编号每行都写，规约域与判定只在首行。"""
        zone = self.zone(self.landed_appendix(), "规约判定")
        rows = [l for l in zone.split("\n") if "| UX-01 |" in l]
        self.assertEqual(2, len(rows), rows)
        self.assertIn("| 命中 |", rows[0])
        self.assertTrue(rows[1].startswith("|  | UX-01 |  |"), rows[1])

    def test_an_author_note_after_a_zone_is_left_alone(self) -> None:
        """H4 下机器区之后是作者说明：不参加比较，重投也不动它。"""
        story = self.landed_appendix()
        end = story.index("<!-- story-build:end -->", story.index("<!-- story-build:begin 技术约定·接口 "))
        cut = end + len("<!-- story-build:end -->")
        note = "\n\n错误码上游未给出，联调时补齐失败语义。"
        self.story_path.write_text(story[:cut] + note + story[cut:], encoding="utf-8")
        code, out = self.check_output()           # 别的章还没写，整篇不过；只看这一区有没有被报
        self.assertNotIn("技术约定·接口", out, out)
        self.build("project")
        self.assertIn("错误码上游未给出，联调时补齐失败语义。", self.story())

    def boundary_zone(self) -> str:
        """只取机器区——目的句在它外面，那一句归作者。"""
        section = self.landed_appendix().split("### 改动边界", 1)[1].split("###", 1)[0]
        return section.split("story-build:begin", 1)[1].split("story-build:end", 1)[0]

    def test_the_boundary_is_one_table_with_one_row_per_module(self) -> None:
        """一个模块一行。两份清单各挤成一格的话，评审者要在一串顿号里找自己那个模块。"""
        zone = self.boundary_zone()
        self.assertIn("| 模块 | 本单怎么动 |", zone)
        for module in ("WalletMain", "AccountManager"):
            self.assertIn(f"| {module} |", zone, f"{module} 没有自己那一行")
        seps = [l for l in zone.split("\n") if set(l.replace("|", "").strip()) <= {"-"}
                and l.strip()]
        self.assertEqual(1, len(seps), f"改动边界应当只有一张表，实际 {len(seps)} 张")

    def test_the_scope_rationale_follows_the_table(self) -> None:
        """Scope 的说明是一整段、不分模块——原样引一次，放在表后，不拆进行里。"""
        zone = self.boundary_zone()
        self.assertNotIn("| 为什么这么切 |", zone, "说明塞进了表格")
        lines = [l for l in zone.split("\n") if l.strip()]
        last_row = max(i for i, l in enumerate(lines) if l.startswith("|"))
        tail = "".join(lines[last_row + 1:])
        self.assertGreater(len(tail), 40, "说明原文没跟在表后")

    def test_the_table_has_only_columns_that_carry_something(self) -> None:
        """两列。第三列「依据」逐行重复同一句来源，读者读它读不出任何新东西。"""
        zone = self.boundary_zone()
        header = next(l for l in zone.split("\n") if l.startswith("| 模块 |"))
        self.assertEqual(2, header.count("|") - 1, f"表不是两列：{header}")

    def test_the_dependency_row_keeps_the_upstream_id_verbatim(self) -> None:
        """来自依赖变更的那一行，第一列一个字都不改：读者拿它回 spec 找原文。

        「这一行讲的是依赖」放第二列说；同一个模块在 Scope 里已有一行时不另起一行。
        """
        zone = self.boundary_zone()
        row = next(l for l in zone.split("\n") if "| 依赖变更：" in l)
        first = row.split("|")[1].strip()
        spec = (self.feature / "spec" / "spec.md").read_text(encoding="utf-8")
        self.assertIn(f"| {first} |", spec, "依赖行的第一列不是 spec 里的那个原文")
        proc = subprocess.run(
            ["node", str(BUILD), "check", "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        out = proc.stdout + proc.stderr
        self.assertNotIn("少了 spec §9.1", out, out[:600])

    def test_the_machine_zone_leaves_no_slot_for_the_author(self) -> None:
        """机器区里的占位，作者填了会被下一次投影打回，不填就一直挂着。"""
        self.assertNotIn("{{", self.boundary_zone(), "机器区还留着作者要填的格子")

    def test_every_machine_zone_passes_the_archive_redlines(self) -> None:
        """投影吐出来的每一个字都随归档走，所以它自己要过红线。

        **机器区没有作者**：它写出违规内容时，作者删掉，下一次 `project` 又写回来，
        check 再报——他赢不了，只能转去改判据或改脚本。一次实跑就这么卡了 25 分钟：
        「依据」列写着 `spec §9.1.5 依赖变更`，而 spec.md 不随归档，红线判它是文档坐标。
        """
        # 「表后散文」那一条随段数配额退场（Q7 §1：说明是否倾倒业务内容归语义审查）；
        # 这里留下的是真红线——文档坐标与仓内路径，它们不读懂内容就看得见。
        story = self.landed_appendix()
        # 每段去掉起始标记的余下半行：标记是注释，check 不扫它
        zones = [z.split("story-build:end", 1)[0].split("\n", 1)[-1]
                 for z in story.split("story-build:begin")[1:]]
        self.assertTrue(zones, "一节机器区都没有，这条守卫在空跑")
        lint = self.EXTENSION / "skills" / "story" / "scripts" / "core" / "story" / "language.mjs"
        for i, zone in enumerate(zones):
            proc = subprocess.run(
                ["node", "--input-type=module", "-e",
                 f"const m = await import({json.dumps(lint.resolve().as_uri())});"
                 f"const t = {json.dumps(zone)};"
                 f"const hits = ["
                 f"  ...m.scanLanguageRedline(t, {{kinds: [{{kind: 'doc_coordinate', scope: 'all'}}],"
                 f"    projectRoot: {json.dumps(str(self.root))}}})"
                 f"    .map(h => `${{h.line}} 行${{h.label}}：${{h.hits.join('、')}}`),"
                 f"  ...m.formatHits(m.scanLocalPaths(t, {json.dumps(str(self.root))}), 'path'),"
                 f"];"
                 "process.stdout.write(JSON.stringify(hits));"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60)
            self.assertEqual(0, proc.returncode, proc.stderr)
            hits = json.loads(proc.stdout or "[]")
            self.assertEqual([], hits, f"第 {i + 1} 节机器区自己撞了归档件红线：{hits}")


class SkeletonPreflightCase(Step8Case):
    """起手预检：**全部读完、判完，才写盘**；每一条不通过都给当前责任动作。

    夹具先把 S1–S4 走完（`ensure_flow_state`），再把上一轮留下的草稿清掉——
    这几条判的都是「这一次起手该不该开始」，盘上有没有旧草稿不该影响答案。
    """

    def setUp(self) -> None:
        super().setUp()
        ensure_flow_state(self.root, FEATURE, self.src, self.DRAFT)
        shutil.rmtree(self.src / "drafts", ignore_errors=True)

    def skeleton(self) -> tuple[int, str]:
        proc = subprocess.run(
            ["node", str(BUILD), "skeleton", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()

    def files_now(self) -> list[str]:
        return sorted(str(p.relative_to(self.root)).replace("\\", "/")
                      for p in self.root.rglob("*") if p.is_file())

    def assert_wrote_nothing(self, before: list[str]) -> None:
        self.assertEqual(before, self.files_now(),
                         "预检没通过却已经写了盘——半份起手比报错更难收拾")


class TestMaterialsMustStillBeTheOnesRegistered(SkeletonPreflightCase):
    """材料在收口之后被改：**两份落盘记录彼此照样相等**，只有按磁盘现状重算才看得见。

    上一版起手只比清单 `digest` 与轮次基准，两个都是旧值——改一份材料正文再起手，
    退出码 0、Story 照建，而它据以成文的那批料已经不是登记的那批。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink(missing_ok=True)     # 复现的是「起手要新建 Story」那一刻

    def change_a_material(self) -> None:
        prd = self.feature_root() / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n补一条：回执超时后允许重试一次。\n",
                       encoding="utf-8")

    def test_a_changed_material_blocks_the_skeleton_and_writes_nothing(self) -> None:
        self.change_a_material()
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, f"材料变了还是起了手：{out}")
        self.assertIn("材料在收口之后又变了", out)
        self.assertIn("round", out, "没给处置动作")
        self.assert_wrote_nothing(before)

    def test_registering_the_change_lets_it_start(self) -> None:
        """处置不是死路：`round` 把这次变化记到本轮之后，起手照常。"""
        self.change_a_material()
        self.round_now()
        code, out = self.skeleton()
        self.assertEqual(0, code, out)
        self.assertTrue(self.story_path.is_file(), out)

    def put_unimported_original(self, name: str = "后到的稿.md") -> None:
        """收件箱里放一份已归类、还没并入正文的原件。"""
        inbox = self.feature_root() / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / name).write_text("# " + name + "\n\n收口之后才到的材料。\n",
                                  encoding="utf-8")
        (inbox / ".classify.json").write_text(
            json.dumps({name: "AR"}, ensure_ascii=False), encoding="utf-8")

    def test_an_unimported_original_blocks_even_after_round(self) -> None:
        """`round` 登记的是基准，不是「已经并入正文」。

        上一版只认「材料变没变」：`round` 一刷新，那一项归假，而原件仍躺在收件箱里——
        起手照过、Story 照建，成文据以写的材料少一份而没有任何信号。
        """
        self.put_unimported_original()
        self.round_now()                      # 基准刷新：changed 归假，pending 仍在
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, f"未导入的原件还在，却起了手：{out}")
        self.assertIn("导入", out)
        self.assertIn("后到的稿.md", out)
        self.assert_wrote_nothing(before)

    def test_it_says_so_when_it_cannot_ask(self) -> None:
        """问不出来就说问不出来——把「问不到」当「材料齐备」等于替没人核过的输入背书。"""
        broken = self.src / "materials.json"
        broken.write_text("{ 这不是 JSON", encoding="utf-8")
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, out)
        self.assertIn("materials.json", out)
        self.assert_wrote_nothing(before)


class TheMaterialListNamesThisRoundsInputs(SkeletonPreflightCase):
    """材料清单列的是这一轮拿到的初始资料：上游正文与收件箱原件，各一行。"""

    def list_every_material(self) -> None:
        """把清单补齐到「这一轮的材料一份不少」。

        夹具的 story 手写在前，而 `round` 按磁盘现状重算材料集合——系统设计那一份
        只有在它没被某条用例删掉时才在集合里，所以不写死在夹具里，由要它的用例补。
        """
        story = self.feature_root() / "AR" / "story.md"
        text = story.read_text(encoding="utf-8")
        if "SR/design.md" in text:
            return
        at = text.index("- 甲需求 PRD")
        story.write_text(
            text[:at] + "- 系统设计：本单的上游系统设计。原文："
            + "[SR/design.md](../SR/design.md)\n" + text[at:], encoding="utf-8")

    def test_the_overwritten_ar_backup_is_not_a_required_row(self) -> None:
        """收口覆盖 `AR/design.md` 之前的备份是退路，不是本轮材料：清单不必列它。"""
        self.list_every_material()
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertNotIn(".backups", out)

    def test_the_spec_and_review_are_not_original_materials(self) -> None:
        """本轮自己生成的规格与记录不是材料——列进去就是把自证当依据。"""
        story = self.feature_root() / "AR" / "story.md"
        text = story.read_text(encoding="utf-8")
        at = text.index("### 材料清单")
        end = text.index("\n### ", at + 5) if "\n### " in text[at + 5:] else len(text)
        story.write_text(
            text[:end] + "\n- 本轮规格：这一轮写的规格。原文：[spec/spec.md](../spec/spec.md)\n"
            + text[end:], encoding="utf-8")
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertIn("不是初始资料", out)

    def test_two_paragraphs_of_source_notes_are_not_flagged(self) -> None:
        """材料清单那一节写两段说明不误拦——段数配额（`proseBlocks`）已随 Q7 退场。"""
        self.list_every_material()
        story = self.feature_root() / "AR" / "story.md"
        text = story.read_text(encoding="utf-8")
        at = text.index("### 材料清单") + len("### 材料清单")
        story.write_text(text[:at] + "\n\n这一节回答据哪几份材料写成。\n\n"
                         + "缺的那几份在上面的记一笔里说过。\n" + text[at:], encoding="utf-8")
        code, out = self.check_output()
        self.assertEqual(0, code, out)


class TestSourceNecessityIsJudgedOnce(SkeletonPreflightCase):
    """来源必不必需，起手与交付前的 check 是**同一份判定**。

    两处各判一次的代价，实测是同一份缺件被说成两件事：起手说「本地单缺它正常」，
    交付前的 check 说「它是必备来源」——作者只能挑一句信。
    """

    def test_a_missing_required_source_blocks_both(self) -> None:
        (self.feature_root() / "spec" / "spec.md").unlink()
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, out)
        self.assertIn("必备来源缺失", out)
        self.assertIn("spec/spec.md", out)
        self.assert_wrote_nothing(before)

        code2, out2 = self.check_output()
        self.assertEqual(1, code2, f"起手拦了，交付前的 check 却放过：{out2}")
        self.assertIn("spec/spec.md", out2)
        self.assertIn("必备来源", out2)

    def test_a_local_ticket_may_lack_the_remote_only_sources(self) -> None:
        """本地单没有需求系统给的 PRD / 系统设计：记一笔，不拦——两处都不拦。"""
        (self.feature_root() / "SR" / "design.md").unlink()
        self.round_now()                    # 材料集合跟着变，清单按现状重算
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertIn("本地单没有需求系统给的这一份", out)
        _, skeleton_out = self.skeleton()
        self.assertIn("本地单没有需求系统给的这一份", skeleton_out)

    def test_a_local_ticket_with_a_leftover_detail_file_stays_local(self) -> None:
        """需求目录里留着 `AR/detail.json`，本地需求仍是本地需求：来源由编号决定。"""
        (self.feature_root() / "AR" / "detail.json").write_text('{"reqNo": "x"}', encoding="utf-8")
        (self.feature_root() / "SR" / "design.md").unlink()
        self.round_now()
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertIn("本地单没有需求系统给的这一份", out)

    def test_a_system_requirement_must_have_them(self) -> None:
        """AR 开头就是系统需求，没有 `detail.json` 也一样：同一份缺件在这里是必备缺失。"""
        remote = "AR90009"
        shutil.copytree(self.feature_root(), self.feature_root().parent / remote)
        (self.feature_root().parent / remote / "SR" / "design.md").unlink()
        proc = subprocess.run(["node", str(BUILD), "check", "--feature", remote, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertEqual(1, proc.returncode, out)
        self.assertIn("SR/design.md", out)
        self.assertIn("必备来源", out)


class TestNothingIsWrittenBeforeThePreflightPasses(SkeletonPreflightCase):
    """坏掉的决策登记：当场报错，**一个字节不写**，更不覆盖已登记的判断。"""

    def test_a_broken_decision_file_writes_nothing(self) -> None:
        (self.src / "decisions.json").write_text("{ 坏了", encoding="utf-8")
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, out)
        self.assertIn("decisions.json", out)
        self.assert_wrote_nothing(before)
        self.assertEqual("{ 坏了", (self.src / "decisions.json").read_text(encoding="utf-8"))

    def test_a_spec_missing_the_sections_it_reads_blocks_and_writes_nothing(self) -> None:
        """起手要读的那几节不在，就回 Spec——不是记一笔往下走。

        「没有这一节」与「这件事不涉及」不是一回事：后者是 Spec 里写出来的结论，
        评审者读得到；前者只是没写到那儿，而一路往下走的话，作者要到十章都写完、
        附录投不出东西时才发现。
        """
        spec = self.feature_root() / "spec" / "spec.md"
        spec.write_text("# 甲需求 — 需求规格（Spec）\n\n## 1. 需求概述\n\n内容未完成。\n",
                        encoding="utf-8")
        before = self.files_now()
        code, out = self.skeleton()
        self.assertEqual(1, code, f"Spec 缺必要章节却起了手：{out}")
        self.assertIn("术语映射表", out)
        self.assertIn("不涉及", out, "没告诉作者「确实不涉及」该怎么写")
        self.assert_wrote_nothing(before)

    def test_each_projection_source_is_required_on_its_own(self) -> None:
        """附录一节从三份输入投影，三份不能互相替代。

        用「任意一节有正文」放过的话，只要 §9.1.2 在，§9.1.3 与 §9.1.4 缺了也不会有人提——
        而附录那一节正是从这三节一起投出来的。
        """
        spec = self.feature_root() / "spec" / "spec.md"
        full = spec.read_text(encoding="utf-8")
        for section in ("#### 9.1.2 数据存储", "#### 9.1.3 配置项", "#### 9.1.4 埋点"):
            with self.subTest(section=section):
                cut = full.index(section)
                end = full.index("#### 9.1", cut + len(section))
                spec.write_text(full[:cut] + full[end:], encoding="utf-8")
                before = self.files_now()
                code, out = self.skeleton()
                self.assertEqual(1, code, f"只缺 {section} 却起了手：{out}")
                self.assertIn(section.split()[1], out, "没说清缺的是哪一节")
                self.assert_wrote_nothing(before)
        spec.write_text(full, encoding="utf-8")

    def test_an_explicit_not_applicable_section_is_legal(self) -> None:
        """写出来的「不涉及：<依据>」是结论，起手照常——不逼作者补一张空表。"""
        code, out = self.skeleton()
        self.assertEqual(0, code, out)
        self.assertTrue(self.story_path.is_file(), out)


class TestTheSubmitCommandRunsAsWritten(StoryBuildCase):
    """草稿里那条提交命令**原样跑得通**——带上真实的工程根，参数按当前 shell 引用。

    只断言命令里有 `chapter` 的话，两种错法都看不见：少了 `--project-root`，
    作者在另一个仓里照抄就落到脚本自己的默认仓；引用规则写错，
    路径里的空格与 `$` 会被 shell 吃掉或展开。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # 工程根带空格与 `$`：两样都是 shell 会动手脚的字符
        self.root = Path(self._tmp.name) / "work space $x"
        shutil.copytree(FIXTURE, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        self.story_path = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"

    def submit_command(self) -> str:
        self.story_path.unlink(missing_ok=True)
        proc = self.run_build("skeleton")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        draft = next(p for p in sorted((self.src / "drafts").glob("*.md"))
                     if "术语" in p.name)
        line = next(l for l in draft.read_text(encoding="utf-8").split("\n")
                    if "提交：" in l)
        return line.split("提交：", 1)[1].rsplit("-->", 1)[0].strip()

    def test_the_rendered_command_lands_the_chapter(self) -> None:
        command = self.submit_command()
        self.assertIn("--project-root", command, "命令没带工程根")
        draft = next(p for p in (self.src / "drafts").glob("*术语*.md"))
        draft.write_text("| 术语 | 在本需求里的意思 |\n|---|---|\n| 受理单编号 | 云侧受理后给的编号 |\n",
                         encoding="utf-8")
        proc = run_in_shell(command, cwd=self.root.parent)
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        self.assertIn("受理单编号", self.story_path.read_text(encoding="utf-8"))


class TestRequiredStructureIsMinimalButReal(StoryBuildCase):
    """必要结构：**位置、最低凭据、条件**三样都按合同判，围栏里的样例不算。

    退掉固定标题与固定张数之后，还要拦得住三种形态：凭据散成一列（「编号」一列的
    验收表）、表在章内错位（交付物表挂到回退设计下面）、总览图挂在某个局部小节里。
    这三样上一版都是零问题——判据只认「章里有一张表」「章里有一张图」。
    """

    def setUp(self) -> None:
        super().setUp()
        self.init_audit()

    def set_chapter(self, title: str, body: str) -> None:
        self.rewrite_story(f"## {title}\n\n本需求不涉及。", f"## {title}\n\n{body}")

    def test_one_bare_id_column_is_not_acceptance_evidence(self) -> None:
        self.set_chapter("验收", "| 编号 |\n|---|\n| AC-1 |\n")
        out = self.assert_check_names("通过条件")
        self.assertIn("验收", out)

    def test_a_helper_table_before_the_real_one_does_not_hide_it(self) -> None:
        """验收章前面先放一张「编号／说明」对照表、后面才是完整验收表——这一章是齐的。

        只认第一张同主语的表，合法产物就被拦在「缺通过条件」上，而作者改哪一张都不对。
        """
        self.set_chapter("验收",
                         "| 编号 | 说明 |\n|---|---|\n| AC-1 | 提交成功 |\n\n"
                         "### 提交与回执\n\n"
                         "| 编号 | 场景与前置 | 可观察的通过条件 | 主责 |\n|---|---|---|---|\n"
                         "| AC-1 | 已登录 | 界面显示受理单编号 | 端侧 |\n")
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_columns_split_across_two_tables_still_fail(self) -> None:
        """凭据散在两张表里要读者自己拼，那不是凭据——不跨表拼列。"""
        self.set_chapter("验收",
                         "| 编号 | 说明 |\n|---|---|\n| AC-1 | 提交成功 |\n\n"
                         "| 场景 | 可观察的通过条件 |\n|---|---|\n| 提交成功 | 显示受理单编号 |\n")
        self.assert_check_names("通过条件")

    def test_renamed_columns_in_one_table_pass(self) -> None:
        """列名按本需求换说法、加列都合法——判的是这几件事在不在同一张表里。"""
        self.set_chapter("验收",
                         "| 原始编号 | 场景与前置 | 怎么算通过 | 主责 |\n|---|---|---|---|\n"
                         "| AC-1 | 提交成功 | 界面显示受理单编号 | 端侧 |\n")
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_the_delivery_table_must_sit_in_its_own_section(self) -> None:
        """交付物那张表挂在回退设计下面：读者在「交付物」一节里什么也没看到。"""
        self.set_chapter("交付与上线",
                         "### 回退设计\n\n关掉提交入口，已受理的申请照常走完。\n\n"
                         "| 交付物 | 给谁 | 做什么用 | 什么时候要 |\n|---|---|---|---|\n"
                         "| 提交说明 | 评审人 | 过目 | 提交前 |\n\n"
                         "### 交付物\n\n随版本发布。\n")
        out = self.assert_check_names("交付物")
        self.assertIn("缺一张表", out)

    def test_a_fenced_example_does_not_substitute_for_the_real_section(self) -> None:
        """围栏里的标题与表是被引用的样例：贴一段示例不该满足本章的必要结构。"""
        self.set_chapter("交付与上线",
                         "```markdown\n### 交付物\n\n"
                         "| 交付物 | 给谁 | 做什么用 | 什么时候要 |\n|---|---|---|---|\n```\n")
        self.assert_check_names("缺「交付物」这一节")

    def test_a_chapter_without_any_diagram_fails(self) -> None:
        """这一章要一张图：一张都没有才是缺。"""
        self.set_chapter("业务流程",
                         "提交之后等回执。\n\n### 回执到达前的等待\n\n界面停在等待态。\n")
        self.assert_check_names("没有图")

    def test_an_overview_inside_its_own_section_is_legal(self) -> None:
        """总览放在一个总览小节里也行——按位置推断它是不是总览，会拦住合法产物。

        它讲没讲清整条业务、局部图接不接得回总览，归语义审查；机器只认这一章真有图。
        """
        self.set_chapter("业务流程",
                         "### 总览\n\n整条业务这样走：\n\n"
                         "```mermaid\nflowchart TD\n  提交 --> 等待 --> 已回执\n  等待 --> 超时未提交\n```\n\n"
                         "### 回执到达前的等待\n\n界面停在等待态。\n")
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_a_diagram_before_the_first_subsection_passes(self) -> None:
        self.set_chapter("业务流程",
                         "整条业务这样走：\n\n"
                         "```mermaid\nflowchart TD\n  提交 --> 等待 --> 已回执\n  等待 --> 超时未提交\n```\n\n"
                         "### 回执到达前的等待\n\n界面停在等待态。\n")
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_a_plain_code_fence_is_not_a_diagram(self) -> None:
        """普通示例代码不算图：算它的话，贴一段数据就能顶掉这一章该画的那张。"""
        self.set_chapter("业务流程",
                         '提交之后等回执。\n\n```json\n{"state": "waiting"}\n```\n')
        self.assert_check_names("没有图")

    def test_sections_named_by_business_are_not_reported_missing(self) -> None:
        """分工、交接、回退这些是**内容目标**：按标题名判会把用业务名起的标题说成缺了。

        金样里讲清了三方分工与权威来源的那一节，却因为标题不叫「参与方与分工」被报缺失。
        讲清没讲清读的是内容，由读者问题、章级维度与独立语义审查判；机器只定位它真要
        定位的那几处（给表定范围的小节与附录五节）。
        """
        self.set_chapter("范围",
                         "### 本单与补卡单怎么分\n\n本单只做提交与回执展示；"
                         "补卡由兄弟单承接，受理单编号由本单生成、它只读。\n")
        self.set_chapter("业务方案",
                         "### 三方各自做什么\n\n"
                         "| 参与方 | 输入 | 输出 | 责任 | 失败影响 |\n|---|---|---|---|---|\n"
                         "| 钱包端 | 用户提交 | 受理请求 | 入口与展示 | 用户看不到回执 |\n")
        code, out = self.check_output()
        self.assertEqual(0, code, f"按标题名判把业务名起的标题说成缺了：{out}")


if __name__ == "__main__":
    unittest.main()


class TheTitleCarriesTheName(StoryBuildCase):
    """AC24：归档件大标题是「编号 需求名」——只有编号，读者在需求系统外认不出是哪件事。"""

    def test_a_title_with_only_the_id_is_named(self) -> None:
        self.init_audit()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, f"# {FEATURE}")
        self.assertIn("大标题缺需求名", self.assert_check_names("大标题缺需求名"))


class SourceMarksPointAtRealUpstreamFigures(StoryBuildCase):
    """AC24：来源标记只核引用——指到上游真有的图、不指向 story 自己；写在围栏外只报一处。"""

    def add_before_terms(self, block: str) -> None:
        self.rewrite_story("本需求不涉及。\n\n## 术语", "本需求不涉及。\n\n" + block + "\n\n## 术语")

    def test_a_mark_to_a_missing_figure_is_named(self) -> None:
        self.init_audit()
        self.add_before_terms("```mermaid\n%% 图源 SR §99 #1\ngraph TD\nA-->B\n```")
        self.assertIn("「SR §99 #1」", self.assert_check_names("来源标记"))

    def test_a_mark_to_the_story_itself_is_named(self) -> None:
        self.init_audit()
        self.add_before_terms("```mermaid\n%% 图源 story §1 #1\ngraph TD\nA-->B\n```")
        self.assertIn("指向的不是上游文档", self.assert_check_names("来源标记"))

    def test_a_mark_outside_the_fence_is_one_report(self) -> None:
        self.init_audit()
        self.add_before_terms("%% 图源 SR §99 #1")
        out = self.assert_check_names("写在了围栏外")
        self.assertNotIn("文档坐标", out, "同一行又按文档坐标报了一遍")


class TheProjectionRefreshesAfterRegistration(Step8Case):
    """AC22：登记之后 spec 改了，`project` 直接重投附录机器区，不必 reopen。"""

    def test_project_runs_on_a_registered_story(self) -> None:
        ensure_flow_state(self.root, FEATURE, self.src, self.DRAFT)
        flow = self.src / "story-flow.json"
        data = json.loads(flow.read_text(encoding="utf-8"))
        data["status"] = "story_written"
        flow.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        proc = self.run_build("project")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("重投", proc.stdout)
