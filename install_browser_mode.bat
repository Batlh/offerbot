@echo off
rem Browser-Modus (Playwright + Chromium) fuer JavaScript-Seiten wie marktguru
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Bitte zuerst setup.bat ausfuehren & pause & exit /b 1)
python -m pip install playwright && python -m playwright install chromium
echo.
echo Fertig. In AngebotsBot unter Einstellungen "Browser-Modus erlauben" anhaken.
pause
