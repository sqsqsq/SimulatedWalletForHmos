#!/usr/bin/env node
/**
 * story adapt —— 把这套扩展装进一个目标工程，或把已装的升到包的版本。
 *
 * **所有权由目录表达**，不靠推断：
 *   `<ext>/skills/story/scripts/core/`      公共，整份换掉（包里不再有的自然消失）
 *   `<ext>/skills/story/scripts/adapters/`  对接实现；Demo 来源不碰，业务仓之间复刻时覆盖
 *   `<ext>/knowledge/`                      目标的知识，脚本不读不写（适配由模型按方法页做）
 *   `<ext>/manifest.yaml`                   机制登记归包，name / description / 知识清单归目标
 *   `<ext>/adaptation.yaml`                 目标的对接来源与已适配版本，归目标
 *   其余 `<ext>/**`                         机制，整份换掉
 *
 * 宿主入口（各宿主的 Skill 跳板、AGENTS.md / CLAUDE.md）由 Framework 原生物化，见 entries.mjs。
 *
 * 边界这么一分，一个文件归谁看它在哪个目录，没有第三种要模型判断的情形；
 * `--check` 据此核**安装结果**——这个目标现在装的是不是包的这一版。
 * `--mark-adapted` 在各块交回后把目标 `adaptation.yaml` 的 `adapted_for` 写成包的版本——这个值只由脚本写，模型不定。
 * `--status` 只读：版本、按当前游标可推导的跟进条目、知识加载结果与内容摘要，stdout 一份 JSON，不写任何文件。
 *
 * 用法: node adapt-scan.mjs --apply|--check|--mark-adapted|--status --target <目标根> [--package <包根>]
 * 退出: 0 通过（--status：事实读取成功，含未安装）/ 1 核对不符（--status：知识结构自检不通过）/ 2 参数或前置错误
 */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync,
} from 'node:fs';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseYaml } from '../../../hooks/shared/yaml.mjs';
import { shellArg } from '../../story/scripts/core/story/drafts.mjs';
import { candidateProblems, entryCheck, entryMaterialize, entryPlan } from './entries.mjs';

const MODES = ['--apply', '--check', '--mark-adapted', '--status'];

/** 目标仓自己实现的那一层。这个目录整个不在写入面上。 */
const ADAPTERS = 'skills/story/scripts/adapters';
/** 目标的知识：首次与升级都不读不写；首装的清单为空，第一份部件定位知识由模型写。 */
const KNOWLEDGE = 'knowledge';
/** 公共脚本的唯一落点。`scripts/` 这一层除了它与 adapters 不放东西——⑤ 守这条。 */
const SCRIPTS_DIR = 'skills/story/scripts';
const CORE = 'core';
/** 升级演进记录：按扩展版本分节、每条标块，升级后据它列出目标这次要做什么。 */
const CHANGES = 'skills/story-adaptation/reference/upgrade-changes.md';
/** 演进记录的两块；对接层只在目标自己维护对接层时列出。 */
const BLOCKS = ['知识', '对接层'];
/** 目标的适配状态：对接来源（adapters）与已适配版本（adapted_for），归目标。 */
const ADAPTATION = 'adaptation.yaml';
/** 1.x 把这两项写在 manifest 顶层；升级时一次性迁进 adaptation.yaml。 */
const ADAPTATION_KEYS = ['adapters', 'adapted_for'];

const argv = process.argv.slice(2);
const mode = MODES.find(m => argv.includes(m));
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
/**
 * 停下并说清原因。`--status` 的读者是脚本与模型，错误也给 JSON：类别（input / config / package / dependency）
 * 加原话，原话里写着读的是哪个文件、按什么判、怎样恢复；读不出不能变成「什么都没有」的空成功。
 */
const die = (msg, code = 2, category = 'input') => {
  if (mode === '--status') console.log(JSON.stringify({ mode: 'status', error: { category, message: msg } }));
  else console.error(`[adapt-scan] ${msg}`);
  process.exit(code);
};

const read = f => readFileSync(f, 'utf8');
const rel = (base, f) => relative(base, f).split(sep).join('/');
const sha = f => createHash('sha256').update(readFileSync(f)).digest('hex').slice(0, 16);

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
    // 读不出不是「没配置」：扩展落点与需求目录都从它取，静默退回缺省值会让
    // 整个写入面悄悄挪到别的路径上，而 diff 那时看起来一切正常。
    return die(`${f} 读不出（${e.message}）：扩展落点与需求目录都从它取`, 2, 'config');
  }
}
const extDir = root => config(root)?.paths?.extension_dir || 'doc/extensions';
const featuresDir = root => config(root)?.paths?.features_dir || 'doc/features';

/**
 * 递归列文件（相对 base 的 posix 路径），`skip` 里的子树整棵不进。
 *
 * **不进去，而不是进去再筛**：`adapters/` 下躺着目标为对接实现装的 `node_modules`，
 * 走一遍它跟升级要做的事毫无关系，而升级的成本本该只取决于固定机制有多大。
 * 点开头的目录是工作件，`__pycache__` 是跑过脚本就有的字节码——两样都既不入库也不交付。
 */
function walk(dir, base = dir, skip = new Set()) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '__pycache__' || e.name.startsWith('.')) return [];
      if (skip.has(rel(base, f))) return [];
      return walk(f, base, skip);
    }
    return [rel(base, f)];
  });
}

/**
 * 这一次要覆盖的范围：`<ext>/` 下除了知识与（按来源）对接层的一切。
 *
 * **一处生成，四处共用**——写入前检查、复制、清理包里不再有的文件、`--check` 核安装结果，
 * 问的都是同一个「这次该管哪些文件」。各算各的话，解除了复制的过滤而自检还在拦，
 * 或者反过来，都只有跑一遍才发现。
 *
 * `manifest.yaml` 不在其中：它一个文件里同时装着归包的机制登记与归目标的身份和知识清单，
 * 按 `composeManifest` 的规则单独合成。`adaptation.yaml` 整份归目标，也不在其中。
 */
function coveredFiles(root, withAdapters) {
  const skip = new Set(withAdapters ? [KNOWLEDGE] : [KNOWLEDGE, ADAPTERS]);
  return walk(root, root, skip).filter(p => p !== 'manifest.yaml' && p !== ADAPTATION);
}

// ── manifest：机制登记归包，知识激活清单归目标 ───────────────────────────────

/**
 * 抽出 `provides.knowledge:` 那一整段（含它上面的注释块）。
 *
 * 按文本块搬而不是解析后重新序列化：清单里的注释是给下一个维护者读的，
 * 解析再吐一遍会把它们全丢掉，而丢了没人会立刻发现。
 */
function knowledgeBlock(manifestText) {
  const lines = manifestText.split(/\r?\n/);
  const at = lines.findIndex(l => /^ {2}knowledge:/.test(l));
  if (at < 0) return null;
  // 往上收编紧邻的注释块——它讲的是这份清单怎么读
  let from = at;
  while (from > 0 && /^ {2}#/.test(lines[from - 1])) from -= 1;
  let to = at + 1;
  while (to < lines.length && !/^ {2}\S/.test(lines[to])) to += 1;
  // 尾随空行留给下一段
  while (to > at + 1 && lines[to - 1].trim() === '') to -= 1;
  return { from, at, to, text: lines.slice(from, to).join('\n') };
}

/**
 * 合成 manifest：包的为底，知识清单按两态各走各的。
 *
 * 它是写入面上唯一一个「一个文件两种所有权」的地方（§3）：其余键与包相同，
 * `provides.knowledge` 归目标。
 *
 * **升级**：目标现有的清单原样放回——知识激活随目标，不因升级重选。
 * **首次**：空清单。照抄包的清单会登记 Demo 那十几份知识正文，而目标里
 * 一份都没有，`activeKnowledge` 当场报「登记的文件读不到」——新仓装完第一件事是撞墙。
 *
 * **目标登记了空清单，那就是空清单。** 一个还没配置知识的仓是正常状态（`knowledge.mjs`
 * 明确这么读），拿包的清单去补齐等于替它重新激活了一批 Demo 知识——它自己的选择被一次
 * 升级改掉了，而这正是「知识激活随目标」要挡的事。
 *
 * 清单上面的注释块三态都保留：它讲的是这份清单怎么读，与登记了什么无关。
 *
 * `name` 与 `description` 同样归目标（`identity`）：它们说的是**这个仓**叫什么、是什么，
 * 一次升级把它们改成包的，目标就顶着发布源的名字了。`version` 反过来归包——
 * 目标只能从它看出自己拿到的是哪一批产物形态。
 */
function composeManifest(pkgText, tgtText, identity) {
  const lines0 = pkgText.split(/\r?\n/);
  const keep = { ...identity };
  if (tgtText) {
    for (const key of TARGET_OWNED_KEYS) {
      const at = tgtText.split(/\r?\n/).find(l => l.startsWith(`${key}:`));
      if (at) keep[key] = at.slice(key.length + 1).trim();
    }
  }
  // 归目标的键：目标有就用目标的，首次按目标生成；目标没有的，包那一行连同它上面的注释不带过去。
  // 去掉的行先占位成 null，知识清单的行号仍按包原文算，拼好再滤掉。
  const lines = lines0.map((l) => {
    const key = TARGET_OWNED_KEYS.find(k => l.startsWith(`${k}:`));
    if (!key) return l;
    return keep[key] !== undefined ? `${key}: ${keep[key]}` : null;
  });
  lines.forEach((l, i) => {
    if (l !== null || lines0[i] === null) return;
    for (let j = i - 1; j >= 0 && lines[j]?.startsWith('#'); j -= 1) lines[j] = null;
  });
  const join = rows => rows.filter(l => l !== null).join('\n');
  const mine = knowledgeBlock(pkgText);
  if (!mine) return join(lines);
  // 空清单写成 `knowledge: []`：只剩一个 `knowledge:` 在 YAML 里是 null，Framework 判它不是数组
  const withList = items => join([
    ...lines.slice(0, mine.at), items.length ? lines[mine.at] : '  knowledge: []',
    ...items.map(p => `    - ${p}`), ...lines.slice(mine.to),
  ]);
  const merged = (() => {
    if (!tgtText) return withList([]);
    const theirs = knowledgeBlock(tgtText);
    if (!theirs) return withList([]);
    return join([...lines.slice(0, mine.from), theirs.text, ...lines.slice(mine.to)]);
  })();
  return withVersionNotes(merged, tgtText);
}

/** 把 `version:` 上面那段注释换成目标自己的（首次安装时目标没有，那里就干净一行）。 */
function withVersionNotes(composed, tgtText) {
  const mine = versionNotes(composed);
  if (!mine) return composed;
  const theirs = tgtText ? versionNotes(tgtText) : null;
  const lines = composed.split(/\r?\n/);
  return [...lines.slice(0, mine.from), ...(theirs?.lines ?? []), ...lines.slice(mine.at)]
    .join('\n');
}

/**
 * manifest 里归目标的键：这个仓叫什么、是什么。升级不改，首次按目标仓生成；目标没写的不从包里带过去。
 */
const TARGET_OWNED_KEYS = ['name', 'description'];

/**
 * `version:` 上面那一段注释 —— 返回它的范围与内容。
 *
 * 发布包在那里记自己的演进（哪一版改了什么产物形态），那是**这个包的历史**，对装它的
 * 工程没有意义：搬过去只会把目标写在同一处的话盖掉，而目标想说的多半是「我们这个仓
 * 怎么用它」。所以这一段与 `name` / `description` 同类，归目标。
 */
function versionNotes(text) {
  const lines = text.split(/\r?\n/);
  const at = lines.findIndex(l => l.startsWith('version:'));
  if (at < 0) return null;
  let from = at;
  while (from > 0 && lines[from - 1].startsWith('#')) from -= 1;
  return { from, at, lines: lines.slice(from, at) };
}

/**
 * 取 manifest 顶层某个键的**值**，不是它那一行的字面。
 *
 * `adapters: stand-in` 与 `adapters: "stand-in"` 在 YAML 里是同一个值，行尾
 * 跟个注释也一样。拿字面去比，加一对引号就会把替身包判成业务仓——而那一判之下
 * `--apply` 会把目标的真实现覆盖成替身，退出码还是 0。所以这里走真正的解析器。
 */
function manifestValue(manifestText, key) {
  try {
    const v = parseYaml(manifestText)?.[key];
    return typeof v === 'string' ? v : null;
  } catch {
    return null;
  }
}

/**
 * 首次安装时这个仓叫什么、是什么。
 *
 * 从目标的 `framework.config.json > project_name` 派生——那是它自己登记的工程名，
 * 拿它当初值是可核实的事实，不是编的。描述由模型在首次那一次确认里改准（SKILL §3）：
 * 脚本知道这个仓叫什么，不知道它是干什么的。
 */
function freshIdentity(root) {
  const project = config(root)?.project_name || '目标工程';
  return {
    name: slugOf(project),
    description: `${project} 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）`,
  };
}

/** Framework manifest 1.1 的 name 规则：小写字母开头，只含小写字母、数字、`_`、`-`。 */
const SLUG = /^[a-z][a-z0-9_-]*$/;

/** 工程名转成 name：驼峰拆开、转小写、其余字符并成 `-`；转不出字母开头的名字时用 story-extension。 */
function slugOf(project) {
  const s = String(project).replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-').replace(/^[-_]+|[-_]+$/g, '');
  return SLUG.test(s) ? s : 'story-extension';
}

/** 读一份 adaptation.yaml：映射，只有 adapters / adapted_for 两个可选字符串。不合规抛错。 */
function parseAdaptation(file) {
  const doc = parseYaml(read(file));
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) throw new Error(`${file} 要是映射`);
  for (const k of Object.keys(doc)) if (!ADAPTATION_KEYS.includes(k)) throw new Error(`${file} 有不认识的键：${k}`);
  for (const k of ADAPTATION_KEYS) {
    if (doc[k] !== undefined && typeof doc[k] !== 'string') throw new Error(`${file} 的 ${k} 要是字符串`);
  }
  return doc;
}

/**
 * 目标这一次之后的适配状态。已有 adaptation.yaml 就读它、文件不动；1.x 升级时从旧 manifest 一次性迁两项；
 * 首次为空映射。旧 manifest 与已有文件对同一项写了不同的值，写前停，由人定用哪一个。
 */
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

// ── 写入面 ──────────────────────────────────────────────────────────────────

/**
 * 目标 `.gitignore` 还缺哪几行。
 *
 * 要挡的是不入库的工作件：章草稿目录、使用记录的一次性输入与本地运行态、记录器的锁与临时文件。
 *
 * **先问 git 它是不是已经被挡住了**：需求目录整个不入库是常见做法（`doc/features/`
 * 一行就盖住了它下面的一切），那时再加一条只是噪声——一条永远不起作用的规则，
 * 下一个维护者还得花时间弄清它为什么在。
 *
 * 问 git 而不是自己比对模式：两条模式等不等价，字符串比不出来。目标不是 git 仓时
 * 按「没挡住」处理，照常补。
 */
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

/** 使用记录被哪条忽略规则挡住（来源:行号:模式），没挡住为空串——它归目标，要能随普通 git add 入库。 */
function usageBlockedBy(root) {
  const r = git(root, ['check-ignore', '-v', '--no-index', USAGE.record]);
  const rule = r.ok ? r.out.trim().split('\t')[0] : '';
  return rule.split(':').slice(2).join(':').startsWith('!') ? '' : rule;   // 最后命中的是放行规则就没挡住
}

/**
 * 这条路径这一次写不写得。**与 `coveredFiles` 同一个边界**，只是换个问法：
 * 那个答「要覆盖哪些」，这个答「某一条在不在覆盖范围里」。写入前查工作区脏不脏用它。
 */
function inWriteFace(root, p, entries, withAdapters) {
  if (p === '.gitignore' || entries.includes(p)) return true;
  const ext = extDir(root);
  if (!p.startsWith(`${ext}/`)) return false;
  const inner = p.slice(ext.length + 1);
  if (inner.startsWith(`${KNOWLEDGE}/`)) return false;
  if (!withAdapters && inner.startsWith(`${ADAPTERS}/`)) return false;
  return true;
}

/**
 * 使用记录归目标、由记录器（story 的 usage.py）唯一写：这里只经扩展里的桥接调它。
 * `ensure` 缺了建空表、在了只校验；`inspect` 只读。`root` 是哪一份扩展的桥接（包或目标已装的）。
 */
async function usageWriter(root, action) {
  const bridge = join(root, 'hooks', 'shared', 'usage.mjs');
  if (!existsSync(bridge)) return { ok: false, errors: [`没有使用记录桥接 ${relative(TARGET, bridge)}`] };
  process.env.PYTHONDONTWRITEBYTECODE = '1';     // 记录器不在目标的机制目录里留字节码，下一次 --apply 的写入面才是干净的
  try {
    return (await import(pathToFileURL(bridge).href)).recordUsage(TARGET, action);
  } catch (e) {
    return { ok: false, errors: [`使用记录桥接加载失败（${e?.message ?? e}）`] };
  }
}

/** apply 收尾：确保目标有可入库的使用记录。返回 {ok, lines}；失败时机制已写完的事实由调用方照常报出。 */
async function ensureUsage() {
  const r = await usageWriter(TDIR, 'ensure');
  const still = usageBlockedBy(TARGET);
  const lines = [];
  if (r.ok) {
    lines.push(r.changed
      ? `[adapt-scan] 已建立使用记录 ${USAGE.record}（schema ${USAGE.schema}，还没有需求）：它归目标，与这次升级改动一起提交`
      : `[adapt-scan] 使用记录 ${USAGE.record} 已在且合法，保留未动`);
  } else {
    lines.push(`[adapt-scan] 使用记录 ${USAGE.record} 没有建立（${(r.errors ?? []).join('；')}）。机制文件已按上面写完，不用重跑 --apply；`
      + '修好原因后只补这一份（下面一行原样复制，在哪个目录跑都行，-B 不留字节码），补完再跑 --check：');
    lines.push(`  echo '{"action":"ensure"}' | python -B ${shellArg(join(TDIR, 'skills', 'story', 'scripts', 'core', 'usage.py'))}`
      + ` --project-root ${shellArg(TARGET)}`);
  }
  if (still) {
    lines.push(`[adapt-scan] ${USAGE.record} 仍被 ${still} 挡住，使用记录进不了库：`
      + '放行它的父路径与这个文件（其余过程目录保持忽略），或按规则来源找它的维护者；未解决前适配不算完成');
  }
  return { ok: r.ok && !still, lines };
}

// ── git ─────────────────────────────────────────────────────────────────────

function git(root, args) {
  const r = spawnSync('git', ['-C', root, ...args], { encoding: 'utf8' });
  return { ok: r.status === 0, out: r.stdout || '', err: (r.stderr || '').trim() };
}
/**
 * 目标**自己**是不是一个 git 仓库的根。
 *
 * 不用 `--is-inside-work-tree`：目标躺在别的 git 仓里面时它也答「是」，而那时
 * `git status` 报的路径相对的是**外层仓的根**，拿去跟写入面（相对目标根）比会全对不上。
 */
function isRepo(root) {
  const r = git(root, ['rev-parse', '--show-toplevel']);
  return r.ok && resolve(r.out.trim()) === resolve(root);
}

/**
 * 工作区里有未提交改动的路径（相对仓库根）。
 *
 * `-uall` 把未跟踪的目录展开成文件：不展开的话 git 只报一个目录名（`?? .claude/`），
 * 而首次安装写进去的跳板恰好都在未跟踪目录里——判据会拿目录名去比路径，一条也对不上。
 *
 * **不 trim 整段输出**：porcelain 的状态位占两格，未暂存的改动第一格是空格
 * （` D path`），整段 trim 会削掉第一行那个空格，之后每条路径都少一个字符。
 */
function dirtyPaths(root) {
  const r = git(root, ['status', '--porcelain', '-uall']);
  if (!r.ok) return [];
  return r.out.split(/\r?\n/).filter(Boolean)
    .map(l => l.slice(3).split(' -> ').pop().replace(/^"|"$/g, ''));
}

// ── 参数与两态 ──────────────────────────────────────────────────────────────

if (!mode) die(`缺模式：${MODES.join(' | ')}`);
if (!opt('--target')) die('缺 --target <目标根>');
const TARGET = findRoot(opt('--target'));
if (!TARGET) die(`目标不是有效仓库根（找不到 framework.config.json）：${opt('--target')}`);
const PKG = opt('--package')
  ? findRoot(opt('--package'))
  : findRoot(dirname(fileURLToPath(import.meta.url)));
if (!PKG) die('包不是有效仓库根（找不到 framework.config.json）');

const PDIR = join(PKG, ...extDir(PKG).split('/'));
//: 使用记录合同（story 包里的那一份）：记录位置、一次性输入文件名
const USAGE = JSON.parse(read(join(PDIR, 'skills', 'story', 'contracts', 'usage.json')));
const TDIR = join(TARGET, ...extDir(TARGET).split('/'));
// 目标关掉了 Framework 生命周期钩子：阶段钩子（含使用记录采集）不执行。这是目标自己的决定，adapt 不改它，
// --apply 与 --check 都把这个限制说出来，不拿「机制面装对了」代替「采集能成立」。
const HOOKS_OFF = config(TARGET)?.lifecycle_hooks_enabled === false
  ? '[adapt-scan] 采集限制：目标 framework.config.json 的 lifecycle_hooks_enabled 是 false，Framework 不执行扩展的阶段钩子，'
    + `直接走 Framework 阶段的使用不会记进 ${USAGE.record}（Story 命令照常记）；`
    + '恢复采集要把它改成 true 或删掉这个键（Framework 默认开启）'
  : null;

// 扩展的 YAML 读取借目标 framework harness 的 `yaml` 包（hooks/shared/yaml.mjs）：装之前先确认它在。
// 缺了也能把文件复制过去，但目标跑第一道门禁就会抛「读取器不可用」——那时人看到的是门禁坏了，不是没装依赖。
// 只在目标**有** harness 时核：harness 本身不在是 framework 还没接入，那是 framework-init 的事，这里只提一句。
{
  const harness = join(TARGET, 'framework', 'harness');
  const yamlPkg = join(harness, 'node_modules', 'yaml');
  if (!existsSync(join(harness, 'package.json'))) {
    console.error(`[adapt-scan] 目标还没有 ${relative(TARGET, harness)}：扩展的门禁要在接入 framework 并装好 harness 依赖之后才能跑`);
  } else if (!existsSync(yamlPkg)) {
    die(`目标的 framework harness 还没装依赖（缺 ${relative(TARGET, yamlPkg)}）：`
      + '先在目标里跑 `cd framework/harness && npm install`，再 --apply / --check', 2, 'dependency');
  }
}
const SAME_TREE = resolve(PKG) === resolve(TARGET);

const pkgManifest = join(PDIR, 'manifest.yaml');
if (!existsSync(pkgManifest)) die(`包里没有 manifest.yaml：${pkgManifest}`, 2, 'package');
const PKG_MANIFEST_TEXT = read(pkgManifest);
/** 包登记的 Skill：宿主入口由 Framework 按它物化。 */
const PKG_SKILLS = (() => {
  try {
    const skills = parseYaml(PKG_MANIFEST_TEXT)?.provides?.skills ?? [];
    return skills.filter(s => typeof s === 'string');
  } catch (e) {
    return die(`包的 manifest.yaml 读不出（${e.message}）`, 2, 'package');
  }
})();
const PKG_VERSION = manifestValue(PKG_MANIFEST_TEXT, 'version');

const tgtManifest = join(TDIR, 'manifest.yaml');
/**
 * 目标升级前装的是哪一版：写目标之前读，写完 `version` 就是包的了。版本事实与 mark 前核安装版本用它；
 * 演进条目按目标的 `adapted_for` 列。
 */
const INSTALLED = existsSync(tgtManifest) ? manifestValue(read(tgtManifest), 'version') ?? '0' : null;
/** 两态，就这一条判据：目标有没有 manifest.yaml。历史版本识别不存在于本实现。 */
const STATE = existsSync(tgtManifest) ? 'upgrade' : 'fresh';

/**
 * 这一次带不带对接层。
 *
 * 包 `adaptation.yaml` 的 `adapters: stand-in` 说明包里的对接实现是替身（用本地目录模拟需求系统），
 * 复制到业务仓等于把人家的真实现盖掉；没有这个键的包是业务仓，共用同一套对接实现，复刻时带上。
 * 这个文件归目标、升级不改，所以每个仓说的都是它自己的对接层。
 */
const WITH_ADAPTERS = (() => {
  const file = join(PDIR, ADAPTATION);
  if (!existsSync(file)) return die(`包里没有 ${ADAPTATION}：判不出对接实现是不是替身`, 2, 'package');
  try {
    return parseAdaptation(file).adapters !== 'stand-in';
  } catch (e) {
    return die(`包的 ${e.message}`, 2, 'package');
  }
})();
/** 目标这一次之后的适配状态（写目标前算好，冲突在这里停）。 */
const TARGET_ADAPTATION = targetAdaptation(TDIR, tgtManifest);

/**
 * 包的升级演进记录逐条读出（版本、块、正文）。启动时就读：包里这份坏了是包的问题，
 * 在写目标之前报出来，不在写完之后。
 */
function changeEntries() {
  const file = join(PDIR, ...CHANGES.split('/'));
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
const CHANGE_ENTRIES = changeEntries();

/** 版本号按数字逐段比较。 */
const newer = (a, b) => {
  const x = String(a).split('.').map(Number);
  const y = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) > (y[i] ?? 0);
  }
  return false;
};

/** 当前激活知识的内容摘要：清单里每份知识的路径与内容（换行归一），独审证据按它对得上当前知识。 */
function knowledgeDigest(files) {
  const h = createHash('sha256');
  for (const f of files) {
    const abs = join(TDIR, ...f.split('/'));
    h.update(f).update('\0').update(existsSync(abs) ? read(abs).replace(/\r\n/g, '\n') : '').update('\0');
  }
  return `sha256:${h.digest('hex').slice(0, 16)}`;
}

/** 按当前协议加载目标知识：按 kind × form 计数、内容摘要与独审证据，或问题清单。 */
async function knowledgeCheck() {
  try {
    const api = await import(pathToFileURL(join(TDIR, 'hooks', 'shared', 'knowledge.mjs')).href);
    const k = api.activeKnowledge(TARGET);
    const problems = api.selfCheck(TARGET, k);
    if (problems.length) return { status: 'FAIL', problems };
    const files = [...k.facts, ...k.constraints, ...k.patterns].map(x => x.file);
    const counts = {};
    for (const kind of ['facts', 'constraints', 'patterns']) {
      for (const x of k[kind]) counts[`${kind} × ${x.form}`] = (counts[`${kind} × ${x.form}`] ?? 0) + 1;
    }
    // 同用途声明候选：只按 applies_when 去首尾空白后原文相同分组，给独立审查当线索；
    // 不判相似、不影响 PASS，为空也不说明没有重复——重复与否由审查读正文判
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

//: 知识独审报告的四个维度：键名与方法页「逐份核四个维度」一一对应
const REVIEW_DIMENSIONS = ['granularity', 'fact_use', 'duplication', 'coding_boundary'];
//: 每维的合法结论；只有 PASS 与带具体建议的 WARN 算这一维审完
const REVIEW_VERDICTS = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];

/**
 * `.adapt/knowledge-review.md` 里的证据块对不对得上当前知识 —— 只读派生，不是状态。
 *
 * 核：块读得出；`digest` 等于当前激活知识的摘要；激活清单每份都有一行、四个维度都有结论与证据；
 * 没有 FAIL、没有阻断项、没有未核。结构有效不证明审查真由独立执行体做过——那由交回与宿主证据核。
 */
async function knowledgeReview(digest, files) {
  const file = join(TDIR, '.adapt', 'knowledge-review.md');
  if (!existsSync(file)) return { status: 'missing', problems: ['.adapt/knowledge-review.md 不在：还没有独立审查报告'] };
  const { parseYaml: parse } = await import(pathToFileURL(join(TDIR, 'hooks', 'shared', 'yaml.mjs')).href);
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

/**
 * 按版本跟进：演进记录里晚于目标 `adapted_for` 的知识与对接层条目，按块分组，
 * 加上按当前协议加载目标知识的结果。只报事实，问不问人由模型照 SKILL 走。
 *
 * 没有 `adapted_for` 的目标从最早一节（知识基线）列起——首次安装拿到的就是完整的知识主题清单。
 * 包带对接实现时（业务仓来源）对接层已整份换成包的，那一块整块不出现。
 */
async function followUp() {
  const since = TARGET_ADAPTATION.doc.adapted_for ?? '0';
  const items = Object.fromEntries(BLOCKS.filter(b => !(WITH_ADAPTERS && b === '对接层')).map(b => [b, []]));
  for (const e of CHANGE_ENTRIES) {
    if (newer(e.version, since) && items[e.block]) items[e.block].push(`${e.version}：${e.text}`);
  }
  return { since, installed: INSTALLED, items, check: await knowledgeCheck() };
}

/** 把目标 `adaptation.yaml` 的 `adapted_for` 写成包的版本：只改这一行，其余行原样。 */
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

/** 写入后的跟进提示：有条目或知识不合协议就摆出来请模型停一次问人；都空就记下适配版本，只一句。 */
async function printFollowUp() {
  const f = await followUp();
  console.log(`[adapt-scan] 按版本跟进：${JSON.stringify(f)}`);
  if (Object.values(f.items).some(list => list.length) || f.check.status !== 'PASS') {
    console.log('[adapt-scan] 有演进条目或知识不合当前协议：按块摆出来，停一次问人「现在做这些适配吗」；'
      + '选稍后就不写任何东西；选中的知识与对接适配都交回后跑 --mark-adapted');
    return;
  }
  writeAdaptedFor();
  console.log(`[adapt-scan] 目标已按包的版本适配，知识与当前协议一致：adapted_for 记为 ${PKG_VERSION}`);
}

// ── --status ────────────────────────────────────────────────────────────────

// 只读聚合：复用 followUp 与 knowledgeCheck 的纯计算，不调 printFollowUp（它会写 adapted_for）。
// 升级前装的是哪一版、历次做完了哪些，另起的进程读不到：照实写 unknown，以上次交回为准，不造状态文件补洞。
if (mode === '--status') {
  const ident = key => (existsSync(tgtManifest) ? manifestValue(read(tgtManifest), key) : null);
  const out = {
    mode: 'status', package: { version: PKG_VERSION },
    target: { installed: STATE === 'upgrade', version: INSTALLED, name: ident('name'), description: ident('description'),
      adapters: TARGET_ADAPTATION.doc.adapters ?? null, adapted_for: TARGET_ADAPTATION.doc.adapted_for ?? null },
    history: 'unknown：升级前所装版本与历次已完成的适配读不到，以上次交回为准；items 只按当前游标推导',
  };
  if (STATE === 'fresh') {
    console.log(JSON.stringify({ ...out, state: 'not_installed' }, null, 2));
    process.exit(0);
  }
  const f = await followUp();
  out.items = f.items;
  out.knowledge = f.check;
  console.log(JSON.stringify(out, null, 2));
  process.exit(f.check.status === 'PASS' ? 0 : 1);
}

// ── --mark-adapted ──────────────────────────────────────────────────────────

if (mode === '--mark-adapted') {
  if (SAME_TREE) die('包与目标是同一棵树，没有可写的东西');
  if (!existsSync(tgtManifest)) die('目标没有 manifest.yaml：还没装过，先 --apply');
  if (INSTALLED !== PKG_VERSION) {
    die(`目标机制是 ${INSTALLED}、包是 ${PKG_VERSION}：先 --apply 把机制升到包的版本，再做适配`);
  }
  const f = await followUp();
  if (f.check.status !== 'PASS') die(`知识不能按当前协议加载，适配还没做完：\n  ${f.check.problems.join('\n  ')}`);
  // 本次有知识演进义务时，加载通过不等于适配完成：当前知识要有对得上的独立审查证据
  if (f.items.知识?.length && f.check.review.status !== 'valid') {
    die(`本次有 ${f.items.知识.length} 条知识演进要适配，知识独审证据不成立（${f.check.review.status}）：\n  `
      + `${f.check.review.problems.join('\n  ')}\n  按 reference/knowledge-review.md 发起与收回审查；`
      + '机制已经装好，知识适配未完成，adapted_for 不写');
  }
  writeAdaptedFor();
  console.log(`[adapt-scan] adapted_for 记为 ${PKG_VERSION}：下次升级只列晚于它的演进条目`);
  process.exit(0);
}

// ── --apply ─────────────────────────────────────────────────────────────────

if (mode === '--apply') {
  if (SAME_TREE) die('包与目标是同一棵树，没有可写的东西');

  // 前置：不满足就停，不猜。工作区脏的话 diff 里混着用户自己的改动，分不清哪些是
  // 升级带来的——而「升级把用户没提交的改动盖了、diff 里还看不出来」没法补救。
  if (!isRepo(TARGET)) {
    die(`目标不是 git 仓库：${TARGET}\n`
      + '  这一次要整份换掉覆盖范围内的文件，没存档的改动被盖掉就找不回来了。');
  }
  // manifest 的 name 归目标、升级不改；Framework 只认小写 slug，不合规就写前停
  const composedText = composeManifest(PKG_MANIFEST_TEXT, existsSync(tgtManifest) ? read(tgtManifest) : '', freshIdentity(TARGET));
  const composedName = manifestValue(composedText, 'name');
  if (!SLUG.test(composedName ?? '')) {
    die(`目标 manifest 的 name（${composedName}）不是小写 slug：Framework 按它识别扩展，`
      + '先把它改成小写字母开头、只含小写字母数字与 _ -，再升级。目标一个字节未写', 2);
  }

  // 待装的扩展（包的机制面 + 合成后的 manifest + 目标自己的知识）先用目标的 Framework 核一遍：
  // 登记坏了时入口渲染也会跟着变，先报根因
  let candidate;
  try {
    candidate = candidateProblems(TARGET, (dir) => {
      for (const p of coveredFiles(PDIR, WITH_ADAPTERS)) {
        mkdirSync(dirname(join(dir, ...p.split('/'))), { recursive: true });
        copyFileSync(join(PDIR, ...p.split('/')), join(dir, ...p.split('/')));
      }
      writeFileSync(join(dir, 'manifest.yaml'), composedText, 'utf8');
      for (const p of walk(join(TDIR, KNOWLEDGE))) {
        mkdirSync(dirname(join(dir, KNOWLEDGE, ...p.split('/'))), { recursive: true });
        copyFileSync(join(TDIR, KNOWLEDGE, ...p.split('/')), join(dir, KNOWLEDGE, ...p.split('/')));
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

  // 宿主入口写前核：原生物化会整份重写入口文件、不接管无归属的入口，有别的内容就先停
  let plan;
  try {
    plan = entryPlan(TARGET, PKG_SKILLS);
  } catch (e) {
    die(`宿主入口核不了（${e.message}）`);
  }

  const dirty = dirtyPaths(TARGET).filter(p => inWriteFace(TARGET, p, [...plan.entries, ...plan.retire], WITH_ADAPTERS));
  if (dirty.length) {
    console.error(`[adapt-scan] 停：写入面上有 ${dirty.length} 处未提交改动，升级会盖掉它们：`);
    dirty.forEach(p => console.error(`  ${p}`));
    die('先提交或暂存自己的改动再升级——本命令不替你动工作区（不 stash、不提交）', 2);
  }
  if (existsSync(join(TARGET, ...USAGE.record.split('/')))) {
    const u = await usageWriter(PDIR, 'inspect');
    if (!u.ok) die(`使用记录 ${USAGE.record} 不合法（${(u.errors ?? []).join('；')}）：它不会被当成空表覆盖。机制一个字节没写，修好后重跑 --apply`, 2);
  }
  if (plan.conflicts.length) {
    console.error(`[adapt-scan] 停：宿主入口有 ${plan.conflicts.length} 处 Framework 物化会覆盖或不接管的内容：`);
    plan.conflicts.forEach(c => console.error(`  ${c}`));
    die('这些内容要保留就挪到它自己的位置，确认可弃就删掉，再升级。目标一个字节未写', 2);
  }

  const pkgFiles = coveredFiles(PDIR, WITH_ADAPTERS);
  const written = [];
  const removed = [];

  // 1. 机制面整体替换：包里没有而目标有的先删，再逐个复制
  const tgtFiles = new Set(existsSync(TDIR) ? coveredFiles(TDIR, WITH_ADAPTERS) : []);
  for (const p of tgtFiles) {
    if (pkgFiles.includes(p)) continue;
    rmSync(join(TDIR, ...p.split('/')));
    removed.push(p);
  }
  for (const p of pkgFiles) {
    const from = join(PDIR, ...p.split('/'));
    const to = join(TDIR, ...p.split('/'));
    if (existsSync(to) && sha(from) === sha(to)) continue;   // 一样就不碰，diff 才说得清
    mkdirSync(dirname(to), { recursive: true });
    copyFileSync(from, to);
    written.push(p);
  }

  // 2. manifest 合成：机制登记归包，知识激活清单归目标
  const composed = composeManifest(
    PKG_MANIFEST_TEXT, existsSync(tgtManifest) ? read(tgtManifest) : '',
    freshIdentity(TARGET));
  if (!existsSync(tgtManifest) || read(tgtManifest) !== composed) {
    mkdirSync(dirname(tgtManifest), { recursive: true });
    writeFileSync(tgtManifest, composed, 'utf8');
    written.push('manifest.yaml');
  }

  // 3. 适配状态：已有就不动；1.x 升级从旧 manifest 迁两项；首次为空映射
  if (TARGET_ADAPTATION.text !== null) {
    writeFileSync(join(TDIR, ADAPTATION), TARGET_ADAPTATION.text, 'utf8');
    written.push(ADAPTATION);
  }

  // 4. `.gitignore`：真的还没被挡住才补；使用记录被目标规则挡住时补一条精确放行再复查
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

  // 5. 首次安装另做一件：配置键。升级不碰。知识不建骨架，由模型按方法页从部件定位知识写起。
  if (STATE === 'fresh') {
    const cfgFile = join(TARGET, 'framework.config.json');
    const cfg = config(TARGET);
    if (!cfg?.paths?.extension_dir) {
      cfg.paths = { ...(cfg.paths || {}), extension_dir: 'doc/extensions' };
      writeFileSync(cfgFile, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8');
      written.push('framework.config.json');
    }
  }

  // 6. 宿主入口：退出已核的旧入口，交 Framework 物化，再核一遍
  let entries;
  try {
    entries = entryMaterialize(TARGET, plan.retire);
  } catch (e) {
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

  // 7. 使用记录：机制写完之后经目标已装的记录器建立；首装、升级、同版本补文件都走这一处
  const usage = await ensureUsage();
  // 一个字节都没动 = 这个目标已经在包的版本上。说出来，不要报「写入 0 个文件」——
  // 那句话看起来像什么都没做成，而事实是没有可做的。
  if (!written.length && !removed.length) {
    console.log('[adapt-scan] 机制已在包的版本上，没有机制文件要写');
    usage.lines.forEach(l => console.log(l));
    if (HOOKS_OFF) console.log(HOOKS_OFF);
    await printFollowUp();
    process.exit(usage.ok ? 0 : 1);
  }
  console.log(`[adapt-scan] ${usage.ok ? `${STATE === 'fresh' ? '首次安装' : '升级'}完成` : '机制文件写完，适配没有全部完成（见下）'}：`
    + `写入 ${written.length} 个文件，清除 ${removed.length} 个包里不再有的文件`);
  if (removed.length) removed.forEach(p => console.log(`  - ${p}`));
  console.log('[adapt-scan] 下一步：跑 --check 自检；'
    + (STATE === 'fresh'
      ? '首次安装接着按 SKILL.md：写部件定位知识并摆给人确认一次 → 按下面列出的知识条目逐题判适用、'
        + '按目标仓写 → 知识交回后跑 --mark-adapted 记下适配版本'
      : '`git diff` 看这次动了哪些文件'));
  usage.lines.forEach(l => console.log(l));
  if (HOOKS_OFF) console.log(HOOKS_OFF);
  await printFollowUp();
  process.exit(usage.ok ? 0 : 1);
}

// ── --check ─────────────────────────────────────────────────────────────────

const bad = [];

// ① 装的是不是包的这一版：机制面逐字对包，包里没有的目标也不该有。
//
// **判的是安装结果，不是「谁改的」。** 拿 `git status` 相对 HEAD 的差异当证据不成立：
// 目标自己改过知识、`--apply` 一个字节没写，diff 照样把那处改动算到 adapt 头上；
// 反过来目标把上一次升级提交了，diff 为空，装错了也看不出来。git 回答的是
// 「相对上一个提交变了什么」，回答不了「这是谁做的」。
//
// 所有权已经由目录定死，`--apply` 的写入面天然不含 `knowledge/` 与 `adapters/`
// （`coveredFiles` 一开始就把它们排除在外）——「adapt 碰没碰它们」由实现保证，
// 不需要再找证据。这里只回答剩下的那个问题：**这个目标现在装的是不是包的这一版。**
{
  const pkgFiles = coveredFiles(PDIR, WITH_ADAPTERS);
  const inPkg = new Set(pkgFiles);
  for (const p of pkgFiles) {
    const to = join(TDIR, ...p.split('/'));
    if (!existsSync(to)) { bad.push(`① 机制面缺文件：${p}——跑 --apply 装上`); continue; }
    if (sha(join(PDIR, ...p.split('/'))) !== sha(to)) {
      bad.push(`① 机制面与包不同：${p}——机制归包，目标改了它下一次升级也会被换回去`);
    }
  }
  for (const p of (existsSync(TDIR) ? coveredFiles(TDIR, WITH_ADAPTERS) : [])) {
    if (!inPkg.has(p)) bad.push(`① 机制面多出包里没有的文件：${p}——跑 --apply 清掉`);
  }
}

// ② manifest：合成一遍，看等不等于盘上那份。
//
// 它是唯一一个「一个文件两种所有权」的地方，而合成规则本身就是那条所有权的表达——
// 拿它当判据，机制段与包不同、知识清单被升级动过，两种都露出来，不必各写一条。
if (existsSync(tgtManifest)) {
  const tgtText = read(tgtManifest);
  // 比之前把换行归一：合成结果一律 LF，而目标用什么换行是它的排版自由——
  // 拿这个判「装错了」，一个内容完全正确的 CRLF 仓会一直红，而报错还指着知识清单。
  const sameText = (a, b) => a.split(/\r\n/).join('\n') === b.split(/\r\n/).join('\n');
  if (!sameText(composeManifest(PKG_MANIFEST_TEXT, tgtText,
    freshIdentity(TARGET)), tgtText)) {
    bad.push('② manifest 不是这个包合成出来的：机制登记（version / skills / hooks / overlay）要与包相同，'
      + 'name / description / provides.knowledge 归目标——跑 --apply 重新合成');
  }
  if (!existsSync(join(TDIR, ADAPTATION))) bad.push(`② 目标没有 ${ADAPTATION}：跑 --apply 写上`);
} else {
  bad.push(`② 目标没有 manifest.yaml：这个仓还没装过，跑 --apply`);
}

// ③ 宿主入口：入口文件等于 Framework 按当前配置的渲染，每个 Skill 的入口都在且归属正确
try {
  for (const p of entryCheck(TARGET).problems) bad.push(`③ 宿主入口：${p}——跑 --apply 物化`);
} catch (e) {
  bad.push(`③ 宿主入口核不了：${e.message}`);
}

// ④ 工作件被挡住了：章草稿、使用记录的一次性输入、锁与临时文件不挡就会被提交进目标的库。
// 目标怎么挡不管——自己写了那一行、或者整个需求目录都不入库，都算挡住了。使用记录本身反过来必须能入库。
for (const line of missingGitignoreLines(TARGET)) {
  bad.push(`④ 工作件没被 .gitignore 挡住：补一行 ${line}`);
}
{
  const blocked = usageBlockedBy(TARGET);
  if (blocked) bad.push(`④ 使用记录 ${USAGE.record} 被 ${blocked} 挡住：它归目标，要能随普通 git add 入库`);
  const u = await usageWriter(existsSync(join(TDIR, 'hooks')) ? TDIR : PDIR, 'inspect');
  if (!u.ok) bad.push(`④ 使用记录：${(u.errors ?? []).join('；')}——缺了跑 --apply 建立；坏了修好后重验，不重置成空表`);
}

// ⑤ 包的 `scripts/` 这一层只有 core/ 与 adapters/ 两个目录
//
// 判的是**包**，不是目标。所有权由目录表达，所以根这一层必须是空的：往根下放一个
// 脚本，它归谁就又要靠推断；所有权只由目录表达。
{
  const at = join(PDIR, ...SCRIPTS_DIR.split('/'));
  if (existsSync(at)) {
    for (const e of readdirSync(at, { withFileTypes: true })) {
      if (e.isDirectory()) {
        if (![CORE, 'adapters', '__pycache__'].includes(e.name)) {
          bad.push(`⑤ 包的 ${SCRIPTS_DIR}/ 下有第三个目录：${e.name}`
            + `——公共脚本进 ${CORE}/，目标仓自己实现的进 adapters/，没有第三种`);
        }
        continue;
      }
      bad.push(`⑤ 包的 ${SCRIPTS_DIR}/ 根下有独立文件：${e.name}`
        + `——公共脚本进 ${CORE}/（会随升级更新），目标仓自己实现的进 adapters/（升级不碰）；`
        + '放在根下的那一份两边都不认，永远升级不到目标手里');
    }
  }
}

if (HOOKS_OFF) console.log(HOOKS_OFF);
if (bad.length) {
  console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`);
  bad.forEach(b => console.error(`  ${b}`));
  process.exit(1);
}
console.log('[adapt-scan] 核对通过：机制面与包一致 / manifest 按所有权合成 / '
  + '宿主入口与 Framework 物化一致 / 工作件被 .gitignore 挡住、使用记录在且合法能入库 / 包的 scripts 只有 core 与 adapters'
  + (WITH_ADAPTERS ? '（来源带对接实现）' : ''));
