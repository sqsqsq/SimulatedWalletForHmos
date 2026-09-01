"""机制收束的四条边界：所有权、索引、推进契约、评审落点。

这一组判的是**文本与结构**，不是运行行为——它们守的东西正是靠 grep 才守得住：
一句话搬了位置、一条规则又长回第二处、一个引用改成了复述，运行时全都照常，
下一轮才发现真源又变成两份。行为侧的判据在 `test_story_build.py`。
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
EXT = REPO_ROOT / "doc" / "extensions"
PATTERNS = EXT / "knowledge" / "design-patterns"
ADAPT = EXT / "skills" / "story-adaptation"
STORY = EXT / "skills" / "story"

EXT_BEGIN = "<!-- story-ext:begin -->"
EXT_END = "<!-- story-ext:end -->"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class KnowledgeOwnership(unittest.TestCase):
    """知识全域归目标工程：包内那份只是样板与提案，不是可以直接盖上去的正本。

    上一版按路径把「规约与模式」判成随包维护的机制内容，同名即换包版本——
    校验里还配了一条对应的排除分支，于是覆盖发生时谁都没在核它。
    只有模型读得懂哪些内容是这个工程的业务定义，路径读不懂。
    """

    def test_the_replace_with_package_version_behaviour_is_gone(self) -> None:
        skill = read(ADAPT / "SKILL.md")
        self.assertNotIn("换成包的版本", skill, "「同名换包版本」还留在处置表里")
        self.assertIn("变更提案", skill)
        self.assertIn("知识全域归目标工程", skill)

    def test_the_checker_no_longer_excludes_package_owned_knowledge(self) -> None:
        """排除分支在校验里也得消失——留着它，覆盖照样无声无息。"""
        scan = read(ADAPT / "scripts" / "adapt-scan.mjs")
        self.assertNotIn("pkgNames", scan, "按包内同名排除守恒的分支还在")
        self.assertIn("目标已有的每一个知识文件", scan)

    def test_the_plan_asks_for_a_diff_to_merge(self) -> None:
        """提案形态要写进方案页：列差异供人确认，而不是列「将被覆盖」。"""
        skill = read(ADAPT / "SKILL.md")
        self.assertIn("包内同名知识文件的变更提案", skill)
        self.assertIn("没确认的一律保持目标原样", skill)

    def test_the_framework_version_stance_is_stated(self) -> None:
        """内网那条猜测（是不是强依赖 framework 新版）在这里有确定答复。"""
        skill = read(ADAPT / "SKILL.md")
        self.assertIn("扩展对 framework 没有版本强依赖", skill)

    def test_the_adapt_residue_is_gone(self) -> None:
        """落点机制早已是 `.adapt-<version>/`；仓里那份是旧版残留。"""
        self.assertFalse((EXT / "adapt").exists(), "doc/extensions/adapt/ 还在")
        self.assertIn(".adapt-${PKG_VERSION}", read(ADAPT / "scripts" / "adapt-scan.mjs"))

    def test_runtime_junk_never_reaches_a_target(self) -> None:
        """`__pycache__` 落在 skills/ 下会被判成机制内容，跟着复制进目标工程。"""
        scan = read(ADAPT / "scripts" / "adapt-scan.mjs")
        self.assertIn("__pycache__", scan)
        self.assertIn("__pycache__/", read(REPO_ROOT / ".gitignore"))


class EntryFileMarkers(unittest.TestCase):
    """「实例扩展」节不止 adapt 一个写者，标记区划清写者边界。

    framework 的 render-agents-md 也往这一节生成 Skill 表格。上一版整节替换，
    把宿主刚生成的表格连同别的内容一起盖掉了。
    """

    def test_the_section_carries_the_markers(self) -> None:
        body = read(STORY / "AGENTS.section.md")
        self.assertTrue(body.lstrip().startswith(EXT_BEGIN))
        self.assertTrue(body.rstrip().endswith(EXT_END))

    def test_both_entry_files_wrap_the_segment(self) -> None:
        """本仓自己就是一个已适配的目标，两份入口文件都要带标记。"""
        for name in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(entry=name):
                text = read(REPO_ROOT / name)
                self.assertIn(EXT_BEGIN, text)
                self.assertIn(EXT_END, text)

    def test_the_write_rule_covers_the_first_migration(self) -> None:
        """认得出旧段就原位包标记——认不出才追加，否则新旧两段并存。"""
        skill = read(ADAPT / "SKILL.md")
        self.assertIn("只重写标记之间", skill)
        self.assertIn("原位包上标记", skill)
        self.assertIn("末尾追加", skill)

    def test_the_checker_tells_the_two_cases_apart(self) -> None:
        """「内容在、标记没包上」与「整段没写进去」修法不同，报错也要不同。"""
        scan = read(ADAPT / "scripts" / "adapt-scan.mjs")
        self.assertIn("入口文件的扩展段没有标记区", scan)
        self.assertIn("入口文件未含扩展段", scan)


class AdaptEntryMarkerFixture(unittest.TestCase):
    """标记协议的正反夹具：跑真的 adapt-scan，退出码即结论。"""

    SECTION = "本工程挂载了 story 实例扩展。\n\n- 动笔之前先读各阶段须知。"

    def build_target(self, entry_body: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for side in ("package", "target"):
            base = root / side / "doc" / "extensions" / "skills" / "story"
            base.mkdir(parents=True)
            (root / side / "framework.config.json").write_text(
                json.dumps({"paths": {"extension_dir": "doc/extensions"}}), encoding="utf-8")
            (root / side / "doc" / "extensions" / "manifest.yaml").write_text(
                'version: "1.0.0"\n', encoding="utf-8")
        (root / "package" / "doc" / "extensions" / "skills" / "story"
         / "AGENTS.section.md").write_text(
            EXT_BEGIN + "\n" + self.SECTION + "\n" + EXT_END + "\n", encoding="utf-8")
        (root / "target" / "AGENTS.md").write_text(
            "# 目标\n\n### 实例扩展 Skill\n\n" + entry_body + "\n", encoding="utf-8")
        return root

    def run_check(self, root: Path) -> tuple[int, str]:
        scan = ADAPT / "scripts" / "adapt-scan.mjs"
        for mode in ("--scan", "--check"):
            proc = subprocess.run(
                ["node", str(scan), mode, "--target", str(root / "target"),
                 "--package", str(root / "package")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60)
            if mode == "--check":
                return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        raise AssertionError("unreachable")

    def test_an_unmarked_old_segment_is_told_to_wrap_in_place(self) -> None:
        code, out = self.run_check(self.build_target(self.SECTION))
        self.assertNotEqual(code, 0)
        self.assertIn("没有标记区", out)
        self.assertIn("原位", out)

    def test_a_missing_segment_is_told_to_append(self) -> None:
        code, out = self.run_check(self.build_target("（这一节还没有扩展须知）"))
        self.assertNotEqual(code, 0)
        self.assertIn("未含扩展段", out)

    def test_a_properly_marked_segment_passes_that_item(self) -> None:
        root = self.build_target(EXT_BEGIN + "\n" + self.SECTION + "\n" + EXT_END)
        _, out = self.run_check(root)
        self.assertNotIn("⑤", out, "标记齐备时不该再报入口段：" + out)


class PatternIndexIsPureIndex(unittest.TestCase):
    """模式 README 只做索引：判定信号的真源是模式文件上篇。

    同一句判定信号原先存在于三处——README 路由表、模式文件 frontmatter、
    模式文件上篇。三处并行维护，漂移只是时间问题。
    """

    def readme(self) -> str:
        return read(PATTERNS / "README.md")

    def test_the_per_pattern_signal_rows_are_gone(self) -> None:
        text = self.readme()
        for gone in ("## 路由", "以上信号都不成立",
                     "每个分支自身是多步的、有自己的失败处理，不是判断完就返回"):
            self.assertNotIn(gone, text, "「" + gone + "」还在 README 里")

    def test_the_four_chapters_are_there(self) -> None:
        headings = [l.strip() for l in self.readme().split("\n") if l.startswith("## ")]
        self.assertEqual(headings,
                         ["## 适用单元", "## 模式清单", "## 候选登记规则", "## 多模式组合"])

    def test_the_general_rules_survived_the_move(self) -> None:
        """移位不删义：F5/F7 立的那几条通用规则要在新位置找得到。"""
        text = self.readme()
        for kept in ("零命中同样要举证", "不要复述判定语言",
                     "信号来自**业务流程本身**",
                     "**spec 阶段候选判定**与 **plan 阶段选型**的共同输入"):
            self.assertIn(kept, text, "「" + kept + "」在移位中丢了")

    def test_the_readme_points_at_the_pattern_files(self) -> None:
        self.assertIn("读对应模式文件的上篇", self.readme())
        self.assertIn("唯一真源是各模式文件的「上篇 · 适用与选型」", self.readme())

    def test_the_frontmatter_is_declared_a_projection(self) -> None:
        """frontmatter 仍被框架消费，所以它留着——但要说清它是投影不是真源。"""
        self.assertIn("一句话机器投影", self.readme())
        self.assertIn("改上篇时同步改这个投影", self.readme())

    def test_every_listed_pattern_has_its_own_upper_half(self) -> None:
        """真源迁到上篇，上篇就必须自带完整信号——否则判定无处可读。"""
        listed = re.findall(r"\|\s*`([a-z-]+)`\s*\|\s*\[", self.readme())
        self.assertTrue(listed, "模式清单没解析出任何 pattern_id")
        for pattern_id in listed:
            with self.subTest(pattern=pattern_id):
                body = read(PATTERNS / (pattern_id + ".md"))
                self.assertIn("上篇 · 适用与选型", body)
                self.assertIn("## 1. 解决什么问题", body)
                self.assertIn("## 2. 什么时候不该用", body)
                self.assertIn("applies_when:", body)
                self.assertIn("not_applies_when:", body)

    def test_the_spec_template_points_at_the_upper_half_too(self) -> None:
        template = read(STORY / "templates" / "spec-sections.md")
        self.assertIn("命中信号与反例读各模式文件的「上篇 · 适用与选型」", template)
        self.assertNotIn("不要复述模式索引里的判定措辞", template)


class AdvanceContract(unittest.TestCase):
    """推进契约一处定义，各阶段只引用。

    授权分两层：extension 流程段内由本节授权；framework 阶段之间不造第二套授权，
    走 framework 自己认的途径。混为一谈就会写出一份与 framework 打架的文本，
    而模型只会更保守地停下来问。
    """

    def skill(self) -> str:
        return read(STORY / "SKILL.md")

    def test_the_section_exists_with_all_three_parts(self) -> None:
        text = self.skill()
        self.assertIn("## 推进契约", text)
        for part in ("### 授权分两层", "### 停等点白名单", "### 裁决衔接链"):
            self.assertIn(part, text)

    def test_the_two_layers_are_kept_apart(self) -> None:
        text = self.skill()
        self.assertIn("story 流程段内", text)
        self.assertIn("framework 阶段之间", text)
        self.assertIn("不另造一套授权", text)

    def test_the_whitelist_is_closed(self) -> None:
        """白名单之外一律不问——那句话本身就是判据。"""
        text = self.skill()
        self.assertIn("此外一律不问", text)
        for item in ("材料缺口", "范围变更", "连续 3 次", "破坏性动作"):
            self.assertIn(item, text)

    def test_the_three_reported_questions_are_named_as_non_questions(self) -> None:
        """内网停下来问的那三处，要在契约里被点名成「不是选择题」。"""
        text = self.skill()
        for asked in ("要不要修", "下一步做什么", "进 harness 还是进 verifier"):
            self.assertIn(asked, text)

    def test_each_author_page_only_references_it(self) -> None:
        """各 author.md 只有引用句，没有第二份正文——同一要求只在一处。"""
        pages = sorted((EXT / "hooks").glob("*/author.md"))
        self.assertTrue(pages)
        for page in pages:
            with self.subTest(page=page.parent.name):
                text = read(page)
                self.assertIn("推进契约", text, "缺引用句")
                self.assertIn("skills/story/SKILL.md#推进契约", text, "引用没指向定义处")
                # 引用可以提白名单的名字，但不能把它的内容再列一遍
                for duplicated in ("材料缺口", "连续 3 次", "破坏性动作", "授权范围"):
                    self.assertNotIn(duplicated, text,
                                     "把契约正文抄进了 author.md：" + duplicated)

    def test_the_gate_error_sentence_lives_in_one_place(self) -> None:
        """「缺什么/写到哪/怎么写」这句话原先在八处，现在只留定义处与契约处。"""
        needle = "缺什么 / 写到哪 / 怎么写"
        hits = [p for p in sorted(EXT.rglob("*"))
                if p.is_file() and p.suffix in (".md", ".mjs", ".py")
                and needle in read(p)]
        names = sorted(p.name for p in hits)
        self.assertEqual(names, ["AGENTS.section.md", "SKILL.md"],
                         "这句话又长回多处：" + str(names))


class ReviewLanding(unittest.TestCase):
    """评审结论落哪、正本归谁——两件都写进作业书，机制不动。"""

    def reflow(self) -> str:
        return read(STORY / "rules" / "review_reflow.md")

    def test_decisions_json_is_declared_read_only(self) -> None:
        text = self.reflow()
        self.assertIn("登记冻结", text)
        self.assertIn("只记进", text)
        self.assertIn("不回写冻结件", text)

    def test_the_write_back_shape_is_defined(self) -> None:
        text = self.reflow()
        self.assertIn("「审核结果：」行", text)
        self.assertIn("其他意见", text)
        self.assertIn("不要拿它整份覆盖", text)

    def test_no_second_input_file_is_introduced(self) -> None:
        """SKILL 说「模型的输入唯一就是 review.md」——回传落点不能和它打架。"""
        self.assertIn("模型的输入唯一就是 `AR/review.md`", read(STORY / "SKILL.md"))
        self.assertNotIn("review-annotated", self.reflow())

    def test_ownership_is_narrowed_to_the_human_zone(self) -> None:
        """归人所有的是人工区，结构归渲染器——整份覆盖正是这两者没分开的后果。"""
        text = self.reflow()
        self.assertIn("人工区", text)
        self.assertIn("结构归渲染器", text)


class NoRoundReferences(unittest.TestCase):
    """轮次与批次指涉退场——内网读者没有本仓的维护史。

    「上一版」「上一轮」是相对说法，任何读者都读得懂，保留；
    「批次 3」「F5」这类只有本仓维护史读者才对得上，改写成事实描述。
    """

    ROUND = re.compile(r"批次\s*\d|(?<![A-Za-z])F\d+\s*(?:实测|那轮|轮|阶段)")

    def test_no_round_or_batch_reference_survives(self) -> None:
        offenders = []
        for path in sorted(EXT.rglob("*")):
            if not path.is_file() or path.suffix not in (".md", ".mjs", ".py", ".json"):
                continue
            for number, line in enumerate(read(path).split("\n"), 1):
                if self.ROUND.search(line):
                    offenders.append(path.relative_to(REPO_ROOT).as_posix()
                                     + ":" + str(number) + " " + line.strip()[:60])
        self.assertEqual(offenders, [], "轮次/批次指涉还在：" + "；".join(offenders))

    def test_the_reason_text_is_kept(self) -> None:
        """删的是编号，不是「为什么」——这些句子必须还在。"""
        units = read(STORY / "scripts" / "source-units.mjs")
        self.assertIn("既无作业指引也无门禁", units)
        self.assertIn("整片丢了", units)


if __name__ == "__main__":
    unittest.main()
