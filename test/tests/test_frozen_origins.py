"""冻结时记下采用文件的外部来源：收件箱导入的转换稿记它的全部原件（一对多，带登记摘要），init 落的空骨架记空列表，
真实的开发需求正文与上游原件不记（它们就是外部原件）。按真实骨架写入者比对，不按文件名排除。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT

sys.path.insert(0, str(DEV_EXT / "skills" / "story" / "scripts" / "core"))
from flow.inputs import ar_design_skeleton, read_ids  # noqa: E402
from materials.frozen import origins  # noqa: E402


class OriginsAreRecordedAtFreeze(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.feature = Path(self._tmp.name) / "REQ-LOCAL"
        (self.feature / "AR").mkdir(parents=True)

    def test_two_inbox_originals_of_one_copy_are_both_kept(self) -> None:
        manifest = {"sources": [
            {"file": "b.docx", "sha256": "sha256:bbbb", "class": "RR", "ingested": True, "target": "RR/prd.md"},
            {"file": "a.docx", "sha256": "sha256:aaaa", "class": "RR", "ingested": True, "target": "RR/prd.md"},
            {"file": "c.docx", "sha256": "sha256:cccc", "class": "RR", "ingested": False}]}
        got = origins(self.feature, ["RR/prd.md", "SR/design.md"], {"RR/prd.md": b"x", "SR/design.md": b"y"}, manifest)
        self.assertEqual({"RR/prd.md": [{"path": "inbox/a.docx", "sha256": "sha256:aaaa"},
                                        {"path": "inbox/b.docx", "sha256": "sha256:bbbb"}]}, got)

    def test_the_local_skeleton_is_generated_but_a_real_ar_body_is_an_original(self) -> None:
        skeleton = ar_design_skeleton(read_ids(self.feature, self.feature.name)).encode("utf-8")
        self.assertEqual({"AR/design.md": []}, origins(self.feature, ["AR/design.md"], {"AR/design.md": skeleton}, {}))
        real = b"# REQ-LOCAL \xe5\xbc\x80\xe5\x8f\x91\xe9\x9c\x80\xe6\xb1\x82\n\n\xe6\xad\xa3\xe6\x96\x87\n"
        self.assertEqual({}, origins(self.feature, ["AR/design.md"], {"AR/design.md": real}, {}))


if __name__ == "__main__":
    unittest.main()
