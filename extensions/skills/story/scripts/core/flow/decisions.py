"""人答记录（`decide`）：人签记在问过之后。

两类入口：

- `--gate material_scope`：材料关卡。人明确用编号或整句标签选一项才认；脚本把摆出的全部选项
  连同人的原话记进契约当前轮。
- `--ask --item --reply` / `--replies-file`：设计后必要问答。问题与选项从**已落盘的问法**取，
  调用方不再重填；记录只存当时问法、原话与出处，不持有目标/版本，也不产生已批准状态。

校验不过也照记的只限材料关卡的业务拒绝（退出码 2、不得前进）；问答记录先落盘再导出来源版本，
导出失败时报告派生未完成，不让人重答。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow.state import (
    FlowError, GATES, in_update, last_gate, load, log, now, require, round_gates, save)
from flow.inputs import GAPS, MATERIAL_REQUEST_KEYS, consume_sidecar
from flow.routing import inputs_answer, live_materials, material_state, next_step
from flow import asks


def export_answers(feature_root: Path, what: str) -> dict:
    """答复已经保存：把此刻的人答原件导出成来源版本、刷新材料索引，返回新索引。

    导出与答复是两件事：导出失败时答复照样生效，报清楚派生没完成、怎么重试，不让人再答一次。
    """
    from materials import registry  # noqa: PLC0415 —— 人答导出由材料索引刷新承担
    try:
        return registry.refresh(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(f"{what}已经记下并生效；导出人答原件、刷新材料索引没完成（{exc}）。"
                        "不要重答：排除问题后跑 `story_flow.py round` 重试派生（材料没变不开新轮）") from exc


def _material_record(feature_root: Path, contract: dict, args: argparse.Namespace) -> tuple[dict, int]:
    reply = str(args.reply or "").strip()
    if not reply:
        raise FlowError("--reply 不能为空：记人的原话")
    gate = "material_scope"
    manifest = live_materials(feature_root)
    settled = inputs_answer(contract) if in_update(contract) else last_gate(round_gates(contract), gate)
    if settled and settled["outcome"] == "accepted":
        raise FlowError(f"本轮材料已经确认过了（{settled['chosen']}）——材料再变会开新一轮，"
                        "那时才轮到重新表态；现在按 `status` 的 next 往下走")
    ask = asks.current_material(feature_root, args.ask)
    options = ask["options"]
    picked = asks.pick_explicit(options, reply)
    current = contract["rounds"][-1]

    outcome, reason, code = "accepted", None, 0
    if picked["key"] in MATERIAL_REQUEST_KEYS:
        # 人陈述的是事实：料放进去了。磁盘上却既没有待导入的原件、材料也没变，
        # 那这一笔记下去下一步无处可去——原地重提，让人再放一次。
        state = material_state(feature_root, current, manifest)
        if not state["pending"] and not state["changed"]:
            outcome, code = "rejected", 2
            reason = ("来源收件箱（含子目录）里没有待导入的件、材料也没变：把文档或界面设计图放进 "
                      f"{feature_root.name}/inbox/（可以整个文件夹放）后再答一次")

    record = {
        "gate": gate, "ask_id": ask["ask_id"], "question": ask["block"],
        "options": [{"no": o["no"], "key": o["key"], "label": o["label"]} for o in options],
        "chosen": picked["key"], "no": picked["no"], "label": picked["label"],
        "reply": reply, "outcome": outcome, "by": "human", "at": now(),
    }
    if reason:
        record["reason"] = reason
    current.setdefault("gates", []).append(record)
    save(feature_root, contract)
    if outcome == "accepted":
        manifest = export_answers(feature_root, f"第 {current['round']} 轮材料确认")
    step, action = next_step(feature_root, contract, manifest)
    if step != f"await_gate:{gate}":
        asks.clear(feature_root)
    if outcome == "accepted":
        consume_sidecar(feature_root, GAPS)
    log(f"第 {current['round']} 轮记录材料确认：第 {picked['no']} 项 {picked['key']} → {outcome}"
        + (f"（{reason}）" if reason else ""))
    result = {"round": current["round"], "gate": gate, "chosen": picked["key"],
              "no": picked["no"], "outcome": outcome}
    if reason:
        result["reason"] = reason
    log(f"下一步：{action}")
    result["next"], result["nextAction"] = step, action
    return result, code


def _replies(args: argparse.Namespace) -> list[dict]:
    """这一次要记的题：单题用 `--item/--reply`，多题同一答复或逐题答复用 `--replies-file`。

    脚本只按定位读取，不猜自由段落属于哪一题。
    """
    if args.replies_file:
        if args.item or args.reply:
            raise FlowError("--replies-file 与 --item/--reply 只用一种：多题写文件，单题直接给")
        path = Path(args.replies_file)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise FlowError(f"答复文件 {path} 读不出来（{exc}）") from exc
        except ValueError as exc:
            raise FlowError(f"答复文件 {path} 不是合法 JSON（{exc}）") from exc
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            raise FlowError(f"答复文件 {path.name} 须是对象且 items 是非空数组："
                            '{"items":[{"item_id":"本组题号","reply":"完整原话"}]}')
        out, seen = [], set()
        for i, raw in enumerate(items, 1):
            if not isinstance(raw, dict):
                raise FlowError(f"答复文件第 {i} 项不是对象")
            item = str(raw.get("item_id") or "").strip()
            reply = str(raw.get("reply") or "").strip()
            if not item or not reply:
                raise FlowError(f"答复文件第 {i} 项缺 item_id 或 reply")
            if item in seen:
                raise FlowError(f"答复文件里 {item} 出现了不止一次")
            seen.add(item)
            out.append({"item_id": item, "reply": reply})
        return out
    item = str(args.item or "").strip()
    reply = str(args.reply or "").strip()
    if not item:
        raise FlowError("记设计问答要带 --item <本组题号>：问题与选项从已落盘的问法取")
    if not reply:
        raise FlowError("--reply 不能为空：记人的原话；保持待定也照实写")
    return [{"item_id": item, "reply": reply}]


def _design_questions(feature_root: Path, contract: dict, args: argparse.Namespace) -> dict:
    ask = asks.current_design(feature_root)
    if ask is None:
        raise FlowError("没有待回答的设计问答：先按必要问人的条件写好问法文件，"
                        "跑 `status` 的 `--questions-file` 生成一次问法，再记人答")
    if str(args.ask or "").strip() != str(ask["ask_id"]):
        raise FlowError(f"--ask「{args.ask or '缺失'}」不是当前问法（{ask['ask_id']}）："
                        "问法换过了，按 `status` 给出的当前问法记")
    by_id = {str(it["item_id"]): it for it in ask["items"]}
    answered = asks.answered_item_ids(feature_root, contract, ask["ask_id"])
    wanted = _replies(args)
    for reply in wanted:
        if reply["item_id"] not in by_id:
            listed = "、".join(str(it["item_id"]) for it in ask["items"])
            raise FlowError(f"当前问法里没有题「{reply['item_id']}」（现有：{listed}）：照 `ask.items` 取题号")
        if reply["item_id"] in answered:
            raise FlowError(f"题「{reply['item_id']}」已经记过原话：同一题不重记，"
                            "有真正新事实再准备下一组问法")
    current = contract["rounds"][-1]
    recorded = []
    for reply in wanted:
        item = by_id[reply["item_id"]]
        entry = {"ask_id": ask["ask_id"], "item_id": str(item["item_id"]),
                 "question": item["question"], "options": list(item["options"]),
                 "reply": reply["reply"], "at": now(), "source_ref": item["source_ref"]}
        recorded.append(entry)
    # 原话按操作身份落：init 在材料 round；开着 update 在同一操作的 record.answers。
    # 收口只改操作状态，不搬动、不改写这些原话。
    rid = str((contract.get("update") or {}).get("open") or "")
    if rid:
        rec = asks._update_record(feature_root, rid)
        rec.setdefault("answers", []).extend(recorded)
        (feature_root.joinpath("AR", "story-src", "updates", rid) / "record.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        current.setdefault("answers", []).extend(recorded)
        save(feature_root, contract)
    export_answers(feature_root, f"设计问答 {ask['ask_id']} 的 {len(recorded)} 条原话")
    # 部分答复返回与普通 status 共用同一次读取：展示块只含余下问题，action 与 ask_block 引用同一字符串。
    shown = asks.pending_view(feature_root, ask, contract)
    pending = shown["pending"]
    if not pending:
        asks.clear(feature_root)
    # 原话已经落盘：算下一步失败不能反过来把这一步报成没发生；让人跑 `status` 取当前位置。
    try:
        step, action = next_step(feature_root, contract, live_materials(feature_root))
    except FlowError as exc:
        step, action = "status", f"原话已记下；下一步暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取"
    result = {"ask": ask["ask_id"], "recorded": [
                  {"item_id": e["item_id"], "reply": e["reply"], "at": e["at"]} for e in recorded],
              "pending": pending, "next": step}
    if pending:
        action = ("原话已记下。把返回的 ask.block 作为本次消息；只摆还没答的问题，全部答完即回原生设计续行：\n"
                  + shown["block"])
        step = "await_questions"
        result["next"] = step
        result["ask_block"] = shown["block"]
    else:
        action = (f"这组设计问答已全部答完（{ask['ask_id']}）：回到原生设计按原话继续，"
                  "原问题与原话留在 answers 原件里。" + action)
    log(f"设计问答 {ask['ask_id']} 记下 {len(recorded)} 条原话，待答 {len(pending)} 题")
    result["nextAction"] = action
    return result


def cmd_decide(feature_root: Path, args: argparse.Namespace) -> tuple[dict, int]:
    contract = require(load(feature_root))
    gate = str(args.gate or "")
    if gate and gate not in GATES:
        # argparse 已经按合同值域拦；手写调用也按同一处判
        raise FlowError(f"--gate「{gate}」不是本版流程的关卡（现有：{'、'.join(GATES)}）")
    design = bool(args.item or args.replies_file)
    if gate == "material_scope":
        if design:
            raise FlowError("材料确认不带 --item/--replies-file：那两个参数只用于设计问答")
        return _material_record(feature_root, contract, args)
    if design:
        return _design_questions(feature_root, contract, args), 0
    if args.ask:
        raise FlowError("记设计问答要带 --item <题号> 与 --reply；材料确认请带 `--gate material_scope`")
    return _material_record(feature_root, contract, args)