"""漂移扫描：FEATURE-CONTENT-MAP 基线表 vs doc/extensions 当前文件。

用法：python 漂移扫描.py
读本目录 FEATURE-CONTENT-MAP.md 的「| [路径:1](...) | 行数 | SHA |」基线表，
与 doc/extensions 现状（排除 __pycache__）比对物理行数与 SHA-256，
输出：未变/变化/已删除/新增 四类清单。用于按需发现实现漂移，不维护映射本身。
基线快照：d36edb70（2026-09-11）；重列基线时同步更新 map 基线表与本脚注。
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MAP = Path(__file__).resolve().parent / "归属存档" / "FEATURE-CONTENT-MAP.md"
EXT = ROOT / "doc" / "extensions"

text = MAP.read_text(encoding="utf-8")
rows = re.findall(r"^\| \[([^:\]]+?):1\]\([^)]*\) \| (\d+) \| `([0-9a-f]{64})` \|", text, re.M)
base = {p: (int(n), sha) for p, n, sha in rows}

cur = {}
for f in EXT.rglob("*"):
    if f.is_file() and "__pycache__" not in f.parts:
        rel = f.relative_to(EXT).as_posix()
        data = f.read_bytes()
        cur[rel] = (len(data.decode("utf-8").splitlines()), hashlib.sha256(data).hexdigest())

deleted = sorted(set(base) - set(cur))
added = sorted(set(cur) - set(base))
common = sorted(set(base) & set(cur))
changed = [p for p in common if base[p][1] != cur[p][1]]
same = [p for p in common if base[p][1] == cur[p][1]]

print(f"基线表 {len(base)} 项，当前 {len(cur)} 份；未变 {len(same)}，变化 {len(changed)}，删除 {len(deleted)}，新增 {len(added)}")
if deleted:
    print("\n## 已删除")
    for p in deleted:
        print(f"- {p}（基线 {base[p][0]} 行）")
if added:
    print("\n## 新增")
    for p in added:
        print(f"- {p}（当前 {cur[p][0]} 行）")
if changed:
    print("\n## 内容变化（路径 | 基线行->当前行）")
    for p in changed:
        print(f"- {p} | {base[p][0]} -> {cur[p][0]}")

