# -*- coding: utf-8 -*-
"""作者起手内容有没有在**动笔之前**送到作者手上（A03/A05）。

这条通道此前是断的：`on_context_load` 钩子一直能产出片段，但全仓唯一的调用点在 harness 的
verifier 装配处——内容只进了 verifier 的上下文，作者一次也看不到。实跑里除了有 `/story` 链
牵着的 spec，其余阶段都是先写完产物再读到要求。

所以这里测的不是「文件在不在」，是**通道**：

1. 六个阶段各自能取到**自己那一份**（来源标识是仓内相对路径，六份互不相同）；
2. 缺席 → 空且退出 0；损坏 → 明确失败、退出非零，**不降级成空**（静默的空和真正的空长得一样）；
3. verifier 的上下文里**不再**出现作者片段；
4. 「读过了」有唯一机械留痕：author 钩子路径进了 `key_inputs_read` 才过既有门禁。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
HARNESS = REPO / "framework" / "harness"
ENTRY = HARNESS / "scripts" / "author-context.ts"
MANIFEST = REPO / "doc" / "extensions" / "manifest.yaml"
RULES = REPO / "doc" / "extensions" / "rules"
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")
# context-exploration 门禁只覆盖这五个；testing 没有，如实无留痕。
GATED_PHASES = ("spec", "plan", "coding", "review", "ut")


def _run_entry(phase: str, *, cwd: Path = HARNESS, feature: str = "demo") -> subprocess.CompletedProcess:
    exe = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")
    return subprocess.run(
        [exe, "ts-node", str(ENTRY), "--phase", phase, "--feature", feature],
        cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )


class AuthorContextReachesTheAuthor(unittest.TestCase):
    """真实工程上跑：六个阶段各拿到自己那一份。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = {p: _run_entry(p) for p in PHASES}

    def test_every_phase_delivers_its_own_content(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                proc = self.outputs[phase]
                self.assertEqual(0, proc.returncode, f"入口挂了：{proc.stderr[-600:]}")
                self.assertIn(f"doc/extensions/hooks/{phase}/author.md", proc.stdout,
                              "没拿到本阶段的作者内容")

    def test_source_marker_is_a_repo_relative_path_not_a_basename(self):
        """标识必须是仓内相对路径。

        六个阶段的钩子都叫 `author.md`；只写文件名时六份标识一模一样——既指不出是哪一阶段，
        也没法被 `key_inputs_read` 逐字覆盖（那条门禁做子串匹配，`author.md` 会命中任何阶段，
        等于不设防）。
        """
        for phase in PHASES:
            with self.subTest(phase=phase):
                marker = next(l for l in self.outputs[phase].stdout.splitlines()
                              if l.startswith("<!-- hook:on_context_load:"))
                self.assertIn(f":doc/extensions/hooks/{phase}/author.md -->", marker)

    def test_phases_do_not_receive_each_others_content(self):
        """互不串台：拿到别的阶段那份，等于作者按错的要求去写。"""
        for phase in PHASES:
            others = [p for p in PHASES if p != phase]
            for other in others:
                with self.subTest(phase=phase, other=other):
                    self.assertNotIn(f"doc/extensions/hooks/{other}/author.md",
                                     self.outputs[phase].stdout)


class ChannelFailuresAreLoud(unittest.TestCase):
    """缺席 / 损坏 / 关闭三种情况必须能分辨——它们的处置完全不同。"""

    def setUp(self) -> None:
        self.ws = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "framework", self.ws / "framework",
                        ignore=shutil.ignore_patterns("node_modules", "__pycache__", "reports", "dist"))
        (self.ws / "framework" / "harness" / "node_modules").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "framework.config.json", self.ws / "framework.config.json")
        for rel in ("doc/architecture.md", "doc/module-catalog.yaml", "doc/glossary.yaml"):
            (self.ws / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, self.ws / rel)

    def tearDown(self) -> None:
        shutil.rmtree(self.ws, ignore_errors=True)

    # 临时工作区没有 node_modules，所以用主仓的 ts-node 以 transpileOnly 加载**副本**入口。
    # 入口按 `__dirname` 自锚，加载副本就等于把工程根锚到临时工作区——正是要测的那一面。
    DRIVER = (
        "require(process.env.TS_NODE_MOD).register({ transpileOnly: true, "
        "compilerOptions: { module: 'commonjs', target: 'ES2020', esModuleInterop: true } });\n"
        "const m = require(process.env.ENTRY);\n"
        "m.loadAuthorContext(process.env.HARNESS_ROOT, process.argv[2], 'demo')\n"
        "  .then(r => { process.stdout.write(JSON.stringify(r)); })\n"
        "  .catch(e => { process.stderr.write(String(e && e.message)); process.exit(1); });\n"
    )

    def _run_in_ws(self, phase: str) -> dict:
        driver = self.ws / "driver.js"
        driver.write_text(self.DRIVER, encoding="utf-8")
        env = dict(
            os.environ,
            # 副本在临时目录，minimist 等依赖只能从主仓的 node_modules 解析。
            NODE_PATH=str(HARNESS / "node_modules"),
            TS_NODE_MOD=str(HARNESS / "node_modules" / "ts-node"),
            ENTRY=str(self.ws / "framework/harness/scripts/author-context.ts"),
            HARNESS_ROOT=str(self.ws / "framework/harness"),
        )
        proc = subprocess.run(
            ["node", str(driver), phase], cwd=str(HARNESS),
            capture_output=True, text=True, encoding="utf-8",
            stdin=subprocess.DEVNULL, env=env,
        )
        self.assertEqual(0, proc.returncode, f"驱动挂了：{proc.stderr[-600:]}")
        return json.loads(proc.stdout)

    def test_no_extension_means_empty_not_failure(self):
        """没有扩展 = 本阶段确实没有额外要求：零片段、零失败，原行为不变。"""
        cfg = json.loads((self.ws / "framework.config.json").read_text(encoding="utf-8"))
        cfg["paths"].pop("extension_dir", None)
        (self.ws / "framework.config.json").write_text(json.dumps(cfg), encoding="utf-8")
        result = self._run_in_ws("spec")
        self.assertEqual([], result["fragments"])
        self.assertEqual([], result["failures"])

    def test_broken_hook_fails_loudly_instead_of_degrading_to_empty(self):
        """钩子抛错 → 明确失败，**不**降级成空。

        静默的空和真正的空长得一样；这条链路一旦静默失效，现场只表现为「作者又没按要求写」。
        """
        ext = self.ws / "doc" / "extensions"
        (ext / "hooks" / "spec").mkdir(parents=True)
        shutil.copy2(REPO / "doc/extensions/manifest.yaml", ext / "manifest.yaml")
        doc = yaml.safe_load((ext / "manifest.yaml").read_text(encoding="utf-8"))
        doc["provides"]["knowledge"] = []
        doc["provides"]["skills"] = []
        doc["provides"]["phase_rules_overlays"] = {}
        doc["provides"]["hooks"] = {"spec": {"on_context_load": ["hooks/spec/boom.mjs"]}}
        (ext / "manifest.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        (ext / "hooks" / "spec" / "boom.mjs").write_text(
            "throw new Error('钩子坏了');\n", encoding="utf-8")

        result = self._run_in_ws("spec")
        self.assertEqual([], result["fragments"])
        self.assertTrue(result["failures"], "钩子抛错却被当成「本阶段没有要求」")


class VerifierNoLongerGetsAuthorContent(unittest.TestCase):
    """`on_context_load` 与 `pre_verifier` 各有各的消费者，不许混。"""

    def test_harness_runner_does_not_emit_on_context_load(self):
        src = (HARNESS / "harness-runner.ts").read_text(encoding="utf-8")
        self.assertNotIn("emitLifecycle('on_context_load')", src,
                         "作者内容又被塞回 verifier 的 prompt 装配处了")
        self.assertIn("emitLifecycle('pre_verifier')", src, "pre_verifier 仍应服务 verifier")

    def test_entry_is_read_only(self):
        """入口不许写盘：它是把已有文本读出来，不是新的状态位。"""
        src = ENTRY.read_text(encoding="utf-8")
        for forbidden in ("writeFileSync", "mkdirSync", "appendFileSync", "renameSync"):
            self.assertNotIn(forbidden, src, f"作者入口出现了写操作 {forbidden}")


class ReadingItLeavesExactlyOneTrace(unittest.TestCase):
    """「读过了」的唯一机械留痕：author 钩子路径进 `key_inputs_read`。"""

    def test_gated_phases_declare_the_author_hook_as_required_snippet(self):
        for phase in GATED_PHASES:
            with self.subTest(phase=phase):
                doc = yaml.safe_load((RULES / f"{phase}-rules.overlay.yaml").read_text(encoding="utf-8"))
                extra = (doc.get("exploration_thresholds") or {}).get("phase_input_snippets_extra") or []
                self.assertIn(f"doc/extensions/hooks/{phase}/author.md", extra)

    def test_ungated_phase_declares_nothing(self):
        """testing 没有 context-exploration 门禁——如实不声明，不造一个假留痕。"""
        doc = yaml.safe_load((RULES / "testing-rules.overlay.yaml").read_text(encoding="utf-8"))
        self.assertIsNone(doc.get("exploration_thresholds"))

    def test_declared_snippet_matches_the_entry_marker_verbatim(self):
        """声明的字符串必须与入口输出的来源标识逐字一致，否则门禁永远命中不了。"""
        for phase in GATED_PHASES:
            with self.subTest(phase=phase):
                doc = yaml.safe_load((RULES / f"{phase}-rules.overlay.yaml").read_text(encoding="utf-8"))
                declared = doc["exploration_thresholds"]["phase_input_snippets_extra"][0]
                proc = _run_entry(phase)
                self.assertIn(f":{declared} -->", proc.stdout)


class ManifestKeepsOneSourceOfTruth(unittest.TestCase):
    def test_six_phases_register_their_author_hook(self):
        """每个阶段的作者坐标是那份 `author.md`，而且排在第一位。

        坐标要唯一：`context-exploration` 的 `key_inputs_read` 逐字引用它。
        同阶段再挂一个 `.mjs` 生成任务包不动摇这一点——`.mjs` 只产内容、不带来源标识行，
        它的内容属于那个坐标。所以判据是「第一项是 author.md、其余只能是同阶段的 author.mjs」。
        """
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        hooks = doc["provides"]["hooks"]
        for phase in PHASES:
            with self.subTest(phase=phase):
                registered = hooks[phase]["on_context_load"]
                self.assertEqual(f"hooks/{phase}/author.md", registered[0])
                self.assertTrue(set(registered[1:]) <= {f"hooks/{phase}/author.mjs"},
                                f"{phase} 挂了别的 on_context_load 钩子：{registered}")

    def test_author_content_is_not_duplicated_anywhere(self):
        """一份真源：author 正文不许被复制进 Skill / AGENTS / 模板。

        判据取每份 author.md 的首个非空标题行——它被复制出去就会在别处出现。
        """
        for phase in PHASES:
            author = REPO / "doc" / "extensions" / "hooks" / phase / "author.md"
            heading = next(l.strip() for l in author.read_text(encoding="utf-8").splitlines()
                           if l.strip().startswith("#"))
            proc = subprocess.run(
                ["git", "grep", "-l", "--fixed-strings", heading, "--",
                 "doc/extensions", "framework", "CLAUDE.md"],
                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
            hits = [h for h in proc.stdout.splitlines() if h.strip()]
            with self.subTest(phase=phase):
                self.assertEqual([f"doc/extensions/hooks/{phase}/author.md"], hits,
                                 f"{phase} 的作者内容出现了第二份：{hits}")

    def test_entry_point_no_longer_carries_per_phase_transport(self):
        """根 AGENTS / 生成入口不再承担逐阶段内容传输，只留机制说明。"""
        for f in (REPO / "CLAUDE.md", REPO / "doc/extensions/skills/story/AGENTS.section.md"):
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=f.name):
                self.assertNotIn("先完整读它", text)
                self.assertIn("author-context.ts", text)


if __name__ == "__main__":
    unittest.main()
