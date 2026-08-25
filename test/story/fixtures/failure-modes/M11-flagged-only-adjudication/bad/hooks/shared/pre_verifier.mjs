export default function preVerifier(ctx) {
  const rows = buildRows(ctx);
  const mustAnswer = rows.filter((r) => r.flagged);
  return { promptFragments: [render(mustAnswer)] };
}
