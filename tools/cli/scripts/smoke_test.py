"""Optional real-CLI smoke test with explicit environment classifications."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..api import DEFAULT_RUNTIME_ROOT, CliClient
from ..models import CliRunRequest, FailureKind


NON_FAILURE_ENVIRONMENT_KINDS = {
    FailureKind.AUTH_REQUIRED.value,
    FailureKind.SUBSCRIPTION_UNAVAILABLE.value,
    FailureKind.MODEL_UNAVAILABLE.value,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an optional real CLI smoke test")
    parser.add_argument("--cli", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--prompt", default="Reply with exactly: CLI_SMOKE_OK")
    parser.add_argument("--registry")
    parser.add_argument("--runtime-root")
    parser.add_argument("--soft-timeout-sec", type=float, default=120)
    parser.add_argument("--hard-timeout-sec", type=float, default=180)
    args = parser.parse_args()
    kwargs = {}
    if args.registry:
        kwargs["registry_path"] = args.registry
    kwargs["runtime_root"] = args.runtime_root or DEFAULT_RUNTIME_ROOT
    client = CliClient(**kwargs)
    result = client.run(
        CliRunRequest(
            cli=args.cli,
            model=args.model,
            prompt=args.prompt,
            cwd=Path(args.cwd),
            profile=args.profile,
            soft_timeout_sec=args.soft_timeout_sec,
            hard_timeout_sec=args.hard_timeout_sec,
        )
    )
    if result.status == "succeeded":
        verdict = "PASS"
        exit_code = 0
    elif args.cli in {"agent", "claude"} and result.failure_kind in NON_FAILURE_ENVIRONMENT_KINDS:
        verdict = "SKIP_ENVIRONMENT"
        exit_code = 0
    else:
        verdict = "FAIL"
        exit_code = 1
    print(
        json.dumps(
            {
                "verdict": verdict,
                "cli": args.cli,
                "status": result.status,
                "failure_kind": result.failure_kind,
                "run_id": result.run_id,
                "run_dir": str(result.run_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
