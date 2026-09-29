"""两种来源：Demo 不给对接实现，业务仓之间共用一套（A12）。\n\nDemo 包里的 `story.js` / `token.js` 是**替身**——用本地目录模拟需求系统，\n复制到业务仓等于把人家的真实现盖掉。业务仓之间不一样：它们对接的是同一个需求系统，\n共用同一套实现，复刻时正该带上。\n\n判来源看包 `adaptation.yaml` 的 `adapters`：写 `stand-in` 的包里是替身，没有这个键的是业务仓。\n它归目标、升级不改，所以每个仓说的都是它自己的对接层——不必靠仓名、\n目录结构或对接脚本的内容去猜。\n\n这一份锁四件：Demo 来源不给也不覆盖对接实现；业务仓来源整体覆盖；目标的身份\n（`name` / `description`）不被任何一次升级改掉；两种来源交替时各按各的规矩。\n"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml
from ext_workspace import REPO_ROOT, git_init_excluding_framework, installed_package, link_framework

#: 包：装好了开发源的临时消费工程——adapt 从包里的脚本起跑（运行态）
PKG_ROOT = installed_package()
PKG_EXT = PKG_ROOT / "doc" / "extensions"
SCAN = PKG_EXT / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
ENTRIES = PKG_EXT / "skills" / "story-adaptation" / "scripts" / "entries.mjs"
ADAPTERS = "doc/extensions/skills/story/scripts/adapters"
DEMO = REPO_ROOT / "demo"
#: demo 装着的 1.9.8 登记的宿主入口：1.x 目标的样子
LEGACY_ENTRIES = tuple(b["target"] for b in yaml.safe_load(
    (DEMO / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))["provides"].get("bridges", []))
#: 本次要物化的一个 Skill 入口位置；3.0 时代的 render-agents-md 在这里生成过无归属标记的跳板
LEGACY_STUB = ".agents/skills/story-adaptation/SKILL.md"
LEGACY_STUB_TEXT = ("---\nname: story-adaptation\ndescription: Framework Skill\n---\n\n# 跳板文件\n\n"
                    "完整 Skill 定义请阅读：doc/extensions/skills/story-adaptation/SKILL.md\n")


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

    def blank_repo(self, project: str, adapters: list[str] | None = None) -> Path:
        """一个接入了 Framework、还没装扩展的空仓：入口文件由 Framework 按「没有扩展」物化，已提交。"""
        at = self.root / project
        at.mkdir(parents=True)
        config = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
        config["project_name"] = project
        if adapters is not None:
            config["materialized_adapters"] = adapters
        (at / "framework.config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        link_framework(at)
        (at / ".gitignore").write_text(
            "doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")
        self.entries(at, "materialize")
        self.commit(at, "baseline")
        return at

    def legacy_repo(self, project: str = "Legacy", keep_stub: bool = False) -> Path:
        """一个装着 1.9.8 的目标：demo 发布时装进去的扩展、六份旧入口与带 story-ext 段的入口文件，已提交。"""
        at = self.root / project
        at.mkdir(parents=True)
        link_framework(at)
        shutil.copytree(DEMO / "doc" / "extensions", at / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for rel in (*LEGACY_ENTRIES, "AGENTS.md", "CLAUDE.md", ".gitignore"):
            (at / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DEMO / rel, at / rel)
        if keep_stub:
            (at / LEGACY_STUB).parent.mkdir(parents=True, exist_ok=True)
            (at / LEGACY_STUB).write_text(LEGACY_STUB_TEXT, encoding="utf-8")
        self.commit(at, "1.9.8 installed")
        return at

    def entries(self, at: Path, action: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(["node", str(ENTRIES), "--project-root", str(at), "--action", action],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, self.out(proc))
        return proc

    def snapshot(self, at: Path) -> dict[str, bytes]:
        return {p.relative_to(at).as_posix(): p.read_bytes() for p in at.rglob("*")
                if p.is_file() and not {".git", "framework"} & set(p.relative_to(at).parts)}

    def commit(self, at: Path, message: str) -> None:
        run = lambda *a: subprocess.run(["git", "-C", str(at), *a], capture_output=True,
                                        text=True, encoding="utf-8", timeout=120)
        if not (at / ".git").exists():
            git_init_excluding_framework(at)
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
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / ADAPTERS).exists(), "Demo 把对接替身装进业务仓了")
        self.assertTrue((target / "doc/extensions/skills/story/scripts/core").is_dir())

    def test_a_demo_upgrade_never_overwrites_a_real_implementation(self) -> None:
        """目标自己实现之后再从 Demo 升级：那三个文件一个字节不动。\n\n        这是本设计要挡的最坏一种后果——业务仓的真实现被一次常规升级换成替身，\n        而它跑起来还像是好的，只是读写的是另一个地方。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        self.write_adapters(target, "BizA 的真实现")
        self.commit(target, "自己实现对接层")

        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target))

    # ---- 业务仓之间 ----

    def source_repo(self, project: str = "BizA") -> Path:
        """一个装好、且自己实现了对接层的业务仓——它就是复刻的来源。"""
        at = self.blank_repo(project)
        self.adapt("--apply", at, PKG_ROOT)
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

        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target))

    # ---- 按版本跟进 ----

    def follow_up(self, proc: subprocess.CompletedProcess) -> dict:
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        return json.loads(line.split("按版本跟进：", 1)[1])

    def test_an_unadapted_target_gets_every_block_from_a_stand_in_source(self) -> None:
        """目标没写 adapted_for、装的是旧版（旧装的仓都是这样）：从头列出各版条目；替身来源不给对接层，那一块照列。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        self.set_version(target, "1.9.3")
        proc = self.adapt("--apply", target, PKG_ROOT)
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
        self.adapt("--apply", target, PKG_ROOT)
        self.set_version(target, "1.9.6")
        got = self.follow_up(self.adapt("--apply", target, PKG_ROOT))
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

    def pkg_with_manifest(self, rewrite, adaptation: str | None = None) -> Path:
        """Demo 包的一份拷贝，manifest 逐行经 `rewrite` 改写；给了 `adaptation` 就换掉包的 adaptation.yaml。"""
        pkg = self.root / "rewritten-pkg"
        if pkg.exists():
            shutil.rmtree(pkg)
        link_framework(pkg)
        shutil.copytree(PKG_EXT, pkg / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".*"))
        manifest = pkg / "doc" / "extensions" / "manifest.yaml"
        manifest.write_text("\n".join(rewrite(l) for l in manifest.read_text(encoding="utf-8").split("\n")),
                            encoding="utf-8")
        if adaptation is not None:
            (pkg / "doc" / "extensions" / "adaptation.yaml").write_text(adaptation, encoding="utf-8")
        return pkg

    def test_yaml_quoting_does_not_change_the_source_kind(self) -> None:
        """`adapters` 取的是 YAML 的**值**，不是那一行的字面。\n\n        `adapters: stand-in` 与 `adapters: "stand-in"` 是同一个值。拿字面去比，\n        加一对引号就把替身包判成业务仓——而那一判之下 `--apply` 会把目标的真实现\n        覆盖成替身，退出码还是 0。这是本设计里唯一不可逆的错法。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        self.write_adapters(target, "BizA 的真实现")
        self.commit(target, "自己实现对接层")

        for written in ('adapters: "stand-in"', "adapters: 'stand-in'",
                        "adapters: stand-in  # 替身",
                        'adapters: "stand-in"  # 引号加注释',
                        "adapters: 'stand-in'  # 引号加注释"):
            pkg = self.pkg_with_manifest(lambda l: l, adaptation=written + "\n")
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

    def test_a_business_repo_carries_no_stand_in_mark(self) -> None:
        """从替身包装出来的业务仓：manifest 不写适配状态，adaptation.yaml 是空映射——替身身份属于包，不属于它。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        text = (target / "doc" / "extensions" / "manifest.yaml").read_text(encoding="utf-8")
        self.assertNotIn("adapters:", text)
        self.assertNotIn("adapted_for:", text)
        self.assertEqual("{}\n", (target / "doc" / "extensions" / "adaptation.yaml").read_text(encoding="utf-8"))

    # ---- 安装结果 ----

    def test_a_broken_bridge_is_caught(self) -> None:
        """宿主入口在 `<ext>/` 之外，覆盖范围扫不到——`--check` 按 Framework 的入口核对报出来。

        而它正是人每天敲 `/story` 打进来的地方。
        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        self.commit(target, "装好")
        (target / ".cac" / "commands" / "story.md").write_text("坏掉的内容\n", encoding="utf-8")

        proc = self.adapt("--check", target, PKG_ROOT)
        self.assertEqual(1, proc.returncode, "宿主入口被改坏却判通过了")
        self.assertIn(".cac/commands/story.md", self.out(proc))

    def test_crlf_in_the_manifest_is_not_a_failure(self) -> None:
        """目标用什么换行是它的排版自由，不是「装错了」。\n\n        合成结果一律 LF，直接与盘上原文比字符串的话，一个内容完全正确的 CRLF 仓\n        会一直红，而报错还指着知识清单——修的人会去翻一份根本没问题的清单。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        raw = manifest.read_bytes()
        raw = raw.replace(bytes([13, 10]), bytes([10])).replace(bytes([10]), bytes([13, 10]))
        manifest.write_bytes(raw)

        proc = self.adapt("--check", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))

    # ---- 装到一个真实仓里 ----

    def test_it_adds_nothing_to_a_gitignore_that_already_covers_the_drafts(self) -> None:
        """需求目录整个不入库时，不再补那一行——一条永远不起作用的规则只是噪声。\n\n        目标怎么挡不管：自己写了那一行、或者 `doc/features/` 一行盖住底下的一切，\n        都算挡住了。两条模式等不等价，字符串比不出来，问 git。\n        """
        target = self.blank_repo("BizA")
        (target / ".gitignore").write_text("doc/features/\nbuild/\n", encoding="utf-8")
        self.commit(target, "需求目录整个不入库")

        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual("doc/features/\nbuild/\n",
                         (target / ".gitignore").read_text(encoding="utf-8"),
                         "已经被挡住了还往 .gitignore 里加")
        self.assertEqual(0, self.adapt("--check", target, PKG_ROOT).returncode)

    def test_an_edited_entry_file_stops_before_writing(self) -> None:
        """入口文件里有 Framework 生成之外的内容：物化会整份重写它，写前就停、点名文件、一个字节不写。"""
        target = self.blank_repo("BizA")
        claude = target / "CLAUDE.md"
        claude.write_text(claude.read_text(encoding="utf-8") + "\n## 我们自己的约定\n\n只在周五发版。\n",
                          encoding="utf-8")
        self.commit(target, "人在 CLAUDE.md 里加了一节")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("CLAUDE.md", self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_the_entry_files_follow_the_targets_hosts(self) -> None:
        """目标用哪些宿主是它自己的事：只物化 claude 的仓只有 `CLAUDE.md`，装完与自检都照它来。"""
        target = self.blank_repo("BizA", adapters=["claude"])
        self.assertFalse((target / "AGENTS.md").exists())
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / "AGENTS.md").exists(), "替目标加了它不用的宿主入口")
        self.assertTrue((target / ".claude" / "commands" / "story.md").is_file())
        self.assertFalse((target / ".codex").exists(), "替目标物化了它不用的宿主")
        check = self.adapt("--check", target, PKG_ROOT)
        self.assertEqual(0, check.returncode, self.out(check))

    def test_the_packages_release_notes_do_not_travel(self) -> None:
        """`version:` 上面那段是发布包的演进记录，对装它的工程没有意义。\n\n        搬过去只会把目标写在同一处的话盖掉——目标想说的多半是「我们这个仓怎么用它」。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
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
        self.adapt("--apply", target, PKG_ROOT)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("只走 story 链", after, "升级把目标自己的说明盖了")
        self.assertNotIn("1.7.0", after.split("version:", 1)[0])

    # ---- 目标的身份 ----

    def test_the_target_keeps_its_own_name_and_description(self) -> None:
        """`name` 与 `description` 归目标：首次按它的工程名生成，之后任何升级都不改。\n\n        改掉的话，目标的 manifest 就顶着发布源的名字——两个仓的产物看起来出自同一处。\n        """
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        first = manifest.read_text(encoding="utf-8")
        self.assertIn("name: biz-a", first, "首次安装没有按目标的工程名生成 name（Framework 只认小写 slug）")
        self.assertIn("BizA 的实例扩展包", first)

        # 人改过描述之后再升级
        manifest.write_text(first.replace(
            "BizA 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）",
            "BizA：钱包业务的需求流程扩展"), encoding="utf-8")
        self.commit(target, "人把描述改准了")
        self.adapt("--apply", target, PKG_ROOT)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("BizA：钱包业务的需求流程扩展", after, "升级把目标改过的描述盖了")
        self.assertIn("name: biz-a", after)

    def test_the_version_follows_the_package(self) -> None:
        """`version` 反过来归包：目标只能从它看出自己拿到的是哪一批产物形态。"""
        target = self.blank_repo("BizA")
        self.adapt("--apply", target, PKG_ROOT)
        pkg = (PKG_EXT / "manifest.yaml").read_text(encoding="utf-8")
        version = next(l for l in pkg.splitlines() if l.startswith("version:"))
        self.assertIn(version, (target / "doc" / "extensions" / "manifest.yaml")
                      .read_text(encoding="utf-8"))

    # ---- 宿主入口 ----

    def test_every_skill_gets_a_framework_owned_entry(self) -> None:
        """新工程装完：包登记的每个 Skill 在每个宿主都有一份带 Framework 归属标记、指向扩展 SKILL 的入口。"""
        target = self.blank_repo("Fresh")
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        skills = yaml.safe_load((PKG_EXT / "manifest.yaml").read_text(encoding="utf-8"))["provides"]["skills"]
        for skill in skills:
            for rel in (f".claude/commands/{skill}.md", f".opencode/skill/{skill}/SKILL.md",
                        f".codex/skills/{skill}/SKILL.md"):
                with self.subTest(entry=rel):
                    text = (target / rel).read_text(encoding="utf-8")
                    self.assertIn("agent-maison:instance-extension-bridge", text)
                    self.assertIn(f"doc/extensions/skills/{skill}/SKILL.md", text)

    # ---- 从 1.x 升上来 ----

    def test_a_1x_install_is_upgraded_in_place(self) -> None:
        """装着 1.9.8 的目标：适配状态迁进 adaptation.yaml，旧入口与 story-ext 段退出，入口改由 Framework 物化。"""
        target = self.legacy_repo()
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        ext = target / "doc" / "extensions"
        adaptation = yaml.safe_load((ext / "adaptation.yaml").read_text(encoding="utf-8"))
        old = yaml.safe_load((DEMO / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual({k: old[k] for k in ("adapters", "adapted_for")}, adaptation)
        manifest = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual("1.1", manifest["schema_version"])
        self.assertFalse({"adapters", "adapted_for"} & set(manifest))
        self.assertNotIn("bridges", manifest["provides"])
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertNotIn("story-ext", (target / name).read_text(encoding="utf-8"), name)
        for rel in LEGACY_ENTRIES:
            self.assertIn("agent-maison:instance-extension-bridge", (target / rel).read_text(encoding="utf-8"), rel)
        self.assertEqual(0, self.adapt("--check", target, PKG_ROOT).returncode)
        self.commit(target, "升到 2.0")
        again = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(0, again.returncode, self.out(again))
        self.assertIn("当前适配仍有效", self.out(again))

    def test_an_unowned_legacy_stub_stops_before_writing(self) -> None:
        """入口位置上有无归属标记、也不是已装旧版登记的文件：不接管、不覆盖，写前停并点名。"""
        target = self.legacy_repo(keep_stub=True)
        before = self.snapshot(target)
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(LEGACY_STUB, self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_an_edited_old_entry_stops_before_writing(self) -> None:
        """已装旧版登记的入口被人改过：与旧发布源不同，不能当作扩展的东西撤掉。"""
        target = self.legacy_repo()
        edited = target / LEGACY_ENTRIES[0]
        edited.write_text(edited.read_text(encoding="utf-8") + "\n我们自己补的一句。\n", encoding="utf-8")
        self.commit(target, "人改了旧入口")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(LEGACY_ENTRIES[0], self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_conflicting_adaptation_values_stop_before_writing(self) -> None:
        """旧 manifest 与已有 adaptation.yaml 对同一项写了不同的值：由人定用哪一个，脚本不替他选。"""
        target = self.legacy_repo()
        (target / "doc" / "extensions" / "adaptation.yaml").write_text('adapted_for: "1.9.3"\n', encoding="utf-8")
        self.commit(target, "两处写了不同的已适配版本")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target, PKG_ROOT)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("adapted_for", self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")


if __name__ == "__main__":
    unittest.main()
