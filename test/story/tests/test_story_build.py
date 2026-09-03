"""`story-build` 三个命令的单元断言——init 派生什么、audit 记什么、check 拦什么。

台账（`check_failure_modes.py`）判的是**形态回不回来**：一个已知会犯的错，机制现在抓不抓得住。
本文件判的是**判据本身的边界**：同一条判据，改一个字符就该翻面的那些地方。两者都要有，
因为台账只覆盖曾经真实发生过的错，而边界是它没走到的地方。

夹具借用 `R01-verdict-echo/good`——它是一份最小但完整的工作区（材料 + story + 激活清单 +
决策件）。每个用例在**副本**上跑：这几条命令会写 `source-units.json` / `audit.json`，
在夹具原地跑会把它写脏，且上一个用例的产物会影响下一个。
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

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "AR90001"
FLOW = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story_flow.py"

CHAPTER_OUT_OF_CONTRACT = "第十五章"
QUOTE = "提交之后回执没到之前，界面停在等待态"


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


def _verdict_tables(repo_root, quote: str, unit_rows, story_path=None) -> str:
    """按合同派生裁决者的三张表：逐单元 / 逐问 / 逐章。

    逐问与逐章的行由**合同**决定（章、问题、维度），不在测试里写死：合同改了夹具
    自动跟着变；写死的话，改合同就要同步改一堆夹具，而没人保证会改。

    引文取该章自己的一段原文——用同一句填满所有章会被 check 判「引文在该章里
    检索不到」，那正是它该做的。
    """
    import json as _json
    contract = _json.loads((Path(repo_root) / "doc/extensions/skills/story/contracts"
                            / "story-chapters.json").read_text(encoding="utf-8"))
    verdicts = contract.get("verdicts") or {}
    question_ok = (verdicts.get("question_words") or ["答了"])[0]
    chapter_ok = (verdicts.get("chapter_words") or ["达标"])[0]
    bodies = _chapter_bodies(story_path)

    lines = ["| 单元键 | 裁决 | 引文 |", "|---|---|---|"]
    lines += ["| {} | {} | {} |".format(k, v, q) for k, v, q in unit_rows]

    lines += ["", "| 章 | 问题 | 裁决 | 引文 |", "|---|---|---|---|"]
    for chapter in contract.get("chapters") or []:
        body = bodies.get(chapter["title"], "")
        if _is_empty_chapter(body):
            continue
        evidence = _chapter_quote(body) or quote
        for question in chapter.get("questions") or []:
            lines.append("| {} | {} | {} | {} |".format(
                chapter["title"], question, question_ok, evidence))

    lines += ["", "| 章 | 维度 | 裁决 | 依据 |", "|---|---|---|---|"]
    for chapter in contract.get("chapters") or []:
        if chapter.get("appendix") or _is_empty_chapter(bodies.get(chapter["title"], "")):
            continue
        for dimension in verdicts.get("chapter_dimensions") or []:
            lines.append("| {} | {} | {} | 本章按此写就 |".format(
                chapter["title"], dimension, chapter_ok))
    return "\n".join(lines) + "\n"


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
        return subprocess.run(
            ["node", str(BUILD), command, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def init_audit(self) -> None:
        for command in ("init", "audit"):
            proc = self.run_build(command)
            self.assertEqual(proc.returncode, 0, f"{command} 跑不起来：{proc.stderr}")

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

    @property
    def units(self) -> list[dict]:
        return json.loads((self.src / "source-units.json").read_text(encoding="utf-8"))["units"]

    @property
    def audit(self) -> dict:
        return json.loads((self.src / "audit.json").read_text(encoding="utf-8"))

    def write_audit(self, data: dict) -> None:
        (self.src / "audit.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_verdicts(self, rows: list[tuple[str, str, str]]) -> None:
        """三张表一起写——裁决者的产物本来就是三张，只写一张 check 会判缺表。"""
        fallback = next((q for _, verdict, q in rows
                         if verdict == "讲清" and len(q) >= 12), "")
        (self.src / "story-verdicts.md").write_text(
            _verdict_tables(REPO_ROOT, fallback, rows, self.story_path), encoding="utf-8")

    def story(self) -> str:
        return self.story_path.read_text(encoding="utf-8")

    def rewrite_story(self, old: str, new: str) -> None:
        text = self.story()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.story_path.write_text(text.replace(old, new), encoding="utf-8")

    @staticmethod
    def _quote_for(body: str, unit_text: str, tokens: list, used: dict) -> str:
        """给这一条单元挑一句引文：**讲它的那一句**，不是全章第一句。

        装置模拟的是尽职的裁决者。拿同一句给全章所有单元作证，正是 check ⑥ 要拦的
        形态（一句章级总述句能满足够长、是原文、非回声三条）——装置这么做，
        那条判据就永远测不出来。
        """
        cands = []
        for line in body.split("\n"):
            cand = line.strip()
            if cand.startswith("|"):
                cells = [c.strip() for c in cand.strip("|").split("|")]
                cells = [c for c in cells if c and not set(c) <= set("-: ")]
                if not cells:
                    continue
                cand = max(cells, key=len)
            if len(cand) >= 14 and cand not in unit_text and not cand.startswith("#"):
                cands.append(cand)
        if QUOTE in body and QUOTE not in unit_text:
            cands.insert(0, QUOTE)
        for cand in cands:
            if any(t and t in cand for t in tokens):
                used[cand] = used.get(cand, 0) + 1
                return cand
        for cand in cands:
            if used.get(cand, 0) < 2:
                used[cand] = used.get(cand, 0) + 1
                return cand
        return cands[0] if cands else ""

    def settle(self) -> list[str]:
        """把机器定不了落点的单元交给作者并配上裁决——夹具的基线态。

        `check` 要求三态之一齐备：机器定不了的那些，正式链路上由 S5 裁决者处置。
        用例要断言「某一条判据翻面」，基线就得是通过态，否则测的是别的问题。
        """
        data = self.audit
        by_key = {u["key"]: u for u in self.units}
        bodies = _chapter_bodies(self.story_path)
        # 表行要落在有表的那一章：把材料的表摊进一章散文里，check ④ 判它降级——
        # 那是它该做的，但这里要的是通过态基线，不是去撞那条判据
        appendix = _appendix_title()
        with_table = next((t for t, b in bodies.items()
                           if t != appendix
                           and any(x.strip().startswith("|") for x in b.split("\n"))), None)
        rows = []
        used: dict = {}
        for record in data["records"]:
            if any(record.get(k) for k in ("at", "covered_by", "machine_facing")):
                continue
            kind = by_key.get(record["key"], {}).get("kind")
            at = with_table if (kind == "table_row" and with_table) else "功能说明"
            record["at"], record["by"] = at, "author"
            body = bodies.get(at, "")
            unit_text = by_key.get(record["key"], {}).get("text") or ""
            tokens = by_key.get(record["key"], {}).get("tokens") or []
            quote = self._quote_for(body, unit_text, tokens, used)
            rows.append((record["key"], "讲清", quote or QUOTE))
        self.write_audit(data)
        if rows:
            self.write_verdicts(rows)
        return [k for k, _, _ in rows]

    def hand_to_author(self) -> list[str]:
        """把机器定不了落点的那些交给作者，返回它们的键。

        夹具里所有单元机器都能定位，所以这里主动造一条：拿走一个单元的机器落点，
        改标成作者落点——`check ⑥` 的裁决核实只对 `by: author` 生效。
        """
        data = self.audit
        keys = []
        for record in data["records"]:
            if record.get("at") and record.get("by") == "machine":
                record["at"], record["by"] = "功能说明", "author"
                keys.append(record["key"])
                break
        self.assertTrue(keys, "夹具里没有可改判的记录")
        for record in data["records"]:
            if not any(record.get(k) for k in ("at", "covered_by", "machine_facing")):
                record["at"], record["by"] = "功能说明", "author"
                keys.append(record["key"])
        self.write_audit(data)
        self.write_verdicts([(k, "讲清", QUOTE) for k in keys])
        return keys


class TestTokenExclusion(StoryBuildCase):
    """守恒对象与归档件红线不能互相打架——同一个词不能既要求出现又禁止出现。"""

    def test_drop_shaped_id_never_becomes_a_token(self) -> None:
        """`drop` 的编号 check ③ 明令不许进 story，它就不能是守恒要求出现的 token。"""
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n功能 F7 与场景 S2 在本期一起上。\n",
                       encoding="utf-8")
        self.init_audit()
        tokens = {t for u in self.units for t in (u.get("tokens") or [])}
        self.assertNotIn("F7", tokens)
        self.assertNotIn("S2", tokens)

    def test_drop_shaped_id_in_story_still_fails(self) -> None:
        """排除的是守恒对象，不是红线——编号真写进 story 仍要被拦。"""
        self.init_audit()
        self.settle()
        self.rewrite_story("本需求不涉及。\n\n## 术语", "功能 F7 已完成。\n\n## 术语")
        self.assert_check_names("story 里出现了仓内工作编号")


class TestTemplateNotes(StoryBuildCase):
    """模板生成的文字不是材料——按生成它的模板约定判，不按样本形状判。"""

    def test_spec_blockquotes_leave_the_author_facing_set(self) -> None:
        """spec 模板的 `>` 块只承载登记项与作业说明，没有可讲的事实。

        它们留在材料面时，审稿者只能对着「**版本**: v1.0」盖一个「讲清」——
        实测 43/43 全「讲清」、0「未讲清」，区分力就是这么被稀释掉的。
        """
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "\n".join([
                "# 甲需求 spec",
                "",
                "> **版本**: v1.0",
                "> **状态**: 草稿（评审中）",
                "",
                "## 0. 术语映射表",
                "",
                "> 本节是本 spec 的第一道 BLOCKER：业务名词必须映射到真实存在的模块名。",
                "",
                "| 原始术语 | 权威模块 |",
                "|---|---|",
                "| 等待态 | 甲模块 |",
                "",
            ]),
            encoding="utf-8")
        self.init_audit()
        spec_bq = [u for u in self.units if u["doc"] == "SPEC" and u["kind"] == "blockquote"]
        self.assertTrue(spec_bq, "夹具的 spec 里应当有 > 块")
        for unit in spec_bq:
            self.assertTrue(unit["machine_facing"], f"{unit['key']} 仍在材料面：{unit['text'][:30]}")
            self.assertEqual(unit["tokens"], [], "机器面单元不参与 token 守恒")

    def test_author_written_blockquotes_are_untouched(self) -> None:
        """PRD 是人写的，它的 `>` 块该留在材料面——判据只对声明了 notes 的那份材料生效。"""
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8")
                       + "\n> 产品强调：断网时也要能打开已经存下来的凭证。\n",
                       encoding="utf-8")
        self.init_audit()
        prd_bq = [u for u in self.units if u["doc"] == "PRD" and u["kind"] == "blockquote"]
        self.assertTrue(prd_bq, "PRD 里应当有 > 块")
        self.assertTrue(all(not u["machine_facing"] for u in prd_bq),
                        "人写的 > 块不该被打成机器面")


class TestDerivedSourceTokens(StoryBuildCase):
    """合同声明 `derived` 的那份材料只守业务编号。

    spec.md 是本轮流程自己生成的中间产物。它的工程 token（元素类型词、夹具名、
    毫秒数、包名）此前全背落点义务，实测 194 个——归档叙事件不该写这些词，
    于是它们只能挤进附录表后的散文尾巴与材料清单，倾倒区就是这么长出来的。
    业务编号仍守恒：那是评审人认得、也会在验收里回找的东西。
    """

    SPEC_BODY = "\n".join([
        "# 甲需求 spec",
        "",
        "## 9. 技术契约",
        "",
        "验收 AC-7 覆盖等待态；接口 submitTicket 超时 1500ms 后转失败，"
        "承接名为 TicketFixture，宿主配置写在 oh-package.json5。",
        "",
    ])

    def put_spec(self) -> None:
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(self.SPEC_BODY, encoding="utf-8")

    def test_only_business_ids_survive_in_a_derived_source(self) -> None:
        self.put_spec()
        self.init_audit()
        tokens = [t for u in self.units if u["doc"] == "SPEC" for t in (u.get("tokens") or [])]
        self.assertIn("AC-7", tokens, "验收编号是业务编号，仍要守恒")
        for engineering in ("submitTicket", "1500ms", "TicketFixture", "oh-package.json5"):
            self.assertNotIn(engineering, tokens,
                             f"{engineering} 是工程细节，它的家是 spec 自己")

    def test_the_text_of_a_derived_unit_is_unchanged(self) -> None:
        """收窄的是机器核对义务，不是信息可见性——分配与渲染仍读得到整行。"""
        self.put_spec()
        self.init_audit()
        hit = [u for u in self.units
               if u["doc"] == "SPEC" and "submitTicket" in (u.get("text") or "")]
        self.assertTrue(hit, "spec 单元的正文该原样留着")

    def test_the_other_sources_keep_every_token(self) -> None:
        """回归：只有声明 `derived` 的那一份变，人写的材料一个 token 都不少。"""
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8")
                       + "\n签约接口 signContract 超时 1500ms 后转失败。\n",
                       encoding="utf-8")
        self.put_spec()
        self.init_audit()
        prd_tokens = [t for u in self.units if u["doc"] == "PRD" for t in (u.get("tokens") or [])]
        self.assertIn("signContract", prd_tokens, "上游材料的接口名照旧守恒")
        self.assertIn("1500ms", prd_tokens, "上游材料的带单位数值照旧守恒")

    def test_a_source_without_the_flag_is_not_narrowed(self) -> None:
        """开关在合同数据里，机制不认识任何一份材料的名字——把标记摘掉，token 就回来。"""
        contract = (REPO_ROOT / "doc/extensions/skills/story/contracts"
                    / "story-chapters.json")
        data = json.loads(contract.read_text(encoding="utf-8"))
        derived = [k for k, v in (data.get("sources") or {}).items()
                   if isinstance(v, dict) and v.get("derived")]
        self.assertEqual(derived, ["SPEC"],
                         "本轮只有 spec 是中间产物；再多一份要连同报告一起说明")


class TestKnowledgeUnits(StoryBuildCase):
    """KR-2a/2b：激活规约条目是来源单元，判定逐条落在合规章的表里。"""

    def test_entries_become_units_with_domain_and_id(self) -> None:
        self.init_audit()
        knowledge = [u for u in self.units if u["key"].startswith("KNOWLEDGE:")]
        self.assertTrue(knowledge, "激活清单里的规约条目应当派生成来源单元")
        for unit in knowledge:
            self.assertTrue(unit.get("domain"), f"{unit['key']} 缺域名")
            self.assertIn(unit["key"].split(":", 1)[1], unit["text"] + str(unit.get("tokens")))

    def test_repo_manifest_derives_units_too(self) -> None:
        """本仓自己的激活清单也要派生得出来——夹具过了不代表真清单过。"""
        script = (
            "import {activeKnowledge} from './doc/extensions/hooks/shared/knowledge.mjs';"
            "import {knowledgeUnits} from './doc/extensions/skills/story/scripts/source-units.mjs';"
            "console.log(knowledgeUnits(activeKnowledge(process.cwd()).entries).length);")
        proc = subprocess.run(["node", "--input-type=module", "-e", script],
                              cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(int(proc.stdout.strip()), 0, "本仓激活清单派生出 0 个规约单元")

    def test_missing_row_is_named(self) -> None:
        self.init_audit()
        self.rewrite_story("| 甲域约束 | SMP-02 | 不命中 | 本需求没有任何上报动作 |\n", "")
        self.assert_check_names("判定表里没有行")

    def test_verdict_word_is_closed(self) -> None:
        self.init_audit()
        self.rewrite_story("| 甲域约束 | SMP-02 | 不命中 |", "| 甲域约束 | SMP-02 | 大概不涉及 |")
        self.assert_check_names("不是 命中 / 不命中 / 整域不适用 之一")

    def test_basis_cannot_be_empty(self) -> None:
        self.init_audit()
        self.rewrite_story("| 甲域约束 | SMP-02 | 不命中 | 本需求没有任何上报动作 |",
                           "| 甲域约束 | SMP-02 | 不命中 |  |")
        self.assert_check_names("没写依据")

    def test_domain_level_row_covers_every_entry(self) -> None:
        """整域不适用时给该域一行即可，域内条目不必逐条列。"""
        self.init_audit()
        self.settle()
        self.rewrite_story(
            "| 甲域约束 | SMP-01 | 命中 | 本需求新增提交入口，受理单编号在入口生成 |\n"
            "| 甲域约束 | SMP-02 | 不命中 | 本需求没有任何上报动作 |",
            "| 甲域约束 | — | 整域不适用 | 本需求不触及该域的任何场景 |")
        code, out = self.check_output()
        self.assertEqual(code, 0, f"域级判定应当覆盖域内全部条目：{out}")


class TestGlossaryAndRedlines(StoryBuildCase):
    """KR-4a：merge-story 并进来的两件事——术语表实体词守恒与归档件四红线。"""

    def write_spec(self, term: str) -> None:
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# 甲需求 spec\n\n## 0. 术语映射表\n\n"
            "| 原始术语 | 权威模块 | 解释 |\n|---|---|---|\n"
            f"| {term} | 甲模块 | 一次提交的唯一标识 |\n",
            encoding="utf-8")

    def test_repo_path_in_story_is_named(self) -> None:
        self.init_audit()
        self.rewrite_story("本需求不涉及。\n\n## 术语",
                           "详见 doc/features/AR90001/AR/design.md。\n\n## 术语")
        self.assert_check_names("仓内路径")


class TestSourceDrift(StoryBuildCase):
    """材料在枚举之后又变过，check 就要拦。

    规格件在 story 写完之后还会继续长——评审裁定回填、遗漏补写。后长出来的内容
    永远不会成为来源单元，守恒面悄悄小了一圈：登记那一刻 check 是过的，
    过些时候重跑 audit 才露出一批三态皆空（首跑实测 27 条，全部来自规格件）。
    这是**物理门禁**而不是流程约定：「记得重跑一次 init」这种话，模型会忘。
    """

    def test_edited_material_is_named(self) -> None:
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0])
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n补一条：超时后允许重试一次。\n",
                       encoding="utf-8")
        out = self.assert_check_names("材料在枚举之后变了")
        self.assertIn("RR/prd.md", out)
        self.assertIn("重跑 init", out)

    def test_a_material_added_after_enumeration_is_named(self) -> None:
        self.init_audit()
        self.settle()
        spec_dir = self.root / "doc" / "features" / FEATURE / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text("# 甲需求 规格\n\n## 1. 范围\n\n只改提交入口。\n",
                                          encoding="utf-8")
        self.assert_check_names("材料在枚举之后变了")

    def test_reenumerating_clears_it_and_keeps_author_placements(self) -> None:
        """重跑 init 之后门禁放行，而且已经分好的落点还在——不然没人敢重跑。"""
        self.init_audit()
        self.settle()
        placed = {r["key"]: r["at"] for r in self.audit["records"] if r.get("by") == "author"}
        self.assertTrue(placed)
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n补一条：超时后允许重试一次。\n",
                       encoding="utf-8")
        self.init_audit()
        after = {r["key"]: r.get("at") for r in self.audit["records"]}
        for key, at in placed.items():
            self.assertEqual(at, after.get(key), f"{key} 的作者落点在重跑后丢了")
        out = self.check_output()[1]
        self.assertNotIn("材料在枚举之后变了", out)


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
        source = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("但那一章里找不到", source)


REVIEW_HUMAN_ZONE = "审核结果：\n"


class TestReviewForm(StoryBuildCase):
    """评审人要填的只剩「审核结果：」一行——需要说明书就是设计错了。

    曾经这里还有暂缓责任人、完成期限、是否阻塞执行、后续动作、确认人、确认日期、
    确认依据七个字段。评审人打开它先要读一遍字段表，而其中六格他答不上来
    （责任人和期限是排期的事，确认依据是审计的事）。答不上来的格子只会被跳过或胡填。
    三态勾选是同一个问题的轻量版：勾「需要修改」而不写改成什么，那一勾传不出任何信息；
    既然要写字，框就是多余的。
    """

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def write_decision(self) -> None:
        (self.src / "decisions.json").write_text(json.dumps({
            "decisions": [{
                "id": "submit-boundary", "status": "settled",
                "title": "提交入口与补卡由两张开发单分别承接",
                "clarification": "**要定的事**：提交与补卡要不要放在同一张单里做。\n\n"
                                 "**根据**：上游已经拆成两张开发单。\n\n"
                                 "**结论与影响**：本单只做提交与回执展示，验收不含补卡。",
                "decider": "需求负责人",
            }],
        }, ensure_ascii=False), encoding="utf-8")

    def test_the_human_zone_is_one_line(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.assertIn(REVIEW_HUMAN_ZONE, text)
        for gone in ("暂缓责任人", "完成期限", "是否阻塞执行", "后续动作",
                     "确认人", "确认日期", "确认依据", "**状态**",
                     "- [ ]", "同意当前建议", "暂缓原因"):
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
            "审核结果：\n\n" + anchor,
            "审核结果：范围要含补卡入口。\n\n**确认人**：某评审人\n\n" + anchor)
        self.review_path.write_text(filled, encoding="utf-8")

        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("审核结果：范围要含补卡入口。", again)
        self.assertIn("**确认人**：某评审人", again, "旧形态里人写过的字也要保住")

    def test_legacy_fields_in_the_review_are_named(self) -> None:
        """人工区之外又长回签署字段与状态行时，check 要点名。"""
        self.init_audit()
        self.settle()
        self.review_path.write_text(
            "# 评审记录\n\n### 1. 提交入口与补卡由两张开发单分别承接\n\n"
            "审核结果：\n\n"
            "<!-- decision: submit-boundary -->\n\n"
            "**确认日期**：\n\n**状态**：草稿（待开发确认）\n",
            encoding="utf-8")
        out = self.assert_check_names("评审记录里出现")
        self.assertIn("确认日期", out)
        self.assertIn("状态行", out)


class TestRequirementIdInTitle(StoryBuildCase):
    """大标题带需求编号——归档件离开这个仓库后，编号是它回到需求系统的唯一一根绳子。"""

    def test_title_without_the_id_is_named(self) -> None:
        self.init_audit()
        self.settle()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, "# " + first[2:].replace(FEATURE, "").strip())
        out = self.assert_check_names("大标题缺需求编号")
        self.assertIn(FEATURE, out, "报错要把该写的编号给出来")

    def test_offline_falls_back_to_the_shape(self) -> None:
        """离线只有一份 story，不知道 feature 叫什么——此时核形态，不放过去。"""
        story = Path(self._tmp.name) / "AR" / "story.md"
        story.parent.mkdir(parents=True, exist_ok=True)
        text = self.story()
        story.write_text(text.replace(text.split("\n", 1)[0], "# 某需求"), encoding="utf-8")
        proc = subprocess.run(
            ["node", str(BUILD), "check", "--offline", "--story", str(story),
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode)
        self.assertIn("大标题缺需求编号", (proc.stderr or "") + (proc.stdout or ""))


class TestRedlineScope(StoryBuildCase):
    """逐类作用域：多数红线只管附录之外，取证语言与装置词在附录里同样不该有。"""

    def _put_in_appendix(self, line: str) -> None:
        bodies = _chapter_bodies(self.story_path)
        anchor = bodies[_appendix_title()].split("\n")[0]
        self.rewrite_story(anchor, anchor + "\n\n" + line)

    def test_search_phrase_in_the_appendix_is_named(self) -> None:
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0])
        self._put_in_appendix("检索挂失回执封装零命中。")
        self.assert_check_names("这是起草过程")

    def test_harness_word_in_the_appendix_is_named(self) -> None:
        self.init_audit()
        self.settle()
        self._put_in_appendix("本次交付先以模拟实现替代真实通道。")
        self.assert_check_names("造它的装置与流程说的话")

    def test_identifiers_stay_legal_in_the_appendix(self) -> None:
        """附录仍是工程标识的落点——顺手把它一起收紧，作者就无处可写了。"""
        self.init_audit()
        self.settle()
        self._put_in_appendix("| 接口 | 用途 |\n|---|---|\n| queryLossState | 查挂失结果 |")
        self.assertEqual(0, self.check_output()[0])


class TestDecisionUnits(StoryBuildCase):
    """决策登记走独立派生通道：取舍理由在材料里没有，它是起草时判出来的。"""

    DECISIONS = {
        "decisions": [
            {"id": "DEC-001", "status": "settled",
             "title": "挂失结果以卡片服务的回执为准",
             "clarification": "**要定的事**：挂失办没办成，以哪一侧的说法为准。\n\n"
                              "**根据**：本端只有请求态，判不了卡是否真的停用。\n\n"
                              "**结论与影响**：以卡片服务的回执为准，页面照回执显示。",
             "decider": "需求负责人", "category": "验收口径"},
            {"id": "DEC-002", "status": "settled",
             "title": "同卡同状态的重复提交按一次算",
             "clarification": "**要定的事**：同一张卡短时间内重复提交怎么处理。\n\n"
                              "**根据**：重复提交只会让用户以为办了两次。\n\n"
                              "**结论与影响**：按一次算，第二次直接回到等待态。",
             "decider": "需求负责人", "category": "流程顺序与准入"},
            {"id": "DEC-003", "status": "open",
             "title": "线下渠道的入口这轮收不收",
             "clarification": "**要定的事**：线下渠道的入口要不要一起收进本单。\n\n"
                              "**可选的做法**：1. 本单先不收，等渠道方给时间表；"
                              "2. 一起收，范围扩到渠道侧。\n\n"
                              "**建议**：按第 1 种做。",
             "decider": "产品负责人", "category": "范围与拆分"},
        ],
    }

    def write_decisions(self, decisions=None) -> None:
        path = self.src / "decisions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["decisions"] = decisions if decisions is not None else self.DECISIONS["decisions"]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_each_decision_becomes_one_unit(self) -> None:
        self.write_decisions()
        self.assertEqual(0, self.run_build("init").returncode)
        units = [u for u in self.units if u["kind"] == "decision"]
        self.assertEqual(3, len(units), "三条决策该切出三个单元")
        settled = next(u for u in units if u["key"] == "DECISION:DEC-001")
        self.assertIn("以卡片服务的回执为准", settled["text"])
        self.assertIn("本端只有请求态", settled["text"], "理由要进正文——它正是取舍的那一半")
        self.assertEqual([], settled["tokens"], "取舍是纯中文叙述，机器不判落点")

    def test_open_issues_carry_no_landing_duty(self) -> None:
        """开放议题还没有结论——正文里写它，等于把未定的事说成定了。"""
        self.write_decisions()
        self.init_audit()
        keys = {r["key"] for r in self.audit["records"]}
        self.assertIn("DECISION:DEC-001", keys)
        self.assertNotIn("DECISION:DEC-003", keys)
        self.settle()
        self.assertEqual(0, self.check_output()[0])

    def test_an_empty_register_speaks_up(self) -> None:
        """一条决策都没登记时要出声——不能当作「这个需求没做过任何判断」静默通过。"""
        self.write_decisions([])
        proc = self.run_build("init")
        self.assertEqual(0, proc.returncode)
        self.assertIn("决策登记里一条都没有", proc.stdout)

    def test_editing_a_decision_never_trips_the_material_drift_gate(self) -> None:
        """决策件是流程里的活件：评审回填、遗漏补写都是既定动作，不该撞指纹门禁。"""
        self.write_decisions()
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0])
        self.write_decisions(self.DECISIONS["decisions"] + [
            {"id": "DEC-004", "status": "open", "title": "回执超时的等待时长",
             "clarification": "**要定的事**：回执迟迟不到时等多久。\n\n"
                              "**可选的做法**：1. 先按现网默认值；2. 等渠道方给数。\n\n"
                              "**建议**：按第 1 种做。",
             "decider": "需求负责人", "category": "规则与数值"}])
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertNotIn("材料在枚举之后变了", out)


class TestDuplicateAcrossParagraphs(StoryBuildCase):
    """重复判的是逐字相等，粒度到句——最常见的那一种跨在两段之间。"""

    SENTENCE = "上一轮办到哪一步由服务端的受理记录决定，本端不自己记账。"

    def _append_to_chapter(self, extra: str) -> None:
        bodies = _chapter_bodies(self.story_path)
        title = next(t for t, b in bodies.items()
                     if t != _appendix_title() and not _is_empty_chapter(b))
        anchor = bodies[title].split("\n")[0]
        self.rewrite_story(anchor, anchor + extra)

    def test_a_sentence_repeated_in_another_paragraph_is_named(self) -> None:
        """长段的末句被另起一段整句重说：两边的「段」不同，句子逐字相同。"""
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0])
        self._append_to_chapter(
            "\n\n用户回到页面时看到的是上一轮的进度。" + self.SENTENCE
            + "\n\n" + self.SENTENCE)
        out = self.assert_check_names("重复")
        self.assertIn("行重复", out, "报错要指回第一次出现的行")

    def test_saying_it_once_passes(self) -> None:
        self.init_audit()
        self.settle()
        self._append_to_chapter(
            "\n\n用户回到页面时看到的是上一轮的进度。" + self.SENTENCE)
        self.assertEqual(0, self.check_output()[0])


class TestOwnRequirementIdIsNotAnIdentifier(StoryBuildCase):
    """本需求自己的编号不是工程标识。

    ①b 要求大标题带着它，材料清单也要写清这份文档出自哪张单——它恰恰是归档件与
    需求系统之间唯一的绳子。判它违规，两条判据就打架，作者无路可走。
    实测一轮实跑卡死在这里：模型反复改标题、始终过不了，最后没登记成文就交了。

    这条**离线跑不出来**（离线没有来源单元，标识符表是空的），所以必须在线跑。
    """

    def _put_id_in_materials(self) -> None:
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.write_text(
            "# " + FEATURE + " 规格\n\n"
            "## 1. 范围\n\n本单 " + FEATURE + " 只改提交入口。\n",
            encoding="utf-8")

    def test_the_title_carrying_the_id_passes(self) -> None:
        self._put_id_in_materials()
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertIn(FEATURE, self.story().split("\n", 1)[0], "夹具的大标题本来就带编号")

    def test_another_repo_identifier_is_still_named(self) -> None:
        """放行的只有本需求编号这一个——别的标识照拦，不然等于把 ⑩ 关掉。"""
        self._put_id_in_materials()
        self.init_audit()
        self.settle()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n提交走 queryLossEligibility 这个接口。")
        self.assert_check_names("工程标识")


class TestChapterSections(StoryBuildCase):
    """正文章的节级形态：必有的小节在不在、该分节的章分没分。

    实测规律（两轮四份产物零例外）：有 check 判据的形态全达成，只写在模板注释或
    占位里的形态全不达成。节级此前只有注释承载，于是方案章、流程章、交付章全部平铺。

    **判据恰三条**，本类的后两条守的正是「没有加码」：菜单项不是配额、
    每章几节不设下限。配额逼出来的是凑数小标题，那比平铺更难读。
    """

    SOLUTION = ("本需求由钱包端发起挂失请求，卡片服务判定结果。\n\n"
                "### 4.1 参与方与分工\n\n"
                "钱包端负责入口与结果展示，卡片服务负责判定与状态落库。\n")

    def put_chapter(self, title: str, body: str) -> None:
        text = self.story()
        head = "## {}\n\n".format(title)
        start = text.index(head) + len(head)
        end = text.index("\n## ", start)
        self.story_path.write_text(text[:start] + body + text[end:], encoding="utf-8")

    def write_decisions(self, decisions: list) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": decisions}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    SETTLED = {
        "id": "DEC-001", "status": "settled",
        "title": "挂失结果以卡片服务的回执为准",
        "clarification": "**要定的事**：以哪一侧为准。\n\n**根据**：本端只有请求态。\n\n"
                         "**结论与影响**：以回执为准。",
        "decider": "需求负责人",
    }

    def test_a_required_section_missing_is_named(self) -> None:
        """必有的小节缺席要点名，并说清这一节是干什么的。"""
        self.put_chapter("业务方案", "钱包端发起、卡片服务判定，两侧以回执为准。\n")
        self.init_audit()
        self.settle()
        out = self.assert_check_names("参与方与分工")
        self.assertIn("这一节", out)

    def test_an_empty_chapter_is_exempt(self) -> None:
        """空章豁免：它已明说这件事不在本需求里，节级形态无从谈起。"""
        self.init_audit()
        self.settle()
        self.assertIn("## 业务方案\n\n本需求不涉及。", self.story())
        self.assertEqual(0, self.check_output()[0])

    def test_settled_decisions_require_the_tradeoff_section(self) -> None:
        """有已定决策却没有取舍那一节——取舍化进散文，读者拼不出「否掉了什么」。"""
        self.put_chapter("业务方案", self.SOLUTION)
        self.write_decisions([self.SETTLED])
        self.init_audit()
        self.settle()
        out = self.assert_check_names("关键取舍")

        # 同一份正文，没有已定决策时不要求——判据跟着登记走，不是无条件加一节
        self.write_decisions([])
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0], out)

    def test_a_flat_chapter_that_must_be_sectioned_is_named(self) -> None:
        self.put_chapter("业务流程", "用户进入入口、提交、等回执，回执到达即结束。\n")
        self.init_audit()
        self.settle()
        self.assert_check_names("个小节")

    def test_the_menu_is_not_a_quota(self) -> None:
        """菜单是命名参考：只写必有的那一节，其余菜单项缺席照样通过。"""
        self.put_chapter("业务方案", self.SOLUTION)
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_no_lower_bound_on_how_many_sections(self) -> None:
        """一节也够：`min_sections` 只区分「分了没分」，不数够不够多。"""
        self.put_chapter(
            "业务流程",
            "### 5.1 提交与回执\n\n用户提交之后等回执，回执到达即结束。\n")
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(0, code, out)


class TestCopyeditTrace(StoryBuildCase):
    """统稿留痕：恰好六行，**内容不判**。

    统稿是唯一一步没有产物的动作，于是跳过它零成本——实测两份产物都有「同一件事
    讲三遍」「图题一章一个样」这类只有通读才看得见的毛病，而门禁全绿。
    留痕不是为了核内容（那归裁决面与抽样人核），是为了让「没做」留下痕迹。
    """

    SIX = "\n".join("第 {} 项：查过，无需改。".format(i) for i in range(1, 7)) + "\n"

    def write_copyedit(self, text: str) -> None:
        (self.src / "copyedit.md").write_text(text, encoding="utf-8")

    def test_missing_file_is_named(self) -> None:
        (self.src / "copyedit.md").unlink()
        self.init_audit()
        self.settle()
        self.assert_check_names("copyedit.md")

    def test_exactly_six_lines_passes(self) -> None:
        self.write_copyedit(self.SIX)
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_writing_more_is_not_rewarded(self) -> None:
        """写成检查报告不加分——不然下一轮就有人为了显得认真而灌水。"""
        self.write_copyedit(self.SIX + "另外还查了一遍标题。\n")
        self.init_audit()
        self.settle()
        self.assert_check_names("恰好 6 行")

    def test_blank_lines_do_not_count(self) -> None:
        self.write_copyedit(self.SIX.replace("\n", "\n\n"))
        self.init_audit()
        self.settle()
        self.assertEqual(0, self.check_output()[0])


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
        head = "### E. 材料清单\n\n"
        start = text.index(head) + len(head)
        self.story_path.write_text(text[:start] + body, encoding="utf-8")

    # ---- lint 1：图前承接 + 图题形态 ----

    def test_an_image_right_after_a_heading_is_named(self) -> None:
        self.put_features("### 6.1 提交与回执\n\n" + self.IMAGE + "\n")
        self.init_audit()
        self.settle()
        self.assert_check_names("图前一句承接")

    def test_an_image_with_a_lead_sentence_passes(self) -> None:
        self.put_features("### 6.1 提交与回执\n\n图 1 是提交入口的位置：\n\n"
                          + self.IMAGE + "\n")
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertNotIn("图前一句承接", out)
        self.assertNotIn("图题", out)

    # ---- lint 2：材料清单的行形态 ----

    def test_a_material_list_written_as_a_table_is_named(self) -> None:
        self.put_materials("| 材料 | 贡献 |\n|---|---|\n| 甲需求 PRD | 状态取值 |\n")
        self.init_audit()
        self.settle()
        self.assert_check_names("材料清单用列表不用表")

    def test_a_material_row_without_a_link_is_named(self) -> None:
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。\n")
        self.init_audit()
        self.settle()
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
        self.settle()
        out = self.assert_check_names("链接点不开")
        self.assertIn("RR/prd.md", out, "报错要把点不开的那个目标给出来")

    def test_a_link_that_resolves_passes(self) -> None:
        """同一份材料写对了相对层级就该过——判的是能不能点开，不是长什么样。"""
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](../RR/prd.md)\n")
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertNotIn("链接点不开", out)

    def test_offline_does_not_judge_whether_the_file_exists(self) -> None:
        """离线不判存在性：那时没有 feature 上下文，基准目录只能靠猜。

        判据一旦开始猜就没法解释也没法回归。金样正是离线跑的——它是独立文件，
        身边没有 RR/ 也没有 AR/，存在性判在那里必然全红。
        """
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](RR/prd.md)\n")
        self.init_audit()
        self.settle()
        proc = subprocess.run(
            ["node", str(BUILD), "check", "--offline", "--story", str(self.story_path),
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertNotIn("链接点不开", (proc.stderr or "") + (proc.stdout or ""))

    def test_the_material_link_is_the_one_place_a_repo_path_may_appear(self) -> None:
        """豁免只到这一节的链接语法：正文里的仓内路径照拦。"""
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(0, code, out)          # 夹具的材料清单本来就带链接

        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n实现见 doc/features/AR90001/spec/spec.md。")
        self.assert_check_names("仓内路径")


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

    def test_the_appendix_keeps_its_letters(self) -> None:
        """附录小节用字母序号，机器不动它——那是附录判据管的地方。"""
        text = self.number()
        self.assertIn("### A. 接口", text)

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
            "import { renumberStory } from './doc/extensions/skills/story/scripts/headings.mjs';"
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
    """六件小账里能机器判的那几条：表行查重、澄清正文禁标题行、装置词表。"""

    def decisions(self) -> dict:
        return json.loads((self.src / "decisions.json").read_text(encoding="utf-8"))

    def write_decisions(self, data: dict) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_two_identical_rows_in_one_table_are_named(self) -> None:
        """同一张表里两行逐字相同——段落查重看不到表行这一面。"""
        self.init_audit()
        self.settle()
        text = self.story()
        row = next(l for l in text.split("\n")
                   if l.strip().startswith("|") and "|---" not in l
                   and len(l.strip()) > 20)
        self.rewrite_story(row, row + "\n" + row)
        out = self.assert_check_names("表里重复的行")
        self.assertIn("逐字相同", out)

    def test_a_repeated_header_across_tables_is_not_named(self) -> None:
        """多张表共用同一个表头是形态要求（每个小节一张表，表头由数据锁死）——
        跨表比对会把这种正确形态判成重复，所以只在一张表内比。"""
        self.init_audit()
        self.settle()
        text = self.story()
        head = next(i for i, l in enumerate(text.split("\n"))
                    if l.strip().startswith("|"))
        rows = text.split("\n")
        table = rows[head:head + 3]
        self.rewrite_story("\n".join(table), "\n".join(table) + "\n\n" + "\n".join(table))
        _, out = self.check_output()
        self.assertNotIn("表里重复的行", out)

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
        self.settle()
        self.write_decisions({"decisions": [
            self.a_decision("### 背景\n\n本条说明这件事的来龙去脉。")]})
        out = self.assert_check_names("的澄清正文里有标题行")
        self.assertIn("加粗段首", out)

    def test_a_bold_lead_in_the_clarification_passes(self) -> None:
        """反面：加粗段首是定稿形态，不该被拦。"""
        self.init_audit()
        self.settle()
        self.write_decisions({"decisions": [
            self.a_decision("**背景**：本条说明这件事的来龙去脉。")]})
        _, out = self.check_output()
        self.assertNotIn("的澄清正文里有标题行", out)

    def test_the_two_new_harness_words_are_registered(self) -> None:
        """装置词表补两词——它们是造这份文档的装置说的话，不是需求事实。

        词表是合同数据（按 kind 带作用域），不写死在脚本里。
        """
        contract = json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))
        terms = contract["language_redline"]["harness_terms"]
        for word in ("import_sources", "人话"):
            self.assertIn(word, terms)

    def test_a_harness_word_in_the_appendix_is_still_named(self) -> None:
        """装置词的作用域是全篇——换个位置它仍然不是需求事实。"""
        self.init_audit()
        self.settle()
        appendix = _appendix_title()
        text = self.story()
        marker = f"## {appendix}"
        hit = next((l for l in text.split("\n") if l.strip().startswith(marker)), None)
        if hit is None:
            self.skipTest("夹具里没有附录章")
        self.rewrite_story(hit, hit + "\n\n这一节按 import_sources 的导入结果整理。")
        self.assert_check_names("import_sources")


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

    def test_the_adapt_work_dir_carries_the_package_version(self) -> None:
        """工作目录带版本、点开头——两个版本的工作件互不覆盖，且一眼看出是临时件。"""
        scan = (self.EXT / "skills/story-adaptation/scripts/adapt-scan.mjs").read_text(
            encoding="utf-8")
        self.assertIn(".adapt-${PKG_VERSION}", scan)
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("doc/extensions/.adapt-*/", gitignore)

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
        「这轮该不该升版本」。版本不升的代价不是洁癖问题——`adapt` 判态直接比它，
        版本相同判「重适配」，而重适配**不执行机制行**，于是机制改动一条都装不进
        目标工程。红了就一起改，别只把断言改绿。
        """
        manifest = (self.EXT / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "1.3.0"', manifest)


class TestLedgerFrozenAfterRegistration(StoryBuildCase):
    """成文登记之后台账随稿冻结——story.md 冻了，账本也得冻。

    实测一轮：登记 00:04，spec 阶段 00:20 又跑了一次 init，登记那一刻的落点账被冲掉。
    产物还在，它据以成文的依据换了一批，谁也看不出来。
    """

    FROZEN = ("source-units.json", "audit.json", "decisions.json",
              "story-verdicts.md", "copyedit.md")

    def ledger_digest(self, name: str) -> str | None:
        path = self.src / name
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def register(self) -> None:
        """把成文态登记写进流程契约——含登记那一刻的台账指纹。"""
        flow = {
            "schema": 3, "feature": FEATURE, "status": "story_written",
            "rounds": [{"round": 1, "gates": []}],
            "story_src_digests": {n: self.ledger_digest(n) for n in self.FROZEN},
        }
        (self.root / "doc" / "features" / FEATURE / "AR" / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_init_is_refused_after_registration(self) -> None:
        self.init_audit()
        self.settle()
        self.register()
        proc = self.run_build("init")
        self.assertEqual(1, proc.returncode, "登记之后 init 还能跑，台账就没冻住")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("台账随稿冻结", out)
        self.assertNotIn("撤登记", out, "登记单向，报错不该指向一个不存在的动作")

    def test_audit_is_refused_after_registration(self) -> None:
        """audit 也要拒：它会写落点账，只拦 init 等于只冻了一半。"""
        self.init_audit()
        self.settle()
        self.register()
        proc = self.run_build("audit")
        self.assertEqual(1, proc.returncode)
        self.assertIn("台账随稿冻结", (proc.stderr or "") + (proc.stdout or ""))

    def test_a_changed_ledger_is_named_by_check(self) -> None:
        """拒绝两条命令挡不住有人直接改文件——指纹核对补上那一面。"""
        self.init_audit()
        self.settle()
        self.register()
        audit = self.audit
        audit["records"].append({"key": "PRD:999:deadbeef", "at": "功能说明", "by": "author"})
        self.write_audit(audit)
        out = self.assert_check_names("与成文登记时的台账对不上")
        self.assertIn("audit.json", out)

    def test_nothing_changes_before_registration(self) -> None:
        """登记之前一切照旧——冻结只在定稿之后生效。"""
        self.init_audit()
        self.settle()
        for command in ("init", "audit"):
            self.assertEqual(0, self.run_build(command).returncode,
                             f"没登记就拦 {command}，那是把正常流程拦了")

    def test_material_drift_after_registration_is_only_noted(self) -> None:
        """定稿之后材料继续演化是常态（评审回稿就在修订规格件）——记一笔，不拦。

        此前这里指路「重跑 init」，而 init 在冻结之后会拒绝执行；两条一起，
        人就被锁在中间，而且没有任何出口。
        """
        self.init_audit()
        self.settle()
        self.register()
        prd = self.root / "doc" / "features" / FEATURE / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n评审回稿补的一句话。\n",
                       encoding="utf-8")
        code, out = self.check_output()
        self.assertEqual(0, code, f"材料演化不该拦住定稿产物：{out}")
        self.assertIn("定稿那一刻的快照", out)
        self.assertNotIn("重跑 init", out)


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
        rows = [{
            "id": "submit-boundary", "status": "settled",
            "title": "提交入口与补卡由两张开发单分别承接",
            "clarification": "**要定的事**：提交与补卡要不要放在同一张单里做。\n\n"
                             "**根据**：上游已经拆成两张开发单。\n\n"
                             "**结论与影响**：本单只做提交与回执展示，验收不含补卡。",
            "decider": "需求负责人",
        }] + (extra or [])
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": rows}, ensure_ascii=False), encoding="utf-8")


class TestReviewComesAfterTheStory(Step8Case):
    """review 是判断的台账，而判断在成文过程中还会长出来。

    实测形态是「story 还没写完，review 先出来了」——那不是模型跑偏，
    是作业顺序把渲染排在了成文前面。顺序本身因此要成为一条判据。
    """

    def test_build_refuses_before_the_story_is_written(self) -> None:
        self.write_decision()
        self.story_path.write_text("# 交通卡紧急挂失（AR90001）\n", encoding="utf-8")
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
            "审核结果：\n\n<!-- decision: submit-boundary -->",
            "审核结果：范围要含补卡入口。\n\n<!-- decision: submit-boundary -->")
        self.assertNotEqual(text, filled, "夹具变了，用例要跟着改")
        self.review_path.write_text(filled, encoding="utf-8")

        self.write_decision(extra=[{
            "id": "receipt-timeout", "status": "open",
            "title": "回执超时后由谁重试",
            "clarification": "**要定的事**：写第五章时发现材料没说超时之后谁重试。\n\n"
                             "**根据**：PRD 只写了超时按未提交处理。\n\n"
                             "**结论与影响**：待评审人定。",
            "decider": "需求负责人",
        }])
        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("回执超时后由谁重试", again, "成文中新登记的判断没进 review")
        self.assertIn("审核结果：范围要含补卡入口。", again, "人填的表态被重渲染冲掉了")

    def test_the_machine_zone_cannot_be_maintained_by_hand(self) -> None:
        """机器区改了也会被重算回来——它不是第二份真源，改它等于白改。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.review_path.write_text(
            text.replace("提交入口与补卡由两张开发单分别承接", "手改过的标题"),
            encoding="utf-8")
        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("提交入口与补卡由两张开发单分别承接", again)
        self.assertNotIn("手改过的标题", again, "机器区被人维护成了第二份真源")


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

    def test_the_same_image_under_two_paths_is_named(self) -> None:
        """同一张图改个名复制进归档目录——只比文件名的判据拦不住这一种。"""
        copy = self.feature_root() / "AR" / "assets" / "签约页.png"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(self.material_image.read_bytes())
        self.put_image_ref("../assets/上游文档/image1.png", "assets/签约页.png")
        self.assert_check_names("同一张图被两个路径引用")

    def test_a_stranger_in_the_archive_dir_is_named(self) -> None:
        """归档目录只放材料里那些图的副本，放别的等于凭空多出一张没有出处的图。"""
        stray = self.feature_root() / "AR" / "assets" / "自己画的.png"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"SOMETHINGELSE")
        self.put_image_ref("assets/自己画的.png")
        self.assert_check_names("不是材料里任何一张图的副本")

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
        self.assertNotIn("列了不是材料的东西", out)

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
        self.assert_check_names("列了不是材料的东西")

    def test_without_a_manifest_the_check_says_it_did_not_run(self) -> None:
        (self.src / "materials.json").unlink()
        self.rewrite_story(self.LISTED, "- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                                        "原文：[别的](../AR/story-src/decisions.json)")
        _, out = self.check_output()
        self.assertIn("的集合判据未执行", out)

    def test_one_wrong_row_is_reported_once(self) -> None:
        """有清单时按清单逐份对，目录白名单那条粗判让位——同一行报两遍，读的人以为是两个问题。

        图片文件单列成行同时踩两条：它所在的目录不在白名单里，它本身也不是「一份材料」。
        """
        image = self.feature_root() / "assets" / "入口原型说明" / "image1.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"PNGDATA1")
        self.round_now()
        self.rewrite_story(self.LISTED, self.LISTED
                           + "\n- 入口原型图：原文：[图 1](../assets/入口原型说明/image1.png)")
        _, out = self.check_output()
        hits = [line for line in out.splitlines() if "assets/入口原型说明/image1.png" in line]
        self.assertEqual(1, len(hits), "同一行被报了不止一次：%s" % hits)
        self.assertIn("列了不是材料的东西", hits[0])


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
            self.assertEqual(0, self.put_chapter(title, f"第 {i + 1} 章的正文。\n").returncode)
        done = {t: self.chapter_text(t) for t in titles[:3]}
        proc = self.put_chapter(titles[3], "第 4 章的正文。\n")
        self.assertEqual(0, proc.returncode)
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("还剩 6 章待写", out, "剩几章要报出来，恢复时才知道从哪续")
        for title, before in done.items():
            with self.subTest(chapter=title):
                self.assertEqual(before, self.chapter_text(title), "已完成的章被动过了")

    def test_a_copyedit_pass_replaces_one_chapter_only(self) -> None:
        """统稿夹具：十章写完之后只改第 5 章，其余九章字节相同。"""
        titles = self.titles()
        for i, title in enumerate(titles):
            self.assertEqual(0, self.put_chapter(title, f"第 {i + 1} 章的正文。\n").returncode)
        before = {t: self.chapter_text(t) for t in titles}
        self.assertEqual(0, self.put_chapter(titles[4], "统稿之后的第 5 章。\n").returncode)
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


if __name__ == "__main__":
    unittest.main()
