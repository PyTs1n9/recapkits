# 把项目内的 uv 与 .venv 放到当前 PowerShell 会话 PATH 的最前面。
# 用法: . .\scripts\env.ps1
$root = Split-Path -Parent $PSScriptRoot
$uvDir = Join-Path $root ".tools\uv"
$venvDir = Join-Path $root ".venv\Scripts"

if (-not (Test-Path (Join-Path $uvDir "uv.exe"))) {
    Write-Error "缺少 $uvDir\uv.exe，先运行 scripts\bootstrap.ps1"
    return
}

$env:PATH = "$uvDir;$venvDir;$env:PATH"
Write-Host "uv  -> $(Join-Path $uvDir 'uv.exe')"
Write-Host "venv -> $venvDir"
& (Join-Path $uvDir "uv.exe") --version
