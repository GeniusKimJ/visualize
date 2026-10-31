@echo off
chcp 65001 > nul
REM 매일 14:20에 run_weekly.bat 실행 (오픈 15:00 기준 40분 전)
REM 오늘 열리는 목표 날짜가 없으면 스크립트가 바로 종료됩니다.
schtasks /Create /TN "AUC_Reserve" /TR "\"%~dp0run_weekly.bat\"" /SC DAILY /ST 14:20 /RL LIMITED /F
echo.
echo 등록 확인: schtasks /Query /TN "AUC_Reserve"
echo 삭제:      schtasks /Delete /TN "AUC_Reserve" /F
pause
