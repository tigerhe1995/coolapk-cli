@echo off
chcp 65001 >nul
title K90 Flash Toolbox
set "ROOT=F:\04.DSH\work\k90-root"
set "SCRIPTS=%ROOT%\scripts"
set "PT=%ROOT%\tools\platform-tools"
rem Locate toolbox dir by wildcard so no non-ASCII literal appears here.
set "TOOLBOX="
for /d %%D in ("%ROOT%\files\01-*") do (
  for /d %%E in ("%%D\*") do (
    if exist "%%E\Tools" set "TOOLBOX=%%E"
  )
)
set "ROM="
for /d %%D in ("%ROOT%\files\03-*") do (
  for /d %%E in ("%%D\*") do (
    for /d %%F in ("%%E\*") do (
      if exist "%%F\flash_all.bat" set "ROM=%%F"
    )
  )
)

echo.
echo   ================================================
echo     K90 Flash Toolbox
echo   ================================================
echo.
echo   [1] Pre-flash checklist
echo   [2] Snapshot device state
echo   [3] Backup UFS memory chip
echo   [4] Backup KernelSU modules
echo   [5] Launch QC unlock toolbox
echo   [6] Fastboot: show unlocked status
echo   [7] Get ARB (anti-rollback) value
echo   [8] Flash official ROM (flash_all.bat)
echo   [9] Flash init_boot with KernelSU
echo  [10] Restore KernelSU modules
echo  [11] Post-flash finalize
echo  [12] Open shell (adb/fastboot in PATH)
echo  [13] Open work folder
echo   [0] Exit
echo.

set /p CHOICE=Choose (0-13):
if "%CHOICE%"=="1" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\00-checklist.ps1" & goto :end )
if "%CHOICE%"=="2" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\01-snapshot.ps1" & goto :end )
if "%CHOICE%"=="3" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\02-backup-ufs.ps1" & goto :end )
if "%CHOICE%"=="4" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\backup-modules.ps1" & goto :end )
if "%CHOICE%"=="5" ( for %%F in ("%TOOLBOX%\*.exe") do start "" "%%F" & goto :end )
if "%CHOICE%"=="6" ( "%PT%\fastboot.exe" devices & "%PT%\fastboot.exe" getvar unlocked & goto :end )
if "%CHOICE%"=="7" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\get-arb-fastboot.ps1" & goto :end )
if "%CHOICE%"=="8" ( cd /d "%ROM%" && flash_all.bat & goto :end )
if "%CHOICE%"=="9" ( "%PT%\fastboot.exe" flash init_boot "%ROOT%\work-patch\init_boot_ksu.img" & goto :end )
if "%CHOICE%"=="10" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\restore-modules.ps1" & goto :end )
if "%CHOICE%"=="11" ( powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\04-finalize.ps1" & goto :end )
if "%CHOICE%"=="12" ( cmd /k "cd /d %PT%" & goto :end )
if "%CHOICE%"=="13" ( explorer "%ROOT%" & goto :end )
if "%CHOICE%"=="0" goto :end

:end
echo.
pause
