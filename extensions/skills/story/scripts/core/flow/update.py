"""`/story update` 的文件侧支持 —— **脚本只回答确定的事**。

这一层做三件机械的事：把本次执行前的现场完整留一份、与上次已处理的版本比一遍、
把结果说清楚。取回来的新内容与人补的料一样进 `inbox/`，走 init 那条材料链——
这里不另开第二个入料口。**变化意味着什么、要改哪里，一概不判**——
那是模型读原文的事（方法在 `phases/update.md`）。

顺序是**先定输入，再检测**：`inputs` 报告上游与本地各有什么（不建任何东西），
模型据此在第一级关卡问人要不要补料；人答完、料登记进本轮，`prepare` 比一遍并开这一轮。
比较结果是交给模型的事实：一个字节没变也照常开轮，变化意味着什么、要不要改由模型读原文判；
没有业务变化时 update-notes 写明比过什么、为什么不用改，照常收口。
**没查到不等于没变**：比较基准缺席、来源读不到，都单列出来说清可查范围，不许混进「无变化」。

落点在 `AR/story-src/updates/<id>/`，它不在材料扫描的范围里（材料只认合同声明的正文源、
`ux-reference`/`assets` 与会议原件），所以本层自己的写入不会把材料版本顶出一个新轮次。

需求目录里的文件按章节合同的 `update_files` 分四类：本扩展写的可改件（editable）、可重生件（regenerate）、
受保护件（protected，没登记的文件也按它）、只改字段的流程契约（field_owned）。快照、恢复与收口都按这一份分类，
受保护件的字节从不改写，流程契约只动它自己的字段。

五个动作：`inputs` 报输入、`prepare` 比一遍并开这一轮、`status` 报现在开着什么、
`close` 收口并留下可比的正文、`restore` 按本轮前后的指纹把本扩展改过的文件退回开轮之前。
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from materials import registry

from flow.routing import basis_drift, inputs_answer, material_state
from flow.state import (CONTRACT, FlowError, STORY, REVIEW, STORY_CONTRACT, file_sha256, system_requirement,
                        load, log, now, registration_drift, round_gates, save)

#: 本层全部落点的根。放在 story-src 下面：它是过程目录，AR 根只留交付件。
UPDATES = ("AR", "story-src", "updates")
#: 除材料正文之外，判「跟上次比变了没有」要看的交付件——**人会直接动的那两份人读件**。
#:
#: 连同合同登记的三份上游正文（`registry.source_docs()`）与收件箱（由材料事实回答，
#: 不按文件哈希比），一共六项。决策登记、写作设计与知识判断不在里面：
#: 它们是模型据这几份写出来的中间真源，随交付件的修订而变，是结果不是原因。
#: 盘上没有的跳过，不当成被删（`_scan`）。
PRODUCTS = (STORY, REVIEW)
#: 这一轮还算开着的状态：恢复留下冲突时轮次照旧开着，等人处理完再恢复或收口。
ACTIVE = ("open", "restore_conflicted")
#: 本轮请求的终点：只取材与澄清（materials），或要同步人读件（documents）。
RESULTS = ("materials", "documents")


def update_files() -> dict[str, list[str]]:
    """章节合同里的 `update_files`：四类文件各自的相对路径模式（`/**` 结尾是整棵子树）。"""
    try:
        sets = json.loads(STORY_CONTRACT.read_text(encoding="utf-8").lstrip("\ufeff"))["update_files"]
        return {k: [str(p) for p in sets[k]] for k in ("editable", "regenerate", "protected", "field_owned")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FlowError(f"{STORY_CONTRACT.name} 的 update_files 读不出来（{exc}）：快照、恢复与收口都按它分文件") from exc


def _matches(rel: str, pattern: str) -> bool:
    return rel.startswith(pattern[:-2]) if pattern.endswith("/**") else rel == pattern


def owner(rel: str, sets: dict[str, list[str]] | None = None) -> str:
    """一个需求目录相对路径归哪一类；没登记的按受保护件。"""
    sets = sets or update_files()
    for kind in ("field_owned", "protected", "editable", "regenerate"):
        if any(_matches(rel, p) for p in sets[kind]):
            return kind
    return "protected"


def _owned(feature_root: Path) -> dict[str, str]:
    """盘上本扩展拥有的文件（可改件与可重生件）→ 原始字节的 SHA-256。"""
    sets = update_files()
    out = {}
    for path in sorted(feature_root.rglob("*")):
        rel = path.relative_to(feature_root).as_posix()
        if path.is_file() and not path.is_symlink() and owner(rel, sets) in ("editable", "regenerate"):
            out[rel] = file_sha256(path)
    return out


def _updates_dir(feature_root: Path) -> Path:
    return feature_root / Path(*UPDATES)


def _records(feature_root: Path) -> list[tuple[str, dict]]:
    """盘上已有的操作记录，按 id 排序。读不出来的那一条要出声，不静默跳过。"""
    base = _updates_dir(feature_root)
    if not base.is_dir():
        return []
    out = []
    for d in sorted(base.iterdir()):
        path = d / "record.json"
        if not path.is_file():
            continue
        try:
            out.append((d.name, json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))))
        except ValueError as exc:
            raise FlowError(f"{path} 不是合法 JSON（{exc}）：它由本脚本写入，"
                            "若曾手工编辑请修正语法，或把整个 "
                            f"{d.name} 目录移走再重跑") from exc
    return out


def _scan(feature_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """当前盘上这一轮要盯的文件 → 指纹。**读不到的单列，不当成不存在。**

    「文件不在」与「文件在但读不出来」是两件事：前者是删除，后者是环境问题。
    混成一个的话，一次权限错误会被报成「上游把这份材料删了」，而模型据此去删下游功能。
    所以读不到的那几份**带着 key 单独返回**——`_compare` 要拿它把这些从「删除」里摘出去，
    否则分开这一步只做了一半：`_scan` 分清了，下游又合回去。
    """
    seen: dict[str, str] = {}
    unreadable: dict[str, str] = {}
    rels = [Path(rel) for rel in registry.source_docs()] + [Path(*p) for p in PRODUCTS]
    for rel in rels:
        path = feature_root / rel
        key = rel.as_posix()
        if not path.exists():
            continue
        try:
            seen[key] = registry.file_digest(path) or ""
        except OSError as exc:
            unreadable[key] = str(exc)
    return seen, unreadable


def _baseline(records: list[tuple[str, dict]]) -> dict[str, str] | None:
    """上次已处理的版本。没有就是没有——**首次不能判「历史没变过」**。

    只认 closed：open 的那一条说明上一轮没走完，它的清单是「开始时的样子」，
    拿它当基准会把上一轮自己改的东西算成这一轮的新变化。
    """
    for _, rec in reversed(records):
        if rec.get("status") == "closed" and isinstance(rec.get("files"), dict):
            return {str(k): str(v) for k, v in rec["files"].items()}
    return None


def _compare(current: dict[str, str], base: dict[str, str] | None,
             unreadable: dict[str, str]) -> dict:
    """与基准比：新增 / 修改 / 删除。基准缺席时**如实说不知道**，不报「无变化」。

    读不到的那几份不进任何一类：它们上次在、这次没读出来，**那不是删除**，
    是这一轮对它们判不了。混进 `removed` 的话，模型会拿着「上游删了它」去删下游功能。
    """
    if base is None:
        return {"complete": False, "added": [], "modified": [], "removed": [],
                "unknown": sorted(current)}
    return {"complete": True,
            "added": sorted(k for k in current if k not in base),
            "modified": sorted(k for k in current if k in base and current[k] != base[k]),
            "removed": sorted(k for k in base if k not in current and k not in unreadable),
            "unknown": []}


def _mirror(feature_root: Path, owned: dict[str, str], dest: Path) -> int:
    """本次执行前本扩展拥有的那几份的原字节，恢复据它写回。**先存够再往下走**：存不下就别开始。

    受保护件不进镜像：恢复从不改写它们。流程契约另存一份，只给收口核「开轮时的登记状态」用。
    """
    for rel in [*owned, "/".join(CONTRACT)]:
        src = feature_root / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / rel)
    return len(owned)


def _write_diffs(feature_root: Path, base_dir: Path | None, changed: list[str], dest: Path) -> int:
    """能取到正文的，写一份逐行差异。取不到旧正文就只留清单——**不编差异**。

    旧正文的来源是上一条 closed 记录的 `after/`；没有它时，这一轮只能说「这几份变了」，
    说不出「变成什么」。那是事实，写成一句比伪造一段 diff 有用。
    """
    if base_dir is None or not base_dir.is_dir():
        return 0
    written = 0
    for rel in changed:
        old = base_dir / rel
        new = feature_root / rel
        if not old.is_file() or not new.is_file():
            continue
        a = old.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        b = new.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        text = "".join(difflib.unified_diff(a, b, fromfile=f"上次/{rel}", tofile=f"现在/{rel}"))
        if not text.strip():
            continue
        out = dest / (rel.replace("/", "__") + ".diff")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        written += 1
    return written

def _contract(feature_root: Path) -> dict:
    contract = load(feature_root)
    if contract is None:
        raise FlowError("这个单没走过 /story：先跑 `story_flow.py init`，"
                        "update 更新的是已经存在的产物")
    return contract


def _resume(records: list[tuple[str, dict]]) -> dict | None:
    """上一轮还开着：**不新建镜像**——新的会把旧的恢复依据盖掉。"""
    for rid, rec in reversed(records):
        if rec.get("status") in ACTIVE:
            return {"comparison": "resume", "update": rid,
                    "notes": f"AR/story-src/updates/{rid}/update-notes.md",
                    "action": f"上一次 update（{rid}）还开着：先读它的 update-notes 与 before/ "
                              "接着做完，或按它的记录还原现场。不新建这一轮的镜像。"}
    return None


def _collect(feature_root: Path, contract: dict, records: list[tuple[str, dict]]) -> dict:
    """输入一次收齐：交付件与上游正文对上次的差异、读不到的、收件箱的材料事实、上次以来新导入的原件。

    `inputs` 与 `prepare` 读的是同一份——两处各收一遍，迟早一处说有变化、一处说没有。
    材料事实就是 init 的第一级关卡用的那两个（`material_state`），不另算一套。
    """
    current, unreadable = _scan(feature_root)
    diff = _compare(current, _baseline(records), unreadable)
    rounds = contract.get("rounds") or []
    last = rounds[-1] if rounds else {}
    state = material_state(feature_root, last)
    # 没登记过材料基准不算「变了」：那是轮次自己缺指纹，由流程契约的判据报
    registered = bool((last.get("materials") or {}).get("digest"))
    return {"current": current, "unreadable": unreadable, "diff": diff,
            "changed": diff["added"] + diff["modified"] + diff["removed"],
            "superseded_hint": _superseded_hint(feature_root, state["pending"]),
            "pending": state["pending"], "materials_changed": registered and state["changed"],
            "imported": _imported_since(feature_root, records)}


def _sources(feature_root: Path) -> list[dict]:
    """已并入正文的原件（文件名、摘要、归类），取自材料清单。读不出清单时为空——那由 `round` 报。"""
    try:
        manifest = registry.read(feature_root)
    except registry.MaterialError:
        return []
    return [{"file": s.get("file"), "sha256": s.get("sha256"), "class": s.get("class")}
            for s in manifest.get("sources") or [] if s.get("ingested")]


def _imported_since(feature_root: Path, records: list[tuple[str, dict]]) -> list[dict]:
    """上一次收口（或成文基准）以来新并入正文的原件，**含只取图的**：它们的正文不进六项比较，
    是不是带来了业务变化由模型读原件判。上一次没有留原件清单时，全部列出。"""
    closed = _latest(records, "closed")
    seen = {(s.get("file"), s.get("sha256")) for s in ((closed[1].get("sources") if closed else None) or [])}
    return [s for s in _sources(feature_root) if (s["file"], s["sha256"]) not in seen]


def _superseded_hint(feature_root: Path, pending: list[str]) -> list[dict]:
    """新原件可能取代的旧原件：收件箱里**已归类**的同类原件。**只列，不判**——是不是新版由你读了定。

    导入链把同一类的原件按名拼接成目标正文，没有「替代」一说：旧原件留在收件箱里，
    目标就是两版拼在一起；只备份目标文件而不处理旧原件，下次导入时两版照样拼回去。
    新原件自己还没归类时，列出全部已归类的原件。
    """
    inbox = feature_root / "inbox"
    path = inbox / ".classify.json"
    if not path.is_file():
        return []
    try:
        classes = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise FlowError(f"inbox/.classify.json 不是合法 JSON（{exc}）：修正归类件再跑") from exc
    if not isinstance(classes, dict):
        raise FlowError("inbox/.classify.json 应是 {\"文件名\": \"类别\"} 对象")
    known = {name: cls for name, cls in classes.items() if (inbox / name).is_file()}
    out = []
    for new in pending:
        cls = known.get(new)
        olds = sorted(n for n, c in known.items() if n != new and (cls is None or c == cls))
        if olds:
            out.append({"new": new, "same_class": olds,
                        "note": f"若 {new} 取代其中某份，导入前先把 inbox 里那份移进 .backups/local/"})
    return out


RECEIPT = ("AR", "story-src", "fetched.json")


def _receipt(feature_root: Path) -> dict | None:
    """最近一次取材的回执。**原样转交**：取到没有、与本地是否相同由对接层写明，这里不判。"""
    path = feature_root / Path(*RECEIPT)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8").lstrip("\ufeff"))
    except ValueError as exc:
        raise FlowError(f"{'/'.join(RECEIPT)} 读不出来（{exc}）：重跑取材，它会重写回执") from exc


def _fetched_this_round(feature_root: Path, contract: dict,
                        records: list[tuple[str, dict]]) -> bool:
    """这一轮取过上游没有：回执里的取材时刻晚于上一轮 update 收口（或成文登记）的那一刻。"""
    path = feature_root / Path(*RECEIPT)
    if not path.is_file():
        return False
    at = str((_receipt(feature_root) or {}).get("fetchedAt") or "")
    try:
        fetched = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        fetched = None
    if fetched is None or fetched.tzinfo is None:
        raise FlowError(f"{'/'.join(RECEIPT)} 的取材时刻 fetchedAt 不是带时区的 ISO 8601 时刻（{at or '缺失'}）："
                        "对接层按合同写回执，重跑取材")
    closed = _latest(records, "closed")
    stamp = (closed[1].get("closed_at") if closed else None) or contract.get("story_written_at")
    return not stamp or fetched >= datetime.fromisoformat(stamp)


def cmd_update_inputs(feature_root: Path, feature: str, project_root: Path) -> dict:
    """输入阶段：**报告，不建任何东西**。人还没说要不要补料，现在比出来的不是最终的变化。

    在流程契约上记一笔 `update.stage = inputs`：路由据它把这一次停在第一级关卡——
    与 init 同一个关卡、同一份侧车、同一条 `decide`，问的是这一次要不要补料。
    """
    contract = _contract(feature_root)
    records = _records(feature_root)
    resumed = _resume(records)
    if resumed:
        return {**resumed, "paths": _paths(project_root, feature_root)}
    system = system_requirement(feature)
    if system and not _fetched_this_round(feature_root, contract, records):
        # 系统上的评审回稿与改版正文只能经取材进来：没取就比，比出来的是上一次的世界
        raise FlowError("系统需求这一轮还没取上游：先按 SKILL「更新」② 取上游，落点用 "
                        "`update --action status` 返回的 paths，取完再报输入")
    facts = _collect(feature_root, contract, records)
    contract["update"] = {**(contract.get("update") or {}), "stage": "inputs", "inputs_at": now(),
                          "inputs_from": len(round_gates(contract))}
    save(feature_root, contract)
    return {"stage": "inputs", "paths": _paths(project_root, feature_root), "changed": facts["changed"], "unreadable": facts["unreadable"],
            "baseline": facts["diff"]["complete"], "pending": facts["pending"],
            "superseded_hint": facts["superseded_hint"],
            "materials_changed": facts["materials_changed"], "imported": facts["imported"],
            "upstream": _receipt(feature_root) if system else None,
            "action": ("`upstream` 是最近一次取材的回执，展示它的时刻；本次取材成功与否以那次取材自己的结果为准。"
                       if system else "本地需求没有上游；")
                      + "按 `rules/init_analysis.md` S2a 盘点手上的料，缺口写进 `.material-gaps.json`，"
                      "跑 `status` 取问法，问人这一次要不要补料，**停等**。人答了 → `decide` 记原话 → "
                      "收件箱有新原件先导入 → `round` 登记到本轮 → `update --action prepare --result <materials|documents>`"}


def _set_result(root: Path, rec: dict, result: str) -> None:
    """续做中的一轮换终点：取材可以升成要同步人读件，反过来不行——已有人读件受影响就是 documents。"""
    was = rec.get("requested_result")
    if result == was:
        return
    if was == "documents":
        raise FlowError("这一轮登记的请求是 documents（要同步人读件），不能改成 materials：终点由人的请求与受影响的已有结果定，不为收口降级")
    rec["requested_result"] = result
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_update_prepare(feature_root: Path, result: str | None) -> dict:
    """输入定了之后比一遍、开这一轮、该留的留下、该说的说清楚。

    `result` 是这一轮请求的终点，照人的请求记：只取材与澄清、没有已有人读件受影响的是 materials，
    其余是 documents。

    `comparison` 直说比出来的是哪一种：

    - `resume`   上一轮还开着。**不新建镜像**——新的会把旧的恢复依据盖掉；
    - `unchanged` 六项都没变、也没有新并入的原件：照常开轮，要不要改由模型按原文与人的这次要求判；
    - `incomplete` 比较基准缺席或来源读不到：说清可查与不可查的范围，交模型判当前一致性；
    - `changed`  有变化：本轮镜像留着不动，差异与位置交给模型。

    **返回的全是机械事实**：哪几份文件跟上次不一样、新并入了哪些原件、镜像在哪。
    这些事实不表示任何业务结论——「变化意味着什么」由模型读原文回答。
    """
    contract = _contract(feature_root)
    update = contract.get("update") or {}
    if update.get("stage") == "inputs":
        answer = inputs_answer(contract)
        if not answer or answer.get("outcome") != "accepted":
            raise FlowError("输入阶段还没问过人要不要补料：按 `status` 的下一步在第一级关卡停一次，"
                            "人答了、料登记进本轮，再跑 prepare")
    if result not in RESULTS:
        raise FlowError("prepare 要带 --result materials|documents：按人这次的请求记本轮终点——只取材与澄清、"
                        "没有已有人读件受影响的是 materials，其余是 documents")
    records = _records(feature_root)
    resumed = _resume(records)
    if resumed:
        rid, rec = _latest(records, None, ACTIVE)
        _set_result(_updates_dir(feature_root) / rid, rec, result)
        return {**resumed, "requested_result": rec.get("requested_result")}

    facts = _collect(feature_root, contract, records)
    if facts["pending"]:
        raise FlowError("收件箱里还有没并入正文的原件，先导入、`round` 登记到本轮，再 prepare："
                        + "、".join(facts["pending"]))
    current, unreadable, diff, changed = (facts["current"], facts["unreadable"],
                                          facts["diff"], facts["changed"])
    pending, imported = facts["pending"], facts["imported"]

    # id 用时间是为了人一眼看得出先后；撞名就加序号，**不把「同一秒跑了两次」做成失败**。
    stem = now().replace("-", "").replace(":", "").replace("T", "-")[:15]
    rid, n = stem, 1
    while (_updates_dir(feature_root) / rid).exists():
        n += 1
        rid = f"{stem}-{n}"
    root = _updates_dir(feature_root) / rid
    before = root / "before"
    before.mkdir(parents=True)
    owned = _owned(feature_root)
    mirrored = _mirror(feature_root, owned, before)

    base_dir = None
    for prev_id, rec in reversed(records):
        if rec.get("status") == "closed":
            cand = _updates_dir(feature_root) / prev_id / "after"
            base_dir = cand if cand.is_dir() else None
            break
    diffs = _write_diffs(feature_root, base_dir, diff["added"] + diff["modified"], root / "diff")

    contract["update"] = {"open": rid, "opened_at": now()}
    save(feature_root, contract)
    # 这一笔是本层自己的记号（路由据它改去向）。镜像里那份一起更新：
    # 不同步的话，每次 restore 都会把流程契约报成「有人在这之后改过」，
    # 而改它的正是我们自己——真正的冲突会被这条噪声埋掉。
    shutil.copyfile(feature_root / Path(*CONTRACT), before / Path(*CONTRACT))
    record = {"id": rid, "opened_at": now(), "status": "open", "requested_result": result,
              "owned_before": owned, "owned_after": None,
              "files": current, "unreadable": unreadable, "comparison": diff,
              "materials": {"pending": pending, "changed": facts["materials_changed"],
                            "imported": imported},
              "mirror": {"path": f"AR/story-src/updates/{rid}/before", "files": mirrored}}
    (root / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")

    material = bool(pending or facts["materials_changed"] or imported)
    kind = ("changed" if (changed or material)
            else "incomplete" if (not diff["complete"] or unreadable) else "unchanged")
    lines = []
    if changed:
        lines.append("变了的：" + "、".join(changed))
    if facts["materials_changed"]:
        lines.append("材料指纹与本轮登记的对不上：先 `round` 登记到本轮")
    if not diff["complete"]:
        lines.append("没有上次已处理的版本可比：这一轮说不出「原来怎么写」，"
                     "按当前材料与产物核一致性，别补造历史")
    if unreadable:
        lines.append("读不到：" + "、".join(f"{k}（{why}）" for k, why in unreadable.items())
                     + "——这是缺口，不是「没有变化」，更不是「它被删了」")
    if imported:
        lines.append("上次以来新并入正文的原件：" + "、".join(f"{s['file']}（{s['class']}）" for s in imported)
                     + "——只取图的原件正文不进上面的比较，读原件判它带没带来业务变化")
    if kind == "unchanged":
        lines.append("与上次已处理的版本逐份比过没有变化：按原文与人这次的要求判要不要改，"
                     "没有业务变化时 update-notes 写明比过什么、为什么不用改，照常收口")
    log(f"update {rid}：镜像 {mirrored} 份、差异 {diffs} 份")
    return {"comparison": kind, "update": rid, "requested_result": result, "changed": changed, "pending": pending,
            "imported": imported, "superseded_hint": facts["superseded_hint"],
            "unreadable": unreadable, "baseline": diff["complete"], "diffs": diffs,
            "mirror": record["mirror"]["path"],
            "action": "；".join(lines) + f"。原貌留在 AR/story-src/updates/{rid}/before/，"
                      "处置方法见 phases/update.md"}


# ---------------------------------------------------------------------------
# 阶段事实：哪些阶段有产物、闭没闭环。**只读报告**：施工归 Framework，update 不推进、不因它挡收口。
#
# 读的是 harness 自己写的 `<阶段>/reports/summary.json`——它是只读投影，不是我们的账。
# 读不出来就说读不出来：闭没闭环这件事不许猜，猜错的方向是「以为闭了」。
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")


def _phase_facts(feature_root: Path) -> list[dict]:
    out = []
    for phase in PHASES:
        summary = feature_root / phase / "reports" / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8").lstrip("\ufeff"))
        except (OSError, ValueError) as exc:
            out.append({"phase": phase, "readable": False, "why": str(exc)})
            continue
        out.append({"phase": phase, "readable": True, "closure": data.get("closure_status"),
                    "verdict": data.get("verdict"), "subject": data.get("verifier_subject_id")})
    return out


def _paths(project_root: Path, feature_root: Path) -> dict:
    """本需求的本地位置（绝对路径）：取材落点 `inbox` 与人补料同一个入料口，回执跟着工程根走。"""
    return {"project_root": project_root.resolve().as_posix(),
            "feature_root": feature_root.resolve().as_posix(),
            "inbox": (feature_root / "inbox").resolve().as_posix()}


def _latest(records: list[tuple[str, dict]], status: str | None = None,
            among: tuple[str, ...] = ()) -> tuple[str, dict] | None:
    for rid, rec in reversed(records):
        if (status is None and not among) or rec.get("status") == status or rec.get("status") in among:
            return rid, rec
    return None


def cmd_update_status(feature_root: Path, feature: str, project_root: Path) -> dict:
    """现在有没有开着的更新、上一次做到哪、说明在哪。**只报事实，不判对错。**"""
    records = _records(feature_root)
    openest = _latest(records, None, ACTIVE)
    closed = _latest(records, "closed")
    out = {"rounds": len(records), "phases": _phase_facts(feature_root),
           "stage": ((load(feature_root) or {}).get("update") or {}).get("stage"),
           "paths": _paths(project_root, feature_root)}
    if openest:
        rid, rec = openest
        notes = _updates_dir(feature_root) / rid / "update-notes.md"
        out.update(open=rid, opened_at=rec.get("opened_at"), requested_result=rec.get("requested_result"),
                   restore_conflicts=rec.get("restore_conflicts") or [],
                   notes=f"AR/story-src/updates/{rid}/update-notes.md" if notes.is_file() else None,
                   action=(f"更新 {rid} 还开着。"
                           + (f"上次恢复留下 {len(rec['restore_conflicts'])} 份冲突，处理完再恢复或收口。"
                              if rec.get("status") == "restore_conflicted" else "")
                           + ("说明在 update-notes.md，接着做完或 restore 还原现场。"
                              if notes.is_file()
                              else "还没有 update-notes.md——close 要绑定它，先把本轮判断写下来。")))
        return out
    out.update(open=None,
               last_closed=closed[0] if closed else None,
               action=("没有开着的更新。" + ("上一次已收口，可以起新的一轮。" if closed
                                             else "这个单还没有做过 update。")))
    return out


#: 本轮设计评审反馈的落点（blueprint-review-feedback@1），相对本轮目录。
FEEDBACK = "design-feedback.json"


def _feedback_states(rec: dict, native_out: dict) -> list[dict]:
    """每条反馈现在的处理状态：蓝图里有决定指向它才算处理过，否则待处理——不自报接受。"""
    handled = native_out.get("handled") or {}
    return [{**item, "state": "已处理" if item["feedback_id"] in handled else "待处理",
             **({"handled_by": handled[item["feedback_id"]]} if item["feedback_id"] in handled else {})}
            for item in rec.get("items", [])]


def cmd_update_feedback(feature_root: Path, project_root: Path) -> dict:
    """把本轮评审人对设计议题的意见交给蓝图负责方：核本轮的 `design-feedback.json`，记进本轮记录。

    每条反馈挂在一条设计议题上（`feedback_id` 是议题编号，同一议题多条写 `D3.1`、`D3.2`），`target_ref` 与议题登记的
    `design_target.target_ref` 相同，这条议题在本轮有人的原话（`decide --update --issue`）。被评的版本是成文登记记下的蓝图
    版本。原生只判每条够不够格进入调和；接受与否由蓝图负责方在 component-design 里处理，这里只报「已处理 / 待处理」。
    没有设计目标的业务意见不进这份文件，留在需求侧照议题处理。
    """
    records = _records(feature_root)
    active = _latest(records, None, ACTIVE)
    if not active:
        raise FlowError("没有开着的更新：设计反馈挂在本轮上，先起一轮 update")
    rid, rec = active
    root = _updates_dir(feature_root) / rid
    path = root / FEEDBACK
    if not path.is_file():
        raise FlowError(f"本轮还没有 {FEEDBACK}：把评审人对设计议题的意见写成 blueprint-review-feedback@1，"
                        f"落点 AR/story-src/updates/{rid}/{FEEDBACK}，写法见 phases/update.md「设计反馈」")
    try:
        doc = json.loads(path.read_text(encoding="utf-8").lstrip("\ufeff"))
    except ValueError as exc:
        raise FlowError(f"{FEEDBACK} 不是合法 JSON（{exc}）") from exc
    contract = load(feature_root) or {}
    blueprint = (contract.get("design_binding") or {}).get("blueprint_id")
    reviewed = ((contract.get("story_basis") or {}).get("blueprint_ref") or {}).get("revision")
    if not blueprint or reviewed is None:
        raise FlowError("这张单还没有按蓝图成文登记过：评审人评的是登记的那一版，没有登记就没有被评的蓝图版本")
    try:
        topics = {str(d.get("id")): d for d in json.loads(
            (feature_root / "AR" / "story-src" / "decisions.json").read_text(encoding="utf-8-sig")).get("decisions", [])}
    except (OSError, ValueError, AttributeError) as exc:
        raise FlowError(f"AR/story-src/decisions.json 读不出议题（{exc}）：反馈按议题认") from exc
    said = {d.get("issue") for d in (contract.get("update") or {}).get("decisions", [])}

    problems, items = [], []
    if doc.get("blueprint_id") != blueprint:
        problems.append(f"blueprint_id 应是本单关联的蓝图 {blueprint}")
    if doc.get("source_revision") != reviewed:
        problems.append(f"source_revision 应是成文登记时评审的蓝图版本 {reviewed}（写的是 {doc.get('source_revision')}）")
    for item in doc.get("items") or []:
        fid = str(item.get("feedback_id", ""))
        issue = fid.split(".")[0]
        target = ((topics.get(issue) or {}).get("design_target") or {}).get("target_ref")
        if not target:
            problems.append(f"{fid}：议题 {issue} 没有登记 design_target——没有设计目标的业务意见留在需求侧，不进设计反馈")
        elif item.get("target_ref") != target:
            problems.append(f"{fid}：target_ref 应是议题 {issue} 登记的 {target}")
        if issue not in said:
            problems.append(f"{fid}：议题 {issue} 在本轮没有记下人的原话——先 `decide --update ... --issue {issue} --reply \"<原话>\"`")
        items.append({"feedback_id": fid, "issue": issue, "kind": item.get("kind"), "target_ref": item.get("target_ref")})
    from flow import native  # noqa: PLC0415 —— 只有这一步要读原生蓝图
    out = native.call(project_root, "feedback", "--blueprint", blueprint, stdin=doc)
    rec["design_feedback"] = {"path": f"AR/story-src/updates/{rid}/{FEEDBACK}", "blueprint_id": blueprint,
                              "source_revision": reviewed, "items": items, "problems": problems,
                              "native_issues": out.get("issues", []), "candidates": out.get("candidates")}
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    states = _feedback_states(rec["design_feedback"], out)
    ok = not problems and out.get("status") == "ok"
    return {"update": rid, "feedback": states, "problems": problems, "native_issues": out.get("issues", []),
            "candidates": out.get("candidates"), "current_revision": out.get("revision"),
            "action": ("反馈合格，交蓝图负责方在 component-design 里调和；接受与否由它定，处理之前每条都是「待处理」，不写成已接受。"
                       if ok else "反馈有问题，改好本轮的 design-feedback.json 再跑：" + "；".join(
                           problems + [f"{i.get('code') or i.get('id')} {i.get('message', '')}" for i in out.get("issues", [])][:8]))}

def record_owned_after(feature_root: Path) -> str | None:
    """这一轮的完成点（story 登记、收口）：记下本扩展拥有的文件此刻的指纹，恢复据它认「本轮留下的就是这一版」。

    没有开着的一轮返回 None。前后两边都列全：开轮时有、现在没有的记 null。
    """
    records = _records(feature_root)
    active = _latest(records, None, ACTIVE)
    if not active:
        return None
    rid, rec = active
    now_owned = _owned(feature_root)
    rec["owned_after"] = {rel: now_owned.get(rel) for rel in sorted({*(rec.get("owned_before") or {}), *now_owned})}
    (_updates_dir(feature_root) / rid / "record.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rid


def cmd_update_close(feature_root: Path) -> dict:
    """收口这一轮：**绑定说明、记下此刻的文件摘要、留一份可比的正文**。

    共同条件：说明与不变项表在、人的原话归进本轮记录、没有未处理的恢复冲突。
    materials 终点另要已有人读件没被这一轮改过；documents 终点另要 story 按当前内容与当前设计登记过——
    登记本身核过结构与可消费的独立审查。**Framework 施工进展只读报告**，不挡收口。
    """
    records = _records(feature_root)
    openest = _latest(records, None, ACTIVE)
    if not openest:
        raise FlowError("没有开着的更新可以收口：先跑 `story_flow.py update` 起一轮")
    rid, rec = openest
    root = _updates_dir(feature_root) / rid
    if rec.get("status") == "restore_conflicted":
        raise FlowError(f"{rid} 的恢复还留着 {len(rec.get('restore_conflicts') or [])} 份冲突，不收口："
                        "逐份定好要哪一版（当前、开轮之前或本轮登记的那一版）后再跑 restore，没有冲突了再收口")
    notes = root / "update-notes.md"
    if not notes.is_file() or not notes.read_text(encoding="utf-8").strip():
        raise FlowError(
            f"{rid} 还没有写 update-notes.md（或它是空的），不收口。"
            "五段：当前依据、变化与影响、决定与修订、不变项与理由（一张表）、核对与剩余——"
            f"落点 AR/story-src/updates/{rid}/update-notes.md")
    text = notes.read_text(encoding="utf-8")
    if not unchanged_rows(text):
        raise FlowError(
            f"{rid} 的 update-notes.md 缺「不变项与理由」表，不收口：列出这次变化牵到却不用改的"
            "重要内容，每行写不变项与为什么不用改——防的是优化一处、损坏另一处")

    contract = load(feature_root) or {}
    result = rec.get("requested_result")
    before = rec.get("owned_before") or {}
    touched = [rel for rel in ("/".join(STORY), "/".join(REVIEW))
               if file_sha256(feature_root / rel) != before.get(rel)]
    if result == "materials" and touched:
        raise FlowError(f"这一轮登记的请求是 materials，却改了已有人读件 {'、'.join(touched)}，不收口："
                        "已有 Story 受影响的是 documents——`update --action prepare --result documents` 改记终点，按 documents 收口")
    if result == "documents" and (feature_root / Path(*STORY)).is_file():
        registered_before = (load(root / "before") or {}).get("status") == "story_written"
        if contract.get("status") != "story_written":
            if registered_before or touched:
                raise FlowError("story 这一轮改过或登记作废了，还没按当前内容重新登记，不收口："
                                "先 `story-build review --action prepare` 定稿（重投附录、编号、渲染 review、全篇 check）并重新独立审查，"
                                "审查通过后跑 `story_flow.py story` 重新登记")
        else:
            drift = registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
            if drift:
                raise FlowError(f"story 与当前依据不同步（needs_sync：{'、'.join(drift)}），不收口："
                                "新设计已接受而稿未同步的，按当前蓝图改稿，`story-build review --action prepare` 定稿并重新独立审查，"
                                "审查通过后跑 `story_flow.py story` 重新登记")

    record_owned_after(feature_root)
    rec = dict(_records(feature_root))[rid]
    feedback = None
    if rec.get("design_feedback"):
        from flow import native  # noqa: PLC0415 —— 有设计反馈才读原生蓝图看处理结果
        doc = json.loads((feature_root / rec["design_feedback"]["path"]).read_text(encoding="utf-8").lstrip("\ufeff"))
        feedback = _feedback_states(rec["design_feedback"],
                                    native.call(native.project_root_of(feature_root), "feedback",
                                                "--blueprint", rec["design_feedback"]["blueprint_id"], stdin=doc))
    current, unreadable = _scan(feature_root)
    # `after/` 是**给下一轮比的正文**，不是交付目录的副本：只留这一轮盯着的那几份。
    kept = _keep(feature_root, current, root / "after")
    phases = _phase_facts(feature_root)
    # 人在这一轮的原话随轮次留档：契约只清「开着的那一轮」（还原同样如此）
    rec.update(status="closed", closed_at=now(), files=current, unreadable=unreadable,
               sources=_sources(feature_root),
               notes=f"AR/story-src/updates/{rid}/update-notes.md",
               after={"path": f"AR/story-src/updates/{rid}/after", "files": kept},
               phases=phases, decisions=(contract.get("update") or {}).get("decisions", []))
    contract["update"] = {"open": None, "last_closed": rid}
    save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    log(f"update {rid} 收口：比较正文留了 {kept} 份")
    return {"update": rid, "status": "closed", "requested_result": result, "compared_next_time": kept,
            "unreadable": unreadable, "phases": phases, "design_feedback": feedback,
            "action": f"{rid} 已收口。下一轮以此刻的内容为基准；本轮的原貌仍在 before/。"
                      + ("本轮终点是取材与澄清：还没有设计或成文，按需求进展接着走。" if result == "materials" else "")
                      + (f"设计反馈 {sum(1 for x in feedback if x['state'] == '待处理')} 条待蓝图负责方处理。"
                         if feedback and any(x['state'] == '待处理' for x in feedback) else "")
                      + ("有读不到的文件，它们这一轮没能记进基准，下一轮仍会被单列。"
                         if unreadable else "")}


#: 「不变项与理由」那一节：标题里有「不变项」，下面至少一行表格数据。
UNCHANGED_HEAD = re.compile(r"^#{2,4}\s+.*不变项")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def unchanged_rows(text: str) -> int:
    """update-notes 里「不变项与理由」表的数据行数。"""
    lines = text.replace("\r\n", "\n").split("\n")
    at = next((i for i, line in enumerate(lines) if UNCHANGED_HEAD.match(line)), None)
    if at is None:
        return 0
    rows = []
    for line in lines[at + 1:]:
        if line.startswith("#"):
            break
        if TABLE_ROW.match(line) and not TABLE_RULE.match(line):
            rows.append(line)
    return max(len(rows) - 1, 0)          # 第一行是表头


def _keep(feature_root: Path, current: dict[str, str], after: Path) -> int:
    """把这一轮盯着的那几份正文留到 `after/`，给下一轮比。"""
    kept = 0
    for key in current:
        src = feature_root / key
        if src.is_file():
            (after / key).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, after / key)
            kept += 1
    return kept


def record_baseline(feature_root: Path) -> str | None:
    """成文登记时留第一份比较基准：之后第一次 update 也比得出「原来怎么写」。

    还没有任何 update 记录时写；重新登记时，旧的成文基准换成这一份。
    已经 update 过的，基准是上一轮收口留下的那一份。
    """
    records = _records(feature_root)
    if any(r.get("kind") != "story_baseline" for _, r in records):
        return None
    for rid, _ in records:
        shutil.rmtree(_updates_dir(feature_root) / rid)
    rid = now().replace("-", "").replace(":", "").replace("T", "-")[:15] + "-story"
    root = _updates_dir(feature_root) / rid
    current, unreadable = _scan(feature_root)
    kept = _keep(feature_root, current, root / "after")
    record = {"id": rid, "kind": "story_baseline", "status": "closed", "closed_at": now(),
              "files": current, "unreadable": unreadable, "sources": _sources(feature_root),
              "after": {"path": f"AR/story-src/updates/{rid}/after", "files": kept}}
    (root / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    return rid


def cmd_update_restore(feature_root: Path) -> dict:
    """把本扩展在这一轮改过的文件退回开轮之前。**先保住现在，再按指纹一份份判。**

    只动可改件与可重生件：受保护件与流程契约的其余字段一个字节不动。逐份按开轮时（before）、
    本轮完成点（after）与现在（current）的指纹判：

    - current 等于 before：本来就是开轮时的样子，不动；
    - 本轮完成点登记过它、current 仍是那一版：退回 before（开轮时没有的删掉）；
    - 其余（后来又改过、本轮没到完成点）：保留 current，列成冲突并给出可比的版本。

    有冲突时轮次照旧开着（`restore_conflicted`），人定好之后再跑一次，只处理满足条件的那几份。
    """
    records = _records(feature_root)
    target = _latest(records, None, ACTIVE)
    if not target:
        raise FlowError("没有开着的更新可以还原：还原撤回的是正在进行的这一轮；已收口的轮次起新一轮 update 来改")
    rid, rec = target
    root = _updates_dir(feature_root) / rid
    before_dir = root / "before"
    if not before_dir.is_dir():
        raise FlowError(f"{rid} 没有留下 before/，还原不了。"
                        "它应当在起手时建好；目录被移走的话，这一轮只能按当前内容继续")
    before = rec.get("owned_before") or {}
    after = rec.get("owned_after")
    current = _owned(feature_root)
    keys = sorted({*before, *current, *(after or {})})

    # 先把现在与开轮时不同的那几份、连同评审记录（人工区在里面）原样存进本轮的受保护历史；存不下就不往下走
    saved = root / f"restore-{now().replace('-', '').replace(':', '').replace('T', '-')[:15]}"
    for rel in [*(k for k in keys if current.get(k) is not None and current.get(k) != before.get(k)), "/".join(REVIEW)]:
        src = feature_root / rel
        if src.is_file():
            (saved / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, saved / rel)

    conflicts, restored, removed = [], [], []
    for rel in keys:
        was, now_sha = before.get(rel), current.get(rel)
        if now_sha == was:
            continue
        if after is not None and rel in after and now_sha == after[rel]:
            if was is None:
                (feature_root / rel).unlink()
                removed.append(rel)
                continue
            src = before_dir / rel
            if src.is_file() and file_sha256(src) == was:
                shutil.copyfile(src, feature_root / rel)
                restored.append(rel)
                continue
        conflicts.append({"file": rel, "before": f"AR/story-src/updates/{rid}/before/{rel}" if was else None,
                          "current": f"AR/story-src/updates/{rid}/{saved.name}/{rel}" if now_sha else None,
                          "why": ("本轮没到完成点，改动没有登记的那一版可比" if after is None or rel not in after
                                  else "本轮完成点之后又改过")})

    contract = load(feature_root) or {}
    rec["decisions"] = (contract.get("update") or {}).get("decisions", [])
    rec.update(status="restore_conflicted" if conflicts else "restored", restored_at=now(),
               restore_conflicts=conflicts, restore_copy=f"AR/story-src/updates/{rid}/{saved.name}")
    if not conflicts:
        contract["update"] = {"open": None, "last_restored": rid}
        save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    drift = (registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
             if contract.get("status") == "story_written" else [])
    log(f"update {rid} 还原：退回 {len(restored)} 份、删掉 {len(removed)} 份、冲突 {len(conflicts)} 份")
    return {"update": rid, "status": rec["status"], "restored": restored, "removed": removed,
            "conflicts": conflicts, "restore_copy": rec["restore_copy"], "needs_sync": drift,
            "action": (f"有 {len(conflicts)} 份不满足退回条件，保留现状、这一轮照旧开着：逐份定好要哪一版后再跑 restore。"
                       if conflicts else f"本扩展在 {rid} 改过的文件已退回开轮之前，轮次关闭。")
                      + (f"成文登记与当前依据不一致（{'、'.join(drift)}）：登记保留原样，交付前按当前依据重新定稿登记。"
                         if drift else "")}
