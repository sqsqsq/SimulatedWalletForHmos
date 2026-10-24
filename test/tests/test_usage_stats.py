"""使用统计（story-stats）按 V5：真实临时 Git 仓 + 真实脚本入口，核 usage 变更归属、混合提交、merge、缺口，
以及统计只读 usage 与 Git——没有需求目录的独立代码仓也能统计，现场缺了或坏了不影响，缺的步骤不替记录端补。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT

STATS = DEV_EXT / "skills" / "story-stats" / "scripts" / "stats.py"
A, B, C = "AR1-20261001T010000.000Z", "DTS22-20261002T010000.000Z", "AR333-20261003T010000.000Z"


def node(steps: dict | None = None, agent="opencode", model="m-a") -> dict:
    return {"ext": "1.9.9", "fw": "3.0.0", "agent": agent, "model": model, "steps": steps or {}}


def usage(reqs: dict) -> str:
    return json.dumps({"schema": 1, "requirements": reqs}, ensure_ascii=False, indent=2) + "\n"


class GitRepo(unittest.TestCase):
    @classmethod
    def make_repo(cls) -> Path:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = root = Path(cls._tmp.name) / "repo"
        root.mkdir()
        cls.git("init", "-q", "-b", "main")
        (root / "framework.config.json").write_text(json.dumps({"project_name": "示例工程"}), encoding="utf-8")
        return root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @staticmethod
    def env(author=("Alice", "alice@x"), at="2026-10-01T09:00:00+08:00") -> dict:
        return {**os.environ, "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1], "GIT_AUTHOR_DATE": at,
                "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1], "GIT_COMMITTER_DATE": at,
                "GIT_CEILING_DIRECTORIES": str(Path(tempfile.gettempdir()).resolve())}

    @classmethod
    def git(cls, *args, author=("Alice", "alice@x"), at="2026-10-01T09:00:00+08:00", check=True) -> str:
        return subprocess.run(["git", "-C", str(cls.root), *args], capture_output=True, text=True, encoding="utf-8",
                              check=check, env=cls.env(author, at)).stdout

    @classmethod
    def commit(cls, message, files: dict, author=("Alice", "alice@x"), at="2026-10-01T09:00:00+08:00") -> str:
        for rel, text in files.items():
            (cls.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.root / rel).write_text(text, encoding="utf-8")
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", message, author=author, at=at)
        return cls.git("rev-parse", "HEAD").strip()

    def collect(self, root: Path | None = None) -> dict:
        p = subprocess.run([sys.executable, str(STATS), "collect", "--project-root", str(root or self.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           env=self.env())
        return json.loads(p.stdout)

    def facts(self) -> dict:
        out = self.collect()
        self.assertTrue(out["ok"], out)
        return json.loads(Path(out["facts"]).read_text(encoding="utf-8"))


class Attribution(GitRepo):
    """usage 与代码在同一些提交里；一笔混合提交、一笔纯代码提交、一个侧枝与一个带解决冲突改动的 merge。"""

    @classmethod
    def setUpClass(cls) -> None:
        root = cls.make_repo()
        cls.c1 = cls.commit("c1", {"doc/usage.json": usage({A: node()}), "a.txt": "1\n2\n3\n"})
        cls.c2 = cls.commit("c2", {"doc/usage.json": usage({A: node({"spec": {"spent": 600}})}), "b.txt": "1\n2\n"},
                            author=("Bob", "bob@x"), at="2026-10-02T09:00:00+08:00")
        cls.c3 = cls.commit("c3", {"doc/usage.json": usage({A: node({"spec": {"spent": 600}, "plan": {"spent": 300}}), B: node()}),
                                   "t.txt": "1\n2\n3\n4\n5\n"}, at="2026-10-03T09:00:00+08:00")
        cls.c4 = cls.commit("c4", {"f.txt": "1\n"}, author=("Carol", "carol@x"), at="2026-10-04T09:00:00+08:00")
        cls.git("checkout", "-q", "-b", "side")
        side = {A: node({"spec": {"spent": 600}, "plan": {"spent": 300}}), B: node({"spec": {}})}
        cls.c5 = cls.commit("c5", {"doc/usage.json": usage(side), "h.txt": "1\n"}, author=("Bob", "bob@x"),
                            at="2026-10-05T09:00:00+08:00")
        cls.git("checkout", "-q", "main")
        main = {A: node({"spec": {"spent": 600}, "plan": {"spent": 300}}), B: node(), C: node(agent=None, model=None)}
        cls.c6 = cls.commit("c6", {"doc/usage.json": usage(main)}, at="2026-10-06T09:00:00+08:00")
        cls.git("merge", "-q", "--no-commit", "--no-ff", "side", check=False, author=("Eve", "eve@x"))
        merged = {A: node({"spec": {"spent": 600}, "plan": {"spent": 300}, "coding": {"spent": 50}}),
                  B: node({"spec": {}}), C: node(agent=None, model=None)}
        (root / "doc/usage.json").write_text(usage(merged), encoding="utf-8")
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", "merge", author=("Eve", "eve@x"), at="2026-10-07T09:00:00+08:00")
        cls.merge = cls.git("rev-parse", "HEAD").strip()
        cls.data = cls.facts_once()

    @classmethod
    def facts_once(cls) -> dict:
        p = subprocess.run([sys.executable, str(STATS), "collect", "--project-root", str(cls.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=cls.env())
        out = json.loads(p.stdout)
        assert out["ok"], out
        cls.out = out
        return json.loads(Path(out["facts"]).read_text(encoding="utf-8"))

    def row(self, key: str) -> dict:
        return next(r for r in self.data["requirements"] if r["key"] == key)

    def test_each_requirement_gets_the_commits_that_added_or_changed_its_node(self) -> None:
        self.assertEqual([self.c1, self.c2, self.c3, self.merge], sorted((c["sha"] for c in self.row(A)["commits"]),
                         key=[self.c1, self.c2, self.c3, self.merge].index))
        self.assertEqual({self.c3, self.c5}, {c["sha"] for c in self.row(B)["commits"]})
        self.assertEqual({self.c6}, {c["sha"] for c in self.row(C)["commits"]})
        self.assertNotIn(self.c4, json.dumps(self.data), "没改 usage 的提交被算进了需求")

    def test_a_mixed_commit_counts_whole_for_each_and_is_marked(self) -> None:
        for key in (A, B):
            c3 = next(c for c in self.row(key)["commits"] if c["sha"] == self.c3)
            self.assertTrue(c3["mixed"])
            self.assertGreaterEqual(c3["added"], 5, "混合提交的行数被拆分或去重了")
        self.assertFalse(next(c for c in self.row(A)["commits"] if c["sha"] == self.c1)["mixed"])

    def test_a_merge_only_counts_what_differs_from_every_parent(self) -> None:
        self.assertNotIn(self.merge, {c["sha"] for c in self.row(B)["commits"]}, "merge 把侧枝已有的改动又算了一次")
        self.assertNotIn(self.merge, {c["sha"] for c in self.row(C)["commits"]})
        self.assertIn(("Eve", "eve@x"), [tuple(x) for x in self.row(A)["committers"]])

    def test_requirements_show_by_number_and_start_and_gaps_are_facts(self) -> None:
        self.assertEqual(("AR1", "20261001T010000.000Z"), (self.row(A)["number"], self.row(A)["stamp"]))
        self.assertEqual(("DTS22", "20261002T010000.000Z"), (self.row(B)["number"], self.row(B)["stamp"]))
        self.assertEqual(["身份未知"], self.row(C)["gaps"])
        self.assertEqual([], self.row(A)["gaps"])
        self.assertFalse({"name", "name_source"} & set(self.row(A)), "还在取需求名称")
        self.assertEqual(self.root.name, self.data["project"], "项目名不是工程目录名")

    def test_the_summary_is_recomputable_from_the_rows(self) -> None:
        s = self.data["summary"]
        self.assertEqual(3, s["requirements"])
        self.assertEqual(6, s["commits"], "去重后的关联提交数不对")
        rows = self.data["requirements"]
        for field in ("added", "deleted"):
            self.assertEqual(sum(r[field] for r in rows), s[field], f"汇总 {field} 不是逐需求之和")
            self.assertEqual(sum(c[field] for r in rows for c in r["commits"]), s[field])
        unique = {c["sha"]: c["added"] for r in rows for c in r["commits"]}
        self.assertEqual(s["added"] - sum(unique.values()), next(c for c in self.row(A)["commits"] if c["sha"] == self.c3)["added"],
                         "混合提交没有在第二个需求里再计一次整笔")
        stat = self.git("show", "--numstat", "--format=", self.c3)
        raw = sum(int(line.split("\t")[0]) for line in stat.splitlines() if line.split("\t")[0].isdigit())
        self.assertEqual(raw, next(c for c in self.row(B)["commits"] if c["sha"] == self.c3)["added"], "不是这笔提交的原始 numstat")
        self.assertEqual(["alice@x", "bob@x", "eve@x"], [d["email"] for d in s["developers"]])
        self.assertEqual({"completed": 2, "timed": 1, "spent_total": 600}, s["steps"]["spec"])
        self.assertEqual([{"agent": None, "model": None, "requirements": 1}, {"agent": "opencode", "model": "m-a", "requirements": 2}],
                         sorted(s["identities"], key=lambda g: str(g["agent"])))
        usage_bytes = (self.root / "doc" / "usage.json").read_bytes()
        self.assertEqual(hashlib.sha256(usage_bytes).hexdigest(), self.data["usage_sha256"])
        self.assertTrue(self.data["record_tracked"])

    def test_the_report_is_left_to_the_model_next_to_the_facts(self) -> None:
        self.assertEqual(Path(self.out["facts"]).parent, Path(self.out["report"]).parent)
        self.assertFalse(Path(self.out["report"]).exists(), "脚本自己写了报告")
        self.assertTrue(Path(self.out["template"]).is_file())


class Gaps(GitRepo):
    @classmethod
    def setUpClass(cls) -> None:
        cls.make_repo()
        cls.commit("init", {"x.txt": "1\n"})

    def test_an_uncommitted_record_is_reported_not_guessed(self) -> None:
        (self.root / "doc").mkdir(exist_ok=True)
        (self.root / "doc/usage.json").write_text(usage({A: node()}), encoding="utf-8")
        data = self.facts()
        self.assertFalse(data["record_tracked"])
        self.assertEqual(["文件未入库", "无提交"], data["requirements"][0]["gaps"])

    def test_an_old_contract_record_stops_the_statistics(self) -> None:
        (self.root / "doc").mkdir(exist_ok=True)
        (self.root / "doc/usage.json").write_text(json.dumps({"schema": 1, "requirements": {"AR1": {
            "name": "甲", "version": "1", "features": ["AR1"], "fw": None, "ext": None, "agent": None, "model": None,
            "steps": {}}}}, ensure_ascii=False), encoding="utf-8")
        out = self.collect()
        self.assertFalse(out["ok"])
        self.assertIn("旧合同", out["error"])

    def test_two_collects_at_once_each_keep_their_own_facts(self) -> None:
        (self.root / "doc").mkdir(exist_ok=True)
        (self.root / "doc/usage.json").write_text(usage({A: node()}), encoding="utf-8")
        outs = []
        threads = [threading.Thread(target=lambda: outs.append(self.collect())) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertTrue(all(o["ok"] for o in outs), outs)
        self.assertNotEqual(outs[0]["facts"], outs[1]["facts"])


class TheArchivedRecordIsSelfContained(GitRepo):
    """记录端在交付前收尾，代码与 usage 一起提交；统计只读这两样，独立代码仓与原现场得出同样的业务事实。"""

    @classmethod
    def setUpClass(cls) -> None:
        from ext_workspace import installed_package
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.package = installed_package()
        cls.root = root = base / "work"
        shutil.copytree(cls.package, root)
        cls.git("init", "-q", "-b", "main")
        # 目标仓的做法：需求目录整体不入库，随代码归档的使用记录只有 doc/usage.json
        cls.commit("项目起点", {"src/app.txt": "1\n", ".gitignore": "doc/features/\n"})
        # 纯 Framework 需求：消费模型照扩展段开始 plan 的工作（begin 建身份），做完、闭环后照同一段收尾——两条命令原样
        section = (root / "AGENTS.md").read_text(encoding="utf-8")
        commands = re.findall(r"`(python doc/extensions/skills/story/scripts/core/usage\.py [^`]+)`", section)

        def run(flag: str) -> subprocess.CompletedProcess:
            command = next(c for c in commands if flag in c)
            args = command.replace("<需求编号>", "AR77").replace("<本阶段>", "plan").split()
            return subprocess.run([sys.executable, *args[1:]], cwd=root, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=cls.env())
        cls.begun = run("--begin")
        reports = root / "doc" / "features" / "AR77" / "plan" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(json.dumps({
            "closure_status": "closed", "gate_fingerprint": "3.0.0:abc",
            "closure_commit": {"committed_at": datetime.now(timezone.utc).isoformat()}}), encoding="utf-8")
        cls.closed = run("--finalize")
        cls.commit("plan 设计落地", {"src/app.txt": "1\n2\n3\n"})
        # 需求目录不入库：工作区里 doc/features 一直在，提交里只有代码与 usage
        # 比的是「同一份 usage 字节与 HEAD」：检出不做换行转换
        cls.git("clone", "-q", "-c", "core.autocrlf=false", str(root), str(base / "clone"))
        cls.clone = base / "clone"

    def stats(self, root: Path) -> dict:
        script = self.package / "doc" / "extensions" / "skills" / "story-stats" / "scripts" / "stats.py"
        out = json.loads(subprocess.run([sys.executable, str(script), "collect", "--project-root", str(root)],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                                        timeout=120, env=self.env()).stdout)
        self.assertTrue(out["ok"], out)
        self.assertFalse(Path(out["facts"]).resolve().is_relative_to(root.resolve()), "统计输出写进了工程")
        return json.loads(Path(out["facts"]).read_text(encoding="utf-8"))

    @staticmethod
    def business(facts: dict) -> dict:
        """业务事实：去掉采集时刻与工程目录名这两样随调用变的。"""
        return {k: v for k, v in facts.items() if k not in ("collected_at", "project")}

    def steps(self) -> dict:
        return next(iter(json.loads((self.root / "doc" / "usage.json").read_text(encoding="utf-8"))["requirements"].values()))["steps"]

    def test_the_closing_command_records_the_last_step(self) -> None:
        self.assertEqual(0, self.begun.returncode, self.begun.stderr)
        self.assertEqual(0, self.closed.returncode, self.closed.stderr)
        self.assertEqual(["plan"], list(self.steps()))
        self.assertIsInstance(self.steps()["plan"]["spent"], int, "从开始工作到收尾没有算出耗时")

    def test_a_clone_without_requirement_folders_gives_the_same_facts(self) -> None:
        self.assertFalse((self.clone / "doc" / "features").exists())
        self.assertEqual("", self.git("log", "--all", "--format=%H", "--", "doc/features"), "需求目录进了提交历史")
        clone, here = self.stats(self.clone), self.stats(self.root)
        self.assertEqual(self.business(here), self.business(clone))
        row = clone["requirements"][0]
        self.assertEqual(("AR77", self.steps()), (row["number"], row["steps"]))
        self.assertNotIn("无提交", row["gaps"], "代码与 usage 的那笔提交没归到需求上")

    def test_the_live_folders_do_not_matter_and_are_not_touched(self) -> None:
        before = self.business(self.stats(self.root))
        fr = self.root / "doc" / "features" / "AR77"
        (fr / "plan" / "reports" / "summary.json").write_text("{坏", encoding="utf-8")
        (fr / ".usage-id").write_text("坏了\n", encoding="utf-8")
        (fr / "detail.json").write_text("{坏", encoding="utf-8")
        (self.root / "doc" / "features" / ".usage-state.json").write_text("{坏", encoding="utf-8")
        raw = (self.root / "doc" / "usage.json").read_bytes()
        status = self.git("status", "--porcelain", "--ignored")
        self.assertEqual(before, self.business(self.stats(self.root)), "现场坏了，统计跟着变")
        self.assertEqual(raw, (self.root / "doc" / "usage.json").read_bytes(), "统计改了 usage")
        self.assertEqual(status, self.git("status", "--porcelain", "--ignored"), "统计在工程里写了东西")

    def test_a_step_the_recorder_did_not_close_is_not_made_up(self) -> None:
        """阶段在现场闭环了而记录端没收尾：统计如实没有这一步，不替它补。"""
        work = Path(self._tmp.name) / "unclosed"
        shutil.copytree(self.clone, work)
        reports = work / "doc" / "features" / "AR77" / "ut" / "reports"
        reports.mkdir(parents=True)
        (reports / "summary.json").write_text(json.dumps({"closure_status": "closed", "closure_commit": {
            "committed_at": "2026-10-22T09:00:00Z"}}), encoding="utf-8")
        self.assertNotIn("ut", self.stats(work)["requirements"][0]["steps"])


class Installed(GitRepo):
    @classmethod
    def setUpClass(cls) -> None:
        cls.make_repo()
        cls.commit("usage", {"doc/usage.json": usage({A: node()})})

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
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=self.env())
        out = json.loads(p.stdout)
        self.assertTrue(out["ok"], out)
        self.assertTrue(Path(out["template"]).read_text(encoding="utf-8").lstrip().startswith("<!--"),
                        "已安装的脚本没指向随包模板")


class HistoryVersions(GitRepo):
    """历史里确实没有 usage 才是空基线；文件在却读不出、Git 查不了，统计停下，不当作空表继续精确归属（I5@3/I6@3）。"""

    def setUp(self) -> None:
        self.make_repo()
        self.addCleanup(type(self)._tmp.cleanup)

    def failed(self) -> str:
        raw = (self.root / "doc" / "usage.json").read_bytes()
        out = self.collect()
        self.assertFalse(out["ok"], out)
        self.assertNotIn("facts", out, "失败了还给出成功的事实路径")
        self.assertEqual(raw, (self.root / "doc" / "usage.json").read_bytes(), "统计改了 usage")
        return out["error"]

    def test_a_project_in_a_subdirectory_reads_its_own_history(self) -> None:
        """工程在仓内子目录：根提交还没有 usage；新增、改动、未变与混合各按节点归属，仓根同名文件不相干。"""
        decoy = {"doc/usage.json": "{坏"}
        self.commit("c0", {**decoy, "app/a.txt": "1\n"})
        c1 = self.commit("c1", {"app/doc/usage.json": usage({A: node()})})
        c2 = self.commit("c2", {"app/doc/usage.json": usage({A: node({"spec": {"spent": 60}}), B: node()})})
        c3 = self.commit("c3", {"app/doc/usage.json": usage({A: node({"spec": {"spent": 60}}), B: node(), C: node()})})
        out = self.collect(self.root / "app")
        self.assertTrue(out["ok"], out)
        rows = {r["key"]: [c["sha"] for c in r["commits"]]
                for r in json.loads(Path(out["facts"]).read_text(encoding="utf-8"))["requirements"]}
        self.assertEqual({A: [c2, c1], B: [c2], C: [c3]}, rows)

    def test_a_broken_version_stops_the_statistics(self) -> None:
        for name, text in (("空文件", ""), ("坏 JSON", "{坏"),
                           ("requirements 不是对象", json.dumps({"schema": 1, "requirements": []}))):
            with self.subTest(name):
                self.setUp()
                self.commit("c1", {"doc/usage.json": usage({A: node()})})
                bad = self.commit("c2", {"doc/usage.json": text})
                self.commit("c3", {"doc/usage.json": usage({A: node(), B: node()})})
                error = self.failed()
                self.assertIn(bad[:12], error)
                self.assertIn("doc/usage.json", error)
                self.assertIn("本次不出统计", error)

    def test_a_version_with_invalid_utf8_bytes_stops_the_statistics(self) -> None:
        """坏字节原样进校验：读取时先替换成 U+FFFD 就成了一份“合法”的历史，照样参与归属。"""
        record = self.root / "doc" / "usage.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_bytes(usage({A: node(agent="AGENT")}).encode("utf-8").replace(b"AGENT", b"ag\xffent"))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c1")
        bad = self.git("rev-parse", "HEAD").strip()
        self.assertIn(b"\xff", subprocess.run(["git", "-C", str(self.root), "show", f"{bad}:doc/usage.json"],
                                              capture_output=True, env=self.env()).stdout, "夹具没把坏字节写进历史")
        self.commit("c2", {"doc/usage.json": usage({A: node(), B: node()})})
        head = self.git("rev-parse", "HEAD")
        error = self.failed()
        self.assertIn(bad[:12], error)
        self.assertIn("UTF-8", error)
        self.assertEqual(head, self.git("rev-parse", "HEAD"), "统计动了 Git")

    def test_a_blob_git_cannot_read_is_an_error_not_an_absent_file(self) -> None:
        self.commit("c1", {"doc/usage.json": usage({A: node()})})
        c2 = self.commit("c2", {"doc/usage.json": usage({A: node({"spec": {"spent": 60}})})})
        self.commit("c3", {"doc/usage.json": usage({A: node({"spec": {"spent": 60}}), B: node()})})
        blob = self.git("rev-parse", f"{c2}:doc/usage.json").strip()
        obj = self.root / ".git" / "objects" / blob[:2] / blob[2:]
        obj.chmod(0o644)                       # Git 把对象写成只读
        obj.unlink()
        error = self.failed()
        self.assertIn(c2[:12], error)
        self.assertIn("查不了", error)

    def test_a_tree_query_that_fails_is_an_error_not_an_absent_file(self) -> None:
        """读树失败用受控替身：被测的是 History 对失败的处理，不是 Git 本身。"""
        import importlib.util  # noqa: PLC0415
        from unittest import mock  # noqa: PLC0415
        self.commit("c1", {"doc/usage.json": usage({A: node()})})
        spec = importlib.util.spec_from_file_location("stats_under_test", STATS)
        stats = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stats)
        real = stats.git

        def git(root, *args, ok=False):
            if args[0] == "ls-tree":
                raise stats.StatsError("git ls-tree 失败（fatal: 替身）")
            return real(root, *args, ok=ok)

        with mock.patch.dict(os.environ, self.env()), mock.patch.object(stats, "git", git):
            with self.assertRaises(stats.StatsError) as caught:
                stats.run(self.root)
        self.assertIn("查不了", str(caught.exception))
        self.assertIn("doc/usage.json", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
