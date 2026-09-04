"""材料里的图：登记时说清它是什么，成文时给它一个去处。

两轮实跑各丢过一次图：首跑主流程没画图，二跑材料里三张图一张没进 story。
第二次的根子不是作者不上心——`materials.json` 里图片只有 kind、paths、sha256，
**没有一个字说这张图是什么**。语义此前寄生在一份可选的、手写的 `ux-reference/README.md` 上；
去掉对它的依赖之后没给这份语义另一个家，作者面上图片就成了「存在但不可用」。

四层各担各的，这里判其中两层：

  ① **登记**（脚本）：复制起名、写下一句说明、刷新清单——作者只给名字与那句话；
  ② **集合一致**（脚本）：清单里的每张图要么被引用，要么被点名说明为什么不用。

判「有没有去处」，不判「该不该用」——图可以不用，理由成不成立归读者审查。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
IMPORTER = "doc/extensions/skills/story/scripts/import_sources.py"
FEATURE = "IM90001"

PNG_ONE = b"\x89PNG\r\n\x1a\nsignup"
PNG_TWO = b"\x89PNG\r\n\x1a\nmanage"


class RegistrationCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)
        (self.feature_root / "inbox").mkdir(parents=True)
        self.incoming = self.root / "incoming"
        self.incoming.mkdir()
        (self.incoming / "raw-1.png").write_bytes(PNG_ONE)
        (self.incoming / "raw-2.png").write_bytes(PNG_TWO)

    def register(self, source: str, name: str, caption: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, IMPORTER, "--feature", FEATURE,
             "--project-root", str(self.root),
             "--register-ux", str(self.incoming / source),
             "--name", name, "--caption", caption],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=self.root)

    def manifest(self) -> dict:
        return json.loads((self.feature_root / "AR" / "story-src" / "materials.json")
                          .read_text(encoding="utf-8"))

    def images(self) -> list[dict]:
        return [m for m in self.manifest()["materials"] if m["kind"] == "image"]


class RegisteringSaysWhatTheImageIs(RegistrationCase):
    def test_it_copies_names_and_captions_in_one_go(self) -> None:
        proc = self.register("raw-1.png", "signup-page", "签约页：门限与面额选择")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertTrue((self.feature_root / "ux-reference" / "signup-page.png").is_file(),
                        "图没有落到 ux-reference/ 或没按语义名起名")
        images = self.images()
        self.assertEqual(1, len(images))
        self.assertEqual("签约页：门限与面额选择", images[0]["caption"])

    def test_a_caption_is_not_optional(self) -> None:
        """没有那句话，下游拿到的只有路径与哈希——丢图就是从这里开始的。"""
        proc = self.register("raw-1.png", "signup-page", "")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("caption", proc.stdout + proc.stderr)

    def test_an_unregistered_image_still_shows_up_with_an_empty_caption(self) -> None:
        """漏登记要看得见，不能悄悄消失。"""
        (self.feature_root / "assets" / "doc-a").mkdir(parents=True)
        (self.feature_root / "assets" / "doc-a" / "image3.png").write_bytes(PNG_TWO)
        self.register("raw-1.png", "signup-page", "签约页")
        captions = {img["paths"][0]: img["caption"] for img in self.images()}
        self.assertEqual("", captions["assets/doc-a/image3.png"])

    def test_the_caption_follows_the_bytes_not_the_path(self) -> None:
        """同一张图复制到第二个落点，说明跟着它——图片的身份是内容。"""
        self.register("raw-1.png", "signup-page", "签约页")
        (self.feature_root / "assets" / "doc-a").mkdir(parents=True)
        (self.feature_root / "assets" / "doc-a" / "image1.png").write_bytes(PNG_ONE)
        self.register("raw-2.png", "manage-page", "管理页")
        same = [img for img in self.images() if len(img["paths"]) > 1]
        self.assertEqual(1, len(same), "同一张图的两个落点没有归并成一条")
        self.assertEqual("签约页", same[0]["caption"])

    def test_changing_a_caption_does_not_change_the_material_version(self) -> None:
        """说明变了不是材料变了——否则改一句话就开出新一轮。"""
        self.register("raw-1.png", "signup-page", "签约页")
        before = self.manifest()["digest"]
        self.register("raw-1.png", "signup-page", "签约页：改了说法，图没换")
        self.assertEqual(before, self.manifest()["digest"])
        self.assertEqual("签约页：改了说法，图没换", self.images()[0]["caption"])

    def test_the_contract_no_longer_declares_a_readme_source(self) -> None:
        """README 不再是任何东西的登记，也就不再是来源。"""
        contract = json.loads(
            (EXT / "skills/story/contracts/story-chapters.json").read_text(encoding="utf-8"))
        self.assertNotIn("UX", contract["sources"],
                         "合同还把 ux-reference/README.md 当来源——那一笔两跑各出现两次")


class EveryRegisteredImageNeedsSomewhereToGo(RegistrationCase):
    """集合一致：清单里的图，要么被引用，要么被点名说明为什么不用。"""

    def build(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", "doc/extensions/skills/story/scripts/story-build.mjs", *args,
             "--feature", FEATURE],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90, cwd=self.root)

    def setUp(self) -> None:
        super().setUp()
        self.register("raw-1.png", "signup-page", "签约页")
        # 台账两件是 story 成文的依据，check 先核它们才走到图片这一条
        src = self.feature_root / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [{
            "id": "D1", "status": "settled", "category": "交付范围",
            "title": "本单只做签约，管理页另议",
            "clarification": "**要定的事**：范围。\n\n**根据**：上游拆成两张单。\n\n"
                             "**结论与影响**：验收不含管理页。",
            "decider": "需求方",
        }]}, ensure_ascii=False), encoding="utf-8")
        (src / "copyedit.md").write_text(
            "- 通读一遍，语气统一\n- 术语与材料一致\n- 表格每列都有落点\n"
            "- 图有承接句\n- 验收逐条可观察\n- 附录只放查阅件\n", encoding="utf-8")
        self.assertEqual(0, self.build("skeleton").returncode)
        self.story = self.feature_root / "AR" / "story.md"

    def check_output(self) -> str:
        proc = self.build("check")
        return (proc.stdout or "") + (proc.stderr or "")

    def test_an_image_nobody_mentions_is_reported_by_name(self) -> None:
        out = self.check_output()
        self.assertIn("ux-reference/signup-page.png", out)
        self.assertIn("写明不引用的理由", out)

    def test_naming_it_in_the_material_list_settles_it(self) -> None:
        """写明为什么不用，就算有去处——判的是集合，不是理由。"""
        text = self.story.read_text(encoding="utf-8")
        self.story.write_text(
            text + "\n参考稿 signup-page.png 与最终交互不一致，本文不引用它。\n",
            encoding="utf-8")
        self.assertNotIn("既没被引用，也没被提到", self.check_output())

    def test_using_it_settles_it_too(self) -> None:
        text = self.story.read_text(encoding="utf-8")
        self.story.write_text(
            text + "\n![图 1 · 签约页](../ux-reference/signup-page.png)\n", encoding="utf-8")
        out = self.check_output()
        self.assertNotIn("既没被引用，也没被提到", out)
        self.assertNotIn("不在材料的图片登记里", out)


if __name__ == "__main__":
    unittest.main()
