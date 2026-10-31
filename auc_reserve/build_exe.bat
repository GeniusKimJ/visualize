@echo off
chcp 65001 > nul
REM Windows PC에서 exe를 직접 빌드합니다. 결과: dist\AUC_Reserve\ 폴더
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :err
python -m unittest discover -s tests || goto :err
python -m PyInstaller --noconfirm --clean --onefile --console --name AUC_Reserve ^
    --collect-all playwright main.py || goto :err
if not exist dist\AUC_Reserve mkdir dist\AUC_Reserve
move /y dist\AUC_Reserve.exe dist\AUC_Reserve\ > nul
for %%f in (config.json .env.example README.md run_weekly.bat register_task.bat) do copy /y %%f dist\AUC_Reserve\ > nul
echo.
echo 완료: dist\AUC_Reserve\AUC_Reserve.exe
pause
exit /b 0
:err
echo 빌드 실패
pause
exit /b 1
