# Unified Agent CLI Runtime

> **来源**：本目录来自 `AIDefectHelpler` 仓库的 `tools/cli`，随本仓交付以避免跨项目路径依赖。
> **与上游的关系**：**两边已分叉，不能整目录覆盖同步**。已知分叉点：`config/clis.json` 的 profile
> 定义（本仓 Cursor Agent 用 `readonly`/`workspace_write`，上游用 `plan`/`build`）、`registry.py`
> （上游多了 Windows npm `.CMD`/`.BAT` 包装器解析）、`runner.py` 与 `process_control.py` 的注释与实现。
> 要取上游改动请**逐文件比对后合入**；算法层与 provider 适配仍建议回上游维护。
> **使用方**：`test/story/scripts/run_case.py` 通过 `from tools.cli import CliClient, CliRunRequest` 调用。

`tools/cli` provides one provider-neutral, replayable interface for
invoking agent CLIs. It does not import business runners.

## Supported CLIs

The central registry is `config/clis.json`. It currently declares:

- `agent` (Cursor Agent)
- `opencode`
- `claude`
- `codex`

Business tools select only a registry name and model. They never pass raw CLI
arguments or provider profile names. Each registry entry maps the common
default behavior to the concrete CLI permissions and flags it requires.

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
Business-specific interpretation remains with callers — case scheduling, phase
gating, scoring, and any harness-specific telemetry rules do not belong in this
package.
