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
import re
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
#: 原件按它在收件箱里的位置引用图（RR/prd.md → assets/flow.svg）；导入后阅读稿改指图的版本位置
PRD = "# 产品需求\n\n## 背景\n\n签约流程见下图：\n\n![签约流程](../assets/flow.svg)\n"
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
        inbox = self.feature_root / "inbox"
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
        self.assertIn("不是材料索引登记的文件", json.loads(proc.stdout)["error"])
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
        self.assertIn(f"没有引用需求 {FEATURE} 登记的材料", problem)

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
    """同一条命令、同一个时点只取一份材料事实：消费者各拿一份「现在的材料」时，谁也说不清读的是哪一份。
    答复生效的那一刻另有一次刷新：把刚生效的人答导出，下一步读到的就是它（刷新里自己的那次计算不算另取）。"""

    def count_material_reads(self) -> tuple[list, list]:
        builds, refreshes = [], []
        real_build, real_refresh = registry.build, registry.refresh
        inside = []

        def counting_build(feature_root, *rest, **kw):
            if not inside:
                builds.append(feature_root)
            return real_build(feature_root, *rest, **kw)

        def counting_refresh(feature_root):
            refreshes.append(feature_root)
            inside.append(True)
            try:
                return real_refresh(feature_root)
            finally:
                inside.pop()

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
        self.assertEqual((0, 1, 1), (code, len(builds), len(refreshes)))

    def test_a_rejected_supply_request_asks_the_disk_once(self) -> None:
        """人说「料放进去了」而盘上什么也没有：原地驳回，同样只读一次。"""
        self.first_gate_ready()
        builds, refreshes = self.count_material_reads()
        result, code = self.decide_now("material_scope", MATERIAL_REQUEST_KEYS[0])
        self.assertEqual((2, "rejected", 1, []), (code, result["outcome"], len(builds), refreshes))

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
        self.assertEqual((0, 1, 1), (code, len(builds), len(refreshes)))

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
        self.assertEqual((0, 1, 1), (code, len(builds), len(refreshes)))


class TheEffectiveAnswersReachTheDesign(HandoverCase):
    """人答一生效就导出，设计作者、核源与 Story 审查读到的是同一份当前有效人答；它独立必读，不取决于需求条目写没写它。"""

    SOURCE = """
    const [module, access, root, feature] = process.argv.slice(1);
    const { designSource, requiredAnswers } = await import(module);
    const { sourcesIdentity } = await import(access);
    const ctx = { projectRoot: root, args: { feature }, featureRoot: `${root}/doc/features/${feature}`,
                  flowPath: `${root}/doc/features/${feature}/AR/story-src/story-flow.json` };
    const src = designSource(ctx);
    process.stdout.write(JSON.stringify({ problems: src.problems, answers: requiredAnswers(ctx),
      versions: src.adopted?.own?.versions ?? [], adopted: (src.adopted?.answers ?? []).map(f => f.path),
      // 成文依据的来源身份（currentBasis 的 sources_sha256）由这几部分算
      identity: src.adopted ? sourcesIdentity([...src.adopted.sources, ...(src.adopted.own?.files ?? []),
        ...src.adopted.projectFiles, ...src.adopted.answers]) : null }));
    """

    def design_view(self) -> dict:
        module = (STORY_SCRIPTS / "story" / "design-source.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", self.SOURCE, module, ACCESS.resolve().as_uri(),
                               str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def exported(self) -> dict:
        answers = next(s for s in registry.read(self.feature_root)["sources"] if s["kind"] == "answer")
        return json.loads((self.feature_root / answers["versions"][-1]["original"]["path"]).read_text(encoding="utf-8"))

    def test_a_scope_answer_reaches_the_design_without_another_refresh(self) -> None:
        """真实 decide 之后不再刷新：导出里有问法与原话；需求条目只写真实需求，人答照样进设计来源。"""
        self.ready()
        status = json.loads(self.flow("status", "--materials").stdout)
        self.assertTrue(status["required_answers"]["in_sync"], status)
        current = self.exported()["current"]
        self.assertEqual(["material_scope", "scope_decision"], [d["gate"] for d in current])
        self.assertEqual("现有材料就是全部", current[0]["reply"])
        self.assertTrue(all(d["question"] for d in current), "导出的人答没带问法")
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        scope = [i["item_id"] for i in yaml_scope(self.root, self.feature)]
        self.assertEqual(["request-main"], scope, "夹具不该为人答或支撑材料造需求条目")
        view = self.design_view()
        self.assertEqual([], view["problems"])
        self.assertIn(self.answers_rel(), [p.split(f"{self.feature}/", 1)[1] for p in view["adopted"]])

    def test_the_scope_answer_carries_who_carries_what(self) -> None:
        """范围答复连同当时的定位导出：本单承载什么、同一系统设计下的兄弟单承载什么，设计与审查按它写范围与边界。"""
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.write_analysis()
        (self.src / ".positioning.json").write_text(json.dumps(
            {"scope_source": "user_stated", "scope_text": "本 AR 承载自动充值签约与管理",
             "sr_related_ars": [{"ar": "AR90002", "scope": "补卡与换卡"}]}, ensure_ascii=False), encoding="utf-8")
        self.ok("round")
        answer(self.ok, "scope_decision", "1")
        text = (self.feature_root / self.answers_rel()).read_text(encoding="utf-8")
        self.assertIn("本单承载：本 AR 承载自动充值签约与管理", text)
        self.assertIn("兄弟单 AR90002：补卡与换卡", text)

    def test_a_support_source_is_adopted_through_its_fact(self) -> None:
        """系统设计只在事实的 provenance 里引用：它的版本进采用集合，不需要伪造约束条目。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        versions = self.design_view()["versions"]
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in versions), versions)
        self.assertTrue(any(re.fullmatch(r"prd(-[0-9a-f]{6})?-v1", v) for v in versions), versions)

    def test_a_support_reference_to_an_unregistered_file_is_named(self) -> None:
        """设计依据引了本需求下没登记的文件：报出位置，不静默省略。"""
        self.ready()
        stray = f"doc/features/{self.feature}/.backups/local/SR/design-v9.md"
        design_kit.install_blueprint(self.root, self.feature, ACCESS, support=[stray])
        self.assertTrue(any("discovery.facts" in p and stray in p for p in self.design_view()["problems"]))

    def test_an_export_failure_keeps_the_answer_and_round_retries(self) -> None:
        """导出写失败：答复已经生效、报清楚怎么重试；重跑 round 只补导出，不开新轮、不重问。"""
        from flow.state import FlowError  # noqa: PLC0415
        from materials import answers  # noqa: PLC0415
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        self.ok("status")
        ask = json.loads((self.src / ".ask.json").read_text(encoding="utf-8"))
        args = argparse.Namespace(gate="material_scope", chosen="confirm_scope", ask=ask["ask_id"],
                                  reply="现有材料就是全部", meeting=None, item=None)
        real = answers.export

        def broken(*_a, **_k):
            raise OSError("磁盘写满")

        answers.export = broken
        self.addCleanup(setattr, answers, "export", real)
        with self.assertRaises(FlowError) as got:
            cmd_decide(self.feature_root, args)
        self.assertIn("已经记下并生效", str(got.exception))
        self.assertIn("story_flow.py round", str(got.exception))
        answers.export = real
        rounds = len(self.contract()["rounds"])
        self.assertEqual(["material_scope"], [g["gate"] for g in self.contract()["rounds"][-1]["gates"]])
        self.assertFalse(json.loads(self.flow("status", "--materials").stdout)["required_answers"]["in_sync"])
        self.assertFalse(self.ok("round")["created"])
        self.assertEqual(rounds, len(self.contract()["rounds"]))
        self.assertTrue(json.loads(self.flow("status", "--materials").stdout)["required_answers"]["in_sync"])
        self.assertNotEqual("await_gate:material_scope", self.ok("status")["next"], "导出补上之后又问了一遍")

    def test_a_supplement_after_reopen_keeps_the_old_scope_out_until_answered_again(self) -> None:
        """设计开始后重开范围、还没重答就补料开了新轮：旧范围答复不回到当前；重新答了之后新答复生效，其余人答不丢。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        self.ok("reopen")
        self.seed({"UX/补充说明.md": ("# 补充\n\n入口挪到卡包首页。\n", "UX")})
        self.assertTrue(self.ok("round")["created"])
        self.assertEqual(["material_scope"], [d["gate"] for d in self.exported()["current"]],
                         "重开之后补料开轮，旧范围答复又算当前了")
        while (step := self.ok("status")["next"]).startswith("await_gate:") or step in ("run_round", "run_analysis"):
            if step == "run_analysis":
                self.write_analysis()
                self.ok("round")
            elif step == "run_round":
                self.ok("round")
            else:
                answer(self.ok, step.split(":", 1)[1], "1")
        current = self.exported()["current"]
        scope = next(d for d in current if d["gate"] == "scope_decision")
        self.assertEqual(self.contract()["rounds"][-1]["round"], scope["round"], "生效的不是重开之后重答的那一次")
        self.assertIn("material_scope", [d["gate"] for d in current])

    def test_a_later_carry_all_retires_the_split_carrier(self) -> None:
        """切两份、定了承载，设计开始后重开范围改成整体承载：旧的承载答复只是历史，不再当前有效。"""
        self.ok("init")
        self.ok("round")
        write_gaps(self.src)
        answer(self.ok, "material_scope", "现有材料就是全部")
        self.write_analysis()
        parts = [{"seq": 1, "scope": "本单承载签约入口", "depends_on": []},
                 {"seq": 2, "scope": "兄弟单承载补卡", "depends_on": [1]}]
        (self.src / ".scope-options.json").write_text(json.dumps(
            [{"key": CARRY_ALL, "label": "按当前范围整体承载"}, {"key": "by_capability", "label": "按能力切两份", "parts": parts}],
            ensure_ascii=False), encoding="utf-8")
        self.ok("round")
        answer(self.ok, "scope_decision", "按能力切两份")
        (self.src / ".split-parts.json").write_text(json.dumps(
            [{"seq": 1, "carrier": FEATURE, "scope": "本单承载签约入口", "depends_on": []},
             {"seq": 2, "carrier": "AR90002", "scope": "兄弟单承载补卡", "depends_on": [1]}], ensure_ascii=False), encoding="utf-8")
        answer(self.ok, "split_carrier", "1")
        self.assertIn("split_carrier", [d["gate"] for d in self.exported()["current"]])
        split = next(d for d in self.exported()["current"] if d["gate"] == "split_carrier")
        self.assertEqual(2, len(split["context"]["parts"]), "承载答复没带当时的份表")
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        self.ok("reopen")
        self.assertNotIn("split_carrier", [d["gate"] for d in self.exported()["current"]], "重开范围后旧承载答复仍算当前")
        while (step := self.ok("status")["next"]).startswith("await_gate:") or step == "run_round":
            if step == "run_round":
                self.ok("round")
            else:
                answer(self.ok, step.split(":", 1)[1], "1")    # 整体承载是第 1 项
        current = self.exported()["current"]
        self.assertNotIn("split_carrier", [d["gate"] for d in current])
        self.assertEqual(CARRY_ALL, next(d for d in current if d["gate"] == "scope_decision")["chosen"])

    def test_a_new_answer_moves_the_basis_but_not_the_materials(self) -> None:
        """重开范围后人又答了一次：材料摘要不动（不开补料轮），成文依据的来源身份（currentBasis 的算法）跟着变。"""
        self.ready()
        design_kit.install_blueprint(self.root, self.feature, ACCESS)
        before = (registry.read(self.feature_root)["digest"], self.design_view()["identity"])
        self.ok("reopen")
        while (step := self.ok("status")["next"]).startswith("await_gate:") or step == "run_round":
            if step == "run_round":
                self.ok("round")
            else:
                answer(self.ok, step.split(":", 1)[1], "1")
        after = (registry.read(self.feature_root)["digest"], self.design_view()["identity"])
        self.assertEqual(before[0], after[0], "答一句话把材料摘要顶动了")
        self.assertNotEqual(before[1], after[1], "新的人答没进成文依据的来源身份")

    def test_a_record_without_its_question_is_a_production_defect(self) -> None:
        """本版生产的人答记录缺问法：明确失败，不补默认值。"""
        from materials import answers  # noqa: PLC0415
        self.ready()
        data = self.contract()
        del data["rounds"][-1]["gates"][-1]["question"]
        (self.src / "story-flow.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(answers.AnswerError) as got:
            answers.collect(self.feature_root)
        self.assertIn("缺 question", str(got.exception))


class SourceIndexCase(HandoverCase):
    """把一个蓝图对象放到同根蓝图的位置，经原生读取取它的来源索引（作者、Story 与审查都消费这一份）。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const { sourcesIdentity } = await import(access);
    const own = out.requirements[0] ?? { versions: [], files: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, versions: own.versions,
      projectFiles: out.projectFiles, authorityFiles: out.authorityFiles, authorityIssues: out.authorityIssues, status: out.status,
      identity: sourcesIdentity([...out.sources, ...own.files, ...out.projectFiles, ...out.authorityFiles]) }));
    """

    def collect(self, blueprint: dict) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(blueprint, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def blueprint(self, *, contract_ref: str, conflict_ref: str | None = None) -> dict:
        prov = lambda ref: {"source_kind": "system_design", "source_ref": ref, "observed_at": "2026-10-30T10:00:00+08:00",
                            "evidence_strength": "observed", "extraction_method": "read-source"}
        conflicts = [{"sources": [{"source_ref": conflict_ref}, {"source_ref": contract_ref}], "owner": "需求负责人"}] if conflict_ref else []
        return {"blueprint_id": self.feature, "discovery": {"inputs": {"current_scope_items": []}, "facts": [], "conflicts": conflicts},
                "contracts": [{"contract_id": "c-sign", "provenance": prov(contract_ref)}]}

    def setUp(self) -> None:
        super().setUp()
        self.ready()
        self.base = f"doc/features/{self.feature}"
        self.sr = f"{self.base}/{next(s for s in registry.read(self.feature_root)['sources'] if s['source_id'] == 'local:SR/design.md')['versions'][-1]['original']['path']}"


class TheSupportSourcesAreCollectedNatively(SourceIndexCase):
    """设计依据按原生出处收全：合同对象自身的 provenance 也算；引用带的片段按原生来源解析核；需求目录里没登记的冲突依据报出；
    需求目录以外的工程文件读出摘要进来源身份。"""

    def test_a_contract_level_reference_adopts_its_version(self) -> None:
        got = self.collect(self.blueprint(contract_ref=f"{self.sr}#分工"))
        self.assertEqual([], got["problems"])
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in got["versions"]), got["versions"])

    def test_a_fragment_that_is_not_in_the_file_is_named(self) -> None:
        got = self.collect(self.blueprint(contract_ref=f"{self.sr}#没有这一节"))
        self.assertTrue(any("contracts[c-sign]" in p and "fragment" in p for p in got["problems"]), got["problems"])

    def test_an_unregistered_conflict_source_is_named(self) -> None:
        stray = f"{self.base}/.backups/local/SR/design-v9.md"
        got = self.collect(self.blueprint(contract_ref=self.sr, conflict_ref=stray))
        self.assertTrue(any("冲突依据" in p and stray in p for p in got["problems"]), got["problems"])

    def test_a_project_file_outside_the_requirement_enters_the_identity(self) -> None:
        doc = self.root / "doc" / "architecture" / "签约边界.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# 签约边界\n\n钱包只发起签约。\n", encoding="utf-8")
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-boundary", "provenance": {"source_ref": "doc/architecture/签约边界.md#签约边界"}}]
        first = self.collect(bp)
        self.assertEqual([], first["problems"])
        self.assertEqual(["doc/architecture/签约边界.md"], [f["path"] for f in first["projectFiles"]])
        doc.write_text("# 签约边界\n\n钱包发起并确认签约。\n", encoding="utf-8")
        self.assertNotEqual(first["identity"], self.collect(bp)["identity"], "工程文件变了，来源身份没跟着变")

    def test_a_non_file_provenance_is_left_to_the_native_contract(self) -> None:
        bp = self.blueprint(contract_ref=self.sr)
        bp["discovery"]["facts"] = [{"fact_id": "f-talk", "provenance": {"source_ref": "interview:2026-10-30-产品"}}]
        got = self.collect(bp)
        self.assertEqual(([], []), (got["problems"], got["projectFiles"]))


class ContractSectionsReadTheirAuthority(SourceIndexCase):
    """契约段的 source_ref 是设计转写出的接口契约（JSON Pointer 指到段），放在需求自己的 blueprint/ 下：
    指针与内容由原生契约校验核，不按材料登记、不按文字片段核；依据引用与某段完全相同就是这一段。坏指针、内容不符照原生报，
    同文件里原生没核过的位置单独报出；权威文件的字节进来源身份。"""

    AUTHORITY = "operations:\n  sign:\n    operation:\n      operation_id: sign\n      direction: outbound\n      version: v1\n"

    def setUp(self) -> None:
        super().setUp()
        self.file = f"{self.base}/blueprint/contracts/sign.yaml"
        self.authority = self.root / Path(*self.file.split("/"))
        self.authority.parent.mkdir(parents=True, exist_ok=True)
        self.authority.write_bytes(self.AUTHORITY.encode("utf-8"))

    def with_contract(self, pointer: str, *, version: str = "v1", fact_ref: str | None = None) -> dict:
        bp = self.blueprint(contract_ref=f"{self.sr}#分工")
        bp["contracts"][0]["operation"] = {"operation_id": "sign", "direction": "outbound", "version": version,
                                           "source_ref": f"{self.file}#{pointer}", "verification_refs": ["ut:sign"]}
        if fact_ref:
            bp["discovery"]["facts"] = [{"fact_id": "f-op", "provenance": {"source_kind": "system_design", "source_ref": fact_ref}}]
        return bp

    def test_a_section_pointer_and_an_equal_design_reference_are_the_authority(self) -> None:
        ref = f"{self.file}#/operations/sign/operation"
        got = self.collect(self.with_contract("/operations/sign/operation", fact_ref=ref))
        self.assertEqual(([], "ok", []), (got["problems"], got["status"], got["authorityIssues"]))
        [row] = got["authorityFiles"]
        self.assertEqual((self.file, f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}", "contract_authority"),
                         (row["path"], row["sha256"], row["role"]))
        self.assertEqual({"contracts[c-sign].operation", "discovery.facts[f-op]"}, {r["where"] for r in row["refs"]})
        self.assertTrue(any(re.fullmatch(r"design(-[0-9a-f]{6})?-v1", v) for v in got["versions"]), "合同自身的原始出处没再采用")

    def test_a_pointer_the_authority_does_not_have_is_the_native_finding(self) -> None:
        got = self.collect(self.with_contract("/operations/refund/operation"))
        self.assertEqual("incomplete", got["status"])
        self.assertEqual(["blueprint_contract_authority_source_invalid"], [i["id"] for i in got["authorityIssues"]])
        self.assertEqual([None], [f["sha256"] for f in got["authorityFiles"]], "坏的契约权威不能给出可复用的摘要")
        self.assertTrue(any("契约权威" in p and "refund" in p for p in got["problems"]), got["problems"])

    def test_content_that_differs_from_its_authority_is_the_native_finding(self) -> None:
        got = self.collect(self.with_contract("/operations/sign/operation", version="v2"))
        self.assertEqual(["blueprint_contract_authority_mismatch"], [i["id"] for i in got["authorityIssues"]])

    def test_another_place_in_the_authority_file_is_named(self) -> None:
        got = self.collect(self.with_contract("/operations/sign/operation", fact_ref=f"{self.file}#/operations"))
        self.assertEqual("ok", got["status"])
        [problem] = got["problems"]
        self.assertIn("discovery.facts[f-op]", problem)
        self.assertIn("原生核过", problem)

    def test_the_authority_bytes_enter_the_identity(self) -> None:
        bp = self.with_contract("/operations/sign/operation")
        first = self.collect(bp)
        self.authority.write_bytes(("# 签约接口\n" + self.AUTHORITY).encode("utf-8"))
        again = self.collect(bp)
        self.assertEqual(([], []), (first["problems"], again["problems"]))
        self.assertNotEqual(first["identity"], again["identity"], "权威文件换了字节，来源身份没跟着变")

    def test_an_equivalent_path_the_native_loader_accepts_is_the_same_authority(self) -> None:
        """原生 loader 接受 `contracts/../contracts/sign.yaml` 这样的根内等价写法：它与标准写法是同一份权威文件、同一摘要、同一来源身份。"""
        pointer = "/operations/sign/operation"
        standard = self.collect(self.with_contract(pointer))
        bp = self.with_contract(pointer)
        bp["contracts"][0]["operation"]["source_ref"] = f"{self.base}/blueprint/contracts/../contracts/sign.yaml#{pointer}"
        equivalent = self.collect(bp)
        self.assertEqual(([], []), (equivalent["problems"], equivalent["authorityIssues"]))
        self.assertEqual([(self.file, f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}")],
                         [(f["path"], f["sha256"]) for f in equivalent["authorityFiles"]], "等价写法的权威文件没进来源集合")
        self.assertEqual(standard["identity"], equivalent["identity"])

    def test_an_authority_outside_the_project_stays_the_native_finding(self) -> None:
        bp = self.with_contract("/operations/sign/operation")
        bp["contracts"][0]["operation"]["source_ref"] = "../outside/sign.yaml#/operations/sign/operation"
        got = self.collect(bp)
        self.assertEqual("incomplete", got["status"])
        self.assertEqual(["blueprint_contract_authority_source_invalid"], [i["id"] for i in got["authorityIssues"]])
        self.assertEqual([], got["authorityFiles"])

    def test_the_review_object_lists_the_authority_reached_by_an_equivalent_path(self) -> None:
        """独审对象是来源集合的直接读者：等价写法引到的权威文件照样进必读材料。"""
        probe = """
        const [access, review, root, feature, BLUEPRINT] = process.argv.slice(1);
        const fs = await import('node:fs');
        const path = await import('node:path');
        const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
        fs.writeFileSync(file, BLUEPRINT);
        const { reviewObject } = await import(review);
        const object = reviewObject(root, feature, { withTask: false });
        fs.rmSync(file);
        process.stdout.write(JSON.stringify(object.rows.map(r => r.path)));
        """
        bp = self.with_contract("/operations/sign/operation")
        bp["contracts"][0]["operation"]["source_ref"] = f"{self.base}/blueprint/contracts/../contracts/sign.yaml#/operations/sign/operation"
        review = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story" / "review-object.mjs"
        manifest = self.root / "doc" / "extensions" / "manifest.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("provides:\n  knowledge: []\n", encoding="utf-8")   # 审查对象要列激活清单；本例不涉知识
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, ACCESS.resolve().as_uri(), review.resolve().as_uri(),
                               str(self.root), self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(self.file, json.loads(proc.stdout), "独审必读材料里没有等价写法引到的权威文件")

    def test_a_read_after_an_edit_in_the_same_process_sees_the_new_bytes(self) -> None:
        """同一进程里先读、改了权威文件再读：后一次按此刻的字节，不沿用前一次的结果。"""
        probe = """
        const [access, root, feature, file, bp, extra] = process.argv.slice(1);
        const fs = await import('node:fs');
        const path = await import('node:path');
        const canonical = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
        fs.writeFileSync(canonical, bp);
        const { readBlueprint } = await import(access);
        const sha = () => readBlueprint(root, feature, 'draft', feature).source_index.authorityFiles.map(f => f.sha256);
        const before = sha();
        fs.writeFileSync(path.join(root, ...file.split('/')), extra + fs.readFileSync(path.join(root, ...file.split('/')), 'utf8'));
        process.stdout.write(JSON.stringify({ before, after: sha() }));
        """
        bp = json.dumps(self.with_contract("/operations/sign/operation"), ensure_ascii=False)
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, ACCESS.resolve().as_uri(), str(self.root), self.feature,
                               self.file, bp, "# 签约接口\n"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual([f"sha256:{hashlib.sha256(self.AUTHORITY.encode('utf-8')).hexdigest()}"], got["before"])
        self.assertEqual([f"sha256:{hashlib.sha256(('# 签约接口' + chr(10) + self.AUTHORITY).encode('utf-8')).hexdigest()}"], got["after"])


class ACitedCurrentDraftStaysAtItsVersion(HandoverCase):
    """作者按当前阅读稿 `RR/prd.md#节` 写需求条目：补出的引用指当时那一版聚合稿的稳定副本与它固定的组成；
    之后一份原件换版，当前稿换成新的一版，旧条目与旧支撑引用仍读旧正文、展开旧组成，新条目指新的一版。
    设计引用当前位置不算依据，报出它此刻对应的稳定文件。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const own = out.requirements[0] ?? { versions: [], files: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, versions: own.versions, files: own.files.map(f => f.path) }));
    """

    LIMIT = "# 限额\n\n## 单笔\n\n单笔上限 {} 元。\n"

    def collect(self, items: list[dict], support: str | None = None) -> dict:
        prov = {"source_kind": "requirement_reading", "source_ref": support, "observed_at": "2026-11-02T10:00:00+08:00",
                "evidence_strength": "observed", "extraction_method": "read-source"}
        bp = {"blueprint_id": self.feature, "discovery": {"inputs": {"current_scope_items": items}, "conflicts": [],
                                                          "facts": [{"fact_id": "f-limit", "provenance": prov}] if support else []}}
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def current(self) -> dict:
        """材料索引里当前稿 `RR/prd.md` 那一行（会换版的当前位置）。"""
        return next(r for r in registry.read(self.feature_root)["files"] if r["path"] == "RR/prd.md")

    def test_the_cited_version_and_its_components_survive_a_new_version(self) -> None:
        self.ready()
        self.seed({"RR/限额.md": (self.LIMIT.format(500), "RR")})
        [old] = self.scoped([item("RR/prd.md#单笔")])["current_scope_items"]
        alias = self.current()
        stable = alias["reference"]["path"]
        self.assertEqual(f"doc/features/{FEATURE}/{stable}#单笔", old["source_ref"], "条目指了会换版的当前稿")
        self.assertEqual(f"draft:RR/prd.md@v{alias['version']}", old["provenance"]["source_revision"])
        self.assertIn("单笔上限 500 元", (self.feature_root / stable).read_text(encoding="utf-8"))
        support = f"doc/features/{FEATURE}/{stable}#背景"
        first = self.collect([old], support)
        self.assertEqual([], first["problems"])
        self.assertIn("限额-v1", first["versions"], "聚合稿的组成没展开")

        self.seed({"RR/限额.md": (self.LIMIT.format(800), "RR")})
        self.assertNotEqual(stable, self.current()["reference"]["path"], "原件换版后当前稿没换成新的一版")
        again = self.collect([old], support)
        self.assertEqual([], again["problems"], "旧引用在材料换版后读不了")
        self.assertEqual(first["versions"], again["versions"], "旧引用展开到了新的组成")
        self.assertIn("单笔上限 500 元", (self.feature_root / stable).read_text(encoding="utf-8"), "旧稳定副本被改了")
        [new] = self.scoped([item("RR/prd.md#单笔")])["current_scope_items"]
        self.assertNotEqual(old["source_ref"], new["source_ref"])
        latest = self.collect([new])
        self.assertIn("限额-v2", latest["versions"])
        self.assertNotIn("限额-v1", latest["versions"])

    def test_a_design_reference_to_the_current_draft_names_its_stable_file(self) -> None:
        self.ready()
        [scoped] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        got = self.collect([scoped], f"doc/features/{FEATURE}/RR/prd.md#背景")
        [problem] = got["problems"]
        self.assertIn("f-limit", problem)
        self.assertIn(self.current()["reference"]["path"], problem, "没指出当前位置对应的稳定文件")


class DirectOriginalsAreCitedAtTheirVersions(HandoverCase):
    """直接写在 RR/SR/AR 的原文：同一批里互相链接时，阅读稿链对方这一批的版本，与先后无关；被链的那份换版，旧版仍读旧正文。
    设计引用的图按用途归集：采用的图进采用，冲突依据直接引或经它的文稿链到的图进冲突核源，不凭空变成采用。"""

    PROBE = """
    const [access, root, feature, BLUEPRINT] = process.argv.slice(1);
    const fs = await import('node:fs');
    const path = await import('node:path');
    const file = path.join(root, 'doc', 'features', feature, 'blueprint', 'component-blueprint.yaml');
    if (fs.existsSync(file)) throw new Error(`${file} 已有蓝图，探针不覆盖`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, BLUEPRINT);
    const { readBlueprint } = await import(access);
    const read = readBlueprint(root, feature, 'draft', feature);
    fs.rmSync(file);
    if (!fs.readdirSync(path.dirname(file)).length) fs.rmdirSync(path.dirname(file));
    if (read.status !== 'ok') throw new Error(`蓝图读不过：${JSON.stringify(read.issues)}`);
    const out = read.source_index;
    const own = out.requirements[0] ?? { files: [], conflictFiles: [] };
    process.stdout.write(JSON.stringify({ problems: out.problems, files: own.files.map(f => f.path),
      conflictFiles: own.conflictFiles.map(f => f.path) }));
    """

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        ensure_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / self.feature
        (self.feature_root / "inbox").mkdir(parents=True)
        self.src = self.feature_root / "AR" / "story-src"
        self.base = f"doc/features/{self.feature}"

    def give(self, files: dict[str, str | bytes]) -> None:
        """直接写进需求目录（不经收件箱），再经真实导入器登记。"""
        for rel, body in files.items():
            (self.feature_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.feature_root / rel).write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        importer.cmd_import(self.feature_root, self.root)

    def latest(self, rel: str) -> dict:
        return next(s for s in registry.read(self.feature_root)["sources"] if s["source_id"] == f"direct:{rel}")["versions"][-1]

    def collect(self, items: list[dict], support: list[str] = (), conflicts: list[str] = ()) -> dict:
        prov = lambda ref: {"source_kind": "requirement_reading", "source_ref": ref, "observed_at": "2026-11-02T10:00:00+08:00",  # noqa: E731
                            "evidence_strength": "observed", "extraction_method": "read-source"}
        bp = {"blueprint_id": self.feature, "discovery": {
            "inputs": {"current_scope_items": items},
            "facts": [{"fact_id": f"f-{i}", "provenance": prov(ref)} for i, ref in enumerate(support)],
            "conflicts": [{"sources": [{"source_ref": ref} for ref in conflicts], "owner": "需求负责人"}] if conflicts else []}}
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, ACCESS.resolve().as_uri(), str(self.root),
                               self.feature, json.dumps(bp, ensure_ascii=False)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_link_between_direct_originals_reads_the_linked_version(self) -> None:
        self.give({"RR/prd.md": "# 产品需求\n\n## 背景\n\n分工见[系统设计](../SR/design.md#分工)。\n",
                   "SR/design.md": "# 系统设计\n\n## 分工\n\n钱包发起签约。\n"})
        [old] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        first = self.collect([old])
        self.assertEqual([], first["problems"], "同一批登记的直接原文链到了会换版的当前位置")
        sr_v1 = f"{self.base}/{self.latest('SR/design.md')['readable']['path']}"
        self.assertIn(sr_v1, first["files"], "链到的系统设计没随采用展开")
        self.assertIn("钱包发起签约", (self.root / sr_v1).read_text(encoding="utf-8"))

        self.give({"SR/design.md": "# 系统设计\n\n## 分工\n\n钱包发起并确认签约。\n"})
        sr_v2 = f"{self.base}/{self.latest('SR/design.md')['readable']['path']}"
        self.assertNotEqual(sr_v1, sr_v2)
        again = self.collect([old])
        self.assertEqual([], again["problems"])
        self.assertIn(sr_v1, again["files"], "旧引用展开到了新版本")
        self.assertNotIn(sr_v2, again["files"])
        self.assertIn("钱包发起签约", (self.root / sr_v1).read_text(encoding="utf-8"), "旧版正文被改了")
        [new] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        self.assertNotEqual(old["source_ref"], new["source_ref"], "被链的原文换版，链它的阅读稿没出新版本")
        self.assertIn(sr_v2, self.collect([new])["files"])

    READERS = """
    const [core, root, feature] = process.argv.slice(1);
    const { createContext } = await import(new URL('context.mjs', core));
    const { adoptedUpstreamTexts, upstreamDocs } = await import(new URL('sources.mjs', core));
    const ctx = createContext({ feature, projectRoot: root });
    process.stdout.write(JSON.stringify({ texts: adoptedUpstreamTexts(ctx), docs: upstreamDocs(ctx).map(([, , rel]) => rel) }));
    """

    def test_two_direct_originals_of_the_same_name_stay_apart(self) -> None:
        """SR/design.md 与 AR/design.md 同一批直接给出、主名相同：各是各的来源版本；设计只采用开发需求时，
        Story 读上游正文与上游图的读者都不把系统设计算作采用。"""
        self.give({"SR/design.md": "# 系统设计\n\n## 分工\n\n云侧负责扣款。\n",
                   "AR/design.md": "# 开发需求\n\n## 范围\n\n钱包发起签约。\n"})
        sr, ar = self.latest("SR/design.md"), self.latest("AR/design.md")
        self.assertNotEqual(sr["dir"], ar["dir"], "两份直接原文的版本身份相同")
        [scoped] = self.scoped([item("AR/design.md#范围")])["current_scope_items"]
        design_kit.install_blueprint(self.root, self.feature, ACCESS, items=[scoped], support=[])
        proc = subprocess.run(["node", "--input-type=module", "-e", self.READERS,
                               (STORY_SCRIPTS / "story").resolve().as_uri() + "/", str(self.root), self.feature],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertTrue(any("钱包发起签约" in text for text in got["texts"]), "采用的开发需求没交给上游正文的读者")
        self.assertFalse(any("云侧负责扣款" in text for text in got["texts"]), "没被采用的系统设计算成了采用的上游正文")
        self.assertEqual([], got["docs"], "没被采用的系统设计进了上游图的读者")

    def test_pictures_follow_the_use_they_were_cited_for(self) -> None:
        picture = self.feature_root / "assets" / "ux" / "界面.png"
        picture.parent.mkdir(parents=True, exist_ok=True)
        picture.write_bytes(b"\x89PNG\r\n\x1a\nui")
        self.give({"RR/prd.md": "# 产品需求\n\n## 背景\n\n签约。\n",
                   "AR/design.md": "# 开发需求\n\n## 界面\n\n![界面](../assets/ux/界面.png)\n"})
        [scoped] = self.scoped([item("RR/prd.md#背景")])["current_scope_items"]
        shown = f"{self.base}/{self.latest('AR/design.md')['images'][0]['path']}"
        reading = f"{self.base}/{self.latest('AR/design.md')['readable']['path']}"
        direct = self.collect([scoped], conflicts=[shown])
        self.assertEqual([], direct["problems"])
        self.assertIn(shown, direct["conflictFiles"], "冲突依据直接引的图没进冲突核源")
        self.assertNotIn(shown, direct["files"], "只作冲突依据的图变成了采用")
        linked = self.collect([scoped], conflicts=[reading])
        self.assertEqual([], linked["problems"])
        self.assertTrue({reading, shown} <= set(linked["conflictFiles"]), "冲突文稿链到的图没随冲突核源交出")
        self.assertNotIn(shown, linked["files"])
        used = self.collect([scoped], support=[shown])
        self.assertIn(shown, used["files"], "设计引用的图没进采用")
        self.assertNotIn(reading, used["files"], "引了文稿里的一张图，把整份文稿都算成了采用")


def yaml_scope(root: Path, feature: str) -> list[dict]:
    """蓝图里的原生需求条目（夹具写成单行 JSON）。"""
    text = (root / "doc" / "features" / feature / "blueprint" / "component-blueprint.yaml").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.strip().startswith("current_scope_items:"))
    return json.loads(line.split(":", 1)[1])


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
