"""对接层的地盘归目标 —— 但机制面一寸不让。

## 为什么有这一份

`adapt-scan` 按**路径长相**分类：`skills/story/scripts/<name>.js` 是对接层，
`skills/story/**` 其余一概是机制。于是目标为自定义对接 js 装的依赖——
`package.json`（不是 `.js`）、`node_modules/**`（有下级目录）——统统落进机制，
撞上「机制目录文件集与内容 == 包」，恒 FAIL，目标**绕不过去**。

根因是分类靠路径长相，而路径长相回答不了「这是谁的东西」。adapt 上一次栽在
同一条上：知识文件按路径判成随包维护，于是目标写好的业务定义被一次升级盖掉。
SKILL.md §2 记着那次的教训——「只有模型读得懂哪些内容是这个工程的业务定义，
**路径读不懂**」。

所以这一层改成按**所有权**判：包里有的归包，包里没有的归目标。
下面前两条锁放宽后的行为，后三条锁「放宽之后机制仍然核得住」。
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
LAUNCHERS = (
    ".cac/commands/story.md", ".claude/commands/story.md",
    ".codex/skills/story/SKILL.md", ".opencode/skill/story/SKILL.md",
)


class AdaptOwnershipCase(unittest.TestCase):
    """每个用例搭一个「已装好扩展」的目标工程，跑真 `adapt-scan`。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "target"
        (self.target / "framework").mkdir(parents=True)
        (self.target / "framework" / "package.json").write_text(
            json.dumps({"name": "framework", "version": "0.0.1"}), encoding="utf-8")
        (self.target / "framework.config.json").write_text(json.dumps({
            "paths": {"extension_dir": "doc/extensions"},
        }, ensure_ascii=False), encoding="utf-8")
        shutil.copytree(PKG_EXT, self.target / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*"))
        for rel in LAUNCHERS:
            dst = self.target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO_ROOT / rel, dst)
        self.ext = self.target / "doc" / "extensions"
        self.scripts = self.ext / "skills" / "story" / "scripts"
        # 入口文件：判据 ⑤ 要它含扩展段（连同标记区）。
        section = self.ext / "skills" / "story" / "AGENTS.section.md"
        body = section.read_text(encoding="utf-8") if section.exists() else ""
        (self.target / "AGENTS.md").write_text(
            "# 目标工程\n\n## 实例扩展\n\n" + body, encoding="utf-8")

    def run_scan(self, mode: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(SCAN), mode, "--target", str(self.target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300)

    def check(self) -> subprocess.CompletedProcess:
        scan = self.run_scan("--scan")
        self.assertEqual(0, scan.returncode,
                         "--scan 失败：" + (scan.stderr or "")[:400])
        return self.run_scan("--check")


class TargetOwnedFilesUnderTheAdapterDir(AdaptOwnershipCase):

    def test_a_clean_target_passes(self) -> None:
        """基线：什么都不动，`--check` 必须过——不然下面几条测不出东西。"""
        proc = self.check()
        self.assertEqual(0, proc.returncode,
                         (proc.stdout or "") + (proc.stderr or ""))

    def test_custom_js_dependencies_are_not_blocked(self) -> None:
        """对接 js 的依赖闭包归目标：`package.json` 与 `node_modules/` 不该被拦。"""
        (self.scripts / "package.json").write_text(
            json.dumps({"name": "story-adapters", "dependencies": {"axios": "^1"}}),
            encoding="utf-8")
        dep = self.scripts / "node_modules" / "axios" / "lib"
        dep.mkdir(parents=True)
        (dep / "index.js").write_text("module.exports = {};\n", encoding="utf-8")
        proc = self.check()
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)
        for noise in ("package.json", "node_modules"):
            self.assertNotIn("机制多出旧文件：skills/story/scripts/" + noise, out)

    def test_an_unknown_dependency_shape_is_also_free(self) -> None:
        """判的是所有权不是文件名——没见过的依赖形态同样不该被拦。"""
        (self.scripts / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n",
                                                     encoding="utf-8")
        (self.scripts / "dist").mkdir()
        (self.scripts / "dist" / "bundle.mjs").write_text("export {};\n",
                                                          encoding="utf-8")
        self.assertEqual(0, self.check().returncode)


class TheMechanismStillHoldsAfterTheRelaxation(AdaptOwnershipCase):
    """放宽之后机制仍然核得住 —— 这三条是本项的硬门。"""

    def test_a_package_script_changed_by_one_byte_is_still_caught(self) -> None:
        """包里带来的机制脚本仍逐字核：改一个字节就要报。"""
        target_file = self.scripts / "story-build.mjs"
        target_file.write_text(target_file.read_text(encoding="utf-8") + "\n// x\n",
                               encoding="utf-8")
        proc = self.check()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("机制内容不同于包：skills/story/scripts/story-build.mjs",
                      (proc.stdout or "") + (proc.stderr or ""))

    def test_a_missing_package_script_is_still_caught(self) -> None:
        """包里有、目标没有——仍报缺文件。"""
        (self.scripts / "story-build.mjs").unlink()
        proc = self.check()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("机制缺文件：skills/story/scripts/story-build.mjs",
                      (proc.stdout or "") + (proc.stderr or ""))

    def test_the_relaxation_covers_only_the_adapter_dir(self) -> None:
        """只放宽对接层一个目录：`hooks/` 下多出来的文件仍报。

        那里没有「目标自己的东西」这个概念——目标要改机制，走方案页。
        """
        stray = self.ext / "hooks" / "shared" / "target-extra.mjs"
        stray.write_text("export const x = 1;\n", encoding="utf-8")
        proc = self.check()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("机制多出旧文件：hooks/shared/target-extra.mjs",
                      (proc.stdout or "") + (proc.stderr or ""))

    def test_the_adapter_js_itself_keeps_its_own_rule(self) -> None:
        """对接 js 本身照旧按 `js` 类处置，不按机制逐字核。"""
        js = self.scripts / "story.js"
        js.write_text(js.read_text(encoding="utf-8") + "\n// 目标自己的对接实现\n",
                      encoding="utf-8")
        proc = self.check()
        self.assertEqual(0, proc.returncode,
                         "对接 js 被当成机制逐字核了：" + (proc.stdout or "")[:400])


class TheRuleIsOwnershipNotAFileList(unittest.TestCase):

    def test_no_dependency_names_are_hardcoded(self) -> None:
        """判定逻辑里不许出现依赖文件名——那是词表式补丁。"""
        body = SCAN.read_text(encoding="utf-8")
        code = "\n".join(l for l in body.splitlines()
                         if not l.strip().startswith(("*", "//", "/*")))
        for name in ("node_modules", "package.json", "pnpm-lock"):
            self.assertNotIn(name, code, "判定逻辑写死了「%s」" % name)


if __name__ == "__main__":
    unittest.main()
