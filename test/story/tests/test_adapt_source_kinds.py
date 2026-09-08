"""两种来源：Demo 不给对接实现，业务仓之间共用一套（A12）。

Demo 包里的 `story.js` / `token.js` / `review.js` 是**替身**——用本地目录模拟需求系统，
复制到业务仓等于把人家的真实现盖掉。业务仓之间不一样：它们对接的是同一个需求系统，
共用同一套实现，复刻时正该带上。

判来源看包 `manifest.yaml` 的 `name`。它归目标、升级不改，所以每个仓的 manifest 里
那个名字始终是它自己的——「这个包从哪个仓发出来」有唯一答案，不必靠仓名长相、
目录结构或对接脚本的内容去猜。

这一份锁四件：Demo 来源不给也不覆盖对接实现；业务仓来源整体覆盖；目标的身份
（`name` / `description`）不被任何一次升级改掉；两种来源交替时各按各的规矩。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        for name in ("story.js", "token.js", "review.js"):
            (d / name).write_text(f"// {mark}\nmodule.exports = {{ who: '{mark}-{name}' }};\n",
                                  encoding="utf-8")

    def adapter_text(self, at: Path, name: str = "story.js") -> str:
        f = at / ADAPTERS / name
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    # ---- Demo 来源 ----

    def test_a_demo_install_does_not_hand_over_the_stand_ins(self) -> None:
        """Demo 装到新仓：给机制与知识骨架，**不给**三个对接替身。

        那三个是本地模拟，装到业务仓里跑起来会往一个不存在的目录读写需求单据。
        目标要自己实现，合同在 `scripts/README.md`。
        """
        target = self.blank_repo("BizA")
        proc = self.adapt("--apply", target, REPO_ROOT)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / ADAPTERS).exists(), "Demo 把对接替身装进业务仓了")
        self.assertTrue((target / "doc/extensions/skills/story/scripts/core").is_dir())

    def test_a_demo_upgrade_never_overwrites_a_real_implementation(self) -> None:
        """目标自己实现之后再从 Demo 升级：那三个文件一个字节不动。

        这是本设计要挡的最坏一种后果——业务仓的真实现被一次常规升级换成替身，
        而它跑起来还像是好的，只是读写的是另一个地方。
        """
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

    # ---- 目标的身份 ----

    def test_the_target_keeps_its_own_name_and_description(self) -> None:
        """`name` 与 `description` 归目标：首次按它的工程名生成，之后任何升级都不改。

        改掉的话，目标的 manifest 就顶着发布源的名字——两个仓的产物看起来出自同一处。
        """
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
