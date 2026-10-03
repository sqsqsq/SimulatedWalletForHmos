"""离线验证的固定入口（test/scripts/verify.py）：每个场景的命令与先后由脚本定，调用方只选场景。

只核命令怎么拼、按什么顺序求值，不真跑全量或失效形态。
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
        return [step for group in verify.scenario(args) for step in group(REPO)]


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


class TheHandbackRunsInOrder(unittest.TestCase):
    def test_full_suite_first_then_failure_modes_on_a_fresh_template_then_the_rest(self) -> None:
        names = [name for name, _ in steps_of("handback")]
        self.assertEqual(["full", "failure-modes", "cli-tests", "compileall", "validate-clis", "node-check"], names)
        failure_modes = dict(steps_of("handback"))["failure-modes"]
        self.assertEqual(["--project-root", "TEMPLATE"], failure_modes[-2:], "失效形态没对现建的模板跑")

    def test_the_template_is_built_only_when_its_turn_comes(self) -> None:
        args = argparse.Namespace(scenario="handback", targets=[], keyword=None)
        groups = verify.scenario(args)
        with mock.patch.object(verify, "build_template", side_effect=AssertionError("全量还没跑就建了模板")):
            groups[0](REPO)


class CasesPlanEveryCase(unittest.TestCase):
    def test_jobs_equal_the_number_of_cases(self) -> None:
        cmd = steps_of("cases")[0][1]
        count = sum(1 for p in (REPO / "test" / "cases").iterdir() if (p / "case.yaml").is_file())
        self.assertEqual(["plan", "--all", "--jobs", str(count)], cmd[-4:])


if __name__ == "__main__":
    unittest.main()
