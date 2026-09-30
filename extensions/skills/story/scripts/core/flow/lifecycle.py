"""只读与登记类命令：`status` 报位置，`story` 登记成文态，`archived` 记归档。

`story` 与 `archived` 沿正式命令路径调用 `story-build.mjs` 做成文检查，不反向导入入口。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from flow.state import (
    CORE_DIR, DESIGN, FlowError, REVIEW, S4_STEPS, STORY, STORY_REGISTERED, file_sha256, last_gate, load, log,
    now, require, round_gates, save, stage_of, PUBLISHED, short_digest)
from flow.routing import live_materials, material_state, next_step, sidecar_shape
from flow import asks
from flow.update import record_baseline, record_owned_after
from flow.meetings import topic_digest
from materials import meeting


#: 设计交接之后等设计的几步与成文的几步（路由给出），派生状态按它们归类
DESIGN_STEPS = ("design_blueprint", "fix_blueprint", "design_projection")
WRITING_STEPS = ("story_skeleton", "story_chapters", "register_story")


def derived_state(contract: dict | None, step: str) -> str:
    """需求现在处在哪一态：由契约与路由的同一次判断派生，不另存副本。

    gathering 材料未确认；scope_pending 范围未定；input_ready 可以冻结输入；waiting_for_design 输入已登记、
    蓝图没有或未准入（含投影无效）；ready_to_write 可以成文；needs_sync 已登记的输入或成文与现状不符；
    registered 成文已登记且与现状一致。update 的两段另由 `update` 字段给出。
    """
    if not contract or not contract.get("rounds"):
        return "gathering"
    status = contract.get("status")
    if status == "story_written":
        return "needs_sync" if step == "register_story" else "registered"
    if status == "complete":
        return ("waiting_for_design" if step in DESIGN_STEPS
                else "ready_to_write" if step in WRITING_STEPS else "needs_sync")
    confirmed = last_gate(round_gates(contract), "material_scope")
    if not confirmed or confirmed.get("outcome") != "accepted":
        return "gathering"
    return "input_ready" if step in S4_STEPS else "scope_pending"


def cmd_status(feature_root: Path) -> dict:
    contract = load(feature_root)
    # 材料事实**一份**：路由、收件箱提示与下面的 JSON 输出读的是同一个时点的清单。
    # 各自再 build 一次的话，同一条命令里会出现两份「现在的材料」，而消费者不知道
    # 自己拿的是哪一份。算不出来沿 FlowError 退出，不伪造 false。
    manifest = live_materials(feature_root) if (contract or {}).get("rounds") else None
    step, action = next_step(feature_root, contract, manifest)
    shape = sidecar_shape(step)
    # 到了停等点就生成问法并写侧车：人看到的选项块与 `decide` 核对的是同一份
    ask = asks.build(feature_root, contract, step) if contract and contract.get("rounds") else None
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
        # 最近一次成文登记的时刻；重跑 `story` 就是重新登记
        "story_written_at": contract.get("story_written_at"),
        "round": current.get("round"),
        "positioning": current.get("positioning"),
        "gates": [{"gate": g.get("gate"), "chosen": g.get("chosen"),
                   "outcome": g.get("outcome"), "by": g.get("by")} for g in gates],
        "split": contract.get("split", {}).get("decided"),
        "design": bool((feature_root / Path(*DESIGN)).is_file()),
        "archived": bool(contract.get("archived")),
        "state": derived_state(contract, step),
        **({"update": stage_of(contract)} if stage_of(contract).startswith("update_") else {}),
        "design_binding": contract.get("design_binding"),
        "input": contract.get("input"),
        "material_state": ({"pending": state["pending"], "changed": state["changed"]}
                           if state else None),
        # 会议话题在这里机械枚举一次：全部版本、全部话题，含不属于本需求与归属判不准的。
        # 模型据它向人呈现，不必自己把 notes 再列一遍；只在读会与摆关卡那几步给，别的步骤用不上它。
        **({"meetings": topics} if topics and "meeting" in step else {}),
        "next": step,
        "action": action,
        **({"ask": ask} if ask else {}),
        **({"sidecar": shape} if shape else {}),
    }


def cmd_story(feature_root: Path, project_root: Path) -> dict:
    """登记「Story 已成文」：按已准入蓝图写成、经独立审查的 story 与 review 就是要交付的这一份。

    **登记只读核对，不改被审对象**：附录重投、编号与 Review 渲染在准备审查时已经做完
    （`story-build review --action prepare`），登记这一步再动它们，审的就不是登记的那一份。依次核：

    1. 全篇结构检查（`story-build check`）通过；
    2. 这一份的独立审查结果（`story-build review --action check`）是 pass 或 warn——审的是现在这份；
    3. 这一刻的成文依据（`story-build basis`）：蓝图引用、交给设计的输入版本、激活知识摘要，
       加上 Story、Review、决策登记与写作设计的原始字节指纹。

    都成立才一次写入新依据；任一步不成立照实报出，已有的登记与依据原样保留（派生为待同步）。
    依据与已登记的相同时什么都不改。
    """
    contract = require(load(feature_root))
    status = contract.get("status")
    if status not in ("complete", "story_written"):
        # 重拍范围之后直接来登记的常见一步：说出现在该做什么，不只说「不行」。
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
        raise FlowError("找不到 node：成文态登记要先跑 story-build 的检查，无法跳过")

    def build(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([node, str(checker), *args, "--feature", feature_root.name, "--project-root", str(project_root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    checked = build("check", "--registering")
    if checked.returncode != 0:
        raise FlowError("story-build check 未通过，成文态不予登记：\n" + (checked.stderr or checked.stdout or "").strip())
    reviewed = build("review", "--action", "check")
    rows = [line for line in reviewed.stdout.splitlines() if line.startswith("{")]
    review = json.loads(rows[-1]) if rows else {}
    if reviewed.returncode != 0 or review.get("result") not in ("pass", "warn"):
        raise FlowError(f"这一份的独立审查还不能消费（{review.get('result', '读不到结果')}）：{review.get('detail', (reviewed.stderr or '').strip()[:600])}"
                        "——按 `phases/design.md`「五、独立审查、登记与交付」处置，审查通过再登记")
    basis = build("basis")
    if basis.returncode != 0:
        raise FlowError("成文依据取不到，成文态不予登记：\n" + (basis.stderr or basis.stdout or "").strip())

    # 登记记下 story、review 与它们据以成文的决策登记、写作设计此刻的指纹：之后 `story-build check`
    # 与流程路由拿它核「登记之后改过没有」，改过就重新审查、重新登记。
    #
    # 登记不动 `story-src/` 里的任何东西：章草稿、候选池、映射表都留在原地。
    # 它们走不漏到读者手上——归档只上传 story.md 与 review.md，`story-src/` 整层
    # 留在本地。留着的用处是实的：出了问题，它们是唯一能看出「这份 story 是怎么
    # 写出来的」的现场；登记之后要改某一章，手上也才有可改的东西。
    wanted = {**json.loads(basis.stdout),
              "files": {rel: file_sha256(feature_root / Path(*rel.split("/"))) for rel in STORY_REGISTERED}}
    if status == "story_written" and contract.get("story_basis") == wanted:
        log("这一份已经按同样的依据登记过，不改")
        record_owned_after(feature_root)
        return {"status": "story_written", "story": str(story), "registered": False}
    contract["status"] = "story_written"
    contract["story_written_at"] = now()
    contract["story_basis"] = wanted
    save(feature_root, contract)
    # 登记是 update 一轮的完成点：本扩展拥有的文件此刻的指纹记进这一轮，撤回时据它认「本轮留下的就是这一版」
    record_owned_after(feature_root)
    baseline = record_baseline(feature_root)
    return {"status": "story_written", "story": str(story), "registered": True, "review": review.get("result"),
            **({"update_baseline": baseline} if baseline else {})}


def publication_record(feature_root: Path) -> dict:
    """上传成功之后的发布记录：这一次发出去的 Story 与 Review 的摘要，外部现在就是这一版；原样留一份给下一次比差异。"""
    story, review = feature_root / Path(*STORY), feature_root / Path(*REVIEW)
    out = feature_root / Path(*PUBLISHED)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(story, out / "story.md")
    shutil.copyfile(review, out / "review.md")
    digest = short_digest(story.read_bytes())
    return {"at": now(), "story_digest": digest, "review_digest": short_digest(review.read_bytes()), "external_digest": digest}


def cmd_archived(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已送审」。归档动作由数据对接层执行，本命令只记状态。

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
    story, review = feature_root / Path(*STORY), feature_root / Path(*REVIEW)
    for path, name in ((story, "AR/story.md"), (review, "AR/review.md")):
        if not path.is_file():
            raise FlowError(f"{name} 不存在：归档件不全，无可登记的归档态")

    checker = CORE_DIR / "story-build.mjs"
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：归档态登记要先重跑交付门，无法跳过")
    # 交付门而不是普通 check：走到这里 story 该已登记、依据未变，审查结论也该已经如实记下。
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

    # 发布记录：外部现在就是这一版，下一次发布据它判外部有没有被别人改过
    contract["archived"] = publication_record(feature_root)
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，重新渲染时人工区逐字保留")
    return {"archived": True, "at": contract["archived"]["at"]}
