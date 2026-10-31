/**
 * fetch.js — 取单据：起单与 update 都只读取材，`fetch` 一个业务文件都不写。
 *
 * fetchUpstream(reqNo, mcpToken, { outDir }) → 回执
 *   把这张单现在关联的上游正文（本单 AR、它挂的 SR、SR 挂的 RR）、评审回稿与两个附件取回。
 *   三份正文写进 outDir（本单来源收件箱下的一个取材批次），批次里写 `.receipt.json`：
 *   reqNo / parentNo / rrNo 与逐件的 role、ticket、title、origin、status、saved——导入按它认来源。
 *   与来源索引里同一来源已存的某一版逐字相同的不落盘（AR 正文与本地已归档的 Story 相同也不落盘，
 *   那是我们自己发布上去的）；评审回稿写 `AR/story-src/review-feedback.md`；评审记录附件与设计参考附件和本地不同时
 *   写 `AR/story-src/fetched-review.md`、`fetched-design-review.md`（不覆盖本地 AR/review.md 的人工区）；
 *   外部当前状态另写 `AR/story-src/fetched.json`，带取材时刻 fetchedAt。每份的 status 四态分开：
 *   fetched / same / absent / failed——混成一个的话，一次读取错误会被当成「评审没提意见」。
 *   关联关系逐级从实际返回解析，取不到就记 absent 与原因，不默认 AR 详情一定带 RR 编号。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { callMcp, REQUIREMENT_URL, ATTACHMENT_URL } = require('./mcp');
const { featureDir } = require('./dirs');

function log(msg) {
  console.error(`[fetch.js] ${msg}`);
}

function text(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** 单据详情（公共）：取标题与上一级单号。 */
async function getDetail(reqNo, mcpToken) {
  return callMcp(REQUIREMENT_URL, 'getDetail', { reqNo }, mcpToken);
}

/** 单据正文（公共）：系统上没有返回 null。 */
async function getBody(reqNo, name, mcpToken) {
  return callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name }, mcpToken);
}

function readOr(file) {
  try { return fs.readFileSync(file, 'utf-8'); } catch { return null; }
}

/** 来源索引里同一来源（角色 + 单号）已存的各版原件：取回的内容与其中一版逐字相同就不再落盘。 */
function storedVersions(root, role, ticket) {
  let index;
  try { index = JSON.parse(readOr(path.join(root, 'AR', 'story-src', 'materials.json')) ?? 'null'); } catch { index = null; }
  const source = (index?.sources ?? []).find(s => s?.source_id === `system:${role}:${ticket}`);
  return (source?.versions ?? []).map(v => ({ dir: v.dir, body: readOr(path.join(root, ...String(v.original?.path ?? '').split('/'))) }));
}

async function fetchUpstream(reqNo, mcpToken, { outDir }) {
  const root = featureDir(reqNo);
  const detail = await getDetail(reqNo, mcpToken);
  const srNo = text(detail.parentNo);
  const srDetail = srNo ? await getDetail(srNo, mcpToken) : null;
  const rrNo = text(detail.rrNo) ?? text(srDetail?.parentNo) ?? text(srDetail?.rrNo);
  const rrDetail = rrNo ? await getDetail(rrNo, mcpToken) : null;
  const src = path.join(root, 'AR', 'story-src');
  const wanted = [
    { name: 'AR-design.md', role: 'AR', label: '开发需求正文（本单）', no: reqNo, title: text(detail.title), body: 'design.md',
      local: ['AR/story.md'] },
    { name: 'SR-design.md', role: 'SR', label: '系统设计正文', no: srNo, title: text(srDetail?.title), body: 'design.md', local: [],
      missing: '本单详情没有给出上一级系统设计单号' },
    { name: 'RR-prd.md', role: 'RR', label: '产品需求正文', no: rrNo, title: text(rrDetail?.title), body: 'prd.md', local: [],
      missing: '本单与系统设计单都没有给出产品需求单号' },
    { name: 'review-feedback.md', label: '评审人留下的回稿', no: reqNo, body: 'review-feedback.md',
      local: [], dir: src },
    { name: 'review.md', label: '评审记录附件', no: reqNo, attachment: 'review.md',
      local: ['AR/review.md'], dir: src, saveAs: 'fetched-review.md' },
    { name: 'design-review.md', label: '设计参考附件', no: reqNo, attachment: 'design-review.md',
      local: ['blueprint/component-blueprint.review.md'], dir: src, saveAs: 'fetched-design-review.md' },
  ];
  const items = [];
  for (const w of wanted) {
    const id = { name: w.name, label: w.label, ticket: w.no || null, ...(w.role ? { role: w.role, title: w.title } : {}) };
    if (!w.no) { items.push({ ...id, status: 'absent', note: w.missing ?? '这张单上没有挂它' }); continue; }
    let body;
    try {
      body = w.attachment
        ? await callMcp(ATTACHMENT_URL, 'getAttachment', { reqNo: w.no, name: w.attachment }, mcpToken)
        : await getBody(w.no, w.body, mcpToken);
    } catch (e) {
      items.push({ ...id, status: 'failed', note: e.message });
      continue;
    }
    if (body === null) { items.push({ ...id, status: 'absent', note: '系统上现在没有这一份' }); continue; }
    const hash = crypto.createHash('sha256').update(body).digest('hex');
    const facts = {
      digest: `sha256:${hash.slice(0, 16)}`,
      sha256: hash,
      origin: `${w.no}/${w.attachment ? `attachments/${w.attachment}` : w.body}`,
      bytes: Buffer.byteLength(body, 'utf-8'),
    };
    const stored = w.role ? storedVersions(root, w.role, w.no).find(v => v.body === body) : null;
    if (stored) { items.push({ ...id, status: 'same', note: `与来源 ${stored.dir} 逐字相同`, ...facts }); continue; }
    const same = w.local.find(rel => readOr(path.join(root, rel)) === body);
    if (same) { items.push({ ...id, status: 'same', note: `与本地 ${same} 逐字相同`, ...facts }); continue; }
    const dir = w.dir || outDir;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, w.saveAs ?? w.name), body, 'utf-8');
    items.push({ ...id, status: 'fetched',
      saved: path.relative(root, path.join(dir, w.saveAs ?? w.name)).split(path.sep).join('/'), ...facts });
  }
  const receipt = { mode: 'fetch', reqNo, parentNo: srNo, rrNo, fetchedAt: new Date().toISOString(), items };
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(src, 'fetched.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  const upstream = items.filter(i => i.role && i.status === 'fetched');
  if (upstream.length) {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, '.receipt.json'),
      `${JSON.stringify({ ...receipt, items: items.filter(i => i.role) }, null, 2)}\n`, 'utf-8');
  }
  const failed = items.filter(i => i.status === 'failed').length;
  log(`取回 ${upstream.length} 份上游正文到 ${outDir}${failed ? `，${failed} 份读取失败` : ''}；一个业务文件都没动`);
  return { out: outDir, fetched: items.filter(i => i.status === 'fetched').length, failed, parentNo: srNo, rrNo, items };
}

module.exports = { fetchUpstream };
