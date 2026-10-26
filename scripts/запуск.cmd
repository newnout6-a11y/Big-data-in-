@echo off
chcp 65001 >nul
rem Launcher выбирает Python 3.12: .venv, py, затем uv.
setlocal
cd /d "%~dp0\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\запуск.py %*
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        python scripts\запуск.py %*
    ) else (
        call py scripts\запуск.py %*
    )
)
set "NAV_EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %NAV_EXIT_CODE%
