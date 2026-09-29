#!/usr/bin/env node
/**
 * 宿主入口交给 Framework 原生物化：写前核、退出旧入口、物化、写后核。维护安装与对外 adapt 共用。
 *
 * 原生 materialize 整份重写 AGENTS.md / CLAUDE.md，只保护带归属标记的 Skill 桥接。所以写前逐个比：
 *   - 入口文件去掉已装旧版的 story-ext 段后，必须与原生按当前配置渲染的结果逐字相同；
 *     有任何别的内容（人工段、旧生成物）就报冲突，不物化。
 *   - 已装旧版 manifest 登记的入口（target/source），目标与已装源逐字相同才退出；改过的报冲突。
 *   - 本次要物化的 Skill 入口位置上已有无归属或被改过的文件，报冲突。
 *
 * 用法：node entries.mjs --project-root <工程根> --action plan --skills a,b [--candidate <待装扩展目录>] | materialize --retire p,q | check
 * 输出 JSON；退出 0 通过，1 有冲突或核对不符，2 输入或依赖错误。
 */
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadNative } from '../../../hooks/shared/framework-access.mjs';

const BEGIN = '<!-- story-ext:begin -->';
const END = '<!-- story-ext:end -->';
const OLD_SECTION = 'skills/story/AGENTS.section.md';

const lf = text => text.replace(/\r\n/g, '\n');
const read = file => (fs.existsSync(file) ? fs.readFileSync(file) : null);

function context(root) {
  const native = loadNative(root);
  const { loadFrameworkConfigWithSources } = native.module('config.ts');
  const sources = loadFrameworkConfigWithSources(native.root);
  const raw = sources.projectRaw ?? {};
  const adapters = [...new Set((Array.isArray(raw.materialized_adapters) ? raw.materialized_adapters : [])
    .filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))];
  if (!adapters.length) throw new Error('framework.config.json 的 materialized_adapters 为空：没有要物化的宿主');
  const extDir = sources.config.paths?.extension_dir ?? 'doc/extensions';
  return { native, raw, adapters, extDir, extRoot: path.join(native.root, ...extDir.split('/')) };
}

/** 各宿主的入口文件（AGENTS.md / CLAUDE.md …）与原生按当前配置的渲染。 */
function renderedEntries(ctx) {
  const { native, raw, adapters } = ctx;
  const YAML = native.require('yaml');
  const tr = native.module('scripts/utils/template-renderer.ts');
  const template = fs.readFileSync(path.join(native.frameworkRoot, 'templates', 'AGENTS.md.template'), 'utf8');
  const targets = new Set();
  for (const adapter of adapters) {
    const file = path.join(native.frameworkRoot, 'agents', adapter, 'adapter.yaml');
    if (!fs.existsSync(file)) throw new Error(`adapter 不存在：${adapter}`);
    const target = YAML.parse(fs.readFileSync(file, 'utf8'))?.agent_entry_file?.target_path;
    if (typeof target === 'string' && target.trim()) targets.add(target.trim());
  }
  return [...targets].map(target => ({
    target,
    rendered: tr.renderAgentsTemplate(template, tr.buildAgentsTemplateVars(raw, {
      entryFile: target, projectRoot: native.root, frameworkRoot: native.frameworkRoot,
    })),
  }));
}

/** 去掉已装旧版的 story-ext 段（连同它前面那一空行）；段与已装源不符或标记不成对返回 null。 */
function withoutOldZone(text, section) {
  const lines = text.split(/\r?\n/);
  const begins = lines.flatMap((l, i) => (l.includes(BEGIN) ? [i] : []));
  const ends = lines.flatMap((l, i) => (l.includes(END) ? [i] : []));
  if (!begins.length && !ends.length) return text;
  if (begins.length !== 1 || ends.length !== 1 || ends[0] < begins[0] || section === null) return null;
  const body = lines.slice(begins[0] + 1, ends[0]).join('\n').trim();
  const own = section.split(/\r?\n/).filter(l => !l.trim().startsWith('<!-- story-ext:')).join('\n').trim();
  if (body !== own) return null;
  const from = begins[0] > 0 && lines[begins[0] - 1] === '' ? begins[0] - 1 : begins[0];
  return [...lines.slice(0, from), ...lines.slice(ends[0] + 1)].join('\n');
}

function bridgeArtifacts(ctx, skills) {
  const { native, adapters, extDir } = ctx;
  const bridge = native.module('scripts/utils/instance-skill-bridge.ts');
  return adapters.flatMap(adapter => bridge.inspectInstanceSkillBridgeArtifacts({
    repoRoot: native.root, frameworkDir: native.frameworkRoot, agentAdapter: adapter,
    extensionDirRel: extDir, declaredSkillIds: skills,
  }));
}

/**
 * 待装的扩展在替换之前用目标 Framework 的原生加载器核一遍：manifest 合法，登记的 Skill、钩子、规则覆盖、资产、
 * 知识与阶段绑定都在。`fill(extDir)` 把待装内容摆进临时工程的扩展目录；临时工程带目标的配置，阶段名按目标的 workflow 核。
 */
export function candidateProblems(root, fill) {
  const native = loadNative(root);
  const { loadFrameworkConfigWithSources } = native.module('config.ts');
  const extDir = loadFrameworkConfigWithSources(native.root).config.paths?.extension_dir ?? 'doc/extensions';
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'story-candidate-'));
  try {
    fs.copyFileSync(path.join(native.root, 'framework.config.json'), path.join(stage, 'framework.config.json'));
    const at = path.join(stage, ...extDir.split('/'));
    fs.mkdirSync(at, { recursive: true });
    fill(at);
    const bundle = native.module('extension-loader.ts').loadInstanceExtensions(stage, extDir, { frameworkRoot: native.frameworkRoot });
    return bundle.errors.map(e => `待装 manifest：${e.code} ${e.message}`.replaceAll(stage, '<待装>'));
  } finally {
    fs.rmSync(stage, { recursive: true, force: true });
  }
}

/** 写前核（只读）：返回要退出的旧入口与冲突。 */
export function entryPlan(root, skills) {
  const ctx = context(root);
  const { native, extRoot } = ctx;
  const retire = [];
  const conflicts = [];
  const installed = read(path.join(extRoot, 'manifest.yaml'));
  const old = installed ? native.require('yaml').parse(installed.toString('utf8')) ?? {} : {};
  for (const item of old.provides?.bridges ?? []) {
    const target = path.join(native.root, ...String(item?.target ?? '').split('/'));
    const current = read(target);
    if (current === null) continue;
    const source = read(path.join(extRoot, ...String(item?.source ?? '').split('/')));
    if (source !== null && current.equals(source)) retire.push(item.target);
    else conflicts.push(`${item.target}：与已装版本登记的入口源不同（改过或源已缺失），保留不动`);
  }
  const section = read(path.join(extRoot, ...OLD_SECTION.split('/')));
  const entries = renderedEntries(ctx);
  for (const { target, rendered } of entries) {
    const current = read(path.join(native.root, target));
    if (current === null) continue;
    const kept = withoutOldZone(lf(current.toString('utf8')), section === null ? null : section.toString('utf8'));
    if (kept === null) conflicts.push(`${target}：扩展段与已装版本不符或标记不成对，原生物化会整份重写它`);
    else if (kept !== rendered) conflicts.push(`${target}：有原生生成之外的内容，原生物化会整份重写它`);
  }
  for (const a of bridgeArtifacts(ctx, skills)) {
    if ((a.state === 'unowned' || a.state === 'drifted') && !retire.includes(a.path)) {
      conflicts.push(`${a.path}：本次要物化的 Skill 入口位置上已有${a.state === 'unowned' ? '无归属' : '被改过'}的文件`);
    }
  }
  return { retire, conflicts: [...new Set(conflicts)], entries: entries.map(e => e.target) };
}

/** 写后核（只读）：manifest 合法、入口文件等于原生渲染、每个 Skill 入口至少一个宿主判为 present 且无异常态。 */
export function entryCheck(root) {
  const ctx = context(root);
  const { native } = ctx;
  const inspect = native.module('scripts/utils/extension-inspect.ts')
    .inspectInstanceExtensions(native.root, native.frameworkRoot);
  const problems = inspect.manifestErrors.map(e => `manifest：${e.code} ${e.message}`);
  for (const { target, rendered } of renderedEntries(ctx)) {
    const current = read(path.join(native.root, target));
    if (current === null || lf(current.toString('utf8')) !== rendered) problems.push(`${target}：与原生渲染不同`);
  }
  const states = new Map();
  for (const row of inspect.rows.filter(r => r.type === 'bridge')) {
    states.set(row.source, [...(states.get(row.source) ?? []), row.status]);
  }
  // 共用同一目录的两个宿主（F5）会让原生对其中一方持续判 stale：同一路径已有宿主判 present 时入口可用，
  // stale 作为已知限制留在 warnings 里，不当作各宿主都核对通过
  const warnings = [];
  for (const [p, list] of states) {
    const bad = list.filter(s => !['present', 'stale'].includes(s));
    if (bad.length || !list.includes('present')) problems.push(`${p}：入口状态 ${list.join('/')}`);
    else if (list.includes('stale')) warnings.push(`${p}：入口状态 ${list.join('/')}（共用目录的宿主互相改写，Framework 已知限制）`);
  }
  for (const f of inspect.findings.filter(f => f.code === 'extension_bridge_adapter_unsupported')) problems.push(f.message);
  return { problems, warnings };
}

/**
 * 退出已核的旧入口 → 原生物化 → 写后核。
 *
 * 写入与删除按本次覆盖面的前后字节算，原生中途抛错也照样核：共用同一目录的两个宿主会各写一遍同一入口
 * （字节不变也报写入），不据原生报告说「改了」；抛错时已经写出或删掉的入口照实列出，原始错误原样保留。
 */
export function entryMaterialize(root, retire) {
  const ctx = context(root);
  const { native } = ctx;
  const installed = read(path.join(ctx.extRoot, 'manifest.yaml'));
  const skills = installed ? native.require('yaml').parse(installed.toString('utf8'))?.provides?.skills ?? [] : [];
  const watched = [...renderedEntries(ctx).map(e => e.target), ...bridgeArtifacts(ctx, skills).map(a => a.path), ...retire];
  const at = p => path.join(native.root, ...p.split('/'));
  const before = new Map(watched.map(p => [p, read(at(p))]));
  const rel = p => (path.isAbsolute(p) ? path.relative(native.root, p).split(path.sep).join('/') : p);
  let reported = [];
  let error = null;
  try {
    for (const p of retire) if (fs.existsSync(at(p))) fs.rmSync(at(p));
    const result = native.module('scripts/extension.ts').materializeExtensions(native.root, native.frameworkRoot);
    reported = [...result.entryFilesWritten, ...result.bridges.flatMap(b => [...(b.filesWritten ?? []), ...(b.filesRemoved ?? [])])].map(rel);
  } catch (e) {
    error = e;
  }
  const written = [];
  const removed = [];
  for (const p of new Set([...watched, ...reported])) {
    const was = before.get(p) ?? null;
    const now = read(at(p));
    if (now && !(was && was.equals(now))) written.push(p);
    else if (!now && was) removed.push(p);
  }
  if (error) return { written, removed, problems: [`原生物化失败：${error?.message ?? error}`], warnings: [] };
  return { written, removed, ...entryCheck(root) };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };
  const list = k => (opt(k) ?? '').split(',').map(s => s.trim()).filter(Boolean);
  const root = opt('--project-root');
  const action = opt('--action');
  try {
    if (!root || !['plan', 'materialize', 'check'].includes(action)) {
      throw new Error('用法：--project-root <工程根> --action plan --skills a,b | materialize --retire p,q | check');
    }
    const out = action === 'plan'
      ? { ...entryPlan(root, list('--skills')),
        problems: opt('--candidate') ? candidateProblems(root, dir => fs.cpSync(path.resolve(opt('--candidate')), dir, { recursive: true })) : [] }
      : action === 'materialize' ? entryMaterialize(root, list('--retire')) : entryCheck(root);
    process.stdout.write(`${JSON.stringify(out, null, 1)}\n`);
    process.exitCode = [...(out.conflicts ?? []), ...(out.problems ?? [])].length ? 1 : 0;
  } catch (e) {
    process.stderr.write(`[entries] ${e?.message ?? e}\n`);
    process.exitCode = 2;
  }
}
