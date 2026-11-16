@echo off
rem Legt eine Verknuepfung im Autostart-Ordner an: AngebotsBot startet minimiert im Infobereich
cd /d "%~dp0"
set TARGET=%~dp0.venv\Scripts\pythonw.exe
set LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AngebotsBot.lnk
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); $s.TargetPath=$env:TARGET; $s.Arguments='main.py --minimiert'; $s.WorkingDirectory='%~dp0'; $s.Save()"
if exist "%LNK%" (echo Autostart eingerichtet. Entfernen: Datei AngebotsBot.lnk im Autostart-Ordner loeschen.) else (echo Autostart konnte nicht angelegt werden.)
pause
