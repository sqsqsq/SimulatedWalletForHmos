export function usedOne() { return 1; }

// 零调用方：它守着的数据会成为从不生效的第二真源
export function neverCalled() { return 2; }

export function parse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return [];
  }
}

export default function run(text) {
  return usedOne() + parse(text).length;
}
