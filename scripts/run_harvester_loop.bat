@echo off
chcp 65001 > nul
REM Бесконечный цикл harvester'а: работа 100-140 мин, сон 20-40 мин (рандом).
REM Двойной клик или Task Scheduler "при входе в систему".
REM
REM Переменные окружения (опционально):
REM   HARVESTER_BUDGET        — бюджет за одну итерацию (дефолт 2000)
REM   HARVESTER_SOURCES       — источники (дефолт: все)
REM   HARVESTER_YEAR_MIN      — фильтр по году
REM   HARVESTER_EMAIL         — email для OpenAlex/EuropePMC
REM   HARVEST_WORK_MIN_LOW/HIGH   — границы работы (дефолт 100..140)
REM   HARVEST_SLEEP_MIN_LOW/HIGH  — границы сна (дефолт 20..40)
REM
REM S3 upload (опционально, задать все 4 для Sber Cloud OBS):
REM   S3_ENDPOINT_URL=https://obs.ru-moscow-1.hc.sbercloud.ru
REM   S3_BUCKET=your-bucket
REM   S3_ACCESS_KEY=...
REM   S3_SECRET_KEY=...

setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

REM ----- Поиск Python -----
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
  echo [ERROR] Python not found. Set PYTHON_EXE env variable.
  pause
  exit /b 1
)

REM ----- Параметры по умолчанию -----
if "%HARVESTER_BUDGET%"=="" set "HARVESTER_BUDGET=2000"
if "%HARVESTER_SOURCES%"=="" set "HARVESTER_SOURCES=arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange,semanticscholar"
if "%HARVESTER_YEAR_MIN%"=="" set "HARVESTER_YEAR_MIN=2020"
if "%HARVESTER_EMAIL%"=="" set "HARVESTER_EMAIL=you@example.com"

echo === Harvester LOOP ===
echo  python:      %PY%
echo  budget/iter: %HARVESTER_BUDGET%
echo  sources:     %HARVESTER_SOURCES%
echo  year_min:    %HARVESTER_YEAR_MIN%
echo  email:       %HARVESTER_EMAIL%
if defined S3_BUCKET (
  echo  S3:          %S3_ENDPOINT_URL% / bucket=%S3_BUCKET%
) else (
  echo  S3:          off
)
echo.

%PY% -m harvester.loop

endlocal
