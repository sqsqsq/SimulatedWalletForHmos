"""所有权由目录表达 —— `core/` 整份换掉，`adapters/` 与 `knowledge/` 一寸不碰。

## 为什么有这一份

上一版 `adapt-scan` 按**路径长相**分类：`skills/story/scripts/<name>.js` 是对接层，
其余一概是机制。于是目标为自定义对接装的依赖（`package.json` 不是 `.js`、
`node_modules/**` 有下级目录）统统落进机制，撞上「机制内容 == 包」恒 FAIL，
目标绕不过去。更早还栽过一次：知识文件按路径判成随包维护，一次升级盖掉了目标的业务定义。

两次都是同一个根因——**路径长相回答不了「这是谁的东西」**。

现在所有权写在目录本身：

    scripts/core/       归包，升级整份换掉，包里没有的删掉
    scripts/adapters/   归目标，升级一个字节不碰
    knowledge/          归目标，升级不读不写

没有推断，也就没有推错的可能。下面锁三件：边界守得住、升级动得对、前置拦得住。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml
from ext_workspace import change_versions, installed_package, link_harness_yaml

#: 包：装好了开发源的临时消费工程——adapt 从包里的脚本起跑（运行态）
PKG_ROOT = installed_package()
PKG_EXT = PKG_ROOT / "doc" / "extensions"
SCAN = PKG_EXT / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
#: 包登记的宿主入口（target），正文在包工程的同一路径
LAUNCHERS = tuple(b["target"] for b in yaml.safe_load(
    (PKG_EXT / "manifest.yaml").read_text(encoding="utf-8"))["provides"]["bridges"])
#: 包的版本：`adapted_for` 只会被脚本写成它
PKG_VERSION = yaml.safe_load((PKG_EXT / "manifest.yaml").read_text(encoding="utf-8"))["version"]


class AdaptCase(unittest.TestCase):
    """每个用例搭一个「已装好扩展、已提交」的目标工程，跑真 `adapt-scan`。

    目标必须是 git 仓且有基线提交：核对靠 `git diff`，没有底就没有「变了哪些」。
    """

    def setUp(self) -> None:  # noqa: D102
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        if shutil.which("git") is None:
            self.skipTest("环境里没有 git")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "target"
        self.target.mkdir(parents=True)
        (self.target / "framework.config.json").write_text(
            json.dumps({"paths": {"extension_dir": "doc/extensions"}}, ensure_ascii=False),
            encoding="utf-8")
        (self.target / ".gitignore").write_text(
            "doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")
        shutil.copytree(PKG_EXT, self.target / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*"))
        link_harness_yaml(self.target)
        for rel in LAUNCHERS:
            dst = self.target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(PKG_ROOT / rel, dst)
        self.ext = self.target / "doc" / "extensions"
        self.scripts = self.ext / "skills" / "story" / "scripts"
        self.core = self.scripts / "core"
        self.adapters = self.scripts / "adapters"
        # 入口文件：⑤ 要它含扩展段连同标记区
        section = self.ext / "skills" / "story" / "AGENTS.section.md"
        body = section.read_text(encoding="utf-8") if section.exists() else ""
        (self.target / "AGENTS.md").write_text(
            "# 目标工程\n\n## 实例扩展\n\n<!-- story-ext:begin -->\n"
            + body.strip() + "\n<!-- story-ext:end -->\n", encoding="utf-8")
        self.commit("baseline")

    # ---- 驱动 ----

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.target), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)

    def commit(self, message: str) -> None:
        if not (self.target / ".git").exists():
            self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", message)

    def adapt(self, mode: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(SCAN), mode, "--target", str(self.target),
             "--package", str(PKG_ROOT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def out(self, proc: subprocess.CompletedProcess) -> str:
        return ((proc.stdout or "") + (proc.stderr or "")).strip()

    def write_review(self, *, digest: str | None = None, verdict: str = "PASS", skip: int = 0) -> None:
        """独立审查者交回的证据块：摘要与激活清单取自 `--status`，四个维度逐份给结论。"""
        knowledge = json.loads(self.adapt("--status").stdout)["knowledge"]
        files = knowledge["files"][skip:]
        dims = "".join(f"      {d}: {{verdict: {verdict}, evidence: 核过 {d}}}\n"
                       for d in ("granularity", "fact_use", "duplication", "coding_boundary"))
        rows = "".join(f"    - path: {f}\n{dims}" for f in files)
        review = self.ext / ".adapt" / "knowledge-review.md"
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text("# 知识独审\n\n```yaml\nknowledge_review:\n"
                          f"  digest: \"{digest or knowledge['digest']}\"\n  executor: subagent-run-1\n"
                          f"  files:\n{rows}  blocking: []\n  unreviewed: []\n```\n", encoding="utf-8")


class TheTargetKeepsWhatIsItsOwn(AdaptCase):
    """`adapters/` 与 `knowledge/` 归目标，升级碰都不碰。"""

    def test_a_clean_target_passes(self) -> None:
        """基线：什么都不动，`--check` 必须过——不然下面几条测不出东西。"""
        proc = self.adapt("--check")
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_an_upgrade_leaves_the_adapters_untouched(self) -> None:
        """目标自己实现的对接脚本，升级之后逐字未变。"""
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
        """对接层的依赖闭包也归目标：`package.json`、`node_modules/` 一律不碰。

        它们不是 `.js`、还带下级目录——按后缀或路径长相分类时正是在这里判错的。
        """
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



class TheMechanismFollowsThePackage(AdaptCase):
    """`core/` 与其余机制面跟着包走，包里没有的清掉。"""

    def test_a_file_the_package_dropped_is_removed(self) -> None:
        """包里不再有的文件，升级之后目标那边也没有。"""
        stale = self.core / "retired.mjs"
        stale.write_text("export const gone = 1;\n", encoding="utf-8")
        self.commit("目标上留着一个包里已经没有的文件")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse(stale.exists(), "包里没有的文件还留在目标上")
        self.assertIn("retired.mjs", self.out(proc), "清掉了却没报出来——静默删比不删更糟")

    def test_a_python_package_arrives_and_its_flat_predecessor_goes(self) -> None:
        """按功能分的子目录要真被装上，同名的旧平铺文件要真被清掉。

        两件事都靠「整份换掉」这一条，而不靠列文件名。漏了前一半，目标上跑的命令
        import 不到模块；漏了后一半，`core/materials.py` 与 `core/materials/` 同时在，
        Python 认包不认模块，于是目标读的是新包、维护者看的是旧文件。
        """
        flat = self.core / "materials.py"
        flat.write_text("SCHEMA = 1  # 上一版的平铺实现\n", encoding="utf-8")
        self.commit("目标上还留着上一版的平铺材料模块")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse(flat.exists(), "旧的平铺文件还在，和新包同时存在")
        for rel in ("flow/state.py", "flow/lifecycle.py",
                    "materials/registry.py", "materials/importer.py"):
            self.assertTrue((self.core / rel).is_file(), f"{rel} 没被装上")

    def test_a_mechanism_file_changed_on_the_target_is_restored(self) -> None:
        """目标改了机制面，升级把它换回包的版本——机制不归目标。"""
        f = self.core / "story" / "chapter-contract.mjs"
        original = f.read_text(encoding="utf-8")
        f.write_text(original + "\n// 目标自己加的\n", encoding="utf-8")
        self.commit("目标改了机制文件")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual(original, f.read_text(encoding="utf-8"), "机制没被换回包的版本")

    def test_the_manifest_keeps_the_targets_knowledge_list(self) -> None:
        """一个文件两种所有权：机制登记跟包，`provides.knowledge` 跟目标。"""
        manifest = self.ext / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        mine = "  knowledge:\n    - knowledge/facts/own-profile.md\n"
        head, _, tail = text.partition("  knowledge:\n")
        keep = tail.split("\n  hooks:", 1)[1] if "\n  hooks:" in tail else ""
        manifest.write_text(head + mine + "\n  hooks:" + keep, encoding="utf-8")
        self.commit("目标只激活一份知识")

        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("    - knowledge/facts/own-profile.md\n", after)
        self.assertNotIn("knowledge/constraints/ux-consistency.md", after,
                         "升级把包的知识清单塞给了目标——知识激活随目标，不因升级重选")
        self.assertIn("story-adaptation", after, "机制登记没跟上包")


class TheStatusViewOnlyReads(AdaptCase):
    """`--status`：刚装完、没有任何需求时照样能核知识；只读——前后文件集合与内容一致；
    未安装、坏清单、坏配置分别是不同的事实，不能都变成「零知识且通过」。"""

    def tree(self) -> dict[str, bytes]:
        return {p.relative_to(self.target).as_posix(): p.read_bytes()
                for p in self.target.rglob("*") if p.is_file() and ".git" not in p.parts}

    def status(self) -> tuple[int, dict]:
        before = self.tree()
        proc = self.adapt("--status")
        self.assertEqual(before, self.tree(), "--status 写了文件")
        return proc.returncode, json.loads(proc.stdout)

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
        shutil.rmtree(self.ext)
        self.commit("空仓")
        self.assertEqual(0, self.adapt("--apply").returncode)
        self.commit("装好")
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("PASS", got["knowledge"]["status"])
        self.assertEqual({}, got["knowledge"]["counts"])
        self.assertTrue(got["items"]["知识"], "从未适配的目标没从知识基线列起")
        self.assertFalse((self.target / "doc" / "features").exists(), "检查造了需求目录")

    def test_not_installed_is_a_fact_not_an_error(self) -> None:
        shutil.rmtree(self.ext)
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
        manifest = self.ext / "manifest.yaml"
        rows = [('adapted_for: "1.9.6"' if l.startswith("adapted_for:") else l)
                for l in manifest.read_text(encoding="utf-8").split("\n")]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        code, got = self.status()
        self.assertEqual(0, code, got)
        self.assertEqual("1.9.6", got["target"]["adapted_for"])
        self.assertTrue(all(tuple(map(int, i.split("：", 1)[0].split("."))) > (1, 9, 6)
                            for i in got["items"]["知识"]), got["items"])
        self.assertEqual([], got["items"]["在途单"], "装的就是包的版本，在途单按当前游标为空")


class SameUseCandidatesAreOnlyHints(TheStatusViewOnlyReads):
    """同用途声明候选只按 `applies_when` 原文相同分组，给独立审查当线索：不改 PASS，不推断相似，
    为空也不说明没有重复。重复与否、互补与否由审查读正文判。"""

    def set_applies(self, name: str, text: str) -> None:
        f = self.ext / "knowledge" / "facts" / name
        rows = [f"applies_when: {text}" if l.startswith("applies_when:") else l
                for l in f.read_text(encoding="utf-8").split("\n")]
        f.write_text("\n".join(rows), encoding="utf-8")

    def test_the_same_declared_use_is_listed_without_changing_the_verdict(self) -> None:
        """同用途但内容互补：脚本只列出来，不判它们重复。"""
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
        """用途写法不同而正文重复：脚本不列，也不说「没有重复」——那归审查。"""
        self.set_applies("component-profile.md", "查本部件边界时")
        self.set_applies("engineering-capabilities.md", "查已有能力时")
        code, got = self.status()
        self.assertEqual(0, code, got)
        listed = [f for g in got["knowledge"]["sameUse"]["groups"] for f in g["files"]]
        self.assertNotIn("knowledge/facts/component-profile.md", listed)
        self.assertNotIn("无重复", json.dumps(got, ensure_ascii=False))


class TheIndependentReviewIsDeliveredBeforeMarking(unittest.TestCase):
    """独立审查的任务页交付四个维度，SKILL 与方法页在 --mark-adapted 之前送达它。"""

    REF = PKG_EXT / "skills" / "story-adaptation"

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
        manifest = self.ext / "manifest.yaml"
        rows = [f'adapted_for: "{version}"' if l.startswith("adapted_for:") else l
                for l in manifest.read_text(encoding="utf-8").split("\n")]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(f"知识按 {version} 适配过")

    def test_newer_protocol_entries_are_listed_and_asked(self) -> None:
        self.set_adapted("1.9.6")
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("1.9.7：每份知识的 frontmatter 写齐", proc.stdout)
        self.assertIn("停一次问人「现在做这些适配吗」", proc.stdout)
        for older in ("1.9.4：", "1.9.5：", "1.9.6："):
            self.assertNotIn(older, proc.stdout, "已适配过的版本又列了一遍")
        manifest = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn('adapted_for: "1.9.6"', manifest, "没等人选就写了适配版本")

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
        """已按包的版本适配过、知识合协议：没有更晚的演进条目，不问人，脚本把 adapted_for 写成包的版本。"""
        self.set_adapted(PKG_VERSION)
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("目标已按包的版本适配，知识与当前协议一致", proc.stdout)
        self.assertNotIn("停一次问人", proc.stdout)
        manifest = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', manifest, "无事可做却没记下已按包的版本适配")
        self.assertEqual("", self.git("status", "--porcelain", "--", "doc/extensions/knowledge").stdout.strip(),
                         "只是提示却写了知识")
        self.assertEqual(0, self.adapt("--check").returncode, "写了 adapted_for 之后 manifest 不再是合成结果")

    def test_a_target_without_adapted_for_starts_from_the_knowledge_baseline(self) -> None:
        """没按任何版本适配过：知识块从基线一节列起，连同后面各版的知识条目。"""
        manifest = self.ext / "manifest.yaml"
        rows = [l for l in manifest.read_text(encoding="utf-8").split("\n") if not l.startswith("adapted_for:")]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit("没写过 adapted_for")
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        knowledge = json.loads(line.split("按版本跟进：", 1)[1])["items"]["知识"]
        self.assertEqual(set(change_versions(PKG_EXT, "知识")), {i.split("：", 1)[0] for i in knowledge},
                         "没从知识基线起列全各版知识条目")
        self.assertIn("停一次问人", proc.stdout)
        self.assertNotIn("adapted_for", manifest.read_text(encoding="utf-8"), "没等人做完就写了适配版本")


class TheAdaptedVersionIsWrittenByTheScript(AdaptCase):
    """`--mark-adapted` 把 adapted_for 写成包的版本；值不由模型定，前置不满足就停。"""

    def mark(self) -> subprocess.CompletedProcess:
        return self.adapt("--mark-adapted")

    def set_manifest_line(self, key: str, value: str) -> None:
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
        manifest = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', manifest)
        self.assertEqual(0, self.adapt("--check").returncode, self.out(self.adapt("--check")))

    def test_knowledge_due_for_adaptation_needs_matching_independent_evidence(self) -> None:
        """有知识演进条目时，加载通过不等于适配完成：缺审、过期、漏一份、判 FAIL 都不写 adapted_for。"""
        self.set_manifest_line("adapted_for", "1.9.2")
        before = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        cases = {"缺审": (None, "missing"), "过期": ({"digest": "sha256:0000000000000000"}, "stale"),
                 "漏一份": ({"skip": 1}, "incomplete"), "判 FAIL": ({"verdict": "FAIL"}, "incomplete")}
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
                self.assertEqual(before, (self.ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.write_review()
        self.assertEqual(0, self.mark().returncode)
        fact = next((self.ext / "knowledge" / "facts").glob("*.md"))
        fact.write_text(fact.read_text(encoding="utf-8") + "\n补一句。\n", encoding="utf-8")
        self.assertEqual("stale", json.loads(self.adapt("--status").stdout)["knowledge"]["review"]["status"],
                         "知识改过之后旧结论还盖着新内容")

    def test_a_mechanism_only_upgrade_needs_no_review(self) -> None:
        """没有晚于 adapted_for 的知识条目：不要求独审，照常记版本。"""
        latest = change_versions(PKG_EXT, "知识")[-1]
        self.set_manifest_line("adapted_for", latest)
        proc = self.mark()
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_it_stops_when_the_target_has_no_manifest(self) -> None:
        shutil.rmtree(self.ext)
        self.commit("空仓")
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("还没装过", self.out(proc))
        self.assertFalse((self.ext / "manifest.yaml").exists(), "没装过却写了 manifest")

    def test_it_stops_before_the_mechanism_is_upgraded(self) -> None:
        self.set_manifest_line("version", "1.9.7")
        before = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("把机制升到包的版本", self.out(proc))
        self.assertEqual(before, (self.ext / "manifest.yaml").read_text(encoding="utf-8"))

    def test_it_stops_when_the_knowledge_does_not_load(self) -> None:
        fact = next((self.ext / "knowledge" / "facts").glob("*.md"))
        fact.write_text(fact.read_text(encoding="utf-8").replace("\nform:", "\nshape:", 1), encoding="utf-8")
        self.commit("有一份知识没写 form")
        before = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        proc = self.mark()
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(fact.name, self.out(proc))
        self.assertEqual(before, (self.ext / "manifest.yaml").read_text(encoding="utf-8"))


class ThePreflightStopsInsteadOfGuessing(AdaptCase):
    """前置不满足就停，不猜、不替用户动工作区。"""

    def test_a_dirty_write_face_stops_the_upgrade(self) -> None:
        """写入面上有未提交改动就停——盖掉了在 diff 里还看不出来，没法补救。"""
        (self.core / "story" / "chapter-contract.mjs").write_text("目标改了一半没提交\n", encoding="utf-8")
        proc = self.adapt("--apply")
        self.assertEqual(2, proc.returncode, "工作区脏却照写了")
        self.assertIn("chapter-contract.mjs", self.out(proc), "停了却没点名是哪个文件脏")
        self.assertEqual("目标改了一半没提交\n",
                         (self.core / "story" / "chapter-contract.mjs").read_text(encoding="utf-8"),
                         "停之前已经写过盘了")

    def test_a_target_outside_git_stops_the_upgrade(self) -> None:
        """不是 git 仓就停：确认靠 diff，没有 git 就没有「变了哪些文件」这个答案。"""
        # 挪走而不是删：Windows 上 git 的对象文件是只读的，rmtree 会撞权限
        (self.target / ".git").rename(self.target.parent / "git-moved-away")
        proc = self.adapt("--apply")
        self.assertEqual(2, proc.returncode, "没有 git 却照写了")
        self.assertIn("git", self.out(proc))

    def test_running_twice_says_the_mechanism_is_current(self) -> None:
        """同版本重复执行不损坏内容，第二次说「机制已在包的版本上」而不是「写入 0 个文件」。"""
        first = self.adapt("--apply")
        self.assertEqual(0, first.returncode, self.out(first))
        self.commit("第一次升级")
        second = self.adapt("--apply")
        self.assertEqual(0, second.returncode, self.out(second))
        self.assertIn("机制已在包的版本上", self.out(second))


class AFreshInstallRunsOutOfTheBox(AdaptCase):
    """空仓装完就能跑 —— 清单登记的是刚建的骨架，不是包里的 Demo 知识。

    照抄包的清单会登记十几份目标里根本没有的知识正文，`activeKnowledge` 当场报
    「登记的文件读不到」：新仓装完第一件事是撞墙。而「装完就能跑」是 A3 的直接后果——
    首次安装不建知识骨架，清单为空，第一份部件画像由模型按方法页写。
    """

    def setUp(self) -> None:  # noqa: D102
        super().setUp()
        # 把「已装好」的那一份撤掉，只留一个空仓：配置键 + 入口文件
        shutil.rmtree(self.ext)
        self.commit("空仓")

    def test_the_manifest_registers_no_knowledge_and_writes_none(self) -> None:
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        manifest = (self.ext / "manifest.yaml").read_text(encoding="utf-8")
        block = manifest.split("  knowledge:\n", 1)[1].split("\n  hooks:", 1)[0]
        listed = [l.strip()[2:] for l in block.splitlines() if l.strip().startswith("- ")]
        self.assertEqual([], listed, "首次安装替目标激活了知识")
        written = [p for p in (self.ext / "knowledge").rglob("*") if p.is_file()] if (self.ext / "knowledge").exists() else []
        self.assertEqual([], written, "脚本往目标的 knowledge/ 写了东西")

    def test_the_derivation_runs_on_a_fresh_install(self) -> None:
        """装完直接跑知识派生：四类皆空、不抛——这是「装完就能跑」的判据本身。"""
        self.assertEqual(0, self.adapt("--apply").returncode)
        probe = (
            "const k = await import(process.argv[1]);"
            "const kn = k.activeKnowledge(process.argv[2]);"
            "process.stdout.write(JSON.stringify({"
            "  facts: kn.facts.length, constraints: kn.constraints.length,"
            "  patterns: kn.patterns.length, entries: kn.entries.length,"
            "  problems: k.selfCheck(process.argv[2], kn).length }));"
        )
        module = (self.ext / "hooks" / "shared" / "knowledge.mjs").resolve().as_uri()
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", probe, module, str(self.target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, f"空仓装完派生就抛了：{proc.stderr}")
        self.assertEqual({"facts": 0, "constraints": 0, "patterns": 0,
                          "entries": 0, "problems": 0}, json.loads(proc.stdout))

    def test_a_fresh_install_passes_its_own_check(self) -> None:
        """刚装完跑 `--check` 要过：首次安装的知识清单为空，判据不把它当成装错。

        两态不分的话，判据会把自己刚写出来的东西判成「升级动了目标的知识」。
        """
        self.assertEqual(0, self.adapt("--apply").returncode)
        proc = self.adapt("--check")
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_a_fresh_install_lists_the_knowledge_baseline_and_leaves_adapted_for_to_the_script(self) -> None:
        """首次安装就列出从基线起的知识条目、不列在途单，不带 adapted_for；交回后 `--mark-adapted` 写成包的版本。"""
        proc = self.adapt("--apply")
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertNotIn("adapted_for", (self.ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("--mark-adapted", proc.stdout)
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        items = json.loads(line.split("按版本跟进：", 1)[1])["items"]
        self.assertEqual(set(change_versions(PKG_EXT, "知识")), {i.split("：", 1)[0] for i in items["知识"]},
                         "首次没从知识基线起拿到各版知识条目")
        self.assertNotIn("在途单", items, "首次安装没有在途单，那一块不该列")
        self.commit("首次装好")
        self.assertEqual(2, self.adapt("--mark-adapted").returncode, "首装写了知识却没独审，也记成已适配")
        self.write_review()
        marked = self.adapt("--mark-adapted")
        self.assertEqual(0, marked.returncode, self.out(marked))
        self.assertIn(f'adapted_for: "{PKG_VERSION}"', (self.ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(0, self.adapt("--check").returncode)



class ThePackageKeepsItsOwnDirectoriesStraight(AdaptCase):
    """⑤ 判的是包：`scripts/` 那一层只有 core/ 与 adapters/。"""

    def test_the_package_scripts_dir_has_exactly_two_subdirs(self) -> None:
        """真包上直接核：所有权由目录表达的前提，就是根这一层是空的。"""
        at = PKG_EXT / "skills" / "story" / "scripts"
        dirs = sorted(p.name for p in at.iterdir() if p.is_dir() and p.name != "__pycache__")
        self.assertEqual(["adapters", "core"], dirs)
        files = sorted(p.name for p in at.iterdir() if p.is_file())
        self.assertEqual([], files, "scripts/ 根下多了文件——它归谁又要靠推断了")

    def test_a_stray_file_in_the_package_is_named(self) -> None:
        """反向锁：包里往根下放一个脚本，`--check` 要报出来。

        判的是**包**不是目标，所以这条用临时包跑：把真包复制一份、放一个脚本进去。
        """
        pkg = Path(self._tmp.name) / "pkg"
        pkg.mkdir()
        shutil.copy(self.target / "framework.config.json", pkg / "framework.config.json")
        shutil.copytree(PKG_EXT, pkg / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*"))
        link_harness_yaml(pkg)
        (pkg / "doc" / "extensions" / "skills" / "story" / "scripts" / "loose.mjs").write_text(
            "export const x = 1;\n", encoding="utf-8")

        proc = subprocess.run(
            ["node", str(SCAN), "--check", "--target", str(self.target),
             "--package", str(pkg)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(1, proc.returncode, "包的 scripts 根下有脚本却判通过了")
        self.assertIn("loose.mjs", self.out(proc))


if __name__ == "__main__":
    unittest.main()
