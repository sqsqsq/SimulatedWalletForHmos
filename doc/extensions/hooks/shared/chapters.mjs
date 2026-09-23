/**
 * 章号核对 —— 主章的号以目标 profile 的模板为准，模板里不编号的章不计入序号。
 *
 * 模板经 profile 的 skill 资产清单取得（`framework.config.json > project_profile.name`
 * → `profiles/<名>/skills/skill-assets.yaml`），不写死某个 profile 的路径。扩展追加的章
 * 由扩展自己的模板给号。只核与模板同名的主章，以及带号子节与父章的对应；
 * 正文里合法的自定义小节不管。
 */
import * as path from 'node:path';
import { extensionRoot, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { parseDocument } from '../../skills/story/scripts/core/story/document.mjs';

const NUMBER = /^(\d+(?:\.\d+)*)\.?\s+/;

/**
 * 目标 profile 里某个 skill 资产的正文。
 * 没配 profile 是合法的「不适用」（`skip`）；配了却读不到清单、键或文件、清单解析失败，是输入坏了（`problem`）。
 * @returns {{text?: string, skip?: string, problem?: string}}
 */
export function profileAsset(projectRoot, skill, key) {
  // 配置自己读：解析失败作为输入问题报出，与未配置 profile 分开
  const raw = readTextOrNull(path.join(projectRoot, 'framework.config.json'));
  let config = {};
  try { config = raw === null ? {} : JSON.parse(raw.replace(/^\uFEFF/, '')); } catch (e) {
    return { problem: `framework.config.json 解析失败：${e.message}` };
  }
  const profile = config?.project_profile?.name;
  if (!profile) return { skip: 'framework.config.json 没有配 project_profile.name，没有模板可对照' };
  const skills = path.join(projectRoot, 'framework', 'profiles', profile, 'skills');
  const where = `framework/profiles/${profile}/skills/skill-assets.yaml`;
  const manifest = readTextOrNull(path.join(skills, 'skill-assets.yaml'));
  if (manifest === null) return { problem: `读不到 ${where}` };
  let rel;
  try { rel = parseYaml(manifest)?.assets?.[skill]?.[key]; } catch (e) { return { problem: `${where} 解析失败：${e.message}` }; }
  if (typeof rel !== 'string') return { problem: `${where} 没有 ${skill}.${key}` };
  const text = readTextOrNull(path.join(skills, skill, rel));
  return text === null ? { problem: `${where} 的 ${skill}.${key} 指向 ${skill}/${rel}，读不到` } : { text };
}

/**
 * 章号核对要的模板：profile 的阶段模板，加扩展为该阶段追加章的模板（有才给）。
 * 取不到时说清缺什么：不适用记进 `skipped`，输入坏了记进 `problems`——都不当「查过且通过」。
 */
export function chapterTemplates(projectRoot, skill, key, extTemplate) {
  const got = profileAsset(projectRoot, skill, key);
  const what = `${skill} 主章号`;
  if (got.skip) return { templates: null, skipped: [{ what, why: got.skip }], problems: [] };
  if (got.problem) return { templates: null, skipped: [], problems: [`${what}核不了：${got.problem}`] };
  if (!extTemplate) return { templates: [got.text], skipped: [], problems: [] };
  const ext = readTextOrNull(path.join(extensionRoot(projectRoot), ...extTemplate.split('/')));
  return ext === null
    ? { templates: null, skipped: [], problems: [`${what}核不了：扩展模板 ${extTemplate} 读不到`] }
    : { templates: [got.text, ext], skipped: [], problems: [] };
}

/** 模板里各主章：名字 → 号（不编号记 null）。 */
function templateChapters(text) {
  const out = new Map();
  for (const h of parseDocument(text).headings) {
    if (h.level === 2) out.set(h.name, NUMBER.exec(h.raw)?.[1] ?? null);
  }
  return out;
}

/**
 * 表里写「号 + 章名」引用本文某一章的格子，号与章名是否对得上本文实际的主章。
 * 只核带号的引用；只写章名、写链接的引用不在这里判。
 *
 * @param {string} text 本文
 * @param {string} column 表头里含这个词的那一列
 */
export function chapterRefProblems(text, column) {
  const doc = parseDocument(text);
  const byNumber = new Map(doc.headings.filter(h => h.level === 2)
    .map(h => [NUMBER.exec(h.raw)?.[1], h.name]).filter(([n]) => n));
  const problems = [];
  for (const t of doc.tables) {
    const i = t.header.findIndex(h => h.includes(column));
    if (i < 0) continue;
    for (const row of t.rows) {
      const m = /^(\d+)[.、]\s*([^（(|]+)/.exec(String(row[i] ?? '').replace(/[`*]/g, '').trim());
      if (!m) continue;
      const name = m[2].trim();
      const actual = byNumber.get(m[1]);
      if (!actual || !(actual.startsWith(name) || name.startsWith(actual))) {
        const real = [...byNumber].find(([, n]) => n.startsWith(name) || name.startsWith(n));
        problems.push(`「${column}」写的「${m[1]}. ${name}」对不上本文的章：`
          + (real ? `「${name}」在本文是第 ${real[0]} 章` : `本文第 ${m[1]} 章是「${actual ?? '（没有）'}」`));
      }
    }
  }
  return [...new Set(problems)];
}

/**
 * 文档的主章号与模板是否一致、带号子节是否挂在同号的父章下。
 *
 * @param {string} text 被核的文档
 * @param {string[]} templates 定义主章的模板正文（framework 模板 + 扩展追加章的模板）
 * @returns {string[]} 问题，每条说清哪一章、应为几
 */
export function chapterNumberProblems(text, templates) {
  const want = new Map();
  for (const t of templates) for (const [name, n] of templateChapters(t)) want.set(name, n);
  const problems = [];
  let parent = [];
  for (const h of parseDocument(text).headings) {
    const got = NUMBER.exec(h.raw)?.[1] ?? null;
    if (h.level === 2) {
      parent = [got];
      if (!want.has(h.name) || want.get(h.name) === got) continue;
      problems.push(want.get(h.name) === null
        ? `「## ${h.raw}」：模板里这一章不编号，不计入章序——去掉「${got}.」，后面各章按模板的号`
        : `「## ${h.raw}」：模板里这一章是第 ${want.get(h.name)} 章，号写成了「${got ?? '无'}」`);
      continue;
    }
    const up = parent[h.level - 3] ?? null;
    parent[h.level - 2] = got;
    parent.length = h.level - 1;
    if (got && up && !got.startsWith(`${up}.`)) {
      problems.push(`「${'#'.repeat(h.level)} ${h.raw}」挂在第 ${up} 章（节）下，号却是 ${got}——子节号以父章号开头`);
    }
  }
  return problems;
}
