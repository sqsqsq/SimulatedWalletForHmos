"""只读与登记类命令：`status` 报位置，`story` 登记成文态，`archived` 记归档。

`story` 与 `archived` 沿正式命令路径调用 `story-build.mjs` 做成文检查，不反向导入入口。
"""
from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
import subprocess
from pathlib import Path

from flow.state import (
    CORE_DIR, DESIGN, FlowError, REVIEW, STORY, STORY_REGISTERED, ledger_digest, load, log,
    now, require, round_gates, save)
from flow.routing import (live_materials, material_state, next_step, reading_work, register_command,
                          sidecar_shape)
from flow import asks
from flow.update import record_baseline
from flow.meetings import topic_digest
from materials import meeting


def cmd_status(feature_root: Path) -> dict:
    contract = load(feature_root)
    # 材料事实**一份**：路由、收件箱提示与下面的 JSON 输出读的是同一个时点的清单。
    # 各自再 build 一次的话，同一条命令里会出现两份「现在的材料」，而消费者不知道
    # 自己拿的是哪一份。算不出来沿 FlowError 退出，不伪造 false。
    manifest = live_materials(feature_root) if (contract or {}).get("rounds") else None
    # 本地阅读同理：成文之后派生一次，路由与输出共用
    reading = reading_work(feature_root) if (contract or {}).get("status") == "story_written" else None
    step, action = next_step(feature_root, contract, manifest, reading)
    shape = sidecar_shape(step)
    # 到了停等点就生成问法并写侧车：人看到的选项块与 `decide` 核对的是同一份
    ask = asks.build(feature_root, contract, step) if contract and contract.get("rounds") else None
    if contract is None:
        out = {"exists": False, "next": step, "action": action}
        if shape:
            out["sidecar"] = shape
        return out

    current = contract["rounds"][-1] if contract.get("rounds") else {}
    # 只列**当前轮**：与 next 的判据一致，免得人看着历史决策去对现在的位置。
    # 历史查契约文件本身。
    gates = round_gates(contract) if contract.get("rounds") else []
    # 材料事实直接给出去：消费者（起手预检、作者包）按 pending/changed 判断，
    # 不从 `next` 的字面值反推——字面值只认得出其中一种情况。没有轮次时没有基准可比，
    # 给 null，不用 false 冒充「材料没问题」。
    state = material_state(feature_root, current, manifest) if manifest is not None else None
    topics = topic_digest(feature_root, meeting.read_notes(feature_root, []), contract)
    return {
        "exists": True,
        "schema": contract.get("schema"),
        "status": contract.get("status"),
        # 最近一次成文登记的时刻；重跑 `story` 就是重新登记
        "story_written_at": contract.get("story_written_at"),
        # 本地阅读与业务闭环分开报：成文之后才有阅读图要做
        **({"reading": reading} if reading is not None else {}),
        "round": current.get("round"),
        "positioning": current.get("positioning"),
        "gates": [{"gate": g.get("gate"), "chosen": g.get("chosen"),
                   "outcome": g.get("outcome"), "by": g.get("by")} for g in gates],
        "split": contract.get("split", {}).get("decided"),
        "design": bool((feature_root / Path(*DESIGN)).is_file()),
        "archived": bool(contract.get("archived")),
        "material_state": ({"pending": state["pending"], "changed": state["changed"]}
                           if state else None),
        # 会议话题在这里机械枚举一次：全部版本、全部话题，含不属于本需求与归属判不准的。
        # 模型据它向人呈现，不必自己把 notes 再列一遍；只在读会与摆关卡那几步给，别的步骤用不上它。
        **({"meetings": topics} if topics and "meeting" in step else {}),
        "next": step,
        "action": action,
        **({"ask": ask} if ask else {}),
        **({"sidecar": shape} if shape else {}),
    }


def cmd_story(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已成文」——spec 阶段三份产物的第三份到位了。

    story 在 **spec 阶段内**成文：先建十章骨架，再按合同顺序一次写一章、经命令原子落盘。
    成文有 spec 的阶段边界守着；逐章落盘让中途失败只影响那一章。

    **登记自带门禁**：先重跑 `story-build check`，通过才记。守恒判据在那里，
    不在这里重实现——两处各判各的，迟早对不上。

    **编号之前先重投影**：附录里按章节合同投影的几节是机器区，
    真源（spec 扩展章、knowledge-use.yaml）在成文期间还会变——补一条规约判断、改一个
    接口出参。以登记这一次为准，`story-build project` 从当前真源重算一遍。

    **check 之前先编号**：章序、小节序、图序是纯确定性变换，由 `story-build number`
    统一铺——作者写业务名标题就够了。编号在登记之前完成；命令幂等，已经对的文件一个字节都不改。

    **可以重复登记**：登记记下 story 与它的决策登记、写作设计此刻的指纹。之后改了任何一份
    （spec 阶段返修、update 修订），改完重跑本命令就是重新登记——上一次登记先作废，
    检查通过再记新的一次；检查没过时状态停在已收口、未登记，照报错改完再跑。
    """
    contract = require(load(feature_root))
    status = contract.get("status")
    invalidated = status == "story_written"
    #: 上一次登记的时刻与指纹：这次检查通过且登记内容逐份相同，仍是那一次成文
    prior = (contract.get("story_written_at"), contract.get("story_digests")) if invalidated else (None, None)
    if invalidated:
        for key in ("story_written_at", "story_digests"):
            contract.pop(key, None)
        contract["status"] = status = "complete"
        save(feature_root, contract)
        log("上一次成文登记已作废，按当前内容重新登记")
    if status != "complete":
        # 重拍范围之后直接来登记的常见一步：说出现在该做什么，不只说「不行」。
        # 下一步要按磁盘现状读材料；读不出来时「还没收口」照样先说，原因附在后面。
        try:
            _, action = next_step(feature_root, contract, live_materials(feature_root))
        except FlowError as exc:
            action = f"暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取下一步"
        raise FlowError(f"流程还没收口（status 是 {status}），成文态无从登记。下一步：{action}")
    story = feature_root / Path(*STORY)
    if not story.is_file():
        raise FlowError("AR/story.md 不存在：没有成文，无可登记的成文态")

    checker = CORE_DIR / "story-build.mjs"
    # 每一步按真源改派生件，check 只读。图源随这次登记一起成立（还没管理的 Mermaid 图加稳定标记、首次写 .mmd）；
    # review 也在这里渲染（机器区按当前决策件重算、人工区逐字节保留），下面那道 check 才核得到归档件红线（⑨）。
    steps = (("project", ["project"], "附录机器区已按当前真源重投"),
             ("number", ["number"], "编号已重铺"),
             ("view --mode prepare", ["view", "--mode", "prepare"], "图源管理标记与 .mmd 已就位"),
             ("build", ["build"], "review 已按决策登记重新渲染"),
             ("check", ["check"], "全篇检查通过"))
    done: list[str] = []
    rerun = f"再跑 `{register_command(feature_root)}` 重新登记"

    def stopped(i: int, what: str, this: str, todo: str) -> FlowError:
        """登记停在第 i 步：已完成、这一步、没跑的步骤与下一动作，都只取本次调用里的事实。"""
        return FlowError(
            f"{what}，成文登记没有提交" + ("，上一次登记已作废" if invalidated else "") + "。\n"
            + f"已完成：{'；'.join(done) or '无'}。{this}。没跑：{'、'.join(s[0] for s in steps[i:]) or '无'}。\n"
            + todo)

    node = shutil.which("node")
    if node is None:
        raise stopped(0, "找不到 node", "story-build 一步都没启动",
                      f"这是运行环境问题，业务稿与派生件都不用改：装好 node 后{rerun}")
    for i, (name, argv, effect) in enumerate(steps):
        try:
            proc = subprocess.run(
                [node, str(checker), *argv, "--feature", feature_root.name, "--project-root", str(project_root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise stopped(i, f"story-build {name} 没能启动（{exc}）", f"{name} 没有启动",
                          f"这是运行环境问题，业务稿与派生件都不用改：环境恢复后{rerun}") from exc
        if proc.returncode == 1:
            this = f"{name} 只读，没有改正文" if name == "check" else f"{name} 改没改文件不确定"
            raise stopped(i + 1, f"story-build {name} 没通过（退出码 1）", this,
                          "已更新的派生件按真源算出，不用删也不用还原；按下面 story-build 的报告处理它点名的真源、草稿或环境"
                          f"（正文经 chapter 提交），{rerun}：\n" + _said(proc))
        if proc.returncode != 0:
            raise stopped(i + 1, f"story-build {name} 没有正常结束（退出码 {proc.returncode}）", f"{name} 改没改文件不确定",
                          f"这不是业务稿的问题，不要为它改真源或草稿：{_not_the_product(proc.returncode)}，"
                          f"修好后{rerun}。原始输出：\n" + _said(proc))
        done.append(effect)

    digests = {rel: ledger_digest(feature_root / Path(*rel.split("/"))) for rel in STORY_REGISTERED}
    contract["status"] = "story_written"
    # 内容没变的重新登记不换登记时刻：使用记录据它认出同一次成文，不把重登当成新的完成
    contract["story_written_at"] = prior[0] if prior[0] and digests == prior[1] else now()
    # 登记记下 story 与它据以成文的决策登记、写作设计此刻的指纹：之后 `story-build check`
    # 与流程路由拿它核「登记之后改过没有」，改过就重跑 `story` 重新登记。
    #
    # 登记不动 `story-src/` 里的任何东西：章草稿、候选池、映射表都留在原地。
    # 它们走不漏到读者手上——归档只上传 story.md 与 review.md，`story-src/` 整层
    # 留在本地。留着的用处是实的：出了问题，它们是唯一能看出「这份 story 是怎么
    # 写出来的」的现场；登记之后要改某一章，手上也才有可改的东西。
    contract["story_digests"] = digests
    save(feature_root, contract)
    baseline = record_baseline(feature_root)
    # 登记之后真正的下一步与 `status` 同一条路由给出，不在这里另写一份；算不出来不遮住已成功的登记
    try:
        step, action = next_step(feature_root, contract, live_materials(feature_root))
    except FlowError as exc:
        step, action = "status", f"成文已登记；下一步暂时算不出来（{exc}），修好后跑 `story_flow.py status` 取"
    return {"status": "story_written", "story": str(story), "next": step, "action": action,
            **({"update_baseline": baseline} if baseline else {})}


#: 外层持有视图的标记：值是需求目录（小写绝对路径），story_flow 与 story-build 共用；带着同一需求的值进来就是子调用，不各自恢复
VIEW_OWNER = "STORY_VIEW_OWNER"


@contextmanager
def reading_view(feature_root: Path, project_root: Path, outcome: dict):
    """最外层动作持有视图：动手前回到正式形态（Mermaid 按源、阅读槽置空），结束或失败后恢复当前可用的阅读图。

    被它调起的 story-build 子命令继承 `STORY_VIEW_OWNER`，不再切入，也不各自恢复。恢复失败只补视图，
    写进 `outcome["view"]`，不遮住原来的结果或错误。
    """
    key = os.path.realpath(feature_root).lower()
    before = os.environ.get(VIEW_OWNER)
    owner = before != key
    if owner:
        os.environ[VIEW_OWNER] = key
    try:
        if owner:       # 同一需求的外层已切入并持有：不再切一遍
            ensure_mermaid(feature_root, project_root)
        yield
    finally:
        if owner:
            if before is None:
                os.environ.pop(VIEW_OWNER, None)
            else:
                os.environ[VIEW_OWNER] = before
            story = feature_root / Path(*STORY)
            if story.is_file() and _managed(story):
                try:
                    outcome["view"] = _view(feature_root, project_root, "svg", "本地阅读图没有恢复，story 保持 Mermaid")
                except FlowError as exc:
                    outcome["view"] = str(exc)


def _managed(story: Path) -> bool:
    """story 里有没有脚本管理区：正式图块或阅读图槽，任一种都要经视图处理。"""
    text = story.read_text(encoding="utf-8", errors="replace")
    return "<!-- story-figure:" in text or "<!-- story-reading:" in text


def ensure_mermaid(feature_root: Path, project_root: Path) -> None:
    """story 里有管理区时先回到正式形态：比较、登记与归档只认 Mermaid 按源、阅读槽为空的文本。没有管理区不起进程。"""
    story = feature_root / Path(*STORY)
    if not story.is_file() or not _managed(story):
        return
    _view(feature_root, project_root, "mermaid", "读 story 之前要先回到正式形态，回不去")


def _view(feature_root: Path, project_root: Path, mode: str, why: str) -> str:
    node = shutil.which("node")
    if node is None:
        raise FlowError(f"找不到 node：{why}（视图切换由 story-build.mjs view 做）")
    proc = subprocess.run(
        [node, str(CORE_DIR / "story-build.mjs"), "view", "--mode", mode, "--feature", feature_root.name,
         "--project-root", str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        raise FlowError(f"{why}：\n" + _said(proc))
    return _said(proc)


def _not_the_product(code: int) -> str:
    """story-build 退出码既不是 0 也不是 1：归谁处理。"""
    return "这是 story-build 自身异常，归扩展维护者处理" if code == 2 else "进程被中断或运行环境出错"


def _said(proc: subprocess.CompletedProcess) -> str:
    """子进程的两路输出原样带回：问题清单常在一路、恢复入口在另一路，只取一路就丢了一半。"""
    return "\n".join(x.strip() for x in (proc.stdout, proc.stderr) if x and x.strip()) \
        or f"退出码 {proc.returncode}，没有任何输出"


def cmd_archived(feature_root: Path, project_root: Path) -> dict:
    """登记「叙事件已送审」。归档动作由数据对接层执行，本命令只记状态。

    归档态是**流程状态**，落在流程契约里：装配脚本据它判定 `AR/review.md` 已归人所有，
    此后重新渲染时人工区逐字保留、机器区按当前决策件重算，评审人的批注与回稿都留在那份文件里。判据在契约里，
    与谁执行的归档无关——数据对接层由各部署环境自备实现，不随交付走。

    **登记自带门禁**：先重跑一次 `story-build check`，通过才记——归档时 story 可能又改过，
    成文态那次的校验不算数。登记不可逆，凭据只认校验过的产物。
    """
    contract = require(load(feature_root))
    if contract.get("status") != "story_written":
        raise FlowError(
            "还没登记成文态：归档的是 story，story 没过 check 就归档等于把未校验的产物送审。"
            "先跑 `story_flow.py story --feature <名>`")
    story, review = feature_root / Path(*STORY), feature_root / Path(*REVIEW)
    for path, name in ((story, "AR/story.md"), (review, "AR/review.md")):
        if not path.is_file():
            raise FlowError(f"{name} 不存在：归档件不全，无可登记的归档态")

    checker = CORE_DIR / "story-build.mjs"
    # 走到这里需求系统那边已经写入并读回：失败只说本地登记没完成，下一步只补登记，不重新上传
    again = (f"只补登记：`{register_command(feature_root, 'archived')}`；需求系统里已上传的那一份不受影响，不要重新上传")
    node = shutil.which("node")
    if node is None:
        raise FlowError(f"找不到 node，交付门没跑，归档态没有登记。这是运行环境问题：装好 node 后{again}")
    # 交付门而不是普通 check：走到这里 spec 该已经闭环，读者审查也该已经落报告。
    # 普通 check 判不到那两样，用它登记归档态等于把「审没审过」这一格空着送审。
    try:
        proc = subprocess.run(
            [node, str(checker), "check", "--deliver", "--feature", feature_root.name,
             "--project-root", str(project_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise FlowError(f"交付门没能启动（{exc}），归档态没有登记。这是运行环境问题：环境恢复后{again}") from exc
    if proc.returncode == 1:
        raise FlowError(
            "交付门这次没通过，归档态没有登记。它核的是本地工作区当前的 AR/story.md、AR/review.md 与审查回执，"
            f"不是需求系统里那一份；按下面的输出处理它点名的问题后{again}。本地业务稿确实要改的，走 `/story update`。"
            "交付门原始输出：\n" + _said(proc))
    if proc.returncode != 0:
        raise FlowError(f"交付门没有正常结束（退出码 {proc.returncode}），归档态没有登记。"
                        f"这不是归档件的问题：{_not_the_product(proc.returncode)}，修好后{again}。原始输出：\n"
                        + _said(proc))

    contract["archived"] = {"at": now()}
    save(feature_root, contract)
    log(f"已登记归档态：{feature_root.name}——此后 AR/review.md 归人所有，重新渲染时人工区逐字保留")
    return {"archived": True, "at": contract["archived"]["at"]}
