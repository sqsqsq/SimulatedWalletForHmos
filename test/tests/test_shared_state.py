"""共享夹具的锁（shared_state.shared_tree）：Windows 上锁文件删除待定时的两处报错不让调用方的用例出错。

实测（output/scratch/2.0.3-shared-tree/ 的并发实验，16 进程抢同一份状态）：持锁进程删锁的同时，别的进程正拿着锁的句柄，
锁处于删除待定；这时独占创建锁报 PermissionError（不是 FileExistsError），删一份已在删除待定的锁也报 PermissionError。
两处都表示锁还被占着或正在消失：等待者接着等，持锁者照常收尾。这里在进程内让那两个调用各报一次同样的错误，其余照真实文件系统走。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shared_state  # noqa: E402


class TheLockToleratesAPendingDelete(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(shared_state, "ROOT", Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def build(work: Path) -> None:
        work.mkdir(parents=True)
        (work / "made.txt").write_text("ok", encoding="utf-8")

    def test_a_lock_in_pending_delete_is_waited_for_not_raised(self) -> None:
        real = os.open
        calls = []

        def pending_once(path, flags, *args):
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, flags, *args)
        with mock.patch.object(shared_state.os, "open", side_effect=pending_once):
            final = shared_state.shared_tree("t", "pending-open", self.build)
        self.assertEqual("ok", (final / "made.txt").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(calls), 2, "删除待定的锁没有接着等")

    def test_dropping_a_lock_already_being_deleted_is_not_an_error(self) -> None:
        real = Path.unlink

        def pending(self_path, missing_ok=False):
            if self_path.suffix == ".lock":
                real(self_path, missing_ok=True)
                raise PermissionError(5, "Access is denied", str(self_path))
            return real(self_path, missing_ok=missing_ok)
        with mock.patch.object(Path, "unlink", pending):
            final = shared_state.shared_tree("t", "pending-unlink", self.build)
        self.assertTrue((final / ".ready").is_file())
        self.assertFalse(list(Path(self._tmp.name).glob("*.lock")), "锁没有收掉")


class TheCleanupLeavesBuildersAlone(unittest.TestCase):
    """另一份状态开造前的清理只收两天前完成的缓存，按 `.ready` 的完成时间判断。

    构建中的目录可能整份复制自旧文件，根目录继承了旧修改时间；另一份状态在它构建途中开造并清理时，它的输入必须还在。"""

    OLD = time.time() - 3 * 86400

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        patcher = mock.patch.object(shared_state, "ROOT", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.seed = Path(self._tmp.name) / "seed"
        self.seed.mkdir()
        (self.seed / "input.txt").write_text("seed", encoding="utf-8")
        os.utime(self.seed, (self.OLD, self.OLD))

    @staticmethod
    def made(text: str):
        def build(work: Path) -> None:
            work.mkdir(parents=True)
            (work / "made.txt").write_text(text, encoding="utf-8")
        return build

    @staticmethod
    def never(work: Path) -> None:
        raise AssertionError(f"已就绪的状态被重造：{work.name}")

    def test_a_build_copied_from_old_files_survives_another_keys_cleanup(self) -> None:
        def build_a(work: Path) -> None:
            shutil.copytree(self.seed, work)
            self.assertLess(work.stat().st_mtime, time.time() - 2 * 86400, "前提：复制出的构建目录继承了旧修改时间")
            shared_state.shared_tree("t", "b", self.made("b"))
            self.assertTrue((work / "input.txt").is_file(), "另一份状态开造时清掉了构建中的目录")
            (work / "made.txt").write_text((work / "input.txt").read_text(encoding="utf-8") + "+a", encoding="utf-8")

        a = shared_state.shared_tree("t", "a", build_a)
        self.assertEqual("seed+a", (a / "made.txt").read_text(encoding="utf-8"))
        self.assertEqual(a, shared_state.shared_tree("t", "a", self.never))
        b = shared_state.shared_tree("t", "b", self.never)
        self.assertEqual("b", (b / "made.txt").read_text(encoding="utf-8"))

    def test_completion_time_decides_what_is_stale(self) -> None:
        self.state.mkdir()
        fresh = self.state / "t-fresh"
        fresh.mkdir()
        (fresh / ".ready").write_text("", encoding="utf-8")
        os.utime(fresh, (self.OLD, self.OLD))
        expired = self.state / "t-expired"
        expired.mkdir()
        (expired / ".ready").write_text("", encoding="utf-8")
        os.utime(expired / ".ready", (self.OLD, self.OLD))

        shared_state.shared_tree("t", "new", self.made("new"))
        self.assertTrue((fresh / ".ready").is_file(), "刚完成的缓存因目录修改时间旧被清掉")
        self.assertFalse(expired.exists(), "两天前完成的缓存没有回收")


if __name__ == "__main__":
    unittest.main()
