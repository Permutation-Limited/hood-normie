"""Minimal Streamable HTTP client for Robinhood's official MCP server."""

import json
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any, Mapping


class McpError(RuntimeError):
    pass


class RobinhoodMcpClient:
    def __init__(self, endpoint: str, bearer_token: str, timeout: float = 30,
                 verbose: bool = False):
        self.endpoint = endpoint
        self.bearer_token = bearer_token
        self.timeout = timeout
        self.verbose = verbose
        self.session_id: str | None = None
        self._request_id = 0

    def connect(self) -> None:
        self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "hood-normie", "version": "0.1.0"},
        })
        self._notify("notifications/initialized", {})

    def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        result = self._rpc("tools/call", {"name": name, "arguments": dict(arguments or {})})
        if result.get("isError"):
            raise McpError(f"Robinhood tool {name} failed: {result}")
        structured = result.get("structuredContent")
        if structured is not None:
            return structured
        for item in result.get("content", []):
            if item.get("type") == "text":
                text = item.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        return result

    def _rpc(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        self._request_id += 1
        response = self._post({
            "jsonrpc": "2.0", "id": self._request_id,
            "method": method, "params": params,
        })
        if "error" in response:
            raise McpError(f"MCP {method} failed: {response['error']}")
        return response.get("result", {})

    def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params}, notification=True)

    def _post(self, payload: Mapping[str, Any], notification: bool = False) -> Mapping[str, Any]:
        if self.verbose:
            print(f"\n>>> MCP POST {self.endpoint}", file=sys.stderr)
            print(json.dumps(payload, indent=2, default=str), file=sys.stderr)
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
            "X-Request-ID": str(uuid.uuid4()),
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(
            self.endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.session_id = response.headers.get("Mcp-Session-Id", self.session_id)
                body = response.read().decode()
                if notification and not body:
                    return {}
                if response.headers.get_content_type() == "text/event-stream":
                    data_lines = [line[6:] for line in body.splitlines() if line.startswith("data: ")]
                    body = data_lines[-1]
                parsed = json.loads(body) if body else {}
                if self.verbose:
                    print(f"<<< MCP HTTP {response.status}", file=sys.stderr)
                    print(json.dumps(parsed, indent=2, default=str), file=sys.stderr)
                return parsed
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            if self.verbose:
                print(f"<<< MCP HTTP {error.code}", file=sys.stderr)
                print(detail, file=sys.stderr)
            raise McpError(f"MCP HTTP {error.code}: {detail}") from error
