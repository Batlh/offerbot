@echo off
rem Baut eine eigenstaendige AngebotsBot.exe (Ordner dist\AngebotsBot) - Python wird dann nicht mehr gebraucht
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Bitte zuerst setup.bat ausfuehren & pause & exit /b 1)
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name AngebotsBot --collect-all rapidocr_onnxruntime --collect-data pymupdf main.py
echo.
echo Fertig: dist\AngebotsBot\AngebotsBot.exe  (Daten liegen dann in dist\AngebotsBot\data)
pause
