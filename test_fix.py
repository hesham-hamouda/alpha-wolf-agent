import json
import httpx

MSG = "\u0627\u0647\u0644\u0627 \u0628\u0643 \u0645\u0627\u0631\u0627\u064a\u0643 \u0641\u064a \u062a\u0635\u0645\u064a\u0645 \u0647\u0630\u0647 \nfile:///D:/A/Applications%20under%20development/TESTS/3d-clock.html"

payload = {
    "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original broken
    "messages": [{"role": "user", "content": MSG}],
    "max_tokens": 4000,
    "auto_tools": True,
    "stream": True,
}

events, order = [], []
with httpx.Client(timeout=300) as c:
    with c.stream("POST", "http://127.0.0.1:8001/v1/chat/stream", json=payload) as r:
        r.raise_for_status()
        ev_buf, data_buf = [], []
        for raw in r.iter_lines():
            if raw is None:
                continue
            line = raw.rstrip("\n")
            if line.startswith("event:"):
                ev_buf.append(line[6:].strip())
            elif line.startswith("data:"):
                data_buf.append(line[5:].strip())
            elif line == "" or line.startswith(":"):
                if data_buf:
                    ds = "\n".join(data_buf)
                    name = ev_buf[0] if ev_buf else "message"
                    if ds == "[DONE]" and not ev_buf:
                        pass
                    elif ds == "[DONE]":
                        events.append({"type": "done", "done": True})
                        order.append("done")
                    else:
                        try:
                            pj = json.loads(ds)
                            pj["type"] = name
                            events.append(pj)
                            order.append(name)
                        except json.JSONDecodeError:
                            pass
                    ev_buf, data_buf = [], []

kinds = {}
for e in events:
    kinds[e.get("type", "?")] = kinds.get(e.get("type", "?"), 0) + 1
text = "".join(e.get("chunk", "") for e in events if e.get("type") == "token")
n_done = kinds.get("done", 0)

print(f"Events: {kinds}")
print(f"Order tail: {order[-6:]}")
print(f"Visible chars: {len(text)}")
if text.strip():
    print(f"First 200: {text[:200].replace(chr(10), ' ')}")
else:
    print("NO VISIBLE TOKENS")
print(f"Verdict: {'OK' if n_done == 1 and text.strip() else 'FAIL'}")