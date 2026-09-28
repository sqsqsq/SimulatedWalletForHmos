"""一次性侧车的读取、本 AR 的定位与选项，以及工作区骨架（`init`）。

侧车是 AI 写、脚本读、读完即销毁的文件：命令行参数只放标量，结构化数据一律走文件，
免得同一份 JSON 在不同 shell 下被二次解析成不同的东西。

AR 提取稿的空骨架在这里唯一维护——`submission` 判断「候选还是不是空骨架」用的是同一个
生成函数；两处各写一份的话，骨架一改，空判断就会漏。
"""
from __future__ import annotations

import json
from pathlib import Path

from flow.state import (
    system_requirement,
    CARRY_ALL, FlowError, GATES, SKILL_ROOT, STORY_CONTRACT, log)

# 拆分份表侧车：AI 写、脚本读，登记进契约后销毁（一次性）
SPLIT_PARTS = ("AR", "story-src", ".split-parts.json")
# 本 AR 定位侧车：三源核对后收敛出的当前范围结论。round 消费
POSITIONING = ("AR", "story-src", ".positioning.json")
# 范围定法选项集侧车：需求分析（S2b）产出的**全部**可选项。round 消费进契约，
# 第二级关卡此后只能从契约里取——见 read_scope_options 的注释
SCOPE_OPTIONS = ("AR", "story-src", ".scope-options.json")
# 材料关卡的缺口：盘点后写，`status` 据它算第一级的推荐，`decide` 记完即销毁
GAPS = ("AR", "story-src", ".material-gaps.json")


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
#: 「我还要料」的那一项：缺口文件里 missing 非空时推荐它。
MATERIAL_REQUEST_KEYS = tuple(o["key"] for o in _MATERIAL_OPTIONS if o.get("request"))


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
    "scope_text": "本 AR 当前范围，一句话；取全量时也要写出全量是什么",
    "sr_related_ars": "同一 SR 下的**其它** AR：[{ar, scope}]，没有就给空数组",
}


def read_positioning(feature_root: Path) -> dict | None:
    """读本 AR 定位侧车：初析三源核对后收敛出的「本 AR 当前范围」。

    这是整条拆分链的**判定对象**——不先把它定下来，后面的三类信号就没有施加对象，
    只能默默取上游全量：初析即使识别出「无预填说明」，若没有一步把该识别结果变成范围结论，
    SR 全量就会被当成本 AR 范围。

    脚本只存 AI「它无从得知」的判断（范围是什么、同 SR 还有哪些 AR），
    不代它判断——与 `import_sources.py` 的归类件同一条分工边界。
    """
    payload = read_sidecar(feature_root, POSITIONING)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise FlowError(f"{POSITIONING[-1]} 须是对象：含 scope_text / sr_related_ars")

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

    return {"scope_text": scope_text, "sr_related_ars": normalized}


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

    recommended = [str(o.get("key")) for o in payload if str(o.get("recommend") or "").strip()]
    if len(recommended) > 1:
        raise FlowError(f"{SCOPE_OPTIONS[-1]} 里有 {len(recommended)} 项写了 recommend："
                        "推荐至多一项，写在那一项的 recommend 里（一句理由）")

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
    # 顺序由契约定：整体承载固定在最前，其余照分析给出的顺序；推荐另起一行，不靠排位
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


def read_gaps(feature_root: Path) -> dict | None:
    """材料盘点的缺口：`{"missing": [还缺的材料…], "why": "一句缺口判断"}`。没写返回 None。"""
    payload = read_sidecar(feature_root, GAPS)
    if payload is None:
        return None
    where = GAPS[-1]
    if not isinstance(payload, dict):
        raise FlowError(f'{where} 须是对象：{{"missing": [还缺的材料], "why": "一句缺口判断"}}')
    missing = payload.get("missing")
    if not isinstance(missing, list) or not all(str(m).strip() for m in missing):
        raise FlowError(f"{where} 的 missing 须是数组，每项写一份还缺的材料；不缺就给空数组")
    why = str(payload.get("why") or "").strip()
    if not why:
        raise FlowError(f"{where} 缺 why：一句缺口判断——缺什么、为什么现有材料不够，或者为什么够了")
    return {"missing": [str(m).strip() for m in missing], "why": why}


def read_split_parts(feature_root: Path, feature: str) -> list[dict]:
    """读拆分份表侧车并校验。

    走文件不走参数：JSON 全是引号，任何 shell 都要对参数再解析一遍——同一条命令在
    bash 下原样送达、在 PowerShell 下双引号被吞。这条纪律本 skill 的所有脚本一致。

    份表回答的是「拆成几份、各归谁、什么顺序、谁依赖谁」；`scope_text` 不单独登记，
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


def read_ids(feature_root: Path, feature: str) -> dict[str, str | None]:
    """单号取自 `detail.json`——那是需求系统的拉取产物，没有它就是本地单。

    只读不造：伪造单号等于谎称本地单有系统单据。
    """
    def field(rel: str, key: str) -> str | None:
        path = feature_root / rel
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise FlowError(f"{rel} 不是合法 JSON：{exc}——它是需求系统的拉取产物，重新取材覆盖它") from exc
        value = data.get(key) if isinstance(data, dict) else None
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

    readme = SKILL_ROOT / "templates" / "inbox-readme.md"
    put("inbox/README.md", readme.read_text(encoding="utf-8"))

    local = not system_requirement(feature)
    missing = [rel for rel in ("RR/prd.md", "SR/design.md") if rel in created]
    log(f"工作区骨架：新建 {len(created)} 个文件"
        + (f"，保留已有 {len(kept)} 个" if kept else ""))
    if missing and not local:
        log(f"上游未拉到：{'、'.join(missing)}——已写占位件，"
            f"请把材料放进 {feature_root.name}/inbox/ 后走导入")
    return {"created": created, "kept": kept, "local": local, "placeholders": missing}
