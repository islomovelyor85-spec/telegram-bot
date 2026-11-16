@echo off
cd /d "%~dp0"
if not exist venv (
  echo Kutubxonalar o'rnatilmoqda...
  python -m venv venv
  venv\Scripts\pip install -q -r requirements.txt
)
venv\Scripts\python main.py
pause
