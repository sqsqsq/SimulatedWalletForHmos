export default function preVerifier(ctx) {
  // 全集裁决：每一行都要裁，风险标记只决定排序，不决定覆盖面
  const rows = buildRows(ctx).sort((a, b) => b.suspicion - a.suspicion);
  return { promptFragments: [render(rows)] };
}
