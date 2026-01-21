from __future__ import annotations

import hashlib
import json
import queue
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import McpServerConfig


class McpError(RuntimeError):
    pass


def _mcp_tool_public_name(server_name: str, tool_name: str) -> str:
    # OpenAI tool names: ^[a-zA-Z0-9_-]{1,64}$
    # MCP tool names may include '.' or '/'.
    raw = f"mcp__{server_name}__{tool_name}"
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", raw)
    if len(sanitized) <= 64:
        return sanitized

    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:9]
    return f"{sanitized[:54]}_{h}"


def _iter_sse_events(resp: Any) -> Any:
    # Incremental SSE parser.
    # Yields (event_name, data_text) for each event separated by a blank line.
    event_name: str | None = None
    data_lines: list[str] = []

    while True:
        raw = resp.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")

        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
                event_name = None
                data_lines = []
            continue

        if line.startswith("event:"):
            event_name = line[len("event:") :].strip() or None
            continue

        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
            continue

    if data_lines:
        yield event_name, "\n".join(data_lines)


def _jsonrpc_request(method: str, params: dict[str, Any], request_id: int) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def _jsonrpc_notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _jsonrpc_is_response(msg: Any) -> bool:
    return isinstance(msg, dict) and msg.get("jsonrpc") == "2.0" and "id" in msg and (
        "result" in msg or "error" in msg
    )


def _jsonrpc_raise_if_error(resp: dict[str, Any]) -> None:
    err = resp.get("error")
    if not err:
        return
    if isinstance(err, dict):
        code = err.get("code")
        msg = err.get("message")
        raise McpError(f"mcp error {code}: {msg}")
    raise McpError(f"mcp error: {err}")


@dataclass
class McpTool:
    server: str
    mcp_name: str
    public_name: str
    description: str
    input_schema: dict[str, Any]


class _StreamableHttpTransport:
    def __init__(self, server: McpServerConfig):
        self._server = server
        self._session_id: str | None = None
        self._next_id = 1

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1

        msg = _jsonrpc_request(method, params=params, request_id=req_id)
        resp = self._post(msg)
        if not _jsonrpc_is_response(resp):
            raise McpError("invalid json-rpc response")

        resp_id = resp.get("id")
        if resp_id is None:
            raise McpError("missing json-rpc id")
        try:
            resp_id_i = int(resp_id)
        except (TypeError, ValueError):
            raise McpError("invalid json-rpc id") from None

        if resp_id_i != req_id:
            raise McpError("json-rpc id mismatch")
        _jsonrpc_raise_if_error(resp)
        return resp

    def notify(self, method: str, params: dict[str, Any]) -> None:
        msg = _jsonrpc_notification(method, params=params)
        try:
            self._post(msg, expect_response=False)
        except Exception:
            pass

    def _post(self, payload: dict[str, Any], expect_response: bool = True) -> dict[str, Any]:
        url = self._server.url
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self._server.protocol_version,
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        headers.update(self._server.headers or {})

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        context = None
        if not self._server.verify_tls:
            context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, timeout=float(self._server.timeout_s), context=context) as resp:
                sid = resp.headers.get("MCP-Session-Id")
                if sid:
                    self._session_id = str(sid)

                if not expect_response:
                    return {}

                ctype = resp.headers.get("Content-Type") or ""
                if "text/event-stream" in ctype:
                    # Synchronous parse until we see our response.
                    for _ev, data in _iter_sse_events(resp):
                        if data.strip() == "[DONE]":
                            continue
                        try:
                            msg = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if _jsonrpc_is_response(msg):
                            return msg
                    raise McpError("stream ended without json-rpc response")

                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise McpError(f"http {e.code}: {raw}") from None
        except urllib.error.URLError as e:
            raise McpError(f"network error: {e}") from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise McpError("invalid json") from None

        if not isinstance(data, dict):
            raise McpError("unexpected response shape")
        return data


class _LegacySseTransport:
    def __init__(self, server: McpServerConfig):
        self._server = server
        self._next_id = 1

        self._session_id: str | None = None
        self._post_url: str | None = None

        self._stop = threading.Event()
        self._inbox: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._thread: threading.Thread | None = None

        self._start_receiver()

    def close(self) -> None:
        self._stop.set()

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1

        msg = _jsonrpc_request(method, params=params, request_id=req_id)
        self._post(msg)

        deadline = time.time() + float(self._server.timeout_s)
        while time.time() < deadline:
            try:
                incoming = self._inbox.get(timeout=0.1)
            except queue.Empty:
                continue

            if _jsonrpc_is_response(incoming):
                incoming_id = incoming.get("id")
                if incoming_id is None:
                    continue
                try:
                    incoming_id_i = int(incoming_id)
                except (TypeError, ValueError):
                    continue

                if incoming_id_i == req_id:
                    _jsonrpc_raise_if_error(incoming)
                    return incoming

        raise McpError(f"timeout waiting for response id={req_id}")

    def notify(self, method: str, params: dict[str, Any]) -> None:
        msg = _jsonrpc_notification(method, params=params)
        try:
            self._post(msg)
        except Exception:
            pass

    def _sse_url(self) -> str:
        u = self._server.url.rstrip("/")
        if u.endswith("/sse"):
            return u
        return u + "/sse"

    def _start_receiver(self) -> None:
        t = threading.Thread(target=self._receiver_loop, daemon=True)
        t.start()
        self._thread = t

        # Wait briefly for endpoint discovery so calls can proceed.
        deadline = time.time() + 5.0
        while self._post_url is None and time.time() < deadline:
            time.sleep(0.05)

    def _receiver_loop(self) -> None:
        url = self._sse_url()
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "MCP-Protocol-Version": self._server.protocol_version,
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        headers.update(self._server.headers or {})

        req = urllib.request.Request(url, headers=headers, method="GET")
        context = None
        if not self._server.verify_tls:
            context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, timeout=float(self._server.timeout_s), context=context) as resp:
                sid = resp.headers.get("MCP-Session-Id")
                if sid:
                    self._session_id = str(sid)

                for ev_name, data in _iter_sse_events(resp):
                    if self._stop.is_set():
                        break

                    if ev_name == "endpoint" and self._post_url is None:
                        ep = data.strip()
                        if ep:
                            # Server may send relative or absolute.
                            self._post_url = urllib.parse.urljoin(url + "/", ep)
                        continue

                    if not data.strip():
                        continue
                    try:
                        msg = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(msg, dict):
                        self._inbox.put(msg)

        except Exception:
            return

    def _post(self, payload: dict[str, Any]) -> None:
        if not self._post_url:
            raise McpError("legacy sse: endpoint not discovered")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": self._server.protocol_version,
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        headers.update(self._server.headers or {})

        req = urllib.request.Request(
            self._post_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        context = None
        if not self._server.verify_tls:
            context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, timeout=float(self._server.timeout_s), context=context) as resp:
                sid = resp.headers.get("MCP-Session-Id")
                if sid:
                    self._session_id = str(sid)
                _ = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise McpError(f"http {e.code}: {raw}") from None
        except urllib.error.URLError as e:
            raise McpError(f"network error: {e}") from None


class McpManager:
    def __init__(self, servers: dict[str, McpServerConfig]):
        # Keep disabled servers too; UI needs to display them.
        self._servers = dict(servers)
        self._clients: dict[str, Any] = {}
        self._tools: list[McpTool] = []
        self._public_to_tool: dict[str, McpTool] = {}
        self._runtime: dict[str, dict[str, Any]] = {}

        for name, cfg in self._servers.items():
            self._runtime[name] = {
                "enabled": bool(cfg.enabled),
                "initialized": False,
                "tool_count": None,
                "last_error": None,
                "last_sync": None,
            }

    def has_servers(self) -> bool:
        for cfg in self._servers.values():
            if cfg.enabled and cfg.url:
                return True
        return False

    def status(self) -> dict[str, dict[str, Any]]:
        # name -> runtime snapshot
        out: dict[str, dict[str, Any]] = {}
        for name, cfg in self._servers.items():
            rt = dict(self._runtime.get(name) or {})
            rt["enabled"] = bool(cfg.enabled)
            rt["url"] = cfg.url
            rt["transport"] = cfg.transport
            out[name] = rt
        return out

    def refresh_tools(self, server_name: str | None = None) -> None:
        tools: list[McpTool] = []
        public_to_tool: dict[str, McpTool] = {}

        if server_name is None:
            target_names: list[str] = list(self._servers.keys())
        else:
            target_names = [server_name]

        for name in target_names:
            cfg = self._servers.get(name)
            if cfg is None:
                continue

            # Keep runtime in sync with current config.
            if name not in self._runtime:
                self._runtime[name] = {
                    "enabled": bool(cfg.enabled),
                    "initialized": False,
                    "tool_count": None,
                    "last_error": None,
                    "last_sync": None,
                }
            self._runtime[name]["enabled"] = bool(cfg.enabled)

            if not cfg.enabled:
                self._runtime[name]["initialized"] = False
                continue

            if not cfg.url:
                self._runtime[name]["initialized"] = False
                self._runtime[name]["last_error"] = "missing url"
                continue

            client = self._clients.get(name)
            if client is None:
                client = self._make_client(cfg)
                self._clients[name] = client

            # Initialize handshake.
            init_params = {
                "protocolVersion": cfg.protocol_version,
                "clientInfo": {"name": "trpgai", "version": "0.1"},
                "capabilities": {"tools": {}},
            }

            try:
                try:
                    _ = client.call("initialize", init_params)
                except McpError:
                    # auto-transport fallback: if streamable HTTP fails, try legacy SSE.
                    if (cfg.transport or "auto").lower().strip() == "auto" and not isinstance(
                        client, _LegacySseTransport
                    ):
                        client = _LegacySseTransport(cfg)
                        self._clients[name] = client
                        _ = client.call("initialize", init_params)
                    else:
                        raise

                client.notify("initialized", {})

                resp = client.call("tools/list", {})
                result = resp.get("result")
                raw_tools = None
                if isinstance(result, dict):
                    raw_tools = result.get("tools")

                if not isinstance(raw_tools, list):
                    raise McpError("tools/list returned no tools")

            except Exception as e:
                self._runtime[name]["initialized"] = False
                self._runtime[name]["last_error"] = str(e)
                continue

            self._runtime[name]["initialized"] = True
            self._runtime[name]["last_error"] = None
            self._runtime[name]["last_sync"] = time.time()
            self._runtime[name]["tool_count"] = int(len(raw_tools))

            for t in raw_tools:
                if not isinstance(t, dict):
                    continue
                mcp_name = t.get("name")
                if not isinstance(mcp_name, str) or not mcp_name:
                    continue
                desc = t.get("description")
                desc_s = str(desc) if desc is not None else ""
                schema = t.get("inputSchema")
                if not isinstance(schema, dict):
                    schema = {"type": "object", "properties": {}}

                public = _mcp_tool_public_name(name, mcp_name)
                tool = McpTool(
                    server=name,
                    mcp_name=mcp_name,
                    public_name=public,
                    description=desc_s,
                    input_schema=schema,
                )
                tools.append(tool)
                public_to_tool[public] = tool

        # Only replace registry when refreshing all servers.
        if server_name is None:
            self._tools = tools
            self._public_to_tool = public_to_tool
        else:
            # Merge: keep other tools intact.
            keep = [t for t in self._tools if t.server != server_name]
            self._tools = keep + tools
            self._public_to_tool = {k: v for k, v in self._public_to_tool.items() if v.server != server_name}
            self._public_to_tool.update(public_to_tool)

    def openai_tools(self) -> list[dict[str, Any]]:
        if not self.has_servers():
            return []

        if not self._tools:
            self.refresh_tools()

        out: list[dict[str, Any]] = []
        for t in self._tools:
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.public_name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
            )
        return out

    def tools(self, server_name: str | None = None) -> list[McpTool]:
        if not self._tools:
            self.refresh_tools(server_name=None)
        if server_name is None:
            return list(self._tools)
        return [t for t in self._tools if t.server == server_name]

    def call_tool(self, public_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._public_to_tool.get(public_name)
        if tool is None:
            raise McpError(f"unknown mcp tool: {public_name}")

        cfg = self._servers.get(tool.server)
        if cfg is None or not cfg.enabled:
            raise McpError(f"mcp server disabled: {tool.server}")

        client = self._clients.get(tool.server)
        if client is None:
            raise McpError(f"mcp server not initialized: {tool.server}")

        resp = client.call("tools/call", {"name": tool.mcp_name, "arguments": arguments})
        result = resp.get("result")
        if not isinstance(result, dict):
            return {"text": json.dumps(resp, ensure_ascii=True)}

        text_parts: list[str] = []
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text_val = item.get("text")
                if item.get("type") == "text" and isinstance(text_val, str):
                    text_parts.append(text_val)

        text = "\n".join(text_parts).strip()
        return {"text": text or json.dumps(result, ensure_ascii=True), "raw": result}

    def _make_client(self, cfg: McpServerConfig) -> Any:
        transport = (cfg.transport or "auto").lower().strip()
        if transport == "streamable_http":
            return _StreamableHttpTransport(cfg)
        if transport == "legacy_sse":
            return _LegacySseTransport(cfg)

        # auto: try streamable http first.
        try:
            return _StreamableHttpTransport(cfg)
        except Exception:
            return _LegacySseTransport(cfg)
