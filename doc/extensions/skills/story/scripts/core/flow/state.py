"""流程契约的持久化与最基础的取用：路径与关卡常量、读写、轮次条目。

这一层不作判断，只回答「契约在哪、现在是什么、写回去」。其余 flow 模块都从这里取
常量与读写函数，它自己不导入任何 flow 模块——方向单一，才不会出现「路由要读契约、
读契约又要问路由」的环。

本 Skill 内的合同、模板与公共 CLI 一律从 `SKILL_ROOT` 往下找：每个模块各数一次
目录层数的话，文件往下挪一层就会漏改一处。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

#: 本 Skill 的根目录（`skills/story`）。合同、模板与公共 CLI 都从这一处往下找。
SKILL_ROOT = Path(__file__).resolve().parents[3]
#: 正式 CLI 与流程模块所在目录，`story-build.mjs` 就在这里。
CORE_DIR = SKILL_ROOT / "scripts" / "core"


SCHEMA = 3
CONTRACT = ("AR", "story-src", "story-flow.json")
ANALYSIS = ("AR", "story-src", "init-analysis.md")


DESIGN = ("AR", "design.md")
# S4 提取稿的落点。**输入与输出分开**：`AR/design.md` 是上游给进来的输入件，
# 模型把提取结果写在这里，由 `complete` 提交上去。写在同一个文件里的话，
# 材料指纹会因为自己的输出而变，流程被自己推回未定状态。
DESIGN_DRAFT = ("AR", "story-src", "design-draft.md")
# 到了这两步就意味着**本轮范围已定**，S4 可以做。候选稿在不在由 `complete` 自己核，
# 不借道 next_step——候选可以由 `--from` 指到别处，而 next_step 只认默认落点。
S4_STEPS = ("generate_design", "run_complete")
# 成文态登记时随稿冻结的依据：story 定稿了，它据以成文的决策登记与写作设计也就定稿了。
# 登记之后再改它们，story.md 冻了而依据换了一批；`reopen` 撤销登记之后才可以改。
STORY_SRC_FROZEN = (
    "decisions.json",
    "story-template.md",
)
# 三级关卡，**每级只问一件事**：材料 → 范围怎么定 → 承载哪一份。
#
# 分三级而不是并成一问：材料与范围是两个维度，挤在一级人得同时权衡两件不相干的事。
# 而它们本有先后——材料不全时范围判断本身就不可靠，在一个还会变的范围上讨论怎么切，
# 讨论了也白讨论。
#
# `meeting` 不是第四级：会议判断里要问人的话题逐条裁决，与第一级在同一轮停等里摆，不新增停等点。
GATES = ("material_scope", "scope_decision", "split_carrier", "meeting")
#: 章节合同。第一级的选项集登记在它的 `gates.material_scope.options` 里，流程侧与
#: `flow/check.mjs` 都从那里读——两边各存一份字面的话，只改一处，`decide` 写进契约的
#: 选择会在阶段门禁上被判非法。
STORY_CONTRACT = SKILL_ROOT / "contracts" / "story-chapters.json"
# 第二级里唯一固定的一项：按当前范围整体承载。其余项是具名维度的切法。
CARRY_ALL = "carry_all"
# 本 AR 当前范围是**哪里定下来的**，按强度排序：
#   user_stated —— 关卡上由人定的（他说了本次做多少、怎么切）。最强：那是决定不是推断。
#   title / design_prefill / sr_related —— 上游材料给了范围，强度依次递减；
#   full —— 谁都没给，只能先按部件全量算。这个范围是**待确认**的，评审者有权推翻。
# 来源本身必须落进契约：下游据它判断这个范围有多可靠。
SCOPE_SOURCES = ("user_stated", "title", "design_prefill", "sr_related", "full")


class FlowError(Exception):
    """可预期的失败：带可执行的补救动作，直接呈给人。退出码 1，不写盘。"""


def log(msg: str) -> None:
    print(f"[story_flow] {msg}", file=sys.stderr)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ledger_digest(path: Path) -> str | None:
    """台账指纹：**换行差异不算改动**（同一份文件在两台机器上可能行尾不同）。

    这一个要与 `story-build.mjs` 的 `digestOf` 逐字节同口径——登记由本脚本写，
    核对由那边做，两边算法差一点就会变成「每次都说台账被改过」。
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def load(feature_root: Path) -> dict | None:
    path = feature_root / Path(*CONTRACT)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError as exc:
        raise FlowError(
            f"AR/story-src/story-flow.json 不是合法 JSON（{exc}）：它应当只由本脚本写入。"
            "若曾手工编辑，请修正语法或删除后回到 S2 重新登记轮次") from exc


def save(feature_root: Path, contract: dict) -> None:
    path = feature_root / Path(*CONTRACT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(contract: dict | None) -> dict:
    if contract is None or not contract.get("rounds"):
        raise FlowError("契约尚无轮次：请先在初析完成后执行 `story_flow.py round`")
    return contract


def after_complete(contract: dict) -> bool:
    """流程收口了没有——**收口那一刻及其之后都算**。

    `complete` 之后还有 `story_written` 与归档；材料在这些状态下再变，同样不该开新轮。
    """
    return (contract.get("status") in ("complete", "story_written")
            or bool(contract.get("archived")))


def round_gates(contract: dict) -> list[dict]:
    """**当前轮**的关卡记录。

    位置一律按当前轮判，不看历史轮次展平后的末条：一轮 = 一次「初析 → 关卡」循环，
    补料后进入新一轮，上一轮选过什么就不再代表现在在哪。展平了判会出两种错——
    第一轮选过 proceed、补料进第二轮后能直接收口；拆分定案后补料重析，想重新拆
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
