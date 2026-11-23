/**
 * fetch.js — 取单据：起单与 update 都只读取材，`fetch` 一个业务文件都不写。
 *
 * fetchUpstream(reqNo, mcpToken, { outDir }) → 回执
 *   把这张单现在关联的上游正文（本单 AR、它挂的 SR、SR 挂的 RR）、评审回稿与附件取回。
 *   三份正文写进 outDir（本单来源收件箱下的一个取材批次），批次里写 `.receipt.json`：
 *   reqNo / parentNo / rrNo 与逐件的 role、ticket、title、origin、status、saved——导入按它认来源。
 *
 *   **先认交付件的来源，再比字节**：本单已有真实发布记录与发布的 Story 备份时，系统上的本单正文是交付回流表面，
 *   不再当 AR 需求原件送材料导入。这样取回的原件与回执写进现收件箱的评审用途区
 *   `inbox/review/<同一取材批次>/`：`AR-design.md`、评审回稿与评审记录附件都在那里，
 *   该批次另有自己的 `.receipt.json`；它们不带 role，不进材料批次的回执。即使某一份恰好等于
 *   旧 AR 原件或当前本地 Story，这次回流身份也照记——系统同一正文接口没有额外身份时，不凭内容变化宣布它是新的权威 AR。
 *   首次未发布的本单正文仍是 AR 原件，RR/SR 仍按原材料导入。
 *
 *   其余落点照旧：外部当前状态另写 `AR/story-src/fetched.json`，带取材时刻 fetchedAt、这张单的交付要求
 *   `delivery_requirements: {design_reference}` 与当次评审批次 `review_out`；评审回稿、历史评审附件与设计参考附件
 *   都进该评审批次（含失败与系统上没有的逐件结果），材料导入不读它。
 *   每份的 status 四态分开：
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

/** 材料索引里同一来源（角色 + 单号）最新登记的那一版原件：取回的内容与它逐字相同就不再落盘。
 * 只比最新一版——系统上改回了旧内容，这一次取得的就是新版本。 */
function latestStored(root, role, ticket) {
  let index;
  try { index = JSON.parse(readOr(path.join(root, 'AR', 'story-src', 'materials.json')) ?? 'null'); } catch { index = null; }
  const source = (index?.sources ?? []).find(s => s?.source_id === `system:${role}:${ticket}`);
  const v = source?.versions?.at(-1);
  return v ? { dir: v.dir, body: readOr(path.join(root, ...String(v.original?.path ?? '').split('/'))) } : null;
}

/** 读取必需为合法对象的本地状态 JSON；不存在返回 null，不可读或损坏时在写前报错、保留原件。 */
function readJsonStrict(root, rel, reason) {
  const file = path.join(root, ...rel.split('/'));
  if (!fs.existsSync(file)) return null;
  let raw;
  try { raw = fs.readFileSync(file, 'utf-8'); } catch (e) {
    throw new Error(`${rel} 读不出来（${e.message}）：${reason}；已保留原件且未写本次回执，请先按既有归档/恢复责任核清`);
  }
  let doc;
  try { doc = JSON.parse(raw); } catch (e) {
    throw new Error(`${rel} 不是合法 JSON（${e.message}）：${reason}；已保留原件且未写本次回执，请先按既有归档/恢复责任核清`);
  }
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
    throw new Error(`${rel} 顶层不是 JSON 对象：${reason}；已保留原件且未写本次回执，请先按既有归档/恢复责任核清`);
  }
  return doc;
}

/**
 * 写前核清本单的发布与覆盖身份：
 * - 未发布且无未恢复正文覆盖 → 首次取材（AR 原件）；
 * - 契约 `archived` 与 `.backups/published/story.md` 双证成立，或旧回执 `body_write` 表明已真实覆盖且未记恢复 → 交付回流表面；
 * - 任一状态文件损坏、发布双证冲突或覆盖前备份缺失 → 在写入任何批次/回执前报错，保留原件并指回既有归档/恢复责任。
 */
function publishedBefore(root) {
  const contractRel = 'AR/story-src/story-flow.json';
  const receiptRel = 'AR/story-src/fetched.json';
  const backupRel = '.backups/published/story.md';
  const contract = readJsonStrict(root, contractRel, '无法核清发布身份，不能按首次 AR 取材');
  const prev = readJsonStrict(root, receiptRel, '旧取材回执可能带有正文覆盖与恢复凭据（body_write），不能直接覆盖');
  const hasBackup = fs.existsSync(path.join(root, ...backupRel.split('/')));
  const archived = Boolean(contract?.archived);
  if (archived && !hasBackup) {
    throw new Error(`${contractRel} 已记发布（archived）但 ${backupRel} 缺失：发布身份不完整，不能按首次 AR 取材；`
      + '已保留原件且未写本次回执，请先按既有归档/恢复责任补齐或核清');
  }
  if (!archived && hasBackup) {
    throw new Error(`${backupRel} 已存在但 ${contractRel} 缺失或未记发布（archived）：发布身份冲突，不能按首次 AR 取材；`
      + '已保留原件且未写本次回执，请先按既有归档/恢复责任核清');
  }
  const kept = prev?.body_write ?? null;
  if (kept !== null && (typeof kept !== 'object' || Array.isArray(kept))) {
    throw new Error(`${receiptRel} 的 body_write 形态损坏：无法核实正文覆盖恢复凭据；`
      + '已保留原件且未写本次回执，请先按既有归档/恢复责任核清');
  }
  if (kept?.backup && !fs.existsSync(path.join(root, ...String(kept.backup).split('/')))) {
    throw new Error(`${receiptRel} 的 body_write 指向备份 ${kept.backup}，但该文件缺失：无法核实远端恢复凭据；`
      + '已保留原件且未写本次回执，请先按既有归档/恢复责任核清');
  }
  const restored = contract?.restored;
  const restoredPartial = Boolean(
    kept && restored && restored.backup && kept.backup && restored.backup === kept.backup
    && (!kept.written_at || Date.parse(restored.at) >= Date.parse(kept.written_at)),
  );
  return { published: (archived && hasBackup) || Boolean(kept && !archived && !restoredPartial), kept };
}

async function fetchUpstream(reqNo, mcpToken, { outDir }) {
  const root = featureDir(reqNo);
  const { published, kept } = publishedBefore(root);
  const detail = await getDetail(reqNo, mcpToken);
  const srNo = text(detail.parentNo);
  const srDetail = srNo ? await getDetail(srNo, mcpToken) : null;
  const rrNo = text(detail.rrNo) ?? text(srDetail?.parentNo) ?? text(srDetail?.rrNo);
  const rrDetail = rrNo ? await getDetail(rrNo, mcpToken) : null;
  const src = path.join(root, 'AR', 'story-src');
  // 评审用途区按同一次取材的批次名落：系统取材写在哪一批，这批的回流件与回执就在同名的 review 子树里
  const reviewDir = path.join(root, 'inbox', 'review', path.basename(outDir));
  const wanted = [
    { name: 'AR-design.md', role: 'AR', label: '开发需求正文（本单）', no: reqNo, title: text(detail.title), body: 'design.md',
      local: ['AR/story.md'] },
    { name: 'SR-design.md', role: 'SR', label: '系统设计正文', no: srNo, title: text(srDetail?.title), body: 'design.md', local: [],
      missing: '本单详情没有给出上一级系统设计单号' },
    { name: 'RR-prd.md', role: 'RR', label: '产品需求正文', no: rrNo, title: text(rrDetail?.title), body: 'prd.md', local: [],
      missing: '本单与系统设计单都没有给出产品需求单号' },
    { name: 'review-feedback.md', label: '评审人留下的回稿', no: reqNo, body: 'review-feedback.md', local: [] },
    { name: 'review.md', label: '评审记录附件', no: reqNo, attachment: 'review.md', local: [], saveAs: 'review.md' },
    { name: 'design-review.md', label: '设计参考附件', no: reqNo, attachment: 'design-review.md', local: [] },
  ];
  // 交付回流的评审输入：系统改过的本单正文（发布过才是交付回流）、评审回稿、历史评审附件
  // 与设计参考附件都进评审用途区，不带 role 进材料导入；显式回稿与历史附件无论发布过没有都是
  // 这一轮的评审输入原件。设计参考附件同时是交付项与评审输入：系统上的那份也可能被别人改过。
  const reviewNames = new Set(['AR-design.md', 'review-feedback.md', 'review.md', 'design-review.md']);
  const items = [];
  const reviewItems = [];
  for (const w of wanted) {
    const id = { name: w.name, label: w.label, ticket: w.no || null, ...(w.role ? { role: w.role, title: w.title } : {}) };
    const reviewInput = reviewNames.has(w.name) && (w.name !== 'AR-design.md' || published);
    if (!w.no) {
      items.push({ ...id, status: 'absent', note: w.missing ?? '这张单上没有挂它' });
      if (reviewInput) reviewItems.push({ ...id, status: 'absent', note: w.missing ?? '这张单上没有挂它' });
      continue;
    }
    let body;
    try {
      body = w.attachment
        ? await callMcp(ATTACHMENT_URL, 'getAttachment', { reqNo: w.no, name: w.attachment }, mcpToken)
        : await getBody(w.no, w.body, mcpToken);
    } catch (e) {
      items.push({ ...id, status: 'failed', note: e.message });
      if (reviewInput) reviewItems.push({ ...id, status: 'failed', note: e.message });
      continue;
    }
    if (body === null) {
      items.push({ ...id, status: 'absent', note: '系统上现在没有这一份' });
      if (reviewInput) reviewItems.push({ ...id, status: 'absent', note: '系统上现在没有这一份' });
      continue;
    }
    const hash = crypto.createHash('sha256').update(body).digest('hex');
    const facts = {
      digest: `sha256:${hash.slice(0, 16)}`,
      sha256: hash,
      origin: `${w.no}/${w.attachment ? `attachments/${w.attachment}` : w.body}`,
      bytes: Buffer.byteLength(body, 'utf-8'),
    };
    if (reviewInput) {
      // 回流身份先于字节比较：与旧原件或本地 Story 相同也照记，后续按批次保留不覆盖
      fs.mkdirSync(reviewDir, { recursive: true });
      const saved = path.relative(root, path.join(reviewDir, w.name)).split(path.sep).join('/');
      fs.writeFileSync(path.join(reviewDir, w.name), body, 'utf-8');
      const row = { name: id.name, label: w.name === 'AR-design.md' ? '交付回流的 Story（被改交付件）'
        : w.name === 'design-review.md' ? '系统上的设计参考附件' : w.label,
        ticket: id.ticket, ...(id.title ? { title: id.title } : {}), status: 'fetched', saved, ...facts };
      items.push(row);
      reviewItems.push(row);
      continue;
    }
    const last = w.role ? latestStored(root, w.role, w.no) : null;
    const stored = last && last.body === body ? last : null;
    if (stored) { items.push({ ...id, status: 'same', note: `与来源 ${stored.dir} 逐字相同`, ...facts }); continue; }
    const same = w.local.find(rel => readOr(path.join(root, rel)) === body);
    if (same) { items.push({ ...id, status: 'same', note: `与本地 ${same} 逐字相同`, ...facts }); continue; }
    const dir = w.dir || outDir;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, w.saveAs ?? w.name), body, 'utf-8');
    items.push({ ...id, status: 'fetched',
      saved: path.relative(root, path.join(dir, w.saveAs ?? w.name)).split(path.sep).join('/'), ...facts });
  }
  // 最近一次真实的正文覆盖（归档写下）已在写前通过 publishedBefore 严格读出并校验：刷新外部现状时原样带着
  const fetchedAt = new Date().toISOString();
  // 只有真的取得或读取失败才建评审批次；系统上本来就没有的件不因此建一个空批次
  const reviewOut = reviewItems.some(i => i.status !== 'absent')
    ? path.relative(root, reviewDir).split(path.sep).join('/') : null;
  const receipt = { mode: 'fetch', reqNo, parentNo: srNo, rrNo, fetchedAt,
    delivery_requirements: { design_reference: detail.design_reference_required === true }, items,
    ...(reviewOut ? { review_out: reviewOut } : {}),
    ...(published ? { delivery_return: true } : {}),
    ...(kept ? { body_write: kept } : {}) };
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(src, 'fetched.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  const upstream = items.filter(i => i.role && i.status === 'fetched');
  if (upstream.length) {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, '.receipt.json'),
      `${JSON.stringify({ ...receipt, items: items.filter(i => i.role) }, null, 2)}\n`, 'utf-8');
  }
  if (reviewOut) {
    // 评审用途区的批次回执：update 按它认每一件的系统身份、来源与摘要；材料导入不读它。
    // 失败与系统上没有的件也写进来——它们是这一批的实际结果，不能只记成功的。
    fs.mkdirSync(reviewDir, { recursive: true });
    fs.writeFileSync(path.join(reviewDir, '.receipt.json'),
      `${JSON.stringify({ ...receipt, items: reviewItems }, null, 2)}\n`, 'utf-8');
  }
  const failed = items.filter(i => i.status === 'failed').length;
  log(`取回 ${upstream.length} 份上游正文到 ${outDir}`
    + `${reviewItems.length ? `、${reviewItems.length} 份交付回流件到 ${reviewDir}` : ''}`
    + `${failed ? `，${failed} 份读取失败` : ''}；一个业务文件都没动`);
  return { out: outDir, fetched: items.filter(i => i.status === 'fetched').length, failed, parentNo: srNo, rrNo, items,
    ...(reviewOut ? { review_out: reviewDir } : {}) };
}

module.exports = { fetchUpstream };