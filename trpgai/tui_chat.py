from __future__ import annotations

import importlib
import json
import locale
import textwrap
import time
import unicodedata
from pathlib import Path
from typing import Any

from .config import AppConfig, ProviderConfig, default_config_path, save_config
from .dice import DiceSyntaxError, roll_expression
from .openai_client import ChatClient, ChatMessage
from .tui_config import edit_config_tui_in_session


def _format_tool_call(call: dict[str, Any]) -> str:
    fn = call.get("function") or {}
    name = str(fn.get("name") or "")
    raw_args = fn.get("arguments")

    args_text = ""
    if isinstance(raw_args, str) and raw_args.strip():
        try:
            parsed = json.loads(raw_args)
            args_text = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        except json.JSONDecodeError:
            args_text = raw_args
    elif raw_args is not None:
        try:
            args_text = json.dumps(raw_args, ensure_ascii=False, sort_keys=True)
        except TypeError:
            args_text = str(raw_args)

    call_id = str(call.get("id") or "")
    header = f"CALL {name}" if name else "CALL"
    if call_id:
        header += f"  id={call_id}"

    if args_text:
        return header + "\n" + args_text
    return header


def _format_tool_result(tool_call_id: str | None, content: str | None) -> str:
    header = "RESULT"
    if tool_call_id:
        header += f"  id={tool_call_id}"

    if content is None:
        return header

    body = content
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            if "error" in parsed:
                body = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
            elif "text" in parsed and isinstance(parsed.get("text"), str):
                body = str(parsed.get("text"))
            else:
                body = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        else:
            body = json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        body = content

    if len(body) > 2000:
        body = body[:2000] + "..."

    return header + "\n" + body


def run_chat_tui(cfg: AppConfig, share_roll: bool, config_path: Path | None = None) -> int:
    try:
        locale.setlocale(locale.LC_ALL, "")
    except Exception:
        pass

    try:
        c = importlib.import_module("curses")
    except Exception as e:
        raise RuntimeError("curses is not available in this python build") from e

    path = config_path or default_config_path()

    def inner(stdscr: Any) -> int:
        return _chat_loop(c, stdscr, cfg, share_roll, path)

    return int(c.wrapper(inner))


def _ensure_system_message(messages: list[ChatMessage], system_prompt: str) -> list[ChatMessage]:
    out = list(messages)

    if out and out[0].role == "system":
        out = out[1:]

    if system_prompt.strip():
        out.insert(0, ChatMessage(role="system", content=system_prompt))

    return out


def _wcwidth_char(ch: str) -> int:
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    eaw = unicodedata.east_asian_width(ch)
    if eaw in {"W", "F"}:
        return 2
    return 1


def _wcswidth(s: str) -> int:
    return sum(_wcwidth_char(ch) for ch in s)


def _slice_to_cols(s: str, start: int, max_cols: int) -> tuple[str, int]:
    cols = 0
    i = start
    out: list[str] = []
    while i < len(s):
        w = _wcwidth_char(s[i])
        if cols + w > max_cols:
            break
        cols += w
        out.append(s[i])
        i += 1
    return "".join(out), i


def _wrap_transcript(transcript: list[tuple[str, str]], width: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    w = max(10, width)

    for who, text in transcript:
        prefix = f"{who}> "
        avail = max(4, w - len(prefix) - 1)
        parts = text.splitlines() or [""]
        first = True
        for part in parts:
            wrapped = textwrap.wrap(part, width=avail) or [""]
            for seg in wrapped:
                if first:
                    lines.append((who, prefix + seg))
                    first = False
                else:
                    lines.append((who, " " * len(prefix) + seg))
            first = False

        lines.append((who, ""))

    return lines


def _chat_loop(c: Any, stdscr: Any, cfg: AppConfig, share_roll: bool, path: Path) -> int:
    c.curs_set(1)
    stdscr.keypad(True)

    try:
        c.use_default_colors()
        c.init_pair(1, c.COLOR_CYAN, -1)
        c.init_pair(2, c.COLOR_GREEN, -1)
        c.init_pair(3, c.COLOR_YELLOW, -1)
        c.init_pair(4, c.COLOR_MAGENTA, -1)
    except Exception:
        pass

    client = ChatClient(cfg)
    messages: list[ChatMessage] = _ensure_system_message([], cfg.chat.system_prompt)

    transcript: list[tuple[str, str]] = []
    transcript.append(("sys", "TRPGAI TUI chat. /help for commands."))

    input_buf = ""
    cursor = 0
    scroll = 0
    status = ""

    def max_scroll(wrapped: list[tuple[str, str]], h: int) -> int:
        view_h = max(1, h - 2)
        return max(0, len(wrapped) - view_h)

    def draw() -> None:
        nonlocal status
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        wrapped = _wrap_transcript(transcript, width=w)
        ms = max_scroll(wrapped, h)
        nonlocal_scroll = min(max(0, scroll), ms)

        view_h = max(1, h - 2)
        end = len(wrapped) - nonlocal_scroll
        start = max(0, end - view_h)

        for row, (who, line) in enumerate(wrapped[start:end], start=0):
            attr = 0
            try:
                if who == "you":
                    attr = c.color_pair(1)
                elif who == "ai":
                    attr = c.color_pair(2)
                elif who in {"sys", "err"}:
                    attr = c.color_pair(3)
                elif who == "tool":
                    attr = c.color_pair(4)
            except Exception:
                attr = 0

            stdscr.addnstr(row, 0, line, max(0, w - 1), attr)

        hint = "PgUp/PgDn scroll  Enter send  /roll  /config  /model  /reset  /exit"
        stdscr.addnstr(h - 2, 0, status or hint, max(0, w - 1))

        prompt = "you> "
        avail_cols = max(1, w - len(prompt) - 1)

        hoff = 0
        while hoff < cursor and _wcswidth(input_buf[hoff:cursor]) > avail_cols:
            hoff += 1

        visible, _end = _slice_to_cols(input_buf, hoff, avail_cols)
        stdscr.addnstr(h - 1, 0, prompt + visible, max(0, w - 1))

        cur_x = len(prompt) + _wcswidth(input_buf[hoff:cursor])
        stdscr.move(h - 1, min(int(cur_x), max(0, w - 1)))

        stdscr.refresh()
        status = ""

    def append(who: str, text: str) -> None:
        nonlocal scroll
        transcript.append((who, text))
        scroll = 0

    while True:
        draw()
        try:
            ch = stdscr.get_wch()
        except Exception:
            ch = stdscr.getch()

        if isinstance(ch, int) and ch == c.KEY_RESIZE:
            continue

        if ch in (3, "\x03"):
            append("sys", "(exit)")
            break

        if isinstance(ch, int) and ch in (c.KEY_PPAGE,):
            h, w = stdscr.getmaxyx()
            wrapped = _wrap_transcript(transcript, width=w)
            scroll = min(max_scroll(wrapped, h), scroll + max(1, (h - 2) // 2))
            continue

        if isinstance(ch, int) and ch in (c.KEY_NPAGE,):
            scroll = max(0, scroll - max(1, (stdscr.getmaxyx()[0] - 2) // 2))
            continue

        if isinstance(ch, int) and ch in (c.KEY_LEFT,):
            cursor = max(0, cursor - 1)
            continue

        if isinstance(ch, int) and ch in (c.KEY_RIGHT,):
            cursor = min(len(input_buf), cursor + 1)
            continue

        if isinstance(ch, int) and ch in (c.KEY_HOME,):
            cursor = 0
            continue

        if isinstance(ch, int) and ch in (c.KEY_END,):
            cursor = len(input_buf)
            continue

        if isinstance(ch, int) and ch in (c.KEY_DC,):
            if cursor < len(input_buf):
                input_buf = input_buf[:cursor] + input_buf[cursor + 1 :]
            continue

        if ch in (c.KEY_BACKSPACE, 127, 8, "\b", "\x7f"):
            if cursor > 0:
                input_buf = input_buf[: cursor - 1] + input_buf[cursor:]
                cursor -= 1
            continue

        if ch in (27, "\x1b"):
            input_buf = ""
            cursor = 0
            continue

        if ch in (c.KEY_ENTER, 10, 13, "\n", "\r"):
            line = input_buf.strip()
            input_buf = ""
            cursor = 0
            if not line:
                continue

            if line in {"/exit", "/quit"}:
                append("sys", "(exit)")
                break

            if line in {"/help", "help", "?"}:
                append(
                    "sys",
                    "commands: /roll EXPR, /config, /provider [name], /providers, /models, /model provider:model, /reset, /exit",
                )
                continue

            if line.startswith("/reset"):
                transcript = [("sys", "(session reset)")]
                messages = _ensure_system_message([], cfg.chat.system_prompt)
                continue

            if line.startswith("/providers"):
                names = list(cfg.providers.keys())
                if not names:
                    append("sys", "no providers configured")
                    continue
                shown = []
                for name in names:
                    mark = "*" if name == cfg.active_provider else " "
                    shown.append(f"{mark} {name}")
                append("sys", "providers:\n" + "\n".join(shown))
                continue

            if line.startswith("/models"):
                p = cfg.providers.get(cfg.active_provider)
                if p is None:
                    append("err", "active provider not found")
                    continue
                models = p.models or ([] if not p.model else [p.model])
                shown = []
                for m in models:
                    mark = "*" if m == p.model else " "
                    shown.append(f"{mark} {m}")
                append("sys", f"models for {cfg.active_provider}:\n" + "\n".join(shown))
                continue

            if line.startswith("/provider"):
                arg = line[len("/provider") :].strip()
                if not arg:
                    append("sys", f"active provider: {cfg.active_provider}")
                    continue
                if arg not in cfg.providers:
                    append("err", f"unknown provider: {arg}")
                    continue
                cfg = AppConfig(active_provider=arg, providers=cfg.providers, chat=cfg.chat)
                save_config(cfg, path)
                client = ChatClient(cfg)
                append("sys", f"switched provider: {arg}")
                continue

            if line.startswith("/model") or line.startswith("/modell"):
                parts = line.split(maxsplit=1)
                arg = parts[1].strip() if len(parts) == 2 else ""
                if not arg:
                    p = cfg.providers.get(cfg.active_provider)
                    cur = p.model if p is not None else ""
                    append("sys", f"active model: {cfg.active_provider}:{cur}")
                    continue

                if ":" in arg:
                    prov, model = arg.split(":", 1)
                    prov = prov.strip()
                    model = model.strip()
                else:
                    prov = cfg.active_provider
                    model = arg.strip()

                if not prov or not model:
                    append("err", "usage: /model provider:model")
                    continue

                p = cfg.providers.get(prov)
                if p is None:
                    append("err", f"unknown provider: {prov}")
                    continue

                models = list(p.models)
                if model not in models:
                    models = [model] + models

                providers = dict(cfg.providers)
                providers[prov] = ProviderConfig(
                    base_url=p.base_url,
                    api_key=p.api_key,
                    timeout_s=p.timeout_s,
                    verify_tls=p.verify_tls,
                    extra_headers=p.extra_headers,
                    models=models,
                    model=model,
                )

                cfg = AppConfig(active_provider=prov, providers=providers, chat=cfg.chat)
                save_config(cfg, path)
                client = ChatClient(cfg)
                append("sys", f"switched model: {prov}:{model}")
                continue



            if line.startswith("/config"):
                updated = edit_config_tui_in_session(c, stdscr, cfg, path)
                save_config(updated, path)
                cfg = updated
                client = ChatClient(cfg)
                messages = _ensure_system_message(messages, cfg.chat.system_prompt)
                append("sys", f"saved: {path}")
                continue

            if line.startswith("/roll"):
                expr = line[len("/roll") :].strip()
                if not expr:
                    append("err", "usage: /roll 2d6+1")
                    continue
                try:
                    r = roll_expression(expr)
                except DiceSyntaxError as e:
                    append("err", str(e))
                    continue

                append("sys", r["text"])
                if share_roll:
                    messages.append(ChatMessage(role="user", content=r["text"]))
                continue

            append("you", line)
            messages.append(ChatMessage(role="user", content=line))

            status = "thinking..."
            draw()

            stream_slot: int | None = None
            stream_text = ""
            last_draw = 0.0
            last_event_draw = 0.0

            def on_stream(ev: dict[str, Any]) -> None:
                nonlocal stream_text, last_draw
                if ev.get("type") == "content_delta":
                    d = ev.get("delta")
                    if isinstance(d, str) and d:
                        stream_text += d
                        if stream_slot is not None and 0 <= stream_slot < len(transcript):
                            transcript[stream_slot] = ("ai", stream_text)

                        now = time.monotonic()
                        if now - last_draw >= 0.05:
                            last_draw = now
                            draw()

            def on_event(ev: dict[str, Any]) -> None:
                nonlocal last_event_draw
                t = ev.get("type")

                if t == "assistant_tool_calls":
                    # If streaming produced deltas, the assistant text is already on screen.
                    # If streaming falls back (no deltas), we still want to show the content.
                    content = ev.get("content")
                    if isinstance(content, str) and content.strip():
                        if not (cfg.chat.stream and stream_text):
                            append("ai", content)

                    calls = ev.get("tool_calls")
                    if isinstance(calls, list):
                        for call in calls:
                            if isinstance(call, dict):
                                append("tool", _format_tool_call(call))

                elif t == "tool_result":
                    tool_call_id = ev.get("tool_call_id")
                    content = ev.get("content")
                    append("tool", _format_tool_result(str(tool_call_id) if tool_call_id else None, content))

                elif t == "assistant_final":
                    content = ev.get("content")
                    if isinstance(content, str):
                        if not (cfg.chat.stream and stream_text):
                            append("ai", content)

                now = time.monotonic()
                if now - last_event_draw >= 0.02:
                    last_event_draw = now
                    draw()

            if cfg.chat.stream:
                stream_slot = len(transcript)
                transcript.append(("ai", ""))

            try:
                _assistant_text, new_messages = client.chat(messages, on_stream=on_stream, on_event=on_event)
            except Exception as e:
                if stream_slot is not None and stream_slot < len(transcript):
                    transcript.pop(stream_slot)
                append("err", f"error: {e}")
                continue

            if stream_slot is not None and stream_slot < len(transcript):
                transcript.pop(stream_slot)

            messages = new_messages
            continue

        if isinstance(ch, str):
            if ch.isprintable():
                input_buf = input_buf[:cursor] + ch + input_buf[cursor:]
                cursor += len(ch)
            continue

        if isinstance(ch, int) and 0 <= ch <= 255:
            try:
                s = chr(ch)
            except ValueError:
                continue
            if s.isprintable():
                input_buf = input_buf[:cursor] + s + input_buf[cursor:]
                cursor += 1

    return 0
