/**
 * 测试专用：Framework 的 ts-node 每起一个进程都要加载 TypeScript 编译器并把原生模块重新转译一遍，全量里几百个这样的
 * 进程把整机算力吃满。这里把转译结果按（文件、源码、TypeScript 版本、注册参数）存到磁盘：
 *
 * - 产品经 `require('ts-node').register(...)` 注册时，换成一个只管 `.ts` 的加载钩子：命中缓存就直接执行缓存里的 JS，
 *   不加载 ts-node 与 TypeScript；没命中才加载真的 ts-node 现转译并存下。转译输出与现转译逐字相同。
 * - Framework 自己的 ts-node 命令行（`ts-node/dist/bin.js`）走完整的 ts-node，只给它的转译挂上同一份缓存。
 *
 * 由 conftest.py 经 NODE_OPTIONS=--require 带给测试起的每个 node 进程；缓存目录取 STORY_TEST_TS_CACHE。
 * 产品运行不经过这里。
 */
'use strict';
const Module = require('module');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const dir = process.env.STORY_TEST_TS_CACHE;

function remember(key, produce) {
  const file = path.join(dir, `${key}.js`);
  try {
    return fs.readFileSync(file, 'utf8');
  } catch {
    // 没有就现转译
  }
  const out = produce();
  // 先写临时文件再改名：并行进程不会读到半份
  const tmp = `${file}.${process.pid}.tmp`;
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(tmp, out);
    fs.renameSync(tmp, file);
  } catch {
    fs.rmSync(tmp, { force: true });
  }
  return out;
}

const keyOf = (salt, fileName, code) =>
  crypto.createHash('sha256').update(salt).update('\0').update(fileName).update('\0').update(code).digest('hex');

/** 完整 ts-node 的服务：转译走缓存（命令行入口用）。 */
function cached(service) {
  if (!dir || service.__storyCached) return service;
  // 注册参数里的 tsconfig 是各临时工程接入 Framework 的路径，每个工程都不同：按它的内容算，不按路径
  let salt;
  try {
    const { project, ...options } = service.options;
    salt = `${service.ts.version}\0${JSON.stringify(options)}\0${project ? fs.readFileSync(project, 'utf8') : ''}`;
  } catch {
    return service;
  }
  const compile = service.compile.bind(service);
  service.compile = (code, fileName, lineOffset) => remember(keyOf(salt, fileName, code), () => compile(code, fileName, lineOffset));
  service.__storyCached = true;
  return service;
}

/**
 * 产品的注册入口：只挂 `.ts` 的加载钩子，缓存命中不加载 TypeScript。
 * `real` 取真的 ts-node 模块（没命中时才调用），盐取 TypeScript 版本、注册参数与 tsconfig 的内容。
 */
function lightRegister(real, options) {
  const { project, ...rest } = options ?? {};
  const version = JSON.parse(fs.readFileSync(Module.createRequire(project).resolve('typescript/package.json'), 'utf8')).version;
  const salt = `light\0${version}\0${JSON.stringify(rest)}\0${project ? fs.readFileSync(project, 'utf8') : ''}`;
  let service = null;
  const compile = (code, fileName) => {
    service ??= real().create(options);
    return service.compile(code, fileName);
  };
  require.extensions['.ts'] = function (module, fileName) {
    const code = fs.readFileSync(fileName, 'utf8');
    module._compile(remember(keyOf(salt, fileName, code), () => compile(code, fileName)), fileName);
  };
  return { options };
}

const load = Module._load;
let full = null;
Module._load = function (request, parent, isMain) {
  if (dir && request === 'ts-node') {
    // 产品经 createRequire(harness).require('ts-node') 注册：给一个只换了 register 的门面，其余照真的。
    // 拦到就撤掉这一层：它留在调用栈上，Node 会把之后 node_modules 里对 punycode 等的引用误当成用户代码而多报弃用警告
    Module._load = load;
    const real = () => (full ??= load.call(Module, request, parent, isMain));
    // 只有带 tsconfig 的注册（产品 loadNative 的写法）走轻钩子；别的注册照真的 ts-node，转译仍走缓存
    return new Proxy({}, { get: (_, key) => (key !== 'register' ? real()[key]
      : opts => (opts?.project ? lightRegister(real, opts) : cached(real().register(opts)))) });
  }
  const exported = load.apply(this, arguments);
  // ts-node 的命令行入口经 ./index 取到它：给它的转译挂上缓存
  if (exported && typeof exported.register === 'function' && typeof exported.create === 'function' && exported.VERSION
      && exported !== full) {
    Module._load = load;
    const register = exported.register;
    exported.register = function () {
      return cached(register.apply(this, arguments));
    };
  }
  return exported;
};
