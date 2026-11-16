@echo off
rem Startet mit sichtbarem Fenster fuer Fehlermeldungen
cd /d "%~dp0"
.venv\Scripts\python.exe main.py %*
pause
