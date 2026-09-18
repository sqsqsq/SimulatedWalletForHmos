"""story_flow.py — init→spec 流程契约（`AR/story-src/story-flow.json`）的**唯一写入者**。

契约记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项，
事后可查、可推翻。

契约同时是这条流程的**状态机**：`status` 子命令读它就能回答「现在走到哪、下一步干什么」。
所以 skill 正文不必维护成篇的分支判定文本——位置由数据回答，不由记忆回答。

契约里绝大多数内容是机械事实——时间戳、轮次边界、收件箱里还有没有没导过的料。
这类事实靠记忆复现就会失真，所以一律由脚本自取。

分工因此是：**判断留 AI，执行归脚本**（与 `import_sources.py` 的归类件同一条边界）。
AI 只传它真正知道而脚本无从得知的东西——人选了哪一项、依据是什么；其余一律脚本自己取。
本轮导入了什么也在「脚本自己取」这一侧：`round` 每次调用都让材料清单按磁盘现状
重算材料清单，从清单里读出哪些原件已经并入正文——没有回执，也不需要谁记住发生过什么。

    python story_flow.py init     --feature <AR>
    python story_flow.py round    --feature <AR>
    python story_flow.py decide   --feature <AR> --gate <g> --chosen <c> --basis <t>
    python story_flow.py meeting-refresh --feature <AR> --meeting <主名>@<sha8>
    python story_flow.py status   --feature <AR>
    python story_flow.py complete --feature <AR> --from AR/story-src/design-draft.md
    python story_flow.py story    --feature <AR>
    python story_flow.py reopen   --feature <AR>
    python story_flow.py archived --feature <AR>

`init` 与 `archived` 不写轮次，写的是**工作区骨架**与**归档态**：这两件事的执行方
（数据对接层 story.js）不随交付走，各部署环境自备实现，所以判据不能挂在它落的文件上。

公共参数：`--project-root <abs>`。stdout 单行 JSON；人类可读日志走 stderr。
**参数只放标量**：JSON 全是引号，而任何 shell 都要对参数再解析一遍——同一条命令
bash 下原样送达、Windows PowerShell 下双引号被吞。结构化数据一律走文件：
选项集走 `AR/story-src/.gate-options.json`、本 AR 定位走 `AR/story-src/.positioning.json`、
拆分份表走 `AR/story-src/.split-parts.json`，脚本读后即销毁（一次性）。

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
- **摆过的选项与选中的那项一起记**。只记 `chosen` 的话，「看过选项后选了不拆」与
  「压根没生成拆分选项」在事后完全同形，后者可以伪装成前者通过全部门禁。
  因此 `options` 必填，且 `chosen` 必须是其中一项：**选的只能是摆出来的**；
- 时间戳一律由本脚本取当下，调用方碰不到该字段。

本文件只做参数解析、分派与顶层输出；每条命令的实现在 `flow/` 下按职责分开：
契约读写与常量在 `state`，一次性侧车与骨架在 `inputs`，「现在走到哪」在 `routing`，
`decide`/`round`/`complete`/`status` 各在 `decisions`/`rounds`/`submission`/`lifecycle`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from materials import importer

from flow.state import DESIGN_DRAFT, FlowError, GATES, log
from flow.inputs import MATERIAL_CHOICES, cmd_init
from flow.decisions import cmd_decide
from flow.rounds import cmd_reopen, cmd_round
from flow.submission import cmd_complete
from flow.lifecycle import cmd_archived, cmd_status, cmd_story
from flow.meetings import cmd_meeting_refresh


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="story init→spec 流程契约的唯一写入者")
    ap.add_argument("mode",
                    choices=["init", "round", "decide", "status", "complete", "reopen",
                             "story", "archived", "meeting-refresh"])
    ap.add_argument("--feature", required=True)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--gate", default=None, choices=list(GATES),
                    help="关卡编号，缺省 material_scope")
    ap.add_argument("--chosen", default=None,
                    help="选中项的 key；material_scope 为 " + " / ".join(MATERIAL_CHOICES))
    ap.add_argument("--basis", default=None, help="决策依据：用户原话，或授权原话 + 推荐理由")
    ap.add_argument("--meeting", default=None,
                    help="会议版本 <主名>@<sha8>：decide --gate meeting 与 meeting-refresh 都用它")
    ap.add_argument("--item", default=None, help="meeting：会议判断里的话题 id")
    ap.add_argument("--from", dest="from_path", default=None,
                    help="complete：要提交的提取稿，落点 " + "/".join(DESIGN_DRAFT))
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
        else:
            result.update(cmd_complete(feature_root, args.feature, args.from_path))

        result["success"] = code == 0
        print(json.dumps(result, ensure_ascii=False))
        return code
    except FlowError as exc:
        log(str(exc))
        result.update(success=False, error=str(exc))
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
