"""S4 提交 —— **输入与输出是两份文件**。

`AR/design.md` 是上游给进来的输入件，也是一份登记在案的材料。S4 的提取稿曾经直接
覆盖它：覆盖之后材料指纹变了，流程判定「材料已经变了」，把刚要收口的这一轮推回
「重新盘点」——自己的输出把自己推回了未定状态，而永久忽略这份材料又会让上游真的
更新时无人发现。

所以提取稿另落一份，由 `complete --from` 提交：被覆盖的上游那一份先进 `.backups/local/`
（与导入覆盖正文同一条退路），再覆盖，再把材料基准挪到覆盖之后的现状。
这一份锁的是这条顺序、它的失败语义，以及「哪些差异算提交自己写的、哪些仍算材料变了」。
"""
from __future__ import annotations

import argparse
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STORY_SCRIPTS = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.decisions import cmd_decide  # noqa: E402
from flow.inputs import MATERIAL_REQUEST_KEYS, material_options  # noqa: E402
from flow.lifecycle import cmd_status  # noqa: E402
from flow.state import CARRY_ALL  # noqa: E402
from flow.submission import cmd_complete  # noqa: E402
from materials import registry  # noqa: E402

FEATURE = "AR90001"
UPSTREAM_AR = ("# AR90001 上游预填\n\n## 上游先写下的几条\n\n"
               "- 判定与扣款都在服务端，端侧只做签约入口。\n")
DRAFT = (
    "# AR90001 自动充值 — 开发需求（AR）\n\n"
    "## 1 简介\n\n### 1.1 需求介绍\n\n端侧承载签约入口与状态展示。\n\n"
    "## 2 需求分析\n\n### 2.1 场景与功能点\n\n签约、解约、状态查看。\n\n"
    "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\n判定在服务端。\n\n"
    "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
    "## 5 上游已声明线索\n\n无。\n")


class S4Case(unittest.TestCase):
    """一份新工作区，跑真脚本走到「可以收口」，再各自测提交。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        for part in ("RR", "SR", "AR"):
            (self.feature_root / part).mkdir(parents=True)
        self.prd = self.feature_root / "RR" / "prd.md"
        self.prd.write_text("# 产品需求\n\n背景。\n", encoding="utf-8")
        (self.feature_root / "SR" / "design.md").write_text(
            "# 系统设计\n\n分工。\n", encoding="utf-8")
        self.design = self.feature_root / "AR" / "design.md"
        self.design.write_text(UPSTREAM_AR, encoding="utf-8")
        self.src = self.feature_root / "AR" / "story-src"
        self.backup_dir = self.feature_root / ".backups" / "local"

    # -- 驱动 ---------------------------------------------------------------

    def flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))

    def ok(self, *args: str) -> dict:
        proc = self.flow(*args)
        self.assertEqual(0, proc.returncode,
                         f"{args} 失败：{proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def next_of(self) -> str:
        return self.ok("status")["next"]

    def backups(self) -> list[Path]:
        """被覆盖的 `AR/design.md` 在 `.backups/local/` 里的全部副本。"""
        return sorted(self.backup_dir.glob("AR-design.md-*.md"))

    def backup_upstream(self, text: str = UPSTREAM_AR) -> Path:
        """把现场摆成「备份已经写了」——断点之前那一步的形态。"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        path = self.backup_dir / "AR-design.md-20260915000000.md"
        path.write_text(text, encoding="utf-8")
        return path

    def gate_options(self, gate: str) -> None:
        self.src.mkdir(parents=True, exist_ok=True)
        options = ([dict(o) for o in material_options()]
                   if gate == "material_scope"
                   else [{"key": CARRY_ALL, "label": "按当前范围整体承载"}])
        (self.src / ".gate-options.json").write_text(
            json.dumps({"gate": gate, "options": options}, ensure_ascii=False),
            encoding="utf-8")

    def ready_to_commit(self, with_draft: bool = True) -> None:
        """S1–S3 走完，停在「该做 S4 了」。"""
        self.ok("init")
        self.ok("round")
        self.gate_options("material_scope")
        self.ok("decide", "--gate", "material_scope", "--chosen", "confirm_scope",
                "--basis", "用户回复：现有材料就是全部")
        self.write_analysis()
        self.ok("round")
        self.gate_options("scope_decision")
        self.ok("decide", "--gate", "scope_decision", "--chosen", CARRY_ALL,
                "--basis", "用户回复：整体承载")
        if with_draft:
            self.write_draft()

    def write_analysis(self) -> None:
        """需求分析（S2b）的两份产出，`round` 消费进本轮契约。"""
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / ".positioning.json").write_text(json.dumps({
            "scope_source": "user_stated",
            "scope_text": "本 AR 承载自动充值签约与管理",
            "sr_related_ars": [],
        }, ensure_ascii=False), encoding="utf-8")
        (self.src / ".scope-options.json").write_text(json.dumps(
            [{"key": CARRY_ALL, "label": "按当前范围整体承载",
              "recommended": True}], ensure_ascii=False), encoding="utf-8")

    def write_draft(self, text: str = DRAFT) -> Path:
        path = self.src / "design-draft.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, source: str = "AR/story-src/design-draft.md") \
            -> subprocess.CompletedProcess:
        return self.flow("complete", "--from", source)

    def second_round_ready(self) -> None:
        """第一轮收口后重开，第二轮由别的材料开出、AR 没换。"""
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.ok("reopen")
        self.prd.write_text("# 产品需求\n\n背景。\n\n第二轮补的。\n", encoding="utf-8")
        self.ok("round")                       # 第 2 轮：没摆第一级选项就不停在那一级
        self.write_analysis()
        self.ok("round")
        self.gate_options("scope_decision")
        self.ok("decide", "--gate", "scope_decision", "--chosen", CARRY_ALL,
                "--basis", "用户回复：整体承载")
        self.write_draft(DRAFT.replace("端侧承载签约入口与状态展示。", "第二轮改写过。"))


class TheCandidateDoesNotReopenItsOwnRound(S4Case):
    """提交自己写下的那一笔差异，不该被读成「材料变了」。"""

    def test_commit_closes_the_round_and_enters_spec(self) -> None:
        self.ready_to_commit()
        self.assertEqual("run_complete", self.next_of(),
                         "提取稿已在，下一步就该是提交收口")
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertTrue(result["committed"])
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual(DRAFT, self.design.read_text(encoding="utf-8"),
                         "提交的必须是模型写的那一份，脚本不改一个字节")
        self.assertTrue(self.next_of().startswith("spec_"),
                        "收口之后该进 spec，而不是回去重新盘点材料")
        self.assertEqual({"human"}, {g["by"] for r in self.contract()["rounds"]
                                     for g in r.get("gates", [])},
                         "关卡记录的签署者不是人")

    def test_the_overwritten_upstream_goes_to_the_backup(self) -> None:
        """上游预填被提取稿盖掉之前留一份：`.backups/local/` 是覆盖正文的通用退路。"""
        self.ready_to_commit()
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual(1, len(self.backups()), "覆盖上游输入之前没有备份")
        self.assertEqual(UPSTREAM_AR, self.backups()[0].read_text(encoding="utf-8"))
        self.assertEqual(self.backups()[0].relative_to(self.feature_root).as_posix(),
                         result["backup"])
        self.assertEqual({"sha256"}, set(self.contract()["design"]),
                         "契约里的提交登记只留身份，不再指向原件")
        self.assertFalse((self.src / "sources").exists(), "按轮次留存的目录又长回来了")

    def test_a_later_round_sees_no_material_change(self) -> None:
        """收口之后再盘点一次：材料基准已随提交挪到覆盖之后，不该开出新一轮。"""
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        before = len(self.contract()["rounds"])
        again = self.ok("round")
        self.assertFalse(again["created"], "提交自己的输出开出了新一轮——自重开就是这么来的")
        self.assertEqual(before, len(self.contract()["rounds"]))

    def test_repeating_the_command_commits_nothing_more(self) -> None:
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        again = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertFalse(again["committed"], "重复成功的命令应当报已完成")
        self.assertEqual(1, len(self.backups()), "第二次提交把自己的输出又备份了一份")

    def test_swapping_the_draft_after_the_close_needs_reopen(self) -> None:
        """收口之后下游就在读 AR/design.md：换一份要显式 reopen，不能悄悄盖过去。"""
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.write_draft(DRAFT.replace("端侧承载签约入口与状态展示。", "改了一句。"))
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("reopen", proc.stderr)
        self.assertEqual(DRAFT, self.design.read_text(encoding="utf-8"))


class RealMaterialChangesAreStillFound(S4Case):
    """只有 AR/design.md 那一笔差异算提交自己的；其余来源照原样检查。"""

    def test_an_upstream_change_before_commit_blocks_it(self) -> None:
        self.ready_to_commit()
        self.prd.write_text("# 产品需求\n\n背景。\n\n补了一节。\n", encoding="utf-8")
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("材料", proc.stderr)
        self.assertEqual(UPSTREAM_AR, self.design.read_text(encoding="utf-8"),
                         "预检失败却动了输入")
        self.assertEqual("in_progress", self.contract()["status"])

    def test_an_edited_ar_before_commit_blocks_it(self) -> None:
        """上游这一轮登记之后又改了 AR：那是材料变了，得重新盘点，不能直接盖掉。"""
        self.ready_to_commit()
        self.design.write_text(UPSTREAM_AR + "\n- 又加了一条。\n", encoding="utf-8")
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertEqual([], self.backups(), "预检失败却写了备份")
        self.assertEqual("in_progress", self.contract()["status"])

    def test_a_change_during_a_retry_blocks_it(self) -> None:
        """覆盖已经发生、其余材料又变了：不认这个差异，也不重置基准。"""
        self.ready_to_commit()
        self.backup_upstream()
        self.design.write_text(DRAFT, encoding="utf-8")
        self.prd.write_text("# 产品需求\n\n背景。\n\n中途补的。\n", encoding="utf-8")
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("材料", proc.stderr)
        self.assertEqual("in_progress", self.contract()["status"])


class InterruptedCommitsRetryTheSameCommand(S4Case):
    """中途断掉之后重跑同一条命令：不回滚、不另记进度，从磁盘现状认出做到哪了。"""

    def test_retry_after_the_overwrite_succeeds(self) -> None:
        self.ready_to_commit()
        kept = self.backup_upstream()
        self.design.write_text(DRAFT, encoding="utf-8")
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual([kept], self.backups(), "重试又写了一份备份")
        self.assertEqual(kept.relative_to(self.feature_root).as_posix(), result["backup"])
        self.assertEqual(UPSTREAM_AR, kept.read_text(encoding="utf-8"),
                         "重试把备份改掉了——上游原话只在那里还找得到")

    def test_retry_after_an_edited_draft_succeeds(self) -> None:
        """断点之后模型又改了一句提取稿：上游原话还在备份里，这一笔仍是提交自己写的。

        只认「候选一个字节没变」的话，改过稿就走非重试判据，自己上一次写下的覆盖被
        判成材料变化，报错还指路 `round`——而 `round` 在未收口态照常开新一轮，把半成品
        候选登记成 AR 材料。
        """
        self.ready_to_commit()
        kept = self.backup_upstream()
        self.design.write_text(DRAFT, encoding="utf-8")
        changed = DRAFT.replace("端侧承载签约入口与状态展示。", "断点之后又改了一句。")
        self.write_draft(changed)
        rounds_before = len(self.contract()["rounds"])
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual([kept], self.backups())
        self.assertEqual(changed, self.design.read_text(encoding="utf-8"),
                         "提交上去的该是改过的那一份")
        self.assertEqual(rounds_before, len(self.contract()["rounds"]),
                         "自己写下的那一笔差异被读成材料变化，开出了新一轮")

    def test_a_half_written_design_is_still_recoverable(self) -> None:
        """覆盖写到一半断掉：盘上那一份既不是原输入也不是完整候选，重跑仍要能收口。"""
        self.ready_to_commit()
        self.backup_upstream()
        self.design.write_text(DRAFT[: len(DRAFT) // 2], encoding="utf-8")
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual(DRAFT, self.design.read_text(encoding="utf-8"))

    def test_retry_without_a_backup_refuses(self) -> None:
        """覆盖发生了、上游那一份却没有备份：这份 AR 的来历说不清，不能当自己的写入放过。"""
        self.ready_to_commit()
        self.design.write_text(DRAFT, encoding="utf-8")     # 只覆盖，没备份
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("来历", proc.stderr)
        self.assertEqual("in_progress", self.contract()["status"])

    def test_an_unrelated_backup_does_not_count_as_this_input(self) -> None:
        """`.backups/local/` 里别的内容不是本次被覆盖的那一份：按内容认，不按文件在不在认。"""
        self.ready_to_commit()
        self.backup_upstream("# 很早以前的另一份\n")
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        texts = [p.read_text(encoding="utf-8") for p in self.backups()]
        self.assertIn(UPSTREAM_AR, texts, "被覆盖的上游那一份没进备份")
        self.assertEqual(UPSTREAM_AR, (self.feature_root / result["backup"])
                         .read_text(encoding="utf-8"))


class OnlyRealUpstreamInputIsBackedUp(S4Case):
    """备份的是上游给进来的东西——空骨架与自己上一轮的提取稿都不是。"""

    def test_the_empty_skeleton_is_not_backed_up(self) -> None:
        self.design.unlink()                       # 让 init 落它自己的空骨架
        self.ready_to_commit()
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertIsNone(result["backup"], "空骨架被当成上游输入备份了")
        self.assertEqual([], self.backups())

    def test_a_new_round_does_not_back_up_its_own_extract(self) -> None:
        """第二轮由别的材料开出、AR 没换：被覆盖的是上一轮的提取稿，不再备份一份派生稿。"""
        self.second_round_ready()
        result = self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertIsNone(result["backup"], "第二轮把自己上一轮的提取稿当成了上游输入")
        self.assertEqual(1, len(self.backups()))
        self.assertEqual(UPSTREAM_AR, self.backups()[0].read_text(encoding="utf-8"))

    def test_after_reopen_with_nothing_changed_the_next_step_is_to_close_again(self) -> None:
        """范围与材料都没变：重开之后下一步就是重新收口——不是重走关卡，也不是直接去登记。"""
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        result = self.ok("reopen")
        self.assertEqual("run_complete", result.get("next"), result)
        self.assertIn("complete", result.get("action", ""))


class PrecheckFailuresChangeNothing(S4Case):
    """预检不通过时，输入、基准与流程状态一个字节都不动。"""

    def assert_untouched(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertEqual(UPSTREAM_AR, self.design.read_text(encoding="utf-8"))
        self.assertEqual("in_progress", self.contract()["status"])
        self.assertEqual([], self.backups())

    def test_a_missing_candidate_says_where_to_write_it(self) -> None:
        self.ready_to_commit(with_draft=False)
        proc = self.commit()
        self.assert_untouched(proc)
        self.assertIn("design-draft.md", proc.stderr)

    def test_no_from_argument_refuses(self) -> None:
        self.ready_to_commit()
        proc = self.flow("complete")
        self.assert_untouched(proc)
        self.assertIn("--from", proc.stderr)

    def test_a_candidate_outside_the_feature_refuses(self) -> None:
        self.ready_to_commit()
        outside = self.root / "elsewhere.md"
        outside.write_text(DRAFT, encoding="utf-8")
        self.assert_untouched(self.commit(str(outside)))

    def test_the_untouched_skeleton_is_not_an_extraction(self) -> None:
        """交上来的还是 init 落的空骨架：提取根本没写，不能当提取稿收下。"""
        self.design.unlink()
        self.ready_to_commit(with_draft=False)
        self.write_draft(self.design.read_text(encoding="utf-8"))
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("空骨架", proc.stderr)
        self.assertEqual("in_progress", self.contract()["status"])

    def test_a_broken_five_section_shape_refuses(self) -> None:
        self.ready_to_commit(with_draft=False)
        self.write_draft("# AR90001\n\n## 1 简介\n\n只写了一段。\n")
        proc = self.commit()
        self.assert_untouched(proc)
        self.assertIn("五段", proc.stderr)

    def test_headings_inside_a_fence_do_not_count(self) -> None:
        """围栏里的标题是被引用的样例，不是本文的段。"""
        fenced = ("# AR90001\n\n```markdown\n## 1 简介\n## 2 需求分析\n"
                  "## 3 SE 方案摘要\n## 4 上游索引\n## 5 上游已声明线索\n```\n")
        self.ready_to_commit(with_draft=False)
        self.write_draft(fenced)
        self.assert_untouched(self.commit())

    def test_an_unsettled_scope_still_blocks_the_commit(self) -> None:
        """范围没定就提交：拦的判据与 `status` 说的是同一个。"""
        self.ok("init")
        self.ok("round")
        self.write_draft()
        proc = self.commit()
        self.assert_untouched(proc)
        self.assertIn("范围", proc.stderr)


class TheFinalSaveFailureStillRecovers(S4Case):
    """materials 已刷新、流程契约未保存的断点：重跑同一条命令仍能收口。

    保存是提交的最后一步，它失败时磁盘上是「清单新基准、流程旧基准」的中间态。
    重试要凭被覆盖那一份的身份认出它——把 AR 换回那一版还能复现旧基准，
    就证明除自己提交外材料未变，直接补上这次保存；同窗口里别的材料变了仍要拦。
    """

    def fail_the_final_save(self) -> subprocess.CompletedProcess:
        # 真实失败：流程契约文件置为只读，最后那笔保存以 PermissionError 落败
        flow_path = self.src / "story-flow.json"
        flow_path.chmod(stat.S_IREAD)
        try:
            proc = self.commit()
        finally:
            flow_path.chmod(stat.S_IWRITE)
        self.assertEqual(1, proc.returncode)
        self.assertIn("已完成", proc.stderr, "保存失败也要报清哪些写入已完成")
        self.assertEqual("in_progress", self.contract()["status"])
        return proc

    def test_retry_after_the_final_save_failure_completes(self) -> None:
        self.ready_to_commit()
        self.fail_the_final_save()
        rounds_before = len(self.contract()["rounds"])
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual(1, len(self.backups()), "恢复又写了一份备份")
        self.assertEqual(UPSTREAM_AR, self.backups()[0].read_text(encoding="utf-8"),
                         "恢复不得改掉备份——上游原话只在那里")
        self.assertEqual(DRAFT, self.design.read_text(encoding="utf-8"))
        self.assertEqual(rounds_before, len(self.contract()["rounds"]),
                         "恢复不得开出新一轮")

    def test_a_real_change_in_the_same_window_still_blocks(self) -> None:
        """同窗口里 RR 真的变了：中间态不豁免，照旧拦下。"""
        self.ready_to_commit()
        self.fail_the_final_save()
        self.prd.write_text("# 产品需求\n\n背景。\n\n窗口内补的。\n", encoding="utf-8")
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("对不上", proc.stderr)
        self.assertEqual("in_progress", self.contract()["status"])

    def test_the_skeleton_case_recovers_without_a_backup(self) -> None:
        """空骨架场景的同一断点：被覆盖的是 init 落的空骨架，没有要备份的，恢复直接补登记。"""
        self.design.unlink()                       # 让 init 落它自己的空骨架
        self.ready_to_commit()
        self.fail_the_final_save()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual([], self.backups(), "空骨架被当成上游输入备份了")
        self.assertEqual(1, len(self.contract()["rounds"]), "恢复不得开出新一轮")
        self.assertEqual(DRAFT, self.design.read_text(encoding="utf-8"))

    def test_the_registered_extract_case_recovers_without_a_new_backup(self) -> None:
        """已登记提取稿场景的同一断点：被覆盖的是上一轮的提取稿，恢复不再备份派生稿。"""
        self.second_round_ready()
        self.fail_the_final_save()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", self.contract()["status"])
        self.assertEqual(1, len(self.backups()), "派生稿被当成上游输入备份了")
        self.assertEqual(2, len(self.contract()["rounds"]), "恢复不得开出新一轮")


class TheMaterialFactIsTakenOncePerTimepoint(S4Case):
    """同一条命令、同一个时点只取一份材料事实。

    重复 build 把同一批文件再哈希一遍、把收件箱再转一遍，而两次之间什么也没发生；
    更要紧的是消费者会各拿一份「现在的材料」，谁也说不清自己读的是哪一份。
    写入前后是两个**不同**的时点：提交前的现状与写入后的刷新都要有，不能互相顶替。
    """

    def count_material_reads(self) -> tuple[list, list]:
        builds, refreshes = [], []
        real_build = registry.build
        real_refresh = registry.refresh

        def counting_build(feature_root):
            builds.append(feature_root)
            return real_build(feature_root)

        def counting_refresh(feature_root):
            refreshes.append(feature_root)
            return real_refresh(feature_root)

        registry.build = counting_build
        registry.refresh = counting_refresh
        self.addCleanup(setattr, registry, "build", real_build)
        self.addCleanup(setattr, registry, "refresh", real_refresh)
        return builds, refreshes

    def test_status_asks_the_disk_once(self) -> None:
        self.ready_to_commit(with_draft=False)
        builds, refreshes = self.count_material_reads()
        cmd_status(self.feature_root)
        self.assertEqual(1, len(builds),
                         f"status 取了 {len(builds)} 次材料事实——路由、提示与输出该共用一份")
        self.assertEqual([], refreshes, "status 只读，不该刷新清单")

    def test_commit_takes_one_snapshot_before_writing_and_refreshes_after(self) -> None:
        self.ready_to_commit()
        builds, refreshes = self.count_material_reads()
        cmd_complete(self.feature_root, FEATURE, "AR/story-src/design-draft.md")
        self.assertEqual(1, len(refreshes), "写入后的刷新是另一个时点，必须仍然发生")
        # 刷新自己也要算一遍：所以写入前恰好一次 = build 比 refresh 多一次
        self.assertEqual(len(refreshes) + 1, len(builds),
                         f"提交期间取了 {len(builds)} 次材料事实，写入前应当只取一次")

    def decide_now(self, gate: str, chosen: str, scope_text: str = "") -> tuple[dict, int]:
        """在进程内记一条关卡决策——要数的是**这一条命令**里读了几次磁盘。"""
        args = argparse.Namespace(gate=gate, chosen=chosen,
                                  basis=f"用户回复：{chosen}", scope_text=scope_text)
        return cmd_decide(self.feature_root, args)

    def write_scope_options(self, options: list[dict]) -> None:
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / ".scope-options.json").write_text(
            json.dumps(options, ensure_ascii=False), encoding="utf-8")

    def first_gate_ready(self) -> None:
        self.ok("init")
        self.ok("round")
        self.gate_options("material_scope")

    def test_the_first_gate_asks_the_disk_once(self) -> None:
        self.first_gate_ready()
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("material_scope", "confirm_scope")
        self.assertEqual(0, code)
        self.assertEqual(1, len(builds), f"第一级取了 {len(builds)} 次材料事实")
        self.assertEqual([], refreshes, "记一条决策不刷新清单")

    def test_a_rejected_supply_request_asks_the_disk_once(self) -> None:
        """人说「料放进去了」而盘上什么也没有：原地驳回，同样只读一次。"""
        self.first_gate_ready()
        builds, _ = self.count_material_reads()
        result, code = self.decide_now("material_scope",
                                       MATERIAL_REQUEST_KEYS[0])
        self.assertEqual(2, code, result)
        self.assertEqual("rejected", result["outcome"])
        self.assertEqual(1, len(builds), f"驳回这一路取了 {len(builds)} 次材料事实")

    def second_gate_ready(self, options: list[dict] | None = None) -> None:
        self.first_gate_ready()
        self.ok("decide", "--gate", "material_scope", "--chosen", "confirm_scope",
                "--basis", "用户回复：现有材料就是全部")
        self.write_analysis()
        if options is not None:
            self.write_scope_options(options)
        self.ok("round")
        self.gate_options("scope_decision")

    def test_the_second_gate_asks_the_disk_once(self) -> None:
        """正常第二级：前置路由与末尾的下一步各要一次事实，它们该是同一份。"""
        self.second_gate_ready()
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("scope_decision", CARRY_ALL)
        self.assertEqual(0, code)
        self.assertEqual(1, len(builds), f"第二级取了 {len(builds)} 次材料事实")
        self.assertEqual([], refreshes)

    def test_the_third_gate_asks_the_disk_once(self) -> None:
        """第三级同一条调用路径：选项由脚本从份表生成，材料事实仍只取一次。"""
        parts = [{"seq": 1, "scope": "本单承载签约入口", "depends_on": []},
                 {"seq": 2, "scope": "兄弟单承载补卡", "depends_on": [1]}]
        self.second_gate_ready(options=[
            {"key": CARRY_ALL, "label": "按当前范围整体承载"},
            {"key": "by_capability", "label": "按能力切两份", "parts": parts},
        ])
        self.ok("decide", "--gate", "scope_decision", "--chosen", "by_capability",
                "--basis", "用户回复：按能力切")
        (self.src / ".split-parts.json").write_text(json.dumps(
            [{"seq": 1, "carrier": FEATURE, "scope": "本单承载签约入口", "depends_on": []},
             {"seq": 2, "carrier": "AR90002", "scope": "兄弟单承载补卡", "depends_on": [1]}],
            ensure_ascii=False), encoding="utf-8")
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("split_carrier", "1")
        self.assertEqual(0, code)
        self.assertEqual(1, len(builds), f"第三级取了 {len(builds)} 次材料事实")
        self.assertEqual([], refreshes)


class RegistrationRunsTheRealChecker(S4Case):
    """成文态登记的结论，就是 `story-build` 这一次的结论。

    守恒判据在 story-build 那边，登记这一步只负责把它跑起来再记。跑不起来与没通过
    必须分得开：公共 CLI 由脚本自己的位置定位，数错一层目录的表现是 spawn 失败——
    那时报出来的是 node 找不到模块，而「哪一章不合格」一个字也看不到，
    于是「登记被拦住了」与「检查压根没跑」在输出上同形。
    """

    def test_the_checker_runs_and_its_own_finding_is_the_verdict(self) -> None:
        self.ready_to_commit()
        self.ok("complete", "--from", "AR/story-src/design-draft.md")
        (self.feature_root / "AR" / "story.md").write_text(
            "# 随手写的一行\n", encoding="utf-8")
        proc = self.flow("story")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertNotIn("Cannot find module", error,
                         "node 找不到 story-build.mjs——公共 CLI 的定位错了")
        self.assertIn("[story-build]", error,
                      "登记没把 story-build 的结论带出来，只报了自己跑不通")
        self.assertNotIn("story", self.contract(), "检查没通过却记了成文态")


if __name__ == "__main__":
    unittest.main()
