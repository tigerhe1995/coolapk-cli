# 刷机前总检查：一次跑完，确认所有准备工作就位
#
# 用法：powershell -ExecutionPolicy Bypass -File 00-检查清单.ps1
#
# 全部 OK 才可以在周末动手刷机。

$ErrorActionPreference = 'Continue'
$Root = 'F:\04.DSH\work\k90-root'
$Files = Join-Path $Root 'files'
$Tools = Join-Path $Root 'tools\platform-tools'
$Backup = Join-Path $Files '04-备份'

$pass = 0
$fail = 0
$warn = 0

function Check([string]$name, [bool]$ok, [string]$detail = '', [switch]$Soft) {
    if ($ok) {
        Write-Host ("  [ OK ] {0,-42} {1}" -f $name, $detail) -ForegroundColor Green
        $script:pass++
    } elseif ($Soft) {
        Write-Host ("  [WARN] {0,-42} {1}" -f $name, $detail) -ForegroundColor Yellow
        $script:warn++
    } else {
        Write-Host ("  [FAIL] {0,-42} {1}" -f $name, $detail) -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "`n================ K90 刷机前检查 ================" -ForegroundColor Cyan

# ---------- 1. 驱动 ----------
Write-Host "`n[1] USB 驱动" -ForegroundColor Yellow
$androidDrv = Get-WindowsDriver -Online -ErrorAction SilentlyContinue |
              Where-Object { $_.ClassName -eq 'AndroidUsbDeviceClass' }
Check "AndroidUsbDeviceClass 驱动" ($androidDrv.Count -ge 1) "$($androidDrv.Count) 个"
$qcDrv = Get-WindowsDriver -Online -ErrorAction SilentlyContinue |
         Where-Object { $_.ProviderName -match 'Qualcomm' -and $_.ClassName -eq 'USBDevice' }
Check "Qualcomm USBDevice 驱动" ($qcDrv.Count -ge 1) "$($qcDrv.Count) 个"

# ---------- 2. 工具链 ----------
Write-Host "`n[2] 工具链" -ForegroundColor Yellow
$adb = Join-Path $Tools 'adb.exe'
$fastboot = Join-Path $Tools 'fastboot.exe'
Check "adb.exe" (Test-Path $adb)
Check "fastboot.exe" (Test-Path $fastboot)
if (Test-Path $fastboot) {
    $v = (& $fastboot --version 2>&1) -join ' '
    Check "fastboot 可执行" ($v -match 'fastboot version') ($v -split '\s+')[0..1] -join ' '
}
$pathOk = ([Environment]::GetEnvironmentVariable('Path','User')) -like "*$Tools*"
Check "platform-tools 已加入 PATH" $pathOk -Soft

# ---------- 3. 解锁工具 ----------
Write-Host "`n[3] 解锁工具" -ForegroundColor Yellow
$toolRoot = Join-Path $Files '01-工具\已解压\Xiaomi-QC解锁BL工具v2.5Plus'
Check "QC工具箱已解压" (Test-Path $toolRoot)
$main = Join-Path $toolRoot '双击我打开Xiaomi-QC解锁BL工具v2.5Plus.exe'
Check "主程序 exe" (Test-Path $main) ("{0:N0} bytes" -f (Get-Item $main -ErrorAction SilentlyContinue).Length)
$driver = Join-Path $toolRoot 'Tools\driver\QcomMtk_Driver_Setup_4.0.1.6.exe'
Check "工具箱自带驱动" (Test-Path $driver)
$ksud = Join-Path $toolRoot 'Tools\bin\ksud'
Check "工具箱自带 ksud" (Test-Path $ksud)

# ---------- 4. K90 专用解锁文件 ----------
Write-Host "`n[4] K90 专用解锁文件" -ForegroundColor Yellow
$img = Join-Path $toolRoot 'Tools\img\8e_unlock_Bootloader'
Check "K90_abl.elf" (Test-Path (Join-Path $img 'Factory_abl\K90_abl.elf'))
Check "K90 官方 gpt_both4.bin" (Test-Path (Join-Path $img 'official-gpt_both\RedmiK90\gpt_both4.bin'))
Check "6.6.118 payload" (Test-Path (Join-Path $img 'SELinux\preload_k90_k90u_6.6.118.so'))
Check "64560 payload" (Test-Path (Join-Path $img 'SELinux_CVE-2026-64560\cve-2026-64560_k90_k90u.so'))
Check "98260 提权库" (Test-Path (Join-Path $img 'SELinux_CVE-2026-98260\libadbroot.so'))

# ---------- 5. KernelSU ----------
Write-Host "`n[5] KernelSU" -ForegroundColor Yellow
$ksuDir = Join-Path $Root 'tools\kernelsu'
$apk = Join-Path $ksuDir 'KernelSU_v3.3.1_manager.apk'
Check "KernelSU 管理器 APK" (Test-Path $apk) ("{0:N0} bytes" -f (Get-Item $apk -ErrorAction SilentlyContinue).Length)
$lkm = Join-Path $ksuDir 'lkm-aarch64-android15-6.6_kernelsu.ko'
Check "LKM 模块 (android15-6.6)" (Test-Path $lkm) ("{0:N0} bytes" -f (Get-Item $lkm -ErrorAction SilentlyContinue).Length)
if (Test-Path $apk) {
    $listing = & 'C:\Program Files\7-Zip\7z.exe' l $apk 2>&1 | Out-String
    Check "APK 内含 libksud.so (arm64)" ($listing -match 'lib\\arm64-v8a\\libksud\.so')
}

# ---------- 6. 线刷包 ----------
Write-Host "`n[6] 官方线刷包" -ForegroundColor Yellow
$rom = Join-Path $Files '03-官方线刷包\已解压\annibale_images_OS4.0.6.0.XPKCNXM_17.0'
Check "线刷包目录" (Test-Path $rom)
Check "flash_all.bat" (Test-Path (Join-Path $rom 'flash_all.bat'))
Check "flash_all_lock.bat（存在但勿用）" (Test-Path (Join-Path $rom 'flash_all_lock.bat'))
$super = Join-Path $rom 'images\super.img'
Check "super.img" (Test-Path $super) ("{0:N0} bytes" -f (Get-Item $super -ErrorAction SilentlyContinue).Length)
Check "boot.img" (Test-Path (Join-Path $rom 'images\boot.img'))
Check "init_boot.img" (Test-Path (Join-Path $rom 'images\init_boot.img'))
Check "gpt_both4.bin" (Test-Path (Join-Path $rom 'images\gpt_both4.bin'))

# ---------- 7. 工程小包 ----------
Write-Host "`n[7] K90 工程小包（9008 备选）" -ForegroundColor Yellow
$pkg = Join-Path $Files '02-K90工程小包\已解压\Redmi_K90工程小包-已测试-用于解锁BL'
Check "工程小包已解压" (Test-Path $pkg)
Check "工程小包 abl.elf" (Test-Path (Join-Path $pkg 'images\abl.elf'))
Check "工程小包 rawprogram0.xml" (Test-Path (Join-Path $pkg 'images\rawprogram0.xml'))
$pkgRar = Join-Path $Files '02-K90工程小包\Redmi_K90工程小包-已测试-用于解锁BL.rar'
Check "工程小包原始 rar" (Test-Path $pkgRar)

# ---------- 8. 脚本 ----------
Write-Host "`n[8] 辅助脚本" -ForegroundColor Yellow
foreach ($s in @('00-checklist.ps1','01-snapshot.ps1','02-backup-ufs.ps1','04-finalize.ps1','toolbox.cmd')) {
    Check $s (Test-Path (Join-Path $Root "scripts\$s"))
}

# ---------- 9. 备份状态 ----------
Write-Host "`n[9] 备份状态" -ForegroundColor Yellow
$snaps = Get-ChildItem $Backup -Directory -Filter '快照-*' -ErrorAction SilentlyContinue
Check "已有刷机前快照" ($snaps.Count -ge 1) "$($snaps.Count) 份" -Soft
$memBaks = Get-ChildItem $Backup -Directory -Filter '字库-*' -ErrorAction SilentlyContinue
Check "已有字库备份" ($memBaks.Count -ge 1) "$($memBaks.Count) 份" -Soft

# ---------- 10. 设备连接 ----------
Write-Host "`n[10] 设备连接（当前状态）" -ForegroundColor Yellow
if (Test-Path $adb) {
    $devices = & $adb devices 2>&1
    Write-Host "    $($devices -join ' ')" -ForegroundColor DarkGray
    $online = ($devices | Out-String) -match '\tdevice$'
    Check "手机已连接并授权" $online "周末刷机前插上线即可" -Soft
} else {
    Check "adb 可用" $false
}

# ---------- 汇总 ----------
Write-Host "`n================ 检查结果 ================" -ForegroundColor Cyan
Write-Host "  通过 $pass   警告 $warn   失败 $fail" -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
if ($fail -eq 0 -and $warn -eq 0) {
    Write-Host "`n>>> 全部就绪，周末可以开工了 <<<" -ForegroundColor Green
} elseif ($fail -eq 0) {
    Write-Host "`n>>> 关键项都过了，警告项按需处理 <<<" -ForegroundColor Yellow
} else {
    Write-Host "`n>>> 有失败项，先补齐再刷机 <<<" -ForegroundColor Red
}
Write-Host ""
