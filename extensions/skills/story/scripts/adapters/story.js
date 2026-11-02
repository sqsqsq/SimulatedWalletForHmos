/**
 * story.js — /story 需求系统对接的公共 CLI 入口（本仓为本地替身；部署环境各自实现入口及其内部模块）
 *
 * 分层：
 *   story.js（入口：参数解析 → 校验 → 分发）
 *     ├─ fetch.js    fetch（fetchUpstream 只读取回本单关联的 AR / SR / RR 正文、评审回稿与附件）
 *     ├─ archive.js  archive（archiveOne，三件逐件写入并读回）
 *     └─ restore.js  restore（restoreOne，照取材回执里的恢复准备写回那次覆盖前的正文）
 *   mcp.js（需求系统访问层）  dirs.js（路径）  token.js（取 token，独立入口）
 *
 * 命令接口（SKILL 按此调用）：
 *   node story.js <archive|restore|fetch> <AR单号> <mcp-token> [--project-root <abs>] [--out <取材批次目录>]
 *
 *   人类可读日志走 stderr；命令执行完 stdout 最后一行是单行 JSON：
 *   archive → {"mode":"archive","reqNo":"...","archived":true,"backupPath":"...","verified":true,
 *              "items":[...],"success":true}
 *             AR/story.md 写成系统正文、AR/review.md 与 blueprint/component-blueprint.review.md（设计参考）传为附件，逐件读回，读回记进
 *             AR/story-src/fetched.json；交付哪几件照回执里发布前核对记下的 delivery；覆盖前系统正文备份到需求目录 `.backups/cloud/`。
 *   restore → {"mode":"restore","reqNo":"...","restored":true,"verified":true,"success":true}
 *             照取材回执里的恢复准备（`restore`）把那次覆盖前的备份写回系统正文并读回；没有准备、远端在准备之后变了或读回不一致即失败。
 *   fetch   → {"mode":"fetch","reqNo":"...","out":"...","parentNo":"SR...","rrNo":"RR...","fetched":3,"failed":0,
 *              "items":[...],"success":true}
 *             只读取材，起单与 update 都用它：上游三份正文写进 --out（必填，本单来源收件箱下的取材批次），
 *             批次回执 .receipt.json 逐件给角色、单号与标题；评审回稿写 AR/story-src/review-feedback.md，
 *             两个附件与本地不同时写 AR/story-src/fetched-review.md、fetched-design-review.md，
 *             外部当前状态写 AR/story-src/fetched.json；items[].status 为 fetched / same / absent / failed。
 *             系统上查无此单即失败；有 failed 时 success 为 false、退出码非 0。一个业务文件都不写。
 *
 *   两层错误：
 *   - 参数错（缺命令、缺单号、缺 token、单号不是 AR 开头、fetch 缺 --out）→ 用法与原因写 stderr，
 *     退出码 1，**不写 stdout JSON**。只有 AR 开头的单挂在需求系统上，其余是本地需求，
 *     在访问系统之前就在这里失败。
 *   - 命令执行出错 → 顶层 catch 写 {"mode":"...","reqNo":"...","success":false,"error":"..."}，退出码 1。
 *
 * mcp-token：token.js 取得。本替身不校验内容、不使用。
 */
'use strict';
const { fetchUpstream } = require('./fetch');
const { archiveOne } = require('./archive');
const { restoreOne } = require('./restore');
const { PROJECT_ROOT } = require('./dirs');
const path = require('node:path');

const USAGE = '用法：node story.js <archive|restore|fetch> <AR单号> <mcp-token> '
  + '[--project-root <abs>] [--out <取材批次目录>（fetch 必填）]';
const MODES = ['archive', 'restore', 'fetch'];

function usageError(reason) {
  console.error(`[story.js] ${reason}\n${USAGE}`);
  process.exit(1);
}

function option(name) {
  const at = process.argv.indexOf(name);
  return at >= 0 ? process.argv[at + 1] : undefined;
}

const [mode, reqNo, mcpToken] = process.argv.slice(2);

async function main() {
  if (!MODES.includes(mode)) usageError(`不认识的命令：${mode ?? '（缺）'}`);
  if (!reqNo) usageError('缺单号');
  if (!reqNo.startsWith('AR')) {
    usageError(`${reqNo} 是本地需求：只有 AR 开头的需求挂在需求系统上，${mode} 不适用（不访问系统）。`
      + '本地需求的材料由人直接放进 inbox/');
  }
  if (!mcpToken || mcpToken.startsWith('--')) usageError('缺 mcp-token');

  if (mode === 'archive' || mode === 'restore') {
    const result = await (mode === 'archive' ? archiveOne(reqNo, mcpToken) : restoreOne(reqNo, mcpToken));
    if (!result.verified) {
      // 读回与上传内容不一致：远端写了但核验不成立，不记整体成功
      console.log(JSON.stringify({ mode, reqNo, ...result, success: false,
        error: '归档核验失败：系统侧读回的内容与上传的不一致，重跑这一条命令后再登记' }));
      process.exit(1);
    }
    return result;
  }
  const out = option('--out');
  if (!out) usageError('fetch 要 --out <取材批次目录>：它只往那里写，不碰任何业务文件');
  const result = await fetchUpstream(reqNo, mcpToken, { outDir: path.resolve(PROJECT_ROOT, out) });
  if (result.failed) {
    console.log(JSON.stringify({ mode, reqNo, ...result, success: false }));
    process.exit(1);
  }
  return result;
}

main()
  .then(result => console.log(JSON.stringify({ mode, reqNo, ...result, success: true })))
  .catch((e) => {
    console.error(`[story.js] ${e.message}`);
    console.log(JSON.stringify({ mode, reqNo, success: false, error: e.message }));
    process.exit(1);
  });
