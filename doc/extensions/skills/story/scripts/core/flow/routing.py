"""「现在走到哪、下一步干什么」：材料事实、关卡状态与阶段定位。

只读不写。材料按磁盘现状取，路由据此回答位置——同一次命令里读到的是同一份事实。

只依赖 state、inputs 与 materials.registry，不导入 decisions/rounds/lifecycle：
命令问路由，路由不问命令。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from materials import meeting, registry

from flow.state import (
    CARRY_ALL, DESIGN_DRAFT, FlowError, STORY_CONTRACT, after_complete,
    last_gate, round_gates)
from flow.inputs import (
    GATE_OPTIONS, POSITIONING, POSITIONING_FIELDS, SCOPE_OPTIONS, material_options,
    read_gate_options, sidecar_gate)
from flow.meetings import meeting_basis, pending_asks, refresh_problems

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
    "story-build skeleton → 写整篇写作设计（阅读主线与每章骨架）→ 再跑 skeleton → 逐章 chapter → "
    "回看清单逐条处置 → "
    "story_flow.py story 登记"
    "（它自己跑 number / build / check，review 一并渲染并核过归档件红线）→ harness → verifier。"
    "**harness 放在成文登记之后**——之前跑它一定红在「三份产物不齐」")


def pending_chapters(feature_root: Path) -> int:
    """story 里还带着待写记号的章数 —— **只读**，不在这里重做章级检查。

    记号的真源是章节合同的 ``pending_mark``；合同读不到是包坏了，照实报错。
    """
    try:
        text = (feature_root / "AR" / "story.md").read_text(encoding="utf-8")
    except OSError:
        return 0
    mark = str(json.loads(STORY_CONTRACT.read_text(encoding="utf-8"))["pending_mark"])
    return len(re.findall(r"<!--\s*" + re.escape(mark) + r"[:：]", text))

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
                "spec.md 已在。跑 `story-build skeleton`：它给出成文要用的当前输入"
                "（材料里的图、系统设计与 Spec 里的图），建写作设计空壳与章草稿，"
                "并告诉你先写整篇设计还是先写哪一章。" + SPEC_STAGE_ORDER)
    left = pending_chapters(feature_root)
    if left:
        return ("story_chapters",
                f"story.md 已在，还有 {left} 章带着待写标记。"
                "先跑 `story-build skeleton` 取回当前输入与下一步（写作设计还没写好时它先让你写设计）；"
                "逐章在草稿上写、`story-build chapter --from <草稿>` 落盘——"
                "每次落盘先核这一章能确定的那几条，判不过时盘上什么都不变；"
                "落盘之后它会给出下一章。" + SPEC_STAGE_ORDER)
    return ("register_story",
            "十章齐了。先跑 `story-build skeleton` 取回看清单，逐条撞两问、处置回真源"
            "（业务结论改 Spec 或决策登记，骨架改写作设计，正文改草稿再 chapter 提交），"
            "`story-build check` 通过之后跑 `story_flow.py story` 登记成文"
            "——**登记之前跑 harness 一定红**。" + SPEC_STAGE_ORDER)


def sidecar_shape(step: str) -> dict | None:
    """这一步要写的侧车长什么样：字段、合法值、为什么要它。

    形状是确定的，该在需要它的那一步就摆出来，而不是等作者去读源码或撞报错。
    合法值取自本模块的常量，不另立一份。
    """
    if step == "run_analysis":
        positioning = dict(POSITIONING_FIELDS)
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
    if step == "await_gate:meeting":
        return {"不写侧车": "选项就是会议判断里那个话题的 options，全部话题在本次输出的 meetings 里；"
                "人答完逐条跑 `decide --gate meeting --meeting <主名>@<sha8> --item <话题 id> "
                "--chosen <key> --basis \"<人的原话>\"`"}
    if step.startswith("await_gate:"):
        gate = step.split(":", 1)[1]
        note = {
            "写这份，再去问人": {
                "path": "/".join(GATE_OPTIONS),
                "shape": {"gate": gate,
                          "options": [{"key": "<选项标识>", "label": "人能看懂的选项文字"}]},
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
        read_gate_options(feature_root, "material_scope", remaining=True)
    except FlowError as exc:
        return True, str(exc)
    return True, None


def frozen_tail(feature_root: Path, contract: dict, manifest: dict | None = None) -> str:
    """冻结态的下一步末尾那一句：收件箱里有没有没人管的原件。`next` 本身不变。"""
    note = frozen_inbox_note(feature_root, contract, manifest)
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

    问法、侧车、人签、登记全是 init 第一级那一套；差别只在它每次 update 都停一次——
    上游变没变、手上还缺什么，只有人说了才算定。
    """
    answer = inputs_answer(contract)
    if answer is None or answer.get("outcome") != "accepted":
        if sidecar_gate(feature_root) == "material_scope":
            try:
                # 问的是「这一次要不要补」，不是补过一轮之后的剩余缺口
                read_gate_options(feature_root, "material_scope", remaining=False)
            except FlowError as exc:
                return "fix_gate_options", f"这一级的选项侧车还立不住，先补齐再问人：{exc}"
        return ("await_gate:material_scope",
                "update 的输入阶段：**先摆选项侧车再问人**——报告上游哪几份变了、没变、取不到，"
                "本地已有什么，一句缺口判断，问这一次要不要补料："
                + " / ".join(str(o.get("label") or o["key"]) for o in material_options()))
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    if state["changed"]:
        return ("refresh_round", "新料已并入正文：跑 `story_flow.py round` 登记到本轮（它不开新轮），"
                "再 `story_flow.py update --action prepare`")
    return ("update_prepare", "输入已定：跑 `story_flow.py update --feature <名> --action prepare`"
            "，它比较八项并开这一轮（全都没变就直接说没变）")


def update_open_step(feature_root: Path, contract: dict,
                     manifest: dict | None = None) -> tuple[str, str] | None:
    """更新正在进行：去向是「按修订清单改」，**不重走材料与范围关卡**——收口前后都是这一句。

    不加这一支的话，update 改完材料一跑 status，路由会把人送回材料盘点与范围关卡；
    `reopen` 之后状态回到 in_progress，常规路径也会把它当成一轮新的范围判断。
    范围这一轮并没有重新定，材料也不是「补了一批要重新拍板」，是一次有明确依据的修订。

    返回 None 的只有一种：reopen 之后材料又变了——那时 `round` 会开新轮，
    交回常规路径如实说「要重新走关卡」，不在这里假装它还是一次修订。
    """
    rid = contract["update"]["open"]
    state = material_state(feature_root, contract["rounds"][-1], manifest)
    pending = pending_import_step(state)
    if pending:
        return pending
    closed = after_complete(contract)
    if state["changed"]:
        if not closed:
            return None
        return ("refresh_round", "这一轮新到的料已并入正文：先跑 `story_flow.py round` 登记到本轮"
                "（它不开新轮），**再** `reopen`——反过来，路由会按「材料变了」把你送回关卡")
    if not closed:
        # 新会议照常走会议关卡：会上有要人定的话题，那是真的要人重新拍板
        meeting_now = meeting_step(feature_root, contract) or meeting_result_step(feature_root, contract)
        if meeting_now:
            return meeting_now
    return ("update_in_progress",
            f"更新 {rid} 正在进行：按 AR/story-src/updates/{rid}/update-notes.md 里的修订清单改，"
            "不重走材料与范围关卡。改章的顺序：`story_flow.py reopen` 撤销成文登记 → "
            "`complete` 收口（范围与材料没变，它直接过）→ 在草稿上改、`chapter` 提交 → "
            "`story` 重新登记。**新到的料先 `round` 登记到本轮，再 reopen**。"
            "范围本身要变不在这一轮做：报「尚未完成：范围需重新拍板」并收口保留项，由人走 `reopen` 重拍。"
            "改完：`--revalidate` → 派 verifier → 完整跑一次 `harness-runner.ts --phase <阶段>` → "
            "`story_flow.py update --action close` 收口这一轮"
            + frozen_tail(feature_root, contract, manifest))


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
    update = contract.get("update") or {}
    if update.get("stage") == "inputs":
        return update_inputs_step(feature_root, contract, manifest)
    # 收口之后才导进来的会议：还没有会议判断的版本。收口前读过的会都已写进判断（范围关卡之前必经）
    late = (sorted(set(meeting.versions(feature_root)) - set(meeting.read_notes(feature_root, [])))
            if after_complete(contract) else [])
    if late:
        return ("reopen_meeting", f"收口之后到了会议转写（{'、'.join(late)}）：一场会一轮，"
                "先跑 `story_flow.py reopen`，再读会；有要人定的话题时摆给人一次"
                + frozen_tail(feature_root, contract, manifest))
    if update.get("open"):
        step = update_open_step(feature_root, contract, manifest)
        if step:
            return step
    if contract.get("status") == "story_written" and contract.get("archived"):
        return ("done", "本轮已归档送审。评审意见与上游新材料走 `/story update`；补料或改稿先 `story_flow.py reopen`"
                + frozen_tail(feature_root, contract, manifest))
    if contract.get("status") == "story_written":
        # 产物没变就不重跑 harness：它每跑一次都重新派生 subject，换了代就要重审，而产物一个
        # 字节没动。check-receipt 报 subject 失配、或产物确实改了才重跑，那时 verifier 也要再来一次。
        return ("run_archived",
                "叙事件已登记成文（review.md 已在登记那一步渲染并核过）。"
                "按这个顺序走完，中间不回头："
                "跑 harness（spec 闭环）→ 按 harness 末尾 `NEXT:` 行派 verifier"
                "（它说没有审查员就直接下一步）→ check-receipt → "
                "`story-build check --deliver` 交付门。"
                "**交付门通过之后按它打印的选择走**：归档送审、进入 plan，或先归档再进 plan；"
                "本地单没有归档，只有进 plan。"
                "**产物没变化就不重跑 harness、不重审**（复用已有结论）；"
                "verifier 回复之后闭环链不回头：有阻断项才返修（见下），没有就走完上面的链。"
                "闭环之后发现的真实问题（有内容依据的 WARN 也算）走 framework 修正入口："
                "`harness-runner.ts --correction-init` 定责任层 → 改真源 → "
                "`--revalidate --feature <名>`（只重跑脚本门禁，verifier 不重审，回执标沿用已有 PASS）；"
                "**不重跑闭环链、不手动派 verifier**。纯表达类 WARN 交评审回流或下一轮；"
                "交付门上人的评审意见走 `/story update`。已做的正确修改不回滚。回执由 harness 生成，不用你填。"
                "verifier 报了阻断问题就跑 `story_flow.py reopen` 撤销成文登记，照它给出的下一步走"
                "（范围与材料没变时先 `complete` 收口），再在草稿上改、`chapter` 提交、`story` 重新登记"
                "——材料变了再审是正常返修，不是重复审"
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
    stops, problem = material_gate_state(feature_root, contract)
    if material is None and problem:
        return ("fix_gate_options",
                f"这一级的选项侧车还立不住，先补齐再问人：{problem}")
    if material is None and stops:
        return ("await_gate:material_scope",
                "S3 第一级：**先摆选项侧车再问人**——带出材料清单与一句缺口判断，取得选择："
                + " / ".join(str(o.get("label") or o["key"]) for o in material_options()))
    if material and material["outcome"] == "rejected":
        return ("await_gate:material_scope",
                "上一笔被驳回（收件箱里没有新文件、材料也没变），在第一级重新取得选择")

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
                f"`{'/'.join(DESIGN_DRAFT)}`——`AR/design.md` 是上游给进来的输入件，"
                "提取稿另成一份，由收口那一步提交上去")
    return ("run_complete",
            "提取稿已在。跑 `story_flow.py complete --feature <名> "
            f"--from {'/'.join(DESIGN_DRAFT)}` 提交并收口")
