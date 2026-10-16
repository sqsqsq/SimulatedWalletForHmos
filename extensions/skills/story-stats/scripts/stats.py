"""使用统计：本仓 usage 与 Git 的确定性聚合（collect），以及候选报告的核对与发布（publish）。

collect 先经同包记录器对已有需求做一次有限对账（不创建需求或步骤），再固定 usage 字节快照与一个 Git HEAD，
后面所有数字只出自这两份快照；表格逐格格式化好、连同可回查的原始计数（raw）与节结构（sections）写进 facts.json，模型照模板组织文字、表格原样取用。
publish 核对 pending 仍是这一次、facts 没变、候选报告的报告头与逐节标题等于 facts、每节下面恰好是该节的表且逐格相同，
然后先把候选改名为 report.md、再原子切换 current.json；旧请求被新请求替代时拒绝。

    python stats.py collect --project-root <目标仓> [--version <业务版本|未知>]
    python stats.py publish --project-root <目标仓> --analysis-id <collect 返回的 id>

stdout 一个结果 JSON；失败退出 1 并说清原因。只用标准库与 git。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "story" / "scripts" / "core"
sys.path.insert(0, str(CORE))
import usage  # noqa: E402
from materials import importer  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "report.md"
UNKNOWN = "未知版本"
TICKET = re.compile(r"^\[TicketNo:\]\s*((?:AR|DTS)[A-Za-z0-9]+)\s*$", re.M)
STEP_HEAD = ["功能步骤", "使用需求数", "使用占比", "步骤完成过的需求数", "步骤完成率"]
VERSION_HEAD = ["业务版本", "框架使用需求数", "需求开发人数", "关联提交数", "新增行数", "删除行数"]
ENV_HEAD = ["环境组", "业务版本", "Framework", "Extension", "agent", "模型", "需求数"]


class StatsError(Exception):
    """统计做不成：原因原样报给 Skill，不出一份看似完整的报告。"""


def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise StatsError(f"git {args[0]} 失败（{p.stderr.strip()[:300]}）：统计要在目标 Git 仓里跑")
    return p.stdout


def commits(root: Path, head: str) -> list[dict]:
    """HEAD 可达的普通提交（merge 不算，避免重复父分支改动）：作者、committer 时间、唯一 TicketNo、加减行数。"""
    out = git(root, "log", head, "--no-merges", "--numstat", "--format=%x1e%H%x1f%an%x1f%ae%x1f%cI%x1f%B%x1f")
    rows = []
    for chunk in out.split("\x1e")[1:]:
        sha, name, email, when, body, stat = chunk.split("\x1f")
        tickets = TICKET.findall(body)
        if len(tickets) != 1 or len(re.findall(r"^\[TicketNo:\]", body, re.M)) != 1:
            continue
        added = deleted = 0
        for line in stat.strip().splitlines():
            a, d, _ = (line.split("\t") + ["", ""])[:3]
            if a.isdigit() and d.isdigit():
                added, deleted = added + int(a), deleted + int(d)
        rows.append({"sha": sha, "name": name, "email": email.lower(), "at": datetime.fromisoformat(when),
                     "ticket": tickets[0], "added": added, "deleted": deleted})
    return list({r["sha"]: r for r in rows}.values())


def pct(n: int, d: int) -> str:
    return f"{n / d * 100:.1f}%" if d else "—"


def when(at: datetime) -> str:
    return at.astimezone().strftime("%Y-%m-%d %H:%M")


def span(rows: list[dict]) -> str:
    """关联提交覆盖的起止时间；没有关联提交为空串（不编时间）。"""
    return f"{when(min(r['at'] for r in rows))}—{when(max(r['at'] for r in rows))}" if rows else ""


def label(version: str | None) -> str:
    return UNKNOWN if version is None else version


def step_counts(reqs: dict) -> dict:
    """每步骤的原始计数：used（有节点的需求数）、completed（完成过的需求数）；分母分别是需求总数与 used。"""
    out = {}
    for step in usage.STEPS:
        used = [r for r in reqs.values() if step in r["steps"]]
        out[step] = {"used": len(used), "completed": sum(1 for r in used if r["steps"][step]["completed"])}
    return out


def step_rows(counts: dict, total: int) -> list[list[str]]:
    return [[step, str(c["used"]), pct(c["used"], total), str(c["completed"]), pct(c["completed"], c["used"])]
            for step, c in counts.items()]


def metrics(reqs: dict, linked: list[dict]) -> dict:
    return {"requirements": len(reqs), "developers": len({c["email"] for c in linked}), "commits": len(linked),
            "added": sum(c["added"] for c in linked), "deleted": sum(c["deleted"] for c in linked)}


def environments(reqs: dict) -> list[dict]:
    """初始化环境组（业务版本 + fw + ext + agent + model）；每步骤只取已完成且 spent 为整数的需求，留合计秒数与样本数。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in reqs.values():
        groups[(label(r["version"]), r["fw"], r["ext"], r["agent"], r["model"])].append(r)
    keys = sorted(groups, key=lambda k: (k[0] == UNKNOWN, k[0], *[str(x) for x in k[1:]]))
    out = []
    for i, key in enumerate(keys, 1):
        members, durations = groups[key], {}
        for step in usage.STEPS:
            spent = [m["steps"][step]["spent"] for m in members if step in m["steps"]
                     and m["steps"][step]["completed"] and isinstance(m["steps"][step]["spent"], int)]
            durations[step] = {"seconds": sum(spent), "samples": len(spent)}
        out.append({"id": f"E{i}", "key": ["—" if v is None else v for v in key], "requirements": len(members),
                    "durations": durations})
    return out


def table(tid: str, header: list[str], rows: list[list[str]]) -> dict:
    return {"id": tid, "header": header, "rows": rows}


def collect(root: Path, version: str | None) -> dict:
    sync = usage.record(root, "reconcile")
    if sync["errors"]:
        raise StatsError("统计前对账没做成：" + "；".join(sync["errors"]))
    # 摘要与所有数字出自同一份字节
    raw, data = usage.snapshot(root / Path(*usage.CONTRACT["record"].split("/")))
    head = git(root, "rev-parse", "HEAD").strip()
    every = commits(root, head)
    all_reqs = data["requirements"]
    want = None if version is None else (None if version in ("未知", UNKNOWN) else version)
    reqs = all_reqs if version is None else {k: v for k, v in all_reqs.items() if v["version"] == want}
    linked = [c for c in every if c["ticket"] in reqs]
    m, counts = metrics(reqs, linked), step_counts(reqs)
    raw_facts: dict = {"overview": m, "steps": counts, "versions": {}}
    overview = [["使用 AI 框架的需求数", str(m["requirements"])], ["需求开发人数（去重）", str(m["developers"])],
                ["关联提交数", str(m["commits"])], ["关联提交新增行数", f"+{m['added']}"], ["关联提交删除行数", f"−{m['deleted']}"]]
    title = ("全版本总览" if version is None else f"业务版本 {label(want)}") + (f"（{span(linked)}）" if linked else "")
    tables = [table("overview", ["指标", "统计结果"], overview), table("steps", STEP_HEAD, step_rows(counts, len(reqs)))]
    sections = [{"level": 2, "title": f"1. {title}", "tables": ["overview"]},
                {"level": 3, "title": "各功能使用程度", "tables": ["steps"]}]
    if version is None:
        vrows, subsections = [], []
        for v in sorted({r["version"] for r in reqs.values()}, key=lambda x: (x is None, x or "")):
            sub = {k: r for k, r in reqs.items() if r["version"] == v}
            sub_linked = [c for c in linked if c["ticket"] in sub]
            vm, vc = metrics(sub, sub_linked), step_counts(sub)
            raw_facts["versions"][label(v)] = {**vm, "steps": vc}
            vrows.append([label(v), str(vm["requirements"]), str(vm["developers"]), str(vm["commits"]),
                          f"+{vm['added']}", f"−{vm['deleted']}"])
            tables.append(table(f"steps:{label(v)}", STEP_HEAD, step_rows(vc, len(sub))))
            subsections.append({"level": 3, "title": label(v) + (f"（{span(sub_linked)}）" if sub_linked else ""),
                                "tables": [f"steps:{label(v)}"]})
        tables.append(table("versions", VERSION_HEAD, vrows))
        sections += [{"level": 2, "title": "2. 按业务版本汇总", "tables": ["versions"]}, *subsections]
    envs = environments(reqs)
    raw_facts["environments"] = envs
    avg = [[step, *(f"{e['durations'][step]['seconds'] / e['durations'][step]['samples'] / 60:.1f}"
                    if e["durations"][step]["samples"] else "—" for e in envs)] for step in usage.STEPS]
    tables += [table("environments", ENV_HEAD, [[e["id"], *e["key"], str(e["requirements"])] for e in envs]),
               table("durations", ["功能步骤", *(f"{e['id']}：{e['key'][0]} / {e['key'][4]}" for e in envs)], avg)]
    n = len([s for s in sections if s["level"] == 2])
    sections += [{"level": 2, "title": f"{n + 1}. 按业务版本统计初始化环境", "tables": ["environments"]},
                 {"level": 3, "title": "各初始化环境的步骤平均耗时（分钟 / 需求）", "tables": ["durations"]},
                 {"level": 2, "title": f"{n + 2}. 统计口径", "tables": []}]
    try:
        project = json.loads((root / "framework.config.json").read_text(encoding="utf-8-sig")).get("project_name")
    except (OSError, ValueError):
        project = None
    zone = datetime.now().astimezone().strftime("%z")
    scope = ("全版本：当前仓库全部 usage 需求" if version is None else f"业务版本 {label(want)} 的 usage 需求") \
        + "；Git 关联取当前分支 HEAD 可达历史"
    info = [["项目", project or root.name], ["统计范围", scope],
            ["报告时间", when(datetime.now().astimezone())], ["统一时区", f"UTC{zone[:3]}:{zone[3:]}"]]
    return {"scope": {"version": version}, "head": head, "usage_sha256": hashlib.sha256(raw).hexdigest(),
            "info": info, "sections": sections, "tables": tables, "raw": raw_facts}


# ---------------------------------------------------------------------------
# 输出目录与发布

def out_root(root: Path) -> Path:
    return root / importer.features_dir(root) / ".usage-stats"


def index(base: Path) -> dict:
    path = base / "current.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StatsError(f"{path.as_posix()} 读不了（{exc}）：它只是统计输出索引，删掉后重跑 collect") from exc
    if not isinstance(data, dict):
        raise StatsError(f"{path.as_posix()} 不是对象：它只是统计输出索引，删掉后重跑 collect")
    return data


def write_index(base: Path, data: dict) -> None:
    tmp = base / f".current.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, base / "current.json")


def outline(text: str) -> tuple[list[dict], list[str], list[str]]:
    """报告实际可见的结构：HTML 注释、围栏代码块、前导空白达 4 列的代码行（Tab 按 CommonMark 的 4 列制表位计）都不算；其余行里 1–3 级标题把正文分节，
    每节收它下面的合法 Markdown 表（表头 + 数据行）。同时返回这些可见行，报告头也只从中找。

    第一项是首个标题之前的部分。表要有与表头同列数的分隔行、每行列数相同。
    """
    parts, bad, shown = [{"level": 0, "title": None, "tables": []}], [], []
    block: list[tuple[int, str]] = []
    fenced = False
    text = re.sub(r"<!--.*?(?:-->|\Z)", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)  # 保留行号

    def close() -> None:
        if not block:
            return
        rows = [[c.strip() for c in s.strip("|").split("|")] for _, s in block]
        sep = len(rows) > 1 and len(rows[1]) == len(rows[0]) and all(re.fullmatch(r":?-{3,}:?", c) for c in rows[1])
        if not sep or len({len(r) for r in rows}) != 1:
            bad.append(f"第 {block[0][0]} 行起的表不是合法 Markdown 表（分隔行缺失或各行列数不一致）")
        else:
            parts[-1]["tables"].append([rows[0], *rows[2:]])
        block.clear()

    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        width = len(line[:len(line) - len(line.lstrip(" \t"))].expandtabs(4))   # 前导空白列宽，Tab 到 4 列制表位
        if width <= 3 and s.startswith(("```", "~~~")):
            close()
            fenced = not fenced
            continue
        if fenced or width >= 4:
            close()
            continue
        shown.append(s)
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            block.append((no, s))
            continue
        close()
        m = re.match(r"(#{1,3})\s+(.+?)\s*#*$", s)
        if m:
            parts.append({"level": len(m.group(1)), "title": m.group(2), "tables": []})
    close()
    return parts, bad, shown


def report_problems(text: str, facts: dict) -> list[str]:
    """候选报告按模板的可见结构核 facts：报告头每项一行且值相同；标题逐节等于 facts.sections（级别与原文）；
    每节下面恰好是该节的表、按顺序逐格相同；节外不放表。正文文字不核。"""
    parts, bad, shown = outline(text)
    for label, value in facts["info"]:
        got = [line.split("：**", 1)[1].strip() for line in shown if line.startswith(f"**{label}：**")]
        if got != [value]:
            bad.append(f"报告头「{label}」应只有一行「**{label}：** {value}」，报告里是 {got or '没有'}")
    if parts[0]["tables"]:
        bad.append("第一个标题之前有表：表只放在它所属的节下面")
    body = parts[1:]
    if body and body[0]["level"] == 1:
        if body[0]["tables"]:
            bad.append("报告大标题与第一节之间有表：表只放在它所属的节下面")
        body = body[1:]
    want = [("#" * s["level"]) + " " + s["title"] for s in facts["sections"]]
    got = [("#" * p["level"]) + " " + p["title"] for p in body]
    if got != want:
        at = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
        bad.append(f"标题与 facts.sections 不一致：第 {at + 1} 个应为「{want[at] if at < len(want) else '（没有了）'}」，"
                   f"报告里是「{got[at] if at < len(got) else '（没有了）'}」；全部标题依次为：{' / '.join(want)}")
        return bad
    tables = {t["id"]: [t["header"], *t["rows"]] for t in facts["tables"]}
    for part, section in zip(body, facts["sections"]):
        if part["tables"] != [tables[i] for i in section["tables"]]:
            bad.append(f"「{section['title']}」下应恰好是表 {' / '.join(section['tables']) or '（无）'}，"
                       f"按顺序、表头与每格逐字照抄 facts；报告里这一节有 {len(part['tables'])} 张表，与 facts 不同")
    return bad


def publish(root: Path, analysis_id: str) -> dict:
    base = out_root(root)
    if not re.fullmatch(r"[0-9T]+-[0-9a-f]{6}", analysis_id):
        raise StatsError(f"analysis_id {analysis_id} 不是本工具生成的格式")
    run = base / analysis_id
    with usage.locked(base / "current.json"):
        cur = index(base)
        report = run / "report.md"
        if cur.get("published") == analysis_id and report.is_file():
            return {"report": report.as_posix(), "analysis_id": analysis_id, "already": True}
        pending = cur.get("pending") or {}
        if pending.get("id") != analysis_id:
            raise StatsError(f"统计请求 {analysis_id} 已被新统计请求替代（当前待发布 {pending.get('id')}）：按新请求成文，旧候选不发布")
        try:
            facts_bytes = (run / "facts.json").read_bytes()
        except OSError as exc:
            raise StatsError(f"{run.name}/facts.json 读不到（{exc}）：重跑 collect") from exc
        if hashlib.sha256(facts_bytes).hexdigest() != pending.get("facts_sha256"):
            raise StatsError("facts.json 与 collect 时不一致：统计事实只由脚本写，重跑 collect")
        facts = json.loads(facts_bytes)
        draft = run / "report.draft.md"
        source = draft if draft.is_file() else report
        if not source.is_file():
            raise StatsError(f"候选报告 {draft.as_posix()} 不在：按模板写好后再发布")
        bad = report_problems(source.read_text(encoding="utf-8"), facts)
        if bad:
            raise StatsError("候选报告与 facts 不一致，未发布：" + "；".join(bad))
        if source == draft:
            os.replace(draft, report)
        write_index(base, {"pending": None, "published": analysis_id})
        # 只清本工具在输出根下建的、已不被 pending/published 引用的目录
        for old in base.iterdir():
            if old.is_dir() and old.name != analysis_id and old.resolve().parent == base.resolve():
                shutil.rmtree(old, ignore_errors=True)
    return {"report": report.as_posix(), "analysis_id": analysis_id}


def main() -> int:
    ap = argparse.ArgumentParser(description="使用统计（story-stats 内部入口）")
    ap.add_argument("action", choices=["collect", "publish"])
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--version", default=None)
    ap.add_argument("--analysis-id", default=None)
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    root = Path(args.project_root).resolve()
    try:
        if args.action == "publish":
            out = publish(root, str(args.analysis_id or ""))
        else:
            facts = collect(root, args.version)
            aid = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"
            base = out_root(root)
            raw = (json.dumps({"analysis_id": aid, **facts}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            # 建目录与切 pending 同在锁内：并发的 publish 清旧输出时不会删到还没登记的这一份
            with usage.locked(base / "current.json"):
                (base / aid).mkdir(parents=True)
                (base / aid / "facts.json").write_bytes(raw)
                cur = index(base)
                write_index(base, {"pending": {"id": aid, "facts_sha256": hashlib.sha256(raw).hexdigest()},
                                   "published": cur.get("published")})
            out = {"analysis_id": aid, "facts": (base / aid / "facts.json").as_posix(),
                   "draft": (base / aid / "report.draft.md").as_posix(), "template": TEMPLATE.as_posix()}
    except (StatsError, usage.UsageError, importer.ImportError_) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
