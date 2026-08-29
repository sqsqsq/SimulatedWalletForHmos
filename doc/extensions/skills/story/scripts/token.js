/**
 * token.js — 获取 mcp token（本文件是部署环境间需要替换的实现之一）
 *
 * 契约（CLI，SKILL.md「需求系统 Token」章为准）：
 *   node token.js
 *     → 成功：exit 0，**stdout 即为 token 本身**（纯文本单行，无引号无 JSON）
 *     → 失败：非 0 退出，错误信息走 stderr；调用方转入 SKILL.md 步骤 2 从配置文件读取
 *
 * stdout 是纯文本而非 JSON：调用方拿到什么就直接当 `<mcp-token>` 传给 story.js，
 * 中间不需要解析这一步。多输出一层结构，就多一个把整行 JSON 当成 token 传下去的机会。
 *
 * **本实现是本地替身**：返回固定串。固定而非随时间变化，是为了让「token 变了」
 * 与「流程变了」这两件事在实跑证据里分得开——带时间戳的 token 每轮都不同，
 * 事后比对两轮日志时它是唯一的噪声源，却一次也没帮上忙。
 * 部署环境替换本文件时从 mcp 配置/凭据缓存取真实 token，保持上述契约不变。
 */
'use strict';
process.stdout.write('local-mcp-token\n');
