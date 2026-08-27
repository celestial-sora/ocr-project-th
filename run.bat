@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ไม่พบ virtual environment: .venv
    echo กรุณารัน: py -m venv .venv
    exit /b 1
)

echo Starting Flask web UI at http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
