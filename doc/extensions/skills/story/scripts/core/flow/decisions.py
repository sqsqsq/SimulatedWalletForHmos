"""关卡决策（`decide`）：把摆出的选项与人选的那一项一起记进契约。

校验与记录是同一次调用，所以不存在「忘了记」；校验不过也照记，只是退出码 2、不得前进。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from flow.state import (
    FlowError, GATES, last_gate, load, log, now, require, round_gates, save)
from flow.inputs import (
    GATE_OPTIONS, MATERIAL_CHOICES, MATERIAL_REQUEST_KEYS, SCOPE_OPTIONS, SPLIT_PARTS,
    consume_sidecar, read_gate_options, read_split_parts, sidecar_gate, split_carrier_options)
from flow.routing import live_materials, material_state, next_step
from flow.meetings import topic_options


def cmd_decide_update(feature_root: Path, item: str, basis: str) -> dict:
    """更新期间人拍的一次板 —— **记原话，不造人签**。

    与三级关卡分开：那三级问的是「材料够不够、范围怎么定、哪份承载」，是起手才有的事；
    这里记的是一次更新里冒出来、只有人能定的事（来源冲突、要改已经承诺过的口径、
    沿用谁在哪一版的表态）。**它不扩大关卡集合**，也不因此多一次停等——
    停不停由方法页定，这条只负责把人真说过的话落到盘上。

    没有开着的更新就不记：那说明这次根本不在更新里，记下来也无从定位它属于哪一轮。
    `update-notes` 里写着「已确认」不算——那是模型的转述，人签只认这条命令记下的原话。
    """
    if not item.strip():
        raise FlowError("--update 要写清定的是哪件事")
    if not basis.strip():
        raise FlowError("--basis 不能为空：人签只认真实原话，模型的转述不算")
    contract = load(feature_root)
    if contract is None:
        raise FlowError("这个单没走过 /story，没有可以记录的流程契约")
    state = contract.get("update") or {}
    if not state.get("open"):
        raise FlowError("现在没有开着的更新：先跑 `story_flow.py update` 起一轮，"
                        "这条记录要挂在某一轮上，否则事后无从定位它属于哪一次")
    entry = {"item": item.strip(), "basis": basis.strip(), "by": "human", "at": now()}
    state.setdefault("decisions", []).append(entry)
    contract["update"] = state
    save(feature_root, contract)
    log(f"更新 {state['open']} 记下一条人的决定：{entry['item']}")
    return {"update": state["open"], "recorded": entry,
            "action": f"已记：{entry['item']}。依据是人的原话，"
                      "后续说明里引用这一条，不要另写「人工已批准」之类的字样"}


def cmd_decide(feature_root: Path, args: argparse.Namespace) -> tuple[dict, int]:
    gate = args.gate or GATES[0]     # 值域由 argparse 的 choices 拦
    if not (args.basis or "").strip():
        raise FlowError("--basis 不能为空：决策的依据（用户原话）是契约的审计价值所在")

    chosen = str(args.chosen or "").strip()
    if not chosen:
        raise FlowError("--chosen 不能为空")

    contract = require(load(feature_root))
    current = contract["rounds"][-1]
    # 本命令里的材料事实**首次需要时取一份**，此后三处共用它：前置路由、补料请求的
    # 驳回判断、末尾的下一步。这条路径不写材料，三处之间不会有第二个时点；
    # 契约变了（多记一条关卡）不改材料基准，`changed` 不必重算。
    manifest: dict | None = None

    def snapshot() -> dict:
        nonlocal manifest
        if manifest is None:
            manifest = live_materials(feature_root)
        return manifest

    # 只能做流程当前允许的那一步。顺序由 `next_step` 一处定义，decide 不自己判前置——
    # 两处各写一套「什么时候能做什么」，迟早对不上。
    #
    # **第一级例外，它问的是另一件事**：`next_step` 回答「下一步做什么」，
    # 而收件箱里有料时那一步是导入。人能不能表态与导入没做没关系——
    # 他可以放好料先答一句，也可以等导完再答，两种都是同一次表态。
    # 所以这一级的前置是「本轮这一级还没有定下来」，不比对 next 的字面。
    if gate == "material_scope":
        settled = last_gate(round_gates(contract), gate)
        if settled and settled["outcome"] == "accepted":
            raise FlowError(
                f"本轮第一级已经定了（{settled['chosen']}）——材料再变会开出新一轮，"
                "那时才轮到重新表态；现在按 `status` 的 next 往下走")
    else:
        expected, action = next_step(feature_root, contract, snapshot())
        if expected != f"await_gate:{gate}":
            raise FlowError(f"当前这一步不是 {gate}：{action}（`status` 的 next 是 {expected}）")

    # 选项来源按关卡分工——**只有第一级读侧车**，后两级从契约取，关卡摆不出分析没定的选项。
    # 后两级不读它，但盘上留着别级的侧车仍要拦：那说明摆选项与走流程对不上，
    # 放过去的话，第一级下一次会把这份别人的侧车读成「材料又有新缺口」。
    if gate == "material_scope":
        options = read_gate_options(feature_root, gate, current["round"])
        if chosen not in MATERIAL_CHOICES:
            raise FlowError(
                f"material_scope 的 --chosen 须为 {' / '.join(MATERIAL_CHOICES)} 之一，实为「{chosen}」")
    elif gate == "scope_decision":
        at = sidecar_gate(feature_root)
        if at and at != gate:
            raise FlowError(f"盘上的选项侧车是给 {at} 级摆的，这一步是 {gate}——先清掉或改对级别")
        # 分析定几项就只能摆几项：现编的空壳选项在此被结构性挡住
        options = current.get("scope_options") or []
        if not options:
            raise FlowError(
                f"本轮尚未登记范围定法选项集：把需求分析产出的全部选项写进 "
                f"{'/'.join(SCOPE_OPTIONS)} 后重跑 `round`")
    elif gate == "meeting":
        # 选项集就是会议判断里那个话题的 options：脚本只认 key，人选了哪一项就记哪一项
        options = topic_options(feature_root, str(getattr(args, "meeting", "") or ""),
                                str(getattr(args, "item", "") or ""))
    else:  # split_carrier
        at = sidecar_gate(feature_root)
        if at and at != gate:
            raise FlowError(f"盘上的选项侧车是给 {at} 级摆的，这一步是 {gate}——先清掉或改对级别")
        # 份表选项由脚本从选定维度的 parts 生成——不读侧车、不混退回项，
        # 第三级只问「承载哪一份」，退回是另一件事
        options = split_carrier_options(current)

    if chosen not in [o["key"] for o in options]:
        raise FlowError(
            f"--chosen「{chosen}」不在本次选项集里（现有：{'、'.join(o['key'] for o in options)}）"
            "——选项集要么漏了这一项，要么选错了 key")

    parts: list[dict] = []
    if gate == "split_carrier":
        # 承载定案：份表此时才成形（哪一份归本 AR 由这一步的选择决定）
        parts = read_split_parts(feature_root, feature_root.name)
        if not parts:
            raise FlowError(
                "split_carrier 缺定案内容：把拆分份表写进 "
                f"{'/'.join(SPLIT_PARTS)}（每份含 seq / carrier / scope / depends_on，"
                "carrier 为本 AR 的恰好一份 = 用户选中的那份，其余份写兄弟 AR 单号或「待立项」）。"
                "只留在对话里，会话一断就丢")
        if parts:
            # 定案的必须是选中的：人选了第 k 份，份表就得把第 k 份给本 AR。
            # 两处各写一次，不核对的话「选的」与「记的」可以完全无关而全绿。
            mine = next(p for p in parts if p["carrier"] == feature_root.name)
            if str(mine["seq"]) != chosen:
                raise FlowError(
                    f"人选的是第 {chosen} 份，份表里归本 AR 的却是第 {mine['seq']} 份"
                    f"（{mine['scope']}）——选择与定案对不上，改份表的 carrier 或改 --chosen")

    outcome, reason, code = "accepted", None, 0
    if gate == "material_scope" and chosen in MATERIAL_REQUEST_KEYS:
        # 人陈述的是事实：料放进去了。磁盘上却既没有待导入的原件、材料也没变，
        # 那这一笔记下去下一步无处可去——原地重提，让人再放一次。
        state = material_state(feature_root, current, snapshot())
        if not state["pending"] and not state["changed"]:
            outcome, code = "rejected", 2
            reason = ("收件箱里没有新文件、材料也没变：把文档或界面设计图放进 "
                      f"{feature_root.name}/inbox/ 后再选一次")

    # 关卡决策只认人签，没有代签这一档：模型判「材料足够」就以自己的名义记掉关卡的话，
    # 材料补充环节整个被跳过。停等的开关不能交给被停的那一方，所以这一栏没有参数可填。
    record = {
        "gate": gate, "options": options, "chosen": chosen, "outcome": outcome,
        "by": "human", "basis": args.basis.strip(), "at": now(),
    }
    if reason:
        record["reason"] = reason
    if gate == "meeting":
        # 裁决绑定会议的这一版：新版本到了，旧版本的裁决照旧指向旧原话
        record.update(meeting=args.meeting, item=args.item)
    current.setdefault("gates", []).append(record)

    if gate == "split_carrier" and outcome == "accepted":
        # scope_text 由本 AR 那一份推导，不单独登记——同一事实两处写，迟早各说各话
        scope_text = next(p["scope"] for p in parts if p["carrier"] == feature_root.name)
        contract["split"] = {"decided": "split", "settled_round": current["round"],
                             "scope_text": scope_text, "parts": parts}

    save(feature_root, contract)
    consume_sidecar(feature_root, GATE_OPTIONS)
    if gate == "split_carrier" and outcome == "accepted" and parts:
        consume_sidecar(feature_root, SPLIT_PARTS)
    log(f"第 {current['round']} 轮记录 {gate}：{chosen} → {outcome}"
        + (f"（{reason}）" if reason else ""))
    result = {"round": current["round"], "gate": gate, "chosen": chosen, "outcome": outcome}
    if reason:
        result["reason"] = reason
    # 下一步与 `status` 同一处算：两处各写一套「记完这一笔该干什么」，迟早对不上。
    step, action = next_step(feature_root, contract, snapshot())
    log(f"下一步：{action}")
    result["next"], result["nextAction"] = step, action
    return result, code
