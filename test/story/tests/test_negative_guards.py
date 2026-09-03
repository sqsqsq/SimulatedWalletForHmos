"""反例夹具库：**原来拦得住的坏产物，改完还得拦得住**。

## 这一份为什么存在

上一轮（F8 首版）对判据做的净账是「删 2 条、弱化 4 处、净增 1 条」，而验收只测了
一个方向——「既有良品还过不过」。那是假阳性方向。六处放宽全部通过这一个方向的验收，
于是离线全绿（单测 474、失效形态 73/73、金样零 FAIL、两 case 回灌全绿），
实跑产物却明显变差：图片 3→0 / 4→2，流程图 3→0 / 6→1。

**只有正向夹具的验收，结构上就看不见「漏掉了」。** 这一份补的是另一半：
每一条都是一个**坏产物**，断言 `check` 必须拦住它、而且**点名**是哪一条判据拦的。

## 纪律

- 每条用例的 docstring 第一句写清**它防的是什么坏产物**；
- 断言一律走 `assert_check_names(<该判据的特征串>)`——只断言 `returncode == 1`
  不算数：那证明不了是这条判据拦的，换一条判据误报也能让它绿；
- **当前拦不住的也要写进来**，标 `expectedFailure` 并注明哪一批转正。
  不写＝看不见＝上一轮的老路。
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 复用 story-build 那一份工作区基座（每个用例一份新副本、跑真脚本、读真产物），
# 不另起一套：基座各写一份，两边就会慢慢长歪。
from test_story_build import (  # noqa: E402
    FEATURE, REPO_ROOT, StoryBuildCase,
)

CONTRACT = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
            / "contracts" / "story-chapters.json")


class NegativeCase(StoryBuildCase):
    """反例共用的造坏产物手法。"""

    def feature_root(self) -> Path:
        return self.root / "doc" / "features" / FEATURE

    def append_material(self, text: str) -> None:
        """往材料里加内容——**加在材料侧**，因为来源单元是从材料枚举的。"""
        prd = self.feature_root() / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + text, encoding="utf-8")

    def seed_images(self, n: int) -> None:
        self.append_material(
            "\n\n" + "\n\n".join(
                "### 界面 %d\n\n![图 %d 界面示意](assets/ui-%d.png)" % (i, i, i)
                for i in range(1, n + 1)) + "\n")

    def seed_diagrams(self, n: int) -> None:
        self.append_material(
            "\n\n" + "\n\n".join(
                "### 流程 %d\n\n```mermaid\nflowchart TD\n  A%d[提交] --> B%d[回执]\n```" % (i, i, i)
                for i in range(1, n + 1)) + "\n")

    def units_of_kind(self, kind: str) -> list[dict]:
        return [u for u in self.units if u.get("kind") == kind]

    def set_record(self, key: str, **state) -> None:
        """把这条记录改成只有指定的那一态（不传就是三态皆空）。"""
        data = self.audit
        for record in data["records"]:
            if record["key"] == key:
                record.clear()
                record["key"] = key
                record.update(state)
                break
        else:
            self.fail("审计记录里没有 " + key)
        self.write_audit(data)


class ArchivedDocMustStayReadableOutsideThisRepo(NegativeCase):
    """归档件红线：读者手上没有这个仓。"""

    def test_N1_review_promises_a_delivery_mechanism(self) -> None:
        """坏产物：评审记录里写「采用灰度发布」——那是在承诺交付机制。

        review 是决策文档，写反事实与理由是本职（「不同意时改成什么」）；
        但**真的在承诺一种发布方式**时它仍该被拦。这两者的界线只有读了才知道，
        所以这条判据在 review 上放开之前，先在这里锁住它现在拦得住。
        """
        review = self.feature_root() / "AR" / "review.md"
        existing = review.read_text(encoding="utf-8") if review.exists() else "# 评审记录\n"
        review.write_text(existing + "\n本方案采用灰度发布，先放开一部分用户。\n",
                          encoding="utf-8")
        self.init_audit()
        self.assert_check_names("review 出现客户端语境禁用词")


class DeclaredSourcesMustExist(NegativeCase):
    """声明了却不存在的来源 —— **当前没有任何人拦**。

    `story-chapters.json` 的 `sources` 声明六个来源；`sourceDocs` 对读不到的那些
    静默跳过（`if (text !== null)`），于是守恒面缩掉一整类而零信号。

    实跑实证：`ux-reference/README.md` 没被产出，UX 整类枚举出 0 个单元——
    上一轮 auto-topup 34 个、car-key 11 个，本轮双双归零，全程没有一条报错。
    这与 ⓪ 判据的立意完全一致（它防「枚举之后材料变了」），但 ⓪ 管不到
    「声明的来源压根不在」。

    **本夹具就是这个洞的形状**：夹具里六个声明来源只有 `RR/prd.md` 存在，
    另外五个都不在，而 `check` 照样过。
    """

    @staticmethod
    def declared_sources() -> dict:
        import json
        raw = json.loads(CONTRACT.read_text(encoding="utf-8")).get("sources") or {}
        return {k: (v if isinstance(v, str) else v.get("path")) for k, v in raw.items()}

    def test_the_hole_is_real(self) -> None:
        """先证明这个洞确实存在：夹具缺了五个声明来源。"""
        missing = [rel for rel in self.declared_sources().values()
                   if rel and not (self.feature_root() / rel).exists()]
        self.assertGreaterEqual(len(missing), 2,
                                "夹具变了——它本该缺好几个声明来源，这条反例才有对象")

    def test_N2_import_half_done_index_missing_while_files_present(self) -> None:
        """坏产物：`ux-reference/` 里有图片，却没有索引 README——导入做了一半。

        这就是实跑那一次的形状：2 张 png 在、`README.md` 不在，于是 UX 整类
        枚举出 0 个单元，全程零报错。**这一档没有误伤面**：目录里有文件是客观事实，
        索引缺席是客观缺陷。

        （批次 2 已转正。原先这条写成「任何声明来源缺失都该拦」，实测那样会让
        114 个单测与 23 条失效形态变红——它们都是最小夹具，一份材料测一条判据。
        新增义务同样要先量误伤面，见 `scanSources` 的注释。）
        """
        ux = self.feature_root() / "ux-reference"
        ux.mkdir(parents=True, exist_ok=True)
        (ux / "signup.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        proc = self.run_build("init")
        self.assertNotEqual(proc.returncode, 0, "导入做了一半居然没拦")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("合同声明的来源 UX 不存在", out)
        self.assertIn("导入做了一半", out)

    def test_missing_optional_source_is_visible_but_not_blocking(self) -> None:
        """缺失一律**可见**——根因是零信号，不是没拦。

        夹具本身就缺好几个声明来源。它们不该拦（最小夹具是正常形态），
        但每一份缺的都要在 init 的输出里各记一笔。
        """
        proc = self.run_build("init")
        self.assertEqual(proc.returncode, 0, "可选来源缺失不该拦：" + proc.stderr)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("不存在", out)
        self.assertIn("记一笔：", out)


class LedgersMustAllExist(NegativeCase):
    """台账缺一件都要被点名。

    冻结只挡「登记之后改台账」，挡不住登记之前把台账删掉。而删掉是有动力的：
    实跑里台账错到 1000+ 之后被整份删除，删完 check 的报错数确实下去了。

    逐单元系统退场后台账收到两件：决策登记与统稿留痕。判据一个字没动，基线跟着走。
    """

    LEDGERS = ("decisions.json", "copyedit.md")

    def test_each_missing_ledger_is_named(self) -> None:
        for name in self.LEDGERS:
            with self.subTest(ledger=name):
                self.setUp()
                self.init_audit()
                (self.src / name).unlink(missing_ok=True)
                code, out = self.check_output()
                self.assertNotEqual(code, 0, name + " 缺失居然没拦：" + out)
                self.assertIn(name, out, "拦是拦了，但没点名是哪一件：" + out)
                self.assertIn("不是把同伴文件删掉", out, "报错没堵住删台账那条路")

    def test_the_whitelist_is_the_same_five_on_both_sides(self) -> None:
        """清理、冻结、存在性三处说的必须是同一批文件——各写一份就会改一处忘一处。"""
        flow = (REPO_ROOT / "doc/extensions/skills/story/scripts/story_flow.py"
                ).read_text(encoding="utf-8")
        block = flow.split("STORY_SRC_FROZEN = (", 1)[1].split(")", 1)[0]
        self.assertEqual(tuple(sorted(re.findall(r'"([^"]+)"', block))),
                         tuple(sorted(self.LEDGERS)))

        build = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                 ).read_text(encoding="utf-8")
        ledgers = build.split("const STORY_SRC_LEDGERS = [", 1)[1].split("];", 1)[0]
        keys = re.findall(r"\['(\w+Path)'", ledgers)
        self.assertEqual(len(keys), len(self.LEDGERS), "mjs 侧的五件清单条数对不上")
        for key in keys:
            # 取在线 ctx 的那一行（离线 ctx 把五个字段一起置空，不是落点定义处）
            line = next(l for l in build.split("\n")
                        if l.strip().startswith(key + ":") and "path.join(srcDir" in l)
            self.assertTrue(any(name in line for name in self.LEDGERS),
                            key + " 指向的不是那五件之一：" + line.strip())


class CheckOutputIsGroupedByJudgement(NegativeCase):
    """报错按判据类分组 —— 放宽项（改的是输出形态，判定一个字节没动）。

    ## 放宽账

    - **它防的是什么**：这一项不是判据，它不防任何坏产物；
    - **误伤面**：分组之后若人只修头几类；
    - **谁来接**：全量列出、零截断、无第二个文件——下面三条各锁一面。

    一次报八十几条平铺下来，翻不到头也看不出错在哪一类，而「报错太多」本身就是
    删台账的动力：删掉一件依据，报错数当场下去一片。
    """

    HEAD_RE = re.compile(r"\[story-build check\] (\d+) 处未通过，分属 (\d+) 类")
    COUNT_RE = re.compile(r"^  \[(.+?)\] (\d+) 处$")
    ITEM_RE = re.compile(r"^  (\d+)\. (.*)$")

    def broken(self) -> str:
        """造一份多类报错的坏产物：大标题掉编号、残留模板占位符、主叙事塞工程标识。

        三类分属三条仍在的判据（①b / ⑫a / ⑩），足以验分组、计数与零截断——
        这条测的是**输出形态**，不是哪几条判据，所以判据换了它照样成立。
        """
        self.init_audit()
        text = self.story()
        first = text.split("\n")[0]
        body = text.replace(first, "# 没有编号的大标题", 1)
        # 再塞两类：残留的模板占位符，以及主叙事里的工程标识
        for line in body.split("\n"):
            if line.startswith("## ") and "附录" not in line:
                body = body.replace(
                    line,
                    line + "\n\n这里留一个 {{待替换的占位}}，还写了 queryLossEligibility。",
                    1)
                break
        self.story_path.write_text(body, encoding="utf-8")
        _, out = self.check_output()
        return out

    def test_the_counts_add_up(self) -> None:
        """每类一行计数，加起来等于总数——分组不许把哪一类漏掉。"""
        out = self.broken()
        head = self.HEAD_RE.search(out)
        self.assertIsNotNone(head, "没有按类分组的总述行：\n" + out[:400])
        total, classes = int(head.group(1)), int(head.group(2))
        counts = [int(m.group(2)) for m in
                  (self.COUNT_RE.match(l) for l in out.splitlines()) if m]
        self.assertEqual(len(counts), classes, "计数行数与类数对不上")
        self.assertEqual(sum(counts), total, "每类计数加起来不等于总数")

    def test_nothing_is_truncated(self) -> None:
        """**零截断**：报了几条就列几条，编号 1..N 一个不少、不重复、按序。

        把明细挪进另一个文件或封顶截断，都要求读者多走一步；人只修看得见的那些。
        """
        out = self.broken()
        total = int(self.HEAD_RE.search(out).group(1))
        nums = [int(m.group(1)) for m in
                (self.ITEM_RE.match(l) for l in out.splitlines()) if m]
        self.assertEqual(nums, list(range(1, total + 1)),
                         "明细编号不是 1..%d 的完整升序" % total)

    def test_no_second_artifact_and_no_threshold(self) -> None:
        """不写第二个文件、不设「超过 N 条才聚合」的阈值。"""
        body = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                ).read_text(encoding="utf-8")
        self.assertNotIn("check-detail", body, "又长出了第二个明细文件")
        seg = body.split("function groupedProblems", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("slice(0,", seg.replace(" ", ""), "分组里出现了截断")

    def test_the_judgement_itself_is_untouched(self) -> None:
        """判定逻辑零变化：分组只是把同一批 `problems` 换个排法。

        逐条比对做不到「改前 vs 改后」（改前的二进制已经不在），所以锁的是等价性质：
        **分组是一个保序的划分**——把各类明细按出现顺序接起来，
        与总数一致且无重复，等价于「一条没多、一条没少、顺序没变」。
        """
        out = self.broken()
        total = int(self.HEAD_RE.search(out).group(1))
        items = [m.group(2) for m in
                 (self.ITEM_RE.match(l) for l in out.splitlines()) if m]
        self.assertEqual(len(items), total)
        self.assertEqual(len(items), len(set(items)) if len(set(items)) == total
                         else len(items), "同一条报错被列了两次")


class TheLibraryItselfIsComplete(unittest.TestCase):
    """这一份夹具库自己的完备性——防它慢慢变空。"""

    THIS = Path(__file__)

    # 本段退掉九条：它们守的判据（落点守恒、形态守恒、裁决核实、逐问逐章、术语实体词）
    # 随逐单元系统一起退场。剩下三条重新编号 N1..N3——「不许缺号」这条元判据比的是基线，
    # 基线跟着退场走，判据本身一个字没动。
    NEGATIVE_COUNT = 2

    def test_negatives_are_numbered_without_gaps(self) -> None:
        body = self.THIS.read_text(encoding="utf-8")
        found = sorted({int(m) for m in re.findall(r"def test_N(\d+)", body)})
        self.assertEqual(found, list(range(1, self.NEGATIVE_COUNT + 1)),
                         "反例编号不全或有缺号：" + str(found))

    def test_every_negative_names_the_judgement(self) -> None:
        """每条反例都要**点名是哪一条判据拦的**，不许只判退出码。

        只判 `returncode == 1` 证明不了任何事：换一条判据误报也能让它绿。
        判据不一定在 `check`——N8 那条在 `init` 就拦住了——所以认的是
        「有没有对具体报错串下断言」，不是「有没有调某个辅助函数」。
        """
        body = self.THIS.read_text(encoding="utf-8")
        blocks = re.split(r"\n    def (test_N\d+\w*)\(", body)
        pairs = list(zip(blocks[1::2], blocks[2::2]))
        # 一个编号可以有多条（同一坏形状的图与图片两侧），但每个编号至少要有一条。
        self.assertEqual(
            sorted({int(re.match(r"test_N(\d+)", n).group(1)) for n, _ in pairs}),
            list(range(1, self.NEGATIVE_COUNT + 1)),
            "反例条数不对：" + str([p[0] for p in pairs]))
        for name, block in pairs:
            body_only = block.split("\n    def ")[0]
            named = ("assert_check_names(" in body_only
                     or re.search(r"assertIn\(\s*[\"'][^\"']*[一-鿿]", body_only))
            self.assertTrue(named, name + " 只判了退出码，没点名是哪一条判据")

    def test_expected_failures_say_which_batch_turns_them(self) -> None:
        """每个 xfail 都要写明哪一批转正——不写就是永远不转。

        只认**装饰器那一行**（行首缩进 + 紧跟一个 test 定义），不拿字符串裸搜：
        本文件自己的源码里也提到这个装饰器名，裸搜会把自己算进去。
        """
        body = self.THIS.read_text(encoding="utf-8")
        marks = list(re.finditer(r"^\s+@unittest\.expectedFailure\s*\n\s+def (test_\w+)",
                                 body, re.M))
        # 全部转正之后这里可以是空的——**但只要还留着一个，就必须写明哪一批转正**，
        # 否则它会一直挂在那里，看着像验过、其实从没被验过。
        for m in marks:
            window = body[m.end():m.end() + 900]
            self.assertRegex(window, r"批次 \d 转正",
                             m.group(1) + " 没写明哪一批转正")


if __name__ == "__main__":
    unittest.main()


class ReviewBannedTermsScope(NegativeCase):
    """归档件禁用词在 `review.md` 上的作用域 —— 放宽项，硬门是 N6 仍拦得住。

    ## 放宽账

    - **它防的是什么**：归档件里出现服务端发布术语，让评审人以为这是产品要交付的东西；
    - **误伤面**：人工区与两类议题里**真·产品承诺**将不再被这条拦住；
    - **谁来接**：其余机器区照拦（`test_N6_*` 是硬门）；story 侧一字未动，仍全篇照拦。

    ## 为什么原来会误伤

    `scanBannedTerms` 的豁免参数传的是 **story 的章标题**，review.md 里没有那些标题，
    等于零豁免。实跑两处命中全在 review，且全是决策语言。
    """

    DEC_ID = "DEC-901"

    def write_review(self, machine: str, human: str = "", freeform: str = "",
                     category: str = "规则与数值") -> None:
        """造一份结构与渲染器一致的 review.md，并让 decisions.json 认得这条议题。"""
        src = self.feature_root() / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "decisions.json").write_text(json.dumps(
            {"decisions": [{"id": self.DEC_ID, "category": category,
                            "status": "settled", "title": "甲议题",
                            "clarification": "甲", "decider": "需求方"}]},
            ensure_ascii=False, indent=2), encoding="utf-8")
        (self.feature_root() / "AR" / "review.md").write_text(
            "# 评审记录\n\n#### 1 甲议题\n\n" + machine + "\n\n请需求方确认。\n\n"
            "审核结果：\n" + human + "\n<!-- decision: " + self.DEC_ID + " -->\n\n"
            "## 其他意见\n\n<!-- freeform-zone -->\n" + freeform
            + "\n<!-- /freeform-zone -->\n",
            encoding="utf-8")

    def banned_hits(self) -> str:
        _, out = self.check_output()
        return "\n".join(l for l in out.splitlines() if "review 出现客户端语境禁用词" in l)

    def test_the_human_zone_is_not_judged(self) -> None:
        """人工区是**人的表态**，不是产品承诺——「文案回退为上一版」不该被拦。"""
        self.write_review("甲议题的澄清正文。", human="不同意时改什么：文案回退为上一版。")
        self.init_audit()
        self.assertEqual(self.banned_hits(), "", "人工区被当成产品承诺判了")

    def test_the_freeform_zone_is_not_judged(self) -> None:
        """「其他意见」章整章是人写的，同理不判。"""
        self.write_review("甲议题的澄清正文。", freeform="上游说没有运营灰度诉求。")
        self.init_audit()
        self.assertEqual(self.banned_hits(), "", "freeform 区被当成产品承诺判了")

    def test_an_exempt_category_is_not_judged(self) -> None:
        """必答内容就是开关管控的那类议题——讲放量是本职，不是跑题。"""
        self.write_review("上游约定：分享功能开关默认关闭，随版本放开。",
                          category="入口与管控")
        self.init_audit()
        self.assertEqual(self.banned_hits(), "", "上线/管控类议题被误伤")

    def test_a_non_exempt_category_is_still_judged(self) -> None:
        """**本项的硬门**：不属上线/管控类的议题，机器区里真承诺发布方式仍要拦。"""
        self.write_review("本方案采用灰度发布，先放开一部分用户。",
                          category="规则与数值")
        self.init_audit()
        self.assertNotEqual(self.banned_hits(), "",
                            "非豁免类议题的机器区放行了——本项设计错，要回退重做")

    def test_the_word_list_itself_is_untouched(self) -> None:
        """收的是作用域，不是词表：`BANNED_TERMS` 的成员数不许少。

        降级词表会让 story 侧一起失守，那是另一码事。
        """
        rules = (REPO_ROOT / "doc/extensions/skills/story/scripts/lint-rules.mjs"
                 ).read_text(encoding="utf-8")
        body = rules.split("const BANNED_TERMS = [", 1)[1].split("];", 1)[0]
        self.assertGreaterEqual(body.count("term:"), 6, "禁用词表被削了")

    def test_the_exempt_set_comes_from_the_contract(self) -> None:
        """豁免类别由合同数据给，脚本不写死类别名——写死名字换个工程就静默失效。"""
        body = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                ).read_text(encoding="utf-8")
        seg = body.split("function redactReviewExemptZones", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("banned_terms_exempt", seg)
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        for cat in contract["decision_categories"]:
            if cat.get("banned_terms_exempt"):
                self.assertNotIn(cat["key"], seg,
                                 "类别名 %s 被写死进脚本了" % cat["key"])


