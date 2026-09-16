"""离线夹具的 framework 依赖：临时工程根下接一条指向真实 `yaml` 包的链接。

扩展的 YAML 读取器（`hooks/shared/yaml.mjs`）借 framework harness 的 `yaml` 包：从自己的位置向上找
`framework.config.json` 定工程根，再从 `<根>/framework/harness` 取包。把扩展拷进临时根再起 node 的
套件，临时根下没有 harness，第一次解析会按设计抛错。这里不复制 node_modules、不在测试里退回别的读法，
只给临时根一条指向真实 `yaml` 包的 junction（Windows）或符号链接；`TemporaryDirectory` 清理时链接本身
被删，真实目录不动。

**只链接 yaml 包这一个目录**，不把整个 `framework/harness` 链过去：有的套件会往临时根的
`framework/harness/…` 放替身（比如 ts-node 的替身 runner、空的 check-receipt.ts），整目录链接会让
它们写进真实的 harness。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = REPO_ROOT / "framework" / "harness"


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
