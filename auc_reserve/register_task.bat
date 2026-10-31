@echo off
chcp 65001 > nul
REM 매주 일요일 09:20에 run_weekly.bat 실행 (오픈 10:00 기준 40분 전)
REM 오픈 시각이 다르면 /ST 값을 바꾸세요.
schtasks /Create /TN "AUC_Reserve" /TR "\"%~dp0run_weekly.bat\"" /SC WEEKLY /D SUN /ST 09:20 /RL LIMITED /F
echo.
echo 등록 확인: schtasks /Query /TN "AUC_Reserve"
echo 삭제:      schtasks /Delete /TN "AUC_Reserve" /F
pause
