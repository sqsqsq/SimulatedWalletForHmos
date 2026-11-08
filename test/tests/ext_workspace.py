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
import re
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

    adapt 按运行态执行：它的包是装好了的工程，从包里的脚本起跑。交回与全量时父进程已按同一合同装好一份
    （`STORY_TEST_INSTALLED_PACKAGE`），worker 只读它；要改包的用例先复制。否则每个进程建一次。
    """
    global _INSTALLED
    shared = os.environ.get("STORY_TEST_INSTALLED_PACKAGE")
    if _INSTALLED is None and shared and Path(shared, "doc", "extensions", "manifest.yaml").is_file():
        _INSTALLED = Path(shared)
    if _INSTALLED is None:
        root = Path(tempfile.mkdtemp(prefix="story-installed-")) / "package"
        atexit.register(shutil.rmtree, root.parent, True)
        link_framework(root)
        result = publish_to_demo.install_extension(DEV_SOURCE, root)
        if result.status != "installed":
            raise RuntimeError(f"开发源装不进临时工程：{result.status} {result.problems or result.failed}")
        _INSTALLED = root
    return _INSTALLED


def change_versions(ext: Path, block: str) -> list[str]:
    """包的升级演进记录里带某块条目的版本，按出现顺序；第一个就是最早一节。

    判「从最早一节列起」要拿记录本身作答案，不在测试里写死版本号——记录加一节、改一节，断言照样成立。
    """
    version, seen = None, []
    text = (ext / "skills" / "story-adaptation" / "reference" / "upgrade-changes.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        head = re.match(r"^##\s+(\d+(?:\.\d+)+)\s*$", line)
        if head:
            version = head.group(1)
        elif version and line.startswith(f"- [{block}]") and version not in seen:
            seen.append(version)
    return seen


_REQUIRED_INPUTS = """
const [, , mod, root, feature, purpose] = process.argv;
const m = await import(mod);
process.stdout.write(JSON.stringify(m.reviewInputs(root, feature, purpose).inputs.filter(x => x.required).map(x => x.key)));
"""


def required_inputs(root: Path, feature: str, purpose: str = "story") -> list[str]:
    """扩展派生的必审集合的核查标识（原生输入是 input_id，文件是相对工程根的路径）。只读：缺的就是缺，不补占位。"""
    import json
    import subprocess
    root = Path(root)
    driver = root / "required-inputs.mjs"
    driver.write_text(_REQUIRED_INPUTS, encoding="utf-8")
    mod = DEV_EXT / "hooks" / "shared" / "review-inputs.mjs"
    proc = subprocess.run(["node", str(driver), mod.resolve().as_uri(), str(root), feature, purpose],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    driver.unlink()
    if proc.returncode:
        raise RuntimeError(proc.stderr[:600])
    return json.loads(proc.stdout)


def cover_report(text: str, root: Path, feature: str, purpose: str = "story") -> str:
    """报告里每处 `examined_inputs: []` 换成当前必审集合的核查标识逐项列出（同缩进）。"""
    import re
    paths = required_inputs(root, feature, purpose)

    def listed(m: "re.Match[str]") -> str:
        ind = m.group(1)
        return f"{ind}examined_inputs:\n" + "".join(f"{ind}  - {p}\n" for p in paths) if paths else m.group(0)
    return re.sub(r"(?m)^([ \t]*)examined_inputs: \[\]\n", listed, text)
