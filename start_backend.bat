@echo off
cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    echo Starting backend with project venv...
    "%~dp0venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000
) else (
    echo No venv folder found, using Python from PATH...
    python -m uvicorn main:app --reload --port 8000
)
