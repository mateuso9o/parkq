@echo off
rem Start the ParkQ web app on http://127.0.0.1:8000
cd /d "%~dp0"
start "" http://127.0.0.1:8000/
python -m uvicorn server:app --app-dir app --host 127.0.0.1 --port 8000
