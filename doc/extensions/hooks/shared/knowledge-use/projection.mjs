/**
 * spec §10/§11 的生成区：渲染、写入与只读保护。
 *
 * 这两章的正文只有生成区一份，每一个字节都由本模块写。作者改判断改 YAML，
 * 手改生成区会被门禁按行指出来——人读的表与机器真源各说各话，比不生成更糟。
 */
import { fail, requirements, text } from './document.mjs';

/** 生成区的边界标记。两个标记之间的每一个字节都由本模块写。 */
const BEGIN = '<!-- knowledge-use:begin ';

const END = '<!-- knowledge-use:end -->';

/** 生成区的名字 —— 同时是 spec 里那两章的标题关键词。 */
const ZONES = [
  { key: 'constraints', name: '规约约束要求', heading: /规约约束要求/ },
  { key: 'patterns', name: '设计模式候选登记', heading: /设计模式候选/ },
];

function cell(value) {
  return String(value ?? '').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ').trim();
}

/** §10 的正文：命中条目逐条一行，本轮豁免与整域不适用各列在后面。 */
function renderConstraints(knowledge, use) {
  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const hits = use.constraints.filter(r => r.applicable === true
    && !(byId.get(text(r, 'id'))?.reviewAction));
  const out = [];
  // 强制力与验法从知识派生：plan 挂落点、选证据来源时要的就是这两样，作者不填
  out.push('| 编号 | 强制力 | 本需求的要求 | 落点契约名 | 验法 |');
  out.push('|---|---|---|---|---|');
  if (!hits.some(r => !r.waived)) {
    out.push('| （无命中条目） | — | 本需求没有产生代码要求的规约条目 | — | — |');
  }
  for (const row of hits.filter(r => !r.waived)) {
    // 一条要求一行：同一个编号有几条要求就出几行。挤进一格的话，读者要在
    // 一百多字里数分号，而每一条本来都该独立可懂。
    const entry = byId.get(text(row, 'id'));
    const at = text(row, 'contract') ? `§9 · ${cell(text(row, 'contract'))}`
      : text(row, 'impact') ? `影响 · ${cell(text(row, 'impact'))}` : '—';
    for (const req of requirements(row)) {
      out.push(`| ${cell(text(row, 'id'))} | ${entry?.force ?? '—'} | ${cell(req)} | ${at} `
        + `| ${(entry?.executors ?? []).join(' / ') || '—'} |`);
    }
  }
  const waived = hits.filter(r => r.waived);
  if (waived.length) {
    out.push('', '命中但本轮豁免（评审判）：');
    for (const row of waived) {
      const comp = text(row.waived, 'compensation');
      out.push(`- ${cell(text(row, 'id'))}（${byId.get(text(row, 'id'))?.force ?? ''}）— `
        + `${cell(text(row.waived, 'reason'))}${comp ? ` — 补偿：${cell(comp)}` : ''}`);
    }
  }
  // 命中的评审动作单列：它们不产生代码要求，混进上面那张表读者会当成要写的代码；
  // 从表里删掉又等于说「没命中」，而它确实命中了。
  const actions = use.constraints.filter(r => r.applicable === true
    && byId.get(text(r, 'id'))?.reviewAction);
  if (actions.length) {
    out.push('');
    out.push('评审动作（命中，不产生代码要求）：');
    for (const row of actions) {
      const entry = byId.get(text(row, 'id'));
      const landing = text(row, 'decision') ? ` — 议题 ${cell(text(row, 'decision'))}`
        : text(row, 'impact') ? ` — 由 ${cell(text(row, 'impact'))} 表态` : '';
      out.push(`- ${cell(text(row, 'id'))} — ${cell(entry?.handling ?? '')}`
        + ` — ${cell(text(row, 'reason'))}${landing}`);
    }
  }
  const na = use.constraints.filter(r => r.applicable === false);
  if (use.domains.length || na.length) {
    out.push('');
    out.push('不命中的依据：');
    for (const row of use.domains) {
      out.push(`- 整域 ${cell(text(row, 'prefix'))} 不适用：${cell(text(row, 'reason'))}`);
    }
    for (const row of na) {
      out.push(`- ${cell(text(row, 'id'))}：${cell(text(row, 'reason'))}`);
    }
  }
  return out.join('\n');
}

/** §11 的正文：逐个适用单元一行，只登记不选型。 */
function renderPatterns(knowledge, use) {
  const out = ['| 适用单元 | 候选 | 命中信号或反证 |', '|---|---|---|'];
  for (const row of use.patterns) {
    out.push(`| ${cell(text(row, 'unit'))} | ${cell(text(row, 'candidate'))} `
      + `| ${cell(text(row, 'signal'))} |`);
  }
  return out.join('\n');
}

/** 两个生成区的正文。键与 ZONES 对齐。 */
export function renderZones(knowledge, use) {
  return {
    constraints: renderConstraints(knowledge, use),
    patterns: renderPatterns(knowledge, use),
  };
}

function zoneBlock(zone, body) {
  return `${BEGIN}${zone.name} · 由 spec/knowledge-use.yaml 生成，手改会被门禁拒绝 -->\n`
    + `${body}\n${END}`;
}

/**
 * 从 spec 正文里取出一个生成区。
 *
 * @returns {{found:boolean, body:string|null, start:number, end:number}}
 */
function zoneOf(specText, zone) {
  const head = `${BEGIN}${zone.name} `;
  const start = specText.indexOf(head);
  if (start < 0) return { found: false, body: null, start: -1, end: -1 };
  const bodyStart = specText.indexOf('-->', start);
  const end = specText.indexOf(END, start);
  if (bodyStart < 0 || end < 0) return { found: false, body: null, start, end: -1 };
  return {
    found: true,
    body: specText.slice(bodyStart + 4, end).replace(/\n$/, ''),
    start,
    end: end + END.length,
  };
}

/**
 * 把生成区写进 spec 正文 —— 幂等：已有生成区就整块替换，没有就追加到该章标题之后。
 *
 * 章不存在时不代写标题：那一章该不该在、叫什么名字，由模板定，不由生成器造。
 */
export function applyZones(specText, rendered) {
  let out = specText.replace(/\r\n/g, '\n');
  for (const zone of ZONES) {
    const block = zoneBlock(zone, rendered[zone.key]);
    const found = zoneOf(out, zone);
    if (found.found) {
      out = out.slice(0, found.start) + block + out.slice(found.end);
      continue;
    }
    const rows = out.split(/\r?\n/);
    const idx = rows.findIndex(l => /^#{2,3}\s/.test(l) && zone.heading.test(l));
    if (idx < 0) {
      fail(`spec.md 里找不到「${zone.name}」章 —— 生成器不代写章标题：`
        + '那一章该不该在、叫什么名字由模板定');
    }
    let insert = idx + 1;
    while (insert < rows.length && rows[insert].trim() === '') insert += 1;
    // 章标题后的 HTML 注释是模板给作者的写法说明，生成区排在它之后
    if (rows[insert]?.trimStart().startsWith('<!--') && !rows[insert].includes(BEGIN.trim())) {
      while (insert < rows.length && !rows[insert].includes('-->')) insert += 1;
      insert += 1;
    }
    rows.splice(insert, 0, '', block);
    out = rows.join('\n');
  }
  return out;
}

/**
 * 一章的正文范围：标题行之后到下一个同级或更高级标题之前。
 *
 * @returns {{start:number, end:number}|null} 行下标，左闭右开
 */
function chapterSpan(rows, heading) {
  const start = rows.findIndex(l => /^#{2,3}\s/.test(l) && heading.test(l));
  if (start < 0) return null;
  const level = (rows[start].match(/^#+/) ?? ['##'])[0].length;
  for (let i = start + 1; i < rows.length; i += 1) {
    const m = rows[i].match(/^#+/);
    if (m && m[0].length <= level) return { start: start + 1, end: i };
  }
  return { start: start + 1, end: rows.length };
}

/**
 * 生成区与 YAML 对不对得上 —— 手改生成区、以及生成区之外的另一张表，都在这里被判出来。
 *
 * 这两章的正文只有生成区一份：同一章出现第二张表，就有两处说同一件事，
 * 而只有一处跟着 YAML 走。
 */
export function zoneProblems(projectRoot, specText, rendered) {
  const problems = [];
  const rows = specText.split(/\r?\n/);
  for (const zone of ZONES) {
    const found = zoneOf(specText, zone);
    if (!found.found) {
      problems.push(`spec.md 的「${zone.name}」章没有生成区 —— `
        + '跑 `node doc/extensions/hooks/shared/knowledge-use.mjs render --feature <名>` 生成');
      continue;
    }
    if (found.body !== rendered[zone.key]) {
      problems.push(`spec.md 的「${zone.name}」生成区与 spec/knowledge-use.yaml 对不上 —— `
        + '这一区由 YAML 生成，手改它等于让人读的表与机器真源各说各话。'
        + '改判断请改 YAML，再跑 `knowledge-use.mjs render` 重新生成');
    }
    const span = chapterSpan(rows, zone.heading);
    if (!span) continue;
    let inZone = false;
    const stray = [];
    for (let i = span.start; i < span.end; i += 1) {
      const line = rows[i];
      if (line.includes(BEGIN.trim())) { inZone = true; continue; }
      if (line.includes(END)) { inZone = false; continue; }
      if (!inZone && line.trimStart().startsWith('|')) stray.push(i + 1);
    }
    if (stray.length) {
      problems.push(`spec.md 的「${zone.name}」章在生成区之外还有表`
        + `（第 ${stray.slice(0, 3).join('、')} 行${stray.length > 3 ? ' …' : ''}）`
        + ' —— 这一章的正文只有生成区一份；判断写在 knowledge-use.yaml 里，投影由 render 生成');
    }
  }
  return problems;
}
