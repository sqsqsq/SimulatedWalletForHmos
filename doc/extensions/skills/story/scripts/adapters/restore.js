/**
 * restore.js — 回退归档：把最近一次归档前的系统正文写回系统（与内网同名文件，导出同签名的 restoreOne）。
 *
 * restoreOne(reqNo, mcpToken) → { restored: true, verified }
 *   取 `<需求目录>/.backups/cloud/` 里最新的一份，经 archiveOne 的 contentOverride 上传（不再备份）。
 *   没有备份即失败：restore 只在 archive 之后可用。本地业务文件不动。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { archiveOne } = require('./archive');
const { cloudBackupDir } = require('./dirs');

function log(msg) {
  console.error(`[restore.js] ${msg}`);
}

async function restoreOne(reqNo, mcpToken) {
  const dir = cloudBackupDir(reqNo);
  const versions = fs.existsSync(dir)
    ? fs.readdirSync(dir).filter(f => /^design-\d+\.md$/.test(f)).sort()
    : [];
  if (versions.length === 0) {
    throw new Error(`${reqNo} 没有归档前的备份：${dir}（restore 只在 archive 之后可用）`);
  }
  const latest = versions[versions.length - 1];
  const content = fs.readFileSync(path.join(dir, latest), 'utf-8');
  const { verified } = await archiveOne(reqNo, mcpToken, true, content);
  log(`已把系统正文恢复到归档前的版本：.backups/cloud/${latest}`);
  return { restored: true, verified };
}

module.exports = { restoreOne };
