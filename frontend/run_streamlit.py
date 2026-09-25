#!/usr/bin/env python3
r"""Run Streamlit Alpha Wolf UI server."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

if __name__ == "__main__":
    import subprocess
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(PROJECT_ROOT / "frontend" / "streamlit_preview.py"),
        "--server.port", "8501",
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    print("Starting Streamlit:", " ".join(cmd))
    subprocess.run(cmd)