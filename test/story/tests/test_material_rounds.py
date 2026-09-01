"""一轮 = 一次材料状态 —— **界面参考也是材料**。

轮次指纹曾只算四份文本源（`RR/prd.md`、`SR/design.md`、`AR/design.md`、
`AR/upstream.md`）。补料如果只有界面图，转换后只落 `ux-reference/`，四份文本
一个字节没变 → 指纹不变 → 不算新一轮 → 关卡列表永不重置 → 流程卡死在
`import_and_reanalyze`。实跑撞到过一次：模型只能自己改机制层绕过去。

这一份锁的就是「什么算材料变了」这个定义的完整性。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOW = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story_flow.py"
FEATURE = "AR90001"


class MaterialRoundCase(unittest.TestCase):
    """每个用例一份新工作区，跑真脚本、读真契约。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "RR").mkdir(parents=True)
        (self.feature_root / "SR").mkdir(parents=True)
        (self.feature_root / "AR").mkdir(parents=True)
        (self.feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n",
                                                         encoding="utf-8")
        (self.feature_root / "SR" / "design.md").write_text("# 系统设计\n\n分工。\n",
                                                            encoding="utf-8")
        (self.feature_root / "AR" / "design.md").write_text("# 提取件\n\n范围。\n",
                                                            encoding="utf-8")

    def run_flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def round_now(self) -> dict:
        proc = self.run_flow("round")
        self.assertEqual(proc.returncode, 0,
                         "round 失败：" + (proc.stdout or "") + (proc.stderr or ""))
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def add_ux(self, name: str, body: bytes = b"\x89PNG\r\n") -> None:
        ux = self.feature_root / "ux-reference"
        ux.mkdir(exist_ok=True)
        (ux / name).write_bytes(body)


class MaterialFingerprintCoversEveryInput(MaterialRoundCase):

    def test_a_ux_only_supplement_starts_a_new_round(self) -> None:
        """只往 `ux-reference/` 加一张图——那也是材料变了，必须算新一轮。"""
        first = self.round_now()
        self.add_ux("界面示意.png")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"),
                            "只补图片时指纹没变——补料等于没发生")
        self.assertGreater(second.get("round", 0), first.get("round", 0),
                           "指纹变了却没进新一轮")

    def test_a_text_only_supplement_still_starts_a_new_round(self) -> None:
        """补文字的老路一步没变。"""
        first = self.round_now()
        prd = self.feature_root / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n补充一段。\n",
                       encoding="utf-8")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"))
        self.assertGreater(second.get("round", 0), first.get("round", 0))

    def test_no_ux_directory_is_not_an_error(self) -> None:
        """没有界面参考的单子照常跑，不因为多了一个目录概念就变了口径。"""
        self.assertFalse((self.feature_root / "ux-reference").exists())
        first = self.round_now()
        self.assertTrue(first.get("materials"))
        self.assertEqual(first.get("round"), self.round_now().get("round"),
                         "材料没变，重跑 round 应当幂等")

    def test_rerunning_without_change_is_idempotent(self) -> None:
        """有界面参考时也一样：材料没动，重跑不造新轮次。"""
        self.add_ux("界面示意.png")
        first = self.round_now()
        second = self.round_now()
        self.assertEqual(first.get("materials"), second.get("materials"))
        self.assertEqual(first.get("round"), second.get("round"))

    def test_changing_one_image_is_a_new_round(self) -> None:
        """换掉同名图的内容也是材料变了——按文件内容算，不按文件名算。"""
        self.add_ux("界面示意.png")
        first = self.round_now()
        self.add_ux("界面示意.png", b"\x89PNG\r\n\x1a\n changed")
        second = self.round_now()
        self.assertNotEqual(first.get("materials"), second.get("materials"))

    def test_the_deadlock_shape_does_not_come_back(self) -> None:
        """复刻实跑撞到的形状：第 1 轮四源齐，第 2 轮只加一张图。

        这一条是本文件的靶子。它红了就说明「什么算材料变了」的定义又缺了一块。
        """
        r1 = self.round_now()
        self.add_ux("签约页.png")
        self.add_ux("管理页.png")
        r2 = self.round_now()
        self.assertGreater(r2.get("round", 0), r1.get("round", 0),
                           "UX-only 补料没能开出新一轮——死锁又回来了")

    def test_the_input_definition_names_no_extras(self) -> None:
        """定义里不许出现「额外 / 附加 / extra」——那正是这个 bug 的根。

        把界面参考写成附加项，下一次谁再加一类材料源，又会被漏在指纹外面。
        """
        body = FLOW.read_text(encoding="utf-8")
        for word in ("EXTRA", "额外", "附加"):
            self.assertNotIn(word, body,
                             "「%s」把某一类材料说成了二等的" % word)




class OnlyTwoStopsAndBothUnconditional(unittest.TestCase):
    """本扩展新增的停等点只有两处，且都无条件。

    ## 为什么要锁

    白名单曾经是四条**条件句**：「材料缺口——**需要**人补料才能继续」。
    需不需要由模型判，等于把停等的开关交给被停的那一方。再配上 `--by ai`
    这一档（用户说「别逐个问」时代签关卡），实跑里就出现了：模型判「材料足够」
    → 条件不成立 → 不停 → 以自己的名义记掉关卡 → 材料补充环节整个被跳过。

    另一头是反的：契约要求模型在 S4 收口处问一次「本轮做到哪一步」，
    于是固定长出第三个停等点。那个问题在更早的两个地方已经有答案。
    """

    SKILL = (REPO_ROOT / "doc/extensions/skills/story/SKILL.md")
    FLOW = (REPO_ROOT / "doc/extensions/skills/story/scripts/story_flow.py")

    def skill(self) -> str:
        return self.SKILL.read_text(encoding="utf-8")

    def run_decide(self, root: Path, by: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.FLOW), "decide", "--feature", "AR90001",
             "--project-root", str(root), "--gate", "material_scope",
             "--chosen", "supplement", "--by", by, "--basis", "他说的原话"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def test_the_gate_decision_only_accepts_a_human_signature(self) -> None:
        """**物理门禁**：`--by ai` 连参数校验都过不去。

        只改文档没用——「记得停下问人」这种话模型会忘，门禁不会。
        """
        import ast
        body = self.FLOW.read_text(encoding="utf-8")
        tree = ast.parse(body)
        actors = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "ACTORS" for t in node.targets):
                actors = ast.literal_eval(node.value)
        self.assertEqual(("human",), actors, "关卡决策不该有人以外的签署者")

    def test_by_ai_is_refused_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR90001" / "AR").mkdir(parents=True)
            proc = self.run_decide(root, "ai")
            self.assertNotEqual(0, proc.returncode, "`--by ai` 竟然被接受了")
            self.assertIn("human", (proc.stdout or "") + (proc.stderr or ""))

    def test_the_whitelist_has_no_conditional_wording(self) -> None:
        """两处停等不许再写成条件句——条件由谁判，开关就在谁手里。"""
        text = self.skill()
        for conditional in ("需要人补料才能继续", "scope_gate 触发的"):
            self.assertNotIn(conditional, text,
                             "「%s」把停等的开关交回给了模型" % conditional)
        self.assertIn("必停", text, "两处停等要明写无条件")

    def test_the_spec_boundary_question_is_gone(self) -> None:
        """S4 收口处那一问退场——它固定长出第三个停等点。"""
        text = self.skill()
        for gone in ("一次问代替逐段问", "一次讲清", "做到哪一步"):
            self.assertNotIn(gone, text, "「%s」还在，进 spec 前仍会停一次" % gone)
        self.assertIn("直接进 spec，不问", text)

    def test_the_failure_exit_has_a_checkable_precondition(self) -> None:
        """「修不动了」是失败上报，不是确认点，而且前提必须可核。

        写成「同一处连续 3 次修不好」由模型自己判的话，试一次就能宣布修不好
        然后合法停下——与条件式白名单是同一个毛病。
        """
        text = self.skill()
        self.assertIn("失败出口", text, "失败上报要与停等点分开写")
        self.assertIn("连续三次运行", text, "前提要可核：连续三次 check 都报同一类")
        self.assertNotIn("触发白名单第 3 条", text, "旧的自述式出口还在被引用")

    def test_no_delegated_choice_path_remains(self) -> None:
        """代选路径整个退场——它就是材料环节被跳过的那条路。"""
        for rel in ("doc/extensions/skills/story/rules/scope_gate.md",
                    "doc/extensions/skills/story/rules/init_analysis.md",
                    "doc/extensions/skills/story/SKILL.md"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for gone in ('by:"ai"', "AI 代选", "代选永远不选"):
                self.assertNotIn(gone, text, "%s 里还留着代选路径：%s" % (rel, gone))


if __name__ == "__main__":
    unittest.main()
