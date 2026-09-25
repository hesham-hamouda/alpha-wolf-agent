#!/usr/bin/env python3
r"""Run FastAPI Alpha Wolf backend server."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

if __name__ == "__main__":
    import uvicorn
    from backend.main import app
    print("Starting FastAPI on http://127.0.0.1:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")