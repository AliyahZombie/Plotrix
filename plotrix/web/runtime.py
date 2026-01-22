from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..config import AppConfig
from ..mcp_client import McpManager
from ..openai_client import ChatCancelledError, ChatClient, ChatMessage


@dataclass
class Session:
    id: str
    title: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
        }


@dataclass
class Run:
    id: str
    session_id: str
    queue: "asyncio.Queue[dict[str, Any]]"
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    error: str | None = None


class Runtime:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            out: list[dict[str, Any]] = []
            for s in self._sessions.values():
                out.append(
                    {
                        "id": s.id,
                        "title": s.title,
                        "created_at": s.created_at,
                        "updated_at": s.updated_at,
                        "message_count": len(s.messages),
                    }
                )
            out.sort(key=lambda x: float(x.get("updated_at") or 0.0), reverse=True)
            return out

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def create_session(self, cfg: AppConfig) -> Session:
        sid = uuid.uuid4().hex
        s = Session(id=sid, title=f"Session {sid[:6]}")
        if cfg.chat.system_prompt.strip():
            s.messages.append(
                ChatMessage(role="system", content=cfg.chat.system_prompt)
            )
        with self._lock:
            self._sessions[sid] = s
        return s

    def reset_session(self, session_id: str, cfg: AppConfig) -> Session | None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            s.messages = []
            if cfg.chat.system_prompt.strip():
                s.messages.append(
                    ChatMessage(role="system", content=cfg.chat.system_prompt)
                )
            s.updated_at = time.time()
            return s

    def create_run(self, session_id: str) -> Run:
        rid = uuid.uuid4().hex
        run = Run(id=rid, session_id=session_id, queue=asyncio.Queue())
        with self._lock:
            self._runs[rid] = run
        return run

    def get_run(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def cancel_run(self, run_id: str) -> bool:
        run = self.get_run(run_id)
        if run is None:
            return False
        run.cancel.set()
        return True

    def start_chat_run(
        self,
        *,
        run: Run,
        cfg: AppConfig,
        user_text: str,
        loop: asyncio.AbstractEventLoop,
        mcp: McpManager | None = None,
    ) -> None:
        s = self.get_session(run.session_id)
        if s is None:
            run.error = "unknown session"
            run.done.set()
            return

        def push(ev: dict[str, Any]) -> None:
            # Called from worker thread; push into asyncio queue.
            asyncio.run_coroutine_threadsafe(run.queue.put(ev), loop)

        def worker() -> None:
            try:
                if run.cancel.is_set():
                    run.error = "cancelled"
                    push({"type": "cancelled"})
                    return

                client = ChatClient(cfg, mcp=mcp)

                # Snapshot messages to avoid concurrent mutation.
                with self._lock:
                    current_messages = list(s.messages)
                    s.messages.append(ChatMessage(role="user", content=user_text))
                    s.updated_at = time.time()
                    current_messages = list(s.messages)

                def on_stream(ev: dict[str, Any]) -> None:
                    push({"type": "stream", "event": ev})

                def on_event(ev: dict[str, Any]) -> None:
                    push({"type": "event", "event": ev})

                text, new_messages = client.chat(
                    current_messages,
                    on_stream=on_stream,
                    on_event=on_event,
                    cancel=run.cancel,
                )
                with self._lock:
                    s.messages = new_messages
                    s.updated_at = time.time()
                push({"type": "done", "assistant": text})
            except ChatCancelledError:
                run.error = "cancelled"
                push({"type": "cancelled"})
            except Exception as e:
                run.error = str(e)
                push({"type": "error", "error": str(e)})
            finally:
                run.done.set()
                push({"type": "eof"})

        t = threading.Thread(
            target=worker, name=f"plotrix-run-{run.id[:8]}", daemon=True
        )
        t.start()
