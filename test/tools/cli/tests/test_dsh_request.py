import json
from pathlib import Path

import pytest

from tools.cli.models import CliRunRequest
from tools.cli.registry import DEFAULT_CONFIG_PATH, CliConfigurationError, CliRegistry


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


def _dsh_argv(tmp_path, *, profile='build', session_id=None, options=None):
    request = CliRunRequest(cli='dsh', model='model', prompt='task', cwd=tmp_path, profile=profile,
                            session_id=session_id, options=options or {})
    argv = CliRegistry().build(request, check_executable=False).argv
    return argv[argv.index('--profile'):]  # drop the Windows launcher prefix, if resolved


@pytest.mark.parametrize('profile', ['plan', 'build'])
def test_dsh_without_options_keeps_the_plain_command(tmp_path, profile):
    assert _dsh_argv(tmp_path, profile=profile) == ['--profile', 'headless', '--json', 'task']
    assert _dsh_argv(tmp_path, profile=profile, session_id='s-1') == [
        '--profile', 'headless', '--json', '--session-id', 's-1', 'task']


def test_dsh_patch_layers_expand_in_order_on_start_and_resume(tmp_path):
    layers = [str(tmp_path / 'first layer.yml'), str(tmp_path / 'second.yml')]
    expanded = ['--patch', layers[0], '--patch', layers[1]]
    assert _dsh_argv(tmp_path, options={'patch': layers}) == ['--profile', 'headless', *expanded, '--json', 'task']
    assert _dsh_argv(tmp_path, session_id='s-1', options={'patch': layers}) == [
        '--profile', 'headless', *expanded, '--json', '--session-id', 's-1', 'task']


def test_option_values_pass_through_verbatim(tmp_path):
    odd = str(tmp_path / '{cwd} literal.yml')
    assert _dsh_argv(tmp_path, options={'patch': [odd]})[2:4] == ['--patch', odd]


@pytest.mark.parametrize('cli,options', [
    ('dsh', {'layer': ['x.yml']}),     # dsh declares no such option
    ('codex', {'patch': ['x.yml']}),   # codex declares no options at all
    ('dsh', {'patch': ['']}),          # empty value
])
def test_undeclared_or_empty_options_are_errors(cli, options):
    with pytest.raises(CliConfigurationError):
        CliRegistry().build(CliRunRequest(cli=cli, model='model', prompt='task', cwd=Path.cwd(), options=options),
                            check_executable=False)


def test_request_round_trip_keeps_options(tmp_path):
    request = CliRunRequest(cli='dsh', model='model', prompt='task', cwd=tmp_path, options={'patch': ['a.yml', 'b.yml']})
    assert CliRunRequest.from_dict(json.loads(json.dumps(request.to_dict()))).options == {'patch': ['a.yml', 'b.yml']}


def _registry_with(tmp_path, mutate):
    data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding='utf-8'))
    mutate(data['clis'])
    path = tmp_path / 'clis.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def _break_slot(clis):
    clis['dsh']['profiles']['build']['args'][2] = '--x={options}'


def _slot_without_declaration(clis):
    clis['codex']['profiles']['build']['args'].insert(0, '{options}')


def _template_without_value(clis):
    clis['dsh']['options']['patch'] = ['--patch']


def _repeated_slot(clis):
    clis['dsh']['profiles']['build']['args'].insert(0, '{options}')


@pytest.mark.parametrize('mutate', [_break_slot, _slot_without_declaration, _template_without_value, _repeated_slot])
def test_malformed_option_declarations_fail_validation(tmp_path, mutate):
    with pytest.raises(CliConfigurationError):
        CliRegistry(_registry_with(tmp_path, mutate))


@pytest.mark.parametrize('profile,mode', [('plan', 'read-only'), ('build', 'danger-full-access')])
def test_dsh_profiles_choose_their_permission_preset(tmp_path, profile, mode):
    # DSH falls back to workspace-write when DSH_PERMISSION_MODE is unset; each profile states its own preset
    request = CliRunRequest(cli='dsh', model='model', prompt='task', cwd=tmp_path, profile=profile)
    assert CliRegistry().build(request, check_executable=False).env['DSH_PERMISSION_MODE'] == mode
