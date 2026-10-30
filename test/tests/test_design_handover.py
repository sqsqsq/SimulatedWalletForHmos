"""需求交给设计：范围定了直接进原生 component-design，蓝图与需求同根，需求条目引 `sources/` 的材料版本。

这一份锁：范围定了之后路由按原生蓝图派生位置，没有交接命令、不写契约；`import_sources.py --scope` 按材料索引
补齐需求条目的来源——系统来源另写原生物化信封并过原生检查，本地来源不落 provider 文件，引了没登记的文件拒绝且不写盘；
蓝图的需求条目采用了本需求的材料版本才进成文；设计开始之后材料再变只登记进本轮，设计开始之前照常开新轮；
旧 schema 的契约明确拒绝；同一时点只取一份材料事实；成文登记跑真的检查器。
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
import design_kit
from flow_steps import answer, ensure_framework, write_gaps

STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"
FLOW = STORY_SCRIPTS / "story_flow.py"
IMPORT = STORY_SCRIPTS / "import_sources.py"
ACCESS = DEV_EXT / "hooks" / "shared" / "framework-access.mjs"

sys.path.insert(0, str(STORY_SCRIPTS))
from flow.decisions import cmd_decide  # noqa: E402
from flow.inputs import MATERIAL_REQUEST_KEYS  # noqa: E402
from flow.lifecycle import cmd_status  # noqa: E402
from flow.state import CARRY_ALL  # noqa: E402
from materials import importer, registry  # noqa: E402

FEATURE = "AR90001"
PRD = "# 产品需求\n\n## 背景\n\n签约流程见下图：\n\n![签约流程](../flow-v1/flow.svg)\n"
AUTHORITY = {"owner": "需求负责人", "formality": "formal_requirement"}


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
        (self.feature_root / "AR").mkdir(parents=True)
        self.src = self.feature_root / "AR" / "story-src"
        self.seed({"RR/prd.md": (PRD, "RR"), "assets/flow.svg": ("<svg xmlns='http://www.w3.org/2000/svg'/>\n", "UX"),
                   "SR/design.md": ("# 系统设计\n\n分工。\n", "SR")})

    def seed(self, files: dict[str, tuple[str, str]], receipt: dict | None = None) -> None:
        """经真实导入器导成材料版本，各来源最新版本的原件路径存成属性。给了 `receipt` 时这批件是一次系统取材。"""
        inbox = self.feature_root / "sources" / "inbox"
        batch = inbox / "fetch-1" if receipt else inbox
        classify = {}
        for rel, (text, cls) in files.items():
            (batch / rel).parent.mkdir(parents=True, exist_ok=True)
            (batch / rel).write_text(text, encoding="utf-8")
            classify[rel] = cls
        if receipt:
            (batch / ".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        else:
            (inbox / ".classify.json").write_text(json.dumps(classify), encoding="utf-8")
        importer.cmd_import(self.feature_root, self.root)
        latest = {s["source_id"]: s["versions"][-1]["original"]["path"] for s in registry.read(self.feature_root)["sources"]}
        self.prd_rel = latest.get("local:RR/prd.md")
        self.flow_rel = latest.get("local:assets/flow.svg")

    # -- 驱动 ---------------------------------------------------------------

    def flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", self.feature, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO_ROOT))

    def ok(self, *args: str) -> dict:
        proc = self.flow(*args)
        self.assertEqual(0, proc.returncode, f"{args} 失败：{proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def write_analysis(self) -> None:
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / ".positioning.json").write_text(json.dumps(
            {"scope_source": "user_stated", "scope_text": "本 AR 承载自动充值签约与管理", "sr_related_ars": []},
            ensure_ascii=False), encoding="utf-8")
        (self.src / ".scope-options.json").write_text(json.dumps(
            [{"key": CARRY_ALL, "label": "按当前范围整体承载"}], ensure_ascii=False), encoding="utf-8")

    def ready(self) -> None:
        """S1–S3 走完、范围已定：停在「交给设计」。"""
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.write_analysis()
        self.ok("round")
        answer(self.ok, "scope_decision", "1")

    def answers_rel(self) -> str:
        """人工答复的最新版本里给人读的那份。"""
        answers = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "answer")
        return answers["versions"][-1]["readable"]["path"]

    def scope(self, items: list[dict], *extra: str) -> subprocess.CompletedProcess:
        path = self.root / "scope-items.json"
        path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(IMPORT), "--feature", self.feature, "--project-root", str(self.root), "--scope", str(path), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def scoped(self, items: list[dict], *extra: str) -> dict:
        proc = self.scope(items, *extra)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def tree(self) -> dict[str, bytes]:
        features = self.root / "doc" / "features"
        return {p.relative_to(features).as_posix(): p.read_bytes() for p in features.rglob("*") if p.is_file()}


def item(source: str, item_id: str = "request-main", kind: str = "requirement") -> dict:
    return {"item_id": item_id, "kind": kind, "source": source, "authority": AUTHORITY}


class ScopeSettledGoesStraightToDesign(HandoverCase):
    """范围定了，下一步就是原生 component-design：没有交接命令，契约里不记设计关联与输入。"""

    def test_status_points_at_component_design_and_writes_nothing(self) -> None:
        self.ready()
        before = self.tree()
        status = self.ok("status")
        self.assertEqual(("waiting_for_design", "design_blueprint"), (status["state"], status["next"]))
        self.assertEqual({"blueprint_id": FEATURE, "exists": False}, status["blueprint"])
        for needle in ("component-design", f"`{FEATURE}/blueprint/`", "import_sources.py --scope"):
            self.assertIn(needle, status["action"])
        contract = self.contract()
        self.assertEqual("gathering", contract["status"])
        self.assertFalse({"input", "design_binding"} & set(contract), "契约又记了设计关联或输入")
        self.assertEqual(before, self.tree(), "status 是只读查询，却写了需求目录")

    def test_the_retired_commands_are_gone(self) -> None:
        self.ready()
        for mode in ("bind-design", "complete"):
            with self.subTest(mode=mode):
                proc = self.flow(mode)
                self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("invalid choice", proc.stderr)

    def test_an_old_contract_is_refused_with_its_schema(self) -> None:
        """旧版本的契约不迁移：明确说是哪一版、当前是哪一版。"""
        self.ready()
        old = {**self.contract(), "schema": 5, "status": "complete"}
        (self.src / "story-flow.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        proc = self.flow("status")
        self.assertEqual(1, proc.returncode)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertIn("schema 5", error)
        self.assertIn("当前 6", error)


class ScopeItemsAreFilledFromTheIndex(HandoverCase):
    """需求条目的语义模型写一次，来源路径、摘要与 provenance 由脚本按材料索引补。"""

    def test_a_local_source_gets_native_items_and_no_provider_file(self) -> None:
        self.ready()
        answers = self.answers_rel()
        out = self.scoped([item(self.prd_rel), item(answers, "scope-ruling", "invariant")])
        main, ruling = out["current_scope_items"]
        prd = self.feature_root / self.prd_rel
        self.assertEqual(f"doc/features/{FEATURE}/{self.prd_rel}", main["source_ref"])
        self.assertEqual("sha256:" + hashlib.sha256(prd.read_bytes()).hexdigest(), main["source_sha256"])
        self.assertEqual(("requirement_material", "observed", "imported_file_observation"),
                         (main["provenance"]["source_kind"], main["provenance"]["evidence_strength"],
                          main["provenance"]["extraction_method"]))
        self.assertEqual(main["source_ref"], main["provenance"]["source_ref"])
        self.assertEqual(("human_decision", "authoritative"),
                         (ruling["provenance"]["source_kind"], ruling["provenance"]["evidence_strength"]),
                         "人工答复是人的原话")
        self.assertEqual(AUTHORITY, main["authority"])
        self.assertNotIn("materialization", out)
        self.assertFalse((self.feature_root / "blueprint").exists(), "本地来源不该落 provider 文件")

    def test_a_fragment_stays_on_the_reference(self) -> None:
        self.ready()
        [main] = self.scoped([item(f"{self.prd_rel}#背景")])["current_scope_items"]
        self.assertTrue(main["source_ref"].endswith(f"{self.prd_rel}#背景"))

    def test_a_file_outside_the_index_is_refused_and_nothing_is_written(self) -> None:
        self.ready()
        before = self.tree()
        proc = self.scope([item("AR/story-src/init-analysis.md"), item(self.prd_rel, "other")])
        self.assertEqual(1, proc.returncode)
        self.assertIn("不是材料索引登记的版本文件", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.tree())

    def test_a_bad_shape_is_named_item_by_item(self) -> None:
        self.ready()
        proc = self.scope([{"item_id": "x", "kind": "story", "source": self.prd_rel}])
        error = json.loads(proc.stdout)["error"]
        self.assertIn("kind 取", error)
        self.assertIn("authority 要有 owner 与 formality", error)


class SystemSourcesGetTheNativeEnvelope(HandoverCase):
    """需求系统取得的来源：同一组条目另写成原生来源物化信封，放在需求的 blueprint/ 里并过原生检查。"""

    def seed_system(self) -> str:
        self.seed({"RR-prd.md": ("# 系统上的产品需求\n\n签约。\n", "RR")},
                  receipt={"reqNo": FEATURE, "rrNo": "RR90001",
                           "items": [{"name": "RR-prd.md", "role": "RR", "ticket": "RR90001", "title": "产品需求",
                                      "status": "fetched"}]})
        source = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "system")
        return source["versions"][-1]["original"]["path"]

    def test_the_envelope_is_written_once_and_checked_natively(self) -> None:
        system = self.seed_system()
        self.ready()
        out = self.scoped([item(system)], "--component", "wallet-home")
        envelope = self.feature_root / "blueprint" / "requirement-source-materialization.json"
        self.assertEqual(f"doc/features/{FEATURE}/blueprint/requirement-source-materialization.json", out["materialization"])
        doc = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(("requirement-source-materialization@1", FEATURE, "wallet-home"),
                         (doc["artifact"], doc["blueprint_id"], doc["component_id"]))
        self.assertEqual(out["current_scope_items"], doc["items"])
        self.assertTrue(doc["items"][0]["provenance"]["source_revision"].startswith("system:RR:RR90001@v"))
        before = envelope.stat().st_mtime_ns
        self.scoped([item(system)], "--component", "wallet-home")
        self.assertEqual(before, envelope.stat().st_mtime_ns, "同一组条目重跑不该重写信封")

    def test_without_a_blueprint_the_component_must_be_given(self) -> None:
        system = self.seed_system()
        self.ready()
        proc = self.scope([item(system)])
        self.assertEqual(1, proc.returncode)
        self.assertIn("--component", json.loads(proc.stdout)["error"])
        self.assertFalse((self.feature_root / "blueprint").exists())

    def test_an_existing_blueprint_decides_the_component(self) -> None:
        system = self.seed_system()
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        doc = self.scoped([item(system)])
        self.assertTrue(doc["materialization"])
        proc = self.scope([item(system)], "--component", "wallet-other")
        self.assertIn(f"归属组件 {design_kit.COMPONENT}", json.loads(proc.stdout)["error"])


class TheDesignAdoptsThisRequirement(HandoverCase):
    """成文按的蓝图要真的采用了本需求的来源：准入、标识对得上还不够，需求条目要指向本需求已导入的材料版本。"""

    SOURCE = """
    const [module, root, feature] = process.argv.slice(1);
    const { designSource } = await import(module);
    const ctx = { projectRoot: root, args: { feature }, featureRoot: `${root}/doc/features/${feature}`,
                  flowPath: `${root}/doc/features/${feature}/AR/story-src/story-flow.json` };
    process.stdout.write(JSON.stringify(designSource(ctx).problems));
    """

    def source_problems(self) -> list[str]:
        module = (STORY_SCRIPTS / "story" / "design-source.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", self.SOURCE, module, str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_blueprint_adopting_this_requirement_is_ready_to_write(self) -> None:
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        before = self.tree()
        self.assertEqual(("ready_to_write", "story_skeleton"), (self.ok("status")["state"], self.ok("status")["next"]))
        self.assertEqual(before, self.tree(), "status 是只读查询，却写了需求或蓝图")
        self.assertEqual([], self.source_problems())

    def test_an_unadmitted_blueprint_is_written_from_its_draft(self) -> None:
        """准入没过：成文读原生草稿，照样到成文（准入只管施工单位开工）。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        design_kit.change_blueprint(self.root, self.feature, ACCESS,
                                    "  admission:\n    status: pass\n", "  admission:\n    status: blocked\n")
        self.assertEqual("ready_to_write", self.ok("status")["state"])

    def test_a_blueprint_on_another_requirements_sources_waits_for_the_design(self) -> None:
        """蓝图的需求条目还是夹具里另一份需求的来源：等设计同步，不成文。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS, consume=False)
        status = self.ok("status")
        self.assertEqual(("waiting_for_design", "design_blueprint"), (status["state"], status["next"]))
        self.assertIn("没有采用本需求的来源", status["action"])
        [problem] = self.source_problems()
        self.assertIn(f"需求 {FEATURE} 已导入的材料版本", problem)

    def test_an_overstated_evidence_strength_is_not_adoption(self) -> None:
        """条目把材料文件声明成 authoritative：材料只证明读到了这些字节，人的原话才是权威。"""
        self.ready()
        items = design_kit.handed_items(self.root, self.feature, ACCESS)
        items[0]["provenance"]["evidence_strength"] = "authoritative"
        design_kit.install_blueprint(self.root, self.feature, ACCESS, items=items)
        self.assertEqual("design_blueprint", self.ok("status")["next"])
        self.assertTrue(any("只能证明 observed" in p for p in self.source_problems()))

    def test_an_older_adopted_version_stays_the_basis(self) -> None:
        """设计开始之后产品需求取得了新版本：不开新轮，蓝图仍采用旧版本，照样可以成文——采不采用新版本由设计判断。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        rounds = len(self.contract()["rounds"])
        self.seed({"RR/prd.md": (PRD + "\n新版补了一句。\n", "RR")})
        self.assertEqual("refresh_round", self.ok("status")["next"])
        self.ok("round")
        self.assertEqual(rounds, len(self.contract()["rounds"]), "设计开始之后材料变了却开了新轮")
        self.assertEqual("ready_to_write", self.ok("status")["state"])
        self.assertEqual([], self.source_problems())


class MaterialChangesBeforeTheDesignReopenTheRound(HandoverCase):
    """范围定了、设计还没开始：材料再变照常开新一轮重新确认，不当作已经交给设计。"""

    def test_a_new_round_opens(self) -> None:
        self.ready()
        rounds = len(self.contract()["rounds"])
        self.seed({"RR/prd.md": (PRD + "\n补充。\n", "RR")})
        self.assertEqual("run_round", self.ok("status")["next"])
        self.assertTrue(self.ok("round")["created"])
        self.assertEqual(rounds + 1, len(self.contract()["rounds"]))

    def test_reopen_needs_a_started_design(self) -> None:
        self.ready()
        self.assertEqual(1, self.flow("reopen").returncode, "设计还没开始，范围关卡本来就能重走")
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        out = self.ok("reopen")
        self.assertEqual("gathering", out["status"])
        self.assertTrue(self.contract()["rounds"][-1]["reopened"])


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
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        (self.feature_root / "AR" / "story.md").write_text("# 随手写的一行\n", encoding="utf-8")
        proc = self.flow("story")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout[proc.stdout.index("{"):])["error"]
        self.assertNotIn("Cannot find module", error, "node 找不到 story-build.mjs——公共 CLI 的定位错了")
        self.assertIn("[story-build]", error, "登记没把 story-build 的结论带出来，只报了自己跑不通")
        self.assertEqual("gathering", self.contract()["status"], "检查没通过却记了成文态")


if __name__ == "__main__":
    unittest.main()
