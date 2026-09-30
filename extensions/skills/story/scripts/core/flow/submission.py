"""需求交给设计：关联设计对象（`bind-design`），冻结本轮采用的设计输入（`complete`）。

`complete` 不覆盖上游的 `AR/design.md`：候选提取稿作为派生分析进冻结集合，原件、图片与真实人签一起冻结，
再经原生来源检查，成功才登记 `input`。冻结的定义在 `materials/frozen.py`。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from materials import frozen, importer, registry

from flow import native
from flow.state import (
    DESIGN_DRAFT, FlowError, S4_STEPS, after_complete, in_update, load, log, now, require, save,
    system_requirement)
from flow.inputs import ar_design_skeleton, read_ids
from flow.routing import material_state, scope_step


#: 提取稿的五段：代码围栏外、带序号的二级标题。序号后的点可有可无。
S4_HEADING = re.compile(r"^##\s+(\d+)\s*\.?\s+\S")
#: 设计输入的默认落点：模型写采用集合、人签编号与语义条目
DESIGN_INPUT = ("AR", "story-src", "design-input.json")


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

    空骨架不是上游给的东西，正文只有段标题和写给模型的判定指引：它被覆盖不必备份，
    交上来当提取稿也不算写过。
    """
    return text.replace("\r\n", "\n") == ar_design_skeleton(read_ids(feature_root, feature))


def candidate_problems(feature_root: Path, feature: str, text: str) -> list[str]:
    """提取稿立不立得住——**只核结构，不核内容**。

    内容对不对由设计与评审看。这里挡的是「交上来的还是那份空骨架」和
    「五段结构塌了」：两样都会让设计的输入从一开始就缺一块。
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


def cmd_bind_design(feature_root: Path, project_root: Path, component: str, blueprint: str) -> dict:
    """需求关联的设计对象：首次写入，同值重复不改一个字节，别的值冲突。

    标识按原生规则核；蓝图已在时核它实际归属的组件。关联之后不自动改绑——绑错了重新起单。
    """
    contract = require(load(feature_root))
    component, blueprint = str(component or "").strip(), str(blueprint or "").strip()
    if not component or not blueprint:
        raise FlowError("bind-design 要 --component 与 --blueprint：新需求的蓝图标识通常就是需求标识，但要显式给出")
    wanted = {"component_id": component, "blueprint_id": blueprint}
    bound = contract.get("design_binding")
    if bound == wanted:
        return {"design_binding": bound, "bound": False}
    if bound:
        raise FlowError(f"本需求已关联 {bound['component_id']}/{bound['blueprint_id']}，不改绑；关联错了按新需求重新起单")
    checked = native.call(project_root, "binding", "--component", component, "--blueprint", blueprint)
    if checked["status"] != "ok":
        raise FlowError(f"设计对象核不过：{native.issues_text(checked)}")
    contract["design_binding"] = wanted
    save(feature_root, contract)
    log(f"需求关联设计对象 {component}/{blueprint}（蓝图{'已在' if checked.get('exists') else '尚未建立'}）")
    return {"design_binding": wanted, "bound": True, "blueprint_exists": bool(checked.get("exists"))}


def cmd_complete(feature_root: Path, project_root: Path, feature: str, from_arg: str | None,
                 input_arg: str | None) -> dict:
    """冻结本轮设计输入并登记，交给设计。

    前置：已关联设计对象；本轮范围已定（update 期间沿用已定范围）；收件箱没有待导入的原件；
    材料与本轮登记的一致。同一候选、采用集合与人签复用同一版本；已登记一版之后换输入要先 reopen 或开 update。
    失败时候选与诊断留在原处，已登记的输入不变。
    """
    contract = require(load(feature_root))
    binding = contract.get("design_binding")
    if not binding:
        raise FlowError("还没关联设计对象：先跑 `story_flow.py bind-design --component <组件> --blueprint <蓝图>`")
    candidate = resolve_candidate(feature_root, from_arg)
    try:
        cand_text = candidate.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FlowError(f"提取稿不是 UTF-8：{from_arg}") from None
    problems = candidate_problems(feature_root, feature, cand_text)
    if problems:
        raise FlowError("提取稿还不能提交：" + "；".join(problems))

    current = contract["rounds"][-1]
    try:
        live = registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    state = material_state(feature_root, current, live)
    if state["pending"]:
        raise FlowError("收件箱里有还没并入正文的原件，先导入再提交：" + "、".join(state["pending"][:3]))
    if live.get("digest") != (current.get("materials") or {}).get("digest"):
        raise FlowError("材料在这一轮登记之后又变了：重跑 `story_flow.py round` 登记，拿新材料重新确认，再提交")
    if not in_update(contract) or current.get("reopened"):
        step, action = scope_step(feature_root, contract)
        if step not in S4_STEPS:
            raise FlowError(f"本轮范围尚未定下来，还不能提交：{action}（`status` 的 next 是 {step}）")
    if contract["split"]["decided"] == "split" and \
            not str(contract["split"].get("scope_text") or "").strip():
        raise FlowError("拆分已定案但 split.scope_text 为空：范围文字丢失")

    input_rel = str(input_arg or "/".join(DESIGN_INPUT)).strip()
    try:
        design_input = frozen.read_input(feature_root, frozen.need_relative(input_rel, "--input"))
        cand_rel = candidate.resolve().relative_to(feature_root.resolve()).as_posix()
        version = frozen.freeze(feature_root, contract, design_input, live, cand_rel, now())
    except frozen.FrozenError as exc:
        raise FlowError(f"设计输入冻结不了：{exc}") from exc
    snapshot_dir = f"{importer.features_dir(project_root)}/{feature_root.name}/{'/'.join(frozen.INPUTS)}/{version['version']}"
    wanted = {"snapshot_ref": f"{snapshot_dir}/{frozen.SNAPSHOT}", "snapshot_sha256": version["snapshot_sha256"],
              "materials_digest": live["digest"], "candidate_sha256": frozen.digest(candidate.read_bytes())}
    registered = contract.get("input")
    if registered == wanted:
        log("这一版设计输入已经登记过，复用")
        return {"status": contract.get("status"), "input": registered, "committed": False}
    if registered and after_complete(contract) and not in_update(contract):
        raise FlowError("本需求已登记一版设计输入，设计按它进行中；换输入先 `story_flow.py reopen` 重新确认范围，"
                        "或按 `phases/update.md` 开一轮 update")

    doc = frozen.materialization(version, snapshot_dir, binding)
    system = system_requirement(feature)
    if system:
        path = version["dir"] / frozen.MATERIALIZATION
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    checked = native.call(project_root, "sources", stdin=doc)
    if checked["status"] != "ok":
        raise FlowError(f"原生来源检查没过，输入未登记（冻结版本 {version['version'][:12]} 留在原处）：{native.issues_text(checked)}")

    contract["input"] = wanted
    contract["status"] = "complete"
    save(feature_root, contract)
    log(f"设计输入已冻结并登记：{wanted['snapshot_ref']}")
    return {"status": "complete", "input": wanted, "committed": True,
            "design_entry": {"snapshot_ref": wanted["snapshot_ref"],
                             **({"materialization": f"{snapshot_dir}/{frozen.MATERIALIZATION}"} if system
                                else {"current_scope_items": doc["items"]})}}
