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
CHECKER_PATH_RE = re.compile(r"framework/harness/scripts/check-[a-z]+\.ts")

#: 从 bash 命令里认出「在读文件」——bash 常被当成第二套 Read。
BASH_READ_RE = re.compile(r"\b(cat|head|tail|sed|less|type)\b")

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


def _text_of(event: dict) -> str:
    """事件里可能提到路径的地方：工具入参与内容。"""
    parts = [str(event.get("content") or "")]
    ti = event.get("tool_input")
    parts.append(json.dumps(ti, ensure_ascii=False) if isinstance(ti, (dict, list)) else str(ti or ""))
    return "\n".join(parts)


def measure(events_path: Path) -> dict:
    events = list(_iter_events(events_path))
    if not events:
        raise SystemExit(f"[measure_run] {events_path} 里没有可解析的事件——不是「指标为零」，是读不到数据")

    reads_rule = 0            # 读框架/扩展的规则文本
    reads_own = 0             # 读自己的产物
    reads_checker = 0         # 读 checker 源码
    tools = Counter()
    context_first = context_last = None
    harness_runs = 0
    check_fail_counts: Counter[str] = Counter()
    conservation: tuple[int, int] | None = None
    first_ts = last_ts = None

    for e in events:
        ts = _ts(e.get("timestamp"))
        if ts:
            first_ts = first_ts or ts
            last_ts = ts

        etype = e.get("type")
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
        blob = _text_of(e)

        looks_like_read = name in {"read", "grep", "glob"} or (
            name == "bash" and BASH_READ_RE.search(blob))
        if looks_like_read:
            if CHECKER_PATH_RE.search(blob):
                reads_checker += 1
            if RULE_PATH_RE.search(blob):
                reads_rule += 1
            elif "doc/features/" in blob:
                reads_own += 1

        if name == "bash" and "harness-runner" in blob:
            harness_runs += 1

        # 门禁报出的 check id：同一个反复 FAIL 说明作者在逐层试
        for m in re.finditer(r"\b(lifecycle_hook_\w+|[a-z_]{6,})\b\s*(?:FAIL|未通过)", blob):
            check_fail_counts[m.group(1)] += 1

        # story 守恒的两层各担多少条——取最后一次通过时的数
        hit = CONSERVATION_RE.search(blob)
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
        "repeated_check_fails": check_fail_counts.most_common(5),
        "conservation_machine": conservation[0] if conservation else None,
        "conservation_model": conservation[1] if conservation else None,
    }


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
        f"    反复 FAIL 的 check：{result['repeated_check_fails'] or '（未识别到）'}   目标 同一 id ≤2 次",
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

    result = measure(path)
    result["source"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
