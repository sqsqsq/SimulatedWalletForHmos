"""关卡决策（`decide`）：人签记在问过之后，模型的判断记成提议。

人签只来自人的回话：`--ask` 必须是 `status` 当前生成的那份问法，`--reply` 记人的原话，
脚本把原话映射到选项，连同摆出的全部选项一起记进契约。校验不过也照记，只是退出码 2、不得前进。
模型的判断用 `--propose` 记为 `by: model`，不推进流程，下一次停等时列给人确认。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from flow.state import (
    FlowError, GATES, in_update, last_gate, load, log, now, require, round_gates, save)
from flow.inputs import (
    GAPS, MATERIAL_REQUEST_KEYS, SPLIT_PARTS, consume_sidecar, read_split_parts)
from flow.routing import inputs_answer, live_materials, material_state, next_step
from flow import asks


def cmd_decide_update(feature_root: Path, item: str, reply: str) -> dict:
    """更新期间人定的一件事 —— **记原话，不造人签**。

    与三级关卡分开：那三级是起手才有的事；这里记的是一次更新里冒出来、只有人能定的事
    （来源冲突、要改已经承诺过的口径、沿用谁在哪一版的表态）。它不扩大关卡集合。
    没有开着的更新就不记：记下来也无从定位它属于哪一轮。
    """
    if not item.strip():
        raise FlowError("--update 要写清定的是哪件事")
    if not reply.strip():
        raise FlowError("--reply 不能为空：人签只认人的原话")
    contract = load(feature_root)
    if contract is None:
        raise FlowError("这个单没走过 /story，没有可以记录的流程契约")
    state = contract.get("update") or {}
    if not state.get("open"):
        raise FlowError("现在没有开着的更新：先跑 `story_flow.py update` 起一轮，"
                        "这条记录要挂在某一轮上")
    entry = {"item": item.strip(), "reply": reply.strip(), "by": "human", "at": now()}
    state.setdefault("decisions", []).append(entry)
    contract["update"] = state
    save(feature_root, contract)
    log(f"更新 {state['open']} 记下一条人的决定：{entry['item']}")
    return {"update": state["open"], "recorded": entry,
            "action": f"已记：{entry['item']}。update-notes 里引用这一条"}


def cmd_propose(feature_root: Path, args: argparse.Namespace) -> dict:
    """模型的判断记成提议：`by: model`，不推进流程，下一次停等请人确认。"""
    gate = args.gate or GATES[0]
    chosen = str(args.chosen or "").strip()
    why = str(args.why or "").strip()
    if not chosen or not why:
        raise FlowError("--propose 要写 --chosen（提议选哪一项）与 --why（一句理由）")
    contract = require(load(feature_root))
    entry = {"gate": gate, "chosen": chosen, "why": why, "by": "model", "at": now()}
    if args.item:
        entry["item"] = str(args.item)
    contract.setdefault("proposals", []).append(entry)
    save(feature_root, contract)
    step, action = next_step(feature_root, contract, live_materials(feature_root))
    return {"proposed": entry, "next": step, "nextAction": action,
            "action": "提议已记，流程不因它前进：下一次停等时它会列进问法，请人确认"}


def _options_for(ask: dict, args: argparse.Namespace) -> tuple[list[dict], dict | None]:
    if ask["gate"] != "meeting":
        return ask["options"], ask.get("recommend")
    item = next((it for it in ask["items"]
                 if it["item"] == str(args.item or "") and it["meeting"] == str(args.meeting or "")),
                None)
    if item is None:
        raise FlowError(f"当前问法里没有会议话题「{args.meeting}/{args.item}」——"
                        "--meeting 写 <主名>@<sha8>，--item 写话题 id，照 `ask.items` 取")
    return item["options"], item.get("recommend")


def cmd_decide(feature_root: Path, args: argparse.Namespace) -> tuple[dict, int]:
    gate = args.gate or GATES[0]     # 值域由 argparse 的 choices 拦
    reply = str(args.reply or "").strip()
    if not reply:
        raise FlowError("--reply 不能为空：记人的原话。自己的判断用 --propose")
    contract = require(load(feature_root))
    manifest = live_materials(feature_root)
    # 第一级问的是事实，人答与导入互不挡路：他可以放好料再答，也可以先答再放，
    # 所以前置是「本轮这一级还没定」，不比对 next 的字面。其余几级只能做流程当前那一步。
    if gate == "material_scope":
        settled = inputs_answer(contract) if in_update(contract) else             last_gate(round_gates(contract), gate)
        if settled and settled["outcome"] == "accepted":
            raise FlowError(f"本轮第一级已经定了（{settled['chosen']}）——材料再变会开出新一轮，"
                            "那时才轮到重新表态；现在按 `status` 的 next 往下走")
    else:
        expected, action = next_step(feature_root, contract, manifest)
        if expected != f"await_gate:{gate}":
            raise FlowError(f"当前这一步不是 {gate}：{action}（`status` 的 next 是 {expected}）")
    ask = asks.current(feature_root, args.ask, gate)
    options, recommend = _options_for(ask, args)
    if gate == "meeting" and any(
            g.get("gate") == "meeting" and g.get("outcome") == "accepted"
            and g.get("meeting") == args.meeting and g.get("item") == args.item
            for g in contract["rounds"][-1].get("gates") or []):
        raise FlowError(f"话题 {args.meeting}/{args.item} 已经记过人的裁决")
    picked, mapped = asks.map_reply(options, reply, str(args.chosen or "").strip() or None, recommend)
    current = contract["rounds"][-1]

    parts: list[dict] = []
    if gate == "split_carrier":
        # 承载定案：份表此时才成形（哪一份归本 AR 由这一步的选择决定）
        parts = read_split_parts(feature_root, feature_root.name)
        if not parts:
            raise FlowError(
                "split_carrier 缺定案内容：把拆分份表写进 "
                f"{'/'.join(SPLIT_PARTS)}（每份含 seq / carrier / scope / depends_on，"
                "carrier 为本 AR 的恰好一份 = 人选中的那份，其余份写兄弟 AR 单号或「待立项」）")
        mine = next(p for p in parts if p["carrier"] == feature_root.name)
        if str(mine["seq"]) != picked["key"]:
            raise FlowError(
                f"人选的是第 {picked['key']} 份，份表里归本 AR 的却是第 {mine['seq']} 份"
                f"（{mine['scope']}）——改份表的 carrier")

    outcome, reason, code = "accepted", None, 0
    if gate == "material_scope" and picked["key"] in MATERIAL_REQUEST_KEYS:
        # 人陈述的是事实：料放进去了。磁盘上却既没有待导入的原件、材料也没变，
        # 那这一笔记下去下一步无处可去——原地重提，让人再放一次。
        state = material_state(feature_root, current, manifest)
        if not state["pending"] and not state["changed"]:
            outcome, code = "rejected", 2
            reason = ("收件箱里没有新文件、材料也没变：把文档或界面设计图放进 "
                      f"{feature_root.name}/inbox/ 后再答一次")

    record = {
        "gate": gate, "ask_id": ask["ask_id"],
        "options": [{"no": o["no"], "key": o["key"], "label": o["label"]} for o in options],
        "chosen": picked["key"], "no": picked["no"], "label": picked["label"],
        "reply": reply, "mapped_by": mapped, "outcome": outcome, "by": "human", "at": now(),
    }
    if reason:
        record["reason"] = reason
    if gate == "meeting":
        # 裁决绑定会议的这一版：新版本到了，旧版本的裁决照旧指向旧原话
        record.update(meeting=args.meeting, item=args.item)
    current.setdefault("gates", []).append(record)
    for p in contract.get("proposals") or []:
        if p.get("gate") == gate and not p.get("resolved") and \
                (gate != "meeting" or p.get("item") == args.item):
            p["resolved"] = record["at"]

    if gate == "split_carrier" and outcome == "accepted":
        # scope_text 由本 AR 那一份推导，不单独登记——同一事实两处写，迟早各说各话
        scope_text = next(p["scope"] for p in parts if p["carrier"] == feature_root.name)
        contract["split"] = {"decided": "split", "settled_round": current["round"],
                             "scope_text": scope_text, "parts": parts}

    save(feature_root, contract)
    # 记一笔关卡不改材料：末尾的下一步沿用开头那一份材料事实
    step, action = next_step(feature_root, contract, manifest)
    if step != f"await_gate:{gate}":
        asks.clear(feature_root)
    if outcome == "accepted":
        if gate == "material_scope":
            consume_sidecar(feature_root, GAPS)
        if gate == "split_carrier":
            consume_sidecar(feature_root, SPLIT_PARTS)
    log(f"第 {current['round']} 轮记录 {gate}：第 {picked['no']} 项 {picked['key']} → {outcome}"
        + (f"（{reason}）" if reason else ""))
    result = {"round": current["round"], "gate": gate, "chosen": picked["key"],
              "no": picked["no"], "mapped_by": mapped, "outcome": outcome}
    if reason:
        result["reason"] = reason
    log(f"下一步：{action}")
    result["next"], result["nextAction"] = step, action
    return result, code

