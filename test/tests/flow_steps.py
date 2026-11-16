"""夹具走流程关卡的一种写法：盘点缺口 → `status` 取问法 → `decide --ask --reply` 记人的原话。

与产品协议同一条路：问法由脚本生成，人签记在问过之后。夹具不另造捷径，
测试里的人签与真实运行留下的记录同形。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from ext_workspace import ensure_framework, project_root_of  # noqa: F401  (夹具从这里取)
from design_fixture import answer, walk_to_design, write_gaps  # noqa: F401
import design_kit


def walk_to_complete(flow: Callable[..., dict], src: Path,
                     scope_text: str = "本 AR 承载自动充值签约与管理") -> None:
    """用真实流程命令走完材料确认与定位、放好同根的准入蓝图（开发版扩展）：走完即「可以成文」。"""
    walk_to_design(flow, src, design_kit.ACCESS, scope_text)
