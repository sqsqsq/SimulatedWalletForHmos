/**
 * 演示：coding 阶段 pre_check 生命周期 hook（stdin JSON → stdout JSON）
 * 白名单路径：plan §7.13 hooks/coding/pre_check.mjs
 */
export default async function preCheckHook(_ctx) {
  return {
    promptFragments: ['<!-- extension coding/pre_check.mjs: ok -->'],
  };
}
