"""流程契约的持久化与最基础的取用：路径与关卡常量、读写、轮次条目。

这一层不作判断，只回答「契约在哪、现在是什么、写回去」。其余 flow 模块都从这里取
常量与读写函数，它自己不导入任何 flow 模块——方向单一，才不会出现「路由要读契约、
读契约又要问路由」的环。

本 Skill 内的合同、模板与公共 CLI 一律从 `SKILL_ROOT` 往下找：每个模块各数一次
目录层数的话，文件往下挪一层就会漏改一处。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

#: 本 Skill 的根目录（`skills/story`）。合同、模板与公共 CLI 都从这一处往下找。
SKILL_ROOT = Path(__file__).resolve().parents[3]
#: 正式 CLI 与流程模块所在目录，`story-build.mjs` 就在这里。
CORE_DIR = SKILL_ROOT / "scripts" / "core"


CONTRACT = ("AR", "story-src", "story-flow.json")


def system_requirement(feature: str) -> bool:
    """本项目只有 AR 开头的需求挂在需求系统上，其余（问题单、自定义名、local 开头…）都是本地需求。

    来源由编号决定，与 `story/context.mjs::isSystemRequirement` 同一规则。
    """
    return str(feature).startswith("AR")


#: 需求的蓝图与需求同根：蓝图标识就是需求标识，原生 canonical 蓝图在需求目录的 `blueprint/` 下
BLUEPRINT = ("blueprint", "component-blueprint.yaml")
# 成文登记时记指纹的文件（相对需求目录）：story、review 与它据以成文的决策登记、写作设计；设计依据（蓝图原生引用与摘要）另记在 story_basis。
# 登记之后任一份再改，`story-build check` 报「登记之后改过」，重跑 `story` 重新登记。
STORY_REGISTERED = (
    "AR/story.md",
    "AR/review.md",
    "AR/story-src/decisions.json",
    "AR/story-src/story-template.md",
)
#: 章节合同。第一级的选项集登记在它的 `gates.material_scope.options` 里，流程侧与
#: `flow/check.mjs` 都从那里读——两边各存一份字面的话，只改一处，`decide` 写进契约的
#: 选择会在阶段门禁上被判非法。
STORY_CONTRACT = SKILL_ROOT / "contracts" / "story-chapters.json"


class FlowError(Exception):
    """可预期的失败：带可执行的补救动作，直接呈给人。退出码 1，不写盘。"""


def contract_flow() -> dict:
    """流程契约的常量，真源是章节合同的 `flow`；门禁 `flow/check.mjs` 读同一处。

    读不出来要出声：schema、关卡名、整体承载键任何一个退化成默认值，写进契约的记录
    都会在阶段门禁上被判非法，而坏掉的是合同的读取路径。
    """
    try:
        data = json.loads(STORY_CONTRACT.read_text(encoding="utf-8").lstrip("\ufeff"))
        flow = data["flow"]
        return {"schema": int(flow["schema"]), "gates": tuple(str(g) for g in flow["gates"]),
                "carry_all": str(flow["carry_all"])}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FlowError(
            f"{STORY_CONTRACT.name} 的 flow 读不出来（{exc}）：契约 schema、关卡名与整体承载键登记在那里"
        ) from exc


_FLOW = contract_flow()
SCHEMA = _FLOW["schema"]
# 三级关卡，**每级只问一件事**：材料 → 范围怎么定 → 承载哪一份。
#
# 分三级而不是并成一问：材料与范围是两个维度，挤在一级人得同时权衡两件不相干的事。
# 而它们本有先后——材料不全时范围判断本身就不可靠，在一个还会变的范围上讨论怎么切，
# 讨论了也白讨论。
#
# `meeting` 是有条件的一处停等，不是第四级：材料确认之后、需求分析之前，会议判断里有要问人的话题
# 才停一次，逐条裁决；没有会议或没有要问的话题就不停。会议本身是需求材料的一种，随材料一起交、一起导入。
GATES = _FLOW["gates"]
# 第二级里唯一固定的一项：按当前范围整体承载。其余项是具名维度的切法。
CARRY_ALL = _FLOW["carry_all"]


def log(msg: str) -> None:
    print(f"[story_flow] {msg}", file=sys.stderr)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str | None:
    """登记指纹：原始字节的完整 SHA-256，读不到为 None。

    与 `story/context.mjs` 的 `digestOf` 同口径——登记由本脚本写，核对两边都做。
    Review 的人工区改了一个字也算改了：人读件变了，审查与登记说的就不是这一份。
    """
    if not path.is_file():
        return None
    return sha256(path.read_bytes()).hexdigest()


#: 上次发布出去的 Story、Review 与设计参考附件原样留在这里（相对需求目录）：下一次发布前据它给出差异
PUBLISHED = (".backups", "published")


def short_digest(data: bytes) -> str:
    """与对接层回执同一口径的摘要：`sha256:` 加前 16 位，比外部正文是哪一版用。"""
    return "sha256:" + sha256(data).hexdigest()[:16]


#: 契约自身的内容摘要。每次写入由本模块重算；读到对不上说明有人绕过命令改过文件。
DIGEST_KEY = "digest"
#: 本次命令里读到的手改提示。入口把它带进输出，命令本身照常执行。
TAMPER_NOTES: list[str] = []


def contract_digest(contract: dict) -> str:
    body = {k: v for k, v in contract.items() if k != DIGEST_KEY}
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def load(feature_root: Path) -> dict | None:
    path = feature_root / Path(*CONTRACT)
    if not path.is_file():
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError as exc:
        raise FlowError(
            f"AR/story-src/story-flow.json 不是合法 JSON（{exc}）：它只由本脚本写入。"
            "修正语法后跑 `story_flow.py status` 核对当前位置") from exc
    if contract.get("schema") != SCHEMA:
        raise FlowError(
            f"不是当前版本的流程契约（schema {contract.get('schema', '缺失')}，当前 {SCHEMA}）："
            "本版只接续本版新初始化的需求，不迁移、不改写这个目录；要在本版做就另建一个新需求")
    if contract.get(DIGEST_KEY) != contract_digest(contract):
        note = ("流程契约被手改过（内容摘要对不上），本次命令照常执行："
                "跑 `story_flow.py status` 核对当前位置；手改里要保留的决定，"
                "用对应命令重新记录（decide / round / reopen），下一次写入会重算摘要")
        if note not in TAMPER_NOTES:
            TAMPER_NOTES.append(note)
            log(note)
    return contract


def save(feature_root: Path, contract: dict) -> None:
    path = feature_root / Path(*CONTRACT)
    path.parent.mkdir(parents=True, exist_ok=True)
    contract[DIGEST_KEY] = contract_digest(contract)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_of(contract: dict | None) -> str:
    """流程现在处在哪一段——**各命令判位置只问这一处**。

    返回 `none`（没有轮次）、`gathering`（成文登记前：盘点、关卡、设计与成文）、`story_written`、
    `archived`（已登记且归档过）、`update_inputs`（update 输入阶段）、`update_open`（update 这一轮开着）。
    update 的两段优先：这一轮沿用已定范围，新材料登记进当前轮。归档是 `story_written` 上的标记，不是另一档状态。
    设计开没开始不存在契约里，由 `closed` 按原生蓝图派生。
    """
    if contract is None or not contract.get("rounds"):
        return "none"
    update = contract.get("update") or {}
    if update.get("stage") == "inputs":
        return "update_inputs"
    if update.get("open"):
        return "update_open"
    if contract.get("status") == "story_written":
        return "archived" if contract.get("archived") else "story_written"
    return "gathering"


def in_update(contract: dict | None) -> bool:
    return stage_of(contract) in ("update_inputs", "update_open")


def require(contract: dict | None) -> dict:
    if contract is None or not contract.get("rounds"):
        raise FlowError("契约尚无轮次：请先在初析完成后执行 `story_flow.py round`")
    return contract


def settled_this_round(contract: dict) -> bool:
    """拆分是不是**在当前轮**定的案。

    `split` 是契约级字段（只认最终那一份），而拆分决策属于某一轮——
    两者用 `settled_round` 挂钩，重新初析后同一份 split 就不再算数。
    """
    split = contract.get("split") or {}
    return (split.get("decided") == "split"
            and split.get("settled_round") == contract["rounds"][-1].get("round"))


def scope_settled(contract: dict) -> bool:
    """本轮范围定下来没有：范围关卡选了整体承载，或本轮切分已定案。只看当前轮的人签——范围关卡只在它之前的
    材料与会议都走完时才问得出来（重开范围的那一轮沿用上一轮的材料确认）。"""
    if not contract.get("rounds"):
        return False
    decision = last_gate(round_gates(contract), "scope_decision")
    if not decision or decision.get("outcome") != "accepted":
        return False
    return decision.get("chosen") == CARRY_ALL or settled_this_round(contract)


def blueprint_exists(feature_root: Path) -> bool:
    """需求的 canonical 蓝图在不在（同根 `blueprint/`）——设计真实开始的原生对象。"""
    return (feature_root / Path(*BLUEPRINT)).is_file()


def closed(feature_root: Path, contract: dict) -> bool:
    """范围收口、设计已经开始没有：成文已登记，或本轮范围已定且原生蓝图已经建立。

    收口之后材料再变只登记进本轮、不开新轮；要重拍范围显式 `reopen`。设计还没开始时范围仍可随材料重新盘点。
    归档过的单 `reopen` 之后回到范围关卡，与没归档过的一样。
    """
    return contract.get("status") == "story_written" or (scope_settled(contract) and blueprint_exists(feature_root))


def registration_drift(feature_root: Path, contract: dict) -> list[str]:
    """已登记的成文之后又变了什么：story 与它的决策登记、写作设计的指纹。没登记过返回空。

    与 `story/context.mjs` 的 `ledgerDigestProblems` 是同一件事的两处读者：
    流程路由与 update 收口在这里问，成文检查在那边问，指纹都由 `file_sha256` 口径算。
    蓝图、采用来源与知识换没换要读原生对象，由路由经 `story-build basis` 另问。
    """
    if contract.get("status") != "story_written":
        return []
    basis = contract.get("story_basis")
    if not isinstance(basis, dict) or not isinstance(basis.get("files"), dict):
        raise FlowError("流程契约记着已成文登记，却没有成文依据 story_basis：契约不完整。"
                        "跑 `story_flow.py story` 按当前内容重新登记")
    return [rel for rel in STORY_REGISTERED
            if basis["files"].get(rel) != file_sha256(feature_root / Path(*rel.split("/")))]


def round_gates(contract: dict) -> list[dict]:
    """**当前轮**的关卡记录。

    位置一律按当前轮判，不看历史轮次展平后的末条：一轮 = 一次「初析 → 关卡」循环，
    补料后进入新一轮，上一轮选过什么就不再代表现在在哪。展平了判会出两种错——
    上一轮的表态替补料后的新一轮收口；拆分定案后补料重析，想重新拆
    却被告知「已定案」。
    """
    return contract["rounds"][-1].get("gates", []) if contract.get("rounds") else []


def last_gate(gates: list[dict], name: str) -> dict | None:
    for g in reversed(gates):
        if g.get("gate") == name:
            return g
    return None


STORY = ("AR", "story.md")
REVIEW = ("AR", "review.md")
#: 设计参考：与需求同根的蓝图原生评审投影。系统送审时按原字节作设计参考附件上传，本地不另存副本
DESIGN_REFERENCE = ("blueprint", "component-blueprint.review.md")


def issue_zone(feature_root: Path, issue: str) -> tuple[str, str]:
    """评审记录里这条议题机器区的摘要与正文：人回话时看到的就是它，记下来作问法的等价物。"""
    review = feature_root / "AR" / "review.md"
    text = review.read_text(encoding="utf-8") if review.is_file() else ""
    # 机器区：标记行之后到人工区填写位（行首「评审结论：」）或本议题的决定锚点
    hit = re.search(rf"<!-- story-build:begin 议题 {re.escape(issue)} · .*?sha256:([0-9a-f]+) -->\n?(.*?)"
                    rf"(?=^评审结论：|<!-- decision: {re.escape(issue)} -->|\Z)", text, re.S | re.M)
    if not hit:
        raise FlowError(f"评审记录里没有议题 {issue}：人定的事先登记成议题、build 进评审记录，"
                        "人看过那一条再回话")
    return hit.group(1), hit.group(2).strip()


def sync_answers(feature_root: Path, what: str) -> str | None:
    """收口、撤回或重开改变了哪些人答当前有效：同步导出。
    已经写盘的那一步照样成立；导出没完成时返回要说的话，交调用方带出，不当作这一步没发生。"""
    from materials import registry  # noqa: PLC0415 —— 人答导出由材料索引刷新承担
    try:
        registry.refresh(feature_root)
    except registry.MaterialError as exc:
        return (f"当前有效人答没能同步导出（{exc}）：排除问题后跑 `story_flow.py round` 重试派生，"
                f"{what}已经生效，不要重做")
    return None
