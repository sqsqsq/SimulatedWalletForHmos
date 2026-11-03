"""设计里的知识应用：形态按 knowledge-application.schema.json（原生 lite-json-schema 校验），知识输入身份、来源、
相关域逐条、稳定地址、实体上的义务与模式角色按实际对象核（hooks/shared/knowledge-application.mjs）。

用例在一份已交给设计、蓝图已准入的工程上改蓝图对象，看核对结论；夹具的准入本身已经过原生完整校验。
夹具的判断：样例规约域里 SMP-01 适用（落在设计对象上，那里写着出自它的 must）、SMP-02 不适用（同一域两种结果），
样例模式没有候选信号、不判。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT, REPO_ROOT
import design_kit
from designed_fixture import designed_copy

FIXTURE = REPO_ROOT / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"
MODULE = (DEV_EXT / "hooks" / "shared" / "knowledge-application.mjs").resolve().as_uri()
ACCESS = (DEV_EXT / "hooks" / "shared" / "framework-access.mjs").resolve().as_uri()
#: 读准入蓝图，按 argv 里的 JS 片段改它（变量 bp、rules：样例规约域的事实、node：夹具的设计对象），再核
SCRIPT = """
const [module, access, root, blueprintId, mutate] = process.argv.slice(1);
const { blueprintKnowledge } = await import(module);
const { readBlueprint } = await import(access);
const bp = structuredClone(readBlueprint(root, blueprintId, 'draft').blueprint);
const rules = bp.discovery.facts.find(f => String(f.provenance?.source_ref).endsWith('constraints/sample-domain.md'));
const node = bp.design_views.flatMap(v => v.nodes ?? []).find(n => n.node_id === 'wallet-balance');
const other = bp.design_views.flatMap(v => v.nodes ?? []).find(n => n.node_id === 'wallet-main-module');
new Function('bp', 'rules', 'node', 'other', mutate)(bp, rules, node, other);
process.stdout.write(JSON.stringify(blueprintKnowledge(root, bp).problems));
"""
RULES = "doc/extensions/knowledge/constraints/sample-domain.md"
PATTERN = "doc/extensions/knowledge/design-patterns/sample-pattern.md"
NODE = "view:logical/node:wallet-balance"
OTHER = "view:development/node:wallet-main-module"


class KnowledgeApplicationsAreCheckedAgainstTheRealObjects(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(FIXTURE, "REQ-DEMO", self.root)

    def problems(self, mutate: str = "") -> list[str]:
        proc = subprocess.run(["node", "--input-type=module", "-e", SCRIPT, MODULE, ACCESS, str(self.root),
                               design_kit.blueprint_of(self.root, "REQ-DEMO"), mutate],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def test_two_outcomes_in_a_related_domain_and_no_pattern_judgement_hold(self) -> None:
        """同一域两条不同结果、没成候选的模式零判断，都是合法设计。"""
        self.assertEqual([], self.problems("if (rules.value.items.map(i => i.outcome).join() !== 'applied,not_applicable')"
                                           " throw new Error('夹具变了');"
                                           "if (bp.discovery.facts.some(f => String(f.provenance?.source_ref).includes('design-patterns')))"
                                           " throw new Error('夹具不该判模式');"))

    def test_a_whole_domain_out_of_scope_is_one_reasoned_fact(self) -> None:
        self.assertEqual([], self.problems("rules.value = {knowledge_kind: 'constraints', outcome: 'not_applicable',"
                                           " rationale: '本需求没有新增入口，也没有上报动作'}; node.must = [];"))

    def test_a_related_domain_judges_every_entry_once(self) -> None:
        missing = self.problems("rules.value.items = rules.value.items.filter(i => i.unit === 'SMP-01');")
        self.assertTrue(any("没有逐条判断 SMP-02" in p for p in missing), missing)
        twice = self.problems("rules.value.items.push({...rules.value.items[1]});")
        self.assertTrue(any("SMP-02 写了两次" in p for p in twice), twice)
        alien = self.problems("rules.value.items[1].unit = 'SMP-99';")
        self.assertTrue(any("SMP-99 不在" in p for p in alien), alien)

    def test_one_fact_per_knowledge_file(self) -> None:
        out = self.problems("bp.discovery.facts.push({...structuredClone(rules), fact_id: 'dup'});")
        self.assertTrue(any("dup" in p and "一份知识一条适用性事实" in p for p in out), out)

    def test_an_applied_entry_needs_a_real_target(self) -> None:
        empty = self.problems("rules.value.items[0].target_refs = [];")
        self.assertTrue(any("形态不合" in p for p in empty), empty)
        nowhere = self.problems("rules.value.items[0].target_refs = ['view:logical/node:nowhere'];")
        self.assertTrue(any("view:logical/node:nowhere" in p for p in nowhere), nowhere)

    def test_a_pending_entry_points_at_a_native_decision_or_gap(self) -> None:
        out = self.problems(f"rules.value.items[1] = {{unit: 'SMP-02', outcome: 'pending', rationale: '上报要不要做等运营定',"
                            f" target_refs: ['{NODE}']}};")
        self.assertTrue(any("待定" in p and "decision / gap" in p for p in out), out)
        ok = ("bp.decisions_and_gaps.decisions.push({decision_id: 'report-or-not', kind: 'open_question', status: 'open_decision',"
              " owner: '需求负责人', rationale: '上报要不要做等运营定', provenance: rules.provenance, verification_refs: []});"
              "rules.value.items[1] = {unit: 'SMP-02', outcome: 'pending', rationale: '上报要不要做等运营定',"
              " target_refs: ['decision:report-or-not']};")
        self.assertEqual([], self.problems(ok))

    def test_a_source_under_the_extension_must_be_active_knowledge(self) -> None:
        out = self.problems("rules.provenance = {...rules.provenance, source_ref: 'doc/extensions/knowledge/constraints/retired.md'};")
        self.assertTrue(any("不是这一轮激活的知识文件" in p for p in out), out)

    def test_a_project_fact_cites_its_file_and_a_real_unit(self) -> None:
        fact = ("bp.discovery.facts.push({fact_id: 'f-from-knowledge', subject: 'module:WalletMain', value: {observation: '钱包主模块'},"
                " provenance: {source_kind: 'knowledge', source_ref: 'doc/extensions/knowledge/facts/sample-facts.md#UNIT',"
                " observed_at: '2026-10-02T00:00:00Z', evidence_strength: 'observed', extraction_method: 'read'}});")
        bad = self.problems(fact.replace("UNIT", "没有这一面"))
        self.assertTrue(any("f-from-knowledge" in p and "没有这一面" in p for p in bad), bad)
        self.assertEqual([], self.problems(fact.replace("#UNIT", "")))

    def test_a_selected_pattern_needs_declared_roles_on_real_objects(self) -> None:
        select = (f"bp.discovery.facts.push({{fact_id: 'k-pattern', subject: 'knowledge:sample-pattern',"
                  " value: {knowledge_kind: 'patterns', outcome: 'selected', rationale: '刷新有多个分支'},"
                  f" provenance: {{...rules.provenance, source_ref: '{PATTERN}'}}}});")
        no_roles = self.problems(select)
        self.assertTrue(any("k-pattern" in p and "节点表、上下文 没有实体承担" in p for p in no_roles), no_roles)
        one = self.problems(select + f"node.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '节点表'}}];")
        self.assertTrue(any("必需角色 上下文 没有实体承担" in p for p in one), one)
        both = (f"node.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '节点表'}}];"
                f"other.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '上下文'}}];")
        self.assertEqual([], self.problems(select + both))
        on_view = self.problems(select + f"node.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '节点表'}}];"
                                f"bp.design_views.find(v => v.view_id === 'logical').pattern_roles = [{{pattern_ref: '{PATTERN}', role: '上下文'}}];")
        self.assertTrue(any("view:logical" in p and "整个视图" in p for p in on_view), on_view)
        undeclared = self.problems(select + f"node.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '编排器'}}];")
        self.assertTrue(any("编排器" in p and "声明的角色" in p for p in undeclared), undeclared)
        unselected = self.problems(f"node.pattern_roles = [{{pattern_ref: '{PATTERN}', role: '节点表'}}];")
        self.assertTrue(any("没有选中的适用性事实" in p for p in unselected), unselected)

    def test_an_applied_entry_has_its_must_on_each_bearer(self) -> None:
        """适用条目与承担它的对象双向对上：落点上要有出自它的 must，must 挂的对象要在落点里，落点是具体设计对象。"""
        dropped = self.problems("node.must = [];")
        self.assertTrue(any("SMP-01 适用、落在 " + NODE in p and "没有出自它的 must" in p for p in dropped), dropped)
        stray = self.problems(f"other.must = [{{text: '模块里也生成编号', source_ref: '{RULES}#SMP-01', verify: 'review'}}];")
        self.assertTrue(any(OTHER in p and "落点" in p and "没有 " + OTHER in p for p in stray), stray)
        both = (f"rules.value.items[0].target_refs = ['{NODE}', '{OTHER}'];"
                f"other.must = [{{text: '模块透传编号', source_ref: '{RULES}#SMP-01', verify: 'review'}}];")
        self.assertEqual([], self.problems(both))
        view = self.problems("rules.value.items[0].target_refs = ['view:logical'];"
                             f"bp.design_views.find(v => v.view_id === 'logical').must = [{{text: 'x', source_ref: '{RULES}#SMP-01', verify: 'review'}}];")
        self.assertTrue(any("view:logical" in p and "整个视图" in p for p in view), view)
        only_decision = self.problems("bp.decisions_and_gaps.decisions.push({decision_id: 'who-numbers', kind: 'open_question',"
                                      " status: 'open_decision', owner: '需求负责人', rationale: '编号由谁生成待定',"
                                      " provenance: rules.provenance, verification_refs: []});"
                                      "rules.value.items[0].target_refs = ['decision:who-numbers']; node.must = [];")
        self.assertTrue(any("SMP-01 适用，却没有承担它的设计对象" in p for p in only_decision), only_decision)

    def test_a_must_comes_from_an_applied_entry_with_a_fitting_verify(self) -> None:
        self.assertEqual([], self.problems(f"node.must = [{{text: '入口生成受理单编号', source_ref: '{RULES}#SMP-01', verify: 'review'}}];"))
        not_applied = self.problems(f"node.must = [{{text: '失败降级', source_ref: '{RULES}#SMP-02', verify: 'review'}}];")
        self.assertTrue(any("SMP-02" in p and "not_applicable" in p for p in not_applied), not_applied)
        unknown = self.problems(f"node.must = [{{text: 'x', source_ref: '{RULES}#SMP-99', verify: 'review'}}];")
        self.assertTrue(any("SMP-99" in p for p in unknown), unknown)

    def test_the_knowledge_context_is_this_rounds(self) -> None:
        missing = self.problems("delete bp.discovery.inputs.knowledge_context;")
        self.assertTrue(any("knowledge_context" in p for p in missing), missing)
        rules = self.root / RULES
        rules.write_bytes(rules.read_bytes() + "\n补一条附注。\n".encode("utf-8"))
        changed = self.problems()
        self.assertTrue(any("原文变了" in p and RULES in p for p in changed), changed)


if __name__ == "__main__":
    unittest.main()
