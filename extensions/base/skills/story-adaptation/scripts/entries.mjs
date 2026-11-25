#!/usr/bin/env node
/**
 * 宿主入口交给 Framework 原生物化：init docs.post_check 钩子、写前核、退出旧入口、物化、写后核。
 *
 * Skill 源位于 `<ext>/base/skills/<id>/SKILL.md`，声明清单在 `<ext>/base/package-manifest.yaml > provides.skills`；
 * 业务根 `<ext>/manifest.yaml` 通过 `provides.hooks.docs.post_check` 挂接本模块，项目级 framework-init CREATE/UPDATE
 * 执行全局 docs 检查时直接触发原生桥生成器 `emitInstanceSkillBridge`（扫描目录指向 `<ext>/base`），同时保护其他所有者的有效入口。
 *
 * 用法：node entries.mjs --project-root <工程根> --action plan [--skills a,b] [--candidate <待装扩展目录>] | materialize [--retire p,q] | check
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
const baseRelOf = extDir => path.posix.join(extDir, 'base');
const isStorySource = (src, extDir) => src.startsWith(`${extDir}/base/skills/`) || src.startsWith(`${extDir}/skills/`);

function context(root) {
  const native = loadNative(root);
  const { loadFrameworkConfigWithSources } = native.module('config.ts');
  const sources = loadFrameworkConfigWithSources(native.root);
  const raw = sources.projectRaw ?? {};
  const adapters = [...new Set((Array.isArray(raw.materialized_adapters) ? raw.materialized_adapters : [])
    .filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))];
  if (!adapters.length) throw new Error('framework.config.json 的 materialized_adapters 为空：没有要物化的宿主');
  const extDir = sources.config.paths?.extension_dir ?? 'doc/extensions';
  return { native, raw, adapters, extDir, baseRel: baseRelOf(extDir), extRoot: path.join(native.root, ...extDir.split('/')) };
}

/** 从 `<ext>/base/package-manifest.yaml`（缺失回退根 `manifest.yaml`）读本包声明的 Skill ID 列表。 */
function packageSkills(extRoot, YAML) {
  for (const rel of [path.join('base', 'package-manifest.yaml'), 'manifest.yaml']) {
    const raw = read(path.join(extRoot, rel));
    if (!raw) continue;
    const list = YAML.parse(raw.toString('utf8'))?.provides?.skills;
    if (Array.isArray(list)) return list.filter(s => typeof s === 'string' && s.trim());
  }
  return [];
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
    rendered: lf(tr.renderAgentsTemplate(template, tr.buildAgentsTemplateVars(raw, {
      entryFile: target, projectRoot: native.root, frameworkRoot: native.frameworkRoot,
    }))),
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
  const { native, adapters, baseRel } = ctx;
  const bridge = native.module('scripts/utils/instance-skill-bridge.ts');
  return adapters.flatMap(adapter => bridge.inspectInstanceSkillBridgeArtifacts({
    repoRoot: native.root, frameworkDir: native.frameworkRoot, agentAdapter: adapter,
    extensionDirRel: baseRel, declaredSkillIds: skills,
  }));
}

/** 保护非本包所有者的有效桥：emitInstanceSkillBridge 清理孤儿前先留快照，写后按原字节恢复。 */
function snapshotOtherOwners(ctx, skills) {
  const saved = new Map();
  for (const a of bridgeArtifacts(ctx, skills)) {
    if (a.state === 'orphan' && a.sourceRel && !isStorySource(a.sourceRel, ctx.extDir)) {
      const abs = path.join(ctx.native.root, ...a.path.split('/'));
      const data = read(abs);
      if (data) saved.set(a.path, { abs, data });
    }
  }
  return saved;
}

function restoreOtherOwners(saved) {
  for (const { abs, data } of saved.values()) {
    if (!fs.existsSync(abs)) {
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      fs.writeFileSync(abs, data);
    }
  }
}

/**
 * 项目级 framework-init CREATE/UPDATE 的正式 docs.post_check 钩子入口（S09）。
 * 仅在 init 的全局 docs 阶段运行，普通 docs 检查零写入；把桥扫描目录指向 `<ext>/base`，保留其他所有者的有效入口。
 */
export default function initSkillBridgeHook(hookCtx) {
  if (hookCtx?.feature !== '_global' || hookCtx?.phase !== 'docs' || !process.env.HARNESS_INIT_INTERNAL_GLOBAL_RUN) {
    return { ok: true };
  }
  const ctx = context(hookCtx.projectRoot);
  const skills = packageSkills(ctx.extRoot, ctx.native.require('yaml'));
  if (!skills.length) return { ok: true, message: 'Story base 未声明可物化 Skill' };
  const bridge = ctx.native.module('scripts/utils/instance-skill-bridge.ts');
  const protectedOwners = snapshotOtherOwners(ctx, skills);
  const rows = ctx.adapters.map(agentAdapter => ({
    agentAdapter,
    ...bridge.emitInstanceSkillBridge({
      repoRoot: ctx.native.root, frameworkDir: ctx.native.frameworkRoot,
      extensionDirRel: ctx.baseRel, agentAdapter, declaredSkillIds: skills,
    }),
  }));
  restoreOtherOwners(protectedOwners);
  const issues = rows.flatMap(r => [...(r.driftedFiles ?? []), ...(r.untouchedFiles ?? []), ...(r.warnings ?? [])]);
  return {
    ok: issues.length === 0,
    message: issues.length ? `Story base 桥物化存在冲突或警告：${issues.join('；')}` : `Story base 桥已按 ${ctx.adapters.join(',')} 物化`,
  };
}

/** 待装扩展在替换前用目标 Framework 原生加载器校验。 */
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

/** 写前核（只读）：返回要退出的旧入口、桥目标路径与冲突。 */
export function entryPlan(root, skills = null) {
  const ctx = context(root);
  const { native, extRoot } = ctx;
  const YAML = native.require('yaml');
  const wanted = skills && skills.length ? skills : packageSkills(extRoot, YAML);
  const retire = [];
  const conflicts = [];
  const installed = read(path.join(extRoot, 'manifest.yaml'));
  const old = installed ? YAML.parse(installed.toString('utf8')) ?? {} : {};
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
  const bridgeTargets = [];
  for (const a of bridgeArtifacts(ctx, wanted)) {
    if (a.state === 'orphan' && a.sourceRel && !isStorySource(a.sourceRel, ctx.extDir)) continue;
    bridgeTargets.push(a.path);
    if ((a.state === 'unowned' || a.state === 'drifted') && !retire.includes(a.path)) {
      conflicts.push(`${a.path}：本次要物化的 Skill 入口位置上已有${a.state === 'unowned' ? '无归属' : '被改过'}的文件`);
    }
  }
  return { retire, conflicts: [...new Set(conflicts)], entries: entries.map(e => e.target), bridges: [...new Set(bridgeTargets)] };
}

/** 写后核（只读）：根 manifest 合法、入口文件等于原生渲染、base/skills 桥全部 present 且无本包孤儿。 */
export function entryCheck(root, skills = null) {
  const ctx = context(root);
  const { native, extRoot } = ctx;
  const wanted = skills && skills.length ? skills : packageSkills(extRoot, native.require('yaml'));
  const inspect = native.module('scripts/utils/extension-inspect.ts')
    .inspectInstanceExtensions(native.root, native.frameworkRoot);
  const problems = inspect.manifestErrors.map(e => `manifest：${e.code} ${e.message}`);
  for (const { target, rendered } of renderedEntries(ctx)) {
    const current = read(path.join(native.root, target));
    if (current === null || lf(current.toString('utf8')) !== rendered) problems.push(`${target}：与原生渲染不同`);
  }
  const states = new Map();
  for (const a of bridgeArtifacts(ctx, wanted)) {
    if (a.state === 'orphan' && a.sourceRel && !isStorySource(a.sourceRel, ctx.extDir)) continue;
    states.set(a.path, [...(states.get(a.path) ?? []), a.state]);
  }
  const warnings = [];
  for (const [p, list] of states) {
    const bad = list.filter(s => !['present', 'stale'].includes(s));
    if (bad.length || !list.includes('present')) problems.push(`${p}：入口状态 ${list.join('/')}`);
    else if (list.includes('stale')) warnings.push(`${p}：入口状态 ${list.join('/')}（共用目录的宿主互相改写，Framework 已知限制）`);
  }
  for (const f of inspect.findings.filter(f => f.code === 'extension_bridge_adapter_unsupported')) problems.push(f.message);
  return { problems, warnings };
}

/** 退出已核旧入口 → 渲染入口文件 → 调原生桥生成器指向 `<ext>/base`（保护其他所有者）→ 写后核。 */
export function entryMaterialize(root, retire = [], skills = null) {
  const ctx = context(root);
  const { native, extRoot } = ctx;
  const wanted = skills && skills.length ? skills : packageSkills(extRoot, native.require('yaml'));
  const bridge = native.module('scripts/utils/instance-skill-bridge.ts');
  const protectedOwners = snapshotOtherOwners(ctx, wanted);
  const entries = renderedEntries(ctx);
  const watched = [...entries.map(e => e.target), ...bridgeArtifacts(ctx, wanted).map(a => a.path), ...retire];
  const at = p => path.join(native.root, ...p.split('/'));
  const before = new Map(watched.map(p => [p, read(at(p))]));
  const rel = p => (path.isAbsolute(p) ? path.relative(native.root, p).split(path.sep).join('/') : p);
  let reported = [];
  let error = null;
  try {
    for (const p of retire) if (fs.existsSync(at(p))) fs.rmSync(at(p));
    for (const adapter of ctx.adapters) {
      const r = bridge.emitInstanceSkillBridge({
        repoRoot: native.root, frameworkDir: native.frameworkRoot, agentAdapter: adapter,
        extensionDirRel: ctx.baseRel, declaredSkillIds: wanted,
      });
      reported.push(...(r.filesWritten ?? []), ...(r.filesRemoved ?? []));
    }
    restoreOtherOwners(protectedOwners);
    for (const { target, rendered } of entries) {
      const abs = at(target);
      if (!fs.existsSync(abs) || lf(fs.readFileSync(abs, 'utf8')) !== rendered) {
        fs.mkdirSync(path.dirname(abs), { recursive: true });
        fs.writeFileSync(abs, rendered, 'utf8');
        reported.push(target);
      }
    }
  } catch (e) {
    restoreOtherOwners(protectedOwners);
    error = e;
  }
  const written = [];
  const removed = [];
  for (const p of new Set([...watched, ...reported.map(rel)])) {
    if (protectedOwners.has(p)) continue;
    const was = before.get(p) ?? null;
    const now = read(at(p));
    if (now && !(was && was.equals(now))) written.push(p);
    else if (!now && was) removed.push(p);
  }
  if (error) return { written, removed, problems: [`原生物化失败：${error?.message ?? error}`], warnings: [] };
  return { written, removed, ...entryCheck(root, wanted) };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };
  const list = k => (opt(k) ?? '').split(',').map(s => s.trim()).filter(Boolean);
  const root = opt('--project-root');
  const action = opt('--action');
  try {
    if (!root || !['plan', 'materialize', 'check'].includes(action)) {
      throw new Error('用法：--project-root <工程根> --action plan [--skills a,b] [--candidate <目录>] | materialize [--retire p,q] | check');
    }
    const skills = list('--skills');
    const out = action === 'plan'
      ? { ...entryPlan(root, skills.length ? skills : null),
        problems: opt('--candidate') ? candidateProblems(root, dir => fs.cpSync(path.resolve(opt('--candidate')), dir, { recursive: true })) : [] }
      : action === 'materialize' ? entryMaterialize(root, list('--retire'), skills.length ? skills : null) : entryCheck(root, skills.length ? skills : null);
    process.stdout.write(`${JSON.stringify(out, null, 1)}\n`);
    process.exitCode = [...(out.conflicts ?? []), ...(out.problems ?? [])].length ? 1 : 0;
  } catch (e) {
    process.stderr.write(`[entries] ${e?.message ?? e}\n`);
    process.exitCode = 2;
  }
}
