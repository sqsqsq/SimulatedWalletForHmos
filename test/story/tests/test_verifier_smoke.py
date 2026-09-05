# -*- coding: utf-8 -*-
"""verifier smoke 的离线判据：不启动 CLI，只锚「夹具与判定逻辑本身是不是可信的」。

真实实跑贵且慢，所以三件事必须先在离线锚死，否则实跑失败时分不清是被测对象的问题还是夹具的问题：

1. **回复表按 registry 的 portable 文案匹配**——匹配键必须在 `confirmation-registry.yaml` 里
   真实存在。写错一个字，实跑时那一关就永远不命中，表现为「模型卡在那儿不动」；
2. **未知确认停等，不盲答**——没有条目命中就停，这是「确认发生在正确时机」这条判据的地基；
3. **链路校验只认磁盘原件**，且每一种绑定不成立的形态都判 FAIL——只测 happy path 的话，
   实跑里一份没绑上的报告会被当成通过。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
SMOKE = REPO / "test" / "story" / "verifier-smoke"
REGISTRY = REPO / "framework" / "skills" / "reference" / "confirmation-registry.yaml"

sys.path.insert(0, str(SMOKE))
import run_smoke  # noqa: E402

SUBJECT = "a" * 64
OTHER = "b" * 64


class SmokeFixture(unittest.TestCase):
    def test_reply_match_keys_exist_in_confirmation_registry(self):
        """匹配键必须是 registry 里真实的 portable 文案片段。

        写错一个字，实跑时那一关永远不命中——现场只表现为「模型停在那儿」，
        没有任何信号说是回复表的问题。
        """
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        entries = {}
        for group in registry.values():
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, dict) and "id" in item:
                        entries[item["id"]] = item
        for rule in run_smoke.load_replies():
            with self.subTest(rule=rule.id):
                self.assertIn(rule.id, entries, f"{rule.id} 不是 registry 里的确认点")
                portable = entries[rule.id].get("portable_menu", "")
                options = " ".join(o.get("portable", "") for o in entries[rule.id].get("options", []))
                haystack = (portable + " " + options).replace(" ", "")
                self.assertIn(rule.match.replace(" ", ""), haystack,
                              f"{rule.id} 的 match「{rule.match}」在 registry 文案里找不到")

    def test_every_reply_is_a_listed_option(self):
        """回复值必须落在该确认点的选项编号范围内，不能是自由文本。"""
        for rule in run_smoke.load_replies():
            if rule.fixture_failure:
                continue
            with self.subTest(rule=rule.id):
                self.assertRegex(rule.reply, r"^[1-9]$", f"{rule.id} 的回复不是编号选项")

    def test_unknown_confirmation_is_not_answered(self):
        """出现夹具没预备的确认点时不许猜——这条塌了，「确认时机」判据就是摆设。"""
        rules = run_smoke.load_replies()
        unknown = "请选择处理方式：\n1=合并到现有模块 2=新建模块 3=先不定"
        self.assertIsNone(run_smoke.match_reply(unknown, rules))
        self.assertTrue(run_smoke.looks_like_question(unknown))

    def test_narration_is_not_mistaken_for_a_question(self):
        """模型自述推进不是提问：误判会让驱动把编号当答案投出去。"""
        rules = run_smoke.load_replies()
        narration = "我已经读完需求，现在开始整理术语映射表。"
        self.assertIsNone(run_smoke.match_reply(narration, rules))
        self.assertFalse(run_smoke.looks_like_question(narration))

    def test_each_registered_confirmation_matches_its_own_rule(self):
        """每条规则只认自己那一关，不串台。"""
        rules = run_smoke.load_replies()
        samples = {
            "feature.track": "请判档：\n1=接受建议档 2=升 full 3=保持 lite",
            "spec.terminology": "术语映射表待确认：\n1=全部确认 high 行 2=逐行确认 3=逐行修改",
            "spec.freeze": "spec 已完成：\n1=冻结 spec，可进 plan 2=继续改 spec",
            "phase.next_step": "spec 已闭环：\n1=执行 assess 推荐动作 2=暂停 3=其它（说明）",
        }
        for rule_id, text in samples.items():
            with self.subTest(rule=rule_id):
                hit = run_smoke.match_reply(text, rules)
                self.assertIsNotNone(hit, f"{rule_id} 的样例没命中任何规则")
                self.assertEqual(rule_id, hit.id)

    def test_feature_path_conflict_is_classified_as_fixture_failure(self):
        """干净 workspace 不该有路径冲突：出现即夹具问题，不能记成 D1 失败。"""
        rules = run_smoke.load_replies()
        hit = run_smoke.match_reply("检测到冲突路径：\n1=换 feature 名 2=清理/恢复路径", rules)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.fixture_failure)

    def test_fixture_project_is_self_consistent(self):
        """合成工程三份文档与配置互相对得上，且确实是不挂 Extension 的 generic 工程。"""
        cfg = json.loads((SMOKE / "fixture" / "framework.config.json").read_text(encoding="utf-8"))
        self.assertEqual("generic", cfg["project_profile"]["name"],
                         "换成别的 profile 会把 UI/视觉/编译门一起拉进来")
        self.assertNotIn("extension_dir", cfg["paths"], "smoke 工程不挂 Extension")
        layers = {l["id"] for l in cfg["architecture"]["outer_layers"]}

        catalog = yaml.safe_load((SMOKE / "fixture" / "doc" / "module-catalog.yaml").read_text(encoding="utf-8"))
        modules = {m["name"] for m in catalog["modules"]}
        for m in catalog["modules"]:
            self.assertIn(m["layer"], layers, f"{m['name']} 的 layer 不在架构声明里")

        glossary = yaml.safe_load((SMOKE / "fixture" / "doc" / "glossary.yaml").read_text(encoding="utf-8"))
        for term in glossary["terms"]:
            self.assertIn(term["canonical_module"], modules,
                          f"术语「{term['term']}」指向了 Catalog 里没有的模块")

    def test_every_fixture_file_is_versioned(self):
        """夹具文件一个都不能被 .gitignore 吞掉。

        实测踩过：`framework.local.json` 命中 `.gitignore` 的个人 setup 规则，本地跑得好好的，
        新克隆却造不出 workspace，且没有任何提示。所以这条按机械回归守，不靠记忆。
        """
        files = [p for p in (SMOKE / "fixture").rglob("*") if p.is_file()]
        self.assertTrue(files, "夹具目录是空的")
        proc = subprocess.run(
            ["git", "check-ignore", *[str(p) for p in files]],
            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
        )
        ignored = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual([], ignored, f"这些夹具文件进不了版本库：{ignored}")

    def test_fixture_prompt_carries_all_six_rules(self):
        """六条需求由夹具冻结：少一条，实跑观察到的就不是同一个需求。"""
        prompt = (SMOKE / "fixture" / "prompt.md").read_text(encoding="utf-8")
        for fragment in ("默认关闭", "****", "重启后保持", "清除应用数据",
                         "不上传服务端", "不改变卡片余额"):
            self.assertIn(fragment, prompt)
        self.assertIn("hide-balance-toggle", prompt)


class SmokeChainVerification(unittest.TestCase):
    """verify() 只从磁盘原件重建链路——每种绑定不成立的形态都必须判 FAIL。

    报告由**调用方**原样写出，落点写在 `summary.verifier_report`：没有钩子代它发布，
    所以「谁发布的」「子会话是不是独立的」这两面在仓内没有对象了。
    留下的是三件仍然可核的事：落点声明了没有、那份 MD 写了没有、
    它的终态块认不认这一版产物。
    """

    def _ws(self, tmp, *, summary_subject=SUBJECT, landing: bool = True,
            report: str | None = None, request: bool = True):
        ws = tmp / "ws"
        reports = ws / "doc" / "features" / run_smoke.FEATURE / run_smoke.PHASE / "reports"
        reports.mkdir(parents=True)
        summary = {"schema_version": "2.0"}
        if summary_subject:
            summary["verifier_subject_id"] = summary_subject
        rel = (f"doc/features/{run_smoke.FEATURE}/{run_smoke.PHASE}/reports"
               f"/verifier.report.{summary_subject}.md")
        if landing and summary_subject:
            summary["verifier_report"] = rel
        (reports / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        if request and summary_subject:
            (reports / f"verifier.request.{summary_subject}.json").write_text("{}", encoding="utf-8")
        if report is not None:
            (ws / rel).write_text(report, encoding="utf-8")
        return ws

    @staticmethod
    def _good_report(subject=SUBJECT) -> str:
        return ("审查结论：通过。\n\n"
                "<!-- maison-verifier-result:v1 -->\n"
                f"verifier_subject_id: {subject}\n"
                "verdict: PASS\nblocker_count: 0\n"
                "<!-- /maison-verifier-result:v1 -->\n")

    def _ids(self, ws) -> dict:
        return {c["id"]: c["status"] for c in run_smoke.verify(ws, quiet=True)["checks"]}

    def test_missing_subject_is_reported_as_no_request(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self._ws(Path(d), summary_subject=None)
            self.assertEqual("FAIL", self._ids(ws)["request_generated"])

    def test_a_summary_without_a_landing_fails(self):
        """没有落点 = 本宿主没登记审查员；冒烟跑的是登记过的那台，缺了就是链路断了。"""
        with tempfile.TemporaryDirectory() as d:
            ws = self._ws(Path(d), landing=False)
            self.assertEqual("FAIL", self._ids(ws)["report_landing_declared"])

    def test_a_declared_landing_with_no_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self._ws(Path(d))
            self.assertEqual("FAIL", self._ids(ws)["report_written"])

    def test_subject_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self._ws(Path(d), report=self._good_report(OTHER))
            self.assertEqual("FAIL", self._ids(ws)["subject_bound"])

    def test_a_bound_report_passes_the_binding_checks(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self._ws(Path(d), report=self._good_report())
            ids = self._ids(ws)
            for cid in ("request_generated", "request_on_disk",
                        "report_landing_declared", "report_written", "subject_bound"):
                self.assertEqual("PASS", ids[cid], cid)


if __name__ == "__main__":
    unittest.main()
