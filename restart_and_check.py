import subprocess
import sys
import time
import httpx

# Kill existing
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], capture_output=True)

# Start backend
print('Starting backend...')
backend = subprocess.Popen([sys.executable, 'backend/run_server.py'], 
                           creationflags=subprocess.CREATE_NO_WINDOW)

time.sleep(3)

# Start frontend
print('Starting frontend...')
frontend = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'frontend/streamlit_preview.py', 
                            '--server.port', '8501', '--server.address', '127.0.0.1',
                            '--server.headless', 'true', '--browser.gatherUsageStats', 'false'],
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print('Waiting for startup...')
time.sleep(10)

# Check processes
import psutil
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info['cmdline'] or [])
        if 'streamlit' in cmdline:
            print(f'Streamlit: PID={proc.info["pid"]}')
        elif 'run_server' in cmdline:
            print(f'Backend: PID={proc.info["pid"]}')
    except:
        pass

time.sleep(5)

try:
    r = httpx.get('http://127.0.0.1:8501/_stcore/health', timeout=5)
    print(f'Streamlit health: {r.status_code}')
except Exception as e:
    print(f'Streamlit health check failed: {e}')

try:
    r = httpx.get('http://127.0.0.1:8501', timeout=10)
    print(f'Frontend HTTP: {r.status_code}')
    print(f'Length: {len(r.text)}')
    if 'streamlit' in r.text.lower():
        print('Streamlit JS found in HTML')
except Exception as e:
    print(f'HTTP Error: {e}')