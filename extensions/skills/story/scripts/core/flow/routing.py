"""「现在走到哪、下一步干什么」：材料事实、人的原话记录与阶段定位。

只读不写。材料按磁盘现状取，路由据此回答位置——同一次命令里读到的是同一份事实。

只依赖 state、inputs、meetings、asks 与 materials.registry，不导入 decisions/rounds/lifecycle：
命令问路由，路由不问命令。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from materials import importer, meeting, registry

from flow.state import (
    CORE_DIR, FlowError, STORY_CONTRACT, blueprint_exists, closed, last_gate,
    registration_drift, round_gates, stage_of, system_requirement)
from flow.inputs import (
    GAPS, POSITIONING, POSITIONING_FIELDS, read_gaps)
from flow.meetings import meeting_basis, refresh_problems
from flow import asks, native

def closed_inbox_note(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """收口及之后，收件箱里还躺着没导入的原件——**把它说出来**，没有就返回空串。

    出口按位置给：已归档的走 `/story update`，其余导入、`round` 登记到本轮、改完重跑 `story` 重新登记。

    不提它，那份文件从此没有任何人知道——`round` 只看已导入的指纹说「材料未变」，
    `status` 只说下一步走 spec 那条路。**下游没有动作时要说明为什么不适用，
    缺席不代表不适用。**
    """
    if not contract.get("rounds") or not closed(feature_root, contract):
        return ""
    pending = material_state(feature_root, contract["rounds"][-1], manifest)["pending"]
    if not pending:
        return ""
    more = f" 等 {len(pending)} 份" if len(pending) > 3 else ""
    head = f"收件箱里有 {len(pending)} 份还没导入的原件（{'、'.join(pending[:3])}{more}）："
    if contract.get("archived") and not (contract.get("update") or {}).get("open"):
        return head + ("本单已归档送审，新材料走 `/story update` 承接；"
                       "不纳入就留在收件箱，本轮不受影响")
    return head + ("先导入、再重跑 `round` 登记到本轮（收口之后它不开新轮）；"
                   "story 已登记的，据新料改完重跑 `story` 重新登记")


def live_materials(feature_root: Path) -> dict:
    """按磁盘现状取一份材料清单 —— **同一个时点只取一次**，由调用链向内传。

    同一条命令里重复 build，是把同一批文件再哈希一遍，
    而两次之间什么也没发生。写入前后是两个不同的时点，那时各取各的。
    """
    try:
        return registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc


def material_state(feature_root: Path, current: dict, manifest: dict | None = None) -> dict:
    """料现在什么样——**两个事实，一次问完**：谁还没导入、材料变没变。

    ``pending`` 是来源收件箱里还没导入的件；``changed`` 是材料指纹与本轮登记的
    对不上（新版本已经导进来了，本轮还没重新登记）。两者都走磁盘不走账本：材料索引
    按盘上的材料版本与收件箱现状算。

    **两件事互不替代**：`round` 登记新基准之后 `changed` 归假，而那份原件仍躺在
    收件箱里没导入——只看 `changed` 的消费者从此再也不会提到它。

    `manifest` 是调用方在这个时点已经取到的清单：传了就按它派生，不再读盘；
    显式判 ``None``，合法的空清单不会被当成「没传」偷偷改回重读。
    不写盘：`status` 只回答现在是什么样，落盘归 `round`。
    """
    if manifest is None:
        manifest = live_materials(feature_root)
    return {"pending": registry.pending(manifest),
            "changed": manifest["digest"] != (current.get("materials") or {}).get("digest")}


def pending_import_step(state: dict) -> tuple[str, str] | None:
    """收件箱里还躺着原件时的下一步 —— **收口前后同一句**：先导入。

    登记新基准不等于原件已经导入：`round` 刷新之后「材料变了」这条判据不再响，
    而那份文件仍在收件箱里。两处各写一句的话，其中一句迟早只说「材料没变」。
    """
    if not state["pending"]:
        return None
    more = f" 等 {len(state['pending'])} 件" if len(state["pending"]) > 3 else ""
    return ("import_materials",
            "收件箱里有还没导入的件（或直接改过的当前阅读稿），先导入："
            "`python doc/extensions/skills/story/scripts/core/import_sources.py --feature <名>`"
            f"（{'、'.join(state['pending'][:3])}{more}），导完重跑 `round` 盘点")


#: 成文这一段的顺序，几个分支共用一句。
STORY_STAGE_ORDER = (
    "顺序：story-build skeleton → 写整篇写作设计（阅读主线与每章骨架）→ 再跑 skeleton → 逐章 chapter → "
    "回看清单逐条处置 → 图源写定后按 `reference/svg.md` 判断哪些图值得做同图增强 → "
    "`story-build review --action prepare --reader task|unavailable` 定稿（重投附录、编号、全篇检查）"
    "并准备独立审查 → 派审 → 回复落盘后重跑 prepare 接收 → `story-build review --action check` → `story_flow.py story` 登记 → 交付门 → 交付选择")


def register_command(feature_root: Path, mode: str = "story") -> str:
    """这张单的登记命令（成文 story / 归档 archived），复制即可运行：参数包法与 story-build 的 `shellArg` 同一规则。"""
    posix = bool(os.environ.get("SHELL")) or sys.platform != "win32"
    def arg(value) -> str:
        text = str(value)
        return "'" + (text.replace("'", "'\\''") if posix else text.replace("'", "''")) + "'"
    return (f"python doc/extensions/skills/story/scripts/core/story_flow.py {mode}"
            f" --feature {arg(feature_root.name)} --project-root {arg(importer.project_root_of(feature_root))}")


def pending_chapters(feature_root: Path) -> int:
    """story 里还带着待写记号的章数 —— **只读**，不在这里重做章级检查。

    记号的真源是章节合同的 ``pending_mark``；合同读不到是包坏了，照实报错。
    """
    try:
        text = (feature_root / "AR" / "story.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise FlowError(f"AR/story.md 读不出来（{exc}）") from exc
    mark = str(json.loads(STORY_CONTRACT.read_text(encoding="utf-8"))["pending_mark"])
    return len(re.findall(r"<!--\s*" + re.escape(mark) + r"[:：]", text))

def design_stage_step(feature_root: Path, contract: dict) -> tuple[str, str]:
    """本轮范围定了之后：按原生蓝图的真实状态回答等设计还是可以成文。flow 不存准入与 revision 的副本。"""
    return design_gate(feature_root, contract) or story_stage_step(feature_root)


def design_gate(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """设计这一侧还差什么：蓝图没建、读不过、没有采用本需求的来源或投影不对时给下一步；都成立返回 None。

    蓝图与需求同根，蓝图标识就是需求标识。成文读的是原生草稿：没准入不挡成文与业务送审，原生 issues 与未决由成文、
    独审与交付说明如实带出；准入只决定施工单位能不能开工，由交付门之后的施工路径消费。
    """
    blueprint = feature_root.name
    if not blueprint_exists(feature_root):
        return ("design_blueprint",
                f"本轮范围已定。按 `phases/design.md`「二、交给设计」「三、设计」进原生 component-design：为本需求建立蓝图 `{blueprint}`"
                f"（与需求同根，在 `{blueprint}/blueprint/`）。来源是材料索引 `AR/story-src/materials.json` 登记的版本（当前阅读稿 `RR/prd.md`、`SR/design.md` 等及它们的组成原件，每版留存在 `.backups/local/`）；当前有效人工答复是必读；"
                "本轮定位（本单承载、同一系统设计下的兄弟单、协作方与不做项）与范围答复写进原生范围与边界。"
                "需求条目只写真实的需求、目标、约束与风险，用 `import_sources.py --scope` 按材料索引补齐来源路径与摘要；"
                "只作支撑的材料在事实与设计对象的 provenance 里引用，不为它造条目。"
                "请求按本次授权写终点（`phases/design.md`「三、设计」）：只到 Story 的写明「完成可评审设计与独立质询，本次不做施工单位准备」，做到生成评审投影为止；"
                "已有授权到施工单位设计、Spec 或 Plan 的，准入后在首次定稿 Story 前完成施工单位设计准备"
                "（准入与否、还开着的问题由原生如实给出，不为过准入删改未决）；"
                "知识在设计决定前取（story-knowledge），独立质询交宿主的隔离子代理。"
                "本轮授权：`/story <AR>` 的启动语义是「做到交付门；已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择」（framework 原请求授权，见 SKILL 推进契约），直接进，不问")
    read = native.call(native.project_root_of(feature_root), "blueprint", "--blueprint", blueprint, "--purpose", "draft",
                       "--consume", blueprint)
    if read["status"] != "ok":
        return ("fix_blueprint", f"蓝图 `{blueprint}` 原生读不过（{read['status']}）：{native.issues_text(read)}——设计职责按原生报错修正")
    consumption = read.get("consumption") or {}
    if consumption.get("status") != "ok":
        return ("design_blueprint",
                f"蓝图 `{blueprint}` 没有采用本需求的来源：{native.issues_text(consumption)}——"
                "设计职责在 component-design 里按登记的材料同步需求条目与设计依据（条目用 `import_sources.py --scope` 补齐路径与摘要），"
                "再重新生成评审投影")
    projection = read.get("projection") or {}
    if projection.get("status") != "valid":
        return ("design_projection",
                f"评审投影 `{projection.get('path')}` {'还没生成' if projection.get('status') == 'missing' else '与当前 revision 对不上'}："
                "由设计职责按原生 renderer 生成，Extension 不手改")
    return None


def story_stage_step(feature_root: Path) -> tuple[str, str]:
    """蓝图可读、投影有效之后，成文做到哪儿了——按磁盘上有什么说清。"""
    if not (feature_root / "AR" / "story.md").is_file():
        return ("story_skeleton",
                "蓝图可读、评审投影有效。跑 `story-build skeleton`：它给出成文要用的当前输入，建写作设计空壳与章草稿，"
                "并告诉你先写整篇设计还是先写哪一章。" + STORY_STAGE_ORDER)
    left = pending_chapters(feature_root)
    if left:
        return ("story_chapters",
                f"story.md 已在，还有 {left} 章带着待写标记。"
                "先跑 `story-build skeleton` 取回当前输入与下一步（写作设计还没写好时它先让你写设计）；"
                "逐章在草稿上写、`story-build chapter --from <草稿>` 落盘——"
                "每次落盘先核这一章能确定的那几条，判不过时盘上什么都不变；"
                "落盘之后它会给出下一章。" + STORY_STAGE_ORDER)
    reading = reading_todo(reading_work(feature_root))
    return ("register_story",
            "本需求的有效章节都写完了。先跑 `story-build skeleton` 取回看清单，逐条撞两问、处置回真源"
            "（业务结论回设计，骨架改写作设计，正文改草稿再 chapter 提交）；"
            "图源写定后按 `reference/svg.md`「值不值得做」判断每张图，值得的先做完同图增强并过源码审查"
            + (f"（已开始的还没做完：{reading}）" if reading else "") +
            "；之后按实际可用的独立读者准备审查（`story-build review --action prepare --reader task|unavailable` 定稿时跑全篇检查，见 phases/design.md「五」）并派审，"
            f"审查结果可消费之后跑 `{register_command(feature_root)}` 登记成文。" + STORY_STAGE_ORDER)


#: 材料关卡的回话方式：问法由 `status` 的 `ask` 给出，人回话后按它记。
DECIDE_USAGE = ("把 `status` 输出里 `ask.block` 原样摆给人（前面一句结论与缺口），停等。"
                "人回话后跑 `story_flow.py decide --feature <名> --gate material_scope --ask <ask_id> "
                "--reply \"<人的原话>\"`。原话只认编号的说法（第 n、n.、n）、选 n、整句为 n）"
                "或整句照抄一项的标签；片段命中或模型替人挑一项都不算人的选择")
#: 设计后必要问答的回话方式：问题与选项从已落盘的问法取，记录不重填问法。
QUESTIONS_USAGE = (
    "把 `ask.block` 原样摆给人，一次把这组题问完；人回话后跑 "
    "`story_flow.py decide --feature <名> --ask <ask_id> --item <题号> --reply \"<人的原话>\"`，"
    "多题同一答复用 `--replies-file <{\"items\":[{\"item_id\",\"reply\"}]}>`。"
    "记录时只按盘上问法取问题与选项，不重填；部分答复只留未答的题，全部答完即回原生设计续行")
#: 设计问答文件的形状：这一次动作的输入，不是第二份机器真源。
QUESTIONS_SHAPE = {
    "path": "<工程内 JSON，只作本次动作输入>",
    "shape": {"items": [{"item_id": "本组题号，不是新议题编号",
                         "question": "要人定什么；写完整问法",
                         "options": ["候选做法与其后果，可为空数组"],
                         "recommend": "建议的一项候选（可为空）",
                         "reason": "为何符合必要问人的三条件、当前用户有权回答",
                         "source_ref": "已取得原件或本轮原生质询报告的相对路径"}]},
    "note": "只有 Spec 三条件内、当前用户有权回答的才放进来；选项与建议来自原件与质询后分析，"
            "已有答案直接复用、第三方才能定的保 gap，不强问当前用户",
}


def sidecar_shape(step: str) -> dict | None:
    """这一步要写的侧车长什么样：字段、合法值、为什么要它。

    形状是确定的，该在需要它的那一步就摆出来，而不是等作者去读源码或撞报错。
    """
    if step == "run_analysis":
        return {"写这份": [{"path": "/".join(POSITIONING), "shape": dict(POSITIONING_FIELDS)}]}
    if step in ("inventory_materials", "fix_material_gaps"):
        return {"path": "/".join(GAPS),
                "shape": {"missing": ["还缺的材料：名称与在哪句话里提到"], "why": "一句缺口判断"},
                "note": "missing 没有就给空数组；材料关卡的推荐由脚本按它算"}
    if step == "await_gate:material_scope":
        return {"回话": DECIDE_USAGE}
    if step == "await_questions":
        return {"回话": QUESTIONS_USAGE}
    if step == "design_blueprint":
        return {"首次原生质询回复到达后确有必须人定的问题": {
            "命令": "`status --questions-file <文件>`",
            **QUESTIONS_SHAPE,
            "note": QUESTIONS_SHAPE["note"],
        }}
    return None


def material_step(feature_root: Path, always: bool) -> tuple[str, str] | None:
    """第一级停不停、停之前缺什么——**一次问完**。

    第一轮与 update 输入阶段必停：还没有人对这批材料表过态。此后每一轮是材料变了才开出来的，
    只在你拿新材料重新盘出缺口、写了缺口文件时再停；不缺就不停，直接进需求分析。
    推荐由脚本按缺口算：还缺料就推荐请人放料，不缺就推荐开始分析。
    """
    try:
        gaps = read_gaps(feature_root)
    except FlowError as exc:
        return "fix_material_gaps", f"缺口文件还立不住，先改好再问人：{exc}"
    if gaps is None:
        if not always:
            return None
        return ("inventory_materials",
                "盘点材料：清单与一句缺口判断写进 `AR/story-src/init-analysis.md` 第 ⑤ 节 1–2，"
                f"缺口写进 `{'/'.join(GAPS)}`，再跑 `status` 取问法")
    if not always and not gaps["missing"]:
        return ("fix_material_gaps", "第 2 轮起只在还缺料时停：缺口文件的 missing 是空的，"
                "删掉它直接进需求分析")
    return "await_gate:material_scope", "第一级材料关卡。" + DECIDE_USAGE


def closed_tail(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """收口之后下一步末尾那一句：收件箱里有没有没人管的原件。`next` 本身不变。"""
    note = closed_inbox_note(feature_root, contract, manifest)
    return f"。**另外**：{note}" if note else ""


def inputs_answer(contract: dict) -> dict | None:
    """update 的输入阶段开始之后，人在第一级留下的最后一笔；还没答过返回 None。

    与 init 同一个关卡、记在当前轮：update 不开新轮（开了，已成文的 story 据以成文的那批料
    就对不上了）。「这一次答没答」按位置分：输入阶段开始时本轮已有几笔记在 `inputs_from`，
    只认它之后追加的。**不按时刻比**——时刻只精确到秒，同一秒里的上一次回答会被当成这一次。
    """
    since = int((contract.get("update") or {}).get("inputs_from") or 0)
    for gate in reversed(round_gates(contract)[since:]):
        if gate.get("gate") == "material_scope":
            return gate
    return None


def update_inputs_step(feature_root: Path, contract: dict,
                       manifest: dict | None = None) -> tuple[str, str]:
    """update 的输入阶段：**先问要不要补料，人答了再比**。

    问法、缺口文件、人签、登记全是 init 第一级那一套；差别只在它每次 update 都停一次——
    上游变没变、手上还缺什么，只有人说了才算定。
    """
    answer = inputs_answer(contract)
    if answer is None or answer.get("outcome") != "accepted":
        return material_step(feature_root, always=True)
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("refresh_round", "新料已导入：跑 `story_flow.py round` 登记到本轮（它不开新轮），"
                "再 `story_flow.py update --action prepare --result <materials|documents>`")
    return ("update_prepare", "输入已定：跑 `story_flow.py update --feature <名> --action prepare --result <materials|documents>`"
            "（按人这次的请求记终点），它比较六项并开这一轮")


def update_open_step(feature_root: Path, contract: dict,
                     manifest: dict | None = None) -> tuple[str, str]:
    """更新正在进行：去向是「按修订清单改」，**不重走材料关卡**。

    新材料 `round` 登记进当前轮，范围沿用本单已定的；设计按新来源同步，story 改了就重跑 `story` 重新登记。
    """
    rid = contract["update"]["open"]
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("refresh_round", "这一轮新到的料已导入：跑 `story_flow.py round` 登记到本轮"
                "（update 期间它不开新轮）")
    # 新会议照常读会、写当前会议结果；会上有要人定的话题进蓝图 gap，不再生成会议裁决关卡
    meeting_now = meeting_step(feature_root, contract) or meeting_result_step(feature_root, contract)
    if meeting_now:
        return meeting_now
    reregister = registration_step(feature_root, contract)
    if reregister:
        return reregister
    return ("update_in_progress",
            f"更新 {rid} 正在进行：按 `AR/story-src/updates/{rid}/update-notes.md` 的修订清单改，"
            "改法与收口见 `phases/update.md`「二、一条线」"
            + closed_tail(feature_root, contract, manifest))


def basis_drift(feature_root: Path, contract: dict) -> list[str]:
    """登记之后蓝图或激活知识换了没有：按 `story-build basis` 给出的这一刻的依据比。读不出来照实报。"""
    if contract.get("status") != "story_written":
        return []
    root = native.project_root_of(feature_root)
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：核成文依据要跑 story-build basis")
    proc = subprocess.run([node, str(CORE_DIR / "story-build.mjs"), "basis", "--feature", feature_root.name,
                           "--project-root", str(root)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FlowError("成文依据读不出来：" + (proc.stderr or proc.stdout or "").strip()[:600])
    now = json.loads(proc.stdout)
    was = (contract.get("story_basis") or {})
    ref, cur = was.get("blueprint_ref") or {}, now.get("blueprint_ref") or {}
    out = []
    if (ref.get("artifact_sha256"), ref.get("revision")) != (cur.get("artifact_sha256"), cur.get("revision")):
        out.append(f"蓝图（登记时 r{ref.get('revision')}，现在 r{cur.get('revision')}）")
    if was.get("sources_sha256") != now.get("sources_sha256"):
        out.append("设计采用的来源")
    if was.get("knowledge_sha256") != now.get("knowledge_sha256"):
        out.append("激活知识")
    return out


def registration_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """story 已写出来之后要不要重新登记：登记之后 story、采用来源、蓝图或知识变了，或还没按当前内容登记
    （update 里重开范围后、重新登记没过）。不需要返回 None。
    """
    waiting = design_gate(feature_root, contract)
    if waiting:
        return waiting
    if contract.get("status") != "story_written":
        return story_stage_step(feature_root)
    drift = registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
    if drift:
        return ("register_story", (f"成文登记之后改过 {'、'.join(drift)}：" if drift else "story 还没按当前内容登记：")
                + "按当前蓝图与来源同步 Story 里受影响的章节，再 `story-build review --action prepare` 定稿（重投附录、编号、全篇 check）并交原读者按改动影响复核，"
                f"审查通过后跑 `{register_command(feature_root)}` 重新登记")
    return None


def next_step(feature_root: Path, contract: dict | None,
              manifest: dict | None = None, reading: dict | None = None) -> tuple[str, str]:
    """流程位置的唯一判据：读契约，回答下一步该干什么。

    位置由数据回答而不由记忆回答——skill 正文因此不必维护成篇的「如果……那么……」，
    恢复一个中断的 feature 也不用靠翻对话。每个返回值都对应 SKILL.md 里的一个具体动作。

    `manifest` 是调用方这个时点已经取到的材料清单，`reading` 是已经取到的本地阅读工作集合：
    路由与它给出的动作要跟同一份事实，消费者（`status` 的 JSON、起手预检）读的也是这一份，不在下游再各判一次。
    """
    if contract is None or not contract.get("rounds"):
        return "run_round", "初析已生成的话，跑 `story_flow.py round` 登记本轮"
    stage = stage_of(contract)
    if stage == "update_inputs":
        return update_inputs_step(feature_root, contract, manifest)
    # 收口之后才导进来的会议：还没有会议判断的版本。收口前读过的会都已写进判断（材料确认之后必经）
    late = (sorted(set(meeting.versions(feature_root)) - set(meeting.read_notes(feature_root, [])))
            if closed(feature_root, contract) and stage != "update_open" else [])
    if late:
        return ("late_meeting", f"收口之后到了会议转写（{'、'.join(late)}）：按 `phases/meeting-read.md` 读会、"
                "把当前会议结果补进 `doc-refresh.md`；会上的结论进蓝图，没定的进 gap，"
                "不再另设会议裁决关卡。只是补充事实就读会后照常改、重跑 `story` 重新登记"
                + closed_tail(feature_root, contract, manifest))
    if stage == "update_open":
        return update_open_step(feature_root, contract, manifest)
    if stage in ("archived", "story_written"):
        reregister = registration_step(feature_root, contract)
        if reregister:
            return reregister
    reading = (reading_todo(reading if reading is not None else reading_work(feature_root))
               if stage in ("archived", "story_written") else None)
    if reading:
        # 已开始的同图增强是本轮工作：先做完再回原接续；读不出时给诊断动作，不当完成。不是业务许可，不挡交付门与归档
        return ("finish_reading", f"已开始的同图增强还没做完，先在本轮做完：{reading}。"
                "做完后按 `story_flow.py status` 的下一步回到原来的收尾" + closed_tail(feature_root, contract, manifest))
    if stage == "archived":
        # 归档之后收口过一轮 update：本地已按它更新，回写需求系统等人确认（`phases/update.md`「已归档」一行）
        last_closed = str((contract.get("update") or {}).get("last_closed") or "")
        archived = contract.get("archived") or {}
        at = str(archived.get("at") or "")
        updated = last_closed[:15] > at.replace("-", "").replace(":", "").replace("T", "-")[:15]
        restored = archived.get("restored_at") and archived.get("external_digest") != archived.get("story_digest")
        return ("done", ("本地已按 update 更新；回写需求系统等人确认，确认后走 `/story archive`。" if updated
                         else "需求系统上的正文已恢复到旧版，两个附件仍是最近一次发布的版本，三件分属不同版本；"
                              "要再送审走 `/story archive`，按逐件基线重新核。" if restored
                         else "本轮已归档送审。")
                + "评审意见、上游新材料与改稿走 `/story update`；真实范围变化也由 update 承接、回蓝图修订"
                + closed_tail(feature_root, contract, manifest))
    if stage == "story_written":
        # 交付选择按这张单的真实来源给：挂在需求系统上的单能送审，本地需求没有系统可送
        choices = ("（本单挂在需求系统上：送审 / 完整设计交接 / 实现方案 / 完整实现 / 暂不推进）"
                   if system_requirement(feature_root.name)
                   else "（本单是本地需求：完整设计交接 / 实现方案 / 完整实现 / 暂不推进）")
        return ("run_delivery_gate",
                "Story 已按当前蓝图写成、经独立审查并登记。按 `phases/design.md`「五、独立审查、登记与交付」走完："
                "`story-build check --deliver` 交付门；通过后已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择"
                + choices + closed_tail(feature_root, contract, manifest))
    if closed(feature_root, contract):
        # 设计开始之后材料又变了，也要先说出来。收口那一刻登记的材料指纹是这一轮的依据，
        # 而设计与叙事件都按那批料写：两份落盘记录（清单与轮次）在文件被改之后
        # 仍然彼此相等，只有按磁盘现状重算才看得见。处置是 `round`——它把这次变化
        # 记到本轮（不开新轮）。**没有登记过基准不算「变了」**：
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
                    "（它不开新轮），再继续——设计与叙事件都按本轮登记的那批料写；"
                    "材料带来的真实范围变化由 update 承接、回蓝图负责方修订"
                    + closed_tail(feature_root, contract, manifest))
        questions = questions_step(feature_root, contract)
        if questions:
            return questions
        step, action = design_stage_step(feature_root, contract)
        return step, action + closed_tail(feature_root, contract, manifest)

    current = contract["rounds"][-1]

    # **已到的材料先处理完，再谈别的**——人回答没回答都一样。
    #
    # 收件箱里躺着原件而流程往下走的话，那份料要到成文登记时才被发现，
    # 在那之前的每一个判断都建立在一份不全的材料上。文件已经在盘上，
    # 导入是脚本的活，不用问人「放好了吗」。
    # 表态与导入互不挡路：第一级的 `decide` 看的是「这一级定没定」，不看这里给的是什么。
    # 设计开始之后不走这条——那时材料再变登记到本轮，见上面 `closed` 那支。
    state = material_state(feature_root, current, manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("run_round",
                "材料已经变了：重跑 `story_flow.py round` 登记新一轮，再拿新材料重新盘点")
    return after_material_step(feature_root, contract)


def meeting_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """材料确认之后、需求分析之前：读会、出阅读件、自检。

    会议是需求材料的一种，没有自己的材料步骤：它随其它材料一起交进来、一起导入。
    没有要做的返回 None——没有会议的需求走原来的路，这一段整段不出现。
    会上有 `question` 的话题不再生成裁决关卡：结论进蓝图，没定的进 gap，当前会议结果照原话写。
    """
    seen = meeting.inspect(feature_root)
    if seen["problems"]:
        return ("fix_meeting", "会议产物自检没过，先修再读：" + "；".join(seen["problems"][:6]))
    if seen["stale"]:
        return ("refresh_meeting",
                f"纠偏差异还没出成阅读件（{'、'.join(seen['stale'])}）：逐版跑 `story_flow.py "
                "meeting-refresh --feature <名> --meeting <主名>@<sha8>`，"
                "它按差异生成 evidence.md，问题一次报全；evidence.md 不手写")
    if seen["missing"]:
        return ("read_meeting", f"会议材料已按版本留下、还没读完（{'、'.join(seen['missing'])}）："
                "按 `phases/meeting-read.md` 读 raw.md，写逐行纠偏差异 → `meeting-refresh` 出阅读件 → "
                "一份 `meeting-notes.json` 逐话题写判断（归属、原话、finding；要人定的事写成 question，"
                "由作者在质询后按必要问人条件并入集中问答或蓝图 gap），写完跑 `status`")
    return None


def meeting_result_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """会议判断写完、议题还没形成 doc-refresh.md：把当前的会议结果写出来。没有会议或已经写好返回 None。

    **由模型写，不由脚本合成**：哪条采纳了、影响到哪、还有什么没定，要读原话才说得清。
    脚本只核它声明的输入是不是这版 notes、每个话题有没有去向、引的原文行在不在。
    """
    notes = meeting.read_notes(feature_root, [])
    problems = refresh_problems(feature_root, notes)
    if not problems:
        return None
    return ("read_meeting",
            "会议判断已写、现在形成当前的会议结果：读 `AR/story-src/meeting-notes.json`，"
            "按原话写 `AR/story-src/doc-refresh.md`——每个话题一个 "
            "`### <版本>/<话题 id> <标题>`，说清本需求实际采纳什么、影响到哪、还有什么没定、归谁定；"
            "不属于本单或已被后续决定替代的也写一句去向。已由有效依据定下的不进 gap，未定的落蓝图 gap。"
            f"开头抄一行 `<!-- meeting-basis:{meeting_basis(notes)} -->`。"
            "要给原话就写 `<版本目录>/raw.md:L起-L止`。当前缺口："
            + "；".join(problems[:4]))


def questions_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """有还没答完的设计问答时停在这一步：同一组问法原样续问，不重新生成更宽的问法。"""
    ask = asks.current_design(feature_root)
    if ask is None:
        return None
    pending = asks.pending_items(ask, contract)
    if not pending:
        return None
    shown = asks.with_answered(ask, contract)
    left = {**shown, "items": [it for it in shown["items"] if str(it["item_id"]) in pending]}
    return ("await_questions",
            f"设计后必要问答还有 {len(pending)} 题没答（{ask['ask_id']}）。把同一展示块里剩下的部分原样摆给人：\n"
            + asks.block(left) + "\n" + QUESTIONS_USAGE)


def after_material_step(feature_root: Path, contract: dict) -> tuple[str, str]:
    """材料已确认之后：会议 → 需求分析 →（设计后问答）→ 交给原生设计这一段。

    **不看材料新鲜度**：那是 `next_step` 在这之前判的。
    """
    current = contract["rounds"][-1]
    gates = round_gates(contract)

    # 材料。**先于任何需求分析**——材料不全时做的分析注定作废，
    # 每次补料都要重做一遍。这一级只需要材料盘点（清单 + 一句缺口判断）。
    material = last_gate(gates, "material_scope")
    if material is None or material["outcome"] == "rejected":
        step = material_step(feature_root,
                             always=len(contract.get("rounds") or []) <= 1 or material is not None)
        if step:
            return step

    # 材料已确认 → 有会议就先读会、形成当前会议结果；不做会议裁决关卡。
    meeting_now = meeting_step(feature_root, contract) or meeting_result_step(feature_root, contract)
    if meeting_now:
        return meeting_now

    # 材料已确认 → 做需求粒度分析；定位是整条范围链的起点，不再要求选项集/份表。
    if not current.get("positioning"):
        return ("run_analysis",
                "S2b 需求粒度分析（材料已确认）：需求概览 → 本部件视角 → 本 AR 定位 → "
                "待实现功能清单 → 来源初筛；定位落 `AR/story-src/.positioning.json` 后重跑 `round`。"
                "本部件的职责范围与交互方在激活知识里自述回答它的那一份，按各知识的 applies_when 找。"
                "待补：" + f"本 AR 定位 → {'/'.join(POSITIONING)}")

    # 设计后必要问答：有未答的就停在这一组问法上，全部答完即回原生设计续行。
    questions = questions_step(feature_root, contract)
    if questions:
        return questions

    # 交给设计这一段按原生蓝图的真实状态往下走；不能凭本地定位存在伪造原生准入。
    return design_stage_step(feature_root, contract)


def reading_work(feature_root: Path) -> dict:
    """本地阅读的工作集合：由 `story-build view --mode status` 从 Story 实际内容派生，不另存状态。读不出返回带 error 的结果。"""
    node = shutil.which("node")
    if node is None:
        return {"error": "找不到 node，本地阅读状态读不出"}
    proc = subprocess.run([node, str(Path(__file__).resolve().parents[1] / "story-build.mjs"), "view", "--mode", "status",
                           "--feature", feature_root.name, "--project-root", str(importer.project_root_of(feature_root))],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return {"error": (proc.stderr or proc.stdout).strip() or f"退出码 {proc.returncode}"}


def reading_todo(work: dict) -> str | None:
    """本地阅读还没完成时要做什么（产品状态给的 `next`）；完成（含没有正式图）返回 None。

    先认读取错误与状态自洽，再接受完成：读不出、缺字段、带着问题说完成，都按未知说，不当完成。
    """
    problems = work.get("problems")
    if (work.get("error") or not isinstance(work.get("complete"), bool) or not isinstance(work.get("applicable"), bool)
            or not isinstance(problems, list)):
        return (f"本地阅读状态读不出（{work.get('error') or '状态缺 applicable、complete 或 problems'}），没有确认阅读图是否完成"
                "——跑 `story-build view --mode status` 查")
    if work["complete"] and not problems:
        return None
    if work["complete"]:
        return f"本地阅读状态自相矛盾（说完成却列了问题：{'；'.join(map(str, problems))}）——跑 `story-build view --mode status` 查"
    return work.get("next") or f"本地阅读没有完成：{'；'.join(map(str, problems)) or '状态没给原因'}"
