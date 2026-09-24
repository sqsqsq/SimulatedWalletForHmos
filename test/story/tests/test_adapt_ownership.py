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
from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PKG_EXT = REPO_ROOT / "doc" / "extensions"
SCAN = PKG_EXT / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
LAUNCHERS = (
    ".cac/commands/story.md", ".claude/commands/story.md",
    ".codex/skills/story/SKILL.md", ".opencode/skill/story/SKILL.md",
)


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
            shutil.copy(REPO_ROOT / rel, dst)
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
             "--package", str(REPO_ROOT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def out(self, proc: subprocess.CompletedProcess) -> str:
        return ((proc.stdout or "") + (proc.stderr or "")).strip()


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
        body = "---\nname: 我的画像\nkind: facts\n---\n\n# 这个仓自己写的\n"
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


class AnOldIndexIsLeftForTheModel(AdaptCase):
    """旧仓自己改过的 README（kind: index）：脚本不碰它与激活清单，机制照装；加载器指出这份要迁移。"""

    def test_upgrade_keeps_the_old_index_and_the_loader_names_it(self) -> None:
        readme = self.ext / "knowledge" / "facts" / "README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text("---\nname: facts-index\nkind: index\nprotocol: 1\n---\n\n本仓自定：画像先写交互方。\n",
                          encoding="utf-8")
        manifest = self.ext / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("  knowledge:\n", "  knowledge:\n    - knowledge/facts/README.md\n", 1),
                            encoding="utf-8")
        self.commit("旧仓带自定义索引件")
        for mode in ("--apply", "--check"):
            proc = self.adapt(mode)
            self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("本仓自定：画像先写交互方。", readme.read_text(encoding="utf-8"))
        self.assertIn("    - knowledge/facts/README.md\n", manifest.read_text(encoding="utf-8"))
        module = (self.ext / "hooks" / "shared" / "knowledge.mjs").resolve().as_uri()
        proc = subprocess.run(
            ["node", "--input-type=module", "-e",
             "const k = await import(process.argv[1]);"
             "try { k.activeKnowledge(process.argv[2]); } catch (e) { process.stdout.write(e.message); }",
             module, str(self.target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("knowledge/facts/README.md 是旧版知识索引件（kind: index）", proc.stdout)


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

    def test_running_twice_says_it_is_still_valid(self) -> None:
        """同版本重复执行不损坏内容，第二次说「仍有效」而不是「写入 0 个文件」。"""
        first = self.adapt("--apply")
        self.assertEqual(0, first.returncode, self.out(first))
        self.commit("第一次升级")
        second = self.adapt("--apply")
        self.assertEqual(0, second.returncode, self.out(second))
        self.assertIn("当前适配仍有效", self.out(second))


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



class ThePackageKeepsItsOwnDirectoriesStraight(AdaptCase):
    """⑧ 判的是包：`scripts/` 那一层只有 core/ 与 adapters/。"""

    def test_the_package_scripts_dir_has_exactly_two_subdirs(self) -> None:
        """真包上直接核：所有权由目录表达的前提，就是根这一层是空的。"""
        at = PKG_EXT / "skills" / "story" / "scripts"
        dirs = sorted(p.name for p in at.iterdir() if p.is_dir() and p.name != "__pycache__")
        self.assertEqual(["adapters", "core"], dirs)
        files = sorted(p.name for p in at.iterdir() if p.is_file())
        self.assertEqual(["README.md"], files,
                         "scripts/ 根下多了独立文件——它归谁又要靠推断了")

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
