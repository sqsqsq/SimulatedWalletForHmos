"""使用统计（story-stats）：真实临时 Git 仓 + 真实脚本入口，核 Git 关联、聚合分母、版本筛选与候选报告发布。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ext_workspace import DEV_EXT

STATS = DEV_EXT / "skills" / "story-stats" / "scripts" / "stats.py"


def local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")


def step(completed: bool, spent):
    return {"start": None, "spent": spent, "verdict": None, "completed": completed, "last_result": None}


ENV = {"fw": "3.0.0", "ext": "1.9.9", "agent": "opencode"}
USAGE = {"schema": 1, "requirements": {
    "AR1": {"name": "甲", "version": "4.2.0", **ENV, "model": "m-a", "features": ["AR1"],
            "steps": {"spec": step(True, 600), "coding": step(False, None)}},
    "DTS22": {"name": "乙", "version": "4.2.0", **ENV, "model": "m-a", "features": ["DTS22"],
              "steps": {"spec": step(True, None)}},
    "AR333": {"name": "丙", "version": "4.3.0", **ENV, "model": "m-b", "features": ["AR333"],
              "steps": {"spec": step(True, 1200), "story": step(True, 0)}},
    "AR4": {"name": "丁", "version": None, **ENV, "model": None, "features": ["AR4"],
            "steps": {"coding": step(False, None)}},
}}


class StatsRepo(unittest.TestCase):
    """一个目标仓：usage 与代码分开提交；两种 TicketNo、跨时区、merge、二进制、描述里带别的编号、无关联提交。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = root = Path(cls._tmp.name) / "repo"
        root.mkdir()
        cls.git("init", "-q", "-b", "main")
        (root / "framework.config.json").write_text(json.dumps({"project_name": "示例工程"}), encoding="utf-8")
        cls.commit("AR1 first", "[TicketNo:] AR1\n[Description:] 起步\n[Binary Source:] NA", files={"x.txt": "x\n"},
                   author=("Alice", "alice@x"), at="2026-10-01T09:00:00+08:00")
        cls.commit("AR1 by alice", "[TicketNo:] AR1\n[Description:] 修 AR4 的提示\n[Binary Source:] NA",
                   files={"a.txt": "1\n2\n3\n"}, author=("Alice", "alice@x"), at="2026-10-02T10:00:00+08:00")
        cls.commit("AR1 by bob", "[TicketNo:] AR1\n[Description:] 补测试\n[Binary Source:] NA",
                   files={"b.txt": "1\n2\n"}, author=("Bob", "bob@x"), at="2026-10-03T01:00:00+00:00")
        cls.commit("DTS by alice", "[TicketNo:] DTS22\n[Description:] 修复\n[Binary Source:] NA",
                   files={"c.txt": "1\n"}, author=("Alice", "ALICE@x"), at="2026-10-04T12:00:00+08:00")
        cls.commit("two tickets", "[TicketNo:] AR1\n[TicketNo:] DTS22\n[Description:] 两个编号\n[Binary Source:] NA",
                   files={"t.txt": "1\n2\n3\n4\n5\n"}, author=("Alice", "alice@x"), at="2026-10-05T10:00:00+08:00")
        cls.commit("AR333", "[TicketNo:] AR333\n[Description:] 新功能\n[Binary Source:] NA",
                   files={"d.txt": "1\n2\n3\n4\n"}, binary="e.bin", author=("Bob", "bob@x"), at="2026-10-11T10:00:00+08:00")
        cls.commit("no ticket", "随手改", files={"f.txt": "1\n"}, author=("Carol", "carol@x"), at="2026-10-12T10:00:00+08:00")
        cls.commit("other req", "[TicketNo:] AR999\n[Description:] 不在 usage\n[Binary Source:] NA",
                   files={"g.txt": "1\n"}, author=("Dan", "dan@x"), at="2026-10-12T11:00:00+08:00")
        cls.git("checkout", "-q", "-b", "side", "HEAD~1")
        cls.commit("side AR333", "[TicketNo:] AR333\n[Description:] 侧枝\n[Binary Source:] NA",
                   files={"h.txt": "1\n"}, author=("Bob", "bob@x"), at="2026-10-13T10:00:00+08:00")
        cls.git("checkout", "-q", "main")
        cls.git("merge", "-q", "--no-ff", "side", "-m", "[TicketNo:] AR1\n[Description:] merge", env=cls.env(("Eve", "eve@x"), "2026-10-14T10:00:00+08:00"))
        # 统计文件晚于代码提交、自身不带编号
        cls.commit("usage", "归档使用记录", files={"doc/usage.json": json.dumps(USAGE, ensure_ascii=False)},
                   author=("Alice", "alice@x"), at="2026-10-15T10:00:00+08:00")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @staticmethod
    def env(author, at) -> dict:
        return {**os.environ, "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1], "GIT_AUTHOR_DATE": at,
                "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1], "GIT_COMMITTER_DATE": at}

    @classmethod
    def git(cls, *args, env=None) -> str:
        return subprocess.run(["git", "-C", str(cls.root), *args], capture_output=True, text=True, encoding="utf-8",
                              check=True, env=env).stdout

    @classmethod
    def commit(cls, _what, message, *, files, author, at, binary=None) -> None:
        for rel, text in files.items():
            (cls.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.root / rel).write_text(text, encoding="utf-8")
        if binary:
            (cls.root / binary).write_bytes(bytes(range(256)) * 4)
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", message, env=cls.env(author, at))

    def run_stats(self, *args, root: Path | None = None) -> dict:
        p = subprocess.run([sys.executable, str(STATS), *args, "--project-root", str(root or self.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return json.loads(p.stdout)

    def facts(self, *args, root: Path | None = None) -> dict:
        out = self.run_stats("collect", *args, root=root)
        self.assertTrue(out["ok"], out)
        return json.loads(Path(out["facts"]).read_text(encoding="utf-8"))

    @staticmethod
    def rows(facts: dict, tid: str) -> dict:
        t = next(t for t in facts["tables"] if t["id"] == tid)
        return {r[0]: r[1:] for r in t["rows"]}

    @staticmethod
    def render(facts: dict) -> str:
        """按模板组织：标题原文、表格原样——模拟模型照 facts 成文。"""
        out = [f"# 报告\n\n## 1. {facts['headings'][0]}\n"]
        out += [f"### {h}\n" for h in facts["headings"][1:]]
        for t in facts["tables"]:
            out.append("| " + " | ".join(t["header"]) + " |\n|" + "---|" * len(t["header"]))
            out += ["| " + " | ".join(r) + " |" for r in t["rows"]]
            out.append("")
        return "\n".join(out)


class Aggregation(StatsRepo):
    def test_the_overview_counts_and_titles(self) -> None:
        f = self.facts()
        over = self.rows(f, "overview")
        # 关联：AR1×3、DTS22、AR333、经 merge 可达的侧枝 AR333 → 6 笔；merge、无编号、两个编号、AR999、usage 归档不算
        self.assertEqual(["4"], over["使用 AI 框架的需求数"])
        self.assertEqual(["2"], over["需求开发人数（去重）"], "邮箱大小写或跨版本同一人重复计了")
        self.assertEqual(["6"], over["关联提交数"])
        # 首笔 2 文件各 1 行 + 3 + 2 + 1 + 4 + 侧枝 1 = 13；二进制与 merge 不计
        self.assertEqual(["+13"], over["关联提交新增行数"], "二进制或 merge 的变更算进了行数")
        self.assertEqual("全版本总览（" + local("2026-10-01T09:00:00+08:00") + "—" + local("2026-10-13T10:00:00+08:00") + "）",
                         f["headings"][0])

    def test_steps_versions_and_their_denominators(self) -> None:
        f = self.facts()
        steps = self.rows(f, "steps")
        self.assertEqual(["3", "75.0%", "3", "100.0%"], steps["spec"])
        self.assertEqual(["2", "50.0%", "0", "0.0%"], steps["coding"])
        self.assertEqual(["0", "0.0%", "0", "—"], steps["story update"])
        versions = self.rows(f, "versions")
        self.assertEqual(["2", "2", "4", "+8", "−0"], versions["4.2.0"])
        self.assertEqual(["1", "0", "0", "+0", "−0"], versions["未知版本"])
        self.assertEqual(["4.2.0", "4.3.0", "未知版本"], list(versions), "未知版本组不在最后")
        self.assertIn("4.2.0（" + local("2026-10-01T09:00:00+08:00") + "—" + local("2026-10-04T12:00:00+08:00") + "）", f["headings"])
        self.assertIn("未知版本", f["headings"], "没有关联提交的版本编了时间")
        self.assertEqual(["1", "100.0%", "1", "100.0%"], self.rows(f, "steps:4.3.0")["spec"])

    def test_environment_averages_use_only_completed_known_spans(self) -> None:
        f = self.facts()
        envs = self.rows(f, "environments")
        self.assertEqual(["4.2.0", "3.0.0", "1.9.9", "opencode", "m-a", "2"], envs["E1"])
        self.assertEqual(["未知版本", "3.0.0", "1.9.9", "opencode", "—", "1"], envs["E3"])
        durations = self.rows(f, "durations")
        width = next(len(t["header"]) for t in f["tables"] if t["id"] == "durations")
        self.assertEqual(1 + len(envs), width, "均值表的列不是一组环境一列")
        one = self.facts("--version", "4.2.0")
        self.assertEqual(["功能步骤", "E1：4.2.0 / m-a"], next(t["header"] for t in one["tables"] if t["id"] == "durations"))
        self.assertEqual(["10.0", "20.0", "—"], durations["spec"], "未知耗时被当 0 参与了平均")
        self.assertEqual(["—", "0.0", "—"], durations["story"], "零秒不是未知")

    def test_a_version_scope_keeps_its_own_denominators(self) -> None:
        f = self.facts("--version", "4.2.0")
        self.assertEqual(["2"], self.rows(f, "overview")["使用 AI 框架的需求数"])
        self.assertTrue(f["headings"][0].startswith("业务版本 4.2.0（"))
        self.assertFalse(any(t["id"] == "versions" for t in f["tables"]))
        self.assertEqual(["2", "100.0%", "2", "100.0%"], self.rows(f, "steps")["spec"])
        unknown = self.facts("--version", "未知")
        self.assertEqual(["1"], self.rows(unknown, "overview")["使用 AI 框架的需求数"])
        empty = self.facts("--version", "9.9")
        self.assertEqual(["0"], self.rows(empty, "overview")["使用 AI 框架的需求数"])
        self.assertEqual(["0", "—", "0", "—"], self.rows(empty, "steps")["spec"])
        self.assertEqual("业务版本 9.9", empty["headings"][0], "空范围退回了全版本或编了时间")

    def test_stats_creates_no_use_and_a_bare_clone_still_reports(self) -> None:
        before = (self.root / "doc" / "usage.json").read_bytes()
        self.facts()
        self.assertEqual(before, (self.root / "doc" / "usage.json").read_bytes(), "统计改写了使用记录")
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            subprocess.run(["git", "clone", "-q", str(self.root), str(clone)], check=True)
            self.assertEqual(["4"], self.rows(self.facts(root=clone), "overview")["使用 AI 框架的需求数"])


class Publishing(StatsRepo):
    def draft(self, out: dict, text: str | None = None) -> None:
        facts = json.loads(Path(out["facts"]).read_text(encoding="utf-8"))
        Path(out["draft"]).write_text(text if text is not None else self.render(facts), encoding="utf-8")

    def current(self) -> dict:
        return json.loads((self.root / "doc" / "features" / ".usage-stats" / "current.json").read_text(encoding="utf-8"))

    def test_publish_rules(self) -> None:
        first = self.run_stats("collect")
        self.draft(first)
        done = self.run_stats("publish", "--analysis-id", first["analysis_id"])
        self.assertTrue(done["ok"], done)
        report = Path(done["report"])
        self.assertTrue(report.is_file())
        self.assertTrue(self.run_stats("publish", "--analysis-id", first["analysis_id"]).get("already"), "重复发布不幂等")

        failed = self.run_stats("collect")
        out = self.run_stats("publish", "--analysis-id", failed["analysis_id"])
        self.assertFalse(out["ok"])
        self.assertEqual(first["analysis_id"], self.current()["published"], "新报告没写成却换掉了旧的")
        self.assertTrue(report.is_file())

        a = self.run_stats("collect")
        b = self.run_stats("collect", "--version", "4.2.0")
        self.draft(a)
        self.draft(b)
        stale = self.run_stats("publish", "--analysis-id", a["analysis_id"])
        self.assertIn("已被新统计请求替代", stale["error"])

        facts = json.loads(Path(b["facts"]).read_text(encoding="utf-8"))
        self.draft(b, self.render(json.loads(Path(a["facts"]).read_text(encoding="utf-8"))))
        self.assertIn("没有按 facts 原样出现", self.run_stats("publish", "--analysis-id", b["analysis_id"])["error"],
                      "换了范围的候选被当成本次发布")
        wrong = self.render(facts).replace("| spec | 2 |", "| spec | 3 |", 1)
        self.draft(b, wrong)
        bad = self.run_stats("publish", "--analysis-id", b["analysis_id"])
        self.assertIn("没有按 facts 原样出现", bad["error"])
        self.draft(b, self.render(facts).replace("| 功能步骤 | 使用需求数 |", "| 功能步骤 | 使用需求数 | 多一列 |", 1))
        self.assertIn("行列数不一致", self.run_stats("publish", "--analysis-id", b["analysis_id"])["error"])
        self.assertEqual(first["analysis_id"], self.current()["published"])

        self.draft(b)
        os.replace(b["draft"], Path(b["draft"]).with_name("report.md"))
        resumed = self.run_stats("publish", "--analysis-id", b["analysis_id"])
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual({"pending": None, "published": b["analysis_id"]}, self.current())
        left = sorted(p.name for p in (self.root / "doc" / "features" / ".usage-stats").iterdir() if p.is_dir())
        self.assertEqual([b["analysis_id"]], left, "旧的未引用输出没清")

    def test_two_identical_tables_must_both_be_written(self) -> None:
        sys.path.insert(0, str(STATS.parent))
        import stats
        same = {"header": ["功能步骤", "使用需求数"], "rows": [["spec", "1"]]}
        facts = {"headings": ["甲", "乙"], "tables": [{"id": "steps:甲", **same}, {"id": "steps:乙", **same}]}
        self.assertEqual(1, len(stats.report_problems(self.render({**facts, "tables": facts["tables"][:1]}), facts)))
        self.assertEqual([], stats.report_problems(self.render(facts), facts))


class Reconciling(unittest.TestCase):
    def test_collect_settles_a_closed_round_before_counting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "framework" / "skills").mkdir(parents=True)
            (root / "framework" / "package.json").write_text('{"version": "3.0.0"}', encoding="utf-8")
            (root / "framework.config.json").write_text("{}", encoding="utf-8")
            reports = root / "doc" / "features" / "AR1" / "spec" / "reports"
            reports.mkdir(parents=True)
            (reports / "summary.json").write_text(json.dumps({
                "verdict": "PASS", "closure_status": "closed", "verifier_subject_id": "s1",
                "closure_commit": {"schema_version": "1.0", "committed_at": "2026-10-02T10:30:00Z",
                                   "receipt_path": "spec/receipt.md"}}), encoding="utf-8")
            begun = {**step(False, 0), "start": "2026-10-02T10:00:00Z"}  # 正式 begin 后的形态
            data = {"schema": 1, "requirements": {"AR1": {**USAGE["requirements"]["AR1"], "steps": {"spec": begun}}}}
            (root / "doc" / "usage.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=a", "-c", "user.email=a@x", "commit", "-q",
                            "--allow-empty", "-m", "[TicketNo:] AR1"], check=True)
            out = json.loads(subprocess.run([sys.executable, str(STATS), "collect", "--project-root", str(root)],
                                            capture_output=True, text=True, encoding="utf-8").stdout)
            self.assertTrue(out["ok"], out)
            spec = json.loads((root / "doc" / "usage.json").read_text(encoding="utf-8"))["requirements"]["AR1"]["steps"]["spec"]
            self.assertEqual((True, 1800), (spec["completed"], spec["spent"]), "统计前没把已关闭的轮次对上")
            facts = json.loads(Path(out["facts"]).read_text(encoding="utf-8"))
            self.assertEqual(["1", "100.0%", "1", "100.0%"], StatsRepo.rows(facts, "steps")["spec"])
            self.assertEqual(["30.0"], StatsRepo.rows(facts, "durations")["spec"])


class Installed(StatsRepo):
    def test_every_installed_entry_routes_stats_to_the_skill_that_runs(self) -> None:
        from ext_workspace import installed_package
        import publish_to_demo
        root = installed_package()
        bridges = publish_to_demo.manifest_bridges(root / "doc" / "extensions")
        self.assertEqual(6, len(bridges))
        for bridge in bridges:
            with self.subTest(bridge.target):
                text = (root / bridge.target).read_text(encoding="utf-8")
                row = next(line for line in text.splitlines() if line.startswith("| `stats"))
                link = row.split("](", 1)[1].split(")", 1)[0]
                self.assertTrue(((root / bridge.target).parent / link).resolve().samefile(
                    root / "doc" / "extensions" / "skills" / "story-stats" / "SKILL.md"))
        script = root / "doc" / "extensions" / "skills" / "story-stats" / "scripts" / "stats.py"
        p = subprocess.run([sys.executable, str(script), "collect", "--project-root", str(self.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        out = json.loads(p.stdout)
        self.assertTrue(out["ok"], out)
        self.assertTrue(Path(out["template"]).resolve().is_relative_to(script.parents[1].resolve()))


if __name__ == "__main__":
    unittest.main()
