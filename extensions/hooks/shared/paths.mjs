/**
 * 路径解析 —— 扩展根、feature 根（原生身份）、配置读取。
 *
 * 所有路径从 `framework.config.json` 现取，取不到用框架默认值；**不写死任何工程路径**
 * （硬编码路径会在配置变更时静默失效）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureDir, featureIdentity } from './framework-access.mjs';

/** 读实例配置；文件缺失或坏 JSON 都返回 null，由调用方决定降级还是出声。 */
function readConfig(projectRoot) {
  try {
    return JSON.parse(fs.readFileSync(path.join(projectRoot, 'framework.config.json'), 'utf-8'));
  } catch {
    return null;
  }
}

/** 扩展根目录（`paths.extension_dir`，默认 `doc/extensions`）。 */
export function extensionRoot(projectRoot) {
  const rel = readConfig(projectRoot)?.paths?.extension_dir ?? 'doc/extensions';
  return path.join(projectRoot, ...String(rel).split(/[\\/]/).filter(Boolean));
}

//: 原生 `feature-identity.js` 的施工单位前缀：只有带它的身份才编码了蓝图与施工单位
const CU_PREFIX = 'cu-';

/**
 * 某个逻辑 Feature 的物理目录。施工单位（`cu-` 前缀）按原生身份解析到它的蓝图下；其余身份在原生规则里是
 * `paths.features_dir` 下的同名目录（`featureRelativePath` 原样返回），直接按配置取，不为此加载原生模块。
 * 施工单位身份认不出时照原生的问题抛错，不回落默认目录。
 */
export function featureRoot(projectRoot, feature) {
  if (!String(feature).startsWith(CU_PREFIX)) {
    const rel = readConfig(projectRoot)?.paths?.features_dir;
    const dir = typeof rel === 'string' && rel.trim() ? rel.trim() : 'doc/features';
    return path.join(projectRoot, ...dir.split(/[\\/]/).filter(Boolean), String(feature));
  }
  const dir = featureDir(projectRoot, feature);
  if (!dir) {
    const why = featureIdentity(projectRoot, feature).issues?.map(i => i.message).join('；');
    throw new Error(`Feature ${feature} 的原生身份认不出${why ? `（${why}）` : ''}`);
  }
  return dir;
}

/** 相对仓库根的展示路径（报错文案里用，跨平台统一正斜杠）。 */
export function relDisplay(projectRoot, abs) {
  return path.relative(projectRoot, abs).replace(/\\/g, '/');
}

/** 读文本；不存在返回 null（调用方判断该降级还是该出声）。 */
export function readTextOrNull(abs) {
  try {
    return fs.readFileSync(abs, 'utf-8');
  } catch {
    return null;
  }
}

/** 读一份 JSON。读不出、解析不动都当作「没有」——调用方据此走缺省路径。 */
export function readJsonOrNull(abs) {
  const raw = readTextOrNull(abs);
  if (raw === null) return null;
  try {
    return JSON.parse(raw.replace(/^\ufeff/, ''));
  } catch {
    return null;
  }
}

export function lines(text) {
  return String(text ?? '').split(/\r?\n/);
}
