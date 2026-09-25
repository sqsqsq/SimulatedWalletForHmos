"""只读查看两个 Case 的隔离 workspace 产物进度：不改被测产物、不消费事件。"""
import io
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path("E:/Project/SimulatedWalletForHmos")
SUITE = sys.argv[1] if len(sys.argv) > 1 else "story-suite-20260914-143310"
WS = Path(os.environ["TEMP"]) / "sw-story" / SUITE
OUT = REPO / "output" / "story" / SUITE / "cases"


def stamp(p: Path) -> str:
    return time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime))


for case, feat in (("auto-topup", "AR90006"), ("car-key-sharing", "ISSUE-206")):
    f = WS / case / "doc" / "features" / feat
    print(f"== {case} {feat}  workspace={f.exists()}")
    for rel in ("spec/knowledge-use.yaml", "spec/spec.md", "acceptance.yaml",
                "AR/story-src/decisions.json", "AR/story-src/story-template.md",
                "AR/story.md", "AR/review.md", "plan/plan.md"):
        p = f / rel
        if not p.exists():
            print(f"   {rel:34} missing")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        print(f"   {rel:34} {len(text.splitlines()):4} lines  mtime {stamp(p)}")
    tpl = f / "AR" / "story-src" / "story-template.md"
    if tpl.exists():
        print("   template placeholders:", len(re.findall(r"\{\{", tpl.read_text(encoding="utf-8", errors="replace"))))
    story = f / "AR" / "story.md"
    if story.exists():
        pending = re.findall(r"<!--\s*待写[:：]\s*([^>]*?)\s*-->", story.read_text(encoding="utf-8", errors="replace"))
        print("   story pending chapters:", len(pending), pending[:3])
    drafts = f / "AR" / "story-src" / "drafts"
    print("   drafts:", len(list(drafts.glob("*.md"))) if drafts.exists() else 0)
    runs = sorted((OUT / case).glob("2026*")) if (OUT / case).exists() else []
    if runs:
        s = runs[-1] / "state.json"
        if s.exists():
            j = json.loads(s.read_text(encoding="utf-8"))
            print("   run", runs[-1].name, "status", j.get("status"), "started", j.get("started_at"))
print("now", time.strftime("%H:%M:%S"))
