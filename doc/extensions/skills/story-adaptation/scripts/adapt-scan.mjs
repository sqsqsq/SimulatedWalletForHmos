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
const PATCH_FILE = 'framework-patch.yaml';      // 包声明的 framework 依赖；没有这份文件就是不依赖

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

/**
 * 递归列文件（相对 base 的 posix 路径）；跳过本命令自己的工作目录。
 *
 * 工作目录带版本号并以点开头（`.adapt-<包 version>/`）：不同版本各自一份，
 * 升到新版不会把既有的方案与 before 快照覆盖掉；点开头是为了在目标工程里
 * 一眼看出它是临时件而不是交付内容。
 */
const isWork = (name) => name === 'adapt' || name.startsWith('.adapt-');
/**
 * 运行产物目录：跑过脚本就会有，既不入库也不交付。
 *
 * 不排除它，`__pycache__` 里的字节码会被 classOf 判成 `skills/story/**` 下的机制内容，
 * 跟着「整体复制」搬进目标工程，再因为两边字节码不同而永远核不平。
 */
const isRuntimeJunk = (name) => name === '__pycache__';
const walk = (dir, base = dir) => !existsSync(dir) ? [] :
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name);
    if (e.isDirectory()) {
      return isWork(rel(base, f)) || isRuntimeJunk(e.name) ? [] : walk(f, base);
    }
    return [rel(base, f)];
  });

/**
 * 对接层的地盘：`skills/story/scripts/`。
 *
 * 它不是「几个 .js 文件」，是**一块归目标所有的目录**——自定义对接 js 会带来
 * 依赖与锁文件（`package.json`、`node_modules/`、构建产物）。按路径长相分类时，
 * 这些统统落进「机制」，撞上「机制目录 == 包」而恒 FAIL，目标绕不过去。
 *
 * 所以这一层**按所有权判，不按路径长相判**：包里有的归包，包里没有的归目标。
 * 不写死依赖文件名——下一个依赖形态（`pnpm-lock.yaml`、`.venv/`、`dist/`）
 * 又得加一条，那是词表式补丁。
 */
const ADAPTER_DIR = 'skills/story/scripts/';

/** 类别（相对 extension_dir 的路径）——与 SKILL.md §2 表一一对应 */
const classOf = (p) =>
  /^skills\/story\/scripts\/[^/]+\.js$/.test(p) ? 'js'
  : p.startsWith(ADAPTER_DIR) && !PKG_FILES.has(p) ? 'custom'
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
/** 版本比较：按点分段数值比，缺段按 0。返回 -1 / 0 / 1。 */
const cmpVersion = (a, b) => {
  const pa = String(a ?? '').split('.').map((x) => parseInt(x, 10) || 0);
  const pb = String(b ?? '').split('.').map((x) => parseInt(x, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d) return d < 0 ? -1 : 1;
  }
  return 0;
};

// ── 前置 ────────────────────────────────────────────────────────────────────
if (!mode) die(`缺模式，用 ${MODES.join(' | ')}`);
const TARGET = opt('--target') && findRoot(opt('--target'));
if (!opt('--target')) die('缺 --target <目标根>');
if (!TARGET) die(`目标不是有效仓库根（找不到 framework.config.json）：${opt('--target')}`);
const PKG = opt('--package') ? findRoot(opt('--package')) : findRoot(dirname(fileURLToPath(import.meta.url)));
if (!PKG) die('定位不到包根');
const TDIR = join(TARGET, extDir(TARGET)), PDIR = join(PKG, extDir(PKG));
const PKG_VERSION = versionOf(existsSync(join(PDIR, 'manifest.yaml'))
  ? read(join(PDIR, 'manifest.yaml')) : '') || 'unknown';
const WORK = join(TDIR, `.adapt-${PKG_VERSION}`), BEFORE = join(WORK, 'before.json');
/** 包里有哪些文件 —— `classOf` 判对接层归属时要它。包自身的文件按定义都在其中。 */
const PKG_FILES = new Set(walk(PDIR));
const manifestOf = (d) => (existsSync(join(d, 'manifest.yaml')) ? read(join(d, 'manifest.yaml')) : '');

/**
 * 机制指纹：机制目录逐文件 sha 按路径排序后再做一次 sha。
 *
 * 判态不能只看版本号——机制改了、版本没动，按版本号判就是「重适配」，
 * 机制行一条不执行，目标拿到的还是旧脚本，而且不报错。指纹把这件事变成可见的停。
 */
function mechanismDigest(dir) {
  const files = walk(dir).filter((p) => classOf(p) === 'mech').sort();
  const h = createHash('sha256');
  for (const p of files) h.update(`${p}\n${sha(join(dir, p))}\n`);
  return h.digest('hex').slice(0, 16);
}

/**
 * 判态（SKILL §1 的数据面）。`package_not_bumped` = 版本相同而机制指纹不同：
 * 停下回包里升版，不擅自复制、不静默跳过。
 */
function adaptState(pkgVersion, tgtVersion, pkgDigest, tgtDigest) {
  if (!tgtVersion) return 'first';
  const c = cmpVersion(tgtVersion, pkgVersion);
  if (c < 0) return 'upgrade';
  if (c > 0) return 'target_newer';
  return pkgDigest === tgtDigest ? 'readapt' : 'package_not_bumped';
}

/** 目标 `.gitignore` 该有的两行：adapt 工作目录、章草稿目录——都是临时件。 */
function gitignoreLines(root) {
  let features = 'doc/features';
  try { features = JSON.parse(read(join(root, 'framework.config.json')))?.paths?.features_dir || features; } catch { /* 缺省 */ }
  return [`${extDir(root)}/.adapt-*/`, `${features}/**/AR/story-src/drafts/`];
}
function gitignoreStatus(root) {
  const f = join(root, '.gitignore');
  const have = existsSync(f) ? read(f).split(/\r?\n/).map((l) => l.trim()) : [];
  return gitignoreLines(root).map((line) => ({ line, present: have.includes(line) }));
}

/**
 * 包声明的 framework 补丁。**没有这份文件 = 不依赖任何 framework 改动**，不是错误。
 *
 * 解析只认三个键 + host：整份是给人读的声明，不做通用 YAML 解析——
 * 装一个解析器进来，下一次就会有人往里加结构。
 */
function frameworkPatches(dir) {
  const raw = existsSync(join(dir, PATCH_FILE)) ? read(join(dir, PATCH_FILE)) : '';
  const out = [];
  let cur = null;
  for (const line of raw.split(/\r?\n/)) {
    const item = line.match(/^\s*-\s+path:\s*(\S+)/);
    if (item) { cur = { path: item[1], kind: null, host: null, why: '' }; out.push(cur); continue; }
    if (!cur) continue;
    const kv = line.match(/^\s+(kind|host|why):\s*(.+)$/);
    if (kv) cur[kv[1]] = kv[2].trim();
  }
  return out;
}

/** 目标工程物化了哪些 adapter —— host_capability 带不带看它，不看包里写死的名单。 */
function targetAdapters(root) {
  const cfg = existsSync(join(root, 'framework.config.json'))
    ? JSON.parse(read(join(root, 'framework.config.json'))) : {};
  const list = cfg?.materialized_adapters ?? [];
  return new Set(Array.isArray(list) ? list.map(String) : []);
}

/** 目标 framework.config.json 的漂移白名单里已登记的路径。 */
function targetAllowlist(root) {
  const cfg = existsSync(join(root, 'framework.config.json'))
    ? JSON.parse(read(join(root, 'framework.config.json'))) : {};
  const list = cfg?.integrity?.drift_allowlist ?? [];
  return new Set((Array.isArray(list) ? list : []).map((e) => String(e?.path ?? '')));
}

/**
 * 每条补丁的去向：带，还是不带、为什么。
 *
 * `extension_dependency` 无条件带——扩展缺了它就是残的。
 * `host_capability` 只在目标用同一宿主时带：同一份声明在不同目标上给出不同结果，
 * 而规则只有一条。`kind` 认不出的**当场报错**，不静默跳过：漏带一份地基，
 * 目标那边的表现是「某个能力莫名其妙不生效」，最难查。
 */
function patchPlan(patches, adapters) {
  return patches.map((x) => {
    if (x.kind === 'extension_dependency') return { ...x, carry: true, reason: '扩展依赖' };
    if (x.kind === 'host_capability') {
      const on = adapters.has(String(x.host));
      return { ...x, carry: on, reason: on ? `目标用 ${x.host}` : `目标未物化 ${x.host}` };
    }
    die(`${PATCH_FILE} 里 ${x.path} 的 kind 认不出：${x.kind ?? '(缺)'}`);
    return null;
  });
}

// ── --scan ──────────────────────────────────────────────────────────────────
if (mode === '--scan') {
  const tf = walk(TDIR), pf = walk(PDIR), pSet = new Set(pf);
  const pick = (files, dir, k) => files.filter((p) => classOf(p) === k).map((p) => ({ p, f: join(dir, p) }));
  const tMech = pick(tf, TDIR, 'mech'), pMech = pick(pf, PDIR, 'mech'), tMechSet = new Set(tMech.map((x) => x.p));
  const pkgDigest = mechanismDigest(PDIR), tgtDigest = existsSync(TDIR) ? mechanismDigest(TDIR) : null;
  const pkgVersion = versionOf(manifestOf(PDIR)), tgtVersion = versionOf(manifestOf(TDIR));
  const state = adaptState(pkgVersion, tgtVersion, pkgDigest, tgtDigest);
  const out = {
    generated_at: new Date().toISOString(),
    package_root: PKG, target_root: TARGET,
    package_version: pkgVersion, target_version: tgtVersion,
    state,
    mechanism_digest: { package: pkgDigest, target: tgtDigest },
    gitignore: gitignoreStatus(TARGET),
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
    framework_patch: patchPlan(frameworkPatches(PDIR), targetAdapters(TARGET)).map((x) => ({
      path: x.path, kind: x.kind, host: x.host, why: x.why, carry: x.carry, reason: x.reason,
      in_target: existsSync(join(TARGET, 'framework', x.path)),
      same_as_package: existsSync(join(TARGET, 'framework', x.path))
        && existsSync(join(PKG, 'framework', x.path))
        && sha(join(TARGET, 'framework', x.path)) === sha(join(PKG, 'framework', x.path)),
      allowlisted: targetAllowlist(TARGET).has(x.path),
    })),
    target_adapters: [...targetAdapters(TARGET)],
    root_files: ROOT_FILES.map((p) => ({ path: p, in_target: existsSync(join(TARGET, p)),
      same_as_package: existsSync(join(TARGET, p)) && existsSync(join(PKG, p)) && sha(join(TARGET, p)) === sha(join(PKG, p)) })),
  };
  mkdirSync(WORK, { recursive: true });
  writeFileSync(BEFORE, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  console.error(`[adapt-scan] 清单已写入 ${BEFORE}——判断按 SKILL.md §2 表逐文件做`);
  if (state === 'package_not_bumped') {
    console.error(`[adapt-scan] 停：包与目标版本都是 ${pkgVersion}，机制指纹却不同（${pkgDigest} ≠ ${tgtDigest}）`
      + '——包改了机制没升版。回包里升 manifest.version，再来');
  }
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
//
// **守恒对象 = 目标已有的每一个知识文件**，不分事实 / 规约 / 模式。把「包里有
// 同名的规约与模式」整类排除在守恒之外，理由是它们随包直接维护、换版本是预期——
// 那条排除正是「升级把目标写好的知识整份盖掉而校验一声不吭」的成因：谁都没在核它。
// 的那些」排除在外时，整份换成包版本也不会报 `知识内容丢失`。
//
// 现在包内知识文件只有两个用途：新装时作初始样板、升级时作**变更提案**（由执行模型
// 语义合并、人确认后写入）。目标已有的内容在任何路径与目录结构下都不被静默覆盖。
// 索引 README 不在此列（classOf 判为 bridge / mech，按 SKILL §2 索引行合成）。
for (const k of before.knowledge) {
  if (k.confirmed === '未确认') continue;            // 样板被填写不在守恒对象内
  const base = k.path.split('/').pop();
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

// ⑤ 入口文件含扩展段（带标记区）
//
// 「实例扩展」节**不止 adapt 一个写者**——framework 的 render-agents-md 也往这一节
// 生成 Skill 表格。按整节替换会把宿主刚生成的表格连同别的内容一起盖掉。
// 标记区划清写者边界：adapt 只重写标记之间，标记之外一律不碰。
//
// 目标里已有**无标记旧段**时单独报：那是首次迁移，做法是原位包上标记，
// 不是再追加一段——两条报错文案不同，因为修法不同。
const SECTION = 'skills/story/AGENTS.section.md', ws = (s) => s.replace(/\s+/g, ' ').trim();
const EXT_BEGIN = '<!-- story-ext:begin -->', EXT_END = '<!-- story-ext:end -->';
if (existsSync(join(PDIR, SECTION))) {
  const raw = read(join(PDIR, SECTION));
  const body = ws(raw);
  // 剥掉标记行之后的正文，用来认出「内容在、标记没包上」的旧段
  const bare = ws(raw.split(/\r?\n/).filter((l) => !l.trim().startsWith('<!-- story-ext:')).join('\n'));
  for (const entry of ['AGENTS.md', 'CLAUDE.md']) {
    const f = join(TARGET, entry);
    if (!existsSync(f)) { if (entry === 'AGENTS.md') bad.push(`⑤ 入口文件缺失：${entry}`); continue; }
    const got = ws(read(f));
    if (got.includes(body)) continue;
    if (bare && got.includes(bare)) {
      bad.push(`⑤ 入口文件的扩展段没有标记区：${entry}`
        + `（首次迁移：把既有那一段**原位**用 ${EXT_BEGIN} / ${EXT_END} 包起来，不要另追加一段）`);
    } else {
      bad.push(`⑤ 入口文件未含扩展段：${entry}（把包内扩展段连同标记区写进它的「实例扩展」节末尾）`);
    }
  }
}

// ⓪ 判态：扫描时该停的这里再拦一次——扫描只报，不写盘
if (before.state === 'package_not_bumped') {
  bad.push('⓪ 包未升版：包与目标版本相同而机制指纹不同——回包里升 manifest.version，再重新 --scan');
}

// ⑥ framework 补丁：该带的带了、带了的登记进目标 drift_allowlist
//
// 只登记不复制 = 目标缺地基；只复制不登记 = 目标第一次跑 harness 就红在完整性上。
// 两件事都核。不带的那些反过来核：它们**不该**出现在目标的 allowlist 里。
{
  const allow = targetAllowlist(TARGET);
  for (const x of patchPlan(frameworkPatches(PDIR), targetAdapters(TARGET))) {
    const at = join(TARGET, 'framework', x.path);
    if (!x.carry) {
      if (allow.has(x.path)) bad.push(`⑥ 不该带的补丁登记进了 allowlist：${x.path}（${x.reason}）`);
      continue;
    }
    if (!existsSync(at)) { bad.push(`⑥ framework 补丁缺文件：${x.path}——${x.why}`); continue; }
    if (sha(at) !== sha(join(PKG, 'framework', x.path))) bad.push(`⑥ framework 补丁内容不同于包：${x.path}`);
    if (!allow.has(x.path)) {
      bad.push(`⑥ 补丁没登记进 drift_allowlist：${x.path}`
        + '——目标的 framework 完整性校验会把它判成漂移，第一次跑 harness 就红');
    }
  }
}

// ⑦ 目标 .gitignore 有那两行：adapt 工作目录与章草稿目录都是临时件，不加就会被提交进目标的库
for (const g of gitignoreStatus(TARGET)) {
  if (!g.present) bad.push(`⑦ 目标 .gitignore 缺一行：${g.line}`);
}

if (bad.length) { console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`); bad.forEach((b) => console.error(`  ${b}`)); process.exit(1); }
console.log('[adapt-scan] 核对通过：版本相符 / 机制 == 包 / 知识内容仍在 / 清单无未确认且路径齐 / 自定义未动 / 入口文件含扩展段（包有时）/ framework 补丁齐且已登记 / .gitignore 两行在');
