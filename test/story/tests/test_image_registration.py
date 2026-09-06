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
    """每张图都有去处：要么正文引了，要么登记了本需求为什么不用它。"""

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

    def mark_unused(self, reason: str) -> subprocess.CompletedProcess:
        """登记这张图为什么不用——与作者手上跑的是同一条命令。"""
        return subprocess.run(
            ["python", "doc/extensions/skills/story/scripts/import_sources.py",
             "--feature", FEATURE, "--caption-image",
             f"doc/features/{FEATURE}/ux-reference/signup-page.png", "--unused", reason],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90, cwd=self.root)

    def test_a_feature_relative_path_is_refused_with_the_right_one(self) -> None:
        """只认相对工程根的写法，报错把正确的一起给出来。

        「先按工程根找、找不到再按需求目录找」这种回落，在两处恰好同名时会取到
        另一张图而且不报错；只说「读不到」的话，作者只能去翻脚本找基准。
        """
        proc = subprocess.run(
            ["python", "doc/extensions/skills/story/scripts/import_sources.py",
             "--feature", FEATURE, "--caption-image",
             "ux-reference/signup-page.png", "--caption", "签约页"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90, cwd=self.root)
        self.assertEqual(1, proc.returncode)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("路径相对工程根", out)
        self.assertIn("doc/features/<需求名>/assets/<文件名>", out)

    def test_an_image_nobody_mentions_is_reported_by_name(self) -> None:
        out = self.check_output()
        self.assertIn("ux-reference/signup-page.png", out)
        self.assertIn("--unused", out, "报错要给出登记去向的那条命令")

    def test_registering_why_it_is_unused_settles_it(self) -> None:
        """登记了为什么不用，就算有去处——判的是有没有去向，理由成不成立归审查。"""
        self.assertEqual(0, self.mark_unused("参考稿与最终交互不一致").returncode)
        self.assertNotIn("没被引用", self.check_output())

    def test_the_reason_survives_a_recount(self) -> None:
        """`round` 每次从磁盘重建条目——取舍按图的内容存，重算之后还在。"""
        self.assertEqual(0, self.mark_unused("参考稿与最终交互不一致").returncode)
        self.assertEqual("参考稿与最终交互不一致", self.images()[0]["unused"])

    def test_marking_it_used_again_clears_the_reason(self) -> None:
        """后来又要用它：撤掉理由，说明留着。"""
        self.assertEqual(0, self.mark_unused("先不用").returncode)
        proc = subprocess.run(
            ["python", "doc/extensions/skills/story/scripts/import_sources.py",
             "--feature", FEATURE, "--caption-image",
             f"doc/features/{FEATURE}/ux-reference/signup-page.png", "--used"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", self.images()[0].get("unused", ""))
        self.assertEqual("签约页", self.images()[0]["caption"], "撤取舍不该动说明")

    def insert_after_heading(self, level: str, title: str, text: str) -> None:
        """在某个标题下面插一段。

        **按标题名找，不按编号找**：编号由 `number` 机器铺，骨架阶段还没有，
        写死「### E.」的夹具在骨架上一定找不到。
        """
        lines = self.story.read_text(encoding="utf-8").split("\n")
        at = next((i for i, l in enumerate(lines)
                   if l.startswith(f"{level} ") and l.rstrip().endswith(title)), None)
        self.assertIsNotNone(at, f"骨架里没有「{title}」这一节，夹具要跟着改")
        lines[at + 1:at + 1] = ["", *text.split("\n")]
        self.story.write_text("\n".join(lines), encoding="utf-8")

    def put_in_list(self, row: str) -> None:
        """写进附录材料清单**那一节**。

        写在别处不算：判据按那一节逐行读，附录末尾随手加一行既不在清单里，
        也会被「附录里不放图」另报一次。
        """
        # 骨架只有章锚，附录的小节由 `chapter --from` 落盘时才有——夹具自己搭这一节。
        self.insert_after_heading(
            "##", "附录", "### 材料清单" + "\n" * 2 + row)

    def put_in_body(self, block: str) -> None:
        """写进正文某一章——附录不算正文，图放那里另有判据管。"""
        self.insert_after_heading("##", "功能说明", block)

    def test_declining_it_and_using_it_is_reported(self) -> None:
        """说了不用却引了——两处对不上，读者按哪一处理解都不对。

        六跑那次十张图全进正文、理由写在图题里：形式上说得通，读者却要在归档件里
        读到别的单的页面。规则改单向之后，机械只盯这一处一致；该不该引归读者审查。
        """
        self.assertEqual(0, self.mark_unused("属别的需求的页面").returncode)
        self.put_in_body("签约页长这样。\n\n"
                         "![图 1 · 签约页](../ux-reference/signup-page.png)\n")
        self.assertIn("正文却引了它", self.check_output())

    def test_using_it_settles_it_too(self) -> None:
        text = self.story.read_text(encoding="utf-8")
        self.story.write_text(
            text + "\n![图 1 · 签约页](../ux-reference/signup-page.png)\n", encoding="utf-8")
        out = self.check_output()
        self.assertNotIn("没被引用", out)
        self.assertNotIn("不在材料的图片登记里", out)


if __name__ == "__main__":
    unittest.main()
