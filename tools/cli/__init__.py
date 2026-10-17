"""Unified runtime for invoking supported agent CLIs.

This package is intentionally independent from the debate and DAG harness
tools.  Business tools should depend only on the public objects exported here.
"""

from .api import CliClient
from .models import (
    CliEvent,
    CliRunRequest,
    EventPage,
    FailureKind,
    RunHandle,
    RunResult,
    RunStatus,
)
from .registry import (
    CliConfigurationError,
    CliNotFoundError,
    CliRegistry,
    ResumeNotSupportedError,
)

__all__ = [
    "CliClient",
    "CliEvent",
    "CliRunRequest",
    "EventPage",
    "FailureKind",
    "RunHandle",
    "RunResult",
    "RunStatus",
    "CliConfigurationError",
    "CliNotFoundError",
    "CliRegistry",
    "ResumeNotSupportedError",
]
