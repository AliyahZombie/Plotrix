from __future__ import annotations

import json
from typing import Any

from ..config import AppConfig, ProviderConfig


REDACTED = "__REDACTED__"


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in ("key", "token", "secret", "authorization", "api_key"))


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (headers or {}).items():
        out[str(k)] = REDACTED if _is_sensitive_key(str(k)) and str(v) else str(v)
    return out


def redact_config(cfg: AppConfig) -> dict[str, Any]:
    """Return config as dict, with obvious secrets redacted.

    This is primarily to prevent accidental leakage via exports, logs, or screenshots.
    In local-only mode, users can still update secrets via PUT /api/config.
    """

    d = cfg.to_dict()

    providers = d.get("providers")
    if isinstance(providers, dict):
        for _name, p in providers.items():
            if not isinstance(p, dict):
                continue
            api_key = p.get("api_key")
            if isinstance(api_key, str) and api_key:
                p["api_key"] = REDACTED
            extra_headers = p.get("extra_headers")
            if isinstance(extra_headers, dict):
                p["extra_headers"] = redact_headers(
                    {str(k): str(v) for k, v in extra_headers.items()}
                )

    mcp = d.get("mcp")
    if isinstance(mcp, dict):
        servers = mcp.get("servers")
        if isinstance(servers, dict):
            for _name, s in servers.items():
                if not isinstance(s, dict):
                    continue
                headers = s.get("headers")
                if isinstance(headers, dict):
                    s["headers"] = redact_headers(
                        {str(k): str(v) for k, v in headers.items()}
                    )

    return d


def _merge_provider_secret(
    old: ProviderConfig | None, incoming_raw: dict[str, Any], parsed: ProviderConfig
) -> ProviderConfig:
    if old is None:
        return parsed

    raw_api_key = incoming_raw.get("api_key", None)
    if raw_api_key is None or raw_api_key == REDACTED:
        api_key = old.api_key
    else:
        api_key = str(raw_api_key)

    raw_headers = incoming_raw.get("extra_headers")
    extra_headers: dict[str, str] = dict(parsed.extra_headers)
    if isinstance(raw_headers, dict):
        extra_headers = {}
        for k, v in raw_headers.items():
            ks = str(k)
            if v == REDACTED and ks in (old.extra_headers or {}):
                extra_headers[ks] = str(old.extra_headers.get(ks))
            else:
                extra_headers[ks] = str(v)

    return ProviderConfig(
        base_url=parsed.base_url,
        api_key=api_key,
        timeout_s=parsed.timeout_s,
        verify_tls=parsed.verify_tls,
        extra_headers=extra_headers,
        models=parsed.models,
        model=parsed.model,
    )


def merge_redacted_config(raw: dict[str, Any], old: AppConfig) -> AppConfig:
    """Parse AppConfig from raw dict, preserving redacted secrets from `old`.

    Frontend receives secrets as REDACTED. When it sends back an unchanged config,
    we must keep the original secret values.
    """

    parsed = AppConfig.from_dict(raw if isinstance(raw, dict) else {})

    raw_providers = raw.get("providers") if isinstance(raw, dict) else None
    providers_out: dict[str, ProviderConfig] = {}
    for name, p in parsed.providers.items():
        incoming_raw = {}
        if isinstance(raw_providers, dict) and isinstance(
            raw_providers.get(name), dict
        ):
            incoming_raw = raw_providers.get(name) or {}
        providers_out[name] = _merge_provider_secret(
            old.providers.get(name), incoming_raw, p
        )

    # Merge MCP headers redaction.
    raw_mcp = raw.get("mcp") if isinstance(raw, dict) else None
    raw_servers = raw_mcp.get("servers") if isinstance(raw_mcp, dict) else None
    mcp_servers_out = {}
    for name, s in parsed.mcp.servers.items():
        incoming_raw = {}
        if isinstance(raw_servers, dict) and isinstance(raw_servers.get(name), dict):
            incoming_raw = raw_servers.get(name) or {}

        headers: dict[str, str] = dict(s.headers or {})
        raw_headers = incoming_raw.get("headers")
        if isinstance(raw_headers, dict):
            headers = {}
            old_s = old.mcp.servers.get(name)
            for k, v in raw_headers.items():
                ks = str(k)
                if v == REDACTED and old_s is not None and ks in (old_s.headers or {}):
                    headers[ks] = str(old_s.headers.get(ks))
                else:
                    headers[ks] = str(v)

        mcp_servers_out[name] = type(s)(
            url=s.url,
            transport=s.transport,
            protocol_version=s.protocol_version,
            timeout_s=s.timeout_s,
            verify_tls=s.verify_tls,
            headers=headers,
            enabled=s.enabled,
        )

    return AppConfig(
        active_provider=parsed.active_provider,
        providers=providers_out,
        chat=parsed.chat,
        mcp=type(parsed.mcp)(servers=mcp_servers_out),
    )


def sse_event(event: str, data: dict[str, Any]) -> str:
    # SSE payload; keep it simple and spec-compliant.
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
