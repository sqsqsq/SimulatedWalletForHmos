"""阅读图的结构检查：一份 SVG 能不能当 story 里那张图的本地阅读视图。

只核确定性事实：是合法 XML、根元素是 SVG 命名空间下的 svg、viewBox 是四个有限数且宽高为正、
`<metadata>` 里有来源快照、文件名就是图块 ID、引用的资源在本地读得到且不出 `AR/` 目录——
引用包括 href、属性与样式里的 `url(...)` 和样式里的 `@import`。不按字数估算可读性——
文字有没有裁切、遮挡，连线对不对，归渲染核（人看）与对照审（独立审查者对着 Mermaid 源读）。

    python figure-check.py <AR/figures/<ID>.svg> --id <ID>

stdout 写问题，一行一条；退出 0 通过 / 1 有问题 / 2 参数或文件读不到。只用标准库。
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"
HREFS = ("href", "{http://www.w3.org/1999/xlink}href")
#: 样式与属性里的资源引用：`url(...)`（字体、图案、滤镜）与 `@import`；`url(#id)` 是文内引用。
CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"]*?))\s*\)""", re.I)
CSS_IMPORT = re.compile(r"""@import\s+(?:"([^"]*)"|'([^']*)')""", re.I)


def first(m: re.Match) -> str:
    return next((g for g in m.groups() if g is not None), "").strip()


def references(root: ET.Element) -> list[str]:
    """一份 SVG 里指向别处的全部引用：href 属性、任意属性与 style 里的 url(...)、<style> 里的 url(...) 与 @import。"""
    refs: list[str] = []
    for el in root.iter():
        for key, value in el.attrib.items():
            if key in HREFS:
                refs.append(value.strip())
            else:
                refs.extend(first(m) for m in CSS_URL.finditer(value))
        if el.tag == f"{SVG_NS}style" or el.tag == "style":
            css = "".join(el.itertext())
            refs.extend(first(m) for m in CSS_URL.finditer(css))
            refs.extend(first(m) for m in CSS_IMPORT.finditer(css))
    return refs


def problems_of(svg: Path, fid: str) -> list[str]:
    out: list[str] = []
    if svg.stem != fid:
        out.append(f"文件名 {svg.name} 与图块 ID {fid} 不一致：阅读图按 AR/figures/<ID>.svg 认")
    try:
        root = ET.parse(svg).getroot()
    except ET.ParseError as exc:
        return out + [f"不是合法 XML（{exc}）"]
    if root.tag != f"{SVG_NS}svg":
        hint = "缺 SVG 命名空间（xmlns=\"http://www.w3.org/2000/svg\"），按图片打开时不渲染" if root.tag == "svg" else "不是 svg"
        return out + [f"根元素是 {root.tag}，{hint}"]
    box = (root.get("viewBox") or "").replace(",", " ").split()
    try:
        nums = [float(x) for x in box]
    except ValueError:
        nums = []
    if len(nums) != 4 or not all(math.isfinite(n) for n in nums) or nums[2] <= 0 or nums[3] <= 0:
        out.append(f"viewBox「{root.get('viewBox') or '（缺）'}」要是四个有限数、宽高为正：缩放与裁切按它算")
    meta = next((e for e in root.iter() if e.tag.endswith("metadata")), None)
    if meta is None or not "".join(meta.itertext()).strip():
        out.append("<metadata> 里没有来源快照：写生成它时采用的 Mermaid 原文，切换按它认视图是不是当前源的")
    base = svg.parent.parent.resolve()
    for ref in references(root):
        if not ref or ref.startswith(("#", "data:")):
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*:", ref, re.I) or ref.startswith(("/", "\\")):
            out.append(f"引用「{ref}」不是本地相对路径：阅读图只用内嵌或 AR/ 下的本地资源")
            continue
        target = (svg.parent / ref.split("#", 1)[0]).resolve()
        if not target.is_relative_to(base):
            out.append(f"引用「{ref}」逃出了 AR/ 目录")
        elif not target.is_file():
            out.append(f"引用「{ref}」读不到")
    return out


def local_deps(svg: Path) -> tuple[list[str], list[str]]:
    """阅读图实际用到的本地资源（相对 AR/），样式表与嵌套 SVG 里再引用的也跟进去；去重、防循环。

    缺件、越界、外部地址或解析不了的嵌套文件都列进问题：依赖确定不了，就不能签这张图已验。"""
    base = svg.parent.parent.resolve()
    deps: list[str] = []
    problems: list[str] = []
    queue = [(svg.parent, ref) for ref in references(ET.parse(svg).getroot())]
    while queue:
        at, ref = queue.pop(0)
        if not ref or ref.startswith(("#", "data:")):
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*:", ref, re.I) or ref.startswith(("/", "\\")):
            problems.append(f"资源「{ref}」不是本地相对路径，依赖确定不了")
            continue
        target = (at / ref.split("#", 1)[0]).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            problems.append(f"资源「{ref}」{'逃出了 AR/ 目录' if not target.is_relative_to(base) else '读不到'}")
            continue
        rel = target.relative_to(base).as_posix()
        if rel in deps:
            continue
        deps.append(rel)
        if target.suffix.lower() == ".css":
            css = target.read_text(encoding="utf-8", errors="replace")
            queue.extend((target.parent, first(m)) for m in [*CSS_URL.finditer(css), *CSS_IMPORT.finditer(css)])
        elif target.suffix.lower() == ".svg":
            try:
                queue.extend((target.parent, ref2) for ref2 in references(ET.parse(target).getroot()))
            except ET.ParseError as exc:
                problems.append(f"嵌套的「{ref}」不是合法 XML（{exc}），它的依赖确定不了")
    return deps, problems


def main() -> int:
    ap = argparse.ArgumentParser(description="阅读图的结构检查")
    ap.add_argument("svg")
    ap.add_argument("--id", required=True)
    ap.add_argument("--deps", action="store_true", help="输出本地资源依赖（JSON），供局部阅读验收请求绑定")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    svg = Path(args.svg)
    if not svg.is_file():
        print(f"读不到 {svg}")
        return 2
    if args.deps:
        import json
        try:
            deps, problems = local_deps(svg)
        except ET.ParseError as exc:
            deps, problems = [], [f"不是合法 XML（{exc}）"]
        print(json.dumps({"deps": deps, "problems": problems}, ensure_ascii=False))
        return 1 if problems else 0
    found = problems_of(svg, args.id)
    print("\n".join(found) if found else "结构检查通过（文字可读、连线与语义等值仍要渲染核与对照审）")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
