@echo off
chcp 65001 > nul
REM Локальный запуск harvester'а на Windows.
REM Двойной клик или из cmd: run_harvester.bat
REM
REM По умолчанию: бюджет 200, все источники, год >= 2020.
REM Можно переопределить переменными окружения, например:
REM   set HARVESTER_BUDGET=500 && run_harvester.bat
REM   set HARVESTER_SOURCES=arxiv,europepmc && run_harvester.bat
REM   set PYTHON_EXE=C:\Users\Redmi\AppData\Local\Programs\Python\Python312\python.exe && run_harvester.bat

setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM ----- Поиск Python -----
REM Приоритет: PYTHON_EXE (env) → py -3 → python → known paths
set "PY="
if defined PYTHON_EXE (
  if exist "!PYTHON_EXE!" set "PY=!PYTHON_EXE!"
)
if not defined PY (
  py -3 -V >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -V >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    "%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe"
    "%LOCALAPPDATA%\Python\pythoncore-3.12-64\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
  ) do (
    if not defined PY if exist %%P set "PY=%%~P"
  )
)
if not defined PY (
  echo [ERROR] Python not found.
  echo Set PYTHON_EXE manually, e.g.:
  echo   set "PYTHON_EXE=C:\Users\Redmi\AppData\Local\Programs\Python\Python312\python.exe"
  echo   run_harvester.bat
  pause
  exit /b 1
)

REM ----- Параметры -----
if "%HARVESTER_BUDGET%"=="" set "HARVESTER_BUDGET=200"
if "%HARVESTER_SOURCES%"=="" set "HARVESTER_SOURCES=arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange"
if "%HARVESTER_YEAR_MIN%"=="" set "HARVESTER_YEAR_MIN=2020"
if "%HARVESTER_EMAIL%"=="" set "HARVESTER_EMAIL=you@example.com"

echo === Harvester ===
echo  python:  %PY%
echo  budget:  %HARVESTER_BUDGET%
echo  sources: %HARVESTER_SOURCES%
echo  year_min: %HARVESTER_YEAR_MIN%
echo  email:   %HARVESTER_EMAIL%
echo.

%PY% -m harvester.harvest_full --budget %HARVESTER_BUDGET% --sources %HARVESTER_SOURCES% --year-min %HARVESTER_YEAR_MIN% --email %HARVESTER_EMAIL% --time-limit-min 60

if errorlevel 1 (
  echo.
  echo [ERROR] Harvester failed. See output above.
  pause
  exit /b 1
)

echo.
echo Done. Chunks in qdrant_db/, PDFs in all_pdfs/.
pause
endlocal
