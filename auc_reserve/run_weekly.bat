@echo off
chcp 65001 > nul
cd /d "%~dp0"
if exist AUC_Reserve.exe (
    AUC_Reserve.exe --open --yes
) else (
    python main.py --open --yes
)
