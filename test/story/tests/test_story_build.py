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


class TestDecisionUnits(StoryBuildCase):
    """决策登记走独立派生通道：取舍理由在材料里没有，它是起草时判出来的。"""

    DECISIONS = {
        "decisions": [
            {"id": "DEC-001", "status": "settled",
             "title": "挂失结果以卡片服务的回执为准",
             "clarification": "**要定的事**：挂失办没办成，以哪一侧的说法为准。\n\n"
                              "**根据**：本端只有请求态，判不了卡是否真的停用。\n\n"
                              "**结论与影响**：以卡片服务的回执为准，页面照回执显示。",
             "decider": "需求负责人"},
            {"id": "DEC-002", "status": "settled",
             "title": "同卡同状态的重复提交按一次算",
             "clarification": "**要定的事**：同一张卡短时间内重复提交怎么处理。\n\n"
                              "**根据**：重复提交只会让用户以为办了两次。\n\n"
                              "**结论与影响**：按一次算，第二次直接回到等待态。",
             "decider": "需求负责人"},
            {"id": "DEC-003", "status": "open",
             "title": "线下渠道的入口这轮收不收",
             "clarification": "**要定的事**：线下渠道的入口要不要一起收进本单。\n\n"
                              "**可选的做法**：1. 本单先不收，等渠道方给时间表；"
                              "2. 一起收，范围扩到渠道侧。\n\n"
                              "**建议**：按第 1 种做。",
             "decider": "产品负责人"},
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

    def test_a_settled_decision_without_a_landing_is_named(self) -> None:
        self.write_decisions()
        self.init_audit()
        self.settle()
        data = self.audit
        for record in data["records"]:
            if record["key"] == "DECISION:DEC-002":
                record.pop("at", None)
                record.pop("by", None)
        self.write_audit(data)
        out = self.assert_check_names("三态皆空")
        self.assertIn("DECISION:DEC-002", out)

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
             "decider": "需求负责人"}])
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


if __name__ == "__main__":
    unittest.main()
