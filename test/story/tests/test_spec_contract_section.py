# -*- coding: utf-8 -*-
"""§9.1 技术契约「表外有段落」这条判据，跑在**真实产物**上。

它只在真实输入上才现形：判的是节内正文的行，而行的边界由切节那一步给。
判据自己把它拼成字符串再切一遍的话，数组会以逗号连成一整行，节首那个空行
也就不再是空行——于是五节全被报成「表外有段落」，而它们都只有表。

所以这一份的输入是 `fixtures/real-run` 的 spec.md：CRLF、五节俱全、每节首行是空行的
那份真东西（目录自带 `.gitattributes: * -text` 保住换行）。构造用例看不见这个形态。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
REAL = REPO_ROOT / "test" / "story" / "fixtures" / "real-run" / "AR90006"
FEATURE = "AR90006"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [hookPath, feature, projectRoot] = process.argv.slice(-3);
const hook = (await import(pathToFileURL(hookPath).href)).default;
process.stdout.write(JSON.stringify(await hook({ phase: 'spec', feature, projectRoot })));
"""


class TheContractSectionIsJudgedOnRealOutput(unittest.TestCase):
    """一个类建一次工作区：它是只读夹具，而建一次要复制一份完整扩展。"""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "work"
        (cls.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, cls.root / "doc" / "extensions")
        link_harness_yaml(cls.root)
        shutil.copytree(REAL, cls.root / "doc" / "features" / FEATURE)
        # §9.1 那一章只在走过 /story 的 feature 上判——夹具里补一份流程契约，
        # 否则这一整组判据整块跳过，测出来的绿是「没判」不是「判过」。
        (cls.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps({"schema": 4, "feature": FEATURE, "status": "complete",
                        "rounds": [{"round": 1, "gates": []}]}, ensure_ascii=False),
            encoding="utf-8")
        driver = cls.root / "drive.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(driver),
             str(cls.root / "doc/extensions/hooks/spec/post_check.mjs"),
             FEATURE, str(cls.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert proc.returncode == 0, proc.stderr[-800:]
        cls.report = proc.stdout

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_a_real_spec_has_no_stray_prose_report(self) -> None:
        """五节都是表，一段散文也没有。"""
        self.assertNotIn("表外有段落", self.report,
                         f"真实 spec 的 §9.1 被误报：{self.report[:600]}")

    def test_the_five_subsections_are_all_seen(self) -> None:
        """判据确实跑到了这五节上——一条都没报不等于一条都没判。"""
        spec = (REAL / "spec" / "spec.md").read_text(encoding="utf-8")
        for name in ("端云接口", "数据存储", "配置项", "埋点", "依赖变更"):
            with self.subTest(section=name):
                self.assertIn(name, spec, "夹具的 §9.1 少了这一节，判据没有对象")
        self.assertNotIn("缺少小节", self.report, f"§9.1 的小节没被认出来：{self.report[:600]}")


if __name__ == "__main__":
    unittest.main()


class OnlyTheEventSectionTakesProse(TheContractSectionIsJudgedOnRealOutput):
    """§9.1.4 承载完整埋点设计，可以有 H4、正文与列表；其余小节仍然只收表。"""

    EVENTS = '#### 9.1.4 埋点\n\n开户与结果查询两个流程各看一个成功率。\n\n##### 开户成功率\n\n衡量开户办理的完成比例：分子是开户成功，分母是全部提交开户；打点在开户办理流程的信息校验与短信验证两步。\n\n| 统计点 | 所在流程 | 适用结果 | 代码现状 |\n|---|---|---|---|\n| 信息校验 | 开户办理 | 步骤成功 / 普通失败 | 检索零命中 |\n| 短信验证 | 开户办理 | 步骤成功 / 普通失败 / 主动取消 | 检索零命中 |\n\n- 页面进入、点击由自动运维上报采集，流程见[开户成功率](#开户成功率)。\n\n##### 查询成功率\n\n衡量开户结果查询的成功比例：分子是查询成功，分母是全部查询；打点在结果查询流程的查询开户结果一步。\n\n| 统计点 | 所在流程 | 适用结果 | 代码现状 |\n|---|---|---|---|\n| 查询开户结果 | 结果查询 | 步骤成功 / 普通失败 | 检索零命中 |\n\n'

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "work"
        (cls.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, cls.root / "doc" / "extensions")
        link_harness_yaml(cls.root)
        feature = cls.root / "doc" / "features" / FEATURE
        shutil.copytree(REAL, feature)
        (feature / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps({"schema": 4, "feature": FEATURE, "status": "complete",
                        "rounds": [{"round": 1, "gates": []}]}, ensure_ascii=False), encoding="utf-8")
        spec = feature / "spec" / "spec.md"
        text = spec.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        start, end = text.index("#### 9.1.4"), text.index("#### 9.1.5")
        head, rest = text[:end], text[end:]
        head = head[:start] + cls.EVENTS.replace("\n", nl)
        at = head.index("#### 9.1.2")
        head = head[:at] + head[at:].replace("|" + nl + nl, "|" + nl + nl + "这里多写了一段说明。" + nl + nl, 1)
        spec.write_bytes((head + rest).encode("utf-8"))
        driver = cls.root / "drive.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(driver), str(cls.root / "doc/extensions/hooks/spec/post_check.mjs"),
             FEATURE, str(cls.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert proc.returncode == 0, proc.stderr[-800:]
        cls.report = proc.stdout

    def test_a_real_spec_has_no_stray_prose_report(self) -> None:
        """父类这一条在这里不成立：数据存储那一节故意多了一段。"""

    def test_the_event_section_is_not_reported(self) -> None:
        self.assertNotIn("「埋点」表外有段落", self.report, self.report[:600])

    def test_other_subsections_still_take_only_tables(self) -> None:
        self.assertIn("「数据存储」表外有段落", self.report, self.report[:600])

    def test_text_and_links_are_not_taken_for_figures(self) -> None:
        self.assertNotIn("里有图或围栏", self.report, self.report[:600])


class FiguresInTheEventSectionAreReportedAtSpec(OnlyTheEventSectionTakesProse):
    """§9.1.4 投影进 Story 附录，附录不收图：图与围栏在 Spec 就报，并指到业务章。"""

    FIGURE = "![开户流程](images/open.png)\n\n"

    @classmethod
    def setUpClass(cls) -> None:
        cls.EVENTS = OnlyTheEventSectionTakesProse.EVENTS.replace("##### 查询成功率\n\n", cls.FIGURE + "##### 查询成功率\n\n")
        super().setUpClass()

    def test_text_and_links_are_not_taken_for_figures(self) -> None:
        """父类这一条在这里不成立：这一节故意放了图。"""

    def test_the_figure_is_reported_with_where_it_belongs(self) -> None:
        self.assertIn("「埋点」里有图或围栏", self.report, self.report[:600])
        self.assertIn("业务需要的图放它讲的业务章", self.report)


class DiagramFencesInTheEventSectionAreReportedAtSpec(FiguresInTheEventSectionAreReportedAtSpec):
    FIGURE = "```mermaid\nflowchart LR\n  A --> B\n```\n\n"
