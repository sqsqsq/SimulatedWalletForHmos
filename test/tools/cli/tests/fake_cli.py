"""Deterministic JSONL-emitting process used by lifecycle tests."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import uuid


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--resume")
    parser.add_argument("--delay", type=float, default=0)
    parser.add_argument("--event-count", type=int, default=0)
    parser.add_argument("--failure", choices=("auth", "subscription", "model"))
    parser.add_argument("--exit-code", type=int, default=0)
    args = parser.parse_args()
    sid = args.resume or f"fake-{uuid.uuid4().hex[:8]}"

    def interrupted(_signum, _frame) -> None:
        emit({"type": "error", "sessionID": sid, "message": "interrupted"})
        raise SystemExit(130)

    signal.signal(signal.SIGINT, interrupted)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupted)

    emit(
        {
            "type": "text",
            "sessionID": sid,
            "part": {"type": "text", "text": f"prompt={args.prompt};model={args.model}"},
        }
    )
    emit(
        {
            "type": "tool_use",
            "sessionID": sid,
            "part": {
                "type": "tool",
                "tool": "read",
                "state": {"status": "completed", "input": {"filePath": "fixture.txt"}, "output": "ok"},
            },
        }
    )
    for index in range(max(0, args.event_count)):
        emit(
            {
                "type": "text",
                "sessionID": sid,
                "part": {"type": "text", "text": f"event-{index}"},
            }
        )
    if args.delay:
        time.sleep(args.delay)
    if args.failure:
        messages = {
            "auth": "Authentication required. Please login.",
            "subscription": "Subscription expired: payment required.",
            "model": "Model unavailable.",
        }
        emit({"type": "error", "sessionID": sid, "message": messages[args.failure]})
        return 9
    emit(
        {
            "type": "step_finish",
            "sessionID": sid,
            "part": {
                "type": "step-finish",
                "tokens": {"input": 10, "output": 3, "total": 13},
                "cost": 0.01,
            },
        }
    )
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
