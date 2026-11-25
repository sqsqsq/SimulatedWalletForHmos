/**
 * restore.js — 回退归档对正文的覆盖：照恢复准备写回那次覆盖前的系统正文。
 *
 * restoreOne(reqNo, mcpToken) → { restored: true, verified: true, backupPath }
 *   恢复准备写在取材回执 `AR/story-src/fetched.json` 的 `restore`：
 *   `{prepared_at, name, local, digest, external, action}`——目标备份（需求目录相对路径）与它的摘要、准备时远端正文的摘要、
 *   这次是只读回（`skip`）还是要写（`write` / `authorized`）。没有准备项、备份字节对不上，或远端正文在准备之后又变了，
 *   一个字都不写。要写时只动正文，不动附件、不再备份；写后读回，读回等于目标才算恢复，
 *   不等或读不回记 failed 与原错误（远端可能已被写过，恢复未确认）。读回结果写进回执正文项的 status / digest / checkedAt。
 *   本地业务文件不动。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { callMcp, REQUIREMENT_URL } = require('./mcp');
const { featureDir } = require('./dirs');

const RECEIPT = path.join('AR', 'story-src', 'fetched.json');
const digest = text => `sha256:${crypto.createHash('sha256').update(text).digest('hex').slice(0, 16)}`;

function log(msg) {
  console.error(`[restore.js] ${msg}`);
}

async function restoreOne(reqNo, mcpToken) {
  const root = featureDir(reqNo);
  const receiptFile = path.join(root, RECEIPT);
  let receipt;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf-8'));
  } catch (e) {
    throw new Error(`${RECEIPT.split(path.sep).join('/')} 读不出来（${e.message}）：恢复前先 fetch 并做恢复准备`);
  }
  const plan = receipt.restore;
  if (!plan?.local || !plan.digest || !['skip', 'write', 'authorized'].includes(plan.action)) {
    throw new Error('取材回执里没有可执行的恢复准备（restore）：先 fetch 再做恢复准备，它定下恢复哪一版、远端现在是哪一版');
  }
  const file = path.join(root, ...String(plan.local).split('/'));
  if (!fs.existsSync(file)) throw new Error(`恢复目标 ${plan.local} 不在：没有那次覆盖前的备份就不能恢复`);
  const content = fs.readFileSync(file, 'utf-8');
  if (digest(content) !== plan.digest) {
    throw new Error(`恢复目标 ${plan.local} 的字节与准备时记的 ${plan.digest} 不同：一个字都没写；重新做恢复准备`);
  }
  const current = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken);
  const now = current === null ? null : digest(current);
  if (now !== (plan.external ?? null)) {
    throw new Error(`需求系统上的正文在恢复准备之后又变了（准备时 ${plan.external ?? '不存在'}，现在 ${now ?? '不存在'}）：`
      + '一个字都没写；重新 fetch、做恢复准备后再恢复');
  }
  const items = receipt.items ?? [];
  let at = items.findIndex(i => i.name === 'AR-design.md');
  if (at < 0) at = items.push({ name: 'AR-design.md' }) - 1;
  const save = () => fs.writeFileSync(receiptFile, `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  const skipped = current === content;
  try {
    if (!skipped) await callMcp(REQUIREMENT_URL, 'putBody', { reqNo, name: 'design.md', content }, mcpToken);
    const back = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken);
    if (back !== content) throw new Error('读回内容与恢复目标不同');
    items[at] = { ...items[at], status: skipped ? 'same' : 'fetched', note: skipped ? '外部已是恢复目标' : '本次恢复已读回',
      digest: digest(back), origin: `${reqNo}/design.md`, bytes: Buffer.byteLength(back, 'utf-8'), checkedAt: new Date().toISOString() };
    receipt.items = items;
    save();
  } catch (e) {
    items[at] = { ...items[at], status: 'failed', note: `${skipped ? '' : '远端可能已被写过，'}恢复未确认：${e.message}` };
    receipt.items = items;
    save();
    throw new Error(`正文恢复未确认（${e.message}）：${skipped ? '' : '远端可能已被写过；'}重新 fetch、做恢复准备核清现状再续`);
  }
  log(`系统正文${skipped ? '已是' : '已恢复到'}归档前的版本：${plan.local}`);
  return { restored: true, verified: true, backupPath: plan.local };
}

module.exports = { restoreOne };
