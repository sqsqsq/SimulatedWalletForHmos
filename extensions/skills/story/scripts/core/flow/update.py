"""`/story update` 的文件侧支持 —— **脚本只回答确定的事**。

这一层做三件机械的事：把本次执行前的现场完整留一份、与上次已处理的版本比一遍、
把结果说清楚。取回来的新内容与人补的料一样进收件箱 `inbox/`，走 init 那条材料链——
这里不另开第二个入料口。**变化意味着什么、要改哪里，一概不判**——
那是模型读原文的事（方法在 `phases/update.md`）。

顺序是**先定输入，再检测**：`inputs` 报告上游与本地各有什么（不建任何东西），
模型据此在第一级关卡问人要不要补料；人答完、料登记进本轮，`prepare` 比一遍并开这一轮。
比较结果是交给模型的事实：一个字节没变也照常开轮，变化意味着什么、要不要改由模型读原文判；
没有业务变化时 update-notes 写明比过什么、为什么不用改，照常收口。
**没查到不等于没变**：比较基准缺席、来源读不到，都单列出来说清可查范围，不许混进「无变化」。

落点在 `AR/story-src/updates/<id>/`，它不在材料索引的范围里（材料只认收件箱原件、当前阅读稿、留存的版本与会议原件），
所以本层自己的写入不会把材料版本顶出一个新轮次。

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

from materials import importer, registry

import usage
from flow.phase_facts import UPDATES, moment, update_records as _records
from flow.routing import basis_drift, inputs_answer, material_state, next_step
from flow.state import (CONTRACT, FlowError, STORY, STORY_CONTRACT, blueprint_exists, file_sha256, system_requirement,
                        load, log, now, registration_drift, round_gates, save, sync_answers)

#: 本层全部落点的根（`UPDATES`）放在 story-src 下面：它是过程目录，AR 根只留交付件。
#: 除材料正文之外，判「跟上次比变了没有」要看的交付件——**人会直接动的那一份人读件**。
#:
#: 连同材料索引里各来源最新取得的版本（按来源身份比原件摘要）与收件箱（由材料事实回答，
#: 不按文件哈希比）。写作设计与知识判断不在里面：
#: 它们是模型据这几份写出来的中间真源，随交付件的修订而变，是结果不是原因。
#: 盘上没有的跳过，不当成被删（`_scan`）。
PRODUCTS = (STORY,)
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


def _reading_evidence(rel: str) -> bool:
    """同图增强的局部阅读证据（`AR/story-src/figures/<ID>.reading/`）：按当前源重新核，撤回不把旧的「已通过」带回来。"""
    parts = rel.split("/")
    return len(parts) > 4 and parts[:3] == ["AR", "story-src", "figures"] and parts[3].endswith(".reading")


def _owned(feature_root: Path) -> dict[str, str]:
    """盘上本扩展拥有的文件（可改件与可重生件，阅读证据除外）→ 原始字节的 SHA-256。"""
    sets = update_files()
    out = {}
    for path in sorted(feature_root.rglob("*")):
        rel = path.relative_to(feature_root).as_posix()
        if (path.is_file() and not path.is_symlink() and not _reading_evidence(rel)
                and owner(rel, sets) in ("editable", "regenerate")):
            out[rel] = file_sha256(path)
    return out


def _updates_dir(feature_root: Path) -> Path:
    return feature_root / Path(*UPDATES)


#: 现收件箱里的评审用途区（不是第七种需求分类）：系统取材回来的交付回流件与本地评审意见、改稿都落在这里，
#: 由 update 取得并送给本轮修改与独审；材料导入跳过这一子树，不把它报成待归类。
REVIEW_INBOX = ("inbox", "review")


def review_inbox(feature_root: Path) -> Path:
    return feature_root.joinpath(*REVIEW_INBOX)


def _review_inputs(feature_root: Path) -> list[dict]:
    """评审用途区里的原件：系统取材批次的每件与批次回执对上身份、来源与摘要，本地放进去的意见/改稿按原件列。

    回执记读取失败、原件读不出、批次里有文件而回执里没有它，都**照实单列**，不当成没放；
    本地评审文档没有系统身份，`system_item` 为空。返回的是给人看的机械事实，意见意味着什么由模型读原件判。
    """
    base = review_inbox(feature_root)
    if not base.is_dir():
        return []
    out: list[dict] = []
    in_batches = set()
    for batch in sorted(p for p in base.iterdir() if p.is_dir()):
        receipt_path = batch / ".receipt.json"
        receipt = None
        if receipt_path.is_file():
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            except ValueError as exc:
                raise FlowError(f"{receipt_path.relative_to(feature_root).as_posix()} 读不出来（{exc}）："
                                "系统批次回执是这批原件的身份与来源，读不出就说不出它们是什么") from exc
        by_saved = {str(i.get("saved")): i for i in (receipt or {}).get("items") or [] if i.get("saved")}
        for path in sorted(p for p in batch.rglob("*") if p.is_file() and p.name != ".receipt.json"):
            rel = path.relative_to(feature_root).as_posix()
            item = by_saved.get(rel)
            entry = {"path": rel, "sha256": file_sha256(path), "origin": None, "system_item": None,
                     "status": "fetched" if item else "local", "digest": item.get("digest") if item else None}
            if item:
                entry.update(origin=item.get("origin"), system_item=item.get("name"), status=item.get("status") or "fetched")
            elif receipt is not None:
                entry.update(status="unreadable", note="批次回执里没有这一件，读不出它是哪一份")
            if entry["sha256"] is None:
                entry.update(status="unreadable", note="原件读不出来")
            out.append(entry)
            in_batches.add(path)
        for item in (receipt or {}).get("items") or []:
            if item.get("status") == "failed" and not item.get("saved"):
                out.append({"path": None, "sha256": None, "origin": item.get("origin"),
                            "system_item": item.get("name"), "status": "failed", "digest": None,
                            "note": item.get("note")})
    for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name != ".receipt.json" and p not in in_batches):
        out.append({"path": path.relative_to(feature_root).as_posix(), "sha256": file_sha256(path),
                    "origin": None, "system_item": None, "status": "local", "digest": None})
    return out


def _review_identity(entry: dict) -> tuple:
    """一条评审输入的身份：系统件按系统项与取回摘要，本地件按原路径与摘要——路径不会让同一份系统正文每次都算新的。"""
    if entry.get("system_item"):
        return ("system", entry.get("system_item"), entry.get("digest") or entry.get("sha256"))
    return ("local", entry.get("path"), entry.get("sha256"))


def _review_new_since(records: list[tuple[str, dict]], review_inputs: list[dict]) -> list[dict]:
    """上次收口以来新出现或变过的评审输入；还没有收口过的轮次列全部（这一轮都要读）。"""
    seen: set[tuple] = set()
    for _, rec in reversed(records):
        if rec.get("status") == "closed" and rec.get("review_inputs") is not None:
            seen = {_review_identity(e) for e in rec["review_inputs"]}
            break
    return [e for e in review_inputs if _review_identity(e) not in seen]


def _snapshot_review_inputs(feature_root: Path, entries: list[dict], dest: Path) -> int:
    """把这一轮的评审输入原件与它的批次回执复制进本轮 before/：恢复不撤人的原件，收口后仍能回看当时收到的是哪一份。"""
    paths = {str(e["path"]) for e in entries if e.get("path")}
    for entry in entries:
        if not entry.get("path"):
            continue
        batch = (feature_root / Path(*str(entry["path"]).split("/"))).parent
        receipt = batch / ".receipt.json"
        if receipt.is_file():
            paths.add(receipt.relative_to(feature_root).as_posix())
    copied = 0
    for rel in sorted(paths):
        src = feature_root / Path(*rel.split("/"))
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / rel)
            copied += 1
    return copied


def _scan(feature_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """当前这一轮要盯的东西 → 指纹。**读不到的单列，不当成不存在。**

    上游材料按来源身份比：键是 `source:<来源>`，值是它最新取得版本的原件摘要——同一来源取得了新版本就是变了，
    新来源是新增，旧来源都在索引里留着不算删除。当前阅读稿与直接原文（`current:<路径>`）、交付件按路径比文件摘要。
    「文件不在」与「文件在但读不出来」是两件事：读不到的那几份**带着 key 单独返回**，`_compare` 把它们从「删除」里摘出去。
    """
    seen: dict[str, str] = {}
    unreadable: dict[str, str] = {}
    try:
        manifest = registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(f"{exc}——材料索引算不出来就说不出上游变没变") from exc
    for v in registry.current(manifest["sources"]):
        if v["kind"] != "answer":
            seen[f"source:{v['source_id']}"] = v["original"]["sha256"]
    # 当前阅读稿与直接原文按盘上字节比：人直接改了它也是变化，不因登记还没跟上就算没变
    for rel in sorted({*manifest.get("drafts", {}), *importer.DIRECT}):
        if (feature_root / rel).is_file():
            seen[f"current:{rel}"] = registry.file_digest(feature_root / rel) or ""
    for rel in (Path(*p) for p in PRODUCTS):
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
    review_inputs = _review_inputs(feature_root)
    # 没登记过材料基准不算「变了」：那是轮次自己缺指纹，由流程契约的判据报
    registered = bool((last.get("materials") or {}).get("digest"))
    return {"current": current, "unreadable": unreadable, "diff": diff,
            "changed": diff["added"] + diff["modified"] + diff["removed"],
            "superseded_hint": _superseded_hint(feature_root, state["pending"]),
            "pending": state["pending"], "materials_changed": registered and state["changed"],
            "imported": _imported_since(feature_root, records),
            "review_inputs": review_inputs, "review_new": _review_new_since(records, review_inputs)}


def _sources(feature_root: Path) -> list[dict]:
    """已导入的来源版本（来源、版本号、原件摘要、类、目录），取自材料索引；收口时记下，下次据它找新导入的。

    读不出索引就报，不当成「没有新料」：那会让人以为上次以来什么都没导入。
    """
    try:
        manifest = registry.read(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(f"{exc}——读不出材料索引就说不出上次以来导入了哪些版本") from exc
    return [{"source_id": s["source_id"], "version": v["version"], "sha256": v["original"]["sha256"],
             "class": s.get("class"), "dir": v.get("dir")}
            for s in manifest.get("sources") or [] if s.get("kind") != "answer" for v in s.get("versions") or []]


def _imported_since(feature_root: Path, records: list[tuple[str, dict]]) -> list[dict]:
    """上一次收口以来新导入的来源版本，**含只取图的**：是不是带来了业务变化由模型读原件判。
    还没有收口过的轮次就没有版本清单可比，不列——比较本身已报「没有上次已处理的版本」，由模型通读现有来源。"""
    closed = _latest(records, "closed")
    if not closed:
        return []
    seen = {(s.get("source_id"), s.get("version")) for s in (closed[1].get("sources") or [])}
    return [s for s in _sources(feature_root) if (s["source_id"], s["version"]) not in seen]


def _superseded_hint(feature_root: Path, pending: list[str]) -> list[dict]:
    """收件箱里的新件可能取代的已有来源：同类的来源。**只列，不判**——是不是新版由你读了定。

    放在同一位置的改版导入后自动成为同一来源的新版本；换了位置或名字的件是新来源，旧来源留在索引里可查，
    设计依据哪一版由设计采用决定，不靠移走旧原件。新件还没归类时列出全部已有来源。
    """
    try:
        manifest = registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(f"{exc}：修正后再跑") from exc
    classes = {i["path"]: i.get("class") for i in manifest.get("inbox", [])}
    known = [(s["source_id"], s.get("class")) for s in manifest.get("sources", []) if s.get("kind") != "answer"]
    out = []
    for new in pending:
        cls = classes.get(new)
        olds = sorted(sid for sid, c in known if cls is None or c == cls)
        if olds:
            out.append({"new": new, "same_class": olds,
                        "note": f"若 {new} 是其中某个来源的新版，读了在影响分析里写明；设计改依据哪一版由设计修订决定"})
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
            "review_inputs": _review_states(facts["review_inputs"]), "review_new": _review_states(facts["review_new"]),
            "upstream": _receipt(feature_root) if system else None,
            "action": ("`upstream` 是最近一次取材的回执，展示它的时刻；本次取材成功与否以那次取材自己的结果为准。"
                       if system else "本地需求没有上游；")
                      + "`review_inputs` 是评审用途区已取得/失败/未读的件，逐件读原件、在 notes 记去向。"
                      "按 `rules/init_analysis.md` S2a 盘点手上的料，缺口写进 `.material-gaps.json`，"
                      "跑 `status` 取问法，问人这一次要不要补料，**停等**。人答了 → `decide` 记原话 → "
                      "收件箱有新原件先导入 → `round` 登记到本轮 → `update --action prepare --result <materials|documents>`"}


def _set_result(root: Path, rec: dict, result: str) -> None:
    """续做中的一轮换终点：取材可以升成要同步人读件，反过来不行——已有人读件受影响就是 documents。"""
    was = rec.get("requested_result")
    if result == was:
        return
    if was == "documents":
        raise FlowError("这一轮登记的请求是 documents（要同步人读件），只能从 materials 改为 documents：终点由人的请求与受影响的已有结果定")
    rec["requested_result"] = result
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _carry_start(feature_root: Path, feature: str, rid: str, rec: dict) -> str | None:
    """把 begin 暂存的开始时刻移进这一轮 record：record 已有就只清暂存；没有就读暂存、写进 record 存盘成功后再清。
    读不出或写不进都保留暂存、返回原因——下一次 prepare 或收口照原值再移，不换成重试那一刻；业务照常继续。"""
    try:
        if not rec.get("started_at"):
            started = usage.update_start(feature_root, feature)
            if not started:
                return None                 # 本来就没有 begin：这一轮的计时缺口，不拿开轮时刻补
            (_updates_dir(feature_root) / rid / "record.json").write_text(
                json.dumps({**rec, "started_at": started}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rec["started_at"] = started
        usage.drop_update_start(feature_root, feature)
    except (usage.UsageError, FlowError, OSError) as exc:
        return f"这一轮 update 的开始时刻还没移进记录（{exc}）：暂存保留着，下一次 prepare 或收口时照原值再移"
    return None


def cmd_update_prepare(feature_root: Path, feature: str, result: str | None) -> dict:
    """输入定了之后比一遍、开这一轮、该留的留下、该说的说清楚。

    `result` 是这一轮请求的终点，照人的请求记：只取材与澄清、没有已有人读件受影响的是 materials，
    其余是 documents。

    `comparison` 直说比出来的是哪一种：

    - `resume`   上一轮还开着。**不新建镜像**——新的会把旧的恢复依据盖掉；
    - `unchanged` 上游来源与交付件都没变、也没有新导入的版本：照常开轮，要不要改由模型按原文与人的这次要求判；
    - `incomplete` 比较基准缺席或来源读不到：说清可查与不可查的范围，交模型判当前一致性；
    - `changed`  有变化：本轮镜像留着不动，差异与位置交给模型。

    **返回的全是机械事实**：哪些来源与文件跟上次不一样、新导入了哪些版本、镜像在哪。
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
        gap = _carry_start(feature_root, feature, rid, rec)
        return {**resumed, "requested_result": rec.get("requested_result"), **({"usage_error": gap} if gap else {})}

    facts = _collect(feature_root, contract, records)
    if facts["pending"]:
        raise FlowError("来源收件箱里还有没导入的件，先导入、`round` 登记到本轮，再 prepare："
                        + "、".join(facts["pending"]))
    current, unreadable, diff, changed = (facts["current"], facts["unreadable"],
                                          facts["diff"], facts["changed"])
    pending, imported = facts["pending"], facts["imported"]
    review_inputs, review_new = facts["review_inputs"], facts["review_new"]

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
    snapshotted = _snapshot_review_inputs(feature_root, review_inputs, before)

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
              "files": current, "unreadable": unreadable, "comparison": diff, "sources": _sources(feature_root),
              "review_inputs": review_inputs,
              "materials": {"pending": pending, "changed": facts["materials_changed"],
                            "imported": imported},
              "mirror": {"path": f"AR/story-src/updates/{rid}/before", "files": mirrored,
                         "review_inputs": snapshotted}}
    (root / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    # 这一轮的工作起点由 update 开头的 begin 暂存，开轮时移进 record（opened_at 仍是开轮这一刻）
    gap = _carry_start(feature_root, feature, rid, record)

    material = bool(pending or facts["materials_changed"] or imported)
    kind = ("changed" if (changed or material or review_new)
            else "incomplete" if (not diff["complete"] or unreadable) else "unchanged")
    lines = []
    if changed:
        lines.append("变了的：" + "、".join(changed))
    if facts["materials_changed"]:
        lines.append("材料指纹与本轮登记的对不上：先 `round` 登记到本轮")
    if review_inputs:
        lines.append("评审用途区的原件（已取得/失败/未读）：" + "、".join(
            f"{e.get('path') or e.get('system_item')}（{_review_states([e])[0]['state']}）" for e in review_inputs)
            + "——逐件读原件，在 update-notes 记「输入原件位置→处理/理由→Story 位置或原生目标」")
    if review_new:
        lines.append("本次新到或变过的评审输入 " + str(len(review_new)) + " 件：先按人的这一版为编辑底稿逐处合入，"
                     "不采纳的原话留在 before/")
    if not diff["complete"]:
        lines.append("没有上次已处理的版本可比：这一轮说不出「原来怎么写」，"
                     "按当前材料与产物核一致性，别补造历史")
    if unreadable:
        lines.append("读不到：" + "、".join(f"{k}（{why}）" for k, why in unreadable.items())
                     + "——这是缺口，不是「没有变化」，更不是「它被删了」")
    if imported:
        lines.append("上次以来新导入的来源版本：" + "、".join(f"{s['dir']}（{s['class']}）" for s in imported)
                     + "——读原件判它带没带来业务变化；只取图的原件正文不作依据")
    if kind == "unchanged":
        lines.append("与上次已处理的版本逐份比过没有变化：按原文与人这次的要求判要不要改，"
                     "没有业务变化时 update-notes 写明比过什么、为什么不用改，照常收口")
    log(f"update {rid}：镜像 {mirrored} 份、评审输入 {snapshotted} 份、差异 {diffs} 份")
    return {"comparison": kind, "update": rid, "requested_result": result, "changed": changed, "pending": pending,
            "imported": imported, "superseded_hint": facts["superseded_hint"],
            "review_inputs": _review_states(review_inputs),
            "unreadable": unreadable, "baseline": diff["complete"], "diffs": diffs,
            "mirror": record["mirror"]["path"],
            "action": "；".join(lines) + f"。原貌留在 AR/story-src/updates/{rid}/before/，"
                      "处置方法见 phases/update.md", **({"usage_error": gap} if gap else {})}


# ---------------------------------------------------------------------------
# 施工事实：需求关联的蓝图有哪些施工单位，各阶段有没有产物、闭没闭环。**只读报告**：施工归 Framework，
# update 不推进、不因它挡收口。
#
# 施工单位由原生读蓝图时列出（身份、原生目录与各阶段报告目录，同一次调用）；阶段读 harness 自己写在报告目录里的
# `summary.json`——它是只读投影，不是我们的账。读不出来就说读不出来：闭没闭环这件事不许猜，猜错的方向是「以为闭了」。
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")


def _unit_facts(feature_root: Path, project_root: Path | None = None) -> list[dict]:
    """需求还没有蓝图时为空列表；蓝图读不过时报原生问题。蓝图与需求同根，标识就是需求标识。"""
    if not blueprint_exists(feature_root):
        return []
    blueprint = feature_root.name
    from flow import native  # noqa: PLC0415 —— 施工单位由原生读蓝图时列出
    project_root = project_root or native.project_root_of(feature_root)
    read = native.call(project_root, "blueprint", "--blueprint", str(blueprint), "--purpose", "draft", "--summary",
                       "--report-phases", ",".join(PHASES))
    if read.get("status") != "ok":
        return [{"blueprint_id": blueprint, "readable": False, "why": native.issues_text(read) or read.get("status")}]
    out = []
    for u in read.get("units") or []:
        phases = _phase_facts(u.get("phase_reports") or [], _evidence(project_root, u["feature_id"]))
        disposition = _disposition(project_root, u["feature_id"], [x["phase"] for x in phases if x.get("readable")])
        out.append({"change_unit_id": u["change_unit_id"], "feature_id": u["feature_id"], "path": u["path"],
                    "phases": _current(phases, disposition), "disposition": disposition})
    return out


def _disposition(project_root: Path, feature_id: str, chain: list[str]) -> dict:
    """施工单位已有阶段此刻的原生当前处置：阻断完成、阻断发布与可披露各列一份，普通完成与发布资格照原生给。
    还没有阶段时为空集合；读不出记 unknown，不当作可以完成。"""
    if not chain:
        return {"status": "ok", "completion_eligible": None, "release_ready": None,
                "completion_blocking": [], "release_blocking": [], "disclosed": []}
    from flow import native  # noqa: PLC0415
    got = native.call(project_root, "disposition", "--feature", feature_id, "--phases", ",".join(chain))
    if got.get("status") != "ok":
        return {"status": "unknown", "why": native.issues_text(got) or got.get("status")}
    keep = ("status", "completion_eligible", "release_ready", "completion_blocking", "release_blocking", "disclosed")
    return {k: got.get(k) for k in keep}


def _current(phases: list[dict], disposition: dict) -> list[dict]:
    """每阶段这一刻算不算完成：历史闭环、证据新鲜、且原生当前处置里没有落在它身上的完成阻断。
    历史 closure 原样保留；处置读不出时一律不算当前。"""
    out = []
    for x in phases:
        if not x.get("readable"):
            out.append(x)
            continue
        blocking = [{"id": b["id"], "action": b["action"], "detail": b["detail"]}
                    for b in disposition.get("completion_blocking") or [] if x["phase"] in (b.get("phase"), b.get("owner"))]
        known = disposition.get("status") == "ok"
        out.append({**x, "blocking": blocking,
                    "current": x["current"] and known and not blocking})
    return out


def _evidence(project_root: Path, feature_id: str) -> dict[str, str]:
    """施工单位各阶段的原生证据此刻是否仍有效（按阶段顺序重算，上游不新鲜传染下游）；读不出整体记为 unknown。"""
    from flow import native  # noqa: PLC0415
    got = native.call(project_root, "phase-evidence", "--feature", feature_id, "--phases", ",".join(PHASES))
    if got.get("status") != "ok":
        return {p: "unknown" for p in PHASES}
    return {r.get("phase"): str(r.get("verdict")) for r in got.get("results") or []}


def _phase_facts(reports: list[dict], evidence: dict[str, str]) -> list[dict]:
    """每阶段按原生报告目录读 summary；目录解析不了是读不出，还没生成的阶段不列。
    `current` 先按闭环且原生证据此刻新鲜给出，再由 `_current` 并上原生当前处置：历史闭环保留，证据变了或当前还有必修、
    待核的不算这一轮的完成，交回里照实列出。"""
    out = []
    for r in reports:
        phase = r["phase"]
        if r.get("error"):
            out.append({"phase": phase, "readable": False, "why": f"报告目录解析不了：{r['error']}"})
            continue
        summary = Path(r["dir"]) / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8").lstrip("\ufeff"))
        except (OSError, ValueError) as exc:
            out.append({"phase": phase, "readable": False, "why": str(exc)})
            continue
        fresh = evidence.get(phase, "unknown")
        out.append({"phase": phase, "readable": True, "closure": data.get("closure_status"),
                    "verdict": data.get("verdict"), "subject": data.get("verifier_subject_id"), "evidence": fresh,
                    "current": data.get("closure_status") == "closed" and fresh == "fresh"})
    return out


def _phase_open(p: dict) -> bool:
    """阶段自身的问题：读不出、没闭环、原生证据此刻不新鲜，或原生当前完成阻断落在这个阶段上。"""
    return p.get("readable") is False or p.get("closure") != "closed" or p.get("evidence") != "fresh" or bool(p.get("blocking"))


def _disposed(items: list[dict] | None) -> list[dict]:
    return [{k: b.get(k) for k in ("id", "phase", "owner", "action", "detail")} for b in items or []]


def stale_units(units: list[dict]) -> list[dict]:
    """施工单位此刻要交代的事，阶段与单位分列。历史闭环保留在 units 里；蓝图读不出时施工影响未知，照实列出。

    - `phases`：有自身问题的阶段，`from` 是最早的那一个；
    - `unit`：原生当前处置里不落在已列阶段上的完成阻断（如 `phase='*'` 的单位级阻断）、只限制发布的阻断与可披露事项；
    - `disposition_unknown`：处置读不出的原因——此刻不能当作已完成，也不据此认定哪个阶段要重做。"""
    out = []
    for u in units:
        if u.get("readable") is False:
            out.append({"blueprint_id": u.get("blueprint_id"), "why": u.get("why"), "phases": []})
            continue
        phases = u.get("phases") or []
        old = [p for p in phases if _phase_open(p)]
        d = u.get("disposition") or {}
        listed = {p["phase"] for p in phases}
        unit = {"completion_blocking": _disposed([b for b in d.get("completion_blocking") or []
                                                  if not {b.get("phase"), b.get("owner")} & listed]),
                "release_blocking": _disposed(d.get("release_blocking")),
                "disclosed": _disposed(d.get("disclosed"))}
        unit = {k: v for k, v in unit.items() if v}
        unknown = d.get("why") if d.get("status") == "unknown" else None
        if not (old or unit or unknown):
            continue
        out.append({"change_unit_id": u["change_unit_id"], "feature_id": u["feature_id"],
                    **({"from": old[0]["phase"]} if old else {}),
                    "phases": [{"phase": p["phase"], "evidence": p.get("evidence"), "closure": p.get("closure"),
                                "blocking": p.get("blocking") or [],
                                **({"why": p["why"]} if p.get("readable") is False else {})} for p in old],
                    **({"unit": unit} if unit else {}),
                    **({"disposition_unknown": unknown} if unknown else {})})
    return out


def stale_text(stale: list[dict]) -> str:
    """受影响 CU 与接手动作：阶段问题、单位完成阻断、发布限制、披露事项、处置读不出各说各的去处，不称可以沿用旧 Plan。"""
    if not stale:
        return ""
    def todo(items: list[dict]) -> str:
        return "、".join(f"{b['id']}（{b['action']}{'，负责方 ' + b['owner'] if b.get('owner') else ''}）" for b in items)

    def phase(p: dict) -> str:
        extra = f"，当前要处理 {todo(p['blocking'])}" if p.get("blocking") else ""
        return f"{p['phase']}（证据 {p.get('evidence') or '读不出'}{extra}）"

    labels = (("completion_blocking", "单位完成受阻"), ("release_blocking", "只限制发布"), ("disclosed", "交付时要披露"))
    rows, kinds = [], set()
    for s in stale:
        if "change_unit_id" not in s:
            rows.append(f"蓝图 {s['blueprint_id']} 读不出（{s['why']}），施工单位受不受影响未知")
            kinds.add("phases")
            continue
        unit = s.get("unit") or {}
        parts = [f"阶段 {'、'.join(phase(p) for p in s['phases'])}"] if s["phases"] else []
        parts += [f"{label}：{todo(unit[key])}" for key, label in labels if unit.get(key)]
        if s.get("disposition_unknown"):
            parts.append(f"当前处置读不出（{s['disposition_unknown']}）")
        rows.append(f"{s['change_unit_id']}（{s['feature_id']}）：" + "；".join(parts))
        kinds.update(key for key, _ in labels if unit.get(key))
        if s["phases"]:
            kinds.add("phases")
        if s.get("disposition_unknown"):
            kinds.add("unknown")
    follow = {"phases": "有阶段问题的，本轮授权到 Plan 就从最早未完成的阶段重新取原生输入、落实变更并闭环到 Plan 才算同步，"
                        "没有施工授权的交施工负责人从这些阶段接手，不沿用旧 Plan",
              "completion_blocking": "单位完成阻断按原生给的负责方与动作处理，不重做没受影响的业务阶段",
              "release_blocking": "发布阻断只限制发布，普通完成照原生结论",
              "disclosed": "披露事项在交付时照实写明，不当作缺陷",
              "unknown": "处置读不出的单位此刻不能当作已完成，读取恢复后再判，不据此重做阶段"}
    return ("施工单位此刻还有要交代的事（历史闭环保留）：" + "；".join(rows) + "。"
            + "；".join(text for key, text in follow.items() if key in kinds) + "。")


def _paths(project_root: Path, feature_root: Path) -> dict:
    """本需求的本地位置（绝对路径）：人补料放进来源收件箱，系统取材落到收件箱下这一次的批次目录；
    人的评审意见与被改 Story 放现收件箱的评审用途区，由 update 取得（材料导入不读它）。"""
    inbox = importer.inbox_of(feature_root)
    return {"project_root": project_root.resolve().as_posix(),
            "feature_root": feature_root.resolve().as_posix(),
            "inbox": inbox.resolve().as_posix(),
            "review_inbox": review_inbox(feature_root).resolve().as_posix(),
            "fetch_batch": (inbox / f"fetch-{datetime.now().strftime('%Y%m%d-%H%M%S')}").resolve().as_posix()}


def _review_states(entries: list[dict]) -> list[dict]:
    """评审输入给人看的逐件事实：已取得 / 失败 / 未读，各带来源与去向。"""
    label = {"fetched": "已取得", "same": "已取得", "failed": "失败", "unreadable": "未读", "local": "未读"}
    return [{**e, "state": label.get(str(e.get("status")), "未读")} for e in entries]


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
    units = _unit_facts(feature_root, project_root)
    out = {"rounds": len(records), "units": units, "stale_units": stale_units(units),
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


#: 本轮设计评审反馈的落点（blueprint-review-feedback@1），相对本轮目录；还没有开着的更新时，
#: 首次问答的反馈落在本轮 init 的问法答复目录（`AR/story-src/answers/`），不要求先伪造一次 update。
FEEDBACK = "design-feedback.json"
ANSWERS_FEEDBACK = ("AR", "story-src", "answers", FEEDBACK)


def _feedback_observed(feature_root: Path, fb: dict) -> list[dict]:
    """每条反馈现在的观察：候选资格照提交时记下的，当前蓝图里来源精确指向它的决定照原生读。

    有相关决定不等于接受：负责方的实际回复记在本轮 update-notes，接受与否由模型读它与当前设计判；这里一律是「待确认」。
    """
    from flow import native  # noqa: PLC0415 —— 只有这一步读原生蓝图
    ids = [item["feedback_id"] for item in fb.get("items", [])]
    out = native.call(native.project_root_of(feature_root), "feedback-related", "--blueprint", fb["blueprint_id"],
                      "--ref", fb["ref"], stdin=ids)
    related = out.get("related") or {}
    return [{**item, "state": "待确认", "related_decisions": related.get(item["feedback_id"], [])} for item in fb.get("items", [])]


def _feedback_file(feature_root: Path, records: list[tuple[str, dict]]) -> tuple[str | None, dict | None, Path, str]:
    """这一轮的反馈文件：开着 update 时在本轮目录，首次问答时在 init 轮的答复目录。返回轮次、记录、绝对路径与展示路径。"""
    active = _latest(records, None, ACTIVE)
    if active:
        rid, rec = active
        return rid, rec, _updates_dir(feature_root) / rid / FEEDBACK, f"AR/story-src/updates/{rid}/{FEEDBACK}"
    return None, None, feature_root.joinpath(*ANSWERS_FEEDBACK), "/".join(ANSWERS_FEEDBACK)


def _evidence_ref_problem(project_root: Path, feature_root: Path, ref: object, fid: str) -> str | None:
    """事实补充的 evidence_refs 指回真实原件：需求目录或工程根内的相对路径要读得到，稳定地址由原生解析。"""
    text = str(ref or "").strip()
    if not text:
        return None
    raw = text.split("#", 1)[0]
    if raw.startswith(("blueprint:", "view:", "node:", "relation:", "flow:", "decision:", "contract:", "gap:", "evidence:")):
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return f"{fid} 的 evidence_refs「{text}」不是工程内的相对路径"
    if (feature_root / path).is_file() or (project_root / path).is_file():
        return None
    return (f"{fid} 的 evidence_refs「{text}」读不到：事实补充要指回真实原件——"
            "本轮评审用途区的原件，或设计问答记下的原话原件")


def cmd_update_feedback(feature_root: Path, project_root: Path) -> dict:
    """把评审人对设计的反馈交给蓝图负责方：核本轮反馈文件的候选资格，记下结果。

    输入是本轮 Story 批注/改稿/追加/转述或已记下的原话；文件按原生 `blueprint-review-feedback@1` 写，字段即原生字段：
    批次 `artifact/blueprint_id/component_id/source_revision/items`，条目 `feedback_id/kind/source_revision/target_ref/body`，
    事实带 `evidence_refs`，授权裁决带真实的 `authority` 与明确的 `decision`。target_ref 与版本只在这份原生传输件里维护：
    目标已有的用它的稳定地址，新问题还没有 gap 时指向现有 `blueprint:<id>` 并说明受影响范围，由 owner 形成真正的新 gap。
    被评的版本是成文登记记下的蓝图版本；还没有成文时取本次质询的实际版本。不能靠改版本号把旧稿意见套到新稿上。

    两件事分开记：提交时的候选资格（原生只判够不够格进入调和，文件没改就不重判）与当前蓝图里来源精确指向这份反馈的决定。
    接受与否由蓝图负责方在 component-design 里定；原生返回的候选不是 accepted，这里只报「待确认」。
    """
    records = _records(feature_root)
    rid, rec, path, shown = _feedback_file(feature_root, records)
    if not path.is_file():
        raise FlowError(f"还没有 {FEEDBACK}：把评审人对设计的反馈写成 blueprint-review-feedback@1，"
                        f"落点 {shown}，写法见 phases/update.md「设计反馈」")
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8").lstrip("\ufeff"))
    except ValueError as exc:
        raise FlowError(f"{FEEDBACK} 不是合法 JSON（{exc}）") from exc
    contract = load(feature_root) or {}
    blueprint = feature_root.name if blueprint_exists(feature_root) else None
    if not blueprint:
        raise FlowError("这张单还没有同根蓝图：设计反馈评的是原生蓝图，设计没开始就没有可评的对象")
    reviewed = ((contract.get("story_basis") or {}).get("blueprint_ref") or {}).get("revision")
    if reviewed is None:
        from flow import native  # noqa: PLC0415 —— 还没有成文时按本次质询的实际版本
        read = native.call(project_root, "blueprint", "--blueprint", blueprint, "--purpose", "draft")
        if read.get("status") != "ok":
            raise FlowError(f"蓝图 {blueprint} 当前读不过（{read.get('status')}）：{native.issues_text(read)}——"
                            "设计反馈要指向可读的原生蓝图")
        reviewed = (read.get("blueprint_ref") or {}).get("revision")
    digest = file_sha256(path)
    state = (rec.get("design_feedback") if rec is not None else contract.get("design_feedback")) or {}
    if state.get("digest") != digest:
        problems = []
        if doc.get("source_revision") != reviewed:
            problems.append(f"source_revision 应是被评的蓝图版本 {reviewed}（写的是 {doc.get('source_revision')}）。"
                            "反馈不能把旧输入改成当前版本号来通过：仍适用的旧意见由负责方按当前目标形成一个新版本的新反馈，"
                            "并引用旧原件")
        items = []
        for item in doc.get("items") or []:
            fid = str(item.get("feedback_id") or "")
            items.append({"feedback_id": fid, "kind": item.get("kind"), "source_revision": item.get("source_revision"),
                          "target_ref": item.get("target_ref"), "evidence_refs": item.get("evidence_refs") or []})
            problems.extend(p for p in (_evidence_ref_problem(project_root, feature_root, r, fid)
                                        for r in item.get("evidence_refs") or []) if p)
        from flow import native  # noqa: PLC0415 —— 资格只由原生判
        out = native.call(project_root, "feedback", "--blueprint", blueprint, stdin=doc)
        fb = {"path": shown, "ref": path.relative_to(project_root).as_posix(), "digest": digest,
              "blueprint_id": blueprint, "source_revision": doc.get("source_revision"), "reviewed_revision": reviewed,
              "items": items, "problems": problems, "native_issues": out.get("issues", []),
              "candidates": out.get("candidates"), "eligible": not problems and out.get("status") == "ok"}
        if rec is not None:
            rec["design_feedback"] = fb
            (_updates_dir(feature_root) / rid / "record.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            contract["design_feedback"] = fb
            save(feature_root, contract)
        state = fb
    observed = _feedback_observed(feature_root, state)
    issues = [f"{i.get('code') or i.get('id')} {i.get('message', '')}" for i in state["native_issues"]]
    return {"update": rid, "where": shown, "feedback": observed, "eligible": state["eligible"],
            "problems": state["problems"], "native_issues": state["native_issues"],
            "candidates": state["candidates"], "source_revision": state["source_revision"],
            "reviewed_revision": state["reviewed_revision"],
            "action": ("反馈够格进入调和，交蓝图负责方在 component-design 里处理。候选资格不等于接受：负责方的回复原文记进本轮 "
                       "update-notes，结合当前蓝图判结果，没有明确结论就保持待确认。"
                       if state["eligible"] else "反馈有问题，改好这一份 design-feedback.json 再跑：" + "；".join(
                           state["problems"] + issues[:8]))}


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


#: 逐件发布基线取自主体的本地件：系统交付项 → 需求目录相对路径
PUBLISHED_LOCAL = {"AR-design.md": "/".join(STORY), "design-review.md": "blueprint/component-blueprint.review.md"}


def carried_external(feature_root: Path, name: str) -> tuple[str, str] | None:
    """最近一次非撤回的 documents 轮已承接这一件外部版本时，给出逐件 B（那一轮实际处理的外部摘要）与来源。

    复用 update 轮的记录与原件，不新增已批准状态或平行基线账本。条件同时成立才算：
    该轮已 closed、当前没有进行中的 update、该轮晚于这一件最近一次真实发布/远端恢复事件、
    系统项的原件与批次回执可核、当前本地件等于该轮 `owned_after` 登记的版本。
    满足时 B 取那一轮实际处理的 E：外部此后没再变就不必再次回答覆盖确认；不满足返回 None，沿原发布/恢复基线。
    """
    contract = load(feature_root) or {}
    if (contract.get("update") or {}).get("open"):
        return None
    local_rel = PUBLISHED_LOCAL.get(name)
    if local_rel is None:
        return None
    events = [at for at in (moment((contract.get("archived") or {}).get("at")),
                            moment((contract.get("archived") or {}).get("restored_at"))) if at]
    current_sha = file_sha256(feature_root / Path(*local_rel.split("/")))
    if current_sha is None:
        return None
    for rid, rec in reversed(_records(feature_root)):
        if rec.get("status") != "closed" or rec.get("requested_result") != "documents":
            continue
        closed = moment(rec.get("closed_at"))
        if closed is None or (events and closed <= max(events)):
            continue
        entry = next((e for e in rec.get("review_inputs") or []
                      if e.get("system_item") == name and e.get("status") in ("fetched", "same")), None)
        if not entry or not entry.get("digest") or not entry.get("path"):
            continue
        if (rec.get("owned_after") or {}).get(local_rel) != current_sha:
            continue                     # close 之后本地又改过：不用旧承接事实给新稿盖章
        original = feature_root / Path(*str(entry["path"]).split("/"))
        if not original.is_file() or file_sha256(original) != entry.get("sha256"):
            continue                     # 取回原件不在了或已变：这一版核不了
        if not (original.parent / ".receipt.json").is_file():
            continue                     # 批次回执不在：摘要的出处核不了
        return str(entry["digest"]), f"update {rid} 已承接受件（{entry.get('path')}）"
    return None


def materials_since_registration(feature_root: Path, contract: dict) -> str | None:
    """成文登记之后材料有没有再变：登记时记下的材料索引摘要不等于现在的，返回原因；没变返回 None。

    本轮来的新材料无论设计采用与否，都要经过一次按当前材料的成文登记（作者据它判断采不采用、Story 要不要改），
    documents 收口才算这一轮承接了它。采用关系与需求条目的变化由成文依据里的设计采用来源另核。
    """
    try:
        live = registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    if live.get("digest") != (contract.get("story_basis") or {}).get("materials_digest"):
        return "成文登记之后材料又变了，登记的还是变化之前的那一版"
    return None


def cmd_update_close(feature_root: Path, feature: str, project_root: Path) -> dict:
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
    touched = [rel for rel in ("/".join(p) for p in PRODUCTS)
               if file_sha256(feature_root / rel) != before.get(rel)]
    if result == "materials" and touched:
        raise FlowError(f"这一轮登记的请求是 materials，却改了已有人读件 {'、'.join(touched)}，不收口："
                        "已有 Story 受影响的是 documents——`update --action prepare --result documents` 改记终点，按 documents 收口")
    if result == "documents" and contract.get("status") == "story_written":
        stale = materials_since_registration(feature_root, contract)
        if stale:
            raise FlowError(f"{stale}，不收口：按新材料判断设计要不要同步（采用的来源在蓝图需求条目里改）、Story 要不要改，"
                            "`story-build review --action prepare` 定稿并重新独立审查，再跑 `story_flow.py story` 重新登记")
    if result == "documents" and (feature_root / Path(*STORY)).is_file():
        registered_before = (load(root / "before") or {}).get("status") == "story_written"
        if contract.get("status") != "story_written":
            if registered_before or touched:
                raise FlowError("story 这一轮改过或登记作废了，还没按当前内容重新登记，不收口："
                                "先 `story-build review --action prepare` 定稿（重投附录、编号、全篇 check）并重新独立审查，"
                                "审查通过后跑 `story_flow.py story` 重新登记")
        else:
            drift = registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
            if drift:
                raise FlowError(f"story 与当前依据不同步（needs_sync：{'、'.join(drift)}），不收口："
                                "新设计已接受而稿未同步的，按当前蓝图改稿，`story-build review --action prepare` 定稿并重新独立审查，"
                                "审查通过后跑 `story_flow.py story` 重新登记")

    record_owned_after(feature_root)
    rec = dict(_records(feature_root))[rid]
    feedback = _feedback_observed(feature_root, rec["design_feedback"]) if rec.get("design_feedback") else None
    current, unreadable = _scan(feature_root)
    # `after/` 是**给下一轮比的正文**，不是交付目录的副本：只留这一轮盯着的那几份。
    kept = _keep(feature_root, current, root / "after")
    units = _unit_facts(feature_root, project_root)
    stale = stale_units(units)
    contract = load(feature_root) or {}
    gap = _carry_start(feature_root, feature, rid, rec)      # 开轮时没移成的开始时刻，收口前再移一次
    # 人在这一轮的原话随轮次留档：契约只清「开着的那一轮」（还原同样如此）
    rec.update(status="closed", closed_at=now(), files=current, unreadable=unreadable,
               sources=_sources(feature_root),
               review_inputs=_review_inputs(feature_root),
               notes=f"AR/story-src/updates/{rid}/update-notes.md",
               after={"path": f"AR/story-src/updates/{rid}/after", "files": kept},
               units=units, stale_units=stale)
    contract["update"] = {"open": None, "last_closed": rid}
    save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    log(f"update {rid} 收口：比较正文留了 {kept} 份")
    answers_gap = sync_answers(feature_root, "本轮的收口")
    # 收口成立不回滚；本轮还有没做完的工作（如已开始的同图增强）由同一路由说出来，不以 closed 结束整个任务。
    # 算不出来不遮住已写盘的收口（同 cmd_story），命令照常成功、使用记录照常收尾
    try:
        step, follow = next_step(feature_root, contract)
    except FlowError as exc:
        step, follow = "status", f"暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取"
    return {"update": rid, "status": "closed", "requested_result": result, "compared_next_time": kept,
            **({"usage_error": gap} if gap else {}), **({"answers_error": answers_gap} if answers_gap else {}),
            "unreadable": unreadable, "units": units, "stale_units": stale, "design_feedback": feedback, "next": step,
            "action": f"{rid} 已收口。下一轮以此刻的内容为基准；本轮的原貌仍在 before/。"
                      + ("本轮终点是取材与澄清：还没有设计或成文，按需求进展接着走。" if result == "materials" else "")
                      + (f"设计反馈 {len(feedback)} 条交蓝图负责方，接受与否待确认（负责方回复记在 update-notes）；施工授权另由人给。"
                         if feedback else "")
                      + ("有读不到的文件，它们这一轮没能记进基准，下一轮仍会被单列。"
                         if unreadable else "") + stale_text(stale) + f"下一步：{follow}"}


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

    人的意见不随撤回退掉：本轮收到的评审输入原件在 before/ 里，收件箱里的原件与改稿也不在可撤回的文件里。

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

    # 先把现在与开轮时不同的那几份原样存进这一轮的记录目录（按轮次可定位）；存不下就不往下走
    saved = root / f"restore-{now().replace('-', '').replace(':', '').replace('T', '-')[:15]}"
    copy = saved.relative_to(feature_root).as_posix()
    for rel in (k for k in keys if current.get(k) is not None and current.get(k) != before.get(k)):
        src = feature_root / rel
        if src.is_file():
            (saved / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, saved / rel)

    conflicts, restored, removed = [], [], []
    # 材料索引是来源版本的登记（原件与留存都是受保护件、不随撤回退掉）：不退回旧索引，撤回之后按登记与盘上现状重算
    index = "/".join(registry.MANIFEST)
    keys = [k for k in keys if k != index]
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
                          "current": f"{copy}/{rel}" if now_sha else None,
                          "why": ("本轮没到完成点，改动没有登记的那一版可比" if after is None or rel not in after
                                  else "本轮完成点之后又改过")})

    contract = load(feature_root) or {}
    rec.update(status="restore_conflicted" if conflicts else "restored", restored_at=now(),
               restore_conflicts=conflicts, restore_copy=copy)
    if not conflicts:
        contract["update"] = {"open": None, "last_restored": rid}
        save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    answers_gap = sync_answers(feature_root, "本轮的撤回") if not conflicts else None
    drift = (registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
             if contract.get("status") == "story_written" else [])
    log(f"update {rid} 还原：退回 {len(restored)} 份、删掉 {len(removed)} 份、冲突 {len(conflicts)} 份")
    return {"update": rid, "status": rec["status"], "restored": restored, "removed": removed,
            "conflicts": conflicts, "restore_copy": rec["restore_copy"], "needs_sync": drift,
            **({"answers_error": answers_gap} if answers_gap else {}),
            "action": (f"有 {len(conflicts)} 份不满足退回条件，保留现状、这一轮照旧开着：逐份定好要哪一版后再跑 restore。"
                       if conflicts else f"本扩展在 {rid} 改过的文件已退回开轮之前，轮次关闭。")
                      + (f"成文登记与当前依据不一致（{'、'.join(drift)}）：登记保留原样，交付前按当前依据重新定稿登记。"
                         if drift else "")}
