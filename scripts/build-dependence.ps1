#requires -Version 5.1
<#
.SYNOPSIS
  Install ohpm dependencies per module (order from build-profile.json5), then ohpm install --all at repo root.

.DESCRIPTION
  Single source of truth: repository root build-profile.json5 → "modules"[].srcPath (see list-build-profile-module-paths.cjs).
  Maintain "modules" order as bottom-up local file: dependencies so ohpm can link HARs; the script does not validate the DAG.

  Environment:
    OHPM_EXE      Optional. Full path to ohpm executable; default: ohpm on PATH.
    DEVECO_NODE   Optional. Path to Node (DevEco). Default: D:\Program Files\Huawei\DevEco Studio\tools\node\node.exe

  Prerequisites: ohpm available; Node for the resolver script.
#>

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path

$DefaultNode = 'D:\Program Files\Huawei\DevEco Studio\tools\node\node.exe'
$NodeExe = if ($env:DEVECO_NODE) { $env:DEVECO_NODE } else { $DefaultNode }
if (-not (Test-Path -LiteralPath $NodeExe)) {
  Write-Error "Node not found: $NodeExe. Set DEVECO_NODE to DevEco tools\node\node.exe."
  exit 1
}

$OhpmExe = $env:OHPM_EXE
if (-not $OhpmExe) {
  $cmd = Get-Command ohpm -ErrorAction SilentlyContinue
  if (-not $cmd) {
    Write-Error 'ohpm not on PATH. Install DevEco OHPM or set OHPM_EXE.'
    exit 1
  }
  $OhpmExe = $cmd.Path
}

function Invoke-Ohpm {
  param([Parameter(Mandatory = $true)][string[]]$OhpmArgs)
  & $OhpmExe @OhpmArgs
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$Resolver = Join-Path $ScriptDir 'list-build-profile-module-paths.cjs'
$ProfilePath = Join-Path $RepoRoot 'build-profile.json5'
if (-not (Test-Path -LiteralPath $ProfilePath)) {
  Write-Error "Missing build-profile.json5: $ProfilePath"
  exit 1
}

Push-Location $RepoRoot
try {
  $moduleRelPaths = @(& $NodeExe $Resolver $ProfilePath)
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }

  foreach ($rel in $moduleRelPaths) {
    $trim = $rel.Trim()
    if ([string]::IsNullOrWhiteSpace($trim)) {
      continue
    }
    $normalized = $trim -replace '/', [System.IO.Path]::DirectorySeparatorChar
    if ($normalized.StartsWith('.' + [System.IO.Path]::DirectorySeparatorChar)) {
      $normalized = $normalized.Substring(2)
    }
    $modRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $normalized))
    if (-not (Test-Path -LiteralPath $modRoot)) {
      Write-Error "Module path does not exist: $modRoot (from build-profile.json5)"
      exit 1
    }
    Write-Host "ohpm install: $modRoot"
    Push-Location $modRoot
    try {
      Invoke-Ohpm @('install')
    } finally {
      Pop-Location
    }
  }

  Write-Host "ohpm install --all: $RepoRoot"
  Invoke-Ohpm @('install', '--all')
} finally {
  Pop-Location
}

exit 0
