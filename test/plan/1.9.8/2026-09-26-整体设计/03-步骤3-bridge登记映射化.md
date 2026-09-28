# 工作分册 03：adapt 取源与 bridge 映射

属于 [总览 P1](00-总览.md#2-三个实施包)，承接 D1/D6、范围 #11、AC02/05。保持安装所有权与业务行为，修复源码脱离消费配置后的实际定位和分发。

## 1. 源和目标

用户入口仍为 story adapt <project_dir>。adapt-scan 从自身 scripts 所在位置确定扩展根，读取同一根下 manifest、skills、hooks、knowledge 和 bridges；目标通过 --target 指定；本版按用户裁定固定装在 doc/extensions，保留既有配置读取，不增加其它安装位能力。

删除源侧 findRoot/framework.config.json 依赖和 --package 的源仓搜索。测试需另一来源时，直接执行该来源里的脚本。源可为开发 extensions，也可为已安装的消费扩展，依据同一相对布局，不自动寻找历史目录。

修改 adapt 的 SKILL、相关命令说明与检查调用，写清源是本次执行脚本所在扩展。真实目标的知识、name/description/adapted_for、adapters 所有权继续按当前合同处理。

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

- bridgesOf 返回 target/source 对；source 相对扩展根。解析失败和源缺失在任何目标写入前报告。
- inWriteFace、写入循环和 --check 全部按同一映射判断，target 相对消费工程；目标范围及无关文件保护沿既有规则。
- 映射 target 必须是目标内的相对文件路径，source 必须指向扩展源内真实文件；重复或越界映射明确报错。
- target 在解析时形成同一规范化路径，重复判定、脏检查、写入、自检共用；路径中的 `.` 及 Windows 同物理路径的大小写写法不能绕过脏面。全部 source 在任何写入前确认是扩展内可读文件，并预读待写文本；目录误作源也必须零写入失败。
- 按实际目标 Git 路径核脏覆盖，消费工程在维护仓子目录时不可把 Git 仓根相对路径错当工程相对路径。独立 target 与 demo 子目录两种输入均验证。
- 升级演进记录登记本版及实际目标适配要求；新格式解析直接服务本版，不新增旧映射 fallback。只有目标需要实际人工处理的知识/对接/在途事项才列三类条目；纯自动定位/映射变化不制造停等，可用普通段落说明无额外人工适配动作。
- 根的 verifier 维护装置与本映射无关。独立 framework 渲染命令的写入行为不成为 adapt 重装调度条件。

## 4. 验收和交回

定向 adapt ownership/source kinds/bridge fixtures 同步新源结构，覆盖首装、升级、自检、缺源、坏映射、脏覆盖、两类来源及目标知识保护。节点语法检查通过；根 Story 宿主位退出，开发六份源齐全。

消费链在固定 doc/extensions 下验：AGENTS 扩展段、bridge、Skill/作者页的下一条命令可定位并运行。工程根本身仍可带空格；这不等于支持自定义扩展安装位。R3 按用户裁定退出原需求，不再要求 bridgeText 或相关路径替换测试。

AC02 按允许面核 diff：manifest/bridges、adapt 脚本/说明、演进和必要入口路径；其余业务机制与知识保持 R197。AC05 在独立目标装开发源验六份入口，不要求 demo 1.9.7 与开发源相同。

交回源/目标实例、写入前失败证据、所有权结果和预算账。P1 总预算分摊见 [总览 §5](00-总览.md#5-预算与计量)。
