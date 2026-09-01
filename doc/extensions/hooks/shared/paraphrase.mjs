/**
 * 复述判定 —— 「只写知识名称不算应用」的机械部分。
 *
 * 这个模块只回答一件事：**这段文字是不是把原文抄了一遍**。它**不回答**「这段文字是不是
 * 本需求的设计」——那是语义判断，归 verifier 的全集逐行裁决。机械层越权下语义结论，
 * 就会变成「可信专名 + 低相似改写」整类逃逸。
 *
 * ## 判定为什么必须唯一可实施
 *
 * 这类判据最容易败在本身不可实施：比较字段没定死（把渲染出的「要求」列也纳入比较，
 * 那一列天然等于原文，于是全员误杀）、规范化笼统「去标点」（把 `data_models.X.field`
 * 折叠成一团，标识符消失）、子串方向没定（反过来比会把「原文是结论的一部分」也判成抄）。
 * 所以下面四件事全部定死，改它们就是改判据：
 *
 * | 维度 | 定死为 |
 * |---|---|
 * | 比较字段 | 只有作者**自己写的**那一列（结论 / 要求 / obligation） |
 * | 来源 | 同行渲染出的原文列 + 条目的约束列、处置列、所属域落法附注 |
 * | 方向 | `规范化(输出) ⊆ 规范化(某个来源)` 才算纯复制；反向不算 |
 * | 规范化 | 去空白 + 去句读，**保留** `.` `-` `_` `/` 与字母数字 |
 *
 * 空字段不在本模块判——那是「没写」不是「抄了」，交结构门禁。
 */

/**
 * 规范化时删除的字符：中文与英文句读、成对括号、引号。
 * **刻意不含** `.` `-` `_` `/`——它们是标识符的组成部分（`data_models.Ctx.flowId`、
 * `feature-flag`、`resource_keys`），一起删掉就没法判断输出里有没有真实的契约实体名。
 */
const DROP_PUNCT_RE = /[，。；：、“”‘’《》〈〉！？…—～·「」『』（）()【】\[\]{}<>,;:!?"'`|]/g;
const WS_RE = /\s+/g;

/** 相似度提示阈值：**只影响 verifier 必答清单的排序**，不参与任何 PASS/FAIL。 */
export const SIMILARITY_HINT_THRESHOLD = 0.6;

/** 规范化：去空白、去句读，保留标识符字符。 */
export function normalize(text) {
  return String(text ?? '').replace(WS_RE, '').replace(DROP_PUNCT_RE, '');
}

/**
 * 纯复制判定。
 *
 * @param {string} output 被检字段——**作者自己写的那一列**
 * @param {string[]} sources 来源文本（同行原文列 + 条目约束/处置/落法附注）
 * @returns {{copied: boolean, source: string}} copied 为 true 时 source 是命中的来源片段
 */
export function isPureCopy(output, sources) {
  const out = normalize(output);
  if (!out) return { copied: false, source: '' };      // 空字段交结构门禁
  for (const raw of sources ?? []) {
    const src = normalize(raw);
    if (src && src.includes(out)) {
      return { copied: true, source: String(raw).slice(0, 80) };
    }
  }
  return { copied: false, source: '' };
}

/**
 * 字符级相似度（最长公共子序列比）。
 * **只用于给 verifier 排序**：把最像原文的行排在必答清单前面，方便人先看它们。
 * 不参与判定——「同义改写绕过阈值」是已实测的逃逸路径，靠阈值防不住。
 */
export function similarity(a, b) {
  const x = normalize(a);
  const y = normalize(b);
  if (!x || !y) return 0;
  return (2 * lcsLength(x, y)) / (x.length + y.length);
}

/** 对一组来源取最高相似度。 */
function maxSimilarity(output, sources) {
  let best = 0;
  for (const s of sources ?? []) best = Math.max(best, similarity(output, s));
  return best;
}

function lcsLength(a, b) {
  // 滚动数组，避免长文本上开二维表
  let prev = new Uint32Array(b.length + 1);
  let cur = new Uint32Array(b.length + 1);
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
    }
    [prev, cur] = [cur, prev];
    cur.fill(0);
  }
  return prev[b.length];
}

/**
 * 输出里有没有出现「本需求自己的名字」。
 *
 * **这是信号不是判定**：没有专名的结论很可能是通用话术，但有专名也可能是
 * 「原文 + 塞一个自造名词」。它只决定必答清单的排序，不决定谁受裁决。
 *
 * @param {string} output
 * @param {string[]} ownTerms 本需求的契约名、步骤标识等
 */
function ownTermHits(output, ownTerms) {
  const out = normalize(output);
  if (!out) return [];
  return (ownTerms ?? []).filter(t => {
    const n = normalize(t);
    return n && n.length >= 2 && out.includes(n);
  });
}

/**
 * 给一行内容打「复述嫌疑」分级，用于必答清单排序。
 *
 * @returns {{verdict: 'PURE_COPY'|'SUSPECT'|'CLEAN', reasons: string[], similarity: number, source: string}}
 *   `PURE_COPY` 是机械可判的 BLOCKER；`SUSPECT`/`CLEAN` **都要进必答清单**，
 *   只是排序不同——分级不决定覆盖面。
 */
export function classify(output, sources, ownTerms) {
  const { copied, source } = isPureCopy(output, sources);
  const sim = maxSimilarity(output, sources);
  const hits = ownTermHits(output, ownTerms);
  const reasons = [];
  if (copied) reasons.push('规范化后是来源原文的子串');
  if (!hits.length) reasons.push('未出现本需求自己的名字');
  if (sim >= SIMILARITY_HINT_THRESHOLD) reasons.push(`与原文相似度 ${sim.toFixed(2)}`);
  return {
    verdict: copied ? 'PURE_COPY' : (reasons.length ? 'SUSPECT' : 'CLEAN'),
    reasons,
    similarity: sim,
    source,
  };
}
