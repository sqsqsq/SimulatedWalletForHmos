"""「现在走到哪、下一步干什么」：材料事实、关卡状态与阶段定位。

只读不写。材料按磁盘现状取，路由据此回答位置——同一次命令里读到的是同一份事实。

只依赖 state、inputs 与 materials.registry，不导入 decisions/rounds/lifecycle：
命令问路由，路由不问命令。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from materials import meeting, registry

from flow.state import (
    CARRY_ALL, CORE_DIR, DESIGN_DRAFT, FlowError, S4_STEPS, STORY_CONTRACT, after_complete,
    last_gate, registration_drift, round_gates, stage_of)
from flow.inputs import (
    GAPS, POSITIONING, POSITIONING_FIELDS, SCOPE_OPTIONS, read_gaps)
from flow.meetings import meeting_basis, pending_asks, refresh_problems
from flow import native

def closed_inbox_note(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """收口及之后，收件箱里还躺着没导入的原件——**把它说出来**，没有就返回空串。

    出口按位置给：已归档的走 `/story update`，其余导入、`round` 登记到本轮、改完重跑 `story` 重新登记。

    不提它，那份文件从此没有任何人知道——`round` 只看已导入的指纹说「材料未变」，
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
    if contract.get("archived") and not (contract.get("update") or {}).get("open"):
        return head + ("本单已归档送审，新材料走 `/story update` 承接；"
                       "不纳入就留在收件箱，本轮不受影响")
    return head + ("先导入、再重跑 `round` 登记到本轮（收口之后它不开新轮）；"
                   "story 已登记的，据新料改完重跑 `story` 重新登记")


def live_materials(feature_root: Path) -> dict:
    """按磁盘现状取一份材料清单 —— **同一个时点只取一次**，由调用链向内传。

    同一条命令里重复 build，是把同一批文件再哈希一遍、把收件箱再转一遍，
    而两次之间什么也没发生。写入前后是两个不同的时点，那时各取各的。
    """
    try:
        return registry.build(feature_root)
    except registry.MaterialError as exc:
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
    return {"pending": registry.pending(manifest),
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


def settled_this_round(contract: dict) -> bool:
    """拆分是不是**在当前轮**定的案。

    `split` 是契约级字段（design.md 只认最终那一份），而拆分决策属于某一轮——
    两者用 `settled_round` 挂钩，重新初析后同一份 split 就不再算数。
    """
    split = contract.get("split") or {}
    return (split.get("decided") == "split"
            and split.get("settled_round") == contract["rounds"][-1].get("round"))


#: 成文这一段的顺序，几个分支共用一句。
STORY_STAGE_ORDER = (
    "顺序：story-build skeleton → 写整篇写作设计（阅读主线与每章骨架）→ 再跑 skeleton → 逐章 chapter → "
    "回看清单逐条处置 → check 通过 → `story-build review --action prepare` 定稿（重投附录、编号、渲染 review）"
    "并准备独立审查 → 派审 → `story-build review --action check` → `story_flow.py story` 登记 → 交付门 → 交付选择")


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
    """设计输入登记之后：按原生蓝图的真实状态回答等设计还是可以成文。flow 不存准入与 revision 的副本。"""
    return design_gate(feature_root, contract) or story_stage_step(feature_root)


def design_gate(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """设计这一侧还差什么：蓝图没建、读不过、没准入、没消费本次输入或投影不对时给下一步；都成立返回 None。"""
    binding = contract.get("design_binding") or {}
    blueprint = binding.get("blueprint_id")
    entry = (contract.get("input") or {}).get("snapshot_ref")
    if not blueprint or not entry:
        raise FlowError("流程契约标了已提交，却没有设计关联（design_binding）或登记的输入（input）：契约不完整。"
                        "跑 `story_flow.py bind-design` 与 `complete` 重新提交")
    read = native.call(native.project_root_of(feature_root), "blueprint", "--blueprint", str(blueprint), "--purpose", "draft",
                       "--snapshot", str(entry))
    if read["status"] == "missing":
        return ("design_blueprint",
                f"设计输入已冻结（`{entry}`）。按 `phases/design.md` 进原生 component-design，"
                f"用这份输入建立蓝图 `{blueprint}` 并走到准入；知识在设计决定前取（story-knowledge）。"
                "本轮授权：`/story <AR>` 的启动语义是「做到交付门并问一次交付选择」（batch 多阶段声明），直接进，不问")
    if read["status"] != "ok":
        return ("fix_blueprint", f"蓝图 `{blueprint}` 原生读不过（{read['status']}）：{native.issues_text(read)}——设计职责按原生报错修正")
    if not read.get("admitted"):
        return ("design_blueprint", f"蓝图 `{blueprint}` 还没准入：按 `phases/design.md` 在 component-design 里继续到准入")
    consumption = read.get("consumption") or {}
    if consumption.get("status") != "ok":
        return ("design_blueprint",
                f"蓝图 `{blueprint}` 还没消费本次交给设计的输入（`{entry}`）：{native.issues_text(consumption)}——"
                "设计职责在 component-design 里按这份输入同步蓝图的需求条目，再重新准入")
    projection = read.get("projection") or {}
    if projection.get("status") != "valid":
        return ("design_projection",
                f"蓝图已准入，评审投影 `{projection.get('path')}` {'还没生成' if projection.get('status') == 'missing' else '与当前 revision 对不上'}："
                "由设计职责按原生 renderer 生成，Extension 不手改")
    return None


def story_stage_step(feature_root: Path) -> tuple[str, str]:
    """蓝图准入、投影有效之后，成文做到哪儿了——按磁盘上有什么说清。"""
    if not (feature_root / "AR" / "story.md").is_file():
        return ("story_skeleton",
                "蓝图已准入。跑 `story-build skeleton`：它给出成文要用的当前输入，建写作设计空壳与章草稿，"
                "并告诉你先写整篇设计还是先写哪一章。" + STORY_STAGE_ORDER)
    left = pending_chapters(feature_root)
    if left:
        return ("story_chapters",
                f"story.md 已在，还有 {left} 章带着待写标记。"
                "先跑 `story-build skeleton` 取回当前输入与下一步（写作设计还没写好时它先让你写设计）；"
                "逐章在草稿上写、`story-build chapter --from <草稿>` 落盘——"
                "每次落盘先核这一章能确定的那几条，判不过时盘上什么都不变；"
                "落盘之后它会给出下一章。" + STORY_STAGE_ORDER)
    return ("register_story",
            "十章齐了。先跑 `story-build skeleton` 取回看清单，逐条撞两问、处置回真源"
            "（业务结论改决策登记或回设计，骨架改写作设计，正文改草稿再 chapter 提交）；"
            "`story-build check` 通过之后准备独立审查（`story-build review --action prepare`）并派审，"
            "审查结果可消费之后跑 `story_flow.py story` 登记成文。" + STORY_STAGE_ORDER)


#: 停等点的回话方式：问法由 `status` 的 `ask` 给出，人回话后按它记。
DECIDE_USAGE = ("把 `status` 输出里 `ask.block` 原样摆给人（前面一句结论与缺口），停等。"
                "人回话后跑 `story_flow.py decide --feature <名> --gate <本级> --ask <ask_id> "
                "--reply \"<人的原话>\"`；原话没用编号的说法（第 n、n.、n）、选 n、整句为 n）或标签指到某一项时加 `--chosen <编号>`。"
                "自己的判断用 `decide --propose --chosen <编号> --why \"<理由>\"` 记成提议，下次停等请人确认")


def sidecar_shape(step: str) -> dict | None:
    """这一步要写的侧车长什么样：字段、合法值、为什么要它。

    形状是确定的，该在需要它的那一步就摆出来，而不是等作者去读源码或撞报错。
    """
    if step == "run_analysis":
        return {
            "写这两份": [
                {"path": "/".join(POSITIONING), "shape": dict(POSITIONING_FIELDS)},
                {"path": "/".join(SCOPE_OPTIONS),
                 "shape": [{"key": CARRY_ALL, "label": "按当前范围整体承载：列出功能点"},
                           {"key": "<切法标识>", "label": "按什么切、切成几份",
                            "recommend": "推荐这一项的一句理由（至多一项写）",
                            "parts": [{"seq": 1, "scope": "这一份承载什么", "depends_on": []},
                                      {"seq": 2, "scope": "另一份承载什么", "depends_on": [1]}]}],
                 "note": f"固定首项 {CARRY_ALL} 必须在——不切永远是一个可选项；"
                         "切法至少两份，没有份表的切法是空壳"},
            ],
        }
    if step in ("inventory_materials", "fix_material_gaps"):
        return {"path": "/".join(GAPS),
                "shape": {"missing": ["还缺的材料：名称与在哪句话里提到"], "why": "一句缺口判断"},
                "note": "missing 没有就给空数组；第一级的推荐由脚本按它算"}
    if step.startswith("await_gate:"):
        return {"回话": DECIDE_USAGE
                + ("；会议逐个话题记，另加 `--meeting <主名>@<sha8> --item <话题 id>`"
                   if step == "await_gate:meeting" else "")}
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
        return ("refresh_round", "新料已并入正文：跑 `story_flow.py round` 登记到本轮（它不开新轮），"
                "再 `story_flow.py update --action prepare`")
    return ("update_prepare", "输入已定：跑 `story_flow.py update --feature <名> --action prepare`"
            "，它比较八项并开这一轮")


def update_open_step(feature_root: Path, contract: dict,
                     manifest: dict | None = None) -> tuple[str, str]:
    """更新正在进行：去向是「按修订清单改」，**不重走材料与范围关卡**。

    新材料 `round` 登记进当前轮；提取稿改了由 `complete` 重新提交，范围沿用本单已定的；
    story 改了（或登记因提交提取稿作废）就重跑 `story` 重新登记。
    """
    rid = contract["update"]["open"]
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("refresh_round", "这一轮新到的料已并入正文：跑 `story_flow.py round` 登记到本轮"
                "（update 期间它不开新轮）")
    # 新会议照常走会议关卡：会上有要人定的话题，那是真的要人拍板
    meeting_now = meeting_step(feature_root, contract) or meeting_result_step(feature_root, contract)
    if meeting_now:
        return meeting_now
    # 这一轮 update 里重开了范围：先回范围关卡重新确认，update 照旧开着
    if contract["rounds"][-1].get("reopened") and not after_complete(contract):
        step, action = scope_step(feature_root, contract)
        if step not in S4_STEPS:
            return step, action
    if not after_complete(contract):
        return ("run_complete", f"更新 {rid}：改完提取稿 `{'/'.join(DESIGN_DRAFT)}` 与设计输入，跑 "
                f"`story_flow.py complete --feature <名> --from {'/'.join(DESIGN_DRAFT)} --input AR/story-src/design-input.json`"
                " 冻结新一版输入交给设计")
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
    if was.get("knowledge_sha256") != now.get("knowledge_sha256"):
        out.append("激活知识")
    return out


def registration_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """story 已写出来之后要不要重新登记：登记之后 story、输入、蓝图或知识变了，或状态停在已收口（update 里
    重新提交输入、重新登记没过）。不需要返回 None。还在逐章写的单不走这里，由成文那条路给下一步。
    """
    waiting = design_gate(feature_root, contract)
    if waiting:
        return waiting
    drift = registration_drift(feature_root, contract) + basis_drift(feature_root, contract)
    if drift or contract.get("status") == "complete":
        return ("register_story", (f"成文登记之后改过 {'、'.join(drift)}：" if drift else "story 还没按当前内容登记：")
                + "改完先 `story-build review --action prepare` 定稿（重投附录、编号、渲染 review、全篇 check）并重新独立审查，审查通过后跑 `story_flow.py story` 重新登记")
    return None


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
    stage = stage_of(contract)
    if stage == "update_inputs":
        return update_inputs_step(feature_root, contract, manifest)
    # 收口之后才导进来的会议：还没有会议判断的版本。收口前读过的会都已写进判断（范围关卡之前必经）
    late = (sorted(set(meeting.versions(feature_root)) - set(meeting.read_notes(feature_root, [])))
            if after_complete(contract) and stage != "update_open" else [])
    if late:
        return ("late_meeting", f"收口之后到了会议转写（{'、'.join(late)}）：按 `phases/meeting-read.md` 读会。"
                "会上有要人定的话题就先 `story_flow.py reopen` 重拍，在范围关卡摆给人；"
                "只是补充事实就读会后照常改、重跑 `story` 重新登记"
                + closed_tail(feature_root, contract, manifest))
    if stage == "update_open":
        return update_open_step(feature_root, contract, manifest)
    if stage in ("archived", "story_written"):
        reregister = registration_step(feature_root, contract)
        if reregister:
            return reregister
    if stage == "archived":
        # 归档之后收口过一轮 update：本地已按它更新，回写需求系统等人确认（`phases/update.md`「已归档」一行）
        closed = str((contract.get("update") or {}).get("last_closed") or "")
        at = str((contract.get("archived") or {}).get("at") or "")
        updated = closed[:15] > at.replace("-", "").replace(":", "").replace("T", "-")[:15]
        return ("done", ("本地已按 update 更新；回写需求系统等人确认，确认后走 `/story archive`。" if updated
                         else "本轮已归档送审。")
                + "评审意见、上游新材料与改稿走 `/story update`；要重拍范围才 `story_flow.py reopen`"
                + closed_tail(feature_root, contract, manifest))
    if stage == "story_written":
        return ("run_archived",
                "Story 已按已准入蓝图写成、经独立审查并登记。按 `phases/design.md`「五、独立审查、登记与交付」走完："
                "`story-build check --deliver` 交付门；通过后按停等表问一次交付选择"
                "（送审 / 完整设计交接 / 完整实现 / 暂不推进；本地单没有送审）"
                + closed_tail(feature_root, contract, manifest))
    if stage == "complete":
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
                    "再继续——设计输入与叙事件都按本轮登记的那批料写"
                    + closed_tail(feature_root, contract, manifest))
        step, action = design_stage_step(feature_root, contract)
        return step, action + closed_tail(feature_root, contract, manifest)

    current = contract["rounds"][-1]

    # **已到的材料先处理完，再谈别的**——人回答没回答都一样。
    #
    # 收件箱里躺着原件而流程往下走的话，那份料要到成文登记时才被发现，
    # 在那之前的每一个判断都建立在一份不全的材料上。文件已经在盘上，
    # 导入是脚本的活，不用问人「放好了吗」。
    # 表态与导入互不挡路：第一级的 `decide` 看的是「这一级定没定」，不看这里给的是什么。
    # 收口之后不走这条——那时材料再变登记到本轮，见上面 `complete` 那支。
    state = material_state(feature_root, current, manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("run_round",
                "材料已经变了：重跑 `story_flow.py round` 登记新一轮，再拿新材料重新盘点")
    return scope_step(feature_root, contract)


def meeting_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """材料确认之后、需求分析之前：读会、出阅读件、自检、有要问人的话题时停一次。

    会议是需求材料的一种，没有自己的材料步骤：它随其它材料一起交进来、一起导入。
    没有要做的返回 None——没有会议的需求走原来的路，这一段整段不出现。
    停不停由会议判断里有没有带 `question` 的话题决定（脚本枚举），不由模型临场判。
    当前会议结果在人裁决之后写（`meeting_result_step`），不在这里：人还没表态时
    写出来的「当前结论」，下一刻就可能被那次裁决改掉。
    """
    seen = meeting.inspect(feature_root)
    if seen["problems"]:
        return ("fix_meeting", "会议产物自检没过，先修再摆关卡：" + "；".join(seen["problems"][:6]))
    if seen["stale"]:
        return ("refresh_meeting",
                f"纠偏差异还没出成阅读件（{'、'.join(seen['stale'])}）：逐版跑 `story_flow.py "
                "meeting-refresh --feature <名> --meeting <主名>@<sha8>`，"
                "它按差异生成 evidence.md，问题一次报全；evidence.md 不手写")
    if seen["missing"]:
        return ("read_meeting", f"会议材料已按版本留下、还没读完（{'、'.join(seen['missing'])}）："
                "按 `phases/meeting-read.md` 读 raw.md，写逐行纠偏差异 → `meeting-refresh` 出阅读件 → "
                "一份 `meeting-notes.json` 逐话题写判断（归属、原话、finding，要问人的写 question 与选项），"
                "写完跑 `status`")
    asks = pending_asks(seen["notes"], contract)
    if asks:
        return ("await_gate:meeting", "会议里有要人定的话题，停这一次："
                "`status` 的 meetings 已逐条列出全部版本与话题（归属、finding、原话位置、"
                "待裁决的问题与选项）——要问的带选项并补上推荐理由，不问的一句摘要说明按会议采纳；"
                f"人一轮答完再逐条 `decide --gate meeting`：{'、'.join(asks)}")
    return None


def meeting_result_step(feature_root: Path, contract: dict) -> tuple[str, str] | None:
    """会议话题该裁决的都裁决了：把当前的会议结果写出来。没有会议或已经写好返回 None。

    **由模型写，不由脚本合成**：哪条采纳了、影响到哪、还有什么没定，要读原话与人的裁决才说得清。
    脚本只核它声明的输入是不是当前这版、每个话题有没有去向、引的原文行在不在。
    """
    notes = meeting.read_notes(feature_root, [])
    problems = refresh_problems(feature_root, notes, contract)
    if not problems:
        return None
    return ("read_meeting",
            "会议判断已定、要人定的话题都已裁决，现在形成当前的会议结果：读 `AR/story-src/meeting-notes.json` 与"
            "契约里人选的那几笔，按原话写 `AR/story-src/doc-refresh.md`——每个话题一个 "
            "`### <版本>/<话题 id> <标题>`，说清本需求实际采纳什么、影响到哪、还有什么没定；"
            "不属于本单或已被后续决定替代的也写一句去向。"
            f"开头抄一行 `<!-- meeting-basis:{meeting_basis(notes, contract)} -->`。"
            "要给原话就写 `<版本目录>/raw.md:L起-L止`。当前缺口："
            + "；".join(problems[:4]))



def scope_step(feature_root: Path, contract: dict) -> tuple[str, str]:
    """本轮范围定到哪一级了——材料关卡、会议、需求分析、后两级关卡与 S4。

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
    if material is None or material["outcome"] == "rejected":
        step = material_step(feature_root,
                             always=len(contract.get("rounds") or []) <= 1 or material is not None)
        if step:
            return step

    # 材料已确认 → 有会议就先读会（有要人定的话题停一次），形成当前的会议结果，
    # 再做需求粒度分析：分析与提取读的都是它
    meeting_now = meeting_step(feature_root, contract) or meeting_result_step(feature_root, contract)
    if meeting_now:
        return meeting_now

    # 材料已确认 → 才做需求粒度分析（全景 / 本部件 / 本 AR 定位 / 功能清单 / 范围定法选项）
    if not current.get("positioning") or not current.get("scope_options"):
        missing = []
        if not current.get("positioning"):
            missing.append(f"本 AR 定位 → {'/'.join(POSITIONING)}")
        if not current.get("scope_options"):
            missing.append(f"范围定法选项集 → {'/'.join(SCOPE_OPTIONS)}")
        return ("run_analysis",
                "S2b 需求粒度分析（材料已确认）：需求概览 → 本部件视角 → 本 AR 定位 → "
                "待实现功能清单 → 范围定法选项 → 来源初筛；落盘后重跑 `round`。"
                "本部件的职责范围与交互方在激活知识里自述回答它的那一份，"
                "按各知识的 applies_when 找。"
                "待补：" + "；".join(missing))

    # 第二级：这个范围怎么定
    decision = last_gate(gates, "scope_decision")
    if decision is None:
        return ("await_gate:scope_decision",
                "S3 第二级：照出契约里的范围定法选项集（分析定几项就摆几项），取得选择")

    # 第三级：本 AR 承载哪一份（仅在选了某个切分维度时）
    if decision["chosen"] != CARRY_ALL and not settled_this_round(contract):
        return "await_gate:split_carrier", "S3 第三级：呈现该维度的份表，取得本 AR 承载哪份"

    # 范围已定——整体承载，或份表已定案。直接进 S4
    if not (feature_root / Path(*DESIGN_DRAFT)).is_file():
        return ("generate_design",
                "S4：按 rules/ar_design_init.md 提取，写到 "
                f"`{'/'.join(DESIGN_DRAFT)}`——`AR/design.md` 是上游给进来的原件，不覆盖；"
                "提取稿作为派生分析与采用的原件一起交给设计")
    bind = "" if contract.get("design_binding") else (
        "先 `story_flow.py bind-design --feature <名> --component <组件> --blueprint <蓝图>` 关联设计对象，再")
    return ("run_complete",
            f"提取稿已在。{bind}按 `phases/design.md` 写设计输入 `AR/story-src/design-input.json`（采用的原件与图、"
            "人签编号、需求条目），跑 `story_flow.py complete --feature <名> "
            f"--from {'/'.join(DESIGN_DRAFT)} --input AR/story-src/design-input.json` 冻结并交给设计")
