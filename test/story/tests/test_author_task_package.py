"""作者动笔之前手上有什么：任务包、判断骨架、这一步的顺序与文件形状。

两轮真实实跑里，作者在 spec 这一段做的事有相当一部分不是写需求，而是**找答案**：
`knowledge-use.yaml` 有哪些字段、「无候选」写成什么、决策登记要哪几个键、
三个侧车长什么样、门禁到底判什么——为此切片读了扩展脚本 68 次。
这些答案都是确定的，也都早就在磁盘上（合同、激活清单、流程契约）。缺的是送达。

所以这一组判的是**送达**，不是判据：

  ① 任务包由真源渲染，不是又一页手写说明——改合同，任务包跟着变；
  ② 判断骨架把激活条目一条不落地摆出来，作者只填判断；
  ③ 位置与文件形状由 `status` 回答，一处真源；
  ④ 章文件带了本章标题时命令自己剥掉——两跑都为这件事重建过骨架。

不判内容质量：任务包写得好不好、作者照没照做，那是实跑与评审看的事。
"""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
CONTRACT = EXT / "skills" / "story" / "contracts" / "story-chapters.json"
FLOW_SCRIPT = EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"
FEATURE = "TP90001"
#: 协议齐全的最小写作设计：章提交要读得了设计，测章文件处理的用例起手前放它。
PLAN_FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes" / "R01-verdict-echo"
                / "good" / "doc" / "features" / "AR90001" / "AR" / "story-src" / "story-template.md")

# 任务包体量上限：作者要在动笔前一次读完它
MAX_PACKAGE_BYTES = 12 * 1024


def run_in_shell(command: str, cwd=None) -> subprocess.CompletedProcess:
    """把渲染出来的命令**原样交给本工程的命令行**跑一遍。

    引用规则由机制那一侧定（`story/drafts.mjs` 的 `shellArg`：PowerShell 的单引号
    字面量）；测试必须用同一个 shell 跑，否则测的是另一套规则——cmd.exe 不认单引号，
    路径会连着引号一起进参数。找不到 PowerShell 就退回 POSIX shell：单引号在它那里
    是同样的字面含义。
    """
    exe = shutil.which("pwsh") or shutil.which("powershell")
    args = ([exe, "-NoProfile", "-Command", command + "; exit $LASTEXITCODE"]
            if exe else ["bash", "-lc", command])
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180,
                          cwd=None if cwd is None else str(cwd))


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90, cwd=cwd)


def as_url(path: Path) -> str:
    """Windows 上动态 import 只认 file:// URL。"""
    return json.dumps(path.resolve().as_uri())


FLOW_SCRIPT = REPO_ROOT / "doc/extensions/skills/story/scripts/core/story_flow.py"
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
    def flow(*args: str) -> None:
        proc = subprocess.run(
            [sys.executable, str(FLOW_SCRIPT), *args, "--feature", feature,
             "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(root))
        assert proc.returncode == 0, f"{args}: {proc.stdout}\n{proc.stderr}"

    src.mkdir(parents=True, exist_ok=True)
    (src / "design-draft.md").write_text(draft_text, encoding="utf-8")
    flow("init")
    flow("round")
    (src / ".gate-options.json").write_text(json.dumps(
        {"gate": "material_scope", "options": [
            {"key": "supplied", "label": "a", "request": True},
            {"key": "confirm_scope", "label": "b"}]}, ensure_ascii=False),
        encoding="utf-8")
    flow("decide", "--gate", "material_scope", "--chosen", "confirm_scope",
         "--basis", "夹具：现有材料就是全部")
    (src / ".positioning.json").write_text(json.dumps({
        "scope_source": "user_stated", "scope_text": "本 AR 承载自动充值签约与管理",
        "sr_related_ars": []}, ensure_ascii=False), encoding="utf-8")
    (src / ".scope-options.json").write_text(json.dumps(
        [{"key": "carry_all", "label": "按当前范围整体承载", "recommended": True}],
        ensure_ascii=False), encoding="utf-8")
    flow("round")
    (src / ".gate-options.json").write_text(json.dumps(
        {"gate": "scope_decision",
         "options": [{"key": "carry_all", "label": "按当前范围整体承载"}]},
        ensure_ascii=False), encoding="utf-8")
    flow("decide", "--gate", "scope_decision", "--chosen", "carry_all",
         "--basis", "夹具：整体承载")
    flow("complete", "--from", "AR/story-src/design-draft.md")


class WorkspaceCase(unittest.TestCase):
    """每个用例一份新工作区，扩展是真的那一份。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        self.feature_root = self.root / "doc" / "features" / FEATURE
        (self.feature_root / "spec").mkdir(parents=True)
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)

    def task_package(self, feature: str = FEATURE) -> str:
        proc = run("node", "doc/extensions/hooks/spec/author.mjs", "--feature", feature,
                   cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def spec_check(self) -> str:
        """跑真的 spec post_check——判据怎么读这份文件，这里就怎么读。"""
        hook = self.root / "doc" / "extensions" / "hooks" / "spec" / "post_check.mjs"
        proc = run("node", "--input-type=module", "-e",
                   f"const hook = (await import({as_url(hook)})).default;"
                   f"const out = await hook({{ phase: 'spec', feature: {json.dumps(FEATURE)},"
                   f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                   "process.stdout.write(JSON.stringify(out));",
                   cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def parse_like_the_framework(self, target: Path) -> dict:
        """用框架自己那份 yaml 解析——它读 acceptance.yaml 走的就是这个包。"""
        proc = run("node", "--input-type=module", "-e",
                   "const YAML = (await import('yaml')).default;"
                   "const fs = await import('node:fs');"
                   f"const doc = YAML.parse(fs.readFileSync({json.dumps(target.as_posix())}, 'utf-8'));"
                   "process.stdout.write(JSON.stringify(doc));",
                   cwd=REPO_ROOT / "framework" / "harness")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}")


class TheAuthorDoesNotHaveToLookThingsUp(WorkspaceCase):
    """作者动笔前该拿到的两样：验收落在哪、禁用词在哪不算。

    这两条都是实跑里逼着作者去翻源码的：路径写错一个层级，他去框架里找真相；
    豁免只写在脚本注释里，他去读判定脚本。
    """

    def test_the_acceptance_path_is_the_one_the_framework_reads(self) -> None:
        """框架读的是需求根目录那一份，不是 `spec/` 下面。"""
        package = self.task_package()
        self.assertIn(f"doc/features/{FEATURE}/acceptance.yaml", package)
        self.assertNotIn("spec/acceptance.yaml", package)

    def test_no_delivery_surface_still_says_spec_acceptance(self) -> None:
        """四处消费者一起改——留一处，作者照样会撞上说法不一。"""
        import subprocess
        proc = subprocess.run(
            ["git", "grep", "-l", "--fixed-strings", "spec/acceptance.yaml",
             "--", "doc/extensions"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual("", proc.stdout.strip(), f"还有地方写着旧路径：{proc.stdout}")

    def test_the_banned_words_come_with_where_they_do_not_count(self) -> None:
        """词表一直在；缺的是作用域——哪几章、哪几类议题、同词的另一种语义。"""
        package = self.task_package()
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        chapters = [c["title"] for c in contract["chapters"] if c.get("banned_terms_exempt")]
        cats = [c["key"] for c in contract.get("decision_categories", [])
                if c.get("banned_terms_exempt")]
        self.assertIn("在哪不算", package)
        for name in chapters:
            with self.subTest(chapter=name):
                self.assertIn(name, package.split("在哪不算", 1)[1])
        for key in cats:
            with self.subTest(category=key):
                self.assertIn(key, package.split("在哪不算", 1)[1])
        self.assertTrue(chapters and cats, "合同里一个豁免都没有，这条夹具没有对象")


class SpecDiagramsReachTheAuthor(WorkspaceCase):
    """spec 里的图逐张给身份、主题与**原件坐标**，不指定放哪一章。

    不复制围栏原文：副本一旦与原件不同步，作者改的是副本；任务包也因此长到一次读不完。
    """

    SPEC = ("# 甲需求\n\n## 5. 业务流程\n\n### 5.2 自动充值触发\n\n"
            "```mermaid\ngraph TD\nC[余额上报] --> D[判定]\n```\n")

    def package_with_spec(self) -> str:
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text(self.SPEC, encoding="utf-8")
        return self.task_package()

    def test_each_diagram_comes_with_coordinates_not_a_copy(self) -> None:
        package = self.package_with_spec()
        self.assertIn("spec 里的图", package)
        self.assertIn("spec §5.2 #1", package, "没给身份，作者不知道标记写什么")
        self.assertIn("`%% 图源 spec §5.2 #1`", package, "没给标记的写法，搬过去就核不到")
        self.assertIn("spec/spec.md", package, "没给原件路径")
        self.assertRegex(package, r"第 \d+–\d+ 行", "没给围栏在原件里的行范围")
        self.assertNotIn("C[余额上报]", package, "把原件围栏复制进任务包了——副本会与原件不同步")

    def test_a_spec_not_yet_written_is_not_reported_as_lost(self) -> None:
        """Spec 还没写成时它的图给不出来——那是时点，不是丢件：说清什么时候给。

        说成「读不到，先找回来」的话，作者会在 Spec 阶段一开头去找一份本来就还不存在的文件。
        """
        spec = self.feature_root / "spec" / "spec.md"
        if spec.exists():
            spec.unlink()
        section = self.task_package().split("## 4b.", 1)[1]
        self.assertIn("还没写成", section)
        self.assertIn("story-build skeleton", section, "没说清这些图什么时候给")
        self.assertNotIn("找回来", section)
        self.assertNotIn("spec 里现在没有图", section, "给不出来不等于没有图")

    def test_an_unreadable_upstream_is_a_problem_not_an_empty_section(self) -> None:
        """远程单的系统设计该有却读不到：要报出来，静默给一节空的，作者会以为上游没画过图。"""
        (self.feature_root / "AR" / "detail.json").write_text(
            json.dumps({"reqNo": FEATURE}, ensure_ascii=False), encoding="utf-8")
        section = self.task_package().split("## 4a.", 1)[1].split("## 4b.", 1)[0]
        self.assertIn("读不到 `SR/design.md`", section)
        self.assertIn("找回来", section)

    def test_a_local_ticket_without_a_system_design_is_not_a_loss(self) -> None:
        """本地单没有需求系统给的系统设计是正常的：照合同说「本需求没有」，不报丢件。"""
        section = self.task_package().split("## 4a.", 1)[1].split("## 4b.", 1)[0]
        self.assertIn("本需求没有 `SR/design.md`", section)
        self.assertNotIn("读不到", section)

    def test_it_names_the_topic_and_not_a_chapter(self) -> None:
        """放哪一节由作者按内容定——任务包不预设位置。"""
        package = self.package_with_spec()
        self.assertIn("自动充值触发", package)
        self.assertIn("放哪一节按它讲的内容定", package)

    def test_both_upstreams_get_their_own_section(self) -> None:
        """上游两份各一节，下游都是 story——spec 的内容归框架管，扩展不往那边搬图。"""
        package = self.package_with_spec()
        self.assertIn("系统设计里的图（搬进 story）", package)
        self.assertIn("spec 里的图（搬进 story）", package)
        self.assertNotIn("搬进 spec", package)

    def test_no_diagrams_says_so(self) -> None:
        (self.feature_root / "spec").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "spec" / "spec.md").write_text("# 甲需求\n", encoding="utf-8")
        self.assertIn("spec 里现在没有图", self.task_package())


class TaskPackageIsRendered(WorkspaceCase):
    """任务包是真源的投影，不是又一页手写说明。"""

    def test_banned_words_come_with_what_to_write_instead(self) -> None:
        """词表连改法一起送达：只说不许用，作者不知道该写什么。"""
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        package = self.task_package()
        for item in contract["language_redline"]["client_vocabulary"]:
            self.assertIn(item["term"], package)
            self.assertIn(item["hint"], package)

    def test_active_constraints_are_counted_from_the_manifest(self) -> None:
        """条目数从激活清单来：作者要知道这一轮要判几条，不是「若干条」。"""
        package = self.task_package()
        self.assertRegex(package, r"激活 \*\*\d+ 条\*\*约束")

    def test_it_names_the_line_to_register_in_key_inputs_read(self) -> None:
        """D12：登记义务直接给出那一行——二跑为这条红过一轮。"""
        self.assertIn("doc/extensions/hooks/spec/author.md", self.task_package())

    def test_it_fits_in_one_read(self) -> None:
        size = len(self.task_package().encode("utf-8"))
        self.assertLessEqual(size, MAX_PACKAGE_BYTES,
                             f"任务包 {size} 字节，超过一次读完的上限——数据性内容要回真源")

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
        package = self.task_package()
        self.assertIn("assets/x/one.png", package)
        self.assertIn("签约页", package)
        self.assertIn("assets/x/two.png", package)
        self.assertIn("--unused", package, "用不上的那些要有写理由的去处")
        # **方法在作业书，数据与命令在任务包**：把「怎么引、怎么登记」也抄进任务包，
        # 同一条规则就有两份会各自漂的写法。这里只核指路在、方法在它该在的地方。
        self.assertIn("story-write.md", package, "任务包没指出方法在哪")
        guide = (REPO_ROOT / "doc/extensions/skills/story/phases/story-write.md"
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
        package = self.task_package()
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
        package = self.task_package()
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
        package = self.task_package()
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
                package = self.task_package()
                self.assertNotIn("材料清单里现在没有图片", package, "坏形状被当成零图")
                self.assertIn("story_flow.py round", package, "没给修法")
                self.assertEqual([], self.image_command_lines(package),
                                 "形状不对却给了可执行的命令")

    def test_a_legal_empty_manifest_really_means_no_images(self) -> None:
        """合法的空清单与非图片材料：这时才是「没有图」。"""
        self.put_manifest({"materials": [
            {"kind": "doc", "sha256": "sha256:aa", "paths": ["RR/prd.md"]}]})
        self.assertIn("材料清单里现在没有图片", self.task_package())

    def test_a_bad_paths_shape_is_a_gap(self) -> None:
        for name, paths in (("不是数组", "assets/x/a.png"), ("空数组", []),
                            ("空串", [""]), ("不是字符串", [12])):
            with self.subTest(paths=name):
                self.put_manifest({"materials": [{"kind": "image", "paths": paths}]})
                package = self.task_package()
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
        package = self.task_package()
        cmds = self.image_command_lines(package)
        self.assertEqual(1, len(cmds))
        self.assertIn("签约页.png", cmds[0])
        self.assertIn("同一张图的其它落点", package)

    def test_a_directory_is_not_a_readable_image(self) -> None:
        """`existsSync` 为真不等于它能当一张图：指到目录的命令照抄必错。"""
        (self.feature_root / "assets" / "x").mkdir(parents=True, exist_ok=True)
        self.put_manifest({"materials": [{"kind": "image", "paths": ["assets/x"]}]})
        package = self.task_package()
        self.assertIn("一个都读不到", package)
        self.assertEqual([], self.image_command_lines(package), "给了指到目录的命令")

    def test_a_broken_manifest_is_not_no_images(self) -> None:
        """读不出来不是「没有图」：静默按零张渲染，作者会以为这一轮不涉及图。"""
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            "{ 坏了", encoding="utf-8")
        package = self.task_package()
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
        package = self.task_package()
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
        package = self.task_package()
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

        `--unused` 把「本需求不用它」写进登记，`--used` 把这条登记撤掉。任务包说
        「每张图下面那条命令原样跑」时，照做一遍就把还要用的图登记成不用、把已经有
        依据不用的图恢复引用——两个方向都是拿作者没做过的决定去写状态。
        """
        for rel in ("assets/x/one.png", self.SPACED):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(rel.encode())          # 内容不同：两张图两个 sha
        self.register_unused("assets/x/one.png", "旧版对照稿")
        self.refresh_manifest()

        package = self.task_package()
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

        restore = self.image_commands(self.task_package())
        self.assertEqual(["--used"], [c[0] for c in restore])
        proc = run_in_shell(restore[0][1], cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)

        ledger = json.loads((self.feature_root / "ux-reference" / ".captions.json")
                            .read_text(encoding="utf-8"))
        self.assertFalse([e for e in ledger.values() if e.get("unused")],
                         f"「不用」的理由没被撤掉：{ledger}")
        self.refresh_manifest()
        after = self.image_commands(self.task_package())
        self.assertEqual(["--unused"], [c[0] for c in after],
                         "撤销之后再给撤销命令，作者跑一遍就把它又标成不用")
        self.assertIn("决定不用它时", after[0][2])


class TheAcceptanceExampleIsRealShape(WorkspaceCase):
    """任务包给的那条最小示例，形状要与消费方一致——漂移了作者照抄就红。

    `acceptance.schema.yaml` 只约束顶层 `criteria`，不定义条目字段：不给示例，
    作者只能去 grep 框架的判据与本扩展的 post_check，为的只是搞清
    `knowledge_rule` 放在哪一层。
    """

    def test_the_example_puts_the_rule_key_inside_a_criteria_item(self) -> None:
        package = self.task_package()
        self.assertIn("criteria:", package)
        block = package.split("一条最小的长这样", 1)[1].split("```", 2)[1]
        lines = [l for l in block.split("\n") if l.strip()]
        item = next(i for i, l in enumerate(lines) if l.strip().startswith("- id:"))
        rule = next(i for i, l in enumerate(lines) if "knowledge_rule" in l)
        self.assertGreater(rule, item, "knowledge_rule 跑到条目外面去了")
        self.assertEqual(lines[item].index("-") + 2, len(lines[rule])
                         - len(lines[rule].lstrip()),
                         "knowledge_rule 与 id 不平级")

    def example_yaml(self, rule: str = "SEC-01") -> str:
        """把任务包里那条示例取出来，占位换成真值——作者照抄写出来的就是这个。"""
        block = self.task_package().split("一条最小的长这样", 1)[1].split("```", 2)[1]
        body = block.split("\n", 1)[1] if block.startswith("yaml") else block
        return (body
                .replace("{{这条规约在本需求上要保证什么，用可观察的话写}}", "卡号在任何出口都脱敏")
                .replace("{{怎么验}}", "打开充值记录列表看卡号")
                .replace("{{看到什么算过}}", "只显示末四位")
                .replace("{{规约编号}}", rule))

    RULE = "SEC-01"

    SPEC_HEAD = """# {feature} spec

## 9. 技术契约

### 9.1 端云接口

| 名称 | 用途 |
|---|---|
| 建立签约接口 | 建立自动充值签约 |

## 10. 规约约束要求

<!-- 由 knowledge-use.yaml 生成 -->

## 11. 设计模式候选登记

<!-- 由 knowledge-use.yaml 生成 -->
"""

    def stage_a_spec_that_reaches_the_bridge(self) -> None:
        """把上下文搭到「桥接那一条真的会跑」——少一样它就提前返回，夹具就成了空跑。

        要的三样：spec.md（缺了整个 hook `skipped`）、一份对得上真实知识的判断
        （对不上时判断本身先红，投影与桥接都到不了）、§10/§11 的生成区
        （由 render 写，投影核不过同样先红）。
        """
        spec_dir = self.feature_root / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text(
            self.SPEC_HEAD.format(feature=FEATURE), encoding="utf-8")

        shared = self.root / "doc" / "extensions" / "hooks" / "shared"
        proc = run("node", "--input-type=module", "-e",
                   f"const u = await import({as_url(shared / 'knowledge-use/document.mjs')});"
                   f"process.stdout.write(u.manifestDigest({json.dumps(self.root.as_posix())}));",
                   cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)

        rows = ["schema: 1", f'manifest_digest: "{proc.stdout.strip()}"', "facts: []',".rstrip("',"),
                "constraint_domains:"]
        for prefix in ("UX", "DFX", "OBS", "RES", "COMPAT", "ENV", "DLV"):
            rows += [f"  - prefix: {prefix}", "    applicable: false",
                     f"    reason: 本需求不涉及 {prefix} 域管的那类改动"]
        rows += ["constraints:",
                 f"  - id: {self.RULE}",
                 "    applicable: true",
                 "    requirement: 卡号在充值记录与日志两个出口都按现有规则脱敏",
                 "    basis: 产品原稿 §3 写明记录列表展示脱敏卡号",
                 "    contract: 建立签约接口",
                 "patterns:",
                 "  - unit: 充值记录列表的卡号展示",
                 "    candidate: page-interaction",
                 "    signal: 单页一次读取一次渲染，没有跨步骤的状态传递"]
        (spec_dir / "knowledge-use.yaml").write_text(
            "\n".join(rows) + "\n", encoding="utf-8")

        proc = run("node", str(shared / "knowledge-use.mjs"), "render",
                   "--feature", FEATURE, "--project-root", str(self.root), cwd=self.root)
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))

    def test_the_extension_side_reads_the_rule_out_of_the_example(self) -> None:
        """把示例当成作者写出来的 acceptance.yaml，跑真的 spec post_check。

        它按 `knowledge_rule: <编号>` 找验收桥；示例的键名或层级一漂移，
        这里就报「有代码要求但 acceptance.yaml 没有对应验收条目」。
        """
        self.stage_a_spec_that_reaches_the_bridge()
        (self.feature_root / "acceptance.yaml").write_text(
            self.example_yaml(self.RULE), encoding="utf-8")
        message = self.spec_check()
        self.assertNotIn("跳过", message, f"这条检查压根没跑：{message[:400]}")
        self.assertNotIn("没有对应验收条目", message, message[:400])
        self.assertNotIn("指向了 spec 里没有要求的条目", message, message[:400])

    def test_the_bridge_check_really_runs_on_the_example(self) -> None:
        """对照：同一份上下文，把示例的编号换成 spec 里没有的那条，桥接当场报两句。

        没有这一条的话，上面那条「没有出错字样」在检查根本没执行时也是绿的。
        """
        self.stage_a_spec_that_reaches_the_bridge()
        (self.feature_root / "acceptance.yaml").write_text(
            self.example_yaml("ZZZ-99"), encoding="utf-8")
        message = self.spec_check()
        self.assertIn("没有对应验收条目", message, message[:400])
        self.assertIn(self.RULE, message)
        self.assertIn("指向了 spec 里没有要求的条目", message, message[:400])

    def test_a_criteria_without_the_field_is_plain_business_acceptance(self) -> None:
        """一条需求里绝大多数验收点与规约无关，它们不写这个字段——那不是漏写。

        为它们各报一条的话，真正缺的那几条会被淹掉。
        """
        self.stage_a_spec_that_reaches_the_bridge()
        (self.feature_root / "acceptance.yaml").write_text(
            self.example_yaml(self.RULE)
            + "  - id: AC-9\n    priority: P1\n"
              "    description: 充值记录列表按时间倒序\n    testable: true\n",
            encoding="utf-8")
        message = self.spec_check()
        self.assertNotIn("跳过", message, f"这条检查压根没跑：{message[:400]}")
        self.assertNotIn("AC-9", message, message[:400])

    def test_a_list_of_rules_in_one_criteria_is_named(self) -> None:
        """一条 criteria 写一串编号——下游按编号分派时对不到场景。

        正则扫只看「文件里出现过这个编号」，这种形态它照样判过，
        而作者会以为自己已经桥接过了。
        """
        self.stage_a_spec_that_reaches_the_bridge()
        (self.feature_root / "acceptance.yaml").write_text(
            self.example_yaml(self.RULE).replace(
                f"knowledge_rule: {self.RULE}",
                f"knowledge_rule: [{self.RULE}, ZZZ-99]"),
            encoding="utf-8")
        message = self.spec_check()
        self.assertIn("不是一个编号", message, message[:400])

    def test_a_real_acceptance_with_block_scalars_reads_through(self) -> None:
        """真实产物里有块标量（`knowledge_rule_bridge: |`）——读取器要认它。

        不认的话，桥接只能改用正则去扫，而正则分不清编号写在哪一层。
        """
        self.stage_a_spec_that_reaches_the_bridge()
        (self.feature_root / "acceptance.yaml").write_text(
            "knowledge_rule_bridge: |\n"
            "  命中规约经 knowledge_rule 桥接：一条 criteria 一个编号。\n"
            "  评审动作条目不建验收条目。\n"
            + self.example_yaml(self.RULE), encoding="utf-8")
        message = self.spec_check()
        self.assertNotIn("跳过", message, f"这条检查压根没跑：{message[:400]}")
        self.assertNotIn("读不出结构", message, message[:400])
        self.assertNotIn("没有对应验收条目", message, message[:400])

    def test_the_framework_side_sees_a_criteria_item_with_an_id(self) -> None:
        """框架侧读的是 `criteria` 数组里的对象与它的 `id`
        （`framework/harness/scripts/check-plan.ts` 的 spec→plan 约束追溯）。

        用框架自己那份 yaml 解析，示例的层级一错——`knowledge_rule` 跑到条目外、
        或 `criteria` 不是数组——这里当场报出来。
        """
        acc = self.feature_root / "acceptance.yaml"
        acc.write_text(self.example_yaml(), encoding="utf-8")
        doc = self.parse_like_the_framework(acc)
        self.assertIsInstance(doc.get("criteria"), list, "criteria 不是数组")
        item = doc["criteria"][0]
        self.assertIsInstance(item, dict, "条目不是对象")
        self.assertTrue(str(item.get("id") or "").strip(), "条目没有 id")
        self.assertIn("knowledge_rule", item, "knowledge_rule 不在条目里")


class SkeletonLeavesOnlyTheJudgement(WorkspaceCase):
    """判断骨架：结构归脚本，判断归作者。"""

    def init_use(self, feature: str = FEATURE) -> subprocess.CompletedProcess:
        return run("node", "doc/extensions/hooks/shared/knowledge-use.mjs",
                   "init", "--feature", feature, cwd=self.root)

    def test_every_active_entry_is_on_the_sheet(self) -> None:
        proc = self.init_use()
        self.assertEqual(0, proc.returncode, proc.stderr)
        body = (self.feature_root / "spec" / "knowledge-use.yaml").read_text(encoding="utf-8")
        listed = run("node", "-e", f"""
            import({as_url(self.root / 'doc/extensions/hooks/shared/knowledge.mjs')}).then(m => {{
              const k = m.activeKnowledge({json.dumps(self.root.as_posix())});
              process.stdout.write(k.entries.map(e => e.id).join(','));
            }});
        """, cwd=self.root)
        self.assertEqual(0, listed.returncode, listed.stderr)
        for entry_id in listed.stdout.strip().split(","):
            self.assertIn(f"- id: {entry_id}", body, f"骨架漏了 {entry_id}——漏一条就是「没判过」")

    def test_it_does_not_decide_for_the_author(self) -> None:
        """applicable 留空：脚本摆结构，不替作者判命中。

        只看数据行——注释里出现「applicable: false」是在讲整域不适用怎么写，那是送达不是判断。
        """
        self.init_use()
        body = (self.feature_root / "spec" / "knowledge-use.yaml").read_text(encoding="utf-8")
        for row in body.splitlines():
            data = row.split("#", 1)[0]
            self.assertNotIn("applicable: true", data)
            self.assertNotIn("applicable: false", data)

    def test_the_legal_no_candidate_literal_is_spelled_out(self) -> None:
        """二跑把它写成了 `no_candidate`——合法字面要在作者眼前。"""
        self.init_use()
        body = (self.feature_root / "spec" / "knowledge-use.yaml").read_text(encoding="utf-8")
        self.assertIn("无候选", body)

    def test_it_refuses_to_overwrite_existing_judgement(self) -> None:
        self.init_use()
        (self.feature_root / "spec" / "knowledge-use.yaml").write_text(
            "schema: 1\n# 作者已经判过了\n", encoding="utf-8")
        again = self.init_use()
        self.assertNotEqual(0, again.returncode, "骨架覆盖了已有判断")
        self.assertIn("已经在了", again.stderr)


class StatusAnswersWhereYouAre(WorkspaceCase):
    """位置与文件形状由 `status` 回答，任务包引用同一处。"""

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
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_after_the_flow_closes_it_gives_the_spec_stage_order(self) -> None:
        """两跑都先跑了 harness 再写 story，三轮 FAIL 全是「产物不齐」。"""
        self.write_contract("complete")
        action = self.status()["action"]
        self.assertIn("knowledge-use.mjs init", action)
        self.assertIn("harness", action)

    def test_it_repeats_the_authorization_for_entering_spec(self) -> None:
        """进 spec 的授权是 `/story` 启动时声明的，收口这一步要原样打出来。

        不打的话，模型在 framework 的阶段边界只能按默认策略再问一次授权——
        它没错，是「/story 即声明做到 spec 闭环」这条链没有接到 framework 认的形态上。
        """
        self.write_contract("complete")
        action = self.status()["action"]
        self.assertIn("本轮授权", action)
        self.assertIn("不必再要一次授权", action)

    def test_it_moves_on_once_the_judgement_exists(self) -> None:
        self.write_contract("complete")
        (self.feature_root / "spec" / "knowledge-use.yaml").write_text("schema: 1\n", encoding="utf-8")
        self.assertIn("spec.md", self.status()["action"])

    def test_after_registration_it_points_at_harness_not_build(self) -> None:
        """登记那一步已经渲染并核过 review——再叫作者去 build 就是两处说法。"""
        self.write_contract("story_written")
        action = self.status()["action"]
        self.assertIn("harness", action)
        self.assertIn("verifier", action)
        self.assertNotIn("`story-build build` 渲染", action)

    def test_the_road_after_verifier_is_spelled_out(self) -> None:
        """verifier PASS 之后做什么，得有下文。

        只写「接着做什么」的话，PASS 之后顺手再跑一次 harness 是很自然的动作——
        时间戳换了 subject，check-receipt 报证据缺失，verifier 只好再来一次，
        而产物一个字节没动。反过来，写成「之后一律不改产物」又会把真实缺陷压住，
        所以两个出口都要写出来。
        """
        self.write_contract("story_written")
        action = self.status()["action"]
        for step in ("check-receipt", "--deliver", "plan"):
            self.assertIn(step, action, f"verifier 之后的「{step}」这一步没写出来")
        self.assertIn("不重跑 harness", action)
        self.assertIn("真实缺陷", action, "真发现缺陷时怎么办没写出来")
        # 回执是 harness 的只读投影（receipt_schema 2.1），agent 零手填——
        # 让模型去回填一份它不该碰的文件，轻则白做，重则被判手写凭证。
        self.assertNotIn("回填", action, "还在让模型回填 framework 的凭证")

    def test_a_gate_step_shows_the_shape_of_the_file_to_write(self) -> None:
        """S1–S4 的侧车形状：二跑为弄清它切片读了本脚本六次。"""
        self.write_contract("in_progress")
        payload = self.status()
        self.assertIn("sidecar", payload, "关卡这一步没给出要写的文件形状")
        shape = json.dumps(payload["sidecar"], ensure_ascii=False)
        self.assertIn(".gate-options.json", shape)
        self.assertIn("material_scope", shape, "侧车形状没写明是给哪一级摆的")
        # 这一级摆哪两项也随形状一起给：键是固定的，作者要改的只有 label。
        # 不给的话他得先去别处找键叫什么，而 `decide` 只认合同登记的那两个。
        keys = [o["key"] for o in json.loads(CONTRACT.read_text(encoding="utf-8"))
                ["gates"]["material_scope"]["options"]]
        for key in keys:
            self.assertIn(key, shape, f"侧车形状里没给出 {key} 这一项")


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
        (self.feature_root / "spec" / "spec.md").write_text(
            '# AR90001 — 需求规格\n\n> **模块标识**: `AR90001`\n'
            + '\n## 0. 术语映射表\n\n| 业务名 | 权威模块 | 说明 |\n|---|---|---|\n| 受理单编号 | 提交入口 | 云侧受理后返回的编号 |\n\n## 9. 技术契约\n\n### 9.1 端云接口\n\n不涉及：复用既有提交接口。\n\n### 9.2 数据存储\n\n不涉及：不落库。\n\n### 9.3 配置项\n\n不涉及：没有新增配置。\n\n### 9.4 埋点\n\n不涉及：不新增埋点。\n\n### 9.5 依赖变更\n\n不涉及：只改一处入口。\n', encoding="utf-8")
        ensure_flow_state(self.root, FEATURE,
                          self.feature_root / "AR" / "story-src", DRAFT_TEXT)
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


class TheSourceScriptAsksTheTargetProject(unittest.TestCase):
    """用**本仓的** `author.mjs` 给另一个工程出任务包：位置读的必须是那个工程。

    此前这里只设了 cwd 而没传 `--project-root`，Python 于是按脚本自身位置解析工程——
    位置那一节回落成「跑 status 查你在哪」，而材料、知识、图读的都是目标工程。
    同一份任务包里两半对不上，作者只能挑一半信。
    """

    FLOW = {
        "schema": 3, "feature": FEATURE, "status": "complete",
        "design_generated_at": "2026-09-12T00:00:00",
        "rounds": [{
            "round": 1,
            "materials": {"path": "AR/story-src/materials.json", "digest": "seeded"},
            "positioning": {"scope_text": "本 AR 承载提交与回执", "sr_related_ars": []},
            "scope_options": [{"key": "carry_all", "label": "按当前范围整体承载"}],
            "gates": [],
        }],
    }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "另一个 工程 $x"
        feature_root = self.root / "doc" / "features" / FEATURE
        (feature_root / "RR").mkdir(parents=True)
        (feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n", encoding="utf-8")
        src = feature_root / "AR" / "story-src"
        src.mkdir(parents=True)
        (src / "story-flow.json").write_text(json.dumps(self.FLOW, ensure_ascii=False),
                                             encoding="utf-8")
        # 目标工程自己的激活清单与知识——任务包按 projectRoot 读它们，缺了会响亮失败
        ext = self.root / "doc" / "extensions"
        ext.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXT / "manifest.yaml", ext / "manifest.yaml")
        shutil.copytree(EXT / "knowledge", ext / "knowledge")

    def test_the_rerun_command_is_quoted_and_runs(self) -> None:
        """没走过 `/story` 时给的那条重跑命令，**原样粘过去就要能跑**。

        路径带空格与 `$`：不引起来的话，作者照抄得到的是另一个工程的答案或一句
        「unrecognized arguments」，而确定性的引用不该留给他自己处理。
        """
        (self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
         / "story-flow.json").unlink()
        proc = run("node", str(REPO_ROOT / "doc" / "extensions" / "hooks" / "spec"
                               / "author.mjs"), "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        block = proc.stdout.split("```powershell", 1)[1].split("```", 1)[0].strip()
        self.assertIn(f"'{self.root}'", block, "工程根没有按 shell 规则引起来")
        ran = run_in_shell(block, cwd=self.root)
        self.assertEqual(0, ran.returncode, (ran.stdout or "") + (ran.stderr or ""))
        self.assertIn('"exists"', ran.stdout, "跑出来的不是那个工程的 status")

    def test_the_position_comes_from_that_project(self) -> None:
        proc = run("node", str(REPO_ROOT / "doc" / "extensions" / "hooks" / "spec"
                               / "author.mjs"), "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("**下一步**", proc.stdout, "位置没取到目标工程的状态")
        self.assertNotIn("位置没取到", proc.stdout, proc.stdout[:400])


if __name__ == "__main__":
    unittest.main()
