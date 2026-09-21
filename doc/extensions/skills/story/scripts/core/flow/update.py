"""`/story update` 的文件侧支持 —— **脚本只回答确定的事**。

这一层做三件机械的事：把本次执行前的现场完整留一份、与上次已处理的版本比一遍、
把结果说清楚。取回来的新内容与人补的料一样进 `inbox/`，走 init 那条材料链——
这里不另开第二个入料口。**变化意味着什么、要改哪里，一概不判**——
那是模型读原文的事（方法在 `phases/update.md`）。

顺序是**先定输入，再检测**：`inputs` 报告上游与本地各有什么（不建任何东西），
模型据此在第一级关卡问人要不要补料；人答完、料登记进本轮，`prepare` 才比一遍。
真的一个字节没变、比较也完整、上一轮没留下没做完的事，就报「未检测到变化」退出，
不进语义流程、不碰业务文件。
**没查到不等于没变**：比较基准缺席、来源读不到，都单列出来说清可查范围，不许混进「无变化」。

落点在 `AR/story-src/updates/<id>/`，它不在材料扫描的范围里（材料只认合同声明的正文源、
`ux-reference`/`assets` 与会议原件），所以本层自己的写入不会把材料版本顶出一个新轮次。

五个动作：`inputs` 报输入、`prepare` 比一遍并开这一轮、`status` 报现在开着什么、
`close` 收口并留下可比的正文、`restore` 把现场还原到这一轮开始之前。
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
from pathlib import Path

from materials import registry

from flow.routing import inputs_answer, material_state
from flow.state import (CONTRACT, FlowError, SKILL_ROOT, STORY, REVIEW,
                        load, log, now, round_gates, save)

#: 本层全部落点的根。放在 story-src 下面：它是过程目录，AR 根只留交付件。
UPDATES = ("AR", "story-src", "updates")
#: 镜像不复制的目录：本层自己的落点（复制它等于把镜像套进镜像），以及阶段报告与导入备份——
#: 它们不是业务内容，而报告带 64 位哈希的文件名，套进更深的目录会超 Windows 的路径上限。
MIRROR_SKIP = {UPDATES[-1], "reports", ".backup"}
#: 同样不复制的单个文件：framework 重验留下的过程件。
MIRROR_SKIP_FILES = {"revalidation.json"}
#: 除材料正文之外，判「跟上次比变了没有」要看的交付件——**人会直接动的那几份**。
#:
#: 连同合同登记的三份上游正文（`registry.source_docs()`）与收件箱（由材料事实回答，
#: 不按文件哈希比），一共八项。决策登记、写作设计、知识判断、验收与两份强契约不在里面：
#: 它们是模型据这几份写出来的中间真源，随交付件的修订而变，是结果不是原因。
#: 人要直接改强契约，那是 framework 的修正入口，不是 update。
#: 盘上没有的跳过，不当成被删（`_scan`）。
PRODUCTS = (STORY, REVIEW, ("spec", "spec.md"), ("plan", "plan.md"))


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


def _skipped(rel: Path) -> bool:
    return bool(set(rel.parts[:-1]) & MIRROR_SKIP) or rel.name in MIRROR_SKIP_FILES


def _mirror(feature_root: Path, dest: Path) -> int:
    """本次执行前的完整现场。**先存够再往下走**：存不下就别开始。

    跳过 `MIRROR_SKIP` 那几类；符号链接不跟随——跟随的话，指到需求目录外面的那一条
    会把镜像写到别处，而「还原」时又照着它写回去。
    """
    count = 0
    for src in sorted(feature_root.rglob("*")):
        rel = src.relative_to(feature_root)
        if _skipped(rel) or src.is_symlink():
            continue
        if src.is_file():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            count += 1
    return count


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
        try:
            a = old.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            b = new.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            continue
        text = "".join(difflib.unified_diff(a, b, fromfile=f"上次/{rel}", tofile=f"现在/{rel}"))
        if not text.strip():
            continue
        out = dest / (rel.replace("/", "__") + ".diff")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        written += 1
    return written


def _note_prepare(feature_root: Path, comparison: str) -> None:
    """这一次检测完了、结论是什么 —— **机械留痕，不是业务产物**。

    「无变化」那条路按设计什么都不建、什么都不删，于是外面看不出它跑过没有。
    留一行点开头的痕迹在过程目录里：不进材料清单、不进比较集合、下一轮照样被忽略，
    但测试装置据它认得出「这一轮走完了，结论是没变化」——
    不然一次「没什么要改」的更新会停在那里等人来收，而它其实早就结束了。
    """
    base = _updates_dir(feature_root)
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / ".last-prepare.json").write_text(
            json.dumps({"comparison": comparison, "at": now()}, ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        pass          # 留痕失败不该让一次正常的检测失败


def _contract(feature_root: Path) -> dict:
    contract = load(feature_root)
    if contract is None:
        raise FlowError("这个单没走过 /story：先跑 `story_flow.py init`，"
                        "update 更新的是已经存在的产物")
    return contract


def _resume(records: list[tuple[str, dict]]) -> dict | None:
    """上一轮还开着：**不新建镜像**——新的会把旧的恢复依据盖掉。"""
    for rid, rec in reversed(records):
        if rec.get("status") == "open":
            return {"comparison": "resume", "update": rid,
                    "notes": f"AR/story-src/updates/{rid}/update-notes.md",
                    "action": f"上一次 update（{rid}）还开着：先读它的 update-notes 与 before/ "
                              "接着做完，或按它的记录还原现场。不新建这一轮的镜像。"}
    return None


def _collect(feature_root: Path, contract: dict, records: list[tuple[str, dict]],
             request: str | None) -> dict:
    """四类输入一次收齐：交付件与上游正文对上次的差异、读不到的、收件箱的材料事实、人的要求。

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
            "request": str(request or "").strip() or None}


def _superseded_hint(feature_root: Path, pending: list[str]) -> list[dict]:
    """新原件可能取代的旧原件：收件箱里**已归类**的同类原件。**只列，不判**——是不是新版由你读了定。

    导入链把同一类的原件按名拼接成目标正文，没有「替代」一说：旧原件留在收件箱里，
    目标就是两版拼在一起（正式 T2 里模型备份了目标文件，旧原件原地没动）。
    新原件自己还没归类时，列出全部已归类的原件。
    """
    inbox = feature_root / "inbox"
    try:
        classes = json.loads((inbox / ".classify.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(classes, dict):
        return []
    known = {name: cls for name, cls in classes.items() if (inbox / name).is_file()}
    out = []
    for new in pending:
        cls = known.get(new)
        olds = sorted(n for n, c in known.items() if n != new and (cls is None or c == cls))
        if olds:
            out.append({"new": new, "same_class": olds,
                        "note": f"若 {new} 取代其中某份，导入前先把 inbox 里那份移进 .backup/"})
    return out


def _nothing(facts: dict) -> bool:
    return (facts["diff"]["complete"] and not facts["changed"] and not facts["unreadable"]
            and not facts["pending"] and not facts["materials_changed"] and not facts["request"])


def _receipt(feature_root: Path) -> dict | None:
    """最近一次取材的回执。**原样转交**：取到没有、与本地是否相同由对接层写明，这里不判。"""
    path = feature_root / "AR" / "story-src" / "fetched.json"
    try:
        return json.loads(path.read_text(encoding="utf-8").lstrip("\ufeff"))
    except (OSError, ValueError):
        return None


def cmd_update_inputs(feature_root: Path, feature: str, project_root: Path,
                      request: str | None = None) -> dict:
    """输入阶段：**报告，不建任何东西**。人还没说要不要补料，现在比出来的不是最终的变化。

    在流程契约上记一笔 `update.stage = inputs`：路由据它把这一次停在第一级关卡——
    与 init 同一个关卡、同一份侧车、同一条 `decide`，问的是这一次要不要补料。
    """
    contract = _contract(feature_root)
    records = _records(feature_root)
    resumed = _resume(records)
    if resumed:
        return resumed
    facts = _collect(feature_root, contract, records, request)
    contract["update"] = {**(contract.get("update") or {}), "stage": "inputs", "inputs_at": now(),
                          "inputs_from": len(round_gates(contract))}
    save(feature_root, contract)
    fetch = _fetch_command(feature_root, feature, project_root)
    return {"stage": "inputs", "changed": facts["changed"], "unreadable": facts["unreadable"],
            "baseline": facts["diff"]["complete"], "pending": facts["pending"],
            "superseded_hint": facts["superseded_hint"],
            "materials_changed": facts["materials_changed"],
            "upstream": _receipt(feature_root) if fetch else None, "fetch": fetch,
            "action": ("`upstream` 是最近一次取材的回执（看它的时刻，没取过或不是这一次取的就先跑 `fetch`）；"
                       if fetch else "本地单没有上游；")
                      + "按 `rules/init_analysis.md` S2a 盘点手上的料，摆第一级选项侧车，"
                      "问人这一次要不要补料，**停等**。人答了 → `decide --gate material_scope` 记原话 → "
                      "收件箱有新原件先导入 → `round` 登记到本轮 → `update --action prepare`"}


def cmd_update_prepare(feature_root: Path, request: str | None = None) -> dict:
    """输入定了之后比一遍、该留的留下、该说的说清楚。

    四种去向，`comparison` 直说是哪一种：

    - `resume`   上一轮还开着。**不新建镜像**——新的会把旧的恢复依据盖掉；
    - `unchanged` 八项都没变、收件箱没有未并入的原件、比较完整、也没有人明确要求：什么都不建，退出；
    - `incomplete` 比较基准缺席或来源读不到：说清可查与不可查的范围，交模型判当前一致性；
    - `changed`  有变化：本轮镜像留着不动，差异与位置交给模型。

    **返回的全是机械事实**：哪几份文件跟上次不一样、收件箱里什么还没并入、镜像在哪。
    这些事实不表示任何业务结论——「变化意味着什么」由模型读原文回答。
    """
    contract = _contract(feature_root)
    update = contract.get("update") or {}
    if update.get("stage") == "inputs":
        answer = inputs_answer(contract)
        if not answer or answer.get("outcome") != "accepted":
            raise FlowError("输入阶段还没问过人要不要补料：按 `status` 的下一步在第一级关卡停一次，"
                            "人答了、料登记进本轮，再跑 prepare")
    records = _records(feature_root)
    resumed = _resume(records)
    if resumed:
        return resumed

    facts = _collect(feature_root, contract, records, request)
    current, unreadable, diff, changed = (facts["current"], facts["unreadable"],
                                          facts["diff"], facts["changed"])
    pending, asked = facts["pending"], bool(facts["request"])

    if _nothing(facts):
        # 本次什么都没建，所以也没有要删的临时副本；说清楚「比过了、真没变」。
        # 输入阶段的记号到此用完：留着的话路由会一直把这个单停在补料关卡。
        contract["update"] = {k: v for k, v in update.items() if k not in ("stage", "inputs_at", "inputs_from")}
        save(feature_root, contract)
        _note_prepare(feature_root, "unchanged")
        return {"comparison": "unchanged", "compared": len(current),
                "action": "与上次已处理的版本逐份比过，没有变化，收件箱也没有未并入的原件，"
                          "没有没做完的更新。这一轮不改任何业务文件，不进语义流程。"}

    # id 用时间是为了人一眼看得出先后；撞名就加序号，**不把「同一秒跑了两次」做成失败**。
    stem = now().replace("-", "").replace(":", "").replace("T", "-")[:15]
    rid, n = stem, 1
    while (_updates_dir(feature_root) / rid).exists():
        n += 1
        rid = f"{stem}-{n}"
    root = _updates_dir(feature_root) / rid
    before = root / "before"
    before.mkdir(parents=True)
    mirrored = _mirror(feature_root, before)

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
    record = {"id": rid, "opened_at": now(), "status": "open",
              "files": current, "unreadable": unreadable, "comparison": diff,
              "materials": {"pending": pending, "changed": facts["materials_changed"]},
              "request": facts["request"],
              "mirror": {"path": f"AR/story-src/updates/{rid}/before", "files": mirrored}}
    (root / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")

    # 有东西要处理就是 changed；走到这里却什么都没有，只能是基准缺席或来源读不到。
    material = bool(pending or facts["materials_changed"])
    kind = "changed" if (changed or material or asked) else "incomplete"
    lines = []
    if changed:
        lines.append("变了的：" + "、".join(changed))
    if pending:
        lines.append(f"收件箱有 {len(pending)} 份还没并入正文（{'、'.join(pending[:3])}）："
                     "采用的先导入、`round` 登记到本轮")
    elif facts["materials_changed"]:
        lines.append("材料指纹与本轮登记的对不上：先 `round` 登记到本轮")
    if not diff["complete"]:
        lines.append("没有上次已处理的版本可比：这一轮说不出「原来怎么写」，"
                     "按当前材料与产物核一致性，别补造历史")
    if unreadable:
        lines.append("读不到：" + "、".join(f"{k}（{why}）" for k, why in unreadable.items())
                     + "——这是缺口，不是「没有变化」，更不是「它被删了」")
    if asked and not changed and not material:
        # 文件一个字节没变，但人明确要求改一件事：这不是「无变化」，要走语义流程。
        lines.append("文件没变，但这一轮有人明确要求改的事，按它处置")
    _note_prepare(feature_root, kind)
    log(f"update {rid}：镜像 {mirrored} 份、差异 {diffs} 份")
    return {"comparison": kind, "update": rid, "changed": changed, "pending": pending,
            "superseded_hint": facts["superseded_hint"],
            "unreadable": unreadable, "baseline": diff["complete"], "diffs": diffs,
            "mirror": record["mirror"]["path"],
            "action": "；".join(lines) + f"。原貌留在 AR/story-src/updates/{rid}/before/，"
                      "处置方法见 phases/update.md"}


# ---------------------------------------------------------------------------
# 阶段事实：哪些阶段有产物、闭没闭环。
#
# 读的是 harness 自己写的 `<阶段>/reports/summary.json`——它是**只读投影**，
# 不是我们的账。自己另记一份的话，两边迟早对不上，而人会信错的那一份。
# 读不出来就说读不出来：闭没闭环这件事不许猜，猜错的方向是「以为闭了」。
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")


def _phase_facts(feature_root: Path) -> list[dict]:
    out = []
    for phase in PHASES:
        summary = feature_root / phase / "reports" / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8").lstrip("﻿"))
        except (OSError, ValueError) as exc:
            out.append({"phase": phase, "readable": False, "why": str(exc)})
            continue
        subject = data.get("verifier_subject_id")
        mode = (data.get("verifier_closure") or {}).get("mode")
        out.append({"phase": phase, "readable": True,
                    "closure": data.get("closure_status"),
                    "verdict": data.get("verdict"),
                    "subject": subject, "closure_mode": mode,
                    "signals": [x.get("id") if isinstance(x, dict) else x
                                for x in data.get("readiness_signals") or []],
                    "unadopted": mode == "completed_with_prior_review"
                    and _report_passed(feature_root / phase / "reports", subject)})
    return out


#: 审查报告的终态块（framework `verifier-subject.ts::parseResultBlock` 读的那一段）。
RESULT_BLOCK = re.compile(r"<!-- maison-verifier-result:v1 -->(.*?)<!-- /maison-verifier-result:v1 -->", re.S)


def _report_passed(reports: Path, subject: str | None) -> bool:
    """当前 subject 的报告在盘上、终态块回显的就是它、判的是 PASS。"""
    if not subject:
        return False
    try:
        text = (reports / f"verifier.report.{subject}.md").read_text(encoding="utf-8")
    except OSError:
        return False
    blocks = RESULT_BLOCK.findall(text)
    if len(blocks) != 1:
        return False
    fields = dict(line.split(":", 1) for line in blocks[0].strip().splitlines() if ":" in line)
    return (fields.get("verifier_subject_id", "").strip() == subject
            and fields.get("verdict", "").strip() == "PASS")


def _fetch_command(feature_root: Path, feature: str, project_root: Path) -> str | None:
    """取材命令由本层渲染：落点是这个单的 `inbox/`——与人补料同一个入料口。

    让模型自己拼 `--out` 的话，它可以指到任何目录，包括需求目录外面。
    `--project-root` 一并写上：回执落在它下面的需求目录里，与 `--out` 必须是同一个工程。
    本地单不挂在需求系统上，没有这条命令。
    """
    if re.match(r"local[-_]", feature, re.IGNORECASE):
        return None
    adapter = SKILL_ROOT / "scripts" / "adapters" / "story.js"
    return (f"node {adapter.as_posix()} fetch {feature} <token> "
            f"--project-root {project_root.as_posix()} --out {(feature_root / 'inbox').as_posix()}")


def _latest(records: list[tuple[str, dict]], status: str | None = None) -> tuple[str, dict] | None:
    for rid, rec in reversed(records):
        if status is None or rec.get("status") == status:
            return rid, rec
    return None


def cmd_update_status(feature_root: Path, feature: str, project_root: Path) -> dict:
    """现在有没有开着的更新、上一次做到哪、说明在哪。**只报事实，不判对错。**"""
    records = _records(feature_root)
    openest = _latest(records, "open")
    closed = _latest(records, "closed")
    out = {"rounds": len(records), "phases": _phase_facts(feature_root),
           "stage": ((load(feature_root) or {}).get("update") or {}).get("stage"),
           "fetch": _fetch_command(feature_root, feature, project_root)}
    if openest:
        rid, rec = openest
        notes = _updates_dir(feature_root) / rid / "update-notes.md"
        out.update(open=rid, opened_at=rec.get("opened_at"),
                   notes=f"AR/story-src/updates/{rid}/update-notes.md" if notes.is_file() else None,
                   action=(f"更新 {rid} 还开着。"
                           + ("说明在 update-notes.md，接着做完或 restore 还原现场。"
                              if notes.is_file()
                              else "还没有 update-notes.md——close 要绑定它，先把本轮判断写下来。")))
        return out
    out.update(open=None,
               last_closed=closed[0] if closed else None,
               action=("没有开着的更新。" + ("上一次已收口，可以起新的一轮。" if closed
                                             else "这个单还没有做过 update。")))
    return out


def cmd_update_close(feature_root: Path) -> dict:
    """收口这一轮：**绑定说明、记下此刻的文件摘要、留一份可比的正文**。

    只记录「本轮处理到这里」，**不判语义对不对，也不发布**——那两件事一个归审查、
    一个归归档。没有 `update-notes.md` 就不收口：收了的话，下一轮拿到的基准背后
    没有任何解释，而「上次为什么这么改」正是下一轮最需要的东西。
    """
    records = _records(feature_root)
    openest = _latest(records, "open")
    if not openest:
        raise FlowError("没有开着的更新可以收口：先跑 `story_flow.py update` 起一轮")
    rid, rec = openest
    root = _updates_dir(feature_root) / rid
    notes = root / "update-notes.md"
    if not notes.is_file() or not notes.read_text(encoding="utf-8").strip():
        raise FlowError(
            f"{rid} 还没有写 update-notes.md（或它是空的），不收口。"
            "四段就够：当前依据、变化与影响、决定与修订、核对与剩余——"
            f"落点 AR/story-src/updates/{rid}/update-notes.md")

    # 报告写了、判了 PASS，阶段却仍标「沿用历史」：framework 不改写已闭环的 summary，
    # 只有再跑一次完整 harness 才采纳它。这时收口，这一轮就带着一个「没审」的闭环结束了。
    phases = _phase_facts(feature_root)
    stuck = [f["phase"] for f in phases if f.get("unadopted")]
    if stuck:
        raise FlowError(
            f"{'、'.join(stuck)} 的审查报告已写、判 PASS，但阶段闭环仍是沿用历史（没被采纳），不收口："
            "逐个跑 `harness-runner.ts --phase <阶段> --feature <编号>`（不是 --sync-closure），"
            "读 summary 确认 semantic_not_reverified 已消失再收口")

    current, unreadable = _scan(feature_root)
    # `after/` 是**给下一轮比的正文**，不是交付目录的副本：只留这一轮盯着的那几份。
    after = root / "after"
    kept = 0
    for key in current:
        src = feature_root / key
        if not src.is_file():
            continue
        target = after / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        kept += 1

    rec.update(status="closed", closed_at=now(), files=current, unreadable=unreadable,
               notes=f"AR/story-src/updates/{rid}/update-notes.md",
               after={"path": f"AR/story-src/updates/{rid}/after", "files": kept},
               phases=phases)
    contract = load(feature_root) or {}
    contract["update"] = {"open": None, "last_closed": rid}
    save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    log(f"update {rid} 收口：比较正文留了 {kept} 份")
    return {"update": rid, "status": "closed", "compared_next_time": kept,
            "unreadable": unreadable, "phases": phases,
            "action": f"{rid} 已收口。下一轮以此刻的内容为基准；本轮的原貌仍在 before/。"
                      + ("有读不到的文件，它们这一轮没能记进基准，下一轮仍会被单列。"
                         if unreadable else "")}


def cmd_update_restore(feature_root: Path) -> dict:
    """把需求目录还原到这一轮开始之前。**先保住现在，再往回写。**

    还原是覆盖，而覆盖掉的可能正是有人刚写的东西。所以顺序是：凡是与 `before/` 不一样的，
    先原样存进 `conflict-<时刻>/`，再照 `before/` 写回去；这一轮之后新建的文件删掉
    （它们在开始之前不存在，「还原」就该让它们不存在），删之前同样先存。
    **两边都留着**，报告说清哪几份有冲突——不替人决定要谁。
    """
    records = _records(feature_root)
    target = _latest(records, "open") or _latest(records)
    if not target:
        raise FlowError("这个单没有做过 update，没有可以还原的现场")
    rid, rec = target
    root = _updates_dir(feature_root) / rid
    before = root / "before"
    if not before.is_dir():
        raise FlowError(f"{rid} 没有留下 before/，还原不了。"
                        "它应当在起手时建好；目录被移走的话，这一轮只能按当前内容继续")

    saved = root / f"conflict-{now().replace('-', '').replace(':', '').replace('T', '-')[:15]}"
    mirrored = {p.relative_to(before).as_posix() for p in before.rglob("*") if p.is_file()}
    # 链接与镜像侧同一口径：镜像不跟随链接，这里也不能把链接算成「这一轮新建的」——
    # 算进去就会被当成多出来的文件删掉，而它在这一轮开始之前就在。
    live = {p.relative_to(feature_root).as_posix() for p in feature_root.rglob("*")
            if p.is_file() and not p.is_symlink()
            and not _skipped(p.relative_to(feature_root))}

    conflicts, restored, removed = [], 0, 0
    def keep(rel: str) -> None:
        src = feature_root / rel
        dest = saved / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        conflicts.append(rel)

    for rel in sorted(mirrored):
        src, dst = before / rel, feature_root / rel
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            continue
        if dst.is_file():
            keep(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        restored += 1
    for rel in sorted(live - mirrored):
        keep(rel)
        (feature_root / rel).unlink()
        removed += 1

    rec.update(status="restored", restored_at=now(),
               conflicts=conflicts,
               conflict_copy=(f"AR/story-src/updates/{rid}/{saved.name}" if conflicts else None))
    contract = load(feature_root) or {}
    contract["update"] = {"open": None, "last_restored": rid}
    save(feature_root, contract)
    (root / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    log(f"update {rid} 已还原：写回 {restored} 份、删掉 {removed} 份、留存 {len(conflicts)} 份")
    return {"update": rid, "status": "restored", "restored": restored, "removed": removed,
            "conflicts": conflicts,
            "conflict_copy": rec["conflict_copy"],
            "action": f"需求目录已回到 {rid} 开始之前。"
                      + (f"有 {len(conflicts)} 份在这之后被改过或新建，原样存在 "
                         f"{rec['conflict_copy']}/，两边都在，要哪一份由人定。"
                         if conflicts else "没有发现这之后的改动。")}
