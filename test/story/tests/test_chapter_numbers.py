"""主章号以目标 profile 的模板为准 —— 模板里不编号的章不计入序号，子节号跟父章走。

C 复测里 auto 的 Spec 把模板里不编号的 Scope 编成第 2 章，后面整体顺延，技术契约成了第 10 章
下面却挂着 9.x；car 的 Plan 按另一套编号引用设计章。门禁只按标题名找章，这两样都放过了。

这里锁住：
  ① 模板经 profile 的 skill 资产清单取得，换一个 profile 名照样取得到，不写死路径；
  ② 模板不编号的章被编了号、主章号与模板不符、带号子节不以父章号开头，各自报出；
  ③ 正文里合法的自定义小节（不带号，或模板没有的章）不报；
  ④ 表里「号 + 章名」的引用与本文实际章对不上时报出，对得上、只写章名的不报。
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODULE = REPO / "doc" / "extensions" / "hooks" / "shared" / "chapters.mjs"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [modulePath, fn, ...args] = process.argv.slice(2);
const mod = await import(pathToFileURL(modulePath).href);
process.stdout.write(JSON.stringify(mod[fn](...JSON.parse(args[0]))));
"""

TEMPLATE = """# 模板

## 0. 名词

## 1. 概述

## 范围声明

### 范围清单

## 2. 场景

## 3. 契约

### 3.1 接口
"""


def call(fn: str, *args):
    with tempfile.TemporaryDirectory() as d:
        driver = Path(d) / "drive.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        r = subprocess.run(["node", str(driver), str(MODULE), fn, json.dumps(args, ensure_ascii=False)],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-600:]
    return json.loads(r.stdout)


class MainChaptersFollowTheTemplate(unittest.TestCase):
    def test_a_document_numbered_like_the_template_passes(self) -> None:
        doc = TEMPLATE + "\n### 3.2 存储\n\n#### 3.2.1 本地表\n\n### 自定义小节\n\n## 附加说明\n"
        self.assertEqual([], call("chapterNumberProblems", doc, [TEMPLATE]))

    def test_numbering_an_unnumbered_chapter_shifts_everything_and_is_named(self) -> None:
        doc = TEMPLATE.replace("## 范围声明", "## 2. 范围声明").replace("## 2. 场景", "## 3. 场景") \
            .replace("## 3. 契约", "## 4. 契约")
        got = call("chapterNumberProblems", doc, [TEMPLATE])
        self.assertIn("「## 2. 范围声明」：模板里这一章不编号", got[0])
        self.assertTrue(any("「## 4. 契约」：模板里这一章是第 3 章" in p for p in got), got)
        self.assertTrue(any("「### 3.1 接口」挂在第 4 章" in p for p in got), got)

    def test_a_child_under_the_wrong_parent_is_named_at_every_level(self) -> None:
        doc = TEMPLATE + "\n### 3.2 存储\n\n#### 3.3.1 本地表\n"
        got = call("chapterNumberProblems", doc, [TEMPLATE])
        self.assertEqual(1, len(got), got)
        self.assertIn("「#### 3.3.1 本地表」挂在第 3.2 章（节）下", got[0])

    def test_an_extension_template_adds_its_own_chapters(self) -> None:
        ext = "## 4. 追加章\n"
        doc = TEMPLATE + "\n## 5. 追加章\n"
        self.assertEqual([], call("chapterNumberProblems", doc, [TEMPLATE]))
        self.assertIn("模板里这一章是第 4 章", call("chapterNumberProblems", doc, [TEMPLATE, ext])[0])


class ChapterReferencesPointAtRealChapters(unittest.TestCase):
    PLAN = ("## 范围声明\n\n| 条目 | 承载设计章 |\n|---|---|\n| 甲 | 1. 架构（入口） |\n| 乙 | 2. 架构 |\n"
            "| 丙 | [架构](#1-架构) |\n| 丁 | 数据 |\n\n## 1. 架构\n\n## 2. 数据\n")

    def test_only_the_wrong_numbered_reference_is_named(self) -> None:
        got = call("chapterRefProblems", self.PLAN, "承载设计章")
        self.assertEqual(["「承载设计章」写的「2. 架构」对不上本文的章：「架构」在本文是第 1 章"], got)


class TheTemplateComesFromTheProfile(unittest.TestCase):
    """profile 名来自 framework.config.json，模板路径来自该 profile 的资产清单。

    没配 profile 是「不适用」；配了却读不到清单、键或文件、清单解析失败是输入坏了——
    后者不能被当成不用核而静默跳过，章号检查会整个消失。
    """

    def workspace(self, d: str, manifest: str | None = "assets:\n  spec:\n    spec_template: tpl/s.md\n",
                  template: bool = True, profile: str | None = "neutral-web") -> Path:
        root = Path(d)
        (root / "framework.config.json").write_text(
            json.dumps({"project_profile": {"name": profile}} if profile else {}), encoding="utf-8")
        skills = root / "framework" / "profiles" / "neutral-web" / "skills"
        (skills / "spec" / "tpl").mkdir(parents=True)
        if template:
            (skills / "spec" / "tpl" / "s.md").write_text(TEMPLATE, encoding="utf-8")
        if manifest is not None:
            (skills / "skill-assets.yaml").write_text(manifest, encoding="utf-8")
        return root

    def test_another_profile_name_resolves_through_its_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            got = call("profileAsset", str(self.workspace(d)), "spec", "spec_template")
            self.assertEqual(TEMPLATE, got["text"].replace("\r\n", "\n"))

    def test_no_profile_is_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            got = call("chapterTemplates", str(self.workspace(d, profile=None)), "spec", "spec_template")
            self.assertIsNone(got["templates"])
            self.assertEqual([], got["problems"])
            self.assertIn("没有配 project_profile.name", got["skipped"][0]["why"])

    def test_a_config_without_a_profile_is_not_applicable(self) -> None:
        """配置文件在、能解析、只是没有 project_profile：合法的未配置。"""
        with tempfile.TemporaryDirectory() as d:
            root = self.workspace(d, profile=None)
            (root / "framework.config.json").write_text('{"paths": {}}', encoding="utf-8")
            got = call("chapterTemplates", str(root), "spec", "spec_template")
            self.assertEqual([], got["problems"])
            self.assertEqual(1, len(got["skipped"]))

    def test_a_broken_config_is_a_problem_not_a_missing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = self.workspace(d)
            (root / "framework.config.json").write_text("{ broken", encoding="utf-8")
            got = call("chapterTemplates", str(root), "spec", "spec_template")
            self.assertEqual([], got["skipped"])
            self.assertIn("framework.config.json 解析失败", got["problems"][0])

    def test_a_configured_profile_with_broken_input_is_a_problem(self) -> None:
        cases = {
            "清单缺席": ({"manifest": None}, "读不到 framework/profiles/neutral-web/skills/skill-assets.yaml"),
            "清单解析失败": ({"manifest": "assets: [\n"}, "解析失败"),
            "没有这一项": ({"manifest": "assets:\n  plan: {}\n"}, "没有 spec.spec_template"),
            "文件读不到": ({"template": False}, "指向 spec/tpl/s.md，读不到"),
        }
        for name, (kw, said) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                got = call("chapterTemplates", str(self.workspace(d, **kw)), "spec", "spec_template")
                self.assertIsNone(got["templates"])
                self.assertEqual([], got["skipped"])
                self.assertIn(said, got["problems"][0])

    def test_a_missing_extension_template_is_a_problem(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            got = call("chapterTemplates", str(self.workspace(d)), "spec", "spec_template", "templates/no-such.md")
            self.assertIn("扩展模板 templates/no-such.md 读不到", got["problems"][0])


if __name__ == "__main__":
    unittest.main()
