/**
 * 知识激活清单派生 —— 三类知识的唯一读取入口。
 *
 * **确定性激活**：只读 `manifest.yaml > provides.knowledge` 列出的文件，
 * 不扫描知识目录、不读未启用文件。目录里放一个未登记的知识文件，阶段读不到它。
 * 每个文件属于哪类知识，由它自己 frontmatter 的 `kind` 决定——清单只有一份。
 *
 * **零硬编码**：域前缀、条目清单、模式标识与角色，全部运行期从激活文件的 frontmatter 与正文派生。
 * 代码里没有任何域名、编号或模式名的字面量——新增一个域只改知识与清单，不改这里。
 *
 * 三类知识的定位见 knowledge/README.md；这里只解析结构，不定义知识。
 *
 * **派生为空必须出声**：清单为空、文件缺失、条目表解析出零行，一律 `throw`。
 * 返回空集会让所有「集合包含」类判据恒真，那是比报错危险得多的静默失效。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, lines, readTextOrNull, relDisplay } from './paths.mjs';
import { parseYaml } from './yaml-lite.mjs';

/** 三类知识的类型键——封闭集合。 */
const KNOWLEDGE_KINDS = ['facts', 'constraints', 'patterns'];

/** 索引件：随清单交付、可被引用，不承载条目、不参与派生；不是第四类知识。 */
const INDEX_KIND = 'index';

/** 激活清单文件名（相对扩展根）。 */
const MANIFEST_NAME = 'manifest.yaml';

/** 处置列以此开头的条目是纯评审动作：不产生代码要求。 */
const REVIEW_ACTION_MARK = '（评审动作）';

class KnowledgeError extends Error {}

function fail(msg) {
  throw new KnowledgeError(msg);
}

/** 切 frontmatter 与正文。无 frontmatter 时 fm 为空字符串。 */
function splitFrontmatter(text) {
  const m = String(text ?? '').match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!m) return { frontmatter: '', body: String(text ?? '') };
  return { frontmatter: m[1], body: m[2] };
}

/** frontmatter 键值（浅层，值保留原始文本）。 */
function frontmatterPairs(fm) {
  const out = {};
  for (const line of lines(fm)) {
    const m = line.match(/^([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
    if (m) out[m[1]] = m[2].trim();
  }
  return out;
}

/** `[a, b]` 形态的 frontmatter 列表值。 */
function fmList(raw) {
  const s = String(raw ?? '').trim();
  if (!s.startsWith('[') || !s.endsWith(']')) return s ? [s] : [];
  const inner = s.slice(1, -1).trim();
  return inner ? inner.split(',').map(x => x.trim()).filter(Boolean) : [];
}

/**
 * 一行拆成单元格。
 *
 * markdown 里 `\|` 是**字面竖线**，不是列分隔符——正则类的单元格（探针列）必然用到它。
 * 按裸 `|` 简单切会把 `\b(left\|right)` 切成两格，后半格还会顶掉右边所有列。
 */
function splitCells(row) {
  const out = [];
  let cur = '';
  for (let i = 0; i < row.length; i++) {
    const ch = row[i];
    if (ch === '\\' && row[i + 1] === '|') { cur += '|'; i++; continue; }
    if (ch === '|') { out.push(cur); cur = ''; continue; }
    cur += ch;
  }
  out.push(cur);
  return out.map(c => c.trim());
}

/**
 * 抽出表头含全部关键词的 Markdown 表。
 * **按列名定位，不按列序**——列序会随编辑漂移，列名是契约。
 */
function markdownTable(text, headerKeywords) {
  const rows = lines(text);
  let headers = null;
  const data = [];
  for (const line of rows) {
    const s = line.trim();
    if (!s.startsWith('|')) { if (headers && !data.length) headers = null; continue; }
    const cells = splitCells(s.replace(/^\|/, '').replace(/([^\\])\|$/, '$1'));
    if (!headers) {
      if (headerKeywords.every(k => cells.some(c => c.includes(k)))) headers = cells;
      continue;
    }
    if (cells.every(c => /^[-: ]*$/.test(c))) continue;   // 分隔行
    data.push(cells);
  }
  return headers ? { headers, data } : null;
}

function pick(cells, headers, keyword) {
  const i = headers.findIndex(h => h.includes(keyword));
  return i >= 0 && i < cells.length ? cells[i] : '';
}

/** 条目编号形态：`<域前缀>-<两位序号>`。前缀本身不硬编码，只约束形态。 */
const ENTRY_ID_RE = /^([A-Z][A-Z0-9]{1,7})-(\d{2})$/;

/** 规约条目表里探针列的列名。列不存在时按「无探针」派生（E9）。 */
const PROBE_COLUMN = '探针';

/** 探针形态封闭为四种：多一种就是给机制层开了个能塞业务规则的口子。 */
const PROBE_KINDS = [
  'absent_regex',                  // 实体所在文件里不得出现
  'present_in_method',             // 实体所在方法体内须出现
  'referenced_outside_definition', // 实体在定义文件之外被引用
  'count_eq',                      // 文件内命中次数恒等
];

/**
 * 解析一格探针。
 *
 * **列缺省不是错误**（需求 E9）：目标工程的规约表还没有这一列时，`pick` 返回空串，
 * 这里按「无探针」派生并返回 null。否则已适配仓一升级，老知识全部派生失败——
 * 新增字段的缺省值是兼容性的一部分，不是可选的礼貌。
 *
 * 表达式里的 `|` 在 markdown 表格里必须写成 `\|`，这里还原。
 */
function parseProbe(raw) {
  // 只剥反引号：`*` 在正则里是量词，按 markdown 强调标记清掉会把 `\s*` 悄悄变成 `\s`。
  const cell = String(raw ?? '').replace(/`/g, '').trim();
  if (!cell || cell === '无' || cell === '—' || cell === '-') return null;
  const expr = cell;
  const kind = expr.split(':', 1)[0];
  if (!PROBE_KINDS.includes(kind)) {
    fail(`探针形态未知：「${kind}」——只接受 ${PROBE_KINDS.join(' / ')}，或写「无」`);
  }
  if (kind === 'referenced_outside_definition') {
    return { kind, pattern: '', count: null, raw: expr };
  }
  const rest = expr.slice(kind.length + 1);
  if (!rest) fail(`探针「${kind}」缺表达式：${expr}`);
  if (kind === 'count_eq') {
    // count_eq:<re>:<n> —— 正则里可能有冒号，所以从右边切一次
    const at = rest.lastIndexOf(':');
    const n = Number(rest.slice(at + 1));
    if (at < 0 || !Number.isInteger(n)) fail(`探针 count_eq 形态应为 count_eq:<正则>:<次数>：${expr}`);
    return { kind, pattern: rest.slice(0, at), count: n, raw: expr };
  }
  return { kind, pattern: rest, count: null, raw: expr };
}

function parseConstraintFile(absPath, rel) {
  const text = readTextOrNull(absPath);
  if (text === null) fail(`派生为空：激活清单登记的规约文件读不到 —— ${rel}`);
  const { frontmatter, body } = splitFrontmatter(text);
  const fm = frontmatterPairs(frontmatter);
  const table = markdownTable(body, ['编号', '约束']);
  if (!table) {
    fail(`派生为空：${rel} 找不到条目表 —— 表头须同时含「编号」与「约束」两列`);
  }
  const entries = [];
  for (const cells of table.data) {
    const id = pick(cells, table.headers, '编号').replace(/[`*]/g, '').trim();
    const m = id.match(ENTRY_ID_RE);
    if (!m) continue;
    const handling = pick(cells, table.headers, '处置');
    // 只派生有消费者的字段（复述比对、出口/冻结门禁、归档渲染、探针执行）；
    // 强制力/命中条件/验证列由模型直接读正文，机制不派生无人读的副本。
    entries.push({
      id,
      prefix: m[1],
      file: rel,
      constraint: pick(cells, table.headers, '约束'),
      handling,
      reviewAction: handling.trim().startsWith(REVIEW_ACTION_MARK),
      probe: parseProbe(pick(cells, table.headers, PROBE_COLUMN)),
    });
  }
  if (!entries.length) {
    fail(`派生为空：${rel} 的条目表解析出零行 —— 检查编号是否为「前缀-两位数」形态`);
  }
  const prefixes = new Set(entries.map(e => e.prefix));
  if (prefixes.size !== 1) {
    fail(`${rel} 的条目跨了多个域前缀（${[...prefixes].join('、')}）—— 一个文件一个域`);
  }
  const declared = fm.domain;
  const derived = [...prefixes][0];
  if (declared && declared !== derived) {
    fail(`${rel} 声明的 domain「${declared}」与条目编号前缀「${derived}」不一致`);
  }
  // 落法附注：判定期要拿它做复述比对的来源之一
  const notesMatch = body.match(/^#+\s*落法附注\s*$/m);
  const notes = notesMatch ? body.slice(notesMatch.index + notesMatch[0].length) : '';
  // 中文域名取正文一级标题——归档件面向评审者，写仓内 slug 他们对不上
  const titleMatch = body.match(/^#\s+(.+?)\s*$/m);
  const title = titleMatch ? titleMatch[1].trim() : (fm.name ?? derived);
  // applies_when 是域级命中条件：`always` 的域每条都要判，条件域先判域再逐条
  // （消费者：归档装配的域级判定、story 的规约判定表核对）。
  const appliesWhen = String(fm.applies_when ?? '').trim();
  return {
    file: rel,
    name: fm.name ?? '',
    title,
    domain: derived,
    appliesWhen,
    alwaysApplies: appliesWhen === 'always',
    entries: entries.map(e => ({ ...e, domainTitle: title })),
    notes,
  };
}

function parsePatternFile(absPath, rel) {
  const text = readTextOrNull(absPath);
  if (text === null) fail(`派生为空：激活清单登记的模式文件读不到 —— ${rel}`);
  const { frontmatter } = splitFrontmatter(text);
  const fm = frontmatterPairs(frontmatter);
  const id = fm.name;
  if (!id) fail(`${rel} 的 frontmatter 缺 name —— 模式标识是全链受控标识，不能缺`);
  const roles = fmList(fm.roles);
  if (!roles.length) {
    fail(`派生为空：${rel} 未声明 roles —— 模式采用后要逐角色投影到契约实体，没有角色就无从校验`);
  }
  const coordinator = fm.coordinator_role ?? '';
  if (coordinator && !roles.includes(coordinator)) {
    fail(`${rel} 的 coordinator_role「${coordinator}」不在 roles 里`);
  }
  // 适用条件与正文由模型直接读，机制只认标识与角色（冻结门禁的投影基准）。
  return {
    file: rel,
    id,
    roles,
    optionalRoles: fmList(fm.optional_roles),
    coordinatorRole: coordinator,
  };
}

/** 索引件：只取名字，不解析条目；正文由 selfCheck 按 file 回读。 */
function parseIndexFile(text, rel) {
  const { frontmatter, body } = splitFrontmatter(text);
  const fm = frontmatterPairs(frontmatter);
  const titleMatch = body.match(/^#\s+(.+?)\s*$/m);
  return {
    file: rel,
    name: fm.name ?? '',
    title: titleMatch ? titleMatch[1].trim() : (fm.name ?? rel),
  };
}

function parseFactFile(absPath, rel) {
  const text = readTextOrNull(absPath);
  if (text === null) fail(`派生为空：激活清单登记的项目知识文件读不到 —— ${rel}`);
  const { frontmatter, body } = splitFrontmatter(text);
  const fm = frontmatterPairs(frontmatter);
  const facets = lines(body)
    .map(l => l.match(/^##\s+(.+?)\s*$/))
    .filter(Boolean)
    .map(m => m[1].replace(/\s*—.*$/, '').replace(/^\d+(\.\d+)*\.?\s*/, '').trim())
    .filter(Boolean);
  return { file: rel, name: fm.name ?? '', facets };
}

/**
 * 读激活清单并派生知识。
 *
 * **清单只有一份**（`provides.knowledge`）；「这个文件属于哪类」写在文件自己的
 * frontmatter `kind` 里。曾经是两份——清单里再按类分一次组——那意味着新增一个知识文件
 * 要在两处登记，改一处忘另一处就是静默漂移，而它们本来就是同一件事。
 *
 * @returns {{facts: object[], constraints: object[], patterns: object[], indexes: object[],
 *            entries: object[], prefixes: string[], patternIds: string[]}}
 * @throws 清单缺失 / 文件读不到 / kind 缺失或未知 / 条目表零行 / 角色未声明
 */
export function activeKnowledge(projectRoot) {
  const root = extensionRoot(projectRoot);
  const manifestPath = path.join(root, MANIFEST_NAME);
  const raw = readTextOrNull(manifestPath);
  if (raw === null) {
    fail(`派生为空：读不到激活清单 ${relDisplay(projectRoot, manifestPath)}`);
  }
  let manifest;
  try {
    manifest = parseYaml(raw);
  } catch (e) {
    fail(`激活清单解析失败（解析失败不当作空清单）：${e.message}`);
  }
  const list = manifest?.provides?.knowledge;
  if (!Array.isArray(list) || !list.length) {
    fail('派生为空：manifest 的 provides.knowledge 缺失或为空 —— 阶段不扫描知识目录，没有清单就没有知识');
  }

  const out = { facts: [], constraints: [], patterns: [], indexes: [] };
  const seen = new Set();
  for (const rel of list) {
    const relPosix = String(rel).replace(/\\/g, '/');
    if (seen.has(relPosix)) fail(`${relPosix} 在激活清单里重复登记`);
    seen.add(relPosix);

    const abs = path.join(root, ...relPosix.split('/').filter(Boolean));
    const text = readTextOrNull(abs);
    if (text === null) fail(`派生为空：激活清单登记的文件读不到 —— ${relPosix}`);

    const kind = frontmatterPairs(splitFrontmatter(text).frontmatter).kind;
    if (!kind) {
      fail(`${relPosix} 的 frontmatter 缺 kind —— 它决定这个文件按哪类知识解析，`
        + `不能靠目录或文件名去猜（可用：${[...KNOWLEDGE_KINDS, INDEX_KIND].join(' / ')}）`);
    }
    if (kind === INDEX_KIND) { out.indexes.push(parseIndexFile(text, relPosix)); continue; }
    if (!KNOWLEDGE_KINDS.includes(kind)) {
      fail(`${relPosix} 的 kind="${kind}" 不在封闭集合里`
        + `（知识三类：${KNOWLEDGE_KINDS.join(' / ')}；说明性文档写 ${INDEX_KIND}，它不形成新的知识类型）`);
    }
    if (kind === 'constraints') out.constraints.push(parseConstraintFile(abs, relPosix));
    else if (kind === 'patterns') out.patterns.push(parsePatternFile(abs, relPosix));
    else out.facts.push(parseFactFile(abs, relPosix));
  }

  for (const kind of KNOWLEDGE_KINDS) {
    if (!out[kind].length) {
      fail(`派生为空：激活清单里没有任何 kind=${kind} 的文件 —— `
        + '三类知识各自都要有内容，缺哪类都要显式说明');
    }
  }

  const entries = out.constraints.flatMap(c => c.entries);
  const ids = entries.map(e => e.id);
  const dup = ids.filter((x, i) => ids.indexOf(x) !== i);
  if (dup.length) fail(`条目编号重复：${[...new Set(dup)].join('、')} —— 编号一经分配不复用`);

  return {
    ...out,
    entries,
    prefixes: [...new Set(entries.map(e => e.prefix))],
    patternIds: out.patterns.map(p => p.id),
  };
}

/** 按编号取条目；找不到返回 null（调用方据此判「编号不在册」）。 */
export function entryById(knowledge, id) {
  return knowledge.entries.find(e => e.id === id) ?? null;
}

/**
 * 知识层自检 —— 结构级边界，不判内容对错（那是人和 verifier 的事）。
 *
 * 扫描面是**全部激活文件**（三类知识 + 索引件），四项判据全部从激活清单与目录结构派生：
 *   1. 规约不携带工程实现事实（源码路径/文件名归项目知识）；
 *   2. 任一知识文件不含阶段消费矩阵（阶段路由归各阶段自己的规则）；
 *   3. 项目知识不含在册规约编号（时机与要求归规约，facts 只写有什么、在哪）；
 *   4. 任一知识文件不指向机制（manifest、hooks/skills/rules 这类目录）——知识是给模型
 *      实现需求用的，维护坐标不进知识。
 *
 * 不做模式基线守恒：那要在机制层存一份模式正文的副本，副本就是第二份真源；归发布清单。
 *
 * @returns {string[]} 问题清单；空数组表示通过
 */
export function selfCheck(projectRoot, knowledge) {
  const problems = [];
  const root = extensionRoot(projectRoot);
  const readRel = rel => readTextOrNull(path.join(root, ...rel.split('/'))) ?? '';
  const allFiles = [
    ...knowledge.constraints, ...knowledge.facts, ...knowledge.patterns, ...knowledge.indexes,
  ].map(k => k.file);

  // 1. 规约不得携带目标工程实现事实：源码路径与源文件名一律归项目知识
  const implPathRe = /[\w./-]+\.(ets|ts|js|json5)\b/;
  for (const c of knowledge.constraints) {
    lines(readRel(c.file)).forEach((line, i) => {
      const m = line.match(implPathRe);
      if (m) {
        problems.push(`${c.file}:${i + 1} 规约携带工程实现事实「${m[0]}」`
          + '——归项目知识；此处只写「按项目知识的入口找现成的」');
      }
    });
  }

  // 2. 知识不维护阶段消费路由：任一知识文件的表格行里不得出现阶段矩阵
  const phaseWords = ['spec', 'plan', 'coding', 'review', 'testing'];
  for (const file of allFiles) {
    for (const line of lines(readRel(file))) {
      if (!line.trim().startsWith('|')) continue;
      const hit = phaseWords.filter(w => line.toLowerCase().includes(w));
      if (hit.length >= 3) {
        problems.push(`${file} 出现阶段消费矩阵（表头含 ${hit.join('/')}）`
          + '——阶段路由归各阶段自己的规则，知识不维护');
        break;
      }
    }
  }

  // 3. 项目知识不含在册规约编号：facts 只答有什么、在哪，时机与要求归规约
  const entryIds = new Set(knowledge.entries.map(e => e.id));
  const anyIdRe = /\b[A-Z][A-Z0-9]{1,7}-\d{2}\b/g;
  for (const f of knowledge.facts) {
    lines(readRel(f.file)).forEach((line, i) => {
      for (const m of line.matchAll(anyIdRe)) {
        if (entryIds.has(m[0])) {
          problems.push(`${f.file}:${i + 1} 项目知识引用规约条目「${m[0]}」`
            + '——时机与要求归规约，facts 只写有什么、在哪');
        }
      }
    });
  }

  // 4. 知识不指向机制：目录名从扩展根实取（knowledge/ 以外的一级目录）+ 激活清单文件名
  let mechanismDirs = [];
  try {
    mechanismDirs = fs.readdirSync(root, { withFileTypes: true })
      .filter(d => d.isDirectory() && d.name !== 'knowledge' && !d.name.startsWith('.'))
      .map(d => d.name);
  } catch { /* 扩展根读不到时本项无从判，前面的激活读取已经出声 */ }
  const mechanismRe = mechanismDirs.length
    ? new RegExp(`(?:^|[\\s(\`/])(?:${mechanismDirs.map(d => d.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})/|${MANIFEST_NAME.replace('.', '\\.')}`)
    : new RegExp(MANIFEST_NAME.replace('.', '\\.'));
  for (const file of allFiles) {
    lines(readRel(file)).forEach((line, i) => {
      const m = line.match(mechanismRe);
      if (m) {
        problems.push(`${file}:${i + 1} 知识指向机制「${m[0].trim()}」`
          + '——维护坐标不进知识，知识只写给模型实现需求用的内容');
      }
    });
  }

  return problems;
}
