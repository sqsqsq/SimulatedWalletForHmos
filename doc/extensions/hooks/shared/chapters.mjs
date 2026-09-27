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
import { childHeading, parseDocument } from '../../skills/story/scripts/core/story/document.mjs';

const NUMBER = /^(\d+(?:\.\d+)*)\.?\s+/;

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
 * 宿主扩展的位置：扩展内容是 framework 模板末尾锚点「宿主扩展治理项」的下一级小节，锚点之后只有附录，附录之后只有附录。
 * 规约约束要求与设计模式候选登记对所有需求生效；技术契约只在走 /story 时要求。
 */
export function hostAnchorProblems(text, isStory, formDoc) {
  const doc = parseDocument(text);
  const problems = [];
  const anchor = doc.headings.find(h => h.level === 2 && /^宿主扩展治理项/.test(h.name));
  const children = [[/规约约束要求/, '规约约束要求'], [/设计模式候选/, '设计模式候选登记'],
    ...(isStory ? [[/技术契约/, '技术契约']] : [])];
  if (!anchor) {
    problems.push('spec.md 缺「9. 宿主扩展治理项」章——按名字以「宿主扩展治理项」开头的二级标题认；它在「8. 验收标准」之后，'
      + `${children.map(([, n]) => `「${n}」`).join('')}是它的下一级小节（形态见 ${formDoc}）`);
  } else {
    problems.push(...anchorPositionProblems(doc, anchor, '9. 宿主扩展治理项'));
    for (const [re, name] of children) {
      const h = doc.headings.find(x => x.level >= 2 && re.test(x.name));
      if (h && h !== childHeading(doc, anchor, re)) {
        problems.push(`「${'#'.repeat(h.level)} ${h.raw}」：「${name}」要写成「9. 宿主扩展治理项」的下一级小节（9.x）——扩展小节按标题名在这一章的下一级找`);
      }
    }
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
 * 宿主扩展的结构：framework plan 模板末尾的锚点写成「9. 宿主扩展」，之后只有附录；知识决策是它的 9.1、埋点是 9.2；
 * 9.1 下三节——设计模式选型、规约义务、项目知识影响——都要在。层级由找到的父标题推出。
 */
const DECISION_PARTS = ['设计模式选型', '规约义务', '项目知识影响'];

export function hostExtensionProblems(planText, formDoc) {
  const doc = parseDocument(planText);
  const anchor = doc.headings.find(h => h.level === 2 && /^宿主扩展/.test(h.name));
  if (!anchor) {
    return ['plan.md 缺「9. 宿主扩展」章——按名字以「宿主扩展」开头的二级标题认；它在「8. spec 功能映射表」之后，'
      + `「知识决策（设计输入）」是它的 9.1、「埋点」是 9.2（形态见 ${formDoc}）`];
  }
  const position = anchorPositionProblems(doc, anchor, '9. 宿主扩展');
  const decision = childHeading(doc, anchor, /^知识决策/);
  if (!decision) {
    const elsewhere = doc.headings.find(h => /^知识决策/.test(h.name));
    return [...position, elsewhere
      ? `「${'#'.repeat(elsewhere.level)} ${elsewhere.raw}」：「知识决策（设计输入）」不在「9. 宿主扩展」的下一级——知识决策按名字在「宿主扩展」的下一级找，形态是 9.1`
      : 'plan.md「9. 宿主扩展」：下一级缺「9.1 知识决策（设计输入）」——按名字以「知识决策」开头的小节认，设计模式选型、规约义务、项目知识影响三节在它下面'];
  }
  return [...position, ...DECISION_PARTS.filter(name => !childHeading(doc, decision, new RegExp(`^${name}`)))
    .map(name => `plan.md「9.1 知识决策（设计输入）」下缺「${name}」一节——三节按名字开头在知识决策的下一级找，都要在`)];
}
