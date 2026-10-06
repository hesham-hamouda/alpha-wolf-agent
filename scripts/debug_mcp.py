"""Quick test to debug MCP server's send_test_message."""
import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Patch the server with verbose logging
    server_params = StdioServerParameters(
        command="python",
        args=["-u", r"E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\mcp_agent_tester\server.py"],
        env={"ALPHA_WOLF_BACKEND_URL": "http://127.0.0.1:8001", "PYTHONUNBUFFERED": "1"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Test with simple message
            print("=== Test 1: Simple chat ===", flush=True)
            r = await session.call_tool("send_test_message", {
                "message": "ما اسمك؟",
                "max_tokens": 200
            })
            data = json.loads(r.content[0].text)
            print(f"  success: {data.get('success')}", flush=True)
            print(f"  final_answer: {data.get('final_answer', '')[:100]}", flush=True)
            print(f"  events: {data.get('events')}", flush=True)
            print(f"  tool_calls: {len(data.get('tool_calls', []))}", flush=True)
            print(f"  tool_results: {len(data.get('tool_results', []))}", flush=True)
            print(f"  raw_answer: {data.get('raw_answer', '')[:200]}", flush=True)

asyncio.run(main())
