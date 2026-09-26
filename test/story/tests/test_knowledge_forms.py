"""知识的类型 × 形态：`form` 声明与四格校验、按形态的登记单元、plan 送达下篇、机制零知识结构。

加载器按每份知识声明的 `form` 分派解析，只认四个合法格；登记单元随形态走（分面是面名，
上下篇是篇名，条目表是编号）。spec 登记用了上篇的上下篇知识，plan 任务包附上它的下篇全文。
机制只引用协议结构名：知识的名字、面名、节名与角色名一个都不写进 hooks、skills、rules。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_neutral_knowledge as nk  # noqa: E402

REPO_ROOT = nk.REPO_ROOT
EXT = nk.EXT
FOUR_CELLS = {("facts", "facets"), ("facts", "halves"), ("constraints", "entries"), ("patterns", "halves")}

# 一份机制没见过的方法型事实：节名任意，下篇有一句可辨认的话。
METHOD = """---
name: neutral-method
kind: facts
form: halves
applies_when: 设计出口核对时：怎样一步步核出口
---

# 中性方法

# 上篇 · 设计（读者：spec）

## 甲步

先把出口逐个列出来。

# 下篇 · 落地（读者：plan）

## 乙步

每个出口写一行：出口名、核对人、核对时机。
"""


def load(root: Path) -> tuple[dict | None, str]:
    """按工作区加载激活知识：成功返回解析结果，失败返回错误文本。"""
    proc = nk.node("--input-type=module", "-e",
                   f"const k = await import({nk.as_url(root / 'doc/extensions/hooks/shared/knowledge.mjs')});"
                   f"try {{ process.stdout.write(JSON.stringify(k.activeKnowledge({json.dumps(root.as_posix())}))); }}"
                   " catch (e) { process.stdout.write('ERR' + e.message); }")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return (None, proc.stdout[3:]) if proc.stdout.startswith("ERR") else (json.loads(proc.stdout), "")


class TheShippedKnowledgeFillsTheFourCells(unittest.TestCase):
    """AC01：Demo 知识全部加载通过，每份带 `form`，四格各至少一份。"""

    def test_every_file_declares_a_legal_cell(self) -> None:
        got, err = load(REPO_ROOT)
        self.assertEqual("", err)
        cells = {(kind, x["form"]) for kind in ("facts", "constraints", "patterns") for x in got[kind]}
        self.assertEqual(FOUR_CELLS, cells)


class MethodCase(nk.NeutralKnowledgeCase):
    """中性工作区再加一份上下篇事实。"""

    def setUp(self) -> None:
        super().setUp()
        self.add("facts/neutral-method.md", METHOD)

    def add(self, rel: str, text: str) -> None:
        (self.ext / "knowledge" / rel).write_text(text, encoding="utf-8")
        manifest = self.ext / "manifest.yaml"
        body = manifest.read_text(encoding="utf-8")
        manifest.write_text(body.replace("  knowledge:\n", f"  knowledge:\n    - knowledge/{rel}\n", 1),
                            encoding="utf-8")

    def use_method(self, facet: str = "上篇") -> None:
        """在默认判断之上登记用了 neutral-method 的某一篇。"""
        self.write_use()
        text = self.use_path.read_text(encoding="utf-8").replace(
            "constraint_domains:",
            f"  - id: neutral-method\n    used:\n      - facet: {facet}\n        used_for: 列出口\n"
            "constraint_domains:", 1)
        self.use_path.write_text(text, encoding="utf-8")

    def plan_package(self) -> str:
        proc = subprocess.run(["node", str(self.ext / "hooks/plan/author.mjs"), "--feature", nk.FEATURE],
                              cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout


class TheFormIsDeclaredAndChecked(MethodCase):
    """AC02：缺 form、值不在集合、组合不合法、声明与正文不符——同一次加载全部点名，含文件与改法。"""

    def test_every_breach_is_named_in_one_load(self) -> None:
        head = "---\nname: {n}\nkind: {k}\n{f}applies_when: 中性\n---\n\n# {n}\n\n"
        halves = "# 上篇 · 设计\n\n## 甲\n\n甲。\n\n# 下篇 · 落地\n\n## 乙\n\n乙。\n"
        files = {
            "facts/no-form.md": head.format(n="no-form", k="facts", f="") + "## 一面\n\n内容。\n",
            "facts/odd-form.md": head.format(n="odd-form", k="facts", f="form: tree\n") + "## 一面\n\n内容。\n",
            "facts/bad-cell.md": head.format(n="bad-cell", k="facts", f="form: entries\n") + "## 一面\n\n内容。\n",
            "facts/facets-halves.md": head.format(n="facets-halves", k="facts", f="form: facets\n") + halves,
            "facts/one-half.md": head.format(n="one-half", k="facts", f="form: halves\n") + "# 上篇 · 设计\n\n## 甲\n\n甲。\n",
            "facts/empty-half.md": head.format(n="empty-half", k="facts", f="form: halves\n")
            + "# 上篇 · 设计\n\n## 甲\n\n甲。\n\n# 下篇 · 落地\n\n只有一段话。\n",
        }
        for rel, text in files.items():
            self.add(rel, text)
        _, err = load(self.root)
        for needle in ("knowledge/facts/no-form.md 的 frontmatter 缺 form",
                       "knowledge/facts/odd-form.md 的 kind: facts 与 form: tree 不是合法组合",
                       "knowledge/facts/bad-cell.md 的 kind: facts 与 form: entries 不是合法组合",
                       "facts 可用的形态：facets / halves",
                       "knowledge/facts/facets-halves.md 声明 form: facets，正文却分了上下篇",
                       "knowledge/facts/one-half.md 声明 form: halves，却缺一级标题 「# 下篇 · …」",
                       "knowledge/facts/empty-half.md 的「下篇」下没有二级标题"):
            with self.subTest(needle=needle):
                self.assertIn(needle, err)


class TheUnitFollowsTheForm(MethodCase):
    """AC03：登记单元按形态；校验用对应标签；投影两次渲染字节一致。"""

    def test_each_cell_has_its_own_unit(self) -> None:
        got, err = load(self.root)
        self.assertEqual("", err)
        by_name = {x.get("name") or x.get("id"): x for kind in ("facts", "patterns") for x in got[kind]}
        self.assertEqual(["出口登记"], by_name["neutral-facts"]["units"])
        self.assertEqual(["上篇", "下篇"], by_name["neutral-method"]["units"])
        self.assertEqual(["上篇", "下篇"], by_name["neutral-pattern"]["units"])
        domain = next(c for c in got["constraints"] if c["domain"] == "NEU")
        self.assertEqual(["NEU-01", "NEU-02"], domain["units"])

    def test_a_wrong_half_is_named_as_a_half(self) -> None:
        self.use_method("中篇")
        proc = self.render()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("facts 的「neutral-method」没有篇「中篇」（有：上篇、下篇）", proc.stdout + proc.stderr)

    def test_the_projection_renders_the_same_bytes_twice(self) -> None:
        self.use_method()
        first = self.render()
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        once = self.spec_path.read_bytes()
        self.assertEqual(0, self.render().returncode)
        self.assertEqual(once, self.spec_path.read_bytes())


class ThePlanPackageCarriesTheLowerHalf(MethodCase):
    """AC26 / AC05：送什么由 spec 的登记决定；节名怎么改、知识怎么增删，机制文件一个字节不动。"""

    def test_a_registered_upper_half_brings_its_lower_half(self) -> None:
        self.use_method()
        package = self.plan_package()
        self.assertIn("### neutral-method · 下篇", package)
        self.assertIn("每个出口写一行：出口名、核对人、核对时机。", package)
        self.assertNotIn("先把出口逐个列出来。", package, "上篇不该跟着附进 plan 任务包")

    def test_an_unregistered_method_is_named_not_attached(self) -> None:
        self.write_use()
        package = self.plan_package()
        self.assertNotIn("### neutral-method · 下篇", package)
        line = next(l for l in package.split("\n") if l.startswith("spec 未登记使用的上下篇知识"))
        self.assertIn("neutral-method", line)

    def test_knowledge_changes_leave_the_mechanism_untouched(self) -> None:
        body = (self.ext / "knowledge/facts/neutral-method.md").read_text(encoding="utf-8")
        (self.ext / "knowledge/facts/neutral-method.md").write_text(
            body.replace("## 甲步", "## 随便一个节名").replace("## 乙步", "## 另一个节名"), encoding="utf-8")
        self.add("facts/neutral-extra.md", "---\nname: neutral-extra\nkind: facts\nform: facets\n"
                 "applies_when: 设计存档时：存档放在哪\n---\n\n# 存档\n\n## 存档位置\n\n中性存档区。\n")
        manifest = self.ext / "manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace(
            "    - knowledge/facts/event-tracking.md\n", ""), encoding="utf-8")
        _, err = load(self.root)
        self.assertEqual("", err)
        self.use_method()
        self.assertEqual(0, self.render().returncode)
        self.assertIn("## 另一个节名", self.plan_package())
        # 门禁与审查请求照常：不因知识的增删改而异常或报知识不合协议
        for hook, phase in (("spec/post_check.mjs", "spec"), ("shared/pre_verifier.mjs", "spec"),
                            ("shared/pre_verifier.mjs", "plan")):
            with self.subTest(hook=hook, phase=phase):
                out = self.run_hook(hook, phase)
                for needle in ("门禁自身异常", "知识不合协议", "激活知识派生失败"):
                    self.assertNotIn(needle, out)

    def run_hook(self, hook: str, phase: str) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const m = (await import({nk.as_url(self.ext / 'hooks' / hook)})).default;"
                       f"const out = await m({{ phase: '{phase}', feature: {json.dumps(nk.FEATURE)},"
                       f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                       "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout


def knowledge_words() -> set[str]:
    """从激活知识派生：知识名、面名、节名与角色名。"""
    got, err = load(REPO_ROOT)
    assert not err, err
    words: set[str] = set()
    for kind in ("facts", "constraints", "patterns"):
        for x in got[kind]:
            words.add(x.get("name") or x.get("id"))
            words.update(x.get("roles") or [])
            if x["form"] == "facets":
                words.update(x["units"])
            for half in (x.get("halves") or {}).values():
                for m in re.finditer(r"^##\s+(.+?)\s*$", half, flags=re.M):
                    words.add(re.sub(r"^\d+(\.\d+)*\.?\s*", "", m.group(1).split(" — ")[0]).strip())
    return {w for w in words if w}


class TheMechanismCarriesNoKnowledgeStructure(unittest.TestCase):
    """AC04 / AC27：机制只引用协议与产物出口的结构名；知识结构与内容词从机制里退出。"""

    STRUCTURE_DOCS = (EXT / "skills/story/reference/knowledge/protocol.md",
                      EXT / "skills/story/templates/spec-sections.md",
                      EXT / "skills/story/templates/plan-sections.md")
    REMOVED = ("所在流程", "字段取值", "settle", "角色与登记位置", "每次上报带什么", "以后台数据为分母", "衡量什么")

    def mechanism_texts(self):
        for base in (EXT / "hooks", EXT / "skills", EXT / "rules"):
            for f in base.rglob("*"):
                if f.is_file() and f.suffix in {".mjs", ".py", ".md", ".yaml", ".json"} and "__pycache__" not in f.parts:
                    yield f, f.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def protocol_structure_names() -> set[str]:
        """协议定义的结构名：两个篇名，§一 的 frontmatter 字段与 §六 条目表的列名。"""
        protocol = (EXT / "skills/story/reference/knowledge/protocol.md").read_text(encoding="utf-8")
        names = {"上篇", "下篇"}
        for no in ("一", "六"):
            section = protocol.split(f"## {no}、", 1)[1].split("\n## ", 1)[0]
            names |= {c.strip().strip("`") for c in re.findall(r"^\| ([^|]+) \|", section, flags=re.M)}
        return names

    def test_no_knowledge_word_outside_the_structure_names(self) -> None:
        """词表从知识派生，减去协议的结构名与产物模板里的出口名；两个字的通用词不算专名。"""
        templates = "\n".join(p.read_text(encoding="utf-8") for p in self.STRUCTURE_DOCS[1:])
        allowed = self.protocol_structure_names()
        words = {w for w in knowledge_words() if w not in allowed and w not in templates and len(w) >= 3}
        self.assertTrue(words, "派生词表为空，这条核不到东西")
        hits = [f"{f.relative_to(EXT).as_posix()}：{w}" for f, text in self.mechanism_texts()
                for w in sorted(words) if w in text]
        self.assertEqual([], hits)

    def test_the_removed_structure_words_are_gone(self) -> None:
        hits = [f"{f.relative_to(EXT).as_posix()}：{w}" for f, text in self.mechanism_texts()
                for w in self.REMOVED if re.search(rf"(?<![A-Za-z]){w}(?![A-Za-z])", text)]
        self.assertEqual([], hits)

    def method_fact(self) -> dict:
        got, _ = load(REPO_ROOT)
        return next(f for f in got["facts"] if f["form"] == "halves")

    def test_the_example_topic_differs_from_cases_and_golden(self) -> None:
        """示例题材从用例补料名与金样标题派生禁用词：整名与它的前三个字都不出现。"""
        topics: set[str] = set()
        golden = REPO_ROOT / "test/story/golden"
        for f in [*golden.glob("*.md"), *golden.glob("*/README.md")]:
            first = f.read_text(encoding="utf-8").split("\n", 1)[0]
            name = re.sub(r"^#\s*(AR\d+\s*)?", "", first).split("（")[0].split("：")[0].strip()
            if re.search(r"[一-鿿]{3}", name):
                topics.update({name, name[:3]})
        for f in (REPO_ROOT / "test/story/cases").glob("*/supplements/*"):
            if re.match(r"[一-鿿]{3}", f.stem):
                topics.update({f.stem, f.stem[:3]})
        self.assertTrue(topics)
        text = json.dumps(self.method_fact()["halves"], ensure_ascii=False)
        self.assertEqual([], sorted(t for t in topics if t in text))


class TheProtocolAndMethodPageAgree(unittest.TestCase):
    """AC06：协议列的字段是加载器读的字段；方法页四格各含四要素；作者页与内网指南指向正确。"""

    def test_the_protocol_fields_are_what_the_loader_reads(self) -> None:
        protocol = (EXT / "skills/story/reference/knowledge/protocol.md").read_text(encoding="utf-8")
        section = protocol.split("## 一、", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"^\| `(\w+)` \|", section, flags=re.M))
        loader = (EXT / "hooks/shared/knowledge.mjs").read_text(encoding="utf-8")
        read = set(re.findall(r"\bfm\.(\w+)", loader))
        self.assertEqual({"name", "kind", "form", "applies_when"}, listed)
        self.assertLessEqual(listed, read)
        self.assertEqual([], sorted(f for f in read if f"`{f}`" not in protocol), "加载器读的字段协议里没写")

    def test_the_method_page_gives_four_elements_for_four_cells(self) -> None:
        page = (EXT / "skills/story-adaptation/reference/knowledge-adaptation.md").read_text(encoding="utf-8")
        table = page.split("## 四格怎么写", 1)[1].split("\n## ", 1)[0]
        rows = [l for l in table.split("\n") if l.startswith("| ")]
        self.assertEqual("| 格 | 何时用这个形态 | 到哪取证 | 照哪份 Demo 示例 | 怎样走查 |", rows[0])
        cells = {tuple(re.match(r"\| (\w+) × (\w+) \|", r).groups()) for r in rows[1:]}
        self.assertEqual(FOUR_CELLS, cells)
        for r in rows[1:]:
            self.assertTrue(all(c.strip() for c in r.strip("|").split("|")), r)

    def test_the_coding_page_and_the_upgrade_record_point_right(self) -> None:
        """升级要做的事只在 adapt 的演进记录里：没有另一份指南，extension 里也不描述目标仓内部。"""
        coding = (EXT / "hooks/coding/author.md").read_text(encoding="utf-8")
        self.assertIn("reference/knowledge/protocol.md", coding)
        self.assertIn("下篇", coding)
        adapt = EXT / "skills/story-adaptation"
        self.assertIn("reference/knowledge-adaptation.md", (adapt / "reference/upgrade-changes.md").read_text(encoding="utf-8"))
        self.assertEqual([], sorted(p.name for p in (REPO_ROOT / "test/story/release").glob("内网适配指南*")))
        self.assertFalse((EXT / "skills/story/scripts/README.md").exists())


if __name__ == "__main__":
    unittest.main()
