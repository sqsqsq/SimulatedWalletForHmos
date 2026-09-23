/**
 * 正文的来源与材料贡献清单 —— 这份 story 据哪几份材料写成，哪一份还没在手里。
 *
 * 必需性只在这里判一次：起手预检与交付前的 check 读同一份结果。两处各判一次的话，
 * 同一份缺件会在一处说「本地单缺它正常」、在另一处说「它是必备来源」。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { isSystemRequirement, readText } from './context.mjs';
import { queryFlowStatus } from '../flow/client.mjs';
import { scanMaterialList } from './language.mjs';
import { appendixChapter, materialSubsectionName } from './appendix.mjs';
import { subsectionSpan } from './document.mjs';

/**
 * 合同声明的每个来源，读到了没有 —— **读不到的也要带回来**。
 *
 * 读不到就静默跳过的话，一整类材料会凭空缺席而零信号：那一份的内容从头到尾
 * 没进过任何一条判据的视野，从起手到交付没有一处提过。
 *
 * 这里只**读合同声明**：谁读到了、谁没读到。这一轮各自必不必需（远程单/本地单）
 * 由 `sourceStatus` 判，起手与交付前的 check 共用它，不在两处各写一份。
 *
 * 索引文件缺席**不是缺陷**：图片的身份与落点在 `materials.json`，那是唯一登记处。
 * 拿「目录里有图而索引不在」当阻断，等于要求作者为一份不承载登记的说明文件停下来。
 *
 * @returns {{docs: object[], missing: object[]}}
 */
function scanSources(ctx) {
  const docs = [], missing = [];
  for (const [doc, decl] of Object.entries(ctx.contract.sources ?? {})) {
    const rel = typeof decl === 'string' ? decl : decl?.path;
    if (!rel) continue;
    const obj = typeof decl === 'object' && decl ? decl : {};
    const abs = path.join(ctx.featureRoot, rel);
    const text = readText(abs);
    if (text !== null) {
      docs.push({
        doc, rel, text,
        // `derived`＝这一份是本轮流程自己生成的中间产物，不是上游给的材料。
        // 它只守业务编号，工程细节的家是它自己。
        derived: obj.derived === true,
      });
      continue;
    }
    // 读不到的带回来，必需性交给 sourceStatus。
    missing.push({ doc, rel, required: obj.required === true });
  }
  return { docs, missing };
}

/** 缺失来源报成一句话。必备与可选两种措辞，降级的那几份带上「为什么不算缺」。 */
export function missingSourceLine(m) {
  return `合同声明的来源 ${m.doc} 不存在：${m.rel}`
    + (m.required
      ? '——它是必备来源，缺了这一轮的材料就不完整'
      : `（${m.why ?? '可选来源'}，缺了是正常的）`);
}

//: 需求系统给的单才有的那两份。本地单没有它们是正常的——把本地单的 PRD 判成缺件，
//: 作者除了造一份假的没有别的路。本轮自己派生的产物（Spec、AR 提取稿）两种单都必需：
//: 跳过它等于拿不全的输入成文。
const REMOTE_ONLY_SOURCES = ['PRD', 'SE'];

/**
 * 合同声明的来源这一轮各自必不必需 —— **起手与交付前的 check 问的是同一份判定**。
 *
 * 两处各判一次，同一份缺件就会被说成两件事：起手说「本地单缺 PRD 正常」，
 * 交付前的 check 说「它是必备来源」。系统需求按编号认（`isSystemRequirement`）。
 *
 * @returns {{docs: object[], missing: object[], blocking: object[]}}
 */
export function sourceStatus(ctx) {
  const { docs, missing } = scanSources(ctx);
  const remote = isSystemRequirement(path.basename(ctx.featureRoot));
  const adjusted = missing.map(m => (remote || !REMOTE_ONLY_SOURCES.includes(m.doc)
    ? m
    : { ...m, required: false, why: '本地单没有需求系统给的这一份' }));
  return { docs, missing: adjusted, blocking: adjusted.filter(m => m.required) };
}

// --------------------------------------------------------------------------
// 正文定位：章、小节与附录机器区
// --------------------------------------------------------------------------

/** 路径的最后一段。判「正文提没提到这张图」用它——作者写文件名比写全路径自然。 */
export function basename(rel) {
  const parts = String(rel).split('/');
  return parts[parts.length - 1];
}

/**
 * 材料里的图片登记 —— 唯一来源是材料清单（`AR/story-src/materials.json`）。
 *
 * 登记的唯一来源是清单：它枚举磁盘上真实存在的图片文件，与谁给它写没写过
 * markdown 链接无关——按链接枚举的话，界面参考目录里只写了名字的那几张就不算数。
 *
 * 清单枚举的是磁盘上真实存在的图片文件，与谁给它写没写链接无关；同一张图复制到第二个
 * 落点时它按内容合并成一条，`paths` 列出全部落点——**图片的身份是它的内容，不是路径**。
 *
 * @returns {{kind:string,sha256:string,paths:string[]}[] | null | 'broken'}
 *   null = 没有清单（offline 或还没跑过 round）；'broken' = 清单坏了，两者不能混为一谈
 */
export function readManifest(ctx) {
  if (ctx.offline || !ctx.srcDir) return null;
  const text = readText(path.join(ctx.srcDir, 'materials.json'));
  if (text === null) return null;
  try { return JSON.parse(text.replace(/^\ufeff/, '')); } catch { return 'broken'; }
}

/**
 * 材料清单那一节**应当**列到的材料 —— 同样出自 `materials.json`。
 *
 * 这一节回答的是「据哪几份材料写成」。谁来定这个集合，决定了它是账还是倾倒区：
 * 由作者自由罗列时，容易把本轮自己生成的规格链进去，
 * 也出现过漏掉一整份的形态——读者据这一节把材料找出来，漏一份等于那份材料没人知道。
 *
 * 集合 = **这一轮拿到的初始资料**：流程正在消费的那几份正文（清单里 `kind: doc`
 * 且真的在盘上的），加收件箱里的原件——那份是人另外给的、没走需求系统，
 * 读者要知道有它。中间产物不在其中：本轮自己生成的规格与记录不是材料，
 * 它们压根不进清单。
 *
 * **图不在这一节**。图的去向是「引了没有、不引为什么」，那是每张图自己的属性，
 * 跟着内容走（同一张图换个名字、复制到第二个落点，判断还是那个）——所以登记在
 * 材料清单的说明库里（`--caption-image … --unused`），由 ④ 逐张核。
 * 写进这一节的话，读者要在「据哪几份材料写成」里读到十行图，
 * 而其中一半是别的需求的页面。
 *
 * **一份材料一行**：`paths` 有几个是它落了几处，不是几份材料。所以 `must` 的每一项
 * 是一组等价路径，列到其中任意一个就算数。
 *
 * @returns {{must: string[][]} | null | 'broken'}
 */
function materialListTargets(ctx) {
  const data = readManifest(ctx);
  if (data === null || data === 'broken') return data;
  if (!Array.isArray(data.materials)) return 'broken';
  const must = data.materials
    .filter(m => m?.kind === 'doc' && m.sha256 && Array.isArray(m.paths) && m.paths.length)
    .map(m => m.paths);
  for (const src of (Array.isArray(data.sources) ? data.sources : [])) {
    if (src?.file) must.push([`inbox/${src.file}`]);
  }
  return { must };
}

export function relFromFeature(ctx, target) {
  return path.relative(ctx.featureRoot, target).split(path.sep).join('/');
}

/** posix 风格拼接并规范化（`..` 逐段回退），跨平台一致。 */
export function joinPosix(base, ref) {
  const parts = String(base ?? '').split('/').filter(p => p && p !== '.');
  for (const seg of String(ref ?? '').split(/[\\/]/)) {
    if (seg === '..') { parts.pop(); continue; }
    if (!seg || seg === '.') continue;
    parts.push(seg);
  }
  return parts.join('/');
}

// --------------------------------------------------------------------------
// 从 spec 派生：story 相对 spec 只能增加，不能减少
// --------------------------------------------------------------------------

/**
 * story 的上游有哪几份 —— 系统设计与 spec，读不到的那份不算，不猜。
 *
 * 上游只列到这两份：产品需求文档里一般不画 `mermaid`，为它留一条通道是空的；
 * 真出现了，作者按内容搬进 story 就是，机器不为一份没有图的文档立判据。
 */
export function upstreamDocs(ctx) {
  const out = [];
  // 标签是图源标记里写的那个名字；路径以合同 `sources` 为准
  for (const [label, key] of [['SR', 'SE'], ['spec', 'SPEC']]) {
    const rel = ctx.contract.sources?.[key]?.path;
    const text = rel ? readText(path.join(ctx.featureRoot, rel)) : null;
    if (text !== null) out.push([label, text]);
  }
  return out;
}

/**
 * 材料清单那一节里的全部链接目标，带行号。
 *
 * 与 `scanMaterialList` 的行形态判分开：那条判「这一行是不是列表、有没有链接」，
 * 这里只把目标取出来，交给调用方判它在不在。两件事分开，报错才说得清是哪一件不成立。
 *
 * @returns {[number, string][]} `[行号, 链接目标]`
 */
function materialLinkTargets(body, baseLine = 0) {
  const out = [];
  const lines = String(body ?? '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    for (const m of lines[i].matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) out.push([baseLine + i, m[1]]);
  }
  return out;
}

/**
 * 把材料清单那一节里的 markdown 链接换成一个占位词，再交给仓内路径与文档坐标扫描。
 *
 * **原文链接是仓内路径唯一允许出现的位置**：归档件的读者打不开这个仓，但他要能
 *据这一行把那份材料找出来——链接是「据哪几份材料写成」这件事唯一可核的形态。
 * 豁免范围只到这一节的链接语法：同一行链接之外的文字照扫，别的章节照扫。
 */
export function redactMaterialLinks(storyText, ctx) {
  const appendix = appendixChapter(ctx.contract);
  const name = materialSubsectionName(ctx.contract);
  if (!appendix || !name) return storyText;
  const span = subsectionSpan(storyText, appendix.title, name);
  if (!span) return storyText;
  const lines = String(storyText).split(/\r?\n/);
  for (let i = span.start; i < span.end && i < lines.length; i++) {
    lines[i] = lines[i].replace(/\[[^\]]*\]\([^)\s]*\)/g, '原文链接');
  }
  return lines.join('\n');
}

/** 附录·材料清单的每一行：类别、文件名与链接由清单给，贡献由作者写。 */
export function materialListSkeleton(ctx) {
  const targets = materialListTargets(ctx);
  if (!targets || targets === 'broken') return [];
  // 类别取合同的 `sources[*].label`，按路径反查——它在那里已经有答案。
  // 收件箱原件不在合同的来源表里（它是人另外给的），落到「原件」。
  const kinds = new Map(Object.values(ctx.contract?.sources ?? {})
    .filter(x => x?.path && x?.label).map(x => [x.path, x.label]));
  return targets.must.map(([rel]) =>
    `- ${kinds.get(rel) ?? (rel.startsWith('inbox/') ? '原件' : '材料')}：`
    + `[${basename(rel)}](${relFromStory(rel)})——{{这份材料贡献了什么}}`);
}

/**
 * 材料现在能不能起稿 —— **事实由 story_flow 的材料链给，这里只消费**。
 *
 * 两件事都要看：`pending` 是收件箱里还没并入正文的原件，`changed` 是磁盘与本轮登记的
 * 基准不同。只认后者的话，`round` 一登记新基准它就归假，而那份原件仍躺在收件箱里——
 * 起手照过，而成文据以写的材料少一份，此后没有任何判据会提到它。
 *
 * 拦的理由用 status 给的那句话：处置写在流程那一侧，这里再写一遍迟早与它分叉。
 *
 * @returns {string|null} 不能起手的原因（含处置）；null = 材料就位
 */
export function materialsNotReady(ctx) {
  const { data, error } = queryFlowStatus(ctx.projectRoot, ctx.args.feature,
    { timeoutMs: 120000 });
  if (error) {
    return `材料现状问不出来（${error}）：原件导没导、材料变没变由 story_flow 的材料链`
      + '按磁盘现状答——它跑不起来就没有人能回答这件事。先让'
      + ' `story_flow.py status --feature <名> --project-root <工程根>` 跑通，再起骨架';
  }
  const state = data?.material_state ?? null;
  if (!state) return null;        // 没有轮次：基准不符由上面的清单判据报
  if (!state.pending.length && !state.changed) return null;
  return String(data.action ?? '').trim()
    || '材料与本轮登记的不是同一批：跑 `story_flow.py status` 看当前该做什么';
}

/**
 * 合同声明的来源在不在 —— 必备缺了拦，可选缺了记一笔。
 *
 * 声明的来源压根不在是隐蔽的：那一份材料的内容从头到尾没进过任何一条判据的视野，
 * 门禁却全绿。
 */
export function sourceProblems(ctx) {
  const problems = [];
  const notes = [];
  // ⓪a 合同声明的来源都在
  //
  // 声明的来源压根不在是隐蔽的：那一份材料的内容从头到尾没进过任何一条判据的视野，
  // 门禁却全绿。必需性与起手用**同一份判定**（`sourceStatus`：远程单/本地单、可选来源
  // 都按那里分）——两处各判一次的话，同一份缺件在起手说「本地单缺它正常」、
  // 在这里说「它是必备来源」，作者只能挑一句信。
  // **必备缺了拦**：归档件的依据缺了一块，评审者无从复核；可选缺了记一笔。
  if (!ctx.offline) {
    const { missing, blocking } = sourceStatus(ctx);
    for (const m of blocking) {
      problems.push(`${missingSourceLine(m)}——补回它再交；`
        + '这一轮确实不该有它，就改合同把它登记成可选来源');
    }
    for (const m of missing.filter(x => !x.required)) notes.push(missingSourceLine(m));
  }
  return { problems, notes };
}

/** 材料清单那一节：行形态、链接点得开、列到的与手里的那几份对得上。 */
export function materialListProblems(ctx, storyText) {
  const problems = [];
  const notes = [];
  // ⑫c 材料清单的行形态
  //
  // 材料清单的行形态：判的是形态不是内容——
  // 只问「这一行能不能把材料定位到原件」。图题编号与小节编号归 `number` 机器铺，这里不判。
  // **「这句话指的是不是这张图」仍不在这里判**：那要读上下文，归独立审查。
  // 这里只判两件不用读懂任何一句话就能看见的事——图前面有没有一句话、两张图挨着没有。
  {
    const appendix = appendixChapter(ctx.contract);
    const name = materialSubsectionName(ctx.contract);
    const span = appendix && name ? subsectionSpan(storyText, appendix.title, name) : null;
    if (span) {
      const body = storyText.split(/\r?\n/).slice(span.start, span.end).join('\n');
      const want = materialListTargets(ctx);
      // 行形态（有没有链接、是不是写成了表格）；链到的是不是这一轮的材料，由下面按材料清单逐份对
      for (const h of scanMaterialList(body, span.start + 1)) {
        problems.push(`「${appendix.title}·${name}」第 ${h.line} 行——${h.hint}`);
      }
      // 链接得能点开 —— 只在线上判，因为只有线上才知道那份文件在不在。
      //
      // 典型写法 `[RR/prd.md](RR/prd.md)` 解析不到：story.md 在 AR/ 下，
      // 这个裸相对路径解析出来是 `AR/RR/prd.md`——**不存在**。
      //
      // 离线不判存在性：那时没有 feature 上下文，基准目录只能靠猜，而判据一旦
      // 开始猜就没法解释也没法回归。离线拿到的往往是一份脱离需求目录的独立文件，
      // 它身边本就没有 RR/ 与 AR/——形态判照跑，存在性留给线上。
      if (!ctx.offline) {
        const fromDir = path.dirname(ctx.storyPath);
        for (const [line, target] of materialLinkTargets(body, span.start + 1)) {
          if (/^(https?:|mailto:)/i.test(target)) continue;
          if (!fs.existsSync(path.resolve(fromDir, target))) {
            problems.push(`「${appendix.title}·${name}」第 ${line} 行的链接点不开：`
              + `${target} —— 从归档件所在的位置解析不到这份文件。`
              + '读者打不开这个仓，链接是「据哪几份材料写成」唯一可核的形态，'
              + '指错了等于没指');
          }
        }
      }
      // 集合面：列到的与真正在手里的那几份材料对得上
      if (want === 'broken') {
        problems.push('AR/story-src/materials.json 读不出材料清单——'
          + `「${appendix.title}·${name}」列得全不全无从核对。`
          + '它只应由脚本写入，若曾手工编辑，删掉后重跑 `story_flow.py round`');
      } else if (!want) {
        notes.push(`没有材料清单（AR/story-src/materials.json），`
          + `「${appendix.title}·${name}」的集合判据未执行`
          + '——跑 `story_flow.py round` 生成它之后这条才判得了');
      } else {
        const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
        const listed = new Set();
        for (const [, target] of materialLinkTargets(body, span.start + 1)) {
          if (/^(https?:|mailto:)/i.test(target)) continue;
          listed.add(joinPosix(storyDir, target));
        }
        const allowed = new Set(want.must.flat());
        for (const group of want.must) {
          if (!group.some(rel => listed.has(rel))) {
            problems.push(`「${appendix.title}·${name}」少了一份材料：${group[0]}`
              + '——它在这一轮的材料里，读者据这一节把材料找出来，漏一份等于那份材料没人知道');
          }
        }
        for (const rel of listed) {
          if (allowed.has(rel)) continue;
          problems.push(`「${appendix.title}·${name}」列了不是初始资料的东西：${rel}`
            + '——这一节回答「据哪几份材料写成」：上游那几份正文与收件箱原件，'
            + '各一行。本轮自己生成的规格与记录不是材料；'
            + '图的去向登记在材料清单里（`--caption-image … --unused`），不写在这一节');
        }
      }
    }
  }
  // 小节编号不在这里判：它由 `number` 命令统一铺（D1）。机器保证的形态再设一条
  // 判据，判的是自己的输出——真正会漏的是机器不做的那部分。
  return { problems, notes };
}

/**
 * 需求目录下的相对路径 → **相对 story.md** 的路径。
 *
 * story.md 在 `AR/` 下，而清单记的是相对需求目录的路径（`RR/prd.md`、
 * `assets/x.png`）。差这一层，链接就点不开、图就断链——落盘后 `check` 会逐条报，
 * 而那几条本可以不发生：串是脚本给作者的，算对是脚本的事。
 */
export function relFromStory(rel) {
  return path.posix.relative('AR', String(rel ?? '').split(path.sep).join('/'));
}
