"""代跑 heartbeat：按间隔 poll，该叫宿主时立刻退出（TEST §3.1）。

两条纪律照 §3.1：
1. `next_action != poll_after_interval` 立刻退出，不自己续睡；
2. 退出原因写进日志，事后看得出是**等宿主**还是脚本自己挂了。
"""
import io
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path("E:/Project/SimulatedWalletForHmos")
SUITE = sys.argv[1]
BUDGET_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 480

started = time.time()
interval = 15
rounds = 0

while True:
    proc = subprocess.run(
        [sys.executable, "test/story/scripts/run_multi_case.py", "poll",
         "--suite-id", SUITE, "--wait-sec", "0"],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    rounds += 1
    try:
        snap = json.loads(proc.stdout[proc.stdout.index("{"):])
    except (ValueError, IndexError):
        print(f"[hb] 第 {rounds} 轮 poll 输出不是 JSON，退出让宿主看：\n"
              f"{proc.stdout[-800:]}\n{proc.stderr[-800:]}")
        sys.exit(2)

    cases = snap.get("cases") or []
    line = " | ".join(
        f"{c.get('case')}: {c.get('status')} @{c.get('current_phase')}"
        f" ev={c.get('event_count')} idle={c.get('events_idle_sec')}s"
        for c in cases)
    action = snap.get("next_action")
    interval = int(snap.get("next_interval_sec") or 15)
    waited = int(time.time() - started)
    print(f"[hb] {rounds:>3} 轮 / {waited:>4}s  {line}  next={action}")

    if action != "poll_after_interval":
        reqs = snap.get("adaptive_reply_requests") or []
        print(f"[hb] 停下叫宿主：next_action={action}，"
              f"awaiting={len(reqs)} 条。**等宿主回话，不是脚本挂了。**")
        print(json.dumps({"next_action": action,
                          "adaptive_reply_requests": reqs,
                          "cases": [{k: c.get(k) for k in
                                     ("case", "status", "current_phase",
                                      "highest_phase_reached", "closure",
                                      "interaction_state", "last_error")}
                                    for c in cases]},
                         ensure_ascii=False, indent=2)[:6000])
        sys.exit(0)

    if snap.get("suite_terminal"):
        print("[hb] suite 已终态，退出。")
        sys.exit(0)
    if time.time() - started > BUDGET_SEC:
        print(f"[hb] 本次代跑预算 {BUDGET_SEC}s 用完，交回宿主继续（不是失败）。")
        sys.exit(3)
    time.sleep(interval)
