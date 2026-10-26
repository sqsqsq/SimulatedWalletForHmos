"""两组金样正本的文件身份、引用与图源：内容不被悄悄改动，引用都落得到地方。

金样是用户审定过的目标效果（2026-10-17 认可，记录在 doc/plan/1.9.9/2026-10-17-R3页面交互金样修订/06）：
`test/golden/auto-topup/`（止于 Spec）与 `test/golden/car-key-sharing/`（止于 Plan）。它给人对照效果，
不当判据的机器否决锚——判据对错按真实依据与中性正反例判。替换或实质修改要重新经用户审定，
机械路径调整也要在交回里列出前后差异再改这里的指纹。

正本的文件身份只在这里登记一处（`REGISTRY`），单正本检查（test_run_measurement）读同一份登记。
指纹取 sha256 前 16 位：Markdown、Mermaid 源与 SVG 按 LF 归一后算（检出时的行尾不算改动），图片按字节算。
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "test" / "golden"

#: 审定身份（05 最终审定清单逐文件 SHA256 的前 16 位）。两份 README 的 test/cases 链接随迁移
#: 从 `../../../../../test/cases/` 改为 `../../cases/`，只改这一处路径，指纹随之重算。
#: 2026-10-20 阅读槽展示接线：两份 Story 与两份 README 按 P4 集中复核 §3 认可的差异重登（Story 移出指路句、
#: 放空阅读槽；README 给独立阅读入口与旧验证记录口径），其余文件身份不变。
REGISTRY = {
    "auto-topup/AR/figures/auto-topup-recovery-boundary.svg": "c49a33b258870a63",
    "auto-topup/AR/review.md": "b5a414978bcb812a",
    "auto-topup/AR/story-src/figures/fig-22c28d5a.mmd": "3716cccb9c98a565",
    "auto-topup/AR/story-src/figures/fig-55cee031.mmd": "ef47d929de5321eb",
    "auto-topup/AR/story-src/figures/fig-e2548d39.mmd": "42b3ff445246c298",
    "auto-topup/AR/story.md": "1dc6ac452f9b000c",
    "auto-topup/README.md": "44894879aa6a7858",
    "auto-topup/spec/spec.md": "c79aadc3bdba2c2a",
    "auto-topup/ux-reference/detail-entry.png": "328419dced4a2be5",
    "auto-topup/ux-reference/disabled-state.png": "adeefcff56af7d05",
    "auto-topup/ux-reference/manage-page.png": "24fbb597b158d849",
    "auto-topup/ux-reference/signup-page.png": "6c8da20cbbc6fdd4",
    "auto-topup/ux-reference/verify-page.png": "c8b62984ec0018e2",
    "car-key-sharing/AR/figures/car-key-revocation-responsibility.svg": "ab3ff231526400cd",
    "car-key-sharing/AR/review.md": "4d2e3274a521d368",
    "car-key-sharing/AR/story-src/figures/fig-0169f210.mmd": "04a0b4e034a12572",
    "car-key-sharing/AR/story-src/figures/fig-b533fea2.mmd": "61b471f393a30158",
    "car-key-sharing/AR/story-src/figures/fig-d087d97f.mmd": "0b4e7f9fa87f45bc",
    "car-key-sharing/AR/story.md": "2f6bf7bfe203e371",
    "car-key-sharing/plan/plan.md": "383c599fda4993e4",
    "car-key-sharing/README.md": "910d119afc41c59a",
    "car-key-sharing/spec/spec.md": "a4850d055370a378",
    "car-key-sharing/ux-reference/accept-page.png": "2508945f90164274",
    "car-key-sharing/ux-reference/key-card-detail.png": "87d832fadbce16ad",
    "car-key-sharing/ux-reference/share-manage.png": "6353c699bfb9ac48",
    "car-key-sharing/ux-reference/share-setup.png": "15056c761f98905d",
}
#: 正本目录里除登记文件外只有入口说明
ENTRY = "README.md"

CASES = ("auto-topup", "car-key-sharing")
#: 每组的正文：情景终点决定有没有 plan
DOCUMENTS = {
    "auto-topup": ("AR/story.md", "AR/review.md", "spec/spec.md"),
    "car-key-sharing": ("AR/story.md", "AR/review.md", "spec/spec.md", "plan/plan.md"),
}
#: 每组登记的综合阅读图：不与某一张 .mmd 等值，metadata 写依据位置；值是它的阅读槽所在的小节标题
COMPOSITE = {
    "auto-topup": {"auto-topup-recovery-boundary": "7.2 写操作前的共同恢复规则"},
    "car-key-sharing": {"car-key-revocation-responsibility": "5.4 车主管理、撤销与重新发起"},
}

TEXT_SUFFIXES = {".md", ".mmd", ".svg"}
SVG_NS = "{http://www.w3.org/2000/svg}"


def digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


def lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def registry_problems(root: Path) -> list[str]:
    """登记的文件在不在、指纹对不对，目录里有没有未登记的文件。"""
    problems = []
    for rel, want in REGISTRY.items():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}：登记的正本文件不在")
        elif digest(path) != want:
            problems.append(f"{rel}：内容与审定身份不同（登记 {want}，现在 {digest(path)}）")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    for rel in sorted(actual - set(REGISTRY) - {ENTRY}):
        problems.append(f"{rel}：正本目录里有未登记的文件")
    return problems


def source_mapping(case_root: Path) -> list[dict]:
    """README 来源对照表：Story 里的产品形态链接 → 仓内权威输入。「同上一行」沿用上一行的输入。"""
    rows, previous = [], None
    for line in lf(case_root / "README.md").splitlines():
        m = re.match(r"\s*\| `([^`]+)` \| [^|]+ \| ([^|]+) \| ([^|]+) \| [^|]+ \|", line)
        if not m:
            continue
        target = re.search(r"\]\(([^)]+)\)", m.group(2))
        written = re.search(r"`([0-9a-f]{16})`", m.group(3))
        rows.append({"link": m.group(1), "target": target.group(1) if target else previous,
                     "own_target": bool(target), "digest": written.group(1) if written else None})
        if target:
            previous = target.group(1)
    return rows


def link_problems(case_root: Path) -> list[str]:
    """正文里的链接：本目录里能解析的直接核存在；产品形态的材料链接逐条要在 README 对照里有一行，
    对照的权威输入要存在、写的摘要与实际文件相符；对照里的行都要真被正文用到。"""
    case = case_root.name
    rows = {r["link"]: r for r in source_mapping(case_root)}
    used, problems = set(), []
    for rel in DOCUMENTS[case]:
        doc = case_root / rel
        for link in re.findall(r"\]\(([^)\s]+)\)", lf(doc)):
            if link.startswith(("http://", "https://", "#")):
                continue
            if (doc.parent / link).exists():
                continue
            if link not in rows:
                problems.append(f"{case}/{rel}：链接 {link} 在正本目录里点不开，README 来源对照也没有这一行")
                continue
            used.add(link)
    for link, row in rows.items():
        target = case_root / row["target"] if row["target"] else None
        if target is None or not target.is_file():
            problems.append(f"{case}/README.md：对照 {link} 的权威输入 {row['target']} 不存在")
        elif row["own_target"] and row["digest"] != hashlib.sha256(target.read_bytes()).hexdigest()[:16]:
            problems.append(f"{case}/README.md：对照 {link} 写的摘要 {row['digest']} 与权威输入不符")
        if link not in used:
            problems.append(f"{case}/README.md：对照 {link} 在正文里没有用到")
    return problems


def reading_slots(story: str) -> dict[str, tuple[str, bool]]:
    """Story 里的阅读槽：ID → (所在小节标题, 是否在该小节末尾且为空)。正本保存正式形态，槽是空的。"""
    lines = story.split("\n")
    out = {}
    for i, line in enumerate(lines):
        m = re.fullmatch(r"<!-- story-reading:([\w-]+):begin -->", line.strip())
        if not m:
            continue
        sid = m.group(1)
        heading = next((re.sub(r"^#+\s*", "", h) for h in reversed(lines[:i]) if re.match(r"#{2,6}\s", h)), "")
        empty = i + 1 < len(lines) and lines[i + 1].strip() == f"<!-- story-reading:{sid}:end -->"
        rest = next((h for h in lines[i + 2:] if h.strip()), "")
        out[sid] = (heading, empty and (not rest or rest.startswith("#")))
    return out


def figure_problems(case_root: Path) -> list[str]:
    """Story 的管理块都有同名 .mmd 且逐字一致、没有多余图源；登记的综合阅读图存在、是合法 SVG、metadata 写了依据、
    在登记的小节末尾有一个空阅读槽、README 给了独立阅读入口；正式 Story 里没有指向 figures/ 的链接，槽都登记过。
    普通 Mermaid 不要求 SVG。"""
    case = case_root.name
    story = lf(case_root / "AR" / "story.md")
    problems = []
    blocks = re.findall(r"<!-- story-figure:([\w-]+):begin -->\n```mermaid\n(.*?)```\n"
                        r"<!-- story-figure:\1:end -->", story, re.S)
    outside = re.sub(r"<!-- story-figure:([\w-]+):begin -->.*?<!-- story-figure:\1:end -->", "", story, flags=re.S)
    if "```mermaid" in outside:
        problems.append(f"{case}：Story 里有没带管理标记的 Mermaid 图")
    sources = case_root / "AR" / "story-src" / "figures"
    for fid, body in blocks:
        mmd = sources / f"{fid}.mmd"
        if not mmd.is_file():
            problems.append(f"{case}/{fid}：图源 AR/story-src/figures/{fid}.mmd 不在")
        elif body.rstrip("\n") != lf(mmd).rstrip("\n"):
            problems.append(f"{case}/{fid}：Story 里的 Mermaid 与图源不同")
    for mmd in sorted(sources.glob("*.mmd")):
        if mmd.stem not in {fid for fid, _ in blocks}:
            problems.append(f"{case}：图源 {mmd.name} 在 Story 里没有对应的图")
    slots = reading_slots(story)
    readme = lf(case_root / "README.md")
    for link in re.findall(r"\]\((figures/[^)]+)\)", story):
        problems.append(f"{case}：Story 正本里有指向 {link} 的链接——正式形态只留空阅读槽")
    for sid, section in COMPOSITE[case].items():
        svg = case_root / "AR" / "figures" / f"{sid}.svg"
        if not svg.is_file():
            problems.append(f"{case}：登记的综合阅读图 AR/figures/{sid}.svg 不在")
            continue
        try:
            el = ET.parse(svg).getroot()
        except ET.ParseError as exc:
            problems.append(f"{case}/{sid}.svg：不是合法 XML（{exc}）")
            continue
        if el.tag != f"{SVG_NS}svg" or len((el.get("viewBox") or "").split()) != 4:
            problems.append(f"{case}/{sid}.svg：不是带 viewBox 的 SVG")
        meta = next((e for e in el.iter() if e.tag.endswith("metadata")), None)
        if meta is None or not "".join(meta.itertext()).strip():
            problems.append(f"{case}/{sid}.svg：metadata 里没有依据说明")
        if sid not in slots:
            problems.append(f"{case}/{sid}：Story 里没有它的阅读槽")
        elif slots[sid] != (section, True):
            problems.append(f"{case}/{sid}：阅读槽应在「{section}」末尾且为空，现在在「{slots[sid][0]}」"
                            f"{'' if slots[sid][1] else '，不在末尾或槽里有内容'}")
        if f"](AR/figures/{sid}.svg)" not in readme:
            problems.append(f"{case}/{sid}：README 没有它的独立阅读入口")
    for svg in sorted((case_root / "AR" / "figures").glob("*.svg")):
        if svg.stem not in COMPOSITE[case]:
            problems.append(f"{case}：AR/figures/{svg.name} 不是登记的综合阅读图")
    for sid in sorted(set(slots) - set(COMPOSITE[case])):
        problems.append(f"{case}：Story 里的阅读槽 {sid} 没有登记")
    return problems


def cross_problems(case_root: Path) -> list[str]:
    """正文互相对得上：Story 引用的 Spec 验收编号在 Spec 里，Spec 治理表引用的决策在 Review 里。"""
    case = case_root.name
    story, spec = lf(case_root / "AR" / "story.md"), lf(case_root / "spec" / "spec.md")
    review = lf(case_root / "AR" / "review.md")
    problems = []
    defined = set(re.findall(r"\*\*(AC-[\w]+)\*\*", spec))
    cited = set(re.findall(r"AC-[\w]+", " ".join(re.findall(r"Spec (AC-[\w]+(?:、AC-[\w]+)*)", story))))
    for ac in sorted(cited - defined):
        problems.append(f"{case}：Story 引用 Spec {ac}，Spec 里没有")
    governed = set(re.findall(r"《决策与评审记录》(D\d+)", spec))
    decided = set(re.findall(r"<!-- decision: (D\d+) -->", review))
    for d in sorted(governed - decided):
        problems.append(f"{case}：Spec 治理表引用的 {d} 不在 Review 里")
    return problems


class TheApprovedSetIsIntact(unittest.TestCase):
    def test_every_registered_file_matches_its_approved_identity(self) -> None:
        self.assertEqual([], registry_problems(GOLDEN))

    def test_each_case_has_its_documents(self) -> None:
        for case, docs in DOCUMENTS.items():
            for rel in docs:
                with self.subTest(file=f"{case}/{rel}"):
                    self.assertIn(f"{case}/{rel}", REGISTRY)


class TheRegistryCheckNamesWhatChanged(unittest.TestCase):
    """在临时副本上改，正式正本不动；每种改动在副本原有结论之外只多报出那一个路径。"""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "golden"
        shutil.copytree(GOLDEN, self.root)
        self.before = registry_problems(self.root)

    def assert_named(self, rel: str) -> None:
        problems = [p for p in registry_problems(self.root) if p not in self.before]
        self.assertEqual(1, len(problems), problems)
        self.assertIn(rel, problems[0])

    def test_a_missing_file(self) -> None:
        (self.root / "car-key-sharing/plan/plan.md").unlink()
        self.assert_named("car-key-sharing/plan/plan.md")

    def test_an_edited_document(self) -> None:
        story = self.root / "auto-topup/AR/story.md"
        story.write_bytes(story.read_bytes().replace("单日充值上限".encode(), "单日充值额度".encode(), 1))
        self.assert_named("auto-topup/AR/story.md")

    def test_an_edited_image(self) -> None:
        png = self.root / "car-key-sharing/ux-reference/share-setup.png"
        png.write_bytes(png.read_bytes() + b"\0")
        self.assert_named("car-key-sharing/ux-reference/share-setup.png")

    def test_an_unregistered_file(self) -> None:
        (self.root / "auto-topup/AR/story-副本.md").write_bytes(b"# copy\n")
        self.assert_named("auto-topup/AR/story-副本.md")

    def test_line_endings_are_not_a_change(self) -> None:
        spec = self.root / "auto-topup/spec/spec.md"
        spec.write_bytes(spec.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.before, registry_problems(self.root))


class LinksAndFiguresResolve(unittest.TestCase):
    def test_the_approved_set_has_no_reference_problems(self) -> None:
        for case in CASES:
            with self.subTest(case=case):
                root = GOLDEN / case
                self.assertEqual([], link_problems(root) + figure_problems(root) + cross_problems(root))

    def test_every_case_maps_its_product_links(self) -> None:
        for case in CASES:
            with self.subTest(case=case):
                self.assertTrue(source_mapping(GOLDEN / case), "README 没有来源对照")


class TheReferenceChecksNameWhatBroke(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "golden"
        shutil.copytree(GOLDEN, self.root)
        # README 的权威输入在 ../../cases：副本旁边放同样的相对位置
        shutil.copytree(REPO_ROOT / "test" / "cases", Path(tmp.name) / "cases")

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.root / rel
        text = path.read_bytes().decode("utf-8")
        self.assertIn(old, text)
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

    def test_the_copy_is_clean(self) -> None:
        for case in CASES:
            root = self.root / case
            self.assertEqual([], link_problems(root) + figure_problems(root) + cross_problems(root))

    def test_a_dropped_mapping_row_names_the_link(self) -> None:
        readme = self.root / "auto-topup/README.md"
        lines = readme.read_bytes().decode("utf-8").split("\n")
        readme.write_bytes("\n".join(l for l in lines if not l.lstrip().startswith("| `../RR/prd.md`"))
                           .encode("utf-8"))
        problems = link_problems(self.root / "auto-topup")
        self.assertTrue(problems)
        self.assertTrue(all("../RR/prd.md" in p for p in problems), problems)

    def test_a_broken_authoritative_input_is_named(self) -> None:
        (self.root.parent / "cases/car-key-sharing/workspace/SR/design.md").unlink()
        problems = link_problems(self.root / "car-key-sharing")
        self.assertEqual(1, len(problems), problems)
        self.assertIn("workspace/SR/design.md", problems[0])

    def test_a_wrong_digest_is_named(self) -> None:
        self.edit("auto-topup/README.md", "`e90230c22fec374c`", "`0000000000000000`")
        problems = link_problems(self.root / "auto-topup")
        self.assertEqual(1, len(problems), problems)
        self.assertIn("../RR/prd.md", problems[0])

    def test_a_missing_reference_image_is_named(self) -> None:
        (self.root / "auto-topup/ux-reference/manage-page.png").unlink()
        problems = link_problems(self.root / "auto-topup")
        self.assertEqual(1, len(problems), problems)
        self.assertIn("manage-page.png", problems[0])

    def test_a_drifted_figure_source_is_named(self) -> None:
        mmd = self.root / "car-key-sharing/AR/story-src/figures/fig-b533fea2.mmd"
        mmd.write_bytes(mmd.read_bytes() + b"    X --> Y\n")
        self.assertEqual(["car-key-sharing/fig-b533fea2：Story 里的 Mermaid 与图源不同"],
                         figure_problems(self.root / "car-key-sharing"))

    def test_an_extra_reading_figure_is_named(self) -> None:
        shutil.copy(self.root / "auto-topup/AR/figures/auto-topup-recovery-boundary.svg",
                    self.root / "auto-topup/AR/figures/extra.svg")
        self.assertEqual(["auto-topup：AR/figures/extra.svg 不是登记的综合阅读图"],
                         figure_problems(self.root / "auto-topup"))

    def test_a_missing_composite_figure_is_named(self) -> None:
        (self.root / "car-key-sharing/AR/figures/car-key-revocation-responsibility.svg").unlink()
        problems = link_problems(self.root / "car-key-sharing") + figure_problems(self.root / "car-key-sharing")
        self.assertTrue(problems)
        self.assertTrue(all("car-key-revocation-responsibility" in p for p in problems), problems)

    def test_a_link_left_outside_the_slot_is_named(self) -> None:
        self.edit("auto-topup/AR/story.md", "结果不明的操作这样收口：", "见[图](figures/auto-topup-recovery-boundary.svg)。结果不明的操作这样收口：")
        self.assertEqual(["auto-topup：Story 正本里有指向 figures/auto-topup-recovery-boundary.svg 的链接——正式形态只留空阅读槽"],
                         figure_problems(self.root / "auto-topup"))

    def test_a_shown_or_moved_slot_is_named(self) -> None:
        begin = "<!-- story-reading:car-key-revocation-responsibility:begin -->\n"
        self.edit("car-key-sharing/AR/story.md", begin, begin + "![x](figures/car-key-revocation-responsibility.svg)\n")
        problems = figure_problems(self.root / "car-key-sharing")
        self.assertIn("car-key-sharing/car-key-revocation-responsibility：阅读槽应在「5.4 车主管理、撤销与重新发起」末尾且为空，"
                      "现在在「5.4 车主管理、撤销与重新发起」，不在末尾或槽里有内容", problems)
        shutil.copytree(GOLDEN, self.root, dirs_exist_ok=True)
        slot = begin + "<!-- story-reading:car-key-revocation-responsibility:end -->\n"
        self.edit("car-key-sharing/AR/story.md", "\n" + slot, "")
        self.edit("car-key-sharing/AR/story.md", "### 5.3 接受方添加与查看\n", "### 5.3 接受方添加与查看\n" + slot)
        self.assertEqual(["car-key-sharing/car-key-revocation-responsibility：阅读槽应在「5.4 车主管理、撤销与重新发起」末尾且为空，"
                          "现在在「5.3 接受方添加与查看」，不在末尾或槽里有内容"], figure_problems(self.root / "car-key-sharing"))

    def test_a_missing_reading_entry_is_named(self) -> None:
        self.edit("auto-topup/README.md", "](AR/figures/auto-topup-recovery-boundary.svg)", "](AR/figures/other.svg)")
        self.assertEqual(["auto-topup/auto-topup-recovery-boundary：README 没有它的独立阅读入口"],
                         figure_problems(self.root / "auto-topup"))

    def test_a_plain_mermaid_needs_no_svg(self) -> None:
        story = lf(self.root / "auto-topup/AR/story.md")
        self.assertNotIn("figures/fig-", story)
        self.assertEqual([], figure_problems(self.root / "auto-topup"))

    def test_an_unknown_acceptance_reference_is_named(self) -> None:
        self.edit("auto-topup/AR/story.md", "（Spec AC-1b）", "（Spec AC-1z）")
        self.assertEqual(["auto-topup：Story 引用 Spec AC-1z，Spec 里没有"],
                         cross_problems(self.root / "auto-topup"))


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
