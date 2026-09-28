export function usedOne() { return 1; }

export function parse(text) {
  try {
    return JSON.parse(text);
  } catch (e) {
    console.error(`解析失败：${e.message}——按空表继续，但这条降级要被看见`);
    return [];
  }
}

export default function run(text) {
  return usedOne() + parse(text).length;
}
