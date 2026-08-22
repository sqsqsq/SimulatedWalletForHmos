"""Validate the central CLI registry."""

from __future__ import annotations

import argparse
import json

from ..registry import DEFAULT_CONFIG_PATH, CliConfigurationError, CliRegistry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the unified CLI registry")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args()
    try:
        registry = CliRegistry(args.config)
    except CliConfigurationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(
        json.dumps(
            {"ok": True, "config": str(registry.path), "clis": registry.cli_names()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
