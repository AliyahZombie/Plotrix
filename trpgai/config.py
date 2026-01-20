from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _xdg_config_home() -> Path:
    env = os.environ.get("XDG_CONFIG_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config"


def default_config_path() -> Path:
    return _xdg_config_home() / "trpgai" / "config.json"


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str = "https://api.openai.com"
    api_key: str = ""
    timeout_s: float = 60.0
    verify_tls: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)

    models: list[str] = field(default_factory=lambda: ["gpt-4o-mini"])
    model: str = "gpt-4o-mini"


@dataclass(frozen=True)
class ChatConfig:
    system_prompt: str = "You are a helpful TRPG GM assistant."
    temperature: float | None = None

    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    max_output_tokens: int | None = None

    stream: bool = False

    enable_tool_roll: bool = True


@dataclass(frozen=True)
class AppConfig:
    active_provider: str = "default"
    providers: dict[str, ProviderConfig] = field(default_factory=lambda: {"default": ProviderConfig()})
    chat: ChatConfig = field(default_factory=ChatConfig)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AppConfig":
        data = data if isinstance(data, dict) else {}
        chat_data = (data.get("chat") or {}) if isinstance(data.get("chat"), dict) else {}

        providers: dict[str, ProviderConfig] = {}
        providers_data = data.get("providers")
        if isinstance(providers_data, dict):
            for name, p in providers_data.items():
                if not isinstance(name, str) or not name:
                    continue
                if not isinstance(p, dict):
                    continue

                extra_headers: dict[str, str] = {}
                raw_headers = p.get("extra_headers")
                if isinstance(raw_headers, dict):
                    extra_headers = {str(k): str(v) for k, v in raw_headers.items()}

                model = p.get("model")
                models: list[str] = []
                raw_models = p.get("models")
                if isinstance(raw_models, list):
                    for m in raw_models:
                        ms = str(m)
                        if ms:
                            models.append(ms)

                model_s = str(model) if model is not None else ""
                if not model_s and models:
                    model_s = models[0]
                if not model_s:
                    model_s = ProviderConfig.model
                if model_s and model_s not in models:
                    models = [model_s] + models
                if not models:
                    models = [ProviderConfig.model]

                providers[name] = ProviderConfig(
                    base_url=str(p.get("base_url", ProviderConfig.base_url)),
                    api_key=str(p.get("api_key", "")),
                    timeout_s=float(p.get("timeout_s", ProviderConfig.timeout_s)),
                    verify_tls=bool(p.get("verify_tls", ProviderConfig.verify_tls)),
                    extra_headers=extra_headers,
                    models=models,
                    model=model_s,
                )

        active_provider = str(data.get("active_provider") or "default")

        if not providers:
            api_data = data.get("api")
            if isinstance(api_data, dict):
                extra_headers: dict[str, str] = {}
                raw_headers = api_data.get("extra_headers")
                if isinstance(raw_headers, dict):
                    extra_headers = {str(k): str(v) for k, v in raw_headers.items()}

                model_s = str(api_data.get("model", ProviderConfig.model))
                providers = {
                    "default": ProviderConfig(
                        base_url=str(api_data.get("base_url", ProviderConfig.base_url)),
                        api_key=str(api_data.get("api_key", "")),
                        timeout_s=float(api_data.get("timeout_s", ProviderConfig.timeout_s)),
                        verify_tls=bool(api_data.get("verify_tls", ProviderConfig.verify_tls)),
                        extra_headers=extra_headers,
                        models=[model_s] if model_s else [ProviderConfig.model],
                        model=model_s or ProviderConfig.model,
                    )
                }
                active_provider = "default"

        if not providers:
            providers = {"default": ProviderConfig()}
            active_provider = "default"

        if active_provider not in providers:
            active_provider = next(iter(providers.keys()))

        def opt_int(key: str) -> int | None:
            v = chat_data.get(key, None)
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        def opt_float(key: str) -> float | None:
            v = chat_data.get(key, None)
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        chat = ChatConfig(
            system_prompt=str(chat_data.get("system_prompt", ChatConfig.system_prompt)),
            temperature=opt_float("temperature"),
            max_tokens=opt_int("max_tokens"),
            max_completion_tokens=opt_int("max_completion_tokens"),
            max_output_tokens=opt_int("max_output_tokens"),
            stream=bool(chat_data.get("stream", ChatConfig.stream)),
            enable_tool_roll=bool(chat_data.get("enable_tool_roll", ChatConfig.enable_tool_roll)),
        )

        return AppConfig(active_provider=active_provider, providers=providers, chat=chat)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path | None = None) -> AppConfig:
    path = path or default_config_path()

    api_key_env = os.environ.get("OPENAI_API_KEY") or os.environ.get("TRPGAI_API_KEY")

    if not path.exists():
        cfg = AppConfig()
        if api_key_env:
            p = cfg.providers.get(cfg.active_provider)
            if p is not None:
                providers = dict(cfg.providers)
                providers[cfg.active_provider] = ProviderConfig(
                    base_url=p.base_url,
                    api_key=str(api_key_env),
                    timeout_s=p.timeout_s,
                    verify_tls=p.verify_tls,
                    extra_headers=p.extra_headers,
                    models=p.models,
                    model=p.model,
                )
                cfg = AppConfig(active_provider=cfg.active_provider, providers=providers, chat=cfg.chat)
        return cfg

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}

    cfg = AppConfig.from_dict(data if isinstance(data, dict) else {})

    if api_key_env:
        p = cfg.providers.get(cfg.active_provider)
        if p is not None:
            providers = dict(cfg.providers)
            providers[cfg.active_provider] = ProviderConfig(
                base_url=p.base_url,
                api_key=str(api_key_env),
                timeout_s=p.timeout_s,
                verify_tls=p.verify_tls,
                extra_headers=p.extra_headers,
                models=p.models,
                model=p.model,
            )
            cfg = AppConfig(active_provider=cfg.active_provider, providers=providers, chat=cfg.chat)

    return cfg


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cfg.to_dict(), ensure_ascii=True, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path
