"""import_sources.py — 把人工放进 inbox/ 的上游材料转成流程能消费的形态（正式入口）。

需求系统里 PRD/SE 有时没及时归档，现场只能人工拿到文档或设计图。本命令把它们接进既有
流程：docx 转 md 覆盖对应上游正文（图片抽出保留引用），设计图分发到框架的 UX 参考落点。
下游（AR/design 生成、章节装配、spec）消费的是那几个权威文件，感知不到材料来源。

    python import_sources.py --feature <AR> [--project-root <abs>]
    python import_sources.py --preview <材料文件>
    python import_sources.py --feature <AR> --caption-image <图> --caption <一句话>
    python import_sources.py --feature <AR> --caption-image <图> --unused <理由>
    python import_sources.py --feature <AR> --register-ux <图> --name <名> --caption <一句话>

归类读 `inbox/.classify.json`，内容是 `{"文件名": "<类>"}`（值域见 `materials/importer.py` 的 `CLASSES`）。**归类判断不是脚本的活**：
它需要读文件名、内容语义与人在关卡上的说明，属语义判断，由 AI 做出后写进该文件；
脚本只负责执行与收敛。没给归类的文件不会被默默忽略——那等于人以为导了、实际没导。

**归类为什么走文件而不是命令行参数**：JSON 全是引号，而任何 shell 都要对参数再解析一遍
——同一条命令 bash 下原样送达，Windows PowerShell 下双引号被吞、这里收到 `{a:b}`。
宿主是变量，所以约束落在接口上：结构化数据走文件（AI 写文件不过 shell），参数只放标量。

本文件只做参数解析、分派与顶层输出：stdout 单行 JSON，人类可读日志走 stderr。
转换、落盘与图片登记的实现在 `materials/importer.py`；材料现在是什么、哪些原件已经并入
正文，一律去 `materials/registry.py` 的清单里按磁盘现状问。导入不另留一份回执：同一事实
两处写，其中一处过期或被清掉时，两边都还理直气壮。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from materials import importer


def main() -> int:
    ap = argparse.ArgumentParser(description="把 inbox/ 里的人工材料导入上游正文")
    ap.add_argument("--feature", required=False,
                    help="导入模式必填；--preview 只读单份材料时可不填")
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--preview", default=None, metavar="PATH",
                    help="只读预览一份材料的正文与图清单，不落盘（归类判断的输入）")
    ap.add_argument("--register-ux", default=None, metavar="PATH",
                    help="把这张图登记成界面参考：复制到 ux-reference/ 起名，并记下它是什么")
    ap.add_argument("--caption-image", default=None, metavar="PATH",
                    help="给材料里的一张图写说明，不复制不改名（流程图这类走它）")
    ap.add_argument("--name", default="", help="--register-ux 的语义名（不带后缀）")
    ap.add_argument("--caption", default="", help="一句「这张图是什么」")
    ap.add_argument("--unused", default="", metavar="REASON",
                    help="与 --caption-image 同用：登记本需求为什么不用这张图")
    ap.add_argument("--used", action="store_true",
                    help="与 --caption-image 同用：撤掉「不用」的理由（说明留着）")
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
    feature_root = (project_root / importer.features_dir(project_root) / args.feature
                    if args.feature else None)

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

    if args.register_ux:
        if feature_root is None:
            return emit({"mode": "register-ux", "ok": False,
                         "error": "登记界面图需要 --feature"}, 1)
        try:
            out = importer.register_ux(
                feature_root, importer.resolve_image_arg(project_root, args.register_ux),
                args.name, args.caption)
        except (importer.ImportError_, OSError) as exc:
            return emit({"mode": "register-ux", "ok": False, "error": str(exc)}, 1)
        importer.log(f"界面图已登记：{out['path']}——{out['caption']}")
        return emit({"mode": "register-ux", "ok": True, **out}, 0)

    if feature_root is None:
        return emit({"mode": "import", "ok": False, "error": "导入模式需要 --feature"}, 1)

    result: dict = {"mode": "import", "reqNo": args.feature}
    try:
        result.update(success=True, **importer.cmd_import(feature_root))
        return emit(result, 0)
    except importer.ImportError_ as exc:
        importer.log(str(exc))
        result.update(success=False, error=str(exc))
        return emit(result, 1)


if __name__ == "__main__":
    sys.exit(main())
