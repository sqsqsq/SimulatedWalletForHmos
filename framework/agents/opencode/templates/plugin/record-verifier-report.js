// ============================================================================
// record-verifier-report.js — opencode 插件：把 verifier 子 agent 的结论发布为
// **身份绑定**的机器真源（publisher 机制 id = `task_tool_result`）
// ============================================================================
// 触发时机：opencode 在 `task` 工具**完成**时触发插件钩子 `tool.execute.after`。
// 宿主此刻一次交出三样绑定材料，全部来自宿主自身、不经主 agent 转述：
//   · `input.args.prompt`      —— 主 agent 实际投给子 agent 的**调用正文**；
//   · `output.metadata`        —— `sessionId`（子会话）与 `parentSessionId`（主会话）；
//   · `output.output`          —— `<task id state><task_result>终稿</task_result></task>`。
//
// 与 claude 家族的 `subagent_stop` 是**同一套协议的两个入口**：四方对账、产物格式、
// CAS 发布语义逐字相同，差别只在宿主把材料交出来的位置——那边要读子 agent 转录才拿得到
// 调用正文，这边调用正文就是工具入参。**因此不叫 subagent_stop**：机制名要如实。
//
// ─── 发布契约（四方对账）────────────────────────────────────────────────────
//   ① request 自述 subject == 按 request 字段**重算**的 subject（抄错任何字段即失配）；
//   ② == summary.verifier_subject_id（runner 现值——迟到/换代报告在此被拦）；
//   ③ == 终态块回显的 subject（子 agent 终稿）；
//   ④ request.prompt_path == 由 config + request 的 feature/phase **自行推导**的
//      canonical 路径，且 request.prompt_sha256 == 该文件的磁盘实测哈希。
// 另加一条本机制特有的**执行体独立性**校验：
//   ⑤ 子会话 id 存在、且 != 主会话 id、且 == 终稿信封 `<task id="…">` 自述的会话 id。
// 任一不成立 → bedside fail-closed，各按具名 reason 落盘。
//
// ─── 宿主截断（必须处理，否则静默审空）─────────────────────────────────────
// opencode 对工具输出有 `tool_output.max_lines` / `max_bytes` 上限（默认 2000 行 /
// 51200 字节），超限**从头部保留**并把全文另存到 `metadata.outputPath`。终态块在终稿
// 末尾，头部截断会把它整块切掉——只读 `output.output` 就会得到「无终态块」而误判。
// 所以 `metadata.truncated === true` 时**必须**改读 `outputPath` 全文；读不到即 bedside。
//
// ─── 硬性边界 ────────────────────────────────────────────────────────────────
//   · 不写 `.current-phase.json`，不碰 phase 状态；
//   · 写入路径由 framework config + request 的 feature/phase **自行推导**；request 里的
//     claimed prompt_path 仅作等值核对，越界（../ / 绝对路径 / 跨 feature）一律拒绝；
//   · 任何异常都 fail-open **对宿主**（绝不让插件异常打断 opencode 会话）、
//     fail-closed **对证据**（绑定不成立就只落 bedside，绝不发布 canonical）；
//   · **只导出 default 一个符号**。宿主装载器会把模块里每一个导出的函数都当插件入口
//     调一遍（实证见文件末尾 `plugin.internals` 处），具名导出会让本发布器静默失效。
//
// 格式 SSOT：framework/harness/scripts/utils/verifier-request.ts（request 与 subject 派生）
// 与 verifier-subject.ts（终态块与结论指纹）——本文件是它们在插件侧的复刻；改格式必须
// 同步，等值由 test/story/tests/test_opencode_verifier_publisher.py 的跨实现比对守护。
// ============================================================================

import crypto from "node:crypto"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const VERIFIER_REPORT_SCHEMA_VERSION = "2.0"
const RESULT_BLOCK_OPEN = "<!-- maison-verifier-result:v1 -->"
const RESULT_BLOCK_CLOSE = "<!-- /maison-verifier-result:v1 -->"
const SUBJECT_ID_PATTERN = /^[0-9a-f]{64}$/
// request 契约（SSOT: harness/scripts/utils/verifier-request.ts）——逐字符复刻。
const VERIFIER_REQUEST_SCHEMA_VERSION = "1.0"
const VERIFIER_REQUEST_KIND = "maison_verifier_request"
const VERIFIER_REQUEST_SUBJECT_SCHEMA = "maison-verifier-request@2"
const AI_PROMPT_FILENAME = "ai-prompt.md"
/** 本插件只对这一个工具的完成事件发布结论。 */
const TASK_TOOL_ID = "task"
/** 报告来源行自述（机制名，不冒充别的宿主的机制）。 */
const SELF_DESCRIPTION = "opencode/plugin/record-verifier-report.js"

// --------------------------------------------------------------------------
// 1. 纯函数：哈希、EOL、块解析
// --------------------------------------------------------------------------

function normalizeEol(text) {
  return typeof text === "string" ? text.replace(/\r\n/g, "\n") : ""
}

function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf-8").digest("hex")
}

function escapeRe(s) {
  return s.replace(/[/\-\\^$*+?.()|[\]{}]/g, "\\$&")
}

function collectBlockBodies(text, open, close) {
  const re = new RegExp(`${escapeRe(open)}([\\s\\S]*?)${escapeRe(close)}`, "g")
  const out = []
  let m
  while ((m = re.exec(normalizeEol(text))) !== null) out.push(m[1])
  return out
}

function readBlockField(body, key) {
  const m = new RegExp(`^\\s*${key}\\s*:\\s*(.+?)\\s*$`, "m").exec(body)
  return m ? m[1].trim() : null
}

/** subject 的规范化输入串——与 verifier-request.ts canonicalRequestInput 逐字符一致。 */
function canonicalRequestInput(f) {
  return [
    VERIFIER_REQUEST_SUBJECT_SCHEMA,
    `feature=${f.feature}`,
    `phase=${f.phase}`,
    `prompt_path=${f.prompt_path}`,
    `material_sha256=${f.material_sha256}`,
    `gate_fingerprint=${f.gate_fingerprint ?? "<absent>"}`,
    // source_commit_sha / worktree_digest 只是审计字段，不进 subject：
    // 它们随任何无关提交或工作区改动变化，进来只会无效换代；
    // 审查材料真的变了已由 material_sha256 覆盖。
  ].join("\n")
}

function computeRequestSubjectId(fields) {
  return sha256(canonicalRequestInput(fields))
}

/** request 的精确键集——多一个键即拒绝（与 verifier-request.ts 逐字符一致）。 */
const VERIFIER_REQUEST_KEYS = new Set([
  "schema_version",
  "kind",
  "subject_id",
  "feature",
  "phase",
  "prompt_path",
  "prompt_sha256",
  "material_sha256",
  "gate_fingerprint",
  "source_commit_sha",
  "worktree_digest",
])

const nonEmpty = (v) => typeof v === "string" && v.trim().length > 0

/** 字段值原样取用；trim 只用来判空白串——字段值里的空白是**内容**，不是排版。 */
function readRequiredStr(v) {
  return typeof v === "string" && v.trim().length > 0 ? v : null
}

/** 可空字段严格读取：只接受 null 或非空字符串（**保留原值**）；其余一律拒绝。 */
function readNullableStr(v) {
  if (v === null) return { ok: true, value: null }
  if (typeof v !== "string" || v.trim().length === 0) return { ok: false }
  return { ok: true, value: v }
}

/**
 * 解析调用面的 request。**只接受一段纯 JSON**（容忍前后空白，不容额外指令/代码围栏）：
 * `JSON.parse` 对"JSON 后追加一句话"天然失败——这就是"抄错即明确失败"的实现。
 * 自述 subject 必须等于按字段重算的 subject，抄错/篡改任何字段都在这里落地。
 */
function parseVerifierRequest(text) {
  if (!nonEmpty(text)) return null
  let doc
  try {
    doc = JSON.parse(normalizeEol(text).trim())
  } catch {
    return null
  }
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) return null
  // 未知键 = 夹带（哪怕它自称注释/元数据）：整份拒绝。subject 重算只覆盖已知字段，
  // 挡不住 `{"instruction": "..."}` 这类随调用正文一起进 verifier 上下文的私货。
  for (const key of Object.keys(doc)) {
    if (!VERIFIER_REQUEST_KEYS.has(key)) return null
  }
  if (doc.schema_version !== VERIFIER_REQUEST_SCHEMA_VERSION) return null
  if (doc.kind !== VERIFIER_REQUEST_KIND) return null
  if (typeof doc.subject_id !== "string" || !SUBJECT_ID_PATTERN.test(doc.subject_id)) return null
  if (typeof doc.prompt_sha256 !== "string" || !SUBJECT_ID_PATTERN.test(doc.prompt_sha256)) return null
  if (typeof doc.material_sha256 !== "string" || !SUBJECT_ID_PATTERN.test(doc.material_sha256)) return null
  const feature = readRequiredStr(doc.feature)
  const phase = readRequiredStr(doc.phase)
  const promptPath = readRequiredStr(doc.prompt_path)
  if (feature === null || phase === null || promptPath === null) return null
  const gateFingerprint = readNullableStr(doc.gate_fingerprint)
  const sourceCommitSha = readNullableStr(doc.source_commit_sha)
  const worktreeDigest = readNullableStr(doc.worktree_digest)
  if (!gateFingerprint.ok || !sourceCommitSha.ok || !worktreeDigest.ok) return null
  const fields = {
    feature,
    phase,
    prompt_path: promptPath,
    prompt_sha256: doc.prompt_sha256,
    material_sha256: doc.material_sha256,
    gate_fingerprint: gateFingerprint.value,
    source_commit_sha: sourceCommitSha.value,
    worktree_digest: worktreeDigest.value,
  }
  if (computeRequestSubjectId(fields) !== doc.subject_id) return null
  return { subject_id: doc.subject_id, ...fields }
}

function parseResultBlock(text) {
  const bodies = collectBlockBodies(text, RESULT_BLOCK_OPEN, RESULT_BLOCK_CLOSE)
  if (bodies.length !== 1) return null
  const body = bodies[0]
  const subjectId = readBlockField(body, "verifier_subject_id")
  const verdict = readBlockField(body, "verdict")
  const blockerRaw = readBlockField(body, "blocker_count")
  if (!subjectId || !SUBJECT_ID_PATTERN.test(subjectId)) return null
  if (verdict !== "PASS" && verdict !== "FAIL") return null
  if (blockerRaw === null || !/^\d+$/.test(blockerRaw)) return null
  return { subject_id: subjectId, verdict, blocker_count: Number(blockerRaw) }
}

function computeResultSha256(verdict, blockerCount, reportText) {
  return sha256(
    [`verdict=${verdict}`, `blocker_count=${blockerCount}`, "report_text:", normalizeEol(reportText)].join("\n"),
  )
}

// --------------------------------------------------------------------------
// 2. 终稿信封解析（本机制特有）
// --------------------------------------------------------------------------

/**
 * 解析 opencode `task` 工具的输出信封：
 *   `<task id="ses_…" state="completed"><task_result>正文</task_result></task>`
 * 失败态用 `<task_error>` 承载正文，`state` 非 completed。
 *
 * **正文原样返回**，不 trim 内部内容——它要参与结论指纹重算。
 */
function parseTaskEnvelope(text) {
  if (!nonEmpty(text)) return null
  const norm = normalizeEol(text)
  const head = /<task\s+id="([^"]*)"\s+state="([^"]*)"\s*>/.exec(norm)
  if (!head) return null
  const bodies = collectBlockBodies(norm, "<task_result>", "</task_result>")
  const errors = collectBlockBodies(norm, "<task_error>", "</task_error>")
  if (bodies.length + errors.length !== 1) return null
  const isError = errors.length === 1
  const raw = isError ? errors[0] : bodies[0]
  // 信封在正文两侧各加了一个换行（Rr 的 join）——只剥这一层，内部内容不动。
  const body = raw.replace(/^\n/, "").replace(/\n$/, "")
  return { session_id: head[1], state: head[2], kind: isError ? "task_error" : "task_result", text: body }
}

// --------------------------------------------------------------------------
// 3. 项目根与报告目录
// --------------------------------------------------------------------------

// 与三个 claude-kernel hook 同款的厂商无关加固：取首个含 hooks 真实依赖标记的候选。
const PROJECT_ROOT_MARKERS = [
  ["framework", "agents", "shared", "guard-framework-write-core.mjs"],
  ["framework", "harness", "scripts", "check-receipt.ts"],
]

function hasProjectRootMarker(root) {
  try {
    return PROJECT_ROOT_MARKERS.some((parts) => fs.existsSync(path.join(root, ...parts)))
  } catch {
    return false
  }
}

function normalizeCandidate(value) {
  return typeof value === "string" && value.trim() ? path.resolve(value.trim()) : null
}

/**
 * 候选序：插件自锚（<root>/.opencode/plugin/ 上跳两级）→ worktree → directory → cwd。
 * 自锚最权威：插件文件物理位于实例根下，而 opencode 的 directory 会随会话 cd 漂移。
 * 全不中时按同序取首个非空值。
 */
function resolveProjectRoot(input) {
  let selfAnchor = null
  try {
    selfAnchor = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..")
  } catch {
    selfAnchor = null
  }
  const worktree = normalizeCandidate(input?.worktree)
  const directory = normalizeCandidate(input?.directory)
  const candidates = [selfAnchor, worktree, directory, process.cwd()].filter(Boolean)
  for (const cand of candidates) {
    if (hasProjectRootMarker(cand)) return cand
  }
  return worktree ?? directory ?? process.cwd()
}

function verifierReportJsonFilename(subjectId) {
  return `verifier.report.${subjectId}.json`
}

function verifierReportMdFilename(subjectId) {
  return `verifier.report.${subjectId}.md`
}

function readJSONSafe(p) {
  try {
    if (!fs.existsSync(p)) return null
    return JSON.parse(fs.readFileSync(p, "utf-8"))
  } catch {
    return null
  }
}

/**
 * `paths.reports_dir_pattern` 缺席时的默认值——**必须与 TS 侧逐字一致**。
 * 沿用别的值会让 runner 与本插件写向两个目录：证据发布在 A、验真读 B，等于静默失联。
 */
const DEFAULT_REPORTS_REL = (feature, phase) => `doc/features/${feature}/${phase}/reports`

/** 对齐 harness/config.featurePhaseReportsDir —— 插件不落 TS，纯 Node 复刻占位符语义。 */
function resolveFeaturePhaseReportDir(projectRoot, feature, phase) {
  if (!feature || !phase || feature === "unknown" || phase === "unknown") return null
  try {
    const cfgPath = path.resolve(projectRoot, "framework.config.json")
    if (feature === "_global") {
      return path.resolve(projectRoot, "framework/harness/reports/_global", phase)
    }
    let pattern = null
    try {
      if (fs.existsSync(cfgPath)) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf-8"))
        const p = cfg?.paths?.reports_dir_pattern
        if (typeof p === "string" && p.trim()) pattern = p.trim()
      }
    } catch {
      pattern = null
    }
    if (pattern) {
      const rel = pattern.replace(/<feature>/g, feature).replace(/<phase>/g, phase)
      return path.resolve(projectRoot, rel)
    }
    return path.resolve(projectRoot, DEFAULT_REPORTS_REL(feature, phase))
  } catch {
    return path.resolve(projectRoot, DEFAULT_REPORTS_REL(feature, phase))
  }
}

function toPosixRel(projectRoot, abs) {
  return path.relative(projectRoot, abs).replace(/\\/g, "/")
}

/**
 * claimed path 只做等值核对，**绝不**作写入目标。先拒绝形态越界（绝对路径 / .. /
 * 盘符 / 反斜杠混写），再要求与自行推导的 canonical 路径逐字符相等。
 */
function claimedPathMatches(claimed, canonicalRel) {
  if (typeof claimed !== "string" || !claimed.trim()) return false
  const norm = claimed.trim().replace(/\\/g, "/")
  if (norm.startsWith("/") || /^[A-Za-z]:/.test(norm)) return false
  if (norm.split("/").some((seg) => seg === "..")) return false
  return norm === canonicalRel
}

// --------------------------------------------------------------------------
// 4. 落盘
// --------------------------------------------------------------------------

function ensureDir(d) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true })
}

function writeFileAtomic(p, content) {
  ensureDir(path.dirname(p))
  const tmp = `${p}.tmp-${process.pid}-${Date.now()}`
  fs.writeFileSync(tmp, content, "utf-8")
  fs.renameSync(tmp, p)
}

/**
 * **仅当不存在时创建**，且目标一旦出现即是完整内容。
 *
 * 原子替换只保证"文件不写半截"，**不保证**「读→判断→写」整段原子。两个并发 verifier
 * 都读到"文件不存在"就会双双写 published，后写者覆盖前写者——PASS 吞掉 FAIL。link()
 * 把"存在性检查 + 落地"合成一次原子操作：抢输的一方拿到 EEXIST，回到 CAS 循环重新读、
 * 重新裁决，于是必然看见对方的结论并升级为 conflict。
 *
 * 硬链接在少数文件系统上不可用，退回 `wx` 独占创建——独占语义相同。
 */
function createExclusive(absPath, content) {
  ensureDir(path.dirname(absPath))
  const tmp = `${absPath}.new-${process.pid}-${Date.now()}`
  try {
    fs.writeFileSync(tmp, content, "utf-8")
    try {
      fs.linkSync(tmp, absPath)
      return true
    } catch (err) {
      if (err && err.code === "EEXIST") return false
      fs.writeFileSync(absPath, content, { encoding: "utf-8", flag: "wx" })
      return true
    }
  } catch (err) {
    if (err && err.code === "EEXIST") return false
    throw err
  } finally {
    try {
      fs.unlinkSync(tmp)
    } catch {
      /* best-effort */
    }
  }
}

function buildMarkdownProjection(doc) {
  const lines = [
    "# Verifier 子 agent 报告（人读投影）",
    "",
    "> 机器真源是同目录 `verifier.report.<subject>.json`。**本 MD 不被任何机器消费者解析**——",
    "> 编辑它不会改变任何门禁结论，也不能让不合格的报告通过 check-receipt。",
    "",
    `- state: ${doc.state}`,
    `- feature: ${doc.feature}`,
    `- phase: ${doc.phase}`,
    `- verifier_subject_id: ${doc.subject_id}`,
    `- verdict: ${doc.verdict}`,
    `- blocker_count: ${doc.blocker_count}`,
    `- agent_id: ${doc.agent_id}`,
    `- agent_type: ${doc.agent_type || "(empty)"}`,
    `- generated_at: ${doc.generated_at}`,
  ]
  if (doc.state === "conflict") {
    lines.push(
      "",
      "## ⚠ CONFLICT — 同一 subject 收到互不相同的 verifier 结论",
      "",
      "同 subject 下出现不同 agent_id 或不同 result hash。两侧都记录在 JSON 的 `conflict.sides`；",
      "check-receipt 对本态**必 FAIL**（绝不保留先到的 PASS 静默吞掉后到的 FAIL）。",
      "",
      "**恢复步骤**（重跑 harness 只有在审查材料真的变了时才换代 subject；",
      "材料没变时会回到同一个 conflict）：",
      "  1. 停止或等待同 subject 的**全部** verifier 结束；",
      "  2. 删除这份 conflict 件——它已不是任何一方的结论，留着只会持续 FAIL；",
      "  3. 只启动**一个** verifier，把 summary.verifier_request 指向的 request JSON 整段投递。",
    )
  }
  return [
    ...lines,
    "",
    "## verifier 结论正文",
    "",
    "```",
    (doc.report_text ?? "").slice(0, 20000),
    "```",
    "",
    `> 本投影由 ${SELF_DESCRIPTION} 从 verifier.report.<subject>.json 生成。`,
    "",
  ].join("\n")
}

/**
 * bedside fail-closed：一切绑定不成立的形态统一落这里。
 * 绝不触碰 canonical JSON，绝不回退 .current-phase.json，绝不丢数据。
 */
function writeBedside(projectRoot, reason, detail) {
  const dir = path.resolve(projectRoot, "framework/harness/state")
  const doc = {
    schema_version: VERIFIER_REPORT_SCHEMA_VERSION,
    state: "bedside",
    reason,
    generated_at: new Date().toISOString(),
    ...detail,
  }
  try {
    writeFileAtomic(path.join(dir, "last-verifier-report.json"), JSON.stringify(doc, null, 2) + "\n")
    writeFileAtomic(
      path.join(dir, "last-verifier-report.md"),
      [
        "# Verifier 报告（bedside · 非权威）",
        "",
        `- state: bedside`,
        `- reason: ${reason}`,
        `- generated_at: ${doc.generated_at}`,
        `- subject_id: ${detail?.subject_id ?? "(n/a)"}`,
        `- agent_id: ${detail?.agent_id ?? "(n/a)"}`,
        "",
        "本报告**未通过身份绑定**，不构成任何阶段的闭环凭证，机器消费者不会读取它。",
        "常见原因：调用方投的不是那份 request JSON（手抄/夹带/投了 ai-prompt 全文）、",
        "verifier 未输出唯一终态块、ai-prompt.md 已被新一轮 harness 换代（prompt_hash_mismatch）、",
        "subject 已换代（迟到报告）、子会话身份缺失或与终稿信封自述不符、",
        "宿主截断了终稿而全文旁路件读不到。",
        "",
        "## 结论正文（截取）",
        "",
        "```",
        (detail?.report_text ?? "").slice(0, 8000),
        "```",
        "",
        `> 由 ${SELF_DESCRIPTION} 生成。`,
        "",
      ].join("\n"),
    )
  } catch {
    /* bedside 写不下去也不得让插件抛错打断宿主会话 */
  }
  return { state: "bedside", reason }
}

// --------------------------------------------------------------------------
// 5. 发布主流程（纯 I/O 装配，可被测试直接调用）
// --------------------------------------------------------------------------

/**
 * 从一次 `task` 工具完成事件发布 verifier 结论。
 *
 * @param {object} p
 * @param {string} p.projectRoot 实例工程根
 * @param {object} p.args        `tool.execute.after` 的 `input.args`（含 prompt / subagent_type）
 * @param {object} p.output      `tool.execute.after` 的 `output`（含 metadata / output）
 * @param {string=} p.toolCallId 仅作审计
 * @param {number=} p.casTestDelayMs 测试缝：在 CAS 的读与写之间人为拉开窗口
 * @returns {Promise<{state: string, reason?: string, json_path?: string}>}
 */
async function publishFromTaskResult({ projectRoot, args, output, toolCallId, casTestDelayMs }) {
  const str = (v) => (typeof v === "string" && v.trim() ? v.trim() : null)

  const metadata = output && typeof output === "object" ? output.metadata : null
  const childSessionId = str(metadata?.sessionId)
  const parentSessionId = str(metadata?.parentSessionId)
  const agentType = typeof args?.subagent_type === "string" ? args.subagent_type : ""
  const invocationText = typeof args?.prompt === "string" ? args.prompt : ""

  const audit = {
    child_session_id: childSessionId,
    parent_session_id: parentSessionId,
    tool_call_id: str(toolCallId),
    recorded_by: SELF_DESCRIPTION,
  }

  // ① 执行体身份：子会话必须在场且与主会话不同。缺失或同一 = 没有独立执行体。
  if (!childSessionId) {
    return writeBedside(projectRoot, "payload_missing_agent_id", { agent_type: agentType, audit })
  }
  if (!parentSessionId) {
    return writeBedside(projectRoot, "payload_missing_parent_session_id", {
      agent_id: childSessionId, agent_type: agentType, audit,
    })
  }
  if (childSessionId === parentSessionId) {
    return writeBedside(projectRoot, "verifier_not_independent", {
      agent_id: childSessionId, agent_type: agentType, audit,
      detail: "子会话 id 与主会话 id 相同——结论并非由独立执行体产出，不构成独立审查证据。",
    })
  }

  // ② 终稿：宿主截断时必须改读全文旁路件，否则末尾终态块会被切掉而误判「无终态块」。
  let envelopeText = typeof output?.output === "string" ? output.output : ""
  if (metadata?.truncated === true) {
    const full = str(metadata?.outputPath)
    let recovered = null
    try {
      if (full && fs.existsSync(full)) recovered = fs.readFileSync(full, "utf-8")
    } catch {
      recovered = null
    }
    if (recovered === null) {
      return writeBedside(projectRoot, "final_draft_truncated", {
        agent_id: childSessionId, agent_type: agentType, audit,
        claimed_output_path: full,
        detail:
          "宿主按 tool_output 上限截断了终稿，且全文旁路件读不到——终态块在正文末尾，" +
          "截断后无法判定结论。请调低输出规模或恢复 outputPath 后重跑 verifier。",
      })
    }
    envelopeText = recovered
  }

  const envelope = parseTaskEnvelope(envelopeText)
  if (!envelope) {
    return writeBedside(projectRoot, "task_envelope_unparseable", {
      agent_id: childSessionId, agent_type: agentType, audit, report_text: envelopeText,
    })
  }
  if (envelope.session_id !== childSessionId) {
    return writeBedside(projectRoot, "session_mismatch_metadata_vs_envelope", {
      agent_id: childSessionId, agent_type: agentType, audit,
      envelope_session_id: envelope.session_id, report_text: envelope.text,
    })
  }
  if (envelope.state !== "completed" || envelope.kind !== "task_result") {
    return writeBedside(projectRoot, "task_not_completed", {
      agent_id: childSessionId, agent_type: agentType, audit,
      task_state: envelope.state, report_text: envelope.text,
    })
  }

  const reportText = envelope.text
  if (!reportText.trim()) {
    return writeBedside(projectRoot, "payload_missing_last_assistant_message", {
      agent_id: childSessionId, agent_type: agentType, audit,
    })
  }

  // ③ result subject（终态块）
  const resultBlock = parseResultBlock(reportText)
  if (!resultBlock) {
    return writeBedside(projectRoot, "result_block_unparseable", {
      agent_id: childSessionId, agent_type: agentType, audit, report_text: reportText,
    })
  }

  // ④ invocation request（工具入参本身——本机制不需要读子会话转录）
  if (!invocationText.trim()) {
    return writeBedside(projectRoot, "invocation_prompt_unreadable", {
      agent_id: childSessionId, agent_type: agentType, audit,
      subject_id: resultBlock.subject_id, report_text: reportText,
      detail: "task 工具入参 prompt 为空——拿不到调用凭证，无法判定这份结论审的是谁。",
    })
  }
  const invocation = parseVerifierRequest(invocationText)
  if (!invocation) {
    return writeBedside(projectRoot, "invocation_request_unparseable", {
      agent_id: childSessionId, agent_type: agentType, audit,
      subject_id: resultBlock.subject_id, report_text: reportText,
      detail:
        "task 工具的 prompt 参数必须是 summary.verifier_request 指向的那份 " +
        "verifier.request.<subject>.json 的**完整 JSON 正文**（可含前后空白，" +
        "不得有任何附加文字、代码围栏或字段改写）。",
    })
  }

  if (invocation.subject_id !== resultBlock.subject_id) {
    return writeBedside(projectRoot, "subject_mismatch_invocation_vs_result", {
      agent_id: childSessionId, agent_type: agentType, audit,
      invocation_subject: invocation.subject_id, result_subject: resultBlock.subject_id,
      report_text: reportText,
    })
  }

  // ⑤ 写入路径**自行推导**（config + request 的 feature/phase），claimed path 仅等值核对。
  const reportDir = resolveFeaturePhaseReportDir(projectRoot, invocation.feature, invocation.phase)
  if (!reportDir) {
    return writeBedside(projectRoot, "report_dir_unresolvable", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      report_text: reportText,
    })
  }
  const jsonPath = path.join(reportDir, verifierReportJsonFilename(invocation.subject_id))
  const mdPath = path.join(reportDir, verifierReportMdFilename(invocation.subject_id))
  const promptPath = path.join(reportDir, AI_PROMPT_FILENAME)
  const canonicalPromptRel = toPosixRel(projectRoot, promptPath)
  if (!claimedPathMatches(invocation.prompt_path, canonicalPromptRel)) {
    return writeBedside(projectRoot, "claimed_path_rejected", {
      agent_id: childSessionId, agent_type: agentType, audit,
      claimed_prompt_path: invocation.prompt_path, derived_prompt_path: canonicalPromptRel,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      report_text: reportText,
    })
  }

  // ⑥ summary 现值——迟到报告在此被拦（subject 已换代 → stale，禁止覆盖 canonical）。
  const summary = readJSONSafe(path.join(reportDir, "summary.json"))
  const currentSubject = str(summary?.verifier_subject_id)
  if (!currentSubject) {
    return writeBedside(projectRoot, "summary_subject_absent", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      report_text: reportText,
    })
  }
  if (currentSubject !== invocation.subject_id) {
    return writeBedside(projectRoot, "subject_stale", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase,
      subject_id: invocation.subject_id, current_summary_subject: currentSubject,
      report_text: reportText,
    })
  }

  // ⑦ 磁盘原件对账：verifier 审的到底是不是 request 所指的那份字节。
  // 这是**误配检测**（harness 重跑过、文件已换代），不是防篡改。
  let promptOnDisk = null
  try {
    if (fs.existsSync(promptPath)) promptOnDisk = fs.readFileSync(promptPath, "utf-8")
  } catch {
    promptOnDisk = null
  }
  if (promptOnDisk === null) {
    return writeBedside(projectRoot, "prompt_missing", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      prompt_path: canonicalPromptRel, report_text: reportText,
    })
  }
  const promptSha = sha256(normalizeEol(promptOnDisk))
  if (promptSha !== invocation.prompt_sha256) {
    return writeBedside(projectRoot, "prompt_hash_mismatch", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      prompt_path: canonicalPromptRel,
      declared_prompt_sha256: invocation.prompt_sha256, observed_prompt_sha256: promptSha,
      detail:
        "request 所声明的 ai-prompt.md 与磁盘现文件不符——多半是这期间又跑了一次 harness。" +
        "请用当前 summary.verifier_request 指向的新 request JSON 重跑 verifier。",
      report_text: reportText,
    })
  }

  // ⑧ 发布：CAS 循环（幂等 / conflict 单调升级 / 独占创建）。
  //
  // 本段只处理**同一 subject 内**的并发；跨 subject 已由文件分区在结构上隔离。
  // 两条不变量：① 首次发布只能经 createExclusive（原子 create-if-absent）；
  // ② 一旦进入 conflict 就**单调吸收**，永不回落 published。
  const resultSha = computeResultSha256(resultBlock.verdict, resultBlock.blocker_count, reportText)
  const side = {
    agent_id: childSessionId,
    agent_type: agentType,
    verdict: resultBlock.verdict,
    blocker_count: resultBlock.blocker_count,
    result_sha256: resultSha,
    observed_at: new Date().toISOString(),
  }
  const freshDoc = {
    schema_version: VERIFIER_REPORT_SCHEMA_VERSION,
    state: "published",
    feature: invocation.feature,
    phase: invocation.phase,
    subject_id: invocation.subject_id,
    // 两个 subject 分别存——此后验真只比仓内三值，绝不重开会话记录。
    invocation_subject: invocation.subject_id,
    result_subject: resultBlock.subject_id,
    agent_id: childSessionId,
    agent_type: agentType,
    verdict: resultBlock.verdict,
    blocker_count: resultBlock.blocker_count,
    result_sha256: resultSha,
    report_text: reportText,
    report_md_path: toPosixRel(projectRoot, mdPath),
    generated_at: new Date().toISOString(),
    audit,
  }

  /** 把既有件与本轮结论合并为 conflict 态（保留先到侧作正文，两侧全记）。 */
  const toConflict = (existing) => {
    const priorSides =
      Array.isArray(existing?.conflict?.sides) && existing.conflict.sides.length > 0
        ? existing.conflict.sides
        : [
            {
              agent_id: existing.agent_id,
              agent_type: existing.agent_type,
              verdict: existing.verdict,
              blocker_count: existing.blocker_count,
              result_sha256: existing.result_sha256,
              observed_at: existing.generated_at,
            },
          ]
    const known = new Set(priorSides.map((s) => `${s.agent_id}::${s.result_sha256}`))
    const sides = known.has(`${side.agent_id}::${side.result_sha256}`) ? priorSides : [...priorSides, side]
    return {
      ...existing,
      schema_version: VERIFIER_REPORT_SCHEMA_VERSION,
      state: "conflict",
      conflict: {
        detected_at: existing?.conflict?.detected_at ?? new Date().toISOString(),
        // 诚实标注：三方及以上并发时，最后一次写入可能覆盖掉另一并发写者刚追加的侧记录。
        // **state=conflict 本身不会丢**（单调吸收），check-receipt 照 FAIL。
        sides_completeness: "best_effort",
        sides,
      },
    }
  }

  const delayMs = Number.parseInt(
    casTestDelayMs ?? process.env.MAISON_VERIFIER_HOOK_TEST_CAS_DELAY_MS ?? "",
    10,
  )

  let published = null
  for (let attempt = 0; attempt < 8 && published === null; attempt++) {
    const existing = readJSONSafe(jsonPath)
    if (attempt === 0 && Number.isFinite(delayMs) && delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }

    if (existing === null) {
      const body = JSON.stringify(freshDoc, null, 2) + "\n"
      let created = false
      try {
        created = createExclusive(jsonPath, body)
      } catch {
        break
      }
      if (created) published = freshDoc
      continue // 抢输 → 重读重裁
    }

    // 文件名已含 subject，所以"自称别的 subject"只可能是内容损坏或人为伪造。
    // **fail-closed，绝不尝试移动或修复**——修复即重新引入"动别人的文件"这一动作。
    if (
      existing.schema_version !== VERIFIER_REPORT_SCHEMA_VERSION ||
      existing.subject_id !== invocation.subject_id
    ) {
      return writeBedside(projectRoot, "canonical_subject_mismatch", {
        agent_id: childSessionId, agent_type: agentType, audit,
        feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
        found_subject: existing.subject_id ?? null,
        report_path: toPosixRel(projectRoot, jsonPath),
        report_text: reportText,
      })
    }

    if (existing.state !== "conflict" && existing.agent_id === childSessionId && existing.result_sha256 === resultSha) {
      // 幂等：同 subject + 同 agent_id + 同 result hash。**不重写**——重写会换
      // generated_at、改变字节，让刚封存的 evidence manifest 无谓 stale。
      return { state: "published", reason: "idempotent", json_path: toPosixRel(projectRoot, jsonPath) }
    }

    const merged = toConflict(existing)
    try {
      writeFileAtomic(jsonPath, JSON.stringify(merged, null, 2) + "\n")
      published = merged
    } catch {
      break
    }
  }

  if (published === null) {
    // CAS 未能收敛（重试耗尽 / I/O 故障）：绝不猜、绝不覆盖，落 bedside。
    return writeBedside(projectRoot, "publish_cas_exhausted", {
      agent_id: childSessionId, agent_type: agentType, audit,
      feature: invocation.feature, phase: invocation.phase, subject_id: invocation.subject_id,
      report_text: reportText,
    })
  }

  try {
    writeFileAtomic(mdPath, buildMarkdownProjection(published))
  } catch {
    /* 人读投影写失败不影响机器真源 */
  }

  return { state: published.state, json_path: toPosixRel(projectRoot, jsonPath) }
}

// --------------------------------------------------------------------------
// 6. 插件入口
// --------------------------------------------------------------------------

/**
 * opencode 插件：只挂 `tool.execute.after`，只对 `task` 工具的完成事件发布结论。
 *
 * **不按 subagent_type 过滤**：归属完全由调用侧那份 request JSON 决定——非 verifier 的
 * 子 agent 天然没有合法 request，会在 invocation_request_unparseable 处 fail-closed。
 * 按名字过滤反而会在实例把 agent 改名时静默失效。
 *
 * 一切异常对宿主 fail-open（绝不抛出打断会话），对证据 fail-closed（不发布 canonical）。
 */
const plugin = async (input) => {
  const projectRoot = resolveProjectRoot(input)
  return {
    "tool.execute.after": async (hookInput, hookOutput) => {
      try {
        if (hookInput?.tool !== TASK_TOOL_ID) return
        await publishFromTaskResult({
          projectRoot,
          args: hookInput?.args,
          output: hookOutput,
          toolCallId: hookInput?.callID,
        })
      } catch {
        /* fail-open 对宿主：插件异常不得打断 opencode 会话 */
      }
    },
  }
}

/**
 * 测试面。**内部函数一律挂在 default 上，不做具名导出**——宿主实证（opencode 1.18.26）：
 * 装载器把插件模块里**每一个导出的函数**都当插件入口调用一遍，入参是 PluginInput。
 * 于是 `publishFromTaskResult(pluginInput)` 会拿着一堆 undefined 跑进 path.resolve 抛错，
 * **整个插件的注册随之中断**——现场表现是「task 跑完了，报告和 bedside 都没有」。
 * 具名导出因此不是风格问题，是会静默关掉发布器的实装错误。
 */
plugin.internals = {
  TASK_TOOL_ID,
  SELF_DESCRIPTION,
  canonicalRequestInput,
  computeRequestSubjectId,
  computeResultSha256,
  parseVerifierRequest,
  parseResultBlock,
  parseTaskEnvelope,
  resolveProjectRoot,
  resolveFeaturePhaseReportDir,
  writeBedside,
  publishFromTaskResult,
}

export default plugin
