"""离线验证的固定入口（test/scripts/verify.py）：每个场景的命令、通道与先后由脚本定，调用方只选场景。

只核命令怎么拼、怎么分通道、按什么顺序求值，不真跑全量或失效形态。
"""
import argparse
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "test" / "scripts"))
import verify  # noqa: E402


def steps_of(scenario: str, **extra) -> list[tuple[str, list[str]]]:
    args = argparse.Namespace(scenario=scenario, targets=extra.get("targets", []), keyword=extra.get("keyword"))
    with mock.patch.object(verify, "build_template", return_value="TEMPLATE"):
        return [step for lane in verify.scenario(args) for group in lane for step in group(REPO)]


class EveryPytestRunIsParallel(unittest.TestCase):
    def test_full_and_affected_carry_the_parallel_arguments(self) -> None:
        for name, cmd in steps_of("full") + steps_of("affected", targets=["test_verify_entry.py"], keyword="parallel"):
            with self.subTest(step=name):
                self.assertIn("-n auto --dist loadscope", " ".join(cmd))
        self.assertIn("--durations", steps_of("full")[0][1])
        affected = steps_of("affected", targets=["test_verify_entry.py"], keyword="parallel")[0][1]
        self.assertIn(str(REPO / "test" / "tests" / "test_verify_entry.py"), affected, "只写文件名时没落到 test/tests")
        self.assertEqual(["-k", "parallel"], affected[-2:])

    def test_an_unknown_test_file_stops_before_running(self) -> None:
        with self.assertRaises(SystemExit):
            verify.affected_steps(["no_such_test.py"], None)


class TheHandbackRunsInLanes(unittest.TestCase):
    def test_full_failure_modes_and_the_rest_are_three_lanes(self) -> None:
        args = argparse.Namespace(scenario="handback", targets=[], keyword=None)
        with mock.patch.object(verify, "build_template", return_value="TEMPLATE"):
            lanes = [[name for group in lane for name, _ in group(REPO)] for lane in verify.scenario(args)]
        self.assertEqual([["full"], ["failure-modes"], ["cli-tests", "compileall", "validate-clis", "node-check"]], lanes)
        failure_modes = dict(steps_of("handback"))["failure-modes"]
        self.assertEqual(["--project-root", "TEMPLATE"], failure_modes[-2:], "失效形态没对现建的模板跑")

    def test_the_template_is_built_when_its_lane_starts(self) -> None:
        """排通道时不建模板：模板在失效形态那条通道开跑时才建，全量那条通道不碰它。"""
        args = argparse.Namespace(scenario="handback", targets=[], keyword=None)
        with mock.patch.object(verify, "build_template", side_effect=AssertionError("排通道时建了模板")):
            lanes = verify.scenario(args)
            lanes[0][0](REPO)
            lanes[2][0](REPO)

    def test_every_lane_reports_in_a_fixed_order(self) -> None:
        """通道同时跑、完成有先后，汇总仍按通道顺序，有一步失败退出码非 0。"""
        def fake_run(name, cmd, log_dir):
            return name, name != "compileall", f"[{name}]"
        with mock.patch.object(verify, "run", side_effect=fake_run), \
                mock.patch.object(verify, "build_template", return_value="TEMPLATE"), \
                mock.patch("sys.stdout"):
            code = verify.main(["handback"])
        self.assertEqual(1, code)


class CasesPlanEveryCase(unittest.TestCase):
    def test_jobs_equal_the_number_of_cases(self) -> None:
        cmd = steps_of("cases")[0][1]
        count = sum(1 for p in (REPO / "test" / "cases").iterdir() if (p / "case.yaml").is_file())
        self.assertEqual(["plan", "--all", "--jobs", str(count)], cmd[-4:])


if __name__ == "__main__":
    unittest.main()
