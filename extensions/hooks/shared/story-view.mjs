/**
 * 阶段开始前把 story 切回 Mermaid —— 原生检查与读审装配都在它之后读 story。
 *
 * Mermaid 是图的唯一语义真源；SVG 形态只是本地阅读窗口。阶段检查、审查请求与登记比较要读的是同一份
 * Mermaid 正文，所以由 framework 的 `pre_phase` 在这一切开始之前切回。没有管理块的 story 零写入。
 * 切不回来（管理块坏了、源缺失）按 BLOCKER 报：SVG 形态不能拿去当 Mermaid 审。
 */
import * as path from 'node:path';
import { featureRoot } from './paths.mjs';
import { ensureMermaid } from '../../skills/story/scripts/core/story/figure-view.mjs';

export default async function storyView(ctx) {
  if (!ctx?.feature || !ctx?.projectRoot) return { ok: true };
  const root = featureRoot(ctx.projectRoot, ctx.feature);
  try {
    const r = ensureMermaid(root);
    if (!r.problems.length) return { ok: true };
    return { ok: false, severityOverride: 'BLOCKER',
      message: `story 切不回 Mermaid，本阶段不拿 SVG 形态当正式正文：\n${r.problems.map((p, i) => `${i + 1}. ${p}`).join('\n')}` };
  } catch (e) {
    return { ok: false, severityOverride: 'BLOCKER',
      message: `story 视图切换自身异常（${e?.stack ?? e}）——${path.join('AR', 'story.md')} 的形态没有确认，本阶段结果不代表通过；归扩展维护者处理` };
  }
}
