# -*- coding: utf-8 -*-
"""从 good 基底生成成对样本 —— 资格夹具只保存「差在哪」，不保存十几份完整 story。

## 为什么是生成而不是落盘

一种缺陷至少要有两个变体（换业务名、换表达），六种缺陷就是十二份 bad 加两份 good。
把它们整份存进仓里，改一句基底就要同步改十四处，而它们本该只差声明的那一处；
更麻烦的是没人看得出某一份到底"坏在哪"——差异淹没在整篇文本里。

所以仓里只有两份 good 基底和一份 `pairs.json`：每个 bad 由基底加一组**精确编辑**得到。
编辑的锚点在基底里必须恰好出现一次，出现零次或多次即报错——那说明基底改过而定义没跟上，
生成出来的样本就不再是它自称的那种缺陷。

## 用法

    python make_narrative_variants.py --out <目录>            # 全部
    python make_narrative_variants.py --out <目录> --id fact_deleted_queue
    python make_narrative_variants.py --list                  # 只列有哪些，不写盘

输出目录下每个变体一份 `<id>.story.md`，另有 `<base>.good.story.md` 与 `<base>.material.md`。
`index.json` 记录每份的 family、expect、基底与业务域，供实验侧按问题族聚合。

**只在测试域跑**：它读的是评测夹具，被测流程不该知道它存在。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
PAIRS_DIR = REPO_ROOT / "test" / "story" / "fixtures" / "narrative-variants" / "pairs"
PAIRS = PAIRS_DIR / "pairs.json"


class VariantError(Exception):
    """夹具定义与基底对不上——生成不出可信样本，停下报出，不产出半份。"""


def load_pairs() -> dict:
    return json.loads(PAIRS.read_text(encoding="utf-8"))


def read_base(rel: str) -> str:
    """基底与材料都按 pairs.json 所在目录解析，行尾归一到 \\n。

    行尾归一是为了让编辑锚点只有一种写法：同一份文件在两台机器上落盘的行尾可能不同，
    锚点却是写死的。
    """
    path = (PAIRS_DIR / rel).resolve()
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def apply_edit(text: str, edit: dict, where: str) -> str:
    op = edit.get("op")
    if op in ("replace", "delete"):
        old = edit["old"]
        new = "" if op == "delete" else edit["new"]
        hits = text.count(old)
        if hits != 1:
            raise VariantError(
                f"{where}：锚点在基底里出现 {hits} 次（要求恰好一次）——"
                f"基底改过而变体定义没跟上。锚点开头是「{old[:30]}…」")
        return text.replace(old, new)
    if op == "replace_span":
        start = text.find(edit["from"])
        if start < 0:
            raise VariantError(f"{where}：找不到起点「{edit['from'][:30]}…」")
        end = text.find(edit["to"], start + len(edit["from"]))
        if end < 0:
            raise VariantError(f"{where}：起点之后找不到终点「{edit['to'][:30]}…」")
        return text[:start] + edit["new"] + text[end:]
    raise VariantError(f"{where}：不认识的编辑动作「{op}」")


def build(spec: dict) -> dict[str, dict]:
    """算出全部样本。不写盘——写盘前先让每一份都成立，不留半套。"""
    out: dict[str, dict] = {}
    for base_key, base in spec["bases"].items():
        out[f"{base_key}.good"] = {
            "id": f"{base_key}.good", "family": "good_baseline", "expect": "clean",
            "base": base_key, "domain": base["domain"],
            "text": read_base(base["story"]),
            "material": read_base(base["material"]),
        }
    for family in spec["families"]:
        for variant in family["variants"]:
            base = spec["bases"][variant["base"]]
            text = read_base(base["story"])
            for i, edit in enumerate(variant["edits"]):
                text = apply_edit(text, edit, f"{variant['id']} 第 {i + 1} 条编辑")
            if text == read_base(base["story"]):
                raise VariantError(f"{variant['id']}：编辑之后与基底一字不差，样本不成立")
            out[variant["id"]] = {
                "id": variant["id"], "family": family["key"], "expect": family["expect"],
                "base": variant["base"], "domain": base["domain"],
                "what": family["what"], "text": text,
                "material": read_base(base["material"]),
            }
    return out


def write(samples: dict[str, dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    index = []
    for key, sample in sorted(samples.items()):
        path = out_dir / f"{key}.story.md"
        path.write_text(sample["text"], encoding="utf-8", newline="\n")
        written.append(path)
        material = out_dir / f"{sample['base']}.material.md"
        if not material.exists():
            material.write_text(sample["material"], encoding="utf-8", newline="\n")
            written.append(material)
        index.append({k: sample[k] for k in ("id", "family", "expect", "base", "domain")
                      if k in sample})
    idx = out_dir / "index.json"
    idx.write_text(json.dumps({"samples": index}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    written.append(idx)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 story 审查的成对资格样本")
    ap.add_argument("--out", default=None, help="输出目录")
    ap.add_argument("--id", default=None, help="只生成这一个变体")
    ap.add_argument("--list", action="store_true", help="只列出有哪些样本")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    try:
        samples = build(load_pairs())
    except VariantError as exc:
        print(f"[make_narrative_variants] {exc}", file=sys.stderr)
        return 1

    if args.id:
        if args.id not in samples:
            print(f"[make_narrative_variants] 没有这个样本：{args.id}", file=sys.stderr)
            return 1
        samples = {args.id: samples[args.id]}

    if args.list or not args.out:
        for key, sample in sorted(samples.items()):
            print(f"{key}\t{sample['family']}\t{sample['expect']}\t{sample['domain']}")
        return 0

    written = write(samples, Path(args.out))
    print(f"[make_narrative_variants] 写出 {len(written)} 个文件到 {args.out}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
