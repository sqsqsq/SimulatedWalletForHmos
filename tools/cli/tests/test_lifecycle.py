from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tools.cli import CliClient, CliRunRequest
from tools.cli.models import TERMINAL_STATUSES
from tools.cli.run_store import RunStore


HERE = Path(__file__).resolve().parent
FAKE_CLI = HERE / "fake_cli.py"


def registry_value() -> dict:
    common = [str(FAKE_CLI), "--prompt", "{prompt}", "--model", "{model}"]
    resume = [
        str(FAKE_CLI),
        "--prompt",
        "{prompt}",
        "--model",
        "{model}",
        "--resume",
        "{session_id}",
    ]
    return {
        "schema_version": 1,
        "defaults": {
            "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            "timeout": {"soft_sec": 2, "hard_sec": 4, "stop_grace_sec": 0.2},
        },
        "clis": {
            "fake": {
                "executable": sys.executable,
                "adapter": "opencode",
                "default_profile": "normal",
                "use_cwd": True,
                "profiles": {
                    "normal": {"args": common, "resume_args": resume},
                    "slow": {
                        "args": [*common, "--delay", "3"],
                        "resume_args": [*resume, "--delay", "3"],
                    },
                    "burst": {
                        "args": [*common, "--event-count", "500"],
                        "resume_args": [*resume, "--event-count", "500"],
                    },
                    "subscription": {
                        "args": [*common, "--failure", "subscription"]
                    },
                },
            }
        },
    }


class LifecycleTests(unittest.TestCase):
    def test_runtime_root_is_caller_owned(self) -> None:
        with self.assertRaises(TypeError):
            CliClient()  # type: ignore[call-arg]

    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[3] / "output" / "cli-tests" / uuid.uuid4().hex
        root.mkdir(parents=True)
        self.root = root
        self.registry_path = root / "clis.json"
        self.registry_path.write_text(json.dumps(registry_value()), encoding="utf-8")
        self.runtime_root = root / "runs"
        self.client = CliClient(
            registry_path=self.registry_path,
            runtime_root=self.runtime_root,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            self.root.parent.rmdir()
        except OSError:
            pass

    def request(self, **values) -> CliRunRequest:
        return CliRunRequest(
            cli="fake",
            model="fake-model",
            prompt=values.pop("prompt", "hello"),
            cwd=self.root,
            **values,
        )

    def wait_terminal(self, run_id: str, timeout: float = 8) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.client.status(run_id)
            if state.get("status") in TERMINAL_STATUSES:
                return state
            time.sleep(0.05)
        self.fail(f"run {run_id} did not finish: {self.client.status(run_id)}")

    def test_foreground_run_and_resume(self) -> None:
        seen = []
        result = self.client.run(self.request(), on_event=seen.append)
        self.assertEqual("succeeded", result.status)
        self.assertTrue(result.session_id)
        self.assertIn("prompt=hello;model=fake-model", result.final_text or "")
        self.assertTrue(any(event.type == "tool" for event in seen))
        self.assertTrue((result.run_dir / "events.jsonl").is_file())
        self.assertTrue((result.run_dir / "raw.jsonl").is_file())

        resumed = self.client.resume(
            self.request(session_id=result.session_id, prompt="continue"),
            parent_run_id=result.run_id,
        )
        self.assertEqual("succeeded", resumed.status)
        self.assertEqual(result.session_id, resumed.session_id)
        state = self.client.status(resumed.run_id)
        self.assertEqual(result.run_id, state["parent_run_id"])

    def test_start_poll_status(self) -> None:
        handle = self.client.start(self.request())
        first = self.client.poll(handle.run_id, cursor=0, wait_sec=5)
        self.assertTrue(first.events)
        state = self.wait_terminal(handle.run_id)
        self.assertEqual("succeeded", state["status"])
        second = self.client.poll(handle.run_id, cursor=first.next_cursor)
        seqs = [event.seq for event in first.events + second.events]
        self.assertEqual(len(seqs), len(set(seqs)))

    def test_poll_during_event_burst_preserves_complete_stream(self) -> None:
        handle = self.client.start(self.request(profile="burst"))
        cursor = 0
        events = []
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            page = self.client.poll(
                handle.run_id,
                cursor=cursor,
                wait_sec=0.1,
                max_events=25,
                max_chars=20000,
            )
            events.extend(page.events)
            cursor = page.next_cursor
            if page.run.get("status") in TERMINAL_STATUSES and not page.has_more:
                break
        else:
            self.fail(f"burst run did not finish: {self.client.status(handle.run_id)}")

        self.assertEqual("succeeded", self.client.status(handle.run_id)["status"])
        seqs = [event.seq for event in events]
        self.assertEqual(seqs, sorted(set(seqs)))
        text_events = [event for event in events if event.type == "text"]
        burst_content = {
            event.content for event in text_events
            if (event.content or "").startswith("event-")
        }
        self.assertEqual({f"event-{index}" for index in range(500)}, burst_content)
        self.assertTrue(
            any((event.content or "").startswith("prompt=") for event in text_events)
        )

    def test_reader_failure_force_stops_child_and_is_classified(self) -> None:
        original = RunStore.append_event

        def fail_in_reader(store, *args, **kwargs):
            if threading.current_thread().name.startswith("cli-reader-"):
                raise PermissionError("simulated event store failure")
            return original(store, *args, **kwargs)

        started = time.monotonic()
        with patch.object(RunStore, "append_event", fail_in_reader):
            result = self.client.run(
                self.request(
                    profile="slow",
                    soft_timeout_sec=20,
                    hard_timeout_sec=40,
                    stop_grace_sec=5,
                )
            )

        self.assertEqual("failed", result.status)
        self.assertEqual("event_stream_failed", result.failure_kind)
        self.assertTrue(result.forced)
        self.assertLess(time.monotonic() - started, 3)
        state = self.client.status(result.run_id)
        self.assertIn("simulated event store failure", state["reader_error"])

    def test_force_stop(self) -> None:
        handle = self.client.start(
            self.request(
                profile="slow",
                soft_timeout_sec=20,
                hard_timeout_sec=40,
                stop_grace_sec=0.1,
            )
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.client.status(handle.run_id)
            if state.get("status") in {"running", "overtime"}:
                break
            time.sleep(0.05)
        result = self.client.stop(handle.run_id, force=True)
        self.assertEqual("stopped", result.status)
        self.assertEqual("stopped", result.failure_kind)

    def test_hard_timeout(self) -> None:
        result = self.client.run(
            self.request(
                profile="slow",
                soft_timeout_sec=0.1,
                hard_timeout_sec=0.3,
                stop_grace_sec=0.1,
            )
        )
        self.assertEqual("timed_out", result.status)
        self.assertEqual("timed_out", result.failure_kind)
        self.assertTrue(result.forced)
        events = self.client.poll(result.run_id).events
        self.assertTrue(any("soft timeout" in (event.content or "") for event in events))
        self.assertTrue(any("hard timeout" in (event.content or "") for event in events))

    def test_subscription_failure_is_classified(self) -> None:
        result = self.client.run(self.request(profile="subscription"))
        self.assertEqual("failed", result.status)
        self.assertEqual("subscription_unavailable", result.failure_kind)


if __name__ == "__main__":
    unittest.main()
