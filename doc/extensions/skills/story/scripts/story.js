/**
 * story.js — /story 的数据对接层（本文件是部署环境间唯一需要替换的实现）
 *
 * 契约（CLI，**本 docstring 即唯一真源**；成功 0 / 失败非 0）：
 *   node story.js <init|archive|restore|review|help> <AR> [mcp-token] [--project-root <abs>]
 *   人类可读日志走 stderr；stdout 最后输出单行 JSON 结果：
 *   init    → {"mode":"init","reqNo":"...","parentNo":"SR...","rrNo":"RR...","success":true}
 *             落盘 AR/SR/RR 三套：各自 detail.json，加 RR/prd.md、SR/design.md，
 *             以及拉到的 AR/design.md（已有内容一律不覆盖——它是需求分析的预填输入）；
 *             拉到的 AR/design.md 无论有无内容都进后续需求分析，范围与覆盖由关卡定，
 *             本命令不做这个判断。
 *             工作区骨架（收件箱、RR/SR 占位件、design.md 空骨架）由 `story_flow.py init`
 *             在本命令之后补齐，两者互不依赖
 *   archive → {"mode":"archive","reqNo":"...","archived":true,"backupPath":"...","verified":true,"success":true}
 *             系统侧正文名固定为 design.md，归档是覆盖它而非新建：
 *             ①拉系统最新正文做远端备份 ②临时把 design.md 改名 design.bak.md
 *             ③story.md 改名 design.md 上传（review.md 作附件）④无论成败还原 design.bak.md
 *             故 **archive 前后工作区 AR/design.md 字节不变**；
 *             AR/story.md 与 AR/review.md 缺任一即失败，无降级路径。
 *             **门禁不在这里**：本文件是需求系统对接层的替身，内网是独立实现、从不调用扩展内容；
 *             归档前的校验由 /story 链的 story-build check 承担（SKILL 归档节 ①）
 *   restore → {"mode":"restore","reqNo":"...","restored":true,"verified":true,"success":true}
 *             从最新备份解析源数据、**重新上传回系统**，恢复的是平台侧正文；本地 design.md 不变
 *   review  → {"mode":"review","reqNo":"...","fetched":true,"target":"AR/review.md",
 *              "backupPath":"AR/.review-backup/<ts>-review.md","status":"confirmed|unchanged","success":true}
 *             拉回评审人在系统上留下的反馈，**直接写入 AR/review.md**（先备份原件）。
 *             产出不是中间 JSON 而是写回 review.md：回流阶段模型的输入唯一就是它，
 *             人可能在系统上批注、也可能直接改本地文件，流程不关心来源。
 *             AR/review.md 不存在即失败（先跑 /spec 产出首版）。实现在同目录 review.js
 *   help    → 打印工作流程（纯文本，CLI 级帮助）
 *   失败    → {"mode":"<命令>","reqNo":"...","success":false,"error":"..."}
 *
 * mcp-token：第三位置参数（token.js 获取）。本实现不校验、不使用；
 * 部署环境用它调 mcp 拉取/归档需求文档，缺失时应报错退出。
 *
 * 本实现是本地替身：RR/SR 取自 test/story/mock-data/（评测域的演示数据源），
 * 「需求系统」的读写以 stderr 占位打印模拟（见 uploadToSystem / fetchSystemCarrier）。
 * 替换本文件时保持上述 CLI 契约不变——
 * 不允许出现「文档写这个、本地干那个」的分叉：那正是本地测不出真实契约问题的成因。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

// mock-data 属评测域，自脚本目录上溯五层到仓库根再下探 test/story/mock-data。
// 本文件是本地替身、不进交付，允许依赖 test/ 下的演示数据。
const MOCK_DATA_DIR = path.resolve(__dirname, '..', '..', '..', '..', '..', 'test', 'story', 'mock-data');

function log(msg) {
  console.error(`[story.js] ${msg}`);
}

function emit(obj) {
  console.log(JSON.stringify(obj));
}

function fail(msg) {
  console.error(`[story.js] ${msg}`);
  emit({ mode: cmd ?? null, reqNo: ar ?? null, success: false, error: msg });
  process.exit(1);
}

function featuresDir(projectRoot) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'framework.config.json'), 'utf-8'));
    if (typeof (cfg.paths && cfg.paths.features_dir) === 'string' && cfg.paths.features_dir.trim()) {
      return cfg.paths.features_dir.trim();
    }
  } catch (_) {
    /* 回落默认 */
  }
  return 'doc/features';
}

function ts() {
  // 本地时间（备份/回执文件名），避免 UTC 裸值与本地时序误读
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  );
}

function writeIfAbsent(target, content) {
  if (fs.existsSync(target)) {
    log(`已存在，跳过：${target}`);
    return false;
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, 'utf-8');
  log(`生成：${target}`);
  return true;
}

function renderMock(file, ids) {
  let s = fs.readFileSync(file, 'utf-8');
  for (const [k, v] of Object.entries(ids)) s = s.split(`{{${k}}}`).join(v);
  return s;
}

function firstHeading(file, fallback) {
  try {
    const m = fs.readFileSync(file, 'utf-8').match(/^#\s+(.+)$/m);
    if (m) return m[1].trim();
  } catch (_) {
    /* 回落 */
  }
  return fallback;
}

/** 需求单据元数据。真实系统按单号返回，本地从已落盘材料的标题合成。 */
function writeDetail(target, detail) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(detail, null, 2)}\n`, 'utf-8');
  log(`生成：${target}`);
}

/**
 * 上传归档件到需求系统——占位实现；对接真实系统时在此用 mcp-token 调用上传接口。
 *
 * 归档是**多文件**的：正文 + 附件。正文在系统侧的名字固定为 design.md，本地的 story.md
 * 改名后上传占的就是这个位；review.md 作附件，评审者在它上面批注。
 *
 * @param {string} ar 单号
 * @param {{path:string, role:string}[]} files 待上传文件，role 为「正文」/「附件」
 */
function uploadToSystem(ar, files) {
  for (const f of files) {
    log(`（占位）上传${f.role}到需求系统：${ar} ← ${f.path}（对接真实系统时实现）`);
  }
}

/**
 * 取系统当前正文（design.md）用于远端备份——占位实现。
 *
 * 真实系统按单号拉取；本地用上一次归档回执模拟「系统上现在是什么」，
 * 从没归档过就退回本地 design.md（等同于系统尚是 init 落下的那一版）。
 */
function fetchSystemCarrier(featureRoot, localAr) {
  const archiveDir = path.join(featureRoot, '.archive');
  if (fs.existsSync(archiveDir)) {
    const prior = fs.readdirSync(archiveDir).filter(f => /^story-\d+\.md$/.test(f)).sort();
    if (prior.length > 0) return path.join(archiveDir, prior[prior.length - 1]);
  }
  return fs.existsSync(localAr) ? localAr : null;
}

function backup(featureRoot, label, srcFile) {
  if (!srcFile || !fs.existsSync(srcFile)) return null;
  const dir = path.join(featureRoot, '.backup');
  fs.mkdirSync(dir, { recursive: true });
  const dest = path.join(dir, `AR-design-${label}-${ts()}.md`);
  fs.copyFileSync(srcFile, dest);
  log(`备份：${dest}`);
  return dest;
}

/**
 * 材料层可显式声明父子关系与材料归属；缺省时按编号推导（1:1 假设）。
 *
 * **两种「读不到」要分开**：某个单号没有专用 detail 文件是设计内的降级（按编号推导即可）；
 * 而整个材料目录不存在，说明这条拉取路径实际在空转——那是设施缺失，必须出声。
 * 用同一个 catch 把两者吞成一样，会让「替身没接上」看起来和「正常走默认」毫无区别。
 */
function readMockDetail(ar) {
  if (!fs.existsSync(MOCK_DATA_DIR)) {
    log(`材料目录不存在：${MOCK_DATA_DIR}——本地替身没有任何上游材料可拉，`
      + '后续将只生成占位件。接真实需求系统时这条路径由系统接入替换。');
    return {};
  }
  const detailPath = path.join(MOCK_DATA_DIR, `${ar}-detail.json`);
  if (!fs.existsSync(detailPath)) return {};   // 无专用声明：按编号推导，设计内
  try {
    return JSON.parse(fs.readFileSync(detailPath, 'utf-8'));
  } catch (e) {
    log(`材料声明解析失败（${detailPath}）：${e.message}——按编号推导继续`);
    return {};
  }
}

// ---------------------------------------------------------------------------
function pullMaterials(ar, featureRoot, localAr, ids) {
  const mockDir = MOCK_DATA_DIR;
  // 用例可为特定 AR 提供更丰富的上游材料；无专用文件时仍使用默认材料。
  // 兄弟 AR（同一 SR 拆出的多个 AR）经 `materials` 指向同一套材料。
  // 选择发生在数据接入层，不向使用方暴露任何判据。
  const owner = readMockDetail(ar).materials ?? ar;
  const prdMock = path.join(mockDir, `${owner}-RR-prd.md`);
  const srMock = path.join(mockDir, `${owner}-SR-design.md`);
  const rrPath = path.join(featureRoot, 'RR', 'prd.md');
  const srPath = path.join(featureRoot, 'SR', 'design.md');
  // 上游文档按**材料归属方**的身份渲染：共享给兄弟 AR 时是同一份文档，
  // 按各自 AR 号重渲染会让同一份 SR 在两个 AR 下内容不同。
  const upstreamIds = { ...ids, AR: owner };
  writeIfAbsent(rrPath, renderMock(fs.existsSync(prdMock) ? prdMock : path.join(mockDir, 'RR-prd.md'), upstreamIds));
  writeIfAbsent(srPath, renderMock(fs.existsSync(srMock) ? srMock : path.join(mockDir, 'SR-design.md'), upstreamIds));

  writeDetail(path.join(featureRoot, 'RR', 'detail.json'), {
    reqNo: ids.RR, type: 'RR', title: firstHeading(rrPath, `${ids.RR} 产品需求`),
  });
  writeDetail(path.join(featureRoot, 'SR', 'detail.json'), {
    reqNo: ids.SR, type: 'SR', title: firstHeading(srPath, `${ids.SR} 系统设计`), rrNo: ids.RR,
  });
  writeDetail(path.join(featureRoot, 'AR', 'detail.json'), {
    reqNo: ids.AR, type: 'AR', title: firstHeading(localAr, `${ids.AR} 开发需求`),
    parentNo: ids.SR, rrNo: ids.RR,
  });
}

function cmdInit(ar, featureRoot, localAr, ids) {
  pullMaterials(ar, featureRoot, localAr, ids);
  log('材料已落盘。接着跑 `story_flow.py init` 建工作区骨架（收件箱、占位件、design.md 空骨架）。');
  emit({ mode: 'init', reqNo: ar, parentNo: ids.SR, rrNo: ids.RR, success: true });
}

function cmdArchive(ar, featureRoot, localAr, projectRoot) {
  // 归档是两份：叙事主件 story.md（正文）+ 决策件 review.md（附件）。
  // 两份都是 spec 阶段的产物，本命令只搬运不生成；缺任一即停，无降级路径——
  // 缺就停，比默默传个次品强（spec.md 含仓内路径、不自包含，顶不了正文）。
  // 决策件承载上线决策与待定项，且评审者在它上面线上批注——不传上去评审就没有批注载体。
  const storyPath = path.join(featureRoot, 'AR', 'story.md');
  const notesPath = path.join(featureRoot, 'AR', 'review.md');
  for (const [p, name] of [[storyPath, 'AR/story.md'], [notesPath, 'AR/review.md']]) {
    if (!fs.existsSync(p)) {
      fail(
        `${name} 不存在，无可归档物：${ar}。` +
          '它是 spec 阶段三份产物之一（spec.md / review.md / story.md）——请回 /spec 补齐后重试。'
      );
    }
  }
  // ① 系统侧正文名固定为 design.md，归档是覆盖它——先把系统当前那一版备份下来，
  //    restore 靠的就是这份备份。
  const backupPath = backup(featureRoot, 'remote', fetchSystemCarrier(featureRoot, localAr));

  // ②③④ 临时改名 → 上传 → 无论成败还原。工作区 design.md 由此在 archive 前后字节不变：
  //     它的身份只有「RR+SR 提取件」一种，借位只在上传的这一瞬间，且由 finally 兜住。
  const bakPath = path.join(featureRoot, 'AR', 'design.bak.md');
  const borrowed = fs.existsSync(localAr);
  if (borrowed) fs.renameSync(localAr, bakPath);
  try {
    uploadToSystem(ar, [
      { path: storyPath, role: '正文（AR/story.md → 系统 design.md）' },
      { path: notesPath, role: '附件（评审记录）' },
    ]);
  } finally {
    if (borrowed) fs.renameSync(bakPath, localAr);
  }

  // 本地回执：归档发生过什么、归的是哪一版，留一份可回查的证据。
  const archiveDir = path.join(featureRoot, '.archive');
  fs.mkdirSync(archiveDir, { recursive: true });
  const stamp = ts();
  const receipt = path.join(archiveDir, `story-${stamp}.md`);
  const notesReceipt = path.join(archiveDir, `review-${stamp}.md`);
  fs.copyFileSync(storyPath, receipt);
  fs.copyFileSync(notesPath, notesReceipt);
  const verified = fs.existsSync(receipt) && fs.existsSync(notesReceipt);
  log(`归档回执：${ar} | 正文=AR/story.md | 附件=AR/review.md | 存档=${receipt}、${notesReceipt}`);
  emit({ mode: 'archive', reqNo: ar, archived: true, backupPath, verified, success: true });
}

function cmdRestore(ar, featureRoot) {
  const dir = path.join(featureRoot, '.backup');
  const all = fs.existsSync(dir)
    ? fs.readdirSync(dir).filter(f => /^AR-design-(remote|local)-\d+\.md$/.test(f))
    : [];
  if (all.length === 0) fail(`无可用备份：${dir}（restore 仅在 archive 之后可用）`);
  // 优先取「系统上一版」（remote 备份）；无远端备份时退回本地旧版。按时间戳取最新。
  const byTs = arr => arr.sort((a, b) => a.match(/(\d+)\.md$/)[1].localeCompare(b.match(/(\d+)\.md$/)[1]));
  const remotes = all.filter(f => f.includes('-remote-'));
  const pool = remotes.length > 0 ? remotes : all;
  const latest = path.join(dir, byTs(pool)[pool.length - 1]);

  // 恢复的是**平台侧**正文：把备份重新上传回系统，回退 archive 对系统的那次覆盖。
  // 本地 AR/design.md 一个字节都不动——它本来就没被 archive 改过。
  uploadToSystem(ar, [{ path: latest, role: '正文（备份 → 系统 design.md）' }]);
  log(`已用备份恢复系统正文（${remotes.length > 0 ? '系统上一版' : '本地旧版'}）：${latest}`);
  log('本地 AR/design.md 未改动。');
  emit({ mode: 'restore', reqNo: ar, restored: true, verified: true, success: true });
}

function cmdReview(ar, featureRoot) {
  // 实现拆在同目录 review.js——部署环境统一走本文件的 CLI，内部怎么组织是各自的事。
  const { fetchReview } = require('./review.js');
  const receipt = fetchReview({ ar, featureRoot, log, ts });
  emit(receipt);
  if (!receipt.success) process.exit(1);
}

function cmdHelp() {
  console.log(`[story.js] /story 工作流程（按预期开发顺序）
  1. /story init <AR>     拉取 AR/SR/RR 单据与材料 + 生成 AR/design.md 空模板（触发 AI 按 rules/ar_design_init.md 提取；覆盖前须确认）
  2. /spec                需求规格三产物：spec.md（代码要求）+ AR/review.md（人的决策）+ AR/story.md（归档件），门禁校验三份齐备
  3. /story archive <AR>  以 AR/story.md 为正文、AR/review.md 为附件归档上传（系统正文名固定 design.md；工作区文件不变）
  4. /story restore <AR>  用最新备份把系统正文恢复回上一版（本地 design.md 不变）
  5. /story review <AR>   拉回评审回稿写入 AR/review.md（先备份），再据此修订 spec
  详细规则：doc/extensions/skills/story/SKILL.md`);
}

// ---------------------------------------------------------------------------
const cmd = process.argv[2];
const ar = process.argv[3];
let mcpToken;
let projectRootArg;
let argError;
for (let i = 4; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a === '--project-root') {
    projectRootArg = process.argv[++i];
    if (projectRootArg === undefined) argError = '--project-root 缺少值';
  } else if (a.startsWith('--project-root=')) {
    projectRootArg = a.slice('--project-root='.length);
  } else if (a.startsWith('--')) {
    argError = `未知参数：${a}`;
  } else if (mcpToken === undefined) {
    mcpToken = a;
  } else {
    argError = `多余参数：${a}`;
  }
}

const USAGE = '用法：node story.js <init|archive|restore|review|help> <AR> [mcp-token] [--project-root <abs>]';
const CMDS = ['init', 'archive', 'restore', 'review', 'help'];
if (argError) fail(`${argError}。${USAGE}`);
if (!CMDS.includes(cmd)) {
  fail(USAGE);
}
if (cmd === 'help') {
  cmdHelp();
  process.exit(0);
}
if (!ar || !/^[\w.-]+$/.test(ar)) fail(`非法 AR 单号：「${ar ?? ''}」`);
// 本实现不校验 mcpToken；部署环境在此校验缺失即失败，并用它调 mcp
if (!mcpToken) log('未传入 mcp-token（本地容忍；部署环境将拒绝执行）');

// scripts → story → skills → extensions → doc → 实例根
const projectRoot = path.resolve(projectRootArg ?? path.join(__dirname, '..', '..', '..', '..', '..'));
const featureRoot = path.join(projectRoot, featuresDir(projectRoot), ar);
const localAr = path.join(featureRoot, 'AR', 'design.md');
// 父子关系：真实系统按单号返回，本地按编号推导。一个 SR 可拆多个 AR，编号推不出兄弟关系，
// 故允许材料层用 <AR>-detail.json 显式声明（parentNo / rrNo / materials）。
const num = ar.replace(/^AR/i, '');
const declared = readMockDetail(ar);
const ids = {
  AR: ar,
  SR: declared.parentNo ?? `SR${num}`,
  RR: declared.rrNo ?? `RR${num}`,
};

if (cmd === 'init') cmdInit(ar, featureRoot, localAr, ids);
else if (cmd === 'archive') cmdArchive(ar, featureRoot, localAr, projectRoot);
else if (cmd === 'restore') cmdRestore(ar, featureRoot);
else if (cmd === 'review') cmdReview(ar, featureRoot);
