"""story_flow.py — init→spec 流程契约（`AR/story-flow.json`）的**唯一写入者**。

契约记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项，
事后可查、可推翻。

契约同时是这条流程的**状态机**：`status` 子命令读它就能回答「现在走到哪、下一步干什么」。
所以 skill 正文不必维护成篇的分支判定文本——位置由数据回答，不由记忆回答。

契约里绝大多数内容是机械事实——文件哈希、时间戳、轮次边界、收件箱里还有没有没导过的料。
这类事实靠记忆复现就会失真，所以一律由脚本自取。

分工因此是：**判断留 AI，执行归脚本**（与 `import_sources.py` 的归类件同一条边界）。
AI 只传它真正知道而脚本无从得知的东西——人选了哪一项、依据是什么；其余一律脚本自己取。
本轮导入了什么也在「脚本自己取」这一侧：`import_sources.py` 成功后把回执落在
`AR/.last-import.json`，`round` 读它并在登记后销毁——回执是一次性的。

    python story_flow.py init     --feature <AR>
    python story_flow.py round    --feature <AR>
    python story_flow.py decide   --feature <AR> --gate <g> --chosen <c> --by <b> --basis <t>
    python story_flow.py status   --feature <AR>
    python story_flow.py complete --feature <AR>
    python story_flow.py archived --feature <AR>

`init` 与 `archived` 不写轮次，写的是**工作区骨架**与**归档态**：这两件事的执行方
（数据对接层 story.js）不随交付走，各部署环境自备实现，所以判据不能挂在它落的文件上。

公共参数：`--project-root <abs>`。stdout 单行 JSON；人类可读日志走 stderr。
**参数只放标量**：JSON 全是引号，而任何 shell 都要对参数再解析一遍——同一条命令
bash 下原样送达、Windows PowerShell 下双引号被吞。结构化数据一律走文件：
选项集走 `AR/story-src/.gate-options.json`、本 AR 定位走 `AR/story-src/.positioning.json`、
拆分份表走 `AR/story-src/.split-parts.json`，脚本读后即销毁（一次性，同导入回执）。

退出码（`decide` 的退出码回答「能不能按这个选择往下走」）：

    0  成功
    1  用法/参数/前置不满足——**没有任何写入**
    2  仅 decide：选择已记录，但校验不通过，**不得前进**（如选了补料却没放料）

核心不变量：

- **一轮 = 一次初析**。轮次边界由 `AR/init-analysis.md` 的 sha256 判定：哈希没变就不是
  新一轮（幂等），假轮次因此不可能被造出来；
- **一次关卡交互 = 一条 gate 记录**，含未生效的那次。校验与记录是同一次调用，
  所以不存在"忘了记"；
- **摆过的选项与选中的那项一起记**。只记 `chosen` 的话，「看过选项后选了不拆」与
  「压根没生成拆分选项」在事后完全同形，后者可以伪装成前者通过全部门禁。
  因此 `options` 必填，且 `chosen` 必须是其中一项：**选的只能是摆出来的**；
- 时间戳一律由本脚本取当下，调用方碰不到该字段。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

SCHEMA = 3
CONTRACT = ("AR", "story-flow.json")
ANALYSIS = ("AR", "init-analysis.md")
# import_sources.py 落下的导入回执（一次性，登记后销毁）
RECEIPT = ("AR", ".last-import.json")
# 拆分份表侧车：AI 写、脚本读，登记进契约后销毁（同导入回执，一次性）
SPLIT_PARTS = ("AR", "story-src", ".split-parts.json")
# 选项集侧车：本次关卡摆给人的全部选项。每条 gate 一份，读后销毁
GATE_OPTIONS = ("AR", "story-src", ".gate-options.json")
# 本 AR 定位侧车：三源核对后收敛出的当前范围结论。round 消费
POSITIONING = ("AR", "story-src", ".positioning.json")
# 范围定法选项集侧车：需求分析（S2b）产出的**全部**可选项。round 消费进契约，
# 第二级关卡此后只能从契约里取——见 read_scope_options 的注释
SCOPE_OPTIONS = ("AR", "story-src", ".scope-options.json")
DESIGN = ("AR", "design.md")
SOURCES = ("RR/prd.md", "SR/design.md", "AR/design.md", "AR/upstream.md")
# 三级关卡，**每级只问一件事**：材料够不够 → 范围怎么定 → 承载哪一份。
#
# 分三级而不是并成一问：材料与范围是两个维度，挤在一级人得同时权衡两件不相干的事。
# 而它们本有先后——材料不全时范围判断本身就不可靠，在一个还会变的范围上讨论怎么切，
# 讨论了也白讨论。
GATES = ("material_scope", "scope_decision", "split_carrier")
# 第一级的值域是闭合的；第二、三级的值域由本次选项集自己定义（维度名、份序号），
# 统一由「chosen 必须在 options 里」把关，不为每级各写一套枚举。
MATERIAL_CHOICES = ("supplement", "confirm_scope")
# 第二级里唯一固定的一项：按当前范围整体承载。其余项是具名维度的切法。
CARRY_ALL = "carry_all"
ACTORS = ("human", "ai")
# 本 AR 当前范围是**哪里定下来的**，按强度排序：
#   user_stated —— 关卡上由人定的（他说了本次做多少、怎么切）。最强：那是决定不是推断。
#   title / design_prefill / sr_related —— 上游材料给了范围，强度依次递减；
#   full —— 谁都没给，只能先按部件全量算。这个范围是**待确认**的，评审者有权推翻。
# 来源本身必须落进契约：下游据它判断这个范围有多可靠。
SCOPE_SOURCES = ("user_stated", "title", "design_prefill", "sr_related", "full")
# 收件箱里不算材料的：目录自解释用的说明书。点文件是控制件（如 AI 写的归类件），同样不算
SKIP_INBOX = {"readme.md"}


class FlowError(Exception):
    """可预期的失败：带可执行的补救动作，直接呈给人。退出码 1，不写盘。"""


def log(msg: str) -> None:
    print(f"[story_flow] {msg}", file=sys.stderr)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def features_dir(project_root: Path) -> str:
    try:
        cfg = json.loads((project_root / "framework.config.json").read_text(encoding="utf-8"))
        value = (cfg.get("paths") or {}).get("features_dir")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except (OSError, ValueError):
        pass
    return "doc/features"


def digest(path: Path) -> str | None:
    """不存在的源记 null 而非省略——「没有」和「没查」是两件事。"""
    if not path.is_file():
        return None
    return "sha256:" + sha256(path.read_bytes()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 契约读写

def load(feature_root: Path) -> dict | None:
    path = feature_root / Path(*CONTRACT)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError as exc:
        raise FlowError(
            f"AR/story-flow.json 不是合法 JSON（{exc}）：它应当只由本脚本写入。"
            "若曾手工编辑，请修正语法或删除后回到 S2 重新登记轮次") from exc


def save(feature_root: Path, contract: dict) -> None:
    path = feature_root / Path(*CONTRACT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(contract: dict | None) -> dict:
    if contract is None or not contract.get("rounds"):
        raise FlowError("契约尚无轮次：请先在初析完成后执行 `story_flow.py round`")
    return contract


# ---------------------------------------------------------------------------
# round：登记一轮初析

def read_receipt(feature_root: Path) -> list[str]:
    """本轮导入了什么：读 import_sources 落下的回执。没有回执 = 本轮没导入。"""
    path = feature_root / Path(*RECEIPT)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise FlowError(f"{'/'.join(RECEIPT)} 不是合法 JSON：{exc}") from exc
    return list(payload.get("converted") or [])


def consume_receipt(feature_root: Path) -> None:
    """回执是一次性的：登记进契约后即销毁，否则下一轮会把它当成本轮的导入再读一遍。

    只在契约落盘成功之后调用——先删后写会在写失败时丢掉这份事实。
    """
    (feature_root / Path(*RECEIPT)).unlink(missing_ok=True)


def consume_sidecar(feature_root: Path, parts: tuple[str, ...]) -> None:
    """侧车同回执，一次性：登记进契约后销毁，否则下一次调用会把陈旧内容当成本次的输入。"""
    (feature_root / Path(*parts)).unlink(missing_ok=True)


def read_sidecar(feature_root: Path, parts: tuple[str, ...]) -> object | None:
    """读一份一次性侧车。不存在返回 None——「没写」与「写了空的」是两件事。"""
    path = feature_root / Path(*parts)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise FlowError(f"{path.name} 不是合法 JSON：{exc}") from exc


def read_positioning(feature_root: Path) -> dict | None:
    """读本 AR 定位侧车：初析三源核对后收敛出的「本 AR 当前范围」。

    这是整条拆分链的**判定对象**——不先把它定下来，后面的三类信号就没有施加对象，
    只能默默取上游全量：初析即使识别出「无预填说明」，若没有一步把该识别结果变成范围结论，
    SR 全量就会被当成本 AR 范围。

    脚本只存 AI「它无从得知」的判断（范围从哪来、是什么、同 SR 还有哪些 AR），
    不代它判断——与 `import_sources.py` 的归类件同一条分工边界。
    """
    payload = read_sidecar(feature_root, POSITIONING)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise FlowError(f"{POSITIONING[-1]} 须是对象：含 scope_source / scope_text / sr_related_ars")

    source = str(payload.get("scope_source") or "").strip()
    if source not in SCOPE_SOURCES:
        raise FlowError(
            f"scope_source 须为 {' / '.join(SCOPE_SOURCES)} 之一，实为「{source}」"
            "——范围是用户直接说的、从 AR 标题读到的、从 design.md 预填读到的、"
            "从 SR 关联清单推出来的，还是都没有而取了部件全量，"
            "下游据此判断这个范围可不可靠")
    scope_text = str(payload.get("scope_text") or "").strip()
    if not scope_text:
        raise FlowError(
            "scope_text 不能为空：本 AR 当前范围必须写成一句话。"
            "取全量时同样要写出全量是什么——「全部」有多大，评审者要能看见")

    related = payload.get("sr_related_ars") or []
    if not isinstance(related, list):
        raise FlowError("sr_related_ars 须是数组（同一 SR 下的其它 AR；没有就给空数组）")
    normalized = []
    for i, item in enumerate(related):
        if not isinstance(item, dict) or not str(item.get("ar") or "").strip():
            raise FlowError(f"sr_related_ars 第 {i + 1} 项缺 ar（兄弟 AR 单号）")
        ar = str(item["ar"]).strip()
        # 字段是「同 SR 的**其它** AR」。把自己列进去，下游「有兄弟 AR 就不可能承载全部」
        # 这条判断会被自己触发，§1.2 的形态也会选错。
        if ar == feature_root.name:
            raise FlowError(
                f"sr_related_ars 含本 AR 自己（{ar}）：该字段只列同一 SR 下的**其它** AR，"
                "本 AR 的范围写在 scope_text")
        normalized.append({"ar": ar, "scope": str(item.get("scope") or "").strip()})

    return {"scope_source": source, "scope_text": scope_text, "sr_related_ars": normalized}


def read_scope_options(feature_root: Path) -> list[dict] | None:
    """读范围定法选项集侧车（需求分析 S2b 的产出）。

    **选项集必须先落契约、关卡再从契约取**：否则分析已写「未找到具名可切维度，
    故不提供拆分选项」时，关卡仍可能照规则示意硬凑满三项——多出来的选项是**现编的空壳**：
    没有份表、没有内容，人看不懂也无从评估，选中后下一级的份表同样现编。
    纯文字约束拦不住现编。

    分析定几项，关卡就只能摆几项：让「摆不出第二项」成为**结构性事实**，而不是纪律。
    想要分析里没有的切法，正当路径是口述修正 → 回去重做分析（补该维度、重落侧车），
    这正是「先做完再问」的原意：分析先行，关卡只负责照出。
    """
    payload = read_sidecar(feature_root, SCOPE_OPTIONS)
    if payload is None:
        return None
    if not isinstance(payload, list) or not payload:
        raise FlowError(f"{SCOPE_OPTIONS[-1]} 须是非空数组：至少含「按当前范围整体承载」一项")

    keys: list[str] = []
    for i, opt in enumerate(payload):
        if not isinstance(opt, dict):
            raise FlowError(f"{SCOPE_OPTIONS[-1]} 第 {i + 1} 项不是对象")
        key = str(opt.get("key") or "").strip()
        if not key:
            raise FlowError(f"{SCOPE_OPTIONS[-1]} 第 {i + 1} 项缺 key")
        if key in keys:
            raise FlowError(f"选项 key 重复：「{key}」")
        if not str(opt.get("label") or "").strip():
            raise FlowError(
                f"选项「{key}」缺 label：标签要让人看得懂选完是什么范围"
                "（整体承载列出功能点；切法写清按什么切、切成几份）")
        keys.append(key)

    if CARRY_ALL not in keys:
        raise FlowError(
            f"选项集缺固定首项 `{CARRY_ALL}`（按当前范围整体承载）"
            "——不切分永远是一个可选项，不摆出来人就无从选择")

    normalized = []
    for opt in payload:
        item = dict(opt)
        item["key"] = str(opt["key"]).strip()
        if item["key"] != CARRY_ALL:
            parts = item.get("parts")
            if not isinstance(parts, list) or len(parts) < 2:
                raise FlowError(
                    f"切法「{item['key']}」缺 parts（至少两份）："
                    "没有份表的切法是空壳，人无法评估切完是什么样")
        normalized.append(item)
    # 固定首项排最前：人第一眼看到的是「不切」，其余是在此基础上的切分建议
    normalized.sort(key=lambda o: 0 if o["key"] == CARRY_ALL else 1)
    return normalized


def chosen_dimension(current: dict) -> dict | None:
    """本轮第二级选中的那个切分维度（选了整体承载或还没选则为 None）。"""
    for g in reversed(current.get("gates") or []):
        if g.get("gate") == "scope_decision" and g.get("outcome") == "accepted":
            if g.get("chosen") == CARRY_ALL:
                return None
            for opt in current.get("scope_options") or []:
                if opt.get("key") == g.get("chosen"):
                    return opt
            return None
    return None


def split_carrier_options(current: dict) -> list[dict]:
    """第三级的选项 = 选定维度的份表，由脚本生成。

    人在第二级选了「按 X 切」，第三级要选的就是 X 那张份表里的哪一份归本 AR——
    选项内容早已在分析里定好，这一级没有任何可现编的余地，所以不读侧车。
    """
    dim = chosen_dimension(current)
    if not dim:
        return []
    return [{"key": str(p.get("seq")), "scope": p.get("scope", ""),
             "depends_on": p.get("depends_on") or []}
            for p in dim.get("parts") or []]


def read_gate_options(feature_root: Path) -> list[dict]:
    """读本次关卡摆出的选项集。

    每项必须有 `key`（选项标识），其余字段随关卡自由（label / scope / recommended /
    dimension …）——统一只约束标识，是为了让「chosen 必须在 options 里」这条校验
    对三级关卡通用，不必为每个关卡各写一套值域。
    """
    payload = read_sidecar(feature_root, GATE_OPTIONS)
    if payload is None:
        raise FlowError(
            "缺选项集侧车：把本次关卡摆给人的全部选项写进 "
            f"{'/'.join(GATE_OPTIONS)}（每项含 key，可带 label / recommended 等）。"
            "只记选中的那项，事后分不清「看过选项后这么选」与「压根没摆过选项」")
    if not isinstance(payload, list) or not payload:
        raise FlowError(f"{GATE_OPTIONS[-1]} 须是非空数组：每项一个选项")

    keys: list[str] = []
    for i, opt in enumerate(payload):
        if not isinstance(opt, dict):
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项不是对象")
        key = str(opt.get("key") or "").strip()
        if not key:
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项缺 key")
        if key in keys:
            raise FlowError(f"选项 key 重复：「{key}」——每项一个标识")
        keys.append(key)

    normalized = []
    for opt in payload:
        item = {k: v for k, v in opt.items() if k != "key"}
        item["key"] = str(opt["key"]).strip()
        normalized.append(item)
    return normalized


def material_fingerprint(inputs: dict[str, str | None]) -> str:
    """本轮材料的指纹：四源哈希的有序摘要。

    **一轮 = 一次材料状态**。轮次边界曾以初析件 sha 划分，那是「先分析后确认材料」时代的
    残留：材料还没确认就得先写出完整初析，材料一变分析全废，每轮补料重做一遍。
    现在材料确认在前、分析在后，轮次自然应该跟着**材料**走——补料导入 → 材料变 → 新一轮；
    材料没变，重跑 round 幂等。

    「防伪造轮次」的职责也由它承接，而且更贴事实：重析的正当理由本来就是材料变了，
    拿分析件的哈希当轮次边界，等于允许「材料没动、重写一遍分析」造出一个新轮次。
    """
    payload = json.dumps(inputs, ensure_ascii=False, sort_keys=True)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()[:16]


def cmd_round(feature_root: Path) -> dict:
    imported = read_receipt(feature_root)
    # 定位与选项集侧车都是 S2b（需求分析）的产物，此刻通常还不存在——
    # round 发生在材料盘点之后、分析之前。写了就消费，没写不失败：
    # 该不该有由 next_step 判（材料没确认前它根本不该有）。
    positioning = read_positioning(feature_root)
    scope_options = read_scope_options(feature_root)

    # 事实一律取当下：调用时机不确定（导入完全可能发生在 round 之后），
    # 所以每次调用都重算，绝不沿用上一次的快照。
    inputs = {rel: digest(feature_root / rel) for rel in SOURCES}
    fingerprint = material_fingerprint(inputs)
    # 分析件可有可无：材料盘点阶段它还没写完整版
    analysis_sha = digest(feature_root / Path(*ANALYSIS))

    contract = load(feature_root) or {
        "schema": SCHEMA, "feature": feature_root.name, "status": "in_progress",
        "rounds": [],
        "split": {"decided": "none", "settled_round": None, "scope_text": None, "parts": []},
        "design": None,
        "design_generated_at": None,
    }
    rounds = contract["rounds"]
    # `imported` 记的是**本轮新导入**的：导入重跑会再落一份内容相同的回执，
    # 累计计入会让「哪一轮导的」永远说不清。
    already = {name for r in rounds for name in r.get("imported", [])}

    def stamp(entry: dict) -> None:
        """把本次调用取到的事实盖进轮次条目（新轮与幂等轮共用）。"""
        entry["inputs"] = inputs
        entry["materials"] = fingerprint
        if analysis_sha:
            # 同一轮内分析件会从盘点版演进到完整版，照实更新，不当成新一轮
            entry["analysis"] = {"path": "AR/init-analysis.md", "sha256": analysis_sha}
        if positioning:
            entry["positioning"] = positioning
        if scope_options:
            entry["scope_options"] = scope_options

    # 材料没变就不是新一轮。「幂等」只意味着**不新建轮次**，不意味着不更新事实。
    if rounds and rounds[-1].get("materials") == fingerprint:
        current = rounds[-1]
        stamp(current)
        fresh = sorted(set(imported) - (already - set(current.get("imported", []))))
        if fresh:
            current["imported"] = sorted(set(current.get("imported", [])) | set(fresh))
        save(feature_root, contract)
        consume_receipt(feature_root)
        consume_sidecar(feature_root, POSITIONING)
        consume_sidecar(feature_root, SCOPE_OPTIONS)
        log(f"材料未变（{fingerprint}），仍在第 {current['round']} 轮（已刷新事实快照）")
        return {"round": current["round"], "created": False, "materials": fingerprint,
                "positioning": bool(current.get("positioning")),
                "scopeOptions": len(current.get("scope_options") or [])}

    entry = {
        "round": len(rounds) + 1,
        "imported": sorted(set(imported) - already),
        "analysis": None,
        "inputs": inputs,
        "materials": fingerprint,
        "positioning": None,
        "scope_options": None,
        "gates": [],
    }
    stamp(entry)
    rounds.append(entry)
    save(feature_root, contract)
    consume_receipt(feature_root)
    consume_sidecar(feature_root, POSITIONING)
    consume_sidecar(feature_root, SCOPE_OPTIONS)
    log(f"登记第 {entry['round']} 轮（材料 {fingerprint}，本轮导入 {len(entry['imported'])} 件）")
    return {"round": entry["round"], "created": True, "materials": fingerprint,
            "positioning": bool(entry.get("positioning")),
            "scopeOptions": len(entry.get("scope_options") or [])}


# ---------------------------------------------------------------------------
# decide：追加一条关卡决策

def pending_material(feature_root: Path, contract: dict) -> list[str]:
    """收件箱里还没导过的料。

    原件导入后留在收件箱存档，所以「有文件」不等于「有新料」——账本是各轮的
    `imported` 并集，AI 记不住，脚本记得住。
    """
    inbox = feature_root / "inbox"
    if not inbox.is_dir():
        return []
    done = {name for r in contract["rounds"] for name in r.get("imported", [])}
    return sorted(p.name for p in inbox.iterdir()
                  if p.is_file() and not p.name.startswith(".")
                  and p.name.lower() not in SKIP_INBOX and p.name not in done)


def read_split_parts(feature_root: Path, feature: str) -> list[dict]:
    """读拆分份表侧车并校验。

    走文件不走参数：JSON 全是引号，任何 shell 都要对参数再解析一遍——同一条命令在
    bash 下原样送达、在 PowerShell 下双引号被吞。这条纪律本 skill 的所有脚本一致。

    份表回答的是「拆成几份、各归谁、什么顺序、谁依赖谁」；`scope_text` 不再单独登记，
    由本 AR 那份的 scope 推导——同一事实两处登记，迟早各说各话。
    """
    path = feature_root / Path(*SPLIT_PARTS)
    if not path.is_file():
        return []
    try:
        parts = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise FlowError(f"{path.name} 不是合法 JSON：{exc}") from exc
    if not isinstance(parts, list) or not parts:
        raise FlowError(f"{path.name} 须是非空数组：每项一份拆分")

    seqs: list[int] = []
    for i, p in enumerate(parts):
        if not isinstance(p, dict):
            raise FlowError(f"{path.name} 第 {i + 1} 项不是对象")
        missing = [k for k in ("seq", "carrier", "scope") if not str(p.get(k) or "").strip()]
        if missing:
            raise FlowError(f"{path.name} 第 {i + 1} 项缺字段：{'、'.join(missing)}")
        if not isinstance(p["seq"], int):
            raise FlowError(f"{path.name} 第 {i + 1} 项的 seq 须是整数（建议执行顺序）")
        seqs.append(p["seq"])

    dup = {s for s in seqs if seqs.count(s) > 1}
    if dup:
        raise FlowError(f"份表 seq 重复：{sorted(dup)}——seq 是执行顺序，每份一个")

    mine = [p for p in parts if str(p["carrier"]).strip() == feature]
    if len(mine) != 1:
        raise FlowError(
            f"份表里 carrier 为「{feature}」的必须恰好一份，实为 {len(mine)} 份"
            "——本 AR 承载哪一份是拆分的核心结论，不能缺也不能多")

    known = set(seqs)
    for p in parts:
        deps = p.get("depends_on") or []
        if not isinstance(deps, list):
            raise FlowError(f"seq {p['seq']} 的 depends_on 须是数组")
        for d in deps:
            if d not in known:
                raise FlowError(f"seq {p['seq']} 依赖了不存在的 seq {d}")
            if d == p["seq"]:
                raise FlowError(f"seq {p['seq']} 依赖了自己")

    # 环检测：依赖是「须先交付」，成环就没有可执行的起点
    graph = {p["seq"]: list(p.get("depends_on") or []) for p in parts}
    state: dict[int, int] = {}

    def walk(node: int) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            raise FlowError(f"份表依赖成环（seq {node} 回到了自己）：没有可执行的起点")
        state[node] = 1
        for nxt in graph[node]:
            walk(nxt)
        state[node] = 2

    for s in seqs:
        walk(s)

    return [{"seq": p["seq"], "carrier": str(p["carrier"]).strip(),
             "scope": str(p["scope"]).strip(),
             "depends_on": list(p.get("depends_on") or [])}
            for p in sorted(parts, key=lambda x: x["seq"])]


def cmd_decide(feature_root: Path, args: argparse.Namespace) -> tuple[dict, int]:
    gate = args.gate or GATES[0]
    if gate not in GATES:
        raise FlowError(f"--gate 须为 {' / '.join(GATES)} 之一，实为「{gate}」")
    if args.by not in ACTORS:
        raise FlowError(f"--by 须为 {' / '.join(ACTORS)} 之一，实为「{args.by}」")
    if not (args.basis or "").strip():
        raise FlowError("--basis 不能为空：决策的依据（用户原话）是契约的审计价值所在")

    chosen = str(args.chosen or "").strip()
    if not chosen:
        raise FlowError("--chosen 不能为空")

    contract = require(load(feature_root))
    current = contract["rounds"][-1]

    # 只能做流程当前允许的那一步。顺序由 `next_step` 一处定义，decide 不自己判前置——
    # 两处各写一套「什么时候能做什么」，迟早对不上。
    expected, action = next_step(feature_root, contract)
    if expected != f"await_gate:{gate}":
        raise FlowError(f"当前这一步不是 {gate}：{action}（`status` 的 next 是 {expected}）")

    # 选项来源按关卡分工——**只有第一级读侧车**，后两级从契约取，关卡摆不出分析没定的选项。
    if gate == "material_scope":
        options = read_gate_options(feature_root)
        if chosen not in MATERIAL_CHOICES:
            raise FlowError(
                f"material_scope 的 --chosen 须为 {' / '.join(MATERIAL_CHOICES)} 之一，实为「{chosen}」")
    elif gate == "scope_decision":
        # 分析定几项就只能摆几项：现编的空壳选项在此被结构性挡住
        options = current.get("scope_options") or []
        if not options:
            raise FlowError(
                f"本轮尚未登记范围定法选项集：把需求分析产出的全部选项写进 "
                f"{'/'.join(SCOPE_OPTIONS)} 后重跑 `round`")
    else:  # split_carrier
        # 份表选项由脚本从选定维度的 parts 生成——不读侧车、不混退回项，
        # 第三级只问「承载哪一份」，退回是另一件事
        options = split_carrier_options(current)

    if chosen not in [o["key"] for o in options]:
        raise FlowError(
            f"--chosen「{chosen}」不在本次选项集里（现有：{'、'.join(o['key'] for o in options)}）"
            "——选项集要么漏了这一项，要么选错了 key")

    parts: list[dict] = []
    if gate == "split_carrier":
        # 承载定案：份表此时才成形（哪一份归本 AR 由这一步的选择决定）
        parts = read_split_parts(feature_root, feature_root.name)
        if not parts and not (args.scope_text or "").strip():
            raise FlowError(
                "split_carrier 缺定案内容：把拆分份表写进 "
                f"{'/'.join(SPLIT_PARTS)}（每份含 seq / carrier / scope / depends_on，"
                "carrier 为本 AR 的恰好一份 = 用户选中的那份，其余份写兄弟 AR 单号或「待立项」），"
                "或退而用 --scope-text 给出本 AR 的范围文字。只留在对话里，会话一断就丢")
        if parts:
            # 定案的必须是选中的：人选了第 k 份，份表就得把第 k 份给本 AR。
            # 两处各写一次，不核对的话「选的」与「记的」可以完全无关而全绿。
            mine = next(p for p in parts if p["carrier"] == feature_root.name)
            if str(mine["seq"]) != chosen:
                raise FlowError(
                    f"人选的是第 {chosen} 份，份表里归本 AR 的却是第 {mine['seq']} 份"
                    f"（{mine['scope']}）——选择与定案对不上，改份表的 carrier 或改 --chosen")

    outcome, reason, code = "accepted", None, 0
    if gate == "material_scope" and chosen == "supplement":
        pending = pending_material(feature_root, contract)
        if not pending:
            outcome, code = "rejected", 2
            reason = ("inbox/ 里没有未导入的材料：请把文档或界面设计图放进 "
                      f"{feature_root.name}/inbox/ 后再选一次")

    record = {
        "gate": gate, "options": options, "chosen": chosen, "outcome": outcome,
        "by": args.by, "basis": args.basis.strip(), "at": now(),
    }
    if reason:
        record["reason"] = reason
    current.setdefault("gates", []).append(record)

    if gate == "split_carrier" and outcome == "accepted":
        # scope_text 由本 AR 那一份推导，不单独登记——同一事实两处写，迟早各说各话
        scope_text = (next(p["scope"] for p in parts if p["carrier"] == feature_root.name)
                      if parts else args.scope_text.strip())
        contract["split"] = {"decided": "split", "settled_round": current["round"],
                             "scope_text": scope_text, "parts": parts}

    save(feature_root, contract)
    consume_sidecar(feature_root, GATE_OPTIONS)
    if gate == "split_carrier" and outcome == "accepted" and parts:
        consume_sidecar(feature_root, SPLIT_PARTS)
    log(f"第 {current['round']} 轮记录 {gate}：{chosen} → {outcome}"
        + (f"（{reason}）" if reason else ""))
    result = {"round": current["round"], "gate": gate, "chosen": chosen, "outcome": outcome}
    if reason:
        result["reason"] = reason
    return result, code


# ---------------------------------------------------------------------------
# status：现在走到哪、下一步干什么

def all_gates(contract: dict) -> list[dict]:
    """全流程的关卡记录，**仅供统计与展示**。位置判定一律用 `round_gates`。"""
    return [g for r in contract.get("rounds", []) for g in r.get("gates", [])]


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


def settled_this_round(contract: dict) -> bool:
    """拆分是不是**在当前轮**定的案。

    `split` 是契约级字段（design.md 只认最终那一份），而拆分决策属于某一轮——
    两者用 `settled_round` 挂钩，重新初析后同一份 split 就不再算数。
    """
    split = contract.get("split") or {}
    return (split.get("decided") == "split"
            and split.get("settled_round") == contract["rounds"][-1].get("round"))


def next_step(feature_root: Path, contract: dict | None) -> tuple[str, str]:
    """流程位置的唯一判据：读契约，回答下一步该干什么。

    位置由数据回答而不由记忆回答——skill 正文因此不必维护成篇的「如果……那么……」，
    恢复一个中断的 feature 也不用靠翻对话。每个返回值都对应 SKILL.md 里的一个具体动作。
    """
    if contract is None or not contract.get("rounds"):
        return "run_round", "初析已生成的话，跑 `story_flow.py round` 登记本轮"
    if contract.get("status") == "story_written":
        return "run_archived", "story 已成文，可以 `/story archive` 归档"
    if contract.get("status") == "complete":
        return "enter_spec", "流程已收口，直接进 /spec；spec 闭环后回 S5 写 story"

    current = contract["rounds"][-1]
    gates = round_gates(contract)

    # 第一级：材料够不够。**先于任何需求分析**——材料不全时做的范围判断注定作废，
    # 每轮补料都要重做一遍。所以这一级只需要材料盘点（清单 + 一句缺口判断）。
    material = last_gate(gates, "material_scope")
    if material is None:
        return ("await_gate:material_scope",
                "S3 第一级：带出材料清单（逐项标来源与状态）与一句缺口判断，"
                "取得选择——补充材料 / 材料充足，开始需求分析")
    if material["chosen"] == "supplement":
        if material["outcome"] == "accepted":
            return "import_and_reanalyze", "回 S2：导入 inbox/ 新料 → 重新盘点材料 → 重跑 `round`"
        return "await_gate:material_scope", "补料被拒（inbox 无新料），在第一级重新取得选择"

    # 材料已确认 → 才做需求粒度分析（全景 / 本部件 / 本 AR 定位 / 功能清单 / 范围定法选项）
    if not current.get("positioning") or not current.get("scope_options"):
        missing = []
        if not current.get("positioning"):
            missing.append(f"本 AR 定位 → {'/'.join(POSITIONING)}")
        if not current.get("scope_options"):
            missing.append(f"范围定法选项集 → {'/'.join(SCOPE_OPTIONS)}")
        return ("run_analysis",
                "S2b 需求粒度分析（材料已确认）：需求概览 → 本部件视角 → 本 AR 定位 → "
                "待实现功能清单 → 范围定法选项；落盘后重跑 `round`。待补：" + "；".join(missing))

    # 第二级：这个范围怎么定
    decision = last_gate(gates, "scope_decision")
    if decision is None:
        return ("await_gate:scope_decision",
                "S3 第二级：照出契约里的范围定法选项集（分析定几项就摆几项），取得选择")

    # 第三级：本 AR 承载哪一份（仅在选了某个切分维度时）
    if decision["chosen"] != CARRY_ALL and not settled_this_round(contract):
        return "await_gate:split_carrier", "S3 第三级：呈现该维度的份表，取得本 AR 承载哪份"

    # 范围已定——整体承载，或份表已定案。直接进 S4，不再回关卡收口
    if not (feature_root / Path(*DESIGN)).is_file():
        return "generate_design", "S4：按 rules/ar_design_init.md 生成 AR/design.md"
    return "run_complete", "跑 `story_flow.py complete` 收口"


def cmd_status(feature_root: Path) -> dict:
    contract = load(feature_root)
    step, action = next_step(feature_root, contract)
    if contract is None:
        return {"exists": False, "next": step, "action": action}

    current = contract["rounds"][-1] if contract.get("rounds") else {}
    # 只列**当前轮**：与 next 的判据一致，免得人看着历史决策去对现在的位置。
    # 历史查契约文件本身。
    gates = round_gates(contract) if contract.get("rounds") else []
    return {
        "exists": True,
        "schema": contract.get("schema"),
        "status": contract.get("status"),
        "round": current.get("round"),
        "positioning": current.get("positioning"),
        "gates": [{"gate": g.get("gate"), "chosen": g.get("chosen"),
                   "outcome": g.get("outcome"), "by": g.get("by")} for g in gates],
        "split": contract.get("split", {}).get("decided"),
        "design": bool((feature_root / Path(*DESIGN)).is_file()),
        "archived": bool(contract.get("archived")),
        "next": step,
        "action": action,
    }


# ---------------------------------------------------------------------------
# complete：收口

def read_ids(feature_root: Path, feature: str) -> dict[str, str | None]:
    """单号取自 `detail.json`——那是需求系统的拉取产物，没有它就是本地单。

    只读不造：伪造单号等于谎称本地单有系统单据。
    """
    def field(rel: str, key: str) -> str | None:
        try:
            data = json.loads((feature_root / rel).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    return {
        "AR": feature,
        "SR": field("AR/detail.json", "parentNo") or field("SR/detail.json", "reqNo"),
        "RR": field("AR/detail.json", "rrNo") or field("RR/detail.json", "reqNo"),
    }


def ar_design_skeleton(ids: dict[str, str | None]) -> str:
    """`AR/design.md` 空骨架——**全流程唯一真源**。

    结构对应 rules/ar_design_init.md 的「需求提取五段结构」；内嵌注释是给后续模型的
    判定指引，必须一并落盘，不是给人看的说明。
    """
    if ids["SR"] and ids["RR"]:
        links = (f"| SR/AR单号 | {ids['SR']} / {ids['AR']} |\n"
                 f"| PRD文档 | requirement://prd/{ids['RR']} |\n"
                 f"| SE设计文档 | requirement://sr/{ids['SR']} |\n")
    else:
        links = (f"| 来源载体 | {ids['AR']}（无需求系统单据） |\n"
                 "| PRD文档 | 人工提供，见 inbox 导入记录 |\n"
                 "| SE设计文档 | 人工提供，见 inbox 导入记录 |\n")
    return (
        f"# {ids['AR']} 开发需求（AR）\n\n"
        "## 1 简介\n\n### 1.1 需求介绍\n\n### 1.2 本 AR 范围与拆分说明\n\n"
        "<!-- 本 AR 承载哪部分；范围外内容归属（兄弟 AR 单号或「待立项」）。必填，空着分不清「没拆」与「忘了写」。\n"
        "     三形态（按流程契约 positioning/split 判）见 rules/ar_design_init.md §3（模板 1.2 三形态）——\n"
        "     「无拆分」不等于「承载全部」：同 SR 有兄弟 AR 时后者是假的，会被 spec 门禁拦下 -->\n\n"
        "### 1.3 相关文档链接\n\n| 内容 | 链接 |\n| --- | --- |\n"
        f"{links}"
        "| UX设计文档 | |\n\n"
        "## 2 需求分析\n\n### 2.1 场景与功能点\n\n### 2.2 验收意图\n\n"
        "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\n"
        "### 3.2 本部件方案要点与流程骨架\n\n"
        "## 4 上游索引\n\n"
        "> 本索引的 SR 章节号指向 `SR/design.md`（与本文件同在本需求工作区，PRD 为 `RR/prd.md`）；\n"
        "> 下游步骤（/spec 及其技术契约与合规判定取证）须按索引直读该文件原文，不得仅凭本文摘要推断。\n\n"
        "| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
        "<!-- 逐类扫描 RR/SR 登记命中项：业务流程时序 / 端云接口 / 异常错误码 / 跨部件交互与调用方 /\n"
        "     系统级存储 / 配置管控 / 打点 / 非功能约束 / 安全合规 / 版本与配套 / 依赖 SDK·TA /\n"
        "     术语与命名 / 上游已定的方案边界。清单与消费方见 rules/ar_design_init.md -->\n\n"
        "## 5 上游已声明线索\n")


def cmd_init(feature_root: Path, feature: str) -> dict:
    """建工作区骨架——`inbox/`、RR/SR 占位件、`AR/design.md` 空骨架的唯一写入者。

    **缺什么补什么，已有的一律不动**，因此它与取材结果无关：系统单在 `story.js init`
    之后跑，本地单（问题单、别人发来的需求文档）直接跑，两条路径同一条命令，重跑安全。
    收件箱由此独立于数据对接层成立——那一层由各部署环境自备实现，不随交付走。

    占位件让「上游没拉到」以**内容**表达：章节合同里有的章只吃 PRD、有的只吃 SE，
    源文件在位，下游才能照常按源取材，补料后由导入步骤覆盖它。

    **不写 detail.json**：那是需求系统的拉取产物，单号只读不造。
    """
    created, kept = [], []

    def put(rel: str, text: str) -> None:
        target = feature_root / rel
        if target.is_file():
            kept.append(rel)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        created.append(rel)

    ids = read_ids(feature_root, feature)
    placeholder = (
        "# {title}\n\n"
        "> **本文档未从需求系统拉取到**（单据未归档，或拉取失败）。\n"
        "> 正文待从 `inbox/` 导入：把材料放进收件箱，由导入步骤归类覆盖本文件。\n"
        "> 在此之前请勿把本占位件当作「需求没有这部分内容」。\n"
    )
    put("RR/prd.md", placeholder.format(title="产品需求（占位）"))
    put("SR/design.md", placeholder.format(title="系统级设计（占位）"))
    put("AR/design.md", ar_design_skeleton(ids))

    readme = Path(__file__).resolve().parent.parent / "templates" / "inbox-readme.md"
    put("inbox/README.md",
        readme.read_text(encoding="utf-8") if readme.is_file()
        else "# 收件箱\n\n把手上的需求材料放进本目录，导入步骤会归类并写入对应上游文件。\n")

    local = not (feature_root / "AR" / "detail.json").is_file()
    missing = [rel for rel in ("RR/prd.md", "SR/design.md") if rel in created]
    log(f"工作区骨架：新建 {len(created)} 个文件"
        + (f"，保留已有 {len(kept)} 个" if kept else ""))
    if missing and not local:
        log(f"上游未拉到：{'、'.join(missing)}——已写占位件，"
            f"请把材料放进 {feature_root.name}/inbox/ 后走导入")
    return {"created": created, "kept": kept, "local": local, "placeholders": missing}


def cmd_complete(feature_root: Path) -> dict:
    contract = require(load(feature_root))
    if not (feature_root / Path(*DESIGN)).is_file():
        raise FlowError("AR/design.md 不存在：收口前须先按「生成design.md」章产出提取件")

    # 收口的前置是**本轮范围已定**，而不是某一条特定记录——补料会开新一轮，
    # 上一轮定的范围不能替这一轮授权。判据与 next_step 同源：它说该收口才能收口
    #（定位/选项集缺失时它会报 run_analysis，不必在这里另判一遍）。
    step, action = next_step(feature_root, contract)
    if step not in ("run_complete", "enter_spec"):
        raise FlowError(f"本轮范围尚未定下来，还不能收口：{action}（`status` 的 next 是 {step}）")
    if contract["split"]["decided"] == "split" and \
            not str(contract["split"].get("scope_text") or "").strip():
        raise FlowError("拆分已定案但 split.scope_text 为空：范围文字丢失，无法写入 design.md")

    # 收口时的 design.md 快照。**不作校验用**——归档会覆盖这个文件（spec 阶段
    # post_check 对此有专门处理），拿它比对当前哈希必然误报。它回答的是审计问题：
    # 这份契约收口时对应的是哪一版提取件。
    contract["design"] = {"sha256": digest(feature_root / Path(*DESIGN))}
    contract["design_generated_at"] = now()
    contract["status"] = "complete"
    save(feature_root, contract)
    total = sum(len(r.get("gates", [])) for r in contract["rounds"])
    log(f"流程收口：{len(contract['rounds'])} 轮、{total} 条关卡记录")
    return {"status": "complete", "rounds": len(contract["rounds"]), "gates": total}


# ---------------------------------------------------------------------------
# archived：登记归档态

STORY = ("AR", "story.md")
REVIEW = ("AR", "review.md")


def cmd_story(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已成文」（S5 收口）。

    story 不再在 spec 会话末尾写——那时上下文已经涨到几十万 token，story 是最后被挤出来的
    那一份。它移到 spec 闭环之后的 S5，由独立 writer 在新鲜上下文里一份写成。

    **登记自带门禁**：先重跑 `story-build check`，通过才记。守恒判据在那里，
    不在这里重实现——两处各判各的，迟早对不上。
    """
    contract = require(load(feature_root))
    if contract.get("status") != "complete":
        raise FlowError("流程还没收口（status 不是 complete），成文态无从谈起")
    story = feature_root / Path(*STORY)
    if not story.is_file():
        raise FlowError("AR/story.md 不存在：没有成文，无可登记的成文态")

    checker = Path(__file__).resolve().parent / "story-build.mjs"
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：成文态登记要先重跑 story-build check，无法跳过")
    proc = subprocess.run(
        [node, str(checker), "check", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FlowError(
            "story-build check 未通过，成文态不予登记：\n"
            + (proc.stderr or proc.stdout or "").strip())

    contract["status"] = "story_written"
    contract["story_written_at"] = now()
    save(feature_root, contract)
    return {"status": "story_written", "story": str(story)}


def cmd_archived(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已送审」。归档动作由数据对接层执行，本命令只记状态。

    归档态是**流程状态**，落在流程契约里：装配脚本据它判定 `AR/review.md` 已归人所有，
    此后只备份不重建，评审人的批注与回稿都留在那份文件里。判据在契约里，
    与谁执行的归档无关——数据对接层由各部署环境自备实现，不随交付走。

    **登记自带门禁**：先重跑一次 `story-build check`，通过才记——归档时 story 可能又改过，
    成文态那次的校验不算数。登记不可逆，凭据只认校验过的产物。
    """
    contract = require(load(feature_root))
    if contract.get("status") != "story_written":
        raise FlowError(
            "还没登记成文态：归档的是 story，story 没过 check 就归档等于把未校验的产物送审。"
            "先跑 `story_flow.py story --feature <名>`")
    story, review = feature_root / Path(*STORY), feature_root / Path(*REVIEW)
    for path, name in ((story, "AR/story.md"), (review, "AR/review.md")):
        if not path.is_file():
            raise FlowError(f"{name} 不存在：归档件三缺一，无可登记的归档态")

    checker = Path(__file__).resolve().parent / "story-build.mjs"
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：归档态登记要先重跑 story-build check，无法跳过")
    proc = subprocess.run(
        [node, str(checker), "check", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        log((proc.stderr or proc.stdout).strip()[:2000])
        raise FlowError(
            "归档件未通过 story-build check（详见上方输出），拒绝登记归档态。"
            "已经传上去的那一版是不合格的：修好后重新归档，再登记")

    contract["archived"] = {
        "at": now(),
        "story": digest(story),
        "review": digest(review),
    }
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，装配只备份不重建")
    return {"archived": True, "at": contract["archived"]["at"]}


def is_archived(feature_root: Path) -> bool:
    try:
        return bool((load(feature_root) or {}).get("archived"))
    except FlowError:
        return False


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="story init→spec 流程契约的唯一写入者")
    ap.add_argument("mode",
                    choices=["init", "round", "decide", "status", "complete", "story", "archived"])
    ap.add_argument("--feature", required=True)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--gate", default=None, choices=list(GATES),
                    help="关卡编号，缺省 material_scope")
    ap.add_argument("--chosen", default=None,
                    help="选中项的 key；material_scope 为 supplement / split / proceed")
    ap.add_argument("--by", default="human", choices=list(ACTORS))
    ap.add_argument("--basis", default=None, help="决策依据：用户原话，或授权原话 + 推荐理由")
    ap.add_argument("--scope-text", default=None,
                    help="split_carrier 无份表侧车时的兜底：本 AR 的范围文字")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    result: dict = {"mode": args.mode, "reqNo": args.feature}
    try:
        project_root = Path(args.project_root).resolve() if args.project_root \
            else Path(__file__).resolve().parents[5]
        feature_root = project_root / features_dir(project_root) / args.feature

        code = 0
        if args.mode == "init":
            result.update(cmd_init(feature_root, args.feature))
        elif args.mode == "round":
            result.update(cmd_round(feature_root))
        elif args.mode == "decide":
            payload, code = cmd_decide(feature_root, args)
            result.update(payload)
        elif args.mode == "status":
            result.update(cmd_status(feature_root))
        elif args.mode == "story":
            result.update(cmd_story(feature_root, project_root))
        elif args.mode == "archived":
            result.update(cmd_archived(feature_root, project_root))
        else:
            result.update(cmd_complete(feature_root))

        result["success"] = code == 0
        print(json.dumps(result, ensure_ascii=False))
        return code
    except FlowError as exc:
        log(str(exc))
        result.update(success=False, error=str(exc))
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
