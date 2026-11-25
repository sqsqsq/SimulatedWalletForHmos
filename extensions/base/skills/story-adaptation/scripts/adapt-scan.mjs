#!/usr/bin/env node
/**
 * story adapt —— 在已解包 `<ext>/base/` 的业务工程内就地安装、升级、校验、清理样例与记版本。
 *
 * 所有权由目录表达：
 *   `<ext>/base/`              通用机制包（整目录替换；含 `package-manifest.yaml`、`.gitignore` 与首装临时 `examples/knowledge/`）
 *   `<ext>/adapters/`          业务侧对接实现，固定入口 `story.js`、`token.js`（脚本不覆盖）
 *   `<ext>/knowledge/`         业务侧知识（脚本不读不写；适配由模型按方法页从项目实际证据写）
 *   `<ext>/manifest.yaml`      运行时唯一清单：机制登记由 `base/package-manifest.yaml` 合并，`name`/`description`/业务 `provides.knowledge` 归目标
 *   `<ext>/adaptation.yaml`    目标的对接来源与已适配版本 `adapted_for`，归目标
 *
 * 用法：node doc/extensions/base/skills/story-adaptation/scripts/adapt-scan.mjs --apply|--check|--mark-adapted|--status|--cleanup-examples [--target <工程根>]
 * 退出：0 通过 / 1 核对不符或清理失败 / 2 参数或前置错误
 */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmdirSync, rmSync, writeFileSync,
} from 'node:fs';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseYaml } from '../../../hooks/shared/yaml.mjs';
import { KNOWLEDGE_SKILL_ENTRY } from '../../../hooks/shared/knowledge.mjs';
import { shellArg } from '../../story/scripts/core/story/drafts.mjs';
import { candidateProblems, entryCheck, entryMaterialize, entryPlan } from './entries.mjs';

const MODES = ['--prepare-init', '--apply', '--check', '--mark-adapted', '--status', '--cleanup-examples'];

const ADAPTERS = 'adapters';
const LEGACY_ADAPTERS = 'skills/story/scripts/adapters';
const LEGACY_DIRS = ['bridges', 'hooks', 'rules', 'skills'];
const RETIRED_STORY = new Set([
  'bridges/agents-skill-story.md', 'bridges/cac-command-story.md', 'bridges/claude-command-story.md', 'bridges/codex-skills-story.md', 'bridges/cursor-skill-story.md', 'bridges/opencode-skill-story.md',
  'hooks/shared/knowledge-use.mjs', 'hooks/shared/knowledge-use/document.mjs', 'hooks/shared/knowledge-use/projection.mjs', 'hooks/shared/knowledge-use/validation.mjs',
  'skills/story/AGENTS.section.md', 'skills/story/phases/spec.md', 'skills/story/rules/ar_design_init.md', 'skills/story/rules/scope_gate.md', 'skills/story/scripts/core/flow/submission.py', 'skills/story/scripts/core/story/review.mjs', 'skills/story/templates/plan-sections.md', 'skills/story/templates/spec-sections.md',
]);
const KNOWLEDGE = 'knowledge';
const CHANGES = 'skills/story-adaptation/reference/upgrade-changes.md';
const BLOCKS = ['知识', '对接层'];
const ADAPTATION = 'adaptation.yaml';
const ADAPTATION_KEYS = ['adapters', 'adapted_for'];

const argv = process.argv.slice(2);
const mode = MODES.find(m => argv.includes(m));
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
const die = (msg, code = 2, category = 'input') => {
  if (mode === '--status') console.log(JSON.stringify({ mode: 'status', error: { category, message: msg } }));
  else console.error(`[adapt-scan] ${msg}`);
  process.exit(code);
};

const read = f => readFileSync(f, 'utf8');
const rel = (base, f) => relative(base, f).split(sep).join('/');
const lf = s => String(s ?? '').replace(/\r\n/g, '\n');

/** 从起点向上找含 framework.config.json 的仓库根。 */
function findRoot(from) {
  for (let d = resolve(from); ; d = dirname(d)) {
    if (existsSync(join(d, 'framework.config.json'))) return d;
    if (d === dirname(d)) return null;
  }
}

function config(root) {
  const f = join(root, 'framework.config.json');
  try {
    return JSON.parse(read(f));
  } catch (e) {
    return die(`${f} 读不出（${e.message}）：扩展落点与需求目录都从它取`, 2, 'config');
  }
}
const extDir = root => config(root)?.paths?.extension_dir || 'doc/extensions';
const featuresDir = root => config(root)?.paths?.features_dir || 'doc/features';

function walk(dir, base = dir, skip = new Set(), all = false) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name), r = rel(base, f);
    if (skip.has(r)) return [];
    if (e.isDirectory()) return !all && (e.name === '__pycache__' || e.name.startsWith('.')) ? [] : walk(f, base, skip, all);
    return [r];
  });
}

function yamlStr(value) {
  const s = String(value);
  return /^[A-Za-z0-9_./-]+$/.test(s) && !['true', 'false', 'null'].includes(s) ? s : JSON.stringify(s);
}

function storyOwnedSet(tgtDoc) {
  const owned = new Set(RETIRED_STORY);
  for (const p of walk(BASE_DIR)) if (/^(?:hooks|rules|skills)\//.test(p)) { owned.add(p); owned.add(`base/${p}`); if (p.startsWith('hooks/') && p.endsWith('/author.md')) owned.add(p.replace(/\.md$/, '.mjs')); }
  for (const b of tgtDoc?.provides?.bridges ?? []) if (b?.source) owned.add(String(b.source).trim());
  return owned;
}

function manifestRefs(doc) {
  const refs = new Set();
  const add = v => { if (typeof v === 'string' && v.trim()) refs.add(v.trim()); };
  for (const a of Object.values(doc?.provides?.skill_assets ?? {})) Object.values(a ?? {}).forEach(add);
  for (const e of Object.values(doc?.provides?.hooks ?? {})) for (const l of Object.values(e ?? {})) (l ?? []).forEach(add);
  Object.values(doc?.provides?.phase_rules_overlays ?? {}).forEach(add);
  for (const s of Object.values(doc?.phase_bindings ?? {})) for (const l of Object.values(s ?? {})) (l ?? []).forEach(b => add(b?.ref));
  return refs;
}

/** 合成运行时唯一根 manifest：按真实所有权合并本包机制，保留目标身份、业务 knowledge 与业务自定义登记，同步退出被接替的旧技能绑定。 */
function composeManifest(pkgText, tgtText, identity) {
  const pkg = parseYaml(pkgText) ?? {};
  const tgt = tgtText ? (parseYaml(tgtText) ?? {}) : {};
  const owned = storyOwnedSet(tgt);
  const isStoryReg = p => owned.has(String(p ?? '').trim());
  const isStoryBind = b => isStoryReg(b?.ref) || (b?.kind === 'skill' && PKG_SKILLS.includes(String(b?.ref ?? '')));
  const name = typeof tgt.name === 'string' && tgt.name.trim() ? tgt.name.trim() : identity.name;
  const description = typeof tgt.description === 'string' && tgt.description.trim()
    ? tgt.description.trim() : identity.description;
  const provides = pkg.provides ?? {};
  const entry = provides.knowledge_entry;
  const rawBiz = Array.isArray(tgt.provides?.knowledge) ? tgt.provides.knowledge : [];
  const biz = rawBiz.filter((item) => {
    const p = typeof item === 'string' ? item.trim() : String(item?.path ?? '').trim();
    return p && p !== KNOWLEDGE_SKILL_ENTRY && p !== 'skills/story-knowledge/SKILL.md';
  });
  const merge2 = (pkgObj, tgtObj, fn) => {
    const res = {};
    for (const [src, own] of [[pkgObj, true], [tgtObj, false]]) {
      for (const [k1, sub] of Object.entries(src ?? {})) for (const [k2, val] of Object.entries(sub ?? {})) fn(res, k1, k2, val, own);
    }
    return res;
  };
  const skillAssets = merge2(provides.skill_assets, tgt.provides?.skill_assets, (r, s, k, v, own) => {
    if (own || (!isStoryReg(v) && !(r[s] && k in r[s]))) (r[s] ??= {})[k] = v;
  });
  const hooks = merge2(provides.hooks, tgt.provides?.hooks, (r, ph, ev, list, own) => {
    const kept = (list ?? []).filter(p => own || !isStoryReg(p));
    if (kept.length) (r[ph] ??= {})[ev] = [...new Set([...(r[ph]?.[ev] ?? []), ...kept])];
  });
  const overlays = { ...Object.fromEntries(Object.entries(tgt.provides?.phase_rules_overlays ?? {}).filter(([, p]) => !isStoryReg(p))), ...(provides.phase_rules_overlays ?? {}) };
  const bindings = merge2(pkg.phase_bindings, tgt.phase_bindings, (r, ph, sl, items, own) => {
    const kept = (items ?? []).filter(b => own || !isStoryBind(b));
    if (!kept.length) return;
    const cur = (r[ph] ??= {})[sl] ?? [];
    for (const b of kept) if (!cur.some(x => x.kind === b.kind && x.ref === b.ref)) cur.push(b);
    r[ph][sl] = cur;
  });
  const verComments = [];
  if (tgtText) {
    const lines = tgtText.split(/\r?\n/);
    const at = lines.findIndex(l => /^version\s*:/.test(l));
    for (let i = at - 1; i >= 0 && lines[i].trimStart().startsWith('#'); i -= 1) verComments.unshift(lines[i]);
  }
  const out = [
    `schema_version: ${JSON.stringify(String(pkg.schema_version ?? '1.1'))}`,
    `name: ${name}`,
    ...verComments,
    `version: ${JSON.stringify(String(pkg.version ?? ''))}`,
    `description: ${description}`,
    'provides:',
  ];
  if (Object.keys(skillAssets).length) {
    out.push('  skill_assets:');
    for (const [sid, assets] of Object.entries(skillAssets)) {
      out.push(`    ${sid}:`);
      for (const [k, v] of Object.entries(assets ?? {})) out.push(`      ${k}: ${v}`);
    }
  }
  out.push('  knowledge:');
  if (entry?.path) {
    out.push(`    - path: ${entry.path}`, `      summary: ${entry.summary}`, `      audience: [${(entry.audience ?? []).join(', ')}]`);
  }
  for (const item of biz) {
    if (typeof item === 'string') out.push(`    - ${item.trim()}`);
    else if (item && typeof item === 'object') {
      out.push(`    - path: ${String(item.path).trim()}`);
      if (item.summary !== undefined) out.push(`      summary: ${yamlStr(item.summary)}`);
      if (Array.isArray(item.audience)) out.push(`      audience: [${item.audience.join(', ')}]`);
      else if (item.audience) out.push(`      audience: ${item.audience}`);
    }
  }
  if (Object.keys(hooks).length) {
    out.push('  hooks:');
    for (const [phase, events] of Object.entries(hooks)) {
      out.push(`    ${phase}:`);
      for (const [ev, list] of Object.entries(events ?? {})) {
        out.push(`      ${ev}:`);
        for (const p of list ?? []) out.push(`        - ${p}`);
      }
    }
  }
  if (Object.keys(overlays).length) {
    out.push('  phase_rules_overlays:');
    for (const [phase, p] of Object.entries(overlays)) out.push(`    ${phase}: ${p}`);
  }
  if (Object.keys(bindings).length) {
    out.push('phase_bindings:');
    for (const [phase, slots] of Object.entries(bindings)) {
      out.push(`  ${phase}:`);
      for (const [slot, items] of Object.entries(slots ?? {})) {
        out.push(`    ${slot}:`);
        for (const b of items ?? []) out.push(`      - {kind: ${b.kind}, ref: ${b.ref}}`);
      }
    }
  }
  return `${out.join('\n')}\n`;
}

function manifestValue(manifestText, key) {
  try {
    const v = parseYaml(manifestText)?.[key];
    return typeof v === 'string' ? v : null;
  } catch {
    return null;
  }
}

function freshIdentity(root) {
  const project = config(root)?.project_name || '目标工程';
  return {
    name: slugOf(project),
    description: `${project} 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）`,
  };
}

const SLUG = /^[a-z][a-z0-9_-]*$/;

function slugOf(project) {
  const s = String(project).replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-').replace(/^[-_]+|[-_]+$/g, '');
  return SLUG.test(s) ? s : 'story-extension';
}

function parseAdaptation(file) {
  const doc = parseYaml(read(file));
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) throw new Error(`${file} 要是映射`);
  for (const k of Object.keys(doc)) if (!ADAPTATION_KEYS.includes(k)) throw new Error(`${file} 有不认识的键：${k}`);
  for (const k of ADAPTATION_KEYS) {
    if (doc[k] !== undefined && typeof doc[k] !== 'string') throw new Error(`${file} 的 ${k} 要是字符串`);
  }
  return doc;
}

function targetAdaptation(tdir, tgtManifestFile) {
  const file = join(tdir, ADAPTATION);
  const legacy = {};
  if (existsSync(tgtManifestFile)) {
    for (const k of ADAPTATION_KEYS) {
      const v = manifestValue(read(tgtManifestFile), k);
      if (v !== null) legacy[k] = v;
    }
  }
  if (existsSync(file)) {
    let doc;
    try { doc = parseAdaptation(file); } catch (e) { return die(e.message); }
    const clash = ADAPTATION_KEYS.filter(k => legacy[k] !== undefined && doc[k] !== undefined && legacy[k] !== doc[k]);
    if (clash.length) die(`旧 manifest 与 ${ADAPTATION} 的 ${clash.join('、')} 不一致：先定用哪一个，再升级`);
    return { doc, text: null };
  }
  const keys = ADAPTATION_KEYS.filter(k => legacy[k] !== undefined);
  return { doc: legacy, text: keys.length ? `${keys.map(k => `${k}: ${JSON.stringify(legacy[k])}`).join('\n')}\n` : '{}\n' };
}

function missingGitignoreLines(root) {
  const fd = featuresDir(root);
  const [dir, name] = [dirname(USAGE.record), basename(USAGE.record)];
  const wants = [[`${fd}/**/AR/story-src/drafts/`, `${fd}/_probe/AR/story-src/drafts/x.md`],
    [`${fd}/**/${USAGE.input_file}`, `${fd}/_probe/${USAGE.input_file}`],
    [`${fd}/${USAGE.state_file}*`, `${fd}/${USAGE.state_file}`],
    [`/${USAGE.record}.lock`, `${USAGE.record}.lock`], [`/${dir}/.${name}.*.tmp`, `${dir}/.${name}.1.tmp`]];
  const f = join(root, '.gitignore');
  const have = existsSync(f) ? read(f).split(/\r?\n/).map(l => l.trim()) : [];
  return wants.filter(([want, probe]) => !have.includes(want)
    && !git(root, ['check-ignore', '-q', '--no-index', probe]).ok).map(([want]) => want);
}

function usageBlockedBy(root) {
  const r = git(root, ['check-ignore', '-v', '--no-index', USAGE.record]);
  const rule = r.ok ? r.out.trim().split('\t')[0] : '';
  return rule.split(':').slice(2).join(':').startsWith('!') ? '' : rule;
}

async function usageWriter(baseRootDir, action) {
  const bridge = join(baseRootDir, 'hooks', 'shared', 'usage.mjs');
  if (!existsSync(bridge)) return { ok: false, errors: [`没有使用记录桥接 ${relative(TARGET, bridge)}`] };
  process.env.PYTHONDONTWRITEBYTECODE = '1';
  try {
    return (await import(pathToFileURL(bridge).href)).recordUsage(TARGET, action);
  } catch (e) {
    return { ok: false, errors: [`使用记录桥接加载失败（${e?.message ?? e}）`] };
  }
}

async function ensureUsage() {
  const r = await usageWriter(BASE_DIR, 'ensure');
  const still = usageBlockedBy(TARGET);
  const lines = [];
  if (r.ok) {
    lines.push(r.changed
      ? `[adapt-scan] 已建立使用记录 ${USAGE.record}（schema ${USAGE.schema}，还没有需求）：它归目标，与这次升级改动一起提交`
      : `[adapt-scan] 使用记录 ${USAGE.record} 已在且合法，保留未动`);
  } else {
    lines.push(`[adapt-scan] 使用记录 ${USAGE.record} 没有建立（${(r.errors ?? []).join('；')}）。机制文件已按上面写完，不用重跑 --apply；`
      + '修好原因后只补这一份（下面一行原样复制，在哪个目录跑都行，-B 不留字节码），补完再跑 --check：');
    lines.push(`  echo '{"action":"ensure"}' | python -B ${shellArg(join(BASE_DIR, 'skills', 'story', 'scripts', 'core', 'usage.py'))}`
      + ` --project-root ${shellArg(TARGET)}`);
  }
  if (still) {
    lines.push(`[adapt-scan] ${USAGE.record} 仍被 ${still} 挡住，使用记录进不了库：`
      + '放行它的父路径与这个文件（其余过程目录保持忽略），或按规则来源找它的维护者；未解决前适配不算完成');
  }
  return { ok: r.ok && !still, lines };
}

function git(root, args) {
  const r = spawnSync('git', ['-C', root, '-c', 'core.quotepath=false', ...args], { encoding: 'utf8' });
  return { ok: r.status === 0, out: r.stdout || '', err: (r.stderr || '').trim() };
}

/** 支持 Git 仓根与仓内子工程（如 repo/apps/pay）：用 Git 顶层加工程相对写面归一路径，兄弟子工程不参与。 */
function repoInfo(root) {
  const r = git(root, ['rev-parse', '--show-toplevel']);
  if (!r.ok) return { ok: false, gitTop: null, prefix: '' };
  const gitTop = resolve(r.out.trim());
  const p = rel(gitTop, resolve(root));
  if (p.startsWith('..')) return { ok: false, gitTop: null, prefix: '' };
  return { ok: true, gitTop, prefix: p === '.' ? '' : p };
}

function dirtyPaths(root) {
  const info = repoInfo(root);
  if (!info.ok) return [];
  const r = git(info.gitTop, ['status', '--porcelain', '-uall']);
  if (!r.ok) return [];
  const all = r.out.split(/\r?\n/).filter(Boolean)
    .map(l => l.slice(3).split(' -> ').pop().replace(/^"|"$/g, ''));
  if (!info.prefix) return all;
  const head = `${info.prefix}/`;
  return all.filter(p => p.startsWith(head)).map(p => p.slice(head.length));
}

function adaptersStatus() {
  const dir = join(TDIR, ADAPTERS);
  const story = existsSync(join(dir, 'story.js')), token = existsSync(join(dir, 'token.js'));
  const standIn = TARGET_ADAPTATION.doc.adapters === 'stand-in';
  const status = story && token ? (standIn ? 'stand_in' : 'present') : story || token ? 'partial' : 'missing';
  return { dir: `${extDir(TARGET)}/${ADAPTERS}`, story, token, standIn, status };
}

function adapterGap(ad = adaptersStatus()) {
  if (ad.story && ad.token) return null;
  const miss = [!ad.story && 'story.js', !ad.token && 'token.js'].filter(Boolean);
  return `对接层未就位（${ad.standIn ? 'stand-in/' : ''}${ad.status}，${ad.dir} 缺 ${miss.join('、')}）——补齐对接文件并核验`;
}

function planAdapterMigration() {
  const legacy = join(TDIR, ...LEGACY_ADAPTERS.split('/'));
  if (!existsSync(legacy) || TARGET_ADAPTATION.doc.adapters === 'stand-in') return { copy: [], conflicts: [] };
  const copy = [], conflicts = [];
  for (const p of walk(legacy)) {
    const src = join(legacy, ...p.split('/')), dst = join(TDIR, ADAPTERS, ...p.split('/'));
    if (!existsSync(dst)) copy.push(p);
    else if (!readFileSync(src).equals(readFileSync(dst))) conflicts.push(`${ADAPTERS}/${p}（与旧 ${LEGACY_ADAPTERS}/${p} 内容不同）`);
  }
  return { copy, conflicts };
}

function pruneEmpty(dir, dropPycache = false) {
  if (!existsSync(dir)) return;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) {
      if (dropPycache && e.name === '__pycache__') rmSync(p, { recursive: true, force: true });
      else pruneEmpty(p, dropPycache);
    }
  }
  if (!readdirSync(dir).length) rmdirSync(dir);
}

function cleanupExamples() {
  const examples = join(BASE_DIR, 'examples'), gitignore = join(BASE_DIR, '.gitignore');
  if (!existsSync(examples)) return { ok: true, removed: false, gitignorePreserved: existsSync(gitignore) };
  const mf = join(examples, '.manifest.json');
  let expected = null;
  if (existsSync(mf)) { try { expected = JSON.parse(read(mf))?.files; } catch { expected = null; } }
  if (!expected || typeof expected !== 'object' || !Object.keys(expected).length) {
    return { ok: false, removed: false, gitignorePreserved: existsSync(gitignore), error: 'base/examples/.manifest.json 缺失或无效，拒绝递归删除' };
  }
  const all = walk(examples, examples, new Set(['.manifest.json']), true);
  const kept = all.flatMap((p) => {
    const exp = expected[p];
    if (!exp) return [`${p}（用户新增，不在发行样例清单内）`];
    const got = `sha256:${createHash('sha256').update(lf(read(join(examples, ...p.split('/')))), 'utf8').digest('hex')}`;
    return got === exp ? [] : [`${p}（内容已改动，与发行样例字节不符）`];
  });
  if (kept.length) return { ok: false, removed: false, gitignorePreserved: existsSync(gitignore), error: `保留非包/已改动文件，未删除：${kept.join('；')}` };
  try { for (const p of all) rmSync(join(examples, ...p.split('/'))); rmSync(mf); pruneEmpty(examples); } catch (e) {
    return { ok: false, removed: false, gitignorePreserved: existsSync(gitignore), error: String(e?.message ?? e) };
  }
  return { ok: !existsSync(examples), removed: true, gitignorePreserved: existsSync(gitignore),
    error: existsSync(examples) ? `${rel(TARGET, examples)} 清理后仍存在` : undefined };
}

const SCRIPT_BASE = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
if (!mode) die(`缺模式：${MODES.join(' | ')}`);
if (argv.includes('--package')) {
  die('本版采用业务工程内就地适配，已退出跨工程 --package 参数：请把 base/ 解包到目标工程 <ext>/base/ 后直接运行其中的 adapt-scan.mjs', 2);
}
const TARGET = opt('--target') ? findRoot(opt('--target')) : findRoot(SCRIPT_BASE);
if (!TARGET) {
  die(`找不到业务工程根（向上未找到 framework.config.json）：${opt('--target') ?? SCRIPT_BASE}；`
    + '空仓首次接入请先执行 framework-init CREATE，或按首装最小根清单写入 docs.post_check 后再初始化', 2, 'config');
}
const TDIR = join(TARGET, ...extDir(TARGET).split('/'));
const BASE_DIR = opt('--source-base') ? resolve(opt('--source-base')) : (opt('--target') ? join(TDIR, 'base') : SCRIPT_BASE);
const pkgManifest = join(BASE_DIR, 'package-manifest.yaml');
if (!existsSync(pkgManifest)) die(`机制包缺少 package-manifest.yaml：${pkgManifest}`, 2, 'package');

const harness = join(TARGET, 'framework', 'harness');
const yamlPkg = join(harness, 'node_modules', 'yaml');
if (!existsSync(join(harness, 'package.json'))) {
  console.error(`[adapt-scan] 目标还没有 ${relative(TARGET, harness)}：扩展的门禁要在接入 framework 并装好 harness 依赖之后才能跑`);
} else if (!existsSync(yamlPkg)) {
  die(`目标的 framework harness 还没装依赖（缺 ${relative(TARGET, yamlPkg)}）：`
    + '先在目标里跑 `cd framework/harness && npm install`，再 --apply / --check', 2, 'dependency');
}

const USAGE = JSON.parse(read(join(BASE_DIR, 'skills', 'story', 'contracts', 'usage.json')));
const HOOKS_OFF = config(TARGET)?.lifecycle_hooks_enabled === false
  ? '[adapt-scan] 采集限制：目标 framework.config.json 的 lifecycle_hooks_enabled 是 false，Framework 不执行扩展的阶段钩子，'
    + `直接走 Framework 阶段的使用不会记进 ${USAGE.record}（Story 命令照常记）；`
    + '恢复采集要把它改成 true 或删掉这个键（Framework 默认开启）'
  : null;

const PKG_MANIFEST_TEXT = read(pkgManifest);
const PKG_SKILLS = (() => {
  try {
    const skills = parseYaml(PKG_MANIFEST_TEXT)?.provides?.skills ?? [];
    return skills.filter(s => typeof s === 'string');
  } catch (e) {
    return die(`包的 package-manifest.yaml 读不出（${e.message}）`, 2, 'package');
  }
})();
const PKG_VERSION = manifestValue(PKG_MANIFEST_TEXT, 'version');
const tgtManifest = join(TDIR, 'manifest.yaml');
const INSTALLED = existsSync(tgtManifest) ? manifestValue(read(tgtManifest), 'version') ?? '0' : null;
const legacyPresent = LEGACY_DIRS.some(d => existsSync(join(TDIR, d)));
const STATE = existsSync(tgtManifest) ? (legacyPresent ? 'legacy_upgrade' : 'upgrade') : 'fresh';
const TARGET_ADAPTATION = targetAdaptation(TDIR, tgtManifest);
const CHANGE_ENTRIES = changeEntries();

function changeEntries() {
  const file = join(BASE_DIR, ...CHANGES.split('/'));
  if (!existsSync(file)) die(`包里没有升级演进记录：${CHANGES}`, 2, 'package');
  const out = [];
  let version = null;
  read(file).split(/\r?\n/).forEach((line, i) => {
    const head = line.match(/^##\s+(\d+(?:\.\d+)+)\s*$/);
    if (head) { version = head[1]; return; }
    if (version && /^\s+-\s/.test(line)) die(`${CHANGES} 第 ${i + 1} 行是缩进的子项：演进记录每条一行、不用子项`, 2, 'package');
    if (!version || !/^-\s+\S/.test(line)) return;
    const m = line.match(/^-\s+\[([^\]]+)\]\s*(.+)$/);
    if (!m || !BLOCKS.includes(m[1])) die(`${CHANGES} 第 ${i + 1} 行没有块标签（${BLOCKS.map(b => `[${b}]`).join(' / ')}）`, 2, 'package');
    out.push({ version, block: m[1], text: m[2].trim() });
  });
  return out;
}

const newer = (a, b) => {
  const x = String(a).split('.').map(Number);
  const y = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) > (y[i] ?? 0);
  }
  return false;
};

function knowledgeDigest(files) {
  const h = createHash('sha256');
  for (const f of files) {
    const abs = join(TDIR, ...f.split('/'));
    h.update(f).update('\0').update(existsSync(abs) ? read(abs).replace(/\r\n/g, '\n') : '').update('\0');
  }
  return `sha256:${h.digest('hex').slice(0, 16)}`;
}

async function knowledgeCheck() {
  try {
    const api = await import(pathToFileURL(join(BASE_DIR, 'hooks', 'shared', 'knowledge.mjs')).href);
    const k = api.activeKnowledge(TARGET);
    const problems = api.selfCheck(TARGET, k);
    if (problems.length) return { status: 'FAIL', problems };
    const files = [...k.facts, ...k.constraints, ...k.patterns].map(x => x.file);
    const counts = {};
    for (const kind of ['facts', 'constraints', 'patterns']) {
      for (const x of k[kind]) counts[`${kind} × ${x.form}`] = (counts[`${kind} × ${x.form}`] ?? 0) + 1;
    }
    const byUse = new Map();
    for (const x of [...k.facts, ...k.constraints, ...k.patterns]) {
      const use = String(x.appliesWhen ?? '').trim();
      byUse.set(use, [...(byUse.get(use) ?? []), x.file]);
    }
    const sameUse = [...byUse].filter(([, list]) => list.length > 1)
      .map(([appliesWhen, list]) => ({ appliesWhen, files: list }));
    const digest = knowledgeDigest(files);
    return { status: 'PASS', counts, digest, files, review: await knowledgeReview(digest, files),
      sameUse: { note: '同用途声明候选，须语义核对', groups: sameUse } };
  } catch (e) {
    return { status: 'FAIL', problems: [String(e?.message ?? e)] };
  }
}

const REVIEW_DIMENSIONS = ['granularity', 'fact_use', 'duplication', 'coding_boundary'];
const REVIEW_VERDICTS = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];

async function knowledgeReview(digest, files) {
  const file = join(TDIR, '.adapt', 'knowledge-review.md');
  if (!existsSync(file)) return { status: 'missing', problems: ['.adapt/knowledge-review.md 不在：还没有独立审查报告'] };
  const { parseYaml: parse } = await import(pathToFileURL(join(BASE_DIR, 'hooks', 'shared', 'yaml.mjs')).href);
  const blocks = [...read(file).matchAll(/```ya?ml\r?\n([\s\S]*?)```/g)].map((m) => {
    try { return parse(m[1])?.knowledge_review; } catch { return undefined; }
  }).filter(Boolean);
  if (blocks.length !== 1) return { status: 'invalid', problems: [`证据块要恰好一个 \`knowledge_review:\` YAML 块（现在 ${blocks.length} 个）`] };
  const r = blocks[0];
  if (r.digest !== digest) return { status: 'stale', problems: [`报告审的是 ${r.digest ?? '（没写）'}，当前知识是 ${digest}：知识或激活清单改过，对受影响的知识重审`] };
  const listed = Array.isArray(r.files) ? r.files.map(x => String(x?.path ?? '')) : [];
  const problems = [];
  const twice = [...new Set(listed.filter((f, i) => listed.indexOf(f) !== i))];
  if (twice.length) problems.push(`同一份知识写了多项：${twice.join('、')}——一份一项，不让后一项盖住前一项`);
  const extra = listed.filter(f => !files.includes(f));
  if (extra.length) problems.push(`报告里有激活清单之外的条目：${extra.join('、')}`);
  for (const f of files) {
    const rows = (Array.isArray(r.files) ? r.files : []).filter(x => String(x?.path ?? '') === f);
    if (!rows.length) { problems.push(`${f}：报告里没有这一份`); continue; }
    for (const row of rows) {
      const lacking = REVIEW_DIMENSIONS.filter(d => !String(row[d]?.evidence ?? '').trim());
      if (lacking.length) problems.push(`${f}：${lacking.join('、')} 没写证据`);
      for (const d of REVIEW_DIMENSIONS) {
        const v = String(row[d]?.verdict ?? '').trim().toUpperCase();
        if (!REVIEW_VERDICTS.includes(v)) problems.push(`${f}：${d} 的结论「${row[d]?.verdict ?? ''}」不在 ${REVIEW_VERDICTS.join(' / ')} 里`);
        else if (!['PASS', 'WARN'].includes(v)) problems.push(`${f}：${d} 判 ${v}——${v === 'FAIL' ? '改完这份知识再审' : '没有审完，不算适配完成'}`);
      }
    }
  }
  for (const key of ['blocking', 'unreviewed']) {
    if (!Array.isArray(r[key])) problems.push(`\`${key}\` 不是列表（没有就写空列表）`);
    else if (r[key].length) problems.push(`\`${key}\` 还有 ${r[key].length} 项：${r[key].map(x => (typeof x === 'string' ? x : JSON.stringify(x))).join('；')}`);
  }
  if (!String(r.executor ?? '').trim()) problems.push('`executor` 没写宿主返回的独立执行或会话引用');
  return problems.length ? { status: 'incomplete', problems } : { status: 'valid', executor: r.executor };
}

async function followUp() {
  const since = TARGET_ADAPTATION.doc.adapted_for ?? '0';
  const items = Object.fromEntries(BLOCKS.map(b => [b, []]));
  for (const e of CHANGE_ENTRIES) {
    if (newer(e.version, since) && items[e.block]) items[e.block].push(`${e.version}：${e.text}`);
  }
  return { since, installed: INSTALLED, items, adapters: adaptersStatus(), check: await knowledgeCheck() };
}

function writeAdaptedFor() {
  const file = join(TDIR, ADAPTATION);
  const lines = (existsSync(file) ? read(file) : '').split(/\r?\n/).filter(l => l.trim() && l.trim() !== '{}');
  const row = `adapted_for: ${JSON.stringify(PKG_VERSION)}`;
  const at = lines.findIndex(l => /^adapted_for\s*:/.test(l));
  if (at >= 0) lines[at] = row;
  else lines.push(row);
  const next = `${lines.join('\n')}\n`;
  if (!existsSync(file) || read(file) !== next) writeFileSync(file, next, 'utf8');
}

async function printFollowUp() {
  const f = await followUp();
  console.log(`[adapt-scan] 按版本跟进：${JSON.stringify(f)}`);
  const adGap = adapterGap(f.adapters);
  if (Object.values(f.items).some(list => list.length) || f.check.status !== 'PASS' || adGap) {
    if (adGap) console.log(`[adapt-scan] 尚欠对接层：${adGap}`);
    console.log('[adapt-scan] 有演进条目、知识不合协议或对接层未就位（条目是待判断的适配主题，不表示目标仓已采用）：按块摆出来，停一次问人「现在做这些适配吗」；'
      + '选稍后就不写任何东西；选中的知识与对接适配都交回后跑 --mark-adapted（将核入口/知识/对接、清理 base/examples/ 并最后写 adapted_for）');
    return true;
  }
  const cleaned = cleanupExamples();
  if (!cleaned.ok || !cleaned.gitignorePreserved) {
    console.error(`[adapt-scan] 清理 base/examples/ 失败（${cleaned.error ?? 'base/.gitignore 缺失'}）：不报适配完成，adapted_for 未写入`);
    return false;
  }
  writeAdaptedFor();
  console.log(`[adapt-scan] 目标已按包的版本适配，入口、知识与对接（${f.adapters.status}）已核，样例已清理，adapted_for 记为 ${PKG_VERSION}`);
  return true;
}

if (mode === '--cleanup-examples') {
  const cleaned = cleanupExamples();
  if (!cleaned.ok) die(`清理 base/examples/ 失败：${cleaned.error}（不报适配完成）`, 1);
  console.log(`[adapt-scan] ${cleaned.removed ? '已清理 base/examples/' : 'base/examples/ 已不存在（重入幂等）'}；base/.gitignore ${cleaned.gitignorePreserved ? '保留' : '缺失'}`);
  process.exit(cleaned.gitignorePreserved ? 0 : 1);
}

if (mode === '--status') {
  const ident = key => (existsSync(tgtManifest) ? manifestValue(read(tgtManifest), key) : null);
  const out = {
    mode: 'status', package: { version: PKG_VERSION, examplesPresent: existsSync(join(BASE_DIR, 'examples')) },
    target: {
      installed: existsSync(tgtManifest), state: STATE, version: INSTALLED,
      name: ident('name'), description: ident('description'),
      adapters: adaptersStatus(), adapted_for: TARGET_ADAPTATION.doc.adapted_for ?? null,
    },
    history: 'unknown：升级前所装版本与历次已完成的适配读不到，以上次交回为准；items 只按当前游标推导',
  };
  if (!existsSync(tgtManifest)) {
    console.log(JSON.stringify({ ...out, state: 'not_installed' }, null, 2));
    process.exit(0);
  }
  const f = await followUp();
  out.items = f.items;
  out.knowledge = f.check;
  console.log(JSON.stringify(out, null, 2));
  process.exit(f.check.status === 'PASS' ? 0 : 1);
}

if (mode === '--mark-adapted') {
  if (!existsSync(tgtManifest)) die('目标没有 manifest.yaml：还没装过，先 --apply');
  if (INSTALLED !== PKG_VERSION) {
    die(`目标机制是 ${INSTALLED}、包是 ${PKG_VERSION}：先 --apply 把机制升到包的版本，再做适配`);
  }
  let entries;
  try { entries = entryCheck(TARGET, PKG_SKILLS); } catch (e) { die(`宿主入口核不了（${e.message}）`, 2); }
  if (entries.problems.length) die(`宿主入口核对不符，adapted_for 不写：\n  ${entries.problems.join('\n  ')}`, 2);
  const f = await followUp();
  if (f.check.status !== 'PASS') die(`知识不能按当前协议加载，适配还没做完：\n  ${f.check.problems.join('\n  ')}`, 2);
  if (f.items.知识?.length && f.check.review.status !== 'valid') {
    die(`本次有 ${f.items.知识.length} 条知识演进要适配，知识独审证据不成立（${f.check.review.status}）：\n  `
      + `${f.check.review.problems.join('\n  ')}\n  按 reference/knowledge-review.md 发起与收回审查；`
      + '机制已经装好，知识适配未完成，adapted_for 不写', 2);
  }
  const adGap = adapterGap(f.adapters);
  if (adGap) die(`${adGap}；适配未完成，不清理 base/examples/，adapted_for 不写`, 2);
  const cleaned = cleanupExamples();
  if (!cleaned.ok) die(`清理 base/examples/ 失败（${cleaned.error}）：不报适配完成，adapted_for 未写入`, 1);
  if (!cleaned.gitignorePreserved) die('base/.gitignore 缺失：清理后必须保留 base/.gitignore，adapted_for 未写入', 1);
  writeAdaptedFor();
  console.log(`[adapt-scan] 宿主入口与目标知识读回通过，对接状态 ${f.adapters.status}（${f.adapters.dir}），`
    + `${cleaned.removed ? '已清理' : '已确认清理'} base/examples/（保留 base/.gitignore），adapted_for 记为 ${PKG_VERSION}`);
  process.exit(0);
}

if (mode === '--apply' || mode === '--prepare-init') {
  const prep = mode === '--prepare-init', dryRun = argv.includes('--dry-run');
  if (!repoInfo(TARGET).ok) {
    die(`目标不在 git 仓库内：${TARGET}\n  这一次要改写或清理旧机制与宿主入口，没存档的改动被盖掉就找不回来了。`);
  }
  const currentManifest = existsSync(tgtManifest) ? read(tgtManifest) : '';
  const tgtDoc = currentManifest ? (parseYaml(currentManifest) ?? {}) : {};
  const owned = storyOwnedSet(tgtDoc);
  const composedText = composeManifest(PKG_MANIFEST_TEXT, currentManifest, freshIdentity(TARGET));
  const bizRefs = manifestRefs(parseYaml(composedText) ?? {});
  const composedName = manifestValue(composedText, 'name');
  if (!SLUG.test(composedName ?? '')) {
    die(`目标 manifest 的 name（${composedName}）不是小写 slug：Framework 按它识别扩展，`
      + '先把它改成小写字母开头、只含小写字母数字与 _ -，再升级。目标一个字节未写', 2);
  }
  let candidate;
  try {
    candidate = candidateProblems(TARGET, (dir) => {
      for (const p of walk(BASE_DIR)) {
        mkdirSync(dirname(join(dir, 'base', ...p.split('/'))), { recursive: true });
        copyFileSync(join(BASE_DIR, ...p.split('/')), join(dir, 'base', ...p.split('/')));
      }
      writeFileSync(join(dir, 'manifest.yaml'), composedText, 'utf8');
      const skip = new Set(['base', 'manifest.yaml', ADAPTATION]);
      for (const p of walk(TDIR, TDIR, skip)) {
        if (owned.has(p) || p.startsWith(`${LEGACY_ADAPTERS}/`)) continue;
        mkdirSync(dirname(join(dir, ...p.split('/'))), { recursive: true });
        copyFileSync(join(TDIR, ...p.split('/')), join(dir, ...p.split('/')));
      }
    });
  } catch (e) {
    die(`待装的扩展核不了（${e.message}）`);
  }
  if (candidate.length) {
    console.error(`[adapt-scan] 停：待装的扩展有 ${candidate.length} 处 Framework 不认的登记：`);
    candidate.forEach(c => console.error(`  ${c}`));
    die('包或目标的知识登记要先修好。目标一个字节未写', 2);
  }
  let plan;
  try { plan = entryPlan(TARGET, PKG_SKILLS, { includeEntries: !prep }); } catch (e) { die(`宿主入口核不了（${e.message}）`); }

  const extRel = extDir(TARGET);
  const legacyAll = LEGACY_DIRS.flatMap(d => walk(join(TDIR, d)).map(p => `${d}/${p}`));
  const legacyOwn = legacyAll.filter(p => owned.has(p) || p.startsWith(`${LEGACY_ADAPTERS}/`));
  const unknownLegacy = legacyAll.filter(p => !owned.has(p) && !p.startsWith(`${LEGACY_ADAPTERS}/`) && !bizRefs.has(p));
  const legacyFiles = prep ? [] : legacyOwn.map(p => `${extRel}/${p}`);
  const adapterPlan = prep ? { copy: [], conflicts: [] } : planAdapterMigration();
  const writeSurface = new Set(prep ? [...plan.retire] : [...legacyFiles, ...plan.pendingEntries, ...plan.retire, ...plan.pendingBridges]);
  if (opt('--source-base') && existsSync(join(TDIR, 'base'))) {
    for (const p of walk(join(TDIR, 'base'), join(TDIR, 'base'), new Set(), true)) writeSurface.add(`${extRel}/base/${p}`);
  }
  if (existsSync(tgtManifest) && lf(currentManifest) !== lf(composedText)) writeSurface.add(`${extRel}/manifest.yaml`);
  if (TARGET_ADAPTATION.text !== null && existsSync(join(TDIR, ADAPTATION))) writeSurface.add(`${extRel}/${ADAPTATION}`);
  if (!prep && (missingGitignoreLines(TARGET).length || usageBlockedBy(TARGET).startsWith('.gitignore:'))) writeSurface.add('.gitignore');
  if (STATE === 'fresh' && !config(TARGET)?.paths?.extension_dir) writeSurface.add('framework.config.json');

  const dirty = dirtyPaths(TARGET).filter(p => writeSurface.has(p));
  if (dirty.length) {
    console.error(`[adapt-scan] 停：写入面上有 ${dirty.length} 处未提交改动，升级会盖掉它们：`);
    dirty.forEach(p => console.error(`  ${p}`));
    die('先提交或暂存自己的改动再升级——本命令不替你动工作区（不 stash、不提交）', 2);
  }
  if (!prep && unknownLegacy.length) {
    console.error(`[adapt-scan] 停：旧机制目录下发现 ${unknownLegacy.length} 处未归属且未在 manifest 登记的文件，保留不动：`);
    unknownLegacy.forEach(p => console.error(`  ${extRel}/${p}`));
    die('请确认去留（归属业务则登记或移至自有目录，无用则删除）再升级。目标一个字节未写', 2);
  }
  if (adapterPlan.conflicts.length) {
    console.error(`[adapt-scan] 停：对接层存在 ${adapterPlan.conflicts.length} 处同名内容冲突：`);
    adapterPlan.conflicts.forEach(c => console.error(`  ${c}`));
    die('先确认保留哪一份再升级。目标一个字节未写', 2);
  }
  if (!prep && existsSync(join(TARGET, ...USAGE.record.split('/')))) {
    const u = await usageWriter(BASE_DIR, 'inspect');
    if (!u.ok) die(`使用记录 ${USAGE.record} 不合法（${(u.errors ?? []).join('；')}）：它不会被当成空表覆盖。机制一个字节没写，修好后重跑 --apply`, 2);
  }
  if (plan.conflicts.length) {
    console.error(`[adapt-scan] 停：宿主入口有 ${plan.conflicts.length} 处 Framework 物化会覆盖或不接管的内容：`);
    plan.conflicts.forEach(c => console.error(`  ${c}`));
    die('这些内容要保留就挪到它自己的位置，确认可弃就删掉，再升级。目标一个字节未写', 2);
  }
  if (dryRun) {
    console.log('[adapt-scan] 写前预检通过（dry-run，目标零字节写入）');
    process.exit(0);
  }
  const written = [];
  const removed = [];
  if (!existsSync(tgtManifest) || lf(read(tgtManifest)) !== lf(composedText)) {
    mkdirSync(dirname(tgtManifest), { recursive: true });
    writeFileSync(tgtManifest, composedText, 'utf8');
    written.push('manifest.yaml');
  }
  if (TARGET_ADAPTATION.text !== null) {
    writeFileSync(join(TDIR, ADAPTATION), TARGET_ADAPTATION.text, 'utf8');
    written.push(ADAPTATION);
  }
  if (STATE === 'fresh') {
    const cfgFile = join(TARGET, 'framework.config.json');
    const cfg = config(TARGET);
    if (!cfg?.paths?.extension_dir) {
      cfg.paths = { ...(cfg.paths || {}), extension_dir: 'doc/extensions' };
      writeFileSync(cfgFile, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8');
      written.push('framework.config.json');
    }
  }
  if (prep) {
    for (const p of plan.retire) { const abs = join(TARGET, ...p.split('/')); if (existsSync(abs)) { rmSync(abs, { force: true }); removed.push(p); } }
    console.log(`[adapt-scan] 已预置根清单（写入 ${written.length} 个文件：${written.join('、') || '无变更'}${removed.length ? `，退出已核旧桥 ${removed.length} 个` : ''}），`
      + '已合入 docs.post_check 稳定登记并保留业务登记；可直接执行项目级 framework-init（CREATE/UPDATE）生成／刷新宿主桥');
    process.exit(0);
  }
  const legacyAdapters = join(TDIR, ...LEGACY_ADAPTERS.split('/'));
  for (const p of adapterPlan.copy) {
    const to = join(TDIR, ADAPTERS, ...p.split('/'));
    mkdirSync(dirname(to), { recursive: true });
    copyFileSync(join(legacyAdapters, ...p.split('/')), to);
    written.push(`${ADAPTERS}/${p}`);
  }
  for (const p of legacyOwn) {
    const abs = join(TDIR, ...p.split('/'));
    if (existsSync(abs)) { rmSync(abs, { force: true }); removed.push(p); }
  }
  for (const d of LEGACY_DIRS) pruneEmpty(join(TDIR, d), true);
  {
    const f = join(TARGET, '.gitignore');
    const have = existsSync(f) ? read(f) : '';
    const missing = missingGitignoreLines(TARGET);
    if (usageBlockedBy(TARGET).startsWith('.gitignore:')) missing.push(`!/${USAGE.record}`);
    if (missing.length) {
      writeFileSync(f, `${have.replace(/\n*$/, '\n')}${missing.join('\n')}\n`, 'utf8');
      written.push('.gitignore');
    }
  }
  let entries;
  try { entries = entryMaterialize(TARGET, plan.retire, PKG_SKILLS); } catch (e) {
    die(`宿主入口物化失败（${e.message}）：已写入 ${written.length} 个文件，用 git 查看并处理`, 1);
  }
  written.push(...entries.written);
  removed.push(...entries.removed);
  entries.warnings.forEach(w => console.error(`[adapt-scan] 已知限制：${w}`));
  if (entries.problems.length) {
    console.error(`[adapt-scan] 宿主入口物化后核对不符 ${entries.problems.length} 处：`);
    entries.problems.forEach(p => console.error(`  ${p}`));
    die(`已写入 ${written.length} 个文件：用 git 查看这次的改动并处理`, 1);
  }
  const usage = await ensureUsage();
  if (!written.length && !removed.length) {
    console.log('[adapt-scan] 机制已在包的版本上，本次已重新核对宿主入口、知识可读与对接状态');
  } else {
    console.log(`[adapt-scan] ${usage.ok ? `${STATE === 'fresh' ? '首次安装' : STATE === 'legacy_upgrade' ? '旧混装升级' : '升级'}完成` : '机制文件写完，适配没有全部完成（见下）'}：`
      + `写入 ${written.length} 个文件，清除 ${removed.length} 个旧文件`);
    if (removed.length) removed.forEach(p => console.log(`  - ${p}`));
  }
  usage.lines.forEach(l => console.log(l));
  if (HOOKS_OFF) console.log(HOOKS_OFF);
  const followOk = await printFollowUp();
  process.exit(usage.ok && followOk ? 0 : 1);
}

// ── --check ───────────────────────────────────────────────────────────────
const bad = [];
if (!existsSync(join(BASE_DIR, '.gitignore'))) bad.push('① 机制包缺 base/.gitignore');
const ownedForCheck = storyOwnedSet(existsSync(tgtManifest) ? (parseYaml(read(tgtManifest)) ?? {}) : {});
for (const d of LEGACY_DIRS) {
  const left = walk(join(TDIR, d)).map(p => `${d}/${p}`).filter(p => ownedForCheck.has(p) || p.startsWith(`${LEGACY_ADAPTERS}/`));
  if (left.length) bad.push(`① 扩展根残留旧机制文件（${d}/ 共 ${left.length} 个，如 ${left[0]}）——跑 --apply 退出旧布局`);
}
const scriptsAt = join(BASE_DIR, 'skills', 'story', 'scripts');
if (existsSync(scriptsAt)) {
  for (const e of readdirSync(scriptsAt, { withFileTypes: true })) {
    if (e.isDirectory()) {
      if (!['core', '__pycache__'].includes(e.name)) bad.push(`① base/skills/story/scripts/ 只应含 core/：发现 ${e.name}`);
    } else bad.push(`① base/skills/story/scripts/ 根下有独立文件：${e.name}`);
  }
}
if (existsSync(tgtManifest)) {
  const tgtText = read(tgtManifest);
  if (lf(composeManifest(PKG_MANIFEST_TEXT, tgtText, freshIdentity(TARGET))) !== lf(tgtText)) {
    bad.push('② 根 manifest.yaml 不是由当前 base/package-manifest.yaml 按所有权合成的——跑 --apply 重新合成');
  }
  if (!existsSync(join(TDIR, ADAPTATION))) bad.push(`② 目标没有 ${ADAPTATION}：跑 --apply 写上`);
} else {
  bad.push('② 目标没有 manifest.yaml：这个仓还没装过，跑 --apply');
}
try {
  for (const p of entryCheck(TARGET, PKG_SKILLS).problems) bad.push(`③ 宿主入口：${p}——跑 --apply 物化`);
} catch (e) {
  bad.push(`③ 宿主入口核不了：${e.message}`);
}
for (const line of missingGitignoreLines(TARGET)) bad.push(`④ 工作件没被 .gitignore 挡住：补一行 ${line}`);
const blocked = usageBlockedBy(TARGET);
if (blocked) bad.push(`④ 使用记录 ${USAGE.record} 被 ${blocked} 挡住：它归目标，要能随普通 git add 入库`);
const u = await usageWriter(BASE_DIR, 'inspect');
if (!u.ok) bad.push(`④ 使用记录：${(u.errors ?? []).join('；')}——缺了跑 --apply 建立；坏了修好后重验，不重置成空表`);
const kc = await knowledgeCheck();
if (kc.status !== 'PASS') bad.push(`⑤ 目标知识不可读：${kc.problems.join('；')}`);
const ad = adaptersStatus();
const adGap = adapterGap(ad);
if (adGap) bad.push(`⑥ ${adGap}`);
if (HOOKS_OFF) console.log(HOOKS_OFF);
if (bad.length) {
  console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`);
  bad.forEach(b => console.error(`  ${b}`));
  process.exit(1);
}
console.log(`[adapt-scan] 核对通过：base 布局与根 manifest 一致 / 宿主入口指向 base/skills / 使用记录合法 / `
  + `知识可读（${kc.files.length} 份） / 对接层 ${ad.status}（${ad.dir}） / `
  + `base/examples ${existsSync(join(BASE_DIR, 'examples')) ? '待清理（完成后跑 --mark-adapted）' : '已清理'}`);
