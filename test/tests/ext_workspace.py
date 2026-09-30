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

sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import publish_to_demo  # noqa: E402
from design_fixture import (  # noqa: E402,F401  接 Framework 的做法与失效形态运行器共用一份
    ensure_framework, link_framework, overlay_framework, project_root_of)


def link_harness_yaml(root: Path) -> Path:
    """让临时工程根像一个接入了 framework 的工程：`framework.config.json`（缺则写空配置，扩展对空配置
    一律取默认路径）、指向真实 `yaml` 包的 `framework/harness/node_modules/yaml` 链接，并补接 demo Framework
    缺的部分（阶段钩子按原生身份找施工单位目录）；已存在的都不动。返回 yaml 链接路径。"""
    from design_fixture import overlay_framework  # noqa: PLC0415
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "framework.config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    target = root / "framework" / "harness" / "node_modules" / "yaml"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        source = HARNESS / "node_modules" / "yaml"
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(source), str(target))
        else:
            os.symlink(source, target, target_is_directory=True)
    overlay_framework(root)
    return target


#: 宿主入口所在：各宿主的 Skill 跳板目录与两份入口文件
HOST_ENTRIES = (".agents", ".cac", ".claude", ".codex", ".cursor", ".opencode", "AGENTS.md", "CLAUDE.md")


def copy_host_entries(source_root: Path, target_root: Path) -> None:
    """把一个工程的宿主入口（各宿主目录与 AGENTS.md / CLAUDE.md）原样复制到另一个工程。"""
    for name in HOST_ENTRIES:
        src = Path(source_root) / name
        if src.is_dir():
            shutil.copytree(src, Path(target_root) / name, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, Path(target_root) / name)


def git_init_excluding_framework(root: Path) -> None:
    """在临时工程里建 git 仓，并让它不看 `framework/`：那是指向 demo 的链接，git 会跟进去收录整个 Framework。"""
    import subprocess
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
    exclude = Path(root) / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("/framework/\n", encoding="utf-8")


def _install_dev_source() -> Path:
    """开发源暂存进临时消费工程的 `doc/extensions`：文件集合用正式安装的源枚举规则，运行态不带。

    只做单测暂存：不装入口、不写扩展段、不合成 manifest，也不证明安装正确——那些归 publish_to_demo。
    """
    root = Path(tempfile.mkdtemp(prefix="story-dev-ext-")) / "consumer"
    atexit.register(shutil.rmtree, root.parent, True)
    ext = root / "doc" / "extensions"
    for rel in publish_to_demo.enumerate_source(DEV_SOURCE):
        (ext / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEV_SOURCE / rel, ext / rel)
    link_harness_yaml(root)
    return ext


#: 开发源装在临时消费工程 `doc/extensions` 下的那一份：执行扩展脚本的套件用它
DEV_EXT = _install_dev_source()
#: 那个临时消费工程的根：按消费相对路径（`doc/extensions/...`）起脚本、读文件时的工作目录
DEV_ROOT = DEV_EXT.parents[1]


_INSTALLED: Path | None = None


def installed_package() -> Path:
    """用正式安装动作把开发源装进一个接入了 demo Framework 的临时消费工程（扩展与各宿主入口都到位），返回工程根。

    adapt 按运行态执行：它的包是装好了的工程，从包里的脚本起跑。每个进程建一次。
    """
    global _INSTALLED
    if _INSTALLED is None:
        root = Path(tempfile.mkdtemp(prefix="story-installed-")) / "package"
        atexit.register(shutil.rmtree, root.parent, True)
        link_framework(root)
        result = publish_to_demo.install_extension(DEV_SOURCE, root)
        if result.status != "installed":
            raise RuntimeError(f"开发源装不进临时工程：{result.status} {result.problems or result.failed}")
        _INSTALLED = root
    return _INSTALLED
