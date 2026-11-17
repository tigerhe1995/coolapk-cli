@echo off
rem Coolapk CLI launcher (Windows)
rem
rem Auto-detects Python, then runs "python -m coolapk <args>".
rem Override the interpreter by setting COOLAPK_PY before running this script.
setlocal

set "PY=%COOLAPK_PY%"
if not defined PY (
    for %%P in (python.exe python3.exe) do (
        if not defined PY (
            for /f "delims=" %%I in ('where %%P 2^>nul') do (
                if not defined PY set "PY=%%I"
            )
        )
    )
)

if not defined PY (
    echo Python not found in PATH. Set COOLAPK_PY to your python.exe path.
    exit /b 1
)

set "ROOT=%~dp0.."
cd /d "%ROOT%"
"%PY%" -m coolapk %*
exit /b %ERRORLEVEL%
