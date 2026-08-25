// 反例：域清单写死在代码里，新增一个域要改这里
export const REQUIRED_ENTRIES = ['SMP-01', 'SMP-02', 'OTH-01'];
export function coverage(rows) {
  return REQUIRED_ENTRIES.filter((id) => !rows.includes(id));
}
