"""Shared helpers for the demo's agent scripts.

Each agent runs as its own Catalyst App ID via `diagrid dev run`, which
injects DAPR_HTTP_ENDPOINT and DAPR_API_TOKEN. Calls into the mcp-server App
ID are routed through Catalyst, which enforces the access-control config
attached to mcp-server. A tool call that policy denies returns HTTP 403.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from typing import Any

import httpx

DAPR_HTTP_ENDPOINT = os.environ.get("DAPR_HTTP_ENDPOINT", "").rstrip("/")
DAPR_API_TOKEN = os.environ.get("DAPR_API_TOKEN", "")
MCP_APP_ID = os.environ.get("MCP_APP_ID", "mcp-server")

TOOL_PATHS = {
    "write":  "write/mcp",
    "schema": "schema/mcp",
    "query":  "query/mcp",
    "delete": "delete/mcp",
}

# ANSI colours for nice live-demo output.
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _tool_url(tool: str) -> str:
    path = TOOL_PATHS[tool]
    return f"{DAPR_HTTP_ENDPOINT}/v1.0/invoke/{MCP_APP_ID}/method/{path}"


def call_tool(tool: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Invoke an MCP tool through Catalyst. Returns (allowed, message)."""
    url = _tool_url(tool)
    headers = {
        "dapr-api-token": DAPR_API_TOKEN,
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=15.0)
    except httpx.HTTPError as e:
        return False, f"network error: {e!r}"

    if resp.status_code == 403 or "ERR_DIRECT_INVOKE" in resp.text or "PermissionDenied" in resp.text:
        return False, f"BLOCKED by Catalyst access policy (HTTP {resp.status_code})"
    if resp.status_code >= 400:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    text = _parse_mcp_response(resp.text)
    return True, text


def _parse_mcp_response(raw: str) -> str:
    """Pull the tool result text out of an MCP streamable-http SSE response."""
    payload = raw
    for line in raw.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            break
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return raw[:300]
    if "error" in data:
        return f"tool error: {data['error']}"
    content = data.get("result", {}).get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", json.dumps(content))
    return json.dumps(data.get("result", data))


def banner(agent: str, role: str) -> None:
    print(f"\n{BOLD}{CYAN}┌─ {agent} ─ {role}{RESET}")


def step(tool: str, label: str) -> None:
    print(f"{CYAN}│{RESET} {BOLD}{label}{RESET}  {DIM}(tool: {tool}){RESET}")


def result(allowed: bool, message: str) -> None:
    icon = f"{GREEN}✓ ALLOWED{RESET}" if allowed else f"{RED}✗ DENIED{RESET}"
    indent = "│   "
    first, *rest = message.splitlines() or [""]
    print(f"{CYAN}{indent}{RESET}{icon}  {first}")
    for r in rest:
        print(f"{CYAN}{indent}{RESET}          {DIM}{r}{RESET}")


def footer() -> None:
    print(f"{CYAN}└─{RESET}\n")


@contextmanager
def require_env():
    if not DAPR_HTTP_ENDPOINT or not DAPR_API_TOKEN:
        print(
            f"{RED}error:{RESET} DAPR_HTTP_ENDPOINT and DAPR_API_TOKEN must be set.\n"
            f"Run this agent under  diagrid dev run --app-id <agent> -- python ...",
            file=sys.stderr,
        )
        sys.exit(2)
    yield


def run_scenario(agent: str, role: str, plan: list[tuple[str, str, dict]]):
    """Run a list of (tool, label, args) calls and print a summary."""
    with require_env():
        banner(agent, role)
        allowed = denied = 0
        for tool, label, args in plan:
            step(tool, label)
            ok, msg = call_tool(tool, args)
            result(ok, msg)
            allowed += int(ok)
            denied += int(not ok)
        footer()
        print(
            f"{BOLD}{agent} summary:{RESET}  "
            f"{GREEN}{allowed} allowed{RESET}   {RED}{denied} denied{RESET}\n"
        )
