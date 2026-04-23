# Run Hypium UT via hvigor from project root (CLI, no DevEco UI).
# Usage: powershell -ExecutionPolicy Bypass -File ./scripts/run-ut.ps1
# Optional: set HVIGORW to full path of hvigorw.bat

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "oh-package.json5"))) {
  $root = (Get-Location).Path
}
Set-Location $root
Write-Host "Project root: $root"

function Find-Hvigorw {
  if ($env:HVIGORW -and (Test-Path -LiteralPath $env:HVIGORW)) { return $env:HVIGORW }
  $candidates = @()
  try {
    $ohpm = Get-Command ohpm -ErrorAction Stop
    $tools = Split-Path (Split-Path $ohpm.Source -Parent) -Parent
    $candidates += (Join-Path $tools "hvigor\bin\hvigorw.bat")
    $candidates += (Join-Path $tools "hvigor\bin\hvigorw.cmd")
  } catch {}
  foreach ($d in @(
      $env:DEVECO_SDK_HOME,
      (Join-Path ${env:ProgramFiles} "Huawei\DevEco Studio"),
      (Join-Path ${env:LOCALAPPDATA} "Huawei\DevEco Studio")
    )) {
    if (-not $d) { continue }
    $candidates += (Join-Path $d "tools\hvigor\bin\hvigorw.bat")
    $candidates += (Join-Path $d "hvigor\bin\hvigorw.bat")
  }
  foreach ($p in $candidates) {
    if ($p -and (Test-Path -LiteralPath $p)) { return $p }
  }
  try {
    $cmd = Get-Command hvigorw -ErrorAction Stop
    return $cmd.Source
  } catch {}
  return $null
}

$hv = Find-Hvigorw
if (-not $hv) {
  Write-Host "hvigorw not found. Add DevEco tools\hvigor\bin to PATH, or set HVIGORW to hvigorw.bat full path." -ForegroundColor Yellow
  exit 1
}

Write-Host "Using: $hv"
& cmd.exe /c "`"$hv`" test"
$code = $LASTEXITCODE
if ($code -ne 0) {
  Write-Host "hvigor test exit code: $code" -ForegroundColor Red
}
exit $code
