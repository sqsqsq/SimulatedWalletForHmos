/**
 * 读 Framework 原生能力的唯一入口：从显式工程根的 `framework/harness` 加载它安装的 ts-node，
 * 再 require 原生 TypeScript 模块。不复制框架实现、不另装运行器、不从维护源码导入。
 *
 * 同一进程对同一工程根只注册一次；harness 或其依赖缺失时抛错，错误里写明缺什么、怎么装。
 */
import * as fs from 'node:fs';
import { createRequire } from 'node:module';
import * as path from 'node:path';

const loaded = new Map();

/**
 * @param {string} projectRoot 消费工程根（含 framework.config.json 与 framework/）
 * @returns {{ root: string, frameworkRoot: string, harness: string, require: (id: string) => any, module: (rel: string) => any }}
 */
export function loadNative(projectRoot) {
  const root = path.resolve(projectRoot);
  if (loaded.has(root)) return loaded.get(root);
  const frameworkRoot = path.join(root, 'framework');
  const harness = path.join(frameworkRoot, 'harness');
  const pkg = path.join(harness, 'package.json');
  if (!fs.existsSync(pkg)) throw new Error(`${root} 没有接入 Framework（缺 framework/harness/package.json）`);
  const req = createRequire(pkg);
  try {
    req('ts-node').register({ project: path.join(harness, 'tsconfig.json'), transpileOnly: true });
  } catch (e) {
    throw new Error(`Framework harness 的依赖不可用（${e?.code ?? e?.message ?? e}）：先在 ${harness} 下跑 npm install`);
  }
  const api = {
    root, frameworkRoot, harness,
    require: req,
    module: rel => req(path.join(harness, ...rel.split('/'))),
  };
  loaded.set(root, api);
  return api;
}
