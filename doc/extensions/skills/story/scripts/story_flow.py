"""story_flow.py — init→spec 流程契约（`AR/story-flow.json`）的**唯一写入者**。

契约记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项，
事后可查、可推翻。

契约同时是这条流程的**状态机**：`status` 子命令读它就能回答「现在走到哪、下一步干什么」。
所以 skill 正文不必维护成篇的分支判定文本——位置由数据回答，不由记忆回答。

契约里绝大多数内容是机械事实——时间戳、轮次边界、收件箱里还有没有没导过的料。
这类事实靠记忆复现就会失真，所以一律由脚本自取。

分工因此是：**判断留 AI，执行归脚本**（与 `import_sources.py` 的归类件同一条边界）。
AI 只传它真正知道而脚本无从得知的东西——人选了哪一项、依据是什么；其余一律脚本自己取。
本轮导入了什么也在「脚本自己取」这一侧：`round` 每次调用都让 `materials.py` 按磁盘现状
重算材料清单，从清单里读出哪些原件已经并入正文——没有回执，也不需要谁记住发生过什么。

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
拆分份表走 `AR/story-src/.split-parts.json`，脚本读后即销毁（一次性）。

退出码（`decide` 的退出码回答「能不能按这个选择往下走」）：

    0  成功
    1  用法/参数/前置不满足——**没有任何写入**
    2  仅 decide：选择已记录，但校验不通过，**不得前进**（如选了补料却没放料）

核心不变量：

- **一轮 = 一次材料状态**。轮次边界只由材料清单的 `digest` 判定（`AR/story-src/materials.json`）：
  材料一个字节没变就不是新一轮（幂等），补料导入则必然换版本。初析件在同一轮内可以从
  盘点版改到完整版，它的哈希照实登记，但不划轮次——否则「材料没动、重写一遍分析」
  就能造出一个新轮次；
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

import materials

SCHEMA = 3
CONTRACT = ("AR", "story-flow.json")
ANALYSIS = ("AR", "init-analysis.md")
# 拆分份表侧车：AI 写、脚本读，登记进契约后销毁（一次性）
SPLIT_PARTS = ("AR", "story-src", ".split-parts.json")
# 选项集侧车：本次关卡摆给人的全部选项。每条 gate 一份，读后销毁
GATE_OPTIONS = ("AR", "story-src", ".gate-options.json")
# 本 AR 定位侧车：三源核对后收敛出的当前范围结论。round 消费
POSITIONING = ("AR", "story-src", ".positioning.json")
# 范围定法选项集侧车：需求分析（S2b）产出的**全部**可选项。round 消费进契约，
# 第二级关卡此后只能从契约里取——见 read_scope_options 的注释
SCOPE_OPTIONS = ("AR", "story-src", ".scope-options.json")
DESIGN = ("AR", "design.md")
# 成文态登记时随稿冻结的台账：story 定稿了，它据以成文的账本也就定稿了。
# 登记之后重跑 init 会把这几份重算一遍：story.md 冻了，账本被后一次重跑冲掉。
STORY_SRC_FROZEN = (
    "decisions.json", "copyedit.md",
)
#: 章草稿目录。作者在这里写、`chapter --from` 从这里读，所以登记前不能扫掉——
#: check 没过时他要回到草稿接着改。登记成功后删：story 冻结了，草稿失去用途。
DRAFTS_DIR = "drafts"


def sweep_story_src(src: Path) -> list[str]:
    """登记前把 story-src/ 扫干净——只留台账那两件。

    模型会在这里造一堆工作草稿（分章文本、候选池、映射表），
    跟台账混在一个目录里进归档。归档件的读者分不清哪些是交付物、
    哪些是造它时的脚手架，而脚手架里往往还有半成品与废弃版本。

    白名单**就是 STORY_SRC_FROZEN 本身**，不在这里另列一份：那两件是随稿冻结、
    要算指纹的台账，清理与冻结说的必须是同一批文件——各写一份，改一处忘一处时，
    要么清掉了要算指纹的，要么留下了不该留的。

    材料清单是这条规则之外的**一件**：它不是造 story 的脚手架，而是材料本身的真源，
    由 `round` 按磁盘现状重算，也会随材料继续演化——所以它留下，但不随稿冻结。
    story 定稿那一刻手里是哪版材料，记在契约当轮的 `materials.digest` 里，那才是快照。

    只扫这一层，不递归、不碰别的目录；清掉的逐个报出来，不静默删。
    """
    if not src.is_dir():
        return []
    keep = set(STORY_SRC_FROZEN) | {materials.MANIFEST[-1], DRAFTS_DIR}
    swept = []
    for item in sorted(src.iterdir()):
        if item.name in keep:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
        swept.append(item.name)
    return swept
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
# 关卡决策**只认人签**，没有 AI 代签这一档。
#
# 不留 `ai` 这个取值：配上「材料缺口时才停」这种条件式判据的话，模型判
# 「材料足够」→ 条件不成立 → 不停 → 以自己的名义把关卡记掉 → 材料补充环节
# 整个被跳过。停等的开关不能交给被停的那一方，这一行就是那道门禁。
ACTORS = ("human",)
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


def ledger_digest(path: Path) -> str | None:
    """台账指纹：**换行差异不算改动**（同一份文件在两台机器上可能行尾不同）。

    这一个要与 `story-build.mjs` 的 `digestOf` 逐字节同口径——登记由本脚本写，
    核对由那边做，两边算法差一点就会变成「每次都说台账被改过」。
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return sha256(text.encode("utf-8")).hexdigest()[:16]


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

def consume_sidecar(feature_root: Path, parts: tuple[str, ...]) -> None:
    """侧车是一次性的：登记进契约后销毁，否则下一次调用会把陈旧内容当成本次的输入。"""
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


#: 定位侧车的字段。读取函数按它校验，`status` 按它给骨架——写两份的话，
#: 改了字段名骨架不会跟着变，作者照骨架写出来的东西会被读取函数拒掉。
POSITIONING_FIELDS = {
    "scope_source": None,          # 合法值来自 SCOPE_SOURCES，骨架里现填
    "scope_text": "本 AR 当前范围，一句话；取全量时也要写出全量是什么",
    "sr_related_ars": "同一 SR 下的**其它** AR：[{ar, scope}]，没有就给空数组",
}


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


def sidecar_gate(feature_root: Path) -> str | None:
    """盘上摆着的选项侧车是给哪一级摆的——没摆、或写坏了，返回 None。

    三级共用一个文件名，所以它必须自报级别。不报的话，模型为第二级摆的选项
    会被第一级读成「材料上又出了新缺口」，把已经往前走的流程拨回上一级。
    """
    payload = read_sidecar(feature_root, GATE_OPTIONS)
    if not isinstance(payload, dict):
        return None
    at = str(payload.get("gate") or "").strip()
    return at if at in GATES else None


def read_gate_options(feature_root: Path, gate: str) -> list[dict]:
    """读本次关卡摆出的选项集，并核它摆的就是这一级。

    每项必须有 `key`（选项标识），其余字段随关卡自由（label / scope / recommended /
    dimension …）——统一只约束标识，是为了让「chosen 必须在 options 里」这条校验
    对三级关卡通用，不必为每个关卡各写一套值域。
    """
    payload = read_sidecar(feature_root, GATE_OPTIONS)
    if payload is None:
        raise FlowError(
            "缺选项集侧车：把本次关卡摆给人的全部选项写进 "
            f'{"/".join(GATE_OPTIONS)}（形如 {{"gate": "{gate}", "options": [{{"key": …}}]}}）。'
            "只记选中的那项，事后分不清「看过选项后这么选」与「压根没摆过选项」")
    if not isinstance(payload, dict):
        raise FlowError(
            f'{GATE_OPTIONS[-1]} 须是对象：{{"gate": "<哪一级>", "options": [每项一个选项]}}'
            "——级别要写在文件里，三级共用一个文件名")
    at = str(payload.get("gate") or "").strip()
    if at not in GATES:
        raise FlowError(
            f"{GATE_OPTIONS[-1]} 的 gate 须为 {' / '.join(GATES)} 之一，实为「{at}」")
    if at != gate:
        raise FlowError(
            f"侧车是给 {at} 级摆的，这一步是 {gate}——"
            "要么摆错了级别，要么这一步走错了。`status` 的 next 说的是哪一级就摆哪一级")
    options = payload.get("options")
    if not isinstance(options, list) or not options:
        raise FlowError(f"{GATE_OPTIONS[-1]} 的 options 须是非空数组：每项一个选项")

    keys: list[str] = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项不是对象")
        key = str(opt.get("key") or "").strip()
        if not key:
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项缺 key")
        if key in keys:
            raise FlowError(f"选项 key 重复：「{key}」——每项一个标识")
        keys.append(key)

    normalized = []
    for opt in options:
        item = {k: v for k, v in opt.items() if k != "key"}
        item["key"] = str(opt["key"]).strip()
        normalized.append(item)
    return normalized


def after_complete(contract: dict) -> bool:
    """流程收口了没有——**收口那一刻及其之后都算**。

    `complete` 之后还有 `story_written` 与归档；材料在这些状态下再变，同样不该开新轮。
    """
    return (contract.get("status") in ("complete", "story_written")
            or bool(contract.get("archived")))


def cmd_round(feature_root: Path) -> dict:
    # 定位与选项集侧车都是 S2b（需求分析）的产物，此刻通常还不存在——
    # round 发生在材料盘点之后、分析之前。写了就消费，没写不失败：
    # 该不该有由 next_step 判（材料没确认前它根本不该有）。
    positioning = read_positioning(feature_root)
    scope_options = read_scope_options(feature_root)

    # 事实一律取当下：调用时机不确定（导入完全可能发生在 round 之后），
    # 所以每次调用都让清单按磁盘现状重算，绝不沿用上一次的快照。
    try:
        manifest = materials.refresh(feature_root)
    except materials.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    digest = manifest["digest"]
    reference = {"path": "/".join(materials.MANIFEST), "digest": digest}
    # 已经并入正文的原件就是「导过的料」——这一份事实只在清单里，契约不再自己记一遍哈希
    ingested = sorted(s["file"] for s in manifest["sources"] if s.get("ingested"))
    # 分析件可有可无：材料盘点阶段它还没写完整版
    analysis_sha = materials.file_digest(feature_root / Path(*ANALYSIS))

    contract = load(feature_root) or {
        "schema": SCHEMA, "feature": feature_root.name, "status": "in_progress",
        "rounds": [],
        "split": {"decided": "none", "settled_round": None, "scope_text": None, "parts": []},
        "design": None,
        "design_generated_at": None,
    }
    rounds = contract["rounds"]
    # `imported` 记的是**本轮新并入**的：清单每次都报全量已并入，累计计入会让
    # 「哪一轮导的」永远说不清。
    already = {name for r in rounds for name in r.get("imported", [])}

    def stamp(entry: dict) -> None:
        """把本次调用取到的事实盖进轮次条目（新轮与幂等轮共用）。"""
        entry["materials"] = reference
        if analysis_sha:
            # 同一轮内分析件会从盘点版演进到完整版，照实更新，不当成新一轮
            entry["analysis"] = {"path": "AR/init-analysis.md", "sha256": analysis_sha}
        if positioning:
            entry["positioning"] = positioning
        if scope_options:
            entry["scope_options"] = scope_options

    # 材料没变就不是新一轮。「幂等」只意味着**不新建轮次**，不意味着不更新事实。
    if rounds and (rounds[-1].get("materials") or {}).get("digest") == digest:
        current = rounds[-1]
        stamp(current)
        fresh = sorted(set(ingested) - (already - set(current.get("imported", []))))
        if fresh:
            current["imported"] = fresh
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        consume_sidecar(feature_root, SCOPE_OPTIONS)
        log(f"材料未变（{digest}），仍在第 {current['round']} 轮（已刷新事实快照）")
        return {"round": current["round"], "created": False, "materials": digest,
                "positioning": bool(current.get("positioning")),
                "scopeOptions": len(current.get("scope_options") or [])}

    # 收口之后材料又变了：**不开新轮**。收口的含义是「本轮范围已定、可以进 spec」，
    # 此后补一份说明文件、改一个错字都不该把流程推回未定状态。
    #
    # 开轮的代价是死锁：新轮没有任何决策，而 `decide` 被 status=complete 挡住，
    # 于是既走不下去也退不回来，只能去手改契约文件——那在正式路径上不允许。
    # 要重新决策请显式跑 `reopen`。
    #
    # **判的是「收口及之后」不是「恰好在 complete」**：`story_written` 与已归档比它更靠后，
    # 而 story 的材料快照就是当轮的 digest——新轮一开，快照所指就换了一批材料，
    # 那份已经定稿的 story 就对不上它自己声称的依据了。
    if after_complete(contract) and rounds:
        current = rounds[-1]
        stamp(current)
        current["materials_changed_after_complete"] = {
            "digest": digest, "at": now(),
            "note": "收口后材料有变；未开新轮。要重新决策跑 `story_flow.py reopen`",
        }
        save(feature_root, contract)
        consume_sidecar(feature_root, POSITIONING)
        consume_sidecar(feature_root, SCOPE_OPTIONS)
        log(f"收口后材料有变（{digest}）：只更新第 {current['round']} 轮的材料指纹，未开新轮。"
            "要重新决策跑 `story_flow.py reopen`")
        return {"round": current["round"], "created": False, "materials": digest,
                "afterComplete": True,
                "positioning": bool(current.get("positioning")),
                "scopeOptions": len(current.get("scope_options") or [])}

    entry = {
        "round": len(rounds) + 1,
        "imported": sorted(set(ingested) - already),
        "analysis": None,
        "materials": reference,
        "positioning": None,
        "scope_options": None,
        "gates": [],
    }
    stamp(entry)
    rounds.append(entry)
    save(feature_root, contract)
    consume_sidecar(feature_root, POSITIONING)
    consume_sidecar(feature_root, SCOPE_OPTIONS)
    log(f"登记第 {entry['round']} 轮（材料 {digest}，本轮并入 {len(entry['imported'])} 件）")
    return {"round": entry["round"], "created": True, "materials": digest,
            "positioning": bool(entry.get("positioning")),
            "scopeOptions": len(entry.get("scope_options") or [])}


# ---------------------------------------------------------------------------
# decide：追加一条关卡决策

def supplement_has_material(feature_root: Path, current: dict) -> bool:
    """「补充材料」这一笔成不成立——**料到了没有**，两条路都算数。

    一是收件箱里还有没并入正文的原件（先签后导：人签完这一笔再去放料）；
    二是磁盘材料指纹已经不等于本轮登记的那个（先导后签：料先到了，人再回一句
    「已放入需求目录」）。只认第一条的话，后一种顺序会被判成「inbox 无新料」而驳回，
    人明明已经把料给了。

    两条都走磁盘不走账本：材料清单拿收件箱那批料重转一遍与正文比对，同名原件被换了
    内容也照样算新料，而这是任何一份「导过什么」的名单都记不住的。
    """
    try:
        manifest = materials.refresh(feature_root)
    except materials.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    pending = [name for name in materials.pending(manifest)
               if name.lower() not in SKIP_INBOX]
    if pending:
        return True
    return manifest["digest"] != (current.get("materials") or {}).get("digest")


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
        raise FlowError(
            f"关卡决策只认人签（--by human），实为「{args.by}」——"
            "材料够不够、范围怎么定由人拍板；你的判断写进选项推荐里，不代签")
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
    # 后两级不读它，但盘上留着别级的侧车仍要拦：那说明摆选项与走流程对不上，
    # 放过去的话，第一级下一次会把这份别人的侧车读成「材料又有新缺口」。
    if gate == "material_scope":
        options = read_gate_options(feature_root, gate)
        if chosen not in MATERIAL_CHOICES:
            raise FlowError(
                f"material_scope 的 --chosen 须为 {' / '.join(MATERIAL_CHOICES)} 之一，实为「{chosen}」")
    elif gate == "scope_decision":
        at = sidecar_gate(feature_root)
        if at and at != gate:
            raise FlowError(f"盘上的选项侧车是给 {at} 级摆的，这一步是 {gate}——先清掉或改对级别")
        # 分析定几项就只能摆几项：现编的空壳选项在此被结构性挡住
        options = current.get("scope_options") or []
        if not options:
            raise FlowError(
                f"本轮尚未登记范围定法选项集：把需求分析产出的全部选项写进 "
                f"{'/'.join(SCOPE_OPTIONS)} 后重跑 `round`")
    else:  # split_carrier
        at = sidecar_gate(feature_root)
        if at and at != gate:
            raise FlowError(f"盘上的选项侧车是给 {at} 级摆的，这一步是 {gate}——先清掉或改对级别")
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
        if not supplement_has_material(feature_root, current):
            outcome, code = "rejected", 2
            reason = ("材料没有变化：请把文档或界面设计图放进 "
                      f"{feature_root.name}/inbox/ 后再选一次"
                      "（已经放进来并导入过的，材料指纹会变，这一笔照样成立）")

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


#: 进 spec 的授权：`/story` 启动时就声明了范围，收口这一步原样回显。
#: 不回显的话，模型在阶段边界只能按 framework 的默认策略再问一次——它没错，是链没接上。
SPEC_STAGE_AUTHORIZATION = (
    "本轮授权：`/story <AR>` 的启动语义是「做到 spec 闭环并通过交付门」（batch 多阶段声明），"
    "spec 阶段在声明范围内，**不必再要一次授权**；plan 及其之后仍按 framework 默认策略停等。")

#: 这一段的顺序，四个分支共用一句。
SPEC_STAGE_ORDER = (
    "动笔前先取本阶段的作者要求：原则页 `doc/extensions/hooks/spec/author.md`，"
    "本次任务包 `node doc/extensions/hooks/spec/author.mjs --feature <名>`"
    "（其余阶段各读 `doc/extensions/hooks/<阶段>/author.md`）。"
    "顺序：knowledge-use init → 逐条填判断 → 写 spec.md 与 §9 → "
    "story-build skeleton → 逐章 chapter → 统稿 → story_flow.py story 登记"
    "（它自己跑 number / build / check，review 一并渲染并核过归档件红线）→ harness → verifier。"
    "**harness 放在成文登记之后**——之前跑它一定红在「三份产物不齐」")


def spec_stage_step(feature_root: Path) -> tuple[str, str]:
    """收口之后、成文登记之前——spec 阶段内做到哪儿了。

    手上没有这一段的顺序时，作者会先跑 harness，再靠门禁一轮轮告诉它还差什么——
    而那些红全是「产物不齐」。顺序本身是确定的，按磁盘上有什么就能说清。
    """
    def have(*rel: str) -> bool:
        return (feature_root / Path(*rel)).is_file()

    if not have("spec", "knowledge-use.yaml"):
        return ("spec_knowledge_use_init",
                SPEC_STAGE_AUTHORIZATION
                + " 进 /spec：第一步 `knowledge-use.mjs init --feature <名>` 生成判断骨架"
                "（激活条目一条不落，你只填 applicable 与依据）。" + SPEC_STAGE_ORDER)
    if not have("spec", "spec.md"):
        return "spec_write", "判断骨架已在。接着写 spec.md（§10/§11 由 render 生成，不手写）。" + SPEC_STAGE_ORDER
    if not have("AR", "story.md"):
        return ("story_skeleton",
                "spec.md 已在。**先重取一次任务包**"
                "（`node doc/extensions/hooks/spec/author.mjs --feature <名>`）"
                "——spec 刚写完，它里面的图这时候才列得出来。"
                "接着 `story-build skeleton` 建骨架，再逐章 `chapter --from <文件>`"
                "（章文件只放正文，不带章标题）。" + SPEC_STAGE_ORDER)
    return ("register_story",
            "story.md 已在。十章都写完、`story-build check` 通过之后，"
            "跑 `story_flow.py story` 登记成文——**登记之前跑 harness 一定红**。" + SPEC_STAGE_ORDER)


def sidecar_shape(step: str) -> dict | None:
    """这一步要写的侧车长什么样：字段、合法值、为什么要它。

    形状是确定的，该在需要它的那一步就摆出来，而不是等作者去读源码或撞报错。
    合法值取自本模块的常量，不另立一份。
    """
    if step == "run_analysis":
        positioning = dict(POSITIONING_FIELDS)
        positioning["scope_source"] = " | ".join(SCOPE_SOURCES)
        return {
            "写这两份": [
                {"path": "/".join(POSITIONING), "shape": positioning},
                {"path": "/".join(SCOPE_OPTIONS),
                 "shape": [{"key": CARRY_ALL, "label": "按当前范围整体承载：列出功能点"},
                           {"key": "<切法标识>", "label": "按什么切、切成几份",
                            "parts": [{"seq": 1, "scope": "这一份承载什么", "depends_on": []},
                                      {"seq": 2, "scope": "另一份承载什么", "depends_on": [1]}]}],
                 "note": f"固定首项 {CARRY_ALL} 必须在——不切永远是一个可选项；"
                         "切法至少两份，没有份表的切法是空壳"},
            ],
        }
    if step.startswith("await_gate:"):
        gate = step.split(":", 1)[1]
        return {
            "写这份，再去问人": {
                "path": "/".join(GATE_OPTIONS),
                "shape": {"gate": gate,
                          "options": [{"key": "<选项标识>", "label": "人能看懂的选项文字",
                                       "recommended": "true/false，可省"}]},
                "note": "先把摆给人的**全部**选项写进这份文件，再跑 `decide` 记录人选了哪个。"
                        "只记选中项，事后分不清「看过选项后这么选」与「压根没摆过选项」。"
                        f"`gate` 必须写 {gate}——三级共用一个文件名，不写明是给谁摆的，"
                        "上一级会把它当成自己这一级又出了新问题",
            },
            "顺序": "签与导入不分先后：料先到了再签、签完再去放料，两种都成立——"
                    "`decide --chosen supplement` 看的是料到没到"
                    "（inbox 里有未导入的，或材料指纹已经变了）",
        }
    return None


def material_gate_stops(feature_root: Path, contract: dict) -> bool:
    """第一级停不停：**第 1 轮无条件停；第 2 轮起，只在本级侧车摆在盘上时停。**

    第一轮没有任何人对材料表过态，必须停。此后每一轮都是材料变了才开出来的，
    而「材料变了」本身不是新问题——人上一次说的「补充材料」就是对「够不够」的回答。
    要再停一次，得是模型在新一轮**盘出了新的缺口**：那时它写一份本级的选项侧车，
    写了就停，没写就直接进分析。`decide` 会消费掉侧车，盘上留着的只会是这一轮新写的。

    判据不看上一轮选了什么。看那个的话，先导后签（料先到、人再签）与先签后导
    给出的答案不同——同一件事按顺序不同判出两种结果，而顺序本来就不该有讲究。
    侧车必须自报级别，否则模型为第二级摆的选项会被这里读成材料上的新缺口。
    """
    if len(contract.get("rounds") or []) <= 1:
        return True
    return sidecar_gate(feature_root) == "material_scope"


def next_step(feature_root: Path, contract: dict | None) -> tuple[str, str]:
    """流程位置的唯一判据：读契约，回答下一步该干什么。

    位置由数据回答而不由记忆回答——skill 正文因此不必维护成篇的「如果……那么……」，
    恢复一个中断的 feature 也不用靠翻对话。每个返回值都对应 SKILL.md 里的一个具体动作。
    """
    if contract is None or not contract.get("rounds"):
        return "run_round", "初析已生成的话，跑 `story_flow.py round` 登记本轮"
    if contract.get("status") == "story_written":
        # verifier 之后不再跑 harness：它每跑一次都重新派生 subject，换了代就要重审，而产物一个
        # 字节没动。只有 check-receipt 报 subject 失配时才重跑，那时 verifier 也要再来一次。
        return ("run_archived",
                "叙事件已登记成文（review.md 已在登记那一步渲染并核过）。"
                "按这个顺序走完，中间不回头："
                "跑 harness（spec 闭环）→ 按 harness 末尾 `NEXT:` 行派 verifier"
                "（它说没有审查员就直接下一步）→ check-receipt → "
                "`story-build check --deliver` 交付门。"
                "**交付门通过之后按它打印的选择走**：归档送审、进入 plan，或先归档再进 plan；"
                "本地单没有归档，只有进 plan。"
                "**verifier 之后不再跑 harness、不再改产物**；回执由 harness 生成，不用你填。"
                "verifier 报了阻断问题就跑 `story_flow.py reopen` 撤销成文登记，"
                "在草稿上改完重新登记——材料变了再审是正常返修，不是重复审")
    if contract.get("status") == "complete":
        return spec_stage_step(feature_root)

    current = contract["rounds"][-1]
    gates = round_gates(contract)

    # 第一级：材料够不够。**先于任何需求分析**——材料不全时做的范围判断注定作废，
    # 每轮补料都要重做一遍。所以这一级只需要材料盘点（清单 + 一句缺口判断）。
    material = last_gate(gates, "material_scope")
    if material is None and material_gate_stops(feature_root, contract):
        return ("await_gate:material_scope",
                "S3 第一级：**先摆选项侧车再问人**——带出材料清单与一句缺口判断，"
                "取得选择：补充材料 / 材料充足，开始需求分析")
    if material and material["chosen"] == "supplement":
        if material["outcome"] == "accepted":
            return ("import_and_reanalyze",
                    "回 S2：inbox/ 里还有未导入的就导入 → 重新盘点材料 → 重跑 `round`"
                    "（料在签之前就导进来了的话，这一步只剩重跑 `round`）")
        return "await_gate:material_scope", "补料被拒（材料没有变化），在第一级重新取得选择"

    # 材料已确认 → 才做需求粒度分析（全景 / 本部件 / 本 AR 定位 / 功能清单 / 范围定法选项）
    if not current.get("positioning") or not current.get("scope_options"):
        missing = []
        if not current.get("positioning"):
            missing.append(f"本 AR 定位 → {'/'.join(POSITIONING)}")
        if not current.get("scope_options"):
            missing.append(f"范围定法选项集 → {'/'.join(SCOPE_OPTIONS)}")
        return ("run_analysis",
                "S2b 需求粒度分析（材料已确认）：需求概览 → 本部件视角 → 本 AR 定位 → "
                "待实现功能清单 → 范围定法选项；落盘后重跑 `round`。"
                "本部件的职责范围与六类交互方在项目事实里，"
                "路径见任务包第 2 节的清单。"
                "待补：" + "；".join(missing))

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


def cmd_reopen(feature_root: Path) -> dict:
    """把收口的流程重新打开——**唯一的回退出口**。

    收口之后材料又变、而且变到需要重新拍板范围时走它。status 回到 `in_progress`，
    于是下一次 `round` 会照常开新轮、`decide` 也不再被挡。

    **已成文的话，成文登记一起撤销**：`story_written_at` 与 `story_src_digests` 是
    「这份 story 据以成文的依据」的快照。status 退回而它们留着就成了两说——流程说还没成文，
    契约里却记着成文时刻与台账指纹，而台账冻结只看 status，重开后台账可以重算，
    那份快照指的却是重算之前的东西。

    留痕：收口与成文都是有后果的判断，撤销它们同样是——没有留痕的话，
    产物为什么与当初那一轮对不上就查不回来了。
    """
    contract = require(load(feature_root))
    status = contract.get("status")
    if not after_complete(contract):
        raise FlowError(f"流程不在收口态（现在是 {status}），没有需要重新打开的东西")
    undone = {key: contract.pop(key) for key in ("story_written_at", "story_src_digests")
              if key in contract}
    contract["status"] = "in_progress"
    contract.setdefault("reopened", []).append({
        "at": now(),
        "from_status": status,
        "from_round": contract["rounds"][-1]["round"] if contract.get("rounds") else None,
        "story_registration_undone": sorted(undone),
    })
    save(feature_root, contract)
    log(f"流程已重新打开（{status} → in_progress）：下一次 `round` 会按材料现状开新轮"
        + ("；成文登记已一并撤销，story 要重新登记" if undone else ""))
    return {"status": "in_progress", "rounds": len(contract.get("rounds") or []),
            "storyRegistrationUndone": sorted(undone)}


def cmd_status(feature_root: Path) -> dict:
    contract = load(feature_root)
    step, action = next_step(feature_root, contract)
    shape = sidecar_shape(step)
    if contract is None:
        out = {"exists": False, "next": step, "action": action}
        if shape:
            out["sidecar"] = shape
        return out

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
        **({"sidecar": shape} if shape else {}),
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
    contract["design"] = {"sha256": materials.file_digest(feature_root / Path(*DESIGN))}
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
    """登记「叙事件已成文」——spec 阶段三份产物的第三份到位了。

    story 在 **spec 阶段内**成文：先建十章骨架，再按合同顺序一次写一章、
    经命令原子落盘。把它挪到 spec 之后当独立一步、由子 agent 一次写成整篇的话，
    两处都出过事——触发条件写「归档之前」而本地单没有归档，于是四个阶段全绿
    而 story 从来没被写出来；一次写成整篇是全有或全无，子 agent 返回空就什么都不剩。

    **登记自带门禁**：先重跑 `story-build check`，通过才记。守恒判据在那里，
    不在这里重实现——两处各判各的，迟早对不上。

    **编号之前先重投影**：附录的接口、数据、边界、判定四节是机器区，
    真源（spec §9、knowledge-use.yaml）在成文期间还会变——补一条规约判定、改一个
    接口出参。以登记这一次为准，`story-build project` 从当前真源重算一遍。

    **check 之前先编号**：章序、小节序、图序是纯确定性变换，由 `story-build number`
    统一铺——作者写业务名标题就够了。登记之后 story 冻结，所以编号必须在这之前完成；
    命令幂等，已经对的文件一个字节都不改。

    **只登记一次**：story 定稿于评审时点，评审回流只改 spec.md，不动 story。
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
    projected = subprocess.run(
        [node, str(checker), "project", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if projected.returncode != 0:
        raise FlowError(
            "story-build project 跑不通，成文态不予登记：\n"
            + (projected.stderr or projected.stdout or "").strip())
    numbered = subprocess.run(
        [node, str(checker), "number", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if numbered.returncode != 0:
        raise FlowError(
            "story-build number 跑不通，成文态不予登记：\n"
            + (numbered.stderr or numbered.stdout or "").strip())
    # review 也在这一步渲染：它的机器区按当前决策件重算，人工填的内容逐字节保留。
    # 不在这里渲染的话，下面那道 check 面对的是一份还不存在的 review——
    # 归档件红线（⑨）于是要等到交付门才报，而那时 story 已经冻结，只能 reopen 重来。
    rendered = subprocess.run(
        [node, str(checker), "build", "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if rendered.returncode != 0:
        raise FlowError(
            "story-build build 跑不通，成文态不予登记：\n"
            + (rendered.stderr or rendered.stdout or "").strip())
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
    # 台账随稿冻结：story 定稿了，它据以成文的账本也定稿了。指纹记在这里，
    # 之后 `story-build check` 拿它核对，`init` 直接拒绝重算。
    src = feature_root / "AR" / "story-src"
    for stray in sweep_story_src(src):
        log(f"清理中间件：{stray}")
    contract["story_src_digests"] = {
        name: ledger_digest(src / name) for name in STORY_SRC_FROZEN
    }
    # 草稿到此为止：story 冻结了，它就没有用途了；不进冻结台账，也不该留进归档。
    drafts = src / DRAFTS_DIR
    if drafts.is_dir():
        # 删不掉就不登记：Windows 上文件被占用是真会发生的事，而「已清理」
        # 一旦记进日志、状态又写成 story_written，草稿就跟着进了归档。
        shutil.rmtree(drafts, ignore_errors=True)
        if drafts.exists():
            raise FlowError(f"章草稿删不掉（{drafts}）：可能有编辑器占着文件。"
                            "关掉再跑一次——story 冻结后草稿不该留在需求目录里")
        log("章草稿已清理（story 已冻结）")
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
        raise FlowError("找不到 node：归档态登记要先重跑交付门，无法跳过")
    # 交付门而不是普通 check：走到这里 spec 该已经闭环，读者审查也该已经落报告。
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

    contract["archived"] = {
        "at": now(),
        "story": materials.file_digest(story),
        "review": materials.file_digest(review),
    }
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，装配只备份不重建")
    return {"archived": True, "at": contract["archived"]["at"]}
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="story init→spec 流程契约的唯一写入者")
    ap.add_argument("mode",
                    choices=["init", "round", "decide", "status", "complete", "reopen",
                             "story", "archived"])
    ap.add_argument("--feature", required=True)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--gate", default=None, choices=list(GATES),
                    help="关卡编号，缺省 material_scope")
    ap.add_argument("--chosen", default=None,
                    help="选中项的 key；material_scope 为 supplement / split / proceed")
    # 取值只剩 human：留着这个参数是为了让契约里那一栏仍然显式记着「谁签的」。
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
        elif args.mode == "reopen":
            result.update(cmd_reopen(feature_root))
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
