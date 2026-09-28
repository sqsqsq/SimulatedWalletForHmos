/**
 * fetch.js — 取单据：`init` 首次拉取，`fetch` 只读取回。
 *
 * fetchOne(reqNo, dirType, mcpToken, backupTimestamp, baseReqNo?) → { parentNo }
 *   拉一级单据的详情与正文，落到 `<features>/<baseReqNo ?? reqNo>/<dirType>/`：
 *   detail.json 每次写；正文（AR/SR 为 design.md，RR 为 prd.md）系统上有才写、本地已有不覆盖——
 *   AR/design.md 是需求分析的预填输入，本地那份可能已经是分析成果。本替身不覆盖正文，
 *   backupTimestamp 不产生备份。
 *   parentNo 是上一级单号（AR → SR，SR → RR，RR 为 null），入口据它逐级往上拉。
 *
 * fetchUpstream(reqNo, mcpToken, { outDir }) → 回执
 *   **只读取材**：把这张单现在关联的上游正文与评审回稿取回，一个业务文件都不写。
 *   三份正文写进 outDir（本单 inbox），与本地对应文件逐字相同的不落盘；评审回稿写
 *   `AR/story-src/review-feedback.md`；回执写 `AR/story-src/fetched.json`（不放 inbox，
 *   否则会被当成一份材料导入），带取材时刻 fetchedAt（带时区的 ISO 8601）。每份的 status 四态分开：fetched / same / absent / failed——
 *   混成一个的话，一次读取错误会被当成「评审没提意见」。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { callMcp, REQUIREMENT_URL } = require('./mcp');
const { featureDir, levelDir } = require('./dirs');

const BODY = { AR: 'design.md', SR: 'design.md', RR: 'prd.md' };
const FALLBACK_TITLE = { AR: '开发需求', SR: '系统设计', RR: '产品需求' };

function log(msg) {
  console.error(`[fetch.js] ${msg}`);
}

function text(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** 单据详情（公共）：update 取材与 init 共用。 */
async function getDetail(reqNo, mcpToken) {
  return callMcp(REQUIREMENT_URL, 'getDetail', { reqNo }, mcpToken);
}

/** 单据正文（公共）：系统上没有返回 null。 */
async function getBody(reqNo, name, mcpToken) {
  return callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name }, mcpToken);
}

/** 上一级单号：AR 的上一级是 SR，SR 的上一级是 RR。 */
function parentOf(detail, dirType) {
  if (dirType === 'AR') return text(detail.parentNo);
  if (dirType === 'SR') return text(detail.parentNo) ?? text(detail.rrNo);
  return null;
}

async function fetchOne(reqNo, dirType, mcpToken, backupTimestamp, baseReqNo) {
  const detail = await getDetail(reqNo, mcpToken);
  const dir = levelDir(baseReqNo ?? reqNo, dirType);
  fs.mkdirSync(dir, { recursive: true });
  const record = { reqNo, type: dirType, title: text(detail.title) ?? `${reqNo} ${FALLBACK_TITLE[dirType]}` };
  if (dirType === 'AR') record.parentNo = parentOf(detail, 'AR');
  if (dirType !== 'RR') record.rrNo = text(detail.rrNo);
  fs.writeFileSync(path.join(dir, 'detail.json'), `${JSON.stringify(record, null, 2)}\n`, 'utf-8');

  const body = await getBody(reqNo, BODY[dirType], mcpToken);
  const target = path.join(dir, BODY[dirType]);
  if (body === null) {
    log(`系统上没有 ${dirType}/${BODY[dirType]}，本地未写入`);
  } else if (fs.existsSync(target)) {
    log(`已存在，跳过：${target}`);
  } else {
    fs.writeFileSync(target, body, 'utf-8');
    log(`生成：${target}`);
  }
  return { parentNo: parentOf(detail, dirType) };
}

function readOr(file) {
  try { return fs.readFileSync(file, 'utf-8'); } catch { return null; }
}

async function fetchUpstream(reqNo, mcpToken, { outDir }) {
  const root = featureDir(reqNo);
  const detail = await getDetail(reqNo, mcpToken);
  const srNo = parentOf(detail, 'AR');
  const rrNo = text(detail.rrNo);
  const src = path.join(root, 'AR', 'story-src');
  const wanted = [
    { name: 'AR-design.md', label: '开发需求正文（本单）', no: reqNo, body: 'design.md',
      local: ['AR/design.md', 'AR/story.md'] },
    { name: 'SR-design.md', label: '系统设计正文', no: srNo, body: 'design.md', local: ['SR/design.md'] },
    { name: 'RR-prd.md', label: '产品需求正文', no: rrNo, body: 'prd.md', local: ['RR/prd.md'] },
    { name: 'review-feedback.md', label: '评审人留下的回稿', no: reqNo, body: 'review-feedback.md',
      local: [], dir: src },
  ];
  const items = [];
  for (const w of wanted) {
    const id = { name: w.name, label: w.label, ticket: w.no || null };
    if (!w.no) { items.push({ ...id, status: 'absent', note: '这张单上没有挂它' }); continue; }
    let body;
    try {
      body = await getBody(w.no, w.body, mcpToken);
    } catch (e) {
      items.push({ ...id, status: 'failed', note: e.message });
      continue;
    }
    if (body === null) { items.push({ ...id, status: 'absent', note: '系统上现在没有这一份' }); continue; }
    const facts = {
      digest: `sha256:${crypto.createHash('sha256').update(body).digest('hex').slice(0, 16)}`,
      origin: `${w.no}/${w.body}`,
      bytes: Buffer.byteLength(body, 'utf-8'),
    };
    const same = w.local.find(rel => readOr(path.join(root, rel)) === body);
    if (same) { items.push({ ...id, status: 'same', note: `与本地 ${same} 逐字相同`, ...facts }); continue; }
    const dir = w.dir || outDir;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, w.name), body, 'utf-8');
    items.push({ ...id, status: 'fetched',
      saved: path.relative(root, path.join(dir, w.name)).split(path.sep).join('/'), ...facts });
  }
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(src, 'fetched.json'),
    `${JSON.stringify({ mode: 'fetch', reqNo, fetchedAt: new Date().toISOString(), items }, null, 2)}\n`, 'utf-8');
  const fetched = items.filter(i => i.status === 'fetched').length;
  const failed = items.filter(i => i.status === 'failed').length;
  log(`取回 ${fetched} 份到 ${outDir}${failed ? `，${failed} 份读取失败` : ''}；一个业务文件都没动`);
  return { out: outDir, fetched, failed, items };
}

module.exports = { fetchOne, fetchUpstream, getDetail, getBody };
