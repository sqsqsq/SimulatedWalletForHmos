"""对外发布（归档）前后的核对与记录：交付资格、三件的外部当前内容与各自的发布基线、发布记录。

上传与恢复由数据对接层执行（它的 archive 与 restore 命令），本层只做它们之前与之后确定的事：
发布前按当前人读交付门核资格，把差异、未决与未验证项摆给人；用最近一次取材的回执逐件核需求系统上的
Story 正文、Review 附件与设计附件还是不是我们上次知道的那一版——被别人改过就交人定，不直接覆盖；
发布与远端恢复之后记下外部现在是哪一版。本地单没有远端，这里的动作都不适用。
"""
from __future__ import annotations

import difflib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flow.state import (CORE_DIR, DESIGN_REVIEW, FlowError, PUBLISHED, REVIEW, STORY, load, log, now, require, save,
                        short_digest, system_requirement)

#: 最近一次取材的回执，与 update 读的是同一份
RECEIPT = ("AR", "story-src", "fetched.json")
#: 发布的三件：回执里的名字、本地文件、发布记录里的摘要键，按上传顺序
ITEMS = (("AR-design.md", STORY, "story_digest"),
         ("review.md", REVIEW, "review_digest"),
         ("design-review.md", DESIGN_REVIEW, "design_review_digest"))


def _remote_only(feature_root: Path) -> None:
    if not system_requirement(feature_root.name):
        raise FlowError("本地单没有远端动作：交付终点就是仓内的 AR/story.md、AR/review.md 与 AR/design-review.md")


def _gate(feature_root: Path, project_root: Path) -> tuple[bool, str]:
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：发布资格按交付门判，无法跳过")
    proc = subprocess.run([node, str(CORE_DIR / "story-build.mjs"), "check", "--deliver", "--feature", feature_root.name,
                           "--project-root", str(project_root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def read_receipt(feature_root: Path) -> dict:
    path = feature_root / Path(*RECEIPT)
    try:
        return json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except (OSError, ValueError) as exc:
        raise FlowError(f"{'/'.join(RECEIPT)} 读不出来（{exc}）：发布前先取一次材，按取回的外部当前内容核") from exc


def _external(feature_root: Path, since: str | None, names: tuple[str, ...]) -> dict[str, dict]:
    """回执里这几件：要在 `since` 之后取过，读取失败不往下判。"""
    receipt = read_receipt(feature_root)
    fetched = datetime.fromisoformat(str(receipt.get("fetchedAt", "")).replace("Z", "+00:00"))
    if since and fetched < datetime.fromisoformat(since):
        raise FlowError("最近一次取材早于这一版的登记：发布前重新取一次材，外部当前内容以那次为准")
    items = {i.get("name"): i for i in receipt.get("items") or []}
    out = {}
    for name in names:
        item = items.get(name)
        if item is None or item.get("status") == "failed":
            raise FlowError(f"外部当前的 {name} 没取到（{(item or {}).get('note', '回执里没有这一件')}）：不知道外部是哪一版就不发布")
        out[name] = item
    return out


def _baselines(feature_root: Path, contract: dict) -> dict[str, str | None]:
    """每件上次允许覆盖的那一版：发布过的取发布记录；正文首次发布取本单原始 AR/design.md，附件首次发布为不存在。"""
    archived = contract.get("archived") or {}
    design = feature_root / "AR" / "design.md"
    first_body = short_digest(design.read_bytes()) if design.is_file() else None
    return {"AR-design.md": archived.get("external_digest") or first_body,
            "review.md": archived.get("review_digest"),
            "design-review.md": archived.get("design_review_digest")}


def cmd_publish(feature_root: Path, project_root: Path, reply: str | None) -> dict:
    """发布前核一遍，**不上传**：资格、三件外部是不是我们知道的那一版、这次要交出去的差异、未决与未验证项。

    逐件比 B（上次允许覆盖的基线）、L（当前登记的本地件）与 E（刚取回的外部内容）：E=L 已完成，跳过；E=B 可写；
    其余是别人改过或所有权未确认，列成冲突交人。人看过、确认仍要覆盖时带 `--reply "<原话>"` 再跑，
    原话连同这一件的 E 与 L 记进契约，只授权这一件的这一次覆盖。
    """
    _remote_only(feature_root)
    contract = require(load(feature_root))
    if contract.get("status") != "story_written":
        raise FlowError("还没登记成文：发布的是登记过的那一份，先跑 `story_flow.py story`")
    passed, gate_out = _gate(feature_root, project_root)
    if not passed:
        raise FlowError("交付门没过，不发布：\n" + gate_out[-1500:])
    external = _external(feature_root, contract.get("story_written_at"), tuple(name for name, _, _ in ITEMS))
    base = _baselines(feature_root, contract)
    granted = contract.get("publish_overrides") or []
    rows = []
    for name, rel, _ in ITEMS:
        e = external[name].get("digest") if external[name].get("status") != "absent" else None
        local = short_digest((feature_root / Path(*rel)).read_bytes())
        action = ("skip" if e == local else "write" if e == base[name]
                  else "authorized" if any(g.get("item") == name and g.get("external") == e and g.get("local") == local
                                           for g in granted) else "conflict")
        rows.append({"item": name, "external": e, "baseline": base[name], "local": local, "action": action})
    conflicts = [r for r in rows if r["action"] == "conflict"]
    if conflicts and reply:
        for r in conflicts:
            granted.append({"at": now(), "item": r["item"], "external": r["external"], "local": r["local"],
                            "baseline": r["baseline"], "reply": reply.strip(), "by": "human"})
            r["action"] = "authorized"
        contract["publish_overrides"] = granted
        save(feature_root, contract)
        conflicts = []
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
    named = "、".join(f"{r['item']}（外部 {r['external'] or '不存在'}，基线 {r['baseline'] or '不存在'}）" for r in conflicts)
    return {"publishable": not conflicts, "items": rows, "conflict": bool(conflicts),
            "diff": diff, "open_topics": pending, "unverified": unverified,
            "action": ("需求系统上这几件与上次允许覆盖的版本不同：" + named + "，不直接覆盖。"
                       "把外部改动与这次的差异摆给人——要并进来的走 `/story update`；人确认仍覆盖时带 `--reply \"<原话>\"` 再跑"
                       if conflicts else
                       "把差异、未决议题与未验证项向人展示；这一单已有送审授权（交付选择选了送审，或明确要求 archive）就接着上传，"
                       "还没有授权先请人授权；三件都读回一致再 `story_flow.py archived` 登记")}


def readbacks(feature_root: Path, since: str | None) -> list[str]:
    """这一版三件的上传读回：都在 `since` 之后核过、状态是取到或相同、摘要等于本地当前件；返回不成立的原因。"""
    try:
        items = {i.get("name"): i for i in read_receipt(feature_root).get("items") or []}
    except FlowError as exc:
        return [str(exc)]
    since_at = datetime.fromisoformat(since) if since else None
    out = []
    for name, rel, _ in ITEMS:
        item = items.get(name) or {}
        local = short_digest((feature_root / Path(*rel)).read_bytes())
        checked = str(item.get("checkedAt") or "")
        if item.get("status") not in ("fetched", "same") or item.get("digest") != local:
            out.append(f"{name}：上传读回 {item.get('status', '没有记录')}（{item.get('note') or item.get('digest') or '—'}），本地当前是 {local}")
        elif not checked or (since_at and datetime.fromisoformat(checked.replace("Z", "+00:00")) < since_at):
            out.append(f"{name}：读回时间 {checked or '缺'} 早于这一版的登记，不是这一次上传的读回")
    return out


def cmd_restored(feature_root: Path) -> dict:
    """远端恢复之后：记下外部正文现在是哪一版，报告与本地的差异。**本地文件一个都不动**，归档登记与人签照旧。

    恢复只回退需求系统上的正文；两个附件的发布基线保持各自真实的版本。正文回退之后三件分属不同版本，
    下一次发布按逐件基线重新核。外部现在是哪一版以恢复后取材的回执为准。
    """
    _remote_only(feature_root)
    contract = require(load(feature_root))
    archived = contract.get("archived") or {}
    if not archived:
        raise FlowError("这张单还没归档过：远端恢复回退的是某一次归档的覆盖")
    item = _external(feature_root, archived.get("at"), ("AR-design.md",))["AR-design.md"]
    external = item.get("digest") if item.get("status") != "absent" else None
    local = short_digest((feature_root / Path(*STORY)).read_bytes())
    archived.update(external_digest=external, restored_at=now())
    contract["archived"] = archived
    save(feature_root, contract)
    log(f"已记下远端恢复：外部正文 {external or item.get('status')}，本地 Story {local}")
    return {"external": external, "local": local, "differs": external != local,
            "action": ("需求系统上的正文现在是恢复后的那一版，两个附件仍是最近一次发布的版本，三件分属不同版本：再次发布前走 `publish` 逐件核。"
                       if external != local else "需求系统上的正文与本地 Story 相同。")}


def publication_record(feature_root: Path, blueprint_ref: dict | None) -> dict:
    """三件都读回之后的发布记录：这一次发出去的 Story、Review 与设计附件的摘要和设计附件的原生引用，
    外部现在就是这一版；三件原样各留一份给下一次比差异。"""
    story, review, design = (feature_root / Path(*rel) for rel in (STORY, REVIEW, DESIGN_REVIEW))
    out = feature_root / Path(*PUBLISHED)
    out.mkdir(parents=True, exist_ok=True)
    for path in (story, review, design):
        shutil.copyfile(path, out / path.name)
    digest = short_digest(story.read_bytes())
    return {"at": now(), "story_digest": digest, "review_digest": short_digest(review.read_bytes()),
            "design_review_digest": short_digest(design.read_bytes()), "design_blueprint_ref": blueprint_ref,
            "external_digest": digest}


def cmd_archived(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已送审」：Story、Review 与设计附件三件都已上传并读回一致。归档动作由数据对接层执行，本命令只记状态。

    归档态是**流程状态**，落在流程契约里：装配脚本据它判定 `AR/review.md` 已归人所有，
    此后重新渲染时人工区逐字保留、机器区按当前决策件重算，评审人的批注与回稿都留在那份文件里。判据在契约里，
    与谁执行的归档无关——数据对接层由各部署环境自备实现，不随交付走。

    **登记自带门禁**：先重跑一次 `story-build check`，通过才记——归档时 story 可能又改过，
    成文态那次的校验不算数。登记不可逆，凭据只认校验过的产物。
    """
    contract = require(load(feature_root))
    if contract.get("status") != "story_written":
        raise FlowError(
            "还没登记成文态：归档的是 story，story 没过 check 就归档等于把未校验的产物送审。"
            "先跑 `story_flow.py story --feature <名>`")
    for rel in (STORY, REVIEW, DESIGN_REVIEW):
        if not (feature_root / Path(*rel)).is_file():
            raise FlowError(f"{'/'.join(rel)} 不存在：归档件不全，无可登记的归档态")

    checker = CORE_DIR / "story-build.mjs"
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：归档态登记要先重跑交付门，无法跳过")
    # 交付门而不是普通 check：走到这里 story 该已登记、依据未变，审查结论也该已经如实记下。
    # 普通 check 判不到那两样，用它登记归档态等于把「审没审过」这一格空着送审。
    proc = subprocess.run(
        [node, str(checker), "check", "--deliver", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        log((proc.stderr or proc.stdout).strip()[:2000])
        raise FlowError(
            "归档件未通过交付门（详见上方输出），拒绝登记归档态。"
            "已经传上去的那一版是不合格的：修好后重新归档，再登记")

    # 三件都要有这一版登记之后的上传读回，且读回的就是本地当前件
    missing = readbacks(feature_root, contract.get("story_written_at"))
    if missing:
        raise FlowError("三件的上传读回不全，拒绝登记归档态：" + "；".join(missing)
                        + "——上传由数据对接层的 archive 命令逐件写入并读回；失败的那件按 SKILL「归档」重新取材、publish 核对后再传")
    # 发布记录：外部现在就是这一版，下一次发布据它逐件判外部有没有被别人改过
    contract["archived"] = publication_record(feature_root, (contract.get("story_basis") or {}).get("blueprint_ref"))
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，重新渲染时人工区逐字保留")
    return {"archived": True, "at": contract["archived"]["at"]}
