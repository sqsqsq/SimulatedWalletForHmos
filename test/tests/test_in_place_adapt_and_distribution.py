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
from ext_workspace import DEV_SOURCE, git_init_excluding_framework, link_framework  # noqa: E402

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
        self.assertIn(".gitignore", files)
        self.assertEqual("/examples/\n", (packed_root / "base" / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("package-manifest.yaml", files)
        self.assertTrue(any(f.startswith("examples/knowledge/") for f in files), "外网包缺 base/examples/knowledge/")
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
        self.assertTrue((pay / "doc/extensions/base/examples/knowledge").is_dir(), "首装 --apply 后样例应仍供模型参考")
        self.assertIn("doc/extensions/base/skills/story/SKILL.md", (pay / ".codex/skills/story/SKILL.md").read_text(encoding="utf-8"))

        # 写目标知识与独立审查报告 → 跑 --check 与 --mark-adapted（清样例、保留 .gitignore、最后写 adapted_for）
        write_sample_knowledge_and_review(pay, scan)
        chk = subprocess.run(["node", str(scan), "--check"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, chk.returncode, chk.stdout + chk.stderr)
        self.assertIn("知识可读（1 份）", chk.stdout)

        # 未清理前 adapted_for 尚未写入
        adapt_before = yaml.safe_load((pay / "doc/extensions/adaptation.yaml").read_text(encoding="utf-8")) or {}
        self.assertNotIn("adapted_for", adapt_before)

        marked = subprocess.run(["node", str(scan), "--mark-adapted"], cwd=str(pay), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, marked.returncode, marked.stdout + marked.stderr)
        self.assertFalse((pay / "doc/extensions/base/examples").exists(), "适配完成后未清理 base/examples/")
        self.assertTrue((pay / "doc/extensions/base/.gitignore").is_file(), "清理 base/examples/ 时误删了 base/.gitignore")
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
        # 造旧混装布局（无 base/，旧 hooks/skills/rules + 业务 knowledge + 业务 adapters + 旧 manifest）
        (ext / "hooks/spec").mkdir(parents=True)
        (ext / "hooks/spec/post_check.mjs").write_text("export default () => ({ ok: true });\n", encoding="utf-8")
        (ext / "rules").mkdir(parents=True)
        (ext / "rules/spec-rules.overlay.yaml").write_text("semantic_checks: {}\n", encoding="utf-8")
        old_adapters = ext / "skills/story/scripts/adapters"
        old_adapters.mkdir(parents=True)
        biz_story = "// LegacyBiz real story adapter\nmodule.exports = { real: true };\n"
        biz_token = "// LegacyBiz real token adapter\nconsole.log('real-token');\n"
        (old_adapters / "story.js").write_text(biz_story, encoding="utf-8")
        (old_adapters / "token.js").write_text(biz_token, encoding="utf-8")
        (ext / "skills/story").mkdir(parents=True, exist_ok=True)
        (ext / "skills/story/SKILL.md").write_text("---\nname: story\ndescription: old\n---\n# old\n", encoding="utf-8")
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
        self.assertTrue((ext / "base/.gitignore").is_file())
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


if __name__ == "__main__":
    unittest.main()
