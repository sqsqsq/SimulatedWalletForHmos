/**
 * dirs.js — 目录路径常量与路径函数，所有命令共用。
 *
 * 工程根：命令行带 `--project-root <abs>` 时用它；不带时从本文件上溯到实例根——
 * 本文件住在 <实例根>/doc/extensions/skills/story/scripts/adapters/，
 * adapters → scripts → story → skills → extensions → doc → 实例根，共六级。
 *
 * 需求目录下的备份分两类，都在 `.backups/` 下：
 *   .backups/cloud/  需求系统拉取内容的备份（归档覆盖系统正文前从系统取下的那一版，restore 从这里取）
 *   .backups/local/  本地文档的备份（core 覆盖本地文件前的旧内容）
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

function argValue(name) {
  const at = process.argv.indexOf(name);
  return at >= 0 ? process.argv[at + 1] : undefined;
}

const PROJECT_ROOT = path.resolve(
  argValue('--project-root') ?? path.join(__dirname, '..', '..', '..', '..', '..', '..'));

function readFeaturesDir(root) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(root, 'framework.config.json'), 'utf-8'));
    const dir = cfg.paths && cfg.paths.features_dir;
    if (typeof dir === 'string' && dir.trim()) return dir.trim();
  } catch (_) {
    /* 没有配置就用默认 */
  }
  return 'doc/features';
}

const FEATURES_DIR = path.join(PROJECT_ROOT, readFeaturesDir(PROJECT_ROOT));

/** 需求目录：`<features>/<单号>`。 */
function featureDir(reqNo) {
  return path.join(FEATURES_DIR, reqNo);
}

/** 需求目录下某一级单据的目录：`<features>/<AR>/<AR|SR|RR>`。 */
function levelDir(baseReqNo, dirType) {
  return path.join(featureDir(baseReqNo), dirType);
}

/** 需求系统拉取内容的备份目录：`<features>/<AR>/.backups/cloud`。 */
function cloudBackupDir(reqNo) {
  return path.join(featureDir(reqNo), '.backups', 'cloud');
}

/** 本地时间戳（备份文件名用），形如 20260924123456。 */
function timestamp() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
    + `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

module.exports = { PROJECT_ROOT, FEATURES_DIR, featureDir, levelDir, cloudBackupDir, timestamp };
