/**
 * 成文的设计来源：与需求同根的蓝图（标识就是需求标识；原生 draft 读取、需求条目采用了本需求的材料版本、
 * 评审投影对得上这一版）与它采用的来源。
 *
 * 附录机器区、术语起始行与材料清单都从这里取，Story 不再读 Spec。草稿可以成文：准入状态与原生 issues 原样带出，
 * 由作者、独立审查与交付说明照实披露——草稿可读不等于准入通过。来源不成立（读不到、坏身份、没采用本需求来源、投影过期）
 * 时给出缺口与责任方，调用方按它停下——不拿空来源当「这一节不涉及」。同一条命令只读一次。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { adoptedSources, readBlueprint, readSourceFiles, relatedStories, sourcesIdentity } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot } from '../../../../../hooks/shared/paths.mjs';
import { ledgerDigestProblems, readJson, readText, requirementContext } from './context.mjs';

const sha256 = (data) => crypto.createHash('sha256').update(data).digest('hex');

const cache = new WeakMap();

/**
 * @returns {{blueprint: object|null, ref: object|null, projection?: string, canonical?: string, admitted?: boolean,
 *   nativeIssues?: string[], adopted: object|null, problems: string[]}}
 *   `projection` 是原生评审投影、`canonical` 是蓝图本体的工程相对路径；`admitted` 与 `nativeIssues` 是原生读取的准入结论与问题；
 *   `adopted` 是蓝图采用的来源（`adoptedSources`），其中本需求的那一份在 `adopted.own`
 */
export function designSource(ctx) {
  if (cache.has(ctx)) return cache.get(ctx);
  const problems = [];
  const id = ctx.args.feature;
  const out = { blueprint: null, ref: null, adopted: null, problems };
  const read = fs.existsSync(path.join(ctx.featureRoot, 'blueprint', 'component-blueprint.yaml'))
    ? readBlueprint(ctx.projectRoot, id, 'draft', id) : { status: 'missing' };
  if (read.status === 'missing') {
    problems.push(`蓝图 ${id} 还没建立——成文按与需求同根的蓝图写，先在 component-design 里按 sources/ 的材料版本完成设计`);
  } else if (read.status !== 'ok') {
    problems.push(`蓝图 ${id}：原生读取 ${read.status}`
      + `${read.issues?.length ? `（${read.issues.slice(0, 3).map(i => i.code ?? i.id).join('、')}）` : ''}`
      + '——由设计职责在 component-design 里修好蓝图');
  } else if (read.consumption?.status !== 'ok') {
    problems.push(`蓝图 ${id} 的需求条目没有采用本需求的来源：`
      + `${(read.consumption?.issues ?? []).map(i => i.message).join('；')}——由设计职责在 component-design 里按 sources/ 的材料版本同步需求条目`);
  } else if (read.projection?.status !== 'valid') {
    problems.push(`蓝图 ${id} 的评审投影 ${read.projection?.path}`
      + `${read.projection?.status === 'missing' ? '还没生成' : '与当前 revision 对不上'}——由设计职责按原生 renderer 生成，Extension 不手改`);
  } else {
    const adopted = adoptedSources(ctx.projectRoot, read.blueprint);
    out.blueprint = read.blueprint;
    out.ref = read.blueprint_ref;
    out.projection = read.projection.path;
    out.canonical = read.canonical_path;
    out.admitted = read.admitted === true;
    out.nativeIssues = (read.issues ?? []).map(i => `${i.code ?? i.id ?? 'issue'}${i.path ? ` @${i.path}` : ''}：${i.message ?? ''}`);
    out.adopted = { ...adopted, own: adopted.requirements.find(r => r.requirement === id) ?? null };
  }
  cache.set(ctx, out);
  return out;
}

/**
 * 蓝图的准入状态与原生问题，一行结论加逐条问题：作者任务、独立审查任务与交付说明照这一份披露。
 * 设计来源不成立时为空（那时调用方报的是缺口）。
 */
export function designStatusLines(source) {
  if (!source?.ref) return [];
  const head = `蓝图 ${source.ref.blueprint_id} r${source.ref.revision}：${source.admitted ? '已准入' : '草稿，未准入'}`
    + `；原生问题 ${source.nativeIssues?.length ?? 0} 条`;
  return [head, ...(source.nativeIssues ?? []).map(i => `  - ${i}`)];
}

/** 激活知识的确定性摘要：有序的激活登记（路径、受众、摘要）与每份知识文件的原始字节。 */
function knowledgeDigest(ctx) {
  const rows = knowledgeRegistrations(ctx.projectRoot).map((r) => {
    let bytes = null;
    try {
      bytes = fs.readFileSync(path.join(extensionRoot(ctx.projectRoot), ...r.file.split('/')));
    } catch {
      bytes = null;
    }
    return { file: r.file, audience: r.audience, summary: r.summary, sha256: bytes === null ? null : sha256(bytes) };
  });
  return sha256(JSON.stringify(rows));
}

/**
 * 这一刻的成文依据：设计引用（原生完整 blueprint_ref）、设计采用来源的身份、激活知识。
 * 登记（`story_flow.py story` 经 `story-build basis`）与核对（check、交付门）用同一份计算。
 */
export function currentBasis(ctx) {
  const source = designSource(ctx);
  return {
    problems: source.problems, blueprint_ref: source.ref,
    sources_sha256: source.adopted ? sourcesIdentity(source.adopted.sources) : null, knowledge_sha256: knowledgeDigest(ctx),
  };
}

/** 成文登记之后，设计、采用的来源或知识换了没有——换了的，登记说的就不是现在这份。文件的改动由登记指纹另核。 */
export function basisDriftProblems(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') return [];
  const basis = flow.story_basis;
  if (!basis) {
    return ['AR/story-src/story-flow.json：记着已成文登记，却没有成文依据 story_basis，契约不完整'
      + '——跑 `story_flow.py story --feature <名>` 按当前内容重新登记'];
  }
  const now = currentBasis(ctx);
  if (now.problems.length) return now.problems;
  const again = '——改完先 `story-build review --action prepare` 定稿并重新审查，审查通过后跑 `story_flow.py story` 重新登记';
  const out = [];
  const was = basis.blueprint_ref ?? {};
  const short = sha => String(sha ?? '').replace(/^sha256:/, '').slice(0, 12);
  if (was.revision !== now.blueprint_ref?.revision) {
    out.push(`登记之后蓝图换了版本（登记时 r${was.revision}，现在 r${now.blueprint_ref?.revision}）${again}`);
  } else if (was.artifact_sha256 !== now.blueprint_ref?.artifact_sha256) {
    out.push(`登记之后蓝图内容变了（版本仍是 r${was.revision}，内容摘要 ${short(was.artifact_sha256)} → `
      + `${short(now.blueprint_ref?.artifact_sha256)}）${again}`);
  }
  if (basis.sources_sha256 !== now.sources_sha256) out.push(`登记之后设计采用的来源换了${again}`);
  if (basis.knowledge_sha256 !== now.knowledge_sha256) out.push(`登记之后激活知识或知识原文变了${again}`);
  return out;
}

/**
 * 蓝图里确认过的术语（`subject: term:<术语>` 的事实）：术语连同它的来源交给作者，意思由作者按来源的定义写，
 * 不拿模块名代替。来源取事实的 `provenance.source_ref`；没有来源时这一格写明缺口，定稿前要补上。
 */
export function termFacts(blueprint) {
  return (blueprint?.discovery?.facts ?? [])
    .filter(f => String(f?.subject ?? '').startsWith('term:'))
    .map((f) => {
      const ref = String(f.provenance?.source_ref ?? '').trim();
      return [String(f.subject).slice('term:'.length).trim(),
        ref ? `{{按 ${ref} 的定义写}}` : '{{缺定义与来源：设计负责方在蓝图事实里补来源}}'];
    })
    .filter(([term]) => term);
}

/** 已核字节的来源里的 Markdown：按去掉片段的文件路径给文本（展示投影去 BOM，摘要已按原字节核过）。 */
const markdownOf = files => files.filter(f => /\.md$/i.test(f.file_path))
  .map(f => [f.file_path, f.bytes.toString('utf-8').replace(/^\uFEFF/, '')]);

/**
 * 设计采用的本需求来源还立不立得住：按材料索引登记的摘要核每份采用文件的原始字节。读不到或字节不符的逐份报出，
 * 当前性检查按来源损坏报。设计来源不成立时为空（那时报的是设计来源的缺口）。
 */
function adoptedSourceProblems(ctx) {
  const own = designSource(ctx).adopted?.own;
  if (!own || !ctx.projectRoot) return [];
  return readSourceFiles(ctx.projectRoot, own.files).problems
    .map(p => `采用的材料版本 ${p}——材料版本导入后不改，恢复原件`);
}

/**
 * 这份 Story 现在还是不是成文登记的那一份 —— 与 check、交付门同一组检查：登记的文件指纹、成文依据（蓝图、采用来源、知识）、
 * 采用文件的字节。登记数据缺失或来源坏了是 `broken`（缺口，要报），登记之后改过是 `stale`（旧表达），都不作可复用的已定来源。
 *
 * @returns {{state: 'current'|'stale'|'unwritten'|'broken', why: string[]}}
 */
function storyCurrency(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') {
    return fs.existsSync(ctx.storyPath) ? { state: 'stale', why: ['Story 没有按当前内容成文登记（修订中或还没登记）'] }
      : { state: 'unwritten', why: ['Story 还没写'] };
  }
  const basis = flow.story_basis;
  if (!basis?.files || !basis?.blueprint_ref || !basis?.sources_sha256) {
    return { state: 'broken', why: ['流程契约记着已成文登记，登记数据不完整（缺文件指纹或成文依据）——需求负责方按当前内容重新登记'] };
  }
  const source = [...designSource(ctx).problems, ...adoptedSourceProblems(ctx)];
  if (source.length) return { state: 'broken', why: source };
  const changed = [...ledgerDigestProblems(ctx), ...basisDriftProblems(ctx)];
  return changed.length ? { state: 'stale', why: changed } : { state: 'current', why: [] };
}

/**
 * 施工单位这次能用的来源：蓝图消费的采用来源（按蓝图登记的摘要核过字节），加上当前有效的关联 Story。
 * 关联 Story 由原生来源链定位（`relatedStories`），当前性按 `storyCurrency`；不是当前的 Story 进 `excluded` 并带原因。
 *
 * @param {object|null} blueprint 本命令已读到的蓝图，给了就不再读
 * @returns {{status: string, documents: Map<string,string>, excluded: Map<string,string>, stories: object[],
 *   problems: string[], blueprint?: object}}
 */
export function unitSources(projectRoot, feature, blueprint = null) {
  const related = relatedStories(projectRoot, feature, blueprint);
  const out = { status: related.status, documents: new Map(), excluded: new Map(), stories: [], problems: [...related.problems],
    blueprint: related.blueprint };
  const read = readSourceFiles(projectRoot, related.sources);
  for (const [at, why] of read.excluded) {
    out.problems.push(`采用来源 ${at}：${why}——设计负责方核对`);
    out.excluded.set(at, why);
  }
  for (const [at, text] of markdownOf(read.files)) out.documents.set(at, text);
  for (const r of related.requirements) {
    const ctx = requirementContext(projectRoot, path.join(projectRoot, ...r.root.split('/')));
    const entry = { ...r, ctx, story: `${r.root}/AR/story.md`, ...storyCurrency(ctx) };
    out.stories.push(entry);
    if (entry.state === 'broken') out.problems.push(...entry.why.map(w => `关联需求 ${r.requirement}：${w}`));
    if (entry.state === 'current') out.documents.set(entry.story, readText(ctx.storyPath) ?? '');
    else out.excluded.set(entry.story, entry.why.join('；'));
  }
  return out;
}
