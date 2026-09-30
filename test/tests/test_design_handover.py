"""需求交给设计：关联设计对象（`bind-design`）与冻结设计输入（`complete`）。

`AR/design.md` 是上游给进来的原件，提交不覆盖它：候选提取稿作为派生分析进冻结集合，采用的原件、图片与
真实人签一起按原始字节冻结在 `AR/story-src/inputs/<版本>/`，经原生来源检查后登记 `input`。
这一份锁：冻结的内容与版本身份、复用与换输入、闭包与人签的拒绝、失败不改已登记的输入、提交前的前置，
以及同一时点只取一份材料事实。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT, REPO_ROOT
from flow_steps import answer, ensure_framework, write_gaps

STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.decisions import cmd_decide  # noqa: E402
from flow.inputs import MATERIAL_REQUEST_KEYS  # noqa: E402
from flow.lifecycle import cmd_status  # noqa: E402
from flow.state import CARRY_ALL  # noqa: E402
from flow.submission import cmd_complete  # noqa: E402
from materials import registry  # noqa: E402

FEATURE = "AR90001"
UPSTREAM_AR = ("# AR90001 上游预填\n\n## 上游先写下的几条\n\n"
               "- 判定与扣款都在服务端，端侧只做签约入口。\n")
PRD = "# 产品需求\n\n背景。签约流程见下图：\n\n![签约流程](../assets/flow.svg)\n"
DRAFT = (
    "# AR90001 自动充值 — 开发需求（AR）\n\n"
    "## 1 简介\n\n### 1.1 需求介绍\n\n端侧承载签约入口与状态展示。\n\n"
    "## 2 需求分析\n\n### 2.1 场景与功能点\n\n签约、解约、状态查看。\n\n"
    "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\n判定在服务端。\n\n"
    "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
    "## 5 上游已声明线索\n\n无。\n")
DRAFT_REL = "AR/story-src/design-draft.md"
INPUT_REL = "AR/story-src/design-input.json"


class HandoverCase(unittest.TestCase):
    """一份接入 demo Framework 的新工程，跑真脚本走到「范围已定」，再各自测交给设计。"""

    feature = FEATURE

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        ensure_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / self.feature
        for part in ("RR", "SR", "AR", "assets"):
            (self.feature_root / part).mkdir(parents=True)
        self.prd = self.feature_root / "RR" / "prd.md"
        self.prd.write_text(PRD, encoding="utf-8")
        (self.feature_root / "assets" / "flow.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
        (self.feature_root / "SR" / "design.md").write_text("# 系统设计\n\n分工。\n", encoding="utf-8")
        self.design = self.feature_root / "AR" / "design.md"
        self.design.write_text(UPSTREAM_AR, encoding="utf-8")
        self.src = self.feature_root / "AR" / "story-src"

    # -- 驱动 ---------------------------------------------------------------

    def flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", self.feature, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO_ROOT))

    def ok(self, *args: str) -> dict:
        proc = self.flow(*args)
        self.assertEqual(0, proc.returncode, f"{args} 失败：{proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def refused(self, *args: str) -> str:
        proc = self.flow(*args)
        self.assertEqual(1, proc.returncode, f"{args} 应当被拒：{proc.stdout}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])["error"]

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def write_analysis(self) -> None:
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / ".positioning.json").write_text(json.dumps(
            {"scope_source": "user_stated", "scope_text": "本 AR 承载自动充值签约与管理", "sr_related_ars": []},
            ensure_ascii=False), encoding="utf-8")
        (self.src / ".scope-options.json").write_text(json.dumps(
            [{"key": CARRY_ALL, "label": "按当前范围整体承载"}], ensure_ascii=False), encoding="utf-8")

    def ready(self, *, bind: bool = True) -> None:
        """S1–S3 走完、提取稿写好、关联好设计对象，停在「可以交给设计」。"""
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.write_analysis()
        self.ok("round")
        answer(self.ok, "scope_decision", "1")
        (self.src / "design-draft.md").write_text(DRAFT, encoding="utf-8")
        if bind:
            self.ok("bind-design", "--component", "wallet-home", "--blueprint", self.feature)

    def scope_ask(self) -> str:
        return next(g["ask_id"] for r in self.contract()["rounds"] for g in r["gates"]
                    if g["gate"] == "scope_decision" and g["outcome"] == "accepted")

    def write_input(self, *, adopted=None, ids=None, items=None) -> None:
        body = {
            "adopted": adopted if adopted is not None else ["RR/prd.md", "assets/flow.svg", "AR/design.md"],
            "human_decision_ids": ids if ids is not None else [self.scope_ask()],
            "scope_items": items if items is not None else [
                {"item_id": "request-main", "kind": "requirement", "source_path": "RR/prd.md",
                 "authority": {"owner": "需求负责人", "formality": "formal_requirement"}},
                {"item_id": "scope-ruling", "kind": "invariant", "source_path": "AR/story-src/human-decisions.json",
                 "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}],
        }
        (self.src / "design-input.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    def commit(self) -> subprocess.CompletedProcess:
        return self.flow("complete", "--from", DRAFT_REL, "--input", INPUT_REL)

    def versions(self) -> list[Path]:
        root = self.src / "inputs"
        return sorted(p for p in root.iterdir() if not p.name.startswith(".")) if root.is_dir() else []


class TheDesignObjectIsBoundOnce(HandoverCase):
    def test_the_first_binding_is_written_and_the_same_one_changes_nothing(self) -> None:
        self.ready(bind=False)
        out = self.ok("bind-design", "--component", "wallet-home", "--blueprint", FEATURE)
        self.assertEqual({"component_id": "wallet-home", "blueprint_id": FEATURE}, out["design_binding"])
        before = (self.src / "story-flow.json").read_bytes()
        self.assertFalse(self.ok("bind-design", "--component", "wallet-home", "--blueprint", FEATURE)["bound"])
        self.assertEqual(before, (self.src / "story-flow.json").read_bytes(), "同值重复关联改了契约")

    def test_another_binding_is_refused(self) -> None:
        self.ready()
        self.assertIn("不改绑", self.refused("bind-design", "--component", "wallet-home", "--blueprint", "other"))

    def test_an_unsafe_identifier_is_refused_by_the_native_rule(self) -> None:
        self.ready(bind=False)
        self.assertIn("blueprint_id_invalid", self.refused("bind-design", "--component", "wallet-home", "--blueprint", "../x"))
        self.assertNotIn("design_binding", self.contract())

    def test_an_existing_blueprint_of_another_component_is_refused(self) -> None:
        self.ready(bind=False)
        fixture = REPO_ROOT / "test" / "fixtures" / "blueprint" / "wallet-balance-refresh" / "doc" / "features"
        shutil.copytree(fixture / "wallet-balance-refresh", self.root / "doc" / "features" / "wallet-balance-refresh")
        error = self.refused("bind-design", "--component", "not-its-component", "--blueprint", "wallet-balance-refresh")
        self.assertIn("blueprint_component_mismatch", error)


class TheInputIsFrozenForTheDesign(HandoverCase):
    """冻结的是本次交给设计的全部依据；上游原件原样不动。"""

    def committed(self) -> dict:
        self.ready()
        self.write_input()
        proc = self.commit()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def test_the_upstream_design_is_never_overwritten(self) -> None:
        self.committed()
        self.assertEqual(UPSTREAM_AR, self.design.read_text(encoding="utf-8"))
        self.assertFalse((self.feature_root / ".backups").exists(), "提交还在备份并覆盖上游 AR")

    def test_the_version_holds_every_file_by_its_raw_bytes_and_role(self) -> None:
        out = self.committed()
        [version] = self.versions()
        snapshot_path = version / "snapshot.json"
        self.assertEqual(out["input"]["snapshot_ref"],
                         snapshot_path.relative_to(self.root).as_posix())
        self.assertEqual(hashlib.sha256(snapshot_path.read_bytes()).hexdigest(), out["input"]["snapshot_sha256"])
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        roles = {row["path"]: row["role"] for row in snapshot["files"]}
        self.assertEqual({"RR/prd.md": "original", "assets/flow.svg": "image", "AR/design.md": "original",
                          DRAFT_REL: "extracted_analysis", "AR/story-src/human-decisions.json": "human_record"}, roles)
        for row in snapshot["files"]:
            data = (version / "files" / row["path"]).read_bytes()
            self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest(), row["path"])
        body = {k: v for k, v in snapshot.items() if k != "observed_at"}
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(version.name, hashlib.sha256(canonical).hexdigest(), "版本号不是快照主体的摘要")

    def test_the_human_record_is_exported_from_the_real_gate(self) -> None:
        self.committed()
        [version] = self.versions()
        exported = json.loads((version / "files" / "AR/story-src/human-decisions.json").read_text(encoding="utf-8"))
        gate = next(g for r in self.contract()["rounds"] for g in r["gates"] if g["ask_id"] == self.scope_ask())
        [row] = exported["decisions"]
        self.assertEqual((gate["reply"], gate["chosen"], gate["at"]), (row["reply"], row["chosen"], row["at"]))
        self.assertFalse((self.src / "human-decisions.json").exists(), "人签导出写进了工作区")

    def test_a_system_requirement_gets_a_materialization_pointing_into_the_version(self) -> None:
        self.committed()
        [version] = self.versions()
        doc = json.loads((version / "materialization.json").read_text(encoding="utf-8"))
        self.assertEqual(("requirement-source-materialization@1", FEATURE), (doc["artifact"], doc["blueprint_id"]))
        prefix = version.relative_to(self.root).as_posix() + "/files/"
        self.assertTrue(all(item["source_ref"].startswith(prefix) for item in doc["items"]))
        self.assertEqual("recorded_user_reply", doc["items"][1]["provenance"]["extraction_method"])

    def test_after_the_commit_the_state_waits_for_the_design(self) -> None:
        self.committed()
        status = self.ok("status")
        self.assertEqual(("complete", "waiting_for_design", "design_blueprint"),
                         (status["status"], status["state"], status["next"]))

    def test_the_same_input_again_reuses_the_version_and_changes_nothing(self) -> None:
        self.committed()
        before = (self.src / "story-flow.json").read_bytes()
        again = json.loads(self.commit().stdout.split("\n")[-2])
        self.assertFalse(again["committed"])
        self.assertEqual(before, (self.src / "story-flow.json").read_bytes())
        self.assertEqual(1, len(self.versions()))

    def test_another_input_needs_reopen_and_the_old_version_stays(self) -> None:
        self.committed()
        self.write_input(adopted=["RR/prd.md", "assets/flow.svg"])
        proc = self.commit()
        self.assertIn("reopen", json.loads(proc.stdout[proc.stdout.index("{"):])["error"])
        self.ok("reopen")
        answer(self.ok, "scope_decision", "1")
        self.write_input(adopted=["RR/prd.md", "assets/flow.svg"])
        self.assertEqual(0, self.commit().returncode)
        self.assertEqual(2, len(self.versions()), "换输入删掉或覆写了已被引用的旧版本")
        self.assertEqual("waiting_for_design", self.ok("status")["state"])


class ALocalRequirementHasNoManifest(HandoverCase):
    feature = "local-autocharge"

    def test_the_items_are_checked_but_no_materialization_is_written(self) -> None:
        self.ready()
        self.write_input()
        out = self.ok("complete", "--from", DRAFT_REL, "--input", INPUT_REL)
        [version] = self.versions()
        self.assertFalse((version / "materialization.json").exists())
        self.assertEqual(2, len(out["design_entry"]["current_scope_items"]))


class WhatCannotBeFrozenIsRefused(HandoverCase):
    """冻结不成立时不登记：候选与诊断留在原处，已登记的输入不变。"""

    def test_an_image_the_original_references_must_be_adopted(self) -> None:
        self.ready()
        self.write_input(adopted=["RR/prd.md"])
        error = json.loads(self.commit().stdout)["error"]
        self.assertIn("assets/flow.svg", error)
        self.assertNotIn("input", self.contract())

    def test_a_forged_human_decision_is_refused(self) -> None:
        self.ready()
        self.write_input(ids=["deadbeef"])
        self.assertIn("deadbeef", json.loads(self.commit().stdout)["error"])
        self.assertEqual([], self.versions())

    def test_something_not_confirmed_this_round_cannot_be_adopted(self) -> None:
        self.ready()
        (self.src / "notes.md").write_text("草稿\n", encoding="utf-8")
        self.write_input(adopted=["RR/prd.md", "assets/flow.svg", "AR/story-src/notes.md"])
        self.assertIn("不是本轮确认的材料", json.loads(self.commit().stdout)["error"])

    def test_a_damaged_version_is_not_reused(self) -> None:
        self.ready()
        self.write_input()
        self.assertEqual(0, self.commit().returncode)
        [version] = self.versions()
        (version / "files" / "RR" / "prd.md").write_text("被改过\n", encoding="utf-8")
        self.ok("reopen")
        answer(self.ok, "scope_decision", "1")
        self.assertIn("已损坏", json.loads(self.commit().stdout)["error"])

    def test_the_native_source_check_decides_and_nothing_is_registered(self) -> None:
        """原生对来源条目的判定（这里是 item_id 不合原生的稳定标识）不过：冻结版本留下，输入不登记。"""
        self.ready()
        self.write_input(items=[{"item_id": "需求 主条", "kind": "requirement", "source_path": "RR/prd.md",
                                 "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}])
        proc = self.commit()
        self.assertEqual(1, proc.returncode)
        self.assertIn("原生来源检查没过", json.loads(proc.stdout)["error"])
        self.assertNotIn("input", self.contract())
        self.assertEqual(1, len(self.versions()), "冻结版本应留在原处供诊断")


class PrecheckFailuresChangeNothing(HandoverCase):
    """提交前的前置不满足：一个字节都不写。"""

    def assert_untouched(self, *args: str, says: str) -> None:
        before = (self.src / "story-flow.json").read_bytes()
        proc = self.flow("complete", *args)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn(says, json.loads(proc.stdout)["error"])
        self.assertEqual(before, (self.src / "story-flow.json").read_bytes())
        self.assertEqual([], self.versions())

    def test_without_a_binding_it_says_bind_first(self) -> None:
        self.ready(bind=False)
        self.write_input()
        self.assert_untouched("--from", DRAFT_REL, "--input", INPUT_REL, says="bind-design")

    def test_a_missing_candidate_says_where_to_write_it(self) -> None:
        self.ready()
        (self.src / "design-draft.md").unlink()
        self.assert_untouched("--from", DRAFT_REL, says="design-draft.md")

    def test_no_from_argument_refuses(self) -> None:
        self.ready()
        self.assert_untouched(says="--from")

    def test_a_candidate_outside_the_feature_refuses(self) -> None:
        self.ready()
        outside = self.root / "draft.md"
        outside.write_text(DRAFT, encoding="utf-8")
        self.assert_untouched("--from", str(outside), says="需求目录外")

    def test_the_untouched_skeleton_is_not_an_extraction(self) -> None:
        self.ready()
        sys.path.insert(0, str(STORY_SCRIPTS))
        from flow.inputs import ar_design_skeleton, read_ids  # noqa: PLC0415
        (self.src / "design-draft.md").write_text(ar_design_skeleton(read_ids(self.feature_root, FEATURE)),
                                                  encoding="utf-8")
        self.assert_untouched("--from", DRAFT_REL, says="空骨架")

    def test_a_broken_five_section_shape_refuses(self) -> None:
        self.ready()
        (self.src / "design-draft.md").write_text("# x\n\n## 1 简介\n\nx\n", encoding="utf-8")
        self.assert_untouched("--from", DRAFT_REL, says="五段结构")

    def test_headings_inside_a_fence_do_not_count(self) -> None:
        self.ready()
        fenced = "```\n" + DRAFT + "```\n"
        (self.src / "design-draft.md").write_text(fenced, encoding="utf-8")
        self.assert_untouched("--from", DRAFT_REL, says="五段结构")

    def test_an_unsettled_scope_still_blocks(self) -> None:
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.ok("bind-design", "--component", "wallet-home", "--blueprint", FEATURE)
        (self.src / "design-draft.md").write_text(DRAFT, encoding="utf-8")
        self.write_input(ids=[])
        self.assert_untouched("--from", DRAFT_REL, "--input", INPUT_REL, says="范围尚未定")

    def test_a_pending_original_in_the_inbox_blocks(self) -> None:
        self.ready()
        self.write_input()
        (self.feature_root / "inbox" / "补充说明.md").write_text("# 补充\n\n新内容。\n", encoding="utf-8")
        self.assert_untouched("--from", DRAFT_REL, "--input", INPUT_REL, says="收件箱")

    def test_a_material_changed_after_the_round_blocks(self) -> None:
        self.ready()
        self.write_input()
        self.prd.write_text(PRD + "\n补了一句。\n", encoding="utf-8")
        self.assert_untouched("--from", DRAFT_REL, "--input", INPUT_REL, says="材料在这一轮登记之后又变了")


class TheMaterialFactIsTakenOncePerTimepoint(HandoverCase):
    """同一条命令、同一个时点只取一份材料事实：消费者各拿一份「现在的材料」时，谁也说不清读的是哪一份。"""

    def count_material_reads(self) -> tuple[list, list]:
        builds, refreshes = [], []
        real_build, real_refresh = registry.build, registry.refresh

        def counting_build(feature_root):
            builds.append(feature_root)
            return real_build(feature_root)

        def counting_refresh(feature_root):
            refreshes.append(feature_root)
            return real_refresh(feature_root)

        registry.build, registry.refresh = counting_build, counting_refresh
        self.addCleanup(setattr, registry, "build", real_build)
        self.addCleanup(setattr, registry, "refresh", real_refresh)
        return builds, refreshes

    def test_status_asks_the_disk_once(self) -> None:
        self.ready()
        builds, refreshes = self.count_material_reads()
        cmd_status(self.feature_root)
        self.assertEqual(1, len(builds), f"status 取了 {len(builds)} 次材料事实——路由、提示与输出该共用一份")
        self.assertEqual([], refreshes, "status 只读，不该刷新清单")

    def test_commit_takes_one_snapshot_and_writes_no_material(self) -> None:
        """提交只冻结、不改材料：取一次现状，不刷新清单。"""
        self.ready()
        self.write_input()
        builds, refreshes = self.count_material_reads()
        cmd_complete(self.feature_root, self.root, FEATURE, DRAFT_REL, INPUT_REL)
        self.assertEqual((1, []), (len(builds), refreshes))

    def decide_now(self, gate: str, chosen: str) -> tuple[dict, int]:
        ask = json.loads((self.src / ".ask.json").read_text(encoding="utf-8"))
        args = argparse.Namespace(gate=gate, chosen=chosen, ask=ask["ask_id"],
                                  reply=f"用户回复：{chosen}", meeting=None, item=None)
        return cmd_decide(self.feature_root, args)

    def first_gate_ready(self) -> None:
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        self.ok("status")

    def test_the_first_gate_asks_the_disk_once(self) -> None:
        self.first_gate_ready()
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("material_scope", "confirm_scope")
        self.assertEqual((0, 1, []), (code, len(builds), refreshes))

    def test_a_rejected_supply_request_asks_the_disk_once(self) -> None:
        """人说「料放进去了」而盘上什么也没有：原地驳回，同样只读一次。"""
        self.first_gate_ready()
        builds, _ = self.count_material_reads()
        result, code = self.decide_now("material_scope", MATERIAL_REQUEST_KEYS[0])
        self.assertEqual((2, "rejected", 1), (code, result["outcome"], len(builds)))

    def second_gate_ready(self, options: list[dict] | None = None) -> None:
        self.first_gate_ready()
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.write_analysis()
        if options is not None:
            (self.src / ".scope-options.json").write_text(json.dumps(options, ensure_ascii=False), encoding="utf-8")
        self.ok("round")
        self.ok("status")

    def test_the_second_gate_asks_the_disk_once(self) -> None:
        self.second_gate_ready()
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("scope_decision", CARRY_ALL)
        self.assertEqual((0, 1, []), (code, len(builds), refreshes))

    def test_the_third_gate_asks_the_disk_once(self) -> None:
        parts = [{"seq": 1, "scope": "本单承载签约入口", "depends_on": []},
                 {"seq": 2, "scope": "兄弟单承载补卡", "depends_on": [1]}]
        self.second_gate_ready(options=[
            {"key": CARRY_ALL, "label": "按当前范围整体承载"},
            {"key": "by_capability", "label": "按能力切两份", "parts": parts},
        ])
        answer(self.ok, "scope_decision", "按能力切两份")
        (self.src / ".split-parts.json").write_text(json.dumps(
            [{"seq": 1, "carrier": FEATURE, "scope": "本单承载签约入口", "depends_on": []},
             {"seq": 2, "carrier": "AR90002", "scope": "兄弟单承载补卡", "depends_on": [1]}],
            ensure_ascii=False), encoding="utf-8")
        self.ok("status")
        builds, refreshes = self.count_material_reads()
        _, code = self.decide_now("split_carrier", "1")
        self.assertEqual((0, 1, []), (code, len(builds), refreshes))


class RegistrationRunsTheRealChecker(HandoverCase):
    """成文态登记的结论，就是 `story-build` 这一次的结论：跑不起来与没通过必须分得开。"""

    def test_the_checker_runs_and_its_own_finding_is_the_verdict(self) -> None:
        self.ready()
        self.write_input()
        self.assertEqual(0, self.commit().returncode)
        (self.feature_root / "AR" / "story.md").write_text("# 随手写的一行\n", encoding="utf-8")
        proc = self.flow("story")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertNotIn("Cannot find module", error, "node 找不到 story-build.mjs——公共 CLI 的定位错了")
        self.assertIn("[story-build]", error, "登记没把 story-build 的结论带出来，只报了自己跑不通")
        self.assertEqual("complete", self.contract()["status"], "检查没通过却记了成文态")


if __name__ == "__main__":
    unittest.main()
