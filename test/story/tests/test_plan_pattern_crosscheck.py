"""spec 登记的模式候选，在 plan 有没有给结论——以及不选时有没有写理由。

实测一轮：spec 正确登记了两条候选（业务信号真实），plan 用「演示仓储一步完成」
「加节点表会扩大文件面」把它们否了——拿临时承载形态当信号输入。否决在闭环内完成，
没有任何人过目。

这条判据只判**形式**两件事：命中的候选有没有行、不选时理由列空不空。
「理由引的是业务信号还是承载形态」是语义，归 verifier 逐问——用措辞正则去拦，
拦出来的是换一种说法的同一件事（上一轮已经实测过一次躲避）。
所以 F4 那两条**不该**被这条判据点名，它们有行也有理由；本文件因此正反两面都验：
真实存档不被误拦，构造的缺行与空理由被点名。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "doc" / "extensions" / "hooks" / "plan" / "post_check.mjs"
ARCHIVE = (REPO_ROOT / "test" / "story" / "design" / "2026-08-25-story分批次交付"
           / "batch-4-评审载体内容与表达" / "F4-形机器化与review承载" / "实跑-1"
           / "car-key-sharing" / "artifact")
FEATURE = "ISSUE-206"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [hookPath, feature, projectRoot] = process.argv.slice(-3);
const hook = (await import(pathToFileURL(hookPath).href)).default;
const out = await hook({ phase: 'plan', feature, projectRoot });
process.stdout.write(JSON.stringify(out));
"""


class PlanPatternCrossCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        if not (ARCHIVE / "plan" / "plan.md").is_file():
            raise unittest.SkipTest("F4 实跑存档不在，跳过（判据本身由构造反例守）")

    def workspace(self) -> Path:
        """把存档摆成一个 projectRoot：doc/extensions + doc/features/<feature>。

        存档是批次 4 的实跑产物，那时知识判断还写在 spec 的 §9.2/§9.3 两张表里。
        真源换成 `spec/knowledge-use.yaml` 之后，**不回头改存档**——历史轮次的产物
        是证据，改了就不是它当时的样子了。工作区里按那两张表现搭一份真源即可：
        判据读的是同一批结论，只是换了个入口。
        """
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(REPO_ROOT / "doc" / "extensions", tmp / "doc" / "extensions")
        link_harness_yaml(tmp)
        shutil.copytree(ARCHIVE, tmp / "doc" / "features" / FEATURE)
        self.write_knowledge_use(tmp)
        return tmp

    def write_knowledge_use(self, root: Path) -> None:
        """按存档 spec 的 §9.2/§9.3 现搭 `spec/knowledge-use.yaml`。

        激活清单里没出现在 §9.2 的条目逐条判不命中——完备性判据要求每条都有去处，
        而存档那一轮的 §9.2 只列命中项。
        """
        spec = (root / "doc" / "features" / FEATURE / "spec" / "spec.md")
        text = spec.read_text(encoding="utf-8")
        hits = self.table_rows(text, "规约约束要求")
        candidates = self.table_rows(text, "设计模式候选登记")

        rows = ["schema: 1", f'manifest_digest: "{self.digest(root)}"',
                "facts:", "  - id: component-profile",
                "    used:", "      - facet: 部件申明",
                "        used_for: 本部件的组件边界按它取", "constraints:"]
        hit_ids = {cells[0] for cells in hits if cells}
        for cells in hits:
            rows += [f"  - id: {cells[0]}", "    applicable: true",
                     f"    requirement: {self.one_line(cells[1])}"]
        for entry in self.active_entries(root):
            if entry in hit_ids:
                continue
            rows += [f"  - id: {entry}", "    applicable: false",
                     "    reason: 本轮的分享链路不触及这条约束管的那类改动"]
        rows.append("patterns:")
        for cells in candidates:
            rows += [f"  - unit: {self.one_line(cells[0])}",
                     f"    candidate: {self.one_line(cells[1])}",
                     f"    signal: {self.one_line(cells[2]) or '按存档登记'}"]
        (root / "doc" / "features" / FEATURE / "spec" / "knowledge-use.yaml").write_text(
            "\n".join(rows) + "\n", encoding="utf-8")

    @staticmethod
    def one_line(cell: str) -> str:
        """YAML 的纯量：去掉反引号与冒号后的歧义——这里只要能被读回来。"""
        return re.sub(r"[`*]", "", cell).replace(":", "：").strip()

    def table_rows(self, text: str, heading: str) -> list[list[str]]:
        rows = text.split("\n")
        start = next(i for i, l in enumerate(rows) if heading in l and l.startswith("#"))
        out = []
        for line in rows[start + 1:]:
            if line.startswith("#"):
                break
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]*", c) for c in cells):
                continue
            if cells[0] in ("编号", "适用单元"):
                continue
            out.append(cells)
        return out

    def node_eval(self, root: Path, expr: str) -> str:
        module = (root / "doc/extensions/hooks/shared/knowledge-use/document.mjs"
                  ).resolve().as_uri()
        km = (root / "doc/extensions/hooks/shared/knowledge.mjs").resolve().as_uri()
        proc = subprocess.run(
            ["node", "--input-type=module", "-e",
             f"const u = await import({json.dumps(module)});"
             f"const k = await import({json.dumps(km)});"
             f"const root = {json.dumps(root.as_posix())};"
             f"process.stdout.write(String({expr}));"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def digest(self, root: Path) -> str:
        return self.node_eval(root, "u.manifestDigest(root)")

    def active_entries(self, root: Path) -> list[str]:
        return self.node_eval(
            root, "k.activeKnowledge(root).entries.map(e => e.id).join(',')").split(",")

    def run_hook(self, root: Path) -> str:
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", DRIVER, "--",
             str(HOOK), FEATURE, str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        payload = json.loads(proc.stdout or "{}")
        return payload.get("message") or ""

    @staticmethod
    def plan_path(root: Path) -> Path:
        return root / "doc" / "features" / FEATURE / "plan" / "plan.md"

    def test_the_archive_is_not_falsely_named(self) -> None:
        """存档的两条候选有行也有理由——形式判不该碰它们。

        它们的病是「理由引的是承载形态」，那一格归 verifier；机器在这里越权下语义结论，
        换来的只是模型换一种说法。
        """
        message = self.run_hook(self.workspace())
        self.assertNotIn("plan 的设计模式选型表里没有这一行", message)
        self.assertNotIn("理由列是空的", message)

    def test_a_hit_candidate_missing_from_the_plan_table_is_named(self) -> None:
        """漏掉一行，那条候选就在闭环里悄悄消失了。"""
        root = self.workspace()
        path = self.plan_path(root)
        rows = path.read_text(encoding="utf-8").split("\n")
        keep = [r for r in rows if "decision-tree" not in r or not r.strip().startswith("|")]
        self.assertLess(len(keep), len(rows), "存档变了：选型表里没有 decision-tree 那一行")
        path.write_text("\n".join(keep), encoding="utf-8")
        self.assertIn("plan 的设计模式选型表里没有这一行", self.run_hook(root))

    def test_an_unselected_candidate_without_a_reason_is_named(self) -> None:
        """不选是表态有后果的决策——理由列不能空。"""
        root = self.workspace()
        path = self.plan_path(root)
        rows = path.read_text(encoding="utf-8").split("\n")
        hit = next(i for i, r in enumerate(rows)
                   if r.strip().startswith("|") and "decision-tree" in r)
        cells = rows[hit].strip().strip("|").split("|")
        cells[-1] = " "
        rows[hit] = "|" + "|".join(cells) + "|"
        path.write_text("\n".join(rows), encoding="utf-8")
        message = self.run_hook(root)
        self.assertIn("理由列是空的", message)
        self.assertIn("业务信号的反证", message)

    def test_no_candidate_rows_do_not_trigger(self) -> None:
        """spec 全写「无候选」时本判据不响——零命中是正常结论，不是遗漏。"""
        root = self.workspace()
        spec = root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        rows = spec.read_text(encoding="utf-8").split("\n")
        out = []
        for r in rows:
            if r.strip().startswith("|") and ("decision-tree" in r or "page-interaction" in r):
                cells = r.strip().strip("|").split("|")
                cells[1] = " 无候选 "
                r = "|" + "|".join(cells) + "|"
            out.append(r)
        spec.write_text("\n".join(out), encoding="utf-8")
        message = self.run_hook(root)
        self.assertNotIn("设计模式选型表里没有这一行", message)
        self.assertNotIn("理由列是空的", message)


class MultiCandidateUnits(PlanPatternCrossCheck):
    """同一单元两个候选是合法业务：各配各的行，谁被选谁被否都分得清。

    旧实现按单元单值记账——同单元第二个候选覆盖第一个，plan 只看最后一条，
    漏选的那个候选在闭环里悄悄消失。这里按 (单元, 候选) 逐对核：07 的七种局面
    各走各的应有结果，两类临时知识都用清单里在册的模式名，不绑某个业务。
    """

    UNIT = "多分支的凭证生成流程"

    def workspace_with_patterns(self, pattern_rows: list[str]) -> Path:
        root = self.workspace()
        use = root / "doc" / "features" / FEATURE / "spec" / "knowledge-use.yaml"
        text = use.read_text(encoding="utf-8")
        use.write_text(
            text.split("patterns:")[0] + "patterns:\n" + "\n".join(pattern_rows) + "\n",
            encoding="utf-8")
        return root

    def write_plan_table(self, root: Path, table_rows: list[str]) -> None:
        self.plan_path(root).write_text(
            "# 计划\n\n## 2. 模块架构图\n\n略。\n\n## 9. 宿主扩展\n\n### 9.1 知识决策（设计输入）\n\n#### 9.1.1 设计模式选型\n\n"
            "| 适用单元 | 候选 | 选 / 不选 | 实例名 | 理由 |\n"
            "|---|---|---|---|---|\n" + "\n".join(table_rows) +
            "\n\n#### 9.1.2 规约义务\n\n略。\n\n#### 9.1.3 项目知识影响\n\n略。\n", encoding="utf-8")

    def test_two_candidates_can_be_split_adopt_and_reject(self) -> None:
        """同单元双候选，一个采用一个拒绝（带理由）——两个结论都合法。"""
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
            f"  - unit: {self.UNIT}", "    candidate: page-interaction",
            "    signal: 步骤之间有先后驱动",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
            f"| {self.UNIT} | page-interaction | 不选 | | 分支之间没有业务结果驱动的先后，各步独立返回 |",
        ])
        message = self.run_hook(root)
        self.assertNotIn("没有这一行", message)
        self.assertNotIn("理由列是空的", message)
        self.assertNotIn("spec 没有提出它", message)
        self.assertNotIn("登记了两次", message)

    def test_two_candidates_both_adopted_pass(self) -> None:
        """组合采用也合法——两个候选各自有行、各自给结论。"""
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
            f"  - unit: {self.UNIT}", "    candidate: page-interaction",
            "    signal: 步骤之间有先后驱动",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
            f"| {self.UNIT} | page-interaction | 采用 | PageHost | 页内交互由业务结果驱动 |",
        ])
        self.assertNotIn("没有这一行", self.run_hook(root))

    def test_a_missing_second_choice_is_named(self) -> None:
        """双候选只给一个结论——另一个就在闭环里悄悄消失了。"""
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
            f"  - unit: {self.UNIT}", "    candidate: page-interaction",
            "    signal: 步骤之间有先后驱动",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
        ])
        self.assertIn("没有这一行", self.run_hook(root))

    def test_a_duplicated_pair_is_named_not_overwritten(self) -> None:
        """同一 unit+candidate 登记两次要报错——后写覆盖前写会让一个候选凭空消失。"""
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 另一段业务也要决策树",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
        ])
        self.assertIn("登记了两次", self.run_hook(root))

    def test_a_candidate_plan_adds_on_its_own_is_named(self) -> None:
        """plan 凭空加一个 spec 没提出的候选——选型只能从 spec 登记的候选里选。"""
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
            "| 另一段页面交互 | page-interaction | 采用 | PageHost | 想加就加 |",
        ])
        self.assertIn("spec 没有提出它", self.run_hook(root))

    def test_no_candidate_is_a_note_not_a_plan_invented_pattern(self) -> None:
        """「无候选」是说明不是模式身份：两侧同义，不进实际模式集合。

        真源（knowledge-use.yaml）与选型表都写「无候选／不选／不适用依据」时，
        反向检查不得把它当成 plan 凭空新增的模式——那会逼着作者删掉合理说明来过检查。
        """
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: 无候选",
            "    signal: 分支各自一步完成，没有贯穿多步的状态",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | 无候选 | 不选 | | 分支各自一步完成，没有贯穿多步的状态 |",
        ])
        message = self.run_hook(root)
        self.assertNotIn("spec 没有提出它", message, message)
        self.assertNotIn("没有这一行", message, message)
        self.assertNotIn("理由列是空的", message, message)
        self.assertNotIn("登记了两次", message, message)

    def test_a_duplicated_plan_row_is_named_and_not_overwritten(self) -> None:
        """plan 侧同一 (单元, 候选) 写两行要报错，且前行不被后行覆盖。

        先「不选且空理由」再「采用且有理由」：只报重复而不保留前行的话，
        空理由的那次表态就被后写悄悄盖掉了。
        """
        root = self.workspace_with_patterns([
            f"  - unit: {self.UNIT}", "    candidate: decision-tree",
            "    signal: 分支各自多步推进",
        ])
        self.write_plan_table(root, [
            f"| {self.UNIT} | decision-tree | 不选 | |",
            f"| {self.UNIT} | decision-tree | 采用 | TreeHost | 三个分支各自多步 |",
        ])
        message = self.run_hook(root)
        self.assertIn("写了两行", message, message)
        self.assertIn("理由列是空的", message, message)


if __name__ == "__main__":
    unittest.main()
