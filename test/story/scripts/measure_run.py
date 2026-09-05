# -*- coding: utf-8 -*-
"""实跑效率度量 —— 从 ``events.jsonl`` 读出批次 3 的七项目标是否达成。

## 为什么要有它

批次 3 的诊断是「时间花在猜门禁要什么」：实测门禁回环占全程 49.3%，读 ``framework/**``
与 ``doc/extensions/**`` 合计是读自身产物的 2.8 倍，``check-spec.ts`` 被读 9 次——
模型在逆向 checker 学要求。这些结论当时是人工统计出来的；没有脚本，下一轮就无从比较。

**它只报数，不判 PASS/FAIL**：数字是诊断信息，不是写作命令（G8）。
达标与否由人看着数字判断，脚本不替它下结论。

用法：
    python measure_run.py <events.jsonl 或含它的目录> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

#: 读「规则文本」的路径形态——判它是不是在猜门禁要什么，而不是在读自己的产物。
RULE_PATH_RE = re.compile(r"(framework/|doc/extensions/)")

#: checker 源码：读它 = 在逆向判据。目标是 0 次。
#:
#: 两处都要认：framework 的 `check-*.ts`，以及**扩展自己的判据脚本**——
#: 一轮实跑里被读得最多的正是后者（`story-build.mjs` 34 次、`knowledge-use.mjs` 17 次）。
#: 知识层（`doc/extensions/knowledge/`）不算：那是给模型实现需求用的内容，读它是正当的。
CHECKER_PATH_RE = re.compile(
    r"framework/harness/scripts/check-[a-z]+\.ts"
    r"|doc/extensions/(?:hooks|skills)/[\w/.-]+\.(?:mjs|py|ts)")

#: 从 bash 命令里认出「在读文件」——bash 常被当成第二套 Read。
#:
#: `node -e "readFileSync(...)"` 也是读：一轮实跑里 68 次读判据脚本**全部**走这条，
#: 而当时的口径只认 `cat/head/sed`，于是报表上写着「读 checker 源码 0 次」。
#: 度量报 0 而实际 68，比没有这项度量更坏——它让人以为这条已经解决了。
#: 图围栏——与 story-build check 的形态判据同一个口径（mermaid 及几种等价标记）。
DIAGRAM_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)[ \t]*(?:mermaid|plantuml|puml|dot|graphviz)\b",
                              re.IGNORECASE)

BASH_READ_RE = re.compile(
    r"\b(cat|head|tail|sed|less|type|grep|rg|awk)\b|readFileSync|readFile\b|open\(")

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


def _request_text(event: dict) -> str:
    """**作者要什么**：工具入参与事件正文。路径类判定只看这里。

    绝不把 `tool_output` 掺进来：Read 的输出里带着整份文件正文，一份 `doc/features/` 产物
    只要正文里提了 `framework/`，就会被算成「在读规则文本」。输入面才是作者的意图。
    """
    parts = [str(event.get("content") or "")]
    ti = event.get("tool_input")
    parts.append(json.dumps(ti, ensure_ascii=False) if isinstance(ti, (dict, list)) else str(ti or ""))
    return "\n".join(parts)


def _output_text(event: dict) -> str:
    """**工具回了什么**：门禁报的 check id、失败轮次、守恒两层的数都只在这里。

    旧口径整个漏了这一面（只读 content + tool_input），于是「反复 FAIL 的 check」在任何
    真实事件流上恒为空——不是「没有反复失败」，是压根没看那半边。ANSI 先剥掉再匹配。
    """
    out = event.get("tool_output")
    if isinstance(out, (dict, list)):
        out = json.dumps(out, ensure_ascii=False)
    return ANSI_RE.sub("", str(out or ""))


def measure(events_path: Path, *, run_dir: Path | None = None) -> dict:
    events = list(_iter_events(events_path))
    if not events:
        raise SystemExit(f"[measure_run] {events_path} 里没有可解析的事件——不是「指标为零」，是读不到数据")

    reads_rule = 0            # 读框架/扩展的规则文本
    reads_own = 0             # 读自己的产物
    reads_checker = 0         # 读 checker 源码
    tools = Counter()
    context_first = context_last = None
    harness_runs = 0
    gate_rounds_with_fail = 0
    check_fail_counts: Counter[str] = Counter()
    # 分段耗时：事件流里**没有工具开始事件**（一次调用只有一条 completed/error），
    # 所以拿不到真实 span。这里用「上一条事件到本条事件的间隔」归给本条，是**近似**，
    # 字段名带 _gap_sec 明说这一点——不把近似值包装成实测值。
    gap_by_kind: dict[str, float] = {"gate": 0.0, "verifier": 0.0, "authoring": 0.0, "other": 0.0}
    prev_ts = None
    conservation: tuple[int, int] | None = None
    first_ts = last_ts = None
    # 模型动的第一下——装置起跑当场就写事件，用它算空档量到的是装置自己
    first_model_ts = None

    for e in events:
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
            continue

        if etype != "tool":
            continue

        name = str(e.get("tool_name") or "").lower()
        tools[name] += 1
        request = _request_text(e)
        output = _output_text(e)

        looks_like_read = name in {"read", "grep", "glob"} or (
            name == "bash" and BASH_READ_RE.search(request))
        if looks_like_read:
            if CHECKER_PATH_RE.search(request):
                reads_checker += 1
            if RULE_PATH_RE.search(request):
                reads_rule += 1
            elif "doc/features/" in request:
                reads_own += 1

        is_harness = name == "bash" and HARNESS_CMD_RE.search(request)
        if is_harness:
            harness_runs += 1

        # 门禁报出的 check id 只在**输出**里。按「这一次工具调用」去重后再计数：
        # 同一份报告在 console 打一次、被 cat 再打一次，按文本次数算就会翻倍，
        # 而判据问的是「同一个 id 在多少**轮**门禁里失败」。
        failed_ids = {m.group(3) for m in CHECK_LINE_RE.finditer(output) if m.group(1) == "FAIL"}
        for cid in failed_ids:
            check_fail_counts[cid] += 1
        if failed_ids:
            gate_rounds_with_fail += 1

        if is_harness:
            gap_by_kind["gate"] += gap
        elif name == "task":
            gap_by_kind["verifier"] += gap
        elif name in {"write", "edit", "patch", "multiedit"}:
            gap_by_kind["authoring"] += gap
        else:
            gap_by_kind["other"] += gap

        # story 守恒的两层各担多少条——取最后一次通过时的数（也在输出面）
        hit = CONSERVATION_RE.search(output)
        if hit:
            conservation = (int(hit.group(1)), int(hit.group(2)))

    duration_min = None
    if first_ts and last_ts:
        duration_min = round((last_ts - first_ts).total_seconds() / 60, 1)

    return {
        "events": len(events),
        "duration_min": duration_min,
        "tool_calls": sum(tools.values()),
        "tools": tools.most_common(8),
        "reads_rule_text": reads_rule,
        "reads_own_artifacts": reads_own,
        "reads_checker_source": reads_checker,
        "rule_over_own_ratio": (round(reads_rule / reads_own, 2) if reads_own else None),
        "harness_runs": harness_runs,
        "context_first": context_first,
        "context_last": context_last,
        "context_growth": (context_last - context_first
                           if context_first is not None and context_last is not None else None),
        "gate_rounds_with_fail": gate_rounds_with_fail,
        "repeated_check_fails": check_fail_counts.most_common(5),
        "worst_repeated_check": (check_fail_counts.most_common(1)[0] if check_fail_counts else None),
        "gap_sec_by_kind": {k: round(v, 1) for k, v in gap_by_kind.items()},
        "conservation_machine": conservation[0] if conservation else None,
        "conservation_model": conservation[1] if conservation else None,
        **_diagrams(run_dir or events_path.parent),
        **_human_wait(run_dir or events_path.parent),
        **_startup_gap(run_dir or events_path.parent, first_model_ts),
    }


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


def render(result: dict) -> str:
    lines = [
        "[measure_run] 实跑效率度量（只报数，达标与否由人判断）",
        f"  事件 {result['events']}｜工具调用 {result['tool_calls']}｜时长 {result['duration_min']} 分钟",
        "",
        "  ── 作者在读什么 ──",
        f"    读规则文本（framework/ 与 doc/extensions/）：{result['reads_rule_text']} 次   目标 ≤20/阶段",
        f"    读自己的产物（doc/features/）：            {result['reads_own_artifacts']} 次",
        f"    两者之比：                                  {result['rule_over_own_ratio']}   诊断基线 2.8",
        f"    **读 checker 源码：                         {result['reads_checker_source']} 次   目标 0**",
        "",
        "  ── 上下文 ──",
        f"    context_total：{result['context_first']} → {result['context_last']}"
        f"（增量 {result['context_growth']}）   spec 阶段目标 ≤150K",
        "",
        "  ── 门禁 ──",
        f"    harness 运行 {result['harness_runs']} 次",
        f"    有 FAIL 的门禁轮次：{result['gate_rounds_with_fail']} 轮",
        f"    反复 FAIL 的 check：{result['repeated_check_fails'] or '（本轮没有 FAIL）'}   目标 同一 id ≤2 轮",
        "",
        "  ── 时间去哪了（间隔归属的近似值，不是实测 span）──",
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
    ]
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
