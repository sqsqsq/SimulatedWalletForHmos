# 术语映射推断 Prompt

> 当 AI 需要为**一批种子术语**生成 glossary 条目草稿时，按本 prompt 执行。
> 前置：`doc/module-catalog.yaml` 已建好（覆盖率 ≥ 80%）。

---

## 输入

1. **种子清单**：`doc/glossary-seed.txt`（用户提供，禁止 AI 自造）
   - 纯文本，每行一个业务名词
   - `#` 开头的行 = 注释，**忽略**
   - 空行忽略
   - 若文件不存在或 "去掉注释和空行后 = 0 行有效数据"，**停下来**跳转 SKILL.md Phase B Step 1.2 自动生成模板并提示用户，**禁止**继续 Step 2
2. **catalog**：`doc/module-catalog.yaml`

---

## 处理流程（**逐条**术语，**不要批量一次生成**）

对每个种子术语 `<T>` 独立生成一个 staging 文件：

```
doc/glossary-staging/<T>.yaml
```

（若 `<T>` 含特殊字符，用 `<T>` 的拼音或 ASCII 化名字，但 staging 文件内的 `term` 字段保留原文）

### Step 1：精确匹配

扫描 catalog，对每个 module 检查：

```
m.typical_business_terms 中是否有某项 === <T>?
```

- **命中** → `confidence: high`，`match_kind: exact_typical_term`，`matched_text: <T>`
- **未命中** → Step 2

### Step 1.5：反向扫描 NOT_responsible_for（**强制，不可跳过**）

> **为什么必须有这步**：catalog 作者可能在同一模块的 `typical_business_terms` 和 `NOT_responsible_for` 里同时提到了同一个业务词（例如 `AccountManager` 既把"账户"列为 typical term，又在 NOT_responsible_for 里排除"钱包账户"）。弱模型一旦在 Step 1 命中就默认 high 通过，会漏掉这类内部冲突——这是 glossary 误分模块的**首号原因**。

对 Step 1 命中 / 或 Step 2 即将产出的**每个**候选模块 m，**逐条**扫 `m.NOT_responsible_for[i]`：

```
条件触发（满足任一即中）：
  a) <T> 是 NOT_responsible_for[i] 原文的子串
  b) <T> 去空格/标点后是 NOT_responsible_for[i] 去空格/标点后的子串
  c) NOT_responsible_for[i] 含有"**等**"、"**等业务数据**"这类枚举收尾，且 <T> 与其中任一列举项字面相差 ≤ 1 字
```

- 若**命中** → 该候选立即退化为"内部冲突"，严格按下表处理：

  | 改写字段 | 新值 |
  |---|---|
  | `match_kind` | `typical_term_with_not_responsible_for_conflict` |
  | `confidence` | 降一级（high→medium，medium→low，low 保持） |
  | `candidates_top3[]` | 把该 m 显式加进来，`NOT_responsible_for_hint` **逐字复制** m.NOT_responsible_for[i] 的原文片段（**不要**总结） |
  | `confidence_hint` | 写："catalog 内部冲突——`<m.name>.typical_business_terms` 收录 `<T>`，但 `NOT_responsible_for[<i>]` 又排除了：<逐字原文>。建议 PRD 阶段对 `<T>` 的语义做分界说明。" |

- 若**未命中** → 不改动任何字段，正常进入 Step 2 / Step 4

**弱模型友好提示**：这是一条"查字符串 + 写两行 yaml"的机械指令，**不涉及推理**。**禁止**因为"Step 1 已经 high 命中"就跳过本步。本步是 Step 1 的后置强制校验，不是可选增强。

### Step 2：模糊匹配（按优先级）

| 优先级 | 匹配位置 | match_kind | confidence |
|--------|---------|-----------|-----------|
| 1 | `typical_business_terms[i]` 包含 `<T>` 或被 `<T>` 包含 | `fuzzy_typical_term` | medium |
| 2 | `one_liner` 包含 `<T>` | `fuzzy_one_liner` | medium |
| 3 | `responsibilities[i]` 包含 `<T>` | `fuzzy_responsibility` | low |

扫描整个 catalog，按命中优先级**取 Top-3 候选模块**。

若 3 个候选都是优先级 1，置信度 `medium`；若有任何优先级 3 的参与，置信度降为 `low`。

### Step 3：如仍零命中

`confidence: low`，`match_kind: unmatched`，`candidates_top3: []`。
在 staging 文件里**显式写**"AI 无法从 catalog 推断，请用户补充该术语所指代的场景或手填 canonical_module"。

### Step 4：选 canonical_module

- Step 1 命中 → 该模块就是 canonical
- Step 2 多候选 → 取 Top-1，**但必须在 staging 里列完整 Top-3 候选**让用户复核
- Step 3 零命中 → `canonical_module: "TBD"`，用户必须手填
- Step 1.5 触发冲突 → canonical 仍取命中模块，但 confidence 已降级；用户 y 前必须在 confidence_hint 里看到冲突原文

### Step 4.5：同 canonical_module 的 alias-merge 分支（**强制检查**）

> **为什么必须有这步**：种子清单里"账号"和"账户"、"卡包"和"卡包页"这类同义对是常态。若为每个都新建独立 term，glossary 会被同义词撑爆，还会污染 Skill 1 Step 1.5 的消歧逻辑（同一模块出现多个几乎等价的 term，反而降低命中质量）。

在写 staging **之前**，扫以下两处：
1. `doc/glossary.yaml` 已入库的 `terms[]`
2. 本批次其余已落地的 `doc/glossary-staging/*.yaml`

对每个已存在的 term `<T'>`（`T' ≠ T`），检查是否同时满足：

| 条件 | 判定 |
|---|---|
| 同 `canonical_module` | `glossary[T'].canonical_module === <候选 canonical>` |
| 字面高度相似 | 满足任一：<br>① `<T>` 是 `<T'>` 的子串或超集<br>② `<T>` 与 `<T'>` 字符级相似度 ≥ 0.5（长度相近、≤ 2 字不同）<br>③ `<T>` 在 `<T'>.aliases` 里、或 `<T'>` 在 `<T>.aliases` 里 |

**全满足 → 触发 alias-merge 候选**，按下表写 staging：

| 字段 | 值 |
|---|---|
| `match_kind` | `alias_merge_candidate` |
| `confidence` | 降级（high→medium） |
| `term.canonical_module / owner_layer` | 正常填 |
| `confidence_hint` | "本 term `<T>` 与已存在的 `<T'>`（canonical=`<ModuleName>`）字面相似度高、同归属，建议作为 `<T'>` 的 alias 合并而非新建独立 term" |

展示时（SKILL.md §3.2），AI 必须把"推荐动作"默认成 `e 并入 <T'>` 而不是 `y`，以免用户盲按 y 产生冗余条目。

**示例**：glossary 已有 `term: "账号", canonical: AccountManager`。本批种子含"账户"，Step 1 命中 AccountManager.typical_business_terms[7]，Step 1.5 又因 NOT_responsible_for 冲突降 medium。Step 4.5 看到：同 canonical + 长度 2 + 1 字差 → 触发 alias_merge_candidate。最终 staging：match_kind = `alias_merge_candidate`，confidence_hint 建议并入"账号"条目。

### Step 5：**强制**补全 easily_confused_with

查 `catalog[canonical_module].easily_confused_with`：
- 若**非空** → 把每条转换成 glossary 的 `{term, module, disambiguation}` 格式复制过来
  - `term`: 对应模块的某个 `typical_business_terms`（选最能代表那个模块的词）
  - `module`: 对应模块 name
  - `disambiguation`: 直接复用 catalog 里 disambiguation 原文
- 若**空** → `easily_confused_with: []`

**禁止**：凭想象编易混项。必须来自 catalog 已有数据。

### Step 6：填其余字段

| 字段 | 填法 |
|------|------|
| `term` | 原始 `<T>`（不做大小写 / 繁简转换） |
| `owner_layer` | 必须等于 `catalog[canonical_module].layer`（不一致就是 bug） |
| `aliases` | 若种子清单里有多个术语指向同一 canonical_module，可作为 aliases（但保持保守，宁缺勿滥） |
| `sample_usage` | 若在 catalog / architecture.md 里找到该术语的使用例句就复制；否则留 `""` 让用户补 |
| `confidence_hint` | 记录你的判定依据，例如："匹配位置：WalletMain.typical_business_terms[3]"；或用户修正时的规则 |
| `match_info.*` | 如实填你的匹配过程（让用户能 audit） |

---

## 输出格式

每条术语一个独立文件：

```
doc/glossary-staging/<term>.yaml
```

严格遵循 `skills/0-catalog-bootstrap/templates/glossary-term-template.yaml`。

---

## 完成后（**默认交互式确认，按 `SKILL.md Phase B Step 3` 执行**）

staging 全部落地后，**不要**一次把原始 YAML 倒给用户看，也**不要**要求用户手动改 flag。走对话式逐条确认：

### 1. 开场汇报（一次）

```
已落 N 条 staging 到 doc/glossary-staging/：
  high: X 条   medium: Y 条   low/unmatched: Z 条（<列出名称>）

开始逐条确认，你只要回 y / e <改指令> / s / q 即可：
```

### 2. 对每条术语（严格 1 条 1 条问，绝不合批）

展示格式照 `SKILL.md §3.2`，必须包含：
- `【i/N】术语："<T>"`
- Canonical module + layer
- 匹配置信度 + 匹配依据（哪个字段命中）
- Aliases
- ⚠️ 易混项（**必出**，即便为空也写"（catalog 未声明）"）——每条含 disambiguation 判定规则
- Sample usage

然后问 `y / e / s / q`。

### 3. 按用户回应自主处理（AI 动手，不让用户改文件）

| 回应 | 动作 |
|------|------|
| `y` | ① staging 的 `confirmed_by_user: true`<br>② 只取 staging 的 `term:` 子树追加/替换到 `doc/glossary.yaml`<br>③ **删除** staging 文件（审计靠 git 历史，不用 `_merged/` 归档）<br>④ 进入下一条 |
| `e <指令>` | patch staging → 重新展示本条 → 再问 |
| `s` | 保留 staging 不动，进入下一条 |
| `q` | 删 staging，进入下一条 |

### 4. 收尾（一次）

```
✅ 合并 A 条 / 修改 B 条 / 跳过 C 条 / 作废 D 条
剩余待确认 staging：<列表>

建议跑：cd harness && npx ts-node harness-runner.ts --phase glossary
```

然后停止，不要自动跑 harness。

**禁止**：
- 在未 `y` 前写入 `doc/glossary.yaml`
- 把多条打包问 "这批都 y 吗？"
- 把 `好的` / `嗯` 当 `y`
- 折叠 easily_confused_with（glossary 的核心防御就靠这一栏）
- 处理用户种子清单外的术语
