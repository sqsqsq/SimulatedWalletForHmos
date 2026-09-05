"""工作区必须带着 verifier 链——不带，被测侧就没有 verifier，也没有作者入口。

首跑（`story-suite-20260904-091600`）实测的后果：`run_multi_case.py` 的工作区白名单
不含 `.opencode`，于是

  · `skill story` 在被测侧找不到，作者只能自己去翻 `SKILL.md` 找命令；
  · verifier 起的是 `general` 子代理（全工具），不是 frontmatter 里逐工具 deny 的只读 verifier；
  · 发布插件不在，`verifier.report.<subject>.json` 由被测主模型**自己手造**
    （`agent_id: storiesuite-verifier-stub`），而 `check-receipt` 照收。

那一跑的 verifier 轴因此失真，步骤 1 的 D1 链路等于没验。

**这条测试不跑模型、不是 smoke**：它只建一次工作区模板，断言那三个文件在。
删掉任一个都会红——那正是它要拦的事。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"

# verifier 链的三件：只读子代理、结论发布插件、作者入口
CHAIN = (
    Path(".opencode/agent/verifier.md"),
    Path(".opencode/plugin/record-verifier-report.js"),
    Path(".opencode/skill/story/SKILL.md"),
)


def load_runner():
    """按路径加载驱动器——它不是包，直接 import 会因同名冲突取到别的模块。"""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "run_multi_case_for_test", SCRIPTS / "run_multi_case.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheWorkspaceCarriesTheVerifierChain(unittest.TestCase):
    """模板一个类建一次：它是只读夹具，而建一次要复制一份带依赖的完整工程。"""

    template: Path
    _tmp: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls._tmp = tempfile.TemporaryDirectory()
        suite_root = Path(cls._tmp.name) / "suite"
        suite_root.mkdir(parents=True)
        # suite-id 带进程号：模板落在共享的系统临时目录下，并行跑时几个 worker 会撞同一条路径
        cls.template, _ = cls.runner.create_workspace_template(
            suite_root, f"verifier-chain-test-{os.getpid()}")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.template.parent, ignore_errors=True)
        cls._tmp.cleanup()

    def test_the_repo_has_the_chain_materialised(self) -> None:
        """先看本仓：模板没物化的话，工作区带什么都带不出来。"""
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                self.assertTrue((REPO_ROOT / rel).is_file(),
                                f"{rel} 没物化——按 framework/agents/opencode/adapter.yaml 落它")

    def test_the_chain_is_not_git_ignored(self) -> None:
        """`.opencode/.gitignore` 忽略了它们的话，换台机器 clone 出来就又没有了。"""
        import subprocess
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                proc = subprocess.run(
                    ["git", "check-ignore", "-q", str(rel)],
                    cwd=str(REPO_ROOT), capture_output=True, text=True)
                self.assertNotEqual(0, proc.returncode,
                                    f"{rel} 被 git 忽略了——它是随仓交付的协议件")

    def test_the_workspace_template_carries_the_chain(self) -> None:
        """三件都要在模板里。这是复制规则真的生效的唯一证据。"""
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                self.assertTrue((self.template / rel).is_file(),
                                f"工作区模板里没有 {rel}——被测侧就没有 verifier 或作者入口")

    def test_dependencies_ride_along_so_nothing_needs_installing(self) -> None:
        """依赖跟着进工作区（用户 2026-09-04 裁定）——工作区就是一个能直接跑的工程。

        这条 2026-09-04 换了边。原来断言的是「不带依赖」，理由是体积；代价的另一半是：
        工作区不带 `framework/harness/node_modules`，被测模型开跑先装一遍依赖，
        那几分钟每一轮都要付一次。
        """
        if not (self.runner.REPO_ROOT / "framework" / "harness" / "node_modules").is_dir():
            self.skipTest("本仓还没装 harness 依赖，无从判断它带没带过来")
        self.assertTrue((self.template / "framework" / "harness" / "node_modules").is_dir(),
                        "harness 依赖没进工作区——被测模型又要现装一遍")


#: 把一次 task 完成事件喂给插件，回显发布结果。
PUBLISH_DRIVER = """
const [, , modulePath, payloadPath] = process.argv;
const fs = await import("node:fs");
const mod = await import(modulePath);
const payload = JSON.parse(fs.readFileSync(payloadPath, "utf-8"));
const out = await mod.default.internals.publishFromTaskResult(payload);
process.stdout.write(JSON.stringify(out));
"""


class TheFrameworkAndThePluginSpeakTheSameRequest(unittest.TestCase):
    """framework 造的 request，插件必须解析得动、发布得出。

    两边各自的夹具都自造 request，于是 schema 版本一分叉就成了盲区：
    实测过一次——framework 升到 1.1、插件停在 1.0，verifier 交了稿被整份拒收
    （`invocation_request_unparseable`），结论只落 bedside，而两边测试全绿。
    这一条跨过那道缝：请求由 framework 亲手造，落盘由插件亲手做。
    """

    HARNESS = REPO_ROOT / "framework" / "harness"
    PLUGIN = (REPO_ROOT / "framework" / "agents" / "opencode" / "templates"
              / "plugin" / "record-verifier-report.js")

    #: 让 framework 按当前实现造一份 request，打印成 JSON。
    #: 与下面写进 ai-prompt.md 的正文必须一致：插件的四方对账会拿 request 里的
    #: prompt_sha256 跟磁盘上那份文件对，对不上就落 bedside。
    PROMPT_TEXT = "# 审查指令\n\n本轮待审产物：spec.md。\n"

    BUILD_SRC = """
import { buildVerifierRequest, renderVerifierRequest, computePromptSha256 }
  from './scripts/utils/verifier-request';
import { readFileSync } from 'node:fs';
const promptText = readFileSync(process.argv[2], 'utf-8');
const request = buildVerifierRequest({
  feature: 'CHAINFEAT', phase: 'spec',
  prompt_path: 'doc/features/CHAINFEAT/spec/reports/ai-prompt.md',
  prompt_sha256: computePromptSha256(promptText), material_sha256: 'b'.repeat(64),
  gate_fingerprint: null, source_commit_sha: null, worktree_digest: null,
});
process.stdout.write(JSON.stringify({ request, rendered: renderVerifierRequest(request) }));
"""

    def test_a_framework_built_request_is_accepted_by_the_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # 先落提示词，再让 framework 照它造 request——harness 就是这个顺序。
            # 按字节写：Windows 上 write_text 会把换行转成 CRLF，两边哈希就对不上，
            # 而那不是本条要测的事。
            reports = root / "doc" / "features" / "CHAINFEAT" / "spec" / "reports"
            reports.mkdir(parents=True)
            prompt_file = reports / "ai-prompt.md"
            prompt_file.write_bytes(self.PROMPT_TEXT.encode("utf-8"))
            builder = self.HARNESS / "story-chain-request.ts"
            builder.write_text(self.BUILD_SRC, encoding="utf-8")
            try:
                built = subprocess.run(
                    ["npx", "ts-node", str(builder), str(prompt_file)], cwd=str(self.HARNESS),
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=180, shell=(os.name == "nt"))
            finally:
                builder.unlink(missing_ok=True)
            if built.returncode != 0:
                self.skipTest(f"ts-node 跑不起来（不是本条要测的事）：{built.stderr[-300:]}")
            payload = json.loads(built.stdout[built.stdout.index("{"):])
            request = payload["request"]

            (reports / "summary.json").write_text(
                json.dumps({"schema_version": "2.0",
                            "verifier_subject_id": request["subject_id"]}), encoding="utf-8")

            driver = root / "driver.mjs"
            driver.write_text(PUBLISH_DRIVER, encoding="utf-8")
            call = {
                "projectRoot": str(root),
                "toolCallId": "call_chain",
                "args": {"prompt": payload["rendered"], "subagent_type": "verifier",
                         "description": "verify spec"},
                "output": {
                    "title": "verify spec",
                    "metadata": {"parentSessionId": "ses_parent000000000000000000",
                                 "sessionId": "ses_child0000000000000000000",
                                 "truncated": False},
                    "output": ('<task id="ses_child0000000000000000000" state="completed">\n'
                               "<task_result>\n审查结论：通过。\n\n"
                               "<!-- maison-verifier-result:v1 -->\n"
                               f"verifier_subject_id: {request['subject_id']}\n"
                               "verdict: PASS\nblocker_count: 0\n"
                               "<!-- /maison-verifier-result:v1 -->\n</task_result>\n</task>"),
                },
            }
            payload_file = root / "payload.json"
            payload_file.write_text(json.dumps(call, ensure_ascii=False), encoding="utf-8")
            ran = subprocess.run(
                ["node", str(driver), self.PLUGIN.as_uri(), str(payload_file)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, ran.returncode, ran.stderr[-500:])
            out = json.loads(ran.stdout)
            self.assertEqual("published", out.get("state"),
                             f"framework 造的 request 插件没收下：{out}")


if __name__ == "__main__":
    unittest.main()
