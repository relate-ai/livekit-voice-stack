from __future__ import annotations

from collections.abc import Mapping

import httpx
from livekit.plugins import openai

from relate_voice.config import LLMConfig


def build_llm(spec: LLMConfig, environment: Mapping[str, str]) -> openai.LLM:
    return openai.LLM.with_openrouter(
        api_key=environment[spec.secret_ref],
        base_url=str(spec.endpoint),
        model=spec.models[0],
        fallback_models=spec.models[1:],
        site_url=str(spec.site_url),
        app_name=spec.app_name,
        temperature=spec.temperature,
        timeout=httpx.Timeout(spec.timeout_seconds),
    )
