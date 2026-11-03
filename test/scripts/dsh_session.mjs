// dsh 原生会话文件的只读解析（测试取证用）：session.v4.jsonl.zstd 是首尾相接的 zstd frame，
// 用 Node 24 内置 zstdDecompressSync 逐个 frame 解开（`info.engine.bytesWritten` 是这一帧吃掉的字节）。
// stdout 一个 JSON：{header, children, calls, settled, lines} 或 {error}。格式不认识就报错，不写兼容层。
//
// - children：父会话 `subagent/catalog` 登记的子会话 `{childId, label, createdAt}`；
// - calls：原生 `tool/call` 按 callId 归并它的 `tool/result`，`{callId, name, time, args, results}`。
//   读写类工具只留入参，结果正文只留给会派生子会话或跑命令的工具（subagent / verifier / task / shell 类），
//   别的结果只记时间与是否出错；同一 callId 内容相同的重复结果只算一次，内容不同的都留着，由读者判冲突；
// - settled：子会话收尾通知（`agent/inbox/spliced` 里 `source.kind = subagent-settled`）`{childId, time, summary, text}`。
import fs from 'node:fs';
import zlib from 'node:zlib';

function decode(file) {
  if (typeof zlib.zstdDecompressSync !== 'function') throw new Error(`Node ${process.version} 没有内置 zstd`);
  const buf = fs.readFileSync(file);
  const parts = [];
  for (let offset = 0; offset < buf.length;) {
    const res = zlib.zstdDecompressSync(buf.subarray(offset), { info: true });
    const used = res.engine.bytesWritten;
    if (!used) throw new Error(`第 ${offset} 字节起的 frame 解不出（文件可能没写完）`);
    parts.push(res.buffer);
    offset += used;
  }
  return Buffer.concat(parts).toString('utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
}

//: 结果正文要留的工具：派生子会话的与跑命令的（门禁、登记、审查结论都在它们的输出里）
const KEEP_OUTPUT = new Set(['subagent', 'verifier', 'task', 'subagent_fork', 'pwsh', 'bash', 'shell', 'shell_command']);
const textOf = content => (Array.isArray(content) ? content : []).filter(c => c?.type === 'text').map(c => c.text).join('\n');

try {
  const rows = decode(process.argv[2]);
  const header = rows[0] ?? {};
  if (header.type !== 'session' || header.version !== 4) throw new Error(`头部不是 v4 会话：${JSON.stringify(header).slice(0, 200)}`);
  const children = rows.filter(r => r.type === 'subagent/catalog' && r.data?.childId)
    .map(r => ({ childId: r.data.childId, label: r.data.label ?? null, createdAt: r.data.childCreatedAt ?? r.time ?? null }));
  const calls = new Map();
  for (const r of rows.filter(x => x.type === 'tool/call' && x.data?.callId)) {
    if (!calls.has(r.data.callId)) {
      calls.set(r.data.callId, { callId: r.data.callId, name: r.data.name, time: r.time ?? null, args: r.data.arguments ?? null, results: [] });
    }
  }
  for (const r of rows.filter(x => x.type === 'tool/result')) {
    const id = r.data?.message?.toolCallId ?? r.data?.toolCallId;
    const call = calls.get(id);
    if (!call) continue;
    const text = KEEP_OUTPUT.has(call.name) ? textOf(r.data?.message?.content) : null;
    const result = { time: r.time ?? null, isError: r.data?.message?.isError === true, text };
    if (!call.results.some(x => x.text === result.text && x.isError === result.isError)) call.results.push(result);
  }
  const settled = rows.filter(r => r.type === 'agent/inbox/spliced')
    .flatMap(r => (r.data?.inserted ?? []).filter(m => m?.source?.kind === 'subagent-settled')
      .map(m => ({ childId: m.source.senderSessionId ?? null, time: r.time ?? null, summary: m.source.summary ?? null,
        text: textOf(m.content) })));
  process.stdout.write(JSON.stringify({ header, children, calls: [...calls.values()], settled, lines: rows.length }));
} catch (e) {
  process.stdout.write(JSON.stringify({ error: String(e?.message ?? e) }));
}
