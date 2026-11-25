"""轮次边界：`round` 按材料开一轮。

一轮 = 一次材料状态。轮次只由材料清单的 digest 判定，与谁重写了几遍分析无关。
设计开始之后材料再变只登记进本轮，不开新轮；真实范围变化走 update，由蓝图负责方修订。
"""
from __future__ import annotations

from pathlib import Path

from materials import registry

from flow.state import (
    FlowError, SCHEMA, closed, in_update, load, log, save)
from flow.inputs import POSITIONING, consume_sidecar, read_positioning
from flow.routing import closed_inbox_note


def cmd_round(feature_root: Path) -> dict:
    # 定位侧车是 S2b（需求分析）的产物，此刻通常还不存在——round 发生在材料盘点之后、
    # 分析之前。写了就消费，没写不失败：该不该有由路由判。
    positioning = read_positioning(feature_root)

    # 事实一律取当下：调用时机不确定（导入完全可能发生在 round 之后），
    # 所以每次调用都让清单按磁盘现状重算，绝不沿用上一次的快照。
    try:
        manifest = registry.refresh(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    digest = manifest["digest"]
    reference = {"digest": digest}
    # 已经导入的来源就是「导过的料」——这一份事实只在材料索引里，契约不另记哈希
    imported = [s for s in manifest["sources"] if s.get("kind") != "answer"]

    contract = load(feature_root) or {
        "schema": SCHEMA, "status": "gathering", "rounds": [],
    }
    rounds = contract["rounds"]

    def stamp(entry: dict) -> None:
        """把本次调用取到的事实盖进轮次条目（新轮与幂等轮共用）。"""
        entry["materials"] = reference
        if positioning:
            entry["positioning"] = positioning

    note = closed_inbox_note(feature_root, contract, manifest)
    if note:
        log(note)

    # 材料没变就不是新一轮。「幂等」只意味着**不新建轮次**，不意味着不更新事实。
    if rounds and (rounds[-1].get("materials") or {}).get("digest") == digest:
        current = rounds[-1]
        stamp(current)
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        log(f"材料未变（{digest}），仍在第 {current['round']} 轮（已刷新事实快照）")
        return {"round": current["round"], "created": False, "materials": digest,
                "positioning": bool(current.get("positioning"))}

    # 设计开始之后材料又变了：**不开新轮**。收口的含义是「材料已确认、设计已经按它开始」，
    # 此后补一份说明文件、改一个错字都不该把流程推回未定状态；新开一轮会把已开始的设计与人的
    # 材料确认晾在一轮没有任何决策的轮次后面。真实范围变化走 update，由蓝图负责方修订。
    #
    # `story_written` 同样算收口：story 的材料快照就是当轮的 digest——新轮一开，快照所指就换了一批材料。
    # 据新料改完 story，重跑 `story` 重新登记。
    #
    # **update 期间同理**：这一轮是一次有依据的修订，材料登记进当前轮，
    # 开新轮会把人送回已确认的材料关卡。
    if (closed(feature_root, contract) or in_update(contract)) and rounds:
        current = rounds[-1]
        stamp(current)
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        log(f"材料有变（{digest}）：只更新第 {current['round']} 轮的材料指纹，未开新轮。"
            "真实范围变化走 update，由蓝图负责方修订")
        return {"round": current["round"], "created": False, "materials": digest,
                "afterComplete": True, "positioning": bool(current.get("positioning"))}

    entry = {
        "round": len(rounds) + 1,
        "materials": reference,
        "positioning": None,
        "gates": [],
    }
    stamp(entry)
    rounds.append(entry)
    save(feature_root, contract)
    consume_sidecar(feature_root, POSITIONING)
    log(f"登记第 {entry['round']} 轮（材料 {digest}，已导入的来源 {len(imported)} 个）")
    return {"round": entry["round"], "created": True, "materials": digest,
            "positioning": bool(entry.get("positioning"))}