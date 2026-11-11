# 首次准备 / 换机后执行: 保证 uv 在项目内, 并同步依赖。
# 用法: powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
$root = Split-Path -Parent $PSScriptRoot
$uvDir = Join-Path $root ".tools\uv"
$uv = Join-Path $uvDir "uv.exe"

if (-not (Test-Path $uv)) {
    New-Item -ItemType Directory -Force -Path $uvDir | Out-Null
    $found = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $found) {
        Write-Error "未找到 uv。先安装一次 uv 后重跑本脚本，或手动把 uv.exe 放到 $uvDir。"
        exit 1
    }
    Copy-Item $found.Source $uv
    Write-Host "已把 uv 复制到 $uv"
}

& $uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $uv --version
Write-Host ""
Write-Host "完成。让 PATH 指向项目内 uv:"
Write-Host "  PowerShell:  . .\scripts\env.ps1"
Write-Host "  cmd:         call scripts\env.cmd"
Write-Host "  或者直接用仓库根入口: uv.cmd (cmd) / ./uv (bash)"
