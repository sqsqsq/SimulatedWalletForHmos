"""story_flow.py — init→spec 流程契约（`AR/story-src/story-flow.json`）的**唯一写入者**。

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
    python story_flow.py complete --feature <AR> --from AR/story-src/design-draft.md
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
    2  仅 decide：选择已记录，但校验不通过，**不得前进**（如说了料已放进 inbox，盘上却没有）

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
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import import_sources
import materials

SCHEMA = 3
CONTRACT = ("AR", "story-src", "story-flow.json")
ANALYSIS = ("AR", "story-src", "init-analysis.md")
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
# S4 提取稿的落点。**输入与输出分开**：`AR/design.md` 是上游给进来的输入件，
# 模型把提取结果写在这里，由 `complete` 提交上去。写在同一个文件里的话，
# 材料指纹会因为自己的输出而变，流程被自己推回未定状态。
DESIGN_DRAFT = ("AR", "story-src", "design-draft.md")
# 被覆盖前的那一份外部 AR 输入，按轮次留存。它是来源追溯用的原件：
# 提交之后 `AR/design.md` 里是本轮的提取稿，上游原话只在这里还找得到。
AR_SOURCES = ("AR", "story-src", "sources", "ar")
# 到了这两步就意味着**本轮范围已定**，S4 可以做。候选稿在不在由 `complete` 自己核，
# 不借道 next_step——候选可以由 `--from` 指到别处，而 next_step 只认默认落点。
S4_STEPS = ("generate_design", "run_complete")
# 成文态登记时随稿冻结的台账：story 定稿了，它据以成文的账本也就定稿了。
# 登记之后重跑 init 会把这几份重算一遍：story.md 冻了，账本被后一次重跑冲掉。
STORY_SRC_FROZEN = (
    "decisions.json", "copyedit.md",
)
# 三级关卡，**每级只问一件事**：材料 → 范围怎么定 → 承载哪一份。
#
# 分三级而不是并成一问：材料与范围是两个维度，挤在一级人得同时权衡两件不相干的事。
# 而它们本有先后——材料不全时范围判断本身就不可靠，在一个还会变的范围上讨论怎么切，
# 讨论了也白讨论。
GATES = ("material_scope", "scope_decision", "split_carrier")
#: 章节合同。第一级的选项集登记在它的 `gates.material_scope.options` 里，本脚本与
#: `flow-check.mjs` 都从那里读——两边各存一份字面的话，只改一处，`decide` 写进契约的
#: 选择会在阶段门禁上被判非法。
STORY_CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "story-chapters.json"
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


class FlowError(Exception):
    """可预期的失败：带可执行的补救动作，直接呈给人。退出码 1，不写盘。"""


def material_options() -> list[dict]:
    """第一级摆给人的选项：键、默认 label、是不是一次「我还要料」的请求。"""
    try:
        data = json.loads(STORY_CONTRACT.read_text(encoding="utf-8").lstrip("\ufeff"))
        options = data["gates"]["material_scope"]["options"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FlowError(
            f"{STORY_CONTRACT.name} 的 gates.material_scope.options 读不出来（{exc}）："
            "第一级的选项集登记在那里") from exc
    return options


_MATERIAL_OPTIONS = material_options()
#: 第一级的值域是闭合的；第二、三级的值域由本次选项集自己定义（维度名、份序号），
#: 统一由「chosen 必须在 options 里」把关，不为每级各写一套枚举。
MATERIAL_CHOICES = tuple(o["key"] for o in _MATERIAL_OPTIONS)
#: 「我还要料」的那一项。第 2 轮起它要写清剩余缺口（见 read_gate_options）；
#: 「现有材料就是全部」不在其中——那不是缺口。
MATERIAL_REQUEST_KEYS = tuple(o["key"] for o in _MATERIAL_OPTIONS if o.get("request"))


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


def read_gate_options(feature_root: Path, gate: str,
                      round_no: int = 1) -> list[dict]:
    """读本次关卡摆出的选项集，并核它摆的就是这一级。

    每项必须有 `key`（选项标识），其余字段随关卡自由（label / scope / recommended /
    dimension …）——统一只约束标识，是为了让「chosen 必须在 options 里」这条校验
    对三级关卡通用，不必为每个关卡各写一套值域。

    **第 2 轮起，材料级里提出补料请求的那些选项还要写 `missing` 与 `why`**
    （还缺什么、为什么现有材料不够）：补齐一轮之后再停，问的必须是**剩余的**缺口，
    不能把上一轮的选项原样再摆一遍。要说得出缺什么，就得先拿新材料盘一遍。
    「继续分析」「调整范围」这类不是缺口，不受此限。
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

    # 第一级的 label 由合同给，作者写了也以合同为准——契约里留痕的必须是
    # **摆给人的那两句**，而它们是固定的。作者要说的缺口在 missing / why 里。
    if gate == "material_scope":
        fixed = {o["key"]: o["label"] for o in material_options()}
        for opt in options:
            opt["label"] = fixed.get(str(opt.get("key") or "").strip(), opt.get("label"))

    keys: list[str] = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项不是对象")
        key = str(opt.get("key") or "").strip()
        if not key:
            raise FlowError(f"{GATE_OPTIONS[-1]} 第 {i + 1} 项缺 key")
        if key in keys:
            raise FlowError(f"选项 key 重复：「{key}」——每项一个标识")
        if (gate == "material_scope" and round_no > 1
                and key in MATERIAL_REQUEST_KEYS):
            for field, what in (("missing", "还缺什么"), ("why", "为什么现有材料不够")):
                if not str(opt.get(field) or "").strip():
                    raise FlowError(
                        f"第 {round_no} 轮的「{key}」缺 {field}（{what}）——"
                        "补齐一轮之后再停，问的必须是剩余的缺口。"
                        "先用新增的材料重新盘点，说得出还缺什么再摆这个选项；"
                        "材料够了就不摆，直接进需求分析")
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
            entry["analysis"] = {"path": "/".join(ANALYSIS), "sha256": analysis_sha}
        if positioning:
            entry["positioning"] = positioning
        if scope_options:
            entry["scope_options"] = scope_options

    frozen = frozen_inbox_note(feature_root, contract, manifest)
    if frozen:
        log(frozen)

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

def frozen_inbox_note(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """收口及之后，收件箱里还躺着没导入的原件——**把它说出来**，没有就返回空串。

    这时不能顺手导：导入会改正文，而已经定稿的 story 声称的依据是当轮的材料快照，
    导完两边就对不上了。所以出口是显式的 `reopen`，不是静默导入。

    但不提它，那份文件从此没有任何人知道——`round` 只看已导入的指纹说「材料未变」，
    `status` 只说下一步走 spec 那条路。**下游没有动作时要说明为什么不适用，
    缺席不代表不适用。**
    """
    if not after_complete(contract) or not contract.get("rounds"):
        return ""
    pending = material_state(feature_root, contract["rounds"][-1], manifest)["pending"]
    if not pending:
        return ""
    more = f" 等 {len(pending)} 份" if len(pending) > 3 else ""
    head = f"收件箱里有 {len(pending)} 份还没导入的原件（{'、'.join(pending[:3])}{more}）："
    if contract.get("status") == "complete" and not contract.get("archived"):
        # 还没登记成文：这时的处置就是导入，与 `next` 给的动作是同一件事。
        return head + "先导入、再重跑 `round` 登记，它们并进正文之前不起稿"
    return head + ("story 已经冻结，要把它们纳入就先跑 `story_flow.py reopen`，"
                   "再导入、重跑 `round`；不纳入就留在收件箱，本轮不受影响")


def live_materials(feature_root: Path) -> dict:
    """按磁盘现状取一份材料清单 —— **同一个时点只取一次**，由调用链向内传。

    同一条命令里重复 build，是把同一批文件再哈希一遍、把收件箱再转一遍，
    而两次之间什么也没发生。写入前后是两个不同的时点，那时各取各的。
    """
    try:
        return materials.build(feature_root)
    except materials.MaterialError as exc:
        raise FlowError(str(exc)) from exc


def material_state(feature_root: Path, current: dict, manifest: dict | None = None) -> dict:
    """料现在什么样——**两个事实，一次问完**：谁还没并入正文、材料变没变。

    ``pending`` 是收件箱里还没导进正文的原件；``changed`` 是材料指纹与本轮登记的
    对不上（原件已经导进去了，本轮还没重新登记）。两者都走磁盘不走账本：材料清单
    拿收件箱那批料重转一遍与正文比对，同名原件被换了内容也照样算新料，而这是任何
    一份「导过什么」的名单都记不住的。

    **两件事互不替代**：`round` 登记新基准之后 `changed` 归假，而那份原件仍躺在
    收件箱里没并进正文——只看 `changed` 的消费者从此再也不会提到它。

    `manifest` 是调用方在这个时点已经取到的清单：传了就按它派生，不再读盘；
    显式判 ``None``，合法的空清单不会被当成「没传」偷偷改回重读。
    不写盘：`status` 只回答现在是什么样，落盘归 `round`。
    """
    if manifest is None:
        manifest = live_materials(feature_root)
    return {"pending": materials.pending(manifest),
            "changed": manifest["digest"] != (current.get("materials") or {}).get("digest")}


def pending_import_step(state: dict) -> tuple[str, str] | None:
    """收件箱里还躺着原件时的下一步 —— **收口前后同一句**：先导入。

    登记新基准不等于原件已经并入：`round` 刷新之后「材料变了」这条判据不再响，
    而那份文件仍在收件箱里。两处各写一句的话，其中一句迟早只说「材料没变」。
    """
    if not state["pending"]:
        return None
    more = f" 等 {len(state['pending'])} 件" if len(state["pending"]) > 3 else ""
    return ("import_materials",
            "收件箱里有还没并入正文的原件，先导入："
            "`python doc/extensions/skills/story/scripts/core/import_sources.py --feature <名>`"
            f"（{'、'.join(state['pending'][:3])}{more}），导完重跑 `round` 盘点")


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
            "材料到齐没有、范围怎么定由人拍板；你的判断写进选项推荐里，不代签")
    if not (args.basis or "").strip():
        raise FlowError("--basis 不能为空：决策的依据（用户原话）是契约的审计价值所在")

    chosen = str(args.chosen or "").strip()
    if not chosen:
        raise FlowError("--chosen 不能为空")

    contract = require(load(feature_root))
    current = contract["rounds"][-1]
    # 本命令里的材料事实**首次需要时取一份**，此后三处共用它：前置路由、补料请求的
    # 驳回判断、末尾的下一步。这条路径不写材料，三处之间不会有第二个时点；
    # 契约变了（多记一条关卡）不改材料基准，`changed` 不必重算。
    manifest: dict | None = None

    def snapshot() -> dict:
        nonlocal manifest
        if manifest is None:
            manifest = live_materials(feature_root)
        return manifest

    # 只能做流程当前允许的那一步。顺序由 `next_step` 一处定义，decide 不自己判前置——
    # 两处各写一套「什么时候能做什么」，迟早对不上。
    #
    # **第一级例外，它问的是另一件事**：`next_step` 回答「下一步做什么」，
    # 而收件箱里有料时那一步是导入。人能不能表态与导入没做没关系——
    # 他可以放好料先答一句，也可以等导完再答，两种都是同一次表态。
    # 所以这一级的前置是「本轮这一级还没有定下来」，不比对 next 的字面。
    if gate == "material_scope":
        settled = last_gate(round_gates(contract), gate)
        if settled and settled["outcome"] == "accepted":
            raise FlowError(
                f"本轮第一级已经定了（{settled['chosen']}）——材料再变会开出新一轮，"
                "那时才轮到重新表态；现在按 `status` 的 next 往下走")
    else:
        expected, action = next_step(feature_root, contract, snapshot())
        if expected != f"await_gate:{gate}":
            raise FlowError(f"当前这一步不是 {gate}：{action}（`status` 的 next 是 {expected}）")

    # 选项来源按关卡分工——**只有第一级读侧车**，后两级从契约取，关卡摆不出分析没定的选项。
    # 后两级不读它，但盘上留着别级的侧车仍要拦：那说明摆选项与走流程对不上，
    # 放过去的话，第一级下一次会把这份别人的侧车读成「材料又有新缺口」。
    if gate == "material_scope":
        options = read_gate_options(feature_root, gate, current["round"])
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
    if gate == "material_scope" and chosen in MATERIAL_REQUEST_KEYS:
        # 人陈述的是事实：料放进去了。磁盘上却既没有待导入的原件、材料也没变，
        # 那这一笔记下去下一步无处可去——原地重提，让人再放一次。
        state = material_state(feature_root, current, snapshot())
        if not state["pending"] and not state["changed"]:
            outcome, code = "rejected", 2
            reason = ("收件箱里没有新文件、材料也没变：把文档或界面设计图放进 "
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
    # 下一步与 `status` 同一处算：两处各写一套「记完这一笔该干什么」，迟早对不上。
    step, action = next_step(feature_root, contract, snapshot())
    log(f"下一步：{action}")
    result["next"], result["nextAction"] = step, action
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
        note = {
            "写这份，再去问人": {
                "path": "/".join(GATE_OPTIONS),
                "shape": {"gate": gate,
                          "options": [{"key": "<选项标识>", "label": "人能看懂的选项文字",
                                       "recommended": "true/false，可省"}]},
                "第一级不用写 label": "那两句固定，脚本按 key 填；缺什么写进 missing / why",
                "note": "先把摆给人的**全部**选项写进这份文件，再跑 `decide` 记录人选了哪个。"
                        "只记选中项，事后分不清「看过选项后这么选」与「压根没摆过选项」。"
                        f"`gate` 必须写 {gate}——三级共用一个文件名，不写明是给谁摆的，"
                        "上一级会把它当成自己这一级又出了新问题",
            },
        }
    if step == "await_gate:material_scope":
        # 这一级问的是事实：料放进去了，或者现有材料就是全部。够不够仍由你盘点、
        # 由人定，机器不判——所以键是固定的两个，label 可以按本轮缺口改写。
        note["这一级摆哪两项"] = material_options()
    return note if step.startswith("await_gate:") else None


def material_gate_state(feature_root: Path, contract: dict) -> tuple[bool, str | None]:
    """第一级停不停，以及本级侧车缺什么——**一次问完**。

    停不停：第 1 轮无条件停；第 2 轮起，只在本级侧车摆在盘上时停。
    第一轮没有任何人对材料表过态，必须停。此后每一轮都是材料变了才开出来的，
    再停一次得是模型拿新材料**重新盘出了缺口**：那时它写一份本级的选项侧车，
    写了就停，没写就直接进分析。`decide` 会消费掉侧车，盘上留着的只会是这一轮新写的。

    判据不看上一轮选了什么：那一次回答的是上一轮的缺口，这一轮问的是**还缺什么**。
    侧车必须自报级别，否则模型为第二级摆的选项会被这里读成材料上的新缺口。

    **侧车立不立得住在这里一并判**（第二个返回值）：校验只写在 `decide` 里的话，
    顺序是 `status` 说停 → 人被问了一次 → `decide` 才拒收。人已经答过，
    缺的字段却要模型回头补，那一次询问白问了——而它问的正是「还缺什么」
    这件模型自己没说清的事。
    """
    if len(contract.get("rounds") or []) <= 1:
        return True, None
    if sidecar_gate(feature_root) != "material_scope":
        return False, None
    try:
        read_gate_options(feature_root, "material_scope",
                          contract["rounds"][-1].get("round", 1))
    except FlowError as exc:
        return True, str(exc)
    return True, None


def frozen_tail(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """冻结态的下一步末尾那一句：收件箱里有没有没人管的原件。`next` 本身不变。"""
    note = frozen_inbox_note(feature_root, contract, manifest)
    return f"。**另外**：{note}" if note else ""


def next_step(feature_root: Path, contract: dict | None,
              manifest: dict | None = None) -> tuple[str, str]:
    """流程位置的唯一判据：读契约，回答下一步该干什么。

    位置由数据回答而不由记忆回答——skill 正文因此不必维护成篇的「如果……那么……」，
    恢复一个中断的 feature 也不用靠翻对话。每个返回值都对应 SKILL.md 里的一个具体动作。

    `manifest` 是调用方这个时点已经取到的材料清单：路由与它给出的动作要跟同一份事实，
    消费者（`status` 的 JSON、起手预检）读的也是这一份，不在下游再各判一次。
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
                "在草稿上改完重新登记——材料变了再审是正常返修，不是重复审"
                + frozen_tail(feature_root, contract, manifest))
    if contract.get("status") == "complete":
        # 收口之后材料又变了，也要先说出来。收口那一刻登记的材料指纹是这一轮的依据，
        # 而 spec 与叙事件都按那批料写：两份落盘记录（清单与轮次）在文件被改之后
        # 仍然彼此相等，只有按磁盘现状重算才看得见。处置是 `round`——它把这次变化
        # 记到本轮（不开新轮），要重新决策才跑 `reopen`。**没有登记过基准不算「变了」**：
        # 那是轮次自己缺了材料指纹，由流程契约的判据报，处置也不是同一个。
        current = contract["rounds"][-1] if contract.get("rounds") else {}
        state = material_state(feature_root, current, manifest)
        # 未导入的原件先导入：它不会因为登记了新基准就并进正文，而此后没有任何
        # 判据会再提到它——那份材料从此没人知道。这一句与收口前共用同一处。
        pending = pending_import_step(state)
        if pending:
            return pending          # 尾巴说的就是同一件事，不再追加一遍
        base = (current.get("materials") or {}).get("digest")
        if base and state["changed"]:
            return ("refresh_round",
                    "材料在收口之后又变了：先跑 `story_flow.py round` 把这次变化登记到本轮"
                    "（它不开新轮；要重新走关卡重新决策，跑 `story_flow.py reopen`），"
                    "再继续 spec 阶段——spec 与叙事件都按本轮登记的那批料写"
                    + frozen_tail(feature_root, contract, manifest))
        step, action = spec_stage_step(feature_root)
        return step, action + frozen_tail(feature_root, contract, manifest)

    current = contract["rounds"][-1]

    # **已到的材料先处理完，再谈别的**——人回答没回答都一样。
    #
    # 收件箱里躺着原件而流程往下走的话，那份料要到成文登记时才被发现，
    # 在那之前的每一个判断都建立在一份不全的材料上。文件已经在盘上，
    # 导入是脚本的活，不用问人「放好了吗」。
    # 表态与导入互不挡路：第一级的 `decide` 看的是「这一级定没定」，不看这里给的是什么。
    # 收口之后不走这条——那时材料再变归 `reopen`，见上面 `story_written` 那支。
    state = material_state(feature_root, current, manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("run_round",
                "材料已经变了：重跑 `story_flow.py round` 登记新一轮，再拿新材料重新盘点")
    return scope_step(feature_root, contract)


def scope_step(feature_root: Path, contract: dict) -> tuple[str, str]:
    """本轮范围定到哪一级了——三级关卡与 S4。

    **不看材料新鲜度**：那是 `next_step` 在这之前判的。分出来是因为 S4 提交要在
    「自己刚写下的那一笔材料差异」之上问同一个问题，而那笔差异会让新鲜度判据说
    「材料变了」——两个问题挤在一个函数里，提交就只能在「重判范围」与
    「跳过范围检查」之间二选一。
    """
    current = contract["rounds"][-1]
    gates = round_gates(contract)

    # 第一级：材料。**先于任何需求分析**——材料不全时做的范围判断注定作废，
    # 每次补料都要重做一遍。所以这一级只需要材料盘点（清单 + 一句缺口判断）。
    material = last_gate(gates, "material_scope")
    stops, problem = material_gate_state(feature_root, contract)
    if material is None and problem:
        return ("fix_gate_options",
                f"这一级的选项侧车还立不住，先补齐再问人：{problem}")
    if material is None and stops:
        return ("await_gate:material_scope",
                "S3 第一级：**先摆选项侧车再问人**——带出材料清单与一句缺口判断，"
                "取得选择："
                + " / ".join(str(o.get("label") or o["key"]) for o in material_options()))
    if material and material["outcome"] == "rejected":
        return ("await_gate:material_scope",
                "上一笔被驳回（收件箱里没有新文件、材料也没变），在第一级重新取得选择")

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
    if not (feature_root / Path(*DESIGN_DRAFT)).is_file():
        return ("generate_design",
                "S4：按 rules/ar_design_init.md 提取，写到 "
                f"`{'/'.join(DESIGN_DRAFT)}`——`AR/design.md` 是上游给进来的输入件，"
                "提取稿另成一份，由收口那一步提交上去")
    return ("run_complete",
            "提取稿已在。跑 `story_flow.py complete --feature <名> "
            f"--from {'/'.join(DESIGN_DRAFT)}` 提交并收口")


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
    # 材料事实**一份**：路由、冻结提示与下面的 JSON 输出读的是同一个时点的清单。
    # 各自再 build 一次的话，同一条命令里会出现两份「现在的材料」，而消费者不知道
    # 自己拿的是哪一份。算不出来沿 FlowError 退出，不伪造 false。
    manifest = live_materials(feature_root) if (contract or {}).get("rounds") else None
    step, action = next_step(feature_root, contract, manifest)
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
    # 材料事实直接给出去：消费者（起手预检、作者包）按 pending/changed 判断，
    # 不再去猜 `next` 的字面值——那样只认得出其中一种情况。没有轮次时没有基准可比，
    # 给 null，不用 false 冒充「材料没问题」。
    state = material_state(feature_root, current, manifest) if manifest is not None else None
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
        "material_state": ({"pending": state["pending"], "changed": state["changed"]}
                           if state else None),
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

    readme = Path(__file__).resolve().parents[2] / "templates" / "inbox-readme.md"
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


#: 提取稿的五段：代码围栏外、带序号的二级标题。序号后的点可有可无。
S4_HEADING = re.compile(r"^##\s+(\d+)\s*\.?\s+\S")


def resolve_candidate(feature_root: Path, given: str | None) -> Path:
    """`--from` 指的那份提取稿。相对路径相对需求根，且必须落在需求根内。"""
    if not str(given or "").strip():
        raise FlowError("缺 --from：收口提交的是你写好的提取稿，"
                        f"落点 {'/'.join(DESIGN_DRAFT)}")
    raw = Path(str(given).strip())
    target = raw if raw.is_absolute() else feature_root / raw
    try:
        target.resolve().relative_to(feature_root.resolve())
    except (OSError, ValueError):
        raise FlowError(f"提取稿在需求目录外：{given}。它是本需求的产物，"
                        "路径按相对需求根写") from None
    if not target.is_file():
        raise FlowError(f"提取稿不在：{given}。按 rules/ar_design_init.md 提取，"
                        f"写到 {'/'.join(DESIGN_DRAFT)}，再跑这条命令")
    return target


def section_numbers(text: str) -> list[int]:
    """正文里的二级标题序号，按出现顺序。围栏里的标题不算——那是被引用的样例。"""
    out: list[int] = []
    fenced = False
    for raw in text.split("\n"):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        hit = S4_HEADING.match(line)
        if hit:
            out.append(int(hit.group(1)))
    return out


def is_ar_skeleton(feature_root: Path, feature: str, text: str) -> bool:
    """这份 AR/design.md 还是 `init` 落的空骨架。

    空骨架不是上游给的东西，正文只有段标题和写给模型的判定指引。把它留存成
    「本轮外部输入」的话，后续按原件读上游原话的作者与审查，
    就会把一份写给模型的指引当成需求原话。
    """
    return text.replace("\r\n", "\n") == ar_design_skeleton(read_ids(feature_root, feature))


def candidate_problems(feature_root: Path, feature: str, text: str) -> list[str]:
    """提取稿立不立得住——**只核结构，不核内容**。

    内容对不对由 spec 与评审看。这里挡的是「交上来的还是那份空骨架」和
    「五段结构塌了」：两样都会让 /spec 的输入从一开始就缺一块，而缺的那一块
    要到阶段门禁上才被发现，那时提取早已过去几步。
    """
    if not text.strip():
        return ["提取稿是空的"]
    if is_ar_skeleton(feature_root, feature, text):
        return ["提取稿与 init 落的空骨架逐字节相同：提取内容还没写"]
    numbers = section_numbers(text)
    if numbers[:5] != [1, 2, 3, 4, 5]:
        return ["五段结构对不上（rules/ar_design_init.md §3）：读到的二级标题序号是 "
                + (str(numbers) if numbers else "一个都没有")
                + "，要的是 1 简介 / 2 需求分析 / 3 SE 方案摘要 / 4 上游索引 / "
                  "5 上游已声明线索"]
    return []


def ar_input_identities(feature_root: Path, feature: str, contract: dict,
                        keep: Path) -> list[tuple[str, str | None]]:
    """被覆盖前那一份 AR 的合法身份：`(内容摘要, 原输入定位)` 逐一列出。

    三类来源各有确定证据——本轮已留存的原件、`init` 落的空骨架（不是外部输入，
    定位为 None；行尾两种形态都认）、契约里已登记的上一轮提取稿（沿它自己的
    origin）。这是「被覆盖的 AR 是谁」仅有的答案集：中间态识别与原输入定位
    共用这一份枚举，出现新场景时加在这里，不在调用方各自猜。
    """
    keep_rel = keep.relative_to(feature_root).as_posix()
    identities: list[tuple[str, str | None]] = []
    if keep.is_file():
        identities.append((materials.file_digest(keep), keep_rel))
    skeleton = ar_design_skeleton(read_ids(feature_root, feature))
    for text in (skeleton, skeleton.replace("\n", "\r\n")):
        identities.append(("sha256:" + sha256(text.encode("utf-8")).hexdigest()[:16], None))
    registered = contract.get("design") or {}
    if registered.get("sha256"):
        identities.append((registered["sha256"], registered.get("origin")))
    return identities


def prior_ar(feature_root: Path, feature: str, contract: dict,
             keep: Path, prior_sha: str | None) -> str | None:
    """被这次提交覆盖掉的那一份 AR，它的原输入定位。

    身份枚举见 `ar_input_identities`：留存件、空骨架、已登记提取稿三类各有
    确定证据，都对不上就说明这份 AR 的来历说不清——调用方据此停下，
    不能把一份来历不明的文件默认当成上游输入存进来源。
    """
    for sha, origin in ar_input_identities(feature_root, feature, contract, keep):
        if sha == prior_sha:
            return origin
    raise FlowError(
        f"AR/design.md 的来历说不清（摘要 {prior_sha}）：既不是本轮已留存的原件，"
        "也不是 init 的空骨架或契约里登记过的提取稿。先确认它是谁写的，"
        "再跑收口——把一份来历不明的文件存成上游输入，下游就会拿它当需求原话")


def cmd_complete(feature_root: Path, feature: str, from_arg: str | None) -> dict:
    """把提取稿提交为 AR/design.md 并收口。

    顺序固定：**留存原输入 → 覆盖 AR/design.md → 刷新材料与本轮基准 → 记 complete**。
    `complete` 最后写，所以中途断掉时状态仍是未收口，重跑同一条命令即可——
    每一步都能从磁盘现状认出自己做没做过，不靠回滚副本，也不另记一份进度。
    """
    contract = require(load(feature_root))
    candidate = resolve_candidate(feature_root, from_arg)
    cand_bytes = candidate.read_bytes()
    try:
        cand_text = cand_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FlowError(f"提取稿不是 UTF-8：{from_arg}") from None

    rel = "/".join(DESIGN)
    design_path = feature_root / Path(*DESIGN)
    design_bytes = design_path.read_bytes() if design_path.is_file() else None
    total = sum(len(r.get("gates", [])) for r in contract["rounds"])
    if after_complete(contract):
        if contract.get("status") == "complete" and design_bytes == cand_bytes:
            log("已经收口过了：AR/design.md 就是这份提取稿，没有重复提交")
            return {"status": "complete", "rounds": len(contract["rounds"]),
                    "gates": total, "committed": False}
        raise FlowError(
            "本轮已经收口，AR/design.md 里是已提交的那一份提取稿。要换掉它，"
            "先跑 `story_flow.py reopen` 重新走范围与收口——下游从收口那一刻起就在读它，"
            "悄悄换一份，读到的和登记的就成了两份")

    current = contract["rounds"][-1]
    base = (current.get("materials") or {}).get("digest")
    try:
        recorded = materials.read(feature_root)
        live = materials.build(feature_root)
    except materials.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    keep = feature_root / Path(*AR_SOURCES) / f"r{current.get('round', 1)}.md"
    keep_rel = keep.relative_to(feature_root).as_posix()
    # 本轮登记的那一版 AR/design.md 的身份。**清单可能已经按提交后的现状刷新过**
    # （断点落在刷新之后、契约保存之前）：那时被覆盖的那一份在三类合法身份里，
    # 哪一个换回 AR 那一格还能复现旧基准，哪一个就是本轮登记过的原输入——
    # 「除自己提交外材料未变」由此有确定答案。身份枚举与 prior_ar 共用同一份。
    prior_sha = None
    refreshed_unsaved = False
    if recorded.get("digest") == base:
        prior_sha = materials.source_sha(recorded, rel)
    else:
        for sha, _origin in ar_input_identities(feature_root, feature, contract, keep):
            if sha and materials.digest_with(live, rel, sha) == base:
                prior_sha = sha
                refreshed_unsaved = True
                break
    if prior_sha is None and recorded.get("digest") != base:
        raise FlowError(
            f"材料清单（{recorded.get('digest')}）与本轮登记的基准（{base}）对不上："
            "先跑 `story_flow.py round` 让轮次与清单归位，再收口")
    kept_is_prior = keep.is_file() and prior_sha is not None \
        and materials.file_digest(keep) == prior_sha
    # 覆盖已经发生过——这是同一条命令的重试。**判据是原输入还在不在**，不是候选一个
    # 字节没变：断点可能落在覆盖写到一半，那一刻盘上既不是原输入也不是完整候选；
    # 重跑之前又改一句提取稿也是正常的。留存件在、且摘要等于本轮登记的那一版，
    # 就证明上游原话已经保住，此后 `AR/design.md` 里是什么都是这条命令自己的中间产物。
    #
    # 反过来，只覆盖没留存时这里判不出重试：那份 AR 的来历没有证据，
    # 认成自己的写入等于把本轮真实的材料变化盖掉。
    retry = design_bytes == cand_bytes or kept_is_prior or refreshed_unsaved

    # 收件箱里还躺着原件时不收口：那时定的范围建立在一份不全的材料上。
    # 用的是上面那份 live——同一条命令、同一个写入前时点，不再把同一批材料转第二遍。
    state = material_state(feature_root, current, live)
    if state["pending"]:
        raise FlowError("收件箱里有还没并入正文的原件，先导入再收口："
                        + "、".join(state["pending"][:3]))
    # 材料必须仍与本轮基准一致。**AR/design.md 单独问**：重试时它已经是提取稿了，
    # 拿整份材料版本去判「变没变」，答案永远是变了；把它换回本轮登记的那一版再算，
    # 「其余材料动没动」才有确定答案。没重试过的话，它自己也必须还是登记的那一版。
    if materials.digest_with(live, rel, prior_sha) != base \
            or (not retry and live.get("digest") != base):
        raise FlowError("材料在这一轮登记之后又变了：重跑 `story_flow.py round` "
                        "登记新一轮，拿新材料重新盘点，再收口")

    # 收口的前置是**本轮范围已定**，而不是某一条特定记录——补料会开新一轮，
    # 上一轮定的范围不能替这一轮授权。判据与 next_step 同源（同一个 scope_step），
    # 定位/选项集缺失时它会报 run_analysis，不必在这里另判一遍。
    step, action = scope_step(feature_root, contract)
    if step not in S4_STEPS:
        raise FlowError(f"本轮范围尚未定下来，还不能收口：{action}（`status` 的 next 是 {step}）")
    if contract["split"]["decided"] == "split" and \
            not str(contract["split"].get("scope_text") or "").strip():
        raise FlowError("拆分已定案但 split.scope_text 为空：范围文字丢失，无法写入 design.md")
    problems = candidate_problems(feature_root, feature, cand_text)
    if problems:
        raise FlowError("提取稿还不能提交：" + "；".join(problems))

    registered = contract.get("design") or {}
    done: list[str] = []
    try:
        if retry:
            origin = prior_ar(feature_root, feature, contract, keep, prior_sha)
        elif design_bytes is None \
                or is_ar_skeleton(feature_root, feature,
                                  design_bytes.decode("utf-8-sig", errors="replace")):
            origin = None                        # 空骨架不是上游给的东西，没什么可留存
        elif registered.get("sha256") == prior_sha:
            origin = registered.get("origin")    # 是上一轮的提取稿：沿用它所指的原输入
        elif keep.is_file():
            raise FlowError(
                f"{keep_rel} 已存在，内容却与当前 AR/design.md 不同：同一轮的原输入"
                "只有一份。先确认这一轮到底是哪一份，别让覆盖抹掉另一份")
        else:
            # 上游这一轮给了新的 AR：先留存，再覆盖。覆盖之后上游原话只在这里还找得到。
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_bytes(design_bytes)
            done.append(keep_rel)
            origin = keep_rel

        if design_bytes != cand_bytes:
            design_path.parent.mkdir(parents=True, exist_ok=True)
            design_path.write_bytes(cand_bytes)     # 脚本只提交，不改一个字节
            done.append(rel)

        manifest = materials.refresh(feature_root)
        current["materials"] = {"path": "/".join(materials.MANIFEST),
                                "digest": manifest["digest"]}
        done.append("/".join(materials.MANIFEST))

        # 收口时的 design.md 身份登记：`sha256` 用于认出「上一轮的提取稿」——
        # 重试与跨轮的原输入定位都拿它对身份；`origin` 指出它盖掉的原输入在哪。
        # 它不是冻结比对基准：归档会用评审载体覆盖这份文件，拿登记哈希去比
        # 归档后的当前 AR 必然误报；成文依据的冻结比对走 story_src_digests 那一套。
        contract["design"] = {"sha256": materials.file_digest(design_path), "origin": origin}
        contract["design_generated_at"] = now()
        contract["status"] = "complete"
        save(feature_root, contract)     # **最后写**，同样在提交失败处理内：
        # 这里断了，清单已是新基准而流程契约还是旧的——重跑同一条命令，
        # 预检会凭留存件认出这个中间态，直接补上这次保存。
    except (OSError, materials.MaterialError) as exc:
        raise FlowError(
            f"提交中途失败（{exc}）。已完成：{'、'.join(done) or '无'}；"
            "流程仍是未收口，原输入与提取稿都在。修好之后重跑同一条 complete 命令"
        ) from exc

    log(f"流程收口：{len(contract['rounds'])} 轮、{total} 条关卡记录"
        + (f"；原输入留存于 {origin}" if origin else ""))
    return {"status": "complete", "rounds": len(contract["rounds"]), "gates": total,
            "committed": True, "origin": origin}


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
    # 之后 `story-build check` 拿它核对，`skeleton` 与 `build` 直接拒绝重算。
    #
    # 登记不动 `story-src/` 里的任何东西：章草稿、候选池、映射表都留在原地。
    # 它们走不漏到读者手上——归档只上传 story.md 与 review.md，`story-src/` 整层
    # 留在本地。留着的用处是实的：出了问题，它们是唯一能看出「这份 story 是怎么
    # 写出来的」的现场；`reopen` 撤销登记后作者要改某一章，手上也才有可改的东西。
    src = feature_root / "AR" / "story-src"
    contract["story_src_digests"] = {
        name: ledger_digest(src / name) for name in STORY_SRC_FROZEN
    }
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
                    help="选中项的 key；material_scope 为 " + " / ".join(MATERIAL_CHOICES))
    # 取值只剩 human：留着这个参数是为了让契约里那一栏仍然显式记着「谁签的」。
    ap.add_argument("--by", default="human", choices=list(ACTORS))
    ap.add_argument("--basis", default=None, help="决策依据：用户原话，或授权原话 + 推荐理由")
    ap.add_argument("--scope-text", default=None,
                    help="split_carrier 无份表侧车时的兜底：本 AR 的范围文字")
    ap.add_argument("--from", dest="from_path", default=None,
                    help="complete：要提交的提取稿，落点 " + "/".join(DESIGN_DRAFT))
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    result: dict = {"mode": args.mode, "reqNo": args.feature}
    try:
        project_root = Path(args.project_root).resolve() if args.project_root \
            else Path(__file__).resolve().parents[6]
        feature_root = project_root / import_sources.features_dir(project_root) / args.feature

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
            result.update(cmd_complete(feature_root, args.feature, args.from_path))

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
