@echo off
REM ====================================================================
REM   ALPHA WOLF AGENT - STOP (Phase 35)
REM ====================================================================
REM   Calls the admin shutdown endpoint, which stops backend AND frontend.
REM   Safe to run any time — if backend is offline, kills the ports too.
REM ====================================================================

setlocal
chcp 65001 >nul 2>&1

set "PROJECT_DIR=%~dp0"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=8501"
set "SHUTDOWN_URL=http://127.0.0.1:%BACKEND_PORT%/v1/admin/stop-all"
set "TIMEOUT_SEC=10"

cd /d "%PROJECT_DIR%"

echo ================================================================
echo   ALPHA WOLF AGENT - stopping...
echo ================================================================

REM ---- 1. Try the admin endpoint (graceful: backend + frontend) ----
echo [1/2] Requesting graceful shutdown via admin endpoint...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%SHUTDOWN_URL%' -Method POST -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -eq 200) { Write-Host '  Backend acknowledged shutdown.'; exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
    echo [WARN] Admin endpoint not reachable, falling back to port-kill.
)

REM ---- 2. Fallback: kill any process still holding our ports ----
echo [2/2] Killing any process holding ports %BACKEND_PORT%/%FRONTEND_PORT%...
powershell -NoProfile -Command "foreach ($p in @(%BACKEND_PORT%, %FRONTEND_PORT%)) { $conns = netstat -ano | Select-String -Pattern (':'+$p+'\s.*LISTENING'); foreach ($line in $conns) { $id = ($line -split '\s+')[-1]; if ($id -match '^\d+$') { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } }"

REM Give OS a moment to release the ports
timeout /t 2 /nobreak >nul

echo.
echo ================================================================
echo   ALPHA WOLF AGENT IS STOPPED.
echo   You can now re-run Alpha_Wolf_Launcher.bat.
echo ================================================================
exit /b 0