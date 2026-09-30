"""测试侧的设计来源夹具：做法在 `test/scripts/design_fixture.py`（与失效形态运行器共用），这里给定开发版扩展的
framework-access 作 ACCESS。"""
from __future__ import annotations

from design_fixture import *  # noqa: F401,F403
from design_fixture import COMPONENT, GENERIC_DECISION  # noqa: F401
from ext_workspace import DEV_EXT

#: 装在临时消费工程里的开发版 framework-access：夹具用它调原生
ACCESS = DEV_EXT / "hooks" / "shared" / "framework-access.mjs"
