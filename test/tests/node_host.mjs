/**
 * 测试专用：随测试起停的 node 宿主。一个测试进程一个，在进程内按命令行的样子执行产品脚本，让 Framework 的 TS 只加载一次。
 *
 * 由 conftest.py 在第一次需要时起，测试进程结束（或 stdin 关闭）时退出。每行 stdin 一个请求，逐条串行执行，回一行 JSON：
 *   {"kind": "script", "argv": [脚本, ...参数], "cwd": ..., "env": {...}}       ——`node 脚本 参数…`
 *   {"kind": "eval",   "source": 正文, "argv": [参数…], "cwd": ..., "env": {...}}   ——`node --input-type=module -e 正文 参数…`
 *   → {"returncode": n, "stdout": "...", "stderr": "..."}；宿主自身出错回 {"fault": 原因}（不是产品结论）。
 *
 * 与命令行同语义的几处：
 * - 每条请求一份新的 ESM 模块：本次解析到的、不在 node_modules 下的 `.mjs` 都带上 `?job=<序号>` 重新求值，
 *   扩展里的模块级状态（缓存、登记）与命令行一样每条命令重新开始；经 require 加载的 Framework TS（CJS）跨请求共享。
 * - `process.exit(n)` 记下第一次的退出码并截断当前执行（命令行里它当场结束进程）；没有 exit 时取 `process.exitCode`。
 * - argv、cwd、env 每条请求设好、结束还原。
 * 产品运行不经过这里。
 */
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import * as readline from 'node:readline';
import { createHash } from 'node:crypto';
import Module, { createRequire, register } from 'node:module';
import { pathToFileURL } from 'node:url';

const writeOut = process.stdout.write.bind(process.stdout);
const writeErr = process.stderr.write.bind(process.stderr);
const realExit = process.exit.bind(process);
const homeCwd = process.cwd();
const homeEnv = { ...process.env };
const evalDir = path.join(os.tmpdir(), 'story-node-host');
fs.mkdirSync(evalDir, { recursive: true });

/** 当前请求的序号；0 表示不在请求里（宿主自身的模块照常缓存）。`seq` 只增不减，保证每条请求的模块 URL 都不同。 */
let job = 0;
let seq = 0;

// ESM 解析钩子在加载线程里（node_host_loader.mjs），只管 ESM import：CJS require（Framework TS、ts-node）与命令行一致。
// 当前请求序号经共享的一个整数交给它
const shared = new SharedArrayBuffer(8 + 32768);
const slot = new Int32Array(shared, 0, 2);
const cwdBytes = new Uint8Array(shared, 8);
register(new URL('./node_host_loader.mjs', import.meta.url), { data: { shared, evalDir } });
const enter = (n, cwd = '') => {
  const encoded = new TextEncoder().encode(cwd);
  cwdBytes.set(encoded.subarray(0, cwdBytes.length));
  Atomics.store(slot, 1, Math.min(encoded.length, cwdBytes.length));
  job = n;
  Atomics.store(slot, 0, n);
};

// 测试转译缓存在命令行里刻意不让 Node 把 node_modules 对 punycode 的引用记到用户代码上（DEP0040 不出现）；
// 宿主里这条警告只是宿主自身的副产物，不让它混进命令的 stderr
const emitWarning = process.emitWarning.bind(process);
process.emitWarning = (warning, ...rest) => {
  const code = typeof rest[0] === 'object' ? rest[0]?.code : rest[1];
  if (code === 'DEP0040') return;
  emitWarning(warning, ...rest);
};

// 测试转译缓存（ts_transpile_cache.cjs）在命令行里经 NODE_OPTIONS 预载：拦每个进程第一次 require('ts-node')，拦完撤掉自己。
// 宿主不带这份预载起（桥接把它放在 STORY_NODE_HOST_PRELOAD），每条请求开始时把 Module._load 复原、重新执行一次它，
// 于是每条请求与一个新的命令行进程一样，第一次 require('ts-node') 被拦、之后照真的解析
const pristineLoad = Module._load;
const preload = process.env.STORY_NODE_HOST_PRELOAD;
const hostRequire = createRequire(import.meta.url);
const freshPreload = () => {
  Module._load = pristineLoad;
  if (!preload) return;
  delete Module._cache[hostRequire.resolve(preload)];
  hostRequire(preload);
};

class HostExit extends Error {}
let current = null;     // 正在执行的请求：{code, stdout[], stderr[]}
process.on('uncaughtException', (e) => {
  if (e instanceof HostExit) return;
  if (!current) throw e;
  // 命令行里未捕获的异常打出栈并以 1 结束
  current.stderr.push(`${e?.stack ?? e}\n`);
  if (current.code === null) current.code = 1;
});
process.on('unhandledRejection', (e) => {
  if (e instanceof HostExit) return;
  if (!current) throw e;
  current.stderr.push(`${e?.stack ?? e}\n`);
  if (current.code === null) current.code = 1;
});

/** 入口守卫里的 main() 是游离的 Promise：让出事件循环，直到连着几轮没有本次请求留下的活动资源。 */
const baseline = () => process.getActiveResourcesInfo().filter(x => x !== 'Immediate');
async function settle(base) {
  let quiet = 0;
  while (quiet < 3) {
    await new Promise(r => setImmediate(r));
    const now = baseline();
    quiet = now.length <= base.length ? quiet + 1 : 0;
  }
}

function evalFile(source) {
  const file = path.join(evalDir, `${createHash('sha256').update(source).digest('hex').slice(0, 24)}.mjs`);
  if (!fs.existsSync(file)) {
    fs.mkdirSync(evalDir, { recursive: true });
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, source);
    fs.renameSync(tmp, file);
  }
  return file;
}

async function run(request) {
  const state = { code: null, stdout: [], stderr: [] };
  const capture = (sink) => (chunk, ...rest) => {
    sink.push(typeof chunk === 'string' ? chunk : Buffer.from(chunk).toString('utf8'));
    const cb = rest.find(x => typeof x === 'function');
    if (cb) cb();
    return true;
  };
  const base = baseline();
  current = state;
  try {
    for (const k of Object.keys(process.env)) delete process.env[k];
    Object.assign(process.env, request.env ?? homeEnv);
    process.chdir(request.cwd ?? homeCwd);
    freshPreload();
    process.exitCode = undefined;
    process.stdout.write = capture(state.stdout);
    process.stderr.write = capture(state.stderr);
    process.exit = (code) => {
      if (state.code === null) state.code = code ?? process.exitCode ?? 0;
      throw new HostExit();
    };
    seq += 1;
    enter(seq, process.cwd());
    const entry = request.kind === 'eval' ? evalFile(request.source) : path.resolve(request.argv[0]);
    process.argv = request.kind === 'eval' ? [process.execPath, ...request.argv] : [process.execPath, entry, ...request.argv.slice(1)];
    await import(`${pathToFileURL(entry).href}?job=${job}`);
    await settle(base);
  } catch (e) {
    if (!(e instanceof HostExit)) {
      // 入口找不到、或入口模块求值时同步抛出：命令行里同样是未捕获异常，打出栈、以 1 结束
      state.stderr.push(`${e?.stack ?? e}\n`);
      if (state.code === null) state.code = 1;
    }
  } finally {
    current = null;
    process.stdout.write = writeOut;
    process.stderr.write = writeErr;
    process.exit = realExit;
    const code = state.code ?? process.exitCode ?? 0;
    process.exitCode = undefined;
    for (const k of Object.keys(process.env)) delete process.env[k];
    Object.assign(process.env, homeEnv);
    process.chdir(homeCwd);
    enter(0);
    writeOut(`${JSON.stringify({ returncode: typeof code === 'number' ? code : Number(code) || 0,
      stdout: state.stdout.join(''), stderr: state.stderr.join('') })}\n`);
  }
}

for await (const line of readline.createInterface({ input: process.stdin })) {
  if (!line.trim()) continue;
  let request;
  try {
    request = JSON.parse(line);
  } catch (e) {
    writeOut(`${JSON.stringify({ fault: `请求不是 JSON：${e.message}` })}\n`);
    continue;
  }
  await run(request);
}
realExit(0);
