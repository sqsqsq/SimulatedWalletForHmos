// 原生 featurePhaseReportsDir 的对照探针：argv = 项目根…，逐个输出 {dir} 或 {error}。只读，不写任何文件。
import { featurePhaseReportsDir } from '../../../demo/framework/harness/config';

const out = process.argv.slice(2).map((root) => {
  try {
    return { dir: featurePhaseReportsDir(root, 'F1', 'spec') };
  } catch (e) {
    return { error: String((e as Error).message ?? e) };
  }
});
process.stdout.write(JSON.stringify(out));
