/**
 * story.js — /story 的数据对接层（本文件是部署环境间唯一需要替换的实现）
 *
 * 契约（CLI，**本 docstring 即唯一真源**；成功 0 / 失败非 0）：
 *   node story.js <init|archive|restore|fetch|help> <AR> [mcp-token]
 *       [--project-root <abs>] [--out <暂存目录>]
 *   人类可读日志走 stderr；stdout 最后输出单行 JSON 结果：
 *   init    → {"mode":"init","reqNo":"...","parentNo":"SR...","rrNo":"RR...","success":true}
 *             按单号从需求系统拉单据：AR 自己、它挂的 SR、SR 挂的 RR，各写一份
 *             detail.json，正文分别落 RR/prd.md、SR/design.md、AR/design.md。
 *             AR/design.md 是**需求分析的预填输入**，系统上有就拉下来、本地已有一律不覆盖；
 *             它有没有内容、范围够不够，由后续关卡判，本命令不做这个判断。
 *             系统上查无此单即失败——单号打错时必须当场停住，而不是落一地占位件；
 *             系统上某份正文缺失则**不写**该文件，留给 `story_flow.py init` 落占位件。
 *             工作区骨架（收件箱、占位件、design.md 空骨架）由它在本命令之后补齐，
 *             两者互不依赖
 *   archive → {"mode":"archive","reqNo":"...","archived":true,"backupPath":"...","verified":true,"success":true}
 *             系统侧正文名固定为 design.md，归档是覆盖它而非新建：
 *             ①系统当前正文备份进该单的历史版本目录（restore 靠的就是它）
 *             ②AR/story.md 的内容写成系统正文 ③AR/review.md 作为附件上传
 *             ④`verified` = 系统侧两份与本地两份字节一致。
 *             **工作区一个字节都不动**——归档是往系统上写，不是在本地搬文件；
 *             AR/story.md 与 AR/review.md 缺任一即失败，无降级路径。
 *             **门禁不在这里**：本文件是需求系统对接层的替身，内网是独立实现、从不调用扩展内容；
 *             归档前的校验由 /story 链的 story-build check 承担（SKILL 归档节 ①）
 *   restore → {"mode":"restore","reqNo":"...","restored":true,"verified":true,"success":true}
 *             把该单最新的历史版本写回系统正文，回退 archive 那次覆盖；
 *             没有历史版本即失败（restore 仅在 archive 之后可用）。本地 design.md 不变
 *   fetch   → {"mode":"fetch","reqNo":"...","out":"<暂存目录>","fetched":3,"failed":0,
 *              "items":[{"name":"...","label":"...","ticket":"...","status":"fetched|same|absent|failed",
 *                        "digest":"sha256:...","origin":"<单号>/<文件>","bytes":123}],"success":true}
 *             **只读取材**：把这张单现在关联到的上游（AR/SR/RR 正文）与评审回稿取回
 *             `--out` 指的暂存目录，并写一份 `fetched.json` 取材回执。
 *             **一个业务文件都不写**——不碰 AR/review.md，也不碰 AR/design.md；
 *             写进正文是模型读完之后的事。`status` 四态分开：取到 / 与本地逐字相同（不落盘）/
 *             系统上没有（常态）/ 读取失败（故障），混成一个的话一次读取错误会被当成「评审没提意见」。
 *             本地单（`local-` 开头）明确不适用：不取 token、不访问系统，当场失败。
 *             `--out` 必填，没有默认落点：默认一个的话，两个单同时更新会写进同一处
 *   help    → 打印工作流程（纯文本，CLI 级帮助）
 *   失败    → {"mode":"<命令>","reqNo":"...","success":false,"error":"..."}
 *
 * mcp-token：第三位置参数（token.js 获取）。本实现不校验、不使用；
 * 部署环境用它调 mcp 拉取/归档需求文档，缺失时应报错退出。
 *
 * **本实现是本地替身**：需求系统是一个本地目录，一个子目录就是一张单——
 *
 *     <system>/<单号>/detail.json          {reqNo,type:"RR|SR|AR",title,parentNo?,rrNo?}
 *     <system>/<RR号>/prd.md               产品需求正文
 *     <system>/<SR号>/design.md            系统设计正文
 *     <system>/<AR号>/design.md            开发需求正文（archive 覆盖的就是它）
 *     <system>/<AR号>/history/             历史版本，archive 备份、restore 取用
 *     <system>/<AR号>/attachments/         附件，评审记录传到这里
 *     <system>/<AR号>/review-feedback.md   评审人留下的回稿（fetch 取它）
 *
 * 目录位置读环境变量 `STORY_REQUIREMENT_SYSTEM_DIR`，未设时取工程内的默认演示目录。
 * **系统只承载 md**：真实需求系统的正文是纯文本单据，图片一律走别的渠道（人手上的
 * 设计文档、原型说明），因此本替身不上传也不拉取任何图片——把图片塞进系统，
 * 本地就会跑出一条真实环境里不存在的取材路径。
 *
 * 替换本文件时保持上述 CLI 契约不变——
 * 不允许出现「文档写这个、本地干那个」的分叉：那正是本地测不出真实契约问题的成因。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

/** 需求系统的默认落点：本工程演示用；正式测试与部署环境都由环境变量指定。 */
const DEFAULT_SYSTEM_DIR = path.join('test', 'story', 'requirement-system');
const SYSTEM_DIR_ENV = 'STORY_REQUIREMENT_SYSTEM_DIR';

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
  // 本地时间（历史版本/备份文件名），避免 UTC 裸值与本地时序误读
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

function writeDetail(target, detail) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(detail, null, 2)}\n`, 'utf-8');
  log(`生成：${target}`);
}

// ---------------------------------------------------------------------------
// 需求系统（本替身 = 一个本地目录）

/** 系统目录。环境变量优先；未设时用工程内的默认演示目录。 */
function systemRoot(projectRoot) {
  const configured = String(process.env[SYSTEM_DIR_ENV] ?? '').trim();
  return configured ? path.resolve(configured) : path.join(projectRoot, DEFAULT_SYSTEM_DIR);
}

/**
 * 取一张单。**三种「取不到」要分开**，它们的补救动作完全不同：
 *   目录不在 = 这条拉取路径没接上（环境没配好）；
 *   单据不在 = 单号打错或该单还没建（停下来问人）；
 *   detail 坏了 = 单据本身有问题（找需求系统的人）。
 * 用同一个 catch 吞成一样，「替身没接上」看起来就和「查无此单」毫无区别。
 */
function readTicket(system, no) {
  if (!fs.existsSync(system)) {
    return { found: false, reason: 'no_system', detail: null };
  }
  const detailPath = path.join(system, no, 'detail.json');
  if (!fs.existsSync(detailPath)) {
    return { found: false, reason: 'no_ticket', detail: null };
  }
  try {
    return { found: true, reason: null, detail: JSON.parse(fs.readFileSync(detailPath, 'utf-8')) };
  } catch (e) {
    return { found: false, reason: `bad_detail:${e.message}`, detail: null };
  }
}

/** 系统上这张单的某份文件；不存在返回 null（缺正文是常态，不是异常）。 */
function ticketText(system, no, ...parts) {
  if (!no) return null;
  const target = path.join(system, no, ...parts);
  return fs.existsSync(target) ? fs.readFileSync(target, 'utf-8') : null;
}

function ticketTitle(system, no, fallback) {
  const ticket = readTicket(system, no);
  const title = ticket.detail && ticket.detail.title;
  return typeof title === 'string' && title.trim() ? title.trim() : fallback;
}

/** 系统侧写入：目录按需建，路径统一以「相对系统根」的形式回执。 */
function systemWrite(system, relParts, content) {
  const target = path.join(system, ...relParts);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, 'utf-8');
  const rel = relParts.join('/');
  log(`需求系统 ← ${rel}`);
  return rel;
}

// ---------------------------------------------------------------------------
function cmdInit(ar, featureRoot, localAr, system) {
  const ticket = readTicket(system, ar);
  if (!ticket.found) {
    if (ticket.reason === 'no_system') {
      fail(`需求系统不可达：${system} 不存在。`
        + `本地替身以该目录为需求系统，请设置环境变量 ${SYSTEM_DIR_ENV} 指向它——`
        + '这不是「查无此单」，单号本身还没被查过。');
    }
    if (ticket.reason === 'no_ticket') {
      fail(`查无此单：需求系统里没有 ${ar}。请确认单号，或确认该单是否已在系统上建立。`);
    }
    fail(`单据数据有问题（${ar}）：${ticket.reason}。请联系需求系统侧核对该单。`);
  }

  const detail = ticket.detail;
  const ids = {
    AR: ar,
    SR: typeof detail.parentNo === 'string' && detail.parentNo.trim() ? detail.parentNo.trim() : null,
    RR: typeof detail.rrNo === 'string' && detail.rrNo.trim() ? detail.rrNo.trim() : null,
  };

  // 正文：系统上有才落。**缺就不写**——写个空文件会让下游分不清
  //「系统上没有这部分内容」和「已经拉到了、内容确实是空的」。
  const prd = ticketText(system, ids.RR, 'prd.md');
  const srDesign = ticketText(system, ids.SR, 'design.md');
  const arDesign = ticketText(system, ar, 'design.md');
  const pulled = [];
  if (prd !== null) { writeIfAbsent(path.join(featureRoot, 'RR', 'prd.md'), prd); pulled.push('RR/prd.md'); }
  if (srDesign !== null) { writeIfAbsent(path.join(featureRoot, 'SR', 'design.md'), srDesign); pulled.push('SR/design.md'); }
  if (arDesign !== null) { writeIfAbsent(localAr, arDesign); pulled.push('AR/design.md'); }

  writeDetail(path.join(featureRoot, 'AR', 'detail.json'), {
    reqNo: ar, type: 'AR', title: ticketTitle(system, ar, `${ar} 开发需求`),
    parentNo: ids.SR, rrNo: ids.RR,
  });
  if (ids.SR) {
    writeDetail(path.join(featureRoot, 'SR', 'detail.json'), {
      reqNo: ids.SR, type: 'SR', title: ticketTitle(system, ids.SR, `${ids.SR} 系统设计`),
      rrNo: ids.RR,
    });
  }
  if (ids.RR) {
    writeDetail(path.join(featureRoot, 'RR', 'detail.json'), {
      reqNo: ids.RR, type: 'RR', title: ticketTitle(system, ids.RR, `${ids.RR} 产品需求`),
    });
  }

  const missing = ['RR/prd.md', 'SR/design.md'].filter(rel => !pulled.includes(rel));
  if (missing.length > 0) {
    log(`系统上没有：${missing.join('、')}——这部分材料要另外拿到并走收件箱导入。`);
  }
  log('材料已落盘。接着跑 `story_flow.py init` 建工作区骨架（收件箱、占位件、design.md 空骨架）。');
  emit({ mode: 'init', reqNo: ar, parentNo: ids.SR, rrNo: ids.RR, success: true });
}

function cmdArchive(ar, featureRoot, system) {
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
  const ticket = readTicket(system, ar);
  if (!ticket.found) {
    fail(`需求系统里没有 ${ar}（${ticket.reason}），无处可归。`
      + '没有系统单据的本地单不走归档：交付终点就是仓内那三份产物。');
  }

  // ① 系统当前正文先存一份历史版本——归档是覆盖，restore 靠的就是它。
  //    系统上还没有正文时不留空历史：restore 回一个空文件比报「无历史」更难查。
  const current = ticketText(system, ar, 'design.md');
  let backupPath = null;
  if (current !== null) {
    backupPath = systemWrite(system, [ar, 'history', `design-${ts()}.md`], current);
  } else {
    log('系统上尚无正文，本次归档是首次写入，没有可备份的历史版本。');
  }

  // ② 正文 ③ 附件。**只上传 md，不上传图片、不改写正文里的链接**——
  //    系统不承载图片，改写链接会让归档件与本地件分叉成两份不同的东西。
  const storyText = fs.readFileSync(storyPath, 'utf-8');
  const notesText = fs.readFileSync(notesPath, 'utf-8');
  systemWrite(system, [ar, 'design.md'], storyText);
  systemWrite(system, [ar, 'attachments', 'review.md'], notesText);

  // ④ 传上去的和本地的是不是同一份东西——回执里的 verified 只认这个。
  const verified = ticketText(system, ar, 'design.md') === storyText
    && ticketText(system, ar, 'attachments', 'review.md') === notesText;
  log(`归档完成：${ar} | 正文=AR/story.md → ${ar}/design.md | 附件=AR/review.md → ${ar}/attachments/review.md`);
  log('工作区未改动。');
  emit({ mode: 'archive', reqNo: ar, archived: true, backupPath, verified, success: true });
}

function cmdRestore(ar, system) {
  const historyDir = path.join(system, ar, 'history');
  const versions = fs.existsSync(historyDir)
    ? fs.readdirSync(historyDir).filter(f => /^design-\d+\.md$/.test(f)).sort()
    : [];
  if (versions.length === 0) {
    fail(`${ar} 在需求系统上没有历史版本：${historyDir}（restore 仅在 archive 之后可用）`);
  }
  const latest = versions[versions.length - 1];
  const content = fs.readFileSync(path.join(historyDir, latest), 'utf-8');
  systemWrite(system, [ar, 'design.md'], content);
  const verified = ticketText(system, ar, 'design.md') === content;
  log(`已把系统正文恢复到上一版：${ar}/history/${latest}`);
  log('本地 AR/design.md 未改动。');
  emit({ mode: 'restore', reqNo: ar, restored: true, verified, success: true });
}

/**
 * fetch —— **只读取材**：把这张单现在关联到的上游与评审内容取回暂存区。
 *
 * 与 `init` 的分工：`init` 是第一次建工作区，不覆盖已有文件；`fetch` 是之后每一次
 * 「上面有没有新东西」，所以它**一个业务文件都不写**，只往 `--out` 指的暂存目录里放，
 * 并留一份清单说清每一份的来历。写进正文是模型读完之后的事，不在这里发生。
 *
 * 它不假设「系统上的就是最新的、本地那一版是旧的」：人可能刚在本地改过 `AR/review.md`，
 * 覆盖就把他的修改吃掉了。所以取回来只放暂存，采不采用、怎么并进去，由读过原文的人和模型定。
 *
 * 取材回执 `fetched.json` 逐份记四件事：它是什么（来源身份）、内容摘要、原件在系统上的位置、
 * 取到没有。**缺席与失败分开**：系统上本来就没有评审回稿是常态，读不出来是故障，
 * 混成一个的话，一次读取错误会被当成「评审没提意见」。
 */
function cmdFetch(ar, featureRoot, system, outDir) {
  if (/^local[-_]/i.test(ar)) {
    fail(`${ar} 是本地单：它不挂在需求系统上，fetch 不适用（也不取 token、不访问系统）。`
      + '本地单的材料由人直接放进 inbox/');
  }
  const ticket = readTicket(system, ar);
  if (!ticket.found) {
    fail(`${ar} 在需求系统上取不到（${ticket.reason}）：先确认单号，或这张单还没建。`
      + 'fetch 不落占位件——取不到就是取不到');
  }
  const srNo = ticket.detail && ticket.detail.parentNo;
  const rrNo = ticket.detail && ticket.detail.rrNo;
  // 三份正文进 inbox，与人补的料走同一条导入链。`local` 是本地对应的那几份：
  // 取回来的与其中一份逐字相同就不落盘（`same`）——放进去它就是一份「未并入的原件」，
  // 每次 update 都会被报成新料。本单的系统正文与本地 story 相同，就是自己归档上去的那一版。
  // 评审回稿不是需求正文，导入链没有它的类别：放在回执旁边，由模型读，不进 inbox。
  const src = path.join(featureRoot, 'AR', 'story-src');
  const wanted = [
    { name: 'AR-design.md', label: '开发需求正文（本单）', no: ar, parts: ['design.md'],
      local: ['AR/design.md', 'AR/story.md'] },
    { name: 'SR-design.md', label: '系统设计正文', no: srNo, parts: ['design.md'], local: ['SR/design.md'] },
    { name: 'RR-prd.md', label: '产品需求正文', no: rrNo, parts: ['prd.md'], local: ['RR/prd.md'] },
    { name: 'review-feedback.md', label: '评审人留下的回稿', no: ar, parts: ['review-feedback.md'],
      local: [], dir: src },
  ];
  const items = wanted.map((w) => {
    if (!w.no) return { ...pick(w), status: 'absent', note: '这张单上没有挂它' };
    let text = null;
    try {
      text = ticketText(system, w.no, ...w.parts);
    } catch (e) {
      return { ...pick(w), status: 'failed', note: e.message };
    }
    if (text === null) return { ...pick(w), status: 'absent', note: '系统上现在没有这一份' };
    const facts = {
      digest: `sha256:${crypto.createHash('sha256').update(text).digest('hex').slice(0, 16)}`,
      origin: [w.no, ...w.parts].join('/'),
      bytes: Buffer.byteLength(text, 'utf-8'),
    };
    const same = w.local.find(rel => readOr(path.join(featureRoot, rel)) === text);
    if (same) return { ...pick(w), status: 'same', note: `与本地 ${same} 逐字相同`, ...facts };
    const dir = w.dir || outDir;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, w.name), text, 'utf-8');
    return { ...pick(w), status: 'fetched', saved: path.relative(featureRoot, path.join(dir, w.name))
      .split(path.sep).join('/'), ...facts };
  });
  const receipt = { mode: 'fetch', reqNo: ar, fetchedAt: ts(), items };
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(src, 'fetched.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  const got = items.filter(i => i.status === 'fetched').length;
  const bad = items.filter(i => i.status === 'failed').length;
  log(`取回 ${got} 份到 ${outDir}${bad ? `，${bad} 份读取失败` : ''}；一个业务文件都没动`);
  emit({ mode: 'fetch', reqNo: ar, out: outDir, fetched: got, failed: bad,
    items, success: bad === 0 });
  if (bad) process.exit(1);
}

function readOr(file) {
  try { return fs.readFileSync(file, 'utf-8'); } catch { return null; }
}

/** 清单里每份都带的身份三件：文件名、它是什么、在系统上挂在哪张单下。 */
function pick(w) {
  return { name: w.name, label: w.label, ticket: w.no || null };
}

function cmdHelp() {
  console.log(`[story.js] /story 工作流程（按预期开发顺序）
  1. /story init <AR>     拉取 AR/SR/RR 单据与材料 + 生成 AR/design.md 空模板（触发 AI 按 rules/ar_design_init.md 提取；覆盖前须确认）
  2. /spec                需求规格三产物：spec.md（代码要求）+ AR/review.md（人的决策）+ AR/story.md（归档件），门禁校验三份齐备
  3. /story archive <AR>  以 AR/story.md 为正文、AR/review.md 为附件归档上传（系统正文名固定 design.md；工作区文件不变）
  4. /story restore <AR>  把系统正文恢复回上一版（本地 design.md 不变）
  5. /story update <AR>   取回上游与评审的新内容，据它更新已有产物（取材只写 inbox，不覆盖当前稿）
  详细规则：doc/extensions/skills/story/SKILL.md`);
}

// ---------------------------------------------------------------------------
const cmd = process.argv[2];
const ar = process.argv[3];
let mcpToken;
let projectRootArg;
let outArg;
let argError;
for (let i = 4; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a === '--project-root') {
    projectRootArg = process.argv[++i];
    if (projectRootArg === undefined) argError = '--project-root 缺少值';
  } else if (a.startsWith('--project-root=')) {
    projectRootArg = a.slice('--project-root='.length);
  } else if (a === '--out') {
    outArg = process.argv[++i];
    if (outArg === undefined) argError = '--out 缺少值';
  } else if (a.startsWith('--out=')) {
    outArg = a.slice('--out='.length);
  } else if (a.startsWith('--')) {
    argError = `未知参数：${a}`;
  } else if (mcpToken === undefined) {
    mcpToken = a;
  } else {
    argError = `多余参数：${a}`;
  }
}

const USAGE = '用法：node story.js <init|archive|restore|fetch|help> <AR> [mcp-token] '
  + '[--project-root <abs>] [--out <本单 inbox>（fetch 必填）]';
const CMDS = ['init', 'archive', 'restore', 'fetch', 'help'];
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

// 本脚本住在 <实例根>/doc/extensions/skills/story/scripts/adapters/，
// 不传 --project-root 时从这里上溯六级回到实例根：
// adapters → scripts → story → skills → extensions → doc → 实例根
const projectRoot = path.resolve(
  projectRootArg ?? path.join(__dirname, '..', '..', '..', '..', '..', '..'));
const featureRoot = path.join(projectRoot, featuresDir(projectRoot), ar);
const localAr = path.join(featureRoot, 'AR', 'design.md');
const system = systemRoot(projectRoot);

if (cmd === 'init') cmdInit(ar, featureRoot, localAr, system);
else if (cmd === 'archive') cmdArchive(ar, featureRoot, system);
else if (cmd === 'restore') cmdRestore(ar, system);
else if (cmd === 'fetch') {
  // 落点必须由调用方指定（update 渲染好的那条命令里就是本单的 inbox）：
  // 默认一个落点的话，两个单同时更新会写进同一处。
  if (!outArg) fail(`fetch 要 --out <本单 inbox>：它只往那里写，不碰任何业务文件。${USAGE}`);
  cmdFetch(ar, featureRoot, system, path.resolve(projectRoot, outArg));
}
