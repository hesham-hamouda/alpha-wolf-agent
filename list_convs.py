import httpx, json
r = httpx.get('http://127.0.0.1:8001/v1/conversations?limit=50', timeout=10)
data = r.json()
convs = data.get('conversations', [])
print(f'Total conversations: {len(convs)}')
for c in convs:
    cid = c.get('conversation_id', '')[:8]
    title = c.get('title', '')[:50]
    print(f'  {cid}... | {title}')