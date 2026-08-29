// 消费者：导出被别的文件用到，才不是死代码。
// 判据问的是「有没有别人用它」，不是「本文件里调没调」——
// 自己调自己的导出，对外仍然是零消费者。
import run, { usedOne, parse } from '../shared/util.mjs';

export default function check(text) {
  return { base: usedOne(), parsed: parse(text), total: run(text) };
}
