"""S4 提取稿的提交（`complete`）：候选核对、三份输入身份与原件留存。

提交前先核候选是不是还是空骨架、章号是不是连续；提交时把被覆盖的那份上游原件按轮次
留存下来——提交之后 `AR/design.md` 里是本轮提取稿，上游原话只在 sources 里还找得到。
"""
from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from materials import registry

from flow.state import (
    AR_SOURCES, DESIGN, DESIGN_DRAFT, FlowError, S4_STEPS, after_complete, load, log, now,
    require, save)
from flow.inputs import ar_design_skeleton, read_ids
from flow.routing import material_state, scope_step


#: 提取稿的五段：代码围栏外、带序号的二级标题。序号后的点可有可无。
S4_HEADING = re.compile(r"^##\s+(\d+)\s*\.?\s+\S")


def resolve_candidate(feature_root: Path, given: str | None) -> Path:
    """`--from` 指的那份提取稿。相对路径相对需求根，且必须落在需求根内。"""
    if not str(given or "").strip():
        raise FlowError("缺 --from：收口提交的是你写好的提取稿，"
                        f"落点 {'/'.join(DESIGN_DRAFT)}")
    raw = Path(str(given).strip())
    target = raw if raw.is_absolute() else feature_root / raw
    try:
        target.resolve().relative_to(feature_root.resolve())
    except (OSError, ValueError):
        raise FlowError(f"提取稿在需求目录外：{given}。它是本需求的产物，"
                        "路径按相对需求根写") from None
    if not target.is_file():
        raise FlowError(f"提取稿不在：{given}。按 rules/ar_design_init.md 提取，"
                        f"写到 {'/'.join(DESIGN_DRAFT)}，再跑这条命令")
    return target


def section_numbers(text: str) -> list[int]:
    """正文里的二级标题序号，按出现顺序。围栏里的标题不算——那是被引用的样例。"""
    out: list[int] = []
    fenced = False
    for raw in text.split("\n"):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        hit = S4_HEADING.match(line)
        if hit:
            out.append(int(hit.group(1)))
    return out


def is_ar_skeleton(feature_root: Path, feature: str, text: str) -> bool:
    """这份 AR/design.md 还是 `init` 落的空骨架。

    空骨架不是上游给的东西，正文只有段标题和写给模型的判定指引。把它留存成
    「本轮外部输入」的话，后续按原件读上游原话的作者与审查，
    就会把一份写给模型的指引当成需求原话。
    """
    return text.replace("\r\n", "\n") == ar_design_skeleton(read_ids(feature_root, feature))


def candidate_problems(feature_root: Path, feature: str, text: str) -> list[str]:
    """提取稿立不立得住——**只核结构，不核内容**。

    内容对不对由 spec 与评审看。这里挡的是「交上来的还是那份空骨架」和
    「五段结构塌了」：两样都会让 /spec 的输入从一开始就缺一块，而缺的那一块
    要到阶段门禁上才被发现，那时提取早已过去几步。
    """
    if not text.strip():
        return ["提取稿是空的"]
    if is_ar_skeleton(feature_root, feature, text):
        return ["提取稿与 init 落的空骨架逐字节相同：提取内容还没写"]
    numbers = section_numbers(text)
    if numbers[:5] != [1, 2, 3, 4, 5]:
        return ["五段结构对不上（rules/ar_design_init.md §3）：读到的二级标题序号是 "
                + (str(numbers) if numbers else "一个都没有")
                + "，要的是 1 简介 / 2 需求分析 / 3 SE 方案摘要 / 4 上游索引 / "
                  "5 上游已声明线索"]
    return []


def ar_input_identities(feature_root: Path, feature: str, contract: dict,
                        keep: Path) -> list[tuple[str, str | None]]:
    """被覆盖前那一份 AR 的合法身份：`(内容摘要, 原输入定位)` 逐一列出。

    三类来源各有确定证据——本轮已留存的原件、`init` 落的空骨架（不是外部输入，
    定位为 None；行尾两种形态都认）、契约里已登记的上一轮提取稿（沿它自己的
    origin）。这是「被覆盖的 AR 是谁」仅有的答案集：中间态识别与原输入定位
    共用这一份枚举，出现新场景时加在这里，不在调用方各自猜。
    """
    keep_rel = keep.relative_to(feature_root).as_posix()
    identities: list[tuple[str, str | None]] = []
    if keep.is_file():
        identities.append((registry.file_digest(keep), keep_rel))
    skeleton = ar_design_skeleton(read_ids(feature_root, feature))
    for text in (skeleton, skeleton.replace("\n", "\r\n")):
        identities.append(("sha256:" + sha256(text.encode("utf-8")).hexdigest()[:16], None))
    registered = contract.get("design") or {}
    if registered.get("sha256"):
        identities.append((registered["sha256"], registered.get("origin")))
    return identities


def prior_ar(feature_root: Path, feature: str, contract: dict,
             keep: Path, prior_sha: str | None) -> str | None:
    """被这次提交覆盖掉的那一份 AR，它的原输入定位。

    身份枚举见 `ar_input_identities`：留存件、空骨架、已登记提取稿三类各有
    确定证据，都对不上就说明这份 AR 的来历说不清——调用方据此停下，
    不能把一份来历不明的文件默认当成上游输入存进来源。
    """
    for sha, origin in ar_input_identities(feature_root, feature, contract, keep):
        if sha == prior_sha:
            return origin
    raise FlowError(
        f"AR/design.md 的来历说不清（摘要 {prior_sha}）：既不是本轮已留存的原件，"
        "也不是 init 的空骨架或契约里登记过的提取稿。先确认它是谁写的，"
        "再跑收口——把一份来历不明的文件存成上游输入，下游就会拿它当需求原话")


def cmd_complete(feature_root: Path, feature: str, from_arg: str | None) -> dict:
    """把提取稿提交为 AR/design.md 并收口。

    顺序固定：**留存原输入 → 覆盖 AR/design.md → 刷新材料与本轮基准 → 记 complete**。
    `complete` 最后写，所以中途断掉时状态仍是未收口，重跑同一条命令即可——
    每一步都能从磁盘现状认出自己做没做过，不靠回滚副本，也不另记一份进度。
    """
    contract = require(load(feature_root))
    candidate = resolve_candidate(feature_root, from_arg)
    cand_bytes = candidate.read_bytes()
    try:
        cand_text = cand_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FlowError(f"提取稿不是 UTF-8：{from_arg}") from None

    rel = "/".join(DESIGN)
    design_path = feature_root / Path(*DESIGN)
    design_bytes = design_path.read_bytes() if design_path.is_file() else None
    total = sum(len(r.get("gates", [])) for r in contract["rounds"])
    if after_complete(contract):
        if contract.get("status") == "complete" and design_bytes == cand_bytes:
            log("已经收口过了：AR/design.md 就是这份提取稿，没有重复提交")
            return {"status": "complete", "rounds": len(contract["rounds"]),
                    "gates": total, "committed": False}
        raise FlowError(
            "本轮已经收口，AR/design.md 里是已提交的那一份提取稿。要换掉它，"
            "先跑 `story_flow.py reopen` 重新走范围与收口——下游从收口那一刻起就在读它，"
            "悄悄换一份，读到的和登记的就成了两份")

    current = contract["rounds"][-1]
    base = (current.get("materials") or {}).get("digest")
    try:
        recorded = registry.read(feature_root)
        live = registry.build(feature_root)
    except registry.MaterialError as exc:
        raise FlowError(str(exc)) from exc
    keep = feature_root / Path(*AR_SOURCES) / f"r{current.get('round', 1)}.md"
    keep_rel = keep.relative_to(feature_root).as_posix()
    # 本轮登记的那一版 AR/design.md 的身份。**清单可能已经按提交后的现状刷新过**
    # （断点落在刷新之后、契约保存之前）：那时被覆盖的那一份在三类合法身份里，
    # 哪一个换回 AR 那一格还能复现旧基准，哪一个就是本轮登记过的原输入——
    # 「除自己提交外材料未变」由此有确定答案。身份枚举与 prior_ar 共用同一份。
    prior_sha = None
    refreshed_unsaved = False
    if recorded.get("digest") == base:
        prior_sha = registry.source_sha(recorded, rel)
    else:
        for sha, _origin in ar_input_identities(feature_root, feature, contract, keep):
            if sha and registry.digest_with(live, rel, sha) == base:
                prior_sha = sha
                refreshed_unsaved = True
                break
    if prior_sha is None and recorded.get("digest") != base:
        raise FlowError(
            f"材料清单（{recorded.get('digest')}）与本轮登记的基准（{base}）对不上："
            "先跑 `story_flow.py round` 让轮次与清单归位，再收口")
    kept_is_prior = keep.is_file() and prior_sha is not None \
        and registry.file_digest(keep) == prior_sha
    # 覆盖已经发生过——这是同一条命令的重试。**判据是原输入还在不在**，不是候选一个
    # 字节没变：断点可能落在覆盖写到一半，那一刻盘上既不是原输入也不是完整候选；
    # 重跑之前又改一句提取稿也是正常的。留存件在、且摘要等于本轮登记的那一版，
    # 就证明上游原话已经保住，此后 `AR/design.md` 里是什么都是这条命令自己的中间产物。
    #
    # 反过来，只覆盖没留存时这里判不出重试：那份 AR 的来历没有证据，
    # 认成自己的写入等于把本轮真实的材料变化盖掉。
    retry = design_bytes == cand_bytes or kept_is_prior or refreshed_unsaved

    # 收件箱里还躺着原件时不收口：那时定的范围建立在一份不全的材料上。
    # 用的是上面那份 live——同一条命令、同一个写入前时点，不再把同一批材料转第二遍。
    state = material_state(feature_root, current, live)
    if state["pending"]:
        raise FlowError("收件箱里有还没并入正文的原件，先导入再收口："
                        + "、".join(state["pending"][:3]))
    # 材料必须仍与本轮基准一致。**AR/design.md 单独问**：重试时它已经是提取稿了，
    # 拿整份材料版本去判「变没变」，答案永远是变了；把它换回本轮登记的那一版再算，
    # 「其余材料动没动」才有确定答案。没重试过的话，它自己也必须还是登记的那一版。
    if registry.digest_with(live, rel, prior_sha) != base \
            or (not retry and live.get("digest") != base):
        raise FlowError("材料在这一轮登记之后又变了：重跑 `story_flow.py round` "
                        "登记新一轮，拿新材料重新盘点，再收口")

    # 收口的前置是**本轮范围已定**，而不是某一条特定记录——补料会开新一轮，
    # 上一轮定的范围不能替这一轮授权。判据与 next_step 同源（同一个 scope_step），
    # 定位/选项集缺失时它会报 run_analysis，不必在这里另判一遍。
    step, action = scope_step(feature_root, contract)
    if step not in S4_STEPS:
        raise FlowError(f"本轮范围尚未定下来，还不能收口：{action}（`status` 的 next 是 {step}）")
    if contract["split"]["decided"] == "split" and \
            not str(contract["split"].get("scope_text") or "").strip():
        raise FlowError("拆分已定案但 split.scope_text 为空：范围文字丢失，无法写入 design.md")
    problems = candidate_problems(feature_root, feature, cand_text)
    if problems:
        raise FlowError("提取稿还不能提交：" + "；".join(problems))

    registered = contract.get("design") or {}
    done: list[str] = []
    try:
        if retry:
            origin = prior_ar(feature_root, feature, contract, keep, prior_sha)
        elif design_bytes is None \
                or is_ar_skeleton(feature_root, feature,
                                  design_bytes.decode("utf-8-sig", errors="replace")):
            origin = None                        # 空骨架不是上游给的东西，没什么可留存
        elif registered.get("sha256") == prior_sha:
            origin = registered.get("origin")    # 是上一轮的提取稿：沿用它所指的原输入
        elif keep.is_file():
            raise FlowError(
                f"{keep_rel} 已存在，内容却与当前 AR/design.md 不同：同一轮的原输入"
                "只有一份。先确认这一轮到底是哪一份，别让覆盖抹掉另一份")
        else:
            # 上游这一轮给了新的 AR：先留存，再覆盖。覆盖之后上游原话只在这里还找得到。
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_bytes(design_bytes)
            done.append(keep_rel)
            origin = keep_rel

        if design_bytes != cand_bytes:
            design_path.parent.mkdir(parents=True, exist_ok=True)
            design_path.write_bytes(cand_bytes)     # 脚本只提交，不改一个字节
            done.append(rel)

        manifest = registry.refresh(feature_root)
        current["materials"] = {"path": "/".join(registry.MANIFEST),
                                "digest": manifest["digest"]}
        done.append("/".join(registry.MANIFEST))

        # 收口时的 design.md 身份登记：`sha256` 用于认出「上一轮的提取稿」——
        # 重试与跨轮的原输入定位都拿它对身份；`origin` 指出它盖掉的原输入在哪。
        # 它不是冻结比对基准：归档会用评审载体覆盖这份文件，拿登记哈希去比
        # 归档后的当前 AR 必然误报；成文依据的冻结比对走 story_src_digests 那一套。
        contract["design"] = {"sha256": registry.file_digest(design_path), "origin": origin}
        contract["design_generated_at"] = now()
        contract["status"] = "complete"
        save(feature_root, contract)     # **最后写**，同样在提交失败处理内：
        # 这里断了，清单已是新基准而流程契约还是旧的——重跑同一条命令，
        # 预检会凭留存件认出这个中间态，直接补上这次保存。
    except (OSError, registry.MaterialError) as exc:
        raise FlowError(
            f"提交中途失败（{exc}）。已完成：{'、'.join(done) or '无'}；"
            "流程仍是未收口，原输入与提取稿都在。修好之后重跑同一条 complete 命令"
        ) from exc

    log(f"流程收口：{len(contract['rounds'])} 轮、{total} 条关卡记录"
        + (f"；原输入留存于 {origin}" if origin else ""))
    return {"status": "complete", "rounds": len(contract["rounds"]), "gates": total,
            "committed": True, "origin": origin}
