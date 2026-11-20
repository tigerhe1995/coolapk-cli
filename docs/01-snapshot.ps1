# 刷机前快照：把设备的基线信息抓下来存档
#
# 用法：连接手机（USB 调试已授权）后运行
#   powershell -ExecutionPolicy Bypass -File 01-刷机前快照.ps1
#
# 输出目录：F:\04.DSH\work\k90-root\files\04-备份\快照-YYYYMMDD-HHmmss\

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$BackupRoot = 'F:\04.DSH\work\k90-root\files\04-备份'
$adb = Join-Path $Tools 'adb.exe'
$fastboot = Join-Path $Tools 'fastboot.exe'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $BackupRoot "快照-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "=== 快照输出: $out ===" -ForegroundColor Cyan

# --- 1. 确认设备在线 ---
$devices = & $adb devices
Write-Host "`n[1] adb devices:" -ForegroundColor Yellow
$devices
$deviceOnline = @($devices | Where-Object { $_ -match '\sdevice$' }).Count -gt 0
if (-not $deviceOnline) {
    Write-Host "`n没有检测到已授权的设备。" -ForegroundColor Red
    Write-Host "请检查：1) 数据线 2) USB调试已开 3) 屏幕上点了'始终允许'" -ForegroundColor Red
    exit 1
}

# --- 2. 基础信息 ---
Write-Host "`n[2] 抓取系统信息..." -ForegroundColor Yellow
& $adb shell getprop                                          | Out-File "$out\getprop.txt" -Encoding UTF8
& $adb shell uname -a                                         | Out-File "$out\uname-a.txt" -Encoding UTF8
& $adb shell cat /proc/partitions                              | Out-File "$out\partitions.txt" -Encoding UTF8
& $adb shell cat /proc/version                                | Out-File "$out\proc-version.txt" -Encoding UTF8
& $adb shell "getprop ro.product.device; getprop ro.product.model; getprop ro.build.version.incremental; getprop ro.build.display.id" | Out-File "$out\device-info.txt" -Encoding UTF8

# --- 3. 基带与 IMEI ---
Write-Host "[3] 抓取基带信息（IMEI/MIUI码）..." -ForegroundColor Yellow
& $adb shell dumpsys iphonesubinfo 2>&1                       | Out-File "$out\dumpsys-iphonesubinfo.txt" -Encoding UTF8
& $adb shell dumpsys telephony.registry 2>&1                   | Out-File "$out\dumpsys-telephony.txt" -Encoding UTF8
& $adb shell "cat /sys/class/net/rmnet_data0/uevent 2>/dev/null; cat /proc/net/xt_qtaguid/stats 2>/dev/null | head -5" | Out-File "$out\rmnet.txt" -Encoding UTF8

# IMEI 多路提取（不同 ROM 路径不一样）
$imei = ""
foreach ($c in @(
    "service call iphonesubinfo 1 i32 1 s16 com.android.shell 2>/dev/null | grep -o '[0-9]\{15\}' | head -1",
    "dumpsys iphonesubinfo 2>/dev/null | grep -o 'DeviceId *= *[0-9]\{15\}' | grep -o '[0-9]\{15\}' | head -1",
    "dumpsys iphonesubinfo 2>/dev/null | grep -o '[0-9]\{15\}' | head -1",
    "getprop | grep -i 'imei' | grep -o '[0-9]\{15\}' | head -1"
)) {
    $v = & $adb shell $c 2>&1
    if ($v -match '[0-9]{15}') {
        $imei = ($v | Select-String -Pattern '[0-9]{15}' -AllMatches).Matches[0].Value
        break
    }
}
if ($imei) {
    $imei | Out-File "$out\IMEI.txt" -Encoding UTF8
    Write-Host "    IMEI = $imei" -ForegroundColor Green
} else {
    Write-Host "    (自动取 IMEI 失败，请手动拨号 *#06# 截图存到 $out)" -ForegroundColor Yellow
}

# ARB 防回滚版本 + 基带版本（刷机后要比对）
$arb = (& $adb shell "getprop ro.boot.arb" 2>&1 | Out-String).Trim()
if (-not $arb) { $arb = (& $adb shell "getprop ro.build.version.incremental" 2>&1 | Out-String).Trim() }
$arb | Out-File "$out\ARB.txt" -Encoding UTF8
Write-Host "    ARB/版本 = $arb" -ForegroundColor Green

& $adb shell "getprop gsm.version.baseband; getprop ro.boot.hardware; getprop ro.serialno" 2>&1 |
    Out-File "$out\baseband.txt" -Encoding UTF8

# --- 4. 关键分区表（后续比对用）---
Write-Host "[4] 抓取分区表..." -ForegroundColor Yellow
& $adb shell "ls -l /dev/block/by-name/ 2>/dev/null | grep -E 'ufs|modem|persist|fsc|bl|xbl|devinfo|tz' " | Out-File "$out\by-name.txt" -Encoding UTF8

# --- 5. 已装模块/管理器 ---
Write-Host "[5] 抓取 root 状态..." -ForegroundColor Yellow
& $adb shell "su -c 'which ksud; ls /data/adb/ksu 2>/dev/null; ls /data/adb/modules 2>/dev/null'" 2>&1 | Out-File "$out\root-state.txt" -Encoding UTF8
& $adb shell pm list packages | Select-String -Pattern 'kernelsu|magisk|sukisu|bakasu|apatch' | Out-File "$out\root-managers.txt" -Encoding UTF8

# --- 6. fastboot 侧信息（若设备在 fastboot 模式）---
$fb = & $fastboot devices
if ($fb) {
    Write-Host "[6] 设备处于 fastboot 模式，抓取变量..." -ForegroundColor Yellow
    & $fastboot getvar all 2>&1 | Out-File "$out\fastboot-getvar.txt" -Encoding UTF8
} else {
    Write-Host "[6] 设备不在 fastboot 模式（正常，跳过）" -ForegroundColor Yellow
}

# --- 汇总 ---
Write-Host "`n=== 快照完成 ===" -ForegroundColor Cyan
Get-ChildItem $out | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "目录: $out" -ForegroundColor Cyan
Write-Host "`n提醒：IMEI 和 MIUI 码务必手动截图存档（拨号盘 *#06# 和 *#*#6488#*#*）" -ForegroundColor Yellow
