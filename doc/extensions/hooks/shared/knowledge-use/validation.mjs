/**
 * 这份判断与激活清单对不对得上 —— 集合一致、编号在册、落点引得到。
 *
 * 只回答机器答得了的那几问。内容真不真（要求是不是本需求的设计、信号指不指向真实
 * 业务特征）是语义判断，归 verifier；这里不看质量。
 *
 * 取值一律用 document 已规范化的结果，不重新读一遍 YAML。
 */
import * as path from 'node:path';
import { NO_CANDIDATE, manifestDigest, requirements, text } from './document.mjs';

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
 * §9.1 技术契约章里登记的名字 —— `constraints[].contract` 只能引用这里面的。
 *
 * 这个字段是**spec 内部**的落点声明：命中的规约要求落在哪个已登记的接口、存储键、
 * 配置项上。plan 侧的实体落点（`contracts.yaml` 的 `must` 挂在哪个实体）是另一层，
 * 由 plan 定，两者不互为抄本。不核的话它就是一列没人读的字，写错写空都没有信号。
 *
 * **§9.1 那一章只在走 `/story` 时才写**，所以找不到它返回 null，调用方不判这一条——
 * 那不是「缺了一章」，是这个需求本来就不写它。直接跑 spec 的需求里，
 * 这一列是自由文本，扩展对它们要保持隐形。
 *
 * **只收数据行**：表头那一格是列名（「云侧接口」「键名/表名」这类），不是实体。
 * 把它收进来，`contract: 云侧接口` 就验得过——而那是一列的名字，不是任何一个落点。
 * 表头认得出来：它的下一行是分隔行。
 *
 * **章在而一个实体都没有，返回的是空集合，不是 null**：那两件事的处置相反——
 * 没有这一章 = 不判；有这一章而空 = 任何 `contract` 都引不到东西，逐条都要报。
 */
function contractNames(specText) {
  const rows = String(specText ?? '').split(/\r?\n/);
  const start = rows.findIndex(l => /^#{2,6}\s+.*技术契约/.test(l.trim()));
  if (start < 0) return null;
  const level = rows[start].trim().match(/^#+/)[0].length;
  const names = new Set();
  const isSeparator = (l) => /^\|[\s:|-]+\|?$/.test(String(l ?? '').trim());
  for (let i = start + 1; i < rows.length; i += 1) {
    const h = rows[i].trim().match(/^(#{2,6})\s+/);
    if (h && h[1].length <= level) break;
    const line = rows[i].trim();
    if (!line.startsWith('|')) continue;
    if (isSeparator(line)) continue;
    if (isSeparator(rows[i + 1])) continue;          // 下一行是分隔行 = 这行是表头
    const first = line.replace(/^\||\|$/g, '').split('|')[0]?.replace(/[`*]/g, '').trim() ?? '';
    if (!first || /^[-: ]*$/.test(first) || /^\{.*\}$/.test(first)) continue;
    names.add(first);
  }
  return names;
}

/**
 * 这份判断与激活清单对不对得上 —— **集合一致，不判内容质量**。
 *
 * 内容真不真（要求是不是本需求的设计、信号指不指向真实业务特征）是语义判断，
 * 归 verifier。这里只回答机器答得了的那几问：判全了吗、编号在册吗、候选在册吗。
 */
export function coverageProblems(projectRoot, knowledge, use, specText = null) {
  const problems = [];
  // §9.1 里登记了哪些名字。那一章只在走 /story 时写，没有它就不判这一条（见 contractNames）。
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

  // facts：激活即事实，只判「登记的那些在册」，不要求逐份登记——
  // 用没用到某一份事实是作者的判断，机器数不出来。登记了就按面记：用了哪一面、拿它做什么——
  // 按文件记答不了「用的是哪个事实」。
  const factByName = new Map();
  for (const f of knowledge.facts) {
    for (const n of [f.file, f.name, path.basename(f.file, '.md')]) if (n) factByName.set(n, f);
  }
  for (const row of use.facts) {
    const id = text(row, 'id');
    if (!id) { problems.push('facts 里有一行没写 id'); continue; }
    const fact = factByName.get(id);
    if (!fact) {
      problems.push(`facts 里的「${id}」不在激活清单的事实件里`
        + `（在册的：${[...factByName.keys()].filter(n => !n.includes('/')).join('、')}）`);
      continue;
    }
    const used = Array.isArray(row.used) ? row.used : [];
    if (!used.length) {
      problems.push(`facts 的「${id}」没写 used —— 逐面一项：facet 写用了哪一面，used_for 写拿它做了什么`);
    }
    for (const u of used) {
      const facet = text(u, 'facet');
      if (!fact.facets.includes(facet)) {
        problems.push(`facts 的「${id}」${facet ? `没有面「${facet}」` : '有一项 facet 空着——填骨架注释列出的面名'}`
          + `（有：${fact.facets.join('、')}）`);
        continue;
      }
      if (!text(u, 'used_for')) problems.push(`facts「${id}·${facet}」没写 used_for —— 用它做了什么是评审者要回查的`);
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
        + ' —— 依据要指出命中条件里哪个事实在本需求中不成立，「不涉及」不是依据');
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
        // 它照样可能命中——命中的结果是一次跨团队的动作，不是代码要求。
        // 判命中就报错的话，作者要绕开只能写「不命中」，那份判断从此与事实不符，
        // 而下游读的正是它。所以这里只核两件事：说清为什么命中；别写成代码要求。
        if (isEmptyReason(text(row, 'reason'))) {
          problems.push(`${id} 是评审动作条目，判命中要写 reason —— `
            + '说清这一轮为什么命中它；要做的动作登记进《决策与评审记录》');
        }
        const wrote = ['requirement', 'contract']
          .filter(f => (f === 'requirement' ? requirements(row).length : text(row, f)));
        if (wrote.length) {
          problems.push(`${id} 的处置标了（评审动作），不产生代码要求 —— `
            + `${wrote.join(' / ')} 留空；落点写 decision（议题 id）或 impact（谁、在哪份产物里表态）`);
        }
        if (text(row, 'decision') && text(row, 'impact')) {
          problems.push(`${id} 同时写了 decision 与 impact —— 二选一：走 /story 的写议题 id，不走的写 impact`);
        }
        continue;
      }
      if (text(row, 'decision')) {
        problems.push(`${id} 写了 decision —— 议题落点只给处置是（评审动作）的条目；`
          + '这一条产生代码要求，落点写 contract 或 impact');
      }
      // 命中但本轮豁免：强制力决定允不允许、补偿要不要写；豁免不写要求与落点
      if (row.waived !== undefined) {
        const w = row.waived;
        if (!w || typeof w !== 'object') {
          problems.push(`${id} 的 waived 要写成块：下面缩进写 reason 与 compensation`);
        } else if (entry.force === '红线') {
          problems.push(`${id} 是红线，命中就要落实，不能本轮豁免`);
        } else {
          if (isEmptyReason(text(w, 'reason'))) problems.push(`${id} 本轮豁免没写 reason —— 为什么这一轮不做`);
          if (entry.force === '基线' && !text(w, 'compensation')) {
            problems.push(`${id} 是基线，本轮豁免要写 compensation —— 不做它时用什么补上`);
          }
        }
        continue;
      }
      if (!requirements(row).length) {
        problems.push(`${id} 判命中却没写 requirement —— 命中而不说要求做什么，编码那里拿不到`);
      }
      // 落点二选一，**由作者显式声明是哪一种**：`contract` 是 §9.1 里的实体名（验真），
      // `impact` 是实际影响对象（不对应 §9.1 登记实体的那一类）。
      // 不按「查不查得到」反推类型：接口名拼错也会滑成非实体落点，验真永远不会失败。
      const at = text(row, 'contract');
      const impact = text(row, 'impact');
      if (!at && !impact) {
        problems.push(`${id} 判命中却没写落点 —— 二选一：`
          + '`contract` 写 §9.1 登记过的接口/存储键/配置项名，或 `impact` 写实际影响对象'
          + '（「页面」「资源」这种泛称不算，要点名）');
      } else if (at && impact) {
        problems.push(`${id} 同时写了 contract 与 impact —— 二选一：`
          + '落在 §9.1 实体上就写 contract，落在别处就写 impact');
      }
      // `contracts === null` = 这个需求不写 §9.1，本条不判；空集合是**判得了的**：
      // 那一章在，只是一个实体都没登记，于是任何 `contract` 都引不到东西。
      if (at && contracts && !contracts.has(at)) {
        const listed = contracts.size
          ? `（已登记的：${[...contracts].slice(0, 6).join('、')}${contracts.size > 6 ? '…' : ''}）`
          : '（§9.1 现在一个实体都没登记）';
        problems.push(`${id} 的 contract「${at}」不在 §9.1 技术契约里${listed}`
          + ' —— 这一列引的是 §9.1 登记过的接口、存储键或配置项名，先在那里登记；'
          + '落点不在 §9.1 实体上时改用 impact');
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

  // patterns：只登记候选，候选须在册。**零在册模式是合法业务**——
  // patterns: [] 就是「没有可判断的候选」的正常登记，不要求作者另写一行
  // 「为什么都不需要」：候选集是空的，那种行注定只有一种填法，问了等于没问。
  if (!use.patterns.length && knowledge.patternIds.length > 0) {
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
    if (row.chosen !== undefined) {
      problems.push(`patterns 的「${unit}」写了 chosen —— spec 只登记候选不选型，`
        + '选型缺方案上下文，那是 plan 的事，结论落 contracts.yaml');
    }
  }
  return problems;
}
