@echo off
chcp 65001>nul
title Jarvis - installa aggiornamento automatico
REM Registra un task che lancia agent.py ogni giorno alle 09:00 (aggiorna tutti i dati).
REM Gira nel tuo utente, niente admin. Per cambiare orario modifica /ST qui sotto.

set PY=C:\ProgramData\miniconda3\python.exe
set DIR=%~dp0
set DIR=%DIR:~0,-1%

echo Creo il task "JarvisDaily" (agent.py ogni giorno alle 09:00)...
schtasks /Create /TN "JarvisDaily" /TR "\"%PY%\" \"%DIR%\agent.py\"" /SC DAILY /ST 09:00 /F
if %ERRORLEVEL%==0 (
  echo.
  echo OK. Jarvis si aggiornera da solo ogni giorno.
  echo Per rimuoverlo:  schtasks /Delete /TN "JarvisDaily" /F
) else (
  echo.
  echo Errore nella creazione del task. Vedi il messaggio sopra.
)
echo.
pause
