/**
 * archive.js — 归档：Story 写成系统正文，Review 与设计附件传为附件，逐件写入并读回。
 *
 * archiveOne(reqNo, mcpToken, skipBackup?, contentOverride?)
 *   → { archived: true, backupPath, verified, items }
 *
 *   ① 写入前逐件核需求系统上的当前内容仍是 发布前核对时取回的那一版（取材回执
 *      `AR/story-src/fetched.json` 里 AR-design.md、review.md、design-review.md 三项的摘要）；有一件变了就停下，一件都不写。
 *   ② 回执里这三项先标成 failed（「本次发布读回尚未完成」），再按 正文 → review.md → design-review.md 的顺序上传：
 *      外部已经是本地这一份的跳过写入；每件写完读回，读回等于本地才把这一项写成 fetched / same 与 checkedAt。
 *      回执里其余项与 fetchedAt 不动。读回不一致或写入失败时这一项记 failed 与原始错误，停下，后面的不写。
 *   ③ 覆盖正文前把系统当前正文备份到 `<需求目录>/.backups/cloud/design-<时刻>.md`（restore 靠它）；系统上还没有正文时不留空备份。
 *   本地只写 `.backups/cloud/` 与取材回执，业务文件一个字节不动。**只上传 md**：系统不承载图片，正文里的图片链接原样保留。
 *   三件缺任一即失败，无降级路径。归档前的交付门与外部冲突由 /story 流程在调用前核完，不在这里。
 *
 *   restore 经 contentOverride 只回传正文（skipBackup 为真，不动附件与回执）。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { callMcp, REQUIREMENT_URL, ATTACHMENT_URL } = require('./mcp');
const { featureDir, cloudBackupDir, timestamp } = require('./dirs');

const RECEIPT = path.join('AR', 'story-src', 'fetched.json');
//: 发布的三件：回执里的名字、本地文件、需求系统上的位置
const ITEMS = [
  { name: 'AR-design.md', local: 'AR/story.md', get: 'getBody', put: 'putBody', url: REQUIREMENT_URL, remote: 'design.md' },
  { name: 'review.md', local: 'AR/review.md', get: 'getAttachment', put: 'putAttachment', url: ATTACHMENT_URL, remote: 'review.md' },
  { name: 'design-review.md', local: 'AR/design-review.md', get: 'getAttachment', put: 'putAttachment', url: ATTACHMENT_URL,
    remote: 'design-review.md' },
];

function log(msg) {
  console.error(`[archive.js] ${msg}`);
}

const digest = text => `sha256:${crypto.createHash('sha256').update(text).digest('hex').slice(0, 16)}`;

async function backupBody(reqNo, mcpToken, root) {
  const current = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken);
  if (current === null) {
    log('系统上尚无正文，本次归档是首次写入，没有可备份的版本');
    return null;
  }
  const dir = cloudBackupDir(reqNo);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `design-${timestamp()}.md`);
  fs.writeFileSync(file, current, 'utf-8');
  const rel = path.relative(root, file).split(path.sep).join('/');
  log(`系统当前正文已备份：${rel}`);
  return rel;
}

/** restore 用：只把给定内容回传为系统正文并核对。 */
async function putBodyOnly(reqNo, mcpToken, content) {
  await callMcp(REQUIREMENT_URL, 'putBody', { reqNo, name: 'design.md', content }, mcpToken);
  const verified = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken) === content;
  return { archived: true, backupPath: null, verified };
}

async function archiveOne(reqNo, mcpToken, skipBackup = false, contentOverride = undefined) {
  if (contentOverride !== undefined) return putBodyOnly(reqNo, mcpToken, contentOverride);
  const root = featureDir(reqNo);
  const local = {};
  for (const item of ITEMS) {
    const file = path.join(root, item.local);
    if (!fs.existsSync(file)) {
      throw new Error(`${item.local} 不存在，无可归档物：${reqNo}。它是 /story 成文登记的产物，请回 /story 补齐后重试。`);
    }
    local[item.name] = fs.readFileSync(file, 'utf-8');
  }
  const receiptFile = path.join(root, RECEIPT);
  let receipt;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf-8'));
  } catch (e) {
    throw new Error(`${RECEIPT.split(path.sep).join('/')} 读不出来（${e.message}）：上传前先 fetch 并做发布前核对`);
  }
  const items = receipt.items ?? [];
  const entry = name => items.find(i => i.name === name);
  // ① 写入前逐件核：外部仍是预检取回的那一版
  const current = {};
  for (const item of ITEMS) {
    const seen = entry(item.name);
    if (!seen || seen.status === 'failed') throw new Error(`取材回执里没有 ${item.name} 的外部当前内容：先 fetch 再做发布前核对`);
    current[item.name] = await callMcp(item.url, item.get, { reqNo, name: item.remote }, mcpToken);
    const now = current[item.name] === null ? null : digest(current[item.name]);
    const then = seen.status === 'absent' ? null : seen.digest;
    if (now !== then) {
      throw new Error(`需求系统上的 ${item.name} 在预检之后又变了（预检 ${then ?? '不存在'}，现在 ${now ?? '不存在'}）：`
        + '一件都没写；重新 fetch、做发布前核对后再传');
    }
  }
  // ② 先撤销三项旧读回对本轮的资格，再逐件写入、读回
  const save = () => fs.writeFileSync(receiptFile, `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  for (const item of ITEMS) {
    const at = items.findIndex(i => i.name === item.name);
    items[at] = { name: item.name, label: items[at].label, ticket: items[at].ticket, status: 'failed', note: '本次发布读回尚未完成' };
  }
  receipt.items = items;
  save();
  const backupPath = skipBackup || current['AR-design.md'] === local['AR-design.md'] ? null
    : await backupBody(reqNo, mcpToken, root);
  for (const item of ITEMS) {
    const at = items.findIndex(i => i.name === item.name);
    const skipped = current[item.name] === local[item.name];
    try {
      if (!skipped) await callMcp(item.url, item.put, { reqNo, name: item.remote, content: local[item.name] }, mcpToken);
      const back = await callMcp(item.url, item.get, { reqNo, name: item.remote }, mcpToken);
      if (back !== local[item.name]) throw new Error('读回内容与本地这一份不同');
      items[at] = { ...items[at], status: skipped ? 'same' : 'fetched', note: skipped ? '外部已是本地这一份' : '本次上传已读回',
        digest: digest(back), origin: `${reqNo}/${item.remote}`, bytes: Buffer.byteLength(back, 'utf-8'),
        checkedAt: new Date().toISOString() };
      save();
    } catch (e) {
      items[at] = { ...items[at], status: 'failed', note: e.message };
      save();
      throw new Error(`${item.name} 上传未完成（${e.message}）：已完成的几件保留，重试前重新 fetch 并做发布前核对`);
    }
  }
  log(`归档完成：${reqNo}（正文 + 评审记录附件 + 设计附件，均已读回）`);
  return { archived: true, backupPath, verified: true, items: items.filter(i => ITEMS.some(x => x.name === i.name)) };
}

module.exports = { archiveOne };
