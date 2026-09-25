# `scripts/` 的两层：谁写的，谁维护

这一层不放独立文件，只有两个目录。**一个文件归谁，看它在哪个目录**——不看后缀、不看文件头自述、不靠任何推断。

| 目录 | 归谁 | 升级时 |
|---|---|---|
| `core/` | 包（本扩展） | 整份换掉，包里没有的删掉 |
| `adapters/` | **目标仓自己实现** | 一个字节不碰 |

新增的公共脚本一律进 `core/`。往 `scripts/` 根下放文件会被 `adapt-scan --check ⑧` 拦下：放在那里的两边都不认，永远升级不到目标手里。

## `adapters/` 的分层、公共入口及其合同

对接层的文件划分与内网实现同名同职责，接口签名一致，跟版时逐文件对照即可。本仓的实现是**替身**（本地目录模拟需求系统，只承载 md），部署环境各自实现，从不调用扩展内容。模型按 SKILL 调用入口，core 不调用入口、也不生成入口命令，只读入口约定落盘的材料与回执。

| 文件 | 层 | 职责与导出 |
|---|---|---|
| `story.js` | 入口 | 解析参数 → 校验 → 分发；不导出函数 |
| `fetch.js` | 命令 | `fetchOne(reqNo, dirType, mcpToken, backupTimestamp, baseReqNo?) → { parentNo }`（`init` 逐级拉 AR → SR → RR）；`fetchUpstream(reqNo, mcpToken, { outDir })`（`fetch` 只读取回）；取单据与正文的公共函数 |
| `archive.js` | 命令 | `archiveOne(reqNo, mcpToken, skipBackup?, contentOverride?) → { archived, backupPath, verified, reviewArchived }` |
| `restore.js` | 命令 | `restoreOne(reqNo, mcpToken) → { restored, verified }`：取 `.backups/cloud/` 最新一份，经 `archiveOne` 的 `contentOverride` 写回系统 |
| `mcp.js` | 需求系统访问 | `callMcp(url, method, params, mcpToken)` 与两个端点常量；命令文件只经它访问系统。替身读写本地目录，方法名替身自定 |
| `dirs.js` | 公共工具 | 工程根、需求目录、`.backups/cloud/` 等路径与时间戳 |
| `token.js` | 独立入口 | 取 mcp token：成功退出 0，**stdout 即 token 本身**（纯文本单行）；失败非 0，错误走 stderr |

内网另有富文本转 Markdown、图片下载与映射、同 SR 子单查询、系统证书引导等工具文件（`post-process.js`、`html-to-md.js`、`download-images.js`、`image-map.js`、`siblings.js`、`system-ca-bootstrap.js`），替身的需求系统只有 md，用不到它们，不建空壳。

`story.js` 的 CLI 合同真源是它的 docstring——**改实现时先读它，那是唯一依据**。要点：

- `node story.js <init|archive|restore|fetch> <AR单号> <mcp-token> [--project-root <abs>] [--out <本单 inbox>]`；
- **只有 AR 开头的单挂在需求系统上**，其余是本地需求；
- **两层错误**：参数错（缺命令、缺单号、缺 token、非 AR、`fetch` 缺 `--out`）只写 stderr 与用法、退出码 1，不写 stdout JSON；命令执行出错由顶层 catch 写 `{"mode","reqNo","success":false,"error"}`、退出码 1；
- 成功时 stdout 最后一行是单行 JSON，各命令字段见 docstring；日志走 stderr。

写盘落点也是合同的一部分：`init` 写各级 `detail.json` 与正文（本地已有不覆盖）；`archive` 在本地只写 `.backups/cloud/`；`fetch` 写本单 `inbox/`、`AR/story-src/review-feedback.md` 与 `AR/story-src/fetched.json`。**公共机制不往 `AR/` 根下写任何辅助文件**，辅助件一律进 `AR/story-src/`。

需求目录下的备份统一在 `.backups/`：`cloud/` 是需求系统拉取内容的备份（归档覆盖系统正文前取下的那一版，restore 据它恢复系统数据），由对接层写；`local/` 是本地文档的备份（覆盖本地文件前的旧内容、被取代的原件），由 core 与作者写。

### `fetch`：只读取材

`fetch <单号> <token> --project-root <工程根> --out <本单 inbox>` 是**只读取材**：取回这张单现在关联的上游正文与评审回稿。
三份正文写进 `--out`（本单的 `inbox/`，与人补的料走同一条导入链），与本地对应文件逐字相同的不落盘；
评审回稿不是需求正文，写在 `AR/story-src/review-feedback.md`；回执 `AR/story-src/fetched.json` 逐份记来源身份、摘要、
系统上的位置、取到没有——它不能放进 inbox，否则会被当成一份材料导入。**一个业务文件都不写**。
`status` 四态分开：`fetched` / `same`（与本地相同）/ `absent`（系统上本来就没有，常态）/ `failed`（读取故障）——
混成一个的话，一次读取错误会被当成「评审没提意见」。

`/story update` 由 SKILL 指导模型调用 `fetch`：两个路径参数取自 core `update --action status` 返回的 `paths`（`project_root`、`inbox`），core 之后原样读回执；命令失败时停在取材这一步。

## 换实现时要守住的两件

1. **CLI 与 stdout 形态不变**：流程脚本按上表解析结果，多一层结构、少一个字段都会让调用方读到别的东西；
2. **失败就失败**：查无此单、缺文件、系统不通，一律非 0 退出并说清哪一步没做完。写一地占位件再报成功，下游会拿着占位件往下走。

## `core/` 里两处不在作者流程上的约定

| 约定 | 是什么 | 怎么用 |
|---|---|---|
| `<需求>/ux-reference/.captions.json` | 图片侧车：按图片内容摘要记「这张图是什么」与「本需求为什么不用它」，材料清单与作者任务包从它读 | 只经 `import_sources.py` 的 `--register-ux`、`--caption-image`（含 `--unused`、`--used`）写，不手改 |

## 内外网隔离与新增能力交接

adapters 隔离部署环境中的需求系统、鉴权和内容处理实现；core 只读约定的材料与回执，两边通过这份合同与落盘文件相接，互不生成对方的命令。对接层的文件划分与导出签名跟内网一致，跨环境变更按文件逐个交代。

新增或改变跨环境能力时，本合同须与调用方一起更新，并在适配交接中明确：新增/变更/删除的能力、触发它的流程、参数与输出、写入范围、失败与不适用语义、目标需要落实的动作及验证方法。无对接变化也明确说明；不能要求目标维护者阅读 Demo diff 推断需补什么。

外网替身通过只证明合同在替身环境可用。目标 adapters 未覆盖的新能力应列为尚未适配，该功能不能宣称可用；不得用替身覆盖内网实现、用静默降级掩盖缺口，或将目标内部模块名写进通用流程。
