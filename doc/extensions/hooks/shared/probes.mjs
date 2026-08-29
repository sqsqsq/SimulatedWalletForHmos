/**
 * 探针执行 —— 机器只判它判得了、且**对已知违规有区分力**的事。
 *
 * 基线的 coding 探针是 `\b名\b` 跨文件文本存在性：不分声明/调用/注释，
 * 末段是容器名时恒真。实测一条明晃晃的违规（方向性布局参数写成 left/right）被它照常放行，
 * 因为它查的是「组件名在不在」，而组件名当然在。
 *
 * 这里执行的是**规约自带的探针表达式**（规约表的「探针」列，随知识走）：
 * 本文件不含任何规则编号、域前缀或来自规约的正则字面——换一套知识，这里一个字都不用改。
 *
 * 四形态封闭。多一种就是给机制层开了个能塞业务规则的口子。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * 把注释内容抹成空格，**保留行数与列位**（报行号要用）。
 *
 * 不剥注释的探针会把「注释里提了一句这个名字」当成真的引用或真的违规——
 * 那正是基线 `\b名\b` 探针「不分声明/调用/注释」的病。实测：一个角色类零调用，
 * 只因另一个文件的注释里写着「这里本该组装 NodeTable」，引用可达性就判过了。
 *
 * 只处理 `//` 与 `/* *\/`。字符串字面量里的 `//`（如 URL）会被误当注释起点，
 * 代价是那半行不参与匹配——宁可漏判也不误判，探针的价值在于报出来的都算数。
 */
function blankComments(text) {
  let out = '';
  let i = 0;
  let mode = 'code';                                  // code | line | block | sq | dq | tpl
  while (i < text.length) {
    const c = text[i];
    const n = text[i + 1];
    if (mode === 'code') {
      if (c === '/' && n === '/') { mode = 'line'; out += '  '; i += 2; continue; }
      if (c === '/' && n === '*') { mode = 'block'; out += '  '; i += 2; continue; }
      if (c === "'") mode = 'sq';
      else if (c === '"') mode = 'dq';
      else if (c === '`') mode = 'tpl';
      out += c; i++; continue;
    }
    if (mode === 'line') {
      if (c === '\n') { mode = 'code'; out += c; } else out += ' ';
      i++; continue;
    }
    if (mode === 'block') {
      if (c === '*' && n === '/') { mode = 'code'; out += '  '; i += 2; continue; }
      out += c === '\n' ? c : ' ';
      i++; continue;
    }
    // 字符串内：原样保留，遇到闭合符回 code（不处理转义，够用即可）
    if ((mode === 'sq' && c === "'") || (mode === 'dq' && c === '"') || (mode === 'tpl' && c === '`')) {
      mode = 'code';
    }
    out += c; i++;
  }
  return out;
}

/**
 * 读一个文件并抹掉注释；读不到返回 null（调用方按「没这个文件」处理，不当作通过）。
 */
function readOrNull(abs) {
  try {
    return blankComments(fs.readFileSync(abs, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * 实体名 → 承载它的实现文件。
 *
 * 先按文件名匹配（实体 `FooSheet` → `.../FooSheet.ets`）；匹配不到就退回
 * 契约点名的全部文件，并让调用方知道这次是**放宽了范围**——放宽会稀释区分力，
 * 静默放宽等于把恒真探针换了个写法。
 */
export function filesForEntity(files, entityName) {
  const name = String(entityName ?? '').trim();
  if (!name) return { files, narrowed: false };
  const hit = files.filter(rel => path.basename(rel).replace(/\.[^.]+$/, '') === name);
  if (hit.length) return { files: hit, narrowed: true };
  const loose = files.filter(rel => path.basename(rel).includes(name));
  if (loose.length) return { files: loose, narrowed: true };
  return { files, narrowed: false };
}

/**
 * 取一个方法的函数体（大括号配对）。
 *
 * 找不到方法定义时返回 null——调用方据此报「方法在契约里，代码里没有」，
 * 而不是拿整个文件当方法体去搜（那会让 `present_in_method` 退化成 `present_in_file`）。
 */
function methodBody(text, methodName) {
  const name = String(methodName ?? '').trim();
  if (!name) return null;
  const re = new RegExp(`(^|[^\\w.])${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*(<[^>]*>)?\\s*\\(`, 'm');
  const m = re.exec(text);
  if (!m) return null;
  const open = text.indexOf('{', m.index + m[0].length - 1);
  if (open < 0) return null;
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    if (text[i] === '{') depth++;
    else if (text[i] === '}') {
      depth--;
      if (depth === 0) return text.slice(open + 1, i);
    }
  }
  return text.slice(open + 1);
}

/**
 * 执行一条探针。
 *
 * @param {{kind: string, pattern: string, count: number|null, raw: string}} probe
 * @param {{projectRoot: string, files: string[], entityName: string, entityKind: string}} target
 * @returns {{ok: boolean, detail: string, scanned: number}}
 *   `scanned` 是实际读到的文件数。**0 命中要出声**（KB-11）：探针写错了与代码没问题，
 *   在结果上完全同形——这正是基线恒真探针的翻版。
 */
export function runProbe(probe, target) {
  const { projectRoot, files, entityName, entityKind } = target;
  const scope = filesForEntity(files, entityName);
  const abs = scope.files.map(rel => ({ rel, abs: path.resolve(projectRoot, rel) }));
  const readable = abs.map(f => ({ ...f, text: readOrNull(f.abs) })).filter(f => f.text !== null);
  if (!readable.length) {
    return { ok: false, detail: `没有可读的实现文件（契约点名 ${scope.files.length} 个）`, scanned: 0 };
  }
  const widened = scope.narrowed ? '' : '（未能定位到该实体自己的文件，已放宽到契约点名的全部文件）';

  let re;
  if (probe.pattern) {
    try {
      re = new RegExp(probe.pattern, 'g');
    } catch (e) {
      return { ok: false, detail: `探针表达式不是合法正则：${probe.raw}（${e.message}）`, scanned: 0 };
    }
  }

  switch (probe.kind) {
    case 'absent_regex': {
      const hits = [];
      for (const f of readable) {
        f.text.split(/\r?\n/).forEach((line, i) => {
          re.lastIndex = 0;
          if (re.test(line)) hits.push(`${f.rel}:${i + 1} ${line.trim().slice(0, 70)}`);
        });
      }
      return hits.length
        ? { ok: false, detail: `不该出现的形态命中 ${hits.length} 处：${hits.slice(0, 3).join('；')}`, scanned: readable.length }
        : { ok: true, detail: `扫描 ${readable.length} 个文件，未出现${widened}`, scanned: readable.length };
    }
    case 'present_in_method': {
      if (entityKind !== 'interfaces') {
        return { ok: false, detail: `present_in_method 只能用在方法上，当前实体是 ${entityKind}`, scanned: 0 };
      }
      const method = String(entityName ?? '').split('.').pop();
      for (const f of readable) {
        const body = methodBody(f.text, method);
        if (body === null) continue;
        re.lastIndex = 0;
        if (re.test(body)) {
          return { ok: true, detail: `${f.rel} 的 ${method}() 里命中`, scanned: readable.length };
        }
        return { ok: false, detail: `${f.rel} 的 ${method}() 方法体里没有要求的形态`, scanned: readable.length };
      }
      return { ok: false, detail: `在 ${readable.length} 个文件里都找不到方法 ${method}()`, scanned: readable.length };
    }
    case 'referenced_outside_definition': {
      const target0 = String(entityName ?? '').split('.').pop();
      if (!target0) return { ok: false, detail: '没有可检索的实体名', scanned: 0 };
      const word = new RegExp(`\\b${target0.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
      const defFiles = new Set(scope.narrowed ? scope.files : []);
      const outside = [];
      for (const rel of files) {
        if (defFiles.has(rel)) continue;
        const text = readOrNull(path.resolve(projectRoot, rel));
        if (text === null) continue;
        if (word.test(text)) outside.push(rel);
      }
      return outside.length
        ? { ok: true, detail: `在定义文件之外被引用：${outside.slice(0, 3).join('、')}`, scanned: files.length }
        : { ok: false, detail: `只在自己的定义文件里出现，没有任何地方调用它`, scanned: files.length };
    }
    case 'count_eq': {
      let n = 0;
      for (const f of readable) {
        re.lastIndex = 0;
        n += (f.text.match(re) ?? []).length;
      }
      return n === probe.count
        ? { ok: true, detail: `命中 ${n} 次，符合恒等要求`, scanned: readable.length }
        : { ok: false, detail: `命中 ${n} 次，要求恒等于 ${probe.count}`, scanned: readable.length };
    }
    default:
      return { ok: false, detail: `未知探针形态：${probe.kind}`, scanned: 0 };
  }
}
