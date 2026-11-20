# 刷机后收尾：关系统更新、装隐藏模块、检查状态
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File 04-刷机后收尾.ps1
#
# 前提：已刷入 KernelSU 且手机已 root

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$adb = Join-Path $Tools 'adb.exe'
$Ksud = 'F:\04.DSH\work\k90-root\tools\kernelsu\lkm-aarch64-android15-6.6_kernelsu.ko'

$devices = & $adb devices
if (@($devices | Where-Object { $_ -match '\sdevice$' }).Count -eq 0) {
    Write-Host "没有检测到已授权的设备。" -ForegroundColor Red
    exit 1
}

function Invoke-Root([string]$cmd) {
    & $adb shell "su -c '$cmd'" 2>&1
}

Write-Host "=== 刷机后收尾 ===" -ForegroundColor Cyan

# --- 1. 状态确认 ---
Write-Host "`n[1] 检查 root 状态..." -ForegroundColor Yellow
$rootId = Invoke-Root "id"
Write-Host "    $rootId" -ForegroundColor DarkGray

$ksuVer = Invoke-Root "ksud -V 2>/dev/null"
Write-Host "    KernelSU: $ksuVer" -ForegroundColor DarkGray

$unlocked = Invoke-Root "getprop ro.boot.flash.locked"
Write-Host "    ro.boot.flash.locked = $unlocked" -ForegroundColor DarkGray
if ($unlocked -match '1') {
    Write-Host "    ⚠ BL 仍是锁定状态，解锁没成功" -ForegroundColor Red
} elseif ($unlocked -match '0') {
    Write-Host "    ✓ BL 已解锁" -ForegroundColor Green
}

# --- 2. 关闭系统更新 ---
Write-Host "`n[2] 关闭系统更新（防止 OTA 回锁/失败）..." -ForegroundColor Yellow
$updatePkgs = @(
    'com.xiaomi.updater',
    'com.miui.systemUpdater',
    'com.miui.huanji',
    'com.xiaomi.midrop'
)
foreach ($pkg in $updatePkgs) {
    $installed = & $adb shell pm list packages $pkg 2>&1
    if ($installed -match $pkg) {
        Invoke-Root "pm disable-user --user 0 $pkg" | Out-Null
        Write-Host "    已禁用 $pkg" -ForegroundColor Green
    }
}

# 关闭更新检查的组件
Invoke-Root "pm disable-user --user 0 com.miui.systemUpdater/com.miui.ota" | Out-Null
Write-Host "    已禁用 OTA 检查组件" -ForegroundColor Green

# --- 3. 安装 ZygiskNext（隐藏 root 环境）---
Write-Host "`n[3] ZygiskNext 状态..." -ForegroundColor Yellow
$zygisk = & $adb shell pm list packages 2>&1 | Select-String 'zygisk'
if ($zygisk) {
    Write-Host "    已安装: $zygisk" -ForegroundColor Green
} else {
    Write-Host "    未安装。需要的话从 https://github.com/Dr-TSNG/ZygiskNext/releases 下载" -ForegroundColor Yellow
    Write-Host "    （或用 LSPosed 的 Shamiko 模块代替）" -ForegroundColor DarkGray
}

# --- 4. 备份刷机后的基带信息，与刷机前对比 ---
Write-Host "`n[4] 对比基带信息..." -ForegroundColor Yellow

function Get-Imei {
    # 多路提取，任一成功即可（不同 ROM 路径不一样）
    $candidates = @(
        "service call iphonesubinfo 1 i32 1 s16 com.android.shell 2>/dev/null | grep -o '[0-9]\{15\}' | head -1",
        "dumpsys iphonesubinfo 2>/dev/null | grep -o 'DeviceId *= *[0-9]\{15\}' | grep -o '[0-9]\{15\}' | head -1",
        "dumpsys iphonesubinfo 2>/dev/null | grep -o '[0-9]\{15\}' | head -1",
        "getprop | grep -i 'imei' | grep -o '[0-9]\{15\}' | head -1"
    )
    foreach ($c in $candidates) {
        $v = Invoke-Root $c
        if ($v -match '[0-9]{15}') { return ($v | Select-String -Pattern '[0-9]{15}' -AllMatches).Matches[0].Value }
    }
    return ""
}

function Get-Arb {
    # 防回滚版本（ARB），刷机版本不能比这个低
    $candidates = @(
        "getprop ro.boot.arb",
        "getprop ro.build.version.incremental",
        "cat /proc/sys/kernel/anti-rollback 2>/dev/null",
        "getprop | grep -i 'anti.rollback\\|anti_rollback' | head -1"
    )
    foreach ($c in $candidates) {
        $v = Invoke-Root $c
        if ($v -and $v.Trim()) { return $v.Trim() }
    }
    return ""
}

$nowImei = Get-Imei
$nowArb  = Get-Arb
Write-Host "    当前 IMEI : $nowImei" -ForegroundColor DarkGray
Write-Host "    当前 ARB  : $nowArb" -ForegroundColor DarkGray

if (-not $nowImei) {
    Write-Host "    ! 自动取 IMEI 失败，请手动拨号 *#06# 与截图对比" -ForegroundColor Yellow
}

$before = Get-ChildItem 'F:\04.DSH\work\k90-root\files\04-备份' -Directory -Filter '快照-*' -ErrorAction SilentlyContinue |
          Sort-Object Name -Descending | Select-Object -First 1
if ($before) {
    $oldImeiFile = Join-Path $before.FullName 'IMEI.txt'
    if (Test-Path $oldImeiFile) {
        $oldImei = (Get-Content $oldImeiFile -Raw).Trim()
        if ($oldImei -and $nowImei) {
            if ($oldImei -eq $nowImei) {
                Write-Host "    ✓ IMEI 与刷机前一致（基带正常）" -ForegroundColor Green
            } else {
                Write-Host "    ✗ IMEI 变化！" -ForegroundColor Red
                Write-Host "      刷机前: $oldImei" -ForegroundColor Yellow
                Write-Host "      现在  : $nowImei" -ForegroundColor Yellow
                Write-Host "      需要用字库备份恢复！" -ForegroundColor Red
            }
        }
    }
    # ARB 对比
    $oldArbFile = Join-Path $before.FullName 'ARB.txt'
    if (Test-Path $oldArbFile) {
        $oldArb = (Get-Content $oldArbFile -Raw).Trim()
        if ($oldArb -and $nowArb) {
            if ($oldArb -eq $nowArb) {
                Write-Host "    ✓ ARB/版本 与刷机前一致" -ForegroundColor Green
            } else {
                Write-Host "    ! ARB/版本 变化" -ForegroundColor Yellow
                Write-Host "      刷机前: $oldArb" -ForegroundColor DarkGray
                Write-Host "      现在  : $nowArb" -ForegroundColor DarkGray
            }
        }
    }
}

# --- 5. 当前系统信息 ---
Write-Host "`n[5] 当前系统信息:" -ForegroundColor Yellow
& $adb shell "getprop ro.product.model; getprop ro.build.version.incremental; getprop ro.build.display.id; getprop ro.build.version.release; getprop ro.build.version.sdk; uname -r" 2>&1 |
    ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

# --- 6. 常用检查项 ---
Write-Host "`n[6] 环境检查:" -ForegroundColor Yellow
$checks = @(
    @{n='SELinux 状态'; c="getenforce"},
    @{n='Play 完整性'; c="pm list packages | grep -c com.google.android.gms"},
    @{n='已装模块'; c="ls /data/adb/modules 2>/dev/null"},
    @{n='KSu 工作目录'; c="ls /data/adb/ksu 2>/dev/null | head -5"}
)
foreach ($check in $checks) {
    $result = Invoke-Root $check.c
    Write-Host "    $($check.n): $result" -ForegroundColor DarkGray
}

Write-Host "`n=== 收尾检查完成 ===" -ForegroundColor Cyan
Write-Host "如果需要装模块，把 zip 放到手机后执行：" -ForegroundColor Yellow
Write-Host "  adb push 模块.zip /data/local/tmp/" -ForegroundColor DarkGray
Write-Host "  adb shell su -c 'ksud module install /data/local/tmp/模块.zip'" -ForegroundColor DarkGray
