"""真实施工单位的知识承接正常链：蓝图里的适用性事实、设计对象上的义务与模式角色，经原生派生 / 物化 → 阶段解析 → 门禁与审查任务。

用 demo Framework 与夹具蓝图（`wallet-balance-refresh`）在临时工程里走原生入口：蓝图带产品生成的知识输入身份，
规约按域写适用性事实（OBS-02 适用，其余域整域不涉及），决策树模式有候选信号时写选中事实，
角色写在承担它的设计对象上（一个落在本施工单位的设计引用内、一个落在别处）；设计对象的契约里带 `must` / `pattern_roles`；
改过蓝图之后按原生的摘要口径更新施工单位的蓝图引用，再冻结范围。

锁的是：原生派生、复用本地物化件时，实体上的义务与角色都还在，并且被 plan 门禁与审查任务实际用上；
施工单位只承担落在自己设计引用内的角色；没有候选信号的模式零判断；测试的转译缓存钩子不改变结果；
设计对象不带验收或契约时由本阶段写出、经实际门禁与原生阶段解析，契约不在而用例权威在时 plan 仍按它对齐。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_knowledge_task import BLUEPRINT, CU, cu_id, make_project, prepare  # noqa: E402  —— 它把 test/scripts 放进导入路径
import design_kit  # noqa: E402

OBS = "doc/extensions/knowledge/constraints/observability.md"
#: 本施工单位承接的那条适用规约条目
KNOWLEDGE_REF = f"{OBS}#OBS-02"
#: 决策树模式：有候选信号时选中，声明的必需角色都有承担者：节点表落在本施工单位的设计对象上，其余落在别处
DECISION_TREE = "knowledge/design-patterns/decision-tree.md"
PATTERN_REF = f"doc/extensions/{DECISION_TREE}"
MODULE = "view:development/node:wallet-main-module"
#: 运行视图里的设计对象：由承担运行视图的另一个施工单位负责
ELSEWHERE = "view:runtime/node:background-sync"
ELSEWHERE_ROLES = ("上下文", "步骤枚举", "构建与启动")
#: 运行视图原来没有节点：放一个后台同步节点作为另一个施工单位的承担对象
RUNTIME_NODE = ("""    nodes:
      - node_id: background-sync
        owner: wallet-team
        current_state: HomeRepository loads data on page mount.
        target_state: HomeRepository loads data on page mount.
        design_basis_refs:
          - view:logical/node:wallet-balance
        provenance: *a2
        verification_refs:
          - verify:background-sync
""")
#: 只落在运行视图上的两条判断（另一个施工单位独有）：一条适用、一条不适用
ELSEWHERE_REF = f"{OBS}#OBS-05"
ELSEWHERE_QUIET = f"{OBS}#OBS-06"
#: 蓝图里登记的原生决定；两条待定都引它：一条只引它（承担对象未定），一条连同运行视图一起引（已知落在运行视图）
DECISION = "decision:balance-refresh-policy"
UNOWNED = f"{OBS}#OBS-03"
PENDING_ELSEWHERE = f"{OBS}#OBS-07"
#: 交付物规约里标「（评审动作）」的条目：只要归档动作与留痕，不产生代码要求
DELIVERABLES = "doc/extensions/knowledge/constraints/deliverables.md"
REVIEW_REF = f"{DELIVERABLES}#DLV-02"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def design(root: Path, with_roles: bool, pattern: str = "selected", elsewhere: bool = False, facts: bool = False,
           pending: bool = False, nested: bool = True, acceptance: bool = True, use_cases: bool = False,
           review: bool = False) -> str | None:
    """改夹具蓝图（按原文插入）：知识输入身份、适用性事实、设计对象契约上的义务与角色；再按原生口径（蓝图原字节的摘要与
    来源指纹）更新施工单位的蓝图引用。`pattern` 是决策树：selected（有候选信号，选中并写角色）/ none（没有候选信号，不判）。
    `elsewhere` 再加两条只落在运行视图上的规约判断（另一个施工单位独有）；`pending` 再加两条待定（见 `UNOWNED`、`PENDING_ELSEWHERE`）；
    `facts` 加两条项目事实 fact-1、fact-10：模块节点的验证引用写 fact-10 与一个合法的裸验收编号，正文提到 fact-1。
    `nested` 为假时模块节点不带机器契约（原生 contracts 投影为 absent，plan 阶段自己写契约），返回拿掉的那段契约原文；
    `acceptance` 为假时模块节点也不带验收（spec 阶段的验收投影为 absent，spec 自己写验收）；
    `use_cases` 给模块节点加一段用例权威（`USE_CASES`），契约不在时它仍是 plan 阶段要对齐的设计权威；
    `review` 再加一条适用的评审动作（`REVIEW_REF`），落点只指原生决定，不产生代码义务。"""
    canonical = root / "doc" / "features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
    old = sha(canonical)
    old_text = canonical.read_text(encoding="utf-8")
    text = old_text
    active = design_kit.active_constraints(root, design_kit.ACCESS)
    judgements = [design_kit.rule_judgement("OBS-02", "applied", "余额刷新是新增的业务过程，刷新失败要记一条可定位的日志")]
    if elsewhere:
        judgements += [design_kit.rule_judgement("OBS-05", "applied", "运行视图上的后台同步要上报结果", [ELSEWHERE]),
                       design_kit.rule_judgement("OBS-06", "not_applicable", "后台同步复用已有事件定义，不新增", [ELSEWHERE])]
    if pending:
        judgements += [design_kit.rule_judgement("OBS-03", "pending", "刷新失败要不要计入运维指标等运维定", [DECISION]),
                       design_kit.rule_judgement("OBS-07", "pending", "后台同步要不要单独采集等运营定", [ELSEWHERE, DECISION])]
    if review:
        judgements.append(design_kit.rule_judgement("DLV-02", "applied", "本需求新增对外开放的签约页，说明文档要归档", [DECISION]))
    if pattern == "selected":
        judgements.append(design_kit.pattern_judgement(DECISION_TREE, "selected", "刷新有多个分支，拆成节点",
                                                       [{"role": "节点表", "target_ref": MODULE},
                                                        *({"role": r, "target_ref": ELSEWHERE} for r in ELSEWHERE_ROLES)]))
    knowledge, attach = design_kit.knowledge_facts(judgements, active, False)
    runtime = "      - verify:runtime\n    nodes: []\n"
    assert text.count(runtime) == 1
    text = text.replace(runtime, "      - verify:runtime\n" + RUNTIME_NODE, 1)
    text = text.replace("  facts:\n", "  facts:\n" + knowledge, 1).replace(
        "  inputs:\n", "  inputs:\n    knowledge_context: "
        + json.dumps(design_kit.knowledge_context(root, design_kit.ACCESS), ensure_ascii=False) + "\n", 1)
    method = "                - name: refreshBalance\n"
    assert text.count(method) == 1
    text = text.replace(method, method + "                  must:\n                    - text: 刷新失败时记一条带页面与原因的日志\n"
                        f"                      source_ref: {KNOWLEDGE_REF}\n                      verify: ut\n", 1)
    if use_cases:
        anchor = "        contracts:\n          modules:"
        assert text.count(anchor) == 1
        text = text.replace(anchor, USE_CASES + anchor, 1)
    if not acceptance:
        start = text.index("        acceptance:\n          criteria:\n")
        end = text.index("          boundaries: []\n", start) + len("          boundaries: []\n")
        text = text[:start] + text[end:]
    removed = None
    if not nested:
        start, end = text.index("        contracts:\n          modules:"), text.index("  - view_id: deployment")
        removed, text = text[start:end], text[:start] + text[end:]
    elif with_roles and pattern == "selected":
        owner = "              class: HomeRepository\n"
        assert text.count(owner) == 1
        text = text.replace(owner, owner + "              pattern_roles:\n"
                            f"                - pattern_ref: {PATTERN_REF}\n                  role: 节点表\n", 1)
    assert text.endswith("derived_results: []\n")
    text += STAT_DETAIL
    if facts:
        text = with_facts(text)
    if attach:
        text = design_kit.with_entities(text, attach)
    canonical.write_bytes(text.encode("utf-8"))
    # 事实变了来源指纹跟着变：按原生算法重算，施工单位的蓝图引用记着它与原字节摘要，按原生口径一并更新
    proc = subprocess.run(["node", "--input-type=module", "-e", design_kit.REFINGERPRINT, str(root), str(design_kit.ACCESS),
                           BLUEPRINT, str(canonical)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stderr[-600:]
    unit = root / "doc" / "features" / BLUEPRINT / "balance-refresh" / "change-unit.yaml"
    stamp = lambda s: s.split("source_fingerprint: ", 1)[1].split("\n", 1)[0]  # noqa: E731
    unit.write_bytes(unit.read_bytes().replace(old.encode(), sha(canonical).encode())
                     .replace(stamp(old_text).encode(), stamp(canonical.read_text(encoding="utf-8")).encode()))
    return removed


#: 模块节点上的一段用例权威：一个用例、一个分支，分支引验收 AC-001（原生 use-cases 结构校验的必填项齐全）
USE_CASES = """        use_cases:
          schema_version: "2.1"
          use_cases:
            - id: balance_refresh
              description: 返回首页刷新余额
              coordinator: HomeRepository
              ui_bindings:
                - ui: HomePage
                  role: entry
                  subscribes: []
                  user_actions:
                    - trigger: 用户返回首页
                      calls: repository.refreshBalance
              data_boundaries:
                - name: wallet
                  type: WalletService
                  kind: cloud
                  methods:
                    - { name: queryBalance, params: [], returns: Balance, async: true }
              state_model:
                phases: [Idle, Refreshing, Done]
              branches:
                - id: refreshed
                  scenario: 返回首页后余额刷新
                  linked_acceptance: [AC-001]
"""


def with_facts(text: str) -> str:
    """两条项目事实与模块节点上的引用：验证引用里整项写 fact-10 与裸验收编号 AC-001，fact-1 只在正文里被提到。"""
    provenance = {"source_kind": "facts", "source_ref": "doc/extensions/knowledge/facts/event-tracking.md",
                  "observed_at": "2026-09-30T00:00:00Z", "evidence_strength": "observed", "extraction_method": "read_and_apply"}
    rows = "".join(f"    - fact_id: {fid}\n      subject: {subject}\n"
                   f"      value: {json.dumps({'observation': subject}, ensure_ascii=False)}\n"
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


class ChainCase(unittest.TestCase):
    WITH_ROLES = True
    PATTERN = "selected"
    ELSEWHERE = False
    FACTS = False
    PENDING = False
    NESTED = True
    ACCEPTANCE = True
    USE_CASES = False
    REVIEW = False
    STEPS: tuple[str, ...] = ("freeze",)

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        cls.removed = design(cls.root, cls.WITH_ROLES, cls.PATTERN, cls.ELSEWHERE, cls.FACTS, cls.PENDING, cls.NESTED,
                             cls.ACCEPTANCE, cls.USE_CASES, cls.REVIEW)
        for step in cls.STEPS:
            prepare(cls.root, step)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def probe(self, env: dict | None = None, fresh: bool = False) -> dict:
        """门禁、审查任务与作者任务读到的结果。类的原状态默认环境下只读一次；`fresh` 读改过之后的工程，读数不进缓存。"""
        cached = env is None and not fresh
        if cached and "_out" in self.__class__.__dict__:
            return self.__class__._out
        proc = subprocess.run(["node", "--input-type=module", "-e", PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        out = json.loads(proc.stdout)
        if cached:
            self.__class__._out = out
        return out

    @property
    def unit(self) -> Path:
        """施工单位的原生目录：阶段产物写在这里。"""
        return self.root / "doc" / "features" / BLUEPRINT / "balance-refresh"

    def variant(self, rel: str, text: str) -> Path:
        """本例的局部变体：在施工单位目录下写 `rel`，结束时恢复它原来的有无与字节，同组其它用例仍看原状态（变体读数用 `fresh`）。"""
        f = self.unit / rel
        before = f.read_bytes() if f.exists() else None
        made = next((d for d in reversed(f.parents) if not d.exists()), None)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

        def restore() -> None:
            if before is not None:
                f.write_bytes(before)
                return
            f.unlink(missing_ok=True)
            if made is not None:
                shutil.rmtree(made, ignore_errors=True)
        self.addCleanup(restore)
        return f


class TheDerivedUnitWithItsRole(ChainCase):
    """同一份前态：模块单位选中决策树并写了角色，原生阶段准备把蓝图契约写成本阶段的 contracts.yaml（与
    prepare-blueprint-design 同一函数）后冻结；改工程的用例用 `variant`，结束即恢复。实体上的义务与角色原样到门禁与审查任务。"""
    STEPS = ("materialize", "freeze")

    def test_obligations_and_roles_survive_derivation_and_are_used(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_REF, out["must"][0]["source_ref"])
        self.assertEqual([{"pattern_ref": PATTERN_REF, "role": "节点表"}], out["roles"])
        self.assertNotIn("契约还没建", out["gate"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])
        self.assertNotIn("没有实体承担", out["gate"], out["gate"])
        self.assertIn(f"| {KNOWLEDGE_REF} |", out["review"], "审查任务没按条目列出实体上的义务")
        self.assertIn("刷新失败时记一条带页面与原因的日志 · ut", out["review"])

    def test_the_plan_author_gets_the_carried_duties_before_the_knowledge_text(self) -> None:
        """plan 作者先拿到本单位承接的条目：理由、落点与这条允许的 verify（与门禁同一份规则），再是知识原文。"""
        author = self.probe()["author"]
        duties = author.split("## 3. 当前契约与义务", 1)[1].split("## 4. 激活知识：索引与本动作的原文", 1)[0]
        self.assertIn(f"`{KNOWLEDGE_REF}`（事实 knowledge-observability）", duties)
        self.assertIn("承担它的实体写 must（source_ref 照抄这条），verify 取", duties)
        self.assertIn(f"模式 `{PATTERN_REF}`", duties)
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

    # plan.md 逐点表的责任方法写「接口 class.方法 name」：契约声明的方法认得出，写错的方法照样被拒绝。

    def test_the_declared_method_passes_and_a_wrong_one_is_named(self) -> None:
        self.variant("plan/plan.md", "# 计划\n\n| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
                     "| 余额刷新 / 保存结果 | 成功 | HomeRepository.refreshBalance |\n"
                     "| 余额刷新 / 保存结果 | 拒绝 | HomeRepository.saveNothing |\n")
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("HomeRepository.saveNothing 在 contracts.yaml 的 interfaces[].methods[] 里找不到", gate)
        self.assertNotIn("HomeRepository.refreshBalance 在 contracts.yaml", gate)
        self.assertNotIn("逐点表里没有行", gate)

    def test_a_point_of_the_design_missing_from_the_table_is_named(self) -> None:
        """蓝图埋点明细的统计点在逐点表里没有行：点名那个统计点。"""
        self.variant("plan/plan.md", "# 计划\n\n| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
                     "| 别的点 | 成功 | HomeRepository.refreshBalance |\n")
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("逐点表里没有行：余额刷新 / 保存结果", gate)

    # spec「宿主扩展治理项」、plan「宿主扩展（可选）」：有 Markdown 时章在、承接的几类各有小节、规约编号引得到、
    # 逐点表在「埋点」小节里；作者与审查拿到本单位不承接的判断，用来写不适用与不选的理由。

    def write(self, phase: str, text: str) -> None:
        self.variant(f"{phase}/{phase}.md", text)

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
        self.assertIn(f"| {KNOWLEDGE_REF} |", review)
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

    def test_the_spec_numbers_its_children_under_their_parent(self) -> None:
        """spec 真实 post_check：带号子节不以父节号开头报出；无号的 Scope 与宿主扩展章、合法的自由编号不报。"""
        body = ("# 规格\n\n## 1. 概述\n\n### 1.1 范围\n\n## Scope 声明\n\n### Scope 模块清单\n\n"
                "## 3. 契约\n\n### 2.1 接口\n\n## 宿主扩展治理项\n\n### 规约\n\n" + RULES + "\n### 设计模式\n\n刷新分支按决策树编排。\n")
        self.write("spec", body)
        gate = self.spec_probe()["gate"]
        self.assertIn("spec.md：「### 2.1 接口」挂在「## 3. 契约」下，号却是 2.1", gate)
        self.assertNotIn("1.1 范围", gate)
        self.assertNotIn("Scope", gate)
        (self.unit / "spec" / "spec.md").write_text(body.replace("### 2.1 接口", "### 3.1 接口"), encoding="utf-8")
        self.assertNotIn("章节编号", self.spec_probe()["gate"])

    def test_the_plan_mapping_points_at_its_own_chapter(self) -> None:
        """plan 真实 post_check：「承载设计章」的「号. 章名」号与章名指不同章时报出；没有这一列不要求。"""
        host = ("\n## 宿主扩展（可选）\n\n### 规约落实到实体\n\n" + RULES
                + "\n### 设计模式选型与角色\n\n节点表由 HomeRepository 承担。\n\n### 埋点\n\n" + POINTS)
        mapping = "## 8. spec 功能映射表\n\n| spec 编号 | 承载设计章 |\n|---|---|\n| F1 | {ref} |\n"
        body = "# 计划\n\n## 1. 模块架构图\n\n略。\n\n## 3. 数据模型定义\n\n略。\n\n" + mapping + host
        self.write("plan", body.format(ref="3. 模块架构图"))
        gate = self.probe(fresh=True)["gate"]
        self.assertIn("plan.md：「承载设计章」列的「3. 模块架构图」对不上本文的章：「模块架构图」在本文是第 1 章", gate)
        plan = self.unit / "plan" / "plan.md"
        plan.write_text(body.format(ref="1. 模块架构图（入口）"), encoding="utf-8")
        self.assertNotIn("承载设计章", self.probe(fresh=True)["gate"])
        plan.write_text(body.replace("承载设计章", "实现模块").format(ref="3. 模块架构图"), encoding="utf-8")
        self.assertNotIn("对不上本文的章", self.probe(fresh=True)["gate"])

    def test_the_author_gets_the_judgements_it_does_not_carry(self) -> None:
        facts = self.probe()["author"].split("## 2. 有效事实与决定", 1)[1].split("## 3. 当前契约与义务", 1)[0]
        self.assertIn("需求级公共依据（不适用或拒绝，没有落点，不产生本单位义务）", facts)
        self.assertIn("→ not_applicable", facts)
        self.assertNotIn(f"`{KNOWLEDGE_REF}`", facts)
        self.assertNotIn(f"`{PATTERN_REF}`", facts)


class ADerivedContractIsAnInputUntilThePlanWritesIt(ChainCase):
    """只冻结、本阶段的 contracts.yaml 还没写出：原生选中的契约是蓝图派生的输入。作者任务按它列义务并写明还没写出；
    本阶段的规格（门禁读的那一份）没有契约，不拿输入当成本阶段已交的产物。"""

    def test_the_author_sees_the_input_and_the_stage_has_no_contract_yet(self) -> None:
        out = self.probe()
        self.assertIsNone(out["must"], "门禁读到了还没写出的契约")
        self.assertEqual([], out["addresses"])
        duties = out["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4. 激活知识：索引与本动作的原文", 1)[0]
        self.assertIn("契约来自 derive derive.blueprint-contracts（原生选中的输入）；本阶段要交的 contracts.yaml 还没写出", duties)
        self.assertIn(KNOWLEDGE_REF, duties, "作者看不到选中输入上的义务")


class AMissingOwnRoleIsNamed(ChainCase):
    """本单位承担的角色没有实体：点名那个角色，不点名别的施工单位的角色。"""
    WITH_ROLES = False
    STEPS = ("materialize", "freeze")

    def test_only_the_units_own_role_is_asked_for(self) -> None:
        gate = self.probe()["gate"]
        self.assertIn("「节点表」", gate)
        self.assertIn("没有实体承担", gate)
        self.assertNotIn("「上下文」", gate)


class NoPatternIsACandidate(ChainCase):
    """没有模式出现候选信号：零模式判断合法，任务不编角色，规约义务与模式知识原文照样送达，门禁不因没有角色而拒绝。"""
    PATTERN = "none"
    STEPS = ("materialize", "freeze")

    def test_no_role_is_invented_and_the_rule_still_arrives(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_REF, out["must"][0]["source_ref"])
        self.assertIsNone(out["roles"])
        self.assertEqual([], out["roleAddresses"])
        for gone in ("没有实体承担", "pattern_roles", "节点表", "模式"):
            self.assertNotIn(gone, out["gate"], out["gate"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])
        duties = out["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4. 激活知识：索引与本动作的原文", 1)[0]
        self.assertIn(f"`{KNOWLEDGE_REF}`", duties)
        self.assertNotIn("模式 `", duties)
        knowledge = out["author"].split("## 4. 激活知识：索引与本动作的原文", 1)[1]
        self.assertIn(PATTERN_REF, knowledge, "没有候选不等于不给模式知识原文")


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
        self.assertIn("- 事实 `fact-10`（", facts)
        self.assertNotIn("- 事实 `fact-1`（", facts)
        self.assertIn("需求里另有知识事实，与本单位的关联未明，只给定位：`fact-1`（WalletMain.Logger）", facts)
        proc = subprocess.run(["node", "--input-type=module", "-e", SPEC_PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        for text in (out["author"], json.loads(proc.stdout)["review"]):
            self.assertNotIn("找不到对象或事实", text, "合法的裸验收编号被判成指不到的事实")



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
  out[f] = { problems: j.problems, decisions: c.mine.map(d => d.source_ref).sort(), global: c.common.map(d => d.source_ref),
             roles: c.mine.flatMap(d => k.rolesOf(d, j.scope).map(r => r.role)).sort(),
             facts: author.split('## 2. 有效事实与决定')[1].split('## 3. 当前契约与义务')[0], author,
             review: (review.promptFragments ?? []).join('\\n') };
}
process.stdout.write(JSON.stringify(out));
"""


class SiblingUnitsInOneBlueprint(ChainCase):
    """同一蓝图两个施工单位：共同落点上的义务两边都承接，只落在一边设计责任内的角色与判断只归那一边；
    没有落点的需求级判断两边各拿一次，作者任务与审查任务按同一份作用域取。待定按承担实体归属，只引决定的是归属待核的公共缺口。"""
    STEPS = ()
    ELSEWHERE = True
    PENDING = True
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
        self.assertEqual(sorted([KNOWLEDGE_REF, PATTERN_REF]), out[CU]["decisions"], "模块单位漏了共同落点上的判断")
        self.assertEqual(sorted([KNOWLEDGE_REF, PATTERN_REF, ELSEWHERE_REF, ELSEWHERE_QUIET, PENDING_ELSEWHERE]), out[second]["decisions"],
                         "运行视图单位漏了它独有的判断")
        self.assertEqual(["节点表"], out[CU]["roles"], "运行视图上的角色被强给了不承担它的单位")
        self.assertEqual(sorted([*ELSEWHERE_ROLES, "节点表"]), out[second]["roles"], "承担运行视图的单位漏了它的角色")

    def test_each_unit_gets_the_whole_index_and_only_its_own_text(self) -> None:
        """两个单位都拿到完整索引；正文只送本单位判过、承接或待核的知识（spec 送上下篇的上篇），需求级的整域不涉及只在索引里。"""
        import re  # noqa: PLC0415
        out, second = self.sibling()
        registered = yaml.safe_load((self.root / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))["provides"]["knowledge"]
        for f in (CU, second):
            with self.subTest(unit=f):
                author = out[f]["author"]
                part = author.split("## 4. 激活知识：索引与本动作的原文", 1)[1].split("## 5. 本次完成条件", 1)[0]
                index = [line for line in part.splitlines() if line.startswith("- `doc/extensions/knowledge/")]
                self.assertEqual(len(registered), len(index), "索引没有列全激活知识")
                sent = set(re.findall(r"^- 位置：`doc/extensions/(knowledge/[^`]+)`", part, re.M))
                self.assertIn(OBS.removeprefix("doc/extensions/"), sent, "本单位承接与待核的规约没有正文")
                self.assertIn(DECISION_TREE, sent, "本单位承担角色的模式没有正文")
                self.assertLess(len(sent), len(registered), "施工单位拿到了全部知识的正文")
                # 夹具里两个单位承接、判过或待核的都在 observability 规约与 decision-tree 模式里；其余规约是需求级整域不涉及
                self.assertEqual({OBS.removeprefix("doc/extensions/"), DECISION_TREE}, sent)
                facts = out[f]["facts"]
                self.assertIn("需求级公共依据", facts, "夹具前提变了：没有需求级整域不涉及")
                pattern = part.split(f"`doc/extensions/{DECISION_TREE}`（", 1)[1].split("\n### ", 1)[0]
                self.assertIn("- 下面是：前言与上篇（另一篇按位置读原文）", pattern)

    def test_a_unit_text_kept_out_by_its_audience_is_named(self) -> None:
        """本单位承接的规约被登记的受众挡在本阶段之外：报登记与消费者冲突，不静默少送。"""
        manifest = self.root / "doc/extensions/manifest.yaml"
        original = manifest.read_bytes()
        self.addCleanup(manifest.write_bytes, original)
        rel = OBS.removeprefix("doc/extensions/")
        text = original.decode("utf-8")
        self.assertIn(f"    - {rel}\n", text)
        manifest.write_bytes(text.replace(f"    - {rel}\n", f"    - {{path: {rel}, audience: [coding]}}\n", 1).encode("utf-8"))
        proc = subprocess.run(["node", str(self.root / "doc/extensions/hooks/shared/knowledge-task.mjs"), "--project-root", str(self.root),
                               "--feature", CU, "--action", "spec", "--audience", "author"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        gaps = proc.stdout.split("## 6. 缺口与责任", 1)[1]
        self.assertIn(f"`{rel}`", gaps)
        self.assertIn("登记与消费者冲突", gaps)

    def test_another_units_judgement_stays_with_it(self) -> None:
        """B 独有的判断不进 A 的作者任务与审查任务；B 自己的审查判断表里有它。"""
        out, second = self.sibling()
        self.assertNotIn(ELSEWHERE_REF, out[CU]["author"])
        self.assertNotIn(ELSEWHERE_REF, out[CU]["review"])
        self.assertIn(f"| {ELSEWHERE_REF} |", out[second]["review"])
        self.assertNotIn(ELSEWHERE_REF, out[second]["facts"], "承接的适用判断在第 3 块，不在第 2 块重复")

    def test_a_judgement_without_duty_placed_on_another_unit_stays_there(self) -> None:
        """落在运行视图上的不适用只归运行视图单位：模块单位看不到，运行视图单位作为相关判断看到，不成义务。"""
        out, second = self.sibling()
        self.assertNotIn(ELSEWHERE_QUIET, out[CU]["author"])
        self.assertNotIn(ELSEWHERE_QUIET, out[CU]["review"])
        own = out[second]["facts"].split("本单位相关、不产生义务的判断（宿主扩展章引用其理由，不重判）：", 1)[1]
        self.assertIn(f"`{ELSEWHERE_QUIET}`", own)
        duties = out[second]["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4.", 1)[0]
        self.assertNotIn(ELSEWHERE_QUIET, duties)

    def test_a_requirement_level_judgement_is_given_once_and_marked(self) -> None:
        """没有落点的需求级判断：两个单位各拿一次，标明需求级，不说成本单位适用。"""
        out, second = self.sibling()
        for f in (CU, second):
            self.assertTrue(out[f]["global"], f)
            self.assertIn("需求级公共依据（不适用或拒绝，没有落点，不产生本单位义务）", out[f]["facts"])
            for d in out[f]["global"]:
                self.assertEqual(1, out[f]["facts"].count(f"`{d}`"), (f, d))
                self.assertEqual(1, out[f]["review"].count(f"| {d} |"), (f, d))
                row = next(line for line in out[f]["review"].splitlines() if line.startswith(f"| {d} |"))
                self.assertTrue(row.endswith(f"| 归属待核的公共知识缺口（{DECISION}） |" if d == UNOWNED
                                             else "| 需求级公共依据（无落点） |"), row)

    def test_a_pending_goes_by_its_entity_and_an_unowned_one_reaches_both(self) -> None:
        """待定连同运行视图一起引决定：只归运行视图单位，作为本单位相关的判断；只引决定的：两个单位都作为归属待核的缺口收到。"""
        out, second = self.sibling()
        for f in (CU, second):
            self.assertIn(UNOWNED, out[f]["global"], f)
            unowned = out[f]["facts"].split("归属待核的公共知识缺口", 1)[1]
            self.assertIn(f"`{UNOWNED}`", unowned, f)
            self.assertIn(DECISION, unowned, f)
        self.assertNotIn(PENDING_ELSEWHERE, out[CU]["author"])
        self.assertNotIn(PENDING_ELSEWHERE, out[CU]["review"])
        own = out[second]["facts"].split("本单位相关、不产生义务的判断（宿主扩展章引用其理由，不重判）：", 1)[1]
        self.assertIn(f"`{PENDING_ELSEWHERE}`", own.split("需求级公共依据", 1)[0])
        duties = out[second]["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4.", 1)[0]
        self.assertNotIn(PENDING_ELSEWHERE, duties, "待定成了已生效的义务")
        self.assertNotIn(UNOWNED, duties, "待定成了已生效的义务")


class ARequirementLevelReviewActionIsNamedAsSuch(ChainCase):
    """适用的评审动作落点只指原生决定：作者任务把它说成需求级评审动作（由评审承接，不产生代码 must），不归进「不适用、无义务」；
    它的规约原文送到，审查表的落点列同样写评审动作。"""
    REVIEW = True

    def test_the_review_action_is_neither_a_code_duty_nor_not_applicable(self) -> None:
        out = self.probe()
        facts = out["author"].split("## 2. 有效事实与决定", 1)[1].split("## 3. 当前契约与义务", 1)[0]
        reviews = facts.split("需求级评审动作（适用", 1)[1].split("\n\n", 1)[0]
        self.assertIn(f"`{REVIEW_REF}`", reviews)
        self.assertIn("→ applied", reviews)
        if "需求级公共依据（不适用或拒绝" in facts:
            basis = facts.split("需求级公共依据（不适用或拒绝", 1)[1].split("需求级判断（", 1)[0]
            self.assertNotIn(REVIEW_REF, basis, "适用的评审动作被说成不适用、无义务")
        duties = out["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4.", 1)[0]
        self.assertNotIn(REVIEW_REF, duties, "评审动作成了代码义务")
        knowledge = out["author"].split("## 4. 激活知识：索引与本动作的原文", 1)[1]
        self.assertIn(f"- 位置：`{DELIVERABLES}`", knowledge, "评审动作的规约原文没送到")
        spec = subprocess.run(["node", "--input-type=module", "-e", SIBLING_PROBE, str(self.root.as_posix()), CU],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, spec.returncode, spec.stderr[-600:])
        review = json.loads(spec.stdout)[CU]["review"]
        row = next(line for line in review.splitlines() if line.startswith(f"| {REVIEW_REF} |"))
        self.assertTrue(row.endswith(f"| 需求级评审动作（{DECISION}） |"), row)


class AUnitCarryingNoJudgementStillGetsTheShared(ChainCase):
    """只承担运行视图的施工单位：没有落在它设计责任内的判断，但需求级公共依据仍是它的判断依据，
    作者任务与审查判断表都列出；两组都空才说没有相关判断。"""
    STEPS = ()
    PATTERN = "none"
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

    def test_the_review_table_keeps_the_common_rows(self) -> None:
        lone = cu_id(BLUEPRINT, self.LONE)
        proc = subprocess.run(["node", "--input-type=module", "-e", SIBLING_PROBE, str(self.root.as_posix()), lone],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        out = json.loads(proc.stdout)[lone]
        self.assertEqual([], out["decisions"], "夹具变了：这个单位不该有落在它设计责任内的判断")
        self.assertTrue(out["global"], "夹具变了：要有需求级公共依据")
        self.assertNotIn("没有与本施工单位相关的知识判断", out["review"])
        for d in out["global"]:
            self.assertIn(f"| {d} |", out["review"])
            self.assertIn(f"`{d}`", out["facts"], "作者任务与审查表不同源")


class APlanWithoutAProjectionWritesItsOwnContract(ChainCase):
    """设计对象只带义务与角色、不带机器契约：原生 contracts 投影是 absent，plan 阶段不回蓝图补、自己写契约。
    作者任务说明由本阶段写；按设计写出的契约把承接的义务与角色落到实体上，plan 门禁照常核过。"""
    NESTED = False

    def test_the_task_hands_the_contract_to_the_plan_stage(self) -> None:
        out = self.probe()
        duties = out["author"].split("## 3. 当前契约与义务", 1)[1].split("## 4.", 1)[0]
        self.assertIn("设计没有给本施工单位的机器契约投影", duties)
        self.assertIn(KNOWLEDGE_REF, duties, "承接的适用条目没交给写契约的作者")

    def test_a_contract_the_plan_writes_carries_the_duties(self) -> None:
        body = yaml.safe_load(textwrap.dedent(self.removed))["contracts"]
        # plan 作者按第 3 块把本单位的角色落到承担它的实体上
        body["interfaces"][0]["pattern_roles"] = [{"pattern_ref": PATTERN_REF, "role": "节点表"}]
        self.variant("contracts.yaml", yaml.safe_dump(body, allow_unicode=True, sort_keys=False))
        got = self.probe(fresh=True)
        self.assertEqual(KNOWLEDGE_REF, (got["must"] or [{}])[0].get("source_ref"), got["problems"])
        self.assertNotIn("没有实体扛着", got["gate"], got["gate"])
        self.assertNotIn("没有实体承担", got["gate"], got["gate"])


#: 阶段实际消费者：原生阶段解析（本阶段与 plan）、本阶段门禁，plan 阶段再加原生的设计权威对齐（与原生 plan 检查同一函数）
STAGE_PROBE = """
import { pathToFileURL } from 'node:url';
const [root, feature, phase] = process.argv.slice(1);
const base = pathToFileURL(root + '/doc/extensions/hooks/').href;
const access = await import(base + 'shared/framework-access.mjs');
const gate = await (await import(base + phase + '/post_check.mjs')).default({ phase, feature, projectRoot: root });
const view = f => ({ status: f.status, issues: f.issues, inputs: Object.fromEntries(Object.entries(f.inputs).map(([k, v]) => [k, [v.state, v.binding?.source ?? null]])) });
const here = access.readFeature(root, feature, phase);
const n = access.loadNative(root);
const p = n.module('scripts/utils/blueprint-skill-projection.ts');
const drift = phase === 'plan' ? p.authoritativeContentDrift(root, feature, n.frameworkRoot, 'contracts', here.spec?.contracts ?? {}) : null;
process.stdout.write(JSON.stringify({ ...view(here), plan: view(access.readFeature(root, feature, 'plan')), gate: gate.message ?? '', ok: gate.ok !== false,
  drift: drift && { state: drift.state, items: (drift.items ?? []).map(i => [i.id, i.field]), expected: drift.items?.[0]?.expected ?? null } }));
"""

#: 模块节点验收的同一条（spec 作者按设计写出的验收）
ACCEPTANCE_TEXT = {"schema_version": "1.0", "feature": CU, "criteria": [{
    "id": "AC-001", "prd_function": None, "priority": "P0", "description": "返回首页时余额刷新", "testable": True,
    "verification_steps": ["切到其他页面后返回首页"], "expected_result": "账户卡片展示最新余额", "ut_layer": "device",
    "device_focus": "返回首页后账户卡片余额文本更新"}], "boundaries": []}


class StageCase(ChainCase):
    def stage(self, phase: str) -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", STAGE_PROBE, str(self.root.as_posix()), CU, phase],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)


class ASpecWithoutAnAcceptanceProjectionWritesItsOwn(StageCase):
    """设计对象既不带验收也不带契约：spec 阶段的验收投影是 absent，spec 自己写 acceptance.yaml。写出之前 plan 被原生挡在缺验收；
    写出的验收由 spec 门禁核承接，plan 阶段改按这份阶段产物解析验收。"""
    NESTED = False
    ACCEPTANCE = False

    def test_the_spec_writes_the_acceptance_and_the_plan_reads_it(self) -> None:
        before = self.stage("spec")
        self.assertEqual(("ok", ["absent", None]), (before["status"], before["inputs"]["acceptance"]), before)
        self.assertIn("acceptance=absent", json.dumps(before["plan"]["issues"], ensure_ascii=False))
        self.variant("acceptance.yaml", yaml.safe_dump(ACCEPTANCE_TEXT, allow_unicode=True, sort_keys=False))
        unbridged = self.stage("spec")
        self.assertIn(f"由本施工单位承接，没有验收条目承接——写一条 criteria，knowledge_refs 列 {KNOWLEDGE_REF}", unbridged["gate"])
        bridged = json.loads(json.dumps(ACCEPTANCE_TEXT))
        bridged["criteria"][0]["knowledge_refs"] = [KNOWLEDGE_REF]
        self.variant("acceptance.yaml", yaml.safe_dump(bridged, allow_unicode=True, sort_keys=False))
        after = self.stage("spec")
        self.assertTrue(after["ok"], after["gate"])
        artifact = ["resolved", {"kind": "artifact", "artifact": "acceptance@1"}]
        self.assertEqual((artifact, "ok"), (after["inputs"]["acceptance"], after["plan"]["status"]), after["plan"])
        self.assertEqual(artifact, after["plan"]["inputs"]["acceptance"])


class APlanUnderAUseCaseAuthority(StageCase):
    """设计对象不带契约、带一段用例权威：plan 的契约投影是 absent，但用例权威仍在。plan 写契约之外要按它写 use-cases.yaml；
    只写契约原生判用例漂移，照权威写齐才对齐，改了分支引用的验收则原生判漂移、plan 门禁点名那个验收编号。"""
    NESTED = False
    USE_CASES = True

    def test_the_use_case_authority_holds_when_the_plan_writes_its_contract(self) -> None:
        before = self.stage("plan")
        self.assertEqual(("ok", "absent"), (before["status"], before["inputs"]["contracts"][0]), before)
        self.assertEqual(("drift", [["use_cases:$", ""]]), (before["drift"]["state"], before["drift"]["items"]))
        authority = before["drift"]["expected"]
        self.assertEqual(["balance_refresh"], [u["id"] for u in authority["use_cases"]])
        body = yaml.safe_load(textwrap.dedent(self.removed))["contracts"]
        body["interfaces"][0]["pattern_roles"] = [{"pattern_ref": PATTERN_REF, "role": "节点表"}]
        self.variant("contracts.yaml", yaml.safe_dump(body, allow_unicode=True, sort_keys=False))
        contract_only = self.stage("plan")
        self.assertEqual(["resolved", {"kind": "artifact", "artifact": "contracts@1"}], contract_only["inputs"]["contracts"])
        self.assertEqual([["use_cases:$", ""]], contract_only["drift"]["items"], "契约 absent 时用例权威被丢了")
        written = {k: v for k, v in authority.items() if k != "source"}
        self.variant("use-cases.yaml", yaml.safe_dump(written, allow_unicode=True, sort_keys=False))
        aligned = self.stage("plan")
        self.assertEqual("aligned", aligned["drift"]["state"], aligned["drift"])
        self.assertTrue(aligned["ok"], aligned["gate"])
        written["use_cases"][0]["branches"][0]["linked_acceptance"] = ["AC-999"]
        self.variant("use-cases.yaml", yaml.safe_dump(written, allow_unicode=True, sort_keys=False))
        moved = self.stage("plan")
        self.assertEqual([["use_cases:refreshed", "linked_acceptance"]], moved["drift"]["items"])
        self.assertIn("use-cases.yaml 引了验收 AC-999（refreshed），acceptance.yaml 里没有这个编号", moved["gate"])


class TheMaterializedContractIsReused(ChainCase):
    """先物化本地契约再冻结：原生复用本地产物，实体上的义务与角色照样被读到。"""
    STEPS = ("materialize", "freeze")

    def test_the_materialized_contract_keeps_the_obligations(self) -> None:
        out = self.probe()
        self.assertEqual([], out["problems"], out["problems"])
        self.assertEqual(KNOWLEDGE_REF, out["must"][0]["source_ref"])
        self.assertTrue(out["roles"])
        self.assertNotIn("没有实体扛着", out["gate"], out["gate"])


if __name__ == "__main__":
    unittest.main()
