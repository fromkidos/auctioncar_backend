@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ================================================================================
REM Daily Auction Crawling Script - includes report extraction
REM ================================================================================

REM 0) 고정 경로 및 공통 환경
set "PROJECT_DIR=C:\projects\courtauction_car"
set "LOG_DIR=%PROJECT_DIR%\logs"
set "PYTHONUTF8=1"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\daily_tasks_%date:~0,4%-%date:~5,2%-%date:~8,2%.log"

pushd "%PROJECT_DIR%"

(
  echo ================================================================================
  echo Starting daily tasks at %date% %time%
  echo PROJECT_DIR=%PROJECT_DIR%
  echo LOG_DIR=%LOG_DIR%
  echo USER:
  whoami >>"%LOG_FILE%" 2>&1
  echo CD: %CD%
  echo ================================================================================
)>>"%LOG_FILE%"

REM 1) Python 탐색 (venv 우선 → py.exe → PATH의 python.exe)
set "VENV_PY=%PROJECT_DIR%\venv\Scripts\python.exe"
set "PY_EXE="

if exist "%VENV_PY%" (
  set "PY_EXE=%VENV_PY%"
  echo Using venv python: "%PY_EXE%" >>"%LOG_FILE%"
) else (
  where py.exe >nul 2>&1
  if not errorlevel 1 (
    set "PY_EXE=py.exe"
    echo Using py launcher >>"%LOG_FILE%"
  ) else (
    for /f "usebackq delims=" %%P in (`where python.exe 2^>nul`) do (
      set "PY_EXE=%%P"
      goto :FOUND_PY
    )
  )
)

:FOUND_PY
if "%PY_EXE%"=="" (
  echo [ERROR] Python not found. >>"%LOG_FILE%"
  goto :END
)

"%PY_EXE%" -V >>"%LOG_FILE%" 2>&1

REM 2) 파이썬 모듈 실행
set RC=0
call :RUNPY "crawling.crawling_auction_ongoing.update_ongoing_auctions" "update_ongoing_auctions.py"
call :RUNPY "crawling.crawling_auction_result.court_auction_car_crawler" "court_auction_car_crawler.py"
call :RUNPY "crawling.process_reports_to_db" "process_reports_to_db.py"
call :RUNPY "crawling.cleanup_old_auctions" "cleanup_old_auctions.py"

goto :END

REM ------------------------------------------------------------------------------
REM 함수: RUNPY <python_module> <label_for_log>
REM ------------------------------------------------------------------------------
:RUNPY
set "MODULE=%~1"
set "LABEL=%~2"
echo. >>"%LOG_FILE%"
echo [INFO] Running %LABEL% ... >>"%LOG_FILE%"
"%PY_EXE%" -m %MODULE% >>"%LOG_FILE%" 2>&1
set "STEP_RC=%ERRORLEVEL%"
echo [INFO] Finished %LABEL%. ExitCode=!STEP_RC! >>"%LOG_FILE%"
if not "!STEP_RC!"=="0" set RC=!STEP_RC!
exit /b 0

REM ------------------------------------------------------------------------------
:END
echo. >>"%LOG_FILE%"
echo ================================================================================
echo All tasks completed at %date% %time% (RC=%RC%) >>"%LOG_FILE%"
echo ================================================================================ >>"%LOG_FILE%"

popd
endlocal
