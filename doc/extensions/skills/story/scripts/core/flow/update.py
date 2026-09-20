"""`/story update` 的文件侧支持 —— **脚本只回答确定的事**。

这一层做四件机械的事：把本次执行前的现场完整留一份、把取回来的新内容放进暂存、
与上次已处理的版本比一遍、把结果说清楚。**变化意味着什么、要改哪里，一概不判**——
那是模型读原文的事（方法在 `phases/update.md`）。

顺序是先检测再决定要不要模型理解：真的一个字节没变、比较也完整、上一轮没留下没做完的事，
就报「未检测到变化」，把本次的临时副本删掉退出，不进语义流程、不碰业务文件。
**没查到不等于没变**：比较基准缺席、来源读不到，都单列出来说清可查范围，不许混进「无变化」。

落点在 `AR/story-src/updates/<id>/`，它不在材料扫描的范围里（材料只认合同声明的正文源、
`ux-reference`/`assets` 与会议原件），所以本层自己的写入不会把材料版本顶出一个新轮次。

C1 只交 `prepare`；`status` / `close` / `restore` 在 C2。
"""
from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

from materials import registry

from flow.state import CONTRACT, FlowError, STORY, REVIEW, load, log, now

#: 本层全部落点的根。放在 story-src 下面：它是过程目录，AR 根只留交付件。
UPDATES = ("AR", "story-src", "updates")
#: 只读取材的暂存区。`adapters/story.js fetch --out` 写它，本层只读、只搬、不解析。
INCOMING = ("AR", "story-src", "incoming")
#: 镜像不复制的东西：本层自己的落点与暂存区。复制它们等于把镜像套进镜像。
MIRROR_SKIP = {UPDATES[-1], INCOMING[-1]}
#: 除材料之外还要盯着的当前产物。它们不是材料，但 update 要回答「它们跟上次比变了没有」。
PRODUCTS = (STORY, REVIEW, ("spec", "spec.md"), ("acceptance.yaml",))


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


def _scan(feature_root: Path) -> tuple[dict[str, str], list[str]]:
    """当前盘上这一轮要盯的文件 → 指纹。**读不到的单列，不当成不存在。**

    「文件不在」与「文件在但读不出来」是两件事：前者是删除，后者是环境问题。
    混成一个的话，一次权限错误会被报成「上游把这份材料删了」，而模型据此去删下游功能。
    """
    seen: dict[str, str] = {}
    unreadable: list[str] = []
    rels = [Path(rel) for rel in registry.source_docs()] + [Path(*p) for p in PRODUCTS]
    for rel in rels:
        path = feature_root / rel
        key = rel.as_posix()
        if not path.exists():
            continue
        try:
            seen[key] = registry.file_digest(path) or ""
        except OSError as exc:
            unreadable.append(f"{key}（{exc}）")
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


def _compare(current: dict[str, str], base: dict[str, str] | None) -> dict:
    """与基准比：新增 / 修改 / 删除。基准缺席时**如实说不知道**，不报「无变化」。"""
    if base is None:
        return {"complete": False, "added": [], "modified": [], "removed": [],
                "unknown": sorted(current)}
    return {"complete": True,
            "added": sorted(k for k in current if k not in base),
            "modified": sorted(k for k in current if k in base and current[k] != base[k]),
            "removed": sorted(k for k in base if k not in current),
            "unknown": []}


def _incoming(feature_root: Path) -> list[str]:
    """取材暂存区里现在有什么。**只看、不导**：导入会改正文，那是模型读完之后的事。"""
    base = feature_root / Path(*INCOMING)
    if not base.is_dir():
        return []
    return sorted(f.relative_to(base).as_posix() for f in base.rglob("*")
                  if f.is_file() and not f.name.startswith("."))


def _mirror(feature_root: Path, dest: Path) -> int:
    """本次执行前的完整现场。**先存够再往下走**：存不下就别开始。

    跳过本层自己的两个目录；符号链接不跟随——跟随的话，指到需求目录外面的那一条
    会把镜像写到别处，而「还原」时又照着它写回去。
    """
    count = 0
    for src in sorted(feature_root.rglob("*")):
        rel = src.relative_to(feature_root)
        if set(rel.parts) & MIRROR_SKIP or src.is_symlink():
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


def cmd_update_prepare(feature_root: Path, request: str | None = None) -> dict:
    """一次 update 的起手：比一遍、该留的留下、该说的说清楚。

    四种去向，`comparison` 直说是哪一种：

    - `resume`   上一轮还开着。**不新建镜像**——新的会把旧的恢复依据盖掉；
    - `unchanged` 真的没变、比较完整、也没有人明确要求重查：删掉本次临时副本退出；
    - `incomplete` 比较基准缺席或来源读不到：说清可查与不可查的范围，交模型判当前一致性；
    - `changed`  有变化：本轮镜像留着不动，差异与位置交给模型。

    **返回的全是机械事实**：哪几份文件跟上次不一样、暂存区里有什么、镜像在哪。
    这些事实不表示任何业务结论——「变化意味着什么」由模型读原文回答。
    """
    contract = load(feature_root)
    if contract is None:
        raise FlowError("这个单没走过 /story：先跑 `story_flow.py init`，"
                        "update 更新的是已经存在的产物")

    records = _records(feature_root)
    for rid, rec in reversed(records):
        if rec.get("status") == "open":
            return {"comparison": "resume", "update": rid,
                    "notes": f"AR/story-src/updates/{rid}/update-notes.md",
                    "action": f"上一次 update（{rid}）还开着：先读它的 update-notes 与 before/ "
                              "接着做完，或按它的记录还原现场。不新建这一轮的镜像。"}

    current, unreadable = _scan(feature_root)
    base = _baseline(records)
    diff = _compare(current, base)
    incoming = _incoming(feature_root)
    asked = bool(str(request or "").strip())
    changed = diff["added"] + diff["modified"] + diff["removed"]

    if diff["complete"] and not changed and not incoming and not unreadable and not asked:
        # 本次什么都没建，所以也没有要删的临时副本；说清楚「比过了、真没变」。
        return {"comparison": "unchanged", "compared": len(current),
                "action": "与上次已处理的版本逐份比过，没有变化，也没有没做完的更新。"
                          "这一轮不改任何业务文件，不进语义流程。"}

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

    if incoming:
        shutil.copytree(feature_root / Path(*INCOMING), root / "incoming", dirs_exist_ok=True)

    record = {"id": rid, "opened_at": now(), "status": "open",
              "files": current, "unreadable": unreadable, "comparison": diff,
              "incoming": incoming, "request": str(request or "").strip() or None,
              "mirror": {"path": f"AR/story-src/updates/{rid}/before", "files": mirrored}}
    (root / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")

    # 有东西要处理就是 changed；走到这里却什么都没有，只能是基准缺席或来源读不到。
    kind = "changed" if (changed or incoming or asked) else "incomplete"
    lines = []
    if changed:
        lines.append("变了的：" + "、".join(changed))
    if incoming:
        lines.append(f"取材暂存区有 {len(incoming)} 份等你读（不覆盖当前稿）")
    if not diff["complete"]:
        lines.append("没有上次已处理的版本可比：这一轮说不出「原来怎么写」，"
                     "按当前材料与产物核一致性，别补造历史")
    if unreadable:
        lines.append("读不到：" + "、".join(unreadable) + "——这是缺口，不是「没有变化」")
    if asked and not changed and not incoming:
        # 文件一个字节没变，但人明确要求改一件事：这不是「无变化」，要走语义流程。
        lines.append("文件没变，但这一轮有人明确要求改的事，按它处置")
    log(f"update {rid}：镜像 {mirrored} 份、差异 {diffs} 份")
    return {"comparison": kind, "update": rid, "changed": changed, "incoming": incoming,
            "unreadable": unreadable, "baseline": bool(base), "diffs": diffs,
            "mirror": record["mirror"]["path"],
            "action": "；".join(lines) + f"。原貌留在 AR/story-src/updates/{rid}/before/，"
                      "处置方法见 phases/update.md"}
