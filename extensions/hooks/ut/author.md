# ut 阶段 · 扩展要求（写之前读这一页）

> 读者：UT 阶段的作者。时机：动笔前读一遍；门禁报错时回到「门禁会拦什么」。

开始本阶段的实际工作之前（读代码、设计、改动之前），先取本阶段的作者知识任务（story-knowledge Skill，`--audience author`）：它同时记下本阶段的开始。第一次开始前在本 Feature 的目录（知识任务第 1 块写的位置）写 `.usage-input.json`：`{"agent": "<宿主>", "model": "<模型>"}`，不知道的写 null。本阶段原生闭环、本轮工作做完后跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <Feature id> --finalize --phase ut`，返回 ok 才算记进 `doc/usage.json`，再交付、问下一阶段或提交代码（带上 `doc/usage.json`）；失败按它报的原因处理后重跑同一条。

**契约实体上的 `must` 定本次义务**：plan 已经把每条规约要求挂到扛着它的实体上，本阶段不重新判断适用性、不改选型。要弄清义务背后的方法、语义或项目协议时，查它指回的原知识（`must.rule` 的规约、选中的模式、相关项目事实，都在激活清单里）；真实接口以代码为准。契约与知识、代码对不上时回 plan 改，不在本阶段绕过。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| `contracts.yaml` | 各实体上的 `must`——`verify` 决定谁来验 |
| 需求根目录的 `acceptance.yaml` | `knowledge_rule` 与 `knowledge_decision_id` 指回这条义务出自的判断的那条验收条目，按它的 `ut_focus` 写断言 |

## 二、产出形态

**`must.verify` 就是分派单源**，不必另找豁免清单：

| verify | 本阶段 |
|---|---|
| `ut` | 只由 UT 验——**必须覆盖** |
| `both` | UT 与实机都要——**也必须覆盖** |
| `device` / `review` | **本阶段不适用**，报「不适用」即可 |

不由 UT 验的条目不必也不应为它硬造用例。

每条义务二选一：**真实证据**（哪个用例覆盖了它）或**显式不适用 + 理由**。不能什么都不写。

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase ut --feature <需求名>
```

阶段闭环之后按本页开头的收尾命令记完（`--finalize --phase ut`），成功后再交付、进下一阶段或提交代码。

## 四、门禁会拦什么

- `verify` 为 `ut` / `both` 的义务在本阶段没有覆盖，也没有说法。
- 标了 `ut` / `both` 却在 `acceptance.yaml` 里找不到 `knowledge_rule` 与 `knowledge_decision_id` 指回它的验收条目
  ——那样本阶段无从知道该覆盖哪个场景。
- 用例名对得上而断言不相干——判据是**用例是否真的覆盖了那个场景**，
  不是用例名里有没有出现该域的词。按验收条目的 `ut_focus` 写断言。

断言对准义务说的可观察行为（产生了什么、何时、几次、带什么值），不对准「调用了某个封装」。

覆盖不了就回 plan 核实际验法——场景确实 UT 验不了时，由 plan 修正 `must.verify`；不要为过检查改分派，也不要留一条名字对得上、断言不相干的用例充数。
