"""S10 + S11 端到端验证：外网 base 发行包、内网两轮导入、正式 Framework 加载、init 钩子到桥、就地适配（根与子工程）与清样例。"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import publish_to_demo as pub  # noqa: E402
from ext_workspace import DEV_SOURCE, ensure_framework, git_init_excluding_framework, link_framework  # noqa: E402

DEMO = REPO_ROOT / "demo"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)


def init_commit(repo_root: Path, *exclude_patterns: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), "init", "-q"], check=True, capture_output=True)
    exclude = repo_root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    lines = ["/framework/", *exclude_patterns]
    exclude.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_git(repo_root, "add", "-A")
    run_git(repo_root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")


def make_consumer(project_dir: Path, project_name: str, adapters: list[str] | None = None) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
    cfg["project_name"] = project_name
    if adapters is not None:
        cfg["materialized_adapters"] = adapters
    (project_dir / "framework.config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    link_framework(project_dir)
    (project_dir / ".gitignore").write_text("doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")


def write_sample_knowledge_and_review(project_dir: Path, scan: Path) -> Path:
    ext = project_dir / "doc" / "extensions"
    kf = ext / "knowledge" / "facts" / "component-profile.md"
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_text(
        "---\n"
        "name: component-profile\n"
        "kind: facts\n"
        "form: facets\n"
        "applies_when: 需要确认本业务工程的部件边界与对外交互方时。\n"
        "---\n\n"
        "## 部件定位\n\n"
        "- 本工程承载支付接入能力（依据：framework.config.json）。\n",
        encoding="utf-8",
    )
    mf = ext / "manifest.yaml"
    mf_text = mf.read_text(encoding="utf-8")
    if "knowledge/facts/component-profile.md" not in mf_text:
        mf_text = mf_text.replace(
            "  hooks:\n",
            "    - knowledge/facts/component-profile.md\n  hooks:\n",
            1,
        )
        mf.write_text(mf_text, encoding="utf-8")
    # 新增知识登记进根 manifest 后同步宿主入口文件（AGENTS.md / CLAUDE.md）
    entries = ext / "base" / "skills" / "story-adaptation" / "scripts" / "entries.mjs"
    subprocess.run(["node", str(entries), "--project-root", str(project_dir), "--action", "materialize"],
                   capture_output=True, text=True, encoding="utf-8", check=True)
    status = subprocess.run(["node", str(scan), "--status"], cwd=str(project_dir),
                            capture_output=True, text=True, encoding="utf-8", check=True)
    digest = json.loads(status.stdout)["knowledge"]["digest"]
    rev = ext / ".adapt" / "knowledge-review.md"
    rev.parent.mkdir(parents=True, exist_ok=True)
    rev.write_text(
        "# 知识独审\n\n```yaml\nknowledge_review:\n"
        f'  digest: "{digest}"\n'
        "  executor: independent-reviewer-1\n"
        "  files:\n"
        "    - path: knowledge/facts/component-profile.md\n"
        "      granularity: {verdict: PASS, evidence: 单面单责}\n"
        "      fact_use: {verdict: PASS, evidence: 指向 framework.config.json}\n"
        "      duplication: {verdict: PASS, evidence: 无重复}\n"
        "      coding_boundary: {verdict: PASS, evidence: 无编码规范}\n"
        "  blocking: []\n"
        "  unreviewed: []\n"
        "```\n",
        encoding="utf-8",
    )
    return kf


class S10DistributionAndFrameworkContractTests(unittest.TestCase):
    """S10：外网 base 包物料清单、内网两轮导入保 adapters、正式 Framework 加载完整根 manifest 与六阶段入口。"""

    def setUp(self) -> None:
        if shutil.which("node") is None or shutil.which("git") is None:
            self.skipTest("需要 node 与 git")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_external_base_package_excludes_demo_knowledge_and_standin_adapters(self) -> None:
        packed_root = self.root / "external-release"
        files = pub.pack_external_base(DEV_SOURCE, packed_root)
        self.assertNotIn(".gitignore", files, "已退出的 base/.gitignore 漏进外网包")
        self.assertIn("package-manifest.yaml", files)
        self.assertFalse(any(f == "examples" or f.startswith("examples/") for f in files), "已退出的 examples/ 漏进外网包")
        self.assertFalse(any(f.startswith("knowledge/") for f in files), "demo 知识漏进外网 base 顶层")
        self.assertFalse(any("adapters/" in f for f in files), "替身 adapters 漏进外网 base 包")
        self.assertFalse((DEV_SOURCE / "manifest.yaml").exists(), "旧顶层 extensions/manifest.yaml 应已退出")
        self.assertFalse((DEV_SOURCE / "knowledge").exists(), "旧顶层 extensions/knowledge 应已迁至 test/fixtures")
        self.assertFalse((DEV_SOURCE / "hooks").exists(), "旧顶层 extensions/hooks 应已退出")

    def test_two_round_intranet_import_preserves_adapters_and_business_install_uses_same_release(self) -> None:
        intranet = self.root / "intranet-release"
        adapters = intranet / "adapters"
        adapters.mkdir(parents=True)
        (adapters / "story.js").write_text("// intranet story adapter v1\nmodule.exports = { ok: true };\n", encoding="utf-8")
        (adapters / "token.js").write_text("// intranet token adapter v1\nconsole.log('tok');\n", encoding="utf-8")
        before_sha = {name: sha256_file(adapters / name) for name in ("story.js", "token.js")}

        # 两轮外网 base 覆盖导入
        for round_no in (1, 2):
            pub.pack_external_base(DEV_SOURCE, intranet)
            after_sha = {name: sha256_file(adapters / name) for name in ("story.js", "token.js")}
            self.assertEqual(before_sha, after_sha, f"第 {round_no} 轮内网导入改写了 adapters")

        # 业务工程从同一内网发行取 base + adapters
        biz = self.root / "biz-app"
        make_consumer(biz, "BizApp", ["codex", "claude"])
        init_commit(biz)
        shutil.copytree(intranet / "base", biz / "doc/extensions/base")
        shutil.copytree(intranet / "adapters", biz / "doc/extensions/adapters")
        scan = biz / "doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs"
        proc = subprocess.run(["node", str(scan), "--apply"], cwd=str(biz),
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        for name in ("story.js", "token.js"):
            self.assertEqual(before_sha[name], sha256_file(biz / "doc/extensions/adapters" / name))

    def test_formal_framework_loads_full_root_manifest_and_delivers_feature_stage_tasks(self) -> None:
        consumer = self.root / "formal-consumer"
        make_consumer(consumer, "FormalApp", ["codex"])
        res = pub.install_extension(DEV_SOURCE, consumer)
        self.assertEqual("installed", res.status, res.problems)

        probe = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
const { loadInstanceExtensions } = req('./extension-loader.ts');
const { formatExtensionPhasePrompt } = req('./scripts/utils/extension-runtime.ts');
const bundle = loadInstanceExtensions(root, 'doc/extensions', { frameworkRoot: fw });
const prompts = Object.fromEntries(['spec', 'plan', 'coding', 'review', 'ut', 'testing'].map(
  ph => [ph, formatExtensionPhasePrompt(bundle, ph, root)]
));
process.stdout.write(JSON.stringify({
  errors: bundle.errors,
  hooks: Object.keys(bundle.hooks).sort(),
  overlays: Object.keys(bundle.phaseRuleOverlayPaths).sort(),
  skillAssets: bundle.skillAssetAbsPaths,
  bindings: Object.keys(bundle.phaseBindings).sort(),
  prompts,
}));
"""
        proc = subprocess.run(["node", "-e", probe, str(consumer)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual([], data["errors"], f"正式 Framework 拒绝了完整根 manifest：{data['errors']}")
        self.assertEqual(["coding", "docs", "plan", "review", "spec", "testing", "ut"], data["hooks"])
        self.assertEqual(["coding", "plan", "review", "spec", "testing", "ut"], data["overlays"])
        self.assertIn("component-design", data["skillAssets"])
        for phase in ("spec", "plan", "coding", "review", "ut", "testing"):
            self.assertIn("base/skills/story-knowledge/SKILL.md", data["prompts"][phase], f"{phase} 未收到前置知识入口")


class S11InPlaceAdaptAndInitHookTests(unittest.TestCase):
    """S11：正式 init 钩子到桥、根仓与 repo/apps/pay 子工程就地首装/旧混装升级、脏文件拦截、清理样例与重入。"""

    def setUp(self) -> None:
        if shutil.which("node") is None or shutil.which("git") is None:
            self.skipTest("需要 node 与 git")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _run_formal_init(self, project_dir: Path, mode: str) -> subprocess.CompletedProcess:
        harness = project_dir / "framework" / "harness"
        return subprocess.run(
            ["npx", "ts-node", "scripts/init-orchestrate.ts", "--scope", "project",
             "--project-root", str(project_dir), "--mode", mode],
            cwd=str(harness), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )

    def test_formal_init_hook_emits_base_bridges_and_preserves_other_owners(self) -> None:
        proj = self.root / "init-hook-proj"
        make_consumer(proj, "InitProj", ["codex"])
        pub.pack_external_base(DEV_SOURCE, proj / "doc" / "extensions")
        # 最小根 manifest 仅登记 docs.post_check（模拟首装前人工原位合并）
        (proj / "doc/extensions/manifest.yaml").write_text(
            'schema_version: "1.1"\nname: init-proj\nprovides:\n  hooks:\n    docs:\n      post_check:\n'
            '        - base/skills/story-adaptation/scripts/entries.mjs\n',
            encoding="utf-8",
        )
        # 放置一个其他所有者的合法受管桥，验证 init 钩子与 entries 物化均不误删
        other_src = proj / "doc/extensions/other-ext/skills/helper/SKILL.md"
        other_src.parent.mkdir(parents=True)
        other_src.write_text("---\nname: helper\ndescription: other owner\n---\n\n# helper\n", encoding="utf-8")
        other_bridge_probe = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
req('./scripts/utils/instance-skill-bridge.ts').emitInstanceSkillBridge({
  repoRoot: root, frameworkDir: fw, agentAdapter: 'codex',
  extensionDirRel: 'doc/extensions/other-ext', declaredSkillIds: ['helper'],
});
"""
        subprocess.run(["node", "-e", other_bridge_probe, str(proj)], check=True, capture_output=True)
        other_bridge = proj / ".codex/skills/helper/SKILL.md"
        self.assertTrue(other_bridge.is_file())
        other_bytes = other_bridge.read_bytes()

        # 直接按 S09 合同触发 entries.mjs 的 docs.post_check 钩子（含非 init 守卫验证）
        hook_probe = """
const [entriesUrl, root, isInit] = process.argv.slice(1);
if (isInit === '1') process.env.HARNESS_INIT_INTERNAL_GLOBAL_RUN = '1';
const mod = await import(entriesUrl);
const res = mod.default({ feature: '_global', phase: 'docs', projectRoot: root });
process.stdout.write(JSON.stringify(res));
"""
        entries_url = (proj / "doc/extensions/base/skills/story-adaptation/scripts/entries.mjs").resolve().as_uri()
        # 普通 docs 检查零写入
        p_normal = subprocess.run(["node", "--input-type=module", "-e", hook_probe, entries_url, str(proj), "0"],
                                  capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertTrue(json.loads(p_normal.stdout)["ok"])
        self.assertFalse((proj / ".codex/skills/story/SKILL.md").exists(), "非 init docs 检查不应写宿主桥")

        # init 内的 docs.post_check 写入全部 base 桥并保留其他所有者
        p_init = subprocess.run(["node", "--input-type=module", "-e", hook_probe, entries_url, str(proj), "1"],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertTrue(json.loads(p_init.stdout)["ok"], p_init.stdout)
        story_bridge = proj / ".codex/skills/story/SKILL.md"
        self.assertTrue(story_bridge.is_file())
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", story_bridge.read_text(encoding="utf-8"))
        self.assertTrue(other_bridge.is_file(), "其他所有者的有效入口被误删")
        self.assertEqual(other_bytes, other_bridge.read_bytes())

    def test_subproject_fresh_install_dirty_isolation_cleanup_and_reentry(self) -> None:
        """仓内子工程 repo/apps/pay：兄弟工程 repo/apps/other 脏文件不挡，本工程写入面脏文件必挡，清样例留 .gitignore 且最后写 adapted_for。"""
        mono = self.root / "monorepo"
        pay = mono / "apps" / "pay"
        other = mono / "apps" / "other"
        make_consumer(pay, "PayApp", ["codex", "claude"])
        other.mkdir(parents=True)
        (other / "README.md").write_text("other app\n", encoding="utf-8")
        # 预物化空工程入口
        entries_src = DEV_SOURCE / "base/skills/story-adaptation/scripts/entries.mjs"
        subprocess.run(["node", str(entries_src), "--project-root", str(pay), "--action", "materialize"],
                       check=True, capture_output=True)
        init_commit(mono, "/apps/pay/framework/")

        # 解包外网 base/ 到 apps/pay/doc/extensions/base/
        pub.pack_external_base(DEV_SOURCE, pay / "doc" / "extensions")
        scan = pay / "doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs"

        # 兄弟子工程有脏文件（已跟踪修改 + 未跟踪）→ 不挡 apps/pay
        (other / "README.md").write_text("sibling dirty\n", encoding="utf-8")
        (other / "untracked.txt").write_text("sibling untracked\n", encoding="utf-8")

        # 本工程写入面 AGENTS.md 有未提交修改 → 必须在写入前阻止（零字节改动）
        agents_before = (pay / "AGENTS.md").read_bytes()
        (pay / "AGENTS.md").write_text(agents_before.decode("utf-8") + "\n", encoding="utf-8")
        blocked = subprocess.run(["node", str(scan), "--apply"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, blocked.returncode, "写入面脏文件未阻止")
        self.assertFalse((pay / "doc/extensions/manifest.yaml").exists(), "脏文件被拦时却写了 manifest.yaml")

        # 恢复本工程 AGENTS.md，保留兄弟工程脏文件 → 就地 --apply 成功
        (pay / "AGENTS.md").write_bytes(agents_before)
        applied = subprocess.run(["node", str(scan), "--apply"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, applied.returncode, applied.stdout + applied.stderr)
        self.assertTrue((pay / "doc/extensions/manifest.yaml").is_file())
        self.assertFalse((pay / "doc/extensions/base/examples").exists(), "无样例包不应含 base/examples")
        self.assertIn("机制已安装", applied.stdout)
        self.assertIn("知识待写", applied.stdout)
        self.assertIn("首次安装作者", applied.stdout)
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", (pay / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))

        # 写目标知识与独立审查报告 → 缺真实对接时 --check 与 --mark-adapted 均拦住并保住样例与游标
        write_sample_knowledge_and_review(pay, scan)
        chk_missing = subprocess.run(["node", str(scan), "--check"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, chk_missing.returncode, chk_missing.stdout + chk_missing.stderr)
        self.assertIn("story.js", chk_missing.stdout + chk_missing.stderr)
        mark_missing = subprocess.run(["node", str(scan), "--mark-adapted"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, mark_missing.returncode, mark_missing.stdout + mark_missing.stderr)
        self.assertFalse((pay / "doc/extensions/base/examples").exists())
        # 补齐真实业务对接实现 → 跑 --check 与 --mark-adapted（清样例、保留 .gitignore、最后写 adapted_for）
        ad_dir = pay / "doc/extensions/adapters"
        ad_dir.mkdir(parents=True, exist_ok=True)
        (ad_dir / "story.js").write_text("// pay story adapter\nmodule.exports = {};\n", encoding="utf-8")
        (ad_dir / "token.js").write_text("// pay token adapter\nconsole.log('tok');\n", encoding="utf-8")
        chk = subprocess.run(["node", str(scan), "--check"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, chk.returncode, chk.stdout + chk.stderr)
        self.assertIn("知识可读（1 份）", chk.stdout)

        # 未清理前 adapted_for 尚未写入
        adapt_before = yaml.safe_load((pay / "doc/extensions/adaptation.yaml").read_text(encoding="utf-8")) or {}
        self.assertNotIn("adapted_for", adapt_before)

        marked = subprocess.run(["node", str(scan), "--mark-adapted"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, marked.returncode, marked.stdout + marked.stderr)
        self.assertFalse((pay / "doc/extensions/base/examples").exists(), "无样例包不应出现 base/examples/")
        self.assertFalse((pay / "doc/extensions/base/.gitignore").exists(), "无样例包不应出现 base/.gitignore")
        adapt_after = yaml.safe_load((pay / "doc/extensions/adaptation.yaml").read_text(encoding="utf-8"))
        self.assertEqual("2.0.6", adapt_after["adapted_for"])

        # 清理后知识仍可从实际知识任务入口读回
        kt = pay / "doc/extensions/base/hooks/shared/knowledge-task.mjs"
        (pay / "doc/features/FEAT-1").mkdir(parents=True)
        readback = subprocess.run(["node", str(kt), "--project-root", str(pay), "--feature", "FEAT-1",
                                   "--action", "spec", "--audience", "author"],
                                  capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, readback.returncode, readback.stderr)
        self.assertIn("component-profile", readback.stdout)

        # 模拟清理后但 adapted_for 未落盘的中断重入：清掉 adapted_for 重跑 --mark-adapted，应幂等成功
        (pay / "doc/extensions/adaptation.yaml").write_text("{}\n", encoding="utf-8")
        reentry = subprocess.run(["node", str(scan), "--mark-adapted"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, reentry.returncode, reentry.stdout + reentry.stderr)
        self.assertEqual("2.0.6", yaml.safe_load((pay / "doc/extensions/adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])

        # 同版重入 --apply 仍核入口、知识可读与对接状态
        run_git(mono, "add", "-A")
        run_git(mono, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "adapted")
        same_ver = subprocess.run(["node", str(scan), "--apply"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, same_ver.returncode, same_ver.stdout + same_ver.stderr)
        self.assertIn("已重新核对宿主入口、知识可读与对接状态", same_ver.stdout)

    def test_legacy_mixed_layout_upgrade_preserves_knowledge_and_business_adapters_and_blocks_untracked_overwrite(self) -> None:
        """旧混装首升：先拦未跟踪待删文件；干净后保留业务知识与真实 adapters（迁至 <ext>/adapters/），退出旧目录并原位更新根 manifest。"""
        proj = self.root / "legacy-proj"
        make_consumer(proj, "LegacyBiz", ["codex", "claude"])
        ext = proj / "doc" / "extensions"
        # 造旧混装布局（无 base/，真实未改旧 hooks/skills/rules + 业务 knowledge + 业务 adapters + 旧 manifest）
        (ext / "hooks/spec").mkdir(parents=True)
        shutil.copy2(DEV_SOURCE / "base/hooks/spec/post_check.mjs", ext / "hooks/spec/post_check.mjs")
        (ext / "rules").mkdir(parents=True)
        shutil.copy2(DEV_SOURCE / "base/rules/spec-rules.overlay.yaml", ext / "rules/spec-rules.overlay.yaml")
        old_adapters = ext / "skills/story/scripts/adapters"
        old_adapters.mkdir(parents=True)
        biz_story = "// LegacyBiz real story adapter\nmodule.exports = { real: true };\n"
        biz_token = "// LegacyBiz real token adapter\nconsole.log('real-token');\n"
        (old_adapters / "story.js").write_text(biz_story, encoding="utf-8")
        (old_adapters / "token.js").write_text(biz_token, encoding="utf-8")
        (ext / "skills/story").mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEV_SOURCE / "base/skills/story/SKILL.md", ext / "skills/story/SKILL.md")
        kf = ext / "knowledge/facts/biz-profile.md"
        kf.parent.mkdir(parents=True)
        kf_text = "---\nname: biz-profile\nkind: facts\nform: facets\napplies_when: 核本业务边界时。\n---\n\n## 定位\n\n- 业务事实。\n"
        kf.write_text(kf_text, encoding="utf-8")
        (ext / "manifest.yaml").write_text(
            'schema_version: "1.1"\nname: legacy-biz\nversion: "2.0.5"\ndescription: 旧业务扩展\n'
            'provides:\n  skills:\n    - story\n  knowledge:\n    - knowledge/facts/biz-profile.md\n',
            encoding="utf-8",
        )
        (ext / "adaptation.yaml").write_text('adapted_for: "2.0.5"\n', encoding="utf-8")
        (proj / "doc/usage.json").write_text('{"schema": 1, "requirements": {}}\n', encoding="utf-8")
        # 渲染旧布局宿主入口
        entries_src = DEV_SOURCE / "base/skills/story-adaptation/scripts/entries.mjs"
        subprocess.run(["node", str(entries_src), "--project-root", str(proj), "--action", "materialize"],
                       check=True, capture_output=True)
        init_commit(proj)

        # 解包新版 base/
        pub.pack_external_base(DEV_SOURCE, ext)
        scan = ext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"

        # 在将被退出的旧 hooks/ 下放一个未跟踪文件 → 必须在删除前阻止
        stray = ext / "hooks/spec/untracked-draft.mjs"
        stray.write_text("// unsaved local work\n", encoding="utf-8")
        blocked = subprocess.run(["node", str(scan), "--apply"], cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, blocked.returncode, "旧机制目录下的未跟踪文件未被写入前检查拦住")
        self.assertTrue(stray.is_file(), "被拦住时却删掉了未跟踪文件")
        stray.unlink()

        # 清理未跟踪文件后运行就地升级
        upgraded = subprocess.run(["node", str(scan), "--apply"], cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, upgraded.returncode, upgraded.stdout + upgraded.stderr)
        # 旧机制目录退出
        for old_dir in ("hooks", "rules", "skills"):
            self.assertFalse((ext / old_dir).exists(), f"旧机制目录 {old_dir}/ 未退出")
        # 业务知识、业务 adapters（已迁至 <ext>/adapters/）和身份原样保留
        self.assertEqual(kf_text, kf.read_text(encoding="utf-8"))
        self.assertEqual(biz_story, (ext / "adapters/story.js").read_text(encoding="utf-8"))
        self.assertEqual(biz_token, (ext / "adapters/token.js").read_text(encoding="utf-8"))
        mf = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual("legacy-biz", mf["name"])
        self.assertEqual("2.0.6", mf["version"])
        self.assertIn("knowledge/facts/biz-profile.md", mf["provides"]["knowledge"])
        self.assertIn("base/skills/story-adaptation/scripts/entries.mjs", mf["provides"]["hooks"]["docs"]["post_check"])
        self.assertNotIn("skills", mf["provides"])
        # 宿主桥已指向 base/skills/
        self.assertIn("doc/extensions/base/skills/story/SKILL.md",
                      (proj / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))
        # 2.0.5 -> 2.0.6 无新演进条目且知识可读：样例已清理、.gitignore 保留、adapted_for 升至 2.0.6
        self.assertFalse((ext / "base/examples").exists())
        self.assertFalse((ext / "base/.gitignore").exists())
        self.assertEqual("2.0.6", yaml.safe_load((ext / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])

    def test_retired_package_flag_is_refused(self) -> None:
        proj = self.root / "refuse-pkg"
        make_consumer(proj, "RefusePkg", ["codex"])
        pub.pack_external_base(DEV_SOURCE, proj / "doc" / "extensions")
        scan = proj / "doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs"
        proc = subprocess.run(["node", str(scan), "--check", "--package", str(proj)],
                              cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, proc.returncode)
        self.assertIn("已退出跨工程 --package", proc.stderr)

    def test_live_framework_init_orchestrator_triggers_docs_post_check_and_bridges(self) -> None:
        """真实 `framework-init` 编排器（init-orchestrate.ts --execute --smart-auto --scope project）在首装与 UPDATE 中触发 docs.post_check 并生成指向 base/skills/ 的桥接。"""
        import os  # noqa: PLC0415
        import design_fixture  # noqa: PLC0415
        proj = self.root / "live-init-app"
        proj.mkdir(parents=True, exist_ok=True)
        # 真实复制 framework（仅 node_modules 共享链接），让 harness-runner 的 realpath 落在目标工程内
        fw_src = design_fixture.framework_under_test()
        shutil.copytree(fw_src, proj / "framework", ignore=shutil.ignore_patterns("node_modules", "reports"))
        nm_src = fw_src / "harness" / "node_modules"
        nm_dst = proj / "framework" / "harness" / "node_modules"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(nm_dst), str(nm_src)], check=True, capture_output=True)
        else:
            nm_dst.symlink_to(nm_src, target_is_directory=True)
        cfg = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
        cfg["project_name"] = "LiveInitApp"
        cfg["materialized_adapters"] = ["claude", "codex", "generic"]
        (proj / "framework.config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for doc_rel in ("doc/architecture.md", "doc/module-catalog.yaml", "doc/glossary.yaml"):
            src_doc = DEMO / doc_rel
            if src_doc.is_file():
                dst_doc = proj / doc_rel
                dst_doc.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_doc, dst_doc)
        (proj / "doc" / "glossary-seed.txt").write_text("# seed\n", encoding="utf-8")
        ext = proj / "doc" / "extensions"
        pub.pack_external_base(DEV_SOURCE, ext)
        pkg_text = (ext / "base/package-manifest.yaml").read_text(encoding="utf-8")
        (ext / "manifest.yaml").write_text(
            pub.compose_root_manifest(pkg_text, name="live-init-app", description="LiveInit", knowledge_items=[]),
            encoding="utf-8",
        )
        # 放一个其它 owner 桥接，验证真实 framework-init 不误清
        other = proj / ".codex/skills/external-tool/SKILL.md"
        other.parent.mkdir(parents=True, exist_ok=True)
        other_body = '<!-- agent-maison:instance-extension-bridge {"schemaVersion":1,"bridgeId":"external-tool","ownerExtension":"other-ext"} -->\n# Other\n'
        other.write_text(other_body, encoding="utf-8")

        harness = proj / "framework" / "harness"
        ts_node = harness / "node_modules" / "ts-node" / "dist" / "bin.js"
        clean_env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        cmd = [
            "node", str(ts_node), "--transpile-only",
            str(harness / "scripts" / "init-orchestrate.ts"),
            "--execute", "--smart-auto", "--scope", "project",
            "--project-root", str(proj),
            "--materialized-adapters", "claude,codex,generic",
        ]
        # 首次 project init
        r1 = subprocess.run(cmd, cwd=str(harness), env=clean_env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, r1.returncode, r1.stdout + r1.stderr)
        for rel, target in (
            (".claude/commands/story.md", "doc/extensions/base/skills/story/SKILL.md"),
            (".codex/skills/story/SKILL.md", "doc/extensions/base/skills/story/SKILL.md"),
            (".codex/skills/story-adaptation/SKILL.md", "doc/extensions/base/skills/story-adaptation/SKILL.md"),
            (".agents/skills/story/SKILL.md", "doc/extensions/base/skills/story/SKILL.md"),
        ):
            self.assertTrue((proj / rel).is_file(), f"真实 framework-init 未生成桥接：{rel}")
            self.assertIn(target, (proj / rel).read_text(encoding="utf-8"), rel)
        self.assertEqual(other_body, other.read_text(encoding="utf-8"), "真实 framework-init 误清了其它 owner 的桥接")
        # 二次 UPDATE 幂等
        r2 = subprocess.run(cmd, cwd=str(harness), env=clean_env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
        self.assertEqual(other_body, other.read_text(encoding="utf-8"))
        self.assertIn("doc/extensions/base/skills/story/SKILL.md",
                      (proj / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))

    def _copy_real_framework(self, proj: Path) -> Path:
        import design_fixture  # noqa: PLC0415
        fw_src = design_fixture.framework_under_test()
        shutil.copytree(fw_src, proj / "framework", ignore=shutil.ignore_patterns("node_modules", "reports"))
        nm_src = fw_src / "harness" / "node_modules"
        nm_dst = proj / "framework" / "harness" / "node_modules"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(nm_dst), str(nm_src)], check=True, capture_output=True)
        else:
            nm_dst.symlink_to(nm_src, target_is_directory=True)
        for doc_rel in ("doc/architecture.md", "doc/module-catalog.yaml", "doc/glossary.yaml"):
            src_doc = DEMO / doc_rel
            if src_doc.is_file():
                dst_doc = proj / doc_rel
                dst_doc.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_doc, dst_doc)
        (proj / "doc" / "glossary-seed.txt").write_text("# seed\n", encoding="utf-8")
        return proj / "framework" / "harness"

    def _run_live_init(self, proj: Path, adapters_csv: str) -> subprocess.CompletedProcess:
        harness = proj / "framework" / "harness"
        ts_node = harness / "node_modules" / "ts-node" / "dist" / "bin.js"
        clean_env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        cmd = [
            "node", str(ts_node), "--transpile-only",
            str(harness / "scripts" / "init-orchestrate.ts"),
            "--execute", "--smart-auto", "--scope", "project",
            "--project-root", str(proj),
            "--materialized-adapters", adapters_csv,
        ]
        return subprocess.run(cmd, cwd=str(harness), env=clean_env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def test_s33_pack_rejects_reintroduced_examples_or_base_gitignore(self) -> None:
        """S33：外网无样例包若重新混入 base/examples/ 或 base/.gitignore，打包必须拒绝且不输出。"""
        with_ex = self.root / "with-ex-src" / "base"
        shutil.copytree(DEV_SOURCE / "base", with_ex)
        (with_ex / "examples" / "knowledge").mkdir(parents=True)
        (with_ex / "examples" / "knowledge" / "a.md").write_text("# stale\n", encoding="utf-8")
        with self.assertRaises(pub.InputError) as cm:
            pub.pack_external_base(with_ex.parent, self.root / "out-ex")
        self.assertIn("examples/", str(cm.exception))
        self.assertFalse((self.root / "out-ex" / "base").exists())

        with_gi = self.root / "with-gi-src" / "base"
        shutil.copytree(DEV_SOURCE / "base", with_gi)
        (with_gi / ".gitignore").write_text("/examples/\n", encoding="utf-8")
        with self.assertRaises(pub.InputError) as cm2:
            pub.pack_external_base(with_gi.parent, self.root / "out-gi")
        self.assertIn(".gitignore", str(cm2.exception))
        self.assertFalse((self.root / "out-gi" / "base").exists())

    def test_s27_s28_legacy_205_first_init_update_preserves_biz_hook_partial_adapters_and_reaches_adapt(self) -> None:
        """S27 R4 + S28 R5/R6b：真实 2.0.5 旧仓（旧桥 + 业务自定义 hook + 新根已有 story.js、旧根独有 token.js）经导入预置后，
        第一次真实 framework-init UPDATE 即刷新旧桥与新增宿主桥，再经生成桥运行 adapt 迁入 token.js 并保留业务 hook 与知识。"""
        proj = self.root / "legacy-205-live"
        proj.mkdir(parents=True)
        self._copy_real_framework(proj)
        cfg = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
        cfg["project_name"] = "Legacy205App"
        cfg["materialized_adapters"] = ["codex", "claude"]
        (proj / "framework.config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (proj / ".gitignore").write_text("doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")

        ext = proj / "doc" / "extensions"
        (ext / "hooks/spec").mkdir(parents=True)
        shutil.copy2(DEV_SOURCE / "base/hooks/spec/post_check.mjs", ext / "hooks/spec/post_check.mjs")
        (ext / "rules").mkdir(parents=True)
        shutil.copy2(DEV_SOURCE / "base/rules/spec-rules.overlay.yaml", ext / "rules/spec-rules.overlay.yaml")
        for sid in ("story", "story-adaptation", "story-stats"):
            (ext / f"skills/{sid}").mkdir(parents=True)
            shutil.copy2(DEV_SOURCE / f"base/skills/{sid}/SKILL.md", ext / f"skills/{sid}/SKILL.md")
        (ext / "skills/story-knowledge").mkdir(parents=True)
        sk_205 = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", "552f8c90:extensions/skills/story-knowledge/SKILL.md"],
            check=True, capture_output=True,
        ).stdout
        (ext / "skills/story-knowledge/SKILL.md").write_bytes(sk_205)
        old_ad = ext / "skills/story/scripts/adapters"
        old_ad.mkdir(parents=True)
        biz_story = "// new root real story.js\nmodule.exports = { v: 2 };\n"
        biz_token = "// legacy unique real token.js\nconsole.log('legacy-token');\n"
        (old_ad / "token.js").write_text(biz_token, encoding="utf-8")
        (ext / "adapters").mkdir(parents=True)
        (ext / "adapters/story.js").write_text(biz_story, encoding="utf-8")
        (ext / "business").mkdir(parents=True)
        (ext / "business/observe.mjs").write_text("export default () => ({ ok: true, message: 'biz-hook-ran' });\n", encoding="utf-8")
        kf = ext / "knowledge/facts/biz-profile.md"
        kf.parent.mkdir(parents=True)
        kf_text = "---\nname: biz-profile\nkind: facts\nform: facets\napplies_when: 核对业务边界时。\n---\n\n## 定位\n\n- 2.0.5 业务事实。\n"
        kf.write_text(kf_text, encoding="utf-8")
        (ext / "manifest.yaml").write_text(
            'schema_version: "1.1"\nname: legacy-205-app\nversion: "2.0.5"\ndescription: 2.0.5 业务扩展\n'
            'provides:\n  skills:\n    - story\n    - story-adaptation\n    - story-knowledge\n    - story-stats\n'
            '  knowledge:\n    - knowledge/facts/biz-profile.md\n'
            '  hooks:\n    spec:\n      post_check:\n        - hooks/spec/post_check.mjs\n        - business/observe.mjs\n',
            encoding="utf-8",
        )
        (ext / "adaptation.yaml").write_text('adapted_for: "2.0.5"\n', encoding="utf-8")
        (proj / "doc/usage.json").write_text('{"schema": 1, "requirements": {}}\n', encoding="utf-8")

        old_bridge_script = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
req('./scripts/utils/instance-skill-bridge.ts').emitInstanceSkillBridge({
  repoRoot: root, frameworkDir: fw, agentAdapter: 'codex',
  extensionDirRel: 'doc/extensions', declaredSkillIds: ['story', 'story-adaptation', 'story-knowledge', 'story-stats'],
});
"""
        subprocess.run(["node", "-e", old_bridge_script, str(proj)], check=True, capture_output=True)
        self.assertIn("doc/extensions/skills/story/SKILL.md", (proj / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))
        init_commit(proj)

        imp = pub.import_external_base(DEV_SOURCE, proj, prepare_init=True)
        self.assertTrue(imp["prepared"], imp["stdout"] + imp["stderr"])
        mf_pre = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("base/skills/story-adaptation/scripts/entries.mjs", mf_pre["provides"]["hooks"]["docs"]["post_check"])
        self.assertIn("business/observe.mjs", mf_pre["provides"]["hooks"]["spec"]["post_check"])
        self.assertNotIn("hooks/spec/post_check.mjs", mf_pre["provides"]["hooks"]["spec"]["post_check"])
        self.assertIn("knowledge/facts/biz-profile.md", mf_pre["provides"]["knowledge"])

        r_init = self._run_live_init(proj, "codex,claude")
        self.assertEqual(0, r_init.returncode, r_init.stdout + r_init.stderr)
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", (proj / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("doc/extensions/base/skills/story-adaptation/SKILL.md", (proj / ".claude/commands/story-adaptation.md").read_text(encoding="utf-8"))

        scan = ext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        applied = subprocess.run(["node", str(scan), "--apply"], cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, applied.returncode, applied.stdout + applied.stderr)
        self.assertEqual(biz_story, (ext / "adapters/story.js").read_text(encoding="utf-8"))
        self.assertEqual(biz_token, (ext / "adapters/token.js").read_text(encoding="utf-8"))
        for old_dir in ("hooks", "rules", "skills"):
            self.assertFalse((ext / old_dir).exists(), f"{old_dir}/ 未退场")
        self.assertEqual(kf_text, kf.read_text(encoding="utf-8"))
        mf_post = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("business/observe.mjs", mf_post["provides"]["hooks"]["spec"]["post_check"])
        self.assertEqual("2.0.6", yaml.safe_load((ext / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])
        self.assertFalse((ext / "base/examples").exists())

        load_probe = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
const bundle = req('./extension-loader.ts').loadInstanceExtensions(root, 'doc/extensions', { frameworkRoot: fw });
process.stdout.write(JSON.stringify({ errors: bundle.errors, specPost: bundle.hooks?.spec?.post_check ?? [] }));
"""
        lp = subprocess.run(["node", "-e", load_probe, str(proj)], capture_output=True, text=True, encoding="utf-8", check=True)
        ld = json.loads(lp.stdout)
        self.assertEqual([], ld["errors"])
        self.assertTrue(any(p.replace("\\", "/").endswith("business/observe.mjs") for p in ld["specPost"]), ld["specPost"])

    def test_s28_same_name_foreign_bridge_adapter_conflict_and_examples_user_draft_protection(self) -> None:
        """S28 R5/R6a/R6c：同名他属桥保护不覆盖、同名不同字节 adapter 冲突写前停、base/examples/ 用户文件保护不误删。"""
        proj = self.root / "foreign-bridge-proj"
        make_consumer(proj, "ForeignBridgeApp", ["codex"])
        ext = proj / "doc" / "extensions"
        pub.pack_external_base(DEV_SOURCE, ext)
        other_root = proj / "doc/extensions/other-ext/skills"
        for sid in ("story", "helper"):
            (other_root / sid).mkdir(parents=True)
            (other_root / sid / "SKILL.md").write_text(f"---\nname: {sid}\ndescription: other\n---\n# {sid}\n", encoding="utf-8")
        emit_other = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
req('./scripts/utils/instance-skill-bridge.ts').emitInstanceSkillBridge({
  repoRoot: root, frameworkDir: fw, agentAdapter: 'codex',
  extensionDirRel: 'doc/extensions/other-ext', declaredSkillIds: ['story', 'helper'],
});
"""
        subprocess.run(["node", "-e", emit_other, str(proj)], check=True, capture_output=True)
        foreign_story = proj / ".codex/skills/story/SKILL.md"
        foreign_helper = proj / ".codex/skills/helper/SKILL.md"
        foreign_story_bytes = foreign_story.read_bytes()
        foreign_helper_bytes = foreign_helper.read_bytes()
        init_commit(proj)

        scan = ext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        p_prep = subprocess.run(["node", str(scan), "--prepare-init"], cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, p_prep.returncode, p_prep.stdout + p_prep.stderr)
        self.assertIn("doc/extensions/other-ext/skills/story/SKILL.md", p_prep.stdout + p_prep.stderr)
        self.assertEqual(foreign_story_bytes, foreign_story.read_bytes())

        p_apply = subprocess.run(["node", str(scan), "--apply"], cwd=str(proj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, p_apply.returncode, p_apply.stdout + p_apply.stderr)
        self.assertEqual(foreign_story_bytes, foreign_story.read_bytes())
        self.assertEqual(foreign_helper_bytes, foreign_helper.read_bytes())

        hook_probe = """
const [entriesUrl, root] = process.argv.slice(1);
process.env.HARNESS_INIT_INTERNAL_GLOBAL_RUN = '1';
const mod = await import(entriesUrl);
process.stdout.write(JSON.stringify(mod.default({ feature: '_global', phase: 'docs', projectRoot: root })));
"""
        entries_url = (ext / "base/skills/story-adaptation/scripts/entries.mjs").resolve().as_uri()
        p_hook = subprocess.run(["node", "--input-type=module", "-e", hook_probe, entries_url, str(proj)],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        hres = json.loads(p_hook.stdout)
        self.assertFalse(hres["ok"], hres)
        self.assertIn("other-ext", hres["message"])
        self.assertEqual(foreign_story_bytes, foreign_story.read_bytes())

        cproj = self.root / "adapter-conflict-proj"
        make_consumer(cproj, "ConflictApp", ["codex"])
        cext = cproj / "doc" / "extensions"
        (cext / "skills/story/scripts/adapters").mkdir(parents=True)
        (cext / "skills/story/scripts/adapters/story.js").write_text("// old version\n", encoding="utf-8")
        (cext / "adapters").mkdir(parents=True)
        (cext / "adapters/story.js").write_text("// new different version\n", encoding="utf-8")
        (cext / "manifest.yaml").write_text('schema_version: "1.1"\nname: conflict-app\nversion: "2.0.5"\nprovides:\n  knowledge: []\n', encoding="utf-8")
        (cext / "adaptation.yaml").write_text('adapted_for: "2.0.5"\n', encoding="utf-8")
        pub.pack_external_base(DEV_SOURCE, cext)
        init_commit(cproj)
        cscan = cext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        c_res = subprocess.run(["node", str(cscan), "--apply"], cwd=str(cproj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, c_res.returncode, c_res.stdout + c_res.stderr)
        self.assertIn("story.js", c_res.stdout + c_res.stderr)
        self.assertTrue((cext / "skills/story/scripts/adapters/story.js").is_file(), "冲突时误删了旧文件")
        self.assertEqual("2.0.5", yaml.safe_load((cext / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])

        # S33：合法目标自带的 <ext>/examples/ 与根 .gitignore 不受破坏；安装后作者/独审读面就位且不含已退样例指引
        eproj = self.root / "target-assets-protect-proj"
        make_consumer(eproj, "TargetAssetsApp", ["codex"])
        eext = eproj / "doc" / "extensions"
        (eext / "examples").mkdir(parents=True)
        (eext / "examples/biz-demo.md").write_text("# target own example\n", encoding="utf-8")
        (eproj / ".gitignore").write_text("# target custom rule\ncustom-build/\n", encoding="utf-8")
        pub.pack_external_base(DEV_SOURCE, eext)
        (eext / "adapters").mkdir(parents=True)
        (eext / "adapters/story.js").write_text("// real story\n", encoding="utf-8")
        (eext / "adapters/token.js").write_text("// real token\n", encoding="utf-8")
        init_commit(eproj)
        escan = eext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        ap_res = subprocess.run(["node", str(escan), "--apply"], cwd=str(eproj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, ap_res.returncode, ap_res.stdout + ap_res.stderr)
        self.assertIn("机制已安装", ap_res.stdout)
        self.assertIn("知识待写", ap_res.stdout)
        self.assertIn("首次安装作者", ap_res.stdout)
        # 验证已安装的 S33 作者/独审读面完整且无 demo 专名
        adapt_doc = (eext / "base/skills/story-adaptation/reference/knowledge-adaptation.md").read_text(encoding="utf-8")
        review_doc = (eext / "base/skills/story-adaptation/reference/knowledge-review.md").read_text(encoding="utf-8")
        topics_doc = (eext / "base/skills/story-adaptation/reference/knowledge-topics.md").read_text(encoding="utf-8")
        self.assertIn("先核实安装脚本给出的游标、已有知识和加载问题", adapt_doc)
        self.assertIn("从脚本给出的已适配版本继续", adapt_doc)
        self.assertIn("拿本次正常需求，先从目标仓给出你的业务判断和源位置", review_doc)
        self.assertIn("## 12. 流程编排", topics_doc)
        self.assertIn("## 13. 页面交互", topics_doc)
        for leak in ("WalletMain", "CommUI", "base/examples/knowledge", "10KB"):
            self.assertNotIn(leak, adapt_doc + review_doc + topics_doc)
        write_sample_knowledge_and_review(eproj, escan)
        m_ok = subprocess.run(["node", str(escan), "--mark-adapted"], cwd=str(eproj), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, m_ok.returncode, m_ok.stdout + m_ok.stderr)
        self.assertEqual("# target own example\n", (eext / "examples/biz-demo.md").read_text(encoding="utf-8"))
        self.assertIn("custom-build/", (eproj / ".gitignore").read_text(encoding="utf-8"))
        self.assertFalse((eext / "base/examples").exists())
        self.assertFalse((eext / "base/.gitignore").exists())
        self.assertEqual("2.0.6", yaml.safe_load((eext / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])

    def test_s29_import_preflight_real_205_bindings_inner_hooks_and_standin_file_gate(self) -> None:
        """S29 R1/R2/R3：导入写前保护（脏 base + 未跟踪稿 + 同名他属桥零写入）、真实 2.0.5 六阶段 skill:story-knowledge 绑定退出
        与 hooks/business-observe.mjs 登记及文件双保留、stand-in 缺件仍拦 --check/--mark-adapted/--apply 自动完成。"""
        # R1：目标已有 base/（含已改跟踪 Skill + 未跟踪稿）+ 同名他属桥 → import_external_base 零字节写入
        p1 = self.root / "s29-dirty-import"
        make_consumer(p1, "S29Dirty", ["codex"])
        e1 = p1 / "doc" / "extensions"
        pub.pack_external_base(DEV_SOURCE, e1)
        init_commit(p1)
        tracked_skill = e1 / "base/skills/story/SKILL.md"
        dirty_text = tracked_skill.read_text(encoding="utf-8") + "\n<!-- local unsaved edit -->\n"
        tracked_skill.write_text(dirty_text, encoding="utf-8")
        untracked_draft = e1 / "base/local-draft.md"
        untracked_draft.write_text("# unsaved draft\n", encoding="utf-8")
        r_dirty = pub.import_external_base(DEV_SOURCE, p1, prepare_init=True)
        self.assertFalse(r_dirty["prepared"])
        self.assertEqual(2, r_dirty["returncode"])
        self.assertEqual(dirty_text, tracked_skill.read_text(encoding="utf-8"), "导入失败却覆盖了已改的受跟踪 Skill")
        self.assertTrue(untracked_draft.is_file(), "导入失败却删除了未跟踪稿")

        # 恢复脏文件但放置同名他属桥 → import_external_base 仍零字节改写目标 base/ 与 manifest.yaml
        run_git(p1, "checkout", "--", "doc/extensions/base/skills/story/SKILL.md")
        untracked_draft.unlink()
        other_src = e1 / "other-ext/skills/story"
        other_src.mkdir(parents=True)
        (other_src / "SKILL.md").write_text("---\nname: story\ndescription: other\n---\n# other\n", encoding="utf-8")
        emit_other = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
req('./scripts/utils/instance-skill-bridge.ts').emitInstanceSkillBridge({
  repoRoot: root, frameworkDir: fw, agentAdapter: 'codex',
  extensionDirRel: 'doc/extensions/other-ext', declaredSkillIds: ['story'],
});
"""
        subprocess.run(["node", "-e", emit_other, str(p1)], check=True, capture_output=True)
        foreign_story = p1 / ".codex/skills/story/SKILL.md"
        foreign_bytes = foreign_story.read_bytes()
        init_commit(p1)
        r_col = pub.import_external_base(DEV_SOURCE, p1, prepare_init=True)
        self.assertFalse(r_col["prepared"])
        self.assertEqual(2, r_col["returncode"])
        self.assertEqual(foreign_bytes, foreign_story.read_bytes())
        self.assertFalse((e1 / "manifest.yaml").exists())

        # R2：真实 2.0.5 原清单（含六阶段 {kind: skill, ref: story-knowledge}）+ 合法 hooks/business-observe.mjs 登记与文件
        p2 = self.root / "s29-real-205"
        make_consumer(p2, "S29Real205", ["codex"])
        e2 = p2 / "doc" / "extensions"
        # 复制完整 2.0.5 旧机制骨架（从当前 base 映射到旧根 + 添加 hooks/business-observe.mjs）
        for sub in ("hooks", "rules", "skills"):
            shutil.copytree(DEV_SOURCE / "base" / sub, e2 / sub)
        biz_hook_body = "export default () => ({ ok: true, message: 'inner-biz-hook-ok' });\n"
        (e2 / "hooks/business-observe.mjs").write_text(biz_hook_body, encoding="utf-8")
        kf = e2 / "knowledge/facts/biz-profile.md"
        kf.parent.mkdir(parents=True)
        kf.write_text("---\nname: biz-profile\nkind: facts\nform: facets\napplies_when: 核业务边界时。\n---\n\n## 定位\n\n- 2.0.5。\n", encoding="utf-8")
        (e2 / "adapters").mkdir(parents=True)
        (e2 / "adapters/story.js").write_text("// real story\n", encoding="utf-8")
        (e2 / "adapters/token.js").write_text("// real token\n", encoding="utf-8")
        # 真实 2.0.5 原清单：含六阶段 phase_bindings skill:story-knowledge 与 hooks/business-observe.mjs
        (e2 / "manifest.yaml").write_text(
            'schema_version: "1.1"\nname: s29-real-205\nversion: "2.0.5"\ndescription: real 2.0.5\n'
            'provides:\n  skills:\n    - story\n    - story-adaptation\n    - story-knowledge\n    - story-stats\n'
            '  skill_assets:\n    component-design:\n      knowledge: hooks/blueprint/author.md\n'
            '  knowledge:\n    - knowledge/facts/biz-profile.md\n'
            '  hooks:\n    spec:\n      pre_phase:\n        - hooks/shared/story-view.mjs\n'
            '      post_check:\n        - hooks/spec/post_check.mjs\n        - hooks/business-observe.mjs\n'
            '      pre_verifier:\n        - hooks/shared/pre_verifier.mjs\n'
            '  phase_rules_overlays:\n    spec: rules/spec-rules.overlay.yaml\n'
            'phase_bindings:\n'
            '  spec: &ak\n    before_phase_work:\n      - {kind: skill, ref: story-knowledge}\n'
            '  plan: *ak\n  coding: *ak\n  review: *ak\n  ut: *ak\n  testing: *ak\n',
            encoding="utf-8",
        )
        (e2 / "adaptation.yaml").write_text('adapted_for: "2.0.5"\n', encoding="utf-8")
        (p2 / "doc/usage.json").write_text('{"schema": 1, "requirements": {}}\n', encoding="utf-8")
        init_commit(p2)

        r2_imp = pub.import_external_base(DEV_SOURCE, p2, prepare_init=True)
        self.assertTrue(r2_imp["prepared"], r2_imp["stdout"] + r2_imp["stderr"])
        mf2 = yaml.safe_load((e2 / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertIn("hooks/business-observe.mjs", mf2["provides"]["hooks"]["spec"]["post_check"])
        self.assertNotIn("hooks/spec/post_check.mjs", mf2["provides"]["hooks"]["spec"]["post_check"])
        for ph in ("spec", "plan", "coding", "review", "ut", "testing"):
            refs = [b["ref"] for b in mf2["phase_bindings"][ph]["before_phase_work"]]
            self.assertEqual(["base/skills/story-knowledge/SKILL.md"], refs, ph)
        scan2 = e2 / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        r2_apply = subprocess.run(["node", str(scan2), "--apply"], cwd=str(p2), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, r2_apply.returncode, r2_apply.stdout + r2_apply.stderr)
        self.assertTrue((e2 / "hooks/business-observe.mjs").is_file(), "业务 hook 文件被误删")
        self.assertEqual(biz_hook_body, (e2 / "hooks/business-observe.mjs").read_text(encoding="utf-8"))
        self.assertFalse((e2 / "hooks/spec/post_check.mjs").exists(), "旧机制 hook 未退出")
        self.assertFalse((e2 / "rules").exists())
        self.assertFalse((e2 / "skills").exists())
        r2_chk = subprocess.run(["node", str(scan2), "--check"], cwd=str(p2), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, r2_chk.returncode, r2_chk.stdout + r2_chk.stderr)

        # R3：stand-in 缺两件或仅缺一件时，--check / --mark-adapted / --apply 自动完成均不放行，保住游标与样例
        p3 = self.root / "s29-standin-gap"
        make_consumer(p3, "S29StandIn", ["codex"])
        e3 = p3 / "doc" / "extensions"
        pub.pack_external_base(DEV_SOURCE, e3)
        (e3 / "adaptation.yaml").write_text('adapters: stand-in\nadapted_for: "2.0.5"\n', encoding="utf-8")
        init_commit(p3)
        scan3 = e3 / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        self.assertEqual(0, subprocess.run(["node", str(scan3), "--apply"], cwd=str(p3), capture_output=True).returncode)
        # 缺两件：--apply 未升游标，--check 退 1，--mark-adapted 退 2
        self.assertFalse((e3 / "base/examples").exists())
        self.assertEqual("2.0.5", yaml.safe_load((e3 / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])
        self.assertEqual(1, subprocess.run(["node", str(scan3), "--check"], cwd=str(p3), capture_output=True).returncode)
        self.assertEqual(2, subprocess.run(["node", str(scan3), "--mark-adapted"], cwd=str(p3), capture_output=True).returncode)
        # 仅补 story.js（缺 token.js）：仍拦
        (e3 / "adapters").mkdir(parents=True)
        (e3 / "adapters/story.js").write_text("// stand-in story\n", encoding="utf-8")
        self.assertEqual(1, subprocess.run(["node", str(scan3), "--check"], cwd=str(p3), capture_output=True).returncode)
        self.assertEqual(2, subprocess.run(["node", str(scan3), "--mark-adapted"], cwd=str(p3), capture_output=True).returncode)
        # 补齐 token.js：--check 与 --mark-adapted 均通过，清理样例并写 2.0.6
        (e3 / "adapters/token.js").write_text("// stand-in token\n", encoding="utf-8")
        self.assertEqual(0, subprocess.run(["node", str(scan3), "--check"], cwd=str(p3), capture_output=True).returncode)
        self.assertEqual(0, subprocess.run(["node", str(scan3), "--mark-adapted"], cwd=str(p3), capture_output=True).returncode)
        self.assertFalse((e3 / "base/examples").exists())
        self.assertEqual("2.0.6", yaml.safe_load((e3 / "adaptation.yaml").read_text(encoding="utf-8"))["adapted_for"])

        # R1 补充：无 framework.config.json 的空仓 --prepare-init 退出 2 且零写入、提示走最小根登记 / framework-init CREATE
        p_empty = self.root / "s29-empty-no-cfg"
        p_empty.mkdir(parents=True)
        r_empty = pub.import_external_base(DEV_SOURCE, p_empty, prepare_init=True)
        self.assertEqual(2, r_empty["returncode"])
        self.assertIn("framework-init CREATE", r_empty["stderr"])
        self.assertFalse((p_empty / "doc/extensions").exists())

        # R1 补充：实际 init-orchestrate.ts 遇同名他属桥即使退出 0，stderr 与后续 --check 仍显式点出缺桥宿主与冲突来源
        p_init_col = self.root / "s29-live-init-collision"
        make_consumer(p_init_col, "S29InitCol", ["codex"])
        ec = p_init_col / "doc/extensions"
        pub.pack_external_base(DEV_SOURCE, ec)
        init_commit(p_init_col)
        sc = ec / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        self.assertEqual(0, subprocess.run(["node", str(sc), "--prepare-init"], cwd=str(p_init_col), capture_output=True).returncode)
        # 放置同名他属桥后直接运行正式 framework-init UPDATE（模拟手工越过预检直接跑 init）
        other_c = ec / "other-ext/skills/story"
        other_c.mkdir(parents=True)
        (other_c / "SKILL.md").write_text("---\nname: story\ndescription: other\n---\n# other\n", encoding="utf-8")
        subprocess.run(["node", "-e", emit_other, str(p_init_col)], check=True, capture_output=True)
        col_bytes = (p_init_col / ".codex/skills/story/SKILL.md").read_bytes()
        clean_env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        r_init = subprocess.run(
            ["npx", "ts-node", "scripts/init-orchestrate.ts", "--scope", "project", "--project-root", str(p_init_col),
             "--execute", "--smart-auto", "--materialized-adapters", "codex"],
            cwd=str(p_init_col / "framework/harness"), capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=os.name == "nt", env=clean_env,
        )
        self.assertEqual(col_bytes, (p_init_col / ".codex/skills/story/SKILL.md").read_bytes(), "init 覆盖了同名他属桥")
        self.assertIn("codex", (r_init.stdout + r_init.stderr).lower())
        r_chk_col = subprocess.run(["node", str(sc), "--check"], cwd=str(p_init_col), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, r_chk_col.returncode)
        self.assertIn(".codex/skills/story/SKILL.md", r_chk_col.stderr)

    def test_s29_real_198_demo_isolated_copy_upgrades_end_to_end(self) -> None:
        """S29 R2：用当前仓 1.9.8 demo 原清单与原桥的隔离副本（自固定提交 6735fc79 取出）实跑
        import_external_base → 项目级 framework-init UPDATE → 宿主 /story adapt 全链，验证 13 份知识与替身就位、旧机制退场。"""
        import io
        import tarfile
        p = self.root / "s29-real-198-demo"
        p.mkdir(parents=True)
        arc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "6735fc79", "--", "demo"],
            check=True, capture_output=True,
        )
        with tarfile.open(fileobj=io.BytesIO(arc.stdout), mode="r:*") as tf:
            for m in tf.getmembers():
                if not m.name.startswith("demo/"):
                    continue
                rel = m.name[len("demo/"):]
                if not rel or rel == "framework" or rel.startswith("framework/"):
                    continue
                dst = p / rel
                if m.isdir():
                    dst.mkdir(parents=True, exist_ok=True)
                elif m.isfile():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(tf.extractfile(m).read())
        from design_fixture import framework_under_test
        fw_src = framework_under_test()
        shutil.copytree(fw_src, p / "framework", ignore=shutil.ignore_patterns("node_modules", "reports", "state"))
        (p / "framework/harness/state").mkdir(parents=True, exist_ok=True)
        (p / "framework/harness/reports").mkdir(parents=True, exist_ok=True)
        nm_dst = p / "framework/harness/node_modules"
        nm_src = fw_src / "harness/node_modules"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(nm_dst), str(nm_src)], check=True, capture_output=True)
        else:
            nm_dst.symlink_to(nm_src, target_is_directory=True)
        cfg = json.loads((p / "framework.config.json").read_text(encoding="utf-8"))
        cfg["materialized_adapters"] = ["codex", "opencode"]
        (p / "framework.config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        init_commit(p)
        # 1) 写前核 + 解包 base + 原位预置根清单
        r_imp = pub.import_external_base(DEV_SOURCE, p, prepare_init=True)
        self.assertTrue(r_imp["prepared"], r_imp["stdout"] + r_imp["stderr"])
        ext = p / "doc/extensions"
        mf = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual("wallet-sdk-demo", mf["name"])
        self.assertEqual("2.0.6", mf["version"])
        self.assertEqual(13, len([x for x in mf["provides"]["knowledge"] if isinstance(x, str)]))
        # 2) 项目级 framework-init UPDATE 刷新宿主桥指向 base/skills
        clean_env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        r_init = subprocess.run(
            ["npx", "ts-node", "scripts/init-orchestrate.ts", "--scope", "project", "--project-root", str(p),
             "--execute", "--smart-auto", "--materialized-adapters", "codex,opencode"],
            cwd=str(p / "framework/harness"), capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=os.name == "nt", env=clean_env,
        )
        self.assertEqual(0, r_init.returncode, r_init.stdout + r_init.stderr)
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", (p / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("doc/extensions/base/skills/story-adaptation/SKILL.md", (p / ".codex/skills/story-adaptation/SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", (p / ".opencode/skill/story/SKILL.md").read_text(encoding="utf-8"))
        self.assertFalse((p / ".claude/commands/story.md").exists(), "1.9.8 旧 claude bridge 未退出")
        self.assertFalse((p / ".cac/commands/story.md").exists(), "1.9.8 旧 cac bridge 未退出")
        # 3) 从桥指向的脚本执行 /story adapt --apply → 补齐 2.0.6 demo 替身 → --check
        scan = ext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        r_apply = subprocess.run(["node", str(scan), "--apply"], cwd=str(p), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, r_apply.returncode, r_apply.stdout + r_apply.stderr)
        for old_dir in ("bridges", "hooks", "rules", "skills"):
            self.assertFalse((ext / old_dir).exists(), f"1.9.8 旧目录未退出：{old_dir}")
        # stand-in 尚无同级 adapters 时 --check 必须拦截（R3）
        self.assertEqual(1, subprocess.run(["node", str(scan), "--check"], cwd=str(p), capture_output=True).returncode)
        # 放入 2.0.6 demo 完整替身 → --check 过
        shutil.copytree(REPO_ROOT / "test/fixtures/demo-extension/adapters", ext / "adapters")
        r_chk = subprocess.run(["node", str(scan), "--check"], cwd=str(p), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, r_chk.returncode, r_chk.stdout + r_chk.stderr)


    def _load_extension_via_native_loader(self, proj: Path) -> dict:
        script = """
const [root] = process.argv.slice(1);
const path = require('node:path');
const { createRequire } = require('node:module');
const fw = path.join(root, 'framework');
const req = createRequire(path.join(fw, 'harness', 'package.json'));
req('ts-node').register({ project: path.join(fw, 'harness', 'tsconfig.json'), transpileOnly: true });
const { loadInstanceExtensions } = req(path.join(fw, 'harness', 'extension-loader.ts'));
const loaded = loadInstanceExtensions(root, 'doc/extensions', { frameworkRoot: fw });
console.log(JSON.stringify({
  manifestVersion: loaded.manifestVersion,
  errors: loaded.errors,
  capabilities: Object.keys(loaded.extensionCapabilities ?? {}),
  mcpActions: Object.keys(loaded.mcpActions ?? {}),
  specPostCheck: loaded.hooks?.spec?.post_check ?? [],
  phaseBindings: loaded.phaseBindings ?? {},
}));
"""
        r = subprocess.run(["node", "-e", script, str(proj)], check=True, capture_output=True, text=True, encoding="utf-8")
        return json.loads(r.stdout.strip().splitlines()[-1])

    def _seed_real_205_repo(self, proj: Path) -> Path:
        import io
        import tarfile
        proj.mkdir(parents=True)
        self._copy_real_framework(proj)
        cfg = json.loads((DEMO / "framework.config.json").read_text(encoding="utf-8"))
        cfg["project_name"] = "Biz205S31"
        cfg["materialized_adapters"] = ["codex", "claude"]
        (proj / "framework.config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (proj / ".gitignore").write_text("doc/features/**/AR/story-src/drafts/\n", encoding="utf-8")
        ext = proj / "doc" / "extensions"
        arc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "552f8c90", "--", "extensions"],
            check=True, capture_output=True,
        )
        with tarfile.open(fileobj=io.BytesIO(arc.stdout), mode="r:*") as tf:
            for m in tf.getmembers():
                if not m.name.startswith("extensions/"):
                    continue
                rel = m.name[len("extensions/"):]
                if not rel or rel.startswith("knowledge/"):
                    continue
                dst = ext / rel
                if m.isdir():
                    dst.mkdir(parents=True, exist_ok=True)
                elif m.isfile():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(tf.extractfile(m).read())
        (ext / "business").mkdir(parents=True, exist_ok=True)
        (ext / "business/provider.mjs").write_text("export default () => ({ ok: true });\n", encoding="utf-8")
        (ext / "hooks/business-observe.mjs").write_text("export default () => ({ ok: true });\n", encoding="utf-8")
        kf = ext / "knowledge/facts/biz-profile.md"
        kf.parent.mkdir(parents=True, exist_ok=True)
        kf.write_text("---\nname: biz-profile\nkind: facts\nform: facets\napplies_when: 核对业务边界时。\n---\n\n## 定位\n\n- 真实 2.0.5 业务事实。\n", encoding="utf-8")
        mf_205 = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        mf_205["name"] = "biz-205-s31"
        mf_205["provides"]["knowledge"] = ["knowledge/facts/biz-profile.md"]
        mf_205["provides"]["hooks"]["spec"]["post_check"].append("hooks/business-observe.mjs")
        mf_205["provides"]["capabilities"] = {
            "biz-reconciliation": {"provider": "business/provider.mjs", "severity": "WARN"}
        }
        mf_205["provides"]["mcp_actions"] = {
            "biz-receipt": {
                "tool": "receipt_lookup",
                "usage": "Read local business receipt",
                "required": False,
                "severity": "MAJOR",
                "produces": ["doc/features/receipt.json"],
            }
        }
        (ext / "manifest.yaml").write_text(yaml.safe_dump(mf_205, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (ext / "adaptation.yaml").write_text('adapted_for: "2.0.5"\n', encoding="utf-8")
        (proj / "doc/usage.json").write_text('{"schema": 1, "requirements": {}}\n', encoding="utf-8")
        return ext

    def test_s31_preserves_capabilities_mcp_actions_and_blocks_modified_or_unknown_legacy_before_write(self) -> None:
        """S31 R1/R2：真实 2.0.5 原件带 capabilities/mcp_actions/业务 hook，导入前、init 后、apply 后均经原生 loader 核通过；
        同名旧文件改为业务字节或旧目录含已提交未知文件时，在写入任何字节前拦截。"""
        # 1) 正常真实 2.0.5 含 capabilities + mcp_actions + hooks/business-observe.mjs
        p_ok = self.root / "s31-ok"
        ext = self._seed_real_205_repo(p_ok)
        init_commit(p_ok)
        before = self._load_extension_via_native_loader(p_ok)
        self.assertEqual([], before["errors"], before)
        self.assertIn("biz-reconciliation", before["capabilities"])
        self.assertIn("biz-receipt", before["mcpActions"])

        imp = pub.import_external_base(DEV_SOURCE, p_ok, prepare_init=True)
        self.assertTrue(imp["prepared"], imp["stdout"] + imp["stderr"])
        r_init = self._run_live_init(p_ok, "codex,claude")
        self.assertEqual(0, r_init.returncode, r_init.stdout + r_init.stderr)
        after_init = self._load_extension_via_native_loader(p_ok)
        self.assertEqual([], after_init["errors"], after_init)
        self.assertIn("biz-reconciliation", after_init["capabilities"])
        self.assertIn("biz-receipt", after_init["mcpActions"])
        self.assertTrue(any(p.replace("\\", "/").endswith("hooks/business-observe.mjs") for p in after_init["specPostCheck"]), after_init)
        self.assertNotIn('"kind": "skill", "ref": "story-knowledge"', json.dumps(after_init["phaseBindings"]))

        scan = ext / "base/skills/story-adaptation/scripts/adapt-scan.mjs"
        r_apply = subprocess.run(["node", str(scan), "--apply"], cwd=str(p_ok), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, r_apply.returncode, r_apply.stdout + r_apply.stderr)
        after_apply = self._load_extension_via_native_loader(p_ok)
        self.assertEqual([], after_apply["errors"], after_apply)
        self.assertIn("biz-reconciliation", after_apply["capabilities"])
        self.assertIn("biz-receipt", after_apply["mcpActions"])
        self.assertTrue((ext / "business/provider.mjs").is_file())
        self.assertTrue((ext / "hooks/business-observe.mjs").is_file())
        self.assertFalse((ext / "hooks/spec/post_check.mjs").exists())
        self.assertFalse((ext / "skills").exists())
        self.assertFalse((ext / "rules").exists())
        self.assertEqual(0, subprocess.run(["node", str(scan), "--check"], cwd=str(p_ok), capture_output=True).returncode)

        # 2) 单差异 A：旧包同名路径 hooks/spec/post_check.mjs 被提交改为业务字节 → 写前拦截，零写入
        p_mod = self.root / "s31-modified-own"
        ext_mod = self._seed_real_205_repo(p_mod)
        custom_bytes = "// committed business override\nexport default () => ({ ok: true });\n"
        (ext_mod / "hooks/spec/post_check.mjs").write_text(custom_bytes, encoding="utf-8")
        mf_before = (ext_mod / "manifest.yaml").read_text(encoding="utf-8")
        init_commit(p_mod)
        imp_mod = pub.import_external_base(DEV_SOURCE, p_mod, prepare_init=True)
        self.assertFalse(imp_mod["prepared"], imp_mod)
        self.assertEqual(2, imp_mod["returncode"], imp_mod)
        self.assertIn("hooks/spec/post_check.mjs", imp_mod["stderr"])
        self.assertFalse((ext_mod / "base").exists(), "被拦截时不应解包 base/")
        self.assertEqual(mf_before, (ext_mod / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(custom_bytes, (ext_mod / "hooks/spec/post_check.mjs").read_text(encoding="utf-8"))

        # 3) 单差异 B：旧目录下存在已提交但未在 manifest 登记的未知文件 → 写前拦截，零写入
        p_unk = self.root / "s31-unknown-legacy"
        ext_unk = self._seed_real_205_repo(p_unk)
        unk_file = ext_unk / "hooks/spec/untracked-draft.mjs"
        unk_file.write_text("// committed unknown helper\n", encoding="utf-8")
        mf_unk_before = (ext_unk / "manifest.yaml").read_text(encoding="utf-8")
        init_commit(p_unk)
        imp_unk = pub.import_external_base(DEV_SOURCE, p_unk, prepare_init=True)
        self.assertFalse(imp_unk["prepared"], imp_unk)
        self.assertEqual(2, imp_unk["returncode"], imp_unk)
        self.assertIn("hooks/spec/untracked-draft.mjs", imp_unk["stderr"])
        self.assertFalse((ext_unk / "base").exists(), "被拦截时不应解包 base/")
        self.assertEqual(mf_unk_before, (ext_unk / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertTrue(unk_file.is_file())

if __name__ == "__main__":
    unittest.main()
