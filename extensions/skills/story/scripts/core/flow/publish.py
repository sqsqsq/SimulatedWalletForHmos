"""对外发布（归档）前后的核对与记录：交付资格、三件的外部当前内容与各自的发布基线、发布记录。

上传与恢复由数据对接层执行（它的 archive 与 restore 命令），本层只做它们之前与之后确定的事：
发布前按当前人读交付门核资格，把差异、未决与未验证项摆给人；用最近一次取材的回执逐件核需求系统上的
Story 正文、Review 附件与设计参考附件还是不是我们上次知道的那一版——被别人改过就交人定，不直接覆盖；
发布与远端恢复之后记下外部现在是哪一版。本地单没有远端，这里的动作都不适用。
"""
from __future__ import annotations

import difflib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from flow.lifecycle import _not_the_product, _said
from flow.routing import live_materials, next_step, register_command
from flow.state import (CORE_DIR, DESIGN_REFERENCE, FlowError, PUBLISHED, REVIEW, STORY, load, log, now, require, save,
                        short_digest, system_requirement)

#: 最近一次取材的回执，与 update 读的是同一份
RECEIPT = ("AR", "story-src", "fetched.json")
#: 交付项：回执里的名字、本地来源、发布记录里的摘要键，按上传顺序；设计参考附件取蓝图原生评审投影的原字节。
#: Story 正文与 Review 附件是必需业务项；设计参考附件在对接层给出的系统要求（回执 `delivery_requirements.design_reference`）
#: 为真、或本单已有交付请求带上它（`--with-design-reference`）时选入。发布前核对通过时把这一次选定的集合记进取材回执的
#: `delivery`，对接层照它上传，归档登记与读回核对都读它，不另列一份
ITEMS = (("AR-design.md", STORY, "story_digest"),
         ("review.md", REVIEW, "review_digest"),
         ("design-review.md", DESIGN_REFERENCE, "design_review_digest"))
DESIGN = "design-review.md"


def _remote_only(feature_root: Path) -> None:
    if not system_requirement(feature_root.name):
        raise FlowError("本地单没有远端动作：交付终点就是仓内的 AR/story.md 与 AR/review.md，设计参考是同根蓝图的原生评审投影")


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
    """每件上次允许覆盖的那一版：发布过的取发布记录；正文首次发布取需求系统开发需求来源最新取得的那一版原件，附件首次发布为不存在。"""
    archived = contract.get("archived") or {}
    mine = [s for s in live_materials(feature_root).get("sources", [])
            if s.get("kind") == "system" and s.get("class") == "AR" and (s.get("origin") or {}).get("ticket") == feature_root.name]
    design = feature_root / mine[0]["versions"][-1]["original"]["path"] if mine else None
    first_body = short_digest(design.read_bytes()) if design is not None and design.is_file() else None
    return {"AR-design.md": archived.get("external_digest") or first_body,
            "review.md": archived.get("review_digest"),
            "design-review.md": archived.get("design_review_digest")}


def _selected(feature_root: Path, with_design: bool) -> tuple[tuple, bool]:
    """这一次要交付的项与系统是否要求设计参考附件：要求来自对接层写进取材回执的 `delivery_requirements`，缺了是对接层缺口，
    不按本地有没有投影、远端有没有旧附件去猜；系统要求时不能省掉。"""
    req = read_receipt(feature_root).get("delivery_requirements")
    if not isinstance(req, dict) or not isinstance(req.get("design_reference"), bool):
        raise FlowError("取材回执里没有对接层给出的交付要求（delivery_requirements.design_reference）：这是对接层的缺口，"
                        "按目标系统的合同补上后重新取材再发布；不按本地有没有设计参考来猜")
    names = {"AR-design.md", "review.md"} | ({DESIGN} if req["design_reference"] or with_design else set())
    return tuple(i for i in ITEMS if i[0] in names), req["design_reference"]


def cmd_publish(feature_root: Path, project_root: Path, reply: str | None, with_design: bool = False) -> dict:
    """发布前核一遍，**不上传**：资格、这一次交付的几件外部是不是我们知道的那一版、这次要交出去的差异、未决与未验证项。

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
    items, required = _selected(feature_root, with_design)
    external = _external(feature_root, contract.get("story_written_at"), tuple(name for name, _, _ in items))
    base = _baselines(feature_root, contract)
    granted = contract.get("publish_overrides") or []
    rows = []
    for name, rel, _ in items:
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
    if not conflicts:
        _record_delivery(feature_root, rows, {"design_reference_required": required, "design_reference_requested": with_design,
                                              "design_blueprint_ref": (contract.get("story_basis") or {}).get("blueprint_ref")})
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


def _record_delivery(feature_root: Path, rows: list[dict], basis: dict) -> None:
    """这一次的交付集合只在这里形成：每项的本地来源、此刻的摘要与预检结果写进取材回执的 `delivery`，
    对接层上传前逐项核本地没变；设计参考附件绑定当前蓝图的原生引用。"""
    path = feature_root / Path(*RECEIPT)
    receipt = read_receipt(feature_root)
    local = {name: "/".join(rel) for name, rel, _ in ITEMS}
    # 准备时刻取完整精度：对接层据它确认这份集合晚于本次取材（取材时刻到毫秒）
    receipt["delivery"] = {"prepared_at": datetime.now(timezone.utc).isoformat(), **basis,
                           "items": [{"name": r["item"], "local": local[r["item"]], "digest": r["local"],
                                      "external": r["external"], "baseline": r["baseline"], "action": r["action"]}
                                     for r in rows]}
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _delivered(receipt: dict) -> list[tuple]:
    """回执里这一次的交付集合（发布前核对记下的那一份），按 ITEMS 的顺序；没有、缺必需业务项，
    或系统要求设计参考附件（对接层给的交付要求）而集合里没有它时为空——必交项不只信集合自己。"""
    names = {i.get("name") for i in (receipt.get("delivery") or {}).get("items") or []}
    if not {"AR-design.md", "review.md"} <= names or (_required_design(receipt) and DESIGN not in names):
        return []
    return [i for i in ITEMS if i[0] in names]


def _required_design(receipt: dict) -> bool:
    return (receipt.get("delivery_requirements") or {}).get("design_reference") is True


def readbacks(feature_root: Path, since: str | None) -> list[str]:
    """这一次交付集合的上传读回：都在 `since` 之后核过、状态是取到或相同、摘要等于本地当前件；返回不成立的原因。"""
    try:
        receipt = read_receipt(feature_root)
    except FlowError as exc:
        return [str(exc)]
    delivered = _delivered(receipt)
    if not delivered:
        return ["取材回执里没有这一次的交付集合（或缺 Story 正文、Review 附件，或缺系统要求的设计参考附件）："
                "先做发布前核对，它记下交付哪几件"]
    items = {i.get("name"): i for i in receipt.get("items") or []}
    since_at = datetime.fromisoformat(since) if since else None
    out = []
    for name, rel, _ in delivered:
        item = items.get(name) or {}
        local = short_digest((feature_root / Path(*rel)).read_bytes())
        checked = str(item.get("checkedAt") or "")
        if item.get("status") not in ("fetched", "same") or item.get("digest") != local:
            out.append(f"{name}：上传读回 {item.get('status', '没有记录')}（{item.get('note') or item.get('digest') or '—'}），本地当前是 {local}")
        elif not checked or (since_at and datetime.fromisoformat(checked.replace("Z", "+00:00")) < since_at):
            out.append(f"{name}：读回时间 {checked or '缺'} 早于这一版的登记，不是这一次上传的读回")
    return out


def cmd_restored(feature_root: Path, prepare: bool = False, reply: str | None = None) -> dict:
    """远端正文恢复，分准备与登记两步；**本地文件一个都不动**，本地稿、人答、原生设计与附件的已确认版本照旧。

    顺序：fetch → `restored --prepare` → 对接层 restore → `restored`。
    - 准备：恢复目标是最近一次本扩展真实覆盖正文时留下的备份——对接层写正文时记在取材回执的 `body_write`，
      正文写了而附件失败、还没登记归档也算；没有它就取归档登记里的。按 B（那次覆盖之后已确认的外部正文）、
      L（恢复目标）与 E（刚取回的外部正文）判：E=L 只读回不写；E=B 可写；其余是之后别人改过，交人——普通恢复请求不等于同意覆盖它，
      人看过仍要覆盖时带 `--reply "<原话>"` 再准备，原话连同 E 与 L 记进契约，只授权这一次。可写时把准备项写进取材回执的 `restore`。
    - 登记：对接层读回晚于准备、状态成立、摘要等于目标，才记下外部正文现在是恢复后的那一版；否则恢复未确认。
    """
    _remote_only(feature_root)
    contract = require(load(feature_root))
    archived = contract.get("archived") or {}
    receipt = read_receipt(feature_root) if (feature_root / Path(*RECEIPT)).is_file() else {}
    write = receipt.get("body_write") or {}
    # 最近一次真实覆盖：回执里的那次若已登记进归档，B 用归档记的外部现状（恢复过会更新它），否则用那次写进去的内容
    if write.get("backup"):
        backup = write["backup"]
        b = archived.get("external_digest") if archived.get("body_backup") == backup else write.get("target_digest")
        since = (archived.get("restored_at") or archived.get("at")) if archived.get("body_backup") == backup else write.get("written_at")
    else:
        backup, b = archived.get("body_backup"), archived.get("external_digest")
        since = archived.get("restored_at") or archived.get("at")
    if not backup:
        raise FlowError("没有可核的正文覆盖：恢复回退的是某一次覆盖正文前留下的备份，取材回执与归档登记里都没有它——不能恢复")
    receipt = read_receipt(feature_root)
    if prepare:
        target = feature_root / backup
        if not target.is_file():
            raise FlowError(f"{backup} 不在：那次覆盖前的系统正文备份没了，不能恢复，也不拿别的旧来源顶替")
        local = short_digest(target.read_bytes())
        item = _external(feature_root, since, ("AR-design.md",))["AR-design.md"]
        e = item.get("digest") if item.get("status") != "absent" else None
        granted = contract.get("restore_overrides") or []
        action = ("skip" if e == local else "write" if e == b
                  else "authorized" if any(g.get("external") == e and g.get("local") == local for g in granted) else "conflict")
        if action == "conflict" and reply:
            granted.append({"at": now(), "item": "AR-design.md", "external": e, "local": local, "baseline": b,
                            "reply": reply.strip(), "by": "human"})
            contract["restore_overrides"] = granted
            save(feature_root, contract)
            action = "authorized"
        row = {"name": "AR-design.md", "local": backup, "digest": local, "external": e, "baseline": b, "action": action}
        if action == "conflict":
            return {"restorable": False, "restore": row,
                    "action": f"需求系统上的正文（{e or '不存在'}）既不是上次覆盖之后的那一版（{b}），也不是恢复目标（{local}）："
                              "之后有人改过，不直接覆盖。把差异摆给人；人看过仍要恢复时带 `--reply \"<原话>\"` 再准备"}
        receipt["restore"] = {"prepared_at": now(), **row}
        (feature_root / Path(*RECEIPT)).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"restorable": True, "restore": row,
                "action": "已准备：按恢复授权调对接层 restore，它只动正文并读回；读回成立后再跑 `story_flow.py restored` 登记"}
    r = receipt.get("restore") or {}
    item = {i.get("name"): i for i in receipt.get("items") or []}.get("AR-design.md") or {}
    checked = str(item.get("checkedAt") or "")
    ok = (r.get("digest") and item.get("status") in ("fetched", "same") and item.get("digest") == r["digest"] and checked
          and datetime.fromisoformat(checked.replace("Z", "+00:00")) >= datetime.fromisoformat(r["prepared_at"]))
    if not ok:
        raise FlowError("恢复未确认：取材回执里没有晚于这次恢复准备、摘要等于恢复目标的正文读回"
                        f"（正文 {item.get('status', '没有记录')}：{item.get('note') or item.get('digest') or '—'}）。"
                        "对接层报写入失败或读回不一致时远端可能已被写过：重新 fetch、`restored --prepare` 核清现状再续")
    local = short_digest((feature_root / Path(*STORY)).read_bytes())
    if archived.get("body_backup") == r.get("local"):
        archived.update(external_digest=r["digest"], restored_at=now())
        contract["archived"] = archived
    else:                     # 恢复的是还没登记进归档的那次覆盖：外部现状记在恢复记录里，不冒充归档
        contract["restored"] = {"at": now(), "external_digest": r["digest"], "backup": r.get("local")}
    save(feature_root, contract)
    log(f"已记下远端恢复：外部正文 {r['digest']}，本地 Story {local}")
    return {"external": r["digest"], "local": local, "differs": r["digest"] != local,
            "action": ("需求系统上的正文现在是恢复后的那一版，附件仍是各自最近一次交付的版本：再次发布前走 `publish` 逐件核。"
                       if r["digest"] != local else "需求系统上的正文与本地 Story 相同。")}


def publication_record(feature_root: Path, blueprint_ref: dict | None, previous: dict | None = None) -> dict:
    """这一次交付集合都读回之后的发布记录：交了哪几件、各自的摘要，外部现在就是这一版；交了的原样各留一份给下一次比差异
    （按需求系统上的名字存）。设计参考附件这次没交时，保留上一次的基线与原生引用，标明它不是这一次的新版。
    最近一次真实覆盖正文时对接层留下的备份（回执的 `body_write`，取材与发布前核对都保留它）记下来，远端恢复据它取目标；
    这一次续传时正文已是本地这一份、没再覆盖，也是那一次的备份，不回退到更早一次归档的。"""
    previous = previous or {}
    receipt = read_receipt(feature_root)
    delivered = _delivered(receipt)
    names = [name for name, _, _ in delivered]
    out = feature_root / Path(*PUBLISHED)
    out.mkdir(parents=True, exist_ok=True)
    copies = {"AR-design.md": "story.md", "review.md": "review.md", DESIGN: "design-review.md"}
    for name, rel, _ in delivered:
        shutil.copyfile(feature_root / Path(*rel), out / copies[name])
    digest = short_digest((feature_root / Path(*STORY)).read_bytes())
    design = DESIGN in names
    return {"at": now(), "items": names, "story_digest": digest,
            "review_digest": short_digest((feature_root / Path(*REVIEW)).read_bytes()),
            "design_review_digest": short_digest((feature_root / Path(*DESIGN_REFERENCE)).read_bytes()) if design
            else previous.get("design_review_digest"),
            "design_blueprint_ref": blueprint_ref if design else previous.get("design_blueprint_ref"),
            **({} if design or not previous.get("design_review_digest") else {"design_reference": "上一次交付的版本，这一次没有更新"}),
            "body_backup": (receipt.get("body_write") or {}).get("backup") or previous.get("body_backup"),
            "external_digest": digest}


def cmd_archived(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已送审」：这一次交付集合（Story、Review，及系统要求或已请求的设计参考附件）都已上传并读回一致。
    归档动作由数据对接层执行，本命令只记状态。

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
    for rel in (STORY, REVIEW):     # 必需业务项；这一次实际交了哪几件由读回核对按交付集合核
        if not (feature_root / Path(*rel)).is_file():
            raise FlowError(f"{'/'.join(rel)} 不存在：归档件不全，无可登记的归档态")

    checker = CORE_DIR / "story-build.mjs"
    # 走到这里需求系统那边已经写入并读回：失败只说本地登记没完成，下一步只补登记，不重新上传
    again = (f"只补登记：`{register_command(feature_root, 'archived')}`；需求系统里已上传的那一份不受影响，不要重新上传")
    node = shutil.which("node")
    if node is None:
        raise FlowError(f"找不到 node，交付门没跑，归档态没有登记。这是运行环境问题：装好 node 后{again}")
    # 交付门而不是普通 check：走到这里 story 该已登记、依据未变，审查结论也该已经如实记下。
    # 普通 check 判不到那两样，用它登记归档态等于把「审没审过」这一格空着送审。
    try:
        proc = subprocess.run(
            [node, str(checker), "check", "--deliver", "--feature", feature_root.name,
             "--project-root", str(project_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise FlowError(f"交付门没能启动（{exc}），归档态没有登记。这是运行环境问题：环境恢复后{again}") from exc
    if proc.returncode == 1:
        raise FlowError(
            "交付门这次没通过，归档态没有登记。它核的是本地工作区当前的 Story、Review、设计参考与审查结果，"
            f"不是需求系统里那一份；按下面的输出处理它点名的问题后{again}。本地业务稿确实要改的，走 `/story update`。"
            "交付门原始输出：\n" + _said(proc))
    if proc.returncode != 0:
        raise FlowError(f"交付门没有正常结束（退出码 {proc.returncode}），归档态没有登记。"
                        f"这不是归档件的问题：{_not_the_product(proc.returncode)}，修好后{again}。原始输出：\n"
                        + _said(proc))

    # 这一次交付的每一件都要有这一版登记之后的上传读回，且读回的就是本地当前件
    missing = readbacks(feature_root, contract.get("story_written_at"))
    if missing:
        raise FlowError("交付件的上传读回不全，拒绝登记归档态：" + "；".join(missing)
                        + "——上传由数据对接层的 archive 命令逐件写入并读回；失败的那件按 SKILL「归档」重新取材、publish 核对后再传")
    # 发布记录：外部现在就是这一版，下一次发布据它逐件判外部有没有被别人改过
    contract["archived"] = publication_record(feature_root, (contract.get("story_basis") or {}).get("blueprint_ref"),
                                              contract.get("archived"))
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，重新渲染时人工区逐字保留")
    # 归档成立不回滚；本轮还有没做完的工作同源说出来，算不出来不遮住已成功的登记
    try:
        step, action = next_step(feature_root, contract, live_materials(feature_root))
    except FlowError as exc:
        step, action = "status", f"归档态已登记；下一步暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取"
    return {"archived": True, "at": contract["archived"]["at"], "next": step, "action": action}
