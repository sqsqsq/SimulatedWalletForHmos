"""离线夹具的 framework 依赖：临时工程根下接一条指向真实 `yaml` 包的链接。

扩展的 YAML 读取器（`hooks/shared/yaml.mjs`）借 framework harness 的 `yaml` 包：从自己的位置向上找
`framework.config.json` 定工程根，再从 `<根>/framework/harness` 取包。把扩展拷进临时根再起 node 的
套件，临时根下没有 harness，第一次解析会按设计抛错。这里不复制 node_modules、不在测试里退回别的读法，
只给临时根一条指向真实 `yaml` 包的 junction（Windows）或符号链接；`TemporaryDirectory` 清理时链接本身
被删，真实目录不动。

**只链接 yaml 包这一个目录**，不把整个 `framework/harness` 链过去：有的套件会往临时根的
`framework/harness/…` 放替身（比如 ts-node 的替身 runner、空的 check-receipt.ts），整目录链接会让
它们写进真实的 harness。

开发源 `extensions/` 不在任何消费工程里，扩展脚本在那里原地跑不起来（YAML 读取找不到工程根）。
要执行扩展的套件用 `DEV_EXT`：本进程第一次导入时把开发源（含未提交的改动）逐字拷进一个临时消费工程的
`doc/extensions`，接好 yaml，进程退出时删掉。只读开发源本身的检查（规模计量、adapt 的包）仍读 `extensions/`。
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "demo" / "framework" / "harness"
DEV_SOURCE = REPO_ROOT / "extensions"


def link_harness_yaml(root: Path) -> Path:
    """让临时工程根像一个接入了 framework 的工程：`framework.config.json`（缺则写空配置，扩展对空配置
    一律取默认路径）与指向真实 `yaml` 包的 `framework/harness/node_modules/yaml` 链接；已存在的都不动。
    返回链接路径。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "framework.config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    target = root / "framework" / "harness" / "node_modules" / "yaml"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    source = HARNESS / "node_modules" / "yaml"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(source), str(target))
    else:
        os.symlink(source, target, target_is_directory=True)
    return target


def _install_dev_source() -> Path:
    """开发源装进临时消费工程后的扩展目录。运行态（字节码、适配工作件）不拷。"""
    root = Path(tempfile.mkdtemp(prefix="story-dev-ext-")) / "consumer"
    atexit.register(shutil.rmtree, root.parent, True)
    ext = root / "doc" / "extensions"
    runtime = shutil.ignore_patterns(".adapt-*", ".git", "node_modules", "__pycache__",
                                     ".pytest_cache", "*.pyc", "*.pyo")

    def ignore(folder: str, names: list[str]) -> set[str]:
        skip = set(runtime(folder, names))
        if Path(folder) == DEV_SOURCE and "adapt" in names:
            skip.add("adapt")
        return skip

    shutil.copytree(DEV_SOURCE, ext, ignore=ignore)
    link_harness_yaml(root)
    return ext


#: 开发源装在临时消费工程 `doc/extensions` 下的那一份：执行扩展脚本的套件用它
DEV_EXT = _install_dev_source()
#: 那个临时消费工程的根：按消费相对路径（`doc/extensions/...`）起脚本、读文件时的工作目录
DEV_ROOT = DEV_EXT.parents[1]
