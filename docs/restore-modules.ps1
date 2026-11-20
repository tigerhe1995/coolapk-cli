# 恢复 KernelSU 模块（线刷 + 装好 KernelSU 之后运行）
#
# 用法：powershell -ExecutionPolicy Bypass -File restore-modules.ps1
#
# 恢复顺序很重要：
#   1. hybrid_mount  (metamodule，提供 /system 挂载，必须最先)
#   2. zygisksu      (Zygisk 框架)
#   3. zygisk_lsposed(LSPosed)
#   4. scene_systemless / GGAT_10007 / YH_YC / YuJiaZai  (功能模块)

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$BackupRoot = 'F:\04.DSH\work\k90-root\files\04-备份'
$adb = Join-Path $Tools 'adb.exe'

$devices = & $adb devices
if (@($devices | Where-Object { $_ -match '\sdevice$' }).Count -eq 0) {
    Write-Host "没有检测到已授权的设备。" -ForegroundColor Red
    exit 1
}

# 找最新的备份目录
$src = Get-ChildItem $BackupRoot -Directory -Filter 'modules-*' -ErrorAction SilentlyContinue |
       Sort-Object Name -Descending | Select-Object -First 1
if (-not $src) {
    Write-Host "找不到模块备份目录（modules-*）" -ForegroundColor Red
    exit 1
}
Write-Host "=== 备份源: $($src.FullName) ===" -ForegroundColor Cyan

# 确认 KSU 可用
Write-Host "`n[0] 检查 KernelSU ..." -ForegroundColor Yellow
$ksu = & $adb shell "su -c 'ls /data/adb/ksu/bin/ksud 2>/dev/null || ls /data/adb/ksud 2>/dev/null'" 2>&1
if (-not $ksu) {
    Write-Host "  KernelSU 未就绪，无法恢复模块。请先刷 init_boot。" -ForegroundColor Red
    exit 1
}
Write-Host "  KSU 就绪" -ForegroundColor Green

# 恢复顺序
$order = @('hybrid_mount', 'zygisksu', 'zygisk_lsposed',
           'scene_systemless', 'GGAT_10007', 'YH_YC', 'YuJiaZai')

Write-Host "`n[1] 推送备份包 ..." -ForegroundColor Yellow
foreach ($m in $order) {
    $file = Join-Path $src.FullName "mod_$m.tgz"
    if (Test-Path $file) {
        & $adb push $file "/data/local/tmp/mod_$m.tgz" 2>&1 | Out-Null
        & $adb shell "su -c 'chmod 644 /data/local/tmp/mod_$m.tgz'" 2>&1 | Out-Null
    }
}

Write-Host "`n[2] 按顺序解压到 /data/adb/modules ..." -ForegroundColor Yellow
foreach ($m in $order) {
    $remote = "/data/local/tmp/mod_$m.tgz"
    $check = & $adb shell "test -f $remote && echo Y || echo N" 2>&1
    if ($check -match 'Y') {
        & $adb shell "su -c 'rm -rf /data/adb/modules/$m; tar -xzf $remote -C /data/adb/modules 2>/dev/null && echo OK'" 2>&1 |
            ForEach-Object { Write-Host "    $m : $_" -ForegroundColor Green }
    } else {
        Write-Host "    $m : 备份不存在，跳过" -ForegroundColor Yellow
    }
}

Write-Host "`n[3] 恢复 KSU 配置（授权列表/特性）..." -ForegroundColor Yellow
$cfg = Join-Path $src.FullName 'ksu_cfg.tgz'
if (Test-Path $cfg) {
    & $adb push $cfg '/data/local/tmp/ksu_cfg.tgz' 2>&1 | Out-Null
    & $adb shell "su -c 'chmod 644 /data/local/tmp/ksu_cfg.tgz'" 2>&1 | Out-Null
    # 只恢复配置目录，不覆盖模块本身
    & $adb shell "su -c 'tar -xzf /data/local/tmp/ksu_cfg.tgz -C /data/adb ksu 2>/dev/null && echo OK'" 2>&1 |
        ForEach-Object { Write-Host "    ksu cfg: $_" -ForegroundColor Green }
}

Write-Host "`n[4] 清理临时文件 ..." -ForegroundColor Yellow
& $adb shell "rm -f /data/local/tmp/mod_*.tgz /data/local/tmp/ksu_cfg.tgz"

Write-Host "`n[5] 当前模块列表 ..." -ForegroundColor Yellow
& $adb shell "su -c 'ls /data/adb/modules/'" 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

Write-Host "`n[6] 重启生效（推荐）..." -ForegroundColor Yellow
Write-Host "  执行：adb reboot" -ForegroundColor DarkGray
Write-Host "  重启后检查：ls /data/adb/modules/ 各模块是否正常加载" -ForegroundColor DarkGray
