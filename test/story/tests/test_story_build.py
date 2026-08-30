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
FEATURE = "AR90001"

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
        for record in data["records"]:
            if any(record.get(k) for k in ("at", "covered_by", "machine_facing")):
                continue
            kind = by_key.get(record["key"], {}).get("kind")
            at = with_table if (kind == "table_row" and with_table) else "功能说明"
            record["at"], record["by"] = at, "author"
            body = bodies.get(at, "")
            unit_text = by_key.get(record["key"], {}).get("text") or ""
            quote = QUOTE if (QUOTE in body and QUOTE not in unit_text) else ""
            if not quote:
                for line in body.split("\n"):
                    cand = line.strip()
                    if cand.startswith("|"):
                        cells = [c.strip() for c in cand.strip("|").split("|")]
                        cells = [c for c in cells if c and not set(c) <= set("-: ")]
                        if not cells:
                            continue
                        cand = max(cells, key=len)
                    if len(cand) >= 14 and cand not in unit_text and not cand.startswith("#"):
                        quote = cand[:60]
                        break
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


class TestAllocationDomain(StoryBuildCase):
    """分配域：机器能定的不经模型；模型分的那些不许倒进附录。"""

    def test_narrative_unit_placed_in_the_appendix_is_named(self) -> None:
        """业务叙述分到附录 = 它从阅读路径上消失了，报错要说清该往哪儿放。"""
        self.init_audit()
        data = self.audit
        keys = []
        for record in data["records"]:
            if not any(record.get(k) for k in ("at", "covered_by", "machine_facing")):
                record["at"], record["by"] = "附录", "author"
                keys.append(record["key"])
        self.assertTrue(keys, "夹具里应当有交给作者的纯中文单元")
        self.write_audit(data)
        self.write_verdicts([(k, "讲清", QUOTE) for k in keys])
        out = self.assert_check_names("业务叙述不落在那里")
        self.assertIn("读者在哪一章想知道它", out)

    def test_the_same_unit_in_a_body_chapter_passes(self) -> None:
        """同一条放进正文章就该过——判的是位置，不是这条单元本身。"""
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(code, 0, out)

    def test_engineering_contract_rows_never_reach_the_author(self) -> None:
        """合同声明的技术契约小节由机器直接归附录，不进模型的分配任务。

        落点对那些行都一样（接口表、数据配置事件表），让模型逐条重想是苦役——
        而苦役正是它开始糊弄的地方。
        """
        spec_dir = self.root / "doc" / "features" / FEATURE / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text(
            "# 甲需求 规格\n\n## 9. 技术契约\n\n"
            "| 类型 | 标识 | 约定 |\n|---|---|---|\n"
            "| 接口 | queryOrderState | 查订单当前状态 |\n"
            "| 存储键 | order_draft_key | 草稿本地留存 |\n",
            encoding="utf-8")
        self.init_audit()
        by_key = {u["key"]: u for u in self.units}
        bound = [r for r in self.audit["records"]
                 if by_key.get(r["key"], {}).get("doc") == "SPEC"
                 and str(by_key[r["key"]].get("section") or "").startswith("9.")]
        self.assertTrue(bound, "夹具应当切出技术契约小节的单元")
        for record in bound:
            self.assertEqual("附录", record.get("at"))
            self.assertEqual("machine", record.get("by"))


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
        # 规格件要在枚举之前就位——枚举之后再出现，先撞上的是材料漂移那条判据
        self.write_spec("受理单号")
        self.init_audit()
        self.assert_check_names("受理单号")

    def test_entity_term_present_passes(self) -> None:
        self.write_spec("等待态")          # story 的「功能说明」章里有这个词
        # 术语表的行是表行单元：它们的落点该是有表的那一章，摊成散文会被 ④ 判降级
        self.rewrite_story(
            "## 术语\n\n本需求不涉及。",
            "## 术语\n\n| 术语 | 在本需求里的意思 |\n|---|---|\n"
            "| 等待态 | 已提交但回执还没到的页面状态 |")
        self.init_audit()
        self.settle()
        code, out = self.check_output()
        self.assertEqual(code, 0, out)

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

    def test_numeric_threshold_gets_a_form_hint(self) -> None:
        self.init_audit()
        self.settle()
        self.drop_from_appendix(" 超时 3秒 后")
        out = self.assert_check_names("阈值")
        self.assertIn("随它所属的那句叙述或验收行", out)
        self.assertNotIn("找不到：", out)

    def test_identifier_is_pointed_at_the_appendix_tables(self) -> None:
        self.init_audit()
        self.settle()
        self.drop_from_appendix("createBusinessOrder")
        code, out = self.check_output()
        self.assertEqual(1, code, out)
        self.assertNotIn("找不到：", out)

    def test_the_bare_token_list_style_is_gone_from_the_source(self) -> None:
        """禁止样式在源码里也不该留——留着下一轮就会有人接回去。"""
        source = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("但那一章里找不到", source)


REVIEW_HUMAN_ZONE = """#### 审核结果（由评审人填写）

- [ ] **同意当前建议**
- [ ] **有其他意见，需要修改**
  - 修改意见：
- [ ] **暂缓**
  - 暂缓原因：
"""


class TestReviewForm(StoryBuildCase):
    """评审表单只剩三态勾选与一行说明——需要说明书就是设计错了。

    曾经这里还有暂缓责任人、完成期限、是否阻塞执行、后续动作、确认人、确认日期、
    确认依据七个字段。评审人打开它先要读一遍字段表，而其中六格他答不上来
    （责任人和期限是排期的事，确认依据是审计的事）。答不上来的格子只会被跳过或胡填。
    """

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def write_decision(self) -> None:
        (self.src / "decisions.json").write_text(json.dumps({
            "scanned_categories": {},
            "decisions": [{
                "id": "submit-boundary", "question": "提交入口的责任边界",
                "proposal": "本单只做提交与回执展示", "rationale": "补卡另有开发单承接",
                "impact": ["需求范围"], "source": "上游产品文档", "decider": "需求负责人",
            }],
        }, ensure_ascii=False), encoding="utf-8")

    def test_rendered_form_is_exactly_three_states(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.assertIn(REVIEW_HUMAN_ZONE, text)
        for gone in ("暂缓责任人", "完成期限", "是否阻塞执行", "后续动作",
                     "确认人", "确认日期", "确认依据", "**状态**"):
            self.assertNotIn(gone, text, f"「{gone}」不该再出现在评审记录里")

    def test_filled_human_zone_survives_a_rerender(self) -> None:
        """人填过的内容一个字节都不能动——重算它等于把做完的决定推回去一次。

        连**旧形态**的人工区也要保住：字段是被裁掉了，人当时写在里面的话不是。
        """
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        filled = text.replace("- [ ] **有其他意见，需要修改**\n  - 修改意见：",
                              "- [x] **有其他意见，需要修改**\n  - 修改意见：范围要含补卡入口")
        filled = filled.replace("<!-- decision: submit-boundary -->",
                                "**确认人**：某评审人\n\n<!-- decision: submit-boundary -->")
        self.review_path.write_text(filled, encoding="utf-8")

        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("修改意见：范围要含补卡入口", again)
        self.assertIn("**确认人**：某评审人", again, "旧形态里人写过的字也要保住")

    def test_legacy_fields_in_the_review_are_named(self) -> None:
        """人工区之外又长回签署字段与状态行时，check 要点名。"""
        self.init_audit()
        self.settle()
        self.review_path.write_text(
            "# 评审记录\n\n### 提交入口的责任边界\n\n"
            "#### 审核结果（由评审人填写）\n\n- [ ] **同意当前建议**\n\n"
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


class TestMachineFacingColumns(StoryBuildCase):
    """机器面列**连正文一起排除**：模型读到的就是单元正文，只免 token 义务断不了照抄。"""

    def _rows_of(self, table: str) -> list[dict]:
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.write_text("# " + FEATURE + " 规格\n\n## 0. 术语映射表\n\n" + table,
                        encoding="utf-8")
        self.assertEqual(0, self.run_build("init").returncode)
        return [u for u in self.units if u["doc"] == "SPEC" and u["kind"] == "table_row"]

    def test_machine_column_text_never_reaches_the_unit(self) -> None:
        rows = self._rows_of(
            "| 原始术语 | 权威模块 | 在本需求中的含义 |\n|---|---|---|\n"
            "| 挂失 | WalletCardManager | 让原卡不能再被使用 |\n")
        self.assertTrue(rows, "术语映射表该切出行单元")
        row = rows[0]
        self.assertNotIn("WalletCardManager", row["text"],
                         "机器面列还留在单元正文里，模型照抄它就是照抄类名")
        self.assertIn("让原卡不能再被使用", row["text"], "同一行的业务列还要守恒")

    def test_a_row_of_only_machine_columns_keeps_its_text_for_diagnosis(self) -> None:
        rows = self._rows_of(
            "| 权威模块 | 代码现状 |\n|---|---|\n"
            "| WalletCardManager | 检索挂失封装于本模块零命中 |\n")
        self.assertTrue(rows)
        self.assertTrue(rows[0]["machine_facing"], "整行都是机器面列，这一行整行不守恒")
        self.assertEqual([], rows[0]["tokens"])


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


if __name__ == "__main__":
    unittest.main()
