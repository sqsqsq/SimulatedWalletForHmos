"""测试专用：把测试里起的产品命令放进测试进程里执行——node 命令交给本测试进程的 node 宿主（`node_host.mjs`），
Python 流程脚本直接在本进程里按 `__main__` 执行（它内部再起的 node 命令经同一处交给宿主）。

conftest.py 导入它即生效：替换 `subprocess.run`，只转下列形态，其余一律照原样起进程——
- `python <产品脚本.py> 参数…`（解释器是 python 或本进程的解释器，脚本在 `extensions/skills` 或 `extensions/hooks` 下，不带解释器参数）；
- `node <脚本.mjs> 参数…`（脚本不在 node_modules 下）与 `node --input-type=module -e <正文> 参数…`，不带别的 node 参数；
- 没给 `input` / `stdin`，没开 `shell`，`stdout` / `stderr` 只是 PIPE、STDOUT、DEVNULL 或不给；
- 给了 `env` 时其中的 `NODE_OPTIONS` 与本进程一致（要对照「关掉某个预载」的用例自动走真实进程）；
- 当前用例没有声明 `REAL_CLI = True`（进程边界本身的见证）；
- 调用发生在主线程（用例自己开线程并发起命令，比的就是多个进程同时跑）。

`STORY_TEST_NODE_HOST=0` 时一律走真实进程。`STORY_TEST_NODE_HOST_LOG=<目录>` 时，凡符合上面形态的调用（不论这次走哪条路）
都记一行归一化的结果，两轮全量比对宿主与命令行是否等价（TEST §5「进程内宿主」）。产品运行不经过这里。
"""
from __future__ import annotations

import atexit
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import types
from pathlib import Path

HOST_SCRIPT = Path(__file__).with_name("node_host.mjs")
ENABLED = os.environ.get("STORY_TEST_NODE_HOST", "1") != "0"
LOG_DIR = os.environ.get("STORY_TEST_NODE_HOST_LOG")
#: 宿主执行这么多条请求后在请求之间重启：每条请求一份新的 ESM 模块，进程里的模块只增不减（实测每条约 2.3 MB，60 条约 400 MB）
RESTART_AFTER = int(os.environ.get("STORY_TEST_NODE_HOST_JOBS", "60"))
DEFAULT_TIMEOUT = 600

_real_run = subprocess.run
#: 宿主起在固定的 cwd 与导入时的环境下：它可能在进程内执行的 Python 脚本里第一次被用到，不能继承那条请求的 cwd 与 env
_HOME_ENV = dict(os.environ)
_HOME_CWD = str(HOST_SCRIPT.parent)
_FREE_STREAMS = (None, subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL)

#: 当前用例是不是进程边界见证（conftest 每条用例开始时设）
real_cli = False
#: 本进程交给宿主执行的请求数（conftest 按用例计数）
jobs = 0
#: 正在进程内执行的 Python 脚本层数：脚本内部起的命令不记比对日志（命令行轮里它们在子进程里，不经过这里）
_depth = 0


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


_PYTHONS = {"python", "python.exe", "python3", "python3.exe"}


def _product_script(path: str) -> bool:
    norm = path.replace("\\", "/")
    return norm.endswith(".py") and ("/extensions/skills/" in norm or "/extensions/hooks/" in norm)


def _python_request(args, kwargs: dict) -> dict | None:
    """`python <产品脚本.py> 参数…` 能不能在本进程里执行：能就回请求，不能回 None。"""
    if not isinstance(args, (list, tuple)) or len(args) < 2:
        return None
    exe = str(args[0])
    if Path(exe).name.lower() not in _PYTHONS and os.path.normcase(exe) != os.path.normcase(sys.executable):
        return None
    if kwargs.get("input") is not None or kwargs.get("stdin") is not None or kwargs.get("shell"):
        return None
    if kwargs.get("stdout") not in _FREE_STREAMS or kwargs.get("stderr") not in _FREE_STREAMS:
        return None
    a = [str(x) for x in args]
    cwd = str(kwargs.get("cwd") or os.getcwd())
    script = os.path.join(cwd, a[1])
    if a[1].startswith("-") or not _product_script(script) or not os.path.isfile(script):
        return None          # 脚本不存在时由真实进程报，与命令行同一句
    env = kwargs.get("env")
    return {"kind": "python", "argv": a[1:], "cwd": cwd,
            "env": {str(k): str(v) for k, v in (env if env is not None else os.environ).items()}}


def _product_module(module) -> bool:
    where = getattr(module, "__file__", None) or next(iter(getattr(module, "__path__", []) or []), None)
    return bool(where) and ("/extensions/skills/" in str(where).replace("\\", "/") or "/extensions/hooks/" in str(where).replace("\\", "/"))


def _run_python(req: dict) -> dict:
    """在本进程里按命令行的样子执行一个产品 Python 脚本，回 {returncode, stdout, stderr}。

    argv、sys.path（脚本目录排首位）、cwd、env 设好再还原；stdout / stderr 换成 UTF-8 的 TextIOWrapper（产品会 reconfigure）；
    已加载的产品模块先收起，脚本导入全新的一份，结束后丢掉、放回原来的——产品模块级状态与每条命令一个进程时一样从零开始。
    """
    global _depth
    script = os.path.normpath(os.path.join(req["cwd"], req["argv"][0]))      # 相对路径按本次 cwd，与按脚本运行一致
    saved_argv, saved_path, saved_cwd = sys.argv, list(sys.path), os.getcwd()
    saved_env = dict(os.environ)
    saved_out, saved_err, saved_main = sys.stdout, sys.stderr, sys.modules["__main__"]
    stash = {name: m for name, m in list(sys.modules.items()) if _product_module(m)}
    for name in stash:
        del sys.modules[name]
    out, err = io.BytesIO(), io.BytesIO()
    wrapped = (io.TextIOWrapper(out, encoding="utf-8", errors="replace", write_through=True),
               io.TextIOWrapper(err, encoding="utf-8", errors="replace", write_through=True))
    sys.stdout, sys.stderr = wrapped
    code = 0
    _depth += 1
    try:
        os.environ.clear()
        os.environ.update(req["env"])
        os.chdir(req["cwd"])
        sys.argv = list(req["argv"])                   # 命令行里 argv[0] 照给的写法，__file__ 是绝对路径
        sys.path[:0] = [os.path.dirname(script)]
        main = types.ModuleType("__main__")
        main.__file__ = script
        sys.modules["__main__"] = main
        with open(script, "rb") as f:
            source = f.read()
        exec(compile(source, script, "exec"), main.__dict__)
    except SystemExit as e:
        if e.code is None:
            code = 0
        elif isinstance(e.code, int):
            code = e.code
        else:
            print(e.code, file=sys.stderr)
            code = 1
    except BaseException:  # noqa: BLE001 —— 命令行里同样是打出 traceback、以 1 结束
        traceback.print_exc(file=sys.stderr)
        code = 1
    finally:
        _depth -= 1
        for stream in wrapped:
            try:
                stream.flush()
                stream.detach()      # 撤下包装，不让它关掉底下收输出的缓冲
            except Exception:  # noqa: BLE001 —— 产品自己关了流也不影响取输出
                pass
        sys.stdout, sys.stderr = saved_out, saved_err
        sys.modules["__main__"] = saved_main
        sys.argv = saved_argv
        sys.path[:] = saved_path
        os.chdir(saved_cwd)
        os.environ.clear()
        os.environ.update(saved_env)
        for name in [n for n, m in list(sys.modules.items()) if _product_module(m)]:
            del sys.modules[name]
        sys.modules.update(stash)
    return {"returncode": code, "stdout": out.getvalue().decode("utf-8", "replace"),
            "stderr": err.getvalue().decode("utf-8", "replace")}


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


_SEP = r"(?:\\\\|\\|/)+"           # 一个或两个反斜杠（JSON 里转义过的）或斜杠
_TMP = _SEP.join(re.escape(part) for part in re.split(r"[\\/]+", tempfile.gettempdir()) if part)
_NORMALIZE = (
    (re.compile(r"(?:file:/+)?" + _TMP + _SEP + r"[^\\/\s'\"`|,;:)\]]+", re.IGNORECASE), "<TMP>"),
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
    entry = "eval:" + req["source"][:60] if req["kind"] == "eval" else req["argv"][0]
    rec = {"test": test, "i": _calls[test], "via": via, "entry": _norm(entry), "args": [_norm(x) for x in req["argv"][1:4]],
           "rc": proc.returncode, "ms": round(ms, 1), "stdout": _norm(proc.stdout), "stderr": _norm(proc.stderr)}
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    with open(Path(LOG_DIR) / f"{os.getpid()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(args, *popenargs, **kwargs):
    global jobs
    req = None if popenargs else (_request(args, kwargs) or _python_request(args, kwargs))
    if req is None:
        return _real_run(args, *popenargs, **kwargs)
    started = time.perf_counter()
    if ENABLED and not real_cli and threading.current_thread() is threading.main_thread():
        jobs += 1
        got = _run_python(req) if req["kind"] == "python" else _host.ask(req, kwargs.get("timeout"))
        proc = _completed(args, kwargs, got)
        via = "host"
    else:
        proc = _real_run(args, **kwargs)
        via = "cli"
    if LOG_DIR and not _depth:
        _log(req, proc, via, (time.perf_counter() - started) * 1000)
    return proc


subprocess.run = run
