# ut 阶段 · 扩展要求（写之前读这一页）

**契约实体上的 `must` 就是本阶段的知识来源**：plan 已经把每条规约义务挂到了扛着它的
那个实体上。不回去重读规约、不重新判断适用性。对不上时回 plan 改 `must`。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| `plan/contracts.yaml` | 各实体上的 `must`——`verify` 决定谁来验 |
| `spec/acceptance.yaml` | `knowledge_rule` 指回规约条目的那条验收条目，按它的 `ut_focus` 写断言 |

## 二、产出形态

**`must.verify` 就是分派单源**，不必另找豁免清单：

| verify | 本阶段 |
|---|---|
| `ut` | 只由 UT 验——**必须覆盖** |
| `both` | UT 与实机都要——**也必须覆盖** |
| `device` / `review` / `probe` | **本阶段不适用**，报「不适用」即可 |

不由 UT 验的条目不必也不应为它硬造用例。

每条义务二选一：**真实证据**（哪个用例覆盖了它）或**显式不适用 + 理由**。不能什么都不写。

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase ut --feature <需求名>
```

## 四、门禁会拦什么

- `verify` 为 `ut` / `both` 的义务在本阶段没有覆盖，也没有说法。
- 标了 `ut` / `both` 却在 `acceptance.yaml` 里找不到 `knowledge_rule` 指回它的验收条目
  ——那样本阶段无从知道该覆盖哪个场景。
- 用例名对得上而断言不相干——判据是**用例是否真的覆盖了那个场景**，
  不是用例名里有没有出现该域的词。按验收条目的 `ut_focus` 写断言。

覆盖不了就回 plan 把 `must.verify` 改成 `device`，不要留一条名字对得上、断言不相干的用例充数。

报错会一次列全，每条都写「缺什么 / 写到哪 / 怎么写」。不需要读 `post_check.mjs` 反推判据。
