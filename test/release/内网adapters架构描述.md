# 内网 adapters 架构描述

本文描述内网业务仓 Story Extension 的 adapters 层架构：分层结构、调用关系图、各文件的开放接口（输入/输出）。不含内部实现细节。

## 一、分层结构

```
┌─────────────────────────────────────────────┐
│              story.js（入口层）               │
│  参数解析 → 校验 → 分发到命令实现层            │
└───────┬───────┬───────┬───────┬─────────────┘
        │       │       │       │
        ▼       ▼       ▼       ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ fetch.js │ │archive.js│ │restore.js│ │ review.js │
│ (init)   │ │(archive) │ │(restore) │ │(review)  │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │
     │      ┌─────┘            │            │
     ▼      ▼                  ▼            ▼
┌──────────────────────────────────────────────┐
│              mcp.js（数据通信层）              │
│  封装需求系统 MCP 端点的 HTTP 调用             │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│                    公共工具层                          │
│ dirs.js  token.js  post-process.js  html-to-md.js     │
│ download-images.js  image-map.js  siblings.js         │
│ system-ca-bootstrap.js                                │
└──────────────────────────────────────────────────────┘
```

### 入口层

**story.js** — 唯一 CLI 入口。解析参数、校验单号和 token、分发到命令实现层。

### 命令实现层

每条命令一个文件，由 story.js require 后调用。各文件导出一个 async 函数。

- **fetch.js** — init 命令。首次拉取 AR/SR/RR 三级单据的详情与正文。
- **archive.js** — archive 命令。选正文上传到需求系统，上传 review.md 附件。
- **restore.js** — restore 命令。从备份恢复系统正文。
- **review.js** — review 命令。拉取 review.md 附件写入本地。

### 数据通信层

**mcp.js** — 封装需求系统 MCP 端点的 HTTP 调用。所有命令实现层文件通过它访问需求系统。

### 公共工具层

- **dirs.js** — 目录路径常量与路径函数，所有命令共用。
- **token.js** — 从配置文件探测 MCP token，stdout 输出纯文本。
- **post-process.js** — 后处理编排（HTML 转 Markdown + 图片下载），init 和 review 命令拉取后调。
- **html-to-md.js** — 富文本 HTML 转 Markdown，被 post-process 调。
- **download-images.js** — 在线图片下载与路径替换，被 post-process 调。
- **image-map.js** — 图片本地路径与云端 URL 映射表，download-images 写、archive 读。
- **siblings.js** — 查询同 SR 下的子 AR 列表，fetch.js 的 SR 分支调。
- **system-ca-bootstrap.js** — 系统证书库引导，每个脚本第一行 require。

## 二、调用关系图

```
story.js
  ├─→ fetch.js ──→ mcp.js
  │                ├─→ dirs.js
  │                └─→ siblings.js ──→ mcp.js
  ├─→ archive.js ─→ mcp.js
  │                ├─→ dirs.js
  │                └─→ image-map.js
  ├─→ restore.js ─→ archive.js ──→ mcp.js
  │                                ├─→ dirs.js
  │                                └─→ image-map.js
  │              └─→ dirs.js
  ├─→ review.js ──→ mcp.js
  │                ├─→ dirs.js
  │                └─→ post-process.js
  ├─→ dirs.js
  └─→ post-process.js
       ├─→ html-to-md.js
       └─→ download-images.js
            └─→ image-map.js

system-ca-bootstrap.js ← 每个脚本第一行 require
```

### 共用关系

| 被共用文件 | 共用方 |
|---|---|
| mcp.js | fetch.js、archive.js、siblings.js |
| dirs.js | fetch.js、archive.js、restore.js、story.js |
| image-map.js | download-images.js（写映射）、archive.js（读映射还原） |
| post-process.js | story.js（init 分支）、review.js |
| system-ca-bootstrap.js | 所有脚本 |

## 三、各文件的开放接口

### story.js（入口，不导出函数，被 CLI 直接调用）

**输入（命令行参数）**：
- args[0]：mode — init / archive / restore / review
- args[1]：reqNo — 需求单号，必须 AR 开头
- args[2]：mcpToken — MCP 访问令牌

**输出（stdout 末行 JSON）**：
- 成功：{ mode, reqNo, success: true, ...各命令特有字段 }
  - init 额外含：parentNo（SR 号）、rrNo（RR 号）、htmlConverted、imagesDownloaded
  - archive 额外含：archived、backupPath、verified、reviewArchived
  - restore 额外含：restored、verified
  - review 额外含：reviewed、length、imagesDownloaded
- 失败：{ mode, reqNo, success: false, error }
- 人类可读日志走 stderr

**校验**：
- 缺 mode / reqNo / mcpToken → console.error + exit(1)，不写 stdout JSON
- reqNo 非 AR 开头 → console.error + exit(1)，不写 stdout JSON
- 命令实现抛异常 → 顶层 catch 写 stdout JSON + exit(1)

### fetch.js

**导出**：fetchOne(reqNo, dirType, mcpToken, backupTimestamp, baseReqNo?)

**输入**：
- reqNo：单号
- dirType：'AR' / 'SR' / 'RR'
- mcpToken：MCP 令牌
- backupTimestamp：时间戳字符串（用于本地备份目录名）
- baseReqNo：可选，AR 单号（SR/RR 拉取时指定，子目录挂在 AR 下）

**输出（返回值）**：
- { parentNo: string | null } — 父需求号，供 story.js 决定是否递归拉取

**写盘**：
- features/单号/AR|SR|RR/ 目录下：detail.json、design.md（AR/SR）、prd.md（RR）、template.md（AR/SR）

**调用**：mcp.js、dirs.js、siblings.js

### archive.js

**导出**：archiveOne(reqNo, mcpToken, skipBackup?, contentOverride?)

**输入**：
- reqNo：AR 单号
- mcpToken：MCP 令牌
- skipBackup：可选，默认 false。true 时跳过备份（restore 模式用）
- contentOverride：可选，直接指定上传内容，跳过文件选择（restore 模式用）

**输出（返回值）**：
- { archived: true, backupPath: string, verified: boolean, reviewArchived: boolean }

**写盘**：
- 工作区文件不动（临时替换 design.md 的逻辑在内部处理）
- 备份写入 .backups/cloud/ 目录

**调用**：mcp.js、dirs.js、image-map.js

### restore.js

**导出**：restoreOne(reqNo, mcpToken)

**输入**：
- reqNo：AR 单号
- mcpToken：MCP 令牌

**输出（返回值）**：
- { restored: true, verified: boolean }
- 无备份时抛异常

**写盘**：
- 本地文件不动（通过调 archiveOne 的 contentOverride 路径上传，不选本地文件）

**调用**：archive.js、dirs.js

### review.js

**导出**：reviewOne(reqNo, mcpToken)

**输入**：
- reqNo：AR 单号
- mcpToken：MCP 令牌

**输出（返回值）**：
- { reviewed: true, length: number, imagesDownloaded: number }

**写盘**：
- AR/review.md（拉取前备份已有到 .review-backup）

**调用**：mcp.js、dirs.js、post-process.js

### mcp.js

**导出**：callMcp(url, method, params, mcpToken) — async 函数，返回 MCP 响应对象，内置一次重试。另导出两个 MCP 端点 URL 常量。

## 四、core 与 adapters 的调用关系

core（Python 层的 story_flow.py）不直接调 adapters。它渲染命令文本给模型执行，再读 adapters 写的回执文件。

- core 渲染 fetch 命令文本，模型拿到后替换 token 占位符并执行
- core 读 AR/story-src/fetched.json 回执文件获取取材结果，不解析 stdout
- core 用 local[-_] 前缀判断本地单，不渲染 fetch 命令；adapters 的 AR 前缀检查是第二道防线

## 五、对 Demo adapters 改造的建议

基于内网架构描述，Demo 当前实现与内网的主要差异及改造重点：

1. **一命令一文件** — Demo 当前是单文件 400 行，内网是一个命令一个文件。Demo 应拆分为 story.js（入口分发）+ 各命令实现文件 + 公共工具文件。

2. **数据获取逻辑提取为公共函数并导出** — Demo 当前 init 和 fetch 的取数据逻辑各写一遍。内网从 fetch.js 导出公共函数，fetch 命令的实现 import 复用。Demo 拆文件时应把取数据逻辑提取成导出函数。

3. **路径计算收敛在公共工具文件** — Demo 在 story.js 里读 framework.config.json 计算 features 目录。内网所有命令用 dirs.js 的 FEATURES_DIR 常量拼路径，story.js 不读 config。Demo 应把路径计算移到 dirs.js。

4. **错误处理统一为两层** — Demo 用 fail() 函数同时写 stderr 和 stdout JSON。内网是命令分支 console.error+exit（不写 stdout JSON），顶层 catch 统一写 stdout JSON。Demo 应去掉 fail() 的 stdout JSON 输出。

5. **用 async main() + 顶层 catch** — Demo 当前同步调用无 catch。内网用 async main() + .catch() 兜底。Demo 应包裹 async main + catch。

6. **参数解析简化** — Demo 用 20 行循环支持等号格式。内网直接位置取值 + 简单查找。Demo 应简化为不支持等号格式。

7. **替身目录不出现在分发层** — Demo 把 system 参数从 story.js 传给所有命令。内网的替身/MCP 调用是命令实现文件内部细节，不出现在 story.js 的分发接口里。