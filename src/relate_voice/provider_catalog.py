"""Provider catalog — runtime provider availability and model lists."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("relate_voice.provider_catalog")

PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "description": "Access hundreds of free and paid LLMs via OpenRouter",
        "credential_ref": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            {"id": "poolside/laguna-xs-2.1:free", "name": "Laguna XS", "free": True},
            {"id": "z-ai/glm-5.2:free", "name": "GLM 5.2", "free": True},
            {"id": "cohere/north-mini-code:free", "name": "North Mini Code", "free": True},
            {"id": "meta-llama/llama-4-scout:free", "name": "Llama 4 Scout", "free": True},
            {"id": "qwen/qwen3-235b-a22b:free", "name": "Qwen 3 235B", "free": True},
            {"id": "deepseek/deepseek-r1-0528:free", "name": "DeepSeek R1", "free": True},
            {"id": "google/gemma-3-27b-it:free", "name": "Gemma 3 27B", "free": True},
            {"id": "microsoft/phi-4-reasoning-plus:free", "name": "Phi-4 Reasoning+", "free": True},
        ],
    },
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "description": "Google's Gemini models via the Generative Language API",
        "credential_ref": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "free": True},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "free": True},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "free": False},
        ],
    },
    "opencode_zen": {
        "id": "opencode_zen",
        "name": "OpenCode Zen",
        "description": "OpenCode's managed models (not available as OpenAI-compatible API for voice agents)",
        "credential_ref": None,
        "base_url": None,
        "models": [],
        "unavailable_reason": "OpenCode Zen models are accessed through OpenCode's ACP interface, not a standard OpenAI-compatible API. Use OpenRouter for voice agent LLM access.",
    },
}


def get_provider_catalog() -> list[dict[str, Any]]:
    return list(PROVIDER_CATALOG.values())


def get_provider(provider_id: str) -> dict[str, Any] | None:
    return PROVIDER_CATALOG.get(provider_id)


def check_provider_health(provider_id: str, environment: dict[str, str]) -> dict[str, Any]:
    provider = PROVIDER_CATALOG.get(provider_id)
    if not provider:
        return {"available": False, "reason": "Provider not found"}

    if provider.get("unavailable_reason"):
        return {"available": False, "reason": provider["unavailable_reason"]}

    cred_ref = provider.get("credential_ref")
    if cred_ref and not environment.get(cred_ref):
        return {"available": False, "reason": f"Missing credential: {cred_ref}"}

    # For OpenRouter, check API key validity
    if provider_id == "openrouter":
        api_key = environment.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return {"available": False, "reason": "OPENROUTER_API_KEY not set"}
        try:
            resp = httpx.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return {"available": True, "reason": None}
            return {"available": False, "reason": f"API returned {resp.status_code}"}
        except Exception as exc:
            return {"available": False, "reason": f"Connection failed: {type(exc).__name__}"}

    # For Gemini, check API key validity
    if provider_id == "gemini":
        api_key = environment.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"available": False, "reason": "GEMINI_API_KEY not set"}
        try:
            resp = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                return {"available": True, "reason": None}
            return {"available": False, "reason": f"API returned {resp.status_code}"}
        except Exception as exc:
            return {"available": False, "reason": f"Connection failed: {type(exc).__name__}"}

    return {"available": False, "reason": "Unknown provider"}
