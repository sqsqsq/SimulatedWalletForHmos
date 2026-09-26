/**
 * mcp.js — 需求系统访问层（本地替身）。
 *
 * 导出 `callMcp(url, method, params, mcpToken)` 与两个端点常量。
 * 命令文件只经它访问需求系统；需求系统在哪、怎么连，只有这一层知道。
 *
 * **本替身的需求系统是一个本地目录**，一个子目录就是一张单，只承载 md：
 *
 *     <system>/<单号>/detail.json          {reqNo,type:"RR|SR|AR",title,parentNo?,rrNo?}
 *     <system>/<RR号>/prd.md               产品需求正文
 *     <system>/<SR号>/design.md            系统设计正文
 *     <system>/<AR号>/design.md            开发需求正文（archive 覆盖的就是它）
 *     <system>/<AR号>/attachments/         附件，评审记录传到这里
 *     <system>/<AR号>/review-feedback.md   评审人留下的回稿
 *
 * 目录位置读环境变量 `STORY_REQUIREMENT_SYSTEM_DIR`，未设时取工程内的默认演示目录。
 * 方法名是替身自定的（getDetail / getBody / putBody / putAttachment / getAttachment），
 * 评审回稿按正文名 `review-feedback.md` 用 getBody 取。
 *
 * 取不到时抛出带 `code` 的错误，三种要分开，补救动作完全不同：
 *   no_system  需求系统不可达（环境没接上，单号还没被查过）
 *   no_ticket  查无此单（单号打错或该单还没建）
 *   bad_detail 单据数据有问题（找需求系统的人）
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { PROJECT_ROOT } = require('./dirs');

const REQUIREMENT_URL = 'local://requirement';
const ATTACHMENT_URL = 'local://attachment';

const SYSTEM_DIR_ENV = 'STORY_REQUIREMENT_SYSTEM_DIR';
const DEFAULT_SYSTEM_DIR = path.join('test', 'story', 'requirement-system');

function systemRoot() {
  const configured = String(process.env[SYSTEM_DIR_ENV] ?? '').trim();
  return configured ? path.resolve(configured) : path.join(PROJECT_ROOT, DEFAULT_SYSTEM_DIR);
}

function failure(code, message) {
  const e = new Error(message);
  e.code = code;
  return e;
}

function ticketDir(reqNo) {
  const system = systemRoot();
  if (!fs.existsSync(system)) {
    throw failure('no_system', `需求系统不可达：${system} 不存在。本地替身以该目录为需求系统，`
      + `请设置环境变量 ${SYSTEM_DIR_ENV} 指向它——这不是「查无此单」，单号本身还没被查过。`);
  }
  const dir = path.join(system, reqNo);
  if (!fs.existsSync(path.join(dir, 'detail.json'))) {
    throw failure('no_ticket', `查无此单：需求系统里没有 ${reqNo}。请确认单号，或确认该单是否已在系统上建立。`);
  }
  return dir;
}

function readOrNull(file) {
  return fs.existsSync(file) ? fs.readFileSync(file, 'utf-8') : null;
}

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf-8');
}

const METHODS = {
  /** { reqNo } → 单据详情对象 */
  getDetail({ reqNo }) {
    const file = path.join(ticketDir(reqNo), 'detail.json');
    try {
      return JSON.parse(fs.readFileSync(file, 'utf-8'));
    } catch (e) {
      throw failure('bad_detail', `单据数据有问题（${reqNo}）：${e.message}。请联系需求系统侧核对该单。`);
    }
  },
  /** { reqNo, name } → 正文文本；系统上没有这份返回 null（缺正文是常态） */
  getBody({ reqNo, name }) {
    return readOrNull(path.join(ticketDir(reqNo), name));
  },
  /** { reqNo, name, content } → 写系统正文 */
  putBody({ reqNo, name, content }) {
    write(path.join(ticketDir(reqNo), name), content);
    return { saved: `${reqNo}/${name}` };
  },
  /** { reqNo, name, content } → 上传附件 */
  putAttachment({ reqNo, name, content }) {
    write(path.join(ticketDir(reqNo), 'attachments', name), content);
    return { saved: `${reqNo}/attachments/${name}` };
  },
  /** { reqNo, name } → 附件文本；没有返回 null（archive 核对上传结果用） */
  getAttachment({ reqNo, name }) {
    return readOrNull(path.join(ticketDir(reqNo), 'attachments', name));
  },
};

/** 替身忽略 url 与 token，按 method 读写本地目录。 */
async function callMcp(url, method, params, mcpToken) {
  const handler = METHODS[method];
  if (!handler) throw failure('bad_method', `需求系统不认识的方法：${method}`);
  return handler(params ?? {});
}

module.exports = { callMcp, REQUIREMENT_URL, ATTACHMENT_URL };
