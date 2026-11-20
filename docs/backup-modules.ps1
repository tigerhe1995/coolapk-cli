# 备份 KernelSU 模块（线刷清 data 前必做）
#
# 用法：powershell -ExecutionPolicy Bypass -File backup-modules.ps1
# 输出：F:\04.DSH\work\k90-root\files\04-备份\modules-<时间戳>\

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$BackupRoot = 'F:\04.DSH\work\k90-root\files\04-备份'
$adb = Join-Path $Tools 'adb.exe'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $BackupRoot "modules-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "=== 模块备份输出: $out ===" -ForegroundColor Cyan

$devices = & $adb devices
if (@($devices | Where-Object { $_ -match '\sdevice$' }).Count -eq 0) {
    Write-Host "没有检测到已授权的设备。" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1] 当前已装模块:" -ForegroundColor Yellow
$mods = & $adb shell "su -c 'ls /data/adb/modules/ 2>/dev/null'" 2>&1
$mods | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

Write-Host "`n[2] 打包 /data/adb/modules ..." -ForegroundColor Yellow
& $adb shell "su -c 'tar -czf /data/local/tmp/modules_backup.tgz -C /data/adb modules 2>/dev/null; chmod 644 /data/local/tmp/modules_backup.tgz; ls -l /data/local/tmp/modules_backup.tgz'" 2>&1

Write-Host "`n[3] 拉回电脑 ..." -ForegroundColor Yellow
& $adb pull /data/local/tmp/modules_backup.tgz "$out\modules_backup.tgz" 2>&1 | Out-Null
& $adb shell "rm -f /data/local/tmp/modules_backup.tgz"

if (Test-Path "$out\modules_backup.tgz") {
    $size = (Get-Item "$out\modules_backup.tgz").Length
    Write-Host "    完成: $size bytes" -ForegroundColor Green
} else {
    Write-Host "    失败" -ForegroundColor Red
    exit 1
}

Write-Host "`n[4] 逐个模块单独导出（防止整包损坏）..." -ForegroundColor Yellow
$modList = @('GGAT_10007', 'YH_YC', 'YuJiaZai', 'hybrid_mount',
             'scene_systemless', 'zygisk_lsposed', 'zygisksu')
foreach ($m in $modList) {
    $exists = & $adb shell "su -c 'test -d /data/adb/modules/$m && echo Y || echo N'" 2>&1
    if ($exists -match 'Y') {
        & $adb shell "su -c 'tar -czf /data/local/tmp/mod_$m.tgz -C /data/adb/modules $m 2>/dev/null; chmod 644 /data/local/tmp/mod_$m.tgz'" 2>&1 | Out-Null
        & $adb pull "/data/local/tmp/mod_$m.tgz" "$out\mod_$m.tgz" 2>&1 | Out-Null
        & $adb shell "rm -f /data/local/tmp/mod_$m.tgz"
        if (Test-Path "$out\mod_$m.tgz") {
            Write-Host "    [OK] $m" -ForegroundColor Green
        } else {
            Write-Host "    [FAIL] $m" -ForegroundColor Red
        }
    } else {
        Write-Host "    [--] $m 不存在" -ForegroundColor DarkGray
    }
}

Write-Host "`n[5] 备份其他配置..." -ForegroundColor Yellow
# KSU 配置（授权列表、特性）
& $adb shell "su -c 'tar -czf /data/local/tmp/ksu_cfg.tgz -C /data/adb ksu 2>/dev/null; chmod 644 /data/local/tmp/ksu_cfg.tgz'" 2>&1 | Out-Null
& $adb pull /data/local/tmp/ksu_cfg.tgz "$out\ksu_cfg.tgz" 2>&1 | Out-Null
& $adb shell "rm -f /data/local/tmp/ksu_cfg.tgz"

# 隐藏模块（ZygiskNext 配置）
if (& $adb shell "su -c 'test -d /data/adb/modules/zygisknext && echo Y || echo N'" 2>&1) {
    Write-Host "    发现 zygisknext 模块" -ForegroundColor DarkGray
}

Write-Host "`n=== 备份结果 ===" -ForegroundColor Cyan
Get-ChildItem $out | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "目录: $out" -ForegroundColor Cyan
Write-Host "`n恢复方法（线刷+装好 KernelSU 之后）:" -ForegroundColor Yellow
Write-Host "  1. 整包: adb push modules_backup.tgz /data/local/tmp/ && adb shell su -c 'tar -xzf /data/local/tmp/modules_backup.tgz -C /data/adb'" -ForegroundColor DarkGray
Write-Host "  2. 单个: adb push mod_scene_systemless.tgz /data/local/tmp/ && adb shell su -c 'tar -xzf /data/local/tmp/mod_scene_systemless.tgz -C /data/adb/modules'" -ForegroundColor DarkGray
