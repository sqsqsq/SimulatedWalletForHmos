# Unified Agent CLI Runtime

`tools/cli` provides one provider-neutral, replayable interface for
invoking agent CLIs. It does not import business runners.

## Supported CLIs

The central registry is `config/clis.json`. It currently declares:

- `agent` (Cursor Agent)
- `opencode`
- `claude`
- `codex`
- `dsh` (DeepSeek Harness headless CLI)

Business tools select only a registry name and model. They never pass raw CLI
arguments. Each registry entry maps the common default behavior to the concrete
CLI permissions and flags it requires.

## Permission profiles

Every CLI exposes the same two profile names, so callers never have to learn
provider-specific vocabulary:

| Profile | Meaning | How each provider implements it |
|---|---|---|
| `plan` | Read and reason only — no file writes, no command execution | `claude --permission-mode plan` / `agent --mode plan` / `codex --sandbox read-only` / `opencode --agent plan` / `dsh --profile headless` with `DSH_PERMISSION_MODE=read-only` |
| `build` | May write the workspace and run commands | `claude --dangerously-skip-permissions` (capped at 5 USD) / `agent --force --trust` / `codex --yolo` / `opencode --auto --agent build` / `dsh --profile headless` with `DSH_PERMISSION_MODE=danger-full-access` |

`codex` additionally offers `plan_schema` (`plan` plus `--output-schema`). It has
no `resume_args`, so it cannot be used where session continuation is required.

### `dsh` notes

- The process runs in the requested workspace. Windows Electron launchers are
  resolved to the executable and entry script; `ELECTRON_RUN_AS_NODE=1` preserves
  their CLI behavior and multiline tasks remain a single argument.

- Both `plan` and `build` invoke the shipped `headless` profile. The sandbox
  preset is chosen by the `DSH_PERMISSION_MODE` environment variable (DSH
  defaults to `workspace-write` when it is unset), so each profile sets it in its
  `env`: `plan` → `read-only`, `build` → `danger-full-access`, matching the other
  CLIs' build contract. Under `workspace-write` DSH confines commands with a
  write-restricted token, and a confined process cannot open libuv pipe stdio
  for its own children (`spawn ... EPERM`). The model is DSH profile
  configuration (`agent-default-model`), not argv. Point the entry at dedicated DSH
  profiles (for example `batch-plan` / `batch-build` created with
  `dsh --from-default-profile headless <name>` plus a patch layer) to split the
  presets; custom OpenAI-compatible model routes are declared in the same
  patch and resolved by route key from the DSH credential store.
- The request `model` is recorded as metadata; headless has no `--model` flag
  (`model_in_argv: false` in the registry entry opts out of the `{model}`
  argv-placeholder requirement — the model selection is DSH profile config).
- Patch layers: the entry declares the launcher option `patch`
  (`"options": {"patch": ["--patch", "{value}"]}`) and every profile carries the
  `{options}` slot after `--profile <name>`. The caller names the layers:
  `CliRunRequest(..., options={"patch": [<path>, ...]})` expands to one
  `--patch <path>` per value, in order, on start and resume alike; without
  options the argv is unchanged. The runtime knows no project file — which
  layer to load (for example a project-materialized verifier tool) belongs to
  the business repo's own configuration. An option the entry does not declare
  is a configuration error, not silently dropped.
- Resume adopts the persisted DSH session (`--session-id`); session state lives
  under the DSH home directory, while this runtime keeps per-run artifacts only.
- `dsh` failures are classified from the structured `turn_end` error payload
  (for example `code: MISSING_CREDENTIAL` → `auth_required`).
- Native `tool_call {callId, tool, input}` becomes a `tool` event with status
  `started`; `tool_result {callId, status, result}` becomes a `tool` event with
  the same `tool_call_id`, the provider status unchanged (`completed`, `error`,
  …; missing → `unknown`) and `result` as `tool_output`. The result names no
  tool, so consumers pair calls and results by run and `tool_call_id`.
- The DSH JSON stream bounds long strings (8 KiB per string, 32 KiB per event)
  and marks such events `truncated: true`; the model itself received the full
  value. Every DSH event carries this as `source_truncated` (true/false) so
  readers know the stored text may be shortened. Providers that do not report
  it leave `source_truncated` null, and older records without the field read as
  null too.

Request timeout overrides may set both `soft_timeout_sec` and `hard_timeout_sec`
to zero to disable elapsed-time limits. Registry defaults remain finite; mixed
zero/positive, negative, or reversed limits are rejected. Explicit stop requests
and process ownership checks continue to apply to unlimited requests.

> Renamed 2026-08-10 (was `readonly` / `workspace_write` / `full_access` / `build`).
> The old names described each provider's own vocabulary rather than the shared
> contract; callers had to know which name meant "safe" per provider.

## Python API

```python
from pathlib import Path
from tools.cli import CliClient, CliRunRequest

# The caller owns this directory and its retention policy.
client = CliClient(runtime_root="output/my-tool/cli-runtime")
request = CliRunRequest(
    cli="opencode",
    model="alibaba-cn/glm-5.1",
    prompt="Inspect the repository and summarize the result.",
    cwd=Path("."),
)

# Blocking call
result = client.run(request, on_event=lambda event: print(event.type, event.content))

# Detached call and cursor-based event reading
handle = client.start(request)
page = client.poll(handle.run_id, cursor=0, wait_sec=30)
state = client.status(handle.run_id)
client.stop(handle.run_id)

# Agent conversation continuation. This creates a new run linked to the old run.
continued = client.resume(
    CliRunRequest(
        cli="opencode",
        model="alibaba-cn/glm-5.1",
        prompt="Continue with the next step.",
        cwd=Path("."),
        session_id=result.session_id,
    ),
    parent_run_id=result.run_id,
)
```

`resume` resumes an agent conversation; it does not revive an exited operating
system process.

### Detached resume

`start()` also accepts a request carrying `session_id`, which continues the same
agent conversation without blocking the caller:

```python
handle = client.start(
    CliRunRequest(..., session_id=previous.session_id, profile=profile),
    parent_run_id=previous.run_id,
)
```

The new run links to `parent_run_id`, reports the same `session_id`, and is
observed through the usual `poll`/`status` cursor. Callers that must stay
responsive while a model works use this instead of the blocking `resume()`.

## Caller-owned runtime state

Each run gets an isolated directory under the `runtime_root` supplied by the
caller:

- `request.json`: complete standard request
- `run.json`: lifecycle state and result
- `events.jsonl`: normalized, cursor-addressable events
- `raw.jsonl`: original stdout lines
- `worker.log`: detached-worker diagnostics

Normalized public event types include `lifecycle`, `session`, `text`,
`reasoning`, `tool`, `usage`, `error`, and `cli_output`. Provider raw JSON is
kept only in `raw.jsonl`; it is not exposed through `CliEvent`.

If normalized event capture fails, the runtime force-stops the provider process
and returns `failure_kind=event_stream_failed`; it never leaves an unobservable
agent running in the background.

## Commands

```powershell
python -m tools.cli.scripts.validate_clis
python -m tools.cli --runtime-root output/my-tool/cli-runtime describe --cli opencode --model MODEL --prompt test
python -m tools.cli --runtime-root output/my-tool/cli-runtime run --cli opencode --model MODEL --prompt test
python -m tools.cli --runtime-root output/my-tool/cli-runtime start --cli opencode --model MODEL --prompt test
python -m tools.cli --runtime-root output/my-tool/cli-runtime poll RUN_ID --cursor 0 --wait-sec 30
python -m tools.cli --runtime-root output/my-tool/cli-runtime status RUN_ID
python -m tools.cli --runtime-root output/my-tool/cli-runtime stop RUN_ID
```

## Test policy

Deterministic contract and lifecycle tests use `tests/fake_cli.py` and saved
JSONL fixtures; these tests are mandatory.

Real provider smoke tests are optional:

```powershell
python -m tools.cli.scripts.smoke_test --cli agent --model MODEL
python -m tools.cli.scripts.smoke_test --cli claude --model MODEL
```

For Cursor Agent and Claude, authentication, subscription, quota, billing, or
model availability failures produce `SKIP_ENVIRONMENT` and a zero smoke-test
exit code. Command construction errors, adapter crashes, stuck processes, and
unmanaged process termination remain real failures.

## Ownership boundary

This runtime owns provider configuration, command construction, process
lifecycle, session capture, normalized streaming, and durable run state.
Business-specific interpretation remains with callers. In particular, Debate
schema decisions and DAG phase/telemetry rules do not belong in this package.
