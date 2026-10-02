"""设计里的知识应用：形态按 knowledge-application.schema.json（原生 lite-json-schema 校验），来源、原文摘要、
单元、稳定地址、红线不可豁免与逐条覆盖按实际对象核（hooks/shared/knowledge-application.mjs）。

用例在一份已交给设计、蓝图已准入的工程上改蓝图对象里的决定，看核对结论；夹具的准入本身已经过原生完整校验。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT, REPO_ROOT
import design_kit
from designed_fixture import DRAFT, designed_copy

FIXTURE = REPO_ROOT / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"
MODULE = (DEV_EXT / "hooks" / "shared" / "knowledge-application.mjs").resolve().as_uri()
ACCESS = (DEV_EXT / "hooks" / "shared" / "framework-access.mjs").resolve().as_uri()
#: 读准入蓝图，按 argv 里的 JS 片段改它（变量 bp、decisions、sha），再核
SCRIPT = """
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
const [module, access, root, blueprintId, mutate] = process.argv.slice(1);
const { blueprintKnowledge } = await import(module);
const { readBlueprint } = await import(access);
const bp = structuredClone(readBlueprint(root, blueprintId, 'draft').blueprint);
const decisions = bp.decisions_and_gaps.decisions.filter(d => d.kind === 'knowledge_application');
const sha = rel => 'sha256:' + crypto.createHash('sha256').update(fs.readFileSync(root + '/' + rel)).digest('hex');
new Function('bp', 'decisions', 'sha', mutate)(bp, decisions, sha);
process.stdout.write(JSON.stringify(blueprintKnowledge(root, bp).problems));
"""
RULES = "doc/extensions/knowledge/constraints/sample-domain.md"


class KnowledgeApplicationsAreCheckedAgainstTheRealObjects(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(FIXTURE, "REQ-DEMO", DRAFT, self.root)

    def problems(self, mutate: str = "") -> list[str]:
        proc = subprocess.run(["node", "--input-type=module", "-e", SCRIPT, MODULE, ACCESS, str(self.root),
                               design_kit.blueprint_of(self.root, "REQ-DEMO"), mutate],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def test_the_admitted_fixture_holds(self) -> None:
        self.assertEqual([], self.problems())

    def test_an_applied_rule_needs_a_requirement_and_a_target(self) -> None:
        out = self.problems("const d = decisions.find(x => x.knowledge.outcome === 'applied');"
                            "delete d.knowledge.requirement; d.knowledge.target_refs = [];")
        self.assertTrue(any("形态不合" in p for p in out), out)

    def test_a_target_must_be_a_stable_address_of_this_design(self) -> None:
        out = self.problems("decisions.find(x => x.knowledge.outcome === 'applied').knowledge.target_refs = ['view:logical/node:nowhere'];")
        self.assertTrue(any("view:logical/node:nowhere" in p for p in out), out)

    def test_a_source_outside_the_activation_is_refused(self) -> None:
        out = self.problems("decisions[0].provenance.source_ref = 'doc/other/rules.md';")
        self.assertTrue(any("不是这一轮激活的知识文件" in p for p in out), out)

    def test_a_unit_not_in_the_file_is_refused(self) -> None:
        out = self.problems("decisions[0].knowledge.unit = 'SMP-99';")
        self.assertTrue(any("SMP-99" in p for p in out), out)

    def test_the_same_rule_judged_twice_is_named(self) -> None:
        out = self.problems("decisions.push({...structuredClone(decisions[0]), decision_id: 'dup'});"
                            "bp.decisions_and_gaps.decisions.push(decisions[decisions.length - 1]);")
        self.assertTrue(any("只判一次" in p for p in out), out)

    def test_a_red_line_cannot_be_waived(self) -> None:
        rules = self.root / RULES
        rules.write_bytes(rules.read_bytes().replace("| 上报失败只记本地日志，不阻断主流程 | 基线 |".encode("utf-8"),
                                                     "| 上报失败只记本地日志，不阻断主流程 | 红线 |".encode("utf-8")))
        waive = ("const d = decisions.find(x => x.knowledge.unit === 'SMP-02');"
                 "d.status = 'answered_with_evidence';"
                 f"Object.assign(d.knowledge, {{outcome: 'waived', source_sha256: sha('{RULES}'),"
                 "waiver: {reason: '旧页面下线在即', compensation: '下线前加提示', authority_ref: 'gate:scope'}});"
                 f"for (const x of decisions) x.knowledge.source_sha256 = sha('{RULES}');")
        out = self.problems(waive)
        self.assertTrue(any("红线，不能豁免" in p for p in out), out)

    def test_a_fact_read_from_knowledge_must_say_which_unit(self) -> None:
        """事实来源是激活的项目知识却没写 value.knowledge：报出来；来源是仓里代码的普通事实照原生形态，不要求它。"""
        fact = ("bp.discovery.facts.push({fact_id: 'f-from-knowledge', subject: 'module:WalletMain', value: {observation: '钱包主模块'},"
                " provenance: {source_kind: 'knowledge', source_ref: 'doc/extensions/knowledge/facts/sample-facts.md',"
                " observed_at: '2026-10-02T00:00:00Z', evidence_strength: 'observed', extraction_method: 'read'}});")
        out = self.problems(fact)
        self.assertTrue(any("f-from-knowledge" in p and "value.knowledge" in p for p in out), out)
        plain = fact.replace("source_kind: 'knowledge'", "source_kind: 'code'").replace(
            "doc/extensions/knowledge/facts/sample-facts.md", "02-Feature/WalletMain/src/main/ets/pages/Index.ets")
        self.assertEqual([], self.problems(plain))

    def test_a_pending_judgement_is_an_open_decision(self) -> None:
        out = self.problems("decisions[0].knowledge.outcome = 'pending';")
        self.assertTrue(any("形态不合" in p for p in out), "pending 却标成已作答")
        self.assertEqual([], self.problems("decisions[0].knowledge.outcome = 'pending';"
                                           "decisions[0].knowledge.target_refs = []; delete decisions[0].knowledge.requirement;"
                                           "decisions[0].status = 'open_decision';"))


if __name__ == "__main__":
    unittest.main()
