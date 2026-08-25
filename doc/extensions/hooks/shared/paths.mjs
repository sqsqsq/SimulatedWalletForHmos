/**
 * 路径解析 —— 扩展根、feature 根、配置读取。
 *
 * 所有路径从 `framework.config.json` 现取，取不到用框架默认值；**不写死任何工程路径**
 * （硬编码路径会在配置变更时静默失效）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';

/** 读实例配置；文件缺失或坏 JSON 都返回 null，由调用方决定降级还是出声。 */
export function readConfig(projectRoot) {
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

/** feature 归档根（`paths.features_dir`，默认 `doc/features`）。 */
export function featuresDir(projectRoot) {
  const rel = readConfig(projectRoot)?.paths?.features_dir ?? 'doc/features';
  return path.join(projectRoot, ...String(rel).split(/[\\/]/).filter(Boolean));
}

/** 某个 feature 的根目录。 */
export function featureRoot(projectRoot, feature) {
  return path.join(featuresDir(projectRoot), feature);
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

/** 一律 `\r?\n` 分行——按 '\n' 切行会让 CRLF 文件的行尾带 `\r`，正则静默零命中。 */
export function lines(text) {
  return String(text ?? '').split(/\r?\n/);
}
