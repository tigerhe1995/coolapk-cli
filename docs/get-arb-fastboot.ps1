# 进 fastboot 读取 ARB（防回滚版本）与 BL 状态
#
# 用法：手机已连接后运行
#   powershell -ExecutionPolicy Bypass -File get-arb-fastboot.ps1
#
# 流程：adb reboot bootloader -> fastboot getvar -> 询问是否重启回系统

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$adb = Join-Path $Tools 'adb.exe'
$fastboot = Join-Path $Tools 'fastboot.exe'
$Out = 'F:\04.DSH\work\k90-root\files\04-备份'

$devices = & $adb devices
if (@($devices | Where-Object { $_ -match '\sdevice$' }).Count -eq 0) {
    Write-Host "没有检测到已授权的设备（adb）。" -ForegroundColor Red
    Write-Host "如果你已经在 fastboot 模式，请直接跳过本脚本。" -ForegroundColor Yellow
    exit 1
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $Out "fastboot-vars-$stamp.txt"

Write-Host "=== 重启进 fastboot ===" -ForegroundColor Cyan
& $adb reboot bootloader
Start-Sleep -Seconds 12

Write-Host "`n=== fastboot devices ===" -ForegroundColor Yellow
$fb = & $fastboot devices 2>&1
$fb
if (-not $fb) {
    Write-Host "没进入 fastboot。手动操作：长按开机键黑屏 -> 音量下+开机键" -ForegroundColor Yellow
    Write-Host "然后再运行本脚本（会跳过 reboot 直接读）。" -ForegroundColor DarkGray
    exit 1
}

Write-Host "`n=== 读取 fastboot 变量 ===" -ForegroundColor Yellow
$all = & $fastboot getvar all 2>&1
$all | Out-File $log -Encoding UTF8

$vars = @(
    'unlocked', 'anti', 'current-slot', 'slot-count',
    'product', 'version-bootloader', 'secure', 'is-userspace'
)
foreach ($v in $vars) {
    $r = & $fastboot getvar $v 2>&1
    $line = ($r | Where-Object { $_ -match ("{0}\s*:" -f [regex]::Escape($v)) } | Select-Object -First 1)
    if (-not $line) { $line = ($r | Select-Object -Last 1) }
    Write-Host ("    {0,-26} {1}" -f $v, $line.Trim()) -ForegroundColor DarkGray
}

Write-Host "`n=== 关键结论 ===" -ForegroundColor Cyan
$unlockedLine = ($all | Where-Object { $_ -match 'unlocked' } | Select-Object -First 1)
$antiLine = ($all | Where-Object { $_ -match '^\s*anti' } | Select-Object -First 1)

if ($unlockedLine -match 'unlocked:\s*yes') {
    Write-Host "    [OK] BL 已解锁" -ForegroundColor Green
} elseif ($unlockedLine -match 'unlocked:\s*no') {
    Write-Host "    [--] BL 未解锁" -ForegroundColor Red
}
if ($antiLine) {
    Write-Host "    ARB 值: $($antiLine.Trim())" -ForegroundColor Yellow
    Write-Host "    （刷机时 fastboot getvar anti 必须 >= 此值）" -ForegroundColor DarkGray
}

Write-Host "`n完整变量已存: $log" -ForegroundColor Cyan

Write-Host "`n=== 重启回系统 ===" -ForegroundColor Yellow
$ans = Read-Host "回车重启回系统 / 输入 n 保持在 fastboot"
if ($ans -ne 'n') {
    & $fastboot reboot
}
