"""已交给设计、蓝图准入的需求工作区：成文与检查类用例从这里起步。

每份夹具只准备一次（复制夹具、放准入蓝图、用真实流程命令走到交给设计、按蓝图重投附录），各进程与之后各轮共用
（`shared_state`，键是输入内容的摘要），复制给各用例。流程契约与冻结输入只记工程内相对路径，复制到别处照样成立；
Framework 链接复制后重接。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import design_kit
import shared_state
from ext_workspace import DEV_EXT, REPO_ROOT, link_framework
from flow_steps import walk_to_complete

ACCESS = design_kit.ACCESS
BUILD = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
FLOW = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"
def ensure_flow_state(root: Path, feature: str, src: Path) -> None:
    """skeleton 起手预检需要的流程状态：S1–S3 走完、范围已定、同根蓝图已准入（真实脚本生成契约）。

    skeleton 的起手预检要读流程契约与材料基准；夹具没有时，用真实流程命令把 S1–S3 走完。
    """
    def flow(*args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), *args, "--feature", feature,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, f"{args}: {proc.stdout}\n{proc.stderr}"
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    # 流程按原生身份找需求目录：先接被测 Framework
    design_kit.ensure_framework(root)
    if (src / "story-flow.json").is_file():
        # 已走过关卡的工程：起手前 init 照常补工作区骨架，round 把现状登记进本轮
        flow("init")
        flow("round")
        return
    walk_to_complete(flow, src)



#: 夹具激活的两条规约在蓝图里的适用性判断：成文按当前蓝图写，附录·规约按它写
FIXTURE_JUDGEMENTS = [
    design_kit.rule_judgement("SMP-01", "applied", "本需求新增提交入口，受理单编号在入口生成"),
    design_kit.rule_judgement("SMP-02", "not_applicable", "本需求没有任何上报动作"),
]


#: 真实一跑（AR90006）的蓝图还带确认过的术语与一条埋点明细：术语起始行与附录·埋点都从蓝图来；
#: 它激活的是开发版知识，判断落在那几条真实规约上（同域其余逐条判不涉及，其余域整域不涉及）
REAL_RUN_DESIGN = {
    "judgements": [
        design_kit.rule_judgement("OBS-02", "applied", "本需求新增提交入口，受理单编号在入口生成"),
        design_kit.rule_judgement("OBS-03", "not_applicable", "本需求没有任何上报动作"),
    ],
    "terms": [design_kit.term_fact(term) for term in ("自动充值", "免密签约", "充值上限")],
    "details": [design_kit.story_detail("detail-event", "event", "签约转化", "统计点：签约成功时上报一次。")],
}


def designed_copy(fixture: Path, feature: str, target: Path, design: dict | None = None) -> None:
    """夹具 + 已准入的蓝图 + 真实走过的交给设计：同一组输入只准备一次，复制到 `target`。

    流程契约与冻结输入只记工程内相对路径，复制到别处照样成立；Framework 链接复制后重接。
    """
    def build(base: Path) -> None:
        shutil.copytree(fixture, base / "doc" / "features" / feature if fixture.name == feature else base)
        spec = dict(design or {})
        judgements = spec.pop("judgements", FIXTURE_JUDGEMENTS)
        design_kit.prepare_designed(base, feature, flow_script=FLOW, build_script=BUILD, access=ACCESS,
                                    judgements=judgements, design=spec)

    key = shared_state.digest(fixture, *shared_state.COMMON, feature, shared_state.framework_version(),
                              json.dumps(design or {}, ensure_ascii=False, sort_keys=True, default=str))
    base = shared_state.shared_tree("designed", key, build)
    shared_state.copy_tree(base, target)
    link_framework(target)
