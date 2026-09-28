# 工作分册 03：adapt 取源与 bridge 映射

属于 [总览 P1](00-总览.md#2-三个实施包)，承接 D1/D6、范围 #11、AC02/05。保持安装所有权与业务行为，修复源码脱离消费配置后的实际定位和分发。

## 1. 源和目标

用户入口仍为 `story adapt <project_dir>`。正式对外适配从 demo/doc/extensions/skills/story-adaptation/scripts/adapt-scan.mjs 执行，源是 demo 中已安装的发布版；测试从已安装开发版的 template 或消费形态 fixture 执行。

定位、配置读取、YAML 依赖解析、参数行为（含 --package）回到 R197 实现：从脚本位置向上找所在消费工程，使用该工程的已安装扩展及宿主入口。目标为参数指定的真实标准工程。本版固定安装位 doc/extensions，保留 R197 的目标依赖检查和安装所有权规则。

extensions 是源码存放位置；其中链接和命令按安装后的 doc/extensions 与宿主目标位置编写、验证。adapt 不直接消费开发目录 bridges/，发布安装器负责把这些源装到 demo 宿主位置。

## 2. bridge 源与映射

| 包内源（相对扩展根） | 宿主目标（相对目标工程） |
|---|---|
| bridges/opencode-skill-story.md | .opencode/skill/story/SKILL.md |
| bridges/claude-command-story.md | .claude/commands/story.md |
| bridges/cac-command-story.md | .cac/commands/story.md |
| bridges/codex-skills-story.md | .codex/skills/story/SKILL.md |
| bridges/cursor-skill-story.md | .cursor/skills/story/SKILL.md |
| bridges/agents-skill-story.md | .agents/skills/story/SKILL.md |

前四份由 R197 原入口归位；后两份按真实宿主形态补齐命令路由，消费路径指向实际安装位。前四份在 doc/extensions 布局下保持原内容；按用户裁定退出自定义安装位替换分支及专用测试。源文件按宿主分开，不合成通用模板。

### 2.1 两份 .agents 入口的版本归属

| 文件 | demo 的 R197 基线 | 装开发版后的 template |
|---|---|---|
| .agents/skills/story/SKILL.md | Framework 已生成的薄跳板，P1 原字节迁入，归物化保持面；R197 manifest 未登记 | 由本表 agents-skill-story.md 映射安装，归已装 1.9.8 Extension；不再拿 R197 薄跳板作内容基准 |
| .agents/skills/story-adaptation/SKILL.md | Framework 已生成的薄跳板，P1 原字节迁入，归物化保持面 | 复制 demo 后保持，链接到目标实际安装的 story-adaptation；本版不新增第七份 bridge 或第二份源码 |

根两份宿主入口均迁出；新建的 agents-skill-story.md 是 Extension 的路由源，不从旧 Framework 通用跳板复制一个并继续维护两份。独立目标缺 story-adaptation 单独入口时仍可经 `/story adapt` 使用，保留既有功能边界。

### 2.2 升级或独立渲染发生实际差异时

先用目标**已装版本**的 manifest 判断该路径是否属于 Extension 写入面，再核实际 diff：未登记的 Framework 入口按该发布件物化结果核；已登记的入口应等于同一已装包的 bridge 源及既有路径替换结果。demo 仍装 R197 时，两份 .agents 均按 Framework 面核；目标装 1.9.8 后，story 才按 Extension 映射核。

没有实际差异就无附加动作。如果实际调用确实把已登记入口替换成通用内容，只恢复该冲突文件为目标已装包对应的映射内容，并记录路径和证据；不拿开发源升级已发布目标，不全量重装，不增加自动监控或恢复分支。源缺失或发布件要求与当前入口合同冲突时报告维护设计者，不能把不一致视为验收通过。仍不据此声称正常 UPDATE 一定调用该生成器。

manifest 仍用当前 schema 1.0，provides.bridges 改为以下形态；本版不实施 2.0.1 的 manifest 1.1：

```yaml
  bridges:
    - target: .opencode/skill/story/SKILL.md
      source: bridges/opencode-skill-story.md
```

## 3. adapt 改动

- 以 R197 为基线，bridgesOf 读取新登记中的 target；安装和 --check 均从源消费工程的 target 宿主位置读取，再写入或核对目标工程同一路径。source 字段由发布安装器消费。
- 保留 R197 的缺入口源检查、覆盖面脏检查、知识/对接/身份所有权、扩展段处理及自检；缺登记的宿主源时目标不写。
- 退出为开发目录直接执行增加的取源、借目标 harness 解析源 YAML、参数拒绝、仓内子目录 Git 前缀换算/配置跟踪判断，以及 P1 返修的路径规范化、大小写折叠和源预读。--package 恢复 R197 行为，不增加兼容分支。
- 同步 Skill、命令和升级演进说明：正式源来自 demo 发布版；测试源来自已安装副本。仅真实人工适配事项列入知识/对接/在途提示。

## 4. 验收和交回

adapt ownership/source kinds 的包 fixture 使用 package/doc/extensions、framework.config.json、所在工程 YAML 依赖及宿主位置入口。从已安装脚本执行，覆盖首装、升级、重复安装、自检、缺宿主源，以及知识、对接、身份和无关内容保护。六份入口按源工程宿主内容核对。

M09 从登记 target 所在位置解析 bridge 正文链接；checker 执行器使用 --project-root 内安装的扩展。单测 DEV_EXT 保持消费形态，检查下一条命令能在消费根定位。固定 doc/extensions，不要求开发源独立运行。

AC02 核 R197 对照：除登记解析及必要说明外，adapt 保持原定位与复制逻辑；业务 flow/hooks/rules/知识保持。AC05 先装开发版到 template，再由其中 adapt 安装独立目标，不要求 R197 demo 与开发版相等。

交回实际源/目标、六份入口、所有权保护、旧分支和专用测试退出证据。预算按总览 §5 复算；P1 先前通过不免除本次减法的复核。
