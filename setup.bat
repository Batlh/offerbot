@echo off
rem AngebotsBot - einmalige Einrichtung (Python 3.11 bis 3.13 noetig)
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo Python wurde nicht gefunden. Bitte von https://www.python.org/downloads/ installieren
  echo und beim Setup "Add python.exe to PATH" anhaken. Danach setup.bat erneut starten.
  pause & exit /b 1
)
echo Erstelle virtuelle Umgebung ...
%PY% -m venv .venv || (echo Fehler beim Erstellen der Umgebung & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo Fehler bei der Installation & pause & exit /b 1)
echo.
echo Fertig! Starten mit start.bat
echo Optional: autostart_einrichten.bat (startet AngebotsBot mit Windows im Infobereich)
pause
