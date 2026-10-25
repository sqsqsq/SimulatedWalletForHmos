"""机制预算多维统计：AGENTS §5 计量的唯一入口，只读、只报不判。

用法（仓根）：
  python test/scripts/budget_report.py [--base <ref>] [--to <ref>|worktree] [--package <包 id>]
                                       [--depth N] [--out <目录>]
--base 缺省取台账 release.baseline_ref；--to 缺省 worktree（含未提交改动，identity 里列出）。
--out 给了就写 budget-report.json 与 budget-report.md，否则只打印 Markdown 摘要。

指标名与口径（AGENTS §5 引用这里的名字）：
  identity  对象身份：两端 SHA、工作区改动、计量/交付文件数与摘要
  totals    两端有效行，按类型、模块、文件
  endpoint  base→to 逐文件一次差分的 G/X——整版判定用它
  series    base→to 每个改了 extensions 的 first-parent 提交（工作区作最后一段）相邻差分
  invested  series 之和；churn = invested − endpoint——包的 R 用包起点以来的 invested
  peak      series 各点（含两端）按类型与总量各自的最大值及发生点
  package   包起点→to 的 invested 与 endpoint；X 再分「退出上一正式版保留行 / 退出本版新增行」
  control   整版 G 对上限、各类型实测对台账、包 R 分级与确认、责任项实测对预测——只报告
G 是新增或改写的有效行，X 是删除或被改写的有效行；relocated 是 G 里同文件删掉又原样（忽略首尾空白）加回的行，即移动或改缩进。
有效行算法与计量范围取 test/tests/test_mechanism_budget.py，这里不另写。
"""
from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import yaml

TOOL_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOL_REPO / "test" / "tests"))
import test_mechanism_budget as meter  # noqa: E402

CATS = ("prompts_md", "hooks_mjs", "scripts_mjs", "scripts_py", "data")
WORKTREE = "worktree"
#: AGENTS §5 分级表：上界（含）→ 档位与必须动作
BANDS = ((100, "≤100%", "按方案实现并正常评审"),
         (125, "100–125%", "实施者自查并记录差额与原因"),
         (150, "125–150%", "交方案制定者或指定 reviewer 具名确认后继续"),
         (None, ">150%", "reviewer 整体反思，人工确认后继续"))


class ReportError(Exception):
    pass


def git(repo: Path, *args: str, binary: bool = False):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if r.returncode:
        raise ReportError(f"git {' '.join(args)} 失败：{r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


class Snapshot:
    """一个对象（提交或工作区）的 extensions：rel → 字节；有效行按需取。"""

    def __init__(self, label: str, files: dict[str, bytes]):
        self.label, self.files, self._rows = label, files, {}

    def counted(self) -> list[str]:
        return sorted(r for r in self.files if meter.classify_rel(r))

    def rows(self, rel: str) -> list[str]:
        if rel not in self._rows:
            data = self.files.get(rel)
            self._rows[rel] = [] if data is None else meter.effective_rows(
                Path(rel).suffix, data.decode("utf-8", "replace"))
        return self._rows[rel]


def snapshot(repo: Path, ref: str, cache: dict) -> Snapshot:
    """读一个对象的 extensions，字节统一成 LF：git archive 按 core.autocrlf 转换换行，工作区也可能是 CRLF，不归一就会把没改的文件当成改了。"""
    if ref in cache:
        return cache[ref]
    files = {}
    if ref == WORKTREE:
        for rel in git(repo, "ls-files", "-co", "--exclude-standard", "-z", "--", "extensions").split("\0"):
            p = repo / rel
            if rel and p.is_file():
                files[rel[len("extensions/"):]] = lf(p.read_bytes())
    else:
        tar = git(repo, "archive", "--format=tar", ref, "extensions", binary=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            for m in tf.getmembers():
                if m.isfile():
                    files[m.name[len("extensions/"):]] = lf(tf.extractfile(m).read())
    cache[ref] = Snapshot(ref, files)
    return cache[ref]


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def module_of(rel: str, depth: int | None) -> str:
    parts = rel.split("/")[:-1]
    if depth is not None:
        parts = parts[:depth]
    return "/".join(parts) or "(根)"


def file_diff(a: list[str], b: list[str]) -> dict:
    """一个文件两端有效行的差分：G/X、relocated，以及 X 落在旧端的哪些行（供来源拆分）。"""
    g = x = 0
    removed, added, gone = [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        x += i2 - i1
        g += j2 - j1
        gone.extend(range(i1, i2))
        removed += [ln.strip() for ln in a[i1:i2]]
        added += [ln.strip() for ln in b[j1:j2]]
    pool, relocated = list(removed), 0
    for ln in added:
        if ln in pool:
            pool.remove(ln)
            relocated += 1
    return {"G": g, "X": x, "relocated": relocated, "gone": gone}


def retained_rows(base: Snapshot, start: Snapshot, rel: str) -> set[int]:
    """start 里与版本基线逐行对齐（equal）的行号：退出它们算「退出上一正式版保留行」。"""
    keep = set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=base.rows(rel), b=start.rows(rel), autojunk=False).get_opcodes():
        if op == "equal":
            keep.update(range(j1, j2))
    return keep


def zero() -> dict:
    return {"G": 0, "X": 0, "relocated": 0, "files_added": 0, "files_removed": 0, "files_changed": 0}


def add(acc: dict, d: dict) -> None:
    for k, v in d.items():
        if isinstance(v, int):
            acc[k] = acc.get(k, 0) + v


def compare(a: Snapshot, b: Snapshot, depth: int | None, scopes: dict | None = None,
            origin_base: Snapshot | None = None) -> dict:
    """两端逐文件差分，按类型 / 模块 / 文件 / 责任项汇总；给 origin_base 时再拆 X 的来源。"""
    by_cat = {c: zero() for c in CATS}
    by_mod, by_scope, files = {}, {}, {}
    for rel in sorted(set(a.counted()) | set(b.counted())):
        cat = meter.classify_rel(rel)
        if a.files.get(rel) == b.files.get(rel):
            continue
        d = file_diff(a.rows(rel), b.rows(rel))
        status = "added" if rel not in a.files else "removed" if rel not in b.files else "changed"
        row = {"category": cat, "status": status, "G": d["G"], "X": d["X"], "relocated": d["relocated"],
               "files_added": status == "added", "files_removed": status == "removed",
               "files_changed": status == "changed" and bool(d["G"] or d["X"])}
        if origin_base is not None:
            keep = retained_rows(origin_base, a, rel)
            row["X_retained"] = sum(1 for i in d["gone"] if i in keep)
            row["X_version_added"] = d["X"] - row["X_retained"]
        row = {k: int(v) if isinstance(v, bool) else v for k, v in row.items()}
        if not (row["G"] or row["X"] or status != "changed"):
            continue
        files[rel] = row
        add(by_cat[cat], row)
        add(by_mod.setdefault(module_of(rel, depth), zero()), row)
        if scopes is not None:
            hit = [n for n, globs in scopes.items() if any(fnmatch.fnmatch(rel, g) for g in globs)]
            name = hit[0] if len(hit) == 1 else "(共享)" if hit else "(未归属)"
            add(by_scope.setdefault(name, zero()), row)
    total = zero()
    for c in CATS:
        add(total, by_cat[c])
    out = {"total": total, "by_category": by_cat, "by_module": dict(sorted(by_mod.items())), "files": files}
    if scopes is not None:
        out["by_scope"] = by_scope
    return out


def sizes(s: Snapshot, depth: int | None) -> dict:
    by_cat, by_mod = {c: 0 for c in CATS}, {}
    for rel in s.counted():
        n = len(s.rows(rel))
        by_cat[meter.classify_rel(rel)] += n
        by_mod[module_of(rel, depth)] = by_mod.get(module_of(rel, depth), 0) + n
    return {"total": sum(by_cat.values()), "by_category": by_cat, "by_module": dict(sorted(by_mod.items()))}


def digest(s: Snapshot, rels: list[str]) -> str:
    h = hashlib.sha256()
    for r in rels:
        h.update(r.encode() + b"\0" + hashlib.sha256(s.files[r]).digest())
    return h.hexdigest()


def resolve(repo: Path, ref: str) -> str:
    return WORKTREE if ref == WORKTREE else git(repo, "rev-parse", "--verify", ref + "^{commit}").strip()


def chain(repo: Path, base: str, to: str, cache: dict) -> list[str]:
    """base 之后改了 extensions 的 first-parent 提交；to 是工作区且与 HEAD 不同时再加一段。"""
    head = resolve(repo, "HEAD") if to == WORKTREE else to
    refs = [ln for ln in git(repo, "rev-list", "--first-parent", "--reverse", f"{base}..{head}",
                             "--", "extensions").split() if ln]
    if head not in refs and head != base:
        refs.append(head)   # 端点本身没改 extensions 时也作为一点，保证 series 收在 to
    if to == WORKTREE and snapshot(repo, WORKTREE, cache).files != snapshot(repo, head, cache).files:
        refs.append(WORKTREE)
    return refs


def series(repo: Path, base: str, to: str, cache: dict, depth: int | None):
    points, steps, prev = [], [], snapshot(repo, base, cache)
    points.append({"at": base, **sizes(prev, depth)})
    for ref in chain(repo, base, to, cache):
        cur = snapshot(repo, ref, cache)
        d = compare(prev, cur, depth)
        subject = "" if ref == WORKTREE else git(repo, "show", "-s", "--format=%s", ref).strip()
        steps.append({"at": ref, "subject": subject, **{k: d[k] for k in ("total", "by_category", "by_module")}})
        points.append({"at": ref, **sizes(cur, depth)})
        prev = cur
    inv = {"total": zero(), "by_category": {c: zero() for c in CATS}, "by_module": {}}
    for s in steps:
        add(inv["total"], s["total"])
        for c in CATS:
            add(inv["by_category"][c], s["by_category"][c])
        for m, v in s["by_module"].items():
            add(inv["by_module"].setdefault(m, zero()), v)
    peak = {"total": max(points, key=lambda p: p["total"]),
            "by_category": {c: max(points, key=lambda p: p["by_category"][c]) for c in CATS}}
    peak = {"total": {"value": peak["total"]["total"], "at": peak["total"]["at"]},
            "by_category": {c: {"value": p["by_category"][c], "at": p["at"]} for c, p in peak["by_category"].items()}}
    return steps, inv, peak


def churn(inv: dict, end: dict) -> dict:
    return {k: inv["total"][k] - end["total"][k] for k in ("G", "X")}


def band(ratio: float) -> tuple[str, str]:
    for top, name, action in BANDS:
        if top is None or ratio * 100 <= top:
            return name, action
    raise AssertionError


def control(ledger: dict, base_sha: str, to_snap: Snapshot, endpoint: dict, peak: dict,
            pkg: dict | None, repo: Path, depth: int | None) -> dict:
    out = {"note": "机械对照，只报不判；必要性、替代方案与旧路径退出由 reviewer 按 AGENTS §5 判断"}
    ver = ledger.get("release") or {}
    if ver.get("baseline_ref") and resolve(repo, str(ver["baseline_ref"])) == base_sha:
        cap = ver.get("control_g")
        out["version"] = {"id": ver.get("id"), "G": endpoint["total"]["G"], "control_g": cap,
                          "within": cap is None or endpoint["total"]["G"] <= cap}
    closed = str((ledger.get("requirement") or {}).get("status")) == "closed"
    now = sizes(to_snap, depth)
    rows = {}
    for c in CATS:
        e = (ledger.get("categories") or {}).get(c) or {}
        bound = e.get("target") if closed else e.get("interim_ceiling")
        rows[c] = {"actual": now["by_category"][c], "interim_ceiling": e.get("interim_ceiling"),
                   "target": e.get("target"), "bound_in_force": "target" if closed else "interim_ceiling",
                   "within": bound is None or now["by_category"][c] <= bound,
                   "peak": peak["by_category"][c]["value"]}
    t = ledger.get("total") or {}
    bound = t.get("target") if closed else t.get("interim_ceiling")
    rows["total"] = {"actual": now["total"], "interim_ceiling": t.get("interim_ceiling"), "target": t.get("target"),
                     "bound_in_force": "target" if closed else "interim_ceiling",
                     "within": bound is None or now["total"] <= bound, "peak": peak["total"]["value"]}
    out["categories"] = rows
    if pkg:
        out["package"] = pkg["control"]
    return out


def package_report(repo: Path, ledger: dict, pid: str, to: str, base: Snapshot, cache: dict,
                   depth: int | None) -> dict:
    entry = next((p for p in ledger.get("packages") or [] if p.get("id") == pid), None)
    if entry is None:
        raise ReportError(f"台账 packages 里没有 id={pid}")
    start = resolve(repo, str(entry["start_ref"]))
    scopes = entry.get("scopes") or None
    end = compare(snapshot(repo, start, cache), snapshot(repo, to, cache), depth, scopes, origin_base=base)
    steps, inv, _ = series(repo, start, to, cache, depth)
    if scopes:   # 责任项按文件归属，逐段累加
        inv["by_scope"] = compare_scopes_series(repo, start, to, cache, depth, scopes)
    approved = entry.get("approved_g")
    ctl = {"approved_g": approved, "invested_G": inv["total"]["G"]}
    if approved:
        ratio = inv["total"]["G"] / approved
        name, action = band(ratio)
        need = {"125–150%": ("125–150%", ">150%"), ">150%": (">150%",)}.get(name, ())
        got = [c for c in entry.get("confirmations") or [] if str(c.get("band")) in need]
        ctl.update({"R": round(ratio, 4), "band": name, "action": action,
                    "confirmations": got, "confirmation_missing": bool(need) and not got})
    pred = entry.get("predicted") or {}
    if pred:
        ctl["predicted_vs_actual"] = {
            k: {"predicted": v, "invested": (inv["by_scope"].get(k, {}) if k != "total" and scopes else inv["total"])}
            for k, v in pred.items()}
    return {"id": pid, "start_ref": start, "approved_g": approved, "endpoint": end, "invested": inv,
            "churn": churn(inv, end), "series": steps, "control": ctl}


def compare_scopes_series(repo, start, to, cache, depth, scopes) -> dict:
    acc, prev = {}, snapshot(repo, start, cache)
    for ref in chain(repo, start, to, cache):
        cur = snapshot(repo, ref, cache)
        for k, v in compare(prev, cur, depth, scopes)["by_scope"].items():
            add(acc.setdefault(k, zero()), v)
        prev = cur
    return acc


def build(repo: Path, ledger_path: Path, base_ref: str | None, to_ref: str, pid: str | None,
          depth: int | None) -> dict:
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
    base_ref = base_ref or (ledger.get("release") or {}).get("baseline_ref")
    if not base_ref:
        raise ReportError("没有 --base，台账也没有 release.baseline_ref")
    cache: dict = {}
    base, to = resolve(repo, str(base_ref)), resolve(repo, to_ref)
    a, b = snapshot(repo, base, cache), snapshot(repo, to, cache)
    endpoint = compare(a, b, depth)
    steps, inv, peak = series(repo, base, to, cache, depth)
    head = resolve(repo, "HEAD")
    dirty = []
    if to == WORKTREE:
        h = snapshot(repo, head, cache)
        dirty = sorted(r for r in set(b.files) | set(h.files) if b.files.get(r) != h.files.get(r))
    counted, delivered = b.counted(), sorted(b.files)
    identity = {
        "base": base, "to": to, "head": head,
        "uncommitted": [f"extensions/{r}" for r in dirty],
        "uncommitted_counted": [f"extensions/{r}" for r in dirty if meter.classify_rel(r)],
        "counted_files": {"total": len(counted), "by_category": {
            c: sum(1 for r in counted if meter.classify_rel(r) == c) for c in CATS}, "sha256": digest(b, counted)},
        "delivered_files": {"total": len(delivered), "sha256": digest(b, delivered)},
        "excluded_files": len(delivered) - len(counted),
    }
    totals = {"base": sizes(a, depth), "to": sizes(b, depth)}
    totals["net"] = totals["to"]["total"] - totals["base"]["total"]
    pkg = package_report(repo, ledger, pid, to, a, cache, depth) if pid else None
    report = {"identity": identity, "totals": totals, "endpoint": endpoint, "series": steps,
              "invested": inv, "churn": churn(inv, endpoint), "peak": peak}
    if pkg:
        report["package"] = pkg
    report["control"] = control(ledger, base, b, endpoint, peak, pkg, repo, depth)
    check(report)
    return report


def check(r: dict) -> None:
    """自洽：基线 + G − X = 当前；分项之和等于合计；逐提交累计与端点同样守恒。"""
    t, e = r["totals"], r["endpoint"]["total"]
    assert t["base"]["total"] + e["G"] - e["X"] == t["to"]["total"], "端点 G/X 与两端总量不守恒"
    assert t["base"]["total"] + r["invested"]["total"]["G"] - r["invested"]["total"]["X"] == t["to"]["total"]
    for part in ("by_category", "by_module"):
        for k in ("G", "X"):
            assert sum(v[k] for v in r["endpoint"][part].values()) == e[k], f"endpoint.{part}.{k} 之和不等于合计"
    assert sum(t["to"]["by_category"].values()) == t["to"]["total"]


def markdown(r: dict) -> str:
    i, t, e, inv = r["identity"], r["totals"], r["endpoint"], r["invested"]
    sh = lambda s: s if s == WORKTREE else s[:8]  # noqa: E731
    lines = [f"# 机制预算统计 {sh(i['base'])} → {sh(i['to'])}", "",
             f"- 计量文件 {i['counted_files']['total']}（摘要 {i['counted_files']['sha256'][:12]}），"
             f"交付文件 {i['delivered_files']['total']}（摘要 {i['delivered_files']['sha256'][:12]}），HEAD {i['head'][:8]}",
             f"- 未提交的计量文件：{', '.join(i['uncommitted_counted']) or '无'}", "",
             "## 按类型", "",
             "| 类型 | 基线 | 当前 | 净增 | endpoint G | 其中 relocated | endpoint X | 新增/删除文件 | invested G | invested X | peak（发生点） |",
             "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|"]
    for c in CATS:
        ec, ic, pk = e["by_category"][c], inv["by_category"][c], r["peak"]["by_category"][c]
        lines.append(f"| {c} | {t['base']['by_category'][c]} | {t['to']['by_category'][c]} | "
                     f"{t['to']['by_category'][c] - t['base']['by_category'][c]} | {ec['G']} | {ec['relocated']} | {ec['X']} | "
                     f"{ec['files_added']}/{ec['files_removed']} | {ic['G']} | {ic['X']} | {pk['value']}（{sh(pk['at'])}） |")
    et, it, pk = e["total"], inv["total"], r["peak"]["total"]
    lines += [f"| **合计** | {t['base']['total']} | {t['to']['total']} | {t['net']} | {et['G']} | {et['relocated']} | "
              f"{et['X']} | {et['files_added']}/{et['files_removed']} | {it['G']} | {it['X']} | {pk['value']}（{sh(pk['at'])}） |",
              "", f"churn（invested − endpoint）：G{r['churn']['G']} / X{r['churn']['X']}；series {len(r['series'])} 段。", "",
              "## 按模块（endpoint）", "", "| 模块 | 当前 | G | X | relocated |", "|---|---:|---:|---:|---:|"]
    for m, v in e["by_module"].items():
        lines.append(f"| {m} | {t['to']['by_module'].get(m, 0)} | {v['G']} | {v['X']} | {v['relocated']} |")
    c = r["control"]
    lines += ["", "## control（只报告）", ""]
    if "version" in c:
        v = c["version"]
        lines.append(f"- 整版 {v['id']}：endpoint G{v['G']} / 上限 G{v['control_g']}，{'在内' if v['within'] else '超出'}")
    for k, v in c["categories"].items():
        if not v["within"]:
            lines.append(f"- {k}：实测 {v['actual']} 超过 {v['bound_in_force']}")
    if all(v["within"] for v in c["categories"].values()):
        lines.append("- 各类型与总量都在台账当前生效的上限内")
    if "package" in r:
        p, pc = r["package"], r["package"]["control"]
        pe = p["endpoint"]["total"]
        lines += [f"- 包 {p['id']}（起点 {p['start_ref'][:8]}）：invested G{pc['invested_G']}"
                  + (f" / 分母 G{pc['approved_g']}，R={pc['R']:.1%}，{pc['band']}：{pc['action']}"
                     + ("；**缺具名确认**" if pc.get("confirmation_missing") else "") if pc.get("approved_g") else "")
                  + f"；endpoint G{pe['G']}/X{pe['X']}（X 退出保留行 {pe.get('X_retained', 0)}、退出本版新增行 {pe.get('X_version_added', 0)}）"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(TOOL_REPO))
    ap.add_argument("--ledger", help="缺省 <repo>/test/regression/mechanism-budget.yaml")
    ap.add_argument("--base")
    ap.add_argument("--to", default=WORKTREE)
    ap.add_argument("--package")
    ap.add_argument("--depth", type=int)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    ledger = Path(a.ledger) if a.ledger else repo / "test" / "regression" / "mechanism-budget.yaml"
    try:
        report = build(repo, ledger, a.base, a.to, a.package, a.depth)
    except ReportError as exc:
        print(f"[budget_report] {exc}", file=sys.stderr)
        return 2
    md = markdown(report)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "budget-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "budget-report.md").write_text(md, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
