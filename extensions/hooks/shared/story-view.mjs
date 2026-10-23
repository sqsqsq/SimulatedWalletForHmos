/**
 * 阶段开始前把 story 放回正式形态 —— 原生检查与读审装配都在它之后读 story。
 *
 * 正式形态是正式图块按 `.mmd` 还原的 Mermaid；同图的增强 SVG 只是本地阅读窗口。阶段检查、审查请求与登记比较
 * 要读的是同一份正式正文，所以由 framework 的 `pre_phase` 在这一切开始之前处理。没有管理区的 story 零写入。
 * 回不去（管理块坏了、源缺失、旧版阅读槽）按 BLOCKER 报：显示着 SVG 的文本不能拿去当正式正文审。
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
      message: `story 回不到正式形态，本阶段不拿显示着 SVG 的文本当正式正文：\n${r.problems.map((p, i) => `${i + 1}. ${p}`).join('\n')}` };
  } catch (e) {
    return { ok: false, severityOverride: 'BLOCKER',
      message: `story 视图切换自身异常（${e?.stack ?? e}）——${path.join('AR', 'story.md')} 的形态没有确认，本阶段结果不代表通过；归扩展维护者处理` };
  }
}
