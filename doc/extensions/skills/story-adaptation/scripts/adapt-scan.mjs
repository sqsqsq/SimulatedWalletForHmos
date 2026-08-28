#!/usr/bin/env node
/**
 * story adapt 辅助脚本——只做模型不可靠的机械活：列两棵树、核对。
 * 归属与处置判断在 SKILL.md §2，由执行适配的 AI 做；本脚本不替它判。
 *
 * 用法: node adapt-scan.mjs --scan|--check --target <目标根> [--package <包根>]
 * 退出: 0 通过 / 1 核对不符 / 2 参数或前置错误
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { join, relative, dirname, sep, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const MODES = ['--scan', '--check'];
const ROOT_FILES = ['.cac/commands/story.md', '.claude/commands/story.md',
  '.codex/skills/story/SKILL.md', '.opencode/skill/story/SKILL.md', 'framework.config.json'];
const MOCK_MARKERS = ['本地替身', '模拟实现'];   // 包内对接脚本的自述；不认任何仓的具体标识符

const argv = process.argv.slice(2);
const mode = MODES.find((m) => argv.includes(m));
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
const die = (msg, code = 2) => { console.error(`[adapt-scan] ${msg}`); process.exit(code); };

/** 从起点向上找含 framework.config.json 的仓库根 */
const findRoot = (from) => {
  for (let d = resolve(from); ; d = dirname(d)) {
    if (existsSync(join(d, 'framework.config.json'))) return d;
    if (d === dirname(d)) return null;
  }
};
const extDir = (root) => {
  try { return JSON.parse(readFileSync(join(root, 'framework.config.json'), 'utf8'))?.paths?.extension_dir || 'doc/extensions'; }
  catch { return 'doc/extensions'; }
};
const rel = (base, f) => relative(base, f).split(sep).join('/');
const sha = (f) => createHash('sha256').update(readFileSync(f)).digest('hex').slice(0, 16);
const read = (f) => readFileSync(f, 'utf8');

/** 递归列文件（相对 base 的 posix 路径）；跳过本脚本的工作目录 adapt/ */
const walk = (dir, base = dir) => !existsSync(dir) ? [] :
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name);
    if (e.isDirectory()) return rel(base, f) === 'adapt' ? [] : walk(f, base);
    return [rel(base, f)];
  });

/** 类别（相对 extension_dir 的路径）——与 SKILL.md §2 表一一对应 */
const classOf = (p) =>
  /^skills\/story\/scripts\/[^/]+\.js$/.test(p) ? 'js'
  : p === 'manifest.yaml' || /^knowledge\/[^/]+\/README\.md$/.test(p) ? 'bridge'
  : p === 'knowledge/README.md' || p === 'AGENTS.section.md' || /^(hooks|rules)\//.test(p) || /^skills\/(story|story-adaptation)\//.test(p) ? 'mech'
  : /^knowledge\//.test(p) ? 'know'
  : 'custom';

const frontmatter = (txt) => {
  const m = txt.match(/^---\r?\n([\s\S]*?)\r?\n---/); const o = {};
  if (m) for (const l of m[1].split(/\r?\n/)) { const i = l.indexOf(':'); if (i > 0) o[l.slice(0, i).trim()] = l.slice(i + 1).trim(); }
  return o;
};

/** 事实序列：正文里非空的表格单元格与段落行，按出现顺序 */
const factSeq = (txt) => {
  const out = [];
  for (const line of txt.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '').split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    if (t.startsWith('|')) { if (/^\|[\s|:-]+\|$/.test(t)) continue; out.push(...t.split('|').map((c) => c.trim()).filter(Boolean)); }
    else out.push(t);
  }
  return out;
};

/** manifest 的知识清单：只读 knowledge: 段下的 `- ` 行，不做 YAML 解析 */
const knowledgeList = (txt) => {
  const out = []; let indent = -1;
  for (const l of txt.split(/\r?\n/)) {
    const head = l.match(/^(\s*)knowledge:\s*$/);
    if (head) { indent = head[1].length; continue; }
    if (indent < 0) continue;
    const item = l.match(/^(\s*)-\s+(.+?)\s*$/);
    if (item && item[1].length > indent) out.push(item[2]);
    else if (l.trim() && !l.trim().startsWith('#')) break;
  }
  return out;
};
const versionOf = (txt) => (txt.match(/^version:\s*"?([^"\s]+)"?/m) || [])[1] || null;

// ── 前置 ────────────────────────────────────────────────────────────────────
if (!mode) die(`缺模式，用 ${MODES.join(' | ')}`);
const TARGET = opt('--target') && findRoot(opt('--target'));
if (!opt('--target')) die('缺 --target <目标根>');
if (!TARGET) die(`目标不是有效仓库根（找不到 framework.config.json）：${opt('--target')}`);
const PKG = opt('--package') ? findRoot(opt('--package')) : findRoot(dirname(fileURLToPath(import.meta.url)));
if (!PKG) die('定位不到包根');
const TDIR = join(TARGET, extDir(TARGET)), PDIR = join(PKG, extDir(PKG));
const WORK = join(TDIR, 'adapt'), BEFORE = join(WORK, 'before.json');
const manifestOf = (d) => (existsSync(join(d, 'manifest.yaml')) ? read(join(d, 'manifest.yaml')) : '');

// ── --scan ──────────────────────────────────────────────────────────────────
if (mode === '--scan') {
  const tf = walk(TDIR), pf = walk(PDIR), pSet = new Set(pf);
  const pick = (files, dir, k) => files.filter((p) => classOf(p) === k).map((p) => ({ p, f: join(dir, p) }));
  const tMech = pick(tf, TDIR, 'mech'), pMech = pick(pf, PDIR, 'mech'), tMechSet = new Set(tMech.map((x) => x.p));
  const out = {
    generated_at: new Date().toISOString(),
    package_root: PKG, target_root: TARGET,
    package_version: versionOf(manifestOf(PDIR)), target_version: versionOf(manifestOf(TDIR)),
    mechanism: {
      target_only: tMech.filter((x) => !pSet.has(x.p)).map((x) => x.p),
      package_only: pMech.filter((x) => !tMechSet.has(x.p)).map((x) => x.p),
      differ: pMech.filter((x) => tMechSet.has(x.p) && sha(x.f) !== sha(join(TDIR, x.p))).map((x) => x.p),
    },
    knowledge: pick(tf, TDIR, 'know').map(({ p, f }) => {
      const txt = read(f), fm = frontmatter(txt);
      return { path: p, dir: dirname(p), kind: fm.kind ?? null, confirmed: fm.confirmed ?? null, facts: factSeq(txt) };
    }),
    package_knowledge: pf.filter((p) => classOf(p) === 'know'),
    manifest_knowledge: knowledgeList(manifestOf(TDIR)),
    js: {
      package_self_declared_mock: pick(pf, PDIR, 'js').some(({ f }) => MOCK_MARKERS.some((m) => read(f).includes(m))),
      package: pick(pf, PDIR, 'js').map((x) => x.p), target: pick(tf, TDIR, 'js').map((x) => x.p),
    },
    custom: pick(tf, TDIR, 'custom').map(({ p, f }) => ({ path: p, sha: sha(f) })),
    root_files: ROOT_FILES.map((p) => ({ path: p, in_target: existsSync(join(TARGET, p)),
      same_as_package: existsSync(join(TARGET, p)) && existsSync(join(PKG, p)) && sha(join(TARGET, p)) === sha(join(PKG, p)) })),
  };
  mkdirSync(WORK, { recursive: true });
  writeFileSync(BEFORE, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  console.error(`[adapt-scan] 清单已写入 ${BEFORE}——判断按 SKILL.md §2 表逐文件做`);
  process.exit(0);
}

// ── --check ─────────────────────────────────────────────────────────────────
if (!existsSync(BEFORE)) die(`缺 ${BEFORE}，先跑 --scan`);
const before = JSON.parse(read(BEFORE));
const tf = walk(TDIR), bad = [];
const now = (k) => tf.filter((p) => classOf(p) === k);

// ① 机制目录文件集与内容 == 包
const pMech = walk(PDIR).filter((p) => classOf(p) === 'mech'), tMech = new Set(now('mech'));
for (const p of pMech) {
  if (!tMech.has(p)) bad.push(`① 机制缺文件：${p}`);
  else if (sha(join(PDIR, p)) !== sha(join(TDIR, p))) bad.push(`① 机制内容不同于包：${p}`);
}
for (const p of tMech) if (!pMech.includes(p)) bad.push(`① 机制多出旧文件：${p}`);
for (const p of ROOT_FILES.slice(0, 4)) {
  if (!existsSync(join(TARGET, p))) bad.push(`① 跳板缺失：${p}`);
  else if (existsSync(join(PKG, p)) && sha(join(TARGET, p)) !== sha(join(PKG, p))) bad.push(`① 跳板不同于包：${p}`);
}

// ② 目标所有的知识文件：旧事实序列仍按序在新文件（允许新增列/行/键）
//    守恒对象 = 事实文件 + 目标自加的文件；包里有同名的规约/模式在升级时本就换成包的版本，不核
const pkgNames = new Set((before.package_knowledge || []).map((p) => p.split('/').pop()));
for (const k of before.knowledge) {
  if (k.confirmed === '未确认') continue;            // 样板被填写不在守恒对象内
  const base = k.path.split('/').pop();
  if (k.kind !== 'facts' && pkgNames.has(base)) continue;   // 随包直接维护，换版本是预期
  const f = tf.find((p) => p.endsWith(`/${base}`) && classOf(p) === 'know');
  if (!f) { bad.push(`② 知识文件消失：${k.path}`); continue; }
  const seq = factSeq(read(join(TDIR, f)));
  let i = 0;
  for (const fact of k.facts) { const at = seq.indexOf(fact, i); if (at < 0) { bad.push(`② 知识内容丢失：${f} 缺「${fact.slice(0, 40)}」`); break; } i = at + 1; }
}

// ③ 清单里没有未确认的文件，且每条路径都在
for (const p of knowledgeList(manifestOf(TDIR))) {
  if (!existsSync(join(TDIR, p))) { bad.push(`③ 清单路径不存在：${p}`); continue; }
  if (frontmatter(read(join(TDIR, p))).confirmed === '未确认') bad.push(`③ 未确认的文件进了清单：${p}`);
}

// ④ 自定义文件没动过
const nowCustom = new Map(now('custom').map((p) => [p, sha(join(TDIR, p))]));
for (const c of before.custom) {
  if (!nowCustom.has(c.path)) bad.push(`④ 自定义文件被删：${c.path}`);
  else if (nowCustom.get(c.path) !== c.sha) bad.push(`④ 自定义文件被改：${c.path}`);
}

// ⑤ 入口文件含扩展段：包有 AGENTS.section.md 时，目标 AGENTS.md（及存在的 CLAUDE.md）须含其正文；包没有则跳过
const SECTION = 'AGENTS.section.md', ws = (s) => s.replace(/\s+/g, ' ').trim();
if (existsSync(join(PDIR, SECTION))) {
  const body = ws(read(join(PDIR, SECTION)));
  for (const entry of ['AGENTS.md', 'CLAUDE.md']) {
    const f = join(TARGET, entry);
    if (!existsSync(f)) { if (entry === 'AGENTS.md') bad.push(`⑤ 入口文件缺失：${entry}`); continue; }
    if (!ws(read(f)).includes(body)) bad.push(`⑤ 入口文件未含扩展段：${entry}（写入后须重渲染入口文件）`);
  }
}

if (bad.length) { console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`); bad.forEach((b) => console.error(`  ${b}`)); process.exit(1); }
console.log('[adapt-scan] 核对通过：机制 == 包 / 知识内容仍在 / 清单无未确认且路径齐 / 自定义未动 / 入口文件含扩展段（包有时）');
