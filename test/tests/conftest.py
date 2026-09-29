"""测试起的每个 node 进程都带上 ts-node 转译缓存（见 ts_transpile_cache.cjs）：Framework 原生模块不再每个进程重新转译。

缓存按内容取键，放系统临时目录，跨轮复用；删掉它只会让下一轮重新转译。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_PRELOAD = Path(__file__).with_name("ts_transpile_cache.cjs").resolve()
os.environ.setdefault("STORY_TEST_TS_CACHE", str(Path(tempfile.gettempdir()) / "story-ts-transpile-cache"))
os.environ["NODE_OPTIONS"] = " ".join(filter(None, [os.environ.get("NODE_OPTIONS", ""), f'--require "{_PRELOAD.as_posix()}"']))
