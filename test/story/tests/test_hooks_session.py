# -*- coding: utf-8 -*-
"""实例 hook 的会话归属：state 归谁，按本会话 transcript 的一手记录判。

黑盒跑真实 hook（node + stdin JSON），不 import 内部函数——判据是「同仓两个会话时
hook 的对外行为对不对」，而不是某个函数返回了什么。

覆盖一件事：本会话跑过这个阶段的 harness → 未闭环时拦截（exit 2）。

报告落盘那两条判据没有对象了：报告不再由钩子从子 agent 的终态消息生成，
而是由派 verifier 的那个 agent 原样写到 `summary.verifier_report` 指向的路径，
落点由 harness 按 subject 定死，谁也覆盖不了另一个 subject 的文件。
「同仓两个会话抢 state」这个形态，在新协议下不再由归属判定承载。
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HOOKS = REPO / ".claude" / "hooks"

FEATURE = "SMPFEAT"
PHASE = "spec"


def _write_transcript(path: Path, *, ran_harness: bool, spawned_verifier: bool) -> None:
    rows = [{
        "message": {"content": [{"type": "text", "text": "干活中"}]},
    }]
    if ran_harness:
        rows.append({"message": {"content": [{
            "type": "tool_use", "name": "Bash",
            "input": {"command": f"npx ts-node harness-runner.ts --phase {PHASE} --feature {FEATURE}"},
        }]}})
    if spawned_verifier:
        rows.append({"message": {"content": [{
            "type": "tool_use", "name": "Task",
            "input": {"subagent_type": "verifier", "prompt": "verify"},
        }]}})
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def _make_project(tmp: Path, *, ran_harness: bool, spawned_verifier: bool = False):
    """造一个最小宿主工程：config + 未盖章且未闭环的 state + transcript。"""
    (tmp / "framework" / "harness" / "state").mkdir(parents=True)
    # hook 认工程根靠这些标记文件（PROJECT_ROOT_MARKERS）；不造出来它会回落到真仓库
    (tmp / "framework" / "harness" / "scripts").mkdir(parents=True)
    (tmp / "framework" / "harness" / "scripts" / "check-receipt.ts").write_text("", encoding="utf-8")
    (tmp / "framework.config.json").write_text(json.dumps({
        "paths": {
            "features_dir": "doc/features",
            "state_file": "framework/harness/state/.current-phase.json",
            "reports_dir_pattern": "doc/features/<feature>/<phase>/reports",
        },
        "state_machine": {"grace_period_minutes": 5, "ttl_hours": 12},
    }), encoding="utf-8")
    # 未盖章（无 session_id）、刚写下（在 grace 窗口内）、未闭环
    from datetime import datetime, timezone
    (tmp / "framework" / "harness" / "state" / ".current-phase.json").write_text(json.dumps({
        "feature": FEATURE,
        "phase": PHASE,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "harness": {"verdict": "PASS"},
    }), encoding="utf-8")
    transcript = tmp / "transcript.jsonl"
    _write_transcript(transcript, ran_harness=ran_harness, spawned_verifier=spawned_verifier)
    return {
        "session_id": "sess-under-test",
        "transcript_path": str(transcript),
        "cwd": str(tmp),
    }


def _run(hook: str, payload: dict):
    # hook 解析工程根时优先认 CLAUDE_PROJECT_DIR：不指向临时工程，测的就是真仓库的 state
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = payload["cwd"]
    env.pop("CODEAGENT3_PROJECT_DIR", None)
    return subprocess.run(
        ["node", str(HOOKS / hook)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(payload["cwd"]), env=env,
    )


class TestSessionOwnership(unittest.TestCase):
    def test_session_that_ran_harness_is_blocked_when_not_closed(self):
        with tempfile.TemporaryDirectory() as d:
            payload = _make_project(Path(d), ran_harness=True)
            r = _run("check-phase-completion.mjs", payload)
            self.assertEqual(r.returncode, 2,
                             f"跑过 harness 的会话未闭环时应被拦截；stderr={r.stderr[:300]}")


if __name__ == "__main__":
    unittest.main()
