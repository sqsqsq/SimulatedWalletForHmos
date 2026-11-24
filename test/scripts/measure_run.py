# -*- coding: utf-8 -*-
"""实跑效率度量 —— 从 ``events.jsonl`` 读出批次 3 的七项目标是否达成。

## 为什么要有它

批次 3 的诊断是「时间花在猜门禁要什么」：实测门禁回环占全程 49.3%，读 ``framework/**``
与 ``doc/extensions/**`` 合计是读自身产物的 2.8 倍，``check-spec.ts`` 被读 9 次——
模型在逆向 checker 学要求。这些结论当时是人工统计出来的；没有脚本，下一轮就无从比较。

**它只报数，不判 PASS/FAIL**：数字是诊断信息，不是写作命令（G8）。
达标与否由人看着数字判断，脚本不替它下结论。

## 读数口径（TEST.md §6.1 六项）

- 第 2、3 项只看工具**入参**（读了什么），**含 shell 里的读**（bash / pwsh 等）：``cat`` / ``sed`` / ``grep`` / ``Get-Content``，以及
  ``node -e "readFileSync(...)"``（一轮实跑读判据脚本 68 次全走最后这一种，当时口径只认前几种，报表上写着 0）。
- 第 3 项的对象是机制源码：``framework/`` 下的 ``.ts`` 与 ``doc/extensions/`` 下的 ``.mjs``/``.py``，
  读取类动作的参数里出现就计一次；知识层是 ``.md``，不在其内——读知识是正当的。
- 第 4 项只看门禁调用的**输出**（门禁报了什么），同一 check id 按**门禁轮次**去重——一份报告被 console 打一次、又被 ``cat`` 一次不算两轮，
  读一份旧报告也不是一轮门禁。
- ``gate_rounds_with_fail`` 只数原生 harness 有 FAIL 的轮次（原义不变）；同一调用结果另派生 ``gate_fail_by_kind`` 与
  ``gate_unknown_by_kind``（harness / story_register 分计）：缺结果、同键冲突或 ``source_truncated`` 的调用记 unknown，
  不当成通过；登记成功（含原生成功的补登记）不算失败。报告不能用 harness=0 概括「本轮没有 FAIL」。
- 三个字段：``gate_rounds_with_fail``（有 FAIL 的门禁轮次）；``gap_sec_by_kind``（门禁 / verifier / 成文 / 其它的时间去向，
  **按事件间隔归属的近似值**，字段名如实标注；并发调用的区间相互重叠，不能相加成墙钟）；``human_wait_sec``（**由驱动器累计**，
  与模型耗时分开；读不到时报 ``null`` 而不是 0——「这轮没人等过」和「这份记录里没这个字段」是两件事）。
- verifier 只认专用 ``verifier`` 工具与 ``subagent_type=verifier`` 的 task；其它委派计进 ``delegations_unresolved``，是不是审查由人判断。
- 有保全的 dsh 原生会话（``<run>/native-sessions/``）时，``delegations`` 按原生调用认委派的角色：派出去的是产品生成的
  Story 派审载体、蓝图质询载体或阅读图任务，就是那一类审查；派出去的子会话写了需求 ``blueprint/`` 下的设计产物，是蓝图作者；专用 ``verifier``
  工具是阶段审查；其余按 ``unresolved`` 带上 label 交人判。label 只用来定位，不定角色。每个子会话给原生登记到收尾通知的
  **观察跨度**（含等待与排队，不是纯推理时间）与收尾状态；没有收尾通知的跨度是 unknown，不按 0 算。
- 门禁种类另分 ``story_check``（``story-build check``）、``review_check``（``story-build review --action check``，按结论值计
  ``review_results``）与 ``deliver``（``check --deliver``）：成文检查没过、审查结论 fail 或 report_invalid、交付门没过各自计数；
  交付门一次过不说明此前的检查、审查与返修都没有发生。

## 一次调用

所有计数按**调用**算，不按事件条数。有的宿主一次调用只发一条完成事件，有的先发开始、再发不带工具名的结果；
``tool_call_view`` 把两种都归并成调用：同一 run 里同一 ``tool_call_id`` 的开始与终态是一次调用，名称与入参取开始，输出与终态取结果。
归并不了的条目进 ``incomplete_tool_events``（只有结果、只有开始、同键冲突、跨检查点），有这类条目时计数只是已观察到的次数。
只开始没结果的调用计用了什么、读了什么，不计门禁结论。
- 第 5 项按本次实际执行体和阶段取值，说明 input/output/cache/context 字段的含义与累计方式。run_id 变化不证明上下文重置，
  上下文大小不证明是否派过独立作者；无法取得的轨迹标未知。**usage 事件是父会话这一次的上下文读数，不是全部模型 API 调用数**：
  子会话的用量不在父公共事件流里，不能拿父 usage 相加当全模型成本。
- 第 6 项分开记录装配内容和消费模型实际收到的内容，字节不直接当 token。耗时拆分要标工具时间、事件间隔估计或人工等待，
  扣除故障后的估算不是修复后的实测。
- **父/子分列**：父会话的 assistant 响应（`type: text` 事件数）与工具调用（公共事件按调用归并）只算父；
  子会话的 assistant 响应与工具调用从保全的原生会话数，两者口径不同，**不能相加成一次模型 API 次数**，
  也不能用 `native-sessions/children/` 的目录数冒充调用数。没有保全原件时子会话数记 null，不是 0。
- **审查按实际任务分开计**：每个委派给 `task_id`（原生 childId）、`reply_received`（取没取得回复文本）、
  `report_completeness`（报告是否可核完整）、`objects`（派出去的审查对象键个数）；汇总
  `story_review_tasks / replies / full_replies / reports_unknown / objects`。任务是否收尾（`settled`）、
  有没有回复文本、报告是否可核完整是三件事：收尾通知里带着收尾标志不等于拿到了完整报告，
  完整回复只计可核完整的那几份，其余单列未知。目录数不是任务数。有现行报告合同的派审，报告完整性用
  **同一次派审、同一对象、所配位置上成功结果对应的完整写入（读者原件）**（取自保全的读者子会话）与整份
  final 对同一份正文；只有失败或没有结果的调用、写进别的相对目录或同名后缀、只有开头两行、只有正文的
  一部分都记 unknown。载体没有现行报告合同的历史派审才按当时的完整报告形态读取，现行作者自己选的
  Markdown 标题不改变证据标准；不据回复长短或正文里的字样推断。
- **耗时只报能核实的那几类**：墙钟（首末事件）、驱动器累计的人工等待、可核工具调用区间、可核子任务观察区间、
  返修窗口与未知。区间用**并集**计算，交叠部分不重复累加也不重复扣除；`not_attributed_sec` 是墙钟减去可核区间后的
  未归属部分，含模型推理、宿主准备、等待与事件空档，**不是纯推理时间**。`nontool_gap_sec` 与 `tool_gap_sec`
  是相邻事件间隔的近似估计，不是实测 span。

用法：
    python measure_run.py <events.jsonl 或含它的目录> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: 读「规则文本」的路径形态——判它是不是在猜门禁要什么，而不是在读自己的产物。
RULE_PATH_RE = re.compile(r"(framework/|doc/extensions/)")

#: 机制源码：读它 = 在逆向判据。目标是 0 次。
#:
#: 只认两种：机制源码文件——framework 下的 `.ts`（含 `*.ts` 通配）、扩展下的 `.mjs`/`.py`；
#: 以及对源码目录的递归检索——framework 整个目录、它的 harness 源码目录（不含 prompts、reports、
#: state、templates、schemas）、扩展的 hooks 目录、skills 目录与各 skill 目录及其 scripts 目录。
#: 目录带不带结尾斜杠都认；目录名不带点，具体文件（提示词、报告、知识）不会被当成目录；
#: 写在引号里的是检索词，不是路径。Glob 按它要列的文件认，只看源码文件那一种。
#: 知识层是 `.md`，不在其内：那是给模型实现需求用的内容，读它是正当的。
_SOURCE_DIRS = (
    r"(?<=[\s/])framework"
    r"|framework/(?:[\w-]+/)*harness(?:/(?!(?:prompts|reports|state|templates|schemas)\b)[\w-]+)*"
    r"|doc/extensions/(?:base/)?hooks(?:/[\w-]+)*"
    r"|doc/extensions/(?:base/)?skills(?:/[\w-]+)?"
    r"|doc/extensions/(?:base/)?skills(?:/[\w-]+)*/scripts(?:/[\w-]+)*")
SOURCE_FILE_RE = re.compile(r"framework/[\w/.*-]+\.ts\b|doc/extensions/(?:base/)?[\w/.*-]+\.(?:mjs|py)\b")
CHECKER_PATH_RE = re.compile(rf"{SOURCE_FILE_RE.pattern}|(?:{_SOURCE_DIRS})/?(?=[\s|;)]|$)")

#: 从 bash 命令里认出「在读文件」——bash 常被当成第二套 Read。
#:
#: `node -e "readFileSync(...)"` 也是读：一轮实跑里 68 次读判据脚本**全部**走这条，
#: 而当时的口径只认 `cat/head/sed`，于是报表上写着「读 checker 源码 0 次」。
#: 度量报 0 而实际 68，比没有这项度量更坏——它让人以为这条已经解决了。
#: 图围栏——与 story-build check 的形态判据同一个口径（mermaid 及几种等价标记）。
DIAGRAM_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)[ \t]*(?:mermaid|plantuml|puml|dot|graphviz)\b",
                              re.IGNORECASE)

#:
#: **读取动词要直接作用于那条路径**（算法 v3）：命令按引号外、未转义的管道、`&&`、`;` 切段，
#: 只有「段首是读取动词」或「段里有内联读文件」且路径在同一段里，才算读；一次工具调用计一次。
#: `node …/story-build.mjs check | tail -20` 是执行判据脚本再截输出，不是读它的源码。
#: v2 把 grep 模式里的 `\|` 当成管道切段，模式之后的路径落进没有读取动词的段里，读不出来。
READ_ALGORITHM = "v3"
READ_VERB_RE = re.compile(
    r"^(?:cat|head|tail|sed|less|more|type|grep|rg|awk|findstr|get-content|gc|select-string|sls)\b",
    re.IGNORECASE)
INLINE_READ_RE = re.compile(r"readFileSync|readFile\b|open\(")
#: 执行外部脚本文件（非 `-e`/`-c`/`--eval` 内联脚本）：避免把带业务参数文本的脚本执行误当读源码
EXEC_SCRIPT_RE = re.compile(
    r"^(?:node|python3?|py|npx\s+(?:ts-node|tsx)|ts-node|tsx)\s+(?!-(?:e|c)\b|--eval\b)(?:[\"']?[^\s\"']+\.(?:mjs|js|py|ts)\b)",
    re.IGNORECASE)
#: 切段只认引号外、未转义的分隔符：grep 模式里的 `\|` 与引号里的 `|` 是模式的一部分，不是管道。
SEGMENT_SEPARATORS = ("||", "&&", "|", ";", "\n")
#: PowerShell 包了一层：`"…powershell.exe" -Command "rg …"`——剥掉外壳再切段
POWERSHELL_WRAPPER_RE = re.compile(r"^.*?-command\s+[\"']?", re.IGNORECASE)


def _split_segments(command: str) -> list[str]:
    """按管道、`&&`、`;`、换行切段；引号里的与反斜杠转义的分隔符不切。"""
    segs, cur, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and i + 1 < len(command):
            cur.append(command[i:i + 2])
            i += 2
            continue
        if quote:
            quote = None if ch == quote else quote
            cur.append(ch)
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
            i += 1
            continue
        sep = next((x for x in SEGMENT_SEPARATORS if command.startswith(x, i)), None)
        if sep:
            segs.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return segs


def _read_segments(command: str) -> list[str]:
    """bash 命令里真正在读文件的那几段（读取动词打头，或非执行脚本段内有内联读文件）。"""
    out = []
    for seg in _split_segments(command):
        if "-command" in seg.lower():
            seg = POWERSHELL_WRAPPER_RE.sub("", seg, count=1)
        s = seg.strip().strip("\"'").strip()
        if READ_VERB_RE.match(s):
            out.append(s)
        elif INLINE_READ_RE.search(s) and not EXEC_SCRIPT_RE.match(s):
            out.append(s)
    return out

#: 门禁在**控制台输出**里报一条 check 的形态（report-generator 的 printReportToConsole）：
#:     ``  ✗ FAIL [BLOCKER] feature_artifact_resolution``
#: 只锚 ASCII 段。徽标里的 ✗ 在 Windows 控制台常被转成乱码，中文 details 更是整段花掉；
#: 旧口径写成 ``<id>\s*(FAIL|未通过)``——**方向正好相反**，真实输出里 id 在 FAIL 之后，
#: 所以它在任何一份真实事件流上都恒为空。
CHECK_LINE_RE = re.compile(r"(FAIL|WARN)\s*\[(BLOCKER|MAJOR|MINOR)\]\s*([A-Za-z0-9_.]+)")

#: chalk 在非 TTY 下不上色，但捕获链路里偶有残留；剥掉再匹配，别让颜色码把 id 切断。
ANSI_RE = re.compile("\x1b\\[[0-9;]*m")

#: 一次 harness 调用 = 一轮门禁。判「同一 check id 反复 FAIL」要按轮次去重，
#: 不能按文本出现次数——同一份报告被 console 打一次、又被 cat 一次就会翻倍。
HARNESS_CMD_RE = re.compile(r"harness-runner")
#: story 成文登记：`story_flow.py story`。
STORY_REGISTER_RE = re.compile(r"story_flow\.py\S*\s+story\b")
#: 成文检查、交付门与审查结论的命令（story-build 的子命令）
DELIVER_RE = re.compile(r"story-build\.mjs\S*\s+check\b[^\n]*--deliver")
STORY_CHECK_RE = re.compile(r"story-build\.mjs\S*\s+check\b")
REVIEW_CHECK_RE = re.compile(r"story-build\.mjs\S*\s+review\b[^\n]*--action\s+check")
#: 审查结论：`review --action check` 输出里的 result
REVIEW_RESULT_RE = re.compile(r"\"result\":\s*\"([a-z_]+)\"")
#: 成文登记没过时输出里的形态（check 报「N 处未通过」或登记被拒）。
REGISTER_FAIL_RE = re.compile(r"未通过|没有登记|拒绝登记|\"ok\":\s*false")

#: `story-build check` 通过时打印的两个数：多少条机器核实、多少条交给模型裁。
#: 它说明守恒有多少压在模型层上——模型层的保证只能靠对抗测试证明，
#: 这个数越大，那份对抗测试就越要紧。**只报数，不判达标**（G8）。
CONSERVATION_RE = re.compile(r"机器核实\s*(\d+)\s*条[、,]\s*模型裁决\s*(\d+)\s*条")


def _iter_events(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _strings(value) -> list[str]:
    """结构化入参里的**真实字符串值**，逐层取出。

    不先 `json.dumps` 再匹配：序列化会把 Windows 路径的每个反斜杠转义成两个，
    `doc\\extensions\\...` 于是和任何路径正则都对不上——两份实跑的规则读取就这样被报成了 0。
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _norm_path(text: str) -> str:
    """路径比较前归一：反斜杠当斜杠，连续的分隔符并成一个。"""
    return re.sub(r"/{2,}", "/", text.replace("\\", "/"))


def _request_text(event: dict) -> str:
    """**作者要什么**：工具入参与事件正文。路径类判定只看这里。

    绝不把 `tool_output` 掺进来：Read 的输出里带着整份文件正文，一份 `doc/features/` 产物
    只要正文里提了 `framework/`，就会被算成「在读规则文本」。输入面才是作者的意图。
    """
    parts = [str(event.get("content") or ""), *_strings(event.get("tool_input"))]
    return _norm_path("\n".join(parts))


def _output_text(event: dict) -> str:
    """**工具回了什么**：门禁报的 check id、失败轮次、守恒两层的数都只在这里。

    旧口径整个漏了这一面（只读 content + tool_input），于是「反复 FAIL 的 check」在任何
    真实事件流上恒为空——不是「没有反复失败」，是压根没看那半边。ANSI 先剥掉再匹配。
    """
    out = event.get("tool_output")
    if isinstance(out, (dict, list)):
        out = json.dumps(out, ensure_ascii=False)
    return ANSI_RE.sub("", str(out or ""))


#: 宿主的 shell 工具：命令里的读取、门禁与登记都从它们的入参认
SHELL_TOOLS = {"bash", "pwsh", "shell", "shell_command"}
#: 委派类工具：只有专用 verifier 工具、或 task 指明 subagent_type=verifier 才算独立审查
DELEGATION_TOOLS = {"task", "subagent", "subagent_fork"}
AUTHORING_TOOLS = {"write", "edit", "patch", "multiedit"}
#: 调用还没结束的状态；其余（completed / error / cancelled …）都是终态
OPEN_STATUSES = {"started", "pending", "running", "in_progress"}
#: 调用正常结束的状态；历史单事件记录没写状态时按正常结束读
SUCCESS_STATUSES = {"completed", "success", ""}


def _facts(event: dict) -> tuple[str, str]:
    return (str(event.get("tool_name") or "").lower(),
            json.dumps(event.get("tool_input") or {}, ensure_ascii=False, sort_keys=True))


def _outcome(event: dict) -> tuple[str, str]:
    return str(event.get("tool_status") or ""), _output_text(event)


def tool_call_view(events: list[dict], native: dict[str, list[dict]] | None = None) -> tuple[list[dict], list[dict]]:
    """公共 tool 事件归并成调用：返回（按开始先后排列的调用，归并不了的条目）。

    键是 (run_id, tool_call_id)：并发交错按键配，不按相邻行或工具名；不同 run 复用的编号各算各的。
    没有编号的事件自身带名字就是一次调用（单事件宿主与历史记录），不和别的无编号事件猜配。
    每个调用记下它名下所有事件的位置，事件间隔按它归属。
    `native` 是本 run 保全的原生会话里的调用（callId → 各会话里的那一次）：公共事件被截断或缺结果的一侧，
    由同一原生调用的完整入参与结果补齐后再分类（见 `_complete_from_native`）；补不齐的照旧记截断或缺结果。
    """
    calls: list[dict] = []
    incomplete: list[dict] = []
    by_key: dict[tuple[Any, str], dict] = {}

    def note(reason: str, index: int, event: dict) -> None:
        incomplete.append({"reason": reason, "index": index, "run_id": event.get("run_id"),
                           "tool_call_id": event.get("tool_call_id"),
                           "tool_name": event.get("tool_name") or None})

    def open_call(index: int, event: dict) -> dict:
        ended = str(event.get("tool_status") or "").lower() not in OPEN_STATUSES
        call = {"name": _facts(event)[0], "start": event, "start_index": index,
                "end": event if ended else None, "end_index": index if ended else None,
                "indices": [index], "conflict": False}
        calls.append(call)
        return call

    for index, event in enumerate(events):
        if event.get("type") != "tool":
            continue
        named = bool(event.get("tool_name"))
        is_open = str(event.get("tool_status") or "").lower() in OPEN_STATUSES
        call_id = event.get("tool_call_id")
        if not call_id:
            if named:
                open_call(index, event)
            else:
                note("result_without_call", index, event)
            continue
        key = (event.get("run_id"), str(call_id))
        call = by_key.get(key)
        if call is None:
            if named:
                by_key[key] = open_call(index, event)
            else:
                note("result_without_call", index, event)
            continue
        call["indices"].append(index)
        if is_open:
            if not named or _facts(event) == _facts(call["start"]):
                continue                                 # 同一开始重复上报
            if (call["end"] is None and _facts(event)[0] == call["name"]
                    and not call["start"].get("tool_input")):
                call["start"] = event                    # 先报名字、后补入参的宿主
                continue
        elif call["end"] is None:
            call["end"], call["end_index"] = event, index
            continue
        elif _outcome(event) == _outcome(call["end"]):
            continue                                     # 同一结果重复上报
        call["conflict"] = True
        note("conflicting_events", index, event)
    for call in calls:
        call["shortened"] = any(events[i].get("source_truncated") is True for i in call["indices"])
        if (call["shortened"] or call["end"] is None) and not call["conflict"]:
            _complete_from_native(call, native or {})
        call["kind"] = _call_kind(call)
        if call["end"] is None:
            note("no_result", call["start_index"], call["start"])
        if call["shortened"]:
            note("source_truncated", call["start_index"], call["start"])
    incomplete.sort(key=lambda item: item["index"])
    return calls, incomplete


def _complete_from_native(call: dict, native: dict[str, list[dict]]) -> None:
    """同一调用在原生会话里有完整记录时，补齐公共事件截断或缺失的那一侧。

    认同一调用：callId 相同、只在一个原生会话里出现、工具名一致。入参被截断取原生完整入参；结果缺失或被截断取原生结果，
    原生对这次调用只有一份结果才取（内容不同的多份是冲突，不挑）。补齐的一侧记 `completed_from: native`；
    另一侧仍截断时调用照旧是截断，结论照旧判不了。
    """
    found = native.get(str(call["start"].get("tool_call_id") or ""), [])
    if len(found) != 1 or str(found[0].get("name") or "").lower() != call["name"]:
        return
    same = found[0]
    filled = []
    if call["start"].get("source_truncated") is True:
        try:
            args = json.loads(same.get("args") or "")
        except (TypeError, ValueError):
            args = None
        if isinstance(args, dict):
            call["start"] = {**call["start"], "tool_input": args, "source_truncated": False}
            filled.append("input")
    end = call["end"]
    results = same.get("results") or []
    if (end is None or end.get("source_truncated") is True) and len(results) == 1 and results[0].get("text") is not None:
        status = "error" if results[0].get("isError") else "completed"
        base = end or {"type": "tool", "run_id": call["start"].get("run_id"), "tool_call_id": call["start"].get("tool_call_id"),
                       "timestamp": None}
        call["end"] = {**base, "tool_status": status, "tool_output": results[0]["text"], "source_truncated": False}
        filled.append("result")
    if filled:
        call["completed_from"] = {"native": filled}
        call["shortened"] = any(e is not None and e.get("source_truncated") is True for e in (call["start"], call["end"]))


def _is_verifier(call: dict) -> bool:
    if call["name"] == "verifier":
        return True
    subagent = str((call["start"].get("tool_input") or {}).get("subagent_type") or "").lower()
    return call["name"] == "task" and subagent == "verifier"


def _call_kind(call: dict) -> str:
    """调用在做什么：harness / story_register / verifier / delegation / authoring / other。"""
    name, request = call["name"], _request_text(call["start"])
    if name in SHELL_TOOLS and HARNESS_CMD_RE.search(request):
        return "harness"
    if name in SHELL_TOOLS and STORY_REGISTER_RE.search(request):
        return "story_register"
    if name in SHELL_TOOLS and REVIEW_CHECK_RE.search(request):
        return "review_check"
    if name in SHELL_TOOLS and DELIVER_RE.search(request):
        return "deliver"
    if name in SHELL_TOOLS and STORY_CHECK_RE.search(request):
        return "story_check"
    if _is_verifier(call):
        return "verifier"
    if name in DELEGATION_TOOLS:
        return "delegation"
    return "authoring" if name in AUTHORING_TOOLS else "other"


def _result(call: dict) -> str | None:
    """调用的输出；没有结果、同键冲突或宿主输出把它截断了时为 None，门禁结论不从它推
    （截断的输出里没看到 FAIL 不等于通过）。"""
    if call["end"] is None or call["conflict"] or call["shortened"]:
        return None
    return _output_text(call["end"])


def split_at_checkpoint(events: list[dict], run_dir: Path | None) -> int | None:
    """第一段与第二段的分界 —— **按续跑那一刻切，不按时间猜**。

    分界取 worker 在续跑时写进 `state.json` 的 `resumed_at`：它是带日期与时区的完整时刻。
    **不读 `live.jsonl` 的 `ts`**：那一列只有时分秒、没有日期，两段一旦跨过午夜
    （第一段晚上跑完、第二段第二天早上才续上）就比不出先后——实跑里就是这样。
    也不按序号切：装置的 live 与模型的 events 各有各的序号，拿一条的切另一条是巧合。

    没有 `resumed_at` 就是普通单终点，返回 None。
    """
    if run_dir is None:
        return None
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    mark = _ts(state.get("resumed_at"))
    if mark is None:
        return None
    for i, e in enumerate(events):
        ts = _ts(e.get("timestamp"))
        # 两边都带时区才比；混着裸时刻比会抛错，也会比错
        if ts and ts.tzinfo and ts >= mark:
            return i
    return len(events)


def _gate_failed(call: dict, output: str) -> bool:
    """一次有结果的门禁调用没过：harness 输出里有 FAIL 行，审查结论是 fail / report_invalid，登记、成文检查或交付门输出报未通过，
    或命令本身以错误状态结束。"""
    if call["kind"] == "harness":
        fails = any(m.group(1) == "FAIL" for m in CHECK_LINE_RE.finditer(output))
    elif call["kind"] == "review_check":
        fails = any(m.group(1) in {"fail", "report_invalid"} for m in REVIEW_RESULT_RE.finditer(output))
    else:
        fails = bool(REGISTER_FAIL_RE.search(output))
    return fails or str(call["end"].get("tool_status") or "") not in SUCCESS_STATUSES


#: 取知识任务的命令（story-knowledge 的入口）
KNOWLEDGE_TASK_RE = re.compile(r"knowledge-task\.mjs")
#: 第 4 块每份送到的正文：位置行与「下面是」行（knowledge-task.mjs::knowledgeBlock）
BODY_AT_RE = re.compile(r"^- 位置：`([^`]+)`", re.MULTILINE)
BODY_PART_RE = re.compile(r"^- 下面是：(全文|前言与(上篇|下篇))", re.MULTILINE)


def _flag(request: str, name: str) -> str | None:
    """命令里 `--name value` 或 `--name=value` 的值：不加引号、单引号、双引号三种写法都认，去掉外层引号、保留引号里的空格；
    没出现、空值或引号没闭合时是 None（判不了），不猜默认值，也不执行或展开命令。"""
    m = re.search(rf"--{name}(?:=|\s+)(?:'([^']*)'|\"([^\"]*)\"|([^\s'\"]+))", request)
    value = next((g for g in m.groups() if g is not None), None) if m else None
    return value or None


def knowledge_deliveries(calls: list[dict]) -> list[dict]:
    """每次取知识任务送到了什么：对象、动作、读者，输出的 UTF-8 字节，送到正文的文件与篇（全文 / 上篇 / 下篇）。
    输出没取到、冲突或被截断时字节与正文都是 None（不是 0）；字节少不等于 token 或耗时少，也不说明用对了知识。"""
    rows = []
    for call in calls:
        request = _request_text(call["start"])
        if call["name"] not in SHELL_TOOLS or not KNOWLEDGE_TASK_RE.search(request):
            continue
        output = _result(call)
        bodies = None
        if output is not None:
            at = BODY_AT_RE.findall(output)
            parts = [m.group(2) or "全文" for m in BODY_PART_RE.finditer(output)]
            bodies = [{"file": f, "part": part} for f, part in zip(at, parts)] if len(at) == len(parts) else None
        rows.append({"target": _flag(request, "feature") or _flag(request, "blueprint"), "action": _flag(request, "action"),
                     "audience": _flag(request, "audience"), "bytes": len(output.encode("utf-8")) if output is not None else None,
                     "bodies": bodies})
    return rows


def _owners(calls: list[dict]) -> dict[int, dict]:
    """事件位置 → 它所属的调用；事件间隔按调用的用途归属。"""
    return {index: call for call in calls for index in call["indices"]}


def _union_seconds(intervals: list[tuple[datetime, datetime]]) -> float | None:
    """若干时间区间的**并集**秒数；一个可核区间都没有时是 None（未知，不是 0）。

    并发调用的区间相互交叠：相加会把一段时间算两次，逐个相减也会把交叠部分重复扣两次。
    这里先并集再量长度，跨来源（工具、子任务、返修）同样适用。
    """
    def _norm(dt: datetime) -> datetime:
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    spans = sorted(
        (_norm(start), _norm(end))
        for start, end in intervals
        if start is not None and end is not None and _norm(end) >= _norm(start)
    )
    if not spans:
        return None
    total = 0.0
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start > cur_end:
            total += (cur_end - cur_start).total_seconds()
            cur_start, cur_end = start, end
        elif end > cur_end:
            cur_end = end
    total += (cur_end - cur_start).total_seconds()
    return round(total, 1)


def segment_metrics(events: list[dict], calls: list[dict], lo: int, hi: int) -> dict:
    """一段（``events[lo:hi]``）的效率观测：时长、模型与工具时间、verifier 次数与耗时、首次门禁与首次登记、返工时长。

    调用先在整份输入里归并，再按**开始**所在的段归属，跨段的调用不拆成两次。
    非工具事件间隔与工具事件间隔都是**相邻事件间隔的近似值**（间隔归给本条事件），不是实测 span，
    也不称纯推理：非工具间隔里混着模型推理、宿主准备、等待与事件空档。
    首次门禁、登记与返工只看有结果的调用，按结果到达的先后算；返工时长是一次门禁或登记没过到下一次同类通过之间的分钟数，
    多类同时未过时按**并集**算，交叠窗口不重复计。等人时间由驱动器累计，只有全程数。
    """
    owners = _owners(calls)
    stamps = [t for t in (_ts(e.get("timestamp")) for e in events[lo:hi]) if t]
    nontool_gap = tool_gap = verifier_gap = 0.0
    prev = None
    for index in range(lo, hi):
        e = events[index]
        ts = _ts(e.get("timestamp"))
        gap = (ts - prev).total_seconds() if (ts and prev) else 0.0
        prev = ts or prev
        if e.get("type") != "tool":
            nontool_gap += gap
            continue
        tool_gap += gap
        if index in owners and owners[index]["kind"] == "verifier":
            verifier_gap += gap
    mine = [call for call in calls if lo <= call["start_index"] < hi]
    intervals = [(_ts(call["start"].get("timestamp")), _ts((call["end"] or {}).get("timestamp")))
                 for call in mine if call["end"] is not None]
    first = {"harness": None, "story_register": None}
    failing_since: dict[str, datetime] = {}
    rework_intervals: list[tuple[datetime, datetime]] = []
    comparable = False  # 有没有可判的门禁/登记结果：没有时返修是未知，不是「没返修」
    for call in sorted(mine, key=lambda c: c["end_index"] if c["end_index"] is not None else c["start_index"]):
        kind, output = call["kind"], _result(call)
        if kind not in first or output is None:
            continue
        comparable = True
        ts = _ts(call["end"].get("timestamp"))
        status = str(call["end"].get("tool_status") or "")
        fails = (len({m.group(3) for m in CHECK_LINE_RE.finditer(output) if m.group(1) == "FAIL"})
                 if kind == "harness" else len(REGISTER_FAIL_RE.findall(output)))
        if first[kind] is None:
            first[kind] = {"fail_count": fails, "status": status}
        # 命令本身报错（error / failed / cancelled）也是没过，不因输出里没有 FAIL 行就当通过
        passed = not fails and status in SUCCESS_STATUSES
        if not passed and kind not in failing_since and ts:
            failing_since[kind] = ts
        elif passed and kind in failing_since and ts:
            rework_intervals.append((failing_since.pop(kind), ts))
    rework = _union_seconds(rework_intervals)
    if rework is None and comparable:
        rework = 0.0  # 有可判结果、没有未过→通过的窗口：这才是「没返修」
    return {
        "duration_min": round((stamps[-1] - stamps[0]).total_seconds() / 60, 1) if len(stamps) > 1 else None,
        "nontool_gap_sec": round(nontool_gap, 1),
        "tool_gap_sec": round(tool_gap, 1),
        "tool_interval_sec": _union_seconds(intervals),
        "verifier_runs": sum(call["kind"] == "verifier" for call in mine),
        "verifier_gap_sec": round(verifier_gap, 1),
        "delegations_unresolved": sum(call["kind"] == "delegation" for call in mine),
        "first_harness": first["harness"],
        "first_story_register": first["story_register"],
        "rework_min": round(rework / 60, 1) if rework is not None else None,
    }


def measure(events_path: Path, *, run_dir: Path | None = None) -> dict:
    events = list(_iter_events(events_path))
    if not events:
        raise SystemExit(f"[measure_run] {events_path} 里没有可解析的事件——不是「指标为零」，是读不到数据")

    sessions = _native_sessions(run_dir or events_path.parent)
    native: dict[str, list[dict]] = {}
    for _parent, info in sessions["read"]:
        for one in info.get("calls") or []:
            native.setdefault(str(one.get("callId")), []).append(one)
    calls, incomplete = tool_call_view(events, native)
    owners = _owners(calls)
    reads_rule = 0            # 读框架/扩展的规则文本
    reads_own = 0             # 读自己的产物
    reads_checker = 0         # 读 checker 源码
    bash_unclassified = 0     # 提到规则路径、却既不是读也不是跑门禁的 shell 调用（执行脚本等）
    tools = Counter(call["name"] for call in calls)
    context_first = context_last = None
    harness_runs = 0
    gate_rounds_with_fail = 0
    #: 按种类的门禁结论：同一调用一次，结果读不出（没结果、冲突、截断）记 unknown
    gate_fail_by_kind = {"harness": 0, "story_register": 0, "story_check": 0, "review_check": 0, "deliver": 0}
    gate_unknown_by_kind = dict.fromkeys(gate_fail_by_kind, 0)
    review_results: Counter[str] = Counter()
    check_fail_counts: Counter[str] = Counter()
    # 分段耗时：「上一条事件到本条事件的间隔」按本条所属调用的用途归属，是**近似**，
    # 字段名带 _gap_sec 明说这一点——不把近似值包装成实测值。
    gap_by_kind: dict[str, float] = {"gate": 0.0, "verifier": 0.0, "authoring": 0.0, "other": 0.0}
    gap_bucket = {"harness": "gate", "verifier": "verifier", "authoring": "authoring"}
    prev_ts = None
    conservation: tuple[int, int] | None = None
    first_ts = last_ts = None
    # 模型动的第一下——装置起跑当场就写事件，用它算空档量到的是装置自己
    first_model_ts = None

    for index, e in enumerate(events):
        ts = _ts(e.get("timestamp"))
        if ts:
            first_ts = first_ts or ts
            last_ts = ts

        etype = e.get("type")
        if ts and first_model_ts is None and etype in {"tool", "usage"}:
            first_model_ts = ts
        gap = (ts - prev_ts).total_seconds() if (ts and prev_ts) else 0.0
        if ts:
            prev_ts = ts
        if etype == "usage":
            total = (e.get("usage") or {}).get("context_total")
            if isinstance(total, int):
                if context_first is None:
                    context_first = total
                context_last = total
        elif etype == "tool":
            kind = owners[index]["kind"] if index in owners else "other"
            gap_by_kind[gap_bucket.get(kind, "other")] += gap

    for call in calls:
        name, request = call["name"], _request_text(call["start"])
        if name in {"read", "grep", "glob"}:
            segments = [request]
        elif name in SHELL_TOOLS:
            segments = _read_segments(request)
        else:
            segments = []
        read_text = " ".join(segments)
        if read_text:
            # 一次工具调用计一次：命令里哪一段读了机制源码都算
            source = SOURCE_FILE_RE if name == "glob" else CHECKER_PATH_RE
            reads_checker += any(source.search(seg) for seg in segments)
            if RULE_PATH_RE.search(read_text):
                reads_rule += 1
            elif "doc/features/" in read_text:
                reads_own += 1
        is_harness = call["kind"] == "harness"
        if (name in SHELL_TOOLS and not is_harness and RULE_PATH_RE.search(request)
                and not RULE_PATH_RE.search(read_text)):
            bash_unclassified += 1
        harness_runs += is_harness

    for call in sorted(calls, key=lambda c: c["end_index"] if c["end_index"] is not None else c["start_index"]):
        output = _result(call)
        if call["kind"] in gate_fail_by_kind:
            if output is None:
                gate_unknown_by_kind[call["kind"]] += 1
            elif _gate_failed(call, output):
                gate_fail_by_kind[call["kind"]] += 1
        if output is None:
            continue
        if call["kind"] == "review_check":
            review_results.update({m.group(1) for m in REVIEW_RESULT_RE.finditer(output)})
        # 门禁报出的 check id 只在**门禁调用的输出**里。按「这一次调用」去重后再计数：
        # 同一份报告在 console 打一次、被 cat 再打一次，按文本次数算就会翻倍，
        # 而判据问的是「同一个 id 在多少**轮**门禁里失败」。
        if call["kind"] == "harness":
            failed_ids = {m.group(3) for m in CHECK_LINE_RE.finditer(output) if m.group(1) == "FAIL"}
            for cid in failed_ids:
                check_fail_counts[cid] += 1
            if failed_ids:
                gate_rounds_with_fail += 1
        # story 守恒的两层各担多少条——取最后一次通过时的数（也在输出面）
        hit = CONSERVATION_RE.search(output)
        if hit:
            conservation = (int(hit.group(1)), int(hit.group(2)))

    duration_min = None
    wall_sec = None
    if first_ts and last_ts:
        wall_sec = round((last_ts - first_ts).total_seconds(), 1)
        duration_min = round((last_ts - first_ts).total_seconds() / 60, 1)

    # 父/子的 assistant 响应与工具调用分列：两套口径不同（父来自公共事件流，子来自保全的原生会话），
    # 不能相加成一次模型 API 次数，也不能用 children/ 的目录数冒充任务数。
    parent_counts = {"assistant_responses": sum(1 for e in events if e.get("type") == "text"),
                     "tool_calls": len(calls)}
    child_reads = _child_sessions(sessions)
    child_counts = _child_totals(child_reads)
    delegations = native_delegations(sessions, child_reads)

    # 耗时只报能核实的那几类；区间取并集，交叠部分不重复累加，也不重复扣除。
    tool_intervals = [(_ts(call["start"].get("timestamp")), _ts((call["end"] or {}).get("timestamp")))
                      for call in calls if call["end"] is not None]
    delegation_intervals = []
    for start_ms, end_ms in (delegations.get("delegations") or {}).get("observed_intervals") or []:
        try:
            delegation_intervals.append((datetime.fromtimestamp(float(start_ms) / 1000, tz=timezone.utc),
                                         datetime.fromtimestamp(float(end_ms) / 1000, tz=timezone.utc)))
        except (TypeError, ValueError, OSError):
            continue
    tool_interval_sec = _union_seconds(tool_intervals)
    delegation_interval_sec = _union_seconds(delegation_intervals)
    verifiable = tool_interval_sec or 0.0
    if delegation_interval_sec is not None:
        # 工具与子任务可能并行：加到同一并集里再量，避免「两者都扣一次」。
        verifiable = _union_seconds([*tool_intervals, *delegation_intervals]) or 0.0
    # 子任务收尾可能晚于父会话最后一条事件：可核区间超出墙钟时按 0 计，不扣成负数。
    not_attributed = (max(0.0, round(wall_sec - verifiable, 1)) if wall_sec is not None else None)

    # 双检查点单：两段各自多少事件、各自多长。混在一起算的话，第二段那几分钟的增量
    # 会被摊进第一段的总量，「这次更新花了多少」就再也分不出来。
    cut = split_at_checkpoint(events, run_dir)
    if cut is None:
        segments = {"whole": {"events": len(events), **segment_metrics(events, calls, 0, len(events))}}
    else:
        segments = {"initial": {"events": cut, **segment_metrics(events, calls, 0, cut)},
                    "update": {"events": len(events) - cut, **segment_metrics(events, calls, cut, len(events))}}
        for call in calls:
            if call["start_index"] < cut <= max(call["indices"]):
                incomplete.append({"reason": "crosses_checkpoint", "index": call["start_index"],
                                   "run_id": call["start"].get("run_id"),
                                   "tool_call_id": call["start"].get("tool_call_id"),
                                   "tool_name": call["name"] or None})
        incomplete.sort(key=lambda item: item["index"])

    isolation = scan_isolation_boundary(events, calls, run_dir or events_path.parent, sessions, cut)
    story_regs = []
    for call in sorted(calls, key=lambda c: c["end_index"] if c["end_index"] is not None else c["start_index"]):
        if call["kind"] != "story_register":
            continue
        out = _result(call)
        status = str((call["end"] or {}).get("tool_status") or "")
        ok = (out is not None) and (not _gate_failed(call, out))
        story_regs.append({
            "line": call["start_index"] + 1,
            "end_line": (call["end_index"] + 1) if call["end_index"] is not None else None,
            "timestamp": (call["end"] or call["start"]).get("timestamp"),
            "status": "completed" if ok else ("unknown" if out is None else "failed"),
        })

    return {
        "events": len(events),
        "duration_min": duration_min,
        "segments": segments,
        "tool_calls": len(calls),
        "tools": tools.most_common(8),
        "incomplete_tool_events": incomplete,
        "reads_rule_text": reads_rule,
        "reads_own_artifacts": reads_own,
        "reads_checker_source": reads_checker,
        "read_algorithm": READ_ALGORITHM,
        "bash_rule_path_not_read": bash_unclassified,
        "rule_over_own_ratio": (round(reads_rule / reads_own, 2) if reads_own else None),
        "harness_runs": harness_runs,
        "context_first": context_first,
        "context_last": context_last,
        "context_growth": (context_last - context_first
                           if context_first is not None and context_last is not None else None),
        "gate_rounds_with_fail": gate_rounds_with_fail,
        "gate_fail_by_kind": gate_fail_by_kind,
        "gate_unknown_by_kind": gate_unknown_by_kind,
        "review_results": dict(review_results),
        "story_registration_times": story_regs,
        "isolation_boundary": isolation,
        "tool_calls_completed_from_native": sum("completed_from" in call for call in calls),
        "parent_counts": parent_counts,
        "child_counts": child_counts,
        "wall_clock_sec": wall_sec,
        "tool_interval_sec": tool_interval_sec,
        "delegation_interval_sec": delegation_interval_sec,
        "not_attributed_sec": not_attributed,
        "duration_source": "first_to_last_event",
        "usage_source": "parent_session_context_readings_only",
        "gap_semantics": "adjacent_event_interval_estimate_not_pure_reasoning",
        **delegations,
        "knowledge_deliveries": knowledge_deliveries(calls),
        "repeated_check_fails": check_fail_counts.most_common(5),
        "worst_repeated_check": (check_fail_counts.most_common(1)[0] if check_fail_counts else None),
        "gap_sec_by_kind": {k: round(v, 1) for k, v in gap_by_kind.items()},
        "conservation_machine": conservation[0] if conservation else None,
        "conservation_model": conservation[1] if conservation else None,
        **_diagrams(run_dir or events_path.parent),
        **_human_wait(run_dir or events_path.parent),
        **_startup_gap(run_dir or events_path.parent, first_model_ts),
    }


DSH_SESSION_READER = Path(__file__).resolve().parent / "dsh_session.mjs"
#: 产品生成的派审载体与审查任务：派出去的正文按它认审查类委派
CARRIER_ROLES = ((re.compile(r"^# Story 独立人读审查 · 派审"), "story_review"),
                 (re.compile(r"^# 蓝图独立质询 · 派审"), "questioning"),
                 (re.compile(r"的增强阅读 SVG"), "figure_review"))
#: Story 派审载体写明这一次是哪种派审（independent-review.mjs 的三种载体）：先首读、复核、补正上一份回复
REVIEW_MODES = (("## 先首读", "first_read"), ("## 复核", "recheck"), ("## 补正上一份回复", "correction"))
#: 原生阶段审查请求（harness 签发的 request JSON）
STAGE_REQUEST_RE = re.compile(r'\\?"kind\\?"\s*:\s*\\?"maison_verifier_request\\?"')
DELEGATING_TOOLS = {"subagent", "subagent_fork", "task"}
STARTED_RE = re.compile(r"started subagent (\S+)")
BLUEPRINT_FILE_RE = re.compile(r"[\\/]blueprint[\\/]")


def _native(path: Path) -> dict:
    """读一份 dsh 原生会话（`dsh_session.mjs`）；起不来或解不开返回 {error}。"""
    import subprocess  # noqa: PLC0415
    proc = subprocess.run(["node", str(DSH_SESSION_READER), str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": (proc.stderr or proc.stdout or "没有输出").strip()[:300]}


def _args(call: dict) -> dict:
    try:
        value = json.loads(call.get("args") or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _child_role(child: dict) -> str | None:
    """子会话实际产出了什么：写了需求 `blueprint/` 下的设计产物（canonical 或契约转写）的是蓝图作者；其余不在这里定。"""
    for call in child.get("calls") or []:
        if call.get("name") in AUTHORING_TOOLS and BLUEPRINT_FILE_RE.search(str(_args(call).get("file_path") or "")):
            return "blueprint_author"
    return None


def _native_sessions(run_dir: Path) -> dict:
    """本 run 保全的原生父会话：{present, read: [(文件, 读数)], problems}。没有保全原件时 present 为假。"""
    root = run_dir / "native-sessions"
    parents = sorted(root.glob("*/session.v4.jsonl.zstd")) if root.is_dir() else []
    read, problems = [], []
    for parent in parents:
        info = _native(parent)
        if info.get("error"):
            problems.append(f"{parent.parent.name}：{info['error']}")
        else:
            read.append((parent, info))
    return {"present": bool(parents), "read": read, "problems": problems}


def _child_sessions(sessions: dict) -> dict[Path, dict]:
    """保全的**子会话**逐份读数（按文件缓存一份）：父会话登记在它自己的 `children/<childId>/` 下。

    只数实际保全且能解出的子会话；解不开的留给 delegations.problems，不按目录在不在推任务数。
    """
    children: dict[Path, dict] = {}
    for parent, _info in sessions["read"]:
        base = parent.parent / "children"
        if not base.is_dir():
            continue
        for child in sorted(base.glob("*/session.v4.jsonl.zstd")):
            children[child] = _native(child)
    return children


def _child_totals(children: dict[Path, dict]) -> dict:
    """子会话侧可数的两件事：assistant 响应与工具调用；与父会话口径不同，不能相加成 API 次数。"""
    if not children:
        return {"sessions": None, "assistant_responses": None, "tool_calls": None, "problems": None}
    responses = calls = 0
    problems, readable = [], 0
    for path, info in children.items():
        if info.get("error"):
            problems.append(f"{path.parent.name}：{info['error']}")
            continue
        readable += 1
        responses += int(info.get("assistant_responses") or 0)
        calls += int(info.get("tool_calls") or 0)
    return {"sessions": readable, "assistant_responses": responses, "tool_calls": calls,
            "problems": problems or None}


def _review_mode(prompt: str) -> str:
    """Story 派审载体写明的派审种类；载体里没有这几节（旧版本的运行记录）是 unknown，不按次序猜。"""
    return next((mode for head, mode in REVIEW_MODES if re.search(rf"^{re.escape(head)}$", prompt, re.MULTILINE)), "unknown")


#: 宿主收尾通知 summary 里的子代理名：`Background subagent <name> finished ...`
SETTLED_AGENT_RE = re.compile(r"Background subagent (\S+)\s+(?:finished|failed|stopped|completed)")
#: 隔离扫描：识别 shell 里的目录切换与读取/列举动词、动态宿主会话库访问、相对跳出路径和绝对路径
CD_CMD_RE = re.compile(r"^(?:cd|set-location|sl|push-location|pushd)\s+(?:-path\s+)?[\"']?([^\"';|&\n]+)[\"']?", re.IGNORECASE)
ACCESS_VERB_RE = re.compile(
    r"(?:(?:^|\s)(?:cat|head|tail|sed|less|more|type|grep|rg|awk|findstr|get-content|gc|select-string|sls|"
    r"ls|dir|get-childitem|gci|find|tree|resolve-path|test-path|stat)\b|"
    r"(?:^|[\s.(])(?:readfile|readfilesync|readdirsync|statsync|open\(|glob\.glob|os\.listdir|os\.walk|pathlib\.path|zstandard|zstd))",
    re.IGNORECASE)
HOST_SESSION_STORE_RE = re.compile(
    r"(?:(?:userprofile|home|appdata)[^\n]{0,80}\.dsh|\.dsh[/\\](?:sessions|store)|"
    r"dsh[/\\]store|session\.v4\.jsonl\.zstd)",
    re.IGNORECASE)
REL_ESCAPE_RE = re.compile(r"(?<![A-Za-z0-9_.:/-])(\.\.(?:[/\\][^\s\"'`;|&)>]+)+|\.\.(?=[/\\]?(?:\s|$|[\"'`;|&)>])))")
ABS_WIN_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z]:[/\\][^\s\"'`;|&)>]+)")
#: 宿主环境里合法的工具自身路径或公共二进制目录，不算访问旁案/主仓
_BENIGN_ABS_PREFIXES = (
    "c:/windows/", "c:/program files/", "c:/program files (x86)/",
    "e:/tools/", "/usr/", "/bin/", "/opt/",
)
#: 输出失败或空提示，用来辅助判断是实际拿到外部内容还是仅尝试失败
_ACCESS_FAILED_RE = re.compile(r"(?:cannot find path|no such file|does not exist|access is denied|filenotfounderror|enoent)", re.IGNORECASE)


def _norm_abs_posix(raw: str) -> str:
    """将 Windows/POSIX 绝对路径归一为正斜杠并消除 `.`/`..`。"""
    text = str(raw or "").strip().strip("\"'").replace("\\", "/")
    if not text:
        return ""
    drive = ""
    if re.match(r"^[A-Za-z]:", text):
        drive = text[:2].lower()
        rest = text[2:]
    elif text.startswith("/"):
        rest = text
    else:
        return ""
    parts: list[str] = []
    for seg in rest.split("/"):
        if not seg or seg == ".":
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return f"{drive}/" + "/".join(parts)


def _resolve_from_cwd(cwd_posix: str, rel: str) -> str:
    clean = str(rel or "").strip().strip("\"'").replace("\\", "/")
    if not clean:
        return cwd_posix
    if re.match(r"^[A-Za-z]:/", clean) or clean.startswith("/"):
        return _norm_abs_posix(clean)
    if not cwd_posix:
        return ""
    return _norm_abs_posix(f"{cwd_posix.rstrip('/')}/{clean}")


def _inside_root(target: str, root: str) -> bool:
    if not target or not root:
        return False
    t, r = target.rstrip("/").lower(), root.rstrip("/").lower()
    return t == r or t.startswith(r + "/")


def _workspace_root_for_run(run_dir: Path | None, sessions: dict) -> str | None:
    """从保全的父会话 header.cwd、state.json 或 suite.json 取得本 Case 隔离工作区根。"""
    for _parent, info in sessions.get("read") or []:
        cwd = (info.get("header") or {}).get("cwd")
        if cwd:
            norm = _norm_abs_posix(str(cwd))
            if norm:
                return norm
    if run_dir is not None:
        state_file = run_dir / "state.json"
        if state_file.is_file():
            try:
                ws = json.loads(state_file.read_text(encoding="utf-8")).get("workspace")
                if ws:
                    norm = _norm_abs_posix(str(ws))
                    if norm:
                        return norm
            except (OSError, json.JSONDecodeError):
                pass
        # run_dir = <suite>/cases/<case>/<run>
        suite_file = run_dir.parents[2] / "suite.json" if len(run_dir.parents) >= 3 else None
        if suite_file and suite_file.is_file():
            try:
                suite = json.loads(suite_file.read_text(encoding="utf-8"))
                case_name = run_dir.parent.name
                ws = ((suite.get("case_states") or {}).get(case_name) or {}).get("workspace")
                if ws:
                    norm = _norm_abs_posix(str(ws))
                    if norm:
                        return norm
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _allowed_external_roots(run_dir: Path | None, ws_root: str | None) -> list[str]:
    """本 Case 合法外部路径：本 Case 自己的需求系统副本目录（sw-sys）。"""
    allowed: list[str] = []
    if run_dir is not None and len(run_dir.parents) >= 3:
        suite_file = run_dir.parents[2] / "suite.json"
        if suite_file.is_file():
            try:
                suite = json.loads(suite_file.read_text(encoding="utf-8"))
                case_name = run_dir.parent.name
                rec = (suite.get("case_states") or {}).get(case_name) or {}
                for k in ("requirement_system_dir", "system_dir"):
                    if rec.get(k):
                        norm = _norm_abs_posix(str(rec[k]))
                        if norm:
                            allowed.append(norm)
            except (OSError, json.JSONDecodeError):
                pass
    if ws_root and "/sw-story/" in ws_root.lower():
        # 允许指向同 temp 根下的 sw-sys 需求系统目录（仅环境变量替身访问，不放行兄弟 case）
        temp_parent = ws_root[:ws_root.lower().index("/sw-story/")]
        allowed.append(f"{temp_parent}/sw-sys")
    return allowed


def _segment_of(index: int, cut: int | None) -> str:
    if cut is None:
        return "whole"
    return "initial" if index < cut else "update"


def scan_isolation_boundary(events: list[dict], calls: list[dict], run_dir: Path | None,
                            sessions: dict, cut: int | None) -> dict:
    """只读扫描隔离工作区越界：结合事件 cwd 解析相对路径、识别动态拼接/宿主会话库访问与绝对路径越界，
    并区分实际读取/列举与仅出现路径文字；保留原事件行号与影响段，不修改原事件。"""
    ws_root = _workspace_root_for_run(run_dir, sessions)
    allowed_ext = _allowed_external_roots(run_dir, ws_root)
    findings: list[dict] = []
    mentions_only: list[dict] = []
    seen: set[tuple[int, str, str]] = set()

    def is_allowed(target: str) -> bool:
        if not target:
            return True
        if ws_root and _inside_root(target, ws_root):
            return True
        if any(_inside_root(target, root) for root in allowed_ext):
            return True
        low = target.lower()
        return any(low.startswith(prefix) for prefix in _BENIGN_ABS_PREFIXES)

    def record(call: dict, kind: str, target: str, access: str, evidence: str) -> None:
        line = call["start_index"] + 1
        key = (line, kind, target.lower())
        if key in seen:
            return
        seen.add(key)
        item = {
            "line": line,
            "segment": _segment_of(call["start_index"], cut),
            "tool": call["name"],
            "kind": kind,
            "access": access,
            "resolved_path": target,
            "evidence": evidence[:240],
            "truncated_needs_host_check": bool(call["shortened"]),
        }
        if access == "text_mention_only":
            mentions_only.append(item)
        else:
            findings.append(item)

    def output_confirms_access(call: dict) -> str:
        out = _output_text(call["end"]) if call["end"] is not None else ""
        status = str((call["end"] or {}).get("tool_status") or "").lower()
        if call["shortened"]:
            return "confirmed_access" if out.strip() and not _ACCESS_FAILED_RE.search(out) else "attempted_access"
        if status == "error" or _ACCESS_FAILED_RE.search(out):
            return "attempted_access"
        return "confirmed_access" if out.strip() else "attempted_access"

    for call in calls:
        name = call["name"]
        ti = call["start"].get("tool_input") or {}
        if name in {"read", "grep", "glob", "list", "ls", "view", "view_file"}:
            paths = [str(ti.get(k)) for k in ("file_path", "filePath", "path", "directory") if ti.get(k)]
            for raw in paths:
                norm = _resolve_from_cwd(ws_root or "", raw) if ws_root else _norm_abs_posix(raw)
                if norm and not is_allowed(norm):
                    kind = "relative_escape" if not _is_absolute_path(_writer_path(raw)) else "absolute_escape"
                    record(call, kind, norm, output_confirms_access(call), raw)
        elif name in SHELL_TOOLS:
            cmd = str(ti.get("command") or "")
            if not cmd:
                continue
            has_access_verb = bool(ACCESS_VERB_RE.search(cmd))
            # 1. 动态拼接 / 宿主私有会话库访问（如 $env:USERPROFILE\.dsh\sessions、.zstd）
            if HOST_SESSION_STORE_RE.search(cmd):
                access = output_confirms_access(call) if has_access_verb else "text_mention_only"
                record(call, "host_session_store_access", "<host-dsh-session-store>", access, cmd)
            # 2. 按段追踪 cd 后的 cwd，逐段解析相对路径与绝对路径
            cur_cwd = ws_root or ""
            for seg in _split_segments(cmd):
                s = seg.strip()
                if not s:
                    continue
                if "-command" in s.lower():
                    s = POWERSHELL_WRAPPER_RE.sub("", s, count=1).strip().strip("\"'").strip()
                cd_m = CD_CMD_RE.match(s)
                if cd_m and cur_cwd:
                    cur_cwd = _resolve_from_cwd(cur_cwd, cd_m.group(1))
                    if cur_cwd and not is_allowed(cur_cwd):
                        record(call, "relative_escape", cur_cwd, output_confirms_access(call), s)
                    continue
                seg_has_read = has_access_verb or bool(ACCESS_VERB_RE.search(s))
                # 检查相对跳出路径（..）
                if cur_cwd:
                    for rel_m in REL_ESCAPE_RE.finditer(s):
                        raw_rel = rel_m.group(1).rstrip(".,;:")
                        resolved = _resolve_from_cwd(cur_cwd, raw_rel)
                        if resolved and not is_allowed(resolved):
                            # 仅 echo / Write-Output / 注释文本且没有读/列举动作 → 标 text_mention_only
                            is_print_only = bool(re.match(r"^(?:echo|write-output|write-host|printf|#)\b", s, re.IGNORECASE))
                            access = "text_mention_only" if (is_print_only and not seg_has_read) else (
                                output_confirms_access(call) if seg_has_read else "text_mention_only")
                            record(call, "relative_escape", resolved, access, s)
                # 检查绝对路径
                for abs_m in ABS_WIN_PATH_RE.finditer(s):
                    raw_abs = abs_m.group(1).rstrip(".,;:'\"")
                    resolved = _norm_abs_posix(raw_abs)
                    if resolved and not is_allowed(resolved):
                        is_print_only = bool(re.match(r"^(?:echo|write-output|write-host|printf|#)\b", s, re.IGNORECASE))
                        access = "text_mention_only" if (is_print_only and not seg_has_read) else (
                            output_confirms_access(call) if seg_has_read else "text_mention_only")
                        record(call, "absolute_escape", resolved, access, s)

    contaminated_segments = sorted({f["segment"] for f in findings})
    return {
        "workspace_root": ws_root,
        "contaminated": bool(findings),
        "contaminated_segments": contaminated_segments,
        "policy_note": "受污染段停止正式效果评价，仅保留事后诊断（TEST §6.2）" if findings else None,
        "findings": findings,
        "mentions_only": mentions_only,
    }


def _resolve_agent_uuid(agent_name: str | None, description: str, catalog: dict[str, dict],
                        settled_list: list[dict], used_uuids: set[str]) -> str | None:
    """将 subagent 调用的 agent 名/描述对齐到原生 catalog 的 UUID childId。"""
    if agent_name and agent_name in catalog:
        return agent_name
    if agent_name:
        for s in settled_list:
            m = SETTLED_AGENT_RE.search(str(s.get("summary") or ""))
            if m and m.group(1) == agent_name and s.get("childId"):
                return str(s["childId"])
    if description:
        for cid, entry in catalog.items():
            if cid not in used_uuids and str(entry.get("label") or "") == description:
                return cid
    return agent_name


def native_delegations(sessions: dict, children: dict[Path, dict] | None = None) -> dict:
    """原生会话里的委派与派审：按派出去的正文与子会话实际产出认角色，支持常驻子代理经 `send_message`
    复用后的逐轮派发与逐次 `settled` 配对，按对象材料键分别列派发、报告与有效完成；缺关联留 unknown。
    没有保全原件时为 null。"""
    children = children or {}
    if not sessions["present"]:
        return {"delegations": None}
    rows, problems = [], list(sessions["problems"])
    observed: list[list] = []  # 可核子任务区间（原生登记/派发到收尾的 ms 时刻），跨父会话汇总
    for parent, info in sessions["read"]:
        catalog = {c["childId"]: c for c in info.get("children") or []}
        settled_all = list(info.get("settled") or [])
        settled_by_uuid: dict[str, list[dict]] = defaultdict(list)
        for s in settled_all:
            if s.get("childId"):
                settled_by_uuid[str(s["childId"])].append(s)
        for cid in settled_by_uuid:
            settled_by_uuid[cid].sort(key=lambda x: (x.get("time") is None, x.get("time") or 0))
        # 收集整份会话的派发调用（初始 subagent/task/verifier + 后续 send_message）
        agent_to_uuid: dict[str, str] = {}
        uuid_role: dict[str, tuple[str, str | None, str]] = {}  # uuid -> (role, basis, label)
        used_uuids: set[str] = set()
        dispatches: list[dict] = []
        for call in info.get("calls") or []:
            name = call.get("name")
            if name in DELEGATING_TOOLS or name == "verifier":
                args = _args(call)
                started = next((m.group(1) for r in call.get("results") or []
                                for m in [STARTED_RE.search(r.get("text") or "")] if m), None)
                agent_name = str(args.get("name") or started or "") or None
                desc = str(args.get("description") or "")
                prompt = str(args.get("prompt") or "")
                cid = _resolve_agent_uuid(agent_name, desc, catalog, settled_all, used_uuids)
                if cid:
                    used_uuids.add(cid)
                    if agent_name:
                        agent_to_uuid[agent_name] = cid
                role = next((r for pattern, r in CARRIER_ROLES if pattern.search(prompt)), None)
                basis = "派出去的是产品生成的载体" if role else None
                if role is None and STAGE_REQUEST_RE.search(str(call.get("args") or "")):
                    role, basis = "stage_verifier", "派出去的是原生阶段审查请求"
                child_file = parent.parent / "children" / str(cid) / "session.v4.jsonl.zstd" if cid else None
                child = children.get(child_file) if child_file is not None else None
                if child is None and child_file is not None and child_file.is_file():
                    child = _native(child_file)
                if role is None and child and not child.get("error"):
                    role = _child_role(child)
                    basis = "子会话写了蓝图设计产物" if role else None
                entry = catalog.get(cid or "") or {}
                label = entry.get("label") or desc
                if cid:
                    uuid_role[cid] = (role or "unresolved", basis, label)
                dispatches.append({
                    "tool": name, "cid": cid, "agent": agent_name or cid, "prompt": prompt,
                    "role": role or "unresolved", "basis": basis, "label": label,
                    "child": child, "start_time": call.get("time") or entry.get("createdAt"),
                })
            elif name == "send_message":
                args = _args(call)
                agent_name = str(args.get("agent") or "") or None
                prompt = str(args.get("message") or "")
                cid = agent_to_uuid.get(agent_name or "") or _resolve_agent_uuid(agent_name, "", catalog, settled_all, used_uuids)
                if cid and agent_name:
                    agent_to_uuid[agent_name] = cid
                carrier_role = next((r for pattern, r in CARRIER_ROLES if pattern.search(prompt)), None)
                prev_role, prev_basis, prev_label = uuid_role.get(cid or "", ("unresolved", None, agent_name or ""))
                role = carrier_role or prev_role
                basis = "经 send_message 续派产品载体" if carrier_role else (
                    f"续派同一子代理（{prev_basis}）" if prev_basis else "续派同一子代理")
                # 仅把已知审查员/蓝图作者/含产品载体的续派计入委派轮次（避免无关聊天污染）
                if role not in ("questioning", "story_review", "figure_review", "stage_verifier", "blueprint_author"):
                    continue
                child_file = parent.parent / "children" / str(cid) / "session.v4.jsonl.zstd" if cid else None
                child = children.get(child_file) if child_file is not None else None
                if child is None and child_file is not None and child_file.is_file():
                    child = _native(child_file)
                dispatches.append({
                    "tool": name, "cid": cid, "agent": agent_name or cid, "prompt": prompt,
                    "role": role, "basis": basis, "label": prev_label or agent_name or "",
                    "child": child, "start_time": call.get("time"),
                })

        # 按同一 cid 的派发时间顺序逐轮配对 settled 通知
        by_cid: dict[str, list[dict]] = defaultdict(list)
        for d in dispatches:
            by_cid[str(d["cid"] or f"__anon_{id(d)}")].append(d)
        for cid, group in by_cid.items():
            s_queue = list(settled_by_uuid.get(cid, []))
            s_idx = 0
            for idx_in_group, d in enumerate(group):
                t_start = d["start_time"]
                t_next = group[idx_in_group + 1]["start_time"] if idx_in_group + 1 < len(group) else None
                done = None
                if s_idx < len(s_queue):
                    # 优先选在 [t_start, t_next) 区间内的首个未消费 settled
                    while s_idx < len(s_queue):
                        cand = s_queue[s_idx]
                        ct = cand.get("time")
                        if t_start is not None and ct is not None and ct < t_start:
                            s_idx += 1
                            continue
                        if t_next is not None and ct is not None and ct >= t_next:
                            break
                        done = cand
                        s_idx += 1
                        break
                d["done"] = done
                if t_start is not None and done and done.get("time") is not None and done["time"] >= t_start:
                    observed.append([t_start, done["time"]])
            # 兜底：若该 cid 没有任何 call 时间戳但 catalog 有 createdAt 与 settled，仍保留首末跨度
            if not any(d.get("done") for d in group) and cid in catalog and cid in settled_by_uuid:
                cat_t = catalog[cid].get("createdAt")
                last_t = settled_by_uuid[cid][-1].get("time")
                if cat_t and last_t:
                    observed.append([cat_t, last_t])

        for d in dispatches:
            done = d.get("done")
            t_start = d["start_time"]
            span_sec = ((done["time"] - t_start) / 1000
                        if done and done.get("time") is not None and t_start is not None and done["time"] >= t_start
                        else None)
            span = round(span_sec / 60, 1) if span_sec is not None else None
            summary = str((done or {}).get("summary") or "")
            reply = _closing_reply(done)
            prompt = d["prompt"]
            objects = sorted({key for key in CARRIER_KEY_RE.findall(prompt)}) if prompt else []
            report_files = DISPATCH_REPORT_RE.findall(prompt) if prompt else []
            row = {"role": d["role"], "basis": d["basis"], "label": d["label"],
                   "agent": d["agent"], "dispatch_tool": d["tool"],
                   "child_id": d["cid"], "task_id": d["cid"], "observed_span_min": span,
                   "observed_span_sec": round(span_sec, 1) if span_sec is not None else None,
                   "reply_received": reply["reply_received"], "objects": objects if objects else None,
                   "report_file": report_files[0] if len(report_files) == 1 else None,
                   "settled": "failed" if "failed" in summary else "finished" if "finished" in summary else "unknown"}
            if row["role"] == "story_review":
                row["review_mode"] = _review_mode(prompt)
                row["review_conclusion"] = _reply_conclusion(prompt, reply, done)
                row["report_completeness"] = _report_completeness(prompt, reply, row["review_conclusion"], d["child"])
            rows.append(row)

    conclusions = Counter(r["review_conclusion"]["value"] for r in rows if "review_conclusion" in r)
    modes = Counter(r["review_mode"] for r in rows if "review_mode" in r)
    reviews = [r for r in rows if r["role"] == "story_review"]
    questionings = [r for r in rows if r["role"] == "questioning"]
    review_objects = {key for r in reviews for key in (r["objects"] or [])}
    unique_reports = {(key, r.get("report_file")) for r in reviews for key in (r["objects"] or [])}
    by_object: dict[str, dict] = {}
    for r in reviews:
        obj_key = (r["objects"] or ["unknown"])[0]
        bucket = by_object.setdefault(obj_key, {"dispatches": 0, "reports": [], "settled": 0, "complete": 0, "conclusions": []})
        bucket["dispatches"] += 1
        if r.get("report_file") and r["report_file"] not in bucket["reports"]:
            bucket["reports"].append(r["report_file"])
        if r["settled"] != "unknown":
            bucket["settled"] += 1
        if r["report_completeness"]["value"] == "complete":
            bucket["complete"] += 1
        bucket["conclusions"].append(r["review_conclusion"]["value"])

    return {"delegations": {
        "observed_intervals": observed,
        "by_role": dict(Counter(r["role"] for r in rows)),
        "questioning_dispatches": len(questionings),
        "questioning_settled": sum(1 for r in questionings if r["settled"] != "unknown"),
        "story_review_tasks": len(reviews),
        "story_review_dispatches": len(reviews),
        "story_review_settled": sum(1 for r in reviews if r["settled"] != "unknown"),
        "story_review_replies": sum(1 for r in reviews if r["reply_received"]),
        "story_review_full_replies": sum(1 for r in reviews if r["report_completeness"]["value"] == "complete"),
        "story_review_reports_unknown": sum(1 for r in reviews if r["report_completeness"]["value"] == "unknown"),
        "story_review_objects": len(review_objects),
        "story_review_unique_reports": len(unique_reports),
        "story_review_by_object": by_object,
        "story_review_conclusions": dict(conclusions),
        "story_review_modes": dict(modes),
        "items": rows, "problems": problems}}


#: 宿主收尾通知里，子会话最后那条回复从这一行之后开始
CLOSING_MESSAGE = "Its closing message:\n"
#: 产品派审载体给审查者的材料键（independent-review.mjs）
CARRIER_KEY_RE = re.compile(r"^- 材料键：`([0-9a-f]{64})`", re.MULTILINE)
REPLY_KEY_RE = re.compile(r"^material_key: *([0-9a-f]{64}) *$", re.MULTILINE)
#: 产品回复合同的开头第二行（review-report-contract.mjs 的 CONCLUSIONS）
CONCLUSION_LINE_RE = re.compile(r"^conclusion: *(pass|warn|fail) *$")
#: 已保全的 2.0.2 及以前运行记录里的报告标题：只读识别历史记录，产品不再接收这种形态
RECORDED_REPORT_HEADINGS = ("判据核对", "发现", "总体结论")
STATED_RE = re.compile(r"^(pass|warn|fail)(?![A-Za-z])")
#: 派审载体分配给读者的本次报告文件（这一次唯一可写的位置）
DISPATCH_REPORT_RE = re.compile(r"^- 本次报告文件：`([^`]+)`", re.MULTILINE)
#: 读者报告原件的文件名形态（目录可由 `--report-dir` 指定，不写死默认位置）
REPORT_ORIGINAL_RE = re.compile(r"review-original\.\d+\.md$")


def _closing_reply(done: dict | None) -> dict:
    """收尾通知里「取得回复文本」这一件事实：{reply_received, reply, why}。

    任务收尾与否由 `settled` 记；这里只看通知里有没有子会话的回复正文。收尾标志之后是空的
    （或整条通知没有收尾回复）都算没取得回复文本，不拿收尾状态冒充。
    """
    if not done:
        return {"reply_received": False, "reply": None, "why": "没有收尾通知"}
    text = str(done.get("text") or "")
    if CLOSING_MESSAGE not in text:
        return {"reply_received": False, "reply": None, "why": "收尾通知里没有收尾回复"}
    reply = text.split(CLOSING_MESSAGE, 1)[1]
    if not reply.strip():
        return {"reply_received": False, "reply": None, "why": "收尾回复是空的"}
    return {"reply_received": True, "reply": reply, "why": None}


def _reply_conclusion(prompt: str, reply: dict, done: dict | None) -> dict:
    """Story 独审收尾回复写明的结论：{value: pass/warn/fail/unknown, why, at}。

    只做结构提取：取得的那一份回复开头是材料键、恰好一行且是派出去的那一份；现行回复第二行是
    `conclusion: pass|warn|fail`，已保全的历史记录按当时的三个二级标题、「总体结论」第一行读。
    任何一条不成立都是 unknown 并写明原因——不从正文里的 fail 字样推断，也不把收尾 finished 当通过；
    审查是否充分归独立评审。没取得回复文本时用 `_closing_reply` 给的原因，不另造结论。
    """
    def unknown(why: str) -> dict:
        return {"value": "unknown", "why": why, "at": None}
    if not reply["reply_received"]:
        return unknown(reply["why"])
    text = reply["reply"]
    carrier = CARRIER_KEY_RE.findall(prompt)
    keys = REPLY_KEY_RE.findall(text)
    if len(carrier) != 1 or keys != carrier:
        return unknown("回复的材料键对不上派出去的审查对象")
    lines = text.splitlines()
    at = lambda i: {"child_id": (done or {}).get("childId"), "settled_time": (done or {}).get("time"),  # noqa: E731
                    "reply_line": i + 1}
    current = CONCLUSION_LINE_RE.match(lines[1].strip()) if len(lines) > 1 and REPLY_KEY_RE.match(lines[0]) else None
    if current:
        return {"value": current.group(1), "why": None, "at": at(1)}
    if not _recorded_report(lines):
        return unknown("回复开头两行不是材料键与结论，也不是历史记录的报告形态")
    heads = [(i, line[3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    start = next(i for i, h in heads if h == "总体结论")
    end = next((i for i, _ in heads if i > start), len(lines))
    first = next(((i, line.strip()) for i, line in enumerate(lines[start + 1:end], start + 1) if line.strip()), None)
    stated = STATED_RE.match(first[1]) if first else None
    if not stated:
        return unknown("「总体结论」第一行不是 pass / warn / fail")
    return {"value": stated.group(1), "why": None, "at": at(first[0])}


def _recorded_report(lines: list[str]) -> bool:
    """已保全的历史记录（2.0.2 及以前）的报告形态：那三个二级标题齐全。"""
    heads = {line[3:].strip() for line in lines if line.startswith("## ")}
    return all(heading in heads for heading in RECORDED_REPORT_HEADINGS)


def _writer_path(path: object) -> str:
    """工具入参里的文件路径归一成工程相对形态：统一斜杠、去掉开头的 `./`。"""
    text = str(path or "").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _is_absolute_path(text: str) -> bool:
    """归一后的路径是不是绝对路径（Windows 盘符或 POSIX 根）。"""
    return text.startswith("/") or bool(re.match(r"^[A-Za-z]:/", text))


def _same_path(left: str, right: str) -> bool:
    """两个归一后的路径是不是同一个位置；Windows 上盘符与大小写不区分。"""
    return left.casefold() == right.casefold() if sys.platform.startswith("win") else left == right


def _is_report_path(path: object, want: str, cwd: object = None) -> bool:
    """是不是派审载体分配给这一次的报告文件：工程相对路径逐字相等；绝对路径必须是同一子会话工作区里的
    同一个相对位置。写进别的相对目录或别的工作区，即使同名后缀也不算这一次的原件。"""
    got = _writer_path(path)
    if not want:
        return False
    if _same_path(got, want):
        return True
    root = _writer_path(cwd).rstrip("/")
    return _is_absolute_path(got) and bool(root) and _same_path(got, f"{root}/{want}")


def _write_outcome(call: dict) -> str:
    """一次写类调用的结果事实：`success` / `error` / `no_result`（只有调用、没有结果不算写出）。"""
    results = [r for r in call.get("results") or [] if isinstance(r, dict)]
    if not results:
        return "no_result"
    return "error" if results[-1].get("isError") else "success"


def _reader_original(prompt: str, child: dict | None) -> dict:
    """读者原件：派审载体分配的报告文件，在同一个读者子会话里由读者自己成功写出的正文。

    `{report_file, text, why}`。只认载体写明的那个位置（同一工作区、同一相对路径；同名后缀不代证）：
    调用失败或没有结果不算写出；同一位置最后一次成功改动不是「写出全文」时重建不出原样正文；
    没有保全的子会话或读不出时取不到；原件的材料键不是这一次派审的对象也不采用。
    """
    files = DISPATCH_REPORT_RE.findall(prompt)
    if len(files) != 1:
        return {"report_file": None, "text": None, "why": "派审载体没有写明这一次的本次报告文件"}
    report_file = files[0]
    want = _writer_path(report_file)
    if not REPORT_ORIGINAL_RE.search(want):
        return {"report_file": report_file, "text": None,
                "why": f"派审载体写的报告位置不是读者报告原件（review-original.<n>.md）：{report_file}"}
    if not child:
        return {"report_file": report_file, "text": None, "why": "没有保全的读者子会话，取不到读者原件"}
    if child.get("error"):
        return {"report_file": report_file, "text": None, "why": f"读者子会话读不出（{child['error']}）"}
    cwd = (child.get("header") or {}).get("cwd")
    calls = [call for call in child.get("calls") or [] if call.get("name") in AUTHORING_TOOLS]
    touched = [call for call in calls if _is_report_path(_args(call).get("file_path"), want, cwd)]
    if not touched:
        elsewhere = next((call for call in calls
                          if _writer_path(_args(call).get("file_path")).endswith("/" + want)), None)
        if elsewhere:
            return {"report_file": report_file, "text": None,
                    "why": f"读者写的是 {_writer_path(_args(elsewhere).get('file_path'))}，"
                           f"不是本次报告文件位置 {want}：同名后缀不能跨目录或工作区代证"}
        return {"report_file": report_file, "text": None, "why": f"读者子会话里没有写本次报告文件 {want}"}
    done = [(call, _write_outcome(call)) for call in touched]
    if not any(outcome == "success" for _, outcome in done):
        outcome = done[-1][1]
        why = ("读者写本次报告文件的调用返回错误，参数里的正文不能证明文件已经写出"
               if outcome == "error" else
               "读者写本次报告文件的调用没有结果，不能证明文件已经写出")
        return {"report_file": report_file, "text": None, "why": why}
    last = next(call for call, outcome in reversed(done) if outcome == "success")
    if last.get("name") != "write":
        return {"report_file": report_file, "text": None,
                "why": f"本次报告文件最后一次成功改动不是写出全文（{last.get('name')}），重建不出原样正文"}
    text = _args(last).get("content")
    if not isinstance(text, str):
        return {"report_file": report_file, "text": None, "why": "本次报告文件的写出调用没有可恢复的正文"}
    carrier = CARRIER_KEY_RE.findall(prompt)
    if len(carrier) != 1 or REPLY_KEY_RE.findall(text)[:1] != carrier:
        return {"report_file": report_file, "text": None,
                "why": "读者原件的材料键不是这一次派审的对象，不能拿它核完整"}
    return {"report_file": report_file, "text": text, "why": None}


def _whole_text(text: str) -> str:
    """正文对照用的归一：换行统一成 LF、去掉首尾空白；行内不改，合同要求与报告文件同一份正文。"""
    return str(text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _original_completeness(original: str, final: str) -> str | None:
    """读者原件与整份 final 对照：是同一份且有正文返回 None，否则返回为什么算不上可核完整。"""
    want, got = _whole_text(original), _whole_text(final)
    body = [line for line in want.splitlines()[2:] if line.strip()]
    if not want or not got:
        return "读者原件或最终回复是空的"
    if want == got:
        return None if body else "读者原件只有报告开头、没有正文"
    if want.startswith(got):
        return "最终回复只有报告开头" if len(got.splitlines()) <= 2 else "最终回复只是读者原件的一部分，缺正文"
    return "最终回复与读者原件不是同一份（报告文件是原件，最终回复要给同一份正文）"


def _report_completeness(prompt: str, reply: dict, conclusion: dict, child: dict | None) -> dict:
    """报告完整性的可核结论：{value: complete/unknown, why, basis, report_file}。

    **任务收尾、取得回复文本、声明结论、报告可核完整是四件事。** 有现行报告合同的派审（载体写明了
    `本次报告文件`），先核同一次派审、同一对象、所配位置上有成功结果的那次完整写入（读者原件），
    再与整份 final 对同一份正文：一致且原件有正文才算 complete。只有失败或没有结果的调用、写进别的
    相对目录或别的同名后缀，都不足以证明文件存在。载体没有现行报告合同的是按当时身份保全下来的历史
    派审，只能按当时的完整报告形态（三个二级标题）读取；现行作者自己选的 Markdown 标题不改变证据标准。
    其余一律 unknown，并保留已收尾、已取得回复文本、已声明结论这些事实——不据回复长短、正文里的字样
    或收尾状态推断完整。`basis` 写明凭什么判的，便于反查。
    """
    if not reply["reply_received"]:
        return {"value": "unknown", "why": reply["why"], "basis": None, "report_file": None}
    if conclusion.get("why"):
        return {"value": "unknown", "why": conclusion["why"], "basis": None, "report_file": None}
    files = DISPATCH_REPORT_RE.findall(prompt)
    if not files:
        # 旧载体没有「本次报告文件」这一行：这是历史派审，按当时的完整报告形态只读识别。
        if _recorded_report(str(reply["reply"]).splitlines()):
            return {"value": "complete", "why": None, "basis": "recorded_report", "report_file": None}
        return {"value": "unknown", "basis": None, "report_file": None,
                "why": "历史派审没有现行报告文件，回复也不是当时的完整报告形态（三个二级标题），核不了完整"}
    if len(files) > 1:
        return {"value": "unknown", "basis": None, "report_file": None,
                "why": "派审载体写明了不止一个本次报告文件，无法确定哪一份是这一次的原件"}
    original = _reader_original(prompt, child)
    if original["text"] is None:
        return {"value": "unknown", "why": original["why"], "basis": None, "report_file": original["report_file"]}
    why = _original_completeness(original["text"], reply["reply"])
    if why:
        return {"value": "unknown", "why": why, "basis": None, "report_file": original["report_file"]}
    return {"value": "complete", "why": None, "basis": "reader_original", "report_file": original["report_file"]}


def _diagrams(run_dir: Path) -> dict:
    """产物里画了几张图，流程章有没有图。

    图是形态里唯一「有没有」一眼可数的东西，而它恰恰是连续几跑都没自发出现的那一项。
    不数它的话，三轴评分里「产物结果」那一轴只能靠人翻产物才知道图画没画。
    按章分：流程章为 0 单独标出——那一章没有图，等于主路径只剩文字复述。
    """
    story = next(iter(sorted(run_dir.rglob("story.md"))), None)
    if story is None:
        return {"diagrams_total": None, "diagrams_in_flow_chapter": None}
    total = 0
    in_flow = 0
    chapter = ""
    for line in story.read_text(encoding="utf-8", errors="replace").split("\n"):
        head = line.strip()
        if head.startswith("## "):
            chapter = head[3:].strip()
        if DIAGRAM_FENCE_RE.match(line):
            total += 1
            if "流程" in chapter:
                in_flow += 1
    return {"diagrams_total": total, "diagrams_in_flow_chapter": in_flow}


def _startup_gap(run_dir: Path, first_model_ts) -> dict:
    """起跑到**模型动第一下**之间空了多久。

    二跑这一段是 4.5 分钟零事件。是宿主在准备工作区、还是被测模型首轮延迟，
    没有数就只能猜。这里只报数——它不进任何 PASS 条件，是查因的入口。

    量的锚点是第一条工具调用或用量上报：装置起跑当场就会写一条自己的事件，
    拿它当锚点，算出来的空档恒等于零。
    """
    if first_model_ts is None:
        return {"startup_gap_sec": None, "startup_gap_source": "no_model_events"}
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        started = datetime.strptime(str(state["started_at"]), "%Y-%m-%d %H:%M:%S")
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return {"startup_gap_sec": None, "startup_gap_source": "unavailable"}
    first = first_model_ts.replace(tzinfo=None) if first_model_ts.tzinfo else first_model_ts
    return {"startup_gap_sec": round((first - started).total_seconds(), 1),
            "startup_gap_source": "run_state"}


def _human_wait(run_dir: Path) -> dict:
    """人工等待由**驱动器**累计（它才知道什么时候开始等、什么时候等到）。

    读不到就报 ``None`` 而不是 0：「这轮没人等过」和「这份记录里没有这个字段」是两件事，
    压成同一个 0 之后，任何一次统计都无法分辨自己看的是事实还是缺省值。
    """
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"human_wait_sec": None, "human_wait_events": None, "human_wait_source": "unavailable"}
    raw = state.get("human_wait_sec")
    if raw is None:
        return {"human_wait_sec": None, "human_wait_events": None, "human_wait_source": "not_recorded"}
    return {"human_wait_sec": float(raw),
            "human_wait_events": int(state.get("human_wait_events") or 0),
            "human_wait_source": "run_state"}


def _completeness_note(item: dict) -> str:
    """报表里报告完整性的括注：可核时写凭什么核的（读者原件 / 历史报告形态），未核证时写原因。"""
    report = item["report_completeness"]
    if report["value"] == "complete":
        return {"reader_original": "读者原件与整份 final 一致",
                "recorded_report": "历史报告形态"}.get(report.get("basis"), "可核")
    return report.get("why") or "未核证"


def render(result: dict) -> str:
    lines = [
        "[measure_run] 实跑效率度量（只报数，达标与否由人判断；范围是整份 events.jsonl，分段按实际 checkpoint）",
        f"  事件 {result['events']}｜工具调用 {result['tool_calls']}（其中 {result['tool_calls_completed_from_native']} 次由同一原生调用补齐截断或缺端）"
        f"｜时长 {result['duration_min']} 分钟",
        f"  父会话：assistant 响应（text 事件）{result['parent_counts']['assistant_responses']} 条｜工具调用 {result['parent_counts']['tool_calls']} 次",
        (f"  子会话：{result['child_counts']['sessions']} 份保全原件｜assistant 响应 {result['child_counts']['assistant_responses']} 条"
         f"｜工具调用 {result['child_counts']['tool_calls']} 次（与父会话口径不同，不是 API 次数）"
         if result["child_counts"]["sessions"] is not None
         else "  子会话：没有保全原件，响应与工具调用数未知（不是 0）"),
        *([f"  统计不完整，仅为已观察到的次数：归并不了的工具事件 "
           + "、".join(f"{reason} {count}" for reason, count in
                      Counter(item["reason"] for item in result["incomplete_tool_events"]).most_common())]
          if result.get("incomplete_tool_events") else []),
        "",
        "  ── 作者在读什么 ──",
        f"    读规则文本（framework/ 与 doc/extensions/）：{result['reads_rule_text']} 次   目标 ≤20/阶段",
        f"    读自己的产物（doc/features/）：            {result['reads_own_artifacts']} 次",
        f"    两者之比：                                  {result['rule_over_own_ratio']}   诊断基线 2.8",
        f"    **读 checker 源码：                         {result['reads_checker_source']} 次   目标 0**",
        "",
        "  ── 上下文 ──",
        f"    context_total：{result['context_first']} → {result['context_last']}"
        f"（首末两次请求读数之差 {result['context_growth']}，不是单阶段净增）   spec 阶段目标 ≤150K",
        "",
        "  ── 门禁 ──",
        f"    harness 运行 {result['harness_runs']} 次",
        f"    有 FAIL 的门禁轮次：{result['gate_rounds_with_fail']} 轮",
        f"    门禁结论按种类：失败 {result['gate_fail_by_kind']}，判不了 {result['gate_unknown_by_kind']}",
        f"    反复 FAIL 的 check：{result['repeated_check_fails'] or '（本轮没有 FAIL）'}   目标 同一 id ≤2 轮",
        f"    审查结论（review --action check，每次调用的结论值）：{result['review_results'] or '（没有观察到）'}",
        "",
        "  ── 委派（按原生会话认角色；按实际派发轮次算，不按目录数）──",
        *(["    没有保全的原生会话：委派角色未取得（不是没有委派）"] if result.get("delegations") is None else [
            f"    按角色：{result['delegations']['by_role'] or '（没有委派）'}",
            f"    Story 独审任务 {result['delegations']['story_review_tasks']} 个"
            f"（完整回复 {result['delegations']['story_review_full_replies']} 个，"
            f"审查对象 {result['delegations']['story_review_objects']} 个）",
            f"    派发轮次：蓝图质询 {result['delegations'].get('questioning_dispatches', 0)} 次"
            f"（收尾 {result['delegations'].get('questioning_settled', 0)} 次）"
            f"｜Story 独审 {result['delegations'].get('story_review_dispatches', result['delegations']['story_review_tasks'])} 次"
            f"（不同报告 {result['delegations'].get('story_review_unique_reports', 0)} 份）",
            f"    回复事实：已收尾 {result['delegations']['story_review_settled']} 个"
            f"｜取得回复文本 {result['delegations']['story_review_replies']} 个"
            f"｜未核证完整报告 {result['delegations']['story_review_reports_unknown']} 个"
            "（单列，不是任务失败；完整回复只计可核完整的那几份）",
            f"    Story 独审回复写明的总体结论：{result['delegations']['story_review_conclusions'] or '（没有 Story 独审）'}"
            "（与收尾状态、父方报告接收结论分开计）",
            *(f"    - {i['role']}｜{i['label']}（{i.get('dispatch_tool', 'subagent')}）｜观察跨度 {i['observed_span_min'] if i['observed_span_min'] is not None else '未知'} 分钟"
              f"（含等待，不是纯推理）｜收尾 {i['settled']}｜回复文本 {'有' if i['reply_received'] else '无'}"
              + (f"｜完整报告 {'可核' if i['report_completeness']['value'] == 'complete' else '未核证'}"
                 f"（{_completeness_note(i)}）" if "report_completeness" in i else "")
              + (f"｜回复结论 {i['review_conclusion']['value']}"
                 + (f"（{i['review_conclusion']['why']}）" if i['review_conclusion']['why'] else "")
                 if "review_conclusion" in i else "") for i in result["delegations"]["items"]),
            *(f"    读不了：{p}" for p in result["delegations"]["problems"])]),
        "",
        "  ── 隔离边界（只读扫描；受污染段停止正式评价）──",
        *(["    未检出外部访问"
           + (f"（仅提及路径文字 {len(result['isolation_boundary'].get('mentions_only') or [])} 条）"
              if (result.get("isolation_boundary") or {}).get("mentions_only") else "")]
          if not (result.get("isolation_boundary") or {}).get("contaminated") else [
            f"    **已受污染**：{len(result['isolation_boundary']['findings'])} 处外部访问"
            f"（影响段：{', '.join(result['isolation_boundary']['contaminated_segments'])}；"
            f"仅路径文字 {len(result['isolation_boundary'].get('mentions_only') or [])} 条）",
            *(f"    - L{f['line']} [{f['segment']}] {f['tool']} {f['kind']}（{f['access']}）→ {f['resolved_path']}"
              + (" [截断待核]" if f.get("truncated_needs_host_check") else "")
              for f in result["isolation_boundary"]["findings"])]),
        "",
        "  ── 时间去哪了（可核区间取并集；间隔估计不是实测 span）──",
        f"    墙钟 {result['duration_min']} 分钟（首末事件）"
        f"｜可核工具区间 {result['tool_interval_sec'] if result['tool_interval_sec'] is not None else '未知'}s"
        f"｜可核子任务区间 {result['delegation_interval_sec'] if result['delegation_interval_sec'] is not None else '未知'}s"
        f"｜未归属 {result['not_attributed_sec'] if result['not_attributed_sec'] is not None else '未知'}s"
        "（含模型推理、宿主准备、等待与事件空档，不是纯推理）",
        f"    门禁 {result['gap_sec_by_kind']['gate']}s｜verifier {result['gap_sec_by_kind']['verifier']}s"
        f"｜成文 {result['gap_sec_by_kind']['authoring']}s｜其它 {result['gap_sec_by_kind']['other']}s",
        (f"    人工等待：{result['human_wait_sec']}s（{result['human_wait_events']} 次）  —— 独立计时，不进上面四项"
         if result["human_wait_sec"] is not None
         else f"    人工等待：未知（{result['human_wait_source']}）  —— 不是 0，是这份记录里没有"),
        (f"    起跑空档：{result['startup_gap_sec']}s  —— 起跑到第一条会话事件，查因用"
         if result.get("startup_gap_sec") is not None
         else f"    起跑空档：未知（{result.get('startup_gap_source')}）"),
        "",
        "  ── story 守恒两层各担多少 ──",
        (f"    机器核实 {result['conservation_machine']} 条 / 模型裁决 "
         f"{result['conservation_model']} 条   模型层的保证只能靠对抗测试证明"
         if result["conservation_machine"] is not None
         else "    （本轮没跑出 story-build check 的通过行）"),
        "",
        "  ── 按段（模型与工具时间是间隔归属的近似值）──",
    ]
    for name, seg in (result.get("segments") or {}).items():
        lines.append(
            f"    {name}：{seg['duration_min']} 分钟｜非工具事件间隔 {seg['nontool_gap_sec']}s"
            f"（含推理/等待/空档，不是纯推理）｜工具相邻间隔 {seg['tool_gap_sec']}s"
            f"｜verifier {seg['verifier_runs']} 次 {seg['verifier_gap_sec']}s｜其它委派 {seg['delegations_unresolved']} 次"
            f"｜首次门禁 {seg['first_harness']}｜首次登记 {seg['first_story_register']}｜返工 {seg['rework_min']} 分钟")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 events.jsonl 度量实跑效率")
    ap.add_argument("target", help="events.jsonl 路径，或包含它的目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非人读格式")
    args = ap.parse_args()

    path = Path(args.target)
    if path.is_dir():
        # run 目录下有两层 events.jsonl：run 级汇总（本目录直下）与每一轮的
        # `cli-runtime/<turn>/events.jsonl`。**先认本目录直下那份**——
        # 递归后按字符串排序会让 `cli-runtime/…` 排在前面，于是只量到一轮：
        # 实测同一次运行，汇总 1399 条事件、单轮 164 条，七项指标全部失真。
        direct = path / "events.jsonl"
        if direct.exists():
            path = direct
        else:
            found = sorted(path.rglob("events.jsonl"))
            if not found:
                raise SystemExit(f"[measure_run] {path} 下找不到 events.jsonl")
            # 退而求其次时取**最大**的那份，而不是排序第一份
            path = max(found, key=lambda p: p.stat().st_size)
    if not path.exists():
        raise SystemExit(f"[measure_run] 读不到 {path}")

    result = measure(path, run_dir=path.parent)
    result["source"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
