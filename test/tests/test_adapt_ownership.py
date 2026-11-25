"""所有权由目录表达 —— `base/` 整目录随发行替换，`adapters/` 与 `knowledge/` 一寸不碰。

## 为什么有这一份

2.0.6 起目录边界直接表达所有权，并在目标业务工程内就地适配（不再跨仓 `--package` 拷贝）：

    base/           通用机制包，整目录替换（含 package-manifest.yaml、.gitignore、首装临时 examples/）
    adapters/       业务侧对接实现与依赖闭包，升级一个字节不碰
    knowledge/      业务侧知识，升级不读不写
    manifest.yaml   运行时唯一清单：机制登记由 base/package-manifest.yaml 合成，name/description/业务 knowledge 归目标
    adaptation.yaml 目标的对接标记与 adapted_for，归目标

下面锁：边界守得住、状态只读、演进跟进与独审门禁、前置拦得住、使用记录建立与两套 shell 补建命令原样可跑。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml
from ext_workspace import (DEV_BASE, change_versions, copy_host_entries, git_init_excluding_framework,
                           installed_package, link_framework)

REPO = Path(__file__).resolve().parents[2]
#: 已装好开发源的参考工程（含 base/、adapters/、knowledge/、manifest.yaml 与物化好的宿主入口）
PKG_ROOT = installed_package()
PKG_EXT = PKG_ROOT / "doc" / "extensions"
ENTRIES_REF = PKG_EXT / "base" / "skills" / "story-adaptation" / "scripts" / "entries.mjs"
#: 包的版本：`adapted_for` 只会被脚本写成它
PKG_VERSION = yaml.safe_load((DEV_BASE / "package-manifest.yaml").read_text(encoding="utf-8"))["version"]


class AdaptCase(unittest.TestCase):
    """每个用例搭一个「接入了被测 Framework、已装好 base/ 与业务面、已提交」的目标工程，就地跑 `adapt-scan`。"""

    def setUp(self) -> None:  # noqa: D102
        for tool in ("node", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"环境里没有 {tool}")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "target"
        link_framework(self.target)
        (self.target / ".gitignore").write_text(
            "doc/features/**/AR/story-src/drafts/\ndoc/features/**/.usage-input.json\ndoc/features/.usage-stats/\n"
            "doc/features/.usage-state.json*\n/doc/usage.json.lock\n/doc/.usage.json.*.tmp\n", encoding="utf-8")
        shutil.copytree(PKG_EXT, self.target / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*"))
        copy_host_entries(PKG_ROOT, self.target)
        self.ext = self.target / "doc" / "extensions"
        self.base = self.ext / "base"
        self.core = self.base / "skills" / "story" / "scripts" / "core"
        self.adapters = self.ext / "adapters"
        self.scan = self.base / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
        self.entries_script = self.base / "skills" / "story-adaptation" / "scripts" / "entries.mjs"
        # 已适配到本版的目标有使用记录：由适配建立的空表（没有使用记录的情形由各用例自己删掉）
        (self.target / "doc" / "usage.json").write_text('{\n  "schema": 1,\n  "requirements": {}\n}\n', encoding="utf-8")
        self.commit("baseline")

    # ---- 驱动 ----

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.target), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)

    def commit(self, message: str) -> None:
        if not (self.target / ".git").exists():
            git_init_excluding_framework(self.target)
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", message)

    def adapt(self, mode: str, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(self.scan), mode, *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def out(self, proc: subprocess.CompletedProcess) -> str:
        return ((proc.stdout or "") + (proc.stderr or "")).strip()

    def make_fresh(self) -> None:
        """退回首装态：仅保留刚解包到位的 `doc/extensions/base/`，无 manifest/knowledge/adapters，宿主入口按空仓物化。"""
        shutil.rmtree(self.ext)
        proc = subprocess.run(["node", str(ENTRIES_REF), "--project-root", str(self.target), "--action", "materialize"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, self.out(proc))
        shutil.copytree(DEV_BASE, self.base, ignore=shutil.ignore_patterns("__pycache__"))
        self.commit("空仓解包 base")

    def write_review(self, *, digest: str | None = None, verdict: str = "PASS", skip: int = 0,
                     dup_pass: bool = False) -> None:
        """独立审查者交回的证据块：摘要与激活清单取自 `--status`，四个维度逐份给结论。"""
        knowledge = json.loads(self.adapt("--status").stdout)["knowledge"]
        files = knowledge["files"][skip:]
        dims = lambda v: "".join(f"      {d}: {{verdict: {v}, evidence: 核过 {d}}}\n"  # noqa: E731
                                 for d in ("granularity", "fact_use", "duplication", "coding_boundary"))
        rows = "".join(f"    - path: {f}\n{dims(verdict)}" for f in files)
        if dup_pass and files:
            rows += f"    - path: {files[0]}\n{dims('PASS')}"
        review = self.ext / ".adapt" / "knowledge-review.md"
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text("# 知识独审\n\n```yaml\nknowledge_review:\n"
                          f"  digest: \"{digest or knowledge['digest']}\"\n  executor: subagent-run-1\n"
                          f"  files:\n{rows}  blocking: []\n  unreviewed: []\n```\n", encoding="utf-8")


class TheTargetKeepsWhatIsItsOwn(AdaptCase):
    """`adapters/` 与 `knowledge/` 归目标，升级碰都不碰。"""

    def test_a_clean_target_passes(self) -> None:
        proc = self.adapt("--check")
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_an_upgrade_leaves_the_adapters_untouched(self) -> None:
        mine = "// 这个仓自己实现的\nmodule.exports = {};\n"
        for name in ("story.js", "token.js"):
            (self.adapters / name).write_text(mine, encoding="utf-8")
        self.commit("目标自己实现对接层")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        for name in ("story.js", "token.js"):
            self.assertEqual(mine, (self.adapters / name).read_text(encoding="utf-8"),
                             f"升级动了 {name}——那是目标自己实现的")

    def test_dependencies_under_the_adapters_dir_are_free(self) -> None:
        """对接层的依赖闭包也归目标：`package.json`、`node_modules/` 一律不碰。"""
        (self.adapters / "package.json").write_text(
            json.dumps({"name": "story-adapters", "dependencies": {"axios": "^1"}}),
            encoding="utf-8")
        dep = self.adapters / "node_modules" / "axios" / "lib"
        dep.mkdir(parents=True)
        (dep / "axios.js").write_text("module.exports = {};\n", encoding="utf-8")
        (self.adapters / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
        self.commit("目标装了对接层的依赖")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertTrue((dep / "axios.js").is_file(), "升级把对接层的依赖删了")
        check = self.adapt("--check")
        self.assertEqual(0, check.returncode, self.out(check))

    def test_an_upgrade_leaves_the_knowledge_untouched(self) -> None:
        """知识归目标：升级不读不写，正文与激活清单都不动（A2）。"""
        mine = self.ext / "knowledge" / "facts" / "component-profile.md"
        body = "---\nname: 我的画像\nkind: facts\nform: facets\n---\n\n# 这个仓自己写的\n"
        mine.write_text(body, encoding="utf-8")
        self.commit("目标写了自己的画像")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual(body, mine.read_text(encoding="utf-8"), "升级盖掉了目标的知识")


class TheManifestAndLayoutFollowOwnership(AdaptCase):
    """一个 manifest 两种所有权；旧混装目录在升级时退场，--package 参数已退出。"""

    def test_the_manifest_keeps_the_targets_knowledge_list(self) -> None:
        """机制登记取自 base/package-manifest.yaml，业务 provides.knowledge 跟目标。"""
        manifest = self.ext / "manifest.yaml"
        (self.ext / "knowledge" / "facts" / "own-profile.md").write_text(
            "---\nname: 自己的画像\nkind: facts\nform: facets\n"
            "applies_when: 判断需求归不归本部件时读：本部件是谁\n---\n\n## 职责\n\n负责本部件的业务。\n",
            encoding="utf-8")
        text = manifest.read_text(encoding="utf-8")
        head, _, tail = text.partition("  knowledge:\n")
        keep = tail.split("\n  hooks:", 1)[1]
        entry = ("    - path: base/skills/story-knowledge/SKILL.md\n"
                 "      summary: 各阶段知识装配入口\n"
                 "      audience: [spec, plan, coding, review, ut, testing]\n")
        manifest.write_text(head + "  knowledge:\n" + entry + "    - knowledge/facts/own-profile.md\n  hooks:" + keep,
                            encoding="utf-8")
        rendered = subprocess.run(["node", str(self.entries_script), "--project-root", str(self.target), "--action", "materialize"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, rendered.returncode, self.out(rendered))
        self.commit("目标只激活一份知识")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("    - knowledge/facts/own-profile.md\n", after)
        self.assertIn("base/skills/story-knowledge/SKILL.md", after)
        self.assertNotIn("knowledge/constraints/ux-consistency.md", after,
                         "升级把样例知识塞给了目标——知识激活随目标")
        self.assertIn("base/hooks/spec/post_check.mjs", after, "机制登记没跟上 base/package-manifest.yaml")

    def test_retired_package_flag_is_refused(self) -> None:
        proc = self.adapt("--apply", "--package", str(PKG_ROOT))
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("--package", self.out(proc))


class StatusCase(AdaptCase):
    """只读状态视图的辅助：跑 `--status` 并核前后文件一字不变。本类不含用例。"""

    def tree(self) -> dict[str, bytes]:
        return {p.relative_to(self.target).as_posix(): p.read_bytes()
                for p in self.target.rglob("*") if p.is_file() and ".git" not in p.parts}

    def status(self) -> tuple[int, dict]:
        before = self.tree()
        proc = self.adapt("--status")
        self.assertEqual(before, self.tree(), "--status 写了文件")
        return proc.returncode, json.loads(proc.stdout)


class TheStatusViewOnlyReads(StatusCase):
    """`--status`：只读；未安装、坏清单、坏配置分别是不同的事实。"""

    def test_an_installed_target_reports_versions_counts_and_digest(self) -> None:
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual(PKG_VERSION, got["package"]["version"])
        self.assertTrue(got["target"]["installed"])
        self.assertEqual("PASS", got["knowledge"]["status"])
        self.assertTrue(got["knowledge"]["counts"])
        self.assertTrue(got["knowledge"]["digest"].startswith("sha256:"))
        self.assertTrue(got["history"].startswith("unknown"), "读不到的历史没说成未知")

    def test_a_fresh_install_checks_clean_and_writes_nothing(self) -> None:
        self.make_fresh()
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.commit("装好")
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("PASS", got["knowledge"]["status"])
        self.assertEqual({}, got["knowledge"]["counts"])
        self.assertTrue(got["items"]["知识"], "从未适配的目标没从知识基线列起")
        self.assertFalse((self.target / "doc" / "features").exists(), "检查造了需求目录")

    def test_not_installed_is_a_fact_not_an_error(self) -> None:
        self.make_fresh()
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("not_installed", got["state"])
        self.assertNotIn("knowledge", got, "没装的目标报出了知识结果")

    def test_broken_knowledge_exits_one_with_the_file(self) -> None:
        manifest = self.ext / "manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace(
            "  knowledge:\n", "  knowledge:\n    - knowledge/facts/gone.md\n", 1), encoding="utf-8")
        code, got = self.status()
        self.assertEqual(1, code)
        self.assertEqual("FAIL", got["knowledge"]["status"])
        self.assertIn("knowledge/facts/gone.md", "\n".join(got["knowledge"]["problems"]))

    def test_an_unreadable_config_is_an_input_error(self) -> None:
        (self.target / "framework.config.json").write_text("{坏了", encoding="utf-8")
        code, got = self.status()
        self.assertEqual(2, code)
        self.assertEqual("config", got["error"]["category"])
        self.assertIn("framework.config.json", got["error"]["message"])

    def test_after_an_upgrade_the_items_follow_the_current_cursor(self) -> None:
        (self.ext / "adaptation.yaml").write_text('adapters: stand-in\nadapted_for: "1.9.6"\n', encoding="utf-8")
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("1.9.6", got["target"]["adapted_for"])
        self.assertTrue(all(tuple(map(int, i.split("：", 1)[0].split("."))) > (1, 9, 6)
                            for i in got["items"]["知识"]), got["items"])
        self.assertNotIn("在途单", got["items"], "adapt 不处理旧需求，跟进里不该有在途单块")

    def test_a_target_on_2_0_3_gets_the_newer_knowledge_and_adapter_topics(self) -> None:
        """游标在 2.0.3：跟进里含 2.0.4/2.0.5 知识主题与 2.0.5+ 对接层条目；机制升级不改目标知识。"""
        (self.ext / "adaptation.yaml").write_text('adapters: stand-in\nadapted_for: "2.0.3"\n', encoding="utf-8")
        code, got = self.status()
        self.assertEqual(0, code, got)
        topics = got["items"]["知识"]
        self.assertEqual(["2.0.4", "2.0.4", "2.0.5", "2.0.5", "2.0.5"],
                         [t.split("：", 1)[0] for t in topics[:5]], topics)
        self.assertIn("工程能力", topics[0])
        self.assertIn("性能与资源引入", topics[1])
        for theme in ("蓝图唯一决定", "Story 评审回流", "原话与知识验收责任"):
            self.assertTrue(any(theme in t for t in topics[2:]), (theme, topics))
        adapter_versions = [i.split("：", 1)[0] for i in got["items"]["对接层"]]
        self.assertIn("2.0.5", adapter_versions, got["items"])
        self.assertTrue(any("review_out" in i for i in got["items"]["对接层"]))
        self.assertNotIn("目标仓已采用", json.dumps(topics, ensure_ascii=False), "把待判断的主题写成了目标已采用")


class SameUseCandidatesAreOnlyHints(StatusCase):
    """同用途声明候选只按 `applies_when` 原文相同分组，给独立审查当线索。"""

    def set_applies(self, name: str, text: str) -> None:
        f = self.ext / "knowledge" / "facts" / name
        rows = [f"applies_when: {text}" if l.startswith("applies_when:") else l
                for l in f.read_text(encoding="utf-8").split("\n")]
        f.write_text("\n".join(rows), encoding="utf-8")

    def test_the_same_declared_use_is_listed_without_changing_the_verdict(self) -> None:
        self.set_applies("component-profile.md", "设计要用项目已有能力时：在哪、怎么用")
        self.set_applies("engineering-capabilities.md", "  设计要用项目已有能力时：在哪、怎么用  ")
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("PASS", got["knowledge"]["status"])
        self.assertEqual("同用途声明候选，须语义核对", got["knowledge"]["sameUse"]["note"])
        files = [g["files"] for g in got["knowledge"]["sameUse"]["groups"]]
        self.assertIn(sorted(["knowledge/facts/component-profile.md", "knowledge/facts/engineering-capabilities.md"]),
                      [sorted(f) for f in files])

    def test_different_wording_is_not_claimed_free_of_duplicates(self) -> None:
        self.set_applies("component-profile.md", "查本部件边界时")
        self.set_applies("engineering-capabilities.md", "查已有能力时")
        code, got = self.status()
        self.assertEqual(0, code, got)
        listed = [f for g in got["knowledge"]["sameUse"]["groups"] for f in g["files"]]
        self.assertNotIn("knowledge/facts/component-profile.md", listed)
        self.assertNotIn("无重复", json.dumps(got, ensure_ascii=False))


class TheIndependentReviewIsDeliveredBeforeMarking(unittest.TestCase):
    """独立审查的任务页交付四个维度，SKILL 与方法页在 --mark-adapted 之前送达它。"""

    REF = DEV_BASE / "skills" / "story-adaptation"

    def test_the_task_page_names_the_four_dimensions_and_its_inputs(self) -> None:
        page = (self.REF / "reference" / "knowledge-review.md").read_text(encoding="utf-8")
        for dim in ("条目粒度与归类", "项目事实的用途", "跨文件重复", "编码规范边界"):
            self.assertIn(dim, page)
        for given in ("knowledge.digest", "knowledge.sameUse", "正常需求", "未审"):
            self.assertIn(given, page)

    def test_the_review_comes_before_marking_in_both_entry_pages(self) -> None:
        for rel in ("SKILL.md", "reference/knowledge-adaptation.md"):
            text = (self.REF / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertIn("knowledge-review.md", text)
                self.assertLess(text.index("knowledge-review.md"), text.rindex("--mark-adapted"))


class TheUpgradeFollowsTheVersionRecord(AdaptCase):
    """升级后按演进记录（晚于目标 adapted_for 的条目）与只读检查决定问不问人；选稍后不落盘任何文件。"""

    def set_adapted(self, version: str) -> None:
        (self.ext / "adaptation.yaml").write_text(
            f'adapters: stand-in\nadapted_for: "{version}"\n', encoding="utf-8")
        self.commit(f"知识按 {version} 适配过")

    def test_newer_protocol_entries_are_listed_and_asked(self) -> None:
        self.set_adapted("1.9.6")
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("1.9.7：每份知识的 frontmatter 写齐", proc.stdout)
        self.assertIn("停一次问人「现在做这些适配吗」", proc.stdout)
        for older in ("1.9.4：", "1.9.5：", "1.9.6："):
            self.assertNotIn(older, proc.stdout, "已适配过的版本又列了一遍")
        adaptation = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        self.assertIn('adapted_for: "1.9.6"', adaptation, "没等人选就写了适配版本")

    def test_a_knowledge_breach_is_listed_and_asked(self) -> None:
        fact = next((self.ext / "knowledge" / "facts").glob("*.md"))
        fact.write_text(fact.read_text(encoding="utf-8").replace("\nform:", "\nshape:", 1), encoding="utf-8")
        self.commit("有一份知识没写 form")
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn('"status":"FAIL"', proc.stdout)
        self.assertIn(f"{fact.name} 的 frontmatter 缺 form", proc.stdout)
        self.assertIn("停一次问人", proc.stdout)

    def test_nothing_to_adapt_is_one_sentence_and_records_the_version(self) -> None:
        self.set_adapted(PKG_VERSION)
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("目标已按包的版本适配", proc.stdout)
        self.assertNotIn("停一次问人", proc.stdout)
        adaptation = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', adaptation, "无事可做却没记下已按包的版本适配")
        self.assertEqual("", self.git("status", "--porcelain", "--", "doc/extensions/knowledge").stdout.strip(),
                         "只是提示却写了知识")
        self.assertEqual(0, self.adapt("--check").returncode, "写了 adapted_for 之后核对不再通过")

    def test_a_target_without_adapted_for_starts_from_the_knowledge_baseline(self) -> None:
        adaptation = self.ext / "adaptation.yaml"
        adaptation.write_text("adapters: stand-in\n", encoding="utf-8")
        self.commit("没写过 adapted_for")
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        knowledge = json.loads(line.split("按版本跟进：", 1)[1])["items"]["知识"]
        self.assertEqual(set(change_versions(PKG_EXT, "知识")), {i.split("：", 1)[0] for i in knowledge},
                         "没从知识基线起列全各版知识条目")
        self.assertIn("停一次问人", proc.stdout)
        self.assertIn("条目是待判断的适配主题", proc.stdout, "跟进没把「待判断」与「目标已采用」分开")
        self.assertNotIn("adapted_for", adaptation.read_text(encoding="utf-8"), "没等人做完就写了适配版本")


class TheUpgradeRecordKeepsTheOldSiteBoundary(unittest.TestCase):
    """2.0.5 起旧流程契约不迁移：记录写明原版收口/新 init 与保原件，主题只写待判断，不写成目标已采用。"""

    RECORD = DEV_BASE / "skills" / "story-adaptation" / "reference" / "upgrade-changes.md"

    def section(self) -> str:
        text = self.RECORD.read_text(encoding="utf-8")
        self.assertIn("## 2.0.5", text, "演进记录没有 2.0.5 一节")
        after = text.split("## 2.0.5", 1)[1]
        return after.split("\n## ", 1)[0]

    def test_it_names_the_old_site_boundary_and_keeps_originals(self) -> None:
        section = self.section()
        for needle in ("schema 6", "原版", "init", "原件", "不盘点", "在途"):
            with self.subTest(needle=needle):
                self.assertIn(needle, section)

    def test_the_topics_are_checks_on_target_knowledge_not_adoption_claims(self) -> None:
        section = self.section()
        self.assertIn("不表示目标仓已经采用", section)
        topics = [l for l in section.splitlines() if l.startswith("- [知识]")]
        self.assertTrue(topics, "2.0.5 没有知识主题")
        for line in topics:
            with self.subTest(topic=line[:24]):
                self.assertIn("目标知识", line)
                self.assertIn("核：", line)

    def test_the_topics_keep_real_business_requirements_and_only_remove_the_runtime_text(self) -> None:
        topics = [l for l in self.section().splitlines() if l.startswith("- [知识]")]
        self.assertEqual(3, len(topics), "2.0.5 的知识主题条数变了：先核这些断言是否还对着同一批主题")
        for line in topics:
            with self.subTest(topic=line[:24]):
                for needle in ("真实", "保留", "只删掉混进目标知识的", "已安装机制"):
                    self.assertIn(needle, line, f"升级主题少了「{needle}」")
                for gone in ("改为指向蓝图 gap/decision", "改为上面这条链", "改为蓝图设计形成"):
                    self.assertNotIn(gone, line, f"升级主题又把 Extension 的阶段与路径写回目标知识：{gone}")


class TheAdaptedVersionIsWrittenByTheScript(AdaptCase):
    """`--mark-adapted` 核入口/知识/独审、清理 base/examples/（保留 base/.gitignore）并最后写 adapted_for。"""

    def mark(self) -> subprocess.CompletedProcess:
        return self.adapt("--mark-adapted")

    def set_manifest_line(self, key: str, value: str) -> None:
        if key == "adapted_for":
            (self.ext / "adaptation.yaml").write_text(f'adapters: stand-in\nadapted_for: "{value}"\n', encoding="utf-8")
        else:
            manifest = self.ext / "manifest.yaml"
            rows = [f'{key}: "{value}"' if l.startswith(f"{key}:") else l
                    for l in manifest.read_text(encoding="utf-8").split("\n")]
            manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(f"{key} {value}")

    def test_it_writes_the_package_version_and_the_check_still_passes(self) -> None:
        self.set_manifest_line("adapted_for", "1.9.6")
        self.write_review()
        proc = self.mark()
        self.assertEqual(0, proc.returncode, self.out(proc))
        adaptation = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', adaptation)
        self.assertFalse((self.base / "examples").exists(), "完成后应清理 base/examples/")
        self.assertTrue((self.base / ".gitignore").is_file(), "清理后必须保留 base/.gitignore")
        self.assertEqual(0, self.adapt("--check").returncode, self.out(self.adapt("--check")))

    def test_knowledge_due_for_adaptation_needs_matching_independent_evidence(self) -> None:
        self.set_manifest_line("adapted_for", "1.9.2")
        before = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        cases = {"缺审": (None, "missing"), "过期": ({"digest": "sha256:0000000000000000"}, "stale"),
                 "漏一份": ({"skip": 1}, "incomplete"), "判 FAIL": ({"verdict": "FAIL"}, "incomplete"),
                 "未知": ({"verdict": "UNKNOWN"}, "incomplete"), "非法值": ({"verdict": "OK"}, "incomplete"),
                 "重复盖住 FAIL": ({"verdict": "FAIL", "dup_pass": True}, "incomplete")}
        for name, (kw, status) in cases.items():
            with self.subTest(name):
                review = self.ext / ".adapt" / "knowledge-review.md"
                review.unlink(missing_ok=True)
                if kw is not None:
                    self.write_review(**kw)
                status_json = json.loads(self.adapt("--status").stdout)
                self.assertEqual(status, status_json["knowledge"]["review"]["status"])
                proc = self.mark()
                self.assertEqual(2, proc.returncode, self.out(proc))
                self.assertIn("知识适配未完成", self.out(proc))
                self.assertEqual(before, (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))
        self.write_review()
        self.assertEqual(0, self.mark().returncode)
        fact = next((self.ext / "knowledge" / "facts").glob("*.md"))
        fact.write_text(fact.read_text(encoding="utf-8") + "\n补一句。\n", encoding="utf-8")
        self.assertEqual("stale", json.loads(self.adapt("--status").stdout)["knowledge"]["review"]["status"],
                         "知识改过之后旧结论还盖着新内容")

    def test_a_mechanism_only_upgrade_needs_no_review(self) -> None:
        latest = change_versions(PKG_EXT, "知识")[-1]
        self.set_manifest_line("adapted_for", latest)
        proc = self.mark()
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_it_stops_when_the_target_has_no_manifest(self) -> None:
        self.make_fresh()
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("还没装过", self.out(proc))
        self.assertFalse((self.ext / "manifest.yaml").exists(), "没装过却写了 manifest")

    def test_it_stops_before_the_mechanism_is_upgraded(self) -> None:
        self.set_manifest_line("version", "1.9.7")
        before = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("把机制升到包的版本", self.out(proc))
        self.assertEqual(before, (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))

    def test_it_stops_when_the_knowledge_does_not_load(self) -> None:
        fact = next((self.ext / "knowledge" / "facts").glob("*.md"))
        fact.write_text(fact.read_text(encoding="utf-8").replace("\nform:", "\nshape:", 1), encoding="utf-8")
        self.commit("有一份知识没写 form")
        before = (self.ext / "adaptation.yaml").read_text(encoding="utf-8")
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(fact.name, self.out(proc))
        self.assertEqual(before, (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))


class ThePreflightStopsInsteadOfGuessing(AdaptCase):
    """前置不满足就停，不猜、不替用户动工作区。"""

    def test_a_dirty_write_face_stops_the_upgrade(self) -> None:
        """写入面上（宿主入口）有未提交改动就停——盖掉了在 diff 里还看不出来。"""
        entry = self.target / ".claude" / "commands" / "story.md"
        entry.write_text("目标改了一半没提交\n", encoding="utf-8")
        proc = self.adapt("--apply")
        self.assertEqual(2, proc.returncode, "工作区脏却照写了")
        self.assertIn(".claude/commands/story.md", self.out(proc), "停了却没点名是哪个文件脏")
        self.assertEqual("目标改了一半没提交\n", entry.read_text(encoding="utf-8"), "停之前已经写过盘了")

    def test_a_target_outside_git_stops_the_upgrade(self) -> None:
        import os  # noqa: PLC0415
        (self.target / ".git").rename(self.target.parent / "git-moved-away")
        proc = subprocess.run(
            ["node", str(self.scan), "--apply"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(self.target.parent)})
        self.assertEqual(2, proc.returncode, "没有 git 却照写了")
        self.assertIn("git", self.out(proc))

    def test_running_twice_says_the_mechanism_is_current(self) -> None:
        first = self.adapt("--apply")
        self.assertEqual(0, first.returncode, self.out(first))
        self.commit("第一次升级")
        second = self.adapt("--apply")
        self.assertEqual(0, second.returncode, self.out(second))
        self.assertIn("机制已在包的版本上", self.out(second))


class AFreshInstallRunsOutOfTheBox(AdaptCase):
    """空仓解包 base/ 后 `--apply` 就能跑：业务知识清单为空，机制入口可用，首装完成后清理 examples/。"""

    def setUp(self) -> None:  # noqa: D102
        super().setUp()
        self.make_fresh()

    def test_the_manifest_registers_no_business_knowledge_and_writes_none(self) -> None:
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        manifest = yaml.safe_load((self.ext / "manifest.yaml").read_text(encoding="utf-8"))
        biz = [k for k in manifest["provides"]["knowledge"]
               if (k["path"] if isinstance(k, dict) else k) != "base/skills/story-knowledge/SKILL.md"]
        self.assertEqual([], biz, "首次安装替目标激活了业务知识")
        self.assertRegex(manifest["name"], r"^[a-z][a-z0-9_-]*$", "Framework 只认小写 slug 的 name")
        written = [p for p in (self.ext / "knowledge").rglob("*") if p.is_file()] if (self.ext / "knowledge").exists() else []
        self.assertEqual([], written, "脚本往目标的 knowledge/ 写了东西")
        self.assertEqual("{}\n", (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))

    def test_the_derivation_runs_on_a_fresh_install(self) -> None:
        self.assertEqual(0, self.adapt("--apply").returncode)
        probe = (
            "const k = await import(process.argv[1]);"
            "const kn = k.activeKnowledge(process.argv[2]);"
            "process.stdout.write(JSON.stringify({"
            "  facts: kn.facts.length, constraints: kn.constraints.length,"
            "  patterns: kn.patterns.length, entries: kn.entries.length,"
            "  problems: k.selfCheck(process.argv[2], kn).length }));"
        )
        module = (self.base / "hooks" / "shared" / "knowledge.mjs").resolve().as_uri()
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", probe, module, str(self.target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, f"空仓装完派生就抛了：{proc.stderr}")
        self.assertEqual({"facts": 0, "constraints": 0, "patterns": 0,
                          "entries": 0, "problems": 0}, json.loads(proc.stdout))

    def place_real_adapters(self) -> None:
        self.adapters.mkdir(parents=True, exist_ok=True)
        for name in ("story.js", "token.js"):
            (self.adapters / name).write_text(f"// real {name}\nmodule.exports = {{}};\n", encoding="utf-8")

    def test_a_fresh_install_passes_its_own_check(self) -> None:
        self.assertEqual(0, self.adapt("--apply").returncode)
        # S28：缺真实对接层时 --check 报尚欠事项，补齐后通过
        missing = self.adapt("--check")
        self.assertEqual(1, missing.returncode, self.out(missing))
        self.assertIn("story.js", self.out(missing))
        self.assertIn("token.js", self.out(missing))
        self.place_real_adapters()
        proc = self.adapt("--check")
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_a_fresh_install_lists_the_knowledge_baseline_and_leaves_adapted_for_to_the_script(self) -> None:
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertNotIn("adapted_for", (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))
        self.assertIn("--mark-adapted", proc.stdout)
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        items = json.loads(line.split("按版本跟进：", 1)[1])["items"]
        self.assertEqual(set(change_versions(PKG_EXT, "知识")), {i.split("：", 1)[0] for i in items["知识"]},
                         "首次没从知识基线起拿到各版知识条目")
        self.assertNotIn("在途单", items, "adapt 不处理旧需求，跟进里不该有在途单块")
        self.commit("首次装好")
        self.assertEqual(2, self.adapt("--mark-adapted").returncode, "首装未独审却记成已适配")
        self.write_review()
        # 独审已过但真实对接未就位：--mark-adapted 必须阻止、保留样例与游标
        no_ad = self.adapt("--mark-adapted")
        self.assertEqual(2, no_ad.returncode, self.out(no_ad))
        self.assertIn("对接层未就位", self.out(no_ad))
        self.assertTrue((self.base / "examples").is_dir(), "缺真实对接时不应清理 base/examples/")
        self.assertNotIn("adapted_for", (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))
        self.place_real_adapters()
        marked = self.adapt("--mark-adapted")
        self.assertEqual(0, marked.returncode, self.out(marked))
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', (self.ext / "adaptation.yaml").read_text(encoding="utf-8"))
        self.assertFalse((self.base / "examples").exists(), "首装完成应清理 base/examples/")
        self.assertTrue((self.base / ".gitignore").is_file(), "首装清理后必须保留 base/.gitignore")
        self.assertEqual(0, self.adapt("--check").returncode)


class ThePackageKeepsItsOwnDirectoriesStraight(AdaptCase):
    """`base/skills/story/scripts/` 下只有 `core/`，不含任何替身 adapters 或游离脚本。"""

    def test_the_package_scripts_dir_has_only_core(self) -> None:
        at = DEV_BASE / "skills" / "story" / "scripts"
        dirs = sorted(p.name for p in at.iterdir() if p.is_dir() and p.name != "__pycache__")
        self.assertEqual(["core"], dirs)
        files = sorted(p.name for p in at.iterdir() if p.is_file())
        self.assertEqual([], files, "base/skills/story/scripts/ 根下多了文件")

    def test_a_stray_file_in_base_scripts_is_named(self) -> None:
        (self.base / "skills" / "story" / "scripts" / "loose.mjs").write_text(
            "export const x = 1;\n", encoding="utf-8")
        proc = self.adapt("--check")
        self.assertEqual(1, proc.returncode, "base scripts 根下有游离脚本却判通过了")
        self.assertIn("loose.mjs", self.out(proc))


class TheUsageRecordIsSetUpByApply(AdaptCase):
    """adapt 给业务仓建立可入库的 `doc/usage.json`：缺了建空表，在了逐字节保留，检查只读，坏了不覆盖。"""

    EMPTY = {"schema": 1, "requirements": {}}
    REAL = ('{"schema":1,"requirements":{"AR1-20261021T080102.123Z":{"ext":"1.9.9","fw":null,'
            '"agent":null,"model":null,"steps":{"story":{"spent":1656}}}}}')

    def setUp(self) -> None:  # noqa: D102
        super().setUp()
        self.record = self.target / "doc" / "usage.json"

    def without_record(self, message: str = "还没有使用记录") -> None:
        self.record.unlink()
        self.commit(message)

    def doc_listing(self) -> list[str]:
        return sorted(p.name for p in (self.target / "doc").iterdir())

    def assert_set_up(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual(self.EMPTY, json.loads(self.record.read_text(encoding="utf-8")))
        self.assertIn("已建立使用记录 doc/usage.json", proc.stdout)
        self.assertIn("一起提交", proc.stdout)
        self.git("add", "doc/usage.json")
        self.assertIn("A  doc/usage.json", self.git("status", "--porcelain", "doc/usage.json").stdout, "普通 git add 加不进去")
        self.assertEqual(0, self.adapt("--check").returncode, self.out(self.adapt("--check")))

    def test_an_upgrade_from_an_older_version_sets_it_up(self) -> None:
        manifest = self.ext / "manifest.yaml"
        manifest.write_text("\n".join('version: "1.9.8"' if l.startswith("version:") else l
                                      for l in manifest.read_text(encoding="utf-8").split("\n")), encoding="utf-8")
        self.without_record("1.9.8 的仓")
        proc = self.adapt("--apply")
        self.assertIn("升级完成", proc.stdout)
        self.assert_set_up(proc)

    def test_a_fresh_install_and_a_same_version_rerun_set_it_up(self) -> None:
        self.make_fresh()
        self.adapters.mkdir(parents=True, exist_ok=True)
        for name in ("story.js", "token.js"):
            (self.adapters / name).write_text(f"// real {name}\nmodule.exports = {{}};\n", encoding="utf-8")
        self.without_record("空仓")
        self.assert_set_up(self.adapt("--apply"))
        self.commit("装好")
        self.without_record("使用记录被删了")
        proc = self.adapt("--apply")
        self.assertIn("机制已在包的版本上", proc.stdout)
        self.assert_set_up(proc)

    def test_an_existing_record_is_kept_byte_for_byte(self) -> None:
        for text in ('{\n  "schema": 1,\n  "requirements": {}\n}\n', self.REAL):
            with self.subTest(text=text[:20]):
                self.record.write_text(text, encoding="utf-8")
                proc = self.adapt("--apply")
                self.assertEqual(0, proc.returncode, self.out(proc))
                self.assertIn("已在且合法，保留未动", proc.stdout)
                self.assertEqual(text, self.record.read_text(encoding="utf-8"))
                self.git("checkout", "--", "AGENTS.md")

    def test_status_and_check_only_read(self) -> None:
        self.without_record()
        before = self.doc_listing()
        check = self.adapt("--check")
        self.assertEqual(1, check.returncode, self.out(check))
        self.assertIn("④ 使用记录：doc/usage.json 不存在", self.out(check))
        self.assertIn("跑 --apply 建立", self.out(check))
        self.adapt("--status")
        self.assertEqual(before, self.doc_listing(), "检查命令建了文件、锁或临时文件")

    def test_a_bad_record_stops_apply_before_anything_is_written(self) -> None:
        manifest = self.ext / "manifest.yaml"
        stale = manifest.read_text(encoding="utf-8").replace(f'version: "{PKG_VERSION}"', 'version: "1.9.8"', 1)
        for name, text in {"坏 JSON": "{ 坏了", "冲突标记": '<<<<<<< HEAD\n{"schema": 1}\n=======\n{}\n>>>>>>> b\n',
                           "旧 schema": '{"schema": 0, "requirements": {}}'}.items():
            with self.subTest(name):
                manifest.write_text(stale, encoding="utf-8")
                self.record.write_text(text, encoding="utf-8")
                self.commit(name)
                proc = self.adapt("--apply")
                self.assertEqual(2, proc.returncode, self.out(proc))
                self.assertIn("不合法", self.out(proc))
                self.assertIn("机制一个字节没写", self.out(proc))
                self.assertEqual(text, self.record.read_text(encoding="utf-8"))
                self.assertEqual(stale, manifest.read_text(encoding="utf-8"), "坏记录却先写了 manifest")

    def test_an_ignored_record_is_not_called_a_finished_adaptation(self) -> None:
        self.without_record()
        exclude = self.target / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + "\n/doc/usage.json\n", encoding="utf-8")
        proc = self.adapt("--apply")
        self.assertEqual(1, proc.returncode, self.out(proc))
        self.assertIn("仍被", proc.stdout)
        self.assertIn("未解决前适配不算完成", proc.stdout)
        self.assertNotIn("升级完成", proc.stdout)

    def test_a_record_that_cannot_be_written_gives_the_one_repair(self) -> None:
        self.without_record()
        lock = self.target / "doc" / "usage.json.lock"
        lock.mkdir()
        proc = self.adapt("--apply")
        self.assertEqual(1, proc.returncode, self.out(proc))
        self.assertIn("没有建立", proc.stdout)
        self.assertIn("不用重跑 --apply", proc.stdout)
        self.assertFalse(self.record.exists())
        lock.rmdir()
        line = repair_line(proc.stdout)
        done = run_in_shell(line, cwd=PKG_ROOT)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertEqual(self.EMPTY, json.loads(self.record.read_text(encoding="utf-8")))
        self.assertEqual(0, self.adapt("--check").returncode, self.out(self.adapt("--check")))


def repair_line(stdout: str) -> str:
    """apply 输出里那一行补建命令：提示句的下一行，原样取出。"""
    lines = stdout.splitlines()
    at = next(i for i, l in enumerate(lines) if "只补这一份" in l)
    return lines[at + 1].strip()


def run_in_shell(line: str, *, cwd: Path, shell: str | None = None) -> subprocess.CompletedProcess:
    """按命令打印时所针对的宿主 shell 原样执行，不拆参数。"""
    shell = shell or ("bash" if __import__("os").environ.get("SHELL") else "powershell")
    argv = ["powershell", "-NoProfile", "-Command", line] if shell == "powershell" else ["bash", "-c", line]
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


class TheRepairLineRunsAsPrinted(unittest.TestCase):
    """补建那一行在两种宿主 shell 下原样可跑：目标根带单引号、空格与中文，扩展目录自定义且带空格，从别的目录执行。"""

    def setUp(self) -> None:  # noqa: D102
        import os  # noqa: PLC0415
        for tool in ("node", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"环境里没有 {tool}")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.os = os

    def make_target(self, name: str) -> Path:
        target = Path(self._tmp.name) / name
        target.mkdir(parents=True)
        link_framework(target)
        config = json.loads((target / "framework.config.json").read_text(encoding="utf-8"))
        config.setdefault("paths", {})["extension_dir"] = "doc/my ext"
        (target / "framework.config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        shutil.copytree(DEV_BASE, target / "doc" / "my ext" / "base", ignore=shutil.ignore_patterns("__pycache__"))
        ad = target / "doc" / "my ext" / "adapters"
        ad.mkdir(parents=True, exist_ok=True)
        for f in ("story.js", "token.js"):
            (ad / f).write_text(f"// real {f}\nmodule.exports = {{}};\n", encoding="utf-8")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", "-C", str(target), *args], capture_output=True)
        (target / "doc").mkdir(exist_ok=True)
        (target / "doc" / "usage.json.lock").mkdir()
        return target

    def adapt(self, target: Path, mode: str, env: dict) -> subprocess.CompletedProcess:
        scan = target / "doc" / "my ext" / "base" / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
        return subprocess.run(["node", str(scan), mode],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)

    def check_shell(self, shell: str) -> None:
        if shutil.which(shell) is None:
            self.skipTest(f"环境里没有 {shell}")
        env = dict(self.os.environ)
        if shell == "powershell":
            env.pop("SHELL", None)
        else:
            env["SHELL"] = "/bin/bash"
        target = self.make_target(f"O'Brien 目标 {shell}")
        proc = self.adapt(target, "--apply", env)
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        (target / "doc" / "usage.json.lock").rmdir()
        line = repair_line(proc.stdout)
        self.assertIn("python -B", line)
        done = run_in_shell(line, cwd=REPO, shell=shell)
        self.assertEqual(0, done.returncode, f"{line}\n{done.stdout}{done.stderr}")
        record = target / "doc" / "usage.json"
        self.assertEqual({"schema": 1, "requirements": {}}, json.loads(record.read_text(encoding="utf-8")))
        ext = target / "doc" / "my ext"
        self.assertTrue((ext / "manifest.yaml").is_file(), "扩展没装到自定义目录")
        self.assertEqual([], [p for p in ext.rglob("__pycache__")], "补建命令在机制目录里留了字节码")
        check = self.adapt(target, "--check", env)
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)

    def test_powershell(self) -> None:
        self.check_shell("powershell")

    def test_posix_shell(self) -> None:
        self.check_shell("bash")


if __name__ == "__main__":
    unittest.main()
