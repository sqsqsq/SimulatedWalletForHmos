"""作者动笔之前手上有什么：成文要用的当前输入、位置与文件形状。

两轮真实实跑里，作者有相当一部分时间不是在写需求，而是在**找答案**：图有几张、哪张要引、
命令的路径以哪里为基准、下一步写哪个文件、章文件要不要带标题。这些答案都是确定的，
也都早就在磁盘上（材料清单、上游原件、流程契约）。缺的是送达。

所以这一组判的是**送达**，不是判据：

  ① 成文输入（材料里的图、系统设计里的图）由真源渲染，`story-build skeleton` 起手时一并打印；
  ② 位置与文件形状由 `status` 回答，一处真源；
  ③ 章文件带了本章标题时命令自己剥掉——两跑都为这件事重建过骨架；
  ④ 作者页给的验收示例，形状与消费方一致。

不判内容质量：写得好不好、作者照没照做，那是实跑与评审看的事。
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from flow_steps import ensure_framework, walk_to_complete
import design_kit  # noqa: E402
from ext_workspace import link_harness_yaml, DEV_EXT

REPO_ROOT = Path(__file__).resolve().parents[2]
EXT = DEV_EXT
CONTRACT = EXT / "skills" / "story" / "contracts" / "story-chapters.json"
FLOW_SCRIPT = EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"
FEATURE = "TP90001"
#: 协议齐全的最小写作设计：章提交要读得了设计，测章文件处理的用例起手前放它。
PLAN_FIXTURE = (REPO_ROOT / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo"
                / "good" / "doc" / "features" / "REQ-DEMO" / "AR" / "story-src" / "story-template.md")



# 机制按运行环境选 shell（`story/drafts.mjs` 的 `SHELL`）：有 SHELL 变量的是 POSIX shell，
# Windows 上没有它的是 PowerShell。测试用同一条规则选，跑的就是机制引参数时对准的那个。
SHELL = "bash" if os.environ.get("SHELL") or os.name != "nt" else "powershell"


def run_in_shell(command: str, cwd=None) -> subprocess.CompletedProcess:
    """把渲染出来的命令**原样交给宿主的命令行**跑一遍。"""
    exe = shutil.which("pwsh") or shutil.which("powershell")
    args = ([exe, "-NoProfile", "-Command", command + "; exit $LASTEXITCODE"]
            if SHELL == "powershell" else ["bash", "-lc", command])
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180,
                          cwd=None if cwd is None else str(cwd))


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90, cwd=cwd)


def as_url(path: Path) -> str:
    """Windows 上动态 import 只认 file:// URL。"""
    return json.dumps(path.resolve().as_uri())


FLOW_SCRIPT = DEV_EXT / "skills/story/scripts/core/story_flow.py"
DRAFT_TEXT = (
    "# AR90001 — 开发需求（AR）\n\n"
    "## 1 简介\n\n### 1.1 需求介绍\n\nx\n\n"
    "## 2 需求分析\n\n### 2.1 场景与功能点\n\nx\n\n"
    "## 3 SE 方案摘要（本部件相关）\n\n### 3.1 全局方案与部件分工\n\nx\n\n"
    "## 4 上游索引\n\n| 信息类别 | SR 章节 | 本流程消费步骤 |\n| --- | --- | --- |\n\n"
    "## 5 上游已声明线索\n\n无。\n")


def ensure_flow_state(root: Path, feature: str, src: Path, draft_text: str) -> None:
    """skeleton 起手预检需要的流程状态：S1–S3 走完并收口（真实脚本生成契约）。"""
    if (src / "story-flow.json").is_file():
        return
    def flow(*args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW_SCRIPT), *args, "--feature", feature,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(root))
        assert proc.returncode == 0, f"{args}: {proc.stdout}\n{proc.stderr}"
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    walk_to_complete(flow, src, draft_text, "本 AR 承载自动充值签约与管理")


class WorkspaceCase(unittest.TestCase):
    """每个用例一份新工作区，扩展是真的那一份。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)

    def inputs(self, feature: str = FEATURE) -> str:
        """`story-build skeleton` 打印的成文输入：同一个函数、同一份来源状态，不必先把骨架的前置条件全摆齐。"""
        core = self.root / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story"
        proc = run("node", "--input-type=module", "-e",
                   f"const c = await import({as_url(core / 'context.mjs')});"
                   f"const s = await import({as_url(core / 'sources.mjs')});"
                   f"const i = await import({as_url(core / 'story-inputs.mjs')});"
                   f"const ctx = c.createContext({{ feature: {json.dumps(feature)},"
                   f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                   "process.stdout.write(i.storyInputs(ctx, s.sourceStatus(ctx)).join('\\n'));",
                   cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout


class TheAuthorDoesNotHaveToLookThingsUp(WorkspaceCase):
    """验收落在哪各处说法一致：路径写错一个层级，作者就去框架里找真相。"""

    def test_no_delivery_surface_still_says_spec_acceptance(self) -> None:
        """四处消费者一起改——留一处，作者照样会撞上说法不一。"""
        import subprocess
        proc = subprocess.run(
            ["git", "grep", "-l", "--fixed-strings", "spec/acceptance.yaml",
             "--", "doc/extensions"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual("", proc.stdout.strip(), f"还有地方写着旧路径：{proc.stdout}")


class UpstreamDiagramsReachTheAuthor(WorkspaceCase):
    """系统设计里的图逐张给身份、主题与**原件坐标**，不指定放哪一章。

    不复制围栏原文：副本一旦与原件不同步，作者改的是副本；输入也因此长到一次读不完。
    设计事实来自蓝图，Story 不从 Spec 搬图，输入里也就没有 Spec 那一节。
    """

    SR = ("# 系统设计\n\n## 5. 业务流程\n\n### 5.2 自动充值触发\n\n"
          "```mermaid\ngraph TD\nC[余额上报] --> D[判定]\n```\n")

    def inputs_with_sr(self) -> str:
        sr = self.feature_root / "SR" / "design.md"
        sr.parent.mkdir(parents=True, exist_ok=True)
        sr.write_text(self.SR, encoding="utf-8")
        return self.inputs()

    @staticmethod
    def section_4a(package: str) -> str:
        return package.split("## 4a.", 1)[1].split("\n## ", 1)[0]

    def test_each_diagram_comes_with_coordinates_and_its_content(self) -> None:
        """身份、标记写法、原件位置之外，源图内容就在这里：作者对着原图的关系画，不必再去翻原件。"""
        package = self.inputs_with_sr()
        self.assertIn("系统设计里的图", package)
        self.assertIn("SR §5.2 #1", package, "没给身份，作者不知道标记写什么")
        self.assertIn("`%% 图源 SR §5.2 #1`", package, "没给标记的写法，搬过去就核不到")
        self.assertIn("SR/design.md", package, "没给原件路径")
        self.assertRegex(package, r"第 \d+–\d+ 行", "没给围栏在原件里的行范围")
        self.assertIn("C[余额上报]", package, "源图内容没送到，作者只能按行号自己去读")

    def test_an_unreadable_upstream_is_a_problem_not_an_empty_section(self) -> None:
        """系统需求（AR 开头）的系统设计该有却读不到：要报出来，静默给一节空的，作者会以为上游没画过图。"""
        remote = f"AR{FEATURE}"
        shutil.copytree(self.feature_root, self.feature_root.parent / remote)
        section = self.section_4a(self.inputs(remote))
        self.assertIn("读不到 `SR/design.md`", section)
        self.assertIn("找回来", section)

    def test_a_local_ticket_without_a_system_design_is_not_a_loss(self) -> None:
        """本地单没有需求系统给的系统设计是正常的：照合同说「本需求没有」，不报丢件。"""
        section = self.section_4a(self.inputs())
        self.assertIn("本需求没有 `SR/design.md`", section)
        self.assertNotIn("读不到", section)

    def test_it_names_the_topic_and_not_a_chapter(self) -> None:
        """放哪一节由作者按内容定——输入不预设位置。"""
        package = self.inputs_with_sr()
        self.assertIn("自动充值触发", package)
        self.assertIn("放哪一节按它讲的内容定", package)

    def test_only_the_system_design_section_is_given(self) -> None:
        """上游带图的只有系统设计：没有「spec 里的图」一节，也不往 spec 搬图。"""
        package = self.inputs_with_sr()
        self.assertIn("系统设计里的图（搬进 story）", package)
        self.assertNotIn("spec 里的图", package)
        self.assertNotIn("搬进 spec", package)

    def test_no_diagrams_says_so(self) -> None:
        sr = self.feature_root / "SR" / "design.md"
        sr.parent.mkdir(parents=True, exist_ok=True)
        sr.write_text("# 系统设计\n", encoding="utf-8")
        self.assertIn("SR 里现在没有图", self.inputs())


class MaterialImagesAreOneTaskEach(WorkspaceCase):
    """材料里的图是材料清单的投影：一张图一项，命令照抄能跑。"""

    def test_one_image_is_one_task(self) -> None:
        """材料里的图**一张一项**，并写明「用或写明不用」的义务。

        两跑各丢过一次图：一次主流程没画，一次三张图一张没进正文。
        单位是图片对象不是路径：同一张图在仓里有两个落点（文档内嵌位置与
        `ux-reference/` 下的语义名副本）时，按路径摆会让作者以为有两张。
        """
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "paths": ["assets/x/one.png"], "caption": "签约页"},
                {"kind": "image", "paths": ["assets/x/two.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        self.assertIn("assets/x/one.png", package)
        self.assertIn("签约页", package)
        self.assertIn("assets/x/two.png", package)
        self.assertIn("--unused", package, "用不上的那些要有写理由的去处")
        # **方法在作业书，数据与命令在成文输入**：把「怎么引、怎么登记」也抄进来，
        # 同一条规则就有两份会各自漂的写法。这里只核指路在、方法在它该在的地方。
        self.assertIn("story-write.md", package, "输入没指出方法在哪")
        guide = (DEV_EXT / "skills/story/phases/story-write.md"
                 ).read_text(encoding="utf-8")
        self.assertIn("不属于本需求的", guide, "单向规则要在作业书里")
        self.assertIn("写明为什么不用", guide)

    def test_the_other_landing_of_the_same_image_is_an_alias(self) -> None:
        """同一张图两个落点：一项任务、一条命令，另一个落点标成别名。

        按路径逐条摆的话，作者会以为有两张——于是引两次，或者为「另一张」再补一句说明。
        """
        for rel in ("ux-reference/签约页.png", "assets/doc/img3.png"):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa", "caption": "签约页",
                 "paths": ["assets/doc/img3.png", "ux-reference/签约页.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        cmds = [l for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertEqual(1, len(cmds), f"一张图该只有一条命令，实际 {len(cmds)} 条")
        self.assertIn("同一张图的其它落点", package)
        self.assertIn("是同一张，只引一次", package)

    def test_two_different_images_are_not_merged(self) -> None:
        for rel in ("assets/x/a.png", "assets/x/b.png"):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(rel.encode())
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa", "paths": ["assets/x/a.png"]},
                {"kind": "image", "sha256": "sha256:bb", "paths": ["assets/x/b.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        cmds = [l for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertEqual(2, len(cmds), "两张不同的图被并成一项了")

    def test_the_representative_path_is_one_that_actually_reads(self) -> None:
        """登记里的路径可能指向已经不在的文件——拿它渲染出来的引用串与命令都是坏的。"""
        img = self.feature_root / "ux-reference/签约页.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa",
                 "paths": ["assets/doc/没有了.png", "ux-reference/签约页.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        cmd = next(l for l in package.split("\n")
                   if l.strip().startswith("python ") and "--caption-image" in l)
        self.assertIn("签约页.png", cmd, "命令指向了读不到的那个落点")

    def put_manifest(self, payload) -> None:
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            payload if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def image_command_lines(self, package: str) -> list[str]:
        """只取命令行本身——与 `image_commands`（连条件一起取）不是同一件事。"""
        return [l for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]

    def test_a_shape_that_is_not_the_current_contract_is_a_gap(self) -> None:
        """**形状不对不是「没有图」**：静默按零张渲染，作者会以为这一轮不涉及图。

        退旧兼容不等于静默漏掉旧形状——读到旧的 `items`/`path` 要说出来。
        """
        for name, payload in (
            ("空对象", {}),
            ("materials 不是数组", {"materials": "invalid"}),
            ("旧的 items/path", {"items": [{"kind": "image", "path": "assets/x/a.png"}]}),
            ("坏 JSON", "{ 坏了"),
        ):
            with self.subTest(shape=name):
                self.put_manifest(payload)
                package = self.inputs()
                self.assertNotIn("材料清单里现在没有图片", package, "坏形状被当成零图")
                self.assertIn("story_flow.py round", package, "没给修法")
                self.assertEqual([], self.image_command_lines(package),
                                 "形状不对却给了可执行的命令")

    def test_a_legal_empty_manifest_really_means_no_images(self) -> None:
        """合法的空清单与非图片材料：这时才是「没有图」。"""
        self.put_manifest({"materials": [
            {"kind": "doc", "sha256": "sha256:aa", "paths": ["RR/prd.md"]}]})
        self.assertIn("材料清单里现在没有图片", self.inputs())

    def test_a_bad_paths_shape_is_a_gap(self) -> None:
        for name, paths in (("不是数组", "assets/x/a.png"), ("空数组", []),
                            ("空串", [""]), ("不是字符串", [12])):
            with self.subTest(paths=name):
                self.put_manifest({"materials": [{"kind": "image", "paths": paths}]})
                package = self.inputs()
                self.assertIn("`paths` 形状不对", package)
                self.assertEqual([], self.image_command_lines(package))

    def test_an_unreadable_representative_falls_back_to_a_readable_alias(self) -> None:
        """代表路径缺了、别名读得到：用读得到的那个，另一个仍列成别名。"""
        img = self.feature_root / "ux-reference/签约页.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"PNG")
        self.put_manifest({"materials": [{"kind": "image", "caption": "签约页",
                                          "paths": ["assets/doc/没有了.png",
                                                    "ux-reference/签约页.png"]}]})
        package = self.inputs()
        cmds = self.image_command_lines(package)
        self.assertEqual(1, len(cmds))
        self.assertIn("签约页.png", cmds[0])
        self.assertIn("同一张图的其它落点", package)

    def test_a_directory_is_not_a_readable_image(self) -> None:
        """`existsSync` 为真不等于它能当一张图：指到目录的命令照抄必错。"""
        (self.feature_root / "assets" / "x").mkdir(parents=True, exist_ok=True)
        self.put_manifest({"materials": [{"kind": "image", "paths": ["assets/x"]}]})
        package = self.inputs()
        self.assertIn("一个都读不到", package)
        self.assertEqual([], self.image_command_lines(package), "给了指到目录的命令")

    def test_a_broken_manifest_is_not_no_images(self) -> None:
        """读不出来不是「没有图」：静默按零张渲染，作者会以为这一轮不涉及图。"""
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            "{ 坏了", encoding="utf-8")
        package = self.inputs()
        self.assertIn("读不出材料清单", package)
        self.assertNotIn("材料清单里现在没有图片", package)

    #: 图名带空格是常事——导入从文档里抽出来的图常常沿用原文里的名字。
    SPACED = "assets/x/page one.png"

    def seed_two_images(self) -> None:
        """盘上放两张图并登记：一张要用、一张已登记不用（名字带空格）。"""
        for rel in ("assets/x/one.png", self.SPACED):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "paths": [self.SPACED], "caption": "签约页"},
                {"kind": "image", "paths": ["assets/x/one.png"], "unused": "旧版对照稿"},
            ]}, ensure_ascii=False), encoding="utf-8")

    def test_every_image_gets_a_command_that_runs_as_written(self) -> None:
        """展示的引用串相对 `AR/story.md`，命令的路径相对工程根——两个基准不一样。

        写成「上面那一行的路径」的话，作者照抄必错，又要回头去翻脚本找基准。
        """
        self.seed_two_images()
        package = self.inputs()
        cmds = [l.strip() for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertEqual(2, len(cmds), f"每张图各要一条可跑的命令，实际 {len(cmds)} 条")
        for line in cmds:
            arg = shlex.split(line)[shlex.split(line).index("--caption-image") + 1]
            self.assertTrue(arg.startswith("doc/features/"),
                            f"命令的路径不是相对工程根：{arg}")
            self.assertTrue((self.root / arg).exists(), f"命令指到一个不存在的文件：{arg}")

    def test_the_command_in_the_fence_runs_as_written(self) -> None:
        """把围栏里那条命令**原样交给 shell**，认它真的落了盘。

        只核路径与文件存在的话，行尾多一个反斜杠这种事看不见：shell 把它当字面参数，
        续行接不上，作者复制过去就报 `unrecognized arguments`。
        """
        self.seed_two_images()
        package = self.inputs()
        cmds = [l.strip() for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertTrue(cmds, "没有渲染出可跑的取舍命令")
        line = next(c for c in cmds if "--unused" in c).replace(
            '"<为什么它不属于本需求>"', '"属别的需求的页面"')
        self.assertIn("page one.png", line, "跑的应当是名字带空格的那张")
        proc = run_in_shell(line, cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)
        self.assertIn('"ok":true', out.replace(" ", ""), out[:400])
        self.assertNotIn("\\", line, "命令里还有续行的反斜杠——shell 会把它当字面参数")


    def refresh_manifest(self) -> None:
        """用机制自己那份算法重算材料清单——手写的 materials.json 测不到取舍的写入。"""
        core = self.root / "doc/extensions/skills/story/scripts/core"
        proc = run(sys.executable, "-c",
                   "import pathlib, sys;"
                   f"sys.path.insert(0, {json.dumps(core.as_posix())});"
                   "from materials import registry;"
                   f"registry.refresh(pathlib.Path({json.dumps(self.feature_root.as_posix())}))",
                   cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def register_unused(self, rel: str, reason: str) -> None:
        """按真脚本登记「本需求不用这张图」——状态由它写，测试不手改台账。"""
        proc = run(sys.executable,
                   "doc/extensions/skills/story/scripts/core/import_sources.py",
                   "--feature", FEATURE, "--caption-image",
                   f"doc/features/{FEATURE}/{rel}", "--unused", reason, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def image_commands(self, package: str) -> list[tuple[str, str, str]]:
        """逐条取出图片命令与**紧贴它上面**那句条件。

        贴在一起才管得住照抄：条件写在段首、命令在十行之外的话，模型读到的最后一句
        是「跑这条」。
        """
        lines = package.split("\n")
        out: list[tuple[str, str, str]] = []
        for i, line in enumerate(lines):
            cmd = line.strip()
            if not cmd.startswith("python ") or "--caption-image" not in cmd:
                continue
            lead = next(l.strip() for l in reversed(lines[:i])
                        if l.strip() and not l.strip().startswith("```"))
            out.append(("--used" if " --used" in cmd else "--unused", cmd, lead))
        return out

    def test_each_image_command_says_when_it_applies(self) -> None:
        """两条命令写的是相反的状态，所以条件要贴着命令，且不能要求逐张都跑。

        `--unused` 把「本需求不用它」写进登记，`--used` 把这条登记撤掉。输入里说
        「每张图下面那条命令原样跑」时，照做一遍就把还要用的图登记成不用、把已经有
        依据不用的图恢复引用——两个方向都是拿作者没做过的决定去写状态。
        """
        for rel in ("assets/x/one.png", self.SPACED):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(rel.encode())          # 内容不同：两张图两个 sha
        self.register_unused("assets/x/one.png", "旧版对照稿")
        self.refresh_manifest()

        package = self.inputs()
        self.assertNotIn("原样跑", package, "两条命令写的状态相反，不能要求逐张跑")
        cmds = self.image_commands(package)
        self.assertEqual(2, len(cmds), f"每张图各一条命令，实际 {len(cmds)} 条")
        used = [c for c in cmds if c[0] == "--used"]
        unused = [c for c in cmds if c[0] == "--unused"]
        self.assertEqual(1, len(used), "已登记不用的那张要给撤销命令")
        self.assertIn("one.png", used[0][1])
        self.assertIn("要引用它时", used[0][2], used[0][2])
        self.assertEqual(1, len(unused), "还没登记的那张要给登记命令")
        self.assertIn("page one.png", unused[0][1])
        self.assertIn("决定不用它时", unused[0][2], unused[0][2])
        self.assertIn("换成真的理由", unused[0][2], "带占位符的命令不能说原样跑")

    def test_the_restore_command_really_clears_the_registration(self) -> None:
        """撤销那条真的撤销——跑完之后同一张图给的是另一条命令，条件跟着翻。

        这是「不要求逐张跑」的依据：两条命令不是同一个动作的两种写法，
        它们把台账写向相反的方向。
        """
        img = self.feature_root / "assets/x/one.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"PNG-one")
        self.register_unused("assets/x/one.png", "旧版对照稿")
        self.refresh_manifest()

        restore = self.image_commands(self.inputs())
        self.assertEqual(["--used"], [c[0] for c in restore])
        proc = run_in_shell(restore[0][1], cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)

        ledger = json.loads((self.feature_root / "ux-reference" / ".captions.json")
                            .read_text(encoding="utf-8"))
        self.assertFalse([e for e in ledger.values() if e.get("unused")],
                         f"「不用」的理由没被撤掉：{ledger}")
        self.refresh_manifest()
        after = self.image_commands(self.inputs())
        self.assertEqual(["--unused"], [c[0] for c in after],
                         "撤销之后再给撤销命令，作者跑一遍就把它又标成不用")
        self.assertIn("决定不用它时", after[0][2])


class TheAcceptanceExampleIsRealShape(unittest.TestCase):
    """spec 作者页给的那条示例，形状要与消费方一致——漂移了作者照抄就红。

    `acceptance.schema.yaml` 只约束顶层 `criteria`，不定义条目字段：不给示例，
    作者只能去 grep 框架的判据与本扩展的 post_check，为的只是搞清桥放在哪一层。
    """

    def example(self) -> str:
        page = (EXT / "hooks" / "spec" / "author.md").read_text(encoding="utf-8")
        return page.split("```yaml\n", 1)[1].split("```", 1)[0]

    def test_the_bridge_sits_inside_a_criteria_item(self) -> None:
        lines = [l for l in self.example().split("\n") if l.strip()]
        item = next(i for i, l in enumerate(lines) if l.strip().startswith("- id:"))
        indent = lines[item].index("-") + 2
        for key in ("knowledge_rule", "knowledge_decision_id"):
            with self.subTest(key=key):
                at = next(i for i, l in enumerate(lines) if l.strip().startswith(key + ":"))
                self.assertGreater(at, item, f"{key} 跑到条目外面去了")
                self.assertEqual(indent, len(lines[at]) - len(lines[at].lstrip()), f"{key} 与 id 不平级")

    def test_the_framework_side_sees_a_criteria_item_with_an_id(self) -> None:
        """用框架自己那份 yaml 解析——它读 acceptance.yaml 走的就是这个包。"""
        proc = run("node", "--input-type=module", "-e",
                   "const YAML = (await import('yaml')).default;"
                   f"process.stdout.write(JSON.stringify(YAML.parse({json.dumps(self.example())})));",
                   cwd=REPO_ROOT / "demo" / "framework" / "harness")
        self.assertEqual(0, proc.returncode, proc.stderr)
        item = json.loads(proc.stdout)["criteria"][0]
        self.assertTrue(item.get("id"))
        self.assertEqual(str, type(item.get("knowledge_rule")), "一条 criteria 一个编号")
        self.assertTrue(item.get("knowledge_decision_id"))


class StatusAnswersWhereYouAre(WorkspaceCase):
    """位置与文件形状由 `status` 回答，一处真源。"""

    def status(self) -> dict:
        proc = run(sys.executable, "doc/extensions/skills/story/scripts/core/story_flow.py",
                   "status", "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def write_contract(self, status: str) -> None:
        """一份走到某个状态的契约。

        **材料指纹要带上当下的那个**：不带的话「材料变了」先于关卡成立，
        `status` 会先让人去重跑 `round`——那是对的行为，但不是这几条要问的事。
        """
        proc = run(sys.executable, str(FLOW_SCRIPT), "round",
                   "--feature", FEATURE, "--project-root", str(self.root), cwd=self.root)
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        data["rounds"][-1]["gates"] = []
        # 收口意味着已关联设计对象、登记了冻结输入：用产品的冻结模块补成真实状态，之后的位置要读原生蓝图
        ensure_framework(self.root)
        data = design_kit.hand_over_state(self.root, FEATURE, data, with_blueprint=status == "story_written")
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if status == "story_written":
            # 已登记的契约带此刻的成文依据（缺了是契约不完整，status 报错）
            data["story_basis"] = design_kit.registered_basis(self.root, FEATURE)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_after_the_input_is_registered_it_waits_for_the_blueprint(self) -> None:
        """输入登记了、蓝图还没建：派生状态是等设计，下一步指向原生 component-design 与登记的那份输入。"""
        self.write_contract("complete")
        out = self.status()
        self.assertEqual(("waiting_for_design", "design_blueprint"), (out["state"], out["next"]))
        self.assertIn("component-design", out["action"])
        self.assertIn(out["input"]["snapshot_ref"], out["action"])

    def test_after_registration_it_points_at_review_and_delivery(self) -> None:
        """登记那一步已经渲染并核过 review；接下来是独立审查、交付门与一次交付选择，规则所在指向 phase 文档。"""
        self.write_contract("story_written")
        action = self.status()["action"]
        for step in ("独立审查", "--deliver", "交付选择", "phases/design.md"):
            self.assertIn(step, action)
        for gone in ("harness", "verifier", "check-receipt", "`story-build build` 渲染", "回填"):
            self.assertNotIn(gone, action)

    def test_a_gate_step_shows_the_shape_of_the_file_to_write(self) -> None:
        """S1–S4 的侧车形状：二跑为弄清它切片读了本脚本六次。"""
        self.write_contract("in_progress")
        payload = self.status()
        self.assertIn("sidecar", payload, "关卡这一步没给出要写的文件形状")
        shape = json.dumps(payload["sidecar"], ensure_ascii=False)
        self.assertIn(".material-gaps.json", shape)
        self.assertIn("missing", shape, "缺口文件的形状没给出来")


class ChapterFileCarriesOnlyBody(WorkspaceCase):
    """章文件带了本章标题时命令自己剥掉——两跑都为标题重复重建过骨架。"""

    def build(self, *args: str) -> subprocess.CompletedProcess:
        return run("node", "doc/extensions/skills/story/scripts/core/story-build.mjs",
                   *args, "--feature", FEATURE, cwd=self.root)

    def setUp(self) -> None:
        super().setUp()
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.first = self.contract["chapters"][0]["title"]
        # skeleton 起手预检需要收口态的流程契约与材料基准（08 §2.1）
        ensure_flow_state(self.root, FEATURE,
                          self.feature_root / "AR" / "story-src", DRAFT_TEXT)
        (self.feature_root / "AR" / "story-src" / "decisions.json").write_text(
            '{"decisions": [], "no_pending": "夹具：本单无待决"}', encoding="utf-8")
        # 章是照写作设计写的：这一组测章文件的标题处理，设计放一份协议齐全的最小件
        shutil.copy2(PLAN_FIXTURE, self.feature_root / "AR" / "story-src" / "story-template.md")
        self.assertEqual(0, self.build("skeleton").returncode)

    def write_chapter(self, body: str) -> str:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        proc = self.build("chapter", "--chapter", self.first, "--from", str(src))
        self.assertEqual(0, proc.returncode, proc.stderr)
        return (self.feature_root / "AR" / "story.md").read_text(encoding="utf-8")

    def test_the_chapter_title_is_not_written_twice(self) -> None:
        story = self.write_chapter(f"## {self.first}\n\n这一章的正文。\n")
        self.assertEqual(1, story.count(f"## {self.first}"), "章标题被写了两遍")
        self.assertIn("这一章的正文。", story)

    def test_a_stray_h1_is_stripped_too(self) -> None:
        """首章文件带 H1 —— H1 只属于骨架。"""
        story = self.write_chapter(f"# {FEATURE}\n\n## {self.first}\n\n这一章的正文。\n")
        self.assertEqual(1, story.count(f"# {FEATURE}"), "多出来一个 H1")
        self.assertIn("这一章的正文。", story)

    def test_inner_headings_are_left_alone(self) -> None:
        """章内的小节标题是正文，一个字不动。"""
        story = self.write_chapter("### 1.1 一个小节\n\n正文。\n")
        self.assertIn("### 1.1 一个小节", story)

    def test_a_file_with_nothing_but_the_title_is_refused(self) -> None:
        src = self.root / "chapter.md"
        src.write_text(f"## {self.first}\n", encoding="utf-8")
        proc = self.build("chapter", "--chapter", self.first, "--from", str(src))
        self.assertNotEqual(0, proc.returncode, "只有标题没有正文的章被收下了")


if __name__ == "__main__":
    unittest.main()
