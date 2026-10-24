"""使用统计的事实层：一次 collect 从本仓 usage 与 Git 得出逐需求事实与汇总，报告由模型按模板写。

只读两样：一份 usage 字节快照与一个 Git HEAD，所有数字只出自它们；不补记 usage，不读需求目录、运行态与身份件——
最后一步由记录端在交付与提交之前收尾，没有 `doc/features/` 的代码仓同样能统计。需求按 usage 键里的编号与启动身份展示。
Git 归属看 usage 的变更：一笔提交新增了某个节点、或改了某个节点的记录内容，就是这个需求的提交（比的是提交前后的
JSON 对象，不看行数与排版）；merge 只把与每个父提交都不同的那部分算作它自己的改动。一笔提交带了几个需求，
每个需求都计整笔并标「混合提交」，汇总行数按需求累加，不按提交去重；人与提交的个数照常去重。事实写进系统临时目录下
本次独有的 `story-stats-*` 目录的 facts.json，同目录的 report.md 由模型写；目标工程里一个文件都不写。

    python stats.py collect --project-root <目标仓>

stdout 一个结果 JSON；失败退出 1 并说清原因。只用标准库与 git。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "story" / "scripts" / "core"
sys.path.insert(0, str(CORE))
import usage  # noqa: E402  只用它的合同与解析，不调采集或写入

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "report.md"


class StatsError(Exception):
    """统计做不成：原因原样报给 Skill，不出一份看似完整的事实。"""


def git(root: Path, *args: str, ok: bool = False) -> str | None:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        if ok:
            return None
        raise StatsError(f"git {args[0]} 失败（{p.stderr.strip()[:300]}）：统计要在目标 Git 仓里跑")
    return p.stdout


class History:
    """HEAD 可达历史里 usage 的每一版节点与每笔提交的变更量；同一提交只读一次。"""

    def __init__(self, root: Path, record: str):
        self.root, self.record, self.nodes, self.stats = root, record, {}, {}

    def at(self, sha: str) -> dict:
        """这一版的节点：这一版确实没有文件是空的；Git 查不了、文件在却读不出或不合合同，统计停下，不当作空表。"""
        if sha not in self.nodes:
            where = f"提交 {sha[:12]} 的 {self.record}"
            try:
                listed = git(self.root, "ls-tree", "--name-only", sha, "--", self.record)   # 按工程目录解析
                text = git(self.root, "show", f"{sha}:./{self.record}") if listed.strip() else None
            except StatsError as exc:
                raise StatsError(f"{where}查不了：{exc}") from exc
            try:
                self.nodes[sha] = usage.parse(text.encode("utf-8"), where)["requirements"] if text is not None else {}
            except usage.UsageError as exc:
                raise StatsError(f"{exc}——这一版读不出，它之后那笔提交改了哪些需求就算不出；"
                                 "本次不出统计，按提交号核对那一版的记录") from exc
        return self.nodes[sha]

    def numstat(self, sha: str) -> tuple[int, int]:
        """这笔提交自己的加减行（merge 是它相对各父提交的合并差异，不含父分支已有的改动）。"""
        if sha not in self.stats:
            added = deleted = 0
            for line in (git(self.root, "show", "--numstat", "--format=", sha) or "").splitlines():
                a, d = (line.split("\t") + ["", ""])[:2]
                if a.isdigit() and d.isdigit():
                    added, deleted = added + int(a), deleted + int(d)
            self.stats[sha] = (added, deleted)
        return self.stats[sha]

    def touched(self, head: str) -> list[dict]:
        """改过 usage 的提交，各带它新增或改动的节点键。"""
        out = []
        log = git(self.root, "log", "--full-history", "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%cI", head, "--", self.record)
        for line in log.splitlines():
            sha, parents, name, email, when = line.split("\x1f")
            after, before = self.at(sha), [self.at(p) for p in parents.split()] or [{}]
            keys = sorted(k for k, v in after.items() if all(b.get(k) != v for b in before))
            if keys:
                out.append({"sha": sha, "author": name, "email": email.lower(), "committed_at": when, "keys": keys})
        return out


def groups(rows: list[dict], *fields: str) -> list[dict]:
    """按几个字段分组数需求，组按字段值排序。"""
    count = Counter(tuple(r[f] for f in fields) for r in rows)
    return [{**dict(zip(fields, k)), "requirements": n} for k, n in sorted(count.items(), key=lambda kv: [str(v) for v in kv[0]])]


def collect(root: Path) -> dict:
    record = usage.CONTRACT["record"]
    raw, data = usage.snapshot(root / Path(*record.split("/")))      # 摘要与所有数字出自同一份字节
    git(root, "rev-parse", "--git-dir")
    head = (git(root, "rev-parse", "--verify", "-q", "HEAD", ok=True) or "").strip() or None
    tracked = head is not None and git(root, "cat-file", "-e", f"{head}:./{record}", ok=True) is not None
    history = History(root, record)
    commits = history.touched(head) if head else []
    rows, devs, shas = [], {}, set()
    for key, node in sorted(data["requirements"].items()):
        number, stamp = usage.KEY.fullmatch(key).groups()
        mine = []
        for c in (c for c in commits if key in c["keys"]):
            added, deleted = history.numstat(c["sha"])
            mine.append({"sha": c["sha"], "author": c["author"], "email": c["email"], "committed_at": c["committed_at"],
                         "added": added, "deleted": deleted, "mixed": len(c["keys"]) > 1})
            devs.setdefault(c["email"], c["author"])
            shas.add(c["sha"])
        gaps = [g for g, miss in (("文件未入库", not tracked), ("无提交", not mine),
                                  ("身份未知", node["agent"] is None and node["model"] is None)) if miss]
        rows.append({"key": key, "number": number, "stamp": stamp,
                     "committers": sorted({(c["author"], c["email"]) for c in mine}), "steps": node["steps"],
                     "agent": node["agent"], "model": node["model"], "ext": node["ext"], "fw": node["fw"],
                     "commits": mine, "added": sum(c["added"] for c in mine), "deleted": sum(c["deleted"] for c in mine),
                     "gaps": gaps})
    steps = {}
    for step in usage.STEPS:
        done = [r["steps"][step] for r in rows if step in r["steps"]]
        timed = [x["spent"] for x in done if "spent" in x]
        steps[step] = {"completed": len(done), "timed": len(timed), "spent_total": sum(timed),
                       **({"rounds_total": sum(x.get("rounds", 0) for x in done)} if step == usage.UPDATE else {})}
    return {"project": root.name, "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "head": head, "record": record, "record_tracked": tracked, "usage_sha256": hashlib.sha256(raw).hexdigest(),
            "requirements": rows,
            "summary": {"requirements": len(rows), "developers": [{"author": n, "email": e} for e, n in sorted(devs.items())],
                        "commits": len(shas), "added": sum(r["added"] for r in rows),
                        "deleted": sum(r["deleted"] for r in rows), "steps": steps,
                        "identities": groups(rows, "agent", "model"), "versions": groups(rows, "ext", "fw")}}


def run(root: Path) -> dict:
    """事实写进本次独有的临时目录（不与别的统计共用，不用锁）；报告由模型按模板写到同目录。"""
    facts = collect(root)
    folder = Path(tempfile.mkdtemp(prefix="story-stats-"))
    (folder / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"facts": (folder / "facts.json").as_posix(), "report": (folder / "report.md").as_posix(),
            "template": TEMPLATE.as_posix()}


def main() -> int:
    ap = argparse.ArgumentParser(description="使用统计事实（story-stats 内部入口）")
    ap.add_argument("action", choices=["collect"])
    ap.add_argument("--project-root", required=True)
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        out = run(Path(args.project_root).resolve())
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"统计事实写不进去（{exc}）：修好目录权限后重跑"}, ensure_ascii=False))
        return 1
    except (StatsError, usage.UsageError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
