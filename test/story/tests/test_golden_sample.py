"""金样是判据的仲裁锚——改它就是挪掉仲裁源。

四轮机制迭代的判据全部从「病」反推：见到一种坏产物就加一条判据，从不存在
「期望的 story 长什么样」的具体定义。后果是判据之间互相打架时没有仲裁源——
批次 4 首跑就撞上了：一边要求人读的改写，一边要求逐字命中，倾倒成了唯一合法解。

所以先有金样，再有判据。规则只有一条：**任何判据若拦金样，错的是判据**。
这份测试守两件事：

  ① 唯一金样正本与构造场景所需的同轮材料一个字节没变（指纹 + 形态数）；
  ② 现行判据对金样零 FAIL——判据改动先跑这一行。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = REPO_ROOT / "test" / "story" / "golden"
INPUT_FIXTURE = REPO_ROOT / "test" / "story" / "fixtures" / "golden" / "AR90004"
GOLDEN_STORY = GOLDEN / "story-金样-AR90004.md"
BUILD = REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"

#: 定稿时点 2026-08-30（用户逐轮批注后认可）；同日二次修订：材料清单每行带原文链接
#: ——原文链接是仓内路径唯一允许出现的位置，读者据它把那份材料找出来。sha256 前 16 位。
#: 金样正文与归档图片只在 test/story/golden 维护；原始材料夹具保留自己的来源图片。
GOLDEN_FINGERPRINTS = {
    "story-金样-AR90004.md": "c392539c51339d8e",
    "assets/image1.png": "7a0b672988d707e2",
    "assets/image2.png": "da8a096f4a859ddb",
}

INPUT_FINGERPRINTS = {
    "AR/design.md": "ed2119f15893b568",
    "RR/prd.md": "ff0013420c4c0741",
    "SR/design.md": "d9ccbd10489f89d1",
    "spec/spec.md": "8ea24b8250376bc4",
    "ux-reference/README.md": "b7d62b1835408302",
    "assets/紧急挂失界面原型说明/image1.png": "7a0b672988d707e2",
    "assets/紧急挂失界面原型说明/image2.png": "da8a096f4a859ddb",
}

EXPECTED_CANONICAL_FILES = {
    "README.md",
    "story-金样-AR90004.md",
    "review-金样-AR90006.md",
    "assets/image1.png",
    "assets/image2.png",
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
        for root, fingerprints in ((GOLDEN, GOLDEN_FINGERPRINTS),
                                   (INPUT_FIXTURE, INPUT_FINGERPRINTS)):
            for rel, want in fingerprints.items():
                path = root / rel
                with self.subTest(file=path.relative_to(REPO_ROOT)):
                    self.assertTrue(path.is_file(), f"金样或输入夹具少了 {path}")
                    self.assertEqual(
                        want, digest(path),
                        f"{path} 变了——金样正本或冻结输入只有维护者能改，改了要同步指纹")

    def test_no_duplicate_golden_outputs_in_fixture(self) -> None:
        for rel in ("AR/story.md", "AR/review.md", "AR/assets/image1.png", "AR/assets/image2.png"):
            with self.subTest(file=rel):
                path = INPUT_FIXTURE / rel
                self.assertFalse(path.exists(), f"{path} 重复保存金样输出；测试须直接读取 test/story/golden")

    def test_input_fixture_has_only_frozen_inputs(self) -> None:
        """输入夹具只保存构造场景需要的材料，不保存 story/review 金样副本。"""
        actual = {p.relative_to(INPUT_FIXTURE).as_posix()
                  for p in INPUT_FIXTURE.rglob("*") if p.is_file()}
        self.assertEqual(set(INPUT_FINGERPRINTS), actual)

    def test_canonical_golden_files_exist(self) -> None:
        for rel in GOLDEN_FINGERPRINTS:
            with self.subTest(file=rel):
                path = GOLDEN / rel
                self.assertTrue(path.is_file(), f"金样少了 {rel}")

    def test_canonical_directory_has_no_unregistered_files(self) -> None:
        actual = {p.relative_to(GOLDEN).as_posix()
                  for p in GOLDEN.rglob("*") if p.is_file()}
        self.assertEqual(EXPECTED_CANONICAL_FILES, actual)

    def test_shape_is_unchanged(self) -> None:
        lines = GOLDEN_STORY.read_text(encoding="utf-8").split("\n")
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
        code, out = offline_check(GOLDEN_STORY)
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
            work.mkdir(parents=True)
            shutil.copy2(GOLDEN_STORY, work / "story.md")
            shutil.copytree(GOLDEN / "assets", work / "assets")
            story = work / "story.md"
            text = story.read_text(encoding="utf-8")
            marker = "\n\n这里塞一个 queryLossEligibility 进主叙事，再留一个 {{待替换的占位}}。"
            story.write_text(text.replace("## 2. 术语", "## 2. 术语" + marker, 1), encoding="utf-8")
            code, out = offline_check(story)
        self.assertEqual(1, code)
        self.assertIn("工程标识", out)
        self.assertIn("模板占位符", out)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
