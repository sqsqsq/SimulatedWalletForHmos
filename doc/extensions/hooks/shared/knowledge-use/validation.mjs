/**
 * 这份判断与激活清单对不对得上 —— 集合一致、编号在册、落点引得到。
 *
 * 只回答机器答得了的那几问。内容真不真（要求是不是本需求的设计、信号指不指向真实
 * 业务特征）是语义判断，归 verifier；这里不看质量。
 *
 * 取值一律用 document 已规范化的结果，不重新读一遍 YAML。
 */
import { factsByName } from '../knowledge.mjs';
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
 * spec 扩展章「技术契约」与「埋点」两节里登记的名字 —— `constraints[].contract` 只能引用这里面的。
 *
 * 这个字段是**spec 内部**的落点声明：命中的规约要求落在哪个已登记的接口、存储键、
 * 配置项上。plan 侧的实体落点（`contracts.yaml` 的 `must` 挂在哪个实体）是另一层，
 * 由 plan 定，两者不互为抄本。不核的话它就是一列没人读的字，写错写空都没有信号。
 *
 * **这两节只在走 `/story` 时才写**，所以两节都找不到时返回 null，调用方不判这一条——
 * 那不是「缺了一章」，是这个需求本来就不写它。直接跑 spec 的需求里，
 * 这一列是自由文本，扩展对它们要保持隐形。
 *
 * **只收数据行**：表头那一格是列名（「云侧接口」「键名/表名」这类），不是实体。
 * 把它收进来，`contract: 云侧接口` 就验得过——而那是一列的名字，不是任何一个落点。
 * 表头认得出来：它的下一行是分隔行。
 *
 * **节在而一个实体都没有，返回的是空表，不是 null**：那两件事的处置相反——
 * 没有这两节 = 不判；有而空 = 任何 `contract` 都引不到东西，逐条都要报。
 *
 * @returns {Map<string, string>|null} 名字 → 它登记在哪一节（技术契约 / 埋点）
 */
const CONTRACT_SECTIONS = /^#{2,6}\s+(?:\d+(?:\.\d+)*\.?\s+)?(技术契约|埋点)\s*$/;

export function contractSections(specText) {
  const rows = String(specText ?? '').split(/\r?\n/);
  const starts = rows.map((l, i) => (CONTRACT_SECTIONS.test(l.trim()) ? i : -1)).filter(i => i >= 0);
  if (!starts.length) return null;
  const names = new Map();
  const isSeparator = (l) => /^\|[\s:|-]+\|?$/.test(String(l ?? '').trim());
  for (const start of starts) {
    const section = CONTRACT_SECTIONS.exec(rows[start].trim())[1];
    const level = rows[start].trim().match(/^#+/)[0].length;
    for (let i = start + 1; i < rows.length; i += 1) {
      const h = rows[i].trim().match(/^(#{2,6})\s+/);
      if (h && h[1].length <= level) break;
      const line = rows[i].trim();
      if (!line.startsWith('|')) continue;
      if (isSeparator(line)) continue;
      if (isSeparator(rows[i + 1])) continue;          // 下一行是分隔行 = 这行是表头
      const first = line.replace(/^\||\|$/g, '').split('|')[0]?.replace(/[`*]/g, '').trim() ?? '';
      if (!first || /^[-: ]*$/.test(first) || /^\{.*\}$/.test(first)) continue;
      if (!names.has(first)) names.set(first, section);
    }
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
  // 技术契约与埋点里登记了哪些名字。这两节只在走 /story 时写，没有就不判这一条（见 contractSections）。
  const contracts = specText === null ? null : contractSections(specText);

  const want = manifestDigest(projectRoot);
  if (use.manifestDigest && use.manifestDigest !== want) {
    problems.push(`spec/knowledge-use.yaml：manifest_digest 记的是 ${use.manifestDigest}，`
      + `激活知识现在是 ${want}——知识改过了而这份判断没重做：指纹按激活清单里每个知识文件的内容算，`
      + '这个值标明判断对着哪一版知识做');
  } else if (!use.manifestDigest) {
    problems.push(`spec/knowledge-use.yaml：缺 manifest_digest（激活知识现在是 ${want}）`
      + '——这个值标明判断对着哪一版知识做，按激活清单里每个知识文件的内容算');
  }

  // facts：激活即事实，只判「登记的那些在册」，不要求逐份登记——
  // 用没用到某一份事实是作者的判断，机器数不出来。登记了就按面记：用了哪一面、拿它做什么——
  // 按文件记答不了「用的是哪个事实」。
  const factByName = factsByName(knowledge);
  for (const row of use.facts) {
    const id = text(row, 'id');
    if (!id) { problems.push('spec/knowledge-use.yaml：facts 里有一行没写 id——事实按 id 对激活事实件的 name 认'); continue; }
    const fact = factByName.get(id);
    if (!fact) {
      problems.push(`spec/knowledge-use.yaml：facts 里的「${id}」不在激活清单的事实件里`
        + `（在册的：${[...factByName.keys()].join('、')}）——id 按激活事实件 frontmatter 的 name 认`);
      continue;
    }
    const used = Array.isArray(row.used) ? row.used : [];
    const unit = fact.form === 'halves' ? '篇' : '面';
    if (!used.length) {
      problems.push(`spec/knowledge-use.yaml：facts 的「${id}」没写 used——登记了的事实按${unit}记用法：used 逐${unit}一项，facet 是${unit}名，used_for 是拿它做了什么`);
    }
    for (const u of used) {
      const facet = text(u, 'facet');
      if (!fact.units.includes(facet)) {
        problems.push(`spec/knowledge-use.yaml：facts 的「${id}」${facet ? `没有${unit}「${facet}」` : '有一项 facet 空着'}`
          + `（有：${fact.units.join('、')}）——facet 按这份事实的${unit}名认，骨架注释里列着`);
        continue;
      }
      if (!text(u, 'used_for')) problems.push(`spec/knowledge-use.yaml：facts「${id}·${facet}」没写 used_for——评审者按它回查这一${unit}用在了哪个决定上`);
    }
  }

  // constraints：激活的每一条都要有去处
  const naDomains = new Map();
  for (const row of use.domains) {
    const prefix = text(row, 'prefix');
    if (!prefix) { problems.push('spec/knowledge-use.yaml：constraint_domains 里有一行没写 prefix——整域按 prefix 对激活规约的域前缀认'); continue; }
    if (!knowledge.prefixes.includes(prefix)) {
      problems.push(`spec/knowledge-use.yaml：constraint_domains 的域前缀「${prefix}」不在激活清单里`
        + `（在册的：${knowledge.prefixes.join('、')}）——域前缀从激活规约的条目编号派生`);
      continue;
    }
    if (row.applicable !== false) {
      problems.push(`spec/knowledge-use.yaml：constraint_domains 的「${prefix}」写了 applicable: true——`
        + 'constraint_domains 只登记整域不适用（applicable: false）；域内条目命中与否在 constraints 逐条判');
      continue;
    }
    if (isEmptyReason(text(row, 'reason'))) {
      problems.push(`spec/knowledge-use.yaml：constraint_domains 的「${prefix}」判整域不适用但没写依据`
        + '——依据要指出命中条件里哪个事实在本需求中不成立，「不涉及」不是依据');
    }
    naDomains.set(prefix, text(row, 'reason'));
  }

  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const seen = new Set();
  for (const row of use.constraints) {
    const id = text(row, 'id');
    if (!id) { problems.push('spec/knowledge-use.yaml：constraints 里有一行没写 id——条目按 id 对激活规约的编号认'); continue; }
    if (seen.has(id)) problems.push(`spec/knowledge-use.yaml：constraints 里的 ${id} 登记了两次——每条激活条目只有一个判断`);
    seen.add(id);
    const entry = byId.get(id);
    if (!entry) {
      problems.push(`spec/knowledge-use.yaml：constraints 里的 ${id} 不在激活清单里——编号按激活清单登记的规约条目表认`);
      continue;
    }
    if (naDomains.has(entry.prefix)) {
      problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 所在的域 ${entry.prefix} 已判整域不适用，却又逐条登记了——`
        + '一个域只有一种判法：整域不适用时域内条目不逐条登记，域里有命中时逐条判、不判整域');
      continue;
    }
    if (row.applicable === true) {
      if (entry.reviewAction) {
        // 它照样可能命中——命中的结果是一次跨团队的动作，不是代码要求。
        // 判命中就报错的话，作者要绕开只能写「不命中」，那份判断从此与事实不符，
        // 而下游读的正是它。所以这里只核两件事：说清为什么命中；别写成代码要求。
        if (isEmptyReason(text(row, 'reason'))) {
          problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 是评审动作条目，判命中要写 reason——`
            + '评审动作不产生代码要求，命中的依据在 reason，要做的动作归《决策与评审记录》');
        }
        const wrote = ['requirement', 'contract']
          .filter(f => (f === 'requirement' ? requirements(row).length : text(row, f)));
        if (wrote.length) {
          problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 的处置标了（评审动作），不产生代码要求，却写了 ${wrote.join(' / ')}——`
            + '评审动作的落点是 decision（走 /story 的议题 id）或 impact（不走 /story 时谁、在哪份产物里表态）');
        }
        if (text(row, 'decision') && text(row, 'impact')) {
          problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 同时写了 decision 与 impact——评审动作的落点只有一处：走 /story 的是 decision（议题 id），不走的是 impact`);
        }
        continue;
      }
      if (text(row, 'decision')) {
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 写了 decision——decision 只用于处置是（评审动作）的条目；`
          + '这一条产生代码要求，落点是 contract（技术契约或埋点里登记的名字）或 impact（实际影响对象）');
      }
      // 命中但本轮豁免：强制力决定允不允许、补偿要不要写；豁免不写要求与落点
      if (row.waived !== undefined) {
        const w = row.waived;
        if (!w || typeof w !== 'object') {
          problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 的 waived 不是块——waived 按映射读，下面缩进的 reason 与 compensation 是它的两个键`);
        } else if (entry.force === '红线') {
          problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 是红线，写了 waived——红线命中就要落实，本轮豁免只对基线与建议成立`);
        } else {
          if (isEmptyReason(text(w, 'reason'))) problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 本轮豁免没写 reason——reason 说明这一轮为什么不做，评审人按它表态`);
          if (entry.force === '基线' && !text(w, 'compensation')) {
            problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 是基线，本轮豁免要写 compensation——基线豁免要有补偿，compensation 写不做它时用什么补上`);
          }
        }
        continue;
      }
      if (!requirements(row).length) {
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 判命中却没写 requirement——命中而不说要求做什么，spec 的「规约」与下游 plan、编码都拿不到：要求从 requirement 投影`);
      }
      // 落点二选一，**由作者显式声明是哪一种**：`contract` 是技术契约或埋点里登记的名字（验真），
      // `impact` 是实际影响对象（不对应登记名字的那一类）。
      // 不按「查不查得到」反推类型：接口名拼错也会滑成非实体落点，验真永远不会失败。
      const at = text(row, 'contract');
      const impact = text(row, 'impact');
      if (!at && !impact) {
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 判命中却没写落点——落点类型由作者声明：`
          + '`contract` 是技术契约或埋点里登记过的接口/存储键/配置项/统计点名（门禁核它在那两节里），`impact` 是实际影响对象'
          + '（点名，「页面」「资源」这种泛称不算）');
      } else if (at && impact) {
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 同时写了 contract 与 impact——一条命中只有一种落点：`
          + '落在登记名字上的是 contract，落在别处的是 impact');
      }
      // `contracts === null` = 这个需求不写技术契约与埋点，本条不判；空集合是**判得了的**：
      // 那一章在，只是一个实体都没登记，于是任何 `contract` 都引不到东西。
      if (at && contracts && !contracts.has(at)) {
        const listed = contracts.size
          ? `（已登记的：${[...contracts.keys()].slice(0, 6).join('、')}${contracts.size > 6 ? '…' : ''}）`
          : '（技术契约与埋点现在一个名字都没登记）';
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 的 contract「${at}」不在技术契约与埋点里${listed}`
          + '——contract 按这两节各表数据行第一格登记的接口、存储键、配置项或统计点名核；'
          + '不落在这些名字上的落点属于 impact');
      }
    } else if (row.applicable === false) {
      if (isEmptyReason(text(row, 'reason'))) {
        problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 判不命中但没写依据——依据要可回查到命中条件里的事实，「不涉及」三个字不算`);
      }
    } else {
      problems.push(`spec/knowledge-use.yaml：constraints 的 ${id} 的 applicable 不是 true / false（现在是「${row.applicable}」）——applicable 按 YAML 布尔值读`);
    }
  }

  const missing = knowledge.entries
    .filter(e => !seen.has(e.id) && !naDomains.has(e.prefix))
    .map(e => e.id);
  if (missing.length) {
    problems.push(`spec/knowledge-use.yaml：这些激活条目没有去处：${missing.join('、')}——`
      + '去处是 constraints 里逐条的命中判断，或所在域在 constraint_domains 里的整域不适用；'
      + '没有去处是「没判过」，与「判了不命中」是两件事');
  }

  // patterns：只登记候选，候选须在册。**零在册模式是合法业务**——
  // patterns: [] 就是「没有可判断的候选」的正常登记，不要求作者另写一行
  // 「为什么都不需要」：候选集是空的，那种行注定只有一种填法，问了等于没问。
  if (!use.patterns.length && knowledge.patternIds.length > 0) {
    problems.push('spec/knowledge-use.yaml：patterns 一个适用单元都没登记，激活清单里有候选模式——零候选是正常结论，'
      + `登记形态是单元 + candidate「${NO_CANDIDATE}」+ signal 写的反证；空列表分不清「判过了不需要」与「压根没想这件事」`);
  }
  for (const row of use.patterns) {
    const unit = text(row, 'unit');
    if (!unit) { problems.push('spec/knowledge-use.yaml：patterns 里有一行没写 unit——候选按业务单元登记'); continue; }
    const cand = text(row, 'candidate');
    if (!text(row, 'signal')) {
      problems.push(`spec/knowledge-use.yaml：patterns 的「${unit}」没写 signal——`
        + '命中要给信号，不命中要给反证，两种都是举证');
    }
    if (!cand) {
      problems.push(`spec/knowledge-use.yaml：patterns 的「${unit}」没写 candidate——candidate 取在册候选，没有合适候选的单元是「${NO_CANDIDATE}」`);
      continue;
    }
    if (cand === NO_CANDIDATE) continue;
    if (!knowledge.patternIds.includes(cand)) {
      problems.push(`spec/knowledge-use.yaml：patterns 的候选「${cand}」不在册`
        + `（在册的：${knowledge.patternIds.join('、') || '无'}）——`
        + '候选按激活模式知识的 name 认，通用模式名不是合法值');
    }
    if (row.chosen !== undefined) {
      problems.push(`spec/knowledge-use.yaml：patterns 的「${unit}」写了 chosen——spec 只登记候选不选型，`
        + '选型要方案上下文，归 plan，结论落 contracts.yaml');
    }
  }
  return problems;
}
