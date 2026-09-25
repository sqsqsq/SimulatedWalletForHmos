#!/usr/bin/env node
/**
 * story adapt —— 把这套扩展装进一个目标工程，或把已装的升到包的版本。
 *
 * **所有权由目录表达**，不靠推断：
 *   `<ext>/skills/story/scripts/core/`      公共，整份换掉（包里不再有的自然消失）
 *   `<ext>/skills/story/scripts/adapters/`  对接实现；Demo 来源不碰，业务仓之间复刻时覆盖
 *   `<ext>/knowledge/`                      目标的知识，脚本不读不写（适配由模型按方法页做）
 *   `<ext>/manifest.yaml`                   机制登记归包，name / description / adapters / knowledge_adapted_for / 知识清单归目标
 *   其余 `<ext>/**`                         机制，整份换掉
 *
 * 边界这么一分，一个文件归谁看它在哪个目录，没有第三种要模型判断的情形；
 * `--check` 据此核**安装结果**——这个目标现在装的是不是包的这一版。
 *
 * 用法: node adapt-scan.mjs --apply|--check --target <目标根> [--package <包根>]
 * 退出: 0 通过 / 1 核对不符 / 2 参数或前置错误
 */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync,
} from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseYaml } from '../../../hooks/shared/yaml.mjs';

const MODES = ['--apply', '--check'];

/** 目标仓自己实现的那一层。这个目录整个不在写入面上。 */
const ADAPTERS = 'skills/story/scripts/adapters';
/** 目标的知识：首次与升级都不读不写；首装的清单为空，第一份部件定位知识由模型写。 */
const KNOWLEDGE = 'knowledge';
/** 公共脚本的唯一落点。`scripts/` 这一层除了它与 adapters 不放东西——⑤ 守这条。 */
const SCRIPTS_DIR = 'skills/story/scripts';
const CORE = 'core';
/** 知识协议的演进记录：按扩展版本分节，升级后据它提示目标该改什么。 */
const CHANGES = 'skills/story-adaptation/reference/knowledge-changes.md';

const EXT_BEGIN = '<!-- story-ext:begin -->';
const EXT_END = '<!-- story-ext:end -->';
const SECTION = 'skills/story/AGENTS.section.md';
const ENTRIES = ['AGENTS.md', 'CLAUDE.md'];

const argv = process.argv.slice(2);
const mode = MODES.find(m => argv.includes(m));
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
const die = (msg, code = 2) => { console.error(`[adapt-scan] ${msg}`); process.exit(code); };

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
    return die(`${f} 读不出（${e.message}）：扩展落点与需求目录都从它取`);
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
 * 按 `composeManifest` 的规则单独合成。
 */
function coveredFiles(root, withAdapters) {
  const skip = new Set(withAdapters ? [KNOWLEDGE] : [KNOWLEDGE, ADAPTERS]);
  return walk(root, root, skip).filter(p => p !== 'manifest.yaml');
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
  const withList = items => join([
    ...lines.slice(0, mine.at + 1), ...items.map(p => `    - ${p}`), ...lines.slice(mine.to),
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
 * manifest 里归目标的键：这个仓叫什么、是什么、对接层是不是替身、知识按哪一版协议适配过。
 * 升级不改，首次按目标仓生成；目标没写的不从包里带过去。
 */
const TARGET_OWNED_KEYS = ['name', 'description', 'adapters', 'knowledge_adapted_for'];

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
 * `name: wallet-sdk-demo` 与 `name: "wallet-sdk-demo"` 在 YAML 里是同一个值，行尾
 * 跟个注释也一样。拿字面去比，加一对引号就会把 Demo 判成业务仓——而那一判之下
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
    name: project,
    description: `${project} 的实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）`,
  };
}

function bridgesOf(manifestText) {
  const lines = manifestText.split(/\r?\n/);
  const at = lines.findIndex(l => /^ {2}bridges:/.test(l));
  if (at < 0) return [];
  const out = [];
  for (let i = at + 1; i < lines.length && !/^ {2}\S/.test(lines[i]); i += 1) {
    const m = lines[i].match(/^\s+-\s+(\S+)/);
    if (m) out.push(m[1]);
  }
  return out;
}

// ── 写入面 ──────────────────────────────────────────────────────────────────

/**
 * 目标 `.gitignore` 还缺哪几行。
 *
 * 要挡的只有章草稿目录——本命令自己不落工作件，没有第二样东西。
 *
 * **先问 git 它是不是已经被挡住了**：需求目录整个不入库是常见做法（`doc/features/`
 * 一行就盖住了它下面的一切），那时再加一条只是噪声——一条永远不起作用的规则，
 * 下一个维护者还得花时间弄清它为什么在。
 *
 * 问 git 而不是自己比对模式：两条模式等不等价，字符串比不出来。目标不是 git 仓时
 * 按「没挡住」处理，照常补。
 */
function missingGitignoreLines(root) {
  const want = `${featuresDir(root)}/**/AR/story-src/drafts/`;
  const probe = `${featuresDir(root)}/_probe/AR/story-src/drafts/x.md`;
  if (git(root, ['check-ignore', '-q', '--no-index', probe]).ok) return [];
  const f = join(root, '.gitignore');
  const have = existsSync(f) ? read(f).split(/\r?\n/).map(l => l.trim()) : [];
  return have.includes(want) ? [] : [want];
}

/**
 * 这条路径这一次写不写得。**与 `coveredFiles` 同一个边界**，只是换个问法：
 * 那个答「要覆盖哪些」，这个答「某一条在不在覆盖范围里」。写入前查工作区脏不脏用它。
 */
function inWriteFace(root, p, bridges, withAdapters) {
  if (p === '.gitignore' || ENTRIES.includes(p)) return true;
  if (bridges.includes(p)) return true;
  const ext = extDir(root);
  if (!p.startsWith(`${ext}/`)) return false;
  const inner = p.slice(ext.length + 1);
  if (inner.startsWith(`${KNOWLEDGE}/`)) return false;
  if (!withAdapters && inner.startsWith(`${ADAPTERS}/`)) return false;
  return true;
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
const TDIR = join(TARGET, ...extDir(TARGET).split('/'));

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
      + '先在目标里跑 `cd framework/harness && npm install`，再 --apply / --check');
  }
}
const SAME_TREE = resolve(PKG) === resolve(TARGET);

const pkgManifest = join(PDIR, 'manifest.yaml');
if (!existsSync(pkgManifest)) die(`包里没有 manifest.yaml：${pkgManifest}`);
const PKG_MANIFEST_TEXT = read(pkgManifest);
const BRIDGES = bridgesOf(PKG_MANIFEST_TEXT);

const tgtManifest = join(TDIR, 'manifest.yaml');
/** 两态，就这一条判据：目标有没有 manifest.yaml。历史版本识别不存在于本实现。 */
const STATE = existsSync(tgtManifest) ? 'upgrade' : 'fresh';

/**
 * 这一次带不带对接层。
 *
 * 包 manifest 的 `adapters: stand-in` 说明包里的对接实现是替身（用本地目录模拟需求系统），
 * 复制到业务仓等于把人家的真实现盖掉；没有这个键的包是业务仓，共用同一套对接实现，复刻时带上。
 * 这个键归目标、升级不改，所以每个仓说的都是它自己的对接层。
 */
const WITH_ADAPTERS = manifestValue(PKG_MANIFEST_TEXT, 'adapters') !== 'stand-in';

/** 版本号按数字逐段比较。 */
const newer = (a, b) => {
  const x = String(a).split('.').map(Number);
  const y = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) > (y[i] ?? 0);
  }
  return false;
};

/**
 * 升级之后知识要不要适配：演进记录里晚于目标 `knowledge_adapted_for` 的条目，
 * 与按当前协议加载目标知识的结果（按 kind × form 计数，或问题清单）。只报事实，问不问人由模型照 SKILL 走。
 */
async function knowledgeFollowUp() {
  const since = manifestValue(read(tgtManifest), 'knowledge_adapted_for') ?? '0';
  const text = existsSync(join(PDIR, ...CHANGES.split('/'))) ? read(join(PDIR, ...CHANGES.split('/'))) : '';
  const changes = [];
  let version = null;
  for (const line of text.split(/\r?\n/)) {
    const head = line.match(/^##\s+(\d+(?:\.\d+)+)\s*$/);
    if (head) { version = head[1]; continue; }
    if (version && newer(version, since) && /^-\s+\S/.test(line)) changes.push(`${version}：${line.slice(2).trim()}`);
  }
  try {
    const api = await import(pathToFileURL(join(TDIR, 'hooks', 'shared', 'knowledge.mjs')).href);
    const k = api.activeKnowledge(TARGET);
    const problems = api.selfCheck(TARGET, k);
    const counts = {};
    for (const kind of ['facts', 'constraints', 'patterns']) {
      for (const x of k[kind]) counts[`${kind} × ${x.form}`] = (counts[`${kind} × ${x.form}`] ?? 0) + 1;
    }
    return { changes, check: problems.length ? { status: 'FAIL', problems } : { status: 'PASS', counts } };
  } catch (e) {
    return { changes, check: { status: 'FAIL', problems: [String(e?.message ?? e)] } };
  }
}

/** 升级后的知识适配提示：有内容就摆出来请模型停一次问人，都空只一句。 */
async function printFollowUp() {
  const f = await knowledgeFollowUp();
  console.log(`[adapt-scan] 知识适配：${JSON.stringify(f)}`);
  console.log(f.changes.length || f.check.status !== 'PASS'
    ? '[adapt-scan] 有演进条目或知识不合当前协议：把它们摆出来，停一次问人「现在做知识适配吗」；选稍后就不写任何东西'
    : '[adapt-scan] 知识与当前协议一致，不用适配');
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
  // 包先查：跳板清单是包自己在 manifest 里登记的，登记了却没有文件是包坏了，不是可选项。
  // 排在目标那几条之前——包坏了跟目标的状态无关，先说这件事，人才不必先去收拾工作区。
  const noBridge = BRIDGES.filter(b => !existsSync(join(PKG, ...b.split('/'))));
  if (noBridge.length) {
    console.error(`[adapt-scan] 停：包里登记了跳板却没有文件（${noBridge.length} 个）：`);
    noBridge.forEach(b => console.error(`  ${b}`));
    die('包坏了——补上文件，或从 manifest 的 provides.bridges 里撤掉登记。目标一个字节未写', 2);
  }

  const dirty = dirtyPaths(TARGET).filter(p => inWriteFace(TARGET, p, BRIDGES, WITH_ADAPTERS));
  if (dirty.length) {
    console.error(`[adapt-scan] 停：写入面上有 ${dirty.length} 处未提交改动，升级会盖掉它们：`);
    dirty.forEach(p => console.error(`  ${p}`));
    die('先提交或暂存自己的改动再升级——本命令不替你动工作区（不 stash、不提交）', 2);
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

  // 3. 跳板：扩展自有的宿主入口文件，直接覆盖（缺文件已由前置拦下）
  for (const b of BRIDGES) {
    const from = join(PKG, ...b.split('/'));
    const to = join(TARGET, ...b.split('/'));
    if (existsSync(to) && sha(from) === sha(to)) continue;
    mkdirSync(dirname(to), { recursive: true });
    copyFileSync(from, to);
    written.push(b);
  }

  // 4. 入口文件的标记区：只重写标记之间，标记之外一个字节不动
  const sectionFile = join(PDIR, ...SECTION.split('/'));
  if (existsSync(sectionFile)) {
    const block = `${EXT_BEGIN}\n${stripMarks(read(sectionFile))}\n${EXT_END}`;
    for (const entry of ENTRIES) {
      const f = join(TARGET, entry);
      if (!existsSync(f)) continue;
      const before = read(f);
      const { text: after, note } = replaceZone(before, block);
      if (after !== before) { writeFileSync(f, after, 'utf8'); written.push(entry); }
      if (note) console.error(`[adapt-scan] ${entry}：${note}`);
    }
  }

  // 5. `.gitignore`：真的还没被挡住才补
  {
    const f = join(TARGET, '.gitignore');
    const have = existsSync(f) ? read(f) : '';
    const missing = missingGitignoreLines(TARGET);
    if (missing.length) {
      writeFileSync(f, `${have.replace(/\n*$/, '\n')}${missing.join('\n')}\n`, 'utf8');
      written.push('.gitignore');
    }
  }

  // 6. 首次安装另做一件：配置键。升级不碰。知识不建骨架，由模型按方法页从部件定位知识写起。
  if (STATE === 'fresh') {
    const cfgFile = join(TARGET, 'framework.config.json');
    const cfg = config(TARGET);
    if (!cfg?.paths?.extension_dir) {
      cfg.paths = { ...(cfg.paths || {}), extension_dir: 'doc/extensions' };
      writeFileSync(cfgFile, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8');
      written.push('framework.config.json');
    }
  }

  // 一个字节都没动 = 这个目标已经在包的版本上。说出来，不要报「写入 0 个文件」——
  // 那句话看起来像什么都没做成，而事实是没有可做的。
  if (!written.length && !removed.length) {
    console.log('[adapt-scan] 当前适配仍有效：目标已在包的版本上，没有要写的东西');
    if (STATE === 'upgrade') await printFollowUp();
    process.exit(0);
  }
  console.log(`[adapt-scan] ${STATE === 'fresh' ? '首次安装' : '升级'}完成：`
    + `写入 ${written.length} 个文件，清除 ${removed.length} 个包里不再有的文件`);
  if (removed.length) removed.forEach(p => console.log(`  - ${p}`));
  console.log('[adapt-scan] 下一步：跑 --check 自检；'
    + (STATE === 'fresh'
      ? '首次安装还要按 SKILL.md 写部件定位知识，摆给人确认一次'
      : '`git diff` 看这次动了哪些文件'));
  if (STATE === 'upgrade') await printFollowUp();
  process.exit(0);
}

/** 剥掉正文里已有的标记行——包里那一份带不带标记，写出去都只包一层。 */
function stripMarks(text) {
  return text.split(/\r?\n/).filter(l => !l.trim().startsWith('<!-- story-ext:')).join('\n').trim();
}

/** 标记区在就整段替换，不在就追加到末尾。标记之外一个字节不动。 */
function replaceZone(text, block) {
  // 按**行**做，不按字符偏移：行是按 CRLF / LF 两种都认的方式拆的，而偏移若按 LF
  // 重新拼算，CRLF 的文件每行少算一个字符——插入点整体提前，正文被从中间切开。
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const lines = text.split(/\r?\n/);
  const rows = block.split(/\r?\n/);
  const from = lines.findIndex(l => l.includes(EXT_BEGIN));
  const to = lines.findIndex(l => l.includes(EXT_END));
  if (from >= 0 && to >= from) {
    return { text: [...lines.slice(0, from), ...rows, ...lines.slice(to + 1)].join(eol), note: null };
  }
  const at = extensionSectionEnd(lines);
  if (at !== null) {
    return { text: [...lines.slice(0, at), '', ...rows, ...lines.slice(at)].join(eol), note: null };
  }
  return {
    text: [...lines, '', ...rows, ''].join(eol),
    note: '入口文件里没有讲实例扩展的那一节，扩展段先追加在文件末尾'
      + '——它是给读者的路标，位置不对等于没放：挪进讲扩展与 Skill 路由的那一节，标记区一起带走',
  };
}

/**
 * 入口文件里「实例扩展」那一节到哪一行为止 —— 返回该插入的行号，找不到返回 null。
 *
 * 首次安装往哪儿写，答案不是「文件末尾」：入口文件是给读者的路标，扩展段落在讲
 * Skill 路由的那一节里才有人读到；追加在末尾的那一段，人打开文件时早就走过了。
 *
 * 锚点取标题里的「实例扩展」四个字，不写死某个具体标题——不同工程的标题层级与后缀
 * 都不一样，而这四个字正是这一节之所以是这一节的原因。找到就插在该节末尾
 * （下一个同级或更高级标题之前），跟在已有内容后面，不打断它。
 */
function extensionSectionEnd(lines) {
  const at = lines.findIndex(l => /^#{2,6}\s.*实例扩展/.test(l));
  if (at < 0) return null;
  const depth = lines[at].match(/^#+/)[0].length;
  let end = lines.length;
  for (let i = at + 1; i < lines.length; i += 1) {
    const m = lines[i].match(/^(#+)\s/);
    if (m && m[1].length <= depth) { end = i; break; }
  }
  while (end > at + 1 && lines[end - 1].trim() === '') end -= 1;
  return end;
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
  // 跳板在 `<ext>/` 之外，覆盖范围扫不到它们——不单独核的话，一个装坏了的宿主入口
  // 能一直躺在那里而自检说通过，而它正是人每天敲 `/story` 打进来的地方。
  for (const b of BRIDGES) {
    const from = join(PKG, ...b.split('/'));
    const to = join(TARGET, ...b.split('/'));
    if (!existsSync(to)) { bad.push(`① 跳板缺失：${b}——跑 --apply 写上`); continue; }
    if (existsSync(from) && sha(from) !== sha(to)) {
      bad.push(`① 跳板与包不同：${b}——它是扩展自己的宿主入口，跑 --apply 覆盖`);
    }
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
    bad.push('② manifest 不是这个包合成出来的：机制登记（version / skills / bridges / hooks /'
      + ' overlay）要与包相同，name / description / adapters / knowledge_adapted_for / provides.knowledge 归目标'
      + '——跑 --apply 重新合成');
  }
} else {
  bad.push(`② 目标没有 manifest.yaml：这个仓还没装过，跑 --apply`);
}

// ③ 入口文件含扩展段与标记区
//
// **目标有哪个入口文件是它自己的事**：挂 Claude 的仓只有 `CLAUDE.md`，别的宿主只有
// `AGENTS.md`，两个都有的也不少。要求某一个必须存在，等于替目标决定它用哪个宿主。
// 有几个核几个；一个都没有才是真缺——那时扩展段无处可放，人也读不到入口。
{
  const sectionFile = join(PDIR, ...SECTION.split('/'));
  if (existsSync(sectionFile)) {
    const ws = s => s.replace(/\s+/g, ' ').trim();
    const body = ws(stripMarks(read(sectionFile)));
    const present = ENTRIES.filter(e => existsSync(join(TARGET, e)));
    if (!present.length) {
      bad.push(`③ 一个入口文件都没有（${ENTRIES.join(' / ')}）：扩展段无处可放，人也读不到入口`);
    }
    for (const entry of present) {
      const f = join(TARGET, entry);
      const got = read(f);
      if (!ws(got).includes(body)) {
        bad.push(`③ 入口文件未含扩展段：${entry}（跑 --apply 把它连同标记区写进「实例扩展」节）`);
        continue;
      }
      if (!got.includes(EXT_BEGIN) || !got.includes(EXT_END)) {
        bad.push(`③ 入口文件的扩展段没有标记区：${entry}`
          + `（把既有那一段**原位**用 ${EXT_BEGIN} / ${EXT_END} 包起来，不要另追加一段）`);
      }
    }
  }
}

// ④ 章草稿目录被挡住了：它是临时件，不挡就会被提交进目标的库。
// 目标怎么挡不管——自己写了那一行、或者整个需求目录都不入库，都算挡住了。
for (const line of missingGitignoreLines(TARGET)) {
  bad.push(`④ 章草稿目录没被 .gitignore 挡住：补一行 ${line}`);
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
      // README.md 是这一层的说明（两个目录各归谁、对接层的输出合同），不是脚本，
      // 归谁的问题在它身上不存在。例外只此一个，写死在这里。
      if (e.name === 'README.md') continue;
      bad.push(`⑤ 包的 ${SCRIPTS_DIR}/ 根下有独立文件：${e.name}`
        + `——公共脚本进 ${CORE}/（会随升级更新），目标仓自己实现的进 adapters/（升级不碰）；`
        + '放在根下的那一份两边都不认，永远升级不到目标手里');
    }
  }
}

if (bad.length) {
  console.error(`[adapt-scan] 核对不符 ${bad.length} 处：`);
  bad.forEach(b => console.error(`  ${b}`));
  process.exit(1);
}
console.log('[adapt-scan] 核对通过：机制面与包一致 / manifest 按所有权合成 / '
  + '入口文件含扩展段与标记区 / .gitignore 有章草稿那一行 / 包的 scripts 只有 core 与 adapters'
  + (WITH_ADAPTERS ? '（来源带对接实现）' : ''));
