"""给**人**用：装好本地需求系统、从 demo 复制一份隔离副本，让人在副本里跑 `/story init <单号>`。

## 为什么需要它

`story.js` 把需求系统当成一个本地目录读（`STORY_REQUIREMENT_SYSTEM_DIR`）。CLI 测试装置
每次把用例夹具复制到系统临时目录再显式指过去；人手跑时没有这一步，报错是「需求系统不可达」，
`doc/features/` 一个字节都不会落。

单据装在维护域的 `test/requirement-system`（不入库）：它是测试 Case 的单据，不进 demo。

会话在隔离副本里起：demo 是发布基线，不存需求产物。副本用 Case 装配同一套复制规则
（排除运行态与 `doc/features`），带着 demo 装的发布版扩展，放在系统临时目录的
`sw-story-trial/<时间>`——在仓外，模型沿父目录走不到维护材料。产物只落在副本里。
开发版的试跑走正式 template 装配（TEST §2），不在这里。

## 为什么它在 test/scripts，不随扩展包交付

它要读 `cases/*/system/`，那里是 AR90006 这类**测试 Case 的单号**。机制层不得出现
测试特征——脚本一旦进 `extensions/`，就把测试单号带进了交付物。真实工程有自己的
需求系统，`story.js`/`token.js` 两个替身本来就要换成自己的实现，
连带也就不需要这个脚本。

## 用法

    python test/scripts/bootstrap_local_story.py            # 装上全部预制单据
    python test/scripts/bootstrap_local_story.py --list     # 只看有哪些单，不写盘
    python test/scripts/bootstrap_local_story.py --only AR90006
    python test/scripts/bootstrap_local_story.py --reset    # 回出厂状态
    python test/scripts/bootstrap_local_story.py --verify AR90006   # 验证链路真的通

装完按回执设好环境变量、进副本起会话说 `/story init AR90006`。三点要知道：

- 目录是**可写**的：`archive` 会覆盖单据正文、`restore` 会回退；想回出厂状态跑 `--reset`。
- 每跑一次建一份新副本，里面没有上一轮的 `doc/features`；用完的副本自己删。
- 补料（`supplements/` 里那些 docx）不会自动进 `inbox/`，那正是「模型会不会开口要材料」
  要观测的东西：手跑时等它开口，你再复制过去。

## 与 CLI 测试互不干扰

装置给每个 Case 的需求系统指针要么指向该 Case 自己的快照、要么指向一个不存在的路径，
绝不会落到这个目录（有机械回归守着）；Case 工作区与试用副本都从 demo 复制，带不进维护域的这个目录。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = REPO_ROOT / "test" / "cases"
#: 试用副本的来源：维护仓里的 demo，用它装好的发布版扩展
DEMO_ROOT = REPO_ROOT / "demo"
#: 试用副本的父目录（仓外）
TRIAL_PARENT = Path(tempfile.gettempdir()) / "sw-story-trial"


def demo_extension() -> Path:
    """demo 装扩展的位置：按它 framework.config.json 的 paths.extension_dir。"""
    config = json.loads((DEMO_ROOT / "framework.config.json").read_text(encoding="utf-8"))
    return DEMO_ROOT / (config.get("paths", {}).get("extension_dir") or "doc/extensions")


EXT_SCRIPTS = demo_extension() / "skills" / "story" / "scripts"
STORY_JS = EXT_SCRIPTS / "adapters" / "story.js"
STORY_FLOW = EXT_SCRIPTS / "core" / "story_flow.py"

#: 默认目标目录：维护域里不入库的那一份（相对维护仓根）
DEFAULT_SYSTEM_DIR = Path("test") / "requirement-system"
SYSTEM_DIR_ENV = "STORY_REQUIREMENT_SYSTEM_DIR"

#: `story.js` 认的单据数据文件——有它才算一张单。
DETAIL = "detail.json"


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", file=sys.stderr, flush=True)


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
    installed, skipped, drift = [], [], []
    for no, (case_id, src) in tickets.items():
        dst = target / no
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            out = dst / path.relative_to(src)
            if out.exists():
                skipped.append(str(out.relative_to(target)))
                if out.read_bytes() != path.read_bytes():
                    drift.append(f"{out.relative_to(target).as_posix()}（与夹具不同）")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
        # 夹具里已经没有的文件还留在副本里：副本落后于夹具，人读到的是旧单据
        if dst.is_dir():
            drift += [f"{p.relative_to(target).as_posix()}（夹具里没有）"
                      for p in sorted(dst.rglob("*")) if p.is_file()
                      and not (src / p.relative_to(dst)).exists()
                      and p.relative_to(dst).parts[0] not in ("history", "attachments")]
        installed.append({**ticket_summary(src), "from_case": case_id})
    return {"installed": installed, "skipped": skipped, "drift": drift}


def make_trial_copy() -> Path:
    """从 demo 复制一份试用副本：与 Case 装配同一套复制规则，另建空的需求目录。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_multi_case

    trial = TRIAL_PARENT / time.strftime("%Y%m%d-%H%M%S")
    if trial.exists():
        raise SystemExit(f"[bootstrap] 试用副本目录已存在，拒绝覆盖：{trial}")
    run_multi_case._copy_workspace_tree(DEMO_ROOT, trial)
    (trial / "doc" / "features").mkdir(parents=True, exist_ok=True)
    return trial


def verify(ticket: str, target: Path) -> dict:
    """在临时目录里把两条命令真跑一遍——回执里那句「可以跑了」的唯一证据。

    **不替人在副本里跑 `story_flow.py init`**：那两条命令是 `/story init` 的正文，
    替人跑掉就把「模型能不能自己走通初始化」这件事抹掉了，而那正是要观测的。
    这里只在 `%TEMP%` 里验证链路通不通，跑完删干净，仓里零残留。
    """
    node = shutil.which("node")
    if node is None:
        return {"ok": False, "error": "环境里没有 node，跳过链路验证"}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "probe"
        root.mkdir()
        shutil.copy2(DEMO_ROOT / "framework.config.json", root / "framework.config.json")
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
        description="装好本地需求系统、从 demo 复制试用副本，让人在副本里跑 /story init <单号>")
    ap.add_argument("--system-dir", default=None,
                    help=f"目标目录；缺省是维护域的 {DEFAULT_SYSTEM_DIR}")
    ap.add_argument("--only", action="append", default=[],
                    help="只装这些单号，可多次")
    ap.add_argument("--list", action="store_true", help="只列出有哪些单，不写盘")
    ap.add_argument("--reset", action="store_true", help="删掉目标目录重建（回出厂状态）")
    ap.add_argument("--verify", default=None, metavar="单号",
                    help="装完在临时目录里把 /story init 的两条命令真跑一遍")
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

    result = seed(target, tickets, args.only, args.reset)
    for item in result["installed"]:
        log(f"装上 {item['reqNo']}（{item['type']}）{item['title']} "
            f"← {item['from_case']}，{len(item['files'])} 个文件")
    for rel in result["skipped"]:
        log(f"已存在，跳过：{rel}")
    for rel in result["drift"]:
        log(f"副本落后于夹具：{rel}——跑 --reset 回到当前夹具")

    verified = verify(args.verify, target) if args.verify else None
    if verified is not None:
        log("链路验证：" + ("通过" if verified.get("ok") else f"没通过 {verified}"))

    ok = (verified is None or bool(verified.get("ok"))) and not result["drift"]
    # 链路不通或单据落后时不建副本：人拿到的副本一定是能跑的
    trial = make_trial_copy() if ok else None
    if trial:
        log(f"试用副本：{trial}")

    receipt = {
        "ok": ok,
        "system_dir": str(target),
        "env": {SYSTEM_DIR_ENV: str(target)},
        "trial_root": str(trial) if trial else None,
        "installed": [item["reqNo"] for item in result["installed"]],
        "skipped_files": len(result["skipped"]),
        "drift": result["drift"],
        "verify": verified,
        "next": [
            f'$env:{SYSTEM_DIR_ENV} = "{target}"',
            f'cd "{trial}"',
            "在这里起 CLI 会话，说：/story init <单号>",
            f"或在副本里手动：node {STORY_JS.relative_to(DEMO_ROOT).as_posix()} init <单号> local-mcp-token",
            f"        python {STORY_FLOW.relative_to(DEMO_ROOT).as_posix()} init --feature <单号>",
        ],
        "notes": [
            "这套目录是**可写**的：archive 会覆盖单据正文、restore 会回退，"
            "想回出厂状态跑 --reset",
            "只给本仓用，不随扩展包交付；真实工程换自己的 story.js 实现",
        ],
    }
    log(f"记得设环境变量：{SYSTEM_DIR_ENV}={target}")
    print(json.dumps(receipt, ensure_ascii=False, indent=1))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
