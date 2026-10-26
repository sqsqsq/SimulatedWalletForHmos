# testing 阶段 · 扩展要求（写之前读这一页）

> 读者：真机测试阶段的作者。时机：动笔前读一遍；门禁报错时回到「门禁会拦什么」。

开始本阶段的实际工作之前（读代码、设计、改动之前），先取本阶段的作者知识任务（story-knowledge Skill，`--audience author`）：它同时记下本阶段的开始。第一次开始前在本 Feature 的目录（知识任务第 1 块写的位置）写 `.usage-input.json`：`{"agent": "<宿主>", "model": "<模型>"}`，不知道的写 null。本阶段原生闭环、本轮工作做完后跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <Feature id> --finalize --phase testing`，返回 ok 才算记进 `doc/usage.json`，再交付、问下一阶段或提交代码（带上 `doc/usage.json`）；失败按它报的原因处理后重跑同一条。

**契约实体上的 `must` 定本次义务**：plan 已经把每条规约要求挂到扛着它的实体上，本阶段不重新判断适用性、不改选型。要弄清义务背后的方法、语义或项目协议时，查它指回的原知识（`must.rule` 的规约、选中的模式、相关项目事实，都在激活清单里）；真实接口以代码为准。契约与知识、代码对不上时回 plan 改，不在本阶段绕过。

**本阶段是最后一道关**——这些约束再往后就没有验证环节了。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| `contracts.yaml` | 各实体上的 `must`——`verify` 决定谁来验 |
| 需求根目录的 `acceptance.yaml` | `knowledge_rule` 与 `knowledge_decision_id` 指回这条义务出自的判断的那条验收条目，按它的 `device_focus` 走查 |

## 二、产出形态

**`must.verify` 就是分派单源**：

| verify | 本阶段 |
|---|---|
| `device` | 只由实机验——**必须覆盖** |
| `both` | UT 与实机都要——**也必须覆盖** |
| `ut` / `review` | **本阶段不适用** |

按验收条目的 `device_focus` 走查或测量，给**可复核证据**：截图、数值、日志。

**「已验证」三个字不构成结论**——只写「符合要求」而没有可复核证据的，记为未验证。

确实到不了的（环境不具备、依赖未就绪），诚实写「待验证 + 阻塞原因」，不要标成已验证。
**未到达的阶段不得称已验证，这条比覆盖率重要。**

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase testing --feature <需求名>
```

阶段闭环之后按本页开头的收尾命令记完（`--finalize --phase testing`），成功后再交付、进下一阶段或提交代码。

## 四、门禁会拦什么

- `verify` 为 `device` / `both` 的义务在本阶段没有覆盖，也没有说法。
- 结论只有「已验证」「符合要求」而没有可复核证据。
