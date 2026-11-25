"""一次性侧车的读取、本 AR 的定位与工作区骨架（`init`）。

侧车是 AI 写、脚本读、读完即销毁的文件：命令行参数只放标量，结构化数据一律走文件，
免得同一份 JSON 在不同 shell 下被二次解析成不同的东西。
"""
from __future__ import annotations

import json
from pathlib import Path

from flow.state import (
    system_requirement,
    FlowError, SKILL_ROOT, STORY_CONTRACT, log)

# 本 AR 定位侧车：三源核对后收敛出的当前范围结论。round 消费
POSITIONING = ("AR", "story-src", ".positioning.json")
# 材料关卡的缺口：盘点后写，`status` 据它算推荐，`decide` 记完即销毁
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


def cmd_init(feature_root: Path, feature: str) -> dict:
    """建工作区骨架——收件箱 `inbox/` 与它的说明的唯一写入者。

    **缺什么补什么，已有的一律不动**，因此它与取材结果无关：系统单取材之后跑，本地单直接跑，
    两条路径同一条命令，重跑安全。收件箱由此独立于数据对接层成立——那一层由各部署环境自备实现。
    缺哪类上游材料由材料索引按来源回答，不落占位件。
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

    readme = SKILL_ROOT / "templates" / "inbox-readme.md"
    put("inbox/README.md", readme.read_text(encoding="utf-8"))
    from materials import registry  # 延迟导入：materials 引用 flow
    try:
        registry.refresh(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    local = not system_requirement(feature)
    log(f"工作区骨架：新建 {len(created)} 个文件" + (f"，保留已有 {len(kept)} 个" if kept else ""))
    return {"created": created, "kept": kept, "local": local}
