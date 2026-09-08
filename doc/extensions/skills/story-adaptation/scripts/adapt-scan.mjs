#!/usr/bin/env node
/**
 * story adapt —— 把这套扩展装进一个目标工程，或把已装的升到包的版本。
 *
 * **所有权由目录表达**，不靠推断：
 *   `<ext>/skills/story/scripts/core/`      公共，升级整份换掉（包里不再有的自然消失）
 *   `<ext>/skills/story/scripts/adapters/`  目标仓自己实现，升级一个字节不碰
 *   `<ext>/knowledge/`                      目标的知识，升级不读不写
 *   其余 `<ext>/**`                         机制，升级整份换掉
 *
 * 边界这么一分，「升级之后哪些文件变了」本身就是答案——所以确认用 `git diff`，
 * 不再读两棵树逐文件比 sha256、也不再有第三种要模型判断的情形。
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
 * 递归列文件（相对 base 的 posix 路径），跳过点开头的目录与运行产物。
 *
 * 点开头的目录是工作件，`__pycache__` 是跑过脚本就有的字节码——两样都既不入库
 * 也不交付，混进写入面会让 diff 永远核不平。
 */
function walk(dir, base = dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const f = join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '__pycache__' || e.name.startsWith('.')) return [];
      return walk(f, base);
    }
    return [rel(base, f)];
  });
}

/** 包里归本机制所有的那些文件：`<ext>/` 下去掉知识与对接层，manifest 另按合成规则处理。 */
function packageMechanism(pdir) {
  return walk(pdir).filter(p => p !== 'manifest.yaml'
    && !p.startsWith(`${KNOWLEDGE}/`) && !p.startsWith(`${ADAPTERS}/`));
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
 * 清单上面的注释块两态都保留：它讲的是这份清单怎么读，与登记了什么无关。
 */
function composeManifest(pkgText, tgtText, skeleton) {
  const mine = knowledgeBlock(pkgText);
  if (!mine) return pkgText;
  const lines = pkgText.split(/\r?\n/);
  if (!tgtText) {
    const body = (skeleton ?? []).map(p => `    - ${p}`);
    return [...lines.slice(0, mine.at + 1), ...body, ...lines.slice(mine.to)].join('\n');
  }
  const theirs = knowledgeBlock(tgtText);
  if (!theirs) return pkgText;
  return [...lines.slice(0, mine.from), theirs.text, ...lines.slice(mine.to)].join('\n');
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
  * 就这一行——本命令自己不落任何工作件（确认靠 git diff，不写 before 快照），
  * 所以没有第二行要挡的东西。
  */
const gitignoreLines = root => [`${featuresDir(root)}/**/AR/story-src/drafts/`];

/**
 * 这条路径 adapt 碰不碰得。**写入面就是所有权的另一种说法**——
 * 它答不上「是」的，diff 里出现就是错的。
 */
function inWriteFace(root, p, bridges) {
  if (p === '.gitignore' || ENTRIES.includes(p)) return true;
  if (bridges.includes(p)) return true;
  const ext = extDir(root);
  if (!p.startsWith(`${ext}/`)) return false;
  const inner = p.slice(ext.length + 1);
  if (inner.startsWith(`${KNOWLEDGE}/`) || inner.startsWith(`${ADAPTERS}/`)) return false;
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

// ── --apply ─────────────────────────────────────────────────────────────────

if (mode === '--apply') {
  if (SAME_TREE) die('包与目标是同一棵树，没有可写的东西');

  // 前置：不满足就停，不猜。工作区脏的话 diff 里混着用户自己的改动，分不清哪些是
  // 升级带来的——而「升级把用户没提交的改动盖了、diff 里还看不出来」没法补救。
  if (!isRepo(TARGET)) {
    die(`目标不是 git 仓库：${TARGET}\n  升级的确认靠 git diff，没有 git 就没有「哪些文件变了」这个答案。`);
  }
  // 包先查：跳板清单是包自己在 manifest 里登记的，登记了却没有文件是包坏了，不是可选项。
  // 排在目标那几条之前——包坏了跟目标的状态无关，先说这件事，人才不必先去收拾工作区。
  const noBridge = BRIDGES.filter(b => !existsSync(join(PKG, ...b.split('/'))));
  if (noBridge.length) {
    console.error(`[adapt-scan] 停：包里登记了跳板却没有文件（${noBridge.length} 个）：`);
    noBridge.forEach(b => console.error(`  ${b}`));
    die('包坏了——补上文件，或从 manifest 的 provides.bridges 里撤掉登记。目标一个字节未写', 2);
  }

  const dirty = dirtyPaths(TARGET).filter(p => inWriteFace(TARGET, p, BRIDGES));
  if (dirty.length) {
    console.error(`[adapt-scan] 停：写入面上有 ${dirty.length} 处未提交改动，升级会盖掉它们：`);
    dirty.forEach(p => console.error(`  ${p}`));
    die('先提交或暂存自己的改动再升级——本命令不替你动工作区（不 stash、不提交）', 2);
  }

  const pkgFiles = packageMechanism(PDIR);
  const written = [];
  const removed = [];

  // 1. 机制面整体替换：包里没有而目标有的先删，再逐个复制
  const tgtFiles = new Set(existsSync(TDIR) ? packageMechanism(TDIR) : []);
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
    skeletonKnowledge(PDIR));
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
      : 'git diff 看变了哪些文件'));
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

// diff 落点：升级之后变了哪些文件，答案要与所有权一致。
//
// **判的是「有没有碰不该碰的」，不是「diff 里只有 adapt 写的东西」**：工作区里同时
// 躺着用户自己在别处的改动是常态，那些与本命令无关。`--apply` 的前置已经保证写入面上
// 升级前是干净的，所以写入面内的 diff 就是 adapt 写的；剩下要问的只有一句——
// 它有没有伸进 `knowledge/` 或 `adapters/`。
//
// 包与目标是同一棵树时（本仓自适配）diff 没有对象——那时这一条不判，剩下三组照跑。
if (!SAME_TREE) {
  if (!isRepo(TARGET)) {
    bad.push('目标不是 git 仓库：升级的确认靠 git diff，没有 git 就核不了「变了哪些文件」');
  } else {
    const changed = dirtyPaths(TARGET);
    const ext = extDir(TARGET);
    const relManifest = `${ext}/manifest.yaml`;
    // 这次动作是首次安装还是升级：看**上一个提交里**有没有 manifest。盘上那份刚被
    // `--apply` 写出来，拿它判会把每一次首次安装都当成升级。
    //
    // 两态判的东西不同：首次安装的写入面**含**知识骨架（§3 表最后一行），
    // 那几个 README 就是这次装出来的；升级则一条都不许碰。
    const wasInstalled = git(TARGET, ['cat-file', '-e', `HEAD:${relManifest}`]).ok;
    const isSkeleton = p => p.endsWith('/README.md');
    for (const p of changed) {
      if (!p.startsWith(`${ext}/`)) continue;
      const inner = p.slice(ext.length + 1);
      if (inner.startsWith(`${KNOWLEDGE}/`) && !(!wasInstalled && isSkeleton(inner))) {
        bad.push(wasInstalled
          ? `升级动了目标的知识：${p}——已集成仓升级 knowledge 不修改、不补写、不合并（A2）`
          : `首次安装往知识目录写了正文：${p}——只建目录与各类 README，知识从空的开始（A3）`);
      }
      if (inner.startsWith(`${ADAPTERS}/`)) {
        bad.push(`升级动了目标的对接层：${p}——${ADAPTERS}/ 归目标仓自己实现，升级一个字节不碰`);
      }
    }
    // manifest 是写入面上唯一一个「一个文件两种所有权」的：机制登记归包、知识清单归目标。
    // 首次安装没有「升级前」可比，清单就是这次建的骨架，不判。
    if (wasInstalled && changed.includes(relManifest)) {
      const head = git(TARGET, ['show', `HEAD:${relManifest}`]);
      if (head.ok) {
        const was = knowledgeBlock(head.out);
        const now = knowledgeBlock(read(tgtManifest));
        if ((was?.text ?? null) !== (now?.text ?? null)) {
          bad.push('manifest 的 provides.knowledge 被升级改过'
            + '——知识激活随目标，不因升级重选（01 分册 §4）');
        }
      }
    }
  }
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
console.log('[adapt-scan] 核对通过：'
  + (SAME_TREE ? '（包即目标，diff 无对象）' : 'diff 全落在写入面内 / manifest 的知识清单未动 / ')
  + '入口文件含扩展段与标记区 / .gitignore 有章草稿那一行 / 包的 scripts 只有 core 与 adapters');
