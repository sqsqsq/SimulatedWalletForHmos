/**
 * review 阶段 post_check（实例扩展）—— 逐处落点留证。
 *
 * 本阶段的机械判据：**契约里每条 `must`（一处落点）在审查报告里都有一行结论**，
 * 行按 `rule` + 落点定位。同一规约挂在两处，就是两行；只写一处，另一处仍是未覆盖。
 *
 * 为什么要求「不适用」也写出来：缺席与「做过但没写」在产物上事后完全同形，
 * 而只有前者是缺陷。静默跳过让二者无法区分，于是所有人都只能假设它做过了。
 *
 * 「未落实」的后果按规约声明的强制力：红线阻断，基线要写依据，建议不拦。
 * 结论对不对（落实位置是不是真的落实了）是语义判断，归 overlay 的语义判据。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import { readContracts } from '../shared/contracts.mjs';
import { activeKnowledge, entryById } from '../shared/knowledge.mjs';
import { obligationsFromContracts, patternRolesFromContracts } from '../shared/obligations.mjs';
import { guard, gate } from '../shared/gate.mjs';

const SECTION_TITLE = '知识义务复核';
const VERDICTS = ['落实', '未落实', '不适用'];

/** 按列名取单元格——列序会随编辑漂移，列名才是契约。去掉强调与代码标记后比。 */
function cellOf(cells, headers, keyword) {
  const i = (headers ?? []).findIndex(h => h.includes(keyword));
  return i >= 0 && i < cells.length ? cells[i].replace(/[`*]/g, '').trim() : '';
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
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return gate(ctx, { problems: [error] });
  if (!exists) {
    return gate(ctx, { skipped: [{ what: '知识义务复核表', why: '契约还没建（或读不到）' }] });
  }
  const obligations = obligationsFromContracts(contracts);
  const roles = patternRolesFromContracts(contracts);
  if (!obligations.length && !roles.length) {
    return gate(ctx, { skipped: [{ what: '知识义务复核表', why: '契约里没有 must，也没有标 pattern 的文件' }] });
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
      problems: [`审查报告缺「${SECTION_TITLE}」表——契约里每条 must 一行结论。`
        + '形态：| rule | 落点（契约实体） | 落实位置（文件:符号） | 结论（落实/未落实/不适用） | 依据 |'
        + '；「不适用」也要写，缺席与「做过但没写」事后完全同形，而只有前者是缺陷'],
      inputs: [reportPath],
    });
  }

  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    return gate(ctx, { problems: [`激活知识派生失败：${e.message}`], inputs: [reportPath] });
  }

  const problems = [];
  const col = (row, keyword) => cellOf(row.cells, table.headers, keyword);
  for (const ob of obligations) {
    if (!ob.rule) continue;
    const where = `义务 ${ob.rule}（${ob.entityPath}）`;
    const row = table.data.find(r => col(r, 'rule') === ob.rule && col(r, '落点') === ob.entityPath);
    if (!row) {
      problems.push(`${where} 在复核表里没有对应行——一处落点一行：rule 列写编号，落点列写 ${ob.entityPath}；`
        + '同一规约的另一处落点有结论代替不了这一处，哪怕这一处是「不适用 + 理由」');
      continue;
    }
    const verdict = col(row, '结论');
    if (!VERDICTS.includes(verdict)) {
      problems.push(`${where} 的结论列是「${verdict}」——只写 ${VERDICTS.join(' / ')} 之一`);
      continue;
    }
    const force = entryById(knowledge, ob.rule)?.force;
    if (verdict === '未落实' && force === '红线') {
      problems.push(`${where} 判「未落实」，这条规约是红线——回 coding 落实，红线不能带着未落实交付`);
      continue;
    }
    // 依据只看**依据列**——把落实位置列算进来会让「不适用 + 空依据」蒙混过关
    // （那一列填着符号名，看着就有内容了）。
    if ((verdict === '不适用' || (verdict === '未落实' && force === '基线'))
      && col(row, '依据').replace(/[|\s—\-]/g, '').length < 6) {
      problems.push(`${where} 判「${verdict}」但依据列是空的——`
        + (verdict === '不适用' ? '「不适用」三个字不构成依据，要写清本次变更为什么碰不到它'
          : '基线可以不做，但要写清为什么这一处没落实、用什么补上'));
    }
  }

  for (const id of new Set(roles.map(r => r.pattern).filter(Boolean))) {
    if (!table.data.some(r => r.joined.includes(id))) {
      problems.push(`采用的模式 ${id} 在复核表里没有对应行`
        + '——契约里有文件标了它，本阶段就要核实现是否按这个结构落');
    }
  }

  return gate(ctx, {
    problems,
    inputs: [reportPath],
    fix: '处置：在审查报告补齐复核表，或回 plan 修正 must 后重跑。',
  });
});
