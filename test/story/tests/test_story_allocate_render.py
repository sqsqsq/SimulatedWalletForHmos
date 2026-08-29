"""成文 = 先分配后逐章渲染——分配即恰好一处，渲染可续写。

一次写成整篇是**全有或全无**：中途断了磁盘上什么都没有，前面读的材料全白读。
实测四次尝试三次空手而归（子 agent 跑完返回空、谎报 completed）。
改成先分配后渲染之后，每步输出有界、写完即落盘、断了知道从哪一章续。

这里判两件事：
  KF-7a 分配完成后，每个单元恰好一条记录、没有无家可归的、`covered_by` 有效；
  KF-7b 渲染一章只影响该章命中的单元，未渲染章清单正确，续写不重写已有章。
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


class AllocateRenderCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)
        self.feature = self.root / "doc" / "features" / FEATURE
        self.src = self.feature / "AR" / "story-src"
        self.story = self.feature / "AR" / "story.md"
        # 分配发生在正文之前：把夹具带的成品 story 收起来，留作逐章渲染的素材。
        # 但 `init` 要读 spec.md 之外的材料、也会被 story 影响，所以先枚举再收。
        self.finished = self.story.read_text(encoding="utf-8")
        proc = self.run_build("init")
        self.assertEqual(proc.returncode, 0, f"init 跑不起来：{proc.stderr}")
        self.story.unlink()
        (self.src / "audit.json").unlink(missing_ok=True)

    def run_build(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(BUILD), command, "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    @property
    def units(self) -> list[dict]:
        return json.loads((self.src / "source-units.json").read_text("utf-8"))["units"]

    @property
    def records(self) -> list[dict]:
        return json.loads((self.src / "audit.json").read_text("utf-8"))["records"]

    def chapters(self) -> list[str]:
        """成品 story 的章标题，按顺序。"""
        return [l[3:].strip() for l in self.finished.split("\n") if l.startswith("## ")]

    def chapter_text(self, title: str) -> str:
        body, hit = [], False
        for line in self.finished.split("\n"):
            if line.startswith("## "):
                if hit:
                    break
                hit = line[3:].strip() == title
                if hit:
                    body.append(line)
                continue
            if hit:
                body.append(line)
        return "\n".join(body)

    def render(self, titles: list[str]) -> None:
        """把这几章追加到 story.md——模拟逐章渲染。"""
        existing = self.story.read_text("utf-8") if self.story.exists() else ""
        chunks = [self.chapter_text(t) for t in titles]
        self.story.write_text(existing + "\n" + "\n".join(chunks) + "\n", encoding="utf-8")

    def allocate(self) -> None:
        """作者分配：把成品里每章讲了的单元分给那一章，其余分给第一章。

        真实链路上这一步由作者判断；这里只需要造出「每条都有落点」的合法输入。
        """
        titles = self.chapters()
        records = []
        for unit in self.units:
            if unit["machine_facing"]:
                records.append({"key": unit["key"], "machine_facing": True})
                continue
            at = titles[0]
            for t in titles:
                body = self.chapter_text(t)
                if any(tok in body for tok in (unit.get("tokens") or [])) or unit["text"][:8] in body:
                    at = t
                    break
            records.append({"key": unit["key"], "at": at})
        (self.src / "audit.json").write_text(
            json.dumps({"records": records}, ensure_ascii=False, indent=2), encoding="utf-8")


class TestAllocation(AllocateRenderCase):
    """KF-7a：分配即恰好一处。"""

    def test_audit_runs_before_any_chapter_exists(self) -> None:
        """story.md 还不存在 = 一章都没渲染，不是错误——分配先于正文。"""
        self.assertFalse(self.story.exists())
        proc = self.run_build("audit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("未渲染章", proc.stdout)

    def test_unallocated_units_are_listed(self) -> None:
        """没分配时，每一条都该被列成「待处理」——这是分配的任务清单。"""
        proc = self.run_build("audit")
        open_count = sum(1 for r in self.records
                         if not r.get("at") and not r.get("covered_by") and not r.get("machine_facing"))
        self.assertGreater(open_count, 0)
        self.assertIn(f"待处理 {open_count} 条", proc.stdout)

    def test_one_record_per_unit_and_none_homeless(self) -> None:
        self.allocate()
        self.render(self.chapters())
        self.assertEqual(self.run_build("audit").returncode, 0)
        keys = [r["key"] for r in self.records]
        self.assertEqual(len(keys), len(set(keys)), "一个单元只能有一条记录")
        self.assertEqual({u["key"] for u in self.units}, set(keys), "记录与单元一一对应")
        homeless = [r for r in self.records
                    if not r.get("at") and not r.get("covered_by") and not r.get("machine_facing")]
        self.assertEqual(homeless, [], "分配完成后不该还有无家可归的单元")

    def test_covered_by_must_point_at_an_allocated_unit(self) -> None:
        """`covered_by` 指向的那条自己要有落点，否则两条一起悬空。"""
        self.allocate()
        self.render(self.chapters())
        self.run_build("audit")
        records = self.records
        target = next(r for r in records if r.get("at"))
        victim = next(r for r in records if r.get("at") and r["key"] != target["key"])
        victim.pop("at", None)
        victim.pop("by", None)
        victim["covered_by"] = "SOMETHING:0:deadbeef"      # 指向不存在的单元
        (self.src / "audit.json").write_text(
            json.dumps({"records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = self.run_build("check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("covered_by 指向不存在的单元", proc.stderr + proc.stdout)


class TestChapterRendering(AllocateRenderCase):
    """KF-7b：逐章渲染可续写。"""

    def test_pending_chapters_shrink_as_rendering_proceeds(self) -> None:
        self.allocate()
        titles = self.chapters()
        first = self.run_build("audit").stdout
        self.assertIn(f"未渲染章 {len(titles)}/{len(titles)}", first)

        self.render(titles[:2])
        second = self.run_build("audit").stdout
        self.assertIn(f"未渲染章 {len(titles) - 2}/{len(titles)}", second)
        for done in titles[:2]:
            self.assertNotIn(done, second.split("未渲染章")[1].split("\n")[0])

    def test_rendering_a_chapter_only_verifies_that_chapter(self) -> None:
        """渲染一章，只有落在这一章、且正文里核得到的单元变 `by: machine`。"""
        self.allocate()
        by_key = {u["key"]: u for u in self.units}
        allocated = json.loads((self.src / "audit.json").read_text("utf-8"))["records"]
        # 挑一个「章里确实核得到它的 token」的落点，否则渲染完机器仍然定不了，测不到东西
        target = next(
            r["at"] for r in allocated
            if r.get("at") and any(t in self.chapter_text(r["at"])
                                   for t in (by_key[r["key"]].get("tokens") or [])))
        self.render([target])
        self.assertEqual(self.run_build("audit").returncode, 0)
        machine = [r for r in self.records if r.get("by") == "machine"]
        self.assertTrue(machine, "渲染过的章里应当有单元被机器核实")
        self.assertTrue(all(r["at"] == target for r in machine),
                        "未渲染章里的单元不该被标成已核实")

    def test_continuation_does_not_rewrite_finished_chapters(self) -> None:
        """续写只追加：已写好的章逐字节不变。"""
        self.allocate()
        titles = self.chapters()
        self.render(titles[:2])
        before = self.story.read_text("utf-8")
        self.run_build("audit")
        self.render(titles[2:4])
        after = self.story.read_text("utf-8")
        self.assertTrue(after.startswith(before), "续写不得改动已渲染的章")


if __name__ == "__main__":
    unittest.main()
