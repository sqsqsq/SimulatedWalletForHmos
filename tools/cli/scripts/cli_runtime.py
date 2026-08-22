"""Small command-line facade over the standard Python interface."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..api import DEFAULT_RUNTIME_ROOT, CliClient
from ..models import CliRunRequest


def _json(value: Any) -> str:
    def default(item: Any) -> Any:
        if isinstance(item, Path):
            return str(item)
        raise TypeError(type(item).__name__)

    return json.dumps(value, ensure_ascii=False, indent=2, default=default)


def _request(args: argparse.Namespace) -> CliRunRequest:
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt:
        raise ValueError("--prompt or --prompt-file is required")
    return CliRunRequest(
        cli=args.cli,
        model=args.model,
        prompt=prompt,
        cwd=Path(args.cwd),
        profile=args.profile,
        session_id=args.session_id,
        output_schema=Path(args.output_schema) if args.output_schema else None,
        soft_timeout_sec=args.soft_timeout_sec,
        hard_timeout_sec=args.hard_timeout_sec,
        stop_grace_sec=args.stop_grace_sec,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified agent CLI runtime")
    parser.add_argument("--registry")
    parser.add_argument("--runtime-root")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("run", "start", "resume", "describe"):
        command = sub.add_parser(name)
        command.add_argument("--cli", required=True)
        command.add_argument("--model", required=True)
        command.add_argument("--prompt")
        command.add_argument("--prompt-file")
        command.add_argument("--cwd", default=".")
        command.add_argument("--profile")
        command.add_argument("--session-id")
        command.add_argument("--output-schema")
        command.add_argument("--soft-timeout-sec", type=float)
        command.add_argument("--hard-timeout-sec", type=float)
        command.add_argument("--stop-grace-sec", type=float)

    poll = sub.add_parser("poll")
    poll.add_argument("run_id")
    poll.add_argument("--cursor", type=int, default=0)
    poll.add_argument("--wait-sec", type=float, default=0)
    poll.add_argument("--max-events", type=int, default=100)
    poll.add_argument("--max-chars", type=int, default=12000)

    status = sub.add_parser("status")
    status.add_argument("run_id")
    stop = sub.add_parser("stop")
    stop.add_argument("run_id")
    stop.add_argument("--force", action="store_true")

    args = parser.parse_args()
    kwargs = {}
    if args.registry:
        kwargs["registry_path"] = args.registry
    kwargs["runtime_root"] = args.runtime_root or DEFAULT_RUNTIME_ROOT
    client = CliClient(**kwargs)

    if args.command in {"run", "start", "resume", "describe"}:
        request = _request(args)
        if args.command == "run":
            result = client.run(request)
            print(_json(asdict(result)))
            return 0 if result.status == "succeeded" else 1
        if args.command == "start":
            print(_json(asdict(client.start(request))))
            return 0
        if args.command == "resume":
            result = client.resume(request)
            print(_json(asdict(result)))
            return 0 if result.status == "succeeded" else 1
        print(_json(client.describe(request)))
        return 0
    if args.command == "poll":
        page = client.poll(
            args.run_id,
            cursor=args.cursor,
            wait_sec=args.wait_sec,
            max_events=args.max_events,
            max_chars=args.max_chars,
        )
        value = asdict(page)
        print(_json(value))
        return 0
    if args.command == "status":
        print(_json(client.status(args.run_id)))
        return 0
    result = client.stop(args.run_id, force=args.force)
    print(_json(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
