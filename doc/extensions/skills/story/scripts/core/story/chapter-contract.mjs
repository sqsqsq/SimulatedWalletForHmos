/**
 * 章节合同的最小必要结构 —— 必要 H3、必要表、章首图与起始种子的唯一解释。
 *
 * 合同（story-chapters.json）每章给 `structure`：`h3` 是必须存在的 H3 节名，
 * `tables` 是必须出现的表（`header` 全列 + `anchor` 认表的第一列，`when` 可给
 * `siblings`），`diagram: "chapter-start"` 表示这一章要有一张图。哪些章要什么
 * 全部是合同数据，这里不写死任何章名或表头——加一条必要结构改合同，代码不动。
 *
 * 边界：只核机械结构与渲染种子。源图对应、全局编号、投影完整性、图片身份、
 * 冻结、语义质量都不在这里；输入是已解析的数据（`facts`），本模块不读磁盘、
 * 不写文件、不输出 stdout、也不导入 story-build 入口。
 */
import { normalizeHeading } from '../headings.mjs';

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
export function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

/** markdown 表的表头列 —— 分隔行上面那一行就是表头。列名剥掉行内标记。 */
function tableHeaders(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const out = [];
  for (let i = 0; i + 1 < lines.length; i += 1) {
    const head = lines[i].trim();
    const sep = lines[i + 1].trim();
    if (!head.startsWith('|') || !/^\|[-: |]+\|$/.test(sep)) continue;
    out.push(head.replace(/^\||\|$/g, '').split('|').map(c => norm(c.replace(/[`*]/g, ''))));
  }
  return out;
}

/** 渲染一张 markdown 表：表头 + 分隔行 + 数据行。 */
export function renderTable(header, rows) {
  return [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`,
    ...rows.map(r => `| ${r.join(' | ')} |`)];
}

/** 全篇正文里的 `###` 小节名（围栏里的不算——那是被引用的样例）。 */
export function subsectionNames(sectionText) {
  const out = [];
  let inFence = false;
  for (const line of String(sectionText ?? '').split(/\r?\n/)) {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue; }
    if (inFence) continue;
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) out.push({ raw: m[1].trim(), name: normalizeHeading(m[1]) });
  }
  return out;
}

/** 从一章的正文里切出某个 `###` 小节。 */
export function subsectionText(sectionText, name) {
  const want = normalizeHeading(name);
  const lines = String(sectionText ?? '').split(/\r?\n/);
  const body = [];
  let hit = false;
  for (const line of lines) {
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) {
      if (hit) break;
      hit = normalizeHeading(m[1]) === want;      // `### A. 接口` 与合同的 `接口` 是同一节
      continue;
    }
    if (hit) body.push(line);
  }
  return hit ? body.join('\n') : null;
}

/**
 * 按名字找一个小节的正文 —— 先精确，再包含。
 *
 * 合同给的是这一节要讲什么，作者按业务命名；精确匹配会把后者判成「缺这一节」。
 */
function findSubsection(text, name) {
  const exact = subsectionText(text, name);
  if (exact !== null) return exact;
  const want = normalizeHeading(name);
  const hit = subsectionNames(text).find(x => x.name.includes(want));
  return hit ? subsectionText(text, hit.name) : null;
}

/**
 * 这一章适用的最小必要 slots。
 *
 * `facts.siblings` 只有三态：`true` 成立、`false` 确证不成立、`null` 拿不准——
 * 拿不准与不成立必须分开：离线的仲裁锚读不到流程契约，`siblings` 若一律算
 * 不成立，带兄弟单据的那一节就会被判成「不该有」。
 */
function requiredSlots(ch, facts) {
  const out = [];
  for (const t of ch?.structure?.tables ?? []) {
    if (t.when === 'siblings' && facts?.siblings === false) continue;
    out.push({ kind: 'table', anchor: t.anchor, header: t.header });
  }
  if (ch?.structure?.diagram) out.push({ kind: 'diagram' });
  return out;
}

const DIAGRAM_FENCE = /^[ \t]*(?:```|~~~)[ \t]*(?:mermaid|plantuml|puml|dot|graphviz)\b/gmi;

/**
 * 这一章的必要结构在不在 —— 返回问题串；正文合法的新形式不因本模块受限。
 *
 * 必要 H3 按名字找（先精确再包含）；必要表按锚列认（按子串比——锚说的是表的
 * 主语，作者用「受限状态」还是「受限情形」是措辞）；表的位置可在章内合理的
 * H3/H4 下，不只看第一张。报错带实际 H3/表头与所在章，不只说「形态不对」。
 */
export function chapterStructureProblems(ch, body, facts) {
  const problems = [];
  const text = String(body ?? '');
  for (const want of ch?.structure?.h3 ?? []) {
    if (findSubsection(text, want) === null) {
      problems.push(`「${ch.title}」缺「${want}」这一节`);
    }
  }
  for (const slot of requiredSlots(ch, facts)) {
    if (slot.kind === 'diagram') {
      DIAGRAM_FENCE.lastIndex = 0;          // 正则带 /g，每次用前把游标归零
      if (!DIAGRAM_FENCE.test(text)) {
        problems.push(`「${ch.title}」章首缺一张覆盖主路径与全部分支去向的总览图`);
      }
      continue;
    }
    const anchor = norm(slot.anchor);
    if (anchor && !tableHeaders(text).some(h => h.some(c => c.includes(anchor)))) {
      problems.push(`「${ch.title}」缺一张表（表头含「${slot.anchor}」）`);
    }
  }
  return problems;
}

/**
 * 这一章从真源打的底 —— **打完就归作者**。
 *
 * 只保留三类：术语起始行、验收与交付的表头、附录五节与材料清单的贡献行。
 * 表头及附录小节名从合同取；术语行/材料清单行来自输入（facts 已解析），这里
 * 不重读源文件。附录 A–D 不预填机器正文——那四节归投影，作者改的是真源。
 * 流程图由作者按当前业务生成，源图材料不是默认的业务总览答案。
 *
 * @param {object} ch 合同章
 * @param {object} facts 入口解析好的当前输入：terms、materialListRows
 * @returns {string[]} markdown 行
 */
export function chapterSeedRows(ch, facts) {
  if (ch.appendix) {
    const out = [];
    for (const name of ch.subsections ?? []) {
      out.push(`### ${name}`, '', '{{一句这一节给评审者看什么}}', '');
      // 材料清单是作者种子：类别与链接由清单给，「贡献了什么」只有他知道。
      // 其余四节由 `project` 投影，草稿里不放——放了他就要在两处维护同一张表。
      if (normalizeHeading(name) === normalizeHeading(facts?.materialListName ?? '')) {
        out.push(...(facts?.materialListRows ?? []), '');
      }
    }
    return out;
  }
  for (const t of ch?.structure?.tables ?? []) {
    if (!t.seed) continue;
    const cells = String(t.header).split('|');
    // 术语起始行来自 spec §0 的真源数据（facts.terms），不是占位；
    // 其余保留的表头（验收、交付）给占位行让作者往下填。
    if (t.seed === 'terms') {
      const terms = facts?.terms ?? [];
      if (!terms.length) continue;
      return renderTable(cells, terms);
    }
    return renderTable(cells, [cells.map(c => `{{${c || '　'}}}`)]);
  }
  return [];
}
