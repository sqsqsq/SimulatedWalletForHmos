"""只读与登记类命令：`status` 报位置，`story` 登记成文态。

`story` 沿正式命令路径调用 `story-build.mjs` 做成文检查，不反向导入入口；归档登记在 `flow/publish.py`。
"""
from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
import subprocess
from pathlib import Path

from flow.state import (
    CORE_DIR, FlowError, STORY, STORY_REGISTERED, blueprint_exists, file_sha256, load, log,
    material_confirmed, now, require, round_gates, save, stage_of)
from flow.routing import (QUESTIONS_USAGE, live_materials, material_state, next_step, reading_work,
                          register_command, sidecar_shape)
from flow import asks
from flow.update import record_baseline, record_story_registration
from flow.meetings import topic_digest
from materials import meeting


#: 等设计的几步、分析阶段的几步与成文的几步（路由给出），派生状态按它们归类
DESIGN_STEPS = ("design_blueprint", "fix_blueprint", "design_projection", "await_questions")
ANALYSIS_STEPS = ("inventory_materials", "fix_material_gaps", "read_meeting", "refresh_meeting",
                  "fix_meeting", "run_analysis", "await_gate:material_scope")
WRITING_STEPS = ("story_skeleton", "story_chapters", "register_story")


def derived_state(contract: dict | None, step: str) -> str:
    """需求现在处在哪一态：由契约与路由的同一次判断派生，不另存副本。

    gathering 材料未确认；analysis 材料已确认、设计尚未开始；waiting_for_design 设计这一侧还没成立
    （蓝图没有、读不过、没采用本需求来源或投影无效）；ready_to_write 可以成文；
    needs_sync 成文与现状不符；registered 成文已登记且与现状一致。
    update 的两段另由 `update` 字段给出。
    """
    if not contract or not contract.get("rounds"):
        return "gathering"
    if contract.get("status") == "story_written":
        return "needs_sync" if step == "register_story" else "registered"
    if not material_confirmed(contract):
        return "gathering"
    if step in ANALYSIS_STEPS:
        return "analysis"
    return ("waiting_for_design" if step in DESIGN_STEPS
            else "ready_to_write" if step in WRITING_STEPS else "needs_sync")


def cmd_material_status(feature_root: Path) -> dict:
    """只答材料事实：`pending` 与 `changed`、必读人答同步没有。不算下一步——路由要核成文依据，
    而成文依据的读者（story-build basis 等）装配输入时正是来问这一份，算下一步会绕回它们自己。下一步问 `status`。"""
    contract = load(feature_root)
    if not (contract or {}).get("rounds"):
        return {"exists": contract is not None, "material_state": None}
    manifest = live_materials(feature_root)
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    # 必读人答：期待的导出身份与实际导出是否一致——作者、质询与独审装配输入时读这一份，不各算一套
    from materials import answers  # noqa: PLC0415
    required = answers.required(feature_root, [{**v, "source_id": s["source_id"]} for s in manifest["sources"]
                                               for v in s["versions"]])
    return {"exists": True, "material_state": {"pending": state["pending"], "changed": state["changed"]},
            "required_answers": required, "source_problems": required["problems"]}


def cmd_status(feature_root: Path, questions_file: str | None = None) -> dict:
    contract = load(feature_root)
    # 材料事实**一份**：路由、收件箱提示与下面的 JSON 输出读的是同一个时点的清单。
    # 各自再 build 一次的话，同一条命令里会出现两份「现在的材料」，而消费者不知道
    # 自己拿的是哪一份。算不出来沿 FlowError 退出，不伪造 false。
    manifest = live_materials(feature_root) if (contract or {}).get("rounds") else None
    # 本地阅读同理：成文之后派生一次，路由与输出共用
    reading = reading_work(feature_root) if (contract or {}).get("status") == "story_written" else None

    # 设计后必要问答：作者把这一轮的问题写成文件交进来，脚本校形状后生成一次集中 ask。
    # 它只在首次原生质询的真实回复到达之后才有意义，所以先要求设计已开始。
    built = None
    if questions_file:
        if not contract or not contract.get("rounds"):
            raise FlowError("还没有轮次：先 `init` 起单、`round` 登记材料，再谈设计问答")
        if not blueprint_exists(feature_root):
            raise FlowError("设计还没开始（没有同根蓝图）：设计后必要问答在首次原生质询的真实回复到达之后才问，"
                            "先按 `phases/design.md` 进 component-design")
        built = asks.build_questions(feature_root, contract, questions_file)

    ask = None
    if built is not None:
        # 生成与重试走同一份状态：有待答就只摆未答的；零待答直接按原生下一步续行。
        state = _questions_state(feature_root, contract, built)
        if state:
            ask, step, action = state
            if built.get("replaced_unanswered"):
                old = "、".join(str(it.get("item_id")) for it in built["replaced_unanswered"])
                action += (f"；上一组还没答的题（{old}）已被这次问法替换：原问题与依据已留在 "
                           f"`{built.get('replaced_kept')}`，把为何失效写进当前分析或本轮 notes 再往下走")
        else:
            step, action = next_step(feature_root, contract, manifest, reading)
    else:
        step, action = next_step(feature_root, contract, manifest, reading)
        # 到了停等点就生成问法并写侧车：人看到的选项块与 `decide` 核对的是同一份
        ask = (asks.build_material(feature_root, contract)
               if contract and contract.get("rounds") and step == "await_gate:material_scope" else None)
        if ask is None and contract and contract.get("rounds"):
            # 已有设计问答时原样续问：普通 status 不重新生成更宽的问法，也不悄悄覆盖。
            state = _questions_state(feature_root, contract)
            if state:
                ask, step, action = state
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
    topics = topic_digest(feature_root, meeting.read_notes(feature_root, []))
    return {
        "exists": True,
        "schema": contract.get("schema"),
        "status": contract.get("status"),
        # 最近一次成文登记的时刻；重跑 `story` 就是重新登记
        "story_written_at": contract.get("story_written_at"),
        # 本地阅读与业务闭环分开报：成文之后才有增强 SVG 要做
        **({"reading": reading} if reading is not None else {}),
        "round": current.get("round"),
        "positioning": current.get("positioning"),
        "gates": [{"gate": g.get("gate"), "chosen": g.get("chosen"),
                   "outcome": g.get("outcome"), "by": g.get("by")} for g in gates],
        "archived": bool(contract.get("archived")),
        "state": derived_state(contract, step),
        **({"update": stage_of(contract)} if stage_of(contract).startswith("update_") else {}),
        # 蓝图与需求同根：标识就是需求标识，在不在按原生 canonical 文件
        "blueprint": {"blueprint_id": feature_root.name, "exists": blueprint_exists(feature_root)},
        "material_state": ({"pending": state["pending"], "changed": state["changed"]}
                           if state else None),
        # 会议话题在这里机械枚举一次：全部版本、全部话题，含不属于本需求与归属判不准的。
        # 模型据它向人呈现，不必自己把 notes 再列一遍；只在读会那几步给，别的步骤用不上它。
        **({"meetings": topics} if topics and "meeting" in step else {}),
        "next": step,
        "action": action,
        **({"ask": ask} if ask else {}),
        **({"sidecar": shape} if shape else {}),
    }


def _questions_state(feature_root: Path, contract: dict, ask: dict | None = None):
    """设计问答此刻的状态：有待答给只含未答的展示块；零待答撤下临时问法并返回 None，按原生下一步续行。

    普通 `status` 与带同一问法文件的重试都走这里——两条路各写一份的话，一处会重问已答的题。
    待答与展示块由 `asks.pending_view` 的同一次读取给出，不再为拼状态重读记录。
    """
    ask = ask or asks.current_design(feature_root)
    if ask is None:
        return None
    shown = asks.pending_view(feature_root, ask, contract)
    if not shown["pending"]:
        asks.clear(feature_root)
        return None
    return shown, "await_questions", step_action_questions(shown)


def step_action_questions(shown: dict) -> str:
    """设计问答没答完时给人的下一步：把同一个展示块（只含余下问题）原样摆出，不重答已答的题。"""
    return (f"设计后必要问答还有 {len(shown['pending'])} 题没答（{shown['ask_id']}）。"
            "把返回的 ask.block 作为本次消息；只摆还没答的问题，全部答完即回原生设计续行：\n"
            + shown["block"]
            + "\n`decide --ask <id> --item <题号> --reply \"<人的原话>\"`；多题同一答复用 --replies-file")


def cmd_story(feature_root: Path, project_root: Path) -> dict:
    """登记「Story 已成文」：按当前蓝图写成、经独立审查的 Story 就是要交付的这一份。

    **登记只读核对，不改被审对象**：附录重投与编号在准备审查时已经做完
    （`story-build review --action prepare`），登记这一步再动它们，审的就不是登记的那一份。依次核：

    1. 全篇结构检查（`story-build check`）通过；
    2. 这一份的独立审查结果（`story-build review --action check`）是 pass 或 warn——审的是现在这份；
       准备时没有可用的独立读者则如实记为未审（unreviewed），同样可登记，披露随结果；
    3. 这一刻的成文依据（`story-build basis`）：蓝图引用、设计采用的来源、激活知识摘要与材料索引摘要，
       加上 Story 与写作设计的原始字节指纹。

    都成立才一次写入新依据；任一步不成立照实报出，已有的登记与依据原样保留（派生为待同步）。
    依据与已登记的相同时什么都不改，登记时刻也不换：成文时刻是这份稿的业务事实。
    """
    contract = require(load(feature_root))
    status = contract.get("status")
    if status != "story_written" and not material_confirmed(contract):
        # 材料还没人确认就直接来登记：说出现在该做什么，不只说「不行」。
        # 下一步要按磁盘现状读材料；读不出来时「材料还没确认」照样先说，原因附在后面。
        try:
            _, action = next_step(feature_root, contract, live_materials(feature_root))
        except FlowError as exc:
            action = f"暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取下一步"
        raise FlowError(f"本轮材料还没确认，成文态无从登记。下一步：{action}")
    story = feature_root / Path(*STORY)
    if not story.is_file():
        raise FlowError("AR/story.md 不存在：没有成文，无可登记的成文态")

    checker = CORE_DIR / "story-build.mjs"
    rerun = f"再跑 `{register_command(feature_root)}` 重新登记"

    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node，story-build 一步都没启动，成文没有登记。"
                        f"这是运行环境问题，业务稿与派生件都不用改：装好 node 后{rerun}")
    # 三项核对（全篇检查 → 审查结果 → 成文依据）在一个 story-build 进程里按序跑，各步结论与原输出逐项带回
    steps = (("check", "check", "全篇检查通过"), ("review", "review --action check", "独立审查结果可消费"),
             ("basis", "basis", "成文依据已取到"))
    try:
        proc = subprocess.run(
            [node, str(checker), "registration-check", "--feature", feature_root.name, "--project-root", str(project_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FlowError(f"story-build registration-check 没能启动（{exc}），成文没有登记。已完成：无。"
                        f"这是运行环境问题，业务稿与派生件都不用改：环境恢复后{rerun}") from exc
    rows = [line for line in (proc.stdout or "").splitlines() if line.startswith("{")]
    try:
        result = json.loads(rows[-1]) if rows else None
    except ValueError:
        result = None
    if proc.returncode not in (0, 1, 2) or not isinstance(result, dict) or not isinstance(result.get("steps"), list):
        raise FlowError(f"story-build registration-check 没有正常结束（退出码 {proc.returncode}），成文没有登记。"
                        f"这不是业务稿的问题，不要为它改真源或草稿：{_not_the_product(proc.returncode)}，"
                        f"修好后{rerun}。原始输出：\n" + _said(proc))
    by = {s.get("name"): s for s in result["steps"]}
    done: list[str] = []
    for i, (key, name, effect) in enumerate(steps):
        step = by.get(key) or {"status": "not_run", "detail": ""}
        if step.get("status") == "passed":
            done.append(effect)
            continue
        detail = str(step.get("detail") or "").strip() or "没有任何输出"
        if key == "review" and step.get("status") == "failed":
            review = result.get("review") or {}
            raise FlowError(f"这一份的独立审查还不能消费（{review.get('result', '读不到结果')}）："
                            f"{review.get('detail', detail[:600])}"
                            f"——按 `phases/design.md`「五、独立审查、登记与交付」处置，审查结果可消费后{rerun}")
        if step.get("status") == "failed":
            raise FlowError(f"story-build {name} 没通过，成文没有登记，已有的登记原样保留。已完成：{'；'.join(done) or '无'}。"
                            f"没跑：{'、'.join(s[1] for s in steps[i + 1:]) or '无'}。按下面的报告处理它点名的真源、草稿或环境"
                            f"（正文经 chapter 提交），{rerun}：\n" + detail)
        raise FlowError(f"story-build {name} 没有正常结束，成文没有登记。已完成：{'；'.join(done) or '无'}。"
                        f"这不是业务稿的问题，不要为它改真源或草稿：{_not_the_product(2)}，修好后{rerun}。原始输出：\n" + detail)

    # 登记记下 Story 与它据以成文的写作设计此刻的指纹：之后 `story-build check`
    # 与流程路由拿它核「登记之后改过没有」，改过就重新审查、重新登记。
    #
    # 登记不动 `story-src/` 里的任何东西：章草稿、候选池、映射表都留在原地。
    # 它们走不漏到读者手上——归档只上传 story.md 与按需的设计参考投影，`story-src/` 整层
    # 留在本地。留着的用处是实的：出了问题，它们是唯一能看出「这份 story 是怎么
    # 写出来的」的现场；登记之后要改某一章，手上也才有可改的东西。
    # 材料索引摘要随登记记下：update 以 documents 收口时据它认「登记之后来的新材料有没有经过这次成文」
    wanted = {**result["basis"],
              "materials_digest": live_materials(feature_root).get("digest"),
              "files": {rel: file_sha256(feature_root / Path(*rel.split("/"))) for rel in STORY_REGISTERED}}
    if status == "story_written" and contract.get("story_basis") == wanted:
        log("这一份已经按同样的依据登记过，不改")
        record_story_registration(feature_root, result.get("review"))
        return {"status": "story_written", "story": str(story), "registered": False, **_next(feature_root, contract)}
    contract["status"] = "story_written"
    contract["story_written_at"] = now()
    contract["story_basis"] = wanted
    save(feature_root, contract)
    # 登记是 update 一轮的完成点：可撤回文件的指纹与**本轮承接身份**（登记键、设计参考只读投影）此刻一起记下；
    # 撤回时据前者认「本轮留下的就是这一版」，收口与发布据后者认「这份评审输入随这一版 Story 登记过」。
    record_story_registration(feature_root, result.get("review"))
    baseline = record_baseline(feature_root)
    return {"status": "story_written", "story": str(story), "registered": True,
            "review": (result.get("review") or {}).get("result"),
            **({"update_baseline": baseline} if baseline else {}), **_next(feature_root, contract)}


def _next(feature_root: Path, contract: dict) -> dict:
    """登记之后真正的下一步与 `status` 同一条路由给出，不另写一份；算不出来不遮住已成功的登记。"""
    try:
        step, action = next_step(feature_root, contract, live_materials(feature_root))
    except FlowError as exc:
        step, action = "status", f"成文已登记；下一步暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取"
    return {"next": step, "action": action}


#: 外层持有视图的标记：值是需求目录（小写绝对路径），story_flow 与 story-build 共用；带着同一需求的值进来就是子调用，不各自恢复
VIEW_OWNER = "STORY_VIEW_OWNER"


@contextmanager
def reading_view(feature_root: Path, project_root: Path, outcome: dict):
    """最外层动作持有视图：动手前回到正式形态（图块按源的 Mermaid），结束或失败后恢复当前可用的增强 SVG。

    被它调起的 story-build 子命令继承 `STORY_VIEW_OWNER`，不再切入，也不各自恢复。恢复失败只补视图，
    写进 `outcome["view"]`，不遮住原来的结果或错误。
    """
    key = os.path.realpath(feature_root).lower()
    before = os.environ.get(VIEW_OWNER)
    owner = before != key
    if owner:
        os.environ[VIEW_OWNER] = key
    try:
        if owner:       # 同一需求的外层已切入并持有：不再切一遍
            ensure_mermaid(feature_root, project_root)
        yield
    finally:
        if owner:
            if before is None:
                os.environ.pop(VIEW_OWNER, None)
            else:
                os.environ[VIEW_OWNER] = before
            story = feature_root / Path(*STORY)
            if story.is_file() and _managed(story):
                try:
                    outcome["view"] = _view(feature_root, project_root, "svg", "增强 SVG 没有恢复，story 保持 Mermaid")
                except FlowError as exc:
                    outcome["view"] = str(exc)


def _managed(story: Path) -> bool:
    """story 里有没有脚本管理区：正式图块要经视图处理；旧版阅读槽也送去视图，由它报出来。"""
    text = story.read_text(encoding="utf-8", errors="replace")
    return "<!-- story-figure:" in text or "<!-- story-reading:" in text


def ensure_mermaid(feature_root: Path, project_root: Path) -> None:
    """story 里有管理区时先回到正式形态：比较、登记与归档只认图块按源 Mermaid 的文本。没有管理区不起进程。"""
    story = feature_root / Path(*STORY)
    if not story.is_file() or not _managed(story):
        return
    _view(feature_root, project_root, "mermaid", "读 story 之前要先回到正式形态，回不去")


def _view(feature_root: Path, project_root: Path, mode: str, why: str) -> str:
    node = shutil.which("node")
    if node is None:
        raise FlowError(f"找不到 node：{why}（视图切换由 story-build.mjs view 做）")
    proc = subprocess.run(
        [node, str(CORE_DIR / "story-build.mjs"), "view", "--mode", mode, "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        raise FlowError(f"{why}：\n" + _said(proc))
    return _said(proc)


def _not_the_product(code: int) -> str:
    """story-build 退出码既不是 0 也不是 1：归谁处理。"""
    return "这是 story-build 自身异常，归扩展维护者处理" if code == 2 else "进程被中断或运行环境出错"


def _said(proc: subprocess.CompletedProcess) -> str:
    """子进程的两路输出原样带回：问题清单常在一路、恢复入口在另一路，只取一路就丢了一半。"""
    return "\n".join(x.strip() for x in (proc.stdout, proc.stderr) if x and x.strip()) \
        or f"退出码 {proc.returncode}，没有任何输出"
