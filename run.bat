@echo off
REM Jarvis GitHub Agent - lancio giornaliero (Task Scheduler punta qui)
cd /d "%~dp0"
python agent.py --open
