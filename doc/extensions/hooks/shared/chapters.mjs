/**
 * 章号核对 —— 主章的号以目标 profile 的模板为准，模板里不编号的章不计入序号。
 *
 * 模板经 profile 的 skill 资产清单取得（`framework.config.json > project_profile.name`
 * → `profiles/<名>/skills/skill-assets.yaml`），不写死某个 profile 的路径。扩展追加的章
 * 由扩展自己的模板给号。只核与模板同名的主章，以及带号子节与父章的对应；
 * 正文里合法的自定义小节不管。
 */
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extensionRoot, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { childHeading, headingEnd, parseDocument } from '../../skills/story/scripts/core/story/document.mjs';

const NUMBER = /^(\d+(?:\.\d+)*)\.?\s+/;
//: 本文件所在扩展的根（hooks/shared 的上两级）：扩展模板随机制一起交付。
const OWN_EXTENSION_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/**
 * 目标 profile 里某个 skill 资产的正文。
 * 没配 profile 是合法的「不适用」（`skip`）；配了却读不到清单、键或文件、清单解析失败，是输入坏了（`problem`）。
 * @returns {{text?: string, skip?: string, problem?: string}}
 */
function profileAsset(projectRoot, skill, key) {
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
  if (got.problem) return { templates: null, skipped: [], problems: [`${got.problem}——${what}以 project_profile.name 对应 profile 的 skill-assets.yaml 登记的阶段模板为准，取不到模板就核不了`] };
  if (!extTemplate) return { templates: [got.text], skipped: [], problems: [] };
  const ext = readTextOrNull(path.join(extensionRoot(projectRoot), ...extTemplate.split('/')));
  return ext === null
    ? { templates: null, skipped: [], problems: [`扩展模板 ${extTemplate} 读不到——${what}里扩展追加的章以这份模板给号，读不到就核不了`] }
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
        problems.push(`「${column}」列的「${m[1]}. ${name}」对不上本文的章：`
          + (real ? `「${name}」在本文是第 ${real[0]} 章` : `本文第 ${m[1]} 章是「${actual ?? '（没有）'}」`)
          + '——带号引用按「号. 章名」与本文的二级标题比对，号与章名指同一章');
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
        ? `「## ${h.raw}」：模板里这一章不编号，这里写了「${got}.」——主章号以模板为准，模板里不编号的章不计入章序，后面各章按模板的号`
        : `「## ${h.raw}」：模板里这一章是第 ${want.get(h.name)} 章，号写成了「${got ?? '无'}」——主章号以 profile 模板与扩展模板为准，按章名对照`);
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

/**
 * 扩展章在全文的位置：framework 模板末尾的锚点章之后只有附录。spec 与 plan 共用这一条——
 * 两边第 8 章不是同一章，按章号认要各写一套；「之后只有附录」对两边都成立。
 */
function anchorPositionProblems(doc, anchor, name) {
  const h2 = doc.headings.filter(h => h.level === 2);
  const at = h2.indexOf(anchor);
  const after = h2.slice(at + 1).filter(h => !/^附录/.test(h.name));
  if (!after.length) return [];
  const where = `「${anchor.raw}」：位于`
    + (at > 0 ? `「${h2[at - 1].raw}」之后，` : '全文第一章，');
  // 带章号的是设计章，要在扩展章之前；不带章号的（修正记录之类）是附录内容
  const design = after.filter(h => NUMBER.test(h.raw));
  const other = after.filter(h => !design.includes(h));
  const list = hs => `「${hs.map(h => h.raw).join('」「')}」`;
  return [design.length && `${where}后面还有设计章${list(design)}——「${name}」在最后一个设计章之后、附录之前，带章号的二级标题按设计章判`,
    other.length && `${where}后面还有${list(other)}——「${name}」之后只有附录，不带章号的二级标题按附录内容判，位置是附录下的一节`].filter(Boolean);
}

/**
 * 扩展章下有哪几节、什么顺序 —— **只在扩展模板里定义**：模板里宿主扩展那一章（第一个二级标题）的
 * 下一级标题，去掉号就是节名。门禁、投影与作者页都按这些节名认，不按节号。
 * 模板随机制一起交付，按本文件所在的扩展目录取。
 *
 * @param {string} templateRel 相对扩展根的模板路径
 * @returns {{names: string[], problems: string[]}}
 */
export function templateSections(templateRel) {
  const text = readTextOrNull(path.join(OWN_EXTENSION_ROOT, ...templateRel.split('/')));
  if (text === null) return { names: [], problems: [`扩展模板 ${templateRel} 读不到——扩展章有哪几节、什么顺序以这份模板为准，读不到就核不了`] };
  const doc = parseDocument(text);
  const anchor = doc.headings.find(h => h.level === 2);
  const names = anchor
    ? doc.headings.filter(h => h.level === anchor.level + 1 && h.at > anchor.at && h.at < headingEnd(doc, anchor)).map(h => h.name)
    : [];
  return names.length ? { names, problems: [] }
    : { names, problems: [`扩展模板 ${templateRel} 里没有扩展章的小节——扩展章的节名取模板第一个二级标题的下一级标题`] };
}

/**
 * 扩展章的小节：`wanted` 里的每一节都是锚点章的下一级（按节名认），几节的先后按模板顺序 `sections`。
 * 找得到而不在下一级的报位置，找不到的报缺；只核节名与层级，内容各节自己的判据管。
 */
function sectionProblems(doc, anchor, title, sections, wanted, formDoc) {
  const problems = [];
  const list = `「${sections.join('」「')}」`;
  for (const name of wanted) {
    if (childHeading(doc, anchor, new RegExp(`^${name}$`))) continue;
    const elsewhere = doc.headings.find(h => h.level >= 2 && h.name === name);
    problems.push(elsewhere
      ? `「${'#'.repeat(elsewhere.level)} ${elsewhere.raw}」：「${name}」要写成「${title}」的下一级小节——扩展章的小节按节名在这一章的下一级找，${list}平列（形态见 ${formDoc}）`
      : `「${title}」：下一级缺「${name}」一节——扩展章的小节按节名（标题去掉号之后整名相等）在这一章的下一级找，${list}按这个顺序平列（形态见 ${formDoc}）`);
  }
  const end = headingEnd(doc, anchor);
  const kids = doc.headings.filter(h => h.level === anchor.level + 1 && h.at > anchor.at && h.at < end && sections.includes(h.name));
  const order = kids.map(h => sections.indexOf(h.name));
  if (order.some((v, i) => i && v < order[i - 1])) {
    problems.push(`「${title}」：下一级几节的顺序是「${kids.map(h => h.name).join('」「')}」——扩展章小节的顺序固定为${list}，编号按位置顺排`);
  }
  return problems;
}

/**
 * spec 宿主扩展的位置与小节：扩展内容是 framework 模板末尾锚点「宿主扩展治理项」的下一级小节，
 * 锚点之后只有附录，附录之后只有附录。`sections` 是模板定义的全部节名与顺序，`wanted` 是本需求要写的那几节。
 */
export function hostAnchorProblems(text, sections, wanted, formDoc) {
  const doc = parseDocument(text);
  const problems = [];
  const anchor = doc.headings.find(h => h.level === 2 && /^宿主扩展治理项/.test(h.name));
  if (!anchor) {
    problems.push('spec.md 缺「9. 宿主扩展治理项」章——按名字以「宿主扩展治理项」开头的二级标题认；它在「8. 验收标准」之后，'
      + `${wanted.map(n => `「${n}」`).join('')}是它的下一级小节（形态见 ${formDoc}）`);
  } else {
    problems.push(...anchorPositionProblems(doc, anchor, '9. 宿主扩展治理项'));
    problems.push(...sectionProblems(doc, anchor, '9. 宿主扩展治理项', sections, wanted, formDoc));
  }
  const h2 = doc.headings.filter(h => h.level === 2);
  const appendix = h2.findIndex(h => /^附录/.test(h.name));
  const tail = appendix >= 0 ? h2.slice(appendix + 1).filter(h => !/^附录/.test(h.name)) : [];
  if (tail.length) {
    problems.push(`「${tail.map(h => h.raw).join('」「')}」：排在了附录之后——附录之后只有附录，名字以「附录」开头的二级标题按附录判`);
  }
  return problems;
}

/**
 * plan 宿主扩展的位置与小节：framework plan 模板末尾的锚点写成「9. 宿主扩展」，之后只有附录；
 * `wanted` 里的节（设计输入）都要在它的下一级，几节的先后按模板顺序 `sections`。
 */
export function hostExtensionProblems(planText, sections, wanted, formDoc) {
  const doc = parseDocument(planText);
  const anchor = doc.headings.find(h => h.level === 2 && /^宿主扩展/.test(h.name));
  if (!anchor) {
    return ['plan.md 缺「9. 宿主扩展」章——按名字以「宿主扩展」开头的二级标题认；它在「8. spec 功能映射表」之后，'
      + `${sections.map(n => `「${n}」`).join('')}是它的下一级小节（形态见 ${formDoc}）`];
  }
  return [...anchorPositionProblems(doc, anchor, '9. 宿主扩展'),
    ...sectionProblems(doc, anchor, '9. 宿主扩展', sections, wanted, formDoc)];
}
