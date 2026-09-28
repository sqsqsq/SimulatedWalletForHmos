/**
 * story.js — /story 需求系统对接的公共 CLI 入口（本仓为本地替身；部署环境各自实现入口及其内部模块）
 *
 * 分层：
 *   story.js（入口：参数解析 → 校验 → 分发）
 *     ├─ fetch.js    init（fetchOne 逐级拉 AR → SR → RR）与 fetch（fetchUpstream 只读取回）
 *     ├─ archive.js  archive（archiveOne）
 *     └─ restore.js  restore（restoreOne，经 archiveOne 回传备份）
 *   mcp.js（需求系统访问层）  dirs.js（路径）  token.js（取 token，独立入口）
 *
 * 命令接口（SKILL 按此调用）：
 *   node story.js <init|archive|restore|fetch> <AR单号> <mcp-token> [--project-root <abs>] [--out <本单 inbox>]
 *
 *   人类可读日志走 stderr；命令执行完 stdout 最后一行是单行 JSON：
 *   init    → {"mode":"init","reqNo":"...","parentNo":"SR...","rrNo":"RR...","success":true}
 *             按单号拉 AR 自己、它挂的 SR、SR 挂的 RR，各写一份 detail.json，正文分别落
 *             AR/design.md、SR/design.md、RR/prd.md；系统上缺的正文不写，本地已有的不覆盖。
 *             系统上查无此单即失败，不落占位件。
 *   archive → {"mode":"archive","reqNo":"...","archived":true,"backupPath":"...","verified":true,
 *              "reviewArchived":true,"success":true}
 *             AR/story.md 写成系统正文、AR/review.md 传为附件；覆盖前系统正文备份到
 *             需求目录 `.backups/cloud/`；本地只写这一处。缺 story.md 或 review.md 即失败。
 *   restore → {"mode":"restore","reqNo":"...","restored":true,"verified":true,"success":true}
 *             把 `.backups/cloud/` 里最新一份写回系统正文；没有备份即失败。
 *   fetch   → {"mode":"fetch","reqNo":"...","out":"...","fetched":3,"failed":0,"items":[...],"success":true}
 *             只读取材：上游三份正文写进 --out（必填），评审回稿写 AR/story-src/review-feedback.md，
 *             回执写 AR/story-src/fetched.json；items[].status 为 fetched / same / absent / failed。
 *             有 failed 时 success 为 false、退出码非 0。一个业务文件都不写。
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
const { fetchOne, fetchUpstream } = require('./fetch');
const { archiveOne } = require('./archive');
const { restoreOne } = require('./restore');
const { PROJECT_ROOT, timestamp } = require('./dirs');
const path = require('node:path');

const USAGE = '用法：node story.js <init|archive|restore|fetch> <AR单号> <mcp-token> '
  + '[--project-root <abs>] [--out <本单 inbox>（fetch 必填）]';
const MODES = ['init', 'archive', 'restore', 'fetch'];

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

  if (mode === 'init') {
    const stamp = timestamp();
    const { parentNo: srNo } = await fetchOne(reqNo, 'AR', mcpToken, stamp);
    const { parentNo: rrNo } = srNo ? await fetchOne(srNo, 'SR', mcpToken, stamp, reqNo) : { parentNo: null };
    if (rrNo) await fetchOne(rrNo, 'RR', mcpToken, stamp, reqNo);
    return { parentNo: srNo, rrNo };
  }
  if (mode === 'archive') return archiveOne(reqNo, mcpToken);
  if (mode === 'restore') return restoreOne(reqNo, mcpToken);
  const out = option('--out');
  if (!out) usageError('fetch 要 --out <本单 inbox>：它只往那里写，不碰任何业务文件');
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
