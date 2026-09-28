/**
 * YAML 读取 —— 与 framework 同一解析器。
 *
 * framework 的 `spec-loader.ts` / `check-plan.ts` 用 `yaml` 包读 contracts 与 acceptance。扩展自己再造
 * 一份读取器，两边对同一份文件的合法性判断就会分叉：作者按 framework 合法的写法写（流式映射、
 * 锚点、中文键），反被扩展判成写错，只能改掉一句合法的 YAML 去迁就读取器。所以这里不解析，
 * 只借 framework 在 `framework/harness/package.json` 里声明的 `yaml` 依赖，用它的 `parse` 一个入口。
 *
 * 依赖取法只有一条路径：从本文件向上找含 `framework.config.json` 的工程根（扩展目录可配置，
 * 但一定在工程根之下），再从 `<根>/framework/harness` 解析 `yaml`。找不到根或找不到包时在第一次
 * `parseYaml` 抛错并给出可复制的安装命令；不在运行期下载，不退回别的读法。
 *
 * **解析失败必须响亮**：抛 `yaml` 包的原始错误（带行列），调用方不得把异常吞成空对象——
 * 空集会让一切「集合包含」判据恒真。空文档读成空映射，与调用方对「文件在但没内容」的处理一致。
 */
import * as fs from 'node:fs';
import { createRequire } from 'node:module';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** 从本文件向上找工程根：含 `framework.config.json` 的第一个目录。 */
function projectRoot() {
  let dir = HERE;
  for (;;) {
    if (fs.existsSync(path.join(dir, 'framework.config.json'))) return dir;
    const up = path.dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
}

let YAML = null;
let unavailable = null;

function load() {
  if (YAML || unavailable) return;
  const root = projectRoot();
  if (!root) {
    unavailable = `从 ${HERE} 向上找不到含 framework.config.json 的工程根——扩展要装在接入了 framework 的工程里`;
    return;
  }
  const harness = path.join(root, 'framework', 'harness');
  try {
    YAML = createRequire(path.join(harness, 'package.json'))('yaml');
  } catch (e) {
    unavailable = `framework 的 yaml 包不可用（${e?.code ?? e?.message ?? e}）：先装 harness 的依赖——`
      + `\n  cd ${path.relative(process.cwd(), harness) || harness} && npm install`;
  }
}

/**
 * 解析 YAML 文本。
 * @throws 读取器不可用、或语法不可解析时抛错（**不返回空对象**）
 */
export function parseYaml(text) {
  load();
  if (!YAML) throw new Error(`YAML 读取器不可用：${unavailable}`);
  return YAML.parse(String(text ?? '')) ?? {};
}
