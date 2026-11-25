"""三方发行与就地适配边界：`base/` 零替身、`adapters/` 归业务、宿主入口/忽略规则/1.x 混装升级与写前保护。

2.0.6 起外网通用机制发行包只含 `base/`（零 Demo 替身），业务侧自行在 `<ext>/adapters/` 维护真实对接实现，
`adapt-scan.mjs` 在目标工程内就地运行，不碰 `adapters/` 与 `knowledge/`。

本文件锁：
  · `base/` 首装不带对接替身；升级不覆盖业务 `adapters/`；
  · 演进记录解析严格拒绝缩进子项与缺块标签（写前停）；
  · 坏宿主入口、CRLF manifest、`.gitignore` 覆盖与父目录阻断、`lifecycle_hooks_enabled: false`、目标知识登记错误、手改入口冲突；
  · 目标身份（`name`/`description`/`version:` 上方自写注释）跨升级保留，每个 Skill 指向 `base/skills/`；
  · 1.9.8 旧混装仓就地升级到 `base/` 布局（迁走旧机制与旧入口、保知识与状态、写前拦冲突）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml
from ext_workspace import (DEV_BASE, REPO_ROOT, change_versions, git_init_excluding_framework,
                           installed_package, link_framework)

PKG_ROOT = installed_package()
PKG_EXT = PKG_ROOT / "doc" / "extensions"
ENTRIES_REF = DEV_BASE / "skills" / "story-adaptation" / "scripts" / "entries.mjs"
ADAPTERS = "doc/extensions/adapters"
DEMO = REPO_ROOT / "demo"
LEGACY_ENTRIES = tuple(b["target"] for b in yaml.safe_load(
    (DEMO / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))["provides"].get("bridges", []))
LEGACY_STUB = ".agents/skills/story-adaptation/SKILL.md"
LEGACY_STUB_TEXT = ("---\nname: story-adaptation\ndescription: Framework Skill\n---\n\n# 跳板文件\n\n"
                    "完整 Skill 定义请阅读：doc/extensions/skills/story-adaptation/SKILL.md\n")


class InPlaceAdaptCase(unittest.TestCase):
    """目标仓已解包 `doc/extensions/base/`，在目标内就地运行 `adapt-scan.mjs`。"""

    def setUp(self) -> None:  # noqa: D102
        for tool in ("node", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"环境里没有 {tool}")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def blank_repo(self, project: str, adapters: list[str] | None = None) -> Path:
        """一个接入了被测 Framework、已解包 `base/` 但尚未 `--apply` 的新仓，已提交。"""
        at = self.root / project
        at.mkdir(parents=True)
        config = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
        config["project_name"] = project
        if adapters is not None:
            config["materialized_adapters"] = adapters
        (at / "framework.config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        link_framework(at)
        (at / ".gitignore").write_text("doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")
        self.entries(at, "materialize")
        shutil.copytree(DEV_BASE, at / "doc" / "extensions" / "base", ignore=shutil.ignore_patterns("__pycache__"))
        self.commit(at, "baseline with base")
        return at

    def legacy_repo(self, project: str = "Legacy", keep_stub: bool = False) -> Path:
        """一个装着 1.9.8 混装布局的目标仓，同时已把新版 `base/` 解包到位，准备就地升级。"""
        at = self.root / project
        at.mkdir(parents=True)
        link_framework(at)
        shutil.copytree(DEMO / "doc" / "extensions", at / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for rel in (*LEGACY_ENTRIES, ".gitignore"):
            (at / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DEMO / rel, at / rel)
        scratch = self.root / f"{project}-render"
        shutil.copytree(at, scratch, ignore=lambda d, names: ["framework"] if Path(d) == at else [])
        link_framework(scratch)
        for rel in LEGACY_ENTRIES:
            (scratch / rel).unlink()
        self.entries(scratch, "materialize")
        for name in ("AGENTS.md", "CLAUDE.md"):
            legacy = (DEMO / name).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
            begin = next(i for i, l in enumerate(legacy) if "<!-- story-ext:begin" in l)
            end = next(i for i, l in enumerate(legacy) if "<!-- story-ext:end" in l)
            rendered = (scratch / name).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
            (at / name).write_bytes((rendered + "\n\n" + "\n".join(legacy[begin:end + 1]) + "\n").encode("utf-8"))
        if keep_stub:
            (at / LEGACY_STUB).parent.mkdir(parents=True, exist_ok=True)
            (at / LEGACY_STUB).write_text(LEGACY_STUB_TEXT, encoding="utf-8")
        shutil.copytree(DEV_BASE, at / "doc" / "extensions" / "base", ignore=shutil.ignore_patterns("__pycache__"))
        self.commit(at, "1.9.8 installed + new base unpacked")
        return at

    def entries(self, at: Path, action: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(["node", str(ENTRIES_REF), "--project-root", str(at), "--action", action],
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

    def adapt(self, mode: str, target: Path) -> subprocess.CompletedProcess:
        scan = target / "doc" / "extensions" / "base" / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
        return subprocess.run(
            ["node", str(scan), mode],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def out(self, proc: subprocess.CompletedProcess) -> str:
        return ((proc.stdout or "") + (proc.stderr or "")).strip()

    def write_adapters(self, at: Path, mark: str) -> None:
        d = at / ADAPTERS
        d.mkdir(parents=True, exist_ok=True)
        for name in ("story.js", "token.js"):
            (d / name).write_text(f"// {mark}\nmodule.exports = {{ who: '{mark}-{name}' }};\n", encoding="utf-8")

    def adapter_text(self, at: Path, name: str = "story.js") -> str:
        f = at / ADAPTERS / name
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def follow_up(self, proc: subprocess.CompletedProcess) -> dict:
        line = next(l for l in proc.stdout.splitlines() if "按版本跟进：" in l)
        return json.loads(line.split("按版本跟进：", 1)[1])

    def set_version(self, target: Path, version: str) -> None:
        manifest = target / "doc/extensions/manifest.yaml"
        rows = [f'version: "{version}"' if l.startswith("version:") else l
                for l in manifest.read_text(encoding="utf-8").split("\n")]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(target, f"装的是 {version}")


class BasePackageAndAdapterOwnership(InPlaceAdaptCase):
    """通用包零替身；业务 `adapters/` 由业务仓维护、升级永不覆盖。"""

    def test_a_base_install_does_not_hand_over_stand_ins(self) -> None:
        target = self.blank_repo("BizA")
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / ADAPTERS).exists(), "通用包把对接替身装进业务仓了")
        self.assertFalse((target / "doc/extensions/base/skills/story/scripts/adapters").exists())
        self.assertTrue((target / "doc/extensions/base/skills/story/scripts/core").is_dir())

    def test_a_base_upgrade_never_overwrites_business_adapters(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        self.write_adapters(target, "BizA 的真实现")
        self.commit(target, "自己实现对接层")

        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertIn("BizA 的真实现", self.adapter_text(target))
        self.assertEqual("present", self.follow_up(proc)["adapters"]["status"])

    def test_a_business_repo_carries_no_stand_in_mark(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        text = (target / "doc" / "extensions" / "manifest.yaml").read_text(encoding="utf-8")
        self.assertNotIn("adapters:", text)
        self.assertNotIn("adapted_for:", text)
        self.assertEqual("{}\n", (target / "doc" / "extensions" / "adaptation.yaml").read_text(encoding="utf-8"))


class TheAdapterBlocks(InPlaceAdaptCase):
    """演进块：未适配目标拿到知识与对接层两块；坏演进记录写前停。"""

    def test_an_unadapted_target_gets_every_block(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        self.set_version(target, "1.9.3")
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        got = self.follow_up(proc)
        self.assertEqual("0", got["since"])
        self.assertEqual({"知识", "对接层"}, set(got["items"]), "跟进只有知识与对接层两块")
        for block, items in got["items"].items():
            with self.subTest(block=block):
                self.assertTrue(items, f"{block} 一条都没列")
        self.assertTrue(any(i.startswith("1.9.4：") for i in got["items"]["对接层"]))
        self.assertEqual(change_versions(PKG_EXT, "知识")[0], got["items"]["知识"][0].split("：", 1)[0],
                         "知识没从最早一节（基线）列起")
        self.assertIn("停一次问人", proc.stdout)

    def test_the_installed_version_is_a_fact_not_a_filter(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        self.set_version(target, "1.9.6")
        got = self.follow_up(self.adapt("--apply", target))
        self.assertEqual("1.9.6", got["installed"])
        self.assertEqual({"知识", "对接层"}, set(got["items"]))
        self.assertTrue(any(i.startswith("1.9.5：") for i in got["items"]["知识"]), "按装的版本筛掉了知识条目")

    def test_an_indented_sub_item_stops_before_writing(self) -> None:
        target = self.blank_repo("BizA")
        changes = target / "doc/extensions/base/skills/story-adaptation/reference/upgrade-changes.md"
        changes.write_text(changes.read_text(encoding="utf-8") + "  - 缩进的子项\n", encoding="utf-8")
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("不用子项", self.out(proc))

    def test_an_entry_without_a_block_stops_before_writing(self) -> None:
        target = self.blank_repo("BizA")
        changes = target / "doc/extensions/base/skills/story-adaptation/reference/upgrade-changes.md"
        changes.write_text(changes.read_text(encoding="utf-8") + "- 没标块的一条\n", encoding="utf-8")
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("没有块标签", self.out(proc))
        self.assertFalse((target / "doc/extensions/manifest.yaml").exists(), "停之前已经写过盘了")


class HostBridgesAndLineEndings(InPlaceAdaptCase):
    def test_a_broken_bridge_is_caught(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        self.commit(target, "装好")
        (target / ".cac" / "commands" / "story.md").write_text("坏掉的内容\n", encoding="utf-8")
        proc = self.adapt("--check", target)
        self.assertEqual(1, proc.returncode, "宿主入口被改坏却判通过了")
        self.assertIn(".cac/commands/story.md", self.out(proc))

    def test_crlf_in_the_manifest_is_not_a_failure(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        raw = manifest.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        manifest.write_bytes(raw)
        proc = self.adapt("--check", target)
        self.assertEqual(0, proc.returncode, self.out(proc))


class WhatTheTargetGets(InPlaceAdaptCase):
    """目标工程拿到什么：忽略规则、知识登记核对、宿主入口、生命周期钩子提醒，发布说明不随行。"""

    def test_it_adds_nothing_to_a_gitignore_that_already_covers_the_drafts(self) -> None:
        target = self.blank_repo("BizA")
        (target / ".gitignore").write_text("doc/features/\nbuild/\n", encoding="utf-8")
        self.commit(target, "需求目录整个不入库")

        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertEqual("doc/features/\nbuild/\n/doc/usage.json.lock\n/doc/.usage.json.*.tmp\n",
                         (target / ".gitignore").read_text(encoding="utf-8"),
                         "已经被挡住了还往 .gitignore 里加")
        self.assertEqual(0, self.adapt("--check", target).returncode)

    def git_add_takes(self, target: Path, rel: str) -> bool:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("{}\n", encoding="utf-8")
        return subprocess.run(["git", "-C", str(target), "add", "--dry-run", rel], capture_output=True,
                              text=True, encoding="utf-8").returncode == 0

    def test_the_usage_record_can_be_added_and_its_work_files_cannot(self) -> None:
        target = self.blank_repo("BizU")
        (target / ".gitignore").write_text("doc/*\n!doc/features/\n", encoding="utf-8")
        self.commit(target, "doc 下的文件默认不入库")
        self.assertFalse(self.git_add_takes(target, "doc/usage.json"), "前提不成立：规则本来就没挡住")
        (target / "doc" / "usage.json").unlink()
        self.assertNotEqual(0, self.adapt("--check", target).returncode, "挡住了却说核对通过")
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertTrue(self.git_add_takes(target, "doc/usage.json"), "放行之后普通 git add 仍纳入不了")
        for rel in ("doc/features/AR1/.usage-input.json", "doc/features/.usage-state.json",
                    "doc/usage.json.lock", "doc/.usage.json.123.tmp"):
            with self.subTest(rel):
                self.assertFalse(self.git_add_takes(target, rel), f"{rel} 没被挡住")
        check = self.adapt("--check", target)
        self.assertEqual(0, check.returncode, self.out(check))

    def test_disabled_lifecycle_hooks_are_named_and_left_as_the_target_set_them(self) -> None:
        target = self.blank_repo("BizH")
        self.assertEqual(0, self.adapt("--apply", target).returncode)
        self.commit(target, "装好")
        on = self.adapt("--check", target)
        self.assertEqual(0, on.returncode, self.out(on))
        self.assertNotIn("采集限制", self.out(on))
        cfg_file = target / "framework.config.json"
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        cfg_file.write_text(json.dumps({**cfg, "lifecycle_hooks_enabled": False}, ensure_ascii=False), encoding="utf-8")
        off = self.adapt("--check", target)
        self.assertIn("采集限制", off.stdout, "钩子被关了，检查却和开着时一样")
        self.assertIn("lifecycle_hooks_enabled", off.stdout)
        self.commit(target, "目标关掉生命周期钩子")
        applied = self.adapt("--apply", target)
        self.assertIn("采集限制", applied.stdout, self.out(applied))
        self.assertIs(False, json.loads(cfg_file.read_text(encoding="utf-8"))["lifecycle_hooks_enabled"], "adapt 改了目标的设置")
        hook = target / "doc" / "extensions" / "base" / "hooks" / "shared" / "usage.mjs"
        hook.unlink()
        missing = self.adapt("--check", target)
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("usage.mjs", self.out(missing))
        shutil.copy2(DEV_BASE / "hooks" / "shared" / "usage.mjs", hook)
        cfg_file.write_text(json.dumps({**cfg, "lifecycle_hooks_enabled": True}, ensure_ascii=False), encoding="utf-8")
        back = self.adapt("--check", target)
        self.assertEqual(0, back.returncode, self.out(back))
        self.assertNotIn("采集限制", self.out(back))

    def test_a_parent_directory_rule_is_named_not_papered_over(self) -> None:
        target = self.blank_repo("BizV")
        (target / ".gitignore").write_text("doc/\n", encoding="utf-8")
        self.commit(target, "doc 整个不入库")
        proc = self.adapt("--apply", target)
        self.assertIn("仍被 .gitignore:1:doc/", self.out(proc))
        check = self.adapt("--check", target)
        self.assertNotEqual(0, check.returncode)
        self.assertIn("使用记录 doc/usage.json 被", self.out(check))

    def test_a_target_knowledge_registration_framework_rejects_stops_before_writing(self) -> None:
        target = self.legacy_repo()
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace(
            "  knowledge:\n", "  knowledge:\n    - knowledge/facts/gone.md\n", 1), encoding="utf-8")
        self.commit(target, "目标登记了一份不存在的知识")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("knowledge_missing", self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_an_edited_entry_file_stops_before_writing(self) -> None:
        target = self.blank_repo("BizA")
        claude = target / "CLAUDE.md"
        claude.write_text(claude.read_text(encoding="utf-8") + "\n## 我们自己的约定\n\n只在周五发版。\n",
                          encoding="utf-8")
        self.commit(target, "人在 CLAUDE.md 里加了一节")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("CLAUDE.md", self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_the_entry_files_follow_the_targets_hosts(self) -> None:
        target = self.blank_repo("BizA", adapters=["claude"])
        self.assertFalse((target / "AGENTS.md").exists())
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        self.assertFalse((target / "AGENTS.md").exists(), "替目标加了它不用的宿主入口")
        self.assertTrue((target / ".claude" / "commands" / "story.md").is_file())
        self.assertFalse((target / ".codex").exists(), "替目标物化了它不用的宿主")
        check = self.adapt("--check", target)
        self.assertEqual(0, check.returncode, self.out(check))

    def test_the_packages_release_notes_do_not_travel(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        head = manifest.read_text(encoding="utf-8").split("version:", 1)[0]
        self.assertNotIn("#", head, "包的演进记录跟着装进目标了")

        rows = manifest.read_text(encoding="utf-8").split("\n")
        at = next(i for i, l in enumerate(rows) if l.startswith("version:"))
        rows[at:at] = ["# 这个仓怎么用它：只走 story 链。", "# 升级由平台组统一推。"]
        manifest.write_text("\n".join(rows), encoding="utf-8")
        self.commit(target, "目标写了自己的说明")
        self.adapt("--apply", target)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("只走 story 链", after, "升级把目标自己的说明盖了")
        self.assertNotIn("1.7.0", after.split("version:", 1)[0])


class IdentityAndUpgrade(InPlaceAdaptCase):
    def test_the_target_keeps_its_own_name_and_description(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        manifest = target / "doc" / "extensions" / "manifest.yaml"
        first = manifest.read_text(encoding="utf-8")
        self.assertIn("name: biz-a", first, "首次安装没有按目标的工程名生成 name")
        self.assertIn("BizA 的实例扩展包", first)

        manifest.write_text(first.replace(
            "BizA 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）",
            "BizA：钱包业务的需求流程扩展"), encoding="utf-8")
        self.commit(target, "人把描述改准了")
        self.adapt("--apply", target)
        after = manifest.read_text(encoding="utf-8")
        self.assertIn("BizA：钱包业务的需求流程扩展", after, "升级把目标改过的描述盖了")
        self.assertIn("name: biz-a", after)

    def test_the_version_follows_the_package(self) -> None:
        target = self.blank_repo("BizA")
        self.adapt("--apply", target)
        pkg = (DEV_BASE / "package-manifest.yaml").read_text(encoding="utf-8")
        version = next(l for l in pkg.splitlines() if l.startswith("version:"))
        self.assertIn(version, (target / "doc" / "extensions" / "manifest.yaml").read_text(encoding="utf-8"))

    def test_every_skill_gets_a_framework_owned_entry_pointing_to_base(self) -> None:
        target = self.blank_repo("Fresh")
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        skills = yaml.safe_load((DEV_BASE / "package-manifest.yaml").read_text(encoding="utf-8"))["provides"]["skills"]
        for skill in skills:
            for rel in (f".claude/commands/{skill}.md", f".opencode/skill/{skill}/SKILL.md",
                        f".codex/skills/{skill}/SKILL.md"):
                with self.subTest(entry=rel):
                    text = (target / rel).read_text(encoding="utf-8")
                    self.assertIn("agent-maison:instance-extension-bridge", text)
                    self.assertIn(f"doc/extensions/base/skills/{skill}/SKILL.md", text)

    def test_a_1x_install_is_upgraded_in_place(self) -> None:
        """装着 1.9.8 混装布局的目标：迁走旧机制与旧入口、保知识与状态、入口指向 base/skills/。"""
        target = self.legacy_repo()
        proc = self.adapt("--apply", target)
        self.assertEqual(0, proc.returncode, self.out(proc))
        ext = target / "doc" / "extensions"
        adaptation = yaml.safe_load((ext / "adaptation.yaml").read_text(encoding="utf-8"))
        old = yaml.safe_load((DEMO / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual({k: old[k] for k in ("adapters", "adapted_for")}, adaptation)
        manifest = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual("1.1", manifest["schema_version"])
        self.assertFalse({"adapters", "adapted_for"} & set(manifest))
        self.assertNotIn("bridges", manifest["provides"])
        for d in ("hooks", "rules", "skills"):
            self.assertFalse((ext / d).exists(), f"旧机制目录 {d}/ 未退出")
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertNotIn("story-ext", (target / name).read_text(encoding="utf-8"), name)
        for rel in LEGACY_ENTRIES:
            text = (target / rel).read_text(encoding="utf-8")
            self.assertIn("agent-maison:instance-extension-bridge", text, rel)
            self.assertIn("doc/extensions/base/skills/", text, rel)
        self.assertEqual(0, self.adapt("--check", target).returncode)
        self.commit(target, "升到 2.0.6")
        again = self.adapt("--apply", target)
        self.assertEqual(0, again.returncode, self.out(again))
        self.assertIn("机制已在包的版本上", self.out(again))


class IdentityAndUpgradePart2(InPlaceAdaptCase):
    def test_an_unowned_legacy_stub_stops_before_writing(self) -> None:
        target = self.legacy_repo(keep_stub=True)
        before = self.snapshot(target)
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(LEGACY_STUB, self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_an_edited_old_entry_stops_before_writing(self) -> None:
        target = self.legacy_repo()
        edited = target / LEGACY_ENTRIES[0]
        edited.write_text(edited.read_text(encoding="utf-8") + "\n我们自己补的一句。\n", encoding="utf-8")
        self.commit(target, "人改了旧入口")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn(LEGACY_ENTRIES[0], self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")

    def test_conflicting_adaptation_values_stop_before_writing(self) -> None:
        target = self.legacy_repo()
        (target / "doc" / "extensions" / "adaptation.yaml").write_text('adapted_for: "1.9.3"\n', encoding="utf-8")
        self.commit(target, "两处写了不同的已适配版本")
        before = self.snapshot(target)
        proc = self.adapt("--apply", target)
        self.assertEqual(2, proc.returncode, self.out(proc))
        self.assertIn("adapted_for", self.out(proc))
        self.assertEqual(before, self.snapshot(target), "停之前已经写过盘了")


if __name__ == "__main__":
    unittest.main()
