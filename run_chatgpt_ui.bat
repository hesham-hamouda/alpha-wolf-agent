@echo off
cd /d "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
python -m streamlit run frontend\streamlit_preview.py --server.port 8501 --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false
