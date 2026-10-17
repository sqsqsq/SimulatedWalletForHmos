"""Central CLI registration, validation, and command construction."""

from __future__ import annotations

import json
import re
import shutil
import string
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import CliRunRequest

# npm 在 Windows 上装的批处理包装器有两种正文形态：
#   ① 直接指向可执行文件： "%dp0%\node_modules\pkg\bin\foo.exe"   %*
#   ② 经 node 跑脚本：      "%_prog%"  "%dp0%\node_modules\pkg\bin\foo.js" %*
_WRAPPER_EXE = re.compile(r'"%~?dp0%\\?([^"\r\n]+?\.exe)"\s+%\*', re.IGNORECASE)
_WRAPPER_NODE = re.compile(r'"%_prog%"\s+"%~?dp0%\\?([^"\r\n]+?)"\s+%\*', re.IGNORECASE)
_WRAPPER_ELECTRON = re.compile(
    r'"%~dp0([^"\r\n]+?\.exe)"\s+--expose-internals\s+"%~dp0([^"\r\n]+?\.js)"\s+%\*',
    re.IGNORECASE,
)


@lru_cache(maxsize=64)
def resolve_batch_wrapper(executable: str) -> tuple[str, tuple[str, ...]]:
    """Windows 上把 `.CMD`/`.BAT` 包装器解析到它真正调用的程序。

    返回 `(可执行文件, 需要前置的参数)`——node 脚本形态的包装器要把脚本路径作为首个参数。

    为什么必须绕开包装器：`.CMD` 由 **cmd.exe** 解释，而 cmd.exe 按行解析命令——
    参数里只要含换行，命令行就在那里终止，`%*` 展开后**后续内容连同再往后的参数一起丢失**。
    表现是 prompt 被悄悄截断在第一行，且排在 prompt 之后的开关（`--format json` 之类）
    也一并失效，于是 provider 退回默认输出格式。整个过程没有任何报错。

    直接执行底层程序就没有 cmd.exe 参与，argv 逐字送达。

    解析不出目标、或目标不存在时**返回原路径**：这条只是加固，不该让本来能跑的调用失败。
    """
    unchanged: tuple[str, tuple[str, ...]] = (executable, ())
    if sys.platform != "win32":
        return unchanged
    path = Path(executable)
    if path.suffix.lower() not in {".cmd", ".bat"}:
        return unchanged
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return unchanged

    # Electron CLI wrappers launch a script with a fixed Node flag. Preserve
    # both paths and the flag while removing cmd.exe from the argv path.
    match = _WRAPPER_ELECTRON.search(content)
    if match:
        target, script = [(path.parent / value).resolve() for value in match.groups()]
        # Electron reads entry scripts from ASAR archives as virtual files.
        script_exists = script.is_file() or any(parent.suffix.lower() == ".asar" and parent.is_file() for parent in script.parents)
        if target.is_file() and script_exists:
            return str(target), ("--expose-internals", str(script))
        return unchanged

    match = _WRAPPER_EXE.search(content)
    if match:
        target = (path.parent / match.group(1).strip()).resolve()
        return (str(target), ()) if target.is_file() else unchanged

    match = _WRAPPER_NODE.search(content)
    if match:
        script = (path.parent / match.group(1).strip()).resolve()
        if not script.is_file():
            return unchanged
        bundled = path.parent / "node.exe"
        node = str(bundled) if bundled.is_file() else shutil.which("node")
        if node:
            return (node, (str(script),))
    return unchanged


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
            # Some providers bind model selection to their own profile config
            # (for example dsh headless reads agent-default-model) and have no
            # model flag; such entries declare model_in_argv: false and the
            # request model is recorded as metadata only.
            require_model_in_argv = cli.get("model_in_argv", True)
            for profile_name, profile in profiles.items():
                pp = f"{prefix}.profiles.{profile_name}"
                if not isinstance(profile, dict):
                    raise CliConfigurationError(f"{pp} must be an object")
                self._validate_args(profile.get("args"), f"{pp}.args", require_model_in_argv)
                if "resume_args" in profile:
                    self._validate_args(
                        profile["resume_args"], f"{pp}.resume_args", require_model_in_argv
                    )
                    fields = self._fields(profile["resume_args"])
                    if "session_id" not in fields:
                        raise CliConfigurationError(
                            f"{pp}.resume_args must contain {{session_id}}"
                        )
                self._validate_env(profile.get("env", {}), f"{pp}.env")
                if "timeout" in profile:
                    self._validate_timeout(profile["timeout"], f"{pp}.timeout")

    def _validate_args(self, args: Any, label: str, require_model: bool = True) -> None:
        if not isinstance(args, list) or not args or not all(isinstance(v, str) for v in args):
            raise CliConfigurationError(f"{label} must be a non-empty string array")
        unknown = self._fields(args) - ALLOWED_PLACEHOLDERS
        if unknown:
            raise CliConfigurationError(
                f"{label} contains unknown placeholders: {', '.join(sorted(unknown))}"
            )
        required = {"prompt", "model"} if require_model else {"prompt"}
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
        else:
            executable, prefix_args = resolve_batch_wrapper(executable)
            if prefix_args:
                argv = [*prefix_args, *argv]

        defaults = self.data["defaults"]
        timeout = {**defaults["timeout"], **(profile.get("timeout") or {})}
        soft = request.soft_timeout_sec
        hard = request.hard_timeout_sec
        grace = request.stop_grace_sec
        soft = float(timeout["soft_sec"] if soft is None else soft)
        hard = float(timeout["hard_sec"] if hard is None else hard)
        grace = float(timeout["stop_grace_sec"] if grace is None else grace)
        if not ((soft == hard == 0) or (0 < soft < hard)) or grace < 0:
            raise CliConfigurationError(
                "Request timeouts require both limits to be 0 (unlimited), or "
                "0 < soft_timeout_sec < hard_timeout_sec, "
                "and stop_grace_sec >= 0"
            )
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
