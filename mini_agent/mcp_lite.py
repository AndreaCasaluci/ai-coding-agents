"""A minimal Model Context Protocol (MCP) shaped implementation.

MCP is JSON-RPC 2.0 over a transport (stdio or HTTP). The wire format matters
less than the three primitives:

  * **tools**     — functions the model may call (model-controlled)
  * **resources** — data the application may attach to context (app-controlled)
  * **prompts**   — templates the user may invoke (user-controlled)

That control split is the actual design insight. This module implements
initialize / tools.list / tools.call / resources.list / resources.read over
newline-delimited JSON on stdio — enough to see the shape, not enough to be
spec-compliant. Real servers also negotiate versions, capabilities, and
cancellation.

⚠️ Trust boundary: an MCP server is a program you are handing your agent to.
It can return poisoned text, exfiltrate data through tool arguments, or lie
about its capabilities. Treat a third-party server like a third-party
dependency with network access.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

PROTOCOL_VERSION = "2025-06-18"


class RPCError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class MCPServer:
    name: str
    version: str = "0.1.0"
    tools: dict[str, Callable[[dict[str, Any]], str]] = field(default_factory=dict)
    tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)

    def add_tool(self, schema: dict[str, Any], fn: Callable[[dict[str, Any]], str]) -> None:
        name = schema["name"]
        self.tool_schemas[name] = schema
        self.tools[name] = fn

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Pure request → response. Notifications (no id) return None."""
        method = request.get("method", "")
        params = request.get("params") or {}
        req_id = request.get("id")

        try:
            result = self._dispatch(method, params)
        except RPCError as exc:
            return _error(req_id, exc.code, exc.message)
        except Exception as exc:  # a server bug must not crash the client
            return _error(req_id, -32603, f"{type(exc).__name__}: {exc}")

        if req_id is None:  # notification
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": self.name, "version": self.version},
            }
        if method == "notifications/initialized":
            return {}
        if method == "tools/list":
            return {"tools": list(self.tool_schemas.values())}
        if method == "tools/call":
            name = params.get("name", "")
            if name not in self.tools:
                raise RPCError(-32602, f"Unknown tool: {name}")
            output = self.tools[name](params.get("arguments") or {})
            return {"content": [{"type": "text", "text": str(output)}], "isError": False}
        if method == "resources/list":
            return {
                "resources": [
                    {"uri": uri, "name": uri.rsplit("/", 1)[-1], "mimeType": "text/plain"}
                    for uri in self.resources
                ]
            }
        if method == "resources/read":
            uri = params.get("uri", "")
            if uri not in self.resources:
                raise RPCError(-32602, f"Unknown resource: {uri}")
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": self.resources[uri]}]}
        raise RPCError(-32601, f"Method not found: {method}")

    # -- transports --------------------------------------------------------
    def serve_stdio(self, stdin=None, stdout=None) -> None:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                stdout.write(json.dumps(_error(None, -32700, "Parse error")) + "\n")
                stdout.flush()
                continue
            response = self.handle(request)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()


class InProcessTransport:
    """Fastest transport: call the server directly. Ideal for tests and labs."""

    def __init__(self, server: MCPServer):
        self.server = server

    def request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self.server.handle(payload)


class StdioTransport:
    """Spawn a server process and speak newline-delimited JSON to it."""

    def __init__(self, command: list[str]):
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        if "id" not in payload:
            # JSON-RPC notification: no response is sent by the server.
            return None
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed the connection")
        return json.loads(line)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        for stream in (self.proc.stdout, self.proc.stderr):
            if stream:
                stream.close()


class MCPClient:
    """Client side: handshake, list tools, call one."""

    def __init__(self, transport):
        self.transport = transport
        self._next_id = 0
        self.server_info: dict[str, Any] = {}

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}
        response = self.transport.request(payload)
        if response is None:
            return None
        if "error" in response:
            err = response["error"]
            raise RPCError(err.get("code", -1), err.get("message", "unknown"))
        return response.get("result")

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mini-agent", "version": "0.1.0"},
            },
        )
        self.server_info = result or {}
        self._notify("notifications/initialized")
        return self.server_info

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self.transport.request({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def list_tools(self) -> list[dict[str, Any]]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        return "\n".join(c.get("text", "") for c in result.get("content", []))

    def list_resources(self) -> list[dict[str, Any]]:
        return self._request("resources/list").get("resources", [])

    def read_resource(self, uri: str) -> str:
        result = self._request("resources/read", {"uri": uri})
        return "\n".join(c.get("text", "") for c in result.get("contents", []))


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def as_agent_tools(client: MCPClient) -> list[dict[str, Any]]:
    """MCP tool schemas are already close to the model's format — that is the point."""
    return [t for t in client.list_tools()]
