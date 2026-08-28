#!/usr/bin/env node
/**
 * story adapt 辅助脚本——只做模型不可靠的机械活：列两棵树、备份、回滚、核对。
 * 归属与处置判断在 SKILL.md §2，由执行适配的 AI 做；本脚本不替它判。
 *
 * 用法: node adapt-scan.mjs --scan|--backup|--restore|--check --target <目标根> [--package <包根>]
 * 退出: 0 通过 / 1 核对不符 / 2 参数或前置错误
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync, cpSync, readdirSync } from 'node:fs';
import { join, relative, dirname, sep, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const MODES = ['--scan', '--backup', '--restore', '--check'];
const ROOT_FILES = ['.cac/commands/story.md', '.claude/commands/story.md',
  '.codex/skills/story/SKILL.md', '.opencode/skill/story/SKILL.md', 'framework.config.json'];
const MOCK_MARKERS = ['本地替身', '模拟实现', 'MOCK_DATA_DIR'];

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
/** 逐文件复制：cpSync 拒绝复制到自身子目录，而备份就在 extension_dir 内 */
const copyFiles = (files, from, to) => { for (const p of files) { mkdirSync(dirname(join(to, p)), { recursive: true }); cpSync(join(from, p), join(to, p)); } };
const sha = (f) => createHash('sha256').update(readFileSync(f)).digest('hex').slice(0, 16);
const read = (f) => readFileSync(f, 'utf8');

/** 递归列文件（相对 base 的 posix 路径）；默认跳过本脚本的工作目录 adapt/ */
const walk = (dir, base = dir, skipWork = true) => !existsSync(dir) ? [] :
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name);
    if (e.isDirectory()) return skipWork && rel(base, f) === 'adapt' ? [] : walk(f, base, skipWork);
    return [rel(base, f)];
  });

/** 类别（相对 extension_dir 的路径）——与 SKILL.md §2 表一一对应 */
const classOf = (p) =>
  /^skills\/story\/scripts\/[^/]+\.js$/.test(p) ? 'js'
  : p === 'manifest.yaml' || /^knowledge\/[^/]+\/README\.md$/.test(p) ? 'bridge'
  : p === 'knowledge/README.md' || /^(hooks|rules)\//.test(p) || /^skills\/(story|story-adaptation)\//.test(p) ? 'mech'
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
const WORK = join(TDIR, 'adapt'), BEFORE = join(WORK, 'before.json'), BACKUP = join(WORK, 'backup');
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

// ── --backup ────────────────────────────────────────────────────────────────
if (mode === '--backup') {
  rmSync(BACKUP, { recursive: true, force: true });
  mkdirSync(join(BACKUP, 'root'), { recursive: true });
  if (existsSync(TDIR)) copyFiles(walk(TDIR), TDIR, join(BACKUP, 'ext'));   // walk 已跳过 adapt/
  for (const p of ROOT_FILES) if (existsSync(join(TARGET, p))) {
    mkdirSync(dirname(join(BACKUP, 'root', p)), { recursive: true });
    cpSync(join(TARGET, p), join(BACKUP, 'root', p));
  }
  writeFileSync(join(BACKUP, 'manifest.json'), JSON.stringify({ at: new Date().toISOString(), ext_existed: existsSync(TDIR) }, null, 2));
  console.log(`[adapt-scan] 已备份到 ${BACKUP}`);
  process.exit(0);
}

// ── --restore ───────────────────────────────────────────────────────────────
// 顺序写死：先仓库根文件，再 extension_dir。备份自身在 extension_dir 内，
// 反过来先删目录，就把根文件的备份一起删了，跳板与配置再也回不来。
if (mode === '--restore') {
  if (!existsSync(BACKUP)) die(`没有备份可回滚：${BACKUP}`);
  const meta = JSON.parse(read(join(BACKUP, 'manifest.json')));
  // 根文件是逐个恢复的（不像 extension_dir 那样整体替换），所以本次写入**新增**的
  // 那些——备份里没有、目标上却有——必须显式删掉，否则回滚后树会多出几个文件。
  for (const p of ROOT_FILES) {
    const b = join(BACKUP, 'root', p);
    if (existsSync(b)) { mkdirSync(dirname(join(TARGET, p)), { recursive: true }); cpSync(b, join(TARGET, p)); }
    else if (existsSync(join(TARGET, p))) {
      rmSync(join(TARGET, p), { force: true });
      // 连它留下的空目录一起收掉，否则回滚后目标会多出几个空壳目录
      for (let d = dirname(join(TARGET, p)); d.startsWith(TARGET) && d !== TARGET; d = dirname(d)) {
        try { if (readdirSync(d).length) break; rmSync(d, { recursive: true }); } catch { break; }
      }
    }
  }
  // 暂存到 extension_dir 之外：备份在它里面，不先搬走就会被下一步的删除带走
  const staged = join(TDIR, '..', `.adapt-restore-${process.pid}`);
  rmSync(staged, { recursive: true, force: true });
  if (existsSync(join(BACKUP, 'ext'))) copyFiles(walk(join(BACKUP, 'ext')), join(BACKUP, 'ext'), staged);
  // 工作记录（方案与用户确认记录）跟着回滚保留，只有已用掉的备份不留
  for (const n of (existsSync(WORK) ? readdirSync(WORK) : []).filter((n) => n !== 'backup'))
    cpSync(join(WORK, n), join(staged, 'adapt', n), { recursive: true });
  rmSync(TDIR, { recursive: true, force: true });
  if (meta.ext_existed) copyFiles(walk(staged, staged, false), staged, TDIR);
  rmSync(staged, { recursive: true, force: true });
  console.log(`[adapt-scan] 已回滚${meta.ext_existed ? '' : '（首次安装：扩展目录整体移除）'}`);
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
for (const k of before.knowledge) {
  if (k.confirmed === '未确认') continue;            // 样板被填写不在守恒对象内
  const f = tf.find((p) => p.endsWith(`/${k.path.split('/').pop()}`) && classOf(p) === 'know');
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

if (bad.length) { console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`); bad.forEach((b) => console.error(`  ${b}`)); process.exit(1); }
console.log('[adapt-scan] 四项核对通过：机制 == 包 / 知识内容仍在 / 清单无未确认且路径齐 / 自定义未动');
