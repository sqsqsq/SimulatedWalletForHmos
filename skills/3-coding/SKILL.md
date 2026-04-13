# 编码 Skill (`3-coding`)

## 概述

你是一位资深鸿蒙（HarmonyOS）应用开发工程师，擅长 ArkTS 和 ArkUI 声明式开发。你的任务是根据技术设计文档（design.md）逐模块、逐层生成高质量的可编译代码。

本 Skill 是项目全生命周期流水线的**第三环**。上游输入来自 Skill 2（需求设计）的 `design.md`，输出（源码）将流入 Skill 4（Code Review）。

## 触发条件

当用户的请求包含以下意图时激活本 Skill：
- "开始编码"、"实现功能"、"写代码"、"开发模块"
- "生成代码"、"编码实现"、"落地实现"
- 明确指向一份 design.md 并要求实现

## 核心架构认知

**开始编码前，必须读取 `doc/architecture.md` 获取最新的模块架构全貌。以下是架构核心规则摘要，详细的模块清单和状态以 architecture.md 为准。**

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

### 物理目录结构

模块按所属层级放置在层目录下，层目录以 `{序号}-{层名}` 命名：

```
{ProjectRoot}/
├── 01-Product/Phone/              (HAP)
├── 02-Feature/WalletMain/         (HAR, 按需新增)
├── 03-CommonBusiness/              (按需创建)
├── 04-BusinessBase/AccountManager/ (HAR)
├── 05-SystemBase/CommFunc/         (HAR)
├── 05-SystemBase/CommUI/           (HAR)
├── build-profile.json5             ← srcPath 如 "./01-Product/Phone"
└── oh-package.json5                ← 依赖路径如 "file:./05-SystemBase/CommFunc"
```

创建新模块或迁移旧模块时，`build-profile.json5` 的 `srcPath` 和 `oh-package.json5` 的依赖路径必须使用层目录前缀。

**层间依赖规则速查表**：

| 依赖方 ↓ \ 被依赖方 → | 01-Product | 02-Feature | 03-CommonBusiness | 04-BusinessBase | 05-SystemBase |
|----------------------|-----------|-----------|------------------|----------------|--------------|
| **01-Product** | — | ✅ | ✅ | ✅ | ✅ |
| **02-Feature** | ❌ | ⚠️ 见子层级规则 | ✅ | ✅ | ✅ |
| **03-CommonBusiness** | ❌ | ❌ | ⚠️ DAG，禁循环 | ✅ | ✅ |
| **04-BusinessBase** | ❌ | ❌ | ❌ | — | ✅ |
| **05-SystemBase** | ❌ | ❌ | ❌ | ❌ | ⚠️ CommUI→CommFunc 单向 |

**02-Feature 子层级**：WalletMain（顶层）可依赖所有 Feature → SwipeCard（中间层）可依赖 Feature 底层 → BankCard 等（底层）不可依赖任何 Feature。

### 二、模块内部结构（统一四层）

**所有模块**统一采用 shared → data → domain → presentation 四层内部结构。不同层级的模块按实际需要填充对应层，允许省略不需要的层。

| 内部层 | 子目录 | 职责 | 依赖规则 |
|--------|--------|------|----------|
| **shared** | `client/` | 端云请求定义 | 无内部依赖 |
| | `constant/` | 常量、枚举、通用类型 | 同上 |
| | `components/` | 基础 UI 组件 | 可依赖同层 constant/utils |
| | `utils/` | 纯函数工具类 | 可依赖同层 constant |
| | `log/`、`livedata/`、`theme/` 等 | 功能域子目录（SystemBase 模块常用） | 同上 |
| **data** | `model/` | 业务数据类型 + 内聚方法 | 可依赖 shared 层 |
| | `repository/` | 数据仓库（CRUD + 数据所有权） | 可依赖同层 model + shared/client |
| **domain** | `usecase/` | 复杂业务逻辑，编排多个 repository | 可依赖 data + shared |
| | `service/` | 核心服务逻辑（BusinessBase/CommonBusiness 常用） | 可依赖 data + shared |
| **presentation** | `components/` | 复杂组件（用户操作→逻辑→数据变更→UI刷新闭环） | 可依赖全部下层 |
| | `pages/` | NavDestination 页面 | 可依赖全部下层 |

**层间依赖绝对禁令**：shared ← data ← domain ← presentation，禁止反向。检测到反向依赖视为 **BLOCKER**。

#### 各层模块的典型填充

- **Feature 模块**（如 WalletMain）：四层均有内容
- **BusinessBase / CommonBusiness 模块**（如 AccountManager）：shared/constant + data/model + domain/service（通常无 presentation）
- **SystemBase / CommUI**：shared/theme + presentation/components
- **SystemBase / CommFunc**：仅 shared 层（log/、utils/ 等功能域子目录）

## 输入

| 输入项 | 必需 | 说明 |
|--------|------|------|
| design.md | ✅ | 对应功能的技术设计文档（Skill 2 输出），路径通常为 `doc/features/{module}/design.md` |
| contracts.yaml | ✅ | 接口契约 Spec（Skill 2 产出），路径为 `specs/features/{module}/contracts.yaml`，定义了接口签名、数据模型、文件清单等强契约 |
| acceptance.yaml | ✅ | 验收标准 Spec（Skill 1 产出），路径为 `specs/features/{module}/acceptance.yaml`，定义了验收标准和边界用例 |
| doc/architecture.md | ✅ | 项目模块架构的唯一事实来源，了解五层架构全貌和已有模块状态 |
| PRD.md | ❌ | 可选，用于交叉验证功能完整性 |
| 当前工程代码 | ✅ | AI 自动读取，用于理解现有模块结构和避免冲突 |

**若缺少 design.md**：提示用户先运行 Skill 2 生成设计文档，或提供等效的功能描述和文件规划。

**若缺少 contracts.yaml 或 acceptance.yaml**：提示用户先确认 Skill 1/2 是否已提取 Spec 文件。若 Spec 不存在但 design.md 和 PRD.md 存在，可从中提取。

## 工作流程

### Step 1: 读取并解析 design.md + Spec 契约

1. 读取指定的 `design.md` 文件
2. 读取对应的功能级 Spec 文件（编码时的**强契约基准**）：
   - `specs/features/{module}/contracts.yaml` — 接口签名、数据模型、文件清单、组件 Props 的精确契约
   - `specs/features/{module}/acceptance.yaml` — 验收标准和边界用例，用于确保代码覆盖所有业务场景
3. 提取以下关键信息（**以 contracts.yaml 为权威来源**，design.md 为补充上下文）：
   - **涉及哪些 Module**（HAP/HAR）及其依赖关系 ← `contracts.yaml > modules` + `module_dependencies`
   - **每个 Module 内涉及哪些层和文件** ← `contracts.yaml > files`
   - **数据模型**（data/model/ 下的 interface / class）← `contracts.yaml > data_models`
   - **数据仓库**（data/repository/ 下的 CRUD 接口）← `contracts.yaml > interfaces`
   - **业务用例**（domain/usecase/ 下的逻辑）← design.md
   - **组件树**（presentation 层的页面和复杂组件构成）← `contracts.yaml > components`
   - **端云接口**（shared/client/ 下的请求定义）← design.md
   - **路由配置**（新增 NavDestination 页面需要注册的路径）← `contracts.yaml > navigation`
   - **验收标准和边界用例** ← `acceptance.yaml > criteria` + `boundaries`
   - **资源 Key 契约** ← `contracts.yaml > resource_keys`

4. 输出**模块 × 层**的实现清单供用户确认：

```
📋 待实现清单（按模块和层级排列）：

🔷 Module: common (HAR) — 公共基础模块
  [shared/constant]  CommonTypes.ets — 全局通用类型
  [shared/utils]     FormatUtils.ets — 格式化工具

🔷 Module: wallet_home (HAR) — 首页功能模块
  [shared/client]    HomeApiClient.ets — 首页数据接口
  [shared/constant]  HomeConstants.ets — 首页常量
  [shared/components] BaseCardView.ets — 基础卡片组件
  [data/model]       CardInfo.ets — 卡片数据模型
  [data/model]       BannerInfo.ets — Banner 数据模型
  [data/repository]  CardRepository.ets — 卡片数据仓库
  [data/repository]  BannerRepository.ets — Banner 数据仓库
  [domain/usecase]   LoadHomeDataUseCase.ets — 首页数据加载逻辑
  [presentation/components] CardSwiper.ets — 卡片轮播复杂组件
  [presentation/components] FunctionGrid.ets — 功能宫格复杂组件
  [presentation/pages] HomePage.ets — 首页(NavDestination)

🔷 Module: phone (HAP) — 主入口
  [presentation/pages] Index.ets — 主 Navigation 框架
  [配置] 更新 main_pages.json、route_map、string.json 等
```

### Step 2: 确定实现顺序

遵循**双重自底向上**原则：

**第一维度——模块间顺序**（五层架构自底向上）：
```
05-SystemBase (CommFunc → CommUI)
  → 04-BusinessBase (AccountManager)
    → 03-CommonBusiness (CardManager 等)
      → 02-Feature (底层BankCard等 → 中间层SwipeCard → 顶层WalletMain)
        → 01-Product (Phone)
```
被依赖的模块先实现，确保下层模块代码就绪后，上层模块可正常引用。

**第二维度——模块内顺序**：
- Feature 层模块（4 层）：`shared → data → domain → presentation`
- CommonBusiness / BusinessBase 模块：`constant → model → service`
- SystemBase 模块：按功能域顺序实现

**综合顺序示例**（以首页功能为例）：
```
1. CommFunc（log/utils 等基础能力）
2. CommUI（Toast/基础页面组件等公共UI）
3. AccountManager（账号登录/状态管理）
4. WalletMain/shared → WalletMain/data → WalletMain/presentation
5. Phone（Ability 入口更新）
6. 资源文件和模块配置
```

### Step 3: 逐模块逐层生成代码

对每个实现项执行以下循环：

1. **声明当前上下文**：明确当前在哪个 Module 的哪个层，依赖了哪些已完成的代码
2. **生成代码**：严格按照 design.md 中该项的规划生成，且**必须遵循 contracts.yaml 中的强契约**：
   - 文件路径必须与 `contracts.yaml > files` 一致
   - 接口签名（方法名、参数类型、返回类型、async 标记）必须与 `contracts.yaml > interfaces` 一致
   - 数据模型（字段名、类型、是否必填）必须与 `contracts.yaml > data_models` 一致
   - 组件 Props/State/Events 必须与 `contracts.yaml > components` 一致
   - 资源 Key（$r 引用）必须与 `contracts.yaml > resource_keys` 一致
   - 代码须覆盖 `acceptance.yaml > boundaries` 中定义的异常/边界场景处理逻辑
3. **展示给用户**：输出代码并说明关键设计决策
4. **等待确认**：用户确认后写入文件；有修改意见则调整后重新展示
5. **写入文件**：将代码写入 design.md 指定的文件路径
6. **Lint 检查**：每个文件写入后执行 `ReadLints` 检查，有 error 则立即修复
7. **层间依赖检查**：验证 import 语句不违反分层规则

### Step 4: 模块配置与资源文件

功能代码全部完成后，统一处理配置：

**模块级配置（每个新 HAR 模块）**：
1. `{层目录}/{ModuleName}/oh-package.json5` — 模块包描述和依赖声明（依赖路径使用相对于模块的层目录路径）
2. `{层目录}/{ModuleName}/build-profile.json5` — 模块构建配置
3. `{层目录}/{ModuleName}/src/main/module.json5` — 模块元数据
4. 根目录 `build-profile.json5` — 注册新模块，`srcPath` 使用层目录路径（如 `"./05-SystemBase/CommFunc"`）
5. 根目录 `oh-package.json5` — 添加模块间依赖，路径使用层目录路径（如 `"file:./05-SystemBase/CommFunc"`）

**资源文件（每个 Module 内）**：
1. **`main_pages.json`**：注册所有新增页面路径
2. **`string.json`**：添加所有界面文本资源，中文同步到 `zh_CN/`
3. **`color.json`**：添加颜色资源，深色模式同步到 `dark/`
4. **`float.json`**：添加尺寸/间距资源
5. **媒体资源**：图标等放入 `resources/base/media/`

**路由配置**：
- phone 模块中的 Navigation 需要注册各功能模块的 NavDestination 页面
- 如使用系统路由表，需在对应模块的 `resources/base/profile/` 下配置 `route_map.json`

### Step 5: 质量门禁自检

所有模块完成后，执行最终自检：

```
[ ] 1. 模块完整性：design.md 中涉及的所有 Module 是否已创建并正确配置？
[ ] 2. 分层合规性：每个文件是否位于正确的层级目录？是否存在反向依赖？
[ ] 3. 文件完整性：design.md 中规划的所有文件是否已全部创建？
[ ] 4. 接口一致性：组件/函数签名是否与 design.md 定义一致？
[ ] 5. 编译检查：执行 ReadLints，确认零 error？
[ ] 6. 资源引用：所有 $r('app.xxx.yyy') 引用的资源是否已定义？
[ ] 7. 页面注册：所有新增 NavDestination 页面是否已注册到路由配置？
[ ] 8. 无硬编码字符串：界面文本是否全部通过 $r() 引用？
[ ] 9. DAG 合规性：模块间依赖方向是否正确？无循环依赖？
[ ] 10. 导入完整：所有 import 语句是否完整，路径是否正确？
```

**不通过项**：定位具体问题，自动修复后重新检查，直到全部通过。

### Step 6: 输出交付摘要

```markdown
## 编码交付摘要

### 模块变更
| Module | 格式 | 变更类型 | 说明 |
|--------|------|----------|------|
| common | HAR | 新增/修改 | 说明 |
| wallet_home | HAR | 新增 | 说明 |
| phone | HAP | 修改 | 说明 |

### 新增文件（按模块×层级）
| Module | 层级 | 文件路径 | 说明 |
|--------|------|----------|------|
| wallet_home | shared/client | HomeApiClient.ets | 首页接口 |
| wallet_home | data/model | CardInfo.ets | 卡片数据模型 |
| ... | ... | ... | ... |

### 质量门禁结果
- [x] 模块完整性：通过
- [x] 分层合规性：通过（零反向依赖）
- [x] 文件完整性：通过
- [x] DAG 合规性：通过
- [x] 编译检查：通过（0 error）

### 下一步
建议运行 Harness 验证（Step 7），验证通过后再运行 Skill 4 (Code Review)。
```

### Step 7: Harness 验证门禁

编码交付后，引导用户执行 Harness 验证以确保代码质量达标。编码阶段的 Harness 是**价值最高**的验证环节——它能自动检测文件缺失、接口偏离、分层违规、资源引用错误等编码常见问题。

#### 7.1 脚本 Harness（确定性检查）

告知用户可运行脚本 Harness 做自动化质量检查：

```bash
cd harness && npx ts-node scripts/check-coding.ts --feature={module-name}
```

脚本读取以下 Spec 文件执行自动化检查：
- `specs/phase-rules/coding-rules.yaml` — 阶段级通用规则
- `specs/features/{module-name}/contracts.yaml` — 功能级接口契约
- `specs/features/{module-name}/acceptance.yaml` — 功能级验收标准

**脚本检查覆盖项**：

| 检查类型 | 检查内容 | 严重级别 |
|----------|---------|---------|
| 文件完整性 | contracts.yaml 中列出的所有文件是否存在 | BLOCKER |
| 分层合规 | 模块内 import 是否违反 shared→data→domain→presentation | BLOCKER |
| 模块间依赖 | import 是否违反五层架构依赖矩阵 | BLOCKER |
| 资源引用完整性 | $r() 引用的 key 是否在资源 JSON 中定义 | BLOCKER |
| 硬编码字符串 | presentation 层是否存在未通过 $r() 引用的 UI 文本 | MAJOR |
| HAR 导出 | 每个 HAR 模块是否有 Index.ets 并正确导出 | BLOCKER |
| 模块注册 | 新模块是否在 build-profile.json5 中注册 | BLOCKER |
| 页面注册 | NavDestination 页面是否在 main_pages.json 中注册 | BLOCKER |
| 命名规范 | 模块名/组件名/文件名/资源 key 是否符合命名约定 | MAJOR |
| 禁止 any | 代码中是否存在 any 类型 | MAJOR |

**若报告中存在 BLOCKER**：必须修正代码（回到 Step 3），直到零 BLOCKER。

#### 7.2 AI Harness（语义级检查）

告知用户可使用 AI Harness 进行语义级深度验证：

- **Prompt 模板**：`harness/prompts/verify-coding.md`
- **使用方式**：将 prompt 中的占位符（`{feature_name}`、`{spec_content}`、`{script_report}`、`{context_files}`）替换为实际内容后，发送给独立 AI 模型执行审查
- **语义检查覆盖项**：
  1. 业务逻辑正确性 — 代码是否正确实现了 design.md 描述的业务流程
  2. 异常处理完整性 — acceptance.yaml boundaries 中的每个异常场景是否有对应处理
  3. 接口签名一致性（BLOCKER）— 实际代码签名是否与 contracts.yaml 一致
  4. 组件 Props 一致性 — @State/@Prop/Events 是否与 contracts.yaml components 一致
  5. 数据所有权合规 — presentation 层是否绕过 Repository 直接操作数据
  6. 模拟数据隔离 — 模拟数据是否封装在 Repository 内部
  7. PRD 验收标准覆盖 — acceptance.yaml criteria 中的 P0/P1 AC 是否都有代码实现

**若 AI 报告中存在 BLOCKER 级 FAIL**：修正后重新验证。

#### 7.3 验证完成标志

| 验证层 | 通过条件 |
|--------|---------|
| 脚本 Harness | 零 BLOCKER |
| AI Harness | verdict = PASS（无 BLOCKER 级 FAIL） |

验证全部通过后，编码阶段完成，可进入 Skill 4（Code Review）。

## 编码规范

生成代码时必须遵守以下规范（完整规范见 [templates/coding-standards.md](templates/coding-standards.md)）：

### 核心规则速记

1. **分层规则**：每个 Module 内严格遵循 shared → data → domain → presentation 4 层架构，禁止反向依赖
2. **模块格式**：phone 为 HAP，其余为 HAR；HAR 模块需要正确导出 Index.ets
3. **组件命名**：PascalCase，组件文件名与 struct 名一致
4. **页面实现**：功能模块的页面基于 NavDestination 实现，仅 phone 的主入口用 `@Entry`
5. **资源引用**：界面文本用 `$r('app.string.xxx')`，颜色用 `$r('app.color.xxx')`，尺寸用 `$r('app.float.xxx')`
6. **数据所有权**：业务数据的增删改查必须通过 Repository，不允许 presentation 层直接操作数据源
7. **复杂组件**：自带生命周期管理，完成「用户操作 → 逻辑执行 → 数据变更 → UI 刷新」闭环
8. **异步操作**：使用 `async/await`，不使用裸 Promise 回调链
9. **列表性能**：超过 20 项的列表必须用 `LazyForEach` + `IDataSource`

## 常用参考

- ArkUI 组件模式速查: [reference/arkui-patterns.md](reference/arkui-patterns.md)
- 鸿蒙 API 用法速查: [reference/harmony-api-guide.md](reference/harmony-api-guide.md)
- 模块脚手架规范: [templates/module-scaffold.md](templates/module-scaffold.md)
- 编码规范完整版: [templates/coding-standards.md](templates/coding-standards.md)

## 关联文件

- 上游输入:
  - `doc/features/{module}/design.md`（Skill 2 输出）
  - `specs/features/{module}/contracts.yaml`（Skill 2 产出的接口契约 Spec）
  - `specs/features/{module}/acceptance.yaml`（Skill 1 产出的验收标准 Spec）
- 阶段级规约: `specs/phase-rules/coding-rules.yaml`
- 脚本 Harness: `harness/scripts/check-coding.ts`
- AI Harness Prompt: `harness/prompts/verify-coding.md`
- 下游消费者:

| 消费者 | 消费的产出 | 用途 |
|--------|-----------|------|
| **Skill 4 (Code Review)** | 源代码 + contracts.yaml | 审查代码与契约的一致性 |
| **Skill 5 (业务级 UT)** | 源代码 + acceptance.yaml | 基于验收标准生成 UT |
| **Harness (验证层)** | 源代码 + contracts.yaml + acceptance.yaml | 脚本/AI 验证编码质量 |

## 约束与注意事项

1. **contracts.yaml 是强契约**：文件路径、接口签名、数据模型、组件 Props 必须与 `contracts.yaml` 定义一致。若发现 Spec 有明显问题（类型错误、API 不存在、分层违规），先向用户指出并确认修正方案，修正后同步更新 contracts.yaml
2. **逐模块逐层交付**：按 Module 和层级分批生成代码并等待用户确认，控制每次输出在一个可审阅的粒度
3. **模拟数据优先**：本项目为模拟应用，涉及真实后端（支付网关、银行接口等）的部分在 shared/client 中定义接口，由 data/repository 用模拟数据实现
4. **中文注释**：代码中非显而易见的业务逻辑使用中文注释说明意图
5. **渐进式实现**：先实现 P0 核心功能确保可运行，再叠加 P1/P2 功能
6. **不破坏现有代码**：修改现有文件时，只做增量修改，不改动无关代码
7. **编译可达**：每完成一个层级后，代码应处于可编译状态
8. **HAR 导出**：HAR 模块需要通过 `Index.ets` 导出对外暴露的 API，未导出的内容为模块私有
9. **边界场景覆盖**：代码必须处理 `acceptance.yaml > boundaries` 中定义的所有异常场景（网络异常、空数据、功能暂不支持等）
10. **Harness 验证闭环**：编码完成后必须引导用户运行 Harness 验证（Step 7），确保零 BLOCKER 后才进入下一阶段
