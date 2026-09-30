"""已交给设计、蓝图准入的需求工作区：成文与检查类用例从这里起步。

每份夹具每个进程只准备一次（复制夹具、放准入蓝图、用真实流程命令走到交给设计、按蓝图重投附录），
存档后复制给各用例。流程契约与冻结输入只记工程内相对路径，复制到别处照样成立；Framework 链接复制后重接。
"""
from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import design_kit
from ext_workspace import DEV_EXT, REPO_ROOT, link_framework
from flow_steps import walk_to_complete

ACCESS = design_kit.ACCESS
BUILD = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
FLOW = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"
#: 交给设计时提交的最小提取稿：五段结构齐全
DRAFT = (
    "# 需求 — 开发需求（AR）\n\n"
    "## 1 简介\n\n### 1.1 需求介绍\n\nx\n\n"
    "## 2 需求分析\n\n### 2.1 场景与功能点\n\nx\n\n"
    "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\nx\n\n"
    "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
    "## 5 上游已声明线索\n\n无。\n")


def ensure_flow_state(root: Path, feature: str, src: Path, draft_text: str) -> None:
    """skeleton 起手预检需要的流程状态：S1–S3 走完并收口（真实脚本生成契约）。

    08 §2.1 之后 skeleton 的起手预检要读流程契约与材料基准；夹具没有时，
    用真实流程命令把 S1–S3 走完并提交一份提取稿——生成的契约即收口态。
    """
    def flow(*args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", feature,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, f"{args}: {proc.stdout}\n{proc.stderr}"
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    if (src / "story-flow.json").is_file():
        # 已交给设计的工程：起手前 init 照常为没拉到的上游补占位件，round 把它登记进本轮
        flow("init")
        flow("round")
        return
    walk_to_complete(flow, src, draft_text)



#: 夹具激活的两条规约在蓝图里的判断：成文按已准入蓝图写，附录·规约由它投影
FIXTURE_DECISIONS = [
    design_kit.knowledge_decision("knowledge-smp-01", "SMP-01", "applicable", "本需求新增提交入口，受理单编号在入口生成"),
    design_kit.knowledge_decision("knowledge-smp-02", "SMP-02", "not_applicable", "本需求没有任何上报动作"),
]


#: 真实一跑（AR90006）的蓝图还带确认过的术语与一条埋点明细：术语起始行与附录·埋点都从蓝图来
REAL_RUN_DESIGN = {
    "terms": [design_kit.term_fact(term) for term in ("自动充值", "免密签约", "充值上限")],
    "details": [design_kit.story_detail("detail-event", "event", "签约转化", "统计点：签约成功时上报一次。")],
}


def designed_copy(fixture: Path, feature: str, draft: str, target: Path, design: dict | None = None) -> None:
    """夹具 + 已准入的蓝图 + 真实走过的交给设计：每个进程每份夹具只准备一次，存档后复制到 `target`。

    流程契约与冻结输入只记工程内相对路径，复制到别处照样成立；Framework 链接复制后重接。
    """
    key = (fixture, feature)
    if key not in _DESIGNED:
        base = Path(tempfile.mkdtemp(prefix="story-build-designed-")) / "work"
        atexit.register(shutil.rmtree, base.parent, True)
        shutil.copytree(fixture, base / "doc" / "features" / feature if fixture.name == feature else base)
        design_kit.prepare_designed(base, feature, flow_script=FLOW, build_script=BUILD, access=ACCESS, draft=draft,
                                    decisions=FIXTURE_DECISIONS, design=design)
        _DESIGNED[key] = base
    base = _DESIGNED[key]
    shutil.copytree(base, target, dirs_exist_ok=True,
                    ignore=lambda d, names: ["framework"] if Path(d) == base else [])
    link_framework(target)


_DESIGNED: dict[tuple, Path] = {}
