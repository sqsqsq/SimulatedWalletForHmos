"""对外发布（归档）前后的核对与记录：交付资格、外部当前内容与上次实际基线、发布记录。

上传与恢复由数据对接层执行（`story.js archive / restore`），本层只做它们之前与之后确定的事：
发布前按当前人读交付门核资格，把差异、未决与未验证项摆给人；用最近一次取材的回执核需求系统上的正文
还是不是我们上次知道的那一版——被别人改过就交人定，不直接覆盖；发布与远端恢复之后记下外部现在是哪一版。
本地单没有远端，这里的动作都不适用。
"""
from __future__ import annotations

import difflib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flow.state import (CORE_DIR, FlowError, PUBLISHED, STORY, load, log, now, require, save, short_digest,
                        system_requirement)

#: 最近一次取材的回执，与 update 读的是同一份
RECEIPT = ("AR", "story-src", "fetched.json")
def _remote_only(feature_root: Path) -> None:
    if not system_requirement(feature_root.name):
        raise FlowError("本地单没有远端动作：交付终点就是仓内的 AR/story.md 与 AR/review.md")


def _gate(feature_root: Path, project_root: Path) -> tuple[bool, str]:
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：发布资格按交付门判，无法跳过")
    proc = subprocess.run([node, str(CORE_DIR / "story-build.mjs"), "check", "--deliver", "--feature", feature_root.name,
                           "--project-root", str(project_root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def _external(feature_root: Path, since: str | None) -> dict:
    """回执里本单正文那一份（AR-design.md）：要在 `since` 之后取过，读取失败不往下判。"""
    path = feature_root / Path(*RECEIPT)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except (OSError, ValueError) as exc:
        raise FlowError(f"{'/'.join(RECEIPT)} 读不出来（{exc}）：发布前先取一次材，按取回的外部当前内容核") from exc
    fetched = datetime.fromisoformat(str(receipt.get("fetchedAt", "")).replace("Z", "+00:00"))
    if since and fetched < datetime.fromisoformat(since):
        raise FlowError("最近一次取材早于这一版的登记：发布前重新取一次材，外部当前内容以那次为准")
    item = next((i for i in receipt.get("items") or [] if i.get("name") == "AR-design.md"), None)
    if item is None or item.get("status") == "failed":
        raise FlowError("外部当前正文没取到（" + str((item or {}).get("note", "回执里没有这一份")) + "）：不知道外部是哪一版就不发布")
    return item


def cmd_publish(feature_root: Path, project_root: Path, reply: str | None) -> dict:
    """发布前核一遍，**不上传**：资格、外部是不是我们知道的那一版、这次要交出去的差异、未决与未验证项。

    外部基线是上次发布（或远端恢复之后）记下的那一版；从没发布过时是本单采用的 AR 正文。外部摘要对不上基线，
    说明发布之后有人在需求系统上改过：列成冲突交人。人看过、确认仍要覆盖时，带 `--reply "<原话>"` 再跑，原话记进契约。
    """
    _remote_only(feature_root)
    contract = require(load(feature_root))
    if contract.get("status") != "story_written":
        raise FlowError("还没登记成文：发布的是登记过的那一份，先跑 `story_flow.py story`")
    passed, gate_out = _gate(feature_root, project_root)
    if not passed:
        raise FlowError("交付门没过，不发布：\n" + gate_out[-1500:])
    item = _external(feature_root, contract.get("story_written_at"))
    archived = contract.get("archived") or {}
    design = feature_root / "AR" / "design.md"
    baseline = archived.get("external_digest") or (short_digest(design.read_bytes()) if design.is_file() else None)
    current = short_digest((feature_root / Path(*STORY)).read_bytes())
    external = item.get("digest")
    conflict = item.get("status") != "absent" and external not in (baseline, current)
    if conflict and reply:
        contract.setdefault("publish_overrides", []).append({"at": now(), "external": external, "baseline": baseline,
                                                             "reply": reply.strip(), "by": "human"})
        save(feature_root, contract)
    last = feature_root / Path(*PUBLISHED) / "story.md"
    diff = ("首次发布：需求系统上还没有这张单的 Story" if not last.is_file() else "".join(difflib.unified_diff(
        last.read_text(encoding="utf-8").splitlines(keepends=True),
        (feature_root / Path(*STORY)).read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile="上次发布", tofile="这一次"))[:12000] or "与上次发布逐字相同")
    try:
        topics = json.loads((feature_root / "AR" / "story-src" / "decisions.json").read_text(encoding="utf-8-sig"))["decisions"]
    except (OSError, ValueError, KeyError) as exc:
        raise FlowError(f"AR/story-src/decisions.json 读不出议题（{exc}）：未决项从它列") from exc
    pending = [f"{t.get('id')} {t.get('title')}" for t in topics if t.get("status") == "open"]
    unverified = [line.strip() for line in gate_out.splitlines() if "建议照录" in line]
    blocked = conflict and not reply
    return {"publishable": not blocked, "external": external, "baseline": baseline, "conflict": conflict,
            "diff": diff, "open_topics": pending, "unverified": unverified,
            "action": ("需求系统上的正文在上次发布之后被改过（外部 " + str(external) + "，基线 " + str(baseline) + "）：不直接覆盖。"
                       "把外部改动与这次的差异摆给人——要并进来的走 `/story update`；人确认仍覆盖时带 `--reply \"<原话>\"` 再跑"
                       if blocked else
                       "把差异、未决议题与未验证项摆给人，人授权后执行上传，上传成功再 `story_flow.py archived` 登记")}


def cmd_restored(feature_root: Path) -> dict:
    """远端恢复之后：记下外部现在是哪一版，报告与本地的差异。**本地文件一个都不动**，归档登记与人签照旧。

    恢复只回退需求系统上的正文，评审记录附件与之后的人工意见留在系统上；外部现在是哪一版以恢复后取材的回执为准。
    """
    _remote_only(feature_root)
    contract = require(load(feature_root))
    archived = contract.get("archived") or {}
    if not archived:
        raise FlowError("这张单还没归档过：远端恢复回退的是某一次归档的覆盖")
    item = _external(feature_root, archived.get("at"))
    external = item.get("digest") if item.get("status") != "absent" else None
    local = short_digest((feature_root / Path(*STORY)).read_bytes())
    archived.update(external_digest=external, restored_at=now())
    contract["archived"] = archived
    save(feature_root, contract)
    log(f"已记下远端恢复：外部正文 {external or item.get('status')}，本地 Story {local}")
    return {"external": external, "local": local, "differs": external != local,
            "action": ("需求系统上现在是恢复后的那一版，本地 Story 仍是当前版，两边不同：再次发布前走 `publish` 核差异。"
                       if external != local else "需求系统上的正文与本地 Story 相同。")}
