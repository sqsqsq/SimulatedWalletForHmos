"""离线验证的固定入口（test/scripts/verify.py）：每个场景的命令、通道、并发上限与先后由脚本定，调用方只选场景。

只核命令怎么拼、怎么分通道、共享前态由谁准备与清理、按什么顺序求值，不真跑全量或失效形态。
"""
import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "test" / "scripts"))
import verify  # noqa: E402


def steps_of(scenario: str, **extra) -> list[tuple[str, list[str]]]:
    args = argparse.Namespace(scenario=scenario, targets=extra.get("targets", []), keyword=extra.get("keyword"))
    with mock.patch.object(verify.SHARED, "assembly", return_value="TEMPLATE"):
        return [step for lane in verify.scenario(args) for group in lane for step in group(REPO)]


class EveryPytestRunIsParallel(unittest.TestCase):
    def test_full_and_affected_carry_the_parallel_arguments(self) -> None:
        """全量单跑与交回里的全量是同一个固定 worker 数；改一处按机器自动。"""
        full, handback = " ".join(steps_of("full")[0][1]), " ".join(dict(steps_of("handback"))["full"])
        self.assertIn(f"-n {verify.FULL_WORKERS} --dist loadscope", full)
        self.assertEqual(full, handback, "单跑的全量与交回里的全量命令不同")
        self.assertIn("-n auto --dist loadscope", " ".join(steps_of("affected", targets=["test_verify_entry.py"], keyword="parallel")[0][1]))
        self.assertIn("--durations", steps_of("full")[0][1])
        affected = steps_of("affected", targets=["test_verify_entry.py"], keyword="parallel")[0][1]
        self.assertIn(str(REPO / "test" / "tests" / "test_verify_entry.py"), affected, "只写文件名时没落到 test/tests")
        self.assertEqual(["-k", "parallel"], affected[-2:])

    def test_the_handback_lanes_have_fixed_concurrency(self) -> None:
        """交回时各通道的并发上限固定：全量 8 个 worker、失效形态 1 个进程、CLI 测试不并行、compileall 单进程。"""
        got = dict(steps_of("handback"))
        self.assertIn("-n 8 --dist loadscope", " ".join(got["full"]))
        self.assertEqual(["--jobs", "1"], got["failure-modes"][-2:])
        self.assertIn("-p no:xdist", " ".join(got["cli-tests"]))
        self.assertIn("-j 1", " ".join(got["compileall"]))

    def test_an_unknown_test_file_stops_before_running(self) -> None:
        with self.assertRaises(SystemExit):
            verify.affected_steps(["no_such_test.py"], None)


class TheHandbackRunsInLanes(unittest.TestCase):
    def scratch_repo(self):
        """整轮入口的日志目录落在临时目录，不在真实 output/verify 下留下假的交回证据。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return mock.patch.object(verify, "REPO", Path(tmp.name))

    def test_full_failure_modes_and_the_rest_are_three_lanes(self) -> None:
        args = argparse.Namespace(scenario="handback", targets=[], keyword=None)
        with mock.patch.object(verify.SHARED, "assembly", return_value="TEMPLATE"):
            lanes = [[name for group in lane for name, _ in group(REPO)] for lane in verify.scenario(args)]
        self.assertEqual([["full"], ["failure-modes"], ["cli-tests", "compileall", "validate-clis", "node-check"]], lanes)
        failure_modes = dict(steps_of("handback"))["failure-modes"]
        self.assertEqual(["--project-root", "TEMPLATE"], failure_modes[-4:-2], "失效形态没对共享的模板跑")

    def test_laying_out_the_lanes_builds_nothing(self) -> None:
        """排通道时不装任何东西：共享前态由父进程在计时之内准备，全量那条通道不碰模板。"""
        args = argparse.Namespace(scenario="handback", targets=[], keyword=None)
        with mock.patch.object(verify.SHARED, "assembly", side_effect=AssertionError("排通道时建了模板")):
            lanes = verify.scenario(args)
            lanes[0][0](REPO)
            lanes[2][0](REPO)

    def test_the_parent_prepares_once_hands_the_paths_down_and_clears_them(self) -> None:
        """交回：父进程装一次模板与安装包，路径经环境变量交给每一步，全部跑完后由父进程清掉。"""
        seen = []

        def fake_run(name, cmd, log_dir):
            seen.append(dict(verify.SHARED.env))
            return name, True, f"[{name}]"

        def prepare(scenario, log_dir):
            verify.SHARED.env.update(STORY_TEST_ASSEMBLY_ROOT="TEMPLATE", STORY_TEST_INSTALLED_PACKAGE="PKG")
            verify.SHARED.template = "TEMPLATE"

        cleared = []
        with mock.patch.object(verify, "run", side_effect=fake_run), \
                mock.patch.object(verify, "prepare_shared", side_effect=prepare), \
                mock.patch.object(verify.SHARED, "clear", side_effect=lambda: cleared.append(True)), \
                mock.patch.object(verify.SHARED, "env", {}), mock.patch.object(verify.SHARED, "template", None), \
                mock.patch("sys.stdout"), self.scratch_repo():
            self.assertEqual(0, verify.main(["handback"]))
        self.assertTrue(seen and all(e.get("STORY_TEST_ASSEMBLY_ROOT") == "TEMPLATE" and e.get("STORY_TEST_INSTALLED_PACKAGE") == "PKG"
                                     for e in seen), seen)
        self.assertEqual([True], cleared, "共享前态没由父进程清掉")

    def test_full_and_handback_prepare_the_same_shared_state(self) -> None:
        """单跑全量与交回都由父进程装一次模板与安装包：两轮全量的 worker 拿到同一种前态；改一处什么都不装。"""
        for scenario, expected in (("full", ["assembly", "package"]), ("handback", ["assembly", "package"]), ("affected", [])):
            made = []
            with self.subTest(scenario=scenario), \
                    mock.patch.object(verify.SHARED, "assembly", side_effect=lambda d: made.append("assembly")), \
                    mock.patch.object(verify.SHARED, "installed_package", side_effect=lambda: made.append("package")):
                verify.prepare_shared(scenario, REPO)
                self.assertEqual(expected, made)

    def test_every_lane_reports_in_a_fixed_order(self) -> None:
        """通道同时跑、完成有先后，汇总仍按通道顺序，有一步失败退出码非 0。"""
        def fake_run(name, cmd, log_dir):
            return name, name != "compileall", f"[{name}]"
        with mock.patch.object(verify, "run", side_effect=fake_run), \
                mock.patch.object(verify, "prepare_shared"), \
                mock.patch.object(verify.SHARED, "assembly", return_value="TEMPLATE"), \
                mock.patch("sys.stdout"), self.scratch_repo():
            code = verify.main(["handback"])
        self.assertEqual(1, code)

    def test_a_failed_shared_preparation_is_reported_and_nothing_runs(self) -> None:
        """共享前态装不成（如装配守卫的 SystemExit）：报出原错误与各通道没执行，退出码非 0，装了一半的也清掉。"""
        ran, printed, cleared = [], [], []

        def fake_run(name, cmd, log_dir):
            ran.append(name)
            return name, True, f"[通过] {name}"
        with mock.patch.object(verify, "run", side_effect=fake_run), \
                mock.patch.object(verify, "prepare_shared", side_effect=SystemExit("装配前后 demo 的提交变了")), \
                mock.patch.object(verify.SHARED, "clear", side_effect=lambda: cleared.append(True)), \
                mock.patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))), \
                self.scratch_repo():
            code = verify.main(["handback"])
        self.assertEqual(1, code)
        self.assertEqual([], ran)
        self.assertTrue(any("装配前后 demo 的提交变了" in line and "没有执行" in line for line in printed), printed)
        self.assertEqual([True], cleared)

    def test_a_lane_whose_preparation_fails_is_reported_not_swallowed(self) -> None:
        """单跑失效形态时模板在它那条通道里装：装不成记为失败、写明原错误与没执行，退出码非 0。"""
        printed = []
        with mock.patch.object(verify, "run", side_effect=AssertionError("准备失败还跑了")), \
                mock.patch.object(verify.SHARED, "assembly", side_effect=SystemExit("装配前后 demo 的提交变了")), \
                mock.patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))), \
                self.scratch_repo():
            code = verify.main(["failure-modes"])
        self.assertEqual(1, code)
        failed = [line for line in printed if "failure-modes" in line and "准备" in line]
        self.assertTrue(failed and "装配前后 demo 的提交变了" in failed[-1] and "没有执行" in failed[-1], printed)


class CasesPlanEveryCase(unittest.TestCase):
    def test_jobs_equal_the_number_of_cases(self) -> None:
        cmd = steps_of("cases")[0][1]
        count = sum(1 for p in (REPO / "test" / "cases").iterdir() if (p / "case.yaml").is_file())
        self.assertEqual(["plan", "--all", "--jobs", str(count)], cmd[-4:])


if __name__ == "__main__":
    unittest.main()
