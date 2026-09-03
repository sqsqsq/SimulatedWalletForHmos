# -*- coding: utf-8 -*-
"""Story 审查资格门驱动 —— 某个配置上的审查者认不认得出坏稿。

## 它问什么

不是「这一轮产物好不好」（那是 §9 的事），是**这个 `cli_config_id` 上的审查者有没有区分力**：
坏稿认不认得出来，好稿会不会被误判。结论按配置记，不能拿一个配置的结论代替另一个。

## 怎么跑

每份样本一个隔离工作区：把 story、它的材料、材料清单与已登记判断放到真实的目录形态里，
再起一个会话，把 **`story_reader_review` 这条判据的原文**交给它——任务文本从
`rules/spec-rules.overlay.yaml` 现读，不在这里复制一份：复制的那份会跟真源分叉，
届时测的就不是交付出去的那个任务了。

    python run_review_qualification.py --config <cli_config_id> --out <目录> [--base receipt]

## 它判什么、不判什么

**判**：这份样本有没有引出 `blocking_findings`——那是客观的（有没有非空条目）。
**不判**：报的那条对不对、点到没点到本族缺陷。那要读懂两句话说的是不是同一件事，
是维护者读输出后判的。脚本把每份的正文原样留在 `qualification.json` 里，供人核。

只在测试域跑，且只在用户启动的里程碑运行（`TEST.md` §9.1）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OVERLAY = REPO / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml"
PAIRS_DIR = (REPO / "test" / "story" / "fixtures" / "narrative-variants" / "pairs")
CONTRACT_REL = "doc/extensions/skills/story/contracts/story-chapters.json"
FLOW = REPO / "doc" / "extensions" / "skills" / "story" / "scripts" / "story_flow.py"
FEATURE = "AR90001"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
import make_narrative_variants as maker  # noqa: E402

#: 每个基底放一条已登记判断——「编造」那一族判的是「材料与已登记判断都不支持」，
#: 没有已登记判断时那句话就少了一半对照。内容取该基底 story 里真实写着的关键取舍。
DECISIONS = {
    "receipt": {
        "id": "render-on-device", "status": "settled",
        "title": "凭证在端侧渲染，不由服务端生成",
        "clarification": "**要定的事**：凭证由谁渲染。\n\n"
                         "**根据**：材料说明用户的场景之一是不愿再上传交易信息。\n\n"
                         "**结论与影响**：端侧渲染，代价是设备差异带来排版细节差异。",
        "decider": "需求负责人",
    },
    "queue": {
        "id": "subscribe-per-ticket", "status": "settled",
        "title": "按号订阅，不做按门店常驻订阅",
        "clarification": "**要定的事**：订阅的粒度。\n\n"
                         "**根据**：材料只描述了当前这一个号的提醒。\n\n"
                         "**结论与影响**：每次到店重新订阅，不长期保存用户与门店的关联。",
        "decider": "需求负责人",
    },
}


def review_task() -> str:
    """从 overlay 现读这条判据的原文 —— 交付出去的是哪一份，测的就得是哪一份。"""
    text = OVERLAY.read_text(encoding="utf-8")
    start = text.index("  story_reader_review:")
    rest = text[start:]
    end = re.search(r"\n  [a-z_]+:\n|\n[a-z_]+:\n", rest)
    block = rest[:end.start()] if end else rest
    return block


def build_workspace(root: Path, sample: dict) -> Path:
    """把样本放进真实的目录形态：story、材料、材料清单、已登记判断、章节合同。"""
    ws = root / sample["id"]
    feature_root = ws / "doc" / "features" / FEATURE
    (feature_root / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
    (feature_root / "RR").mkdir(parents=True, exist_ok=True)
    (feature_root / "AR" / "story.md").write_text(sample["text"], encoding="utf-8", newline="\n")
    (feature_root / "RR" / "prd.md").write_text(sample["material"], encoding="utf-8", newline="\n")
    (feature_root / "AR" / "story-src" / "decisions.json").write_text(
        json.dumps({"decisions": [DECISIONS[sample["base"]]]}, ensure_ascii=False, indent=2),
        encoding="utf-8", newline="\n")
    contract_dst = ws / CONTRACT_REL
    contract_dst.parent.mkdir(parents=True, exist_ok=True)
    contract_dst.write_text((REPO / CONTRACT_REL).read_text(encoding="utf-8"),
                            encoding="utf-8", newline="\n")
    # 界面图跟着进工作区：story 引用的是仓内既有落盘位置，图不在就成了断链
    assets_src = PAIRS_DIR / "assets"
    if assets_src.is_dir():
        assets_dst = feature_root / "assets"
        assets_dst.mkdir(parents=True, exist_ok=True)
        for png in sorted(assets_src.glob("*.png")):
            (assets_dst / png.name).write_bytes(png.read_bytes())
    (ws / TASK_FILE).write_text(task_document(sample), encoding="utf-8", newline="\n")
    # 材料清单由机制层命令按磁盘现状生成，与真实链路同一条路
    subprocess.run([sys.executable, str(FLOW), "round", "--feature", FEATURE,
                    "--project-root", str(ws)],
                   capture_output=True, text=True, encoding="utf-8", timeout=120)
    return ws


def reader_questions() -> str:
    """每章的读者问题与章级维度 —— 从合同现读，不在这里维护第二份。"""
    contract = json.loads((REPO / CONTRACT_REL).read_text(encoding="utf-8"))
    lines = []
    for chapter in contract["chapters"]:
        qs = chapter.get("questions") or []
        if qs:
            lines.append(f"- **{chapter['title']}**：" + "；".join(qs))
    dims = contract.get("verdicts", {}).get("chapter_dimensions") or []
    if dims:
        lines.append("")
        lines.append("章级质量维度：" + "；".join(str(d) for d in dims))
    return "\n".join(lines)


TASK_FILE = "REVIEW-TASK.md"


def task_document(sample: dict) -> str:
    """审查任务的全文：判据原文 + 读者问题 + 材料 + 已登记判断 + 待审稿。

    让它自己去工作区翻文件，预算会花在找文件上（实测一次 300 秒还没读完就超时），
    而资格门问的是**判断力**：同一份材料与稿子摆在面前，坏稿认不认得出来。
    所以把这些放进**一份**文件，它读一次就齐了。
    """
    decision = DECISIONS[sample["base"]]
    return "\n".join([
        "你是这一阶段的独立审查者。按下面这条判据审查这份归档叙事件，**只做这一件事**。",
        "",
        review_task(),
        "",
        "---",
        "",
        "## 每章要回答的读者问题（章节合同）",
        "",
        reader_questions(),
        "",
        "## 材料（这份需求手上的全部上游材料）",
        "",
        sample["material"],
        "",
        "## 已登记的判断",
        "",
        f"- {decision['title']}：{decision['clarification']}",
        "",
        "## 待审查的归档叙事件",
        "",
        sample["text"],
        "",
        "---",
        "",
        "现在给出结论。不要复述上面的内容，直接按约定的两个小节写。",
    ])


def prompt_for(sample: dict) -> str:
    """命令行只留一句指引 —— 任务全文在工作区的文件里。

    实测同一段长 prompt 走命令行参数时，一个模型收到了全文，另一个回
    「判据和归档叙事件都没提供」。它带着 story 全文，注定长；走文件就不受这个摆布。
    """
    return (f"读工作区根目录下的 `{TASK_FILE}`，按它里面那条判据审查它里面那份归档叙事件。"
            "**只做这一件事**，不要改任何文件，把结论直接写在回复里。")


def parse_blocking(text: str) -> tuple[bool, str]:
    """有没有非空的 blocking_findings —— 这一件是客观的，脚本只判这一件。

    找不到那个小节时按「没报」记，同时把正文留下：报告形态本身也是资格门要看的。
    """
    lowered = text.replace("：", ":")
    idx = lowered.find("blocking_findings")
    if idx < 0:
        return False, ""
    rest = lowered[idx + len("blocking_findings"):]
    nxt = rest.find("advisories")
    block = rest[:nxt] if nxt > 0 else rest[:1500]
    body = block.strip().lstrip(":").strip()
    # 「- （无）」「`[]（无）`」「**无**」「```yaml\n[]」都是空结论。装饰性符号一律剥掉再判，
    # 否则「没报」会被记成「报了」——那正好把区分力读反，据此做的每一步判断都是假的。
    head = body
    for _ in range(6):
        stripped = re.sub(r"^(```[a-z]*\s*|[\s\-*·—`>]+|[0-9]+[.、]\s*|[（(\[])", "",
                          head, count=1)
        if stripped == head:
            break
        head = stripped
    empty = (not head) or head.startswith("]") or bool(re.match(
        r"^(无|没有|none|n/a|na|空|暂无)", head, re.I))
    return (not empty), body[:600]


def run_one(sample: dict, ws: Path, entry: dict) -> dict:
    from tools.cli.api import CliClient
    from tools.cli.models import CliRunRequest

    client = CliClient(runtime_root=ws / ".qual-cli")
    started = time.time()
    result = client.run(CliRunRequest(
        cli=entry["name"], model=entry["model"], profile=entry.get("profile"),
        prompt=prompt_for(sample), cwd=ws,
        # 输入全内联，正常一轮就出结论；给足余量是为了区分「想得久」与「卡住了」
        soft_timeout_sec=420, hard_timeout_sec=600))
    elapsed = time.time() - started
    text = ""
    for attr in ("final_text", "output_text", "text"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            text = value
            break
    status = getattr(result, "status", "")
    has_blocking, excerpt = parse_blocking(text)
    # 「没跑出来」与「审查者看过之后没报」是两件事，混成一个 False 会把装置故障
    # 读成区分力缺口。超时、失败、空输出一律记 no_output，不进命中率。
    if status not in ("succeeded", "completed") or not text.strip():
        verdict = "no_output"
    else:
        verdict = "blocking" if has_blocking else "clean"
    return {
        "id": sample["id"], "family": sample["family"], "expect": sample["expect"],
        "base": sample["base"], "domain": sample["domain"],
        "cli_status": status, "verdict": verdict,
        "seconds": round(elapsed, 1), "output_chars": len(text),
        "has_blocking": has_blocking, "blocking_excerpt": excerpt, "output": text,
    }


def cli_entry(config_id: str) -> dict:
    import yaml
    cfg = yaml.safe_load((REPO / "test" / "story" / "config" / "test.yaml")
                         .read_text(encoding="utf-8"))
    for entry in cfg["cli"]["configurations"]:
        if entry["id"] == config_id:
            return entry
    raise SystemExit(f"config/test.yaml 里没有 cli_config_id={config_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Story 审查资格门")
    ap.add_argument("--config", required=True, help="cli_config_id")
    ap.add_argument("--out", required=True, help="工作区与结果的落点")
    ap.add_argument("--base", default=None, help="只跑这个基底的样本")
    ap.add_argument("--id", default=None, help="只跑这一个样本")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    entry = cli_entry(args.config)
    samples = maker.build(maker.load_pairs())
    chosen = [s for s in samples.values()
              if (args.base is None or s["base"] == args.base)
              and (args.id is None or s["id"] == args.id)]
    chosen.sort(key=lambda s: s["id"])
    if not chosen:
        raise SystemExit("没有匹配的样本")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "qualification.json"

    def flush(rows: list[dict]) -> None:
        """每份跑完就落一次盘——中途停掉时已跑的读数与正文都还在。"""
        summary.write_text(
            json.dumps({"cli_config_id": args.config, "model": entry["model"],
                        "samples": rows}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")

    # 续跑：已经有读数的样本不重跑，只补没跑过的那几份
    rows = []
    done = set()
    if summary.is_file():
        try:
            rows = json.loads(summary.read_text(encoding="utf-8")).get("samples", [])
            done = {r["id"] for r in rows if r.get("verdict") != "no_output"}
        except ValueError:
            rows, done = [], set()

    for i, sample in enumerate(chosen, 1):
        if sample["id"] in done:
            print(f"[{i}/{len(chosen)}] {sample['id']} 已有读数，跳过", file=sys.stderr, flush=True)
            continue
        ws = build_workspace(out_dir, sample)
        print(f"[{i}/{len(chosen)}] {sample['id']}（期望 {sample['expect']}）……",
              file=sys.stderr, flush=True)
        row = run_one(sample, ws, entry)
        rows = [r for r in rows if r["id"] != row["id"]] + [row]
        flush(rows)
        mark = {"blocking": "报了", "clean": "没报", "no_output": "没跑出来"}[row["verdict"]]
        print(f"    {row['cli_status']} {row['seconds']}s {row['output_chars']} 字 → {mark}",
              file=sys.stderr, flush=True)

    rows.sort(key=lambda r: r["id"])
    flush(rows)

    print("\n| 样本 | 族 | 期望 | 实际 | 秒 | 输出字数 |", file=sys.stderr)
    print("|---|---|---|---|---|---|", file=sys.stderr)
    for row in rows:
        print(f"| {row['id']} | {row['family']} | {row['expect']} | "
              f"{row['verdict']} | {row['seconds']} | {row['output_chars']} |",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
