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


class FiguresMustNotVanish(NegativeCase):
    """图与图片在 story 里整个消失 —— 四条反例。

    图类单元是 token 守恒链上最薄的一环：图片单元的 token **只有文件 basename**，
    它只有在作者真写了 `![](…)` 时才命中；没画图，token 也就不在，
    `autoPlace` 返回 null、记录落回作者态，`audit` 的「待你分配 0 条」照样绿。
    流程图更弱——中文节点名被 `tokensOf` 的长度过滤刷掉，tokens 近乎空数组。

    **所以文字事实丢了会被整篇 token 守恒在任意位置捞回来，图丢了不会。**
    下面四条是图这一侧全部的网，动它们之前先在这里锁住。
    """

    def test_N1_material_images_not_referenced_at_all(self) -> None:
        """坏产物：材料给了 3 张图片，story 一张都不引。"""
        self.seed_images(3)
        self.init_audit()
        self.settle()
        out = self.assert_check_names("story 里只引用了")
        self.assertIn("材料里有 3 张图片", out)

    def test_N2_material_diagrams_flattened_to_arrows(self) -> None:
        """坏产物：材料给了 2 张流程图，story 把它压成箭头文字、一张图都没有。"""
        self.seed_diagrams(2)
        self.init_audit()
        self.settle()
        out = self.assert_check_names("数量不该少于源")
        self.assertIn("材料里有 2 张图", out)

    def test_N3_image_placed_in_a_chapter_that_has_no_image(self) -> None:
        """坏产物：图片分了落点章，那一章里没有任何图片引用。

        与 N1 的区别：N1 判整篇数量，这一条判**这一章**。两条各防一面，
        少一条另一面就空了。
        """
        self.seed_images(1)
        self.init_audit()
        self.settle()
        image = self.units_of_kind("image")[0]
        self.set_record(image["key"], at="功能说明")
        self.assert_check_names("但那一章没有图片引用")

    def test_N4_diagram_with_no_state_at_all(self) -> None:
        """坏产物：流程图既没进 story，也没标 covered_by——连表态都没有。"""
        self.seed_diagrams(1)
        self.init_audit()
        self.settle()
        diagram = self.units_of_kind("diagram")[0]
        self.set_record(diagram["key"])
        self.assert_check_names("在 story 里没有落点")


class IdentifiersMustBeConservedWhereTheyLand(NegativeCase):
    """工程标识所属的事实整个丢失。

    守恒对 `by: machine` 的单元核「它的 token 在落点那一章里找得到」。
    放开这一条（例如把范围放大到整个附录），等于只要附录里任何位置出现过这个标识符
    就算核到——那与「这个单元的事实有落点」不是一回事。
    """

    def test_N5_identifier_not_found_in_its_landing_chapter(self) -> None:
        """坏产物：机器给了落点，但那一章里核不到它的 token。"""
        self.init_audit()
        self.settle()
        machine = next(r for r in self.audit["records"] if r.get("by") == "machine")
        by_key = {u["key"]: u for u in self.units}
        token = next(t for t in by_key[machine["key"]]["tokens"])
        text = self.story()
        self.assertIn(token, text, "夹具变了：这个 token 本来应当在 story 里")
        self.story_path.write_text(text.replace(token, "某个业务名"), encoding="utf-8")
        self.assert_check_names("里核不住")


class ArchivedDocMustStayReadableOutsideThisRepo(NegativeCase):
    """归档件红线：读者手上没有这个仓。"""

    def test_N6_review_promises_a_delivery_mechanism(self) -> None:
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
        self.settle()
        self.assert_check_names("review 出现客户端语境禁用词")


class GlossaryEntitiesMustReachTheStory(NegativeCase):
    """术语表里属于本需求的业务词，叙事件里必须找得到。"""

    HEADER = "| 原始术语 | 权威模块 | 所属层 | 置信度 | 易混项 | 用户确认 | 解释 |"
    TERM = "甲乙业务词"

    def test_N7_in_scope_business_term_absent_from_story(self) -> None:
        """坏产物：术语表登记了本需求的业务词，story 里一个字都没有。"""
        spec = self.feature_root() / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# 甲需求 spec\n\n## 0. 术语映射表\n\n" + self.HEADER
            + "\n|---|---|---|---|---|---|---|\n"
            + "| " + self.TERM + " | 甲模块 | 业务层 | 高 | — | [x] | "
            + "本需求里指某个具体业务动作 |\n",
            encoding="utf-8")
        self.init_audit()
        self.settle()
        self.assert_check_names(self.TERM)


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

    def test_N8_import_half_done_index_missing_while_files_present(self) -> None:
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
        但必须在 init 的来源账里以 0 出现、并各记一笔。
        """
        proc = self.run_build("init")
        self.assertEqual(proc.returncode, 0, "可选来源缺失不该拦：" + proc.stderr)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("来源：", out)
        self.assertIn("不存在", out)
        self.assertIn("记一笔：", out)


class LedgersMustAllExist(NegativeCase):
    """五件台账缺一件 —— **当前只拦得住其中三件**。

    冻结只挡「登记之后改台账」，挡不住登记之前把台账删掉。而删掉是有动力的：
    实跑里裁决台账错到上千条之后被整份删除，删完 check 的报错数确实下去了。

    现状：`source-units.json` / `audit.json` 缺失是硬退出，`decisions.json` /
    `copyedit.md` 缺失有判据；**`story-verdicts.md` 只在存在 `by: author` 记录时
    才被要求**——而这份夹具里机器能定位全部单元，`by: author` 为空，
    于是删掉裁决台账一声不吭。
    """

    LEDGERS = ("source-units.json", "audit.json", "decisions.json",
               "story-verdicts.md", "copyedit.md")

    def test_the_three_that_are_covered(self) -> None:
        """先锁住现在拦得住的那几件，改动不许把它们弄丢。"""
        for name in ("source-units.json", "audit.json", "decisions.json", "copyedit.md"):
            with self.subTest(ledger=name):
                self.setUp()
                self.init_audit()
                self.settle()
                (self.src / name).unlink(missing_ok=True)
                code, out = self.check_output()
                self.assertNotEqual(code, 0, name + " 缺失居然没拦：" + out)
                self.assertIn(name.split(".")[0], out,
                              "拦是拦了，但没点名是哪一件：" + out)

    @unittest.expectedFailure
    def test_N9_verdicts_ledger_deleted_without_author_records(self) -> None:
        """坏产物：裁决台账被整份删除，而机器恰好定得了全部落点。

        **批次 4 转正**：`check` 起步先判五件存在，缺任一＝BLOCKER，
        报错文案写明「补产出，不是把同伴文件删掉」。
        """
        self.init_audit()
        self.settle()
        author = [r for r in self.audit["records"] if r.get("by") == "author"]
        self.assertEqual(author, [], "夹具变了：这条反例要的是「没有作者态」那种情形")
        (self.src / "story-verdicts.md").unlink(missing_ok=True)
        self.assert_check_names("story-verdicts.md")


class TheLibraryItselfIsComplete(unittest.TestCase):
    """这一份夹具库自己的完备性——防它慢慢变空。"""

    THIS = Path(__file__)

    def test_nine_negatives_are_present(self) -> None:
        body = self.THIS.read_text(encoding="utf-8")
        found = sorted(set(re.findall(r"def test_(N\d)_", body)))
        self.assertEqual(found, ["N%d" % i for i in range(1, 10)],
                         "反例编号不全：" + str(found))

    def test_every_negative_names_the_judgement(self) -> None:
        """每条反例都要**点名是哪一条判据拦的**，不许只判退出码。

        只判 `returncode == 1` 证明不了任何事：换一条判据误报也能让它绿。
        判据不一定在 `check`——N8 那条在 `init` 就拦住了——所以认的是
        「有没有对具体报错串下断言」，不是「有没有调某个辅助函数」。
        """
        body = self.THIS.read_text(encoding="utf-8")
        blocks = re.split(r"\n    def (test_N\d\w*)\(", body)
        pairs = list(zip(blocks[1::2], blocks[2::2]))
        self.assertEqual(len(pairs), 9, "反例条数不对：" + str([p[0] for p in pairs]))
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
        self.assertTrue(marks, "一个 xfail 都没有——N8/N9 被谁悄悄转正了？")
        for m in marks:
            window = body[m.end():m.end() + 900]
            self.assertRegex(window, r"批次 \d 转正",
                             m.group(1) + " 没写明哪一批转正")


if __name__ == "__main__":
    unittest.main()
