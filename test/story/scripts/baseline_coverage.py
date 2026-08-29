# -*- coding: utf-8 -*-
"""内容基线对照：新写的 story 比以前少讲了什么。

## 为什么要有它

批次 4 重写了 story 的骨架、判据与作业书。「内容更丰富」这件事只能靠比——
跟谁比是关键：跟上一个子批比，每轮只需比上一轮好一点，慢慢就滑走了；
跟批次 3 的产物比，那本身是已知劣化的。所以标尺是 `fixtures/content-baseline/`
里那三份批次 1 实跑产出的 story，它们冻结在那儿不动。

**对照是单向的**：只判「基线有而新 story 无」，不判反向。基线自己也有重复和工程
细节泄漏——那正是批次 4 要治的，当满分去对齐会把旧毛病一起抄回来。

## 它不判 PASS/FAIL

只报数（G8）。达标与否由人看着数字判断：机器能说的是「这 12 条在基线里有、
在新 story 里找不到」，说不了「丢掉它们要不要紧」。

## 只在测试域跑

不进生产链：它读的是基线夹具，那是评测数据，被测流程不该知道它存在。

用法：
    python baseline_coverage.py <新 story 路径> --baseline AR90004
    python baseline_coverage.py <新 story 路径> --baseline AR90004 --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
BASELINE_ROOT = REPO_ROOT / "test" / "story" / "fixtures" / "content-baseline"
SOURCE_UNITS = REPO_ROOT / "doc/extensions/skills/story/scripts/source-units.mjs"

#: 规范化口径与 story-build 的 `norm` 一致——两处不同会让「找得到」的判定各说各话。
_NORM_RE = re.compile(r"[\s，。、；：!?！？（）()「」【】]")


def norm(text: str) -> str:
    return _NORM_RE.sub("", str(text or ""))


def enumerate_units(story_path: Path) -> list[dict]:
    """把基线 story 当作第五份材料切成来源单元。

    复用生产链的枚举器而不是自己写一套：自己写的那套一定会和它漂移，
    到时候「基线里有这条」就成了两个脚本各执一词。
    """
    script = (
        "import {pathToFileURL} from 'node:url';"
        "import * as fs from 'node:fs';"
        "const m=await import(pathToFileURL(process.argv[1]).href);"
        "const text=fs.readFileSync(process.argv[2],'utf-8');"
        "console.log(JSON.stringify(m.enumerateUnits(text,'BASELINE',{})));")
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, "--",
         str(SOURCE_UNITS), str(story_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"[baseline] 枚举跑不起来：{proc.stderr[:300]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def fragments(text: str) -> list[str]:
    """正文切片，与生产链的 `contentFragments` 同口径。

    **按 `｜` 切**：表行单元的正文是用它把单元格拼起来的，整行去找永远找不到
    ——新 story 里那几个格子会被拆开写进不同的句子，而它们各自都在。
    口径不一致的代价是这个工具报一堆假缺失，人会先不信它，再不看它。
    """
    return [f for f in (norm(p) for p in str(text or "").split("｜")) if len(f) >= 8]


def covered(unit: dict, story: str, story_norm: str) -> bool:
    """这条基线单元在新 story 里有没有落点。

    两条路都算：token 逐字命中，或正文片段命中。与生产链的机器落点同口径——
    机器核不到的那些，由裁决者的三张表管，不在这里判死。
    """
    for token in unit.get("tokens") or []:
        if token and token in story:
            return True
    pieces = fragments(unit.get("text") or "")
    if not pieces:
        # 短到切不出片段的单元（「命中六项细节：」这类）整体去找，不然它永远算缺失
        whole = norm(unit.get("text") or "")
        return bool(whole) and whole in story_norm
    return any(piece in story_norm for piece in pieces)


def shape(text: str) -> dict:
    lines = text.split("\n")
    return {
        "行数": len([l for l in lines if l.strip()]),
        "章": sum(1 for l in lines if l.startswith("## ")),
        "表行": sum(1 for l in lines if l.strip().startswith("|")),
        "围栏图": sum(1 for l in lines if l.strip().startswith("```") and len(l.strip()) > 3),
        "图片": sum(l.count("![") for l in lines),
    }


def compare(new_story: Path, baseline: str) -> dict:
    base_story = BASELINE_ROOT / baseline / "AR" / "story.md"
    if not base_story.is_file():
        raise SystemExit(f"[baseline] 没有这份基线：{base_story}")
    new_text = new_story.read_text(encoding="utf-8")
    new_norm = norm(new_text)

    units = [u for u in enumerate_units(base_story) if not u.get("machine_facing")]
    missing = [u for u in units if not covered(u, new_text, new_norm)]

    # **天花板**：拿基线去对照它自己。达不到 1.0 是正常的——有些单元短到切不出
    # 可核片段（「分享只读」这类），机器在**任何**文档里都核不到它们，生产链里
    # 它们归裁决者的三张表管。不报这个数，人会把 0.95 当成「丢了 5%」。
    base_text = base_story.read_text(encoding="utf-8")
    base_norm = norm(base_text)
    ceiling_missing = [u for u in units if not covered(u, base_text, base_norm)]
    ceiling = round((len(units) - len(ceiling_missing)) / len(units), 3) if units else None

    return {
        "baseline": baseline,
        "new_story": str(new_story),
        "基线单元": len(units),
        "有落点": len(units) - len(missing),
        "缺失": len(missing),
        "覆盖率": round((len(units) - len(missing)) / len(units), 3) if units else None,
        "机器可核上限": ceiling,
        "上限外的": len(ceiling_missing),
        "缺失清单": [
            {"来源行": u.get("line"), "类型": u.get("kind"),
             "正文": (u.get("text") or "")[:80],
             "token": (u.get("tokens") or [])[:3]}
            for u in missing
        ],
        "形态": {"基线": shape(base_story.read_text(encoding="utf-8")), "新": shape(new_text)},
    }


def render(result: dict) -> str:
    base = result["形态"]["基线"]
    new = result["形态"]["新"]
    lines = [
        f"[baseline_coverage] 对照 {result['baseline']}（只报数，不判达标）",
        f"  基线单元 {result['基线单元']}｜有落点 {result['有落点']}｜"
        f"缺失 {result['缺失']}｜覆盖率 {result['覆盖率']}",
        f"  机器可核上限 {result['机器可核上限']}"
        f"（{result['上限外的']} 条短到切不出可核片段，在任何文档里都核不到，归裁决者）",
        "",
        "  ── 形态（新 < 基线 就是降级）──",
        f"    {'项':<6} {'基线':>6} {'新':>6}",
    ]
    for key in ("行数", "章", "表行", "围栏图", "图片"):
        flag = "  ← 少了" if new[key] < base[key] else ""
        lines.append(f"    {key:<6} {base[key]:>6} {new[key]:>6}{flag}")
    if result["缺失清单"]:
        lines += ["", "  ── 基线里有、新 story 里找不到的 ──"]
        for item in result["缺失清单"][:20]:
            lines.append(f"    {item['来源行']:>4} 行 [{item['类型']}] {item['正文'][:60]}")
        if len(result["缺失清单"]) > 20:
            lines.append(f"    …… 另有 {len(result['缺失清单']) - 20} 条，用 --json 看全")
    lines += ["", "  机器只能说「这几条找不到」，说不了「丢掉要不要紧」——那要人看。",
              "  机器核不到的那些由裁决者的三张表管，不在这里判死。"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="新 story 与内容基线的对照（只报数）")
    ap.add_argument("story", help="新写的 AR/story.md 路径")
    ap.add_argument("--baseline", required=True,
                    help=f"基线名（{'/'.join(sorted(p.name for p in BASELINE_ROOT.iterdir() if p.is_dir()))}）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    result = compare(Path(args.story), args.baseline)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
