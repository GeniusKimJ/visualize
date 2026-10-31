@echo off
chcp 65001 > nul
REM 작업 스케줄러용: 창을 띄우고 바로 오픈 대기 시작 (오늘 열리는 날짜가 없으면 10초 뒤 자동 종료)
cd /d "%~dp0"
if exist AUC_Reserve.exe (
    start "" AUC_Reserve.exe --auto
) else (
    start "" pythonw gui.py --auto
)
