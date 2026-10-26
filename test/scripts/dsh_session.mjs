// dsh 原生会话文件的只读解析（测试取证用）：session.v4.jsonl.zstd 是首尾相接的 zstd frame，
// 用 Node 24 内置 zstdDecompressSync 逐个 frame 解开（`info.engine.bytesWritten` 是这一帧吃掉的字节）。
// stdout 一个 JSON：{header, children:[{childId, label}], lines} 或 {error}。格式不认识就报错，不写兼容层。
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

try {
  const rows = decode(process.argv[2]);
  const header = rows[0] ?? {};
  if (header.type !== 'session' || header.version !== 4) throw new Error(`头部不是 v4 会话：${JSON.stringify(header).slice(0, 200)}`);
  const children = rows.filter(r => r.type === 'subagent/catalog' && r.data?.childId)
    .map(r => ({ childId: r.data.childId, label: r.data.label ?? null }));
  process.stdout.write(JSON.stringify({ header, children, lines: rows.length }));
} catch (e) {
  process.stdout.write(JSON.stringify({ error: String(e?.message ?? e) }));
}
