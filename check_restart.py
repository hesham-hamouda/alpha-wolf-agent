import httpx
import re

r = httpx.get('http://127.0.0.1:8501', timeout=10)
content = r.text

patterns = ['🔄', 'إعادة تشغيل', 'Restart UI', 'btn_restart_ui', 'col_restart', 'st.columns([4, 1])']
for p in patterns:
    count = content.count(p)
    print(f'{p}: {count} occurrences')

sidebar_start = content.find('data-testid="stSidebar"')
if sidebar_start >= 0:
    sidebar_content = content[sidebar_start:sidebar_start+10000]
    for p in ['🔄', 'إعادة', 'Restart', 'btn_restart']:
        if p in sidebar_content:
            print(f'Found "{p}" in sidebar area')
    print('Sidebar section found')
else:
    print('Sidebar section not found')