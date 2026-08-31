"""Central CLI registration, validation, and command construction."""

from __future__ import annotations

import json
import shutil
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import CliRunRequest


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "clis.json"
ALLOWED_PLACEHOLDERS = {"prompt", "cwd", "model", "session_id", "schema"}


class CliConfigurationError(ValueError):
    pass


class CliNotFoundError(FileNotFoundError):
    pass


class ResumeNotSupportedError(CliConfigurationError):
    pass


@dataclass(frozen=True)
class ResolvedCommand:
    cli: str
    profile: str
    executable: str
    argv: list[str]
    cwd: Path | None
    env: dict[str, str]
    adapter: str
    soft_timeout_sec: float
    hard_timeout_sec: float
    stop_grace_sec: float


class CliRegistry:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = Path(config_path).resolve()
        self.data = self._load()
        self.validate()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            raise CliConfigurationError(f"CLI registry does not exist: {self.path}")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliConfigurationError(f"Invalid CLI registry JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise CliConfigurationError("CLI registry root must be an object")
        return value

    def validate(self) -> None:
        from .adapters import ADAPTERS

        data = self.data
        if data.get("schema_version") != 1:
            raise CliConfigurationError("schema_version must be 1")
        defaults = data.get("defaults")
        clis = data.get("clis")
        if not isinstance(defaults, dict):
            raise CliConfigurationError("defaults must be an object")
        if not isinstance(clis, dict) or not clis:
            raise CliConfigurationError("clis must be a non-empty object")
        self._validate_timeout(defaults.get("timeout"), "defaults.timeout")
        self._validate_env(defaults.get("env", {}), "defaults.env")

        for cli_name, cli in clis.items():
            prefix = f"clis.{cli_name}"
            if not isinstance(cli, dict):
                raise CliConfigurationError(f"{prefix} must be an object")
            for key in ("executable", "adapter", "default_profile", "profiles"):
                if not cli.get(key):
                    raise CliConfigurationError(f"{prefix}.{key} is required")
            if cli["adapter"] not in ADAPTERS:
                raise CliConfigurationError(
                    f"{prefix}.adapter is unknown: {cli['adapter']}"
                )
            profiles = cli["profiles"]
            if not isinstance(profiles, dict) or cli["default_profile"] not in profiles:
                raise CliConfigurationError(f"{prefix}.default_profile must exist in profiles")
            if not profiles[cli["default_profile"]].get("resume_args"):
                raise CliConfigurationError(
                    f"{prefix} default profile must provide resume_args"
                )
            self._validate_env(cli.get("env", {}), f"{prefix}.env")
            for profile_name, profile in profiles.items():
                pp = f"{prefix}.profiles.{profile_name}"
                if not isinstance(profile, dict):
                    raise CliConfigurationError(f"{pp} must be an object")
                self._validate_args(profile.get("args"), f"{pp}.args")
                if "resume_args" in profile:
                    self._validate_args(profile["resume_args"], f"{pp}.resume_args")
                    fields = self._fields(profile["resume_args"])
                    if "session_id" not in fields:
                        raise CliConfigurationError(
                            f"{pp}.resume_args must contain {{session_id}}"
                        )
                self._validate_env(profile.get("env", {}), f"{pp}.env")
                if "timeout" in profile:
                    self._validate_timeout(profile["timeout"], f"{pp}.timeout")

    def _validate_args(self, args: Any, label: str) -> None:
        if not isinstance(args, list) or not args or not all(isinstance(v, str) for v in args):
            raise CliConfigurationError(f"{label} must be a non-empty string array")
        unknown = self._fields(args) - ALLOWED_PLACEHOLDERS
        if unknown:
            raise CliConfigurationError(
                f"{label} contains unknown placeholders: {', '.join(sorted(unknown))}"
            )
        required = {"prompt", "model"}
        missing = required - self._fields(args)
        if missing:
            raise CliConfigurationError(
                f"{label} is missing placeholders: {', '.join(sorted(missing))}"
            )

    @staticmethod
    def _fields(args: list[str]) -> set[str]:
        fields: set[str] = set()
        formatter = string.Formatter()
        for arg in args:
            try:
                for _, field_name, _, _ in formatter.parse(arg):
                    if field_name:
                        fields.add(field_name)
            except ValueError as exc:
                raise CliConfigurationError(f"Invalid placeholder syntax in {arg!r}: {exc}") from exc
        return fields

    @staticmethod
    def _validate_env(value: Any, label: str) -> None:
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            raise CliConfigurationError(f"{label} must be a string-to-string object")

    @staticmethod
    def _validate_timeout(value: Any, label: str) -> None:
        if not isinstance(value, dict):
            raise CliConfigurationError(f"{label} must be an object")
        try:
            soft = float(value["soft_sec"])
            hard = float(value["hard_sec"])
            grace = float(value["stop_grace_sec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CliConfigurationError(
                f"{label} requires numeric soft_sec, hard_sec, stop_grace_sec"
            ) from exc
        if soft <= 0 or hard <= soft or grace < 0:
            raise CliConfigurationError(
                f"{label} requires 0 < soft_sec < hard_sec and stop_grace_sec >= 0"
            )

    def cli_names(self) -> list[str]:
        return sorted(self.data["clis"])

    def build(self, request: CliRunRequest, *, check_executable: bool = True) -> ResolvedCommand:
        cwd = request.cwd.expanduser().resolve()
        if not cwd.is_dir():
            raise CliConfigurationError(f"Request cwd is not a directory: {cwd}")
        cli = self.data["clis"].get(request.cli)
        if cli is None:
            raise CliConfigurationError(
                f"Unknown CLI {request.cli!r}; available: {', '.join(self.cli_names())}"
            )
        profile_name = request.profile or str(cli["default_profile"])
        profile = cli["profiles"].get(profile_name)
        if profile is None:
            choices = ", ".join(sorted(cli["profiles"]))
            raise CliConfigurationError(
                f"Unknown profile {profile_name!r} for {request.cli}; available: {choices}"
            )
        templates = profile.get("resume_args") if request.session_id else profile["args"]
        if request.session_id and not templates:
            raise ResumeNotSupportedError(
                f"CLI {request.cli!r} profile {profile_name!r} does not support resume"
            )
        assert isinstance(templates, list)
        values = {
            "prompt": request.prompt,
            "cwd": str(cwd),
            "model": request.model,
            "session_id": request.session_id,
            "schema": str(request.output_schema.resolve()) if request.output_schema else None,
        }
        fields = self._fields(templates)
        missing = sorted(field for field in fields if not values.get(field))
        if missing:
            raise CliConfigurationError(
                f"Missing request values for placeholders: {', '.join(missing)}"
            )
        argv: list[str] = []
        for template in templates:
            value = template
            for field in fields:
                replacement = values[field]
                if replacement is not None:
                    value = value.replace("{" + field + "}", str(replacement))
            argv.append(value)

        executable_name = str(cli["executable"])
        candidate = Path(executable_name)
        executable = str(candidate.resolve()) if candidate.is_file() else shutil.which(executable_name)
        if not executable:
            if check_executable:
                raise CliNotFoundError(f"CLI is not installed or not in PATH: {executable_name}")
            executable = executable_name

        defaults = self.data["defaults"]
        timeout = {**defaults["timeout"], **(profile.get("timeout") or {})}
        soft = request.soft_timeout_sec
        hard = request.hard_timeout_sec
        grace = request.stop_grace_sec
        soft = float(timeout["soft_sec"] if soft is None else soft)
        hard = float(timeout["hard_sec"] if hard is None else hard)
        grace = float(timeout["stop_grace_sec"] if grace is None else grace)
        # 0 means "no limit". A long agent run is not a failure mode here: the
        # observer drives the session turn by turn and stops it explicitly, so a
        # wall clock that kills the process mid-phase destroys evidence rather
        # than protecting anything.
        unlimited = soft <= 0 and hard <= 0
        if not unlimited and (soft <= 0 or hard <= soft):
            raise CliConfigurationError(
                "Request timeouts require 0 < soft_timeout_sec < hard_timeout_sec, "
                "or both 0 for no limit"
            )
        if grace < 0:
            raise CliConfigurationError("stop_grace_sec must be >= 0")
        env = {
            **defaults.get("env", {}),
            **cli.get("env", {}),
            **profile.get("env", {}),
            **request.env,
        }
        return ResolvedCommand(
            cli=request.cli,
            profile=profile_name,
            executable=str(executable),
            argv=argv,
            cwd=cwd if cli.get("use_cwd", False) else None,
            env={str(k): str(v) for k, v in env.items()},
            adapter=str(cli["adapter"]),
            soft_timeout_sec=soft,
            hard_timeout_sec=hard,
            stop_grace_sec=grace,
        )
