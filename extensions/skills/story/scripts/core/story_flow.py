"""story_flow.py — 需求流程契约（`AR/story-src/story-flow.json`）的**唯一写入者**。

契约记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项，
事后可查、可推翻。

`status` 子命令读它就能回答「现在走到哪、下一步干什么」（位置只由 `flow/state.py > stage_of`
判定）；到了停等点，它同时生成问法（选项、顺序、推荐）并写侧车，模型原样摆给人。

契约里绝大多数内容是机械事实——时间戳、轮次边界、收件箱里还有没有没导过的料。
这类事实靠记忆复现就会失真，所以一律由脚本自取。

分工因此是：**判断留 AI，执行归脚本**（与 `import_sources.py` 的归类件同一条边界）。
AI 只传它真正知道而脚本无从得知的东西——人的原话、材料缺口、需求分析；其余一律脚本自己取。
本轮导入了什么也在「脚本自己取」这一侧：`round` 每次调用都让材料清单按磁盘现状
重算材料索引，从索引里读出哪些来源已经导入、收件箱里还剩什么——没有回执，也不需要谁记住发生过什么。

    python story_flow.py init     --feature <AR>
    python story_flow.py round    --feature <AR>
    python story_flow.py decide   --feature <AR> --gate material_scope --ask <ask_id> --reply <人的原话>
    python story_flow.py decide   --feature <AR> --ask <ask_id> --item <题号> --reply <人的原话>
    python story_flow.py decide   --feature <AR> --ask <ask_id> --replies-file <逐题答复 JSON>
    python story_flow.py meeting-refresh --feature <AR> --meeting <主名>@<sha8>
    python story_flow.py status   --feature <AR> [--questions-file <设计问答 JSON>]
    python story_flow.py story    --feature <AR>
    python story_flow.py publish  --feature <AR> [--reply <人确认覆盖外部改动的原话>]
    python story_flow.py archived --feature <AR>
    python story_flow.py restored --feature <AR>
    python story_flow.py update   --feature <AR> [--action inputs|prepare|status|close|restore|feedback] [--result materials|documents]

`init` 与 `archived` 不写轮次，写的是**工作区骨架**与**归档态**：这两件事的执行方
（数据对接层 story.js）不随交付走，各部署环境自备实现，所以判据不能挂在它落的文件上。

公共参数：`--project-root <abs>`。stdout 单行 JSON；人类可读日志走 stderr。
**参数只放标量**：JSON 全是引号，而任何 shell 都要对参数再解析一遍——同一条命令
bash 下原样送达、Windows PowerShell 下双引号被吞。结构化数据一律走文件：
材料缺口走 `AR/story-src/.material-gaps.json`、本 AR 定位走 `AR/story-src/.positioning.json`，
脚本读后即销毁（一次性）；设计问答文件只作 `status --questions-file` 的本次输入；
问法 `AR/story-src/.ask.json` 由 `status` 写、`decide` 读。

退出码（`decide` 的退出码回答「能不能按这个选择往下走」）：

    0  成功
    1  用法/参数/前置不满足，或命令中途没走完——错误信息说明这次已经做了什么、还没做什么
       （`story` 登记失败时列出已完成的派生步骤与没跑的步骤，派生件不用删，改好后重跑登记）
    2  仅 decide：选择已记录，但校验不通过，**不得前进**（如说了料已放进 inbox，盘上却没有）

核心不变量：

- **一轮 = 一次材料状态**。轮次边界由材料清单的 `digest` 判定（`AR/story-src/materials.json`）：
  材料一个字节没变就不是新一轮（幂等），补料导入则必然换版本。设计开始之后材料再变只登记进本轮；
  真实范围变化走 update，由蓝图负责方修订；
- **一次材料确认 = 一条 gate 记录**，含未生效的那次。校验与记录是同一次调用，
  所以不存在"忘了记"；
- **摆过的选项与人的选择一起记**，连同问法编号与人的原话：选的只能是摆出来的，
  签的只能是问过的；设计问答只记当时问法、原话与出处，不写 gate、不产生已批准状态；
- **契约带自身摘要**：读到对不上时报「契约被手改」并给恢复路径，命令照常执行；
- 时间戳一律由本脚本取当下，调用方碰不到该字段。

本文件只做参数解析、分派与顶层输出；每条命令的实现在 `flow/` 下按职责分开：
契约读写、常量与阶段判定在 `state`，一次性侧车与骨架在 `inputs`，「现在走到哪」在 `routing`，
问法在 `asks`，`decide`/`round`/`status` 各在 `decisions`/`rounds`/`lifecycle`。材料确认之后的设计由原生 component-design 做，
流程只按原生蓝图派生位置，不另设交接命令。
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path

import usage
from materials import importer

from flow.state import FlowError, GATES, TAMPER_NOTES, log
from flow.inputs import cmd_init
from flow.decisions import cmd_decide
from flow.publish import cmd_archived, cmd_publish, cmd_restored
from flow.rounds import cmd_round
from flow.lifecycle import cmd_material_status, cmd_status, cmd_story, reading_view
from flow.meetings import cmd_meeting_refresh
from flow.update import (cmd_update_close, cmd_update_feedback, cmd_update_inputs, cmd_update_prepare,
                         cmd_update_restore, cmd_update_status)


# ---------------------------------------------------------------------------
#: 会读、比较或登记 story 的动作：最外层持有视图——动手前回到正式形态，结束或失败后恢复可用的增强 SVG
VIEW_READERS = {"status", "story", "publish", "archived", "restored", "update", "round"}

def main() -> int:
    ap = argparse.ArgumentParser(description="story 需求流程契约的唯一写入者")
    ap.add_argument("mode",
                    choices=["init", "round", "decide", "status",
                             "story", "publish", "archived", "restored", "meeting-refresh", "update"])
    ap.add_argument("--feature", required=True)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--gate", default=None, choices=list(GATES),
                    help="decide：材料确认写 material_scope；设计问答不写 --gate")
    ap.add_argument("--ask", default=None, help="decide：`status` 给出的问法编号 ask_id")
    ap.add_argument("--reply", default=None, help="decide、publish、restored --prepare：人的原话，逐字")
    ap.add_argument("--with-design-reference", action="store_true",
                    help="publish：本单已有交付请求要附设计参考时带上（系统要求附时不必带，也不能省）")
    ap.add_argument("--prepare", action="store_true", help="restored：只准备远端恢复（三方比较），不写远端")
    ap.add_argument("--meeting", default=None,
                    help="会议版本 <主名>@<sha8>：meeting-refresh 用它")
    ap.add_argument("--item", default=None,
                    help="decide 设计问答：本组问法里的题号 item_id")
    ap.add_argument("--replies-file", default=None,
                    help='decide 设计问答：逐题答复 JSON {"items":[{"item_id","reply"}]}')
    ap.add_argument("--questions-file", default=None,
                    help="status：设计后必要问答的输入 JSON，生成一次集中 ask（不传不触发）")
    ap.add_argument("--action", default="inputs",
                    choices=["inputs", "prepare", "status", "close", "restore", "feedback"],
                    help="update：本轮做哪一步（起手是 inputs：先报输入、问补料，再 prepare）")
    ap.add_argument("--materials", action="store_true",
                    help="status：只答材料事实与必读人答同步没有（起稿预检与来源读者用），不算下一步")
    ap.add_argument("--result", default=None, choices=["materials", "documents"],
                    help="update prepare：本轮请求的终点——只取材与澄清是 materials，要同步人读件是 documents")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    def dispatch(feature_root: Path, project_root: Path) -> int:
        """按 mode 执行一个命令，结果并进 result；返回退出码。"""
        code = 0
        if args.mode == "init":
            result.update(cmd_init(feature_root, args.feature))
        elif args.mode == "round":
            result.update(cmd_round(feature_root))
        elif args.mode == "decide":
            payload, code = cmd_decide(feature_root, args)
            result.update(payload)
        elif args.mode == "status":
            if args.materials:
                if args.questions_file:
                    raise FlowError("--materials 只答材料事实，不与 --questions-file 同用")
                result.update(cmd_material_status(feature_root))
            else:
                result.update(cmd_status(feature_root, args.questions_file))
        elif args.mode == "story":
            result.update(cmd_story(feature_root, project_root))
        elif args.mode == "publish":
            result.update(cmd_publish(feature_root, project_root, args.reply, args.with_design_reference))
        elif args.mode == "restored":
            result.update(cmd_restored(feature_root, args.prepare, args.reply))
        elif args.mode == "archived":
            result.update(cmd_archived(feature_root, project_root))
        elif args.mode == "meeting-refresh":
            result.update(cmd_meeting_refresh(feature_root, str(args.meeting or "").strip()))
        elif args.mode == "update":
            if args.action == "status":
                result.update(cmd_update_status(feature_root, args.feature, project_root))
            elif args.action == "close":
                result.update(cmd_update_close(feature_root, args.feature, project_root))
            elif args.action == "restore":
                result.update(cmd_update_restore(feature_root))
            elif args.action == "feedback":
                result.update(cmd_update_feedback(feature_root, project_root))
            elif args.action == "inputs":
                result.update(cmd_update_inputs(feature_root, args.feature, project_root))
            else:
                result.update(cmd_update_prepare(feature_root, args.feature, args.result))
        return code

    result: dict = {"mode": args.mode, "reqNo": args.feature}
    try:
        project_root = Path(args.project_root).resolve() if args.project_root \
            else importer.DEFAULT_PROJECT_ROOT
        feature_root = project_root / importer.features_dir(project_root) / args.feature
        code = 0
        with (reading_view(feature_root, project_root, result) if args.mode in VIEW_READERS
              else nullcontext()):
            code = dispatch(feature_root, project_root)
        if code == 0:
            # 使用记录在命令成功之后采集；记录失败另列，不改业务结果
            used = usage.after_command(project_root, args.feature, args.mode, getattr(args, "action", None))
            if used["errors"]:
                result["usage_errors"] = used["errors"]
            if used["note"]:
                result["usage_note"] = used["note"]
        result["success"] = code == 0
        if TAMPER_NOTES:
            result["warning"] = TAMPER_NOTES[0]
        print(json.dumps(result, ensure_ascii=False))
        return code
    except (FlowError, importer.ImportError_) as exc:
        log(str(exc))
        result.update(success=False, error=str(exc))
        if TAMPER_NOTES:
            result["warning"] = TAMPER_NOTES[0]
        print(json.dumps(result, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001  脚本自身的缺陷：原始异常全文留在 stderr
        import traceback  # noqa: PLC0415
        traceback.print_exc()
        result.update(success=False, error=f"story_flow 自身异常（{type(exc).__name__}：{exc}）：这一步没有执行完，"
                                           "不是产物或材料的问题——原始异常在 stderr，归扩展维护者处理")
        print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
