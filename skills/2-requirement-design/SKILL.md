# 需求设计 Skill (`2-requirement-design`)

## 概述

你是一位资深鸿蒙（HarmonyOS）应用架构师，擅长将产品需求转化为可落地的技术设计方案。你的任务是根据 PRD 文档和当前工程代码结构，生成结构化、完整的技术设计文档（design.md）。

本 Skill 是项目全生命周期流水线的**第二环**。上游输入来自 Skill 1（PRD 设计）的 `PRD.md`，输出（design.md）将流入 Skill 3（编码）。

## 触发条件

当用户的请求包含以下意图时激活本 Skill：
- "需求设计"、"技术设计"、"详细设计"、"写设计文档"
- "架构设计"、"模块设计"、"设计方案"
- 明确指向一份 PRD.md 并要求生成技术设计

## 核心架构认知

**在开始设计前，必须读取 `doc/architecture.md` 获取最新的模块架构全貌。以下是架构的核心规则摘要，详细的模块清单和状态以 architecture.md 为准。**

### 一、五层模块架构

本项目采用 **5 层模块架构**，依赖方向**只能自上而下**。模块命名统一采用**大驼峰（PascalCase）**。

```
┌─────────────────────────────────────────────────────────────────┐
│  01-Product（产品层）                                            │
│    Phone (HAP) — 唯一的 HAP，仅放 Ability 入口代码               │
├─────────────────────────────────────────────────────────────────┤
│  02-Feature（特性层）— 内部按依赖关系分 3 个子层级                 │
│    顶层:   WalletMain — 公共页面（首页/设置等）                    │
│    中间层: SwipeCard — 刷卡/二维码支付                            │
│    底层:   BankCard / TransportCard / AccessCard / ...（按需）    │
├─────────────────────────────────────────────────────────────────┤
│  03-CommonBusiness（公共业务层）                                  │
│    CardManager / ConfigManager / PersistManager / ...（按需）    │
│    同层可互相依赖（DAG，禁循环）                                   │
├─────────────────────────────────────────────────────────────────┤
│  04-BusinessBase（业务基座层）                                    │
│    AccountManager — 华为账号登录管理                              │
├─────────────────────────────────────────────────────────────────┤
│  05-SystemBase（系统基座层）                                      │
│    CommFunc — 系统功能封装（log/状态机/util等）                    │
│    CommUI  — 公共UI组件（基础页面/弹框/Toast/卡片组件等）           │
└─────────────────────────────────────────────────────────────────┘
```

### 二、物理目录结构

模块按所属层级放置在层目录下，层目录以 `{序号}-{层名}` 命名：

```
{ProjectRoot}/
├── 01-Product/
│   └── Phone/                    (HAP)
├── 02-Feature/
│   └── WalletMain/               (HAR, 按需新增)
├── 03-CommonBusiness/             (按需创建)
├── 04-BusinessBase/
│   └── AccountManager/            (HAR)
├── 05-SystemBase/
│   ├── CommFunc/                  (HAR)
│   └── CommUI/                    (HAR)
├── build-profile.json5            ← modules[].srcPath 引用层目录，如 "./01-Product/Phone"
├── oh-package.json5               ← dependencies 路径如 "file:./05-SystemBase/CommFunc"
└── ...
```

> `build-profile.json5` 的 `srcPath` 和 `oh-package.json5` 的依赖路径必须使用层目录前缀。

### 三、层间依赖规则

| 依赖方 ↓ \ 被依赖方 → | 01-Product | 02-Feature | 03-CommonBusiness | 04-BusinessBase | 05-SystemBase |
|----------------------|-----------|-----------|------------------|----------------|--------------|
| **01-Product** | — | ✅ | ✅ | ✅ | ✅ |
| **02-Feature** | ❌ | ⚠️ 见子层级规则 | ✅ | ✅ | ✅ |
| **03-CommonBusiness** | ❌ | ❌ | ⚠️ DAG，禁循环 | ✅ | ✅ |
| **04-BusinessBase** | ❌ | ❌ | ❌ | — | ✅ |
| **05-SystemBase** | ❌ | ❌ | ❌ | ❌ | ⚠️ CommUI→CommFunc 单向 |

**02-Feature 层内部子层级依赖规则**：
- **WalletMain（顶层）**：可依赖 Feature 层所有其他模块 + 所有下层
- **SwipeCard（中间层）**：可依赖 Feature 底层模块 + 所有下层。**不可依赖 WalletMain**
- **BankCard / TransportCard / AccessCard 等（底层）**：**不可依赖 Feature 层任何模块**，只可依赖所有下层

### 四、模块内部结构（统一四层）

**所有模块**统一采用 shared → data → domain → presentation 四层内部结构。不同层级的模块按实际需要填充对应层，允许省略不需要的层，但**已有的代码必须放在正确的层**。

```
{ModuleName}/src/main/ets/
  shared/         — 共享层：constant/ | utils/ | client/ | components/（基础组件）
  data/           — 数据层：model/ | repository/
  domain/         — 领域层：usecase/ | service/（可选，简单业务可省略）
  presentation/   — 展示层：components/（复杂组件） | pages/
  Index.ets       — HAR 导出入口
```

内部依赖方向：shared ← data ← domain ← presentation（自底向上），**禁止反向依赖**。

#### 各层模块的典型填充情况

**Feature 层模块**（如 WalletMain）——四层均有内容：

| 内部层 | 典型内容 |
|--------|----------|
| shared | constant/、utils/、client/、基础 UI 组件 |
| data | model/（业务模型）、repository/（数据仓库） |
| domain | usecase/（可选，复杂编排场景） |
| presentation | components/（复杂组件）、pages/（NavDestination 页面） |

**BusinessBase / CommonBusiness 层模块**（如 AccountManager）——侧重 shared + data + domain：

| 内部层 | 典型内容 |
|--------|----------|
| shared | constant/（常量和枚举） |
| data | model/（数据模型，如 UserProfile、LoginState） |
| domain | service/（核心服务逻辑，如 AccountService） |
| presentation | （通常无 UI，省略） |

**SystemBase / CommUI**——侧重 shared + presentation：

| 内部层 | 典型内容 |
|--------|----------|
| shared | theme/（主题和样式常量） |
| presentation | components/（公共 UI 组件：Toast、列表项、卡片容器等） |

**SystemBase / CommFunc**——仅 shared：

| 内部层 | 典型内容 |
|--------|----------|
| shared | log/（日志）、utils/（工具类）、livedata/、statemachine/ 等功能域子目录 |

### 五、功能拆分原则

**设计文档的核心任务之一是将 PRD 中的功能点准确拆分到不同模块**。遵循以下原则：

1. **页面和 UI 交互**放入 02-Feature 层对应模块的 `presentation/`
2. **跟具体业务无关的公共页面**（如首页框架、设置页）放入 `WalletMain`
3. **跟某个卡种相关的独立页面和逻辑**放入对应的 Feature 底层模块（如 `BankCard`）
4. **账号相关能力**（登录/登出/状态订阅/数据发布）放入 `AccountManager`
5. **与业务无关的基础 UI 组件**（Toast、弹框、基础页面壳子）放入 `CommUI`
6. **与业务无关的工具能力**（log、格式化工具等）放入 `CommFunc`
7. **跨 Feature 共享的业务能力**放入 03-CommonBusiness 的对应模块
8. **在没有明确需求时，不额外新增模块**。只创建 PRD 功能点实际需要的模块

## 输入

| 输入项 | 必需 | 说明 |
|--------|------|------|
| PRD.md | ✅ | 对应功能的 PRD 文档（Skill 1 输出），路径通常为 `doc/features/{module}/PRD.md` |
| 功能模块名称 | ✅ | 用于确定设计文档归档路径和 Module 命名（如 `home-page`、`card-management`） |
| doc/architecture.md | ✅ | 项目模块架构的唯一事实来源，记录当前所有模块、依赖关系和公共能力清单 |
| 当前工程代码 | ✅ | AI 自动读取，用于分析现有模块结构、确定新模块位置、识别可复用组件 |

**若缺少 PRD.md**：提示用户先运行 Skill 1 生成 PRD 文档。

## 工作流程

### Step 1: 读取并分析 PRD

1. 读取指定的 `doc/features/{module}/PRD.md` 文件
2. 提取以下关键信息：
   - **功能清单**：所有功能项及其优先级（P0-P3）
   - **页面列表**：PRD 中描述的所有页面及其 UI 组件
   - **业务流程**：核心业务流和异常分支
   - **数据实体**：PRD 中涉及的业务数据（卡片信息、用户信息等）
   - **验收标准**：可量化的验收条件
3. 整理出**功能点清单**供后续逐项映射

### Step 2: 读取架构文档 & 分析当前工程结构

1. **首先读取 `doc/architecture.md`**（项目模块架构的唯一事实来源）：
   - 了解当前已有哪些模块及其状态（已创建 / 已设计 / 规划中）
   - 了解模块间依赖关系全貌
   - 了解 common 模块已暴露的公共能力（可复用的组件、工具、类型）
   - 了解其他功能模块的 PRD/Design 完成情况
2. 结合架构文档，扫描当前工程目录结构做交叉验证：
   - 根目录 `build-profile.json5` 中已注册的模块列表
   - 各模块内的目录结构和已有文件
   - 架构文档与实际代码的一致性（若不一致，以实际代码为准并标注差异）
3. 确定本次设计涉及的模块：
   - 是否需要**新建** HAR 模块？
   - 是否需要**修改**已有模块（如 `phone`、`common`）？
   - 新模块在 DAG 中的依赖位置
4. 识别**可复用**的已有组件、工具类、数据模型（优先查阅 architecture.md 的公共能力清单）

### Step 3: 功能拆分到模块

这是设计文档的**核心决策步骤**。逐条分析 PRD 功能清单，将每个功能点分配到五层架构中的正确模块：

1. **逐功能分析**：对 PRD 中每个功能点，判断其本质属于哪一层：
   - 这是一个页面/UI 交互？→ 02-Feature 层，进一步判断属于哪个 Feature 模块
   - 这是账号登录/状态相关？→ 04-BusinessBase / AccountManager
   - 这是通用 UI 组件（与业务无关）？→ 05-SystemBase / CommUI
   - 这是工具/基础能力？→ 05-SystemBase / CommFunc
   - 这是跨 Feature 共享的业务能力？→ 03-CommonBusiness

2. **输出功能拆分表**（先于详细设计，供用户确认）：

   | PRD 编号 | 功能名称 | 分配模块 | 所属层 | 拆分理由 |
   |----------|----------|----------|--------|----------|
   | F1 | xxx | WalletMain | 02-Feature | 公共页面框架 |
   | F7 | xxx | AccountManager | 04-BusinessBase | 账号状态管理 |
   | — | Toast 工具 | CommUI | 05-SystemBase | 与业务无关的基础UI |

3. **确定需要创建/修改的模块列表**：
   - 哪些模块需要**新建**？（仅创建 PRD 功能实际需要的，不多加）
   - 哪些模块需要**修改**？
   - 验证所有模块间依赖关系是否符合五层架构规则

4. **用户确认后**，进入详细设计。

### Step 4: 设计模块架构

1. **绘制模块架构图**（Mermaid diagram）：展示本次涉及的所有模块及其依赖关系，标注所属层级
2. **规划目录/文件结构**：精确到每个新增 `.ets` 文件的完整路径（各层模块使用对应的内部结构）
3. **确定模块配置变更**：列出需要修改的 `build-profile.json5`、`oh-package.json5`、`module.json5` 等配置文件

### Step 5: 设计数据层

按 data model 模板规范，逐个定义：

1. **数据模型**（`data/model/`）：
   - 定义 `interface` 或 `class`，包含所有字段的名称、类型、说明
   - 标注哪些字段是必填/可选
   - 若模型有内聚方法（如格式化、校验），一并定义方法签名

2. **数据仓库**（`data/repository/`）：
   - 定义 Repository 类及其方法签名
   - 标注数据来源（本地模拟 / API 调用 / AppStorage）
   - 明确每个方法的入参、出参、异步策略

3. **端云接口**（`shared/client/`，如有远程数据需求）：
   - 定义请求体和响应体的 interface
   - 标注接口 URL（模拟数据场景可标注 "模拟"）

### Step 6: 设计领域层

若存在跨 repository 的复杂业务逻辑：

1. **业务用例**（`domain/usecase/`）：
   - 定义 UseCase 函数/类的签名
   - 描述编排逻辑（调用哪些 repository，数据如何流转）
   - 标注异常处理策略

若业务逻辑简单（单 repository 操作），可省略 domain 层，在 presentation 中直接调用 repository。

### Step 7: 设计展示层

1. **页面组件树**：每个页面拆分为哪些自定义组件
   ```
   HomePage (NavDestination)
   ├── CardGuideSection (复杂组件)
   │   ├── CardImageBanner (基础组件)
   │   └── AddCardButton (基础组件)
   ├── ServiceGrid (复杂组件)
   │   └── ServiceGridItem (基础组件)
   └── PromoBanner (复杂组件)
   ```

2. **组件接口定义**：每个自定义组件的 Props（@Prop / @Link / @ObjectLink）和事件回调

3. **状态管理方案**：
   - 页面级状态用 `@State`
   - 父子组件间传递用 `@Prop`（单向）或 `@Link`（双向）
   - 跨页面共享用 `AppStorage` / `LocalStorage`
   - 列表数据用 `@Observed` + `@ObjectLink` 或 `LazyForEach` + `IDataSource`

4. **路由/导航设计**：
   - 页面间跳转关系（基于 Navigation + NavDestination）
   - NavPathStack 的使用方式
   - 路由参数定义

### Step 8: 构建 PRD 功能映射表

逐项映射 PRD 中的每个功能点到具体的技术实现（应与 Step 3 的功能拆分表一致，但更详细）：

| PRD 功能编号 | 功能名称 | 优先级 | 所属层 | 实现模块 | 模块内层级 | 关键文件 | 实现说明 |
|-------------|----------|--------|--------|----------|-----------|----------|----------|
| F1 | Tab导航 | P0 | 02-Feature | WalletMain | presentation | HomePage.ets | Tabs框架 |
| F7 | 账号状态 | P0 | 04-BusinessBase | AccountManager | service | AccountService.ets | 登录状态管理 |

**必须确保**：
- PRD 中每个 P0/P1 功能点都有对应的技术映射行
- 每行的"所属层"和"实现模块"与 Step 3 拆分结果一致
- 跨模块的功能点拆分为多行（一个功能可能涉及多个模块）

### Step 9: 质量门禁自检

生成设计文档后，执行以下自检清单：

```
[ ] 1. PRD 映射完整性：PRD 中每个 P0/P1 功能点是否在映射表中有明确条目？
[ ] 2. 五层架构合规：每个模块是否放在了正确的架构层？依赖方向是否全部自上而下？
[ ] 3. Feature 子层级合规：Feature 层模块间的依赖是否符合 顶层/中间层/底层 规则？
[ ] 4. 模块最小化：是否只创建了 PRD 功能实际需要的模块？没有多余的模块？
[ ] 5. 功能拆分准确性：每个功能点是否放在了最合适的模块？（账号→AccountManager，通用UI→CommUI等）
[ ] 6. 文件路径合规：所有新增文件路径是否符合各层模块对应的内部结构？
[ ] 7. 数据类型合法：数据模型字段类型是否都是 ArkTS 合法类型？
[ ] 8. 接口签名完整：所有函数/方法签名是否包含入参类型和返回类型？
[ ] 9. 无 TBD 项：P0/P1 范围内是否有"待定"、"TBD"、"TODO"等未决项？
[ ] 10. 组件树完整：每个页面是否都有组件拆分方案？
[ ] 11. 状态管理明确：关键数据的状态管理策略是否已明确？
[ ] 12. 路由设计完整：页面间跳转关系是否与 PRD 业务流程图一致？
```

**不通过项**：找出具体缺失点，自动补充完善后重新自检，直到全部通过。

### Step 10: 输出与归档

1. 将设计文档展示给用户确认
2. 用户确认后，将文档保存到项目文档目录：
   ```
   doc/features/{module-name}/design.md
   ```
3. 若用户要求修改，根据反馈调整后重新走 Step 9 自检

### Step 11: 提取功能级 Spec

设计文档归档后，**必须**同步提取功能级接口契约到 `specs/features/{module-name}/` 目录。Spec 是连接生成层和验证层的枢纽，也是 Skill 3（编码）的强契约基准。

#### 11.1 提取接口契约 (`contracts.yaml`)

从 design.md 中提取结构化接口契约，写入 `specs/features/{module-name}/contracts.yaml`：

**`modules` 章节**（从设计文档「模块架构图」和模块变更摘要提取）：

| 字段 | 来源 | 说明 |
|------|------|------|
| `name` | 模块名 | 如 WalletMain、CommUI |
| `layer` | 所属层 | 如 02-Feature、05-SystemBase |
| `format` | HAP/HAR | |
| `change_type` | 变更类型 | new / modify / migrate_and_modify |
| `package_path` | 物理路径 | 如 "02-Feature/WalletMain" |

**`module_dependencies` 章节**（从模块架构图的依赖箭头提取）

**`data_models` 章节**（从设计文档「数据模型定义」提取）：

| 字段       | 来源                       | 说明                       |
| -------- | ------------------------ | ------------------------ |
| `name`   | 模型名                      | 如 CardInfo、UserProfile   |
| `module` | 所属模块                     |                          |
| `file`   | 完整文件路径                   |                          |
| `kind`   | interface / class / enum |                          |
| `fields` | 字段列表                     | 每个字段含 name、type、required |

**`interfaces` 章节**（从设计文档「服务层接口定义」提取）：

| 字段        | 来源     | 说明                                         |
| --------- | ------ | ------------------------------------------ |
| `module`  | 所属模块   |                                            |
| `layer`   | 内部层级   | 如 data/repository、domain/service           |
| `file`    | 完整文件路径 |                                            |
| `class`   | 类名     |                                            |
| `methods` | 方法列表   | 每个方法含 name、params、return、async、description |

**`components` 章节**（从设计文档「页面组件树」和「状态管理方案」提取）：

| 字段 | 来源 | 说明 |
|------|------|------|
| `name` | 组件名 | |
| `module` | 所属模块 | |
| `file` | 完整文件路径 | |
| `kind` | page / component / utility | |
| `state` | @State 变量列表 | |
| `props` | @Prop 变量列表 | |
| `events` | 事件回调列表 | |
| `children` | 子组件列表 | |

**`state_management` 章节**（从「状态管理方案」提取）

**`navigation` 章节**（从「路由/导航设计」提取）

**`files` 章节**（从「目录/文件结构规划」提取完整文件清单）

**`resource_keys` 章节**（从设计文档中涉及的 `$r()` 引用提取资源 key 契约）

**`prd_to_code_traceability` 章节**（从「PRD 功能映射表」提取追溯映射）

#### 11.2 补充边界用例 Spec（若 Skill 1 未产出）

若 `specs/features/{module-name}/acceptance.yaml` 已由 Skill 1 产出，检查并补充设计阶段新增的边界场景（如从技术角度发现的新边界用例）。

若 Skill 1 未产出 `acceptance.yaml`（历史原因），则从 PRD.md 中提取并创建。

#### 11.3 输出文件与参考

```
specs/features/{module-name}/contracts.yaml
```

参考已有示例：`specs/features/home-page/contracts.yaml`

> **为什么这一步如此重要**：`contracts.yaml` 是 Skill 3 编码时的强契约——文件路径、接口签名、组件 Props 必须与 contracts.yaml 一致。Harness 也依赖它做接口一致性验证。

### Step 12: 更新项目架构文档

设计文档和 Spec 归档后，**必须**同步更新 `doc/architecture.md`，确保架构文档始终反映最新状态：

1. **模块总览图**：若新增了模块，在 Mermaid 图中添加节点和依赖箭头
2. **模块清单表**：
   - 新增模块：添加一行，状态改为 `已设计`
   - 已有模块被修改：更新说明列
   - 规划中模块首次被实际设计：状态从 `未创建（规划中）` 改为 `已设计`
3. **各模块公共能力清单**：若本次设计为 CommFunc/CommUI/AccountManager/CommonBusiness 等公共模块新增了能力，添加对应行
4. **功能模块与 PRD/Design 对照表**：更新 Design 列的链接和涉及模块
5. **变更记录**：追加一行，记录日期、变更内容和关联 Skill

> **为什么这一步如此重要**：architecture.md 是后续所有 Skill（编码、Review、UT、测试）了解项目全貌的入口。如果不更新，下一个功能模块的设计将基于过时的信息进行。

### Step 13: Harness 验证门禁

所有产出归档后，引导用户执行验证以确保设计文档质量达标。

#### 13.1 脚本 Harness（确定性检查）

告知用户可运行脚本 Harness 检查设计文档结构合规性：

```bash
cd harness && npx ts-node scripts/check-design.ts --feature={module-name}
```

脚本读取以下 Spec 文件执行自动化检查：
- `specs/phase-rules/design-rules.yaml` — 阶段级通用规则（章节存在性、表格格式、映射覆盖率等）
- `specs/features/{module-name}/contracts.yaml` — 功能级接口契约（文件清单、接口签名）
- `specs/features/{module-name}/acceptance.yaml` — 功能级验收标准（PRD 追溯覆盖率）

**若报告中存在 BLOCKER 级问题**：必须修正设计文档并重新提取 Spec（回到 Step 9），直到零 BLOCKER。

#### 13.2 AI Harness（语义级检查）

告知用户可使用 AI Harness 进行语义级深度验证：

- **Prompt 模板**：`harness/prompts/verify-design.md`
- **使用方式**：将 prompt 中的占位符（`{feature_name}`、`{spec_content}`、`{script_report}`、`{context_files}`）替换为实际内容后，发送给独立 AI 模型执行审查
- **语义检查覆盖项**：
  1. 五层架构合规性（BLOCKER）
  2. 模块内四层合规性（BLOCKER）
  3. 模块最小性
  4. 功能拆分合理性
  5. 数据类型合法性（BLOCKER）
  6. P0/P1 无未决项（BLOCKER）
  7. 架构文档一致性
  8. 导航流程一致性
  9. 验收标准到接口追溯

**若 AI 报告中存在 BLOCKER 级 FAIL**：修正后重新验证。

#### 13.3 验证完成标志

| 验证层 | 通过条件 |
|--------|---------|
| 脚本 Harness | 零 BLOCKER |
| AI Harness | verdict = PASS（无 BLOCKER 级 FAIL） |

验证全部通过后，设计阶段完成，可进入 Skill 3（编码）。

## 输出规范

### 文件路径

| 产出 | 路径 |
|------|------|
| 设计文档 | `doc/features/{module-name}/design.md` |
| 接口契约 Spec | `specs/features/{module-name}/contracts.yaml` |

### 文档结构

设计文档**必须包含以下 8 个章节**（读取模板以获取详细格式）：

```
skills/2-requirement-design/templates/design-template.md
```

1. **模块架构图** — Mermaid diagram，展示模块间依赖关系
2. **目录/文件结构规划** — 精确到每个新增的 `.ets` 文件路径及其职责说明
3. **数据模型定义** — interface/class 定义，含字段类型和说明
4. **页面组件树** — 每个页面拆分为哪些自定义组件，含层级关系
5. **状态管理方案** — 各装饰器的使用策略和数据流向
6. **服务层接口定义** — Repository / UseCase / Client 的函数签名
7. **路由/导航设计** — 页面间跳转关系和参数传递
8. **PRD 功能映射表** — 每个 PRD 功能点到技术实现的逐项映射

### 文档格式
- 使用 Markdown 格式
- 架构图使用 Mermaid 语法
- 数据模型使用 TypeScript/ArkTS 代码块
- 接口定义使用代码块 + 表格补充说明
- 组件树使用树形文本图

### 辅助模板

数据模型和接口规范可参考以下模板：
- 数据模型模板: [templates/data-model.md](templates/data-model.md)
- 接口规范模板: [templates/api-spec.md](templates/api-spec.md)

## 设计决策原则

在遇到需要权衡的技术决策时，遵循以下原则：

1. **简单优先**：本项目为模拟应用，优先选择简单直接的方案，避免过度设计
2. **分层清晰**：宁可多一个文件，也不要在错误的层级放置代码
3. **模拟数据**：涉及真实后端（支付网关、银行接口等）的部分，在 client 层定义接口，由 repository 用本地模拟数据实现
4. **复用优先**：已有的公共组件/工具优先复用，不重复造轮子
5. **渐进式设计**：P0 功能必须设计完整，P2/P3 功能可标注为"预留扩展点"
6. **可编译导向**：设计方案必须是可直接编码实现的，不含无法落地的抽象描述

## 关联文件

- **项目架构文档**: [doc/architecture.md](../../doc/architecture.md)（必读 + 必更新）
- 设计文档模板: [templates/design-template.md](templates/design-template.md)
- 接口规范模板: [templates/api-spec.md](templates/api-spec.md)
- 数据模型模板: [templates/data-model.md](templates/data-model.md)
- 示例设计文档: [examples/example-design.md](examples/example-design.md)
- 阶段级规约: `specs/phase-rules/design-rules.yaml`
- 功能级 Spec 示例: `specs/features/home-page/contracts.yaml`
- 脚本 Harness: `harness/scripts/check-design.ts`
- AI Harness Prompt: `harness/prompts/verify-design.md`

## 上游与下游

- **上游输入**:
  - `doc/features/{module}/PRD.md`（Skill 1 输出）
  - `specs/features/{module}/acceptance.yaml`（Skill 1 产出的验收标准 Spec）
  - `doc/architecture.md`（项目架构全貌，跨 Skill 共享）
- **下游消费者**:

| 消费者 | 消费的产出 | 用途 |
|--------|-----------|------|
| **Skill 3 (编码)** | design.md + contracts.yaml | 按文件规划和接口契约逐模块生成代码 |
| **Skill 4 (Code Review)** | design.md + contracts.yaml | 对照检查实现一致性 |
| **Skill 5 (业务级 UT)** | design.md + contracts.yaml | 读取业务流程信息生成 DAG |
| **Harness (验证层)** | contracts.yaml | 脚本/AI 验证代码接口一致性和文件完整性 |

## 约束与注意事项

1. **PRD 是唯一的需求来源**：不得自行添加 PRD 中未提及的功能，若发现 PRD 缺失重要场景，应标注并建议用户回到 Skill 1 补充
2. **严格遵循分层架构**：design.md 中规划的每个文件必须落在正确的层级目录，设计阶段就要杜绝分层违规
3. **鸿蒙生态适配**：组件设计优先使用 ArkUI 原生组件（Column、Row、List、Tabs、Navigation、Swiper 等），避免自造轮子
4. **ArkTS 类型系统**：数据模型字段类型必须是 ArkTS 合法类型（string、number、boolean、Resource、Array 等），不得使用 any
5. **设计即契约**：design.md 中的接口签名、文件路径、组件 Props 定义将作为 Skill 3 编码的强契约，务必精确
6. **Spec 必须同步产出**：设计文档归档后必须提取 `contracts.yaml`（Step 11），这是下游编码和 Harness 验证的基准。contracts.yaml 的精确度直接影响编码质量和自动化验证的有效性
7. **中文输出**：所有设计文档内容使用简体中文
8. **模块最小化**：只创建 PRD 功能实际需要的模块，不额外新增。一个 PRD 的功能通常会跨多个已有模块（如 Feature + AccountManager + CommUI），但不意味着要为每个功能创建新模块
9. **跨模块拆分是核心能力**：Skill 2 的核心价值之一是将 PRD 中的功能点准确拆分到五层架构的正确模块中，确保职责单一、依赖合规
10. **Harness 验证闭环**：设计完成后必须引导用户运行 Harness 验证（Step 13），确保零 BLOCKER 后才进入编码阶段
