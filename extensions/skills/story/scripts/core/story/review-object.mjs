/**
 * 独立审查的对象 —— 这一次交给审查者的全部材料，只在这里定义一份。
 *
 * 审查任务列它、原生请求把它作为目标逐字节绑定、材料键由它算、覆盖声明与发现定位对着它核：几处用同一份，审的就是要交付的那一份。
 * 待审的是当前 Story；其余是只读对照，区分**必读**与**绑定按疑点回查**：
 * - 必读（`required_read: true`）：当前 Story、有效人答原话、当轮评审输入与动手前现场、会议原件/纠偏/阅读件、设计采用的必要承诺依据、冲突依据、写作设计与判据；
 * - 绑定按疑点回查（`kind: 'text', read: false`）：未采用库存阅读稿、当前蓝图与评审投影、接口转写与映射、激活知识原文、工程引用文件；
 * - 核在场与摘要（`kind: 'metadata', read: false`）：二进制原件、只取图原件、材料清单与人答记录。
 * 同一路径若兼具更强的必读身份（如有效人答、当轮评审输入或采用依据），取最强阅读义务，不被「未采用库存」降级。
 * 全部已登记原件与库存均保留路径与字节绑定，换版即换材料键、旧 PASS 不可移签；流程契约、登记时刻、审查目录与历史报告不在其中。
 *
 * 比较依据只产生一次（`comparisonContext`）：审查对象的行、读法任务与阶段审查的必审输入都取这一份，不再各自看 `flow.update.open`，
 * 也不各自按目录现状拼一遍。开着的这一轮与已收口的最近有效变更轮是同一份依据——收口只让这一轮从 open 变成 closed，
 * 不把已审过的比较依据移出对象。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readBlueprint } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot, featureRoot, readJsonOrNull } from '../../../../../hooks/shared/paths.mjs';
import { materialSet } from './sources.mjs';
import { requiredAnswers } from './design-source.mjs';
import { requirementContext } from './context.mjs';

const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

/** 审查任务在需求目录里的位置：它也是审查对象的一部分。 */
export const TASK = ['AR', 'story-src', 'review', 'task.md'];

/**
 * 同一审查版本的比较依据：最近一次有效变更轮——开着的这一轮，没有时取 `update.last_closed` 指向的已收口轮。
 *
 * 轮次由 `story-flow.json` 的 `update` 给出；首次 init 没有这类记录时不给比较依据，也不报缺口。
 * 候选记录必须真实存在且状态是 `open` / `closed`：撤回与成文基准不是有效变更轮——撤回时由 `restore`
 * 用现有轮次记录选回仍有效的上一轮并写进 `last_closed`，这里不另扫一轮目录、不复制第二个状态源。
 * 记着轮次而记录读不出、id/状态对不上、before/ 不在时照实报位置，不吞成「没有 update」。
 *
 * 依据取这一轮 record **已经固定的清单与摘要**，不按目录现状重新拼：`owned_before` 是开轮时本扩展文件的
 * 路径 → 摘要，`mirror.path` 下的这一件必须逐字仍是那一份；`review_inputs` 记了摘要的原件同样核 `before/` 里的字节。
 * 审查对象的行与阶段审查的必审输入都取 `${before}/${review_inputs[].path}` 这一份固定件，不取当前收件箱里的同名件：
 * 后来的新版本属于下一次 update，不在本轮核对。
 * 快照生成时被合法改写的只有流程契约（`story-flow.json`：开轮时在镜像里写上 `update.open`），它是流程元数据、
 * 不是动手前的原件，所以不进这份清单；批次回执是评审输入的身份凭据，也不进比较内容。
 * `update-notes` 是这一轮作者的判断：**已收口**的一轮必须有它（close 以它为前提），**还开着**的一轮可以还没写。
 * 缺件或字节不符时给出位置、轮次与恢复来源，并让调用方停下——不以残缺集派新审。
 *
 * 路径相对**需求目录**（与轮次记录的 `mirror.path` 同坐标）。审查对象的行、读法任务与阶段审查的必审输入共用这一份：
 * 收口只改记录状态与完成点，这里取到的 rid、before 原件清单与 notes 路径不变，审过的那一版对象就不换。
 *
 * @returns {{rid: string|null, before: string|null, notes: string|null,
 *   files: string[], inputs: {path: string, sha256: string|null, system_item: string|null}[], problems: string[]}}
 */
export function comparisonContext(projectRoot, feature, flow = null) {
  const root = featureRoot(projectRoot, feature);
  const src = path.join(root, 'AR', 'story-src');
  const state = flow ?? readJsonOrNull(path.join(src, 'story-flow.json'));
  const update = (state && typeof state.update === 'object' && state.update) || {};
  const out = { rid: null, before: null, notes: null, files: [], inputs: [], problems: [] };
  const rid = update.open ? String(update.open) : update.last_closed ? String(update.last_closed) : null;
  if (!rid) return out;
  if (!/^[\w.-]+$/.test(rid)) {
    out.problems.push(`story-flow.json 的 update 轮次 id「${rid}」不是合法的轮次 id`);
    return out;
  }
  // 撤回留下冲突时这一轮仍开着（restore_conflicted），动手前的现场仍是有效依据
  const statuses = update.open ? ['open', 'restore_conflicted'] : ['closed'];
  const rec = readJsonOrNull(path.join(src, 'updates', rid, 'record.json'));
  if (!rec || rec.id !== rid || !statuses.includes(rec.status) || rec.kind === 'story_baseline') {
    out.problems.push(`story-flow.json 记着 update「${rid}」（要 ${statuses.join(' / ')}），但 updates/${rid}/record.json 读不出，`
      + '或它记的 id/状态与它不一致——这一轮缺比较基准，不是没有 update');
    return out;
  }
  const round = path.posix.join('AR', 'story-src', 'updates', rid);
  const mirror = String((rec.mirror && rec.mirror.path) || '');
  if (!mirror.startsWith(`${round}/`) || mirror.split('/').includes('..')) {
    out.problems.push(`${round}/record.json 的 mirror.path「${mirror || '缺失'}」不在这一轮自己的目录下——这一轮缺比较基准`);
    return out;
  }
  const at = rel => path.join(root, ...String(rel).split('/'));
  const digestOf = abs => { try { return sha256(fs.readFileSync(abs)); } catch { return null; } };
  // 恢复来源对两类缺件是同一处：目标仓版本库里这一轮 before/ 的原件
  const recover = `从目标仓版本库里这一轮 ${mirror}/ 的原件恢复同一摘要；恢复不了就停下，不在残缺集上派新审`;
  out.rid = rid;
  out.before = mirror;
  out.notes = `${round}/update-notes.md`;
  // 收口过的这一轮的 notes 是必备义务；还开着的一轮可以还没写（见文末）
  const closedRound = rec.status === 'closed';
  if (!fs.existsSync(at(mirror))) {
    out.problems.push(`${mirror} 不在——这一轮缺比较基准，不是没有 update；${recover}`);
    return out;
  }
  // 一件固定原件：before/ 里的字节必须仍是 record 记的那一份；不在或不同都给出位置、轮次与恢复来源
  const keepsFixed = (path0, want, what) => {
    const got = digestOf(at(path0));
    if (got !== null && want && got.startsWith(want)) return true;
    out.problems.push(got === null
      ? `${path0} 不在：update ${rid} 固定的${what}缺失（记录摘要 ${want.slice(0, 12)}）；${recover}`
      : `${path0} 的字节与 update ${rid} 记录的${what}不同（记录 ${want.slice(0, 12)}，现在 ${got.slice(0, 12)}）：本轮动手前的这一版被改过，新稿改掉了什么核不了；${recover}`);
    return false;
  };
  // 开轮时固定的清单来自 record，不按目录里还剩什么算；快照生成时合法改写的流程契约不在其中
  const fixed = rec.owned_before && typeof rec.owned_before === 'object' && !Array.isArray(rec.owned_before)
    ? rec.owned_before : null;
  if (!fixed) {
    out.problems.push(`${round}/record.json 没有记开轮时的固定清单（owned_before）——这一轮缺比较依据，拿不到「动手前是哪一版」`);
  } else {
    for (const rel of Object.keys(fixed).sort()) {
      const path0 = `${mirror}/${rel}`;
      if (keepsFixed(path0, String(fixed[rel] ?? '').replace(/^sha256:/, ''), '开轮时的这一件原件')) out.files.push(path0);
    }
  }
  // 评审输入原件：record 里记了摘要的逐件核字节；失败/缺失/系统上没有的件没有固定原件，状态由本轮记录说明
  out.inputs = (Array.isArray(rec.review_inputs) ? rec.review_inputs : []).filter(entry => entry && entry.path)
    .map(entry => ({ path: String(entry.path), sha256: entry.sha256 ? String(entry.sha256) : null,
      system_item: entry.system_item ? String(entry.system_item) : null }));
  for (const entry of out.inputs) {
    const want = String(entry.sha256 ?? '').replace(/^sha256:/, '');
    if (want) keepsFixed(`${mirror}/${entry.path}`, want, '评审输入原件');
  }
  if (!out.files.length && !out.problems.length) out.problems.push(`${mirror} 里没有这一轮固定的原件——这一轮缺比较基准`);
  // 已收口的一轮必须有 update-notes（close 的前提）；还开着的一轮可以还没写，不在这里报缺口
  if (closedRound) {
    let bytes = null;
    try { bytes = fs.readFileSync(at(out.notes)); } catch { bytes = null; }
    if (!bytes || !bytes.toString('utf-8').trim()) {
      out.problems.push(`${out.notes} ${bytes ? '是空的' : '不在'}：update ${rid} 已收口，这一轮的变化、依据、决定与不变项应当写在里面；`
        + `从目标仓版本库里这一轮 ${round}/update-notes.md 恢复后再准备审查；恢复不了就停下，不在残缺集上派新审`);
    }
  }
  return out;
}

/**
 * `withTask` 为假时不含审查任务本身（生成任务时列材料用）。`source` 是同一命令已取得的设计来源（`designSource` 的
 * `read` 与 `answers`），给了就用它，不再另读蓝图与人答。
 *
 * 每行带 `kind`（`text` / `image` / `metadata`）与 `required_read`：为真的是业务核查入口（待审件、业务原文与阅读稿、冲突依据、
 * 人答、会议、上游图、写作设计与判据）；为假的 `metadata` 行只核在场与来源摘要（二进制原件、只取图的原件、材料清单本身），
 * 为假的 `text` 行按问题回查（蓝图、原生评审投影、接口转写与映射、知识、设计引用的工程文件）。两类都按字节绑定、进材料键。同一内容的几个路径（图片对象的几个落点）
 * 记进 `alias`：路径 → 规范路径（第一个落点），覆盖、发现定位与图面延期按它归一；内容不同的不互相顶替。
 *
 * @returns {{rows: {path: string, role: 'object'|'source', label: string, kind: string, required_read: boolean}[],
 *   problems: string[], design: {admitted: boolean, issues: object[]}|null, alias: Map<string, string>, read: object,
 *   comparison: object}}
 *   路径相对工程根；缺了该有的材料写进 problems，不当作没有。`design` 是蓝图的原生准入结论与问题（草稿也审），
 *   `read` 是这一次的原生读取结果，任务里的视觉裁定用同一份。`comparison` 是这一次唯一的比较依据
 *   （`comparisonContext` 的结果），读法任务直接用它，不再自己看流程契约的 update 状态。
 */
export function reviewObject(projectRoot, feature, { withTask = true, source = null } = {}) {
  const root = featureRoot(projectRoot, feature);
  const rel = abs => path.relative(projectRoot, abs).split(path.sep).join('/');
  const rows = [];
  const problems = [];
  const alias = new Map();
  const add = (abs, role, label, required = true, { kind = 'text', read = true, canonical = null } = {}) => {
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      const p = rel(abs);
      const seen = rows.find(r => r.path === p);
      if (seen) {
        if (read && !seen.required_read) {
          seen.required_read = true;
          seen.label = label;
        }
      } else rows.push({ path: p, role, label, kind, required_read: read });
      if (canonical && canonical !== p) alias.set(p, canonical);
    } else if (required) problems.push(`${rel(abs)} 读不到（${label}）`);
  };
  const src = path.join(root, 'AR', 'story-src');
  add(path.join(root, 'AR', 'story.md'), 'object', '待审的 Story');
  add(path.join(src, 'story-template.md'), 'source', '作者的写作设计（待核的作者判断）');
  for (const name of ['doc-refresh.md', 'template-adjustments.md', 'meeting-notes.json']) {
    add(path.join(src, name), 'source', name === 'doc-refresh.md' ? '会议之后的当前结果'
      : name === 'meeting-notes.json' ? '会议判断' : '写作设计的调整记录', false);
  }
  // 比较依据只产生一次：审查对象的行与读法任务都取这一份，不再各自看 `flow.update.open`
  const flow = readJsonOrNull(path.join(src, 'story-flow.json'));
  const comparison = comparisonContext(projectRoot, feature, flow);
  problems.push(...comparison.problems);
  // 最近有效变更轮的评审输入原件（系统回流的交付件与本地意见/改稿）：审查要对着人的这一版核 Story 有没有按它改。
  // 本轮固定的那一份是 update 开轮时 before/ 里的快照（有摘要的已由 comparisonContext 逐件核字节）；收件箱里同名件
  // 后来的新版本属于下一次 update，不在本轮核对——Story 任务与阶段审查的必审输入取同一件。
  // 记了摘要的件缺件/字节不符已由 comparison.problems 报出，这里不重复报；没记摘要的件没有可核的原件，缺失要报。
  if (comparison.rid) {
    for (const entry of comparison.inputs) {
      add(path.join(root, ...comparison.before.split('/'), ...entry.path.split('/')), 'source',
        `update ${comparison.rid} 的评审输入原件${entry.system_item ? `（系统 ${entry.system_item}）` : '（本地）'}（本轮固定的 before 版）`,
        !entry.sha256);
    }
  }
  // 每版会议：原文、纠偏留痕与纠偏后的阅读件，核纠偏有没有改了意思
  const meetings = path.join(src, 'meetings');
  if (fs.existsSync(meetings)) {
    for (const stem of fs.readdirSync(meetings).sort()) {
      if (!fs.statSync(path.join(meetings, stem)).isDirectory()) continue;
      for (const version of fs.readdirSync(path.join(meetings, stem)).sort()) {
        const dir = path.join(meetings, stem, version);
        if (!fs.existsSync(path.join(dir, 'raw.md'))) continue;
        add(path.join(dir, 'raw.md'), 'source', '会议原文');
        add(path.join(dir, 'corrections.json'), 'source', '会议纠偏留痕（读会必写，没有纠偏也写 []）');
        add(path.join(dir, 'evidence.md'), 'source', '会议纠偏后的阅读件（`story_flow.py meeting-refresh` 按纠偏生成）');
      }
    }
  }

  // 最近有效变更轮动手前的现场与本轮说明也是对照材料，新稿改掉的旧约束对着它核。
  // 清单来自这一轮 record 固定的 owned_before，不按 before/ 目录里还剩什么算；缺件已由 comparison.problems 报出，
  // 这里不重复报，只把还在的那几件列进对象。还开着的这一轮可以还没写 update-notes，不写成缺件。
  if (comparison.rid) {
    add(path.join(root, ...comparison.notes.split('/')), 'source',
      `update ${comparison.rid} 的变化、依据与不变项（作者的判断）`, false);
    for (const f of comparison.files) {
      add(path.join(root, ...f.split('/')), 'source',
        `update ${comparison.rid} 前的现场 ${f.slice(comparison.before.length + 1)}`, false);
    }
  }
  // 设计采用的来源：与需求同根的蓝图，它的需求条目与设计依据引用的本需求材料版本逐份展开，字节按材料索引登记的摘要核
  const adopted = new Map();            // 采用文件（相对需求目录）→ {sha256, role}
  const conflicted = new Map();         // 冲突依据（没被采用的那一方）→ {sha256, role}
  // 与设计来源同一组参数读
  const read = source?.read ?? readBlueprint(projectRoot, feature, 'draft', feature);
  if (read.status !== 'ok') {
    problems.push(`蓝图 ${feature} 读不到（原生读取 ${read.status}）`);
  } else {
    const found = read.source_index;
    const own = found.requirements[0];
    problems.push(...found.problems);
    if (!own?.versions.length) problems.push('蓝图的需求条目与设计依据没有引用本需求登记的材料');
    const local = f => f.path.slice(own.root.length + 1);
    for (const f of own?.files ?? []) adopted.set(local(f), { sha256: f.sha256.replace(/^sha256:/, ''), role: f.role });
    for (const f of own?.conflictFiles ?? []) conflicted.set(local(f), { sha256: f.sha256.replace(/^sha256:/, ''), role: f.role });
    for (const f of found.projectFiles) {
      add(path.join(projectRoot, ...f.path.split('/')), 'source',
        `设计${f.use === 'conflict' ? '冲突依据' : '依据'}引用的${f.role === 'design_file' ? '设计记录' : '工程文件'} ${f.path}（${f.where}）`, true, { kind: 'text', read: false });
    }
  }
  // 人答原件：独立必读，导出落后于流程记录时报缺口，不拿旧导出顶替
  const answers = source?.answers ?? requiredAnswers(requirementContext(projectRoot, root));
  problems.push(...answers.problems);
  // 材料清单登记的全部原件、阅读稿与图片：没采用的也在，审查要核作者为何排除它
  const set = materialSet({ srcDir: src });
  const manifest = path.join(src, 'materials.json');
  if (set === null) problems.push('AR/story-src/materials.json 不在——材料索引由 `story_flow.py round` 按磁盘现状生成');
  else {
    add(manifest, 'source', '材料清单（原件、阅读稿与图片的登记）', true, { kind: 'metadata', read: false });
    problems.push(...set.gaps);
    for (const p of set.pending) problems.push(`${p} 还在来源收件箱、没导入——先按来源导入规则导入，再准备审查`);
  }
  const at = r => path.join(root, ...String(r).split('/'));
  const bytesOf = abs => { try { return fs.readFileSync(abs); } catch { return null; } };
  // 采用文件的字节要等于材料索引登记的那一版：材料版本导入后不改，不在或字节不同报缺口，不拿同一来源的新版本顶替
  const checkAdopted = (r) => {
    const f = adopted.get(r);
    const bytes = bytesOf(at(r));
    if (f && !(bytes && sha256(bytes) === f.sha256)) {
      problems.push(`设计采用的 ${r}（${f.sha256.slice(0, 12)}）${bytes ? '字节已与登记的那一版不同' : '不在原处'}：这一版来源核不了`);
    }
  };
  for (const o of set?.origins ?? []) {
    const bytes = bytesOf(at(o.path));
    const want = String(o.sha256 ?? '').replace(/^sha256:/, '');
    if (bytes && want && !sha256(bytes).startsWith(want)) {
      problems.push(`原件 ${o.path} 现在的字节与材料清单登记的 ${o.sha256} 不同——登记的那一版不在原处：`
        + '把原件恢复成登记的那一版，或重跑 `story_flow.py round` 按磁盘现状登记后重新准备');
    }
    const readable = Array.isArray(o.readable_paths) ? o.readable_paths : [];
    const pictureOnly = Array.isArray(o.image_paths) && o.image_paths.length;
    if (pictureOnly || !readable.includes(o.path)) {
      // 二进制原件与只取图的原件：核在场与来源摘要，阅读义务在它的阅读稿与抽出的图上
      add(at(o.path), 'source', pictureOnly ? `只取图的原件 ${o.path}（核在场，图逐张在下面）` : `原件 ${o.path}（核在场与来源摘要，正文读它的阅读稿）`,
        true, { kind: 'metadata', read: false });
    }
    if (pictureOnly) continue;
    for (const r of readable) {
      checkAdopted(r);
      const fixed = set.current?.get(r);
      const isAdopted = adopted.has(r) || Boolean(fixed && adopted.has(fixed));
      add(at(r), 'source', adopted.has(r) ? `设计采用的阅读稿 ${r}`
        : fixed && adopted.has(fixed) ? `设计采用的阅读稿 ${r}（设计引用的是它此刻对应的稳定副本 ${fixed}）`
          : `未采用库存阅读稿 ${r}（保留版本绑定，有疑点时回查）`, true, { kind: 'text', read: isAdopted });
    }
  }
  // 设计采用的较早版本与会议纠偏/阅读件：材料清单只列各来源最新的一版原件与阅读稿，采用的那些在这里补齐
  const listed = r => rows.some(x => x.path === rel(at(r)));
  const META = new Set(['original', 'answer_record']);
  const LABEL = { original: '设计采用版本的原件', raw: '设计采用的会议原文', corrections: '设计采用的会议纠偏记录',
    evidence: '设计采用的会议阅读件', answer: '设计引用的人工答复', answer_record: '设计引用的人工答复记录', text: '设计采用的阅读稿' };
  for (const [r, f] of adopted) {
    if (f.role === 'image' || listed(r)) continue;
    checkAdopted(r);
    add(at(r), 'source', `${LABEL[f.role] ?? '设计采用的来源'} ${r}${META.has(f.role) ? '（核在场与来源摘要，正文读它的阅读稿）' : ''}`,
      true, META.has(f.role) ? { kind: 'metadata', read: false } : { kind: 'text' });
  }
  for (const [r, f] of conflicted) {
    if (f.role === 'image' || listed(r)) continue;
    add(at(r), 'source', `冲突依据 ${r}（蓝图登记的冲突一方，没有被采用；核取舍）`, true,
      META.has(f.role) ? { kind: 'metadata', read: false } : { kind: 'text' });
  }
  for (const f of answers.files) {
    add(path.join(projectRoot, ...f.path.split('/')), 'source',
      f.role === 'answer' ? '人答原件（必读：当时的问法与原话）' : '人答原件的记录', true,
      f.role === 'answer' ? { kind: 'text' } : { kind: 'metadata', read: false });
  }
  // 图片按对象列，逐路径按字节认同一内容：同字节的落点是别名（第一个落点作规范路径），内容不同的落点各自核读；未用图按问题回查
  const usedImg = new Set([...(bytesOf(path.join(root, 'AR', 'story.md'))?.toString('utf8') ?? '').matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)].map(x => path.posix.normalize(`AR/${x[1].trim().replace(/\\/g, '/')}`)));
  for (const m of set?.images ?? []) {
    const unused = String(m.unused ?? '').trim();
    const label = `登记的图 ${m.caption || '（没写说明）'}${unused ? `，作者登记不用：${unused}` : ''}`;
    const groups = new Map();           // 内容摘要 → 这份内容的落点
    for (const r of m.paths) {
      const bytes = bytesOf(at(r));
      const digest = bytes ? sha256(bytes) : `missing:${r}`;
      if (!groups.has(digest)) groups.set(digest, []);
      groups.get(digest).push(r);
    }
    [...groups].forEach(([digest, paths], i) => {
      const canonical = rel(at(paths[0]));
      const apart = i ? '；与同条登记的其它落点内容不同，单独核读' : '';
      for (const r of paths) add(at(r), 'source', `${label}（${r}${apart}）`, true, { kind: 'image', canonical, read: !unused || paths.some(p => adopted.has(p) || usedImg.has(p)) });
    });
  }
  for (const [r, f] of adopted) {
    if (f.role === 'image' && !listed(r)) {
      checkAdopted(r);
      add(at(r), 'source', `设计采用的图 ${r}`, true, { kind: 'image' });
    }
  }
  if (read.status === 'ok') {
    add(path.join(projectRoot, ...read.canonical_path.split('/')), 'source',
      `蓝图 r${read.blueprint_ref.revision}（${read.admitted ? '已准入' : '草稿，未准入'}）`, true, { read: false });
    add(path.join(projectRoot, ...read.projection.path.split('/')), 'source',
      '蓝图的原生评审投影（设计参考：业务相关正文与关联对象对照，技术参考区按问题回查）', true, { read: false });
    for (const f of read.source_index.authorityFiles) {
      add(path.join(projectRoot, ...f.path.split('/')), 'source', `蓝图契约段引用的接口转写或映射 ${f.path}（原生逐段核对结构）`,
        true, { read: false });
    }
  }

  const ext = extensionRoot(projectRoot);
  add(path.join(ext, 'manifest.yaml'), 'source', '知识激活清单', true, { kind: 'metadata', read: false });
  for (const r of knowledgeRegistrations(projectRoot)) {
    add(path.join(ext, ...r.file.split('/')), 'source', `激活知识 ${r.file}`, true, { read: false });
  }
  add(path.join(ext, 'skills', 'story', 'contracts', 'story-chapters.json'), 'source', '章节合同');
  add(path.join(ext, 'rules', 'story-reader-rules.yaml'), 'source', '审查判据');
  const object = { rows, problems, alias, read, answers, comparison,
    design: read.status === 'ok' ? { admitted: read.admitted === true, issues: read.issues ?? [] } : null };
  return withTask ? withTaskRow(projectRoot, feature, object) : object;
}

/**
 * 给一份不含审查任务的对象补上任务那一行（紧跟在待审件之后），得到最终的审查对象；任务不在记进 problems。
 * 同一次动作先组装一次对象生成任务，再用它补出最终身份，不为任务另组装一遍。
 */
export function withTaskRow(projectRoot, feature, object) {
  const abs = path.join(featureRoot(projectRoot, feature), ...TASK);
  const p = path.relative(projectRoot, abs).split(path.sep).join('/');
  if (!(fs.existsSync(abs) && fs.statSync(abs).isFile())) return { ...object, problems: [...object.problems, `${p} 读不到（审查任务）`] };
  const rows = [...object.rows];
  const at = rows.reduce((last, r, i) => (r.role === 'object' ? i + 1 : last), 0);
  rows.splice(at, 0, { path: p, role: 'source', label: '审查任务', kind: 'text', required_read: true });
  return { ...object, rows };
}

/**
 * 材料键：对象里每份文件的项目相对路径与原始字节 SHA-256，按路径排序后的摘要。
 * 用来选这一次的报告目录、判重入；它不是原生请求的身份（那由原生 prepare 给出）。
 */
export function materialKey(projectRoot, rows) {
  const files = rows.map(r => [r.path, crypto.createHash('sha256')
    .update(fs.readFileSync(path.join(projectRoot, ...r.path.split('/')))).digest('hex')])
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return crypto.createHash('sha256').update(JSON.stringify(files)).digest('hex');
}
