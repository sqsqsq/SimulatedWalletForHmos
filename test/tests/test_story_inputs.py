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

def ensure_flow_state(root: Path, feature: str, src: Path) -> None:
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

    walk_to_complete(flow, src, "本 AR 承载自动充值签约与管理")


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

    def put(self, files: dict[str, tuple[bytes, str]]) -> None:
        """经真实导入命令把原件导成材料版本：键是收件箱里的位置，值是字节与来源类。"""
        inbox = self.feature_root / "inbox"
        for rel, (body, _) in files.items():
            (inbox / rel).parent.mkdir(parents=True, exist_ok=True)
            (inbox / rel).write_bytes(body)
        (inbox / ".classify.json").write_text(
            json.dumps({rel: cls for rel, (_, cls) in files.items()}, ensure_ascii=False), encoding="utf-8")
        proc = run(sys.executable, "doc/extensions/skills/story/scripts/core/import_sources.py",
                   "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def latest(self, key: str) -> str:
        """收件箱位置为 `key` 的那份来源最新版本的原件（相对需求目录）。"""
        index = json.loads((self.feature_root / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))
        return next(s for s in index["sources"] if s["source_id"] == f"local:{key}")["versions"][-1]["original"]["path"]

    def put_prd(self) -> None:
        """交给设计要一份正文材料：放一份产品需求。"""
        self.put({"RR/prd.md": ("# 产品需求\n\n自动充值签约。\n".encode("utf-8"), "RR")})

    def inputs(self, feature: str = FEATURE) -> str:
        """`story-build skeleton` 打印的成文输入：同一个函数、同一份来源状态，不必先把骨架的前置条件全摆齐。"""
        core = self.root / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story"
        proc = run("node", "--input-type=module", "-e",
                   f"const c = await import({as_url(core / 'context.mjs')});"
                   f"const i = await import({as_url(core / 'story-inputs.mjs')});"
                   f"const ctx = c.createContext({{ feature: {json.dumps(feature)},"
                   f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                   "process.stdout.write(i.storyInputs(ctx).join('\\n'));",
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
    """本次采用的系统设计里的图逐张给身份、主题、原件位置与原图，登记写法照抄；不指定放哪一节。

    设计开始之后来源是蓝图需求条目采用的那一版：系统设计之后取得了新版本、加了图，不改变已采用的来源。
    """

    SR = ("# 系统设计\n\n## 5. 业务流程\n\n### 5.2 自动充值触发\n\n"
          "```mermaid\ngraph TD\nC[余额上报] --> D[判定]\n```\n")

    def design_adopts(self) -> None:
        """设计开始：放好同根准入蓝图，需求条目采用各来源此刻最新的版本。"""
        ensure_framework(self.root)
        design_kit.install_blueprint(self.root, FEATURE, design_kit.ACCESS)

    @staticmethod
    def section_4b(package: str) -> str:
        return package.split("## 4b.", 1)[1].split("\n## ", 1)[0]

    def put_sr(self, text: str) -> str:
        self.put({"SR/design.md": (text.encode("utf-8"), "SR")})
        return self.latest("SR/design.md")

    def test_each_diagram_comes_with_its_identity_position_and_content(self) -> None:
        self.put_sr(self.SR)
        section = self.section_4b(self.inputs())
        self.assertIn("**SR §5.2 #1**（", section, "没给图身份")
        self.assertIn("自动充值触发", section, "没给图讲的主题")
        self.assertRegex(section, r"第 \d+–\d+ 行", "没给图在原件里的行范围")
        self.assertIn("C[余额上报]", section, "原图内容没送到")
        self.assertIn("要标承接位置时写 `- 承接上游图：SR §5.2 #1`", section, "没给照抄的登记写法")
        self.assertNotIn("%% 图源", section, "退出的围栏标记又出现了")

    def test_the_adopted_version_is_the_source(self) -> None:
        """设计开始之后系统设计取得了新版本、加了图：照设计采用的那一版列。"""
        first = self.put_sr(self.SR)
        self.design_adopts()
        second = self.put_sr(self.SR + "\n### 5.3 新加的\n\n```mermaid\ngraph TD\nX --> Y\n```\n")
        self.assertNotEqual(first, second, "新内容没出新版本")
        self.assertRegex(second, r"^\.backups/local/inbox/SR/design\.[0-9a-f]{16}\.md$")
        section = self.section_4b(self.inputs())
        self.assertIn("SR §5.2 #1", section)
        self.assertNotIn("SR §5.3 #1", section, "没采用的新版本被当成了已采用的来源")

    def test_a_missing_system_design_is_named(self) -> None:
        self.assertIn("材料索引里没有系统设计来源的阅读稿", self.section_4b(self.inputs()))

    def test_no_diagram_is_said_plainly(self) -> None:
        self.put_sr("# 系统设计\n\n只有文字。\n")
        self.assertIn("里现在没有图", self.section_4b(self.inputs()))

class TheDesignReferenceAndJudgementsReachTheAuthor(WorkspaceCase):
    """同根蓝图在：起手输入给出设计参考（原生评审投影）的位置与蓝图里已定的每条知识判断，作者不必自己去翻。"""

    def test_the_projection_and_every_judgement_are_listed(self) -> None:
        self.put_prd()
        ensure_framework(self.root)
        design_kit.install_blueprint(self.root, FEATURE, design_kit.ACCESS)
        package = self.inputs()
        section = package.split("## 4d.", 1)[1]
        self.assertIn(f"`doc/features/{FEATURE}/blueprint/component-blueprint.review.md`", section)
        constraints = [x for x in design_kit.active_constraints(self.root, design_kit.ACCESS) if x["kind"] == "constraints"]
        self.assertTrue(constraints, "夹具变了：要有激活规约")
        for c in constraints:
            self.assertIn(f"`doc/extensions/{c['file']}`（整域）→ not_applicable", section, c["file"])

    def test_without_a_blueprint_nothing_is_invented(self) -> None:
        self.put_prd()
        self.assertNotIn("## 4d.", self.inputs())


class MaterialImagesAreOneTaskEach(WorkspaceCase):
    """材料里的图是材料清单的投影：一张图一项，命令照抄能跑。"""

    def test_one_image_is_one_task(self) -> None:
        """材料里的图**一张一项**，并写明「用或写明不用」的义务。

        两跑各丢过一次图：一次主流程没画，一次三张图一张没进正文。
        单位是图片对象不是路径：同一张图在仓里有两个落点（两份材料版本里各有一份）时，
        按路径摆会让作者以为有两张。
        """
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "paths": ["sources/x-v1/images/one.png"], "caption": "签约页"},
                {"kind": "image", "paths": ["sources/x-v1/images/two.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        self.assertIn("sources/x-v1/images/one.png", package)
        self.assertIn("签约页", package)
        self.assertIn("sources/x-v1/images/two.png", package)
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
        for rel in ("sources/签约页-v1/签约页.png", "sources/需求说明-v1/images/img3.png"):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa", "caption": "签约页",
                 "paths": ["sources/需求说明-v1/images/img3.png", "sources/签约页-v1/签约页.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        cmds = [l for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertEqual(1, len(cmds), f"一张图该只有一条命令，实际 {len(cmds)} 条")
        self.assertIn("同一张图的其它落点", package)
        self.assertIn("是同一张，只引一次", package)

    def test_two_different_images_are_not_merged(self) -> None:
        for rel in ("sources/x-v1/images/a.png", "sources/x-v1/images/b.png"):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(rel.encode())
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa", "paths": ["sources/x-v1/images/a.png"]},
                {"kind": "image", "sha256": "sha256:bb", "paths": ["sources/x-v1/images/b.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.inputs()
        cmds = [l for l in package.split("\n")
                if l.strip().startswith("python ") and "--caption-image" in l]
        self.assertEqual(2, len(cmds), "两张不同的图被并成一项了")

    def test_the_representative_path_is_one_that_actually_reads(self) -> None:
        """登记里的路径可能指向已经不在的文件——拿它渲染出来的引用串与命令都是坏的。"""
        img = self.feature_root / "sources/签约页-v1/签约页.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"materials": [
                {"kind": "image", "sha256": "sha256:aa",
                 "paths": ["sources/需求说明-v1/images/没有了.png", "sources/签约页-v1/签约页.png"]},
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
            ("旧的 items/path", {"items": [{"kind": "image", "path": "sources/x-v1/images/a.png"}]}),
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
            {"kind": "doc", "sha256": "sha256:aa", "paths": ["sources/prd-v1/prd.md"]}]})
        self.assertIn("材料清单里现在没有图片", self.inputs())

    def test_a_bad_paths_shape_is_a_gap(self) -> None:
        for name, paths in (("不是数组", "sources/x-v1/images/a.png"), ("空数组", []),
                            ("空串", [""]), ("不是字符串", [12])):
            with self.subTest(paths=name):
                self.put_manifest({"materials": [{"kind": "image", "paths": paths}]})
                package = self.inputs()
                self.assertIn("`paths` 形状不对", package)
                self.assertEqual([], self.image_command_lines(package))

    def test_an_unreadable_representative_falls_back_to_a_readable_alias(self) -> None:
        """代表路径缺了、别名读得到：用读得到的那个，另一个仍列成别名。"""
        img = self.feature_root / "sources/签约页-v1/签约页.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"PNG")
        self.put_manifest({"materials": [{"kind": "image", "caption": "签约页",
                                          "paths": ["sources/需求说明-v1/images/没有了.png",
                                                    "sources/签约页-v1/签约页.png"]}]})
        package = self.inputs()
        cmds = self.image_command_lines(package)
        self.assertEqual(1, len(cmds))
        self.assertIn("签约页.png", cmds[0])
        self.assertIn("同一张图的其它落点", package)

    def test_a_directory_is_not_a_readable_image(self) -> None:
        """`existsSync` 为真不等于它能当一张图：指到目录的命令照抄必错。"""
        (self.feature_root / "assets" / "x").mkdir(parents=True, exist_ok=True)
        self.put_manifest({"materials": [{"kind": "image", "paths": ["sources/x-v1/images"]}]})
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

    def put_two_images(self) -> tuple[str, str]:
        """导入两张内容不同的图，返回它们的原件位置；第二张名字带空格——原文里的图名常常带空格。"""
        self.put({"one.png": (b"PNG-one", "UX"), "page one.png": (b"PNG-two", "UX")})
        return self.latest("one.png"), self.latest("page one.png")

    def seed_two_images(self) -> None:
        """两张图：带空格的那张写了说明、还要用，另一张已登记不用。"""
        one, spaced = self.put_two_images()
        proc = run(sys.executable, "doc/extensions/skills/story/scripts/core/import_sources.py",
                   "--feature", FEATURE, "--caption-image", f"doc/features/{FEATURE}/{spaced}",
                   "--caption", "签约页", cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.register_unused(one, "旧版对照稿")

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
        self.assertIn("/page one.", line, "跑的应当是名字带空格的那张")
        proc = run_in_shell(line, cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)
        self.assertIn('"ok":true', out.replace(" ", ""), out[:400])
        self.assertNotIn("\\", line, "命令里还有续行的反斜杠——shell 会把它当字面参数")


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
        one, _ = self.put_two_images()
        self.register_unused(one, "旧版对照稿")

        package = self.inputs()
        self.assertNotIn("原样跑", package, "两条命令写的状态相反，不能要求逐张跑")
        cmds = self.image_commands(package)
        self.assertEqual(2, len(cmds), f"每张图各一条命令，实际 {len(cmds)} 条")
        used = [c for c in cmds if c[0] == "--used"]
        unused = [c for c in cmds if c[0] == "--unused"]
        self.assertEqual(1, len(used), "已登记不用的那张要给撤销命令")
        self.assertIn("/one.", used[0][1])
        self.assertIn("要引用它时", used[0][2], used[0][2])
        self.assertEqual(1, len(unused), "还没登记的那张要给登记命令")
        self.assertIn("/page one.", unused[0][1])
        self.assertIn("决定不用它时", unused[0][2], unused[0][2])
        self.assertIn("换成真的理由", unused[0][2], "带占位符的命令不能说原样跑")

    def test_the_restore_command_really_clears_the_registration(self) -> None:
        """撤销那条真的撤销——跑完之后同一张图给的是另一条命令，条件跟着翻。

        这是「不要求逐张跑」的依据：两条命令不是同一个动作的两种写法，
        它们把台账写向相反的方向。
        """
        self.put({"one.png": (b"PNG-one", "UX")})
        self.register_unused(self.latest("one.png"), "旧版对照稿")

        restore = self.image_commands(self.inputs())
        self.assertEqual(["--used"], [c[0] for c in restore])
        proc = run_in_shell(restore[0][1], cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)

        notes = json.loads((self.feature_root / "AR" / "story-src" / "materials.json")
                           .read_text(encoding="utf-8"))["notes"]
        self.assertFalse([e for e in notes.values() if e.get("unused")],
                         f"「不用」的理由没被撤掉：{notes}")
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
        for key in ("knowledge_refs",):
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
        refs = item.get("knowledge_refs")
        self.assertEqual(list, type(refs), "knowledge_refs 是条目引用列表")
        self.assertTrue(refs and all("#" in r for r in refs), "条目引用写 <知识文件>#<编号>")


class StatusAnswersWhereYouAre(WorkspaceCase):
    """位置与文件形状由 `status` 回答，一处真源。"""

    def status(self) -> dict:
        proc = run(sys.executable, "doc/extensions/skills/story/scripts/core/story_flow.py",
                   "status", "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def write_contract(self, status: str, *, settled: bool = True) -> None:
        """一份走到某个状态的契约：`settled` 时本轮范围已定。

        **材料指纹要带上当下的那个**：不带的话「材料变了」先于关卡成立，
        `status` 会先让人去重跑 `round`——那是对的行为，但不是这几条要问的事。
        """
        self.put_prd()
        proc = run(sys.executable, str(FLOW_SCRIPT), "round",
                   "--feature", FEATURE, "--project-root", str(self.root), cwd=self.root)
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        at = "2026-10-30T00:00:00Z"
        data["rounds"][-1]["gates"] = [
            {"gate": "material_scope", "ask_id": "m1", "question": "材料齐了吗？",
             "options": [{"no": 1, "key": "confirm_scope", "label": "现有材料就是全部"}],
             "chosen": "confirm_scope", "no": 1, "label": "现有材料就是全部", "reply": "1",
             "outcome": "accepted", "by": "human", "at": at},
            {"gate": "scope_decision", "ask_id": "s1", "question": "这个需求承载哪些？",
             "options": [{"no": 1, "key": "carry_all", "label": "按当前范围整体承载"}],
             "chosen": "carry_all", "no": 1, "label": "按当前范围整体承载", "reply": "1",
             "outcome": "accepted", "by": "human", "at": at, "context": {"scope_text": "本 AR 承载签约"}}] if settled else []
        if settled:
            data["rounds"][-1].update(positioning={"scope_text": "本 AR 承载签约", "sr_related_ars": []},
                                      scope_options=[{"key": "carry_all", "label": "按当前范围整体承载"}])
        # 范围定了之后的位置要读原生蓝图：接 Framework，成文登记了的放好同根蓝图
        ensure_framework(self.root)
        data = design_kit.hand_over_state(self.root, FEATURE, data, with_blueprint=status == "story_written")
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if settled:
            design_kit._core_modules()[0].refresh(self.feature_root)    # 答复生效时 decide 做的那一步：导出人答
        if status == "story_written":
            # 已登记的契约带此刻的成文依据（缺了是契约不完整，status 报错）
            data["story_basis"] = design_kit.registered_basis(self.root, FEATURE)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_a_settled_scope_waits_for_the_blueprint(self) -> None:
        """范围定了、蓝图还没建：派生状态是等设计，下一步指向原生 component-design 与补齐需求条目来源的命令。"""
        self.write_contract("gathering")
        out = self.status()
        self.assertEqual(("waiting_for_design", "design_blueprint"), (out["state"], out["next"]))
        self.assertIn("component-design", out["action"])
        self.assertIn("import_sources.py --scope", out["action"])

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
        self.write_contract("gathering", settled=False)
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
        self.put_prd()
        ensure_flow_state(self.root, FEATURE,
                          self.feature_root / "AR" / "story-src")
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
