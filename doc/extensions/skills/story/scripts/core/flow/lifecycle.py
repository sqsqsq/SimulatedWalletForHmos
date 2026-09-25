"""只读与登记类命令：`status` 报位置，`story` 登记成文态，`archived` 记归档。

`story` 与 `archived` 沿正式命令路径调用 `story-build.mjs` 做成文检查，不反向导入入口。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from flow.state import (
    CORE_DIR, DESIGN, FlowError, REVIEW, STORY, STORY_SRC_FROZEN, ledger_digest, load, log,
    now, require, round_gates, save)
from flow.routing import live_materials, material_state, next_step, sidecar_shape
from flow.meetings import topic_digest
from materials import meeting


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
    # 不从 `next` 的字面值反推——字面值只认得出其中一种情况。没有轮次时没有基准可比，
    # 给 null，不用 false 冒充「材料没问题」。
    state = material_state(feature_root, current, manifest) if manifest is not None else None
    topics = topic_digest(feature_root, meeting.read_notes(feature_root, []), contract)
    return {
        "exists": True,
        "schema": contract.get("schema"),
        "status": contract.get("status"),
        # 成文登记的时刻：story 定稿于这一刻，重开会把它撤掉
        "story_written_at": contract.get("story_written_at"),
        "round": current.get("round"),
        "positioning": current.get("positioning"),
        "gates": [{"gate": g.get("gate"), "chosen": g.get("chosen"),
                   "outcome": g.get("outcome"), "by": g.get("by")} for g in gates],
        "split": contract.get("split", {}).get("decided"),
        "design": bool((feature_root / Path(*DESIGN)).is_file()),
        "archived": bool(contract.get("archived")),
        "material_state": ({"pending": state["pending"], "changed": state["changed"]}
                           if state else None),
        # 会议话题在这里机械枚举一次：全部版本、全部话题，含不属于本需求与归属判不准的。
        # 模型据它向人呈现，不必自己把 notes 再列一遍；只在读会与摆关卡那几步给，别的步骤用不上它。
        **({"meetings": topics} if topics and "meeting" in step else {}),
        "next": step,
        "action": action,
        **({"sidecar": shape} if shape else {}),
    }


def cmd_story(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已成文」——spec 阶段三份产物的第三份到位了。

    story 在 **spec 阶段内**成文：先建十章骨架，再按合同顺序一次写一章、经命令原子落盘。
    成文有 spec 的阶段边界守着；逐章落盘让中途失败只影响那一章。

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
    status = contract.get("status")
    if status == "story_written":
        raise FlowError("成文态已经登记过：story 定稿于登记那一刻，只登记一次。"
                        "要改先跑 `story_flow.py reopen`，按它给出的下一步走")
    if status != "complete":
        # reopen 之后直接来登记的常见一步：说出现在该做什么，不只说「不行」。
        # 下一步要按磁盘现状读材料；读不出来时「还没收口」照样先说，原因附在后面。
        try:
            _, action = next_step(feature_root, contract, live_materials(feature_root))
        except FlowError as exc:
            action = f"暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取下一步"
        raise FlowError(f"流程还没收口（status 是 {status}），成文态无从登记。下一步：{action}")
    story = feature_root / Path(*STORY)
    if not story.is_file():
        raise FlowError("AR/story.md 不存在：没有成文，无可登记的成文态")

    checker = CORE_DIR / "story-build.mjs"
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
    # 之后 `story-build check` 拿它核对，`skeleton`、`project` 与 `chapter` 直接拒绝重算。
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
            raise FlowError(f"{name} 不存在：归档件不全，无可登记的归档态")

    checker = CORE_DIR / "story-build.mjs"
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

    contract["archived"] = {"at": now()}
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，装配只备份不重建")
    return {"archived": True, "at": contract["archived"]["at"]}
