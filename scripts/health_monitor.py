#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Health Monitor (Auto-Restart)
==================================================

Per Quхائд directive 2026-09-25: "اتبعوا قواعدكم ياخبراء" — the user's
experience should be seamless. If any service stops, restart it.

Monitors:
- Backend (FastAPI on port 8001)
- Frontend (Streamlit on port 8501)
- MinimaMax fallback proxy (port 9999)

Action on failure:
- Log the crash
- Restart the failed service
- Verify recovery

Usage:
    python scripts/health_monitor.py            # one-shot check
    python scripts/health_monitor.py --watch  # continuous monitoring (every 30s)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_SCRIPT = PROJECT_ROOT / "backend" / "run_server.py"
LOG_DIR = PROJECT_ROOT / "logs"

LOG_DIR.mkdir(exist_ok=True)


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is accepting connections."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def start_backend() -> None:
    """Start the FastAPI backend in background."""
    log_file = open(PROJECT_ROOT / "backend_start.log", "a")
    subprocess.Popen(
        ["python", str(BACKEND_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    print(f"  [OK] Backend started (PID pending)")


def start_frontend() -> None:
    """Start the Streamlit frontend in background."""
    log_file = open(PROJECT_ROOT / "frontend_start.log", "a")
    subprocess.Popen(
        [
            "python", "-m", "streamlit", "run", "./streamlit_preview.py",
            "--server.port", "8501",
            "--server.headless", "true",
            "--server.fileWatcherType", "none",
        ],
        cwd=str(FRONTEND_DIR),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    print(f"  [OK] Frontend started (PID pending)")


def check_services() -> dict[str, bool]:
    """Check all services and return their status."""
    return {
        "backend": is_port_open(8001),
        "frontend": is_port_open(8501),
        "minimax_proxy": is_port_open(9999),
    }


def main() -> int:
    """One-shot health check + auto-restart if needed."""
    print("=" * 60)
    print("  🐺 Alpha Wolf Agent — Health Monitor")
    print("=" * 60)
    print()

    status = check_services()
    print("Service status:")
    for name, ok in status.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}: {'UP' if ok else 'DOWN'}")

    # Auto-restart if down
    restarted = False
    if not status["backend"]:
        print("\n[Auto-restart] Starting backend...")
        start_backend()
        restarted = True
        time.sleep(5)
    if not status["frontend"]:
        print("\n[Auto-restart] Starting frontend...")
        start_frontend()
        restarted = True
        time.sleep(8)

    if restarted:
        print("\nVerifying recovery...")
        time.sleep(3)
        new_status = check_services()
        for name, ok in new_status.items():
            icon = "✅" if ok else "❌"
            print(f"  {icon} {name}: {'UP' if ok else 'DOWN'}")
        return 0 if all(new_status.values()) else 1

    return 0 if all(status.values()) else 1


def watch_mode(interval: int = 30) -> None:
    """Continuously monitor services and auto-restart if they go down."""
    print(f"Watch mode: monitoring every {interval}s. Press Ctrl+C to stop.\n")
    try:
        while True:
            status = check_services()
            down = [k for k, v in status.items() if not v]
            if down:
                print(f"[{time.strftime('%H:%M:%S')}] DOWN: {', '.join(down)} — auto-restarting...")
                for service in down:
                    if service == "backend":
                        start_backend()
                    elif service == "frontend":
                        start_frontend()
                time.sleep(10)
                status = check_services()
                recovered = [k for k, v in status.items() if v]
                print(f"  [{time.strftime('%H:%M:%S')}] Recovered: {', '.join(recovered)}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] All services UP")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch_mode()
    else:
        sys.exit(main())
