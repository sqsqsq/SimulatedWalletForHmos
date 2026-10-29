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
from design_fixture import answer, design_input, walk_to_design, write_gaps  # noqa: F401
import design_kit


#: 评审记录人工区的首版：三态与修改意见
HUMAN_ZONE = "评审结论：\n- [ ] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n"


def settled_decision(did: str, title: str, point: str, conclusion: str, *,
                     said: str = "按这个做", who: str = "产品负责人在需求澄清会上",
                     category: str = "范围与交付", decider: str = "需求负责人") -> dict:
    """一条已定的议题：依据引人的原话，评审人复核结论。"""
    return {"id": did, "status": "settled", "review_mode": "confirm", "title": title,
            "clarification": f"**决策点**：{point}\n\n**依据**：{who}说「{said}」。\n\n"
                             f"**结论与影响**：{conclusion}",
            "decider": decider, "category": category}


def open_decision(did: str, title: str, point: str, options: list[tuple[str, str]],
                  suggestion: str, *, category: str = "范围与交付",
                  decider: str = "产品负责人") -> dict:
    """一条待评审的议题：列可选的做法与后果，给建议。"""
    listed = "\n".join(f"{i}. {how}——{effect}" for i, (how, effect) in enumerate(options, 1))
    return {"id": did, "status": "open", "review_mode": "choice", "title": title,
            "clarification": f"**决策点**：{point}\n\n**可选的做法**：\n{listed}\n\n"
                             f"**建议**：{suggestion}",
            "decider": decider, "category": category}


def walk_to_complete(flow: Callable[..., dict], src: Path, draft_text: str,
                     scope_text: str = "本 AR 承载自动充值签约与管理") -> None:
    """用真实流程命令走完 S1–S3 并交给设计（开发版扩展）：走完即「可以成文」。"""
    walk_to_design(flow, src, draft_text, design_kit.ACCESS, scope_text)
