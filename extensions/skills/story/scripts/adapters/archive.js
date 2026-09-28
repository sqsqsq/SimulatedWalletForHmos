/**
 * archive.js — 归档：把叙事主件写成系统正文、评审记录传为附件。
 *
 * archiveOne(reqNo, mcpToken, skipBackup?, contentOverride?)
 *   → { archived: true, backupPath, verified, reviewArchived }
 *
 *   ① 覆盖前把系统当前正文备份到 `<需求目录>/.backups/cloud/design-<时刻>.md`（restore 靠它）；
 *      系统上还没有正文时不留空备份。skipBackup 为真时跳过（restore 用）。
 *   ② 系统正文 = contentOverride ?? AR/story.md；③ 附件 = AR/review.md（contentOverride 时不传）。
 *   ④ verified = 系统侧与上传内容逐字一致。
 *   本地只写 `.backups/cloud/`，业务文件一个字节不动。**只上传 md**：系统不承载图片，
 *   正文里的图片链接原样保留。AR/story.md 或 AR/review.md 缺任一即失败，无降级路径。
 *   归档前的校验由 /story 流程在调用前完成，不在这里。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { callMcp, REQUIREMENT_URL, ATTACHMENT_URL } = require('./mcp');
const { featureDir, cloudBackupDir, timestamp } = require('./dirs');

function log(msg) {
  console.error(`[archive.js] ${msg}`);
}

async function archiveOne(reqNo, mcpToken, skipBackup = false, contentOverride = undefined) {
  const root = featureDir(reqNo);
  let body = contentOverride;
  let notes = null;
  if (body === undefined) {
    for (const rel of ['AR/story.md', 'AR/review.md']) {
      if (!fs.existsSync(path.join(root, rel))) {
        throw new Error(`${rel} 不存在，无可归档物：${reqNo}。它是 spec 阶段的产物，请回 spec 补齐后重试。`);
      }
    }
    body = fs.readFileSync(path.join(root, 'AR', 'story.md'), 'utf-8');
    notes = fs.readFileSync(path.join(root, 'AR', 'review.md'), 'utf-8');
  }

  let backupPath = null;
  if (!skipBackup) {
    const current = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken);
    if (current === null) {
      log('系统上尚无正文，本次归档是首次写入，没有可备份的版本');
    } else {
      const dir = cloudBackupDir(reqNo);
      fs.mkdirSync(dir, { recursive: true });
      const file = path.join(dir, `design-${timestamp()}.md`);
      fs.writeFileSync(file, current, 'utf-8');
      backupPath = path.relative(root, file).split(path.sep).join('/');
      log(`系统当前正文已备份：${backupPath}`);
    }
  }

  await callMcp(REQUIREMENT_URL, 'putBody', { reqNo, name: 'design.md', content: body }, mcpToken);
  let reviewArchived = false;
  if (notes !== null) {
    await callMcp(ATTACHMENT_URL, 'putAttachment', { reqNo, name: 'review.md', content: notes }, mcpToken);
    reviewArchived = true;
  }
  const verified = await callMcp(REQUIREMENT_URL, 'getBody', { reqNo, name: 'design.md' }, mcpToken) === body
    && (!reviewArchived
      || await callMcp(ATTACHMENT_URL, 'getAttachment', { reqNo, name: 'review.md' }, mcpToken) === notes);
  log(`归档完成：${reqNo}${reviewArchived ? '（正文 + 评审记录附件）' : '（正文）'}`);
  return { archived: true, backupPath, verified, reviewArchived };
}

module.exports = { archiveOne };
