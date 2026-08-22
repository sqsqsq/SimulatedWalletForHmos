"""Detached worker entry point. Not a public business interface."""

from __future__ import annotations

import argparse

from .registry import CliRegistry
from .run_store import RunStore
from .runner import CliRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    store = RunStore(args.runtime_root, args.run_id)
    result = CliRunner(CliRegistry(args.registry)).execute(store)
    if result.status == "succeeded":
        return 0
    return int(result.exit_code) if result.exit_code not in (None, 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
