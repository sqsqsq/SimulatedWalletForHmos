"""共享夹具的锁（shared_state.shared_tree）：Windows 上锁文件删除待定时的两处报错不让调用方的用例出错。

实测（output/scratch/2.0.3-shared-tree/ 的并发实验，16 进程抢同一份状态）：持锁进程删锁的同时，别的进程正拿着锁的句柄，
锁处于删除待定；这时独占创建锁报 PermissionError（不是 FileExistsError），删一份已在删除待定的锁也报 PermissionError。
两处都表示锁还被占着或正在消失：等待者接着等，持锁者照常收尾。这里在进程内让那两个调用各报一次同样的错误，其余照真实文件系统走。
"""
from __future__ import annotations

import os
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
