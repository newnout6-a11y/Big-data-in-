@echo off
REM Локальный запуск harvester'а на Windows.
REM Двойной клик или из cmd: run_harvester.bat
REM
REM По умолчанию: бюджет 200, все источники, год >= 2020.
REM Можно переопределить переменными окружения, например:
REM   set HARVESTER_BUDGET=500 && run_harvester.bat
REM   set HARVESTER_SOURCES=arxiv,europepmc && run_harvester.bat
REM
REM Или запланировать через Планировщик задач Windows — см. документация\TASK_SCHEDULER.md

setlocal

cd /d "%~dp0"

if "%HARVESTER_BUDGET%"=="" set HARVESTER_BUDGET=200
if "%HARVESTER_SOURCES%"=="" set HARVESTER_SOURCES=arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange
if "%HARVESTER_YEAR_MIN%"=="" set HARVESTER_YEAR_MIN=2020
if "%HARVESTER_EMAIL%"=="" set HARVESTER_EMAIL=you@example.com

echo === Harvester ===
echo  budget:  %HARVESTER_BUDGET%
echo  sources: %HARVESTER_SOURCES%
echo  year>=:  %HARVESTER_YEAR_MIN%
echo  email:   %HARVESTER_EMAIL%
echo.

python -m harvester.harvest_full ^
  --budget %HARVESTER_BUDGET% ^
  --sources %HARVESTER_SOURCES% ^
  --year-min %HARVESTER_YEAR_MIN% ^
  --email %HARVESTER_EMAIL% ^
  --time-limit-min 60

if errorlevel 1 (
  echo.
  echo Harvester упал. См. вывод выше.
  pause
  exit /b 1
)

echo.
echo Готово. Чанки в qdrant_db/, PDF в all_pdfs/.
endlocal
