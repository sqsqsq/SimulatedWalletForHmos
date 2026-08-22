# Validation

本目录自带的离线校验。**改动 `tools/cli` 后手动跑**——本仓的门禁
(`pytest test/story/tests`) 对象是 story 能力，不含本目录。

Run from the repository root:

```powershell
python -m tools.cli.scripts.validate_clis
python -m unittest discover -s tools/cli/tests -v
python -m compileall -q tools/cli
```

These checks do not require provider accounts or network access. Real CLI smoke
tests are optional and follow the environment classification documented in
`README.md`.

> The checks above do **not** cover spawning the worker process — `CliClient.start()`
> launches `python -m tools.cli.worker` in a subprocess, and a wrong module path or
> `cwd` fails silently: the run produces no events and the caller waits until timeout.
> After touching `api.py`, also verify the module resolves:
>
> ```powershell
> python -m tools.cli.worker --help
> ```
