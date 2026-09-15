# `scripts/` 的两层：谁写的，谁维护

这一层不放独立文件，只有两个目录。**一个文件归谁，看它在哪个目录**——不看后缀、不看文件头自述、不靠任何推断。

| 目录 | 归谁 | 升级时 |
|---|---|---|
| `core/` | 包（本扩展） | 整份换掉，包里没有的删掉 |
| `adapters/` | **目标仓自己实现** | 一个字节不碰 |

新增的公共脚本一律进 `core/`。往 `scripts/` 根下放文件会被 `adapt-scan --check ⑧` 拦下：放在那里的两边都不认，永远升级不到目标手里。

## `adapters/` 里那三个的输出合同

它们是需求系统的对接层。本仓这三份是**替身**（本地目录模拟需求系统），部署环境各自实现自己那份，从不调用扩展内容。

合同的真源是每个文件自己的 docstring——**改实现时先读它，那是唯一依据**：

| 文件 | 干什么 | 合同要点 |
|---|---|---|
| `story.js` | 需求系统对接（`init` / `archive` / `restore` / `review` / `help`） | 人类可读日志走 stderr；stdout 最后一行是 JSON 结果，各命令的字段见 docstring；失败非 0 退出且 JSON 带 `success: false` 与 `error` |
| `token.js` | 取 mcp token | 成功退出 0，**stdout 即 token 本身**（纯文本单行，不是 JSON）；失败非 0，错误走 stderr |
| `review.js` | `story.js review` 的实现模块 | 由 `story.js` 同目录 `require`，不单独作为 CLI 入口 |

写盘落点也是合同的一部分：`AR/design.md`、`AR/review.md`、`AR/detail.json`、`AR/.review-backup/` 由这一层写。**公共机制不往 `AR/` 根下写任何辅助文件**，辅助件一律进 `AR/story-src/`。

## 换实现时要守住的两件

1. **CLI 与 stdout 形态不变**：流程脚本按上表解析结果，多一层结构、少一个字段都会让调用方读到别的东西；
2. **失败就失败**：查无此单、缺文件、系统不通，一律非 0 退出并说清哪一步没做完。写一地占位件再报成功，下游会拿着占位件往下走。

## `core/` 里两处不在作者流程上的约定

| 约定 | 是什么 | 怎么用 |
|---|---|---|
| `<需求>/ux-reference/.captions.json` | 图片侧车：按图片内容摘要记「这张图是什么」与「本需求为什么不用它」，材料清单与作者任务包从它读 | 只经 `import_sources.py` 的 `--register-ux`、`--caption-image`（含 `--unused`、`--used`）写，不手改 |
| `story-build.mjs check --offline --story <文件>` | 对一份脱离需求目录的 story 单独跑不依赖工作区的确定性检查（例如核一份认可的样稿）；来源、材料清单、决策登记相关的判项不跑 | 不读需求工作区，不写盘 |
