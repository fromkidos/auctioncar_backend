@echo OFF
setlocal

:: ============================================================================
:: Daily Auction Crawling Script
:: 매일 실행할 경매 크롤링 스크립트
:: ============================================================================

:: 1. 프로젝트 루트 디렉터리 설정
::    이 파일은 backend 폴더에 있으므로, 상위 폴더(..)를 기준으로 합니다.
set "PROJECT_DIR=%~dp0.."
cd /d "%PROJECT_DIR%"

:: 2. 로그 파일 경로 설정
::    로그 파일은 이제 backend 폴더 내에 생성됩니다.
set "LOG_FILE=%~dp0daily_tasks.log"

:: 3. (선택 사항) 파이썬 가상 환경(venv)의 activate.bat 파일 경로
::    가상 환경을 사용하지 않는 경우, 이 경로는 무시됩니다.
set "VENV_ACTIVATE=%PROJECT_DIR%\venv\Scripts\activate.bat"

echo ================================================================================ >> %LOG_FILE%
echo Starting daily tasks at %date% %time% >> %LOG_FILE%
echo ================================================================================ >> %LOG_FILE%

:: 가상 환경이 존재하면 활성화
if exist "%VENV_ACTIVATE%" (
    echo Activating Python virtual environment... >> %LOG_FILE%
    call "%VENV_ACTIVATE%"
) else (
    echo Virtual environment not found at "%VENV_ACTIVATE%". Using system Python. >> %LOG_FILE%
)

:: 4. 스크립트를 순서대로 실행하고 결과를 로그 파일에 기록
echo. >> %LOG_FILE%
echo [INFO] Running update_ongoing_auctions.py... >> %LOG_FILE%
python -m backend.crawling.crawling_auction_ongoing.update_ongoing_auctions >> %LOG_FILE% 2>&1
echo [INFO] Finished update_ongoing_auctions.py. >> %LOG_FILE%

echo. >> %LOG_FILE%
echo [INFO] Running court_auction_car_crawler.py... >> %LOG_FILE%
python -m backend.crawling.crawling_auction_result.court_auction_car_crawler >> %LOG_FILE% 2>&1
echo [INFO] Finished court_auction_car_crawler.py. >> %LOG_FILE%

echo. >> %LOG_FILE%
echo [INFO] Running cleanup_old_auctions.py... >> %LOG_FILE%
python -m backend.crawling.cleanup_old_auctions >> %LOG_FILE% 2>&1
echo [INFO] Finished cleanup_old_auctions.py. >> %LOG_FILE%

echo. >> %LOG_FILE%
echo ================================================================================ >> %LOG_FILE%
echo All tasks completed at %date% %time% >> %LOG_FILE%
echo ================================================================================ >> %LOG_FILE%

endlocal
