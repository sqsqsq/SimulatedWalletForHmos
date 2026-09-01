/**
 * 来源单元枚举 —— 把上游材料切成可核对的最小事实单位，并取出每个单位里的可核对 token。
 *
 * ## 为什么不是「逐章取材」
 *
 * 1.0 的做法是每章一份取材路标（去 PRD 的哪几节抄什么），守恒判「每章把取材节的每行
 * 表格/数值/反引号写全」。后果是**同一个事实被四个章节合同各指一次，于是被强制写四遍**。
 * 这里改成：材料整体切成单元，守恒判「每个单元的 token 在 story 整篇有落点」——
 * 事实只需要出现一次，在哪一章由作者按叙述需要决定。
 *
 * ## 为什么 token 取全部单元格
 *
 * 基线只从表格首列取 ASCII 标识符，于是中文表格整行掉进自由文本理由——实测 9 个页面状态的
 * 触发条件整列、接口字段名、`freezeTicketId`、AC 编号全部丢失，142 条理由写着「表头」而
 * 表头压根不会成为单元。全部单元格都取，才谈得上「不丢」。
 *
 * 本模块只做**枚举与切分**，不判对错；判据在 `story-build.mjs check`。
 */
import * as crypto from 'node:crypto';
import * as path from 'node:path';

/**
 * 单元类型是**封闭集合**，十种：`paragraph` / `list_item` / `table_row` / `image` /
 * `link` / `diagram`（mermaid、flowchart 围栏）/ `blockquote` / `code`（yaml、json 围栏）/
 * `knowledge`（激活清单里的规约条目——它不从材料切出来，token 是条目编号）/
 * `decision`（决策登记里的一条——同样不从材料切出来）。
 *
 * 多一种就要同时给出它的 token 取法，不然就是漏判。这份清单以 `push()` 的调用点为准；
 * 曾经另有一个导出的常量重列一遍，零消费者——两份清单迟早对不上，删了。
 */

/**
 * 决策登记 → 来源单元。
 *
 * **为什么是独立通道而不是第七份材料**：决策件是流程里的活件——评审回填、遗漏补写，
 * 它本来就会在流程中合法地变。上游材料的指纹门禁防的是「材料在枚举之后还在长而没人
 * 重跑 init」，把活件塞进那条链，等于每改一条决策就撞一次 BLOCKER。规约条目早就是
 * 这么处理的，同构即可。
 *
 * **为什么必须成为单元**：取舍理由在材料里本来就没有——它是起草时判出来的。不给它
 * 落点义务，守恒链就永远不会要求它出现，于是产物里满篇结论、一条理由都没有
 * （实测两份产物：一份只有一条取舍成形，另一份零条）。
 *
 * token 留空：取舍是纯中文叙述，机器定不了落点，由作者分配、由裁决者逐条裁。
 * `status` 原样带出：已定的那些要在正文的取舍位置出现，开放议题不承担正文落点义务
 * （它还没有结论，写进正文反而是把未定的事说成定了）。
 *
 * @param {{id, status, title, clarification, decider}[]} decisions
 */
export function decisionUnits(decisions) {
  return (decisions ?? []).filter(d => d && d.id).map(d => {
    const body = [d.title, d.clarification]
      .map(x => String(x ?? '').trim()).filter(Boolean).join(' ｜ ');
    return {
      key: `DECISION:${d.id}`,
      doc: 'DECISIONS',
      kind: 'decision',
      section: String(d.decider ?? ''),
      line: 0,
      text: body.slice(0, 400),
      tokens: [],
      machine_facing: false,
      status: d.status === 'settled' ? 'settled' : 'open',
    };
  });
}

/**
 * 激活规约条目 → 来源单元。
 *
 * 逐条判定原先落在一份独立的判定记录文件里，那份文件退场后既无作业指引也无门禁——
 * 规约的「知识应用」在 story 侧就这么丢过一次。把条目变成来源单元，它就和材料里的
 * 其它事实走同一条守恒链：一条不落，缺一条点名一条。
 *
 * token 是**编号**：判定表里出现编号是允许的（那是给评审者的完备性回显）；
 * 正文里仍写中文规约名，归档件红线拦的是正文里的仓内标识。
 *
 * @param {{id, domainTitle, constraint}[]} entries `activeKnowledge().entries`
 */
export function knowledgeUnits(entries) {
  return (entries ?? []).map(e => ({
    key: `KNOWLEDGE:${e.id}`,
    doc: 'KNOWLEDGE',
    kind: 'knowledge',
    section: e.domainTitle ?? '',
    line: 0,
    text: `${e.domainTitle ?? ''} ｜ ${e.constraint ?? ''}`.trim(),
    tokens: [e.id],
    machine_facing: false,
    domain: e.domainTitle ?? '',
  }));
}

/** 围栏语言 → 单元类型。未列出的围栏按 code 处理。 */
const DIAGRAM_LANGS = new Set(['mermaid', 'flowchart', 'sequencediagram', 'graph', 'plantuml']);

/** 带量纲的数值：阈值、时长、次数——它们是最容易在改写中丢掉的事实。 */
const NUMERIC_RE = /\d+(?:\.\d+)?\s*(?:ms|毫秒|秒|s|分钟|min|小时|h|次|条|个|天|kb|mb|%)/gi;

/** ASCII 标识符：接口名、字段名、存储键。长度 ≥4 才取——短的碰巧命中太多。 */
const IDENT_RE = /\b[A-Za-z_][A-Za-z0-9_.]{3,}\b/g;

/** 反引号跨度：作者显式标注的可核对名字。 */
const CODE_SPAN_RE = /`([^`\n]+)`/g;

const IMAGE_RE = /!\[([^\]]*)\]\(([^)\s]+)/g;
const LINK_RE = /(?<!!)\[([^\]]*)\]\((https?:\/\/[^)\s]+)/g;

function sha8(s) {
  return crypto.createHash('sha256').update(s, 'utf-8').digest('hex').slice(0, 8);
}

/** 一行拆单元格；`\|` 是字面竖线不是分隔符。 */
function splitCells(row) {
  const out = [];
  let cur = '';
  for (let i = 0; i < row.length; i++) {
    if (row[i] === '\\' && row[i + 1] === '|') { cur += '|'; i++; continue; }
    if (row[i] === '|') { out.push(cur); cur = ''; continue; }
    cur += row[i];
  }
  out.push(cur);
  return out.map(c => c.trim());
}

/**
 * 从一段文本里取全部可核对 token。
 *
 * @param {string} text
 * @param {string[]} idShapes 合同声明的编号形态（正则源），命中的编号也算 token
 * @param {Function|null} exclude 合同声明的排除判定
 * @param {boolean} idOnly 只取编号形态命中——本轮生成的中间产物用（合同 `derived`）。
 *   它的工程细节（标识、带单位数值、包名）的家是那份产物自己；逼它们在归档叙事件里
 *   找落点，只会长出散文尾巴与倾倒区。业务编号仍守恒：那是评审人认得的东西。
 */
function tokensOf(text, idShapes = [], exclude = null, idOnly = false) {
  const s = String(text ?? '');
  const out = new Set();
  if (!idOnly) {
    for (const m of s.matchAll(CODE_SPAN_RE)) out.add(m[1].trim());
    for (const m of s.matchAll(IDENT_RE)) out.add(m[0]);
    for (const m of s.matchAll(NUMERIC_RE)) out.add(m[0].replace(/\s+/g, ''));
    for (const m of s.matchAll(IMAGE_RE)) out.add(path.basename(m[2]));
    for (const m of s.matchAll(LINK_RE)) out.add(m[2]);
  }
  for (const shape of idShapes) {
    try {
      for (const m of s.matchAll(new RegExp(shape, 'g'))) out.add(m[0]);
    } catch {
      // 形态写错了不该让整次枚举崩掉；check 会单独报「编号形态不是合法正则」
    }
  }
  // 排除表由合同给（仓内单号、工程代号、spec Scope 里的模块名）：
  // 要求 story 写出模块目录名，与归档件红线「不写仓内路径与模块名」直接冲突——
  // 作者只能违反其一。这里由数据决定排除什么，本模块不写任何具体词。
  return [...out].filter(t => t && t.length >= 2 && !(exclude && exclude(t)));
}

/**
 * 把一份材料切成单元。
 *
 * @param {string} text 材料全文
 * @param {string} doc 材料标识（PRD / SE / SPEC / DESIGN）
 * @param {{idShapes?: string[], excludeToken?: Function, idTokensOnly?: boolean,
 *          machineFacing?: {unit_kinds?: string[], table_columns?: string[]},
 *          templateNotes?: string[]}} opts
 *   `templateNotes`：这份材料由模板生成时，模板约定「不是事实」的那几类单元
 * @returns {{key, doc, kind, section, line, text, tokens, machine_facing}[]}
 */
export function enumerateUnits(text, doc, opts = {}) {
  const idShapes = opts.idShapes ?? [];
  const exclude = typeof opts.excludeToken === 'function' ? opts.excludeToken : null;
  // 合同 `derived` 的那份材料只守业务编号——是数据说了算，本文件不认识任何一份材料的名字
  const idOnly = opts.idTokensOnly === true;
  // 这份材料自己在需求目录里的位置：图片引用是相对它写的，判「引的是不是既有落盘位置」
  // 要先能把相对路径还原回需求目录里的那一条。
  const docPath = opts.docPath ?? '';
  const mf = opts.machineFacing ?? {};
  // 两个来源合成同一个「这类单元不是事实」的集合：
  //   `machine_facing.unit_kinds` —— 按**用途**声明（工具读的登记项，对所有材料生效）；
  //   `templateNotes`            —— 按**生成它的模板约定**声明（只对那一份材料生效）。
  // 两者都是合同数据，本文件不写任何具体类型名。
  const mfKinds = new Set([...(mf.unit_kinds ?? []), ...(opts.templateNotes ?? [])]);
  const mfColumns = new Set(mf.table_columns ?? []);

  const lines = String(text ?? '').split(/\r?\n/);
  const units = [];
  let section = '';
  let tableHeaders = null;
  let para = [];
  let paraLine = 0;
  let fence = null;          // {lang, start, body[]}

  const flushPara = () => {
    if (!para.length) return;
    const body = para.join(' ').trim();
    if (body) push('paragraph', body, paraLine);
    para = [];
  };

  const push = (kind, body, line, extra = {}) => {
    const machineFacing = mfKinds.has(kind) || extra.machineFacing === true;
    // token 与正文同源：模型看到什么，机器就核什么。两者分家过一版——表格行的
    // token 只从非机器面列取、正文却是整行，于是「不用守恒」的列照样被抄进产物。
    const src = body;
    units.push({
      key: `${doc}:${line}:${sha8(`${doc}|${line}|${body}`)}`,
      doc,
      docPath,
      kind,
      section,
      line,
      text: body.slice(0, 400),
      tokens: machineFacing ? [] : (extra.tokens ?? tokensOf(src, idShapes, exclude, idOnly)),
      machine_facing: machineFacing,
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const s = raw.trim();

    // 围栏：diagram 与 code 各成一个单元，内容不再逐行切
    if (s.startsWith('```')) {
      if (fence) {
        const lang = fence.lang.toLowerCase();
        const kind = DIAGRAM_LANGS.has(lang) ? 'diagram' : 'code';
        push(kind, fence.body.join('\n'), fence.start);
        fence = null;
      } else {
        flushPara();
        fence = { lang: s.slice(3).trim(), start: i + 1, body: [] };
      }
      continue;
    }
    if (fence) { fence.body.push(raw); continue; }

    if (!s) { flushPara(); tableHeaders = null; continue; }

    if (s.startsWith('#')) {
      flushPara();
      tableHeaders = null;
      section = s.replace(/^#+\s*/, '').trim();
      continue;
    }

    if (s.startsWith('|')) {
      flushPara();
      const cells = splitCells(s.replace(/^\|/, '').replace(/([^\\])\|$/, '$1'));
      if (cells.every(c => /^[-: ]*$/.test(c))) continue;          // 分隔行
      if (!tableHeaders) { tableHeaders = cells; continue; }        // 表头本身不是单元
      // **机器面按列排除，不整行打标**：一行里有「置信度」这种机器列，不代表同一行的
      // 「触发条件」也不用守恒。基线正是在这里丢了 9 个页面状态的触发条件整列。
      //
      // 排除是**连正文一起排**，不只是免掉 token 义务：单元正文是模型分配与渲染时
      // 唯一读到的东西，工具面的列留在正文里，它就照抄进产物——实测两份产物的术语表
      // 抄进十几个类名、附录抄进整句检索结论，都是从这里来的。
      const kept = cells.filter((c, idx) => c && !mfColumns.has((tableHeaders[idx] ?? '').trim()));
      const allMachine = kept.length === 0;
      // 整行皆机器面时保留整行原样：这一行本来就整体不参与守恒，正文只用于报错定位。
      push('table_row', (allMachine ? cells.filter(Boolean) : kept).join(' ｜ '), i + 1,
        { machineFacing: allMachine });
      continue;
    }
    tableHeaders = null;

    if (s.startsWith('>')) { flushPara(); push('blockquote', s.replace(/^>\s?/, ''), i + 1); continue; }

    if (/^[-*+]\s|^\d+[.)]\s/.test(s)) {
      flushPara();
      push('list_item', s.replace(/^([-*+]|\d+[.)])\s+/, ''), i + 1);
      continue;
    }

    // 图片与外链单独成单元——它们最容易在改写中整个丢掉，而守恒的是「这张图/这个链接还在」，
    // 不是它周围那句话。token 只取 basename 与 URL 本身，不把路径拆成一堆噪声。
    let media = false;
    for (const m of s.matchAll(IMAGE_RE)) {
      flushPara();
      push('image', m[0], i + 1,
        { tokens: idOnly ? [] : [path.basename(m[2])].filter(t => !(exclude && exclude(t))) });
      media = true;
    }
    for (const m of s.matchAll(LINK_RE)) {
      flushPara();
      push('link', m[0], i + 1,
        { tokens: idOnly ? [] : [m[2]].filter(t => !(exclude && exclude(t))) });
      media = true;
    }
    if (media) continue;

    para.push(s);
    if (para.length === 1) paraLine = i + 1;
  }
  flushPara();
  if (fence) push('code', fence.body.join('\n'), fence.start);

  return units;
}

/**
 * 跨材料内容去重：正文规范化后相同的单元互相登记 `also_in`。
 *
 * 保留而不合并——同一事实在 PRD 与 SE 各说一次是常态，story 里写一次就够；
 * 但要让 audit 知道它们是同一件事，否则作者会被要求为每一份各写一遍。
 */
export function linkDuplicates(units) {
  const byNorm = new Map();
  for (const u of units) {
    const norm = u.text.replace(/\s+/g, '').toLowerCase();
    if (!norm) continue;
    if (!byNorm.has(norm)) byNorm.set(norm, []);
    byNorm.get(norm).push(u);
  }
  for (const group of byNorm.values()) {
    if (group.length < 2) continue;
    for (const u of group) {
      u.also_in = group.filter(o => o.key !== u.key).map(o => o.key);
    }
  }
  return units;
}
