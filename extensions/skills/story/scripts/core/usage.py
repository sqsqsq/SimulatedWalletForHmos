"""使用记录：目标工程 `doc/usage.json` 与需求目录身份件 `.usage-id` 的唯一写入者。

一个需求目录一个节点，键是 `<目录编号>-<身份时刻>`；身份时刻在需求目录的 `.usage-id` 里，创建一次不再改。
节点只存最后活动的 ext/fw、模型自报的 agent/model 与做完过的步骤：`spent` 是可核实轮次的累计秒数，
`story update` 另有收口轮数 `rounds`。没做完过的步骤没有行；缺起点的完成轮只让行出现，不补耗时。

计的是模型实际执行一个步骤的日历时长（含本轮等待与中断）：起点是开始工作前的 begin，终点是工作结束后的收尾请求，
时间全取记录器的机器时刻，保留毫秒、求差后取整秒。story 从身份时刻（`/story init` 取材前的 begin 建立）到 `story_written_at`，
身份只由 begin 建：漏了这一步，init 不补身份，之后第一次 begin 建身份时 Story 已经开始过，Story 记为耗时缺口；
Framework 阶段从 begin 到 finalize 那一刻，原生闭环只作完成资格——此刻有有效闭环、且不早于本轮开始；
update 一轮从 record 的 `started_at`（prepare 时由 begin 的暂存移入）到 `closed_at`。漏了 begin 不拿检查、trace 或文件时刻补：
完成行照出、这一轮记为耗时缺口。本地运行态 `<需求根>/.usage-state.json`（不入库）只留两样：还没收尾的那一轮起点
（结算或移交即清），与已算好、待写进 usage 的那几步（写 usage 失败后下一次照它赋值，不重复累加）；都没有时不留这个文件。
重复 begin 保留最早的起点，重复收尾不再加。

动作：
- begin：一个步骤开始实际工作之前（Spec / Plan 的作者任务包入口自动调，其余由作者页与 Skill 的第一步执行）：
  没有身份件就建（本地未提交的同编号旧节点替换掉，已提交的保留）；阶段与 update 登记这一轮的起点，已有就保留最早的；
- init：story init 成功后；沿用开始时 begin 建的身份并刷新；没有身份不补建，报 Story 开始记录缺口；
- refresh：其它 story 命令成功后；已有身份才刷新版本、自报身份、Story 与 update，不结算 Framework 阶段；
- finalize：阶段原生闭环之后的 Extension 收尾，由消费模型在交付、进下一阶段或提交代码之前执行，Story 交付门也调它：
  核本阶段已闭环、身份在，结算这一轮并读回落盘的 usage 确认这一步已记；失败时按报出的原因处理（没闭环先完成阶段，写不进先修环境）再重跑同一命令；
- close：update 收口之后，对这一轮进入过、此刻有效闭环的阶段同样收尾；
- ensure / inspect：适配时确保记录文件在 / 只读校验。

入口：`python usage.py --project-root <根> --feature <需求编号> --begin --step <步骤>` 与 `... --finalize --phase <阶段>`；
其余动作由 story 命令
经 stdin 一个 JSON（action、feature、step）调用。stdout `{ok, changed, errors, requirement, pending_identity, note}`，
收尾另有 `phase`、`recorded`、`timing_gap`。只用标准库与 git。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from materials import importer  # noqa: E402
from flow import phase_facts, state  # noqa: E402

EXT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "usage.json").read_text(encoding="utf-8"))
SCHEMA, STEPS, UPDATE = CONTRACT["schema"], CONTRACT["steps"], "story update"
ACTIONS = ("init", "begin", "refresh", "finalize", "close", "ensure", "inspect")
NODE_FIELDS = ("ext", "fw", "agent", "model", "steps")
STAMP = re.compile(r"\d{8}T\d{6}\.\d{3}Z")
KEY = re.compile(r"(.+)-(\d{8}T\d{6}\.\d{3}Z)")
OLD = ("旧合同的使用记录（编号直作键，或含 name/version/features、start/verdict/completed/last_result）："
       "本版不支持，也不自动转换——旧版进行中的需求在旧版收口，或从 init 重起；原文件不改写")
#: 等锁的上限（秒）：记录是短读改写，等不到说明另一次记录卡住了，报出来让原操作重试
LOCK_WAIT = 10.0


class UsageError(Exception):
    """usage 读写失败：原文件保持不动，原因原样报出。"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def record_path(project_root: Path) -> Path:
    return Path(project_root) / Path(*CONTRACT["record"].split("/"))


# ---------------------------------------------------------------------------
# 单文件事务：OS 互斥 → 锁后重读 → 只改本次节点 → 同目录临时文件原子替换

@contextmanager
def locked(record: Path):
    lock = record.with_name(record.name + ".lock")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock, "a+b")  # noqa: SIM115  下面的 with 负责关
    except OSError as exc:
        raise UsageError(f"{lock.name} 打不开（{exc}）：原记录没动，修好目录或文件权限后重跑原操作即可补记") from exc
    with fh:
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                _lock(fh, True)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise UsageError(f"{record.name} 正被另一次记录占用：稍后重跑原操作即可重试") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            _lock(fh, False)


def _lock(fh, on: bool) -> None:
    if os.name == "nt":
        import msvcrt  # noqa: PLC0415
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK if on else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl  # noqa: PLC0415
        fcntl.flock(fh, (fcntl.LOCK_EX | fcntl.LOCK_NB) if on else fcntl.LOCK_UN)


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp") if path.name.startswith(".") \
        else path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise UsageError(f"{path.name} 写不进去（{exc}）：原文件保持不变，修好环境后重跑原操作即可补记") from exc


def load(record: Path) -> dict:
    return snapshot(record)[1]


def snapshot(record: Path) -> tuple[bytes, dict]:
    """读 usage 的完整字节并解析（统计用这份字节算摘要与数字）；没有文件是空表。"""
    if not record.exists():
        return b"", {"schema": SCHEMA, "requirements": {}}
    try:
        raw = record.read_bytes()
    except OSError as exc:
        raise UsageError(f"{record.name} 读不出（{exc}）") from exc
    return raw, parse(raw, record.name)


def parse(raw: bytes, name: str) -> dict:
    """坏 JSON、冲突标记、不支持的 schema、旧合同或节点不合合同都报错，不重置。"""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"{name} 不是 UTF-8 文本（{exc}）") from exc
    if re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.M):
        raise UsageError(f"{name} 里有合并冲突标记：按 Git 正常解决冲突后重跑，同一需求的 spent 不自动相加")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise UsageError(f"{name} 不是合法 JSON（{exc}）：修好后重跑，不会把它重置成空表") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("requirements"), dict):
        raise UsageError(f"{name} 不是 schema {SCHEMA} 的使用记录：不支持的格式不改写")
    old, bad = shape_problems(data["requirements"])
    if old:
        raise UsageError(f"{name} 是{OLD}")
    if bad:
        raise UsageError(f"{name} 的节点不合合同（{'；'.join(bad[:5])}{' 等' if len(bad) > 5 else ''}）："
                         "字段合同见 doc/extensions/skills/story/contracts/usage.json，修好后重跑，原文件不改写")
    return data


def shape_problems(reqs: dict) -> tuple[bool, list[str]]:
    """(是不是旧合同, 不合合同的地方)。"""
    old, bad = False, []
    text = lambda v: v is None or isinstance(v, str)  # noqa: E731
    count = lambda v, low: isinstance(v, int) and not isinstance(v, bool) and v >= low  # noqa: E731
    for key, node in reqs.items():
        if not isinstance(node, dict):
            bad.append(f"{key} 不是对象")
            continue
        steps = node.get("steps")
        rows = steps.values() if isinstance(steps, dict) else []
        if not KEY.fullmatch(key) or {"name", "version", "features"} & set(node) \
                or any(isinstance(r, dict) and {"start", "verdict", "completed", "last_result"} & set(r) for r in rows):
            old = True
            continue
        bad += [f"{key} 缺 {f}" for f in NODE_FIELDS if f not in node]
        bad += [f"{key} 有合同外的字段 {f}" for f in node if f not in NODE_FIELDS]
        bad += [f"{key}.{f} 应为文字或 null" for f in ("ext", "fw", "agent", "model") if f in node and not text(node[f])]
        if not isinstance(steps, dict):
            bad.append(f"{key}.steps 不是对象")
            continue
        for step, row in steps.items():
            where = f"{key}.steps.{step}"
            allowed = {"spent", "rounds"} if step == UPDATE else {"spent"}
            if step not in STEPS:
                bad.append(f"{key}.steps 有合同外的步骤 {step}")
            elif not isinstance(row, dict) or set(row) - allowed:
                bad.append(f"{where} 只能有 {' / '.join(sorted(allowed))}")
            elif "spent" in row and not count(row["spent"], 0):
                bad.append(f"{where}.spent 应为非负整数秒")
            elif "rounds" in row and not count(row["rounds"], 1):
                bad.append(f"{where}.rounds 应为正整数")
    return old, bad


def load_state(path: Path) -> dict:
    """本地运行态：`{需求键: {"starts": {阶段: 重试轮起点}, "pending": {步骤: 待写的行}}}`。坏了报出来，不当成空的。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"{path.name} 读不出（{exc}）：它是本地运行态，删掉它只丢未结算轮次的起点，已累计的耗时不受影响") from exc
    if not isinstance(data, dict):
        raise UsageError(f"{path.name} 不是 JSON 对象：删掉它只丢未结算轮次的起点")
    return data


# ---------------------------------------------------------------------------
# 身份、版本与自报身份

def read_identity(feature_root: Path) -> str | None:
    path = feature_root / CONTRACT["identity_file"]
    if not path.is_file():
        return None
    try:
        stamp = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise UsageError(f"{feature_root.name}/{path.name} 读不出（{exc}）") from exc
    if not STAMP.fullmatch(stamp):
        raise UsageError(f"{feature_root.name}/{path.name} 不是身份时刻（形如 20261021T080102.123Z）：它一次写成后不改，"
                         "被改坏了按版本库里的那份恢复")
    return stamp


def stamp_time(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def committed_keys(project_root: Path) -> set[str]:
    """HEAD 里 usage 已有的节点键；新仓没有 HEAD 或 HEAD 里没有这份文件时是空集。查不了就报原因，不许当成未提交。"""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(project_root), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    try:
        if git("rev-parse", "--git-dir").returncode:
            raise UsageError("工程不在 Git 仓里")
        if git("rev-parse", "--verify", "-q", "HEAD").returncode:
            return set()
        shown = git("show", f"HEAD:./{CONTRACT['record']}")       # ./ 按工程目录解析，工程不必在仓根
        if shown.returncode:
            return set()                                         # HEAD 里还没有这份文件
        reqs = json.loads(shown.stdout).get("requirements")
    except (OSError, ValueError, AttributeError) as exc:
        raise UsageError(f"读不出 HEAD 里的 {CONTRACT['record']}（{exc}）") from exc
    if not isinstance(reqs, dict):
        raise UsageError(f"HEAD 里的 {CONTRACT['record']} 没有 requirements 对象")
    return set(reqs)


def ext_version() -> str | None:
    try:
        m = re.search(r'^version:\s*"?([^"\s]+)"?', (EXT_ROOT / "manifest.yaml").read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


def fw_version(feature_root: Path) -> str | None:
    """最近写过的阶段 summary 里 `gate_fingerprint` 的版本前缀；没有 summary 就是 None（不猜）。"""
    found = []
    for phase in phase_facts.PHASES:
        s = phase_facts.summary(feature_root, phase)
        gate = (s.get("data") or {}).get("gate_fingerprint")
        gate = gate.get("fingerprint") if isinstance(gate, dict) else gate
        if isinstance(gate, str) and ":" in gate:
            found.append((s["path"].stat().st_mtime, gate.split(":", 1)[0]))
    return max(found)[1] if found else None


def take_input(feature_root: Path, node: dict, done: list) -> None:
    """模型在原任务里写的 `{agent, model}`：按字段接收，已有非空值的不改，不知道的保持 null；记录落盘后删掉这份输入。"""
    path = feature_root / CONTRACT["input_file"]
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("不是 JSON 对象")
    except (OSError, ValueError) as exc:
        raise UsageError(f'{feature_root.name}/{path.name} 读不出（{exc}）：写成 {{"agent": "<宿主>", "model": "<模型>"}}，'
                         '不知道的写 null') from exc
    for k in ("agent", "model"):
        if node[k] is None and isinstance(v := data.get(k), str) and v.strip():
            node[k] = v.strip()
    done.append(lambda: path.unlink(missing_ok=True))


# ---------------------------------------------------------------------------
# 结算：每类步骤一个真源

def closed_at(feature_root: Path, phase: str) -> datetime | None:
    s = phase_facts.summary(feature_root, phase)
    if s["state"] == "unreadable":
        raise UsageError(f"{s['path'].as_posix()} 读不出（{s['why']}）：{phase} 的完成判不了")
    commit = (s.get("data") or {}).get("closure_commit")
    return phase_facts.moment(commit.get("committed_at")) if s["state"] == "closed" and isinstance(commit, dict) else None


def add(row: dict | None, start: datetime, end: datetime) -> dict:
    row = dict(row or {})
    row["spent"] = row.get("spent", 0) + round((end - start).total_seconds())
    return row


def finish_round(fr: Path, phase: str, steps: dict, starts: dict) -> str | None:
    """收尾结算一轮：begin 的起点到此刻；此刻要有有效闭环且不早于本轮开始，否则旧闭环不结算、起点保留。
    没有起点的首次完成只让行出现、记为缺口，不拿 trace 或检查时刻补。返回不结算或缺口的说明，结算了返回 None。"""
    closed = closed_at(fr, phase)
    start = phase_facts.moment(starts.get(phase))
    if closed is None:
        return f"{phase} 此刻没有有效闭环"
    if start is None:
        if phase in steps:
            return None                     # 这一轮已经收过尾
        steps[phase] = {}
        return f"{phase} 这一轮没有开始记录（工作前没跑 begin）：完成行已记，耗时是缺口"
    if closed < start:
        return f"{phase} 重新开始之后还没有新的闭环（闭环早于本轮开始），这一轮没有结算，起点保留到闭环后收尾"
    steps[phase] = add(steps.get(phase), start, now())
    starts.pop(phase, None)
    return None


def tally_story(fr: Path, stamp: str, steps: dict) -> None:
    """Story 只在第一次成文时计：身份时刻到 `story_written_at`；之后再登记不再加。"""
    written = phase_facts.moment((state.load(fr) or {}).get("story_written_at"))
    if written is None or "story" in steps:
        return
    start = stamp_time(stamp)
    steps["story"] = add(None, start, written) if written >= start else {}


def tally_update(fr: Path, steps: dict) -> None:
    """update 的完成事实全在原生 record 里：有 `closed_at` 的一轮就是收口过一轮（之后撤回也不抹掉），
    轮数按记录数，耗时只累计有 `started_at`（begin 移入）且起止合法的那几轮；从没收口的不计。每次按全部记录重算后赋值，
    重复刷新不会多加；盘上记录比已记的轮数少、或算出的耗时少于已记的（没有开始记录的轮次）时不拿较少的结果覆盖已有累计。"""
    rounds, spent, timed = 0, 0, False
    for _, rec in phase_facts.update_records(fr):
        closed = phase_facts.moment(rec.get("closed_at"))
        if rec.get("kind") == "story_baseline" or closed is None:
            continue
        rounds += 1
        started = phase_facts.moment(rec.get("started_at"))
        # 收口时刻只记到秒、起点带毫秒：同一秒里收口不算起止颠倒
        if started is not None and closed >= started.replace(microsecond=0):
            spent, timed = spent + max(0, int((closed - started).total_seconds())), True
    known = steps.get(UPDATE, {})
    if rounds and rounds >= known.get("rounds", 0):
        spent = max(spent, known.get("spent", 0))
        steps[UPDATE] = {**({"spent": spent} if timed or "spent" in known else {}), "rounds": rounds}


def refresh(fr: Path, stamp: str, node: dict, slot: dict, done: list) -> None:
    """一个节点按当前真源刷新：版本、自报身份、Story 与 update。Framework 阶段不在这里结算，也不在这里开始。"""
    steps, starts = node["steps"], slot.setdefault("starts", {})
    for step, row in slot.pop("pending", {}).items():      # 上次写 usage 没成的结算行：赋值，不再加
        steps[step] = row
    node["ext"] = ext_version()
    node["fw"] = fw_version(fr) or node["fw"]
    take_input(fr, node, done)
    tally_story(fr, stamp, steps)
    tally_update(fr, steps)


# ---------------------------------------------------------------------------
# 动作

def feature_dir(project_root: Path, number: str) -> Path:
    return Path(project_root) / importer.features_dir(project_root) / number


def apply(project_root: Path, data: dict, st: dict, action: str, feature: str | None, step: str | None,
          errors: list[str], done: list, notes: list[str]) -> list[str]:
    """在已读出的 usage 与运行态上执行一个动作，返回动过的节点键；`done` 收记录落盘之后才做的写入。"""
    reqs = data["requirements"]
    allowed = phase_facts.PHASES if action == "finalize" else STEPS if action == "begin" else None
    if not feature or (allowed and step not in allowed):
        raise UsageError(f"{action} 要 feature{'与步骤 step（' + ' / '.join(allowed) + '）' if allowed else ''}")
    fr = feature_dir(project_root, feature)
    stamp = read_identity(fr)
    if action == "finalize" and stamp is None:
        raise UsageError(f"{feature} 没有使用记录身份（{CONTRACT['identity_file']}）：收尾不新建身份，"
                         "开始工作时的 begin 会建它")
    if action == "finalize" and closed_at(fr, step) is None:
        raise UsageError(f"{feature} 的 {step} 还没有原生有效闭环（summary 没有 closure_commit）：先完成阶段闭环再收尾")
    late = False
    if stamp is None:
        if action == "init":            # 身份只由开始工作前的 begin 建：init 时刻晚于取材，拿它当起点会少算还像是完整的
            notes.append("这次 Story 没有开始记录（取材前没跑 begin --step story）：不拿 init 时刻补，Story 的耗时记为缺口；"
                         "业务照常继续，之后各阶段开始前照常 begin")
        if action != "begin":
            return []
        # Story 已经 init 过（收件箱骨架或流程契约在）：它的开始早于这个身份
        late = (fr / "inbox").is_dir() or (fr / Path(*state.CONTRACT)).is_file()
        moment = now()
        stamp = moment.strftime("%Y%m%dT%H%M%S.") + f"{moment.microsecond // 1000:03d}Z"
        same = [k for k in reqs if KEY.fullmatch(k).group(1) == feature]
        try:
            committed = committed_keys(project_root) if same else set()
        except UsageError as exc:
            errors.append(f"{exc}：同编号旧节点 {'、'.join(same)} 是否已提交判不了，保留未删")
            committed = set(same)
        for k in same:
            if k not in committed:          # 本地重启：未提交的旧尝试丢弃；已提交的（含别人的）保留
                reqs.pop(k)
                st.pop(k, None)
        done.append(lambda: (fr.mkdir(parents=True, exist_ok=True),
                             (fr / CONTRACT["identity_file"]).write_text(stamp + "\n", encoding="utf-8")))
    key = f"{feature}-{stamp}"
    node = reqs.setdefault(key, {"ext": None, "fw": None, "agent": None, "model": None, "steps": {}})
    slot = st.setdefault(key, {})
    if late and "story" not in node["steps"]:
        node["steps"]["story"] = {}
        notes.append("Story 在这个使用记录身份之前已经开始（取材前没跑 begin --step story）：Story 记为耗时缺口")
    try:
        refresh(fr, stamp, node, slot, done)
        starts = slot.setdefault("starts", {})
        if action == "begin" and step == UPDATE and not open_update(fr):
            stale, last = phase_facts.moment(starts.get(UPDATE)), last_closed(fr)
            if stale is not None and last is not None and stale.replace(microsecond=0) <= phase_facts.moment(last["closed_at"]):
                starts.pop(UPDATE)          # 上一轮收口时没移成的起点（当时已报）：那一轮已是缺口，不带进新一轮
                notes.append(f"上一轮 update（{last.get('id')}）的开始时刻没移进它的记录，那一轮记为耗时缺口；这一轮从现在开始")
        if action == "begin" and step != "story" and not (step == UPDATE and open_update(fr)):
            starts.setdefault(step, iso(now()))        # story 的起点是身份时刻；开着的 update 轮次已有 started_at
        elif action == "finalize":
            notes.extend(filter(None, [finish_round(fr, step, node["steps"], starts)]))
        elif action == "close":             # update 收口：这一轮开始过、此刻有效闭环的阶段
            if (last_closed(fr) or {}).get("started_at"):
                starts.pop(UPDATE, None)    # 起点已在刚收口的那一轮里：剩下的暂存是残留；还没移交的不清
            for p in [p for p in phase_facts.PHASES if p in starts and closed_at(fr, p) is not None]:
                notes.extend(filter(None, [finish_round(fr, p, node["steps"], starts)]))
    except (UsageError, state.FlowError, importer.ImportError_) as exc:     # 已结算的步骤各自成立，照常落盘
        errors.append(str(exc))
    return [key]


def last_closed(fr: Path) -> dict | None:
    """最近收口过的那一轮 update 记录（之后撤回的也算）；没有返回 None。"""
    return next((rec for _, rec in reversed(phase_facts.update_records(fr))
                 if rec.get("kind") != "story_baseline" and phase_facts.moment(rec.get("closed_at"))), None)


def open_update(fr: Path) -> dict | None:
    """开着的那一轮 update 记录；没有返回 None。"""
    return next((rec for _, rec in reversed(phase_facts.update_records(fr)) if rec.get("status") == "open"), None)


def update_start(feature_root: Path) -> str | None:
    """begin 暂存的 update 起点（只读）：prepare 开轮时把它写进 record 的 `started_at`。"""
    stamp = read_identity(feature_root)
    project_root = importer.project_root_of(feature_root)
    path = Path(project_root) / importer.features_dir(project_root) / CONTRACT["state_file"]
    slot = load_state(path).get(f"{feature_root.name}-{stamp}", {}) if stamp else {}
    return (slot.get("starts") or {}).get(UPDATE)


def drop_update_start(feature_root: Path) -> None:
    """起点已经在 record 里了：清掉运行态里的暂存，稳定状态只留一处。"""
    stamp = read_identity(feature_root)
    project_root = importer.project_root_of(feature_root)
    path = Path(project_root) / importer.features_dir(project_root) / CONTRACT["state_file"]
    if not stamp or not path.exists():
        return
    with locked(record_path(project_root)):
        st = load_state(path)
        (st.get(f"{feature_root.name}-{stamp}", {}).get("starts") or {}).pop(UPDATE, None)
        tidy(st)
        save_state(path, st)


def tidy(st: dict) -> None:
    """运行态只留有内容的部分：空的起点表、待写表与需求槽都去掉。"""
    for key in list(st):
        slot = st[key] if isinstance(st[key], dict) else {}
        for part in ("starts", "pending"):
            if not slot.get(part):
                slot.pop(part, None)
        if not slot:
            st.pop(key)


def save_state(path: Path, st: dict) -> None:
    """有内容才写；最后一项必要状态没了就删掉文件，不留空壳。"""
    if st:
        write_json(path, st)
    elif path.exists():
        try:
            path.unlink()
        except OSError as exc:
            raise UsageError(f"{path.name} 清不掉（{exc}）：它只剩空内容，删掉它不影响已记的使用记录") from exc


def after_command(project_root: Path, feature: str, mode: str, action: str | None = None) -> dict:
    """Story 命令成功之后的采集：init 沿用开始时的身份（没有就报缺口），update 收口结算这一轮进入过的阶段，其余已有身份才刷新。
    记录错误与提示另列，不改业务结果。"""
    which = "init" if mode == "init" else "close" if (mode, action) == ("update", "close") else "refresh"
    return record(project_root, which, feature=feature)


def record(project_root: Path, action: str, *, feature: str | None = None, step: str | None = None) -> dict:
    """执行一个动作并落盘；失败不改原文件。返回 `{ok, changed, errors, requirement, pending_identity, note}`。"""
    out = {"ok": False, "changed": False, "errors": [], "requirement": None, "pending_identity": False, "note": None}
    if action not in ACTIONS:
        out["errors"].append(f"未知动作 {action}：可用 {' / '.join(ACTIONS)}")
        return out
    path = record_path(project_root)
    if action in ("ensure", "inspect"):
        return ensure(path, out) if action == "ensure" else inspect(path, out)
    if action == "refresh" and not path.exists():
        out["ok"] = True            # 刷新不创造记录：没有 usage 就没有要补的事实，也不建锁
        return out
    state_path = Path(project_root) / importer.features_dir(project_root) / CONTRACT["state_file"]
    try:
        with locked(path):
            data, st, done, notes = load(path), load_state(state_path), [], []
            before = json.dumps([data, st], sort_keys=True)
            old = json.loads(json.dumps(data["requirements"]))
            keys = apply(Path(project_root), data, st, action, feature, step, out["errors"], done, notes)
            tidy(st)
            if json.dumps([data, st], sort_keys=True) != before:
                # 先把这次变了的步骤行记进运行态（起点已清），再写 usage，最后清待写——任一步失败，下一次刷新都不会重复累计
                for key in keys:
                    steps = data["requirements"].get(key, {}).get("steps", {})
                    moved = {k: v for k, v in steps.items() if old.get(key, {}).get("steps", {}).get(k) != v}
                    if moved:
                        st.setdefault(key, {})["pending"] = moved
                save_state(state_path, st)
                write_json(path, data)
                for key in keys:
                    st.get(key, {}).pop("pending", None)
                tidy(st)
                save_state(state_path, st)
                out["changed"] = True
            if action == "finalize" and not out["errors"]:
                # 读回盘上那一份核这一步已记：写进去了才算收尾完成
                row = load(path)["requirements"].get(keys[0], {}).get("steps", {}).get(step)
                if row is None:
                    out["errors"].append(f"{CONTRACT['record']} 读回没有 {step} 这一行")
                out.update(phase=step, recorded=row, timing_gap=row is not None and "spent" not in row)
            for later in done:      # 身份件与已接收的输入在记录落盘之后才写、才删：落盘失败时下一次照样能接上
                later()
    except UsageError as exc:
        out["errors"].append(str(exc))
        return out
    except OSError as exc:      # 文件系统层面的失败（权限、占用）：记录没做成，原业务结果不受影响
        out["errors"].append(f"使用记录没写成（{exc}）：修好环境后重跑原操作即可补记")
        return out
    node = data["requirements"].get(keys[0]) if len(keys) == 1 else None
    story = node is not None and feature and (feature_dir(project_root, feature) / Path(*state.CONTRACT)).is_file()
    pending = bool(story) and node["agent"] is None and node["model"] is None
    out.update(ok=not out["errors"], requirement=keys[0] if len(keys) == 1 else None, pending_identity=pending)
    if pending:     # Story 需求有模型在场：自报身份是它的任务，缺了就说，不当成纯框架的未知
        rel = (feature_dir(project_root, feature) / CONTRACT["input_file"]).relative_to(project_root).as_posix()
        notes.append(f"使用记录还没有本需求的 agent 与模型：在 {rel} 写 "
                       '{"agent": "<你所在的宿主>", "model": "<你的模型>"}（不知道的写 null），下一次 begin、finalize 或 story 命令自动接收')
    if notes:
        out["note"] = "；".join(notes)
    return out


def ensure(path: Path, out: dict) -> dict:
    """锁内重判：缺文件就以空表原子建立；已有文件只按合同校验，一个字节不改。"""
    try:
        with locked(path):
            if path.exists():
                parse(path.read_bytes(), path.name)
            else:
                write_json(path, load(path))
                out["changed"] = True
    except UsageError as exc:
        out["errors"].append(str(exc))
    except OSError as exc:
        out["errors"].append(f"{path.name} 建不起来（{exc}）：修好目录权限后重跑")
    out["ok"] = not out["errors"]
    return out


def inspect(path: Path, out: dict) -> dict:
    """只读：文件在不在、合不合合同。"""
    try:
        if not path.is_file():
            raise UsageError(f"{CONTRACT['record']} 不存在：使用记录还没建立")
        parse(path.read_bytes(), path.name)
    except UsageError as exc:
        out["errors"].append(str(exc))
    except OSError as exc:
        out["errors"].append(f"{path.name} 读不出（{exc}）")
    out["ok"] = not out["errors"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="使用记录：阶段闭环后的收尾，或内部入口（stdin 一个 JSON）")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--begin", action="store_true", help="一个步骤开始实际工作之前")
    ap.add_argument("--step", default=None, choices=STEPS)
    ap.add_argument("--finalize", action="store_true", help="阶段原生闭环之后的 Extension 收尾")
    ap.add_argument("--feature", default=None)
    ap.add_argument("--phase", default=None, choices=phase_facts.PHASES)
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        # 按 UTF-8 读原始字节：不随控制台代码页变，PowerShell 管道在开头带的 BOM 一并去掉
        req = {"action": "finalize", "feature": args.feature, "step": args.phase} if args.finalize \
            else {"action": "begin", "feature": args.feature, "step": args.step} if args.begin \
            else json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    except ValueError as exc:
        print(json.dumps({"ok": False, "changed": False, "errors": [f"stdin 不是 JSON（{exc}）"]}, ensure_ascii=False))
        return 2
    out = record(Path(args.project_root), str(req.get("action")), feature=req.get("feature"), step=req.get("step"))
    print(json.dumps(out, ensure_ascii=False))
    for err in out["errors"]:
        print(f"[usage] {err}", file=sys.stderr)
    if args.finalize and not out["ok"]:
        print(f"[usage] {args.feature} 的 {args.phase} 使用记录没有收尾：按上面的原因处理（阶段还没闭环就先完成阶段），"
              "再重跑同一条收尾命令；成功前不要说使用记录可以归档", file=sys.stderr)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
