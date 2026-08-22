from __future__ import annotations

import subprocess
import sys
import time
import uuid

import pytest

from tools.cli.process_control import (
    WindowsProcessJob,
    force_kill_tree,
    popen_group_options,
)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows creation flags")
def test_windows_cli_process_group_has_no_visible_console() -> None:
    flags = int(popen_group_options()["creationflags"])

    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
    assert flags & subprocess.CREATE_NO_WINDOW


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object lifecycle")
def test_windows_job_force_kills_cli_process_tree() -> None:
    child_code = (
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)'],"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "time.sleep(20)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        **popen_group_options(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    job = WindowsProcessJob.create(uuid.uuid4().hex, proc)
    try:
        time.sleep(0.2)
        assert force_kill_tree(proc.pid, job.name) is True
        proc.wait(timeout=10)
    finally:
        job.close()
        if proc.poll() is None:
            proc.kill()
