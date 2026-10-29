"""冻结时记下采用文件的外部来源：材料版本里的转换正文记它那一版的原件（带完整摘要），生成的空骨架记空列表，
可直接阅读的原件不记（它们就是外部原件）。按真实骨架写入者比对，不按文件名排除。"""
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

    def test_a_converted_text_records_the_original_of_its_own_version(self) -> None:
        manifest = {"origins": [
            {"path": "sources/prd-v2/prd.docx", "sha256": "bbbb", "readable_paths": ["sources/prd-v2/text.md"]},
            {"path": "sources/prd-v1/prd.docx", "sha256": "aaaa", "readable_paths": ["sources/prd-v1/text.md"]},
            {"path": "sources/design-v1/design.md", "sha256": "cccc", "readable_paths": ["sources/design-v1/design.md"]}]}
        adopted = ["sources/prd-v2/text.md", "sources/design-v1/design.md"]
        got = origins(self.feature, adopted, {rel: b"x" for rel in adopted}, manifest)
        self.assertEqual({"sources/prd-v2/text.md": [{"path": "sources/prd-v2/prd.docx", "sha256": "bbbb"}]}, got)

    def test_the_local_skeleton_is_generated_but_a_real_ar_body_is_an_original(self) -> None:
        skeleton = ar_design_skeleton(read_ids(self.feature, self.feature.name)).encode("utf-8")
        self.assertEqual({"AR/design.md": []}, origins(self.feature, ["AR/design.md"], {"AR/design.md": skeleton}, {}))
        real = b"# REQ-LOCAL \xe5\xbc\x80\xe5\x8f\x91\xe9\x9c\x80\xe6\xb1\x82\n\n\xe6\xad\xa3\xe6\x96\x87\n"
        self.assertEqual({}, origins(self.feature, ["AR/design.md"], {"AR/design.md": real}, {}))


if __name__ == "__main__":
    unittest.main()
