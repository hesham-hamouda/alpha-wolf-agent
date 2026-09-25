@echo off
REM Alpha Wolf Agent Launcher
REM Starts Backend (FastAPI) + Frontend (Streamlit)
REM Opens the chat UI automatically

cd /d "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"

echo.
echo ============================================================
echo   🐺 ALPHA WOLF AGENT LAUNCHER
echo ============================================================
echo.

REM Kill any existing instances
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Alpha Wolf*" 2>nul >nul
taskkill /F /FI "IMAGENAME eq python.exe AND WINDOWTITLE eq *alpha*" 2>nul >nul

REM Start Backend (FastAPI) in new window
echo [1/3] Starting Backend (FastAPI on port 8001)...
start "Alpha Wolf Backend" cmd /k "cd /d E:\Projects and systems managed by the team of experts\Alpha Wolf Agent && python backend\run_server.py"

REM Wait 3 seconds for backend to start
timeout /t 3 /nobreak >nul

REM Start Frontend (Streamlit) in new window
echo [2/3] Starting Frontend (Streamlit on port 8501)...
start "Alpha Wolf Frontend" cmd /k "cd /d E:\Projects and systems managed by the team of experts\Alpha Wolf Agent && python -m streamlit run frontend\streamlit_preview.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false"

REM Wait 5 seconds for Streamlit to be ready
timeout /t 5 /nobreak >nul

REM Open browser to the chat UI
echo [3/3] Opening chat UI in browser...
start "" "http://127.0.0.1:8501/"

echo.
echo ============================================================
echo   ✅ ALPHA WOLF AGENT RUNNING
echo ============================================================
echo.
echo   Backend:  http://127.0.0.1:8001/
echo   Frontend: http://127.0.0.1:8501/
echo   Chat:     http://127.0.0.1:8501/
echo.
echo   Press any key to close this window (servers stay running)...
pause >nul