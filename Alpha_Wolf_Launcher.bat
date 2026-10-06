@echo off
REM ====================================================================
REM   ALPHA WOLF AGENT - ONE-CLICK LAUNCHER (Phase 11+ v4.0)
REM ====================================================================
REM   Double-click (or the Desktop icon) and get:
REM     1. Backend  (FastAPI  http://127.0.0.1:8001) ? health-gated
REM     2. Frontend (Streamlit http://127.0.0.1:8501) ? health-gated
REM     3. Browser opens automatically on the chat UI
REM
REM   Fixes vs old launcher:
REM     - Kills ONLY processes holding OUR ports (never every python.exe)
REM     - Every wait has a TIMEOUT with a clear error (no infinite hangs)
REM     - Backend starts via backend\run_server.py (proven entry point)
REM     - Output goes to backend_start.log / frontend_start.log
REM ====================================================================

setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "PROJECT_DIR=%~dp0"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=8501"
set "PYTHON_EXE=python"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%/v1/body/health"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%/"
set "TIMEOUT_SEC=90"

cd /d "%PROJECT_DIR%"
if not exist "backend\main.py" (
    echo [ERROR] backend\main.py not found in: %PROJECT_DIR%
    echo Run this file from the Alpha Wolf Agent directory.
    pause
    exit /b 1
)
if not exist "frontend\streamlit_preview.py" (
    echo [ERROR] frontend\streamlit_preview.py not found in: %PROJECT_DIR%
    pause
    exit /b 1
)
where %PYTHON_EXE% >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.12+.
    pause
    exit /b 1
)

echo ================================================================
echo   ALPHA WOLF AGENT - starting...
echo ================================================================

REM ---- 0. Free our ports only (precise, never kills foreign pythons) ----
echo [0/3] Freeing ports %BACKEND_PORT% and %FRONTEND_PORT% (ours only)...
powershell -NoProfile -Command "foreach ($p in @(8001, 8501)) { netstat -ano | Select-String -Pattern $(':'+$p+'\s.*LISTENING') | ForEach-Object { $id = ($_ -split '\s+')[-1]; if ($id -match '^\d+$') { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } }" 2>nul
timeout /t 3 /nobreak >nul

REM ---- 1. Backend (Phase 35 ? WindowStyle Hidden, no cmd window stays open) ----
echo [1/3] Starting Backend (FastAPI) on port %BACKEND_PORT%...
powershell -NoProfile -Command "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('backend\run_server.py') -WorkingDirectory '%PROJECT_DIR%' -WindowStyle Hidden -RedirectStandardOutput 'backend_start.log' -RedirectStandardError 'backend_err.log'"
call :WAIT_FOR "%BACKEND_URL%" "Backend"
if errorlevel 1 goto :BACKEND_FAIL

REM ---- 2. Frontend (Phase 35 ? WindowStyle Hidden, no cmd window stays open) ----
echo [2/3] Starting Frontend (Streamlit) on port %FRONTEND_PORT%...
powershell -NoProfile -Command "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('-m','streamlit','run','frontend\streamlit_preview.py','--server.port','%FRONTEND_PORT%','--server.address','127.0.0.1','--server.headless','true','--browser.gatherUsageStats','false') -WorkingDirectory '%PROJECT_DIR%' -WindowStyle Hidden -RedirectStandardOutput 'frontend_start.log' -RedirectStandardError 'frontend_err.log'"
call :WAIT_FOR "%FRONTEND_URL%" "Frontend"
if errorlevel 1 goto :FRONTEND_FAIL

REM ---- 3. Browser ----
echo [3/3] Opening chat UI...
start "" "http://127.0.0.1:%FRONTEND_PORT%/"
echo.
echo ================================================================
echo   ALPHA WOLF AGENT IS READY
echo   Chat UI:  http://127.0.0.1:%FRONTEND_PORT%/
echo   Backend:  http://127.0.0.1:%BACKEND_PORT%/
echo ================================================================
echo Logs: backend_start.log / frontend_start.log
echo Use the "Stop Everything" button in the sidebar to shut down.
echo Or run Alpha_Wolf_Stop.bat to kill via admin endpoint.
exit /b 0

:BACKEND_FAIL
echo [ERROR] Backend did not become healthy within %TIMEOUT_SEC%s.
echo See backend_start.log for details.
pause
exit /b 1

:FRONTEND_FAIL
echo [ERROR] Frontend did not become ready within %TIMEOUT_SEC%s.
echo See frontend_start.log for details.
pause
exit /b 1

REM ---- :WAIT_FOR url label : polls with timeout, returns 0/1 ----
:WAIT_FOR
set "URL=%~1"
set "LABEL=%~2"
set /a TRIES=%TIMEOUT_SEC%/2
:WAIT_LOOP
if %TRIES% LEQ 0 (
    echo [%LABEL%] timed out waiting for %URL%
    exit /b 1
)
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    set /a TRIES-=1
    goto :WAIT_LOOP
)
echo [%LABEL%] ready.
exit /b 0
