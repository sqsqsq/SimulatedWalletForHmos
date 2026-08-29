"""`story-build` 三个命令的单元断言——init 派生什么、audit 记什么、check 拦什么。

台账（`check_failure_modes.py`）判的是**形态回不回来**：一个已知会犯的错，机制现在抓不抓得住。
本文件判的是**判据本身的边界**：同一条判据，改一个字符就该翻面的那些地方。两者都要有，
因为台账只覆盖曾经真实发生过的错，而边界是它没走到的地方。

夹具借用 `R01-verdict-echo/good`——它是一份最小但完整的工作区（材料 + story + 激活清单 +
决策件）。每个用例在**副本**上跑：这几条命令会写 `source-units.json` / `audit.json`，
在夹具原地跑会把它写脏，且上一个用例的产物会影响下一个。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "F1"

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

    def settle(self) -> list[str]:
        """把机器定不了落点的单元交给作者并配上裁决——夹具的基线态。

        `check` 要求三态之一齐备：机器定不了的那些，正式链路上由 S5 裁决者处置。
        用例要断言「某一条判据翻面」，基线就得是通过态，否则测的是别的问题。
        """
        data = self.audit
        keys = []
        for record in data["records"]:
            if any(record.get(k) for k in ("at", "covered_by", "machine_facing")):
                continue
            record["at"], record["by"] = "功能说明", "author"
            keys.append(record["key"])
        self.write_audit(data)
        if keys:
            self.write_verdicts([(k, "讲清", QUOTE) for k in keys])
        return keys

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


class TestMachinePlacement(StoryBuildCase):
    """KR-1a：机器落点每条都能核回 story 正文，且不沿用上一次的结果。"""

    def test_machine_records_are_backed_by_the_chapter_text(self) -> None:
        self.init_audit()
        by_key = {u["key"]: u for u in self.units}
        chapters = {}
        title = None
        for line in self.story().split("\n"):
            if line.startswith("## "):
                title = line[3:].strip()
                chapters[title] = []
            elif title:
                chapters[title].append(line)
        machine = [r for r in self.audit["records"] if r.get("by") == "machine"]
        self.assertTrue(machine, "夹具里应当有机器定位的单元")
        for record in machine:
            body = "\n".join(chapters[record["at"]])
            unit = by_key[record["key"]]
            tokens = unit.get("tokens") or []
            hit = any(t in body for t in tokens) or unit["text"][:8] in body
            self.assertTrue(hit, f"{record['key']} 标在「{record['at']}」但那一章里核不到")

    def test_rerun_recomputes_machine_and_keeps_author(self) -> None:
        self.init_audit()
        before = {r["key"]: r.get("at") for r in self.audit["records"] if r.get("by") == "machine"}
        data = self.audit
        moved = next(r for r in data["records"] if r.get("by") == "machine")
        moved["at"] = "交付与上线"          # 机器落点被改脏
        authored = next(r for r in data["records"]
                        if not any(r.get(k) for k in ("at", "covered_by", "machine_facing")))
        authored["at"], authored["by"] = "术语", "author"   # 机器定不了、作者接手的那一条
        self.write_audit(data)

        self.assertEqual(self.run_build("audit").returncode, 0)
        records = {r["key"]: r for r in self.audit["records"]}
        self.assertEqual(records[moved["key"]].get("at"), before[moved["key"]],
                         "机器落点应当每次重算——上一次的结果不作数")
        self.assertEqual(records[authored["key"]].get("at"), "术语",
                         "机器定不了的那条，作者落点应当保留，交 S5 裁决")
        self.assertEqual(records[authored["key"]].get("by"), "author")


class TestHardFactConservation(StoryBuildCase):
    """守恒只守硬事实：机器给落点的依据只有 token，纯中文叙事一律交作者。

    上一版还有一条正文片段兜底：无 token 的单元，正文里找得到 ≥8 字的片段就算落点。
    它让守恒同时要求「改写成人话」与「逐字保留原句」——两条互斥，把材料整段抄进
    一个倾倒区是唯一同时满足的解，而门禁会判它通过（实测 267 个单元里 224 条塌进去）。
    """

    def test_units_without_tokens_are_never_machine_placed(self) -> None:
        self.init_audit()
        by_key = {u["key"]: u for u in self.units}
        for record in self.audit["records"]:
            if record.get("by") != "machine":
                continue
            unit = by_key[record["key"]]
            self.assertTrue(unit.get("tokens"),
                            f"{record['key']} 没有 token 却被机器定了落点——片段通道回来了")

    def test_a_paraphrased_chinese_unit_stays_open_for_the_author(self) -> None:
        """材料里的中文句子被逐字抄进 story 时，机器也不认它——那是裁决者的活。"""
        self.init_audit()
        by_key = {u["key"]: u for u in self.units}
        open_units = [by_key[r["key"]] for r in self.audit["records"]
                      if not any(r.get(k) for k in ("at", "covered_by", "machine_facing"))]
        self.assertTrue(open_units, "夹具里应当有机器定不了的纯中文单元")
        for unit in open_units:
            self.assertFalse(unit.get("tokens"),
                             f"{unit['key']} 有 token 却没被机器定位——那是另一类失败")

    def test_the_word_fragment_channel_is_gone_from_the_source(self) -> None:
        """通道的退场要在代码里也成立——留着函数没人调，下一轮就会有人接回去。"""
        source = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("contentFragments", source)


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


class TestAuthorPlacement(StoryBuildCase):
    """KR-1b：作者落点的三种坏形态，各自点名。"""

    def test_author_chapter_must_be_in_the_contract(self) -> None:
        self.init_audit()
        data = self.audit
        data["records"][0]["at"] = CHAPTER_OUT_OF_CONTRACT
        data["records"][0]["by"] = "author"
        self.write_audit(data)
        self.assert_check_names(f"的 at「{CHAPTER_OUT_OF_CONTRACT}」不是合同里的章节标题")

    def test_all_three_states_empty_is_named(self) -> None:
        self.init_audit()
        data = self.audit
        for key in ("at", "by", "covered_by", "machine_facing"):
            data["records"][0].pop(key, None)
        self.write_audit(data)
        self.assert_check_names("没有任何落点（三态皆空）")

    def test_author_cannot_declare_machine_facing(self) -> None:
        self.init_audit()
        data = self.audit
        record = data["records"][0]
        record.pop("at", None)
        record.pop("by", None)
        record["machine_facing"] = True
        self.write_audit(data)
        self.assert_check_names("被标成 machine_facing，但枚举器没这么判")


class TestVerdicts(StoryBuildCase):
    """KR-1c：S5 裁决的核实——缺行、非法取值、短引文、回声、未讲清。"""

    def test_missing_row_is_named(self) -> None:
        self.init_audit()
        self.hand_to_author()
        self.write_verdicts([])
        self.assert_check_names("裁决表里没有")

    def test_verdict_word_is_closed(self) -> None:
        self.init_audit()
        keys = self.hand_to_author()
        self.write_verdicts([(keys[0], "基本讲了", QUOTE)])
        self.assert_check_names("不是 讲清 / 未讲清 之一")

    def test_quote_below_floor_is_named(self) -> None:
        self.init_audit()
        keys = self.hand_to_author()
        self.write_verdicts([(keys[0], "讲清", "界面停在等待态")])
        self.assert_check_names("的引文只有")

    def test_quote_must_come_from_the_chapter(self) -> None:
        self.init_audit()
        keys = self.hand_to_author()
        self.write_verdicts([(keys[0], "讲清", "这句话在 story 的那一章里根本检索不到")])
        self.assert_check_names("在它落点那一章里检索不到")

    def test_echo_of_the_source_unit_is_rejected(self) -> None:
        """引文抄的是材料原文——它证明「材料这么说」，不是「story 讲清了」。"""
        self.init_audit()
        keys = self.hand_to_author()
        unit = next(u for u in self.units if u["key"] == keys[0])
        echo = unit["text"][:20]
        self.rewrite_story(QUOTE, f"{QUOTE}。{echo}")
        self.write_verdicts([(keys[0], "讲清", echo)])
        self.assert_check_names("回声")

    def test_not_covered_verdict_fails_the_check(self) -> None:
        self.init_audit()
        keys = self.hand_to_author()
        self.write_verdicts([(keys[0], "未讲清", QUOTE)])
        self.assert_check_names("被裁「未讲清」")

    def test_author_placement_without_verdict_file_is_named(self) -> None:
        self.init_audit()
        self.hand_to_author()
        (self.src / "story-verdicts.md").unlink(missing_ok=True)
        self.assert_check_names("需要裁决者逐条裁")


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

    def test_entity_term_absent_from_story_is_named(self) -> None:
        self.init_audit()
        self.write_spec("受理单号")
        self.assert_check_names("受理单号")

    def test_entity_term_present_passes(self) -> None:
        self.init_audit()
        self.settle()
        self.write_spec("等待态")          # story 的「功能说明」章里有这个词
        code, out = self.check_output()
        self.assertEqual(code, 0, out)

    def test_repo_path_in_story_is_named(self) -> None:
        self.init_audit()
        self.rewrite_story("本需求不涉及。\n\n## 术语",
                           "详见 doc/features/F1/AR/design.md。\n\n## 术语")
        self.assert_check_names("仓内路径")


if __name__ == "__main__":
    unittest.main()
