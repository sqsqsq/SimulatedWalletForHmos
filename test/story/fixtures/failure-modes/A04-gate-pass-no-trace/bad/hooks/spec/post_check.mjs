// 通过时直接返回，什么都不留——「跑了并通过」与「根本没跑」事后同形。
export default async function specPostCheck(ctx) {
  const problems = [];
  if (problems.length) return { ok: false, severityOverride: 'BLOCKER', message: problems.join('；') };
  return { ok: true };
}
