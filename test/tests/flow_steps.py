"""夹具走流程关卡的一种写法：盘点缺口 → `status` 取问法 → `decide --ask --reply` 记人的原话。

与产品协议同一条路：问法由脚本生成，人签记在问过之后。夹具不另造捷径，
测试里的人签与真实运行留下的记录同形。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def write_gaps(src: Path, missing: tuple[str, ...] = (), why: str = "夹具：材料齐了") -> None:
    """材料关卡的缺口文件：`missing` 为空时推荐「现有材料就是全部」。"""
    src.mkdir(parents=True, exist_ok=True)
    (src / ".material-gaps.json").write_text(
        json.dumps({"missing": list(missing), "why": why}, ensure_ascii=False), encoding="utf-8")


def answer(flow: Callable[..., dict], gate: str, reply: str, *extra: str) -> dict:
    """按当前问法答一关：先 `status` 取 `ask_id`，再记人的原话。`flow` 返回解析后的 JSON。"""
    ask = flow("status")["ask"]
    return flow("decide", "--gate", gate, "--ask", ask["ask_id"], "--reply", reply, *extra)


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
    """用真实流程命令走完 S1–S3 并提交提取稿：材料关卡、需求分析、范围关卡、收口。"""
    src.mkdir(parents=True, exist_ok=True)
    (src / "design-draft.md").write_text(draft_text, encoding="utf-8")
    flow("init")
    flow("round")
    write_gaps(src)
    answer(flow, "material_scope", "夹具：现有材料就是全部", "--chosen", "confirm_scope")
    (src / ".positioning.json").write_text(json.dumps(
        {"scope_text": scope_text, "sr_related_ars": []}, ensure_ascii=False), encoding="utf-8")
    (src / ".scope-options.json").write_text(json.dumps(
        [{"key": "carry_all", "label": "按当前范围整体承载"}], ensure_ascii=False), encoding="utf-8")
    flow("round")
    answer(flow, "scope_decision", "夹具：整体承载", "--chosen", "carry_all")
    flow("complete", "--from", "AR/story-src/design-draft.md")
