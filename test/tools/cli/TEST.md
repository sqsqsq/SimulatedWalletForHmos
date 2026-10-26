# CLI runtime 验证与同步

`tools/cli/` 与本目录的 `tests/`、`fixtures/` 从中心仓 `C:/Users/kangz/.agents/tools/cli-runtime` 同步；版本与提交见 `tools/cli/.sync-stamp.json`。运行时与契约测试的修正回中心仓完成，再同步到本仓。本文件维护本仓的验证入口。

在仓根执行以下离线检查，不需要模型账户或网络，不启动真实模型：

```powershell
python -m pytest test/tools/cli -n auto --dist loadscope
python -m tools.cli.scripts.validate_clis
python -m tools.cli.worker --help
python -m compileall -q -j 0 tools/cli test/scripts
python test/scripts/run_multi_case.py plan --all --jobs 2
python C:/Users/kangz/.agents/tools/cli-runtime/sync.py --check .
```

契约测试包含 fake CLI 的启动、事件读取、会话续行、终止与进程所有权验证；`worker --help` 另核子进程模块入口可解析。Story 消费方相关回归按 `test/TEST.md` §5 执行。

`tests/test_story_runtime_regression.py` 保留本仓同步前已有的日志流式读取、OpenCode 参数顺序和故障分类回归；这些回归已回到中心仓维护并随运行时同步。同步与验证结果见 `test/EVOLUTION.md` 的对应记录。

真实 Case 统一通过 `test/scripts/run_multi_case.py` 启动，授权、交互与证据要求见 `test/TEST.md` §0–§4。dsh 的模型选择限制见 `tools/cli/README.md` 的 dsh notes：请求的 `model` 只作元数据，实际模型由 dsh profile 配置决定。
