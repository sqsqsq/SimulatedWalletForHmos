#requires -Version 5.1
<#
.SYNOPSIS
  Run build-dependence.ps1, then assembleHap with hvigorw via DevEco Node.

.DESCRIPTION
  Environment:
    DEVECO_NODE     Node executable (default: D:\...\DevEco Studio\tools\node\node.exe)
    DEVECO_HVIGORW  Path to hvigorw.js (default: ...\tools\hvigor\bin\hvigorw.js)
    OHPM_EXE        Optional; passed through to build-dependence.ps1

  Working directory for hvigor is the repository root (where hvigorfile.ts lives).
#>

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path

$DependenceScript = Join-Path $ScriptDir 'build-dependence.ps1'
& $DependenceScript
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

$DefaultNode = 'D:\Program Files\Huawei\DevEco Studio\tools\node\node.exe'
$DefaultHvigorw = 'D:\Program Files\Huawei\DevEco Studio\tools\hvigor\bin\hvigorw.js'

$NodeExe = if ($env:DEVECO_NODE) { $env:DEVECO_NODE } else { $DefaultNode }
$Hvigorw = if ($env:DEVECO_HVIGORW) { $env:DEVECO_HVIGORW } elseif ($env:HVIGORW_JS) { $env:HVIGORW_JS } else { $DefaultHvigorw }

if (-not (Test-Path -LiteralPath $NodeExe)) {
  Write-Error "Node not found: $NodeExe. Set DEVECO_NODE."
  exit 1
}
if (-not (Test-Path -LiteralPath $Hvigorw)) {
  Write-Error "hvigorw.js not found: $Hvigorw. Set DEVECO_HVIGORW."
  exit 1
}

Push-Location $RepoRoot
try {
  Write-Host "hvigor assembleHap (release) in $RepoRoot"
  & $NodeExe $Hvigorw `
    '--mode', 'module', `
    '-p', 'product=default', `
    '-p', 'buildMode=release', `
    'assembleHap', `
    '--analyze=normal', `
    '--parallel', `
    '--incremental', `
    '--daemon'
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
