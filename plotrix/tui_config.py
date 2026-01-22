from __future__ import annotations

import importlib
import json
import locale
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import AppConfig, ProviderConfig


class TuiCancelled(Exception):
    pass


def edit_config_tui(cfg: AppConfig, path: Path) -> AppConfig:
    try:
        locale.setlocale(locale.LC_ALL, "")
    except Exception:
        pass

    try:
        c = importlib.import_module("curses")
    except Exception as e:
        raise RuntimeError("curses is not available in this python build") from e

    try:
        return c.wrapper(lambda stdscr: _edit_config(c, stdscr, cfg, path))
    except TuiCancelled:
        return cfg


def edit_config_tui_in_session(
    c: Any, stdscr: Any, cfg: AppConfig, path: Path
) -> AppConfig:
    try:
        return _edit_config(c, stdscr, cfg, path)
    except TuiCancelled:
        return cfg


def _mask_secret(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 4:
        return "*" * len(v)
    return v[:2] + "*" * (len(v) - 4) + v[-2:]


def _edit_config(c: Any, stdscr: Any, cfg: AppConfig, path: Path) -> AppConfig:
    c.curs_set(0)
    stdscr.keypad(True)

    work = cfg.to_dict()
    idx = 0
    status = ""

    def fields() -> list[dict[str, Any]]:
        providers = work.setdefault("providers", {})
        chat = work.setdefault("chat", {})
        mcp = work.setdefault("mcp", {})

        active = str(work.get("active_provider") or "default")

        if not isinstance(providers, dict):
            providers = {}
            work["providers"] = providers

        if active not in providers or not isinstance(providers.get(active), dict):
            providers[active] = asdict(ProviderConfig())

        p = providers[active]

        if not isinstance(mcp, dict):
            mcp = {}
            work["mcp"] = mcp

        servers = mcp.get("servers")
        if not isinstance(servers, dict):
            servers = {}
            mcp["servers"] = servers

        def get_models_text() -> str:
            raw = p.get("models")
            if isinstance(raw, list):
                return "\n".join(str(x) for x in raw if str(x))
            return ""

        def set_models_text(v: str) -> None:
            models: list[str] = []
            for line in v.splitlines():
                s = line.strip()
                if s:
                    models.append(s)
            p["models"] = models
            if not p.get("model") and models:
                p["model"] = models[0]

        return [
            {
                "key": "active_provider",
                "kind": "str",
                "get": lambda: str(work.get("active_provider", "default")),
                "set": lambda v: work.__setitem__(
                    "active_provider", str(v) or "default"
                ),
            },
            {
                "key": f"providers.{active}.base_url",
                "kind": "str",
                "get": lambda: str(p.get("base_url", "")),
                "set": lambda v: p.__setitem__("base_url", v),
            },
            {
                "key": f"providers.{active}.api_key",
                "kind": "secret",
                "get": lambda: _mask_secret(str(p.get("api_key", ""))),
                "set": lambda v: p.__setitem__("api_key", v),
            },
            {
                "key": f"providers.{active}.model",
                "kind": "str",
                "get": lambda: str(p.get("model", "")),
                "set": lambda v: p.__setitem__("model", v),
            },
            {
                "key": f"providers.{active}.models",
                "kind": "text",
                "get": get_models_text,
                "set": set_models_text,
            },
            {
                "key": f"providers.{active}.timeout_s",
                "kind": "float",
                "get": lambda: str(p.get("timeout_s", "")),
                "set": lambda v: p.__setitem__("timeout_s", v),
            },
            {
                "key": f"providers.{active}.verify_tls",
                "kind": "bool",
                "get": lambda: bool(p.get("verify_tls", True)),
                "set": lambda v: p.__setitem__("verify_tls", v),
            },
            {
                "key": f"providers.{active}.extra_headers",
                "kind": "json",
                "get": lambda: json.dumps(
                    p.get("extra_headers", {}) or {}, ensure_ascii=True
                ),
                "set": lambda v: p.__setitem__("extra_headers", v),
            },
            {
                "key": "mcp.servers",
                "kind": "json",
                "get": lambda: json.dumps(servers, ensure_ascii=True),
                "set": lambda v: mcp.__setitem__("servers", v),
            },
            {
                "key": "chat.system_prompt",
                "kind": "text",
                "get": lambda: str(chat.get("system_prompt", "")),
                "set": lambda v: chat.__setitem__("system_prompt", v),
            },
            {
                "key": "chat.temperature",
                "kind": "float_or_empty",
                "get": lambda: ""
                if chat.get("temperature") is None
                else str(chat.get("temperature")),
                "set": lambda v: chat.__setitem__("temperature", v),
            },
            {
                "key": "chat.max_tokens",
                "kind": "int_or_empty",
                "get": lambda: ""
                if chat.get("max_tokens") is None
                else str(chat.get("max_tokens")),
                "set": lambda v: chat.__setitem__("max_tokens", v),
            },
            {
                "key": "chat.max_completion_tokens",
                "kind": "int_or_empty",
                "get": lambda: ""
                if chat.get("max_completion_tokens") is None
                else str(chat.get("max_completion_tokens")),
                "set": lambda v: chat.__setitem__("max_completion_tokens", v),
            },
            {
                "key": "chat.max_output_tokens",
                "kind": "int_or_empty",
                "get": lambda: ""
                if chat.get("max_output_tokens") is None
                else str(chat.get("max_output_tokens")),
                "set": lambda v: chat.__setitem__("max_output_tokens", v),
            },
            {
                "key": "chat.stream",
                "kind": "bool",
                "get": lambda: bool(chat.get("stream", False)),
                "set": lambda v: chat.__setitem__("stream", v),
            },
            {
                "key": "chat.enable_tool_roll",
                "kind": "bool",
                "get": lambda: bool(chat.get("enable_tool_roll", True)),
                "set": lambda v: chat.__setitem__("enable_tool_roll", v),
            },
        ]

    def draw() -> None:
        nonlocal status
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        title = f"Plotrix 配置: {path}"
        stdscr.addnstr(0, 0, title, w - 1)
        stdscr.addnstr(
            1,
            0,
            "UP/DOWN：选择  ENTER：编辑  SPACE：切换布尔  s：保存  q/ESC：取消",
            w - 1,
        )

        fs = fields()
        top = 0
        if idx >= h - 4:
            top = idx - (h - 5)

        for row, f in enumerate(fs[top : top + (h - 4)], start=2):
            k = f["key"]
            v = f["get"]()
            line = f"{k}: {v}"
            if top + (row - 2) == idx:
                stdscr.attron(c.A_REVERSE)
                stdscr.addnstr(row, 0, line, w - 1)
                stdscr.attroff(c.A_REVERSE)
            else:
                stdscr.addnstr(row, 0, line, w - 1)

        stdscr.hline(h - 2, 0, ord("-"), max(0, w - 1))
        stdscr.addnstr(h - 1, 0, status, w - 1)
        stdscr.refresh()
        status = ""

    def prompt_text(initial: str, multiline: bool) -> str:
        h, w = stdscr.getmaxyx()
        win_h = min(10 if multiline else 3, max(3, h - 4))
        win_w = min(max(40, w - 4), w - 2)
        y = max(1, (h - win_h) // 2)
        x = max(1, (w - win_w) // 2)

        win = c.newwin(win_h, win_w, y, x)
        win.border()
        win.addnstr(
            0,
            2,
            " 编辑（CTRL+G 完成） " if multiline else " 编辑（ENTER 完成） ",
            win_w - 4,
        )

        box = c.newwin(win_h - 2, win_w - 2, y + 1, x + 1)
        box.erase()
        if initial:
            lines = initial.splitlines() if multiline else [initial]
            for i, line in enumerate(lines[: win_h - 2]):
                box.addnstr(i, 0, line, win_w - 3)
        box.refresh()

        if multiline:
            textpad = importlib.import_module("curses.textpad")
            tb = textpad.Textbox(box, insert_mode=True)
            s = tb.edit().rstrip("\n")
            return s

        c.curs_set(1)
        c.echo()
        box.move(0, min(len(initial), win_w - 3))
        s = box.getstr(0, 0, win_w - 3).decode("utf-8", errors="replace")
        c.noecho()
        c.curs_set(0)
        return s

    while True:
        draw()
        ch = stdscr.getch()

        if ch in (ord("q"), 27):
            raise TuiCancelled()

        if ch == c.KEY_UP:
            idx = max(0, idx - 1)
            continue

        if ch == c.KEY_DOWN:
            idx = min(len(fields()) - 1, idx + 1)
            continue

        if ch == ord("s"):
            try:
                return _dict_to_config(work)
            except Exception as e:
                status = f"配置无效: {e}"
            continue

        fs = fields()
        f = fs[idx]
        kind = f["kind"]

        if kind == "bool" and ch == ord(" "):
            cur = bool(f["get"]())
            f["set"](not cur)
            continue

        if ch not in (c.KEY_ENTER, 10, 13):
            continue

        try:
            if kind in {"str", "secret"}:
                s = prompt_text(
                    "" if kind == "secret" else str(f["get"]()), multiline=False
                )
                f["set"](s)

            elif kind == "float":
                s = prompt_text(str(f["get"]()), multiline=False).strip()
                f["set"](float(s))

            elif kind == "float_or_empty":
                s = prompt_text(str(f["get"]()), multiline=False).strip()
                f["set"](None if s == "" else float(s))

            elif kind == "int_or_empty":
                s = prompt_text(str(f["get"]()), multiline=False).strip()
                f["set"](None if s == "" else int(s))

            elif kind == "json":
                raw = prompt_text(str(f["get"]()), multiline=True)
                parsed = json.loads(raw) if raw.strip() else {}
                if not isinstance(parsed, dict):
                    raise ValueError("must be a json object")
                f["set"](parsed)

            elif kind == "text":
                s = prompt_text(str(f["get"]()), multiline=True)
                f["set"](s)

        except Exception as e:
            status = f"edit failed: {e}"


def _dict_to_config(d: dict[str, Any]) -> AppConfig:
    return AppConfig.from_dict(d)
