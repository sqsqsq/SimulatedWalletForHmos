"""使用记录：目标工程 `doc/usage.json` 的唯一写入者。

正式入口（六阶段 pre_phase、作者任务包、Story 与 update 命令、stats 前对账）在内部调用；模型只在原任务里
写 `<需求目录>/.usage-input.json` 提供名称与业务版本，不额外运行本脚本。

动作：
- observe：登记确实发生的使用与 feature 关联，接收首份初始化输入；检查观测不形成可信起点；
- begin：真实工作入口，先对账旧结果再开本轮起点，同轮重复进入保留原起点；
- reconcile：按已登记的 features/steps 读现存原生事实，更新结果与计时，不创造需求或步骤；
- finish-own / abort-own：Story 与 update 自有操作落盘后结算对应步骤（结果从文件核，不收调用方自报）；
- ensure：适配时确保记录文件在——缺了建空表，在了只校验不重写，不创建需求；
- inspect：只读校验记录文件，缺失明说，不建目录、锁或临时文件。

结算只认终态事件（原生闭环、Story 成文且 spec 闭环、update 关轮或撤回）；`last_result` 是最近采纳的终态游标，
中间结论、文件暂缺与格式变化不推进它。同一终态反复出现不重复计；判不清区间归属就记耗时未知，不猜。

机器入口：`python usage.py --project-root <根>`，stdin 一个 JSON（action、feature、step、requirement），
stdout 一个结果 JSON `{ok, changed, errors, requirement, pending_init}`，不经 shell 拼接。只用标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
SCHEMA, STEPS = CONTRACT["schema"], CONTRACT["steps"]
OWN = {"story", "story update"}
ACTIONS = ("observe", "begin", "reconcile", "finish-own", "abort-own", "ensure", "inspect")
#: 等锁的上限（秒）：记录是短读改写，等不到说明另一次记录卡住了，报出来让原操作重试
LOCK_WAIT = 10.0


class UsageError(Exception):
    """usage 读写失败：原文件保持不动，原因原样报出。"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(at: datetime) -> str:
    """UTC 时刻；保留原值的小数秒（Framework 写毫秒），游标与原生事件同精度。"""
    at = at.astimezone(timezone.utc)
    return at.strftime("%Y-%m-%dT%H:%M:%S") + (f".{at.microsecond:06d}" if at.microsecond else "") + "Z"


# ---------------------------------------------------------------------------
# 单文件事务：OS 互斥 → 锁后重读 → 只改本次条目 → 同目录临时文件原子替换

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


def load(record: Path) -> dict:
    return snapshot(record)[1]


def snapshot(record: Path) -> tuple[bytes, dict]:
    """读 usage 的完整字节并解析（统计用这份字节算摘要与数字）；没有文件是空表。
    坏 JSON、冲突标记、不支持的 schema、节点不合合同都报错，不重置。"""
    if not record.exists():
        return b"", {"schema": SCHEMA, "requirements": {}}
    try:
        raw = record.read_bytes()
    except OSError as exc:
        raise UsageError(f"{record.name} 读不出（{exc}）") from exc
    return raw, parse(raw, record.name)


def parse(raw: bytes, name: str) -> dict:
    """从一份完整字节解析并按合同校验；统计用同一份字节算摘要与数字。"""
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
    bad = shape_problems(data["requirements"])
    if bad:
        raise UsageError(f"{name} 的节点不合合同（{'；'.join(bad[:5])}{' 等' if len(bad) > 5 else ''}）："
                         "字段合同见 doc/extensions/skills/story/contracts/usage.json，修好后重跑，原文件不改写")
    return data


_KINDS = {
    "string": lambda v: isinstance(v, str),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
    "object": lambda v: isinstance(v, dict),
    "datetime": lambda v: phase_facts.moment(v) is not None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "{id, ended_at}": lambda v: isinstance(v, dict) and isinstance(v.get("id"), str)
    and phase_facts.moment(v.get("ended_at")) is not None,
}


def _fields(where: str, node: object, spec: dict) -> list[str]:
    if not isinstance(node, dict):
        return [f"{where} 不是对象"]
    return [f"{where} 缺 {f}" if f not in node else f"{where}.{f} 应为 {k}" for f, k in spec.items()
            if f not in node or not ((k.endswith("|null") and node[f] is None) or _KINDS[k.removesuffix("|null")](node[f]))]


def shape_problems(reqs: dict) -> list[str]:
    """按合同的 requirement / step 字段核每个节点；记录器与统计实际消费的就是这些字段。"""
    bad = []
    for key, node in reqs.items():
        bad += _fields(key, node, CONTRACT["requirement"])
        steps = node.get("steps") if isinstance(node, dict) else None
        for step, entry in (steps if isinstance(steps, dict) else {}).items():
            bad += (_fields(f"{key}.steps.{step}", entry, CONTRACT["step"]) if step in STEPS
                    else [f"{key}.steps 有合同外的步骤 {step}"])
    return bad


def save(record: Path, data: dict) -> None:
    tmp = record.with_name(f".{record.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        os.replace(tmp, record)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise UsageError(f"{record.name} 写不进去（{exc}）：原文件保持不变，修好环境后重跑原操作即可补记") from exc


# ---------------------------------------------------------------------------
# 初始化输入与环境

def read_input(feature_root: Path) -> tuple[dict | None, list[str]]:
    """`.usage-input.json`：requirement、name、version 必有（version 可为 null 表示已判断未知），agent/model 可空。"""
    path = feature_root / CONTRACT["input_file"]
    if not path.is_file():
        return None, []
    where = f"{feature_root.name}/{path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, [f"{where} 读不出（{exc}）"]
    if not isinstance(data, dict):
        return None, [f"{where} 不是 JSON 对象"]
    bad = [f"缺 {k}" for k in CONTRACT["input"]["required"] if k not in data]
    text = lambda v: isinstance(v, str) and bool(v.strip())  # noqa: E731
    if "requirement" in data and not text(data["requirement"]):
        bad.append("requirement 要是非空文字")
    if "name" in data and not text(data["name"]):
        bad.append("name 要是非空文字")
    if "version" in data and not (data["version"] is None or text(data["version"])):
        bad.append("version 要是非空文字，或 null 表示已判断为未知")
    bad += [f"{k} 要是文字或 null" for k in CONTRACT["input"]["optional"]
            if k in data and not (data[k] is None or isinstance(data[k], str))]
    if bad:
        return None, [f"{where}：{'；'.join(bad)}——字段合同见 doc/extensions/skills/story/contracts/usage.json，修好后重跑原操作"]
    return data, []


def versions(project_root: Path) -> tuple[str | None, str | None]:
    """实际安装的 Framework（框架根 package.json）与 Extension（已安装 manifest）版本；读不到为 null。"""
    fw = None
    root = next((r for r in (project_root / "framework", project_root)
                 if (r / "skills").exists() or (r / "workflows").exists()), None)
    if root is not None:
        try:
            fw = json.loads((root / "package.json").read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            fw = None
    try:
        m = re.search(r'^version:\s*"?([^"\s]+)"?', (EXT_ROOT / "manifest.yaml").read_text(encoding="utf-8"), re.M)
    except OSError:
        m = None
    return fw, (m.group(1) if m else None)


# ---------------------------------------------------------------------------
# 终态事件与结算

def events(project_root: Path, features: list[str], step: str) -> tuple[list[dict], str | None, list[str]]:
    """这个步骤在已登记 features 上的终态事件、当前检查结论与读不出的证据。"""
    found, verdict, errors = [], None, []
    base = project_root / importer.features_dir(project_root)
    for feature in features:
        fr = base / feature
        try:
            if step in phase_facts.PHASES:
                s = phase_facts.summary(fr, step)
                if s["state"] == "unreadable":
                    errors.append(f"{s['path'].as_posix()} 读不出（{s['why']}）：{step} 的结果判不了")
                elif s["state"] != "missing":
                    verdict = s["data"].get("verdict") or verdict
                found += [e for e in [phase_facts.closure_event(fr, step)] if e]
            elif step == "story":
                contract = state.load(fr) or {}
                written = phase_facts.moment(contract.get("story_written_at"))
                spec = phase_facts.closure_event(fr, "spec")
                if contract.get("status") == "story_written" and written and spec:
                    found.append(phase_facts.event("story", "complete", max(written, spec["ended_at"]),
                                                   fr.resolve().as_posix(), contract["story_written_at"], spec["id"]))
            else:
                for rid, rec in phase_facts.update_records(fr):
                    if rec.get("kind") == "story_baseline":
                        continue
                    kind, at = {"closed": ("complete", rec.get("closed_at")),
                                "restored": ("abort", rec.get("restored_at"))}.get(rec.get("status"), (None, None))
                    at = phase_facts.moment(at)
                    if kind and at:
                        found.append(phase_facts.event("update", kind, at, fr.resolve().as_posix(), rid))
        except (state.FlowError, importer.ImportError_) as exc:
            errors.append(str(exc))
    return found, verdict, errors


def take_terminal(entry: dict, found: list[dict], sources: int) -> None:
    """按终态游标结算一个步骤（规则见模块说明与 S1 §4）。

    只采纳严格晚于游标的终态；与游标同一时刻的别的终态分不出先后，是稳定的未知边界：
    完成事实照记、耗时记未知、游标不动，再对账字节不变。起点只有一个、不带来源，
    所以需求关联了多个 feature 时，起点与终态是否同属一个来源证明不了，耗时一律未知。
    """
    cur = entry["last_result"]
    cur_at = phase_facts.moment(cur["ended_at"]) if cur else None
    ties = [e for e in found if cur and e["id"] != cur["id"] and e["ended_at"] == cur_at]
    if ties:
        entry["completed"] = entry["completed"] or any(e["kind"] == "complete" for e in ties)
        entry["spent"] = None
    fresh = sorted((e for e in found if cur is None or (e["id"] != cur["id"] and e["ended_at"] > cur_at)),
                   key=lambda e: (e["ended_at"], e["id"]))
    if not fresh:
        return
    last, start = fresh[-1], phase_facts.moment(entry["start"])
    if any(e["kind"] == "complete" for e in fresh):
        entry["completed"] = True
        if last["kind"] == "complete" and entry["verdict"] is None:
            entry["verdict"] = "PASS"
    proven = len(fresh) == 1 and sources == 1
    if start is not None and last["ended_at"] < start:
        entry["spent"] = None                       # 早于本轮起点的旧终态：只补历史，不结束本轮
    elif start is None:
        if last["kind"] == "complete":
            entry["spent"] = None                   # 有完成、没有本轮起点：完成成立，耗时未知
    else:
        if proven and isinstance(entry["spent"], int):
            entry["spent"] += int((last["ended_at"] - start).total_seconds())
        else:
            entry["spent"] = None                   # 区间归属证明不了
        entry["start"] = None
    entry["last_result"] = {"id": last["id"], "ended_at": iso(last["ended_at"])}


def reconcile_node(project_root: Path, node: dict, steps: list[str], errors: list[str]) -> None:
    for step in steps:
        entry = node["steps"].get(step)
        if entry is None:
            continue
        found, verdict, bad = events(project_root, node["features"], step)
        errors += bad
        if verdict is not None:
            entry["verdict"] = verdict
        take_terminal(entry, found, len(node["features"]))


# ---------------------------------------------------------------------------
# 动作

def apply(project_root: Path, data: dict, req: dict, errors: list[str]) -> tuple[str | None, Path | None]:
    """在已读出的 usage 上执行一个动作；返回需求键与本次已接收、待清理的初始化输入。"""
    action, feature, step = req.get("action"), req.get("feature"), req.get("step")
    reqs = data["requirements"]
    owner = next((k for k, v in reqs.items() if feature and feature in v.get("features", [])), None)
    if action == "reconcile":
        keys = [req.get("requirement") or owner] if (req.get("requirement") or feature) else list(reqs)
        for key in [k for k in keys if k in reqs]:
            reconcile_node(project_root, reqs[key], STEPS, errors)
        return (keys[0] if len(keys) == 1 else None), None
    if not feature or step not in STEPS:
        raise UsageError(f"{action} 要 feature 与 step（{' / '.join(STEPS)}）")
    if action in ("finish-own", "abort-own") and step not in OWN:
        raise UsageError(f"{action} 只结算 Story 自有步骤（{' / '.join(sorted(OWN))}）")
    fr = project_root / importer.features_dir(project_root) / feature
    given, problems = read_input(fr)
    errors += problems
    key = req.get("requirement") or owner or (given or {}).get("requirement") or feature
    if owner and owner != key:
        raise UsageError(f"feature {feature} 已属于需求 {owner}，这次给的是 {key}：不跨需求改写")
    if given and given["requirement"] != key:
        errors.append(f"{feature}/{CONTRACT['input_file']} 写的需求是 {given['requirement']}，实际是 {key}：不接收")
        given = None
    node = reqs.get(key)
    if node is None:
        fw, ext = versions(project_root)
        raw = given or {}
        node = reqs[key] = {"name": None, "version": None, "fw": fw, "ext": ext,
                            "agent": raw.get("agent"), "model": raw.get("model"), "features": [], "steps": {}}
    if feature not in node["features"]:
        node["features"].append(feature)
    consumed = None
    if given:
        if node["name"] is None:
            node["name"], node["version"] = given["name"].strip(), given["version"]
            consumed = fr / CONTRACT["input_file"]
        elif (node["name"], node["version"]) == (given["name"].strip(), given["version"]):
            consumed = fr / CONTRACT["input_file"]
        else:
            errors.append(f"{key} 的名称与业务版本已固定为 {node['name']} / {node['version']}：初始化输入不覆盖")
    entry = node["steps"].setdefault(step, {"start": None, "spent": None, "verdict": None,
                                            "completed": False, "last_result": None})
    reconcile_node(project_root, node, STEPS if action in ("observe", "begin") else [step], errors)
    if action == "begin" and entry["start"] is None:
        if entry["spent"] is None and entry["last_result"] is None:
            entry["spent"] = 0      # 还没有任何结束的轮次：已结束累计是 0，不是未知
        entry["start"] = iso(now().replace(microsecond=0))   # 起点取整秒（不晚于实际开始）：原生结束时刻最细到秒的也比得上
    return key, consumed


#: Story 命令 → 使用记录动作：init/round 记使用，story 登记后结算成文，update 起手与开轮是起点、
#: 关轮结算、撤回终止，status 与归档只对账已有记录
COMMANDS = {"init": ("observe", "story"), "round": ("observe", "story"), "story": ("finish-own", "story"),
            "status": ("reconcile", None), "archived": ("reconcile", None),
            "update:inputs": ("begin", "story update"), "update:prepare": ("begin", "story update"),
            "update:close": ("finish-own", "story update"), "update:restore": ("abort-own", "story update"),
            "update:status": ("reconcile", None)}


def after_command(project_root: Path, feature: str, mode: str, action: str | None = None) -> list[str]:
    """Story 命令成功之后的采集；返回记录错误（业务结果不受影响，另列给调用方）。"""
    act = COMMANDS.get(f"{mode}:{action}" if mode == "update" else mode)
    return record(project_root, act[0], feature=feature, step=act[1])["errors"] if act else []


def record(project_root: Path, action: str, *, feature: str | None = None, step: str | None = None,
           requirement: str | None = None) -> dict:
    """执行一个动作并原子落盘；失败不改原文件。返回 `{ok, changed, errors, requirement, pending_init}`。"""
    out = {"ok": False, "changed": False, "errors": [], "requirement": None, "pending_init": False}
    if action not in ACTIONS:
        out["errors"].append(f"未知动作 {action}：可用 {' / '.join(ACTIONS)}")
        return out
    path = Path(project_root) / Path(*CONTRACT["record"].split("/"))
    if action in ("ensure", "inspect"):
        return ensure(path, out) if action == "ensure" else inspect(path, out)
    if action == "reconcile" and not path.exists():
        out["ok"] = True            # 对账不创造记录：没有 usage 就没有要补的事实，也不建锁
        return out
    try:
        with locked(path):
            data = load(path)
            before = json.dumps(data, sort_keys=True)
            key, consumed = apply(Path(project_root), data, {"action": action, "feature": feature, "step": step,
                                                            "requirement": requirement}, out["errors"])
            if json.dumps(data, sort_keys=True) != before:
                save(path, data)
                out["changed"] = True
            if consumed is not None:
                consumed.unlink(missing_ok=True)
    except UsageError as exc:
        out["errors"].append(str(exc))
        return out
    except OSError as exc:      # 文件系统层面的失败（权限、占用）：记录没做成，原业务结果不受影响
        out["errors"].append(f"使用记录没写成（{exc}）：修好环境后重跑原操作即可补记")
        return out
    node = data["requirements"].get(key) if key else None
    out.update(ok=not out["errors"], requirement=key, pending_init=bool(node) and node["name"] is None)
    return out


def ensure(path: Path, out: dict) -> dict:
    """锁内重判：缺文件就以空表原子建立；已有文件只按合同校验，一个字节不改。"""
    try:
        with locked(path):
            if path.exists():
                parse(path.read_bytes(), path.name)
            else:
                save(path, load(path))
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
    ap = argparse.ArgumentParser(description="使用记录（内部入口，stdin 一个 JSON）")
    ap.add_argument("--project-root", required=True)
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except ValueError as exc:
        print(json.dumps({"ok": False, "changed": False, "errors": [f"stdin 不是 JSON（{exc}）"]}, ensure_ascii=False))
        return 2
    out = record(Path(args.project_root), str(req.get("action")), feature=req.get("feature"),
                 step=req.get("step"), requirement=req.get("requirement"))
    print(json.dumps(out, ensure_ascii=False))
    for err in out["errors"]:
        print(f"[usage] {err}", file=sys.stderr)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
