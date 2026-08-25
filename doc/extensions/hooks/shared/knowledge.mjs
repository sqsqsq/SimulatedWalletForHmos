/**
 * 知识激活清单派生 —— 三类知识的唯一读取入口。
 *
 * **确定性激活**：只读 `manifest.yaml > provides.knowledge` 列出的文件，
 * 不扫描知识目录、不读未启用文件。目录里放一个未登记的知识文件，阶段读不到它。
 * 每个文件属于哪类知识，由它自己 frontmatter 的 `kind` 决定——清单只有一份。
 *
 * **零硬编码**：域前缀、条目清单、模式标识与角色，全部运行期从激活文件的正文派生。
 * 代码里没有任何域名、编号或模式名的字面量——新增一个域只改知识与清单，不改这里。
 *
 * **派生为空必须出声**：清单为空、文件缺失、条目表解析出零行，一律 `throw`。
 * 返回空集会让所有「集合包含」类判据恒真，那是比报错危险得多的静默失效。
 */
import * as path from 'node:path';
import { extensionRoot, lines, readTextOrNull, relDisplay } from './paths.mjs';
import { parseYaml } from './yaml-lite.mjs';

/** 三类知识的类型键——封闭集合（项目事实 / 规约 / 设计模式）。 */
export const KNOWLEDGE_KINDS = ['facts', 'constraints', 'patterns'];

/**
 * 索引件：目录的字段模型、模式的路由与粒度定义这类**说明性文档**。
 *
 * 它随激活清单交付、可被各阶段引用（那些「粒度照索引的定义切」的指令指的就是它），
 * 但不承载条目，因此不参与条目与模式的派生。
 * **它不是第四类知识**——说明性文档不形成新的知识类型。
 */
export const INDEX_KIND = 'index';

/** 处置列以此开头的条目是纯评审动作：不产生代码要求。 */
const REVIEW_ACTION_MARK = '（评审动作）';

class KnowledgeError extends Error {}

function fail(msg) {
  throw new KnowledgeError(msg);
}

/** 切 frontmatter 与正文。无 frontmatter 时 fm 为空字符串。 */
export function splitFrontmatter(text) {
  const m = String(text ?? '').match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!m) return { frontmatter: '', body: String(text ?? '') };
  return { frontmatter: m[1], body: m[2] };
}

/** frontmatter 键值（浅层，值保留原始文本）。 */
export function frontmatterPairs(fm) {
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
    const cells = s.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
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
    entries.push({
      id,
      prefix: m[1],
      file: rel,
      constraint: pick(cells, table.headers, '约束'),
      force: pick(cells, table.headers, '强制力'),
      hitWhen: pick(cells, table.headers, '命中条件'),
      handling,
      verify: pick(cells, table.headers, '验证'),
      reviewAction: handling.trim().startsWith(REVIEW_ACTION_MARK),
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
  return {
    file: rel,
    name: fm.name ?? '',
    title,
    domain: derived,
    appliesWhen: fm.applies_when ?? '',
    entries: entries.map(e => ({ ...e, domainTitle: title })),
    notes,
  };
}

function parsePatternFile(absPath, rel) {
  const text = readTextOrNull(absPath);
  if (text === null) fail(`派生为空：激活清单登记的模式文件读不到 —— ${rel}`);
  const { frontmatter, body } = splitFrontmatter(text);
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
  return {
    file: rel,
    id,
    roles,
    optionalRoles: fmList(fm.optional_roles),
    coordinatorRole: coordinator,
    appliesWhen: fm.applies_when ?? '',
    notAppliesWhen: fm.not_applies_when ?? '',
    body,
  };
}

/** 索引件：只取名字与正文，供引用它的阶段读取（不解析条目）。 */
function parseIndexFile(text, rel) {
  const { frontmatter, body } = splitFrontmatter(text);
  const fm = frontmatterPairs(frontmatter);
  const titleMatch = body.match(/^#\s+(.+?)\s*$/m);
  return {
    file: rel,
    name: fm.name ?? '',
    title: titleMatch ? titleMatch[1].trim() : (fm.name ?? rel),
    body,
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
  return { file: rel, name: fm.name ?? '', facets, body };
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
  const manifestPath = path.join(root, 'manifest.yaml');
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
 * 复述判定的来源文本：该条目的约束列、处置列与所属域的落法附注。
 * **不含**渲染出的「要求」列——那本就是原文，纳入比较会把全员误杀（判据唯一性要求）。
 */
export function paraphraseSources(knowledge, id) {
  const e = entryById(knowledge, id);
  if (!e) return [];
  const domain = knowledge.constraints.find(c => c.file === e.file);
  return [e.constraint, e.handling, domain?.notes ?? ''].filter(Boolean);
}

/**
 * 知识层自检 —— 结构级，不判内容对错。
 *
 * **只查机制层与知识层的职责边界**，不查知识内容对不对（那是人和 verifier 的事）：
 *   1. 规约不得携带目标工程的实现事实（类名、路径、API 归项目知识）；
 *   2. 知识不得维护阶段消费路由（阶段路由归各阶段自己的规则，写在这里就是第二份真源）。
 *
 * **这里刻意不做模式基线守恒**：那需要在机制层存一份模式正文的 SHA 与元数据副本，
 * 而那份副本就是「机制层维护 knowledge 的第二份清单」——改一个字的模式正文、
 * 或新增一个模式，story 机制就会报错。模式内容的守恒归版本发布清单（它本就管内容归属），
 * 不归这里。
 *
 * @returns {string[]} 问题清单；空数组表示通过
 */
export function selfCheck(projectRoot, knowledge) {
  const problems = [];
  const root = extensionRoot(projectRoot);

  // 规约不得携带目标工程实现事实：源码路径与源文件名一律归项目知识
  const implPathRe = /[\w./-]+\.(ets|ts|js|json5)\b/;
  for (const c of knowledge.constraints) {
    const text = readTextOrNull(path.join(root, ...c.file.split('/'))) ?? '';
    lines(text).forEach((line, i) => {
      const m = line.match(implPathRe);
      if (m) {
        problems.push(`${c.file}:${i + 1} 规约携带工程实现事实「${m[0]}」`
          + '——归项目知识；此处只写「去仓里按项目知识的定位规则找现成的」');
      }
    });
  }

  // Knowledge 不维护阶段消费路由：知识正文里不得出现阶段矩阵
  const phaseWords = ['spec', 'plan', 'coding', 'review', 'testing'];
  for (const c of knowledge.constraints) {
    const text = readTextOrNull(path.join(root, ...c.file.split('/'))) ?? '';
    for (const line of lines(text)) {
      if (!line.trim().startsWith('|')) continue;
      const hit = phaseWords.filter(w => line.toLowerCase().includes(w));
      if (hit.length >= 3) {
        problems.push(`${c.file} 出现阶段消费矩阵（表头含 ${hit.join('/')}）`
          + '——阶段路由归各阶段自己的规则，知识不维护');
        break;
      }
    }
  }

  return problems;
}
