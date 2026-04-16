@echo off
cd /d "%~dp0"

:: 优先使用 C:\Users\zz\a23-doc-system\venv（实际安装包的位置）
if exist "C:\Users\zz\a23-doc-system\venv\Scripts\python.exe" (
    echo [OK] Using venv: C:\Users\zz\a23-doc-system\venv
    "C:\Users\zz\a23-doc-system\venv\Scripts\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
) else if exist "%~dp0venv\Scripts\python.exe" (
    echo [OK] Using venv: %~dp0venv
    "%~dp0venv\Scripts\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
) else (
    echo [WARN] No venv found, using Python from PATH...
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
)
