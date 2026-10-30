"""import_sources.py — 把来源收件箱 `sources/inbox/` 里的原件导成材料版本（正式入口）。

一份原件导成 `sources/<标签>-v<N>/`：原件字节、转换正文与内嵌图一起按版本留住，导入成功的原件移出收件箱。
同一来源这次的内容与最新版本相同就复用；内容变了是新版本，旧版本留着可查。

    python import_sources.py --feature <AR> [--project-root <abs>]
    python import_sources.py --preview <材料文件>
    python import_sources.py --feature <AR> --caption-image <图> --caption <一句话>
    python import_sources.py --feature <AR> --caption-image <图> --unused <理由>
    python import_sources.py --feature <AR> --caption-image <图> --used
    python import_sources.py --feature <AR> --scope <条目.json> [--component <组件>]

本地放进来的件，归类读 `sources/inbox/.classify.json`，内容是 `{"<相对收件箱的路径>": "<类>"}`（值域见
`materials/importer.py` 的 `CLASSES`）。**归类判断不是脚本的活**：它需要读文件名、内容语义与人在关卡上的说明，
由 AI 做出后写进该文件；系统取材批次里回执列着的件按回执的角色归类。没给归类的件不会被默默忽略。

**归类为什么走文件而不是命令行参数**：JSON 全是引号，而任何 shell 都要对参数再解析一遍——
宿主是变量，所以约束落在接口上：结构化数据走文件（AI 写文件不过 shell），参数只放标量。

`--scope` 给设计用：需求条目的语义由模型写进文件，脚本按材料索引补来源路径、摘要与 provenance（`materials/scope.py`）。

本文件只做参数解析、分派与顶层输出：stdout 单行 JSON，人类可读日志走 stderr。
导入与图片说明的实现在 `materials/importer.py`；材料现在是什么，一律去 `materials/registry.py` 的索引问。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from materials import importer, scope


def main() -> int:
    ap = argparse.ArgumentParser(description="把来源收件箱里的原件导成材料版本")
    ap.add_argument("--feature", required=False,
                    help="导入模式必填；--preview 只读单份材料时可不填")
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--preview", default=None, metavar="PATH",
                    help="只读预览一份材料的正文与图清单，不落盘（归类判断的输入）")
    ap.add_argument("--caption-image", default=None, metavar="PATH",
                    help="给材料版本里的一张图写说明、登记不用的理由或撤掉理由；不复制不改名")
    ap.add_argument("--caption", default="", help="一句「这张图是什么」")
    ap.add_argument("--unused", default="", metavar="REASON",
                    help="与 --caption-image 同用：登记本需求为什么不用这张图")
    ap.add_argument("--used", action="store_true",
                    help="与 --caption-image 同用：撤掉「不用」的理由（说明留着）")
    ap.add_argument("--scope", default=None, metavar="PATH",
                    help="需求条目文件 [{item_id, kind, source, authority}]：按材料索引补来源，输出原生需求条目")
    ap.add_argument("--component", default=None,
                    help="与 --scope 同用：条目来自需求系统、蓝图还没建立时，给原生设计认定的组件标识")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    def emit(payload: dict, code: int) -> int:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return code

    if args.preview:
        # 只读分支：不碰 feature 目录、不写任何文件，走完就退出。
        try:
            out = importer.preview(Path(args.preview))
        except importer.ImportError_ as exc:
            return emit({"mode": "preview", "ok": False, "error": str(exc)}, 1)
        importer.log(f"预览 {out['file']}：正文 {len(out['text'])} 字，"
                     f"图 {len(out['images'])} 张")
        return emit({"mode": "preview", "ok": True, **out}, 0)

    project_root = Path(args.project_root).resolve() if args.project_root \
        else importer.DEFAULT_PROJECT_ROOT
    try:
        feature_root = (project_root / importer.features_dir(project_root) / args.feature
                        if args.feature else None)
    except importer.ImportError_ as exc:
        return emit({"mode": "import", "ok": False, "error": str(exc)}, 1)

    if args.scope:
        if feature_root is None:
            return emit({"mode": "scope", "ok": False, "error": "补需求条目需要 --feature"}, 1)
        try:
            items = scope.read_items(Path(args.scope))
            out = scope.materialize(feature_root, project_root, items, args.component)
        except (scope.ScopeError, importer.ImportError_) as exc:
            return emit({"mode": "scope", "ok": False, "error": str(exc)}, 1)
        importer.log(f"需求条目 {len(out['current_scope_items'])} 条已按材料索引补齐来源"
                     + (f"；来源物化信封 {out['materialization']}" if out.get("materialization") else ""))
        return emit({"mode": "scope", "ok": True, **out}, 0)

    if args.caption_image:
        if feature_root is None:
            return emit({"mode": "caption-image", "ok": False,
                         "error": "写图片说明需要 --feature"}, 1)
        target = importer.resolve_image_arg(project_root, args.caption_image)
        # 三件事共用一条路：写说明、登记不用的理由、撤掉理由。图只有一个身份，
        # 分成三个入口的话作者要记三种路径写法。
        mode = "image-used" if args.used else ("image-unused" if args.unused
                                               else "caption-image")
        try:
            if args.used:
                out = importer.mark_used(feature_root, target)
            elif args.unused:
                out = importer.mark_unused(feature_root, target, args.unused)
            else:
                out = importer.caption_image(feature_root, target, args.caption)
        except (importer.ImportError_, OSError) as exc:
            return emit({"mode": mode, "ok": False, "error": str(exc)}, 1)
        if args.used:
            importer.log(f"这张图要用了：{args.caption_image}——「不用」的理由已撤")
        elif args.unused:
            importer.log(f"图的取舍已记下：{args.caption_image}——未引用：{out['unused']}")
        else:
            importer.log(f"图片说明已记下：{args.caption_image}——{out['caption']}")
        return emit({"mode": mode, "ok": True, **out}, 0)

    if feature_root is None:
        return emit({"mode": "import", "ok": False, "error": "导入模式需要 --feature"}, 1)

    result: dict = {"mode": "import", "reqNo": args.feature}
    try:
        result.update(success=True, **importer.cmd_import(feature_root, project_root))
        return emit(result, 0)
    except importer.ImportError_ as exc:
        importer.log(str(exc))
        result.update(success=False, error=str(exc))
        return emit(result, 1)


if __name__ == "__main__":
    sys.exit(main())
