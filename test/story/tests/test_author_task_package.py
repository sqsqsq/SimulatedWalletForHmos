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
FEATURE = "TP90001"

# 任务包体量上限：作者要在动笔前一次读完它
MAX_PACKAGE_BYTES = 12 * 1024


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90, cwd=cwd)


def as_url(path: Path) -> str:
    """Windows 上动态 import 只认 file:// URL。"""
    return json.dumps(path.resolve().as_uri())


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
    """spec 里的图逐张给主题与可粘贴围栏，**不指定放哪一章**。"""

    SPEC = ("# 甲需求\n\n## 5. 业务流程\n\n### 5.2 自动充值触发\n\n"
            "```mermaid\ngraph TD\nC[余额上报] --> D[判定]\n```\n")

    def package_with_spec(self) -> str:
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text(self.SPEC, encoding="utf-8")
        return self.task_package()

    def test_each_diagram_comes_with_a_pasteable_fence(self) -> None:
        package = self.package_with_spec()
        self.assertIn("spec 里的图", package)
        self.assertIn("%% 图源 spec §5.2 #1", package, "围栏没带上来源标记，粘过去就核不到")
        self.assertIn("C[余额上报]", package, "围栏原文没给，作者得自己回去抄")

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

    def test_chapter_questions_come_from_the_contract(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        package = self.task_package()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["title"], package,
                          f"任务包漏了「{chapter['title']}」这一章")
            self.assertIn(chapter["questions"][0], package,
                          "章的读者问题没从合同渲染进来")

    def test_a_new_contract_question_shows_up_without_touching_the_hook(self) -> None:
        """改合同，任务包跟着变——这是「投影」与「副本」的分界。"""
        path = self.root / "doc/extensions/skills/story/contracts/story-chapters.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        contract["chapters"][0]["questions"].append("这一轮新加的读者问题")
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertIn("这一轮新加的读者问题", self.task_package())

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

    def test_images_in_the_material_list_are_listed_one_by_one(self) -> None:
        """材料里的图逐张列出，并写明「用或写明不用」的义务。

        两跑各丢过一次图：一次主流程没画，一次三张图一张没进正文。
        """
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"items": [
                {"kind": "image", "paths": ["assets/x/one.png"], "caption": "签约页"},
                {"kind": "image", "paths": ["assets/x/two.png"]},
            ]}, ensure_ascii=False), encoding="utf-8")
        package = self.task_package()
        self.assertIn("assets/x/one.png", package)
        self.assertIn("签约页", package)
        self.assertIn("assets/x/two.png", package)
        self.assertIn("不属于本需求的不进正文", package)
        self.assertIn("引进正文再在图题里解释不算", package,
                      "规则要单向：把图引进正文再解释是六跑那次的形态")
        self.assertIn("--unused", package, "用不上的那些要有写理由的去处")

    #: 图名带空格是常事——导入从文档里抽出来的图常常沿用原文里的名字。
    SPACED = "assets/x/page one.png"

    def seed_two_images(self) -> None:
        """盘上放两张图并登记：一张要用、一张已登记不用（名字带空格）。"""
        for rel in ("assets/x/one.png", self.SPACED):
            img = self.feature_root / rel
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(b"PNG")
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"items": [
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
        proc = subprocess.run(line, shell=True, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=90,
                              cwd=self.root)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(0, proc.returncode, out)
        self.assertIn('"ok":true', out.replace(" ", ""), out[:400])
        self.assertNotIn("\\", line, "命令里还有续行的反斜杠——shell 会把它当字面参数")


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
                   f"const u = await import({as_url(shared / 'knowledge-use.mjs')});"
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
        proc = run(sys.executable, "doc/extensions/skills/story/scripts/story_flow.py",
                   "status", "--feature", FEATURE, cwd=self.root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def write_contract(self, status: str) -> None:
        (self.feature_root / "AR" / "story-flow.json").write_text(json.dumps({
            "schema": 3, "feature": FEATURE, "status": status,
            "rounds": [{"round": 1, "gates": []}],
        }, ensure_ascii=False), encoding="utf-8")

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

        只写「之后不再改产物」的话，PASS 之后顺手再跑一次 harness 是很自然的动作——
        时间戳换了 subject，check-receipt 报证据缺失，verifier 只好再来一次，
        而产物一个字节没动。
        """
        self.write_contract("story_written")
        action = self.status()["action"]
        for step in ("check-receipt", "--deliver", "plan"):
            self.assertIn(step, action, f"verifier 之后的「{step}」这一步没写出来")
        self.assertIn("不再跑 harness", action)
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
        self.assertIn("签与导入不分先后", shape)


class ChapterFileCarriesOnlyBody(WorkspaceCase):
    """章文件带了本章标题时命令自己剥掉——两跑都为标题重复重建过骨架。"""

    def build(self, *args: str) -> subprocess.CompletedProcess:
        return run("node", "doc/extensions/skills/story/scripts/story-build.mjs",
                   *args, "--feature", FEATURE, cwd=self.root)

    def setUp(self) -> None:
        super().setUp()
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.first = self.contract["chapters"][0]["title"]
        (self.feature_root / "AR" / "story-src" / "materials.json").write_text(
            json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")
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
