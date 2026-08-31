# -*- coding: utf-8 -*-
"""实例 hook 的会话归属：state 归谁，按本会话 transcript 的一手记录判。

黑盒跑真实 hook（node + stdin JSON），不 import 内部函数——判据是「同仓两个会话时
hook 的对外行为对不对」，而不是某个函数返回了什么。

覆盖两件事：
  1. 本会话跑过这个阶段的 harness → 未闭环时拦截（exit 2）；
  2. 归属不成立时 record hook 不把报告写进 feature 目录、更不新建那个目录。

原本还有第三条「本会话没跑过 → 放行且不把 state 盖成自己的」，F6 合并
framework 3.0.0 后退役：新协议不再按 transcript 判归属，报告改为按 subject
分区落盘（verifier.report.<64位subject>.json），谁也没有能力覆盖另一个 subject
的文件；Stop 新鲜度只读 session_id + updated_at。「同仓两个会话抢 state」这个
被批次 1 T0-T18 修过的形态，在新协议下不再由归属判定承载，因此这条判据没有
对象了。它是否真的被覆盖，看冒烟短程里 verifier 留痕正不正常。
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

    def test_report_not_written_into_feature_dir_without_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            payload = _make_project(tmp, ran_harness=False, spawned_verifier=True)
            r = _run("record-verifier-report.mjs", payload)
            self.assertEqual(r.returncode, 0)
            self.assertFalse((tmp / "doc" / "features" / FEATURE).exists(),
                             "不是本会话的 state，不该凭 hook 触发建出 feature 目录")
            self.assertTrue((tmp / "framework" / "harness" / "state"
                             / "last-verifier-report.md").exists(),
                            "归属不成立时报告应落到 state 兜底目录，不能丢")


if __name__ == "__main__":
    unittest.main()
