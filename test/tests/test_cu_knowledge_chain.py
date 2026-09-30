"""真实施工单位的知识承接正常链：蓝图设计对象里的义务与模式角色，经原生派生 / 物化 → 阶段解析 → 门禁与审查任务。

用 demo Framework 与夹具蓝图（`wallet-balance-refresh`）在临时工程里走原生入口：蓝图里放逐条判断的知识应用决定、一个选型决定
（两个角色，一个落在本施工单位的设计引用内、一个落在别处），设计对象的契约里带 `must` / `pattern_roles`；
改过蓝图之后按原生的摘要口径更新施工单位的蓝图引用，再冻结范围。

锁的是：原生派生、复用本地物化件时，实体上的义务与角色都还在，并且被 plan 门禁与审查任务实际用上；
施工单位只承担落点在自己设计引用内的角色；测试的转译缓存钩子不改变结果。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_knowledge_task import BLUEPRINT, CU, make_project, prepare  # noqa: E402  —— 它把 test/scripts 放进导入路径
import design_kit  # noqa: E402

KNOWLEDGE_ID = "knowledge-obs-02"
PATTERN_ID = "pattern-decision-tree"
MODULE = "view:development/node:wallet-main-module"
ELSEWHERE = "view:runtime"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def pattern_text(root: Path) -> str:
    """选型决定：两个角色，一个落在本施工单位的设计对象上，一个落在别处。"""
    ref = "doc/extensions/knowledge/design-patterns/decision-tree.md"
    knowledge = {"kind": "patterns", "form": "halves", "unit": "上篇", "source_sha256": sha(root / ref), "outcome": "selected",
                 "target_refs": [MODULE], "roles": [{"role": "节点表", "target_ref": MODULE}, {"role": "上下文", "target_ref": ELSEWHERE}]}
    provenance = {"source_kind": "knowledge", "source_ref": ref, "observed_at": "2026-09-30T00:00:00Z",
                  "evidence_strength": "inferred", "extraction_method": "read_and_apply"}
    return (f"    - decision_id: {PATTERN_ID}\n      kind: knowledge_application\n      status: answered_with_evidence\n"
            f"      owner: design-author\n      rationale: 刷新有多个分支，拆成节点\n"
            f"      provenance: {json.dumps(provenance, ensure_ascii=False)}\n      verification_refs: [{MODULE}]\n"
            f"      knowledge: {json.dumps(knowledge, ensure_ascii=False)}\n")


def design(root: Path, with_roles: bool) -> None:
    """改夹具蓝图（按原文插入，不整份重写）：逐条的知识判断、选型决定、设计对象契约上的义务与角色；
    再按原生口径（蓝图原字节的摘要）更新施工单位的蓝图引用。"""
    canonical = root / "doc" / "features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
    old = sha(canonical)
    text = canonical.read_text(encoding="utf-8")
    active = design_kit.active_constraints(root, design_kit.ACCESS)
    judged = design_kit.judged_rules(active, [design_kit.knowledge_decision(
        KNOWLEDGE_ID, "OBS-02", "applied", "余额刷新是新增的业务过程", requirement="刷新失败记一条可定位的日志")], False)
    text = text.replace("decisions_and_gaps:\n  decisions:\n", "decisions_and_gaps:\n  decisions:\n"
                        + "".join(design_kit.decision_text(root, d, active) for d in judged) + pattern_text(root), 1)
    method = "                - name: refreshBalance\n"
    assert text.count(method) == 1
    text = text.replace(method, method + "                  must:\n                    - rule: OBS-02\n"
                        f"                      decision_id: {KNOWLEDGE_ID}\n                      text: 刷新失败时记一条带页面与原因的日志\n"
                        "                      verify: ut\n", 1)
    if with_roles:
        owner = "              class: HomeRepository\n"
        assert text.count(owner) == 1
        text = text.replace(owner, owner + "              pattern_roles:\n                - pattern: decision-tree\n"
                            f"                  role: 节点表\n                  decision_id: {PATTERN_ID}\n", 1)
    canonical.write_bytes(text.encode("utf-8"))
    unit = root / "doc" / "features" / BLUEPRINT / "balance-refresh" / "change-unit.yaml"
    unit.write_bytes(unit.read_bytes().replace(old.encode(), sha(canonical).encode()))


PROBE = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const base = pathToFileURL(root + '/doc/extensions/hooks/').href;
const c = await import(base + 'shared/contracts.mjs');
const plan = (await import(base + 'plan/post_check.mjs')).default;
const pre = (await import(base + 'shared/pre_verifier.mjs')).default;
const a = c.phaseArtifacts(root, feature, 'plan');
const i = a.contracts?.interfaces?.[0] ?? {};
const gate = await plan({ phase: 'plan', feature, projectRoot: root });
const review = await pre({ phase: 'plan', feature, projectRoot: root });
process.stdout.write(JSON.stringify({ must: i.methods?.[0]?.must ?? null, roles: i.pattern_roles ?? null, problems: a.problems,
  gate: gate.message ?? '', review: (review.promptFragments ?? []).join('\\n') }));
"""


class ChainCase(unittest.TestCase):
    WITH_ROLES = True
    STEPS: tuple[str, ...] = ("freeze",)

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        design(cls.root, cls.WITH_ROLES)
        for step in cls.STEPS:
            prepare(cls.root, step)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def probe(self, env: dict | None = None) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)


class TheDerivedContractCarriesTheObligations(ChainCase):
    """没有本地契约：原生从蓝图派生，实体上的义务与角色原样到门禁与审查任务。"""

    def test_obligations_and_roles_survive_derivation_and_are_used(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_ID, out["must"][0]["decision_id"])
        self.assertEqual([{"pattern": "decision-tree", "role": "节点表", "decision_id": PATTERN_ID}], out["roles"])
        self.assertNotIn("契约还没建", out["gate"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])
        self.assertNotIn("没有实体承担", out["gate"], out["gate"])
        self.assertIn(f"ut · {KNOWLEDGE_ID}", out["review"], "审查任务没并列出实体上的义务与出自的决定")

    def test_a_role_placed_elsewhere_is_not_this_units(self) -> None:
        """「上下文」落在别的设计对象上：本单位不被要求承担它。"""
        self.assertNotIn("上下文", self.probe()["gate"])

    def test_the_transpile_cache_hook_does_not_change_the_result(self) -> None:
        """测试的转译缓存钩子只省时间：关掉它重跑，门禁、审查任务与读到的义务一样。"""
        cached = self.probe()
        env = {**os.environ, "NODE_OPTIONS": " ".join(p for p in os.environ.get("NODE_OPTIONS", "").split('--require')
                                                      if "ts_transpile_cache" not in p).strip()}
        env.pop("STORY_TEST_TS_CACHE", None)
        self.assertEqual(cached, self.probe(env))


class AMissingOwnRoleIsNamed(ChainCase):
    """本单位承担的角色没有实体：点名那个角色，不点名别的施工单位的角色。"""
    WITH_ROLES = False

    def test_only_the_units_own_role_is_asked_for(self) -> None:
        gate = self.probe()["gate"]
        self.assertIn("「节点表」", gate)
        self.assertIn("没有实体承担", gate)
        self.assertNotIn("「上下文」", gate)


class TheMaterializedContractIsReused(ChainCase):
    """先物化本地契约再冻结：原生复用本地产物，实体上的义务与角色照样被读到。"""
    STEPS = ("materialize", "freeze")

    def test_the_materialized_contract_keeps_the_obligations(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_ID, out["must"][0]["decision_id"])
        self.assertTrue(out["roles"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])


if __name__ == "__main__":
    unittest.main()
