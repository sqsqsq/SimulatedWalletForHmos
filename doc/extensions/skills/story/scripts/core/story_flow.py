"""story_flow.py — init→spec 流程契约（`AR/story-src/story-flow.json`）的**唯一写入者**。

契约记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项，
事后可查、可推翻。

`status` 子命令读它就能回答「现在走到哪、下一步干什么」（位置只由 `flow/state.py > stage_of`
判定）；到了停等点，它同时生成问法（选项、顺序、推荐）并写侧车，模型原样摆给人。

契约里绝大多数内容是机械事实——时间戳、轮次边界、收件箱里还有没有没导过的料。
这类事实靠记忆复现就会失真，所以一律由脚本自取。

分工因此是：**判断留 AI，执行归脚本**（与 `import_sources.py` 的归类件同一条边界）。
AI 只传它真正知道而脚本无从得知的东西——人的原话、材料缺口、需求分析；其余一律脚本自己取。
本轮导入了什么也在「脚本自己取」这一侧：`round` 每次调用都让材料清单按磁盘现状
重算材料清单，从清单里读出哪些原件已经并入正文——没有回执，也不需要谁记住发生过什么。

    python story_flow.py init     --feature <AR>
    python story_flow.py round    --feature <AR>
    python story_flow.py decide   --feature <AR> --gate <g> --ask <ask_id> --reply <人的原话> [--chosen <编号>]
    python story_flow.py decide   --feature <AR> --gate <g> --propose --chosen <编号> --why <理由>
    python story_flow.py decide   --feature <AR> --update <定了哪件事> --reply <人的原话>
    python story_flow.py meeting-refresh --feature <AR> --meeting <主名>@<sha8>
    python story_flow.py status   --feature <AR>
    python story_flow.py complete --feature <AR> --from AR/story-src/design-draft.md
    python story_flow.py story    --feature <AR>
    python story_flow.py reopen   --feature <AR>
    python story_flow.py archived --feature <AR>
    python story_flow.py update   --feature <AR> [--action inputs|prepare|status|close|restore]
                                  [--request <人这次要求改的事>]

`init` 与 `archived` 不写轮次，写的是**工作区骨架**与**归档态**：这两件事的执行方
（数据对接层 story.js）不随交付走，各部署环境自备实现，所以判据不能挂在它落的文件上。

公共参数：`--project-root <abs>`。stdout 单行 JSON；人类可读日志走 stderr。
**参数只放标量**：JSON 全是引号，而任何 shell 都要对参数再解析一遍——同一条命令
bash 下原样送达、Windows PowerShell 下双引号被吞。结构化数据一律走文件：
材料缺口走 `AR/story-src/.material-gaps.json`、本 AR 定位走 `AR/story-src/.positioning.json`、
拆分份表走 `AR/story-src/.split-parts.json`，脚本读后即销毁（一次性）；问法 `AR/story-src/.ask.json`
由 `status` 写、`decide` 读。

退出码（`decide` 的退出码回答「能不能按这个选择往下走」）：

    0  成功
    1  用法/参数/前置不满足——**没有任何写入**
    2  仅 decide：选择已记录，但校验不通过，**不得前进**（如说了料已放进 inbox，盘上却没有）

核心不变量：

- **一轮 = 一次材料状态**。轮次边界只由材料清单的 `digest` 判定（`AR/story-src/materials.json`）：
  材料一个字节没变就不是新一轮（幂等），补料导入则必然换版本。初析件在同一轮内可以从
  盘点版改到完整版，它的哈希照实登记，但不划轮次——否则「材料没动、重写一遍分析」
  就能造出一个新轮次；
- **一次关卡交互 = 一条 gate 记录**，含未生效的那次。校验与记录是同一次调用，
  所以不存在"忘了记"；
- **摆过的选项与选中的那项一起记**，连同问法编号与人的原话：选的只能是摆出来的，
  签的只能是问过的；
- **契约带自身摘要**：读到对不上时报「契约被手改」并给恢复路径，命令照常执行；
- 时间戳一律由本脚本取当下，调用方碰不到该字段。

本文件只做参数解析、分派与顶层输出；每条命令的实现在 `flow/` 下按职责分开：
契约读写、常量与阶段判定在 `state`，一次性侧车与骨架在 `inputs`，「现在走到哪」在 `routing`，
问法在 `asks`，`decide`/`round`/`complete`/`status` 各在 `decisions`/`rounds`/`submission`/`lifecycle`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from materials import importer

from flow.state import DESIGN_DRAFT, FlowError, GATES, TAMPER_NOTES, log
from flow.inputs import cmd_init
from flow.decisions import cmd_decide, cmd_decide_update, cmd_propose
from flow.rounds import cmd_reopen, cmd_round
from flow.submission import cmd_complete
from flow.lifecycle import cmd_archived, cmd_status, cmd_story
from flow.meetings import cmd_meeting_refresh
from flow.update import (cmd_update_close, cmd_update_inputs, cmd_update_prepare,
                         cmd_update_restore, cmd_update_status)


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="story init→spec 流程契约的唯一写入者")
    ap.add_argument("mode",
                    choices=["init", "round", "decide", "status", "complete", "reopen",
                             "story", "archived", "meeting-refresh", "update"])
    ap.add_argument("--feature", required=True)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--gate", default=None, choices=list(GATES),
                    help="关卡编号，缺省 material_scope")
    ap.add_argument("--ask", default=None, help="decide：`status` 给出的问法编号 ask_id")
    ap.add_argument("--reply", default=None, help="decide：人的原话，逐字")
    ap.add_argument("--chosen", default=None,
                    help="decide：人选的选项编号或键——原话没写编号或标签时用；--propose 时是提议项")
    ap.add_argument("--propose", action="store_true", help="decide：记成模型的提议，不推进流程")
    ap.add_argument("--why", default=None, help="decide --propose：一句理由")
    ap.add_argument("--meeting", default=None,
                    help="会议版本 <主名>@<sha8>：decide --gate meeting 与 meeting-refresh 都用它")
    ap.add_argument("--item", default=None, help="meeting：会议判断里的话题 id")
    ap.add_argument("--update", dest="update_item", default=None,
                    help="decide：更新期间人定的一件事（与三级关卡无关，要有开着的 update）")
    ap.add_argument("--from", dest="from_path", default=None,
                    help="complete：要提交的提取稿，落点 " + "/".join(DESIGN_DRAFT))
    ap.add_argument("--action", default="inputs",
                    choices=["inputs", "prepare", "status", "close", "restore"],
                    help="update：本轮做哪一步（起手是 inputs：先报输入、问补料，再 prepare）")
    ap.add_argument("--request", default=None,
                    help="update：人这次明确要求改的事（原话）。只是「查一下有没有变化」不填——"
                         "填了就不会走无变化快速退出")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    result: dict = {"mode": args.mode, "reqNo": args.feature}
    try:
        project_root = Path(args.project_root).resolve() if args.project_root \
            else importer.DEFAULT_PROJECT_ROOT
        feature_root = project_root / importer.features_dir(project_root) / args.feature

        code = 0
        if args.mode == "init":
            result.update(cmd_init(feature_root, args.feature))
        elif args.mode == "round":
            result.update(cmd_round(feature_root))
        elif args.mode == "decide":
            if args.update_item:
                result.update(cmd_decide_update(feature_root, args.update_item,
                                                str(args.reply or "")))
            elif args.propose:
                result.update(cmd_propose(feature_root, args))
            else:
                payload, code = cmd_decide(feature_root, args)
                result.update(payload)
        elif args.mode == "status":
            result.update(cmd_status(feature_root))
        elif args.mode == "story":
            result.update(cmd_story(feature_root, project_root))
        elif args.mode == "archived":
            result.update(cmd_archived(feature_root, project_root))
        elif args.mode == "reopen":
            result.update(cmd_reopen(feature_root))
        elif args.mode == "meeting-refresh":
            result.update(cmd_meeting_refresh(feature_root, str(args.meeting or "").strip()))
        elif args.mode == "update":
            if args.action == "status":
                result.update(cmd_update_status(feature_root, args.feature, project_root))
            elif args.action == "close":
                result.update(cmd_update_close(feature_root))
            elif args.action == "restore":
                result.update(cmd_update_restore(feature_root))
            elif args.action == "inputs":
                result.update(cmd_update_inputs(feature_root, args.feature, project_root,
                                                 args.request))
            else:
                result.update(cmd_update_prepare(feature_root, args.request))
        else:
            result.update(cmd_complete(feature_root, args.feature, args.from_path))

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


if __name__ == "__main__":
    sys.exit(main())
