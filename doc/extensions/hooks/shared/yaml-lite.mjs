/**
 * 最小 YAML 读取器 —— 只覆盖 contracts / acceptance / manifest 实际用到的子集。
 *
 * 支持：嵌套映射、序列（块式 `- ` 与行内 `[a, b]`）、标量（引号可选）、`#` 注释、空行。
 * 不支持：锚点别名、多行标量（`|` / `>`）、复杂键、流式映射 `{a: 1}`。
 *
 * 两条实现纪律：
 * 1. **一律 `\r?\n` 分行**——按 '\n' 切会让 CRLF 文件每行尾挂个 `\r`，
 *    行尾正则从此静默零命中（曾导致契约名集合返回空集而门禁照过）。
 * 2. **子结构按下一行的实际缩进判断**，不假设固定两空格——契约件里 2/4 空格会混用。
 *
 * **解析失败必须响亮**：本模块只在语法确实不可解析时 throw；调用方不得把异常吞成空对象
 * ——空集会让一切「集合包含」判据恒真。
 */
import { lines } from './paths.mjs';

const KV_RE = /^(\s*)([^\s#][^:]*?)\s*:\s*(.*)$/;
const ITEM_RE = /^(\s*)-\s*(.*)$/;

/** 标量解析：去引号、识别 true/false/null/数字，其余原样。 */
function scalar(raw) {
  const s = String(raw ?? '').trim();
  if (!s) return '';
  const m = s.match(/^(['"])([\s\S]*)\1$/);
  if (m) return m[2];
  // 行尾注释：只在非引号标量上剥，且要求 # 前有空白（`a#b` 是内容不是注释）
  const cut = s.replace(/\s+#.*$/, '').trim();
  if (cut === 'true') return true;
  if (cut === 'false') return false;
  if (cut === 'null' || cut === '~') return null;
  if (/^-?\d+$/.test(cut)) return Number(cut);
  if (/^-?\d*\.\d+$/.test(cut)) return Number(cut);
  return cut;
}

/** 行内序列 `[a, b, c]`；元素里带括号的场景本子集不支持，原样落回标量。 */
function inlineSeq(raw) {
  const s = String(raw).trim();
  if (!(s.startsWith('[') && s.endsWith(']'))) return null;
  const inner = s.slice(1, -1).trim();
  if (!inner) return [];
  return inner.split(',').map(x => scalar(x));
}

function indentOf(line) {
  return line.match(/^(\s*)/)[1].length;
}

function isBlank(line) {
  return !line.trim() || line.trim().startsWith('#');
}

/**
 * 解析一个块，返回 { value, next }。
 * @param rows 全部行
 * @param start 起始行号
 * @param baseIndent 本块的缩进（该缩进上的键/项属于本块）
 */
function parseBlock(rows, start, baseIndent) {
  let i = start;
  let map = null;
  let seq = null;

  while (i < rows.length) {
    const line = rows[i];
    if (isBlank(line)) { i++; continue; }
    const ind = indentOf(line);
    if (ind < baseIndent) break;
    if (ind > baseIndent) {
      // 更深的缩进应当已被上一轮的子块吞掉；走到这里说明缩进不一致
      throw new Error(`yaml-lite：第 ${i + 1} 行缩进不一致（期望 ${baseIndent}，实际 ${ind}）`);
    }

    const item = line.match(ITEM_RE);
    if (item) {
      if (map) throw new Error(`yaml-lite：第 ${i + 1} 行把序列项混进了映射块`);
      seq = seq ?? [];
      const rest = item[2];
      if (!rest.trim()) {
        // `- ` 独占一行，值在下一行更深的缩进上
        const nextIndent = nextMeaningfulIndent(rows, i + 1);
        if (nextIndent === null || nextIndent <= baseIndent) { seq.push(null); i++; continue; }
        const sub = parseBlock(rows, i + 1, nextIndent);
        seq.push(sub.value);
        i = sub.next;
        continue;
      }
      if (KV_RE.test(rest)) {
        // `- key: value`：本项是个映射，其后续键与 `-` 后第一个字符同列。
        // 把 `-` 换成空格再按普通映射块解析——否则递归会重新撞上同一个 `-`。
        const sub = parseSeqItemMap(rows, i);
        seq.push(sub.value);
        i = sub.next;
        continue;
      }
      seq.push(scalar(rest));
      i++;
      continue;
    }

    const kv = line.match(KV_RE);
    if (!kv) throw new Error(`yaml-lite：第 ${i + 1} 行无法解析：${line.trim()}`);
    if (seq) throw new Error(`yaml-lite：第 ${i + 1} 行把映射键混进了序列块`);
    map = map ?? {};
    const key = kv[2].trim();
    const rest = kv[3];

    if (rest.trim()) {
      const arr = inlineSeq(rest);
      map[key] = arr === null ? scalar(rest) : arr;
      i++;
      continue;
    }
    // 值在后续更深缩进的行上（映射或序列）
    const nextIndent = nextMeaningfulIndent(rows, i + 1);
    if (nextIndent === null || nextIndent < baseIndent) { map[key] = null; i++; continue; }
    if (nextIndent === baseIndent && !isSeqAt(rows, i + 1)) { map[key] = null; i++; continue; }
    const sub = parseBlock(rows, i + 1, nextIndent);
    map[key] = sub.value;
    i = sub.next;
  }

  return { value: seq ?? map ?? {}, next: i };
}

/** `- key: v` 起头的映射项：从 `-` 之后的第一个字符列开始，作为该项映射的基准缩进。 */
function parseSeqItemMap(rows, start) {
  const line = rows[start];
  const ind = indentOf(line);
  const dashRest = line.slice(ind + 1).replace(/^\s*/, '');
  const itemIndent = line.length - dashRest.length;
  const patched = rows.slice();
  patched[start] = ' '.repeat(itemIndent) + dashRest;
  return parseBlock(patched, start, itemIndent);
}

function nextMeaningfulIndent(rows, from) {
  for (let i = from; i < rows.length; i++) {
    if (isBlank(rows[i])) continue;
    return indentOf(rows[i]);
  }
  return null;
}

function isSeqAt(rows, from) {
  for (let i = from; i < rows.length; i++) {
    if (isBlank(rows[i])) continue;
    return ITEM_RE.test(rows[i]);
  }
  return false;
}

/**
 * 解析 YAML 文本。
 * @throws 语法不可解析时抛错（**不返回空对象**——空集会让包含类判据恒真）
 */
export function parseYaml(text) {
  const rows = lines(text);
  const first = nextMeaningfulIndent(rows, 0);
  if (first === null) return {};
  const { value } = parseBlock(rows, 0, first);
  return value;
}
