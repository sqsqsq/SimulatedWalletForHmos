"""新装的仓装完就能跑：`provides.knowledge` 是空的，全链照走。

首次安装不建知识骨架，不放任何知识正文（Adapt 需求 A3）。那之后清单
就是空的，而知识派生此前把「清单为空」当派生失败：`activeKnowledge` 直接 throw，
八个调用点里七个硬失败——新仓装完第一件事是撞墙。

这里守的是**两件事的区别**：

  没登记 = 这个仓还没配置知识，返回四类皆空，链条照走；
  登记了却读不到 = 读取失败被吞成空，仍然响亮报错（失效形态 M06 守的正是它）。

判据分不出这两件事，就只能二选一：要么新仓跑不起来，要么一份读不到的知识被当成
「本来就没有」静默放过。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
FEATURE = "EK90001"


def node(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=90)


def as_url(path: Path) -> str:
    return json.dumps(path.resolve().as_uri())


class EmptyKnowledgeRepo(unittest.TestCase):
    """一份工作区：真实扩展，但激活清单被清空——新装的仓就是这个样子。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        self.ext = self.root / "doc" / "extensions"
        (self.root / "framework.config.json").write_text(
            json.dumps({"paths": {"extension_dir": "doc/extensions"}}), encoding="utf-8")

        # 清单清空：`knowledge:` 那一节的条目全删，键留着——首次安装建的就是这个形态
        manifest = self.ext / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^    - knowledge/.*\n", "", text)
        text = text.replace("  knowledge:\n", "  knowledge: []\n")
        manifest.write_text(text, encoding="utf-8")
        self.manifest = manifest

        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "spec").mkdir(parents=True)

    # ---- 驱动 ----

    def module(self, name: str) -> Path:
        return self.ext / "hooks" / "shared" / name

    def derive(self, expr: str) -> subprocess.CompletedProcess:
        """在这个仓上跑一段用知识派生的表达式，回传 stdout / stderr / 退出码。"""
        return node("--input-type=module", "-e",
                    f"const k = await import({as_url(self.module('knowledge.mjs'))});"
                    f"const root = {json.dumps(self.root.as_posix())};"
                    f"process.stdout.write(String({expr}));")

    # ---- 判据 ----

    def test_an_empty_manifest_derives_four_empty_kinds(self) -> None:
        """清单空 = 还没配置知识，四类皆空，不抛。"""
        proc = self.derive(
            "JSON.stringify(((x) => ({facts: x.facts.length, constraints: x.constraints.length,"
            " patterns: x.patterns.length, entries: x.entries.length}))(k.activeKnowledge(root)))")
        self.assertEqual(0, proc.returncode, f"空清单把派生打挂了：{proc.stderr}")
        self.assertEqual({"facts": 0, "constraints": 0, "patterns": 0, "entries": 0},
                         json.loads(proc.stdout))

    def test_self_check_passes_on_an_empty_manifest(self) -> None:
        """没有知识文件要扫，自检自然通过——它扫的是激活清单里的文件。"""
        proc = self.derive(
            "JSON.stringify(k.selfCheck(root, k.activeKnowledge(root)))")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual([], json.loads(proc.stdout))

    def test_a_registered_file_that_cannot_be_read_still_fails_loudly(self) -> None:
        """登记了却读不到仍然报错——那是读取失败被吞成空，与「还没配置」是两件事。"""
        text = self.manifest.read_text(encoding="utf-8")
        self.manifest.write_text(
            text.replace("  knowledge: []\n",
                         "  knowledge:\n    - knowledge/facts/not-there.md\n"),
            encoding="utf-8")
        proc = self.derive("JSON.stringify(k.activeKnowledge(root))")
        self.assertNotEqual(0, proc.returncode, "登记的文件读不到却过了——那正是静默失效")
        self.assertIn("not-there.md", proc.stderr)

    def test_the_task_package_says_this_repo_has_no_knowledge(self) -> None:
        """任务包给作者一句人话，不是「激活 0 条约束（域：）」那种像坏了的句子。"""
        proc = subprocess.run(
            ["node", str(self.ext / "hooks" / "spec" / "author.mjs"), "--feature", FEATURE],
            cwd=str(self.root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, f"空知识下任务包出不来：{proc.stderr}")
        self.assertIn("本仓未配置知识", proc.stdout)
        self.assertNotIn("域：）", proc.stdout, "渲染出了空洞的派生结果，作者会以为机制坏了")
        self.assertIn("skills/story/reference/knowledge/protocol.md", proc.stdout)

    def test_the_use_skeleton_comes_out_with_zero_entries(self) -> None:
        """`knowledge-use.yaml` 的骨架照样生成，只是一条都没有——没有条目要判。"""
        proc = subprocess.run(
            ["node", str(self.module("knowledge-use.mjs")), "init", "--feature", FEATURE],
            cwd=str(self.root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, f"空知识下骨架生成失败：{proc.stderr}")
        text = (self.feature_root / "spec" / "knowledge-use.yaml").read_text(encoding="utf-8")
        body = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
        self.assertNotIn("applicable", "\n".join(body), "零条目的骨架里冒出了要判的条目")
        self.assertIn("patterns: []", "\n".join(body),
                      "一个候选都不在册还摆着填写占位——那个问题只有一种答案")


if __name__ == "__main__":
    unittest.main()
