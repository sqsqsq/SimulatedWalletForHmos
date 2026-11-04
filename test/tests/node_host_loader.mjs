/**
 * 测试专用：node 宿主（node_host.mjs）的 ESM 解析钩子，经 `module.register` 装在加载线程里，只管 ESM import，不碰 CJS require。
 * 宿主把当前请求写进共享内存：[0] 请求序号，[1] 本次 cwd 的 UTF-8 字节数，第 8 字节起是 cwd。
 * - 在请求里时，解析到的、不在 node_modules 下的 `.mjs` 都带上 `?job=<序号>`，每条请求拿到一份新的模块；
 * - 内联模块（`-e` 的正文被宿主写成临时文件）里的导入照命令行的规则，相对本次 cwd 解析。
 */
import { pathToFileURL } from 'node:url';

let slot;
let bytes;
let evalPrefix;

export async function initialize({ shared, evalDir }) {
  slot = new Int32Array(shared, 0, 2);
  bytes = new Uint8Array(shared, 8);
  evalPrefix = pathToFileURL(evalDir).href.toLowerCase();
}

const cwdURL = () => {
  const n = Atomics.load(slot, 1);
  return pathToFileURL(`${new TextDecoder().decode(bytes.slice(0, n))}/[eval]`).href;
};

export async function resolve(specifier, context, next) {
  const job = slot ? Atomics.load(slot, 0) : 0;
  const fromEval = job && context.parentURL?.toLowerCase().startsWith(evalPrefix);
  const out = await next(specifier, fromEval ? { ...context, parentURL: cwdURL() } : context);
  if (job && out.url.startsWith('file:')) {
    const bare = out.url.split('?')[0];
    if (bare.endsWith('.mjs') && !bare.includes('/node_modules/')) return { ...out, url: `${bare}?job=${job}` };
  }
  return out;
}
