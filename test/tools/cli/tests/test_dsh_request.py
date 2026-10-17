from pathlib import Path

import pytest

from tools.cli.models import CliRunRequest
from tools.cli.registry import CliConfigurationError, CliRegistry


def test_dsh_keeps_workspace_and_multiline_task(tmp_path):
    task = 'first line\nsecond line with spaces'
    resolved = CliRegistry().build(CliRunRequest(cli='dsh', model='metadata-model', prompt=task, cwd=tmp_path, soft_timeout_sec=0, hard_timeout_sec=0), check_executable=False)
    assert resolved.cwd == tmp_path.resolve()
    assert resolved.argv[-1] == task
    assert resolved.env['ELECTRON_RUN_AS_NODE'] == '1'
    assert resolved.soft_timeout_sec == resolved.hard_timeout_sec == 0


@pytest.mark.parametrize('soft,hard', [(0,1), (1,0), (-1,0), (2,1), (1,1)])
def test_invalid_timeout_pairs_remain_errors(soft, hard):
    with pytest.raises(CliConfigurationError):
        CliRegistry().build(CliRunRequest(cli='dsh', model='model', prompt='task', cwd=Path.cwd(), soft_timeout_sec=soft, hard_timeout_sec=hard), check_executable=False)
