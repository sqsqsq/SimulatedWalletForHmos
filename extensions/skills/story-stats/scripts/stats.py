"""使用统计：本仓 usage 与 Git 的确定性聚合（collect），以及候选报告的核对与发布（publish）。

collect 先经同包记录器对已有需求做一次有限对账（不创建需求或步骤），再固定 usage 字节快照与一个 Git HEAD，
后面所有数字只出自这两份快照；表格逐格格式化好写进 facts.json，模型照模板组织文字、表格原样取用。
publish 核对 pending 仍是这一次、facts 没变、候选报告里每张表与 facts 逐格相同且标题时间都在，
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


def step_rows(reqs: dict) -> list[list[str]]:
    rows = []
    for step in usage.STEPS:
        used = [r for r in reqs.values() if step in r["steps"]]
        done = [r for r in used if r["steps"][step].get("completed")]
        rows.append([step, str(len(used)), pct(len(used), len(reqs)), str(len(done)), pct(len(done), len(used))])
    return rows


def metrics(reqs: dict, linked: list[dict]) -> dict:
    return {"requirements": len(reqs), "developers": len({c["email"] for c in linked}), "commits": len(linked),
            "added": sum(c["added"] for c in linked), "deleted": sum(c["deleted"] for c in linked)}


def env_tables(reqs: dict) -> tuple[list[list[str]], list[list[str]], list[str]]:
    """初始化环境组（业务版本 + fw + ext + agent + model）与组内各步骤的每需求平均耗时（分钟）。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in reqs.values():
        groups[(label(r.get("version")), r.get("fw"), r.get("ext"), r.get("agent"), r.get("model"))].append(r)
    keys = sorted(groups, key=lambda k: (k[0] == UNKNOWN, k[0], *[str(x) for x in k[1:]]))
    envs, heads, avg = [], [], [[s] for s in usage.STEPS]
    for i, key in enumerate(keys, 1):
        gid, members = f"E{i}", groups[key]
        show = ["—" if v is None else v for v in key]
        envs.append([gid, *show, str(len(members))])
        heads.append(f"{gid}：{show[0]} / {show[4]}")
        for row, step in zip(avg, usage.STEPS):
            spent = [m["steps"][step]["spent"] for m in members if step in m["steps"]
                     and m["steps"][step].get("completed") and isinstance(m["steps"][step].get("spent"), int)]
            row.append(f"{sum(spent) / len(spent) / 60:.1f}" if spent else "—")
    return envs, avg, heads


def table(tid: str, header: list[str], rows: list[list[str]]) -> dict:
    return {"id": tid, "header": header, "rows": rows}


def collect(root: Path, version: str | None) -> dict:
    sync = usage.record(root, "reconcile")
    if sync["errors"]:
        raise StatsError("统计前对账没做成：" + "；".join(sync["errors"]))
    record = root / Path(*usage.CONTRACT["record"].split("/"))
    raw = record.read_bytes() if record.exists() else b""
    data = usage.load(record) if raw else {"schema": usage.SCHEMA, "requirements": {}}
    head = git(root, "rev-parse", "HEAD").strip()
    every = commits(root, head)
    all_reqs = data["requirements"]
    want = None if version is None else (None if version in ("未知", UNKNOWN) else version)
    reqs = all_reqs if version is None else {k: v for k, v in all_reqs.items() if v.get("version") == want}
    linked = [c for c in every if c["ticket"] in reqs]
    tables, headings = [], []
    m = metrics(reqs, linked)
    overview = [["使用 AI 框架的需求数", str(m["requirements"])], ["需求开发人数（去重）", str(m["developers"])],
                ["关联提交数", str(m["commits"])], ["关联提交新增行数", f"+{m['added']}"], ["关联提交删除行数", f"−{m['deleted']}"]]
    title = ("全版本总览" if version is None else f"业务版本 {label(want)}") + (f"（{span(linked)}）" if linked else "")
    headings.append(title)
    tables += [table("overview", ["指标", "统计结果"], overview), table("steps", STEP_HEAD, step_rows(reqs))]
    if version is None:
        vrows = []
        for v in sorted({r.get("version") for r in reqs.values()}, key=lambda x: (x is None, x or "")):
            sub = {k: r for k, r in reqs.items() if r.get("version") == v}
            sub_linked = [c for c in linked if c["ticket"] in sub]
            vm = metrics(sub, sub_linked)
            vrows.append([label(v), str(vm["requirements"]), str(vm["developers"]), str(vm["commits"]),
                          f"+{vm['added']}", f"−{vm['deleted']}"])
            head_v = label(v) + (f"（{span(sub_linked)}）" if sub_linked else "")
            headings.append(head_v)
            tables.append(table(f"steps:{label(v)}", STEP_HEAD, step_rows(sub)))
        tables.insert(2, table("versions", VERSION_HEAD, vrows))
    envs, avg, heads = env_tables(reqs)
    tables += [table("environments", ENV_HEAD, envs), table("durations", ["功能步骤", *heads], avg)]
    try:
        project = json.loads((root / "framework.config.json").read_text(encoding="utf-8-sig")).get("project_name")
    except (OSError, ValueError):
        project = None
    zone = datetime.now().astimezone().strftime("%z")
    return {"scope": {"version": version}, "head": head, "usage_sha256": hashlib.sha256(raw).hexdigest(),
            "project": project or root.name, "generated_at": when(datetime.now().astimezone()),
            "timezone": f"UTC{zone[:3]}:{zone[3:]}", "headings": headings, "tables": tables}


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


def md_tables(text: str) -> list[list[list[str]]]:
    """报告里的 Markdown 表：每张表的各行单元格（含表头，去掉分隔行）。"""
    out, cur = [], []
    for line in text.splitlines() + [""]:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                cur.append(cells)
            continue
        if cur:
            out.append(cur)
            cur = []
    return out


def report_problems(text: str, facts: dict) -> list[str]:
    """候选报告与 facts 的结构和数值核对：每张表逐格相同、所有表列数一致、标题时间都在。"""
    found = md_tables(text)
    bad = [f"有一张表的行列数不一致（表头 {t[0]}）" for t in found if len({len(r) for r in t}) != 1]
    # 按次数核：两个版本的表恰好相同时，各自都要写出来
    left = list(found)
    for t in facts["tables"]:
        want = [t["header"], *t["rows"]]
        if want in left:
            left.remove(want)
        else:
            bad.append(f"表「{t['id']}」没有按 facts 原样出现（表头 {' | '.join(t['header'])}，{len(t['rows'])} 行）")
    bad += [f"标题「{h}」不在报告里" for h in facts["headings"] if h not in text]
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
