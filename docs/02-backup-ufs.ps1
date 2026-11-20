# 字库备份：把 UFS/基带相关分区导出到电脑
#
# 字库存着 IMEI/基带信息，刷机一旦丢了只能靠 9008 写回。
# 解锁成功后**第一时间**跑这个脚本。
#
# 用法（手机需已 root）：
#   powershell -ExecutionPolicy Bypass -File 02-字库备份.ps1
#
# 输出目录：F:\04.DSH\work\k90-root\files\04-备份\字库-YYYYMMDD-HHmmss\

$ErrorActionPreference = 'Continue'
$Tools = 'F:\04.DSH\work\k90-root\tools\platform-tools'
$BackupRoot = 'F:\04.DSH\work\k90-root\files\04-备份'
$adb = Join-Path $Tools 'adb.exe'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $BackupRoot "字库-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "=== 字库备份输出: $out ===" -ForegroundColor Cyan

$devices = & $adb devices
if (@($devices | Where-Object { $_ -match '\sdevice$' }).Count -eq 0) {
    Write-Host "没有检测到已授权的设备，请检查 USB 调试。" -ForegroundColor Red
    exit 1
}

# --- 1. 确认 root 可用 ---
Write-Host "[1] 检测 root..." -ForegroundColor Yellow
$rootCheck = & $adb shell "su -c id 2>/dev/null | grep -q uid && echo OK || echo NO" 2>&1
if ($rootCheck -notmatch 'OK') {
    Write-Host "未检测到 root。字库备份需要 root 权限（su）。" -ForegroundColor Red
    Write-Host "如果刚解锁还没刷 KSU，先用临时 root 跑本脚本。" -ForegroundColor Yellow
    exit 1
}
Write-Host "    root OK" -ForegroundColor Green

# --- 2. 列出需要备份的分区 ---
# 关键：ufs_*（UFS 闪存，含 IMEI/NV/校准数据）、modemst/fsc/persist（基带）、
#       devinfo/tz/abl/xbl（引导链，出问题可救砖）
$partitions = @(
    'ufs_a', 'ufs_b', 'ufs_a_1', 'ufs_b_1', 'ufs_a_2', 'ufs_b_2',
    'modemst1', 'modemst2', 'fsc', 'persist', 'persist2',
    'devinfo', 'devcfg', 'tz', 'abl', 'xbl', 'xbl_config', 'aop', 'aop_config',
    'misc', 'frp', 'config', 'keystore', 'bootconfig'
)

Write-Host "`n[2] 探测分区存在性..." -ForegroundColor Yellow
$available = @()
foreach ($p in $partitions) {
    $exists = & $adb shell "test -e /dev/block/by-name/$p && echo Y || echo N" 2>&1
    if ($exists -match 'Y') {
        $available += $p
        Write-Host "    [有] $p" -ForegroundColor DarkGray
    }
}

if ($available.Count -eq 0) {
    Write-Host "没找到任何目标分区，检查 /dev/block/by-name 是否可读。" -ForegroundColor Red
    & $adb shell "ls /dev/block/by-name/ | head -40" 2>&1 | Write-Host
    exit 1
}

Write-Host "`n    共 $($available.Count) 个分区待备份" -ForegroundColor Cyan

# --- 3. 逐个 dd 出来 ---
$ok = 0
$fail = @()
foreach ($p in $available) {
    $target = Join-Path $out "$p.img"
    Write-Host "    导出 $p ..." -ForegroundColor DarkGray
    # dd 走 stdout，用 shell 重定向到手机临时目录再 pull，避免管道编码问题
    & $adb shell "su -c 'dd if=/dev/block/by-name/$p of=/data/local/tmp/$p.img bs=4M 2>/dev/null && chmod 644 /data/local/tmp/$p.img'"
    & $adb pull "/data/local/tmp/$p.img" "$target" 2>&1 | Out-Null
    & $adb shell "rm -f /data/local/tmp/$p.img"

    if ((Test-Path $target) -and (Get-Item $target).Length -gt 0) {
        $size = (Get-Item $target).Length
        $hash = (Get-FileHash $target -Algorithm MD5).Hash.ToLower()
        "$p  $size  md5=$hash" | Out-File "$out\$p.md5" -Encoding UTF8
        Write-Host "        OK $size bytes  md5=$hash" -ForegroundColor Green
        $ok++
    } else {
        Write-Host "        失败" -ForegroundColor Red
        $fail += $p
    }
}

# --- 4. 生成校验清单 ---
$manifest = @()
foreach ($p in $available) {
    $file = Join-Path $out "$p.img"
    if (Test-Path $file) {
        $manifest += [PSCustomObject]@{
            Partition = $p
            Size      = (Get-Item $file).Length
            MD5       = (Get-FileHash $file -Algorithm MD5).Hash.ToLower()
        }
    }
}
$manifest | Export-Csv "$out\manifest.csv" -NoTypeInformation -Encoding UTF8

Write-Host "`n=== 备份结果 ===" -ForegroundColor Cyan
Write-Host "成功 $ok / $($available.Count)" -ForegroundColor $(if ($ok -eq $available.Count) { 'Green' } else { 'Yellow' })
if ($fail.Count) { Write-Host "失败: $($fail -join ', ')" -ForegroundColor Yellow }
Write-Host "`n目录: $out" -ForegroundColor Cyan
Write-Host "校验清单: $out\manifest.csv" -ForegroundColor Cyan

if ($ok -eq $available.Count -and $ok -gt 0) {
    Write-Host "`n字库已完整备份。务必把这个目录也复制一份到移动硬盘/网盘。" -ForegroundColor Green
} else {
    Write-Host "`n部分分区备份失败，务必重试直到全部成功。" -ForegroundColor Yellow
}
