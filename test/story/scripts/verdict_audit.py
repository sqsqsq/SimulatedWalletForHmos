# -*- coding: utf-8 -*-
"""裁决表的两件收口工具：随机抽样人核，以及删事实对抗的副本制备。

## 为什么要有它

裁决者一轮能交出上百条「讲清」。首跑那次 107 条全绿——三张表没有一条否定，
而产物是坏的。全绿本身不是证据：它既可能是「真的都讲清了」，也可能是橡皮章，
两者从表上看一模一样。

分两条路把它们分开：

- **抽样人核**（`sample`）：随机抽若干行交人复核「引文真在该章、引文确实陈述该单元的
  事实、裁决词与引文相称」。**随机种子记进报告**——不记种子，抽样就成了挑行。
- **删事实对抗**（`doctor`）：给它一份已知有缺口的副本，看它报不报。报不出来，
  这一轮所有「讲清」都不作数。

两条都只报数、不判 PASS/FAIL（G8）：机器能说的是「这 10 行的引文对不对得上」，
说不了「这一轮裁决可不可信」——那要人看。

用法：
    python verdict_audit.py sample <story-src 目录> [--n 10] [--seed 1234]
    python verdict_audit.py doctor <story-src 目录> <输出目录> [--facts 5] [--seed 1234]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path

UNIT_HEADER = "单元键"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def parse_unit_table(text: str) -> list[dict]:
    """切出逐单元表。**按表头认，不按标题认**——标题是给人读的，改一个字就找不着了。"""
    rows: list[dict] = []
    mode = False
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.replace("`", "").replace("*", "").strip()
                 for c in s.strip("|").split("|")]
        if re.fullmatch(r"[-: ]*", cells[0] or ""):
            continue
        if cells[0] == UNIT_HEADER:
            mode = True
            continue
        if cells[0] in ("章",):
            mode = False
            continue
        if mode and len(cells) >= 3:
            rows.append({"key": cells[0], "verdict": cells[1], "quote": cells[2]})
    return rows


#: 章标题的序号前缀。归档件写 `## 1. 背景`，落点记的是业务名「背景」——
#: 两边口径不一致，这里就会把每一行都判成「引文不在该章」，人会先不信它，再不看它。
_HEADING_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)+|\d+\.)\s*|^[A-Z][.、]\s*")


def normalize_heading(title: str) -> str:
    return _HEADING_PREFIX.sub("", str(title or "").strip()).strip()


def chapter_bodies(story: str) -> dict:
    out, cur, buf = {}, None, []
    for line in story.split("\n"):
        if line.startswith("## "):
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = normalize_heading(line[3:]), []
            continue
        if cur is not None:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return out


def cmd_sample(args: argparse.Namespace) -> int:
    src = Path(args.src)
    rows = parse_unit_table(read_text(src / "story-verdicts.md"))
    if not rows:
        print("[verdict_audit] 逐单元表是空的——没有可抽的行")
        return 1
    audit = json.loads(read_text(src / "audit.json") or '{"records":[]}')
    at_of = {r["key"]: r.get("at") for r in audit.get("records", [])}
    units = {u["key"]: u for u in
             json.loads(read_text(src / "source-units.json") or '{"units":[]}').get("units", [])}
    bodies = chapter_bodies(read_text(src.parent / "story.md"))

    seed = args.seed if args.seed is not None else random.randrange(10 ** 6)
    picked = random.Random(seed).sample(rows, min(args.n, len(rows)))

    print(f"[verdict_audit] 抽样人核｜随机种子 **{seed}**｜逐单元表共 {len(rows)} 行，抽 {len(picked)} 行")
    print("人核三件事：① 引文真在该章 ② 引文确实陈述该单元的事实 ③ 裁决词与引文相称")
    print("≥2 行对不上 = 判据面无效，与「删事实测试 0 未讲清」同等处置\n")
    print("| 单元 | 落点章 | 裁决 | 引文 | 机器预检 | 人判 |")
    print("|---|---|---|---|---|---|")
    for row in picked:
        at = at_of.get(row["key"]) or "—"
        body = bodies.get(at, "")
        quote = row["quote"]
        unit_text = (units.get(row["key"]) or {}).get("text") or ""
        flags = []
        if quote and quote not in body:
            flags.append("引文不在该章")
        if quote and quote in unit_text:
            flags.append("引文是材料原话（回声）")
        pre = "、".join(flags) if flags else "无异常"
        cell = quote.replace("|", "·")[:60]
        print(f"| {row['key']} | {at} | {row['verdict']} | {cell} | {pre} |  |")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """造一份已知有缺口的副本：删 5 个事实（≥2 个纯中文），再整章挖空一处。

    挖空不写成「本需求不涉及。」——那是合法的空章，判据会豁免它，测不出东西。
    """
    src, out = Path(args.src), Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(src, out / "story-src")
    story_path = src.parent / "story.md"
    story = read_text(story_path)
    units = json.loads(read_text(src / "source-units.json") or '{"units":[]}').get("units", [])
    audit = {r["key"]: r for r in
             json.loads(read_text(src / "audit.json") or '{"records":[]}').get("records", [])}

    rng = random.Random(args.seed if args.seed is not None else random.randrange(10 ** 6))
    seed = args.seed if args.seed is not None else rng.randrange(10 ** 6)

    def landed(unit: dict) -> bool:
        rec = audit.get(unit["key"]) or {}
        return bool(rec.get("at"))

    chinese = [u for u in units if landed(u) and not (u.get("tokens") or [])]
    tokened = [u for u in units if landed(u) and (u.get("tokens") or [])]
    removed = []
    text = story

    for pool, want in ((chinese, 2), (tokened, args.facts - 2)):
        rng.shuffle(pool)
        for unit in pool:
            if want <= 0:
                break
            frag = next((p.strip() for p in (unit.get("text") or "").split("｜")
                         if len(p.strip()) >= 8 and p.strip() in text), None)
            token = next((t for t in (unit.get("tokens") or []) if t in text), None)
            target = frag or token
            if not target:
                continue
            text = text.replace(target, "", 1)
            removed.append({"key": unit["key"], "kind": unit.get("kind"),
                            "pure_chinese": not (unit.get("tokens") or []),
                            "removed": target[:60]})
            want -= 1

    bodies = chapter_bodies(text)
    candidates = [t for t, b in bodies.items()
                  if len(b) > 200 and b.strip() != "本需求不涉及。"]
    blanked = rng.choice(candidates) if candidates else None
    if blanked:
        text = text.replace(bodies[blanked], "这一章的内容与本需求无关，留作占位。", 1)

    (out / "story.md").write_text(text, encoding="utf-8")
    manifest = {"seed": seed, "removed_facts": removed, "blanked_chapter": blanked,
                "source": str(story_path)}
    (out / "doctored.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[verdict_audit] 副本已生成：{out}")
    print(f"  随机种子 {seed}；删掉 {len(removed)} 个事实"
          f"（纯中文 {sum(1 for r in removed if r['pure_chinese'])} 个）"
          f"；挖空章「{blanked}」")
    print("  拿这份副本重跑裁决：逐单元应报出被删的那几条，"
          "挖空那章应在逐问被裁「没答」、逐章被裁「不达标」")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="裁决表的抽样人核与删事实对抗（只报数）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="随机抽若干行交人复核（种子记进报告）")
    s.add_argument("src", help="AR/story-src 目录")
    s.add_argument("--n", type=int, default=10)
    s.add_argument("--seed", type=int, default=None)
    s.set_defaults(func=cmd_sample)
    d = sub.add_parser("doctor", help="造一份已知有缺口的副本")
    d.add_argument("src", help="AR/story-src 目录")
    d.add_argument("out", help="副本输出目录")
    d.add_argument("--facts", type=int, default=5)
    d.add_argument("--seed", type=int, default=None)
    d.set_defaults(func=cmd_doctor)
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
