@echo off
REM Run the new app.py
cd /d "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
echo Starting Streamlit with new app.py at http://127.0.0.1:8501/
streamlit run frontend/app.py --server.port 8501 --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false 2>&1
