"""轮次边界：`round` 按材料开一轮，`reopen` 为重拍范围开一轮。

一轮 = 一次材料状态。轮次只由材料清单的 digest 判定，与谁重写了几遍分析无关。
"""
from __future__ import annotations

from pathlib import Path

from materials import registry

from flow.state import (
    FlowError, SCHEMA, after_complete, in_update, load, log, require, save)
from flow.inputs import (
    POSITIONING, SCOPE_OPTIONS, consume_sidecar, read_positioning, read_scope_options)
from flow.routing import frozen_inbox_note, live_materials, next_step


def cmd_round(feature_root: Path) -> dict:
    # 定位与选项集侧车都是 S2b（需求分析）的产物，此刻通常还不存在——
    # round 发生在材料盘点之后、分析之前。写了就消费，没写不失败：
    # 该不该有由 next_step 判（材料没确认前它根本不该有）。
    positioning = read_positioning(feature_root)
    scope_options = read_scope_options(feature_root)

    # 事实一律取当下：调用时机不确定（导入完全可能发生在 round 之后），
    # 所以每次调用都让清单按磁盘现状重算，绝不沿用上一次的快照。
    try:
        manifest = registry.refresh(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    digest = manifest["digest"]
    reference = {"digest": digest}
    # 已经并入正文的原件就是「导过的料」——这一份事实只在清单里，契约不另记哈希
    ingested = sorted(s["file"] for s in manifest["sources"] if s.get("ingested"))

    contract = load(feature_root) or {
        "schema": SCHEMA, "status": "in_progress",
        "rounds": [],
        "split": {"decided": "none", "settled_round": None, "scope_text": None, "parts": []},
        "design": None,
        "design_generated_at": None,
    }
    rounds = contract["rounds"]

    def stamp(entry: dict) -> None:
        """把本次调用取到的事实盖进轮次条目（新轮与幂等轮共用）。"""
        entry["materials"] = reference
        if positioning:
            entry["positioning"] = positioning
        if scope_options:
            entry["scope_options"] = scope_options

    frozen = frozen_inbox_note(feature_root, contract, manifest)
    if frozen:
        log(frozen)

    # 材料没变就不是新一轮。「幂等」只意味着**不新建轮次**，不意味着不更新事实。
    if rounds and (rounds[-1].get("materials") or {}).get("digest") == digest:
        current = rounds[-1]
        stamp(current)
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        consume_sidecar(feature_root, SCOPE_OPTIONS)
        log(f"材料未变（{digest}），仍在第 {current['round']} 轮（已刷新事实快照）")
        return {"round": current["round"], "created": False, "materials": digest,
                "positioning": bool(current.get("positioning")),
                "scopeOptions": len(current.get("scope_options") or [])}

    # 收口之后材料又变了：**不开新轮**。收口的含义是「本轮范围已定、可以进 spec」，
    # 此后补一份说明文件、改一个错字都不该把流程推回未定状态。
    #
    # 开轮的代价是死锁：新轮没有任何决策，而 `decide` 被 status=complete 挡住，
    # 于是既走不下去也退不回来，只能去手改契约文件——那在正式路径上不允许。
    # 要重新决策请显式跑 `reopen`。
    #
    # **判的是「收口及之后」不是「恰好在 complete」**：`story_written` 与已归档比它更靠后，
    # 而 story 的材料快照就是当轮的 digest——新轮一开，快照所指就换了一批材料，
    # 那份已经定稿的 story 就对不上它自己声称的依据了。
    #
    # **update 期间同理**：这一轮是一次有依据的修订，范围沿用本单已定的；新材料登记进当前轮，
    # reopen 之后也一样——开新轮会把人送回材料与范围关卡。
    if (after_complete(contract) or in_update(contract)) and rounds:
        current = rounds[-1]
        stamp(current)
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        consume_sidecar(feature_root, SCOPE_OPTIONS)
        log(f"材料有变（{digest}）：只更新第 {current['round']} 轮的材料指纹，未开新轮。"
            "要重新拍板范围，先收口这一轮 update，再跑 `story_flow.py reopen`")
        return {"round": current["round"], "created": False, "materials": digest,
                "afterComplete": True,
                "positioning": bool(current.get("positioning")),
                "scopeOptions": len(current.get("scope_options") or [])}

    entry = {
        "round": len(rounds) + 1,
        "materials": reference,
        "positioning": None,
        "scope_options": None,
        "gates": [],
    }
    stamp(entry)
    rounds.append(entry)
    save(feature_root, contract)
    consume_sidecar(feature_root, POSITIONING)
    consume_sidecar(feature_root, SCOPE_OPTIONS)
    log(f"登记第 {entry['round']} 轮（材料 {digest}，已并入正文的原件 {len(ingested)} 件）")
    return {"round": entry["round"], "created": True, "materials": digest,
            "positioning": bool(entry.get("positioning")),
            "scopeOptions": len(entry.get("scope_options") or [])}


def cmd_reopen(feature_root: Path) -> dict:
    """重拍范围——**唯一的回退出口**，只做这一件事。

    收口之后要重新拍板范围（材料变了、会上有要人定的话题、范围本身定错了）时走它：
    状态回到 `in_progress`，另开一轮承接重拍的关卡，材料没变也一样——当前轮已记的
    范围关卡不替重拍授权。新一轮沿用本轮的材料基准、本 AR 定位与范围选项集，
    分析要改就改侧车再跑 `round`。

    已登记的成文一并作废：范围重拍之后 story 要按新范围重新登记。
    只改 story 不用走这里——改完重跑 `story` 就是重新登记。

    update 这一轮开着时不重拍：update 沿用本单已定的范围，先 `update close` 收口这一轮。
    """
    contract = require(load(feature_root))
    status = contract.get("status")
    if in_update(contract):
        raise FlowError("update 这一轮还开着：它沿用本单已定的范围，不在这一轮里重拍。"
                        "先按 `phases/update.md` 收口这一轮（`update --action close`，范围问题写进保留项），"
                        "再跑 `story_flow.py reopen`")
    if not after_complete(contract):
        raise FlowError(f"流程还没收口（现在是 {status}），范围关卡本来就开着：跑 `story_flow.py status` 取下一步")
    undone = sorted(key for key in ("story_written_at", "story_digests") if contract.pop(key, None) is not None)
    current = contract["rounds"][-1]
    entry = {"round": len(contract["rounds"]) + 1,
             "materials": current.get("materials"),
             "positioning": current.get("positioning"),
             "scope_options": current.get("scope_options"),
             "gates": []}
    contract["rounds"].append(entry)
    contract["status"] = "in_progress"
    save(feature_root, contract)
    # **重开到此成立。** 往下只是算下一步：通常是范围关卡；材料变了先盘点。
    # 算下一步要按磁盘现状读材料，读不出来不能反过来把重开报成失败：盘上已经是 in_progress，
    # 再跑 reopen 只会被「还没收口」挡回。所以只兜这一段，写入失败照常失败。
    try:
        step, action = next_step(feature_root, contract, live_materials(feature_root))
    except FlowError as exc:
        step, action = None, (f"下一步暂时算不出来（{exc}）。重开已经生效，不要再跑 reopen；"
                              "按这个原因修好材料后跑 `story_flow.py status` 取下一步")
    log(f"流程已重开（{status} → in_progress），重拍的关卡记进第 {entry['round']} 轮"
        + ("；成文登记已作废，范围定了之后 story 重新登记" if undone else "")
        + f"。下一步：{action}")
    return {"status": "in_progress", "rounds": len(contract["rounds"]),
            "storyRegistrationUndone": undone, "next": step, "action": action}
