"""测试专用：把测试里起的 node 产品命令转给本测试进程的 node 宿主（`node_host.mjs`）在进程内执行。

conftest.py 导入它即生效：替换 `subprocess.run`，只转下列形态，其余（含全部 Python 命令）一律照原样起真实进程——
- `node <脚本.mjs> 参数…`（脚本不在 node_modules 下）与 `node --input-type=module -e <正文> 参数…`，不带别的 node 参数；
- 没给 `input` / `stdin`，没开 `shell`，`stdout` / `stderr` 只是 PIPE、STDOUT、DEVNULL 或不给；
- 给了 `env` 时其中的 `NODE_OPTIONS` 与本进程一致（要对照「关掉某个预载」的用例自动走真实进程）；
- 当前用例没有声明 `REAL_CLI = True`（进程边界本身的见证）；
- 调用发生在主线程（宿主一次只执行一条请求；用例自己开线程并发起命令，比的就是多个进程同时跑）。

`STORY_TEST_NODE_HOST=0` 时一律走真实进程。`STORY_TEST_NODE_HOST_LOG=<目录>` 时，凡符合上面形态的调用（不论这次走哪条路）
都记一行：用例与阶段、完整的命令身份（入口与其字节摘要、全部参数、内联正文的摘要与原文、cwd、调用选项、显式改过的环境），
原始输出与只换掉临时根和仓根的归一结果分开记，供两轮全量逐条比对（TEST §5「进程内宿主」）。产品运行不经过这里。
"""
from __future__ import annotations

import atexit
import hashlib
import json
import locale
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HOST_SCRIPT = Path(__file__).with_name("node_host.mjs")
ENABLED = os.environ.get("STORY_TEST_NODE_HOST", "1") != "0"
LOG_DIR = os.environ.get("STORY_TEST_NODE_HOST_LOG")
#: 宿主执行这么多条请求后在请求之间重启：每条请求一份新的 ESM 模块，进程里的模块只增不减（实测每条约 2.3 MB，60 条约 400 MB）
RESTART_AFTER = int(os.environ.get("STORY_TEST_NODE_HOST_JOBS", "60"))
DEFAULT_TIMEOUT = 600

_real_run = subprocess.run
#: 宿主起在固定的 cwd 与导入时的环境下：它在请求之间重启，不能继承用例那时临时切进去的 cwd 与改过的 env
#: （继承了 cwd，Windows 上那个目录就删不掉）
_HOME_ENV = dict(os.environ)
_HOME_CWD = str(HOST_SCRIPT.parent)
_FREE_STREAMS = (None, subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL)

#: 当前用例是不是进程边界见证（conftest 每条用例开始时设）
real_cli = False
#: 本进程交给宿主执行的请求数（conftest 按用例计数）
jobs = 0


class _Host:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.served = 0

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 —— 退不干净就强制结束，测试进程反正要退出
                self.proc.kill()
        self.proc = None

    def start(self) -> None:
        self.stop()
        # 测试转译缓存的预载由宿主每条请求重新执行一次（与每个命令行进程一样只拦第一次 require('ts-node')），宿主自己不带它起
        env = dict(_HOME_ENV)
        options = env.get("NODE_OPTIONS", "")
        hit = re.search(r'--require\s+"([^"]*ts_transpile_cache\.cjs)"', options)
        if hit:
            env["NODE_OPTIONS"] = (options[:hit.start()] + options[hit.end():]).strip()
            env["STORY_NODE_HOST_PRELOAD"] = hit.group(1)
        self.proc = subprocess.Popen(["node", str(HOST_SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     env=env, cwd=_HOME_CWD)
        self.served = 0

    def ask(self, request: dict, timeout: float | None) -> dict:
        if self.proc is None or self.proc.poll() is not None or self.served >= RESTART_AFTER:
            self.start()
        self.served += 1
        self.proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        box: dict = {}
        reader = threading.Thread(target=lambda: box.setdefault("line", self.proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(timeout or DEFAULT_TIMEOUT)
        if reader.is_alive():
            self.proc.kill()
            self.proc = None
            raise subprocess.TimeoutExpired(request.get("argv") or ["node", "-e"], timeout or DEFAULT_TIMEOUT)
        line = box.get("line")
        if not line:
            self.proc = None
            raise RuntimeError("node 宿主中途退出（不是产品结论）")
        got = json.loads(line)
        if "fault" in got:
            raise RuntimeError(f"node 宿主自身出错（不是产品结论）：{got['fault']}")
        return got


_host = _Host()
atexit.register(_host.stop)


def _request(args, kwargs: dict) -> dict | None:
    """这次调用能不能交给宿主：能就回请求，不能回 None。"""
    if not isinstance(args, (list, tuple)) or len(args) < 2:
        return None
    if Path(str(args[0])).name.lower() not in ("node", "node.exe"):
        return None
    if kwargs.get("input") is not None or kwargs.get("stdin") is not None or kwargs.get("shell"):
        return None
    if kwargs.get("stdout") not in _FREE_STREAMS or kwargs.get("stderr") not in _FREE_STREAMS:
        return None
    env = kwargs.get("env")
    if env is not None and env.get("NODE_OPTIONS") != os.environ.get("NODE_OPTIONS"):
        return None
    a = [str(x) for x in args]
    if a[1] == "--input-type=module" and len(a) >= 4 and a[2] == "-e":
        rest = a[4:]
        if rest[:1] == ["--"]:
            rest = rest[1:]
        req = {"kind": "eval", "source": a[3], "argv": rest}
    elif a[1].startswith("-") or not a[1].endswith(".mjs") or "node_modules" in a[1].replace("\\", "/"):
        return None
    else:
        req = {"kind": "script", "argv": a[1:]}
    req["cwd"] = str(kwargs.get("cwd") or os.getcwd())
    req["env"] = {str(k): str(v) for k, v in (env if env is not None else os.environ).items()}
    return req


def _text_mode(kwargs: dict) -> bool:
    return bool(kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding") or kwargs.get("errors"))


def _completed(args, kwargs: dict, got: dict) -> subprocess.CompletedProcess:
    """宿主的结果按调用方要的形态交回：与 subprocess.run 对同一个进程的结果一致。"""
    text = _text_mode(kwargs)
    out, err = got["stdout"], got["stderr"]
    so, se = kwargs.get("stdout"), kwargs.get("stderr")
    if kwargs.get("capture_output"):
        so = se = subprocess.PIPE
    if se == subprocess.STDOUT:
        out, err, se = out + err, "", None
        so = so if so is not None else subprocess.PIPE
    if text:
        # 与 subprocess 读同一份字节：按调用给的 encoding（没给就是本机区域编码）与 errors 解码、做通用换行转换。
        # 解不开时 Windows 上 subprocess 的读取线程出错、那一路得到 None，这里同样给 None——不替被测命令把输出“修好”
        encoding = kwargs.get("encoding") or ("utf-8" if sys.flags.utf8_mode else locale.getencoding())
        errors = kwargs.get("errors") or "strict"

        def conv(s: str) -> str | None:
            try:
                return s.encode("utf-8").decode(encoding, errors).replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                return None
    else:
        def conv(s: str) -> bytes:
            return s.encode("utf-8")
    stdout = conv(out) if so == subprocess.PIPE else None
    stderr = conv(err) if se == subprocess.PIPE else None
    if so is None and out:
        sys.stdout.write(out)
    if se is None and err:
        sys.stderr.write(err)
    proc = subprocess.CompletedProcess(args, got["returncode"], stdout, stderr)
    if kwargs.get("check") and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, args, stdout, stderr)
    return proc


_SEP = r"(?:\\\\|\\|/)+"           # 一个或两个反斜杠（JSON 里转义过的）或斜杠
_TMP_ROOT = re.compile(r"(?:file:/+)?" + _SEP.join(re.escape(part) for part in re.split(r"[\\/]+", tempfile.gettempdir()) if part)
                       + _SEP + r"([^\\/\s'\"`|,;:)\]]+)", re.IGNORECASE)
_REPO = re.compile(_SEP.join(re.escape(part) for part in re.split(r"[\\/]+", str(HOST_SCRIPT.parents[2])) if part), re.IGNORECASE)
#: 每个用例里出现过的临时根（系统临时目录下的第一层）按出现先后编号：同一用例里不同的根仍可区分，两轮按顺序对应
_roots: dict[str, dict[str, str]] = {}
_calls: dict[str, int] = {}


def _norm(text, test: str) -> str:
    """只换掉每轮必然不同的位置：本用例的临时根换成 <TMPn>（原值记在 roots 里），仓根换成 <REPO>；正文其余照旧。"""
    text = text.decode("utf-8", "replace") if isinstance(text, bytes) else str(text or "")
    roots = _roots.setdefault(test, {})

    def root(m: re.Match) -> str:
        key = m.group(1).lower()
        if key not in roots:
            roots[key] = f"<TMP{len(roots) + 1}>"
        return roots[key]
    return _REPO.sub("<REPO>", _TMP_ROOT.sub(root, text))


def _digest(data: bytes | str) -> str:
    return "sha256:" + hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def _log(req: dict, args, kwargs: dict, rc, out, err, via: str, ms: float) -> None:
    """记一条调用：用例与阶段、本用例里的第几次、走哪条路，完整的命令身份与调用选项，原始输出与归一结果分开记。"""
    current = os.environ.get("PYTEST_CURRENT_TEST") or ""
    test, _, phase = current.rpartition(" (")
    test, phase = (test, phase.rstrip(")")) if test else (current, "")
    _calls[test] = _calls.get(test, 0) + 1
    log = Path(LOG_DIR)
    log.mkdir(parents=True, exist_ok=True)
    if req["kind"] == "eval":
        # 身份取归一后正文的摘要（正文里常嵌着本轮的临时路径）；原文按原始摘要另存一份，entry_bytes 指向它
        entry = "eval:" + _digest(_norm(req["source"], test))
        entry_bytes = _digest(req["source"])
        source = log / "eval" / (entry_bytes.split(":", 1)[1] + ".mjs")
        if not source.exists():
            source.parent.mkdir(exist_ok=True)
            source.write_text(req["source"], encoding="utf-8")
    else:
        script = Path(req["cwd"], req["argv"][0])
        entry = str(script.resolve()) if script.exists() else req["argv"][0]
        entry_bytes = _digest(script.read_bytes()) if script.is_file() else None
    env = kwargs.get("env")
    overrides = {}
    if env is not None:
        for k in sorted(set(env) | set(os.environ)):
            if env.get(k) != os.environ.get(k):
                v = env.get(k)
                overrides[k] = None if v is None else (_norm(v, test) if k.startswith("STORY_") else _digest(v)[:19])
    options = {k: kwargs[k] for k in ("text", "universal_newlines", "encoding", "errors", "timeout", "check", "capture_output")
               if kwargs.get(k) is not None}
    for k in ("stdout", "stderr"):
        if kwargs.get(k) is not None:
            options[k] = {subprocess.PIPE: "PIPE", subprocess.STDOUT: "STDOUT", subprocess.DEVNULL: "DEVNULL"}.get(kwargs[k], "other")
    raw = {"stdout": out.decode("utf-8", "replace") if isinstance(out, bytes) else out,
           "stderr": err.decode("utf-8", "replace") if isinstance(err, bytes) else err}
    rec = {"test": test, "phase": phase, "i": _calls[test], "via": via, "rc": rc, "ms": round(ms, 1),
           "kind": req["kind"], "entry": _norm(entry, test), "entry_bytes": entry_bytes,
           "argv": [_norm(x, test) for x in (req["argv"] if req["kind"] == "eval" else req["argv"][1:])],
           "cwd": _norm(req["cwd"], test), "options": options, "env": overrides,
           "raw": raw, "norm": {k: None if v is None else _norm(v, test).replace("\r\n", "\n") for k, v in raw.items()},
           "roots": {v: k for k, v in _roots.get(test, {}).items()}}
    with open(log / f"{os.getpid()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(args, *popenargs, **kwargs):
    global jobs
    req = None if popenargs else _request(args, kwargs)
    if req is None:
        return _real_run(args, *popenargs, **kwargs)
    started = time.perf_counter()
    host = ENABLED and not real_cli and threading.current_thread() is threading.main_thread()
    via = "host" if host else "cli"
    try:
        if host:
            jobs += 1
            proc = _completed(args, kwargs, _host.ask(req, kwargs.get("timeout")))
        else:
            proc = _real_run(args, **kwargs)
    except subprocess.CalledProcessError as e:        # check=True 的失败：照样记下再抛给调用方
        if LOG_DIR:
            _log(req, args, kwargs, e.returncode, e.stdout, e.stderr, via, (time.perf_counter() - started) * 1000)
        raise
    except subprocess.TimeoutExpired as e:
        if LOG_DIR:
            _log(req, args, kwargs, "timeout", e.stdout, e.stderr, via, (time.perf_counter() - started) * 1000)
        raise
    if LOG_DIR:
        _log(req, args, kwargs, proc.returncode, proc.stdout, proc.stderr, via, (time.perf_counter() - started) * 1000)
    return proc


subprocess.run = run
