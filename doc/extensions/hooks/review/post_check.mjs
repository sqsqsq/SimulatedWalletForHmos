/**
 * review 阶段 post_check（实例扩展）—— 逐义务留证。
 *
 * 本阶段的机械判据只有一条：**每条冻结义务在审查报告里都有一行结论**。
 *
 * 为什么要求「不适用」也写出来：缺席与「做过但没写」在产物上事后完全同形，
 * 而只有前者是缺陷。静默跳过让二者无法区分，于是所有人都只能假设它做过了。
 *
 * 结论对不对（落实位置是不是真的落实了）是语义判断，归 overlay 的语义判据。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import { loadLedger } from '../shared/downstream.mjs';
import { guard, gate } from '../shared/gate.mjs';

const SECTION_TITLE = '知识义务复核';
const VERDICTS = ['落实', '未落实', '不适用'];

/** 按列名取单元格——列序会随编辑漂移，列名才是契约。 */
function cellOf(cells, headers, keyword) {
  const i = (headers ?? []).findIndex(h => h.includes(keyword));
  return i >= 0 && i < cells.length ? cells[i] : '';
}

/** 审查报告里的知识义务复核表。 */
function reviewTable(text) {
  const rows = lines(text);
  const start = rows.findIndex(l => /^#{2,4}\s+.*知识义务复核/.test(l.trim()));
  if (start < 0) return null;
  const level = (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  let headers = null;
  const data = [];
  for (let i = start + 1; i < rows.length; i++) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const s = rows[i].trim();
    if (!s.startsWith('|')) continue;
    const cells = s.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (!headers) { headers = cells; continue; }
    if (cells.every(c => /^[-: ]*$/.test(c))) continue;
    data.push({ line: i + 1, cells, joined: cells.join(' ') });
  }
  return { headers, data };
}

export default guard('review', async (ctx) => {
  const { ok, problem, book } = loadLedger(ctx, 'review');
  if (!ok) {
    return gate(ctx, problem
      ? { problems: [problem] }
      : { skipped: [{ what: '知识义务复核表', why: '契约还没建（或读不到）' }] });
  }
  if (!book.obligations.length && !book.patterns.length) {
    return gate(ctx, { skipped: [{ what: '知识义务复核表', why: '本需求没有冻结义务与模式' }] });
  }

  const reportPath = path.join(featureRoot(ctx.projectRoot, ctx.feature), 'review', 'review-report.md');
  const text = readTextOrNull(reportPath);
  if (text === null) {
    // 报告缺失由框架的 check-review 负责，但本判据确实没跑成，要留痕
    return gate(ctx, { skipped: [{ what: '知识义务复核表', why: '审查报告还没生成' }] });
  }

  const table = reviewTable(text);
  if (!table || !table.data.length) {
    return gate(ctx, {
      problems: [`审查报告缺「${SECTION_TITLE}」表——冻结的每条义务都要有一行结论。`
        + '形态：| rule | 落实位置（文件:符号） | 结论（落实/未落实/不适用） | 依据 |'
        + '；「不适用」也要写，缺席与「做过但没写」事后完全同形，而只有前者是缺陷'],
      inputs: [reportPath],
    });
  }

  const problems = [];
  const covered = new Map();
  for (const row of table.data) {
    for (const m of row.joined.matchAll(/\b[A-Z][A-Z0-9]{1,7}-\d{2}\b/g)) {
      covered.set(m[0], row);
    }
  }

  for (const ob of book.obligations) {
    const rule = String(ob.rule ?? '').trim();
    if (!rule) continue;
    const row = covered.get(rule);
    if (!row) {
      problems.push(`义务 ${rule} 在复核表里没有对应行——每条冻结义务都要有结论，`
        + '哪怕结论是「不适用 + 理由」');
      continue;
    }
    const verdict = VERDICTS.find(v => row.joined.includes(v));
    if (!verdict) {
      problems.push(`义务 ${rule} 的行没有明确结论（须是 ${VERDICTS.join(' / ')} 之一）`);
      continue;
    }
    if (verdict === '不适用') {
      // 依据只看**依据列**——把落实位置列算进来会让「不适用 + 空依据」蒙混过关
      // （那一列填着符号名，看着就有内容了）。
      const reason = cellOf(row.cells, table.headers, '依据');
      const residue = reason.replace(/[|\s—\-]/g, '');
      if (residue.length < 6) {
        problems.push(`义务 ${rule} 标「不适用」但依据列是空的——`
          + '「不适用」三个字不构成依据，要写清本次变更为什么碰不到它');
      }
    }
  }

  for (const p of book.patterns) {
    const id = String(p.pattern_id ?? '').trim();
    if (!id) continue;
    if (!table.data.some(r => r.joined.includes(id))) {
      problems.push(`采用的模式 ${id} 在复核表里没有对应行`
        + '——冻结了它，本阶段就要核实现是否按这个结构落');
    }
  }

  return gate(ctx, {
    problems,
    inputs: [reportPath],
    fix: '处置：在审查报告补齐复核表，或回 plan 修正冻结后重跑。',
  });
});
