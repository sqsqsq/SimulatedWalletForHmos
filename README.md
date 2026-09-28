# SimulatedWalletForHmos

Story Extension 的维护仓。Story Extension 挂在 AgentMaison framework 上，引导 AI 从需求材料一路走到 spec、plan 和代码。
本仓放着它的开发源、一份装好它的完整鸿蒙钱包工程（demo），以及维护它用的测试与方案。

| 目录 | 是什么 |
|---|---|
| `extensions/` | Story Extension 开发源 |
| `demo/` | 完整消费工程：钱包业务代码 + `framework/` 发布件 + 已安装的 Extension 发布版。人手试用 `/story` 在这里 |
| `test/` | 维护域：维护契约、测试协议与脚本、Case、需求与方案 |
| `tools/cli/` | 实跑测试调起的 CLI runtime |

维护入口是 [AGENTS.md](AGENTS.md)（结构、framework 接入、Extension 安装与发布），开工前再完整读 [test/AGENTS.md](test/AGENTS.md)。
测试怎么跑看 [test/TEST.md](test/TEST.md)。

## 新 checkout 恢复依赖

依赖目录不入库，clone 之后按下面装齐（PowerShell，在仓根执行）：

```powershell
python -m pip install pytest pytest-xdist pyyaml                     # 维护脚本与测试
cd demo/framework/harness; npm install; cd ../../..                  # framework harness（门禁、渲染脚本）
cd demo/.opencode; npm install @opencode-ai/plugin@1.18.26; cd ../..  # opencode 插件；package.json 由 opencode 生成、不入库
$env:OHPM_EXE = "<DevEco>\tools\ohpm\bin\ohpm.bat"                    # 鸿蒙依赖用本机 DevEco 自带的 ohpm 与 node
$env:DEVECO_NODE = "<DevEco>\tools\node\node.exe"
demo/scripts/build-dependence.ps1                                     # 重建 demo 各模块的 oh_modules
```

`package-lock.json` 不入库，harness 的依赖会解析到各自版本范围内的最新补丁版。人手试用 `/story` 还要装本地需求系统，见 TEST §0.3。
