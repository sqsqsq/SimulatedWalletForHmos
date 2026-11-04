"""测试专用：把测试里起的 node 产品命令转给本测试进程的 node 宿主（`node_host.mjs`）在进程内执行。

conftest.py 导入它即生效：替换 `subprocess.run`，只转下列形态，其余一律照原样起进程——
- `node <脚本.mjs> 参数…`（脚本不在 node_modules 下）与 `node --input-type=module -e <正文> 参数…`，不带别的 node 参数；
- 没给 `input` / `stdin`，没开 `shell`，`stdout` / `stderr` 只是 PIPE、STDOUT、DEVNULL 或不给；
- 给了 `env` 时其中的 `NODE_OPTIONS` 与本进程一致（要对照「关掉某个预载」的用例自动走真实进程）；
- 当前用例没有声明 `REAL_CLI = True`（进程边界本身的见证）。

`STORY_TEST_NODE_HOST=0` 时一律走真实进程。`STORY_TEST_NODE_HOST_LOG=<目录>` 时，凡符合上面形态的调用（不论这次走哪条路）
都记一行归一化的结果，两轮全量比对宿主与命令行是否等价（TEST §5「进程内宿主」）。产品运行不经过这里。
"""
from __future__ import annotations

import atexit
import json
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
        env = dict(os.environ)
        options = env.get("NODE_OPTIONS", "")
        hit = re.search(r'--require\s+"([^"]*ts_transpile_cache\.cjs)"', options)
        if hit:
            env["NODE_OPTIONS"] = (options[:hit.start()] + options[hit.end():]).strip()
            env["STORY_NODE_HOST_PRELOAD"] = hit.group(1)
        self.proc = subprocess.Popen(["node", str(HOST_SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     env=env)
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
    if text:   # 文本模式下 subprocess 做通用换行转换
        out, err = (s.replace("\r\n", "\n").replace("\r", "\n") for s in (out, err))
    so, se = kwargs.get("stdout"), kwargs.get("stderr")
    if kwargs.get("capture_output"):
        so = se = subprocess.PIPE
    if se == subprocess.STDOUT:
        out, err, se = out + err, "", None
        so = so if so is not None else subprocess.PIPE
    conv = (lambda s: s) if text else (lambda s: s.encode("utf-8"))
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


_TMP = re.escape(tempfile.gettempdir()).replace(r"\\", r"[\\/]+").replace("/", r"[\\/]+")
_NORMALIZE = (
    (re.compile(_TMP + r"[\\/]+[^\\/\s'\"`|,;:)\]]+", re.IGNORECASE), "<TMP>"),
    (re.compile(re.escape(tempfile.gettempdir().replace("\\", "/")) + r"/+[^/\s'\"`|,;:)\]]+", re.IGNORECASE), "<TMP>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:?\d{2}|Z)?"), "<TS>"),
)


def _norm(text) -> str:
    text = text.decode("utf-8", "replace") if isinstance(text, bytes) else str(text or "")
    for pattern, repl in _NORMALIZE:
        text = pattern.sub(repl, text)
    return text.replace("\r\n", "\n")


_calls: dict[str, int] = {}


def _log(req: dict, proc: subprocess.CompletedProcess, via: str, ms: float) -> None:
    test = (os.environ.get("PYTEST_CURRENT_TEST") or "").rsplit(" (", 1)[0]
    _calls[test] = _calls.get(test, 0) + 1
    entry = req["argv"][0] if req["kind"] == "script" else "eval:" + req["source"][:60]
    rec = {"test": test, "i": _calls[test], "via": via, "entry": _norm(entry), "args": [_norm(x) for x in req["argv"][1:4]],
           "rc": proc.returncode, "ms": round(ms, 1), "stdout": _norm(proc.stdout), "stderr": _norm(proc.stderr)}
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    with open(Path(LOG_DIR) / f"{os.getpid()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(args, *popenargs, **kwargs):
    global jobs
    req = None if popenargs else _request(args, kwargs)
    if req is None:
        return _real_run(args, *popenargs, **kwargs)
    started = time.perf_counter()
    if ENABLED and not real_cli:
        jobs += 1
        proc = _completed(args, kwargs, _host.ask(req, kwargs.get("timeout")))
        via = "host"
    else:
        proc = _real_run(args, **kwargs)
        via = "cli"
    if LOG_DIR:
        _log(req, proc, via, (time.perf_counter() - started) * 1000)
    return proc


subprocess.run = run
