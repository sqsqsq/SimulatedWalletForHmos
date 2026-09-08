#!/usr/bin/env node
/**
 * story adapt —— 把这套扩展装进一个目标工程，或把已装的升到包的版本。
 *
 * **所有权由目录表达**，不靠推断：
 *   `<ext>/skills/story/scripts/core/`      公共，整份换掉（包里不再有的自然消失）
 *   `<ext>/skills/story/scripts/adapters/`  对接实现；Demo 来源不碰，业务仓之间复刻时覆盖
 *   `<ext>/knowledge/`                      目标的知识，不读不写
 *   `<ext>/manifest.yaml`                   机制登记归包，name / description / 知识清单归目标
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
import { fileURLToPath } from 'node:url';

const MODES = ['--apply', '--check'];

/** 目标仓自己实现的那一层。这个目录整个不在写入面上。 */
const ADAPTERS = 'skills/story/scripts/adapters';
/** 目标的知识：升级不读不写，首次只建目录与各类 README。 */
const KNOWLEDGE = 'knowledge';
/** 公共脚本的唯一落点。`scripts/` 这一层除了它与 adapters 不放东西——⑧ 守这条。 */
const SCRIPTS_DIR = 'skills/story/scripts';
const CORE = 'core';

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
 * 首次安装建的知识骨架：各类 README，一份不多。
 *
 * 它们是读法与清单说明（`kind: index`），派生出来四类皆空——正是「这个仓还没配置
 * 知识」该有的样子。包里的知识正文一份不带：那是 Demo 自己的业务内容（A3）。
 */
function skeletonKnowledge(pdir) {
  return walk(join(pdir, KNOWLEDGE), pdir).filter(p => p.endsWith('README.md')).sort();
}

/**
 * 合成 manifest：包的为底，知识清单按两态各走各的。
 *
 * 它是写入面上唯一一个「一个文件两种所有权」的地方（§3）：其余键与包相同，
 * `provides.knowledge` 归目标。
 *
 * **升级**：目标现有的清单原样放回——知识激活随目标，不因升级重选。
 * **首次**：换成刚建的骨架。照抄包的清单会登记 Demo 那十几份知识正文，而目标里
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
function composeManifest(pkgText, tgtText, skeleton, identity) {
  const lines0 = pkgText.split(/\r?\n/);
  const keep = { ...identity };
  if (tgtText) {
    for (const key of TARGET_OWNED_KEYS) {
      const at = tgtText.split(/\r?\n/).find(l => l.startsWith(`${key}:`));
      if (at) keep[key] = at.slice(key.length + 1).trim();
    }
  }
  const lines = lines0.map((l) => {
    const key = TARGET_OWNED_KEYS.find(k => l.startsWith(`${k}:`));
    return key && keep[key] !== undefined ? `${key}: ${keep[key]}` : l;
  });
  const mine = knowledgeBlock(pkgText);
  if (!mine) return lines.join('\n');
  const withList = items => [
    ...lines.slice(0, mine.at + 1), ...items.map(p => `    - ${p}`), ...lines.slice(mine.to),
  ].join('\n');
  if (!tgtText) return withList(skeleton ?? []);
  const theirs = knowledgeBlock(tgtText);
  if (!theirs) return withList([]);
  return [...lines.slice(0, mine.from), theirs.text, ...lines.slice(mine.to)].join('\n');
}

/** manifest 里归目标的键：这个仓叫什么、是什么。升级不改，首次按目标仓生成。 */
const TARGET_OWNED_KEYS = ['name', 'description'];

function manifestValue(manifestText, key) {
  const at = manifestText.split(/\r?\n/).find(l => l.startsWith(`${key}:`));
  return at ? at.slice(key.length + 1).trim() : null;
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
  * 目标 `.gitignore` 该有的：章草稿目录。
  *
  * 就这一行——本命令自己不落任何工作件（自检直接核安装结果，不写 before 快照），
  * 所以没有第二行要挡的东西。
  */
const gitignoreLines = root => [`${featuresDir(root)}/**/AR/story-src/drafts/`];

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
 * 两种来源：**Demo** 的三个 js 是本地目录模拟需求系统的替身，复制到业务仓等于把人家的
 * 真实现盖掉；**业务仓之间**共用同一套对接实现，复刻时正该带上（A12）。
 *
 * 判据是包 manifest 的 `name`：它归目标、升级不改，所以每个仓的 manifest 里那个名字
 * 始终是它自己的——「这个包从哪个仓发出来」有唯一答案，不必靠仓名长相、目录结构
 * 或对接脚本的内容去猜。
 */
const MOCK_ADAPTER_PACKAGE = 'wallet-sdk-demo';
const PKG_NAME = manifestValue(PKG_MANIFEST_TEXT, 'name');
const WITH_ADAPTERS = PKG_NAME !== MOCK_ADAPTER_PACKAGE;

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
    skeletonKnowledge(PDIR), freshIdentity(TARGET));
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
      const after = replaceZone(before, block);
      if (after !== before) { writeFileSync(f, after, 'utf8'); written.push(entry); }
    }
  }

  // 5. `.gitignore` 两行：缺就补
  {
    const f = join(TARGET, '.gitignore');
    const have = existsSync(f) ? read(f) : '';
    const missing = gitignoreLines(TARGET)
      .filter(l => !have.split(/\r?\n/).map(x => x.trim()).includes(l));
    if (missing.length) {
      writeFileSync(f, `${have.replace(/\n*$/, '\n')}${missing.join('\n')}\n`, 'utf8');
      written.push('.gitignore');
    }
  }

  // 6. 首次安装另做两件：配置键与知识骨架。升级两件都不碰。
  if (STATE === 'fresh') {
    const cfgFile = join(TARGET, 'framework.config.json');
    const cfg = config(TARGET);
    if (!cfg?.paths?.extension_dir) {
      cfg.paths = { ...(cfg.paths || {}), extension_dir: 'doc/extensions' };
      writeFileSync(cfgFile, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8');
      written.push('framework.config.json');
    }
    // 知识只建目录与各类 README（读法与清单说明），不放包里的知识正文——
    // 那是这个仓自己的东西，从空的开始（A3）。**与写进 manifest 的是同一份清单**：
    // 各扫一遍的话，登记的与建出来的会在下一次改动时错开。
    for (const p of skeletonKnowledge(PDIR)) {
      const to = join(TDIR, ...p.split('/'));
      mkdirSync(dirname(to), { recursive: true });
      copyFileSync(join(PDIR, ...p.split('/')), to);
      written.push(p);
    }
  }

  // 一个字节都没动 = 这个目标已经在包的版本上。说出来，不要报「写入 0 个文件」——
  // 那句话看起来像什么都没做成，而事实是没有可做的。
  if (!written.length && !removed.length) {
    console.log('[adapt-scan] 当前适配仍有效：目标已在包的版本上，没有要写的东西');
    process.exit(0);
  }
  console.log(`[adapt-scan] ${STATE === 'fresh' ? '首次安装' : '升级'}完成：`
    + `写入 ${written.length} 个文件，清除 ${removed.length} 个包里不再有的文件`);
  if (removed.length) removed.forEach(p => console.log(`  - ${p}`));
  console.log('[adapt-scan] 下一步：跑 --check 自检；'
    + (STATE === 'fresh'
      ? '首次安装还要按 SKILL.md 写部件画像，摆给人确认一次'
      : '`git diff` 看这次动了哪些文件'));
  process.exit(0);
}

/** 剥掉正文里已有的标记行——包里那一份带不带标记，写出去都只包一层。 */
function stripMarks(text) {
  return text.split(/\r?\n/).filter(l => !l.trim().startsWith('<!-- story-ext:')).join('\n').trim();
}

/** 标记区在就整段替换，不在就追加到末尾。标记之外一个字节不动。 */
function replaceZone(text, block) {
  const from = text.indexOf(EXT_BEGIN);
  const to = text.indexOf(EXT_END);
  if (from >= 0 && to > from) {
    return text.slice(0, from) + block + text.slice(to + EXT_END.length);
  }
  return `${text.replace(/\n*$/, '\n')}\n${block}\n`;
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
// （`packageMechanism` 一开始就把它们排除在外）——「adapt 碰没碰它们」由实现保证，
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
  if (composeManifest(PKG_MANIFEST_TEXT, tgtText, skeletonKnowledge(PDIR),
    freshIdentity(TARGET)) !== tgtText) {
    bad.push('② manifest 不是这个包合成出来的：机制登记（version / skills / bridges / hooks /'
      + ' overlay）要与包相同，name / description / provides.knowledge 归目标'
      + '——跑 --apply 重新合成');
  }
} else {
  bad.push(`② 目标没有 manifest.yaml：这个仓还没装过，跑 --apply`);
}

// ⑤ 入口文件含扩展段与标记区
{
  const sectionFile = join(PDIR, ...SECTION.split('/'));
  if (existsSync(sectionFile)) {
    const ws = s => s.replace(/\s+/g, ' ').trim();
    const body = ws(stripMarks(read(sectionFile)));
    for (const entry of ENTRIES) {
      const f = join(TARGET, entry);
      if (!existsSync(f)) {
        if (entry === 'AGENTS.md') bad.push(`⑤ 入口文件缺失：${entry}`);
        continue;
      }
      const got = read(f);
      if (!ws(got).includes(body)) {
        bad.push(`⑤ 入口文件未含扩展段：${entry}（跑 --apply 把它连同标记区写进「实例扩展」节）`);
        continue;
      }
      if (!got.includes(EXT_BEGIN) || !got.includes(EXT_END)) {
        bad.push(`⑤ 入口文件的扩展段没有标记区：${entry}`
          + `（把既有那一段**原位**用 ${EXT_BEGIN} / ${EXT_END} 包起来，不要另追加一段）`);
      }
    }
  }
}

// ⑦ 目标 .gitignore 有那两行：adapt 工作目录与章草稿目录都是临时件，不加就会被提交进目标的库
{
  const f = join(TARGET, '.gitignore');
  const have = existsSync(f) ? read(f).split(/\r?\n/).map(l => l.trim()) : [];
  for (const line of gitignoreLines(TARGET)) {
    if (!have.includes(line)) bad.push(`⑦ 目标 .gitignore 缺一行：${line}`);
  }
}

// ⑧ 包的 `scripts/` 这一层只有 core/ 与 adapters/ 两个目录
//
// 判的是**包**，不是目标。所有权由目录表达，所以根这一层必须是空的：往根下放一个
// 脚本，它归谁就又要靠推断——而「靠推断」正是这次重写要退掉的东西。
{
  const at = join(PDIR, ...SCRIPTS_DIR.split('/'));
  if (existsSync(at)) {
    for (const e of readdirSync(at, { withFileTypes: true })) {
      if (e.isDirectory()) {
        if (![CORE, 'adapters', '__pycache__'].includes(e.name)) {
          bad.push(`⑧ 包的 ${SCRIPTS_DIR}/ 下有第三个目录：${e.name}`
            + `——公共脚本进 ${CORE}/，目标仓自己实现的进 adapters/，没有第三种`);
        }
        continue;
      }
      // README.md 是这一层的说明（两个目录各归谁、对接层的输出合同），不是脚本，
      // 归谁的问题在它身上不存在。例外只此一个，写死在这里。
      if (e.name === 'README.md') continue;
      bad.push(`⑧ 包的 ${SCRIPTS_DIR}/ 根下有独立文件：${e.name}`
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
