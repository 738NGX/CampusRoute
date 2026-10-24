param(
    [string]$Python = 'python',
    [string]$Adb = '',
    [switch]$Repair
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskTemporary = Join-Path $taskRoot 'work\.cache\launch'
New-Item -ItemType Directory -Force -Path $taskTemporary | Out-Null
$env:TEMP = $taskTemporary
$env:TMP = $taskTemporary
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    & $Python -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14), "Python 3.11-3.13 required"'
    if ($LASTEXITCODE -ne 0) { throw '请选择 Python 3.11、3.12 或3.13，或使用 -Python 指定解释器路径。' }
    & $Python -m venv (Join-Path $taskRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
    $Repair = $true
}
$taskProbe = @'
import sys
try:
    import campusroute.console
    from importlib.metadata import version
    assert version('campusroute') == '1.1.0'
except Exception:
    sys.exit(1)
'@
& $taskPython -B -c $taskProbe
if ($LASTEXITCODE -ne 0) { $Repair = $true }
if ($Repair) {
    & $taskPython -B -m pip install --disable-pip-version-check --no-cache-dir -e .
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查上方错误后重试。' }
}
& $taskPython -B -m pip check
if ($LASTEXITCODE -ne 0) { throw '依赖校验未通过，请使用 -Repair 修复。' }
$taskArguments = @('-B', '-m', 'campusroute', '--root', $taskRoot, '--backend', 'android')
if ($Adb) { $taskArguments += @('--adb', $Adb) }
& $taskPython @taskArguments
exit $LASTEXITCODE
