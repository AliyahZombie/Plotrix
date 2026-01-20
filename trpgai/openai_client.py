from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import AppConfig, ProviderConfig
from .dice import DiceSyntaxError, roll_expression


def _accumulate_tool_calls(
    acc: list[dict[str, Any]],
    delta_tool_calls: Any,
) -> list[dict[str, Any]]:
    if not isinstance(delta_tool_calls, list):
        return acc

    by_index: dict[int, dict[str, Any]] = {i: acc[i] for i in range(len(acc))}

    for item in delta_tool_calls:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if not isinstance(idx, int) or idx < 0:
            continue

        cur = by_index.get(idx)
        if cur is None:
            cur = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
            by_index[idx] = cur

        if "id" in item and item.get("id") is not None:
            cur["id"] = str(item.get("id"))
        if "type" in item and item.get("type") is not None:
            cur["type"] = str(item.get("type"))

        fn_delta = item.get("function")
        if isinstance(fn_delta, dict):
            fn = cur.get("function")
            if not isinstance(fn, dict):
                fn = {"name": "", "arguments": ""}
                cur["function"] = fn

            if "name" in fn_delta and fn_delta.get("name") is not None:
                fn["name"] = str(fn_delta.get("name"))

            if "arguments" in fn_delta and fn_delta.get("arguments") is not None:
                prev = fn.get("arguments")
                prev_s = str(prev) if prev is not None else ""
                fn["arguments"] = prev_s + str(fn_delta.get("arguments"))

    max_idx = max(by_index.keys(), default=-1)
    out: list[dict[str, Any]] = []
    for i in range(max_idx + 1):
        if i in by_index:
            out.append(by_index[i])
    return out


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        return d


class ChatClient:
    def __init__(self, cfg: AppConfig):
        self._cfg = cfg

    def _provider(self) -> ProviderConfig:
        p = self._cfg.providers.get(self._cfg.active_provider)
        if p is None:
            return next(iter(self._cfg.providers.values()))
        return p

    def chat(
        self,
        messages: list[ChatMessage],
        on_stream: Any | None = None,
        on_event: Any | None = None,
    ) -> tuple[str, list[ChatMessage]]:
        provider = self._provider()
        endpoint = provider.base_url.rstrip("/") + "/v1/chat/completions"

        tools: list[dict[str, Any]] = []
        if self._cfg.chat.enable_tool_roll:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "roll_dice",
                        "description": "Roll a TRPG dice expression like 2d6+1, 4d6kh3, d%.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {"type": "string"},
                                "seed": {"type": ["integer", "null"]},
                            },
                            "required": ["expression"],
                            "additionalProperties": False,
                        },
                    },
                }
            )

        max_iters = 8
        current = list(messages)

        def emit(ev: dict[str, Any]) -> None:
            try:
                if callable(on_event):
                    on_event(ev)
            except Exception:
                # UI callbacks should never break core chat.
                pass

        for _ in range(max_iters):
            model = provider.model
            if not model and provider.models:
                model = provider.models[0]

            payload: dict[str, Any] = {
                "model": model,
                "messages": [m.to_dict() for m in current],
            }

            temp = self._cfg.chat.temperature
            if temp is not None:
                payload["temperature"] = float(temp)

            if self._cfg.chat.max_completion_tokens is not None:
                payload["max_completion_tokens"] = int(self._cfg.chat.max_completion_tokens)
            elif self._cfg.chat.max_output_tokens is not None:
                payload["max_output_tokens"] = int(self._cfg.chat.max_output_tokens)
            elif self._cfg.chat.max_tokens is not None:
                payload["max_tokens"] = int(self._cfg.chat.max_tokens)
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            stream_enabled = bool(self._cfg.chat.stream and callable(on_stream))
            if stream_enabled:
                payload["stream"] = True

            assistant_content: str | None = None
            tool_calls: list[dict[str, Any]] = []

            if stream_enabled:
                try:
                    if callable(on_stream):
                        on_stream({"type": "start"})
                    assistant_content, tool_calls = self._post_json_stream(endpoint, payload, on_stream=on_stream)
                    if callable(on_stream):
                        on_stream({"type": "end", "content": assistant_content or "", "tool_calls": tool_calls})
                except Exception:
                    stream_enabled = False
                    payload.pop("stream", None)

            if not stream_enabled:
                data = self._post_json(endpoint, payload)

                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError("no choices in response")

                msg = (choices[0] or {}).get("message") or {}
                assistant_content = msg.get("content")

                raw_tool_calls = msg.get("tool_calls")
                if isinstance(raw_tool_calls, list):
                    for tc in raw_tool_calls:
                        if isinstance(tc, dict):
                            tool_calls.append({str(k): v for k, v in tc.items()})

                fc = msg.get("function_call")
                if fc and not tool_calls:
                    tool_calls = [
                        {
                            "id": "function_call",
                            "type": "function",
                            "function": {
                                "name": fc.get("name"),
                                "arguments": fc.get("arguments"),
                            },
                        }
                    ]

            if tool_calls:
                current.append(
                    ChatMessage(
                        role="assistant",
                        content=assistant_content,
                        tool_calls=tool_calls,
                    )
                )

                emit(
                    {
                        "type": "assistant_tool_calls",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    }
                )

                for call in tool_calls:
                    tool_msg = self._handle_tool_call(call)
                    current.append(tool_msg)
                    emit(
                        {
                            "type": "tool_result",
                            "call": call,
                            "tool_call_id": tool_msg.tool_call_id,
                            "content": tool_msg.content,
                        }
                    )

                continue

            current.append(ChatMessage(role="assistant", content=str(assistant_content or "")))
            emit({"type": "assistant_final", "content": str(assistant_content or "")})
            return str(assistant_content or ""), current

        raise RuntimeError("tool call loop did not converge")

    def _handle_tool_call(self, call: dict[str, Any]) -> ChatMessage:
        call_id = str(call.get("id") or "")
        fn = call.get("function") or {}
        name = str(fn.get("name") or "")
        raw_args = fn.get("arguments")

        if name != "roll_dice":
            content = json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=True)
            return ChatMessage(role="tool", tool_call_id=call_id, content=content)

        args: dict[str, Any] = {}
        if isinstance(raw_args, str) and raw_args.strip():
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {"expression": str(raw_args)}

        expr = args.get("expression")
        seed = args.get("seed")

        if not isinstance(expr, str) or not expr.strip():
            content = json.dumps({"error": "roll_dice requires expression"}, ensure_ascii=True)
            return ChatMessage(role="tool", tool_call_id=call_id, content=content)

        seed_i: int | None = None
        if seed is not None:
            try:
                seed_i = int(seed)
            except (TypeError, ValueError):
                seed_i = None

        try:
            rolled = roll_expression(expr, seed=seed_i)
        except DiceSyntaxError as e:
            content = json.dumps({"error": str(e), "expression": expr}, ensure_ascii=True)
            return ChatMessage(role="tool", tool_call_id=call_id, content=content)

        content = json.dumps(rolled, ensure_ascii=True)
        return ChatMessage(role="tool", tool_call_id=call_id, content=content)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        provider = self._provider()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.extra_headers or {})

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        context = None
        if not provider.verify_tls:
            context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, timeout=float(provider.timeout_s), context=context) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"http {e.code}: {raw}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"network error: {e}") from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"invalid json response: {raw[:200]}") from None

        if not isinstance(data, dict):
            raise RuntimeError("unexpected response shape")
        return data

    def _post_json_stream(
        self,
        url: str,
        payload: dict[str, Any],
        on_stream: Any,
    ) -> tuple[str, list[dict[str, Any]]]:
        provider = self._provider()
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.extra_headers or {})

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        context = None
        if not provider.verify_tls:
            context = ssl._create_unverified_context()

        assistant_parts: list[str] = []
        tool_calls_acc: list[dict[str, Any]] = []

        def emit(event: dict[str, Any]) -> None:
            if callable(on_stream):
                on_stream(event)

        try:
            with urllib.request.urlopen(req, timeout=float(provider.timeout_s), context=context) as resp:
                while True:
                    raw = resp.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue

                    data_str = line[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(chunk, dict):
                        continue

                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue

                    choice0 = choices[0]
                    if not isinstance(choice0, dict):
                        continue

                    delta = choice0.get("delta")
                    if not isinstance(delta, dict):
                        continue

                    content_delta = delta.get("content")
                    if isinstance(content_delta, str) and content_delta:
                        assistant_parts.append(content_delta)
                        emit({"type": "content_delta", "delta": content_delta})

                    tool_calls_acc = _accumulate_tool_calls(tool_calls_acc, delta.get("tool_calls"))
                    if tool_calls_acc:
                        emit({"type": "tool_calls", "tool_calls": tool_calls_acc})

        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"http {e.code}: {raw}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"network error: {e}") from None

        return "".join(assistant_parts), tool_calls_acc
