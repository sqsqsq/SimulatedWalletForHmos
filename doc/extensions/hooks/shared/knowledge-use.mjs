/**
 * knowledge-use —— spec 阶段知识判断的**唯一结构化真源**与它的投影。
 *
 * ## 这份文件解决什么
 *
 * 判断「哪条规约命中、本需求要求做什么」「哪些模式是候选」，此前直接写在 `spec.md`
 * 的 §10/§11 两张 markdown 表里。人读的表同时当机器真源，代价是每一条机械判据都要
 * 先把表解析回结构（表头找列、单元格剥装饰、编号抽正则），而作者每次手填都可能把
 * 表写歪一点点——判据于是不断在「解析得动人写的表」上加补丁。
 *
 * 现在倒过来：作者只编辑 `spec/knowledge-use.yaml`，§10/§11 是从它**确定性生成**的
 * 只读区。人读的投影不再是判断的真源，两者不一致时错的一定是投影。
 *
 * ## 三类知识各自的生命周期（合同）
 *
 * - **facts**：激活即事实，不判命中与否。这里只记「用它做了什么」，供评审者回查。
 * - **constraints**：spec 判命中，命中的写清**本需求要求做什么**；不命中的给可回查依据。
 *   落点（哪个接口、哪个存储键）与验证方式由 plan 定，不在这里。
 * - **patterns**：spec **只登记候选，不选型**。选型缺方案上下文，那是 plan 的事。
 *
 * ## 完备性怎么判
 *
 * 激活清单里的每一条约束条目，都要在这份文件里有去处：要么逐条登记（命中或不命中），
 * 要么被一条「整域不适用」覆盖。漏一条就是**没判过**——而没判过与判了不命中，
 * 对读者是完全不同的两件事。
 *
 * 既是库也是命令：`node knowledge-use.mjs render --feature <名> [--project-root <路径>]`
 * 把生成区写进 `spec.md`。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { parseYaml } from './yaml-lite.mjs';
import { activeKnowledge } from './knowledge.mjs';
import { extensionRoot, featureRoot, readTextOrNull, relDisplay } from './paths.mjs';

const SCHEMA = 1;
const USE_FILE = ['spec', 'knowledge-use.yaml'];

/** 生成区的边界标记。两个标记之间的每一个字节都由本模块写。 */
const BEGIN = '<!-- knowledge-use:begin ';
const END = '<!-- knowledge-use:end -->';

/** 生成区的名字 —— 同时是 spec 里那两章的标题关键词。 */
const ZONES = [
  { key: 'constraints', name: '规约约束要求', heading: /规约约束要求/ },
  { key: 'patterns', name: '设计模式候选登记', heading: /设计模式候选/ },
];

const NO_CANDIDATE = '无候选';

export class UseError extends Error {}

function fail(message) {
  throw new UseError(message);
}

function usePath(projectRoot, feature) {
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
  const raw = readTextOrNull(path.join(root, 'manifest.yaml'));
  if (raw === null) fail('读不到 manifest.yaml');
  const list = parseYaml(raw)?.provides?.knowledge ?? [];
  const h = createHash('sha256');
  for (const rel of list) {
    const relPosix = String(rel).replace(/\\/g, '/');
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

function text(row, field) {
  return String(row?.[field] ?? '').trim();
}

/**
 * 「没写依据」的确定性形态：空，或者恰好就是那三个字。
 *
 * 不设字数下限——**多少字算够是配额，不是不变量**：一句十二字的套话与一句八字的
 * 具体依据，长度分不出高下。依据站不站得住是语义判断，归 verifier。
 */
function isEmptyReason(reason) {
  return !reason || /^不涉及[。.]?$/.test(reason);
}

/**
 * §9 技术契约章里登记的名字 —— `constraints[].contract` 只能引用这里面的。
 *
 * 这个字段是**spec 内部**的落点声明：命中的规约要求落在哪个已登记的接口、存储键、
 * 配置项上。plan 侧的实体落点（`contracts.yaml` 的 `must` 挂在哪个实体）是另一层，
 * 由 plan 定，两者不互为抄本。不核的话它就是一列没人读的字，写错写空都没有信号。
 *
 * **§9 那一章只在走 `/story` 时才写**，所以找不到它返回 null，调用方不判这一条——
 * 那不是「缺了一章」，是这个需求本来就不写它。直接跑 spec 的需求里，
 * 这一列是自由文本，扩展对它们要保持隐形。
 */
function contractNames(specText) {
  const rows = String(specText ?? '').split(/\r?\n/);
  const start = rows.findIndex(l => /^#{2,4}\s+.*技术契约/.test(l.trim()));
  if (start < 0) return null;
  const level = (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  const names = new Set();
  for (let i = start + 1; i < rows.length; i += 1) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const line = rows[i].trim();
    if (!line.startsWith('|')) continue;
    const first = line.replace(/^\||\|$/g, '').split('|')[0]?.replace(/[`*]/g, '').trim() ?? '';
    if (!first || /^[-: ]*$/.test(first) || /^\{.*\}$/.test(first)) continue;
    names.add(first);
  }
  return names;
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
 * 这份判断与激活清单对不对得上 —— **集合一致，不判内容质量**。
 *
 * 内容真不真（要求是不是本需求的设计、信号指不指向真实业务特征）是语义判断，
 * 归 verifier。这里只回答机器答得了的那几问：判全了吗、编号在册吗、候选在册吗。
 */
export function coverageProblems(projectRoot, knowledge, use, specText = null) {
  const problems = [];
  // §9 里登记了哪些名字。那一章只在走 /story 时写，没有它就不判这一条（见 contractNames）。
  const contracts = specText === null ? null : contractNames(specText);

  const want = manifestDigest(projectRoot);
  if (use.manifestDigest && use.manifestDigest !== want) {
    problems.push(`knowledge-use.yaml 记的 manifest_digest 是 ${use.manifestDigest}，`
      + `激活清单现在是 ${want} —— 知识改过了而这份判断没重做。`
      + '逐条看一遍改动是否影响本需求的判断，再把 digest 更新成新值');
  } else if (!use.manifestDigest) {
    problems.push(`knowledge-use.yaml 缺 manifest_digest（当前应为 ${want}）`
      + ' —— 没有它就看不出「判断做的时候知识是哪一版」');
  }

  // facts：激活即事实，只判「登记的那些在册」，不要求逐条登记——
  // 用没用到某一份事实是作者的判断，机器数不出来。
  const factNames = new Set();
  for (const f of knowledge.facts) {
    factNames.add(f.file);
    if (f.name) factNames.add(f.name);
    factNames.add(path.basename(f.file, '.md'));
  }
  for (const row of use.facts) {
    const id = text(row, 'id');
    if (!id) { problems.push('facts 里有一行没写 id'); continue; }
    if (!factNames.has(id)) {
      problems.push(`facts 里的「${id}」不在激活清单的事实件里`
        + `（在册的：${[...factNames].filter(n => !n.includes('/')).join('、')}）`);
    }
    if (!text(row, 'used_for')) {
      problems.push(`facts 的「${id}」没写 used_for —— 用它做了什么是评审者要回查的`);
    }
  }

  // constraints：激活的每一条都要有去处
  const naDomains = new Map();
  for (const row of use.domains) {
    const prefix = text(row, 'prefix');
    if (!prefix) { problems.push('constraint_domains 里有一行没写 prefix'); continue; }
    if (!knowledge.prefixes.includes(prefix)) {
      problems.push(`constraint_domains 的域前缀「${prefix}」不在激活清单里`
        + `（在册的：${knowledge.prefixes.join('、')}）`);
      continue;
    }
    if (row.applicable !== false) {
      problems.push(`constraint_domains 的「${prefix}」写了 applicable: true —— `
        + '这一段只用来登记**整域不适用**；域内有命中条目时逐条登记到 constraints');
      continue;
    }
    if (isEmptyReason(text(row, 'reason'))) {
      problems.push(`constraint_domains 的「${prefix}」判整域不适用但没写依据`
        + ' —— 依据要可回查：「本需求无新增对外开放页面或接口」是依据，「不涉及」不是');
    }
    naDomains.set(prefix, text(row, 'reason'));
  }

  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const seen = new Set();
  for (const row of use.constraints) {
    const id = text(row, 'id');
    if (!id) { problems.push('constraints 里有一行没写 id'); continue; }
    if (seen.has(id)) problems.push(`constraints 里的 ${id} 登记了两次`);
    seen.add(id);
    const entry = byId.get(id);
    if (!entry) {
      problems.push(`constraints 里的 ${id} 不在激活清单里 —— 编号写错，或那条规约已下架`);
      continue;
    }
    if (naDomains.has(entry.prefix)) {
      problems.push(`${id} 所在的域 ${entry.prefix} 已判整域不适用，却又逐条登记了 —— `
        + '两种判法留一种：域不适用就不逐条登记，域里有命中就不判整域');
      continue;
    }
    if (row.applicable === true) {
      if (entry.reviewAction) {
        problems.push(`${id} 的处置标了（评审动作），不产生代码要求 —— `
          + '它的动作归《决策与评审记录》的跨团队协同，不写进本需求的要求');
      }
      if (!requirements(row).length) {
        problems.push(`${id} 判命中却没写 requirement —— 命中而不说要求做什么，编码那里拿不到`);
      }
      // 落点二选一，**由作者显式声明是哪一种**：`contract` 是 §9 里的实体名（验真），
      // `impact` 是实际影响对象（RTL、图标、文案、翻译这类本来就没有 §9 实体）。
      // 不按「查不查得到」反推类型：接口名拼错也会滑成非实体落点，验真永远不会失败。
      const at = text(row, 'contract');
      const impact = text(row, 'impact');
      if (!at && !impact) {
        problems.push(`${id} 判命中却没写落点 —— 二选一：`
          + '`contract` 写 §9 登记过的接口/存储键/配置项名，或 `impact` 写实际影响对象'
          + '（「页面」「资源」这种泛称不算，要点名）');
      } else if (at && impact) {
        problems.push(`${id} 同时写了 contract 与 impact —— 二选一：`
          + '落在 §9 实体上就写 contract，落在别处就写 impact');
      }
      if (at && contracts && contracts.size && !contracts.has(at)) {
        problems.push(`${id} 的 contract「${at}」不在 §9 技术契约里`
          + `（已登记的：${[...contracts].slice(0, 6).join('、')}${contracts.size > 6 ? '…' : ''}）`
          + ' —— 这一列引的是 §9 登记过的接口、存储键或配置项名，先在那里登记；'
          + '落点不在 §9 实体上时改用 impact');
      }
    } else if (row.applicable === false) {
      if (isEmptyReason(text(row, 'reason'))) {
        problems.push(`${id} 判不命中但没写依据 —— 依据要可回查，「不涉及」三个字不算`);
      }
    } else {
      problems.push(`${id} 的 applicable 不是 true / false（现在是「${row.applicable}」）`);
    }
  }

  const missing = knowledge.entries
    .filter(e => !seen.has(e.id) && !naDomains.has(e.prefix))
    .map(e => e.id);
  if (missing.length) {
    problems.push(`这些激活条目在 knowledge-use.yaml 里没有去处：${missing.join('、')} —— `
      + '要么逐条登记命中与否，要么用 constraint_domains 判它整域不适用。'
      + '漏一条是「没判过」，与「判了不命中」是两件事');
  }

  // patterns：只登记候选，候选须在册
  if (!use.patterns.length) {
    problems.push('patterns 一个适用单元都没登记 —— 零候选是正常结论，'
      + '但要写出单元与「为什么都不需要」，空着分不清「判过了不需要」与「压根没想这件事」');
  }
  for (const row of use.patterns) {
    const unit = text(row, 'unit');
    if (!unit) { problems.push('patterns 里有一行没写 unit'); continue; }
    const cand = text(row, 'candidate');
    if (!text(row, 'signal')) {
      problems.push(`patterns 的「${unit}」没写 signal —— `
        + '命中要给信号，不命中要给反证，两种都是举证');
    }
    if (!cand) {
      problems.push(`patterns 的「${unit}」没写 candidate（没有候选就写「${NO_CANDIDATE}」）`);
      continue;
    }
    if (cand === NO_CANDIDATE) continue;
    if (!knowledge.patternIds.includes(cand)) {
      problems.push(`patterns 的候选「${cand}」不在册`
        + `（在册的：${knowledge.patternIds.join('、') || '无'}）—— `
        + '候选只能查表填，通用模式名不是合法值');
    }
    if (text(row, 'chosen') || row.chosen !== undefined) {
      problems.push(`patterns 的「${unit}」写了 chosen —— spec 只登记候选不选型，`
        + '选型缺方案上下文，那是 plan 的事，结论落 contracts.yaml');
    }
  }
  return problems;
}

function cell(value) {
  return String(value ?? '').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ').trim();
}

/** §10 的正文：命中条目逐条一行，整域不适用各一行。 */
function renderConstraints(knowledge, use) {
  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const hits = use.constraints.filter(r => r.applicable === true
    && !(byId.get(text(r, 'id'))?.reviewAction));
  const out = [];
  out.push('| 编号 | 本需求的要求 | 落点契约名 |');
  out.push('|---|---|---|');
  if (!hits.length) {
    out.push('| （无命中条目） | 本需求没有产生代码要求的规约条目 | — |');
  }
  for (const row of hits) {
    // 一条要求一行：同一个编号有几条要求就出几行。挤进一格的话，读者要在
    // 一百多字里数分号，而每一条本来都该独立可懂。
    const at = text(row, 'contract') ? `§9 · ${cell(text(row, 'contract'))}`
      : text(row, 'impact') ? `影响 · ${cell(text(row, 'impact'))}` : '—';
    for (const req of requirements(row)) {
      out.push(`| ${cell(text(row, 'id'))} | ${cell(req)} | ${at} |`);
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

/**
 * 一条条目的要求 —— **列表**，一条一句。
 *
 * 写成一段的时候，读者要在一百多字里数分号才分得出这是几件事，而每一件本来都该
 * 独立可懂。旧写法（单句）照收：那也是一条。
 */
function requirements(row) {
  const raw = row?.requirement;
  if (Array.isArray(raw)) return raw.map(x => String(x ?? '').trim()).filter(Boolean);
  const one = String(raw ?? '').trim();
  return one ? [one] : [];
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
function applyZones(specText, rendered) {
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
 * 生成区与 YAML 对不对得上 —— 手改生成区、以及生成区之外的旧手写表，都在这里被判出来。
 *
 * 后一条是迁移期真会遇到的：这一章原先是人手填的表，加了生成区之后旧表还在，
 * 于是同一章有两张表说同一件事，而只有一张跟着 YAML 走。
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
        + ' —— 这一章的正文只有生成区一份。旧的手写表删掉，判断改到 knowledge-use.yaml 里');
    }
  }
  return problems;
}

// ---------------------------------------------------------------------------
// 命令行：render
// ---------------------------------------------------------------------------

/**
 * 骨架正文。**只摆结构，不替作者判断**——applicable 留空，依据留空。
 *
 * 说明写进文件本身而不是只写在文档里：作者打开的是这份 YAML，它得自己说清怎么填。
 */
function renderSkeleton(projectRoot, knowledge) {
  const rows = [
    '# 本阶段知识判断的唯一真源。spec 的 §10/§11 由它生成，那两章不手写。',
    '#',
    '# 怎么填：激活的每一条 constraints 都要有去处——命中写 requirement（列表，一条要求一句，',
    '# 写得下一个人照着能编码），不命中写 reason（可回查的依据；「不涉及」三个字不算依据）。',
    '# contract 引 spec §9 里登记的名字，没有就留空串。填完跑 render。',
    `schema: ${SCHEMA}`,
    `manifest_digest: ${manifestDigest(projectRoot)}`,
    '',
    '# 用到了哪几份项目知识，各自用来做了什么。没用到的不必登记。',
    'facts:',
  ];
  for (const f of knowledge.facts) {
    rows.push(`  - id: ${f.name || path.basename(f.file, '.md')}`, '    used_for: ""');
  }
  rows.push(
    '',
    '# 整域都不适用时登记在这里（prefix / applicable: false / reason）。',
    '# 域里只要有一条命中，就不判整域、改为逐条登记到 constraints。',
    'constraint_domains: []',
    '',
    'constraints:',
  );
  for (const e of knowledge.entries) {
    rows.push(`  - id: ${e.id}`,
      '    applicable:   # true → 补 requirement（列表）与落点；false → 补 reason',
      '    #   落点二选一：contract 写 §9 登记过的名字，impact 写实际影响对象');
  }
  rows.push(
    '',
    '# 设计模式候选：**只登记不选型**（选型是 plan 的事）。',
    `# 在册候选：${knowledge.patternIds.join(' / ') || '（激活清单里没有候选）'}`,
    `# 这个单元没有合适的候选时，candidate 写「${NO_CANDIDATE}」，signal 里说明为什么没有。`,
    'patterns:',
    '  - unit: ""      # 哪一段业务；按业务切，不是整个需求一个单元',
    '    candidate: ""',
    '    signal: ""    # 从本需求的哪个事实看出它像这个模式',
    '',
  );
  return rows.join('\n');
}

/** 骨架只在开头生成一次：已经有判断在里面时不许覆盖。 */
function cmdInit(projectRoot, feature) {
  const target = usePath(projectRoot, feature);
  if (fs.existsSync(target)) {
    process.stderr.write(`${relDisplay(projectRoot, target)} 已经在了`
      + '——骨架只在开头生成一次，重来会盖掉已经做过的判断\n');
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, renderSkeleton(projectRoot, activeKnowledge(projectRoot)), 'utf-8');
  process.stdout.write(`[knowledge-use] 骨架已写入 ${relDisplay(projectRoot, target)}`
    + '：逐条填 applicable 与依据，填完跑 render\n');
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a.startsWith('--')) out[a.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = argv[++i];
  }
  return out;
}

function main(argv) {
  const [command, ...rest] = argv;
  if (command !== 'render' && command !== 'init') {
    process.stderr.write('用法：knowledge-use.mjs <init|render> --feature <名> [--project-root <路径>]\n'
      + '  init   —— 按激活清单生成骨架（条目一条不落，判断留空）\n'
      + '  render —— 判断填完之后，把 spec 的 §10/§11 生成出来\n');
    process.exit(2);
  }
  const args = parseArgs(rest);
  if (!args.feature) {
    process.stderr.write('缺 --feature <需求名>\n');
    process.exit(2);
  }
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const projectRoot = path.resolve(args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..'));
  try {
    if (command === 'init') { cmdInit(projectRoot, args.feature); return; }
    const knowledge = activeKnowledge(projectRoot);
    const use = readUse(projectRoot, args.feature);
    const specPath = path.join(featureRoot(projectRoot, args.feature), 'spec', 'spec.md');
    const specText = readTextOrNull(specPath);
    if (specText === null) {
      process.stderr.write(`读不到 ${relDisplay(projectRoot, specPath)}\n`);
      process.exit(1);
    }
    const problems = coverageProblems(projectRoot, knowledge, use, specText);
    if (problems.length) {
      process.stderr.write(`knowledge-use.yaml 还不能生成，先修这 ${problems.length} 处：\n`);
      for (const p of problems) process.stderr.write(`  · ${p}\n`);
      process.exit(1);
    }
    const next = applyZones(specText, renderZones(knowledge, use));
    fs.writeFileSync(specPath, next, 'utf-8');
    process.stdout.write(`[knowledge-use] 生成区已写入 ${relDisplay(projectRoot, specPath)}\n`);
  } catch (e) {
    process.stderr.write(`${e.message}\n`);
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main(process.argv.slice(2));
}
