from __future__ import annotations

import asyncio
import time
import os
import threading
from pathlib import Path
from typing import Any

from ..config import AppConfig, default_config_path, load_config, save_config
from ..dice import DiceSyntaxError, roll_expression
from ..mcp_client import McpManager
from ..openai_client import ChatClient
from .runtime import Runtime
from .util import REDACTED, merge_redacted_config, redact_config, sse_event


def create_app(config_path: Path | None = None):
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Web UI dependencies missing. Install with: pip install 'plotrix[web]'"
        ) from e

    cfg_path = config_path or default_config_path()
    rt = Runtime()

    mcp_lock = threading.Lock()
    mcp_cached: McpManager | None = None
    mcp_snapshot: dict[str, Any] | None = None

    app = FastAPI(title="Plotrix Web")

    # Local-only UI: allow browser origins on localhost/127.0.0.1.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def _index() -> Any:
        return FileResponse(str(static_dir / "index.html"))

    def _load_cfg() -> AppConfig:
        return load_config(cfg_path)

    def _get_mcp(cfg: AppConfig) -> McpManager:
        nonlocal mcp_cached, mcp_snapshot
        snap = cfg.to_dict().get("mcp")
        if not isinstance(snap, dict):
            snap = {}
        with mcp_lock:
            if mcp_cached is None or mcp_snapshot != snap:
                mcp_cached = McpManager(cfg.mcp.servers)
                mcp_snapshot = snap
            return mcp_cached

    @app.get("/api/config")
    def get_config() -> Any:
        cfg = _load_cfg()
        env_key = bool(
            ("OPENAI_API_KEY" in os.environ) or ("PLOTRIX_API_KEY" in os.environ)
        )
        return {
            "config_path": str(cfg_path),
            "env_api_key_present": env_key,
            "config": redact_config(cfg),
            "redacted_sentinel": REDACTED,
        }

    @app.put("/api/config")
    async def put_config(req: Request) -> Any:
        raw = await req.json()
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="config must be an object")

        # Support both { ...config fields... } and {"config": {...}} payloads.
        if isinstance(raw.get("config"), dict):
            raw = raw.get("config")

        old = _load_cfg()
        merged = merge_redacted_config(raw, old)
        save_config(merged, cfg_path)
        return {
            "config_path": str(cfg_path),
            "config": redact_config(merged),
            "redacted_sentinel": REDACTED,
        }

    @app.post("/api/sessions")
    def create_session() -> Any:
        cfg = _load_cfg()
        s = rt.create_session(cfg)
        return {"session_id": s.id}

    @app.get("/api/sessions")
    def list_sessions() -> Any:
        return {"sessions": rt.list_sessions()}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> Any:
        s = rt.get_session(session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        return s.to_dict()

    @app.post("/api/sessions/{session_id}/reset")
    def reset_session(session_id: str) -> Any:
        cfg = _load_cfg()
        s = rt.reset_session(session_id, cfg)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        return {"ok": True, "session": s.to_dict()}

    @app.post("/api/sessions/{session_id}/message")
    async def post_message(session_id: str, req: Request) -> Any:
        s = rt.get_session(session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        raw = await req.json()
        if not isinstance(raw, dict) or not isinstance(raw.get("content"), str):
            raise HTTPException(status_code=400, detail="content required")
        content = str(raw.get("content") or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content required")

        cfg = _load_cfg()
        loop = asyncio.get_running_loop()
        run = rt.create_run(session_id)
        rt.start_chat_run(
            run=run,
            cfg=cfg,
            user_text=content,
            loop=loop,
            mcp=_get_mcp(cfg),
        )
        return {"run_id": run.id}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str):
        run = rt.get_run(run_id)
        if run is None:
            return PlainTextResponse("run not found", status_code=404)

        async def gen():
            # Keep the connection alive even if there are no events yet.
            last_ping = time.time()
            try:
                yield sse_event("hello", {"run_id": run.id})
                while True:
                    if time.time() - last_ping > 15:
                        last_ping = time.time()
                        yield sse_event("ping", {"t": last_ping})
                    try:
                        ev = await asyncio.wait_for(run.queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if run.done.is_set():
                            break
                        continue
                    yield sse_event("event", ev)
                    if ev.get("type") == "eof":
                        break
            except asyncio.CancelledError:
                # Browser disconnected; best-effort cancel.
                run.cancel.set()
                raise

        from fastapi.responses import StreamingResponse

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> Any:
        run = rt.get_run(run_id)
        if run is None:
            return {"ok": False}
        run.cancel.set()
        # Notify client immediately.
        await run.queue.put({"type": "cancel_requested"})
        return {"ok": True}

    @app.post("/api/dice/roll")
    async def dice_roll(req: Request) -> Any:
        raw = await req.json()
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="invalid body")
        expr = raw.get("expression")
        seed = raw.get("seed")
        if not isinstance(expr, str) or not expr.strip():
            raise HTTPException(status_code=400, detail="expression required")
        seed_i: int | None = None
        if seed is not None and seed != "":
            try:
                seed_i = int(seed)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400, detail="seed must be int"
                ) from None
        try:
            return {"ok": True, "result": roll_expression(expr, seed=seed_i)}
        except DiceSyntaxError as e:
            return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

    @app.get("/api/mcp/servers")
    def mcp_servers() -> Any:
        cfg = _load_cfg()
        client = ChatClient(cfg, mcp=_get_mcp(cfg))
        return {"status": client.mcp_status()}

    @app.post("/api/mcp/sync")
    async def mcp_sync(req: Request) -> Any:
        cfg = _load_cfg()
        client = ChatClient(cfg, mcp=_get_mcp(cfg))
        try:
            raw = await req.json()
        except Exception:
            raw = {}
        server = None
        if isinstance(raw, dict) and raw.get("server"):
            server = str(raw.get("server"))
        return {"status": client.mcp_sync(server_name=server)}

    @app.get("/api/mcp/tools")
    def mcp_tools(server: str | None = None) -> Any:
        cfg = _load_cfg()
        client = ChatClient(cfg, mcp=_get_mcp(cfg))
        return {"tools": client.mcp_tools(server_name=server)}

    @app.get("/{path:path}")
    def spa_fallback(path: str) -> Any:
        # Allow hard refresh on hash-less routes if the frontend uses them.
        if path.startswith("api/") or path.startswith("static/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(str(static_dir / "index.html"))

    return app
