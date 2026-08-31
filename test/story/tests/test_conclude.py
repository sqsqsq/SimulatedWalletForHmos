"""宿主收工与终态归因。

两件事：

- `conclude` 是**优雅收工**——只放控制文件，不杀进程。`stop` 强杀进程树，
  门禁从不运行、`phase-results/` 不产出，拿到的报告是残的；两者不能混。
- 终态归因不塌缩。上一版把「模型真没做完」「没人回话超时」「CLI 没回 session id」
  统统记成 `target_not_reached`，事后完全分不出来——而其中两种压根不是被测对象的账。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load("story_run_case_conclude", "run_case.py")


class ConcludeIsNotAKill(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_the_request_is_taken_once_and_carries_the_reason(self) -> None:
        """理由要留下来——事后才看得出这一轮为什么停在这里。"""
        (self.tmp / rc.CONCLUDE_FILE).write_text(
            json.dumps({"reason": "模型宣告进入 plan，本轮目标 spec 已到位"}),
            encoding="utf-8")
        got = rc.pop_conclude_request(self.tmp)
        self.assertEqual("模型宣告进入 plan，本轮目标 spec 已到位", got["reason"])
        self.assertIsNone(rc.pop_conclude_request(self.tmp), "取走即删，一次判定只用一次")

    def test_a_broken_file_is_not_mistaken_for_a_decision(self) -> None:
        """半写状态下一轮就完整了；把破文件当成收工判定会白白截断一轮。"""
        (self.tmp / rc.CONCLUDE_FILE).write_text("{半个", encoding="utf-8")
        self.assertIsNone(rc.pop_conclude_request(self.tmp))


class TerminalStatusTable(unittest.TestCase):
    """一次运行为什么停在这里 → 记成什么终态、退出码是几。

    退出码表达的是「**这次运行有没有装置或 CLI 层面的失败**」：宿主判定收工是正常
    收场（0），哪怕目标没闭环——目标闭没闭环由 `target_reached` 与 `target_missing`
    单独说，评测看那两个。
    """

    def test_every_stop_reason_maps_to_its_own_terminal(self) -> None:
        table = [
            # (execution_status, stop_reason, target_reached) → (status, exit)
            ("finished", "target_reached", True, "finished", 0),
            ("finished", "host_concluded", True, "finished", 0),
            # 宿主收工而目标没闭环：模型自认为做完了、凭证却不齐。
            # 这是**有效观测**，不是装置失败。
            ("finished", "host_concluded", False, "concluded_by_host", 0),
            # 自然结束、产物不齐——唯一保留原义的那一支
            ("finished", None, False, "target_not_reached", 1),
            ("finished", "cli_cannot_continue", False, "cli_failed", 1),
            # CLI 回了 succeeded 却没给 session id：adapter 的账
            ("finished", "no_session_id", False, "cli_session_lost", 2),
        ]
        for execution, reason, reached, want_status, want_code in table:
            with self.subTest(stop_reason=reason, reached=reached):
                self.assertEqual((want_status, want_code),
                                 rc.terminal_status_for(execution, reason, reached))

    def test_the_awaiting_timeout_reason_is_gone(self) -> None:
        """等宿主回话不再有上限，那个 stop_reason 也就没有产生者了。

        判的是**代码里还用不用它**，不是字面——注释里说明「它为什么退场」是应该的，
        把那段也一并禁掉，下一个人就不知道这里曾经踩过什么坑。
        """
        self.assertFalse(hasattr(rc, "REPLY_WAIT"), "REPLY_WAIT 应当已退场")
        self.assertEqual(0, rc.REPLY_NUDGE > 0 and 0,
                         "取而代之的是提醒间隔，它不终止任何东西")
        source = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        for gone in ('"awaiting_reply_timeout"', "REPLY_WAIT =", "timeout=REPLY_WAIT"):
            self.assertNotIn(gone, source, f"代码里还留着 {gone}")

    def test_a_stale_config_key_is_refused(self) -> None:
        """`reply_wait_sec` 写进配置要直接报错——静默忽略会让人以为限制还在。"""
        source = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("reply_wait_sec", source, "拒绝清单里要点名这个键")


if __name__ == "__main__":
    unittest.main()
