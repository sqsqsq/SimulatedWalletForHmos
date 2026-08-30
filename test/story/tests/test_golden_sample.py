"""金样是判据的仲裁锚——改它就是挪掉仲裁源。

四轮机制迭代的判据全部从「病」反推：见到一种坏产物就加一条判据，从不存在
「期望的 story 长什么样」的具体定义。后果是判据之间互相打架时没有仲裁源——
批次 4 首跑就撞上了：一边要求人读的改写，一边要求逐字命中，倾倒成了唯一合法解。

所以先有金样，再有判据。规则只有一条：**任何判据若拦金样，错的是判据**。
这份测试守两件事：

  ① 金样与它同轮的四份材料一个字节没变（指纹 + 形态数）；
  ② 现行判据对金样零 FAIL——判据改动先跑这一行。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = REPO_ROOT / "test" / "story" / "fixtures" / "golden" / "AR90004"
BUILD = REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"

#: 定稿时点 2026-08-30（用户逐轮批注后认可）；同日二次修订：材料清单每行带原文链接
#: ——原文链接是仓内路径唯一允许出现的位置，读者据它把那份材料找出来。sha256 前 16 位。
#: 两处 image 是同一对文件的两个落点：金样正文按 `assets/x.png` 引，
#: 界面材料按需求目录的 `../assets/<文档名>/x.png` 引——两条链都要能解析。
FINGERPRINTS = {
    "AR/story.md": "c392539c51339d8e",
    "AR/design.md": "ed2119f15893b568",
    "AR/assets/image1.png": "7a0b672988d707e2",
    "AR/assets/image2.png": "da8a096f4a859ddb",
    "RR/prd.md": "ff0013420c4c0741",
    "SR/design.md": "d9ccbd10489f89d1",
    "spec/spec.md": "8ea24b8250376bc4",
    "ux-reference/README.md": "b7d62b1835408302",
    "assets/紧急挂失界面原型说明/image1.png": "7a0b672988d707e2",
    "assets/紧急挂失界面原型说明/image2.png": "da8a096f4a859ddb",
}

#: 定稿时点的形态。验收拿新产物与它并排比：任一项显著低于它就是缩水。
SHAPE = {"lines": 398, "chapters": 10, "subsections": 34,
         "table_rows": 159, "diagrams": 1, "images": 2}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def offline_check(story: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["node", str(BUILD), "check", "--offline", "--story", str(story),
         "--project-root", str(REPO_ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()


class GoldenIsFrozen(unittest.TestCase):
    def test_every_file_matches_its_fingerprint(self) -> None:
        for rel, want in FINGERPRINTS.items():
            with self.subTest(file=rel):
                path = GOLDEN / rel
                self.assertTrue(path.is_file(), f"金样少了 {rel}")
                self.assertEqual(want, digest(path),
                                 f"{rel} 变了——金样定稿后只有维护者能改，改了要同步这里的指纹")

    def test_no_extra_files_slipped_in(self) -> None:
        """多出来的文件也是改动：判据会把它当材料读进去。"""
        actual = {p.relative_to(GOLDEN).as_posix() for p in GOLDEN.rglob("*") if p.is_file()}
        self.assertEqual(set(FINGERPRINTS), actual)

    def test_shape_is_unchanged(self) -> None:
        lines = (GOLDEN / "AR" / "story.md").read_text(encoding="utf-8").split("\n")
        actual = {
            "lines": len(lines) - (1 if lines and lines[-1] == "" else 0),
            "chapters": sum(1 for x in lines if x.startswith("## ")),
            "subsections": sum(1 for x in lines if x.startswith("### ")),
            "table_rows": sum(1 for x in lines if x.startswith("|")),
            "diagrams": sum(1 for x in lines if x.startswith("```mermaid")),
            "images": sum(x.count("![") for x in lines),
        }
        self.assertEqual(SHAPE, actual)


class JudgementsDoNotBlockTheGolden(unittest.TestCase):
    """判据改动先跑这一行：拦住金样的判据，错的是判据。"""

    def test_offline_check_is_clean(self) -> None:
        code, out = offline_check(GOLDEN / "AR" / "story.md")
        self.assertEqual(0, code, f"判据拦住了金样——修判据，不修金样：\n{out[:1500]}")

    def test_the_offline_judgements_actually_run(self) -> None:
        """零 FAIL 要是「真的判过了」，不是「一条都没跑」。

        往副本的主叙事里塞一个工程标识加一段超长的话，两条判据都该点名。
        不验这个，`--offline` 退化成空转也没人知道。
        """
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "AR"
            shutil.copytree(GOLDEN / "AR", work)
            story = work / "story.md"
            text = story.read_text(encoding="utf-8")
            marker = "\n\n这里塞一个 queryLossEligibility 进主叙事：" + "复述一遍没有信息量的话，" * 20
            story.write_text(text.replace("## 2. 术语", "## 2. 术语" + marker, 1), encoding="utf-8")
            code, out = offline_check(story)
        self.assertEqual(1, code)
        self.assertIn("工程标识", out)
        self.assertIn("过长的段落", out)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
