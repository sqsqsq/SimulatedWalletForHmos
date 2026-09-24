/**
 * knowledge-use 的真源文件本身：怎么定位、怎么读、怎么算指纹、骨架长什么样。
 *
 * spec 阶段的知识判断只有这一份真源（`spec/knowledge-use.yaml`）。本模块只管
 * 「文件里现在写的是什么」，判全了没有归 validation，投影成 §10/§11 归 projection。
 *
 * 条目取值的规范化（列表、去空白、要求写成一条还是一列）也在这里唯一维护：
 * 验证与渲染读的是同一份规范化结果，各写一份的话，同一行字会在两边判出两种形态。
 *
 * 激活清单由 `knowledge.mjs` 读，本模块不另解析 manifest。
 */
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { knowledgeFiles } from '../knowledge.mjs';
import { extensionRoot, featureRoot, readTextOrNull, relDisplay } from '../paths.mjs';
import { parseYaml } from '../yaml.mjs';

const SCHEMA = 1;

const USE_FILE = ['spec', 'knowledge-use.yaml'];

export const NO_CANDIDATE = '无候选';

export class UseError extends Error {}

export function fail(message) {
  throw new UseError(message);
}

export function usePath(projectRoot, feature) {
  return path.join(featureRoot(projectRoot, feature), ...USE_FILE);
}

/**
 * 激活清单的指纹 —— 知识变了而这份判断没重做，要看得出来。
 *
 * 算的是**清单里每个文件的内容**，不是 manifest 自己：改 manifest 的注释不该让
 * 全仓需求的判断作废，而改一条规约的正文必须。
 */
export function manifestDigest(projectRoot) {
  const root = extensionRoot(projectRoot);
  const h = createHash('sha256');
  for (const relPosix of knowledgeFiles(projectRoot)) {
    const text = readTextOrNull(path.join(root, ...relPosix.split('/').filter(Boolean)));
    if (text === null) fail(`激活清单登记的文件读不到：${relPosix}`);
    h.update(relPosix).update('\0').update(text.replace(/\r\n/g, '\n')).update('\0');
  }
  return 'sha256:' + h.digest('hex').slice(0, 16);
}

function asList(value, field) {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) fail(`knowledge-use.yaml 的 ${field} 不是列表`);
  return value;
}

export function text(row, field) {
  return String(row?.[field] ?? '').trim();
}

/** 读这份判断。文件不在、坏了、schema 不对，三种都要分得清。 */
export function readUse(projectRoot, feature) {
  const p = usePath(projectRoot, feature);
  const raw = readTextOrNull(p);
  if (raw === null) {
    fail(`缺 ${relDisplay(projectRoot, p)} —— spec 阶段的知识判断写在这里：`
      + 'facts 用了什么、每条规约命中与否、模式有哪些候选。'
      + '它是唯一真源，§10/§11 由它生成');
  }
  let data;
  try {
    data = parseYaml(raw);
  } catch (e) {
    fail(`${relDisplay(projectRoot, p)} 解析失败（解析失败不当作空判断）：${e.message}`);
  }
  if (Number(data?.schema) !== SCHEMA) {
    fail(`${relDisplay(projectRoot, p)} 的 schema 是 ${data?.schema}，本版要求 ${SCHEMA}`);
  }
  return {
    schema: SCHEMA,
    manifestDigest: text(data, 'manifest_digest'),
    facts: asList(data.facts, 'facts'),
    domains: asList(data.constraint_domains, 'constraint_domains'),
    constraints: asList(data.constraints, 'constraints'),
    patterns: asList(data.patterns, 'patterns'),
  };
}

/**
 * 一条条目的要求 —— **列表**，一条一句。
 *
 * 写成一段的时候，读者要在一百多字里数分号才分得出这是几件事，而每一件本来都该
 * 独立可懂。旧写法（单句）照收：那也是一条。
 */
export function requirements(row) {
  const raw = row?.requirement;
  if (Array.isArray(raw)) return raw.map(x => String(x ?? '').trim()).filter(Boolean);
  const one = String(raw ?? '').trim();
  return one ? [one] : [];
}

/**
 * 骨架正文。**只摆结构，不替作者判断**——applicable 留空，依据留空。
 *
 * 说明写进文件本身而不是只写在文档里：作者打开的是这份 YAML，它得自己说清怎么填。
 */
export function renderSkeleton(projectRoot, knowledge) {
  const rows = [
    '# 本阶段知识判断的唯一真源。spec 的 §10/§11 由它生成，那两章不手写。',
    '#',
    '# 怎么填：激活的每一条 constraints 都要有去处——命中写 requirement（列表，一条要求一句，',
    '# 写得下一个人照着能编码），不命中写 reason：命中条件里哪个事实在本需求不成立',
    '# （「不涉及」三个字不算依据；拿处置结果否定命中也不算）。',
    '# contract 引 spec §9 里登记的名字，没有就留空串。填完跑 render。',
    '# 值里有英文冒号加空格（「条件: 结果」）时整句加引号，否则这份 YAML 读不出来。',
    '# 命中但这一轮不做：applicable: true 加 waived 块（下面缩进写 reason 与 compensation）；',
    '# 红线不能豁免，基线要写 compensation，豁免要登记进《决策与评审记录》由评审人表态。',
    `schema: ${SCHEMA}`,
    `manifest_digest: ${manifestDigest(projectRoot)}`,
    '',
    '# 用到了哪几份项目知识：used 逐面一项（facet 取下面列的面名，used_for 写拿它做了什么；',
    '# 面是「未确认」的，补 verified 写核实依据及位置：当前实现引代码或配置，已定规范引协议、需求或负责人确认记录）。没用到的整份删掉。',
    'facts:',
  ];
  for (const f of knowledge.facts) {
    const pending = f.unconfirmed.length ? `（未确认：${f.unconfirmed.join(' / ')}）` : '';
    rows.push(`  - id: ${f.name || path.basename(f.file, '.md')}`,
      `    # 面：${f.facets.join(' / ')}${pending}`, '    used:', '      - facet: ""', '        used_for: ""');
  }
  rows.push(
    '',
    '# 整域都不适用时登记在这里（prefix / applicable: false / reason）。',
    '# 域里只要有一条命中，就不判整域、改为逐条登记到 constraints。',
    'constraint_domains: []',
    '',
    'constraints:',
  );
  const generalOf = new Map(knowledge.constraints.map(c => [c.file, c.general ?? []]));
  let lastFile = null;
  for (const e of knowledge.entries) {
    if (e.file !== lastFile) {
      lastFile = e.file;
      for (const g of generalOf.get(e.file) ?? []) rows.push(`  # ${e.domainTitle}·通则：${g}`);
    }
    // 判命中要的是条目本身：约束原文、命中条件、命中后要给出什么、附注与验法，分行送到这一条下面，
    // 作者不必另开规约文件对照。「命中后要给出」是处置，不是判命中的依据。
    rows.push(`  - id: ${e.id}`,
      `    # ${e.force} · ${e.constraint}`,
      `    # 命中条件：${e.when || '—'}`,
      `    # 命中后要给出：${e.handling || '—'}`,
      ...(e.note ? [`    # 附注：${e.note}`] : []),
      `    # 验法：${e.executors.join(' / ')}`);
    if (e.reviewAction) {
      // 这一条命中也不产生代码要求，填法与别的不同——写在它自己这一行下面，
      // 作者不必先去别处弄清「评审动作」是什么意思才敢填。
      rows.push('    applicable:   # 处置是评审动作：命中与否照判，两种都补 reason；不写 requirement / contract',
        '    #   命中时落点：走 /story 的写 decision（《决策与评审记录》里登记这件事的议题 id——先登记议题再填，',
        '    #   成文登记之后才判到就先 reopen）；不走 /story 的写 impact（谁、在哪份产物里表态）');
      continue;
    }
    rows.push('    applicable:   # true → 补 requirement（列表）与落点；false → 补 reason',
      '    #   落点二选一：contract 写 §9 登记过的名字（落在统计点上的写统计点名），impact 写实际影响对象');
  }
  rows.push('', '# 设计模式候选：**只登记不选型**（选型是 plan 的事）。');
  // 一个候选都不在册时不摆填写占位：那个空条目问的是「这一段像哪个模式」，
  // 而候选集是空的，作者只能填「无候选」——注定只有一种答案的问题不该问。
  if (!knowledge.patternIds.length) {
    rows.push('# 激活清单里没有候选，这一节无从登记。', 'patterns: []', '');
  } else {
    rows.push(
      `# 在册候选：${knowledge.patternIds.join(' / ')}`,
      `# 这个单元没有合适的候选时，candidate 写「${NO_CANDIDATE}」，signal 里说明为什么没有。`,
      'patterns:',
      '  - unit: ""      # 哪一段业务；按业务切，不是整个需求一个单元',
      '    candidate: ""',
      '    signal: ""    # 从本需求的哪个事实看出它像这个模式',
      '',
    );
  }
  return rows.join('\n');
}
