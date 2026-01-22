from __future__ import annotations

import importlib
import json
import locale
import textwrap
import time
import unicodedata
from pathlib import Path
from typing import Any

from .config import (
    AppConfig,
    McpConfig,
    McpServerConfig,
    ProviderConfig,
    default_config_path,
    save_config,
)
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


def _tool_name_from_call(call: dict[str, Any]) -> str:
    fn = call.get("function")
    if isinstance(fn, dict):
        name = fn.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return ""


def _format_tool_status(
    tool_call_id: str, call: dict[str, Any], state: str, elapsed_s: float | None
) -> str:
    name = _tool_name_from_call(call)
    header = f"{state}"
    if name:
        header += f"  {name}"
    if tool_call_id:
        header += f"  id={tool_call_id}"
    if elapsed_s is not None:
        header += f"  {elapsed_s:.2f}s"
    return header


def run_chat_tui(
    cfg: AppConfig, share_roll: bool, config_path: Path | None = None
) -> int:
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


def _ensure_system_message(
    messages: list[ChatMessage], system_prompt: str
) -> list[ChatMessage]:
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


def _wrap_transcript(
    transcript: list[tuple[str, str]], width: int
) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    w = max(10, width)

    # Keep internal role ids stable (for coloring), but show Chinese labels.
    role_label = {
        "you": "你",
        "ai": "助手",
        "sys": "系统",
        "err": "错误",
        "tool": "工具",
    }

    for who, text in transcript:
        prefix = f"{role_label.get(who, who)}> "
        prefix_cols = _wcswidth(prefix)
        avail = max(4, w - prefix_cols - 1)
        parts = text.splitlines() or [""]
        first = True
        for part in parts:
            wrapped = textwrap.wrap(part, width=avail) or [""]
            for seg in wrapped:
                if first:
                    lines.append((who, prefix + seg))
                    first = False
                else:
                    lines.append((who, " " * prefix_cols + seg))
            first = False

        lines.append((who, ""))

    return lines


def _chat_loop(
    c: Any, stdscr: Any, cfg: AppConfig, share_roll: bool, path: Path
) -> int:
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
    transcript.append(("sys", "Plotrix 终端聊天。输入 /help 查看命令。"))

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

        hint = "PgUp/PgDn 滚动  Enter 发送  /roll  /config  /model  /mcp  /reset  /exit"
        stdscr.addnstr(h - 2, 0, status or hint, max(0, w - 1))

        prompt = "你> "
        prompt_cols = _wcswidth(prompt)
        avail_cols = max(1, w - prompt_cols - 1)

        hoff = 0
        while hoff < cursor and _wcswidth(input_buf[hoff:cursor]) > avail_cols:
            hoff += 1

        visible, _end = _slice_to_cols(input_buf, hoff, avail_cols)
        stdscr.addnstr(h - 1, 0, prompt + visible, max(0, w - 1))

        cur_x = prompt_cols + _wcswidth(input_buf[hoff:cursor])
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
            append("sys", "（退出）")
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
                append("sys", "（退出）")
                break

            if line in {"/help", "help", "?"}:
                append(
                    "sys",
                    "命令：/roll 表达式, /config, /provider [name], /providers, /models, /model provider:model, /mcp, /reset, /exit",
                )
                continue

            if line.startswith("/reset"):
                transcript = [("sys", "（会话已重置）")]
                messages = _ensure_system_message([], cfg.chat.system_prompt)
                continue

            if line.startswith("/mcp"):
                parts = line.split()
                sub = parts[1].lower() if len(parts) >= 2 else "status"

                def render_status() -> None:
                    st = client.mcp_status()
                    names = list(cfg.mcp.servers.keys())
                    if not names:
                        append("sys", "MCP：未配置服务器")
                        return

                    lines: list[str] = []
                    ok = 0
                    err = 0
                    off = 0
                    tools_total = 0

                    now = time.time()
                    for name in names:
                        scfg = cfg.mcp.servers[name]
                        rt = st.get(name) or {}
                        enabled = bool(scfg.enabled)
                        mark = "*" if enabled else " "

                        last_error = rt.get("last_error")
                        initialized = bool(rt.get("initialized"))
                        tool_count = rt.get("tool_count")
                        last_sync = rt.get("last_sync")
                        transport = str(scfg.transport or "auto")

                        if not enabled:
                            tag = "OFF"
                            off += 1
                        elif last_error:
                            tag = "ERR"
                            err += 1
                        elif initialized:
                            tag = "OK"
                            ok += 1
                        else:
                            tag = "NEW"

                        tools_str = "--"
                        if isinstance(tool_count, int):
                            tools_str = str(tool_count)
                            tools_total += tool_count

                        sync_str = "--"
                        if isinstance(last_sync, (int, float)) and last_sync > 0:
                            age = max(0, int(now - float(last_sync)))
                            sync_str = f"{age}s"

                        url = scfg.url
                        base = f"{mark} {name:<10} {tag:<3} tools={tools_str:<3} sync={sync_str:<6} transport={transport}"
                        if url:
                            base += f" url={url}"
                        lines.append(base)
                        if last_error:
                            lines.append(f"    最近错误: {last_error}")

                    append("sys", "MCP 服务器：\n" + "\n".join(lines))
                    append(
                        "sys",
                        f"MCP：正常={ok} 错误={err} 关闭={off} 工具总数={tools_total}",
                    )

                if sub in {"status", "list"}:
                    render_status()
                    continue

                if sub == "sync":
                    target = parts[2] if len(parts) >= 3 else None
                    if target is not None and target not in cfg.mcp.servers:
                        append("err", f"未知 MCP 服务器: {target}")
                        continue
                    if target is not None and not cfg.mcp.servers[target].enabled:
                        append(
                            "err",
                            f"MCP 服务器已禁用: {target}（使用 /mcp on {target} 启用）",
                        )
                        continue

                    append("sys", f"MCP：正在同步{' ' + target if target else ''}...")
                    status = "MCP：同步中..."
                    draw()
                    try:
                        client.mcp_sync(server_name=target)
                    except Exception as e:
                        append("err", f"MCP 同步失败: {e}")
                        continue
                    render_status()
                    continue

                if sub == "tools":
                    target = parts[2] if len(parts) >= 3 else None
                    if target is not None and target not in cfg.mcp.servers:
                        append("err", f"未知 MCP 服务器: {target}")
                        continue

                    try:
                        tools = client.mcp_tools(server_name=target)
                    except Exception as e:
                        append("err", f"获取 MCP 工具失败: {e}")
                        continue

                    if not tools:
                        append("sys", "MCP：未加载工具（可尝试 /mcp sync）")
                        continue

                    lines: list[str] = []
                    for t in tools:
                        server = str(t.get("server") or "")
                        mcp_name = str(t.get("mcp_name") or "")
                        public = str(t.get("public_name") or "")
                        desc = str(t.get("description") or "")
                        if desc:
                            desc = desc.splitlines()[0]
                        lines.append(f"{server}: {mcp_name} -> {public}  {desc}")

                    append("sys", "MCP 工具：\n" + "\n".join(lines))
                    continue

                if sub in {"on", "off", "enable", "disable"}:
                    if len(parts) < 3:
                        append("err", "用法：/mcp on|off <server>")
                        continue
                    name = parts[2]
                    if name not in cfg.mcp.servers:
                        append("err", f"未知 MCP 服务器: {name}（可通过 /config 编辑）")
                        continue

                    enabled = sub in {"on", "enable"}
                    old = cfg.mcp.servers[name]
                    servers = dict(cfg.mcp.servers)
                    servers[name] = McpServerConfig(
                        url=old.url,
                        transport=old.transport,
                        protocol_version=old.protocol_version,
                        timeout_s=old.timeout_s,
                        verify_tls=old.verify_tls,
                        headers=old.headers,
                        enabled=enabled,
                    )
                    cfg = AppConfig(
                        active_provider=cfg.active_provider,
                        providers=cfg.providers,
                        chat=cfg.chat,
                        mcp=McpConfig(servers=servers),
                    )
                    save_config(cfg, path)
                    client = ChatClient(cfg)
                    append("sys", f"MCP 服务器 {name}: {'启用' if enabled else '禁用'}")
                    render_status()
                    continue

                append(
                    "err",
                    "用法：/mcp [status|list|sync [server]|tools [server]|on <server>|off <server>]",
                )
                continue

            if line.startswith("/providers"):
                names = list(cfg.providers.keys())
                if not names:
                    append("sys", "未配置 provider")
                    continue
                shown = []
                for name in names:
                    mark = "*" if name == cfg.active_provider else " "
                    shown.append(f"{mark} {name}")
                append("sys", "providers：\n" + "\n".join(shown))
                continue

            if line.startswith("/models"):
                p = cfg.providers.get(cfg.active_provider)
                if p is None:
                    append("err", "未找到当前 provider")
                    continue
                models = p.models or ([] if not p.model else [p.model])
                shown = []
                for m in models:
                    mark = "*" if m == p.model else " "
                    shown.append(f"{mark} {m}")
                append("sys", f"{cfg.active_provider} 的模型：\n" + "\n".join(shown))
                continue

            if line.startswith("/provider"):
                arg = line[len("/provider") :].strip()
                if not arg:
                    append("sys", f"当前 provider: {cfg.active_provider}")
                    continue
                if arg not in cfg.providers:
                    append("err", f"未知 provider: {arg}")
                    continue
                cfg = AppConfig(
                    active_provider=arg,
                    providers=cfg.providers,
                    chat=cfg.chat,
                    mcp=cfg.mcp,
                )
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
                    append("sys", f"当前模型: {cfg.active_provider}:{cur}")
                    continue

                if ":" in arg:
                    prov, model = arg.split(":", 1)
                    prov = prov.strip()
                    model = model.strip()
                else:
                    prov = cfg.active_provider
                    model = arg.strip()

                if not prov or not model:
                    append("err", "用法：/model provider:model")
                    continue

                p = cfg.providers.get(prov)
                if p is None:
                    append("err", f"未知 provider: {prov}")
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

                cfg = AppConfig(
                    active_provider=prov,
                    providers=providers,
                    chat=cfg.chat,
                    mcp=cfg.mcp,
                )
                save_config(cfg, path)
                client = ChatClient(cfg)
                append("sys", f"已切换模型: {prov}:{model}")
                continue

            if line.startswith("/config"):
                updated = edit_config_tui_in_session(c, stdscr, cfg, path)
                save_config(updated, path)
                cfg = updated
                client = ChatClient(cfg)
                messages = _ensure_system_message(messages, cfg.chat.system_prompt)
                append("sys", f"已保存: {path}")
                continue

            if line.startswith("/roll"):
                expr = line[len("/roll") :].strip()
                if not expr:
                    append("err", "用法：/roll 2d6+1")
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

            status = "思考中..."
            draw()

            stream_slot: int | None = None
            stream_text = ""
            last_draw = 0.0
            last_event_draw = 0.0

            tool_status_slots: dict[str, tuple[int, float, dict[str, Any]]] = {}
            # Stream-mode tool calls: render/update early to avoid end-of-turn "jump".
            stream_tool_call_slots: dict[int, int] = {}

            def on_stream(ev: dict[str, Any]) -> None:
                nonlocal stream_text, last_draw
                t = ev.get("type")
                if t == "content_delta":
                    d = ev.get("delta")
                    if isinstance(d, str) and d:
                        stream_text += d
                        if stream_slot is not None and 0 <= stream_slot < len(
                            transcript
                        ):
                            transcript[stream_slot] = ("ai", stream_text)

                        now = time.monotonic()
                        if now - last_draw >= 0.05:
                            last_draw = now
                            draw()

                elif t == "tool_calls":
                    calls = ev.get("tool_calls")
                    if isinstance(calls, list):
                        for i, call in enumerate(calls):
                            if not isinstance(call, dict):
                                continue
                            rendered = _format_tool_call(call)
                            slot = stream_tool_call_slots.get(i)
                            if slot is None:
                                slot = len(transcript)
                                transcript.append(("tool", rendered))
                                stream_tool_call_slots[i] = slot
                            elif 0 <= slot < len(transcript):
                                transcript[slot] = ("tool", rendered)

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
                        for i, call in enumerate(calls):
                            if not isinstance(call, dict):
                                continue
                            rendered = _format_tool_call(call)
                            slot = stream_tool_call_slots.get(i)
                            if slot is not None and 0 <= slot < len(transcript):
                                transcript[slot] = ("tool", rendered)
                            else:
                                append("tool", rendered)

                elif t == "tool_result":
                    tool_call_id = ev.get("tool_call_id")
                    content = ev.get("content")
                    tool_call_id_s = str(tool_call_id) if tool_call_id else ""

                    if tool_call_id_s and tool_call_id_s in tool_status_slots:
                        slot, start_t, call = tool_status_slots[tool_call_id_s]
                        elapsed = time.monotonic() - start_t
                        if 0 <= slot < len(transcript):
                            transcript[slot] = (
                                "tool",
                                _format_tool_status(
                                    tool_call_id_s, call, "DONE", elapsed
                                ),
                            )
                        tool_status_slots.pop(tool_call_id_s, None)

                    append("tool", _format_tool_result(tool_call_id_s or None, content))

                elif t == "tool_start":
                    tool_call_id = ev.get("tool_call_id")
                    call = ev.get("call")
                    tool_call_id_s = str(tool_call_id) if tool_call_id else ""
                    call_d = call if isinstance(call, dict) else {}

                    if tool_call_id_s:
                        slot = len(transcript)
                        transcript.append(
                            (
                                "tool",
                                _format_tool_status(
                                    tool_call_id_s, call_d, "RUNNING", None
                                ),
                            )
                        )
                        tool_status_slots[tool_call_id_s] = (
                            slot,
                            time.monotonic(),
                            call_d,
                        )

                elif t == "assistant_final":
                    content = ev.get("content")
                    if isinstance(content, str):
                        if not (cfg.chat.stream and stream_text):
                            append("ai", content)

                elif t == "mcp_error":
                    err = ev.get("error")
                    append("err", f"MCP 错误: {err}")

                now = time.monotonic()
                if now - last_event_draw >= 0.02:
                    last_event_draw = now
                    draw()

            if cfg.chat.stream:
                stream_slot = len(transcript)
                transcript.append(("ai", ""))

            try:
                _assistant_text, new_messages = client.chat(
                    messages, on_stream=on_stream, on_event=on_event
                )
            except Exception as e:
                if stream_slot is not None and stream_slot < len(transcript):
                    transcript.pop(stream_slot)
                append("err", f"错误: {e}")
                continue

            if stream_slot is not None and stream_slot < len(transcript):
                # Streaming placeholder: keep it if we actually streamed visible content.
                if not (cfg.chat.stream and stream_text):
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
