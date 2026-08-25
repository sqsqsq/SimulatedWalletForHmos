// 反例：整文件 SHA 绑死，元数据一扩展就失败
import { createHash } from 'node:crypto';
export function verifyPattern(text, expected) {
  const sha256 = createHash('sha256').update(text).digest('hex');
  return sha256 === expected;   // design-patterns 基线
}
