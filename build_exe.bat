@echo off
rem Baut eine eigenstaendige AngebotsBot.exe (Ordner dist\AngebotsBot) - Python wird dann nicht mehr gebraucht
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Bitte zuerst setup.bat ausfuehren & pause & exit /b 1)
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name AngebotsBot --collect-all rapidocr_onnxruntime --collect-all playwright --collect-all pypdfium2 --collect-all pypdfium2_raw --add-data "README.md:." --add-data "angebotsbot/core/install_update.ps1:angebotsbot/core" main.py
python -m angebotsbot.lizenzen dist\AngebotsBot\_internal\THIRD_PARTY_LICENSES.txt
echo.
echo Fertig: dist\AngebotsBot\AngebotsBot.exe  (Daten liegen dann in dist\AngebotsBot\data)
pause
