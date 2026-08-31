"""给**人**用：在本仓装好本地需求系统，让 `/story init <单号>` 直接跑得起来。

## 为什么需要它

`story.js` 把需求系统当成一个本地目录读（`STORY_REQUIREMENT_SYSTEM_DIR`，未设时回落
到 `test/story/requirement-system`）。**那个默认目录在本仓从来没有存在过**——CLI 测试
装置从不走这条回落，它每次把用例夹具复制到系统临时目录再显式指过去。于是这个洞只有
人手跑时才撞得上，报错是「需求系统不可达」，`doc/features/` 一个字节都不会落。

装完之后**不用设任何环境变量**：默认目标目录就是 `story.js` 的回落值。

## 为什么它在 test/story/scripts，不随扩展包交付

它要读 `cases/*/system/`，那里是 AR90006 这类**测试 Case 的单号**。机制层不得出现
测试特征——脚本一旦进 `doc/extensions/`，就把测试单号带进了交付物。真实工程有自己的
需求系统，`story.js`/`review.js`/`token.js` 三个替身本来就要换成自己的实现，
连带也就不需要这个脚本。

## 用法

    python test/story/scripts/bootstrap_local_story.py            # 装上全部预制单据
    python test/story/scripts/bootstrap_local_story.py --list     # 只看有哪些单，不写盘
    python test/story/scripts/bootstrap_local_story.py --only AR90006
    python test/story/scripts/bootstrap_local_story.py --reset    # 回出厂状态
    python test/story/scripts/bootstrap_local_story.py --verify AR90006   # 验证链路真的通
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_ROOT = REPO_ROOT / "test" / "story" / "cases"
EXT_SCRIPTS = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
STORY_JS = EXT_SCRIPTS / "story.js"
STORY_FLOW = EXT_SCRIPTS / "story_flow.py"

#: 默认目标目录。**必须与 `story.js` 的 `DEFAULT_SYSTEM_DIR` 一字不差**——
#: 一致，人才不用设环境变量。单测 `test_local_bootstrap.py` 跨语言比对这两个常量。
DEFAULT_SYSTEM_DIR = Path("test") / "story" / "requirement-system"
SYSTEM_DIR_ENV = "STORY_REQUIREMENT_SYSTEM_DIR"

#: `story.js` 认的单据数据文件——有它才算一张单。
DETAIL = "detail.json"


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", file=sys.stderr, flush=True)


def read_default_system_dir_from_story_js() -> Path | None:
    """从 `story.js` 里把那个默认目录读出来，用于核对两边没有漂移。

    读不到就返回 None——这是个核对手段，不是运行依赖；`story.js` 换了写法时
    脚本仍然能跑，只是核对失效，由单测去发现。
    """
    try:
        text = STORY_JS.read_text(encoding="utf-8")
    except OSError:
        return None
    hit = re.search(r"DEFAULT_SYSTEM_DIR\s*=\s*path\.join\(([^)]*)\)", text)
    if not hit:
        return None
    parts = re.findall(r"'([^']*)'", hit.group(1))
    return Path(*parts) if parts else None


def discover_tickets() -> dict[str, tuple[str, Path]]:
    """把所有用例夹具里的单据摊平成 `{单号: (case_id, 目录)}`。

    含已退役的用例——它的 `system/` 快照还完好，对人手试用一样是好素材；
    退役的是「这个场景还跑不跑自动测试」，不是「这些单据作废了」。

    单号撞车即报错停下：两张不同的单挤进同一个目录，谁覆盖谁全看扫描顺序，
    那种错事后没人看得出来。
    """
    tickets: dict[str, tuple[str, Path]] = {}
    for system_dir in sorted(CASES_ROOT.glob("*/system")):
        case_id = system_dir.parent.name
        for ticket_dir in sorted(p for p in system_dir.iterdir() if p.is_dir()):
            if not (ticket_dir / DETAIL).is_file():
                continue
            no = ticket_dir.name
            if no in tickets:
                raise SystemExit(
                    f"[bootstrap] 单号撞车：{no} 同时出现在 {tickets[no][0]} 与 {case_id}。"
                    "两张单挤进同一个目录，谁覆盖谁全看扫描顺序——先把其中一个改名")
            tickets[no] = (case_id, ticket_dir)
    return tickets


def ticket_summary(ticket_dir: Path) -> dict:
    try:
        detail = json.loads((ticket_dir / DETAIL).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        detail = {}
    return {
        "reqNo": detail.get("reqNo") or ticket_dir.name,
        "type": detail.get("type") or "?",
        "title": detail.get("title") or "",
        "files": sorted(p.name for p in ticket_dir.rglob("*") if p.is_file()),
    }


def resolve_system_dir(raw: str | None) -> Path:
    """定目标目录，并**拒绝就地作业**。

    指向 `cases/*/system/` 是最省事也最坏的做法：`story.js` 的 archive 会覆盖
    `<AR>/design.md`、往 `history/` 累积版本、往 `attachments/` 写评审件——
    夹具会被就地改写，而且一声不吭。
    """
    target = (REPO_ROOT / DEFAULT_SYSTEM_DIR) if not raw else Path(raw)
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()
    try:
        target.relative_to(CASES_ROOT)
    except ValueError:
        return target
    raise SystemExit(
        f"[bootstrap] 拒绝把需求系统指向 {target}："
        "cases/*/system 是用例夹具的正本，archive/restore 会就地改写它。"
        "换一个目录，脚本会把单据复制过去")


def seed(target: Path, tickets: dict[str, tuple[str, Path]],
         only: list[str], reset: bool) -> dict:
    """把单据复制过去。默认缺什么补什么，**每个跳过的都要出声**。

    静默跳过与「本来就没有」事后同形——人会以为装上了新版本，其实读的是上一轮
    archive 改写过的正文。
    """
    if only:
        unknown = [no for no in only if no not in tickets]
        if unknown:
            raise SystemExit(f"[bootstrap] 没有这些单：{unknown}；用 --list 看有哪些")
        tickets = {no: tickets[no] for no in only}
    if reset and target.exists():
        # 删之前把边界核清楚：必须在仓内、且不能是夹具
        target.relative_to(REPO_ROOT)
        resolve_system_dir(str(target))
        log(f"--reset：删掉 {target} 重建")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    installed, skipped = [], []
    for no, (case_id, src) in tickets.items():
        dst = target / no
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            out = dst / path.relative_to(src)
            if out.exists():
                skipped.append(str(out.relative_to(target)))
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
        installed.append({**ticket_summary(src), "from_case": case_id})
    return {"installed": installed, "skipped": skipped}


def leftover_features(tickets: dict) -> list[str]:
    """需求目录里还留着的同名 feature。

    `story.js` 用「已存在就跳过」的写法落材料，残留在那儿会让新一轮的材料**拉不进来**
    且不报错——人拿到的是半旧半新的工作区。所以默认拦下来，不替人删：那是人的产物。
    """
    features = REPO_ROOT / "doc" / "features"
    return sorted(no for no in tickets if (features / no).is_dir())


def verify(ticket: str, target: Path) -> dict:
    """在临时目录里把两条命令真跑一遍——回执里那句「可以跑了」的唯一证据。

    **不替人在本仓跑 `story_flow.py init`**：那两条命令是 `/story init` 的正文，
    替人跑掉就把「模型能不能自己走通初始化」这件事抹掉了，而那正是要观测的。
    这里只在 `%TEMP%` 里验证链路通不通，跑完删干净，仓里零残留。
    """
    node = shutil.which("node")
    if node is None:
        return {"ok": False, "error": "环境里没有 node，跳过链路验证"}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "probe"
        root.mkdir()
        shutil.copy2(REPO_ROOT / "framework.config.json", root / "framework.config.json")
        env = {**os.environ, SYSTEM_DIR_ENV: str(target)}
        steps = [
            [node, str(STORY_JS), "init", ticket, "local-mcp-token",
             "--project-root", str(root)],
            [sys.executable, str(STORY_FLOW), "init", "--feature", ticket,
             "--project-root", str(root)],
        ]
        for argv in steps:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  cwd=str(root), env=env, timeout=120)
            if proc.returncode != 0:
                return {"ok": False, "step": Path(argv[1]).name,
                        "stderr": (proc.stderr or proc.stdout or "")[-1200:]}
        feature_root = root / "doc" / "features" / ticket
        want = ["RR/prd.md", "SR/design.md", "AR/design.md", "AR/detail.json",
                "inbox/README.md"]
        missing = [rel for rel in want if not (feature_root / rel).is_file()]
        return {"ok": not missing, "missing": missing,
                "produced": sorted(str(p.relative_to(feature_root))
                                   for p in feature_root.rglob("*") if p.is_file())}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="在本仓装好本地需求系统，让人能直接跑 /story init <单号>")
    ap.add_argument("--system-dir", default=None,
                    help=f"目标目录；缺省是 story.js 的回落值 {DEFAULT_SYSTEM_DIR}")
    ap.add_argument("--only", action="append", default=[],
                    help="只装这些单号，可多次")
    ap.add_argument("--list", action="store_true", help="只列出有哪些单，不写盘")
    ap.add_argument("--reset", action="store_true", help="删掉目标目录重建（回出厂状态）")
    ap.add_argument("--verify", default=None, metavar="单号",
                    help="装完在临时目录里把 /story init 的两条命令真跑一遍")
    ap.add_argument("--allow-leftover-features", action="store_true",
                    help="需求目录里已有同名 feature 时照样继续（默认拦下）")
    args = ap.parse_args()

    tickets = discover_tickets()
    if not tickets:
        raise SystemExit(f"[bootstrap] 在 {CASES_ROOT} 下找不到任何单据")
    if args.list:
        print(json.dumps({no: ticket_summary(src)
                          for no, (_, src) in tickets.items()},
                         ensure_ascii=False, indent=1))
        return 0

    target = resolve_system_dir(args.system_dir)
    declared = read_default_system_dir_from_story_js()
    if declared and args.system_dir is None and declared != DEFAULT_SYSTEM_DIR:
        log(f"注意：story.js 的默认目录是 {declared}，本脚本装到 {DEFAULT_SYSTEM_DIR}——"
            "两边漂了，装完仍需设环境变量")

    leftover = leftover_features(tickets)
    if leftover and not args.allow_leftover_features:
        log("需求目录里已经有同名 feature：" + "、".join(leftover))
        log("story.js 落材料时「已存在就跳过」，新一轮材料会拉不进来且不报错——"
            "先把它们移走或删掉，或者加 --allow-leftover-features 明知故犯")
        return 2

    result = seed(target, tickets, args.only, args.reset)
    for item in result["installed"]:
        log(f"装上 {item['reqNo']}（{item['type']}）{item['title']} "
            f"← {item['from_case']}，{len(item['files'])} 个文件")
    for rel in result["skipped"]:
        log(f"已存在，跳过：{rel}")

    verified = verify(args.verify, target) if args.verify else None
    if verified is not None:
        log("链路验证：" + ("通过" if verified.get("ok") else f"没通过 {verified}"))

    receipt = {
        "ok": verified is None or bool(verified.get("ok")),
        "system_dir": str(target),
        "needs_env_var": target != (REPO_ROOT / DEFAULT_SYSTEM_DIR),
        "installed": [item["reqNo"] for item in result["installed"]],
        "skipped_files": len(result["skipped"]),
        "leftover_features": leftover,
        "verify": verified,
        "next": [
            "会话里说：/story init <单号>",
            f"或手动：node {STORY_JS.relative_to(REPO_ROOT)} init <单号> local-mcp-token",
            f"        python {STORY_FLOW.relative_to(REPO_ROOT)} init --feature <单号>",
        ],
        "notes": [
            "这套目录是**可写**的：archive 会覆盖单据正文、restore 会回退，"
            "想回出厂状态跑 --reset",
            "只给本仓用，不随扩展包交付；真实工程换自己的 story.js 实现",
        ],
    }
    if not receipt["needs_env_var"]:
        log("不用设环境变量——这就是 story.js 的默认目录")
    else:
        log(f"记得设环境变量：{SYSTEM_DIR_ENV}={target}")
    print(json.dumps(receipt, ensure_ascii=False, indent=1))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
