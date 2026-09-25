#!/usr/bin/env python3
r"""
Alpha Wolf Agent — MCP Server Framework | إطار خادم MCP
========================================================
Minimal MCP (Model Context Protocol) server framework.

Provides:
- MCPServer base class with stdio + HTTP transports
- Tool registration via @server.tool() decorator
- List_tools + Call_tool handlers (MCP-compatible JSON-RPC)
- stdio transport for local MCP clients
- HTTP/SSE transport for remote clients

This is a BASIC framework — not full MCP spec compliance.
For production-grade MCP, use the official `mcp` Python SDK.
This is sufficient for Alpha Wolf's needs.

Iron Laws Applied:
- #15 (Verify)        : Self-test included
- #22 (Autonomous)    : No prompts — execute immediately
- #33 (Lessons)       : Bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : Errors include diagnostic context
- #47 (Bilingual)     : Every public function has Arabic translation
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger("alpha_wolf.mcp")


# ============================================================================
# MCP Types (JSON-RPC 2.0 compatible)
# ============================================================================

JSONRPC_VERSION = "2.0"


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request.

    طلب JSON-RPC 2.0.
    """
    jsonrpc: str = JSONRPC_VERSION
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response.

    استجابة JSON-RPC 2.0.
    """
    jsonrpc: str = JSONRPC_VERSION
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


# ============================================================================
# MCP Server
# ============================================================================

@dataclass
class ToolDefinition:
    """MCP tool definition (loose JSON schema).

    تعريف أداة MCP.
    """
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


class MCPServer:
    """Minimal MCP server with stdio + HTTP transports.

    خادم MCP بسيط مع بروتوكولي stdio و HTTP.

    Usage:
        server = MCPServer(name="alpha-wolf")
        @server.tool(name="greet", description="Say hello")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        # stdio:
        await server.run_stdio()

        # HTTP:
        uvicorn.run(server.app, host="127.0.0.1", port=8765)
    """

    def __init__(self, name: str = "alpha-wolf-mcp", version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, ToolDefinition] = {}
        self._tool_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self.resources: Dict[str, Any] = {}
        self._initialized = False
        self._app = None  # FastAPI app (lazy)

    def tool(self, name: Optional[str] = None, description: str = ""):
        """Decorator to register a tool.

        مُسجِّل للأداة.

        Example:
            @server.tool(name="sum", description="Add two numbers")
            async def sum(a: int, b: int) -> int:
                return a + b
        """
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            tool_name = name or func.__name__
            self.tools[tool_name] = ToolDefinition(
                name=tool_name,
                description=description or (func.__doc__ or ""),
                input_schema={"type": "object", "properties": {}},
            )
            self._tool_handlers[tool_name] = func
            logger.info(f"Registered tool: {tool_name}")
            return func
        return decorator

    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle a JSON-RPC request.

        معالجة طلب JSON-RPC.
        """
        if request.method == "initialize":
            return JSONRPCResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": self.name, "version": self.version},
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            )
        elif request.method == "tools/list":
            return JSONRPCResponse(
                id=request.id,
                result={"tools": [
                    {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                    for t in self.tools.values()
                ]},
            )
        elif request.method == "tools/call":
            return await self._handle_tool_call(request)
        elif request.method == "notifications/initialized":
            self._initialized = True
            return JSONRPCResponse(id=request.id, result={})
        else:
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {request.method}"},
            )

    async def _handle_tool_call(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle a tool call request.

        معالجة طلب استدعاء أداة.
        """
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32602, "message": "Missing 'name' parameter"},
            )

        handler = self._tool_handlers.get(tool_name)
        if not handler:
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32602, "message": f"Unknown tool: {tool_name}"},
            )

        try:
            result = await handler(**arguments)
            return JSONRPCResponse(
                id=request.id,
                result={"content": [{"type": "text", "text": str(result)}]},
            )
        except Exception as e:
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32603, "message": f"Tool execution failed: {type(e).__name__}: {e}"},
            )

    async def run_stdio(self) -> None:
        """Run server on stdio (for local MCP clients like Claude Desktop).

        تشغيل الخادم على stdio (لعملاء MCP المحليين).
        """
        logger.info(f"Starting MCP server on stdio: {self.name} v{self.version}")
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    continue

                request = JSONRPCRequest(
                    method=data.get("method", ""),
                    params=data.get("params"),
                    id=data.get("id"),
                )
                response = await self.handle_request(request)
                sys.stdout.write(json.dumps(response.to_dict()) + "\n")
                sys.stdout.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"stdio error: {e}")
                break

    def get_fastapi_app(self):
        """Get or create the FastAPI app for HTTP transport.

        الحصول على تطبيق FastAPI للنقل عبر HTTP.
        """
        if self._app is not None:
            return self._app

        try:
            from fastapi import FastAPI, HTTPException
            from fastapi.middleware.cors import CORSMiddleware
            from pydantic import BaseModel
        except ImportError:
            raise ImportError("FastAPI is required for HTTP transport. pip install fastapi")

        app = FastAPI(
            title=f"{self.name} MCP Server",
            version=self.version,
            description="Alpha Wolf Agent MCP server (HTTP/SSE transport)",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        class RPCRequest(BaseModel):
            jsonrpc: str = "2.0"
            method: str
            params: Optional[Dict[str, Any]] = None
            id: Optional[Union[str, int]] = None

        @app.post("/rpc")
        async def rpc_endpoint(req: RPCRequest):
            request = JSONRPCRequest(
                method=req.method,
                params=req.params,
                id=req.id,
            )
            response = await self.handle_request(request)
            return response.to_dict()

        @app.get("/tools")
        async def list_tools_http():
            return {"tools": [
                {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                for t in self.tools.values()
            ]}

        @app.get("/health")
        async def health():
            return {"status": "ok", "name": self.name, "version": self.version, "tools": len(self.tools)}

        self._app = app
        return app


# ============================================================================
# Alpha Wolf MCP Server Instance (registers tools from agent.tools)
# ============================================================================

def create_alpha_wolf_mcp_server() -> MCPServer:
    """Create an MCP server exposing Alpha Wolf tools.

    إنشاء خادم MCP يكشف أدوات Alpha Wolf.

    Registers all 6 tools from backend.agent.tools as MCP tools.
    """
    from . import tools as agent_tools

    server = MCPServer(name="alpha-wolf-agent", version="0.1.0")

    # Wrap each agent tool as an MCP tool
    for spec in agent_tools.TOOL_SPECS:
        tool_name = spec.name
        # Build wrapper that handles ToolResult -> string
        async def make_wrapper(name: str):
            async def wrapper(**kwargs) -> str:
                result = agent_tools.execute_tool(name, kwargs)
                if result.success:
                    return json.dumps(result.output, ensure_ascii=False, default=str)
                else:
                    return f"Error: {result.error}"
            return wrapper

        # Register via the decorator pattern
        server.tools[tool_name] = ToolDefinition(
            name=tool_name,
            description=spec.description + " | " + spec.description_ar,
            input_schema=spec.parameters,
        )

        # Build a proper async closure (Python 3.10+ syntax)
        async def make_handler(name: str):
            async def handler(**kwargs) -> str:
                return await _call_agent_tool(name, kwargs)
            return handler

        # Use a sync wrapper to create the coroutine
        # (avoids asyncio.coroutine which was removed in Python 3.11)
        import functools
        def handler_factory(name: str):
            @functools.wraps(_call_agent_tool)
            async def wrapper(**kwargs):
                return await _call_agent_tool(name, kwargs)
            return wrapper

        server._tool_handlers[tool_name] = handler_factory(tool_name)

    return server


async def _call_agent_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Async wrapper for agent tool execution.

    غلاف غير متزامن لتنفيذ أداة الوكيل.
    """
    from . import tools as agent_tools
    result = agent_tools.execute_tool(name, arguments)
    if result.success:
        return json.dumps(result.output, ensure_ascii=False, default=str)
    return f"Error: {result.error}"


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

async def _async_self_test() -> bool:
    """Verify MCP server works.

    التحقق من أن خادم MCP يعمل.
    """
    print("Running MCP self-tests...")
    print("تشغيل اختبارات MCP الذاتية...")

    passed = 0
    failed = 0

    # Test 1: Create server
    server = MCPServer(name="test-mcp")
    if server.name == "test-mcp":
        passed += 1
        print("  ✓ MCPServer created")
    else:
        failed += 1
        print(f"  ✗ server creation failed: {server.name}")

    # Test 2: Register tool
    @server.tool(name="echo", description="Echo input")
    async def echo(message: str) -> str:
        return f"Echo: {message}"

    if "echo" in server.tools:
        passed += 1
        print("  ✓ tool registered")
    else:
        failed += 1
        print(f"  ✗ tool not registered")

    # Test 3: Handle initialize request
    req = JSONRPCRequest(method="initialize", id=1)
    resp = await server.handle_request(req)
    if resp.result and resp.result.get("serverInfo", {}).get("name") == "test-mcp":
        passed += 1
        print("  ✓ initialize handler")
    else:
        failed += 1
        print(f"  ✗ initialize: {resp.to_dict()}")

    # Test 4: Handle tools/list
    req2 = JSONRPCRequest(method="tools/list", id=2)
    resp2 = await server.handle_request(req2)
    if resp2.result and any(t["name"] == "echo" for t in resp2.result["tools"]):
        passed += 1
        print(f"  ✓ tools/list handler ({len(resp2.result['tools'])} tools)")
    else:
        failed += 1
        print(f"  ✗ tools/list: {resp2.to_dict()}")

    # Test 5: Handle tools/call
    req3 = JSONRPCRequest(
        method="tools/call",
        id=3,
        params={"name": "echo", "arguments": {"message": "hello"}},
    )
    resp3 = await server.handle_request(req3)
    if resp3.result and "Echo: hello" in str(resp3.result):
        passed += 1
        print("  ✓ tools/call handler")
    else:
        failed += 1
        print(f"  ✗ tools/call: {resp3.to_dict()}")

    # Test 6: Unknown tool returns error
    req4 = JSONRPCRequest(
        method="tools/call",
        id=4,
        params={"name": "unknown_tool", "arguments": {}},
    )
    resp4 = await server.handle_request(req4)
    if resp4.error and "Unknown tool" in resp4.error.get("message", ""):
        passed += 1
        print("  ✓ unknown tool error")
    else:
        failed += 1
        print(f"  ✗ unknown tool: {resp4.to_dict()}")

    # Test 7: Unknown method
    req5 = JSONRPCRequest(method="unknown/method", id=5)
    resp5 = await server.handle_request(req5)
    if resp5.error and resp5.error.get("code") == -32601:
        passed += 1
        print("  ✓ unknown method error (code -32601)")
    else:
        failed += 1
        print(f"  ✗ unknown method: {resp5.to_dict()}")

    # Test 8: Get FastAPI app
    try:
        app = server.get_fastapi_app()
        if app is not None:
            passed += 1
            print("  ✓ FastAPI app created")
        else:
            failed += 1
            print(f"  ✗ FastAPI app is None")
    except ImportError:
        failed += 1
        print(f"  ✗ FastAPI not installed (test skipped)")

    # Test 9: Create alpha-wolf MCP server (registers 6 tools)
    wolf_server = create_alpha_wolf_mcp_server()
    if len(wolf_server.tools) == 6:
        passed += 1
        print(f"  ✓ alpha-wolf MCP server: {len(wolf_server.tools)} tools registered")
    else:
        failed += 1
        print(f"  ✗ expected 6 tools, got {len(wolf_server.tools)}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


def _self_test() -> bool:
    """Synchronous wrapper for async self-test."""
    return asyncio.run(_async_self_test())


if __name__ == "__main__":
    _self_test()
