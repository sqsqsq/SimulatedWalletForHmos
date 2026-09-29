/**
 * 测试专用：Framework 的 ts-node 每起一个进程都把原生模块重新转译一遍（读一次阶段输入要带出一百五十来个 .ts，约 1.5 秒），
 * 全量里几百个这样的进程把整机算力吃满。这里把转译结果按（文件、源码、TypeScript 版本、注册参数）存到磁盘，
 * 同样的输入直接取上次的输出——输出与现转译逐字相同，加载路径与产品一致。
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
  service.compile = (code, fileName, lineOffset) => {
    const key = crypto.createHash('sha256').update(salt).update('\0').update(fileName).update('\0').update(code).digest('hex');
    const file = path.join(dir, `${key}.js`);
    try {
      return fs.readFileSync(file, 'utf8');
    } catch {
      // 没有就现转译
    }
    const out = compile(code, fileName, lineOffset);
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
  };
  service.__storyCached = true;
  return service;
}

// 只在等 ts-node 入口时包一层 Module._load，挂上缓存就撤掉：这一帧留在调用栈上，Node 会把之后 node_modules 里
// 对 punycode 等模块的引用误当成用户代码而多报弃用警告，改变进程的 stderr。
const load = Module._load;
Module._load = function (request, parent, isMain) {
  const exported = load.apply(this, arguments);
  // ts-node 的入口模块：产品经 require('ts-node')，ts-node 的 bin 经 ./index，两条都认导出形状
  if (exported && typeof exported.register === 'function' && typeof exported.create === 'function' && exported.VERSION) {
    Module._load = load;
    const register = exported.register;
    exported.register = function () {
      return cached(register.apply(this, arguments));
    };
  }
  return exported;
};
