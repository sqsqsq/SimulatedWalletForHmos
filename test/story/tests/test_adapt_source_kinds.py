"""两种来源：Demo 不给对接实现，业务仓之间共用一套（A12）。\n\nDemo 包里的 `story.js` / `token.js` 是**替身**——用本地目录模拟需求系统，\n复制到业务仓等于把人家的真实现盖掉。业务仓之间不一样：它们对接的是同一个需求系统，\n共用同一套实现，复刻时正该带上。\n\n判来源看包 `manifest.yaml` 的 `adapters`：写 `stand-in` 的包里是替身，没有这个键的是业务仓。\n它归目标、升级不改，所以每个仓说的都是它自己的对接层——不必靠仓名、\n目录结构或对接脚本的内容去猜。\n\n这一份锁四件：Demo 来源不给也不覆盖对接实现；业务仓来源整体覆盖；目标的身份\n（`name` / `description`）不被任何一次升级改掉；两种来源交替时各按各的规矩。\n"""
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
ADAPTERS = "doc/extensions/skills/story/scripts/adapters"
LAUNCHERS = (
    ".cac/commands/story.md", ".claude/commands/story.md",
    ".codex/skills/story/SKILL.md", ".opencode/skill/story/SKILL.md",
)


class SourceKindCase(unittest.TestCase):
    """两个空的目标仓，包按用例自己选：真包（Demo）或另一个业务仓。"""

    def setUp(self) -> None:  # noqa: D102
        for tool in ("node", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"环境里没有 {tool}")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    # ---- 驱动 ----

    def blank_repo(self, project: str) -> Path:
        """一个只有配置与入口文件的空仓，已提交。"""
        at = self.root / project
        at.mkdir(parents=True)
        (at / "framework.config.json").write_text(
            json.dumps({"project_name": project,
                        "paths": {"extension_dir": "doc/extensions"}}, ensure_ascii=False),
            encoding="utf-8")
        link_harness_yaml(at)
        (at / ".gitignore").write_text(
            "doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")
        section = PKG_EXT / "skills" / "story" / "AGENTS.section.md"
        (at / "AGENTS.md").write_text(
            f"# {project}\n\n## 实例扩展\n\n<!-- story-ext:begin -->\n"
            + section.read_text(encoding="utf-8").strip() + "\n<!-- story-ext:end -->\n",
            encoding="utf-8")
        for rel in LAUNCHERS:
            dst = at / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO_ROOT / rel, dst)
        self.commit(at, "baseline")
        return at

    def commit(self, at: Path, message: str) -> None:
        run = lambda *a: subprocess.run(["git", "-C", str(at), *a], capture_output=True,
                                        text=True, encoding="utf-8", timeout=120)
        if not (at / ".git").exists():
            run("init", "-q")
        run("add", "-A")
        run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", message)

    def adapt(self, mode: str, target: Path, package: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(SCAN), mode, "--target", str(target), "--package", str(package)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def out(self, proc: subprocess.CompletedProcess) -> str:
        return ((proc.stdout or "") + (proc.stderr or "")).strip()

    def write_adapters(self, at: Path, mark: str) -> None:
        """把某个仓的对接层换成它自己的实现。"""
        d = at / ADAPTERS
        d.mkdir(parents=True, exist_ok=True)
        for name in ("story.js", "token.js"):
            (d / name).write_text(f"// {mark}\nmodule.exports = {{ who: '{mark}-{name}' }};\n",
                                  encoding="utf-8")

    def adapter_text(self, at: Path, name: str = "story.js") -> str:
        f = at / ADAPTERS / name
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    # ---- Demo 来源 ----

    def test_a_demo_install_does_not_hand_over_the_stand_ins(self) -> None:
        """Demo 装到新仓：给机制与知识骨架，**不给**三个对接替身。\n\n        那三个是本地模拟，装到业务仓里跑起来会往一个不存在的目录读写需求单据。\n        目标从已实现的业务仓复刻，之后按升级演进记录的对接层条目跟进。\n        """
        target = self.blank_repo("BizA")
        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / ADAPTERS).exists(), "Demo 把对接替身装进业务仓了")
        self.assertTrue((target / "doc/extensions/skills/story/scripts/core").is_dir())

    def test_a_demo_upgrade_never_overwrites_a_real_implementation(self) -> None:
        """目标自己实现之后再从 Demo 升级：那三个文件一个字节不动。\n\n        这是本设计要挡的最坏一种后果——业务仓的真实现被一次常规升级换成替身，\n        而它跑起来还像是好的，只是读写的是另一个地方。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        self.write_adapters(target, "BizA 的真实现")
        self.commit(target, "自己实现对接层")

        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target))

    # ---- 业务仓之间 ----

    def source_repo(self, project: str = "BizA") -> Path:
        """一个装好、且自己实现了对接层的业务仓——它就是复刻的来源。"""
        at = self.blank_repo(project)
        self.adapt("--apply", at, REPO_ROOT)
        self.write_adapters(at, f"{project} 的真实现")
        self.commit(at, "装好并自己实现对接层")
        return at

    def test_copying_between_business_repos_carries_the_adapters(self) -> None:
        """业务仓之间复刻：对接实现跟着过去——它们共用同一套（A12）。"""
        source = self.source_repo("BizA")
        target = self.blank_repo("BizB")

        proc = self.adapt("--apply", target, source)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target),
                      "业务仓之间复刻没把对接实现带过去")
        self.assertEqual(0, self.adapt("--check", target, source).returncode)

    def test_a_later_source_change_reaches_the_target(self) -> None:
        """来源改了对接实现，再复刻一次，目标跟上——它归来源，不是目标的自留地。"""
        source = self.source_repo("BizA")
        target = self.blank_repo("BizB")
        self.adapt("--apply", target, source)
        self.commit(target, "第一次复刻")

        self.write_adapters(source, "BizA 的真实现 v2")
        self.commit(source, "对接层改版")
        proc = self.adapt("--apply", target, source)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("v2", self.adapter_text(target))

    def test_a_demo_upgrade_after_a_copy_still_keeps_the_adapters(self) -> None:
        """两种来源交替：从业务仓复刻来的实现，再走一次 Demo 升级也不会被替身盖掉。"""
        source = self.source_repo("BizA")
        target = self.blank_repo("BizB")
        self.adapt("--apply", target, source)
        self.commit(target, "复刻完成")

        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target))

    # ---- 按版本跟进 ----

    def follow_up(self, proc: subprocess.CompletedProcess) -> dict:
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        return json.loads(line.split("按版本跟进：", 1)[1])

    def test_an_unadapted_target_gets_every_block_from_a_stand_in_source(self) -> None:
        """目标没写 adapted_for、装的是旧版（旧装的仓都是这样）：从头列出各版条目；替身来源不给对接层，那一块照列。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        self.set_version(target, "1.9.3")
        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        got = self.follow_up(proc)
        self.assertEqual("0", got["since"])
        self.assertEqual({"知识", "对接层", "在途单"}, set(got["items"]))
        for block, items in got["items"].items():
            with self.subTest(block=block):
                self.assertTrue(items, f"{block} 一条都没列")
        self.assertTrue(any(i.startswith("1.9.4：") for i in got["items"]["对接层"]))
        self.assertIn("停一次问人", proc.stdout)

    def set_version(self, target: Path, version: str) -> None:
        manifest = target / "doc/extensions/manifest.yaml"
        rows = [f'version: "{version}"' if l.startswith("version:") else l
                for l in manifest.read_text(encoding="utf-8").split("\n")]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(target, f"装的是 {version}")

    def test_in_flight_entries_follow_the_installed_version(self) -> None:
        """在途单只跟从哪一版升上来有关：装的是上一版就只列本版；知识与对接层没写 adapted_for 仍从头列。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        self.set_version(target, "1.9.6")
        got = self.follow_up(self.adapt("--apply", target, REPO_ROOT))
        self.assertEqual("1.9.6", got["installed"])
        self.assertTrue(got["items"]["在途单"])
        self.assertTrue(all(i.startswith("1.9.7：") for i in got["items"]["在途单"]), got["items"]["在途单"])
        self.assertTrue(any(i.startswith("1.9.5：") for i in got["items"]["知识"]))

    def test_a_business_source_leaves_out_the_adapter_block(self) -> None:
        """业务仓来源整份换了对接层，那一块不用目标再做。"""
        source = self.source_repo("BizA")
        target = self.blank_repo("BizB")
        self.adapt("--apply", target, source)
        self.commit(target, "复刻")
        proc = self.adapt("--apply", target, source)
        self.assertEqual(0, proc.returncode, self.out(proc))
        got = self.follow_up(proc)
        self.assertNotIn("对接层", got["items"])
        self.assertTrue(got["items"]["知识"])

    def test_an_indented_sub_item_stops_before_writing(self) -> None:
        """演进记录每条一行：缩进的子项不静默跳过，写目标之前就停。"""
        pkg = self.pkg_with_manifest(lambda l: l)
        changes = pkg / "doc/extensions/skills/story-adaptation/reference/upgrade-changes.md"
        changes.write_text(changes.read_text(encoding="utf-8") + "  - 缩进的子项\n", encoding="utf-8")
        target = self.blank_repo("BizA")
        proc = self.adapt("--apply", target, pkg)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("不用子项", self.out(proc))

    def test_an_entry_without_a_block_stops_before_writing(self) -> None:
        """包里的演进记录有一条没标块：包坏了，写目标之前就停。"""
        pkg = self.pkg_with_manifest(lambda l: l)
        changes = pkg / "doc/extensions/skills/story-adaptation/reference/upgrade-changes.md"
        changes.write_text(changes.read_text(encoding="utf-8") + "- 没标块的一条\n", encoding="utf-8")
        target = self.blank_repo("BizA")
        proc = self.adapt("--apply", target, pkg)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("没有块标签", self.out(proc))
        self.assertFalse((target / "doc/extensions/manifest.yaml").exists(), "停之前已经写过盘了")

    def pkg_with_manifest(self, rewrite) -> Path:
        """Demo 包的一份拷贝，manifest 逐行经 `rewrite` 改写。"""
        pkg = self.root / "rewritten-pkg"
        if pkg.exists():
            shutil.rmtree(pkg)
        pkg.mkdir()
        shutil.copy(REPO_ROOT / "framework.config.json", pkg / "framework.config.json")
        shutil.copytree(PKG_EXT, pkg / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".*"))
        link_harness_yaml(pkg)
        for rel in LAUNCHERS:
            dst = pkg / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO_ROOT / rel, dst)
        manifest = pkg / "doc" / "extensions" / "manifest.yaml"
        manifest.write_text("\n".join(rewrite(l) for l in manifest.read_text(encoding="utf-8").split("\n")),
                            encoding="utf-8")
        return pkg

    def test_yaml_quoting_does_not_change_the_source_kind(self) -> None:
        """`adapters` 取的是 YAML 的**值**，不是那一行的字面。\n\n        `adapters: stand-in` 与 `adapters: "stand-in"` 是同一个值。拿字面去比，\n        加一对引号就把替身包判成业务仓——而那一判之下 `--apply` 会把目标的真实现\n        覆盖成替身，退出码还是 0。这是本设计里唯一不可逆的错法。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        self.write_adapters(target, "BizA 的真实现")
        self.commit(target, "自己实现对接层")

        for written in ('adapters: "stand-in"', "adapters: 'stand-in'",
                        "adapters: stand-in  # 替身",
                        'adapters: "stand-in"  # 引号加注释',
                        "adapters: 'stand-in'  # 引号加注释"):
            pkg = self.pkg_with_manifest(lambda l, w=written: w if l.startswith("adapters:") else l)
            proc = self.adapt("--apply", target, pkg)
            self.assertEqual(0, proc.returncode, self.out(proc))
            self.assertIn("BizA 的真实现", self.adapter_text(target),
                          f"`{written}` 被判成业务仓，目标的真实现被替身盖了")

    def test_the_package_name_does_not_decide(self) -> None:
        """包改叫什么都不影响来源判断：写了 `adapters: stand-in` 就不给对接实现。"""
        target = self.blank_repo("BizA")
        pkg = self.pkg_with_manifest(lambda l: "name: renamed-demo" if l.startswith("name:") else l)
        proc = self.adapt("--apply", target, pkg)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / ADAPTERS).exists(), "换了包名就把替身装进业务仓了")

    def test_a_business_manifest_carries_no_stand_in_mark(self) -> None:
        """从替身包装出来的业务仓，manifest 里没有 `adapters` 那一行和它的注释。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        text = (target / "doc" / "extensions" / "manifest.yaml").read_text(encoding="utf-8")
        self.assertNotIn("adapters:", text)
        self.assertNotIn("替身", text)

    # ---- 安装结果 ----

    def test_a_broken_bridge_is_caught(self) -> None:
        """跳板在 `<ext>/` 之外，覆盖范围扫不到——不单独核，装坏的宿主入口没人管。\n\n        而它正是人每天敲 `/story` 打进来的地方（A7）。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        self.commit(target, "装好")
        (target / ".cac" / "commands" / "story.md").write_text("坏掉的内容\n", encoding="utf-8")

        proc = self.adapt("--check", target, REPO_ROOT)
        self.assertEqual(1, proc.returncode, "跳板被改坏却判通过了")
        self.assertIn("story.md", self.out(proc))

    def test_crlf_in_the_manifest_is_not_a_failure(self) -> None:
        """目标用什么换行是它的排版自由，不是「装错了」。\n\n        合成结果一律 LF，直接与盘上原文比字符串的话，一个内容完全正确的 CRLF 仓\n        会一直红，而报错还指着知识清单——修的人会去翻一份根本没问题的清单。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        raw = manifest.read_bytes()
        raw = raw.replace(bytes([13, 10]), bytes([10])).replace(bytes([10]), bytes([13, 10]))
        manifest.write_bytes(raw)

        proc = self.adapt("--check", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))

    # ---- 装到一个真实仓里 ----

    def test_it_adds_nothing_to_a_gitignore_that_already_covers_the_drafts(self) -> None:
        """需求目录整个不入库时，不再补那一行——一条永远不起作用的规则只是噪声。\n\n        目标怎么挡不管：自己写了那一行、或者 `doc/features/` 一行盖住底下的一切，\n        都算挡住了。两条模式等不等价，字符串比不出来，问 git。\n        """
        target = self.blank_repo("BizA")
        (target / ".gitignore").write_text("doc/features/\nbuild/\n", encoding="utf-8")
        self.commit(target, "需求目录整个不入库")

        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual("doc/features/\nbuild/\n",
                         (target / ".gitignore").read_text(encoding="utf-8"),
                         "已经被挡住了还往 .gitignore 里加")
        self.assertEqual(0, self.adapt("--check", target, REPO_ROOT).returncode)

    def test_the_section_lands_inside_the_extension_chapter(self) -> None:
        """扩展段落在讲实例扩展的那一节里，不是文件末尾。\n\n        入口文件是给读者的路标；追加在末尾的那一段，人打开文件时早就走过了。\n        原有内容不被打断，后面的章节也不该跑到它前面去。\n        """
        target = self.root / "WithChapter"
        target.mkdir()
        (target / "framework.config.json").write_text(
            json.dumps({"project_name": "WithChapter",
                        "paths": {"extension_dir": "doc/extensions"}}), encoding="utf-8")
        link_harness_yaml(target)
        (target / ".gitignore").write_text("doc/features/\n", encoding="utf-8")
        (target / "CLAUDE.md").write_text(
            "# 目标工程\n\n## 四、工作流\n\n### 实例扩展 Skill（doc/extensions）\n\n"
            "> 这一节原本就有的一句话。\n\n## 五、交付凭证\n\n收尾的内容。\n",
            encoding="utf-8")
        for rel in LAUNCHERS:
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO_ROOT / rel, dst)
        self.commit(target, "baseline")

        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertLess(text.index("<!-- story-ext:begin -->"), text.index("## 五、交付凭证"),
                        "扩展段跑到后面的章节去了")
        self.assertLess(text.index("这一节原本就有的一句话"),
                        text.index("<!-- story-ext:begin -->"),
                        "扩展段插在了原有内容前面，把它挤开了")

    def test_one_entry_file_is_enough(self) -> None:
        """目标有哪个入口文件是它自己的事——挂 Claude 的仓只有 `CLAUDE.md`。\n\n        要求某一个必须存在，等于替目标决定它用哪个宿主。\n        """
        target = self.blank_repo("BizA")
        (target / "AGENTS.md").unlink()
        (target / "CLAUDE.md").write_text("# 目标工程\n\n## 实例扩展\n", encoding="utf-8")
        self.commit(target, "这个仓只有 CLAUDE.md")

        self.assertEqual(0, self.adapt("--apply", target, REPO_ROOT).returncode)
        proc = self.adapt("--check", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))

    def test_the_packages_release_notes_do_not_travel(self) -> None:
        """`version:` 上面那段是发布包的演进记录，对装它的工程没有意义。\n\n        搬过去只会把目标写在同一处的话盖掉——目标想说的多半是「我们这个仓怎么用它」。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        head = manifest.read_text(encoding="utf-8").split("version:", 1)[0]
        self.assertNotIn("#", head, "包的演进记录跟着装进目标了")

        # 目标自己在那儿写了两句，升级不该动它。
        # 按行找 `version:` 那一行——`schema_version:` 也含这个子串，字符串替换会插错地方。
        rows = manifest.read_text(encoding="utf-8").split("\n")
        at = next(i for i, l in enumerate(rows) if l.startswith("version:"))
        rows[at:at] = ["# 这个仓怎么用它：只走 story 链。", "# 升级由平台组统一推。"]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(target, "目标写了自己的说明")
        self.adapt("--apply", target, REPO_ROOT)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("只走 story 链", after, "升级把目标自己的说明盖了")
        self.assertNotIn("1.7.0", after.split("version:", 1)[0])

    # ---- 目标的身份 ----

    def test_the_target_keeps_its_own_name_and_description(self) -> None:
        """`name` 与 `description` 归目标：首次按它的工程名生成，之后任何升级都不改。\n\n        改掉的话，目标的 manifest 就顶着发布源的名字——两个仓的产物看起来出自同一处。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        first = manifest.read_text(encoding="utf-8")
        self.assertIn("name: BizA", first, "首次安装没有按目标的工程名生成 name")
        self.assertIn("BizA 的实例扩展包", first)

        # 人改过描述之后再升级
        manifest.write_text(first.replace(
            "BizA 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）",
            "BizA：钱包业务的需求流程扩展"), encoding="utf-8")
        self.commit(target, "人把描述改准了")
        self.adapt("--apply", target, REPO_ROOT)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("BizA：钱包业务的需求流程扩展", after, "升级把目标改过的描述盖了")
        self.assertIn("name: BizA", after)

    def test_the_version_follows_the_package(self) -> None:
        """`version` 反过来归包：目标只能从它看出自己拿到的是哪一批产物形态。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, REPO_ROOT)
        pkg = (PKG_EXT / "manifest.yaml").read_text(encoding="utf-8")
        version = next(l for l in pkg.splitlines() if l.startswith("version:"))
        self.assertIn(version, (target / "doc" / "extensions" / "manifest.yaml")
                      .read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
