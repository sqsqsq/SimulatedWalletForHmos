# Hylyre vendor（hmos-app）

## 目录是什么

本目录是 **hmos-app** profile 集成真机自动化测试的 vendor 入口：内置 Hylyre **明文源码树**（`src/`，默认安装形态）与同版本 **py3-none-any wheel**（兼容/回退形态），整个目录**提交进 Git**（体量 < 1 MB），协作者 `git clone` 即可拿到，不依赖联网拉取 Hylyre 本体。

源码树全部为可 review 的文本文件，作为默认安装与验真入口；wheel 保留给 legacy/离线回退场景。两者由根部联合 schema 2 manifest 绑定，harness 双存时源码优先，源码缺失时仅回落到 manifest 明确声明且 hash 匹配的 wheel。

传递依赖（如设备侧 Hypium 栈）仍由首次 `ensure` 时通过 PyPI 镜像安装，不在本目录 vendor。

**本目录仅保留发布件**：`src/`、`hylyre-<version>-py3-none-any.whl`、`release.manifest.json`、本 README。Hylyre 发布包里的 `downstream-harness-requests.md` 等移交文档**不提交**进本目录。

## 布局与 manifest（schema 2）

```
vendor/hylyre/
├── src/                    # Hylyre 源码树（pip install <src> 直接可装）
│   ├── pyproject.toml
│   ├── README.md
│   └── hylyre/…            # 含 contracts/ package-data（json/yaml/md）
├── hylyre-0.4.1-py3-none-any.whl # schema 2 manifest 的 wheel 回退工件
├── release.manifest.json   # schema 2：hylyre_version + source{…} + wheel{…}
└── README.md               # 本文件（maison 所有，非 Hylyre 发布物）
```

- `source.files[]` 逐文件声明 sha256；`tree_sha256` = 对「POSIX 路径升序的 `<path>\n<sha256>\n` 拼接串」整体 sha256。
- `wheel.filename` / `wheel.sha256` / `wheel.size_bytes` 声明同版本 wheel；源码树存在时源码优先，源码缺失时才允许按该声明回落。
- 源文件统一 **LF** 落盘并按 LF 字节计算 hash；本仓 `.gitattributes` 全局 `eol=lf`，checkout 字节与声明恒等。
- harness 对齐判定**按 manifest 声明清单**复算 tree hash——vendor 内意外杂物（如 `__pycache__`）不会假触发"发布件损坏"；「src 内未声明文件」的检测由 Hylyre `--verify` 负责。

## 何时更新

- Hylyre 仓 `pyproject.toml` 版本号变更
- 工程内自检提示与 `release.manifest.json` 中的版本不一致
- 升级本 framework 集成并约定使用新版 Hylyre CLI

## 三步同步流程

与 Hylyre 文档 `docs/framework-vendor-bundle.md` 对齐：

```powershell
# ① 在 Hylyre 仓产出两类发布件
cd D:\1.code\Hylyre
python scripts/build_wheel.py --clean
python scripts/build_wheel.py --source --clean

# ② cp 到本目录（源码优先；联合 manifest；不拷移交 md）
$wheel = "D:\1.code\Hylyre\dist\release"
$source = "D:\1.code\Hylyre\dist\release-src"
$dst = "D:\1.code\agent-maison-br\profiles\hmos-app\vendor\hylyre"
Remove-Item -Recurse -Force "$dst\src" -ErrorAction Ignore
Remove-Item -Force "$dst\hylyre-*.whl" -ErrorAction Ignore
Copy-Item -Recurse -Force "$source\src" "$dst\src"
Copy-Item -Force "$wheel\hylyre-*.whl" $dst
$sourceManifest = Get-Content "$source\release.manifest.json" -Raw | ConvertFrom-Json
$wheelManifest = Get-Content "$wheel\release.manifest.json" -Raw | ConvertFrom-Json
$sourceManifest | Add-Member -NotePropertyName wheel -NotePropertyValue $wheelManifest.wheel -Force
$sourceManifest | ConvertTo-Json -Depth 20 | Set-Content "$dst\release.manifest.json" -Encoding utf8

# ③ 校验源码树与 wheel（integration_docs 缺失放行、根层自有文件免检）
python D:\1.code\Hylyre\scripts\build_wheel.py --verify $dst
$actualWheel = (Get-FileHash "$dst\$($wheelManifest.wheel.filename)").Hash.ToLower()
if ($actualWheel -ne $wheelManifest.wheel.sha256) { throw "wheel sha256 mismatch" }
```

同步后 Hylyre 发布包内如仍带 `integration_docs` 等移交文件，**不要**提交进 maison；把 harness 侧变更摘要补进下文「Framework 集成要点」。

## Framework 集成要点（vendor 0.4.1）

以下由 harness 已落地，消费者读 profile 文档即可，无需另附移交清单。

### 源码树安装（plan a7c3e9d1）

- `ensureHylyreReady` 双兼容 schema 1（wheel）/ schema 2（源码树，可带 wheel），**双存时源码优先**；安装命令等价 `pip install <src副本> "hylyre[device,mcp]"`，extras 与传递依赖照旧走镜像。
- 安装前 harness 会把 `src/` **按声明清单拷贝到 `.hylyre/build-src/` 临时副本**再交给 pip——pip ≥21.3 对目录是 in-tree build，直接装会在 vendor 目录产 `build/`、`*.egg-info/` 污染仓库。该副本装完即清，且下次安装前会先清空整个 `build-src/` 自愈残留。
- venv 内 `.hylyre-vendor-fingerprint.json` 记录 `artifact_kind`（wheel/source）与工件指纹（wheel sha256 / tree_sha256）；从 wheel 切到源码树、同版本补丁件、指纹缺失均自动触发 pip 对齐，**无需手删 `.hylyre/venv`**。
- 步骤键集 SSOT 消费直读 `src/hylyre/api/planned_step_keys.py`（不再从 whl zip 解包）。

### 冷重启与 force-stop（testing 阶段）

- `device-test-run.ts` 使用 **positional** `hdc shell aa force-stop <bundle>`（勿用 `-b`，部分本机会失败）。
- 默认 **冷重启**：`force-stop` 后再 `aa start`。配置 `framework.config.json > tools.hylyre.cold_restart_before_run`（hmos-app 默认 `true`）；环境变量 `HARNESS_DEVICE_TEST_COLD_RESTART=1/0` 优先。
- meta 字段：`cold_restart` / `cold_restart_attempted` / `cold_restart_ok`。

### `app page save`（快照缓存）

- 跑后按访问页面名逐个 `hylyre app page save`；页面名与业务 slug 一致，落盘 `doc/app-snapshot-cache/<bundle>/pages/<name>.json`。
- 可选 env：`HARNESS_HYLYRE_PAGE_SAVE_NAMES`（逗号分隔）；adhoc 可 `--skip-page-save`。
- 失败时 stderr + exit 归档到 run 目录 `hylyre-page-save.log`（非 silent）。

### personal setup 原子性（F3 · harness）

- 阶段入口（coding / ut / testing）内联 **`ensurePersonalSetup`**：半就绪 `framework.local.json`（如只记 `agent_adapter`、缺 DevEco）会在放行前自动确定性 repair（单 adapter / DevEco 探测）。
- `init-orchestrate record-adapter` 写 local 后 **best-effort** 补 DevEco；探测不到时不失败任务，阶段入口仍会校验 DevEco。

### Hylyre 0.4.1 CLI / 步骤与证据能力

- **`input`**：支持与 `touch` 一致的 `by_type` / 富选择器（`scope`/`within`/`index`/`all`/`visible` 等），或一步式 `into` 定位输入；无选择器时落当前聚焦框（仍建议先 `touch` 聚焦）。
- **`scroll_to`**：滚动前先匹配已在屏目标，避免对已可见项空滚。
- 选择器 `match` 只接受 `exact` / `contains`；显式 `exact` 失败不会再静默放宽为 `contains`，动作多命中时 fail-closed，并使用 `index` / `scope` / `within` / `all` 等既有字段消歧。
- 消费 trace/report 时以 `cases[].steps[]` 为证据真源，`tool_calls` 仅为兼容投影；先按 `failure_kind`、再按 `failure_code` 路由，`verification=inconclusive` 或 `evidence=incomplete` 不得判为已验证。
- 要求验证的断言必须有非空 evidence；Toast 断言的触发动作应紧邻断言，未覆盖触发窗口时不得作为验证证据。最低接入版本为 `hylyre>=0.4.1`，trace schema 为 `0.3-p0`；结构化 selector identity（`by_id` / `by_key` / `id` / `key` / `selected_id`）逐字保留，用户文本和值继续脱敏。
- 富选择器、`--failure-dir` 失败诊断等见 [`../../skills/device-testing/reference/hylyre-planned-step-fields.md`](../../skills/device-testing/reference/hylyre-planned-step-fields.md) 与 device-testing profile addendum。
- 上游能力需求与真机踩坑记录留在 **Hylyre 仓** 或开发 plan，不进本 vendor 目录。

## 升级原则

- Commit message 建议：`chore(vendor): hylyre <旧版本> -> <新版本>`（如 `0.4.0 -> 0.4.1`）
- 正文粘贴 `release.manifest.json` 中关键字段（如 `hylyre_version`、`source.tree_sha256`）
- **覆盖 vendor 后无需手删 `.hylyre/venv`**：协作者/用户用自然语言重新发起 **device-testing 真机测试**即可；**agent 在 device-testing Step 7 自跑 testing harness** 时，**`ensureHylyreReady`** 会按 manifest 版本与工件指纹自动 pip 对齐（`tools.hylyre.auto_install=true` 且未设置 `HYLYRE_PYTHON` 时）。**用户不直接执行 harness 脚本。**

## 故障排查

| 现象 | 处置 |
|------|------|
| `build_wheel.py --verify` 报 sha 不匹配 | 删除旧 `src/` 后重新从 `dist/release-src` 覆盖拷贝 |
| harness 报「vendor 源码树与 manifest 声明不一致（声明文件缺失）」 | src 半拷贝/被改：按同步流程②重新覆盖 `src/` 与 manifest |
| harness 报「vendor 发布件缺失」或 wheel sha 不匹配 | schema 2 双存布局须同时具备声明有效的 `src/` 或 manifest 背书的 wheel；按同步流程重新覆盖，并核对 `wheel.sha256` |
| Python 版本错误 | 使用 **Python 3.10+** 创建隔离环境 |
| `verify_report` / 缺 `report-sections.yaml` | `ensureHylyreReady` 会探测 contracts，缺失时对默认 venv 从 vendor 强制重装 |
| vendor 已更新但 venv 仍旧版 | 用户重新发起 device-testing；agent Step 7 自跑 testing harness 时会自动对齐；仍失败则查 `hylyre-doctor.log`，必要时删 `.hylyre/venv` 后由 agent 再跑 Step 7 |
| 设置了 `HYLYRE_PYTHON` 且版本与 manifest 不一致 | harness **BLOCKER**；在该环境手动升级 hylyre，或取消 `HYLYRE_PYTHON` 改用默认 venv |
| 连续多轮 testing 状态污染 | 确认 `cold_restart_before_run` 为 true 或 `HARNESS_DEVICE_TEST_COLD_RESTART=1`；日志中 force-stop 勿出现 `-b` 语法 |
| 只记 adapter 后 testing 报缺 DevEco | 确认 framework 版本含 personal setup 内联 repair；或手动 `check-personal-setup --ensure --phase testing` |

## 不要做

- **不要**手改 `src/` 内任何文件、`source.files[]`/`tree_sha256` 或 `wheel` hash；按上方流程由 Hylyre 两类发布件生成联合 manifest（逐文件/工件 sha 由 manifest 锁定）。
- **不要**把 Hylyre 同步包里的 `integration_docs` / 移交 md 提交进本目录；`.whl` 仅保留当前 manifest 声明的同版本工件。
- **不要**在 `src/` 里直接跑 `pip install`（in-tree build 会产 `build/`、`egg-info/` 污染）；harness 自动走临时副本。
- 设备栈等大体量传递依赖**不要**往本目录塞；走镜像与 pip 缓存。
