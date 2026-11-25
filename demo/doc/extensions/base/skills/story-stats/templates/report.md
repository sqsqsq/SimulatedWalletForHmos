<!-- 报告模板：按下面的结构写，数字只取 facts.json；注释不进报告。 -->

# AI 框架使用情况统计报告

- **项目：** <facts.project>
- **统计时间：** <facts.collected_at>
- **依据：** `<facts.record>` 摘要 <facts.usage_sha256 前 12 位>；Git HEAD <facts.head 前 12 位，没有写「无提交」>

## 1. 汇总

| 指标 | 结果 |
|---|---|
| 使用框架的需求数 | <summary.requirements> |
| 开发人（提交人去重） | <summary.developers 的人数> |
| 关联提交数（去重） | <summary.commits> |
| 关联提交新增 / 删除行数（按需求累加） | +<summary.added> / −<summary.deleted> |

各功能步骤：每个步骤一行，列「做完过的需求数 completed」「有耗时的需求数 timed」「累计耗时 spent_total（秒换成时:分:秒，表头写明单位）」；
`story update` 另列收口轮数 rounds_total。`summary.identities` 按 agent / 模型列需求数，`summary.versions` 按 Extension / Framework 版本列需求数，
值为 null 的写「未知」。

## 2. 逐需求明细

每个需求一小节，标题写「<number>（启动于 <stamp>）」，节点键 key 写在标题下一行。依次写：
提交人、agent / 模型、Extension / Framework 版本；做完过的步骤与各自耗时（时:分:秒；有 rounds 的写轮数，没有 spent 的写「耗时未知」，没有行的步骤不写）；
关联提交逐笔一行（短 SHA、提交人、时间、+/− 行数，`mixed` 为真的标「混合提交」）与合计；`gaps` 非空时逐项写出。

## 3. 统计口径

- 步骤行存在表示该步骤做完过；spent 是可核实轮次的日历跨度之和，含轮内等待与中断，步骤之间可以重叠，不相加成需求总耗时。
- 提交归属看 `doc/usage.json` 的变更：新增或改动某个需求节点的提交算这个需求的；一笔提交带几个需求就各计整笔并标混合提交；汇总行数是逐需求行数之和，混合提交在每个相关需求里各计一次。
- 需求以编号与启动身份区分，不取名称；agent 与模型是模型自报，没有自报的写身份未知。
