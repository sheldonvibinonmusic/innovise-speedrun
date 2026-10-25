@echo off
setlocal enabledelayedexpansion
title Trustworthy Financial Research System - Server
cd /d "%~dp0"

echo ==============================================================================
echo Trustworthy Multi-Agent Financial Research & Decision Support System
echo ==============================================================================
echo.

REM 1. Ensure .env exists from template
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    )
)

REM 2. Determine Python interpreter
set PYTHON_CMD=python
where python >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Python314\python.exe" (
        set PYTHON_CMD="C:\Program Files\Python314\python.exe"
    ) else (
        echo [ERROR] Python was not found in PATH or at C:\Program Files\Python314\python.exe.
        echo Please ensure Python is installed and added to PATH.
        pause
        exit /b 1
    )
)

REM 3. Determine available port (default 8000, fallback to 8001 if 8000 is occupied)
set SERVER_PORT=8000
if not "%~1"=="" (
    set SERVER_PORT=%~1
) else (
    netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
    if not errorlevel 1 (
        echo [WARN] Port 8000 is currently occupied by another process.
        echo [INFO] Automatically selecting fallback port 8001.
        set SERVER_PORT=8001
    )
)

echo [INFO] Python command: %PYTHON_CMD%
echo [INFO] Starting FastAPI server on http://127.0.0.1:%SERVER_PORT% ...
echo [INFO] Interactive Research UI: http://127.0.0.1:%SERVER_PORT%/ui/
echo [INFO] Swagger API Docs:        http://127.0.0.1:%SERVER_PORT%/docs
echo [INFO] Health Check:            http://127.0.0.1:%SERVER_PORT%/api/health
echo.

REM 4. Launch browser automatically to the Interactive Research UI
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:%SERVER_PORT%/ui/"

REM 5. Run Uvicorn ASGI server
%PYTHON_CMD% -m uvicorn app.main:app --host 127.0.0.1 --port %SERVER_PORT% --reload

if errorlevel 1 (
    echo.
    echo [ERROR] Server terminated with an error.
    pause
)
