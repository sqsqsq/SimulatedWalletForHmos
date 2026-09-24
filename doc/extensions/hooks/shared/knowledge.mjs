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
 * 三类知识的读写规则见 `skills/story/reference/knowledge/protocol.md`；这里只解析结构，不定义知识。
 *
 * **派生为空必须出声**：清单登记了却读不到、条目表解析出零行，一律 `throw`。
 * 返回空集会让所有「集合包含」类判据恒真，那是比报错危险得多的静默失效。
 *
 * **「还没配置」是另一件事**：清单本身缺失或为空，说明这个仓尚未配置知识——那是新装
 * 的仓的正常状态，返回四类皆空的集合，链条照走。两件事的区别在于**登记过没有**：
 * 没登记就没有要读的东西，登记了读不到才是读取失败被吞成空。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, lines, readTextOrNull, relDisplay } from './paths.mjs';
import { parseYaml } from './yaml.mjs';

/** 三类知识的类型键——封闭集合。 */
const KNOWLEDGE_KINDS = ['facts', 'constraints', 'patterns'];

/** 读写规则与适配方法的位置（相对扩展根）：任务包、审查与报错都指向这里。 */
const PROTOCOL_DOC = 'skills/story/reference/knowledge/protocol.md';

/** 激活清单文件名（相对扩展根）。 */
const MANIFEST_NAME = 'manifest.yaml';

/** 处置列以此开头的条目是纯评审动作：不产生代码要求。 */
const REVIEW_ACTION_MARK = '（评审动作）';

/** 强制力值域：未满足时怎么处理——红线阻断不许豁免，基线可豁免须补偿，建议可不做。 */
const FORCES = ['红线', '基线', '建议'];

/** 执行体值域：证据从哪来。验证列写成若干段「<执行体>：<怎么验>」，各段共同必需。 */
const EXECUTORS = ['模型', '构建', '实机', '人工'];

/** 探针列的前缀：知识作者声明「这个形态本身就是要求」。不带它的探针只是取证线索。 */
const BLOCKING_MARK = '阻断：';

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

/**
 * frontmatter 按 YAML 读成映射：与 manifest 同一读取器，引号、转义、折叠与保留换行都按 YAML 的真实含义取值。
 * 读不出或不是映射时抛 KnowledgeError，由调用方记在该文件名下。
 */
function frontmatterOf(fm) {
  let value;
  try {
    value = parseYaml(fm);
  } catch (e) {
    if (e?.name !== 'YAMLParseError') throw e;
    fail(`frontmatter 不是合法 YAML —— ${e.message.split('\n')[0]}`);
  }
  if (typeof value !== 'object' || Array.isArray(value)) fail('frontmatter 要写成「键: 值」映射');
  return value;
}

/** frontmatter 的标量取成去空白的字符串；没写为空串。 */
function fmText(value) {
  return value === undefined || value === null ? '' : String(value).trim();
}

/** frontmatter 的列表值：YAML 列表逐项取字符串，单个标量当一项。 */
function fmList(value) {
  if (Array.isArray(value)) return value.map(fmText).filter(Boolean);
  const s = fmText(value);
  return s ? [s] : [];
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
 * 带 `阻断：` 前缀的记 `blocking`：形态不符就是这处落点没落实；不带的只是取证线索。
 */
function parseProbe(raw) {
  // 只剥反引号：`*` 在正则里是量词，按 markdown 强调标记清掉会把 `\s*` 悄悄变成 `\s`。
  const cell = String(raw ?? '').replace(/`/g, '').trim();
  if (!cell || cell === '无' || cell === '—' || cell === '-') return null;
  const blocking = cell.startsWith(BLOCKING_MARK);
  const expr = blocking ? cell.slice(BLOCKING_MARK.length).trim() : cell;
  const kind = expr.split(':', 1)[0];
  if (!PROBE_KINDS.includes(kind)) {
    fail(`探针形态未知：「${kind}」——只接受 [${BLOCKING_MARK}]${PROBE_KINDS.join(' / ')}，或写「无」`);
  }
  const rest = expr.slice(kind.length + 1);
  const probe = { kind, pattern: rest, count: null, raw: expr, blocking };
  if (kind === 'referenced_outside_definition') return { ...probe, pattern: '' };
  if (!rest) fail(`探针「${kind}」缺表达式：${expr}`);
  if (kind === 'count_eq') {
    // count_eq:<re>:<n> —— 正则里可能有冒号，所以从右边切一次
    const at = rest.lastIndexOf(':');
    const n = Number(rest.slice(at + 1));
    if (at < 0 || !Number.isInteger(n)) fail(`探针 count_eq 形态应为 count_eq:<正则>:<次数>：${expr}`);
    return { ...probe, pattern: rest.slice(0, at), count: n };
  }
  return probe;
}

/**
 * 验证列里声明的执行体。段首是「<执行体>：」；整格不带冒号时按分隔符拆（`模型 / 实机`）。
 * 反引号里的检索式可能自带冒号，先去掉再认段首。
 */
function parseExecutors(cell) {
  const s = String(cell ?? '').replace(/`[^`]*`/g, '').trim();
  return /[：:]/.test(s)
    ? [...s.matchAll(/(?:^|[。；;]\s*)([^：:。；;\s]{1,6})\s*[：:]/g)].map(m => m[1])
    : s.split(/[\s/、，,]+/).filter(Boolean);
}

function parseConstraintFile(body, fm, rel, bad) {
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
    const reviewAction = handling.trim().startsWith(REVIEW_ACTION_MARK);
    // 强制力定未满足时的后果，执行体定证据从哪来，两者独立；各道门按它们执行，所以值域在载入时核。
    const force = pick(cells, table.headers, '强制力').replace(/[`*]/g, '').trim();
    const executors = parseExecutors(pick(cells, table.headers, '验证'));
    const say = (msg) => bad.push(`${rel} ${id} ${msg}`);
    if (!FORCES.includes(force)) say(`的强制力「${force || '(空)'}」不在 ${FORCES.join(' / ')} 里`);
    const alien = executors.filter(x => !EXECUTORS.includes(x));
    if (!executors.length || alien.length) {
      say(`的验证列${alien.length ? `有不认识的执行体「${alien.join('、')}」` : '解析不出执行体'}`
        + `——写成「<执行体>：<怎么验>」，执行体取 ${EXECUTORS.join(' / ')}，几段就是几种证据都要`);
    }
    if (reviewAction !== executors.includes('人工') && (reviewAction || executors.every(x => x === '人工'))) {
      say(reviewAction ? '的处置是评审动作，验证列要有「人工」'
        : `只由人工验，处置要以「${REVIEW_ACTION_MARK}」开头——不产生代码要求的条目才只靠人工`);
    }
    let probe = null;
    try {
      probe = parseProbe(pick(cells, table.headers, PROBE_COLUMN));
    } catch (e) {
      if (!(e instanceof KnowledgeError)) throw e;
      say(`的${e.message}`);
    }
    entries.push({
      id,
      prefix: m[1],
      file: rel,
      constraint: pick(cells, table.headers, '约束'),
      when: pick(cells, table.headers, '命中条件'),
      handling,
      reviewAction,
      force,
      executors,
      probe,
    });
  }
  if (!entries.length) {
    fail(`派生为空：${rel} 的条目表解析出零行 —— 检查编号是否为「前缀-两位数」形态`);
  }
  const prefixes = new Set(entries.map(e => e.prefix));
  if (prefixes.size !== 1) {
    fail(`${rel} 的条目跨了多个域前缀（${[...prefixes].join('、')}）—— 一个文件一个域`);
  }
  const declared = fmText(fm.domain);
  const derived = [...prefixes][0];
  if (declared && declared !== derived) {
    fail(`${rel} 声明的 domain「${declared}」与条目编号前缀「${derived}」不一致`);
  }
  // 落法附注：顶层列表项以 `**<编号>**` 起头的是那一条的附注，到下一个顶层项或标题为止（缩进的续行、
  // 子项并成一行）；其余顶层项是整域通则。送到判断骨架与审查任务书，读它的是判命中的作者与审查者。
  const noteOf = new Map();
  const general = [];
  const notesAt = body.match(/^#+\s*落法附注\s*$/m);
  if (notesAt) {
    let append = null;
    for (const line of lines(body.slice(notesAt.index + notesAt[0].length))) {
      if (/^#+\s/.test(line)) break;
      if (!line.trim()) continue;
      const item = line.match(/^-\s+(.*)$/);
      if (!item) { if (append) append(line.trim().replace(/^[-*]\s+/, '')); continue; }
      const head = item[1].match(/^\*\*([A-Z][A-Z0-9]{1,7}-\d{2})\*\*\s*[：:]?\s*(.*)$/);
      if (head) {
        const id = head[1];
        if (!entries.some(e => e.id === id)) bad.push(`${rel} 的落法附注里有「${id}」，条目表里没有这个编号`);
        noteOf.set(id, head[2].trim());
        append = (t) => noteOf.set(id, `${noteOf.get(id)} ${t}`.trim());
      } else {
        general.push(item[1].trim());
        const k = general.length - 1;
        append = (t) => { general[k] = `${general[k]} ${t}`.trim(); };
      }
    }
  }
  // 中文域名取正文一级标题——归档件面向评审者，写仓内 slug 他们对不上
  const titleMatch = body.match(/^#\s+(.+?)\s*$/m);
  const title = titleMatch ? titleMatch[1].trim() : (fmText(fm.name) || derived);
  return {
    file: rel,
    name: fmText(fm.name),
    title,
    domain: derived,
    entries: entries.map(e => ({ ...e, domainTitle: title, note: noteOf.get(e.id) ?? '' })),
    general,
  };
}

function parsePatternFile(body, fm, rel, bad) {
  const id = fmText(fm.name);
  if (!id) fail(`${rel} 的 frontmatter 缺 name —— 模式标识是全链受控标识，不能缺`);
  // 上篇给 spec / plan 选型，下篇给 coding / review 落地：缺一篇，那一侧就无从读起。
  const halves = ['上篇', '下篇'].filter(h => !new RegExp(`^#\\s+${h}\\s*·`, 'm').test(body));
  if (halves.length) {
    bad.push(`${rel} 缺一级标题 ${halves.map(h => `「# ${h} · …」`).join('')}`
      + '——模式文件分上篇（适用与选型）与下篇（结构与落地）两个一级标题');
  }
  const roles = fmList(fm.roles);
  if (!roles.length) {
    fail(`派生为空：${rel} 未声明 roles —— 模式采用后要逐角色投影到契约实体，没有角色就无从校验`);
  }
  const coordinator = fmText(fm.coordinator_role);
  if (coordinator && !roles.includes(coordinator)) {
    fail(`${rel} 的 coordinator_role「${coordinator}」不在 roles 里`);
  }
  // 适用条件与正文由模型直接读，机制只认标识与角色（冻结门禁的投影基准）。
  return {
    file: rel,
    id,
    roles,
    optionalRoles: fmList(fm.optional_roles),
  };
}

/** 一个二级标题是一面：面名去掉编号与「 — 」之后的说明。 */
function parseFactFile(body, fm, rel) {
  const facets = lines(body).map(l => l.match(/^##\s+(.+?)\s*$/)).filter(Boolean)
    .map(m => m[1].replace(/\s*—.*$/, '').replace(/^\d+(\.\d+)*\.?\s*/, '').trim()).filter(Boolean);
  return { file: rel, name: fmText(fm.name), facets };
}

/**
 * 读激活清单，返回登记的知识文件路径。
 *
 * 只回答「清单登记了哪些」，不回答「读到了什么」——**清单合法不等于每个文件存在**，
 * 存在性由各消费者按自己的职责处置（激活派生与摘要核对各自出声）。
 * 路径保持清单顺序与重复项（重复由激活派生出声），不扫描知识目录、不去重。
 *
 * 清单文件本身必须可读：读不到或解析失败都抛错，不当作「没有知识」。
 * 在可读的清单里，`provides.knowledge` 整条不写或为合法空列表，表示这个仓
 * 没有激活知识，返回空数组。至于登记了却读不到文件，由各消费者按职责出声。
 * 「写错了」是相反的处境：`knowledge:` 写成字符串或映射说明有人想登记什么但写坏了，
 * 都降成空集的话，一个填错的清单会安静地表现成一个什么都没登记的仓，
 * 而那正是它看起来最正常的样子——所以形状不对要抛错，不当作没配置。
 *
 * @returns {string[]} 相对扩展根的 POSIX 斜杠路径，按清单顺序
 */
export function knowledgeFiles(projectRoot) {
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
  const declared = manifest?.provides?.knowledge;
  if (declared !== undefined && declared !== null && !Array.isArray(declared)) {
    fail(`manifest 的 provides.knowledge 不是列表（读到 ${typeof declared}）——`
      + '要么逐行列出激活的知识文件，要么整条不写；写成别的形状没有「还没配置」的含义');
  }
  return (Array.isArray(declared) ? declared : [])
    .map(rel => String(rel).replace(/\\/g, '/'));
}

/**
 * 读激活清单并派生知识。
 *
 * **清单只有一份**（`provides.knowledge`）；「这个文件属于哪类」写在文件自己的
 * frontmatter `kind` 里。清单里再按类分一次组就成了两份，那意味着新增一个知识文件
 * 要在两处登记，改一处忘另一处就是静默漂移，而它们本来就是同一件事。
 *
 * 知识靠自己描述自己：frontmatter 的 `applies_when` 说何时读、回答什么，每份解析结果带上它
 * （`appliesWhen`），任务包与审查据此把知识交给当前阶段；机制不点任何知识的名字。
 *
 * @returns {{facts: object[], constraints: object[], patterns: object[],
 *            entries: object[], prefixes: string[], patternIds: string[]}}
 * @throws 清单缺失 / 文件读不到 / kind 或 applies_when 缺失 / kind 未知 / 条目表零行 / 角色未声明
 */
export function activeKnowledge(projectRoot) {
  const root = extensionRoot(projectRoot);
  const out = { facts: [], constraints: [], patterns: [] };
  const seen = new Set();
  // 不合协议的条目收齐再一次报：知识所有者升级机制之后要逐条改，不该改一条撞一条。
  const bad = [];
  for (const relPosix of knowledgeFiles(projectRoot)) {
    if (seen.has(relPosix)) { bad.push(`${relPosix} 在激活清单里重复登记`); continue; }
    seen.add(relPosix);

    const abs = path.join(root, ...relPosix.split('/').filter(Boolean));
    const text = readTextOrNull(abs);
    if (text === null) { bad.push(`派生为空：激活清单登记的文件读不到 —— ${relPosix}`); continue; }

    const { frontmatter, body } = splitFrontmatter(text);
    let fm;
    try {
      fm = frontmatterOf(frontmatter);
    } catch (e) {
      if (!(e instanceof KnowledgeError)) throw e;
      bad.push(`${relPosix} 的 ${e.message}`);
      continue;
    }
    const kind = fmText(fm.kind);
    if (!kind) {
      bad.push(`${relPosix} 的 frontmatter 缺 kind —— 它决定这个文件按哪类知识解析，`
        + `不能靠目录或文件名去猜（可用：${KNOWLEDGE_KINDS.join(' / ')}）`);
      continue;
    }
    if (!KNOWLEDGE_KINDS.includes(kind)) {
      bad.push(`${relPosix} 的 kind="${kind}" 不在封闭集合里（知识三类：${KNOWLEDGE_KINDS.join(' / ')}，`
        + `写法见 ${PROTOCOL_DOC}）`);
      continue;
    }
    const raw = fm.applies_when;
    const appliesWhen = typeof raw === 'string' ? raw.trim() : '';
    if (!appliesWhen) {
      const got = raw === undefined || raw === null ? '的 frontmatter 缺 applies_when'
        : typeof raw === 'string' ? '的 applies_when 是空的' : `的 applies_when 不是文字（读到 ${typeof raw}）`;
      bad.push(`${relPosix} ${got} —— 用一句话写这份知识何时读、回答什么，`
        + `任务包与审查按它把知识交给当前阶段（写法见 ${PROTOCOL_DOC}）`);
    }
    // 本文件的结构错误（条目表零行、缺角色等）记下后接着核下一份：维护者一轮看到全部问题。
    try {
      if (kind === 'constraints') out.constraints.push({ ...parseConstraintFile(body, fm, relPosix, bad), appliesWhen });
      else if (kind === 'patterns') out.patterns.push({ ...parsePatternFile(body, fm, relPosix, bad), appliesWhen });
      else out.facts.push({ ...parseFactFile(body, fm, relPosix), appliesWhen });
    } catch (e) {
      if (!(e instanceof KnowledgeError)) throw e;
      bad.push(e.message);
    }
  }
  if (bad.length) fail(`知识不合协议（${bad.length} 处，按所在文件改）：\n  · ${bad.join('\n  · ')}`);

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
 * 扫描面是**全部激活文件**，四项判据全部从激活清单与目录结构派生：
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
    ...knowledge.constraints, ...knowledge.facts, ...knowledge.patterns,
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

/**
 * 激活知识及其自述用途，外加读写规则的位置：作者任务包与审查任务共用这一段。
 * 只渲染已有对象，不按任何知识名字分支。
 */
export function knowledgeGuide(projectRoot, knowledge) {
  const at = rel => `\`${relDisplay(projectRoot, path.join(extensionRoot(projectRoot), rel))}\``;
  const all = [...(knowledge?.facts ?? []), ...(knowledge?.constraints ?? []), ...(knowledge?.patterns ?? [])];
  return [`知识的读写规则见 ${at(PROTOCOL_DOC)}。激活的知识与各自用途（按当前需求选读）：`, '',
    ...(all.length ? all.map(k => `- ${at(k.file)} —— ${k.appliesWhen.replace(/\n/g, '\n  ')}`) : ['- （激活清单为空）'])];
}
