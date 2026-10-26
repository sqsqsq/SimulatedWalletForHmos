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
from test_knowledge_task import BLUEPRINT, CU, cu_id, make_project, prepare  # noqa: E402  —— 它把 test/scripts 放进导入路径
import design_kit  # noqa: E402

KNOWLEDGE_ID = "knowledge-obs-02"
PATTERN_ID = "pattern-decision-tree"
MODULE = "view:development/node:wallet-main-module"
ELSEWHERE = "view:runtime"
ELSEWHERE_ID = "knowledge-runtime-only"
ELSEWHERE_PENDING = "pattern-runtime-pending"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


#: 选型决定：两个角色，一个落在本施工单位的设计对象上，一个落在别处
DECISION_TREE = "knowledge/design-patterns/decision-tree.md"


def pattern_spec(mode: str) -> list[dict]:
    """决策树这个模式的判断：选中（带角色）、待定、拒绝交给夹具默认，漏判则连默认也不写。"""
    if mode == "selected":
        return [design_kit.pattern_decision(PATTERN_ID, DECISION_TREE, "selected", "刷新有多个分支，拆成节点", [MODULE],
                                            [{"role": "节点表", "target_ref": MODULE}, {"role": "上下文", "target_ref": ELSEWHERE}])]
    if mode == "pending":
        return [design_kit.pattern_decision(PATTERN_ID, DECISION_TREE, "pending", "分支是否多步要等接口定稿")]
    return []


def design(root: Path, with_roles: bool, pattern: str = "selected", elsewhere: bool = False, facts: bool = False) -> None:
    """改夹具蓝图（按原文插入，不整份重写）：逐条的知识判断、选型决定、设计对象契约上的义务与角色；
    再按原生口径（蓝图原字节的摘要）更新施工单位的蓝图引用。`pattern` 是决策树的判断：selected / pending /
    rejected（与其他模式一样按夹具默认有据拒绝）/ missing（激活模式一条判断都不写，漏判反例）。
    `elsewhere` 再加一条只落在运行视图上的适用规约与一条落在那里的待定模式（另一个施工单位独有）；
    `facts` 加两条知识事实 fact-1、fact-10：模块节点的验证引用写 fact-10 与一个合法的裸验收编号，正文提到 fact-1。"""
    canonical = root / "doc" / "features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
    old = sha(canonical)
    text = canonical.read_text(encoding="utf-8")
    active = design_kit.active_constraints(root, design_kit.ACCESS)
    other = next(u for c in active if c["kind"] == "constraints" for u in c["units"] if u != "OBS-02")
    other_pattern = next(c["file"] for c in active if c["kind"] == "patterns" and c["file"] != DECISION_TREE)
    extra = [design_kit.knowledge_decision(ELSEWHERE_ID, other, "applied", "运行视图上的后台同步要满足它",
                                           requirement="同步失败可回查", target_refs=[ELSEWHERE]),
             design_kit.pattern_decision(ELSEWHERE_PENDING, other_pattern, "pending", "后台同步的交互待定",
                                         [ELSEWHERE])] if elsewhere else []
    judged = design_kit.judged_rules(active, [design_kit.knowledge_decision(
        KNOWLEDGE_ID, "OBS-02", "applied", "余额刷新是新增的业务过程", requirement="刷新失败记一条可定位的日志"),
        *pattern_spec(pattern), *extra], False)
    if pattern == "missing":
        judged = [d for d in judged if "file" not in d]
    text = text.replace("decisions_and_gaps:\n  decisions:\n", "decisions_and_gaps:\n  decisions:\n"
                        + "".join(design_kit.decision_text(root, d, active) for d in judged), 1)
    method = "                - name: refreshBalance\n"
    assert text.count(method) == 1
    text = text.replace(method, method + "                  must:\n                    - rule: OBS-02\n"
                        f"                      decision_id: {KNOWLEDGE_ID}\n                      text: 刷新失败时记一条带页面与原因的日志\n"
                        "                      verify: ut\n", 1)
    if with_roles and pattern == "selected":
        owner = "              class: HomeRepository\n"
        assert text.count(owner) == 1
        text = text.replace(owner, owner + "              pattern_roles:\n                - pattern: decision-tree\n"
                            f"                  role: 节点表\n                  decision_id: {PATTERN_ID}\n", 1)
    assert text.endswith("derived_results: []\n")
    text += STAT_DETAIL
    if facts:
        text = with_facts(root, text)
    canonical.write_bytes(text.encode("utf-8"))
    if facts:
        proc = subprocess.run(["node", "--input-type=module", "-e", design_kit.REFINGERPRINT, str(root), str(design_kit.ACCESS),
                               BLUEPRINT, str(canonical)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert proc.returncode == 0, proc.stderr[-600:]
    unit = root / "doc" / "features" / BLUEPRINT / "balance-refresh" / "change-unit.yaml"
    refs = unit.read_bytes().replace(old.encode(), sha(canonical).encode())
    if facts:
        # 事实变了来源指纹跟着变：施工单位的蓝图引用记着它，按原生口径一并更新
        stamp = lambda s: s.split("source_fingerprint: ", 1)[1].split("\n", 1)[0]  # noqa: E731
        refs = refs.replace(stamp(text).encode(), stamp(canonical.read_text(encoding="utf-8")).encode())
    unit.write_bytes(refs)


def with_facts(root: Path, text: str) -> str:
    """两条知识事实与模块节点上的引用：验证引用里整项写 fact-10 与裸验收编号 AC-001，fact-1 只在正文里被提到。"""
    ref = "doc/extensions/knowledge/facts/event-tracking.md"
    knowledge = {"unit": "上篇", "form": "halves", "source_sha256": sha(root / ref)}
    provenance = {"source_kind": "facts", "source_ref": ref, "observed_at": "2026-09-30T00:00:00Z",
                  "evidence_strength": "observed", "extraction_method": "read_and_apply"}
    rows = "".join(f"    - fact_id: {fid}\n      subject: {subject}\n"
                   f"      value: {json.dumps({'observation': subject, 'knowledge': knowledge}, ensure_ascii=False)}\n"
                   f"      provenance: {json.dumps(provenance, ensure_ascii=False)}\n"
                   for fid, subject in (("fact-1", "WalletMain.Logger"), ("fact-10", "WalletMain.WalletHAManager")))
    for old, new in (("  facts:\n", "  facts:\n" + rows),
                     ("        verification_refs:\n          - verify:wallet-main-module\n",
                      "        verification_refs:\n          - verify:wallet-main-module\n          - fact-10\n          - AC-001\n"),
                     ("        current_state: no refresh trigger\n", "        current_state: no refresh trigger (see fact-1)\n")):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


#: 落在本施工单位模块上的埋点明细：带附加条件与多种结果
STAT_DETAIL = f"""story_details:
  - id: detail-balance-refresh-event
    kind: event
    title: 余额刷新埋点
    body: |
      刷新结果进统计。失败原因必须保留，拒绝时带上拒绝码。

      | 统计点 | 业务动作 | 实际适用结果 |
      |---|---|---|
      | 余额刷新 / 保存结果 | 返回首页 | 成功、拒绝 |
    evidence_refs:
      - {MODULE}
"""


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
const kt = await import(base + 'shared/knowledge-task.mjs');
const author = kt.knowledgeTask(root, { action: 'plan', audience: 'author', feature });
const o = await import(base + 'shared/obligations.mjs');
const addresses = o.obligationsFromContracts(a.contracts ?? {}).map(x => x.entityPath);
const roleAddresses = o.patternRolesFromContracts(a.contracts ?? {}).map(x => x.entityPath);
process.stdout.write(JSON.stringify({ must: i.methods?.[0]?.must ?? null, roles: i.pattern_roles ?? null, problems: a.problems,
  gate: gate.message ?? '', review: (review.promptFragments ?? []).join('\\n'), author, dir: a.dir, addresses, roleAddresses,
  resolved: [...addresses, ...roleAddresses].map(r => c.resolveEntityRef(a.contracts, r).ok) }));
"""


class ChainCase(unittest.TestCase):
    WITH_ROLES = True
    PATTERN = "selected"
    ELSEWHERE = False
    FACTS = False
    STEPS: tuple[str, ...] = ("freeze",)

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        design(cls.root, cls.WITH_ROLES, cls.PATTERN, cls.ELSEWHERE, cls.FACTS)
        for step in cls.STEPS:
            prepare(cls.root, step)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def probe(self, env: dict | None = None, fresh: bool = False) -> dict:
        """门禁、审查任务与作者任务读到的结果；同一类的工程不变，默认环境下只跑一次（`fresh` 在改过工程后重读）。"""
        if env is None and not fresh and "_out" in self.__class__.__dict__:
            return self.__class__._out
        proc = subprocess.run(["node", "--input-type=module", "-e", PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        out = json.loads(proc.stdout)
        if env is None:
            self.__class__._out = out
        return out


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

    def test_the_plan_author_gets_the_carried_duties_before_the_knowledge_text(self) -> None:
        """plan 作者先拿到本单位承接的判断：要求、落点与这条允许的 verify（与门禁同一份规则），再是知识原文。"""
        author = self.probe()["author"]
        duties = author.split("## 3. 当前契约与义务", 1)[1].split("## 4. 激活知识及原文", 1)[0]
        self.assertIn(f"`{KNOWLEDGE_ID}`（OBS-02", duties)
        self.assertIn("must 带 decision_id，verify 取", duties)
        self.assertIn(f"`{PATTERN_ID}`（模式 decision-tree", duties)
        self.assertIn("节点表 →", duties)

    def test_the_stat_detail_reaches_author_and_reviewer_in_full(self) -> None:
        """没有 plan.md：埋点明细正文、方法说明与验收完整条目原样送到 plan 作者与审查。"""
        out = self.probe()
        for who in ("author", "review"):
            for needle in ("失败原因必须保留，拒绝时带上拒绝码", "| 余额刷新 / 保存结果 | 返回首页 | 成功、拒绝 |",
                           "detail-balance-refresh-event；依据 " + MODULE, "`interfaces.HomeRepository.refreshBalance`：刷新余额",
                           "criteria `AC-001`", "expected_result：账户卡片展示最新余额", "device_focus：返回首页后账户卡片余额文本更新"):
                self.assertIn(needle, out[who], who)
        self.assertIn("这一次没有 plan.md：逐点核每个统计点", out["review"])

    def test_every_consumer_names_the_interface_by_its_class(self) -> None:
        """原生接口身份是 class：义务地址、接口角色地址、引用解析与审查任务都认 HomeRepository。"""
        out = self.probe()
        self.assertEqual(["interfaces.HomeRepository.refreshBalance"], out["addresses"])
        self.assertEqual(["interfaces.HomeRepository"], out["roleAddresses"])
        self.assertEqual([True, True], out["resolved"])
        self.assertIn("interfaces.HomeRepository.refreshBalance：刷新失败时记一条带页面与原因的日志", out["review"])
        self.assertNotIn("interfaces..", json.dumps(out, ensure_ascii=False))

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


class ThePlanTableNamesTheClassMethod(ChainCase):
    """plan.md 逐点表的责任方法写「接口 class.方法 name」：契约声明的方法认得出，写错的方法照样被拒绝。"""

    def test_the_declared_method_passes_and_a_wrong_one_is_named(self) -> None:
        plan = Path(self.probe()["dir"]) / "plan" / "plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("# 计划\n\n| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
                        "| 余额刷新 / 保存结果 | 成功 | HomeRepository.refreshBalance |\n"
                        "| 余额刷新 / 保存结果 | 拒绝 | HomeRepository.saveNothing |\n", encoding="utf-8")
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("HomeRepository.saveNothing 在 contracts.yaml 的 interfaces[].methods[] 里找不到", gate)
        self.assertNotIn("HomeRepository.refreshBalance 在 contracts.yaml", gate)
        self.assertNotIn("逐点表里没有行", gate)

    def test_a_point_of_the_design_missing_from_the_table_is_named(self) -> None:
        """蓝图埋点明细的统计点在逐点表里没有行：点名那个统计点。"""
        plan = Path(self.probe()["dir"]) / "plan" / "plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("# 计划\n\n| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
                        "| 别的点 | 成功 | HomeRepository.refreshBalance |\n", encoding="utf-8")
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("逐点表里没有行：余额刷新 / 保存结果", gate)


class AMissingOwnRoleIsNamed(ChainCase):
    """本单位承担的角色没有实体：点名那个角色，不点名别的施工单位的角色。"""
    WITH_ROLES = False

    def test_only_the_units_own_role_is_asked_for(self) -> None:
        gate = self.probe()["gate"]
        self.assertIn("「节点表」", gate)
        self.assertIn("没有实体承担", gate)
        self.assertNotIn("「上下文」", gate)


class EveryPatternIsRejected(ChainCase):
    """每个激活模式都有据拒绝：零选中角色合法，任务不编角色，规约义务与激活知识照样送达，门禁不因没有角色而拒绝。"""
    PATTERN = "rejected"

    def test_no_role_is_invented_and_the_rule_still_arrives(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_ID, out["must"][0]["decision_id"])
        self.assertIsNone(out["roles"])
        self.assertEqual([], out["roleAddresses"])
        for gone in ("没有实体承担", "pattern_roles", "节点表"):
            self.assertNotIn(gone, out["gate"], out["gate"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])
        duties = out["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4. 激活知识及原文", 1)[0]
        self.assertIn(f"`{KNOWLEDGE_ID}`（OBS-02", duties)
        self.assertNotIn("模式 decision-tree", duties)
        knowledge = out["author"].split("## 4. 激活知识及原文", 1)[1]
        self.assertIn("doc/extensions/knowledge/design-patterns/decision-tree.md", knowledge,
                      "没选模式不等于不给模式知识原文")



class AnUnjudgedPatternIsNamed(ChainCase):
    """激活模式一条判断都没有是漏判：门禁点名模式与上篇单元，交设计负责方补，不当作「没选中」放过。"""
    PATTERN = "missing"

    def test_the_gate_names_the_missing_pattern(self) -> None:
        out = self.probe()
        self.assertIn("没有判断激活模式", out["gate"])
        self.assertIn("decision-tree.md", out["gate"])
        self.assertIsNone(out["roles"])


class APendingPatternIsAJudgement(ChainCase):
    """待定是判断：不报漏判，不编角色；是否阻断按原生缺口与切片责任处理。"""
    PATTERN = "pending"

    def test_pending_is_not_reported_as_missing(self) -> None:
        out = self.probe()
        self.assertNotIn("没有判断激活模式", out["gate"])
        self.assertIsNone(out["roles"])

    def test_a_pending_without_target_is_undetermined_not_requirement_wide(self) -> None:
        """没有落点的待定不说成对整个需求成立：显示作用域未确定，并作为待设计处理项进缺口。"""
        author = self.probe()["author"]
        facts = author.split("## 2. 有效事实与决定", 1)[1].split("## 3. 当前契约与义务", 1)[0]
        undetermined = facts.split("作用域未确定的判断（没有落点，需设计负责方明确归属）：", 1)[1]
        self.assertIn(f"`{PATTERN_ID}`", undetermined)
        self.assertNotIn(f"`{PATTERN_ID}`", facts.split("作用域未确定的判断", 1)[0], "待定被放进了公共依据")
        self.assertNotIn("对整个需求成立", author)
        gaps = author.split("## 6. 缺口与责任", 1)[1]
        self.assertIn(f"判断 {PATTERN_ID}（上篇，pending）没有落点，作用域未确定", gaps)


FACT_PROBE = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const k = await import(pathToFileURL(root + '/doc/extensions/hooks/shared/knowledge-application.mjs').href);
const j = k.featureKnowledge(root, feature, null);
const c = k.unitContext(j);
process.stdout.write(JSON.stringify({ facts: c.facts.map(f => f.fact_id), located: c.located.map(f => f.fact_id), refs: j.scope.refs() }));
"""


class FactsBelongByTheirReferences(ChainCase):
    """事实按设计对象引用字段里的完整标识归属：fact-10 不连带 fact-1，正文里提到不算引用，没被引用的事实只给定位。
    引用字段是通用引用：验收编号这类裸标识不当成事实，也不判它不存在。作者与审查同一份取数。"""
    FACTS = True

    def test_only_the_whole_cited_id_belongs_to_the_unit(self) -> None:
        proc = subprocess.run(["node", "--input-type=module", "-e", FACT_PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        out = json.loads(proc.stdout)
        self.assertEqual(["fact-10"], out["facts"])
        self.assertEqual(["fact-1"], out["located"])
        self.assertIn("AC-001", out["refs"], "夹具的裸验收编号没进引用字段")

    def test_the_author_gets_the_cited_fact_and_a_locator_for_the_other(self) -> None:
        out = self.probe()
        self.assertEqual([], [p for p in out["problems"]], out["problems"])
        facts = out["author"].split("## 2. 有效事实与决定", 1)[1].split("## 3. 当前契约与义务", 1)[0]
        self.assertIn("- 事实 `fact-10`：", facts)
        self.assertNotIn("- 事实 `fact-1`：", facts)
        self.assertIn("需求里另有知识事实，与本单位的关联未明，只给定位：`fact-1`（WalletMain.Logger）", facts)
        proc = subprocess.run(["node", "--input-type=module", "-e", SPEC_PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        for text in (out["author"], json.loads(proc.stdout)["review"]):
            self.assertNotIn("找不到对象或事实", text, "合法的裸验收编号被判成指不到的事实")

SPEC_PROBE = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const base = pathToFileURL(root + '/doc/extensions/hooks/').href;
const spec = (await import(base + 'spec/post_check.mjs')).default;
const pre = (await import(base + 'shared/pre_verifier.mjs')).default;
const gate = await spec({ phase: 'spec', feature, projectRoot: root });
const review = await pre({ phase: 'spec', feature, projectRoot: root });
process.stdout.write(JSON.stringify({ gate: gate.message ?? '', review: (review.promptFragments ?? []).join('\\n') }));
"""

POINTS = ("| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
          "| 余额刷新 / 保存结果 | 成功 | HomeRepository.refreshBalance |\n"
          "| 余额刷新 / 保存结果 | 拒绝 | HomeRepository.refreshBalance |\n")
RULES = "| 编号 | 落实成什么 | 落点 |\n|---|---|---|\n| OBS-02 | 刷新失败记一条可定位的日志 | `HomeRepository.refreshBalance` |\n"


class TheHostChapterExplainsTheUnit(ChainCase):
    """spec「宿主扩展治理项」、plan「宿主扩展（可选）」：有 Markdown 时章在、承接的几类各有小节、规约编号引得到、
    逐点表在「埋点」小节里；作者与审查拿到本单位不承接的判断，用来写不适用与不选的理由。"""

    def write(self, phase: str, text: str) -> None:
        f = Path(self.probe()["dir"]) / phase / f"{phase}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        self.addCleanup(f.unlink)

    def spec_probe(self) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", SPEC_PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def test_a_spec_without_the_anchor_is_named(self) -> None:
        self.write("spec", "# 规格\n\n## 1. 概述\n\n刷新余额。\n")
        self.assertIn("spec.md：没有「宿主扩展治理项」章", self.spec_probe()["gate"])

    def test_the_spec_chapter_needs_its_sections_and_known_rules(self) -> None:
        self.write("spec", "# 规格\n\n## 宿主扩展治理项\n\n### 规约\n\n| 编号 | 判定 |\n|---|---|\n| OBS-02 | 适用，见 AC-001 |\n| ZZZ-99 | 适用，见 AC-999 |\n")
        gate = self.spec_probe()["gate"]
        self.assertIn("本单位承接设计模式，这一章下没有讲它的小节", gate)
        self.assertIn("ZZZ-99 不是设计判断过的规约", gate)
        self.assertNotIn("OBS-02 不是", gate)
        self.assertNotIn("本单位承接规约", gate)
        self.assertIn("引用的验收 AC-999 在 acceptance.yaml 里没有", gate)
        self.assertNotIn("AC-001 在", gate)

    def test_a_complete_spec_chapter_passes(self) -> None:
        self.write("spec", "# 规格\n\n## 宿主扩展治理项\n\n### 规约\n\n" + RULES + "\n### 设计模式\n\n刷新分支按决策树编排。\n\n## 附录\n")
        self.assertNotIn("宿主扩展治理项", self.spec_probe()["gate"])

    def test_the_spec_review_lists_judgements_the_unit_does_not_carry(self) -> None:
        review = self.spec_probe()["review"]
        self.assertIn(f"| {KNOWLEDGE_ID} |", review)
        self.assertIn("| 需求级公共依据（无落点） |", review)

    def test_the_plan_table_sits_in_the_events_section(self) -> None:
        self.write("plan", "# 计划\n\n## 宿主扩展（可选）\n\n### 规约落实到实体\n\n" + RULES
                   + "\n### 设计模式选型与角色\n\n节点表由 HomeRepository 承担。\n\n### 埋点\n\n" + POINTS)
        gate = self.probe(fresh=True)["gate"]
        for gone in ("宿主扩展（可选）」章", "没有讲它的小节", "逐点表不在", "不是设计判断过的规约"):
            self.assertNotIn(gone, gate)

    def test_the_plan_chapter_cites_real_acceptance(self) -> None:
        self.write("plan", "# 计划\n\n## 宿主扩展（可选）\n\n### 规约落实到实体\n\n" + RULES
                   + "\n验证见 AC-001 与 AC-999。\n\n### 设计模式选型与角色\n\n节点表由 HomeRepository 承担。\n\n### 埋点\n\n" + POINTS)
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("plan.md「宿主扩展（可选）」：引用的验收 AC-999 在 acceptance.yaml 里没有", gate)
        self.assertNotIn("AC-001 在", gate)

    def test_a_point_table_elsewhere_and_a_missing_section_are_named(self) -> None:
        self.write("plan", "# 计划\n\n## 9. 埋点\n\n" + POINTS + "\n## 宿主扩展（可选）\n\n### 规约落实到实体\n\n" + RULES)
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("的逐点表不在「宿主扩展（可选）」的「埋点」小节里", gate)
        self.assertIn("本单位承接埋点，这一章下没有讲它的小节", gate)
        self.assertIn("本单位承接设计模式，这一章下没有讲它的小节", gate)

    def test_the_author_gets_the_judgements_it_does_not_carry(self) -> None:
        facts = self.probe()["author"].split("## 2. 有效事实与决定", 1)[1].split("## 3. 当前契约与义务", 1)[0]
        self.assertIn("需求级公共依据（不适用或拒绝，没有落点，不产生本单位义务）", facts)
        self.assertIn("（not_applicable）", facts)
        self.assertNotIn(f"`{KNOWLEDGE_ID}`", facts)
        self.assertNotIn(f"`{PATTERN_ID}`", facts)

SIBLING_PROBE = """
import { pathToFileURL } from 'node:url';
const [root, ...features] = process.argv.slice(1);
const base = pathToFileURL(root + '/doc/extensions/hooks/').href;
const k = await import(base + 'shared/knowledge-application.mjs');
const kt = await import(base + 'shared/knowledge-task.mjs');
const pre = (await import(base + 'shared/pre_verifier.mjs')).default;
const out = {};
for (const f of features) {
  const j = k.featureKnowledge(root, f, null);
  const c = k.unitContext(j);
  const author = kt.knowledgeTask(root, { action: 'spec', audience: 'author', feature: f });
  const review = await pre({ phase: 'spec', feature: f, projectRoot: root });
  out[f] = { problems: j.problems, decisions: c.mine.map(d => d.decision_id).sort(), global: c.common.map(d => d.decision_id),
             roles: c.mine.flatMap(d => k.rolesOf(d, j.scope).map(r => r.role)).sort(),
             facts: author.split('## 2. 有效事实与决定')[1].split('## 3. 当前契约与义务')[0], author,
             review: (review.promptFragments ?? []).join('\\n') };
}
process.stdout.write(JSON.stringify(out));
"""


class SiblingUnitsInOneBlueprint(ChainCase):
    """同一蓝图两个施工单位：共同落点上的义务两边都承接，只落在一边设计责任内的角色与判断只归那一边；
    没有落点的需求级判断两边各拿一次，作者任务与审查任务按同一份作用域取。"""
    STEPS = ()
    ELSEWHERE = True
    SECOND = "balance-runtime"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        base = cls.root / "doc" / "features" / BLUEPRINT
        text = (base / "balance-refresh" / "change-unit.yaml").read_text(encoding="utf-8")
        text = text.replace("change_unit_id: balance-refresh", f"change_unit_id: {cls.SECOND}")
        head, tail = text.split("design_refs:\n", 1)
        refs, after = tail[:tail.index("touches:")], tail[tail.index("touches:"):]
        first = refs[:refs.index("  - artifact: component-blueprint@1", 4)]
        runtime = first.replace("  - &a1\n    artifact", "  - artifact").replace(
            "kind: node\n      id: wallet-main-module\n      view_id: development", "kind: view\n      id: runtime")
        (base / cls.SECOND).mkdir()
        (base / cls.SECOND / "change-unit.yaml").write_text(head + "design_refs:\n" + refs + runtime + after, encoding="utf-8")

    def sibling(self) -> tuple[dict, str]:
        if "_sibling" not in self.__class__.__dict__:
            second = cu_id(BLUEPRINT, self.SECOND)
            proc = subprocess.run(["node", "--input-type=module", "-e", SIBLING_PROBE, str(self.root.as_posix()), CU, second],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, proc.returncode, proc.stderr[-600:])
            self.__class__._sibling = (json.loads(proc.stdout), second)
        return self.__class__._sibling

    def test_each_unit_carries_its_own_and_the_shared_duties(self) -> None:
        out, second = self.sibling()
        for f in (CU, second):
            self.assertEqual([], out[f]["problems"], f)
        self.assertEqual(sorted([KNOWLEDGE_ID, PATTERN_ID]), out[CU]["decisions"], "模块单位漏了共同落点上的判断")
        self.assertEqual(sorted([KNOWLEDGE_ID, PATTERN_ID, ELSEWHERE_ID, ELSEWHERE_PENDING]), out[second]["decisions"],
                         "运行视图单位漏了它独有的判断")
        self.assertEqual(["节点表"], out[CU]["roles"], "运行视图上的角色被强给了不承担它的单位")
        self.assertEqual(["上下文", "节点表"], out[second]["roles"], "承担运行视图的单位漏了它的角色")

    def test_another_units_judgement_stays_with_it(self) -> None:
        """B 独有的判断不进 A 的作者任务与审查任务；B 自己的审查判断表里有它。"""
        out, second = self.sibling()
        self.assertNotIn(ELSEWHERE_ID, out[CU]["author"])
        self.assertNotIn(ELSEWHERE_ID, out[CU]["review"])
        self.assertIn(f"| {ELSEWHERE_ID} |", out[second]["review"])
        self.assertNotIn(ELSEWHERE_ID, out[second]["facts"], "承接的适用判断在第 3 块，不在第 2 块重复")

    def test_a_pending_placed_on_another_unit_stays_there(self) -> None:
        """落在运行视图上的待定只归运行视图单位：模块单位看不到，运行视图单位作为相关判断看到，不成义务。"""
        out, second = self.sibling()
        self.assertNotIn(ELSEWHERE_PENDING, out[CU]["author"])
        self.assertNotIn(ELSEWHERE_PENDING, out[CU]["review"])
        own = out[second]["facts"].split("本单位相关、不产生义务的判断（宿主扩展章引用其理由，不重判）：", 1)[1]
        self.assertIn(f"`{ELSEWHERE_PENDING}`", own)
        duties = out[second]["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4.", 1)[0]
        self.assertNotIn(ELSEWHERE_PENDING, duties)

    def test_a_requirement_level_judgement_is_given_once_and_marked(self) -> None:
        """没有落点的需求级判断：两个单位各拿一次，标明需求级，不说成本单位适用。"""
        out, second = self.sibling()
        for f in (CU, second):
            self.assertTrue(out[f]["global"], f)
            self.assertIn("需求级公共依据（不适用或拒绝，没有落点，不产生本单位义务）", out[f]["facts"])
            for d in out[f]["global"]:
                self.assertEqual(1, out[f]["author"].count(f"`{d}`"), (f, d))
                self.assertEqual(1, out[f]["review"].count(f"| {d} |"), (f, d))
                row = next(line for line in out[f]["review"].splitlines() if line.startswith(f"| {d} |"))
                self.assertTrue(row.endswith("| 需求级公共依据（无落点） |"), row)


class AUnitCarryingNoJudgementStillGetsTheShared(ChainCase):
    """只承担运行视图的施工单位：没有落在它设计责任内的判断，但需求级公共依据与作用域未确定的待定仍是它的判断依据，
    作者任务与审查判断表都列出；三组都空才说没有相关判断。"""
    STEPS = ()
    PATTERN = "pending"
    LONE = "balance-watch"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        base = cls.root / "doc" / "features" / BLUEPRINT
        text = (base / "balance-refresh" / "change-unit.yaml").read_text(encoding="utf-8")
        text = text.replace("change_unit_id: balance-refresh", f"change_unit_id: {cls.LONE}")
        head, tail = text.split("design_refs:\n", 1)
        refs, after = tail[:tail.index("touches:")], tail[tail.index("touches:"):]
        runtime = refs[:refs.index("  - artifact: component-blueprint@1", 4)].replace(
            "kind: node\n      id: wallet-main-module\n      view_id: development", "kind: view\n      id: runtime")
        (base / cls.LONE).mkdir()
        (base / cls.LONE / "change-unit.yaml").write_text(head + "design_refs:\n" + runtime + after, encoding="utf-8")

    def test_the_review_table_keeps_common_and_undetermined_rows(self) -> None:
        lone = cu_id(BLUEPRINT, self.LONE)
        proc = subprocess.run(["node", "--input-type=module", "-e", SIBLING_PROBE, str(self.root.as_posix()), lone],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        out = json.loads(proc.stdout)[lone]
        self.assertEqual([], out["decisions"], "夹具变了：这个单位不该有落在它设计责任内的判断")
        self.assertTrue(out["global"], "夹具变了：要有需求级公共依据")
        self.assertNotIn("没有与本施工单位相关的知识判断", out["review"])
        row = next((line for line in out["review"].splitlines() if line.startswith(f"| {PATTERN_ID} |")), "")
        self.assertTrue(row.endswith("| 作用域未确定（无落点，待设计负责方明确） |"), out["review"][-1500:])
        for d in out["global"]:
            self.assertIn(f"| {d} |", out["review"])
        self.assertIn("作用域未确定的判断（没有落点，需设计负责方明确归属）", out["facts"], "作者任务与审查表不同源")


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
